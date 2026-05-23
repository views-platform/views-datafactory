# GHS-BUILT-S

| Field | Value |
|-------|-------|
| Provider | European Commission, Joint Research Centre (JRC) — Copernicus programme |
| Product | GHS-BUILT-S R2023A — GHS built-up surface grid, derived from Sentinel2 composite and Landsat, multitemporal (1975–2030) |
| URL | https://human-settlement.emergency.copernicus.eu/ghs_buS2023.php |
| DOI | 10.2905/9F06F36F-4B11-47EC-ABB0-4F8B7B1D72EA |
| License | EU reuse policy (Commission Decision of 12 December 2011) — open access, no registration |
| Citation | Pesaresi, M. & Politis, P. (2023). GHS-BUILT-S R2023A — GHS built-up surface grid, derived from Sentinel2 composite and Landsat, multitemporal (1975–2030). European Commission, Joint Research Centre. doi:10.2905/9F06F36F-4B11-47EC-ABB0-4F8B7B1D72EA |
| Codebook | https://human-settlement.emergency.copernicus.eu/documents/GHSL_Data_Package_2023.pdf |
| Upstream contact | JRC GHSL team (jrc-ghsl-data@ec.europa.eu) |
| Native format | Cloud Optimized GeoTIFF (LZW-compressed, ~178 MB per epoch) |
| Native CRS | Mollweide (ESRI:54009) and WGS84 (EPSG:4326) — we use WGS84 |
| Native resolution | 10 m and 100 m (Mollweide); 3 arcsec and 30 arcsec (WGS84) — we use 30 arcsec WGS84 |
| Native dtype | uint32 (built-up surface area in m² per pixel) |
| Spatial extent | Global |
| Temporal coverage | 1975–2030 (12 epochs at 5-year intervals) |
| Temporal granularity | 5-year epochs |
| Update cadence | Irregular major releases (~2–3 years; R2022A → R2023A) |
| Access method | Direct download, no registration, no authentication |
| Authentication | None |
| Features produced | `ghsbuilts_built_area` |
| Grid layers | Harvest → Viewpoint → Compilation → Assembly (skips consolidation — single release) |
| Selection ADR | [ADR-034](../ADRs/034_ghs_built_s_as_built_up_surface_source.md) |
| Provenance ledger | `provenance/ghsbuilts/ingestion_ledger.jsonl` |

## Description

Built-up surface area estimates (m² per grid cell) on a global grid, derived from satellite multispectral imagery (Landsat and Sentinel-2). R2023A uses improved classification algorithms applied to the full Landsat archive (1975–2020) and Sentinel-2 composites (2018–2020), with projections for 2025 and 2030. Built-up surface captures the physical footprint of urbanisation — complementary to GHS-POP which captures the human footprint. Together they provide a richer structural picture of where people live and what has been built.

## Pipeline path

**Harvest → Viewpoint → Compilation → Assembly.** Consolidation is skipped — GHS-BUILT-S has a single release (R2023A) with nothing to merge or deduplicate. When JRC publishes R2024A, a consolidator will be added.

- **Harvest:** Downloads 12 GeoTIFF files (one per epoch) from JRC. ~2.1 GB total.
- **Viewpoint:** Spatial aggregation (sum 60×60 source pixels per PRIO-GRID cell) and temporal interpolation (linear between 5-year epochs). These are opinionated decisions, not mechanical transforms — ADR-014.
- **Compilation:** Mechanical placement of (pgid, month_id, value) rows into the [T, H, W, C] grid.
- **Assembly:** Combined with UCDP, ACLED, GHS-POP, PRIO-GRID static, and GAUL admin into the final grid.

## Known limitations

- **Temporal sparsity.** 12 epochs across 456+ monthly time steps. Inter-epoch months carry interpolated values, not independent measurements. Models must be aware of this.
- **Classification accuracy.** Built-up detection relies on spectral signatures. Accuracy varies by land cover type — arid regions and bare soil can be confused with built-up surface, particularly in earlier epochs (pre-Sentinel-2).
- **No functional classification.** All built-up surface is treated equally — residential, industrial, commercial, and infrastructure are not distinguished. For conflict forecasting, the type of built-up area may matter more than the total.
- **2025 and 2030 are modelled.** The last two epochs are projections based on historical trends, not direct satellite observation.
- **Reference validation.** Global built-up totals validated against raw pixel sums from GHS_BUILT_S R2023A GeoTIFFs (consistent with JRC BUTOT values in GHSL Data Package 2023, Table 13). Grid epoch totals match to within 1–2%, confirming sum aggregation of absolute m² pixel values is correct.
