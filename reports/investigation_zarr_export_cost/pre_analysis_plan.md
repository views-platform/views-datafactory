# Pre-analysis plan — is the memory boundary the export's non-linearity?

**Issue:** #516 (S5 of epic #512) · **Written:** 2026-10-22, *before any measurement was taken*
**Measured on:** `views-datafactory-00` — 8 vCPU AMD EPYC-Genoa, 15 GiB RAM, 15 GiB swap,
150 GB root with 58 GB free. Box idle at write time (load 0.00, no pipeline process).
**Runs as:** `simmaa_prio`. **No `sudo`, no root, no writes to `/home/views-deploy`.**

This plan is registered first because #501's verdict is trustworthy today only because its
criterion was written before its number arrived. The same discipline applies here, and it is the
whole reason this file exists before any timing.

---

## 0. The premise this plan corrects

The approved epic wrote S5's hypothesis against **4 vCPU / 8 GB**, which is what the repo
documents in 13 places across 11 files. The box was rescaled; the real spec was measured on
2026-10-21 and recorded in `findings.md` §4.4. The overcommit for the grid is therefore:

| the grid against | ratio |
|---|---:|
| 8 GB — what the epic assumed | 4.7× |
| 15 GiB RAM — measured | 2.3× |
| RAM + swap — measured | **1.17×** |

And the comparison S5 leaned on does not survive it: the June laptop had 32 GB RAM + 2 GB swap
= 34 GB addressable against this box's 32 GB. **Within 6%.** "The laptop nearly fit the grid and
the server does not" was never true. What differs between the two machines is RAM-versus-swap
composition, CPU, storage, **and the feature count — 43 then, 79 now.** Two variables moved at
once, which is exactly why the June/October comparison cannot answer this and a controlled
measurement must.

---

## 1. The quantity under test, stated exactly

`grid.npy` is **37,349,683,328 bytes** (34.78 GiB), shape **[T=456, H=360, W=720, F=79]**
`float32`, C-order. Arithmetic check: `456 × 360 × 720 × 79 × 4 = 37,349,683,200` + 128-byte
header = the file size exactly.

`scripts/export_zarr.py:252-263` sums one last-axis slice per feature:

```python
for i, name in enumerate(feature_names):
    feature_slice = grid[:, :, :, i]
    source_sums[name] = float(feature_slice.sum())
```

Because `F` is the contiguous axis, `grid[:, :, :, i]` strides by `79 × 4 = 316` bytes. A 4096-byte
page therefore yields `4096 / 316 = 12.96` wanted elements — **51.9 useful bytes per 4096, or 1.27%
page utilisation.** One pass touches every page of the file to collect 1/79 of it.

**The model:** if the file cannot be held in page cache, each of the 79 passes re-reads it from
disk, so bytes-from-disk ≈ `79 × 34.78 GiB ≈ 2.95 TB`, and cost is linear in passes while the
file size is itself linear in F — i.e. **time ∝ F²**, which is the shape the non-linearity needs.

It arithmetically fits what we measured: 8,434.2s / 79 passes = **106.8 s/pass**, and
37.35 GB / 106.8s = **350 MB/s**, a credible figure for 4 KiB-granular reads on virtualised NVMe.
That fit is suggestive and is *not* evidence — a model built to match one number will match it.
The point of E1 is to test it against a quantity it was not fitted to: **bytes actually read from
the block device.**

Cache headroom for context: ~14 GiB available against a 34.78 GiB file, so the cache can hold at
most **40%** of it even when otherwise empty.

---

## 2. E1 — read amplification, at fixed file size

**No synthetic data, no disk written, uses the real production grid read-only.** Vary the number
of passes `F ∈ {1, 2, 4, 8}` over the *same* 34.78 GiB file, reproducing production's call shape
exactly (one `grid[:, :, :, i].sum()` per pass, no chunking — chunking would change the very
access pattern under test).

Per run, record: wall time, CPU time (`utime+stime`), **`read_bytes` from `/proc/self/io`**,
peak RSS, and `buff/cache` before and after. `read_bytes` is the decisive instrument: it counts
bytes fetched from the block device, so it measures amplification directly instead of inferring it
from timing.

`posix_fadvise(POSIX_FADV_DONTNEED)` is called on `grid.npy` before each run so every run starts
from the same cold state. That is the only intervention, it needs no root, and it touches only
this file's cache.

### Predictions, committed now

| F | predicted wall | predicted `read_bytes` |
|---:|---:|---:|
| 1 | ~107s | ~37.3 GB |
| 2 | ~214s | ~74.7 GB |
| 4 | ~427s | ~149 GB |
| 8 | ~854s | ~299 GB |

