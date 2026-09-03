import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tiny_cpu_logisim import ROOT, autonomous_project, resolve_jar


class LogisimLauncherTests(unittest.TestCase):
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

    def test_vendored_jar_is_preferred_without_an_override(self):
        with tempfile.TemporaryDirectory() as directory:
            vendored = Path(directory) / "vendor/logisim-evolution-4.1.0-all.jar"
            vendored.parent.mkdir()
            vendored.write_bytes(b"test jar")
            self.assertEqual(resolve_jar(None, vendored=vendored), vendored)


if __name__ == "__main__":
    unittest.main()
