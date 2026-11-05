# 11 — Allocator specification: math, pseudocode, guards

**Date:** 2026-11-05 · **Status:** spec, ready to implement
**Purpose:** working tools that distribute summary events in time and space, conserving mass, inside
the datafactory's existing rules. Not a research agenda.

---

## 1. The problem, stated once

An event `e` carries an extensive count `v_e` (fatalities; likewise `v_lo`, `v_hi`) that the source
declares to be imprecise in time, space, or both. We must emit non-negative integers on cell-months.

Let

- `T_e = {t_0, …, t_{m-1}}` — the months the event spans, `m = span`
- `S_e = {c_1, …, c_k}` — the cells of the event's target polygon, `k = |S_e|`

**Required:** an allocation `a_e : T_e × S_e → ℤ≥0` with

```
    Σ_{t∈T_e} Σ_{c∈S_e}  a_e(t,c)  =  v_e          (exactly; ADR-040 Invariant 1)
```

## 1b. ⭐ Three declared signals, with three different jobs

UCDP declares its own limits in **three** fields. We were using two, partially, and the third
carries the most mass.

| field | question it answers | share of all fatality mass |
|---|---|---:|
| `where_prec` | do we know **where**? (KGI) | `>=4`: 32.88% |
| `date_prec` | do we know **when**? (KTI) | `>=4` & span>1: 24.65% |
| **`event_clarity`** | **is the count one incident, or an aggregate?** | `==2`: **45.56%** |

`event_clarity == 2` is UCDP saying *the reported figure aggregates several incidents*. Crossing it
with precision gives four categories, and the distinction is the one magnitude cannot make:

| | `clarity=2` (aggregated count) | `clarity=1` (single incident) |
|---|---|---|
| **imprecise** (KGI or KTI) | **A — 19,315 ev / 36.41% of mass** | **C — 57,249 ev / 9.21%** |
| **precise** | **B — 14,163 ev / 9.17%** | D — 350,686 ev / 45.20% |

**A** is the artefact class. All four worked examples sit here — `463131` (Tigray, 113,368),
`463137` (121,848), `34362` (48,183), `445207` (40,000) — each `where_prec=5`, `date_prec` 4–5,
`clarity=2`.

**B is real and must never be touched:**

```
40,000  wp=1 dp=2 clarity=2   Murambi Sector - Principal Murambi site
24,173  wp=2 dp=2 clarity=2   El Fasher and along exit routes
18,600  wp=1 dp=2 clarity=2   Cyahinda town (Catholic church in)
```

Forty thousand deaths at one memorial site in April 1994, location known **exactly**. The count
aggregates incidents *at the same place and time*; there is nothing to redistribute.

### ⚠️ Correcting a first reading: clarity is NOT an allocation gate

An earlier draft of this said allocation should be "gated on category A". That is wrong, and the
right statement is cleaner:

- **Allocation is triggered by *imprecision* alone** — `where_prec` for space, `date_prec` for time.
  So **A and C are both allocated** (C is a single incident we cannot place), and **B and D are
  not**. The existing precision gates already do this: `proportional` returns the event unchanged
  for `where_prec < 4`, and a span-1 event has only one month to go to.
- **`event_clarity` adds nothing to the allocation decision and everything to the declaration.** It
  explains concentration that allocation *cannot and should not* remove.

So `event_clarity` belongs to **O3**, not to the allocator — making O3's deliverable **three fields
plus a derived category**. That category is what lets a consumer tell *"113,395 because we dumped a
three-region annual aggregate on one cell"* from *"40,000 because 40,000 people died at that site"*.
views-hydranet and views-models each independently refused to winsorise on magnitude; this is the
field that vindicates them, and it is already harvested.

---

## 2. The design move: one rounder, many weight functions

Every option below is **a choice of weight function composed with a single shared integer rounder**:

```
    a_e = LRM( v_e , w_e )          where     w_e(t,c) = τ_e(t) · σ_e(c)
                                              Σ_{t,c} w_e(t,c) = 1
```

