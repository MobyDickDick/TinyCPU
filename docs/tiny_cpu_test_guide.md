# Testing TinyCPU.circ yourself

This guide provides the short, recommended procedure for a complete test of
the committed circuit. Run all commands from the root of the TinyLanguage
checkout.

## Prerequisites

- **Java 21 or newer** (`java -version`)
- **Python 3** (`python3 --version`)
- an internet connection for the first run **or** the file
  `logisim-evolution-4.1.0-all.jar`

You do not need to install Logisim separately. Logisim support is part of the
project: circuits, fixtures, launcher, pinned version, and CI provisioning are
checked in. Only the unchanged upstream binary is **not duplicated as a Git
blob**; its conventional local location is documented.
The test script first uses `vendor/logisim-evolution-4.1.0-all.jar` when you
place it there, then checks `~/.cache/tinycpu/`, and only downloads the exact
supported version as a last resort. GitHub Actions caches this download between
runs, so it is not fetched anew for every commit.

## Complete automated test

Before using Java, run the repository's fast offline gate:

```bash
scripts/test-offline.sh
```

It parses every checked-in JSON and Logisim project, rejects malformed circuit
hierarchies, duplicate pin names, recursive subcircuits, missing subcircuits,
zero-length wires, and diagonal wires, and cross-checks the opcode/profile and
electrical-matrix inventories. This is a structural and contract check only;
it does **not** replace the electrical Logisim run below.

## Automated checks for commits and pull requests

The same offline test suite is used locally and by GitHub, so failures can be
found before code is pushed:

```bash
python3 -m pip install pre-commit
pre-commit install
```

After this one-time setup, `.pre-commit-config.yaml` runs
`scripts/test-offline.sh` before every commit. A failing check aborts the
commit. Run `pre-commit run --all-files` to check the complete working tree at
any time. The hook can only protect checkouts in which it has been installed;
the test script may also be run directly without installing `pre-commit`.

GitHub Actions runs the offline command and the electrical profile acceptance
for every push, pull request, and merge queue entry. To prevent failed pull
requests from being merged, configure the repository's protected branch or
ruleset to require **Offline verification and unit tests** and **Electrical
acceptance (all profiles)**. The workflow supplies both checks, while the
branch protection setting in GitHub enforces them.

1. Open a terminal and change to the checkout:

   ```bash
   cd /pfad/zu/TinyLanguage
   ```

2. Check Java:

   ```bash
   java -version
   ```

   The output must report Java 21 or newer.

3. Start the test:

   ```bash
   scripts/test-logisim.sh
   ```

The script loads `TinyCPU.circ` and `TinyCPU-8-8.circ` in the real simulator.
For each profile it runs the complete 17-edge countdown and all isolated programs from
the corresponding electrical matrix: one positive case for every opcode and
the six sticky-error fixtures. Conditional jumps additionally have separate
taken and non-taken programs. The offline gate rejects a matrix that omits an
opcode or repeats a case ID. Results are kept below
`artifacts/tinycpu-profile-acceptance/<profile>/`; a failure in one profile
does not prevent the other profile from being attempted, but the combined
command still exits nonzero.

Logisim's table logger is change-driven: if two clock edges leave every
exported signal unchanged, it emits no duplicate row. Consequently, the raw
table can contain fewer than 17 data rows even though the complete countdown
ran. Logisim's raw table contains values but no column-name header. Acceptance
therefore relies on the autonomous clock together with `table,halt`: successful
termination means that the temporary runner's specially named halt output was
asserted. Before each run, the reference VM determines whether the fixture ends
through `HALTED` or `HALTED_WITH_ERROR`; the launcher renames that expected
event in the temporary copy. Both terminal instructions therefore stop the runner,
whereas a CPU which never halts reaches the launcher timeout. The table row
count is deliberately not treated as a clock-edge counter.

This complete command is a required CI test. A missing simulator, an incomplete
matrix, or any electrical failure causes the run to fail; there is no silent
fallback to a project-loading-only or Python test. The CI artifact preserves
all tables produced before success or failure.

The matrix launcher prints and immediately flushes the profile, fixture number,
fixture count, and fixture ID before starting each isolated Logisim process.
This heartbeat is intentional: every fixture needs a fresh JVM for its injected
ROM, so a complete two-profile run can otherwise look stalled in a buffered CI
log even though electrical simulation is still advancing. The last printed ID
also identifies the fixture to inspect if its per-process timeout is reached.
The acceptance script runs fixtures serially because Logisim JVMs can share
simulator state outside their isolated project directories on hosted runners.
Environments known to isolate that state may opt into concurrency with, for
example, `LOGISIM_JOBS=2`; CI deliberately prioritizes reproducibility. A
fixture failure includes its profile and ID in the final error message.
In the default serial mode the launcher stops immediately at that fixture; it
does not print or execute the remaining matrix entries after a failure.

The `LOAD_ADDRESS_REGISTER_PLUS_OFFSET` acceptance case also guards a physical
top-level junction: the address path's register-plus-offset sum must branch to
the effective-address selector. A visually routed but electrically floating
selector input prevents Logisim from settling and appears as a launcher
timeout rather than as an ordinary value mismatch.

### If you already have the Logisim JAR

Pass its path explicitly instead of downloading it:

```bash
LOGISIM_JAR=/pfad/zu/logisim-evolution-4.1.0-all.jar scripts/test-logisim.sh
```

## Inspecting the circuit as well

For a visual inspection, start Logisim-evolution 4.1.0 and open
`hardware/logisim/TinyCPU.circ`. Select the `TinyCPUMain` sheet on the left. You
can inspect signals with the Poke tool; the automated test does not require
changes to the file.

If the large project does not load, first open
`hardware/logisim/smoke/PinPair-1bit.circ`, `PinPair-12bit.circ`, and
`PinPair-16bit.circ` in that order. If they work, use the standalone projects
under `hardware/logisim/diagnostics/` to narrow the problem down to the affected
circuit sheet.

## Common problems

| Message or symptom | Solution |
|---|---|
| `Java 21 or newer is required` | Install Java 21+ or use `JAVA=/pfad/zu/java scripts/test-logisim.sh`. |
| JAR download fails | Download the JAR manually and run `scripts/test-logisim-local.sh /pfad/zur/JAR`. |
| Multiple JAR files found | Pass the desired full path to `scripts/test-logisim-local.sh`. |
| Test fails | Check the first error message and `artifacts/tinycpu-ap12-acceptance/acceptance.json`; an aborted run does not count as passing. |

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
