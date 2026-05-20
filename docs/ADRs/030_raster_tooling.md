# ADR-030: Raster Tooling — tifffile Now, Rust Long-Term

**Status:** Accepted
**Date:** 2026-05-18
**Deciders:** Simon Polichinel von der Maase, Claude Code
**Applies:** ADR-029 (GHS-POP as First Population Source), ADR-012 (Four-Layer Data Architecture)

---

## Context

ADR-029 selects GHS-POP as the first raster data source and explicitly defers the raster toolchain choice to a separate ADR. With GHS-POP, the data factory moves from event-level API data (UCDP, ACLED) to pre-gridded raster files (GeoTIFF). This requires tooling for reading raster pixel data, handling nodata values, and spatial aggregation to PRIO-GRID cells.

A thorough investigation of the JRC download portal (Phase 0A) revealed a critical finding: **JRC provides GHS-POP in WGS84 (EPSG:4326) at 30-arcsecond resolution**, not only in Mollweide as initially assumed. This eliminates the need for CRS reprojection. On the WGS84 grid, each PRIO-GRID cell (0.5°) contains exactly 60×60 source pixels, making spatial aggregation a numpy reshape+sum operation — no coordinate transformation required.

A format survey of foreseeable raster data sources was also conducted:

| Domain | Dataset | Format | CRS |
|--------|---------|--------|-----|
| Population | GHS-POP (JRC) | GeoTIFF | WGS84 available |
| Infrastructure | GHS-BUILT (JRC) | GeoTIFF | WGS84 available |
| Precipitation | CHIRPS | GeoTIFF, NetCDF | WGS84 |
| Climate | ERA5 (ECMWF) | GRIB natively, NetCDF available | Regular lat/lon |
| Food insecurity | FEWS NET / SEDAC | GeoTIFF, Shapefiles | WGS84 |
| Floods | Copernicus GFM | GeoTIFF | WGS84 configurable |

Every foreseeable source is either GeoTIFF (WGS84) or NetCDF. xarray, already in our dependencies, reads NetCDF natively. The question is therefore narrower than initially expected: **which tool reads WGS84 GeoTIFF files into numpy arrays?**

This decision matters now because GHS-POP implementation is next on the roadmap and the tooling choice affects dependency management, server deployment, and the architectural boundary between Python orchestration and raster I/O.

---

## Decision

### Short-term: tifffile for GeoTIFF I/O

**tifffile** is the raster I/O tool for the current and next several raster data sources. It reads GeoTIFF files as numpy arrays with no system dependencies. Combined with xarray for NetCDF sources, this covers the foreseeable data landscape without introducing GDAL.

### Long-term direction: Rust for raster processing

When the project has processed 2–3 raster sources and the requirements are well-understood, a Rust-based raster processing tool will replace tifffile. The Rust tool will handle GeoTIFF I/O, spatial aggregation, and nodata handling as a compiled binary with zero runtime dependencies and predictable memory behavior. This is a stated direction, not a current commitment — no Rust code is written until the pattern is proven in Python.

### Not chosen: rasterio / GDAL

rasterio (GDAL bindings) was evaluated and is not the anticipated long-term solution. It remains an option of last resort if an unforeseen data source requires a format or CRS transformation that neither tifffile/Rust nor xarray can handle. See Considered Alternatives for the full reasoning.

### In scope

