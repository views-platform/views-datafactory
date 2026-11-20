# ADR-053: Temporal Distribution of Imprecise UCDP Events (Known Temporal Imprecision)

**Status:** Accepted
**Date:** 2026-11-07 (drafted) · 2026-11-10 (accepted)
**Deciders:** Simon Polichinel von der Maase
**Applies:** ADR-011 (Fail Loud), ADR-014 (Viewpoints as Derived Views), ADR-015 (UCDP Consolidation), ADR-023 (Viewpoint Builder Invariants), ADR-040 (Count Conservation), ADR-049 (Spatial Distribution of Imprecise UCDP Events)

> **This ADR is the temporal twin of ADR-049.** ADR-049 decided what to do when UCDP does not
> know *where* an event happened. This decides what to do when UCDP does not know *when*. The two
> axes are independent, they compose, and until now only one of them had a governing decision.

> **Amended 2026-11-10** — see the *Amendment* section below. The production pipeline now invokes
> `kgi_kti_activity`, which this document deliberately declined to decide; `source_distribution_map`
> is settled; and the three observers *Validation & Monitoring* asked for are implemented. The
> Decision itself is unchanged. Two bullets under *What this ADR does not decide* are superseded in
> place and say so.

---

## Context

The Uppsala Conflict Data Program (UCDP) records armed-conflict deaths as individual events. Its
Georeferenced Event Dataset (GED) encodes temporal uncertainty in the `date_prec` field. Per the
GED codebook:

| `date_prec` | Meaning |
|---|---|
| 1 | Exact date known |
| 2 | Known within 2–6 days |
| 3 | Known within 7–30 days |
| 4 | Known within more than 30 days, but inside one calendar year |
| 5 | Known only within a range longer than a year |

`date_prec >= 4` is therefore UCDP stating, in its own data, **"we do not know which month."**
Writing the codebook semantics down here is deliberate. These values are hardcoded in the pipeline
with no reference to the codebook they come from, so if UCDP ever redefines the precision codes the
pipeline would process the new meaning silently. This ADR does not fix that, but it is the first
governing document to state the mapping its decision depends on.

When UCDP does not know the month, it still has to put the event somewhere, so it reports a
**span** — the window from `date_start` to `date_end` inside which the deaths occurred. The viewpoint
builder then has to choose a single month within that span — or several.

### Current behaviour

The `production_parity` profile sets `source_distribution_map={"annual": "date_end_only"}`. For
annual-source events — which is every finalised GED release — this assigns **one row at the
`date_end` month**, whatever the span. An event covering 2021-01-01 to 2021-12-31 lands wholly in
December 2021.

The consequence is a calendar artifact, and it is measurable. Share of state-based fatalities by
calendar month, over the whole store, built 2026-11-06:

| month | `production_parity` | `kgi_distributed` | `kgi_kti_distributed` | `kgi_kti_activity` |
|---|---:|---:|---:|---:|
| Jan | 6.34 | 6.22 | 8.04 | 8.10 |
| Feb | 7.40 | 6.97 | 8.51 | 8.97 |
| Mar | 7.14 | 7.72 | 8.78 | 8.30 |
| Apr | 7.11 | 6.94 | 7.86 | 7.77 |
| May | 7.43 | 7.19 | 7.73 | 8.20 |
| Jun | 10.69 | 9.57 | 8.80 | 10.24 |
| Jul | 7.05 | 6.82 | 7.53 | 7.01 |
| Aug | 6.66 | 6.48 | 9.49 | 11.30 |
| Sep | 7.42 | 7.14 | 9.17 | 7.25 |
| Oct | 13.33 | 12.00 | 9.48 | 9.02 |
| Nov | 7.16 | 7.35 | 7.44 | 7.22 |
| **Dec** | **12.27** | **15.60** | **7.16** | **6.62** |
| max − min, in percentage points (pp) | 6.99 | 9.38 | 2.33 | 4.68 |

An even year is 8.33%. **December carries 12.27% of all state-based fatalities ever recorded, and
October 13.33%.** This is not a property of conflict. It is a property of where `date_end_only` puts
mass it cannot place.

The mechanism, measured on the `production_parity` output. Events with `date_prec >= 4` account for
522,366 state-based fatalities — **26.7% of the total** — and their `date_end` months are not
uniform:

