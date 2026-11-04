# 02 — Design: the option space, and what belongs to this repo

**Date:** 2026-11-04 · **Status:** drafted, awaiting `expert-method-review`
**Graduates to:** a proposed ADR amending/extending ADR-049 on `promote`

---

## 1. The problem, stated precisely

UCDP records a fatality total together with its own declaration of how precisely that total is
located in space (`where_prec`) and time (`date_prec`). When either declaration is coarse, the total
refers to a *region* and a *window*, not to a cell-month. The viewpoint layer must nevertheless emit
cell-months. **The allocation is therefore unavoidable and is a modelling decision**, whatever we do
— including when we do nothing, because "assign it all to one cell-month" is an allocation too, and
the least defensible one.

Measured consequence (`reports/investigation_summary_event_concentration/findings.md`): 21,766
events / 21.95% of all fatality mass; 48.8% of mass in 2020–2024; ten cell-months holding 12.4% of
the dataset; one cell holding 7.79% of all fatalities ever recorded.

## 2. What is *not* in question

- **UCDP is not at fault.** Every event carries honest precision metadata.
- **The information is present.** `date_prec` and `where_prec` are harvested and retained.
- **The capability is partly built.** Five temporal strategies and a `where_prec ≥ 4` polygon
  mechanism exist and are tested.

## 3. ⚠️ CORRECTED 2026-11-04 — ADR-049 *is* implemented; what was missing was the join

**This section originally claimed ADR-049 "is accepted and not live." That was wrong, and the
error mattered**, because it framed a governance gap as an implementation gap and would have sent
P2 looking for code that already exists.

**What is actually true.** `proportional` implements §3's mechanism in full — polygon determination
via the GAUL crosswalks, proportional weighting, uniform fallback, exact floor-plus-remainder
conservation — with **46 unit tests**, the builder wired to it, the weight map built whenever the
strategy is not `passthrough`, the crosswalk parquets present, and
**`ViewpointConfig.spatial_distribution_strategy` defaulting to `"proportional"`**, which honours
§6's "on by default" as written. A full weight-map build over the 2.73M-row store takes **3.1
seconds**.

**What was genuinely missing** is narrower and was closed on 2026-11-04:

1. `production_parity` was the *only* registered UCDP profile, and it overrides the default back to
   `passthrough` for VIEWSER parity. So §6's recommended behaviour had **no name anyone could
   select**, could not be compared against parity, and could not be tested end to end.
2. **No test asserted either choice**, so the ADR and the invoked configuration could drift in
   silence — and did, for four months, while cell 148759's total *grew* from 273,076 to 274,358 with
   nothing going red. C-365's mechanism exactly: a decision with no observer.

**Closed by** the ADR-049 amendment of 2026-11-04, the `kgi_distributed` profile, and
`tests/test_adr049_profile_contract.py`. The production pipeline still invokes `production_parity`;
switching it remains open and is decision D1.

### Measured consequence of the mechanism, for reference

Cell 148759 sits in GAUL admin-1 **1301**, which has **18 weighted cells**, and the cell's own weight
is **0.0743**. So under `proportional` the Tigray event's 113,368 fatalities split across 18 cells
with ~**8,423** landing on 148759 instead of 113,368 — a **13.5× reduction**, conserving the total
exactly. That is §Validation's criterion, now asserted by test rather than asserted by prose.

### The two findings that remain unchanged

`init` found two divergences between the accepted ADR and the code. **Both are governance questions,
not research questions, and both should be resolved before any experiment is designed** — otherwise
this program risks "discovering" a decision that was already taken in June.

#### Finding 1 — the golden criterion was unobserved (now fixed)

ADR-049 §6: *"Spatial distribution is **on by default** for all events with `where_prec` ≥ 4."*
ADR-049's own golden test: *"cell 148759's all-history total should drop from 273,076 to its
proportional share within the Tigray admin-1 region."*

Measured 2026-11-04 on `data/viewpoint/production_parity.parquet`:

| | ADR-049 (2026-06-28) | measured now |
|---|---:|---:|
| cell 148759, all history | 273,076 | **274,358** |
| cell 150919, all history | 79,841 | **80,064** |

The profile sets `spatial_distribution_strategy="passthrough"`. The totals have *grown*, not
dropped. **The ADR's golden test is not satisfied and nothing is red**, because no test asserts it.

#### Finding 2 — the ADR's worked example misdescribes the code (now corrected in the ADR)

ADR-049 §Context: *"the Tigray war event (id 463131 …) **is spread across 12 months by temporal
distribution (correct)** but dumped into one cell spatially (incorrect)."*

