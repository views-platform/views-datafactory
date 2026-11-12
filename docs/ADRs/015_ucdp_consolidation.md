
# ADR-015: UCDP Consolidation and Viewpoint Specifics

**Status:** Accepted
**Date:** 2026-03-20
**Deciders:** Simon Polichinel von der Maase
**Applies:** ADR-013 (Consolidation Principles), ADR-014 (Viewpoints as Derived Views)

---

## Context

UCDP/GED (Georeferenced Event Dataset) is the primary conflict event source for the VIEWS platform. It has three data streams:

- **UCDP/GED Annual** — yearly releases covering 1989 to the prior year. Each release is a complete, curated dataset. New releases may revise events from prior years.
- **UCDP/GED Candidate** — monthly releases, each covering a trailing 12-month window of events. Events are preliminary and subject to revision. Multiple candidate versions may exist for the same month. The API retains all historical releases (available from January 2018 onward — empirically confirmed 2026-03-21).
- **UCDP/GED .9 Consolidated** (format `YY.9.MM`) — a bespoke monthly data product. Empirical investigation (2026-03-21) found that the `.9` is **not** a consolidation of annual + candidate data — it contains exclusive events (count varies by version — from ~350 to ~2,600 per version, 3-12% of content) not available through any standard API endpoint. The `.9` is a distinct data source with exclusive content, available on the public API but undocumented in any UCDP codebook. See `reports/dot9_investigation/` for the full investigation.

Investigation of real UCDP data revealed three layers of hidden complexity:

1. **Summary events** (`date_prec=5`): 1.4% of events but 15.8% of fatalities. These span multiple months and require temporal distribution.
2. **Candidate version overlap**: Multiple candidate versions cover the same months. Without explicit survivorship rules, events can be double-counted.
3. **Temporal uncertainty**: 31.5% of fatalities come from events with `date_prec >= 4` (week-level precision or worse).

This ADR applies the constitutional principles of ADR-013 and ADR-014 to UCDP specifically.

---

## Decision

### UCDP Consolidation (Layer 2)

The UCDP consolidator combines all annual releases, all candidate versions, and all .9 consolidated versions into a single event store, following ADR-013 principles.

**Entity key:** The `id` field uniquely identifies an event across sources. The same event may appear in both annual and candidate data with different field values.

**Version tracking metadata** (added during consolidation):

| Column | Description | Example |
|--------|-------------|---------|
| `_source_type` | `"annual"`, `"candidate"`, or `"dot9"` | `"annual"` |
| `_source_version` | Version identifier from the source | `"25.1"`, `"25.0.3"`, `"25.9.11"` |
| `_ingested_at` | UTC timestamp of ingestion | `"2026-03-20T14:30:00Z"` |
| `_harvest_digest` | Content digest of the source Parquet file (ADR-017) | `"sha256:a1b2c3d4..."` |
| `_harvest_timestamp` | UTC timestamp of when the source was fetched (ADR-017) | `"2026-03-21T10:00:00Z"` |

**Fields preserved:** All fields from all three sources. No columns are dropped. The consolidator adds metadata columns but never removes source columns. Key fields include but are not limited to: `id`, `latitude`, `longitude`, `priogrid_gid`, `date_start`, `date_end`, `date_prec`, `where_prec`, `best`, `low`, `high`, `type_of_violence`, `code_status`, `number_of_sources`.

**Append-only:** Each harvest run adds records to the store. Existing records are never modified. If UCDP revises an event in a new annual release, the revision appears as a new record with a different `_source_version`.

### UCDP Viewpoint v1 (Layer 3)

**Why this viewpoint exists:** Viewpoint v1 deliberately replicates the behavior of the legacy UCDP ingestor that fed the old VIEWS database. Every decision below — survivorship order, `date_end` for month assignment, even-split fatality distribution for summary events — was chosen to match production output, not because it is analytically optimal. The goal is to prove that the new data factory can reproduce the exact same data the models were trained on, establishing a trusted baseline before evolving the rules.

This is a parity target, not a design ideal. Future UCDP viewpoints should revisit these choices on their own merits (see Open Questions).

