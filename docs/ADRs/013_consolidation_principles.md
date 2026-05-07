
# ADR-013: Consolidation Principles

**Status:** Accepted
**Date:** 2026-03-20
**Deciders:** Simon Polichinel von der Maase, Claude Code

---

## Context

Data sources produce multiple snapshots over time: annual releases, monthly candidate updates, revised versions of the same events. These snapshots overlap, supersede, and sometimes contradict each other. The raw data from Layer 1 (ADR-012) is a collection of independent files with no unified view.

Before any analysis can happen, these snapshots must be consolidated into a single, queryable structure. But consolidation faces a critical design choice: should it also decide which version of an event is "correct"? Should it resolve temporal ambiguity? Should it discard superseded records?

The answer is no. Consolidation must be lossless, because:

1. **Research evolves.** The rules for choosing between versions (survivorship) change as research progresses. If consolidation discards data, those rules cannot be retroactively applied.
2. **Uncertainty is information.** Fields like `date_prec`, `where_prec`, `low`/`high` estimates encode measurement uncertainty. Discarding them is a methodological error (ISO GUM).
3. **Vintages matter.** In forecasting evaluation, you must distinguish between what was known at prediction time vs. what is known now. Discarding old versions makes this impossible.
4. **Reproducibility requires completeness.** If the consolidated store is lossy, reproducing a past analysis requires the original raw files — defeating the purpose of consolidation.

---

## Decision

Consolidation (Layer 2, ADR-012) must be **lossless**, **append-only**, and **version-aware**.

> The consolidated event store preserves every version of every event from every source.
> No fields are dropped. No records are discarded. No opinions are applied.
> Opinions about which version is "right" belong to the viewpoint builder (Layer 3).

---

## Principles

### 1. Lossless

No fields are dropped during consolidation. All uncertainty metadata, precision indicators, geolocation fields, and source-specific annotations are preserved. If a source provides a field, the consolidated store retains it.

The consolidated store may add metadata columns (e.g., `_source_type`, `_source_version`, `_ingested_at`) but must never remove source columns.

### 2. Append-Only

New vintages are added to the consolidated store. Existing records are never modified or deleted. The store grows monotonically.

If a source revises an event, the revision appears as a new record with different version metadata — not as an update to the existing record.

### 3. Bitemporal

The consolidated store tracks two time dimensions:

- **Valid time** — when the event occurred in the real world (the event's own dates).
- **Transaction time** — when the system learned about this version of the event (ingestion timestamp, source version identifier).

This enables temporal queries: "What was the dataset as known on date X?" and "How has our knowledge of event Y changed over time?"

### 4. Queryable

The consolidated store must support at minimum:

- **Latest snapshot:** The most recent version of each event (by transaction time).
- **Event history:** All versions of a specific event, ordered by transaction time.
- **Point-in-time view:** The dataset as it was known at a specific transaction time.
- **Source filtering:** All events from a specific source or source version.

These are read patterns, not prescriptions for storage format.

### 5. Provenance-Tracked

Every consolidation operation records:

- Which source files were consolidated
- Content digests of inputs and outputs
- Timestamp of consolidation
- Any metadata added during consolidation

Per ADR-008, consolidation failures must be logged and raised.

---

## What Consolidation Does NOT Do

The following decisions are explicitly **out of scope** for the consolidation layer:

| Decision | Owner |
|----------|-------|
| Choose between conflicting versions of an event | Viewpoint builder (Layer 3) |
| Distribute summary events across months | Viewpoint builder (Layer 3) |
| Handle temporal uncertainty (date_prec) | Viewpoint builder (Layer 3) |
| Assign events to grid cells | Compilation (Layer 4) |
| Aggregate events into cell-month bins | Compilation (Layer 4) |
| Decide which fields are "important" | Viewpoint builder (Layer 3) |

If consolidation is making a judgment call about data meaning, it has overstepped its boundary.

---

## Grounding in Established Frameworks

| Framework | Principle Applied |
|-----------|------------------|
| **Bitemporal modeling** (Snodgrass, Johnston) | Separate valid time from transaction time |
| **Event sourcing** (CQRS) | Consolidation is the write model — append everything, derive views separately |
| **SCD Type 2/4** (Kimball) | Store all versions; current view is derived, not primary |
| **Data vintages** (economics) | Keep all preliminary and revised releases indexed by when they were known |
| **W3C PROV** | Consolidation is a first-class activity with recorded inputs and outputs |
| **ISO GUM** | Uncertainty metadata must propagate; discarding it is a methodological error |

---

## Consequences

### Positive

- Viewpoint rules can be changed and reapplied without re-harvesting
- Multiple viewpoint versions can coexist over the same consolidated store
- Evaluation can distinguish preliminary from final data (vintage-aware)
- Full audit trail from raw source to any derived view
- No data is ever lost

### Negative

- Storage cost is higher than a deduplicated store
- Query patterns must account for multiple versions per event
- Contributors must understand the consolidation/viewpoint boundary

These costs are accepted. Storage is cheap; lost data is irreplaceable.

---

## Notes

This ADR is **constitutional** — it defines principles that apply to consolidation of any data source, not just UCDP. Source-specific consolidation rules (e.g., how UCDP annual and candidate versions relate) are defined in project-specific ADRs (ADR-015+) that apply these principles to a concrete source.

This ADR does not prescribe storage format (Parquet, DuckDB, etc.), file layout, or specific column names. Those are implementation decisions governed by the source-specific ADRs and the module's ARCHITECTURE.md.

### Schema Evolution (added 2026-03-22)

The consolidated Parquet store uses `pa.concat_tables(promote_options="default")` when merging new records with existing ones. This means:

- **New columns:** If a source adds a field, the column appears silently in the store. Existing records have `null` for the new column.
- **Removed columns:** If a source removes a field, old records retain it; new records have `null`. The column is never dropped.
- **Type changes:** PyArrow's type promotion resolves compatible types (e.g., int32 → int64). Incompatible changes (e.g., int → string) will raise an error during concatenation.

This is intentional: the lossless principle means no data is discarded, and schema differences between vintages are preserved rather than resolved. Consumers should handle nullable columns gracefully.

---

## References

- Kleppmann & Riccomini, *Designing Data-Intensive Applications*, 2nd ed., O'Reilly 2026:
  - Ch.1 p.10: The "sushi principle" — raw data is better; each consumer transforms to suit their needs
  - Ch.1 pp.10-11: Systems of record hold authoritative data; if there's a discrepancy, the system of record wins
  - Ch.4 p.131: Archival storage — re-encode snapshots using the latest schema; opportunity for columnar format
  - Ch.10 p.397: Immutability — batch inputs are never modified; outputs replace atomically
  - Ch.11 p.457: Event sourcing — store state as immutable sequence of events, derive current state by replay
  - Ch.12 pp.524-526: Immutability enables recovery from bugs — rerun derivation from intact inputs
