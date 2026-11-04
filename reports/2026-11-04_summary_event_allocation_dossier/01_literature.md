# 01 — Literature

**Date:** 2026-11-04 · **Source:** `/home/simon/brain/9_library` (840 papers, 3,807 claims, 99%
extraction coverage), surveyed via the `library` skill plus a keyword scan over all 840 titles.

**Method note.** Semantic search returned near-uniform scores (~0.016) on roughly half the queries —
effectively noise — so every absence claim below was re-checked against the full title list rather
than inferred from a failed search. Three apparent hits on "extremes" were false positives:
`Martin2017_CleanArch_Ch30/31/32` matched `tail` inside *de**tail**s*. Absence of a title keyword is
strong evidence, not proof, of absent content.

---

## A0. ⭐ The eight acquisitions of 2026-11-04 — and what they changed

Simon added all seven Tier 1 items plus one I did not know existed. **Four of them change the
design**, and one makes the status quo formally indefensible rather than merely suboptimal.

### A0.1 `Croicu2026_GeospatialPrecisionConflictData` — the decisive paper

*Enhancing geospatial precision in conflict data: a stochastic approach to addressing known
geographically imprecise observations in conflict event data.*

This is our problem, by its own name, from inside UCDP/ViEWS. What it establishes:

- **KGI is 31.1% of 293,634 UCDP GED observations** (20–40% across GED, ACLED and SCAD).
  ⚠️ Our own measurement puts `where_prec ≥ 4` at 68,084 of 440,461 (15.5%) — a different
  denominator and possibly a different KGI definition. **The two numbers must be reconciled before
  either is cited**; added to P0.
- **KGI is non-random.** It correlates with remoteness, reporting quality, *and commonly used
  predictors of violence* — so both centroid retention and list-wise deletion are sources of
  systematic bias.
- **Multiple Spatial Imputation (MSI).** Fit actor-dyad-monthly Gaussian Process models of the
  probabilistic conflict space from the cloud of *precisely located* events in a 24-month window,
  then sample *m* plausible locations for each KGI point **within its known administrative
  boundary**. Two RBF length-scale priors — local (0.25°, ~27.5 km) and conflict-zone global
  (0.5°, ~55 km) — with roughly half the draws from each. Output: *m* complete datasets for a
  multiple-imputation or **ensemble-forecasting** framework.
- **Measured effect.** RMSLE down **34.92%** vs list deletion and **36.30%** vs UCDP centroid
  imputation across 800 simulated worlds; MSI wins in **100% of 2,400 simulations**. Point-level
  geographic error falls from **519 km → 275 km** (mean) and **468 km → 205 km** (median).
- **Robust** to remoteness bias at empirically plausible levels (w_bias 0–0.3); breaks only at
  implausible (~0.7).
- **Cheap version works.** Even **m = 1** beats centroid placement in 100% of simulations and list
  deletion in 93.2%. Gains plateau past **m = 20**.
- **Actor-dyad level is essential *and* is what makes it tractable** — per-dyad-month models average
  308 points, roughly **27,000× cheaper** than one GP over the full dataset given O(n³).
- **Stated limit.** MSI addresses only "known unknowns", and assumes the precise-point cloud
  adequately represents the true conflict process — which is itself remoteness- and
  reporting-biased.

**This overturns two of ADR-049's deferrals.**

| ADR-049 deferred | Croicu's evidence |
|---|---|
| *Actor-informed distribution* — because actor normalisation is hard, some actors appear only in summary events, and it "approaches a conflict-process model rather than a data materialization step" | Actor-dyad decomposition is **essential** to the method and is precisely what makes the computation feasible. Reason (b) — actors with no well-located history — survives as a real gap; (c) is a boundary judgement Croicu answers the other way, by treating MSI as data preparation producing *m* datasets. |
| *Input uncertainty sampling* — "represent each imprecise event as a distribution over cells rather than a point allocation … belongs in a downstream transformation or modeling layer, not in the viewpoint" | MSI **is** that treatment, and it operates on the event cloud — the viewpoint layer's own input — not downstream. And m=1 means a cheap form exists today. |

**Note what Croicu does *not* benchmark: ADR-049's proportional weighting.** His comparators are
centroid imputation and list deletion. Our O1 is a third thing — deterministic dasymetric weighting
by well-located fatalities. **Plausibly O1 is a crude deterministic approximation of MSI's GP
surface**, and that is exactly the comparison our harness should run.

### A0.2 `Heitjan1991_IgnorabilityCoarseData` — this makes the status quo indefensible

