# ADR-040: Count Conservation and Hierarchical Reconciliation

**Status:** Accepted
**Date:** 2026-06-05
**Deciders:** Simon Polichinel von der Maase, Claude Code
**Applies:** ADR-012 (Four-Layer Data Architecture), ADR-013 (Consolidation Principles), ADR-014 (Viewpoints as Derived Views), ADR-024 (Compilation Grid Invariants), ADR-025 (Country Identity Uses GAUL Codes)

---

## Context

On 2026-04-30, a pipeline verification audit discovered that country-month (CM) fatality totals were systematically 4% lower than the corresponding grid-level (PGM) totals (C-149, `reports/postmortem_cm_unmapped_gaul_cells.md`). The root cause: 603 PRIO-GRID cells classified as land by PRIO-GRID but with centroids in the ocean received `gaul0_code = -1` during assembly. `grid_to_country_month()` filtered on `country_ids > 0` and silently excluded these cells — dropping 45,593 state-based fatalities across 435 months, with single-month peaks of 2,688.

No ADR, no test, and no runtime check caught this. The pipeline completed successfully. Provenance ledgers showed no anomaly. The system ran for 27 days with a ~3.8% silent data gap.

The existing ADR stack provides layer-local guarantees but no system-wide count integrity:

- **ADR-013** guarantees lossless consolidation (Layer 2), but only within that layer. Events are never discarded during consolidation — but consolidation does not control what happens when those events are compiled into grid cells, assigned to countries, and aggregated.
- **ADR-008** mandates fail-loud for structural errors (schema mismatches, missing files, wrong array shapes). But C-149 was not a structural error — the grid had the correct shape, the Parquet files were valid, and the spatial join executed without exception. The data gap was an arithmetic gap, not a structural failure.
- **ADR-024** defines grid layout invariants (dimension order, spatial binning, temporal binning). These constrain the physical format of the grid but say nothing about whether the grid's aggregate counts match the viewpoint's aggregate counts.
- **ADR-025** explicitly acknowledges unmapped cells (lines 96–102): "These cells appear in PGM output but are excluded from CM aggregation by `grid_to_country_month()`, which filters on `country_ids > 0`." The ADR treats this as an implementation note, not a violation. There was no invariant to violate.

The pipeline needs cross-layer count integrity constraints that make silent data loss structurally impossible — not as a post-hoc test, but as an architectural invariant with the same constitutional weight as lossless consolidation.

---

## Decision

The data factory adopts two architectural invariants and one supporting concept:

> Count data entering the VIEWS data factory must be accounted for at every layer boundary and every spatial aggregation level within a reconciliation family. No count may be silently dropped. If a count is excluded, the exclusion must be declared, quantified, and visible in the provenance ledger.

**Invariant 1: Count Conservation** — at every layer transition, the accounting equation `placed + excluded = input` must hold. Every exclusion must be quantified.

**Invariant 2: Hierarchical Reconciliation** — within a reconciliation family, aggregations at different administrative levels must produce identical totals.

**Supporting concept: Reconciliation Family** — a set of administrative levels from a single source system that share a proper containment hierarchy.

---

## Invariant 1: Count Conservation

At every layer boundary in the data pipeline, the total count of the quantity being processed must be fully accounted for. The general form:

For any transformation *f* that maps input data *D_in* to output data *D_out*, there must exist a partition of *D_in* into *D_placed* (data that reaches the output) and *D_excluded* (data that does not). The accounting equation is:

```
count(D_in) = count(D_placed) + count(D_excluded)
aggregate(D_out) = aggregate(D_placed)
```

*D_excluded* must be explicitly logged in the provenance ledger with per-exclusion-reason counts. Exclusions are permitted (the viewpoint builder filters events, the CM aggregation excludes ocean cells), but they must never be silent.

### Layer-specific accounting equations

**Viewpoint → Compilation** (`grid_compilation.py`, `_place_events_columnar`):

```
placed + skipped_spatial + skipped_temporal = input_rows
```

The variables `n_skipped_spatial` and `n_skipped_temporal` already exist (lines 103–151). This invariant makes the equation a mandatory assertion, not an optional log message.

