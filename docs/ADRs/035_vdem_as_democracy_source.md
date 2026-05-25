# ADR-035: V-Dem as Democracy Indicator Source

**Status:** Accepted
**Date:** 2026-05-26
**Deciders:** Simon Polichinel von der Maase, Claude Code
**Applies:** ADR-012 (Four-Layer Data Architecture), ADR-029 (skip consolidation precedent), ADR-033 (Data Source Catalog), ADR-034 (GHS-BUILT-S pattern)

---

## Context

The assembled grid now carries conflict event data (UCDP, ACLED), population (GHS-POP), built-up surface (GHS-BUILT-S), static geography (PRIO-GRID), and administrative codes (GAUL). What is missing is any measure of governance, institutional quality, or political regime — variables that 28 of 29 production models in `views-models` already consume from V-Dem via the legacy VIEWSER pipeline.

V-Dem (Varieties of Democracy) is the standard academic dataset for measuring democracy and institutional characteristics across countries and time. Version 16 (March 2026) covers 202 countries from 1789 to 2025, with 531 indicators. The dataset is released annually as a single CSV under CC-BY-SA 4.0, requires no authentication, and is available for direct download.

Cross-referencing the 531 V-Dem variables against actual `config_queryset.py` usage in production models shows that 22 raw V-Dem variables (after stripping spatial/temporal lag prefixes which are feature-engineering, not data) are consumed by 7–28 models each. These 22 variables are the minimum viable set for the data factory to serve production models.

---

## Decision

**V-Dem v16** (Varieties of Democracy, version 16) is the 7th data source for the VIEWS data factory, contributing 22 democracy indicator variables to the assembled grid (53 → 75 total features).

### Variable selection

22 variables selected by cross-referencing V-Dem codebook against production model querysets:

**Tier 1 — 12 variables (used by 25–28 models):**
`v2xcl_dmove`, `v2xeg_eqdr`, `v2xpe_exlsocgr`, `v2x_clphy`, `v2xcl_prpty`, `v2x_ex_military`, `v2x_ex_party`, `v2x_horacc`, `v2xnp_client`, `v2xnp_regcorr`, `v2xpe_exlgeo`, `v2x_veracc`

**Tier 2 — 7 variables (used by 14–20 models):**
`v2xpe_exlpol`, `v2x_diagacc`, `v2x_divparctrl`, `v2xeg_eqprotec`, `v2x_genpp`, `v2xpe_exlgender`, `v2x_hosabort`

**Tier 3 — 3 variables (used by 7–10 models):**
`v2x_libdem`, `v2xcl_rol`, `v2x_accountability`

### In scope

- Harvesting V-Dem v16 CSV from the V-Dem distribution
- Viewpoint building: country-year → country-month expansion with ISO3→GAUL crosswalk for grid broadcast
- Compilation via `compile_pregridded` to [T, H, W, C] npy arrays
- Integration into the assembled grid as 22 features (all prefixed `vdem_`)

### Out of scope

- V-Dem lower-level indicators (the ~500 remaining variables) — add via future ADR if models need them
- Temporal interpolation within years — V-Dem is annual; no sub-annual signal exists to interpolate
- Spatial disaggregation within countries — V-Dem is country-level; subnational variation is not in the source data
- Derived features (democracy indices, regime change rates, lag variables) — model-layer concern, not data store
- DemScore harmonisation platform — web-only download, no API, not suitable as a harvester target

---

## Rationale

### V-Dem is the standard source for institutional variables

V-Dem is the most widely used academic dataset for measuring democracy and governance. It is already the source behind 28/29 production models. Moving it into the data factory replaces a legacy VIEWSER dependency with a provenance-tracked, version-controlled pipeline.

### 22 variables cover production needs without overreach

The full V-Dem dataset has 531 indicators, but only 22 raw variables appear in production model querysets. Starting with this minimal set avoids grid bloat while covering all current model requirements. Additional variables can be added incrementally — each is a one-line change in the harvester config and source registry.

