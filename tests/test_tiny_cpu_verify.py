from __future__ import annotations

import importlib.util
import json
import shutil
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


class CircuitVerificationTests(unittest.TestCase):
    def write_project(self, circuit_body: str, main: str = "Main") -> Path:
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        path = directory / "test.circ"
        path.write_text(
            f'<project><main name="{main}"/><circuit name="Main">{circuit_body}</circuit></project>',
            encoding="utf-8",
        )
        return path

    def test_accepts_an_orthogonal_wire(self) -> None:
        path = self.write_project('<wire from="(0,0)" to="(10,0)"/>')
        self.assertEqual(VERIFY.verify_circuit(path), (1, 1))

    def test_rejects_a_diagonal_wire(self) -> None:
        path = self.write_project('<wire from="(0,0)" to="(10,10)"/>')
        with self.assertRaisesRegex(VERIFY.VerificationError, "diagonal wire"):
            VERIFY.verify_circuit(path)

    def test_rejects_a_missing_main(self) -> None:
        path = self.write_project("", main="Missing")
        with self.assertRaisesRegex(VERIFY.VerificationError, "does not exist"):
            VERIFY.verify_circuit(path)

    def test_rejects_duplicate_pin_labels(self) -> None:
        pins = "".join(
            f'<comp lib="0" loc="({x},0)" name="Pin"><a name="label" val="A"/></comp>'
            for x in (0, 10)
        )
        path = self.write_project(pins)
        with self.assertRaisesRegex(VERIFY.VerificationError, "duplicate Pin labels"):
            VERIFY.verify_circuit(path)


    def test_ap18_circuit_matches_public_pin_contract(self) -> None:
        VERIFY.verify_system_circuit()

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
            '<wire from="(330,260)" to="(430,260)"/>', "", 1), encoding="utf-8")
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
            '<wire from="(410,280)" to="(540,280)"/>', "", 1), encoding="utf-8")
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
            '<wire from="(490,140)" to="(510,140)"/>', "", 1), encoding="utf-8")
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
            '<wire from="(350,260)" to="(430,260)"/>', "", 1), encoding="utf-8")
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
            '<wire from="(530,175)" to="(580,175)"/>', "", 1), encoding="utf-8")
        system = VERIFY.load_system_profile("tinycpu-peripherals-16-12-v1")
        original = VERIFY.LOGISIM
        VERIFY.LOGISIM = temporary / "logisim"
        self.addCleanup(setattr, VERIFY, "LOGISIM", original)
        with mock.patch.object(VERIFY, "load_system_profile",
                               return_value=replace(system, circuit_path=circuit)):
            with self.assertRaisesRegex(VERIFY.VerificationError,
                                        "InterruptController wiring"):
                VERIFY.verify_system_circuit()





if __name__ == "__main__":
    unittest.main()