This factorisation is the whole design. It means:

- conservation is proved **once**, in the rounder, not re-argued per strategy;
- a new allocation idea is a new `τ` or `σ` — registered through the existing
  `datafactory_provenance.registry.Registry` seam, no builder change (OCP);
- the temporal and spatial axes compose by multiplication rather than by sequential re-rounding.

⚠️ **Separability is a stated modelling assumption**: `w(t,c) = τ(t)·σ(c)` asserts that *when* and
*where* are independent given the event. That is false in general — fighting moves — but it is the
weakest assumption that does not require a conflict-process model, and it is the one that makes the
result testable. Any violation is a known, declared limitation, not a hidden one.

**It also improves on ADR-049 §4.** That section prescribes temporal-then-spatial with independent
conservation at each stage — i.e. two rounding steps. The product form rounds **once** over the
`m × k` grid: strictly less rounding loss, one conservation check instead of two.

---

## 3. The rounder: largest-remainder (Hamilton) apportionment

```
LRM(v, w):                                  # v ∈ ℤ≥0,  w_i ≥ 0,  Σ w_i = 1,  n = |w|
    q_i   ← v · w_i                         # ideal real share
    f_i   ← floor(q_i)
    r     ← v − Σ f_i                       # integer, 0 ≤ r ≤ n−1
    order ← indices sorted by (q_i − f_i) descending,
                            then by a deterministic key ascending   # (month, cell)
    a_i   ← f_i + 1   for the first r indices of `order`
    a_i   ← f_i       otherwise
    return a
```

### Properties — each one is a test

| | property | statement |
|---|---|---|
| **P1** | **Conservation** | `Σ a_i = Σ f_i + r = v`, exactly, for all `v`, `w`. |
| **P2** | **Boundedness** | `a_i ∈ {floor(q_i), ceil(q_i)}` — no cell-month deviates from its ideal share by 1 or more. |
| **P3** | **Determinism** | identical input ⇒ identical output. Satisfies ADR-014 Principle 3 with **no seed required**; these allocators are pure. |
| **P4** | **Zero-preservation** | `w_i = 0 ⇒ a_i = 0`. *Proof:* a zero weight gives remainder exactly 0, which sorts last. And `r = Σ(q_i − f_i)` is a sum of `n` values each `< 1`, so `r ≤ #{i : q_i − f_i > 0}`. The `r` units are therefore exhausted on strictly-positive remainders before any zero is reached. ∎ |
| **P5** | **Order preservation** | for fixed support, `w_i ≥ w_j ⇒ a_i ≥ a_j`. |

**P4 is the one that matters substantively**: a month or cell with no supporting evidence never
receives mass. It is what makes "weight by observed activity" honest rather than smearing.

**P2 replaces `ceil_split`.** `ceil` assigns `ceil(v/m)` to *every* month, so `Σ a = m·ceil(v/m) ≥ v`
— the measured 0.91% inflation. LRM cannot inflate, by P1.

### The `v < n` regime, which is where the surprises live

When `v_e < m·k`, LRM gives 1 to the `v_e` highest-weighted cell-months and **0 to the rest**. This is
correct and is the opposite of `ceil`'s behaviour, which would have inflated a 1-death event over 3
months into 3 deaths. It also bounds output size:

```
    nonzero rows per event  =  min( v_e , m · k )
```

⚠️ **Current `proportional` does not do this** — it emits a row for every weighted cell regardless of
whether that cell received anything, so a 1-fatality event over an 18-cell polygon emits 18 rows, 17
of them zero. That is a large part of why the `kgi_distributed` build produced 2,414,552 rows against
parity's 372,303. **Emitting only nonzero rows is a required part of this spec.**

---

## 4. Temporal weights `τ_e`

| id | name | definition | notes |
|---|---|---|---|
| **T0** | `endpoint` | `τ(t) = 1[t = t_{m-1}]` | **parity**. Reproduces `date_end_only`. The control. |
| **T1** | `uniform` | `τ(t) = 1/m` | no indicator assumed. |
| **T2** | `activity` | `τ(t) ∝ A_e(t)` | weight by observed monthly activity; cascade below. |

