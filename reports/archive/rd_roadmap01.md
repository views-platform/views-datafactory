# R&D Roadmap v01 — Path to Production Parity

**Date:** 2026-03-21
**Supersedes:** rd_roadmap.md (2026-03-16)
**Status:** Active

---

## Where We Are

The system harvests UCDP annual and candidate data, consolidates into a lossless event store, builds opinionated viewpoints, and compiles onto the PRIO-GRID. The full 4-layer pipeline (ADR-012) runs end-to-end with 250 tests passing.

But the system **cannot reproduce what VIEWS production uses**. Production depends on UCDP's `.9` data stream — an undocumented, bespoke dataset containing exclusive events (count varies by version and year — from ~350 to ~2,600 per version) not available through any standard API endpoint. Our pipeline has no mechanism to harvest, consolidate, or build viewpoints from `.9` data.

Additionally, we discovered that UCDP candidate versions are mutable — the same version number can return different data at different times. This undermines reproducibility assumptions throughout the pipeline.

---

## Research Questions

### RQ-1: What is the .9 data stream?

**Status:** Partially answered. See `reports/dot9_investigation/`.

**Known:**
- Format `YY.9.MM`, available on public API from 18.9.1 through 26.9.2
- Contains exclusive events not in annual or candidate releases
- Undocumented — no UCDP codebook or specification exists
- Production depends on it monthly

**Open:**
- How does UCDP construct it? (Email pending to Håvard/Angelica)
- Why does it contain events not in any candidate release?
- Does the .9 apply internal consolidation (survivorship) rules?
- Is there a formal agreement for VIEWS to receive it?

**Why it matters:** We cannot achieve production parity without understanding and harvesting .9. The answer to this question gates all downstream work.

### RQ-2: How mutable is UCDP candidate data?

**Status:** Partially answered. See `reports/dot9_investigation/reproducibility_note.md`.

**Known:**
- All 14 candidate versions (25.0.1-26.0.2) gained exactly +1,000 events in a single bulk update
- 2024 versions are stable; 2025-2026 versions are mutable
- There appears to be an undocumented age boundary (~1 year) for version freezing

**Open:**
- How frequently does UCDP update candidate versions?
- Is the +1,000 pattern typical or a one-time correction?
- Are .9 versions also mutable?
- Does the annual dataset ever change after publication?

**Why it matters:** If data is mutable, version numbers are insufficient for reproducibility. Our vintage-aware consolidation (ADR-017) is designed for this, but we need to understand the update cadence to set re-harvesting schedules.

### RQ-3: Can we reconstruct .9 from annual + candidate?

**Status:** Answered — NO.

The .9 contains 13,005 events not in any annual or candidate release. Even after checking all 2024 candidate versions (24.0.1-24.0.12), only 99 of those events appeared (0.8% reduction). The .9 is a distinct data source, not a derivable consolidation.

**Implication:** The .9 must be harvested directly as a third source type.

### RQ-4: What defines "production parity"?

**Status:** Partially answered.

Production uses the GedLoader notebook to ingest `YY.9.MM` data with `fix_summary_events=True`. This involves:
1. Fetch .9 version
2. Filter: `priogrid_gid >= 1`, `type_of_violence < 4`
3. Assign month from `date_end` (not `date_start`)
4. Distribute summary events using `ceil()` (rounds up, inflates totals)
5. Filter for PG aggregation: `where_prec not in (4, 6)`
6. Aggregate by (pg_id, month_id, type_of_violence) → sum and count

**Open:**
- Are there additional transformations not visible in the notebook?
- Does the annual ingestion follow the same logic?
- How does production handle the annual-to-candidate transition?

### RQ-5: What is the statistical profile of the production data?

**Status:** Not started.

The original roadmap's RQ-1 asked for zero-inflation rate, tail distribution, spatial autocorrelation, and temporal persistence. This remains unanswered but depends on having production-parity data first.

### RQ-6: What can the revision history tell us?

**Status:** Not started. Depends on RQ-2.

With all 98 candidate versions (18.0.1-26.0.2) and all .9 versions (18.9.1-26.9.2) consolidated with vintage awareness, we could measure:
- How events are revised between candidate releases
- Whether .9 exclusive events eventually appear in annual releases
- Whether revision patterns are informative for uncertainty quantification

---

## Research Phases

### Phase 0: Clarify — COMPLETE (blocked items remain open)

- ~~Send email to Håvard/Angelica about .9 data lifecycle~~ Email sent 2026-03-21, awaiting response
- Document answers in `reports/dot9_investigation/` — done
- RQ-1 and RQ-2 open questions documented but not fully answered

