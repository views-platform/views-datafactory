# ADR-037: Bounded-Memory Compilation via Memory-Mapped Arrays

## Status

Accepted

## Date

2026-05-31

## Context

The compilation pipeline allocates the entire output grid as a single in-memory NumPy array via `np.full()`. Grid shape is `[T, H, W, C]` where T=552 months, H=360, W=720, and C=number of features. At 4 bytes per float32 element, this is 0.44 GB per feature.

Current memory requirements per source:

| Source | Features | RAM (np.full) |
|--------|----------|---------------|
| V-Dem | 22 | 9.7 GB |
| ACLED | 8 | 3.5 GB |
| UCDP | 6 | 2.6 GB |
| GHS-POP | 1 | 0.4 GB |
| GHS-BUILT-S | 1 | 0.4 GB |

Adding WDI (20-50 features) or SHDI (4 features) would push single-source compilation past the 16 GB available on the production server (Hetzner CPX32). Memory grows linearly with features and with time (12 new months per year). This is not sustainable.

## Decision

Replace `np.full()` with `np.lib.format.open_memmap()` in both compilation functions (`compile_grid` and `compile_pregridded`). The grid is written directly to a temporary `.npy` file on disk. The OS virtual memory system pages data in and out as needed, keeping peak RSS bounded to the active working set (~100-200 MB) regardless of total grid size.

This is the same pattern already used successfully in `assemble_grid.py` (line 491) for the 79-feature assembled grid.

### Pre-flight disk space check

Both functions check available disk space before allocating the memmap file, raising `RuntimeError` if free space is less than 1.2x the required bytes. This prevents silent failure from a full disk producing a truncated or corrupt output file.

### Zarr export

`export_zarr.py` previously used `np.asarray(grid[:, :, :, i])` to extract per-feature slices, which materialized the full slice into RAM. Changed to use the memmap slice directly (`grid[:, :, :, i]`), since the grid is already loaded with `mmap_mode="r"`.

## Alternatives Considered

1. **Zarr-native compilation** (write directly to zarr chunks instead of npy). Higher complexity, requires rearchitecting the output format. Deferred to v2.0+ if npy+memmap proves insufficient.

2. **Chunked processing by feature** (compile one feature at a time). Would require restructuring the compilation loop and writing partial arrays. More invasive than memmap for the same benefit.

3. **Chunked processing by time** (compile one month at a time). Same tradeoff as feature chunking — more complex loop structure for bounded memory that memmap provides for free.

## Consequences

- Peak RSS for any single-source compilation drops from grid-size to ~100-200 MB regardless of feature count.
- Compilation requires temporary disk space equal to the output grid size (typically 0.4-10 GB per source). Pre-flight check prevents silent failure.
- Output is bit-identical: `np.save()` on a memmap array produces the same bytes as on an in-memory array.
- Temporary memmap files are cleaned up in a `finally` block, even on compilation failure.
- The assembly step (`assemble_grid.py`) already used this pattern; compilation now follows the same convention.

## References

- C-223: Compilation pipeline allocates full grid in RAM
- ADR-024: Grid invariants ([T, H, W, C] dimension order)
- `main()` in `scripts/assemble_grid.py`: precedent for `open_memmap()` in this codebase
