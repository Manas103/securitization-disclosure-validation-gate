"""Benchmark: every correction file emits a field-level restatement diff that
names exactly the fields that changed, no more and no fewer.

    python scripts/run_restatement_check.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.generator import generate_file
from app.restatement import diff_correction, generate_correction_batch
from app.spec_loader import load_spec


def main() -> int:
    attributes = load_spec()
    by_id = {a.attribute_id: a for a in attributes}
    originals = generate_file(attributes, "mk", seed=2024, n_records=100)
    originals_by_id = {r["record_id"]: r for r in originals}

    corrections, expected = generate_correction_batch(attributes, originals, seed=99, n_corrections=40)

    print("-- claim: correction files emit a field-level restatement diff naming exactly the changed fields --")
    exact_matches = 0
    for correction in corrections:
        original = originals_by_id[correction["supersedes_record_id"]]
        diffs = diff_correction(original, correction, by_id)
        found_ids = {d.attribute_id for d in diffs}
        expected_ids = expected[correction["record_id"]]
        if found_ids == expected_ids:
            exact_matches += 1
        else:
            print(f"  MISMATCH {correction['record_id']}: found {found_ids}, expected {expected_ids}")
    print(f"correction records with an exact restatement diff: {exact_matches} / {len(corrections)}")

    print()
    print("example restatement diff (first correction record):")
    first = corrections[0]
    original = originals_by_id[first["supersedes_record_id"]]
    for d in diff_correction(original, first, by_id):
        print(f"  {d.attribute_id} ({d.attribute_name}): '{d.old_value}' -> '{d.new_value}'")
    print(f"  lineage: {first['record_id']} supersedes {first['supersedes_record_id']}")

    return 0 if exact_matches == len(corrections) else 1


if __name__ == "__main__":
    raise SystemExit(main())
