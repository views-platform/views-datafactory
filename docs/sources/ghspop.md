# GHS-POP

| Field | Value |
|-------|-------|
| Provider | European Commission, Joint Research Centre (JRC) — Copernicus programme |
| Product | GHS-POP R2023A — GHS population grid multitemporal (1975–2030) |
| URL | https://human-settlement.emergency.copernicus.eu/ghs_pop2023.php |
| DOI | 10.2905/2FF68A52-5B5B-4A22-8F40-C41DA8332CFE |
| License | EU reuse policy (Commission Decision of 12 December 2011) — open access, no registration |
| Citation | Schiavina, M., Freire, S., Carioli, A. & MacManus, K. (2023). GHS-POP R2023A — GHS population grid multitemporal (1975–2030). European Commission, Joint Research Centre. doi:10.2905/2FF68A52-5B5B-4A22-8F40-C41DA8332CFE |
| Codebook | https://human-settlement.emergency.copernicus.eu/documents/GHSL_Data_Package_2023.pdf |
| Upstream contact | JRC GHSL team (jrc-ghsl-data@ec.europa.eu) |
| Native format | Cloud Optimized GeoTIFF (LZW-compressed, ~350 MB per epoch) |
| Native CRS | Mollweide (ESRI:54009) and WGS84 (EPSG:4326) — we use WGS84 |
| Native resolution | 3 arcsec and 30 arcsec (WGS84); 100 m and 1 km (Mollweide) — we use 30 arcsec WGS84 |
| Spatial extent | Global |
| Temporal coverage | 1975–2030 (12 epochs at 5-year intervals) |
| Temporal granularity | 5-year epochs |
| Update cadence | Irregular major releases (~2–3 years; R2022A → R2023A) |
| Access method | Direct download, no registration, no authentication |
| Authentication | None |
| Features produced | `ghspop_pop_count` |
| Grid layers | Harvest → Viewpoint → Compilation → Assembly (skips consolidation — single release) |
| Selection ADR | [ADR-029](../ADRs/029_ghs_pop_as_first_population_source.md) |
| Provenance ledger | `provenance/ghspop/ingestion_ledger.jsonl` |

## Description

Residential population estimates on a global grid, produced by dasymetric disaggregation of census counts using satellite-detected built-up areas and building volumes as spatial covariates. R2023A uses CIESIN GPWv4.11 census data disaggregated with GHS-BUILT-V R2022A built-up volume maps. This is the first non-event, non-conflict source in the data factory — a slow-moving structural covariate with direct causal links to conflict dynamics. It is also the gateway raster source: solving GeoTIFF ingest here opens the path to nightlights, built-up area, and land cover.

## Pipeline path

**Harvest → Viewpoint → Compilation → Assembly.** Consolidation is skipped — GHS-POP has a single release (R2023A) with nothing to merge or deduplicate. When JRC publishes R2024A, a consolidator will be added.

- **Harvest:** Downloads 12 GeoTIFF files (one per epoch) from JRC. ~4.2 GB total.
- **Viewpoint:** Spatial aggregation (sum 60×60 source pixels per PRIO-GRID cell) and temporal interpolation (linear between 5-year epochs). These are opinionated decisions, not mechanical transforms — ADR-014.
- **Compilation:** Mechanical placement of (pgid, month_id, value) rows into the [T, H, W, C] grid.
- **Assembly:** Combined with UCDP, ACLED, PRIO-GRID static, and GAUL admin into the final grid.

## Known limitations

- **Temporal sparsity.** 12 epochs across 456+ monthly time steps. Inter-epoch months carry interpolated values, not independent measurements. Models must be aware of this.
- **Census dependency.** Accuracy depends on underlying census quality, which varies by country. Sub-Saharan Africa and conflict-affected regions often have the weakest census coverage — precisely where VIEWS needs the most accuracy.
- **No sub-annual variation.** Population is treated as constant within each 5-year epoch. Seasonal migration, displacement, and conflict-driven population movements are not captured.
- **2025 and 2030 are projections.** The last two epochs are UN WPP-based projections, not census-derived estimates.
