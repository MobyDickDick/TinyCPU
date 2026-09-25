import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tiny_cpu_logisim import (
    ROOT,
    LogisimError,
    _expected_edges,
    _expected_halt_output,
    _matrix_program,
    autonomous_project,
    parse_args,
    resolve_jar,
    run_core_acceptance,
    run_matrix,
    run_trace,
)
from tiny_cpu_profiles import load_profile


def _attributes(component):
    return {
        attribute.get("name"): attribute.get("val")
        for attribute in component.findall("a")
    }


def _component_by_label(circuit, label):
    matches = [
        component for component in circuit.findall("comp")
        if _attributes(component).get("label") == label
    ]
    if len(matches) != 1:
        raise AssertionError(f"expected exactly one component labelled {label!r}")
    return matches[0]


def _wire_path_exists(circuit, start, end):
    graph = {}
    for wire in circuit.findall("wire"):
        left, right = wire.get("from"), wire.get("to")
        graph.setdefault(left, set()).add(right)
        graph.setdefault(right, set()).add(left)
    pending, visited = [start], set()
    while pending:
        point = pending.pop()
        if point == end:
            return True
        if point not in visited:
            visited.add(point)
            pending.extend(graph.get(point, ()))
    return False


def _point_offset(component, x=0, y=0):
    """Return a component connection point relative to its labelled location."""
    component_x, component_y = map(
        int, component.get("loc").strip("()").split(",")
    )
    return f"({component_x + x},{component_y + y})"


def _pin_location(circuit, label):
    return _component_by_label(circuit, label).get("loc")


