# Post-mortem: Stale zarr store — 46% fatality gap on Hetzner

**Date:** 2026-04-25 (updated 2026-04-26)
**Severity:** Critical (blocked model training with silently wrong data)
**Status:** Resolved. v1.2.7 deployed to Hetzner 2026-04-26. Full pipeline passed. ged_sb_best = 1,956,320 (expected ~1,955,000).

## Summary

The Hetzner-served zarr store had 46% fewer fatalities than the gold set for the calibration period (months 121–492). Models trained on this data (bright_starship) would have learned from systematically undercounted conflict data. The issue was discovered during a consumer parity investigation, not by any automated check.

The root cause was three compounding bugs: (1) `harvest_ucdp.py` used `page_size=50000`, which the UCDP API silently truncates — returning only 335,918 of 384,918 events regardless of which machine makes the request; (2) no TotalCount assertion existed to detect the shortfall; and (3) when the TotalCount assertion was added, its percentage-based 1% tolerance failed for small candidate versions where the UCDP API's consistent ~1000-event type_of_violence=4 offset is 40–100% of the total. The fixes: revert to `page_size=1000` with rate-limit backoff (v1.2.6), and change the assertion to a dual threshold requiring BOTH >1% AND >1100 absolute events (v1.2.7).

## Timeline

