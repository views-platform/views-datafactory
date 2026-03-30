# R&D Roadmap v02 — Beyond Production Parity

**Date:** 2026-03-25
**Supersedes:** rd_roadmap01.md (2026-03-21)
**Status:** Active

---

## Where We Are

The data factory is feature-complete for UCDP conflict data on the PRIO-GRID.
Five data sources (UCDP annual, candidate, .9, PRIO-GRID static, GAUL admin
boundaries) flow through the 4-layer graph (ADR-012) to produce assembled
grids with ~39 features. Production parity is achieved (100% match on
non-expanded events). The codebase has 381 tests, 22 ADRs, 16 CICs, and a
formalized technical risk register (ADR-020) with 56 of 80 concerns resolved.

The last development sprint (2026-03-22 to 2026-03-25) focused on quality:
GAUL admin boundaries, consumer-facing adapters, visualization consolidation,
grid shape validation, atomic writes, stale lock detection, schema fingerprinting,
and governance formalization.

---

## Research Questions

### RQ-1: What is the .9 data stream?

**Status:** Partially answered. Email sent to UCDP (2026-03-21), awaiting response.

**Known:** Format `YY.9.MM`, available from 18.9.1, contains 13,005 exclusive
events not in annual or candidate releases. Undocumented by UCDP.

**Open:** How does UCDP construct it? Why exclusive events? Does it apply
internal survivorship? Is there a formal data sharing agreement?

### RQ-2: How mutable is UCDP candidate data?

**Status:** Partially answered.

**Known:** All 14 candidate versions (25.0.1-26.0.2) gained +1,000 events in
a bulk update. 2024 versions stable; 2025-2026 mutable. Undocumented age
boundary (~1 year) for version freezing.

### RQ-3: Can we reconstruct .9 from annual + candidate?

**Status:** Answered — NO. The .9 must be harvested as a distinct source.

### RQ-4: What defines "production parity"?

**Status:** Answered. Production GedLoader logic documented and matched:
survivorship, ceil_split distribution, priogrid/violence/where_prec filtering.

### RQ-5: What is the statistical profile of the production data?

**Status:** Not started. Ready to begin — assembled grid exists with all
features. Needs: zero-inflation rate, tail distribution, spatial
autocorrelation, temporal persistence, covariate correlations.

### RQ-6: What can the revision history tell us?

**Status:** Not started. Needs full candidate + .9 harvest (78 of ~98 .9
versions currently fetched). With complete vintage data: measure revision
patterns, track .9 exclusive event lifecycle, assess uncertainty implications.

---

## Completed Phases

### Phase 0: Clarify — COMPLETE
Documented .9 data stream, candidate mutability, production GedLoader logic.

### Phase 1: Build .9 Infrastructure — COMPLETE
Harvester, three-source consolidation, .9-aware survivorship, full .9 history
(78 of ~98 versions fetched).

### Phase 2: Achieve Production Parity — COMPLETE
100% match on 27,853 non-expanded events. Full pipeline: harvest → consolidate
→ viewpoint → compile → assemble.

### Phase 2a: PRIO-GRID Static Features — COMPLETE
34 static variables from PRIO-GRID 2.0 API. Falsification audit survived.

### Phase 2b: Operational Readiness — COMPLETE
Health check script, schema evolution documentation, script tests, falsification
stub retirement policy.

### Phase 2c: Data Quality & Consumer Readiness — COMPLETE (2026-03-25)
- GAUL 2024 admin boundary harvester (3 levels: country, province, district)
- `datafactory_adapters` module: FeatureFrame, grid↔DataFrame, grid↔FeatureFrame
  roundtrip with shape validation (C-73)
- Visualization consolidation: shared `viz_style.py` module (ADR-019)
- Production hardening: atomic Parquet writes (C-67), stale lock detection (C-68),
  schema fingerprint in consolidation ledger (C-69)
- Technical risk register formalized (ADR-020): split to active + archive
- Falsification marker system: `@pytest.mark.falsification` + `--run-falsification`
- Retired superseded scaffolding: `visualize_grid.py`

---

## Next Phases

### Phase 3: Raster Data Sources — BLOCKED on rasterio

Population, built-up area, nightlights require raster-to-grid aggregation.
Blocked on adding `rasterio` (GDAL) as a dependency.

**Investigation findings (2026-03-23):**
- WorldPop 1km annual (2000-2020): best quality, direct HTTP download
- GPW v4 at 0.5°: exact grid match but 5-year epochs, requires registration
- Temporal strategy: back-fill 1989-1999 with 2000, forward-fill 2021-2026 with 2020

**When unblocked:**
- P3-1: Raster-to-grid aggregation infrastructure
- P3-2: WorldPop population harvester
- P3-3: GHSL built-up area harvester
- P3-4: Statistical characterization with combined data

### Phase 4: Synthetic Generation + Advanced Sources

- Grid-native synthetic generators calibrated against real data
- Nighttime lights (requires flare masking)
- ACLED conflict data (second conflict source)
- Uncertainty propagation through the pipeline

---

## Next Directions (not yet sequenced)

These are the natural next moves. Order depends on priorities and blockers.

### Outward — Building on the foundation

1. **Metric lab integration** — First real consumer. The `datafactory_adapters`
   module (FeatureFrame, grid conversion) is the handoff point. Needs: define
   the contract, test the roundtrip with real metric lab code, verify month_id
   epoch alignment.

2. **Full-scale .9 harvest** — 78 of ~98 versions fetched. Re-run harvest for
   25.9.x/26.9.x to complete the history. Enables RQ-6.

3. **Rasterio dependency** — Unblock Phase 3. Investigate uv-compatible GDAL
   installation or conda/mamba fallback.

### Research — Using the data

4. **RQ-5: Statistical profile** — The assembled grid has ~39 features across
   456 months and 259,200 cells. Characterize: zero-inflation, spatial
   autocorrelation, temporal persistence, feature correlations. This is the
   "what does the data look like" question.

5. **RQ-6: Revision history** — With full candidate + .9 history, measure how
   events change between releases. Potential for uncertainty quantification.

6. **RQ-1 follow-up** — If UCDP responds to the .9 email, update the data
   stream documentation and adjust the pipeline accordingly.

---

## Risk Register

Active concerns tracked in `reports/technical_risk_register.md` (ADR-020).
56 of 80 concerns resolved. 24 deferred with explicit trigger conditions.
No Tier 1 code concerns remain; the one open Tier 1 item (D-03: operational
resilience) is a design policy question, not a code defect.
