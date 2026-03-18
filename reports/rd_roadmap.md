# Research & Development Roadmap

**Repository:** views-datafactory
**Date:** 2026-03-16
**Status:** Living document

---

## 1. Problem Definition

The VIEWS conflict forecasting platform requires a data foundation that can:

- **Harvest** conflict event data from multiple providers (UCDP/GED today, additional sources tomorrow) with full audit trail and drift detection, at a standard appropriate for mission-critical humanitarian early warning systems.
- **Construct** a spatiotemporal grid (PRIO-GRID, 259,200 cells at 0.5° resolution, monthly time steps) as a shared coordinate system for all downstream consumers.
- **Compile** raw event data onto that grid, producing dense arrays suitable for neural forecasting models.
- **Generate** synthetic data with covariance structure statistically faithful to authentic conflict data, enabling controlled experimentation.
- **Track provenance** end-to-end, so any value in a compiled grid can be traced back to the specific source records and compilation config that produced it.

The system architecture is a **graph, not a pipeline**: source nodes (harvesters, synthetic generators) produce data independently; compilation edges transform source data into consumer-specific formats (grid npy, panel parquet, relational DB); consumer nodes (the metric lab, other VIEWS repos) read compiled outputs. Sources don't know about consumers. Edges are consumer-driven. This structure must be preserved as the system grows.

---

## 2. Research Questions

### Data
**RQ-1:** What is the statistical profile of real UCDP/GED conflict data when aggregated to PRIO-GRID cells at monthly resolution — specifically the zero-inflation rate, tail index, spatial autocorrelation length, and temporal persistence?

