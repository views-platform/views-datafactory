# Technical Approach Evaluation: Area-Majority Spatial Join

**Date:** 2026-06-04
**Issue:** #115 / C-149

---

## 1. Problem Statement

The GAUL spatial join in `gaul_admin.py:183-260` assigns PRIO-GRID cells to countries by testing whether each cell's centroid falls inside a GAUL polygon. This is a point-in-polygon operation.

For 149 coastal cells, the centroid (center of the 0.5-degree square) falls in water — outside any GAUL polygon. These cells receive `gaul0_code = -1` and are excluded from country-level aggregations by the `country_ids > 0` filter in `grid_to_country_month.py`.

**Quantified impact** (from `reports/postmortem_cm_unmapped_gaul_cells.md`):

| Metric | Value |
|--------|-------|
| Affected cells | 149 unmapped + 454 border (603 total with gaul0_code issues) |
| State-based fatalities lost | 409,743 / ~10.5M total (~3.9%) |
| Non-state fatalities lost | ~6,012 (~3.3%) |
| One-sided fatalities lost | ~7,986 (~0.7%) |
| Max single-month gap | 2,688 fatalities |

The gap is silent — no error, no warning, no log entry. Models trained on country-month data see ~4% fewer fatalities than models trained on the same data at PRIO-GRID resolution.

## 2. Input Data Characteristics

Both inputs to the spatial join are effectively static:

| Dataset | Last update | Previous update | Update frequency |
|---------|-------------|-----------------|-----------------|
| GAUL L2 | 2024 | 2015 | ~9 years |
| PRIO-GRID 2.0 | 2015 (frozen) | — | Never (grid definition is fixed) |

This means a precomputed lookup table would be valid indefinitely. The next GAUL update is not expected before ~2030.

**GAUL shapefile size:** 775 MB (GAUL_2024_L2.shp), 45,524 polygons, 0 invalid geometries after `make_valid()`.

**PRIO-GRID cell count:** 259,200 cells globally (360 × 720 at 0.5-degree resolution). 13,110 cells in the Africa + Middle East legacy region.

## 3. Approaches Evaluated

### Approach A: Shapely-only (polygon intersection)

**Description:** Extend the existing `_spatial_join()` function. Instead of testing centroid points against GAUL polygons, build 0.5-degree cell polygons (`shapely.geometry.box`) and compute polygon-polygon intersections. For each cell, query the STRtree for candidates, compute `cell.intersection(gaul_poly).area` for each, assign the cell to the polygon with the largest area.

**Dependencies:** None new. `shapely>=2.0` and `pyshp>=2.3` are already in `pyproject.toml`.

**Benchmark results** (500 real Africa+ME cells, 2026-06-04):

| Metric | Value |
|--------|-------|
| Sample size | 500 cells |
| GAUL L2 polygons | 45,524 |
| STRtree build time | ~2s |
| Per-cell join rate | 1,218 cells/sec |
| GAUL shapefile load | 62.5s |
| Extrapolated: 13,110 cells | ~73s (1.2 min) |
| Extrapolated: 259,200 cells | ~213s (3.5 min) |
| Total estimated (global) | ~276s (4.6 min) including load |

Benchmark script: `/tmp/bench_area_majority.py` (not in repo — to be committed as part of implementation).

**Shapely 2.x vectorized APIs** (not yet benchmarked, potential speedup):
- `STRtree.query(geometry_array, predicate="intersects")` — batch candidate lookup
- `shapely.intersection(geom_array_a, geom_array_b)` — vectorized intersection
- `shapely.area(geom_array)` — vectorized area computation
- These are numpy ufuncs backed by GEOS, potentially 5-10x faster than per-cell Python loops

**Verdict:** Viable. Zero new dependencies. Performance is acceptable even without vectorization. Recommended for generating the precomputed table.

### Approach B: Rust binary (geo-rs)

**Description:** A standalone Rust program that reads the GAUL shapefile and PRIO-GRID centroids, computes area-majority assignments, and writes the output as Parquet (or CSV/JSON). Compiled to a static binary via `x86_64-unknown-linux-musl`. Zero runtime dependencies — `scp` the binary to any server and run it.

**Rust ecosystem (as of 2026):**

| Crate | Version | Purpose | Maturity |
|-------|---------|---------|----------|
| `geo` | 0.31.0 | `BooleanOps::intersection()`, `unsigned_area()` | Stable, pure Rust, outperforms GEOS 1-47x |
| `rstar` | 0.12.2 | R-tree spatial index | Stable, integrates with `geo` types |
| `shapefile` | 0.7.0 | Read .shp + .dbf attributes | Stable, pure Rust |
| `arrow` / `parquet` | 53.x | Parquet output | Stable, Apache-maintained |

**Estimated development effort:** 10-15 hours (weekend project for someone comfortable with Rust).

**Expected performance:** Full global grid in seconds, not minutes. Rust's `geo` crate outperforms GEOS (which backs shapely) by 1-47x depending on the operation.

**Alignment with ADR-030:** ADR-030 states "a Rust-based raster processing tool will replace tifffile" as a long-term direction, with the caveat "no Rust code is written until the pattern is proven in Python." The area-majority spatial join would be the second spatial computation pattern (after centroid), strengthening the case for Rust migration.

