# Post-mortem: Stale zarr store — 46% fatality gap on Hetzner

**Date:** 2026-04-25
**Severity:** Critical (blocked model training with silently wrong data)
**Status:** In progress — root cause identified, fixes partially deployed

## Summary

The Hetzner-served zarr store had 46% fewer fatalities than the gold set for the calibration period (months 121–492). Models trained on this data (bright_starship) would have learned from systematically undercounted conflict data. The issue was discovered during a consumer parity investigation, not by any automated check.

## Timeline

| When | What |
|------|------|
| 2026-03-21 | Local machine fetches UCDP v25.1 annual: **384,918 events**. No page_delay (pre-fix code). |
| 2026-03-29 | Commit `9fab694`: adds page_delay=0.5s after UCDP API rate-limits at page 94. Commit `bb52dbf`: increases to 2.0s after 0.5s still triggers 400 at page 38. |
| 2026-03-31 | Hetzner server fetches UCDP v25.1 annual: **335,918 events** (49,000 short). Harvest reports PASS. |
| ~2026-04-08 | Local pipeline rebuilds grid from local data (384,918 annual). Grid matches gold set at 99.3%. |
| 2026-04-09 | Hetzner zarr store symlinked and served via Caddy. bright_starship begins consuming it. |
| 2026-04-24 | Consumer parity investigation discovers 46% gap between Hetzner zarr and gold set. |
| 2026-04-24 | Three-way comparison confirms: local data correct, remote data stale. |
| 2026-04-24 | Round-trip integrity check added to `export_zarr.py`. Global sum assertion added to `test_consumer_parity.py`. Server operations runbook written. Risk register updated. PR #20 merged. |
| 2026-04-25 | v1.2.4 deployed to Hetzner. OOM kill on first attempt (round-trip check loaded full dataset into memory). Memory-efficient fix committed, re-tagged, re-deployed. |
| 2026-04-25 | Pipeline completes on Hetzner but zarr still shows 1,481,960 for ged_sb_best (expected ~1,955,000). |
| 2026-04-25 | Investigation reveals server's raw v25.1 has 335,918 events vs local's 384,918. Consolidated store rebuilt from same raw data produces same short total — problem is in the raw harvest, not downstream. |
| 2026-04-25 | Mert Yilmaz (UCDP) confirms v25.1 is immutable. Hypothesis that UCDP revised data is ruled out. |
| 2026-04-25 | Fresh fetch from UCDP API returns **384,918 events**, digest-identical to March 21 backup. API is stable. Server's March 31 fetch was a silent partial failure. |

## Root causes

### Primary: Silent partial fetch (harvest layer)

The UCDP API rate-limits paginated requests. On March 31, the server's fetch completed with 335,918 events instead of 384,918 — losing ~50 pages of results. The harvester reported PASS because:

1. **No TotalCount assertion.** The API's first-page response includes `TotalCount: 385918`. The harvester reads this for logging but never asserts `len(fetched_events) >= TotalCount`. A fetch that returns 87% of expected events passes validation silently.

2. **Rate-limit interaction is non-deterministic.** The UCDP API enforces ~40 requests/minute but the exact threshold varies. Fetches with 0s delay hit 400 at page 94. Fetches with 0.5s delay hit 400 at page 38. Fetches with 2.0s delay succeed today but failed partially on March 31. The 4xx fail-fast correctly rejects individual 400 responses, but the failure mode is a *shorter total*, not a hard error — the API may return fewer results per page or skip pages.

**How this produced 335,918 instead of 384,918:** Unknown exactly. Possible mechanisms: (a) API returned truncated pages under load, (b) rate-limit caused retries that returned different result sets, (c) CDN/cache served partial data during a window. The harvester has no way to detect any of these because it only checks that each individual page has results and that the required fields exist.

### Contributing: No downstream total check

Even after the partial fetch, the pipeline ran to completion: consolidate → viewpoint → compile → assemble → export. At no point did any step check whether the total fatalities were in the expected range. The round-trip integrity check (added in this incident) only verifies zarr == grid.npy — it doesn't catch a grid that was built from incomplete raw data.

### Contributing: Consolidated store append-only semantics

The consolidated store is append-only with dedup by relid. When we re-ran the pipeline on Hetzner (after deleting intermediates but keeping raw data), consolidation ingested 2,273,421 records from the existing (short) raw files and reported "0 new records." The append-only design correctly prevented duplicates but also prevented detection — it looked healthy.

### Contributing: No automated parity check against gold set

The consumer parity tests (`test_consumer_parity.py`) check per-cell mismatch rates (0.1% threshold) and row/col structure. A 46% global fatality gap passes the per-cell check because the missing events are spread across many cells — each cell's individual mismatch is small relative to the total row count.

## What we fixed (so far)

