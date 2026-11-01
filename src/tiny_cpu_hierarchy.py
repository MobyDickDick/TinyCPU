"""Bit-accurate connectivity and an analysis view of the modular CPU.

The analysis view is never written to a production circuit or executed. It
lets existing component-level checks inspect real connections across unit
pins, scoped tunnels and control-bus splitters without fixing canvas positions.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections import defaultdict
import xml.etree.ElementTree as ET


CORE_UNITS = {
    "FetchUnit": "FETCH_UNIT",
    "AccumulatorUnit": "ACCUMULATOR_UNIT",
    "AddressUnit": "ADDRESS_UNIT",
    "MemoryUnit": "MEMORY_UNIT",
    "ExecutionUnit": "EXECUTION_UNIT",
    "FaultUnit": "FAULT_UNIT",
    "BranchUnit": "BRANCH_UNIT",
    "CoreDiagnostics": "CORE_DIAGNOSTICS",
}


def attributes(component):
    return {a.get("name"): a.get("val") for a in component.findall("a")}


def splitter_groups(component):
    """Logisim omits bit mappings equal to its balanced ascending default."""
    a = attributes(component)
    incoming, fanout = int(a.get("incoming", "2")), int(a.get("fanout", "2"))
    size, extra = divmod(incoming, fanout)
    defaults = [group for group in range(fanout)
                for _ in range(size + (group < extra))]
    return [int(a.get(f"bit{i}", str(defaults[i]))) for i in range(incoming)]


def control_bus_splitter(circuit, width=45):
    """Find the bus by its electrical shape; Splitter has no saved label."""
    candidates = [c for c in circuit.findall("comp[@name='Splitter']")
                  if int(attributes(c).get("incoming", "2")) == width
                  and int(attributes(c).get("fanout", "2")) == width]
    if len(candidates) != 1:
        raise ValueError(f"{circuit.get('name')}: control-bus boundary is missing or ambiguous")
    return candidates[0]


def point(text):
    return tuple(map(int, text.strip("()").split(",")))


def location(value):
    return f"({value[0]},{value[1]})"


class UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, key):
        self.parent.setdefault(key, key)
        if self.parent[key] != key:
            self.parent[key] = self.find(self.parent[key])
        return self.parent[key]

    def union(self, left, right):
        left, right = self.find(left), self.find(right)
        if left != right:
            self.parent[right] = left


def on_segment(p, a, b):
    return ((a[0] == b[0] == p[0] and min(a[1], b[1]) <= p[1] <= max(a[1], b[1]))
            or (a[1] == b[1] == p[1] and min(a[0], b[0]) <= p[0] <= max(a[0], b[0])))


def wire_network(circuit, extra_points=()):
    """Resolve physical junctions; diagonal analysis aliases join endpoints only."""
    wires = [(point(w.get("from")), point(w.get("to"))) for w in circuit.findall("wire")]
    points = set(extra_points) | {p for pair in wires for p in pair}
    result = UnionFind()
    for a, b in wires:
        result.union(a, b)
        if a[0] == b[0] or a[1] == b[1]:
            for p in points:
                if on_segment(p, a, b):
                    result.union(a, p)
    return result


def wire_path_exists(circuit, start, end):
    a, b = point(start), point(end)
    network = wire_network(circuit, (a, b))
    return network.find(a) == network.find(b)


def gate_input_constant(circuit, gate_label, input_name):
    """Locate a constant by the gate contact it drives, even after GUI save."""
    gates = [c for c in circuit.findall("comp") if attributes(c).get("label") == gate_label]
    if len(gates) != 1:
        raise ValueError(f"missing or ambiguous gate: {gate_label}")
    contacts = [p for p, _, incoming, _, name in component_ports({}, gates[0])
                if incoming and name == str(input_name)]
    if len(contacts) != 1:
        raise ValueError(f"missing gate input: {gate_label}.{input_name}")
    network = wire_network(circuit, contacts)
    constants = [c for c in circuit.findall("comp[@name='Constant']")
                 if network.find(point(c.get("loc"))) == network.find(contacts[0])]
    if len(constants) != 1:
        raise ValueError(f"missing or ambiguous constant at {gate_label}.{input_name}")
    return constants[0]


def _rotate(dx, dy, facing):
    return {"east": (dx, dy), "south": (-dy, dx),
            "west": (-dx, -dy), "north": (dy, -dx)}[facing]


def component_ports(definitions, component):
    """Return (point, width, input, output, name) for supported wiring shapes."""
    a = attributes(component)
    kind = component.get("name")
    x, y = point(component.get("loc"))
    width = int(a.get("width", "1"))
    facing = a.get("facing", "east")

    def terminal(dx, dy, bits, incoming, outgoing, name=""):
        dx, dy = _rotate(dx, dy, facing)
        return ((x + dx, y + dy), bits, incoming, outgoing, name)

    if component.get("lib") is None and kind in definitions:
        # Import lazily: verify imports this module for its analysis view.
        from tiny_cpu_verify import generated_symbol_ports
        definition = definitions[kind]
        ports = generated_symbol_ports(definition, component)
        return [(point(ports[p["label"]]), int(p.get("width", "1")),
                 p.get("type", "input") != "output", p.get("type") == "output", p["label"])
                for p in sorted((attributes(pin) for pin in definition.findall("comp[@name='Pin']")),
                                key=lambda p: p["label"])]
    if kind == "Pin":
        output = a.get("type") == "output"
        return [((x, y), width, output, not output, a.get("label", ""))]
    if kind in {"Constant", "Clock"}:
        return [((x, y), width, False, True, "")]
    if kind in {"Probe", "Tunnel"}:
        return [((x, y), int(a.get("width", "0")), True, False, a.get("label", ""))]
    if kind == "Splitter":
        count = int(a.get("fanout", "2"))
        incoming = int(a.get("incoming", "2"))
        groups = splitter_groups(component)
        spacing = int(a.get("spacing", "1"))
        appearance = a.get("appear", "left")
        side = {"left": -1, "right": 1, "center": 0, "legacy": 0}[appearance]
        pitch = 10 * spacing
        result = [((x, y), incoming, True, False, "incoming")]
        for index in range(count):
            if facing in {"east", "west"}:
                sign = 1 if facing == "east" else -1
                first = (-pitch * (count // 2) if not side else
                         10 if sign * side > 0 else -10 - pitch * (count - 1))
                p = (x + sign * 20, y + first + pitch * index)
            else:
                sign = 1 if facing == "north" else -1
                first = (pitch * ((count + 1) // 2 - 1) if not side else
                         -10 if sign * side < 0 else 10 + pitch * (count - 1))
                p = (x + first - pitch * index, y - sign * 20)
            result.append((p, groups.count(index), False, True, str(index)))
        return result
    if kind == "Multiplexer":
        count = 1 << int(a.get("select", "1"))
        return ([terminal(0, 0, width, False, True, "output")]
                + [terminal(-30, 20 * i - 10 * (count - 1), width, True, False, str(i))
                   for i in range(count)]
                + [terminal(-20, 10 * count, int(a.get("select", "1")), True, False, "select")])
    if kind.endswith(" Gate"):
        if kind == "NOT Gate":
            return [terminal(0, 0, width, False, True, "output"),
                    terminal(-int(a.get("size", "30")), 0, width, True, False, "0")]
        count = int(a.get("inputs", "2"))
        size = int(a.get("size", "50"))
        spacing = 10 if size == 30 or count >= 4 else 20
        offsets = ([spacing * (i - count // 2) for i in range(count)] if count % 2
                   else [spacing * (i - count // 2 + (i >= count // 2)) for i in range(count)])
        return [terminal(0, 0, width, False, True, "output")] + [
            terminal(-size - (10 if a.get(f"negate{i}") == "true" else 0), dy,
                     width, True, False, str(i)) for i, dy in enumerate(offsets)]
    raise ValueError(f"unsupported analysis component: {kind}")


class CircuitBits:
    """A circuit instance's physical nets, with scoped tunnel aliases."""
    def __init__(self, definitions, circuit, path):
        self.path = path
        self.circuit = circuit
        self.ports = {id(c): component_ports(definitions, c) for c in circuit.findall("comp")}
        self.network = wire_network(circuit, (p for ports in self.ports.values() for p, *_ in ports))
        tunnels = {}
        for c in circuit.findall("comp[@name='Tunnel']"):
            label = attributes(c).get("label", "")
            p = point(c.get("loc"))
            if label in tunnels:
                self.network.union(p, tunnels[label])
            else:
                tunnels[label] = p
        self.widths = {}
        for ports in self.ports.values():
            for p, width, *_ in ports:
                if width:
                    net = self.network.find(p)
                    if net in self.widths and self.widths[net] != width:
                        raise ValueError(f"{path}: incompatible widths {self.widths[net]}/{width} at {p}")
                    self.widths[net] = width

    def vector(self, p, width=0):
        net = self.network.find(p)
        width = width or self.widths.get(net, 1)
        return [(self.path, net, bit) for bit in range(width)]


