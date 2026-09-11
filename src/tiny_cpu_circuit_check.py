#!/usr/bin/env python3
"""Static wiring checks and conservative repairs for Logisim ``.circ`` files."""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

Point = tuple[int, int]


def _point(value: str) -> Point:
    x, y = value.strip("()").split(",")
    return int(x), int(y)


def _attributes(component: ET.Element) -> dict[str, str]:
    return {item.get("name", ""): item.get("val", "") for item in component.findall("a")}


def _on_segment(point: Point, ends: tuple[Point, Point]) -> bool:
    (x, y), ((x1, y1), (x2, y2)) = point, ends
    return ((x1 == x2 == x and min(y1, y2) <= y <= max(y1, y2)) or
            (y1 == y2 == y and min(x1, x2) <= x <= max(x1, x2)))


@dataclass(frozen=True)
class CircuitIssue:
    circuit: str
    message: str

    def __str__(self) -> str:
        return f"{self.circuit}: {self.message}"


@dataclass(frozen=True)
class _Driver:
    point: Point
    label: str


def _subcircuit_outputs(definition: ET.Element, instance: ET.Element) -> list[_Driver]:
    """Return generated-box output terminals for a subcircuit instance.

    Logisim's fixed generated box puts output pins, in sheet-position order, at
    the instance anchor and then at 20-pixel intervals below it.  This is the
    important detail the old checker missed: an instance output is just as
    much a driver as the output of a primitive gate.
    """
    anchor_x, anchor_y = _point(instance.get("loc", ""))
    outputs = []
    pins = [pin for pin in definition.findall("comp")
            if pin.get("name") == "Pin" and _attributes(pin).get("type") == "output"]
    # Generated boxes order ports by their position in the child sheet, not by
    # XML element order (the latter often reflects years of manual editing).
    pins.sort(key=lambda pin: (_point(pin.get("loc", ""))[1],
                               _point(pin.get("loc", ""))[0]))
    for pin in pins:
        attributes = _attributes(pin)
        outputs.append(_Driver(
            (anchor_x, anchor_y + 20 * len(outputs)),
            f"{attributes.get('label', 'output')} of "
            f"{_attributes(instance).get('label', instance.get('name', 'subcircuit'))}",
        ))
    return outputs


def _drivers(circuit: ET.Element,
             definitions: dict[str, ET.Element] | None = None) -> list[_Driver]:
    gate_kinds = {
        "AND Gate", "OR Gate", "XOR Gate", "NAND Gate", "NOR Gate", "NOT Gate",
    }
    result = []
    for component in circuit.findall("comp"):
        kind = component.get("name", "")
        attributes = _attributes(component)
        if kind in gate_kinds:
            result.append(_Driver(
                _point(component.get("loc", "")),
                attributes.get("label") or f"{kind}@{component.get('loc')}",
            ))
        elif definitions and kind in definitions:
            result.extend(_subcircuit_outputs(definitions[kind], component))
    return result


def _net_drivers(circuit: ET.Element,
                 definitions: dict[str, ET.Element] | None = None,
                 omitted_wire: ET.Element | None = None) -> dict[Point, list[_Driver]]:
    segments = [(_point(w.get("from", "")), _point(w.get("to", "")))
                for w in circuit.findall("wire") if w is not omitted_wire]
    all_drivers = _drivers(circuit, definitions)
    points = ({point for segment in segments for point in segment}
              | {driver.point for driver in all_drivers})
    parent = {point: point for point in points}

    def find(point: Point) -> Point:
        while parent[point] != point:
            parent[point] = parent[parent[point]]
            point = parent[point]
        return point

    def union(left: Point, right: Point) -> None:
        left, right = find(left), find(right)
        if left != right:
            parent[right] = left

    for left, right in segments:
        union(left, right)
    # An endpoint on the interior of another segment creates a Logisim junction.
    for point in points:
        for segment in segments:
            if _on_segment(point, segment):
                union(point, segment[0])

    nets: dict[Point, list[_Driver]] = {}
    for driver in all_drivers:
        if driver.point in parent:
            nets.setdefault(find(driver.point), []).append(driver)
    return nets


def inspect_circuit(circuit: ET.Element,
                    definitions: dict[str, ET.Element] | None = None) -> list[CircuitIssue]:
    """Find nets driven by multiple primitive or subcircuit outputs."""
    name = circuit.get("name", "<unnamed>")
    issues = []
    for drivers in _net_drivers(circuit, definitions).values():
        if len(drivers) > 1:
            labels = sorted(driver.label for driver in drivers)
            issues.append(CircuitIssue(name, "outputs share one net: " + ", ".join(labels)))
    return issues


def _repair_circuit(circuit: ET.Element, definitions: dict[str, ET.Element]) -> bool:
    """Remove an unambiguous accidental bridge between two driven nets.

    A wire is considered safe to remove only if it belongs to a multi-driver
    net and removing it splits *all* drivers of that net into singly-driven
    nets.  Ambiguous faults are reported but deliberately left for a human.
    """
    bad_sets = [frozenset(driver.label for driver in drivers)
                for drivers in _net_drivers(circuit, definitions).values()
                if len(drivers) > 1]
    changed = False
    for bad in bad_sets:
        candidates = []
        for wire in circuit.findall("wire"):
            nets = _net_drivers(circuit, definitions, wire)
            groups = [frozenset(driver.label for driver in drivers)
                      for drivers in nets.values() if drivers]
            separated = [group for group in groups if group & bad]
            if (set().union(*separated) == set(bad)
                    and all(len(group & bad) <= 1 for group in separated)):
                candidates.append(wire)
        # Prefer a bridge whose two ends are already served by other wires.
        # Removing such a cross-link preserves both original signal routes.
        junction_bridges = []
        for candidate in candidates:
            others = [(_point(w.get("from", "")), _point(w.get("to", "")))
                      for w in circuit.findall("wire") if w is not candidate]
            ends = (_point(candidate.get("from", "")), _point(candidate.get("to", "")))
            if all(any(_on_segment(end, segment) for segment in others) for end in ends):
                junction_bridges.append(candidate)
        if junction_bridges:
            candidates = junction_bridges
        if len(candidates) == 1:
            circuit.remove(candidates[0])
            changed = True
    return changed


def inspect_project(path: Path) -> list[CircuitIssue]:
    root = ET.parse(path).getroot()
    definitions = {c.get("name", ""): c for c in root.findall("circuit")}
    return [issue for circuit in root.findall("circuit")
            for issue in inspect_circuit(circuit, definitions)]


def repair_project(path: Path) -> list[CircuitIssue]:
    """Repair uniquely identifiable bridges in *path* and return remaining issues."""
    tree = ET.parse(path)
    root = tree.getroot()
    definitions = {c.get("name", ""): c for c in root.findall("circuit")}
    changed = False
    for circuit in root.findall("circuit"):
        changed = _repair_circuit(circuit, definitions) or changed
    if changed:
        ET.indent(tree, space="  ")
        tree.write(path, encoding="unicode", xml_declaration=True)
    return [issue for circuit in root.findall("circuit")
            for issue in inspect_circuit(circuit, definitions)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="check and repair Logisim output collisions")
    parser.add_argument("--fix", action="store_true",
                        help="remove only uniquely identifiable accidental bridge wires")
    parser.add_argument("projects", nargs="+", type=Path)
    args = parser.parse_args(argv)
    issues = []
    for project in args.projects:
        issues.extend(repair_project(project) if args.fix else inspect_project(project))
    for issue in issues:
        print(issue)
    return int(bool(issues))


if __name__ == "__main__":
    raise SystemExit(main())
