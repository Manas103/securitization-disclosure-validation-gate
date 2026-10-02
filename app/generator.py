"""Deterministic synthetic security-level disclosure file generator.

This is simulated data: no real issuer, servicer, security, or loan is
represented here. Every value is built directly from the attribute's own
datatype, format, max_length, and enumeration in ``spec/disclosure_spec.json``,
so the generator is conformant with the spec by construction (a value is
produced only by code paths that already respect the attribute's own rules).
This is the same role ``app/generator.py`` plays in the sibling
``business-rules-acceptance-criteria-pack`` repo.

``generate_file`` produces one "clean" file's worth of records for a given
``file_type`` (``mk``, ``mi``, ``mo``, or ``mw``; see ``spec/disclosure_spec.json``
for what each means). Correction files (``mo``/``mw``) additionally force the
Security Data Correction Indicator (S-07) to ``Y``; daily issuance / monthly
factor files (``mk``/``mi``) force it to ``N``.
"""

from __future__ import annotations

import random
import string

from app.spec_loader import Attribute

_ALNUM = string.ascii_uppercase + string.digits


def _random_alnum(rng: random.Random, length: int) -> str:
    return "".join(rng.choice(_ALNUM) for _ in range(length))


def _generate_numeric(attr: Attribute, rng: random.Random) -> str:
    if attr.enumeration:
        return rng.choice(attr.enumeration)
    if attr.format:
        int_digits, dec_digits = (int(x) for x in attr.format.split("."))
        int_part = rng.randint(0, (10 ** int_digits) - 1)
        dec_part = rng.randint(0, (10 ** dec_digits) - 1)
        return f"{int_part}.{dec_part:0{dec_digits}d}"
    digits = max(1, attr.max_length)
    return str(rng.randint(0, (10 ** digits) - 1))


def _generate_date(attr: Attribute, rng: random.Random) -> str:
    month = rng.randint(1, 12)
    year = rng.randint(2015, 2026)
    if attr.format == "MMDDCCYY":
        day = rng.randint(1, 28)
        return f"{month:02d}{day:02d}{year:04d}"
    # MMCCYY
    return f"{month:02d}{year:04d}"


def _generate_string(attr: Attribute, rng: random.Random) -> str:
    if attr.enumeration:
        return rng.choice(attr.enumeration)
    length = rng.randint(1, min(attr.max_length, 12))
    return _random_alnum(rng, length)


def generate_value(attr: Attribute, rng: random.Random) -> str:
    if attr.datatype == "numeric":
        return _generate_numeric(attr, rng)
    if attr.datatype == "date":
        return _generate_date(attr, rng)
    return _generate_string(attr, rng)


def generate_record(attributes: list[Attribute], rng: random.Random,
                     record_id: str, correction_indicator: str = "N") -> dict:
    fields = {}
    for attr in attributes:
        if attr.attribute_id == "S-07":
            fields[attr.attribute_id] = correction_indicator
        else:
            fields[attr.attribute_id] = generate_value(attr, rng)
    return {"record_id": record_id, "fields": fields}


def generate_file(attributes: list[Attribute], file_type: str, seed: int,
                   n_records: int = 120) -> list[dict]:
    """Returns a list of records (see app/db.py's load_file for the shape).
    ``file_type`` controls only the record_id prefix and the Security Data
    Correction Indicator default; the field layout is identical for every
    file_type, per the guide's "file layouts are the same" statement."""
    rng = random.Random(seed)
    is_correction = file_type in ("mo", "mw")
    indicator = "Y" if is_correction else "N"
    records = []
    for i in range(n_records):
        record_id = f"{file_type}-{seed}-{i:04d}"
        records.append(generate_record(attributes, rng, record_id, indicator))
    return records