Measured: **event 463131 produces exactly one output row**, at `date_month 2021-12-01`. It is not
spread at all. The cause is `source_distribution_map={"annual": "date_end_only"}`, which overrides
`ceil_split` for annual-source events — and 463131 is annual-source. ADR-049's premise that the
temporal analog already works is false for the production profile.

**Consequence for this program.** The spatial half is *decided but dormant*; the temporal half is
*undecided and was believed decided*. The research question is therefore narrower and differently
shaped than #533 implies.

### The parity knot, and how ADR-049 already unties it

`source_distribution_map={"annual": "date_end_only"}` is under a standing freeze (VIEWSER
`GedLoader` parity; formally with Håvard). That freeze looks like it blocks everything — but
**ADR-049 §6 already resolved the same tension on the spatial side**: parity *"remains achievable via
configuration"*. Parity is a **profile**, not a destiny.

So the design does not require changing what parity means. It requires deciding whether parity
remains the **default**. That reframing is the single most useful thing in this document:

> Keep `production_parity` byte-identical and frozen. Add a separate recommended profile. The
> question becomes which profile the pipeline invokes — a one-line, reversible, auditable change —
> rather than whether to mutate a frozen contract.

## 4. The option space

Options are not mutually exclusive; O1 is a prerequisite for honest evaluation of anything else.

| # | Option | What changes | Status | This repo's? |
|---|---|---|---|---|
| **O0** | **Status quo** — `date_end_only` + `passthrough` | nothing | live | — (the control) |
| **O1** | **Make ADR-049 live** — proportional dasymetric weighting by well-located fatalities | `spatial_distribution_strategy` | **decided, dormant** | **yes** |
| **O1b** | **Pycnophylactic allocation** (`Tobler1979`) — minimise the Dirichlet integral subject to mass preservation, Dirichlet boundary at water via our land mask | a new registry entry | new option, from `Gotway2002`'s ladder | **yes** |
| **O2** | **Temporal allocation, Denton first-difference** (`Denton1971`) — ⚠️ **not** `even_split`, which Denton rejects by name | a new registry entry | undecided | **yes** |
| **O2b** | **Covariate-informed temporal allocation** (`ChowLin1971`) — BLUE with an indicator series; conservation emerges rather than being imposed | a new registry entry | undecided | **yes**, but needs an indicator series |
| **O3** | **Declare, don't allocate** — per-cell-month provenance: concentrated mass, its share, the coarsest contributing precision | new export columns + contract | undecided | **yes** (ADR-009 / ADR-049 §8) |
| **⭐ O7** | **Multiple Spatial Imputation** (`Croicu2026`) — actor-dyad-monthly GP over the precise-event cloud; sample *m* locations per KGI event inside its admin polygon; emit *m* datasets | a new strategy **plus** an *m*-realisation output mode | **new; the measured state of the art** | **boundary question — see below** |
| **O4** | **Drop** — extend `exclude_where_prec` to 5 | profile config | argued against twice over | yes, but no |
| **O5** | **Weighted / scale-invariant scoring** — twCRPS, SCRPS downstream | nothing here | n/a | **no — hydranet's** |
| **O6** | **Intensity-measure target** — evaluate against Λ, never bin | nothing here | n/a | **no — downstream** |

### The boundary cut

This repo's responsibility is **producing data and declaring its provenance** (ADR-009; ADR-014
"viewpoints as derived views"). ADR-049 already drew the line in its *Deferred* section: *"represent
each imprecise event as a distribution over cells rather than a point allocation … belongs in a
downstream transformation or modeling layer, not in the viewpoint."*

Therefore **O5 and O6 are out of scope and must not be built here** — but they are the comparators
any in-scope option must be judged against, and O3 is what makes them *possible* downstream. O3 is
the load-bearing deliverable for #533, and it is provenance, not modelling, so it sits inside the
line ADR-049 drew.

#### ⚠️ O7 puts that line in question, and the question is Simon's

