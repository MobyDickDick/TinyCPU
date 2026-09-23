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


class CircuitVerificationTests(unittest.TestCase):
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

    def test_ap18_system_top_requires_public_state_wiring(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        circuit = temporary / "logisim" / "TinyCPU_Peripherals.circ"
        circuit.write_text(circuit.read_text(encoding="utf-8").replace(
            '<wire from="(620,680)" to="(820,680)"/>', "", 1), encoding="utf-8")
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
            '<wire from="(200,580)" to="(400,580)"/>', "", 1), encoding="utf-8")
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
        for endpoint in (
            "(1090,730)", "(1090,750)", "(1100,760)", "(1120,740)",
            "(1120,790)", "(1120,810)", "(1130,820)", "(1150,800)",
        ):
            with self.subTest(endpoint=endpoint):
                temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
                shutil.copytree(source, temporary / "logisim")
                core = temporary / "logisim" / "TinyCPU.circ"
                project = ET.parse(core)
                main = project.getroot().find("circuit[@name='TinyCPUMain']")
                self.assertIsNotNone(main)
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
                        VERIFY.VerificationError, "external-memory selection paths differ"
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
        text = core.read_text(encoding="utf-8")
        text = text.replace(
            '<wire from="(2120,1040)" to="(2650,1040)"/>',
            '<wire from="(2120,1040)" to="(2650,1020)"/>',
            1,
        ).replace(
            '<wire from="(2610,1020)" to="(2650,1020)"/>',
            '<wire from="(2610,1020)" to="(2650,1040)"/>',
            1,
        )
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
            with self.assertRaisesRegex(
                VERIFY.VerificationError, "validity inputs are crossed"
            ):
                VERIFY.verify_system_circuit()

    def test_ap18_cpu_integration_requires_declared_core_paths(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        for label in (
            "CLK", "RESET", "RAM_READ_VALUE", "RAM_READ_VALID",
            "READ_VALUE", "READ_VALID", "WRITE_VALUE", "WRITE_VALID",
            "WRITE_ENABLE", "INSTRUCTION_BOUNDARY", "ENABLE_REQUEST",
            "DISABLE_REQUEST", "RETURN_REQUEST",
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

    def test_ap18_cpu_integration_requires_declared_data_paths(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        for source_label, target_label in (
            ("CORE_ADDRESS", "ADDRESS"),
            ("CORE_NEXT_PC", "NEXT_PC"),
        ):
            with self.subTest(path=(source_label, target_label)):
                temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
                shutil.copytree(source, temporary / "logisim")
                circuit = temporary / "logisim" / "TinyCPU_Peripherals.circ"
                project = ET.parse(circuit)
                boundary = project.getroot().find("circuit[@name='CPUIntegrationBoundary']")
                self.assertIsNotNone(boundary)
                locations = {}
                for component in boundary.findall("comp[@name='Pin']"):
                    attributes = {
                        item.get("name"): item.get("val") for item in component.findall("a")
                    }
                    locations[attributes.get("label", "")] = component.get("loc")
                source_location = locations[source_label]
                wire = next(item for item in boundary.findall("wire")
                            if source_location in {item.get("from"), item.get("to")})
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
                        VERIFY.VerificationError, "CPU integration data paths differ"
                    ):
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
            "(620,350)", "(620,370)", "(1040,780)", "(1040,800)",
            "(1040,820)", "(1040,840)", "(620,430)", "(1040,860)",
            "(1040,880)", "(1040,900)", "(1040,920)", "(1040,940)",
            "(620,540)", "(620,640)", "(620,600)",
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
            '<comp lib="5" loc="(900,660)" name="Register">\n      <a name="appearance" val="logisim_evolution"/>\n      <a name="labelfont" val="SansSerif plain 9"/>\n      <a name="width" val="12"/>',
            '<comp lib="5" loc="(900,660)" name="Register">\n      <a name="appearance" val="logisim_evolution"/>\n      <a name="labelfont" val="SansSerif plain 9"/>\n      <a name="width" val="1"/>', 1),
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
            '<wire from="(1000,170)" to="(1000,220)"/>', "", 1), encoding="utf-8")
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
            '<wire from="(1010,350)" to="(1110,350)"/>', "", 1), encoding="utf-8")
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
            '<wire from="(1010,550)" to="(1350,550)"/>', "", 1), encoding="utf-8")
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
            '<wire from="(1040,360)" to="(1100,360)"/>', "", 1), encoding="utf-8")
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
            '<wire from="(1040,900)" to="(1110,900)"/>', "", 1), encoding="utf-8")
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
            '<wire from="(1060,820)" to="(1060,890)"/>', "", 1), encoding="utf-8")
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
            '<wire from="(1080,630)" to="(1080,880)"/>', "", 1), encoding="utf-8")
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
            '<wire from="(1080,630)" to="(1270,630)"/>', "", 1), encoding="utf-8")
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
            ("(870,760)", "(870,880)"),
            ("(1210,650)", "(1210,780)"),
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
        self.assertIn(("(520,630)", "(1080,630)"), wires)
        self.assertIn(("(1080,630)", "(1080,880)"), wires)
        self.assertIn(("(1040,360)", "(1040,900)"), wires)
        self.assertNotIn(("(520,630)", "(1040,630)"), wires)
        self.assertNotIn(("(1040,630)", "(1080,630)"), wires)


if __name__ == "__main__":
    unittest.main()
