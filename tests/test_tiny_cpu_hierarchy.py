import copy
import json
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tiny_cpu_hierarchy import (
    attributes, control_bus_splitter, control_bus_splitters, core_topology_fingerprint, flatten_core, gate_input_constant,
    splitter_groups, verify_core_modularity, wire_path_exists,
)
from tiny_cpu_verify import generated_symbol_ports

ROOT = Path(__file__).resolve().parents[1]


class HierarchyTests(unittest.TestCase):
    def setUp(self):
        self.project = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        self.contract = json.loads((ROOT / "hardware/logisim/tinycpu-core-control-v1.json").read_text())

    def test_overview_contains_exactly_the_eight_functional_units(self):
        verify_core_modularity(self.project, self.contract)

    def test_execution_unit_contains_its_operations_instance(self):
        unit = self.project.find("circuit[@name='ExecutionUnit']")
        instances = unit.findall("comp[@name='Operations']")
        self.assertEqual(len(instances), 1)
        self.assertEqual(attributes(instances[0]).get("label"), "OPERATIONS_INSTANCE")

    def test_memory_write_mux_uses_combined_write_request(self):
        from tiny_cpu_hierarchy import CircuitBits
        definitions = {c.get("name"): c for c in self.project.findall("circuit")}
        unit = definitions["MemoryUnit"]
        state = CircuitBits(definitions, unit, "memory")
        memory, = unit.findall("comp[@name='Memory']")
        ram_guard = next(c for c in unit.findall("comp[@name='AND Gate']")
                         if attributes(c).get("label") == "VALID_RAM_WRITE")
        write_enable = next(p for p, *_, name in state.ports[id(ram_guard)] if name == "0")
        muxes = [c for c in unit.findall("comp[@name='Multiplexer']")
                 if any(name == "output" and state.network.find(p) == state.network.find(write_enable)
                        for p, *_, name in state.ports[id(c)])]
        self.assertEqual(len(muxes), 1)
        ports = {name: p for p, *_, name in state.ports[id(muxes[0])]}
        request = next(c for c in unit.findall("comp[@name='AND Gate']")
                       if attributes(c).get("label") == "VALID_MEMORY_WRITE_REQUEST")
        combined = next(p for p, *_, name in state.ports[id(request)] if name == "output")
        pins = {attributes(c)["label"]: c for c in unit.findall("comp[@name='Pin']")}
        for port, source in (("0", combined), ("1", state.ports[id(pins["RAM_WRITE"])][0][0]),
                             ("select", state.ports[id(pins["EXT_SELECT"])][0][0])):
            with self.subTest(port=port):
                self.assertEqual(state.network.find(ports[port]), state.network.find(source))

    def test_operand_validity_selector_uses_not_instead_of_xor(self):
        from tiny_cpu_hierarchy import CircuitBits, location
        definitions = {c.get("name"): c for c in self.project.findall("circuit")}
        circuit = definitions["Operations"]
        state = CircuitBits(definitions, circuit, "operations")
        invert = next(c for c in circuit.findall("comp[@name='NOT Gate']")
                      if attributes(c).get("label") == "OPERAND_INVALID")
        input_terminal = next(p for p, _, incoming, _, _ in state.ports[id(invert)] if incoming)
        selectors = [c for c in circuit.findall("comp[@name='Multiplexer']")
                     if state.network.find(state.ports[id(c)][0][0])
                     == state.network.find(input_terminal)]
        self.assertEqual(len(selectors), 1)
        select = next(p for p, _, _, _, name in state.ports[id(selectors[0])] if name == "select")
        pins = {attributes(c).get("label"): c for c in circuit.findall("comp[@name='Pin']")}
        self.assertTrue(wire_path_exists(circuit, location(select), pins["NOT_OPERAND"].get("loc")))
        self.assertFalse(wire_path_exists(circuit, location(select), pins["XOR_OPERAND"].get("loc")))

    def test_primitive_cannot_be_added_to_the_overview(self):
        main = self.project.find("circuit[@name='TinyCPUMain']")
        ET.SubElement(main, "comp", {"lib": "1", "name": "AND Gate", "loc": "(100,100)"})
        with self.assertRaisesRegex(ValueError, "primitive"):
            verify_core_modularity(self.project, self.contract)

    def test_extracted_network_matches_accepted_flat_topology(self):
        self.assertEqual(core_topology_fingerprint(self.project), self.contract["topology_sha256"])

    def test_disconnected_control_bus_is_not_hidden_by_scoped_tunnel_names(self):
        main = self.project.find("circuit[@name='TinyCPUMain']")
        unit = next(c for c in main.findall("comp") if c.get("name") == "MemoryUnit")
        definition = self.project.find("circuit[@name='MemoryUnit']")
        terminal = generated_symbol_ports(definition, unit)["CONTROL"]

        def store_connected():
            flat = flatten_core(self.project)
            overview = flat.find("circuit[@name='TinyCPUMain']")
            decoder = next(c for c in overview.findall("comp") if c.get("name") == "FetchDecodeControls")
            controls = generated_symbol_ports(flat.find("circuit[@name='FetchDecodeControls']"), decoder)
            gate = next(c for c in overview.findall("comp")
                        if attributes(c).get("label") == "MEMORY_WRITE_REQUEST")
            x, y = map(int, gate.get("loc").strip("()").split(","))
            return wire_path_exists(overview, controls["STORE_ADR"], f"({x - 50},{y - 20})")

        self.assertTrue(store_connected())
        wire = next(w for w in main.findall("wire") if terminal in w.attrib.values())
        main.remove(wire)
        self.assertFalse(store_connected())
        self.assertNotEqual(core_topology_fingerprint(self.project), self.contract["topology_sha256"])

    def test_swapped_control_bit_is_rejected(self):
        unit = self.project.find("circuit[@name='AddressUnit']")
        splitter = control_bus_splitters(unit)[0]
        groups = splitter_groups(splitter)
        selected = next(i for i, group in enumerate(groups) if group >= 0)
        for bit, value in ((selected, "none"), ((selected + 1) % len(groups), str(groups[selected]))):
            attribute = splitter.find(f"a[@name='bit{bit}']")
            if attribute is None:
                attribute = ET.SubElement(splitter, 'a', {'name': f'bit{bit}'})
            attribute.set('val', value)
        with self.assertRaisesRegex(ValueError, "bit mapping"):
            verify_core_modularity(self.project, self.contract)

    def test_accumulator_memory_request_uses_all_three_memory_load_modes(self):
        from tiny_cpu_hierarchy import CircuitBits
        definitions = {c.get("name"): c for c in self.project.findall("circuit")}
        unit = definitions["AccumulatorUnit"]
        state = CircuitBits(definitions, unit, "accumulator")
        splitters = control_bus_splitters(unit)
        gate = next(c for c in unit.findall("comp[@name='OR Gate']")
                    if attributes(c).get("label") == "ACC_MEMORY_REQUEST_SELECT")
        controls = {signal["bit"]: signal["name"] for signal in self.contract["signals"]}
        connected = []
        for terminal, _, incoming, _, _ in state.ports[id(gate)]:
            if incoming:
                connected.append([
                    controls[bit] for splitter in splitters
                    for group, (source, *_) in enumerate(state.ports[id(splitter)][1:])
                    for bit, mapped in enumerate(splitter_groups(splitter)) if mapped == group
                    and state.network.find(source) == state.network.find(terminal)
                ])
        self.assertCountEqual(connected, [["LOAD_ADR"], ["LOAD_ADR_REG"], ["LOAD_REG_OFF"]])

    def test_address_requests_use_their_named_control_bits(self):
        from tiny_cpu_hierarchy import CircuitBits
        definitions = {c.get("name"): c for c in self.project.findall("circuit")}
        unit = definitions["AddressUnit"]
        state = CircuitBits(definitions, unit, "address")
        controls = {signal["bit"]: signal["name"] for signal in self.contract["signals"]}
        expected = {
            "REGISTER_ADDRESS_REQUEST": {"ADDR_REG_ARGUMENT", "STORE_ADR_REG", "LOAD_ADR_REG"},
            "OFFSET_ADDRESS_REQUEST": {"ADDR_REG_OFFS_ARGUMENT", "STORE_REG_OFF", "LOAD_REG_OFF"},
        }
        for label, signals in expected.items():
            gate = next(c for c in unit.findall("comp[@name='OR Gate']")
                        if attributes(c).get("label") == label)
            connected = []
            for terminal, _, incoming, _, _ in state.ports[id(gate)]:
                if incoming:
                    connected.append([
                        controls[bit] for splitter in control_bus_splitters(unit)
                        for group, (source, *_) in enumerate(state.ports[id(splitter)][1:])
                        for bit, mapped in enumerate(splitter_groups(splitter)) if mapped == group
                        and state.network.find(source) == state.network.find(terminal)
                    ])
            with self.subTest(request=label):
                self.assertCountEqual(connected, [[signal] for signal in signals])

    def test_address_register_mux_selects_immediate_or_memory_data(self):
        from tiny_cpu_hierarchy import CircuitBits
        definitions = {c.get("name"): c for c in self.project.findall("circuit")}
        unit = definitions["AddressRegisterLoad"]
        state = CircuitBits(definitions, unit, "address")
        mux, = [c for c in unit.findall("comp[@name='Multiplexer']")
                if any(name == "select" and wire_path_exists(unit, str(p).replace(' ', ''), "(100,220)")
                       for p, *_, name in state.ports[id(c)])]
        ports = {name: terminal for terminal, _, _, _, name in state.ports[id(mux)]}
        pins = {attributes(c).get("label"): state.ports[id(c)][0][0]
                for c in unit.findall("comp[@name='Pin']")}
        for port, source in (("0", "IMMEDIATE"), ("1", "READ_VALUE")):
            with self.subTest(input=port):
                self.assertEqual(state.network.find(ports[port]), state.network.find(pins[source]))
        self.assertEqual(state.network.find(ports["select"]), state.network.find(pins["LOAD_MEMORY"]))

    def test_address_load_boundary_uses_memory_value_and_validity_together(self):
        from tiny_cpu_hierarchy import CircuitBits, point
        definitions = {c.get("name"): c for c in self.project.findall("circuit")}
        unit = definitions["AddressUnit"]
        state = CircuitBits(definitions, unit, "address")
        instance, = unit.findall("comp[@name='AddressRegisterLoad']")
        ports = generated_symbol_ports(definitions["AddressRegisterLoad"], instance)
        pins = {attributes(c)["label"]: c.get("loc") for c in unit.findall("comp[@name='Pin']")}
        for source, target in (("READ_VALUE", "READ_VALUE"), ("READ_VALID", "READ_VALID"),
                               ("IMMEDIATE_VALUE", "IMMEDIATE")):
            self.assertTrue(wire_path_exists(unit, pins[source], ports[target]))
        for bit, target in ((22, "LOAD_CONST"), (23, "LOAD_MEMORY")):
            tap, = [t for t in control_bus_splitters(unit) if splitter_groups(t)[bit] == 0]
            source = state.ports[id(tap)][1][0]
            self.assertEqual(state.network.find(source), state.network.find(point(ports[target])))

    def test_splitter_uses_logisim_defaults_for_omitted_bits(self):
        splitter = ET.fromstring('<comp name="Splitter"><a name="incoming" val="7"/>'
                                '<a name="fanout" val="3"/></comp>')
        self.assertEqual(splitter_groups(splitter), [0, 0, 0, 1, 1, 2, 2])
        ET.SubElement(splitter, "a", {"name": "bit6", "val": "0"})
        self.assertEqual(splitter_groups(splitter), [0, 0, 0, 1, 1, 2, 0])

    def test_splitter_none_leaves_other_control_bits_unmapped(self):
        splitter = ET.fromstring('''<comp name="Splitter">
          <a name="incoming" val="3"/><a name="fanout" val="1"/>
          <a name="bit0" val="none"/><a name="bit2" val="none"/>
        </comp>''')
        self.assertEqual(splitter_groups(splitter), [-1, 0, -1])

    def test_accumulator_tap_cannot_select_the_neighboring_control_bit(self):
        unit = self.project.find("circuit[@name='AccumulatorUnit']")
        tap = next(c for c in control_bus_splitters(unit) if splitter_groups(c)[41] >= 0)
        group = splitter_groups(tap)[41]
        for bit, value in ((41, "none"), (40, str(group))):
            attribute = tap.find(f"a[@name='bit{bit}']")
            if attribute is None:
                attribute = ET.SubElement(tap, 'a', {'name': f'bit{bit}'})
            attribute.set('val', value)
        with self.assertRaisesRegex(ValueError, "bit mapping"):
            verify_core_modularity(self.project, self.contract)

    def test_accumulator_tap_must_reach_the_control_bus(self):
        unit = self.project.find("circuit[@name='AccumulatorUnit']")
        tap = control_bus_splitters(unit)[0]
        for wire in list(unit.findall('wire')):
            if tap.get('loc') in wire.attrib.values():
                unit.remove(wire)
        with self.assertRaisesRegex(ValueError, "disconnected"):
            verify_core_modularity(self.project, self.contract)

    def test_remaining_unit_taps_reject_changed_bit_and_disconnected_bus(self):
        for name in ("MemoryUnit", "ExecutionUnit", "FaultUnit", "BranchUnit", "CoreDiagnostics"):
            for mutation in ("bit mapping", "disconnected"):
                with self.subTest(unit=name, mutation=mutation):
                    project = copy.deepcopy(self.project)
                    unit = project.find(f"circuit[@name='{name}']")
                    tap = control_bus_splitters(unit)[0]
                    if mutation == "bit mapping":
                        selected = splitter_groups(tap).index(0)
                        tap.find(f"a[@name='bit{selected}']").set("val", "none")
                        tap.find(f"a[@name='bit{(selected + 1) % 45}']").set("val", "0")
                    else:
                        for wire in list(unit.findall("wire")):
                            if tap.get("loc") in wire.attrib.values():
                                unit.remove(wire)
                    with self.assertRaisesRegex(ValueError, mutation):
                        verify_core_modularity(project, self.contract)

    def test_decoder_mutations_find_neutral_inputs_without_constant_labels(self):
        decoder = self.project.find("circuit[@name='FetchDecodeControls']")
        for c in decoder.findall("comp[@name='Constant']"):
            for label in c.findall("a[@name='label']"):
                c.remove(label)
        register = gate_input_constant(decoder, "ACC_LOAD_REQUEST", 12)
        store = gate_input_constant(decoder, "ACC_LOAD_REQUEST", 14)
        self.assertIsNot(register, store)
        self.assertEqual(attributes(register)["value"], "0x0")
        self.assertEqual(attributes(store)["value"], "0x0")

    def test_gui_save_defaults_and_xml_order_preserve_topology(self):
        explicit = copy.deepcopy(self.project)
        for circuit in explicit.findall("circuit"):
            components = circuit.findall("comp")
            for comp in components:
                kind, a = comp.get("name"), attributes(comp)
                defaults = {}
                if kind == "Splitter":
                    defaults.update({f"bit{i}": str(g) for i, g in enumerate(splitter_groups(comp))})
                    defaults["label"] = "UNSAVED_SPLITTER_LABEL"
                if kind in {"Constant", "Multiplexer"}:
                    defaults["label"] = "UNSAVED_COMPONENT_LABEL"
                if kind == "Constant":
                    defaults["value"] = "0x1"
                if kind in {"Pin", "Tunnel"}:
                    defaults["width"] = "1"
                if kind.endswith(" Gate") and kind != "NOT Gate":
                    defaults["inputs"] = "2"
                for name, value in defaults.items():
                    if name not in a:
                        ET.SubElement(comp, "a", {"name": name, "val": value})
            for comp in components:
                circuit.remove(comp)
            circuit.extend(reversed(components))
        verify_core_modularity(explicit, self.contract)
        self.assertEqual(core_topology_fingerprint(explicit), self.contract["topology_sha256"])

    def test_gate_caption_font_does_not_change_electrical_topology(self):
        gate = self.project.find("circuit[@name='AddressUnit']/comp[@name='OR Gate']")
        font = gate.find("a[@name='labelfont']")
        if font is None:
            font = ET.SubElement(gate, "a", {"name": "labelfont"})
        font.set("val", "SansSerif plain 24")
        self.assertEqual(core_topology_fingerprint(self.project), self.contract["topology_sha256"])

    def test_sheet_annotations_do_not_change_electrical_topology(self):
        from tiny_cpu_hierarchy import component_ports
        unit = self.project.find("circuit[@name='AccumulatorUnit']")
        note = ET.SubElement(unit, "comp", {"lib": "9", "name": "Text", "loc": "(320,80)"})
        ET.SubElement(note, "a", {"name": "text", "val": "Qualifiers [3:0]"})
        self.assertEqual(component_ports({}, note), [])
        self.assertEqual(core_topology_fingerprint(self.project), self.contract["topology_sha256"])

    def test_named_fault_feedback_and_error_halt_are_separate_nets(self):
        main = self.project.find("circuit[@name='TinyCPUMain']")

        def ports(name):
            return generated_symbol_ports(self.project.find(f"circuit[@name='{name}']"),
                                          main.find(f"comp[@name='{name}']"))

        faults, branch, fetch = ports("FaultUnit"), ports("BranchUnit"), ports("FetchUnit")
        public = {attributes(p)["label"]: p.get("loc") for p in main.findall("comp[@name='Pin']")}
        sources = [faults[n] for n in ("ADDR", "DIV0", "ILL", "INPUT", "INV", "OVF")]
        sources.extend(fetch[name] for name in ("ERROR_HALT", "HALT", "PRINT_ADDR", "PRINT"))
        for name in ("ADDR", "DIV0", "ILL", "INPUT", "INV", "OVF"):
            with self.subTest(signal=name):
                self.assertTrue(wire_path_exists(main, faults[name], branch[name]))
                self.assertTrue(wire_path_exists(main, faults[name], public[f"ERROR_{name}"]))
        self.assertTrue(wire_path_exists(main, fetch["ERROR_HALT"], public["HALTED_WITH_ERROR"]))
        for source, destination in (("HALT", "HALTED"),
                                    ("PRINT_ADDR", "PRINT_ADDRESS_ENABLE"),
                                    ("PRINT", "PRINT_ENABLE")):
            with self.subTest(signal=source):
                self.assertTrue(wire_path_exists(main, fetch[source], public[destination]))
        for index, source in enumerate(sources):
            for other in sources[index + 1:]:
                self.assertFalse(wire_path_exists(main, source, other))

    def test_public_pin_reordering_is_rejected(self):
        main = self.project.find("circuit[@name='TinyCPUMain']")
        clk = next(p for p in main.findall("comp[@name='Pin']") if attributes(p)["label"] == "CLK")
        clk.set("loc", "(60,10000)")
        with self.assertRaisesRegex(ValueError, "public symbol pin order"):
            verify_core_modularity(self.project, self.contract)

    def test_input_only_box_is_anchored_at_its_first_input(self):
        definition = ET.fromstring('<circuit name="Monitor"><comp lib="0" name="Pin" loc="(40,50)">'
                                   '<a name="label" val="VALUE"/></comp></circuit>')
        instance = ET.fromstring('<comp name="Monitor" loc="(100,200)"/>')
        self.assertEqual(generated_symbol_ports(definition, instance), {"VALUE": "(100,200)"})

    def test_custom_symbol_without_a_drawing_is_not_treated_as_an_evolution_box(self):
        definition = ET.fromstring('''<circuit name="Incomplete">
          <a name="appearance" val="custom"/>
          <comp lib="0" name="Pin" loc="(100,100)"><a name="label" val="VALUE"/></comp>
        </circuit>''')
        instance = ET.fromstring('<comp name="Incomplete" loc="(500,200)"/>')
        with self.assertRaisesRegex(ValueError, "no explicit appearance"):
            generated_symbol_ports(definition, instance)

    def test_explicit_symbol_ports_are_independent_of_sheet_pin_order(self):
        definition = ET.fromstring('''<circuit name="Stable">
          <a name="appearance" val="custom"/>
          <appear>
            <circ-port dir="out" pin="100,300" x="270" y="60"/>
            <circ-port dir="out" pin="100,100" x="270" y="80"/>
            <circ-anchor facing="east" x="270" y="60"/>
          </appear>
          <comp lib="0" name="Pin" loc="(100,300)">
            <a name="label" val="A"/><a name="type" val="output"/>
          </comp>
          <comp lib="0" name="Pin" loc="(100,100)">
            <a name="label" val="B"/><a name="type" val="output"/>
          </comp>
        </circuit>''')
        instance = ET.fromstring('<comp name="Stable" loc="(500,200)"/>')
        self.assertEqual(generated_symbol_ports(definition, instance),
                         {"A": "(500,200)", "B": "(500,220)"})
        ET.SubElement(instance, "a", {"name": "facing", "val": "west"})
        self.assertEqual(generated_symbol_ports(definition, instance),
                         {"A": "(500,200)", "B": "(500,180)"})
        definition.find("appear/circ-port").set("pin", "999,999")
        with self.assertRaisesRegex(ValueError, "unknown or duplicate pin"):
            generated_symbol_ports(definition, instance)

    def test_splitter_handedness_matches_native_logisim_endpoints(self):
        from tiny_cpu_hierarchy import component_ports
        for facing, appear, first, last in (
            ("east", "left", (120,50), (120,90)),
            ("east", "right", (120,110), (120,150)),
            ("west", "left", (80,110), (80,150)),
            ("west", "right", (80,50), (80,90)),
        ):
            with self.subTest(facing=facing, appear=appear):
                splitter = ET.fromstring(f'''<comp name="Splitter" loc="(100,100)">
                  <a name="fanout" val="3"/><a name="incoming" val="3"/>
                  <a name="spacing" val="2"/><a name="facing" val="{facing}"/>
                  <a name="appear" val="{appear}"/>
                </comp>''')
                ports = component_ports({}, splitter)
                self.assertEqual((ports[1][0], ports[-1][0]), (first, last))

    def test_fetch_control_merger_faces_its_decoder(self):
        from tiny_cpu_hierarchy import component_ports
        unit = self.project.find("circuit[@name='FetchUnit']")
        splitter = control_bus_splitter(unit)
        self.assertEqual(attributes(splitter)["facing"], "west")
        self.assertEqual(attributes(splitter)["appear"], "right")
        ports = component_ports({}, splitter)
        self.assertTrue(all(p[0] < ports[0][0][0] for p, *_ in ports[1:]))

    def test_functional_unit_pins_have_horizontal_wire_entries(self):
        from tiny_cpu_hierarchy import CORE_UNITS, point
        checked = 0
        for circuit in self.project.findall("circuit"):
            if circuit.get("name") not in CORE_UNITS:
                continue
            for pin in circuit.findall("comp[@name='Pin']"):
                attached = [w for w in circuit.findall("wire")
                            if pin.get("loc") in w.attrib.values()]
                for wire in attached:
                    with self.subTest(circuit=circuit.get("name"), pin=attributes(pin)["label"]):
                        self.assertEqual(point(wire.get("from"))[1], point(wire.get("to"))[1])
                        checked += 1
        self.assertGreater(checked, 0)

    def test_functional_units_have_no_free_wire_tips(self):
        from collections import Counter
        from tiny_cpu_hierarchy import CORE_UNITS, component_ports, location
        definitions = {c.get("name"): c for c in self.project.findall("circuit")}
        for name in CORE_UNITS:
            circuit = definitions[name]
            ports = {location(p) for c in circuit.findall("comp")
                     for p, *_ in component_ports(definitions, c)}
            ends = Counter(p for w in circuit.findall("wire")
                           for p in (w.get("from"), w.get("to")))
            with self.subTest(circuit=name):
                self.assertEqual([p for p, degree in ends.items()
                                  if degree == 1 and p not in ports], [])


if __name__ == "__main__":
    unittest.main()