ADR-049 placed sampling treatments downstream: *"represent each imprecise event as a distribution
over cells … belongs in a downstream transformation or modeling layer, not in the viewpoint."*
`Croicu2026` answers the other way — MSI is **data preparation** that consumes the event cloud (this
layer's own input) and emits *m* complete datasets. Both readings are defensible:

- **For "downstream":** MSI fits Gaussian Processes over actor-dyad conflict histories. That is a
  conflict-process model, and ADR-049's deferral reason (c) said so.
- **For "here":** the GP is fitted *to the observed precise events*, not to covariates or forecasts,
  and its output is a dataset, not a prediction. It is the same kind of object as ADR-049's
  proportional weighting — which is *already* accepted at this layer — only with a better estimator
  and *m* draws instead of one.

My reading is that **O7 belongs here and ADR-049's deferral should be amended**, because the
distinction it drew (materialisation vs modelling) does not survive contact with the fact that
ADR-049's own accepted mechanism already estimates a spatial weighting from observed events. But
this is a platform-boundary decision with consequences beyond this repo, so it is **D5 in the
roadmap's decision table, not a conclusion of this document**.

One architectural consequence either way: **emitting *m* realisations is a new output shape.** Every
consumer contract assumes one viewpoint per profile. m=1 already beats centroid placement in 100% of
Croicu's simulations, so a staged path exists — m=1 first, which needs no new output shape at all.

### On O4, and a reason to reject it the ADR did not have

ADR-049 rejected dropping because it loses real deaths. The library now adds two sharper arguments,
and they point the same way.

**First, magnitude.** `Vesco2026_UnderreportedDeathTollWars`: UCDP underreporting is **non-linear in
event size** — ~30% for large events versus >100% for single-fatality ones. **The large aggregates
are the most accurately-counted values in the dataset.**

**Second, and more directly, `Weidmann2015`: counts are substantially more accurate than
locations.** Casualty estimates agree with military records in ~50% of matched events with symmetric
deviations, and remoteness degrades *locational* accuracy without degrading *casualty* accuracy.

So the reliable component of a KGI event is its count, and the unreliable component is its
coordinate. **Dropping the event discards the reliable number because the unreliable one is
unreliable.** O4 should be rejected on this basis and the reason recorded. (`Croicu2026` measures the
cost: list deletion is 34.92% worse in RMSLE than MSI, and attenuates estimated effect sizes in his
Pierskalla–Hollenbach replication.)

### ⭐ And a theorem against O0, which ADR-049 did not have

`Heitjan1991` proves that under **coarsening at random (CAR)** the coarsening mechanism may be
ignored — and that **when data are *not* CAR, ignoring it "leads to severely biased inference"**
(their simulation: estimates over 21 standard errors out).

`Croicu2026` measures that **KGI is non-random**: it correlates with remoteness, reporting quality,
and commonly used predictors of violence.

> KGI is not CAR. `passthrough` and `date_end_only` ignore the coarsening mechanism. Therefore the
> status quo is expected to bias inference severely — not as a matter of degree, but as a
> consequence of a proved result with an empirically verified premise.

This is the strongest argument in the dossier and it shifts the burden: **O0 is not a conservative
default to be displaced by evidence; it is a specification error to be corrected.** What remains
genuinely open is *which* remedy, not whether one is needed.

## 5. How to evaluate — the coarsen-and-recover design

The naive evaluation ("does the forecast improve?") is unavailable to us: it is downstream,
confounded by the model, and circular given that the score itself is the instrument under suspicion.
We need an evaluation **internal to this repo** with a known answer.

**The design.** The dataset contains **343,865 events with `where_prec ≤ 3` and `date_prec ≤ 2`** —
precisely located in space and time — carrying **2,362,552 fatalities, 68.6% of all mass**. Of these,
**334,314 have `adm_1` populated**, which is what the spatial coarsening needs. For this population
the truth is known, and it is large enough to stratify.

1. **Coarsen them synthetically.** Take a well-located event, replace its location with its
   admin-1 (or country) polygon and its date with the enclosing year — manufacturing exactly the
   degradation UCDP applies to summary events.
2. **Run each allocation strategy** on the coarsened version.
3. **Score the recovered allocation against the known truth.**

This is a known-answer test, it needs no new data, and it is the repo's own established idiom (cf.
the synthetic pipeline with gold-standard snapshots, and `scripts/verify_acled_pagination_parity.py`
as the precedent for a measurement script whose output is evidence).

### Metrics, in gate order

