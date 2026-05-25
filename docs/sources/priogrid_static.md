# PRIO-GRID Static

| Field | Value |
|-------|-------|
| Provider | Peace Research Institute Oslo (PRIO) |
| Product | PRIO-GRID 2.0 static features — terrain, resources, land cover |
| URL | https://grid.prio.org/ |
| DOI | 10.1177/0022343311431287 |
| License | Creative Commons Attribution 4.0 (CC-BY-4.0) |
| Citation | Tollefsen, A.F., Strand, H. & Buhaug, H. (2012). PRIO-GRID: A unified spatial data structure. Journal of Peace Research 49(2): 363–374. doi:10.1177/0022343311431287 |
| Codebook | https://grid.prio.org/extensions/codebook |
| Upstream contact | PRIO GRID team (grid@prio.org) |
| Native format | JSON (API) |
| Native CRS | WGS84 (EPSG:4326) — 0.5° × 0.5° grid cells |
| Native resolution | 0.5° × 0.5° (matching our compilation grid) |
| Spatial extent | Global land cells (64,818 cells) |
| Temporal coverage | Static (2009–2015 vintages, frozen) |
| Temporal granularity | None (time-invariant) |
| Update cadence | One-time (PRIO-GRID 2.0 is no longer updated) |
| Access method | REST API, no authentication |
| Authentication | None |
| Features produced | 34 static features (terrain elevation, slope, land cover categories, resources, etc.) |
| Grid layers | Harvest → Assembly (skips consolidation, viewpoint, compilation — already at 0.5°) |
| Selection ADR | Original source — no selection ADR (foundational spatial backbone) |
| Provenance ledger | `provenance/priogrid_static/ingestion_ledger.jsonl` |

## Description

PRIO-GRID 2.0 provides static geographic and socioeconomic variables at 0.5° × 0.5° resolution, directly matching the VIEWS compilation grid. These are time-invariant structural features — terrain elevation, slope, land cover proportions, distance to resources, and similar geographic covariates. The data is frozen (2009–2015 vintages depending on variable) and will not be updated.

Because the data is already at native PRIO-GRID resolution, it bypasses consolidation, viewpoint, and compilation layers entirely — harvested variables are stored as per-variable Parquet files with `(gid, value)` columns and assembled directly into the final grid.

## Pipeline path

**Harvest → Assembly.** Consolidation, viewpoint, and compilation are skipped — the data is already at 0.5° resolution with no versions to merge or opinions to apply.

- **Harvest:** Fetches each variable individually from the PRIO-GRID 2.0 API. Each variable stored as a separate Parquet file with columns `(gid, value)`.
- **Assembly:** Per-variable Parquet files are read and placed directly into the assembled grid alongside compiled UCDP, ACLED, GHS-POP, and GHS-BUILT-S layers.

## Known limitations

- **Frozen data.** PRIO-GRID 2.0 is no longer updated. The static features reflect conditions from 2009–2015 depending on variable. For temporal analysis, these serve as time-invariant controls, not evolving covariates.
- **Land cells only.** Only 64,818 of the 259,200 global cells contain data. Ocean cells have no static features.
- **Variable vintage variation.** Different variables may come from different base years. The codebook documents this per variable.