**Compilation → Assembly** (`assemble_grid.py`):

Every source's compiled grid must contribute to the assembled grid without cell loss. If a source covers 259,200 cells, all 259,200 must appear in the assembly.

**Assembly → Country-Month** (`grid_to_country_month.py`):

```
sum(all country totals) + sum(excluded cell values) = sum(all grid cells)
```

The exclusion count `n_excluded` and the warning for nonzero excluded events already exist (lines 73–95). This invariant elevates the accounting from a warning to a verifiable equation.

### What "count data" means

This invariant applies to **extensive quantities** — values where sums are meaningful: fatality counts, event counts, population counts. It does not apply to **intensive quantities** — values where sums are not meaningful: democracy scores (V-Dem), human development indices (SHDI), built-up surface fractions (GHS-BUILT-S). The distinction follows the thermodynamic convention: extensive properties scale with system size; intensive properties do not.

If a future source provides count data (e.g., WDI economic indicators denominated in units), it falls under this invariant automatically.

---

## Invariant 2: Hierarchical Reconciliation

Within a single administrative boundary system, aggregations at different administrative levels must produce identical totals when covering the same territory and time period.

For an administrative system *S* with levels *L₀* > *L₁* > *L₂* (where > means "contains"), and for any count feature *f* and time period *t*:

```
sum(f, t, over all L₂ districts in country X)
  = sum(f, t, over all L₁ provinces in country X)
  = f(t, country X at L₀)
```

This holds because admin levels within a single system share a proper containment hierarchy: every *L₂* polygon is fully contained within exactly one *L₁* polygon, which is fully contained within exactly one *L₀* polygon. The spatial assignment method (centroid-in-polygon, area-majority, or any future method) produces a deterministic mapping from PRIO-GRID cell to exactly one unit at each level. Therefore, summing grid cell values grouped by *L₂*, then summing those *L₂* sums within their parent *L₁* units, must yield the same result as directly summing grid cells grouped by *L₁*.

If this reconciliation fails, the spatial assignment has produced an inconsistent hierarchy — a cell claims to be in district X (L₂) but is assigned to a province that does not contain district X (L₁). This is a data corruption bug, not an edge case.

### Grid-to-administrative-unit reconciliation

A special case of hierarchical reconciliation connects the PRIO-GRID to any administrative system:

```
sum(f, t, over all pgids assigned to country X) = CM(f, t, country X)
```

Every PRIO-GRID cell maps to at most one administrative unit via its GAUL code. The sum of all cell values for cells assigned to country X must equal country X's country-month total. If it does not, either Invariant 1 (count conservation) or the spatial assignment is broken.

---

## Reconciliation Families

A **reconciliation family** is a set of administrative or spatial levels from a single source system that share a proper containment hierarchy. Within a family, hierarchical reconciliation (Invariant 2) is mandatory. Between families, reconciliation is not required and not expected.

| System | Levels | Reconciliation | Reason |
|--------|--------|---------------|--------|
| GAUL | gaul0_code, gaul1_code, gaul2_code | Required (hierarchical) | Same FAO source dataset; L₂ ⊂ L₁ ⊂ L₀ by construction |
| GDL | gdl_region_code | N/A (single level) | No sub-levels to reconcile |
| GAUL vs. GDL | gaul0_code vs. gdl_region_code | **Not required** | Different source systems define "Democratic Republic of Congo" differently at the boundary; a PRIO-GRID cell assigned to GAUL-DRC may overlap a GDL region spanning DRC and Republic of Congo |
| PRIO-GRID vs. any admin system | pgid vs. admin code | One-directional | Every pgid maps to at most one admin unit; sum of pgid values for unit X = unit X's aggregate total |

This table is the authoritative registry of reconciliation families. When a new spatial system is added to the data factory (e.g., GADM, custom conflict zones, UN statistical areas), it must be classified here as either:

1. **Joining an existing family** — if its levels are proper subsets of an existing system's levels (rare; most systems define their own boundaries).
2. **Forming an independent family** — if its boundaries are drawn from a different source (typical).
3. **Single-level system** — if it provides only one aggregation level (no internal reconciliation needed).