**Verdict:** Best long-term option. Premature for a one-time computation on static data. Recommended as the documented upgrade path when a second spatial computation need arises.

### Approach C: Precomputed static table

**Description:** Run the spatial join once (using any tool), store the result as Parquet files in `data/raw/gaul_admin/`. The harvester reads a table instead of computing spatial joins at runtime.

**Output format:** Same `(gid, value)` Parquet files as current centroid output: `gaul0_code.parquet`, `gaul1_code.parquet`, `gaul2_code.parquet`. Estimated size: ~1.7 MB total.

**Precedent in repo:** `land_pgids.json` (static list of land cell IDs), `africa_me_legacy_pgids.json` (static list of Africa+ME cell IDs). Both are precomputed and checked into the repo.

**Regeneration process:** When GAUL updates (estimated ~2030), run the generation script again. Document the process in the ADR.

**Provenance:** Record GAUL version, computation method, content digest, and timestamp in the ingestion ledger — same as any other harvested artifact.

**Verdict:** Recommended as the delivery mechanism. Decouples the computation (one-time, any tool) from the consumption (every pipeline run, every server). Zero runtime spatial dependencies.

### Approach D: geopandas

**Description:** Use geopandas' `sjoin()` with `how="inner", predicate="intersects"` followed by area computation. geopandas wraps GEOS (via shapely) and provides a DataFrame API for spatial operations.

**Dependencies:** `geopandas` pulls in `fiona` (GDAL bindings), `pyproj`, and transitively `libgdal`, `libgeos`, `libproj`. On Ubuntu/Debian, this requires system packages (`libgdal-dev`). On Alpine/minimal containers, GDAL compilation can take 20+ minutes.

**Why rejected:**

ADR-030 documents the rationale extensively:
> "rasterio (GDAL bindings) was evaluated and is not the anticipated long-term solution."

The same arguments apply to geopandas:
1. **Dependency hell:** GDAL installation fails on minimal servers, requires system packages, version conflicts
2. **Memory unpredictability:** GDAL opens files via its own memory management, not Python's
3. **Every server pays the cost:** The "one-time computation" framing is false — every `pip install` / `uv sync` on every machine pulls GDAL
4. **Existing alternative:** shapely (already installed) provides the same GEOS operations without GDAL

The `views-postprocessing` repo uses geopandas for this exact operation (3,100-line runtime mapper with 774 MB bundled shapefiles). It has 22 risk register concerns. We are not replicating that architecture.

**Verdict:** Rejected. Conflicts with ADR-030.

### Approach E: DuckDB Spatial / ogr2ogr

**Description:** DuckDB's spatial extension provides `ST_Intersection()` and `ST_Area()` via SQL. ogr2ogr (part of GDAL) can compute spatial joins from the command line.

**Why rejected:** DuckDB's spatial extension bundles GDAL internally. ogr2ogr requires GDAL on the system. Both introduce the same dependency chain as geopandas. The SQL interface adds no value for a one-time batch computation — the overhead of loading data into DuckDB exceeds the computation itself.

**Verdict:** Rejected. Same GDAL dependency problem.

## 4. Recommendation

**Approach C (precomputed table), generated by Approach A (shapely-only).**

This recommendation separates two concerns:

1. **How to compute the table:** Shapely polygon intersection (zero new dependencies, proven in benchmark, extends existing code pattern)
2. **How to deliver the table:** Static Parquet files in `data/raw/gaul_admin/` (zero runtime spatial dependency, same format as today, consumed by assembly without code changes)

The generation script runs once per GAUL version. The output is consumed by every pipeline run on every server. If shapely performance ever becomes insufficient (unlikely given the ~5-9 year GAUL update cycle), the Rust binary (Approach B) is the documented upgrade path.

### Why not Rust now?

ADR-030's principle: "no Rust code is written until the pattern is proven in Python." The area-majority pattern will be proven by the shapely implementation. When a second spatial computation need arises (e.g., distance-to-border, spatial lag), the combined evidence will justify the Rust investment. Building a Rust binary for a computation that runs once every 5-9 years is premature optimization.

### Why not just extend gaul_admin.py to run at harvest time?

The current centroid join runs during harvest. We could replace it with area-majority at harvest time. But:
- Every server would compute the join (shapefile load + spatial computation), even though the result is always the same
- Harvest time would increase by ~5 minutes per run
- A precomputed table makes the harvester simpler (read a file, not compute geometry)
- The generation script is still committed to the repo — anyone can regenerate

## 5. References

- Tollefsen, A. F., Strand, H., & Buhaug, H. (2012). PRIO-GRID: A unified spatial data structure. *Journal of Peace Research*, 49(2), 363-374. DOI: 10.1177/0022343311431287
- FAO GAUL 2024 Release Note 02 (area-majority assignment specification)
- ADR-030: Raster Tooling — tifffile Now, Rust Long-Term (`docs/ADRs/030_raster_tooling.md`)
- ADR-025: Static Grid Features (`docs/ADRs/025_static_grid_features.md`)
- C-149 root cause: `reports/postmortem_cm_unmapped_gaul_cells.md`
- Benchmark script: `/tmp/bench_area_majority.py` (to be committed during implementation)
- Shapely 2.x documentation: STRtree, vectorized operations
- Rust geo crate: `georust/geo` — `BooleanOps::intersection()`, benchmarks vs GEOS
