#!/usr/bin/env python3
"""Check address-register constants and indirect reads, including mutations."""

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


def force_input(source: Path, destination: Path, instance_label: str,
                port: str, value: int, width: int) -> None:
    """Replace one named boundary input only in a test copy."""
    tree = ET.parse(source)
    root = tree.getroot()
    main = root.find("circuit[@name='TinyCPUMain']")
    instance = next(component for component in main.findall("comp")
                    if component.find(f"a[@name='label'][@val='{instance_label}']")
                    is not None)
    definition = root.find(f"circuit[@name='{instance.get('name')}']")
    terminal = generated_symbol_ports(definition, instance)[port]
    branches = [wire for wire in main.findall("wire")
                if terminal in {wire.get("from"), wire.get("to")}]
    if len(branches) != 1:
        raise LogisimError(f"{port} mutation requires a single input branch")
    main.remove(branches[0])
    constant = ET.SubElement(main, "comp", {"lib": "0", "name": "Constant", "loc": terminal})
    ET.SubElement(constant, "a", {"name": "value", "val": hex(value)})
    ET.SubElement(constant, "a", {"name": "width", "val": str(width)})
    tree.write(destination, encoding="utf-8", xml_declaration=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/address-register")
    parser.add_argument("--java", default=os.environ.get("JAVA", "java"))
    parser.add_argument("--jar", type=Path,
                        default=Path(os.environ["LOGISIM_JAR"])
                        if os.environ.get("LOGISIM_JAR") else None)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    proof = args.output / "proof.json"
    proof.unlink(missing_ok=True)
    profile = load_profile()
    jar = resolve_jar(args.jar)
    source = ROOT / "hardware/logisim" / profile.circuit
    original = source.read_bytes()
    cases = {
        "constant-hold": "LOAD_CONST(7)\nLOAD_ADDRESS_REGISTER_CONST(20)\nHALT()\n",
        "zero-and-reload": ("LOAD_CONST(-7)\nLOAD_ADDRESS_REGISTER_CONST(20)\n"
                            "LOAD_ADDRESS_REGISTER_CONST(0)\n"
                            "LOAD_ADDRESS_REGISTER_CONST(4095)\nHALT()\n"),
        "register-read": ("LOAD_CONST(7)\nSTORE_ADDRESS(20)\n"
                          "LOAD_ADDRESS_REGISTER_CONST(20)\nLOAD_CONST(0)\n"
                          "LOAD_ADDRESS_REGISTER()\nPRINT()\nHALT()\n"),
        "register-read-zero": ("LOAD_CONST(0)\nSTORE_ADDRESS(20)\n"
                               "LOAD_ADDRESS_REGISTER_CONST(20)\nLOAD_CONST(-1)\n"
                               "LOAD_ADDRESS_REGISTER()\nPRINT()\nHALT()\n"),
        "offset-read-two": ("LOAD_CONST(7)\nSTORE_ADDRESS(22)\n"
                            "LOAD_ADDRESS_REGISTER_CONST(20)\nLOAD_CONST(0)\n"
                            "LOAD_ADDRESS_REGISTER_PLUS_OFFSET(2)\nPRINT()\nHALT()\n"),
        "offset-read-negative": ("LOAD_CONST(7)\nSTORE_ADDRESS(19)\n"
                                 "LOAD_ADDRESS_REGISTER_CONST(20)\nLOAD_CONST(0)\n"
                                 "LOAD_ADDRESS_REGISTER_PLUS_OFFSET(-1)\nPRINT()\nHALT()\n"),
        "register-store": ("LOAD_ADDRESS_REGISTER_CONST(20)\nLOAD_CONST(-1)\n"
                           "STORE_ADDRESS_REGISTER()\nLOAD_CONST(0)\n"
                           "LOAD_ADDRESS(20)\nPRINT()\nHALT()\n"),
        "offset-store": ("LOAD_ADDRESS_REGISTER_CONST(20)\nLOAD_CONST(-1)\n"
                         "STORE_ADDRESS_REGISTER_PLUS_OFFSET(2)\nLOAD_CONST(0)\n"
                         "LOAD_ADDRESS(22)\nPRINT()\nHALT()\n"),
        "register-from-memory": ("LOAD_CONST(20)\nSTORE_ADDRESS(10)\n"
                                 "LOAD_ADDRESS_REGISTER_ADDRESS(10)\nHALT()\n"),
    }

    def compare(project: Path, case: str, name: str) -> None:
        program = assemble(cases[case], profile)
        run_core_comparison(project, profile, program, tuple(encode_program(program)),
                            jar, args.java, args.output / f"{name}.tsv", 30,
                            f"address-register-{name}")

    for name in cases:
        compare(source, name, name)
    rejected = {}
    mutations = (
        ("reset-stuck", "ADDRESS_PATH", "ADDRESS_PATH_STARTUP_RESET", 1, 1,
         "constant-hold", 2, "post", "AR", 20, 0),
        ("load-disabled", "ADDRESS_PATH", "AR_LOAD", 0, 1,
         "constant-hold", 2, "post", "AR", 20, 0),
        ("data-stuck", "ADDRESS_PATH", "ADDRESS_IN", 1, 16,
         "constant-hold", 2, "post", "AR", 20, 1),
        ("register-unselected", "EFFECTIVE_ADDRESS_FBOX", "ADDR_REG_ARGUMENT", 0, 1,
         "register-read", 5, "pre", "MEM_ADDRESS", 20, 0),
        ("negative-offset-carry", "ADDRESS_RANGE_FBOX", "OFFSET_CARRY", 1, 1,
         "offset-read-negative", 5, "post", "ERROR_ADDR", 0, 1),
    )
    for name, owner, port, value, width, case, edge, phase, signal, expected, actual in mutations:
        mutated = args.output / f"{name}.circ"
        force_input(source, mutated, owner, port, value, width)
        try:
            compare(mutated, case, name)
        except LogisimError as exc:
            mismatch = exc.__cause__
            if not (isinstance(mismatch, CoreMismatch) and mismatch.edge == edge
                    and mismatch.phase == phase and mismatch.signal == signal
                    and mismatch.expected == expected and mismatch.actual == actual):
                raise
            rejected[name] = vars(mismatch)
        else:
            raise LogisimError(f"address-register mutation unexpectedly passed: {name}")
    if source.read_bytes() != original:
        raise LogisimError("address-register regression modified the source circuit")
    proof.write_text(json.dumps({"controls_passed": list(cases),
                                 "mutations_rejected": rejected,
                                 "source_unchanged": True}, indent=2) + "\n", encoding="utf-8")
    print("address-register acceptance passed: constants, hold, reload, indirect reads; "
          "reset/load/data/selection/carry mutations rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