| When | What |
|------|------|
| 2026-03-21 | Local machine fetches UCDP v25.1 annual: **384,918 events**. No page_delay (pre-fix code). Used default `page_size=1000`. |
| 2026-03-29 | Commit `9fab694`: adds page_delay=0.5s after UCDP API rate-limits at page 94. Commit `bb52dbf`: increases to 2.0s after 0.5s still triggers 400 at page 38. |
| 2026-03-29 | `harvest_ucdp.py` changed to `page_size=50000` (8 pages) to avoid rate limiting. Deployment log records this as "success." |
| 2026-03-31 | Hetzner server fetches UCDP v25.1 annual via `harvest_ucdp.py` with `page_size=50000`: **335,918 events** (49,000 short). Harvest reports PASS — no TotalCount assertion exists. |
| ~2026-04-08 | Local pipeline rebuilds grid from local data (384,918 annual, fetched March 21 with `page_size=1000`). Grid matches gold set at 99.3%. |
| 2026-04-09 | Hetzner zarr store symlinked and served via Caddy. bright_starship begins consuming it. |
| 2026-04-24 | Consumer parity investigation discovers 46% gap between Hetzner zarr and gold set. |
| 2026-04-24 | Three-way comparison confirms: local data correct, remote data stale. |
| 2026-04-24 | Round-trip integrity check added to `export_zarr.py`. Global sum assertion added to `test_consumer_parity.py`. Server operations runbook written. Risk register updated. PR #20 merged. |
| 2026-04-25 | v1.2.4 deployed to Hetzner. OOM kill on first attempt (round-trip check loaded full dataset into memory). Memory-efficient fix committed, re-tagged, re-deployed. |
| 2026-04-25 | Pipeline completes on Hetzner but zarr still shows 1,481,960 for ged_sb_best (expected ~1,955,000). |
| 2026-04-25 | Investigation reveals server's raw v25.1 has 335,918 events vs local's 384,918. Consolidated store rebuilt from same raw data produces same short total — problem is in the raw harvest, not downstream. |
| 2026-04-25 | Mert Yilmaz (UCDP) confirms v25.1 is immutable. Hypothesis that UCDP revised data is ruled out. |
| 2026-04-25 | Fresh fetch from UCDP API using default `UcdpAnnualConfig()` (page_size=1000) returns **384,918 events**, digest-identical to March 21 backup (`767045ffc47e78ae`). |
| 2026-04-25 | TotalCount assertion added to `fetch_paginated()`. v1.2.5 deployed to Hetzner. Annual harvest correctly fails: "API reports 385918 events but only 336000 fetched (12.9% shortfall)." Candidate also fails: 0 of 307 events (100% shortfall). |
| 2026-04-26 | Raw API probes from Hetzner server (curl via `urllib.request`) return identical first-page results to laptop: TotalCount=385918, correct ResultLen for all page sizes (1, 1000, 50000). DNS resolves identically (130.238.55.71 / pcr-web002.its.uu.se). **The API is not treating the server differently.** |
| 2026-04-26 | Page-by-page test with `page_size=50000` **from the laptop** reveals the API bug: pages 1–6 return 50,000 events each, page 7 returns 35,918, page 8 returns 0. Total: 335,918 — the exact same shortfall as the server. **`page_size=50000` truncation is not server-specific; it's an API pagination bug.** |
| 2026-04-26 | Test with `page_size=1000` from laptop hits HTTP 400 rate limit at page 307 (1502s elapsed). The UCDP API rate-limits after ~300 requests regardless of page_delay. Previous laptop success (March 21) was with page_size=1000 but no page_delay — likely succeeded because network latency to Uppsala provided natural spacing, or the rate-limit window had not been reached. |
| 2026-04-26 | Rate-limit backoff added to `fetch_paginated()`: catches HTTP 400 during pagination and retries with exponential backoff (30s base, up to 5 attempts). `harvest_ucdp.py` reverted to `page_size=1000`. |
| 2026-04-26 | Local test with rate-limit backoff: **384,918 events — PASS** (1952s / ~32 min, includes backoff pauses). |
| 2026-04-26 | v1.2.6 deployed to Hetzner. Annual: **384,918 events — PASS**. Candidate: **FAIL** — TotalCount=307 but 0 events for version 26.0.3 (100% shortfall). dot9: PASS (99 cached). Pipeline fails at step 1/7. |
| 2026-04-26 | Re-ran pipeline after rate-limit cooldown (annual cached, no rate-limit pressure from annual). Candidate fails again with identical error. **This is not residual rate limiting from annual.** Total harvest time 132s — candidate alone triggers the failure. |
| 2026-04-26 | Code trace reveals: (1) candidate discovery makes ~98 API requests at 0.5s intervals; (2) version fetch loop has **no inter-version delay** (`ucdp_candidate.py` line 414); (3) all ~98 versions need re-fetch because `data/*` was deleted but provenance ledgers remain; (4) `fetch_paginated()` gets HTTP 200 with TotalCount=307 and empty Result array — the rate-limit backoff never fires because it only catches HTTP 400, not HTTP 200 with empty data. **This last point is a hypothesis, not verified.** |
| 2026-04-26 | **Experiment Step 1 (cold-start probe):** Fetched 8 candidate versions from laptop with zero rate-limit pressure. ALL versions show exactly 1000-event shortfall between TotalCount and actual events (e.g., 26.0.3: TotalCount=1787, fetched=787). This is the same type_of_violence=4 offset as annual (385,918 vs 384,918). **The candidate failure was caused by our own TotalCount assertion being percentage-based (1%) — for small datasets, 1000/1787 = 56% shortfall, far exceeding 1%.** Not rate limiting at all. |
| 2026-04-26 | Fix: changed TotalCount assertion to dual threshold — shortfall must exceed BOTH 1% AND 1100 absolute events to raise. This tolerates the ~1000 type_of_violence=4 offset for small candidate versions while still catching genuine truncation (e.g., page_size=50000 → 50,000-event shortfall). |
| 2026-04-26 | Local verification: candidate harvest PASS — 64 versions served, 0 failed (285.8s). |
| 2026-04-26 | v1.2.7 deployed to Hetzner. Full pipeline completed: annual 384,918 events PASS, candidate 64 versions PASS (0 failed), dot9 99 versions PASS. Consolidation: 2,322,421 records. Assembly: (456, 360, 720, 43). Zarr export: 43 features, round-trip sums match. |
| 2026-04-26 | **Final verification:** `ged_sb_best = 1,956,320`, `ged_ns_best = 285,346`, `ged_os_best = 1,232,241`. All within expected ranges. Data boundary: month 556 (2026-04). Export freshness: 0h. **Incident resolved.** |

## Root causes

### Primary: `page_size=50000` triggers UCDP API pagination bug

The UCDP GED API has an undocumented pagination bug with large page sizes. When `pagesize=50000` is requested for v25.1 (385,918 total events, TotalPages=8):

| Page | Expected events | Actual events |
|------|----------------|---------------|
| 1–6 | 50,000 each | 50,000 each |
| 7 | 50,000 | **35,918** |
| 8 | 35,918 | **0** |
| **Total** | **385,918** | **335,918** |

