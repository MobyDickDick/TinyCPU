# TinyCPU: architecture, assembly language, and reference execution

TinyCPU is a teaching accumulator machine. The supported execution profile is
**tinycpu-16-12**: signed 16-bit data, 12-bit addresses, and 4,096 data cells.
Program ROM and data RAM are separate. The former experimental 8/8 profile is
retired; the current tools expose only 16/12. The optional peripheral system
uses that same base profile.

## Implemented tools and machine format

- [`tiny_cpu_vm.py`](../src/tiny_cpu_vm.py): reference CPU state and execution;
  a Python library without a standalone command-line runner.
- [`tiny_cpu_assembler.py`](../src/tiny_cpu_assembler.py): symbolic
  `Instruction`/`Program`, `assemble()`, `load_program()`, and `encode_program()`.
- [`tiny_cpu_debugger.py`](../src/tiny_cpu_debugger.py): the program-running CLI,
  breakpoints, steps, and text/JSON state output. See its
  [options and exit codes](tiny_cpu_debugger.md).
- [`tiny_cpu_profiles.py`](../src/tiny_cpu_profiles.py): the supported profile.
- [`tiny_cpu_verify.py`](../src/tiny_cpu_verify.py): offline contract checks.

The versioned [opcode table](../hardware/logisim/tinycpu-machine-v1.json)
defines a 22-bit word: six opcode bits plus a 16-bit operand. The assembler
encodes a `Program` into machine words; `load_program()` reads `.tcpu` sources
or Logisim `.rom` files. The checked-in [countdown source](../hardware/logisim/ap5_countdown.tcpu)
and [ROM](../hardware/logisim/ap5_countdown.rom) are reproducible fixtures.
There is no separate ISA, machine-encoder, or general-purpose CLI module.

## Hardware and clock contract

[`TinyCPU.circ`](../hardware/logisim/TinyCPU.circ) runs in Logisim-evolution
**4.1.0** with Java 21 or newer. `TinyCPUMain` is an overview of eight functional
boxes. Details belong inside those boxes; the hand-drawn decoder remains
protected by [the Logisim rules](../hardware/logisim/AGENTS.md).

| State | Contract |
|---|---|
| PC | 12-bit instruction index into program ROM |
| Accumulator | 16-bit signed value plus validity; valid zero/negative status |
| Address register | 12-bit address plus validity; invalid indirect accesses are rejected |
| Data RAM | 16-bit value and validity per cell |
| Errors | Sticky OVF, DIV0, ADDR, INV, ILL, INPUT; ERR is their OR |
| I/O | INPUT loads the accumulator; PRINT emits valid values |
| Halt | Separate normal and error halt states |

Before each rising edge, fetch/decode selects the instruction, sources, write
requests, and next PC. The edge commits register, RAM, flag, and PC changes.
Taken jumps use instruction indices and validate their targets; an untaken
jump does not validate its target. `CLEAR_ERROR()` clears flags without
repairing invalid data. The [core trace contract](tiny_cpu_core_trace.md)
defines the exact pre/post observations and memory comparison.

The [test guide](tiny_cpu_test_guide.md) gives the current required commands.
The electrical gate includes complete observed-state comparisons against the
VM for its fixtures, dynamic INPUT, system, arithmetic, and operator checks.
A successful load, structural check, or normal halt alone is insufficient.
[Current evidence and remaining limits](tiny_cpu_instruction_status.md) distinguish
local acceptance from the pending fresh-checkout release and manual GUI tests.

## Guiding principle: errors are not modular arithmetic

Every register and memory cell logically consists of `(value, valid)`. An
operation produces a valid value only if all inputs are valid, the operation is
permitted, and the result is within the signed range of the configured data bus
(for 16 bits: -32768 to 32767). Otherwise, the destination becomes `0 INVALID`
and a specific error flag is set. Invalidity propagates when the value is used
again.