| `date_end` month | share of `date_prec >= 4` fatalities |
|---|---:|
| Oct | 28.09% |
| Dec | 26.09% |
| Jun | 10.75% |
| all others | ≤ 6.71% each |

Of the December enders, **85.8% start in January** — Jan–Dec annual spans, exactly as expected. Of
the October enders, **88.8% start in August**, which is *not* an annual span: that peak is dominated
by one event, 463137 (121,848 fatalities, Aug–Oct 2022), the second Tigray summary event. So the two
spikes have different causes — December is systematic, October is one event large enough to bend the
whole-history distribution by itself. Both are artifacts of endpoint placement; only one is seasonal.

This matters more than the spatial artifact for one reason: **models learn seasonality.** A spatial
spike is one wrong cell. A calendar spike is a recurring signal with a twelve-month period, present
in every year of the training data, and a forecasting system will fit it.

### The spatial fix alone makes it worse

Measured, not predicted. `kgi_distributed` — ADR-049's recommendation, spatial axis only — moves
December from 12.27% to **15.60%** and widens the annual spread from 6.99 pp to 9.38 pp.

The mechanism: `kgi_distributed` sets `exclude_where_prec=()`, which stops dropping 43,933 events
carrying 785,626 fatalities (+22.6%). Those events are overwhelmingly annual summary events. So the
spatial fix spreads them correctly across space and then stacks every one of them into the same
month. Fixing one axis in isolation amplifies the artifact on the other.

**This is the finding that motivates this ADR.** Shipping ADR-049's recommendation without a
temporal decision would have made the seasonality defect worse while closing the spatial one.

---

## Prior art: the legacy ingestor already decided this

This ADR does not introduce temporal distribution to VIEWS — the Violence & Impact Early Warning
System this data factory feeds. It restores it.

The legacy UCDP ingestor — the system the data factory was built to reproduce (ADR-015) — spread
summary events across their spanned months. Its `fix_summary_events` path detected a summary event
as `best > 0 and span > 1 and best >= span`, then emitted one row per month in the span.
`ceil_split` in `temporal_distribution.py` reproduces it exactly, confirmed hunk by hunk in
`reports/2026-11-04_summary_event_allocation_dossier/08_legacy_gedloader.md`.

So the position that temporally imprecise events should be spread rather than stacked is **not
novel, not this ADR's invention, and already has production precedent in VIEWS.** What this ADR
changes is three defects in how it was done, and one reason it stopped happening:

| | Legacy / `ceil_split` | This ADR |
|---|---|---|
| **Trigger** | `best >= span` — a magnitude proxy. `date_prec` is never consulted. | `date_prec >= 4` and span > 1 — UCDP's own declaration. |
| **Rounding** | `ceil(v/m)` to every month. Sums to **more** than `v`. | Largest-remainder apportionment. Exact. |
| **Weights** | Flat across the span. | Observed monthly activity, with a fallback to flat. |
| **Reached at all?** | **No** — the annual `date_end_only` override preempts it for every finalised release. | Override removed. |

Two of those defects are measured, not inferred:

- **`ceil_split` inflates.** Measured excess across the store is **0.91%**. More sharply: it reports
  **96 deaths across 74 events that appear in no version of the source store** — deaths invented by
  the rounding policy. Both apportioning strategies report zero.
- **The magnitude proxy is protective, not principled.** `best >= span` blocks spreading one death
  over three months, which under `ceil` would become three deaths. It is an undocumented guard
  against the rounding policy. Once the rounder conserves, the guard is unnecessary — and the
  dossier's earlier critique that "temporal imprecision cannot depend on how many people died" is
  **retracted there as measured-wrong**, because the events the proxy misses are a median of
  1 fatality over 3 months.

Of events that genuinely need spreading (`date_prec >= 4` **and** span > 1): **5,487 events,
1,112,848 fatalities, 24.65% of the store's state-based mass.** Detection was never the blocker.
The annual override was.

---

## Decision

### 1. Temporal distribution strategy

For any event where UCDP declares it does not know the month, distribute that event's `best`, `low`
and `high` across the months the event spans, **weighted by the fatalities that well-observed events
in the same conflict recorded in those months**.

The implementation is `activity_weighted` in `temporal_distribution.py`, registered under the name
`activity_weighted`, and the profile that selects it is **`kgi_kti_activity`** in `profiles.py`.

