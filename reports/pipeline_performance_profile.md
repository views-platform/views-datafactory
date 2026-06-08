# Pipeline Performance Profile

**Date:** 2026-06-08
**Machine:** 13th Gen Intel i9-13900H, 32 GB RAM, 2 GB swap
**Grid shape:** [T=456, H=360, W=720, F=75] = 35.5 GB (float32)
**Measured on:** development branch, commit 975b401

---

## Time Budget

All times are wall-clock, measured or estimated from observed runs on the machine above.

| Step | Script | Data flow | Output size | Time | Bottleneck |
|------|--------|-----------|-------------|------|------------|
| 0. Pre-flight | refresh_pipeline.sh | credentials + disk | — | ~5s | — |
| 1. Harvest | harvest scripts (×7) | APIs → data/raw/ | 8.5 GB | 10–30 min | Network / API rate limits |
| 2. Consolidate UCDP | consolidate_ucdp.py | raw → event store | 708 MB | 2–5 min | Parquet I/O |
| 3. Viewpoint | build_viewpoint.py | consolidated → views | 90 MB | 1–2 min | — |
| 4. Compile UCDP | compile_ucdp_grid.py | viewpoint → grid npy | 2.8 GB | 5–10 min | Grid placement |
| 5. Compile ACLED | compile_acled_grid.py | raw → grid npy (full path) | 570 MB | 3–5 min | Grid placement |
| 6. Compile GHS-POP | compile_ghspop_grid.py | viewpoint → grid npy | 452 MB | 2–3 min | Grid placement |
| 7. Compile GHS-BUILT-S | compile_ghsbuilts_grid.py | viewpoint → grid npy | 452 MB | 2–3 min | Grid placement |
| 8. Compile V-Dem | compile_vdem_grid.py | viewpoint → grid npy | 10.4 GB | 10–15 min | Memory: 22 vars × 456 months |
| **9. Assembly** | **assemble_grid.py** | **compiled → assembled** | **35.5 GB** | **46 min** | **Memory: 40% RSS, swap pressure** |
| **10a. Zarr export** | **export_zarr.py** | **grid.npy → grid.zarr** | **2.8 GB** | **57 min** | **Full grid read + per-feature write** |
| 10b. Consumer parquet | generate_consumer_data.py | grid → 3 parquet files | 199 MB | 4.5 min | Digest gate ~90s |
| 11. Health check | check_health.py | verify freshness | — | ~5s | — |
| | | | | | |
| **Total (no harvest)** | | | | **~2.5 hours** | |
| **Total (with harvest)** | | | | **~3 hours** | |

### Digest gate overhead (new, from this session)

Source-digest verification reads the full 35.5 GB grid via SHA-256 streaming (64 KB chunks). Each hash takes ~60–90 seconds depending on I/O load.

| Where | Hashes | Purpose |
|-------|--------|---------|
| Assembly (output) | 1 | Write provenance.json digest |
| Zarr export (input) | 1 | Gate: compare against provenance |
| Consumer parquet (input) | 1 | Gate: compare against provenance |
| **Total digest tax** | **3** | **~3–4 min across full pipeline** |

This is <3% of total runtime. The structural guarantee (stale exports are impossible) is worth the cost.

---

## Memory Profile

| Step | Peak RSS | Notes |
|------|----------|-------|
| Compile UCDP | ~3 GB | np.full() allocation |
| Compile ACLED | ~4.3 GB | np.full() + Parquet |
| Compile GHS-POP | ~0.5 GB | Small grid |
| Compile GHS-BUILT-S | ~0.5 GB | Small grid |
| Compile V-Dem | ~15.4 GB | 22 features × 456 months; OOM-killed server 3× during v1.2.22 |
| **Assembly** | **~13 GB (40% of 32 GB)** | **Full grid in memory; 2 GB swap fully used** |
| Zarr export | ~13 GB | Reads entire grid.npy |
| Consumer parquet | ~4 GB | load_dataset() with mmap |

Assembly and zarr export together push the machine to its limits: 40% RSS + 100% swap.

---

## Disk Profile

| Directory | Size | Notes |
|-----------|------|-------|
| data/raw/ | 8.5 GB | All harvested sources |
| data/consolidated/ | 708 MB | UCDP event store |
| data/viewpoint/ | 90 MB | Materialized views |
| data/compiled/ | 34 GB | All compiled grids (includes 20.8 GB stale V-Dem memmaps) |
| data/compiled/vdem/ | 31.2 GB | 10.4 GB grid + 20.8 GB orphaned _memmap_*.npy files |
| data/assembled/ | 41 GB | grid.npy (35.5 GB) + grid.zarr (2.8 GB) + provenance |
| data/consumer/ | 199 MB | 3 parquet files + provenance manifest |
| **Total** | **~85 GB** | **~21 GB is stale/orphaned** |

### Stale files to clean

- `data/compiled/vdem/_memmap_h38m8063.npy` (10.4 GB) — orphaned memmap
- `data/compiled/vdem/_memmap_z84uyg04.npy` (10.4 GB) — orphaned memmap

These are leftover from compilation runs that didn't clean up temporary memory-mapped files. They don't affect correctness but waste 20.8 GB of disk.

---

## The Two Dominant Costs

Assembly (46 min) and zarr export (57 min) account for **103 minutes** — 70% of the non-harvest pipeline. Both are bottlenecked on the same root cause: the 35.5 GB monolithic grid.

**Assembly** must allocate the full `[456, 360, 720, 75]` array, fill it from 5 compiled sources + 37 static/admin variables, then write it sequentially. The array exceeds available RAM, causing swap thrashing.

**Zarr export** must read that 35.5 GB grid back into memory, then iterate over 75 features writing compressed chunks. The round-trip integrity check reads the entire zarr store again.

### Iteration cost

A debug cycle that touches assembly or export costs **103 minutes minimum** before you can verify the result. This is why the ACLED dedup incident (correct grid, stale zarr) cost half a day: two full assembly + export cycles to diagnose and fix.

The source-digest gates added in this session catch the symptom immediately (fail-loud at export), but do not reduce the cycle time.

---

## Improvement Opportunities

### Reduce cycle time (fast feedback)

1. **Synthetic test path** — small fully synthetic datasets with gold-standard snapshots at each layer boundary. Run the same code paths in seconds, not hours. For development and CI.
2. **Incremental assembly** — only re-assemble features whose compiled grid changed (compare digests). Skip unchanged sources.
3. **Lazy zarr export** — write directly from compiled grids to zarr without materializing the full assembled grid.npy. Each compiled source writes its own zarr variables.

### Reduce resource pressure (memory/disk)

4. **Bounded-memory compilation** — already proposed in `reports/rd_plan_bounded_memory_compilation.md`. Use open_memmap() instead of np.full() for compilation.
5. **Clean stale memmaps** — delete orphaned `_memmap_*.npy` files after compilation (20.8 GB recoverable now).
6. **Streaming assembly** — write grid.npy via memmap instead of in-memory allocation. Already partially implemented (assembly uses memmap for reading compiled grids).

### Reduce wall-clock (parallelism)

7. **Parallel compilation** — UCDP, ACLED, GHS-POP, GHS-BUILT-S, V-Dem compilations are independent. Run them concurrently (limited by memory).
8. **Parallel digest** — compute grid.npy digest during assembly write (hash-as-you-write) instead of as a separate pass.
