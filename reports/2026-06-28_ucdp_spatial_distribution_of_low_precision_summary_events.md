# UCDP low-precision "summary" events are not spatially distributed — a data artifact that poisons PGM-level models

**Author:** Surfaced during the views-stepshifter salvage effort (Simon / Claude), 2026-06-28
**Audience:** views-datafactory maintainers
**Status:** Findings + design proposal. No datafactory code changed. Handoff for your team to action.
**Severity:** High — silent, plausible-looking corruption of the PGM (PRIO-GRID-month) fatalities target that distorts every grid-level model trained on it. Not a crash; produces wrong-but-believable numbers.

---

## 0. TL;DR

UCDP GED records some events with **low spatial precision** (`where_prec ≥ 4`: the location is known only to an admin-1 region or coarser). These get **geocoded to a single centroid cell**. When a large, multi-month "summary" event is involved — e.g. the **Tigray war** — the result is a single PRIO-GRID cell holding a **quarter of a million fatalities**.

Datafactory already does the *temporal* analog of the right thing: it **spreads imprecise-*date* events across their months** (`even_split` in `temporal_distribution.py`). But there is **no spatial analog** — imprecise-*location* events are dropped whole into one cell. The fix is the mirror image of what already exists: a **`spatial_distribution` strategy** that spreads `where_prec ≥ 4` events across the cells of their admin region (datafactory already harvests the GAUL boundaries needed).

We are flagging this **now**, while the team migrates from viewser to datafactory, so the bug is fixed at the destination rather than rediscovered in a few months. Today datafactory deliberately reproduces this (it targets viewser **production-parity**), so the fix should be a **new, opt-in strategy** that lets you keep parity as the default while validating the improvement separately.

---

## 1. How this surfaced

June 2026 PGM forecasts (the `skinny_love` ensemble and others) showed a **dead-straight horizontal "stripe" of elevated predicted violence at ~13.25°N**, running across the African continent through empty desert. Real conflict is never a straight line, so we traced it.

It turned out to be **two independent bugs stacked**:

- **Problem A (this report — datafactory/data):** the historical fatalities target has one cell with ~273k deaths, because a region-wide UCDP summary event is pinned to one cell.
- **Problem B (separate — views-stepshifter/model):** the stepshifter model was accidentally feeding the PRIO-GRID cell ID to the tree as a feature (`use_static_covariates=True` default in darts), which smears that one hot cell into a full-latitude line. Being fixed separately in views-stepshifter; **out of scope here.**

This report is **only Problem A**. It stands on its own: even with no modelling bug, a single 55×55 km cell holding a quarter-million deaths is a false hotspot that corrupts any PGM model, evaluation metric, or map built on this target.

---

## 2. The artifact

Summing the historical target (`lr_ged_sb` / `ged_sb_best`) per cell over all history:

| rank | priogrid_gid | lat / lon | location | total deaths (all history) | worst single month |
|------|--------------|-----------|----------|----------------------------|--------------------|
| 1 | **148759** | 13.25 / 39.25 | **Mekelle, Tigray, Ethiopia** | **273,076** | 54,495 (gold) / **121,915** (raw) |
| 2 | 150919 | 14.75 / 39.25 | N. Tigray / Eritrea border | 79,841 | 30,000 / 48,183 |
| 3 | 178273 | 33.75 / 36.25 | Syria (~Homs) | 39,389 | 2,482 |
| 4 | 181875 | 36.25 / 37.25 | Syria (~Aleppo) | 35,750 | 1,413 |

For scale, across the **entire** PGM panel the **99.99th percentile of the target is 255** and the median is 0. Cell 148759 alone is the global maximum and **3.4× the next-worst cell on the continent**. This is not a plausible single-cell value — it is an entire war's toll collapsed onto one grid point.

