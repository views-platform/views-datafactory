# 01 — Literature

**Date:** 2026-11-04 · **Source:** `/home/simon/brain/9_library` (840 papers, 3,807 claims, 99%
extraction coverage), surveyed via the `library` skill plus a keyword scan over all 840 titles.

**Method note.** Semantic search returned near-uniform scores (~0.016) on roughly half the queries —
effectively noise — so every absence claim below was re-checked against the full title list rather
than inferred from a failed search. Three apparent hits on "extremes" were false positives:
`Martin2017_CleanArch_Ch30/31/32` matched `tail` inside *de**tail**s*. Absence of a title keyword is
strong evidence, not proof, of absent content.

---

## A. What we have, and what we take from it

### A1. Evaluation when a few observations dominate — the strongest area (31 + 14 papers)

This is the literature that makes the *evaluation* half of this program tractable.

| Source | What we take from it |
|---|---|
| `Lerch2017_ForecastersDilemmaExtremeEvents` | The forecaster's dilemma by name: conditioning evaluation on extreme outcomes rewards hedging. Proper **weighted** scoring rules (twCRPS, CL, CSL) restore correct rankings. **This is the normative answer to "one cell is 98% of the slice" — but it lives downstream, not here.** |
| `Gneiting2011_ComparingDensityForecasts` | Threshold-weighted and quantile-weighted CRPS, and the **threshold decomposition** `CRPS = ∫BS(z)dz`. We take the decomposition as a *diagnostic*: it localises which part of the value range carries a score's mass. |
| `Bolin2023_LocalScaleInvarianceScoringRules` | SCRPS — locally scale-invariant. Directly addresses "the score is in count units, so magnitude buys leverage." The comparator against which any data-side remedy should be judged. |
| `Arnold2024_CRPSDecompositions` | CRPS decompositions; the vocabulary for attributing a score change to calibration vs sharpness rather than to one cell. |
| `Taillardat2023_ExtremeEventsEvaluationCRPS`, `Rudy2021_OutputWeightedExtremeLoss`, `Shi2024_BoostingExtremeEvents` | Supporting treatments of extreme-event evaluation and output-weighted losses. |
| `Gneiting2007_StrictlyProperScoringRules`, `Gneiting2007_CalibrationSharpness`, `Brocker2009_ReliabilitySufficiencyDecomposition` | Foundations. |

### A2. Point processes — the formalism that dissolves the problem (22 papers)

| Source | What we take from it |
|---|---|
| `Brehmer2023_PointProcessForecasts` | **Consistent scoring functions for a point process's intensity measure Λ.** The key idea for us: an evaluation target that does not require choosing a cell, so it is invariant to binning. The principled long-run target for the platform. |
| `Moller1998_LogGaussianCoxProcesses`, `Taylor2012_INLAMCMCLogGaussianCox`, `Choiruddin2025_DeepLearningMultivariateLGCP` | LGCP: a latent continuous intensity field with aggregate observations. The natural generative model for "a year's total over three regions". |
| `Simpson2016_GoingOffGrid` | Variable sampling effort and observation-window effects — the closest thing in the library to change-of-support. |
| `Lindgren2011_ExplicitLinkSPDE` | SPDE/Matérn: a continuous field discretisable at any support. The mechanism by which a region-level total could be allocated coherently. |
| `Browning2024_BayesianHawkesConflict`, `Lewis2011_SelfExcitingIraq`, `Reinhart2018_SelfExcitingSpatioTemporal`, `Mohler2011_SelfExcitingCrime` | Conflict- and crime-specific self-exciting processes. Relevant because self-excitation is a *testable* alternative to our proportional-weighting assumption: if conflict clusters in time, an annual total should not be spread uniformly. |

### A3. UCDP measurement error — small but exactly on point (3 papers)

| Source | What we take from it |
|---|---|
| `Vesco2026_UnderreportedDeathTollWars` + `Vesco2024_UnderreportedDeathTollPreprint` | UCDP counts are systematically **underreported, non-linearly in event size** — >100% for single-fatality events, ~30% for large ones. **Consequence for this program: the large aggregates we are worried about are the *least* underreported values in the dataset.** Any remedy that effectively discounts them trades a known allocation error for a known magnitude error. This must be stated in any pre-registration. |
| `Gibbons2014_MeasuringUnderreportingInfectiousDisease` | The surveillance-pyramid analogue, and the discipline of reporting uncertainty on multiplication factors. Methodological template for declaring what our allocation does not know. |

### A4. Conservation and reconciliation (3 papers + our own ADR-040)

