# R&D Plan: Bounded-Memory Compilation Pipeline

**Date:** 2026-05-28
**Origin:** Expert code review during v1.2.22 deployment (Sprint S3)
**Status:** Proposed
**Branch:** TBD (to be created from `development`)

---

## Problem Statement

The compilation pipeline allocates the entire output grid as a single
in-memory array via `np.full()` before writing to disk. Grid shape is
`[T, H, W, C]` where T=456 months, H=360, W=720, C=features.

Current memory requirements per compile step:

| Source | Features (C) | Grid size | + Parquet overhead | Total peak |
|--------|-------------|-----------|-------------------|------------|
| UCDP | 6 | 2.6 GB | ~0.4 GB | ~3 GB |
| ACLED | 8 | 3.5 GB | ~0.8 GB | ~4.3 GB |
| GHS-POP | 1 | 0.4 GB | ~0.1 GB | ~0.5 GB |
| GHS-BUILT-S | 1 | 0.4 GB | ~0.1 GB | ~0.5 GB |
| V-Dem | 22 | 9.7 GB | ~5.7 GB | ~15.4 GB |
| Assembly | 75 | 33 GB | (mmap inputs) | ~0.2 GB* |

*Assembly already uses memory-mapped I/O — it is not part of the problem.

The V-Dem compile step OOM-killed the production server three times
during the v1.2.22 deployment, requiring server rescaling (8→16 GB)
and 16 GB swap. Each new data source adds features, and each year
adds 12 time steps. Without intervention, the next large source
(WDI: 20-50 features) will push per-source compile past 20 GB.

**Root cause:** `np.full()` at `pregridded_compilation.py:171` and
`grid_compilation.py:224` allocates the full grid in RAM. The
placement loops that follow (row-by-row cell writes) would work
identically on a memory-mapped array.

**Existence proof:** `assemble_grid.py:491` already uses
`np.lib.format.open_memmap()` for the assembled grid. The pattern
is proven, tested, and running in production.

---

## Objectives

1. Per-source compile runs within 1 GB peak RSS regardless of feature count
2. No change to output format (grid.npy, pgids.npy, time_steps.npy, feature_names.json)
3. No change to downstream consumers (assembly, export, query)
4. Server can return to CPX32 (8 GB RAM) without swap dependency
5. Clear diagnostic messages when resources are insufficient (no silent OOM kills)

---

## Four Steps

### Step 1: Memory-Mapped Compilation Output

**What:** Replace `np.full()` with `np.lib.format.open_memmap()` in
both `compile_pregridded()` and `compile_grid()`.

**Where:**
- `src/datafactory_compilation/pregridded_compilation.py:171-175`
- `src/datafactory_compilation/grid_compilation.py:224-228`

**How it works:** Instead of allocating the grid in RAM, create it as
a memory-mapped file on disk. The OS page cache handles which pages
are in physical memory at any time. The placement loops (element-wise
assignment to `grid_array[t, r, c, f]`) work identically — numpy
mmap arrays support the same indexing operations as regular arrays.
Peak memory drops from grid-size to page-cache-size (~100-200 MB).

**Pattern to follow:** `assemble_grid.py:490-496`:
```python
assembled = np.lib.format.open_memmap(
    str(tmp_path),
    mode="w+",
    dtype=dtype,
    shape=(n_t, n_h, n_w, n_total),
)
```

**Fill value handling:** `open_memmap` initializes to zeros. If
`config.fill_value` is non-zero, set it with `grid_array[:] = config.fill_value`
after creation. For the current codebase, `fill_value=0.0` everywhere,
so this is a no-op.

**Output handling:** `write_compilation_output()` receives the mmap
array. It already calls `np.save()` internally — verify whether it
re-copies the data or can accept an mmap. If it re-copies, change it
to flush-and-rename the tmp file instead (same pattern as
`assemble_grid.py:574-577`).

**Risk:** Low. The placement loops are pure element-wise assignment.
The only behavioral difference is I/O pattern (random writes to disk
vs RAM). On NVMe, this adds ~10-30% wall-clock time due to page
faults. On HDD, it would be unacceptable — verify the server uses
NVMe (it does: Hetzner CPX series uses NVMe SSDs).

