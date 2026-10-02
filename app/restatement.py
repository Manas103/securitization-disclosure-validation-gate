"""Field-level restatement diffs for correction files.

The guide states that a correction file (``mo``/``mw``) shares the identical
layout with the original it supersedes, and carries the Security Data
Correction Indicator (S-07) set to ``Y``. What the guide does not hand you for
free is which fields actually changed: a reviewer staring at two 87-column
rows side by side has to find the difference themselves. ``diff_correction``
does that mechanically, field by field, against the exact original record a
correction supersedes (tracked via ``supersedes_record_id``, the lineage
pointer set when the correction was built), and reports only the fields that
actually moved.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.spec_loader import Attribute


@dataclass(frozen=True)
class FieldRestatement:
    attribute_id: str
    attribute_name: str
    old_value: str | None
    new_value: str | None


def generate_correction_batch(attributes: list[Attribute], originals: list[dict],
                               seed: int, n_corrections: int, max_changed_fields: int = 3):
    """Builds ``n_corrections`` correction records, each supersedes a distinct
    record drawn from ``originals``. Each correction changes 1 to
    ``max_changed_fields`` non-key fields to a new, still spec-conformant
    value (S-01/S-02 and S-07 are never chosen as a restated field: S-07 is
    always forced to 'Y' on a correction, and S-01/S-02 identify the security,
    not a restatable attribute). Returns (correction_records, expected), where
    ``expected`` maps record_id -> the set of attribute_ids that were actually
    changed, the ground truth ``diff_correction`` is checked against.
    """
    import random
    from app.generator import generate_value

    rng = random.Random(seed)
    restatable = [a for a in attributes if a.attribute_id not in ("S-01", "S-02", "S-07")]
    by_id = {a.attribute_id: a for a in attributes}

    chosen = rng.sample(originals, min(n_corrections, len(originals)))
    corrections = []
    expected: dict[str, set[str]] = {}

    for i, original in enumerate(chosen):
        new_fields = dict(original["fields"])
        n_changes = rng.randint(1, max_changed_fields)
        targets = rng.sample(restatable, n_changes)
        changed_ids = set()
        for attr in targets:
            old_value = new_fields[attr.attribute_id]
            # redraw until the new value actually differs from the old one
            for _ in range(20):
                candidate = generate_value(attr, rng)
                if candidate != old_value:
                    break
            new_fields[attr.attribute_id] = candidate
            changed_ids.add(attr.attribute_id)
        new_fields["S-07"] = "Y"
        record_id = f"correction-{seed}-{i:04d}"
        corrections.append({
            "record_id": record_id,
            "supersedes_record_id": original["record_id"],
            "fields": new_fields,
        })
        expected[record_id] = changed_ids

    return corrections, expected


def diff_correction(original: dict, correction: dict,
                     attributes_by_id: dict[str, Attribute]) -> list[FieldRestatement]:
    """Compares a correction record against the exact original record it
    names in ``supersedes_record_id`` and returns one FieldRestatement per
    field that actually changed. S-07 (the correction indicator itself) is
    excluded: it is expected to flip on every correction and is not part of
    the restated content."""
    if correction.get("supersedes_record_id") != original["record_id"]:
        raise ValueError(
            f"correction {correction['record_id']} does not supersede "
            f"original {original['record_id']}"
        )
    diffs = []
    for attribute_id, new_value in correction["fields"].items():
        if attribute_id == "S-07":
            continue
        old_value = original["fields"].get(attribute_id)
        if old_value != new_value:
            attr = attributes_by_id[attribute_id]
            diffs.append(FieldRestatement(
                attribute_id=attribute_id,
                attribute_name=attr.name,
                old_value=old_value,
                new_value=new_value,
            ))
    return diffs
