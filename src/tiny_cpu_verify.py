#!/usr/bin/env python3
"""Offline consistency checks for the checked-in TinyCPU artifacts.

This intentionally does not claim to replace electrical simulation.  It catches
broken JSON contracts and structural Logisim errors before the considerably more
expensive simulator acceptance run is started.
"""

from __future__ import annotations

import argparse
import hashlib
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




def verify_system_electrical_matrix(system: object, matrix: object | None = None) -> int:
    """Validate AP-18's executable scenario inventory before electrical integration."""
    source = system.electrical_matrix_path
    matrix = load_json(source) if matrix is None else matrix
    if not isinstance(matrix, dict):
        raise VerificationError(f"{display_path(source)}: matrix root must be an object")
    if (matrix.get("schema") != system.electrical_matrix
            or matrix.get("system") != system.name
            or matrix.get("machine_format") != system.machine_format
            or matrix.get("trace_schema") != system.trace_schema):
        raise VerificationError(f"{display_path(source)}: system matrix cross-links differ")

    required = matrix.get("required_behaviors")
    cases = matrix.get("cases")
    if (not isinstance(required, list) or not required
            or any(not isinstance(item, str) or not item for item in required)
            or len(required) != len(set(required))):
        raise VerificationError(f"{display_path(source)}: required_behaviors must be unique names")
    if not isinstance(cases, list) or not cases or any(not isinstance(case, dict) for case in cases):
        raise VerificationError(f"{display_path(source)}: cases must be a non-empty object array")
    ids = [case.get("id") for case in cases]
    if any(not isinstance(case_id, str) or not case_id for case_id in ids) or len(ids) != len(set(ids)):
        raise VerificationError(f"{display_path(source)}: case ids must be unique names")

    covered: set[str] = set()
    system_opcodes = {"ENABLE_INTERRUPTS", "DISABLE_INTERRUPTS", "RETURN_FROM_INTERRUPT"}
    for case in cases:
        coverage = case.get("covers")
        events = case.get("events")
        if (not isinstance(coverage, list) or not coverage
                or any(not isinstance(item, str) for item in coverage)):
            raise VerificationError(f"{display_path(source)}: case {case.get('id')!r} has invalid coverage")
        if (not isinstance(events, list) or any(
                not isinstance(event, dict)
                or not isinstance(event.get("edge"), int)
                or event["edge"] < 0
                or not set(event) <= {"edge", "interrupt_request", "reset"}
                or any(not isinstance(value, bool) for key, value in event.items() if key != "edge")
                for event in events)):
            raise VerificationError(f"{display_path(source)}: case {case.get('id')!r} has invalid events")
        try:
            assemble(str(case.get("program", "")), system.base_profile, system)
            vector_program = case.get("vector_program")
            if vector_program is not None:
                assemble(str(vector_program), system.base_profile, system)
        except AssemblyError as exc:
            raise VerificationError(
                f"{display_path(source)}: case {case.get('id')!r} is invalid: {exc}"
            ) from exc
        covered.update(coverage)

    missing = set(required).union(system_opcodes) - covered
    unknown = covered - set(required) - system_opcodes
    if missing or unknown:
        raise VerificationError(
            f"{display_path(source)}: system matrix coverage mismatch; "
            f"missing={sorted(missing)}, unknown={sorted(unknown)}"
        )
    return len(cases)


