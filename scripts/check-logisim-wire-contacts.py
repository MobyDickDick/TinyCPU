#!/usr/bin/env python3
"""Repository entry point for the Logisim wire-contact geometry audit."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tiny_cpu_wire_contacts import main

if __name__ == "__main__":
    projects = sys.argv[1:] or [
        str(path) for path in sorted((ROOT / "hardware/logisim").rglob("*.circ"))
    ]
    raise SystemExit(main(projects))
