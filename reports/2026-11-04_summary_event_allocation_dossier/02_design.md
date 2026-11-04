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

## 3. ⚠️ The blocker: ADR-049 is accepted and not live

`init` found two divergences between the accepted ADR and the code. **Both are governance questions,
not research questions, and both should be resolved before any experiment is designed** — otherwise
this program risks "discovering" a decision that was already taken in June.

### Divergence 1 — the decision is not in effect

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

### Divergence 2 — the ADR's worked example misdescribes the code

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
| **O1** | **Make ADR-049 live** — enable spatial distribution in a non-parity profile | `spatial_distribution_strategy` | **decided, dormant** | **yes** |
| **O2** | **Temporal analog** — spread `date_prec ≥ 4` annual events across their span, conserving | a new registry entry; `even_split` or a benchmarking-style successor | undecided | **yes** |
| **O3** | **Declare, don't allocate** — emit per-cell-month provenance: concentrated mass, its share, and the coarsest contributing precision | new export columns + contract | undecided | **yes** (ADR-009 / ADR-049 §8) |
| **O4** | **Drop** — extend `exclude_where_prec` to 5 | profile config | argued against by ADR-049 | yes, but |
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

### On O4, and a reason to reject it the ADR did not have

ADR-049 rejected dropping because it loses real deaths. The library adds a sharper argument:
`Vesco2026_UnderreportedDeathTollWars` finds UCDP underreporting is **non-linear in event size** —
~30% for large events versus >100% for single-fatality ones. **The large aggregates are the most
accurately-counted values in the dataset.** Dropping or discounting them trades a known allocation
error for a known and larger magnitude error. O4 should be rejected on this basis and the reason
recorded.

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

**C-b — the ground truth is not ground truth at our resolution.** ⚠️ Added 2026-11-04 from
`Weidmann (2015)`, *On the Accuracy of Media-based Conflict Event Data* (JCR 59(6)): benchmarking
UCDP-GED against military SIGACT records in Afghanistan, district-level patterns are captured
reasonably well but **locational accuracy degrades sharply at finer spatial scales**. Our cells are
0.5° (~55 km). So a `where_prec ≤ 3` event is *precisely coded*, not *precisely known*, and the
"truth" we score recovery against carries its own locational error.

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

## 6. Expected ranking — a prediction to be tested, not a conclusion

Stated now so it can be falsified later:

1. **O1 + O3 together.** O1 is already decided and dormant; O3 is what #533 actually asked for and
   is cheap provenance. Expected to dominate because neither requires a new assumption beyond what
   ADR-049 already accepted.
2. **O2**, conditional on beating uniform. The temporal axis carries 17.79% of mass and is the
   *undecided* half, so it has the most genuine research content.
3. **O0** retained permanently as `viewser_parity` — not a failure, a contract.
4. **O4 rejected** on the Vesco underreporting argument.

**The honest caveat:** this ranking is an expectation from a literature survey and one measurement
pass. The point of the harness in `03` and the pre-registration in `05` is to make it refutable.
