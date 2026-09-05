"""Versioned optional system profiles layered on frozen TinyCPU hardware profiles."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from tiny_cpu_profiles import Profile, ROOT, load_profile


@dataclass(frozen=True)
class SystemProfile:
    """Validated AP-18 integration contract selected explicitly by name."""

    name: str
    base_profile: Profile
    output_address: int
    interrupt_vector: int
    machine_format: str
    machine_path: Path
    trace_schema: str
    trace_path: Path
    circuit_path: Path
    top_circuit: str
    public_pins: dict[str, dict[str, object]]


_FILES = {"tinycpu-peripherals-16-12-v1": "tinycpu-peripherals-16-12-v1.json"}


def load_system_profile(name: str) -> SystemProfile:
    """Load an optional system contract without changing the default CPU profile."""
    try:
        path = ROOT / "hardware" / "logisim" / _FILES[name]
    except KeyError:
        raise ValueError(f"unknown TinyCPU system profile {name!r}") from None
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("system") != name:
        raise ValueError(f"system profile {name!r} has an inconsistent identifier")
    base = load_profile(data["base_profile"])
    machine_path = path.with_name(data["machine_format"])
    trace_path = path.with_name(data["trace_schema"])
    machine = json.loads(machine_path.read_text(encoding="utf-8"))
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    if machine.get("format") != data["machine_format_id"]:
        raise ValueError(f"system profile {name!r} has an inconsistent machine format")
    if trace.get("system") != name or trace.get("schema") != trace_path.stem:
        raise ValueError(f"system profile {name!r} has an inconsistent trace schema")
    output_address = data["io"]["output_address"]
    vector = data["interrupt"]["vector"]
    if not 0 <= output_address < base.memory_size or not 0 <= vector < base.memory_size:
        raise ValueError(f"system profile {name!r} contains an out-of-range address")
    if output_address == vector:
        raise ValueError(f"system profile {name!r} aliases its output port and interrupt vector")
    circuit_path = path.with_name(data["circuit"])
    if not circuit_path.is_file():
        raise ValueError(f"system profile {name!r} refers to a missing circuit")
    public_pins = data.get("public_pins")
    if not isinstance(public_pins, dict) or not public_pins:
        raise ValueError(f"system profile {name!r} has no public pin contract")
    return SystemProfile(name, base, output_address, vector, machine["format"],
                         machine_path, trace["schema"], trace_path, circuit_path,
                         data["top_circuit"], public_pins)