Cross-family reconciliation failure is expected and is not a bug. A researcher summing fatalities in GAUL-Congo and GDL-Congo should expect different totals because the boundary polygons differ. This is not a data integrity issue — it is a fundamental property of working with multiple spatial reference systems.

---

## What This ADR Does NOT Do

| Out of scope | Owner | Reason |
|-------------|-------|--------|
| Choose which events to filter or exclude | Viewpoint builder (ADR-014, ADR-023) | Filtering is a research decision; this ADR requires only that filters are accounted for in the conservation equation |
| Choose the spatial assignment method | ADR-025, ADR-039 (draft) | This ADR requires that whatever method is used produces complete coverage; it does not choose between centroid-in-polygon, area-majority, or any other method |
| Require cross-system reconciliation | N/A | Different systems define boundaries differently; cross-system reconciliation is not meaningful (see Reconciliation Families) |
| Define grid layout or array shape | ADR-024 | Compilation invariants are structural; this ADR is about count integrity |
| Propagate input uncertainty | Deferred (Alternative B) | Uncertainty propagation (confidence intervals on counts) is a future concern |
| Assign events to countries using event coordinates | Deferred (Alternative A) | Event-level assignment bypasses centroid limitations but requires architectural redesign |
| Define conservation rules for intensive features | Future ADR | HDI, democracy scores, built-up fraction have different aggregation semantics (weighted average, not sum) |
| Prescribe specific float tolerance thresholds | Implementation detail | Tests may use `atol=1e-3` or similar; the ADR defines the principle, not the epsilon |

---

## Deferred Alternatives

### Alternative A: Event-level country assignment

Instead of assigning events to grid cells (via event lat/lon) and then assigning grid cells to countries (via cell centroid or area-majority), assign events directly to countries using the event's own coordinates. An event at a coastal coordinate would be assigned to the nearest country polygon, bypassing the centroid-in-polygon problem entirely.

**Deferred because:**

1. It changes the fundamental architecture: events would skip the grid for country assignment, creating a parallel spatial path. The grid remains the atomic unit for PGM queries (ADR-024), but CM aggregation would operate on event-level data — breaking the current design where CM is always derived from PGM.
2. It may resolve naturally as grid resolution decreases. At higher resolution (e.g., 0.25° or 0.1° cells), fewer centroids fall in water and the centroid-vs-area-majority distinction becomes negligible.
3. It only affects the grid-to-country aggregation path. PGM output (grid-level queries) is unaffected.

### Alternative B: Input uncertainty propagation

Count conservation treats all counts as exact integers. In reality, UCDP `best` estimates have `low` and `high` bounds, and ACLED event geocoding precision varies. Propagating uncertainty through aggregation (e.g., as confidence intervals) would give consumers richer information about the reliability of country-month totals.

**Deferred because:**

1. No downstream model currently consumes uncertainty bounds on count features.
2. The statistical framework for aggregating uncertainty across spatial units is non-trivial — correlated events within a cell-month require joint distributions, not independent error propagation.
3. The priority is establishing exact-count conservation before adding uncertainty. The floor (no silent drops) must exist before the ceiling (bounded uncertainty) is meaningful.

---

## Grounding in Established Frameworks

| Framework | Principle applied |
|-----------|------------------|
| **Double-entry bookkeeping** (Pacioli, 1494) | Every debit has a credit; the accounting equation must balance at every transaction. Count conservation is double-entry bookkeeping for data — every event that enters the system must exit it or be explicitly written off. |
| **Kleppmann & Riccomini, DDIA 2nd ed. (2026), Ch.12 pp.524–526** | "Violations of timeliness can be fixed by waiting; violations of integrity are permanent." A silent count drop is a permanent integrity violation — there is no eventual consistency that recovers the missing fatalities. |
| **Kleppmann & Riccomini, DDIA 2nd ed. (2026), Ch.10 pp.397–398** | Batch processing treats inputs as immutable. Count conservation is the batch-processing equivalent of transactional integrity: the sum of outputs must equal the sum of inputs, or the batch has a bug. |
| **ISO 19157:2013 — Geographic information: Data quality** | Defines completeness as a data quality element with two sub-elements: commission (excess data) and omission (missing data). Count conservation is an omission guard; hierarchical reconciliation is a commission/omission consistency guard. |
| **Tollefsen, Strand, Buhaug (2012), "PRIO-GRID: A unified spatial data structure"** | PRIO-GRID methodology uses area-weighted assignment for gridded data. The reconciliation family concept formalizes which spatial assignments must be mutually consistent. |
| **Kimball dimensional modeling** | Conformed dimensions reconcile across fact tables. A reconciliation family is the VIEWS equivalent of a conformed dimension: GAUL admin levels 0, 1, and 2 are conformed because they derive from the same source, just as Kimball's "customer" dimension must reconcile across sales and support fact tables. |

