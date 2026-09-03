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
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from tiny_cpu_profiles import DEFAULT_PROFILE, load_profile


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


def autonomous_project(source: Path, destination: Path, top: str) -> None:
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
    if len(rows) < 18:
        raise LogisimError(f"electrical table ended before the 17-edge fixture ({len(rows) - 1} rows)")
    header = re.split(r"\s+", rows[0].strip())
    try:
        halt_column = header.index("halt")
    except ValueError as exc:
        raise LogisimError("electrical table has no halt observation column") from exc
    values = re.split(r"\s+", rows[-1].strip())
    if halt_column >= len(values) or values[halt_column] not in {"1", "0x1"}:
        raise LogisimError("electrical table did not terminate with normal halt asserted")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--jar", type=Path)
    parser.add_argument("--java", default=os.environ.get("JAVA", "java"))
    parser.add_argument("--trace-output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=90)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        profile = load_profile(args.profile)
        if java_major(args.java) < 21:
            raise LogisimError("Java 21 or newer is required")
        jar = resolve_jar(args.jar)
        source = ROOT / "hardware" / "logisim" / str(profile["circuit"])
        with tempfile.TemporaryDirectory(prefix="tinycpu-logisim-") as directory:
            project = Path(directory) / source.name
            autonomous_project(source, project, str(profile["top_circuit"]))
            run_trace(project, jar, args.java, args.trace_output, args.timeout)
        print(f"electrical trace passed: {profile['name']} -> {args.trace_output}")
        return 0
    except (LogisimError, KeyError, OSError, ET.ParseError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
