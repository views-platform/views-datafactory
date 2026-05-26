# Sprint Plan S2: V-Dem Documentation Gaps

**Date:** 2026-05-26
**Branch:** `development` (documentation-only changes, no code modifications)
**Goal:** Close the 5-entry V-Dem documentation cluster (C-217, C-218, C-219, C-220, C-221) identified by the falsification audit of V-Dem visual audit implementation decisions (2026-05-26). Prevent consumer misuse of V-Dem features before external users access the data.
**Estimated effort:** 2–3 hours.
**Source:** `/falsify` (V-Dem visual audit documentation, 2026-05-26), `/register-risk` (C-217–C-221, 2026-05-26), `/review-rr prioritize` (2026-05-26, Cluster D: highest score at 7.0).
**Prerequisite:** None. Sprint S1 (register curation) is recommended first but not blocking.
**Blocking:** This sprint should be completed before V-Dem data is used by external consumers. The consumer guide is the primary external interface — incorrect or missing scale/range information will cause silent model training errors.

---

## Context

The V-Dem integration (2026-05-26, PR #68 / v1.2.22) prioritized functional correctness: harvester, viewpoint builder, pregridded compilation, pipeline runner, assembly integration, and 15-plot visual audit. All code is tested and working. However, the falsification audit revealed that 5 implementation decisions made during the visual audit work are not documented in any governance artifact:

1. **Scale classification** (C-217): 17 features are bounded [0,1]; 5 use interval scale [-2.3, +2.3]. The only place this is recorded is the `INTERVAL_SCALE_FEATURES` constant in `scripts/verify_vdem_grid.py`. No consumer-facing document mentions it.

2. **Exclusion temporal cutoff** (C-218): 4 exclusion features (v2xpe_exlsocgr, exlgeo, exlpol, exlgender) have data only through 2023 in V-Dem v16. All governance docs state blanket "1789-2025" or "1980-2025" coverage without per-feature caveats.

3. **PrecomputedData CIC** (C-219): 21-field dataclass with non-obvious invariants (country_values uses per-feature last_valid_t). ADR-006 requires CICs for non-trivial classes in scripts/.

4. **Broadcast invariant** (C-220): V-Dem values are broadcast identically to all cells within a country. ADR-024 lists 5 compilation grid invariants; broadcast is not among them.

5. **Inverse pgid formula** (C-221): `row = (pgid - 1) // 720, col = (pgid - 1) % 720`. Used in verification scripts and viewpoint builders but not stated in any governance doc. The 1-indexed convention is the source of off-by-one bugs.

**Why this matters:** A consumer reading the consumer data guide to select V-Dem features for model training will:
- Not know that 5 features have a different scale than the other 17 → incorrect normalization
- Not know that 4 features end at 2023 → NaN in 2024-2025 with no explanation
- Not know the pgid indexing convention → off-by-one when implementing spatial lookups

---

## Task 1: Add Scale Classification to Consumer Guide and Data Card (C-217)

**Why:** This is the highest-impact documentation gap. A consumer normalizing all 22 V-Dem features to [0,1] range would clip 5 interval-scale features whose actual range is approximately [-2.3, +2.3]. The 5 interval-scale features are accountability indices (horizontal, vertical, diagonal accountability; division of party control; overall accountability) — these are core democracy measures, not peripheral indicators.

**Register ref:** C-217 (T3). Falsification audit probe P-3 (hard falsification) and P-7 (soft falsification).

### What to document

Two scale types exist in V-Dem's feature set:

| Scale | Range | Features | Count |
|-------|-------|----------|-------|
| Bounded index | [0, 1] | v2xcl_dmove, v2xeg_eqdr, v2x_clphy, v2xcl_prpty, v2x_ex_military, v2x_ex_party, v2xnp_client, v2xnp_regcorr, v2xeg_eqprotec, v2x_genpp, v2x_hosabort, v2x_libdem, v2xcl_rol, v2xpe_exlsocgr, v2xpe_exlgeo, v2xpe_exlpol, v2xpe_exlgender | 17 |
| Interval (additive polyarchy) | ≈[-2.3, +2.3] | v2x_horacc, v2x_veracc, v2x_diagacc, v2x_divparctrl, v2x_accountability | 5 |

The interval-scale features are centered near 0 and can take negative values. They use V-Dem's "additive polyarchy" measurement model, which produces unbounded continuous scores. The bounded features are constructed as 0-to-1 indices.

### Steps

1. **Consumer data guide** (`docs/guides/consumer_data_guide.md`): In the V-Dem feature table (lines 380-407), add a "Scale" column to each feature row. Add a note above the table:
   ```markdown
   **Scale types:** V-Dem features use two distinct scales. 17 features are bounded
   indices in [0, 1] (higher = more democratic). 5 accountability features use an
   interval scale centered near 0 with approximate range [-2.3, +2.3] (V-Dem's
   additive polyarchy measurement model). Do not normalize interval-scale features
   to [0, 1] — this clips meaningful variation.
   ```

2. **Data card** (`docs/sources/vdem.md`): Add a "Scale Classification" section after the feature list (line 20). Include the same scale table and the `INTERVAL_SCALE_FEATURES` constant reference:
   ```markdown
   ## Scale Classification

   | Scale | Range | Features |
   |-------|-------|----------|
   | Bounded index | [0, 1] | 17 features (see list above) |
   | Interval (additive polyarchy) | ≈[-2.3, +2.3] | v2x_horacc, v2x_veracc, v2x_diagacc, v2x_divparctrl, v2x_accountability |

   The interval-scale features use V-Dem's additive polyarchy measurement model.
   They are centered near 0 and can take negative values. The authoritative code
   constant is `INTERVAL_SCALE_FEATURES` in `scripts/verify_vdem_grid.py`.
   ```

3. **ADR-035** (`docs/ADRs/035_vdem_as_democracy_source.md`): In the feature selection rationale section (around line 119), add a note about scale heterogeneity:
   ```markdown
   **Scale note:** The 22 selected features span two V-Dem scale types: 17 bounded
   [0, 1] indices and 5 interval-scale accountability measures (≈[-2.3, +2.3]).
   Consumer documentation must distinguish these scales to prevent incorrect
   normalization. See `docs/sources/vdem.md` (Scale Classification).
   ```

### Acceptance criteria

- Consumer guide V-Dem feature table has a "Scale" column or equivalent scale annotation for each feature.
- Consumer guide has a note explaining the two scale types and warning against normalizing interval features to [0, 1].
- Data card has a "Scale Classification" section with the 5 interval-scale features listed.
- ADR-035 mentions scale heterogeneity.
- `grep -c "interval" docs/guides/consumer_data_guide.md` returns >= 2.
- `grep -c "interval" docs/sources/vdem.md` returns >= 2.
- Falsification test stub `tests/test_falsification_vdem_audit_docs.py::TestP3P7ConsumerGuideScaleClassification::test_consumer_guide_has_scale_info` passes (remove `xfail`).
- Falsification test stub `tests/test_falsification_vdem_audit_docs.py::TestP3P7ConsumerGuideScaleClassification::test_data_card_has_scale_info` passes (remove `xfail`).

---

## Task 2: Document Exclusion Features' 2023 Temporal Cutoff (C-218)

**Why:** Four exclusion features have data only through 2023 in V-Dem v16. All governance docs state blanket temporal coverage without per-feature caveats. A developer or consumer querying these features at 2024-2025 receives NaN with no documentation explaining why. This is an upstream data property of V-Dem v16 — not a pipeline bug — but consumers must be informed.

**Register ref:** C-218 (T3). Falsification audit probe P-4 (soft falsification).

### The 4 exclusion features

| Feature | Description | Last valid year |
|---------|-------------|----------------|
| v2xpe_exlsocgr | Exclusion by socioeconomic group | 2023 |
| v2xpe_exlgeo | Exclusion by urban-rural location | 2023 |
| v2xpe_exlpol | Exclusion by political group | 2023 |
| v2xpe_exlgender | Exclusion by gender | 2023 |

All other 18 features extend to 2024 (the latest year in V-Dem v16). In the compiled grid, these 4 features have NaN values for months after December 2023 (time steps 420–443 for 2024-01 through 2025-12).

### Steps

1. **ADR-035** (`docs/ADRs/035_vdem_as_democracy_source.md`): In the temporal coverage section (around line 119), add:
   ```markdown
   **Per-feature temporal caveat:** Four exclusion features (v2xpe_exlsocgr,
   v2xpe_exlgeo, v2xpe_exlpol, v2xpe_exlgender) have data only through 2023
   in V-Dem v16, while all other features extend to 2024. The compiled grid
   contains NaN for these features at months after December 2023. This is an
   upstream V-Dem data property — these indices are published with a 1-year
   lag relative to the main release. Future V-Dem versions may close the gap.
   ```

2. **Data card** (`docs/sources/vdem.md`): In the temporal coverage line (line 15), change "1789–2024" to "1789–2024 (4 exclusion features end at 2023)". Add a "Temporal Caveats" section:
   ```markdown
   ## Temporal Caveats

   | Features | Coverage | Grid behavior after cutoff |
   |----------|----------|---------------------------|
   | 18 main features | 1789–2024 | NaN after 2024 |
   | 4 exclusion features (v2xpe_exl*) | 1789–2023 | NaN after 2023 |

   The exclusion indices are published with a ~1 year lag in V-Dem's release
   cycle. Consumers using these features for 2024 predictions should be aware
   that values will be NaN. The verification script (`scripts/verify_vdem_grid.py`,
   Plot 13) visualizes this cutoff as a vertical dashed line.
   ```

3. **Consumer guide** (`docs/guides/consumer_data_guide.md`): In the V-Dem feature table, annotate the 4 exclusion features with a footnote marker (e.g., `†`). Add footnote:
   ```markdown
   † Exclusion features have data through 2023 only (V-Dem v16). Values are NaN
   for 2024 onward. See `docs/sources/vdem.md` (Temporal Caveats).
   ```

### Acceptance criteria

- ADR-035 mentions "2023" and at least one exclusion feature name in the temporal section.
- Data card has a "Temporal Caveats" section listing the 4 features.
- Consumer guide has a footnote or annotation on the 4 exclusion features.
- Falsification test stub `tests/test_falsification_vdem_audit_docs.py::TestP4ExclusionTemporalLag::test_exclusion_lag_documented` passes (remove `xfail`).

---

## Task 3: Write PrecomputedData CIC (C-219)

**Why:** `PrecomputedData` is a 21-field dataclass in `scripts/verify_vdem_grid.py` that maintains precomputed state for 15 verification plots. ADR-006 requires CICs for non-trivial classes that "maintain internal state across operations" and explicitly scopes `scripts/` (lists `AssemblyConfig` from `scripts/assemble_grid.py` as a precedent). The `country_values` field has a non-obvious invariant: values are extracted at each feature's own last valid time step, not a single shared t. Without a CIC, this invariant is undiscoverable.

**Register ref:** C-219 (T4). Falsification audit probe P-1 (soft falsification).

### Key invariants to document

1. **Per-feature last_valid_t:** The `country_values` array is NOT extracted at a single time step. Each feature uses its own last valid time step. For 18 main features, this is t=443 (Dec 2025). For 4 exclusion features, this is t=419 (Dec 2023). The `feat_last_t` array records each feature's last_valid_t.

2. **Country deduplication:** `country_values` and `country_values_t0` contain one representative cell per country (the first cell in the GAUL crosswalk for that ISO3 code). All cells within a country have identical values (broadcast invariant), so any cell is representative.

3. **Grid dependency:** All fields are derived from `grid` (the mmap'd npy file). The `precompute()` function performs a single pass to populate all fields, minimizing mmap reads.

4. **GAUL crosswalk dependency:** Country-level fields depend on `data/raw/gaul_admin/iso3_code.parquet`. If this file is missing, country-level plots are skipped (not crashed).

### Steps

1. Create `docs/CICs/PrecomputedData.md` following the CIC template established by `docs/CICs/AssemblyConfig.md` (the other scripts/ class with a CIC). Include:
   - Section 1: Identity (class name, location, purpose)
   - Section 2: Constructor (21 fields with types and descriptions)
   - Section 3: Responsibilities and Guarantees (the 4 invariants above)
   - Section 4: Dependencies (grid npy, GAUL crosswalk, feature_names.json)
   - Section 5: Failure Modes (missing GAUL crosswalk, all-NaN feature, empty grid)
   - Section 6: Usage Context (called by `precompute()`, consumed by 15 plot functions)
   - Section 10: Test Alignment (reference to `tests/test_falsification_vdem_audit_docs.py::TestP1PrecomputedDataCIC`)

2. Update `docs/CICs/README.md`: Add `PrecomputedData` to the active contracts list.

3. Update falsification test: Remove `xfail` from `tests/test_falsification_vdem_audit_docs.py::TestP1PrecomputedDataCIC::test_precomputed_data_cic_exists`.

### Acceptance criteria

- `docs/CICs/PrecomputedData.md` exists and follows the CIC template.
- Per-feature last_valid_t invariant is documented in section 3.
- Country deduplication method is documented.
- `docs/CICs/README.md` lists PrecomputedData.
- Falsification test `test_precomputed_data_cic_exists` passes without xfail.

---

## Task 4: Add Broadcast Invariant to ADR-024 (C-220)

**Why:** ADR-024 (Compilation Grid Invariants) lists 5 invariants that all compiled grids must satisfy. The broadcast property — that all cells within a country have identical values for country-level sources — is not among them. This invariant is specific to V-Dem (and will apply to WDI when added), where country-year data is broadcast to all PRIO-GRID cells within that country. Without formalizing it, a new compilation path for a country-level source could omit the broadcast check, causing within-country values to silently diverge.

**Register ref:** C-220 (T4). Falsification audit probe P-5 (soft falsification).

### Steps

1. Read `docs/ADRs/024_compilation_grid_invariants.md` to identify the current 5 invariants and their numbering.

2. Add invariant 6 (broadcast) after the existing 5:
   ```markdown
   ### Invariant 6: Country-Level Broadcast

   **Applies to:** Pregridded (country-level) sources only (V-Dem, future WDI).

   For sources that provide country-level data (not cell-level), all PRIO-GRID
   cells within the same country must have identical values at every time step
   for every feature. Within-country standard deviation must be exactly zero.

   **Rationale:** Country-level sources like V-Dem provide one value per
   country-year. The viewpoint builder broadcasts this value to all cells in
   the country via the GAUL ISO3→pgid crosswalk. If the broadcast is incorrect
   (e.g., off-by-one in pgid mapping, partial crosswalk update), neighboring
   country values would bleed into each other — a spatial data corruption that
   would be invisible in country-level analysis but produce wrong cell-level
   model inputs.

   **Verification:** `scripts/verify_vdem_grid.py`, Plot 14 (Broadcast
   Integrity). Computes within-country standard deviation for all features
   at the latest valid time step. PASS if all values are exactly 0.0.

   **Not applicable to:** Event-based sources (UCDP, ACLED) where cell values
   differ by construction. Raster sources (GHS-POP, GHS-BUILT-S) where cell
   values vary spatially within countries.
   ```

3. Update the invariant count in ADR-024's introduction (e.g., "5 invariants" → "6 invariants").

4. In ADR-035 (`docs/ADRs/035_vdem_as_democracy_source.md`), add a cross-reference to ADR-024 Invariant 6 where the broadcast property is described informally (around lines 64-72).

### Acceptance criteria

- ADR-024 lists 6 invariants (previously 5).
- Invariant 6 is clearly scoped to country-level sources.
- ADR-035 cross-references ADR-024 Invariant 6.
- Falsification test `tests/test_falsification_vdem_audit_docs.py::TestP5BroadcastInvariantFormalized::test_broadcast_in_compilation_invariants` passes (remove `xfail`).

---

## Task 5: Document Inverse PGID Formula (C-221)

**Why:** The forward pgid formula (`pgid = row * ncol + col + 1`, 1-indexed) is documented in a code comment in `cell_generator.py:30`. The inverse formula (`row = (pgid - 1) // 720, col = (pgid - 1) % 720`) is used in at least 3 locations — `verify_vdem_grid.py`, `vdem_v1.py` viewpoint builder, and GAUL crosswalk processing — but is not stated in any governance artifact. The 1-indexed convention (pgid starts at 1, not 0) is the specific source of off-by-one bugs. It is trivially derivable but non-obvious to someone unfamiliar with PRIO-GRID's convention.

**Register ref:** C-221 (T4). Falsification audit probe P-2 (observation).

### Steps

1. **ADR-024** (already being edited in Task 4): Add the pgid formula to the spatial binning invariant section, or add a new "PGID Convention" subsection:
   ```markdown
   #### PGID Convention

   PRIO-GRID cell IDs (`pgid`) are 1-indexed:

   - **Forward (coordinates → pgid):** `pgid = row * 720 + col + 1`
     where `row = 0..359` (north to south), `col = 0..719` (west to east).
   - **Inverse (pgid → grid indices):** `row = (pgid - 1) // 720`,
     `col = (pgid - 1) % 720`.

   The 1-indexed convention means `pgid` ranges from 1 to 259,200.
   Grid arrays use 0-indexed `[row, col]`. The `- 1` in the inverse
   formula accounts for this offset. Omitting it shifts all spatial
   data one cell east and wraps the last column.

   **Authoritative source:** `src/datafactory_priogrid/cell_generator.py:30`.
   ```

2. **Data card or PRIO-GRID documentation:** If `docs/sources/priogrid_static.md` exists, add the pgid formula there as well. If it doesn't exist, the ADR-024 addition is sufficient.

### Acceptance criteria

- ADR-024 contains both the forward and inverse pgid formulas.
- The 1-indexed convention is explicitly stated.
- The `- 1` offset is explained (prevents off-by-one).

---

## Task 6: Update Risk Register

**Why:** After completing Tasks 1-5, all 5 entries in the V-Dem documentation cluster should be resolved.

### Steps

1. Strike through C-217, C-218, C-219, C-220, C-221 in the summary table.
2. Add resolution notes to each full entry.
3. Move full entries to resolved archive.
4. Update V-Dem documentation work package to resolved: `~~**V-Dem documentation**~~ | ~~C-217, C-218, C-219, C-220, C-221~~ | Resolved 2026-05-2x`
5. Update header counts: open 60 → 55 (assuming S1 was done first), Tier 3 15 → 13, Tier 4 33 → 30.
6. Remove all `xfail` markers from the 5 falsification test stubs in `tests/test_falsification_vdem_audit_docs.py`.

### Acceptance criteria

- All 5 entries resolved in register.
- All 5 falsification test stubs pass without xfail.
- V-Dem documentation work package is resolved.
- `uv run pytest tests/test_falsification_vdem_audit_docs.py -v` — all 5 tests PASS.

---

## Commit Strategy

Two commits:

1. **Documentation commit:**
   ```
   docs: V-Dem scale classification, temporal caveats, broadcast invariant, pgid formula, PrecomputedData CIC
   ```
   Files: `docs/guides/consumer_data_guide.md`, `docs/sources/vdem.md`, `docs/ADRs/035_vdem_as_democracy_source.md`, `docs/ADRs/024_compilation_grid_invariants.md`, `docs/CICs/PrecomputedData.md`, `docs/CICs/README.md`

2. **Register + test commit:**
   ```
   docs: resolve V-Dem documentation cluster (C-217, C-218, C-219, C-220, C-221)
   ```
   Files: `reports/technical_risk_register.md`, `reports/archive/technical_risk_register_resolved.md`, `tests/test_falsification_vdem_audit_docs.py`

---

## Final Verification

```bash
# All falsification stubs pass
uv run pytest tests/test_falsification_vdem_audit_docs.py -v

# Consumer guide mentions interval scale
grep -c "interval" docs/guides/consumer_data_guide.md  # >= 2

# Data card has temporal caveats
grep -c "2023" docs/sources/vdem.md  # >= 2

# ADR-024 has 6 invariants
grep -c "### Invariant" docs/ADRs/024_compilation_grid_invariants.md  # 6

# CIC exists
test -f docs/CICs/PrecomputedData.md && echo "CIC exists"

# Register cluster resolved
grep "V-Dem documentation" reports/technical_risk_register.md | grep -c "Resolved"  # 1
```
