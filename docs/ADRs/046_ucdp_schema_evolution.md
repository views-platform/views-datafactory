
# ADR-046: UCDP Schema Evolution Strategy

**Status:** Accepted
**Date:** 2026-06-19
**Deciders:** Simon (data engineer)
**Consulted:** Risk register C-36, C-37, C-45

---

## Context

UCDP provides no schema versioning or schema contract. The API returns whatever fields the current dataset version has. Three risk register entries track the consequences:

- **C-36 (Tier 4):** The UCDP API has no schema version header or endpoint. We cannot detect schema changes before fetching data.
- **C-37 (Tier 4):** `date_prec=5` semantics (sub-national, below admin-2) are hardcoded in our pipeline without reference to a codebook. If UCDP redefines date precision codes, we process silently wrong data.
- **C-45 (Tier 4):** Column additions are handled by `promote_options="default"`, but column removals and renames have no explicit strategy.

The existing defenses are functional but undocumented:

1. `REQUIRED_FIELDS` (13 fields) in `ucdp_annual.py` L58-73 fail-loud on missing fields at harvest time.
2. `FIELD_TYPES` in `ucdp_annual.py` L75-89 fail-loud on type changes.
3. `promote_options="default"` in `ucdp.py` L409-410 handles column additions by filling nulls.
4. Schema fingerprints are computed and recorded in the provenance ledger (`ucdp.py` L485-503) but never compared across runs.
5. `tests/test_schema_evolution.py` covers addition, removal, mixed schemas, and fingerprint change (4 tests).

This ADR documents the strategy so the defenses are legible and the remaining gaps are explicit.

---

## Decision

Schema defense for UCDP uses a **fail-loud + provenance fingerprint** approach. No schema registry. No JSON Schema contracts.

### In scope

1. **Column additions:** Handled by `pa.concat_tables(promote_options="default")`. New columns from later UCDP versions appear in the consolidated store with null values for older rows. Tested in `test_schema_evolution.py::test_new_column_added_in_later_version`.

2. **Column removals:** If a column present in old data disappears from new data, old rows retain the column value and new rows get null. This is the natural behavior of `promote_options="default"`. Tested in `test_schema_evolution.py::test_column_removed_in_later_version`.

3. **Column renames:** Treated as a simultaneous removal and addition. The old column persists (nulls for new rows), and the new column appears (nulls for old rows). This is an accepted risk: no automated detection, but the fingerprint will change and the ledger records both states.

4. **`date_prec` semantics:** The set {1, 2, 3, 4, 5} is hardcoded. New values fail-loud via DGP validation checks (`_check_date_prec_range` in `ucdp_annual.py`). If UCDP introduces `date_prec=6`, the pipeline raises `ValueError` rather than processing unknown semantics.

5. **`type_of_violence` semantics:** The set {1, 2, 3} (state-based, non-state, one-sided) is hardcoded. New values fail-loud via DGP validation.

6. **Schema fingerprint:** A SHA-256 fingerprint of sorted column names is recorded in every consolidation ledger entry (`schema_fingerprint` field). This provides a forensic record of when schemas changed.

### Out of scope

- **Automated fingerprint comparison across runs.** The fingerprint is recorded but not compared programmatically. A future sprint should add a `_check_schema_drift()` function that compares the current fingerprint against the previous ledger entry and logs a warning on change. This is the recommended next step.
- **Semantic versioning of source schemas.** UCDP does not publish schema versions; we cannot version what the source does not version.
- **Automated codebook parsing.** UCDP publishes a PDF codebook. Automated extraction is not cost-effective for one source.

---

## Rationale

1. **Fail-loud is cheaper than fail-safe.** A schema registry or contract system requires ongoing maintenance. Fail-loud via `REQUIRED_FIELDS` and DGP validation catches the same problems at the moment of ingestion, with zero maintenance cost beyond updating the field list when UCDP legitimately adds fields.

2. **`promote_options="default"` is the right default.** PyArrow's union-of-schemas behavior matches our consolidation semantics: preserve all data, fill gaps with null. This is exactly how a system of record should handle schema evolution (Kleppmann, DDIA 2nd ed., Ch.4 pp.112-127).

3. **Provenance fingerprinting provides the audit trail.** Even without automated comparison, the fingerprint in the ledger enables post-hoc analysis. If a downstream model produces unexpected results, we can check whether the schema changed at a specific consolidation timestamp.