**Survivorship rules:** Two strategies are implemented:

- `annual_wins` — Annual takes precedence. For months not covered by annual, the latest candidate version wins. Does not use `.9` data.
- `dot9_wins` (production parity) — Annual takes precedence, then `.9`, then candidate. For months covered by the annual release, annual wins. For the trailing window, `.9` wins over candidate. This matches VIEWS production behavior.

**Summary event handling:** Events with `date_prec=5` (spanning `date_start` to `date_end` across multiple months) are distributed across those months. Fatalities (`best`, `low`, `high`) are divided evenly across the spanned months, following the production `fix_summary_events` logic.

**Month assignment:** Uses `date_end` for month assignment, matching production behavior. This is a documented choice, not an accident — future viewpoint versions may use `date_start` or a distribution approach.

**Spatial assignment:** Uses `priogrid_gid` from UCDP when available. Falls back to lat/lon computation via `latlon_to_pgid` when `priogrid_gid` is missing or null.

**Output format:** Single Parquet with one row per event-month (summary events expand to multiple rows). Ready for consumption by Layer 4 (compilation).

---

## The `.9` Dual Role

The `.9` version serves two roles in this system:

**Validation oracle.** The `.9` was initially used to validate viewpoint v1. 100% parity was achieved on 27,853 non-expanded events when using `.9` as sole input with the `production_parity` profile (see `reports/dot9_investigation/parity_results.md`).

**Production data source.** Because `.9` contains exclusive events not available through annual or candidate endpoints, it is also ingested as a distinct Layer 1 source. The `dot9_wins` survivorship strategy (annual > .9 > candidate) consumes `.9` data from the consolidated store. This is the production parity target.

If UCDP discontinues `.9`, we lose access to its exclusive events but our annual + candidate consolidation stands on its own via the `annual_wins` strategy.

---

## Known Complexities

### Summary Events (date_prec=5)
- 1.4% of events, 15.8% of fatalities in 2023 annual data
- Span multiple months (`date_start` to `date_end`)
- Production distributes fatalities evenly across spanned months
- Future viewpoint versions may use more sophisticated distribution

### Candidate Version Overlap
- Multiple candidate versions (e.g., 25.0.1, 25.0.2, 25.0.3) cover overlapping months
- Without survivorship rules, the same event can appear multiple times
- The consolidator stores all versions; the viewpoint builder resolves overlap

### Temporal Uncertainty
- `date_prec` ranges from 1 (exact date) to 5 (multi-month range)
- 31.5% of fatalities come from events with `date_prec >= 4`
- Viewpoint v1 ignores this (matching production). Future versions should propagate uncertainty.

### priogrid_gid vs. Computed Cell
- UCDP provides `priogrid_gid` for most events
- Our current compiler computes cell from lat/lon
- These can disagree (border cells, precision issues)
- Viewpoint v1 should prefer `priogrid_gid` to match production

---

## Extensibility

This ADR demonstrates the OCP pattern for source-specific ADRs:

- **ADR-013** (constitutional) defines what consolidation must guarantee — lossless, append-only, bitemporal, queryable
- **ADR-014** (constitutional) defines what a viewpoint must be — disposable, rebuildable, versioned, configurable
- **This ADR** (project-specific) applies those principles to UCDP

When a new data source is added (e.g., ACLED), it gets its own project-specific ADR (e.g., ADR-016) that applies ADR-013 and ADR-014 to that source's specific entity keys, version tracking, survivorship rules, and known complexities. The constitutional ADRs are not modified.

---

## Consequences

### Positive

- Eliminates dependency on UCDP's custom `.9` consolidation
- Full version history enables vintage-aware evaluation
- Summary event handling is explicit and auditable
- Path to improved viewpoints without re-consolidation
- New UCDP data streams (e.g., new candidate release cadence) require only this ADR's update

### Negative

- Higher storage cost (all versions retained)
- Summary event distribution adds complexity to the viewpoint builder
- `.9` parity testing requires access to `.9` data (one-time fetch)

These costs are accepted. Independent consolidation is a prerequisite for methodological integrity.