def flatten_core(project):
    """Expand only the new functional units for semantic offline checks.

    Control buses are followed bit by bit. Tunnel names are scoped to each
    instance; matching names alone never connect different units. Resulting
    wires are analysis aliases, not a drawable or runnable replacement CPU.
    """
    result = copy.deepcopy(project)
    definitions = {c.get("name"): c for c in result.findall("circuit")}
    main = definitions.get("TinyCPUMain")
    if main is None or not any(c.get("name") in CORE_UNITS for c in main.findall("comp")):
        return result
    bits = UnionFind()
    kept = []
    instances = []

    def visit(circuit, path, shift, top=False):
        state = CircuitBits(definitions, circuit, path)
        bus_splitter = None if top else control_bus_splitter(circuit)
        for c in circuit.findall("comp"):
            kind = c.get("name")
            a = attributes(c)
            if kind in CORE_UNITS and c.get("lib") is None:
                child_shift = 10000 * (len(instances) + 1)
                instances.append(path + "/" + a.get("label", kind))
                child = visit(definitions[kind], instances[-1], child_shift)
                from tiny_cpu_verify import generated_symbol_ports
                parent_ports = generated_symbol_ports(definitions[kind], c)
                for pin in definitions[kind].findall("comp[@name='Pin']"):
                    pa = attributes(pin)
                    for outer, inner in zip(
                            state.vector(point(parent_ports[pa["label"]]), int(pa.get("width", "1"))),
                            child.vector(point(pin.get("loc")), int(pa.get("width", "1")))):
                        bits.union(outer, inner)
            elif kind != "Tunnel" and (top or kind != "Pin") and c is not bus_splitter:
                clone = copy.deepcopy(c)
                x, y = point(c.get("loc"))
                clone.set("loc", location((x + shift, y + shift)))
                ports = [(location((p[0] + shift, p[1] + shift)), state.vector(p, width))
                         for p, width, *_ in state.ports[id(c)]]
                kept.append((clone, ports))
            if kind == "Splitter":
                ports = state.ports[id(c)]
                incoming = state.vector(ports[0][0], ports[0][1])
                offsets = defaultdict(int)
                groups = splitter_groups(c)
                for bit in range(len(incoming)):
                    group = groups[bit]
                    if group < 0:  # Explicitly unconnected splitter bit.
                        continue
                    branch = ports[group + 1]
                    outgoing = state.vector(branch[0], branch[1])
                    bits.union(incoming[bit], outgoing[offsets[group]])
                    offsets[group] += 1
        return state

    visit(main, "TinyCPUMain", 0, top=True)
    for c in list(main):
        if c.tag in {"comp", "wire"}:
            main.remove(c)
    nets = defaultdict(set)
    for c, ports in kept:
        main.append(c)
        for p, vector in ports:
            nets[tuple(bits.find(bit) for bit in vector)].add(p)
    for index, points in enumerate(nets.values()):
        if len(points) < 2:
            continue
        alias = location((-1000000 - index * 10, -2000000 - index * 10))
        for p in sorted(points):
            ET.SubElement(main, "wire", {"from": p, "to": alias})
    return result