Version 1 deliberately preserves one DIV exception: `−32768 / −1` yields
`−32768 VALID` without OVF. Signed division truncates toward zero and retains
the low data-width bits; division by zero and invalid operands still fail.
ADD, SUB and MUL outside the signed range produce `0 INVALID` and OVF.
See the [6 November arithmetic acceptance](tiny_cpu_circuit_repair_20261106.md).

## Width-independent design requirement

The long-term architecture requirement is **width-independent, not limited to
a list of preferred sizes**.  There are two independent parameters:

* `DATA_WIDTH` is at least 16 bits and covers the accumulator, ALU, data RAM,
  input/output and the operand field;
* `PC_WIDTH` is at least 12 bits and covers the program counter, jump targets,
  address register, effective-address arithmetic and the address inputs of ROM
  and RAM.  A 12-bit PC addresses 4,096 instruction locations; it is an
  address bus, not a reduction of the CPU's data bus.

Every positive integral width at or above these minima is a design
target, not an implemented execution profile. In particular, no special case
may be required for 12, 16, 24, 32, 36, 48 or 64 bits.  Register widths, constants, splitters, sign extension,
overflow/range checks, masks and memory-address ports must all be derived from
`DATA_WIDTH` or `PC_WIDTH`; truncation between the two domains must be explicit
and range-checked.  The program counter wraps or reports an address error
according to the architectural address rules, never according to a hidden
16-bit intermediate.

The ISA and assembly language represent numbers, addresses, offsets, and jump
targets symbolically as integers.  A width-independent machine format retains
the six-bit opcode and derives its operand field and complete instruction width
from the selected profile.  An assembled program is portable when all of its
values and addresses fit the destination profile.

The data bus uses two’s complement and determines the accumulator, memory
cells, input/output values, and arithmetic overflow. The address bus is
unsigned and independently determines the address register, effective
addresses, program counter, and maximum addressable memory size. `memory_size`
may be smaller than the address space (partially populated memory), but never
larger.

The checked-in `TinyCPU.circ` and `tinycpu-machine-v1` remain the concrete,
accepted 16-data/12-PC profile.  Logisim-evolution does not parameterize a
subcircuit automatically, so a wider physical realization must consistently
apply the two parameters to every affected component and must pass the same
structural and electrical matrices.  This distinction prevents the current
fixed artifact from being mistaken for proof that arbitrary widths have
already been electrically accepted.

Error flags are **sticky**. `CLEAR_ERROR()` clears them but does not repair
invalid values. For example, only `LOAD_CONST(5)` makes the accumulator valid
again. Supported flags are `OVF`, `DIV0`, `ADDR`, `INV`, `ILL`, and `INPUT`;
`ERR` means “at least one error flag is set.”

## Syntax

Every instruction uses function-call syntax. Comments begin with `;` or `//`.
Direct operands are mandatory; consequently, `ADD_ADDRESS()` is an assembler
error, while `ADD_ADDRESS_REGISTER()` is correct.

```text
sum := 100
ADC := ADD_CONST

LOAD_CONST(7)
STORE_ADDRESS(sum)
LOAD_CONST(5)
ADC(3)
ADD_ADDRESS(sum)
PRINT()
HALT()
```

`name := 100` defines a value alias, and `ADC := ADD_CONST` defines an
instruction alias. Jump targets are defined with `name:`. Common abbreviations
(`LDC`, `LDA`, `STA`, `ADC`, `ADA`, `JMP`, `JZ`, `JNZ`, `JNEG`, `JER`, `CER`,
`HLT`) are built in; canonical names remain the documented interface.

## Instruction set

The `LOAD`, `ADD`, `SUB`, `MUL`, `DIV`, `AND`, `OR`, and `XOR` operations each
have four explicit sources:

```text
OP_CONST(value)
OP_ADDRESS(address)
OP_ADDRESS_REGISTER()
OP_ADDRESS_REGISTER_PLUS_OFFSET(offset)
```