### 2. Trigger on the declared signal, not on a proxy

Distribution triggers when **both** hold:

- `date_prec >= 4` — UCDP states the month is unknown; and
- the span crosses a calendar month boundary.

Both are required. `date_prec >= 4` inside a single month needs no allocation, the month is already
right. A multi-month span with `date_prec <= 3` is a *precisely dated* event straddling a calendar
boundary — a different problem with a different answer, and out of scope here.

Events that do not trigger get one row at their `date_end` month, which is `date_end_only`'s
behaviour. Nothing precisely dated moves.

### 3. Activity weighting, with a cascade and a declared fallback

The indicator `A_e(t)` is total `best` in month `t` over events that are **both well-located and
well-dated** (`where_prec <= 2` and `date_prec <= 2`), restricted to the same conflict as the event
being placed. "Same conflict" descends a most-specific-first cascade, in `CASCADE_KEYS`:

`dyad_new_id` → `conflict_new_id` → `side_b_new_id` → `country_id`

A **dyad** is UCDP's unit for a specific pair of fighting parties — so `dyad_new_id` asks "what was
*this particular pair* doing each month?", and each step down the cascade widens the question when
the narrower one has no observed activity to answer it.

The first level with nonzero activity anywhere in the span wins. **`dyad_new_id` carries 98.6% of
cases.** With no weight map, or zero activity at every level, allocation falls back to
`uniform_span` — **never to flat-on-the-end-month**, because that is the behaviour being replaced.

A month with zero observed activity receives **zero** allocation, by the rounder's
zero-preservation property. This is deliberate — it says "no well-observed fighting here, so do not
invent any" — and it is also **the assumption in this ADR most likely to be wrong**, because absence
of well-observed reporting is not absence of fighting. **1,760 KTI events — events with Known
Temporal Imprecision, meaning the `date_prec >= 4` multi-month-span events this ADR governs — have at
least one zero-activity month inside their span.** Stated here as a known weakness, not hidden in a
docstring.

### 4. Conservation

Allocation goes through `apportion` in `apportionment.py`, which implements largest-remainder
(Hamilton) apportionment over integer totals — the method used to hand out parliamentary seats:
give each month its whole-number share, then award the leftover units to the months with the largest
fractional remainders. The point is that the parts always sum back to the original total. `best`, `low` and `high` are each conserved **exactly**.
This extends ADR-040's count conservation invariant to the temporal dimension, as ADR-049 §5 extended
it to the spatial one.

Rows are emitted only where allocation is nonzero, so output size is bounded by `min(v, span)`
rather than by `span`. One death over three months stays one death.

### 5. Composition with spatial distribution

ADR-049 §4 already fixes the order: **temporal first, then spatial.** Temporal distribution produces
per-month records; spatial distribution then distributes each month's total across cells. Each stage
conserves independently, and each is separately assertable.

`kgi_kti_activity` is therefore `activity_weighted` on the temporal axis composed with
`proportional` on the spatial axis — both axes distributed, which is what the two ADRs together
recommend.

### 6. Default behaviour and the option set

Temporal distribution is **on by default** for events meeting §2's trigger. The alternatives remain
configurable, mirroring ADR-049 §6's framing of one mechanism with several settings:

- **Activity-weighted (recommended):** weight by observed monthly activity. Conserves exactly.
  Introduces a temporal allocation assumption, stated in §3.
- **Uniform (`uniform_span`):** flat across the span. Conserves exactly. The honest floor that any
  weighted strategy must beat before its extra assumption is earned.
- **Endpoint (`date_end_only`):** all mass at `date_end`. Reproduces the behaviour of VIEWSER, the
  legacy VIEWS data service this factory replaces. Creates the
  calendar artifact documented in Context. Not recommended.
- **`ceil_split`:** retained for parity reproduction only. **Does not conserve** — it invents
  fatalities, §Prior art. Should not be selected for new work.

### 7. The annual override is removed

`kgi_kti_activity` sets `source_distribution_map=None`, dropping the
`{"annual": "date_end_only"}` entry that preempts temporal distribution for every finalised GED
release. Without this, §1 through §6 do not run on the data that matters.

**This field is under separate discussion with Håvard** and is named explicitly here so the change
is a decision rather than a side effect of selecting a profile.

