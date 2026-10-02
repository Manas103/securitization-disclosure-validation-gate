from app import db
from app.compiler import compile_assertions
from app.engine import run_all
from app.spec_loader import load_spec
from app.violations import inject_seeded_violations


def test_exactly_60_seeded_violations_built():
    attributes = load_spec()
    _, expected = inject_seeded_violations(attributes, seed=777, n_records=120)
    assert len(expected) == 60


def test_seeded_violations_target_distinct_record_attribute_pairs():
    attributes = load_spec()
    _, expected = inject_seeded_violations(attributes, seed=777, n_records=120)
    keys = {(e.file_type, e.record_id, e.attribute_id) for e in expected}
    assert len(keys) == 60


def test_gate_catches_all_60_with_zero_unexpected():
    attributes = load_spec()
    assertions = compile_assertions(attributes)
    conn = db.connect()
    files, expected = inject_seeded_violations(attributes, seed=777, n_records=120)
    for file_type, records in files.items():
        db.load_file(conn, file_type, records)
    violations = run_all(conn, assertions)
    found = {(v.file_type, v.record_id, v.attribute_id) for v in violations}
    expected_keys = {(e.file_type, e.record_id, e.attribute_id) for e in expected}
    assert expected_keys <= found
    assert found == expected_keys, f"unexpected extra violations: {found - expected_keys}"
