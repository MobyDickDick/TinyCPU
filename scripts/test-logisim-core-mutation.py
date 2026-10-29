#!/usr/bin/env python3
"""Prove that a wrong accumulator result with correct halt fails the core gate."""

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


def corrupt_result(source: Path, destination: Path) -> None:
    """Insert a 16-bit inverter before accumulator loading in a copied circuit.

    Keep the public DATA_IN pin in the same input row. The decoder, clock,
    validity and halt paths are untouched. Never modify the authored project.
    """
    tree = ET.parse(source)
    datapath = tree.getroot().find("circuit[@name='Datapath']")
    pin = next(component for component in datapath.findall("comp[@name='Pin']")
               if component.find("a[@name='label']").get("val") == "DATA_IN")
    x, y = map(int, pin.get("loc").strip("()").split(","))
    location = pin.get("loc")
    pin.set("loc", f"({x - 40},{y})")
    inverter = ET.SubElement(datapath, "comp", {"lib": "1", "name": "NOT Gate",
                                               "loc": location})
    ET.SubElement(inverter, "a", {"name": "width", "val": "16"})
    ET.SubElement(datapath, "wire", {"from": pin.get("loc"),
                                      "to": f"({x - 20},{y})"})
    tree.write(destination, encoding="utf-8", xml_declaration=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/core-mutation")
    parser.add_argument("--java", default=os.environ.get("JAVA", "java"))
    parser.add_argument("--jar", type=Path,
                        default=Path(os.environ["LOGISIM_JAR"])
                        if os.environ.get("LOGISIM_JAR") else None)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    profile = load_profile()
    jar = resolve_jar(args.jar)
    source = ROOT / "hardware/logisim" / profile.circuit
    program = assemble("LOAD_CONST(3)\nHALT()\n", profile)
    words = tuple(encode_program(program))
    run_core_comparison(source, profile, program, words, jar, args.java,
                        args.output / "correct.tsv", 30, "mutation-control")
    mutated = args.output / "corrupt-result.circ"
    corrupt_result(source, mutated)
    try:
        run_core_comparison(mutated, profile, program, words, jar, args.java,
                            args.output / "wrong.tsv", 30, "corrupt-result")
    except LogisimError as exc:
        mismatch = exc.__cause__
        if not (isinstance(mismatch, CoreMismatch) and mismatch.edge == 1
                and mismatch.phase == "post" and mismatch.signal == "ACC"
                and mismatch.expected == 3 and mismatch.actual == 65532):
            raise
    else:
        raise LogisimError("corrupted result unexpectedly passed")
    lines = (args.output / "wrong.tsv").read_text(encoding="utf-8").splitlines()
    rows = [dict(zip(lines[0].split("\t"), line.split("\t"))) for line in lines[1:]]
    terminal = rows[-2]
    if terminal["HALTED"] != "1" or terminal["HALTED_WITH_ERROR"] != "0":
        raise LogisimError("negative control did not retain the correct normal halt")
    (args.output / "proof.json").write_text(json.dumps({
        "control_passed": True, "mutation_rejected": True,
        "normal_halt_preserved": True, "edge": 1, "signal": "ACC",
        "expected": 3, "actual": 65532,
    }, indent=2) + "\n", encoding="utf-8")
    print("electrical core negative control passed: wrong ACC rejected despite normal halt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
