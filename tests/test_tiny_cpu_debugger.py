from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from tiny_cpu_assembler import AssemblyError, assemble
from tiny_cpu_debugger import Debugger


COUNTDOWN = """counter := 100
LOAD_CONST(3)
loop:
PRINT()
SUB_CONST(1)
STORE_ADDRESS(counter)
JUMP_NOT_ZERO(loop)
HALT()
"""


class DebuggerTests(unittest.TestCase):
    def test_label_breakpoint_stops_before_each_visit(self) -> None:
        debugger = Debugger(assemble(COUNTDOWN))
        debugger.add_breakpoint("loop")
        self.assertEqual(debugger.continue_()["pc"], 1)
        observed = []
        for _ in range(3):
            debugger.step()
            state = debugger.continue_()
            observed.append((state["stop_reason"], state["pc"]))
        self.assertEqual(observed, [("breakpoint", 1), ("breakpoint", 1), ("halt", 6)])

    def test_steps_match_complete_normal_run(self) -> None:
        stepped = Debugger(assemble(COUNTDOWN))
        while not stepped.cpu.halted: stepped.step()
        normal = Debugger(assemble(COUNTDOWN)); normal.continue_()
        self.assertEqual(stepped.cpu, normal.cpu)

    def test_invalid_breakpoints_are_rejected(self) -> None:
        debugger = Debugger(assemble("HALT()"))
        with self.assertRaisesRegex(ValueError, "unknown label"): debugger.add_breakpoint("missing")
        with self.assertRaisesRegex(ValueError, "outside"): debugger.add_breakpoint(1)

    def test_all_flags_and_invalid_states_are_visible(self) -> None:
        debugger = Debugger(assemble("HALT()"))
        debugger.cpu.address_register_valid = False
        debugger.cpu.memory[12] = (0, False)
        for flag in debugger.cpu.errors: debugger.cpu.errors[flag] = True
        state = debugger.snapshot("step")
        self.assertFalse(state["accumulator"]["valid"])
        self.assertFalse(state["address_register"]["valid"])
        self.assertTrue(all(state["errors"].values()))
        self.assertFalse(debugger.read_memory(12)[0]["valid"])

    def test_json_is_byte_stable(self) -> None:
        root = Path(__file__).parents[1]
        command = [sys.executable, str(root / "src/tiny_cpu_debugger.py"),
                   str(root / "hardware/logisim/ap5_countdown.tcpu"), "--json"]
        first = subprocess.run(command, check=True, capture_output=True, text=True).stdout
        second = subprocess.run(command, check=True, capture_output=True, text=True).stdout
        self.assertEqual(first, second)
        self.assertEqual(json.loads(first)["stop_reason"], "halt")

    def test_assembler_source_map_and_errors(self) -> None:
        program = assemble(COUNTDOWN)
        self.assertEqual(program.source_map[1].label, "loop")
        with self.assertRaisesRegex(AssemblyError, "requires an operand"):
            assemble("ADD_ADDRESS()")

    def test_labels_and_aliases_cannot_redefine_each_other(self) -> None:
        with self.assertRaisesRegex(AssemblyError, "duplicate label"):
            assemble("value := 1\nvalue:\nHALT()")
        with self.assertRaisesRegex(AssemblyError, "duplicate alias"):
            assemble("value:\nvalue := 1\nHALT()")


if __name__ == "__main__": unittest.main()