### 8. No cross-source dependency

The indicator uses only UCDP's own well-observed events. No other feature source is read. This
matches ADR-049 §7.

### 9. Provenance

Each temporally distributed row carries `_temporal_distributed`, `_temporal_n_months` and
`_temporal_weight_key` — the last naming which cascade level supplied the weights, so an allocation
can be audited back to its indicator.

**These annotations do not currently reach the output parquet.** This is the same defect ADR-049's
2026-11-05 amendment §6 records for the spatial annotations, and the same defect
views-datafactory#533 asks us to close. It is recorded here, not fixed here, so that it is fixed once
and deliberately as that issue's deliverable. This is the **fourth** recorded instance of the
pattern: the legacy loader's `is_summary` flag, event precision lost when events are aggregated to
cell-months (one grid cell in one calendar month — the unit the published data is shaped in),
ADR-049's spatial annotations, and these.

---

## Rationale

### Why activity weighting over uniform

Measured, with each event held out of its own indicator, over 20,000 events whose true month is
known (`scripts/evaluate_temporal_allocation.py`):

| strategy | mean hit share | mean distance |
|---|---:|---:|
| `date_end_only` (parity) | 0.0703 | 5.564 months |
| `uniform_span` | 0.0825 | 4.883 months |
| `activity_weighted` | **0.1525** | **3.305 months** |

Reading the two columns: **hit share** is the fraction of an event's deaths that landed in the month
the event actually happened in — 1.0 would be perfect, 0.0 means none of them did. **Distance** is
how far the allocated deaths sat from that true month, in months, averaged over the event's mass —
so lower is better, and 5.564 means parity's placements were on average more than five months off.

Activity is closer than uniform on 64.9% of events and further on 22.9%.

**The gain is in the mean, not the median.** Median hit share is 0.00 for all three strategies,
because most events are small enough to land wholly in one month and usually the wrong one. So this
helps the typical *fatality*, not the typical *event* — which is the right place for it, since mass
is what concentrates, but it must not be oversold.

### Why uniform is not the answer, despite a flatter year

The seasonality table shows `kgi_kti_distributed` (uniform) at a 2.33 pp annual spread against
activity's 4.68 pp. Flatter is not automatically better. **Uniform smears a year-long war into
twelve identical months, which erases genuine seasonality along with the fake kind.** Real conflict
has seasonality — dry-season offensives, campaign rhythms — and a 2.33 pp spread is flatter than
conflict plausibly is.

Activity's 4.68 pp spread is a shape *borrowed from precisely-dated events in the same conflict*. It
is an estimate with a stated assumption, not a calendar artifact. Replacing an artifact with a
data-driven estimate is the point; replacing it with a flat line is only a different distortion.

### Why both axes, not one

Measured on the Tigray case (event 463131, cell 148759, December 2021) and on the whole store:

| | cell 148759, Dec 2021 | biggest cell that month | its share | month ESS | top cell-month, all history |
|---|---:|---:|---:|---:|---:|
| `production_parity` | 113,395 | 113,395 | 98.1% | 1.04 | 121,915 |
| `kgi_distributed` | 13,865 | 41,645 | 35.8% | 5.75 | 45,887 |
| `kgi_kti_distributed` | 1,180 | 3,470 | 28.0% | 9.05 | 24,979 |
| `kgi_kti_activity` | **240** | **642** | **13.6%** | **20.24** | 39,487 |

**Month ESS** is the effective sample size of that month's spread across grid cells: `1 / Σpᵢ²`,
where `pᵢ` is each cell's share of the month's fatalities. It answers "how many cells is this month's
death toll *effectively* spread over?" — 1.04 means one cell holds essentially all of it, 20.24 means
the mass is spread as evenly as it would be across about twenty cells. Higher is less concentrated.

Across the 13 worst months in
`reports/investigation_summary_event_concentration/findings.md`, the count still above a 70% single-cell
share: **13 under parity, 7 under `kgi_distributed`, 4 under `kgi_kti_distributed`, 5 under
`kgi_kti_activity`.**

Two honest readings of that last row. Activity leaves one more bad month above 70% than uniform, and
its worst single cell-month over all history (39,487) is higher than uniform's (24,979). Both follow
from the same mechanism: activity weighting concentrates mass into months with observed fighting,
which is what makes it accurate on the held-out evaluation and what makes it less flat. The metric
that distinguishes them is not concentration but *correctness of placement*, and on that measure
activity wins by 1.58 months of mean distance.

