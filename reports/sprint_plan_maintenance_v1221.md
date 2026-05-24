# Sprint Plan: Maintenance Branch v1.2.21

**Date:** 2026-05-24
**Branch:** `chore/maintenance-v1221` (from `development`)
**Goal:** Pay WET-before-DRY debt, restore CI signal, curate risk register, clean dead code — before adding the 5th data source.
**Estimated effort:** 4–5 hours of focused work.
**Source:** repo-assimilation (2026-05-24), tech-debt-cleanup investigation (2026-05-24), strategic review-rr + prioritize (2026-05-24).
**QA review:** 8-expert code review (2026-05-24). Corrections applied: import DAG blocker (Task 3), module naming (Tasks 4-5), test file reference (Task 7), error handling (Task 8), register count verification (Task 1), package refresh (Task 9), smoke tests (Final Verification).
**Falsification audit 1:** ADR alignment (2026-05-24), 8 probes, verdict CONTESTED → 4 soft falsifications addressed: F-1 (ADR-012 provenance scope → Task 3 step 6), F-2 (ADR-005 test coverage → Task 10), F-5 (ADR-008 print-vs-logger → Task 8 note, deferred), F-7 (ADR-012 synthetic references → Task 9 step 4).
**Falsification audit 2:** SOLID alignment (2026-05-24), 8 probes, verdict CONTESTED → 1 hard falsification addressed: S-4 (NameError — `_load_source_grid` references `np` and `DEFAULT_GRID_CONFIG` imported inside `main()` → Task 8 step 1, move imports to module level).
**Falsification audit 3:** Package principles alignment (2026-05-24), 8 probes, verdict CONTESTED → 1 soft falsification noted: P-6 (SAP Zone of Pain — provenance has I=0.00, A=0.00, D=1.00; Task 3 adds concrete constant without abstraction → acknowledged in Task 3, deferred to architecture sprint).
**Falsification audit 4:** Screaming architecture (2026-05-24), 8 probes, verdict CONTESTED → 1 soft falsification addressed: R-1 (VIEWS_EPOCH_YEAR placement — Task 3 step 1 changed from `digests_and_ledgers.py` to dedicated `constants.py`).
**Falsification audit 5:** Definition of Done (2026-05-24), 5 probes, verdict CONTESTED → 3 soft falsifications addressed: D-1 (Task 1 missing acceptance criteria section + contradictory header blocks → formal section added, wrong block removed), D-2 (subjective criteria in Tasks 3, 8, 10 → rewritten as binary checks), D-5 (no terminal action → ship gate added to Final Verification).

---

## Prerequisites

Before any task in this plan can begin:

1. **Create maintenance branch** from `development`:
   ```
   git checkout development
   git checkout -b chore/maintenance-v1221
   ```

2. **Commit the untracked deployment postmortem** that is currently sitting in the working tree:
   - File: `reports/post_mortems/2026-05-24_deployment_v1220.md`
   - Stage and commit before starting maintenance work so it doesn't get mixed in.

---

## Task 0: Version Bump to 1.2.21

**Why:** The test `test_version_not_already_tagged` fails because git tag `v1.2.20` already exists. Every subsequent commit will fail the test gate until the version is bumped.

**Register refs:** Prerequisite for all subsequent tasks.

### Steps

1. Open `pyproject.toml` and change `version = "1.2.20"` to `version = "1.2.21"`.
2. Verify: `uv run pytest tests/test_falsification_ghspop_deploy_v2.py::TestGhsPopDeployReadiness::test_version_not_already_tagged tests/test_falsification_ghsbuilts_deploy_v2.py::TestGhsBuiltSDeployReadiness::test_version_not_already_tagged -v` — both must pass.
3. Commit: `chore: bump version to 1.2.21 for maintenance branch`.

### Acceptance criteria

- `pyproject.toml` version is `1.2.21`.
- Both `test_version_not_already_tagged` tests pass.

---

## Task 1: Register Curation (14 Strategic Fixes)

**Why:** The strategic review found C-178 still listed as open despite being fixed, C-03 describing a concern in a dead module, stale triggers, and two marginal disagreements. Accurate register state is a prerequisite for register-driven planning.

**Register refs:** Strategic review-rr findings (2026-05-24).

### Steps

#### 1a. Resolve C-178

C-178 (`compute_content_digest(path.read_bytes())`) was fixed on 2026-05-21 — all three call sites updated. The entry says "FIX APPLIED" but is still in the open Tier 3 section.

- In `reports/technical_risk_register.md`:
  - Cross out the C-178 heading: `### ~~C-178~~: ...`
  - Add `| Trigger | Resolved 2026-05-21 |` to the field table.
  - Move the full entry text to `reports/archive/technical_risk_register_resolved.md`.
- Update header counts: resolved 103 → 104, open 67 → 66, Tier 3 17 → 16.

#### 1b. Merge C-03 into C-176

C-03 warns about protocol proliferation in `datafactory_synthetic`. C-176 says the module is dead with zero exports. C-03 is moot.

- Cross out C-03 in the register. Add note: "Subsumed into C-176 — module is dead (zero exports)."
- Update C-176 narrative to mention C-03: "See also C-03 (protocol proliferation — moot since module has no implementation)."
- Update header: add C-03 to the merged-entry parenthetical. Open count 66 → 65. Tier 4 36 → 35.

#### 1c. Tier recalibrations

- **C-177: Tier 3 → 4.** The function `_aggregate_to_prio_grid` is dead code (not called since v1.2.18), documented with warning, 7 tests exercise it, single developer. Add note: "Tier recalibrated from 3 to 4 during review-rr (2026-05-24). Dead function, single developer, docstring warning. D-25 tracks the design question."
  - Move entry from Tier 3 section to Tier 4 section.
  - Update header: Tier 3 16 → 15, Tier 4 35 → 36.

