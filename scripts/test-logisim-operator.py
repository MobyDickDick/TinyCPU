#!/usr/bin/env python3
"""Electrically verify the operator panel's STEP/RUN clock arbitration."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tiny_cpu_logisim import LogisimError, resolve_jar


def main() -> int:
    explicit = Path(os.environ["LOGISIM_JAR"]) if os.environ.get("LOGISIM_JAR") else None
    if explicit is None:
        local = ROOT / ".venv/Include/logisim-evolution-4.1.0-all.jar"
        explicit = local if local.is_file() else None
    jar = resolve_jar(explicit)
    rows = (
        "RESET STEP RUN CPU_CLOCK <set> <seq>\n"
        "0 0 0 0 1 1\n"
        "0 1 0 1 1 2\n"
        "0 1 0 1 1 3\n"
    )
    with tempfile.TemporaryDirectory(prefix="tinycpu-operator-") as directory:
        vector = Path(directory) / "operator-clock.txt"
        vector.write_text(rows, encoding="utf-8")
        result = subprocess.run(
            [os.environ.get("JAVA", "java"), "-cp", str(jar),
             str(ROOT / "scripts/LogisimHeadlessVector.java"), "TinyCPUOperator",
             str(vector), str(ROOT / "hardware/logisim/TinyCPU_Operator.circ")],
            capture_output=True, text=True, timeout=30, check=False,
        )
    if result.returncode:
        raise LogisimError(
            "operator clock arbitration failed: "
            + (result.stdout + result.stderr).strip()
        )
    print("electrical operator-panel acceptance passed: one STEP edge, no held-input retrigger")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
