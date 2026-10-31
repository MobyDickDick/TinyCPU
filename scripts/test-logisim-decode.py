#!/usr/bin/env python3
"""Electrically compare FetchDecodeControls with the machine opcode contract."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
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
    "ADDR_REG_OFFS_ARGUMENT", "INVERT", "JUMP_ADR", "JUMP_ZERO",
    "JUMP_NOT_ZERO", "JUMP_NEGATIVE", "JUMP_ERROR", "JUMP_NOT_ERROR",
    "LOAD_CONST", "LOAD_ADR", "LOAD_ADR_REG", "LOAD_REG_OFF",
    "LD_REG_CONST", "LD_REG_ADR", "STORE_ADR", "STORE_ADR_REG",
    "STORE_REG_OFF",
    "SET_OVF", "SET_DIV0", "SET_ADDR", "SET_INV", "SET_ILL", "SET_INPUT",
    "CLEAR_ERROR", "INPUT", "PRINT", "PRINT_ADR", "HALT", "HALT_ERROR",
    "INVALID_OPERAND", "ENABLE_INTERRUPTS_REQUEST",
    "DISABLE_INTERRUPTS_REQUEST", "RETURN_FROM_INTERRUPT_REQUEST", "ACC_MEMORY_REQUEST",
)

DIRECT = {
    "NOT": "INVERT", "JUMP_ADDRESS": "JUMP_ADR", "JUMP_ZERO": "JUMP_ZERO",
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
SYSTEM_ROWS = {
    0x38: "ENABLE_INTERRUPTS_REQUEST",
    0x39: "DISABLE_INTERRUPTS_REQUEST",
    0x3A: "RETURN_FROM_INTERRUPT_REQUEST",
}


def expected_row(code: int, opcodes: dict[str, dict[str, object]]) -> dict[str, int]:
    row = dict.fromkeys(OUTPUTS, 0)
    instruction = next((item for item in opcodes.values() if item["code"] == code), None)
    if instruction is None:
        if code in SYSTEM_ROWS:
            row[SYSTEM_ROWS[code]] = 1
            return row
        if code == 0x3F:
            row["SET_ILL"] = 1
            row["HALT_ERROR"] = 1
        if code in INTERNAL_ROWS:
            row[INTERNAL_ROWS[code]] = 1
        else:
            row["INVALID_OPERAND"] = 1
        return row
    mnemonic = str(instruction["mnemonic"])
    family = mnemonic.split("_", 1)[0]
    arithmetic = family in {"ADD", "SUB", "MUL", "DIV", "AND", "OR", "XOR"}
    # Hold/write requirements diagnosed in AP 22.1's complete core traces.
    if mnemonic in {"STORE_ADDRESS", "STORE_ADDRESS_REGISTER",
                    "STORE_ADDRESS_REGISTER_PLUS_OFFSET", "LOAD_ADDRESS_REGISTER_CONST",
                    "LOAD_ADDRESS_REGISTER_ADDRESS", "CLEAR_ERROR"}:
        row["ACC_WRITE_REQUEST"] = 0
    if mnemonic == "INPUT":
        row["ACC_WRITE_REQUEST"] = 1
    if mnemonic in {"LOAD_ADDRESS", "LOAD_ADDRESS_REGISTER",
                    "LOAD_ADDRESS_REGISTER_PLUS_OFFSET"}:
        row["ACC_MEMORY_REQUEST"] = 1
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


def check_table(output: str, source: Path, opcodes: dict[str, dict[str, object]]) -> None:
    lines = [line.split() for line in output.splitlines() if line.strip()]
    if (not lines or not lines[0] or lines[0][0] != "OPCODE"
            or not (set(OUTPUTS) | {"ACC_WRITE_REQUEST"}).issubset(lines[0])):
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
        differences = [f"{name} (expected {value}, actual {actual[name]})"
                       for name, value in expected.items() if actual[name] != str(value)]
        if differences:
            raise LogisimError(
                f"{source.name}: opcode {code}: mismatched outputs {', '.join(differences)}"
            )


def run_table(tree: ET.ElementTree, jar: Path, evidence: Path) -> str:
    evidence.mkdir(parents=True, exist_ok=True)
    target = evidence / "decode.circ"
    tree.getroot().find("main").set("name", "FetchDecodeControls")
    tree.write(target, encoding="utf-8", xml_declaration=True)
    command = [os.environ.get("JAVA", "java"), "-jar", str(jar),
               "-tty", "table", str(target)]
    (evidence / "command.json").write_text(json.dumps(command, indent=2) + "\n",
                                          encoding="utf-8")
    with (evidence / "stdout.tsv").open("w", encoding="utf-8") as stdout, \
         (evidence / "stderr.txt").open("w", encoding="utf-8") as stderr:
        result = subprocess.run(command, stdout=stdout, stderr=stderr, timeout=30, check=False)
    if result.returncode:
        raise LogisimError(f"{target}: decode table failed; see {evidence / 'stderr.txt'}")
    return (evidence / "stdout.tsv").read_text(encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/decode")
    args = parser.parse_args()
    explicit = Path(os.environ["LOGISIM_JAR"]) if os.environ.get("LOGISIM_JAR") else None
    if explicit is None:
        local = ROOT / ".venv/Include/logisim-evolution-4.1.0-all.jar"
        explicit = local if local.is_file() else None
    jar = resolve_jar(explicit)
    opcodes = opcode_table(load_profile("tinycpu-16-12"))
    sources = (ROOT / "hardware/logisim/TinyCPU.circ",)
    for source in sources:
        original = source.read_bytes()
        tree = ET.parse(source)
        check_table(run_table(tree, jar, args.output / "control"), source, opcodes)
        decoder = tree.getroot().find("circuit[@name='FetchDecodeControls']")
        neutral = next(component for component in decoder.findall("comp[@name='Constant']")
                       if component.find("a[@name='label'][@val='ACC_LD_REG_CONST_DISABLED']")
                       is not None)
        pin = next(component for component in decoder.findall("comp[@name='Pin']")
                   if component.find("a[@name='label'][@val='LD_REG_CONST']") is not None)
        branches = [wire for wire in decoder.findall("wire")
                    if pin.get("loc") in {wire.get("from"), wire.get("to")}]
        if len(branches) != 1:
            raise LogisimError("register-request mutation requires a single decoded source branch")
        branch = branches[0]
        start = branch.get("from") if branch.get("to") == pin.get("loc") else branch.get("to")
        target = neutral.get("loc")
        # Restore the diagnosed branch only in the copy, following the named
        # source junction and gate contact rather than fixed canvas positions.
        bend = f"({start.strip('()').split(',')[0]},{target.strip('()').split(',')[1]})"
        decoder.remove(neutral)
        ET.SubElement(decoder, "wire", {"from": start, "to": bend})
        ET.SubElement(decoder, "wire", {"from": bend, "to": target})
        mutated = run_table(tree, jar, args.output / "register-request-enabled")
        try:
            check_table(mutated, source, opcodes)
        except LogisimError as exc:
            expected = (f"{source.name}: opcode 39: mismatched outputs "
                        "ACC_WRITE_REQUEST (expected 0, actual 1)")
            if str(exc) != expected:
                raise
        else:
            raise LogisimError("re-enabled register-constant load request unexpectedly passed")
        if source.read_bytes() != original:
            raise LogisimError("decoder regression modified the source circuit")
        (args.output / "proof.json").write_text(json.dumps({
            "control_rows_passed": 64, "mutation_rejected": True,
            "opcode": 39, "signal": "ACC_WRITE_REQUEST", "expected": 0, "actual": 1,
            "source_unchanged": True,
        }, indent=2) + "\n", encoding="utf-8")
        print(f"{source.name}: electrical decode acceptance passed: "
              "50 core opcodes, 3 system opcodes, 6 internal rows, "
              "and 5 reserved codes; register-constant write mutation rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
