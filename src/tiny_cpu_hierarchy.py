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

# These local boxes have no control-bus boundary of their own.
ADDRESS_HELPERS = {"AddressRegisterLoad", "AddressAccess"}

# Wiring-only transport sheets and functional groups; original unit interfaces stay intact.
CORE_CONTAINERS = {
    *(f"CPU{name}Link" for name in CORE_UNITS),
    "CPUAccumulatorInputUnitLink", "CPUFaultInputUnitLink",
    "CPUFlowStage", "CPUComputeStage", "CPUComputeStageInput",
    "CPUMemoryStage", "CPUStatusStage", "CPUStatusStageInput",
    "CPUHostInputs", "CPUHostOutputs", "CPUInputSource",
}
CORE_OVERVIEW_UNITS = {
    "CPUHostInputs": "HOST_INPUTS", "CPUHostOutputs": "HOST_OUTPUTS",
    "CPUFlowStage": "FLOW_STAGE", "CPUComputeStage": "COMPUTE_STAGE",
    "CPUMemoryStage": "MEMORY_STAGE", "CPUStatusStage": "STATUS_STAGE",
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
    return [-1 if a.get(f"bit{i}") == "none" else int(a.get(f"bit{i}", str(defaults[i])))
            for i in range(incoming)]


def control_bus_splitters(circuit, width=45):
    """Return the physical control-bus breakout or its local single-bit taps."""
    candidates = [c for c in circuit.findall("comp[@name='Splitter']")
                  if int(attributes(c).get("incoming", "2")) == width]
    if not candidates:
        raise ValueError(f"{circuit.get('name')}: control-bus boundary is missing")
    return candidates


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


def add_output_term(circuit, output_name, term_name):
    """Inject output OR term into a test copy, independent of gate internals.

    Both signals must be distinct one-bit, right-side output pins. Existing
    gates and wires stay in place. Extending only the target pin horizontally
    preserves its automatic symbol order; explicit symbol bindings follow it.
    Never call this on a production circuit to be saved back to its source.
    """
    def output_pin(name):
        pins = [p for p in circuit.findall("comp[@name='Pin']")
                if attributes(p).get("label") == name]
        if len(pins) != 1:
            raise ValueError(f"missing or ambiguous output: {name}")
        a = attributes(pins[0])
        if (a.get("type") != "output" or a.get("width", "1") != "1"
                or a.get("facing", "east") != "west"):
            raise ValueError(f"expected a one-bit right-side output: {name}")
        return pins[0]

    output, term = output_pin(output_name), output_pin(term_name)
    if output is term:
        raise ValueError("output and injected term must be distinct")
    old = output.get("loc")
    x, y = point(old)
    tx, ty = point(term.get("loc"))
    if any(p is not output and point(p.get("loc"))[1] == y
           for p in circuit.findall("comp[@name='Pin']")
           if attributes(p).get("type") == "output"):
        raise ValueError("mutation requires a unique output row")
    if abs(ty - y) <= 20:
        raise ValueError("mutation requires separate source and output rows")
    points = [point(c.get("loc")) for c in circuit.findall("comp")]
    points += [point(w.get(end)) for w in circuit.findall("wire") for end in ("from", "to")]
    gx = (max(p[0] for p in points) // 100 + 3) * 100
    new = location((gx, y))
    gate = ET.SubElement(circuit, "comp", {"lib": "1", "name": "OR Gate", "loc": new})
    ET.SubElement(gate, "a", {"name": "label", "val": "TEST_OUTPUT_TERM"})
    for route in (((x, y), (gx - 100, y), (gx - 100, y - 20), (gx - 50, y - 20)),
                  ((tx, ty), (gx - 80, ty), (gx - 80, y + 20), (gx - 50, y + 20))):
        for start, end in zip(route, route[1:]):
            if start != end:
                ET.SubElement(circuit, "wire", {"from": location(start), "to": location(end)})
    output.set("loc", new)
    for binding in circuit.findall("appear/circ-port"):
        if binding.get("pin") == old.strip("()"):
            binding.set("pin", new.strip("()"))


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

    if kind == "Text":
        return []  # Sheet annotations have no electrical terminals.

    def terminal(dx, dy, bits, incoming, outgoing, name=""):
        dx, dy = _rotate(dx, dy, facing)
        return ((x + dx, y + dy), bits, incoming, outgoing, name)

    if kind in definitions and component.get("lib") not in {str(i) for i in range(10)}:
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
    if kind == "Comparator":
        return [terminal(-40, -10, width, True, False, "a"),
                terminal(-40, 10, width, True, False, "b"),
                terminal(0, -10, 1, False, True, "gt"),
                terminal(0, 0, 1, False, True, "eq"),
                terminal(0, 10, 1, False, True, "lt")]
    if kind == "Register" and a.get("appearance") == "logisim_evolution":
        return [terminal(60, 30, width, False, True, "q"),
                terminal(0, 30, width, True, False, "d"),
                terminal(0, 70, 1, True, False, "clock"),
                terminal(30, 90, 1, True, False, "reset"),
                terminal(0, 50, 1, True, False, "enable")]
    if kind.endswith(" Gate"):
        if kind == "NOT Gate":
            return [terminal(0, 0, width, False, True, "output"),
                    terminal(-int(a.get("size", "30")), 0, width, True, False, "0")]
        count = int(a.get("inputs", "2"))
        size = int(a.get("size", "50"))
        depth = size + (10 if kind in {"NAND Gate", "NOR Gate", "XNOR Gate"} else 0)
        spacing = 10 if size == 30 or count >= 4 else 20
        offsets = ([spacing * (i - count // 2) for i in range(count)] if count % 2
                   else [spacing * (i - count // 2 + (i >= count // 2)) for i in range(count)])
        return [terminal(0, 0, width, False, True, "output")] + [
            terminal(-depth - (10 if a.get(f"negate{i}") == "true" else 0), dy,
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


def flatten_core(project, *, transport_only=False, top_name="TinyCPUMain"):
    """Expand the declared CPU hierarchy for semantic offline checks.

    With transport_only, keep the original eight functional units atomic.
    This compares their original terminals through the new wiring sheets.
    Control buses are followed bit by bit. Tunnel names are scoped to each
    instance; matching names alone never connect different units. Resulting
    wires are analysis aliases, not a drawable or runnable replacement CPU.
    """
    result = copy.deepcopy(project)
    definitions = {c.get("name"): c for c in result.findall("circuit")}
    main = definitions.get(top_name)
    expanded = CORE_CONTAINERS if transport_only else CORE_CONTAINERS | CORE_UNITS.keys() | ADDRESS_HELPERS
    if main is None or not any(c.get("name") in expanded for c in main.findall("comp")):
        return result
    bits = UnionFind()
    kept = []
    instances = []

    def visit(circuit, path, shift, top=False):
        state = CircuitBits(definitions, circuit, path)
        bus_splitters = (set(circuit.findall("comp[@name='Splitter']"))
                         if circuit.get("name") in CORE_CONTAINERS else
                         set(control_bus_splitters(circuit))
                         if not transport_only and not top and circuit.get("name") in CORE_UNITS else set())
        for c in circuit.findall("comp"):
            kind = c.get("name")
            a = attributes(c)
            if kind in expanded and c.get("lib") is None:
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
            elif kind not in {"Tunnel", "Text"} and (top or kind != "Pin") and c not in bus_splitters:
                clone = copy.deepcopy(c)
                # Resolve the analysis name from the public output connection.
                # The visible caption may be absent or renamed during layout;
                # neither case changes the electrical boundary being checked.
                if circuit.get("name") == "AddressAccess" and kind == "NOR Gate":
                    output = next((pin for pin in circuit.findall("comp[@name='Pin']")
                                   if attributes(pin).get("label") == "ACCESS_VALID"), None)
                    if output is not None and wire_path_exists(circuit, c.get("loc"), output.get("loc")):
                        label = clone.find("a[@name='label']")
                        if label is None:
                            label = ET.SubElement(clone, "a", name="label")
                        label.set("val", "ACCESS_VALID")
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

    visit(main, top_name, 0, top=True)
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
    definitions = {c.get("name"): c for c in project.findall("circuit")}
    modular = any(c.get("name") in CORE_CONTAINERS for c in main.findall("comp"))
    if modular:
        boxes = {c.get("name"): attributes(c).get("label") for c in main.findall("comp") if c.get("name") != "Pin"}
        if boxes != CORE_OVERVIEW_UNITS or len(main.findall("comp")) != len(main.findall("comp[@name='Pin']")) + len(CORE_OVERVIEW_UNITS):
            raise ValueError("CPU overview contains a primitive or undeclared functional box")
        def audit(circuit, active=()):
            name = circuit.get("name")
            if name in active:
                raise ValueError("recursive CPU transport hierarchy")
            for component in circuit.findall("comp"):
                kind = component.get("name")
                if kind in CORE_CONTAINERS and component.get("lib") is None:
                    audit(definitions[kind], (*active, name))
                elif kind not in CORE_UNITS and kind not in {"Pin", "Splitter"}:
                    raise ValueError(f"CPU transport contains a primitive or undeclared box: {kind}")
        audit(main)
        overview = flatten_core(project, transport_only=True).find("circuit[@name='TinyCPUMain']")
    else:
        overview = main
    counts = defaultdict(int)
    for c in overview.findall("comp"):
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
        splitters = control_bus_splitters(circuit, width)
        if len(pins) != 1:
            raise ValueError(f"{name}: control-bus boundary is missing")
        pa = attributes(pins[0])
        if (int(pa.get("width", "1")) != width
                or (pa.get("type") == "output") != (name == "FetchUnit")):
            raise ValueError(f"{name}: control-bus bit mapping differs from contract")
        full_breakout = (len(splitters) == 1
                         and int(attributes(splitters[0]).get("fanout", "2")) == width
                         and splitter_groups(splitters[0]) == list(range(width)))
        tapped = []
        for splitter in splitters:
            groups = splitter_groups(splitter)
            if (int(attributes(splitter).get("fanout", "2")) != 1
                    or groups.count(0) != 1 or any(g not in (-1, 0) for g in groups)):
                break
            tapped.append(groups.index(0))
        tap_signals = {
            "AccumulatorUnit": {"LOAD_ADR", "LOAD_ADR_REG", "LOAD_REG_OFF", "INVERT", "INPUT", "ACC_WRITE_REQUEST"},
            "AddressUnit": {"LD_REG_CONST", "LD_REG_ADR", "ADDR_ARGUMENT", "ADDR_REG_ARGUMENT", "STORE_ADR_REG",
                            "LOAD_ADR_REG", "ADDR_REG_OFFS_ARGUMENT", "STORE_REG_OFF", "LOAD_REG_OFF",
                            "LOAD_ADR", "STORE_ADR", "PRINT_ADR"},
            "MemoryUnit": {"ADDR_ARGUMENT", "ADDR_REG_ARGUMENT", "ADDR_REG_OFFS_ARGUMENT",
                           "STORE_ADR", "STORE_ADR_REG", "STORE_REG_OFF", "ACC_MEMORY_REQUEST"},
            "ExecutionUnit": {"ADD_OPERAND", "SUB_OPERAND", "MUL_OPERAND", "DIV_OPERAND",
                              "AND_OPERAND", "OR_OPERAND", "XOR_OPERAND", "CONST_ARGUMENT", "INVERT"},
            "FaultUnit": {"SET_ILL", "CLEAR_ERROR", "INPUT", "PRINT", "PRINT_ADR", "ACC_MEMORY_REQUEST"},
            "BranchUnit": {"JUMP_ADR", "JUMP_ZERO", "JUMP_NOT_ZERO", "JUMP_NEGATIVE",
                           "JUMP_ERROR", "JUMP_NOT_ERROR"},
            # Preserve the existing probe wiring, including its historical
            # captions. Their names are not a new decoder signal contract.
            "CoreDiagnostics": {"JUMP_ADR", "JUMP_ZERO", "JUMP_NOT_ZERO", "JUMP_NEGATIVE",
                                "JUMP_ERROR", "JUMP_NOT_ERROR", "LOAD_CONST", "ACC_MEMORY_REQUEST",
                                "LOAD_REG_OFF", "LD_REG_CONST", "LD_REG_ADR", "SET_OVF"},
        }.get(name, set())
        required_taps = {signal["bit"] for signal in signals if signal["name"] in tap_signals}
        local_taps = (bool(tap_signals) and len(tapped) == len(splitters) == len(required_taps)
                      and len(set(tapped)) == len(required_taps) and set(tapped) == required_taps)
        if not (full_breakout or local_taps):
            raise ValueError(f"{name}: control-bus bit mapping differs from contract")
        if any(not wire_path_exists(circuit, pins[0].get("loc"), splitter.get("loc"))
               for splitter in splitters):
            raise ValueError(f"{name}: control-bus breakout is disconnected")


def find_core_instance(project, label):
    """Find an existing functional instance through the new wrapper units."""
    definitions = {c.get("name"): c for c in project.findall("circuit")}

    def visit(circuit):
        for c in circuit.findall("comp"):
            if attributes(c).get("label") == label:
                return circuit, c
            if c.get("name") in CORE_UNITS.keys() | ADDRESS_HELPERS | CORE_CONTAINERS and c.get("lib") is None:
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
    return _topology_fingerprint(definitions, main)


def circuit_topology_fingerprint(project, name, external_definitions=None):
    """Fingerprint a circuit's components and real terminal nets, without layout."""
    definitions = dict(external_definitions or {})
    definitions.update({c.get("name"): c for c in project.findall("circuit")})
    return _topology_fingerprint(definitions, definitions[name])


def _topology_fingerprint(definitions, main):
    state = CircuitBits(definitions, main, "analysis")
    colours, neighbours = {}, defaultdict(list)

    def node(key, value):
        colours[key] = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

    def edge(a, b):
        neighbours[a].append(b)
        neighbours[b].append(a)

    for index, c in enumerate(main.findall("comp")):
        if c.get("name") == "Text":
            continue
        component = ("component", index)
        a = attributes(c)
        kind = c.get("name")
        commutative = kind in {"AND Gate", "OR Gate", "XOR Gate", "NAND Gate", "NOR Gate", "XNOR Gate"}
        inversions = {key: value for key, value in a.items() if key.startswith("negate")}
        # Canvas presentation and unsupported labels disappear on a GUI save.
        # Keep electrical parameters, including Logisim's omitted defaults.
        a = {k: v for k, v in a.items()
             if k not in {"appearance", "facing", "spacing", "label", "radix", "radix2"}}
        if kind.endswith(" Gate"):
            # A gate's caption font changes no electrical port.
            a.pop("labelfont", None)
            a.pop("labelloc", None)
        if commutative:
            # Gate inputs may be exchanged in an authored drawing. Keep each
            # inversion attached to its connected term instead of its row.
            a = {key: value for key, value in a.items() if not key.startswith("negate")}
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
            if commutative and incoming:
                node(terminal, ["gate-input", width, inversions.get(f"negate{label}") == "true"])
            else:
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


def circuit_bit_network(definitions, circuit):
    """Return a physical state and bit aliases through all visible splitters."""
    state = CircuitBits(definitions, circuit, "signals")
    bits = UnionFind()
    for splitter in circuit.findall("comp[@name='Splitter']"):
        ports = state.ports[id(splitter)]
        incoming = state.vector(ports[0][0], ports[0][1])
        offsets = defaultdict(int)
        for bit, group in enumerate(splitter_groups(splitter)):
            if group < 0:
                continue
            branch = ports[group + 1]
            target = state.vector(branch[0], branch[1])[offsets[group]]
            bits.union(incoming[bit], target)
            offsets[group] += 1
    return state, bits
