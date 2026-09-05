from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


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

    def test_8_8_circuit_matches_profile_and_embedded_fixture(self) -> None:
        root = MODULE_PATH.parents[1]
        logisim = root / "hardware" / "logisim"
        profile = json.loads((logisim / "tinycpu-8-8.json").read_text())
        machine = json.loads((logisim / "tinycpu-machine-8-v1.json").read_text())
        VERIFY.verify_small_profile_circuit(profile, machine)

    def test_ap18_circuit_matches_public_pin_contract(self) -> None:
        VERIFY.verify_system_circuit()

    def test_8_8_circuit_rejects_a_legacy_width(self) -> None:
        root = MODULE_PATH.parents[1]
        source = root / "hardware" / "logisim"
        temporary = Path(self.enterContext(tempfile.TemporaryDirectory()))
        shutil.copy(source / "TinyCPU-8-8.circ", temporary)
        shutil.copy(source / "ap17_countdown_8_8.rom", temporary)
        circuit = temporary / "TinyCPU-8-8.circ"
        circuit.write_text(circuit.read_text().replace('name="width" val="8"',
                                                        'name="width" val="16"', 1))
        profile = json.loads((source / "tinycpu-8-8.json").read_text())
        machine = json.loads((source / "tinycpu-machine-8-v1.json").read_text())
        original = VERIFY.LOGISIM
        VERIFY.LOGISIM = temporary
        self.addCleanup(setattr, VERIFY, "LOGISIM", original)
        with self.assertRaisesRegex(VERIFY.VerificationError, "legacy 16/12 width"):
            VERIFY.verify_small_profile_circuit(profile, machine)

    def test_8_8_electrical_matrix_is_complete_and_profile_valid(self) -> None:
        root = MODULE_PATH.parents[1]
        logisim = root / "hardware" / "logisim"
        matrix = json.loads((logisim / "tinycpu-electrical-matrix-8-v1.json").read_text())
        machine = json.loads((logisim / "tinycpu-machine-8-v1.json").read_text())
        self.assertEqual(
            VERIFY.verify_electrical_matrix(
                matrix, machine, "tinycpu-8-8",
                logisim / "tinycpu-electrical-matrix-8-v1.json",
            ),
            6,
        )

    def test_8_8_electrical_matrix_rejects_16_bit_operand(self) -> None:
        root = MODULE_PATH.parents[1]
        logisim = root / "hardware" / "logisim"
        matrix = json.loads((logisim / "tinycpu-electrical-matrix-8-v1.json").read_text())
        machine = json.loads((logisim / "tinycpu-machine-8-v1.json").read_text())
        matrix["fixtures"][0]["program"] = "LOAD_CONST(32767)\nHALT_ERROR()\n"
        with self.assertRaisesRegex(VERIFY.VerificationError, "invalid for tinycpu-8-8"):
            VERIFY.verify_electrical_matrix(matrix, machine, "tinycpu-8-8", Path("matrix.json"))


if __name__ == "__main__":
    unittest.main()