### Country-to-grid broadcast via GAUL crosswalk

V-Dem data is country-year. To place it on the PRIO-GRID, we use the GAUL admin boundary data already in the factory:

1. GAUL `iso3_code.parquet` maps each pgid (PRIO-GRID cell) to an ISO3 country code
2. V-Dem `country_text_id` is ISO3 alpha-3
3. Invert the GAUL mapping: ISO3 → set of pgids → broadcast country-level values to all cells

All cells in a country get the same V-Dem value. This is not a limitation — it is what the data says. V-Dem does not vary within countries.

### Annual → monthly expansion as step function

V-Dem is annual. Each year's values are constant across all 12 months (step function). No interpolation is applied — unlike GHS-POP which interpolates between five-year epochs, V-Dem changes are real annual observations, not temporal samples of a continuous process. The step function preserves the data faithfully.

### Consolidation: skipped

Same rationale as GHS-POP (ADR-029) and GHS-BUILT-S (ADR-034): V-Dem is a single annual release with nothing to merge, deduplicate, or reconcile between snapshots. When v17 arrives, a version-management strategy can be added, but for a single release there is no consolidation work to do.

### Pipeline path

Harvest → Viewpoint → Compilation → Assembly. Three layers, not four — consolidation is skipped.

---

## Consequences

### Positive

- 22 democracy/governance variables available in the grid — covers 28/29 production model needs
- Removes legacy VIEWSER dependency for V-Dem data
- Provenance-tracked: every harvest, viewpoint build, and compilation writes ledger entries
- Validates the country-level data pattern (distinct from event-level UCDP/ACLED and raster GHS-POP/GHS-BUILT-S)
- Opens path for other country-year sources (WDI, QoG) using the same crosswalk pattern

### Negative

- 22 additional features increase grid memory by ~42% (22/53 of pre-existing features)
- Country-level granularity means all cells in a country share identical values — models must account for this
- GAUL-V-Dem ISO3 mismatches will cause some countries to be unmapped (logged as warnings, not silent)
- Annual step function means V-Dem features are constant within years — models should not expect sub-annual variation

These costs are accepted. The 22 variables are already consumed by production models; the data factory must provide them.

---

## Implementation Notes

### Data characteristics

| Property | Value |
|----------|-------|
| Provider | V-Dem Institute, University of Gothenburg |
| Version | v16 (March 2026) |
| Format | CSV (inside ZIP, ~300 MB uncompressed) |
| Countries | 202 |
| Temporal coverage | 1789–2025 (grid uses 1980–2025) |
| Temporal granularity | Annual |
| Variables selected | 22 of 531 |
| License | CC-BY-SA 4.0 |
| Authentication | None |
| Country identifier | `country_text_id` (ISO3 alpha-3) |

### Feature names in assembled grid

All 22 features are prefixed `vdem_`: `vdem_v2xcl_dmove`, `vdem_v2xeg_eqdr`, etc.

### Pipeline flow

Harvest (CSV download) → Viewpoint (ISO3→pgid crosswalk + annual→monthly) → Compilation (`compile_pregridded`) → Assembly.

### Memory considerations

22 float32 features × 456 time steps × 360 × 720 = ~4.1 GB additional grid data. The Hetzner server (8 GB RAM) handles this via memory-mapped assembly (same pattern as existing sources). No OOM risk.

---

## References

- V-Dem Institute: https://www.v-dem.net/
- V-Dem v16 Codebook: https://www.v-dem.net/documents/38/V-Dem_Codebook_v16.pdf
- Coppedge, Michael et al. (2026). V-Dem Dataset v16. Varieties of Democracy (V-Dem) Project. https://doi.org/10.23696/vdemds16
- ADR-029: GHS-POP as First Population Source (skip consolidation precedent)
- ADR-033: Data Source Catalog
- ADR-034: GHS-BUILT-S as Built-Up Surface Area Source
