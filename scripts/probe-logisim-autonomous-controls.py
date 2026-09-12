#!/usr/bin/env python3
"""Expose the 8/8 autonomous fetch path without changing its source project."""

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


def expose_monitor(
    circuit: ET.Element, monitor_label: str, probe_label: str, width: str | None = None
) -> None:
    """Turn an existing, already connected monitor into a table output."""
    monitor = next(
        (
            component
            for component in circuit.findall("comp")
            if attributes(component).get("label") == monitor_label
        ),
        None,
    )
    if monitor is None or monitor.get("name") != "Probe":
        raise ValueError(f"{monitor_label} is not a probe")
    monitor.set("name", "Pin")
    for item in list(monitor):
        monitor.remove(item)
    add_attribute(monitor, "appearance", "classic")
    add_attribute(monitor, "facing", "west")
    add_attribute(monitor, "label", probe_label)
    add_attribute(monitor, "type", "output")
    if width is not None:
        add_attribute(monitor, "width", width)


def build_probe(source: Path, destination: Path) -> None:
    autonomous_project(source, destination, "TinyCPUMain")
    tree = ET.parse(destination)
    root = tree.getroot()
    circuit = next(
        item for item in root.findall("circuit")
        if item.get("name") == "TinyCPUMain"
    )

    expose_monitor(circuit, "MONITOR_PC_OUT", "PC_OUT_PROBE", "8")
    expose_monitor(circuit, "MONITOR_LOAD_CONST", "DECODE_LOAD_CONST_PROBE")

    # FetchDecode's 14-bit OPCODE output is connected to both decoder
    # boundaries at this existing junction.  The temporary branch therefore
    # observes the actual ROM word rather than a copied ROM fixture.
    add_probe(circuit, "(1260,480)", "ROM_WORD_PROBE", "(1160,480)")
    rom_probe = next(
        component for component in circuit.findall("comp")
        if attributes(component).get("label") == "ROM_WORD_PROBE"
    )
    add_attribute(rom_probe, "width", "14")

    for component in circuit.findall("comp"):
        values = attributes(component)
        if (component.get("name") == "Pin"
                and values.get("type") == "output"
                and values.get("label") not in {
                    "halt", "PC_OUT_PROBE", "ROM_WORD_PROBE",
                    "DECODE_LOAD_CONST_PROBE",
                }):
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
