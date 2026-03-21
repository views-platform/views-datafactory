
# ADR-017: Vintage-Aware Consolidation

**Status:** Accepted (implementation deferred)
**Date:** 2026-03-21
**Deciders:** Simon Polichinel von der Maase, Claude Code
**Extends:** ADR-013 (Consolidation Principles)

---

## Context

ADR-013 mandates that the consolidated event store is lossless, append-only, and bitemporal — preserving both valid time (when events happened) and transaction time (when we learned about them).

Empirical investigation on 2026-03-21 revealed that UCDP candidate versions are mutable: the same version number can return different data at different times. All 14 candidate versions from 2025-2026 gained exactly +1,000 events each within 24 hours, while 2024 versions remained stable. This appears to be a bulk retroactive update by UCDP, not organic growth.

The current consolidator deduplicates on `(id, _source_type, _source_version)`. This means:

- If we re-fetch a mutated version, the new records have the same dedup key as the old ones
- Dedup either skips the update (losing new data) or overwrites the old data (losing the prior vintage)
- Both outcomes violate ADR-013 (lossless) and ISO GUM (uncertainty metadata must propagate)

The problem is not specific to UCDP — any data source that updates releases retroactively creates the same issue. The solution must be source-agnostic.

---

## Decision

The consolidated event store must preserve **all vintages** of the same source version. Two fetches of the same version that return different data must both be preserved as distinct records.

> Deduplication is content-addressed, not version-addressed.
> Identical data is deduplicated. Updated data creates a new vintage.
> The version number is necessary but not sufficient for deduplication.

---

## Mechanism

### Additional metadata columns

Two columns are added to every consolidated record:

| Column | Type | Description |
|--------|------|-------------|
| `_harvest_digest` | str | Content digest of the source Parquet file at harvest time |
| `_harvest_timestamp` | str | UTC ISO 8601 timestamp of when the source was fetched from the API |

These supplement the existing `_source_type`, `_source_version`, and `_ingested_at` columns.

### Deduplication key

The dedup key changes from:
```
(id, _source_type, _source_version)
```
to:
```
(id, _source_type, _source_version, _harvest_digest)
```

This ensures:
- **Identical re-fetch** (same data, same digest): deduplicated correctly, no false duplicates
- **Updated re-fetch** (different data, different digest): both vintages preserved as distinct records
- **Content-addressed**: the digest is deterministic — same bytes always produce the same digest, regardless of fetch timing

### Survivorship implications

When multiple vintages exist for the same `(id, _source_type, _source_version)`, the viewpoint survivorship strategy must decide which vintage to use. Possible strategies:

- **Latest vintage** (default): prefer the most recent `_harvest_timestamp` for each `(id, source_type, version)` group
- **First vintage**: prefer the oldest, preserving what was originally known at first fetch
- **Specific point-in-time**: return the vintage closest to a specified date

These are viewpoint-layer decisions (ADR-014), not consolidation-layer decisions. The consolidator preserves all vintages; the viewpoint selects.

---

## Rationale

### Why content-addressed dedup?

Version-addressed dedup (`_source_version` only) assumes versions are immutable. This assumption was falsified on 2026-03-21 (see `reports/dot9_investigation/findings.md`, section 6.3 and `tests/test_falsification_candidate_mutability.py`).

Content-addressed dedup handles both mutable and immutable sources correctly:
- If the source is immutable: the digest never changes, so re-fetches are always deduplicated. No storage overhead.
- If the source is mutable: each update produces a new digest, preserving both vintages. Storage grows proportionally to actual changes.

### Why both digest and timestamp?

The digest is the dedup key (deterministic, content-addressed). The timestamp is for human-readable provenance and point-in-time queries. Together they answer: "What data did we have, and when did we get it?"

### Alignment with established frameworks

| Framework | How this ADR applies it |
|-----------|------------------------|
| **Bitemporal modeling** | `_harvest_timestamp` is a second dimension of transaction time (when we observed this vintage of the data) |
| **Data vintages** (economics) | Every fetch creates a vintage. Vintages are never overwritten. |
| **ISO GUM** | Measurement uncertainty includes "which version of the source did we use?" The digest answers this precisely. |
| **Content-addressable storage** (Git, IPFS) | The same principle: identity is determined by content, not by name. |

---

## Implementation Status

**Deferred.** The design is accepted. Implementation is deferred pending:

1. UCDP clarification on their version mutability policy (email sent 2026-03-21)
2. Confirmation that the +1,000 bulk update pattern is representative (needs more observation points)
3. Decision on whether to re-harvest existing data with vintage tracking

When implemented, the changes affect:
- `src/datafactory_consolidation/consolidators/ucdp.py` — add harvest metadata columns, change dedup key
- `src/datafactory_consolidation/consolidation_result.py` — add vintage count to result
- `src/datafactory_viewpoint/survivorship.py` — add vintage-aware strategies
- `tests/test_consolidation.py` — update dedup tests

No changes needed to:
- ADR-013 (already requires bitemporal tracking — this ADR is a more faithful implementation)
- The compilation layer (reads viewpoint output, doesn't care about vintages)
- The harvester (already computes and records content digests)

---

## Consequences

### Positive

- Every fetch is a timestamped, content-addressed archive — nothing is ever lost
- Mutable and immutable sources are handled correctly by the same mechanism
- Revision dynamics become measurable (how does the same version change over time?)
- Point-in-time reproducibility: "give me the data as we knew it on March 1"
- Aligns with ISO GUM, bitemporal modeling, and data vintage best practices

### Negative

- Storage grows with each distinct vintage (proportional to actual changes, not to re-fetch count)
- Survivorship strategies become more complex (must consider vintage, not just source type)
- Re-harvesting the full candidate history with vintage tracking is a large operation

These costs are accepted. The alternative — silently losing data updates or prior vintages — is a methodological error.

---

## Notes

This ADR extends ADR-013 by making the "transaction time" dimension more granular. ADR-013 tracks `_ingested_at` (when we consolidated). This ADR adds `_harvest_timestamp` (when we fetched from the API) and `_harvest_digest` (content fingerprint of what we fetched). Together, these create a complete provenance chain from API response to compiled grid.

The evidence for this decision is documented in:
- `reports/dot9_investigation/findings.md` (section 6.3: candidate mutability)
- `reports/dot9_investigation/reproducibility_note.md`
- `tests/test_falsification_candidate_mutability.py`
