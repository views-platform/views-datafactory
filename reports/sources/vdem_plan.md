# Product Development Plan: V-Dem Integration

**Date:** 2026-03-26
**Status:** Not started
**Goal:** Add V-Dem democracy indicators to the assembled grid as country-level features broadcast to PRIO-GRID cells.

---

## Source Profile

| Property | Value |
|----------|-------|
| Name | Varieties of Democracy (V-Dem) |
| Resolution | Country-year |
| Temporal | Annual, 1789-2025 (dense from 1900) |
| Format | CSV download (~100 MB) |
| Access | Free, no registration |
| Update frequency | Annual (March release) |
| Relevant indicators | ~10 of 531 (high-level indices) |

---

## Architecture Fit

```
Layer 1: Harvester → download CSV, write per-indicator Parquet
Layer 2: Consolidation → trivial (country-year, no dedup needed)
Layer 3: Viewpoint → not applicable (no survivorship decisions)
    ↓
NEW: Country-to-cell broadcast → GAUL mapping → [T, H, W] arrays
    ↓
Assembly: add to assembled grid alongside UCDP + static + admin
```

**Key difference from UCDP:** No consolidation complexity (single
source, no versions), no viewpoint decisions. The complexity is in
the spatial broadcast step.

---

## Reuse from Existing Infrastructure

| Component | Reuse | Notes |
|-----------|-------|-------|
| Harvester pattern | `priogrid_static.py` | Both download + parse + Parquet. V-Dem is CSV instead of API. |
| GAUL admin codes | `gaul_admin.py` output | Already harvested. Provides country → cell mapping. |
| Assembly broadcast | `assemble_grid.py` | Already broadcasts admin codes. Needs generalization. |
| Provenance | `append_ledger_entry()` | Standard pattern. |
| Config pattern | Frozen dataclass | Standard pattern. |

---

## New Infrastructure Needed

1. **Country-to-cell broadcast module** — Given (country_code, year,
   value) records and the GAUL country grid, produce a [T, H, W]
   array where each cell gets the value of its country for that
   year. This is reusable for V-Dem, WID, and any future
   country-level source.

2. **Annual-to-monthly expansion** — V-Dem is annual; grid is monthly.
   Need a strategy (constant within year is simplest and defensible).

3. **Country code mapping table** — V-Dem country codes → GAUL codes.
   May require manual curation for ~10-20 edge cases (border changes,
   disputed territories, small states).

---

## Milestones

### M-V1: Investigation
- Download V-Dem v16 dataset
- Explore coverage, identify indicator selection
- Build V-Dem → GAUL country code mapping
- Decide interpolation strategy
- **DoD:** Mapping table covers 95%+ of countries; indicator set chosen

### M-V2: Harvester
- `VdemConfig` dataclass + `fetch_vdem()` function
- Download, parse CSV, write per-indicator Parquet
- Tests: Green/Beige/Red following existing pattern
- **DoD:** `fetch_source("vdem", config=...)` produces Parquet with provenance

### M-V3: Broadcast Infrastructure
- Country-to-cell broadcast function (reusable)
- Input: country-level Parquet + GAUL grid
- Output: [T, H, W] array (monthly, broadcast from annual)
- Tests: known country → correct cells get value
- **DoD:** Broadcast produces correct spatial distribution for test country

### M-V4: Assembly Integration
- Add V-Dem features to assembled grid
- Update feature_names.json, provenance, zarr export
- **DoD:** Assembled grid includes V-Dem indicators; zarr store updated

---

## Access Requirements

- **Cost:** Free
- **Registration:** None
- **API key:** None
- **License:** Creative Commons (CC-BY-SA for academic use)
- **Citation:** Required (V-Dem Codebook provides citation format)

---

## Acceptance Criteria

1. V-Dem indicators appear in the assembled grid
2. Each cell's V-Dem values match its country's values
3. Temporal coverage: annual values broadcast to monthly
4. Provenance tracks V-Dem version and indicator selection
5. Zarr store includes V-Dem variables with correct metadata
6. Country code mapping documented (including mismatches)
