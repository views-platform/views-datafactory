# ADR-032: Harvest Idempotence and Caching

**Status:** Accepted
**Date:** 2026-05-21
**Deciders:** Simon Polichinel von der Maase, Claude Code
**Extends:** ADR-008 (Observability and Explicit Failure), ADR-011 (Fail Loud, No Stale Data Serving), ADR-027 (Harvest Count Verification)

---

## Context

The data factory harvests from 7 external data sources (UCDP annual, candidate, dot9; ACLED; GHS-POP; PRIO-GRID static; GAUL admin). Each harvester independently implements caching to avoid re-fetching data that has already been successfully retrieved. Over time, three distinct caching implementations emerged:

1. **UCDP candidate/dot9:** Two-tier cache — file exists AND ledger digest matches, plus post-fetch digest comparison to detect source changes ("unchanged" heartbeat when content hasn't changed).
2. **ACLED:** Single-tier cache — file exists AND ledger has a digest for this version. No post-fetch digest comparison.
3. **GHS-POP:** Single-tier cache — file exists AND ledger digest matches. No change detection.

These three implementations converge on the same two-key pattern (file + ledger) but diverge on change detection, `--force` semantics, outcome vocabulary, and error recovery. The divergence is not accidental — it reflects genuine differences in source behavior (mutable vs immutable data, API-based vs file-based, single-version vs multi-version). But without a shared contract, each new source must rediscover these patterns by reading existing code.

### Incident: C-182

`last_digest_for_version` returned the `content_digest` from failed ledger entries, causing subsequent runs to treat a failed harvest as cached. Fixed by filtering on `outcome: "success"` (or absent, for backward compatibility).

---

## Decision

### Two-key cache: file existence AND successful provenance

A harvest version is cached if and only if:

1. The output file exists on disk at the expected path.
2. The provenance ledger contains a **successful** entry for that version with a `content_digest`.

Both conditions must hold. File existence alone is insufficient (partial write, orphan from a previous run). Ledger entry alone is insufficient (file may have been deleted or corrupted).

`last_digest_for_version` (versioned sources) and `last_digest` (non-versioned sources like UCDP annual) enforce condition 2 by accepting only entries with `outcome` in `("success", "unchanged")` or entries without an `outcome` field (backward compatibility). Entries with `outcome = "failed"` or `"cached"` are skipped. Both functions also skip entries that lack the `content_digest` field entirely, preventing malformed entries from shadowing valid ones.

### Source mutability determines cache tier

Not all sources need the same depth of cache validation:

| Source class | Mutability | Cache tier | Rationale |
|---|---|---|---|
| Immutable release | None | **Single-tier** — file + successful ledger entry | JRC GeoTIFF epochs, PRIO-GRID static. New data gets a new URL/filename; existing files never change. Re-downloading to compare digests is waste. |
| Mutable versioned | Monthly updates | **Two-tier** — single-tier + post-fetch digest comparison | UCDP candidate/dot9. Same version string, but content may change as UCDP curates events. Digest comparison detects silent updates. |
| Mutable partitioned | Ongoing corrections | **Single-tier** with full-year re-fetch on `--force` | ACLED. Historical years may receive retroactive corrections. Default: trust cache. Force: re-fetch and compare. |

Each harvester must declare its source mutability in its docstring and implement the corresponding tier.

### Cache key structure

The cache key is `(dataset_id, version_string)`, where:

- `dataset_id` is the `DATASET_ID` constant in each source module (e.g., `"ucdp_candidate"`, `"acled"`, `"ghspop"`).
- `version_string` is source-specific:
  - UCDP annual: full version string (e.g., `"25.1"`)
  - UCDP candidate: `YYMM` (e.g., `"2501"` for January 2025)
  - UCDP dot9: version string (e.g., `"25.0.9"`)
  - ACLED: `YYYY_YYYY` (e.g., `"2023_2023"`)
  - GHS-POP: `EYYYY` (e.g., `"E2020"`)

The file path is a deterministic function of the version string and config. No harvester may infer the version from the filename — the ledger is the authority (ADR-003).

### `--force` semantics

Every harvest script must accept `--force` (or `force_refresh=True`):

- **When false (default):** Check the two-key cache. Skip if cached.
- **When true:** Bypass the cache entirely. Re-fetch, re-validate, re-record provenance. For two-tier sources, the digest comparison still runs (detects if the source has changed since last forced fetch).

`--force` never deletes existing data. It fetches fresh and overwrites atomically (write to temp, then rename).

### Outcome vocabulary

Every ledger entry must include an `outcome` field with one of these values:

| Outcome | Meaning | Recorded when |
|---|---|---|
| `"success"` | Fetch, validation, and storage all succeeded | After writing the output file and computing its digest |
| `"cached"` | Skipped because the cache was valid | After verifying file + ledger |
| `"unchanged"` | Fetched but content matches previous (two-tier only) | After digest comparison shows no change |
| `"failed"` | An error occurred during fetch or validation | In the `except` handler, before re-raising |

Only `"success"` and `"unchanged"` entries are considered valid cache hits by `last_digest_for_version` and `last_digest`. `"cached"` entries are informational (they don't add a new digest). `"failed"` entries are never used for cache decisions.

### Discovery probing is separate from data fetching

UCDP candidate/dot9 harvesters must discover available versions before fetching. Discovery probes the API with small requests (`pagesize=1`) to enumerate the version space. This is architecturally separate from data fetching:

- Discovery runs unconditionally (not cached) — the version space is the harvester's input, not its output.
- Each discovered version is then checked against the cache independently.
- A future optimization (D-26) may cache discovery results, but this ADR does not require it.

---

## Rationale

### Why two keys, not just the file?

A file can exist without provenance (orphan from a manual copy, interrupted write, or pre-provenance version of the code). A file with provenance can exist after a failed attempt (C-182). The two-key check ensures that only fully-validated, successfully-completed harvests are treated as cached.

### Why not always use two-tier caching?

For immutable sources (GHS-POP, PRIO-GRID static), the only way to detect a change is to re-download the entire file and compare digests. GHS-POP epochs are ~450 MB ZIPs. Re-downloading on every run to confirm immutability is waste — the source provider guarantees immutability by convention (new data gets new URLs). If the convention breaks, `--force` provides the escape hatch.

### Why filter failed entries at the provenance layer, not the caller?

Every caller that uses `last_digest_for_version` or `last_digest` for cache decisions would need to independently check `outcome`. Moving the filter into the shared functions (provenance layer) prevents the bug class entirely. No caller can accidentally use a failed digest.

### Why backward compatibility for missing `outcome`?

Early ledger entries (pre-v1.2) don't have an `outcome` field. These are necessarily successful (the code path that wrote them didn't have failure recording). Rejecting them would force a full re-harvest of all existing data on upgrade.

---

## Consequences

### Positive

- **Safe retry after failure:** A failed harvest followed by a retry will correctly re-fetch, because `last_digest_for_version` and `last_digest` skip failed entries (C-182 fix).
- **Source-appropriate caching:** Immutable sources don't waste bandwidth on redundant downloads. Mutable sources detect silent updates.
- **Shared vocabulary:** Harvesters with outcome vocabulary use the same outcome values, making ledger analysis consistent. Pre-outcome harvesters (PRIO-GRID shapefile) rely on backward compatibility.
- **`--force` is always safe:** Re-fetching never deletes data; it atomically replaces.

### Negative

- **Single-tier sources miss silent updates:** If JRC silently replaces a GeoTIFF at the same URL, we won't detect it without `--force` (C-185). Accepted risk for immutable-by-convention sources.
- **ACLED file integrity unchecked:** `_year_is_cached` checks file existence but not content integrity (C-184). A truncated file passes the cache check. Downstream Parquet readers provide a secondary signal (they fail on truncated files), but the error message is confusing. Future improvement: add a digest comparison to `_year_is_cached`.
- **Discovery probing is expensive:** UCDP candidate/dot9 make 98+ API calls per run for discovery (C-181). Not addressed here — tracked as D-26 for future optimization.

---

## Implementation Notes

- `last_digest_for_version` and `last_digest` in `datafactory_provenance/digests_and_ledgers.py` filter by `outcome` and skip entries missing the digest field, as of v1.2.18.
- UCDP annual (`ucdp_annual.py:fetch_ucdp_annual`): uses `last_digest` (non-versioned). Records `"failed"` on validation failure.
- UCDP candidate (`ucdp_candidate.py:_fetch_version`), UCDP dot9 (`ucdp_dot9.py:_fetch_dot9_version`): uses `last_digest_for_version`. Two-tier with `"unchanged"` heartbeat. Records `"failed"` on validation failure.
- ACLED (`acled.py:_year_is_cached`, `_fetch_single_year`): uses `last_digest_for_version`. Single-tier with `"cached"` outcome on skip. Records `"failed"` on validation failure.
- GHS-POP (`ghspop.py:_fetch_epoch`): uses `last_digest_for_version`. Single-tier with `"cached"` outcome on skip. Records `"failed"` on download, ZIP, or extraction failure.
- PRIO-GRID static (`priogrid_static.py:_fetch_variable`): uses `last_digest_for_version`. Records `"failed"` on empty or invalid API response.
- GAUL admin (`gaul_admin.py:fetch_gaul_admin`): uses `last_digest_for_version`. Records `"failed"` in ledger via `append_ledger_entry` in the except block wrapping `_write_variable` (C-188, fixed v1.2.18).
- PRIO-GRID shapefile (`shapefile_harvester.py:fetch_shapefile`): uses `last_digest` (non-versioned). Pre-outcome harvester — entries use `"changed": True/False` instead of outcome vocabulary. No failure recording (C-186). Backward-compatible: entries without `outcome` are accepted by the digest functions.

---

## References

- ADR-003 (Authority of Declarations Over Inference)
- ADR-008 (Observability and Explicit Failure)
- ADR-011 (Fail Loud, No Stale Data Serving)
- ADR-027 (Harvest Count Verification)
- `reports/technical_risk_register.md` C-44, C-46, C-181, C-182, C-183, C-184, C-185, C-186, C-187, C-188, D-26, D-27, D-28, D-29