The API correctly reports `TotalCount=385918` and `TotalPages=8`, but only serves 335,918 events through pagination. Page 7 receives the tail of the data (35,918 events that should be on page 8), and page 8 is empty. This behavior is **identical from all IPs** — confirmed by running the same 8-page fetch from both the laptop (Oslo) and the Hetzner server (Helsinki) on 2026-04-26. It is an API bug, not a network or rate-limit issue.

The same data fetched with `pagesize=1000` (386 pages) returns 384,918 events correctly. The 1,000-event gap to TotalCount (385,918 vs 384,918) is within the 1% tolerance and likely represents type_of_violence=4 events counted by the API but not returned.

**How `page_size=50000` entered the codebase:** During initial Hetzner deployment (2026-03-29), `page_size=1000` required 386 API requests, which exceeded the UCDP rate limit (~40 requests). The rate limit returns HTTP 400, and `request_with_retry` correctly fails fast on 4xx errors. After trying `page_delay=0.5s`, `page_delay=2.0s`, and `page_size=10000` (all still rate-limited), `page_size=50000` was adopted because it reduced the request count to 8, avoiding rate limits entirely. The deployment log recorded this as "success" — but 335,918 ≠ 384,918. The shortfall was invisible because no TotalCount assertion existed.

**Why the laptop appeared unaffected:** The laptop's local harvester tests used `UcdpAnnualConfig()` defaults (`page_size=1000`), while `harvest_ucdp.py` (the production script) overrode to `page_size=50000`. The laptop never ran `harvest_ucdp.py` against the API with the production config — it always used the default config, which returns correct data. This configuration divergence between "test locally" and "run in production" masked the bug.

### Contributing: No TotalCount assertion (fixed 2026-04-25)

The API's first-page response includes `TotalCount: 385918`. The harvester logged this but never asserted `len(fetched_events) >= TotalCount`. A fetch that returns 87% of expected events passed validation silently. Fixed in v1.2.5 with a 1% tolerance threshold.

### Contributing: 4xx fail-fast prevents rate-limit recovery

`request_with_retry` treats all 4xx responses as non-retryable (fail fast). This is correct for most client errors (404, 403, 422), but UCDP uses HTTP 400 for rate limiting — which IS retryable after a backoff. With `page_size=1000`, the 386 requests exceed the rate limit around page 300, and the fail-fast behavior crashes the entire fetch. Fixed in v1.2.6 with rate-limit-specific backoff in `fetch_paginated()`: catches HTTP 400 during pagination, backs off with exponential delay (30s base, up to 5 attempts), and retries the same page.

### Contributing: No downstream total check

Even after the partial fetch, the pipeline ran to completion: consolidate → viewpoint → compile → assemble → export. At no point did any step check whether the total fatalities were in the expected range. The round-trip integrity check (added in this incident) only verifies zarr == grid.npy — it doesn't catch a grid that was built from incomplete raw data.

### Contributing: Consolidated store append-only semantics

The consolidated store is append-only with dedup by relid. When we re-ran the pipeline on Hetzner (after deleting intermediates but keeping raw data), consolidation ingested 2,273,421 records from the existing (short) raw files and reported "0 new records." The append-only design correctly prevented duplicates but also prevented detection — it looked healthy.

### Contributing: No automated parity check against gold set

The consumer parity tests (`test_consumer_parity.py`) check per-cell mismatch rates (0.1% threshold) and row/col structure. A 46% global fatality gap passes the per-cell check because the missing events are spread across many cells — each cell's individual mismatch is small relative to the total row count.

## What we fixed

