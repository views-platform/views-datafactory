# Class Intent Contract: AcledConfig

**Status:** Active
**Owner:** Simon Polichinel von der Maase
**Last reviewed:** 2026-05-02
**Related ADRs:** ADR-009, ADR-012, ADR-026

---

## 1. Purpose

> Immutable configuration for fetching ACLED event data from the ACLED API.

Separates harvest transport and storage concerns from credential management (ADR-026) and analysis. Contains year range, event type scope, API transport parameters, and storage paths.

---

## 2. Non-Goals (Explicit Exclusions)

- This class does **not** store or resolve credentials (that is `get_acled_credentials`)
- This class does **not** manage OAuth2 token state (that is `_TokenState`)
- This class does **not** validate path existence (directories may not exist yet)
- This class does **not** perform any I/O or network access
- This class does **not** know about consolidation, viewpoints, or compilation

---

## 3. Responsibilities and Guarantees

- Guarantees immutability (frozen dataclass)
- Guarantees all parameters are valid after construction (`__post_init__` validation)
- Guarantees `end_year >= start_year`
- Guarantees `page_size >= 1`
- Guarantees `max_retries >= 1`
- Guarantees `page_delay > 0`
- Guarantees `timeout >= 1`
- Guarantees all `event_types` are members of `ALL_EVENT_TYPES`

---

## 4. Inputs and Assumptions

- `start_year`: int, first year of data range (default: `1997`)
- `end_year`: int, last year of data range (default: `2025`)
- `event_types`: tuple of event type strings, subset of `ALL_EVENT_TYPES` (default: all 6 types)
- `api_url`: str, ACLED API base URL
- `token_url`: str, ACLED OAuth2 token endpoint
- `page_size`: int, >= 1, records per API page (default: `5000`)
- `timeout`: int, >= 1, HTTP request timeout in seconds (default: `60`)
- `max_retries`: int, >= 1, retry attempts (default: `3`)
- `page_delay`: float, > 0, seconds between pages (default: `2.0`)
- `data_dir`: Path, output directory for Parquet snapshots
- `ledger_path`: Path, provenance ledger location

Assumptions not met cause immediate `ValueError`.

---

## 5. Outputs and Side Effects

- No side effects. Pure configuration container.
- No derived properties or computed fields.

---

## 6. Failure Modes and Loudness

- `ValueError` on `end_year < start_year`
- `ValueError` on `page_size < 1`
- `ValueError` on `max_retries < 1`
- `ValueError` on `page_delay <= 0`
- `ValueError` on `timeout < 1`
- `ValueError` on unknown event type not in `ALL_EVENT_TYPES`
- `AttributeError` on any attempt to mutate fields (frozen)

All failures are immediate and loud. No silent fallbacks.

---

## 7. Boundaries and Interactions

- Used by `fetch_acled` as the sole configuration input
- Storage paths consumed by `save_event_snapshot` and `append_ledger_entry`
- Must not depend on any other `datafactory_*` config class
- Registered in the source registry via `register_source("acled", ...)`

---

## 8. Examples of Correct Usage

```python
cfg = AcledConfig()  # Full range, all event types
cfg = AcledConfig(start_year=2020, end_year=2024)
cfg = AcledConfig(event_types=("Battles", "Riots"))
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: end_year before start_year
AcledConfig(start_year=2025, end_year=2020)  # ValueError

# WRONG: unknown event type
AcledConfig(event_types=("Combat",))  # ValueError

# WRONG: zero page size
AcledConfig(page_size=0)  # ValueError
```

---

## 10. Test Alignment

- **Green:** Default construction, custom parameters, event type validation
- **Beige:** Inverted year range, zero page_size, zero retries, negative page_delay, zero timeout, unknown event type
- **Red:** Mutation attempt (frozen enforcement), malformed API responses, token endpoint failures

Tests in `tests/test_acled_harvester.py`.

---

## End of Contract

This document defines the **intended meaning** of `AcledConfig`.

Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
