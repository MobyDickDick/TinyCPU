import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tiny_cpu_assembler import assemble
from tiny_cpu_vm import TinyCPU


class AddressRegisterTests(unittest.TestCase):
    def test_memory_load_uses_direct_operand_independently_of_previous_register(self):
        for previous, valid in ((0, False), (30, True)):
            with self.subTest(previous=previous, valid=valid):
                cpu = TinyCPU(assemble("LOAD_CONST(20)\nSTORE_ADDRESS(10)\n"
                                       "LOAD_ADDRESS_REGISTER_ADDRESS(10)\nHALT()\n"))
                cpu.address_register, cpu.address_register_valid = previous, valid
                cpu.memory[30] = (99, True)
                for _ in range(3):
                    cpu.step()
                self.assertEqual((cpu.address_register, cpu.address_register_valid), (20, True))
                self.assertEqual((cpu.accumulator, cpu.accumulator_valid), (20, True))
                self.assertFalse(any(cpu.errors.values()))


if __name__ == "__main__":
    unittest.main()