- **C-21: Tier 3 → 4.** No migration is planned. Partially addressed by `ex_*.py` verification scripts. Single-developer scope. Add note: "Tier recalibrated from 3 to 4 during review-rr (2026-05-24). No migration imminent. Partially addressed by verification examples."
  - Move entry from Tier 3 section to Tier 4 section.
  - Update header: Tier 3 15 → 14, Tier 4 36 → 37.

#### 1d. Trigger rewrites (7 entries)

Replace stale/vague triggers with actionable versions:

| ID | Old Trigger | New Trigger |
|----|------------|-------------|
| C-88 | "Before production deployment" | "Before granting additional SSH users, or when PRIO IT provides VPN CIDR ranges for firewall rules" |
| C-29 | "Server in production" | "When pipeline validation needs independent orchestration, or 2nd deployment target is set up" |
| C-44 | "5 sources exist" | "Before V-Dem (9th source) — extract shared harvest template to reduce copy-paste per source" |
| C-74 | "User confusion observed" | "When a new developer writes a CompilationConfig and the strategy string enum is needed for IDE discoverability" |
| C-75 | "Recurring misuse patterns" | "When a consumer constructs FeatureFrame with wrong shape and the error message is insufficient to diagnose" |
| C-21 | "Next migration batch planned" | "When views-metric-lab plans to migrate a model that depends on viewser-transformed features (currently no migration planned)" |
| D-29 | (no trigger) | "When shapefile harvester is next touched for a bug fix, or when V-Dem requires shapefile-like ingestion" |

For each: edit the trigger field in the register entry. Append "(trigger rewritten during review-rr 2026-05-24)" to the end of the trigger text.

#### 1e. Resolve D-25 and D-28

Both are marginal disagreements where the current state IS the resolution:

- **D-25** (dead function retention): The decision is made — retain `_aggregate_to_prio_grid` with docstring warning, delete when tests are restructured. Add resolution: "Resolved 2026-05-24: retain with docstring warning (current state). Re-evaluate at next refactor cycle when `_aggregate_with_alignment` tests fully replace the old function's test coverage. Tier recalibrated to 4 (C-177)."
- **D-28** (one function vs two for digest lookup): The bug (C-182) was fixed. The two-function API works. Add resolution: "Resolved 2026-05-24: keep two functions (current state). C-182 bug fixed in both. The shared `_find_latest_valid_entry` helper (GoF recommendation) is a nice-to-have for the next provenance refactor, not a risk."

Move both to the resolved disagreements archive. Update header: open disagreements 7 → 5.

#### 1f. Update register date and source line

- Update `**Date:**` to `(updated 2026-05-24)`.
- Add `review-rr strategic + prioritize 2026-05-24` to the source line.

### Expected final header after all 1a–1f changes

Arithmetic (verify against actuals before writing):

- Start: 67 open (8 T2, 17 T3, 36 T4, 6 deferred)
- Resolve C-178 (T3): 66 open (8 T2, 16 T3, 36 T4, 6 deferred)
- Merge C-03 into C-176 (C-03 was T4): 65 open (8 T2, 16 T3, 35 T4, 6 deferred)
- C-177 T3→T4: 65 open (8 T2, 15 T3, 36 T4, 6 deferred)
- C-21 T3→T4: 65 open (8 T2, 14 T3, 37 T4, 6 deferred)
- D-25, D-28 resolved: 5 open disagreements

```
195 concern IDs assigned (..., C-03 merged into C-176):
105 resolved, 65 open concerns (8 Tier 2, 14 Tier 3, 37 Tier 4, 6 deferred by design;
4 with fired triggers), 5 open disagreements.
```

### Acceptance criteria

- C-178 is struck through in the register and moved to the resolved archive.
- C-03 is struck through with "Subsumed into C-176" note. C-176 narrative references C-03.
- C-177 and C-21 appear in the Tier 4 section, not Tier 3.
- All 7 trigger rewrites are present (verify: `grep -c "trigger rewritten during review-rr 2026-05-24" reports/technical_risk_register.md` returns 7).
- D-25 and D-28 are in the resolved disagreements archive.
- Register header counts match a mechanical grep: `grep -c "^### C-" reports/technical_risk_register.md` per tier section matches the header.
- No ID appears in both open sections and the resolved archive.
- **Mechanical count before starting:** Run `grep -c "^### C-" reports/technical_risk_register.md` per tier section to confirm starting counts match (67 open, 17 T3, 36 T4). If they differ, re-derive the arithmetic from actuals.

### Commit

`docs: risk register curation — resolve C-178, merge C-03→C-176, recalibrate C-177/C-21, rewrite 7 triggers, resolve D-25/D-28`

---

## Task 2: Restore CI Signal (C-169)

**Why:** Two tests consistently fail in CI due to missing infrastructure (server credentials, sibling repo), making CI permanently UNSTABLE. Real regressions are invisible. This must be fixed before the WET extraction work so that CI validates those changes.

**Register refs:** C-169 (Tier 4, but prerequisite for all CI-gated work).

### Steps

1. **Identify the failing tests.** The register names:
   - `tests/test_falsification_staleness.py:57` — `test_remote_zarr_has_last_valid_month_id`
   - `tests/test_structural_invariants.py:145` — `test_at_least_one_model_found`

2. **Check existing skip guards.** Both tests already have conditional skips:
   - `test_remote_zarr_has_last_valid_month_id` (line 57): catches `URLError, HTTPError, TimeoutError, OSError` → `pytest.skip()`. HTTP 401 should be caught as `HTTPError`. If it still fails in CI, the 401 may be raising a different exception type — investigate by checking the actual CI error output.
   - `test_at_least_one_model_found` (line 145): `if not MODELS_ROOT.exists(): pytest.skip(...)`. Should already skip when `../views-models/` is missing.

