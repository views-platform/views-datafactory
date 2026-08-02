# ADR-036: GDL Subnational HDI (SHDI) as First Admin-1 Socioeconomic Source

**Status:** Accepted
**Date:** 2026-05-29
**Deciders:** Simon Polichinel von der Maase, Claude Code
**Applies:** ADR-012 (Four-Layer Data Architecture), ADR-029 (skip consolidation precedent), ADR-033 (Data Source Catalog), ADR-034 (GHS-BUILT-S pattern), ADR-035 (V-Dem pattern)

---

## Context

The assembled grid carries conflict events (UCDP, ACLED), population (GHS-POP), built-up surface (GHS-BUILT-S), static geography (PRIO-GRID), administrative codes (GAUL), and democracy indicators (V-Dem). All socioeconomic data is either country-level (V-Dem) or grid-level (GHS-POP/BUILT-S). There is no subnational socioeconomic indicator — no measure of human development that varies within countries.

The Global Data Lab (GDL) publishes the Subnational Human Development Index (SHDI), covering 1,801 administrative regions across 188 countries from 1990 to 2023. SHDI provides a composite HDI plus three sub-indices (health, education, income) at admin-1 resolution — finer than V-Dem's country level but coarser than PRIO-GRID's 0.5° cells.

SHDI is the 6th data source contributing features to the assembled grid (8th overall counting PRIO-GRID Shapefile and GAUL Admin which don't contribute features directly).

### The crosswalk problem

GDL uses a proprietary region coding system (GDL-Code V6.5). These codes are not GAUL, not ISO 3166-2, and not GADM. No official GDL-to-GAUL or GDL-to-GADM mapping exists. However, GDL publishes shapefiles (GDL Shapefiles V6.5) containing the polygons for all 1,801 regions with matching GDL codes.

This means we can map GDL regions to PRIO-GRID cells via a direct spatial join — the same STRtree centroid-in-polygon technique already used for GAUL admin boundaries.

---

## Decision

**GDL SHDI** is the 6th feature-producing data source for the VIEWS data factory, contributing 4 subnational human development features to the assembled grid.

### Variable selection

4 variables selected from the SHDI dataset:

| Variable | Description | Scale |
|----------|-------------|-------|
| `shdi` | Subnational Human Development Index (composite) | [0, 1] |
| `healthindex` | Health sub-index (life expectancy) | [0, 1] |
| `edindex` | Education sub-index (schooling years) | [0, 1] |
| `incindex` | Income sub-index (GNI per capita, log) | [0, 1] |

### In scope

- Harvesting SHDI CSV from the GDL Data API (token-based authentication, ADR-026)
- Downloading GDL shapefiles from PRIO CDN (no authentication)
- Spatial join crosswalk: GDL shapefiles → PRIO-GRID centroids → `gdl_to_pgid.parquet`
- Viewpoint building: region-year → region-month expansion with GDL→pgid crosswalk
- Compilation via `compile_pregridded` to [T, H, W, C] npy arrays
- Integration into the assembled grid as 4 features (all prefixed `shdi_`)

### Out of scope

- GDL's other indicators (poverty, inequality, gender) — add via future ADR if models need them
- Temporal interpolation within years — SHDI is annual
- Subnational disaggregation below admin-1 — the source data does not vary within GDL regions
- GDL's other datasets beyond SHDI — add via future ADR if models need them

---

## Rationale

### SHDI fills the subnational socioeconomic gap

V-Dem provides country-level institutional indicators. SHDI provides subnational socioeconomic indicators. Together they give models both political and development covariates at complementary spatial resolutions.

### Direct spatial join is the only viable crosswalk

No official GDL→GAUL or GDL→GADM mapping exists. Building a GDL→GAUL mapping would itself require a spatial join between GDL and GAUL polygons — at which point we might as well join GDL directly to PRIO-GRID centroids and skip the intermediary. Direct join also avoids boundary misalignment between GAUL and GDL administrative definitions.

The pattern is proven: `_spatial_join()` in `gaul_admin.py` uses the identical STRtree centroid-in-polygon approach for GAUL admin boundaries.

### Consolidation: skipped

Same rationale as GHS-POP (ADR-029), GHS-BUILT-S (ADR-034), and V-Dem (ADR-035): SHDI is a single periodic release with nothing to merge or deduplicate between snapshots.

### 4 features is the right scope

SHDI's 4 indices (composite + 3 sub-indices) are the core product. GDL's other indicators (poverty, inequality) are separate datasets with different update cycles. Starting with 4 features avoids scope creep while providing the key development signal.

---

## Considered Alternatives

### Alternative A: GDL→GAUL→pgid (indirect crosswalk)

- **Pros:** Reuses existing GAUL infrastructure; GAUL codes are already in the grid
- **Cons:** No official GDL→GAUL mapping exists. Building one requires a spatial join between GDL and GAUL polygons. Boundary misalignment between GDL and GAUL definitions introduces systematic error.
- **Reason for rejection:** The indirect path requires the same spatial join work as the direct path, plus an extra intermediary that adds error. Direct join is strictly simpler and more accurate.

### Alternative B: GADM admin boundaries as intermediary

- **Pros:** GADM is widely used, has ISO 3166-2 codes
- **Cons:** Same problem — no official GDL→GADM mapping. GADM boundaries don't align exactly with GDL boundaries. Adds a dependency on GADM data.
- **Reason for rejection:** Same reasoning as Alternative A. No intermediary avoids the mapping problem entirely.

### Alternative C: Manual region-to-country mapping + V-Dem-style country broadcast

- **Pros:** Avoids spatial join entirely; simple lookup table
- **Cons:** Destroys the subnational signal, which is the entire point of using SHDI instead of a country-level indicator.
- **Reason for rejection:** Defeats the purpose of the data source.

---

## Consequences

### Positive

- First subnational socioeconomic indicator in the grid
- Direct spatial join pattern is reusable for any future admin-1 source
- 4 new features for 1.8 GB compile cost (well within server RAM)
- Fills a gap identified by production model teams

### Negative

- GDL API requires free registration for API token — one-time operator setup
- GDL shapefile quality is unverified (Phase 0 investigation will assess)
- One-to-many crosswalk: each GDL region maps to many pgids, so all pgids within a region share the same value (same pattern as V-Dem country broadcast, but at admin-1 resolution)
- Spatial join must be rerun if GDL updates their shapefile version

---

## Implementation Notes

- **Harvester:** `src/datafactory_harvester/sources/shdi.py` — downloads SHDI CSV from GDL Data API (`GDL_API_TOKEN` env var, ADR-026), GDL shapefiles from PRIO CDN (no auth), produces `shdi_v10.2.parquet` + `gdl_to_pgid.parquet`
- **Data API:** `https://globaldatalab.org/shdi/download/{indicator}/?format=csv&token={token}` — one request per indicator (combined URL returns only latest year; discovered during live smoke test)
- **Shapefile CDN:** `https://cdn.cloud.prio.org/files/604a306f-80de-49af-8610-948af8e2e474/GDL%20Shapefiles%20V64.zip` — cached locally after first download
- **Spatial join:** Reuse the STRtree pattern from `_spatial_join()` in `gaul_admin.py`. Load PRIO-GRID centroids, build STRtree index of GDL polygons, join centroid → polygon.
- **Crosswalk output:** `data/raw/shdi/gdl_to_pgid.parquet` with schema `(gid: int32, gdl_code: string)`
- **Feature naming:** `shdi_shdi`, `shdi_healthindex`, `shdi_edindex`, `shdi_incindex`
- **Viewpoint (Sprint 2):** Same pattern as `vdem_v1.py` — read crosswalk, expand annual → 12 monthly rows, broadcast to pgids
- **Compilation (Sprint 2):** `compile_pregridded()` with 4 `PregriddedFeatureSpec` entries

---

## Validation & Monitoring

- Crosswalk coverage: expect ~85,000+ of 86,091 pgids mapped (ocean/Antarctica cells unmapped)
- Every GDL code in the CSV must appear in the shapefile (cross-validation)
- Grid output: 4 features × [T, 360, 720] with NaN for unmapped cells and years before 1990
- Verification script (Sprint 2): plot spatial coverage, temporal completeness, value distributions

---

## Open Questions

1. **Shapefile CRS** — expected WGS84 (EPSG:4326) but needs confirmation for spatial join compatibility
2. **Missing value encoding** — how does GDL encode missing data in the CSV? (blank, NA, -999?)

---

## References

- GDL SHDI data: https://globaldatalab.org/shdi/
- GDL Data API: token-based REST API (discovered via GDL R package source code)
- GDL R package (API reference implementation): https://github.com/GlobalDataLab/R-package
- PRIO CDN shapefile mirror: https://cdn.cloud.prio.org/files/604a306f-80de-49af-8610-948af8e2e474/GDL%20Shapefiles%20V64.zip
- ADR-026: Credential Management Strategy (token resolution pattern)
- GAUL spatial join pattern: `_spatial_join()` in `src/datafactory_harvester/sources/gaul_admin.py`
- V-Dem harvester (pattern source): `src/datafactory_harvester/sources/vdem.py`
- Sprint plan: `reports/sprint_plan_admin1_crosswalk.md`
