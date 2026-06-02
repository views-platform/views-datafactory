# Sprint Plan: Bounded-Memory Compilation (C-223)

**Date:** 2026-05-29
**Status:** Draft — developing iteratively (R&D plan exists)
**Branch:** TBD (from `development`)
**Register entries:** C-223, related: C-144, C-145, C-173
**Work package:** Scaling headroom (register row 82)
**Estimated effort:** ~8 hours
**R&D plan:** `reports/rd_plan_bounded_memory_compilation.md` (full technical design)

---

## Problem Statement

The compilation pipeline allocates the entire output grid as a single
in-memory array via `np.full()` before writing to disk. Grid shape is
`[T, H, W, C]` = `(456, 360, 720, features)` in float32.

**Per-feature cost:** 456 × 360 × 720 × 4 bytes = **0.44 GB/feature**

| Source | Features | Grid size | + Overhead | Total peak |
|--------|----------|-----------|------------|------------|
| UCDP | 6 | 2.6 GB | ~0.4 GB | ~3 GB |
| ACLED | 8 | 3.5 GB | ~0.8 GB | ~4.3 GB |
| GHS-POP | 1 | 0.4 GB | ~0.1 GB | ~0.5 GB |
| GHS-BUILT-S | 1 | 0.4 GB | ~0.1 GB | ~0.5 GB |
| V-Dem | 22 | 9.7 GB | ~5.7 GB | ~15.4 GB |
| SHDI (planned) | 4 | 1.8 GB | ~0.3 GB | ~2.1 GB |
| Assembly | 75+ | 33+ GB | (mmap) | ~0.2 GB* |

*Assembly already uses `open_memmap()` — it is not part of the problem.

**Production impact:** V-Dem compile OOM-killed the server three times
during v1.2.22 deployment, requiring server rescaling (8→16 GB RAM)
and 16 GB swap. Future large sources (WDI: 20-50 features) would push
single-source compile past 20 GB.

**Root cause:** `np.full()` at `pregridded_compilation.py:171` and
`grid_compilation.py:224` allocates the full grid in RAM. The
placement loops that follow (row-by-row cell writes) would work
identically on a memory-mapped array.

**Server:** CPX42, 16 GB RAM + 16 GB swap = 32 GB total. Current
headroom is thin for V-Dem (15.4 GB peak) and insufficient for
WDI-scale sources.

---

## Existence Proof

`scripts/assemble_grid.py:491` already uses `np.lib.format.open_memmap()`
for the assembled grid (75+ features, 33+ GB). The pattern is proven,
tested, and running in production. Peak RSS for assembly is ~0.2 GB
regardless of feature count.

---

## Solution (from R&D Plan)

Replace `np.full()` with `np.lib.format.open_memmap()` in both
compilation functions. The placement loops (row-by-row cell writes)
work identically on memory-mapped arrays because numpy's `[]` operator
is the same for in-memory and mmap arrays.

### Step 1: Memory-Mapped Compilation (~4 hours)

**`pregridded_compilation.py:171`** — Replace:
```python
grid = np.full(shape, fill_value=np.nan, dtype=np.float32)
```
With:
```python
grid = np.lib.format.open_memmap(
    str(output_path), mode="w+",
    shape=shape, dtype=np.float32,
)
grid[:] = np.nan
```

**`grid_compilation.py:224`** — Same replacement.

**Key insight:** The fill step (`grid[:] = np.nan`) writes page-by-page
through the mmap — it doesn't allocate the full grid in RAM. The OS
manages page cache, evicting old pages as needed.

### Step 2: Pre-Flight Disk Space Checks (~1 hour)

Before allocating the mmap file, verify sufficient disk space:
```python
required_bytes = math.prod(shape) * np.dtype(np.float32).itemsize
free = shutil.disk_usage(output_path.parent).free
if free < required_bytes * 1.2:  # 20% headroom
    raise RuntimeError(f"Need {required_bytes/1e9:.1f} GB, "
                       f"only {free/1e9:.1f} GB free")
```

### Step 3: Zarr Export Fix (~2 hours)

**`scripts/export_zarr.py:120`** — `np.asarray()` on an mmap array
forces the full array into RAM, defeating the purpose. Replace with
chunk-by-chunk copy to zarr:

```python
# Instead of: zarr_array[:] = np.asarray(grid)
for t in range(grid.shape[0]):
    zarr_array[t] = grid[t]
```

### Step 4: ADR (~1 hour)

Document the bounded-memory decision: why mmap, what the invariant is
(< 1 GB peak RSS per compile regardless of feature count), what the
alternative was (chunked processing — rejected for simplicity).

---

## Current Code Paths

### `compile_pregridded()` — pregridded sources (V-Dem, GHS-POP, GHS-BUILT-S)

**File:** `src/datafactory_compilation/pregridded_compilation.py`
- Line 171: `np.full()` allocation
- Lines 172-220: Row-by-row placement loop (reads viewpoint Parquet,
  maps pgid → (row, col), writes values into grid cells)
- Lines 221-240: Output writing (grid.npy, pgids.npy, time_steps.npy,
  feature_names.json)

