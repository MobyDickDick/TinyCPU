#!/usr/bin/env python3
"""Electrical address-validity regression, including rejected fault injections."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from tiny_cpu_assembler import Instruction, Program, encode_program
from tiny_cpu_core_trace import CoreMismatch, expected_trace
from tiny_cpu_logisim import LogisimError, resolve_jar, run_core_comparison
from tiny_cpu_profiles import load_profile


def raw_program(text, profile):
    """Exercise malformed machine operands intentionally rejected by the assembler."""
    instructions = []
    for line in text.splitlines():
        name, operand = line.rstrip(")").split("(")
        instructions.append(Instruction(name, int(operand or 0) & profile.data_mask))
    return Program(tuple(instructions), {}, {}, profile)


def cases():
    result = {}
    # Valid RAM at zero makes an erroneously allowed read observable as well.
    prefix = "LOAD_CONST(9)\nSTORE_ADDRESS(0)\nLOAD_CONST(7)\n"
    for suffix in ("ADDRESS_REGISTER()", "ADDRESS_REGISTER_PLUS_OFFSET(1)"):
        for op in ("LOAD", "STORE", "ADD", "SUB", "MUL", "DIV", "AND", "OR", "XOR"):
            result[f"uninitialized-{op.lower()}-{suffix.split('(')[0].lower()}"] = (
                prefix + f"{op}_{suffix}\nHALT()\n")
    result.update({
        "direct-with-invalid-register": prefix + "LOAD_ADDRESS(0)\nADD_ADDRESS(0)\nHALT()\n",
        "valid-zero": "LOAD_ADDRESS_REGISTER_CONST(0)\nLOAD_CONST(7)\nSTORE_ADDRESS_REGISTER()\nLOAD_ADDRESS_REGISTER()\nHALT()\n",
        "invalid-memory-load": "LOAD_ADDRESS_REGISTER_CONST(20)\nLOAD_ADDRESS_REGISTER_ADDRESS(10)\nCLEAR_ERROR()\nLOAD_CONST(7)\nSTORE_ADDRESS_REGISTER()\nHALT()\n",
        "recovery": "LOAD_ADDRESS_REGISTER_ADDRESS(10)\nCLEAR_ERROR()\nLOAD_ADDRESS_REGISTER_CONST(0)\nLOAD_CONST(7)\nSTORE_ADDRESS_REGISTER()\nHALT()\n",
    })
    for value in (0, 4095, 4096, -1):
        result[f"constant-{value}"] = f"LOAD_ADDRESS_REGISTER_CONST({value})\nHALT()\n"
        result[f"memory-{value}"] = (f"LOAD_CONST({value})\nSTORE_ADDRESS(10)\n"
                                    "LOAD_ADDRESS_REGISTER_ADDRESS(10)\nHALT()\n")
    for base, offset in ((0, -1), (4095, 1), (1, -1), (4094, 1)):
        result[f"offset-{base}-{offset}"] = (f"LOAD_ADDRESS_REGISTER_CONST({base})\n"
            f"LOAD_CONST(7)\nSTORE_ADDRESS_REGISTER_PLUS_OFFSET({offset})\nHALT()\n")
    for op in ("LOAD", "STORE", "ADD", "PRINT"):
        result[f"direct-range-{op.lower()}"] = f"LOAD_CONST(7)\n{op}_ADDRESS(4096)\nHALT()\n"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/address-validity")
    parser.add_argument("--project", type=Path, default=ROOT / "hardware/logisim/TinyCPU.circ")
    parser.add_argument("--java", default=os.environ.get("JAVA", "java"))
    parser.add_argument("--jar", type=Path, default=Path(os.environ["LOGISIM_JAR"]) if os.environ.get("LOGISIM_JAR") else None)
    parser.add_argument("--diagnose", action="store_true", help="Record first mismatches without repairing the project")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    proof = args.output / "proof.json"
    proof.unlink(missing_ok=True)
    jar, profile = resolve_jar(args.jar), load_profile()
    original = args.project.read_bytes()
    programs = cases()
    passed, failures = [], {}

    def compare(project, name, text):
        program = raw_program(text, profile)
        run_core_comparison(project, profile, program, tuple(encode_program(program)),
                            jar, args.java, args.output / f"{name}.tsv", 30, name)

    # Independently fixed architectural expectations, in addition to the VM trace.
    for value in (0, 4095, 4096, -1):
        for source, flag in (("constant", "ADDR"), ("memory", "INV")):
            final = expected_trace(raw_program(programs[f"{source}-{value}"], profile))[-1]
            valid = int(0 <= value < 4096)
            assert (final["AR"], final["AR_VALID"], final[f"ERROR_{flag}"]) == (value if valid else 0, valid, 1-valid)
    for name, text in programs.items():
        try:
            compare(args.project, name, text)
            passed.append(name)
        except LogisimError as exc:
            if not args.diagnose or not isinstance(exc.__cause__, CoreMismatch):
                raise
            failures[name] = vars(exc.__cause__)
    rejected = {}
    if not args.diagnose:
        spec = importlib.util.spec_from_file_location("address_register_test", ROOT / "scripts/test-logisim-address-register.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for name, owner, port, value, width, case, edge, phase, signal, wanted, actual in (
            ("access-bypass", "MEMORY_UNIT", "ACCESS_VALID", 1, 1, "uninitialized-store-address_register", 4, "pre", "MEM_WRITE", 0, 1),
            ("load-valid-bypass", "ADDRESS_PATH", "VALID_IN", 1, 1, "invalid-memory-load", 2, "post", "AR_VALID", 0, 1),
            ("inv-disconnected", "FAULT_UNIT", "ADDRESS_INVALID", 0, 1, "uninitialized-store-address_register", 4, "post", "ERROR_INV", 1, 0),
        ):
            mutated = args.output / f"{name}.circ"
            module.force_input(args.project, mutated, owner, port, value, width)
            try:
                compare(mutated, name, programs[case])
            except LogisimError as exc:
                mismatch = exc.__cause__
                if not (isinstance(mismatch, CoreMismatch)
                        and (mismatch.edge, mismatch.phase, mismatch.signal, mismatch.expected, mismatch.actual)
                        == (edge, phase, signal, wanted, actual)):
                    raise
                rejected[name] = vars(exc.__cause__)
            else:
                raise LogisimError(f"address-validity mutation passed: {name}")
    assert args.project.read_bytes() == original
    proof.write_text(json.dumps({"controls_passed": passed, "first_mismatches": failures,
        "mutations_rejected": rejected, "source_unchanged": True}, indent=2) + "\n", encoding="utf-8")
    print(f"address-validity: {len(passed)} passed, {len(failures)} diagnosed, {len(rejected)} mutations rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
