# Securitization Disclosure Validation and Correction Gate

A compiler that turns Freddie Mac's real, published Multifamily Disclosure
Guide into 227 executable field-level assertions over datatype, format, max
length and enumeration, a gate that holds a simulated disclosure file at the
exact record and attribute that breaks one of them, and a field-level
restatement diff for correction files. Python, SQL (DuckDB), and openpyxl for
a non-SQL exception pack. Every number below was measured on this machine,
not targeted: 60 of 60 seeded violations were caught and attributed to the
correct record and attribute, 0 of 20 independently generated clean files
were falsely held, and every one of 40 generated correction records produced
a restatement diff naming exactly the fields that changed.

## Why this exists

A disclosure validation rule usually starts life as a row in a PDF table (an
attribute ID, a definition, a data type, a format, a max length) and ends as
someone's hand-typed check, and the two drift apart the moment the guide is
revised and the check is not. This project collapses that gap the other
direction from its sibling `business-rules-acceptance-criteria-pack`: instead
of a human authoring one `Rule` per field, `app/compiler.py` derives every
assertion mechanically from an `Attribute` parsed out of the actual guide.
Add an attribute to the spec and it gets a datatype check, a max-length
check, and (where the guide declares one) a format check and an enumeration
check, for free, with no second place to remember to add logic. On top of
that, disclosure files in this business are routinely superseded: a published
record can later be corrected, and a disclosure team needs to know, instantly
and precisely, what changed.

## Honest framing, up front

- **This is simulated disclosure file data, not a connection to any real
  issuance.** `app/generator.py` generates every file below from a fixed
  seed; no real security, loan, or issuer is represented.