`Wickramasuriya2019_OptimalForecastReconciliation`, `Panagiotelis2023_ProbabilisticForecastReconciliation`,
`Hyndman2018_OptimalReconciliation_FPP2` — optimal reconciliation of hierarchical forecasts, including
the probabilistic case. We take the **conservation-under-constraint formalism**; we do not take the
forecast-combination machinery, which solves a different problem (reconciling *predictions*, not
allocating *observations*).

### A5. Domain and system context (62 papers)

`Hegre2024_VIEWSPredictionChallenge`, `Hegre2025_PredictionChallenge`, `Hegre2019_ViEWS`,
`Hegre2020_UCDPCandidateEvents`, `Schincariol2025_AccountingForVariability`,
`Raleigh2005_IntroducingACLED`, `ZammitMangion2012_AfghanWarDiary` (nonparametric analysis of event
logs at weekly resolution), `Braun2025_LLMEventExtraction`.

---

## B. Gaps — verified absent, and what each would buy

Each line was checked against all 840 titles.

| Gap | Papers | Why it matters here |
|---|---:|---|
| **Modifiable Areal Unit Problem / ecological inference / change-of-support** | **0** | This is the *formal name* for our problem: a quantity observed on one support, required on another. We are currently reasoning about it without its vocabulary or its known failure modes. **Highest-value gap.** |
| **Temporal disaggregation / benchmarking** (Denton; Chow–Lin; Litterman) | **0** | The classical econometrics of distributing an annual total across months subject to a conserving constraint — precisely what a principled `even_split` successor would be. We would be reinventing a 1971 literature. |
| **Areal interpolation / dasymetric mapping** | ~0 | ADR-049's proportional weighting *is* dasymetric mapping with well-located fatalities as the ancillary surface. The literature knows when that fails; we do not. |
| **Coarsened-at-random / partial identification** (Heitjan & Rubin; Manski) | 3, all Tobit censored-*regression* | The framework for *declining to allocate* — carrying a set rather than a point. This underwrites the "emit a flag, let downstream widen" option. Tobit is censoring of a scalar, a different problem. |
| Influence / leverage diagnostics for *scores* | 0 | `Koh2017_InfluenceFunctions` concerns training data, not forecast scores. hydranet's effective-sample-size instrument is sound but currently unanchored in any cited method. |
| EM / latent allocation | ~0 | The estimation machinery if allocation weights were ever learned rather than assumed. |

### Gaps to fetch — the acquisition list

Citations below were **verified by web search on 2026-11-04** except where marked
⚠️ *unverified* (recalled, not checked — confirm before ordering). Checked against all 840 titles
first, so nothing here is already held.

#### Tier 1 — blocks the program; fetch before P2/P3

| # | Citation | What it buys |
|---|---|---|
| 1 | **Gotway & Young (2002)**, "Combining Incompatible Spatial Data", *JASA* 97(458):632–648, doi:10.1198/016214502760047140 | The change-of-support review. Its own keyword list is *change of support · ecological inference · modifiable areal unit problem · spatially-misaligned data* — i.e. our entire top gap in one paper. Gives the observed-support × inference-support typology that classifies what we are doing. |
| 2 | **Tobler (1979)**, "Smooth Pycnophylactic Interpolation for Geographical Regions", *JASA* 74(367):519–530, doi:10.1080/01621459.1979.10481647 | **Mass-preserving** areal interpolation — "pycnophylactic" *means* the zone total is preserved. This is ADR-040 Invariant 1 expressed as an interpolation method, and the principled relative of ADR-049's proportional weighting. R implementation exists (`pycno`). |
| 3 | **Denton (1971)**, "Adjustment of Monthly or Quarterly Series to Annual Totals: An Approach Based on Quadratic Minimization", *JASA* 66:99–102 | The conserving temporal allocation, by quadratic minimisation subject to the annual total. **This is option O2 done properly**; `even_split` is a crude member of this family. |
| 4 | **Chow & Lin (1971)**, "Best Linear Unbiased Interpolation, Distribution, and Extrapolation of Time Series by Related Series", *Rev. Econ. Stat.*:372–375 | Covariate-informed temporal allocation (BLUE). The temporal analogue of ADR-049's spatial weighting — distribute a total using a correlated indicator series. |
| 5 | **Heitjan & Rubin (1991)**, "Ignorability and Coarse Data", *Ann. Statist.* 19(4):2244–2253, doi:10.1214/aos/1176348396 — **open access** (Project Euclid) | The formal framework for **O3**. A general model of *coarsening* covering "rounded, heaped, censored, partially categorized and missing data" — our case named exactly — and defines **coarsening at random (CAR)**, the condition under which the coarsening mechanism may be ignored. Tells us when declaring the coarsening is sufficient and when it is not. |
| 6 | **Weidmann (2015)**, "On the Accuracy of Media-based Conflict Event Data", *J. Conflict Resolution* 59(6):1129–1149 | ⚠️ **This one changes our evaluation design.** Benchmarks UCDP-GED against military SIGACT records in Afghanistan and finds district-level patterns are captured reasonably well but **locational accuracy degrades sharply at finer spatial scales**. Consequence: our `where_prec ≤ 3` "ground truth" is not ground truth at 0.5° (~55 km). See `02 §5`. |
| 7 | **Weidmann (2013)**, "The higher the better? The limits of analytical resolution in conflict event datasets" | Asks directly whether one should work at fine spatial resolution with media-based event data at all. Prior art for the question our whole grid rests on. |

