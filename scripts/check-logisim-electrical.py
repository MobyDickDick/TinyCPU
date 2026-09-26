#!/usr/bin/env python3
"""Run Logisim's own truth-table evaluator and reject electrical E/U values."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVALID_VALUE = re.compile(r"(?<![0-9A-Za-z_])[EU](?![0-9A-Za-z_])")


def evaluate(project: Path, jar: Path, circuit: str | None = None) -> list[str]:
    command = ["java", "-jar", str(jar)]
    if circuit:
        command += ["--toplevel-circuit", circuit]
    command += ["-tty", "table", str(project)]
    result = subprocess.run(command, cwd=project.parent, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(
            f"Logisim exited with status {result.returncode}:\n{result.stdout.rstrip()}"
        )
    rows = [line for line in result.stdout.splitlines()
            if line.strip() and not line.startswith(("[", "Sep ", "INFO "))]
    if len(rows) < 2:
        raise RuntimeError(f"Logisim produced no truth-table rows:\n{result.stdout.rstrip()}")
    return [line for line in rows[1:] if INVALID_VALUE.search(line)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="reject undefined (U) and electrical-error (E) Logisim outputs"
    )
    parser.add_argument("projects", nargs="+", type=Path)
    parser.add_argument("--jar", type=Path,
                        default=Path(os.environ.get(
                            "LOGISIM_JAR",
                            ROOT / ".venv/Include/logisim-evolution-4.1.0-all.jar")))
    parser.add_argument("--circuit", help="evaluate this circuit as the top level")
    args = parser.parse_args(argv)
    if not args.jar.is_file():
        parser.error(f"Logisim JAR not found: {args.jar}")

    failed = False
    for project in args.projects:
        try:
            invalid = evaluate(project.resolve(), args.jar.resolve(), args.circuit)
        except RuntimeError as error:
            print(f"{project}: {error}", file=sys.stderr)
            failed = True
            continue
        if invalid:
            failed = True
            print(f"{project}: electrical E/U value in Logisim truth table:", file=sys.stderr)
            for row in invalid:
                print(f"  {row}", file=sys.stderr)
        else:
            suffix = f" ({args.circuit})" if args.circuit else ""
            print(f"{project}{suffix}: electrical outputs defined")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
