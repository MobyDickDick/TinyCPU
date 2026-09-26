import importlib.util
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/check-logisim-electrical.py"
SPEC = importlib.util.spec_from_file_location("logisim_electrical_check", MODULE_PATH)
CHECK = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(CHECK)


class ElectricalCheckTests(unittest.TestCase):
    @patch.object(CHECK.subprocess, "run")
    def test_accepts_defined_multibit_values(self, run):
        run.return_value = subprocess.CompletedProcess(
            [], 0, "A BUS VALID\n0 0x00e0 1\n1 0x00ff 0\n"
        )
        self.assertEqual(CHECK.evaluate(Path("machine.circ"), Path("logisim.jar")), [])

    @patch.object(CHECK.subprocess, "run")
    def test_rejects_only_standalone_error_and_unknown_values(self, run):
        run.return_value = subprocess.CompletedProcess(
            [], 0, "A VALUE VALID\n0 E 0\n1 0x00e0 U\n"
        )
        self.assertEqual(
            CHECK.evaluate(Path("machine.circ"), Path("logisim.jar")),
            ["0 E 0", "1 0x00e0 U"],
        )

    @patch.object(CHECK.subprocess, "run")
    def test_rejects_a_missing_truth_table(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "A VALUE\n")
        with self.assertRaisesRegex(RuntimeError, "no truth-table rows"):
            CHECK.evaluate(Path("machine.circ"), Path("logisim.jar"))

    @patch.object(CHECK.subprocess, "run")
    def test_reports_logisim_failure(self, run):
        run.return_value = subprocess.CompletedProcess([], 2, "load failed\n")
        with self.assertRaisesRegex(RuntimeError, "status 2"):
            CHECK.evaluate(Path("machine.circ"), Path("logisim.jar"))


if __name__ == "__main__":
    unittest.main()
