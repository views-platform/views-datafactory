# Class Intent Contract: AcledViewpointConfig

**Status:** Active
**Owner:** Simon Polichinel von der Maase
**Last reviewed:** 2026-05-02
**Related ADRs:** ADR-009, ADR-012, ADR-014

---

## 1. Purpose

> Immutable configuration for building an ACLED viewpoint from a consolidated event store.

Simpler than `ViewpointConfig` — no survivorship or distribution strategies. Carries consolidated store path, output path, optional event type filter, and version tag.

---

## 2. Non-Goals (Explicit Exclusions)

- This class does **not** implement survivorship strategies (ACLED has one source type)
- This class does **not** implement temporal distribution (daily events map 1:1 to months)
- This class does **not** validate that the consolidated store exists (checked at build time)
- This class does **not** validate event type filter values against known types
- This class does **not** know about the harvester, consolidation, or compilation

---

## 3. Responsibilities and Guarantees

- Guarantees immutability (frozen dataclass)
- Guarantees `version` is non-empty
- Carries `consolidated_path`: source event store (required, no default)
- Carries `output_path`: viewpoint Parquet destination
- Carries `ledger_path`: viewpoint provenance ledger destination
- Carries `event_type_filter`: optional tuple of event types to include (None = all)

---

## 4. Inputs and Assumptions

- `consolidated_path`: Path (required, no default)
- `output_path`: Path (default: `data/viewpoint/acled_v1.parquet`)
- `ledger_path`: Path (default: `provenance/viewpoint/acled_v1_ledger.jsonl`)
- `event_type_filter`: tuple[str, ...] | None (default: None — include all event types)
- `version`: str, non-empty (default: `"acled_v1"`)

---

## 5. Outputs and Side Effects

- No side effects. Pure configuration container.
- No derived properties or computed fields.

---

## 6. Failure Modes and Loudness

- `ValueError` on empty `version`
- `AttributeError` on any attempt to mutate fields (frozen)

All failures are immediate and loud. No silent fallbacks.

---

## 7. Boundaries and Interactions

- Used by `build_acled_v1` as the sole configuration input
- Paths consumed by `pq.read_table`, `pq.write_table`, and `append_ledger_entry`
- Loaded by `load_acled_profile` from `profiles.py`
- Must not depend on any other `datafactory_*` config class
- Registered via `register_builder("acled_v1", ...)`

---

## 8. Examples of Correct Usage

```python
cfg = AcledViewpointConfig(consolidated_path=Path("data/consolidated/acled/store.parquet"))
cfg = AcledViewpointConfig(
    consolidated_path=Path("store.parquet"),
    event_type_filter=("Battles", "Riots"),
    version="acled_violence_v2",
)
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: empty version
AcledViewpointConfig(
    consolidated_path=Path("store.parquet"),
    version="",
)  # ValueError

# WRONG: mutating frozen config
cfg = AcledViewpointConfig(consolidated_path=Path("store.parquet"))
cfg.version = "new"  # AttributeError
```

---

## 10. Test Alignment

- **Green:** Default construction, custom parameters
- **Beige:** Empty version rejection
- **Red:** Mutation attempt (frozen enforcement), malformed consolidated store, total filter elimination

Tests in `tests/test_acled_viewpoint.py`.

---

## End of Contract

This document defines the **intended meaning** of `AcledViewpointConfig`.

Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
