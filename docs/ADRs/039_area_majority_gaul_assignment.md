# ADR-039: Area-Majority GAUL Assignment with Precomputed Table

**Status:** Accepted
**Date:** 2026-06-04 (accepted 2026-06-05)
**Deciders:** Simon Polichinel von der Maase, Claude Code
**Supersedes:** Centroid-in-polygon assignment (implicit, undocumented)
**Applies:** ADR-025 (Static Grid Features), ADR-030 (Raster Tooling — Rust Long-Term), ADR-012 (Four-Layer Data Architecture)

---

## Context

The datafactory assigns PRIO-GRID cells to GAUL administrative regions using the `_spatial_join()` helper in `gaul_admin.py`. The current method tests whether each cell's centroid (center point of the 0.5-degree square) falls inside a GAUL polygon. This is a point-in-polygon operation.

For 149 coastal cells in Africa+ME (9,481 globally), the centroid falls in water — outside any GAUL polygon. These cells are assigned `gaul0_code = -1` (unassigned) and excluded from country-level aggregations. This drops 409,743 fatalities (~3.9% of the state-based total) silently from country-month output. No error is emitted. The gap was identified in `postmortem_cm_unmapped_gaul_cells.md` and registered as C-149 (Tier 2 — silent data gap).

FAO GAUL documentation (Release Note 02) specifies area-majority as the correct assignment method for gridded data. Tollefsen et al. (2012, Journal of Peace Research) describe area-weighted aggregation as a standard PRIO-GRID operation.

Both inputs are effectively static. GAUL had a 9-year gap between releases (2015 → 2024). PRIO-GRID 2.0 is frozen. A precomputed assignment table is valid indefinitely.

The `views-postprocessing` repository implements area-majority via a 3,100-line geopandas runtime mapper with 774 MB bundled shapefiles — a known liability with 22 risk register concerns. This ADR documents a simpler approach.

---

## Decision

### Precomputed area-majority lookup table

The GAUL spatial join is precomputed using shapely polygon intersection and stored as static Parquet files. The pipeline reads a lookup table instead of computing spatial joins at runtime.

**Generation:** A standalone script (`scripts/generate_area_majority_gaul.py`) computes area-majority assignments for all 259,200 PRIO-GRID cells using shapely 2.x (already a dependency). For each cell, it builds a 0.5-degree polygon, queries an STRtree for overlapping GAUL polygons, computes intersection areas, and assigns the cell to the polygon with the largest overlap.

**Output:** Three Parquet files in `data/raw/gaul_admin/`:
- `gaul0_code.parquet` — country-level (GAUL Level 0)
- `gaul1_code.parquet` — province-level (GAUL Level 1)
- `gaul2_code.parquet` — district-level (GAUL Level 2)

Each file has columns `gid` (int) and `value` (int). Same schema as the former centroid-based files.

**Pipeline integration:** `refresh_pipeline.sh` runs `harvest_gaul.py` (for shapefile download + name files), then `generate_area_majority_gaul.py` which overwrites the three code files with area-majority versions. Name files and iso3_code remain from the centroid harvester.

**Regeneration:** Run the generation script when GAUL updates (estimated next: ~2030). The script, GAUL shapefile version, computation method, and content digest are recorded in the provenance ledger.

### In scope

- Precomputed area-majority Parquet files for all three GAUL levels
- Generation script using shapely + pyshp (existing dependencies)
- Provenance ledger integration
- Before/after comparison artifact documenting the change
- Pipeline integration (refresh_pipeline.sh)

### Out of scope

- Runtime spatial computation during harvest or assembly
- Rust implementation (deferred — see "Relationship to ADR-030")
- Changes to the `(gid, value)` Parquet schema
- Retroactive recalculation of historical pipeline outputs
- Name file generation for recovered cells (known gap; see Consequences)

---

## Rationale

### Static inputs justify a precomputed table

GAUL and PRIO-GRID are both static. Computing the spatial join at runtime — on every server, every pipeline run — wastes time and introduces unnecessary dependencies. A precomputed table:
- Runs on every server without shapefile loading or spatial computation
- Has zero runtime dependency beyond Parquet reading (pyarrow, already installed)
- Is deterministic: same input data, same output, same content digest

