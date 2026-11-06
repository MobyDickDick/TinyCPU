#!/usr/bin/env python3
"""Electrical signed boundaries with mathematical expectations and VM parity."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from tiny_cpu_assembler import assemble, encode_program
from tiny_cpu_core_trace import CoreMismatch, expected_trace
from tiny_cpu_logisim import LogisimError, resolve_jar, run_core_comparison
from tiny_cpu_profiles import load_profile


def arithmetic(operation, left, right):
    if operation == "DIV" and right == 0:
        return 0, 0, 0, 1
    if operation == "DIV":
        result = (abs(left) // abs(right)) * (-1 if (left < 0) != (right < 0) else 1)
        # Explicit v1 compatibility decision: min / -1 wraps without OVF.
        return result & 0xffff, 1, 0, 0
    result = {"ADD": lambda: left + right, "SUB": lambda: left - right,
              "MUL": lambda: left * right}[operation]()
    overflow = int(not -32768 <= result <= 32767)
    return 0 if overflow else result & 0xffff, 1-overflow, overflow, 0


def program(operation, mode, left, right):
    if mode == "CONST":
        return f"LOAD_CONST({left})\n{operation}_CONST({right})\nHALT()\n"
    prefix = f"LOAD_CONST({right})\nSTORE_ADDRESS(101)\n"
    if mode == "ADDRESS":
        return prefix + f"LOAD_CONST({left})\n{operation}_ADDRESS(101)\nHALT()\n"
    base, suffix = (101, "ADDRESS_REGISTER()") if mode == "REGISTER" else (100, "ADDRESS_REGISTER_PLUS_OFFSET(1)")
    return prefix + f"LOAD_ADDRESS_REGISTER_CONST({base})\nLOAD_CONST({left})\n{operation}_{suffix}\nHALT()\n"


def run_vectors(jar, java, output, name, circuit, vector, source, *, reject=False):
    command = [java, "-Djava.awt.headless=true", "-cp", str(jar),
               str(ROOT / "scripts/LogisimHeadlessVector.java"), circuit, str(vector), str(source)]
    (output / f"{name}-command.json").write_text(json.dumps(command, indent=2) + "\n")
    with (output / f"{name}.txt").open("wb") as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=30)
    assert (result.returncode != 0) if reject else (result.returncode == 0), name


def require_core_rejection(source, output, jar, java, profile, code, wanted, name):
    p = assemble(code, profile)
    try:
        run_core_comparison(source, profile, p, tuple(encode_program(p)), jar, java,
                            output / f"{name}.tsv", 30, name)
    except LogisimError as exc:
        mismatch = exc.__cause__
        assert isinstance(mismatch, CoreMismatch), exc
        assert (mismatch.edge, mismatch.phase, mismatch.signal,
                mismatch.expected, mismatch.actual) == wanted, mismatch
        return vars(mismatch)
    raise AssertionError(f"{name} defect was accepted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/arithmetic-boundaries")
    parser.add_argument("--before-mul", type=Path, help="retain a pre-fix core as an electrical negative control")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    profile = load_profile()
    jar = resolve_jar(Path(os.environ["LOGISIM_JAR"]) if os.environ.get("LOGISIM_JAR") else None)
    java = os.environ.get("JAVA", "java")
    source = ROOT / "hardware/logisim/TinyCPU.circ"
    saved = source.read_bytes()
    cases = []
    for op, pairs in {
        "ADD": [(32767, 1), (-32768, -1), (32767, -32768), (-1, 1), (32767, 0)],
        "SUB": [(-32768, 1), (32767, -1), (-32768, -1), (-32768, -32768), (0, 1)],
        "MUL": [(16384, 2), (32767, 32767), (-32768, -1), (-32768, 1),
                (-16384, 2), (-128, -128), (0, -32768), (-7, 3), (300, 300)],
        "DIV": [(7, 2), (-7, 2), (7, -2), (-7, -2), (-32768, -1), (-32768, 1), (7, 0)],
    }.items():
        for index, (left, right) in enumerate(pairs):
            modes = ("CONST", "ADDRESS", "REGISTER", "OFFSET") if op in {"MUL", "DIV"} else ("CONST",)
            for mode in modes:
                code = program(op, mode, left, right)
                cases.append((f"{op.lower()}-{index}-{mode.lower()}", code, arithmetic(op, left, right)))
    cases.append(("clear-preserves-invalid", "LOAD_CONST(16384)\nMUL_CONST(2)\nCLEAR_ERROR()\nHALT()\n", (0, 0, 0, 0)))
    for op in ("ADD", "SUB", "MUL", "DIV"):
        cases.append((f"{op.lower()}-invalid-left", f"{op}_CONST(2)\nHALT()\n", (0, 0, 0, 0)))
        cases.append((f"{op.lower()}-invalid-memory", f"LOAD_CONST(7)\n{op}_ADDRESS(101)\nHALT()\n", (0, 0, 0, 0)))
    passed = []
    for name, code, wanted in cases:
        p = assemble(code, profile)
        final = expected_trace(p)[-1]
        actual = tuple(final[k] for k in ("ACC", "ACC_VALID", "ERROR_OVF", "ERROR_DIV0"))
        assert actual == wanted, (name, wanted, actual)
        if "invalid-" in name:
            assert final["ERROR_INV"] == 1, name
        print("arithmetic", name, flush=True)
        run_core_comparison(source, profile, p, tuple(encode_program(p)), jar, java,
                            args.output / f"{name}.tsv", 30, name)
        passed.append(name)
    # Isolated multiplier: both copies, including input validity and activation.
    rows = ["LEFT[16] RIGHT[16] MUL_ACTIVATED INPUT_VALID RESULT[16] OVERFLOW RESULT_VALID <set> <seq>"]
    seq = 0
    for left, right in [(16384, 2), (32767, 32767), (-32768, -1), (-32768, 1),
                        (-16384, 2), (-128, -128), (0, -32768), (-7, 3), (300, 300)]:
        product = left * right
        for active, valid in ((0, 0), (0, 1), (1, 0), (1, 1)):
            seq += 1
            ovf = int(active and valid and not -32768 <= product <= 32767)
            rows.append(f"0x{left & 0xffff:04x} 0x{right & 0xffff:04x} {active} {valid} "
                        f"0x{(product & 0xffff) if active else 0:04x} {ovf} {int(active and valid and not ovf)} 1 {seq}")
    vector = args.output / "mul-vector.txt"
    vector.write_text("\n".join(rows) + "\n")
    for name, path in (("integrated", source), ("standalone", ROOT / "hardware/logisim/diagnostics/TinyCPU-MulArithmeticCircuit.circ")):
        run_vectors(jar, java, args.output, f"mul-{name}", "MulArithmeticCircuit", vector, path)
    div_rows = ["LEFT[16] RIGHT[16] DIV_ACTIVATED INPUT_VALID RESULT[16] DIVIDE_BY_ZERO RESULT_VALID <set> <seq>"]
    div_seq = 0
    for left, right in [(7, 2), (7, -2), (-7, 2), (-7, -2), (-32768, -1),
                        (-32768, 1), (7, 0), (7, 1), (0, -32768)]:
        quotient = ((abs(left) // abs(right)) * (-1 if (left < 0) != (right < 0) else 1)
                    if right else left)
        for active, valid in ((0, 0), (0, 1), (1, 0), (1, 1)):
            div_seq += 1
            div_rows.append(f"0x{left & 0xffff:04x} 0x{right & 0xffff:04x} {active} {valid} "
                            f"0x{(quotient & 0xffff) if active else 0:04x} "
                            f"{int(active and valid and right == 0)} {int(active and valid and right != 0)} 1 {div_seq}")
    div_vector = args.output / "div-vector.txt"
    div_vector.write_text("\n".join(div_rows) + "\n")
    for name, path in (("integrated", source), ("standalone", ROOT / "hardware/logisim/diagnostics/TinyCPU-DivArithmeticCircuit.circ")):
        run_vectors(jar, java, args.output, f"div-{name}", "DivArithmeticCircuit", div_vector, path)
    # A deliberately incorrect expectation must also fail the native vector adapter.
    wrong_vector = args.output / "wrong-div-vector.txt"
    wrong_vector.write_text(div_rows[0] + "\n" + div_rows[4].replace("0x0003", "0x0004") + "\n")
    run_vectors(jar, java, args.output, "wrong-vector-rejected", "DivArithmeticCircuit",
                wrong_vector, source, reject=True)
    # Portable fault controls, independent of a locally retained historical copy.
    fault_rejections = {}
    for kind in ("mul-range-bypass", "div-signed-zero-check"):
        tree = ET.parse(source)
        circuit = tree.getroot().find(f"circuit[@name='{'Mul' if kind.startswith('mul') else 'Div'}ArithmeticCircuit']")
        comparator = circuit.find("comp[@name='Comparator']")
        if kind.startswith("mul"):
            circuit.remove(comparator)
            constant = ET.SubElement(circuit, "comp", {"lib": "0", "name": "Constant", "loc": comparator.get("loc")})
            ET.SubElement(constant, "a", {"name": "value", "val": "0x1"})
            code, wanted = program("MUL", "CONST", 16384, 2), (2, "post", "ACC", 0, 32768)
        else:
            comparator.find("a[@name='mode']").set("val", "twosComplement")
            code, wanted = program("DIV", "CONST", 7, -2), (2, "post", "ACC", 65533, 0)
        mutant = args.output / f"{kind}.circ"
        tree.write(mutant, encoding="utf-8", xml_declaration=True)
        fault_rejections[kind] = require_core_rejection(mutant, args.output, jar, java, profile, code, wanted, kind)
    rejected = None
    if args.before_mul:
        old = ET.parse(args.before_mul).getroot().find("circuit[@name='MulArithmeticCircuit']")
        tree = ET.parse(source)
        current = tree.getroot().find("circuit[@name='MulArithmeticCircuit']")
        tree.getroot().remove(current)
        tree.getroot().append(old)
        mutant = args.output / "old-mul.circ"
        tree.write(mutant, encoding="utf-8", xml_declaration=True)
        rejected = require_core_rejection(mutant, args.output, jar, java, profile,
            program("MUL", "CONST", 16384, 2), (2, "post", "ACC", 0, 32768), "old-mul")
    assert saved == source.read_bytes()
    (args.output / "proof.json").write_text(json.dumps({"core_cases": passed,
        "mul_vectors_per_copy": seq, "div_vectors_per_copy": div_seq,
        "fault_rejections": fault_rejections, "wrong_vector_rejected": True, "old_mul_rejected": rejected,
        "division_min_over_minus_one": "v1-wrap-valid-no-OVF", "source_unchanged": True}, indent=2) + "\n")
    print(f"Arithmetic: {len(passed)} full VM comparisons, {seq} MUL and {div_seq} DIV vectors per copy; negative controls rejected")


if __name__ == "__main__":
    main()