### `compile_grid()` — event sources (UCDP, ACLED)

**File:** `src/datafactory_compilation/grid_compilation.py`
- Line 224: `np.full()` allocation
- Lines 225-280: Event-to-cell placement (lat/lon → row/col, strategy
  dispatch: count/sum/max)
- Lines 281-300: Output writing

### `assemble_grid.py` — assembly (already mmap)

**File:** `scripts/assemble_grid.py`
- Line 491: `np.lib.format.open_memmap()` — the pattern we're adopting
- Lines 492-560: Channel-by-channel copy from source grids into
  assembled grid

### `export_zarr.py` — zarr export

**File:** `scripts/export_zarr.py`
- Line 120: `np.asarray()` on mmap array — the secondary fix target
- The zarr chunking is already correct; only the copy method needs
  to avoid full-array materialization

---

## Success Criteria

1. V-Dem compile (22 features, 9.7 GB grid) runs in **< 1 GB peak RSS**
2. No change to output format (grid.npy, pgids.npy, time_steps.npy,
   feature_names.json remain identical)
3. No change to downstream consumers (assembly, export, query all
   produce identical results)
4. Pre-flight check catches insufficient disk space before creating
   the mmap file

---

## Task Breakdown

### Task 1: `pregridded_compilation.py` mmap conversion
- [ ] Replace `np.full()` with `open_memmap()` at line 171
- [ ] Add pre-flight disk space check
- [ ] Test: output grid is bit-identical to pre-mmap version
- [ ] Test: peak RSS stays below 1 GB (use `/proc/self/status` VmPeak)

### Task 2: `grid_compilation.py` mmap conversion
- [ ] Replace `np.full()` with `open_memmap()` at line 224
- [ ] Add pre-flight disk space check
- [ ] Test: output grid is bit-identical
- [ ] Test: peak RSS stays below 1 GB

### Task 3: `export_zarr.py` chunk-by-chunk copy
- [ ] Replace `np.asarray(grid)` with per-timestep copy
- [ ] Test: zarr output is identical
- [ ] Test: peak RSS stays low during zarr export

### Task 4: ADR
- [ ] Write ADR documenting bounded-memory decision
- [ ] Reference assembly's existing mmap pattern as precedent
- [ ] Document the invariant: < 1 GB RSS per compile

### Task 5: Register updates
- [ ] Resolve C-223
- [ ] Update C-144 (compilation to_pydict) if affected
- [ ] Update C-145 (viewpoint full store load) if affected
- [ ] Update C-173 (server memory headroom) with new bounds
- [ ] Update header counts

---

## Alternatives Considered (from R&D plan)

| Approach | Complexity | Peak RSS | Trade-off |
|----------|------------|----------|-----------|
| **mmap (chosen)** | Low | < 1 GB | Disk I/O for random writes; OS manages page cache |
| Chunked by feature | Medium | ~0.5 GB | Requires restructuring placement loops; O(F) passes over source data |
| Chunked by time | Medium | ~0.5 GB | Better for sequential writes but requires reordering source iteration |
| Direct-to-zarr | High | ~0.5 GB | Eliminates npy intermediate but changes output format; downstream impact |
| Streaming writes | High | ~0.1 GB | Complete rewrite of compilation; row-by-row writes are very slow for npy |

**Why mmap wins:** One-line change at the allocation site. Everything
downstream (placement loops, output writing, consumer reads) works
identically because numpy's `[]` operator is transparent to
mmap vs. in-memory. The assembly step already proves the pattern.

---

## When to Execute

This sprint is **NOT a prerequisite for SHDI** (4 features = 1.8 GB,
well within server RAM). It becomes critical before:

1. **WDI integration** (20-50 features → 8.8-22 GB per compile)
2. **Any source exceeding ~30 features** on the current server
3. **Time dimension growth** (each year adds 12 T steps → +0.037 GB
   per feature per year; by 2030, V-Dem alone would need 11.6 GB)
4. **If server is downsized** back to 8 GB RAM

Current priority: lower than harvest correctness and WET extraction,
but should be done before the 7th or 8th pipeline source.

---

## Open Questions

1. Should the mmap file be written to a temp path and atomically
   renamed, or written directly to the output path? (Atomic rename
   prevents partial files on crash but requires 2× disk space briefly.)
2. Does the zarr export need chunk-by-time or chunk-by-feature
   iteration? (Current zarr chunk shape determines this.)
3. Should we add a `--memory-limit` flag to compilation scripts for
   operator control, or rely on the mmap approach entirely?
4. Do existing tests exercise the full compilation path, or do we need
   integration tests that compile a small grid and verify output?
5. Should C-145 (viewpoint full store load) be addressed in this sprint
   too? It's a separate memory bottleneck in the viewpoint layer.

---

## Dependencies

- **Blocks:** WDI integration (would OOM without mmap)
- **Blocked by:** Nothing
- **Related:** C-144 (compilation to_pydict), C-145 (viewpoint full
  store load), C-173 (server memory headroom), D-24 (hardware vs
  software — resolved: both)
- **R&D plan:** `reports/rd_plan_bounded_memory_compilation.md` (full
  technical design, 324 lines)
