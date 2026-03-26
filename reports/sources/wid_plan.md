# Product Development Plan: WID Integration

**Date:** 2026-03-26
**Status:** Not started
**Dependency:** Country-to-cell broadcast infrastructure (shared with V-Dem; build V-Dem first)
**Goal:** Add WID inequality indicators to the assembled grid as country-level features, enabling inequality-conflict research.

---

## Source Profile

| Property | Value |
|----------|-------|
| Name | World Inequality Database (WID) |
| Resolution | Country-year |
| Temporal | Annual, varying depth (1900+ for rich countries, 1980+ for developing) |
| Format | CSV download or AJAX queries |
| Access | Free, no registration |
| Update frequency | Irregular (not on fixed schedule) |
| Relevant indicators | ~3-5 of hundreds (Gini, top shares, bottom shares) |

---

## Architecture Fit

```
Layer 1: Harvester → download CSV/query AJAX → per-indicator Parquet
Layer 2: Consolidation → trivial (country-year, single source)
Layer 3: Viewpoint → not applicable
    ↓
Country-to-cell broadcast → GAUL mapping → [T, H, W] arrays
(SAME INFRASTRUCTURE AS V-DEM — build once, reuse)
    ↓
Assembly: add to assembled grid
```

**Identical pattern to V-Dem.** The broadcast infrastructure built
for V-Dem serves WID with no additional work.

---

## Reuse from Existing Infrastructure

| Component | Reuse | Notes |
|-----------|-------|-------|
| Broadcast infrastructure | V-Dem M-V3 | Build for V-Dem; reuse for WID directly |
| GAUL admin codes | Already harvested | Country → cell mapping |
| Harvester pattern | `priogrid_static.py` | Download + parse + Parquet |
| Provenance | Standard pattern | Unchanged |

---

## New Infrastructure Needed

1. **Nothing beyond what V-Dem requires.** The broadcast
   infrastructure serves both sources. WID-specific work is only
   the harvester (download + parse) and indicator selection.

2. **Missing data handling** — WID has more coverage gaps than V-Dem
   (especially developing countries). Need a strategy: carry forward
   last known value, interpolate, or leave as NaN.

---

## Milestones

### M-W1: Investigation
- Download WID sample data
- Explore coverage for conflict-affected countries
- Select 3-5 indicators (Gini, top 10% share, bottom 50% share)
- Map WID country codes to GAUL codes
- Assess: is broadcasting defensible for conflict research?
- **DoD:** Indicator set chosen; coverage gaps documented; honest assessment written

### M-W2: Harvester
- `WidConfig` dataclass + `fetch_wid()` function
- Download/query, parse, write per-indicator Parquet
- Handle missing years (carry forward or NaN)
- Tests: Green/Beige/Red
- **DoD:** `fetch_source("wid", config=...)` produces Parquet with provenance

### M-W3: Assembly Integration
- Broadcast WID indicators to cells (reuse V-Dem infrastructure)
- Add to assembled grid
- Update zarr export
- **DoD:** Grid has WID indicators; values match source country data

### M-W4: Research
- Cross-tabulate inequality with UCDP conflict patterns (RQ-9)
- Test inequality × governance interaction (RQ-9 + RQ-7 combined)
- **DoD:** Findings documented; broadcasting limitations acknowledged

---

## Access Requirements

- **Cost:** Free
- **Registration:** None
- **API key:** None
- **License:** Open access (check specific terms for redistribution)
- **Citation:** Required

---

## Acceptance Criteria

1. WID indicators appear in assembled grid
2. Each cell's WID values match its country's values
3. Missing years handled consistently (documented strategy)
4. Broadcasting assumption explicitly documented in metadata
5. Provenance tracks WID data version and indicator selection
6. Research output: at least preliminary RQ-9 analysis
