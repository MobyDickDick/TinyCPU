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


class LogisimLauncherTests(unittest.TestCase):
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

    def test_default_cli_profile_is_a_loadable_profile_name(self):
        args = parse_args(["--trace-output", "trace.tsv"])
        profile = load_profile(args.profile)
        self.assertEqual(profile.name, "tinycpu-16-12")
        self.assertEqual(profile.circuit, "TinyCPU.circ")
        self.assertEqual(args.jobs, 1)

    def test_cli_rejects_nonpositive_job_count(self):
        with self.assertRaises(SystemExit):
            parse_args(["--trace-output", "trace.tsv", "--jobs", "0"])

    def test_combined_gate_attempts_both_profiles_after_a_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            log = temporary / "calls"
            fake_python = temporary / "python3"
            fake_python.write_text(
                "#!/bin/sh\n"
                f"printf '%s\\n' \"$*\" >> {log}\n"
                "case \" $* \" in *' --profile tinycpu-16-12 '*) exit 1;; esac\n",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)
            environment = os.environ.copy()
            environment["PATH"] = f"{temporary}:{environment['PATH']}"
            environment["LOGISIM_OUTPUT"] = str(temporary / "evidence")
            result = subprocess.run(
                ["bash", str(ROOT / "scripts/test-logisim.sh")],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            calls = log.read_text(encoding="utf-8")
            self.assertEqual(result.returncode, 1)
            self.assertIn("--profile tinycpu-16-12", calls)
            self.assertIn("--profile tinycpu-8-8", calls)
            self.assertIn("--jobs 1", calls)
            self.assertIn("tinycpu-16-12", result.stderr)

    def test_autonomous_project_uses_profile_specific_circuit(self):
        source = ROOT / "hardware/logisim/TinyCPU-8-8.circ"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / source.name
            autonomous_project(source, target, "TinyCPUMain")
            root = ET.parse(target).getroot()
            main = next(c for c in root.findall("circuit") if c.get("name") == "TinyCPUMain")
            parts = {(c.get("name"), c.get("loc")) for c in main.findall("comp")}
            self.assertIn(("Clock", "(200,310)"), parts)
            self.assertIn(("PowerOnReset", "(200,370)"), parts)
            labels = [a.get("val") for a in main.findall("comp/a") if a.get("name") == "label"]
            self.assertIn("halt", labels)
            self.assertIn("HALTED_WITH_ERROR", labels)
            self.assertNotIn("HALTED", labels)

    def test_autonomous_project_can_stop_on_error_halt(self):
        source = ROOT / "hardware/logisim/TinyCPU-8-8.circ"
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
        source = ROOT / "hardware/logisim/TinyCPU-8-8.circ"
        before = source.read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            autonomous_project(source, Path(directory) / "copy.circ", "TinyCPUMain")
        self.assertEqual(before, source.read_bytes())

    def test_register_offset_sum_reaches_effective_address_selector(self):
        for name in ("TinyCPU.circ", "TinyCPU-8-8.circ"):
            root = ET.parse(ROOT / "hardware/logisim" / name).getroot()
            main = next(c for c in root.findall("circuit") if c.get("name") == "TinyCPUMain")
            wires = {(w.get("from"), w.get("to")) for w in main.findall("wire")}
            expected = (("(2410,1430)", "(2660,1430)") if name == "TinyCPU.circ"
                        else ("(2280,2130)", "(2470,2130)"))
            self.assertIn(
                expected, wires,
                f"{name} leaves the register-plus-offset selector floating",
            )

    def test_register_offset_load_selects_memory_data(self):
        for name in ("TinyCPU.circ", "TinyCPU-8-8.circ"):
            root = ET.parse(ROOT / "hardware/logisim" / name).getroot()
            decode = next(c for c in root.findall("circuit") if c.get("name") == "DecodeSignals")
            wires = {(w.get("from"), w.get("to")) for w in decode.findall("wire")}
            self.assertNotIn(("(600,100)", "(710,100)"), wires)
            self.assertIn(("(570,160)", "(680,160)"), wires)
            self.assertIn(("(680,100)", "(680,160)"), wires)
            self.assertIn(("(680,100)", "(710,100)"), wires)

    def test_grouped_public_decoder_replaces_legacy_adapter(self):
        for name in ("TinyCPU.circ", "TinyCPU-8-8.circ"):
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

    def test_program_limit_source_uses_profile_maximum(self):
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        main = next(c for c in root.findall("circuit") if c.get("name") == "TinyCPUMain")
        sources = [
            component
            for component in main.findall("comp")
            if component.get("name") == "Constant"
            and any(
                attribute.get("name") == "label"
                and attribute.get("val") == "PROGRAM_LIMIT_MAX"
                for attribute in component.findall("a")
            )
        ]
        self.assertEqual(len(sources), 1)
        attributes = {
            attribute.get("name"): attribute.get("val")
            for attribute in sources[0].findall("a")
        }
        self.assertEqual(attributes.get("width"), "16")
        self.assertEqual(attributes.get("value"), "0xfff")

        source = sources[0].get("loc")
        attached_wires = [
            wire for wire in main.findall("wire")
            if source in (wire.get("from"), wire.get("to"))
        ]
        self.assertEqual(
            len(attached_wires), 1,
            "the named program-limit source must exclusively drive its existing fetch net",
        )

    def test_visible_top_level_or_gates_have_every_input_connected(self):
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        main = next(c for c in root.findall("circuit") if c.get("name") == "TinyCPUMain")

        # These are the input terminals rendered by Logisim for the OR gates
        # highlighted on the integration sheet.  Keep the count explicit so a
        # redraw cannot silently leave an input at its default/floating value.
        expected_inputs = {
            "MEMORY_WRITE_REQUEST": {"(530,670)", "(530,690)", "(530,710)"},
            "JUMP_ADR_OR_JNZ_CONTROL": {"(2580,1910)", "(2580,1930)"},
            "JUMP_ZERO_OR_PREVIOUS_CONTROLS": {"(2890,1930)", "(2890,1950)"},
            "JUMP_NEGATIVE_OR_PREVIOUS_CONTROLS": {"(3280,1950)", "(3280,1970)"},
            "JUMP_ADR_OR_NOT_ZERO": {"(2890,2040)", "(2890,2060)"},
            "JUMP_ZERO_OR_PREVIOUS_TAKEN": {"(3270,2080)", "(3270,2100)"},
            "JUMP_NEGATIVE_OR_PREVIOUS_TAKEN": {"(3610,2160)", "(3610,2180)"},
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
        expected = ("(1400,1050)", "(2650,1050)")
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

    def test_print_control_reaches_public_enable_pin(self):
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        main = next(c for c in root.findall("circuit") if c.get("name") == "TinyCPUMain")
        print_enable = _component_by_label(main, "PRINT_ENABLE")

        # Follow the complete net instead of fixing the test to a particular
        # canvas route.  (1400,1610) is the PRINT port of the controls instance.
        self.assertTrue(
            _wire_path_exists(main, "(1400,1610)", print_enable.get("loc")),
            "FetchDecodeControls.PRINT does not reach TinyCPUMain.PRINT_ENABLE",
        )

    def test_print_address_control_reaches_public_enable_pin(self):
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        main = next(c for c in root.findall("circuit") if c.get("name") == "TinyCPUMain")
        print_address_enable = _component_by_label(main, "PRINT_ADDRESS_ENABLE")

        # Follow the complete net instead of fixing the test to a particular
        # canvas route.  (1400,1630) is the PRINT_ADDRESS port of the controls
        # instance.
        self.assertTrue(
            _wire_path_exists(main, "(1400,1630)", print_address_enable.get("loc")),
            "FetchDecodeControls.PRINT_ADDRESS does not reach "
            "TinyCPUMain.PRINT_ADDRESS_ENABLE",
        )

    def test_halt_control_reaches_public_halted_pin(self):
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        main = next(c for c in root.findall("circuit") if c.get("name") == "TinyCPUMain")
        halted = _component_by_label(main, "HALTED")

        # Follow the complete net instead of fixing the test to a particular
        # canvas route.  (1400,1650) is the HALT port of the controls instance.
        self.assertTrue(
            _wire_path_exists(main, "(1400,1650)", halted.get("loc")),
            "FetchDecodeControls.HALT does not reach TinyCPUMain.HALTED",
        )

    def test_halt_error_control_reaches_public_halted_with_error_pin(self):
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        main = next(c for c in root.findall("circuit") if c.get("name") == "TinyCPUMain")
        halted_with_error = _component_by_label(main, "HALTED_WITH_ERROR")

        # Follow the complete net instead of fixing the test to a particular
        # canvas route.  (1400,1670) is the HALT_ERROR port of the controls
        # instance.
        self.assertTrue(
            _wire_path_exists(main, "(1400,1670)", halted_with_error.get("loc")),
            "FetchDecodeControls.HALT_ERROR does not reach "
            "TinyCPUMain.HALTED_WITH_ERROR",
        )

    def test_unconditional_jump_reaches_common_pc_select(self):
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        main = next(c for c in root.findall("circuit") if c.get("name") == "TinyCPUMain")

        jump_tunnels = [
            component for component in main.findall("comp")
            if component.get("name") == "Tunnel"
        ]
        self.assertEqual(
            [_attributes(component).get("label") for component in jump_tunnels],
            ["NEGATIVE_FOR_JUMP", "NEGATIVE_FOR_JUMP", "NEGATIVE_FOR_JUMP"],
        )
        self.assertTrue(_wire_path_exists(main, "(1400,1330)", "(2580,1930)"))
        self.assertTrue(_wire_path_exists(main, "(1400,1370)", "(2580,1910)"))
        self.assertTrue(_wire_path_exists(main, "(3950,1940)", "(4230,1950)"))
        self.assertTrue(_wire_path_exists(main, "(3980,2200)", "(4400,2400)"))

    def test_jump_zero_reaches_common_pc_select(self):
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        main = next(c for c in root.findall("circuit") if c.get("name") == "TinyCPUMain")

        self.assertTrue(_wire_path_exists(main, "(1400,1350)", "(2890,2110)"))
        self.assertTrue(_wire_path_exists(main, "(2080,490)", "(2890,2130)"))
        self.assertTrue(_wire_path_exists(main, "(2920,2120)", "(3270,2100)"))
        self.assertTrue(_wire_path_exists(main, "(2920,1940)", "(3280,1950)"))

    def test_jump_negative_reaches_common_pc_select(self):
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        main = next(c for c in root.findall("circuit") if c.get("name") == "TinyCPUMain")

        self.assertTrue(_wire_path_exists(main, "(1400,1390)", "(2890,2180)"))
        self.assertTrue(_wire_path_exists(main, "(2080,510)", "(2100,510)"))
        self.assertTrue(_wire_path_exists(main, "(2870,2200)", "(2890,2200)"))
        self.assertTrue(_wire_path_exists(main, "(2920,2190)", "(3610,2180)"))
        self.assertTrue(_wire_path_exists(main, "(3300,2090)", "(3610,2160)"))

    def test_jump_error_reaches_common_pc_select(self):
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        main = next(c for c in root.findall("circuit") if c.get("name") == "TinyCPUMain")

        any_error = _component_by_label(main, "ANY_ERROR_FOR_JUMP")
        error_taken = _component_by_label(main, "JUMP_ERROR_AND_ANY_ERROR")
        control_merge = _component_by_label(main, "JUMP_ERROR_OR_PREVIOUS_CONTROLS")
        taken_merge = _component_by_label(main, "JUMP_ERROR_OR_PREVIOUS_TAKEN")
        self.assertEqual(any_error.get("name"), "OR Gate")
        self.assertEqual(_attributes(any_error).get("inputs"), "6")
        self.assertEqual(error_taken.get("name"), "AND Gate")
        self.assertEqual(control_merge.get("name"), "OR Gate")
        self.assertEqual(taken_merge.get("name"), "OR Gate")

        for error_pin, terminal in zip((
            "ERROR_OVF", "ERROR_DIV0", "ERROR_ADDR",
            "ERROR_INV", "ERROR_ILL", "ERROR_INPUT",
        ), ("(3520,2220)", "(3520,2240)", "(3520,2260)",
            "(3520,2280)", "(3520,2300)", "(3520,2320)")):
            self.assertTrue(
                _wire_path_exists(main, _component_by_label(main, error_pin).get("loc"), terminal),
                f"{error_pin} does not contribute to the JUMP_ERROR condition",
            )

        # (1400,1410) is FetchDecodeControls.JUMP_ERROR.  The two merge
        # stages extend, rather than replace, the previously repaired jump
        # control and taken-condition chains.
        self.assertTrue(_wire_path_exists(main, "(1400,1410)", "(3810,2250)"))
        self.assertTrue(_wire_path_exists(main, "(1400,1410)", "(3920,1930)"))
        self.assertTrue(_wire_path_exists(main, any_error.get("loc"), "(3810,2270)"))
        self.assertTrue(_wire_path_exists(main, "(3310,1960)", "(3920,1950)"))
        self.assertTrue(_wire_path_exists(main, "(3640,2170)", "(3950,2190)"))
        self.assertTrue(_wire_path_exists(main, error_taken.get("loc"), "(3950,2210)"))
        self.assertTrue(_wire_path_exists(main, control_merge.get("loc"), "(4230,1950)"))
        self.assertTrue(_wire_path_exists(main, taken_merge.get("loc"), "(4400,2400)"))

    def test_jump_error_routes_stop_at_gate_inputs(self):
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        main = next(c for c in root.findall("circuit") if c.get("name") == "TinyCPUMain")
        wires = {(wire.get("from"), wire.get("to")) for wire in main.findall("wire")}

        # A source routed from the right of an east-facing gate continues
        # through its symbol and is rendered as a misleading tail.  Both AND
        # inputs must instead be approached from the left and end exactly at
        # their terminals.
        self.assertIn(("(3790,2250)", "(3810,2250)"), wires)
        self.assertIn(("(3770,2270)", "(3810,2270)"), wires)
        self.assertNotIn(("(3810,2250)", "(3880,2250)"), wires)

        # Keep the two doglegs on separate x coordinates: sharing one would
        # join JUMP_ERROR to ANY_ERROR before the AND gate.
        self.assertIn(("(3790,1920)", "(3790,2250)"), wires)
        self.assertIn(("(3770,2270)", "(3770,2440)"), wires)

    def test_jump_not_error_reaches_common_pc_select(self):
        root = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ").getroot()
        main = next(c for c in root.findall("circuit") if c.get("name") == "TinyCPUMain")

        any_error = _component_by_label(main, "ANY_ERROR_FOR_JUMP")
        no_error = _component_by_label(main, "INVERT_ANY_ERROR_FOR_JUMP_NOT_ERROR")
        not_error_taken = _component_by_label(main, "JUMP_NOT_ERROR_AND_NO_ERROR")
        control_merge = _component_by_label(main, "JUMP_NOT_ERROR_OR_PREVIOUS_CONTROLS")
        taken_merge = _component_by_label(main, "JUMP_NOT_ERROR_OR_PREVIOUS_TAKEN")
        self.assertEqual(no_error.get("name"), "NOT Gate")
        self.assertEqual(not_error_taken.get("name"), "AND Gate")
        self.assertEqual(control_merge.get("name"), "OR Gate")
        self.assertEqual(taken_merge.get("name"), "OR Gate")

        # (1400,1430) is FetchDecodeControls.JUMP_NOT_ERROR.  Selecting the
        # jump target is independent of the condition; taking it additionally
        # requires the inverse of the combined sticky-error state.
        self.assertTrue(_wire_path_exists(main, "(1400,1430)", "(4230,1970)"))
        self.assertTrue(_wire_path_exists(main, "(1400,1430)", "(4180,2410)"))
        self.assertTrue(_wire_path_exists(main, any_error.get("loc"), "(3810,2440)"))
        self.assertTrue(_wire_path_exists(main, no_error.get("loc"), "(4180,2430)"))
        self.assertTrue(_wire_path_exists(main, "(3950,1940)", "(4230,1950)"))
        self.assertTrue(_wire_path_exists(main, "(3980,2200)", "(4400,2400)"))
        self.assertTrue(_wire_path_exists(main, not_error_taken.get("loc"), "(4400,2420)"))
        self.assertTrue(_wire_path_exists(main, control_merge.get("loc"), "(800,510)"))
        self.assertTrue(_wire_path_exists(main, taken_merge.get("loc"), "(800,530)"))

    def test_sub_operand_reaches_operations_input(self):
        expected = ("(1400,1070)", "(2650,1070)")
        decoder_route = ("(1460,90)", "(1610,90)")
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
            control_wires = {
                (wire.get("from"), wire.get("to"))
                for wire in controls.findall("wire")
            }
            self.assertIn(
                decoder_route, control_wires,
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

    def test_public_decoder_separates_operations_from_argument_kinds(self):
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
            "AND_OPERAND", "OR_OPERAND", "XOR_OPERAND", "LOAD_OPERAND",
            "STORE_OPERAND", "CONST_ARGUMENT", "ADDR_ARGUMENT",
            "ADDR_REG_ARGUMENT", "ADDR_REG_OFFS_ARGUMENT",
        }.issubset(labels))
        self.assertTrue({
            "LOAD_CONST", "LOAD_ADR", "LOAD_ADR_REG", "LOAD_REG_OFF",
            "STORE_ADR", "STORE_ADR_REG", "STORE_REG_OFF",
        }.isdisjoint(labels))

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
        source = ROOT / "hardware/logisim/TinyCPU-8-8.circ"
        before = source.read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "copy.circ"
            autonomous_project(source, target, "TinyCPUMain", (0x123, 0x456))
            root = ET.parse(target).getroot()
            rom = next(c for owner in root.findall("circuit") for c in owner.findall("comp")
                       if c.get("name") == "ROM")
            contents = next(a for a in rom.findall("a") if a.get("name") == "contents")
            self.assertEqual(contents.text, "addr/data: 8 14\n123 456\n")
        self.assertEqual(before, source.read_bytes())

    def test_reserved_opcode_fixture_halts_in_reference_model(self):
        profile = load_profile("tinycpu-8-8")
        case = {"program": "HALT()\n", "raw_words": [0x3F00, 0x2D00]}
        program = _matrix_program(case, profile)
        self.assertEqual(program.instructions[0].mnemonic, "__ILLEGAL__")
        self.assertEqual(_expected_edges(program), 1)
        self.assertEqual(_expected_halt_output(program), "HALTED_WITH_ERROR")

    def test_matrix_reports_progress_before_each_electrical_run(self):
        profile = load_profile("tinycpu-8-8")
        output = StringIO()
        with tempfile.TemporaryDirectory() as directory, patch(
            "tiny_cpu_logisim.run_trace"
        ) as trace, redirect_stdout(output):
            count = run_matrix(
                ROOT / "hardware/logisim/TinyCPU-8-8.circ",
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
        self.assertIn("tinycpu-8-8", lines[0])

    def test_matrix_can_run_two_electrical_fixtures_concurrently(self):
        profile = load_profile("tinycpu-8-8")
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
                ROOT / "hardware/logisim/TinyCPU-8-8.circ",
                profile,
                Path("logisim.jar"),
                "java",
                Path(directory) / "evidence",
                90,
                jobs=2,
            )

        self.assertEqual(trace.call_count, count)

    def test_matrix_error_identifies_the_failing_fixture(self):
        profile = load_profile("tinycpu-8-8")

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
                LogisimError, "tinycpu-8-8 fixture load-const: trace timed out"
            ):
                run_matrix(
                    ROOT / "hardware/logisim/TinyCPU-8-8.circ",
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

    def test_missing_vendored_jar_is_named_when_download_fails(self):
        with tempfile.TemporaryDirectory() as directory, patch(
            "tiny_cpu_logisim.urllib.request.urlretrieve",
            side_effect=OSError("network unavailable"),
        ):
            vendored = Path(directory) / "vendor" / "missing.jar"
            with patch("tiny_cpu_logisim.Path.home", return_value=Path(directory)):
                with self.assertRaisesRegex(LogisimError, str(vendored)):
                    resolve_jar(None, vendored=vendored)


if __name__ == "__main__":
    unittest.main()
