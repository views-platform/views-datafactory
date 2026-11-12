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
| **Viewpoint -> Compilation** | Column schema match (required fields not stripped); cell assignment from the field the compilation config declares, falling back to floor-based binning on the coordinates (**corrected 2026-11-12, previously "spatial binning via floor-based cell assignment"** — see the Amendment below and ADR-024's); temporal binning at month precision; dimension order [T, H, W, C] | ADR-024 |
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
| Month assignment from `date_end` | Consolidation -> Viewpoint | Partial | `tests/test_consumer_parity.py` | Parity test validates output, not the assignment rule directly |
| Count conservation | Viewpoint -> Compilation | Yes | `_conservation.py::assert_cm_conservation()` | Runtime assertion only; no dedicated test. **And it cannot see relocation** -- it counts rows and sums totals, both of which are preserved when a row is placed in the wrong cell. A passing conservation check is not evidence that placement is correct. |
| Column schema match | Viewpoint -> Compilation | Yes | `tests/test_cross_layer_contracts.py` | None |
| Dimension order [T,H,W,C] | Compilation -> Assembly | Yes | `tests/test_compiler.py` | None |
| Spatial binning (floor-based) | Viewpoint -> Compilation | Yes | `tests/test_compiler.py` | **Corrected 2026-11-12, was "None".** The binning rule itself is tested. What was not tested is whether a cell an upstream stage had already *decided* survives this boundary -- it did not, for four months. Now covered by `tests/test_falsification_spatial_allocation_delivery.py`. See the Amendment below. |
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

---

## Amendment 2026-11-12 — one narrow exception to boundary-only verification (#547, #556)

**The Decision above stands, and boundary verification remains the doctrine.** This amendment
adds a single, bounded exception and corrects two rows of the gap table. Dated amendment, not a
rewrite.

### 1. What this ADR got right, and the exact shape of what it missed

§Decision states: *"Soundness is verified at layer boundaries, not end-to-end. … An end-to-end
invariant would require coupling layers that the architecture deliberately separates."* That
reasoning is sound and this amendment does not overturn it.

The defect it could not see had an unusual shape: **it lived at a boundary but was only
observable as a cross-boundary property.** The viewpoint stage wrote a decision into a column;
the compilation stage never read that column and re-derived the same quantity from different
inputs. Every per-boundary contract passed. The schema matched, by name. Conservation held,
because relocation conserves. Floor-based binning was correct, because it was the wrong
function to be calling at all.

The property that would have caught it cannot be stated on either side alone. It is: *the
number of distinct cells the allocator chose equals the number the grid delivers.* One side
knows the first number, the other knows the second, and neither can check the equality.

### 2. The exception

> **Where one stage makes a decision that a later stage could re-derive from other inputs, that
> decision must be verified at the layer the consumer reads — not at the boundary where it was
> written.**
>
> This applies only to *decisions*: a value chosen by a stage among alternatives, where a
> plausible independent derivation of the same quantity exists downstream. It does not apply to
> data that merely passes through, and it does not license end-to-end testing of anything else.

Two tests satisfy it today, and both are deliberately cheap: they run on synthetic geography,
in CI, with no real data present, because a verification that can be skipped is the condition
that produced this defect rather than a remedy for it.

### 3. How to tell whether this exception applies to a new boundary

Ask: *could the downstream stage compute this value itself from something other than the field
the upstream stage wrote?* If yes, there are two sources of truth and the architecture has not
designated one. ADR-003 requires that designation. The practical test is whether removing the
upstream field entirely would change the output — if it would not, the decision is not reaching
the consumer.

### 4. Gap table corrections

Two rows were wrong in a way worth naming rather than silently editing:

- **Spatial binning, Viewpoint → Compilation** recorded gap *"None"*. It certified as sound the
  exact boundary at which 26.49% of UCDP fatality mass was being misplaced. The row was not
  careless: the binning rule *is* tested. It recorded the absence of a gap in the thing it
  measured and was read as recording the absence of a gap.
- **Count conservation, Viewpoint → Compilation** recorded *"Runtime assertion only; no
  dedicated test"*, which was true and insufficient. Conservation counts rows and sums totals;
  both survive a row being placed in the wrong cell. ADR-049 had already written the sentence
  that matters — *"a guard that cannot distinguish distribution from relocation is not a guard
  for this ADR"* — and applied it only inside the viewpoint.

Both rows now say what they do and do not cover.

### 5. A note on the gap table as an instrument

§Consequences calls the gap table *"a living artifact"*. The failure above suggests one rule for
keeping it honest: a `Gap` cell saying *"None"* is a claim that **no** property of that boundary
is unverified, which is almost never true. Prefer naming what the listed test covers. A table
that records *"None"* fifteen times reads as a certificate, and this one was cited as such.
