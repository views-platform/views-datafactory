# Catalog: UCDP summary events concentrated by measurement

**Date:** 2026-11-04
**Source data:** `data/viewpoint/production_parity.parquet` (local viewpoint build dated
2026-06-01), 372,303 distributed event-rows / 372,058 events, `date_month` 1989-01 … 2026-04.
**Profile:** `production_parity` — survivorship `dot9_wins`, `distribution_strategy="ceil_split"`,
`source_distribution_map={"annual": "date_end_only"}`, `spatial_distribution_strategy="passthrough"`,
`exclude_where_prec=(4, 6)`.
**Prompted by:** views-datafactory#533 (views-hydranet), extending #484.
**Status:** measurement only. No configuration, code or data was changed.

---

## The thing to read if you read nothing else

**21,766 events (5.8% of all events) carry 21.95% of all UCDP fatality mass, and every one of them
is assigned to a single cell-month that its own metadata says it is not resolved to.**

The concentration is itself extremely concentrated. **Ten cell-months hold 431,802 fatalities —
12.4% of all mass in the dataset.** A single 0.5° cell at 13.25°N 39.25°E (`priogrid_gid 148759`,
the Tigray/Amhara border, Ethiopia) holds **270,688 — 7.79% of every fatality UCDP records,
1989–2026** — delivered in ten events across eight months.

And the problem is worst exactly where models are evaluated: **in 2020–2024, 48.8% of all fatality
mass is concentrated by measurement.** Not 5%. Nearly half.

This is not a data defect. Every one of these events is a true total, correctly recorded by UCDP
with honest precision metadata. The concentration is produced by our own distribution policy, which
reproduces VIEWSER `GedLoader` parity deliberately.

---

## The instrument

An event is **concentrated by measurement** when it lands wholly in one cell-month while its own
UCDP precision fields declare it is not resolved to that cell-month. Two independent mechanisms,
both reachable from the production profile:

| flag | definition | mechanism | events | mass | share |
|---|---|---|---:|---:|---:|
| **T** temporal | `date_prec >= 4` (month or coarser) **and** `span_months > 1` **and** not spread | `date_end_only` assigns annual-source events to their `date_end` month "regardless of whether the event spans multiple months" (its own docstring) | 3,315 | 618,082 | 17.79% |
| **S** spatial | `where_prec >= 5` (country-level or unclear) | `passthrough` returns the event unchanged whatever its `where_prec`; the profile excludes only `where_prec` 4 and 6, so 5 and 7 pass through onto a single cell | 18,908 | 533,950 | 15.37% |
| **T+S** both | the severe class | both at once | **457** | **389,571** | **11.22%** |
| either | | | 21,766 | 762,461 | 21.95% |

Note the asymmetry: **457 events — 0.12% of the dataset — carry 11.22% of its mass.**

Only **181 events in the entire dataset are ever spread across months.** `ceil_split` reaches
only non-annual sources, and its detection test (`best > 0 and span > 1 month and best >= span`)
is further narrowed by the annual override. Of 2,333 events UCDP itself flags `date_prec == 5`,
almost none are redistributed.

Cell-months touched: **13,848 of 135,146 (10.25%)** — but those cell-months hold **36.77% of all
mass**.

---

## Tier A — the catalog: ten cell-months that dominate their own slice

`ESS` is the participation ratio `(Σc)²/Σc²` over per-cell values within a (violence type, month)
slice: it equals the cell count when every cell contributes equally, and 1 when one cell carries
everything. `ESS→excl` is the same with the single largest cell removed.

