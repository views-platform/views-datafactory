# Class Intent Contract: GhsPopViewpointConfig

**Status:** Active
**Owner:** Simon Polichinel von der Maase
**Last reviewed:** 2026-05-19
**Related ADRs:** ADR-009, ADR-012, ADR-014, ADR-029, ADR-030

---

## 1. Purpose

> Immutable configuration for building a GHS-POP viewpoint from harvested GeoTIFF files.

Carries the source directory (harvest output), output/ledger paths, epoch selection, raster metadata identifiers, spatial aggregation method, temporal interpolation method, temporal range, nodata sentinel, and version tag.

This is a raster viewpoint — it performs spatial aggregation (30-arcsecond pixels to 0.5-degree PRIO-GRID cells) and temporal interpolation (12 five-year epochs to monthly), not survivorship or event distribution.

---

## 2. Non-Goals (Explicit Exclusions)

- This class does **not** implement spatial aggregation or temporal interpolation (that is `build_ghspop_v1`)
- This class does **not** validate that `source_dir` exists or contains GeoTIFFs (checked at build time)
- This class does **not** read or write any files
- This class does **not** know about the harvester, consolidation, or compilation layers
- This class does **not** implement survivorship strategies (raster data has no event identity)
- This class does **not** validate `aggregation` or `temporal_interpolation` against known strategies

---

## 3. Responsibilities and Guarantees

- Guarantees immutability (frozen dataclass)
- Guarantees `version` is non-empty
- Guarantees `epochs` is non-empty
- Guarantees all `epochs` are members of `KNOWN_EPOCHS` (1975..2030 in 5-year steps)
- Carries `source_dir`: Path to harvested GeoTIFFs (required, no default)
- Carries `output_path`: viewpoint Parquet destination
- Carries `ledger_path`: viewpoint provenance ledger destination
- Constructs deterministic TIF filenames via `tif_filename(epoch)` from `release`, `crs`, `resolution`

---

## 4. Inputs and Assumptions

- `source_dir`: Path (required, no default) — directory containing harvested GeoTIFFs
- `output_path`: Path (default: `data/viewpoint/ghspop_v1.parquet`)
- `ledger_path`: Path (default: `provenance/viewpoint/ghspop_v1_ledger.jsonl`)
- `epochs`: tuple[int, ...], non-empty subset of `KNOWN_EPOCHS` (default: all 12 epochs)
- `release`: str, JRC release identifier (default: `"R2023A"`)
- `resolution`: str, raster resolution code (default: `"30ss"`)
- `crs`: str, coordinate reference system code (default: `"4326"`)
- `aggregation`: str, spatial aggregation method (default: `"sum"`)
- `temporal_interpolation`: str, temporal fill method (default: `"step"`)
- `start_year`: int, first output year (default: `1975`)
- `start_month`: int, first output month (default: `1`)
- `end_year`: int, last output year (default: `2030`)
- `end_month`: int, last output month (default: `12`)
- `nodata`: float, raster nodata sentinel (default: `-200.0`)
- `version`: str, non-empty (default: `"ghspop_v1"`)

Assumptions not met cause immediate `ValueError`.

---

## 5. Outputs and Side Effects

- No side effects. Pure configuration container.
- `tif_filename(epoch)` returns a deterministic filename string matching JRC naming convention.

---

## 6. Failure Modes and Loudness

- `ValueError` on empty `version`
- `ValueError` on empty `epochs`
- `ValueError` on any epoch not in `KNOWN_EPOCHS`
- `AttributeError` on any attempt to mutate fields (frozen)

All failures are immediate and loud. No silent fallbacks.

---

## 7. Boundaries and Interactions

- Used by `build_ghspop_v1` as the sole configuration input
- Paths consumed by `tifffile.imread`, `pq.write_table`, and `append_ledger_entry`
- Must not depend on any other `datafactory_*` config class
- Registered via `register_builder("ghspop_v1", ...)`

---

## 8. Examples of Correct Usage

```python
cfg = GhsPopViewpointConfig(source_dir=Path("data/raw/ghspop"))
cfg = GhsPopViewpointConfig(
    source_dir=Path("data/raw/ghspop"),
    epochs=(2020, 2025),
    version="ghspop_recent_v1",
)
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: empty version
GhsPopViewpointConfig(
    source_dir=Path("data/raw/ghspop"),
    version="",
)  # ValueError

# WRONG: empty epochs
GhsPopViewpointConfig(
    source_dir=Path("data/raw/ghspop"),
    epochs=(),
)  # ValueError

# WRONG: unknown epoch
GhsPopViewpointConfig(
    source_dir=Path("data/raw/ghspop"),
    epochs=(1999,),
)  # ValueError

# WRONG: mutating frozen config
cfg = GhsPopViewpointConfig(source_dir=Path("data/raw/ghspop"))
cfg.version = "new"  # AttributeError
```

---

## 10. Test Alignment

- **Green:** Default construction, frozen enforcement, custom epochs, full end-to-end flow, schema validation, provenance recording, builder registry, zero-skip, PGID mapping, month_id correctness
- **Beige:** Nodata handling, empty epochs rejection, unknown epoch rejection, all-zero raster
- **Red:** Missing source directory, missing epoch file, negative population clamping, non-divisible raster dimensions

Tests in `tests/test_ghspop_viewpoint.py`.

---

## 11. Evolution Notes

- `aggregation` and `temporal_interpolation` are currently string fields with no validation against known strategies. If additional strategies are added (e.g., linear interpolation), consider validating against an enum.
- If JRC publishes R2024A, a new version tag and potentially new epochs would be needed. The config supports this without structural changes.
- Consolidation layer is currently skipped (ADR-029). If a second release requires consolidation, `source_dir` would change from harvest output to consolidated store.

---

## End of Contract

This document defines the **intended meaning** of `GhsPopViewpointConfig`.

Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
