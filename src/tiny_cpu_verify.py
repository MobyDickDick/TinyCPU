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

from tiny_cpu_assembler import AssemblyError, assemble, opcode_table
from tiny_cpu_profiles import load_profile
from tiny_cpu_systems import load_system_profile


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


def _rom_words(text: str, *, source: Path, address_bits: int, word_bits: int) -> list[int]:
    """Parse the uncompressed Logisim raw format used by the AP-17 fixture."""
    tokens = text.split()
    expected_header = ["addr/data:", str(address_bits), str(word_bits)]
    if tokens[:3] != expected_header:
        raise VerificationError(
            f"{display_path(source)}: expected ROM header {' '.join(expected_header)!r}"
        )
    try:
        words = [int(token, 16) for token in tokens[3:]]
    except ValueError as exc:
        raise VerificationError(f"{display_path(source)}: invalid ROM word") from exc
    if not words or any(word >= 1 << word_bits for word in words):
        raise VerificationError(f"{display_path(source)}: empty or out-of-range ROM payload")
    return words


def verify_small_profile_circuit(profile: dict[str, object], machine: dict[str, object]) -> None:
    """Check that the checked-in 8/8 circuit really is width-specialized.

    This remains a structural gate, not a substitute for the electrical AP-17
    trace.  It nevertheless prevents the new profile from silently pointing at
    a renamed 16/12 circuit or embedding a ROM for the wrong machine format.
    """
    path = LOGISIM / str(profile.get("circuit", ""))
    if not path.is_file():
        raise VerificationError(f"{display_path(path)}: profile circuit is missing")
    project = ET.parse(path).getroot()
    if project.find("main") is None or project.find("main").get("name") != profile.get("top_circuit"):
        raise VerificationError(f"{display_path(path)}: top circuit differs from profile")

    width_attributes = {"width", "incoming", "dataWidth", "addrWidth"}
    forbidden = {"16", "12", "22"}
    for attribute in project.findall(".//a"):
        if attribute.get("name") in width_attributes and attribute.get("val") in forbidden:
            raise VerificationError(
                f"{display_path(path)}: legacy 16/12 width remains in {attribute.get('name')}"
            )

    rom = next((component for component in project.findall(".//comp")
                if component.get("name") == "ROM" and any(
                    item.get("name") == "label" and item.get("val") == "INSTRUCTION_ROM"
                    for item in component.findall("a"))), None)
    if rom is None:
        raise VerificationError(f"{display_path(path)}: INSTRUCTION_ROM is missing")
    attributes = {item.get("name"): item for item in rom.findall("a")}
    address_bits = int(profile["address_bits"])
    word_bits = int(machine["word_bits"])
    if (attributes.get("addrWidth") is None or attributes["addrWidth"].get("val") != str(address_bits)
            or attributes.get("dataWidth") is None or attributes["dataWidth"].get("val") != str(word_bits)
            or attributes.get("contents") is None):
        raise VerificationError(f"{display_path(path)}: ROM widths differ from profile")
    embedded = _rom_words(attributes["contents"].text or "", source=path,
                          address_bits=address_bits, word_bits=word_bits)
    fixture_path = LOGISIM / "ap17_countdown_8_8.rom"
    fixture_tokens = fixture_path.read_text(encoding="utf-8").split()
    if fixture_tokens[:2] != ["v2.0", "raw"]:
        raise VerificationError(f"{display_path(fixture_path)}: invalid raw ROM header")
    try:
        fixture = [int(token, 16) for token in fixture_tokens[2:]]
    except ValueError as exc:
        raise VerificationError(f"{display_path(fixture_path)}: invalid ROM word") from exc
    if embedded != fixture:
        raise VerificationError(f"{display_path(path)}: embedded ROM differs from AP-17 fixture")


