#!/usr/bin/env python3
"""Expose reset, clock and PC in the autonomous 8/8 acceptance project."""

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tiny_cpu_logisim import autonomous_project  # noqa: E402


def attributes(component: ET.Element) -> dict[str, str]:
    return {
        item.get("name", ""): item.get("val", "")
        for item in component.findall("a")
    }


def add_attribute(component: ET.Element, name: str, value: str) -> None:
    ET.SubElement(component, "a", {"name": name, "val": value})


def add_probe(circuit: ET.Element, location: str, label: str, source: str) -> None:
    pin = ET.SubElement(
        circuit, "comp", {"lib": "0", "loc": location, "name": "Pin"}
    )
    add_attribute(pin, "appearance", "classic")
    add_attribute(pin, "facing", "west")
    add_attribute(pin, "label", label)
    add_attribute(pin, "type", "output")
    ET.SubElement(circuit, "wire", {"from": source, "to": location})


def build_probe(source: Path, destination: Path) -> None:
    autonomous_project(source, destination, "TinyCPUMain")
    tree = ET.parse(destination)
    root = tree.getroot()
    circuit = next(
        item for item in root.findall("circuit")
        if item.get("name") == "TinyCPUMain"
    )

    pc = next(
        (component for component in circuit.findall("comp")
         if attributes(component).get("label") == "MONITOR_PC_OUT"),
        None,
    )
    if pc is None or pc.get("name") != "Probe":
        raise ValueError(f"{source}: MONITOR_PC_OUT is not a probe")
    pc.set("name", "Pin")
    for item in list(pc):
        pc.remove(item)
    add_attribute(pc, "appearance", "classic")
    add_attribute(pc, "facing", "west")
    add_attribute(pc, "label", "PC_OUT_PROBE")
    add_attribute(pc, "type", "output")
    add_attribute(pc, "width", "8")

    for component in circuit.findall("comp"):
        values = attributes(component)
        if (component.get("name") == "Pin"
                and values.get("type") == "output"
                and values.get("label") not in {"halt", "PC_OUT_PROBE"}):
            component.set("name", "Probe")
            for item in component.findall("a"):
                if item.get("name") == "type":
                    component.remove(item)

    add_probe(circuit, "(350,400)", "CLK_SOURCE_PROBE", "(350,390)")
    add_probe(circuit, "(350,450)", "RESET_SOURCE_PROBE", "(350,440)")
    tree.write(destination, encoding="utf-8", xml_declaration=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument(
        "--source", type=Path,
        default=Path("hardware/logisim/TinyCPU-8-8.circ"),
    )
    args = parser.parse_args()
    build_probe(args.source, args.destination)


if __name__ == "__main__":
    main()