def verify_core_modularity(project, control_contract=None):
    main = project.find("circuit[@name='TinyCPUMain']")
    if main is None:
        raise ValueError("CPU overview is missing")
    counts = defaultdict(int)
    for c in main.findall("comp"):
        if c.get("name") == "Pin":
            continue
        if c.get("lib") is not None or c.get("name") not in CORE_UNITS:
            raise ValueError(f"CPU overview contains a primitive or undeclared box: {c.get('name')}")
        counts[c.get("name")] += 1
        if attributes(c).get("label") != CORE_UNITS[c.get("name")]:
            raise ValueError(f"CPU overview box label differs: {c.get('name')}")
    if dict(counts) != dict.fromkeys(CORE_UNITS, 1):
        raise ValueError("CPU overview must contain each of its eight functional units exactly once")
    if control_contract is None:
        return
    definitions = {c.get("name"): c for c in project.findall("circuit")}
    decoder = definitions["FetchDecodeControls"]
    outputs = sorted((p for p in decoder.findall("comp[@name='Pin']")
                      if attributes(p).get("type") == "output"),
                     key=lambda p: (point(p.get("loc"))[1], point(p.get("loc"))[0]))
    signals = [{"bit": i, "name": attributes(p)["label"]} for i, p in enumerate(outputs)]
    width = len(signals)
    if (control_contract.get("schema_version") != 1
            or control_contract.get("signals") != signals
            or control_contract.get("width") != width
            or control_contract.get("units") != CORE_UNITS):
        raise ValueError("CPU control-bus contract differs from the decoder interface")
    for output, key in ((False, "public_inputs"), (True, "public_outputs")):
        pins = sorted((p for p in main.findall("comp[@name='Pin']")
                       if (attributes(p).get("type") == "output") == output),
                      key=lambda p: (point(p.get("loc"))[1], point(p.get("loc"))[0]))
        interface = [{"name": attributes(p)["label"],
                      "width": int(attributes(p).get("width", "1"))} for p in pins]
        if interface != control_contract.get(key):
            raise ValueError(f"CPU public symbol pin order differs: {key}")
    for name in CORE_UNITS:
        circuit = definitions[name]
        pins = [p for p in circuit.findall("comp[@name='Pin']")
                if attributes(p).get("label") == "CONTROL"]
        splitter = control_bus_splitter(circuit, width)
        if len(pins) != 1:
            raise ValueError(f"{name}: control-bus boundary is missing")
        pa, sa = attributes(pins[0]), attributes(splitter)
        if (int(pa.get("width", "1")) != width
                or (pa.get("type") == "output") != (name == "FetchUnit")
                or int(sa.get("incoming", "2")) != width
                or int(sa.get("fanout", "2")) != width
                or splitter_groups(splitter) != list(range(width))):
            raise ValueError(f"{name}: control-bus bit mapping differs from contract")


