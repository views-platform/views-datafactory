# R&D Roadmap — WDI (World Development Indicators) Integration

**Date:** 2026-06-20
**Status:** Planning. Prerequisites remain before implementation.

---

## Why WDI

51% of production models (45 of 88 in views-models) already consume WDI features
via VIEWSER's `country_year` level-of-analysis. WDI is the most heavily demanded
unintegrated source. It shares the same structural profile as V-Dem (country ×
year, broadcast to PRIO-GRID via GAUL) — the integration pattern is proven.

18 models share a common `_add_wdi()` helper with 13 core indicators. The
remaining 27 models compose custom subsets from a wider pool. In total, 27
unique WDI indicators are used across the fleet.

All 27 codes have been verified against the World Bank API (2026-06-20). The
mapping from views-models names to WDI API codes is mechanical:
`wdi_ny_gdp_mktp_kd` → `NY.GDP.MKTP.KD` (lowercase, underscores → dots, drop
`wdi_` prefix).

---

## The 27 Indicators

### Economy (4)

| views-models name | WDI code | Indicator | Models |
|---|---|---|---|
| `wdi_ny_gdp_mktp_kd` | `NY.GDP.MKTP.KD` | GDP (constant 2015 US$) | core 13 + custom |
| `wdi_ny_gdp_pcap_kd` | `NY.GDP.PCAP.KD` | GDP per capita (constant 2015 US$) | custom |
| `wdi_nv_agr_totl_kn` | `NV.AGR.TOTL.KN` | Agriculture value added (constant LCU) | core 13 + custom |
| `wdi_nv_agr_totl_kd` | `NV.AGR.TOTL.KD` | Agriculture value added (constant 2015 US$) | custom |

### Military & Aid (3)

