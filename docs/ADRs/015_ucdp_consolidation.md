
# ADR-015: UCDP Consolidation and Viewpoint Specifics

**Status:** Accepted
**Date:** 2026-03-20
**Deciders:** Simon Polichinel von der Maase, Claude Code
**Applies:** ADR-013 (Consolidation Principles), ADR-014 (Viewpoints as Derived Views)

---

## Context

UCDP/GED (Georeferenced Event Dataset) is the primary conflict event source for the VIEWS platform. It has two data streams:

- **UCDP/GED Annual** — yearly releases covering 1989 to the prior year. Each release is a complete, curated dataset. New releases may revise events from prior years.
- **UCDP/GED Candidate** — monthly releases, each covering a trailing 12-month window of events. Events are preliminary and subject to revision. Multiple candidate versions may exist for the same month. The API retains all historical releases (available from January 2018 onward — empirically confirmed 2026-03-21).

The VIEWS production system uses UCDP's `.9` version (format `YY.9.MM`), a bespoke monthly data product. Empirical investigation (2026-03-21) found that the `.9` is **not** a consolidation of annual + candidate data — it contains approximately 13,000 exclusive events (42% of its content) not available through any standard API endpoint. The `.9` is a distinct data source with exclusive content, available on the public API but undocumented in any UCDP codebook. See `reports/dot9_investigation/` for the full investigation.

Investigation of real UCDP data revealed three layers of hidden complexity:

1. **Summary events** (`date_prec=5`): 1.4% of events but 15.8% of fatalities. These span multiple months and require temporal distribution.
2. **Candidate version overlap**: Multiple candidate versions cover the same months. Without explicit survivorship rules, events can be double-counted.
3. **Temporal uncertainty**: 31.5% of fatalities come from events with `date_prec >= 4` (week-level precision or worse).

This ADR applies the constitutional principles of ADR-013 and ADR-014 to UCDP specifically.

---

## Decision

### UCDP Consolidation (Layer 2)

The UCDP consolidator combines all annual releases and all candidate versions into a single event store, following ADR-013 principles.

**Entity key:** The `id` field uniquely identifies an event across sources. The same event may appear in both annual and candidate data with different field values.

**Version tracking metadata** (added during consolidation):

| Column | Description | Example |
|--------|-------------|---------|
| `_source_type` | `"annual"` or `"candidate"` | `"annual"` |
| `_source_version` | Version identifier from the source | `"25.1"`, `"25.0.3"` |
| `_ingested_at` | UTC timestamp of ingestion | `"2026-03-20T14:30:00Z"` |

**Fields preserved:** All fields from both sources. No columns are dropped. The consolidator adds metadata columns but never removes source columns. Key fields include but are not limited to: `id`, `latitude`, `longitude`, `priogrid_gid`, `date_start`, `date_end`, `date_prec`, `where_prec`, `best`, `low`, `high`, `type_of_violence`, `code_status`, `number_of_sources`.

**Append-only:** Each harvest run adds records to the store. Existing records are never modified. If UCDP revises an event in a new annual release, the revision appears as a new record with a different `_source_version`.

### UCDP Viewpoint v1 (Layer 3)

The first viewpoint version targets parity with the production `.9` consolidation. This proves the consolidation is correct before evolving the rules.

**Survivorship rule:** For months covered by the annual release, annual wins. For the trailing window not yet covered by annual, the latest candidate version wins. When the same event appears in both annual and candidate with overlapping date coverage, the annual record takes precedence.

**Summary event handling:** Events with `date_prec=5` (spanning `date_start` to `date_end` across multiple months) are distributed across those months. Fatalities (`best`, `low`, `high`) are divided evenly across the spanned months, following the production `fix_summary_events` logic.

**Month assignment:** Uses `date_end` for month assignment, matching production behavior. This is a documented choice, not an accident — future viewpoint versions may use `date_start` or a distribution approach.

**Spatial assignment:** Uses `priogrid_gid` from UCDP when available. Falls back to lat/lon computation via `latlon_to_pgid` when `priogrid_gid` is missing or null.

**Output format:** Single Parquet with one row per event-month (summary events expand to multiple rows). Ready for consumption by Layer 4 (compilation).

---

## Validation Oracle

The `.9` version serves as the validation oracle for viewpoint v1:

1. Fetch `.9` for a known year range
2. Build viewpoint v1 from annual + candidate via our consolidation
3. Compare event-by-event: counts, fatalities, spatial placement, temporal placement
4. Parity means our consolidation is correct

Once parity is proven, the viewpoint builder can evolve independently. If UCDP discontinues `.9`, we are not affected — our consolidation stands on its own.

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
