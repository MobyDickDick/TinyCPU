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

The Python VM is the executable reference model and is the quickest way to
learn the instruction set:

```bash
PYTHONPATH=src python src/tiny_cpu_vm.py hardware/logisim/ap5_countdown.tcpu
```

To inspect a program instruction by instruction, use the symbolic debugger:

```bash
PYTHONPATH=src python src/tiny_cpu_debugger.py \
  hardware/logisim/ap5_countdown.tcpu
```

The debugger supports stepping, continuing, breakpoints, memory inspection,
input injection, and JSON traces; its command reference is in
[`tiny_cpu_debugger.md`](tiny_cpu_debugger.md).

## Watch the actual Logisim circuit

On a desktop, open `hardware/logisim/TinyCPU.circ` with Logisim-evolution
4.1.0, select `TinyCPUMain`, reset the simulation, and toggle the external
`CLK` pin from 0 to 1 and back to 0 for each step. Do not use Logisim’s manual
tick command: this circuit intentionally uses an external clock pin.

The exact Linux, Windows, and container/VNC instructions and the expected
countdown trace are in the [manual GUI test](../hardware/logisim/README.md#manueller-gui-kurztest).
If the interface is too low-level, the proposed operator panel explains a
safer future UI with reset, single-step, run, and readable state displays; see
[`tiny_cpu_operator_panel_plan.md`](tiny_cpu_operator_panel_plan.md).

## Where to read next

1. [`tiny_cpu.md`](tiny_cpu.md) — complete architecture, syntax, and ISA.
2. [`tiny_cpu_instruction_status.md`](tiny_cpu_instruction_status.md) — what is
   electrically verified rather than merely planned.
3. [`tiny_cpu_test_guide.md`](tiny_cpu_test_guide.md) — repeatable checks.
4. [`tiny_cpu_peripherals.md`](tiny_cpu_peripherals.md) — output port and
   interrupt behavior.
5. [`tiny_cpu_development_directions.md`](tiny_cpu_development_directions.md) —
   deliberately bounded options for further work.