**T2's indicator.** `A_e(t)` = total `best` over events that are **well-located and well-dated**
(`where_prec ≤ 2` and `date_prec ≤ 2`) and share `e`'s actor dyad, in month `t`.

Cascade, each level used only if the one above sums to zero over the span:

```
    A_e(t)  ←  dyad activity        (3,904 distinct; coverage 86.8% of KTI events)
            ←  conflict activity    (3,319 distinct)
            ←  side_b activity      (1,994 distinct)
            ←  country activity     (154 distinct; coverage 97.8%)
            ←  uniform, i.e. fall back to T1
```

All five keys are non-null for every KGI event, so the cascade cannot fail for want of an
identifier. The two middle rungs were missing from the first draft: they sit between dyad and
country in granularity and should be preferred over dropping straight to a 154-key aggregate.

**On T1 versus Denton (1971).** Denton rejects the identity-matrix penalty because it introduces
spurious year-boundary discontinuities *when adjusting an existing sub-annual series to annual
totals*. We have no preliminary series: for a single event with no indicator, Denton's
first-difference penalty with constant `z` **reduces to the uniform allocation**. So T1 is the
correct no-indicator baseline and Denton's objection does not bite here. **T2 is the Chow–Lin case** —
allocation by a correlated indicator series — and that is where Denton/Chow–Lin genuinely applies.
*(This corrects an earlier claim in `02 §4` that `even_split` was "rejected by name".)*

## 5. Spatial weights `σ_e`

| id | name | definition | notes |
|---|---|---|---|
| **S0** | `centroid` | `σ(c) = 1[c = c_0]` | **parity**. Reproduces `passthrough`. The control. |
| **S1** | `uniform` | `σ(c) = 1/k` | ADR-049's existing fallback, promoted to an option in its own right so it can be the honest control for S2. |
| **S2** | `fatality` | `σ(c) ∝ W_e(c)` | = existing `proportional`. `W_e(c)` = well-located fatalities in cell `c` within the target polygon. Dasymetric mapping with fatalities as the ancillary surface. |

| **S3** | `declared_support` | polygon set from the event's **own** `adm_1` / `where_description` rather than from its centroid | **new; see below** |

Target polygon for S1/S2 per ADR-049 §2: admin-1 for `where_prec` 4–5, country for `≥ 6`, via the
GAUL crosswalks — i.e. derived from **the centroid cell**, deliberately avoiding free-text matching.

### ⚠️ S3: the support may be wrong, not just the weights

ADR-049 §2 takes the polygon from the centroid's admin-1. The events themselves say otherwise:

```
113,368   where_description = "Tigray, Afar, Amhara"                           <- THREE regions
 79,456   where_description = "Northern Amhara, western-most Afar and Tigray"  <- THREE regions
 30,000   where_description = "Badme and the strip Ethiopia holds to the west..."
```

**We spread a three-region event over one region.** `adm_1` is populated for 83.7% of KGI events but
is `None` for exactly these highest-mass ones, where the information sits in `where_description`.
20.7% of KGI mass has a comma-separated `where_description`.

**This is a candidate explanation for the residual.** `kgi_only` cut cell 148759 by 7× all-history
yet left the largest state-based cell at month 504 at 41,645 (~36% of the month). If the true support
is roughly 3× wider than the polygon we use, that is the residual you would predict.

Cost: name matching against GAUL, which ADR-049 avoided for good reason — fragile and
locale-dependent. **Treat S3 as a hypothesis to test on the top-mass events only**, where the payoff
is concentrated and the strings can be checked by hand, not as a general parser.

## 6. Guards — fail loud, never silently clamp (ADR-011)

