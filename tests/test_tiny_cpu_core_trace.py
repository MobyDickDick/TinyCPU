import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tiny_cpu_assembler import assemble, encode_program
from tiny_cpu_core_trace import CoreMismatch, SIGNALS, compare_trace, expected_trace
from tiny_cpu_logisim import ROOT, LogisimError, run_core_comparison
from tiny_cpu_profiles import load_profile


def electrical_table(rows):
    """Encode synthetic exporter records, including defined inactive buses."""
    lines = ["\t".join(["edge", "phase", *SIGNALS, "MEMORY"])]
    for row in rows:
        cells = [str(row["edge"]), row["phase"]]
        cells += [format(row.get(name, 0), f"0{width}b")
                  for name, (width, _) in SIGNALS.items()]
        cells += [row.get("MEMORY", "-")]
        lines.append("\t".join(cells))
    return "\n".join(lines) + "\n"


class CoreTraceTests(unittest.TestCase):
    def setUp(self):
        self.program = assemble("LOAD_CONST(3)\nHALT()\n")
        self.expected = expected_trace(self.program)
        # Independent hand-written observations: the next decoded HALT is
        # already visible after edge 1. Its terminal event belongs to pre 2.
        self.rows = [
            {"edge": 1, "phase": "pre"},
            {"edge": 1, "phase": "post", "PC": 1, "ACC": 3,
             "ACC_VALID": 1, "HALTED": 1},
            {"edge": 2, "phase": "pre", "PC": 1, "ACC": 3,
             "ACC_VALID": 1, "HALTED": 1},
            {"edge": 2, "phase": "post", "PC": 2, "ACC": 3, "ACC_VALID": 1},
        ]

    def test_settled_terminal_decode_is_not_a_sticky_halt_register(self):
        compare_trace(electrical_table(self.rows), self.expected)

    def test_wrong_result_is_rejected_even_with_correct_halt(self):
        self.rows[1]["ACC"] = 4
        with self.assertRaises(CoreMismatch) as raised:
            compare_trace(electrical_table(self.rows), self.expected)
        self.assertEqual(vars(raised.exception), {
            "edge": 1, "phase": "post", "signal": "ACC", "expected": 3, "actual": 4,
        })

    def test_undefined_bits_are_rejected_even_on_inactive_buses(self):
        for bit in ("E", "U", "x", "?"):
            with self.subTest(bit=bit):
                table = electrical_table(self.rows).splitlines()
                cells = table[1].split("\t")
                cells[2 + list(SIGNALS).index("PRINT_ADDRESS_VALUE")] = bit * 16
                table[1] = "\t".join(cells)
                with self.assertRaisesRegex(CoreMismatch, "PRINT_ADDRESS_VALUE"):
                    compare_trace("\n".join(table), self.expected)

    def test_missing_extra_duplicate_and_reordered_samples_fail(self):
        for rows in (self.rows[:-1], self.rows + [self.rows[-1]],
                     self.rows[:1] + self.rows, self.rows[1:] + self.rows[:1]):
            with self.subTest(rows=rows), self.assertRaises(CoreMismatch):
                compare_trace(electrical_table(rows), self.expected)

    def test_missing_and_duplicate_columns_fail(self):
        table = electrical_table(self.rows)
        for header in ("edge\tphase\tACC", table.splitlines()[0] + "\tACC"):
            with self.subTest(header=header), self.assertRaises(CoreMismatch):
                compare_trace(header + "\n" + "\n".join(table.splitlines()[1:]), self.expected)

    def test_repeated_identical_instructions_still_require_every_edge(self):
        rows = expected_trace(assemble("LOAD_CONST(7)\nLOAD_CONST(7)\nHALT()\n"))
        self.assertEqual(len(rows), 6)
        del rows[2:4]
        with self.assertRaises(CoreMismatch):
            compare_trace(electrical_table(rows), expected_trace(
                assemble("LOAD_CONST(7)\nLOAD_CONST(7)\nHALT()\n")))

    def test_memory_write_and_later_read_cover_address_value_validity(self):
        rows = expected_trace(assemble(
            "LOAD_CONST(7)\nSTORE_ADDRESS(20)\nLOAD_CONST(0)\nLOAD_ADDRESS(20)\nHALT()\n"))
        store = rows[2]
        self.assertEqual({key: store[key] for key in (
            "MEM_WRITE", "MEM_ADDRESS", "MEM_WRITE_VALUE", "MEM_WRITE_VALID")}, {
                "MEM_WRITE": 1, "MEM_ADDRESS": 20, "MEM_WRITE_VALUE": 7, "MEM_WRITE_VALID": 1,
            })
        self.assertEqual(rows[3]["MEMORY"], "20:7:1")
        self.assertEqual(rows[6]["MEM_READ_VALUE"], 7)
        self.assertEqual(rows[6]["MEM_READ_VALID"], 1)
        self.assertEqual(rows[7]["ACC"], 7)
        for signal, value, index in (("MEMORY", "21:7:1", 3), ("MEM_ADDRESS", 21, 2),
                                     ("MEM_WRITE_VALID", 0, 2), ("MEM_READ_VALUE", 8, 6)):
            wrong = [dict(row) for row in rows]
            wrong[index][signal] = value
            with self.subTest(signal=signal), self.assertRaisesRegex(CoreMismatch, signal):
                compare_trace(electrical_table(wrong), rows)

    def test_invalid_store_then_read_and_output_events(self):
        rows = expected_trace(assemble(
            "STORE_ADDRESS(20)\nLOAD_ADDRESS(20)\nPRINT()\nPRINT_ADDRESS(20)\nHALT()\n"))
        self.assertEqual(rows[0]["MEM_WRITE_VALID"], 0)
        self.assertEqual(rows[2]["MEM_READ_VALID"], 0)
        self.assertEqual((rows[4]["PRINT_ENABLE"], rows[4]["PRINT_VALUE"],
                          rows[4]["PRINT_VALID"]), (1, 0, 0))
        self.assertEqual((rows[6]["PRINT_ADDRESS_ENABLE"], rows[6]["PRINT_ADDRESS_VALUE"],
                          rows[6]["PRINT_ADDRESS_VALID"]), (1, 0, 0))
        self.assertEqual(rows[1]["ERROR_INV"], 1)

    def test_address_register_and_sticky_flags_are_compared_each_edge(self):
        rows = expected_trace(assemble(
            "LOAD_ADDRESS_REGISTER_CONST(20)\nLOAD_CONST(32767)\nADD_CONST(1)\n"
            "CLEAR_ERROR()\nHALT_ERROR()\n"))
        self.assertEqual((rows[1]["AR"], rows[1]["AR_VALID"]), (20, 1))
        self.assertEqual((rows[5]["ACC"], rows[5]["ACC_VALID"], rows[5]["ERROR_OVF"]), (0, 0, 1))
        self.assertEqual((rows[7]["ERROR_OVF"], rows[7]["ACC_VALID"]), (0, 0))
        self.assertEqual((rows[-2]["HALTED"], rows[-2]["HALTED_WITH_ERROR"]), (0, 1))
        wrong = [dict(row) for row in rows]
        wrong[1]["AR_VALID"] = 0
        with self.assertRaisesRegex(CoreMismatch, "AR_VALID"):
            compare_trace(electrical_table(wrong), rows)

    def test_missing_input_has_explicit_invalid_zero_result(self):
        rows = expected_trace(assemble("LOAD_CONST(9)\nINPUT()\nHALT_ERROR()\n"))
        self.assertEqual((rows[3]["ACC"], rows[3]["ACC_VALID"], rows[3]["ERROR_INPUT"]), (0, 0, 1))

    def test_output_event_value_validity_and_every_flag_are_checked(self):
        expected = expected_trace(assemble("LOAD_CONST(7)\nPRINT()\nHALT()\n"))
        for signal, index, value in (
            ("PRINT_ENABLE", 2, 0), ("PRINT_VALUE", 2, 8), ("PRINT_VALID", 2, 0),
            *((name, 1, 1) for name in SIGNALS if name.startswith("ERROR_")),
        ):
            wrong = [dict(row) for row in expected]
            wrong[index][signal] = value
            with self.subTest(signal=signal), self.assertRaisesRegex(CoreMismatch, signal):
                compare_trace(electrical_table(wrong), expected)

    def test_exporter_failure_cannot_pass_with_plausible_complete_data(self):
        def export(command, **kwargs):
            kwargs["stdout"].write(electrical_table(self.rows).encode())
            return subprocess.CompletedProcess(command, 1)

        with tempfile.TemporaryDirectory() as directory, patch(
            "tiny_cpu_logisim.subprocess.run", side_effect=export
        ):
            with self.assertRaisesRegex(LogisimError, "exporter exited 1"):
                run_core_comparison(ROOT / "hardware/logisim/TinyCPU.circ", load_profile(),
                                    self.program, tuple(encode_program(self.program)),
                                    Path("logisim.jar"), "java", Path(directory) / "trace.tsv", 10, "bad")

    def test_timeout_keeps_partial_raw_evidence(self):
        def export(command, **kwargs):
            kwargs["stdout"].write(b"partial raw trace\n")
            raise subprocess.TimeoutExpired(command, 1)

        with tempfile.TemporaryDirectory() as directory, patch(
            "tiny_cpu_logisim.subprocess.run", side_effect=export
        ):
            output = Path(directory) / "trace.tsv"
            with self.assertRaisesRegex(LogisimError, "trace timed out"):
                run_core_comparison(ROOT / "hardware/logisim/TinyCPU.circ", load_profile(),
                                    self.program, tuple(encode_program(self.program)),
                                    Path("logisim.jar"), "java", output, 1, "timeout")
            self.assertEqual(output.read_bytes(), b"partial raw trace\n")

    def test_comparison_preserves_raw_trace_inputs_and_first_failure(self):
        self.rows[1]["ACC"] = 4
        raw = electrical_table(self.rows).encode()

        def export(command, **kwargs):
            kwargs["stdout"].write(raw)
            kwargs["stderr"].write(b"simulator diagnostic\n")
            return subprocess.CompletedProcess(command, 0)

        with tempfile.TemporaryDirectory() as directory, patch(
            "tiny_cpu_logisim.subprocess.run", side_effect=export
        ):
            output = Path(directory) / "wrong.tsv"
            with self.assertRaisesRegex(LogisimError, "fixture wrong: edge 1 post, ACC"):
                run_core_comparison(ROOT / "hardware/logisim/TinyCPU.circ", load_profile(),
                                    self.program, tuple(encode_program(self.program)),
                                    Path("logisim.jar"), "java", output, 10, "wrong")
            self.assertEqual(output.read_bytes(), raw)
            evidence = output.with_suffix("")
            self.assertTrue((evidence / "TinyCPU.circ").is_file())
            self.assertTrue((evidence / "expected.json").is_file())
            self.assertTrue((evidence / "probes.tsv").is_file())
            self.assertEqual(json.loads((evidence / "diagnostic.json").read_text()), {
                "fixture": "wrong", "edge": 1, "phase": "post", "signal": "ACC",
                "expected": 3, "actual": 4,
            })


if __name__ == "__main__":
    unittest.main()
