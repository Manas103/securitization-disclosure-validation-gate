"""Loads one or more simulated disclosure files into a fresh in-memory DuckDB
database, reshaped from the wide pipe-delimited layout into a single long
("EAV": entity-attribute-value) ``observations`` table:

    observations(file_type VARCHAR, record_id VARCHAR, attribute_id VARCHAR, value VARCHAR)

Why reshape at all. The real file is wide: one row per security, 87
pipe-delimited columns (S-01 .. S-99). A compiler that generates SQL
per-attribute against a wide table would need 87 differently-named columns
and 87 differently-shaped queries (``WHERE "S-01" ...``, ``WHERE "S-15" ...``),
because a column name cannot be a bind parameter. Reshaping into one row per
(record, attribute) first means ``app/compiler.py`` can emit the same four
query shapes for every attribute, with only the ``attribute_id`` and the
attribute's own rules substituted in; adding attribute #88 needs no new SQL
shape, just one more set of substituted queries. The cost is the reshape step
itself (``load_file`` below), which is a single, boring, well-tested loop.
"""

from __future__ import annotations

import duckdb

from app.spec_loader import Attribute


def connect() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(":memory:")
    conn.execute(
        "CREATE TABLE observations ("
        "file_type VARCHAR, record_id VARCHAR, attribute_id VARCHAR, value VARCHAR)"
    )
    return conn


def load_file(conn: duckdb.DuckDBPyConnection, file_type: str, records: list[dict]) -> None:
    """``records`` is a list of dicts, each ``{"record_id": ..., "fields": {attribute_id: value}}``.
    A missing or None field value is loaded as SQL NULL (a blank pipe-delimited
    column), not skipped, so a required field that is blank still gets a row
    to fail its datatype/max_length assertion against."""
    rows = []
    for rec in records:
        for attribute_id, value in rec["fields"].items():
            rows.append((file_type, rec["record_id"], attribute_id, value))
    conn.executemany(
        "INSERT INTO observations VALUES (?, ?, ?, ?)", rows
    )


def clear(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("DELETE FROM observations")


def field_order(attributes: list[Attribute]) -> list[str]:
    return [a.attribute_id for a in attributes]
