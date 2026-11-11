# TinyCPU documentation

## Current entry points

Start with the [ten-minute quickstart](tiny_cpu_quickstart.md). Its first
program run uses the existing debugger CLI, requires only Python, and shows
the complete output and exit code.

| Page | Purpose |
|---|---|
| [Architecture and ISA](tiny_cpu.md) | Machine state, syntax, error semantics, implemented tools, executable examples |
| [Test guide](tiny_cpu_test_guide.md) | Current Bash/PowerShell commands, required gates, artifacts, and GUI limits |
| [Instruction status](tiny_cpu_instruction_status.md) | Latest local evidence and remaining acceptance gaps; older results clearly dated |
| [Debugger](tiny_cpu_debugger.md) | CLI/API, breakpoints, input, JSON, and exit codes |
| [Core trace](tiny_cpu_core_trace.md) | Pre/post clock-edge observations and full observed-state comparison |
| [Peripherals](tiny_cpu_peripherals.md) | Optional output-port and interrupt-system contract |
| [Compatibility](tiny_cpu_compatibility.md) | Format boundaries, corrections, and the preserved v1 DIV exception |
| [Hardware guide](../hardware/logisim/README.md) | Circuit files, native launch instructions, and manual GUI procedure |
| [Core sheets](../hardware/logisim/TinyCPU.md) | Functional explanations of the circuit hierarchy |
| [Operator](../hardware/logisim/TinyCPU_Operator.md) | Implemented RESET/STEP/RUN circuit |
| [System sheets](../hardware/logisim/TinyCPU_Peripherals.md) | Integration, output, and interrupt blocks |
| [Runtime provisioning](../vendor/README.md) | Pinned Logisim JAR resolution |
| [Development directions](tiny_cpu_development_directions.md) | Bounded future ideas, after the required quality tasks |

These pages and this index form the current-documentation inventory checked by
[test_tiny_cpu_documentation.py](../tests/test_tiny_cpu_documentation.py).
Its local-file and heading-link checks do not require web access. The central
program examples are executed verbatim and checked for stdout, stderr, and
exit code by the mandatory offline suite.

## Current work and evidence

AP 22.1 and 22.2 are locally accepted. The supported base profile is
**tinycpu-16-12**; the 8/8 experiment is retired. AP 18's optional peripheral
system, AP 21's operator panel, and AP 23's eight-box core overview are
implemented. Their existence does not imply a newly qualified release.

The [10 November local acceptance](tiny_cpu_input_reset_repair.md) covers
63 baseline core fixtures, 23 dynamic INPUT cases, arithmetic/address
boundaries, seven system cases, operator tests, and negative controls.
The [6 November report](tiny_cpu_circuit_repair_20261106.md) records the
arithmetic contract, including the preserved v1 division exception.
The Linux evidence from AP 22.4, common fresh-checkout release acceptance from
AP 22.5, and interactive GUI acceptance remain open.

- [Quality work packages (AP 22)](tiny_cpu_quality_work_packages.md): required next work and acceptance criteria.
- [Roadmap](tiny_cpu_roadmap.md): package sequence and dated progress.
- [Documentation acceptance (AP 22.3)](tiny_cpu_documentation_acceptance.md): scope, fresh source snapshot, commands, and evidence for these pages.

## Binding circuit rules

[AGENTS.md](../AGENTS.md), the [schematic style](tiny_cpu_schematic_style.md),
and the [Logisim rules](../hardware/logisim/AGENTS.md) remain binding. They
include visible wiring without tunnels, protected hand-drawn decoders, and
named interface contracts. Historical layout proposals do not override them.

## Historical plans and diagnosis records

The other dated repair, layout, diagnosis, recovery, and release documents
are project records. Their commands, counts, and open items describe their
stated candidate and date; they are not instructions for the current checkout.
Use the current entry pages above for running programs and tests. In mixed
records such as the roadmap and instruction-status page, the newest status
appears first and older sections retain explicit dates.

Useful records include the [AP 19 diagnosis](tiny_cpu_circuit_debug_plan.md),
[AP 20 recovery](tiny_cpu_recovery_work_packages.md),
[AP 21 operator implementation](tiny_cpu_operator_panel_plan.md),
[AP 23 modularity](tiny_cpu_modularity_plan.md), and
[INPUT reset repair](tiny_cpu_input_reset_repair.md).
The [1.0 notes](tiny_cpu_1_0_release_notes.md) and
[1.1 notes](tiny_cpu_1_1_release_notes.md) retain historical release claims;
they do not replace the open AP 22.5 qualification of the current candidate.
