
# ADR-049: Spatial Distribution of Imprecise UCDP Events (Known Geographical Imprecision)

**Status:** Accepted
**Date:** 2026-06-28
**Deciders:** Simon Polichinel von der Maase, Claude Code
**Applies:** ADR-014 (Viewpoints as Derived Views), ADR-015 (UCDP Consolidation), ADR-023 (Viewpoint Builder Invariants), ADR-040 (Count Conservation), ADR-044 (Source Taxonomy)

> **Amended 2026-11-04** — see *Amendment 2026-11-04* below. One statement in **Context** was wrong
> about the code and is corrected there; the relationship between this decision and the profile the
> production pipeline invokes was never recorded and now is. The Decision itself is unchanged.

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
| 4 | Admin-1 region | Centroid cell's GAUL admin-1 code via `gaul1_code.parquet` crosswalk |
| 5 | Admin-1 region | Centroid cell's GAUL admin-1 code via `gaul1_code.parquet` crosswalk |
| 6 | Country | Centroid cell's GAUL country code via `gaul0_code.parquet` crosswalk |

All precision levels use the same mechanism: the centroid PRIO-GRID cell is looked up in the precomputed GAUL crosswalk parquet to find the containing polygon. No free-text field parsing or name matching is required.

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

## Amendment 2026-11-04 — which profile, and a correction (#533)

Prompted by views-datafactory#533 and the catalog in
`reports/investigation_summary_event_concentration/findings.md`. The **Decision above stands
unchanged**; this amendment corrects one factual error in Context and records a relationship the
original left implicit. Dated amendment, not a rewrite, per the register's editorial rule.

### 1. Correction to Context

Context states that the Tigray event (id 463131) *"is spread across 12 months by temporal
distribution (correct) but dumped into one cell spatially (incorrect)."*

**The first half is wrong.** Measured 2026-11-04 against the `production_parity` viewpoint output,
event 463131 produces **exactly one output row**, at `date_month` 2021-12-01. It is not spread at
all. The cause is the profile's `source_distribution_map` entry sending annual-source events to
`date_end_only`, which assigns one row at `date_end` whatever the span, and event 463131 is
annual-source. The temporal override wins over `ceil_split` for that source type.

So the asymmetry the original Context described is real but **both halves concentrate**, not one.
That strengthens rather than weakens the case for this ADR's decision; it was simply mis-stated.
The temporal half remains an open question and is **not** settled by this ADR.

### 2. The decision was implemented; the invoked profile overrides it

This has caused confusion and is worth stating precisely, because an earlier reading of the same
evidence concluded wrongly that this ADR "was never implemented."

**It was.** `proportional` in `spatial_distribution.py` implements §3's mechanism in full — polygon
determination through the GAUL crosswalks, proportional weighting by well-located fatalities, uniform
fallback, and exact conservation by floor-plus-remainder — and it is covered by 46 unit tests in
`tests/test_spatial_distribution.py`. The viewpoint builder wires it, builds the weight map whenever
the strategy is not `passthrough`, and records the strategy in the provenance ledger.
**`ViewpointConfig.spatial_distribution_strategy` defaults to `"proportional"`, which honours §6's
"on by default" exactly as written.**

What was never recorded is the join to production. Until 2026-11-04 the only registered UCDP profile
was `production_parity`, which overrides the default back to `passthrough` to reproduce VIEWSER's
`GedLoader` — a legitimate use of the configurability §6 provides. But:

- §6's **recommended** behaviour had no profile name, so it could not be selected, compared, or
  tested end to end; and
- **no test asserted either choice**, so the ADR and the invoked configuration could drift apart in
  silence — and did, unnoticed, for four months.

§Validation's golden criterion (cell 148759 dropping from 273,076 to its proportional share) was
therefore never checkable. The cell's all-history total has since **grown to 274,358** under
`passthrough`, and nothing went red, because nothing was watching. That is concern C-365's mechanism
recurring: a decision with no observer.

### 3. What this amendment adds

**A name for the recommendation.** Profile **`kgi_distributed`** is registered in `profiles.py`. It
differs from `production_parity` in exactly one concern — how events whose own `where_prec` disowns
their cell are handled — which takes two fields, because §6 frames drop, passthrough and distribute
as three options on one mechanism:

| field | `production_parity` | `kgi_distributed` |
|---|---|---|
| `spatial_distribution_strategy` | `passthrough` | `proportional` |
| `exclude_where_prec` | `(4, 6)` | `()` |

The temporal axis is left identical. One variable at a time.

Two consequences of `exclude_where_prec=()` worth naming: `where_prec` 7 (276 events) and an
**undocumented `where_prec = 99`** (19 events, 84 fatalities, absent from the UCDP codebook) also
flow in, both routed to the country polygon by the `>= 6` branch. That is the intended graceful
degradation of §Rationale, but it had not been considered for value 99 and is recorded here so it is
a decision rather than an accident.

**Observers, so this cannot recur.** `tests/test_adr049_profile_contract.py` pins:

- every strategy field of `production_parity`, so a parity break must be deliberate;
- that `scripts/build_viewpoint.py` still defaults to `production_parity`, so switching what
  production runs cannot happen by diff;
- that `ViewpointConfig`'s default is still `proportional`, i.e. that §6 and the code still agree;
- that `kgi_distributed` differs from parity in exactly the two fields above;
- **§Validation's golden criterion on the real event** — the centroid's share collapses, the
  allocation matches the weight map cell by cell to within the rounding tolerance, and `best`, `low`
  and `high` are each conserved exactly.

The proportionality assertion exists because of a mutation that survived without it: concentrating
the whole total onto a *different* single cell left the centroid at zero and passed the
"centroid share fell" check. A guard that cannot distinguish distribution from relocation is not a
guard for this ADR.

### 4. What this amendment does **not** decide

**It does not change what the production pipeline invokes.** `scripts/build_viewpoint.py` still
defaults to `production_parity`, and the monthly pipeline still calls it. Switching to
`kgi_distributed` would move every published grid-level fatality figure for `where_prec >= 4` events
and invalidate the ADR-041 content digests, so it is a separate decision requiring agreement on the
VIEWSER-parity contract. It should also wait on evidence: whether §3's proportional weighting beats
uniform allocation by enough to justify its extra assumption has **never been measured**, and
`reports/2026-11-04_summary_event_allocation_dossier/` exists to measure it.

**It does not revisit the Deferred section**, though new literature bears on it directly — see
`Croicu2026` in that dossier's literature review, which finds actor-level modelling essential rather
than premature and treats location sampling as data preparation rather than a downstream concern.
Both deferrals are left standing here and raised as decisions in the dossier's roadmap.

---

## References

- `reports/2026-06-28_ucdp_spatial_distribution_of_low_precision_summary_events.md` — Original investigation report
- `src/datafactory_viewpoint/temporal_distribution.py` — Temporal distribution registry (architectural template)
- ADR-023 — Viewpoint Builder Invariants (temporal distribution decisions)
- ADR-040 — Count Conservation and Hierarchical Reconciliation
- ADR-044 — Source Taxonomy: Reference Infrastructure vs Feature Sources
- UCDP GED Codebook — `where_prec` field definitions