def find_core_instance(project, label):
    """Find an existing functional instance through the new wrapper units."""
    definitions = {c.get("name"): c for c in project.findall("circuit")}

    def visit(circuit):
        for c in circuit.findall("comp"):
            if attributes(c).get("label") == label:
                return circuit, c
            if c.get("name") in CORE_UNITS and c.get("lib") is None:
                found = visit(definitions[c.get("name")])
                if found is not None:
                    return found
        return None

    found = visit(definitions["TinyCPUMain"])
    if found is None:
        raise ValueError(f"missing core instance: {label}")
    return found


def core_topology_fingerprint(project):
    """Position-independent component/port/net fingerprint for extraction QA.

    Existing leaf circuits are atomic. Unit wrappers, scoped tunnels and bus
    routing disappear through real bit-level connectivity, not through names.
    Electrical acceptance remains the independent behavioral check.
    """
    flat = flatten_core(project)
    definitions = {c.get("name"): c for c in flat.findall("circuit")}
    main = definitions["TinyCPUMain"]
    state = CircuitBits(definitions, main, "analysis")
    colours, neighbours = {}, defaultdict(list)

    def node(key, value):
        colours[key] = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

    def edge(a, b):
        neighbours[a].append(b)
        neighbours[b].append(a)

    for index, c in enumerate(main.findall("comp")):
        component = ("component", index)
        a = attributes(c)
        kind = c.get("name")
        # Canvas presentation and unsupported labels disappear on a GUI save.
        # Keep electrical parameters, including Logisim's omitted defaults.
        a = {k: v for k, v in a.items()
             if k not in {"appearance", "facing", "spacing", "label"}}
        if kind.endswith(" Gate"):
            # A gate's caption font changes no electrical port.
            a.pop("labelfont", None)
        if kind == "Pin":
            a["label"] = attributes(c)["label"]
        if kind in {"Pin", "Constant", "Multiplexer", "Probe"} or kind.endswith(" Gate"):
            a.setdefault("width", "1")
        if kind == "Constant":
            a.setdefault("value", "0x1")
        if kind.endswith(" Gate") and kind != "NOT Gate":
            a.setdefault("inputs", "2")
        if kind == "Splitter":
            a.update({f"bit{i}": str(group) for i, group in enumerate(splitter_groups(c))})
        node(component, [kind, c.get("lib"), a])
        for port_index, (p, width, incoming, outgoing, label) in enumerate(state.ports[id(c)]):
            width = width or state.widths.get(state.network.find(p), 1)
            terminal = ("port", index, port_index)
            net = ("net", state.network.find(p))
            node(terminal, ["port", port_index, width, incoming, outgoing, label])
            if net not in colours:
                node(net, ["net", width])
            edge(component, terminal)
            edge(terminal, net)
    for _ in range(32):
        colours = {n: hashlib.sha256((colour + ":" + ":".join(
            sorted(colours[other] for other in neighbours[n]))).encode()).hexdigest()
                   for n, colour in colours.items()}
    return hashlib.sha256("\n".join(sorted(colours.values())).encode()).hexdigest()
