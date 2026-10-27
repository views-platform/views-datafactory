# Where does the zarr export's five hours actually go?

**Issue:** #501 · **Pre-registered:** 2026-10-20 (`reports/post_mortems/2026-10-20_release_v1150.md:204-205`)
**Measured:** 2026-10-21, production monthly run · **Epic:** #512 Story 4 (#515)
**Machine:** `views-datafactory-00` — **8 vCPU (AMD EPYC-Genoa), 16 GB RAM, 16 GB swapfile, 150 GB usable root.** Measured on the box 2026-10-21, **not** the 4 vCPU / 8 GB the repo documents everywhere; see §4.4.
**Deployed version:** `v1.15.0`, the first run on the instrumented code — evidenced by the installed wheel (`views_datafactory-1.15.0.dist-info`). No `.views-deploy-tag` file exists at the documented path.
**Status:** Complete for what it set out to measure. The *cause* of the non-linearity is still open and is #516's question.

---

## The question, and the short answer

On 2026-10-16 the zarr export took **5h07m** against a figure of **57 min** recorded in June.
Nothing said which part of it was slow. #501 added per-phase timers and asked for the result to
be written down here.

**Two phases account for 95.6% of the export, in almost equal parts: `scan` at 47.5% and
`write` at 48.2%.** The remaining 4.4% is grid load, coordinates, digests, the sentinel, and
the round-trip verification.

The pre-registered refutation test was aimed at `scan`. It **survives** — `scan` came in at
nearly twice the threshold that would have retired the explanation.

This document follows the shape of `reports/investigation_zarr_restatement/findings.md`: what
is confirmed, what is inferred, and what is genuinely open. Every claim carries a citation.
Where the evidence runs out, that is said rather than smoothed over.

---

## 1. What we KNOW (empirically confirmed)

### 1.1 The breakdown

One `export_ledger.jsonl` entry, written 2026-10-21T11:52:34Z. Pipeline 04:27:48 → 11:52:56 UTC.
Source digest `4cdcf66e2e5aca83` → `053241912fc36c92`.

| phase | what it covers | seconds | share of export |
|---|---|---:|---:|
| `write` | `to_zarr` + metadata consolidation | 8,558.9 | **48.2%** |
| `scan` | `source_sums` loop — one strided traversal of `grid.npy` per feature | 8,434.2 | **47.5%** |
| `other` | grid load, coordinate construction, digests, sentinel | 756.6 | 4.3% |
| `verify` | ADR-011 / C-144 round-trip read of the finished store | 23.8 | 0.1% |
| `swap` | `.tmp` → `rename` | 0.3 | 0.0% |
| **export total** | | **17,773.8** | **100%** |

The five phases sum to 17,773.8s exactly — checked, not assumed. `other` is a residual by
construction, and as of #514 it is persisted rather than only printed; before that the entry
accounted for 17,017.2s and a reader had to subtract to find the 756.6s hole.

**Export was 66.5% of the 26,708s (7h25m) pipeline.**

### 1.2 This is the first production breakdown that exists

`export_ledger.jsonl` has three earlier entries — 2026-08-21, 2026-09-21, 2026-10-16 — and
each carries only an outcome and a digest. `phase_seconds` shipped in v1.15.0. **There is no
earlier production breakdown to compare against**, so every statement below about *change over
time* rests on totals, not on phases.

### 1.3 The export cost is stable run-to-run

17,773.8s here against **18,426.6s** on 2026-10-16: a **3.5% drop**. This matters more than it
looks. It is what makes this run a fair proxy for the one #501 was opened about — a breakdown
taken on a run 3.5% from the original is applicable to it; a breakdown taken on a run half the
size would not have been.

### 1.4 The 88% share was never a constant, and the difference is assembly

| run | export | pipeline | export share | assembly |
|---|---:|---:|---:|---|
| 2026-10-16 | 18,426.6s | 21,007s | **87.7%** | skipped (ADR-041 content-addressed skip) |
| 2026-10-21 | 17,773.8s | 26,708s | **66.5%** | ran |

Same export, two shares, because the denominator changed. "88% of the run" describes a
no-change-upstream run specifically. Corrected in `docs/guides/server_quickref.md` — see §4.

---

## 2. The pre-registered criterion, and its verdict

