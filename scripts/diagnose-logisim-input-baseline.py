#!/usr/bin/env python3
"""Passively measure AP 22.1's unavailable INPUT before adding input hardware."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tiny_cpu_assembler import assemble, encode_program
from tiny_cpu_core_trace import CoreMismatch, SIGNALS, compare_trace, expected_trace
from tiny_cpu_logisim import LogisimError, resolve_jar, run_core_comparison
from tiny_cpu_profiles import load_profile


PROBES = {
    "DECODE_INPUT": (1, "FETCH_UNIT/FETCH_DECODE_CONTROLS/INPUT"),
    "DECODE_ACC_WRITE": (1, "FETCH_UNIT/FETCH_DECODE_CONTROLS/ACC_WRITE_REQUEST"),
    "DECODE_SET_INPUT": (1, "FETCH_UNIT/FETCH_DECODE_CONTROLS/SET_INPUT"),
    "ACC_CONTROL": (45, "ACCUMULATOR_UNIT/CONTROL"),
    "FAULT_CONTROL": (45, "FAULT_UNIT/CONTROL"),
    "DATA_IN": (16, "ACCUMULATOR_UNIT/DATAPATH_INSTANCE/DATA_IN"),
    "ACC_LOAD": (1, "ACCUMULATOR_UNIT/DATAPATH_INSTANCE/ACC_LOAD"),
    "VALID_IN": (1, "ACCUMULATOR_UNIT/DATAPATH_INSTANCE/VALID_IN"),
    "DATAPATH_CLK": (1, "ACCUMULATOR_UNIT/DATAPATH_INSTANCE/CLK"),
    "SET_INPUT": (1, "FAULT_UNIT/ERROR_FLAGS/SET_INPUT"),
    "INPUT_OUT": (1, "FAULT_UNIT/ERROR_FLAGS/INPUT_OUT"),
}


def check_internal_trace(text, expected):
    """Keep the full VM comparator and reject undefined diagnostic buses too."""
    lines = text.splitlines()
    header = ["edge", "phase", *SIGNALS, *PROBES, "MEMORY"]
    if not lines or lines[0].split("\t") != header:
        raise CoreMismatch(0, "schema", "columns", header, lines[0] if lines else "<missing>")
    projected = ["\t".join(["edge", "phase", *SIGNALS, "MEMORY"])]
    rows = []
    for line in lines[1:]:
        cells = line.split("\t")
        if len(cells) != len(header):
            raise CoreMismatch(0, "schema", "columns", len(header), len(cells))
        raw = dict(zip(header, cells))
        projected.append("\t".join(raw[name] for name in ["edge", "phase", *SIGNALS, "MEMORY"]))
        rows.append(raw)
    compare_trace("\n".join(projected) + "\n", expected)
    observations = []
    for raw in rows:
        edge, phase = int(raw["edge"]), raw["phase"]
        row = {"edge": edge, "phase": phase}
        for name, (width, _) in PROBES.items():
            bits = raw[name]
            if len(bits) != width or any(bit not in "01" for bit in bits):
                raise CoreMismatch(edge, phase, name, f"{width} defined bits", bits)
            row[name] = int(bits, 2)

        def require(name, wanted):
            if row[name] != wanted:
                raise CoreMismatch(edge, phase, name, wanted, row[name])

        require("DATAPATH_CLK", int(phase == "post"))
        require("INPUT_OUT", int(raw["ERROR_INPUT"], 2))
        # Decoder SET_INPUT is the explicit flag-setting instruction. The
        # unavailable INPUT error instead follows CONTROL bit 34 (INPUT).
        require("DECODE_SET_INPUT", 0)
        require("SET_INPUT", row["DECODE_INPUT"])
        require("ACC_LOAD", row["DECODE_ACC_WRITE"])
        for bus in ("ACC_CONTROL", "FAULT_CONTROL"):
            if (row[bus] >> 34) & 1 != row["DECODE_INPUT"]:
                raise CoreMismatch(edge, phase, f"{bus}.34", row["DECODE_INPUT"], (row[bus] >> 34) & 1)
        # Independent expectations for the actual INPUT window. Post 1 already
        # decodes INPUT; only edge 2 stores its result and its sticky error.
        if (edge, phase) in {(1, "post"), (2, "pre")}:
            for name, wanted in {"DECODE_INPUT": 1, "DECODE_ACC_WRITE": 1,
                                 "SET_INPUT": 1, "DATA_IN": 0,
                                 "ACC_LOAD": 1, "VALID_IN": 0, "INPUT_OUT": 0}.items():
                require(name, wanted)
        if (edge, phase) == (1, "pre"):
            for name, wanted in {"DECODE_INPUT": 0, "DATA_IN": 7,
                                 "ACC_LOAD": 1, "VALID_IN": 1, "SET_INPUT": 0}.items():
                require(name, wanted)
        if (edge, phase) in {(2, "post"), (3, "pre")}:
            for name, wanted in {"DECODE_INPUT": 0, "ACC_LOAD": 0,
                                 "SET_INPUT": 0, "INPUT_OUT": 1}.items():
                require(name, wanted)
        observations.append(row)
    return observations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/input-baseline")
    parser.add_argument("--java", default=os.environ.get("JAVA", "java"))
    parser.add_argument("--jar", type=Path, default=Path(os.environ["LOGISIM_JAR"])
                        if os.environ.get("LOGISIM_JAR") else None)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    proof = args.output / "proof.json"
    proof.unlink(missing_ok=True)
    (args.output / "internal-diagnostic.json").unlink(missing_ok=True)
    sources = {path: path.read_bytes() for path in (ROOT / "hardware/logisim").rglob("*.circ")}
    profile, jar = load_profile(), resolve_jar(args.jar)
    source = ROOT / "hardware/logisim" / profile.circuit
    code = "LOAD_CONST(7)\nINPUT()\nHALT()\n"
    program = assemble(code, profile)
    (args.output / "program.tcpu").write_text(code, encoding="utf-8")
    run_core_comparison(source, profile, program, tuple(encode_program(program)),
                        jar, args.java, args.output / "baseline.tsv", 30, "input-baseline")
    evidence = args.output / "baseline"
    probes = args.output / "internal-probes.tsv"
    probes.write_text("".join(f"{name}\t{path}\n" for name, (_, path)
                              in {**SIGNALS, **PROBES}.items()), encoding="utf-8")
    command = json.loads((evidence / "command.json").read_text(encoding="utf-8"))
    command[-2] = str(probes.resolve())
    (args.output / "internal-command.json").write_text(json.dumps(command, indent=2) + "\n", encoding="utf-8")
    output = args.output / "internal.tsv"
    try:
        with output.open("wb") as stdout, (args.output / "internal-stderr.txt").open("wb") as stderr:
            result = subprocess.run(command, stdout=stdout, stderr=stderr, timeout=30, check=False)
        if result.returncode:
            raise LogisimError(f"internal exporter exited {result.returncode}; evidence: {args.output}")
        observations = check_internal_trace(output.read_text(encoding="utf-8"), expected_trace(program))
    except CoreMismatch as exc:
        (args.output / "internal-diagnostic.json").write_text(json.dumps(vars(exc), indent=2) + "\n", encoding="utf-8")
        raise
    finally:
        if any(path.read_bytes() != original for path, original in sources.items()):
            raise LogisimError("passive INPUT measurement modified a source circuit")
    proof.write_text(json.dumps({
        "program": code, "vm_comparison_passed": True,
        "internal_vm_comparison_passed": True, "internal_observations": observations,
        "source_circuits_unchanged": True,
        "source_sha256": hashlib.sha256(sources[source]).hexdigest(),
        "jar_sha256": hashlib.sha256(jar.read_bytes()).hexdigest(),
    }, indent=2) + "\n", encoding="utf-8")
    print("INPUT baseline passed: 3 edges, full VM state/RAM comparison and named internal paths; source circuits unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
