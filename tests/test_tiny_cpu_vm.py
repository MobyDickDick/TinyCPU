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


class InputContractTests(unittest.TestCase):
    """Fixed architectural expectations for AP 22.1's planned input boundary."""

    def test_input_signed_boundaries_and_invalid_host_values(self):
        for value, expected, valid in ((0, 0, True), (-1, -1, True),
                                       (-32768, -32768, True), (32767, 32767, True),
                                       (-32769, 0, False), (32768, 0, False)):
            with self.subTest(value=value):
                cpu = TinyCPU(assemble("INPUT()\nHALT()\n"), inputs=[value])
                cpu.step()
                self.assertEqual((cpu.pc, cpu.accumulator, cpu.accumulator_valid),
                                 (1, expected, valid))
                self.assertEqual(cpu.errors, {flag: flag == "INPUT" and not valid for flag in cpu.errors})
                self.assertEqual(cpu.inputs, [])
                self.assertFalse(cpu.halted)

    def test_unavailable_input_advances_without_stalling_and_clear_does_not_validate(self):
        cpu = TinyCPU(assemble("LOAD_CONST(7)\nINPUT()\nCLEAR_ERROR()\nHALT()\n"))
        cpu.step()
        cpu.step()
        self.assertEqual((cpu.pc, cpu.accumulator, cpu.accumulator_valid), (2, 0, False))
        self.assertTrue(cpu.errors["INPUT"])
        cpu.step()
        self.assertFalse(any(cpu.errors.values()))
        self.assertEqual((cpu.accumulator, cpu.accumulator_valid), (0, False))

    def test_only_executed_input_consumes_and_repeated_reads_take_one_item_each(self):
        cpu = TinyCPU(assemble("LOAD_CONST(9)\nINPUT()\nPRINT()\nINPUT()\n"
                               "PRINT()\nINPUT()\nHALT()\n"), inputs=[0, -1])
        for remaining in ([0, -1], [-1], [-1], [], []):
            cpu.step()
            self.assertEqual(cpu.inputs, remaining)
        self.assertEqual(cpu.output, [0, -1])
        self.assertFalse(any(cpu.errors.values()))
        cpu.step()
        self.assertEqual((cpu.pc, cpu.accumulator, cpu.accumulator_valid), (6, 0, False))
        self.assertTrue(cpu.errors["INPUT"])

    def test_successful_input_restores_validity_but_keeps_sticky_error(self):
        cpu = TinyCPU(assemble("INPUT()\nINPUT()\nCLEAR_ERROR()\nHALT()\n"), inputs=[32768, 23])
        cpu.step()
        self.assertEqual(cpu.inputs, [23])
        cpu.step()
        self.assertEqual((cpu.accumulator, cpu.accumulator_valid), (23, True))
        self.assertTrue(cpu.errors["INPUT"])
        self.assertFalse(cpu.errors["INV"])
        cpu.step()
        self.assertFalse(any(cpu.errors.values()))
        self.assertEqual((cpu.accumulator, cpu.accumulator_valid), (23, True))

    def test_input_value_and_validity_survive_store_and_load(self):
        cpu = TinyCPU(assemble("INPUT()\nSTORE_ADDRESS(101)\nLOAD_CONST(7)\n"
                               "LOAD_ADDRESS(101)\nPRINT()\nHALT()\n"), inputs=[-32768])
        for _ in range(6):
            cpu.step()
        self.assertEqual(cpu.memory[101], (-32768, True))
        self.assertEqual((cpu.accumulator, cpu.accumulator_valid), (-32768, True))
        self.assertEqual(cpu.output, [-32768])
        self.assertFalse(any(cpu.errors.values()))
        self.assertTrue(cpu.halted)


if __name__ == "__main__":
    unittest.main()
