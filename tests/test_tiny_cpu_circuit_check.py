import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tiny_cpu_circuit_check import inspect_circuit, inspect_project, repair_project
from tiny_cpu_wire_contacts import inspect_circuit as inspect_wire_contacts

ROOT = Path(__file__).resolve().parents[1]


class CircuitCheckTests(unittest.TestCase):
    def test_wire_contact_audit_finds_t_junction_and_overlap(self):
        circuit = ET.fromstring("""
          <circuit name="Crowded">
            <wire from="(0,20)" to="(100,20)"/>
            <wire from="(50,0)" to="(50,20)"/>
            <wire from="(80,20)" to="(120,20)"/>
          </circuit>
        """)
        issues = inspect_wire_contacts(circuit)
        self.assertEqual(
            [(issue.kind, issue.at) for issue in issues],
            [("endpoint-on-wire junction", "(50, 20)"),
             ("collinear overlap", "(80, 20)..(100, 20)")],
        )

    def test_wire_contact_audit_ignores_nonconnecting_crossing(self):
        circuit = ET.fromstring("""
          <circuit name="Crossing">
            <wire from="(0,20)" to="(100,20)"/>
            <wire from="(50,0)" to="(50,40)"/>
          </circuit>
        """)
        self.assertEqual(inspect_wire_contacts(circuit), [])

    def test_all_projects_have_no_static_gate_wiring_faults(self):
        projects = sorted((ROOT / "hardware/logisim").rglob("*.circ"))
        self.assertGreater(len(projects), 1)
        for project in projects:
            with self.subTest(project=project.relative_to(ROOT)):
                self.assertEqual(inspect_project(project), [])

    def test_diagnostic_sheets_belong_to_the_integrated_cpu(self):
        integrated = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        integrated_names = {
            circuit.get("name") for circuit in integrated.findall("circuit")
        }

        diagnostics = ROOT / "hardware/logisim/diagnostics"
        for project in sorted(diagnostics.glob("*.circ")):
            with self.subTest(project=project.relative_to(ROOT)):
                circuits = ET.parse(project).getroot().findall("circuit")
                self.assertEqual(len(circuits), 1)
                self.assertIn(circuits[0].get("name"), integrated_names)


    def test_main_fetch_decoder_uses_one_shared_decoder_net(self):
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        decoder = next(
            circuit for circuit in root.findall("circuit")
            if circuit.get("name") == "FetchDecodeControls"
        )

        components = decoder.findall("comp")
        self.assertEqual(
            sum(component.get("name") == "Decoder" for component in components),
            1,
        )
        self.assertFalse(any(
            component.get("name") == "Tunnel"
            for circuit in root.findall("circuit")
            for component in circuit.findall("comp")
        ))
        self.assertGreater(len(decoder.findall("wire")), 0)

    def test_memory_write_or_third_input_is_driven_by_store_reg_offset(self):
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        main = next(circuit for circuit in root.findall("circuit")
                    if circuit.get("name") == "TinyCPUMain")
        wires = {(wire.get("from"), wire.get("to"))
                 for wire in main.findall("wire")}
        self.assertIn((("(1400,1600)"), ("(1710,1600)")), wires)
        self.assertIn((("(1710,190)"), ("(1710,1600)")), wires)
        self.assertNotIn((("(1710,190)"), ("(1710,1680)")), wires)

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

    def test_fetch_decoder_outputs_have_short_explanations(self):
        projects = (
            ROOT / "hardware/logisim/TinyCPU.circ",
            ROOT / "hardware/logisim/diagnostics/TinyCPU-FetchDecodeControls.circ",
        )
        for project in projects:
            with self.subTest(project=project.name):
                root = ET.parse(project).getroot()
                decoder = next(
                    circuit for circuit in root.findall("circuit")
                    if circuit.get("name") == "FetchDecodeControls"
                )
                output_labels = {
                    attribute.get("val")
                    for component in decoder.findall("comp")
                    if component.get("name") == "Pin"
                    and any(
                        attribute.get("name") == "type"
                        and attribute.get("val") == "output"
                        for attribute in component.findall("a")
                    )
                    for attribute in component.findall("a")
                    if attribute.get("name") == "label"
                }
                explained_labels = {
                    attribute.get("val").split(":", 1)[0]
                    for component in decoder.findall("comp")
                    if component.get("name") == "Text"
                    for attribute in component.findall("a")
                    if attribute.get("name") == "text" and ":" in attribute.get("val", "")
                }
                self.assertEqual(output_labels, explained_labels)

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

    def test_detects_undriven_gate_input_with_dangling_wire(self):
        circuit = ET.fromstring("""
          <circuit name="Broken">
            <comp lib="1" loc="(200,120)" name="OR Gate">
              <a name="inputs" val="3"/><a name="label" val="WRITE_REQUEST"/>
            </comp>
            <wire from="(150,100)" to="(700,100)"/>
            <wire from="(700,100)" to="(700,180)"/>
          </circuit>
        """)
        messages = [issue.message for issue in inspect_circuit(circuit)]
        self.assertEqual(messages, [
            "WRITE_REQUEST input at (150, 100) has an undriven wire ending at (700, 180)"
        ])

    def test_compact_gate_uses_its_declared_terminal_spacing(self):
        circuit = ET.fromstring("""
          <circuit name="Compact">
            <comp lib="1" loc="(200,120)" name="AND Gate">
              <a name="inputs" val="3"/><a name="label" val="COMPACT"/>
              <a name="size" val="30"/>
            </comp>
            <wire from="(170,110)" to="(700,110)"/>
            <wire from="(700,110)" to="(700,180)"/>
          </circuit>
        """)
        messages = [issue.message for issue in inspect_circuit(circuit)]
        self.assertEqual(messages, [
            "COMPACT input at (170, 110) has an undriven wire ending at (700, 180)"
        ])

    def test_detects_wire_stopping_before_multiplexer_terminals(self):
        circuit = ET.fromstring("""
          <circuit name="Broken">
            <comp lib="2" loc="(200,120)" name="Multiplexer">
              <a name="label" val="MEMORY_SELECT"/>
            </comp>
            <wire from="(100,100)" to="(160,100)"/>
            <wire from="(100,140)" to="(160,140)"/>
          </circuit>
        """)
        messages = [issue.message for issue in inspect_circuit(circuit)]
        self.assertEqual(messages, [
            "MEMORY_SELECT input at (170, 110) is not wired",
            "MEMORY_SELECT input at (170, 130) is not wired",
        ])

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

    def test_prunes_only_verified_and_explicitly_marked_dangling_branch(self):
        project = """<?xml version='1.0'?>
          <project><circuit name="Top">
            <wire from="(100,100)" to="(200,100)"/>
            <wire from="(200,100)" to="(300,100)"/>
            <wire from="(200,100)" to="(200,160)" tinycpu-dangling="true"/>
          </circuit></project>"""
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stub.circ"
            path.write_text(project)
            self.assertEqual(repair_project(path, prune_dangling=True), [])
            wires = ET.parse(path).getroot().findall("circuit/wire")
            self.assertEqual(
                {(wire.get("from"), wire.get("to")) for wire in wires},
                {(("(100,100)"), ("(200,100)")),
                 (("(200,100)"), ("(300,100)"))},
            )

    def test_does_not_prune_unverified_marked_wire(self):
        project = """<?xml version='1.0'?>
          <project><circuit name="Top">
            <wire from="(100,100)" to="(200,100)"/>
            <wire from="(200,100)" to="(200,160)" tinycpu-dangling="true"/>
          </circuit></project>"""
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "not-a-proven-stub.circ"
            path.write_text(project)
            repair_project(path, prune_dangling=True)
            self.assertEqual(
                len(ET.parse(path).getroot().findall("circuit/wire")), 2
            )




if __name__ == "__main__":
    unittest.main()
