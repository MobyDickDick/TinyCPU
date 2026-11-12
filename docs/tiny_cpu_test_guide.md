# Testing TinyCPU yourself

Run commands from the **TinyCPU repository root**. The
[quickstart](tiny_cpu_quickstart.md) runs the Python reference model; this page
covers offline checks and the actual Logisim circuit.

## Prerequisites

Use Python 3.12 or newer (CI uses 3.12). The offline suite uses only the Python
standard library. Electrical tests additionally need Java 21 or newer and the
pinned Logisim-evolution **4.1.0** JAR. On Linux, provide an X display or Xvfb
for the native vector runners; CI installs Xvfb. Shell gates require Bash.

The launcher uses `LOGISIM_JAR` or `--jar` when supplied, otherwise the
[vendor location](../vendor/README.md), then the local TinyCPU cache, then the
pinned upstream download. An available JAR avoids network access.

## Offline gate

Under Bash:

```bash
scripts/test-offline.sh
```

Under native PowerShell, run the same three checks individually and verify
that each exits 0 (`$LASTEXITCODE` after each command):

```powershell
python src/tiny_cpu_verify.py
python scripts/check-logisim-circuit.py
python -m unittest discover -s tests -v
```

These check JSON/ISA/profile contracts, circuit structure and named wiring,
layout constraints, VM/tool behavior, executable documentation examples, and
local links on the current documentation pages. They reject malformed or
missing connections but do not replace electrical simulation. The suite's
current-page inventory is in
[`test_tiny_cpu_documentation.py`](../tests/test_tiny_cpu_documentation.py);
linked historical records retain their dated commands.

## Complete electrical gate

Use Bash (including Git Bash on Windows):

```bash
scripts/test-logisim.sh
```

An explicit local runtime can be selected without changing system settings:

```bash
JAVA='/path/to/java' LOGISIM_JAR='/path/to/logisim-evolution-4.1.0-all.jar' scripts/test-logisim.sh
```

Replace both placeholders with real paths. The gate runs the one supported
base profile, `tinycpu-16-12`; the 8/8 experiment is retired. The complete
matrix is mandatory, with no `TINYCPU_FULL_ACCEPTANCE` switch. It includes:

- two deterministic minimal-core runs, the 17-instruction countdown, and all
  63 baseline ISA/error fixtures with full observed-state comparison;
- 23 dynamic INPUT cases, three INPUT error copies, and the 63 baseline
  fixtures through the input top with inactive input;
- targeted decode, STORE, PRINT, immediate/address, arithmetic, and mutation
  regressions;
- all seven optional peripheral-system cases and operator clock/core checks.

The [core comparator](tiny_cpu_core_trace.md) compares pre/post observations
at each driven rising edge: PC, registers and validity, flags, output events,
write requests, and RAM. The separate INPUT ledger checks consumption. The
older autonomous `table,halt` run is still supplementary; its change-driven
row count is not an instruction count, and reaching halt alone is insufficient.

Fixtures run serially by default and report their ID before execution. A
failed fixture stops its serial matrix at the first difference, which names
the edge, phase, signal, expected and observed value. The shell gate attempts
its remaining independent check groups, then exits nonzero if any failed.
`LOGISIM_JOBS` can opt into parallel baseline fixtures; the default is 1.

Raw traces and reports remain below
`artifacts/tinycpu-profile-acceptance/` (override with `LOGISIM_OUTPUT`). In
particular, inspect `tinycpu-16-12/isa-matrix/`, `input/`,
`tinycpu-peripherals-16-12-v1/system-matrix/`, and `operator-core/`, together
with the first error message. A partial artifact directory is not a pass.

## Focused native PowerShell diagnostic

For the baseline core and matrix only:

```powershell
python src/tiny_cpu_logisim.py --trace-output artifacts/core/core.tsv --matrix-output artifacts/core/isa
```

Add `--java 'C:/path/to/java.exe'` and `--jar 'C:/path/to/logisim-evolution-4.1.0-all.jar'`
if needed. This diagnostic does not replace INPUT, system, operator, or the
other regressions in the full shell gate. The 10 November
[local acceptance record](tiny_cpu_input_reset_repair.md) documents how those
same Python subcommands were run where sandbox restrictions prevented Bash.

## CI and manual inspection

[GitHub Actions](../.github/workflows/tests.yml) runs the offline gate with
Python 3.12 and the electrical gate with Java 21 on Linux, preserving electrical
artifacts even on failure. The existing check names are **Offline verification
and unit tests** and **Electrical acceptance (all profiles)**; the latter is
a retained CI name, not evidence that multiple base profiles are supported.
A configured workflow is not proof of a completed Linux run for this candidate.

The optional pre-commit hook runs the offline gate after installing
`pre-commit` and running `pre-commit install`; use `pre-commit run --all-files`
for a manual hook run. Direct execution needs no hook installation.

Open [TinyCPU.circ](../hardware/logisim/TinyCPU.circ) to inspect the core or
[TinyCPU_Operator.circ](../hardware/logisim/TinyCPU_Operator.circ) for the
implemented RESET/STEP/RUN panel. If loading fails, start with the
[one-bit smoke project](../hardware/logisim/smoke/PinPair-1bit.circ) and the
[standalone diagnostics](../hardware/logisim/diagnostics/).
The [manual GUI procedure](../hardware/logisim/README.md#manueller-gui-kurztest)
requires visible interaction and a recorded result. It remains open. Neither
an automated operator test nor an Xvfb process completes it.

The [current status](tiny_cpu_instruction_status.md) links the latest local
acceptance. Fresh-checkout release qualification (AP 22.5) and Linux CI evidence
(AP 22.4) remain separate open tasks.

# Topological circuit tests

`hardware/logisim/TinyCPU.circ` is a manually maintained drawing. Its electrical
interface, not its arrangement on the canvas, is the test contract. Circuit
tests therefore always name the circuit sheet, component, source port, and
destination port. A test must neither compare fixed `loc` coordinates nor
calculate the connection coordinates of an automatically generated subcircuit
component from its position.

This rule applies to **every** circuit sheet and also to textual acceptance
tests: names, docstrings, and error messages describe, for example,
“`FetchDecode.PC_OUT` reaches `Datapath`” rather than “wire `(x1,y1)` reaches
`(x2,y2)`.” Absolute points are permitted only in synthetic, local XML fixtures
that test the netlist parser itself.

When making corrections, always use the latest user-maintained circuit as the
baseline. A failed historical layout test never justifies copying back an older
drawing. First reproduce the electrical fault at named ports; then correct the
circuit and test together against this topological contract.

The checkout gate `PYTHONPATH=src python3 src/tiny_cpu_verify.py` also enforces
this contract. It requires unique names for all sheet ports and subcircuit
instances, then checks open ports, multiple drivers, and bus widths on the
networks that are actually connected. Electrically relevant individual
components are identified by their `label`; their `loc` position is neither
their identity nor an expected value of the check.
