#!/usr/bin/env python3
"""Run the pinned Logisim-evolution load and electrical table gate.

The launcher deliberately keeps the simulator boundary small.  It selects the
project from the hardware profile, creates an autonomous temporary copy and
stores Logisim's unmodified table output as evidence.  The table is required
to reach the normal-halt output; a project which merely parses is not accepted
as an electrical run.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from tiny_cpu_profiles import DEFAULT_PROFILE, load_profile
from tiny_cpu_assembler import Instruction, Program, assemble, encode_program, opcode_table
from tiny_cpu_vm import TinyCPU


ROOT = Path(__file__).resolve().parents[1]
LOGISIM_VERSION = "4.1.0"
JAR_NAME = f"logisim-evolution-{LOGISIM_VERSION}-all.jar"
JAR_URL = (
    "https://github.com/logisim-evolution/logisim-evolution/releases/download/"
    f"v{LOGISIM_VERSION}/{JAR_NAME}"
)
VENDORED_JAR = ROOT / "vendor" / JAR_NAME


class LogisimError(RuntimeError):
    """A controlled dependency, simulator, or electrical-trace failure."""


def _attributes(component: ET.Element) -> dict[str, ET.Element]:
    return {item.get("name", ""): item for item in component.findall("a")}


def autonomous_project(
    source: Path, destination: Path, top: str, rom_words: tuple[int, ...] | None = None
) -> None:
    """Replace only the top-level clock/reset pins in a temporary project."""
    tree = ET.parse(source)
    root = tree.getroot()
    circuit = next((item for item in root.findall("circuit") if item.get("name") == top), None)
    if circuit is None:
        raise LogisimError(f"{source}: top circuit {top!r} is missing")

    found: set[str] = set()
    for component in circuit.findall("comp"):
        if component.get("name") != "Pin":
            continue
        attributes = _attributes(component)
        label = attributes.get("label")
        if label is None or label.get("val") not in {"CLK", "RESET", "HALTED"}:
            continue
        name = label.get("val", "")
        found.add(name)
        if name == "CLK":
            component.set("lib", "0")
            component.set("name", "Clock")
            for item in list(component):
                component.remove(item)
            ET.SubElement(component, "a", {"name": "label", "val": "TRACE_CLK"})
        elif name == "RESET":
            component.set("lib", "0")
            component.set("name", "PowerOnReset")
            for item in list(component):
                component.remove(item)
        else:
            # Logisim's `table,halt` mode stops on an asserted output named halt.
            label.set("val", "halt")

    if found != {"CLK", "RESET", "HALTED"}:
        raise LogisimError(f"{source}: cannot create autonomous trace (found {sorted(found)})")
    if rom_words is not None:
        rom = next((component for owner in root.findall("circuit")
                    for component in owner.findall("comp")
                    if component.get("name") == "ROM"
                    and _attributes(component).get("label") is not None
                    and _attributes(component)["label"].get("val") == "INSTRUCTION_ROM"), None)
        if rom is None:
            raise LogisimError(f"{source}: INSTRUCTION_ROM is missing")
        attributes = _attributes(rom)
        contents = attributes.get("contents")
        if contents is None:
            raise LogisimError(f"{source}: INSTRUCTION_ROM has no contents")
        contents.text = (f"addr/data: {attributes['addrWidth'].get('val')} "
                         f"{attributes['dataWidth'].get('val')}\n"
                         + " ".join(f"{word:x}" for word in rom_words) + "\n")
    tree.write(destination, encoding="utf-8", xml_declaration=True)


def java_major(java: str) -> int:
    result = subprocess.run([java, "-version"], capture_output=True, text=True, check=False)
    text = result.stderr + result.stdout
    match = re.search(r'version "(\d+)', text)
    if result.returncode or match is None:
        raise LogisimError(f"cannot determine Java version using {java!r}")
    return int(match.group(1))


def resolve_jar(explicit: Path | None, *, vendored: Path = VENDORED_JAR) -> Path:
    """Resolve explicit, repository-vendored, cached, then downloadable JAR."""
    if explicit is not None:
        if not explicit.is_file():
            raise LogisimError(f"Logisim JAR does not exist: {explicit}")
        return explicit
    if vendored.is_file():
        return vendored
    cached = Path.home() / ".cache" / "tinycpu" / JAR_NAME
    if not cached.exists():
        cached.parent.mkdir(parents=True, exist_ok=True)
        partial = cached.with_suffix(".part")
        try:
            urllib.request.urlretrieve(JAR_URL, partial)
            partial.replace(cached)
        except OSError as exc:
            partial.unlink(missing_ok=True)
            raise LogisimError(f"cannot download pinned Logisim {LOGISIM_VERSION}: {exc}") from exc
    return cached


def run_trace(project: Path, jar: Path, java: str, output: Path, timeout: int) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [java, "-jar", str(jar), "-tty", "table,halt", str(project)]
    try:
        result = subprocess.run(command, capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        output.write_bytes(exc.stdout or b"")
        raise LogisimError(f"Logisim trace did not halt within {timeout} seconds") from exc
    output.write_bytes(result.stdout)
    diagnostics = result.stderr.decode("utf-8", errors="replace").strip()
    if result.returncode:
        raise LogisimError(f"Logisim exited with {result.returncode}: {diagnostics}")
    if not result.stdout.strip():
        raise LogisimError("Logisim produced no electrical table")
    # table,halt returning successfully is only meaningful if the designated
    # halt column was asserted.  Accept Logisim's binary and decimal displays.
    rows = [row for row in result.stdout.decode("utf-8", errors="replace").splitlines()
            if row.strip()]
    if len(rows) < 2:
        raise LogisimError("electrical table has no data rows")
    header = re.split(r"\s+", rows[0].strip())
    try:
        halt_column = header.index("halt")
    except ValueError as exc:
        raise LogisimError("electrical table has no halt observation column") from exc
    values = re.split(r"\s+", rows[-1].strip())
    if halt_column >= len(values) or values[halt_column] not in {"1", "0x1"}:
        raise LogisimError("electrical table did not terminate with normal halt asserted")


def _matrix_program(case: dict[str, object], profile) -> Program:
    """Assemble one matrix case, preserving deliberately illegal raw opcodes."""
    program = assemble(str(case.get("program", "")), profile)
    raw = case.get("raw_words")
    if not raw:
        return program
    by_code = {int(item["code"]): str(item["mnemonic"])
               for item in opcode_table(profile).values()}
    instructions = []
    for word in raw:
        code = int(word) >> profile.data_bits
        operand = int(word) & profile.data_mask
        instructions.append(Instruction(by_code.get(code, "__ILLEGAL__"), operand))
    return Program(tuple(instructions), {}, {}, profile)


def _expected_edges(program: Program) -> int:
    cpu = TinyCPU(program)
    edges = 0
    limit = max(64, len(program.instructions) * 8)
    while not cpu.halted and edges <= limit:
        cpu.step()
        edges += 1
    if not cpu.halted:
        raise LogisimError("matrix fixture does not halt in the reference VM")
    return edges


def run_matrix(
    source: Path, profile, jar: Path, java: str, output: Path, timeout: int
) -> int:
    matrix_path = ROOT / "hardware" / "logisim" / (
        "tinycpu-electrical-matrix-8-v1.json"
        if profile.name == "tinycpu-8-8" else "tinycpu-electrical-matrix-v1.json"
    )
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    cases = [*matrix["opcode_cases"], *matrix["fixtures"]]
    ids = [str(case["id"]) for case in cases]
    if len(ids) != len(set(ids)):
        raise LogisimError(f"{matrix_path}: duplicate fixture id")
    output.mkdir(parents=True, exist_ok=True)
    for case in cases:
        program = _matrix_program(case, profile)
        words = tuple(case.get("raw_words") or encode_program(program))
        # Validate the fixture independently in the reference model. Logisim's
        # table logger is change-driven, so its row count is not an edge count:
        # consecutive clock edges with identical observed outputs are folded.
        _expected_edges(program)
        with tempfile.TemporaryDirectory(prefix="tinycpu-matrix-") as directory:
            project = Path(directory) / source.name
            autonomous_project(source, project, profile.top_circuit, words)
            run_trace(project, jar, java, output / f"{case['id']}.tsv", timeout)
    return len(cases)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default=DEFAULT_PROFILE.name)
    parser.add_argument("--jar", type=Path)
    parser.add_argument("--java", default=os.environ.get("JAVA", "java"))
    parser.add_argument("--trace-output", type=Path, required=True)
    parser.add_argument("--matrix-output", type=Path)
    parser.add_argument("--timeout", type=int, default=90)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        profile = load_profile(args.profile)
        if java_major(args.java) < 21:
            raise LogisimError("Java 21 or newer is required")
        jar = resolve_jar(args.jar)
        source = ROOT / "hardware" / "logisim" / profile.circuit
        with tempfile.TemporaryDirectory(prefix="tinycpu-logisim-") as directory:
            project = Path(directory) / source.name
            autonomous_project(source, project, profile.top_circuit)
            run_trace(project, jar, args.java, args.trace_output, args.timeout)
        if args.matrix_output is not None:
            count = run_matrix(source, profile, jar, args.java, args.matrix_output, args.timeout)
            print(f"electrical matrix passed: {profile.name} ({count} fixtures)")
        print(f"electrical trace passed: {profile.name} -> {args.trace_output}")
        return 0
    except (LogisimError, KeyError, OSError, ET.ParseError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
