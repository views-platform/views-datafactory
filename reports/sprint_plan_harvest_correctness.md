# Sprint Plan: Harvest Correctness Quick Win

**Date:** 2026-05-29
**Status:** Draft — developing iteratively
**Branch:** TBD (from `development`)
**Register entries:** C-184, C-185, C-186, C-159, D-29
**Estimated effort:** ~4 hours
**Work package:** Harvest correctness (register row 85)

---

## Problem Statement

Three harvesters have cache integrity gaps that could accept
corrupted or silently-updated data:

1. **C-184 (Tier 3):** ACLED's `_year_is_cached()` checks file
   existence + ledger entry, but never verifies the file's content
   matches the ledger digest. A truncated Parquet (e.g., from
   disk-full during write) passes both checks.

2. **C-185 (Tier 4):** GHS-POP's `_fetch_epoch()` has the same
   weakness — `tif_path.exists()` + `last_digest_for_version()` but
   no digest comparison of the actual file.

3. **C-186 (Tier 3):** Shapefile harvester uses `"changed": True/False`
   instead of the standard outcome vocabulary (`"outcome": "success"`,
   `"outcome": "unchanged"`, `"outcome": "failed"`). No error handling
   around download/extraction. ADR-032 overstates compliance.

4. **C-159 (Tier 4):** ACLED snapshot archiving and revision comparison
   paths are untested.

5. **D-29 (Disagreement):** How deep to retrofit the shapefile
   harvester — full outcome compliance vs. organic evolution.

---

## The Gold Standard: UCDP Two-Tier Caching

UCDP candidate (`ucdp_candidate.py:324-347`) and dot9
(`ucdp_dot9.py:343-379`) implement the correct pattern:

1. **Fetch first** — download/validate the data from the API
2. **Compute digest of fetched content** — `validation.content_digest`
3. **Compare to previous** — `previous_digest != validation.content_digest`
4. **Only store if changed** — record `"outcome": "unchanged"` on
   cache hit with matching digest
5. **Archive + compare snapshots** — `compare_snapshots()` then
   `archive_snapshot()` before overwriting

This is the pattern all harvesters should converge toward.

---

## Current State (Code Locations)

### C-184: ACLED `_year_is_cached`

**File:** `src/datafactory_harvester/sources/acled.py:435-443`

```python
def _year_is_cached(year: int, config: AcledConfig) -> bool:
    snap_path = config.data_dir / f"acled_{year}_{year}.parquet"
    if not snap_path.exists():
        return False
    return last_digest_for_version(
        config.ledger_path, version
    ) is not None
```

**Missing:** No call to `compute_file_digest(snap_path)` to verify
the file matches the ledger digest. The function only checks
"file exists AND ledger has a digest" — never "file content matches
ledger digest."

**Fix pattern:** Add `compute_file_digest(snap_path)` comparison:

```python
def _year_is_cached(year: int, config: AcledConfig) -> bool:
    snap_path = config.data_dir / f"acled_{year}_{year}.parquet"
    if not snap_path.exists():
        return False
    version = f"{year}_{year}"
    previous = last_digest_for_version(config.ledger_path, version)
    if previous is None:
        return False
    actual = compute_file_digest(snap_path)
    return actual == previous
```

**`compute_file_digest` location:**
`src/datafactory_provenance/digests_and_ledgers.py:88-117` — streams
file in 64 KB chunks, returns truncated hex digest. Already imported
throughout the codebase.

### C-185: GHS-POP `_fetch_epoch` cache check

**File:** `src/datafactory_harvester/sources/ghspop.py:150-164`

```python
if not force_refresh and tif_path.exists():
    previous = last_digest_for_version(config.ledger_path, version)
    if previous is not None:
        logger.info("Epoch %d cached (digest: %s)", epoch, previous)
        return {"outcome": "cached", "content_digest": previous, ...}
```

**Missing:** Same as ACLED — `previous` is the ledger digest, not the
actual file digest. No `compute_file_digest(tif_path)` call.

**Fix pattern:** Same approach — compute actual digest, compare to
ledger. GHS-POP also has GHS-BUILT-S equivalent at
`src/datafactory_harvester/sources/ghsbuilts.py` — check if that
has the same gap.

### C-186: Shapefile harvester outcome vocabulary

**File:** `src/datafactory_priogrid/shapefile_harvester.py:127-165`

```python
# On cache hit (line 153):
append_ledger_entry(config.ledger_path, {**base_entry, "changed": False})

# On new data (line 163):
append_ledger_entry(config.ledger_path, {**base_entry, "changed": changed, ...})
```