The formalism: coarse data are observations in the *power set* of the sample space — a set
containing the realisation rather than the realisation. Subsumes rounding, heaping, censoring,
interval censoring and missingness. **Coarsened at random (CAR)** generalises MAR, and under CAR
plus distinct parameters the coarsening mechanism may be ignored.

**And the converse, which is the finding:** *"When coarsened data are not CAR, ignoring the
coarsening mechanism leads to severely biased inference"* — in their simulation, estimates land over
**21 standard errors** from the truth.

Compose that with Croicu's measurement that **KGI is non-random**:

> KGI is not CAR ⇒ ignoring the coarsening mechanism is expected to produce severely biased
> inference. `passthrough` and `date_end_only` ignore the coarsening mechanism.

**This upgrades the argument against the status quo from "the evaluation instrument degrades" to a
theorem with an empirically verified premise.** It is the strongest single result in this dossier
and it was not available to ADR-049.

### A0.3 `Weidmann2015_AccuracyMediaConflictData` — a ceiling, and a reversal

- Spatial error is **of the order of an administrative district, ~50 km**. 80% of matched events sit
  within 50 km; 63.4% hit the right district, +18.6% a neighbour.
- **"Spatial analyses using media-based conflict event data should not operate below approximately
  50×50 km grid cells or district-level resolution."** Our cells are 0.5° ≈ 55 km — **exactly at
  the stated floor.** That both *validates the grid choice* and *caps* how much allocation precision
  is worth chasing.
- ⭐ **Counts are substantially more accurate than locations.** In ~50% of matched events the
  casualty estimate agrees, and deviations are symmetric. **Remoteness degrades location accuracy
  but not casualty accuracy** — plausibly because casualty figures are politically sensitive and get
  verified, while location is treated as unimportant.
- Afghanistan is likely a **lower bound** on error, given unusually dense coverage.
- All of it conditional on an event being reported: this is the *veracity* problem, not *selection*.

**What this reverses.** Our evaluation design treated `where_prec ≤ 3` events as ground truth.
Weidmann says they are *precisely coded*, not *precisely known*. So the oracle is not a true
ceiling, and the metric must tolerate displacement of roughly one cell. See `02 §5` confound C-b.

**What it argues for.** Combined with `Vesco2026` (magnitudes underreported, but least so for large
events): **trust the count, distrust the location.** That is a direct argument for *allocating* a
reliable total across an honest spatial distribution, and against dropping (O4) — which discards a
reliable number because of an unreliable coordinate.

### A0.4 `Weidmann2013_AnalyticalResolutionConflictData` — the resolution gradient

ACLED vs the WikiLeaks War Diary: correlation **0.68** at province/month, **0.29** at district/week,
**0.15** at cell/three-day. Triangulation across *different reporting mechanisms* is a more
fundamental validity check than swapping datasets built by the same mechanism. And the caution we
should carry: *"Neither dataset has a prior claim to greater accuracy"* — the mismatch does not
invalidate either, and the discrepancies deserve study in their own right.

### A0.5 `Gotway2002_CombiningIncompatibleSpatialData` — the map we were missing

**Ecological inference, MAUP, block kriging, the scaling problem, pycnophylactic interpolation, the
polygonal overlay problem and spatially misaligned data are all special cases of the change of
support problem.** We had been treating ours as sui generis.

- MAUP decomposes into the **scale effect** and the **grouping/zoning effect**.
- Any COSP solution must (1) account for the information lost to aggregation and (2) relate
  variation among aggregated units to variation among the original units.
- The **point-support covariance function is the building block**: block-support covariances follow
  by integrating it over the regions.
