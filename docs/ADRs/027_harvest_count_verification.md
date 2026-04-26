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

When an API uses non-standard HTTP status codes for rate limiting (e.g., UCDP uses 400 instead of 429), handle rate-limit retry at the pagination layer rather than the HTTP retry layer. The pagination context (the request was valid for earlier pages) is what makes the retry safe. The HTTP retry layer should continue to fail fast on 4xx, since most client errors are not retryable.

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

---

## References

- ADR-008 (Observability and Explicit Failure)
- ADR-011 (Fail Loud, No Stale Data Serving)
- ADR-018 (Operational Resilience Policy)
- `reports/post_mortems/2026-04-25_stale_zarr_store.md`
- `reports/technical_risk_register.md` C-137, C-138, C-139
