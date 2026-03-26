# R&D Roadmap: WID (World Inequality Database)

**Date:** 2026-03-26
**Status:** Investigation
**Priority:** Medium (high research value, hard integration decisions)

---

## 1. What is WID?

The World Inequality Database is the authoritative source for global
inequality data. It provides distributional national accounts — how
income and wealth are distributed within and between countries over
time.

It's maintained by an international academic consortium (the World
Inequality Lab, founded by Thomas Piketty and colleagues). The data
combines tax records, surveys, and national accounts to produce
consistent inequality metrics across 190+ countries.

In plain terms: WID answers "who gets what?" — how income and wealth
are distributed, how that's changed, and how countries compare.

---

## 2. Why does VIEWS need it?

Inequality is one of the most theorized drivers of conflict:

- **Horizontal inequality** (between groups) is associated with
  civil war onset. WID's income distribution data provides the
  country-level context.
- **Vertical inequality** (between rich and poor within a society)
  may affect both conflict risk and conflict type (e.g., one-sided
  violence vs protests).
- **Trend matters as much as level.** Rapidly increasing inequality
  may be more destabilizing than stable inequality at any level.
- **Interaction with governance.** Inequality + weak institutions
  (V-Dem) may be more conflict-prone than inequality + strong
  institutions. WID + V-Dem together enable this analysis.

**Important caveat:** WID is country-level. Inequality within a
country varies enormously by region. Broadcasting national Gini
coefficients to all cells in a country is a strong assumption.
This must be acknowledged and documented, not hidden.

---

## 3. What data is available?

- **Income indicators:** Pre-tax/post-tax income, labour income,
  capital income, wages, pensions
- **Wealth indicators:** Personal wealth, financial assets, housing,
  business assets, government wealth
- **Distribution metrics:** Gini coefficients, top percentile shares
  (top 1%, 0.1%, 0.01%), bottom 50% share, middle 40% share
- **Macro aggregates:** GDP, national income, consumption
- **Coverage:** 190+ countries, varying historical depth
  (rich countries: 1900+, developing: 1980+)
- **Resolution:** Country-year (some indicators have longer intervals)
- **Variable codes:** Standardized 5-letter codes (e.g., `sptinc` for
  pre-tax income share of top percentile)
- **Format:** CSV/Excel downloads, structured web interface
- **Size:** Varies by indicator selection (typically 10-50 MB)

---

## 4. How is it accessed?

- **Completely free.** No registration, no API key.
- **Web interface:** wid.world — interactive data explorer with
  country/indicator/year selection
- **Bulk download:** CSV exports from the data portal
- **Programmatic access:** AJAX endpoints for structured queries
  (not a formal API, but workable)
- **R package:** `wid` — convenient for exploration
- **Update frequency:** Irregular (new countries/years added
  periodically, not on a fixed schedule)

---

## 5. Research questions this enables

### RQ-9: Does inequality predict conflict at the subnational level?

This is the big question — and the honest answer is "we can't
directly test this with WID data alone" because WID is national.
But we can test:

- Does national inequality (Gini, top 1% share) correlate with
  national conflict levels (UCDP fatalities)?
- Does the *change* in inequality predict conflict onset?
- Does inequality interact with governance (V-Dem) to predict
  conflict? (High inequality + weak institutions = higher risk?)

### RQ-11: Can inequality trends serve as slow-moving risk indicators?

Inequality changes slowly (years to decades). It may function as a
"background risk level" that modulates the probability of conflict
given a triggering event. This would be valuable for VIEWS's
structural risk assessment.

---

## 6. Open questions

1. **The broadcasting problem.** National Gini coefficients are
   uniform within a country when broadcast to cells. This is the
   single largest challenge. It's not a technical problem — it's a
   research assumption. We must document it clearly and consider
   whether subnational inequality proxies exist (they don't in WID,
   but DHS surveys or nightlights might approximate).

2. **Indicator selection.** WID has hundreds of indicators at
   different distribution points (top 1%, top 10%, bottom 50%).
   Which are most relevant for conflict research? Literature
   suggests: Gini coefficient, top 10% income share, bottom 50%
   income share. Start there.

3. **Temporal coverage gaps.** Developing countries (where most
   conflict occurs) have sparser WID data. Fill strategy: last
   known value carried forward? Interpolation? Missing = missing?

4. **GDP vs inequality.** WID includes GDP (a level indicator) and
   inequality (a distribution indicator). Both matter for conflict.
   Include both? GDP is also available from World Bank with better
   coverage — should we use WID GDP or World Bank GDP?

5. **Consistency across countries.** WID harmonizes data, but
   underlying sources (tax records vs surveys) differ by country.
   Is the Gini coefficient truly comparable between Sweden (tax
   records) and Somalia (surveys with limited coverage)?

---

## 7. Integration phases

### Phase W1: Investigation (no code)
- Download sample WID data for 20 countries
- Explore: coverage, gaps, indicator quality
- Select initial indicators (3-5)
- Map WID country identifiers to GAUL codes
- Review literature on inequality and conflict
- **Key output:** Honest assessment of whether broadcasting is
  defensible for conflict research

### Phase W2: Harvester
- `src/datafactory_harvester/sources/wid.py`
- `WidConfig` dataclass (indicators, countries, date range)
- Download CSV or query AJAX endpoints
- Write per-indicator Parquet files
- Provenance ledger entry

### Phase W3: Broadcast (shared with V-Dem)
- Reuse the country-to-cell broadcast infrastructure from V-Dem
- Same GAUL-based mapping
- Same annual-to-monthly expansion
- WID-specific: handle missing years (carry forward or interpolate)

### Phase W4: Assembly Integration
- Add WID indicators to assembled grid
- Update feature metadata
- Update zarr export

### Phase W5: Research and Validation
- Cross-tabulate inequality with conflict (RQ-9)
- Test interaction with V-Dem governance indicators
- Document broadcasting assumption and its limitations

---

## 8. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Broadcasting assumption criticized | High | Medium | Document explicitly; offer country-level analysis as alternative |
| Coverage gaps in conflict-affected countries | High | Medium | Last-known-value imputation; document gaps |
| Indicator comparability across countries | Medium | Medium | Use WID's harmonized series; note methodology differences |
| Research value uncertain until tested | Medium | Medium | Start with 3 indicators; expand if predictive |
| Overlapping indicators with other sources | Low | Low | Document what WID provides that others don't |
| AJAX endpoints unstable (not a formal API) | Medium | Low | Fall back to manual CSV download if endpoints change |
