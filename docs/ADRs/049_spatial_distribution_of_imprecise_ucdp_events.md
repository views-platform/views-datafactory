
# ADR-049: Spatial Distribution of Imprecise UCDP Events (Known Geographical Imprecision)

**Status:** Accepted
**Date:** 2026-06-28
**Deciders:** Simon Polichinel von der Maase, Claude Code
**Applies:** ADR-014 (Viewpoints as Derived Views), ADR-015 (UCDP Consolidation), ADR-023 (Viewpoint Builder Invariants), ADR-040 (Count Conservation), ADR-044 (Source Taxonomy)

---

## Context

UCDP GED encodes spatial uncertainty in the `where_prec` field: 1 = exact point, 2 = ≤25 km, 3 = admin-2, 4 = admin-1, 5 = larger than admin-1, 6 = country, 7 = international. When spatial precision is low (≥ 4), UCDP geocodes the event to a **regional centroid** — a single lat/lon point representing an entire administrative region, sub-national area, or country.

The data factory's viewpoint builder already handles the **temporal** analog: `temporal_distribution.py` spreads imprecise-date events across their spanned months (ADR-023). But there is **no spatial analog**. An event with `where_prec = 5` whose deaths span "northern Ethiopia" is placed entirely into the single PRIO-GRID cell containing the centroid (Mekelle, cell 148759).

This produces false hotspots. Cell 148759 accumulates 273,076 deaths over all history — a quarter of a million fatalities in a single 55×55 km grid square. For scale, the 99.99th percentile of the PGM target is 255. This is not a single-event outlier: the Eritrea–Ethiopia border war (1999–2000) creates the same artifact at cell 150919 (79,841 deaths), confirming a systemic mechanism keyed on `where_prec`, not a data entry error.

The asymmetry is concrete: the Tigray war event (id 463131, 113,368 deaths, `date_prec = 5`, `where_prec = 5`) is spread across 12 months by temporal distribution (correct) but dumped into one cell spatially (incorrect). The temporal and spatial imprecision are the same kind of problem and warrant the same kind of solution.

### Current behavior

The `production_parity` viewpoint profile sets `exclude_where_prec=(4, 6)`, which **drops** events with `where_prec` 4 (admin-1) and 6 (country). Events with `where_prec = 5` are **not excluded** — they pass through to the centroid cell. This gap is where the largest false hotspots occur.

### Scale

The consolidated UCDP store contains 20,787 unique events with `where_prec = 5`, totaling 806,959 deaths (deduplicated). Of these, 72% have a populated `adm_1` field (admin-1 region known); 28% lack `adm_1` but all have `country_id` (100%).

---

## Decision

### 1. Spatial distribution strategy

Add a `spatial_distribution.py` module in the viewpoint layer, mirroring `temporal_distribution.py`. For any event with `where_prec` ≥ 4, instead of placing all deaths in one centroid cell, **distribute deaths across the cells of the event's target polygon, weighted proportionally by existing well-located fatalities in those cells**.

"Well-located" means events with `where_prec` ≤ 3 (location known to admin-2 or better). These provide the spatial conflict pattern used as weights. Cells with zero well-located fatalities receive zero distributed deaths. This ensures deaths are placed where conflict is empirically observed, not spread into peaceful cells.

### 2. Polygon determination by precision level

The same two-step mechanism applies at all levels — only the polygon source varies:

| `where_prec` | Polygon | How determined |
|--------------|---------|----------------|
| 4 | Admin-1 region | `adm_1` field from UCDP, matched to GAUL admin-1 polygon |
| 5 (with `adm_1`) | Admin-1 region | `adm_1` field from UCDP, matched to GAUL admin-1 polygon |
| 5 (without `adm_1`) | Admin-1 region | Spatial join of centroid lat/lon against GAUL admin-1 boundaries |
| 6 | Country | `country_id` from UCDP, matched to GAUL country polygon |

For `where_prec = 5` without an `adm_1` field, the centroid coordinates that UCDP provides are joined against GAUL to find the containing admin-1 polygon. This is a coordinate-based spatial operation — no free-text parsing of `where_coordinates`.

### 3. Proportional weighting

Within the target polygon, deaths are distributed proportionally to existing well-located fatalities:

```
cell_share = well_located_deaths_in_cell / well_located_deaths_in_polygon
cell_allocation = event_best × cell_share
```

If the target polygon has zero well-located fatalities (rare — would mean no precisely-located conflict has ever been recorded there), fall back to uniform distribution across the polygon's cells.

### 4. Composition with temporal distribution

Events with both temporal and spatial imprecision (e.g., Tigray: `date_prec = 5` and `where_prec = 5`) require both strategies. Order of application: **temporal first, then spatial**. Temporal distribution produces per-month records; spatial distribution then distributes each month's total across cells. Each stage conserves independently.

### 5. Conservation

Total deaths are conserved: the sum of distributed deaths across all target cells equals the original `best` (and `low`, `high`), subject to a documented rounding policy. This extends ADR-040's count conservation invariant to the spatial dimension.

### 6. Default behavior

Spatial distribution is **on by default** for all events with `where_prec` ≥ 4. This is the datafactory's recommended behavior — it conserves total deaths and eliminates false hotspots. The existing `exclude_where_prec` option and a pass-through option remain available for researchers who need alternative handling:

- **Distribute (default):** Spread deaths across the target polygon proportionally. Conserves total deaths. Introduces a spatial allocation assumption.
- **Drop:** Remove the event entirely. Loses real deaths but eliminates false hotspots. To approximate viewser production parity, set `exclude_where_prec=(4, 6)` and disable spatial distribution for `where_prec = 5` — this replicates the legacy behavior where `where_prec` 4 and 6 are dropped and 5 passes through to the centroid cell.
- **Pass-through:** Do nothing; deaths land in the centroid cell. Creates false hotspots. Not recommended.

All three options remain configurable per `where_prec` level. Researchers choose based on their analysis requirements.

### 7. No cross-source dependency

The weighting uses only UCDP's own well-located events — no other feature source (GHS-POP, V-Dem, etc.) is read. GAUL admin boundaries are spatial infrastructure (ADR-044: reference source), not a cross-source dependency.

### 8. Provenance

Every spatially distributed event carries provenance annotation: the original event ID, the distribution strategy applied, the target polygon identifier, and the number of cells across which deaths were distributed. This supports audit and reproducibility.

---

## Deferred

### Actor-informed distribution

UCDP events carry structured actor fields (`side_a`, `side_b`, `dyad_name`). In principle, the spatial footprint of well-located events for a specific actor dyad could provide more discriminating weights than all-conflict fatalities within a polygon. Deferred because: (a) actor name normalization across UCDP versions is non-trivial, (b) some actors appear only in summary events with no well-located history, and (c) this approaches a conflict-process model rather than a data materialization step.

### Input uncertainty sampling

A more principled treatment of known geographical imprecision (KGI) would represent each imprecise event as a distribution over cells rather than a point allocation. This would compose with analogous treatment of temporal imprecision and propagate uncertainty to downstream models. This is a future capability that belongs in a downstream transformation or modeling layer, not in the viewpoint.

Both deferred approaches may be revisited when the platform's input uncertainty infrastructure matures.

---

## Rationale

- **Mirror of temporal distribution:** The viewpoint layer already makes temporal allocation decisions for imprecise events (ADR-023). Spatial allocation is the same kind of decision at the same layer. Doing one but not the other is an inconsistency, not a principled boundary.
- **Proportional over uniform:** Uniform distribution spreads deaths into cells with no observed conflict, creating implausible low-level noise everywhere. Proportional distribution places deaths where fighting is empirically observed — a weaker assumption than population weighting (which would require cross-source data) but stronger than uniform.
- **Distribute over drop:** Dropping `where_prec` ≥ 4 events loses real deaths systematically. Models trained on data with missing fatalities underestimate conflict intensity — a silent bias arguably worse than the spatial concentration bias of proportional distribution.
- **Country-level distribution for `where_prec = 6`:** With proportional weighting, country-level distribution is not as diffuse as it appears — deaths only flow to cells with existing conflict, which constrains the spread to conflict-affected areas within the country.
- **Graceful precision degradation:** The strategy's spatial resolution degrades naturally with source precision: admin-1 polygon for `where_prec` 4–5, country polygon for `where_prec` 6. Less precise source data produces more diffuse distribution, which is the honest behavior.

---

## Consequences

### Positive

- Eliminates false hotspots: cell 148759 (Mekelle) drops from 273,076 to a realistic share of Tigray-region fatalities.
- Conserves total deaths: no signal lost, unlike the drop strategy.
- Consistent with temporal distribution: the viewpoint layer now handles both dimensions of UCDP imprecision symmetrically.
- Viewser parity remains achievable via configuration (§6) for researchers who need it.

### Negative

- Spatial allocation is a modeling assumption. Proportional weighting assumes imprecise events follow the same spatial pattern as well-located events. This is reasonable for civil wars (fighting clusters geographically) but may not hold for all conflict types.
- Reinforces spatial concentration: cells with existing conflict receive more distributed deaths, which could amplify existing patterns. This is a known property of the weighting, not a hidden bias.
- Composition complexity: temporal × spatial distribution requires careful ordering and independent conservation checks at each stage.

---

## Validation & Monitoring

- **Golden test (Tigray):** After spatial distribution, cell 148759's all-history total should drop from 273,076 to its proportional share within the Tigray admin-1 region. The sum across all cells in the region must equal 273,076 (± rounding).
- **Conservation assertion:** `sum(distributed_cells) == original_best` for every distributed event.
- **Provenance counters:** The viewpoint builder logs `n_spatially_distributed`, `n_excluded_where_prec`, and `n_passthrough_where_prec` to the provenance ledger for audit.

---

## References

- `reports/2026-06-28_ucdp_spatial_distribution_of_low_precision_summary_events.md` — Original investigation report
- `src/datafactory_viewpoint/temporal_distribution.py` — Temporal distribution registry (architectural template)
- ADR-023 — Viewpoint Builder Invariants (temporal distribution decisions)
- ADR-040 — Count Conservation and Hierarchical Reconciliation
- ADR-044 — Source Taxonomy: Reference Infrastructure vs Feature Sources
- UCDP GED Codebook — `where_prec` field definitions
