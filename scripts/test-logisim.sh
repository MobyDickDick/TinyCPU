#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OUTPUT="${LOGISIM_OUTPUT:-artifacts/tinycpu-ap17-8-8}"
args=(--profile tinycpu-8-8 --trace-output "$OUTPUT/core-trace.tsv")
if [[ -n "${LOGISIM_JAR:-}" ]]; then
  args+=(--jar "$LOGISIM_JAR")
fi
PYTHONPATH=src python3 src/tiny_cpu_logisim.py "${args[@]}"
