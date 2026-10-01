# Possible development directions

TinyCPU has reached a useful stopping point: its current 16/12 profile, ISA,
reference VM, and electrical regression suite form a coherent result. Further
ideas are valuable, but combining them in one circuit would cross the point
where educational value is lost to integration complexity. This document
therefore treats each direction as a separate experiment and recommends a
break before changing the accepted machine.

## Recommendation

First complete only the deferred manual GUI smoke test and preserve the current
release as a baseline. If work resumes, implement an **operator/trace panel** as
the next small project. It directly answers the need to watch TinyCPU work,
changes no ISA semantics, and has a clear definition of done: load the supplied
countdown program, reset it, single-step it, run/pause it, and visibly show PC,
instruction, accumulator plus validity, output, halt state, and error flags.

After that, choose **one** research branch in a copy or feature branch. Do not
redraw the CPU, unify memory, add multithreading, and make it asynchronous in a
single evolution step.

## Evaluation of the proposed directions

| Direction | Value | Cost/risk | Suggested scope |
|---|---|---|---|
| Beginner documentation | Very high | Low | Keep the ten-minute guide executable and add one annotated trace. |
| English documentation | High | Medium | Use English for new canonical pages; translate one topic at a time without mixing language inside a page. |
| Watch execution | Very high | Low–medium | Build the operator/trace panel first; retain the existing debugger as the non-GUI reference. |
| Redraw `TinyCPUMain` using only functional blocks | High for readability | Medium–high; easy to break accepted wiring | Create a new presentation top level that instantiates tested blocks. Keep the accepted top level unchanged until equivalence tests pass. |
| Unified program/data memory | High as an architecture experiment | High; changes machine format, loader, write protection, and tests | Define a separate von Neumann profile, boot protocol, address map, and protected/code-writable policy. Do not silently change the 16/12 profile. |
| Concurrent programs | Interesting, but not small | Very high; scheduling, memory isolation, I/O ownership, interrupt and error semantics | Prototype banked PC/ACC/flags in the VM first. Specify context switching and shared memory before drawing hardware. |
| Live input/output | High and demonstrable | Medium | Start with one input register/queue and one output display; specify handshake, validity, and behavior when no input is available. |
| More types/functions | Depends on teaching goal | Medium–very high | Prefer library routines first. Add an ISA type only after defining representation, overflow, validity, encoding, and tests. |
| Transistor-level visualization | High educational value | Extreme at whole-CPU scale | Demonstrate a latch, full adder, or tiny ALU slice as a separate model; do not expand the full CPU immediately. |
| Clockless/asynchronous CPU | High research value | Extreme; hazards and completion detection replace the clock | Prototype a dual-rail or bundled-data handshake for one ALU operation and verify delay assumptions before considering a CPU. |
| Publish for Logisim users | High, low technical risk | Low | Tag a stable release with the `.circ`, sample program, screenshots, license, supported Logisim version, and reproducible test commands. |

## Important architectural notes

### Functional-block redraw

A presentation-oriented `TinyCPUMainBlocks` is safer than editing the verified
`TinyCPUMain` in place. Its public pins should match the existing top level,
and an automated trace comparison should prove the same behavior. Hierarchy
can hide detail without deleting it: users can descend from CPU to datapath,
ALU, adder, and eventually gate-level demonstrations.

### Unified memory and booting

Program overwrite is not inherently an error in a von Neumann machine;
self-modifying code may even be intentional. The design must choose and state a
policy. A minimal safe experiment needs:

* one address space and an explicit code/data memory map;
* an external loader that holds the CPU in reset while loading;
* a reset vector and defined initial PC;
* either write-protected code, a privileged unlock mechanism, or deliberately
  writable code;
* rules for instruction/data width and alignment;
* tests for loading, executing, rejected writes, and malformed images.

This is a new profile, not a backward-compatible wiring improvement.

### Concurrency

Register banks indexed by a thread ID are only the storage part of
multithreading. A usable design also needs a scheduler, an atomic definition of
instruction boundaries, per-thread halt/error state, interrupt ownership,
input/output arbitration, and a policy for shared memory. A two-thread,
round-robin VM prototype with banked `PC`, accumulator, address register,
validity, and flags is the smallest credible experiment.

### Live I/O

The existing input and output semantics are a natural seam for a calculator.
Keep the CPU independent of a particular keyboard or display by defining a
small handshake at the boundary: `input_available`, `input_value`,
`input_consume`, and `output_enable/value/valid`. A calculator front end can
then be replaced without changing the processor.

### Clockless operation

Computing twice and comparing results detects some faults, but it does not by
itself establish that combinational signals have settled, nor does it make an
asynchronous circuit hazard-free. Identical transient results can occur before
the final result, and duplicated logic can share the same systematic error. A
clockless design needs an explicit completion protocol, request/acknowledge
handshakes, delay or indication assumptions, and analysis of hazards,
metastability, reset, and forks. Treat this as a separate asynchronous-logic
research project, beginning with one block.

## A complexity budget for every experiment

Before implementation, require a one-page proposal containing:

1. the learning question;
2. what remains unchanged;
3. the new public interface and state;
4. compatibility consequences;
5. one minimal demonstration;
6. automated acceptance criteria;
7. a stop rule and an archive/revert plan.

A useful default limit is one new architectural concept, one demonstrator, and
one acceptance trace per experiment. If the idea cannot fit that boundary,
split it before touching the circuit.

## Additional small ideas

These options provide educational value without redesigning the processor:

* generate a cycle-by-cycle HTML or terminal trace from the existing debugger;
* add an annotated “tour” program that exercises arithmetic, memory, a branch,
  error recovery, input, and output;
* add waveform export for PC, opcode, accumulator, validity, memory write, and
  output signals;
* create fault-injection exercises by disconnecting one copied diagnostic
  circuit and asking the learner to identify the failing invariant;
* publish a gallery of tiny programs (counter, sum, Euclidean GCD, calculator
  core) with expected traces;
* create a gate-level full-adder and register lesson linked to, but not
  instantiated thousands of times inside, the production CPU.

A break is therefore not abandonment. Freezing a tested release, recording the
ideas, and returning only when one experiment has a clear question is the most
likely way to keep TinyCPU understandable.
