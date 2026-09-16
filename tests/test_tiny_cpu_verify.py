from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
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

    def test_ap18_interrupt_controller_uses_only_visible_enlarged_routes(self) -> None:
        project = VERIFY.ET.parse(
            MODULE_PATH.parents[1] / "hardware/logisim/TinyCPU-Peripherals.circ"
        ).getroot()
        interrupt = project.find("circuit[@name='InterruptController']")
        self.assertIsNotNone(interrupt)
        self.assertEqual(interrupt.findall("comp[@name='Tunnel']"), [])
        points = {
            endpoint
            for wire in interrupt.findall("wire")
            for endpoint in (tuple(map(int, wire.get("from").strip("()").split(","))),
                             tuple(map(int, wire.get("to").strip("()").split(","))))
        }
        self.assertLess(min(x for x, _ in points), 0)
        self.assertGreater(max(x for x, _ in points), 2000)
        self.assertGreater(max(y for _, y in points), 1800)

    def test_ap18_interrupt_controller_has_no_implicit_wire_contacts(self) -> None:
        project = VERIFY.ET.parse(
            MODULE_PATH.parents[1] / "hardware/logisim/TinyCPU-Peripherals.circ"
        ).getroot()
        interrupt = project.find("circuit[@name='InterruptController']")
        self.assertIsNotNone(interrupt)
        self.assertEqual(WIRE_CONTACTS.inspect_circuit(interrupt), [])

    def test_ap18_output_port_has_unambiguous_control_routes(self) -> None:
        project = VERIFY.ET.parse(
            MODULE_PATH.parents[1] / "hardware/logisim/TinyCPU-Peripherals.circ"
        ).getroot()
        output = project.find("circuit[@name='OutputPort']")
        self.assertIsNotNone(output)
        self.assertEqual(WIRE_CONTACTS.inspect_circuit(output), [])

    def test_ap18_output_port_owns_value_and_valid_registers(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        circuit = temporary / "logisim" / "TinyCPU-Peripherals.circ"
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
        circuit = temporary / "logisim" / "TinyCPU-Peripherals.circ"
        circuit.write_text(circuit.read_text(encoding="utf-8").replace(
            '<wire from="(400,260)" to="(430,260)" />', "", 1), encoding="utf-8")
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        original = VERIFY.LOGISIM
        VERIFY.LOGISIM = temporary / "logisim"
        self.addCleanup(setattr, VERIFY, "LOGISIM", original)
        with mock.patch.object(VERIFY, "load_system_profile",
                               return_value=replace(system, circuit_path=circuit)):
            with self.assertRaisesRegex(VERIFY.VerificationError, "OutputPort wiring"):
                VERIFY.verify_system_circuit()

    def test_ap18_output_memory_path_enforces_reserved_address(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        circuit = temporary / "logisim" / "TinyCPU-Peripherals.circ"
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
        circuit = temporary / "logisim" / "TinyCPU-Peripherals.circ"
        circuit.write_text(circuit.read_text(encoding="utf-8").replace(
            '<wire from="(410,280)" to="(540,280)" />', "", 1), encoding="utf-8")
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
        circuit = temporary / "logisim" / "TinyCPU-Peripherals.circ"
        circuit.write_text(circuit.read_text(encoding="utf-8").replace(
            'label" val="REQUEST_LEVEL"', 'label" val="BROKEN_REQUEST_LEVEL"', 1),
            encoding="utf-8",
        )
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
        circuit = temporary / "logisim" / "TinyCPU-Peripherals.circ"
        circuit.write_text(circuit.read_text(encoding="utf-8").replace(
            '<wire from="(870,280)" to="(880,280)"/>', "", 1), encoding="utf-8")
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
        circuit = temporary / "logisim" / "TinyCPU-Peripherals.circ"
        circuit.write_text(circuit.read_text(encoding="utf-8").replace(
            '<wire from="(1010,480)" to="(1030,480)"/>', "", 1), encoding="utf-8")
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
        circuit = temporary / "logisim" / "TinyCPU-Peripherals.circ"
        circuit.write_text(circuit.read_text(encoding="utf-8").replace(
            '<wire from="(810,970)" to="(880,970)"/>', "", 1), encoding="utf-8")
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
        circuit = temporary / "logisim" / "TinyCPU-Peripherals.circ"
        circuit.write_text(circuit.read_text(encoding="utf-8").replace(
            '<wire from="(1010,310)" to="(1080,310)"/>', "", 1), encoding="utf-8")
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
        circuit = temporary / "logisim" / "TinyCPU-Peripherals.circ"
        circuit.write_text(circuit.read_text(encoding="utf-8").replace(
            '<wire from="(540,510)" to="(640,510)"/>', "", 1), encoding="utf-8")
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
        circuit = temporary / "logisim" / "TinyCPU-Peripherals.circ"
        circuit.write_text(circuit.read_text(encoding="utf-8").replace(
            '<wire from="(1260,1140)" to="(1330,1140)"/>', "", 1), encoding="utf-8")
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
        circuit = temporary / "logisim" / "TinyCPU-Peripherals.circ"
        circuit.write_text(circuit.read_text(encoding="utf-8").replace(
            '<wire from="(1170,1240)" to="(1200,1240)"/>', "", 1), encoding="utf-8")
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
        circuit = temporary / "logisim" / "TinyCPU-Peripherals.circ"
        circuit.write_text(circuit.read_text(encoding="utf-8").replace(
            '<wire from="(1230,420)" to="(1230,430)"/>', "", 1), encoding="utf-8")
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        original = VERIFY.LOGISIM
        VERIFY.LOGISIM = temporary / "logisim"
        self.addCleanup(setattr, VERIFY, "LOGISIM", original)
        with mock.patch.object(VERIFY, "load_system_profile",
                               return_value=replace(system, circuit_path=circuit)):
            with self.assertRaisesRegex(VERIFY.VerificationError,
                                        "InterruptController wiring"):
                VERIFY.verify_system_circuit()

    def test_ap18_system_verifier_rejects_disconnected_visible_route(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        circuit = temporary / "logisim" / "TinyCPU-Peripherals.circ"
        circuit.write_text(circuit.read_text(encoding="utf-8").replace(
            '<wire from="(-560,1440)" to="(2000,1440)"/>', "", 1),
            encoding="utf-8",
        )
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        original = VERIFY.LOGISIM
        VERIFY.LOGISIM = temporary / "logisim"
        self.addCleanup(setattr, VERIFY, "LOGISIM", original)
        with mock.patch.object(VERIFY, "load_system_profile",
                               return_value=replace(system, circuit_path=circuit)):
            with self.assertRaisesRegex(VERIFY.VerificationError,
                                        "visible route HANDLER_REGISTER_NEXT is disconnected"):
                VERIFY.verify_system_circuit()

    def test_ap18_system_verifier_rejects_implicit_interrupt_contact(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copytree(source, temporary / "logisim")
        circuit = temporary / "logisim" / "TinyCPU-Peripherals.circ"
        project = VERIFY.ET.parse(circuit)
        interrupt = project.getroot().find("circuit[@name='InterruptController']")
        self.assertIsNotNone(interrupt)
        VERIFY.ET.SubElement(interrupt, "wire", {
            "from": "(900,230)", "to": "(900,280)"
        })
        project.write(circuit, encoding="unicode")
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        original = VERIFY.LOGISIM
        VERIFY.LOGISIM = temporary / "logisim"
        self.addCleanup(setattr, VERIFY, "LOGISIM", original)
        with mock.patch.object(VERIFY, "load_system_profile",
                               return_value=replace(system, circuit_path=circuit)):
            with self.assertRaisesRegex(VERIFY.VerificationError,
                                        "implicit wire contacts"):
                VERIFY.verify_system_circuit()

    def test_ap18_contact_audit_detects_a_regression(self) -> None:
        project = VERIFY.ET.parse(
            MODULE_PATH.parents[1] / "hardware/logisim/TinyCPU-Peripherals.circ"
        ).getroot()
        interrupt = project.find("circuit[@name='InterruptController']")
        self.assertIsNotNone(interrupt)
        VERIFY.ET.SubElement(interrupt, "wire", {
            "from": "(900,230)", "to": "(900,280)"
        })
        self.assertTrue(WIRE_CONTACTS.inspect_circuit(interrupt))


if __name__ == "__main__":
    unittest.main()
