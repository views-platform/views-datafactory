# ADR-025: Country identity uses GAUL codes, not G&W / C-Shapes

**Status:** Accepted
**Date:** 2026-04-19
**Deciders:** Simon, views-datafactory maintainers
**Consulted:** HydraNet ADR-032 (authoritative output schema)

---

## Context

The VIEWS platform carries a `c_id` column through the training pipeline. HydraNet ADR-032 §3.2 declares it a "mandatory identity column" — metadata carried losslessly for geographic traceability, not a training feature.

In the legacy system (viewser), `c_id` came from the Gleditsch & Ward (G&W) state system list, mapped through the ETH C-Shapes project. These codes are **time-varying**: a grid cell's country assignment changes as borders change. For example, Sudan and South Sudan share a code before 2011 and have separate codes after. This made `c_id` simultaneously an identity label *and* a time-varying signal about political boundaries — conflating two concerns.

This conflation caused problems:

1. **Identity instability.** The same grid cell has different `c_id` values in different months, making it unreliable as a spatial grouping key for evaluation or aggregation.
2. **Implicit feature leakage.** A "bookkeeping" column that changes over time carries predictive signal (border changes correlate with conflict). If consumed as an identity, this signal is invisible and uncontrolled. If consumed as a feature, its temporal dynamics are undocumented.
3. **Reproducibility.** The G&W/C-Shapes coding depends on which version of the state system list is loaded. Different viewser snapshots produce different `c_id` values for the same cell and month.

The data factory uses **FAO GAUL 2024** (Global Administrative Unit Layers) as its administrative boundary system. The shapefiles are downloaded from FAO's official distribution at `https://storage.googleapis.com/fao-maps-catalog-data/boundaries/GAUL_2024_L{1,2}.zip` (CC-BY-4.0 license). Both the boundary polygons and the country codes (`gaul0_code`) come from the same source dataset. GAUL codes are **time-invariant per grid cell** — a cell belongs to the same country in all months.

---

## Decision

1. The `c_id` column in data factory output uses **GAUL country codes** (`gaul0_code`), not G&W / C-Shapes codes.
2. `c_id` is strictly an **identity column** — a time-invariant spatial label for grouping, tracing, and display. It is never a training feature.
3. If temporal boundary information is needed as a **predictive feature** (e.g., "this cell changed sovereignty in month X"), it must be constructed as an explicit, named feature — not smuggled through the identity column.

**In scope:** The `c_id` coding system used by the data factory and consumer models that source from it (e.g., bright_starship).

**Out of scope:** Modifying viewser's `c_id` or changing how legacy models (e.g., purple_alien) interpret their existing data.

---

## Rationale

Separating identity from signal is a fundamental data hygiene principle. An identity column that changes value over time is a feature pretending to be metadata. By using time-invariant GAUL codes:

- **Identity is stable.** A grid cell always maps to the same `c_id`, regardless of which month is queried. This makes `c_id` safe to use as a group-by key for evaluation, aggregation, and diagnostics.
- **Signal is explicit.** If we want border-change information, we build a feature called `border_change` or `sovereignty_transition` with documented semantics. Researchers see it in the feature list and can reason about it.
- **Reproducibility improves.** GAUL is a single, versioned dataset. The factory harvests it once and the mapping is fixed.

The audit script (`bright_starship/scripts/audit_data_parity.py`) confirmed that viewser's `c_id` has up to 7 different values per grid cell across the calibration partition, while the factory's GAUL-based `c_id` has exactly 1 per cell.

---

## Considered Alternatives

### Alternative A: Keep G&W / C-Shapes codes

- **Pros:** Backward compatibility with viewser output. No documentation of the difference needed.
- **Cons:** Perpetuates the identity/feature conflation. Requires maintaining the G&W state system list and C-Shapes mapping, which are not part of the data factory's GAUL-based admin pipeline.
- **Reason for rejection:** The whole point of the factory is to do things correctly, not to replicate legacy quirks.

### Alternative B: Carry both code systems

- **Pros:** Maximum compatibility.
- **Cons:** Two columns (`c_id_gw`, `c_id_gaul`) doubles the confusion. Which one does HydraNet use? Which does evaluation aggregate by? The answer should be: one authoritative identity, additional features as needed.
- **Reason for rejection:** Complexity without benefit. The G&W codes should be a feature if they carry signal, not a parallel identity system.

---

## Consequences

### Positive

- `c_id` is a reliable spatial grouping key in all factory-sourced models.
- The distinction between "what this cell *is*" (identity) and "what happened *to* this cell" (feature) is explicit.
- Future features like sovereignty transitions, border distance, or state fragility can be designed intentionally with proper documentation.

### Negative

- Factory-sourced models (bright_starship) and viewser-sourced models (purple_alien) have different `c_id` coding. Predictions from the two cannot be directly joined on `c_id` without a mapping table.
- Any downstream system that interprets `c_id` values (e.g., rendering country names) needs to use the GAUL codebook, not the G&W list.

---

## Implementation Notes

- `config_queryset.py` in bright_starship renames `gaul0_code` → `c_id` via `FEATURE_RENAME`. This is the single point where the GAUL code enters the HydraNet pipeline as `c_id`.
- The GAUL admin data is harvested by `datafactory_harvester` from FAO's official GAUL 2024 shapefiles (`https://storage.googleapis.com/fao-maps-catalog-data/boundaries/GAUL_2024_L{1,2}.zip`, CC-BY-4.0). The harvester performs a spatial join (pyshp + shapely STRtree point-in-polygon) against PRIO-GRID centroids. Output is stored in `data/raw/gaul_admin/gaul0_name.parquet`. The mapping from GAUL code to country name is authoritative.
- GAUL codes include `-1` for ocean or unassigned cells. HydraNet treats `c_id` as float64 metadata, so `-1.0` is valid.
- If a GAUL-to-G&W mapping is ever needed for cross-system comparison, it should be a standalone utility, not embedded in the pipeline.

---

## Validation & Monitoring

- `audit_data_parity.py` verifies that factory `c_id` is internally consistent (1 value per pgid) and documents the coding difference vs. viewser.
- If a future model requires time-varying boundary information, the trigger is clear: build an explicit feature, not a modified `c_id`.
- Watch for: downstream aggregation or visualization code that hardcodes G&W country code values.

---

## References

- HydraNet ADR-032 §3.2: `c_id` as mandatory identity column
- HydraNet ADR-030 §2.1: Standard Identity Registry (`priogrid_gid`, `row`, `col`, `month_id`, `c_id`)
- `bright_starship/scripts/audit_data_parity.py`: Parity audit confirming 1 c_id per pgid (factory) vs 7 (viewser)
- `reports/consumer_parity_investigation.md`: Overall parity findings
- FAO GAUL 2024: `https://www.fao.org/agroinformatics/training-and-resources/data-sets/data-set-detail/global-gaul-new-2024-release/en` (CC-BY-4.0)
- Gleditsch & Ward (1999): State system membership list
- Weidmann, Kuse, Gleditsch (2010): CShapes dataset