**RQ-2:** How do candidate monthly revisions (UCDP's in-flight corrections) affect the statistical profile? Is the revision process itself informative (do revisions cluster in space/time)?

**RQ-3:** As new data sources are integrated (ACLED, satellite-derived indicators, PRIO static variables), how should multi-source compilation handle temporal misalignment, spatial resolution mismatch, and conflicting values?

### Synthetic Generation
**RQ-4:** Can a grid-native synthetic generator (spatial kernels + temporal AR processes) reproduce the joint covariance structure of real conflict data — including cross-feature correlations, spatial clustering, and regime-dependent tail behavior?

**RQ-5:** What is the minimum set of statistical moments/properties that must match between synthetic and authentic data for downstream model evaluation to remain valid? (Zero-inflation rate alone is insufficient; spatial correlation and tail index are likely necessary.)

**RQ-6:** The metric lab's existing generators (LatentDataGenerator, EpistemicGenerator) use Log-Normal tails, which are lighter than the power-law behavior observed in real conflict data. Can GPD-based or Pareto-mixture generators on the grid produce more faithful tail structure while maintaining controllable covariance?

### Compilation
**RQ-7:** What aggregation strategies (count, sum fatalities, max severity, weighted combinations) produce the most informative grid features for the Hurdle decomposition models that will consume them?

**RQ-8:** How should the compilation node handle the boundary between the annual dataset (authoritative but delayed) and the candidate monthly dataset (current but revised)? Is temporal stitching sufficient, or does the revision uncertainty need to propagate into the compiled output?

---

## 3. Hypotheses

**H-1:** A grid-native synthetic generator with Matérn spatial correlation and AR(1) temporal dynamics will produce data whose spatial autocorrelation function matches real UCDP/GED data within 10% across all lag distances up to 5 degrees.

**H-2:** Replacing Log-Normal magnitude distributions with GPD (Generalized Pareto Distribution) in the synthetic generator will reduce the tail index discrepancy between synthetic and authentic data by at least 50%, as measured by the Hill estimator.

**H-3:** Content-digest-based provenance (SHA-256 of source data + compilation config) is sufficient to detect all cases where a compiled grid becomes stale due to upstream revision, without requiring timestamp-based invalidation.

**H-4:** The statistical fidelity of synthetic data (as measured by a validation node comparing authentic vs. synthetic compiled grids) will degrade gracefully as the number of controlled features increases — i.e., adding spatial correlation does not break temporal fidelity.

---

## 4. Data Research Agenda

### 4.1 Characterising the Authentic Data-Generating Process

The first research task after compilation is operational: produce a **statistical profile** of real UCDP/GED data on the PRIO-GRID. This profile becomes the calibration target for synthetic generators and the reference distribution for drift detection.

Required statistics:
- Marginal: zero-inflation rate, mean/variance of positive counts, tail index (Hill estimator), kurtosis
- Spatial: empirical variogram (semivariance vs. lag distance), Moran's I at multiple scales
- Temporal: autocorrelation function, regime persistence (mean time in zero-state vs. active-state)
- Joint: cross-feature correlations (fatalities vs. event count, type of violence vs. intensity)

### 4.2 Source Expansion

Current: UCDP/GED (annual + candidate monthly).

Planned:
- **ACLED** (Armed Conflict Location and Event Data) — higher temporal resolution, different coding methodology. Research question: how do ACLED and UCDP events correspond spatially and temporally?
- **PRIO-GRID static variables** — population, terrain, climate. These are covariates, not conflict events. Different harvester pattern (periodic snapshots, not event streams).
- **Satellite-derived indicators** — NDVI, nightlights, population displacement proxies. Research question: what spatial/temporal resolution and latency are achievable?

Each new source raises its own research questions about bias, coverage, and alignment with the existing grid.

### 4.3 Revision Dynamics

UCDP revises past months in candidate releases. This creates a data-generating process *about* the data-generating process. Questions:
- Do revisions correlate with conflict intensity (more revisions in active zones)?
- What is the typical revision magnitude (number of events added/removed/changed)?
- Can revision patterns serve as an uncertainty indicator for recent data?

The harvester already tracks revisions via digest comparison and snapshot archiving. The research task is to analyse these archives.

---

## 5. Modeling Research Agenda

The data factory does not build forecasting models — that's the metric lab's domain. But it must produce data that models can consume effectively.

### 5.1 Aggregation Strategy Research

Different aggregation strategies produce different features:
- **Event count**: How many conflict events in this cell-month?
- **Fatality sum**: Total fatalities in this cell-month.
- **Max severity**: Worst single event in this cell-month.
- **Type decomposition**: Separate counts by type_of_violence (state-based, non-state, one-sided).

The compiler should support pluggable aggregation. The research question is which strategies produce the best downstream signal — this requires collaboration with the metric lab (run models on different aggregations, compare evaluation metrics).

### 5.2 Resolution Research

The grid is currently 0.5° (PRIO standard). Some research questions:
- Does 0.25° resolution improve model performance? (4× more cells, potentially better spatial signal.)
- Does temporal resolution finer than monthly help? (Weekly or daily aggregation.)
- The grid generator already supports custom resolution. The compiler would need to handle the increased dimensionality.

---

## 6. Experimentation Framework

### 6.1 Synthetic vs. Authentic Fidelity Testing

The validation node (future) will compare:
- Marginal distributions (KS test, AD test on tails)
- Spatial structure (variogram comparison, Moran's I)
- Temporal structure (ACF comparison, regime duration histograms)
- Joint structure (cross-correlation matrices)

Protocol: generate synthetic data with current best parameters → compile to grid → compare against authentic grid → report discrepancies → adjust generator parameters → repeat.

### 6.2 Compilation Regression Testing

When a new data source is added or an aggregation strategy changes, the compiled output changes. Regression testing:
- Compile with old config → store digest
- Compile with new config → compare
- Report: which cells changed, by how much, in which direction

This uses the same provenance infrastructure as the harvester.

### 6.3 Harvester Stress Testing

- **API failure modes**: What happens when UCDP returns 500, timeout, partial response, malformed JSON?
- **Schema drift**: What happens when UCDP adds/removes/renames fields between versions?
- **Revision storms**: What if a candidate monthly release revises >50% of events?

The harvester's validation module already detects schema violations and distributional drift. The research task is to characterise the failure modes systematically and ensure the audit system catches them.

---

## 7. Evaluation Metrics

### For Data Quality
- **Completeness**: Fraction of expected (cell, month) pairs with data vs. structural zeros
- **Freshness**: Time since last successful harvest per source
- **Revision stability**: Fraction of cells whose compiled value changed between consecutive candidate versions
- **Provenance integrity**: Fraction of compiled outputs with complete source→output lineage

### For Synthetic Fidelity
- **Marginal KS distance**: Maximum CDF deviation between synthetic and authentic marginals
- **Tail index ratio**: Hill estimator (synthetic) / Hill estimator (authentic) — target: 1.0
- **Variogram RMSE**: Root mean squared error between empirical variograms
- **ACF RMSE**: Root mean squared error between autocorrelation functions at lags 1-12

### For System Health
- **Digest collision rate**: Should be 0.0 (SHA-256)
- **Ledger completeness**: Every compiled output has a corresponding provenance entry
- **Rebuild fidelity**: Deleting compiled outputs and rebuilding from raw data + provenance produces bit-identical results

---

## 8. Uncertainty Research

### 8.1 Source Uncertainty

UCDP data is not ground truth. Events are coded from media reports, and coding decisions involve judgment. Known uncertainty sources:
- **Fatality estimates**: UCDP provides `best`, `low`, `high` — these are expert estimates, not confidence intervals
- **Spatial precision**: `where_prec` field indicates geocoding quality (1=exact, 7=country only)
- **Temporal precision**: `date_prec` indicates date certainty
- **Coverage bias**: Media-rich regions are better covered than remote areas

Research question: can these precision fields be propagated through compilation into the grid as per-cell uncertainty estimates?

### 8.2 Compilation Uncertainty

Aggregating events to cells introduces additional uncertainty:
- Events with low spatial precision (where_prec > 3) are assigned to cells with significant spatial ambiguity
- Multiple events in the same cell-month may overlap or double-count
- The choice of aggregation strategy (count vs. sum vs. max) produces different values from the same inputs

Research question: can compilation produce not just point estimates but uncertainty bands per cell-month?

### 8.3 Revision Uncertainty

The candidate monthly data is revised. The compiled grid from month N may change when month N+1 is released. This creates a "nowcasting" uncertainty that decays as data matures.

Research question: can the revision archive be used to estimate the expected revision magnitude for recent data, providing a data-maturity confidence indicator?

---

## 9. Research Milestones

### Phase 1: Characterise (current → near-term)
- [x] Compile authentic UCDP/GED data onto PRIO-GRID as npy — code complete (DoD004), ready for real data
- [ ] Produce statistical profile of authentic data (marginals, spatial, temporal, joint)
- [ ] Establish calibration targets for synthetic generators

### Phase 2: Generate (near-term)
- [ ] Build grid-native synthetic generator with controllable spatial and temporal covariance
- [ ] Calibrate against authentic statistical profile
- [ ] Validate synthetic fidelity (KS, variogram, ACF comparisons)

### Phase 3: Expand (medium-term)
- [ ] Add second data source (ACLED or PRIO static variables)
- [ ] Design multi-source compilation (handle resolution mismatch, temporal misalignment)
- [ ] Characterise revision dynamics from candidate monthly archive

### Phase 4: Quantify Uncertainty (longer-term)
- [ ] Propagate source precision fields through compilation
- [ ] Estimate compilation uncertainty (aggregation sensitivity)
- [ ] Build revision-based nowcasting confidence indicator

---

## 10. Research Risks

**R-1: Covariance structure may be intractable.**
Real conflict data may have covariance structure (spatial clustering around borders, contagion dynamics, regime-dependent correlation) that cannot be captured by stationary spatial kernels. Mitigation: start simple (Matérn + AR(1)), measure the gap, add complexity only where the fidelity metrics demand it.

**R-2: Tail faithfulness may require domain-specific generators.**
Log-Normal tails are too light; GPD may be too heavy in some regimes. The "right" tail distribution may vary by region and conflict type. Mitigation: make the tail distribution a pluggable component of the generator, not hardcoded.

**R-3: Multi-source compilation may introduce systematic bias.**
Different sources (UCDP, ACLED) have different coverage, coding rules, and biases. Naively combining them on the same grid may amplify rather than reduce uncertainty. Mitigation: keep sources as separate features in the compiled grid; let consumers decide how to combine.

**R-4: Provenance overhead may become burdensome.**
Full end-to-end provenance for every cell in a 259,200 × 432 grid is ~112 million provenance records. Mitigation: track provenance at the source-snapshot level (not per-cell), with deterministic compilation ensuring cell-level traceability is recoverable.

**R-5: Synthetic fidelity validation may be circular.**
If we calibrate synthetic generators against authentic data, and then validate models on synthetic data, we're testing models against our own assumptions about the data-generating process. Mitigation: always validate final models on held-out authentic data; synthetic data is for development, not final evaluation.
