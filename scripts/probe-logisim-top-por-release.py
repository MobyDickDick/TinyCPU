#!/usr/bin/env python3
"""Build a temporary 8/8 top-level project that exposes POR and CPU clock."""

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path


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
    tree = ET.parse(source)
    root = tree.getroot()
    main = root.find("main")
    if main is None or main.get("name") != "TinyCPUMain":
        raise ValueError(f"{source}: TinyCPUMain is not the start circuit")
    circuit = next(
        item for item in root.findall("circuit")
        if item.get("name") == "TinyCPUMain"
    )

    found: set[str] = set()
    for component in circuit.findall("comp"):
        values = attributes(component)
        label = values.get("label", "")
        if label not in {"CLK", "RESET", "HALTED", "MONITOR_PC_OUT"}:
            continue
        if label == "MONITOR_PC_OUT":
            if component.get("name") != "Probe":
                raise ValueError(f"{source}: MONITOR_PC_OUT is not a probe")
        elif component.get("name") != "Pin":
            raise ValueError(f"{source}: {label} is not a pin")
        found.add(label)
        if label == "CLK":
            component.set("name", "Clock")
            for item in list(component):
                component.remove(item)
        elif label == "RESET":
            component.set("name", "POR")
            for item in list(component):
                component.remove(item)
        elif label == "HALTED":
            next(
                item for item in component.findall("a")
                if item.get("name") == "label"
            ).set("val", "halt")
        else:
            component.set("name", "Pin")
            for item in list(component):
                component.remove(item)
            add_attribute(component, "appearance", "classic")
            add_attribute(component, "facing", "west")
            add_attribute(component, "label", "PC_OUT_PROBE")
            add_attribute(component, "type", "output")
            add_attribute(component, "width", "8")

    expected = {"CLK", "RESET", "HALTED", "MONITOR_PC_OUT"}
    if found != expected:
        raise ValueError(f"{source}: unexpected probe boundary: {sorted(found)}")

    for component in circuit.findall("comp"):
        values = attributes(component)
        if (
            component.get("name") == "Pin"
            and values.get("type") == "output"
            and values.get("label") not in {"halt", "PC_OUT_PROBE"}
        ):
            component.set("name", "Probe")
            for item in component.findall("a"):
                if item.get("name") == "type":
                    component.remove(item)

    add_probe(circuit, "(350,400)", "CLK_SOURCE_PROBE", "(350,390)")
    add_probe(circuit, "(350,450)", "POR_SOURCE_PROBE", "(350,440)")

    destination.parent.mkdir(parents=True, exist_ok=True)
    tree.write(destination, encoding="utf-8", xml_declaration=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("hardware/logisim/TinyCPU-8-8.circ"),
    )
    args = parser.parse_args()
    build_probe(args.source, args.destination)


if __name__ == "__main__":
    main()
