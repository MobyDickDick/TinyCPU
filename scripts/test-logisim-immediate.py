#!/usr/bin/env python3
"""Check constant operands and reject suppressed selection or immediate data."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tiny_cpu_assembler import assemble, encode_program
from tiny_cpu_core_trace import CoreMismatch
from tiny_cpu_logisim import LogisimError, resolve_jar, run_core_comparison
from tiny_cpu_profiles import load_profile
from tiny_cpu_hierarchy import find_core_instance
from tiny_cpu_verify import generated_symbol_ports


def suppress_selector(source: Path, destination: Path) -> None:
    """Drive the existing selection branch low only in a temporary copy."""
    tree = ET.parse(source)
    root = tree.getroot()
    main, instance = find_core_instance(root, "FETCH_DECODE_CONTROLS")
    definition = root.find("circuit[@name='FetchDecodeControls']")
    terminal = generated_symbol_ports(definition, instance)["CONST_ARGUMENT"]
    wires = [wire for wire in main.findall("wire")
             if terminal in {wire.get("from"), wire.get("to")}]
    if len(wires) != 1:
        raise LogisimError("constant operand mutation requires a single source branch")
    wire = wires[0]
    other = wire.get("to") if wire.get("from") == terminal else wire.get("from")
    main.remove(wire)
    constant = ET.SubElement(main, "comp", {"lib": "0", "name": "Constant", "loc": other})
    ET.SubElement(constant, "a", {"name": "value", "val": "0x0"})
    tree.write(destination, encoding="utf-8", xml_declaration=True)


def suppress_immediate(source: Path, destination: Path) -> None:
    """Replace only the Operations immediate data input with a 16-bit zero."""
    tree = ET.parse(source)
    root = tree.getroot()
    main, instance = find_core_instance(root, "OPERATIONS_INSTANCE")
    definition = root.find("circuit[@name='Operations']")
    terminal = generated_symbol_ports(definition, instance)["IMMEDIATE_VALUE"]
    wires = [wire for wire in main.findall("wire")
             if terminal in {wire.get("from"), wire.get("to")}]
    if len(wires) != 1:
        raise LogisimError("immediate data mutation requires a single input branch")
    main.remove(wires[0])
    constant = ET.SubElement(main, "comp", {"lib": "0", "name": "Constant", "loc": terminal})
    ET.SubElement(constant, "a", {"name": "value", "val": "0x0"})
    ET.SubElement(constant, "a", {"name": "width", "val": "16"})
    tree.write(destination, encoding="utf-8", xml_declaration=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/immediate-operand")
    parser.add_argument("--java", default=os.environ.get("JAVA", "java"))
    parser.add_argument("--jar", type=Path,
                        default=Path(os.environ["LOGISIM_JAR"])
                        if os.environ.get("LOGISIM_JAR") else None)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    profile = load_profile()
    jar = resolve_jar(args.jar)
    source = ROOT / "hardware/logisim" / profile.circuit
    original = source.read_bytes()
    cases = {
        "countdown-add": "LOAD_CONST(3)\nADD_CONST(-1)\nHALT()\n",
        "valid-zero": "LOAD_CONST(-1)\nADD_CONST(1)\nHALT()\n",
    }
    for name, code in cases.items():
        program = assemble(code, profile)
        run_core_comparison(source, profile, program, tuple(encode_program(program)),
                            jar, args.java, args.output / f"{name}.tsv", 30,
                            f"immediate-operand-{name}")

    mutated = args.output / "selector-suppressed.circ"
    suppress_selector(source, mutated)
    program = assemble(cases["countdown-add"], profile)
    try:
        run_core_comparison(mutated, profile, program, tuple(encode_program(program)),
                            jar, args.java, args.output / "wrong.tsv", 30,
                            "constant-selector-suppressed")
    except LogisimError as exc:
        mismatch = exc.__cause__
        if not (isinstance(mismatch, CoreMismatch) and mismatch.edge == 2
                and mismatch.phase == "post" and mismatch.signal == "ACC"
                and mismatch.expected == 2 and mismatch.actual == 0):
            raise
    else:
        raise LogisimError("suppressed constant operand selector unexpectedly passed")
    with (args.output / "wrong.tsv").open(encoding="utf-8") as trace:
        rejected = next(row for row in csv.DictReader(trace, delimiter="\t")
                        if row["edge"] == "2" and row["phase"] == "post")
    if rejected["ACC_VALID"] != "0" or rejected["ERROR_INV"] != "1":
        raise LogisimError("suppressed selector must produce 0 INVALID with INV set")
    wrong_data = args.output / "immediate-suppressed.circ"
    suppress_immediate(source, wrong_data)
    try:
        run_core_comparison(wrong_data, profile, program, tuple(encode_program(program)),
                            jar, args.java, args.output / "wrong-data.tsv", 30,
                            "immediate-data-suppressed")
    except LogisimError as exc:
        mismatch = exc.__cause__
        if not (isinstance(mismatch, CoreMismatch) and mismatch.edge == 2
                and mismatch.phase == "post" and mismatch.signal == "ACC"
                and mismatch.expected == 2 and mismatch.actual == 3):
            raise
    else:
        raise LogisimError("suppressed immediate data unexpectedly passed")
    if source.read_bytes() != original:
        raise LogisimError("constant operand regression modified the source circuit")
    (args.output / "proof.json").write_text(json.dumps({
        "controls_passed": list(cases), "mutation_rejected": True,
        "source_unchanged": True, "edge": 2, "phase": "post",
        "signal": "ACC", "expected": 2, "actual": 0,
        "acc_valid": 0, "error_inv": 1,
        "data_mutation_rejected": True,
        "data_mismatch": {"edge": 2, "phase": "post", "signal": "ACC",
                          "expected": 2, "actual": 3},
    }, indent=2) + "\n", encoding="utf-8")
    print("constant operand forwarding passed: countdown addition and valid zero; "
          "suppressed selector and immediate data rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
