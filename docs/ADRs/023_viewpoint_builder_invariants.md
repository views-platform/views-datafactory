
# ADR-023: Viewpoint Builder Invariants

**Status:** Accepted
**Date:** 2026-04-08
**Deciders:** Simon Polichinel von der Maase, Claude Code
**Applies:** ADR-014 (Viewpoints as Derived Views), ADR-015 (UCDP Consolidation)

---

## Context

A forensic parity investigation (April 2026) compared the data factory's viewpoint output against VIEWSER's production database. The investigation required iterating over many data transformation decisions to identify root causes of discrepancy. It revealed two categories of decisions:

1. **Configurable research choices** — survivorship strategy, distribution strategy, filters, per-source routing. These are now exposed as ViewpointConfig fields (survivorship_strategy, distribution_strategy, source_distribution_map, filter_stale_versions, and the three filter fields).

2. **Architectural invariants** — decisions that are fixed for correctness or VIEWSER parity, where making them configurable would create untestable combinatorial complexity without clear research value.

This ADR documents the second category. These are the decisions that a researcher must know about but cannot change through configuration.

---

## Decision

The following are architectural invariants of the UCDP viewpoint builder (`builders/ucdp_v1.py`). They are not configurable and are not expected to change unless VIEWSER's GedLoader fundamentally changes.

### 1. Summary Event Detection Formula

An event is treated as a summary event if and only if all three conditions hold:

```
best > 0  AND  span > 1  AND  best >= span
```

Where `span` is the number of calendar months between `date_start` and `date_end` (inclusive).

The `>=` threshold (not strict `>`) matches VIEWSER's GED_loader0 and GED_loader1 notebooks. An older version (GED_loader2) used strict `>`, but the current production notebook uses `>=`.

### 2. Month Assignment from `date_end`

Non-summary events are assigned to the calendar month of their `date_end` field (not `date_start`). This matches VIEWSER's `pd.DataFrame.pgm.from_datetime(self.ged, 'date_end')`.

If `date_end` is missing, `date_start` is used as fallback.

### 3. Stale Filtering Specifics

When `filter_stale_versions=True` (the default), the builder applies these specific rules:

- **Annual coverage boundary:** The maximum `date_end` value across all annual events defines the temporal boundary.
- **Within annual period:** Non-annual rows are dropped if their event `id` does not appear in the annual data.
- **Latest .9 only:** Among .9 sources, only the latest version (by `_parse_version`) is retained; all older .9 versions are dropped.

These rules replicate VIEWSER's sequential loading behavior (annual first, .9 overwrites trailing 12 months).

### 4. Stripped Metadata Columns

The following consolidation metadata columns are removed from viewpoint output:

```python
{"_source_type", "_source_version", "_ingested_at",
 "_harvest_digest", "_harvest_timestamp"}
```

These are internal provenance fields that do not belong in consumer-facing output.

### 5. Processing Order

- Events are sorted by `id` for deterministic grouped processing.
- Filters (min_priogrid_gid, max_type_of_violence, exclude_where_prec) are applied **after** survivorship and distribution, not before. This ensures that distribution sees the original event before filtering.

---

## Rationale

- **Detection formula:** Matching VIEWSER's current production behavior is the primary constraint. The `>=` vs `>` choice affects only edge cases (events where `best == span`), but consistency with the gold set is mandatory.
- **Month from `date_end`:** VIEWSER assigns months from `date_end`. Using `date_start` would shift events backward in time, breaking parity.
- **Stale filtering specifics:** These rules were empirically derived from the parity investigation. They eliminated 30,000+ stale rows and reduced mismatch rates from ~0.1% to ~0.03%.
- **Filter order:** Filtering before distribution would prevent summary events from being detected (a filtered event's `best` might be zeroed). VIEWSER filters after distribution.

---

## Considered Alternatives

### Make detection formula configurable

Add a `summary_detection: str` parameter to ViewpointConfig with options like `"gte"` and `"gt"`.

**Rejected:** The `>=` vs `>` distinction affects fewer than 50 events in the entire dataset. The configurability cost (new parameter, new tests, documentation) exceeds the research value. If VIEWSER changes its detection formula, we change the code.

### Make stripped fields configurable

Add a `strip_fields: set[str]` parameter.

**Rejected:** The stripped fields are consolidation-layer metadata. They have no research meaning in the viewpoint. Exposing them as configurable invites misuse (e.g., stripping `date_end` or `best`).

---

## Consequences

### Positive

- Researchers know exactly which decisions are fixed and which are configurable.
- The invariants are documented in one place rather than scattered across code comments.
- Future parity investigations can reference this ADR as the baseline.

### Negative

- If UCDP changes their data model or VIEWSER changes its loading behavior, these invariants may need updating. This ADR makes the coupling explicit.

---

## Validation & Monitoring

- The consumer parity tests (`tests/test_consumer_parity.py`) validate that these invariants produce output matching VIEWSER's gold set within the known annual-version tolerance.
- The viewpoint unit tests (`tests/test_viewpoint.py`) test each invariant directly (e.g., ceil_split detection, date_end month assignment).

---

## References

- `reports/consumer_parity_investigation.md` — Full investigation report
- `reports/dot9_investigation/parity_results.md` — .9-only parity validation
- VIEWSER GED_loader notebooks (Desktop/notebook/GED_loader{0,1,2}.ipynb) — source of truth for VIEWSER behavior
