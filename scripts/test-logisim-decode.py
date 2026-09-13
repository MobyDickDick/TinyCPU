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
    "AND_OPERAND", "OR_OPERAND", "XOR_OPERAND", "LOAD_OPERAND",
    "STORE_OPERAND", "CONST_ARGUMENT", "ADDR_ARGUMENT", "ADDR_REG_ARGUMENT",
    "ADDR_REG_OFFS_ARGUMENT", "NOT", "JUMP_ADR", "JUMP_ZERO",
    "JUMP_NOT_ZERO", "JUMP_NEGATIVE", "JUMP_ERROR", "JUMP_NOT_ERROR",
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
}


def expected_row(code: int, opcodes: dict[str, dict[str, object]]) -> dict[str, int]:
    row = dict.fromkeys(OUTPUTS, 0)
    instruction = next((item for item in opcodes.values() if item["code"] == code), None)
    if instruction is None:
        row["INVALID_OPERAND"] = 1
        return row
    mnemonic = str(instruction["mnemonic"])
    family = mnemonic.split("_", 1)[0]
    if family in {"ADD", "SUB", "MUL", "DIV", "AND", "OR", "XOR"}:
        row[f"{family}_OPERAND"] = 1
    elif family == "LOAD" and mnemonic not in {"LOAD_ADDRESS_REGISTER_CONST", "LOAD_ADDRESS_REGISTER_ADDRESS"}:
        row["LOAD_OPERAND"] = 1
    elif family == "STORE":
        row["STORE_OPERAND"] = 1
    if mnemonic in DIRECT:
        row[DIRECT[mnemonic]] = 1
    operand = str(instruction["operand"])
    if operand == "value":
        row["CONST_ARGUMENT"] = 1
    elif operand == "address":
        row["ADDR_ARGUMENT"] = 1
    elif mnemonic.endswith("_ADDRESS_REGISTER") or mnemonic == "STORE_ADDRESS_REGISTER":
        row["ADDR_REG_ARGUMENT"] = 1
    elif mnemonic.endswith("_ADDRESS_REGISTER_PLUS_OFFSET") or mnemonic == "STORE_ADDRESS_REGISTER_PLUS_OFFSET":
        row["ADDR_REG_OFFS_ARGUMENT"] = 1
    return row


def main() -> int:
    explicit = Path(os.environ["LOGISIM_JAR"]) if os.environ.get("LOGISIM_JAR") else None
    if explicit is None:
        local = ROOT / ".venv/Include/logisim-evolution-4.1.0-all.jar"
        explicit = local if local.is_file() else None
    jar = resolve_jar(explicit)
    opcodes = opcode_table(load_profile("tinycpu-16-12"))
    expected_header = ["OPCODE", *OUTPUTS]
    sources = (
        ROOT / "hardware/logisim/TinyCPU.circ",
        ROOT / "hardware/logisim/diagnostics/TinyCPU-FetchDecodeControls.circ",
    )
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
        if not lines or lines[0] != expected_header:
            raise LogisimError(
                f"{source.name}: unexpected decode-table header: {lines[0] if lines else 'empty'}"
            )
        if len(lines) != 65:
            raise LogisimError(f"{source.name}: expected 64 decode rows, got {len(lines) - 1}")
        for code, cells in enumerate(lines[1:]):
            if len(cells) != len(expected_header) or int(cells[0], 2) != code:
                raise LogisimError(f"{source.name}: malformed decode row {code}: {' '.join(cells)}")
            expected = expected_row(code, opcodes)
            actual = dict(zip(OUTPUTS, cells[1:]))
            differences = [name for name in OUTPUTS if actual[name] != str(expected[name])]
            if differences:
                raise LogisimError(
                    f"{source.name}: opcode {code}: mismatched outputs {', '.join(differences)}"
                )
        print(f"{source.name}: electrical decode acceptance passed: "
              "50 opcodes and 14 reserved codes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
