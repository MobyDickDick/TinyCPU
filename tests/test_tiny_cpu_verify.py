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
            "CPUIntegrationBoundary": "(1270,590)",
            "OutputMemoryPath": "(810,360)",
            "InterruptController": "(810,590)",
        })
        core = boundary.find("comp[@name='TinyCPUMain']")
        self.assertIsNotNone(core)
        self.assertEqual(core.get("loc"), "(630,160)")

        wires = {(wire.get("from"), wire.get("to")) for wire in top.findall("wire")}
        stale_reconstruction = {
            ("(1190,830)", "(1270,830)"),
            ("(1270,830)", "(1270,150)"),
            ("(1270,150)", "(410,150)"),
        }
        self.assertFalse(stale_reconstruction <= wires)

    def test_ap18_illegal_return_gate_label_does_not_cover_its_output(self) -> None:
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
        attributes = {
            attribute.get("name"): attribute.get("val")
            for attribute in illegal_return_or.findall("a")
        }
        self.assertEqual(attributes.get("labelloc"), "north")

    def test_ap18_system_top_requires_public_state_wiring(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        circuit = temporary / "logisim" / "TinyCPU_Peripherals.circ"
        circuit.write_text(circuit.read_text(encoding="utf-8").replace(
            '<wire from="(820,940)" to="(1490,940)"/>', "", 1), encoding="utf-8")
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
            '<wire from="(360,630)" to="(590,630)"/>', "", 1), encoding="utf-8")
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

    def test_ap18_instruction_boundary_constant_must_be_asserted(self) -> None:
        """A connected default-zero Constant must not masquerade as a boundary."""
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        core = temporary / "logisim" / "TinyCPU.circ"
        project = ET.parse(core)
        main = project.getroot().find("circuit[@name='TinyCPUMain']")
        self.assertIsNotNone(main)
        constant = next(
            component for component in main.findall("comp[@name='Constant']")
            if component.get("loc") == "(3560,930)"
        )
        value = next(
            attribute for attribute in constant.findall("a")
            if attribute.get("name") == "value"
        )
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
        wire = next(item for item in main.findall("wire")
                    if "(3590,1170)" in {item.get("from"), item.get("to")})
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
            with self.assertRaisesRegex(VERIFY.VerificationError, "next-PC path"):
                VERIFY.verify_system_circuit()

    def test_ap18_interrupt_command_paths_reject_bus_contention(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        core = temporary / "logisim" / "TinyCPU.circ"
        project = ET.parse(core)
        main = project.getroot().find("circuit[@name='TinyCPUMain']")
        ET.SubElement(main, "wire", {"from": "(3560,930)", "to": "(2960,930)"})
        ET.SubElement(main, "wire", {"from": "(2960,930)", "to": "(2960,390)"})
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
        swaps = {
            frozenset(("(2120,1050)", "(2410,1050)")): "(2410,1030)",
            frozenset(("(2360,1030)", "(2410,1030)")): "(2410,1050)",
        }
        for wire in main.findall("wire"):
            replacement = swaps.get(frozenset((wire.get("from"), wire.get("to"))))
            if replacement is not None:
                wire.set("to", replacement)
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

    def test_ap18_cpu_integration_requires_declared_core_paths(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        for label in (
            "CLK", "RESET", "RAM_READ_VALUE", "RAM_READ_VALID",
            "READ_VALUE", "READ_VALID", "WRITE_VALUE", "WRITE_VALID",
            "WRITE_ENABLE", "INSTRUCTION_BOUNDARY", "ENABLE_REQUEST",
            "DISABLE_REQUEST", "RETURN_REQUEST", "NEXT_PC",
            "INTERRUPT_ACCEPT", "TARGET_PC", "ILL_RET",
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

    def test_ap18_cpu_integration_requires_address_width_adapter(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        circuit = temporary / "logisim" / "TinyCPU_Peripherals.circ"
        project = ET.parse(circuit)
        boundary = project.getroot().find("circuit[@name='CPUIntegrationBoundary']")
        self.assertIsNotNone(boundary)
        splitter = boundary.find("comp[@name='Splitter'][@loc='(700,580)']")
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
            "(1050,590)", "(1050,610)", "(810,360)", "(810,380)",
            "(1270,670)", "(1270,690)", "(810,440)", "(1270,730)",
            "(1270,710)", "(1270,750)", "(1270,770)", "(1270,790)",
            "(1270,810)", "(1270,830)",
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