def verify_system_circuit() -> None:
    """Match the AP-18 system's public electrical boundary to its contract."""
    system = load_system_profile("tinycpu-peripherals-16-12-v1")
    project = ET.parse(system.circuit_path).getroot()
    main = project.find("main")
    if main is None or main.get("name") != system.top_circuit:
        raise VerificationError(f"{display_path(system.circuit_path)}: top circuit differs from system profile")
    circuit = project.find(f"circuit[@name='{system.top_circuit}']")
    if circuit is None:
        raise VerificationError(f"{display_path(system.circuit_path)}: system top circuit is missing")
    actual: dict[str, dict[str, object]] = {}
    for component in circuit.findall("comp[@name='Pin']"):
        attributes = {item.get("name"): item.get("val") for item in component.findall("a")}
        actual[attributes.get("label", "")] = {
            "direction": attributes.get("type", "input"),
            "bits": int(attributes.get("width", "1")),
        }
    if actual != system.public_pins:
        raise VerificationError(f"{display_path(system.circuit_path)}: public pins differ from system profile")
    if system.circuit_path.name == system.base_profile.circuit:
        raise VerificationError("AP-18 must use an independent circuit")

    contract = load_json(LOGISIM / "tinycpu-peripherals-16-12-v1.json")
    component_contract = contract.get("components", {}).get("output_port", {})
    output_name = component_contract.get("circuit")
    output = project.find(f"circuit[@name='{output_name}']")
    if output is None:
        raise VerificationError(
            f"{display_path(system.circuit_path)}: OutputPort circuit is missing"
        )
    pins = {}
    for component in output.findall("comp[@name='Pin']"):
        attributes = {item.get("name"): item.get("val") for item in component.findall("a")}
        pins[attributes.get("label", "")] = {
            "direction": attributes.get("type", "input"),
            "bits": int(attributes.get("width", "1")),
        }
    expected_pins = {
        "WRITE_VALUE": {"direction": "input", "bits": 16},
        "WRITE_VALID": {"direction": "input", "bits": 1},
        "WRITE_ENABLE": {"direction": "input", "bits": 1},
        "CLK": {"direction": "input", "bits": 1},
        "RESET": {"direction": "input", "bits": 1},
        "VALUE": {"direction": "output", "bits": 16},
        "VALID": {"direction": "output", "bits": 1},
    }
    if pins != expected_pins:
        raise VerificationError(
            f"{display_path(system.circuit_path)}: OutputPort pins differ from contract"
        )
    registers = {}
    for component in output.findall("comp[@name='Register']"):
        attributes = {item.get("name"): item.get("val") for item in component.findall("a")}
        registers[attributes.get("label", "")] = int(attributes.get("width", "1"))
    expected_registers = {
        "OUTPUT_VALUE": component_contract.get("registers", {}).get("value"),
        "OUTPUT_VALID": component_contract.get("registers", {}).get("valid"),
    }
    if registers != expected_registers:
        raise VerificationError(
            f"{display_path(system.circuit_path)}: OutputPort registers differ from contract"
        )
    output_wires = {
        (wire.get("from"), wire.get("to")) for wire in output.findall("wire")
    }
    # Check the actual Logisim register ports, not merely the presence of
    # suitably named components. Removing either half of a shared control net
    # must fail offline before an electrical run is attempted.
    expected_output_wires = {
        ("(180,140)", "(430,140)"),
        ("(180,200)", "(300,200)"),
        ("(300,200)", "(300,240)"),
        ("(300,240)", "(430,240)"),
        ("(180,260)", "(330,260)"),
        ("(330,160)", "(330,260)"),
        ("(330,160)", "(430,160)"),
        ("(330,260)", "(430,260)"),
        ("(180,320)", "(350,320)"),
        ("(350,180)", "(350,320)"),
        ("(350,180)", "(430,180)"),
        ("(350,280)", "(350,320)"),
        ("(350,280)", "(430,280)"),
        ("(180,380)", "(460,380)"),
        ("(460,200)", "(460,380)"),
        ("(460,200)", "(460,210)"),
        ("(460,300)", "(460,380)"),
        ("(460,300)", "(460,310)"),
        ("(490,140)", "(600,140)"),
        ("(490,240)", "(600,240)"),
    }
    expected_paths = {
        "write_value_to_value_register", "write_valid_to_valid_register",
        "shared_write_enable", "shared_clock", "shared_reset",
        "value_register_to_output", "valid_register_to_output",
    }
    if (output_wires != expected_output_wires
            or set(component_contract.get("verified_paths", [])) != expected_paths):
        raise VerificationError(
            f"{display_path(system.circuit_path)}: OutputPort wiring differs from contract"
        )

    path_contract = contract.get("components", {}).get("output_memory_path", {})
    path_name = path_contract.get("circuit")
    memory_path = project.find(f"circuit[@name='{path_name}']")
    if memory_path is None:
        raise VerificationError(
            f"{display_path(system.circuit_path)}: OutputMemoryPath circuit is missing"
        )
    path_pins = {}
    for component in memory_path.findall("comp[@name='Pin']"):
        attributes = {item.get("name"): item.get("val") for item in component.findall("a")}
        path_pins[attributes.get("label", "")] = {
            "direction": attributes.get("type", "input"),
            "bits": int(attributes.get("width", "1")),
        }
    expected_path_pins = {
        "ADDRESS": {"direction": "input", "bits": path_contract.get("address_bits")},
        "WRITE_VALUE": {"direction": "input", "bits": path_contract.get("data_bits")},
        "WRITE_VALID": {"direction": "input", "bits": 1},
        "WRITE_ENABLE": {"direction": "input", "bits": 1},
        "RAM_READ_VALUE": {"direction": "input", "bits": path_contract.get("data_bits")},
        "RAM_READ_VALID": {"direction": "input", "bits": 1},
        "CLK": {"direction": "input", "bits": 1},
        "RESET": {"direction": "input", "bits": 1},
        "READ_VALUE": {"direction": "output", "bits": path_contract.get("data_bits")},
        "READ_VALID": {"direction": "output", "bits": 1},
        "RAM_WRITE_ENABLE": {"direction": "output", "bits": 1},
        "OUTPUT_PORT_VALUE": {"direction": "output", "bits": path_contract.get("data_bits")},
        "OUTPUT_PORT_VALID": {"direction": "output", "bits": 1},
    }
    if path_pins != expected_path_pins:
        raise VerificationError(
            f"{display_path(system.circuit_path)}: OutputMemoryPath pins differ from contract"
        )
    labelled = {
        item.get("val")
        for component in memory_path.findall("comp")
        for item in component.findall("a[@name='label']")
    }
    required = {"OUTPUT_ADDRESS_DECODE", "NOT_OUTPUT_ADDRESS", "RAM_WRITE_GATE",
                "OUTPUT_WRITE_GATE", "OUTPUT_READ_VALUE_SELECT",
                "OUTPUT_READ_VALID_SELECT", "OUTPUT_PORT"}
    if not required <= labelled:
        raise VerificationError(
            f"{display_path(system.circuit_path)}: OutputMemoryPath routing differs from contract"
        )
    constant = memory_path.find("comp[@name='Constant']/a[@name='value']")
    if constant is None or int(constant.get("val", "-1"), 0) != path_contract.get("output_address"):
        raise VerificationError(
            f"{display_path(system.circuit_path)}: OutputMemoryPath address differs from contract"
        )
    memory_wires = {
        (wire.get("from"), wire.get("to")) for wire in memory_path.findall("wire")
    }
    # These segments anchor every functional route at a real component port.
    # The intervening orthogonal segments remain free to be redrawn, but no
    # declared path may be replaced with labels alone.
    required_memory_wires = {
        ("(300,130)", "(310,130)"),  # address -> comparator
        ("(290,100)", "(310,100)"),  # reserved constant -> comparator
        ("(410,240)", "(440,240)"),  # match -> inverter
        ("(520,235)", "(540,235)"),  # mismatch -> RAM write gate
        ("(500,245)", "(540,245)"),  # write enable -> RAM write gate
        ("(410,280)", "(540,280)"),  # match -> output write gate
        ("(500,275)", "(540,275)"),  # write enable -> output write gate
        ("(620,130)", "(660,130)"),  # RAM value -> value mux
        ("(600,170)", "(660,170)"),  # RAM validity -> validity mux
        ("(640,150)", "(660,150)"),  # output value -> value mux
        ("(630,190)", "(660,190)"),  # output validity -> validity mux
        ("(610,170)", "(670,170)"),  # match -> value selector
        ("(610,210)", "(670,210)"),  # match -> validity selector
        ("(560,330)", "(650,330)"),  # write value -> output port
        ("(550,340)", "(650,340)"),  # write validity -> output port
        ("(590,350)", "(650,350)"),  # gated write -> output port
        ("(530,360)", "(650,360)"),  # clock -> output port
        ("(540,370)", "(650,370)"),  # reset -> output port
        ("(690,140)", "(800,140)"),  # selected value -> read output
        ("(690,180)", "(800,180)"),  # selected validity -> read output
        ("(570,240)", "(800,240)"),  # gated RAM write output
        ("(760,300)", "(800,300)"),  # output value state
        ("(780,340)", "(800,340)"),  # output validity state
    }
    expected_memory_paths = {
        "reserved_address_decode", "ram_write_on_address_mismatch",
        "output_write_on_address_match", "ram_value_read_default",
        "ram_valid_read_default", "output_value_read_on_address_match",
        "output_valid_read_on_address_match", "output_port_write_value_and_valid",
        "output_port_clock_and_reset", "read_and_state_outputs",
    }
    if (not required_memory_wires <= memory_wires
            or set(path_contract.get("verified_paths", [])) != expected_memory_paths):
        raise VerificationError(
            f"{display_path(system.circuit_path)}: OutputMemoryPath wiring differs from contract"
        )

    interrupt_contract = contract.get("components", {}).get("interrupt_controller", {})
    interrupt_name = interrupt_contract.get("circuit")
    interrupt = project.find(f"circuit[@name='{interrupt_name}']")
    if interrupt is None:
        raise VerificationError(
            f"{display_path(system.circuit_path)}: InterruptController circuit is missing"
        )
    interrupt_pins = {}
    for component in interrupt.findall("comp[@name='Pin']"):
        attributes = {item.get("name"): item.get("val") for item in component.findall("a")}
        interrupt_pins[attributes.get("label", "")] = {
            "direction": attributes.get("type", "input"),
            "bits": int(attributes.get("width", "1")),
        }
    address_bits = interrupt_contract.get("address_bits")
    expected_interrupt_pins = {
        "INTERRUPT_REQUEST": {"direction": "input", "bits": 1},
        "INSTRUCTION_BOUNDARY": {"direction": "input", "bits": 1},
        "ENABLE_REQUEST": {"direction": "input", "bits": 1},
        "DISABLE_REQUEST": {"direction": "input", "bits": 1},
        "RETURN_REQUEST": {"direction": "input", "bits": 1},
        "NEXT_PC": {"direction": "input", "bits": address_bits},
        "CLK": {"direction": "input", "bits": 1},
        "RESET": {"direction": "input", "bits": 1},
        "INTERRUPT_ACCEPT": {"direction": "output", "bits": 1},
        "TARGET_PC": {"direction": "output", "bits": address_bits},
        "INTERRUPT_ENABLED": {"direction": "output", "bits": 1},
        "INTERRUPT_PENDING": {"direction": "output", "bits": 1},
        "IN_INTERRUPT_HANDLER": {"direction": "output", "bits": 1},
        "RETURN_ADDRESS": {"direction": "output", "bits": address_bits},
        "RETURN_ADDRESS_VALID": {"direction": "output", "bits": 1},
        "ILLEGAL_RETURN": {"direction": "output", "bits": 1},
    }
    if interrupt_pins != expected_interrupt_pins:
        raise VerificationError(
            f"{display_path(system.circuit_path)}: InterruptController pins differ from contract"
        )
    register_labels = {
        "REQUEST_LEVEL": "request_level",
        "INTERRUPT_ENABLED": "enabled",
        "INTERRUPT_PENDING": "pending",
        "IN_INTERRUPT_HANDLER": "in_handler",
        "RETURN_ADDRESS": "return_address",
        "RETURN_ADDRESS_VALID": "return_address_valid",
    }
    interrupt_registers = {}
    for component in interrupt.findall("comp[@name='Register']"):
        attributes = {item.get("name"): item.get("val") for item in component.findall("a")}
        label = attributes.get("label", "")
        if label in register_labels:
            interrupt_registers[register_labels[label]] = int(attributes.get("width", "1"))
    if interrupt_registers != interrupt_contract.get("registers"):
        raise VerificationError(
            f"{display_path(system.circuit_path)}: InterruptController registers differ from contract"
        )
    interrupt_labels = {
        item.get("val")
        for component in interrupt.findall("comp")
        for item in component.findall("a[@name='label']")
    }
    required_interrupt_labels = {
        "INTERRUPT_VECTOR", "RISING_EDGE_DETECT", "INTERRUPT_ACCEPT_GATE",
        "ILLEGAL_RETURN_GATE", "INTERRUPT_TARGET_SELECT", "PREVIOUS_REQUEST_NOT",
        "REQUEST_LEVEL_WRITE_ENABLE", "PENDING_SET_OR_HOLD",
        "PENDING_WRITE_ENABLE",
    }
    if not required_interrupt_labels <= interrupt_labels:
        raise VerificationError(
            f"{display_path(system.circuit_path)}: InterruptController routing differs from contract"
        )
    vector = None
    for constant_component in interrupt.findall("comp[@name='Constant']"):
        label = constant_component.find("a[@name='label']")
        if label is not None and label.get("val") == "INTERRUPT_VECTOR":
            vector = constant_component.find("a[@name='value']")
            break
    if vector is None or int(vector.get("val", "-1"), 0) != interrupt_contract.get("vector"):
        raise VerificationError(
            f"{display_path(system.circuit_path)}: InterruptController vector differs from contract"
        )
    if (interrupt_contract.get("vector") != system.interrupt_vector
            or interrupt_contract.get("priority") != contract.get("priority")
            or interrupt_contract.get("request_edge") != contract["interrupt"]["request"]):
        raise VerificationError(
            f"{display_path(system.circuit_path)}: InterruptController contract differs from system profile"
        )
    interrupt_wires = {
        (wire.get("from"), wire.get("to")) for wire in interrupt.findall("wire")
    }
    required_interrupt_wires = {
        ("(160,120)", "(360,120)"),
        ("(360,140)", "(430,140)"),
        ("(550,115)", "(580,115)"),
        ("(390,160)", "(430,160)"),
        ("(380,180)", "(430,180)"),
        ("(460,200)", "(460,210)"),
        ("(490,140)", "(510,140)"),
        ("(540,140)", "(560,140)"),
        ("(560,125)", "(580,125)"),
        ("(300,255)", "(320,255)"),
        ("(310,265)", "(320,265)"),
        ("(350,260)", "(430,260)"),
        ("(390,280)", "(430,280)"),
        ("(380,300)", "(430,300)"),
        ("(490,260)", "(700,260)"),
        ("(700,220)", "(820,220)"),
    }
    expected_interrupt_paths = {
        "request_to_level_register", "request_level_clock_and_reset",
        "previous_level_inversion", "rising_edge_detection",
        "pending_set_or_hold", "pending_clock_and_reset", "pending_state_output",
    }
    if (not required_interrupt_wires <= interrupt_wires
            or set(interrupt_contract.get("verified_paths", []))
            != expected_interrupt_paths):
        raise VerificationError(
            f"{display_path(system.circuit_path)}: InterruptController wiring differs from contract"
        )


