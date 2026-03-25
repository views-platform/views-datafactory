# Product Development Plan v02 — Beyond Production Parity

**Date:** 2026-03-25
**Supersedes:** product_development_plan01.md (2026-03-21)
**Status:** Active
**Goal:** Production-parity data factory with quality infrastructure for scaling to new sources and consumers.

---

## Current State

### What Works

| Layer | Component | Status | Tests |
|-------|-----------|--------|-------|
| 0 | Provenance (digests, ledgers, locking, rotation, schema fingerprint) | Done | 30 |
| 1 | PRIO-GRID backbone (grid, temporal, parity, shapefile, land mask) | Done | 67 |
| 1 | Harvester — UCDP annual | Done | 15 |
| 1 | Harvester — UCDP candidate | Done | 16 |
| 1 | Harvester — UCDP .9 | Done | 14 |
| 1 | Harvester — PRIO-GRID static (34 variables) | Done | 13 |
| 1 | Harvester — GAUL admin boundaries (3 levels) | Done | 12 |
| 2 | Consolidation (3-source, vintage-aware, atomic writes) | Done | 35 |
| 3 | Viewpoint (survivorship, distribution, filtering, profiles) | Done | 55 |
| 4 | Grid compilation (columnar placement, feature disaggregation) | Done | 25 |
| — | Adapters (FeatureFrame, grid↔DataFrame, grid↔FeatureFrame, shape validation) | Done | 35 |
| — | DAG enforcement | Done | 1 |
| — | Integration tests | Done | 4 |
| — | Script structure tests | Done | 10 |
| — | Falsification stubs (empirical UCDP data documentation) | Done | 11 (marker-gated) |

**Total: 376 passed, 0 skipped**

### Architecture

- **8 packages** under `src/datafactory_*`: provenance, priogrid, harvester, synthetic (stub), consolidation, viewpoint, compilation, adapters
- **5 data sources**: UCDP annual, UCDP candidate, UCDP .9, PRIO-GRID static, GAUL admin boundaries
- **21 ADRs** (10 constitutional + 11 project-specific)
- **16 CICs** (class intent contracts)
- **Technical risk register** (ADR-020): 80 concerns tracked, 56 resolved, 24 deferred with triggers

### Production Parity — ALL CRITERIA MET (2026-03-21)

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Harvest all three UCDP streams | MET | annual, candidate, .9 harvesters |
| Consolidated store with vintage tracking | MET | ADR-017 dedup, schema fingerprint |
| <5% event-level discrepancy | EXCEEDED | 100% match on 27,853 non-expanded events |
| All discrepancies documented | MET | `reports/dot9_investigation/parity_results.md` |
| Full pipeline end-to-end | MET | harvest → consolidate → viewpoint → compile → assemble |

### Quality Infrastructure Added (2026-03-22 to 2026-03-25)

| Deliverable | Concern | Description |
|-------------|---------|-------------|
| GAUL admin harvester | — | Country, province, district codes on PRIO-GRID |
| Adapters module | — | FeatureFrame, grid conversions, roundtrip tests |
| Grid shape validation | C-73 | Catches transposed grids at adapter boundary |
| Atomic Parquet writes | C-67 | Temp file + rename prevents crash corruption |
| Stale lock detection | C-68 | 5-minute staleness check on .lock files |
| Schema fingerprint | C-69 | Drift detection in consolidation ledger |
| Viz style consolidation | ADR-019 | Shared `viz_style.py` for all plot scripts |
| Risk register formalized | ADR-020 | Active + resolved archive split |
| Falsification markers | C-76 | `@pytest.mark.falsification` + `--run-falsification` |
| Retired scaffolding | — | `visualize_grid.py`, `smoke_test.py` |

---

## Milestones (All Complete)

| Milestone | Description | Status |
|-----------|-------------|--------|
| M1 | .9 harvester | Complete |
| M2 | Three-source consolidation | Complete |
| M3 | .9-aware survivorship (`dot9_wins`) | Complete |
| M4 | Production-parity summary handling (`ceil_split`) | Complete |
| M5 | Production filtering rules | Complete |
| M6 | End-to-end production parity test | Complete |

---

## Operational Concerns

All Tier 1-3 concerns resolved. Remaining 24 items are Tier 4 deferrals
with explicit trigger conditions. See `reports/technical_risk_register.md`.

Key deferred items by category:
- **Before production deployment:** D-03 (resilience policy), C-29 (e2e test)
- **Before scaling:** C-30 (perf test), C-70/71 (circuit breaker, jitter)
- **On code growth:** C-44 (harvest template on 4th source), C-80 (registry on 6th)
- **On external change:** C-36/37/45 (UCDP schema changes)

---

## Architecture References

| ADR | Relevance |
|-----|-----------|
| ADR-012 | 4-layer graph architecture |
| ADR-013 | Consolidation: lossless, append-only, bitemporal |
| ADR-014 | Viewpoints: disposable, rebuildable, versioned |
| ADR-015 | UCDP consolidation specifics |
| ADR-016 | Viewpoint profiles (named presets) |
| ADR-017 | Vintage-aware consolidation (content-digest dedup) |
| ADR-018 | Operational resilience policy |
| ADR-019 | Visualization style guide |
| ADR-020 | Technical risk register |
