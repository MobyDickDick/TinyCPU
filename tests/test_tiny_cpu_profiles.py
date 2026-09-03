from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from tiny_cpu_assembler import AssemblyError, assemble, encode_program, load_program, opcode_table
from tiny_cpu_debugger import Debugger
from tiny_cpu_profiles import DEFAULT_PROFILE, load_profile


PORTABLE_COUNTDOWN = """LOAD_CONST(3)
loop:
PRINT()
SUB_CONST(1)
JUMP_NOT_ZERO(loop)
HALT()
"""


class ProfileTests(unittest.TestCase):
    def test_default_remains_16_12(self) -> None:
        program = assemble("LOAD_CONST(32767)\nHALT()")
        self.assertEqual(program.profile, DEFAULT_PROFILE)
        self.assertEqual(program.profile.name, "tinycpu-16-12")
        self.assertEqual(program.profile.circuit, "TinyCPU.circ")
        self.assertEqual(program.profile.top_circuit, "TinyCPUMain")
        self.assertEqual(encode_program(program)[0], 0x7fff)

    def test_all_opcodes_roundtrip_in_8_8_format(self) -> None:
        profile = load_profile("tinycpu-8-8")
        lines = []
        for entry in opcode_table(profile).values():
            operand = {"none": "", "value": "1", "offset": "-1",
                       "address": "1", "target": "0"}[entry["operand"]]
            lines.append(f"{entry['mnemonic']}({operand})")
        program = assemble("\n".join(lines), profile)
        words = encode_program(program)
        self.assertEqual(len(words), 50)
        self.assertTrue(all(0 <= word < (1 << 14) for word in words))
        with tempfile.TemporaryDirectory() as directory:
            rom = Path(directory) / "all.rom"
            rom.write_text("v2.0 raw\n" + " ".join(f"{word:x}" for word in words))
            decoded = load_program(rom, profile)
        self.assertEqual(decoded.instructions, program.instructions)

    def test_profile_operand_boundaries_are_not_truncated(self) -> None:
        profile = load_profile("tinycpu-8-8")
        for value in (-128, 127):
            self.assertEqual(assemble(f"LOAD_CONST({value})", profile).instructions[0].operand, value)
        for source in ("LOAD_CONST(-129)", "LOAD_CONST(128)",
                       "LOAD_ADDRESS(-1)", "LOAD_ADDRESS(256)",
                       "ADD_ADDRESS_REGISTER_PLUS_OFFSET(-129)"):
            with self.subTest(source=source), self.assertRaisesRegex(AssemblyError, "tinycpu-8-8"):
                assemble(source, profile)

    def test_portable_debugger_state_matches_both_profiles(self) -> None:
        states = []
        for name in ("tinycpu-16-12", "tinycpu-8-8"):
            debugger = Debugger(assemble(PORTABLE_COUNTDOWN, load_profile(name)))
            state = debugger.continue_()
            self.assertEqual((state["profile"], state["machine_format"]),
                             (name, debugger.cpu.profile.machine_format))
            states.append((state["stop_reason"], state["output"], state["pc"]))
        self.assertEqual(states[0], states[1])

    def test_8_bit_overflow_uses_profile_boundary(self) -> None:
        debugger = Debugger(assemble("LOAD_CONST(127)\nADD_CONST(1)\nHALT()",
                                     load_profile("tinycpu-8-8")))
        debugger.continue_()
        self.assertTrue(debugger.cpu.errors["OVF"])
        self.assertFalse(debugger.cpu.accumulator_valid)


if __name__ == "__main__":
    unittest.main()