Reproduced independently at every datafactory layer we have on disk (so it is not a one-off in one consumer's file):

| layer | cell 148759 (max month) |
|-------|--------------------------|
| `data/compiled/dataframe.parquet` (raw `ged_sb_best`) | **121,915** |
| `data/gold/viewser_pgm_africa_me.parquet` (`lr_sb_best`) | 54,495 (sum 273,076) |
| `data/consumer/forecasting_viewser_df.parquet` | 54,495 |
| the model's actual training input (viewser) | 54,495 (sum 273,076) |
| **UCDP GED source (live API)** | events summing **274,357** |

(The gold/consumer 54,495 vs raw 121,915 difference is the *temporal* even-split redistributing the raw monthly spike across the event's span — see §4. The **total** is conserved at ~273–274k across all five layers.)

---

## 3. Root cause: UCDP low-precision summary events

Cell 148759 (the Mekelle PRIO-GRID cell, footprint lat 13.0–13.5, lon 39.0–39.5) contains these **actual UCDP GED events** (GED 24.1, `country=530` Ethiopia):

| event id | best | date span | where_prec | date_prec | where_coordinates |
|----------|------|-----------|-----------:|----------:|-------------------|
| 463137 | **121,848** | 2022-08-24 → 2022-10-24 | **5** | 5 | "northern Ethiopia" |
| 463131 | **113,368** | 2021-01-01 → 2021-12-31 (**whole year**) | **5** | 5 | "northern Ethiopia" |
| 449986 | 20,000 | 2022-08-24 → 2022-09-30 | 5 | 5 | "northern Ethiopia" |
| 510098 | 15,372 | 2022-08-24 → 2022-11-02 | 5 | 5 | "northern Ethiopia" |
| 510583 | 1,818 | 2021-02-13 (1 day) | **2** | 1 | "Ādī Iser village" |

The deaths are **real** (the Tigray war, 2021–2022). The problem is **how UCDP encodes location uncertainty**:

- **`where_prec = 5`** means UCDP only knows the event happened in *"an area larger than an admin-1 region"* — here, *"northern Ethiopia."* UCDP still must attach a single lat/lon, so it uses a **regional centroid** (Mekelle's coordinates). That centroid falls in PRIO-GRID cell 148759, so **the entire regional toll is geocoded to one cell.**
- The lone **`where_prec = 2`** event (a precisely-located village strike, 1,818 deaths) is exactly what a *well-located* event looks like, for contrast.

This is **not Tigray-specific**. Cell #2 (150919, 79,841 deaths) is the **1999–2000 Eritrea–Ethiopia border war** (`where_prec=5`, "Eritrea-Ethiopia common border"). **Same mechanism, different conflict, 20 years apart** — strong evidence the issue is **systemic**, keyed on `where_prec`, not a single bad record.

### UCDP precision code reference (for context)

`where_prec`: 1 = exact point · 2 = ≤25 km · 3 = adm-2 · 4 = **adm-1** · 5 = **larger than adm-1** · 6 = country · 7 = multi-country/international.
`date_prec`: 1 = exact day · … · 5 = range longer than a month.

The pathological cases are `where_prec ≥ 4` (location no more precise than a province). Tigray is the worst possible: `where_prec = 5` **and** `date_prec = 5` — maximally imprecise in **both** space and time.

---

## 4. Proof of mechanism (end-to-end, r = 0.99998)

We reconstructed cell 148759's monthly training values **from the live UCDP events alone**, applying only *temporal* even-split (best ÷ number of months in the date span) and **no spatial redistribution** — i.e. simulating exactly what datafactory/viewser does today:

| month | UCDP temporal-reconstruction | actual training value |
|-------|------------------------------|-----------------------|
| 2021-01 … 2021-12 | ~9,447 / month | ~9,447 / month |
| 2022-08 | 54,488 | 54,487 |
| 2022-09 | 54,496 | 54,495 |
| 2022-10 | 44,485 | 44,484 |

Correlation **0.99998**, totals 274,357 vs 273,076 (0.5% apart — UCDP version drift). This confirms the full causal chain:

> UCDP low-precision summary event → temporal even-split across its months (✅ correct) → **all months piled into one centroid cell (❌ the bug)** → one cell with a quarter-million deaths.

Note the chain demonstrates the **asymmetry**: the *date* imprecision is handled (the 113,368 became ~9,447 × 12, not a single 113k spike); the *location* imprecision is not handled at all.

---

## 5. Blast radius

Within the Africa+Middle-East PGM extent, **16 cells** carry a single-month value above 2,000 (vs a global 99.99th percentile of 255). The dominant cluster is **Ethiopia/Tigray** (gids 148759, 150919, 151639, 150916). The remainder map onto **Syria (Aleppo, Homs), Gaza/Israel, Somalia (Mogadishu), DR Congo, Angola** — i.e. several distinct conflicts.

**Caveat / honesty:** only the **Tigray** cells are *verified* against the UCDP source as `where_prec`-driven artifacts. The others share the signature (suspiciously high single-cell totals at conflict locations with round summary numbers) but were **not individually confirmed**. A global `where_prec ≥ 4` sweep of UCDP (any country, large `best`) would quantify the true systemic scope — recommended as a scoping step before implementing.

---

## 6. Current datafactory behavior (what we read)

### 6.1 Temporal distribution: present and reasonable ✅

`src/datafactory_viewpoint/temporal_distribution.py` is a clean strategy registry (`event dict → list[dict]`), with:

- `even_split` (config **default**) — for `date_prec == 5`, divides `best/low/high` evenly across the spanned months. **This is why the Tigray toll is spread across 12 months rather than dumped in one.**
- `ceil_split` / `floor_split` — production-parity variants matching the viewser GedLoader's `fix_summary_events` (detect summary as `best > 0 ∧ span > 1 ∧ best ≥ span`; round up/down per month).
- `date_end_only` — assigns everything to the `date_end` month, **no distribution**. Exists only to bit-match the old viewser annual loader; **not the default**. (Worth noting because, if selected, it *would* reproduce the "everything in one month" failure.)

### 6.2 Spatial distribution: absent ❌

- There is **no** `spatial_distribution.py` and no spatial strategy anywhere.
- An event arrives already carrying a single `priogrid_gid` (its imprecise location collapsed to a centroid upstream). `src/datafactory_compilation/pregridded_compilation.py:235–241` maps `pgid → (row, col)` and writes the value into that **single cell**. No spreading, no aggregation choice.
- The only `where_prec` lever is **exclusion**: `ViewpointConfig.exclude_where_prec` (default empty) **drops** matching events entirely (`builders/ucdp_v1.py:80–83`). That loses real deaths; it does not place them correctly.

### 6.3 This is currently intentional (production-parity)

`builders/ucdp_v1.py` describes itself as a *"production-parity materialized view"* that deliberately **replicates viewser**, including its source-ordering survivorship (lines 134–219). We confirmed parity empirically: datafactory's own gold/consumer/compiled layers reproduce the 273k Mekelle cell. **So datafactory faithfully inherits the viewser bug by design.** Fixing it is therefore a *deliberate divergence*, not a regression to patch — see §8.

---

## 7. Why it matters downstream

- **Every PGM-level model** trained on this target sees a permanent quarter-million-death hotspot at Mekelle. It distorts learned spatial structure, inflates that location's forecasts, and (as we found in stepshifter) can be amplified into continent-spanning artifacts.
- **Evaluation metrics** computed on this target are contaminated: a model that "correctly" predicts the false hotspot scores well for the wrong reason; one that doesn't is penalized.
- It is **silent**: the numbers are large but not infinite, plausible at a glance, and never raise an error. It survives every existing gate.
- It is **systemic and recurring** (Tigray 2021–22 and Eritrea–Ethiopia 1999–2000 are the same bug), so it will keep appearing as new low-precision summary events enter UCDP.

---

## 8. Proposed fix: a `spatial_distribution` strategy (mirror of the temporal one)

The architecture already contains the template. Mirror `temporal_distribution.py` with a spatial registry:

> **For an event with `where_prec ≥ T`, instead of emitting one row at the centroid cell, emit N rows that spread `best/low/high` across the PRIO-GRID cells of the event's admin region**, conserving the total.

The parallel to what already exists is exact:

| | temporal (exists) | spatial (proposed) |
|---|---|---|
| trigger | `date_prec == 5` | `where_prec ≥ T` (T≈4) |
| spread over | the months in `[date_start, date_end]` | the **cells** in the event's admin region |
| split | even / ceil / floor | even / **population-weighted** / area-weighted |
| conserves | total fatalities across months | total fatalities across cells |
| registry | `temporal_distribution.py` | new `spatial_distribution.py` |

### 8.1 Design decisions for your team

1. **`where_prec` threshold (T).** `where_prec = 4` (adm-1) maps cleanly to a single GAUL adm-1 polygon → straightforward to distribute. `where_prec = 5` ("larger than adm-1") is genuinely ambiguous — the region may span several adm-1 units (e.g. "northern Ethiopia" ⊃ Tigray + Afar + Amhara). `where_prec = 6` = whole country. You'll need a policy per level (and `where_prec = 5` likely needs a configured region map or a fallback to the UCDP `adm_1`/country fields — **do not parse the free-text `where_coordinates` string**; use the structured `adm_1` / `country_id` / `gwno` fields).

2. **Spread weighting.** Uniform-across-cells is the primitive baseline. **Population-weighting is materially better** for conflict (deaths track population), and datafactory already harvests `ghspop` (`data/viewpoint/ghspop_v1.parquet`). Recommend population-weighted as the target, uniform as the fallback where population is unavailable.

3. **Admin geometry source.** Datafactory already harvests **GAUL admin boundaries** (`provenance/gaul_admin`, `gaul_admin_area_majority`, ADR-025). Use these to enumerate the PRIO-GRID cells of an event's region. The `gaul_admin_area_majority` crosswalk (cell → admin by area majority) is likely the natural join.

4. **Composition with temporal distribution.** Tigray is `date_prec = 5` **and** `where_prec = 5`, so it needs **both** strategies — spread across months **and** cells. Decide the order/joint application (e.g. temporal first to get per-month totals, then spatial per month) and ensure the two compose cleanly (the temporal registry already emits `list[dict]`; spatial would expand each of those further).

5. **Conservation & provenance.** The compilation layer already enforces a conservation invariant (`placed + skipped_spatial + skipped_temporal = input`, `conservation.py`) and logs counters. Spatial distribution must **preserve the total** (sum over cells = original `best`, modulo a documented rounding policy like the temporal `ceil`/`floor`) and add provenance counters (`n_spatially_distributed`, cells-per-event) to the ledger.

6. **Parity vs improved mode (the real policy call).** Because datafactory targets viewser parity, ship this as a **new opt-in strategy, off by default**. Keep parity as the validated baseline; turn the spatial strategy on as a deliberate, separately-validated improvement. This lets you migrate on parity *and* capture the fix without conflating the two.

### 8.2 Acceptance criteria / regression test

- After the spatial strategy is enabled, **no single cell-month should receive the full `best` of a `where_prec ≥ T` event.** Concretely: the Tigray event (id 463131, 113,368 over 2021) should distribute across Tigray's ~N cells × 12 months, so cell 148759's per-month value drops from ~9,447 to roughly `9,447 / N`.
- **Total conserved:** `Σ_cells Σ_months = original best` (± documented rounding).
- A **golden test** pinning the Tigray case: assert cell 148759's all-history total falls from 273,076 to a realistic spread, and that the **sum over the Tigray region is unchanged**.

---

## 9. Reproduction recipe (for your team)

UCDP GED API (auth header `x-ucdp-access-token`, token in env `UCDP_API_TOKEN`):

```
GET https://ucdpapi.pcr.uu.se/api/gedevents/24.1?country=530&pagesize=1000&page=N
```

Filter the result to the Mekelle cell footprint (`13.0 ≤ latitude < 13.5`, `39.0 ≤ longitude < 39.5`) and inspect `best`, `where_prec`, `date_prec`, `date_start/end`. You will see events 463137 (121,848) and 463131 (113,368) at `where_prec = 5`. PRIO-GRID decode used throughout: `col = (gid-1) % 720 + 1`, `row = (gid-1) // 720 + 1`, `lon = -180 + (col-0.5)*0.5`, `lat = -90 + (row-0.5)*0.5` (gid 148759 → row 207, col 439 → lat 13.25, lon 39.25).

---

## 10. Relationship to the stepshifter bug (so it's not conflated)

The visible *stripe* was a **compounding** of two bugs:

- **Problem A (this report):** one over-concentrated cell — your domain, the fix above.
- **Problem B (views-stepshifter):** the model fed the PRIO-GRID id to the tree as a feature (darts `use_static_covariates=True` default), turning that one hot cell into a latitude-wide line. Fixed independently in views-stepshifter.

They are **independent**: fixing A removes the false hotspot; fixing B stops the model from smearing *any* sharp cell (real or artifact) into a line. Both are needed for trustworthy PGM forecasts, but **A is yours and B is ours.** This report is self-contained for A.

---

## 11. Recommended next steps for datafactory

1. **Scope it:** run a global UCDP `where_prec ≥ 4`, large-`best` sweep to enumerate every cell currently mis-concentrated worldwide (not just the 16 we found in Africa/ME).
2. **Decide policy:** confirm the opt-in / parity-preserving approach (§8.1.6) and the `where_prec` threshold (§8.1.1).
3. **Build** `spatial_distribution.py` mirroring `temporal_distribution.py`; population-weight via `ghspop`; spread via GAUL `gaul_admin_area_majority`.
4. **Conserve + provenance** (§8.1.5); **golden test** the Tigray case (§8.2).
5. **Validate as an improvement** (not parity): compare the PGM target before/after on the known cells.

Questions or the underlying analysis scripts/figures are available on the stepshifter side; ping us.