3. **If skip guards are already working** (tests skip, not fail), the CI UNSTABLE status comes from somewhere else. Run `uv run pytest --tb=short 2>&1 | grep -E "FAILED|ERROR"` to identify actual failures.

4. **If skip guards are not sufficient**, add explicit `@pytest.mark.skipif` decorators at the class level:
   ```python
   # test_falsification_staleness.py
   @pytest.mark.skipif(
       not Path("~/.netrc").expanduser().exists(),
       reason="No .netrc — server auth unavailable"
   )
   class TestP5RemoteZarrAttr:
       ...
   ```
   ```python
   # test_structural_invariants.py
   MODELS_ROOT = Path(__file__).resolve().parent.parent.parent / "views-models"

   @pytest.mark.skipif(
       not MODELS_ROOT.exists(),
       reason="views-models sibling repo not available"
   )
   class TestModelPartitionParity:
       ...
   ```

5. **Verify:** `uv run pytest` — full suite must pass (0 FAILED, 0 ERROR). Skipped tests are acceptable.

### Acceptance criteria

- `uv run pytest` exits with code 0.
- No FAILED or ERROR results.
- The two infrastructure-dependent tests show as SKIPPED when infrastructure is absent.

### Commit

`fix: add skipif guards for infra-dependent tests (C-169)`

---

## Task 3: WET Extraction — `_VIEWS_EPOCH_YEAR` Constant Dedup

**Why:** `_VIEWS_EPOCH_YEAR = 1980` is defined as a private constant in two viewpoint builders (`ghspop_v1.py:49`, `ghsbuilts_v1.py:47`) when the authoritative public constant `VIEWS_EPOCH_YEAR` already exists in `datafactory_priogrid.temporal_generator:17`. The viewpoint layer (Layer 3) cannot import from priogrid (Layer 1) per ADR-012, so the constant must be relocated to provenance (Layer 0), which all layers may import.

**Register refs:** C-164 pattern #5.

### Steps

1. **Move the constant to provenance (Layer 0):**
   - Create `src/datafactory_provenance/constants.py` with a single domain constant:
     ```python
     """Cross-cutting platform constants shared by all layers."""
     VIEWS_EPOCH_YEAR = 1980
     ```
     Do NOT add this to `digests_and_ledgers.py` — that file's responsibility is content digests and JSONL ledger operations. A calendar epoch constant is unrelated to either (R-1 falsification fix).
   - Export it from `src/datafactory_provenance/__init__.py`: add `"VIEWS_EPOCH_YEAR"` to `__all__` and add `from datafactory_provenance.constants import VIEWS_EPOCH_YEAR`.

2. **Update `datafactory_priogrid.temporal_generator`:**
   - Change line 17 from `VIEWS_EPOCH_YEAR = 1980` to `from datafactory_provenance import VIEWS_EPOCH_YEAR`.
   - `_VIEWS_EPOCH` (line 18) stays — it depends on numpy and is priogrid-specific.
   - Verify `src/datafactory_priogrid/__init__.py` re-exports `VIEWS_EPOCH_YEAR` — it currently does (line 24). It will now re-export the provenance-sourced value. No change needed there.

3. **Update `datafactory_compilation.pregridded_compilation`:**
   - Line 31 imports `VIEWS_EPOCH_YEAR` from `datafactory_priogrid.temporal_generator`. This still works (priogrid re-exports it). No change strictly needed, but optionally switch to `from datafactory_provenance import VIEWS_EPOCH_YEAR` for directness.

4. **Update both viewpoint builders:**
   - In `src/datafactory_viewpoint/builders/ghspop_v1.py`:
     - Add to imports: `from datafactory_provenance import VIEWS_EPOCH_YEAR`
     - Delete line 49: `_VIEWS_EPOCH_YEAR = 1980`
     - Replace all `_VIEWS_EPOCH_YEAR` usages with `VIEWS_EPOCH_YEAR` (line 567: `mid = (year - _VIEWS_EPOCH_YEAR) * 12 + month`).
   - In `src/datafactory_viewpoint/builders/ghsbuilts_v1.py`:
     - Add to imports: `from datafactory_provenance import VIEWS_EPOCH_YEAR`
     - Delete line 47: `_VIEWS_EPOCH_YEAR = 1980`
     - Replace all `_VIEWS_EPOCH_YEAR` usages with `VIEWS_EPOCH_YEAR` (line 448).

5. **Verify import enforcement:** Viewpoint already imports from provenance (allowed). Priogrid already imports from provenance (allowed). No DAG change. Run: `uv run pytest tests/test_import_enforcement.py -v`

6. **Update ADR-012 (F-1 falsification fix):** Provenance already contains `PIPELINE_SOURCES`, `SourceEntry`, `FRESHNESS_SLO_HOURS`, `validate_preflight()` — domain concepts beyond "digests and ledger operations." Adding `VIEWS_EPOCH_YEAR` extends this. Update the Layer 0 description in `docs/ADRs/012_four_layer_data_architecture.md` to acknowledge provenance's actual role:
   - Find the Layer 0 / Foundation description and change "content digests and JSONL ledger operations" to "content digests, JSONL ledger operations, source registry, and cross-cutting platform constants."
   - This is a documentation-honesty fix, not a scope expansion — the scope already expanded when `source_registry.py` and `health.py` were added.

7. **Run tests:**
   ```
   uv run pytest tests/test_ghspop_viewpoint.py tests/test_ghsbuilts_viewpoint.py tests/test_ghspop_compilation.py tests/test_ghsbuilts_compilation.py -v
   ```

