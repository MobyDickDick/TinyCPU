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
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from tiny_cpu_profiles import DEFAULT_PROFILE, load_profile
from tiny_cpu_assembler import Instruction, Program, assemble, encode_program, opcode_table
from tiny_cpu_systems import load_system_profile
from tiny_cpu_vm import TinyCPU


ROOT = Path(__file__).resolve().parents[1]
LOGISIM_VERSION = "4.1.0"
JAR_NAME = f"logisim-evolution-{LOGISIM_VERSION}-all.jar"
JAR_URL = (
    "https://github.com/logisim-evolution/logisim-evolution/releases/download/"
    f"v{LOGISIM_VERSION}/{JAR_NAME}"
)
CORE_ACCEPTANCE_SOURCE = "LOAD_CONST(3)\nHALT()\n"
VENDORED_JAR = ROOT / "vendor" / JAR_NAME
LOCAL_ENV_JAR = ROOT / ".venv" / "Include" / JAR_NAME


class LogisimError(RuntimeError):
    """A controlled dependency, simulator, or electrical-trace failure."""


def _attributes(component: ET.Element) -> dict[str, ET.Element]:
    return {item.get("name", ""): item for item in component.findall("a")}


def autonomous_project(
    source: Path, destination: Path, top: str, rom_words: tuple[int, ...] | None = None,
    halt_output: str = "HALTED",
) -> None:
    """Add autonomous inputs and select the expected halt in a temporary project."""
    if halt_output not in {"HALTED", "HALTED_WITH_ERROR"}:
        raise LogisimError(f"unsupported halt output: {halt_output!r}")
    tree = ET.parse(source)
    root = tree.getroot()
    circuit = next((item for item in root.findall("circuit") if item.get("name") == top), None)
    if circuit is None:
        raise LogisimError(f"{source}: top circuit {top!r} is missing")

    found: set[str] = set()
    for component in list(circuit.findall("comp")):
        if component.get("name") in {"POR", "PowerOnReset"}:
            circuit.remove(component)
            continue
        if component.get("name") != "Pin":
            continue
        attributes = _attributes(component)
        label = attributes.get("label")
        if label is None or label.get("val") not in {
            "CLK", "RESET", "HALTED", "HALTED_WITH_ERROR",
            "EXTERNAL_MEMORY_VALUE", "EXTERNAL_MEMORY_VALID", "USE_EXTERNAL_MEMORY",
            "INTERRUPT_ACCEPT", "INTERRUPT_TARGET_PC", "ILL_RET",
        }:
            continue
        name = label.get("val", "")
        if name in {"CLK", "RESET", "HALTED", "HALTED_WITH_ERROR"}:
            found.add(name)
        if name == "CLK":
            component.set("lib", "0")
            component.set("name", "Clock")
            for item in list(component):
                component.remove(item)
            ET.SubElement(component, "a", {"name": "label", "val": "TRACE_CLK"})
            ET.SubElement(component, "a", {"name": "highDuration", "val": "2"})
            ET.SubElement(component, "a", {"name": "lowDuration", "val": "2"})
        elif name == "RESET":
            # POR reflects Logisim's simulator-reset state; it does not emit a
            # startup pulse in a headless table run.  Generate a deterministic
            # pulse instead: the inverted slow clock starts high, falls before
            # the first active CPU edge and stays low for the fixture.
            component.set("lib", "1")
            component.set("name", "NOT Gate")
            for item in list(component):
                component.remove(item)
            x, y = (int(value) for value in component.get("loc", "")[1:-1].split(","))
            reset_clock_location = f"({x - 40},{y})"
            reset_clock_output = f"({x - 20},{y})"
            reset_clock = ET.SubElement(
                circuit,
                "comp",
                {"lib": "0", "loc": reset_clock_location, "name": "Clock"},
            )
            ET.SubElement(reset_clock, "a", {"name": "highDuration", "val": "100"})
            ET.SubElement(reset_clock, "a", {"name": "lowDuration", "val": "2"})
            ET.SubElement(
                circuit,
                "wire",
                {"from": reset_clock_location, "to": reset_clock_output},
            )
        elif (name.startswith("EXTERNAL_MEMORY_")
              or name in {"USE_EXTERNAL_MEMORY", "INTERRUPT_ACCEPT",
                          "INTERRUPT_TARGET_PC", "ILL_RET"}):
            # The additive AP-18 interfaces are inactive in every autonomous
            # TinyCPU 1.0 fixture.  Drive them explicitly instead of relying on
            # a simulator-specific value for otherwise floating input pins.
            width = attributes.get("width")
            component.set("lib", "0")
            component.set("name", "Constant")
            for item in list(component):
                component.remove(item)
            if width is not None:
                ET.SubElement(component, "a", {"name": "width", "val": width.get("val", "1")})
            # Pin replacement must preserve the current circuit's explicit
            # inactive levels.  In particular, Logisim's one-bit Constant
            # defaults to one: that is required by the active-low adapter
            # selects, but it falsely asserts the active-high ILL_RET input
            # and makes JUMP_ERROR take its error branch in clean runs.
            inactive_value = "0x0" if name == "ILL_RET" else "0x1"
            ET.SubElement(
                component, "a", {"name": "value", "val": inactive_value}
            )
        elif name == halt_output:
            # Logisim's table,halt mode stops on an asserted output named halt.
            label.set("val", "halt")

    required = {"CLK", "RESET", "HALTED", "HALTED_WITH_ERROR"}
    if found != required:
        raise LogisimError(f"{source}: cannot create autonomous trace (found {sorted(found)})")
    if rom_words is not None:
        _inject_rom(root, source, rom_words)
    tree.write(destination, encoding="utf-8", xml_declaration=True)


