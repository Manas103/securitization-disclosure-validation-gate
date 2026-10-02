"""The spec-to-assertion compiler.

This is the genuinely new part of this repo relative to its sibling
(``business-rules-acceptance-criteria-pack``): instead of a human typing one
``Rule`` object per field, ``compile_assertions`` walks every ``Attribute``
parsed out of the published disclosure guide (see ``app/spec_loader.py``) and
*derives* one or more SQL assertions per attribute, mechanically, from the
attribute's own datatype, format, max_length and enumeration. Add an
attribute to ``spec/disclosure_spec.json`` and it gets assertions for free;
there is no second place to remember to add a check.

Every compiled assertion's SQL has the same shape: it runs against the
``observations`` table built by ``app/db.py`` (one row per
``(file_type, record_id, attribute_id, value)`` triple, see that module's
docstring for why the gate reshapes the wide pipe-delimited file into this
long form) and returns the ``(file_type, record_id, attribute_id, value)`` of
every observation of that one attribute that fails the check. A query that
returns zero rows means that assertion passed on everything currently loaded.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.spec_loader import Attribute

# Date formats actually used in the Security Level File table (S-04..S-76).
# Maps the guide's letter template to (digit-count regex, strptime pattern).
_DATE_FORMATS = {
    "MMCCYY": (r"^\d{6}$", "%m%Y"),
    "MMDDCCYY": (r"^\d{8}$", "%m%d%Y"),
}


@dataclass(frozen=True)
class Assertion:
    assertion_id: str
    attribute_id: str
    attribute_name: str
    assertion_type: str  # "datatype" | "format" | "max_length" | "enumeration"
    description: str
    sql: str


def _datatype_sql(attr: Attribute) -> str:
    if attr.datatype == "numeric":
        condition = "TRY_CAST(value AS DOUBLE) IS NULL"
    elif attr.datatype == "date":
        _, strptime_fmt = _DATE_FORMATS[attr.format]
        condition = f"TRY_STRPTIME(value, '{strptime_fmt}') IS NULL"
    else:  # string
        condition = "value IS NULL OR LENGTH(value) = 0"
    return (
        "SELECT file_type, record_id, attribute_id, value FROM observations "
        f"WHERE attribute_id = '{attr.attribute_id}' AND ({condition})"
    )


def _format_sql(attr: Attribute) -> str | None:
    if attr.format is None:
        return None
    if attr.datatype == "date":
        pattern, _ = _DATE_FORMATS[attr.format]
    elif attr.datatype == "numeric":
        int_digits, dec_digits = attr.format.split(".")
        pattern = rf"^\d{{1,{int_digits}}}\.\d{{{dec_digits}}}$"
    else:
        return None
    return (
        "SELECT file_type, record_id, attribute_id, value FROM observations "
        f"WHERE attribute_id = '{attr.attribute_id}' "
        f"AND NOT regexp_matches(value, '{pattern}')"
    )


def _max_length_sql(attr: Attribute) -> str:
    return (
        "SELECT file_type, record_id, attribute_id, value FROM observations "
        f"WHERE attribute_id = '{attr.attribute_id}' "
        f"AND LENGTH(value) > {attr.max_length}"
    )


def _enumeration_sql(attr: Attribute) -> str | None:
    if not attr.enumeration:
        return None
    in_list = ", ".join(f"'{code}'" for code in attr.enumeration)
    return (
        "SELECT file_type, record_id, attribute_id, value FROM observations "
        f"WHERE attribute_id = '{attr.attribute_id}' "
        f"AND value NOT IN ({in_list})"
    )


def compile_assertions(attributes: list[Attribute]) -> list[Assertion]:
    """Compiles every attribute into its datatype, format (if any), max_length,
    and enumeration (if any) assertions. Order is deterministic (attribute
    order from the spec, then datatype, format, max_length, enumeration) so a
    rerun of the compiler on an unchanged spec produces byte-identical SQL."""
    assertions: list[Assertion] = []
    for attr in attributes:
        assertions.append(Assertion(
            assertion_id=f"{attr.attribute_id}-DATATYPE",
            attribute_id=attr.attribute_id,
            attribute_name=attr.name,
            assertion_type="datatype",
            description=(
                f"{attr.attribute_id} ({attr.name}) must be a valid {attr.datatype} value."
            ),
            sql=_datatype_sql(attr),
        ))
        fmt_sql = _format_sql(attr)
        if fmt_sql is not None:
            assertions.append(Assertion(
                assertion_id=f"{attr.attribute_id}-FORMAT",
                attribute_id=attr.attribute_id,
                attribute_name=attr.name,
                assertion_type="format",
                description=(
                    f"{attr.attribute_id} ({attr.name}) must match the published "
                    f"format {attr.format}."
                ),
                sql=fmt_sql,
            ))
        assertions.append(Assertion(
            assertion_id=f"{attr.attribute_id}-MAXLEN",
            attribute_id=attr.attribute_id,
            attribute_name=attr.name,
            assertion_type="max_length",
            description=(
                f"{attr.attribute_id} ({attr.name}) must not exceed "
                f"{attr.max_length} characters."
            ),
            sql=_max_length_sql(attr),
        ))
        enum_sql = _enumeration_sql(attr)
        if enum_sql is not None:
            assertions.append(Assertion(
                assertion_id=f"{attr.attribute_id}-ENUM",
                attribute_id=attr.attribute_id,
                attribute_name=attr.name,
                assertion_type="enumeration",
                description=(
                    f"{attr.attribute_id} ({attr.name}) must be one of the "
                    f"published codes: {', '.join(attr.enumeration)}."
                ),
                sql=enum_sql,
            ))
    return assertions