**SAP Zone of Pain note (P-6 falsification finding):** This task adds a concrete constant to `datafactory_provenance`, which already has Instability I=0.00 (no outbound imports), Abstractness A=0.00 (zero Protocols or ABCs across 5 modules), and Distance from Main Sequence D=1.00 — maximally in Martin's Zone of Pain. Adding `VIEWS_EPOCH_YEAR` is directionally correct (constants belong in the most-stable layer) but incrementally worsens the abstractness deficit. This is acceptable for a maintenance sprint. A future architecture sprint should consider introducing a `LedgerWriter` Protocol or similar to move A>0 and reduce D. Tracked as a deferred item below.

### Acceptance criteria

- `VIEWS_EPOCH_YEAR` defined once, in `datafactory_provenance`.
- No private `_VIEWS_EPOCH_YEAR` constant in either builder.
- `temporal_generator.py` imports from provenance instead of defining the constant.
- Import enforcement test passes (no DAG violation).
- ADR-012 Layer 0 description contains the phrase "source registry" or "platform constants" (verify: `grep -iE "source.registry|platform.constants" docs/ADRs/012_four_layer_data_architecture.md`).
- All viewpoint and compilation tests pass.
- `uv run ruff check src/datafactory_provenance/ src/datafactory_priogrid/ src/datafactory_viewpoint/builders/ src/datafactory_compilation/` — clean.

### Commit

`refactor: move VIEWS_EPOCH_YEAR to provenance (Layer 0), update ADR-012 scope description (C-164 #5)`

---

## Task 4: WET Extraction — Raster GeoTIFF Reader

**Why:** `_read_geotiff()` is identical in `ghspop_v1.py:129-167` and `ghsbuilts_v1.py:125-161` — 39 lines of copy-paste. It is a pure I/O function with no domain coupling (reads TIFF tags, returns array + geotransform). Safe to extract.

**Register refs:** C-164 (2026-05-22 note, 2026-05-24 quantification).

### Steps

1. **Create shared module:** `src/datafactory_viewpoint/raster_io.py`

2. **Move the function** from `ghspop_v1.py:129-167` into `raster_io.py`:
   ```python
   """GeoTIFF I/O for raster-based viewpoint builders (GHS-POP, GHS-BUILT-S)."""

   from __future__ import annotations

   import logging
   from pathlib import Path

   import numpy as np
   import tifffile

   logger = logging.getLogger(__name__)


   def read_geotiff(
       path: Path,
   ) -> tuple[np.ndarray, float, float, float, float]:
       """Read GeoTIFF and extract geotransform from TIFF tags.

       Returns native dtype — no in-memory dtype conversion.
       Strip-based aggregation handles any input dtype.

       Returns:
           (data, tiepoint_x, tiepoint_y, pixel_scale_x, pixel_scale_y)
           where tiepoint is the top-left geographic coordinate.
       """
       ...  # (same body as current _read_geotiff)
   ```
   Note: the function is now public (no underscore prefix) since it's in a shared module.

3. **Update both builders** to import from the shared module:
   - `ghspop_v1.py`: Replace `_read_geotiff` definition with `from datafactory_viewpoint.raster_io import read_geotiff`. Update all call sites from `_read_geotiff(...)` to `read_geotiff(...)`.
   - `ghsbuilts_v1.py`: Same change.

4. **Update `__init__.py`:** No change needed — `raster_io` is an internal module, not part of the public API.

5. **Run tests:**
   ```
   uv run pytest tests/test_ghspop_viewpoint.py tests/test_ghsbuilts_viewpoint.py -v
   uv run ruff check src/datafactory_viewpoint/
   uv run mypy src/datafactory_viewpoint/raster_io.py
   ```

### Acceptance criteria

- `_read_geotiff` does not exist in either builder.
- `raster_io.py` contains the single definition.
- Both builders import `read_geotiff` from `raster_io`.
- All viewpoint tests pass. Lint and mypy clean.

### Commit

`refactor: extract read_geotiff into shared raster_io module (C-164)`

---

## Task 5: WET Extraction — Temporal Interpolation Suite

**Why:** Three functions are identical copy-paste between `ghspop_v1.py:361-465` and `ghsbuilts_v1.py:244-348` — 103 lines total. These are pure data transformation functions (epoch values → monthly time series) with zero domain coupling.

**Register refs:** C-164 (2026-05-22 note, 2026-05-24 quantification).

### Steps

1. **Create a separate shared module:** `src/datafactory_viewpoint/temporal.py`
   - Move `_interpolate_temporal()` (lines 361-408 in ghspop_v1.py)
   - Move `_interp_step()` (lines 411-428)
   - Move `_interp_linear()` (lines 431-464)
   - Also move the constant `VALID_TEMPORAL_INTERPOLATIONS = ("step", "linear")` — it's used by both builders and currently duplicated.
   - Make all four names public (drop underscore prefix): `interpolate_temporal`, `interp_step`, `interp_linear`, `VALID_TEMPORAL_INTERPOLATIONS`.
   ```python
   """Temporal interpolation for epoch-based viewpoint builders."""

   from __future__ import annotations

   VALID_TEMPORAL_INTERPOLATIONS = ("step", "linear")


   def interpolate_temporal(
       epoch_values: dict[int, float],
       *,
       strategy: str,
       start_year: int,
       start_month: int,
       end_year: int,
       end_month: int,
   ) -> list[float]:
       ...  # (same body as current _interpolate_temporal)


   def interp_step(...) -> list[float]:
       ...  # (same body)


   def interp_linear(...) -> list[float]:
       ...  # (same body)
   ```

   Note: temporal interpolation is NOT a raster utility — it converts epoch values to monthly time series. Keeping it in a separate `temporal.py` module ensures the name matches the content.

