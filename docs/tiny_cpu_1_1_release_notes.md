# TinyCPU 1.1.0 release notes

TinyCPU 1.1.0 is the first minor release after the qualified 1.0 baseline. It
keeps the existing 16-bit-data/12-bit-address CPU and version-1 machine format
compatible and packages the additive work completed after 1.0. The release tag
is `tinycpu-v1.1.0`.

## Changes since 1.0.0

- The symbolic debugger provides source mappings, breakpoints, single-step
  execution, deterministic text and JSON state output, and memory-change
  reporting.
- The optional `tinycpu-peripherals-16-12-v1` system adds a memory-mapped
  output port and one maskable, edge-triggered interrupt source. Selecting the
  system is explicit; programs that use the original CPU profile retain their
  previous behaviour.
- `TinyCPU_Operator.circ` adds an operator view with reset, debounced
  single-step, slow-run clocking, and named state indicators without changing
  the `TinyCPUMain` interface.
- The electrical system fixtures, structural mutation checks, and operator
  panel vector test are part of the automated regression suite.

## Compatibility and supported environment

- Existing version-1 machine words, the `tinycpu-16-12` hardware profile, and
  the public `TinyCPUMain` pins are unchanged.
- The debugger, peripheral system, and operator panel are additive. They do
  not become implicit requirements for consumers of the 1.0 CPU boundary.
- Logisim-evolution 4.1.0 and Java 21 or newer remain the supported electrical
  acceptance environment.
- The Python VM remains the reference model; electrical acceptance continues
  to require the pinned Logisim-evolution simulator.

## Known limitation

The automated operator-panel checks cover topology and one-shot STEP pulse
behaviour. The documented manual GUI short test still requires an interactive
desktop and is therefore not claimed by the non-interactive release gate.

## Release procedure

The checked-in `VERSION` file and the machine-readable release contract both
identify this source state as 1.1.0. Before publishing, run the complete
offline and electrical gates on the exact release commit:

```bash
scripts/test-offline.sh
scripts/test-logisim.sh
test "$(cat VERSION)" = "1.1.0"
test "$(git status --porcelain)" = ""
git tag -s tinycpu-v1.1.0 "$(git rev-parse HEAD)" -m "TinyCPU 1.1.0"
```

Create the signed tag only after the release commit has reached the release
branch. This repository change deliberately does not manufacture a tag for an
unmerged commit or claim that the outstanding interactive GUI observation ran
in a headless environment.
