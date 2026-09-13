#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 src/tiny_cpu_verify.py
python3 scripts/check-logisim-circuit.py
python3 -m unittest discover -s tests -v
