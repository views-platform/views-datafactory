# ADR-045: Data Soundness Invariants Across Layers

**Status:** Accepted
**Date:** 2026-06-18
**Supersedes:** None
**Related:** ADR-012 (graph architecture), ADR-023 (viewpoint invariants), ADR-024 (compilation grid invariants), ADR-040 (count conservation)

## Context

Data soundness invariants are scattered across three ADRs (023, 024, 040) with no single document defining what "soundness" means for the assembled grid or how invariants chain across layers. This ADR consolidates the definition and maps the current state of verification.

## Decision

**A grid is "sound" when every layer boundary preserves its documented invariants.**

Soundness is verified at layer boundaries, not end-to-end. This matches the graph architecture (ADR-012): layers are decoupled by the filesystem, and each boundary has its own invariant contract. An end-to-end invariant would require coupling layers that the architecture deliberately separates.

### Feature Type Distinction

Not all invariants apply to all features:

| Feature type | Examples | Aggregation semantics | Conservation applies |
|---|---|---|---|
| Extensive (counts) | `ged_sb_best`, `acled_count_*` | Summation | Yes (ADR-040) |
| Intensive (indices) | `vdem_*`, `shdi_*`, `ghsbuilts_*` | Averaging | No |
| Static (categorical) | `gaul0_code`, `pgid` | Mode/majority | No |

Extensive features must conserve: `input = placed + excluded`. Intensive features must not be summed across spatial cells (ADR-040). Confusing the two silently produces wrong numbers.

### Invariant Chain

| Boundary | What must hold | Source ADR |
|---|---|---|
| **Harvest output** | Raw data written atomically (temp + rename); content digest recorded in provenance ledger | ADR-011, event_store.py |
| **Harvest -> Consolidation** | Lossless append; no row modification; deduplication by event ID preserves latest version | ADR-023 |
| **Consolidation -> Viewpoint** | Count conservation: `placed + filtered = input` with per-reason exclusion counts logged; summary event detection formula (ADR-023); month assignment from `date_end` | ADR-023, ADR-040 |
| **Viewpoint -> Compilation** | Column schema match (required fields not stripped); spatial binning via floor-based cell assignment; temporal binning at month precision; dimension order [T, H, W, C] | ADR-024 |
| **Compilation -> Assembly** | All 259,200 cells present; feature stacking in declaration order; `feature_names.json` sidecar matches channel dimension | ADR-024 |
| **Assembly -> Query** | Read-back fidelity (mmap returns identical bytes); region subsetting preserves values; feature selection by name matches channel index | ADR-024 |
| **Assembly -> Country-Month** | For extensive features: `sum(grid cells in country) = CM(country)` with tolerance `rtol=1e-6, atol=1e-4` (float32 summation) | ADR-040 |

### Structural Invariant

**Layer independence (ADR-012):** No layer imports from a layer above it. Layers communicate through files on disk. This is enforced by `tests/test_import_enforcement.py`.

### Gap Table

| Invariant | Boundary | Tested | Test location | Gap |
|---|---|---|---|---|
| Atomic write (temp + rename) | Harvest output | Yes | `tests/test_consolidation.py::TestStoreCharacterization` | None |
| Lossless append | Harvest -> Consolidation | Partial | `tests/test_consolidation.py::TestStoreIoGreen` | No explicit lossless check |
| Summary event detection | Consolidation -> Viewpoint | Yes | `tests/test_viewpoint.py` | None |
| Month assignment from `date_end` | Consolidation -> Viewpoint | Yes | `tests/test_consumer_parity.py` | None |
| Count conservation | Viewpoint -> Compilation | Yes | `_conservation.py::assert_cm_conservation()` | Runtime assertion only; no dedicated test |
| Column schema match | Viewpoint -> Compilation | Yes | `tests/test_cross_layer_contracts.py` | None |
| Dimension order [T,H,W,C] | Compilation -> Assembly | Yes | `tests/test_compiler.py` | None |
| Spatial binning (floor-based) | Viewpoint -> Compilation | Yes | `tests/test_compiler.py` | None |
| 259,200 cells present | Compilation -> Assembly | Yes | `tests/test_grid.py::TestGridCharacterization` | None |
| Feature stacking order | Compilation -> Assembly | Partial | `tests/test_compiler.py` | Assembly-level not tested |
| Country broadcast (pregridded) | Compilation | Yes | `tests/test_compiler.py` | None |
| Hierarchical reconciliation | Assembly -> CM | Partial | `_conservation.py` | Only GAUL hierarchy; no test for GDL |
| Layer independence | All layers | Yes | `tests/test_import_enforcement.py` | None |
| Ledger rotation | Provenance | Yes | `tests/test_provenance.py::TestRotateLedgerCharacterization` | None |
| Consumer provenance manifest | Assembly -> Consumer | Yes | `tests/test_consumer_provenance.py` | None |

### Untested Gaps (Priority Order)

1. **Count conservation as a dedicated test** -- `assert_cm_conservation()` runs as a runtime assertion during compilation. No test exercises it with known-answer synthetic data.
2. **Lossless append verification** -- no test verifies that consolidation preserves every input row without modification.
3. **Assembly-level feature stacking order** -- no test pins the channel index against `feature_names.json` at the assembly boundary (only compilation is tested).

## Consequences

- New data sources must declare whether their features are extensive or intensive (ADR-040 section 3).
- Layer boundary tests in `test_cross_layer_contracts.py` are the enforcement mechanism for this ADR.
- The gap table is a living artifact: close gaps by adding characterization tests, then update this section.
