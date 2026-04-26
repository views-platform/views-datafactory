
# ADR-021: Zarr as Servable Export Format

**Status:** Accepted
**Date:** 2026-03-25
**Deciders:** Simon

---

## Context

The assembled grid is a 19 GB float32 npy file. Consumers must download
the entire file to access any subset — there is no way to fetch "just
Ethiopia 2020-2024" without loading all 456 months, 259,200 cells, and
43 features.

The CLAUDE.md contract ("npy now, zarr-ready") anticipated this moment:
the dimension order `[T, H, W, C]` and sidecar coordinate files were
designed for zarr conversion from the start (ADR-012).

The immediate goal is making the data available to VIEWS team members
via HTTP. Future consumers (broader research community) may follow.

---

## Decision

Add a zarr export script (`scripts/export_zarr.py`) that converts the
assembled grid to an **xarray-compatible zarr store**. The zarr store
can be served by any static HTTP server. Consumers access it with
`xarray.open_zarr(url)` and load only the data they need.

### Dataset structure

Each feature becomes a separate data variable with dimensions
`(time, lat, lon)`:

```
<xarray.Dataset>
Dimensions:       (time: 456, lat: 360, lon: 720)
Coordinates:
  * time          (time) datetime64[M] 1989-01 ... 2026-12
  * lat           (lat) float64 -89.75 -89.25 ... 89.25 89.75
  * lon           (lon) float64 -179.75 -179.25 ... 179.25 179.75
    pgid          (lat, lon) int32 1 2 3 ... 259198 259199 259200
Data variables:
    ged_sb_count  (time, lat, lon) float32 ...
    ged_sb_best   (time, lat, lon) float32 ...
    ... (one variable per assembled feature)
Attributes:
    title:              VIEWS Conflict Data Factory — Assembled Grid
    crs:                EPSG:4326
    resolution_degrees: 0.5
```

### Feature ordering

Zarr stores features as separate data variables with no intrinsic order.
When `load_dataset()` reads a zarr store, it uses the `feature_order`
attribute (list of feature names) if present; otherwise it falls back
to alphabetical order (`sorted(ds.data_vars)`). The npy backend always
uses `feature_names.json` order. To ensure consistent column ordering
across backends, zarr exports should include `feature_order` in
`ds.attrs`. See C-127 in the technical risk register.

### Chunking

12-month temporal chunks, full spatial extent per chunk:
- Chunk size: 360 x 720 x 12 x 4 bytes = ~12 MB per variable
- 1-year query reads 1 chunk; full timeline reads 38 chunks
- Per-variable: loading one feature does not touch others

### Why one variable per feature (not a 4th dimension)

xarray consumers expect `ds["ged_sb_best"].sel(time="2020")`, not
`ds["grid"].sel(feature="ged_sb_best")`. Separate variables enable
per-variable compression, chunking, and metadata. This is standard
practice for gridded spatiotemporal datasets (cf. ERA5, CMIP6).

---

## Rationale

- **Zarr over HTTP is infrastructure-free.** Any static file server
  (nginx, caddy, S3) can serve zarr. No application code, no running
  process, no crashes.
- **xarray is the standard.** Climate science, remote sensing, and
  geospatial analysis all use xarray for gridded data. VIEWS team
  members know it or can learn it from abundant documentation.
- **Lazy loading solves the 19 GB problem.** Consumers working on one
  country or one decade download only the relevant chunks (~12 MB
  each), not the full dataset.
- **Backward-compatible.** npy files are still produced. zarr is an
  additional export, not a replacement.

---

## Considered Alternatives

### Alternative A: REST API (FastAPI / Flask)
- **Pros:** Query flexibility, JSON responses for non-Python consumers.
- **Cons:** Requires running application, maintenance, monitoring.
  Overkill for internal Python consumers who can use xarray directly.
- **Reason for rejection:** Static serving is simpler and sufficient
  for current consumers. Revisit if non-Python consumers emerge.

### Alternative B: Cloud-optimized GeoTIFF (COG)
- **Pros:** Broad GIS tool support, standard in remote sensing.
- **Cons:** Designed for 2D raster, not 4D spatiotemporal. Poor fit
  for time-series queries. Requires rasterio dependency.
- **Reason for rejection:** Wrong data model for monthly conflict data.

### Alternative C: Parquet (already available)
- **Pros:** Already implemented via `export_dataframe.py`.
- **Cons:** Flat table, no spatial indexing, no lazy loading of spatial
  subsets. Good for tabular analysis, poor for gridded access.
- **Status:** Kept as complementary export format.

---

## Consequences

### Positive
- Internal consumers can access subsets without downloading 19 GB
- Standard xarray interface — no custom client code needed
- Serving requires only a static HTTP server
- Coordinates and metadata travel with the data

### Negative
- Two new dependencies: `xarray`, `zarr`
- Zarr store size is comparable to npy (~18 GB) — not compressed
- Consumers must know xarray (mitigated by consumer guide)

---

## Implementation Notes

- `scripts/export_zarr.py` — conversion script following `export_dataframe.py` pattern
- Dependencies added to `pyproject.toml`: `xarray>=2024.1,<2026`, `zarr>=2.16,<3`
- Output: `data/assembled/grid.zarr` (default; inside assembled directory, gitignored under `data/`)
- Chunking configurable via `--chunks-time` (default: 12 months)
- Consumer guide: `docs/guides/zarr_consumer_guide.md`

---

## Validation & Monitoring

- Script produces a zarr store that opens cleanly with `xarray.open_zarr()`
- Dimension names, coordinate values, and feature count match the source grid
- Round-trip integrity check (v1.2.4): after export, reads back every feature from the zarr store and verifies per-feature sums match the source grid within floating-point tolerance (>0.5 absolute). Catches partial writes, chunking bugs, and stale stores. Memory-efficient — loads one feature at a time.
- Store size is within 10% of source npy size (no unexpected bloat)
- Consumer guide examples are copy-pasteable and produce correct output

---

## References

- ADR-012: Four-layer data architecture (compilation output format)
- `scripts/export_zarr.py`: Implementation
- `docs/guides/zarr_consumer_guide.md`: Consumer documentation
- xarray documentation: https://docs.xarray.dev/
- zarr specification: https://zarr.readthedocs.io/
- Kleppmann & Riccomini, *Designing Data-Intensive Applications*, 2nd ed., O'Reilly 2026:
  - Ch.3 pp.91-99: Column-oriented storage — read only the columns you need, drastically reducing I/O for analytics
  - Ch.4 p.131: Parquet/columnar formats for archival storage — re-encode snapshots in analytics-friendly format
  - Ch.10 pp.411-413: Batch-derived outputs — read-only database files written once, replaced atomically
