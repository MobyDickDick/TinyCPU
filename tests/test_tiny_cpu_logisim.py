import os
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tiny_cpu_logisim import (
    ROOT,
    LogisimError,
    _expected_edges,
    _matrix_program,
    autonomous_project,
    parse_args,
    resolve_jar,
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
            self.assertNotIn("HALTED", labels)

    def test_source_project_is_not_modified(self):
        source = ROOT / "hardware/logisim/TinyCPU-8-8.circ"
        before = source.read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            autonomous_project(source, Path(directory) / "copy.circ", "TinyCPUMain")
        self.assertEqual(before, source.read_bytes())

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
