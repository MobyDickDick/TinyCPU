"""Strict AP 22.1 per-edge offers and an independent source-consumption ledger."""
from __future__ import annotations

import json
from pathlib import Path

SCHEMA = "tinycpu-input-stimuli-v1"
STIMULUS_HEADER = "edge\tRESET\tINPUT_VALUE\tINPUT_VALID"
LEDGER_HEADER = STIMULUS_HEADER + "\tINPUT_CONSUME"


def host_offer(edge, value, *, entry, reset=0):
    if type(value) is not int:
        raise ValueError("host input must be an integer")
    return {"edge": edge, "reset": reset, "value": value & 0xffff,
            "valid": int(-32768 <= value <= 32767), "source": "host",
            "entry": entry, "host_value": value}


def bus_offer(edge, value=0, valid=0, *, source="idle", entry=None, reset=0):
    return {"edge": edge, "reset": reset, "value": value, "valid": valid,
            "source": source, "entry": entry}


def validate_stimuli(document):
    if (type(document) is not dict or set(document) != {"schema", "edges"}
            or document["schema"] != SCHEMA or type(document["edges"]) is not list
            or not document["edges"]):
        raise ValueError("invalid INPUT stimulus document")
    offers = document["edges"]
    entries = {}
    for edge, offer in enumerate(offers, 1):
        required = {"edge", "reset", "value", "valid", "source", "entry"}
        if type(offer) is not dict or set(offer) not in (required, required | {"host_value"}):
            raise ValueError(f"edge {edge}: missing/unknown stimulus fields")
        for field, maximum in (("edge", len(offers)), ("reset", 1), ("value", 65535), ("valid", 1)):
            if type(offer[field]) is not int or not 0 <= offer[field] <= maximum:
                raise ValueError(f"edge {edge}: {field} outside its defined width")
        if offer["edge"] != edge:
            raise ValueError(f"edge {edge}: missing, duplicate or reordered stimulus")
        source, entry = offer["source"], offer["entry"]
        if type(source) is not str or source not in {"host", "invalid", "empty", "idle"}:
            raise ValueError(f"edge {edge}: unknown source")
        if source in {"host", "invalid"}:
            if type(entry) is not str or not entry:
                raise ValueError(f"edge {edge}: source entry required")
            identity = (source, offer["value"], offer["valid"], offer.get("host_value"))
            if entry in entries and entries[entry] != identity:
                raise ValueError(f"edge {edge}: source entry changed while offered")
            entries[entry] = identity
        elif entry is not None:
            raise ValueError(f"edge {edge}: idle/empty source has no entry")
        if source in {"invalid", "empty"} and offer["valid"] != 0:
            raise ValueError(f"edge {edge}: invalid/empty source must be invalid")
        if source == "host":
            value = offer.get("host_value")
            if (type(value) is not int or offer["value"] != value & 0xffff
                    or offer["valid"] != int(-32768 <= value <= 32767)):
                raise ValueError(f"edge {edge}: host range/bit-pattern contract differs")
        elif "host_value" in offer:
            raise ValueError(f"edge {edge}: host_value requires host source")
    return offers


def load_stimuli(path: Path):
    def unique_fields(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate stimulus field: {key}")
            result[key] = value
        return result
    document = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_fields)
    validate_stimuli(document)
    return document


def write_stimuli(path: Path, document):
    offers = validate_stimuli(document)
    path.write_text(STIMULUS_HEADER + "\n" + "".join(
        f'{o["edge"]}\t{o["reset"]}\t{o["value"]:016b}\t{o["valid"]}\n' for o in offers),
        encoding="utf-8")


def check_consumption(text, document, expected_events):
    """Check exporter readbacks against fixed transaction/entry expectations.

    Every physical edge is logged, including reset and non-INPUT instructions.
    A failed read is an attempt; only a present source entry is removed. No VM
    input queue or exported trace column supplies the expected event list.
    """
    offers = validate_stimuli(document)
    lines = text.splitlines()
    if not lines or lines[0] != LEDGER_HEADER or len(lines) != len(offers) + 1:
        raise ValueError("consumption ledger has missing/extra rows or wrong columns")
    events, consumed = [], set()
    for offer, line in zip(offers, lines[1:]):
        cells = line.split("\t")
        prefix = [str(offer["edge"]), str(offer["reset"]), f'{offer["value"]:016b}', str(offer["valid"])]
        if len(cells) != 5 or cells[:4] != prefix or cells[4] not in {"0", "1"}:
            raise ValueError(f'edge {offer["edge"]}: invalid consumption readback')
        if cells[4] == "1":
            if offer["reset"] or offer["source"] == "idle":
                raise ValueError(f'edge {offer["edge"]}: reset/idle input consumed')
            entry = offer["entry"]
            if entry is not None:
                if entry in consumed:
                    raise ValueError(f'edge {offer["edge"]}: duplicate source consumption')
                consumed.add(entry)
            events.append({"edge": offer["edge"], "entry": entry, "source": offer["source"]})
        elif offer["entry"] in consumed:
            raise ValueError(f'edge {offer["edge"]}: consumed entry offered again')
    if events != expected_events:
        raise ValueError(f"consumption events differ: expected {expected_events}, actual {events}")
    return {"events": events, "attempts": len(events), "removed_entries": len(consumed)}