2. **Update both builders:**
   - `ghspop_v1.py`: Remove the three function definitions and `VALID_TEMPORAL_INTERPOLATIONS`. Add import: `from datafactory_viewpoint.temporal import interpolate_temporal, VALID_TEMPORAL_INTERPOLATIONS`. Update call sites (the builder function calls `_interpolate_temporal(...)` — change to `interpolate_temporal(...)`).
   - `ghsbuilts_v1.py`: Same changes.

3. **Verify the constant `DEFAULT_NODATA = -200.0`** in `ghspop_v1.py:45` — this is GHS-POP-specific (float nodata sentinel). It does NOT exist in `ghsbuilts_v1.py`. Leave it in `ghspop_v1.py`. Do NOT move it to either shared module.

4. **Run tests:**
   ```
   uv run pytest tests/test_ghspop_viewpoint.py tests/test_ghsbuilts_viewpoint.py -v
   uv run ruff check src/datafactory_viewpoint/
   uv run mypy src/datafactory_viewpoint/temporal.py
   ```

### Acceptance criteria

- `_interpolate_temporal`, `_interp_step`, `_interp_linear` do not exist in either builder.
- `temporal.py` contains all three functions + `VALID_TEMPORAL_INTERPOLATIONS`.
- Both builders import from `temporal`.
- All viewpoint tests pass. Lint and mypy clean.

### Commit

`refactor: extract temporal interpolation suite into viewpoint temporal module (C-164)`

---

## Task 6: WET Extraction — Consolidation `_tag_table`

**Why:** `_tag_table()` is 100% identical between `consolidators/ucdp.py:198-236` and `consolidators/acled.py:127-159` — 34 lines of copy-paste. It appends 5 metadata columns to a PyArrow table. Zero domain variance.

**Register refs:** C-164 pattern #2.

### Steps

1. **Create shared module:** `src/datafactory_consolidation/tagging.py`
   ```python
   """Shared metadata tagging for consolidation."""

   from __future__ import annotations

   import pyarrow as pa


   def tag_table(
       table: pa.Table,
       *,
       source_type: str,
       source_version: str,
       ingested_at: str,
       harvest_digest: str,
       harvest_timestamp: str,
   ) -> pa.Table:
       """Add consolidation metadata columns to a PyArrow table.

       Adds _source_type, _source_version, _ingested_at,
       _harvest_digest, and _harvest_timestamp columns without
       removing any existing columns (lossless per ADR-013).
       Vintage-aware per ADR-017.
       """
       ...  # (same body as current _tag_table)
   ```

2. **Update both consolidators:**
   - `consolidators/ucdp.py`: Delete `_tag_table` definition (lines 198-236). Add import: `from datafactory_consolidation.tagging import tag_table`. Update call sites: `_tag_table(...)` → `tag_table(...)`.
   - `consolidators/acled.py`: Delete `_tag_table` definition (lines 127-159). Add same import. Update call sites.

3. **Update `src/datafactory_consolidation/__init__.py`:** No change needed — `tagging` is an internal module.

4. **Run tests:**
   ```
   uv run pytest tests/test_consolidation.py tests/test_acled_consolidation.py -v
   uv run ruff check src/datafactory_consolidation/
   uv run mypy src/datafactory_consolidation/tagging.py
   ```

### Acceptance criteria

- `_tag_table` does not exist in either consolidator.
- `tagging.py` contains the single definition.
- Both consolidators import `tag_table` from `tagging`.
- All consolidation tests pass. Lint and mypy clean.

### Commit

`refactor: extract tag_table into shared consolidation module (C-164 #2)`

---

## Task 7: WET Extraction — Compilation Output Writer

**Why:** The output-writing section in `grid_compilation.py:268-303` and `pregridded_compilation.py:241-277` is near-identical — 30 lines writing `grid.npy`, `pgids.npy`, `time_steps.npy`, `feature_names.json`, `provenance.json`, and appending a ledger entry. The only difference: pregridded adds 3 diagnostic fields (`n_placed`, `n_skipped_spatial`, `n_skipped_temporal`) to its ledger dict.

**Register refs:** C-164 pattern #4.

### Steps

1. **Create shared helper** in `src/datafactory_compilation/output.py`:
   ```python
   """Shared output writing for compilation modules."""

   from __future__ import annotations

   import json
   import logging
   from pathlib import Path
   from typing import Any

   import numpy as np

   from datafactory_provenance import (
       DIGEST_SCHEME,
       LEDGER_VERSION,
       append_ledger_entry,
       compute_file_digest,
   )

   logger = logging.getLogger(__name__)


   def write_compilation_output(
       *,
       grid_array: np.ndarray,
       pgids_2d: np.ndarray,
       time_steps: np.ndarray,
       feature_names: list[str],
       output_dir: Path,
       ledger_path: Path,
       dataset_id: str,
       source_path: Path,
       source_digest: str,
       n_placed: int | None = None,
       n_skipped_spatial: int | None = None,
       n_skipped_temporal: int | None = None,
   ) -> str:
       """Write grid output files, provenance, and ledger entry.

       The three n_* parameters are pregridded-compilation diagnostics.
       They are included in the ledger entry only when not None.

       Returns the output digest string.
       """
       output_dir.mkdir(parents=True, exist_ok=True)

       grid_path = output_dir / "grid.npy"
       np.save(grid_path, grid_array)
       np.save(output_dir / "pgids.npy", pgids_2d)
       np.save(output_dir / "time_steps.npy", time_steps)
       (output_dir / "feature_names.json").write_text(
           json.dumps(feature_names)
       )

       output_digest = compute_file_digest(grid_path)

       provenance = {
           "source_path": str(source_path),
           "source_digest": source_digest,
           "grid_shape": list(grid_array.shape),
           "feature_names": feature_names,
           "output_digest": output_digest,
       }
       provenance_path = output_dir / "provenance.json"
       provenance_path.write_text(json.dumps(provenance, indent=2))

       ledger_entry: dict[str, Any] = {
           "dataset": dataset_id,
           "source_path": str(source_path),
           "source_digest": source_digest,
           "grid_shape": list(grid_array.shape),
           "feature_names": feature_names,
           "output_dir": str(output_dir),
           "output_digest": output_digest,
           "ledger_version": LEDGER_VERSION,
           "digest_algorithm": DIGEST_SCHEME,
       }
       if n_placed is not None:
           ledger_entry["n_placed"] = n_placed
       if n_skipped_spatial is not None:
           ledger_entry["n_skipped_spatial"] = n_skipped_spatial
       if n_skipped_temporal is not None:
           ledger_entry["n_skipped_temporal"] = n_skipped_temporal
       append_ledger_entry(ledger_path, ledger_entry)

       return output_digest
   ```

