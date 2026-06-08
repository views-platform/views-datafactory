# Pre-Deploy Post-Mortem: Drift Detection + Stale Artifact Fix

**Date:** 2026-06-08
**Author:** Simon Polichinel von der Maase, Claude Code
**Scope:** Source-digest gates, stale zarr/parquet re-export, provenance enforcement
**Branch:** chore/pre-deploy-drift-detection (from development)
**Commit:** 975b401
**Root cause report:** Expert code review + expert method review (2026-06-08)
**Related:** PR #139 (ACLED dedup fix), Issue #138 (closed)

---

## Incident

After the ACLED dedup fix (PR #139, merged 2026-06-07), the assembled `grid.npy` was correct (2025 ACLED = 411,089 events). However, derived artifacts were still built from the pre-fix grid:

- **grid.zarr**: 822,178 events (2× correct value)
- **consumer parquet**: 822,178 events (2× correct value)

The factory *records* provenance digests but never *verifies* them at derivation boundaries. A re-assembly produced a new grid.npy but didn't invalidate or re-export downstream artifacts.

## Root cause

**Provenance recording without provenance enforcement (C-253, Tier 1).**

Export scripts read `provenance.json` for metadata but never compared the recorded digest against the actual grid.npy. There was no gate, no assertion, no fail-loud check. Stale derived artifacts were structurally possible for every data source.

## What we found during the fix

1. **provenance.json was itself stale** — dated June 1, while grid.npy was from June 7. The re-assembly on June 7 (after ACLED dedup) didn't write a new provenance.json. Our new digest gate caught this immediately on first export attempt: `ABORT: grid.npy digest (b6affdfdf4949eac) does not match provenance.json (1d835e7a748f7703)`.
2. **Full re-assembly required** — we had to re-run the 46-minute assembly to get a matching provenance.json. The re-assembly produced an identical grid (same digest `b6affdfdf4949eac`), confirming the June 7 grid was correct.
3. **V-Dem has 20.8 GB of orphaned memmap files** in `data/compiled/vdem/`. Two `_memmap_*.npy` files at 10.4 GB each.

## Fix

9 files changed, 618 insertions:

| File | Change |
|------|--------|
| scripts/export_zarr.py | Source-digest gate: compute grid.npy SHA-256, compare with provenance.json, ABORT on mismatch |
| scripts/generate_consumer_data.py | Same digest gate + provenance manifest (source digest, feature mapping, output digests) |
| scripts/assemble_grid.py | Write `.exports_required` sentinel after assembly |
| scripts/check_health.py | Report content-freshness + sentinel status alongside time-freshness |
| src/datafactory_provenance/health.py | `verify_source_digest()` + `content_fresh` field in `check_export_freshness()` |
| src/datafactory_provenance/__init__.py | Export `verify_source_digest` |
| tests/test_drift_detection.py | 8 unit tests for new provenance enforcement |
| tests/test_falsification_deploy_readiness.py | 2 falsification tests: zarr ACLED count + zarr timestamp |
| reports/technical_risk_register.md | D-35 full entry + concern updates |

## Verification

| Gate | Result |
|------|--------|
| Lint (ruff) | Clean |
| Full test suite | 1651 passed, 0 failed, 14 xfailed |
| Drift detection tests | 8/8 passed |
| Falsification deploy readiness | 2/2 passed |
| Zarr 2025 ACLED | 411,089 (was 822,178) |
| Consumer parquet | Regenerated with provenance manifest |
| Digest match | grid.npy b6affdfdf4949eac = provenance.json |
| Sentinel | Written by assembly, cleared by export |

## Time cost of this session

| Activity | Wall-clock |
|----------|-----------|
| Code review + plan development | ~30 min |
| Code changes (9 files, 618 lines) | ~30 min |
| Re-assembly (required: stale provenance.json) | 46 min |
| Zarr re-export | 57 min |
| Consumer parquet regeneration | 4.5 min |
| Test suite + verification | 12 min |
| **Total** | **~3 hours** |

Of that, **103 minutes** (57%) was waiting for assembly + zarr export. The actual engineering work was ~1 hour. This iteration cost is the motivation for the synthetic test path proposal.

## Concerns addressed

| ID | Tier | Status |
|----|------|--------|
| C-253 | 1 | **Resolved** — source-digest gate in export scripts |
| C-254 | 2 | **Resolved** — consumer parquet gets provenance manifest + digest gate |
| C-255 | 2 | **Resolved** — health check reports content-freshness |

## What this does NOT fix

- **Assembly iteration time** (46 min) — structural; requires incremental assembly or synthetic test path
- **Zarr export time** (57 min) — structural; requires lazy export or direct-to-zarr compilation
- **Memory pressure** (40% RSS + 100% swap) — see `reports/rd_plan_bounded_memory_compilation.md`
- **V-Dem stale memmaps** (20.8 GB) — cleanup needed, no correctness impact
