#!/usr/bin/env python3
"""Electrically compare FetchDecodeControls with the machine opcode contract."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tiny_cpu_assembler import opcode_table
from tiny_cpu_logisim import LogisimError, resolve_jar
from tiny_cpu_profiles import load_profile

OUTPUTS = (
    "ADD_OPERAND", "SUB_OPERAND", "MUL_OPERAND", "DIV_OPERAND",
    "AND_OPERAND", "OR_OPERAND", "XOR_OPERAND",
    "CONST_ARGUMENT", "ADDR_ARGUMENT", "ADDR_REG_ARGUMENT",
    "ADDR_REG_OFFS_ARGUMENT", "NOT", "JUMP_ADR", "JUMP_ZERO",
    "JUMP_NOT_ZERO", "JUMP_NEGATIVE", "JUMP_ERROR", "JUMP_NOT_ERROR",
    "LOAD_CONST", "LOAD_ADR", "LOAD_ADR_REG", "LOAD_REG_OFF",
    "LD_REG_CONST", "LD_REG_ADR", "STORE_ADR", "STORE_ADR_REG",
    "STORE_REG_OFF",
    "SET_OVF", "SET_DIV0", "SET_ADDR", "SET_INV", "SET_ILL", "SET_INPUT",
    "CLEAR_ERROR", "INPUT", "PRINT", "PRINT_ADR", "HALT", "HALT_ERROR",
    "INVALID_OPERAND",
)

DIRECT = {
    "NOT": "NOT", "JUMP_ADDRESS": "JUMP_ADR", "JUMP_ZERO": "JUMP_ZERO",
    "JUMP_NOT_ZERO": "JUMP_NOT_ZERO", "JUMP_NEGATIVE": "JUMP_NEGATIVE",
    "JUMP_ERROR": "JUMP_ERROR", "JUMP_NOT_ERROR": "JUMP_NOT_ERROR",
    "CLEAR_ERROR": "CLEAR_ERROR", "INPUT": "INPUT", "PRINT": "PRINT",
    "PRINT_ADDRESS": "PRINT_ADR", "HALT": "HALT", "HALT_ERROR": "HALT_ERROR",
    "LOAD_CONST": "LOAD_CONST", "LOAD_ADDRESS": "LOAD_ADR",
    "LOAD_ADDRESS_REGISTER": "LOAD_ADR_REG",
    "LOAD_ADDRESS_REGISTER_PLUS_OFFSET": "LOAD_REG_OFF",
    "LOAD_ADDRESS_REGISTER_CONST": "LD_REG_CONST",
    "LOAD_ADDRESS_REGISTER_ADDRESS": "LD_REG_ADR",
    "STORE_ADDRESS": "STORE_ADR",
    "STORE_ADDRESS_REGISTER": "STORE_ADR_REG",
    "STORE_ADDRESS_REGISTER_PLUS_OFFSET": "STORE_REG_OFF",
}
INTERNAL_ROWS = {
    0x2C: "SET_OVF", 0x2D: "SET_DIV0", 0x2E: "SET_ADDR",
    0x2F: "SET_INV", 0x30: "SET_ILL", 0x31: "SET_INPUT",
}


def expected_row(code: int, opcodes: dict[str, dict[str, object]]) -> dict[str, int]:
    row = dict.fromkeys(OUTPUTS, 0)
    instruction = next((item for item in opcodes.values() if item["code"] == code), None)
    if instruction is None:
        if code in INTERNAL_ROWS:
            row[INTERNAL_ROWS[code]] = 1
        else:
            row["INVALID_OPERAND"] = 1
        return row
    mnemonic = str(instruction["mnemonic"])
    family = mnemonic.split("_", 1)[0]
    arithmetic = family in {"ADD", "SUB", "MUL", "DIV", "AND", "OR", "XOR"}
    if arithmetic:
        row[f"{family}_OPERAND"] = 1
    if mnemonic in DIRECT:
        row[DIRECT[mnemonic]] = 1
    if arithmetic:
        operand = str(instruction["operand"])
        if operand == "value":
            row["CONST_ARGUMENT"] = 1
        elif operand == "address":
            row["ADDR_ARGUMENT"] = 1
        elif mnemonic.endswith("_ADDRESS_REGISTER"):
            row["ADDR_REG_ARGUMENT"] = 1
        elif mnemonic.endswith("_ADDRESS_REGISTER_PLUS_OFFSET"):
            row["ADDR_REG_OFFS_ARGUMENT"] = 1
    return row


def main() -> int:
    explicit = Path(os.environ["LOGISIM_JAR"]) if os.environ.get("LOGISIM_JAR") else None
    if explicit is None:
        local = ROOT / ".venv/Include/logisim-evolution-4.1.0-all.jar"
        explicit = local if local.is_file() else None
    jar = resolve_jar(explicit)
    opcodes = opcode_table(load_profile("tinycpu-16-12"))
    sources = (ROOT / "hardware/logisim/TinyCPU.circ",)
    for source in sources:
        with tempfile.TemporaryDirectory(prefix="tinycpu-decode-") as directory:
            target = Path(directory) / "decode.circ"
            tree = ET.parse(source)
            tree.getroot().find("main").set("name", "FetchDecodeControls")
            tree.write(target, encoding="utf-8", xml_declaration=True)
            result = subprocess.run(
                [os.environ.get("JAVA", "java"), "-jar", str(jar), "-tty", "table", str(target)],
                capture_output=True, text=True, timeout=30, check=False,
            )
        if result.returncode:
            raise LogisimError(f"{source.name}: decode table failed: {result.stderr.strip()}")
        lines = [line.split() for line in result.stdout.splitlines() if line.strip()]
        if (not lines or not lines[0] or lines[0][0] != "OPCODE"
                or not set(OUTPUTS).issubset(lines[0])):
            raise LogisimError(
                f"{source.name}: unexpected decode-table header: {lines[0] if lines else 'empty'}"
            )
        actual_header = lines[0]
        if len(lines) != 65:
            raise LogisimError(f"{source.name}: expected 64 decode rows, got {len(lines) - 1}")
        for code, cells in enumerate(lines[1:]):
            if len(cells) != len(actual_header) or int(cells[0], 2) != code:
                raise LogisimError(f"{source.name}: malformed decode row {code}: {' '.join(cells)}")
            expected = expected_row(code, opcodes)
            actual = dict(zip(actual_header[1:], cells[1:]))
            differences = [name for name in OUTPUTS if actual[name] != str(expected[name])]
            if differences:
                raise LogisimError(
                    f"{source.name}: opcode {code}: mismatched outputs {', '.join(differences)}"
                )
        print(f"{source.name}: electrical decode acceptance passed: "
              "50 opcodes, 6 internal rows, and 8 reserved codes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