Not every month is a defect. **February 1999 barely moves under any option** (91.8% → 90.1% → 88.9%
→ 89.2%) — that is genuine concentration, correctly left alone. **March 1993 goes 80.6% → 76.4% →
53.6% → 12.5%**, which is an artifact being removed.

### Why this needs an ADR at all

ADR-023 documents the temporal *mechanism* as a configurable field and pins the parity invariants —
the summary-event formula, `date_end` month assignment. It does not decide which temporal strategy is
**correct**; it records which one matches VIEWSER. ADR-049 governs the spatial axis and explicitly
says the temporal half "remains an open question and is **not** settled by this ADR."

So the temporal axis had a mechanism, a measured evaluation, a registered strategy and a named
profile, and **no governing decision.** ADR-000 requires code and ADRs to agree; there was nothing
to agree with. This closes that gap.

---

## Consequences

### Positive

- **Removes the calendar artifact.** December falls from 12.27% to 6.62%, October from 13.33% to
  9.02%, annual spread from 6.99 pp to 4.68 pp. Spurious twelve-month seasonality is no longer
  present in the training signal.
- **Makes ADR-049 shippable.** The spatial fix in isolation worsens December; composed with this, it
  does not.
- **Conserves exactly**, on all three count fields, and stops inventing the 96 fatalities
  `ceil_split` reports.
- **Recovers 785,626 fatalities** (+22.6%) currently dropped by `exclude_where_prec=(4, 6)`, placing
  them rather than discarding them.
- **Restores legacy intent.** The legacy ingestor spread summary events; the annual override
  silently disabled it. This re-enables it with a conserving rounder and a declared trigger.

### Negative

- **Temporal allocation is a modeling assumption.** Activity weighting assumes imprecisely-dated
  events follow the intensity pattern of precisely-dated events in the same conflict. Defensible,
  and stated — but an assumption, and the whole bet of this ADR.
- **Zero-activity months receive zero.** 1,760 KTI events have at least one such month in their
  span. Absence of well-observed reporting is not absence of fighting (§3).
- **Every published grid-month fatality figure changes** for any event meeting §2's trigger, and the
  ADR-041 content digests are invalidated. Row count goes from 372,303 to 2,654,111 — a **7.1×
  increase** downstream must absorb. Build time goes from 86.6 s to 425.6 s.
- **Breaks VIEWSER parity by construction.** Parity remains reachable via `production_parity`, but a
  model retrained on this data is not trained on what the current production models were trained on.
- **Composition complexity.** Temporal × spatial requires the §5 ordering and independent
  conservation checks at each stage.

---

## Validation & Monitoring

- **Conservation, per event, per field:** `sum(allocated) == original` for `best`, `low` and `high`.
  Covered by `tests/test_apportionment.py` on the rounder's properties and
  `tests/test_activity_weighted.py` on the strategy.
- **Golden test (Tigray):** event 463131's allocation across months 2021-01 to 2021-12 must sum to
  113,368 exactly, be nonzero in more than one month, and leave cell 148759 at December 2021 below
  1,000 when composed with ADR-049's spatial stage.
- **The seasonality guard.** December's share of state-based fatalities must stay below 9.0%. This is
  the observer the artifact lacked: the defect this ADR exists to fix is a *distributional* property
  that no per-event assertion can see. ADR-049's 2026-11-04 amendment records what happens without
  one — cell 148759 grew from 273,076 to 274,358 while nothing went red, because nothing was
  watching. A decision with no observer drifts from its code in silence.
- **Non-triggering events do not move:** an event with `date_prec <= 3` must produce exactly one row,
  at its `date_end` month, under every strategy.
- **Fallback is reached, not assumed:** an event whose every cascade level has zero activity must
  fall to `uniform_span`, and this must be observed rather than argued.
- **Provenance counters** on every build: how many events were temporally distributed, the
  distribution of `_temporal_weight_key` across cascade levels, and how many fell back to uniform.

---

## Deferred

### The zero-activity assumption

