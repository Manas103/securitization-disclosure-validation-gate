from app.generator import generate_file
from app.restatement import diff_correction, generate_correction_batch
from app.spec_loader import load_spec


def test_restatement_diff_names_exactly_the_changed_fields():
    attributes = load_spec()
    by_id = {a.attribute_id: a for a in attributes}
    originals = generate_file(attributes, "mk", seed=10, n_records=50)
    originals_by_id = {r["record_id"]: r for r in originals}

    corrections, expected = generate_correction_batch(attributes, originals, seed=11, n_corrections=20)
    assert len(corrections) == 20

    for correction in corrections:
        original = originals_by_id[correction["supersedes_record_id"]]
        diffs = diff_correction(original, correction, by_id)
        found_ids = {d.attribute_id for d in diffs}
        assert found_ids == expected[correction["record_id"]]
        assert "S-07" not in found_ids


def test_restatement_diff_lineage_rejects_wrong_original():
    attributes = load_spec()
    by_id = {a.attribute_id: a for a in attributes}
    originals = generate_file(attributes, "mk", seed=20, n_records=10)
    corrections, _ = generate_correction_batch(attributes, originals, seed=21, n_corrections=2)

    wrong_original = originals[0]
    correction = corrections[1] if corrections[1]["supersedes_record_id"] != wrong_original["record_id"] else corrections[0]
    try:
        diff_correction(wrong_original, correction, by_id)
        assert False, "expected a lineage mismatch to raise"
    except ValueError:
        pass