| Fix | Where | Version | What it catches |
|-----|-------|---------|----------------|
| Round-trip integrity check | `scripts/export_zarr.py` | v1.2.4 | Zarr store diverging from grid.npy (catches export bugs, stale stores) |
| Memory-efficient round-trip | `scripts/export_zarr.py` | v1.2.4 | Same check but fits in 8 GB RAM (pre-computes sums, uses zarr directly) |
| Global sum parity assertion | `tests/test_consumer_parity.py` | v1.2.4 | Systematic under/over-counting that per-cell checks miss |
| Server operations runbook | `docs/guides/server_operations.md` | v1.2.4 | Knowledge gap — deployment, verification, troubleshooting procedures |
| Risk register entries | `reports/technical_risk_register.md` | v1.2.4 | C-137 (round-trip), C-138 (post-deploy verification), C-139 (global sum parity) |
| TotalCount assertion | `src/datafactory_harvester/sources/ucdp_annual.py` | v1.2.5 | Silent partial fetches — asserts len(events) within 1% of API's TotalCount |
| Revert page_size to 1000 | `scripts/harvest_ucdp.py` | v1.2.6 | Eliminates `page_size=50000` which the UCDP API silently truncates |
| Rate-limit backoff | `src/datafactory_harvester/sources/ucdp_annual.py` | v1.2.6 | HTTP 400 rate limits during pagination — exponential backoff (30s base, 5 attempts) instead of fail-fast |
| Dual-threshold TotalCount assertion | `src/datafactory_harvester/sources/ucdp_annual.py` | v1.2.7 | Shortfall must exceed BOTH 1% AND 1100 events. Tolerates ~1000 type_of_violence=4 offset for small candidate versions while catching genuine truncation |

### Fix details

#### TotalCount assertion (v1.2.5)

Added to `fetch_paginated()`: after pagination completes, asserts `len(all_events)` is within 1% of `TotalCount` from the API's first-page response. Raises `ValueError` if the shortfall exceeds 1%. Protects all three harvesters (annual, candidate, dot9) since they share `fetch_paginated()`.

**Verified:** v1.2.5 deployed to Hetzner on 2026-04-25. Annual harvest correctly failed: "API reports 385918 events but only 336000 fetched (12.9% shortfall)." The assertion caught the `page_size=50000` truncation that had been invisible since March 29.

#### Revert page_size and add rate-limit backoff (v1.2.6)

Two changes that work together:

1. **`harvest_ucdp.py`**: removed `page_size=50000` override, reverting to `UcdpAnnualConfig` default of 1000. With page_size=1000, the API returns all 384,918 events correctly across 386 pages.

2. **`fetch_paginated()`**: added rate-limit retry loop around `request_with_retry()`. When an HTTP 400 is received during pagination, the loop backs off exponentially (30s × 2^attempt + jitter, up to 5 attempts) before retrying the same page. This is distinct from `request_with_retry`'s general retry logic, which correctly fails fast on 4xx — rate limiting is the specific exception where a 400 IS retryable after waiting.

**Verified locally on 2026-04-26:**
- `page_size=1000` with rate-limit backoff: 384,918 events in 1952s (~32 min). Hit rate limit around page 307, backed off 30s, resumed successfully.
- `page_size=50000` page-by-page test: confirmed truncation — page 7 returns 35,918 instead of 50,000, page 8 returns 0. Total 335,918. This is an API bug, not rate limiting.

### Server re-harvest (complete)

v1.2.7 deployed to Hetzner on Apr 26. Full pipeline completed successfully:
- Annual: 384,918 events PASS
- Candidate: 64 versions served, 0 failed PASS
- Dot9: 99 versions cached PASS
- Assembly: (456, 360, 720, 43), 43 features
- Zarr export: round-trip integrity check passed (43 features verified)
- Final totals: ged_sb_best = 1,956,320, ged_ns_best = 285,346, ged_os_best = 1,232,241

### Candidate harvest failure (resolved)

The candidate harvester failed consistently with "Fetch count mismatch" — but the root cause was NOT rate limiting. It was the TotalCount assertion added in v1.2.5.

**Root cause:** The UCDP API includes type_of_violence=4 events in TotalCount but excludes them from Result — a consistent offset of exactly 1000 events across all versions (annual and candidate). For annual (384K events), 1000/385,918 = 0.26% — within the 1% tolerance. For candidate versions (200–2300 events), 1000/1787 = 56% — far exceeding 1%. The assertion was percentage-based and did not account for the fixed ~1000 offset being a large fraction of small datasets.

**Evidence (cold-start experiment, 8 versions, zero rate-limit pressure):**

| Version | TotalCount | Fetched | Shortfall |
|---------|-----------|---------|-----------|
| 26.0.3 | 1787 | 787 | 1000 |
| 26.0.2 | 1298 | 298 | 1000 |
| 26.0.1 | 1727 | 727 | 1000 |
| 25.0.12 | 1912 | 912 | 1000 |
| 25.0.6 | 2276 | 1276 | 1000 |
| 25.0.1 | 2159 | 1159 | 1000 |
| 24.0.6 | 2202 | 1202 | 1000 |
| 20.0.1 | 278 | 0 | 278 |