| # | month | cell | lat/lon | type | mass | % of slice | ESS → excl | event(s) | conflict |
|---|---|---|---|---|---:|---:|---|---|---|
| 1 | **2022-10** (514) | 148759 | 13.25N 39.25E | sb | **121,915** | 94.7% | 1.11 → 12.70 (**11.4×**) | `463137` (121,848) | Ethiopia: Government |
| 2 | **2021-12** (504) | 148759 | 13.25N 39.25E | sb | **113,395** | 98.1% | 1.04 → 29.86 (**28.7×**) | `463131` (113,368) | Ethiopia: Government — TPLF |
| 3 | **2000-06** (246) | 150919 | 14.75N 39.25E | sb | **48,183** | 94.7% | — | `34362` (48,183) | Eritrea – Ethiopia |
| 4 | **2025-10** (550) | 149451 | 13.75N 25.25E | os | **41,249** | 96.9% | 1.07 → 10.55 (**9.9×**) | — | **this is #484's cell** |
| 5 | **1994-05** (173) | 125700 | 2.75S 29.75E | os | **40,589** | 46.6% | — | `445207` (40,000) | Rwanda – Civilians |
| 6 | **1999-06** (234) | 150919 | 14.75N 39.25E | sb | **30,000** | 95.7% | 1.09 → 22.87 (**21.0×**) | `34346` (30,000) | Eritrea – Ethiopia |
| 7 | **2022-09** (513) | 148759 | 13.25N 39.25E | sb | **20,016** | 76.5% | 1.70 → 16.57 (**9.7×**) | `449986` (20,000) | Ethiopia: Government |
| 8 | **2022-05** (509) | 197716 | 47.25N 37.75E | sb | **16,539** | 80.6% | 1.54 → 19.60 (**12.8×**) | `438282` (15,996) | Russia – Ukraine (Mariupol) |
| 9 | **2022-11** (515) | 148759 | 13.25N 39.25E | sb | **15,372** | 67.2% | — | `510098` (15,372) | Ethiopia: Government |
| 10 | **1994-05** (173) | 127141 | — | os | **13,700** | 15.7% | — | `298498` (13,645) | Rwanda – Civilians |

### The worst single entry is one nobody has reported yet

**Event `463137`: 121,848 fatalities**, `date_start 2022-08-24` → `date_end 2022-10-24`,
`date_prec 5`, `where_prec 5`, assigned entirely to cell 148759 in **October 2022 (month 514)**.
It is **8% larger than the event in #533** and accounts for **94.7% of all state-based fatalities
recorded anywhere on earth that month**. views-hydranet's scored window ends at month 504, so their
instrument could not see it.

### The anchor case, fully resolved (#533)

**Event `463131`: 113,368 fatalities**, `date_start 2021-01-01` → `date_end 2021-12-31` — the entire
year — `date_prec 5`, `where_prec 5`, `where_description "Tigray, Afar, Amhara"` (three Ethiopian
regions). Assigned to one 0.5° cell in December 2021. Its three cell-mates that month total 27.

**Correction to #533:** this is **Ethiopia / Tigray, not Darfur**. views-hydranet inferred Darfur by
analogy with #484. The mechanism is identical; the conflict is a different war. #484's cell
(`149451`, 13.75N 25.25E) *is* North Darfur and *is* confirmed severe — entry 5 above.

---

## Tier B — repeat-offender cells

A cell that concentrates mass repeatedly is worse than a one-off spike: a model can learn the cell
identity as a predictor, and a spatially-structured improvement elsewhere cannot register against it.

| cell | lat/lon | conc. mass | % of ALL mass | events | months | where |
|---|---|---:|---:|---:|---:|---|
| **148759** | 13.25N 39.25E | **270,688** | **7.79%** | 10 | 8 | Tigray/Amhara, Ethiopia |
| **150919** | 14.75N 39.25E | 78,183 | 2.25% | 3 | 3 | Eritrea–Ethiopia border |
| **125700** | 2.75S 29.75E | 49,527 | 1.43% | 28 | 6 | Rwanda/Burundi |
| 197716 | 47.25N 37.75E | 24,012 | 0.69% | 11 | 5 | Mariupol, Ukraine |
| 127141 | — | 21,610 | 0.62% | 11 | 4 | Kigali, Rwanda |
| 126421 | — | 15,767 | 0.45% | 8 | 4 | Rwanda/Burundi |
| 199156 | — | 12,768 | 0.37% | 10 | 8 | Avdiivka, Ukraine |
| 187654 | — | 7,428 | 0.21% | **159** | **78** | Nagorno-Karabakh |
| 137227 | — | 5,296 | 0.15% | **79** | **58** | Southern Sudan |

