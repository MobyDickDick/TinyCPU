from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).parents[1] / "src" / "tiny_cpu_verify.py"
SPEC = importlib.util.spec_from_file_location("tiny_cpu_verify", MODULE_PATH)
assert SPEC and SPEC.loader
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)

WIRE_MODULE_PATH = MODULE_PATH.with_name("tiny_cpu_wire_contacts.py")
WIRE_SPEC = importlib.util.spec_from_file_location(
    "tiny_cpu_wire_contacts", WIRE_MODULE_PATH
)
assert WIRE_SPEC and WIRE_SPEC.loader
WIRE_CONTACTS = importlib.util.module_from_spec(WIRE_SPEC)
sys.modules[WIRE_SPEC.name] = WIRE_CONTACTS
WIRE_SPEC.loader.exec_module(WIRE_CONTACTS)


def _component_by_label(circuit: ET.Element, label: str) -> ET.Element:
    """Return one labelled component without depending on its canvas position."""
    matches = [
        component for component in circuit.findall("comp")
        if any(
            attribute.get("name") == "label" and attribute.get("val") == label
            for attribute in component.findall("a")
        )
    ]
    if len(matches) != 1:
        raise AssertionError(f"expected exactly one component labelled {label!r}")
    return matches[0]


def _component_terminal(component: ET.Element, x: int, y: int) -> str:
    component_x, component_y = map(
        int, component.get("loc", "").strip("()").split(",")
    )
    return f"({component_x + x},{component_y + y})"


def _subcircuit_ports(project: ET.Element, circuit: ET.Element,
                      label: str) -> dict[str, str]:
    instance = _component_by_label(circuit, label)
    definition = project.find(f"circuit[@name='{instance.get('name')}']")
    if definition is None:
        raise AssertionError(f"missing definition for {instance.get('name')}")
    return VERIFY.generated_symbol_ports(definition, instance)


def _remove_wire_at(circuit: ET.Element, endpoint: str) -> None:
    """Remove a wire incident on a named/derived electrical terminal."""
    wire = next((
        item for item in circuit.findall("wire")
        if endpoint in {item.get("from"), item.get("to")}
    ), None)
    if wire is None:
        raise AssertionError(f"no wire is connected to terminal {endpoint}")
    circuit.remove(wire)


def _wire_path_exists(circuit: ET.Element, start: str, end: str) -> bool:
    """Follow a Logisim net, including explicit T-junction endpoints."""
    wires = [(wire.get("from"), wire.get("to"))
             for wire in circuit.findall("wire")]
    points = {point for wire in wires for point in wire} | {start, end}

    def coordinates(value: str) -> tuple[int, int]:
        return tuple(map(int, value.strip("()").split(",")))

    graph: dict[str, set[str]] = {}
    for left, right in wires:
        x1, y1 = coordinates(left)
        x2, y2 = coordinates(right)
        contacts = [
            point for point in points
            if ((x1 == x2 == coordinates(point)[0]
                 and min(y1, y2) <= coordinates(point)[1] <= max(y1, y2))
                or (y1 == y2 == coordinates(point)[1]
                    and min(x1, x2) <= coordinates(point)[0] <= max(x1, x2)))
        ]
        contacts.sort(key=coordinates)
        for first, second in zip(contacts, contacts[1:]):
            graph.setdefault(first, set()).add(second)
            graph.setdefault(second, set()).add(first)

    pending, visited = [start], set()
    while pending:
        point = pending.pop()
        if point == end:
            return True
        if point not in visited:
            visited.add(point)
            pending.extend(graph.get(point, ()))
    return False


def _multiplexer_driven_by(circuit: ET.Element, pin_label: str,
                           width: str = "1") -> ET.Element:
    """Resolve a classic mux by the net on its select-1 data input."""
    pin = _component_by_label(circuit, pin_label)
    matches = []
    for component in circuit.findall("comp[@name='Multiplexer']"):
        attributes = {
            attribute.get("name"): attribute.get("val")
            for attribute in component.findall("a")
        }
        if attributes.get("width", "1") != width:
            continue
        if _wire_path_exists(
            circuit, pin.get("loc"), _component_terminal(component, -30, 10)
        ):
            matches.append(component)
    if len(matches) != 1:
        raise AssertionError(
            f"expected one {width}-bit multiplexer driven by {pin_label}"
        )
    return matches[0]


