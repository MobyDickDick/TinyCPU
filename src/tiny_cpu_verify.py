#!/usr/bin/env python3
"""Offline consistency checks for the checked-in TinyCPU artifacts.

This intentionally does not claim to replace electrical simulation.  It catches
broken JSON contracts and structural Logisim errors before the considerably more
expensive simulator acceptance run is started.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOGISIM = ROOT / "hardware" / "logisim"
LOCATION = re.compile(r"^\((-?\d+),(-?\d+)\)$")


class VerificationError(ValueError):
    """A controlled error in a checked-in artifact."""


def display_path(path: Path) -> Path:
    """Return a stable repository-relative name, while supporting test fixtures."""
    try:
        return path.relative_to(ROOT)
    except ValueError:
        return path


def load_json(path: Path) -> object:
    try:
        with path.open(encoding="utf-8") as source:
            return json.load(source)
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"{display_path(path)}: invalid JSON: {exc}") from exc


def point(value: str, *, source: Path) -> tuple[int, int]:
    match = LOCATION.fullmatch(value)
    if not match:
        raise VerificationError(f"{display_path(source)}: invalid location {value!r}")
    return int(match.group(1)), int(match.group(2))


def verify_circuit(path: Path) -> tuple[int, int]:
    try:
        project = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        raise VerificationError(f"{display_path(path)}: invalid Logisim XML: {exc}") from exc

    circuits = project.findall("circuit")
    names = [circuit.get("name", "") for circuit in circuits]
    duplicates = sorted(name for name, count in Counter(names).items() if count > 1)
    if not names or any(not name for name in names) or duplicates:
        raise VerificationError(
            f"{display_path(path)}: circuit names must be present and unique"
            + (f" (duplicates: {', '.join(duplicates)})" if duplicates else "")
        )

    main = project.find("main")
    main_name = main.get("name") if main is not None else None
    if main_name not in names:
        raise VerificationError(f"{display_path(path)}: main circuit {main_name!r} does not exist")

    references: dict[str, list[str]] = {name: [] for name in names}
    wires = 0
    for circuit in circuits:
        circuit_name = circuit.get("name", "")
        pin_labels: list[str] = []
        for component in circuit.findall("comp"):
            location = component.get("loc")
            if location is None:
                raise VerificationError(f"{display_path(path)}:{circuit_name}: component without loc")
            point(location, source=path)
            attributes = {item.get("name"): item.get("val") for item in component.findall("a")}
            if component.get("name") == "Pin":
                label = attributes.get("label", "")
                if not label:
                    raise VerificationError(f"{display_path(path)}:{circuit_name}: unlabeled Pin")
                pin_labels.append(label)
            if component.get("lib") is None:
                target = component.get("name", "")
                if target not in references:
                    raise VerificationError(
                        f"{display_path(path)}:{circuit_name}: missing subcircuit {target!r}"
                    )
                references[circuit_name].append(target)

        repeated_pins = sorted(label for label, count in Counter(pin_labels).items() if count > 1)
        if repeated_pins:
            raise VerificationError(
                f"{display_path(path)}:{circuit_name}: duplicate Pin labels: "
                + ", ".join(repeated_pins)
            )

        for wire in circuit.findall("wire"):
            start = point(wire.get("from", ""), source=path)
            end = point(wire.get("to", ""), source=path)
            if start == end:
                raise VerificationError(f"{display_path(path)}:{circuit_name}: zero-length wire {start}")
            if start[0] != end[0] and start[1] != end[1]:
                raise VerificationError(
                    f"{display_path(path)}:{circuit_name}: diagonal wire {start} -> {end}"
                )
            wires += 1

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str, stack: list[str]) -> None:
        if name in visiting:
            cycle = stack[stack.index(name) :] + [name]
            raise VerificationError(f"{display_path(path)}: recursive circuit: {' -> '.join(cycle)}")
        if name in visited:
            return
        visiting.add(name)
        for target in references[name]:
            visit(target, stack + [target])
        visiting.remove(name)
        visited.add(name)

    for name in names:
        visit(name, [name])
    return len(circuits), wires


def verify_contracts() -> tuple[int, int]:
    machine_path = LOGISIM / "tinycpu-machine-v1.json"
    matrix_path = LOGISIM / "tinycpu-electrical-matrix-v1.json"
    profile_path = LOGISIM / "tinycpu-16-12.json"
    machine = load_json(machine_path)
    matrix = load_json(matrix_path)
    profile = load_json(profile_path)
    if not isinstance(machine, dict) or not isinstance(matrix, dict) or not isinstance(profile, dict):
        raise VerificationError("machine, matrix, and profile roots must be JSON objects")
    small_machine_path = LOGISIM / "tinycpu-machine-8-v1.json"
    small_profile_path = LOGISIM / "tinycpu-8-8.json"
    small_machine, small_profile = load_json(small_machine_path), load_json(small_profile_path)
    if not isinstance(small_machine, dict) or not isinstance(small_profile, dict):
        raise VerificationError("8/8 machine and profile roots must be JSON objects")
    expected_profiles = ((profile, machine, 16, 4096, 22),
                         (small_profile, small_machine, 8, 256, 14))
    for current_profile, current_machine, bits, size, word_bits in expected_profiles:
        if (current_profile.get("data_bits"), current_profile.get("memory_size"),
                current_profile.get("machine_format_id"), current_machine.get("word_bits")) != (
                    bits, size, current_machine.get("format"), word_bits):
            raise VerificationError(f"profile {current_profile.get('name')!r} is inconsistent")
        if current_profile.get("machine_format") != current_machine_path_name(current_machine):
            raise VerificationError(f"profile {current_profile.get('name')!r} selects the wrong format file")

    opcodes = machine.get("opcodes")
    if not isinstance(opcodes, list) or not opcodes:
        raise VerificationError(f"{machine_path.relative_to(ROOT)}: opcodes must be a non-empty list")
    codes: list[int] = []
    mnemonics: list[str] = []
    for index, opcode in enumerate(opcodes):
        if not isinstance(opcode, dict):
            raise VerificationError(f"{machine_path.relative_to(ROOT)}: opcode {index} is not an object")
        code, hexadecimal, mnemonic = opcode.get("code"), opcode.get("hex"), opcode.get("mnemonic")
        if code != index or hexadecimal != f"0x{index:02x}" or not isinstance(mnemonic, str):
            raise VerificationError(
                f"{machine_path.relative_to(ROOT)}: inconsistent opcode entry at index {index}"
            )
        codes.append(code)
        mnemonics.append(mnemonic)
    if len(set(codes)) != len(codes) or len(set(mnemonics)) != len(mnemonics):
        raise VerificationError(f"{machine_path.relative_to(ROOT)}: duplicate opcode code or mnemonic")
    small_opcodes = small_machine.get("opcodes")
    if small_opcodes != opcodes:
        raise VerificationError(f"{small_machine_path.relative_to(ROOT)}: opcode table differs from v1")

    isa_controls = profile.get("isa_controls", {})
    signals = isa_controls.get("instruction_signals") if isinstance(isa_controls, dict) else None
    # The four XOR controls were added compatibly as named entries instead of
    # reordering the frozen instruction_signals array.
    extended_signals = list(signals) if isinstance(signals, list) else []
    if isinstance(isa_controls, dict):
        xor_control_names = {
            "XOR_CONST": "XOR_CONST",
            "XOR_ADR": "XOR_ADDRESS",
            "XOR_ADR_REG": "XOR_ADDRESS_REGISTER",
            "XOR_REG_OFF": "XOR_ADDRESS_REGISTER_PLUS_OFFSET",
        }
        extended_signals.extend(
            mnemonic for control, mnemonic in xor_control_names.items() if control in isa_controls
        )
    # Pin order is a drawing detail (JUMP_NOT_ZERO deliberately occupies the
    # final free symbol position), so the contract compares the inventories.
    if not isinstance(signals, list) or Counter(extended_signals) != Counter(mnemonics):
        raise VerificationError(
            f"{profile_path.relative_to(ROOT)}: instruction_signals do not match the machine opcode table"
        )
    cases = matrix.get("opcode_cases")
    case_opcodes = [case.get("opcode") for case in cases] if isinstance(cases, list) else []
    if set(case_opcodes) != set(mnemonics):
        missing = sorted(set(mnemonics) - set(case_opcodes))
        extra = sorted(set(case_opcodes) - set(mnemonics))
        raise VerificationError(
            f"{matrix_path.relative_to(ROOT)}: opcode matrix mismatch; missing={missing}, extra={extra}"
        )
    fixture_ids = {fixture.get("id") for fixture in matrix.get("fixtures", []) if isinstance(fixture, dict)}
    sticky_ids = {item.get("fixture") for item in matrix.get("sticky_errors", []) if isinstance(item, dict)}
    if sticky_ids != fixture_ids:
        raise VerificationError(f"{matrix_path.relative_to(ROOT)}: sticky-error fixtures do not match fixtures")
    debug_path = LOGISIM / "tinycpu-debug-v1.json"
    debug = load_json(debug_path)
    if not isinstance(debug, dict) or debug.get("schema_version") != 1:
        raise VerificationError(f"{debug_path.relative_to(ROOT)}: unsupported debug schema")
    expected_reasons = {"breakpoint", "step", "halt", "halt_error", "step_limit"}
    if set(debug.get("stop_reasons", [])) != expected_reasons:
        raise VerificationError(f"{debug_path.relative_to(ROOT)}: incomplete stop reasons")
    if debug.get("breakpoint_timing") != "before_instruction":
        raise VerificationError(f"{debug_path.relative_to(ROOT)}: invalid breakpoint timing")
    return len(opcodes), len(fixture_ids)


def current_machine_path_name(machine: dict[str, object]) -> str:
    return "tinycpu-machine-8-v1.json" if machine.get("format") == "tinycpu-machine-8-v1" else "tinycpu-machine-v1.json"


def verify(root: Path = ROOT) -> list[str]:
    global ROOT, LOGISIM
    original_root, original_logisim = ROOT, LOGISIM
    ROOT, LOGISIM = root.resolve(), root.resolve() / "hardware" / "logisim"
    try:
        json_files = sorted(LOGISIM.glob("*.json"))
        for path in json_files:
            load_json(path)
        circuit_files = sorted(LOGISIM.rglob("*.circ"))
        circuit_count = wire_count = 0
        for path in circuit_files:
            circuits, wires = verify_circuit(path)
            circuit_count += circuits
            wire_count += wires
        opcode_count, fixture_count = verify_contracts()
        return [
            f"JSON: {len(json_files)} files valid",
            f"Logisim: {len(circuit_files)} files, {circuit_count} circuits, {wire_count} orthogonal wires valid",
            f"Contracts: {opcode_count} opcodes and {fixture_count} sticky-error fixtures consistent",
        ]
    finally:
        ROOT, LOGISIM = original_root, original_logisim


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify TinyCPU checkout artifacts offline")
    parser.add_argument("--root", type=Path, default=ROOT, help="checkout root (defaults to this source tree)")
    args = parser.parse_args(argv)
    try:
        messages = verify(args.root)
    except VerificationError as exc:
        print(f"TinyCPU verification failed: {exc}", file=sys.stderr)
        return 1
    for message in messages:
        print(message)
    print("TinyCPU offline verification passed (electrical simulation not included).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