§3 gives zero allocation to months with no well-observed activity. A smoothed indicator — a kernel
over neighbouring months, or a floor proportional to the conflict's mean intensity — would weaken the
assumption at the cost of a tuning parameter. Deferred because the held-out evaluation already shows
activity beating uniform without it, so the parameter is not yet earned.

### Precision as published output

The right end state is that a consumer can see *that* a cell-month's figure was allocated rather than
observed, and how diffusely. §9 records that the annotations exist and are dropped at the write.
views-datafactory#533 owns this.

### Distributional treatment

ADR-049's 2026-11-05 amendment admits sampling as a viewpoint concern and declares
`ViewpointConfig.seed` against the first stochastic strategy. The temporal axis inherits that
decision unchanged: a temporal sampler would be admissible under the same terms, and must reject a
`None` seed rather than seed itself. None is built, and none is authorised here.

---

## What this ADR does **not** decide

- **It does not change what the production pipeline invokes.** `scripts/build_viewpoint.py` still
  defaults to `production_parity`, and `scripts/refresh_pipeline.sh` still passes
  `--profile production_parity`. Selecting `kgi_kti_activity` in the pipeline is a separate,
  explicitly gated action. — **Superseded by the Amendment of 2026-11-10 below**, which is that
  separate action. The reasoning above is left standing because it is why the switch needed its
  own decision rather than arriving as a side effect of this one.
- **It does not settle `source_distribution_map`.** §7 states what the profile does and why. The
  field itself is under discussion with Håvard and is not resolved by this document. —
  **Superseded by the Amendment of 2026-11-10 below.** The discussion concluded.
- **It does not retrain or revalidate any model.** Every consumer of this package — 28 views-models
  requirements files — reads data whose grid-month values this changes. Notifying them is a
  precondition of the switch, not a consequence of it.
- **It does not pin the codebook mapping in code.** Context states what the `date_prec` values
  mean; no test asserts it, so a redefinition upstream would still pass unnoticed.

---

## Amendment 2026-11-10 — production invokes `kgi_kti_activity` (#533)

**The Decision above is unchanged.** This amendment records the separate, explicitly gated action
that *What this ADR does not decide* reserved: the production pipeline now builds under
`kgi_kti_activity`, and the `source_distribution_map` question is settled. Dated amendment, not a
rewrite, per the repository's editorial rule.

### 1. What changed, and where

`scripts/refresh_pipeline.sh` names its allocation profile once, in a `VIEWPOINT_PROFILE`
variable, and both the viewpoint build and the UCDP compile step read it. Previously step 3 named
`production_parity` and step 4 inherited `compile_grid.py`'s own default — two literals in two
files that had to agree.

**They did not have to agree, and nothing would have said so.** `build_viewpoint.py` derives its
output path from the profile name when given no explicit output, while `compile_grid.py` defaults
its source to the parity parquet. Changing only the profile would have left the compile step
reading the *previous* profile's output: the UCDP digest would not have moved, ADR-041's
content-addressed skip would have correctly skipped assembly and export, and the run would have
reported success having changed nothing. One variable used twice cannot disagree with itself, and
`test_compile_reads_the_viewpoint_the_pipeline_just_built` fails if either side stops deriving
from it.

`production_parity` remains registered, and `build_viewpoint.py` still defaults to it, so VIEWSER
parity stays reachable by naming it. Parity is a profile, not something lost.

### 2. `source_distribution_map` is settled

§7 and the reservation above both flagged `{"annual": "date_end_only"}` as under discussion with
Håvard. That discussion concluded, and the operator confirmed on 2026-11-10 that the hold is
cleared. `kgi_kti_activity` sets `source_distribution_map=None`, so §1–§6 now run on finalised GED
releases — the data the override had been exempting, and the data that matters.

### 3. What it costs, measured

Measured on the 2026-11-06 consolidated store, state-based unless stated:

| | `production_parity` | `kgi_kti_activity` |
|---|---:|---:|
| cell 148759, December 2021 | **113,395** | **240** |
| that month's largest cell | 113,395 | 642 |
| its share of the month's slice | 98.1% | 13.6% |
| the month's slice ESS | **1.04** | **20.24** |
| event 463131 occupies | 1 cell-month | 12 months × 18 cells |
| deaths above the source ceiling | 96 across 74 events | **0** |
| rows | 372,303 | 2,654,111 (**7.1×**) |
| total `best` | 3,473,358 | 4,258,880 (**+22.6%**) |
| build time | 86.6 s | 425.6 s (136 s warm — see below) |
| build peak RSS | — | **8.19 GiB** |

