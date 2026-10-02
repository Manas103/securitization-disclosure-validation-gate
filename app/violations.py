"""Injects exactly 60 seeded violations across four simulated files (one
daily-issuance core file ``mk``, one monthly factor core file ``mi``, and
their two correction counterparts ``mo``/``mw``), 15 per file, spread evenly
across the four assertion types (datatype, format, max_length, enumeration).

Each of the 60 mutations is built to trip exactly one targeted assertion on
one attribute of one record, and to leave every *other* assertion on that
same attribute passing, so the gate benchmark's unexpected-violation count
(see ``scripts/run_gate_benchmark.py``) is a real check, not a formality. The
isolation trick is simpler here than in the sibling
``business-rules-acceptance-criteria-pack`` repo, where mutations had to dodge
cross-*field* rules: because every assertion here is scoped to a single
``attribute_id`` (see ``app/db.py``'s EAV layout), a mutation can only ever
collide with another assertion on the *same* attribute, never a different
one. The candidate pools below (``_pure_*``) exist specifically to dodge
even that same-attribute collision, e.g. a max_length mutation is only drawn
from attributes that have no format and no enumeration to also trip.
"""

from __future__ import annotations

import random
import string
from dataclasses import dataclass

from app.generator import generate_file
from app.spec_loader import Attribute

FILE_TYPES = ("mk", "mi", "mo", "mw")


@dataclass(frozen=True)
class SeededViolation:
    file_type: str
    record_id: str
    attribute_id: str
    assertion_type: str  # "datatype" | "format" | "max_length" | "enumeration"


def _pure_datatype_pool(attributes: list[Attribute]) -> list[Attribute]:
    # Dates are a deliberate special case: a datatype mutation keeps the
    # right digit count (so the format assertion still passes) but uses an
    # invalid calendar value (month 13), so format and datatype can be
    # isolated even though every date attribute has a format. Every other
    # attribute is only included if it has neither a format nor an
    # enumeration: a numeric/string datatype mutation (garbage letters, or a
    # blank value) cannot be made to simultaneously fail its datatype check
    # and pass a format or enumeration check on the same attribute, so those
    # attributes are excluded here rather than produce a cascading
    # "unexpected" violation on the same (file, record, attribute).
    return [a for a in attributes
            if a.attribute_id != "S-07"
            and (a.datatype == "date" or (not a.format and not a.enumeration))]


def _pure_format_pool(attributes: list[Attribute]) -> list[Attribute]:
    # Numeric, has a format, no enumeration (so shortening a decimal digit
    # cannot incidentally also trip an enumeration check on the same value).
    return [a for a in attributes
            if a.datatype == "numeric" and a.format and not a.enumeration]


def _pure_maxlen_pool(attributes: list[Attribute]) -> list[Attribute]:
    # No format, no enumeration, and not a date (dates are fixed-width by
    # format in this spec, so lengthening one would also break its format
    # assertion).
    return [a for a in attributes
            if a.datatype != "date" and not a.format and not a.enumeration
            and a.attribute_id != "S-07"]


def _pure_enum_pool(attributes: list[Attribute]) -> list[Attribute]:
    return [a for a in attributes if a.enumeration]


def _mutate_datatype(attr: Attribute, rng: random.Random) -> str:
    if attr.datatype == "numeric":
        letters = "".join(rng.choice(string.ascii_uppercase) for _ in range(min(3, attr.max_length)))
        return letters
    if attr.datatype == "date":
        if attr.format == "MMDDCCYY":
            return f"13{rng.randint(1,28):02d}{rng.randint(2015,2026):04d}"
        return f"13{rng.randint(2015,2026):04d}"
    return ""  # string: blank trips "required field" datatype check


def _mutate_format(attr: Attribute, rng: random.Random, clean_value: str) -> str:
    int_part, _, dec_part = clean_value.partition(".")
    shortened_dec = dec_part[:-1] if len(dec_part) > 1 else dec_part
    return f"{int_part}.{shortened_dec}"


def _mutate_maxlen(attr: Attribute, rng: random.Random, clean_value: str) -> str:
    # The generator draws clean values of variable length up to max_length,
    # so a fixed-size append is not guaranteed to push a short clean value
    # over the limit; pad to at least max_length + 3 characters past it.
    overflow = max(3, (attr.max_length - len(clean_value)) + 3)
    if attr.datatype == "numeric":
        return clean_value + "".join(str(rng.randint(0, 9)) for _ in range(overflow))
    return clean_value + "".join(rng.choice(string.ascii_uppercase) for _ in range(overflow))