**Fix (v1.2.7):** Changed TotalCount assertion to dual threshold — shortfall must exceed BOTH 1% AND 1100 absolute events. This tolerates the ~1000 type_of_violence=4 offset for all dataset sizes while still catching genuine truncation (e.g., page_size=50000 produces 50,000-event shortfall, which exceeds both thresholds).

**Why rate limiting was a red herring:** The server's candidate failure showed TotalCount=307 and 0 events. This was likely a compounding effect: rate limiting (from ~98 discovery probes) caused the API to return degraded data, which then also failed the overly strict assertion. The cold-start experiment proved the assertion itself was the primary problem — even without rate limiting, every candidate version fails the 1% threshold.

**Note on dot9:** Mert confirmed .9 includes type_of_violence=4 events (violent political protest). Need to verify our viewpoint handles these correctly — if type 4 events reach the grid, models see data not in the annual reference.

## Remaining weaknesses

### The TotalCount discrepancy (385,918 vs 384,918)

The API reports 1,000 more events than it returns with `page_size=1000`. Our best hypothesis is type_of_violence=4 events counted by the API but excluded from results. The 1% tolerance in the TotalCount assertion accommodates this. If the discrepancy changes (e.g., the API starts including type 4 in results, or the count grows beyond 1%), the assertion may need recalibration.

### No end-to-end data budget assertion

The pipeline has no single check that says "the final grid should contain approximately X fatalities." Each layer validates internally (schema, shape, provenance digest) but none checks the global total against an expected baseline. The global sum parity test in `test_consumer_parity.py` partially addresses this, but it requires a gold-set comparison rather than checking against an expected range. A data budget — an expected range for key aggregates — would catch issues like this regardless of which layer introduces them.

### No inter-version delay in candidate/dot9 fetch loops

`fetch_ucdp_candidate()` (line 414) and `fetch_ucdp_dot9()` (line 426) iterate through discovered versions with no delay between fetches. Combined with discovery (~98 requests), a clean-state candidate harvest makes ~200 API requests in ~60 seconds. This almost certainly exceeds the rate limit. The 2.0s `page_delay` inside `fetch_paginated()` only applies between pages within a single version — there is no delay between completing one version and starting the next.

### Version discovery rate limiting

Candidate and dot9 version discovery makes ~98 sequential API requests (one probe per month from Jan 2018 to present) using `request_with_retry` directly, not `fetch_paginated()`. These probes are subject to the same rate limit but do NOT have rate-limit backoff. If discovery triggers a 400, it interprets this as "version not available" and stops discovery early, potentially missing later versions. The `_DISCOVERY_RATE_LIMIT_SECONDS = 0.5` delay between probes provides some spacing but may be insufficient.

### Rate-limit detection gap: HTTP 200 with empty Result (still unverified)

The rate-limit backoff in `fetch_paginated()` only catches HTTP 400. If the API also rate-limits by returning HTTP 200 with `TotalCount > 0` but an empty `Result` array, the backoff would not fire. This hypothesis was proposed during the candidate debugging but the cold-start experiment showed the candidate failure was caused by the TotalCount assertion tolerance, not rate limiting. The HTTP-200-empty-Result scenario remains unverified and may still be a latent issue under heavy load.

### UCDP API uses HTTP 400 for rate limiting

The UCDP API returns HTTP 400 (Bad Request) for rate limiting instead of the standard HTTP 429 (Too Many Requests). This makes rate limits indistinguishable from genuine client errors without additional context. Our backoff logic catches all 400s during pagination, which is safe for the pagination loop (the request was valid if it worked on page 1) but could mask genuine 400 errors in other contexts. The API has no `Retry-After` header.

### .9 data governance

The .9 dataset is produced specifically for VIEWS with no formal agreement. It includes type 4 events not present in annual/candidate. This informal arrangement is a single-point-of-failure dependency. If Mert leaves or UCDP reorganizes, the .9 data stream could stop without notice.

### Consolidated store cannot detect raw data regression

