import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from tiny_cpu_assembler import assemble
from tiny_cpu_core_trace import CoreMismatch, INPUT_SIGNALS, compare_trace, expected_trace
from tiny_cpu_input_stimuli import (SCHEMA, LEDGER_HEADER, bus_offer, host_offer,
                                    check_consumption, load_stimuli, validate_stimuli, write_stimuli)
from tiny_cpu_logisim import LogisimError

spec = importlib.util.spec_from_file_location("input_driver", ROOT / "scripts/test-logisim-input.py")
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


def table(rows):
    header = ["edge", "phase", *INPUT_SIGNALS, "MEMORY"]
    def cell(row, name):
        if name in INPUT_SIGNALS:
            return format(row.get(name, 0), f"0{INPUT_SIGNALS[name][0]}b")
        return str(row.get(name, "-"))
    return "\t".join(header) + "\n" + "".join(
        "\t".join(cell(row, name) for name in header) + "\n" for row in rows)


def ledger(document, attempts):
    return LEDGER_HEADER + "\n" + "".join(
        f'{o["edge"]}\t{o["reset"]}\t{o["value"]:016b}\t{o["valid"]}\t{int(o["edge"] in attempts)}\n'
        for o in document["edges"])


class InputStimuliTests(unittest.TestCase):
    def setUp(self):
        self.cases = {c["name"]: c for c in driver.load_cases()}
        self.document = copy.deepcopy(self.cases["consecutive"]["inputs"])

    def test_fixed_matrix_states_and_independent_consumption(self):
        self.assertEqual(len(self.cases), 23)
        for case in self.cases.values():
            with self.subTest(case=case["name"]):
                original = copy.deepcopy(case["inputs"])
                rows = expected_trace(assemble(case["program"]), stimuli=case["inputs"])
                driver.fixed_expectations(rows, case["checks"])
                compare_trace(table(rows), rows, signals=INPUT_SIGNALS)
                summary = check_consumption(ledger(case["inputs"], [e["edge"] for e in case["events"]]),
                                            case["inputs"], case["events"])
                self.assertEqual(summary["attempts"], len(case["events"]))
                self.assertEqual(case["inputs"], original)

    def test_all_existing_roms_keep_full_state_parity_on_the_inactive_input_top(self):
        fixtures = list(driver.baseline_cases())
        self.assertEqual(len(fixtures), 63)
        self.assertEqual(len({case['name'] for case, _, _ in fixtures}), 63)
        for case, program, words in fixtures:
            with self.subTest(case=case['name']):
                reference = expected_trace(program)
                rows = expected_trace(program, stimuli=case['inputs'])
                self.assertEqual(len(rows), len(reference))
                for row, baseline in zip(rows, reference):
                    self.assertEqual({k: row[k] for k in baseline}, baseline)
                self.assertTrue(words)
                self.assertTrue(all(o['value'] == o['valid'] == 0 for o in case['inputs']['edges']))
                check_consumption(ledger(case['inputs'], [e['edge'] for e in case['events']]),
                                  case['inputs'], case['events'])

    def test_host_range_is_checked_before_bus_encoding(self):
        for value, bits, valid in [(-32769, 32767, 0), (-32768, 32768, 1),
                                   (32767, 32767, 1), (32768, 32768, 0), (-1, 65535, 1)]:
            offer = host_offer(1, value, entry="a")
            self.assertEqual((offer["value"], offer["valid"], offer["host_value"]), (bits, valid, value))
        for value in (True, 3.5, "23"):
            with self.assertRaises(ValueError):
                host_offer(1, value, entry="a")
        self.document["edges"][0] = host_offer(1, 32768, entry="a")
        self.document["edges"][0]["valid"] = 1
        with self.assertRaisesRegex(ValueError, "host range"):
            validate_stimuli(self.document)

    def test_unknown_missing_fields_widths_and_undefined_values_fail_closed(self):
        mutations = [("extra", 0), ("edge", 0), ("reset", 2), ("valid", -1),
                     ("value", 65536), ("value", -1), ("value", "E"),
                     ("valid", "U"), ("value", True), ("host_value", 3.5)]
        for field, value in mutations:
            document = copy.deepcopy(self.document)
            document["edges"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate_stimuli(document)
        for field in self.document["edges"][0]:
            document = copy.deepcopy(self.document)
            del document["edges"][0][field]
            with self.subTest(missing=field), self.assertRaises(ValueError):
                validate_stimuli(document)

    def test_duplicate_json_fields_and_unknown_document_schema_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "inputs.json"
            path.write_text('{"schema":"a","schema":"b","edges":[]}')
            with self.assertRaisesRegex(ValueError, "duplicate"):
                load_stimuli(path)
        for document in ({"schema": SCHEMA, "edges": []}, {**self.document, "extra": 1},
                         {**self.document, "schema": "v2"}):
            with self.assertRaises(ValueError):
                validate_stimuli(document)

    def test_stimulus_count_and_order_must_match_executed_edges(self):
        program = assemble(self.cases["consecutive"]["program"])
        for rows in (self.document["edges"][:-1],
                     self.document["edges"] + [bus_offer(5)],
                     list(reversed(self.document["edges"])),
                     self.document["edges"][:1] + self.document["edges"]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                expected_trace(program, stimuli={"schema": SCHEMA, "edges": rows})
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            expected_trace(program, inputs=[1], stimuli=self.document)

    def test_offers_are_held_through_post_and_consumption_is_per_edge(self):
        rows = expected_trace(assemble(self.cases["consecutive"]["program"]), stimuli=self.document)
        self.assertEqual([rows[i]["INPUT_CONSUME"] for i in range(3)], [1, 1, 1])
        for pre, post, offer in zip(rows[::2], rows[1::2], self.document["edges"]):
            self.assertEqual(pre["INPUT_VALUE"], post["INPUT_VALUE"])
            self.assertEqual(post["INPUT_VALUE"], offer["value"])
            self.assertEqual(pre["INPUT_VALID"], post["INPUT_VALID"])

    def test_reset_restarts_fetch_and_blocks_input_without_clearing_existing_state(self):
        offers = {"schema": SCHEMA, "edges": [host_offer(1, 23, entry="a"),
            host_offer(2, -1, entry="b", reset=1), host_offer(3, -1, entry="b"),
            bus_offer(4), bus_offer(5)]}
        rows = expected_trace(assemble("INPUT()\nPRINT()\nHALT()\n"), stimuli=offers)
        for index in (2, 3):
            self.assertEqual((rows[index]["PC"], rows[index]["ACC"], rows[index]["ACC_VALID"],
                              rows[index]["INPUT_CONSUME"]), (0, 23, 1, 0))
        self.assertEqual((rows[5]["ACC"], rows[5]["ACC_VALID"]), (65535, 1))

    def test_input_readback_widths_values_and_post_hold_are_checked(self):
        rows = expected_trace(assemble(self.cases["consecutive"]["program"]), stimuli=self.document)
        for signal, index, value in [("INPUT_VALUE", 1, 1), ("INPUT_VALID", 1, 0),
                                     ("INPUT_CONSUME", 0, 0), ("RESET", 0, 1)]:
            wrong = copy.deepcopy(rows)
            wrong[index][signal] = value
            with self.subTest(signal=signal), self.assertRaisesRegex(CoreMismatch, signal):
                compare_trace(table(wrong), rows, signals=INPUT_SIGNALS)
        text = table(rows)
        for signal in ("INPUT_VALUE", "INPUT_VALID", "INPUT_CONSUME", "RESET"):
            for raw in ("E", "U", "0" * (INPUT_SIGNALS[signal][0] + 1)):
                lines = text.splitlines()
                cells = lines[1].split("\t")
                cells[lines[0].split("\t").index(signal)] = raw
                lines[1] = "\t".join(cells)
                with self.subTest(signal=signal, raw=raw), self.assertRaisesRegex(CoreMismatch, signal):
                    compare_trace("\n".join(lines), rows, signals=INPUT_SIGNALS)

    def test_ledger_detects_omissions_duplicates_reset_and_non_input_consumption(self):
        for name, attempts in [("consecutive", [1]), ("consecutive", [1, 2, 3]),
                                ("reset", [1, 3]), ("noinput", [1])]:
            case = self.cases[name]
            with self.subTest(name=name, attempts=attempts), self.assertRaises(ValueError):
                check_consumption(ledger(case["inputs"], attempts), case["inputs"], case["events"])
        document = {"schema": SCHEMA, "edges": [host_offer(1, 23, entry="a"), host_offer(2, 23, entry="a")]}
        with self.assertRaisesRegex(ValueError, "duplicate source"):
            check_consumption(ledger(document, [1, 2]), document, [])
        with self.assertRaisesRegex(ValueError, "offered again"):
            check_consumption(ledger(document, [1]), document, [])

    def test_ledger_requires_every_edge_and_defined_pin_readbacks(self):
        text = ledger(self.document, [1, 2])
        lines = text.splitlines()
        wrong = [lines[:-1], lines + [lines[-1]], [lines[0], lines[2], lines[1], *lines[3:]],
                 [lines[0], lines[1][:-1] + "E", *lines[2:]]]
        for rows in wrong:
            with self.assertRaises(ValueError):
                check_consumption("\n".join(rows), self.document, self.cases["consecutive"]["events"])
        result = check_consumption(ledger(self.cases["interleaved"]["inputs"], [1, 3, 5]),
                                   self.cases["interleaved"]["inputs"], self.cases["interleaved"]["events"])
        self.assertEqual((result["attempts"], result["removed_entries"]), (3, 2))

    def test_stimulus_serialization_contains_no_vm_expectations(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stimuli.tsv"
            write_stimuli(path, self.document)
            text = path.read_text()
            self.assertEqual(text.splitlines()[0], "edge\tRESET\tINPUT_VALUE\tINPUT_VALID")
            self.assertNotIn("ACC", text)
            self.assertNotIn("CONSUME", text)

    def test_exporter_failure_and_timeout_keep_raw_evidence_and_cannot_pass(self):
        for failure in ("exit", "timeout"):
            def export(command, **kwargs):
                kwargs["stdout"].write(b"partial evidence\n")
                if failure == "timeout":
                    raise subprocess.TimeoutExpired(command, 45)
                return subprocess.CompletedProcess(command, 1)
            with tempfile.TemporaryDirectory() as directory, patch.object(driver.subprocess, "run", side_effect=export):
                output = Path(directory)
                with self.assertRaises(LogisimError):
                    driver.run_case(ROOT / "hardware/logisim/TinyCPU.circ", output, Path("logisim.jar"), "java", self.cases["valid23"])
                self.assertEqual((output / "trace.tsv").read_bytes(), b"partial evidence\n")
                self.assertTrue((output / "inputs.json").is_file())
                self.assertTrue((output / "command.json").is_file())

    def test_matrix_stops_before_mutations_and_retains_partial_results(self):
        def run(source, output, jar, java, case):
            if case["name"] == "reset":
                raise CoreMismatch(1, "post", "ACC", 0, 23)
            return {"edges": len(case["inputs"]["edges"])}
        with tempfile.TemporaryDirectory() as directory, patch.object(driver, "run_case", side_effect=run) as mocked, \
                patch.object(driver, "resolve_jar", return_value=Path("unused.jar")), \
                patch.object(sys, "argv", ["test-logisim-input.py", "--output", directory]), patch("builtins.print"):
            with self.assertRaises(CoreMismatch):
                driver.main()
            self.assertEqual(mocked.call_count, 20)
            summary = json.loads((Path(directory) / "run-summary.json").read_text())
            self.assertEqual((summary["status"], summary["fixture"], len(summary["cases"])), ("stopped", "reset", 19))
            self.assertEqual(summary["mutations"], {})
            self.assertTrue(summary["source_circuits_unchanged"])
            self.assertFalse((Path(directory) / "proof.json").exists())


if __name__ == "__main__":
    unittest.main()
