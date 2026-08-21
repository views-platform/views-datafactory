# Does the served zarr ever restate earlier months?

**Issue:** #453 · **Asked by:** views-postprocessing (views-postprocessing#272), on behalf of FAO-FSFC
**Answered:** 2026-08-21 · **Epic:** #461 Story 3 (#464)
**Status:** Complete — documentary. The empirical half is named in §3 and not done.

---

## The question, and the short answer

FAO's contractor asked whether they can update their copy of the historical dataset by **appending
the newest month**, or whether they must **re-pull the whole thing** each time.

**Short answer: re-pull. Earlier months can and do change.**

The cheap optimisation is not append — it is *skip*. One HTTP request tells you whether anything
changed at all, and if nothing did you can skip the re-pull entirely. What that request **cannot**
tell you is whether a change was an append or a restatement, and §3 says why.

This document follows the shape of `reports/dot9_investigation/findings.md`: what is confirmed,
what is inferred, and what is genuinely open. Every claim carries a citation. Where the evidence
runs out, that is said rather than smoothed over.

---

## 1. What we KNOW (empirically confirmed)

### 1.1 The store is fully rewritten on every run. There is no append path.

`scripts/export_zarr.py` writes to a temporary directory, then swaps:

```
:326   shutil.rmtree(tmp_output)
:329   ds.to_zarr(...)            # mode="w"
:359   os.rename(str(output), str(old_output))
:360   os.rename(str(tmp_output), str(output))
```

There is no incremental or append code path anywhere in the export. Assembly behaves the same way —
it pre-allocates with `np.zeros` and rebuilds the whole `[T, H, W, C]` array (ADR-047, rule 3 under `### Rules`).

**Consequence for you:** every byte you fetch may differ from last month's, including bytes for
1990. Not because they were targeted, but because nothing writes a subset.

### 1.2 Skip logic is all-or-nothing, never partial.

ADR-041 (content-addressed skip): assembly skips only if *every* input digest matches *and* the
output digest matches; the export skips only if the store's recorded digest matches the
provenance digest. So the store is either **byte-identical to the previous run** or **entirely
replaced**. No mechanism exists that could rewrite only the tail.

### 1.3 Upstream data is mutable, and this was measured, not assumed.

On 2026-03-21, probing 26 retained UCDP candidate versions spanning 2024-2026 (the API retains candidates from January 2018 onward per ADR-015:16; earlier versions were **not** probed, which bounds §2.1)
(`reports/dot9_investigation/findings.md:277-280`):

| Versions | Count | Result |
|---|---|---|
| 2025–2026 candidates | 14 | **All changed: exactly +1,000 events each** |
| 2024 candidates | 12 | Perfectly stable |

The identical delta across fourteen versions indicates a bulk retroactive update by UCDP, not
organic growth.

ADR-015:15 states the design assumption directly: *"New releases may revise events from prior
years."*

### 1.4 A revision reaches the grid by replacing, not by accumulating.

This is the step that turns upstream mutability into *your* problem, and it is worth being precise
about because the two layers behave differently:

- **The consolidated store is append-only.** ADR-015:49 — *"Each harvest run adds records to the
  store. Existing records are never modified. If UCDP revises an event in a new annual release,
  the revision appears as a new record with a different `_source_version`."* Every vintage is kept.
- **The grid is not.** `src/datafactory_viewpoint/survivorship.py:57-77` (`annual_wins`) selects
  **annual if available, else the latest candidate**. So when a new annual release lands, months
  previously served from candidate data are **replaced** by the annual figures.

History is preserved upstream of the grid and discarded at it. You receive the survivor.

### 1.5 One counter-example, stated because it bounds the claim.

Not everything upstream is mutable. On 2026-04-25, UCDP confirmed directly that annual **v25.1 is
immutable** (`reports/post_mortems/2026-04-25_stale_zarr_store.md:29`) — a hypothesis that UCDP had
revised data was investigated and **ruled out** for that release.

So the mutability lives in **candidate/dot9 versions** and in **annual-release turnover**, not
within a given annual version once published.

### 1.6 A magnitude estimate already exists.

`docs/guides/viewser_transition_guide.md:142`:

> ~0.05–0.14% of conflict event cells may have different values between a viewser-sourced parquet
> and a factory-sourced parquet. The differences are real — UCDP revises fatality estimates between
> annual releases. **They are not pipeline bugs.**

That figure compares two *sources* rather than two vintages of ours, so treat it as an order of
magnitude, not a measurement of run-to-run drift. It is the closest number that exists.

---

## 2. What we THINK we know (inferred from evidence)

### 2.1 There may be an undocumented stability boundary, and it would matter a great deal to you.

`reports/dot9_investigation/reproducibility_note.md:24`:

> Our observation is consistent with a policy where versions older than approximately one year
> become immutable, while more recent versions remain subject to updates. **We have not confirmed
> this boundary and it is not documented in any UCDP codebook we could find.**

The 2026-03-21 probe is consistent with it — all fourteen recent versions moved, all twelve
year-old ones did not.

**Even if it were confirmed, it would not make append-only safe** — an earlier draft said it would,
which was wrong. The boundary concerns **candidate** versions. Annual releases are a separate
mechanism: ADR-015:15 says a new annual release *"may revise events from prior years"*, with no
stated limit, and §1.4 shows survivorship replacing served months when one lands. **There is no
recency window on annual restatement.**