def verify_system_circuit() -> None:
    """Match the AP-18 system's public electrical boundary to its contract."""
    system = load_system_profile("tinycpu-peripherals-16-12-v1")
    verify_system_electrical_matrix(system)
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

    # Require the component boundaries on the top sheet and follow their
    # generated-box outputs all the way to the public state pins.  This keeps
    # an electrically empty overview sheet from passing component-only checks.
    top_instances = Counter(component.get("name") for component in circuit.findall("comp")
                            if component.get("lib") is None)
    if top_instances != Counter({"OutputMemoryPath": 1, "InterruptController": 1}):
        raise VerificationError(
            f"{display_path(system.circuit_path)}: system top components differ from contract"
        )
    top_wires = {(wire.get("from"), wire.get("to")) for wire in circuit.findall("wire")}
    required_top_wires = {
        ("(600,170)", "(790,170)"),  # output-port value state
        ("(600,190)", "(770,190)"),  # output-port validity state
        ("(770,190)", "(770,210)"),
        ("(770,210)", "(790,210)"),
        ("(600,340)", "(800,340)"),  # pending state
        ("(600,360)", "(800,360)"),  # mask state
        ("(600,400)", "(800,400)"),  # return address
        ("(600,440)", "(800,440)"),  # return-address validity
        ("(600,460)", "(800,460)"),  # handler state
        ("(200,250)", "(260,250)"),  # clock distribution
        ("(260,250)", "(380,250)"),
        ("(260,250)", "(260,340)"),
        ("(260,340)", "(380,340)"),
        ("(200,270)", "(280,270)"),  # reset distribution
        ("(280,270)", "(380,270)"),
        ("(280,270)", "(280,320)"),
        ("(280,320)", "(380,320)"),
        ("(200,360)", "(380,360)"),  # interrupt request
    }
    if not required_top_wires <= top_wires:
        raise VerificationError(
            f"{display_path(system.circuit_path)}: system top integration wiring differs from contract"
        )

    contract = load_json(LOGISIM / "tinycpu-peripherals-16-12-v1.json")
    cpu_contract = contract.get("components", {}).get("cpu_integration", {})
    cpu_name = cpu_contract.get("circuit")
    cpu_boundary = project.find(f"circuit[@name='{cpu_name}']")
    if cpu_boundary is None:
        raise VerificationError(
            f"{display_path(system.circuit_path)}: CPU integration boundary is missing"
        )
    cpu_pins = {}
    for component in cpu_boundary.findall("comp[@name='Pin']"):
        attributes = {item.get("name"): item.get("val") for item in component.findall("a")}
        cpu_pins[attributes.get("label", "")] = {
            "direction": attributes.get("type", "input"),
            "bits": int(attributes.get("width", "1")),
        }
    if cpu_pins != cpu_contract.get("pins"):
        raise VerificationError(
            f"{display_path(system.circuit_path)}: CPU integration boundary differs from contract"
        )
    cpu_wires = {
        frozenset((wire.get("from"), wire.get("to")))
        for wire in cpu_boundary.findall("wire")
    }
    cpu_pin_locations = {}
    for component in cpu_boundary.findall("comp[@name='Pin']"):
        attributes = {item.get("name"): item.get("val") for item in component.findall("a")}
        cpu_pin_locations[attributes.get("label", "")] = component.get("loc")
    required_cpu_paths = {
        "ram_read_value_to_cpu_read_value": ("RAM_READ_VALUE", "READ_VALUE"),
        "ram_read_valid_to_cpu_read_valid": ("RAM_READ_VALID", "READ_VALID"),
        "core_address_to_memory_address": ("CORE_ADDRESS", "ADDRESS"),
        "core_write_value_to_memory_write_value": ("CORE_WRITE_VALUE", "WRITE_VALUE"),
        "core_write_valid_to_memory_write_valid": ("CORE_WRITE_VALID", "WRITE_VALID"),
        "core_write_enable_to_memory_write_enable": ("CORE_WRITE_ENABLE", "WRITE_ENABLE"),
        "core_instruction_boundary_to_interrupt_boundary": (
            "CORE_INSTRUCTION_BOUNDARY", "INSTRUCTION_BOUNDARY"),
        "core_enable_request_to_interrupt_enable_request": (
            "CORE_ENABLE_REQUEST", "ENABLE_REQUEST"),
        "core_disable_request_to_interrupt_disable_request": (
            "CORE_DISABLE_REQUEST", "DISABLE_REQUEST"),
        "core_return_request_to_interrupt_return_request": (
            "CORE_RETURN_REQUEST", "RETURN_REQUEST"),
        "core_next_pc_to_interrupt_next_pc": ("CORE_NEXT_PC", "NEXT_PC"),
    }
    required_cpu_wires = {
        frozenset((cpu_pin_locations[source], cpu_pin_locations[target]))
        for source, target in required_cpu_paths.values()
    }
    if cpu_contract.get("verified_paths") != list(required_cpu_paths) \
            or not required_cpu_wires <= cpu_wires:
        raise VerificationError(
            f"{display_path(system.circuit_path)}: CPU integration data paths differ from contract"
        )

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
    accepted_write_gates = []
    for component in output.findall("comp[@name='AND Gate']"):
        attributes = {item.get("name"): item.get("val") for item in component.findall("a")}
        if attributes.get("label") == "OUTPUT_WRITE_ACCEPTED":
            accepted_write_gates.append((component.get("loc"), attributes.get("inputs", "2")))
    if (accepted_write_gates != [("(340,260)", "2")]
            or component_contract.get("accepted_write") != "WRITE_VALID AND WRITE_ENABLE"):
        raise VerificationError(
            f"{display_path(system.circuit_path)}: OutputPort accepted-write gate differs from contract"
        )
    output_wires = {
        (wire.get("from"), wire.get("to")) for wire in output.findall("wire")
    }
    # Check the actual Logisim register ports, not merely the presence of
    # suitably named components. Removing either half of a shared control net
    # must fail offline before an electrical run is attempted.
    expected_output_wires = {
        ("(200,130)", "(500,130)"),
        ("(200,230)", "(290,230)"),
        ("(200,270)", "(310,270)"),
        ("(200,320)", "(480,320)"),
        ("(200,380)", "(530,380)"),
        ("(290,230)", "(290,250)"),
        ("(290,230)", "(560,230)"),
        ("(290,250)", "(310,250)"),
        ("(340,260)", "(460,260)"),
        ("(460,150)", "(460,260)"),
        ("(460,150)", "(500,150)"),
        ("(460,260)", "(580,260)"),
        ("(480,170)", "(480,280)"),
        ("(480,170)", "(500,170)"),
        ("(480,280)", "(480,320)"),
        ("(480,280)", "(580,280)"),
        ("(530,190)", "(530,310)"),
        ("(530,310)", "(530,380)"),
        ("(530,310)", "(610,310)"),
        ("(560,130)", "(730,130)"),
        ("(560,230)", "(560,240)"),
        ("(560,240)", "(580,240)"),
        ("(610,300)", "(610,310)"),
        ("(640,240)", "(680,240)"),
    }
    expected_paths = {
        "write_value_to_value_register", "write_valid_to_valid_register",
        "shared_accepted_write_enable", "shared_clock", "shared_reset",
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
    # Logisim removes labels from components which do not render them when a
    # project is saved in the GUI.  Treat labels as identifiers only for the
    # gates where they are retained, and identify the comparator/multiplexers
    # by their electrical role below instead of requiring hidden metadata.
    required = {"RAM_WRITE_GATE", "OUTPUT_WRITE_GATE", "OUTPUT_PORT_VALUE",
                "OUTPUT_PORT_VALID"}
    if not required <= labelled:
        raise VerificationError(
            f"{display_path(system.circuit_path)}: OutputMemoryPath routing differs from contract"
        )
    constant = memory_path.find("comp[@name='Constant']/a[@name='value']")
    if constant is None or int(constant.get("val", "-1"), 0) != path_contract.get("output_address"):
        raise VerificationError(
            f"{display_path(system.circuit_path)}: OutputMemoryPath address differs from contract"
        )
    path_components = Counter(component.get("name") for component in memory_path.findall("comp"))
    if path_components["Comparator"] != 1 or path_components["Multiplexer"] != 2:
        raise VerificationError(
            f"{display_path(system.circuit_path)}: OutputMemoryPath routing differs from contract"
        )
    memory_wires = {
        (wire.get("from"), wire.get("to")) for wire in memory_path.findall("wire")
    }
    # These segments anchor every functional route at a real component port.
    # The intervening orthogonal segments remain free to be redrawn, but no
    # declared path may be replaced with labels alone.
    required_memory_wires = {
        ("(410,190)", "(480,190)"),  # address -> comparator
        ("(460,210)", "(480,210)"),  # reserved constant -> comparator
        ("(520,200)", "(560,200)"),  # comparator -> address-match rail
        ("(560,460)", "(610,460)"),  # match -> RAM write gate (negated)
        ("(540,480)", "(620,480)"),  # write enable -> RAM write gate
        ("(560,360)", "(620,360)"),  # match -> output write gate
        ("(600,350)", "(620,350)"),  # validity -> output write gate
        ("(540,370)", "(620,370)"),  # write enable -> output write gate
        ("(410,90)", "(920,90)"),  # RAM value -> value mux
        ("(410,150)", "(920,150)"),  # RAM validity -> validity mux
        ("(860,110)", "(920,110)"),  # output value -> value mux
        ("(900,170)", "(920,170)"),  # output validity -> validity mux
        ("(930,120)", "(930,130)"),  # match -> value selector
        ("(880,200)", "(930,200)"),  # match -> validity selector
        ("(410,260)", "(780,260)"),  # write value -> output register
        ("(700,390)", "(780,390)"),  # write validity -> output register
        ("(720,410)", "(780,410)"),  # gated write -> valid register
        ("(740,300)", "(780,300)"),  # shared clock
        ("(760,330)", "(810,330)"),  # shared reset rail
        ("(810,320)", "(810,330)"),  # reset branch to value register
        ("(950,100)", "(970,100)"),  # selected value -> read output
        ("(950,160)", "(970,160)"),  # selected validity -> read output
        ("(650,470)", "(980,470)"),  # gated RAM write output
        ("(860,260)", "(980,260)"),  # output value state
        ("(900,390)", "(980,390)"),  # output validity state
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
    interrupt_registers = []
    for component in interrupt.findall("comp[@name='Register']"):
        attributes = {item.get("name"): item.get("val") for item in component.findall("a")}
        interrupt_registers.append(int(attributes.get("width", "1")))
    if Counter(interrupt_registers) != Counter(interrupt_contract.get("registers", {}).values()):
        raise VerificationError(
            f"{display_path(system.circuit_path)}: InterruptController registers differ from contract"
        )
    interrupt_labels = {
        item.get("val")
        for component in interrupt.findall("comp")
        for item in component.findall("a[@name='label']")
    }
    required_interrupt_labels = {
        "RISING_EDGE_DETECT", "INTERRUPT_ACCEPT_GATE", "ILLEGAL_RETURN_GATE",
        "PENDING_SET_OR_HOLD", "PENDING_HOLD_UNTIL_ACCEPT",
        "MASK_HOLD", "MASK_NEXT", "VALID_RETURN_GATE",
        "RETURN_VALID_HOLD", "RETURN_VALID_NEXT", "HANDLER_HOLD",
        "HANDLER_NEXT",
    }
    if not required_interrupt_labels <= interrupt_labels:
        raise VerificationError(
            f"{display_path(system.circuit_path)}: InterruptController routing differs from contract"
        )
    vector = None
    for constant_component in interrupt.findall("comp[@name='Constant']"):
        value = constant_component.find("a[@name='value']")
        width = constant_component.find("a[@name='width']")
        if (value is not None and width is not None
                and int(width.get("val", "1"), 0) == address_bits):
            if vector is not None:
                raise VerificationError(
                    f"{display_path(system.circuit_path)}: InterruptController vector is ambiguous"
                )
            vector = value
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
    # The controller is a deliberately hand-routed state machine.  Its
    # versioned canonical wire list lets a visual redraw be reviewed once and
    # then protects every branch, including long feedback paths which cannot
    # be identified reliably from component labels alone.
    wire_fingerprint = hashlib.sha256("\n".join(
        f"{start}->{end}" for start, end in sorted(interrupt_wires)
    ).encode("ascii")).hexdigest()
    expected_interrupt_paths = {
        "request_to_level_register", "request_level_clock_and_reset",
        "previous_level_inversion", "rising_edge_detection",
        "pending_set_or_hold", "pending_clock_and_reset", "pending_state_output",
        "accept_requires_pending_enabled_boundary_and_idle", "accept_state_output",
        "pending_cleared_on_accept", "mask_set_by_enable_or_return",
        "mask_cleared_by_disable_or_accept", "mask_state_hold",
        "mask_clock_and_reset", "mask_state_output",
        "return_address_captured_on_accept",
        "return_address_valid_set_on_accept", "return_state_clock_and_reset",
        "return_address_valid_cleared_on_valid_return",
        "return_address_valid_held_without_valid_return",
        "handler_set_on_interrupt_accept", "handler_cleared_on_valid_return",
        "handler_held_until_valid_return",
        "interrupt_vector_selected_without_valid_return",
        "return_address_selected_on_valid_return",
        "valid_return_selects_target", "selected_target_output",
        "return_state_outputs",
    }
    if (wire_fingerprint != interrupt_contract.get("wiring_sha256")
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
    expected_profiles = ((profile, machine, 16, 4096, 22),)
    for current_profile, current_machine, bits, size, word_bits in expected_profiles:
        if (current_profile.get("data_bits"), current_profile.get("memory_size"),
                current_profile.get("machine_format_id"), current_machine.get("word_bits")) != (
                    bits, size, current_machine.get("format"), word_bits):
            raise VerificationError(f"profile {current_profile.get('name')!r} is inconsistent")
        if current_profile.get("machine_format") != current_machine_path_name(current_machine):
            raise VerificationError(f"profile {current_profile.get('name')!r} selects the wrong format file")
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
        if (not isinstance(code, int) or not 0 <= code < 64
                or hexadecimal != f"0x{code:02x}"
                or not isinstance(mnemonic, str)):
            raise VerificationError(
                f"{machine_path.relative_to(ROOT)}: inconsistent opcode entry at index {index}"
            )
        codes.append(code)
        mnemonics.append(mnemonic)
    if len(set(codes)) != len(codes) or len(set(mnemonics)) != len(mnemonics):
        raise VerificationError(f"{machine_path.relative_to(ROOT)}: duplicate opcode code or mnemonic")

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
    return "tinycpu-machine-v1.json"


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