Committed on 2026-10-20, before any production figure existed
(`reports/post_mortems/2026-10-20_release_v1150.md:204-205`):

> if `scan` comes in under ~25% of the export, the strided-memmap explanation is refuted and I
> stop advancing it

**`scan` is 47.5% — 1.9× the refutation threshold. The explanation survives this test.**

The contrast also moved in the predicted direction. On the synthetic grid, where 0.1 GB fits
comfortably in RAM, `scan` was **10.1%** and the *smallest* named phase
(`reports/post_mortems/2026-10-20_release_v1150.md:207`). In production, at 37.3 GB against
8 GB of RAM, it is co-largest. **That inversion is what the claim was about**, and it happened.

### 2.1 What surviving does not mean

Stated plainly because the temptation to over-read a survived test is the whole reason the
criterion was written down first:

1. **Surviving a refutation test is not confirmation.** The criterion could have killed the
   explanation; it did not. That is one failed attempt at refutation, not proof.
2. **#501's own objection is untouched.** The grid went from 43 to 79 features — 1.8× — while
   the export went from ~14 min to ~296 min, **21×**. No linear reading of a strided-access
   model produces that. Something is non-linear and **this breakdown cannot say what.**
3. **It does not exclude a second cause.** `write` is 48.2%, marginally *larger* than `scan`,
   and the strided-memmap story says nothing about `write` at all. An explanation that covers
   47.5% of the cost and is silent on the other 48.2% is at best half an answer.

---

## 3. What is INFERRED (consistent with the evidence, not established by it)

### 3.1 The `verify`-versus-`scan` contrast is an upper bound, not a measurement

`verify` reads every feature back out of the finished store in **23.8s**. `scan` reads the
memmap, strided, in **8,434.2s**.

