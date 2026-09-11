#!/usr/bin/env python3
"""Static wiring checks for Logisim ``.circ`` projects."""

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


def inspect_circuit(circuit: ET.Element) -> list[CircuitIssue]:
    """Find nets driven by multiple combinational gate outputs."""
    name = circuit.get("name", "<unnamed>")
    segments = [(_point(w.get("from", "")), _point(w.get("to", "")))
                for w in circuit.findall("wire")]
    points = {point for segment in segments for point in segment}
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
    # Logisim creates a junction when a wire endpoint lands on another segment.
    for point in points:
        for segment in segments:
            if _on_segment(point, segment):
                union(point, segment[0])

    issues: list[CircuitIssue] = []
    drivers: dict[Point, list[str]] = {}
    gate_kinds = {
        "AND Gate", "OR Gate", "XOR Gate", "NAND Gate", "NOR Gate", "NOT Gate",
    }
    for component in circuit.findall("comp"):
        kind = component.get("name", "")
        if kind not in gate_kinds:
            continue
        attributes = _attributes(component)
        label = attributes.get("label") or f"{kind}@{component.get('loc')}"
        output = _point(component.get("loc", ""))
        if output in parent:
            drivers.setdefault(find(output), []).append(label)

    for labels in drivers.values():
        if len(labels) > 1:
            issues.append(CircuitIssue(
                name, "gate outputs share one net: " + ", ".join(sorted(labels))))
    return issues


def inspect_project(path: Path) -> list[CircuitIssue]:
    root = ET.parse(path).getroot()
    return [issue for circuit in root.findall("circuit") for issue in inspect_circuit(circuit)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="check Logisim gate wiring")
    parser.add_argument("projects", nargs="+", type=Path)
    args = parser.parse_args(argv)
    issues = [issue for project in args.projects for issue in inspect_project(project)]
    for issue in issues:
        print(issue)
    return int(bool(issues))


if __name__ == "__main__":
    raise SystemExit(main())