- **The field specification is real where it says it is, and nowhere else.**
  `spec/disclosure_spec.json` was built by downloading the actual Multifamily
  Disclosure Guide PDF (version 1.11, effective 2025-10-02,
  `https://capitalmarkets.freddiemac.com/mbs/docs/multifamily_disclosure_guide.pdf`)
  and extracting the Security Level File attribute table with pdfplumber's
  `extract_tables()` (`pdftotext -layout` was tried first and rejected: the
  table's wrapped multi-line cells came out misaligned across columns). 98
  attribute rows (S-01 through S-99) were found in the real table; 87 of them
  had a complete, unambiguous Data Type / Format / Max Length triple in the
  same extracted row and are used here verbatim, attribute ID, name,
  definition, data type, format, max length, and enumeration all taken
  directly from the guide. The other 11 (S-31, S-32, S-84 through S-91) had a
  blank Data Type/Max Length cell in the extraction because the source PDF
  visually merges that cell across an adjacent attribute's taller definition
  text; rather than guess at a value the guide does not cleanly state in a
  machine-extractable way, those 11 were dropped. `spec/disclosure_spec.json`
  records this `extraction_method` verbatim so the provenance of every field
  is auditable.
- **The four file types this gate validates (`mk`, `mi`, `mo`, `mw`) share one
  layout, per the guide's own Timing and Frequency of Data table**: daily
  issuance (`mk`), its correction (`mo`), monthly factor (`mi`), and its
  correction (`mw`) are all the same 87-plus-attribute Security Level File
  shape, which is why one compiled assertion set validates all four.
- **DuckDB, in-memory, not a managed database service.** Every load lives in
  a fresh `:memory:` DuckDB connection (`app/db.py`); there is no server to
  stand up.
- **Machine and toolchain.** 16 logical cores, Windows 11 Home, Python
  3.12.10, DuckDB 1.5.5, openpyxl 3.1.5, pytest 9.1.0.

## Architecture

```
spec/
  disclosure_spec.json   87 real attributes extracted from the Multifamily
                          Disclosure Guide PDF, plus extraction_method
                          disclosing exactly how and what was dropped.
app/
  spec_loader.py   the only code that reads the spec file; parses it into
                   Attribute objects.
  compiler.py      derives one or more SQL assertions per Attribute
                   (datatype, format, max_length, enumeration), 227 total.
  generator.py     deterministic synthetic file generator, conformant to the
                   spec by construction.
  violations.py    injects exactly 60 seeded violations (15 per file type,
                   spread evenly across the four assertion types), each
                   isolated so it trips exactly its own targeted assertion.
  restatement.py   builds correction records that supersede a named original
                   record, and diffs a correction against that exact
                   original field by field.
  db.py            reshapes wide pipe-delimited-style records into a long
                   (file_type, record_id, attribute_id, value) observations
                   table, see below for why.
  engine.py         runs every compiled assertion and names the exact
                   (file, record, attribute) that fails.
scripts/
  run_gate_benchmark.py        60-seeded-violation catch rate, 20 clean files
  run_restatement_check.py     field-level restatement diff accuracy
  generate_exception_pack.py   the one command that (re)writes
                                docs/exception_pack.xlsx
tests/           13 pytest tests (spec/compiler shape, generator conformance,
                 seeded-violation catch rate, restatement diff accuracy)
```

### Why the observations table is long (one row per attribute), not wide

A real Security Level File record is wide: one row per security, 87-plus
pipe-delimited columns. A compiler that generated SQL against a wide table
would need 87 differently-named columns and 87 differently-shaped queries,
because a column name cannot be a bind parameter. `app/db.py` reshapes every
loaded record into `observations(file_type, record_id, attribute_id, value)`
first, so `app/compiler.py` can emit the same four query shapes
(`WHERE attribute_id = ?`) for every attribute, substituting only the
attribute's own id and rules. Adding attribute 88 needs no new SQL shape.

### Why the compiler derives assertions instead of a human writing one per field

The sibling repo, `business-rules-acceptance-criteria-pack`, pairs each
business rule's plain-language text with its enforcing SQL on the same
object, so the two cannot drift apart, but a human still writes each pairing
by hand. That does not scale to a published field specification with
dozens of attributes, each carrying up to four independent properties
(datatype, format, max length, enumeration). `app/compiler.py` instead
treats the specification itself as the source of truth: `compile_assertions`
is a pure function from `Attribute` to `Assertion`, so the entire 227-
assertion catalog is a deterministic consequence of `disclosure_spec.json`,
re-derivable byte-for-byte on every run (`test_compiler_is_deterministic`).

### Why seeded-violation isolation is simpler here than in the sibling repo

In `business-rules-acceptance-criteria-pack`, seeded mutations had to dodge
cross-*field* rules (changing `quantity` could incidentally break a rule
about `principal_amount`). Here, every assertion is scoped to a single
`attribute_id` by construction (the EAV layout above), so a mutation can only
ever collide with another assertion on the *same* attribute, never a
different one. `app/violations.py`'s `_pure_*` candidate pools exist
specifically to dodge even that narrower, same-attribute collision (for
example, a max_length mutation is only drawn from attributes with no format
and no enumeration to also trip).

### Why the restatement diff needs an explicit lineage pointer, not a key match

A correction record's own `record_id` is not the same as the record it
supersedes; a disclosure correction file does not reuse the original's
identifier. `app/restatement.py` tracks lineage explicitly via a
`supersedes_record_id` field set when the correction is built, and
`diff_correction` refuses (raises `ValueError`) if asked to diff a correction
against a record it does not actually supersede, rather than silently
comparing the wrong pair.

## Validation

### Gate benchmark (60 seeded violations, 20 clean files)

```
$ python scripts/run_gate_benchmark.py
-- claim: 60 of 60 seeded violations caught, attributed to the correct record and attribute --
seeded violations caught: 60 / 60
unexpected violations on the seeded-violation load: 0

-- claim: 0 of 20 independently generated clean files falsely held --
false holds across 20 independent clean loads: 0
```

Full output: `docs/gate_benchmark_output.txt`.

### Restatement diff check (40 correction records)

```
$ python scripts/run_restatement_check.py
-- claim: correction files emit a field-level restatement diff naming exactly the changed fields --
correction records with an exact restatement diff: 40 / 40

example restatement diff (first correction record):
  S-54 (Interest Rate Adjustment Frequency): '565' -> '955'
  lineage: correction-99-0000 supersedes mk-2024-0051
```

Full output: `docs/restatement_check_output.txt`.

### Exception pack generation (one command)

```
$ python scripts/generate_exception_pack.py
wrote .../docs/exception_pack.xlsx (16479 bytes)
Assertion Catalog: 227 rows
Exceptions Detail: 60 rows
Summary By File: 4 rows
```

Full output: `docs/exception_pack_generation_output.txt`. The committed
`docs/exception_pack.xlsx` (16 KB) is this exact run: an "Assertion Catalog"
sheet (227 rows), an "Exceptions Detail" sheet (60 rows, one per caught
violation on the seeded-violation demo load), and a "Summary By File" sheet
(4 rows), every sheet flat and pivot-ready.

### Tests

13 pytest tests: the spec's real-attribute shape and uniqueness, the
compiler's 140+ assertion count and deterministic output, generator
conformance to every compiled assertion on a clean file, the 60-seeded-
violation set's shape and exact catch rate, and the restatement diff's
exactness and lineage-mismatch guard.

```
$ python -m pytest tests -q
.............                                                           [100%]
13 passed in 7.86s
```

Full transcript: `docs/test_output.txt`.

## Findings

### The real PDF's attribute table could not be fully machine-extracted, and the honest fix was to drop the ambiguous rows rather than guess

**Symptom.** The first extraction pass over the real guide PDF using
`pdftotext -layout` produced a Security Level File table where several
attributes' Data Type, Format, and Max Length values were shifted into the
wrong row.

**Wrong hypothesis first.** The first guess was a parsing bug in how the
plain-text table was split into columns by whitespace width.

**The measurement that discriminated.** Re-extracting with `pdfplumber`'s
`extract_tables()`, which uses the PDF's actual cell boundaries rather than
inferring columns from whitespace, produced correctly aligned rows for most
attributes, but 11 attributes (S-31, S-32, S-84 through S-91) still came back
with a blank Data Type/Max Length cell. Inspecting the PDF directly showed
why: those attributes have an unusually tall, multi-line Definition cell, and
the PDF's rendering visually merges the Data Type/Format/Max Length cell of
the row below into the taller row above, so that cell is empty in the
boundary-accurate extraction, not wrong.

**Root cause.** A PDF table layout issue in the source document itself, not
a parser bug: some attribute rows are taller than one line of text, and the
visual rendering does not keep every cell's content aligned with its own row
boundary for those attributes.

**Fix.** Rather than infer a datatype, format, or max length for the 11
affected attributes (which would make the spec silently less authoritative
than it claims to be), they were excluded from `disclosure_spec.json`
entirely, and `extraction_method` records exactly which 11 and why. The 87
remaining attributes compile to 227 assertions, comfortably over the 140+
claim even with 11 real attributes deliberately left out.

**Why the method mattered.** A specification that silently guessed at 11
fields would have been indistinguishable, from the outside, from one that
extracted all 98 cleanly. Recording the extraction method and the exact drop
list in the spec file itself is what makes "compiled from a published
disclosure file specification" a checkable claim rather than an assertion.

## Measured results

16 logical cores, Windows 11 Home, Python 3.12.10, DuckDB 1.5.5.

| Metric | Measured | Claim |
|---|---|---|
| **Field-level assertions** | **227**, from 87 real extracted attributes | 140+ field-level assertions over datatype, format, max length and enumeration |
| Compiled from a published spec | 87/87 attributes sourced verbatim from the real guide PDF; 11 ambiguous rows disclosed and dropped | compiled from a published disclosure file specification |
| **Seeded violations caught, attributed by record and attribute** | **60 / 60**, 0 unexpected | 60 of 60 seeded violations failed closed on the correct record and attribute |
| **False holds, 20 clean files** | **0** | 0 of 20 clean files were falsely held |
| Restatement diff exactness | 40 / 40 correction records diffed to exactly the changed fields | correction files emitted a field-level restatement diff |
| Exception pack regeneration | 1 command, 3 sheets (227 + 60 + 4 rows) | Excel exception pack for a non-SQL reviewer |

## Building and running

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

python -m pytest tests -q                       # docs/test_output.txt
python scripts/run_gate_benchmark.py            # docs/gate_benchmark_output.txt
python scripts/run_restatement_check.py         # docs/restatement_check_output.txt
python scripts/generate_exception_pack.py       # docs/exception_pack.xlsx
```

## Sibling comparison

[`business-rules-acceptance-criteria-pack`](https://github.com/Manas103/business-rules-acceptance-criteria-pack)
is this portfolio's other rule-object-to-assertion gate (32 of 32 seeded
violations caught and attributed, 0 of 20 clean loads falsely failed). That
repo's 32 rules are hand-authored, one `Rule` object at a time, against a
simulated brokerage domain with no published specification behind it. This
repo answers a different question: given a real, published field
specification with dozens of attributes, can the assertion catalog itself be
a derived artifact rather than a hand-maintained one. Both repos reuse the
same core idea (the rule and its enforcement live on one object so they
cannot drift), but here that object is the output of a compiler, not a
human's dataclass literal, and this repo adds correction-file handling with
a field-level restatement diff and explicit lineage, which the sibling does
not have because its domain has no concept of a superseding record.

## Limitations

- **87 of the real guide's 98 Security Level File attributes are covered.**
  The 11 dropped attributes (S-31, S-32, S-84 through S-91) are a genuine
  PDF-extraction gap, not a design choice; see Findings.
- **The format assertion covers two patterns (`MMCCYY`/`MMDDCCYY` dates and
  `digits.decimals` numeric formats)**, the formats actually present among
  the 87 extracted attributes; a future attribute using a different format
  string would need a new branch in `app/compiler.py`'s `_format_sql`.
- **The restatement diff compares two records already in hand**; it does not
  itself search a file for which original record a correction's
  `supersedes_record_id` refers to across a multi-file corpus, that lookup is
  the caller's responsibility (`run_restatement_check.py` does it with a
  simple dict).
- **The Excel exception pack reflects a single demo run** (the 60-seeded-
  violation load), not a time series of production exceptions.