**The 7.1× row increase does not cost 7.1× the memory, and that is the figure an
operator needs.** Peak RSS for the full build was measured at 8,593,264 KB = **8.19
GiB**, which is within rounding of the 8.6 GB ADR-049's amendment measured for
`kgi_distributed` at 2.41M rows — 10% fewer rows for the same memory. The cost is
dominated by reading the consolidated store and building the two weight maps, not by
the output. On a 16 GB server that leaves roughly 7.8 GB of headroom, so the viewpoint
step carries no OOM risk; C-345's exit-137 trap is not in play here.

Build wall-clock is the one figure that moved on re-measurement: 425.6 s originally,
**136 s** when measured again with the store warm in page cache. The cause was not
isolated and page-cache warmth is a hypothesis, not a finding — both numbers are
recorded rather than one replacing the other, and the larger one is the one to plan
with.

**Cascade levels, measured on the same build** — the distribution the counters in §5
exist to report:

| level | events | share |
|---|---:|---:|
| `dyad_new_id` | 4,112 | 84.7% |
| `side_b_new_id` | 317 | 6.5% |
| `country_id` | 286 | 5.9% |
| `conflict_new_id` | 51 | 1.1% |
| **`uniform_fallback`** | **91** | **1.87%** |

4,857 events were temporally allocated in total. **Activity weighting actually applies
to 98.1% of them**, so the assumption this ADR bets on is doing work rather than
quietly degrading to a flat prior. That 1.87% is the baseline the fallback counter
should be watched against.

The **+785,626** fatalities are 43,933 events readmitted because `exclude_where_prec` drops from
`(4, 6)` to empty. **The switch adds deaths; it does not only move them.** Any consumer diffing
totals sees that before anything else, which is why notifying them was a precondition and not a
consequence.

### 4. Seasonality: the guard passes, and the peak moves rather than vanishes

December's share of state-based fatalities falls from **12.27% to 6.62%**, against the 9.0% ceiling
*Validation & Monitoring* sets. Annual spread narrows from 6.99 to 4.67 percentage points.

**The honest part.** The largest month is no longer October (13.33%) but **August (11.30%, up from
6.66%)**. Most of that is event 463137 — 121,848 deaths recorded 2022-08-24 to 2022-10-24 — moving
to the months where precisely-dated fighting was actually observed. That is the mechanism doing
what §3 says it does: it borrows the shape of well-observed events. It is a different thing from a
calendar artifact, which was an artifact of the *allocation rule* rather than of the data. But
August is now the largest month by a clear margin, and reading the December result as "seasonality
is fixed" claims more than was measured.

### 5. The observers this ADR asked for now exist

*Validation & Monitoring* named three things to watch, and until this amendment none of them was
implemented — no test in the repository referenced this ADR at all, which is the failure shape §
Rationale warns about in its own words.

- The **composed golden criterion** — temporal then spatial, in §5's order — asserts exact
  conservation on `best`, `low` and `high`, that the artifact cell-month falls below 1,000, and
  that both stages marked the rows they produced. Composition is what production runs, and neither
  axis's own tests could catch a composition defect.
- The **December seasonality guard** asserts the 9.0% ceiling, and was demonstrated to fire:
  against a `production_parity` build it reports 12.27% and fails.
- **Provenance counters** on every build: `n_temporally_distributed`,
  `temporal_weight_key_counts` across the cascade levels, and `n_temporal_uniform_fallback`. The
  fallback count is the one worth watching — it is how many events got flat weights after all,
  and a rising share means the assumption this ADR bets on is quietly applying less often.

### 6. What this amendment does **not** decide

- **It does not retrain or revalidate any model.** That bullet above stands unchanged.
- **It does not publish the precision of an allocated value.** §9's defect is untouched: the row
  annotations still do not reach the output parquet, and the served artifact still carries no
  `date_prec`, no `where_prec`, and no marker naming the profile that produced it. A consumer
  cannot distinguish an allocated value from an observed one. That is views-datafactory#533's own
  acceptance criterion and it remains open.
