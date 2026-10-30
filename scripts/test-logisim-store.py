#!/usr/bin/env python3
"""Check STORE_ADDRESS accumulator hold and reject its former load request."""

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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/store-acc-hold")
    parser.add_argument("--java", default=os.environ.get("JAVA", "java"))
    parser.add_argument("--jar", type=Path,
                        default=Path(os.environ["LOGISIM_JAR"])
                        if os.environ.get("LOGISIM_JAR") else None)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    profile = load_profile()
    jar = resolve_jar(args.jar)
    source = ROOT / "hardware/logisim" / profile.circuit
    cases = {
        "negative": "LOAD_CONST(-1)\nSTORE_ADDRESS(101)\nHALT()\n",
        "valid-zero": "LOAD_CONST(0)\nSTORE_ADDRESS(101)\nHALT()\n",
    }
    for name, code in cases.items():
        program = assemble(code, profile)
        run_core_comparison(source, profile, program, tuple(encode_program(program)),
                            jar, args.java, args.output / f"{name}.tsv", 30,
                            f"store-acc-hold-{name}")

    # Re-enable the removed request in a copy by driving its neutral input
    # high. Resolve by label, so moving the authored gate cannot evade this
    # control. The original drawing is never written.
    tree = ET.parse(source)
    decoder = tree.getroot().find("circuit[@name='FetchDecodeControls']")
    neutral = next(component for component in decoder.findall("comp[@name='Constant']")
                   if component.find("a[@name='label']") is not None
                   and component.find("a[@name='label']").get("val") == "ACC_STORE_DISABLED")
    neutral.find("a[@name='value']").set("val", "0x1")
    mutated = args.output / "store-request-enabled.circ"
    tree.write(mutated, encoding="utf-8", xml_declaration=True)
    program = assemble(cases["negative"], profile)
    try:
        run_core_comparison(mutated, profile, program, tuple(encode_program(program)),
                            jar, args.java, args.output / "wrong.tsv", 30,
                            "store-request-enabled")
    except LogisimError as exc:
        mismatch = exc.__cause__
        if not (isinstance(mismatch, CoreMismatch) and mismatch.edge == 2
                and mismatch.phase == "post" and mismatch.signal == "ACC"
                and mismatch.expected == 65535 and mismatch.actual == 0):
            raise
    else:
        raise LogisimError("re-enabled accumulator write during STORE unexpectedly passed")
    (args.output / "proof.json").write_text(json.dumps({
        "controls_passed": list(cases), "mutation_rejected": True,
        "edge": 2, "phase": "post", "signal": "ACC",
        "expected": 65535, "actual": 0,
    }, indent=2) + "\n", encoding="utf-8")
    print("STORE_ADDRESS accumulator hold passed: negative and valid zero; "
          "re-enabled load request rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