The last two are a different shape worth naming: not one giant event but *persistent* low-grade
concentration — 159 events over 78 months. These will not show up in any top-N-by-magnitude scan,
and a magnitude threshold would never catch them.

---

## Tier C — conflict clusters

| country | conflict | conc. mass | % of all | n | span |
|---|---|---:|---:|---:|---|
| Ethiopia | Ethiopia: Government | **276,317** | **7.96%** | 142 | 1990-06 … 2026-01 |
| Rwanda | Government of Rwanda – Civilians | **106,283** | **3.06%** | 182 | 1991-02 … 1997-07 |
| Ethiopia | Eritrea – Ethiopia | 78,183 | 2.25% | 2 | 1999-06 … 2000-06 |
| Ukraine | Russia – Ukraine | 50,526 | 1.45% | **1,893** | 2022-02 … 2026-03 |
| Afghanistan | Afghanistan: Government | 13,798 | 0.40% | 557 | 1989-02 … 2021-09 |
| Sudan | Sudan: Government | 11,104 | 0.32% | 219 | 1989-10 … 2026-03 |
| Azerbaijan | Nagorno-Karabakh | 9,739 | 0.28% | 363 | 1991-12 … 2023-09 |
| Syria | Syria: Government | 5,905 | 0.17% | **1,736** | 2011-10 … 2024-12 |

Ukraine and Syria are the many-small-events pattern; Ethiopia and the Eritrea–Ethiopia war are the
few-enormous-events pattern. **A remedy aimed only at outliers fixes Ethiopia and misses Ukraine.**

---

## When: the problem is worst in the evaluation era

| period | concentrated | all mass | share |
|---|---:|---:|---:|
| 1985–89 | 11,520 | 51,228 | 22.5% |
| 1990–94 | 162,202 | 1,060,083 | 15.3% |
| 1995–99 | 74,856 | 321,167 | 23.3% |
| 2000–04 | 67,440 | 222,250 | 30.3% |
| 2005–09 | 13,008 | 144,051 | 9.0% |
| 2010–14 | 17,400 | 315,191 | 5.5% |
| 2015–19 | 35,465 | 414,443 | 8.6% |
| **2020–24** | **369,041** | **756,549** | **48.8%** |
| 2025– | 11,529 | 188,396 | 6.1% |

The 2020–24 figure is the one that matters operationally: it is the window most training and
evaluation splits draw on, and **nearly half its fatality mass is in the wrong place, the wrong
month, or both.**

---

## Why this damages evaluation and training differently

**Evaluation.** CRPS is in count units, so each cell's contribution to the score scales with its
magnitude. When one cell holds 94–98% of a slice's mass, the slice's effective sample size collapses
to ~1: the score is a measurement of one number. A model change that improves hundreds of thousands
of cells produces no visible movement, and *"no effect"* becomes indistinguishable from *"the
instrument cannot see it."* views-hydranet has already paid a day for this, establishing that a
flat CRPS reading on an arm that improved spatial structure on 5/5 seeds was the instrument.

**Training.** The same cell-months are a worse problem, and a quieter one. A model fitting
`113,368` at 13.25N 39.25E in December 2021 is fitting an artifact of assignment. It has two options
and both are bad: learn the spike (and carry a spurious death-sink at that cell identity), or treat
it as noise (and lose the real 113,368 deaths that did occur, somewhere in three regions across
twelve months). Tier B's repeat offenders make the first failure mode more likely, because the cell
recurs with the same signature.

---

## Negative results — things I checked that are clean

- **`date_prec == 5` with `span_months == 1`: zero events.** No year-precision value is pinned to a
  single-month date range. Had there been any, they would have been invisible to a span-based test.
