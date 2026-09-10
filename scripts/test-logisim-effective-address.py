#!/usr/bin/env python3
"""Electrically verify the address selection and range check."""

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


def run_fixture(jar: Path, name: str, values: dict[str, int]) -> dict[str, str]:
    tree = ET.parse(ROOT / "hardware/logisim/TinyCPU.circ")
    root = tree.getroot()
    root.find("main").set("name", "EffectiveAddress")
    circuit = next(
        item for item in root.findall("circuit")
        if item.get("name") == "EffectiveAddress"
    )
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
        if label in {"REG_ADDR", "DIRECT_ADDR", "OFFSET_ADDR", "REG_SELECTED"}:
            ET.SubElement(component, "a", name="width", val="16")

    with tempfile.TemporaryDirectory(prefix=f"tinycpu-effective-address-{name}-") as directory:
        target = Path(directory) / "effective-address.circ"
        tree.write(target, encoding="utf-8", xml_declaration=True)
        result = subprocess.run(
            [os.environ.get("JAVA", "java"), "-jar", str(jar), "-tty", "table", str(target)],
            capture_output=True, text=True, timeout=30, check=False,
        )
    if result.returncode:
        raise LogisimError(f"effective-address fixture {name} failed: {result.stderr.strip()}")
    rows = [line.split() for line in result.stdout.splitlines() if line.strip()]
    if len(rows) != 2 or len(rows[0]) != len(rows[1]):
        raise LogisimError(f"effective-address fixture {name} returned an unexpected table")
    return dict(zip(rows[0], rows[1]))


def main() -> int:
    explicit = Path(os.environ["LOGISIM_JAR"]) if os.environ.get("LOGISIM_JAR") else None
    if explicit is None:
        local = ROOT / ".venv/Include/logisim-evolution-4.1.0-all.jar"
        explicit = local if local.is_file() else None
    jar = resolve_jar(explicit)
    common = {
        "REG_ADDR": 20,
        "DIRECT_ADDR": 10,
        "OFFSET_ADDR": 21,
        "REG_SELECTED": 20,
        "ADDR_REG_ARGUMENT": 0,
        "ADDR_REG_OFFS_ARGUMENT": 0,
    }
    fixtures = {
        "direct": ({"REG_SELECTED": 10}, "0x000a", "0"),
        "register": ({"ADDR_REG_ARGUMENT": 1}, "0x0014", "0"),
        "register-offset": ({"ADDR_REG_ARGUMENT": 1, "ADDR_REG_OFFS_ARGUMENT": 1}, "0x0015", "0"),
        "maximum": ({"ADDR_REG_ARGUMENT": 1, "REG_ADDR": 0x0FFF, "REG_SELECTED": 0x0FFF}, "0x0fff", "0"),
        "out-of-range": ({"ADDR_REG_ARGUMENT": 1, "REG_ADDR": 0x1000, "REG_SELECTED": 0x1000}, "0x1000", "1"),
    }
    for name, (specific, expected_address, expected_range) in fixtures.items():
        actual = run_fixture(jar, name, common | specific)
        expected = {
            "EFFECTIVE_MEMORY_ADDRESS": expected_address,
            "ADDRESS_OUT_OF_RANGE": expected_range,
        }
        differences = [key for key, value in expected.items() if actual.get(key) != value]
        if differences:
            raise LogisimError(f"effective-address fixture {name}: mismatched {', '.join(differences)}")
    print("electrical effective-address acceptance passed: direct, register, offset, and range boundary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