class LogisimLauncherTests(unittest.TestCase):

    def test_interrupt_feedback_inputs_remain_connected_after_layout_edits(self):
        """Guard electrical paths without freezing their drawing coordinates."""
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        main = root.find("circuit[@name='TinyCPUMain']")
        self.assertIsNotNone(main)
        self.assertTrue(
            _wire_path_exists(
                main, _pin_location(main, "INTERRUPT_ACCEPT"), "(810,460)"
            )
        )
        self.assertTrue(
            _wire_path_exists(
                main, _pin_location(main, "INTERRUPT_TARGET_PC"), "(810,480)"
            )
        )
        illegal_return_or = _component_by_label(main, "ILLEGAL_RETURN_OR")
        # The default Logisim-evolution gate size is 50 pixels.  Its contacts
        # are therefore 50 pixels left of the output location; wires ending at
        # x - 30 only appear to touch the body of the symbol.
        upper_input = _point_offset(illegal_return_or, x=-50, y=-10)
        lower_input = _point_offset(illegal_return_or, x=-50, y=10)
        self.assertTrue(
            _wire_path_exists(main, _pin_location(main, "ILL_RET"), upper_input)
        )
        self.assertTrue(_wire_path_exists(main, "(1400,1750)", lower_input))
        self.assertTrue(
            _wire_path_exists(main, illegal_return_or.get("loc"), "(2400,570)")
        )

    def test_interrupt_pc_override_preserves_sequential_pc_when_inactive(self):
        """Select zero must keep the normal next-PC path, not the IRQ target."""
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        fetch = root.find("circuit[@name='FetchDecode']")
        self.assertIsNotNone(fetch)
        override = _component_by_label(fetch, "INTERRUPT_PC_OVERRIDE")
        # A classic two-input mux selects its lower data contact for select 0.
        default_input = _point_offset(override, x=-30, y=10)
        interrupt_input = _point_offset(override, x=-30, y=-10)
        self.assertTrue(_wire_path_exists(fetch, "(870,240)", default_input))
        self.assertTrue(
            _wire_path_exists(
                fetch,
                _pin_location(fetch, "INTERRUPT_TARGET_PC"),
                interrupt_input,
            )
        )
        self.assertFalse(
            _wire_path_exists(
                fetch,
                _pin_location(fetch, "INTERRUPT_TARGET_PC"),
                default_input,
            )
        )

    def test_recovery_topology_regressions_reject_named_port_mutations(self):
        """Prove AP 20 repairs are guarded independently of canvas layout."""
        source = ROOT / "hardware/logisim/TinyCPU.circ"

        def disconnect(tree, circuit_name, point):
            circuit = next(
                candidate for candidate in tree.getroot().findall("circuit")
                if candidate.get("name") == circuit_name
            )
            wires = [
                wire for wire in circuit.findall("wire")
                if point in (wire.get("from"), wire.get("to"))
            ]
            self.assertTrue(
                wires,
                f"mutation point {circuit_name}.{point} is not connected",
            )
            for wire in wires:
                circuit.remove(wire)

        def reserved_opcode_point(tree):
            controls = next(
                candidate for candidate in tree.getroot().findall("circuit")
                if candidate.get("name") == "FetchDecodeControls"
            )
            decoder = next(
                component for component in controls.findall("comp")
                if component.get("name") == "Decoder"
            )
            decoder_x, decoder_y = map(
                int, decoder.get("loc").strip("()").split(",")
            )
            return f"({decoder_x + 20},{decoder_y - 640 + 0x3f * 10})"

        mutations = (
            (
                "normal halt export",
                "TinyCPUMain",
                lambda tree: "(1400,1830)",
                self.test_halt_control_reaches_public_halted_pin,
            ),
            (
                "error halt export",
                "TinyCPUMain",
                lambda tree: "(1400,1850)",
                self.test_halt_error_control_reaches_public_halted_with_error_pin,
            ),
            (
                "jump control alignment",
                "TinyCPUMain",
                lambda tree: "(1400,1330)",
                self.test_jump_wiring_is_encapsulated_without_tunnels,
            ),
            (
                "zero jump polarity",
                "JumpBox",
                lambda tree: _pin_location(
                    next(
                        circuit for circuit in tree.getroot().findall("circuit")
                        if circuit.get("name") == "JumpBox"
                    ),
                    "JUMP_ZERO",
                ),
                self.test_jump_box_gates_zero_conditions_with_the_matching_controls,
            ),
            (
                "error jump polarity",
                "JumpBox",
                lambda tree: _pin_location(
                    next(
                        circuit for circuit in tree.getroot().findall("circuit")
                        if circuit.get("name") == "JumpBox"
                    ),
                    "JUMP_ERROR",
                ),
                self.test_jump_box_gates_error_conditions_with_the_matching_controls,
            ),
            (
                "reserved opcode error halt",
                "FetchDecodeControls",
                reserved_opcode_point,
                self.test_reserved_opcode_3f_sets_illegal_and_halts_with_error,
            ),
            (
                "memory write gate input",
                "TinyCPUMain",
                lambda tree: "(530,600)",
                self.test_visible_top_level_memory_or_gate_has_every_input_connected,
            ),
        )

        for name, circuit_name, point_for, regression in mutations:
            with self.subTest(mutation=name), tempfile.TemporaryDirectory() as directory:
                temporary_root = Path(directory)
                target = temporary_root / "hardware/logisim/TinyCPU.circ"
                target.parent.mkdir(parents=True)
                tree = ET.parse(source)
                disconnect(tree, circuit_name, point_for(tree))
                tree.write(target, encoding="utf-8", xml_declaration=True)

                with patch(f"{__name__}.ROOT", temporary_root):
                    with self.assertRaises(AssertionError):
                        regression()

    def test_halt_error_isolated_before_input_error_fixture(self):
        matrix = json.loads(
            (ROOT / "hardware/logisim/tinycpu-electrical-matrix-v1.json").read_text(
                encoding="utf-8"
            )
        )
        cases = matrix["opcode_cases"]
        ids = [case["id"] for case in cases]
        self.assertLess(ids.index("halt-error"), ids.index("input"))
        halt_error = next(case for case in cases if case["id"] == "halt-error")
        self.assertEqual(halt_error["program"], "LOAD_CONST(1)\nHALT_ERROR()\n")

    def test_core_acceptance_injects_minimal_rom_twice(self):
        profile = load_profile("tinycpu-16-12")
        source = ROOT / "hardware/logisim/TinyCPU.circ"
        seen_words = []

        def record_project(source, destination, top, rom_words=None, halt_output="HALTED"):
            seen_words.append(rom_words)
            destination.write_text("temporary project", encoding="utf-8")

        def deterministic_trace(project, jar, java, output, timeout):
            output.write_bytes(b"0\t0\n3\t1\n")

        with tempfile.TemporaryDirectory() as directory, patch(
            "tiny_cpu_logisim.autonomous_project", side_effect=record_project
        ), patch("tiny_cpu_logisim.run_trace", side_effect=deterministic_trace):
            run_core_acceptance(
                source, profile, Path("logisim.jar"), "java",
                Path(directory) / "core.tsv", 20,
            )

        self.assertEqual(seen_words, [(0x230003, 0x360000)] * 2)

    def test_core_acceptance_rejects_nondeterministic_runs(self):
        profile = load_profile("tinycpu-16-12")
        traces = iter((b"first\n", b"second\n"))

        def differing_trace(project, jar, java, output, timeout):
            output.write_bytes(next(traces))

        with tempfile.TemporaryDirectory() as directory, patch(
            "tiny_cpu_logisim.autonomous_project"
        ), patch("tiny_cpu_logisim.run_trace", side_effect=differing_trace):
            with self.assertRaisesRegex(LogisimError, "not deterministic"):
                run_core_acceptance(
                    ROOT / "hardware/logisim/TinyCPU.circ", profile,
                    Path("logisim.jar"), "java", Path(directory) / "core.tsv", 20,
                )



    def test_change_driven_table_is_not_mistaken_for_an_edge_count(self):
        # Logisim emits values, not a synthetic column-name header. Successful
        # completion of table,halt is the halt observation.
        table = b"0\t0\n1\t0\n2\t1\n"
        completed = subprocess.CompletedProcess([], 0, table, b"")
        with tempfile.TemporaryDirectory() as directory, patch(
            "tiny_cpu_logisim.subprocess.run", return_value=completed
        ):
            output = Path(directory) / "trace.tsv"
            run_trace(Path("project.circ"), Path("logisim.jar"), "java", output, 90)
            self.assertEqual(output.read_bytes(), table)

    def test_empty_electrical_table_is_rejected(self):
        completed = subprocess.CompletedProcess([], 0, b"", b"")
        with tempfile.TemporaryDirectory() as directory, patch(
            "tiny_cpu_logisim.subprocess.run", return_value=completed
        ):
            with self.assertRaisesRegex(LogisimError, "no electrical table"):
                run_trace(
                    Path("project.circ"), Path("logisim.jar"), "java",
                    Path(directory) / "trace.tsv", 90,
                )

    def test_timeout_reports_when_the_other_halt_output_was_reached(self):
        source = ROOT / "hardware/logisim/TinyCPU.circ"
        timed_out = subprocess.TimeoutExpired([], 1, output=b"partial\n")
        opposite_halt = subprocess.CompletedProcess([], 0, b"0\t1\n", b"")
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "autonomous.circ"
            autonomous_project(source, project, "TinyCPUMain")
            output = Path(directory) / "trace.tsv"
            with patch(
                "tiny_cpu_logisim.subprocess.run",
                side_effect=[timed_out, opposite_halt],
            ):
                with self.assertRaisesRegex(LogisimError, "non-selected halt output"):
                    run_trace(project, Path("logisim.jar"), "java", output, 1)
            self.assertEqual(output.read_bytes(), b"partial\n")

    def test_timeout_preserves_and_reports_the_trace_tail(self):
        source = ROOT / "hardware/logisim/TinyCPU.circ"
        rows = b"".join(f"pc-{index}\n".encode() for index in range(105))
        timed_out = subprocess.TimeoutExpired([], 1, output=rows)
        diagnostic_timeout = subprocess.TimeoutExpired([], 1, output=b"")
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "autonomous.circ"
            autonomous_project(source, project, "TinyCPUMain")
            output = Path(directory) / "trace.tsv"
            with patch(
                "tiny_cpu_logisim.subprocess.run",
                side_effect=[timed_out, diagnostic_timeout],
            ):
                with self.assertRaises(LogisimError) as raised:
                    run_trace(project, Path("logisim.jar"), "java", output, 1)
            message = str(raised.exception)
            self.assertIn(f"partial trace preserved at {output}", message)
            self.assertIn("last observed PC/control state", message)
            self.assertNotIn("pc-4\n", message)
            self.assertIn("pc-5\n", message)
            self.assertTrue(message.endswith("pc-104"))
            self.assertEqual(output.read_bytes(), rows)

    def test_default_cli_profile_is_a_loadable_profile_name(self):
        args = parse_args(["--trace-output", "trace.tsv"])
        profile = load_profile(args.profile)
        self.assertEqual(profile.name, "tinycpu-16-12")
        self.assertEqual(profile.circuit, "TinyCPU.circ")
        self.assertEqual(args.jobs, 1)

    def test_cli_rejects_nonpositive_job_count(self):
        with self.assertRaises(SystemExit):
            parse_args(["--trace-output", "trace.tsv", "--jobs", "0"])


    def test_autonomous_project_uses_profile_specific_circuit(self):
        source = ROOT / "hardware/logisim/TinyCPU.circ"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / source.name
            autonomous_project(source, target, "TinyCPUMain")
            root = ET.parse(target).getroot()
            main = next(c for c in root.findall("circuit") if c.get("name") == "TinyCPUMain")
            parts = {(c.get("name"), c.get("loc")) for c in main.findall("comp")}
            self.assertIn(("Clock", "(330,300)"), parts)
            self.assertIn(("NOT Gate", "(330,360)"), parts)
            self.assertIn(("Clock", "(290,360)"), parts)
            self.assertNotIn(("POR", "(330,360)"), parts)
            self.assertNotIn(("PowerOnReset", "(330,360)"), parts)
            clocks = {
                component.get("loc"): _attributes(component)
                for component in main.findall("comp")
                if component.get("name") == "Clock"
            }
            self.assertEqual(clocks["(330,300)"]["highDuration"], "2")
            self.assertEqual(clocks["(330,300)"]["lowDuration"], "2")
            self.assertEqual(clocks["(290,360)"]["highDuration"], "100")
            self.assertEqual(clocks["(290,360)"]["lowDuration"], "2")
            wires = {
                (wire.get("from"), wire.get("to"))
                for wire in main.findall("wire")
            }
            self.assertIn(("(290,360)", "(310,360)"), wires)
            labels = [a.get("val") for a in main.findall("comp/a") if a.get("name") == "label"]
            self.assertIn("halt", labels)
            self.assertIn("HALTED_WITH_ERROR", labels)
            self.assertNotIn("HALTED", labels)

    def test_autonomous_project_drives_optional_inputs_inactive(self):
        source = ROOT / "hardware/logisim/TinyCPU.circ"
        inactive = {
            "EXTERNAL_MEMORY_VALUE", "EXTERNAL_MEMORY_VALID",
            "USE_EXTERNAL_MEMORY", "INTERRUPT_ACCEPT",
            "INTERRUPT_TARGET_PC", "ILL_RET",
        }
        source_main = ET.parse(source).getroot().find("circuit[@name='TinyCPUMain']")
        self.assertIsNotNone(source_main)
        locations = {
            component.get("loc"): _attributes(component).get("label")
            for component in source_main.findall("comp[@name='Pin']")
            if _attributes(component).get("label") in inactive
        }
        self.assertEqual(set(locations.values()), inactive)

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / source.name
            autonomous_project(source, target, "TinyCPUMain")
            generated_main = ET.parse(target).getroot().find(
                "circuit[@name='TinyCPUMain']"
            )
            self.assertIsNotNone(generated_main)
            constants = {
                component.get("loc"): _attributes(component)
                for component in generated_main.findall("comp[@name='Constant']")
                if component.get("loc") in locations
            }
            self.assertEqual(set(constants), set(locations))
            for location, attributes in constants.items():
                name = locations[location]
                with self.subTest(input=name):
                    expected = "0x0" if name == "ILL_RET" else "0x1"
                    self.assertEqual(attributes.get("value"), expected)

    def test_autonomous_project_can_stop_on_error_halt(self):
        source = ROOT / "hardware/logisim/TinyCPU.circ"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / source.name
            autonomous_project(
                source, target, "TinyCPUMain", halt_output="HALTED_WITH_ERROR"
            )
            root = ET.parse(target).getroot()
            main = next(c for c in root.findall("circuit") if c.get("name") == "TinyCPUMain")
            labels = [a.get("val") for a in main.findall("comp/a") if a.get("name") == "label"]
            self.assertIn("halt", labels)
            self.assertIn("HALTED", labels)
            self.assertNotIn("HALTED_WITH_ERROR", labels)

    def test_source_project_is_not_modified(self):
        source = ROOT / "hardware/logisim/TinyCPU.circ"
        before = source.read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            autonomous_project(source, Path(directory) / "copy.circ", "TinyCPUMain")
        self.assertEqual(before, source.read_bytes())

    def test_register_offset_sum_reaches_effective_address_selector(self):
        for name in ("TinyCPU.circ",):
            root = ET.parse(ROOT / "hardware/logisim" / name).getroot()
            main = next(c for c in root.findall("circuit") if c.get("name") == "TinyCPUMain")
            wires = {(w.get("from"), w.get("to")) for w in main.findall("wire")}
            expected = (("(2180,1410)", "(2410,1410)") if name == "TinyCPU.circ"
                        else ("(2720,1760)", "(2940,1760)"))
            self.assertIn(
                expected, wires,
                f"{name} leaves the register-plus-offset selector floating",
            )

    def test_register_offset_load_selects_memory_data(self):
        for name in ("TinyCPU.circ",):
            root = ET.parse(ROOT / "hardware/logisim" / name).getroot()
            circuit_name = (
                "FetchDecodeControls" if name == "TinyCPU.circ" else "DecodeSignals"
            )
            decode = next(
                c for c in root.findall("circuit") if c.get("name") == circuit_name
            )
            if name == "TinyCPU.circ":
                pin_labels = {
                    attribute.get("val")
                    for component in decode.findall("comp")
                    for attribute in component.findall("a")
                    if component.get("name") == "Pin"
                    and attribute.get("name") == "label"
                }
                self.assertIn("LOAD_REG_OFF", pin_labels)
                self.assertIn("ADDR_REG_OFFS_ARGUMENT", pin_labels)
                continue
            wires = {(w.get("from"), w.get("to")) for w in decode.findall("wire")}
            self.assertNotIn(("(600,100)", "(710,100)"), wires)
            self.assertIn(("(570,160)", "(680,160)"), wires)
            self.assertIn(("(680,100)", "(680,160)"), wires)
            self.assertIn(("(680,100)", "(710,100)"), wires)

    def test_grouped_public_decoder_replaces_legacy_adapter(self):
        for name in ("TinyCPU.circ",):
            root = ET.parse(ROOT / "hardware/logisim" / name).getroot()
            main = next(c for c in root.findall("circuit") if c.get("name") == "TinyCPUMain")
            decoders = [
                component
                for component in main.findall("comp")
                if component.get("name") == "FetchDecodeControls"
            ]
            self.assertEqual(len(decoders), 1)
            self.assertFalse(any(
                component.get("name") == "ControlAdapterBlock"
                for component in main.findall("comp")
            ))
            self.assertFalse(any(
                circuit.get("name") == "ControlAdapterBlock"
                for circuit in root.findall("circuit")
            ))
            if name == "TinyCPU.circ":
                controls = next(
                    circuit for circuit in root.findall("circuit")
                    if circuit.get("name") == "FetchDecodeControls"
                )
                self.assertEqual(
                    sum(
                        component.get("name") == "Decoder"
                        for component in controls.findall("comp")
                    ),
                    1,
                    "FetchDecodeControls must fan out one shared opcode decoder",
                )

    def test_fetch_path_uses_profile_address_width(self):
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        fetch = next(c for c in root.findall("circuit") if c.get("name") == "FetchDecode")
        source = _component_by_label(fetch, "PROGRAM_LIMIT")
        attributes = _attributes(source)
        self.assertEqual(source.get("name"), "Pin")
        self.assertEqual(attributes.get("width"), "12")
        self.assertEqual(attributes.get("initial"), "0xfff")

        expected = {
            ("Constant", "(710,240)"),
            ("Register", "(550,190)"),
            ("Adder", "(770,230)"),
            ("Multiplexer", "(870,240)"),
            ("Comparator", "(740,390)"),
        }
        for kind, location in expected:
            matches = [
                component for component in fetch.findall("comp")
                if component.get("name") == kind
                and component.get("loc") == location
            ]
            self.assertEqual(len(matches), 1, f"expected one fetch {kind}")
            self.assertEqual(
                _attributes(matches[0]).get("width"), "12",
                f"FetchDecode {kind} must use the 12-bit address profile",
            )
        pc_splitter = next(
            component for component in fetch.findall("comp")
            if component.get("name") == "Splitter"
            and component.get("loc") == "(710,470)"
        )
        self.assertEqual(_attributes(pc_splitter).get("incoming"), "12")

    def test_authored_fetch_controls_keep_decoder_rows(self):
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        controls = next(
            circuit for circuit in root.findall("circuit")
            if circuit.get("name") == "FetchDecodeControls"
        )
        decoder = next(
            component for component in controls.findall("comp")
            if component.get("name") == "Decoder"
        )
        decoder_x, decoder_y = map(
            int, decoder.get("loc").strip("()").split(",")
        )

        # The canonical machine table follows this hand-authored control sheet:
        # decoder row 0 selects the ADD operation family and row 54 selects
        # HALT.  Do not reinterpret row 0 as the former LOAD_CONST opcode.
        # Resolve destinations by their public labels so the authored layout
        # can move without weakening this semantic regression.
        add_select = _component_by_label(controls, "ADD_OPERAND_SELECT")
        add_x, add_y = map(
            int, add_select.get("loc").strip("()").split(",")
        )
        authored_rows = (
            (0x00, f"({add_x - 50},{add_y - 20})", "ADD_OPERAND"),
            (0x36, _component_by_label(controls, "HALT").get("loc"), "HALT"),
        )
        for code, destination, label in authored_rows:
            source = f"({decoder_x + 20},{decoder_y - 640 + code * 10})"
            self.assertTrue(
                _wire_path_exists(controls, source, destination),
                f"decoder row 0x{code:02x} does not reach {label}",
            )

        self.assertTrue(
            _wire_path_exists(
                controls,
                add_select.get("loc"),
                _component_by_label(controls, "ADD_OPERAND").get("loc"),
            ),
            "ADD_OPERAND_SELECT does not reach ADD_OPERAND",
        )

    def test_reserved_opcode_3f_sets_illegal_and_halts_with_error(self):
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        controls = next(
            circuit for circuit in root.findall("circuit")
            if circuit.get("name") == "FetchDecodeControls"
        )
        decoder = next(
            component for component in controls.findall("comp")
            if component.get("name") == "Decoder"
        )
        decoder_x, decoder_y = map(
            int, decoder.get("loc").strip("()").split(",")
        )
        reserved_3f = f"({decoder_x + 20},{decoder_y - 640 + 0x3f * 10})"
        halt_error = f"({decoder_x + 20},{decoder_y - 640 + 0x37 * 10})"

        for gate_label, output_label in (
            ("RESERVED_OPCODE_SET_ILL", "SET_ILL"),
            ("RESERVED_OPCODE_HALT_ERROR", "HALT_ERROR"),
        ):
            gate = _component_by_label(controls, gate_label)
            gate_x, gate_y = map(int, gate.get("loc").strip("()").split(","))
            gate_inputs = (
                f"({gate_x - 50},{gate_y - 20})",
                f"({gate_x - 50},{gate_y + 20})",
            )
            self.assertTrue(
                any(
                    _wire_path_exists(controls, reserved_3f, terminal)
                    for terminal in gate_inputs
                ),
                f"reserved opcode 0x3f does not reach {gate_label}",
            )
            if output_label == "HALT_ERROR":
                self.assertTrue(
                    any(
                        _wire_path_exists(controls, halt_error, terminal)
                        for terminal in gate_inputs
                    ),
                    "HALT_ERROR opcode 0x37 does not reach its output gate",
                )
            self.assertTrue(
                _wire_path_exists(
                    controls,
                    gate.get("loc"),
                    _component_by_label(controls, output_label).get("loc"),
                ),
                f"{gate_label} does not reach {output_label}",
            )

    def test_visible_top_level_memory_or_gate_has_every_input_connected(self):
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        main = next(c for c in root.findall("circuit") if c.get("name") == "TinyCPUMain")

        # These are the input terminals rendered by Logisim for the OR gates
        # highlighted on the integration sheet.  Keep the count explicit so a
        # redraw cannot silently leave an input at its default/floating value.
        expected_inputs = {
            "MEMORY_WRITE_REQUEST": {"(530,600)", "(530,620)", "(530,640)"},
        }
        wire_endpoints = {
            endpoint
            for wire in main.findall("wire")
            for endpoint in (wire.get("from"), wire.get("to"))
        }

        for label, terminals in expected_inputs.items():
            gate = _component_by_label(main, label)
            attributes = _attributes(gate)
            self.assertEqual(gate.get("name"), "OR Gate")
            self.assertEqual(int(attributes.get("inputs", "2")), len(terminals))
            self.assertTrue(
                terminals.issubset(wire_endpoints),
                f"{label} has an unconnected input terminal",
            )

    def test_add_operand_reaches_operations_input(self):
        expected = ("(1400,1090)", "(2410,1090)")
        wrong_error_flags_route = {
            ("(1270,930)", "(2170,930)"),
            ("(2170,450)", "(2170,930)"),
            ("(2170,450)", "(2490,450)"),
            ("(2490,450)", "(2520,450)"),
        }
        stale_load_const_route = {
            ("(1270,930)", "(1640,930)"),
            ("(1640,770)", "(1640,930)"),
            ("(1640,770)", "(3350,770)"),
        }
        for name in ("TinyCPU.circ",):
            root = ET.parse(ROOT / "hardware/logisim" / name).getroot()
            operations = next(c for c in root.findall("circuit") if c.get("name") == "Operations")
            add_operand = _component_by_label(operations, "ADD_OPERAND")
            add_operation = _component_by_label(operations, "ADD_OPERATION")
            operation_x, operation_y = map(
                int, add_operation.get("loc").strip("()").split(",")
            )
            self.assertTrue(
                _wire_path_exists(
                    operations, add_operand.get("loc"),
                    f"({operation_x - 220},{operation_y})",
                ),
                f"{name} does not drive the addition enable input",
            )
            main = next(c for c in root.findall("circuit") if c.get("name") == "TinyCPUMain")
            wires = {(wire.get("from"), wire.get("to")) for wire in main.findall("wire")}
            self.assertIn(expected, wires, f"{name} leaves ADD_OPERAND disconnected")
            self.assertTrue(
                wrong_error_flags_route.isdisjoint(wires),
                f"{name} routes ADD_OPERAND into the ErrorFlags instance",
            )
            self.assertTrue(
                stale_load_const_route.isdisjoint(wires),
                f"{name} still routes ADD_OPERAND to the LOAD_CONST monitor",
            )

    def test_effective_address_monitors_do_not_cross_address_range_box(self):
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        main = next(c for c in root.findall("circuit") if c.get("name") == "TinyCPUMain")

        # The generated AddressRangeFBox occupies x=3060..3280 and
        # y=1370..1530.  The old direct monitor routes crossed its face,
        # obscuring port names and making unrelated nets look connected.
        box_left, box_right = 3060, 3280
        box_top, box_bottom = 1370, 1530
        for wire in main.findall("wire"):
            (x1, y1), (x2, y2) = (
                tuple(map(int, wire.get(endpoint).strip("()").split(",")))
                for endpoint in ("from", "to")
            )
            horizontal_crossing = (
                y1 == y2
                and box_top < y1 < box_bottom
                and min(x1, x2) < box_right
                and max(x1, x2) > box_left
            )
            self.assertFalse(
                horizontal_crossing,
                f"wire {wire.get('from')}..{wire.get('to')} crosses AddressRangeFBox",
            )

        self.assertTrue(
            _wire_path_exists(main, "(2630,1330)", "(3590,1280)"),
            "effective-register monitor was disconnected by the visual reroute",
        )
        self.assertTrue(
            _wire_path_exists(main, "(2630,1370)", "(3580,1300)"),
            "effective-address monitor was disconnected by the visual reroute",
        )

    def test_print_control_reaches_public_enable_pin(self):
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        main = next(c for c in root.findall("circuit") if c.get("name") == "TinyCPUMain")
        print_enable = _component_by_label(main, "PRINT_ENABLE")

        # Follow the complete net instead of fixing the test to a particular
        # canvas route.  (1400,1650) is the PRINT port of the controls instance.
        self.assertTrue(
            _wire_path_exists(main, "(1400,1650)", print_enable.get("loc")),
            "FetchDecodeControls.PRINT does not reach TinyCPUMain.PRINT_ENABLE",
        )

    def test_print_address_control_reaches_public_enable_pin(self):
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        main = next(c for c in root.findall("circuit") if c.get("name") == "TinyCPUMain")
        print_address_enable = _component_by_label(main, "PRINT_ADDRESS_ENABLE")

        # Follow the complete net instead of fixing the test to a particular
        # canvas route.  (1400,1670) is the PRINT_ADDRESS port of the controls
        # instance.
        self.assertTrue(
            _wire_path_exists(main, "(1400,1670)", print_address_enable.get("loc")),
            "FetchDecodeControls.PRINT_ADDRESS does not reach "
            "TinyCPUMain.PRINT_ADDRESS_ENABLE",
        )

    def test_halt_control_reaches_public_halted_pin(self):
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        main = next(c for c in root.findall("circuit") if c.get("name") == "TinyCPUMain")
        halted = _component_by_label(main, "HALTED")

        # Follow the complete net instead of fixing the test to a particular
        # canvas route.  (1400,1830) is the HALT port of the controls instance.
        self.assertTrue(
            _wire_path_exists(main, "(1400,1830)", halted.get("loc")),
            "FetchDecodeControls.HALT does not reach TinyCPUMain.HALTED",
        )

    def test_halt_error_control_reaches_public_halted_with_error_pin(self):
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        main = next(c for c in root.findall("circuit") if c.get("name") == "TinyCPUMain")
        halted_with_error = _component_by_label(main, "HALTED_WITH_ERROR")

        # Follow the complete net instead of fixing the test to a particular
        # canvas route.  (1400,1850) is the HALT_ERROR port of the controls
        # instance.
        self.assertTrue(
            _wire_path_exists(main, "(1400,1850)", halted_with_error.get("loc")),
            "FetchDecodeControls.HALT_ERROR does not reach "
            "TinyCPUMain.HALTED_WITH_ERROR",
        )

    def test_input_error_control_reaches_input_error_flag(self):
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        main = next(c for c in root.findall("circuit") if c.get("name") == "TinyCPUMain")

        # INPUT with no value asserts SET_INPUT at the controls instance. The
        # matching ErrorFlags input is the last input on its generated symbol.
        self.assertTrue(
            _wire_path_exists(main, "(1400,1770)", "(2400,590)"),
            "FetchDecodeControls.SET_INPUT does not reach ErrorFlags.SET_INPUT",
        )

    def test_jump_wiring_is_encapsulated_without_tunnels(self):
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        main = next(c for c in root.findall("circuit") if c.get("name") == "TinyCPUMain")
        boxes = [component for component in main.findall("comp")
                 if component.get("name") == "JumpBox"]
        self.assertEqual(len(boxes), 1)
        self.assertEqual(_attributes(boxes[0]).get("label"), "JUMP_BOX")
        self.assertEqual(
            boxes[0].get("loc"), "(3540,450)",
            "JumpBox must stay in the existing compact upper-right layout",
        )

        jump_labels = {
            "JUMP_ADR_CONTROL", "JUMP_ZERO_CONTROL", "JUMP_NEGATIVE_CONTROL",
            "JUMP_ERROR_CONTROL", "JUMP_NOT_ERROR_CONTROL", "ANY_JUMP_CONTROL",
            "ANY_JUMP_CONDITION", "ANY_ERROR_CONDITION", "NO_ERROR_CONDITION",
        }
        self.assertFalse(any(
            component.get("name") == "Tunnel"
            and (_attributes(component).get("label") in jump_labels
                 or _attributes(component).get("label", "").startswith("JUMP_"))
            for component in main.findall("comp")
        ))
        self.assertFalse(any(
            component.get("name") in {"AND Gate", "NOT Gate"}
            or (component.get("name") == "OR Gate"
                and _attributes(component).get("label", "").startswith("JUMP_"))
            for component in main.findall("comp")
        ))

        # The generated JumpBox symbol orders inputs by the child sheet's pin
        # position: errors, controls, then NEGATIVE and ZERO.  The six control
        # taps start at (1400,1330); (1400,1440) and (1400,1460) are LOAD_CONST
        # and LOAD_ADDRESS and must never feed the jump-control inputs.
        # Keep the box in
        # its established upper-right position: moving it below the main
        # circuit makes every signal take a long, hard-to-read detour.
        sources = [
            "(2620,450)", "(2620,470)", "(2620,490)", "(2620,510)",
            "(2620,530)", "(2620,550)", "(1400,1330)", "(1400,1350)",
            "(1400,1370)", "(1400,1390)", "(1400,1410)", "(1400,1430)",
            "(2000,510)", "(2000,490)",
        ]
        for source, y in zip(sources, range(450, 730, 20)):
            self.assertTrue(
                _wire_path_exists(main, source, f"(3320,{y})"),
                f"{source} does not reach its JumpBox input",
            )
        self.assertTrue(_wire_path_exists(main, "(3540,450)", "(670,380)"))
        self.assertTrue(_wire_path_exists(main, "(3540,470)", "(650,400)"))

    def test_jump_box_gates_zero_conditions_with_the_matching_controls(self):
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        jump_box = next(
            circuit for circuit in root.findall("circuit")
            if circuit.get("name") == "JumpBox"
        )
        jump_zero = _component_by_label(jump_box, "JUMP_ZERO_AND_ZERO")
        invert_zero = _component_by_label(jump_box, "INVERT_ZERO_FOR_JNZ")
        jump_not_zero = _component_by_label(jump_box, "JUMP_NOT_ZERO_AND_NOT_ZERO")
        taken = _component_by_label(jump_box, "JUMP_ZERO_OR_PREVIOUS_TAKEN")

        self.assertEqual(jump_not_zero.get("name"), "AND Gate")
        self.assertEqual(_attributes(taken).get("inputs"), "3")
        self.assertTrue(_wire_path_exists(
            jump_box, _pin_location(jump_box, "JUMP_NOT_ZERO"),
            _point_offset(jump_not_zero, -50, -20),
        ))
        self.assertTrue(_wire_path_exists(
            jump_box, invert_zero.get("loc"),
            _point_offset(jump_not_zero, -50, 20),
        ))
        self.assertTrue(_wire_path_exists(
            jump_box, _pin_location(jump_box, "JUMP_ZERO"),
            _point_offset(jump_zero, -50, -20),
        ))
        self.assertTrue(_wire_path_exists(
            jump_box, _pin_location(jump_box, "ZERO"),
            _point_offset(jump_zero, -50, 20),
        ))
        self.assertTrue(_wire_path_exists(
            jump_box, _pin_location(jump_box, "JUMP_ADR"),
            _point_offset(taken, -50, 0),
        ))

    def test_jump_box_gates_error_conditions_with_the_matching_controls(self):
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        jump_box = next(
            circuit for circuit in root.findall("circuit")
            if circuit.get("name") == "JumpBox"
        )
        any_error = _component_by_label(jump_box, "ANY_ERROR_FOR_JUMP")
        invert_error = _component_by_label(
            jump_box, "INVERT_ANY_ERROR_FOR_JUMP_NOT_ERROR"
        )
        # These two historical labels describe their former positions in the
        # chain.  Assert their actual operands through named components so a
        # drawing-only move cannot invalidate the topology test again.
        jump_error = _component_by_label(
            jump_box, "JUMP_NOT_ERROR_AND_NO_ERROR"
        )
        jump_not_error = _component_by_label(
            jump_box, "JUMP_ERROR_AND_ANY_ERROR"
        )

        self.assertTrue(_wire_path_exists(
            jump_box, _pin_location(jump_box, "JUMP_ERROR"),
            _point_offset(jump_error, -50, -20),
        ))
        self.assertTrue(_wire_path_exists(
            jump_box, any_error.get("loc"),
            _point_offset(jump_error, -50, 20),
        ))
        self.assertTrue(_wire_path_exists(
            jump_box, _pin_location(jump_box, "JUMP_NOT_ERROR"),
            _point_offset(jump_not_error, -50, -20),
        ))
        self.assertTrue(_wire_path_exists(
            jump_box, invert_error.get("loc"),
            _point_offset(jump_not_error, -50, 20),
        ))

    def test_sub_operand_reaches_operations_input(self):
        expected = ("(1400,1110)", "(2410,1110)")
        stale_sub_monitor_route = {
            ("(1270,950)", "(1740,950)"),
            ("(1740,950)", "(1740,2500)"),
        }
        stale_sub_input_route = {
            ("(1720,850)", "(1720,1030)"),
            ("(1720,850)", "(2490,850)"),
        }
        for name in ("TinyCPU.circ",):
            root = ET.parse(ROOT / "hardware/logisim" / name).getroot()
            operations = next(c for c in root.findall("circuit") if c.get("name") == "Operations")
            sub_operand = _component_by_label(operations, "SUB_OPERAND")
            sub_operation = _component_by_label(operations, "SUB_OPERATION")
            operation_x, operation_y = map(
                int, sub_operation.get("loc").strip("()").split(",")
            )
            self.assertTrue(
                _wire_path_exists(
                    operations, sub_operand.get("loc"),
                    f"({operation_x - 220},{operation_y})",
                ),
                f"{name} does not drive the subtraction enable input",
            )

            controls = next(
                c for c in root.findall("circuit")
                if c.get("name") == "FetchDecodeControls"
            )
            public_sub_operand = _component_by_label(controls, "SUB_OPERAND")
            sub_operand_select = _component_by_label(
                controls, "SUB_OPERAND_SELECT"
            )
            self.assertTrue(
                _wire_path_exists(
                    controls,
                    sub_operand_select.get("loc"),
                    public_sub_operand.get("loc"),
                ),
                f"{name} does not drive the public SUB_OPERAND output",
            )
            main = next(c for c in root.findall("circuit") if c.get("name") == "TinyCPUMain")
            wires = {(wire.get("from"), wire.get("to")) for wire in main.findall("wire")}
            self.assertIn(expected, wires, f"{name} leaves SUB_OPERAND disconnected")
            self.assertTrue(
                stale_sub_monitor_route.isdisjoint(wires),
                f"{name} still routes SUB_OPERAND to the stale monitor net",
            )
            self.assertTrue(
                stale_sub_input_route.isdisjoint(wires),
                f"{name} still routes the stale decoder output to SUB_CONST",
            )

    def test_public_decoder_preserves_authored_control_boundary(self):
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        controls = next(
            circuit for circuit in root.findall("circuit")
            if circuit.get("name") == "FetchDecodeControls"
        )
        labels = {
            attribute.get("val")
            for component in controls.findall("comp")
            for attribute in component.findall("a")
            if component.get("name") == "Pin" and attribute.get("name") == "label"
        }
        self.assertTrue({
            "ADD_OPERAND", "SUB_OPERAND", "MUL_OPERAND", "DIV_OPERAND",
            "AND_OPERAND", "OR_OPERAND", "XOR_OPERAND",
            "CONST_ARGUMENT", "ADDR_ARGUMENT",
            "ADDR_REG_ARGUMENT", "ADDR_REG_OFFS_ARGUMENT",
        }.issubset(labels))
        self.assertTrue({
            "LOAD_CONST", "LOAD_ADR", "LOAD_ADR_REG", "LOAD_REG_OFF",
            "STORE_ADR", "STORE_ADR_REG", "STORE_REG_OFF",
        }.issubset(labels))
        self.assertTrue({"LOAD_OPERAND", "STORE_OPERAND"}.isdisjoint(labels))

    def test_argument_kind_drives_effective_address_without_operation_fan_in(self):
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        effective = next(
            circuit for circuit in root.findall("circuit")
            if circuit.get("name") == "EffectiveAddress"
        )
        pin_labels = {
            attribute.get("val")
            for component in effective.findall("comp")
            for attribute in component.findall("a")
            if component.get("name") == "Pin" and attribute.get("name") == "label"
        }
        self.assertTrue({"ADDR_REG_ARGUMENT", "ADDR_REG_OFFS_ARGUMENT"}.issubset(pin_labels))
        self.assertFalse(any(
            label and (label.startswith("ADD_") or label.startswith("LOAD_")
                       or label.startswith("STORE_") or label.startswith("SUB_"))
            for label in pin_labels
        ))

    def test_matrix_rom_is_injected_only_into_temporary_project(self):
        source = ROOT / "hardware/logisim/TinyCPU.circ"
        before = source.read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "copy.circ"
            autonomous_project(source, target, "TinyCPUMain", (0x123, 0x456))
            root = ET.parse(target).getroot()
            rom = next(c for owner in root.findall("circuit") for c in owner.findall("comp")
                       if c.get("name") == "ROM")
            contents = next(a for a in rom.findall("a") if a.get("name") == "contents")
            self.assertEqual(contents.text, "addr/data: 12 22\n123 456\n")
        self.assertEqual(before, source.read_bytes())

    def test_reserved_opcode_fixture_halts_in_reference_model(self):
        profile = load_profile("tinycpu-16-12")
        case = {"program": "HALT()\n", "raw_words": [0x3F0000, 0x2D0000]}
        program = _matrix_program(case, profile)
        self.assertEqual(program.instructions[0].mnemonic, "__ILLEGAL__")
        self.assertEqual(_expected_edges(program), 1)
        self.assertEqual(_expected_halt_output(program), "HALTED_WITH_ERROR")

    def test_matrix_reports_progress_before_each_electrical_run(self):
        profile = load_profile("tinycpu-16-12")
        output = StringIO()
        with tempfile.TemporaryDirectory() as directory, patch(
            "tiny_cpu_logisim.run_trace"
        ) as trace, redirect_stdout(output):
            count = run_matrix(
                ROOT / "hardware/logisim/TinyCPU.circ",
                profile,
                Path("logisim.jar"),
                "java",
                Path(directory) / "evidence",
                90,
            )

        lines = output.getvalue().splitlines()
        self.assertEqual(len(lines), count)
        self.assertEqual(trace.call_count, count)
        self.assertIn(f"[1/{count}]", lines[0])
        self.assertIn(f"[{count}/{count}]", lines[-1])
        self.assertIn("tinycpu-16-12", lines[0])

    def test_matrix_can_run_two_electrical_fixtures_concurrently(self):
        profile = load_profile("tinycpu-16-12")
        barrier = threading.Barrier(2)
        lock = threading.Lock()
        started = 0

        def synchronized_trace(*_args):
            nonlocal started
            with lock:
                started += 1
                should_wait = started <= 2
            if should_wait:
                barrier.wait(timeout=5)

        with tempfile.TemporaryDirectory() as directory, patch(
            "tiny_cpu_logisim.run_trace", side_effect=synchronized_trace
        ) as trace, redirect_stdout(StringIO()):
            count = run_matrix(
                ROOT / "hardware/logisim/TinyCPU.circ",
                profile,
                Path("logisim.jar"),
                "java",
                Path(directory) / "evidence",
                90,
                jobs=2,
            )

        self.assertEqual(trace.call_count, count)

    def test_matrix_error_identifies_the_failing_fixture(self):
        profile = load_profile("tinycpu-16-12")

        def fail_first(_project, _jar, _java, output, _timeout):
            if output.stem == "load-const":
                raise LogisimError("trace timed out")

        attempted = []

        def record_and_fail(*args):
            attempted.append(args[3].stem)
            fail_first(*args)

        with tempfile.TemporaryDirectory() as directory, patch(
            "tiny_cpu_logisim.run_trace", side_effect=record_and_fail
        ), redirect_stdout(StringIO()):
            with self.assertRaisesRegex(
                LogisimError, "tinycpu-16-12 fixture load-const: trace timed out"
            ):
                run_matrix(
                    ROOT / "hardware/logisim/TinyCPU.circ",
                    profile,
                    Path("logisim.jar"),
                    "java",
                    Path(directory) / "evidence",
                    90,
                )
        self.assertEqual(attempted, ["load-const"])

    def test_vendored_jar_is_preferred_without_an_override(self):
        with tempfile.TemporaryDirectory() as directory:
            vendored = Path(directory) / "vendor/logisim-evolution-4.1.0-all.jar"
            vendored.parent.mkdir()
            vendored.write_bytes(b"test jar")
            self.assertEqual(resolve_jar(None, vendored=vendored), vendored)

    def test_repository_virtual_environment_jar_is_used_offline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vendored = root / "vendor" / "missing.jar"
            local_env = root / ".venv" / "Include" / "logisim.jar"
            local_env.parent.mkdir(parents=True)
            local_env.write_bytes(b"test jar")
            self.assertEqual(
                resolve_jar(None, vendored=vendored, local_env=local_env),
                local_env,
            )

    def test_missing_vendored_jar_is_named_when_download_fails(self):
        with tempfile.TemporaryDirectory() as directory, patch(
            "tiny_cpu_logisim.urllib.request.urlretrieve",
            side_effect=OSError("network unavailable"),
        ):
            vendored = Path(directory) / "vendor" / "missing.jar"
            local_env = Path(directory) / ".venv" / "Include" / "missing.jar"
            with patch("tiny_cpu_logisim.Path.home", return_value=Path(directory)):
                with self.assertRaisesRegex(LogisimError, str(vendored)):
                    resolve_jar(None, vendored=vendored, local_env=local_env)


if __name__ == "__main__":
    unittest.main()
