#!/usr/bin/env python3
"""Geometry audit for accidental contacts between Logisim wires."""

from __future__ import annotations

import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

Point = tuple[int, int]
Segment = tuple[Point, Point]


def schematic_geometry_digest(circuit: ET.Element) -> str:
    """Identify a reviewed drawing independent of XML order and ROM contents."""
    components = []
    for component in circuit.findall('comp'):
        attributes = sorted((a.get('name'), a.get('val'), a.text or '')
                            for a in component.findall('a')
                            if a.get('name') not in {'contents', 'value'})
        components.append((sorted(component.attrib.items()), attributes))
    wires = sorted(tuple(sorted((_point(w.get('from')), _point(w.get('to')))))
                   for w in circuit.findall('wire'))
    payload = [circuit.get('name'), sorted(components), wires]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


@lru_cache(maxsize=1)
def _restored_layouts() -> set[str]:
    manifest = Path(__file__).resolve().parents[1] / 'hardware/logisim/layout-restoration-v1.json'
    data = json.loads(manifest.read_text(encoding='utf-8'))
    return {entry['geometry_sha256'] for entry in data['circuits']}


def inspect_schematic_layout(circuit: ET.Element, origin=(0, 0)) -> list[str]:
    """Keep the user's restored drawings; check other geometry on the grid.

    The exception covers exact reviewed geometry only. Adding or moving any
    wire or component falls back to the strict grid check. Electrical checks
    and interface validation are independent and always remain active.
    """
    if schematic_geometry_digest(circuit) in _restored_layouts():
        return []
    return inspect_routing_grid(circuit, origin=origin)


def _point(value: str) -> Point:
    x, y = value.strip("()").split(",")
    return int(x), int(y)


def _orientation(segment: Segment) -> str:
    (x1, y1), (x2, y2) = segment
    if x1 == x2 and y1 != y2:
        return "vertical"
    if y1 == y2 and x1 != x2:
        return "horizontal"
    return "invalid"


def _strictly_inside(point: Point, segment: Segment) -> bool:
    (x, y), ((x1, y1), (x2, y2)) = point, segment
    return ((x1 == x2 == x and min(y1, y2) < y < max(y1, y2)) or
            (y1 == y2 == y and min(x1, x2) < x < max(x1, x2)))


def _overlap(left: Segment, right: Segment) -> tuple[Point, Point] | None:
    orientation = _orientation(left)
    if orientation == "invalid" or orientation != _orientation(right):
        return None
    axis = 1 if orientation == "vertical" else 0
    fixed = 0 if axis == 1 else 1
    if left[0][fixed] != right[0][fixed]:
        return None
    start = max(min(end[axis] for end in left), min(end[axis] for end in right))
    stop = min(max(end[axis] for end in left), max(end[axis] for end in right))
    if start >= stop:
        return None
    coordinate = left[0][fixed]
    if axis == 1:
        return (coordinate, start), (coordinate, stop)
    return (start, coordinate), (stop, coordinate)


@dataclass(frozen=True)
class ContactIssue:
    circuit: str
    kind: str
    at: str
    wires: tuple[int, int]
    segments: tuple[str, str]

    def __str__(self) -> str:
        return (f"{self.circuit}: {self.kind} at {self.at}; wire "
                f"#{self.wires[0]} {self.segments[0]} and "
                f"#{self.wires[1]} {self.segments[1]}")


def inspect_circuit(circuit: ET.Element) -> list[ContactIssue]:
    """Find implicit T junctions and positive-length collinear overlaps.

    A proper perpendicular crossing is intentionally ignored: unlike an
    endpoint touching another wire, it does not form a Logisim junction.
    """
    name = circuit.get("name", "<unnamed>")
    segments = [(_point(wire.get("from", "")), _point(wire.get("to", "")))
                for wire in circuit.findall("wire")]
    issues: list[ContactIssue] = []
    for left_index, left in enumerate(segments, 1):
        for right_index in range(left_index + 1, len(segments) + 1):
            right = segments[right_index - 1]
            overlap = _overlap(left, right)
            if overlap:
                issues.append(ContactIssue(
                    name, "collinear overlap", f"{overlap[0]}..{overlap[1]}",
                    (left_index, right_index), (str(left), str(right))))
                continue
            contacts = ({point for point in left if _strictly_inside(point, right)} |
                        {point for point in right if _strictly_inside(point, left)})
            for point in sorted(contacts):
                issues.append(ContactIssue(
                    name, "endpoint-on-wire junction", str(point),
                    (left_index, right_index), (str(left), str(right))))
    return issues