Predicted total ≈ **27 minutes**. Predicted `cpu_time / wall_time` ≈ **< 0.15** (I/O-bound).

### What refutes it — written before the run

- **R1 — amplification.** If F=8's `read_bytes` is **under 2× the file size** (≈75 GB rather than
  ≈299 GB), passes are being absorbed by cache or readahead, and the memory boundary is not the
  mechanism. **Refuted.**
- **R2 — I/O vs CPU.** If `cpu_time / wall_time > 0.8`, the scan is **CPU-bound**. More RAM cannot
  help, and the RAM purchase is refuted *regardless of R1*. This is the single most
  decision-relevant number in the plan.
- **R3 — constant per-pass cost.** If per-pass wall time varies by more than ±25% across F, the
  "each pass costs one full file read" model is wrong even if R1 holds.
- **R4 — does the experiment reproduce production at all?** If `79 × (per-pass time)` differs from
  the measured 8,434.2s by more than 2×, the harness is not measuring the production phenomenon
  and **no conclusion transfers** — positive or negative.

R4 is a validity check on the instrument, not on the hypothesis. It is listed because a plan that
can only fail in the interesting direction is not a plan.

---

## 3. E2 — where the knee is, run only if E1 survives

E1 tests amplification at one size. It cannot locate the boundary, which is what sizing a RAM
purchase actually requires. E2 repeats the identical access pattern on synthetic `float32` arrays
of **4, 8, 12, 20 and 28 GiB** (≤ 28 GiB written into the 58 GB free, deleted after), spanning
below and above the ~14 GiB cache limit at **fixed hardware and fixed access pattern** — which is
the confound the June/October comparison cannot escape.

**Prediction:** per-pass cost collapses toward memory bandwidth once the array fits, and the knee
sits near available cache, not near `MemTotal`.

**Refuted if** per-pass cost is flat across the boundary, or the knee is nowhere near ~14 GiB.

E2 is what converts "buy RAM" into "buy *this much* RAM". E1 alone cannot size the purchase.

---

## 4. E3 — the 354× upper bound, if the timebox allows

`findings.md` §3.1 reports `scan` at 4.43 MB/s against `verify` at 1218.5 MB/s — 354× by time,
275× volume-normalised — and labels both **upper bounds**, because the 3.1 GB zarr store had just
been written and fits in RAM. An `fadvise`-cold read of the store converts the bound into a
measurement. Lowest priority; recorded as not-run if the timebox expires first.

---

## 5. What each outcome means for spending money

| outcome | buy RAM? |
|---|---|
| R1 and R2 both survive | RAM would help `scan` — **but so would a single-pass read, for free.** Measure the knee (E2), then choose between them. |
| R2 fails (CPU-bound) | **No.** The money would buy nothing. |
| R1 fails (no amplification) | **No.** The cause is elsewhere and unidentified. |
| R4 fails | No conclusion. The instrument did not reproduce the phenomenon. |

Note the first row honestly: **even full confirmation does not make 64 GB the right purchase.**
If the cost is 79 re-reads of one file, reading it once gets the same win for nothing, and keeps
working as the grid grows past any box bought today. That is `findings.md` open item 4, and it
stays closed here — this plan measures, it does not optimise
(`post_mortems/2026-10-20_release_v1150.md:339-341`). What the measurement changes is that item's
priority, not its status.

---

## 6. Safety, and what it costs the box

- **Read-only.** Nothing under `/home/views-deploy` is written. No `sudo`.
- **No OOM path.** Worst case, a materialised slice is `118,195,200 × 4 = 473 MB` against 14 GiB
  available — and `.sum()` over a strided view is not expected to materialise at all. RSS is
  recorded so the claim is checked rather than asserted.
- **Single-threaded and `nice`d**, so 7 of 8 vCPUs stay free.
- **Real cost to others:** ~350 MB/s of disk for ~27 minutes, and other users' page cache gets
  evicted. The box is idle (load 0.00, 2 users) and the next cron is **21 November**, so there is
  no pipeline to collide with. This satisfies the epic's "must not run concurrently with a
  production pipeline run".
- **Timebox: 90 minutes, hard stop.** E1 is predicted to need 27. A negative or inconclusive
  result is a valid outcome and gets recorded as one.

---

## 7. What this cannot settle, however it comes out

1. **`write`, at 48.2% — the largest phase.** Nothing here touches it. Even a total success caps
   the achievable export saving at roughly half.
2. **Whether June's laptop was faster because of hardware or because of 43-vs-79 features.** Only
   E2 separates those, and only at fixed hardware.
3. **Whether `scan` needs to exist in this form.** Deliberately out of scope (§5 above).