2. **Update `grid_compilation.py`:** Replace lines 268-303 with a call to `write_compilation_output(...)`. The function returns `output_digest` which is not used after this point, so the return value can be ignored. Keep the final `logger.info(...)` and `return output_dir` lines.

3. **Update `pregridded_compilation.py`:** Replace lines 241-277 with a call to `write_compilation_output(...)`, passing the three diagnostic fields as named arguments: `n_placed=n_placed, n_skipped_spatial=n_skipped_spatial, n_skipped_temporal=n_skipped_temporal`. Keep the final `logger.info(...)` and `return output_dir` lines.

4. **Run tests:**
   ```
   uv run pytest tests/test_compiler.py tests/test_ghspop_compilation.py tests/test_ghsbuilts_compilation.py tests/test_acled_compilation.py -v
   uv run ruff check src/datafactory_compilation/
   uv run mypy src/datafactory_compilation/output.py
   ```

### Acceptance criteria

- `np.save(grid_path, ...)` and `provenance.json` writing code exists only in `output.py`.
- Both compilation modules call `write_compilation_output(...)`.
- All compilation tests pass. Lint and mypy clean.

### Commit

`refactor: extract write_compilation_output into shared module (C-164 #4)`

---

## Task 8: Assembly Source-Loader Extraction

**Why:** `assemble_grid.py:240-441` contains 3 structurally identical load-validate-align blocks (ACLED 59 lines, GHS-POP 66 lines, GHS-BUILT-S 77 lines = 202 lines) that differ only by variable name. A parameterized function would replace all 3 blocks and handle the 5th source without new code.

**Register refs:** C-146 (2026-05-24 tech-debt note).

### Steps

1. **Move deferred imports to module level (S-4 falsification fix):** The existing script defers `import numpy as np` and `from datafactory_priogrid.grid_config import DEFAULT_GRID_CONFIG` to inside `main()` (lines 219, 222). Since `_load_source_grid` is defined *before* `main()`, these names would not be in scope — causing `NameError` at runtime. Move these two imports to the module-level import block (after `from pathlib import Path`):
   ```python
   import numpy as np
   from datafactory_priogrid.grid_config import DEFAULT_GRID_CONFIG
   ```
   Leave `import pyarrow.parquet as pq` deferred inside `main()` — it is not used by the helper function. Remove the now-redundant `import numpy as np` and `from datafactory_priogrid.grid_config import DEFAULT_GRID_CONFIG` lines from inside `main()`.

2. **Define the helper function** near the top of `assemble_grid.py` (after the module-level imports, before `main()`):
   ```python
   def _load_source_grid(
       name: str,
       grid_dir: Path,
       time_steps: np.ndarray,
       n_t: int,
   ) -> tuple[np.ndarray, list[str], int] | None:
       """Load, validate, and align a compiled source grid.

       Returns (grid, feature_names, temporal_offset) or None on
       validation failure (after printing a FAIL message). Callers
       must check for None and handle accordingly.
       """
       grid_path = grid_dir / "grid.npy"
       feat_path = grid_dir / "feature_names.json"
       time_path = grid_dir / "time_steps.npy"

       for p in (grid_path, feat_path, time_path):
           if not p.exists():
               print(f"FAIL: {p} not found")
               return None

       grid = np.load(grid_path, mmap_mode="r")
       features = json.loads(feat_path.read_text())
       source_time_steps = np.load(time_path)

       DEFAULT_GRID_CONFIG.assert_grid_shape(grid)

       start_dt = source_time_steps[0]
       matches = np.where(time_steps == start_dt)[0]
       if len(matches) != 1:
           print(
               f"FAIL: {name} start {start_dt} not found "
               f"in UCDP timeline (or ambiguous)"
           )
           return None
       offset = int(matches[0])
       n_source_t = grid.shape[0]
       end_idx = offset + n_source_t

       if end_idx > n_t:
           print(
               f"FAIL: {name} extends beyond UCDP timeline "
               f"(offset {offset} + {n_source_t} > {n_t})"
           )
           return None

       n_features = len(features)
       print(
           f"{name} grid: [T={n_source_t}, "
           f"H={grid.shape[1]}, W={grid.shape[2]}, "
           f"C={n_features}]"
       )
       print(f"{name} features: {features}")
       print(
           f"{name} temporal alignment: indices "
           f"{offset}-{end_idx - 1} in assembled grid"
       )
       if offset > 0 or end_idx < n_t:
           print(
               f"  Zero-fill: 0-{offset - 1}, "
               f"{end_idx}-{n_t - 1}"
           )

       return grid, features, offset
   ```

