import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tiny_cpu_assembler import (AssemblyError, Instruction, Program, assemble,
                                encode_program, opcode_table)
from tiny_cpu_profiles import DEFAULT_PROFILE
from tiny_cpu_systems import load_system_profile
from tiny_cpu_debugger import Debugger
from tiny_cpu_vm import TinyCPU


class SystemProfileTests(unittest.TestCase):
    def test_ap18_contracts_are_cross_linked(self):
        system = load_system_profile("tinycpu-peripherals-16-12-v1")
        self.assertEqual(system.base_profile.name, "tinycpu-16-12")
        self.assertEqual(system.output_address, 4095)
        self.assertEqual(system.interrupt_vector, 4080)
        self.assertEqual(system.machine_format, "tinycpu-system-machine-v1")
        self.assertEqual(system.trace_schema, "tinycpu-system-trace-v1")
        self.assertEqual(system.circuit_path.name, "TinyCPU-Peripherals.circ")
        self.assertEqual(system.top_circuit, "TinyCPUSystemMain")
        self.assertEqual(system.public_pins["INTERRUPT_REQUEST"], {
            "direction": "input", "bits": 1
        })
        self.assertEqual(system.public_pins["OUTPUT_PORT_VALUE"], {
            "direction": "output", "bits": 16
        })

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

    def test_system_instructions_require_explicit_selection(self):
        source = "ENABLE_INTERRUPTS()\nDISABLE_INTERRUPTS()\nRETURN_FROM_INTERRUPT()"
        with self.assertRaisesRegex(AssemblyError, "unknown instruction"):
            assemble(source)
        system = load_system_profile("tinycpu-peripherals-16-12-v1")
        program = assemble(source, system.base_profile, system)
        self.assertEqual([item.mnemonic for item in program.instructions], [
            "ENABLE_INTERRUPTS", "DISABLE_INTERRUPTS", "RETURN_FROM_INTERRUPT"
        ])
        self.assertEqual([word >> 16 for word in encode_program(program)], [50, 51, 52])

    def test_output_port_is_not_written_to_ram(self):
        system = load_system_profile("tinycpu-peripherals-16-12-v1")
        cpu = TinyCPU(assemble(
            "LOAD_CONST(23)\nSTORE_ADDRESS(4095)\nLOAD_ADDRESS(4095)\nHALT()",
            system.base_profile, system,
        ))
        while not cpu.halted:
            cpu.step()
        self.assertEqual((cpu.output_port, cpu.output_port_valid), (23, True))
        self.assertEqual((cpu.accumulator, cpu.accumulator_valid), (23, True))
        self.assertNotIn(system.output_address, cpu.memory)

    def test_masked_edge_remains_pending_and_interrupt_returns(self):
        system = load_system_profile("tinycpu-peripherals-16-12-v1")
        instructions = [Instruction("HALT") for _ in range(system.interrupt_vector + 2)]
        instructions[0:2] = [Instruction("ENABLE_INTERRUPTS"), Instruction("HALT")]
        instructions[system.interrupt_vector:system.interrupt_vector + 2] = [
            Instruction("LOAD_CONST", 7), Instruction("RETURN_FROM_INTERRUPT")]
        cpu = TinyCPU(Program(tuple(instructions), {}, {}, system.base_profile, system))

        cpu.step(interrupt_request=True)
        self.assertTrue(cpu.interrupt_pending)
        cpu.step(interrupt_request=False)
        self.assertTrue(cpu.in_interrupt_handler)
        self.assertEqual(cpu.return_address, 1)
        cpu.step()
        cpu.step()
        self.assertEqual(cpu.pc, 1)
        self.assertTrue(cpu.interrupts_enabled)
        self.assertFalse(cpu.return_address_valid)

    def test_interrupt_vector_error_illegal_return_and_reset(self):
        system = load_system_profile("tinycpu-peripherals-16-12-v1")
        vector_error = TinyCPU(assemble("ENABLE_INTERRUPTS()\nHALT()",
                                        system.base_profile, system))
        vector_error.step()
        vector_error.step(interrupt_request=True)
        self.assertTrue(vector_error.errors["ADDR"])
        self.assertTrue(vector_error.halt_error)

        illegal = TinyCPU(assemble("RETURN_FROM_INTERRUPT()", system.base_profile, system))
        illegal.step()
        self.assertTrue(illegal.errors["ILL"])
        self.assertTrue(illegal.halt_error)
        illegal.output_port = 9
        illegal.output_port_valid = illegal.interrupt_pending = True
        illegal.step(reset=True)
        self.assertFalse(illegal.halted)
        self.assertEqual((illegal.output_port, illegal.output_port_valid), (0, False))
        self.assertFalse(illegal.interrupt_pending)

    def test_debugger_uses_extended_trace_shape(self):
        system = load_system_profile("tinycpu-peripherals-16-12-v1")
        state = Debugger(assemble("HALT()", system.base_profile, system)).snapshot("step")
        self.assertEqual(state["schema_version"], 2)
        self.assertEqual(state["system"], system.name)
        self.assertEqual(state["machine_format"], system.machine_format)
        self.assertEqual(state["output_port"], {"value": 0, "valid": False})
        self.assertEqual(state["interrupt"], {
            "enabled": False, "pending": False, "in_handler": False
        })


if __name__ == "__main__":
    unittest.main()
