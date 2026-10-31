#!/usr/bin/env python3
"""Check PRINT event forwarding and reject a suppressed pulse despite halt."""

from __future__ import annotations

import argparse
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
from tiny_cpu_verify import generated_symbol_ports


def suppress_print(source: Path, destination: Path) -> None:
    """Disconnect the named PRINT source and drive its branch low in a copy."""
    tree = ET.parse(source)
    main = tree.getroot().find("circuit[@name='TinyCPUMain']")
    definition = tree.getroot().find("circuit[@name='FetchDecodeControls']")
    instance = next(component for component in main.findall("comp")
                    if component.find("a[@name='label'][@val='FETCH_DECODE_CONTROLS']")
                    is not None)
    terminal = generated_symbol_ports(definition, instance)["PRINT"]
    wires = [wire for wire in main.findall("wire")
             if terminal in {wire.get("from"), wire.get("to")}]
    if len(wires) != 1:
        raise LogisimError("PRINT mutation requires a single source branch")
    wire = wires[0]
    other = wire.get("to") if wire.get("from") == terminal else wire.get("from")
    main.remove(wire)
    constant = ET.SubElement(main, "comp", {"lib": "0", "name": "Constant", "loc": other})
    ET.SubElement(constant, "a", {"name": "value", "val": "0x0"})
    tree.write(destination, encoding="utf-8", xml_declaration=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/print-forwarding")
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
        "positive": "LOAD_CONST(3)\nPRINT()\nHALT()\n",
        "negative": "LOAD_CONST(-1)\nPRINT()\nHALT()\n",
        "valid-zero": "LOAD_CONST(0)\nPRINT()\nPRINT()\nHALT()\n",
        "no-print": "LOAD_CONST(3)\nHALT()\n",
    }
    for name, code in cases.items():
        program = assemble(code, profile)
        run_core_comparison(source, profile, program, tuple(encode_program(program)),
                            jar, args.java, args.output / f"{name}.tsv", 30,
                            f"print-forwarding-{name}")

    mutated = args.output / "print-suppressed.circ"
    suppress_print(source, mutated)
    program = assemble(cases["positive"], profile)
    try:
        run_core_comparison(mutated, profile, program, tuple(encode_program(program)),
                            jar, args.java, args.output / "wrong.tsv", 30,
                            "print-suppressed")
    except LogisimError as exc:
        mismatch = exc.__cause__
        if not (isinstance(mismatch, CoreMismatch) and mismatch.edge == 2
                and mismatch.phase == "pre" and mismatch.signal == "PRINT_ENABLE"
                and mismatch.expected == 1 and mismatch.actual == 0):
            raise
    else:
        raise LogisimError("suppressed PRINT pulse unexpectedly passed")
    lines = (args.output / "wrong.tsv").read_text(encoding="utf-8").splitlines()
    terminal = dict(zip(lines[0].split("\t"), lines[-2].split("\t")))
    if terminal["HALTED"] != "1" or terminal["HALTED_WITH_ERROR"] != "0":
        raise LogisimError("PRINT negative control did not retain normal halt")
    if source.read_bytes() != original:
        raise LogisimError("PRINT regression modified the source circuit")
    (args.output / "proof.json").write_text(json.dumps({
        "controls_passed": list(cases), "mutation_rejected": True,
        "normal_halt_preserved": True, "source_unchanged": True,
        "edge": 2, "phase": "pre", "signal": "PRINT_ENABLE",
        "expected": 1, "actual": 0,
    }, indent=2) + "\n", encoding="utf-8")
    print("PRINT forwarding passed: positive, negative, valid zero, consecutive events "
          "and no-print control; suppressed pulse rejected despite normal halt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