3. **Replace the 3 blocks in `main()`** with calls to the helper:
   ```python
   # ── ACLED channels ──
   if has_acled:
       acled_result = _load_source_grid(
           "ACLED", config.acled_grid_dir, time_steps, n_t,
       )
       if acled_result is None:
           return 1
       acled_grid, acled_features, acled_offset = acled_result
   else:
       acled_grid, acled_features, acled_offset = None, [], 0
   n_acled = len(acled_features)
   ```
   Repeat for GHS-POP and GHS-BUILT-S. The stacking logic later in `main()` (which reads `acled_grid`, `acled_offset`, etc.) remains unchanged — the variable names are the same.

4. **Error handling note:** The helper returns `None` on validation failure (after printing a FAIL message). `main()` checks for `None` and returns 1, preserving the existing `return 1` error-handling pattern throughout the script. This avoids `sys.exit(1)` which would bypass cleanup, raise `SystemExit`, and make the function untestable.

   **ADR-008 non-compliance (F-5, known, deferred):** The existing script uses `print("FAIL: ...")` throughout rather than `logger.error(...)`, and returns exit codes instead of raising exceptions. ADR-008 says "structural failures must be logged at ERROR and raised explicitly" and "applies to all layers." This extraction preserves the existing pattern rather than rewriting the script's error-handling style. Retrofitting `assemble_grid.py` to use proper logging + exceptions is a separate task (not maintenance scope — it would change the script's CLI output contract).

5. **Run tests:**
   ```
   uv run pytest tests/test_assemble.py -v
   uv run ruff check scripts/assemble_grid.py
   ```

### Acceptance criteria

- `import numpy as np` and `from datafactory_priogrid.grid_config import DEFAULT_GRID_CONFIG` are at module level, not inside `main()`.
- No duplicate imports remain inside `main()` for these two.
- `_load_source_grid()` defined once, called 3 times (ACLED, GHS-POP, GHS-BUILT-S).
- `assemble_grid.py` total line count is under 720 lines (verify: `wc -l scripts/assemble_grid.py`).
- All assembly tests pass. Lint clean.

### Commit

`refactor: extract _load_source_grid in assemble_grid.py (C-146)`

---

## Task 9: Dead Module Cleanup (C-176 + C-03)

**Why:** `datafactory_synthetic` is declared in `pyproject.toml`, tested for `__all__` existence, and subject to import enforcement — but exports nothing and is imported by nothing. C-03 warns about protocol proliferation in this module, but the module is dead. Both entries are noise.

**Register refs:** C-176 (Tier 4), C-03 (merged into C-176 in Task 1).

### Steps

1. **Delete the module directory:** `src/datafactory_synthetic/` (including `__init__.py`, `ARCHITECTURE.md`, and any `__pycache__`).

2. **Update `pyproject.toml`:** Remove `"datafactory_synthetic"` from the `[tool.hatch.build.targets.wheel.packages]` list.

3. **Update tests:**
   - `tests/test_package_structure.py`: Remove `datafactory_synthetic` from the package list that's checked for `__all__`.
   - `tests/test_import_enforcement.py`: Remove `datafactory_synthetic` from the `ALLOWED_INTERNAL_IMPORTS` dict.

4. **Update ADRs (F-7 falsification fix):** Seven ADRs reference `datafactory_synthetic` by name. Deleting the module without updating them creates governance drift. Update these:
   - `docs/ADRs/012_four_layer_data_architecture.md`: Remove `datafactory_synthetic` from the import table, DAG diagram, and data flow section. Add a note in the Decision or Consequences section: "datafactory_synthetic was removed in v1.2.21 (dead module, zero exports). Synthetic data generation is deferred to a future design."
   - `docs/ADRs/001_ontology_of_the_repository.md`: Remove or strike through `datafactory_synthetic` references.
   - `docs/ADRs/002_topology_and_dependency_rules.md`: Remove from dependency lists (superseded by ADR-012 but still referenced).
   - `docs/ADRs/005_testing_as_mandatory_critical_infrastructure.md`: Remove synthetic-specific test examples if they reference the module by name.
   - `docs/ADRs/009_boundary_contracts_and_configuration_validation.md`: Remove from package lists.
   - Verify with: `grep -rl "datafactory_synthetic" docs/ADRs/` — must return no results.

5. **Refresh the editable install** so hatchling picks up the removed package:
   ```
   uv sync
   ```

5. **Verify:**
   ```
   uv run pytest tests/test_package_structure.py tests/test_import_enforcement.py -v
   uv run ruff check .
   uv run python -c "import datafactory_synthetic" 2>&1 | grep ModuleNotFoundError
   ```
   The last command must print a `ModuleNotFoundError` — confirms the package is fully gone from the installed environment, not just the filesystem.

6. **Update the register** (if not already done in Task 1): Mark C-176 as resolved with note: "Resolved 2026-05-24: module deleted, removed from pyproject.toml and test infrastructure."

### Acceptance criteria

- `src/datafactory_synthetic/` directory does not exist.
- `datafactory_synthetic` does not appear in `pyproject.toml`.
- No test references `datafactory_synthetic`.
- `import datafactory_synthetic` raises `ModuleNotFoundError`.
- All tests pass.

### Commit

`chore: delete dead datafactory_synthetic module (C-176, C-03)`

---

## Task 10: Direct Tests for Extracted Modules (F-2 Falsification Fix)

**Why:** ADR-005 mandates test coverage for all non-trivial functionality. Tasks 4-7 create 4 new shared modules. The existing integration tests exercise them indirectly through the builders, but a developer modifying `raster_io.py` has no way to know which test file to run. Direct tests make the coverage connection explicit and satisfy ADR-005's spirit.

**Register refs:** ADR-005 compliance (falsification audit F-2, 2026-05-24).

### Steps

