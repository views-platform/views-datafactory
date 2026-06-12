
# ADR-042: SHDI Viewpoint Preserves NaN — Imputation Is a Consumer Concern

**Status:** Accepted
**Date:** 2026-06-12
**Deciders:** Simon Polichinel von der Maase, Claude Code
**Applies:** ADR-014 (Viewpoints as Derived Views), ADR-036 (SHDI Source Selection), ADR-040 (Count Conservation / Intensive Quantities), ADR-011 (Fail-Loud)

---

## Context

The SHDI visual audit (June 2026) quantified the missingness structure of SHDI data in the assembled grid:

| Category | Cells | % of land | Rubin class | Cause |
|----------|-------|-----------|-------------|-------|
| Never covered | 6,546 | 10.1% | MNAR | GDL has no subnational region defined |
| Intermittent gaps | 7,486 | 11.5% | MAR | GDL expanded over time (1990 → 2023) |
| 2009 reporting gap | 205 | 0.3% | MCAR | Single-year GDL reporting artifact |

Of the 6,546 never-covered cells, 946 fall in the Africa+ME forecast region.

The question: should the SHDI viewpoint builder fill these NaN cells, or preserve them?

### The missingness mechanism matters

The 6,546 never-covered cells are **MNAR** (missing not at random, per Rubin 1976). GDL lacks subnational regions in areas where statistical infrastructure is weakest — which correlates with low human development, which is what SHDI measures. The probability of observing the data depends on the unobserved value itself.

This means any imputation method that assumes MAR (missing at random) will produce biased estimates. Spatial neighbor fill and national-level fallback both assume MAR implicitly. In a conflict forecasting context, this bias direction is the worst possible: systematically overestimating development in the areas where underdevelopment is a conflict driver.

### Four imputation approaches were evaluated

| Approach | What it fills | Mechanism assumption | Verdict |
|----------|---------------|---------------------|---------|
| B1: Temporal forward-fill | Intermittent + 2009 gaps | MAR/MCAR (correct for these) | Defensible but low ROI |
| B2: Spatial neighbor fill | All including never-covered | MAR (incorrect for MNAR cells) | Rejected — invents data at political boundaries |
| B3: National-level fallback | Never-covered cells | MAR (incorrect) | Rejected — regression to mean, destroys subnational signal |
| B4: Linear interpolation | Single-year gaps only | MCAR (correct for 2009) | Defensible for 205 cells; poor cost/benefit |

### Architectural constraints

- ADR-014: "A viewpoint must not contain information that is absent from the consolidated store."
- ADR-011: Silent data fabrication is worse than explicit NaN.
- ADR-012: No cross-source dependencies — the SHDI viewpoint must not read other sources.
- ADR-040: SHDI is an intensive quantity; sums are meaningless but spatial averaging is mathematically valid.
- All other viewpoints (UCDP, ACLED, V-Dem, GHS-POP, GHS-BUILT-S) preserve NaN.

---

## Decision

**The SHDI viewpoint builder preserves NaN.** Missing cells are not filled, interpolated, or imputed at the viewpoint, compilation, or assembly layer. NaN means "GDL has no data for this cell-month."

Imputation is a consumer concern. Downstream models that need complete SHDI data must implement their own imputation strategy and propagate the imputation uncertainty through their analyses.

---

## Rationale

### 1. The primary missingness is MNAR

The 6,546 never-covered cells are missing because GDL lacks measurement infrastructure — which correlates with the value being measured. No imputation method available at the viewpoint layer can safely handle MNAR data. The only methodologically sound treatment is within a model that explicitly models the missingness mechanism (Rubin, 1976; Little & Rubin, 2019).

### 2. Single imputation is methodologically wrong

All evaluated approaches produce single-imputed values with no uncertainty quantification. A consumer who receives a filled value cannot distinguish it from an observed value (even with provenance flags, the filled value has no error bar). This makes downstream confidence intervals too narrow and coefficient estimates potentially biased (Harrell, 2015; Gelman et al., 2013).

### 3. The architectural contract forbids it

ADR-014 states: "A viewpoint must not contain information that is absent from the consolidated store." Imputed values are, by definition, absent from the source. Introducing imputation at the viewpoint layer would violate this constitutional principle and set a precedent that erodes the factory's honesty contract.

### 4. The practical cost of NaN is low

- 946 never-covered cells in Africa+ME = 1.5% of the forecast region
- Modern ML models handle NaN natively (XGBoost, masked neural networks)
- Panel data models can simply exclude SHDI features for missing cells
- Coverage grew from 78.7% (1990) to 89.9% (2023) — the trend is toward completeness

### 5. Consistency across viewpoints

All six viewpoints in the factory preserve NaN. A uniform contract ("NaN = source has no data") is more valuable than per-source imputation strategies with different assumptions.

