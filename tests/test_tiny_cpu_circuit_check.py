import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tiny_cpu_circuit_check import inspect_circuit, inspect_project, repair_project
from tiny_cpu_wire_contacts import inspect_circuit as inspect_wire_contacts
from tiny_cpu_wire_contacts import inspect_routing_grid
from tiny_cpu_hierarchy import CORE_UNITS

ROOT = Path(__file__).resolve().parents[1]


def _attributes(component):
    return {item.get("name"): item.get("val") for item in component.findall("a")}


def _labelled(circuit, label):
    return next(component for component in circuit.findall("comp")
                if _attributes(component).get("label") == label)


class CircuitCheckTests(unittest.TestCase):
    def test_long_horizontal_input_to_an_offset_fbox_terminal_is_connected(self):
        definition = ET.fromstring('''<circuit name="Box">
          <comp lib="0" name="Pin" loc="(100,100)">
            <a name="label" val="DATA"/><a name="width" val="16"/>
          </comp>
          <comp lib="0" name="Pin" loc="(500,100)">
            <a name="label" val="RESULT"/><a name="width" val="16"/>
            <a name="type" val="output"/>
          </comp>
        </circuit>''')
        circuit = ET.fromstring('''<circuit name="DirectInput">
          <comp lib="0" name="Pin" loc="(100,100)">
            <a name="label" val="VALUE"/><a name="width" val="16"/>
          </comp>
          <comp name="Box" loc="(800,100)"/>
          <wire from="(100,100)" to="(580,100)"/>
        </circuit>''')
        self.assertEqual(inspect_circuit(circuit, {"Box": definition}), [])

    def test_grouped_routing_grid_accepts_four_tracks_and_a_three_row_gap(self):
        circuit = ET.Element("circuit", {"name": "Grouped"})
        for x in (20, 40, 60, 80, 120, 140, 160, 180):
            ET.SubElement(circuit, "wire", {"from": f"({x},0)", "to": f"({x},400)"})
        self.assertEqual(inspect_routing_grid(circuit), [])
        ET.SubElement(circuit, "wire", {"from": "(100,0)", "to": "(100,400)"})
        self.assertEqual(len(inspect_routing_grid(circuit)), 1)

    def test_grouped_routing_grid_merges_segments_and_allows_short_port_escapes(self):
        circuit = ET.fromstring('''<circuit name="SplitRun">
          <wire from="(0,30)" to="(100,30)"/>
          <wire from="(100,30)" to="(200,30)"/>
          <wire from="(0,50)" to="(120,50)"/>
        </circuit>''')
        issues = inspect_routing_grid(circuit)
        self.assertEqual(len(issues), 1)
        self.assertIn("horizontal run at 30", issues[0])

    def test_all_functional_units_use_the_grouped_routing_grid(self):
        project = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        for circuit in project.findall("circuit"):
            if circuit.get("name") in CORE_UNITS:
                with self.subTest(circuit=circuit.get("name")):
                    self.assertEqual(inspect_routing_grid(circuit), [])

    def test_splitter_branch_requires_a_physically_connected_bus_source(self):
        circuit = ET.fromstring('''<circuit name="Control">
          <comp lib="0" loc="(1300,200)" name="Pin">
            <a name="label" val="CONTROL"/><a name="width" val="2"/>
          </comp>
          <comp lib="0" loc="(1400,200)" name="Splitter"/>
          <comp lib="1" loc="(700,400)" name="OR Gate"/>
          <wire from="(1300,200)" to="(1400,200)"/>
          <wire from="(1420,180)" to="(1500,180)"/>
          <wire from="(1500,180)" to="(1500,380)"/>
          <wire from="(650,380)" to="(1500,380)"/>
        </circuit>''')
        self.assertEqual(inspect_circuit(circuit), [])
        bus_wire = circuit.find("wire[@from='(1300,200)']")
        circuit.remove(bus_wire)
        self.assertTrue(any("undriven wire" in issue.message
                            for issue in inspect_circuit(circuit)))

    def test_tunnels_are_rejected_by_the_static_checker(self):
        circuit = ET.fromstring('''<circuit name="Hidden">
          <comp lib="0" loc="(100,100)" name="Tunnel"/>
        </circuit>''')
        self.assertEqual([issue.message for issue in inspect_circuit(circuit)], [
            "Tunnel components are forbidden; use visible orthogonal wires",
        ])

    def test_all_project_sheets_are_tunnel_free_with_explicit_unit_junctions(self):
        for project in sorted((ROOT / "hardware/logisim").rglob("*.circ")):
            for circuit in ET.parse(project).getroot().findall("circuit"):
                with self.subTest(project=project.name, circuit=circuit.get("name")):
                    self.assertEqual(circuit.findall("comp[@name='Tunnel']"), [])
                    if circuit.get("name") in CORE_UNITS:
                        self.assertEqual(inspect_wire_contacts(circuit), [])

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

    def test_integrated_fetch_decoder_has_no_implicit_wire_contacts(self):
        """Keep interrupt feedback away from the live PC feedback net."""
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        fetch = root.find("circuit[@name='FetchDecode']")
        self.assertIsNotNone(fetch)
        self.assertEqual(inspect_wire_contacts(fetch), [])

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
            if circuit.get("name") not in CORE_UNITS
            for component in circuit.findall("comp")
        ))
        self.assertGreater(len(decoder.findall("wire")), 0)

        main = next(
            circuit for circuit in root.findall("circuit")
            if circuit.get("name") == "TinyCPUMain"
        )
        definitions = {circuit.get("name"): circuit
                       for circuit in root.findall("circuit")}
        self.assertEqual(inspect_circuit(main, definitions), [])

    def test_memory_write_or_third_input_is_driven_by_store_reg_offset(self):
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        main = next(circuit for circuit in root.findall("circuit")
                    if circuit.get("name") == "MemoryUnit")
        definitions = {circuit.get("name"): circuit
                       for circuit in root.findall("circuit")}
        self.assertEqual(inspect_circuit(main, definitions), [])
        gate = _labelled(main, "MEMORY_WRITE_REQUEST")
        self.assertEqual(_attributes(gate).get("inputs"), "3")

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

    def test_detects_multiplexer_output_joined_to_subcircuit_output(self):
        producer = ET.fromstring("""
          <circuit name="Producer">
            <comp lib="0" loc="(100,100)" name="Pin">
              <a name="label" val="VALID"/><a name="type" val="output"/>
            </comp>
          </circuit>
        """)
        circuit = ET.fromstring("""
          <circuit name="Broken">
            <comp loc="(200,100)" name="Producer"><a name="label" val="SOURCE"/></comp>
            <comp lib="2" loc="(100,200)" name="Multiplexer">
              <a name="label" val="SELECTED_VALID"/>
            </comp>
            <wire from="(200,100)" to="(300,100)"/>
            <wire from="(100,200)" to="(300,200)"/>
            <wire from="(300,100)" to="(300,200)"/>
          </circuit>
        """)
        messages = [issue.message for issue in inspect_circuit(
            circuit, {"Producer": producer}
        )]
        self.assertIn(
            "outputs share one net: SELECTED_VALID, VALID of SOURCE",
            messages,
        )

    def test_detects_dangling_subcircuit_output_wire(self):
        producer = ET.fromstring("""
          <circuit name="Producer">
            <comp lib="0" loc="(100,100)" name="Pin">
              <a name="label" val="RESULT"/><a name="type" val="output"/>
            </comp>
          </circuit>
        """)
        circuit = ET.fromstring("""
          <circuit name="Broken">
            <comp loc="(200,100)" name="Producer"><a name="label" val="ALU"/></comp>
            <wire from="(200,100)" to="(300,100)"/>
          </circuit>
        """)
        messages = [issue.message for issue in inspect_circuit(
            circuit, {"Producer": producer}
        )]
        self.assertEqual(
            messages,
            ["RESULT of ALU has a dangling output wire ending at (300, 100)"],
        )

    def test_detects_abandoned_bus_input_stub(self):
        circuit = ET.fromstring("""
          <circuit name="Broken">
            <comp lib="0" loc="(100,100)" name="Pin">
              <a name="label" val="OFFSET_ADDR"/><a name="width" val="16"/>
            </comp>
            <comp lib="0" loc="(400,300)" name="Constant">
              <a name="width" val="16"/>
            </comp>
            <wire from="(100,100)" to="(250,100)"/>
          </circuit>
        """)
        messages = [issue.message for issue in inspect_circuit(circuit)]
        self.assertEqual(messages, [
            "OFFSET_ADDR has a dangling input wire ending at (250, 100)"
        ])

    def test_detects_unconnected_bus_input_pin(self):
        circuit = ET.fromstring("""
          <circuit name="Broken">
            <comp lib="0" loc="(100,100)" name="Pin">
              <a name="label" val="OFFSET_ADDR"/><a name="width" val="16"/>
            </comp>
          </circuit>
        """)
        messages = [issue.message for issue in inspect_circuit(circuit)]
        self.assertEqual(messages, [
            "OFFSET_ADDR is an unconnected input pin"
        ])

    def test_accepts_bus_input_wire_ending_at_nearby_component_contact(self):
        circuit = ET.fromstring("""
          <circuit name="Connected">
            <comp lib="0" loc="(100,100)" name="Pin">
              <a name="label" val="VALUE"/><a name="width" val="16"/>
            </comp>
            <comp lib="3" loc="(300,100)" name="Comparator">
              <a name="width" val="16"/>
            </comp>
            <wire from="(100,100)" to="(250,100)"/>
          </circuit>
        """)
        self.assertEqual(inspect_circuit(circuit), [])

    def test_accepts_subcircuit_output_wire_continued_at_a_bend(self):
        producer = ET.fromstring("""
          <circuit name="Producer">
            <comp lib="0" loc="(100,100)" name="Pin">
              <a name="label" val="RESULT"/><a name="type" val="output"/>
            </comp>
          </circuit>
        """)
        circuit = ET.fromstring("""
          <circuit name="Connected">
            <comp loc="(200,100)" name="Producer"/>
            <comp lib="0" loc="(300,200)" name="Pin">
              <a name="label" val="RESULT_OUT"/><a name="type" val="output"/>
            </comp>
            <wire from="(200,100)" to="(300,100)"/>
            <wire from="(300,100)" to="(300,200)"/>
          </circuit>
        """)
        self.assertEqual(inspect_circuit(circuit, {"Producer": producer}), [])

    def test_detects_16_bit_bus_connected_to_one_bit_output(self):
        producer = ET.fromstring("""
          <circuit name="Producer">
            <comp lib="0" loc="(100,100)" name="Pin">
              <a name="label" val="DATA"/><a name="type" val="output"/>
              <a name="width" val="16"/>
            </comp>
          </circuit>
        """)
        circuit = ET.fromstring("""
          <circuit name="Broken">
            <comp loc="(200,100)" name="Producer"><a name="label" val="SOURCE"/></comp>
            <comp lib="0" loc="(400,100)" name="Pin">
              <a name="label" val="VALID"/><a name="type" val="output"/>
            </comp>
            <wire from="(200,100)" to="(400,100)"/>
          </circuit>
        """)
        messages = [issue.message for issue in inspect_circuit(
            circuit, {"Producer": producer}
        )]
        self.assertIn(
            "incompatible widths share one net: DATA of SOURCE (16-bit), VALID (1-bit)",
            messages,
        )

    def test_accepts_matching_bus_widths(self):
        circuit = ET.fromstring("""
          <circuit name="Connected">
            <comp lib="0" loc="(100,100)" name="Pin">
              <a name="label" val="INPUT"/><a name="width" val="16"/>
            </comp>
            <comp lib="0" loc="(300,100)" name="Pin">
              <a name="label" val="OUTPUT"/><a name="type" val="output"/>
              <a name="width" val="16"/>
            </comp>
            <wire from="(100,100)" to="(300,100)"/>
          </circuit>
        """)
        self.assertEqual(inspect_circuit(circuit), [])

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

    def test_public_input_drives_gate_and_distant_multiplexer_fanout(self):
        circuit = ET.fromstring("""
          <circuit name="Fanout">
            <comp lib="0" loc="(100,100)" name="Pin"/>
            <comp lib="1" loc="(200,120)" name="AND Gate"/>
            <comp lib="2" loc="(800,180)" name="Multiplexer"/>
            <wire from="(100,100)" to="(150,100)"/>
            <wire from="(150,100)" to="(700,100)"/>
            <wire from="(700,100)" to="(700,170)"/>
            <wire from="(700,170)" to="(770,170)"/>
            <wire from="(700,190)" to="(770,190)"/>
          </circuit>
        """)
        self.assertEqual(inspect_circuit(circuit), [])
        circuit.remove(circuit.find("comp[@name='Pin']"))
        self.assertTrue(any("undriven wire" in issue.message
                            for issue in inspect_circuit(circuit)))

    def test_even_input_gate_uses_grid_aligned_terminals(self):
        circuit = ET.fromstring("""
          <circuit name="Connected">
            <comp lib="1" loc="(200,120)" name="AND Gate">
              <a name="inputs" val="4"/><a name="label" val="COMPACT"/>
              <a name="size" val="30"/>
            </comp>
            <comp lib="0" loc="(100,100)" name="Constant"/>
            <wire from="(100,100)" to="(170,100)"/>
            <comp lib="0" loc="(100,110)" name="Constant"/>
            <wire from="(100,110)" to="(170,110)"/>
            <comp lib="0" loc="(100,130)" name="Constant"/>
            <wire from="(100,130)" to="(170,130)"/>
            <comp lib="0" loc="(100,140)" name="Constant"/>
            <wire from="(100,140)" to="(170,140)"/>
          </circuit>
        """)
        self.assertEqual(inspect_circuit(circuit), [])

    def test_negated_gate_input_accounts_for_inverter_bubble(self):
        circuit = ET.fromstring("""
          <circuit name="Connected">
            <comp lib="1" loc="(200,120)" name="AND Gate">
              <a name="inputs" val="4"/><a name="label" val="COMPACT"/>
              <a name="negate3" val="true"/><a name="size" val="30"/>
            </comp>
            <comp lib="0" loc="(100,140)" name="Constant"/>
            <wire from="(100,140)" to="(160,140)"/>
          </circuit>
        """)
        self.assertEqual(inspect_circuit(circuit), [])

    def test_detects_wire_stopping_before_multiplexer_contacts(self):
        circuit = ET.fromstring("""
          <circuit name="Broken">
            <comp lib="2" loc="(200,120)" name="Multiplexer">
              <a name="label" val="MEMORY_SELECT"/>
            </comp>
            <wire from="(100,110)" to="(160,110)"/>
            <wire from="(100,130)" to="(160,130)"/>
          </circuit>
        """)
        messages = [issue.message for issue in inspect_circuit(circuit)]
        self.assertEqual(messages, [
            "MEMORY_SELECT input at (170, 110) is not wired",
            "MEMORY_SELECT input at (170, 130) is not wired",
        ])

    def test_accepts_wires_at_classic_multiplexer_contacts(self):
        circuit = ET.fromstring("""
          <circuit name="Connected">
            <comp lib="2" loc="(200,120)" name="Multiplexer"/>
            <wire from="(100,110)" to="(170,110)"/>
            <wire from="(100,130)" to="(170,130)"/>
          </circuit>
        """)
        self.assertEqual(inspect_circuit(circuit), [])

    def test_main_external_memory_multiplexers_reach_their_contacts(self):
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        main = next(circuit for circuit in root.findall("circuit")
                    if circuit.get("name") == "MemoryUnit")
        definitions = {circuit.get("name"): circuit
                       for circuit in root.findall("circuit")}
        self.assertEqual(inspect_circuit(main, definitions), [])
        selectors = [component for component in main.findall("comp")
                     if component.get("name") == "Multiplexer"]
        self.assertGreaterEqual(len(selectors), 2)

    def test_main_has_no_abandoned_memory_control_branches(self):
        """Audit the main sheet electrically instead of naming old segments."""
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        main = root.find("circuit[@name='TinyCPUMain']")
        definitions = {circuit.get("name"): circuit
                       for circuit in root.findall("circuit")}
        self.assertIsNotNone(main)
        self.assertEqual(inspect_circuit(main, definitions), [])

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
              <comp lib="0" loc="(200,100)" name="Pin">
                <a name="label" val="LEFT_OUT"/><a name="type" val="output"/>
              </comp>
              <comp lib="0" loc="(300,140)" name="Pin">
                <a name="label" val="RIGHT_OUT"/><a name="type" val="output"/>
              </comp>
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

    def test_pruning_rechecks_topology_until_a_marked_branch_is_gone(self):
        project = """<?xml version='1.0'?>
          <project><circuit name="Top">
            <wire from="(100,100)" to="(200,100)"/>
            <wire from="(200,100)" to="(300,100)"/>
            <wire from="(200,100)" to="(200,160)" tinycpu-dangling="true"/>
            <wire from="(200,160)" to="(260,160)" tinycpu-dangling="true"/>
          </circuit></project>"""
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "multi-segment-stub.circ"
            path.write_text(project)
            self.assertEqual(repair_project(path, prune_dangling=True), [])
            wires = ET.parse(path).getroot().findall("circuit/wire")
            self.assertEqual(
                {(wire.get("from"), wire.get("to")) for wire in wires},
                {("(100,100)", "(200,100)"),
                 ("(200,100)", "(300,100)")},
            )

    def test_pruning_rechecks_a_junction_with_multiple_marked_leaves(self):
        project = """<?xml version='1.0'?>
          <project><circuit name="Top">
            <wire from="(100,100)" to="(200,100)"/>
            <wire from="(200,100)" to="(300,100)"/>
            <wire from="(200,100)" to="(200,40)" tinycpu-dangling="true"/>
            <wire from="(200,100)" to="(200,160)" tinycpu-dangling="true"/>
          </circuit></project>"""
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "two-stubs.circ"
            path.write_text(project)
            self.assertEqual(repair_project(path, prune_dangling=True), [])
            wires = ET.parse(path).getroot().findall("circuit/wire")
            self.assertEqual(len(wires), 2)




if __name__ == "__main__":
    unittest.main()
