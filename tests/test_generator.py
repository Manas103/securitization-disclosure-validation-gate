from app import db
from app.compiler import compile_assertions
from app.engine import run_all
from app.generator import generate_file
from app.spec_loader import load_spec


def test_clean_file_conforms_to_every_assertion():
    attributes = load_spec()
    assertions = compile_assertions(attributes)
    conn = db.connect()
    records = generate_file(attributes, "mk", seed=1, n_records=150)
    db.load_file(conn, "mk", records)
    violations = run_all(conn, assertions)
    assert violations == []


def test_correction_file_forces_s07_to_y():
    attributes = load_spec()
    records = generate_file(attributes, "mo", seed=2, n_records=10)
    assert all(r["fields"]["S-07"] == "Y" for r in records)


def test_daily_file_forces_s07_to_n():
    attributes = load_spec()
    records = generate_file(attributes, "mk", seed=3, n_records=10)
    assert all(r["fields"]["S-07"] == "N" for r in records)


def test_generation_is_seed_reproducible():
    attributes = load_spec()
    a = generate_file(attributes, "mk", seed=55, n_records=20)
    b = generate_file(attributes, "mk", seed=55, n_records=20)
    assert a == b