4. **Column renames are rare and detectable.** UCDP has maintained stable column names across 25+ annual releases. A rename would show up as a fingerprint change and a new `REQUIRED_FIELDS` violation (fail-loud). The risk is real but the probability is low.

---

## Considered Alternatives

### Alternative A: Confluent-style schema registry

- **Pros:** Automated compatibility checking, schema versioning, consumer contracts.
- **Cons:** Infrastructure overhead (needs a registry service), maintenance cost, overkill for 10 sources that each publish once per year.
- **Reason for rejection:** The benefit does not justify the cost at our scale. All 10 data sources publish schemas implicitly via their data; none publish explicit schema contracts.

### Alternative B: JSON Schema contract per source

- **Pros:** Machine-readable schema definitions, automated validation, diff-able.
- **Cons:** Requires writing and maintaining a JSON Schema for each source (60+ fields for UCDP). Schema changes require manual contract updates. The existing `REQUIRED_FIELDS` + `FIELD_TYPES` pattern provides the same validation with less indirection.
- **Reason for rejection:** The `REQUIRED_FIELDS` + `FIELD_TYPES` + DGP checks pattern is simpler and already tested.

### Alternative C: Pin expected schema per version

- **Pros:** Detect any column change immediately.
- **Cons:** Every legitimate UCDP release would require a code change to update the pinned schema. This creates friction without adding safety — the `promote_options="default"` behavior already handles additions gracefully.
- **Reason for rejection:** Too rigid. Additions should be handled gracefully; only removals and type changes warrant fail-loud.

---

## Consequences

### Positive

- All three risk register entries (C-36, C-37, C-45) are resolved with documented rationale.
- The pipeline's schema defenses are legible to new developers via this ADR.
- DGP validation provides fail-loud on semantic changes (`date_prec`, `type_of_violence`).
- The provenance ledger records schema evolution history for forensic analysis.

### Negative

- Column renames are not detected automatically. A rename to a required field triggers a fail-loud, but a rename to a non-required field is silently absorbed. This is an accepted risk.
- Schema fingerprint comparison is manual (ledger inspection). Automated comparison is deferred.

---

## Implementation Notes

The defenses documented here are already implemented:

| Defense | Location | Mechanism |
|---------|----------|-----------|
| Required field check | `ucdp_annual.py` L58-73 | `REQUIRED_FIELDS` → `validate_events()` |
| Type check | `ucdp_annual.py` L75-89 | `FIELD_TYPES` → `validate_events()` |
| Column addition | `ucdp.py` L409-410 | `promote_options="default"` |
| Schema fingerprint | `ucdp.py` L485-503 | SHA-256 of sorted column names |
| DGP semantic checks | `ucdp_annual.py` | `UCDP_DGP_CHECKS` → `validate_dgp_assumptions()` |

**Recommended follow-up:** Add `_check_schema_drift()` to the consolidation path that compares the current schema fingerprint against the most recent ledger entry. Log a warning on change. This is a natural extension of the existing fingerprint infrastructure.

---

## Validation & Monitoring

- `tests/test_schema_evolution.py` (4 tests) validates addition, removal, mixed-schema, and fingerprint change scenarios.
- DGP validation tests (in `tests/test_dgp_validation.py`) validate semantic checks for `date_prec` and `type_of_violence`.
- Failure mode: if UCDP removes a required field, `validate_events()` raises immediately. No silent processing.
- Failure mode: if UCDP adds a new `date_prec` value, `_check_date_prec_range()` raises `ValueError` immediately.

---

## Open Questions

- Should schema fingerprint comparison be implemented as a warning (log only) or a gate (fail-loud on change)? A warning is recommended: schema changes are often legitimate (new fields in a new UCDP release), and a gate would require manual approval for every release.
- Should we track field-level schema diffs (not just fingerprint change)? Deferred: the current fingerprint is sufficient for forensic analysis; field-level diffs can be computed from the `schema_columns` lists in the ledger.

---

## References

- Risk register: C-36, C-37, C-45
- ADR-045: Data soundness invariants
- `tests/test_schema_evolution.py`: Schema evolution test suite
- `src/datafactory_harvester/sources/ucdp_annual.py`: `REQUIRED_FIELDS`, `FIELD_TYPES`
- `src/datafactory_consolidation/consolidators/ucdp.py`: `promote_options`, schema fingerprint
- Kleppmann, M. (2026). *Designing Data-Intensive Applications*, 2nd ed., Ch.4: Encoding and Evolution
- GitHub issue: #209
