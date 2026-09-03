"""Versioned execution profiles shared by TinyCPU tools."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Profile:
    name: str
    data_bits: int
    address_bits: int
    memory_size: int
    machine_format: str
    machine_path: Path

    @property
    def word_bits(self) -> int:
        return 6 + self.data_bits

    @property
    def signed_min(self) -> int:
        return -(1 << (self.data_bits - 1))

    @property
    def signed_max(self) -> int:
        return (1 << (self.data_bits - 1)) - 1

    @property
    def data_mask(self) -> int:
        return (1 << self.data_bits) - 1


_FILES = {
    "tinycpu-16-12": "tinycpu-16-12.json",
    "tinycpu-8-8": "tinycpu-8-8.json",
}


def load_profile(name: str = "tinycpu-16-12") -> Profile:
    """Load a checked-in profile by its stable identifier."""
    try:
        path = ROOT / "hardware" / "logisim" / _FILES[name]
    except KeyError:
        raise ValueError(f"unknown TinyCPU profile {name!r}") from None
    data = json.loads(path.read_text(encoding="utf-8"))
    machine_path = path.with_name(data["machine_format"])
    machine = json.loads(machine_path.read_text(encoding="utf-8"))
    if machine["format"] != data["machine_format_id"]:
        raise ValueError(f"profile {name!r} has an inconsistent machine format")
    return Profile(name, data["data_bits"], data["address_bits"],
                   data["memory_size"], data["machine_format_id"], machine_path)


DEFAULT_PROFILE = load_profile()
