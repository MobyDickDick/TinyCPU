# TinyCPU in ten minutes

This page is the shortest path from “I do not know how TinyCPU works” to a
running program. It deliberately describes the architectural idea before the
Logisim wiring. For the complete instruction reference, see
[`tiny_cpu.md`](tiny_cpu.md); for the circuit test procedure, see
[`tiny_cpu_test_guide.md`](tiny_cpu_test_guide.md).

## The machine in one picture

```text
 program ROM --instruction--> control unit --control signals--+
       ^                                                       |
       |                                                       v
 program counter                                      +----------------+
       ^                                               | accumulator    |
       |                                               | address reg.   |
       +-------- next PC / jump -----------------------| ALU and flags  |
                                                       +-------+--------+
                                                               |
                                                       data + valid bit
                                                               |
                                                       +-------v--------+
 input queue ----------------------------------------->| data memory    |---> output
                                                       +----------------+
```

TinyCPU is an accumulator machine. Most calculations use the **accumulator**
and replace its value. The **program counter (PC)** selects the next
instruction from program ROM. An optional **address register** helps select a
data-memory cell. The control unit decodes the current instruction and enables
the required register, ALU, memory, jump, or I/O path at the next clock edge.

The accepted hardware profile has 16-bit signed data, 12-bit addresses, and
4,096 memory cells. Program ROM and data RAM are deliberately separate in the
current design. Every data location and important data register carries both a
value and a **valid** bit. Invalid input therefore propagates explicitly rather
than silently becoming an ordinary number.

## What happens during one instruction

Conceptually, one instruction performs four steps:

1. The PC selects an instruction in ROM.
2. The control unit decodes its opcode and operand; the next sequential PC is
   prepared.
3. The selected source is read and the ALU, memory, branch, or I/O action is
   evaluated.
4. On the active clock edge, the new PC, accumulator, memory value, validity,
   and sticky error flags are committed together.

A normal `HALT()` and `HALT_ERROR()` are distinct observable states. Arithmetic
overflow, division by zero, an invalid value, an illegal instruction, an
invalid address, or unavailable input sets a sticky error flag. `CLEAR_ERROR()`
clears flags but cannot make invalid data valid again.

## Follow a tiny program

```text
LOAD_CONST(3)       ; accumulator = 3, valid = true
STORE_ADDRESS(10)   ; memory[10] = 3, valid = true
LOAD_CONST(2)       ; accumulator = 2
ADD_ADDRESS(10)     ; accumulator = 2 + memory[10] = 5
PRINT()             ; emit 5
HALT()              ; stop normally
```

The data flow is easier to understand by watching these values after each
instruction: `PC`, accumulator value and validity, address register, selected
memory value and validity, all error flags, output enable/value/validity, and
the two halt outputs.

## Run it without the circuit GUI

Use Python 3.12 or newer from the repository root. These single-line commands
work in Bash and PowerShell with `python` on PATH; use `python3` instead on
systems that require that name. No packages, Java, or `PYTHONPATH` are needed
for these VM runs. The existing debugger is the command-line entry point;
`tiny_cpu_vm.py` itself is a library.

<!-- example: countdown exit: 0 -->

```bash
python src/tiny_cpu_debugger.py hardware/logisim/ap5_countdown.tcpu
```

```text
stop=halt pc=9 steps=17
ACC=0 valid=true AR=0 valid=false ZERO=true NEGATIVE=false
errors=- output=[3, 2, 1]
memory_changes=[{'address': 100, 'value': 0, 'valid': True}, {'address': 101, 'value': -1, 'valid': True}]
```

This prints the final machine state; the program's three PRINT events appear
in `output=[3, 2, 1]`. The process exits with code **0**. The countdown source
is slightly longer than the sum example above: it stores a decrement and a
counter, then loops three times.

The six-instruction sum above is checked in as
[`examples/sum.tcpu`](examples/sum.tcpu). Run it with:

<!-- example: sum exit: 0 -->

```bash
python src/tiny_cpu_debugger.py docs/examples/sum.tcpu
```

```text
stop=halt pc=6 steps=6
ACC=5 valid=true AR=0 valid=false ZERO=false NEGATIVE=false
errors=- output=[5]
memory_changes=[{'address': 10, 'value': 3, 'valid': True}]
```

Exit code: **0**. For breakpoints, single steps, input values, and JSON state
output, see the [debugger reference](tiny_cpu_debugger.md). Each CLI invocation
starts a new run; the Python debugger API supports a continuing session.

## Watch the actual Logisim circuit

The implemented [operator panel](../hardware/logisim/TinyCPU_Operator.circ)
provides RESET, STEP, and RUN around the real CPU. Its
[description](../hardware/logisim/TinyCPU_Operator.md) and
[implementation/acceptance record](tiny_cpu_operator_panel_plan.md) explain the
clock controls. Open it with Logisim-evolution **4.1.0**, using Java 21 or
newer. For direct inspection, open
[`TinyCPU.circ`](../hardware/logisim/TinyCPU.circ) and select `TinyCPUMain`.
That sheet uses an external CLK pin; Logisim's manual tick command does not
toggle it. The [manual GUI procedure](../hardware/logisim/README.md#manueller-gui-kurztest)
explains the raw-core path. The interactive GUI acceptance remains open;
automated operator and core tests do not establish a successful manual run.

The current local electrical acceptance covers 63 baseline core fixtures,
23 dynamic INPUT cases, arithmetic boundaries, seven system cases, and the
operator. These are bounded tests rather than a proof for every possible
program. See [status and evidence](tiny_cpu_instruction_status.md).

## Where to read next

1. [`tiny_cpu.md`](tiny_cpu.md) — complete architecture, syntax, and ISA.
2. [`tiny_cpu_instruction_status.md`](tiny_cpu_instruction_status.md) — what is
   electrically verified rather than merely planned.
3. [`tiny_cpu_test_guide.md`](tiny_cpu_test_guide.md) — repeatable checks.
4. [`tiny_cpu_peripherals.md`](tiny_cpu_peripherals.md) — output port and
   interrupt behavior.
5. [`tiny_cpu_development_directions.md`](tiny_cpu_development_directions.md) —
   deliberately bounded options for further work.