- **It does not settle whether activity weighting is the best allocator**, only that it is better
  than booking a year onto one month. The dossier's coarsen-and-recover evaluator was never built,
  so the comparison against uniform rests on the held-out measurement in §Rationale rather than on
  a standing harness.

---

## References

- ADR-049 — Spatial Distribution of Imprecise UCDP Events; this ADR's twin on the other axis
- ADR-023 — Viewpoint Builder Invariants; the temporal parity invariants this ADR departs from
- ADR-040 — Count Conservation and Hierarchical Reconciliation
- ADR-014 — Viewpoints as Derived Views; versioned coexisting materialisations
- `src/datafactory_viewpoint/temporal_distribution.py` — strategy registry; `uniform_span`,
  `activity_weighted`, `ceil_split`, `date_end_only`
- `src/datafactory_viewpoint/temporal_weights.py` — `build_temporal_weight_map`, `CASCADE_KEYS`
- `src/datafactory_viewpoint/apportionment.py` — `apportion`, the conserving rounder
- `src/datafactory_viewpoint/profiles.py` — `kgi_kti_activity` and the three comparison profiles
- `scripts/evaluate_temporal_allocation.py` — the held-out evaluation in §Rationale
- `notebooks/summary_event_allocation.ipynb` — the measurements in Context and §Rationale, re-runnable
- `reports/2026-11-04_summary_event_allocation_dossier/` — allocator spec (T0/T1/T2), legacy loader
  forensics, literature review
- `reports/investigation_summary_event_concentration/findings.md` — the 13-month catalog
- UCDP GED Codebook — `date_prec` field definitions

---

## Amendment 2026-11-12 — the temporal axis arrived; its reported figures still describe allocation (#547, #556)

**The Decision and the Amendment of 2026-11-10 both stand.** This amendment records a layer
distinction that applies unevenly to the two axes, and that unevenness is the part worth
knowing. Dated amendment, not a rewrite.

### 1. The temporal axis was never affected, and the reason matters

The event compiler reads the month field **by name**: whichever column its configuration names
is the column it bins on, and the production pipeline names the one the temporal allocator
writes. So a month this ADR's allocator chose is a month the grid receives. Every temporal
claim in this ADR held in delivered data, including the recovery of fatality mass that
`production_parity` had been excluding.

The spatial axis did not have that property. ADR-049's allocator records its chosen *cell* by
rewriting a field the compiler re-derived from coordinates, so the spatial decision was
discarded on arrival. See ADR-049's amendment of the same date.

**Two stages, the same shape of decision, opposite outcomes — decided by whether the downstream
stage reads the field or recomputes the quantity.** That is the general lesson, and it is now
governed by ADR-045's amendment of the same date.

### 2. Which of this ADR's figures are allocation figures

Those measured by grouping on `priogrid_gid` — the per-cell and cell-month numbers, including
the Tigray cell-month in §Validation & Monitoring. Those are allocator output. The per-month
and per-month-share figures, including December's share of state-based fatalities, are
delivered figures, because the month axis survived.

The delivered values are in `reports/investigation_allocation_delivery/findings.md`.

### 3. A pre-registration failure this ADR's amendment had already anticipated

The 2026-11-10 amendment recorded the mechanism plainly: activity weighting moves mass toward
months with observed fighting, so *"the event's own peak cell-month rises"* — from 3,471 under
uniform spreading to 11,732 under activity weighting. A later verification nonetheless
pre-registered *"worst delivered cell-month below 5,000"*, a target correct behaviour cannot
reach, and graded a release against it.

Two consequences recorded here because this ADR is where the mechanism lives:

- **A bound below a value the chosen method is known to produce is not a falsifier.** It
  manufactures a failure, and the usual repair is to widen it afterwards, which is the one thing
  pre-registration exists to prevent. The replacement is an equality: delivery must reproduce
  the allocation.
- **Do not pre-register the single slice the previous defect concentrated in.** December 2021
  was chosen as the test month because the old pipeline dumped everything there. After temporal
  spreading December is the *second lowest* of the twelve months in that cell, so the check
  reported a 64× improvement where the worst month across the span had improved 3.5×. A factor
  of 18, entirely from the choice of slice.

### 4. What this amendment does not change

The `date_prec` semantics, the activity-weighted cascade, the uniform fallback, the profile
production invokes, and the seasonality guard are all untouched. This amendment is about what
the ADR's numbers mean and where a future number must be read.
