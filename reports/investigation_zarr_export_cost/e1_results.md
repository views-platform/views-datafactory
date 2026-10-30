# E1 result — the memory boundary is not the mechanism. Read amplification is.

**Issue:** #516 · **Measured:** 2026-10-22 on `views-datafactory-00`, box idle (load 0.00), no
pipeline running · **Pre-registered:** `pre_analysis_plan.md`, written before any timing
**Raw data:** `e1_raw_2026-10-22.jsonl` (4 runs) · **Harness:** production numpy 2.4.3 via
`PYTHONPATH`, read-only on `grid.npy`, nothing written, nothing installed on the box

## Short answer

The `scan` phase re-reads the entire 37.355 GB grid **once per feature** — 79 times, **2.951 TB
from disk** — and that single fact accounts for **97%** of its measured 8,434.2s. Only **2%** of
the cost is arithmetic. The remaining 98% is moving the same bytes off disk over and over.

This is *not* a RAM-capacity story, and the distinction decides a purchase. The file exceeds
cache, so nothing is retained between passes — but the fix for that is reading the file once,
not buying enough memory to cache a file we re-read needlessly.

## All four criteria, as registered

| F | wall/pass | `read_bytes`/pass | amplification | MB/s | cpu/wall | utime/wall |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 122.35s | 37,351,559,168 | 1.000× | 305.3 | 0.3299 | — |
| 2 | 126.05s | 37,355,397,120 | 2.000× | 296.4 | 0.3353 | — |
| 4 | 125.63s | 37,355,213,824 | 4.001× | 297.3 | 0.3274 | — |
| 8 | 109.76s | 37,355,058,176 | 8.001× | 340.3 | 0.3846 | **0.0198** |

- **R1 — amplification.** Refuted if F=8 read under 2× the file. Measured **8.001×**, and
  per-pass reads are 1.0001× the file size at every F. **Survived.** Each pass genuinely fetches
  all 37.355 GB from the block device; the cache absorbs nothing, even at F=8.
- **R2 — I/O vs CPU.** Refuted if `cpu/wall > 0.8`. Measured **0.3846**. **Survived** — and the
  split sharpens it decisively (below).
- **R3 — constant per-pass cost.** Refuted if spread exceeded ±25%. Measured 109.76–126.05s,
  **max deviation 9.2%**. **Survived.**
- **R4 — does the harness reproduce production?** Refuted if `79 × per-pass` missed the measured
  8,434.2s by more than 2×. Using F=8, the closest pass count to production's 79:
  `79 × 109.76 = 8,671.0s` against **8,434.2s** → **1.028×**. **Survived, within 2.8%.**

R4 is the result that matters most. A 2.8% agreement means the model is not one candidate among
several — it accounts for the phase.

## The split that changed the answer

The combined CPU figure (0.33–0.38) cannot distinguish arithmetic from kernel page-fault
servicing. Split, at F=8:

| component | per pass | × 79 passes | removable? |
|---|---:|---:|---|
| `utime` — the strided summation itself | 2.17s | 171.5s | no, but it is negligible |
| `stime` — kernel fault servicing and page mapping | 40.04s | 3,163.1s | yes, by traversing once |
| blocked on disk (wall − cpu) | 67.5s | ~5,336s | yes, by reading once or by caching |

`utime/wall = 0.0198`. **The arithmetic is 2% of the phase.** 4,845,001 minor faults against
1,622 major ones per F=8 run confirms the shape: readahead is fetching the bytes and the cost is
in mapping and waiting, not computing.

**This corrects an interim figure I reported mid-run.** On the F=1/F=2 data alone I attributed
~3,339s to "CPU no amount of RAM removes" and put the RAM ceiling at ~85 minutes. That treated
all CPU as irreducible. With the split, the irreducible part is **171.5s**, not 3,339s, and the
earlier ceiling was wrong in the direction that understated the available win. The split existed
as a known gap in the instrument and was named as one before this run; it is recorded here
because the number reached the operator before it was corrected.

## What this means for buying memory

Both remedies collapse disk reads from 2.951 TB to 37.355 GB. They are not equivalent beyond that.

| | scan | basis |
|---|---:|---|
| today | **8,434.2s** | measured |
| with enough RAM to cache the grid | ~3,400s | **inferred** — removes the disk wait, keeps the 3,163s of per-pass mapping |
| traversing the file once | ~165s | **inferred** — removes both; unmeasured |

Neither figure for a remedy is measured; both are projections from measured components and are
labelled as such. The ordering between them, however, follows from the measurement rather than
from the projection: **RAM eliminates the waiting but still maps the file 79 times, while one
traversal eliminates both.**

So, to the question that prompted this spike — **64 GB would not solve the problem.** It would
buy roughly 1.4 hours of a 7.4-hour pipeline, cost money every month, stop helping once the grid
outgrows it (37.355 GB today at 79 features, and the grid grows per feature), and be beaten by a
change that costs nothing and does not expire.

And **it cannot be the whole answer either way**: `write` is 48.2% of the export and nothing here
touches it. Even the free remedy leaves a pipeline over 5 hours.

## Scope — what was deliberately not done

Implementing the single-pass traversal is an **optimisation**, and this spike is measurement only
(`post_mortems/2026-10-20_release_v1150.md:339-341`; `findings.md` §5 item 4). The projection above
is the argument for opening that item, not a licence to act on it inside a spike.

## E2 and E3

- **E2 (locating the knee) is not run, and is now superseded rather than pending.** Its purpose was
  to size a RAM purchase. The measurement says not to make one, so the knee's location no longer
  decides anything. If the RAM option is revived, E2 becomes necessary again — it is the only
  experiment that separates hardware from feature count at fixed conditions.
- **E3 (converting the 354× `verify`/`scan` bound into a measurement)** is not run. Still cheap,
  still open, and it would sharpen `findings.md` §3.1 rather than change a decision.

## Correction owed to the record

`findings.md` §5 item 1 calls the cause of the non-linearity "unexplained". For `scan` it is now
explained and quantified. Item 3 — `write` at 8,558.9s — remains entirely unexplained, and is now
the largest open question about the export rather than a co-equal one.

## Cleanup

`/home/simmaa_prio/probe516.py`, `probe516.out` and `probe516_f8.out` remain on the box; the
failed `probe516_venv` directory was left by an aborted `venv` attempt (`python3-venv` is not
installed and installing it needs root, so the harness used the production venv's numpy by
`PYTHONPATH` instead). None of it is in a path the pipeline reads.
