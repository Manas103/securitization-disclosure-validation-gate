"""Loads the machine-readable disclosure specification (``spec/disclosure_spec.json``)
into ``Attribute`` objects. This is the only thing in the repo that reads the
spec file; the compiler in ``app/compiler.py`` is the only thing that turns an
``Attribute`` into assertions, so there is exactly one path from the published
guide's field table to an executable check.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SPEC_PATH = Path(__file__).resolve().parents[1] / "spec" / "disclosure_spec.json"


@dataclass(frozen=True)
class Attribute:
    attribute_id: str
    name: str
    definition: str
    datatype: str          # "string" | "numeric" | "date"
    format: str | None      # e.g. "MMCCYY", "MMDDCCYY", "14.2", or None
    max_length: int
    enumeration: tuple[str, ...] | None


def load_spec(path: Path = DEFAULT_SPEC_PATH) -> list[Attribute]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    attrs = []
    for a in raw["attributes"]:
        enum = tuple(a["enumeration"]) if a.get("enumeration") else None
        attrs.append(Attribute(
            attribute_id=a["attribute_id"],
            name=a["name"],
            definition=a["definition"],
            datatype=a["datatype"],
            format=a.get("format"),
            max_length=a["max_length"],
            enumeration=enum,
        ))
    return attrs


def load_spec_metadata(path: Path = DEFAULT_SPEC_PATH) -> dict:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return {k: v for k, v in raw.items() if k != "attributes"}