1. **Create `tests/test_raster_io.py`:** One Green test that calls `read_geotiff` on a tiny synthetic GeoTIFF (create a 4x4 pixel TIFF with tifffile in a temp dir) and verifies the returned tuple structure (array shape, tiepoint, pixel scale types).

2. **Create `tests/test_temporal.py`:** One Green test that calls `interpolate_temporal` with 3 epoch values and verifies the output list length and boundary values. One Beige test that passes an unknown strategy string and verifies `ValueError` is raised.

3. **Create `tests/test_tagging.py`:** One Green test that calls `tag_table` on a minimal PyArrow table and verifies the 5 metadata columns are added without removing originals.

4. **Create `tests/test_compilation_output.py`:** One Green test that calls `write_compilation_output` with a small numpy array in a tmp dir and verifies all 5 output files exist and the returned digest is non-empty.

5. **Run:** `uv run pytest tests/test_raster_io.py tests/test_temporal.py tests/test_tagging.py tests/test_compilation_output.py -v`

### Acceptance criteria

- Each extracted module has at least one direct test file.
- All direct tests pass.
- Test file names match the module names: `tests/test_raster_io.py`, `tests/test_temporal.py`, `tests/test_tagging.py`, `tests/test_compilation_output.py` all exist.

### Commit

`test: add direct tests for extracted shared modules (ADR-005, F-2)`

---

## Final Verification

After all tasks are complete:

1. **Full test suite:** `uv run pytest` — 0 FAILED, 0 ERROR.
2. **Lint:** `uv run ruff check .` — clean.
3. **Type check:** `uv run mypy src/` — no new errors.
4. **Smoke-test new shared modules:**
   ```
   uv run python -c "from datafactory_viewpoint.raster_io import read_geotiff; print('raster_io OK')"
   uv run python -c "from datafactory_viewpoint.temporal import interpolate_temporal, VALID_TEMPORAL_INTERPOLATIONS; print('temporal OK')"
   uv run python -c "from datafactory_consolidation.tagging import tag_table; print('tagging OK')"
   uv run python -c "from datafactory_compilation.output import write_compilation_output; print('output OK')"
   uv run python -c "from datafactory_provenance import VIEWS_EPOCH_YEAR; print(f'VIEWS_EPOCH_YEAR={VIEWS_EPOCH_YEAR}')"
   ```
5. **ADR coherence:** `grep -rl "datafactory_synthetic" docs/ADRs/` returns no results.
6. **Git status:** Only expected files modified. No untracked files except this sprint plan.
7. **Register coherence:** Header counts match actual entries (mechanical grep count). All new cross-references valid.

### Ship gate

When all 7 verification items above pass:

1. `git log --oneline development..HEAD` — review the commit list.
2. `git push -u origin chore/maintenance-v1221`
3. Create PR to `development`: `gh pr create --base development --title "chore: maintenance v1.2.21 — WET extraction, CI signal, register curation"`
4. The sprint is **done** when the PR is merged to `development`.

---

## What This Sprint Does NOT Do

These items were explicitly evaluated and deferred:

| Item | Why deferred |
|------|-------------|
| C-164 patterns 6-8 (harvest wrappers, pipeline runners, provenance recording) | Moderate complexity, larger refactor scope. Do after safe extractions prove the pattern works. |
| `_aggregate_with_alignment` extraction | Domain-justified divergence: ghspop has float32+nodata masking, ghsbuilts has uint32+no masking. NOT copy-paste — do not extract. |
| C-138 (post-deploy verification script) | New functionality, not cleanup. Needs design (what to compare, tolerance thresholds). |
| Cluster C (zero-fill root cause — zero vs NaN) | Architectural design decision with consumer-breaking implications. Not maintenance scope. |
| Cluster D (harvest caching contract) | Blocked by D-27 (two-tier vs single-tier decision). Good candidate for next sprint. |
| C-88, C-121 (SSH restriction, Phase 6.4) | Blocked on PRIO IT providing VPN CIDR ranges. |
| C-173 (swap on Hetzner) | Server ops task, not code. Execute on the server directly. |
| Cluster F (memory scaling) | All deferred per D-23/D-24 resolutions. Data volume 60x below threshold. |
| C-189 (GHS-BUILT-S test parity) | Large effort (significant test writing). Lowest-risk source — same provider as GHS-POP. |
| C-195 (falsification test archival) | Lower priority than code extraction. Revisit after WET extraction. |
| P-6 SAP: Provenance Zone of Pain (I=0.00, A=0.00, D=1.00) | Architecture sprint scope — needs Protocol/ABC design for provenance's contract surface. Not maintenance. |

---

## Register Updates After Sprint

After this sprint, update C-164 to reflect completed extractions:

- Pattern #2 (`_tag_table`): **Resolved** — extracted to `datafactory_consolidation.tagging`.
- Pattern #4 (compilation output writer): **Resolved** — extracted to `datafactory_compilation.output`.
- Pattern #5 (`_VIEWS_EPOCH_YEAR`): **Resolved** — moved to `datafactory_provenance` (Layer 0), all copies replaced.
- Raster I/O (`_read_geotiff`): **Resolved** — extracted to `datafactory_viewpoint.raster_io`.
- Temporal interpolation: **Resolved** — extracted to `datafactory_viewpoint.temporal`.

Remaining open C-164 patterns: #1 (harvester config validators), #3 (viewpoint scaffolding), #6 (provenance recording), #7 (pipeline runners), #8 (harvest wrappers). C-164 stays open (5 of 8 patterns remain).

Mark C-176 as resolved (module deleted).
Mark C-169 as resolved (CI signal restored).

After these updates, the register should have: **63 open concerns** (65 after Task 1, minus C-176 resolved in Task 9, minus C-169 resolved in Task 2). Verify with a mechanical grep count before updating the header.