| condition | behaviour |
|---|---|
| `v_e = 0` | emit a single row at `(t_{m-1}, c_0)` with 0. Preserves the event's existence without inventing mass. |
| polygon undeterminable (water / unassigned centroid) | passthrough; log; increment `n_passthrough_where_prec`. |
| `k = 0` | as above. |
| `Σ_t A_e(t) = 0` | descend the T2 cascade; if all levels are zero, use T1. |
| `Σ_c W_e(c) = 0` | use S1. ADR-049 §3 already specifies this. |
| `v_e` not a non-negative integer | **raise**. |
| any weight NaN, `inf`, or negative | **raise**. Do not normalise away. |
| `Σ w = 0` after cascade | **raise** — reaching here means the cascade is misconfigured. |

Provenance per row (ADR-049 §8, currently computed and dropped — see `08`): source event id, `τ`
and `σ` names, polygon code, `m`, `k`, and the count of nonzero rows emitted.

---

## 7. The option set, named

Nine combinations; four matter.

| | **S0 centroid** | **S1 uniform** | **S2 fatality** |
|---|---|---|---|
| **T0 endpoint** | **`parity`** — today's behaviour, the control | — | `kgi_only` — ADR-049 as currently built |
| **T1 uniform** | `kti_only` | `both_uniform` — the honest floor | — |
| **T2 activity** | — | — | **`both_activity`** — the proposal |

**To test:** `parity` (control) · `kgi_only` (ADR-049 alone) · `both_uniform` (the floor any weighting
must beat) · `both_activity` (the proposal). The others exist for ablation.

---

## 8. Test plan — three tiers, cheapest first

### Tier 1 — properties of the rounder. Minutes, decisive, no data needed.
Exhaustive over `v ∈ [0, 50]` × all weight vectors on `n ≤ 5` from a coarse simplex grid, then
randomised for large `v`, `n`. Assert **P1–P5** directly. Plus a mutation drill: break the remainder
step and confirm P1 goes red.

### Tier 2 — known-answer recovery. Hours.
Take events that are **well-located and well-dated** (`where_prec ≤ 2`, `date_prec ≤ 2`), coarsen
them synthetically to `(admin-1 or country) × year`, allocate with each of the four strategies, and
score the recovery against the known truth.

**Primary endpoint:** earth-mover distance on the cell-month grid against `both_uniform`.
**Hard gate:** exact conservation on every event.
**Stratify** by event magnitude and by span, because the `v < m·k` regime behaves qualitatively
differently and pooling would hide it.

### Tier 3 — surprise hunt. Pre-named, because unnamed surprises get rationalised.
1. **Row count.** Does `min(v, m·k)` hold, and what is the real total against parity's 372,303?
2. **The sparse regime.** For `v < m·k`, allocation is a *subset selection*, not a spread. Does EMD
   even mean what we want there?
3. **Zero months.** 1,760 KTI events have at least one zero-activity month inside their span. T2 puts
   0 there by P4. Correct, or over-confident?
4. **Does T2 beat T1 at all?** If not, the activity indicator earns nothing and T1 is the answer.
5. **Does the spike move rather than shrink?** Measured already for `kgi_only`: cell 148759 falls
   7× all-history, yet the largest state-based cell at month 504 is still 41,645 (~36% of it).

---

## 9. What this spec deliberately excludes

- **Gaussian-process / MSI sampling (`Croicu2026`).** Admissible per ADR-049's 2026-11-05 amendment,
  and out of scope here: it needs 15,722 fitted models and a seed contract. T2 is its deterministic
  shadow — same idea, observed activity instead of a fitted field, no sampling.
- **Pycnophylactic interpolation (`Tobler1979`).** The next rung; needs a smoothness solver.
- **Changing what production invokes.** These land in profiles. `production_parity` stays
  byte-identical and remains what the pipeline runs.
- **Victim-type decomposition.** `deaths_a + deaths_b + deaths_civilians + deaths_unknown == best`
  for **100%** of KGI events, so an exact four-way split is available, and civilian deaths plausibly
  distribute differently from battle deaths. Excluded because it needs a *differential* weighting
  surface per victim type: the well-located cloud would have to be split the same way, which is a
  modelling question rather than an allocation one. Recorded because the decomposition being exact
  is the precondition, and it holds.