def verify_electrical_matrix(
    matrix: dict[str, object], machine: dict[str, object], profile_name: str, source: Path
) -> int:
    """Validate that an electrical matrix is complete and executable for a profile."""
    profile = load_profile(profile_name)
    if matrix.get("machine_format") != machine.get("format"):
        raise VerificationError(f"{display_path(source)}: matrix selects the wrong machine format")
    if matrix.get("profile") != profile_name:
        raise VerificationError(f"{display_path(source)}: matrix selects the wrong profile")

    opcode_names = set(opcode_table(profile))
    cases = matrix.get("opcode_cases")
    if not isinstance(cases, list) or any(not isinstance(case, dict) for case in cases):
        raise VerificationError(f"{display_path(source)}: opcode_cases must be an object array")
    case_opcodes = [case.get("opcode") for case in cases]
    if set(case_opcodes) != opcode_names:
        missing = sorted(opcode_names - set(case_opcodes))
        extra = sorted(set(case_opcodes) - opcode_names)
        raise VerificationError(
            f"{display_path(source)}: opcode matrix mismatch; missing={missing}, extra={extra}"
        )
    if len(cases) != len({case.get("id") for case in cases}):
        raise VerificationError(f"{display_path(source)}: duplicate opcode-case id")
    # Conditional jumps deliberately have taken and non-taken cases. Every
    # opcode must nevertheless own at least one independently identified case.
    if any(not case.get("id") or not case.get("program") for case in cases):
        raise VerificationError(f"{display_path(source)}: every opcode case needs an id and program")

    fixtures = matrix.get("fixtures")
    sticky = matrix.get("sticky_errors")
    if (not isinstance(fixtures, list) or not isinstance(sticky, list)
            or any(not isinstance(item, dict) for item in fixtures + sticky)):
        raise VerificationError(f"{display_path(source)}: invalid sticky-error fixtures")
    fixture_ids = {fixture.get("id") for fixture in fixtures}
    sticky_ids = {item.get("fixture") for item in sticky}
    if sticky_ids != fixture_ids or {item.get("flag") for item in sticky} != {
            "OVF", "DIV0", "ADDR", "INV", "ILL", "INPUT"}:
        raise VerificationError(f"{display_path(source)}: sticky-error coverage is incomplete")

    for case in fixtures + cases:
        try:
            assemble(str(case.get("program", "")), profile)
        except AssemblyError as exc:
            raise VerificationError(
                f"{display_path(source)}: fixture {case.get('id')!r} is invalid for {profile_name}: {exc}"
            ) from exc
        raw_words = case.get("raw_words", [])
        if (not isinstance(raw_words, list) or any(
                not isinstance(word, int) or not 0 <= word < (1 << profile.word_bits)
                for word in raw_words)):
            raise VerificationError(
                f"{display_path(source)}: fixture {case.get('id')!r} has an out-of-range raw word"
            )
    return len(fixtures)


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
    verify_small_profile_circuit(small_profile, small_machine)
    verify_system_circuit()

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
    # The legacy matrix predates the explicit profile field. Keep accepting it
    # as the frozen 1.0 contract while requiring it on every new profile.
    matrix.setdefault("profile", "tinycpu-16-12")
    fixture_count = verify_electrical_matrix(matrix, machine, "tinycpu-16-12", matrix_path)
    small_matrix_path = LOGISIM / "tinycpu-electrical-matrix-8-v1.json"
    small_matrix = load_json(small_matrix_path)
    if not isinstance(small_matrix, dict):
        raise VerificationError(f"{small_matrix_path.relative_to(ROOT)}: matrix root must be an object")
    small_fixture_count = verify_electrical_matrix(
        small_matrix, small_machine, "tinycpu-8-8", small_matrix_path
    )
    if small_fixture_count != fixture_count:
        raise VerificationError("electrical matrices have different sticky-error coverage")
    debug_path = LOGISIM / "tinycpu-debug-v1.json"
    debug = load_json(debug_path)
    if not isinstance(debug, dict) or debug.get("schema_version") != 1:
        raise VerificationError(f"{debug_path.relative_to(ROOT)}: unsupported debug schema")
    expected_reasons = {"breakpoint", "step", "halt", "halt_error", "step_limit"}
    if set(debug.get("stop_reasons", [])) != expected_reasons:
        raise VerificationError(f"{debug_path.relative_to(ROOT)}: incomplete stop reasons")
    if debug.get("breakpoint_timing") != "before_instruction":
        raise VerificationError(f"{debug_path.relative_to(ROOT)}: invalid breakpoint timing")
    return len(opcodes), fixture_count


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