---

## Notes

This is the first project-specific ADR applying ADR-013 and ADR-014. It serves as the template for future source-specific ADRs.

Open questions for future viewpoint versions:
- Should `date_prec` influence temporal assignment confidence?
- Should `where_prec` influence spatial assignment confidence?
- How should nowcasting adjustments interact with the golden record?
- Should `code_status` affect survivorship (e.g., prefer "Clear" over "Unclear")?

These questions are research outputs, not infrastructure decisions. They belong in future viewpoint version configurations.

---

## Amendment 2026-11-12 — the spatial assignment rule is now implemented (#547, #551)

**The Decision above is unchanged.** This amendment records that one sentence of it went
unimplemented from acceptance until 2026-11-12, that the disagreement it predicted did occur,
and what it cost. Dated amendment, not a rewrite.

### 1. The sentence

§Decision, *Spatial assignment*: *"Uses `priogrid_gid` from UCDP when available. Falls back to
lat/lon computation via `latlon_to_pgid` when `priogrid_gid` is missing or null."*

And §Known Complexities, *priogrid_gid vs. Computed Cell*: *"These can disagree (border cells,
precision issues) · Viewpoint v1 should prefer `priogrid_gid` to match production."*

**Neither the preference nor the fallback existed anywhere in `src/`.** `CompilationConfig`
offered `lat_field` and `lon_field` and no way to name a decided cell, and
`grid_compilation._place_events` derived every event's cell by calling `latlon_to_pgid` on the
coordinates. `_required_columns` did not even load `priogrid_gid` from the parquet, so the
field this ADR designated as authoritative was never read.

### 2. What it cost

The gap was invisible while nothing wrote to `priogrid_gid`. It became load-bearing when
ADR-049's spatial allocator shipped, because the allocator records its chosen cell *by
rewriting `priogrid_gid`* and leaves `latitude`/`longitude` at the source centroid. Every
allocated row therefore returned to the cell it came from.

Measured 2026-11-12 on the production store: **1,128,236 deaths across 60,105 events — 26.49%
of all UCDP fatality mass — delivered in a cell the allocator had not chosen.** At
`where_prec=6`, 97.3% of the eligible mass. For the Tigray annual summary, 18 allocated cells
arrived as 1.

Totals were conserved throughout, which is why no conservation boundary reported anything:
relocation conserves. The delivered figures are in
`reports/investigation_allocation_delivery/findings.md`.

### 3. What changed

`CompilationConfig` gains `pgid_field`, defaulting to `None`. When set, `_required_columns`
loads that column and `_place_events` uses its value when the value is present and names a
cell inside the grid, falling back to `latlon_to_pgid` otherwise — which is this ADR's rule,
verbatim, four months late. The fallback is counted and reported, and any unusable declared
value warns, because a silent fallback is what made the original gap survivable.

`scripts/compile_grid.py` passes `--pgid-field priogrid_gid` by default. The default stays
`None` in the library so that existing callers are unaffected: ACLED does not allocate, so for
ACLED `latlon_to_pgid` *is* the correct authority and there is no decision to defer to.

The capability was not invented for this. `PregriddedCompilationConfig` already had
`pgid_field`, which is why V-Dem, SHDI, GHS-POP and GHS-BUILT-S were structurally immune — their
compiler reads the decided cell. The event compiler was simply never given the same field.

### 4. One stated cause of the disagreement is refuted

§Known Complexities attributes the pre-existing `priogrid_gid` ↔ coordinate disagreements to
*"border cells, precision issues"*. Measured on the same store: of the seventy events where the
two disagree, **zero are border-adjacent**, the median offset is **1,460 cells**, and 62 of 70
are `where_prec=6`, where the declared cell and the coordinates are two independently chosen
representatives of the same country. The disagreement is not a rounding artifact; it is two
different answers to a question neither field was asked.

### 5. What this amendment does not change

The survivorship rules, the `.9` dual role, the month-assignment choice and the summary-event
handling are untouched. ADR-053 superseded the even-division of summary events; this amendment
touches only the spatial sentence.