- Adding `tifffile` as a dependency
- Python ≥3.12 version bump (tifffile's current releases require it; assessed as safe for this repo)
- Reading WGS84 GeoTIFF files into numpy arrays
- GeoTIFF metadata validation (CRS tag, dimensions, nodata)
- Spatial aggregation via numpy (block-sum to 0.5° cells)
- xarray for NetCDF sources (already a dependency, no new work)

### Out of scope

- CRS reprojection (not needed — WGS84 data is available for all foreseeable sources)
- Writing or modifying raster files (we only read)
- Rust implementation (deferred until 2–3 raster sources are implemented in Python)
- GDAL or rasterio installation

---

## Rationale

### WGS84 availability eliminates the core argument for GDAL

The primary justification for rasterio/GDAL was CRS reprojection (Mollweide → WGS84). The JRC portal investigation showed that WGS84 data is available as a direct download for GHS-POP and GHS-BUILT. The format survey found the same for CHIRPS, FEWS NET, and Copernicus flood data. ERA5 uses NetCDF, which xarray handles. With no reprojection needed, GDAL's core capability goes unused.

### tifffile matches WET-before-DRY

This project has been disciplined about not abstracting before the pattern is proven (two event sources before considering shared abstractions). The same discipline applies to tooling. tifffile solves the immediate problem — reading GeoTIFF pixel data — with minimal complexity. Building a Rust tool or adopting GDAL before processing a single raster would be premature.

### Rust as long-term direction, not current commitment

The long-term case for Rust over GDAL rests on three factors:

1. **Dependency freedom.** A Rust binary is self-contained. No `libgdal` system package, no version coupling between GDAL and Python bindings, no "GDAL dependency hell." On every machine, forever, it just runs.

2. **Memory predictability.** The production server has 8 GB RAM. We already hit OOM during ACLED compilation with 2M events (C-157, fixed by column projection). Processing multi-GB rasters in Rust gives explicit control over memory allocation — critical when multiple raster sources are processed in sequence.

3. **Clean architectural boundary.** Rust handles raster I/O and spatial math (a bounded, well-defined problem). Python handles orchestration and opinions (viewpoint logic, temporal interpolation, provenance). The language boundary matches the responsibility boundary.

The case against committing to Rust now: we haven't processed a single raster yet. Building GHS-POP with tifffile first teaches us the exact operations needed, the edge cases that appear, and how the viewpoint layer wants to consume the data. That experience becomes the specification for the Rust tool. This is the same WET-before-DRY reasoning that guided UCDP → ACLED → shared abstractions.

### Why tifffile specifically

TIFF is a notoriously flexible format — OME axes, metadata conflicts, exotic compression, ImageJ/QuPath compatibility issues are real problems for people working with diverse TIFF sources. But our situation is narrower than the general case: one product, one producer, predictable structure. GHS-POP GeoTIFFs from JRC are single-band, known dimensions (21,600×43,200 for 30ss), standard compression (LZW or DEFLATE), known nodata (-9999). The TIFF complexity problem does not apply to our use case.

tifffile reads GeoTIFF data directly to numpy arrays via `imread()`. It handles GeoTIFF metadata tags (GeoKeys) for CRS validation. It supports memory-mapped reading for large files. Standard compression (LZW, DEFLATE) is handled natively without optional dependencies. If JRC uses an exotic compression codec, tifffile's optional `imagecodecs` dependency covers it — but this is unlikely for a population grid.

Pillow and imageio were evaluated and rejected (see Considered Alternatives). Pillow cannot handle our file sizes without workarounds and cannot read GeoTIFF CRS tags. imageio uses tifffile as its TIFF backend, making it an unnecessary wrapper.

### The format landscape is narrower than GDAL's breadth

GDAL reads hundreds of raster formats and handles arbitrary CRS transformations. Among "big solid institutional" datasets relevant to conflict forecasting, every source we surveyed provides GeoTIFF or NetCDF in WGS84 or standard geographic coordinates. We would be paying the GDAL dependency tax for capabilities we don't use.

---

## Considered Alternatives

### Alternative A: rasterio (GDAL bindings)

The standard geospatial Python toolkit. Full CRS handling, reprojection, resampling, reading every raster format.

- **Pros:** Battle-tested, extensive documentation, handles any raster format or CRS we might encounter, large community.
- **Cons:** Requires `libgdal` system library on every machine. Version coupling between rasterio and GDAL is a known maintenance problem. Heavy transitive dependencies (PROJ, GEOS). Memory behavior with multi-GB rasters is not always predictable.
- **Reason for deferral:** With WGS84 data available for all foreseeable sources, GDAL's reprojection and format breadth go unused. We would be taking on a significant system dependency for capabilities we don't need. Not rejected permanently — it remains the option of last resort if an unforeseen source demands it.
- **Revisit condition:** A required data source arrives in a format that neither tifffile/Rust nor xarray can read, AND does not offer a WGS84/geographic variant.

### Alternative B: rioxarray (xarray + rasterio)

Higher-level API wrapping rasterio, integrating raster I/O with xarray's data model.

- **Pros:** Convenient xarray integration, clean API for multi-band raster operations.
- **Cons:** Same GDAL system dependency as rasterio. More abstraction than needed for our use case (read array, block-sum, done).
- **Reason for rejection:** Inherits all of rasterio's dependency costs with no offsetting benefit — we don't need the xarray integration for spatial aggregation.

### Alternative C: Pillow

General-purpose image library with TIFF support.

- **Pros:** Widely used, well-maintained, already a common transitive dependency in Python ecosystems.
- **Cons:** Has a decompression bomb guard that rejects large images by default — a 21,600×43,200 raster would require overriding the pixel limit. Returns PIL Image objects, requiring conversion to numpy. Cannot read GeoTIFF metadata tags (no CRS validation). Not designed for large scientific rasters.
- **Reason for rejection:** Requires workarounds for our file sizes and cannot validate CRS. tifffile is the more direct tool for scientific raster data.

### Alternative D: imageio

Modern image I/O library with a clean API.

- **Pros:** Simple `imread()` interface, supports multiple backends.
- **Cons:** For TIFF files, imageio uses tifffile as its backend. Using imageio means adding an abstraction layer on top of the tool we'd actually be using.
- **Reason for rejection:** Wrapping tifffile adds a dependency without adding capability.

### Alternative E: Commit to Rust now

Write the Rust raster processing tool immediately for GHS-POP, skip the tifffile phase entirely.

- **Pros:** No throwaway work. Sets up Rust infrastructure once, reused for all raster sources.
- **Cons:** Larger upfront investment before we've processed a single raster. Adds a build system (maturin or standalone CLI) we haven't used before. Commits to a tool design before understanding the real requirements. Counter to WET-before-DRY discipline.
- **Reason for deferral:** The operations are probably simple enough to get right on the first try, but "probably" is doing work in that sentence. Building GHS-POP with tifffile first is lower risk and produces concrete experience to inform the Rust design.
- **Revisit condition:** After 2–3 raster sources are implemented, the pattern is clear, and the tifffile implementations serve as the specification.

---

## Consequences

### Positive

- **Zero system dependencies for raster I/O.** tifffile is pure Python, pip-installable everywhere. No `apt install libgdal-dev`, no version coupling, no platform-specific build issues.
- **Fastest path to working GHS-POP.** tifffile + numpy is the simplest tool that solves the current problem.
- **Clear long-term direction.** Rust is documented as the target, so tifffile code is written with the understanding that it will be replaced — no over-investment in Python raster abstractions.
- **Server deployment is trivial.** `pip install tifffile` works on any platform with Python ≥3.12.

### Negative

- **tifffile code is eventually throwaway.** When the Rust tool is built, the tifffile-based raster reading will be replaced. This is accepted as the cost of WET-before-DRY learning.
- **tifffile doesn't parse GeoTIFF CRS metadata as first-class objects.** We validate CRS by reading raw TIFF GeoKey tags rather than through a geospatial API. This is adequate for WGS84 validation but less ergonomic than rasterio.
- **Python ≥3.12 version bump required.** Current tifffile releases require Python 3.12+. This is assessed as safe for this repository (no 3.10-specific patterns in codebase, all dependencies have 3.12-compatible versions) but requires bumping dependency lower bounds (numpy ≥1.26, pandas ≥2.0, matplotlib ≥3.8).

---

## Implementation Notes

### Immediate (GHS-POP integration)

1. Bump `requires-python` to `">=3.12"` in `pyproject.toml`. Adjust dependency lower bounds as needed.
2. Add `tifffile` to dependencies.
3. Verify `uv run pytest` passes after dependency changes.
4. GeoTIFF reading pattern: `tifffile.imread(path)` returns numpy array. Validate dimensions (21600×43200 for 30ss global), check GeoKey tags for EPSG:4326, replace nodata (-9999) with 0.
5. Spatial aggregation: `data.reshape(360, 60, 720, 60).sum(axis=(1, 3))` produces the 360×720 PRIO-GRID array.

### When adding Rust (after 2–3 raster sources)

1. Decide integration strategy: PyO3 extension module (Python-importable) vs standalone CLI (subprocess).
2. Use Rust `tiff` crate for GeoTIFF I/O.
3. The Python tifffile implementations serve as test oracles — the Rust tool must produce identical output for the same input.
4. Retire tifffile dependency once Rust tool is validated.

### What stays in Python regardless

- Viewpoint orchestration (temporal interpolation, release selection, provenance)
- NetCDF reading (xarray)
- Compilation (grid placement)
- All tests

---

## Validation & Monitoring

### tifffile adequacy

- **Signal:** tifffile successfully reads GHS-POP and GHS-BUILT GeoTIFFs with correct data, dimensions, and nodata handling.
- **Failure trigger:** A required GeoTIFF file that tifffile cannot read (unusual compression, tiling, or data type). This would be the point to evaluate rasterio or accelerate Rust.

### Rust timing

- **Signal:** After 2–3 raster sources are implemented with tifffile, the raster I/O pattern is stable and well-understood.
- **Failure trigger:** Rust development reveals that the problem is more complex than the Python prototype suggested, or the Rust geospatial crate ecosystem is insufficiently mature.

### GDAL last resort

- **Trigger:** A required data source arrives in a format that neither tifffile, Rust `tiff` crate, nor xarray can handle, AND does not offer a WGS84/standard geographic variant.

---

## Open Questions

1. **Rust integration strategy.** PyO3 extension module vs standalone CLI — deferred until implementation.
2. **Infrastructure data landscape.** The format survey covered likely sources but infrastructure data has not been broadly surveyed. An unusual infrastructure dataset could change the tooling calculus.
3. **tifffile compression support.** GHS-POP GeoTIFFs are compressed (likely LZW or DEFLATE). tifffile handles these, but the specific compression used by JRC should be verified on first download.
4. **Python 3.12 on production server.** The Hetzner server currently runs the pipeline. Python 3.12 availability needs to be confirmed before deployment.

---

## References

- ADR-029: GHS-POP as First Population Source — motivation for this decision
- ADR-012: Four-Layer Data Architecture — raster I/O sits in Layer 1 (harvest) and Layer 3 (viewpoint)
- JRC download portal: `https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_POP_GLOBE_R2023A/`
- tifffile on PyPI: `https://pypi.org/project/tifffile/`
- Rust `tiff` crate: `https://crates.io/crates/tiff`
