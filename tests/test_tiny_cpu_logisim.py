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
            expected = (("(2280,1310)", "(2530,1310)") if name == "TinyCPU.circ"
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

    def test_add_operand_reaches_operations_input(self):
        expected = ("(1270,930)", "(2520,930)")
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
            operation_pins = {
                attribute.get("val"): component.get("loc")
                for component in operations.findall("comp")
                if component.get("name") == "Pin"
                for attribute in component.findall("a")
                if attribute.get("name") == "label"
            }
            self.assertEqual(operation_pins.get("ADD_OPERAND"), "(330,450)")
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

    def test_sub_operand_reaches_operations_input(self):
        expected = ("(1270,950)", "(2520,950)")
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
            operation_pins = {
                attribute.get("val"): component.get("loc")
                for component in operations.findall("comp")
                if component.get("name") == "Pin"
                for attribute in component.findall("a")
                if attribute.get("name") == "label"
            }
            self.assertEqual(operation_pins.get("SUB_OPERAND"), "(330,470)")
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