---

## Considered Alternatives

### Alternative B1: Temporal forward-fill for intermittent gaps

- **Pros:** Methodologically defensible for the MAR/MCAR gaps (7,486 + 205 cells). HDI changes slowly; LOCF is standard practice.
- **Cons:** Does not help the 6,546 never-covered cells (the largest gap). Adds viewpoint builder complexity, provenance tracking, and testing burden for a marginal coverage improvement. Breaks the uniform "no imputation" contract.
- **Reason for rejection:** The intermittent gaps are predominantly early-period (3,859 cells missing only 1990–1992). Coverage is already 89.9% by 2023. The engineering cost exceeds the benefit.

### Alternative B2: Spatial neighbor fill

- **Pros:** Fills all cells including never-covered. SHDI is intensive (ADR-040), so spatial averaging is mathematically valid.
- **Cons:** Assumes spatial autocorrelation, which breaks at political boundaries — exactly where GDL regions end. Invents data for cells where GDL has never measured. Incorrect mechanism assumption (assumes MAR for MNAR data).
- **Reason for rejection:** Systematic bias in the wrong direction for conflict forecasting.

### Alternative B3: National-level HDI fallback

- **Pros:** Uses data from the same source (GDL publishes national HDI). Respects the no-cross-source constraint.
- **Cons:** National HDI is the *mean* of subnational values. Assigning it to unmapped cells creates regression-to-the-mean bias, destroying the subnational variance that is SHDI's purpose. Causally circular: the fill value is a function of the quantity being filled.
- **Reason for rejection:** Defeats the purpose of using a subnational indicator.

### Alternative B4: Linear temporal interpolation

- **Pros:** Uncontroversial for the 205-cell 2009 gap (MCAR, values on both sides).
- **Cons:** Covers only 0.3% of land cells. Building and testing interpolation infrastructure for this narrow case is poor cost/benefit.
- **Reason for rejection:** Insufficient ROI.

---

## Consequences

### Positive

- Viewpoint contract remains clean: NaN = "source has no data"
- No methodological assumptions embedded in the data layer
- Consistent with all other viewpoints
- No additional provenance complexity
- Consumer models retain freedom to handle missingness appropriately for their use case

### Negative

- 946 cells in Africa+ME forecast region have no SHDI features
- Consumers must handle NaN themselves (masking, exclusion, or model-level imputation)
- If a future consumer naively treats NaN as zero, they'll get incorrect results (but this is a consumer bug, not a factory deficiency)

### Risk: uninformed consumer imputation

A downstream model team that fills SHDI NaN without understanding the MNAR mechanism will produce biased forecasts. The missingness structure and mechanism classification documented in this ADR must be communicated to consumers. The CIC for ShdiViewpointConfig has been updated accordingly.

---

## Missingness Structure Reference

For consumers who need to implement their own imputation:

| Category | Cell count | Years affected | Mechanism | Recommendation |
|----------|-----------|----------------|-----------|----------------|
| Never covered | 6,546 (946 in Africa+ME) | All (1990–2023) | MNAR | Model the missingness mechanism jointly with the prediction model. Do NOT use spatial neighbors or national averages without uncertainty propagation. |
| Intermittent — early period | 3,859 | 1990–1992 only | MAR (time) | Backward-fill from 1993 is defensible. HDI changes slowly at annual resolution. |
| Intermittent — other | 3,627 | Various | MAR (time) | LOCF or linear interpolation within observed periods. |
| 2009 reporting gap | 205 | 2009 only | MCAR | Linear interpolation between 2008 and 2010 is uncontroversial. |

---

## References

- Rubin, D.B. (1976). "Inference and Missing Data." *Biometrika* 63(3): 581–592. — MCAR/MAR/MNAR taxonomy.
- Little, R.J.A. & Rubin, D.B. (2019). *Statistical Analysis with Missing Data.* 3rd ed., Wiley. — Canonical textbook on missing data methodology.
- Harrell, F.E. (2015). *Regression Modeling Strategies.* 2nd ed., Springer. §3.8 on single vs multiple imputation.
- Gelman, A., Carlin, J.B., Stern, H.S., Dunson, D.B., Vehtari, A., & Rubin, D.B. (2013). *Bayesian Data Analysis.* 3rd ed., CRC Press. Ch.18 on missing data.
- Kleppmann, M. & Riccomini, C. (2026). *Designing Data-Intensive Applications.* 2nd ed., O'Reilly. Ch.12 on derived data and materialized views.
- ADR-014: Viewpoints as Derived Views
- ADR-036: GDL SHDI as First Admin-1 Socioeconomic Source
- ADR-040: Count Conservation and Hierarchical Reconciliation (intensive quantity classification)
- ADR-011: Fail-Loud, No Stale Data Serving
