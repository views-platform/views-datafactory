# 08 — The legacy GedLoader: what the old database actually did

**Date:** 2026-11-04 · **Source:** the production `GedLoader` ingestion notebook (ingester3 /
`views3` Postgres), supplied by Simon 2026-11-04. Run shown is `version='26.9.9'`,
`fix_summary_events=True`, executed 2026-10-22.

This is prior art, not a target. It is recorded because **three of its properties change this
program's design**, and one of them is a live parity divergence in our repo.

---

## 1. What it confirms — our parity claims are faithful

| Our code | Legacy source | Verdict |
|---|---|---|
| `ceil_split` detection: `best > 0 and span > 1 month and best >= span` | `np.where((best > 0) & (summary_period > 1) & (best >= summary_period), 1, 0)` | ✅ **exact match** |
| `ceil_split` allocation: `ceil(fatalities / span)` to every month in span | `np.int64(np.ceil(best/summary_period))`, then one row per month in `range(date_start_month, date_end_month+1)` | ✅ **exact match** |
| `date_end_only`: month from `date_end` | `pgm.from_datetime(self.ged, 'date_end')` | ✅ **exact match** |
| `exclude_where_prec=(4, 6)` | `self.pg_ged = self.ged[(where_prec != 4) & (where_prec != 6)]` | ✅ match **for the grid path only** — see §3 |
| `min_priogrid_gid=1` | `self.ged[self.ged.priogrid_gid >= 1]` | ✅ |
| `max_type_of_violence=3` | `self.ged[self.ged.tv < 4]` | ✅ |
| `source_distribution_map={"annual": "date_end_only"}` | `fix_summary_events` is a constructor flag; the candidate run passes `True` | ✅ consistent — the switch is per-loader, as our docstring says |

**`ceil_split`'s non-conservation is inherited, not ours.** The legacy code applies `np.ceil` to
`best`, `high` *and* `low`, assigning the rounded-up value to every month in the span. Total out
≥ total in, by construction. Our measured 0.91% inflation is therefore **faithful parity with a
legacy defect**, which changes how it should be handled: fixing it is a *parity break*, not a bug
fix, and belongs behind the same profile switch as everything else.

---

## 2. ⭐ What it reveals that we did not have documented

### 2a. An `is_summary` flag already existed — and was thrown away at aggregation

```python
self.ged['is_summary'] = np.where((best > 0) & (summary_period > 1) & (best >= summary_period), 1, 0)
self.ged['summary_period'] = 1 + date_end_month - date_start_month
```

Both columns are computed on the event table. Then:

```python
ged_fraction = self.pg_ged[['tv','pg_id','month_id','best','high']]   # is_summary not selected
```

**The flag is computed and then dropped at the aggregation boundary** — exactly the loss documented
in `02 §4` for our own pipeline. So **views-hydranet's ask #1 is a restoration, not an invention**:
the concept existed upstream in the legacy system and died at the same seam. That materially
strengthens the case for **O3** and weakens any objection that a precision flag is a novel
consumer demand.

### 2b. `_nokgi` — the legacy schema declared the exclusion in the column name

Every ingested column is named e.g. `ged_sb_best_sum_nokgi`, `ged_os_high_count_nokgi`.
**`nokgi` = "no Known Geographical Imprecision."** The legacy database encoded, in its own column
names, that these features *exclude* geographically imprecise events — and by implication
anticipated a `_kgi` counterpart that was never built. ADR-049's *Deferred* section uses the same
KGI vocabulary.

Two consequences:

1. **Naming precedent for O1/O3.** A distributed variant has an obvious legacy-consistent name, and
   the distinction is one the platform's schema has always expected to make.
2. **Our exported feature names carry no such marker.** `lr_sb_best` does not say whether KGI events
   are in or out. The legacy schema was *more* self-documenting than ours on exactly this point.

### 2c. Summary events spreading past the current month are discarded

```python
summary_events_spread = summary_events_spread[summary_events_spread['month_id'] <= end_month]
regular_events       = regular_events[regular_events['month_id'] <= end_month]
```