| Order | Metric | Role |
|---|---|---|
| 1 | **Conservation**: `Σ allocated == best` | **hard gate** (ADR-040 Invariant 1). A strategy that fails it is invalid, not merely worse. |
| 2 | **Earth-mover distance** between allocated and true cell-month mass | primary endpoint — "did the mass land near where it belonged?" |
| 3 | **Mass-weighted hit rate** at the true cell and within k cells | interpretable secondary |
| 4 | **Slice effective sample size** (hydranet's instrument) and the **CRPS threshold decomposition** (`Gneiting2011`) | does the remedy actually restore a usable instrument, or only move the spike? |
| 5 | **Scale-invariant comparison** (SCRPS-style, `Bolin2023`) | guards against a remedy that looks good only because it shrank magnitudes |

### Controls that must be included or the result is uninterpretable

- **O0 passthrough** — the current behaviour. Any option must beat it.
- **Uniform allocation** — spread evenly over the polygon/window. If proportional weighting cannot
  beat uniform, its extra assumption is unearned. ADR-049's fallback is already uniform, so this
  control is free.
- **Oracle allocation** — allocate using the true distribution. Bounds the achievable gain and tells
  us whether a 2× improvement is near-ceiling or barely started.

### The two confounds this design must declare

**C-a — proxy population.** Coarsened *well-located* events may not resemble genuine summary events.
Genuine summary events are larger, concentrated in active wars, and produced by a different
reporting process. **The evaluation measures allocation skill on a proxy population, and the
transfer to the real population is an assumption, not a result.** Stratifying the coarsening by
event size and conflict intensity is the available mitigation.

**C-b — the ground truth is not ground truth at our resolution.** ⚠️ From `Weidmann2015`, now read
rather than inferred: against military SIGACT records in Afghanistan (N=1,077), **80% of matched
events lie within 50 km of their actual position, 63.4% are referenced to the correct district and a
further 18.6% to a neighbouring one**, and the spatial error is *"roughly of the same order of
magnitude as the size of an administrative district (approximately 50 km)."* Weidmann's explicit
recommendation: **do not operate below ~50×50 km cells or district resolution.** Our cells are 0.5°
≈ 55 km — at the floor, which validates the grid and bounds the exercise. So a `where_prec ≤ 3`
event is *precisely coded*, not *precisely known*, and the "truth" we score against carries error of
about one cell. `Weidmann2013` gives the gradient: ACLED-vs-military correlation 0.68 at
province/month, 0.29 at district/week, 0.15 at cell/three-day. Afghanistan is likely a **lower
bound** on error, given unusually dense coverage.

Three consequences, all of which must be in the pre-registration:

1. **The oracle baseline is not a true ceiling** — it is a ceiling on recovering *the coded
   location*, which is itself noisy.
2. **Metric choice should be tolerant of small displacement.** This is an argument for an
   earth-mover / neighbourhood-tolerant metric over exact-cell hit rate, and the library already
   holds the relevant survey: `Gilleland2009_SpatialVerificationIntercomparison`.
3. **It caps how much skill is worth chasing.** If coded locations are unreliable below district
   scale, an allocation that is right at admin-1 and diffuse within it may be the honest answer
   rather than a weak one — which, note, is also what ADR-049's graceful-degradation rationale
   argues for on entirely separate grounds.

Both confounds belong in the skepticism ledger of any pre-registration.

## 6. Expected ranking — revised 2026-11-04, still a prediction to be tested

The eight acquisitions reordered this. Stated so it can be falsified:

1. **O3 (declare) ships first and alone.** It is what #533 asked for, it is provenance rather than
   modelling, it is independent of every allocation decision, and `Croicu2026` shows the flag is a
   *restoration* of a concept both the legacy loader and the literature already had.
2. **O7 (MSI) is the measured state of the art**, by 34.92% RMSLE over list deletion and 36.30% over
   centroid, with mean point error halved (519 → 275 km). **m=1 is the cheap entry point** — it beats
   centroid in 100% of simulations and needs no new output shape. Subject to decision **D5** on
   whether it belongs in this layer.
3. **O1 then O1b on the spatial axis.** O1 is already decided and dormant, so making it live is the
   lowest-cost improvement available. `Gotway2002` places it on the bottom rung of the overlay
   ladder, with `Tobler1979`'s pycnophylactic surface as the next rung — and Tobler's mass
   preservation is ADR-040 Invariant 1 by construction rather than by assertion.
4. **O2 (Denton first-difference) on the temporal axis**, *not* `even_split`.
5. **O0 is no longer a defensible default** (§4, the CAR argument) but **`production_parity` is
   retained permanently as a contract** — those are different claims and both hold.
6. **O4 rejected** on the Vesco + Weidmann count-vs-location argument.

**What would falsify the ordering.** If proportional weighting (O1) cannot beat uniform allocation on
the coarsen-and-recover harness, ADR-049 needs amending rather than enabling, and the ladder should
be climbed straight to O1b/O7. If MSI's gains do not survive our own data — Croicu's are from Monte
Carlo simulation plus one replication, not from our pipeline — then the cheap options are the right
ones. Neither has been tested here.

**A caution on importing his effect sizes.** Croicu's comparators are centroid imputation and list
deletion. **He does not benchmark ADR-049's proportional weighting**, which is what we would actually
be replacing. The 34.92% is therefore not our expected gain, and quoting it as such would be the
kind of borrowed-number error this dossier exists to avoid.
