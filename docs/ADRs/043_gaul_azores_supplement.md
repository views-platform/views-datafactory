# ADR-043: GAUL Azores Supplement with Natural Earth Polygons

**Status:** Accepted
**Date:** 2026-06-12
**Deciders:** Simon Polichinel von der Maase, Claude Code
**Applies:** ADR-039 (Area-Majority GAUL Assignment)

---

## Context

FAO's GAUL 2024 shapefile is missing 4 of 9 Azorean islands from both L1 and L2 resolution levels:

| Missing island | Population | GAUL L1 present? |
|---|---|---|
| Ilha de Sao Miguel | ~140,000 | No |
| Ilha de Santa Maria | ~6,000 | No |
| Ilha das Flores | ~3,800 | No |
| Ilha do Corvo | ~430 | No |

The other 5 Azorean islands (Terceira, Graciosa, Sao Jorge, Faial, Pico) are present with L1 codes 3720-3726. Zero null geometries exist in the shapefile — the 4 islands are simply absent from the file FAO distributes. This was confirmed by scanning both L1 (3,110 records) and L2 (45,524 records) shapefiles exhaustively.

The gap affects 6 PRIO-GRID cells (GIDs 182470, 183190, 183909, 183910, 186058, 186778) which were excluded from the `land_gaul` region. Conflict-forecasting impact is near zero (the Azores are not a conflict zone), but this is a data-integrity issue: the largest island in the Azores — with 140,000 inhabitants — was silently excluded from all country-level aggregations.

Investigation: `scripts/investigate_gaul_excluded_cells.py`, `reports/investigation_gaul_excluded_cells/`.

---

## Decision

Supplement the GAUL shapefile with Natural Earth 10m admin-1 polygons for the 4 missing Azorean islands. The supplement is loaded by `generate_area_majority_gaul.py` via a `--supplement` argument and appended to the GAUL polygon list before the area-majority join.

### Supplement file

`data/raw/gaul_admin/supplement_azores.geojson` — 4 features extracted from Natural Earth's `ne_10m_admin_1_states_provinces` dataset (CC0 public domain). Each feature carries GAUL-compatible attributes:

- `gaul0_code`: 325 (Portugal — matches GAUL)
- `gaul0_name`: "Portugal"
- `gaul1_code`: Negative synthetic codes (-3727 to -3730) — clearly distinguishable from FAO-assigned codes
- `gaul1_name`: GAUL naming convention ("Ilha de Sao Miguel", etc.)
- `gaul2_code`: Same negative code as `gaul1_code` (each island is a single admin unit; using -1 would collide with the "unassigned" sentinel and break hierarchy nesting checks)
- `gaul2_name`: Same as L1 name
- `iso3_code`: "PRT"
- `source`: "natural_earth_10m_supplement"

### Integration

`generate_area_majority_gaul.py` accepts `--supplement <path>`. If provided, supplement polygons are appended after GAUL polygons. The area-majority join then naturally covers the previously uncovered cells. No special-case logic — the supplement polygons participate in the same spatial join as GAUL polygons.

### Extraction reproducibility

`scripts/extract_azores_supplement.py` downloads Natural Earth 10m admin-1, extracts the 4 missing island polygons from the Azores MultiPolygon, and writes the GeoJSON. The GeoJSON is committed; the script is kept for reproducibility.

### Scope

Azores only. This is not a general-purpose GAUL supplement mechanism. If other GAUL defects are discovered, they should be evaluated individually.

---

## Rationale

### Natural Earth is authoritative and license-compatible

Natural Earth is maintained by the North American Cartographic Information Society (NACIS), used by governments and international organizations, and released under CC0 (public domain). Its 10m admin-1 boundaries are detailed enough for 0.5-degree grid assignment.

### Negative synthetic codes prevent confusion

Using negative gaul1_code values (-3727 to -3730) ensures supplement-assigned cells are immediately distinguishable from FAO-assigned cells in any downstream analysis. Consumers filtering on `gaul1_code > 0` automatically exclude supplement assignments; consumers using `gaul0_code` (the primary use case for country aggregation) get the correct value (325 = Portugal).

### Additive supplement avoids modifying FAO data

The GAUL shapefile is untouched. The supplement only adds polygons for areas GAUL doesn't cover. No GAUL polygon is replaced, modified, or overridden.

---

## Consequences

### Positive

- 6 PRIO-GRID cells recovered for `land_gaul` (64,736 -> 64,742)
- Sao Miguel (140K inhabitants) correctly assigned to Portugal
- Supplement is transparent: negative codes, `source` field, provenance ledger

### Negative

- Supplement must be maintained if Natural Earth admin-1 boundaries change
- gaul1/gaul2 values for supplemented cells are synthetic, not FAO-assigned
- One additional file to track in the repo

### Sunset condition

Remove the supplement when FAO releases a corrected GAUL version that includes the missing Azorean islands. Verify by checking whether the 4 L1 entries appear in the new shapefile. The self-deactivation guard (`_filter_covered_supplements`) automatically detects when GAUL covers a supplement polygon (>50% area overlap) and skips it with a retirement warning.

### Upstream reporting obligation

This supplement patches FAO's own product. FAO must be informed so the defect can be fixed at source:

- **Defect reported to FAO:** Logged in project notes (`~/brain/2_projects/fao02/project_log.md`, entry 2026-06-12). Formal communication pending next PRIO-FAO coordination meeting.
- **Release-note obligation:** Any data delivery that includes supplement-assigned cells must disclose the synthetic negative codes (gaul1_code -3727 to -3730, gaul2_code same) and their Natural Earth provenance. Consumers filtering on `gaul1_code > 0` automatically exclude supplement assignments.

---

## References

- Investigation: `scripts/investigate_gaul_excluded_cells.py`
- Investigation output: `reports/investigation_gaul_excluded_cells/`
- ADR-039: Area-Majority GAUL Assignment
- Natural Earth: https://www.naturalearthdata.com/ (CC0)
- FAO GAUL 2024: https://www.fao.org/agroinformatics/training-and-resources/data-sets/data-set-detail/global-gaul-new-2024-release/en