def _inject_rom(root: ET.Element, source: Path, rom_words: tuple[int, ...]) -> None:
    """Replace the instruction ROM contents without changing circuit inputs."""
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


def java_major(java: str) -> int:
    result = subprocess.run([java, "-version"], capture_output=True, text=True, check=False)
    text = result.stderr + result.stdout
    match = re.search(r'version "(\d+)', text)
    if result.returncode or match is None:
        raise LogisimError(f"cannot determine Java version using {java!r}")
    return int(match.group(1))


def resolve_jar(
    explicit: Path | None,
    *,
    vendored: Path = VENDORED_JAR,
    local_env: Path = LOCAL_ENV_JAR,
) -> Path:
    """Resolve explicit, vendored, local-environment, cached, then remote JAR."""
    if explicit is not None:
        if not explicit.is_file():
            raise LogisimError(f"Logisim JAR does not exist: {explicit}")
        return explicit
    if vendored.is_file():
        return vendored
    if local_env.is_file():
        return local_env
    cached = Path.home() / ".cache" / "tinycpu" / JAR_NAME
    if not cached.exists():
        cached.parent.mkdir(parents=True, exist_ok=True)
        partial = cached.with_suffix(".part")
        try:
            urllib.request.urlretrieve(JAR_URL, partial)
            partial.replace(cached)
        except OSError as exc:
            partial.unlink(missing_ok=True)
            raise LogisimError(
                f"pinned Logisim JAR was not found at {vendored}, {local_env}, "
                f"or {cached}, "
                f"and version {LOGISIM_VERSION} could not be downloaded: {exc}"
            ) from exc
    return cached