#### Tier 2 — strengthens the design

| # | Citation | What it buys |
|---|---|---|
| 8 | **Openshaw (1984)**, *The Modifiable Areal Unit Problem*, CATMOG 38 — ⚠️ *unverified* | The canonical MAUP statement; the vocabulary for why results change with the zoning. |
| 9 | **Dagum & Cholette (2006)**, *Benchmarking, Temporal Distribution, and Reconciliation Methods for Time Series*, Springer | The book-length treatment of the Denton/Chow–Lin family. Confirmed as the standard reference by the `TSdisaggregation` R package. |
| 10 | **Fernández (1981)** and **Litterman (1983)** | Chow–Lin variants under different error processes. Confirmed as part of the same family. Relevant because conflict series are strongly autocorrelated, which is exactly what distinguishes these variants. |
| 11 | **Manski (2003)**, *Partial Identification of Probability Distributions*, Springer — ⚠️ *unverified* | Bounds instead of point estimates: the formal case for emitting an interval rather than an allocation. Pairs with #5 for O3. |
| 12 | **Banerjee, Carlin & Gelfand**, *Hierarchical Modeling and Analysis for Spatial Data* (misalignment chapter) — ⚠️ *unverified* | The Bayesian treatment of spatial misalignment; the bridge from #1 to the LGCP machinery we already hold. |
| 13 | **Kish (1965)**, *Survey Sampling* (design effect / effective sample size) — ⚠️ *unverified* | The **origin of the formula views-hydranet is using**: ESS from weights as `(Σw)²/Σw²`. Anchors their instrument in its own literature instead of leaving it ad hoc. |
| 14 | **Young & Gotway (2007)**, "Linking spatial data from different sources: the effects of change of support", *SERRA* | The follow-up to #1, on the *effects* of change of support — i.e. what breaks downstream. |

#### Tier 3 — only if a specific path is taken

| # | Citation | Trigger |
|---|---|---|
| 15 | **Mennis (2003)** dasymetric mapping; **Eicher & Brewer (2001)** dasymetric/areal-interpolation evaluation — ⚠️ *unverified* | Only if ADR-049's proportional weighting is revisited or compared against alternatives. |
| 16 | **Dempster, Laird & Rubin (1977)**, EM — ⚠️ *unverified* | Only if allocation weights are ever *learned* rather than assumed. |
| 17 | **Gill, van der Laan & Robins (1997)** on coarsening at random — ⚠️ *unverified* | Only if O3 is formalised beyond a declared flag. |

#### Already held — do not re-fetch

The title scan surfaced holdings I missed in the first pass:

- **`Gilleland2009_SpatialVerificationIntercomparison`** — *Intercomparison of Spatial Forecast
  Verification Methods*. **Directly relevant to choosing the allocation metric** in `02 §5`; it is
  the survey of exactly the family (including earth-mover-style distances) we proposed to use.
- **`Dietrich2020`** — *Known unknowns: Media bias in the reporting of political violence*. Partly
  covers the reporting-bias need alongside Weidmann.
- `Weidmann2010_PredictingConflictSpaceTime` · `Tobler1970_ComputerMovieUrbanGrowth` (the 1970
  Detroit paper, **not** the 1979 pycnophylactic one) · `Giacomini2006_TestsConditionalPredictiveAbility`
  (for testing score differences) · `Wikle2001_SpatiotemporalHierarchicalBayesian` ·
  `Taylor2012_INLAMCMCLogGaussianCox`.

**The shape of the finding.** The library equips us to *measure* the damage and to *evaluate*
remedies rigorously. It does not equip us to *construct* them — and the missing material falls into
exactly the two families that correspond to the two strategies in `02_design`: redistribute
(change-of-support) and decline to redistribute (coarse data).
