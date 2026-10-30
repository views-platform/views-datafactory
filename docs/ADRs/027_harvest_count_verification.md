# ADR-027: Harvest Count Verification

**Status:** Accepted
**Date:** 2026-04-26
**Deciders:** Simon Polichinel von der Maase, Claude Code
**Extends:** ADR-008 (Observability and Explicit Failure), ADR-011 (Fail Loud, No Stale Data Serving)

---

## Context

On 2026-04-25, a consumer parity investigation revealed that the Hetzner-served zarr store had 46% fewer fatalities than the gold set. The root cause was a UCDP API pagination bug triggered by `page_size=50000`, which silently returned 335,918 of 384,918 events. The harvest reported success because it validated schema and provenance but never checked event counts.

The pipeline ran to completion on the truncated data: consolidation, viewpoint, compilation, assembly, and zarr export all passed their internal validations. No layer detected that 49,000 events were missing. The shortfall was invisible for 27 days.

Full details: `reports/post_mortems/2026-04-25_stale_zarr_store.md`.

---

## Decision

### Harvest success requires count verification

A harvest is not successful unless the fetched event count is within tolerance of the API's declared total. Schema validation, file writing, and provenance recording are necessary but not sufficient.

For paginated APIs that report a `TotalCount` (or equivalent):
1. After pagination completes, assert `len(fetched) >= TotalCount * (1 - tolerance)`.
2. The tolerance accounts for known API inconsistencies (e.g., UCDP excludes ~1000 type_of_violence=4 events from results while counting them in TotalCount).
3. Violations raise `ValueError` and halt the pipeline.

### Dual-threshold assertions for datasets with fixed-offset inconsistencies

When an API has a known fixed-count inconsistency (not proportional to dataset size), a percentage-only threshold fails for small datasets. Use a dual threshold: the shortfall must exceed BOTH a percentage AND an absolute count.

Current implementation for UCDP: shortfall must exceed both 1% AND 1100 events. This tolerates the ~1000 type_of_violence=4 offset for candidate versions (200-2300 events) while catching genuine truncation like the page_size=50000 bug (50,000-event shortfall).

### Rate-limit recovery at the pagination layer

When an API uses non-standard HTTP status codes for rate limiting (e.g., UCDP uses 400 instead of 429), handle rate-limit retry at the pagination layer rather than the HTTP retry layer. The pagination context (the request was valid for earlier pages) is what makes the retry safe. ~~The HTTP retry layer should continue to fail fast on 4xx, since most client errors are not retryable.~~ **Amended 2026-10-21 — see below.**

### Amendment 2026-10-21 — 429 is retried at the HTTP layer (#511, C-72)

The struck sentence above read: *"The HTTP retry layer should continue to fail fast on 4xx, since
most client errors are not retryable."* It is **narrowed**, not reversed, to:

> The HTTP retry layer should continue to fail fast on 4xx **except the statuses whose meaning is
> "later" rather than "never" — currently 429 alone.**

**Why the original rule does not cover 429.** This section's own justification is *"the pagination
context is what makes the retry safe"*, and it is written about **ambiguous** status codes — the
parenthetical names the case exactly: UCDP signals a rate limit as **400**, which could equally mean
a malformed request. Only the knowledge that earlier pages succeeded makes retrying a 400 safe, and
only the pagination layer has that knowledge. **429 is never ambiguous.** RFC 6585 §4 gives it one
meaning, for every caller, with no context required — so the premise that confined the decision to
the pagination layer does not apply to it.

**What this changes.** `datafactory_http.retry.request_with_retry` now retries 429 using a
rate-limit-scale backoff (30s base, doubling, 120s ceiling) that honours `Retry-After` when present.
Every other 4xx still fails fast and loud. All eleven call sites inherit it, which was the point:
the 2026-10-21 production abort was ACLED, but UCDP, SHDI, V-Dem, GHS-POP, GHS-BUILT-S, GAUL and the
shapefile harvester shared the defect.

**What this does not change.** **UCDP's 400 handling stays exactly where it is**, at the pagination
layer in `fetch_paginated()` (`sources/ucdp_annual.py`), unchanged. That is this section's actual
content and it remains correct. A 400 must not be retried by a layer that cannot tell a rate limit
from a bad request.

**Why it was not already caught.** C-72 recorded this defect on 2026-04-26 — the same day as this
ADR — and deferred it at Tier 4 with the note *"not observed to date"*. The 2026-10-21 00:07 UTC
monthly cron abort fired that trigger.

