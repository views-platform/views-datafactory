# V-Dem

| Field | Value |
|-------|-------|
| Provider | V-Dem Institute, University of Gothenburg |
| Product | V-Dem Country-Year Dataset v16 |
| URL | https://www.v-dem.net/ |
| DOI | 10.23696/vdemds16 |
| License | CC-BY-SA 4.0 |
| Citation | Coppedge, Michael et al. (2026). V-Dem Dataset v16. Varieties of Democracy (V-Dem) Project. https://doi.org/10.23696/vdemds16 |
| Codebook | https://www.v-dem.net/documents/38/V-Dem_Codebook_v16.pdf |
| Native format | CSV (inside ZIP) |
| Native resolution | Country-year |
| Spatial extent | Global (202 countries) |
| Temporal coverage | 1789–2025 (grid uses 1980–2025) |
| Temporal granularity | Annual |
| Update cadence | Annual (typically March) |
| Access method | Direct download (no authentication) |
| Authentication | None |
| Features produced | `vdem_v2xcl_dmove`, `vdem_v2xeg_eqdr`, `vdem_v2xpe_exlsocgr`, `vdem_v2x_clphy`, `vdem_v2xcl_prpty`, `vdem_v2x_ex_military`, `vdem_v2x_ex_party`, `vdem_v2x_horacc`, `vdem_v2xnp_client`, `vdem_v2xnp_regcorr`, `vdem_v2xpe_exlgeo`, `vdem_v2x_veracc`, `vdem_v2xpe_exlpol`, `vdem_v2x_diagacc`, `vdem_v2x_divparctrl`, `vdem_v2xeg_eqprotec`, `vdem_v2x_genpp`, `vdem_v2xpe_exlgender`, `vdem_v2x_hosabort`, `vdem_v2x_libdem`, `vdem_v2xcl_rol`, `vdem_v2x_accountability` |
| Grid layers | Harvest → Viewpoint → Compilation → Assembly |
| Selection ADR | [ADR-035](../ADRs/035_vdem_as_democracy_source.md) |
| Provenance ledger | `provenance/vdem/ingestion_ledger.jsonl` |

## Description

V-Dem (Varieties of Democracy) is the standard academic dataset for measuring democracy and institutional characteristics across countries and time. Version 16 covers 202 countries from 1789 to 2025, with 531 indicators. The 22 variables selected for the data factory were chosen by cross-referencing V-Dem codebook variables against actual usage in 28/29 production models.

V-Dem is country-year data — every cell in a country gets the same value for each time step. This is not a limitation; it is what the data says.

## Pipeline path

**Harvest → Viewpoint → Compilation → Assembly.** Consolidation is skipped (single annual release).

- **Harvest:** Downloads V-Dem CSV (ZIP) from the V-Dem distribution. Filters to 22 variables + country/year identifiers. Stores as Parquet.
- **Viewpoint:** Reads GAUL `iso3_code.parquet` for ISO3→pgid crosswalk. Expands annual values to 12 monthly rows (step function: constant within year). Outputs (pgid, month_id, variables) Parquet.
- **Compilation:** Places (pgid, month_id, value) data onto [T, H, W, C] grid via `compile_pregridded`.
- **Assembly:** Combined with UCDP, ACLED, GHS-POP, GHS-BUILT-S, PRIO-GRID static, and GAUL admin into the final grid.

## Known limitations

- **Country-level granularity.** All grid cells in a country share the same V-Dem value. No subnational variation.
- **Annual step function.** Values are constant across all 12 months within a year. No sub-annual variation exists in the source data.
- **ISO3 crosswalk gaps.** Some V-Dem countries may not map to GAUL ISO3 codes (e.g., historical states, disputed territories). These are logged as warnings.
- **Version coupling.** Tied to V-Dem v16. When v17 is released, the harvester URL and potentially variable names may need updating.