| | volume | time | throughput |
|---|---:|---:|---:|
| `scan` — strided over `grid.npy` | 37.3 GB | 8,434.2s | **4.4 MB/s** |
| `verify` — contiguous over `grid.zarr` | ~29 GB (decompressed, #501's estimate) | 23.8s | **1,218 MB/s** |

**On raw time the ratio is 354×. Normalised for volume it is 275×**, because `scan` reads 1.29×
more bytes. The 354× figure recorded in #501's comment is the time ratio; both are stated here
because the un-normalised one flatters the contrast by about 29%.

**Neither number is a controlled measurement, and the reason is specific.** The 3.1 GB store had
just been written by the `write` phase immediately before, and 3.1 GB fits inside 8 GB of RAM —
so an unknown and probably large fraction of `verify` was served from page cache rather than
from the SSD. The comparison therefore bounds the access-pattern effect from above. It does not
size it.

Turning this into a measurement needs a dropped-cache read, which is **#516's job and not this
story's.**

### 3.2 `grid.npy` is 37,349,683,328 bytes, against less headroom than claimed but more than feared

Measured on the server, not derived from the shape. The overcommit depends on which figure for
the machine you use, and the repo's figure is wrong (§4.4):

| against | size | overcommit |
|---|---:|---:|
| 8 GB RAM — **as documented, and incorrect** | 8.0 GB | 4.7× |
| 16 GB RAM — **as measured** | 16.0 GB | **2.3×** |
| 16 GB RAM + 16 GB swap — total addressable | 32.0 GB | **1.17×** |

So the grid still does not fit, and a memory boundary is still crossed — but by 17% over
RAM-plus-swap rather than by the 4.7× that every document in this repository implies. Any
explanation whose force comes from the *size* of the overcommit is weaker than it looked, and
**#516's hypothesis is specifically about crossing this boundary**, so #516 must be
re-premised on the measured numbers before it is run.

---

## 4. The record, corrected by kind

Following the editorial rule already established at
`reports/technical_risk_register.md:3302-3304`: live guides carry the measured figure, records
of what was true when written carry **dated amendments** and are not rewritten.

| Location | Figure | Kind | Action |
|---|---|---|---|
| `reports/pipeline_performance_profile.md:25,26,89` | 46 min / 57 min / 103 min / 70% | June 2026 record — **had no amendment at all** | **dated amendment added** (#515) |
| `docs/guides/server_quickref.md:54` | "88% of the run" | **operator-facing authority** | **corrected** — share made conditional, duration untouched |
| `docs/ADRs/041_content_addressed_skip.md:12` | 46 / 57 min in Context | ADR record | left — already amended at `:115` on 2026-10-18 |
| `docs/ADRs/041_content_addressed_skip.md:115` | "88% of a 21,007s run" | the amendment itself | left — accurate **as scoped to that run** |
| `reports/technical_risk_register.md:3316,3322` | 5h07m, 88%, ~57 min, ~350 min | dated register addenda | left — history |
| `reports/product_development_plan12.md:29` | 18,427s, 88% | dated plan | left — history |
| `reports/post_mortems/2026-10-20_release_v1150.md:46-47` | 5h07m, 88%, ~57 min | post-mortem | left — out of scope by #515, and a record |
| `reports/post_mortems/2026-06-08_pre_deploy_drift_detection.md:69,70,87,88` | 46 / 57 min | June post-mortem | left — a record of what was true that day |
| `docs/guides/hetzner_deployment_log.md:296-302` | ~2.5 h total, ~14 min export | March 2026 log | left — carries its own amendment, verified |
| `reports/dot9_investigation/data_streams.md:121,125` | "~88%" | **unrelated** — UCDP candidate-version event overlap | left — false positive for this search |

Every occurrence of `57 min`, `46 min` and `88%` under `docs/` and `reports/` is in this table.
Checked by re-running the search after the edits, not assumed from having made them.

### 4.1 The June profile was never a server measurement

Worth separating, because "stale" undersells it.
`reports/pipeline_performance_profile.md:1-6` records its own machine: **13th Gen Intel
i9-13900H, 32 GB RAM, 2 GB swap**, commit `975b401`, 2026-06-08. The 57 min export was measured
on a **laptop**, against a 35.5 GB grid.

So the figure ADR-041 inherited and reasoned from was never a production number at all. Part of
the 5× discrepancy recorded in ADR-041's amendment is four months of drift; part of it is simply
a different machine.

**How different is smaller than the documents suggest, and this cuts against the convenient
story.** The laptop had 32 GB RAM and 2 GB swap: **34 GB addressable**. The server, as measured,
has 16 GB RAM and 16 GB swap: **32 GB addressable** — within 6%. On RAM alone the laptop has 2×,
not the 4× the documented 8 GB would give.

That matters because the tidy explanation — *the laptop nearly fit the grid in memory and the
server does not* — is not supported by the addressable totals. Neither machine fits a 35.5–37.3 GB
grid. What differs is RAM versus swap composition, CPU, and storage, and this measurement cannot
separate them.

### 4.2 The duration figure was deliberately not revised downward

`server_quickref.md` keeps **~5h07m** as the planning figure for the export even though this run
measured 4h56m. `reports/technical_risk_register.md:3316` states the rule and the reason:

> An over-estimate is harmless; an under-estimate licenses intervention on a healthy run.

An operator who is told 4h56m and is five hours in starts wondering whether to kill it. That is
how the 2026-10-16 outage would be reproduced from a document. Both measurements are now listed;
the expectation is set by the larger.

### 4.4 The documented production hardware is wrong, and ADRs reason from it

Found while filling in this report's machine slot, which is the one slot #515 insisted on
("a production measurement without the tag it ran under is not reproducible"). Measured on
`views-datafactory-00`, 2026-10-21:

| | documented | measured |
|---|---|---|
| vCPU | 4 | **8** (AMD EPYC-Genoa) |
| RAM | 8 GB | **16 GB** (`MemTotal: 15982924 kB`) |
| swap | 2–4 GB swapfile, added as a fix | **16 GB** swapfile |
| root disk | 160 GB | 150 GB usable |

The repo even documents the procedure that produces this exact machine —
`docs/guides/server_operations.md:534-536`: *"click **Rescale** to upgrade to CPX42 (8 vCPU,
16 GB RAM, ~27 EUR/mo). Requires a power-off (~30 seconds)."* The box has been up since
**2026-05-28 08:50 UTC**, consistent with that power-off. **The rescale was performed and never
recorded.**

**13 occurrences across 11 files** still assert the old spec (counted:
`grep -rn "4 vCPU\|8 GB RAM" docs/ reports/`). The problem is not the figure — it is that
conclusions were drawn from it:

- `docs/ADRs/030_raster_tooling.md:82` justifies the Rust raster path on **"memory
  predictability. The production server has 8 GB RAM."**
- `docs/ADRs/035_vdem_as_democracy_source.md:140` concludes **"No OOM risk"** for V-Dem's
  ~4.1 GB from the 8 GB premise.
- `docs/guides/server_operations.md:499` tells an operator **"The CPX32 has 8 GB RAM"** and
  derives the swap advice from it.
- `reports/technical_risk_register.md:1571` states the server **"has no swap partition or
  swapfile"** and proposes a 2 GB one. It has 16 GB.
- `docs/guides/hetzner_deployment_log.md:22,370`, `reports/rd_plan_bounded_memory_compilation.md:51`,
  `reports/sprint_plan_bounded_memory.md:223`, `reports/sprint_plan_s3_hetzner_deployment.md:16,40`,
  and three post-mortems carry the same premise.

**Not corrected here, and deliberately.** #515 is scoped to export-cost figures; rewriting a
hardware premise that two ADRs reason from is a governance change needing its own issue, and
some of those documents are dated records that should carry amendments rather than edits. Filed
on #518. Two consequences are worth stating now because they are load-bearing elsewhere:

1. **#516 must be re-premised before it runs.** Its hypothesis is that *crossing the RAM
   boundary* inverts `scan`'s share. The boundary is at 16 GB + 16 GB swap, not 8 GB, so the
   overcommit it is reasoning about is 1.17×, not 4.7× (§3.2).
2. **The conclusions may well still hold** — a 37.3 GB grid exceeds 32 GB addressable either
   way, and nothing here says the Rust decision or the V-Dem assessment was wrong. What is
   established is only that **their stated premise is false**, which is enough to require
   re-checking and not enough to overturn anything.

### 4.3 ADR-041's "~350 min" still reads true

Checked against the new number, as #515 asked. A no-change deploy skips assembly **and** export:
~45 min + 296.2 min = **341.2 min**, which is **2.5% below** the ~350 min the amendment claims.
Within its own stated precision. **No change needed**, and `reports/technical_risk_register.md:3322`
reads true for the same reason.

---

## 5. What is OPEN

1. **The cause of the non-linearity.** 1.8× the features, 21× the time. Unexplained. #516 —
   which must be re-premised on the measured 16 GB first (§4.4).
2. **The access-pattern effect, sized rather than bounded.** Needs a dropped-cache read; §3.1.
3. **Why `write` costs 8,558.9s.** It is the largest single phase and no hypothesis has been
   offered for it, let alone tested. The strided-memmap explanation does not reach it. Compression
   settings and the `12 × 360 × 720` chunking against a 3.1 GB store are untested candidates
   (named, not advanced — `docs/ADRs/041_content_addressed_skip.md:122`).
4. **Whether `scan` is necessary at all.** `source_sums` exists to verify per-feature sums
   (ADR-011 / C-144). Whether that check needs a full strided traversal per feature, or could
   read the same bytes once, is an **optimisation question and is deliberately not opened here** —
   `reports/post_mortems/2026-10-20_release_v1150.md:339-341` says not to optimise the export
   before the production number exists. The number now exists; a cause still does not.

---

## 6. Provenance of every figure in this document

| Figure | Source |
|---|---|
| All five phase timings, 17,773.8s | the 2026-10-21 `export_ledger.jsonl` entry |
| 26,708s pipeline, 04:27:48 → 11:52:56 | the same run's `logs/refresh.log` |
| 18,426.6s / 21,007s (2026-10-16) | `docs/guides/server_quickref.md:54`, ADR-041:115 |
| `scan` 10.1% on synthetic | `reports/post_mortems/2026-10-20_release_v1150.md:207` |
| 37,349,683,328 bytes | `stat` on `views-datafactory-00` |
| ~29 GB decompressed store | #501's estimate — **an estimate, carried as one** |
| 43 → 79 features, ~14 min baseline | #501's body |
| Machine spec (8 vCPU / 16 GB / 16 GB swap) | measured on the box 2026-10-21: `nproc`, `/proc/cpuinfo`, `/proc/meminfo`, `swapon --show`, `df -h` |
| Deployed version `v1.15.0` | `.venv/lib/python3.12/site-packages/views_datafactory-1.15.0.dist-info` on the server |
| Uptime since 2026-05-28 | `uptime -s` on the box |

No figure above was taken on a different input and presented as this run's.
