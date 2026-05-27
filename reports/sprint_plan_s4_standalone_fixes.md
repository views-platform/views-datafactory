# Sprint Plan S4: Standalone Fixes

**Date:** 2026-05-26
**Branch:** `development`
**Goal:** Close 3 standalone entries (C-175, C-129, C-149) that are independent of each other and of the other sprints. Each is a small, safe, targeted fix with clear acceptance criteria. Together they address: silent zero-fill on field rename, partition boundary magic values, and unmapped GAUL cell transparency.
**Estimated effort:** 2–3 hours total.
**Source:** `/review-rr prioritize` (2026-05-26), standalone rankings #1, #2, #5.
**Prerequisite:** None. These tasks are independent of sprints S1-S3 and of each other. They can be done in any order or interleaved with other work.
**Blocking:** None.

---

## Context

The prioritize report ranked 7 standalone entries. Three are actionable with small, well-defined fixes:

| Rank | Entry | Tier | Fix Effort | Why now |
|------|-------|------|-----------|---------|
| 1 | C-149 | 2 | Medium | 4% fatality gap in CM output; consumers training CM models have no visibility |
| 2 | C-129 | 3 | Medium | Partition boundaries duplicated in 5+ locations; next partition shift requires coordinated find-replace |
| 5 | C-175 | 3 | Small | One-line guard prevents entire feature column becoming silent zeros on UCDP field rename |

The remaining 4 standalone entries (C-189, C-153, C-146, C-126) are deferred: C-189 needs ~30 tests (high effort), C-153 is an external dependency, C-146 is an architectural change, and C-126 requires a separate repo.

---

## Task 1: Add `value_field` Column Validation (C-175)

**Why:** The `sum_field` and `max_field` aggregation strategies in `aggregation.py` use `e.get(field, 0) or 0` — if a field is missing from an event dict, it silently contributes 0. If UCDP renamed `best` to `best_estimate`, every event would contribute 0 to the `fatalities` feature. The compiled grid would contain all zeros for that column, indistinguishable from "zero events." The `count` strategy is unaffected (ignores field values). The `_required_columns()` function in `grid_compilation.py` already validates `lat_field`, `lon_field`, and `date_field` against the table schema — but `value_field` is not validated.

**Register ref:** C-175 (T3). Cross-ref: C-45 (Parquet schema evolution), C-36 (UCDP no schema versioning).

### The fix

Add `value_field` validation to the column check in `grid_compilation.py`. This is a one-line addition to an existing validation block.

### Steps

1. **Read the current validation code:**
   ```
   src/datafactory_compilation/grid_compilation.py
   ```
   Find the `_required_columns()` function or the column validation block that checks `config.lat_field`, `config.lon_field`, `config.date_field` against table column names.

2. **Add value_field validation.** For each feature in `config.features`, if the feature's aggregation strategy is `sum_field` or `max_field`, add `feature.value_field` to the set of required columns. Example:

   ```python
   required = {config.lat_field, config.lon_field, config.date_field}
   for feat in config.features:
       if feat.value_field is not None:
           required.add(feat.value_field)
   ```

   Then assert all required columns are present in the table:
   ```python
   missing = required - set(table.column_names)
   if missing:
       msg = f"Table missing required columns: {missing}"
       raise ValueError(msg)
   ```

3. **Verify the guard catches missing fields:**
   ```bash
   uv run pytest tests/test_compilation.py -v -k "missing" --no-header
   ```
   If no existing test covers this, add one:
   ```python
   def test_missing_value_field_raises(self):
       """C-175: value_field not in table columns should raise, not silently zero-fill."""
       # Create config with value_field="nonexistent"
       # Assert ValueError is raised during compilation
   ```

4. **Run full test suite to confirm no regressions:**
   ```bash
   uv run pytest tests/test_compilation.py tests/test_acled_compilation.py -v
   ```

### What NOT to change

