import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tiny_cpu_circuit_check import inspect_circuit, inspect_project, repair_project

ROOT = Path(__file__).resolve().parents[1]


class CircuitCheckTests(unittest.TestCase):
    def test_profile_projects_have_no_static_gate_wiring_faults(self):
        for project in ("TinyCPU.circ", "TinyCPU-8-8.circ"):
            with self.subTest(project=project):
                self.assertEqual(
                    inspect_project(ROOT / "hardware/logisim" / project), []
                )

    def test_8_bit_top_level_uses_visible_wires_instead_of_tunnels(self):
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU-8-8.circ").getroot()
        main = next(
            circuit for circuit in root.findall("circuit")
            if circuit.get("name") == "TinyCPUMain"
        )
        tunnels = [
            component for component in main.findall("comp")
            if component.get("name") == "Tunnel"
        ]

        self.assertEqual(tunnels, [])

    def test_main_fetch_decoder_uses_visible_wires(self):
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        decoder = next(
            circuit for circuit in root.findall("circuit")
            if circuit.get("name") == "FetchDecodeControls"
        )

        self.assertFalse(any(
            component.get("name") == "Tunnel"
            for component in decoder.findall("comp")
        ))
        self.assertGreater(len(decoder.findall("wire")), 0)

    def test_standalone_fetch_decoder_uses_visible_wires(self):
        path = (
            ROOT / "hardware/logisim/diagnostics"
            / "TinyCPU-FetchDecodeControls.circ"
        )
        root = ET.parse(path).getroot()
        decoder = next(
            circuit for circuit in root.findall("circuit")
            if circuit.get("name") == "FetchDecodeControls"
        )

        self.assertFalse(any(
            component.get("name") == "Tunnel"
            for component in decoder.findall("comp")
        ))
        self.assertGreater(len(decoder.findall("wire")), 0)

    def test_detects_outputs_joined_through_endpoint_on_segment(self):
        circuit = ET.fromstring("""
          <circuit name="Broken">
            <comp lib="1" loc="(100,100)" name="OR Gate"><a name="label" val="FIRST"/></comp>
            <comp lib="1" loc="(200,100)" name="OR Gate"><a name="label" val="SECOND"/></comp>
            <wire from="(50,90)" to="(100,90)"/><wire from="(50,110)" to="(100,110)"/>
            <wire from="(150,90)" to="(200,90)"/><wire from="(150,110)" to="(200,110)"/>
            <wire from="(100,100)" to="(250,100)"/><wire from="(200,100)" to="(200,120)"/>
          </circuit>
        """)
        messages = [issue.message for issue in inspect_circuit(circuit)]
        self.assertIn("outputs share one net: FIRST, SECOND", messages)

    def test_detects_and_repairs_subcircuit_output_bridge(self):
        project = """<?xml version='1.0'?>
          <project>
            <circuit name="Producer">
              <comp lib="0" loc="(100,100)" name="Pin">
                <a name="label" val="VALUE"/><a name="type" val="output"/>
              </comp>
            </circuit>
            <circuit name="Top">
              <comp loc="(100,100)" name="Producer"><a name="label" val="LEFT"/></comp>
              <comp loc="(300,100)" name="Producer"><a name="label" val="RIGHT"/></comp>
              <wire from="(100,100)" to="(200,100)"/>
              <wire from="(300,100)" to="(300,140)"/>
              <wire from="(200,100)" to="(300,100)"/>
            </circuit>
          </project>"""
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.circ"
            path.write_text(project)
            messages = [str(issue) for issue in inspect_project(path)]
            self.assertEqual(messages, [
                "Top: outputs share one net: VALUE of LEFT, VALUE of RIGHT"
            ])
            self.assertEqual(repair_project(path), [])
            top = next(c for c in ET.parse(path).getroot().findall("circuit")
                       if c.get("name") == "Top")
            wires = {(w.get("from"), w.get("to")) for w in top.findall("wire")}
            self.assertNotIn((("(200,100)"), ("(300,100)")), wires)




if __name__ == "__main__":
    unittest.main()
