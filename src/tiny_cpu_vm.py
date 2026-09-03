"""Pausable 16/12-bit TinyCPU reference execution core."""

from __future__ import annotations

from dataclasses import dataclass, field

from tiny_cpu_assembler import Instruction, Program


FLAGS = ("OVF", "DIV0", "ADDR", "INV", "ILL", "INPUT")


def signed(value: int, bits: int = 16) -> int:
    mask = (1 << bits) - 1
    value &= mask
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


@dataclass
class TinyCPU:
    program: Program
    inputs: list[int] = field(default_factory=list)
    pc: int = 0
    accumulator: int = 0
    accumulator_valid: bool = False
    address_register: int = 0
    address_register_valid: bool = False
    memory: dict[int, tuple[int, bool]] = field(default_factory=dict)
    errors: dict[str, bool] = field(default_factory=lambda: {name: False for name in FLAGS})
    output: list[int] = field(default_factory=list)
    halted: bool = False
    halt_error: bool = False

    @property
    def profile(self):
        return self.program.profile

    def _error(self, name: str) -> None:
        self.errors[name] = True

    def _address(self, instruction: Instruction) -> int | None:
        name, operand = instruction.mnemonic, signed(instruction.operand, self.profile.data_bits)
        if "ADDRESS_REGISTER" in name and not name.startswith("LOAD_ADDRESS_REGISTER_CONST"):
            if not self.address_register_valid:
                self._error("INV")
                return None
            address = self.address_register
            if "PLUS_OFFSET" in name:
                address += operand
        else:
            address = instruction.operand
        if not 0 <= address < self.profile.memory_size:
            self._error("ADDR")
            return None
        return address

    def _source(self, instruction: Instruction) -> tuple[int, bool]:
        if instruction.mnemonic.endswith("_CONST"):
            return signed(instruction.operand, self.profile.data_bits), True
        address = self._address(instruction)
        return self.memory.get(address, (0, False)) if address is not None else (0, False)

    def _write_accumulator(self, value: int, valid: bool) -> None:
        self.accumulator = signed(value, self.profile.data_bits) if valid else 0
        self.accumulator_valid = valid

    def step(self) -> set[int]:
        """Execute exactly one instruction and return changed memory addresses."""
        if self.halted:
            return set()
        if not 0 <= self.pc < len(self.program.instructions):
            self._error("ADDR"); self.halted = self.halt_error = True
            return set()
        instruction = self.program.instructions[self.pc]
        self.pc += 1
        name = instruction.mnemonic
        changed: set[int] = set()
        if name.startswith("LOAD_") and not name.startswith("LOAD_ADDRESS_REGISTER_"):
            value, valid = self._source(instruction)
            if not valid: self._error("INV")
            self._write_accumulator(value, valid)
        elif name == "LOAD_ADDRESS_REGISTER_CONST":
            value = instruction.operand
            valid = 0 <= value < self.profile.memory_size
            self.address_register, self.address_register_valid = (value if valid else 0), valid
            if not valid: self._error("ADDR")
        elif name == "LOAD_ADDRESS_REGISTER_ADDRESS":
            address = self._address(instruction)
            value, valid = self.memory.get(address, (0, False)) if address is not None else (0, False)
            valid = valid and 0 <= value < self.profile.memory_size
            self.address_register, self.address_register_valid = (value if valid else 0), valid
            if not valid: self._error("INV" if address is not None else "ADDR")
        elif name.startswith("STORE_"):
            address = self._address(instruction)
            if address is not None:
                self.memory[address] = (self.accumulator if self.accumulator_valid else 0, self.accumulator_valid)
                changed.add(address)
                if not self.accumulator_valid: self._error("INV")
        elif name == "NOT":
            if self.accumulator_valid: self._write_accumulator(~self.accumulator, True)
            else: self._error("INV")
        elif name.split("_", 1)[0] in {"ADD", "SUB", "MUL", "DIV", "AND", "OR", "XOR"}:
            operation = name.split("_", 1)[0]
            right, valid = self._source(instruction)
            if not self.accumulator_valid or not valid:
                self._error("INV"); self._write_accumulator(0, False)
            elif operation == "DIV" and right == 0:
                self._error("DIV0"); self._write_accumulator(0, False)
            else:
                left = self.accumulator
                result = {"ADD": lambda: left + right, "SUB": lambda: left - right,
                          "MUL": lambda: left * right, "DIV": lambda: int(left / right),
                          "AND": lambda: left & right, "OR": lambda: left | right,
                          "XOR": lambda: left ^ right}[operation]()
                if operation in {"ADD", "SUB", "MUL"} and not self.profile.signed_min <= result <= self.profile.signed_max:
                    self._error("OVF"); self._write_accumulator(0, False)
                else: self._write_accumulator(result, True)
        elif name.startswith("JUMP_"):
            take = name == "JUMP_ADDRESS"
            take |= name == "JUMP_ZERO" and self.accumulator_valid and self.accumulator == 0
            take |= name == "JUMP_NOT_ZERO" and self.accumulator_valid and self.accumulator != 0
            take |= name == "JUMP_NEGATIVE" and self.accumulator_valid and self.accumulator < 0
            take |= name == "JUMP_ERROR" and any(self.errors.values())
            take |= name == "JUMP_NOT_ERROR" and not any(self.errors.values())
            if take:
                target = instruction.operand
                if 0 <= target < len(self.program.instructions): self.pc = target
                else: self._error("ADDR"); self.halted = self.halt_error = True
        elif name == "CLEAR_ERROR": self.errors = {flag: False for flag in FLAGS}
        elif name == "INPUT":
            if self.inputs:
                value = self.inputs.pop(0)
                if self.profile.signed_min <= value <= self.profile.signed_max: self._write_accumulator(value, True)
                else: self._error("INPUT"); self._write_accumulator(0, False)
            else: self._error("INPUT"); self._write_accumulator(0, False)
        elif name in {"PRINT", "PRINT_ADDRESS"}:
            value, valid = ((self.accumulator, self.accumulator_valid) if name == "PRINT"
                            else self.memory.get(self._address(instruction), (0, False)))
            if valid: self.output.append(value)
            else: self._error("INV")
        elif name == "HALT": self.halted = True
        elif name == "HALT_ERROR": self.halted = self.halt_error = True
        else: self._error("ILL"); self.halted = self.halt_error = True
        return changed