def _mutate_enum(attr: Attribute, rng: random.Random) -> str:
    if attr.datatype == "numeric" and attr.format:
        int_digits, dec_digits = (int(x) for x in attr.format.split("."))
        for _ in range(50):
            candidate = f"{rng.randint(0, (10**int_digits)-1)}.{rng.randint(0,(10**dec_digits)-1):0{dec_digits}d}"
            if candidate not in attr.enumeration:
                return candidate
        raise RuntimeError(f"could not find an off-enum numeric value for {attr.attribute_id}")
    # Generic branch: the candidate must respect the attribute's own
    # max_length (several enumerated indicators are single-character, e.g.
    # Y/N/9 flags) or it trips an unintended max_length violation on top of
    # the intended enumeration one.
    length = min(attr.max_length, 2) if attr.max_length >= 2 else attr.max_length
    pool = string.digits if attr.datatype == "numeric" else string.ascii_uppercase
    for _ in range(100):
        candidate = "".join(rng.choice(pool) for _ in range(length))
        if candidate not in attr.enumeration:
            return candidate
    raise RuntimeError(f"could not find an off-enum value for {attr.attribute_id}")


def _assign_groups(attributes: list[Attribute], seed: int) -> dict[str, list[tuple[Attribute, str]]]:
    rng = random.Random(seed)
    dt_pool = list(_pure_datatype_pool(attributes))
    fmt_pool = list(_pure_format_pool(attributes))
    maxlen_pool = list(_pure_maxlen_pool(attributes))
    enum_pool = list(_pure_enum_pool(attributes))
    rng.shuffle(dt_pool)
    rng.shuffle(fmt_pool)
    rng.shuffle(maxlen_pool)
    rng.shuffle(enum_pool)

    dt_targets = dt_pool[:15]
    fmt_targets = fmt_pool[:15]
    maxlen_targets = maxlen_pool[:15]
    enum_targets = enum_pool[:15]
    assert len(dt_targets) == 15, f"only {len(dt_targets)} datatype candidates available"
    assert len(fmt_targets) == 15, f"only {len(fmt_targets)} format candidates available"
    assert len(maxlen_targets) == 15, f"only {len(maxlen_targets)} max_length candidates available"
    assert len(enum_targets) == 15, f"only {len(enum_targets)} enumeration candidates available"

    all_targets = (
        [(a, "datatype") for a in dt_targets]
        + [(a, "format") for a in fmt_targets]
        + [(a, "max_length") for a in maxlen_targets]
        + [(a, "enumeration") for a in enum_targets]
    )
    rng.shuffle(all_targets)
    groups: dict[str, list[tuple[Attribute, str]]] = {ft: [] for ft in FILE_TYPES}
    for i, target in enumerate(all_targets):
        groups[FILE_TYPES[i % 4]].append(target)
    return groups


def inject_seeded_violations(attributes: list[Attribute], seed: int = 777,
                              n_records: int = 120):
    """Returns (files, expected): ``files`` maps file_type -> list of records
    (one clean file per file_type, each with 15 mutated records), ``expected``
    is the list of 60 SeededViolation tuples the gate benchmark checks for."""
    groups = _assign_groups(attributes, seed)
    by_id = {a.attribute_id: a for a in attributes}

    files: dict[str, list[dict]] = {}
    expected: list[SeededViolation] = []

    for file_type in FILE_TYPES:
        records = generate_file(attributes, file_type, seed=seed + hash(file_type) % 1000, n_records=n_records)
        rng = random.Random(seed + 1)
        targets = groups[file_type]
        # one distinct record per mutation, drawn without replacement
        record_indices = rng.sample(range(len(records)), len(targets))
        for (attr, assertion_type), rec_idx in zip(targets, record_indices):
            record = records[rec_idx]
            clean_value = record["fields"][attr.attribute_id]
            if assertion_type == "datatype":
                new_value = _mutate_datatype(attr, rng)
            elif assertion_type == "format":
                new_value = _mutate_format(attr, rng, clean_value)
            elif assertion_type == "max_length":
                new_value = _mutate_maxlen(attr, rng, clean_value)
            else:
                new_value = _mutate_enum(attr, rng)
            record["fields"][attr.attribute_id] = new_value
            expected.append(SeededViolation(
                file_type=file_type,
                record_id=record["record_id"],
                attribute_id=attr.attribute_id,
                assertion_type=assertion_type,
            ))
        files[file_type] = records

    assert len(expected) == 60, f"expected exactly 60 seeded violations, built {len(expected)}"
    assert len({(e.file_type, e.record_id, e.attribute_id) for e in expected}) == 60, \
        "each seeded violation must target a distinct (file, record, attribute)"
    return files, expected