- **`where_prec` 4 and 6 are correctly excluded** by the profile, as configured.
- **Survivorship is working.** 372,058 unique event ids over 372,303 rows; the excess is month
  spreading, not duplicate versions.
- **No evidence of a data-quality fault in UCDP.** Every event examined carries honest precision
  metadata. The information needed to handle these correctly is present in the store and is
  retained through the builder (`src/datafactory_viewpoint/builders/ucdp_v1.py:60-62`).

**One non-conservation to record:** mass over rows (3,473,358) exceeds mass over events (3,441,686)
by **31,672 (0.91% of the row total)**. That is `ceil_split` rounding up per month — documented in its docstring
(`best=7` over 3 months → 9). It affects only the 181 spread events, but it means totals are not
conserved today, which matters for any remedy that claims to conserve them.

---

## Catalog files

- **`catalog_concentrated_events.csv`** — 21,766 rows, one per concentrated event, with `lat`/`lon`,
  flags, precision fields, `span_months`, cell-month total, the event's share of its cell-month, and
  its cell-month's share of the month. Sorted by mass.
- **`catalog_severe_cell_months.csv`** — 13,848 rows, one per affected (type, month, cell), with
  concentrated mass, the slice's ESS with and without its top cell, and whether this cell *is* that
  top cell.

Severity bands, cell-months by concentrated mass: ≥10,000 → 10 cells (431,802 mass) · ≥1,000 → 63
(558,889) · ≥100 → 456 (663,350) · ≥10 → 3,079 (737,670) · ≥1 → 11,575 (762,461).

**The ten-row head of that distribution is 57% of the total concentrated mass.** A remedy that
addressed only Tier A would recover more than half the damage.

---

## Caveats, stated plainly

1. **The basis is a local viewpoint build dated 2026-06-01, covering data through 2026-04.** The
   production server's current build is newer. Events after 2026-04 are not in this catalog, and
   the figures should be re-measured against the deployed build before anyone cites them as current.
2. **Leverage is proxied by `best`, not measured on model scores.** This is sound for a
   count-unit CRPS, and views-hydranet reports the directly measured figure is the same order, but
   it is a proxy. The ESS figures here are computed on truth, not on per-cell scores.
3. **No causal claim about any model's performance.** This catalog says the instrument is
   degenerate on these slices. It does not say any particular reading was wrong.
4. **I did not change the distribution policy, and this catalog does not recommend one.**
   `source_distribution_map={"annual": "date_end_only"}` is the production-parity contract and sits
   formally with Håvard. Changing it would move every published fatality figure.

## What exists already, if a policy decision is ever taken

`src/datafactory_viewpoint/temporal_distribution.py` already registers and tests `even_split`
(spreads `date_prec == 5` evenly across the spanned months, **conserving the total**), `ceil_split`
(does not conserve — rounds up), `floor_split`, and `date_end_only`. The spatial side has
`passthrough` plus the `where_prec >= 4` polygon machinery in
`src/datafactory_viewpoint/spatial_distribution.py`, currently unused by the production profile.

**The capability is built. What is missing is a decision and a per-cell-month flag on the export.**
Precision is an event-level attribute consumed during distribution and then destroyed by
aggregation to cell-months, so no downstream consumer can currently distinguish a real massacre from
a reporting artifact without re-deriving it from this store.

---

## Reproduction

```
uv run python scripts/investigate_summary_event_concentration.py
```

Every figure in this document is printed by that script, which also writes the two CSVs. It takes
well under a minute and needs only `data/viewpoint/production_parity.parquet`; if that file is
absent, rebuild it with `scripts/build_viewpoint.py --profile production_parity`.

**The two CSVs are deliberately not committed.** They are derived data — 6.7 MB regenerated from a
single command against a build that is already superseded — and committing them would put a stale
snapshot in the repository's permanent history. This document and the script are the durable record.
Re-run the script against the production build before citing any figure here as current.