| Fix | Where | What it catches |
|-----|-------|----------------|
| Round-trip integrity check | `scripts/export_zarr.py` | Zarr store diverging from grid.npy (catches export bugs, stale stores) |
| Memory-efficient round-trip | `scripts/export_zarr.py` | Same check but fits in 8 GB RAM (pre-computes sums, uses zarr directly) |
| Global sum parity assertion | `tests/test_consumer_parity.py` | Systematic under/over-counting that per-cell checks miss |
| Server operations runbook | `docs/guides/server_operations.md` | Knowledge gap — deployment, verification, troubleshooting procedures |
| Risk register entries | `reports/technical_risk_register.md` | C-137 (round-trip), C-138 (post-deploy verification), C-139 (global sum parity) |

## What still needs fixing

### 1. Harvester TotalCount assertion (DONE — 2026-04-25)

Added to `fetch_paginated()` in `src/datafactory_harvester/sources/ucdp_annual.py`: after pagination completes, asserts `len(all_events)` is within 1% of `TotalCount` from the API's first-page response. Raises `ValueError` if the shortfall exceeds 1%.

This directly prevents the primary root cause. The server's 335,918 fetch (13.0% shortfall against TotalCount 385,918) would now fail loudly instead of silently succeeding. The fix protects all three harvesters (annual, candidate, dot9) since they share `fetch_paginated()`.

**Verified:** Fresh fetch on 2026-04-25 returned 384,918 events, digest-identical to March 21 backup (`767045ffc47e78ae`). API's TotalCount is 385,918 — the 1,000-event discrepancy (0.26%) passes the 1% tolerance. Likely type_of_violence=4 events counted by the API but not returned.

### 2. Server re-harvest

Force re-fetch on Hetzner with the hardened harvester (TotalCount assertion). Delete intermediates. Rebuild pipeline. Verify ged_sb_best total matches ~1,955,000.

### 3. Candidate and dot9 harvester hardening

The same TotalCount gap could exist for candidate and dot9 fetches. All three harvesters use `fetch_paginated()` patterns — the fix should be consistent across all three.

**Note on dot9:** Mert confirmed .9 includes type_of_violence=4 events (violent political protest). Need to verify our viewpoint handles these correctly — if type 4 events reach the grid, models see data not in the annual reference.

## Remaining weaknesses

### The TotalCount discrepancy (385,918 vs 384,918)

The API reports 1,000 more events than it returns. Our best hypothesis is type 4 filtering, but this is unconfirmed. If the discrepancy changes over time or varies by endpoint, the TotalCount assertion could produce false positives. The tolerance needs to be calibrated, and we should track the discrepancy in provenance.

### No end-to-end data budget assertion

The pipeline has no single check that says "the final grid should contain approximately X fatalities." Each layer validates internally (schema, shape, provenance digest) but none checks the global total against an expected baseline. A data budget — an expected range for key aggregates — would catch issues like this regardless of which layer introduces them.

### Rate-limit non-determinism

UCDP's rate limits are undocumented and appear to vary. A fetch that works today with 2.0s delay may fail tomorrow. The harvester has retries but no adaptive backoff for pagination specifically. If a page returns 400, the 4xx fail-fast correctly stops retries for that page, but the failure doesn't propagate clearly — it depends on whether `request_with_retry` raises or returns an error response.

### .9 data governance

The .9 dataset is produced specifically for VIEWS with no formal agreement. It includes type 4 events not present in annual/candidate. This informal arrangement is a single-point-of-failure dependency. If Mert leaves or UCDP reorganizes, the .9 data stream could stop without notice.

### Consolidated store cannot detect raw data regression

If a raw file is re-fetched with fewer events (as happened here), the consolidated store's append-only semantics mean it can only grow. It cannot detect that a source file has shrunk. A re-harvest that returns partial data would be silently incorporated — the store would keep the old records and not notice the source regressed.

## Documentation updates needed

- [ ] **ADR or addendum on harvest reliability**: document the TotalCount assertion, rate-limit mitigation, and the principle that harvest success requires count verification, not just schema validation
- [ ] **Runbook update**: add "verify raw data totals" step to server operations after harvest
- [ ] **Risk register**: review C-137/C-138/C-139 status; consider new entries for TotalCount discrepancy, .9 governance, rate-limit non-determinism

## Lessons

1. **Validation must check totals, not just structure.** Schema validation, shape checks, and per-cell comparisons all passed with 46% of the data missing. Global aggregates are the cheapest and most effective integrity check.

2. **A harvester that doesn't verify count is not a harvester.** The fetch completed, the file was valid Parquet, the schema was correct, and provenance was recorded. None of that matters if 49,000 events are silently missing.

3. **"PASS" is not a sufficient outcome.** Every PASS should be accompanied by the number it verified. "335,918 events — PASS" looks correct until you know the expected count is 384,918.

4. **Immutable data can still be fetched incorrectly.** The source data was stable (confirmed by re-fetch). The instability was in the transport layer (API rate limiting + our pagination). Source immutability is necessary but not sufficient for reproducibility — the fetch itself must be verified.

5. **Append-only stores hide regressions.** The consolidated store's inability to detect that a source file shrank is a design gap, not a feature. Append-only is correct for accumulating new data, but it should also detect when a re-ingested source has fewer records than before.