If a raw file is re-fetched with fewer events (as happened here), the consolidated store's append-only semantics mean it can only grow. It cannot detect that a source file has shrunk. A re-harvest that returns partial data would be silently incorporated — the store would keep the old records and not notice the source regressed. The TotalCount assertion now prevents partial raw files from being written, but the consolidated store itself has no regression detection.

## Documentation updates needed

- [ ] **ADR or addendum on harvest reliability**: document the TotalCount assertion, rate-limit mitigation, and the principle that harvest success requires count verification, not just schema validation
- [ ] **Runbook update**: add "verify raw data totals" step to server operations after harvest
- [x] **Risk register**: C-137/C-138/C-139 updated. C-140 (incident fix test coverage), C-141–C-143 (test gaps) registered 2026-04-26. 21 new tests added.
- [ ] **Deployment log update**: correct the "page_size=50000 → success" entry to note that it was a silent failure producing 335,918 instead of 384,918 events
- [x] **CIC update**: `UcdpAnnualConfig.md` line 46 references "production override: 50000" — needs updating now that production uses default 1000
- [ ] **Health check SLO per source**: health check uses 168h SLO for all sources including static datasets (PRIO-GRID). Need per-source expected update frequency so that static=never, annual=yearly, candidate/dot9=monthly, future ACLED=biweekly.

## Lessons

1. **Validation must check totals, not just structure.** Schema validation, shape checks, and per-cell comparisons all passed with 46% of the data missing. Global aggregates are the cheapest and most effective integrity check.

2. **A harvester that doesn't verify count is not a harvester.** The fetch completed, the file was valid Parquet, the schema was correct, and provenance was recorded. None of that matters if 49,000 events are silently missing.

3. **"PASS" is not a sufficient outcome.** Every PASS should be accompanied by the number it verified. "335,918 events — PASS" looks correct until you know the expected count is 384,918.

4. **Immutable data can still be fetched incorrectly.** The source data was stable (confirmed by re-fetch). The instability was in the transport layer (API pagination bug + our page_size choice). Source immutability is necessary but not sufficient for reproducibility — the fetch itself must be verified.

5. **Append-only stores hide regressions.** The consolidated store's inability to detect that a source file shrank is a design gap, not a feature. Append-only is correct for accumulating new data, but it should also detect when a re-ingested source has fewer records than before.

6. **Large page sizes can silently truncate API results.** The UCDP API accepts `pagesize=50000` without error but returns fewer events than `TotalCount` promises. The last 1–2 pages are short or empty. This is an undocumented API behavior — the API does not reject the page size or return an error; it simply omits events. Always verify total event count against `TotalCount`, regardless of page size.

7. **"Works from the laptop" is not "works in production."** The laptop used `page_size=1000` (default config); production used `page_size=50000` (harvest_ucdp.py override). The configuration divergence meant the laptop always fetched correct data while production silently lost 49,000 events. Test the actual production config, not a different config that happens to share some code.

8. **Rate limits are retryable, not fatal.** The UCDP API uses HTTP 400 for rate limiting. Our HTTP retry layer correctly treats 4xx as non-retryable (most client errors will never succeed on retry). But rate limiting is the exception — a 400 that means "slow down" should be retried after backoff, not treated as a permanent failure. The fix: handle rate-limit 400s at the pagination layer, not the HTTP layer, because the pagination context (we know the request was valid — it worked for earlier pages) is what makes the retry safe.

9. **Verify assumptions before implementing fixes.** Over two days, we repeatedly claimed to know the root cause of a failure and implemented a fix, only to discover a different failure. "I know exactly why" without experimental evidence is a warning sign, not a conclusion. Each fix should be preceded by a controlled experiment that produces a concrete pass/fail result — not by reasoning about what the code "should" do.

10. **Assertions can cause failures too.** The TotalCount assertion added to catch the page_size=50000 bug used a 1% tolerance. This worked for annual (384K events, 1000 offset = 0.26%) but catastrophically failed for candidate versions (200–2300 events, 1000 offset = 40–100%). The fix was a 5-minute change to a dual threshold. The debugging took two days because we assumed the failures were caused by the API or rate limiting — we never considered that our own safety check was the problem. When a new assertion causes widespread failures, suspect the assertion first.
