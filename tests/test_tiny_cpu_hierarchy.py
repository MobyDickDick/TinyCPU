import json
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tiny_cpu_hierarchy import (
    attributes, core_topology_fingerprint, flatten_core, verify_core_modularity,
    wire_path_exists,
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
        splitter = next(c for c in unit.findall("comp[@name='Splitter']")
                        if attributes(c).get("label") == "CONTROL_BUS_SPLITTER")
        splitter.find("a[@name='bit0']").set("val", "1")
        with self.assertRaisesRegex(ValueError, "bit mapping"):
            verify_core_modularity(self.project, self.contract)

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


if __name__ == "__main__":
    unittest.main()