---

## Consequences

### Positive

- **C-149 class of bugs becomes structurally impossible.** Any silent count drop triggers an assertion failure at the layer boundary where it occurs, not a post-hoc audit weeks later.
- **Country-month consumers can trust that totals reflect all events.** The accounting equation makes exclusions explicit — a researcher knows whether the CM total is 100% of PGM or 96% of PGM, and why.
- **The reconciliation family concept prevents future spatial system mismatches.** When a new administrative system is added, its relationship to existing systems is classified before any code is written.
- **Extends ADR-013's lossless guarantee from one layer to the entire pipeline.** ADR-013 says "no data is ever lost" within consolidation. This ADR says "no count is ever silently lost" across all layers.
- **Provenance ledgers gain accounting semantics.** Exclusion counts in the ledger are not just informational — they are one side of a mandatory equation.

### Negative

- **Every new layer transition requires an accounting assertion.** This adds test surface and validation code at each boundary. The cost is accepted: the alternative is silent data loss.
- **The reconciliation family table must be maintained.** When new spatial systems are added, someone must classify them. If the classification is wrong (two systems are declared as the same family but their boundaries don't actually nest), the reconciliation test will fail — which is the correct behavior.
- **Float32 summation ordering affects equality.** Summing 13,110 grid cells per country in different orders produces different totals due to floating-point non-associativity. Reconciliation tests must use appropriate tolerances (`atol`, not exact equality). This is a well-understood limitation of IEEE 754 arithmetic, not a flaw in the invariant.
- **Conservation is only defined for extensive quantities.** Features like HDI, democracy scores, and built-up fraction are not covered. If a future consumer needs "conservation" semantics for intensive features (e.g., area-weighted average preservation), a separate ADR is needed.

---

## Validation & Monitoring

### Viewpoint → Compilation

**Location:** `src/datafactory_compilation/grid_compilation.py`, `_place_events_columnar`, lines 103–151.

The variables `n_skipped_spatial` and `n_skipped_temporal` already exist. Add assertion:

```python
n_placed = len(row_bins)
assert n_placed + n_skipped_spatial + n_skipped_temporal == table.num_rows, (
    f"Count conservation: {n_placed} placed + {n_skipped_spatial} skipped_spatial "
    f"+ {n_skipped_temporal} skipped_temporal != {table.num_rows} input rows"
)
```

**Test:** `tests/test_compiler.py` — add accounting verification to compilation tests.

### Assembly → Country-Month

**Location:** `src/datafactory_adapters/grid_to_country_month.py`, lines 73–99.

The exclusion mask and count already exist. Add post-aggregation verification:

```python
grid_total = float(np.nansum(flat_data[:, event_idx]))
cm_total = float(result[feature].sum())
excluded_total = float(np.nansum(flat_data[excluded_mask][:, event_idx]))
assert abs(grid_total - (cm_total + excluded_total)) < atol, (
    f"Count conservation: grid={grid_total}, cm={cm_total}, "
    f"excluded={excluded_total}, gap={grid_total - cm_total - excluded_total}"
)
```

**Test:** `tests/test_pipeline_consistency.py::TestPGMCMAggregation` — extend with full accounting equation.

### Hierarchical Reconciliation

**New test location:** `tests/test_pipeline_consistency.py` or `tests/test_count_conservation.py`.

For each count feature, load the assembled grid with `gaul0_code`, `gaul1_code`, `gaul2_code` channels. Group by `gaul0_code` and sum. Group by `gaul1_code`, sum, then re-group by parent `gaul0_code` and sum. Assert the two sums are identical (within float tolerance).

The `gaul1_to_gaul0` mapping is derivable from the assembled grid: for each cell, its `(gaul1_code, gaul0_code)` pair defines the hierarchy. No additional data artifact is needed.

### End-to-End Count Trace

**Test location:** `tests/test_pipeline_consistency.py`.

Trace a single count feature from viewpoint through compiled grid, assembled grid, and country-month output. The total should be accounted for at every stage:

```
consolidation_output = consolidation_input - n_dedup_removed - n_records_replaced + n_records_replaced
                     = consolidation_input - n_dedup_removed
viewpoint_total = viewpoint_placed + viewpoint_filtered
viewpoint_placed = grid_total
grid_total = cm_total + excluded_total
```

At the consolidation boundary, ACLED's cross-run replacement (`n_records_replaced` in the ledger) is a swap, not a loss: the same number of records are removed from the existing store as are added from the new harvest. The net count change is `n_records_new` (genuinely new event IDs). The `n_dedup_removed` term accounts for cross-file deduplication within a single run.

---

## Notes

This ADR is **constitutional** — it defines count integrity principles that apply to all data sources and all layer transitions, not just UCDP or GAUL. Any future data source that provides count data (event counts, fatality estimates, population counts) is automatically covered by Invariant 1. Any future administrative system with hierarchical levels is automatically covered by Invariant 2.

### Float32 summation

Grid data is stored as float32. Summing *N* cells in different orders can produce different totals due to floating-point non-associativity. For example, summing 13,110 cells for a large country may differ by O(10⁻³) depending on reduction order. Reconciliation and conservation tests must use `numpy.testing.assert_allclose` with an appropriate absolute tolerance, not exact equality. The invariant is mathematical; the implementation must account for IEEE 754 arithmetic.

### Magnitude monitoring

Count conservation permits exclusions as long as they are accounted for. This creates a theoretical risk: if 50% of events are "excluded with documentation," the invariant is technically satisfied but practically useless. The provenance ledger should record exclusion magnitudes (both absolute counts and percentages) so that operational monitoring can flag anomalous exclusion rates. The threshold for "anomalous" is an operational decision, not an architectural one — this ADR does not prescribe it.

---

## References

- `reports/postmortem_cm_unmapped_gaul_cells.md` — the C-149 incident that motivates this ADR
- `reports/technical_risk_register.md` — C-149 entry (Tier 2, resolved)
- `src/datafactory_compilation/grid_compilation.py:103–151` — existing skip-count variables
- `src/datafactory_adapters/grid_to_country_month.py:73–99` — existing exclusion logic and warning
- `tests/test_pipeline_consistency.py` — existing cross-layer consistency tests
- ADR-013 (Consolidation Principles) — lossless guarantee within Layer 2; this ADR extends it cross-layer
- ADR-014 (Viewpoints as Derived Views) — viewpoint filtering is permitted but must be accounted for
- ADR-024 (Compilation Grid Invariants) — structural layout invariants; this ADR adds count integrity
- ADR-025 (Country Identity Uses GAUL Codes) — GAUL assignment and unmapped cells (lines 96–102)
- Kleppmann & Riccomini, *Designing Data-Intensive Applications*, 2nd ed., O'Reilly 2026:
  - Ch.1 pp.10–11: Systems of record; if there's a discrepancy, the system of record wins
  - Ch.10 pp.397–398: Batch processing treats inputs as immutable; outputs replace atomically
  - Ch.12 pp.524–526: "Violations of timeliness can be fixed by waiting; violations of integrity are permanent"
- ISO 19157:2013 — Geographic information: Data quality (completeness dimension)
- FAO GAUL Release Note 02 — area-majority assignment specification for gridded data
- Tollefsen, Strand, Buhaug (2012). "PRIO-GRID: A unified spatial data structure." *Journal of Peace Research* 49(2): 363–374.
- Pacioli (1494). *Summa de Arithmetica, Geometria, Proportioni et Proportionalità*. Venice. — double-entry bookkeeping as the original count conservation invariant.