This follows the existing pattern: `land_pgids.json` and `africa_me_legacy_pgids.json` are also precomputed static tables derived from PRIO-GRID geometry.

### Shapely for generation, not a new dependency

The generation script uses shapely 2.x and pyshp — both already in `pyproject.toml`. No new dependencies are introduced for either generation or consumption. The generation script runs once per GAUL version. Performance is acceptable: 17.1 minutes for the full global grid across all three levels.

### Area-majority is strictly more complete than centroid

Every cell that centroid assigns correctly, area-majority also assigns correctly (the centroid's polygon must overlap the cell by some area). Area-majority additionally handles the 9,481 coastal cells that centroid misses. It also reassigns 368 border cells (gaul0 level) to the country that covers the most area — a more geographically accurate assignment.

The reassignment of border cells is a correction, not a regression. A cell on a national border whose centroid is 0.1 degrees inside country A but whose area is 60% in country B should be assigned to country B. This is the intended behavior of area-majority and the reason FAO specifies it.

### WET-before-DRY and ADR-030 consistency

ADR-030 established the principle: "no Rust code is written until the pattern is proven in Python." The area-majority spatial join is the second spatial computation pattern in the datafactory (after centroid). Building it in shapely first:
1. Proves the pattern works
2. Produces a test oracle for the eventual Rust implementation
3. Documents the exact operations needed (STRtree query, polygon intersection, area comparison)

When a third spatial computation need arises, the combined evidence from centroid and area-majority will justify the Rust investment.

---

## Considered Alternatives

### Alternative A: Extend gaul_admin.py to run area-majority at harvest time

Replace the centroid join with area-majority in the harvester, computing it on every pipeline run.

- **Pros:** No precomputed artifact to maintain. Self-contained.
- **Cons:** Every server loads the 775 MB GAUL shapefile and computes 259,200 intersections on every pipeline run (~17 minutes). The result is always the same. Wastes time and makes the harvester more complex.
- **Reason for rejection:** Runtime computation of a static result contradicts the "immutable input" batch processing principle. The lookup table is simpler and faster.

### Alternative B: Rust binary (geo-rs)

A standalone Rust program using `geo` v0.31.0, `rstar` v0.12.2, and `shapefile` v0.7.0.

- **Pros:** Fastest option. Zero runtime dependencies. Aligns with ADR-030's Rust direction.
- **Cons:** Requires Rust knowledge and a build pipeline. Premature for a one-time computation on static data.
- **Reason for deferral:** The computation runs once per GAUL version (~every 9 years). Building and maintaining a Rust binary for this frequency is over-engineering.
- **Revisit condition:** When the datafactory needs a spatial computation that runs frequently enough to justify the Rust investment, or when a third spatial operation pattern emerges.

### Alternative C: geopandas

Use `geopandas.sjoin()` for the spatial join.

- **Reason for rejection:** Pulls in GDAL/fiona. Same rationale as ADR-030.

### Alternative D: DuckDB Spatial / ogr2ogr

SQL-based spatial join via DuckDB, or command-line via GDAL's ogr2ogr.

- **Reason for rejection:** DuckDB Spatial bundles GDAL internally. Same dependency chain.

---

## Consequences

### Positive

- **9,481 coastal cells recovered globally.** Valid GAUL codes assigned to all cells classified as "land" by PRIO-GRID whose centroids fall in water. In Africa+ME, 149 cells carrying 409,743 fatalities are restored to country-level aggregations.
- **Zero new dependencies.** Generation uses shapely + pyshp (existing). Consumption uses pyarrow (existing).
- **368 border cells corrected (gaul0).** Border cells assigned to the country covering the most area. gaul1: 1,453 redistributed. gaul2: 4,845 redistributed.
- **Zero consumer code changes.** Assembly, CM aggregation, consumer bridge, and region subsetting work without modification.
- **Documented Rust path.** Area-majority is the second spatial computation pattern, strengthening the case for eventual Rust migration.

### Negative

- **Precomputed table is an opaque artifact.** Mitigated by: generation script committed, provenance recorded, before/after comparison artifact produced.
- **Regeneration process must be documented.** When GAUL updates (~2030), someone must run the script and commit new files.
- **Name file gap.** Recovered cells have country codes but no names in `gaul0_name.parquet` (86,091 rows from centroid era vs 259,200 code rows). Region subsetting via `regions.py` is unaffected (name files unchanged), but recovered cells cannot be looked up by country name. Not a regression — these cells were previously unmapped entirely.
- **Shapely generation code is eventually throwaway.** When Rust is adopted, the Python generation script will be replaced. Accepted as the cost of WET-before-DRY.

---

## Validation Results

### Pre-analysis plan

This decision was pre-registered: hypotheses H1-H5 were stated before experiments were run, with pre-committed decision criteria. See `reports/investigation_area_majority_gaul/pre_analysis_plan.md`.

| Hypothesis | Verdict | Key Metric |
|------------|---------|------------|
| H1 Coastal Recovery | SURVIVED | 9,481 cells recovered (204 countries) |
| H2 No Assignment Loss | SURVIVED | 0 cells lost valid assignments; valid: 86,091 → 95,572 |
| H3 Border Redistribution | SURVIVED | 368 cells changed (gaul0), within [100, 2000] |
| H4 Performance | DEVIATION | 17.1 min total (threshold: 10 min; acceptable for batch job) |
| H5 Format Compatibility | SURVIVED | Schema match, all 3 levels, zero consumer code changes |

Per pre-committed decision criteria: H1 + H2 + H3 + H5 all hold → **adopt area-majority**.

### Before/after comparison

Documented in `reports/investigation_area_majority_gaul/before_after_comparison.md`.

### Ongoing monitoring

- **Content digest:** The provenance ledger records the content digest of each Parquet file. If the file changes unexpectedly, the digest check fails loudly.
- **Test suite:** 39 area-majority tests (unit, hypothesis, integration, splash zone) verify correctness across all phases. CM aggregation tests verify country-level totals.
- **Regeneration trigger:** When GAUL is next updated (~2030), run `scripts/generate_area_majority_gaul.py` with the new shapefile.

---

## Relationship to ADR-030

ADR-030 established the "tifffile now, Rust long-term" pattern for raster I/O. This ADR extends the same principle to vector spatial operations: "shapely now, Rust long-term."

The area-majority spatial join is the **second spatial computation pattern** in the datafactory:
1. Centroid-in-polygon (existing, `gaul_admin.py`)
2. Polygon-polygon intersection + area comparison (this ADR)

ADR-030's revisit condition for Rust was "after 2-3 raster sources are implemented." The equivalent for vector operations: when a third spatial computation need arises (e.g., distance-to-border, spatial lag, polygon simplification), the case for a Rust spatial tool becomes compelling. Two proven Python implementations provide the specification.

---

## Resolved Questions

1. **Island cells with minimal GAUL overlap.** Verified: area-majority assigns cells to the GAUL polygon with the largest intersection area, regardless of how small. No minimum threshold needed — any overlap is better than no assignment.

2. **Tied areas.** The generation script uses a deterministic tiebreaker: lowest GAUL code wins. In practice, exact ties are extremely rare with real polygon geometry. The tiebreaker is tested with synthetic data.

3. **Before/after impact on trained models.** The 368 border cells that change gaul0 assignment are a correction. Models should be retrained on the corrected data. No transition period needed — the old assignments were wrong.

4. **GAUL L1/L2 quality.** All three levels verified independently. L0: 95,572 valid cells, L1: 95,572 valid, L2: 95,572 valid. Zero invalid geometries in GAUL 2024 L2 shapefile.

---

## References

- Tollefsen, A. F., Strand, H., & Buhaug, H. (2012). PRIO-GRID: A unified spatial data structure. *Journal of Peace Research*, 49(2), 363-374.
- FAO GAUL 2024, Release Note 02 (area-majority assignment specification)
- ADR-025: Static Grid Features
- ADR-030: Raster Tooling — tifffile Now, Rust Long-Term
- ADR-012: Four-Layer Data Architecture
- C-149: `reports/postmortem_cm_unmapped_gaul_cells.md`
- Investigation: `reports/investigation_area_majority_gaul/`
