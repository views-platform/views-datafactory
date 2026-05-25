# GAUL Admin

| Field | Value |
|-------|-------|
| Provider | Food and Agriculture Organization of the United Nations (FAO) |
| Product | GAUL 2024 — Global Administrative Unit Layers |
| URL | https://www.fao.org/agroinformatics/training-and-resources/data-sets/data-set-detail/global-gaul-new-2024-release/en |
| DOI | — |
| License | Creative Commons Attribution 4.0 (CC-BY-4.0) |
| Citation | FAO (2024). Global Administrative Unit Layers (GAUL) 2024 Release. Food and Agriculture Organization of the United Nations. |
| Codebook | Included in shapefile attribute table |
| Upstream contact | FAO GeoNetwork (GeoNetwork@fao.org) |
| Native format | Shapefile (.shp) — polygon boundaries |
| Native CRS | WGS84 (EPSG:4326) |
| Native resolution | Administrative boundary polygons |
| Spatial extent | Global |
| Temporal coverage | Static (2024 release) |
| Temporal granularity | None (time-invariant) |
| Update cadence | One-time (annual GAUL releases, but we pin to the 2024 version) |
| Access method | Direct download, no authentication |
| Authentication | None |
| Features produced | `gaul0_code`, `gaul1_code`, `gaul2_code` |
| Grid layers | Harvest → Assembly (skips consolidation, viewpoint, compilation) |
| Selection ADR | [ADR-031](../ADRs/031_gaul_admin_boundaries.md) |
| Provenance ledger | `provenance/gaul_admin/ingestion_ledger.jsonl` |

## Description

GAUL provides global administrative boundary polygons at three levels: country (admin-0), first-level subdivision (admin-1), and second-level subdivision (admin-2). The harvester downloads GAUL shapefiles and performs a spatial join against PRIO-GRID cell centroids to produce a lookup table mapping each grid cell to its containing administrative units.

This enables country-month and sub-national aggregation of grid-level forecasts — essential for translating 0.5° grid outputs into policy-relevant geographic units.

## Pipeline path

**Harvest → Assembly.** Consolidation, viewpoint, and compilation are skipped — the spatial join produces per-variable Parquet files at PRIO-GRID resolution.

- **Harvest:** Downloads GAUL 2024 shapefiles from FAO. Performs spatial join (STRtree point-in-polygon) against PRIO-GRID cell centroids. Outputs per-variable Parquet files with columns `(gid, value)`.
- **Assembly:** Per-variable Parquet files are placed directly into the assembled grid.

## Known limitations

- **Boundary disputes.** Administrative boundaries are politically sensitive. GAUL reflects FAO's boundary decisions, which may differ from other sources.
- **Centroid assignment.** Cells are assigned to the admin unit containing their centroid. Border cells may be assigned to the "wrong" country if the centroid falls on one side of a boundary that bisects the cell.
- **Static snapshot.** We pin to the GAUL 2024 release. Administrative boundary changes after 2024 are not reflected.