def inspect_project(path: Path, circuits: set[str] | None = None) -> list[ContactIssue]:
    root = ET.parse(path).getroot()
    return [issue for circuit in root.findall("circuit")
            if circuits is None or circuit.get("name") in circuits
            for issue in inspect_circuit(circuit)]


def inspect_routing_grid(circuit: ET.Element, *, origin: Point = (0, 0)) -> list[str]:
    """Check long runs on four 20-pixel tracks followed by a 40-pixel gap.

    Logisim's grid pitch is 10 pixels. Coordinates 20/40/60/80 modulo 100
    therefore leave one empty row between wires and three between groups.
    Native component ports require short escapes; runs up to 160 pixels are
    exempt. Merge collinear segments first so junctions cannot hide a long run.
    The overview uses an x offset to clear its fixed symbol contacts.
    An explicit origin preserves the same spacing without requiring a global
    canvas translation. Protected hand-drawn decoders are checked separately.
    """
    lines = defaultdict(list)
    for wire in circuit.findall("wire"):
        a, b = _point(wire.get("from", "")), _point(wire.get("to", ""))
        if a[0] == b[0]:
            lines[("vertical", a[0])].append(sorted((a[1], b[1])))
        elif a[1] == b[1]:
            lines[("horizontal", a[1])].append(sorted((a[0], b[0])))
    issues = []
    for (orientation, coordinate), spans in sorted(lines.items()):
        merged = []
        for start, stop in sorted(spans):
            if merged and start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], stop)
            else:
                merged.append([start, stop])
        for start, stop in merged:
            offset = origin[0 if orientation == "vertical" else 1]
            if stop - start > 160 and (coordinate - offset) % 100 not in (20, 40, 60, 80):
                issues.append(
                    f"{circuit.get('name')}: {orientation} run at {coordinate} "
                    f"from {start} to {stop} violates the grouped routing grid"
                )
    return issues


def inspect_parallel_spacing(circuit: ET.Element) -> list[str]:
    """Require an empty 10-pixel row between overlapping parallel wire spans.

    Unlike the long-run grid check, this also inspects short pin fan-outs.
    Adjacent bends whose projections only meet at one point are not parallel
    runs. Collinear electrical contacts are checked by inspect_circuit.
    """
    segments = [(_point(w.get("from")), _point(w.get("to")))
                for w in circuit.findall("wire")]
    issues = []
    for index, (a, b) in enumerate(segments):
        direction = _orientation((a, b))
        if direction == "invalid":
            continue
        axis = 0 if direction == "horizontal" else 1
        fixed = 1 - axis
        for c, d in segments[index + 1:]:
            if _orientation((c, d)) != direction:
                continue
            gap = abs(a[fixed] - c[fixed])
            overlap = (min(max(a[axis], b[axis]), max(c[axis], d[axis]))
                       - max(min(a[axis], b[axis]), min(c[axis], d[axis])))
            if 0 < gap < 20 and overlap > 0:
                issues.append(f"{circuit.get('name')}: parallel {direction} wires "
                              f"at {a[fixed]} and {c[fixed]} leave no empty row")
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="find inconspicuous electrical contacts between Logisim wires")
    parser.add_argument("--json", action="store_true",
                        help="emit machine-readable findings")
    parser.add_argument("--circuit", action="append", default=[], metavar="NAME",
                        help="limit the audit to this circuit (repeatable)")
    parser.add_argument("projects", nargs="+", type=Path)
    args = parser.parse_args(argv)
    selected = set(args.circuit) or None
    findings = [(path, issue) for path in args.projects
                for issue in inspect_project(path, selected)]
    if args.json:
        print(json.dumps([{"project": str(path), **asdict(issue)}
                          for path, issue in findings], indent=2))
    else:
        for path, issue in findings:
            print(f"{path}: {issue}")
    return int(bool(findings))


if __name__ == "__main__":
    raise SystemExit(main())
