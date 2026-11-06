#!/usr/bin/env python3
"""Compare the operator panel's STEP-driven CPU to the full VM edge trace."""
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
from tiny_cpu_core_trace import CoreMismatch, compare_trace, expected_trace, write_probes
from tiny_cpu_logisim import _inject_rom, resolve_jar
from tiny_cpu_profiles import load_profile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/operator-core")
    parser.add_argument("--project", type=Path, default=ROOT / "hardware/logisim/TinyCPU_Operator.circ")
    parser.add_argument("--core", type=Path, default=ROOT / "hardware/logisim/TinyCPU.circ")
    parser.add_argument("--no-mutation", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    profile = load_profile()
    jar = resolve_jar(Path(os.environ["LOGISIM_JAR"]) if os.environ.get("LOGISIM_JAR") else None)
    originals = {p: p.read_bytes() for p in (args.project, args.core)}

    def compare(name, code, mutate=False):
        out = args.output / name
        out.mkdir(parents=True, exist_ok=True)
        program = assemble(code, profile)
        core = ET.parse(args.core)
        _inject_rom(core.getroot(), args.core, tuple(encode_program(program)))
        core.write(out / "TinyCPU.circ", encoding="utf-8", xml_declaration=True)
        operator = ET.parse(args.project)
        if mutate:
            for co in operator.getroot().findall(".//comp[@name='Constant']"):
                value = co.find("a[@name='value']")
                if value is None:
                    value = ET.SubElement(co, "a", {"name": "value"})
                value.set("val", "0x1")
        operator.write(out / "TinyCPU_Operator.circ", encoding="utf-8", xml_declaration=True)
        probes = out / "probes.tsv"
        write_probes(probes)
        expected = expected_trace(program)
        (out / "expected.json").write_text(json.dumps(expected, indent=2) + "\n")
        command = [os.environ.get("JAVA", "java"), "-Djava.awt.headless=true", "-cp", str(jar),
                   str(ROOT / "scripts/LogisimCoreTrace.java"), "TinyCPUOperator",
                   str((out / "TinyCPU_Operator.circ").resolve()), str(probes.resolve()),
                   str(len(expected) // 2 + 1), "--operator"]
        (out / "command.json").write_text(json.dumps(command, indent=2) + "\n")
        with (out / "trace.tsv").open("wb") as stdout, (out / "stderr.txt").open("wb") as stderr:
            result = subprocess.run(command, stdout=stdout, stderr=stderr, timeout=30)
        try:
            compare_trace((out / "trace.tsv").read_text(), expected)
        except CoreMismatch as exc:
            (out / "diagnostic.json").write_text(json.dumps(vars(exc), indent=2) + "\n")
            raise
        if result.returncode:
            raise RuntimeError(f"exporter failed: {out}")

    code = "LOAD_CONST(7)\nPRINT()\nHALT()\n"
    compare("load-print-halt", code)
    compare("countdown", (ROOT / "hardware/logisim/ap5_countdown.tcpu").read_text())
    rejected = None
    if not args.no_mutation:
        try:
            compare("idle-inputs-high", code, True)
        except CoreMismatch as exc:
            assert (exc.edge, exc.phase, exc.signal, exc.expected, exc.actual) == (1, "pre", "MEM_WRITE", 0, 1), exc
            rejected = vars(exc)
        else:
            raise AssertionError("operator idle-input mutation passed")
    assert all(p.read_bytes() == data for p, data in originals.items())
    (args.output / "proof.json").write_text(json.dumps({"vm_comparisons": 2,
        "mutation_rejected": rejected, "sources_unchanged": True}, indent=2) + "\n")
    print("Operator CPU: load/print/halt and countdown match VM; idle-input mutation rejected" if rejected else "Operator CPU: VM comparisons passed")


if __name__ == "__main__":
    main()
