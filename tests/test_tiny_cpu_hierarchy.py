import copy
import json
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tiny_cpu_hierarchy import (
    attributes, control_bus_splitter, core_topology_fingerprint, flatten_core, gate_input_constant,
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
        splitter = control_bus_splitter(unit)
        ET.SubElement(splitter, "a", {"name": "bit0", "val": "1"})
        with self.assertRaisesRegex(ValueError, "bit mapping"):
            verify_core_modularity(self.project, self.contract)

    def test_splitter_uses_logisim_defaults_for_omitted_bits(self):
        splitter = ET.fromstring('<comp name="Splitter"><a name="incoming" val="7"/>'
                                '<a name="fanout" val="3"/></comp>')
        self.assertEqual(splitter_groups(splitter), [0, 0, 0, 1, 1, 2, 2])
        ET.SubElement(splitter, "a", {"name": "bit6", "val": "0"})
        self.assertEqual(splitter_groups(splitter), [0, 0, 0, 1, 1, 2, 0])

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