**Issues:**
1. Uses `"changed": True/False` instead of `"outcome": "success"` /
   `"outcome": "unchanged"` / `"outcome": "failed"`
2. No try/except around `request_with_retry()` (line 133) or
   `_extract_zip()` (line 158)
3. No `"outcome": "failed"` ever recorded

**Fix:** Replace `"changed"` with `"outcome"` vocabulary. Add
try/except around download and extraction. Record `"outcome": "failed"`
on error.

**D-29 resolution:** Adopt the minimal fix — outcome vocabulary
alignment without full two-tier digest retrofit. The shapefile is
downloaded infrequently (PRIO-GRID shapefile changes approximately
never), so full two-tier caching is over-engineering.

### C-159: ACLED archiving untested

**File:** `src/datafactory_harvester/sources/acled.py:523-550`

The archiving logic itself exists and is correct:
```python
comparison = compare_snapshots(snap_path, events, ...)
if snap_path.exists():
    archive_snapshot(snap_path)
save_event_snapshot(events, snap_path)
```

**Gap:** No test exercises this path. The `compare_snapshots` and
`archive_snapshot` calls are in `_fetch_single_year()` but the test
suite only tests the happy path (fresh fetch, no prior snapshot).

---

## Task Breakdown

### Task 1: ACLED digest verification (C-184)
- [ ] Edit `acled.py:435-443`: add `compute_file_digest` comparison
- [ ] Add import for `compute_file_digest`
- [ ] Add test: cached file with wrong content is re-fetched
- [ ] Add test: cached file with correct content is skipped

### Task 2: GHS-POP digest verification (C-185)
- [ ] Edit `ghspop.py:150-164`: add `compute_file_digest` comparison
- [ ] Check GHS-BUILT-S (`ghsbuilts.py`) for same gap — fix if present
- [ ] Add test for GHS-POP cache integrity
- [ ] Add test for GHS-BUILT-S cache integrity (if applicable)

### Task 3: Shapefile outcome vocabulary (C-186)
- [ ] Replace `"changed": True/False` with `"outcome"` vocabulary
- [ ] Add try/except around download + extraction
- [ ] Record `"outcome": "failed"` on error
- [ ] Add test for outcome recording
- [ ] Resolve D-29: document decision (minimal fix, not full retrofit)

### Task 4: ACLED archiving tests (C-159)
- [ ] Add test: `_fetch_single_year` with existing snapshot triggers
  `compare_snapshots` + `archive_snapshot`
- [ ] Add test: archived snapshot exists after re-fetch
- [ ] Add test: revision detection (changed fatalities count)

### Task 5: Register updates
- [ ] Resolve C-184, C-185, C-186, C-159
- [ ] Close D-29 with decision rationale
- [ ] Update header counts
- [ ] Update ADR-032 if needed (correct false claims about compliance)

---

## ADR-032 Accuracy Audit

ADR-032 (`docs/ADRs/032_harvest_idempotence.md`) makes claims about
harvest compliance that should be verified during this sprint:

- **Line 139:** Claims ACLED uses "Single-tier with `"cached"` outcome
  on skip." Actually ACLED never records outcome `"cached"` —
  `_year_is_cached()` returns True/False without any ledger recording.
  Only `_fetch_single_year()` records `"outcome": "success"` or
  `"outcome": "failed"`.
- **Line 143:** Correctly identifies shapefile as "No failure recording
  (C-186)" — this is accurate.

After fixing C-184/C-186, update ADR-032 compliance table to reflect
actual behavior.

---

## Verification

```bash
uv run ruff check src/datafactory_harvester/ src/datafactory_priogrid/
uv run pytest tests/ -q
uv run pytest tests/test_harvest*.py -v  # harvest-specific tests
```

---

## Open Questions

1. Does GHS-BUILT-S have the same cache gap as GHS-POP? (Check
   `ghsbuilts.py` cache logic during Task 2)
2. Should `_year_is_cached` log a warning when digest mismatch is
   detected (corrupted file found)?
3. Should we add a `--verify-cache` flag to harvest scripts that
   checks all cached files against ledger digests?
4. Performance impact of `compute_file_digest` on large GeoTIFFs
   (~100-300 MB)? Probably negligible given it streams in 64 KB
   chunks.

---

## Dependencies

- **Blocks:** Nothing directly — but harvest correctness is a
  prerequisite for trusting cached data in any deployment
- **Blocked by:** Nothing
- **Related:** C-164 (WET debt — harvest wrappers are pattern #8),
  ADR-032 (harvest idempotence documentation)
