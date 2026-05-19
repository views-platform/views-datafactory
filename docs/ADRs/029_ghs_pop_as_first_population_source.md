# ADR-029: GHS-POP as First Population Data Source

**Status:** Accepted
**Date:** 2026-05-17
**Deciders:** Simon Polichinel von der Maase, Claude Code
**Applies:** ADR-012 (Four-Layer Data Architecture), ADR-013 (Consolidation Principles), ADR-014 (Viewpoints as Derived Views), ADR-024 (Compilation Grid Invariants)

---

## Context

The data factory has two conflict event sources (UCDP, ACLED) fully integrated and proven on the production server (v1.2.14). The next source is the WET-before-DRY inflection point: the third pipeline will reveal which patterns are genuinely shared across sources and which are source-specific artifacts (see product plan v11, task #27).

Population is a natural third source for three reasons:

1. **Theoretical relevance.** Population is a slow-moving structural covariate with direct causal links to conflict dynamics — higher population density correlates with both conflict incidence and severity. It is arguably the single most important non-conflict feature for conflict forecasting models.

2. **Structural novelty.** UCDP and ACLED are both event-level conflict datasets with the same pipeline shape: harvest API → consolidate events → build viewpoint → compile to grid. Population data is fundamentally different — it arrives as a pre-gridded raster, not as event records. This means the third source will test whether the graph architecture (ADR-012) handles non-event, non-API data cleanly, rather than just confirming that a third event source works like the first two.

3. **Raster gateway.** Population is the first raster source. Solving the raster I/O/reprojection/aggregation problem now opens the path to nightlights, built-up area, land cover, and other raster covariates (Direction 3 on the roadmap), all of which share the same ingest pattern.

A surface-level review of the global gridded population data landscape was conducted, covering institutional products (JRC/Copernicus, NASA SEDAC, ORNL, WorldPop, UN WPP), big tech initiatives (Microsoft, Google, Meta), and selected intergovernmental efforts (OGC, OECD). The finding: **no institution operates a continuously-maintained, weather-service-style global gridded population product.** The field works in periodic releases built from decennial census rounds combined with satellite imagery and modeling. The practical candidates are GPW, GHS-POP, LandScan, and WorldPop.

---

## Decision

**GHS-POP R2023A** (Global Human Settlement Layer — Population Grid, Release 2023A), produced by the European Commission's Joint Research Centre (JRC) under the Copernicus programme, is the first population data source for the VIEWS data factory.

### In scope

- Harvesting GHS-POP GeoTIFF files from the JRC distribution
- Reprojection from Mollweide (ESRI:54009) to WGS84 (EPSG:4326)
- Aggregation from ~1 km native resolution to 0.5° PRIO-GRID cells
- Integration into the assembled grid as population feature(s)
- Raster I/O and reprojection tooling (rasterio is the likely solution, but the raster toolchain choice warrants its own ADR)

### Out of scope

- Population-derived features (density, change rate, urbanization) beyond the raw count
- Cross-source derived features (e.g., conflict-adjusted population — see Considered Alternatives)
- Cross-validation against other population products (GPW, LandScan)
- Sub-national population modeling or nowcasting

---

## Rationale

### Methodology

GHS-POP uses **dasymetric disaggregation**: census counts are distributed across space using satellite-detected built-up areas (Landsat/Sentinel) and building footprints as covariates. This is methodologically superior to GPW's proportional allocation, which distributes census counts uniformly across administrative units. At PRIO-GRID's 0.5° resolution the difference is less dramatic than at fine resolution, but it still matters for cells that straddle urban/rural boundaries.

### Institutional stability

GHS-POP is part of the EU Copernicus programme — a multi-decade institutional commitment with dedicated funding. JRC has published the GHSL framework since 2012 and shows no signs of discontinuation. The data is fully open access (no registration wall), distributed under standard EU open data terms.

### Temporal honesty

GHS-POP publishes ~6 epochs (1975, 1990, 2000, 2015, 2020, 2025) rather than annual releases. This is a feature, not a limitation. Population changes slowly at the grid-cell level, and the inter-censal years in "annual" products like LandScan are model-interpolated from the same underlying census data — they do not represent independent population observations. GHS-POP's epoch-only approach avoids creating false annual precision. For a conflict forecasting system where scientific defensibility matters, this is the right trade-off.

### Raster tooling investment

GHS-POP's GeoTIFF format and Mollweide projection require raster I/O and reprojection tooling. rasterio is the most likely solution, but alternatives exist (e.g., rioxarray, GDAL bindings, or pure-xarray workflows for regularly-gridded data). The specific toolchain choice warrants its own ADR. Regardless of which tool is chosen, this is a one-time infrastructure investment that pays forward: LandScan, nightlights (VIIRS), built-up area (GHS-BUILT), and land cover (ESA CCI) all share the same raster ingest pattern. Solving raster I/O now opens Direction 3 on the roadmap.

### Flow through the four-layer graph

GHS-POP traverses all four layers of the data architecture (ADR-012), but with different operations than event sources. Each layer does real work.

**Harvest (Layer 1):** Download GeoTIFF files from JRC, store as-is in `data/raw/ghspop/`. Pure acquisition with provenance ledger entry per download. Analogous to UCDP/ACLED API fetches. WGS84 (EPSG:4326) data is available at 30 arcsecond resolution, eliminating the need for reprojection (see ADR-030).

**Consolidation (Layer 2): Skipped.** GHS-POP has a single release (R2023A) with no event records to merge or deduplicate. The consolidation layer exists for vintage-aware tracking of multiple release versions — there is nothing to consolidate until JRC publishes R2024A. The viewpoint reads directly from `data/raw/ghspop/`. This is consistent with ADR-012's design principle that "not all paths traverse all layers" — synthetic data already skips consolidation, viewpoint, and compilation. When a second GHS-POP release arrives, a consolidator will be added to track both releases with the same ADR-013 guarantees as UCDP/ACLED.

**Viewpoint (Layer 3):** This is where opinionated decisions live, following ADR-014. For raster data, the viewpoint owns different operations than for event data, because the input is a gridded raster rather than coordinate-bearing event records:

- **Spatial aggregation** — sum 30-arcsecond cells into 0.5° PRIO-GRID cells. Each PRIO-GRID cell contains exactly 60×60 source pixels, so aggregation is a numpy reshape+sum with no coordinate transformation. For event sources, spatial assignment (lat/lon → cell) is a compilation concern because events are coordinate points that need binning. For raster sources, the data is already gridded — the aggregation function (sum vs. mean vs. area-weighted) is an opinion about how to present the data at a different resolution, making it a viewpoint concern.
- **Temporal interpolation** — how to fill the gap between 12 epochs and monthly time steps (step function, linear interpolation, etc.). This is analogous to UCDP's temporal distribution of summary events — an opinion about what the data looks like between observations.

No reprojection is needed — JRC provides WGS84 data directly (ADR-030). No release survivorship is needed until a second release exists.

The viewpoint output should be tabular: one row per (pgid, month_id) with population value(s). This gives compilation a uniform input shape across all sources.

**Compilation (Layer 4):** Mechanical placement of viewpoint output into the [T, H, W, C] grid array (ADR-024). With the viewpoint producing (pgid, month_id, value) rows, compilation for GHS-POP is structurally identical to UCDP/ACLED compilation — read tabular input, fill the grid.

---

## Considered Alternatives

### Alternative A: GPW v4.11 (NASA SEDAC)

- **Pros:** Available at exactly 0.5° in WGS84 as NetCDF — zero reprojection, no rasterio dependency, readable with xarray alone. Census-based, well-documented, open access.
- **Cons:** Uses proportional allocation (uniform distribution within admin units), which is less accurate than dasymetric disaggregation. Only 5 epochs (2000, 2005, 2010, 2015, 2020). Choosing GPW would defer the raster tooling problem rather than solving it — every future raster source would still require it.
- **Reason for rejection:** Weaker methodology and avoids the raster tooling investment that all raster sources eventually require. GPW remains a valid cross-validation reference.
- **Revisit condition:** If raster tooling proves unexpectedly difficult to integrate and a population feature is urgently needed, GPW could serve as a temporary bridge.

### Alternative B: LandScan (ORNL / US DOE)

- **Pros:** Annual releases (2000–2024), NGA-backed ambient population model, ~1 km resolution. Annual cadence gives one value per year rather than requiring interpolation.
- **Cons:** The "annual" cadence is modeled, not observed — ORNL reruns their model each year with updated satellite imagery, but the underlying census data only changes every ~10 years. Inter-censal years are model artifacts, not independent measurements. Requires ORNL registration (not fully open). Also requires raster tooling (GeoTIFF format).
- **Reason for rejection:** False precision in the annual cadence, registration wall, and no methodological advantage over GHS-POP for our use case. LandScan's ambient population model (where people are during the day) vs. GHS-POP's residential model is a distinction that washes out at 0.5° resolution.
- **Revisit condition:** If annual population variation proves analytically valuable and models benefit from year-over-year changes, LandScan could be added as a second population source.

### Alternative C: WorldPop Global2 (R2025A)

- **Pros:** 100 m resolution, annual 2015–2030, uses building footprints from Google/Microsoft/Meta as covariates. Highest spatial resolution available.
- **Cons:** Short temporal coverage (2015–2030 vs. GHS-POP's 1975–2025). Academic project without the institutional backing of JRC or NASA. The extreme resolution (100 m) means massive file sizes that must be aggregated down to 0.5° — engineering overhead without analytical benefit at PRIO-GRID scale.
- **Reason for rejection:** Short temporal coverage, less institutional stability, and the resolution advantage is irrelevant at 0.5° aggregation.

### Alternative D: Big tech population products (Microsoft, Google, Meta)

- **Investigation finding:** None of these companies produce population counts. Microsoft publishes Global Building Footprints (polygons of building outlines). Google publishes Open Buildings (similar). Meta published HRSL (High Resolution Settlement Layer), which is now discontinued and folded into WorldPop. All three produce **building footprints**, which are used as **inputs to** GHS-POP and WorldPop, not as standalone population products.
- **Reason for rejection:** These are covariates for population modeling, not population data sources. By choosing GHS-POP, we consume their contributions indirectly through a product that has been validated and published by domain experts.

### Alternative E: Conflict-adjusted population

- **Idea:** Subtract cumulative conflict fatalities (from UCDP/ACLED) from GHS-POP estimates to produce a "corrected" population feature that accounts for conflict deaths.
- **Reason for rejection (three grounds):**
  1. **Violates viewpoint independence.** ADR-014 requires that a viewpoint be a pure function of its own consolidated store plus configuration. A conflict-adjusted population viewpoint would need to read from the UCDP/ACLED consolidated stores, creating a cross-source dependency that breaks the layer boundary.
  2. **Selectively dishonest.** Conflict kills ~100K–200K people per year globally. Conflict *displaces* tens of millions. Birth rates in many conflict-affected regions far exceed death rates. Adjusting for fatalities without accounting for displacement, migration, and births corrects for the smallest effect while ignoring the largest ones. The result is neither the census estimate nor the true population — it is a hybrid that is wrong in a specific, misleading way.
  3. **Double-counting risk.** If models consume both population and fatality features, the conflict signal appears in both. This kind of redundant encoding produces correlated features that look powerful in training but are fragile in deployment.
- **Conclusion:** Population is what GHS-POP says it is. If conflict-population interaction matters, that is a model-level concern (feature engineering in the training scripts), not a data factory concern.

### Alternative F: V-Dem or WDI (non-population sources)

- **Pros:** Strong theoretical relevance (democracy indicators, development indicators). Country-year tabular data — no rasterio needed.
- **Cons:** Would be a third event/tabular source with the same pipeline shape as UCDP and ACLED. Would not test whether the architecture handles raster data. Would not solve the rasterio gate for future raster sources.
- **Reason for rejection:** Population provides more architectural novelty (raster ingest) and greater theoretical relevance (structural covariate) than another tabular source. V-Dem/WDI remain strong candidates for the fourth source.

---

## Consequences

### Positive

- First non-event, non-conflict feature in the assembled grid — models gain a structural covariate
- Raster I/O tooling solved once, applicable to all future raster sources (nightlights, built-up area, land cover)
- Third pipeline reveals which graph patterns are genuinely shared vs. source-specific
- EU/Copernicus institutional backing provides long-term data availability
- Open access with no registration wall — CI/CD-friendly harvesting

### Negative

- **Raster tooling dependency.** GeoTIFF I/O and Mollweide reprojection require tooling beyond the current pure-Python stack. rasterio (GDAL bindings) is the most likely choice but adds a compiled dependency that may require system-level libraries on the server. The raster toolchain selection warrants its own ADR.
- **Mollweide reprojection.** GHS-POP's native CRS requires coordinate transformation before PRIO-GRID alignment. This adds a processing step that GPW would not require.
- **Temporal sparsity.** ~6 epochs across 456 monthly time steps means most months will carry interpolated or repeated population values. Models must be aware that inter-epoch population is not independently measured. This is honestly the same situation as LandScan (where inter-censal years are modeled), but GHS-POP makes it explicit rather than hiding it behind annual releases.
- **Different operations per layer.** Although GHS-POP traverses all four layers, the viewpoint does fundamentally different work than for event sources — raster reprojection and spatial aggregation instead of survivorship and temporal distribution. This tests whether the viewpoint layer is general enough to accommodate non-event data, or whether it needs to evolve.

These costs are accepted. The raster tooling investment and architectural novelty are features of this choice, not bugs — they are exactly why population is the right third source.

---

## Implementation Notes

Implementation design is deferred to a separate discussion. This ADR anchors the source selection decision; pipeline architecture follows.

### What we know

- **Source URL:** JRC distributes GHS-POP via `https://human-settlement.emergency.copernicus.eu/download.php` as Cloud Optimized GeoTIFF tiles
- **Resolution options:** 100 m (Mollweide), 1 km / 30 arcsec (Mollweide). The 1 km product is the practical choice — 100 m would require aggregating ~3,600 pixels per PRIO-GRID cell vs. ~55 pixels at 1 km
- **Epochs available (R2023A):** 1975, 1990, 2000, 2015, 2020, 2025
- **GAUL integration:** Population features will be per-cell, not per-country. The GAUL admin boundaries (ADR-025) are not needed for spatial assignment — the raster-to-grid aggregation handles this directly via coordinate alignment
- **Compilation output:** One or more population features in the assembled grid, following the [T, H, W, C] invariant (ADR-024). Feature naming convention TBD.

### Resolved design questions

- **Graph flow:** Harvest → Viewpoint → Compilation. Consolidation is skipped until a second JRC release exists. See "Flow through the four-layer graph" above.
- **Reprojection:** Not needed. JRC provides WGS84 (EPSG:4326) at 30 arcsecond resolution. Each PRIO-GRID cell is exactly 60×60 source pixels. See ADR-030.
- **Raster tooling:** tifffile (pure Python). See ADR-030.
- **Spatial aggregation ownership:** Viewpoint layer, not compilation. For raster sources, the input is already gridded — the aggregation function is an opinion about how to present data at a different resolution, unlike event sources where coordinate-to-cell binning is mechanical.
- **Temporal interpolation ownership:** Viewpoint layer. Analogous to UCDP temporal distribution of summary events.

### What requires design decisions

- What aggregation function for spatial aggregation? (Sum is the natural choice for population counts, but this is a viewpoint v1 decision)
- What temporal interpolation strategy? (Step function? Linear? This is a viewpoint v1 decision)
- Should the harvester download all epochs or only those within the configured temporal range?
- What features to produce in v1? (Raw population count? Log-population? Population density?)
- What raster I/O toolchain? (Warrants its own ADR)

---

## Validation & Monitoring

- Downloaded GeoTIFF files should be verified against published checksums (if JRC provides them)
- Aggregated population grid should be sanity-checked: global sum should approximate known world population for each epoch (~4B in 1975, ~8B in 2025)
- Spatial distribution should be visually verified: high-population cells should correspond to known urban areas
- Zero-population cells on land should be investigated (could indicate aggregation errors vs. genuinely uninhabited areas)
- Whatever raster tooling is chosen should be tested in CI — compiled dependencies may require a system package install step

---

## Open Questions

- What is the exact download URL structure for GHS-POP R2023A GeoTIFF tiles? (Requires checking the JRC data portal)
- Does JRC provide the 1 km product in WGS84 (EPSG:4326) in addition to Mollweide? If so, reprojection may be unnecessary.
- What is the total download size for all epochs at 1 km resolution?
- Should population data be log-transformed before serving to models? (Common practice, but a viewpoint decision — different viewpoints might present raw counts vs. log-transformed)
- How should the temporal gap between epochs interact with the ACLED temporal boundary (C-156)? Both represent "no data before year X" but for different reasons.
- Is there a versioning/update cadence for GHS-POP releases? (R2023A superseded R2022A — how often do new releases appear?)
- What does the consolidated store look like for raster data? (Parquet metadata catalog pointing to versioned GeoTIFF files? Or something else?)

---

## References

- JRC Global Human Settlement Layer: https://human-settlement.emergency.copernicus.eu/
- GHS-POP R2023A product page: https://human-settlement.emergency.copernicus.eu/ghs_pop2023.php
- GHS-WUP 2025 (urbanization projections): https://human-settlement.emergency.copernicus.eu/ghs_wup2025.php
- JRC GHSL data catalogue: https://data.jrc.ec.europa.eu/collection/ghsl
- ADR-012: Four-Layer Data Architecture
- ADR-013: Consolidation Principles (lossless, append-only, version-aware)
- ADR-014: Viewpoints as Derived Views (opinionated, rebuildable, versioned)
- ADR-024: Compilation Grid Invariants
- ADR-025: Country Identity Uses GAUL Codes
- ADR-028: ACLED Consolidation and Viewpoint Specifics (template for source-specific ADRs)
- Product Development Plan v11: `reports/product_development_plan11.md` (task #27: choose next source)
- R&D Roadmap v11: `reports/rd_roadmap11.md` (Direction 1: source expansion)
- GPW v4.11: https://sedac.ciesin.columbia.edu/data/collection/gpw-v4
- LandScan: https://landscan.ornl.gov/
- WorldPop: https://www.worldpop.org/
