# Product Development Plan: ACLED Integration

**Date:** 2026-03-26
**Status:** Blocked (requires ACLED access)
**Goal:** Add ACLED conflict and protest events as a second event-level source on the PRIO-GRID, enabling cross-source conflict analysis.

---

## Source Profile

| Property | Value |
|----------|-------|
| Name | Armed Conflict Location & Event Data (ACLED) |
| Resolution | Point events (lat/lon) |
| Temporal | Daily events, 1997-present (varies by region) |
| Format | JSON/CSV via REST API |
| Access | Registration required; Research tier minimum |
| Update frequency | Daily (partner) / ~12-month lag (research) |
| Event types | Battles, explosions, violence, protests, riots, strategic |
| Size | ~1M+ events globally |

---

## Architecture Fit

```
Layer 1: Harvester → ACLED API (OAuth) → event Parquet files
Layer 2: Consolidation → separate event store (like UCDP)
Layer 3: Viewpoint → event type filtering, temporal aggregation
Layer 4: Compilation → lat/lon → PRIO-GRID cell (same as UCDP)
Assembly: add ACLED features alongside UCDP features
```

**Key similarity to UCDP:** Point events with lat/lon. Same spatial
binning logic. Same compilation path.

**Key differences from UCDP:**
- OAuth authentication (UCDP uses simple API token)
- Broader event taxonomy (6 types vs UCDP's 3 violence types)
- Daily granularity (UCDP is aggregated to monthly)
- Regional coverage varies (UCDP is more uniform)

---

## Reuse from Existing Infrastructure

| Component | Reuse | Notes |
|-----------|-------|-------|
| Harvester pattern | `ucdp_annual.py` | Both paginated API, Parquet storage. ACLED needs OAuth instead of token. |
| Retry logic | `request_with_retry()` | Same pattern, different auth headers. |
| Spatial binning | `grid_compilation.py` | Identical: lat/lon → pgid → grid cell. |
| Feature specs | `FeatureSpec` | Same: name, strategy, filter dict. |
| Provenance | Standard pattern | Unchanged. |
| Consolidation | `consolidators/ucdp.py` | Adapt: single source type, no vintage complexity. |

---

## New Infrastructure Needed

1. **OAuth authentication handler** — Token refresh logic (24h expiry,
   14-day refresh tokens). New for this codebase.

2. **Event type taxonomy** — ACLED has 6 event types with subtypes.
   Need a mapping to feature names (e.g., `acled_battle_count`,
   `acled_protest_count`, `acled_fatalities`).

3. **Cross-source analysis tools** — Compare ACLED and UCDP on the
   same grid. Not compilation infrastructure — research scripts.

4. **Possibly: new ADR** — If ACLED events are stored alongside UCDP
   in the same consolidated store, need dedup/distinction rules.
   If separate stores, simpler but more files.

---

## Milestones

### M-A1: Access Negotiation (BLOCKER)
- Register at acleddata.com
- Determine tier (Research / Partner)
- Get API credentials
- Review data sharing terms
- **DoD:** Working API credentials; terms reviewed

### M-A2: Investigation
- Explore API with sample queries
- Download Somalia 2020 as test dataset
- Compare with UCDP Somalia 2020 event-by-event
- Document schema, event types, precision indicators
- **DoD:** Schema documented; overlap with UCDP quantified

### M-A3: Harvester
- `AcledConfig` dataclass + `fetch_acled()` function
- OAuth token management
- Paginated API fetching
- Per-country or per-year Parquet storage
- Tests: Green/Beige/Red
- **DoD:** `fetch_source("acled", config=...)` produces Parquet with provenance

### M-A4: Compilation
- Define ACLED FeatureSpecs (battle count, protest count, fatalities, etc.)
- Compile to grid using existing compilation infrastructure
- New features appear in assembled grid
- **DoD:** Grid has ACLED features; values match source data

### M-A5: Cross-Source Analysis
- UCDP vs ACLED comparison on same grid
- Publish findings for RQ-8 and RQ-10
- **DoD:** Analysis documented with quantified agreement/disagreement

---

## Access Requirements

- **Cost:** Free for Research tier; Partner/Enterprise may have costs
- **Registration:** Required (acleddata.com account)
- **API key:** OAuth tokens (managed by harvester)
- **License:** Academic use typically free; redistribution may be restricted
- **Critical check:** Can we serve ACLED-derived data via our zarr store?
  Terms of use must be reviewed before integration.

---

## Acceptance Criteria

1. ACLED events harvested and stored with provenance
2. Events compiled to PRIO-GRID using same spatial binning as UCDP
3. At least 3 ACLED features in assembled grid (battle count, protest count, fatalities)
4. Cross-source comparison with UCDP documented
5. Data sharing terms allow serving via zarr (or terms documented if restricted)