**Verification:**
- All existing compilation tests pass (they verify cell values, not memory usage)
- `uv run pytest tests/test_compilation.py tests/test_acled_compilation.py -v`
- Manual check: run V-Dem compile on server, verify peak RSS < 1 GB via `/usr/bin/time -v`
- Output grid is bit-identical to the in-memory version

**Estimated effort:** 2-3 hours (code change is ~20 lines; most time is testing)

---

### Step 2: Pre-Flight Resource Checks

**What:** Before allocating the grid (whether in RAM or as mmap),
calculate the required resources and fail with a clear diagnostic
message if insufficient.

**Where:**
- `src/datafactory_compilation/pregridded_compilation.py` — before line 171
- `src/datafactory_compilation/grid_compilation.py` — before line 224

**Two checks:**

**A. Disk space check (for mmap output):**
```python
expected_bytes = n_steps * nrow * ncol * n_features * dtype.itemsize
free_bytes = shutil.disk_usage(config.output_dir).free
if free_bytes < expected_bytes * 1.2:
    raise RuntimeError(
        f"Insufficient disk space for grid: "
        f"need {expected_bytes * 1.2 / 1e9:.1f} GB, "
        f"have {free_bytes / 1e9:.1f} GB free"
    )
```

This is copied directly from `assemble_grid.py:477-488` which
already does this check.

**B. Memory advisory (informational warning):**
```python
import warnings
avail = shutil.disk_usage("/").free  # conservative proxy
# or: psutil.virtual_memory().available if psutil is available
if expected_bytes > avail * 0.8:
    warnings.warn(
        f"Grid ({expected_bytes / 1e9:.1f} GB) exceeds 80% of "
        f"available memory. Using memory-mapped I/O.",
        stacklevel=2,
    )
```

After Step 1, the memory warning is informational only (mmap makes
it safe). But it provides visibility into resource usage and helps
operators anticipate when the server is under pressure.

**Risk:** Negligible. These are read-only checks that run before any
allocation.

**Verification:**
- Unit test: mock `shutil.disk_usage` to return low values, assert RuntimeError
- Unit test: mock low memory, assert warning is emitted
- Existing tests unaffected (test fixtures are tiny grids)

**Estimated effort:** 1-2 hours

---

### Step 3: Fix Unnecessary Materialization in Zarr Export

**What:** Remove the `np.asarray()` wrapper in `export_zarr.py:120`
that forces each feature slice from mmap into a full RAM copy.

**Where:** `scripts/export_zarr.py:120`

**Current code:**
```python
for i, name in enumerate(feature_names):
    feature_data = np.asarray(grid[:, :, :, i])  # ← forces copy into RAM
```

**Fixed code:**
```python
for i, name in enumerate(feature_names):
    feature_data = grid[:, :, :, i]  # ← keeps mmap; xarray reads lazily
```

**Why this matters:** With 75 features in float32, the loop cycles
through 75 × 0.44 GB = 33 GB of explicit RAM copies, one at a time.
Each feature slice is ~440 MB. Without `np.asarray()`, xarray
receives a numpy mmap view and writes zarr chunks directly from the
mmap without a full-feature copy.

**Caveat:** Verify that `xr.Dataset.to_zarr()` handles mmap slices
correctly. It should — xarray's zarr writer iterates over chunks, and
numpy mmap slicing returns a view. But test this explicitly with the
round-trip integrity check that already exists in the script
(lines 226-239).

**Risk:** Low. The round-trip integrity check catches any silent
data loss. If xarray can't handle mmap views, the fix is to read
one chunk at a time instead of one feature at a time — still bounded
memory, just a different slicing strategy.

**Verification:**
- Run `export_zarr.py` on the assembled grid
- Round-trip check passes (feature sums match)
- Monitor peak RSS during export: should drop from ~440 MB spikes to ~50 MB steady

**Estimated effort:** 1 hour (code change is 1 line; testing is the work)

---

### Step 4: Write-Up and Architecture Decision