| views-models name | WDI code | Indicator | Models |
|---|---|---|---|
| `wdi_ms_mil_xpnd_gd_zs` | `MS.MIL.XPND.GD.ZS` | Military expenditure (% of GDP) | core 13 + custom |
| `wdi_ms_mil_xpnd_zs` | `MS.MIL.XPND.ZS` | Military expenditure (% of gov't expenditure) | custom |
| `wdi_dt_oda_odat_pc_zs` | `DT.ODA.ODAT.PC.ZS` | Net ODA received per capita (current US$) | core 13 + custom |

### Demographics (7)

| views-models name | WDI code | Indicator | Models |
|---|---|---|---|
| `wdi_sp_pop_totl` | `SP.POP.TOTL` | Population, total | custom |
| `wdi_sp_pop_grow` | `SP.POP.GROW` | Population growth (annual %) | core 13 + custom |
| `wdi_sp_urb_totl_in_zs` | `SP.URB.TOTL.IN.ZS` | Urban population (% of total) | core 13 + custom |
| `wdi_sp_pop_0014_fe_zs` | `SP.POP.0014.FE.ZS` | Population ages 0-14, female (% of female pop) | custom |
| `wdi_sp_pop_1564_fe_zs` | `SP.POP.1564.FE.ZS` | Population ages 15-64, female (% of female pop) | custom |
| `wdi_sp_pop_65up_fe_zs` | `SP.POP.65UP.FE.ZS` | Population ages 65+, female (% of female pop) | custom |
| `wdi_sp_dyn_le00_in` | `SP.DYN.LE00.IN` | Life expectancy at birth, total (years) | custom |

### Migration & Refugees (3)

| views-models name | WDI code | Indicator | Models |
|---|---|---|---|
| `wdi_sm_pop_netm` | `SM.POP.NETM` | Net migration | core 13 + custom |
| `wdi_sm_pop_refg_or` | `SM.POP.REFG.OR` | Refugee population by country of origin | core 13 + custom |
| `wdi_sm_pop_totl_zs` | `SM.POP.TOTL.ZS` | International migrant stock (% of pop) | custom |

### Education (3)

| views-models name | WDI code | Indicator | Models |
|---|---|---|---|
| `wdi_se_enr_prim_fm_zs` | `SE.ENR.PRIM.FM.ZS` | School enrollment, primary (gross), GPI | core 13 + custom |
| `wdi_se_enr_prsc_fm_zs` | `SE.ENR.PRSC.FM.ZS` | School enrollment, primary+secondary (gross), GPI | custom |
| `wdi_se_prm_nenr` | `SE.PRM.NENR` | School enrollment, primary (% net) | custom |

### Health & Mortality (5)

| views-models name | WDI code | Indicator | Models |
|---|---|---|---|
| `wdi_sp_dyn_imrt_in` | `SP.DYN.IMRT.IN` | Mortality rate, infant (per 1,000 live births) | custom |
| `wdi_sp_dyn_imrt_fe_in` | `SP.DYN.IMRT.FE.IN` | Mortality rate, infant, female (per 1,000) | core 13 + custom |
| `wdi_sh_dyn_mort_fe` | `SH.DYN.MORT.FE` | Mortality rate, under-5, female (per 1,000) | custom |
| `wdi_sh_sta_maln_zs` | `SH.STA.MALN.ZS` | Prevalence of underweight (% children under 5) | core 13 + custom |
| `wdi_sh_sta_stnt_zs` | `SH.STA.STNT.ZS` | Prevalence of stunting (% children under 5) | core 13 + custom |

### Labor & Land (2)

| views-models name | WDI code | Indicator | Models |
|---|---|---|---|
| `wdi_sl_tlf_totl_fe_zs` | `SL.TLF.TOTL.FE.ZS` | Labor force, female (% of total) | core 13 + custom |
| `wdi_ag_lnd_frst_k2` | `AG.LND.FRST.K2` | Forest area (sq. km) | custom |

---

## Data Model

- **Source:** World Bank API v2 (public, no authentication required)
- **Format:** JSON, paginated
- **Resolution:** country × year
- **Endpoint pattern:** `api.worldbank.org/v2/country/all/indicator/{CODE}?format=json&per_page=500&date=1960:2024`
- **Country codes:** ISO 3166-1 alpha-3 (must map to GAUL via crosswalk)
- **Coverage:** Varies by indicator — some from 1960, others from 1990+.
  Conflict-affected countries (our forecast region) often have the spottiest
  coverage. A coverage audit for Africa+ME is a Phase 0 task.
- **All intensive quantities** — ratios, percentages, indices, per-capita
  measures (except `SP.POP.TOTL`, `SM.POP.NETM`, `SM.POP.REFG.OR`,
  `NV.AGR.TOTL.KN/KD`, `AG.LND.FRST.K2`, `NY.GDP.MKTP.KD` which are
  extensive). The intensive/extensive distinction matters for spatial
  disaggregation (ADR-040): intensive values broadcast unchanged to all cells
  in a country; extensive values would need disaggregation — but all extensive
  WDI indicators are country-level aggregates that consumers interpret at
  country level, so broadcasting the country total is the correct semantic.

---

## Architecture

- **Path:** Harvest → Viewpoint → Compilation → Assembly (no Consolidation —
  single-release reference data; same skip as V-Dem, GHS-POP, GHS-BUILT-S per
  ADR-029/034/035/036)
- **Spatial disaggregation:** Country-level values broadcast to all PRIO-GRID
  cells within that country, using GAUL admin boundaries (ADR-025, ADR-044).
  Same pattern as V-Dem.
- **Temporal alignment:** Annual data broadcast to all 12 months within each
  year. Same pattern as V-Dem.
- **Feature count:** 27 indicators → 27 grid channels
- **Grid impact:** Current grid is `[T, H, W, 79]`; WDI adds 27 →
  `[T, H, W, 106]`. This is a ~34% increase in the feature dimension.

---

## Prerequisites

These must be resolved before WDI integration begins:

1. **dev↔main sync** — development is 12 commits ahead of main. Merge before
   starting new source work.

2. **Open readiness gate stories** — Stories 4 (#211: GAUL data integrity) and
   5 (#212: DGP validation) from the readiness gate sprint are still
   pending/in-progress. Story 6 (#213: register update for 10 resolved
   concerns) also pending.

3. **ISO→GAUL country crosswalk** — WDI uses ISO 3166-1 alpha-3 country codes;
   our spatial infrastructure uses GAUL codes. Need a mapping table. GAUL's own
   metadata includes ISO codes — this may already be extractable from our
   existing GAUL shapefiles.

4. **C-223: Compilation memory** (Tier 3) — Adding 27 features pushes
   single-source compilation past current memory budget. Solution (memmap via
   `np.lib.format.open_memmap`) is researched
   (`rd_plan_bounded_memory_compilation.md`) but not yet implemented. Must land
   before or during WDI compilation phase.

5. **C-164: WET-before-DRY** (Tier 3, trigger fired) — With 9 sources
   integrated, shared patterns across harvest/viewpoint/compilation layers are
   proven. Sequencing decision: extract shared utilities *before* WDI (so WDI
   is the first consumer of extracted code) or *after* (WDI as one more WET
   instance, then extract from 10). Either is viable.

---

## Integration Phases

Follows `docs/guides/data_source_integration_guide.md`:

| Phase | Deliverable | Effort | Depends on |
|-------|-------------|--------|------------|
| **WDI-0: Investigation** | API spike: coverage audit for all 27 indicators in Africa+ME, missingness patterns, temporal extent | 1 day | Nothing |
| **WDI-1: ADR** | ADR-0XX: WDI as economic/development source (modeled on ADR-035 V-Dem) | 0.5 day | WDI-0 |
| **WDI-2: Harvester** | `src/datafactory_harvester/sources/wdi.py` — fetch 27 indicators, paginate, ISO country codes | 1 day | WDI-1, ISO→GAUL crosswalk |
| **WDI-3: Viewpoint** | `src/datafactory_viewpoint/builders/wdi_v1.py` — country-to-grid broadcast via GAUL (V-Dem pattern) | 1 day | WDI-2 |
| **WDI-4: Compilation** | `scripts/compile_wdi.py` — 27 features placed on grid, temporal alignment | 0.5 day | WDI-3, C-223 resolved |
| **WDI-5: Assembly** | Wire into `scripts/assemble_grid.py`, update `source_registry.py`, feature_names, provenance | 0.5 day | WDI-4 |
| **WDI-6: Verification** | Visual audit script, consumer parity check against VIEWSER, statistical spot-checks | 0.5 day | WDI-5 |
| **WDI-7: Deployment** | Server pipeline run, remote verification, version bump | 0.5 day | WDI-6 |

**Total: ~5–6 days** once prerequisites are cleared.

---

## Risk Register Entries

Existing concerns relevant to WDI:

| Concern | Tier | Title | WDI relevance |
|---------|------|-------|---------------|
| C-223 | 3 | Compilation allocates full grid in RAM | 27 new features push compile past 16 GB |
| C-164 | 3 | Cross-layer WET debt (trigger fired) | Sequencing decision: extract before or after WDI |
| C-29 | 4 | No end-to-end integration test | Trigger: before 10th source |
| C-155 | 4 | No shared visual audit framework | Trigger: before 6th pipeline source |
| C-173 | 4 | Hetzner memory headroom | Observed during WDI pilot |

---

## Open Questions

1. **Indicator scope:** Harvest all 27, or start with the core 13 from
   `_add_wdi`? The 13-indicator core covers the highest-demand features. The
   remaining 14 are used by individual models with custom configs. Harvesting
   all 27 is cheap (same API, same pattern) — the cost is in grid size, not
   development effort.

2. **Missing data strategy:** Forward-fill? Leave NaN? Same design question as
   SHDI (ADR decision pending from expert method review). WDI missingness is
   likely worse than SHDI in conflict-affected countries — the Phase 0 coverage
   audit will quantify this.

3. **Consumer bridge:** `scripts/generate_consumer_data.py` currently exports a
   fixed set of features with `wdi_` → `lr_wdi_` renaming. Will need to be
   updated to include WDI features once integrated.

4. **Overlap with existing sources:** Some WDI indicators overlap conceptually
   with existing sources:
   - `SP.POP.TOTL` (population) overlaps with GHS-POP (but at country vs. grid
     resolution)
   - `AG.LND.FRST.K2` (forest area) overlaps with PRIO-GRID static
     `forest_gc` (but WDI is country-level, static is cell-level)

   These are not conflicts — different resolutions serve different modeling
   needs — but worth documenting in the ADR.

---

## References

- World Bank API documentation: `api.worldbank.org/v2`
- ADR-035: V-Dem integration (the pattern WDI follows)
- ADR-044: Source taxonomy (WDI is a country-level reference source)
- ADR-040: Count conservation (intensive/extensive distinction)
- `docs/guides/data_source_integration_guide.md`: the integration checklist
- `rd_plan_bounded_memory_compilation.md`: memmap solution for C-223
