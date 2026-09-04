import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tiny_cpu_assembler import opcode_table
from tiny_cpu_profiles import DEFAULT_PROFILE
from tiny_cpu_systems import load_system_profile


class SystemProfileTests(unittest.TestCase):
    def test_ap18_contracts_are_cross_linked(self):
        system = load_system_profile("tinycpu-peripherals-16-12-v1")
        self.assertEqual(system.base_profile.name, "tinycpu-16-12")
        self.assertEqual(system.output_address, 4095)
        self.assertEqual(system.interrupt_vector, 4080)
        self.assertEqual(system.machine_format, "tinycpu-system-machine-v1")
        self.assertEqual(system.trace_schema, "tinycpu-system-trace-v1")

    def test_system_format_adds_opcodes_without_changing_v1(self):
        system = load_system_profile("tinycpu-peripherals-16-12-v1")
        system_machine = json.loads(system.machine_path.read_text(encoding="utf-8"))
        base = opcode_table(DEFAULT_PROFILE)
        extended = {item["mnemonic"]: item for item in system_machine["opcodes"]}
        self.assertEqual(set(extended).difference(base), {
            "ENABLE_INTERRUPTS", "DISABLE_INTERRUPTS", "RETURN_FROM_INTERRUPT"
        })
        for mnemonic, entry in base.items():
            self.assertEqual(extended[mnemonic], entry)

    def test_default_profile_remains_frozen(self):
        self.assertEqual(DEFAULT_PROFILE.machine_format, "tinycpu-machine-v1")
        self.assertEqual(len(opcode_table(DEFAULT_PROFILE)), 50)

    def test_unknown_system_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown TinyCPU system profile"):
            load_system_profile("tinycpu-peripherals-8-8-v1")


if __name__ == "__main__":
    unittest.main()
