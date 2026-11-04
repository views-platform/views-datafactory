# 09 — Library acquisition list

**Date:** 2026-11-04 · **Target:** `/home/simon/brain/9_library` (via `/library add <pdf>`)
**Checked against all 840 existing titles — nothing below is already held.**
Citations verified by search 2026-11-04 except where marked ⚠️ *unverified* (recalled; confirm
before spending time hunting).

PDF naming per ADR-019: `<FirstAuthorSurname><Year>_<ShortTitle>.pdf`.

---

## Tier 1 — ✅ **ACQUIRED 2026-11-04** (all seven, plus one)

Simon added all seven, plus `Croicu2026_GeospatialPrecisionConflictData`, which was not on this list
and is the most important of the eight. Library is now 848 papers. See `01 §A0` for what each one
changed; four of them changed the design. **Nothing in this tier remains to fetch.**

| library paper_id | status |
|---|---|
| `ChowLin1971_BestLinearUnbiasedInterpolation` | ✅ in |
| `Denton1971_AdjustmentMonthlyQuarterly` | ✅ in |
| `Tobler1979_SmoothPycnophylacticInterpolation` | ✅ in |
| `Heitjan1991_IgnorabilityCoarseData` | ✅ in |
| `Gotway2002_CombiningIncompatibleSpatialData` | ✅ in |
| `Weidmann2013_AnalyticalResolutionConflictData` | ✅ in |
| `Weidmann2015_AccuracyMediaConflictData` | ✅ in |
| **`Croicu2026_GeospatialPrecisionConflictData`** | ✅ in — **not requested by me; the decisive paper** |

<details><summary>Original Tier 1 request, kept for the record</summary>


| # | Suggested filename | Full citation | Access |
|---|---|---|---|
| 1 | `Gotway2002_CombiningIncompatibleSpatialData.pdf` | Gotway, C.A. & Young, L.J. (2002). "Combining Incompatible Spatial Data." *Journal of the American Statistical Association* **97**(458), 632–648. doi:10.1198/016214502760047140 | paywalled (JASA) |
| 2 | `Tobler1979_SmoothPycnophylacticInterpolation.pdf` | Tobler, W.R. (1979). "Smooth Pycnophylactic Interpolation for Geographical Regions." *JASA* **74**(367), 519–530. doi:10.1080/01621459.1979.10481647 | paywalled; copies circulate |
| 3 | `Denton1971_AdjustmentToAnnualTotals.pdf` | Denton, F.T. (1971). "Adjustment of Monthly or Quarterly Series to Annual Totals: An Approach Based on Quadratic Minimization." *JASA* **66**(333), 99–102. | paywalled |
| 4 | `ChowLin1971_BestLinearUnbiasedInterpolation.pdf` | Chow, G.C. & Lin, A. (1971). "Best Linear Unbiased Interpolation, Distribution, and Extrapolation of Time Series by Related Series." *Review of Economics and Statistics* **53**(4), 372–375. | paywalled |
| 5 | `Heitjan1991_IgnorabilityAndCoarseData.pdf` | Heitjan, D.F. & Rubin, D.B. (1991). "Ignorability and Coarse Data." *Annals of Statistics* **19**(4), 2244–2253. doi:10.1214/aos/1176348396 | ✅ **open access** — projecteuclid.org/euclid.aos/1176348396 |
| 6 | `Weidmann2015_AccuracyMediaBasedConflictEventData.pdf` | Weidmann, N.B. (2015). "On the Accuracy of Media-based Conflict Event Data." *Journal of Conflict Resolution* **59**(6), 1129–1149. | ✅ **green OA** — KOPS, Univ. Konstanz |
| 7 | `Weidmann2013_LimitsAnalyticalResolution.pdf` | Weidmann, N.B. (2013). "The Higher the Better? The Limits of Analytical Resolution in Conflict Event Datasets." *Cooperation and Conflict* (⚠️ venue unverified). | ✅ **green OA** — KOPS |

**Why these seven.** #1 and #5 are the two frameworks we were reasoning *without*: change of
support, and coarsening. #2 is mass-preserving interpolation — our ADR-040 conservation invariant as
an existing method. #3 and #4 are the temporal-allocation family that option O2 would otherwise
reinvent. #6 and #7 bound how much allocation skill is even measurable at 0.5° resolution.

</details>

### What acquiring them cost us in rework — worth recording

Three of my own positions did not survive the reading, which is the point of reading first:

1. **O2 was going to be `even_split`.** Denton (1971) rejects exactly that specification by name as
   *"inadequate for practical use"* — it introduces spurious year-boundary discontinuities. O2 is now
   Denton first-difference.
2. **The case against the status quo was "the evaluation instrument degrades."** With
   `Heitjan1991` + `Croicu2026` it is a theorem with a verified premise: KGI is non-random, hence not
   CAR, hence ignoring the coarsening mechanism is expected to bias inference severely.
3. **ADR-049's two deferrals looked settled.** Croicu contradicts both — actor-level modelling is
   *essential* rather than premature, and the sampling treatment belongs in data preparation rather
   than downstream.

## Tier 2 — still to fetch; strengthens the design

