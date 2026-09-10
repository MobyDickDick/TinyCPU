#!/usr/bin/env python3
"""Electrically verify repaired operand and arithmetic paths in ``Operations``."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tiny_cpu_logisim import LogisimError, resolve_jar

INPUTS = {
    "ACC_VALUE": 0,
    "ACC_VALID": 1,
    "ADD_OPERAND": 0,
    "SUB_OPERAND": 0,
    "MUL_OPERAND": 0,
    "DIV_OPERAND": 0,
    "AND_OPERAND": 0,
    "OR_OPERAND": 0,
    "XOR_OPERAND": 0,
    "NOT_OPERAND": 0,
}


def run_fixture(jar: Path, name: str, values: dict[str, int]) -> dict[str, str]:
    tree = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ")
    root = tree.getroot()
    root.find("main").set("name", "Operations")
    circuit = next(item for item in root.findall("circuit") if item.get("name") == "Operations")
    for component in circuit.findall("comp"):
        attributes = {item.get("name"): item.get("val") for item in component.findall("a")}
        label = attributes.get("label")
        if component.get("name") != "Pin" or attributes.get("type") == "output":
            continue
        component.set("name", "Constant")
        component.set("lib", "0")
        for attribute in list(component):
            component.remove(attribute)
        ET.SubElement(component, "a", name="value", val=hex(values[label]))
        if label in {"ACC_VALUE", "MEMORY_VALUE", "IMMEDIATE_VALUE"}:
            ET.SubElement(component, "a", name="width", val="16")

    with tempfile.TemporaryDirectory(prefix=f"tinycpu-operations-{name}-") as directory:
        target = Path(directory) / "operations.circ"
        tree.write(target, encoding="utf-8", xml_declaration=True)
        result = subprocess.run(
            [os.environ.get("JAVA", "java"), "-jar", str(jar), "-tty", "table", str(target)],
            capture_output=True, text=True, timeout=30, check=False,
        )
    if result.returncode:
        raise LogisimError(f"operations fixture {name} failed: {result.stderr.strip()}")
    rows = [line.split() for line in result.stdout.splitlines() if line.strip()]
    if len(rows) != 2 or len(rows[0]) != len(rows[1]):
        raise LogisimError(f"operations fixture {name} returned an unexpected table")
    return dict(zip(rows[0], rows[1]))


def main() -> int:
    explicit = Path(os.environ["LOGISIM_JAR"]) if os.environ.get("LOGISIM_JAR") else None
    if explicit is None:
        local = ROOT / ".venv/Include/logisim-evolution-4.1.0-all.jar"
        explicit = local if local.is_file() else None
    jar = resolve_jar(explicit)
    fixtures = {
        "memory": ({"MEMORY_VALUE": 0x1234, "IMMEDIATE_VALUE": 0xABCD,
                    "MEMORY_VALID": 1, "CONST_OPERAND": 0}, "0x1234"),
        "immediate": ({"MEMORY_VALUE": 0x1234, "IMMEDIATE_VALUE": 0xABCD,
                       "MEMORY_VALID": 0, "CONST_OPERAND": 1}, "0xabcd"),
        "multiply-positive-overflow": ({"ACC_VALUE": 0x4000,
                                         "MEMORY_VALUE": 0,
                                         "IMMEDIATE_VALUE": 2,
                                         "MEMORY_VALID": 1,
                                         "CONST_OPERAND": 1,
                                         "MUL_OPERAND": 1}, "0x8000"),
        "multiply-in-range": ({"ACC_VALUE": 3, "MEMORY_VALUE": 0,
                                "IMMEDIATE_VALUE": 2, "MEMORY_VALID": 1,
                                "CONST_OPERAND": 1, "MUL_OPERAND": 1},
                              "0x0006"),
        "divide-in-range": ({"ACC_VALUE": 7, "MEMORY_VALUE": 0,
                              "IMMEDIATE_VALUE": 2, "MEMORY_VALID": 1,
                              "CONST_OPERAND": 1, "DIV_OPERAND": 1},
                            "0x0003"),
        "divide-by-zero": ({"ACC_VALUE": 7, "MEMORY_VALUE": 0,
                             "IMMEDIATE_VALUE": 0, "MEMORY_VALID": 1,
                             "CONST_OPERAND": 1, "DIV_OPERAND": 1},
                           "0x0007"),
    }
    for name, (specific, expected_value) in fixtures.items():
        actual = run_fixture(jar, name, INPUTS | specific)
        expected = {"RESULT_VALUE": expected_value}
        if name.startswith("multiply-"):
            expected["OVERFLOW"] = (
                "1" if name == "multiply-positive-overflow" else "0"
            )
        elif name.startswith("divide-"):
            expected["DIVIDE_BY_ZERO"] = "1" if name == "divide-by-zero" else "0"
            expected["RESULT_IS_VALID"] = "0" if name == "divide-by-zero" else "1"
        else:
            expected["RESULT_IS_VALID"] = "1"
        differences = [key for key, value in expected.items() if actual.get(key) != value]
        if differences:
            raise LogisimError(f"operations fixture {name}: mismatched {', '.join(differences)}")
    print(
        "electrical operations acceptance passed: operand selection and "
        "multiplication overflow and division validity"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
