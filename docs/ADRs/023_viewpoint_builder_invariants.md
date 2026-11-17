
# ADR-023: Viewpoint Builder Invariants

**Status:** Accepted
**Date:** 2026-04-08
**Deciders:** Simon Polichinel von der Maase
**Applies:** ADR-014 (Viewpoints as Derived Views), ADR-015 (UCDP Consolidation)

---

## Context

A forensic parity investigation (April 2026) compared the data factory's viewpoint output against VIEWSER's production database. The investigation required iterating over many data transformation decisions to identify root causes of discrepancy. It revealed two categories of decisions:

1. **Configurable research choices** — survivorship strategy, distribution strategy, filters, per-source routing. These are now exposed as ViewpointConfig fields (survivorship_strategy, distribution_strategy, source_distribution_map, filter_stale_versions, and the three filter fields).

2. **Architectural invariants** — decisions that are fixed for correctness or VIEWSER parity, where making them configurable would create untestable combinatorial complexity without clear research value.

This ADR documents the second category. These are the decisions that a researcher must know about but cannot change through configuration.

**Scope:** Despite the general title, this ADR covers UCDP viewpoint invariants specifically. Other viewpoint builders (ACLED, V-Dem, SHDI) have their own invariant sets documented in their respective ADRs or CICs.

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

---

## Amendment 2026-11-17 — annual releases now supersede each other (#594, #595)

**The Decision above is unchanged in intent.** This amendment records that §Decision item 3
enumerated three stale-filtering rules as if they were exhaustive, that the missing fourth
rule let withdrawn events stay in published figures for as long as two annual releases
coexisted, and what it cost. Dated amendment, not a rewrite.

### 1. The gap

§Decision item 3 defines the *Annual coverage boundary* as "the maximum `date_end` value
across all annual events" — across the **union** of annual releases, not the latest one — and
its three bullets say nothing about one annual release superseding another. The third bullet
does exactly that for `.9` data: "among .9 sources, only the latest version is retained".
Annual got no equivalent.

That asymmetry was invisible while only one annual release was on disk. It became
load-bearing when v26.1 was harvested on 2026-07-02 alongside v25.1, which is the state the
production store has been in since.

### 2. What it cost

UCDP does not only revise events between annual releases — it **deletes and merges** them.
Because the consolidated store is append-only by design (ADR-013), a withdrawn event keeps
its row from the superseded release. That row is annual, so the "within annual period" rule
kept it unconditionally; the ".9" rule never looked at it; and survivorship could not discard
it, because the event id had no competing row to lose to.

Measured 2026-11-17 against UCDP release 26.1: **229 events and 2,878 deaths** across
2022–2024 were events UCDP had withdrawn, of which 2,499 were Ukraine. The per-year totals —
90, 388 and 2,400 — accounted exactly for the entire gap between our published global figures
and UCDP's own. An external reviewer found the symptom before we did.

Nothing went red. Deaths were neither created nor destroyed by the pipeline, so every ADR-040
conservation invariant held; the error entered at ingestion of a release that was later
withdrawn.

### 3. The rule now applied

A fourth rule, applied **before** the annual coverage boundary is derived:

- **Latest annual only:** among annual sources, only the latest version (by `_parse_version`)
  is retained for the span that version covers. Rows from an older release whose `date_end`
  lies beyond the latest release's coverage survive.

The ordering is load-bearing. Running it first means the coverage boundary and the annual id
set are derived from a single release, and a `.9` or candidate row for a withdrawn event is
dropped with it. Running it last would leave that row to win survivorship and republish the
event from another source.

The span clause selects nothing today — v26.1 spans 1989–2025 and v25.1 spans 1989–2024 — and
exists so that a future release with a shorter span cannot silently delete history.

Implemented in the UCDP viewpoint builder, inside the same block the other three rules live
in, under the existing `filter_stale_versions` flag. Guarded by `tests/test_viewpoint.py`,
which now carries the first fixtures in the suite with two annual versions present.

### 4. What this does not change

The consolidation layer still preserves every vintage (ADR-013, ADR-017). Supersession is a
viewpoint decision, which is where ADR-013 places it. Nothing is deleted from `data/raw/`.
