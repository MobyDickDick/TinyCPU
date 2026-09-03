#!/usr/bin/env python3
"""Symbolic step/continue debugger for the TinyCPU Python reference model."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tiny_cpu_assembler import AssemblyError, Program, load_program
from tiny_cpu_vm import FLAGS, TinyCPU


SCHEMA_VERSION = 1
STOP_REASONS = ("breakpoint", "step", "halt", "halt_error", "step_limit")


class DebuggerError(ValueError):
    """Invalid debugger configuration or command."""


class Debugger:
    def __init__(self, program: Program, *, inputs: list[int] | None = None,
                 step_limit: int = 10000) -> None:
        self.cpu = TinyCPU(program, list(inputs or []))
        self.program = program
        self.step_limit = step_limit
        self.steps = 0
        self.breakpoints: set[int] = set()
        self._changes: set[int] = set()

    def resolve_breakpoint(self, value: str | int) -> int:
        if isinstance(value, str) and value in self.program.labels:
            address = self.program.labels[value]
        else:
            try: address = int(value)
            except (TypeError, ValueError):
                raise DebuggerError(f"unknown label {value!r}") from None
        if not 0 <= address < len(self.program.instructions):
            raise DebuggerError(f"breakpoint address {address} is outside the loaded program")
        return address

    def add_breakpoint(self, value: str | int) -> None:
        self.breakpoints.add(self.resolve_breakpoint(value))

    def remove_breakpoint(self, value: str | int) -> None:
        self.breakpoints.discard(self.resolve_breakpoint(value))

    def _terminal_reason(self) -> str | None:
        if self.cpu.halted: return "halt_error" if self.cpu.halt_error else "halt"
        if self.steps >= self.step_limit: return "step_limit"
        return None

    def step(self) -> dict[str, object]:
        reason = self._terminal_reason()
        if reason is None:
            self._changes |= self.cpu.step()
            self.steps += 1
            reason = self._terminal_reason() or "step"
        return self.snapshot(reason)

    def continue_(self) -> dict[str, object]:
        reason = self._terminal_reason()
        if reason is not None: return self.snapshot(reason)
        while True:
            if self.cpu.pc in self.breakpoints:
                return self.snapshot("breakpoint")
            self._changes |= self.cpu.step()
            self.steps += 1
            reason = self._terminal_reason()
            if reason is not None: return self.snapshot(reason)

    def snapshot(self, reason: str) -> dict[str, object]:
        if reason not in STOP_REASONS: raise DebuggerError(f"invalid stop reason {reason}")
        pc = self.cpu.pc
        location = self.program.source_map.get(pc)
        result: dict[str, object] = {
            "schema_version": SCHEMA_VERSION,
            "stop_reason": reason,
            "steps": self.steps,
            "pc": pc,
            "source": None if location is None else {
                "line": location.line, "text": location.text, "label": location.label},
            "accumulator": {"value": self.cpu.accumulator, "valid": self.cpu.accumulator_valid},
            "address_register": {"value": self.cpu.address_register,
                                 "valid": self.cpu.address_register_valid},
            "zero": self.cpu.accumulator_valid and self.cpu.accumulator == 0,
            "negative": self.cpu.accumulator_valid and self.cpu.accumulator < 0,
            "errors": {name: self.cpu.errors[name] for name in FLAGS},
            "halted": self.cpu.halted,
            "output": list(self.cpu.output),
            "memory_changes": [
                {"address": address, "value": self.cpu.memory[address][0],
                 "valid": self.cpu.memory[address][1]}
                for address in sorted(self._changes)
            ],
        }
        self._changes.clear()
        return result

    def read_memory(self, start: int, end: int | None = None) -> list[dict[str, object]]:
        end = start if end is None else end
        if not 0 <= start <= end < 4096:
            raise DebuggerError("memory range must be within 0..4095")
        return [{"address": address, "value": self.cpu.memory.get(address, (0, False))[0],
                 "valid": self.cpu.memory.get(address, (0, False))[1]}
                for address in range(start, end + 1)]


def format_text(state: dict[str, object]) -> str:
    acc, adr = state["accumulator"], state["address_register"]
    errors = [name for name, set_ in state["errors"].items() if set_]
    return (f"stop={state['stop_reason']} pc={state['pc']} steps={state['steps']}\n"
            f"ACC={acc['value']} valid={str(acc['valid']).lower()} "
            f"AR={adr['value']} valid={str(adr['valid']).lower()} "
            f"ZERO={str(state['zero']).lower()} NEGATIVE={str(state['negative']).lower()}\n"
            f"errors={','.join(errors) if errors else '-'} output={state['output']}\n"
            f"memory_changes={state['memory_changes']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Debug a TinyCPU program symbolically")
    parser.add_argument("program", type=Path, help=".tcpu source or v2.0 raw .rom image")
    parser.add_argument("--breakpoint", "-b", action="append", default=[], metavar="ADDRESS|LABEL")
    parser.add_argument("--step", action="store_true", help="execute exactly one instruction")
    parser.add_argument("--json", action="store_true", help="emit stable machine-readable JSON")
    parser.add_argument("--input", action="append", type=int, default=[])
    parser.add_argument("--step-limit", type=int, default=10000)
    args = parser.parse_args(argv)
    try:
        debugger = Debugger(load_program(args.program), inputs=args.input, step_limit=args.step_limit)
        for breakpoint in args.breakpoint: debugger.add_breakpoint(breakpoint)
        state = debugger.step() if args.step else debugger.continue_()
    except (OSError, AssemblyError, DebuggerError) as exc:
        parser.error(str(exc))
    print(json.dumps(state, sort_keys=True, separators=(",", ":")) if args.json else format_text(state))
    return 1 if state["stop_reason"] in {"halt_error", "step_limit"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