A summary event whose span extends beyond the ingestion month loses the months past the cut — mass
silently dropped, undeclared. A second inherited conservation leak, distinct from the `ceil`
inflation and pulling the other way. Note the commented-out alternative in the source,
`for month in range(r[38], end_month+1)`, which would have spread to the current month instead of to
`date_end` — evidence the boundary was experimented with and never settled.

### 2d. `where_prec == 99` exists and is in no codebook

The consolidated store holds **19 events with `where_prec = 99`** (84 fatalities). UCDP's codebook
defines 1–7. `exclude_where_prec=(4, 6)` does not catch it, and our `spatial_conc` flag
(`where_prec >= 5`) does. Negligible in mass; worth a declared decision rather than an accident.

---

## 3. ⚠️ A live parity divergence: the PGM/CM asymmetry

**This is the finding with the largest consequence.** In the legacy loader the two aggregations read
*different* tables:

```python
def aggregate_to_pg(self):
    ged_fraction = self.pg_ged[[...]]        # FILTERED: where_prec not in (4, 6)

def aggregate_to_cm(self):
    ged_cm_agg = self.ged[[...]]             # UNFILTERED: all where_prec
```

So in the legacy system, a `where_prec` 4 or 6 event is **excluded from priogrid-month and included
in country-month**. That is coherent: at country level the location *is* known to sufficient
precision, so the deaths belong there; at grid level they do not.

**Our architecture cannot reproduce this.** `grid_to_country_month(grid, ...)` takes the assembled
`[T, H, W, C]` grid as its input, so country-month is derived *from* the grid — after
`exclude_where_prec` has already removed those events at the viewpoint stage. They are therefore in
**neither** aggregation.

### Scale

Measured on `data/consolidated/ucdp_store.parquet` with the legacy filters applied
(`priogrid_gid >= 1`, `type_of_violence < 4`), deduplicated by UCDP event `id`:

| `where_prec` | events | fatalities | % of mass |
|---:|---:|---:|---:|
| 1 | 205,177 | 1,573,708 | 34.86% |
| 2 | 103,604 | 1,044,676 | 23.14% |
| 3 | 63,596 | 411,879 | 9.12% |
| **4** | **42,028** | **420,891** | **9.32%** |
| 5 | 19,665 | 617,047 | 13.67% |
| **6** | **6,096** | **443,978** | **9.83%** |
| 7 | 276 | 2,634 | 0.06% |
| 99 | 19 | 84 | 0.00% |

**`where_prec` 4 or 6: 48,124 events, 864,869 fatalities — 19.16% of all mass.** Present in legacy
country-month; absent from ours.

⚠️ *Caveat:* deduplication by `id` is an approximation of the real survivorship rule
(`dot9_wins` + `filter_stale_versions`), which is why this yields 440,461 events against the
viewpoint's 372,058. **The percentage is the right order of magnitude, not a final number**, and
should be re-measured properly before being cited.

### Why it matters to this program

1. **It is a parity claim we have not verified.** `production_parity` is named for reproducing the
   legacy loader. On the country-month path it does not, and nothing tests it.
2. **It is structural, not configurable.** No profile setting fixes it; CM derives from the grid.
   Restoring it would mean an event-level CM aggregation path — a genuine architectural change,
   well beyond this program's scope.
3. **It is an argument for O1.** If `where_prec` 4–6 events were *distributed* (ADR-049) rather than
   dropped, they would appear in the grid and therefore in country-month automatically — closing
   this divergence as a side effect rather than by new machinery.

**Routed to `register-risk`, not fixed here.** Scope per `04_roadmap.md` P0.

---

## 4. What this does to the roadmap

- **P0 gains a third governance item**: the CM/PGM parity divergence (§3), alongside the two
  ADR-049 divergences.
- **O3's case strengthens** (§2a): the flag is a restoration of a legacy concept, not a new demand.
- **The `ceil_split` conservation question is re-framed** (§1): it is inherited parity, so "fixing"
  it is a parity break and must sit behind the profile switch.
- **A naming decision appears** (§2b): our exported feature names should say whether KGI events are
  included, as the legacy schema's `_nokgi` suffix did.
