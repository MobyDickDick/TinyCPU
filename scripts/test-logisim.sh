#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OUTPUT="${LOGISIM_OUTPUT:-artifacts/tinycpu-profile-acceptance}"
profiles=(tinycpu-16-12)
failed=()
mkdir -p "$OUTPUT"

for profile in "${profiles[@]}"; do
  args=(--profile "$profile" --trace-output "$OUTPUT/$profile/core-trace.tsv"
        --matrix-output "$OUTPUT/$profile/isa-matrix"
        --jobs "${LOGISIM_JOBS:-1}")
  if [[ -n "${LOGISIM_JAR:-}" ]]; then
    args+=(--jar "$LOGISIM_JAR")
  fi
  if ! PYTHONPATH=src python3 src/tiny_cpu_logisim.py "${args[@]}"; then
    failed+=("$profile")
  fi
done

if (( ${#failed[@]} )); then
  printf 'electrical profile acceptance failed: %s\n' "${failed[*]}" >&2
  exit 1
fi

printf 'electrical profile acceptance passed: %s\n' "${profiles[*]}"
