"""Assembler for the versioned TinyCPU instruction set.

The assembler deliberately keeps source locations in :class:`Program`; they
are optional debugger metadata and never change the encoded machine word.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from tiny_cpu_profiles import DEFAULT_PROFILE, Profile


ROOT = Path(__file__).resolve().parents[1]
CALL = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*\((.*?)\)\s*$")
NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
BUILTIN_ALIASES = {
    "LDC": "LOAD_CONST",
    "LDA": "LOAD_ADDRESS",
    "STA": "STORE_ADDRESS",
    "ADC": "ADD_CONST",
    "ADA": "ADD_ADDRESS",
    "JMP": "JUMP_ADDRESS",
    "JZ": "JUMP_ZERO",
    "JNZ": "JUMP_NOT_ZERO",
    "JNEG": "JUMP_NEGATIVE",
    "JER": "JUMP_ERROR",
    "CER": "CLEAR_ERROR",
    "HLT": "HALT",
}


class AssemblyError(ValueError):
    """A source program cannot be assembled."""


@dataclass(frozen=True)
class Instruction:
    mnemonic: str
    operand: int = 0


@dataclass(frozen=True)
class SourceLocation:
    line: int
    text: str
    label: str | None = None


@dataclass(frozen=True)
class Program:
    instructions: tuple[Instruction, ...]
    source_map: dict[int, SourceLocation]
    labels: dict[str, int]
    profile: Profile = DEFAULT_PROFILE


def opcode_table(profile: Profile = DEFAULT_PROFILE) -> dict[str, dict[str, object]]:
    data = json.loads(profile.machine_path.read_text(encoding="utf-8"))
    return {entry["mnemonic"]: entry for entry in data["opcodes"]}


def _lines(source: str) -> list[tuple[int, str]]:
    result = []
    for number, raw in enumerate(source.splitlines(), 1):
        text = re.split(r";|//", raw, maxsplit=1)[0].strip()
        if text:
            result.append((number, text))
    return result


def assemble(source: str, profile: Profile = DEFAULT_PROFILE) -> Program:
    """Assemble source text and retain an address-to-source mapping."""
    table = opcode_table(profile)
    aliases: dict[str, str | int] = {}
    labels: dict[str, int] = {}
    pending: list[str] = []
    statements: list[tuple[int, str, str | None]] = []
    pc = 0
    for line, text in _lines(source):
        if text.endswith(":"):
            label = text[:-1].strip()
            if not NAME.fullmatch(label) or label in labels or label in aliases:
                raise AssemblyError(f"line {line}: invalid or duplicate label {label!r}")
            labels[label] = pc
            pending.append(label)
        elif ":=" in text:
            name, value = (part.strip() for part in text.split(":=", 1))
            if not NAME.fullmatch(name) or name in aliases or name in labels:
                raise AssemblyError(f"line {line}: invalid or duplicate alias {name!r}")
            try:
                aliases[name] = int(value, 0)
            except ValueError:
                aliases[name] = value
        else:
            statements.append((line, text, pending[-1] if pending else None))
            pending.clear()
            pc += 1

    instructions = []
    source_map = {}
    for address, (line, text, label) in enumerate(statements):
        match = CALL.fullmatch(text)
        if not match:
            raise AssemblyError(f"line {line}: expected INSTRUCTION(operand)")
        name, operand_text = match.groups()
        # Source-defined aliases deliberately take precedence so existing
        # programs can redefine a shorthand without shadowing a canonical
        # instruction name.
        name = str(aliases.get(name, BUILTIN_ALIASES.get(name, name)))
        entry = table.get(name)
        if entry is None:
            raise AssemblyError(f"line {line}: unknown instruction {name!r}")
        kind = entry["operand"]
        if kind == "none":
            if operand_text.strip():
                raise AssemblyError(f"line {line}: {name} takes no operand")
            operand = 0
        else:
            token = operand_text.strip()
            if not token:
                raise AssemblyError(f"line {line}: {name} requires an operand")
            value = labels.get(token, aliases.get(token, token))
            try:
                operand = int(value, 0) if isinstance(value, str) else value
            except (TypeError, ValueError):
                raise AssemblyError(f"line {line}: unknown operand {token!r}") from None
            if kind in {"address", "target"} or name == "LOAD_ADDRESS_REGISTER_CONST":
                minimum, maximum = 0, profile.memory_size - 1
            else:
                minimum, maximum = profile.signed_min, profile.signed_max
            if not minimum <= operand <= maximum:
                raise AssemblyError(
                    f"line {line}: {kind} {operand} is outside {minimum}..{maximum} "
                    f"for profile {profile.name}"
                )
        instructions.append(Instruction(name, operand))
        source_map[address] = SourceLocation(line, text, label)
    return Program(tuple(instructions), source_map, labels, profile)


def load_program(path: Path, profile: Profile = DEFAULT_PROFILE) -> Program:
    """Load assembly or a Logisim ``v2.0 raw`` ROM image."""
    if path.suffix != ".rom":
        return assemble(path.read_text(encoding="utf-8"), profile)
    tokens = path.read_text(encoding="utf-8").split()
    if tokens[:2] != ["v2.0", "raw"]:
        raise AssemblyError(f"{path}: expected 'v2.0 raw' ROM header")
    by_code = {entry["code"]: entry for entry in opcode_table(profile).values()}
    instructions = []
    for address, token in enumerate(tokens[2:]):
        try:
            word = int(token, 16)
            if word >= 1 << profile.word_bits:
                raise ValueError
            entry = by_code[word >> profile.data_bits]
        except (ValueError, KeyError):
            raise AssemblyError(f"{path}: invalid word at address {address}: {token!r}") from None
        operand = word & profile.data_mask
        if entry["operand"] in {"value", "offset"} and entry["mnemonic"] != "LOAD_ADDRESS_REGISTER_CONST":
            sign_bit = 1 << (profile.data_bits - 1)
            operand = operand - (1 << profile.data_bits) if operand & sign_bit else operand
        instructions.append(Instruction(entry["mnemonic"], operand))
    return Program(tuple(instructions), {}, {}, profile)


def encode_program(program: Program) -> tuple[int, ...]:
    """Encode a program using the format selected during assembly."""
    table = opcode_table(program.profile)
    return tuple((int(table[item.mnemonic]["code"]) << program.profile.data_bits)
                 | (item.operand & program.profile.data_mask)
                 for item in program.instructions)
