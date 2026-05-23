# ADR-034: GHS-BUILT-S as Built-Up Surface Area Source

**Status:** Accepted
**Date:** 2026-05-22
**Deciders:** Simon Polichinel von der Maase, Claude Code
**Applies:** ADR-012 (Four-Layer Data Architecture), ADR-029 (GHS-POP precedent), ADR-030 (tifffile tooling), ADR-031 (Resource Ownership), ADR-032 (Harvest Idempotence)

---

## Context

GHS-POP is proven end-to-end on the production server (v1.2.18). The raster pipeline — harvest GeoTIFF from JRC, aggregate to PRIO-GRID, interpolate temporally, compile to grid — works. The next source should test whether this pipeline generalises beyond a single product.

Built-up surface area is theoretically relevant to conflict forecasting. Urbanisation changes the physical terrain of violence, economic opportunity, population density, and state capacity. Built-up surface is complementary to population: GHS-POP measures *who lives where*, while GHS-BUILT-S measures *what has been built where*. The two together provide a richer structural picture than either alone.

GHS-BUILT-S R2023A is produced by the same institution (JRC/Copernicus), in the same format (Cloud Optimized GeoTIFF), at the same resolution (30 arcsec WGS84), with the same epochs (1975-2030), and distributed from the same infrastructure (no authentication). The implementation effort is minimal relative to the analytical value.

---

## Decision

**GHS-BUILT-S R2023A** (Global Human Settlement Layer - Built-Up Surface grid), produced by JRC under the Copernicus programme, is the second raster data source for the VIEWS data factory.

### In scope

- Harvesting GHS-BUILT-S GeoTIFF files from JRC distribution
- Spatial aggregation from 30 arcsec to 0.5-degree PRIO-GRID cells (sum)
- Temporal interpolation from 12 five-year epochs to monthly time steps
- Integration into the assembled grid as one feature: `ghsbuilts_built_area`

### Out of scope

- GHS-BUILT-V (built-up volume, m^3/cell) — candidate for a future ADR
- GHS-BUILT-H (building height) — derived from V/S ratio, not an independent source
- GHS-BUILT-C (building morphology characteristics) — candidate for a future ADR
- Derived features (built-up density, change rate, urban/rural classification) — future viewpoint variants
- Cross-source derived features (population per m^2 of built-up area) — model-layer concern

---

## Rationale

### Same pipeline shape as GHS-POP

GHS-BUILT-S shares the same pipeline shape: harvest GeoTIFF from JRC, skip consolidation (single release R2023A), aggregate in viewpoint, compile to grid. This validates that the raster infrastructure built for GHS-POP is reusable, not one-off.

### Aggregation is sum

Built-up surface area is measured in m^2 per source pixel. Aggregation to PRIO-GRID cells uses sum — the total built-up area in the cell. This is the same aggregation strategy as GHS-POP (population count), not an opinion that needs new viewpoint logic.

### Data characteristics differ from GHS-POP

Despite the same pipeline shape, the raster data has different properties:

| Property | GHS-POP | GHS-BUILT-S |
|----------|---------|-------------|
| Dtype | float64 | uint32 |
| Nodata | -200.0 | None (0 = no built-up) |
| File size/epoch | ~350 MB | ~178 MB |
| Raster columns | 43202 | 43201 |
| Value range | 0-1.4 billion | 0-848,108 |
| Unit | persons | m^2 |

The unsigned integer dtype and absence of a nodata sentinel simplify the viewpoint: no nodata masking is needed. Zero genuinely means zero built-up surface.

### Consolidation: skipped

Same rationale as GHS-POP (ADR-029): single release (R2023A) with nothing to merge or deduplicate. When JRC publishes R2024A, a consolidator can be added.

### Theoretical relevance

Urbanisation is a structural driver of conflict through multiple causal pathways:
- **Opportunity cost:** Urban areas offer alternative livelihoods that raise the cost of rebellion
- **State capacity:** Built-up infrastructure correlates with state presence and control
- **Terrain:** Urban vs. rural environments shape the type and lethality of violence
- **Inequality:** Urban-rural divides in built infrastructure correlate with grievance

Built-up surface captures the *physical footprint* of urbanisation — complementary to population which captures the *human footprint*.

---

## Consequences

### Positive

- Second structural covariate in the assembled grid (alongside population)
- Validates raster pipeline generality beyond GHS-POP
- Same institutional source — no new access patterns, auth, or distribution infrastructure
- Opens path to GHS-BUILT-V (volume) with minimal additional effort

### Negative

- ~2.1 GB additional download (12 epochs at ~178 MB each)
- One additional feature in the assembled grid increases memory proportionally (~1/53 of current grid)
- Temporal sparsity — same 12 epochs as GHS-POP, same interpolation caveats

These costs are minimal and accepted.

---

## Implementation Notes

### What we verified

Before implementation, one epoch (E2020) was downloaded and inspected:

- **URL pattern:** `https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_BUILT_S_GLOBE_R2023A/GHS_BUILT_S_E{epoch}_GLOBE_R2023A_4326_30ss/V1-0/GHS_BUILT_S_E{epoch}_GLOBE_R2023A_4326_30ss_V1_0.zip`
- **ZIP contents:** `GHSL_Data_Package_2023.pdf`, `GHS_BUILT_S_E{epoch}_GLOBE_R2023A_4326_30ss_V1_0.tif`, `.tif.ovr` (overview)
- **Raster shape:** 21384 x 43201 (one column fewer than GHS-POP's 43202 — strip-based aggregation handles this via boundary clipping)
- **Dtype:** uint32 (not float64)
- **Nodata:** None — 0 means no built-up surface
- **Tiepoint:** (-180.001, 89.100) with 0.00833 degree pixel scale — same alignment as GHS-POP
- **File size:** ~178 MB compressed per epoch (~129 MB uncompressed TIF)

### Pipeline flow

Harvest → Viewpoint → Compilation → Assembly (same as GHS-POP, skipping consolidation).

### Feature name

`ghsbuilts_built_area` — total built-up surface area (m^2) per PRIO-GRID cell per month.

### Memory considerations

uint32 rasters are ~3.4 GB uncompressed (vs 6.88 GB for GHS-POP's float64). Strip-based aggregation (`_aggregate_with_alignment`) keeps peak memory at raw array + ~20 MB working buffer. No OOM risk on the 8 GB server.

---

## References

- JRC GHS-BUILT-S R2023A product page: https://human-settlement.emergency.copernicus.eu/ghs_buS2023.php
- JRC Data Catalogue: https://data.jrc.ec.europa.eu/dataset/9f06f36f-4b11-47ec-abb0-4f8b7b1d72ea
- GHSL Data Package 2023: https://human-settlement.emergency.copernicus.eu/documents/GHSL_Data_Package_2023.pdf
- ADR-029: GHS-POP as First Population Source
- ADR-030: Raster Tooling Selection (tifffile)
- ADR-031: Resource Ownership and Data Representation
- ADR-032: Harvest Idempotence and Caching
