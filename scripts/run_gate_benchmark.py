"""Benchmark: 60 of 60 seeded violations caught and named by record and
attribute, 0 of 20 independently generated clean files falsely held.

    python scripts/run_gate_benchmark.py
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db
from app.compiler import compile_assertions
from app.engine import run_all
from app.generator import generate_file
from app.spec_loader import load_spec
from app.violations import inject_seeded_violations


def _load_and_run(conn, assertions, files: dict[str, list[dict]]):
    db.clear(conn)
    for file_type, records in files.items():
        db.load_file(conn, file_type, records)
    return run_all(conn, assertions)


def main() -> int:
    attributes = load_spec()
    assertions = compile_assertions(attributes)
    conn = db.connect()

    print("-- claim: 60 of 60 seeded violations caught, attributed to the correct record and attribute --")
    files, expected = inject_seeded_violations(attributes, seed=777, n_records=120)
    violations = _load_and_run(conn, assertions, files)
    found = {(v.file_type, v.record_id, v.attribute_id) for v in violations}
    expected_keys = {(e.file_type, e.record_id, e.attribute_id) for e in expected}
    caught = expected_keys & found
    unexpected = found - expected_keys
    print(f"seeded violations caught: {len(caught)} / {len(expected_keys)}")
    print(f"unexpected violations on the seeded-violation load: {len(unexpected)}")
    if unexpected:
        for file_type, record_id, attribute_id in sorted(unexpected):
            print(f"  unexpected: {file_type} {record_id} {attribute_id}")

    print()
    print("-- claim: 0 of 20 independently generated clean files falsely held --")
    false_holds = 0
    rng = random.Random(4242)
    for i in range(20):
        clean_seed = rng.randint(100000, 999999)
        clean_files = {
            ft: generate_file(attributes, ft, seed=clean_seed + j, n_records=80)
            for j, ft in enumerate(("mk", "mi", "mo", "mw"))
        }
        v = _load_and_run(conn, assertions, clean_files)
        if v:
            false_holds += len({(x.file_type, x.record_id) for x in v})
            print(f"  clean load {i} (seed {clean_seed}) produced {len(v)} unexpected violation(s)")
    print(f"false holds across 20 independent clean loads: {false_holds}")

    ok = len(caught) == len(expected_keys) and not unexpected and false_holds == 0
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