**A larger `Retry-After` fails loud rather than being honoured.** A server asking for longer than the
120s ceiling is declaring a quota block, not a burst; Cloudflare-fronted 429s routinely carry 3600 or
86400, and sleeping one off would stall an unattended monthly cron for a day. ADR-011 forbids that
more clearly than it forbids retrying. The refusal names the requested value.

---

## Rationale

### Why count verification, not just schema validation?

A Parquet file with 335,918 correctly-formatted rows is structurally valid. Schema checks pass. Provenance digests are computed and recorded. The file is a legitimate artifact — it just contains 87% of the data. Only a count check catches this class of failure.

### Why at the harvest layer?

Downstream layers (consolidation, viewpoint, compilation) receive their input as files on disk. They have no way to know what the API promised. The harvest is the only point where the expected count is available.

### Why dual thresholds?

The UCDP API has a fixed ~1000-event inconsistency between TotalCount and actual results. For annual data (384K events), this is 0.26% — invisible. For candidate versions (200-2300 events), the same 1000-event offset is 40-100% of the total — a percentage-only threshold rejects every candidate version. The dual threshold (percentage AND absolute) accommodates fixed offsets at any dataset size.

---

## Consequences

### Positive

- Silent partial fetches are now impossible for any source using `fetch_paginated()`.
- The dual threshold is robust to both proportional and fixed-count API inconsistencies.
- Rate-limit backoff enables `page_size=1000` (correct results) without failing on the ~300-request rate limit.

### Negative

- The tolerance values (1%, 1100 events) are calibrated to the current UCDP API behavior. If the API changes its type_of_violence=4 handling, the thresholds may need recalibration.
- Rate-limit backoff adds up to 5 minutes of retry time per rate-limit hit. Annual harvest takes ~32 minutes with backoff vs ~20 minutes with `page_size=50000` (which is no longer safe to use).

---

## Implementation Notes

- `fetch_paginated()` in `datafactory_harvester/sources/ucdp_annual.py` implements the TotalCount assertion (v1.2.5) and rate-limit backoff (v1.2.6).
- Dual threshold added in v1.2.7.
- `harvest_ucdp.py` reverted from `page_size=50000` to default `page_size=1000` in v1.2.6.
- All three UCDP harvesters (annual, candidate, dot9) share `fetch_paginated()` and inherit these protections.
- ACLED `fetch_paginated()` in `datafactory_harvester/sources/acled.py` does not implement TotalCount verification — the ACLED API does not expose a total count in its response envelope. Downstream `validate_events()` catches schema violations but not silent count shortfalls.

### Amendment 2026-10-10 — ACLED's detection signal changed (#487)

The paragraph above used to end: *"Pagination terminates when a page returns fewer results than
`page_size`. This 'short page' heuristic detects complete pagination but cannot detect server-side
truncation within a page."* **That heuristic no longer exists.**

ACLED deprecated offset pagination on 2026-10-27, and `fetch_paginated()` now walks cursors and
terminates only on `next_cursor is null`. A short page is not evidence of anything under cursor
pagination, so the break that keyed on page length was deleted — keeping it would have truncated
harvests silently.

**The replacement is strictly better on this ADR's own terms.** `next_cursor` is a *server-declared*
continuation token, where the short-page rule was a *client-side inference*. The series boundary is
now stated by ACLED rather than guessed by us, and two conditions that previously could not be
distinguished from a clean finish now raise (ADR-011): a response missing `next_cursor`, and a
response with no events while the cursor is still live.

**What has NOT changed, and is the part that still matters here:** the envelope still reports
`count: null` and `total_count: null` — re-confirmed against a live cursor response on 2026-10-10,
on every page of an 8-page walk. So ACLED still has no server-declared total, this ADR's
`len(fetched) >= TotalCount * (1 - tolerance)` rule still cannot be applied to it, and the exemption
stands. Register entry C-153 is amended rather than closed for exactly this reason.

That leaves a gap this ADR should name explicitly, because it is the gap that produced this ADR in
the first place: nothing compares an ACLED harvest's event count against the previous harvest of the
same year. `n_events` is written to the ingestion ledger and never read back. A zero-event year
fails loud via `validate_events()`; **any non-zero shortfall is recorded as `outcome: "success"`
with a new, short content digest.** Tracked as #488 with register entry C-359. Parity between the
two pagination methods was measured before the deadline and the recording retained, since the
comparison can never be repeated — `reports/investigation_acled_cursor/findings.md`.

---

## References

- ADR-008 (Observability and Explicit Failure)
- ADR-011 (Fail Loud, No Stale Data Serving)
- ADR-018 (Operational Resilience Policy)
- `reports/post_mortems/2026-04-25_stale_zarr_store.md`
- `reports/technical_risk_register.md` C-137, C-138, C-139