class CircuitVerificationTests(unittest.TestCase):
    def test_pin_handoffs_reject_crossed_address_and_ram_value_widths(self) -> None:
        interfaces = {
            "CPU": {"ADDRESS": {"direction": "output", "bits": 12}},
            "Memory": {"RAM_READ_VALUE": {"direction": "input", "bits": 16}},
        }
        with self.assertRaisesRegex(
            VERIFY.VerificationError,
            r"bus width mismatch.*CPU\.ADDRESS -> Memory\.RAM_READ_VALUE: 12 != 16",
        ):
            VERIFY.verify_pin_handoffs(
                interfaces,
                (("CPU", "ADDRESS", "Memory", "RAM_READ_VALUE"),),
            )

    def test_pin_handoffs_accept_matching_address_buses(self) -> None:
        interfaces = {
            "CPU": {"ADDRESS": {"direction": "output", "bits": 12}},
            "Memory": {"ADDRESS": {"direction": "input", "bits": 12}},
        }
        VERIFY.verify_pin_handoffs(
            interfaces,
            (("CPU", "ADDRESS", "Memory", "ADDRESS"),),
        )

    def write_project(self, circuit_body: str, main: str = "Main") -> Path:
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        path = directory / "test.circ"
        path.write_text(
            f'<project><main name="{main}" /><circuit name="Main">{circuit_body}</circuit></project>',
            encoding="utf-8",
        )
        return path

    def test_accepts_an_orthogonal_wire(self) -> None:
        path = self.write_project('<wire from="(0,0)" to="(10,0)" />')
        self.assertEqual(VERIFY.verify_circuit(path), (1, 1))

    def test_rejects_a_diagonal_wire(self) -> None:
        path = self.write_project('<wire from="(0,0)" to="(10,10)" />')
        with self.assertRaisesRegex(VERIFY.VerificationError, "diagonal wire"):
            VERIFY.verify_circuit(path)

    def test_rejects_a_missing_main(self) -> None:
        path = self.write_project("", main="Missing")
        with self.assertRaisesRegex(VERIFY.VerificationError, "does not exist"):
            VERIFY.verify_circuit(path)

    def test_rejects_duplicate_pin_labels(self) -> None:
        pins = "".join(
            f'<comp lib="0" loc="({x},0)" name="Pin"><a name="label" val="A" /></comp>'
            for x in (0, 10)
        )
        path = self.write_project(pins)
        with self.assertRaisesRegex(VERIFY.VerificationError, "duplicate Pin labels"):
            VERIFY.verify_circuit(path)


    def test_ap18_circuit_matches_public_pin_contract(self) -> None:
        VERIFY.verify_system_circuit()

    def test_ap18_system_matrix_covers_every_new_behavior(self) -> None:
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        self.assertEqual(VERIFY.verify_system_electrical_matrix(system), 7)

    def test_ap18_system_matrix_rejects_missing_coverage(self) -> None:
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        matrix = VERIFY.load_json(system.electrical_matrix_path)
        matrix["cases"][0]["covers"] = ["output-invalid-write"]
        with self.assertRaisesRegex(VERIFY.VerificationError, "coverage mismatch"):
            VERIFY.verify_system_electrical_matrix(system, matrix)

    def test_ap18_schematic_uses_only_visible_wiring(self) -> None:
        root = MODULE_PATH.parents[1]
        project = VERIFY.ET.parse(
            root / "hardware" / "logisim" / "TinyCPU_Peripherals.circ"
        ).getroot()
        self.assertEqual(project.findall(".//comp[@name='Tunnel']"), [])

    def test_ap18_authored_integration_layout_is_not_rebuilt_from_stale_coordinates(self) -> None:
        """Keep removed pre-redraw routing from being presented as a repair."""
        project = VERIFY.ET.parse(
            MODULE_PATH.parents[1] / "hardware/logisim/TinyCPU_Peripherals.circ"
        ).getroot()
        top = project.find("circuit[@name='TinyCPUSystemMain']")
        boundary = project.find("circuit[@name='CPUIntegrationBoundary']")
        self.assertIsNotNone(top)
        self.assertIsNotNone(boundary)

        top_instances = {
            component.get("name"): component.get("loc")
            for component in top.findall("comp")
            if component.get("lib") is None
        }
        self.assertEqual(top_instances, {
            "CPUIntegrationBoundary": "(1260,610)",
            "OutputMemoryPath": "(810,360)",
            "InterruptController": "(810,590)",
        })
        core = boundary.find("comp[@name='TinyCPUMain']")
        self.assertIsNotNone(core)
        self.assertEqual(core.get("loc"), "(660,160)")

        wires = {(wire.get("from"), wire.get("to")) for wire in top.findall("wire")}
        stale_reconstruction = {
            ("(1190,830)", "(1270,830)"),
            ("(1270,830)", "(1270,150)"),
            ("(1270,150)", "(410,150)"),
        }
        self.assertFalse(stale_reconstruction <= wires)

    def test_ap18_illegal_return_gate_output_reaches_error_flags(self) -> None:
        project = VERIFY.ET.parse(
            MODULE_PATH.parents[1] / "hardware/logisim/TinyCPU.circ"
        ).getroot()
        main = project.find("circuit[@name='TinyCPUMain']")
        self.assertIsNotNone(main)
        illegal_return_or = next(
            component
            for component in main.findall("comp[@name='OR Gate']")
            if {
                attribute.get("name"): attribute.get("val")
                for attribute in component.findall("a")
            }.get("label") == "ILLEGAL_RETURN_OR"
        )
        error_flags = _subcircuit_ports(project, main, "ERROR_FLAGS")
        self.assertTrue(_wire_path_exists(
            main, illegal_return_or.get("loc"), error_flags["SET_ILL"]
        ))

    def test_ap18_system_top_requires_public_state_wiring(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        circuit = temporary / "logisim" / "TinyCPU_Peripherals.circ"
        circuit.write_text(circuit.read_text(encoding="utf-8").replace(
            '<wire from="(820,960)" to="(1540,960)"/>', "", 1), encoding="utf-8")
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        original = VERIFY.LOGISIM
        VERIFY.LOGISIM = temporary / "logisim"
        self.addCleanup(setattr, VERIFY, "LOGISIM", original)
        with mock.patch.object(VERIFY, "load_system_profile",
                               return_value=replace(system, circuit_path=circuit)):
            with self.assertRaisesRegex(VERIFY.VerificationError,
                                        "system top integration wiring"):
                VERIFY.verify_system_circuit()

    def test_ap18_system_top_requires_control_input_wiring(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        circuit = temporary / "logisim" / "TinyCPU_Peripherals.circ"
        circuit.write_text(circuit.read_text(encoding="utf-8").replace(
            '<wire from="(330,630)" to="(590,630)"/>', "", 1), encoding="utf-8")
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        original = VERIFY.LOGISIM
        VERIFY.LOGISIM = temporary / "logisim"
        self.addCleanup(setattr, VERIFY, "LOGISIM", original)
        with mock.patch.object(VERIFY, "load_system_profile",
                               return_value=replace(system, circuit_path=circuit)):
            with self.assertRaisesRegex(VERIFY.VerificationError,
                                        "system top integration wiring"):
                VERIFY.verify_system_circuit()

    def test_ap18_output_port_has_unambiguous_control_routes(self) -> None:
        project = VERIFY.ET.parse(
            MODULE_PATH.parents[1] / "hardware/logisim/TinyCPU_Peripherals.circ"
        ).getroot()
        output = project.find("circuit[@name='OutputPort']")
        self.assertIsNotNone(output)
        self.assertEqual(WIRE_CONTACTS.inspect_circuit(output), [])

    def test_ap18_peripheral_project_has_only_orthogonal_wires(self) -> None:
        path = MODULE_PATH.parents[1] / "hardware/logisim/TinyCPU_Peripherals.circ"
        wires, circuits = VERIFY.verify_circuit(path)
        self.assertGreater(wires, 0)
        self.assertGreater(circuits, 0)

    def test_ap18_system_routes_have_no_implicit_contacts(self) -> None:
        project = VERIFY.ET.parse(
            MODULE_PATH.parents[1] / "hardware/logisim/TinyCPU_Peripherals.circ"
        ).getroot()
        for name in ("TinyCPUSystemMain", "CPUIntegrationBoundary"):
            with self.subTest(circuit=name):
                circuit = project.find(f"circuit[@name='{name}']")
                self.assertIsNotNone(circuit)
                self.assertEqual(WIRE_CONTACTS.inspect_circuit(circuit), [])

    def test_ap18_cpu_integration_boundary_matches_contract(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        circuit = temporary / "logisim" / "TinyCPU_Peripherals.circ"
        circuit.write_text(circuit.read_text(encoding="utf-8").replace(
            'label" val="NEXT_PC"', 'label" val="BROKEN_NEXT_PC"', 1),
            encoding="utf-8",
        )
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        original = VERIFY.LOGISIM
        VERIFY.LOGISIM = temporary / "logisim"
        self.addCleanup(setattr, VERIFY, "LOGISIM", original)
        with mock.patch.object(VERIFY, "load_system_profile",
                               return_value=replace(system, circuit_path=circuit)):
            with self.assertRaisesRegex(VERIFY.VerificationError,
                                        "CPU integration boundary differs"):
                VERIFY.verify_system_circuit()

    def test_ap18_cpu_integration_requires_full_cpu_core(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        circuit = temporary / "logisim" / "TinyCPU_Peripherals.circ"
        project = ET.parse(circuit)
        boundary = project.getroot().find("circuit[@name='CPUIntegrationBoundary']")
        self.assertIsNotNone(boundary)
        core = boundary.find("comp[@name='TinyCPUMain']")
        self.assertIsNotNone(core)
        boundary.remove(core)
        project.write(circuit, encoding="utf-8", xml_declaration=True)
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        with mock.patch.object(VERIFY, "LOGISIM", temporary / "logisim"), \
             mock.patch.object(
                 VERIFY,
                 "load_system_profile",
                 return_value=replace(system, circuit_path=circuit),
             ):
            with self.assertRaisesRegex(
                VERIFY.VerificationError, "full CPU core placement differs"
            ):
                VERIFY.verify_system_circuit()

    def test_ap18_cpu_integration_requires_external_memory_interface(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        core = temporary / "logisim" / "TinyCPU.circ"
        core.write_text(core.read_text(encoding="utf-8").replace(
            'label" val="EXTERNAL_MEMORY_VALUE"',
            'label" val="BROKEN_EXTERNAL_MEMORY_VALUE"',
            1,
        ), encoding="utf-8")
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        with mock.patch.object(VERIFY, "LOGISIM", temporary / "logisim"), \
             mock.patch.object(
                 VERIFY,
                 "load_system_profile",
                 return_value=replace(
                     system,
                     circuit_path=temporary / "logisim" / "TinyCPU_Peripherals.circ",
                 ),
             ):
            with self.assertRaisesRegex(
                VERIFY.VerificationError, "external-memory interface differs"
            ):
                VERIFY.verify_system_circuit()

    def test_ap18_cpu_integration_requires_external_memory_selection_paths(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        selector_cases = (
            ("EXTERNAL_MEMORY_VALUE", "16", (-30, -10), (-30, 10), (-20, 20), (0, 0)),
            ("EXTERNAL_MEMORY_VALID", "1", (-30, -10), (-30, 10), (-20, 20), (0, 0)),
        )
        for pin_label, width, *offsets in selector_cases:
            for offset in offsets:
                with self.subTest(selector=pin_label, terminal=offset):
                    temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
                    shutil.copytree(source, temporary / "logisim")
                    core = temporary / "logisim" / "TinyCPU.circ"
                    project = ET.parse(core)
                    main = project.getroot().find("circuit[@name='TinyCPUMain']")
                    self.assertIsNotNone(main)
                    selector = _multiplexer_driven_by(main, pin_label, width)
                    _remove_wire_at(
                        main, _component_terminal(selector, *offset)
                    )
                    project.write(core, encoding="utf-8", xml_declaration=True)
                    system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
                    with mock.patch.object(VERIFY, "LOGISIM", temporary / "logisim"), \
                         mock.patch.object(
                             VERIFY,
                             "load_system_profile",
                             return_value=replace(
                                 system,
                                 circuit_path=temporary / "logisim" / "TinyCPU_Peripherals.circ",
                             ),
                         ):
                        with self.assertRaisesRegex(
                            VERIFY.VerificationError,
                            "external-memory selection paths differ",
                        ):
                            VERIFY.verify_system_circuit()

    def test_ap18_cpu_integration_requires_external_write_paths(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        for label in (
            "EXTERNAL_WRITE_VALUE",
            "EXTERNAL_WRITE_VALID",
            "EXTERNAL_WRITE_ENABLE",
        ):
            with self.subTest(label=label):
                temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
                shutil.copytree(source, temporary / "logisim")
                core = temporary / "logisim" / "TinyCPU.circ"
                project = ET.parse(core)
                main = project.getroot().find("circuit[@name='TinyCPUMain']")
                self.assertIsNotNone(main)
                pin = next(
                    component for component in main.findall("comp[@name='Pin']")
                    if any(
                        attribute.get("name") == "label"
                        and attribute.get("val") == label
                        for attribute in component.findall("a")
                    )
                )
                endpoint = pin.get("loc")
                wire = next(
                    item for item in main.findall("wire")
                    if endpoint in {item.get("from"), item.get("to")}
                )
                main.remove(wire)
                project.write(core, encoding="utf-8", xml_declaration=True)
                system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
                with mock.patch.object(VERIFY, "LOGISIM", temporary / "logisim"), \
                     mock.patch.object(
                         VERIFY,
                         "load_system_profile",
                         return_value=replace(
                             system,
                             circuit_path=temporary / "logisim" / "TinyCPU_Peripherals.circ",
                         ),
                     ):
                    with self.assertRaisesRegex(
                        VERIFY.VerificationError, "external-write paths differ"
                    ):
                        VERIFY.verify_system_circuit()

    def test_ap18_cpu_integration_requires_interrupt_command_paths(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        for label in (
            "INSTRUCTION_BOUNDARY",
            "ENABLE_INTERRUPTS_REQUEST",
            "DISABLE_INTERRUPTS_REQUEST",
            "RETURN_FROM_INTERRUPT_REQUEST",
        ):
            with self.subTest(label=label):
                temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
                shutil.copytree(source, temporary / "logisim")
                core = temporary / "logisim" / "TinyCPU.circ"
                project = ET.parse(core)
                main = project.getroot().find("circuit[@name='TinyCPUMain']")
                self.assertIsNotNone(main)
                pin = next(
                    component for component in main.findall("comp[@name='Pin']")
                    if any(
                        attribute.get("name") == "label"
                        and attribute.get("val") == label
                        for attribute in component.findall("a")
                    )
                )
                endpoint = pin.get("loc")
                wire = next(
                    item for item in main.findall("wire")
                    if endpoint in {item.get("from"), item.get("to")}
                )
                main.remove(wire)
                project.write(core, encoding="utf-8", xml_declaration=True)
                system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
                with mock.patch.object(VERIFY, "LOGISIM", temporary / "logisim"), \
                     mock.patch.object(
                         VERIFY,
                         "load_system_profile",
                         return_value=replace(
                             system,
                             circuit_path=temporary / "logisim" / "TinyCPU_Peripherals.circ",
                         ),
                     ):
                    with self.assertRaisesRegex(
                        VERIFY.VerificationError, "interrupt-command paths differ"
                    ):
                        VERIFY.verify_system_circuit()

    def test_ap18_interrupt_command_sources_belong_to_contract(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        contract_path = temporary / "logisim" / "tinycpu-peripherals-16-12-v1.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["components"]["cpu_integration"][
            "core_interrupt_command_sources"
        ]["ENABLE_INTERRUPTS_REQUEST"] = "(0,0)"
        contract_path.write_text(json.dumps(contract), encoding="utf-8")
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        with mock.patch.object(VERIFY, "LOGISIM", temporary / "logisim"), \
             mock.patch.object(
                 VERIFY,
                 "load_system_profile",
                 return_value=replace(
                     system,
                     circuit_path=temporary / "logisim" / "TinyCPU_Peripherals.circ",
                 ),
             ):
            with self.assertRaisesRegex(
                VERIFY.VerificationError,
                "interrupt-command source contract differs",
            ):
                VERIFY.verify_system_circuit()

    def test_ap18_interrupt_decoder_may_move_without_changing_its_contract(self) -> None:
        """The redrawn FetchDecode command paths remain electrically valid."""
        VERIFY.verify_system_circuit()

    def test_ap18_fetch_opcode_path_is_required(self) -> None:
        """Follow named ports and connectivity, not the current canvas coordinates."""
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        core = temporary / "logisim" / "TinyCPU.circ"
        project = ET.parse(core)
        main = project.getroot().find("circuit[@name='TinyCPUMain']")
        self.assertIsNotNone(main)
        controls = next(
            component for component in main.findall("comp[@name='FetchDecodeControls']")
        )
        definition = project.getroot().find("circuit[@name='FetchDecodeControls']")
        self.assertIsNotNone(definition)
        opcode_terminal = VERIFY.generated_symbol_ports(definition, controls)["OPCODE"]
        _remove_wire_at(main, opcode_terminal)
        project.write(core, encoding="utf-8", xml_declaration=True)
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        with mock.patch.object(VERIFY, "LOGISIM", temporary / "logisim"), \
             mock.patch.object(
                 VERIFY,
                 "load_system_profile",
                 return_value=replace(
                     system,
                     circuit_path=temporary / "logisim" / "TinyCPU_Peripherals.circ",
                 ),
             ):
            with self.assertRaisesRegex(
                VERIFY.VerificationError,
                "opcode path from FetchDecode to FetchDecodeControls differs",
            ):
                VERIFY.verify_system_circuit()

    def test_ap18_instruction_boundary_constant_must_be_asserted(self) -> None:
        """An explicitly cleared Constant must not masquerade as a boundary."""
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        core = temporary / "logisim" / "TinyCPU.circ"
        project = ET.parse(core)
        main = project.getroot().find("circuit[@name='TinyCPUMain']")
        self.assertIsNotNone(main)
        boundary = _component_by_label(main, "INSTRUCTION_BOUNDARY")
        constants = [
            component for component in main.findall("comp[@name='Constant']")
            if _wire_path_exists(main, component.get("loc"), boundary.get("loc"))
        ]
        self.assertEqual(len(constants), 1)
        value = next((
            attribute for attribute in constants[0].findall("a")
            if attribute.get("name") == "value"
        ), None)
        if value is None:
            value = ET.SubElement(constants[0], "a", {"name": "value"})
        value.set("val", "0x0")
        project.write(core, encoding="utf-8", xml_declaration=True)
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        with mock.patch.object(VERIFY, "LOGISIM", temporary / "logisim"), \
             mock.patch.object(
                 VERIFY,
                 "load_system_profile",
                 return_value=replace(
                     system,
                     circuit_path=temporary / "logisim" / "TinyCPU_Peripherals.circ",
                 ),
             ):
            with self.assertRaisesRegex(
                VERIFY.VerificationError, "interrupt-command paths differ"
            ):
                VERIFY.verify_system_circuit()

    def test_ap18_cpu_next_pc_path_is_required(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        core = temporary / "logisim" / "TinyCPU.circ"
        project = ET.parse(core)
        main = project.getroot().find("circuit[@name='TinyCPUMain']")
        next_pc = _component_by_label(main, "NEXT_PC")
        _remove_wire_at(main, next_pc.get("loc", ""))
        project.write(core, encoding="utf-8", xml_declaration=True)
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        with mock.patch.object(VERIFY, "LOGISIM", temporary / "logisim"), \
             mock.patch.object(
                 VERIFY,
                 "load_system_profile",
                 return_value=replace(
                     system,
                     circuit_path=temporary / "logisim" / "TinyCPU_Peripherals.circ",
                 ),
             ):
            with self.assertRaisesRegex(VERIFY.VerificationError, "next-PC path"):
                VERIFY.verify_system_circuit()

    def test_ap18_interrupt_command_paths_reject_disconnection(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        core = temporary / "logisim" / "TinyCPU.circ"
        project = ET.parse(core)
        main = project.getroot().find("circuit[@name='TinyCPUMain']")
        controls = _subcircuit_ports(
            project.getroot(), main, "FETCH_DECODE_CONTROLS"
        )
        _remove_wire_at(main, controls["DISABLE_INTERRUPTS_REQUEST"])
        project.write(core, encoding="utf-8", xml_declaration=True)
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        with mock.patch.object(VERIFY, "LOGISIM", temporary / "logisim"), \
             mock.patch.object(
                 VERIFY,
                 "load_system_profile",
                 return_value=replace(
                     system,
                     circuit_path=temporary / "logisim" / "TinyCPU_Peripherals.circ",
                 ),
             ):
            with self.assertRaisesRegex(
                VERIFY.VerificationError, "interrupt-command paths differ"
            ):
                VERIFY.verify_system_circuit()

    def test_ap18_cpu_integration_accepts_unrendered_selector_labels(self) -> None:
        """A normal Logisim save may discard labels absent from the appearance."""
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        core = temporary / "logisim" / "TinyCPU.circ"
        text = core.read_text(encoding="utf-8")
        for label in ("EXTERNAL_MEMORY_VALUE_SELECT", "EXTERNAL_MEMORY_VALID_SELECT"):
            text = text.replace(f'      <a name="label" val="{label}"/>\n', "", 1)
        core.write_text(text, encoding="utf-8")
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        with mock.patch.object(VERIFY, "LOGISIM", temporary / "logisim"), \
             mock.patch.object(
                 VERIFY,
                 "load_system_profile",
                 return_value=replace(
                     system,
                     circuit_path=temporary / "logisim" / "TinyCPU_Peripherals.circ",
                 ),
             ):
            VERIFY.verify_system_circuit()

    def test_ap18_cpu_integration_keeps_operation_validity_inputs_separate(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        core = temporary / "logisim" / "TinyCPU.circ"
        project = ET.parse(core)
        main = project.getroot().find("circuit[@name='TinyCPUMain']")
        operations = _subcircuit_ports(project.getroot(), main, "OPERATIONS_INSTANCE")
        memory = _subcircuit_ports(project.getroot(), main, "MEMORY_INSTANCE")
        datapath = _subcircuit_ports(project.getroot(), main, "DATAPATH_INSTANCE")
        for target in (operations["MEMORY_VALID"], operations["ACC_VALID"]):
            _remove_wire_at(main, target)
        for source, target in (
            (memory["MEMORY_VALID"], operations["ACC_VALID"]),
            (datapath["ACC_VALID_OUT"], operations["MEMORY_VALID"]),
        ):
            sx, sy = map(int, source.strip("()").split(","))
            tx, ty = map(int, target.strip("()").split(","))
            bend = f"({sx},{ty})"
            ET.SubElement(main, "wire", {"from": source, "to": bend})
            ET.SubElement(main, "wire", {"from": bend, "to": target})
        project.write(core, encoding="utf-8", xml_declaration=True)
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        with mock.patch.object(VERIFY, "LOGISIM", temporary / "logisim"), \
             mock.patch.object(
                 VERIFY,
                 "load_system_profile",
                 return_value=replace(
                     system,
                     circuit_path=temporary / "logisim" / "TinyCPU_Peripherals.circ",
                 ),
             ):
            with self.assertRaisesRegex(
                VERIFY.VerificationError, "validity inputs are crossed"
            ):
                VERIFY.verify_system_circuit()

    def test_ap18_cpu_integration_requires_load_validity_selection(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        for label in (
            "ACC_MEMORY_VALID_SELECT", "ACC_NOT_VALID_SELECT", "ACC_INPUT_VALID_SELECT"
        ):
            with self.subTest(selector=label):
                temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
                shutil.copytree(source, temporary / "logisim")
                core = temporary / "logisim" / "TinyCPU.circ"
                project = ET.parse(core)
                main = project.getroot().find("circuit[@name='TinyCPUMain']")
                datapath = next(
                    component for component in main.findall("comp")
                    if component.get("name") == "Datapath"
                )
                datapath_ports = VERIFY.generated_symbol_ports(
                    project.getroot().find("circuit[@name='Datapath']"), datapath
                )
                one_bit_muxes = [
                    component for component in main.findall("comp[@name='Multiplexer']")
                    if next((attribute.get("val") for attribute in component.findall("a")
                             if attribute.get("name") == "width"), "1") == "1"
                ]
                input_selector = next(
                    component for component in one_bit_muxes
                    if _wire_path_exists(main, component.get("loc"),
                                         datapath_ports["VALID_IN"])
                )
                not_selector = next(
                    component for component in one_bit_muxes
                    if component is not input_selector and _wire_path_exists(
                        main, component.get("loc"),
                        _component_terminal(input_selector, -30, -10),
                    )
                )
                memory_selector = next(
                    component for component in one_bit_muxes
                    if component not in (input_selector, not_selector)
                    and _wire_path_exists(
                        main, component.get("loc"),
                        _component_terminal(not_selector, -30, -10),
                    )
                )
                selector = {
                    "ACC_MEMORY_VALID_SELECT": memory_selector,
                    "ACC_NOT_VALID_SELECT": not_selector,
                    "ACC_INPUT_VALID_SELECT": input_selector,
                }[label]
                _remove_wire_at(main, selector.get("loc"))
                project.write(core, encoding="utf-8", xml_declaration=True)
                system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
                with mock.patch.object(VERIFY, "LOGISIM", temporary / "logisim"), \
                     mock.patch.object(
                         VERIFY,
                         "load_system_profile",
                         return_value=replace(
                             system,
                             circuit_path=temporary / "logisim" / "TinyCPU_Peripherals.circ",
                         ),
                     ):
                    with self.assertRaisesRegex(
                        VERIFY.VerificationError,
                        "load-validity (?:selectors|selection paths)",
                    ):
                        VERIFY.verify_system_circuit()

    def test_ap18_cpu_integration_requires_declared_core_paths(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        for label in (
            "CLK", "RESET", "RAM_READ_VALUE", "RAM_READ_VALID",
            "READ_VALUE", "READ_VALID", "WRITE_VALUE", "WRITE_VALID",
            "WRITE_ENABLE", "INSTRUCTION_BOUNDARY", "ENABLE_INTERRUPTS_REQUEST",
            "DISABLE_INTERRUPTS_REQUEST", "RETURN_FROM_INTERRUPT_REQUEST", "NEXT_PC",
            "INTERRUPT_ACCEPT", "INTERRUPT_TARGET_PC", "ILL_RET",
        ):
            with self.subTest(path=label):
                temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
                shutil.copytree(source, temporary / "logisim")
                circuit = temporary / "logisim" / "TinyCPU_Peripherals.circ"
                project = ET.parse(circuit)
                boundary = project.getroot().find("circuit[@name='CPUIntegrationBoundary']")
                self.assertIsNotNone(boundary)
                pin = next(
                    component for component in boundary.findall("comp[@name='Pin']")
                    if any(attribute.get("name") == "label"
                           and attribute.get("val") == label
                           for attribute in component.findall("a"))
                )
                wire = next(item for item in boundary.findall("wire")
                            if pin.get("loc") in {item.get("from"), item.get("to")})
                boundary.remove(wire)
                project.write(circuit, encoding="utf-8", xml_declaration=True)
                system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
                with mock.patch.object(VERIFY, "LOGISIM", temporary / "logisim"), \
                     mock.patch.object(
                         VERIFY,
                         "load_system_profile",
                         return_value=replace(system, circuit_path=circuit),
                     ):
                    with self.assertRaisesRegex(
                        VERIFY.VerificationError, "CPU core integration paths differ"
                    ):
                        VERIFY.verify_system_circuit()

    def test_ap18_cpu_integration_rejects_width_incompatible_input_order(self) -> None:
        """Generated core terminals must be followed instead of boundary pin order."""
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        circuit = temporary / "logisim" / "TinyCPU_Peripherals.circ"
        project = ET.parse(circuit)
        boundary = project.getroot().find("circuit[@name='CPUIntegrationBoundary']")
        self.assertIsNotNone(boundary)
        wire = next(item for item in boundary.findall("wire")
                    if item.get("from") == "(320,240)")
        boundary.remove(wire)
        ET.SubElement(boundary, "wire", {"from": "(320,240)", "to": "(400,180)"})
        project.write(circuit, encoding="utf-8", xml_declaration=True)
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        with mock.patch.object(VERIFY, "LOGISIM", temporary / "logisim"), \
             mock.patch.object(VERIFY, "load_system_profile", return_value=replace(
                 system, circuit_path=circuit)):
            with self.assertRaisesRegex(
                    VERIFY.VerificationError, "CPU core integration paths differ"):
                VERIFY.verify_system_circuit()

    def test_ap18_ram_write_enable_reaches_the_cpu_memory_path(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        circuit = temporary / "logisim" / "TinyCPU.circ"
        project = ET.parse(circuit)
        main = project.getroot().find("circuit[@name='TinyCPUMain']")
        self.assertIsNotNone(main)
        selector = _multiplexer_driven_by(main, "RAM_WRITE_ENABLE")
        wire = next(
            item for item in main.findall("wire")
            if selector.get("loc") in {item.get("from"), item.get("to")}
        )
        main.remove(wire)
        project.write(circuit, encoding="utf-8", xml_declaration=True)
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        with mock.patch.object(VERIFY, "LOGISIM", temporary / "logisim"), \
             mock.patch.object(
                 VERIFY,
                 "load_system_profile",
                 return_value=replace(
                     system,
                     circuit_path=temporary / "logisim" / "TinyCPU_Peripherals.circ",
                 ),
             ):
            with self.assertRaisesRegex(
                VERIFY.VerificationError, "RAM write-enable selection paths"
            ):
                VERIFY.verify_system_circuit()

    def test_ap18_memory_write_request_uses_store_decoder_outputs(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        circuit = temporary / "logisim" / "TinyCPU.circ"
        project = ET.parse(circuit)
        main = project.getroot().find("circuit[@name='TinyCPUMain']")
        self.assertIsNotNone(main)
        gate = _component_by_label(main, "MEMORY_WRITE_REQUEST")
        _remove_wire_at(main, _component_terminal(gate, -50, -20))
        project.write(circuit, encoding="utf-8", xml_declaration=True)
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        with mock.patch.object(VERIFY, "LOGISIM", temporary / "logisim"), \
             mock.patch.object(
                 VERIFY,
                 "load_system_profile",
                 return_value=replace(
                     system,
                     circuit_path=temporary / "logisim" / "TinyCPU_Peripherals.circ",
                 ),
             ):
            with self.assertRaisesRegex(
                VERIFY.VerificationError, "memory-write request sources"
            ):
                VERIFY.verify_system_circuit()

    def test_ap18_cpu_integration_requires_address_width_adapter(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        circuit = temporary / "logisim" / "TinyCPU_Peripherals.circ"
        project = ET.parse(circuit)
        boundary = project.getroot().find("circuit[@name='CPUIntegrationBoundary']")
        self.assertIsNotNone(boundary)
        splitter = boundary.find("comp[@name='Splitter'][@loc='(680,510)']")
        self.assertIsNotNone(splitter)
        incoming = next(item for item in splitter.findall("a")
                        if item.get("name") == "incoming")
        incoming.set("val", "12")
        project.write(circuit, encoding="utf-8", xml_declaration=True)
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        with mock.patch.object(VERIFY, "LOGISIM", temporary / "logisim"), \
             mock.patch.object(VERIFY, "load_system_profile", return_value=replace(
                 system, circuit_path=circuit)):
            with self.assertRaisesRegex(
                    VERIFY.VerificationError, "CPU address width adapter differs"):
                VERIFY.verify_system_circuit()

    def test_ap18_cpu_address_splitter_output_must_be_connected(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware/logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        circuit = temporary / "logisim" / "TinyCPU_Peripherals.circ"
        project = ET.parse(circuit)
        boundary = project.getroot().find("circuit[@name='CPUIntegrationBoundary']")
        self.assertIsNotNone(boundary)
        splitter = next(
            component for component in boundary.findall("comp[@name='Splitter']")
            if {
                attribute.get("name"): attribute.get("val")
                for attribute in component.findall("a")
            }.get("incoming") == "16"
        )
        _remove_wire_at(boundary, _component_terminal(splitter, 20, -20))
        project.write(circuit, encoding="utf-8", xml_declaration=True)
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        with mock.patch.object(VERIFY, "LOGISIM", temporary / "logisim"), \
             mock.patch.object(VERIFY, "load_system_profile", return_value=replace(
                 system, circuit_path=circuit)):
            with self.assertRaisesRegex(
                    VERIFY.VerificationError, "CPU address width adapter differs"):
                VERIFY.verify_system_circuit()

    def test_ap18_cpu_address_is_exported_from_the_effective_address_net(self) -> None:
        root = MODULE_PATH.parents[1]
        core_project = ET.parse(
            root / "hardware/logisim/TinyCPU.circ"
        ).getroot()
        core = core_project.find("circuit[@name='TinyCPUMain']")
        boundary = ET.parse(
            root / "hardware/logisim/TinyCPU_Peripherals.circ"
        ).getroot().find("circuit[@name='CPUIntegrationBoundary']")
        self.assertIsNotNone(core)
        self.assertIsNotNone(boundary)

        address = next(
            component
            for component in core.findall("comp[@name='Pin']")
            if any(
                attribute.get("name") == "label"
                and attribute.get("val") == "ADDRESS"
                for attribute in component.findall("a")
            )
        )
        attributes = {
            attribute.get("name"): attribute.get("val")
            for attribute in address.findall("a")
        }
        self.assertEqual(attributes.get("type"), "output")
        self.assertEqual(attributes.get("width"), "16")
        effective_ports = _subcircuit_ports(
            core_project, core, "EFFECTIVE_ADDRESS_FBOX",
        )
        self.assertTrue(_wire_path_exists(
            core, effective_ports["EFFECTIVE_MEMORY_ADDRESS"],
            address.get("loc", ""),
        ))
        VERIFY.verify_system_circuit()

    def test_ap18_top_level_requires_cpu_integration_boundary(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        circuit = temporary / "logisim" / "TinyCPU_Peripherals.circ"
        project = ET.parse(circuit)
        top = project.getroot().find("circuit[@name='TinyCPUSystemMain']")
        self.assertIsNotNone(top)
        instance = top.find("comp[@name='CPUIntegrationBoundary']")
        self.assertIsNotNone(instance)
        top.remove(instance)
        project.write(circuit, encoding="utf-8", xml_declaration=True)
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        with mock.patch.object(VERIFY, "LOGISIM", temporary / "logisim"), \
             mock.patch.object(
                 VERIFY,
                 "load_system_profile",
                 return_value=replace(system, circuit_path=circuit),
             ):
            with self.assertRaisesRegex(
                VERIFY.VerificationError, "system top components differ from contract"
            ):
                VERIFY.verify_system_circuit()

    def test_ap18_top_level_requires_cpu_boundary_hand_offs(self) -> None:
        # The top-level CPU hand-offs must terminate at the generated-symbol
        # ports, not merely pass near the three boundary instances.
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        terminals = (
            "(1040,610)", "(1040,630)", "(810,360)", "(810,380)",
            "(1260,650)", "(1260,670)", "(810,440)", "(1260,710)",
            "(1260,690)", "(1260,730)", "(1260,750)", "(1260,770)",
            "(1260,790)", "(1260,810)",
            "(810,590)", "(810,690)", "(810,650)",
        )
        for terminal in terminals:
            with self.subTest(cpu_hand_off=terminal):
                temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
                shutil.copytree(source, temporary / "logisim")
                circuit = temporary / "logisim" / "TinyCPU_Peripherals.circ"
                project = ET.parse(circuit)
                top = project.getroot().find("circuit[@name='TinyCPUSystemMain']")
                wire = next(item for item in top.findall("wire")
                            if terminal in {item.get("from"), item.get("to")})
                top.remove(wire)
                project.write(circuit, encoding="utf-8", xml_declaration=True)
                system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
                with mock.patch.object(VERIFY, "LOGISIM", temporary / "logisim"), \
                     mock.patch.object(VERIFY, "load_system_profile",
                                       return_value=replace(system, circuit_path=circuit)):
                    with self.assertRaisesRegex(
                            VERIFY.VerificationError, "CPU top-level hand-offs differ"):
                        VERIFY.verify_system_circuit()

    def test_ap18_top_level_verification_is_independent_of_canvas_coordinates(self) -> None:
        """Moving the complete authored top-level layout preserves its contract."""
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        circuit = temporary / "logisim" / "TinyCPU_Peripherals.circ"
        project = ET.parse(circuit)
        top = project.getroot().find("circuit[@name='TinyCPUSystemMain']")
        self.assertIsNotNone(top)

        def translated(location: str) -> str:
            x, y = map(int, location.strip("()").split(","))
            return f"({x + 170},{y + 90})"

        for component in top.findall("comp"):
            component.set("loc", translated(component.get("loc")))
        for wire in top.findall("wire"):
            wire.set("from", translated(wire.get("from")))
            wire.set("to", translated(wire.get("to")))
        project.write(circuit, encoding="utf-8", xml_declaration=True)
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        with mock.patch.object(VERIFY, "LOGISIM", temporary / "logisim"), \
             mock.patch.object(VERIFY, "load_system_profile", return_value=replace(
                 system, circuit_path=circuit)):
            VERIFY.verify_system_circuit()

    def test_ap18_rejects_crossed_address_and_read_value_buses(self) -> None:
        """A 12-bit address must never terminate at the 16-bit read input."""
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        circuit = temporary / "logisim" / "TinyCPU_Peripherals.circ"
        project = ET.parse(circuit)
        top = project.getroot().find("circuit[@name='TinyCPUSystemMain']")
        self.assertIsNotNone(top)

        # Move the CPU ADDRESS route from OutputMemoryPath.ADDRESS (590,400)
        # onto its 16-bit RAM_READ_VALUE terminal (590,360).  This reproduces
        # the particularly dangerous redraw regression independently of the
        # checked-in coordinate contract.
        address_end = next(
            wire for wire in top.findall("wire")
            if wire.get("to") == "(590,400)"
        )
        address_end.set("to", "(590,360)")
        project.write(circuit, encoding="utf-8", xml_declaration=True)

        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        with mock.patch.object(VERIFY, "LOGISIM", temporary / "logisim"), \
             mock.patch.object(
                 VERIFY,
                 "load_system_profile",
                 return_value=replace(system, circuit_path=circuit),
             ):
            with self.assertRaisesRegex(
                VERIFY.VerificationError,
                "CPU top-level hand-offs differ.*cpu_address_to_memory",
            ):
                VERIFY.verify_system_circuit()

    def test_ap18_output_port_owns_value_and_valid_registers(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        circuit = temporary / "logisim" / "TinyCPU_Peripherals.circ"
        circuit.write_text(circuit.read_text(encoding="utf-8").replace(
            'label" val="OUTPUT_VALID"', 'label" val="BROKEN_VALID"', 1), encoding="utf-8")
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        original = VERIFY.LOGISIM
        VERIFY.LOGISIM = temporary / "logisim"
        self.addCleanup(setattr, VERIFY, "LOGISIM", original)
        with mock.patch.object(VERIFY, "load_system_profile",
                               return_value=replace(system, circuit_path=circuit)):
            with self.assertRaisesRegex(VERIFY.VerificationError, "OutputPort registers"):
                VERIFY.verify_system_circuit()

    def test_ap18_output_port_requires_atomic_control_wiring(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        circuit = temporary / "logisim" / "TinyCPU_Peripherals.circ"
        circuit.write_text(circuit.read_text(encoding="utf-8").replace(
            '<wire from="(340,260)" to="(460,260)"/>', "", 1), encoding="utf-8")
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        original = VERIFY.LOGISIM
        VERIFY.LOGISIM = temporary / "logisim"
        self.addCleanup(setattr, VERIFY, "LOGISIM", original)
        with mock.patch.object(VERIFY, "load_system_profile",
                               return_value=replace(system, circuit_path=circuit)):
            with self.assertRaisesRegex(VERIFY.VerificationError, "OutputPort wiring"):
                VERIFY.verify_system_circuit()

    def test_ap18_output_port_requires_accepted_write_gate(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        circuit = temporary / "logisim" / "TinyCPU_Peripherals.circ"
        circuit.write_text(circuit.read_text(encoding="utf-8").replace(
            'label" val="OUTPUT_WRITE_ACCEPTED"',
            'label" val="BROKEN_WRITE_ACCEPTED"', 1), encoding="utf-8")
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        original = VERIFY.LOGISIM
        VERIFY.LOGISIM = temporary / "logisim"
        self.addCleanup(setattr, VERIFY, "LOGISIM", original)
        with mock.patch.object(VERIFY, "load_system_profile",
                               return_value=replace(system, circuit_path=circuit)):
            with self.assertRaisesRegex(VERIFY.VerificationError, "accepted-write gate"):
                VERIFY.verify_system_circuit()

    def test_ap18_output_memory_path_enforces_reserved_address(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        circuit = temporary / "logisim" / "TinyCPU_Peripherals.circ"
        circuit.write_text(circuit.read_text(encoding="utf-8").replace(
            'label" val="RAM_WRITE_GATE"', 'label" val="BROKEN_RAM_WRITE_GATE"', 1),
            encoding="utf-8",
        )
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        original = VERIFY.LOGISIM
        VERIFY.LOGISIM = temporary / "logisim"
        self.addCleanup(setattr, VERIFY, "LOGISIM", original)
        with mock.patch.object(VERIFY, "load_system_profile",
                               return_value=replace(system, circuit_path=circuit)):
            with self.assertRaisesRegex(VERIFY.VerificationError,
                                        "OutputMemoryPath routing"):
                VERIFY.verify_system_circuit()

    def test_ap18_output_memory_path_requires_functional_wiring(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        circuit = temporary / "logisim" / "TinyCPU_Peripherals.circ"
        circuit.write_text(circuit.read_text(encoding="utf-8").replace(
            '<wire from="(600,350)" to="(620,350)"/>', "", 1), encoding="utf-8")
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        original = VERIFY.LOGISIM
        VERIFY.LOGISIM = temporary / "logisim"
        self.addCleanup(setattr, VERIFY, "LOGISIM", original)
        with mock.patch.object(VERIFY, "load_system_profile",
                               return_value=replace(system, circuit_path=circuit)):
            with self.assertRaisesRegex(VERIFY.VerificationError,
                                        "OutputMemoryPath wiring"):
                VERIFY.verify_system_circuit()

    def test_ap18_interrupt_controller_owns_interrupt_state(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        circuit = temporary / "logisim" / "TinyCPU_Peripherals.circ"
        circuit.write_text(circuit.read_text(encoding="utf-8").replace(
            '<comp lib="5" loc="(890,660)" name="Register">\n      <a name="appearance" val="logisim_evolution"/>\n      <a name="labelfont" val="SansSerif plain 9"/>\n      <a name="width" val="12"/>',
            '<comp lib="5" loc="(890,660)" name="Register">\n      <a name="appearance" val="logisim_evolution"/>\n      <a name="labelfont" val="SansSerif plain 9"/>\n      <a name="width" val="1"/>', 1),
            encoding="utf-8")
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        original = VERIFY.LOGISIM
        VERIFY.LOGISIM = temporary / "logisim"
        self.addCleanup(setattr, VERIFY, "LOGISIM", original)
        with mock.patch.object(VERIFY, "load_system_profile",
                               return_value=replace(system, circuit_path=circuit)):
            with self.assertRaisesRegex(VERIFY.VerificationError,
                                        "InterruptController registers"):
                VERIFY.verify_system_circuit()

    def test_ap18_interrupt_controller_requires_edge_detector_wiring(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        circuit = temporary / "logisim" / "TinyCPU_Peripherals.circ"
        circuit.write_text(circuit.read_text(encoding="utf-8").replace(
            '<wire from="(990,170)" to="(990,220)"/>', "", 1), encoding="utf-8")
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        original = VERIFY.LOGISIM
        VERIFY.LOGISIM = temporary / "logisim"
        self.addCleanup(setattr, VERIFY, "LOGISIM", original)
        with mock.patch.object(VERIFY, "load_system_profile",
                               return_value=replace(system, circuit_path=circuit)):
            with self.assertRaisesRegex(VERIFY.VerificationError,
                                        "InterruptController wiring"):
                VERIFY.verify_system_circuit()

    def test_ap18_interrupt_controller_requires_pending_wiring(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        circuit = temporary / "logisim" / "TinyCPU_Peripherals.circ"
        circuit.write_text(circuit.read_text(encoding="utf-8").replace(
            '<wire from="(1000,350)" to="(1100,350)"/>', "", 1), encoding="utf-8")
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        original = VERIFY.LOGISIM
        VERIFY.LOGISIM = temporary / "logisim"
        self.addCleanup(setattr, VERIFY, "LOGISIM", original)
        with mock.patch.object(VERIFY, "load_system_profile",
                               return_value=replace(system, circuit_path=circuit)):
            with self.assertRaisesRegex(VERIFY.VerificationError,
                                        "InterruptController wiring"):
                VERIFY.verify_system_circuit()

    def test_ap18_interrupt_controller_requires_mask_wiring(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        circuit = temporary / "logisim" / "TinyCPU_Peripherals.circ"
        circuit.write_text(circuit.read_text(encoding="utf-8").replace(
            '<wire from="(1000,550)" to="(1340,550)"/>', "", 1), encoding="utf-8")
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        original = VERIFY.LOGISIM
        VERIFY.LOGISIM = temporary / "logisim"
        self.addCleanup(setattr, VERIFY, "LOGISIM", original)
        with mock.patch.object(VERIFY, "load_system_profile",
                               return_value=replace(system, circuit_path=circuit)):
            with self.assertRaisesRegex(VERIFY.VerificationError,
                                        "InterruptController wiring"):
                VERIFY.verify_system_circuit()

    def test_ap18_interrupt_controller_requires_acceptance_wiring(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        circuit = temporary / "logisim" / "TinyCPU_Peripherals.circ"
        circuit.write_text(circuit.read_text(encoding="utf-8").replace(
            '<wire from="(1030,360)" to="(1090,360)"/>', "", 1), encoding="utf-8")
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        original = VERIFY.LOGISIM
        VERIFY.LOGISIM = temporary / "logisim"
        self.addCleanup(setattr, VERIFY, "LOGISIM", original)
        with mock.patch.object(VERIFY, "load_system_profile",
                               return_value=replace(system, circuit_path=circuit)):
            with self.assertRaisesRegex(VERIFY.VerificationError,
                                        "InterruptController wiring"):
                VERIFY.verify_system_circuit()

    def test_ap18_interrupt_controller_requires_return_capture_wiring(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        circuit = temporary / "logisim" / "TinyCPU_Peripherals.circ"
        circuit.write_text(circuit.read_text(encoding="utf-8").replace(
            '<wire from="(1030,900)" to="(1100,900)"/>', "", 1), encoding="utf-8")
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        original = VERIFY.LOGISIM
        VERIFY.LOGISIM = temporary / "logisim"
        self.addCleanup(setattr, VERIFY, "LOGISIM", original)
        with mock.patch.object(VERIFY, "load_system_profile",
                               return_value=replace(system, circuit_path=circuit)):
            with self.assertRaisesRegex(VERIFY.VerificationError,
                                        "InterruptController wiring"):
                VERIFY.verify_system_circuit()

    def test_ap18_interrupt_controller_requires_return_valid_clear_wiring(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        circuit = temporary / "logisim" / "TinyCPU_Peripherals.circ"
        circuit.write_text(circuit.read_text(encoding="utf-8").replace(
            '<wire from="(1050,820)" to="(1050,890)"/>', "", 1), encoding="utf-8")
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        original = VERIFY.LOGISIM
        VERIFY.LOGISIM = temporary / "logisim"
        self.addCleanup(setattr, VERIFY, "LOGISIM", original)
        with mock.patch.object(VERIFY, "load_system_profile",
                               return_value=replace(system, circuit_path=circuit)):
            with self.assertRaisesRegex(VERIFY.VerificationError,
                                        "InterruptController wiring"):
                VERIFY.verify_system_circuit()

    def test_ap18_interrupt_controller_requires_handler_state_wiring(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        circuit = temporary / "logisim" / "TinyCPU_Peripherals.circ"
        circuit.write_text(circuit.read_text(encoding="utf-8").replace(
            '<wire from="(1070,630)" to="(1070,880)"/>', "", 1), encoding="utf-8")
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        original = VERIFY.LOGISIM
        VERIFY.LOGISIM = temporary / "logisim"
        self.addCleanup(setattr, VERIFY, "LOGISIM", original)
        with mock.patch.object(VERIFY, "load_system_profile",
                               return_value=replace(system, circuit_path=circuit)):
            with self.assertRaisesRegex(VERIFY.VerificationError,
                                        "InterruptController wiring"):
                VERIFY.verify_system_circuit()

    def test_ap18_interrupt_controller_requires_return_target_selection(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        circuit = temporary / "logisim" / "TinyCPU_Peripherals.circ"
        circuit.write_text(circuit.read_text(encoding="utf-8").replace(
            '<wire from="(1070,630)" to="(1260,630)"/>', "", 1), encoding="utf-8")
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        original = VERIFY.LOGISIM
        VERIFY.LOGISIM = temporary / "logisim"
        self.addCleanup(setattr, VERIFY, "LOGISIM", original)
        with mock.patch.object(VERIFY, "load_system_profile",
                               return_value=replace(system, circuit_path=circuit)):
            with self.assertRaisesRegex(VERIFY.VerificationError,
                                        "InterruptController wiring"):
                VERIFY.verify_system_circuit()

    def test_ap18_interrupt_controller_routing_corridors_are_bounded(self) -> None:
        """Visual routing rails stop at their first and last electrical branch."""
        root = ET.parse(
            MODULE_PATH.parents[1] / "hardware" / "logisim" / "TinyCPU_Peripherals.circ"
        ).getroot()
        interrupt = root.find("circuit[@name='InterruptController']")
        self.assertIsNotNone(interrupt)
        wires = {
            (wire.get("from"), wire.get("to"))
            for wire in interrupt.findall("wire")
        }
        self.assertTrue({
            ("(560,300)", "(560,410)"),
            ("(580,530)", "(580,840)"),
            ("(820,840)", "(820,970)"),
            ("(840,730)", "(840,860)"),
            ("(860,760)", "(860,880)"),
            ("(1200,650)", "(1200,780)"),
        } <= wires)
        self.assertFalse(any(
            start.endswith(",50)") and end.endswith(",850)")
            for start, end in wires
        ))

    def test_ap18_interrupt_handler_and_return_valid_feedback_are_separate(self) -> None:
        """The two one-bit states must not share the former x=1040 branch."""
        root = ET.parse(
            MODULE_PATH.parents[1] / "hardware" / "logisim" / "TinyCPU_Peripherals.circ"
        ).getroot()
        interrupt = root.find("circuit[@name='InterruptController']")
        self.assertIsNotNone(interrupt)
        wires = {
            (wire.get("from"), wire.get("to"))
            for wire in interrupt.findall("wire")
        }
        self.assertIn(("(520,630)", "(1070,630)"), wires)
        self.assertIn(("(1070,630)", "(1070,880)"), wires)
        self.assertIn(("(1030,360)", "(1030,900)"), wires)
        self.assertNotIn(("(520,630)", "(1030,630)"), wires)
        self.assertNotIn(("(1030,630)", "(1070,630)"), wires)


if __name__ == "__main__":
    unittest.main()
