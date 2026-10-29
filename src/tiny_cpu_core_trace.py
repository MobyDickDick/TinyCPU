"""AP 22.1: strict settled pre/post-edge electrical core/VM comparison."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path

from tiny_cpu_assembler import Program
from tiny_cpu_vm import FLAGS, TinyCPU


# (width, existing labelled hierarchy). No coordinate-dependent probes.
SIGNALS = {
    "PC": (12, "FETCH_DECODE/PC_OUT"),
    "ACC": (16, "DATAPATH_INSTANCE/ACC_OUT"),
    "ACC_VALID": (1, "DATAPATH_INSTANCE/ACC_VALID_OUT"),
    "AR": (16, "ADDRESS_PATH/ADDRESS"),
    "AR_VALID": (1, "ADDRESS_PATH/ADDRESS_VALID"),
    **{f"ERROR_{flag}": (1, f"ERROR_{flag}") for flag in FLAGS},
    "HALTED": (1, "HALTED"),
    "HALTED_WITH_ERROR": (1, "HALTED_WITH_ERROR"),
    "PRINT_ENABLE": (1, "PRINT_ENABLE"),
    "PRINT_VALUE": (16, "PRINT_VALUE"),
    "PRINT_VALID": (1, "DATAPATH_INSTANCE/ACC_VALID_OUT"),
    "PRINT_ADDRESS_ENABLE": (1, "PRINT_ADDRESS_ENABLE"),
    "PRINT_ADDRESS_VALUE": (16, "PRINT_ADDRESS_VALUE"),
    "PRINT_ADDRESS_VALID": (1, "PRINT_ADDRESS_VALID"),
    "MEM_WRITE": (1, "MEMORY_INSTANCE/WRITE_ENABLE"),
    "MEM_ADDRESS": (16, "MEMORY_INSTANCE/ADDRESS"),
    "MEM_WRITE_VALUE": (16, "MEMORY_INSTANCE/DATA_IN"),
    "MEM_WRITE_VALID": (1, "MEMORY_INSTANCE/VALID_IN"),
    "MEM_READ_VALUE": (16, "MEMORY_INSTANCE/MEMORY_DATA"),
    "MEM_READ_VALID": (1, "MEMORY_INSTANCE/MEMORY_VALID"),
}


@dataclass
class CoreMismatch(ValueError):
    edge: int
    phase: str
    signal: str
    expected: object
    actual: object

    def __str__(self) -> str:
        return (f"edge {self.edge} {self.phase}, {self.signal}: "
                f"expected {self.expected}, actual {self.actual}")


def write_probes(path: Path) -> None:
    path.write_text("".join(f"{name}\t{location}\n"
                            for name, (_, location) in SIGNALS.items()), encoding="utf-8")


def _memory(cpu: TinyCPU) -> str:
    return ",".join(f"{address}:{value & cpu.profile.data_mask}:{int(valid)}"
                    for address, (value, valid) in sorted(cpu.memory.items())
                    if value or valid) or "-"


def _state(cpu: TinyCPU) -> dict[str, int | str]:
    return {
        "PC": cpu.pc & (cpu.profile.memory_size - 1),
        "ACC": cpu.accumulator & cpu.profile.data_mask,
        "ACC_VALID": int(cpu.accumulator_valid),
        "AR": cpu.address_register & cpu.profile.data_mask,
        "AR_VALID": int(cpu.address_register_valid),
        **{f"ERROR_{flag}": int(cpu.errors[flag]) for flag in FLAGS},
        "MEMORY": _memory(cpu),
    }


def expected_trace(program: Program) -> list[dict[str, object]]:
    """Terminal decodes are pre-edge events; VM step includes their flag edge.

    The current core has no public INPUT value/valid port: INPUT is explicitly
    unavailable (value 0, valid 0), matching an empty VM input queue.
    """
    cpu = TinyCPU(program, inputs=[])
    rows: list[dict[str, object]] = []
    for edge in range(1, max(64, len(program.instructions) * 8) + 2):
        if not 0 <= cpu.pc < len(program.instructions):
            raise ValueError("core fixture fetches outside its ROM program")
        instruction = program.instructions[cpu.pc]
        name = instruction.mnemonic
        pre = {"edge": edge, "phase": "pre", **_state(cpu)}
        pre.update({
            "HALTED": int(name == "HALT"),
            "HALTED_WITH_ERROR": int(name in {"HALT_ERROR", "__ILLEGAL__"}),
            "PRINT_ENABLE": int(name == "PRINT"),
            "PRINT_ADDRESS_ENABLE": int(name == "PRINT_ADDRESS"),
            "MEM_WRITE": 0,
        })
        if name == "PRINT":
            pre.update(PRINT_VALUE=cpu.accumulator & cpu.profile.data_mask,
                       PRINT_VALID=int(cpu.accumulator_valid))
        memory_operand = ("ADDRESS" in name and name not in {
            "LOAD_ADDRESS_REGISTER_CONST", "JUMP_ADDRESS"})
        if memory_operand:
            address = copy.deepcopy(cpu)._address(instruction)
            if address is not None:
                value, valid = cpu._read(address)
                pre.update(MEM_ADDRESS=address, MEM_READ_VALUE=value & cpu.profile.data_mask,
                           MEM_READ_VALID=int(valid))
                if name.startswith("STORE_"):
                    pre.update(MEM_WRITE=1,
                               MEM_WRITE_VALUE=cpu.accumulator & cpu.profile.data_mask,
                               MEM_WRITE_VALID=int(cpu.accumulator_valid))
                if name == "PRINT_ADDRESS":
                    pre.update(PRINT_ADDRESS_VALUE=value & cpu.profile.data_mask,
                               PRINT_ADDRESS_VALID=int(valid))
            elif name == "PRINT_ADDRESS":
                pre.update(PRINT_ADDRESS_VALUE=0, PRINT_ADDRESS_VALID=0)
        rows.append(pre)
        cpu.step()
        rows.append({"edge": edge, "phase": "post", **_state(cpu)})
        if cpu.halted:
            return rows
    raise ValueError("core fixture does not halt in the reference VM")


def compare_trace(text: str, expected: list[dict[str, object]]) -> None:
    """Fail closed on missing/extra samples, undefined bits and first mismatch."""
    lines = text.splitlines()
    header = ["edge", "phase", *SIGNALS, "MEMORY"]
    if not lines or lines[0].split("\t") != header:
        raise CoreMismatch(0, "schema", "columns", header, lines[0] if lines else "<missing>")
    for index, line in enumerate(lines[1:]):
        if index >= len(expected):
            raise CoreMismatch(index // 2 + 1, "pre", "sample", "<end>", line)
        wanted = expected[index]
        edge, phase = int(wanted["edge"]), str(wanted["phase"])
        cells = line.split("\t")
        if len(cells) != len(header):
            raise CoreMismatch(edge, phase, "columns", len(header), len(cells))
        actual: dict[str, object] = dict(zip(header, cells))
        for field in ("edge", "phase"):
            if actual[field] != str(wanted[field]):
                raise CoreMismatch(edge, phase, field, wanted[field], actual[field])
        for name, (width, _) in SIGNALS.items():
            raw = str(actual[name])
            if len(raw) != width or any(bit not in "01" for bit in raw):
                raise CoreMismatch(edge, phase, name, f"{width} defined bits", raw)
            actual[name] = int(raw, 2)
        # The sparse full RAM image is canonical decimal address:value:valid.
        # All entries, including unexpected writes and stale invalid data,
        # participate in the exact comparison.
        for signal, value in wanted.items():
            if signal in {"edge", "phase"}:
                continue
            if actual[signal] != value:
                raise CoreMismatch(edge, phase, signal, value, actual[signal])
    if len(lines) - 1 < len(expected):
        missing = expected[len(lines) - 1]
        raise CoreMismatch(int(missing["edge"]), str(missing["phase"]),
                           "sample", "observation", "<missing>")
