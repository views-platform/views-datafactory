# Class Intent Contract: GhsBuiltSViewpointConfig

**Status:** Active
**Owner:** Simon Polichinel von der Maase
**Last reviewed:** 2026-05-23
**Related ADRs:** ADR-009, ADR-012, ADR-014, ADR-030, ADR-034

---

## 1. Purpose

> Immutable configuration for building a GHS-BUILT-S viewpoint from harvested GeoTIFF files.

Carries the source directory (harvest output), output/ledger paths, epoch selection, raster metadata identifiers, spatial aggregation method, temporal interpolation method, temporal range, and version tag.

This is a raster viewpoint — it performs spatial aggregation (30-arcsecond pixels to 0.5-degree PRIO-GRID cells) and temporal interpolation (12 five-year epochs to monthly), not survivorship or event distribution.

---

## 2. Non-Goals (Explicit Exclusions)

- This class does **not** implement spatial aggregation or temporal interpolation (that is `build_ghsbuilts_v1`)
- This class does **not** validate that `source_dir` exists or contains GeoTIFFs (checked at build time)
- This class does **not** read or write any files
- This class does **not** know about the harvester, consolidation, or compilation layers
- This class does **not** implement survivorship strategies (raster data has no event identity)
- This class does **not** validate `aggregation` against known strategies (only `"sum"` is implemented)
- This class does **not** handle nodata masking (GHS-BUILT-S is uint32 where 0 = no built-up, not a nodata sentinel)

---

## 3. Responsibilities and Guarantees

- Guarantees immutability (frozen dataclass)
- Guarantees `version` is non-empty
- Guarantees `epochs` is non-empty
- Guarantees all `epochs` are members of `KNOWN_EPOCHS` (1975..2030 in 5-year steps)
- Guarantees `temporal_interpolation` is one of `VALID_TEMPORAL_INTERPOLATIONS` (`"step"`, `"linear"`)
- Carries `source_dir`: Path to harvested GeoTIFFs (required, no default)
- Carries `output_path`: viewpoint Parquet destination
- Carries `ledger_path`: viewpoint provenance ledger destination
- Constructs deterministic TIF filenames via `tif_filename(epoch)` from `release`, `crs`, `resolution`

---

## 4. Inputs and Assumptions

- `source_dir`: Path (required, no default) — directory containing harvested GeoTIFFs
- `output_path`: Path (default: `data/viewpoint/ghsbuilts_v1.parquet`)
- `ledger_path`: Path (default: `provenance/viewpoint/ghsbuilts_v1_ledger.jsonl`)
- `epochs`: tuple[int, ...], non-empty subset of `KNOWN_EPOCHS` (default: all 12 epochs)
- `release`: str, JRC release identifier (default: `"R2023A"`)
- `resolution`: str, raster resolution code (default: `"30ss"`)
- `crs`: str, coordinate reference system code (default: `"4326"`)
- `aggregation`: str, spatial aggregation method (default: `"sum"`)
- `temporal_interpolation`: str, temporal fill method; must be one of `VALID_TEMPORAL_INTERPOLATIONS` (`"step"`, `"linear"`) (default: `"linear"`)
- `start_year`: int, first output year (default: `1975`)
- `start_month`: int, first output month (default: `1`)
- `end_year`: int, last output year (default: `2030`)
- `end_month`: int, last output month (default: `12`)
- `version`: str, non-empty (default: `"ghsbuilts_v1"`)

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
- `ValueError` on `temporal_interpolation` not in `VALID_TEMPORAL_INTERPOLATIONS`
- `AttributeError` on any attempt to mutate fields (frozen)

All failures are immediate and loud. No silent fallbacks.

---

## 7. Boundaries and Interactions

- Used by `build_ghsbuilts_v1` as the sole configuration input (required argument)
- Created directly or via `from_shortcuts(source_dir=...)`
- Paths consumed by `tifffile.imread`, `pq.write_table`, and `append_ledger_entry`
- Must not depend on any other `datafactory_*` config class
- Registered via `register_builder("ghsbuilts_v1", ...)`

---

## 8. Examples of Correct Usage

```python
cfg = GhsBuiltSViewpointConfig(source_dir=Path("data/raw/ghsbuilts"))
cfg = GhsBuiltSViewpointConfig.from_shortcuts(source_dir=Path("data/raw/ghsbuilts"))
cfg = GhsBuiltSViewpointConfig(
    source_dir=Path("data/raw/ghsbuilts"),
    epochs=(2020, 2025),
    version="ghsbuilts_recent_v1",
)
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: empty version
GhsBuiltSViewpointConfig(
    source_dir=Path("data/raw/ghsbuilts"),
    version="",
)  # ValueError

# WRONG: empty epochs
GhsBuiltSViewpointConfig(
    source_dir=Path("data/raw/ghsbuilts"),
    epochs=(),
)  # ValueError

# WRONG: unknown epoch
GhsBuiltSViewpointConfig(
    source_dir=Path("data/raw/ghsbuilts"),
    epochs=(1999,),
)  # ValueError

# WRONG: invalid interpolation
GhsBuiltSViewpointConfig(
    source_dir=Path("data/raw/ghsbuilts"),
    temporal_interpolation="cubic",
)  # ValueError

# WRONG: mutating frozen config
cfg = GhsBuiltSViewpointConfig(source_dir=Path("data/raw/ghsbuilts"))
cfg.version = "new"  # AttributeError
```

---

## 10. Test Alignment

- **Green:** Default construction, frozen enforcement, custom epochs, full end-to-end flow, schema validation, provenance recording, builder registry, PGID mapping, month_id correctness
- **Beige:** Empty epochs rejection, unknown epoch rejection, invalid temporal interpolation rejection, all-zero raster (0 is valid — no built-up)
- **Red:** Missing source directory, missing epoch file, empty version rejection

Tests in `tests/test_ghsbuilts_viewpoint.py`.

---

## 11. Evolution Notes

- `temporal_interpolation` is validated against `VALID_TEMPORAL_INTERPOLATIONS` (`"step"`, `"linear"`). `aggregation` remains unvalidated — only `"sum"` is implemented.
- Default temporal interpolation is `"linear"` — linear interpolation between epochs with flat extrapolation beyond the last epoch.
- No `nodata` field — unlike GHS-POP (which uses `-200.0`), GHS-BUILT-S pixel values are uint32 where 0 means "no built-up surface," not missing data.
- If JRC publishes R2024A, a new version tag and potentially new epochs would be needed. The config supports this without structural changes.
- Consolidation layer is currently skipped (ADR-034). If a second release requires consolidation, `source_dir` would change from harvest output to consolidated store.

---

## End of Contract

This document defines the **intended meaning** of `GhsBuiltSViewpointConfig`.

Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
