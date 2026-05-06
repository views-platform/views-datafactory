# ADR-028: ACLED Consolidation and Viewpoint Specifics

**Status:** Accepted
**Date:** 2026-05-05
**Deciders:** Simon Polichinel von der Maase, Claude Code
**Applies:** ADR-013 (Consolidation Principles), ADR-014 (Viewpoints as Derived Views)

---

## Context

ACLED (Armed Conflict Location & Event Data) is the second conflict event source integrated into the VIEWS data factory. Unlike UCDP (ADR-015), where viewpoint v1 was designed to achieve parity with the legacy ingestor, ACLED has no legacy system to match. The decisions here were made from first principles in a clean-room design process (2026-05-05), deliberately avoiding the assumptions baked into the prior ACLED ingestion script used by the metric lab.

ACLED has one data stream (the ACLED API) and a simpler event model than UCDP:

- **Single source type** — no annual/candidate/.9 split, so no survivorship rules needed
- **Atomic daily events** — each event has exactly one `event_date`. Multi-day conflicts are recorded as separate daily events (ACLED Codebook: "If a military campaign starts on 1 March 2020 and lasts until 5 March 2020 with violent activity reported each day, this is recorded as five different events."). No temporal distribution needed.
- **No summary events** — no equivalent of UCDP's `date_prec=5` spanning events
- **Six event types** — Battles, Explosions/Remote violence, Violence against civilians, Protests, Riots, Strategic developments
- **~25 sub-event types** — finer categorization within each event type
- **geo_precision** — 1 (exact), 2 (nearest settlement), 3 (admin centroid). Analogous to UCDP's `where_prec`.
- **time_precision** — 1 (exact day), 2 (within a week), 3 (within a month). Analogous to UCDP's `date_prec`.

This ADR follows the extensibility pattern established in ADR-015: constitutional ADRs (013, 014) define the principles; this project-specific ADR applies them to ACLED.

---

## Decision

### ACLED Consolidation (Layer 2)

The ACLED consolidator tags raw harvester snapshots with source metadata and writes a single event store, following ADR-013 principles.

**Entity key:** `event_id_cnty` uniquely identifies an event across snapshots.

**Version tracking metadata** (added during consolidation):

| Column | Description | Example |
|--------|-------------|---------|
| `_source_type` | Always `"acled"` | `"acled"` |
| `_source_version` | Year range from snapshot filename | `"1997_2025"` |
| `_ingested_at` | UTC timestamp of ingestion | `"2026-05-03T14:30:00Z"` |
| `_harvest_digest` | Content digest of the source Parquet file | `"sha256:a1b2c3d4..."` |
| `_harvest_timestamp` | UTC timestamp of when the source was fetched | `"2026-05-03T10:00:00Z"` |

**Deduplication:** On `(event_id_cnty, _harvest_digest)`. Identical re-fetches are skipped; updated snapshots with different digests are preserved.

**Fields preserved:** All fields from the API response. No columns are dropped.

### ACLED Viewpoint v1 (Layer 3)

**Why this viewpoint exists:** To provide a minimal, correct pass-through from the consolidated store to compilation. There is no legacy system to match — this is the simplest defensible viewpoint for ACLED event data.

**What it does:**
- Assigns `date_month` by slicing `event_date[:7]` (YYYY-MM)
- Optionally filters by event type (configurable)
- Strips consolidation metadata columns (`_source_type`, `_source_version`, `_ingested_at`, `_harvest_digest`, `_harvest_timestamp`)

**What it does NOT do:**
- No survivorship (single source type — nothing to resolve)
- No temporal distribution (atomic daily events — nothing to distribute)
- No spatial transformation (lat/lon passed through as-is)
- No aggregation (one row per event, same as input)

### ACLED Compilation v1 (Layer 4)

**Why this compilation exists:** To produce the first set of ACLED features on the PRIO-GRID for model consumption. Feature selection was driven by domain knowledge: ACLED's primary analytical value is in event counts (not fatalities), and the six event types represent meaningfully distinct conflict dynamics.

**Spatial assignment:** Lat/lon → PRIO-GRID cell via floor-based lookup, same as UCDP. All events assigned regardless of `geo_precision`. Precision-3 events (admin centroids) are assigned to their reported cell — the noise this introduces is accepted as a known limitation.

**Temporal assignment:** `event_date` → calendar month. One event = one date = one month. No ambiguity.

**Features produced (8 columns per cell-month):**

| Feature | Strategy | Description |
|---------|----------|-------------|
| `acled_count` | count | Total events in cell-month |
| `acled_battles` | count | Events where `event_type = "Battles"` |
| `acled_explosions` | count | Events where `event_type = "Explosions/Remote violence"` |
| `acled_vac` | count | Events where `event_type = "Violence against civilians"` |
| `acled_protests` | count | Events where `event_type = "Protests"` |
| `acled_riots` | count | Events where `event_type = "Riots"` |
| `acled_strategic` | count | Events where `event_type = "Strategic developments"` |
| `acled_fatalities` | sum | Sum of `fatalities` field |

---

## Rationale

### Clean-room design, not parity

