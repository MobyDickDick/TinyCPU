#!/usr/bin/env python3
"""AP 22.1 step 3: serial dynamic INPUT/VM acceptance, stopping at first difference."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from tiny_cpu_assembler import assemble, encode_program
from tiny_cpu_core_trace import CoreMismatch, INPUT_SIGNALS, compare_trace, expected_trace, write_probes
from tiny_cpu_input_boundary import mutate_input
from tiny_cpu_input_stimuli import (check_consumption, load_stimuli, validate_stimuli,
                                    write_stimuli, SCHEMA, bus_offer)
from tiny_cpu_logisim import LogisimError, _inject_rom, resolve_jar, _matrix_program
from tiny_cpu_profiles import load_profile

CASES = ROOT / "hardware/logisim/tinycpu_input_cases.json"


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def load_cases(path=CASES):
    document = json.loads(path.read_text(encoding="utf-8"))
    if set(document) != {"schema", "cases"} or document["schema"] != "tinycpu-input-cases-v1":
        raise ValueError("invalid INPUT case matrix")
    names = set()
    for case in document["cases"]:
        if set(case) != {"name", "program", "inputs", "events", "checks"} or not case["checks"]:
            raise ValueError("invalid INPUT case")
        if case["name"] in names or not case["name"].replace("-", "").isalnum():
            raise ValueError("duplicate/unsafe INPUT case name")
        names.add(case["name"])
        validate_stimuli(case["inputs"])
    if not names:
        raise ValueError("empty INPUT case matrix")
    return document["cases"]


def fixed_expectations(expected, checks):
    """These literal matrix values are checked before using VM rows as oracle."""
    rows = {(r["edge"], r["phase"]): r for r in expected}
    for check in checks:
        row = rows[(check["edge"], check["phase"])]
        for signal, wanted in check["values"].items():
            if row[signal] != wanted:
                raise ValueError(f"fixed expectation differs at {check['edge']} {check['phase']} "
                                 f"{signal}: {wanted} != {row[signal]}")


def baseline_cases():
    """Reuse every existing ROM, including illegal raw opcodes, on the input top."""
    matrix = json.loads((ROOT / "hardware/logisim/tinycpu-electrical-matrix-v1.json").read_text())
    for fixture in [*matrix["opcode_cases"], *matrix["fixtures"]]:
        program = _matrix_program(fixture, load_profile())
        rows = expected_trace(program)
        offers, events = [], []
        for row in rows[::2]:
            is_input = program.instructions[row["PC"]].mnemonic == "INPUT"
            offers.append(bus_offer(row["edge"], source="empty" if is_input else "idle"))
            if is_input:
                events.append({"edge": row["edge"], "source": "empty", "entry": None})
        case = {"name": str(fixture["id"]), "program": str(fixture.get("program", "")),
                "inputs": {"schema": SCHEMA, "edges": offers}, "events": events, "checks": []}
        yield case, program, tuple(fixture.get("raw_words") or encode_program(program))


def run_case(source, output, jar, java, case, mutation=None, *, program=None, words=None):
    output.mkdir(parents=True, exist_ok=True)
    for stale in ("diagnostic.json", "consumption.json"):
        (output / stale).unlink(missing_ok=True)
    save(output / "inputs.json", case["inputs"])
    # Parse the serialized evidence through the same strict external contract.
    inputs = load_stimuli(output / "inputs.json")
    program = program if program is not None else assemble(case["program"])
    words = words if words is not None else tuple(encode_program(program))
    expected = expected_trace(program, stimuli=inputs)
    fixed_expectations(expected, case["checks"])
    save(output / "expected.json", expected)
    save(output / "expected-events.json", case["events"])
    save(output / "fixed-checks.json", case["checks"])
    save(output / "rom-words.json", words)
    (output / "program.tcpu").write_text(case["program"], encoding="utf-8")
    write_stimuli(output / "stimuli.tsv", inputs)
    write_probes(output / "probes.tsv", signals=INPUT_SIGNALS)
    tree = ET.parse(source)
    _inject_rom(tree.getroot(), source, words)
    if mutation:
        mutate_input(tree.getroot(), mutation)
    tree.write(output / "TinyCPU.circ", encoding="utf-8", xml_declaration=True)
    command = [java, "-Djava.awt.headless=true", "-cp", str(jar.resolve()),
               str(ROOT / "scripts/LogisimCoreTrace.java"), "TinyCPUInputMain",
               str((output / "TinyCPU.circ").resolve()), str((output / "probes.tsv").resolve()),
               str(len(inputs["edges"])), "--inputs", str((output / "stimuli.tsv").resolve()),
               str((output / "consumption.tsv").resolve())]
    save(output / "command.json", command)
    with (output / "trace.tsv").open("wb") as stdout, (output / "stderr.txt").open("wb") as stderr:
        try:
            result = subprocess.run(command, stdout=stdout, stderr=stderr, timeout=45, check=False)
        except subprocess.TimeoutExpired as exc:
            raise LogisimError(f"fixture {case['name']}: exporter timed out; evidence: {output}") from exc
    if result.returncode:
        raise LogisimError(f"fixture {case['name']}: exporter exited {result.returncode}; evidence: {output}")
    try:
        compare_trace((output / "trace.tsv").read_text(encoding="utf-8"), expected, signals=INPUT_SIGNALS)
        consumption = check_consumption((output / "consumption.tsv").read_text(encoding="utf-8"),
                                        inputs, case["events"])
    except (CoreMismatch, ValueError) as exc:
        save(output / "diagnostic.json", {"fixture": case["name"], **(vars(exc) if isinstance(exc, CoreMismatch)
                                                                    else {"error": str(exc)})})
        raise
    save(output / "consumption.json", consumption)
    return {"edges": len(inputs["edges"]), **consumption}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/input-dynamic")
    parser.add_argument("--java", default=os.environ.get("JAVA", "java"))
    parser.add_argument("--baseline-matrix", action="store_true",
                        help="also compare all existing core fixtures on TinyCPUInputMain with inactive input")
    parser.add_argument("--jar", type=Path, default=Path(os.environ["LOGISIM_JAR"]) if os.environ.get("LOGISIM_JAR") else None)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    proof = args.output / "proof.json"
    proof.unlink(missing_ok=True)
    source = ROOT / "hardware/logisim/TinyCPU.circ"
    originals = {p: p.read_bytes() for p in source.parent.rglob("*.circ")}
    jar = resolve_jar(args.jar)
    results, mutations, baseline = {}, {}, {}
    cases = load_cases()
    source_hashes = {p.relative_to(source.parent).as_posix(): hashlib.sha256(data).hexdigest()
                     for p, data in originals.items()}
    summary = {"status": "running", "cases": results, "mutations": mutations, "baseline": baseline,
               "source_sha256": source_hashes}
    save(args.output / "run-summary.json", summary)
    active = None
    try:
        for case in cases:
            active = case["name"]
            results[case["name"]] = run_case(source, args.output / case["name"], jar, args.java, case)
            save(args.output / "run-summary.json", summary)
            print(f"PASS {case['name']}", flush=True)
        for name, base, wanted in [
            ("value", "valid23", (1, "post", "ACC", 23, 42)),
            ("valid", "invalidffff", (1, "post", "ACC_VALID", 0, 1)),
            ("consume", "valid23", (1, "pre", "INPUT_CONSUME", 1, 0)),
        ]:
            case = next(c for c in cases if c["name"] == base)
            active = f"mutation-{name}"
            output = args.output / f"mutation-{name}"
            try:
                run_case(source, output, jar, args.java, case, name)
            except CoreMismatch as exc:
                if (exc.edge, exc.phase, exc.signal, exc.expected, exc.actual) != wanted:
                    raise LogisimError(f"mutation {name} failed at unexpected observation: {exc}") from exc
                # The wrong-value mutation must still reach a correct normal
                # halt; a crash, timeout or missing terminal is no proof.
                lines = (output / "trace.tsv").read_text(encoding="utf-8").splitlines()
                terminal = dict(zip(lines[0].split("\t"), lines[-2].split("\t")))
                if terminal["HALTED"] != "1" or terminal["HALTED_WITH_ERROR"] != "0":
                    raise LogisimError(f"mutation {name} did not reach normal halt")
                mutations[name] = vars(exc)
                print(f"REJECT mutation-{name}: {exc}", flush=True)
            else:
                raise LogisimError(f"INPUT mutation {name} was accepted")
        if args.baseline_matrix:
            for case, program, words in baseline_cases():
                active = f"baseline/{case['name']}"
                baseline[case["name"]] = run_case(source, args.output / active, jar, args.java,
                                                  case, program=program, words=words)
                save(args.output / "run-summary.json", summary)
                print(f"PASS {active}", flush=True)
    except Exception as exc:
        summary.update(status="stopped", fixture=active, error=str(exc))
        if isinstance(exc, CoreMismatch):
            summary["first_difference"] = vars(exc)
        save(args.output / "run-summary.json", summary)
        raise
    finally:
        if any(p.read_bytes() != original for p, original in originals.items()):
            raise LogisimError("dynamic INPUT tests modified source circuits")
        summary["source_circuits_unchanged"] = True
        save(args.output / "run-summary.json", summary)
    summary["status"] = "passed"
    save(args.output / "run-summary.json", summary)
    save(proof, {"scope": "AP22.1 dynamic INPUT" + (" and complete baseline matrix on input top" if args.baseline_matrix else " only"),
                 "cases": results, "mutations": mutations, "baseline": baseline, "source_circuits_unchanged": True,
                 "source_sha256": hashlib.sha256(originals[source]).hexdigest(),
                 "matrix_sha256": hashlib.sha256(CASES.read_bytes()).hexdigest(),
                 "jar_sha256": hashlib.sha256(jar.read_bytes()).hexdigest()})
    print(f"Dynamic INPUT passed: {len(results)} full core/VM cases, independent consumption, three rejected mutations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
