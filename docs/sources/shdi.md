# SHDI

| Field | Value |
|-------|-------|
| Provider | Global Data Lab (GDL), Radboud University |
| Product | Subnational Human Development Index |
| URL | https://globaldatalab.org/shdi/ |
| License | Free for academic use (registration required) |
| Citation | Smits, J., Permanyer, I. (2019). The Subnational Human Development Database. Scientific Data, 6, 190038. |
| Codebook | GDL Codes (from GDL website) |
| Native format | CSV (via GDL Data API) |
| Native resolution | Admin-1 (1,801+ GDL regions) |
| Spatial extent | Global (188 countries) |
| Temporal coverage | 1990–2023 |
| Temporal granularity | Annual |
| Update cadence | Periodic |
| Access method | GDL Data API (token auth) |
| Authentication | `GDL_API_TOKEN` env var (free account, ADR-026) |
| Shapefile source | PRIO CDN (no auth required) |
| Features produced | `shdi_shdi`, `shdi_healthindex`, `shdi_edindex`, `shdi_incindex` |
| Grid layers | Harvest → Viewpoint → Compilation → Assembly |
| Selection ADR | [ADR-036](../ADRs/036_shdi_as_subnational_hdi_source.md) |
| NaN policy ADR | [ADR-042](../ADRs/042_shdi_nan_preservation.md) |
| Provenance ledger | `provenance/shdi/ingestion_ledger.jsonl` |

## Description

SHDI (Subnational Human Development Index) is produced by the Global Data Lab at Radboud University. It provides HDI values at admin-1 resolution for 1,801+ regions across 188 countries, from 1990 to 2023. The composite index and three sub-indices (health, education, income) are all bounded [0, 1].

This is the first subnational socioeconomic source in the data factory. Unlike V-Dem (country-level), SHDI varies within countries at the admin-1 level. All grid cells within the same GDL region share the same value.

## Pipeline path

**Harvest → Viewpoint → Compilation → Assembly.** Consolidation is skipped (single periodic release).

- **Harvest:** Downloads SHDI CSV from GDL Data API and GDL shapefiles from PRIO CDN. Stores CSV as Parquet. Performs spatial join (GDL polygons → PRIO-GRID centroids) to produce `gdl_to_pgid.parquet` crosswalk.
- **Viewpoint:** Reads crosswalk for GDL-code→pgid mapping. Expands annual values to 12 monthly rows (step function: constant within year). Outputs (pgid, month_id, variables) Parquet.
- **Compilation:** Places (pgid, month_id, value) data onto [T, H, W, C] grid via `compile_pregridded`.
- **Assembly:** Combined with UCDP, ACLED, GHS-POP, GHS-BUILT-S, V-Dem, PRIO-GRID static, and GAUL admin into the final grid.

## Scale Classification

| Scale | Range | Features |
|-------|-------|----------|
| Bounded index | [0, 1] | All 4: shdi, healthindex, edindex, incindex |

## Crosswalk

GDL uses proprietary region codes (GDL-Code), not GAUL or ISO 3166-2. The crosswalk is built via direct spatial join of GDL shapefile polygons against PRIO-GRID centroids using STRtree — the same pattern as `gaul_admin.py`. Output: `data/raw/shdi/gdl_to_pgid.parquet` with schema `(gid: int32, gdl_code: string)`.

## Licensing and access

GDL terms of use (https://globaldatalab.org/termsofuse/) permit free download and use for noncommercial purposes with attribution. Commercial use requires written permission.

VIEWS is a publicly funded academic project at PRIO and Uppsala University. Our use of SHDI as an input covariate in conflict forecasting models is noncommercial — we do not redistribute GDL data, and our forecasts are freely available. However, because VIEWS also serves as an operational early warning system used by international organizations and governments, we sent a proactive permission request to GDL (Professor Jeroen Smits) on 2026-05-29 to confirm our use is within terms. Response pending as of 2026-05-29.

**API token:** Free account registered at globaldatalab.org → "My GDL" → "API Access". Token stored as `GDL_API_TOKEN` environment variable per ADR-026. The token is shown once at creation and cannot be retrieved later — keep a record. GDL limits each token to 1000 requests (our harvester uses 5 requests per run — one per indicator plus shapefile — so this is not a constraint). Note: GDL built the API for their R package (`gdldata`) and describes it as intended "for both classroom settings and research alike." We discovered it works as a plain REST endpoint by reading the R package source code.

## Coverage and missing data

SHDI coverage is incomplete. The data factory preserves NaN — no interpolation or imputation is applied (ADR-042).

| Category | Cells | % of land | Missingness mechanism |
|----------|-------|-----------|----------------------|
| Never covered | 6,546 | 10.1% | MNAR — GDL has no subnational region |
| Intermittent gaps | 7,486 | 11.5% | MAR — GDL expanded over time |
| 2009 reporting gap | 205 | 0.3% | MCAR — single-year artifact |

Coverage grew from 78.7% of land cells (1990) to 89.9% (2023). Of the 6,546 never-covered cells, 946 fall in the Africa+ME forecast region.

The primary missingness (never-covered cells) is MNAR: cells are missing because GDL lacks statistical infrastructure, which correlates with low development — the quantity being measured. Consumers who need complete SHDI data must implement their own imputation and should model the missingness mechanism. See ADR-042 for the full rationale and per-category imputation guidance.

## Known limitations

- **Admin-1 granularity.** All grid cells within a GDL region share the same SHDI value. No variation below admin-1.
- **Annual step function.** Values are constant across all 12 months within a year.
- **Temporal coverage starts 1990.** Grid cells for months before January 1990 will be NaN.
- **10.1% of land cells never covered.** See coverage table above.
- **Version coupling.** Tied to current SHDI data version and GDL shapefiles. Updates may require updating column names.