`STORE` has the three writable destination variants (there is no
`STORE_CONST`). The address register is loaded by
`LOAD_ADDRESS_REGISTER_CONST(value)` or
`LOAD_ADDRESS_REGISTER_ADDRESS(address)`. In addition, there are:

| Group | Instructions |
|---|---|
| Logic | `NOT()` |
| Jumps | `JUMP_ADDRESS`, `JUMP_ZERO`, `JUMP_NOT_ZERO`, `JUMP_NEGATIVE`, `JUMP_ERROR`, `JUMP_NOT_ERROR` |
| Errors | `CLEAR_ERROR()`, `HALT_ERROR()` |
| I/O | `INPUT()`, `PRINT()`, `PRINT_ADDRESS(address)` |
| Control flow | `HALT()` |

Jump instructions expect a label or a numeric instruction address. `INPUT()`
reads the next number queued with the debugger option `--input`. Missing or
out-of-range input sets `INPUT` and invalidates the accumulator. Invalid
PRINT operands set `INV` and emit no output.

## Run the reference model

Use Python 3.12 or newer from the repository root, without installing packages
or setting `PYTHONPATH`. The [quickstart](tiny_cpu_quickstart.md) gives the
countdown and sum commands with their complete output. More examples follow.

[`examples/input.tcpu`](examples/input.tcpu) contains INPUT, PRINT, and HALT.
With a supplied value, the process exits **0**:

<!-- example: input exit: 0 -->

```bash
python src/tiny_cpu_debugger.py docs/examples/input.tcpu --input 41
```

```text
stop=halt pc=3 steps=3
ACC=41 valid=true AR=0 valid=false ZERO=false NEGATIVE=false
errors=- output=[41]
memory_changes=[]
```

Without input, INPUT invalidates the accumulator and sets INPUT. PRINT then
sets INV and emits nothing. HALT still stops normally and exits **0**; sticky
flags alone do not change the debugger exit code:

<!-- example: missing-input exit: 0 -->

```bash
python src/tiny_cpu_debugger.py docs/examples/input.tcpu
```

```text
stop=halt pc=3 steps=3
ACC=0 valid=false AR=0 valid=false ZERO=false NEGATIVE=false
errors=INV,INPUT output=[]
memory_changes=[]
```

An explicit HALT_ERROR stops with exit code **1**:

<!-- example: error-halt exit: 1 -->

```bash
python src/tiny_cpu_debugger.py docs/examples/halt-error.tcpu
```

```text
stop=halt_error pc=1 steps=1
ACC=0 valid=false AR=0 valid=false ZERO=false NEGATIVE=false
errors=- output=[]
memory_changes=[]
```

A breakpoint stops before the labelled instruction, with exit code **0**:

<!-- example: breakpoint exit: 0 -->

```bash
python src/tiny_cpu_debugger.py hardware/logisim/ap5_countdown.tcpu --breakpoint loop
```

```text
stop=breakpoint pc=4 steps=4
ACC=3 valid=true AR=0 valid=false ZERO=false NEGATIVE=false
errors=- output=[]
memory_changes=[{'address': 100, 'value': 3, 'valid': True}, {'address': 101, 'value': -1, 'valid': True}]
```

Use `--json` for the [debug JSON contract](tiny_cpu_debugger.md#json-vertrag).
`--step-limit N` bounds execution; reaching the limit exits 1. Invalid
arguments or unassemblable sources exit 2. These examples and the quickstart
commands are executed directly from the documentation by
[`test_tiny_cpu_documentation.py`](../tests/test_tiny_cpu_documentation.py).
The current runner does not offer disassembly or width-selection flags.

## Future compiler direction

A possible TinyLanguage backend could target the assembler's canonical
`Instruction`/`Program` model. A reverse compiler would need a bounded canonical
subset because original names and control structures cannot generally be
reconstructed. Neither compiler is implemented in this repository.