- Do not modify `aggregation.py` itself (the `e.get(field, 0)` pattern). The fix belongs at the validation boundary, not in the aggregation loop.
- Do not add validation for `count` strategy features (they don't use `value_field`).
- Do not add schema evolution handling — that's C-45's scope.

### Acceptance criteria

- Compilation with a `value_field` not present in the table raises `ValueError` with the missing field name.
- Compilation with valid `value_field` continues to work (no regression).
- At least one test exercises the missing-value_field path.
- `uv run ruff check src/datafactory_compilation/grid_compilation.py` passes.

### Commit

```
fix: validate value_field columns before aggregation (C-175)
```

---

## Task 2: Extract Partition Boundaries to Single Source of Truth (C-129)

**Why:** The calibration/validation/forecasting partition boundaries (121/444, 445/492, 493/540) appear as bare literals in 5+ independent locations across two repos. No shared authoritative definition exists. Adding a new partition type or shifting a boundary requires coordinated find-and-replace with no compiler or test to catch a missed update. ADR-003 requires: "a single source of truth must be designated."

**Register ref:** C-129 (T3). Cross-ref: ADR-003 (single source of truth).

### Current locations of partition literals

| File | Line(s) | Values |
|------|---------|--------|
| `scripts/generate_consumer_data.py` | ~56 | `PARTITIONS = {"calibration": (121, 444), "validation": (445, 492), "forecasting": (493, 540)}` |
| `examples/ex_partitions.py` | 21-101 | 6+ occurrences in assertions |
| `tests/test_consumer_data.py` | ~162, 169 | Partition boundary assertions |
| `tests/test_consumer_parity.py` | ~57 | Calibration start |
| Downstream: `bright_starship/configs/config_partitions.py` | — | Same literals (different repo) |

### The fix

Create a `PARTITIONS` frozen dict in a shared location within `src/` and have all in-repo consumers import from it.

### Steps

1. **Choose the location.** The partitions are a temporal concept used by consumers. The most natural home is `src/datafactory_priogrid/partitions.py` (alongside `temporal_config.py` which already defines `TemporalConfig` and `DEFAULT_TEMPORAL_CONFIG`). Alternative: `src/datafactory_query/partitions.py` (closer to consumers). Use `datafactory_priogrid` — it's the temporal/spatial backbone package.

2. **Create `src/datafactory_priogrid/partitions.py`:**
   ```python
   """VIEWS partition boundaries (month IDs).

   Single source of truth for calibration, validation, and
   forecasting partitions. All consumers must import from here.
   Ref: ADR-003 (single source of truth).
   """

   from __future__ import annotations

   from types import MappingProxyType

   PARTITIONS: MappingProxyType[str, tuple[int, int]] = MappingProxyType({
       "calibration": (121, 444),
       "validation": (445, 492),
       "forecasting": (493, 540),
   })
   ```

   Using `MappingProxyType` makes the dict immutable at runtime (consistent with the frozen dataclass convention used elsewhere).

3. **Update `src/datafactory_priogrid/__init__.py`:** Add `PARTITIONS` to `__all__`.

4. **Update consumers:**

   a. `scripts/generate_consumer_data.py`: Replace the inline `PARTITIONS` dict with:
      ```python
      from datafactory_priogrid import PARTITIONS
      ```
      Remove the old `PARTITIONS = {...}` definition.

   b. `examples/ex_partitions.py`: Import `PARTITIONS` and use it instead of bare literals.

   c. `tests/test_consumer_data.py`: Import `PARTITIONS` and reference `PARTITIONS["calibration"][0]` instead of `121`.

   d. `tests/test_consumer_parity.py`: Import `PARTITIONS` and reference accordingly.

5. **Add a test that the partitions are contiguous and non-overlapping:**
   ```python
   def test_partitions_contiguous():
       """Partitions must be contiguous: validation starts where calibration ends + 1."""
       from datafactory_priogrid import PARTITIONS
       cal = PARTITIONS["calibration"]
       val = PARTITIONS["validation"]
       fcast = PARTITIONS["forecasting"]
       assert val[0] == cal[1] + 1
       assert fcast[0] == val[1] + 1
   ```

6. **Verify no remaining bare literals:**
   ```bash
   # Search for the boundary values as bare literals (should only appear in the new source file and tests)
   grep -rn "121.*444\|445.*492\|493.*540" src/ scripts/ tests/ examples/ --include="*.py" | grep -v "partitions.py" | grep -v "__pycache__"
   ```

### What NOT to change

- Do not update `bright_starship/configs/config_partitions.py` — that's a different repo. Document the downstream consumer in a comment in `partitions.py`.
- Do not change the partition values themselves. This task is about deduplication, not recalibration.
- Do not add dynamic partition computation (e.g., deriving from dates). The values are fixed by VIEWS convention.

### Acceptance criteria

- `src/datafactory_priogrid/partitions.py` exists with `PARTITIONS` as `MappingProxyType`.
- `PARTITIONS` is in `datafactory_priogrid.__all__`.
- `scripts/generate_consumer_data.py` imports from `datafactory_priogrid` (no inline definition).
- `examples/ex_partitions.py` imports from `datafactory_priogrid`.
- `tests/test_consumer_data.py` and `tests/test_consumer_parity.py` import from `datafactory_priogrid`.
- Grep for bare partition literals returns only the new `partitions.py` and its test.
- `uv run pytest tests/test_consumer_data.py tests/test_consumer_parity.py examples/ex_partitions.py -v` passes.
- `uv run ruff check src/datafactory_priogrid/partitions.py` passes.

### Commit

```
refactor: extract PARTITIONS to single source of truth (C-129, ADR-003)
```

---

## Task 3: Add Runtime Warning for Unmapped GAUL Cells in CM Aggregation (C-149)

**Why:** 603 PRIO-GRID cells in `africa_me_legacy` have centroids outside any FAO GAUL polygon and are assigned `gaul0_code = -1` during assembly. `grid_to_country_month()` filters on `country_ids > 0`, silently dropping these cells from CM output. The dropped cells carry significant fatalities: 45,593 sb_best, 6,012 ns_best, 7,986 os_best across 435 months, with single-month peaks up to 2,688. This creates a ~4% systematic gap between PGM and CM fatality totals. Tests account for the gap (C-149 fix from 2026-04-30), but consumers have no runtime visibility.

**Register ref:** C-149 (T2, RESOLVING). The code fix (tests accounting for the gap) is done. What remains is consumer transparency: a runtime warning listing excluded cells and quantifying the gap.

### The fix

Add a warning to `grid_to_country_month()` that fires when the function drops cells with nonzero event values. The warning should include: (a) count of excluded cells, (b) count of excluded cells that have events, (c) total excluded fatalities per feature.

### Steps

1. **Read the current filtering code:**
   ```
   src/datafactory_adapters/grid_to_country_month.py
   ```
   Find the line that filters on `country_ids > 0` (around line 72-76).

2. **Add a warning after the filter.** Before discarding the excluded cells, compute event totals for the excluded rows:

   ```python
   import warnings

   # Identify excluded cells
   excluded_mask = country_ids <= 0
   n_excluded = int(excluded_mask.sum())

   if n_excluded > 0:
       # Check if any excluded cells have nonzero values
       excluded_data = grid_data[excluded_mask]  # or however the data is structured
       excluded_totals = excluded_data.sum(axis=0)  # per-feature totals
       n_with_events = int((excluded_data.sum(axis=1) > 0).sum())

       if n_with_events > 0:
           warnings.warn(
               f"CM aggregation excluded {n_excluded} cells with "
               f"gaul0_code <= 0 (unmapped GAUL centroids). "
               f"{n_with_events} of these cells have nonzero values. "
               f"This creates a systematic gap between PGM and CM totals. "
               f"See C-149 in the technical risk register.",
               UserWarning,
               stacklevel=2,
           )
   ```

   The exact implementation depends on the function signature and data flow. The key requirements are:
   - Warning fires only when excluded cells have nonzero data (not on every call).
   - Warning includes the count of excluded cells and the count with events.
   - Warning references C-149 for context.

3. **Add a test that verifies the warning fires:**
   ```python
   def test_cm_aggregation_warns_on_excluded_cells_with_events(self):
       """C-149: Consumer should be warned about excluded cells with nonzero values."""
       # Create test data where some cells have gaul0_code = -1 and nonzero events
       # Call grid_to_country_month
       # Assert UserWarning is raised with "unmapped GAUL" in message
   ```

4. **Verify existing tests still pass:**
   ```bash
   uv run pytest tests/test_model_parity.py tests/test_pipeline_consistency.py -v -k "CM"
   ```

### What NOT to change

- Do not change the filtering behavior itself (cells with `gaul0_code <= 0` are correctly excluded from CM output).
- Do not change the test tolerances that account for the gap.
- Do not attempt to improve the GAUL spatial join (buffered centroids, polygon-edge matching) — that's a separate, larger effort.
- Do not add the warning to PGM output (PGM includes all cells, no exclusion).

### Acceptance criteria

- `grid_to_country_month()` emits `UserWarning` when excluded cells have nonzero values.
- Warning message includes the count of excluded cells and the count with events.
- Warning does not fire when excluded cells have all-zero values (e.g., ocean cells).
- Existing CM parity tests pass unchanged.
- At least one new test verifies the warning.
- `uv run ruff check src/datafactory_adapters/grid_to_country_month.py` passes.

### Commit

```
feat: warn consumers when CM aggregation excludes cells with events (C-149)
```

---

## Task 4: Update Risk Register

**Why:** After Tasks 1-3, three entries can be resolved or advanced.

### Entry status updates

| Entry | Before | After | Rationale |
|-------|--------|-------|-----------|
| C-175 | T3 DEFER | **RESOLVED** | `value_field` columns validated before aggregation |
| C-129 | T3 OPEN | **RESOLVED** | `PARTITIONS` extracted to `datafactory_priogrid.partitions`; single source of truth |
| C-149 | T2 RESOLVING | **RESOLVED** | Runtime warning added; consumer has visibility into excluded cells and gap magnitude |

### Steps

1. Strike through all 3 entries in the summary table.
2. Add resolution notes to each full entry.
3. Move full entries to resolved archive.
4. Update work packages:
   - "Compilation correctness" package: both items (C-174 resolved earlier, C-175 now resolved). Mark package as resolved.
   - "ADR-003 compliance" package: C-129 now resolved. Update package (C-128 and C-168 already resolved).
   - "Data integrity" package: C-149 now resolved. Only C-138 remains (closed in S3).
5. Update header counts.

### Header count impact (cumulative with S1 + S2 + S3)

If all prior sprints completed: starting from ~49 open (estimated after S1-S3).
- Resolve C-175 (T3): T3 count decreases by 1.
- Resolve C-129 (T3): T3 count decreases by 1.
- Resolve C-149 (T2): T2 count decreases by 1.

### Acceptance criteria

- All 3 entries struck through in summary table.
- Compilation correctness work package marked resolved.
- `grep "C-175\|C-129\|C-149" reports/technical_risk_register.md | grep -c "Resolved"` returns 3.

### Commit

```
docs: resolve C-175, C-129, C-149 after standalone fixes
```

---

## Dependency Map

```
Task 1 (C-175)  ──┐
                   ├──→  Task 4 (register update)
Task 2 (C-129)  ──┤
                   │
Task 3 (C-149)  ──┘

No dependencies between Tasks 1, 2, 3 — they can be done in any order or in parallel.
Task 4 should be done after all three are complete.
```

---

## Final Verification

```bash
# All affected tests pass
uv run pytest tests/test_compilation.py tests/test_acled_compilation.py tests/test_consumer_data.py tests/test_consumer_parity.py -v

# No bare partition literals outside the source file
grep -rn "121.*444\|445.*492\|493.*540" src/ scripts/ tests/ examples/ --include="*.py" | grep -v "partitions.py" | grep -v "__pycache__" | wc -l
# Expected: 0 (or only comments/docs)

# Ruff clean
uv run ruff check src/datafactory_compilation/grid_compilation.py src/datafactory_priogrid/partitions.py src/datafactory_adapters/grid_to_country_month.py

# Register counts consistent
grep -c "^### C-" reports/technical_risk_register.md  # per-section grep to verify
```