### Phase 1: Build .9 Infrastructure — COMPLETE

- ~~Implement .9 harvester (`ucdp_dot9.py`)~~ Done (M1)
- ~~Extend consolidation to three source types~~ Done (M2)
- ~~Implement .9-aware survivorship strategy~~ Done (M3, `dot9_wins`)
- ~~Harvest full .9 history (18.9.1 through latest)~~ 78 of ~98 versions fetched; re-run needed for 25.9.x/26.9.x

### Phase 2: Achieve Production Parity — COMPLETE

- ~~Match production's `fix_summary_events` logic exactly~~ Done (M4, `ceil_split`)
- ~~Match production's filtering~~ Done (M5, priogrid_gid/type_of_violence/where_prec)
- ~~Compare output against production data event-by-event~~ 100% match on 27,853 non-expanded events
- ~~Document remaining discrepancies~~ `reports/dot9_investigation/parity_results.md`
- ~~Full pipeline including compilation~~ Done (`full_harvest.py` step 6/6)

### Phase 2a: PRIO-GRID Static Features (production quality)

Second data source. 34 static variables (terrain, resources, land cover) from the PRIO-GRID 2.0 API. Frozen datasets (2009-2015 vintages), 64,818 land cells each.

- P2a-1: CIC for `PriogridStaticConfig` (docs/CICs/)
- P2a-2: Tests — Green/Beige/Red, ~14 tests matching UCDP pattern
- P2a-3: Schema validation — type checks, structured validation
- P2a-4: ARCHITECTURE.md — package structure + key concepts
- P2a-5: Error handling — narrow exceptions (C-42 pattern)
- P2a-6: Revision detection — archive old snapshots on overwrite

**DoD:** Falsification audit on "priogrid static harvester is at UCDP quality" survives.

### Phase 2b: Operational Readiness

Prepare the system for production operation. Address operator visibility, documentation gaps, and test coverage for consumer-facing scripts.

- ~~P2b-1: `scripts/check_health.py`~~ Done. Reads all ledger files, reports last-successful timestamp per source, warns on stale data (C-51)
- ~~P2b-2: Document Parquet schema evolution~~ Done. Added to ADR-013 Notes section (C-52)
- ~~P2b-3: Tests for scripts~~ Done. `tests/test_scripts.py` validates all scripts have main(), argparse, __name__ guard (C-53)
- P2b-4: ~~Define falsification stub retirement policy~~ Done. Policy: resolved stubs are converted to passing assertions that verify the fix. Empirical data stubs (11 current) are retained as audit trail — they document UCDP data characteristics, not code bugs. Archive only when the empirical finding is superseded by new data.

**DoD:** All P2b items resolved. No operator-facing scripts without tests.

### Phase 3: Raster Data Sources (blocked on rasterio dependency)

Population, built-up area, nightlights, and other vulnerability proxies require raster-to-grid aggregation. This is blocked on adding `rasterio` (GDAL) as a dependency.

**Investigation findings (2026-03-23):**
- WorldPop 1km annual (2000-2020): best quality, direct HTTP download, ~1 GB/year
- GPW v4 at 0.5°: exact grid match but 5-year epochs only, requires SEDAC registration
- Monthly population data does not exist globally
- Temporal strategy: back-fill 1989-1999 with 2000, forward-fill 2021-2026 with 2020

**When unblocked:**
- P3-1: Raster-to-grid aggregation infrastructure (shared capability)
- P3-2: WorldPop population harvester (annual 2000-2020)
- P3-3: GHSL built-up area harvester (5-year epochs, primary vulnerability proxy)
- P3-4: Statistical characterization using combined UCDP + population + built-up data

### Phase 4: Synthetic Generation + Advanced Sources

- Build grid-native synthetic generators calibrated against real data
- Nighttime lights (requires flare masking — see vulnerability proxy survey)
- ACLED conflict data (second conflict source)
- Uncertainty propagation through the pipeline

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| UCDP discontinues .9 | Low | Critical | Archive all .9 snapshots; build independent consolidation as fallback |
| UCDP changes .9 format without notice | Medium | High | Content-digest comparison detects changes; vintage-aware storage preserves prior state |
| Candidate mutability makes vintage analysis unreliable | Medium | Medium | ADR-017 vintage-aware consolidation; re-harvest periodically |
| Production GedLoader has undocumented transformations | Medium | High | Compare output systematically; ask colleagues to review |
| Performance at full scale (384K events × 98 versions) | Low | Medium | Profile before scaling; compiler memory optimization (C-24) |
