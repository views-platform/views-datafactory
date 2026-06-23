# Class Intent Contract: ValidationResult

**Status:** Active
**Owner:** Simon Polichinel von der Maase
**Last reviewed:** 2026-06-23
**Related ADRs:** ADR-003, ADR-008, ADR-009

---

## 1. Purpose

> Structured outcome of validating a batch of raw events against a schema contract.

Carries the validation verdict (`valid`), event count, collected warnings and errors, schema snapshot, and content digest. Source-agnostic — the schema is injected by the caller. The caller decides whether to halt or continue based on the result.

---

## 2. Non-Goals (Explicit Exclusions)

- This class does **not** perform validation (that is `validate_events()`)
- This class does **not** decide what to do on failure (caller decides)
- This class does **not** know about specific data sources
- This class does **not** enforce immutability (mutable dataclass by design — populated incrementally during validation)

---

## 3. Responsibilities and Guarantees

- Carries a boolean `valid` flag: True if no fatal schema violations were found
- Carries `n_events`: the count of events that were validated
- Collects `warnings`: non-fatal issues including fatality bound violations (`best > high`, `low > best`, `best < 0`), coordinate range violations (lat outside [-90,90], lon outside [-180,180]), and duplicate event IDs
- Collects `errors`: fatal schema violations (missing required fields, type mismatches)
- Carries `schema_snapshot`: dict mapping field names to observed types
- Carries `content_digest`: SHA-256 digest computed from digest fields

---

## 4. Inputs and Assumptions

- `valid`: bool, overall validation verdict
- `n_events`: int, number of events validated
- `warnings`: list[str], non-fatal observations (default: empty)
- `errors`: list[str], fatal violations (default: empty)
- `schema_snapshot`: dict[str, str], observed field→type mapping (default: empty)
- `content_digest`: str, content digest of validated data (default: empty)

No `__post_init__` validation — fields are populated by `validate_events()`.

---

## 5. Outputs and Side Effects

- No side effects. Data container only.
- `valid` is True when `errors` is empty, False otherwise.

---

## 6. Failure Modes and Loudness

- No constructor failures (mutable dataclass, no validation).
- The class itself does not raise. It is the *output* of validation, not the validator.
- A `valid=False` result with non-empty `errors` is the "loud failure" mechanism (ADR-008).

---

## 7. Boundaries and Interactions

- Created exclusively by `validate_events()` in `event_validation.py`
- Consumed by source orchestrators (e.g., `fetch_ucdp_annual`) to decide halt/continue
- `content_digest` computed via `datafactory_provenance.compute_content_digest`
- Must not depend on any `datafactory_*` class other than provenance
- `event_validation.py` also exports `validate_dgp_assumptions()` (runs source-specific DGP checks, raises `ValueError` on violations) and `date_range()` (extracts min/max date strings from events). These are public API siblings, not consumers of `ValidationResult`

---

## 8. Examples of Correct Usage

```python
result = validate_events(events, REQUIRED_FIELDS, FIELD_TYPES)
if not result.valid:
    logger.error("Validation failed: %s", result.errors)
    raise ValueError(result.errors)
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: constructing directly instead of using validate_events
result = ValidationResult(valid=True, n_events=100)  # Skips actual validation
```

---

## 10. Test Alignment

- **Green:** Valid events produce `valid=True`, correct counts, non-empty digest
- **Beige:** Missing required fields produce `valid=False` with specific errors
- **Red:** Empty event list, type mismatches, malformed data

Tests in `tests/test_ucdp_annual.py` (via `validate_events`).

---

## End of Contract

This document defines the **intended meaning** of `ValidationResult`.

Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
