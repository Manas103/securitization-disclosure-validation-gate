"""Runs every compiled assertion against whatever is currently loaded into the
``observations`` table and names the exact (file, record, attribute) that
fails. Failing closed means: any row returned by any assertion's SQL is held,
by record and attribute, not just counted.
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb

from app.compiler import Assertion


@dataclass(frozen=True)
class Violation:
    assertion_id: str
    attribute_id: str
    attribute_name: str
    assertion_type: str
    file_type: str
    record_id: str
    value: str | None


def run_assertion(conn: duckdb.DuckDBPyConnection, assertion: Assertion) -> list[Violation]:
    rows = conn.execute(assertion.sql).fetchall()
    return [
        Violation(
            assertion_id=assertion.assertion_id,
            attribute_id=assertion.attribute_id,
            attribute_name=assertion.attribute_name,
            assertion_type=assertion.assertion_type,
            file_type=row[0],
            record_id=row[1],
            value=row[3],
        )
        for row in rows
    ]


def run_all(conn: duckdb.DuckDBPyConnection, assertions: list[Assertion]) -> list[Violation]:
    violations: list[Violation] = []
    for assertion in assertions:
        violations.extend(run_assertion(conn, assertion))
    return violations


def held_records(violations: list[Violation]) -> set[tuple[str, str]]:
    """The set of (file_type, record_id) pairs held by at least one violation,
    i.e. the records the gate refuses to publish as-is."""
    return {(v.file_type, v.record_id) for v in violations}
