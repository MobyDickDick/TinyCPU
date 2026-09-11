import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tiny_cpu_circuit_check import inspect_circuit, inspect_project

ROOT = Path(__file__).resolve().parents[1]


class CircuitCheckTests(unittest.TestCase):
    def test_primary_project_has_no_static_gate_wiring_faults(self):
        self.assertEqual(inspect_project(ROOT / "hardware/logisim/TinyCPU.circ"), [])

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
        self.assertIn("gate outputs share one net: FIRST, SECOND", messages)




if __name__ == "__main__":
    unittest.main()