**What:** After Steps 1-3 are implemented and verified, write an ADR
documenting the bounded-memory compilation decision and the long-term
direction toward zarr-native compilation.

**ADR content:**
- **Context:** Grid size grows linearly with features × time. In-memory
  allocation hit the server's RAM ceiling at 75 features. Swap is a
  temporary mitigation, not a solution.
- **Decision:** Compilation uses memory-mapped output arrays via
  `np.lib.format.open_memmap()`. Peak memory is bounded by OS page
  cache size (~100-200 MB), independent of grid dimensions.
- **Consequences:** Wall-clock time increases ~10-30% due to page
  faults on random writes. NVMe is required (no HDD support).
  Output format unchanged.
- **Future direction:** When the 10th source is added or total features
  exceed 150, consider zarr-native compilation — writing directly to
  zarr chunks instead of building npy intermediates. This would
  eliminate the assembly step (zarr-merge replaces array concatenation)
  and enable time-partitioned storage.

**Location:** `docs/adr/adr-0XX-bounded-memory-compilation.md`

**Risk register updates:**
- Register the current OOM risk as a concern (if not already tracked)
- Resolve it once Steps 1-3 are merged

**Estimated effort:** 1-2 hours

---

## Long-Term Architecture (Beyond This Plan)

These are not part of the current work. They are documented here so
the reasoning is preserved for future planning.

### Zarr-Native Compilation (v2.0 candidate)

Instead of compiling to npy and then exporting to zarr, compile
directly to zarr chunks. Each source writes its feature variables
independently. Assembly becomes a zarr-merge operation (concatenate
along the feature dimension in metadata, not in a monolithic file).

**Enables:**
- No monolithic npy files anywhere in the pipeline
- Per-feature or per-chunk writes — memory bounded by chunk size
- Incremental updates (rewrite only changed features/time ranges)
- Export step becomes redundant — compile output IS the zarr store

**Requires:**
- Rethinking provenance (per-chunk digests instead of per-file)
- Rethinking the query layer (zarr as canonical format, npy as legacy)
- Rethinking assembly (metadata-level concatenation, not array copy)
- ADR and CIC updates across 4+ packages

**When:** When adding the 10th data source or when total features
exceed 150, whichever comes first.

### Time-Partitioned Storage (v2.0+ candidate)

Partition the grid along the time dimension (by decade or year).
Compile only the partition that changed. Assembly concatenates
partitions along time via zarr groups.

**Enables:**
- Bounded growth — adding 12 months/year only touches one partition
- Faster re-runs — recompile only the changed time range
- Parallel compilation — each partition can run independently

**When:** When T exceeds 600 months (~2030) or when a real-time
update model requires sub-monthly compilation latency.

---

## Execution Plan

```
Step 1: Memory-mapped compilation       [~3 hours]
Step 2: Pre-flight resource checks      [~2 hours]
Step 3: Fix zarr export materialization  [~1 hour]
Step 4: ADR + register updates          [~2 hours]
                                         --------
Total estimated:                         ~8 hours
```

**Sequencing:** Steps 1-3 are independent code changes and could be
done in parallel, but Step 1 is the highest-value change and should
be verified first. Step 4 depends on 1-3 being complete.

**Branch:** `feature/bounded-memory-compilation` from `development`

**Verification after all steps:**
1. `uv run ruff check .` — clean
2. `uv run pytest -q` — all pass
3. Run V-Dem compile on server: peak RSS < 1 GB
4. Run full pipeline on server: all sources compile, assemble, export
5. Remote zarr verification: feature sums match expected values
6. Server can run on CPX32 (8 GB) without swap

---

## Success Criteria

- [ ] V-Dem (22 features) compiles in < 1 GB peak RSS
- [ ] WDI-scale source (50 features) would compile in < 1 GB peak RSS
- [ ] No change to output files (bit-identical grid.npy)
- [ ] No change to downstream consumers
- [ ] Pre-flight check catches insufficient disk space before allocation
- [ ] Zarr export peak RSS < 500 MB for 75-feature grid
- [ ] All existing tests pass
- [ ] ADR documents decision and future direction