So this is an interesting observation about one upstream series, not a route to a cheaper strategy.
Do not build on it — not merely because it is unconfirmed, but because it would be insufficient even
if confirmed.

### 2.2 Restatement and append almost always arrive together.

The pipeline harvests, re-consolidates and re-exports in a single monthly run. So a cycle that adds
a new month is also a cycle that may have revised old ones. We have not seen a run that did one
without the other, and the architecture gives no reason to expect one.

---

## 3. What we DON'T know (open questions)

### 3.1 Nobody has ever measured a before/after diff of two store vintages.

This is the honest limit of this document. Everything above is derived from **how the code behaves**
and from **upstream probes**. No one has taken two consecutive zarr vintages and diffed them at
cell-month level to say *"in the September run, N cells in months before August changed, by this
much."*

That measurement needs a snapshot taken **before** a monthly run, and the pipeline runs at 00:00 UTC
on the 21st. It is a bounded piece of work and it is not done.

### 3.2 You cannot distinguish restatement from append — and this is the important part.

The store publishes `source_digest` (`scripts/export_zarr.py:236`), computed by
`compute_file_digest` over the **entire** `grid.npy` (`:206`). One digest, whole grid, every month,
every feature. It changes identically whether a month was appended or 1991 was rewritten.

There is **no per-month digest, no per-region digest, and no version counter.**

**What you can do today, with no new machinery.** Fetch `.zattrs` (about 2 KB) and record two values
each cycle — `source_digest` and `last_valid_month_id`:

| Observation | What it means | Your action |
|---|---|---|
| `source_digest` unchanged | **No grid values changed.** Guaranteed by §1.2. It digests `grid.npy` only, so a re-export with different chunking or labels could republish under the same digest — values are what it protects, and values are what you care about | **Skip the re-pull entirely.** This is the real saving |
| `source_digest` changed | **Something changed. We cannot tell you what.** | Re-pull |

**That is the whole signal. Two states, not three.**

An earlier draft of this document claimed a third — that a changed digest with an *unchanged*
`last_valid_month_id` was an unambiguous restatement signal. **That was wrong, and the error is
recorded here because it is exactly the kind that would have cost you.**

`last_valid_month_id` is computed from `ged_*` features **only**: `scripts/export_zarr.py:280-294`
filters `feature_names` to those beginning `ged_`, i.e. UCDP. The grid also carries ACLED, GHS-POP,
GHS-BUILT-S, V-Dem, SHDI and the GAUL crosswalk. So a run in which **only ACLED gains a month**
changes the digest and leaves `last_valid_month_id` exactly where it was — producing the signature
the draft called "unambiguous restatement" for what is a plain append.

Acted on, that would have had views-postprocessing report a history rewrite to FAO in a month where
nothing was rewritten. Caught in review before publication.

**So `last_valid_month_id` tells you whether UCDP's observed frontier moved, and nothing else.** It
is what views-postprocessing already uses to decide which months are fabricated in the delivery.
Do not press it into service as a change detector.

**We are deliberately not building a finer signal.** Reasons, in case it is asked for later: a
per-month digest could be asserted by us but not *verified* by you, because the store's chunks span
twelve months each (`export_zarr.py:316-319`) — checking one month would mean decompressing a
12-month window of every feature. And any such digest would move for reasons unrelated to
restatement, e.g. a change in feature order or dtype, so it would owe you a second mechanism to
distinguish *that*. If this becomes genuinely blocking, say so and we will reconsider on evidence.

### 3.3 A correction to the premise of the question.

#453 infers from `docs/CICs/ComparisonResult.md` that revision-detection machinery already exists.
It does, but **it is harvest-time only and does not reach the store.** `compare_snapshots` is called
exclusively from the harvester sources — `ucdp_annual.py`, `ucdp_candidate.py`, `ucdp_dot9.py`,
`acled.py` — and its output is logging and alerting. Nothing propagates it downstream.

The real propagation path is the one in §1.4: consolidation dedup keeps every vintage, and viewpoint
survivorship selects one.

### 3.4 What reaches FAO is a parquet, not this store.

Worth stating because it changes who can act on §3.2. **views-postprocessing builds and re-uploads
FAO's historical file themselves** — this repository does not deliver to FAO directly. What it
serves is exactly three paths: `grid.zarr`, `dataframe.parquet` (produced by
`scripts/export_dataframe.py`, `refresh_pipeline.sh:301`) and `status.html`. No provenance manifest
is served alongside either artifact.

*(An earlier draft named `scripts/generate_consumer_data.py` here. That is the views-models training
bridge — it writes `{model}/data/raw/{run_type}_viewser_df.parquet` — and is not on the FAO path.
Corrected in review.)*

So the digest check in §3.2 is available to **views-postprocessing**, who fetch the zarr. It is not
available to FAO's contractor directly. Any saving has to be realised on the views-postprocessing
side, or passed through deliberately.

---

## 4. Recommendation

1. **Keep doing the full re-pull.** It is correct, and it stays correct regardless of anything above.
2. **Add the `source_digest` check if the re-pull cost is worth avoiding.** It is one GET of a 2 KB
   file and it turns "always re-pull" into "re-pull when something changed" — which, on a month
   where the pipeline skipped, saves the whole transfer.
3. **Do not adopt append-only.** Not on §2.1's unconfirmed stability boundary, and not on §3.2's
   ambiguous middle row.
4. **If you need a real bound on how far back changes reach**, ask for §3.1 — the before/after
   measurement. It needs one snapshot taken before a monthly run and it has not been done.
