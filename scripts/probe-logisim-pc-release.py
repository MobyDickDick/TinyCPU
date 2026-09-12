#!/usr/bin/env python3
"""Build a temporary 8/8 FetchDecode project for the AP 20.5 PC probe."""

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


def add_probe(
    circuit: ET.Element,
    location: str,
    label: str,
    source: str,
    width: str | None = None,
) -> None:
    pin = ET.SubElement(
        circuit, "comp", {"lib": "0", "loc": location, "name": "Pin"}
    )
    add_attribute(pin, "appearance", "classic")
    add_attribute(pin, "facing", "west")
    add_attribute(pin, "label", label)
    add_attribute(pin, "type", "output")
    if width is not None:
        add_attribute(pin, "width", width)
    ET.SubElement(circuit, "wire", {"from": source, "to": location})


def build_probe(source: Path, destination: Path) -> None:
    tree = ET.parse(source)
    root = tree.getroot()
    main = root.find("main")
    if main is None:
        raise ValueError(f"{source}: main circuit declaration is missing")
    main.set("name", "FetchDecode")
    circuit = next(
        item for item in root.findall("circuit") if item.get("name") == "FetchDecode"
    )

    found: set[str] = set()
    for component in circuit.findall("comp"):
        values = attributes(component)
        label = values.get("label", "")
        if component.get("name") != "Pin" or values.get("type") == "output":
            continue
        found.add(label)
        component.set("lib", "0")
        for item in list(component):
            component.remove(item)
        if label == "CLK":
            component.set("name", "Clock")
            add_attribute(component, "highDuration", "2")
            add_attribute(component, "lowDuration", "2")
        elif label == "RESET":
            # Invert a slow clock: RESET starts high, falls before the first
            # active CPU edge, and then remains low throughout the short probe.
            component.set("lib", "1")
            component.set("name", "NOT Gate")
            reset_clock = ET.SubElement(
                circuit, "comp", {"lib": "0", "loc": "(460,290)", "name": "Clock"}
            )
            add_attribute(reset_clock, "highDuration", "100")
            add_attribute(reset_clock, "lowDuration", "2")
            ET.SubElement(circuit, "wire", {"from": "(460,290)", "to": "(480,290)"})
        else:
            component.set("name", "Constant")
            if "width" in values:
                add_attribute(component, "width", values["width"])
            add_attribute(
                component,
                "value",
                "0xff" if label == "PROGRAM_LIMIT" else "0x0",
            )

    expected = {
        "CLK", "RESET", "DEC_JUMP_NOT_ZERO", "NOT_ZERO",
        "PROGRAM_LIMIT", "DEC_HALT_ERROR",
    }
    if found != expected:
        raise ValueError(f"{source}: unexpected FetchDecode inputs: {sorted(found)}")

    add_probe(circuit, "(490,220)", "PC_D_PROBE", "(530,220)", "8")
    add_probe(circuit, "(490,260)", "CLK_PROBE", "(500,260)")
    add_probe(circuit, "(490,290)", "RESET_PROBE", "(500,290)")

    # table,halt advances clocks only when a halt-labelled output is present.
    zero = ET.SubElement(
        circuit, "comp", {"lib": "0", "loc": "(450,320)", "name": "Constant"}
    )
    add_attribute(zero, "value", "0x0")
    add_probe(circuit, "(490,320)", "halt", "(450,320)")

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