| # | Suggested filename | Full citation | Note |
|---|---|---|---|
| 8 | `DagumCholette2006_BenchmarkingTemporalDistribution.pdf` | Dagum, E.B. & Cholette, P.A. (2006). *Benchmarking, Temporal Distribution, and Reconciliation Methods for Time Series.* Springer, Lecture Notes in Statistics 186. | book — consider `/library add-book` |
| 9 | `Fernandez1981_MethodologicalNoteInterpolation.pdf` | Fernández, R.B. (1981). "A Methodological Note on the Estimation of Time Series." *Review of Economics and Statistics* **63**(3), 471–476. ⚠️ *title/pages unverified* | Chow–Lin variant |
| 10 | `Litterman1983_RandomWalkMarkovInterpolation.pdf` | Litterman, R.B. (1983). "A Random Walk, Markov Model for the Distribution of Time Series." *Journal of Business & Economic Statistics* **1**(2), 169–173. ⚠️ *pages unverified* | Chow–Lin variant; relevant because conflict series are strongly autocorrelated |
| 11 | `YoungGotway2007_LinkingSpatialDataChangeOfSupport.pdf` | Young, L.J. & Gotway, C.A. (2007). "Linking spatial data from different sources: the effects of change of support." *Stochastic Environmental Research and Risk Assessment* **21**, 589–600. ⚠️ *pages unverified* | the follow-up to #1 |
| 12 | `Openshaw1984_ModifiableArealUnitProblem.pdf` | Openshaw, S. (1984). *The Modifiable Areal Unit Problem.* CATMOG 38, Geo Books. ⚠️ *unverified* | canonical MAUP; CATMOG series is freely available online |
| 13 | `Manski2003_PartialIdentification.pdf` | Manski, C.F. (2003). *Partial Identification of Probability Distributions.* Springer. ⚠️ *unverified* | book; bounds instead of point estimates — pairs with #5 for O3 |
| 14 | `Banerjee2015_HierarchicalModelingSpatialData.pdf` | Banerjee, S., Carlin, B.P. & Gelfand, A.E. *Hierarchical Modeling and Analysis for Spatial Data*, 2nd ed. (2015), CRC. ⚠️ *unverified* — want the **spatial misalignment** chapter | book; bridges #1 to the LGCP machinery we already hold |
| 15 | `Kish1965_SurveySampling.pdf` | Kish, L. (1965). *Survey Sampling.* Wiley. ⚠️ *unverified* — want the **design effect / effective sample size** material | **the origin of views-hydranet's own formula**, ESS from weights as `(Σw)²/Σw²`. Anchors their instrument in its literature. A later secondary source may serve better than the 1965 book. |

## Tier 3 — still to fetch; only if a specific path is taken

| # | Citation | Trigger |
|---|---|---|
| 16 | Mennis, J. (2003). "Generating Surface Models of Population Using Dasymetric Mapping." *The Professional Geographer* **55**(1), 31–42. ⚠️ *unverified* | only if ADR-049's proportional weighting is revisited |
| 17 | Eicher, C.L. & Brewer, C.A. (2001). "Dasymetric Mapping and Areal Interpolation: Implementation and Evaluation." *Cartography and Geographic Information Science* **28**(2), 125–138. ⚠️ *unverified* | as #16; this is the *evaluation* half |
| 18 | Dempster, A.P., Laird, N.M. & Rubin, D.B. (1977). "Maximum Likelihood from Incomplete Data via the EM Algorithm." *JRSS-B* **39**(1), 1–38. ⚠️ *unverified* | only if allocation weights are ever **learned** rather than assumed |
| 19 | Gill, R.D., van der Laan, M.J. & Robins, J.M. (1997). "Coarsening at Random: Characterizations, Conjectures, Counter-Examples." ⚠️ *unverified* | only if O3 is formalised beyond a declared flag |

---

## Already held — do **not** re-fetch

Surfaced by the title scan; two were missed in the first survey pass:

- **`Gilleland2009_SpatialVerificationIntercomparison`** — *Intercomparison of Spatial Forecast
  Verification Methods*. **Directly relevant to the metric choice in `02 §5`**; it surveys exactly
  the family (including displacement-tolerant distances) we proposed to use.
- **`Dietrich2020`** — *Known unknowns: Media bias in the reporting of political violence*. Partly
  covers the reporting-bias need alongside Weidmann.
- `Vesco2026_UnderreportedDeathTollWars` + `Vesco2024_UnderreportedDeathTollPreprint` ·
  `Gibbons2014_MeasuringUnderreportingInfectiousDisease` · `Weidmann2010_PredictingConflictSpaceTime` ·
  `Tobler1970_ComputerMovieUrbanGrowth` (the Detroit paper — **not** the 1979 pycnophylactic one) ·
  `Giacomini2006_TestsConditionalPredictiveAbility` · `Wikle2001_SpatiotemporalHierarchicalBayesian` ·
  `Taylor2012_INLAMCMCLogGaussianCox` · `Lerch2017_ForecastersDilemmaExtremeEvents` ·
  `Gneiting2011_ComparingDensityForecasts` · `Bolin2023_LocalScaleInvarianceScoringRules` ·
  `Arnold2024_CRPSDecompositions` · `Brehmer2023_PointProcessForecasts` ·
  `Moller1998_LogGaussianCoxProcesses` · `Wickramasuriya2019_OptimalForecastReconciliation` ·
  `Panagiotelis2023_ProbabilisticForecastReconciliation`.

## Software worth noting (not library items)

- **`pycno`** (R, CRAN) — implements Tobler's pycnophylactic interpolation. A reference
  implementation to validate any mass-preserving spatial allocation against.
- **`TSdisaggregation`** (R, CRAN) — implements Denton, Chow–Lin, Fernández, Litterman. Same role
  for the temporal axis.

Both are useful as **oracles for the coarsen-and-recover harness** (`03 §C1`): if our allocation
disagrees with an established implementation on the same input, one of us is wrong, and that is a
cheaper test than arguing from first principles.