- **Bayesian hierarchical models are the unifying framework** — measurement model + process model +
  parameter model. (This is also the frame Croicu's GP sits in.)
- Map overlay methods form a ladder: **simple proportional allocation → pycnophylactic interpolation
  (Tobler 1979) → geostatistical/hierarchical approaches.** **ADR-049's proportional weighting is
  the bottom rung of a known ladder**, which is useful and not pejorative: it tells us what the next
  rung is.
- ⭐ A direct mandate for our harness: *"the assumptions made when combining incompatible spatial
  data … often surreptitiously determine cross-scale relationships, and data-driven diagnostic and
  validation tools to assess the impact and validity of these assumptions are needed."*

### A0.6 `Tobler1979_SmoothPycnophylacticInterpolation` — mass preservation as a method

Minimise the Dirichlet integral (sum of squared first partials) **subject to the constraint that the
density integrates to the observed count in each region**. Unconstrained this is Laplace's equation;
constrained it is the pycnophylactic surface. Two smoothness options (Laplacian and biharmonic).
Exactly invertible: the original counts are recoverable.

Three practical details that transfer directly:

1. **Boundary conditions matter decisively** and propagate inward. Dirichlet (fixed values — e.g.
   **zero density at water boundaries**) vs Neumann (zero gradient). **We have a land mask**
   (`datafactory_priogrid/land_mask.py`), so the Dirichlet-at-water condition is available to us.
2. **Negative densities are clipped to zero** each iteration — the same non-negativity problem any
   allocation of fatalities faces.
3. The stated core assumption is **spatial smoothness**: *events in one region affect adjacent
   regions*. For conflict that is defensible, and it is the same assumption ADR-049's proportional
   weighting makes implicitly without stating it.

Tobler also frames the exact use case: *interconverting data collected under distinct sets of
geographical boundaries* — i.e. admin-1 polygon → PRIO-GRID cell.

### A0.7 `Denton1971_AdjustmentMonthlyQuarterly` — ⚠️ it rejects `even_split` by name

Constrained quadratic minimisation: minimise `(x−z)'A(x−z)` subject to `B'x = y` (sub-annual values
sum to the annual total).

**The finding that changes O2:** with `A = I` — minimising squared differences, which distributes
each year's discrepancy *equally* among sub-annual periods — the result *"in general introduces
spurious discontinuities at year boundaries"*, and Denton states the specification is
**"inadequate for practical use."**

**That is `even_split`.** The option we proposed for O2 is precisely the special case Denton wrote
the paper to improve upon. The remedy is his: specify the penalty on **first differences**
(`A = D'D`), which removes the year-boundary artefact. He also gives a proportionate-difference
variant where larger original values bear commensurately larger adjustment.

### A0.8 `ChowLin1971_BestLinearUnbiasedInterpolation` — conservation for free

One regression model `y = Xβ + u` unifies interpolation, distribution and extrapolation. The BLUE
estimator combines fitted values from indicator series with a distributed residual.

⭐ **Temporal additivity is not imposed as a constraint — it emerges from best linear unbiasedness.**
A conserving allocation need not be a *constrained* allocation. With AR(1) residuals the estimator
needs only the autocorrelation parameter, which matters here because conflict series are strongly
autocorrelated. And the methodological aside worth keeping: *the distinction between distribution
and interpolation is unjustified from the viewpoint of estimation theory.*

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

## B. Gaps — status after the 2026-11-04 acquisitions

**Four of the six gaps are now closed.** What the eight new papers did and did not fix:

Each line was checked against all 840 titles.

| Gap | Status | Now held / still missing |
|---|---|---|
| **Change of support / MAUP / ecological inference** | ✅ **closed** | `Gotway2002` — and it reframes our problem as a known special case of COSP rather than something novel. |
| **Temporal disaggregation / benchmarking** | ✅ **closed for the core** | `Denton1971` + `ChowLin1971`. ⚠️ Denton *rejects* `even_split` by name (§A0.7), so this closure changed option O2. Still missing: `Dagum & Cholette (2006)` for the book-length family, and the `Fernández`/`Litterman` variants. |
| **Areal interpolation / mass-preserving allocation** | ✅ **closed for the key method** | `Tobler1979` gives pycnophylactic interpolation, i.e. ADR-040 Invariant 1 as a method, with boundary conditions we can map onto our land mask. Still missing: the dasymetric *evaluation* literature (Mennis; Eicher & Brewer), Tier 3. |
| **Coarsened-at-random / partial identification** | ✅ **closed for the decisive half** | `Heitjan1991` supplies CAR **and its converse** — the result that makes the status quo indefensible once KGI is known to be non-random (§A0.2). Still missing: `Manski` on partial identification, if O3 is ever formalised into bounds. |
| **KGI in conflict data specifically** | ✅ **closed — and it was not on my list** | `Croicu2026`. A method (MSI), a measured effect size, and a boundary judgement that contradicts two of ADR-049's deferrals. |
| **The resolution floor for media-based event data** | ✅ **closed** | `Weidmann2015` + `Weidmann2013`. Our 0.5° grid sits exactly at the stated floor, which validates it and caps achievable allocation precision. |
| Influence / leverage diagnostics for *scores* | ❌ **still open** | Nothing acquired. `Kish (1965)` would anchor views-hydranet's ESS formula in its own literature; Tier 2. |
| EM / latent allocation | ❌ **still open** | Lower priority, and partly superseded: Croicu's GP-sampling approach is the method we would actually use, and we now hold it. |

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