The UCDP viewpoint v1 targets parity with the legacy ingestor (ADR-015). For ACLED, we deliberately chose NOT to replicate the old metric lab ACLED ingestor. That script may carry assumptions that were never examined. Instead, these decisions were derived from the ACLED codebook, API documentation, and domain knowledge about what conflict features matter.

### Event counts over fatalities

ACLED's fatality estimates are less reliable than UCDP's — ACLED itself emphasizes event occurrence patterns over casualty counts. Fatalities are included because the data is available, but the six per-type count features are the primary analytical contribution.

### Per-type, not per-sub-type

Six event types provide meaningful disaggregation without excessive sparsity. Sub-event types (~25 categories) would produce mostly-zero columns for most cells in most months. This is a scope decision for v1 — sub-event-type features are a known future viewpoint/compilation variant.

### All geo_precision values included

Dropping precision-3 events would lose data, and the consolidated store does not support "partial drops" — a viewpoint either includes an event or it doesn't. A future viewpoint can handle geo_precision differently (uncertainty weighting, exclusion, spatial spreading), but that requires its own ADR and analytical justification. For v1, the simplest correct approach is to assign all events to their reported location.

---

## Considered Alternatives

### Alternative A: Per-sub-event-type features (~25 columns)

- **Pros:** Maximum disaggregation, captures within-type variation (e.g., "Armed clash" vs. "Government regains territory" within Battles)
- **Cons:** Extreme sparsity, 25+ mostly-zero features per cell-month, diminishing analytical returns for v1
- **Reason for rejection:** Deferred to a future viewpoint/compilation version. Decision can be revisited once models are consuming the 8-column v1 and researchers identify sub-type signal.

### Alternative B: Drop geo_precision=3 events

- **Pros:** Cleaner spatial signal, no false-precision assignments
- **Cons:** Data loss, especially in remote/poorly-covered regions. No way to recover dropped events without re-running the viewpoint.
- **Reason for rejection:** The graph architecture means we never need to drop data at the viewpoint level — we can always build a more selective viewpoint later from the same consolidated store.

### Alternative C: Per-type fatalities (e.g., `acled_battles_fatalities`)

- **Pros:** Richer signal per feature
- **Cons:** 6 additional columns, extreme sparsity (fatalities are rare per cell-month, even rarer per type), ACLED fatality estimates are less reliable than UCDP's
- **Reason for rejection:** Deferred. Can be added in a future compilation version if models benefit.

### Alternative D: Actor-based features

- **Pros:** Captures who is fighting, not just what happened
- **Cons:** Requires actor taxonomy design, affects both ACLED and UCDP, cross-source design effort
- **Reason for rejection:** Important future work, but a separate design effort that spans both data sources. Not appropriate for an ACLED-only v1.

---

## Consequences

### Positive

- Clean analytical foundation for ACLED features, not constrained by legacy decisions
- Eight features with clear rationale, each traceable to this ADR
- Graph architecture preserves all data — future viewpoints can make different choices without re-harvesting or re-consolidating
- Same spatial assignment approach as UCDP — consistency across sources

### Negative

- geo_precision=3 noise accepted (mitigated by future precision-aware viewpoint)
- Sub-event-type signal not captured in v1 (mitigated by future compilation variant)
- Actor information not captured (mitigated by future cross-source design effort)

These costs are accepted. The v1 compilation should be correct and useful, not comprehensive.

---

## Implementation Notes

- Consolidator: `src/datafactory_consolidation/consolidators/acled.py` (exists)
- Viewpoint builder: `src/datafactory_viewpoint/builders/acled_v1.py` (exists)
- Compilation: `src/datafactory_compilation/` (to be built — ACLED compiler does not exist yet)
- The compiler should follow the same `FeatureSpec` pattern as UCDP compilation (ADR-024)
- `geo_precision` and `time_precision` are preserved in the consolidated store for future viewpoints

---

## Relationship to Future ACLED Viewpoints

This ADR documents viewpoint v1 and compilation v1. Future viewpoints may include:

- **Precision-aware viewpoint** — excludes or down-weights geo_precision=3 / time_precision=3 events
- **Sub-event-type viewpoint** — disaggregates to ~25 sub-types
- **Actor-enriched viewpoint** — adds actor taxonomy features (joint design with UCDP)
- **Uncertainty-propagating viewpoint** — treats precision codes as confidence intervals

Each future viewpoint should reference this ADR and document its own rationale in a new ADR or an update to this one.

---

## Open Questions

- Should `time_precision` influence temporal assignment confidence in a future viewpoint?
- Should `geo_precision` influence spatial assignment confidence?
- How should actor-based features be designed to work across both ACLED and UCDP?
- At what point does sub-event-type disaggregation provide diminishing returns vs. sparsity cost?
- Should `interaction` codes (dyad types) become features?

These questions are research outputs, not infrastructure decisions. They belong in future viewpoint version ADRs.

---

## References

- ADR-013: Consolidation Principles
- ADR-014: Viewpoints as Derived Views
- ADR-015: UCDP Consolidation and Viewpoint Specifics (template for this ADR)
- ADR-024: Compilation Grid Invariants
- ACLED Codebook (2024): https://acleddata.com/methodology/acled-codebook
- ACLED API documentation: https://apidocs.acleddata.com/
- Clean-room design discussion: 2026-05-05 session
