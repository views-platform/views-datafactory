# R&D Roadmap: V-Dem (Varieties of Democracy)

**Date:** 2026-03-26
**Status:** Investigation
**Priority:** High (easiest integration, high research value)

---

## 1. What is V-Dem?

V-Dem is the world's most comprehensive democracy measurement project.
It produces 531 indicators and 251 indices measuring different aspects
of democracy — electoral, deliberative, participatory, egalitarian,
liberal — for every country, every year, going back to 1789.

It's produced by the V-Dem Institute at the University of Gothenburg
with 9 regional centres and thousands of country experts. Version 16
was released March 2026.

In plain terms: V-Dem answers "how democratic is this country, in what
ways, and how has that changed over time?"

---

## 2. Why does VIEWS need it?

Conflict forecasting benefits from governance context. Democracy
indicators are among the strongest predictors of both conflict onset
and conflict duration:

- **Regime type matters for conflict risk.** Autocracies and
  anocracies (partial democracies) have different conflict profiles.
- **Democratic backsliding** — deteriorating scores may signal
  increasing conflict risk before events occur.
- **Institutional strength** — rule of law, civil liberties, media
  freedom indices provide context for interpreting conflict patterns.
- **Cross-source analysis** — combining UCDP event data with V-Dem
  governance data enables questions like "does conflict increase
  during democratic transitions?"

---

## 3. What data is available?

- **531 indicators** across 5 democracy dimensions + sub-components
- **Coverage:** 202 countries, 1789-2025 (density varies by era)
- **Resolution:** Country-year (one row per country per year)
- **Key indices:**
  - `v2x_polyarchy` — Electoral Democracy Index
  - `v2x_libdem` — Liberal Democracy Index
  - `v2x_partipdem` — Participatory Democracy Index
  - `v2x_delibdem` — Deliberative Democracy Index
  - `v2x_egaldem` — Egalitarian Democracy Index
  - `v2x_rule` — Rule of Law Index
  - `v2x_corr` — Political Corruption Index
  - `v2x_civlib` — Civil Liberties Index
- **Format:** CSV, R data, Stata, SPSS
- **Size:** ~100 MB (full dataset with all indicators)
- **Codebook:** Comprehensive, 500+ pages, freely available

---

## 4. How is it accessed?

- **Completely free.** No registration, no API key, no terms to accept.
- **Download:** CSV from v-dem.net/data/the-v-dem-dataset/
- **R package:** `vdemdata` on GitHub (not needed; CSV is sufficient)
- **No API.** Bulk download only. This is fine — the dataset changes
  once per year (annual release, typically March).
- **Versioning:** Each annual release is a complete snapshot. Version
  numbers are not backward-compatible (indices are recalculated
  with updated coder data).

---

## 5. Research questions this enables

### RQ-7: Do democracy indicators predict conflict dynamics?

Can V-Dem indices (especially regime type, civil liberties, rule of
law) improve VIEWS conflict forecasts? Specifically:

- Does the Electoral Democracy Index correlate with UCDP fatality
  levels at the country level?
- Does democratic backsliding (year-over-year decline in indices)
  precede conflict onset?
- Are different democracy dimensions (liberal vs egalitarian vs
  participatory) differentially predictive?

### RQ-8: Does institutional context explain spatial conflict patterns?

Countries with similar conflict levels but different governance
profiles may have different spatial distributions of violence.
V-Dem indicators could explain why some countries concentrate
violence in specific regions while others have diffuse patterns.

---

## 6. Open questions

1. **Which indicators matter?** 531 is too many. Need a principled
   selection (literature review or dimensionality reduction).
   Start with the 5 high-level indices + rule of law + corruption.

2. **Annual-to-monthly interpolation.** V-Dem is annual; our grid is
   monthly. Options: constant within year (simplest, defensible),
   linear interpolation between years (assumes gradual change),
   or match to specific month (e.g., January = start of year).

3. **Version stability.** V-Dem recalculates historical indices with
   each release. Should we pin to a specific version or always use
   the latest? Pinning aids reproducibility; latest is more accurate.

4. **Country code mapping.** V-Dem uses its own country codes
   (`country_id`). These need to be mapped to GAUL codes for
   broadcasting to PRIO-GRID cells. The mapping may not be 1:1
   (border changes, disputed territories).

---

## 7. Integration phases

### Phase V1: Investigation (no code)
- Download V-Dem v16 CSV
- Explore: how many indicators, coverage gaps, country code scheme
- Map V-Dem country codes to GAUL codes — identify mismatches
- Select initial indicator set (5-10 indices)
- Decide interpolation strategy

### Phase V2: Harvester
- `src/datafactory_harvester/sources/vdem.py`
- `VdemConfig` frozen dataclass (version, indicator list, data_dir)
- Download CSV, parse, write per-indicator Parquet files
- Provenance ledger entry with version, indicator count, digest

### Phase V3: Country-to-Cell Broadcast Infrastructure
- Generalize the GAUL broadcast pattern from `assemble_grid.py`
- New module or extension: given (country_id, year, value) records
  and a GAUL-to-PRIO-GRID mapping, produce [T, H, W] arrays
- This infrastructure serves both V-Dem and WID

### Phase V4: Assembly Integration
- Add V-Dem indicators to the assembled grid
- Update `feature_names.json` with V-Dem indicator names
- Update zarr export to include V-Dem variables

### Phase V5: Validation and Research
- Compare country-level V-Dem values against known benchmarks
- Cross-tabulate with UCDP conflict patterns (RQ-7)
- Verify broadcasting doesn't introduce artifacts

---

## 8. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Country code mismatch (V-Dem ↔ GAUL) | High | Medium | Manual mapping table; document mismatches |
| Broadcasting hides subnational variation | Certain | Medium | Accepted — V-Dem is country-level by design |
| Version instability (recalculated history) | Medium | Low | Pin to version; re-harvest on new release |
| Indicator selection bias | Medium | Medium | Start with high-level indices; expand based on research |
| Large feature count inflates grid | Low | Low | Select 5-10 indicators, not all 531 |