def run_trace(project: Path, jar: Path, java: str, output: Path, timeout: int) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [java, "-jar", str(jar), "-tty", "table,halt", str(project)]
    try:
        result = subprocess.run(command, capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        partial = exc.stdout or b""
        output.write_bytes(partial)
        # The retry is diagnostic only and must not double the gate's timeout.
        unexpected = _unexpected_halt_reached(project, jar, java, min(timeout, 10))
        if unexpected:
            raise LogisimError(
                "Logisim reached the non-selected halt output instead of the "
                f"expected halt within {timeout} seconds"
            ) from exc
        rows = partial.decode("utf-8", errors="replace").splitlines()
        tail = "\n".join(rows[-100:]) if rows else "<no trace rows observed>"
        raise LogisimError(
            f"Logisim trace did not halt within {timeout} seconds\n"
            f"partial trace preserved at {output}\n"
            f"last observed PC/control state (up to 100 rows):\n{tail}"
        ) from exc
    output.write_bytes(result.stdout)
    diagnostics = result.stderr.decode("utf-8", errors="replace").strip()
    if result.returncode:
        raise LogisimError(f"Logisim exited with {result.returncode}: {diagnostics}")
    if not result.stdout.strip():
        raise LogisimError("Logisim produced no electrical table")
    # Logisim's table format contains values only; pin labels are not emitted as
    # a header. With the autonomous clock still running, ``table,halt`` returns
    # only when the specially named halt output is asserted. A circuit which
    # never reaches halt is rejected by the timeout above.
    rows = [row for row in result.stdout.decode("utf-8", errors="replace").splitlines()
            if row.strip()]
    if not rows:
        raise LogisimError("electrical table has no data rows")


def run_core_acceptance(
    source: Path, profile, jar: Path, java: str, output: Path, timeout: int,
) -> None:
    """Run AP 20.4's minimal fetch fixture twice and require determinism."""
    program = assemble(CORE_ACCEPTANCE_SOURCE, profile)
    words = encode_program(program)
    if _expected_halt_output(program) != "HALTED":
        raise LogisimError("core acceptance fixture does not normally halt in the VM")

    with tempfile.TemporaryDirectory(prefix="tinycpu-core-") as directory:
        directory_path = Path(directory)
        traces = []
        for run in (1, 2):
            project = directory_path / f"run-{run}-{source.name}"
            trace = output if run == 1 else directory_path / "repeat.tsv"
            autonomous_project(source, project, profile.top_circuit, words)
            run_trace(project, jar, java, trace, timeout)
            traces.append(trace.read_bytes())
        if traces[0] != traces[1]:
            raise LogisimError("independent core traces are not deterministic")


def _unexpected_halt_reached(
    project: Path, jar: Path, java: str, timeout: int,
) -> bool:
    """Return whether a timed-out run actually reached its other halt output.

    ``autonomous_project`` names only the expected terminal output ``halt``.
    A CPU that reaches the other terminal state otherwise looks exactly like a
    CPU that stopped making progress: both runs time out.  Retry a temporary
    copy with the two terminal labels exchanged so the launcher can preserve
    that important distinction in its diagnostic.
    """
    try:
        tree = ET.parse(project)
        labels = [
            attribute
            for circuit in tree.getroot().findall("circuit")
            for component in circuit.findall("comp")
            if component.get("name") == "Pin"
            for attribute in component.findall("a")
            if attribute.get("name") == "label"
        ]
        selected = next(item for item in labels if item.get("val") == "halt")
        other = next(
            item for item in labels
            if item.get("val") in {"HALTED", "HALTED_WITH_ERROR"}
        )
    except (ET.ParseError, OSError, StopIteration):
        return False

    selected.set("val", "EXPECTED_HALT")
    other.set("val", "halt")
    with tempfile.TemporaryDirectory(prefix="tinycpu-opposite-halt-") as directory:
        diagnostic = Path(directory) / project.name
        tree.write(diagnostic, encoding="utf-8", xml_declaration=True)
        try:
            result = subprocess.run(
                [java, "-jar", str(jar), "-tty", "table,halt", str(diagnostic)],
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return False
    return result.returncode == 0 and bool(result.stdout.strip())


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


def _expected_halt_output(program: Program) -> str:
    """Return the terminal event output selected by the reference execution."""
    cpu = TinyCPU(program)
    limit = max(64, len(program.instructions) * 8)
    for _ in range(limit + 1):
        if cpu.halted:
            return "HALTED_WITH_ERROR" if cpu.halt_error else "HALTED"
        cpu.step()
    raise LogisimError("matrix fixture does not halt in the reference VM")


def run_matrix(
    source: Path, profile, jar: Path, java: str, output: Path, timeout: int,
    jobs: int = 1,
) -> int:
    matrix_path = ROOT / "hardware" / "logisim" / "tinycpu-electrical-matrix-v1.json"
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    cases = [*matrix["opcode_cases"], *matrix["fixtures"]]
    ids = [str(case["id"]) for case in cases]
    if len(ids) != len(set(ids)):
        raise LogisimError(f"{matrix_path}: duplicate fixture id")
    output.mkdir(parents=True, exist_ok=True)
    total = len(cases)
    runs: list[tuple[int, dict[str, object], tuple[int, ...], str]] = []
    for index, case in enumerate(cases, start=1):
        program = _matrix_program(case, profile)
        words = tuple(case.get("raw_words") or encode_program(program))
        # Validate the fixture independently in the reference model. Logisim's
        # table logger is change-driven, so its row count is not an edge count:
        # consecutive clock edges with identical observed outputs are folded.
        _expected_edges(program)
        runs.append((index, case, words, _expected_halt_output(program)))

    def run_case(run: tuple[int, dict[str, object], tuple[int, ...], str]) -> None:
        index, case, words, halt_output = run
        # Report when a worker actually starts the JVM, not when work is merely
        # queued, so the heartbeat continues throughout a parallel matrix run.
        print(
            f"electrical matrix: {profile.name} [{index}/{total}] {case['id']}",
            flush=True,
        )
        with tempfile.TemporaryDirectory(prefix="tinycpu-matrix-") as directory:
            project = Path(directory) / source.name
            autonomous_project(
                source, project, profile.top_circuit, words,
                halt_output=halt_output,
            )
            try:
                run_trace(project, jar, java, output / f"{case['id']}.tsv", timeout)
            except LogisimError as exc:
                raise LogisimError(
                    f"{profile.name} fixture {case['id']}: {exc}"
                ) from exc

    # Do not queue the whole matrix behind a single worker: ThreadPoolExecutor
    # continues with later queued calls after an early failure. That made a
    # failure in fixture 4 appear only after heartbeats 5 through 61. The normal
    # serial gate must instead fail immediately at the responsible fixture.
    if jobs == 1:
        for run in runs:
            run_case(run)
        return len(cases)

    # Explicit parallel runs remain available for environments known to isolate
    # Logisim's shared state. Executor shutdown waits for diagnostic output from
    # work which was already started.
    with ThreadPoolExecutor(max_workers=jobs) as executor:
        futures = [executor.submit(run_case, run) for run in runs]
        for future in futures:
            future.result()
    return len(cases)


def _system_program(case: dict[str, object], system) -> Program:
    """Build one system fixture, placing its handler at the fixed vector."""
    main = assemble(str(case.get("program", "")), system.base_profile, system)
    vector_source = case.get("vector_program")
    if vector_source is None:
        return main
    handler = assemble(str(vector_source), system.base_profile, system)
    if len(main.instructions) > system.interrupt_vector:
        raise LogisimError(f"system fixture {case.get('id')!r} overlaps its vector")
    padding = (Instruction("HALT"),) * (system.interrupt_vector - len(main.instructions))
    return Program(main.instructions + padding + handler.instructions, {}, {},
                   system.base_profile, system)


def _system_expected_states(case: dict[str, object], program: Program) -> list[tuple[bool, bool, TinyCPU]]:
    """Return input levels and post-edge VM states for a matrix fixture."""
    events = {int(item["edge"]): item for item in case.get("events", [])}
    cpu = TinyCPU(program)
    request = False
    states = []
    # Reset scenarios intentionally loop.  Other fixtures run to a terminal
    # state, with a bounded tail that turns wiring mistakes into clear errors.
    reset_scenario = any(bool(item.get("reset")) for item in events.values())
    limit = max(16, len(program.instructions) * 2)
    if reset_scenario:
        limit = max(events, default=0) + 2
    for edge in range(limit):
        event = events.get(edge, {})
        request = bool(event.get("interrupt_request", request))
        reset = bool(event.get("reset", False))
        cpu.step(interrupt_request=request, reset=reset)
        states.append((request, reset, TinyCPU(
            program, pc=cpu.pc, accumulator=cpu.accumulator,
            accumulator_valid=cpu.accumulator_valid,
            address_register=cpu.address_register,
            address_register_valid=cpu.address_register_valid,
            memory=dict(cpu.memory), errors=dict(cpu.errors), output=list(cpu.output),
            halted=cpu.halted, halt_error=cpu.halt_error,
            output_port=cpu.output_port, output_port_valid=cpu.output_port_valid,
            interrupts_enabled=cpu.interrupts_enabled,
            interrupt_pending=cpu.interrupt_pending,
            in_interrupt_handler=cpu.in_interrupt_handler,
            return_address=cpu.return_address,
            return_address_valid=cpu.return_address_valid,
            _interrupt_level=cpu._interrupt_level,
        )))
        if cpu.halted and not reset_scenario:
            return states
    if not reset_scenario:
        raise LogisimError(f"system fixture {case.get('id')!r} does not halt in the VM")
    return states


def _write_system_vector(path: Path, states: list[tuple[bool, bool, TinyCPU]]) -> None:
    """Write a sequential Logisim vector with one checked row per clock level."""
    header = ("CLK RESET INTERRUPT_REQUEST OUTPUT_PORT_VALUE[16] "
              "OUTPUT_PORT_VALID INTERRUPT_ENABLED INTERRUPT_PENDING "
              "IN_INTERRUPT_HANDLER RET_ADDR[12] RET_ADDR_VALID <set> <seq>")
    rows = [header]
    initial = TinyCPU(states[0][2].program)

    def values(clock: int, reset: bool, request: bool, cpu: TinyCPU, seq: int) -> str:
        return (f"{clock} {int(reset)} {int(request)} "
                f"0x{cpu.output_port & 0xffff:04x} {int(cpu.output_port_valid)} "
                f"{int(cpu.interrupts_enabled)} {int(cpu.interrupt_pending)} "
                f"{int(cpu.in_interrupt_handler)} 0x{cpu.return_address & 0xfff:03x} "
                f"{int(cpu.return_address_valid)} 1 {seq}")

    first_request, first_reset, _ = states[0]
    rows.append(values(0, first_reset, first_request, initial, 1))
    sequence = 2
    for index, (request, reset, cpu) in enumerate(states):
        rows.append(values(1, reset, request, cpu, sequence))
        sequence += 1
        if index + 1 < len(states):
            next_request, next_reset, _ = states[index + 1]
            rows.append(values(0, next_reset, next_request, cpu, sequence))
            sequence += 1
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def run_system_matrix(system, jar: Path, java: str, output: Path, timeout: int) -> int:
    """Execute AP-18's sequential vectors against the peripheral circuit."""
    matrix = json.loads(system.electrical_matrix_path.read_text(encoding="utf-8"))
    cases = matrix["cases"]
    output.mkdir(parents=True, exist_ok=True)
    for index, case in enumerate(cases, 1):
        print(f"electrical system matrix: {system.name} [{index}/{len(cases)}] "
              f"{case['id']}", flush=True)
        program = _system_program(case, system)
        states = _system_expected_states(case, program)
        with tempfile.TemporaryDirectory(prefix="tinycpu-system-matrix-") as directory:
            temporary = Path(directory)
            project = temporary / system.circuit_path.name
            core = temporary / system.base_profile.circuit
            project.write_bytes(system.circuit_path.read_bytes())
            tree = ET.parse(ROOT / "hardware/logisim" / system.base_profile.circuit)
            _inject_rom(tree.getroot(), core, tuple(encode_program(program)))
            tree.write(core, encoding="utf-8", xml_declaration=True)
            vector = temporary / f"{case['id']}.txt"
            _write_system_vector(vector, states)
            command = [java, "-jar", str(jar), "--test-vector", system.top_circuit,
                       str(vector), str(project)]
            # Logisim 4.1.0's test-vector entry point initializes Swing even
            # though the evaluator itself is non-interactive.
            if not os.environ.get("DISPLAY"):
                xvfb = shutil.which("xvfb-run")
                if xvfb is None:
                    raise LogisimError(
                        "system matrix requires DISPLAY or xvfb-run because "
                        "Logisim's test-vector launcher initializes Swing"
                    )
                command = [xvfb, "-a", *command]
            try:
                result = subprocess.run(command, capture_output=True, text=True,
                                        timeout=timeout, check=False)
            except subprocess.TimeoutExpired as exc:
                raise LogisimError(f"system fixture {case['id']}: timed out") from exc
            evidence = output / f"{case['id']}.txt"
            evidence.write_text(result.stdout + result.stderr, encoding="utf-8")
            if result.returncode:
                raise LogisimError(
                    f"system fixture {case['id']} failed; evidence: {evidence}"
                )
    return len(cases)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default=DEFAULT_PROFILE.name)
    parser.add_argument("--system")
    parser.add_argument("--jar", type=Path)
    parser.add_argument("--java", default=os.environ.get("JAVA", "java"))
    parser.add_argument("--trace-output", type=Path, required=True)
    parser.add_argument("--matrix-output", type=Path)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--jobs", type=int, default=1)
    args = parser.parse_args(argv)
    if args.jobs < 1:
        parser.error("--jobs must be at least 1")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        profile = load_profile(args.profile)
        if java_major(args.java) < 21:
            raise LogisimError("Java 21 or newer is required")
        jar = resolve_jar(args.jar)
        source = ROOT / "hardware" / "logisim" / profile.circuit
        print(f"electrical trace: {profile.name} core (2 runs)", flush=True)
        run_core_acceptance(
            source, profile, jar, args.java, args.trace_output, args.timeout
        )
        if args.matrix_output is not None:
            count = run_matrix(
                source, profile, jar, args.java, args.matrix_output, args.timeout, args.jobs
            )
            print(f"electrical matrix passed: {profile.name} ({count} fixtures)")
        if args.system is not None:
            if args.matrix_output is None:
                raise LogisimError("--system requires --matrix-output")
            system = load_system_profile(args.system)
            if system.base_profile.name != profile.name:
                raise LogisimError(
                    f"system {system.name!r} requires profile {system.base_profile.name!r}"
                )
            count = run_system_matrix(
                system, jar, args.java, args.matrix_output / "system", args.timeout
            )
            print(f"electrical system matrix passed: {system.name} ({count} fixtures)")
        print(f"electrical trace passed: {profile.name} -> {args.trace_output}")
        return 0
    except (LogisimError, KeyError, OSError, ET.ParseError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
