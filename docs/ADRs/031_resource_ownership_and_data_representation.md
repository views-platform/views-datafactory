# ADR-031: Resource Ownership and Data Representation

**Status:** Accepted
**Date:** 2026-05-20
**Deciders:** Simon Polichinel von der Maase, Claude Code
**Applies:** ADR-003 (Authority of Declarations), ADR-009 (Boundary Contracts), ADR-011 (Fail Loud), ADR-030 (Raster Tooling)

---

## Context

The GHS-POP pipeline (v1.2.15–v1.2.17) OOM-killed three times on an 8 GB server. Each incident had a different proximate cause, but the root cause was the same: **memory behavior was an accidental side effect of implementation, not an explicit design concern.**

Three independent code paths exhibited the same antipattern:

1. **Viewpoint builder** accumulated ~60M Python objects in three lists (~6.5 GB) to build a Parquet file. The domain operation was "interpolate and emit rows." The memory cost was incidental — caused by the choice of `list.append()` over numpy array construction.

2. **Pre-gridded compilation** called `.to_pylist()` on Arrow columns, inflating ~60M rows from ~0.5 GB (columnar) to ~6 GB (Python objects). The domain operation was "place values into a grid." The memory cost was incidental — caused by converting columnar data to row-oriented Python objects.

3. **Spatial aggregation** called `data.copy()` on a 6.88 GiB array to mask nodata values. The domain operation was "replace nodata with zero, then sum." The memory cost was incidental — caused by holding both the original and the cleaned copy simultaneously.

In each case, the code was correct in output but accidentally expensive in representation. The fixes were trivial (`del` after use, `.to_numpy()` instead of `.to_pylist()`, strip-based processing), but nothing in the codebase's existing governance made these failures predictable, detectable, or preventable.

The deeper issue: **data transformation and resource management are complected.** The pipeline is written as sequential imperative logic where data accumulates as the transformation proceeds, but there is no separation between what is being computed and how memory is controlled. Python is not Rust — it cannot enforce ownership at the type level — but Rust's core insight applies in any language: **every allocation should have a clear owner, a known lifetime, and an explicit point of release.**

This ADR establishes principles for resource-aware data processing. It is deliberately narrow — scoped to what three OOM incidents taught us, not to hypothetical future problems. Broader concerns (memory budgets, circuit breakers, streaming frameworks) are deferred until more sources reveal whether the GHS-POP patterns generalize. This follows the same WET-before-DRY discipline applied to code abstractions (ADR-030): write the principle after the third incident, not the first.

---

## Decision

This repository adopts the following principles for data representation and resource management:

### Principle 1: Columnar In, Columnar Through, Columnar Out

> Data that arrives in columnar form (Arrow, numpy, Parquet) must remain in columnar form throughout processing. Conversion to Python object collections (lists of dicts, lists of scalars via `.to_pylist()`, `.to_pydict()`) is forbidden for datasets that may exceed 1M rows.

**Why:** A Python `int` is 28 bytes. A numpy `int32` is 4 bytes. A list of 60M Python ints costs 1.68 GB; the same data as a numpy array costs 0.24 GB — a 7x amplification. This is not an optimization concern. It is the difference between fitting in memory and OOM-killing.

**In practice:**
- Use `.to_numpy()` instead of `.to_pylist()` when extracting Arrow columns for iteration.
- Build output as numpy arrays, then wrap with `pa.table()` (zero-copy) instead of accumulating Python lists and converting.
- When row-by-row iteration over Arrow data is unavoidable, iterate over chunks or use `to_batches()`.

### Principle 2: Release What You No Longer Need

> When a derived representation supersedes its source, the source must be explicitly released. `del` is not cleanup — it is a design statement about ownership transfer.

**Why:** Python's garbage collector handles circular references, but for large allocations (multi-GB numpy arrays, Arrow tables), deterministic release matters. CPython's reference counting frees objects immediately when the last reference is removed. For arrays allocated via `mmap` (glibc's default for allocations above ~128 KB), `del` triggers `munmap`, returning memory to the OS within the same statement. Relying on scope exit or GC cycles for multi-GB objects is not acceptable on memory-constrained servers.

**In practice:**
- After `pa.table(...)` from lists: `del` the lists.
- After `.to_numpy()` from an Arrow table: `del` the table.
- After aggregation from a raw array: `del` the raw array.
- Each `del` should be readable as: "ownership of the data has moved to the new representation."

This is Rust's move semantics expressed as a Python convention. The compiler cannot enforce it, but the principle is the same: after a value is consumed, the previous binding must not remain live.

### Principle 3: Never Hold Source and Copy Simultaneously at Scale

> When transforming a large array (>100 MB), avoid patterns that require both the input and a full-size output to coexist. Prefer in-place mutation, strip/chunk processing, or sequential release.

**Why:** `clean = data.copy()` on a 6.88 GiB array doubles peak memory to 13.76 GiB. `.astype(np.float32, copy=False)` on a float64 array may or may not copy depending on the input dtype — the `copy=False` is a hint, not a guarantee. These patterns create transient memory peaks that are invisible in profiling (the copy is freed shortly after) but fatal on constrained hardware.

**In practice:**
- Prefer in-place masking: `data[data == nodata] = 0.0` instead of `clean = data.copy(); clean[clean == nodata] = 0.0`.
- When in-place mutation is not safe (immutable input contract), process in strips/chunks that fit in a fraction of available memory.
- When dtype conversion is needed, do it per-chunk rather than on the full array.

### What This ADR Does Not Cover

These are deferred until we have more operational experience:

- **Memory budgets or ceilings.** We do not yet know what the right budget is per pipeline step. The 8 GB server constraint is an operational fact, not an architectural principle.
- **Streaming or chunked I/O frameworks.** The pipeline is batch-oriented (runs monthly on static data). Streaming adds complexity that is not yet justified.
- **Automatic memory monitoring or circuit breakers.** These are operational concerns (ADR-018 territory) that require more deployment experience.
- **Server sizing decisions.** Whether to run on 8, 16, or 64 GB is a capacity planning question, not an architecture question.

---

## Rationale

### Why now, not earlier?

Three independent OOM incidents in one pipeline is the WET-before-DRY threshold. The first incident (v1.2.15) could have been a one-off mistake. The second (v1.2.16) suggested a pattern. The third (falsification of v1.2.17 — list accumulation and `.to_pylist()` discovered before deployment) confirmed it: this is a class of error, not an instance.

### Why these principles and not others?

The three principles correspond directly to the three antipatterns observed:

| Incident | Antipattern | Principle |
|----------|------------|-----------|
| `.to_pylist()` in compilation | Columnar → Python objects | Columnar In, Columnar Through |
| Lists never deleted in viewpoint | Source outlives its usefulness | Release What You No Longer Need |
| `data.copy()` in aggregation | Source + copy coexist | Never Hold Source and Copy |

A broader ADR covering memory budgets, streaming, or profiling would be speculative. These three principles are grounded in observed failures.

### What can Python learn from Rust without pretending to be Rust?

Rust enforces three properties at compile time that are relevant here:

1. **Ownership:** Every value has exactly one owner. When the owner goes out of scope, the value is dropped. Python cannot enforce this, but we can adopt the convention: every large allocation should have a clear owner, and ownership transfer (via `del` or reassignment) should be explicit and deliberate.

2. **Move semantics:** After a value is moved, the previous binding is invalid. Python has no move — `del` is the closest equivalent. The discipline is: after consuming a large value to produce a derived value, `del` the original. This is a convention, not a compiler check, but it makes resource flow visible in code review.

3. **Borrowing:** Rust distinguishes between owning data and borrowing a reference to it. In Python, numpy views (`data[0:60, :]`) are borrows — they reference the original without copying. `.astype()` and `.copy()` are ownership transfers — they allocate new memory. The principle: prefer views (borrows) over copies (ownership transfers) when the original will outlive the derived use.

What Python *cannot* do: enforce these at the type level, prevent use-after-del, or guarantee that a reference doesn't leak. The ADR establishes conventions that code review can enforce, not compiler guarantees. This is analogous to how ADR-003 (declarations over inference) establishes a semantic discipline that Python's type system cannot enforce — the value is in the shared convention, not the enforcement mechanism.

---

## Consequences

### Positive

- Memory behavior becomes a reviewable property of code, not an accidental side effect.
- New pipeline code has clear guidance on representation choices — the "obvious" approach (Python lists, `.to_pylist()`) is explicitly flagged as dangerous at scale.
- Code review can catch resource ownership violations before deployment, rather than discovering them via OOM kills on the server.
- The principles are language-appropriate — they ask for conventions and discipline, not for Python to be something it isn't.

### Negative

- Developers must think about data size when choosing representations. For small datasets (<1M rows), Python lists are fine and the principles are irrelevant. The threshold is a judgment call, not an enforceable rule.
- `del` statements add visual noise to functions. The trade-off: one line of `del` versus an OOM kill at 3 AM.
- Strip/chunk processing is more complex than whole-array operations. This is accepted — the strip-based aggregation in `ghspop_v1.py` is 70 lines where the whole-array version was 10. The 70-line version works on 8 GB; the 10-line version doesn't.

---

## Implementation Notes

### Existing code compliance

The v1.2.18 fixes bring the GHS-POP pipeline into compliance:

| Principle | Fix | File |
|-----------|-----|------|
| Columnar Through | `.to_pylist()` → `.to_numpy()` | `pregridded_compilation.py` |
| Release | `del pgid_rows, month_id_rows, pop_count_rows` | `ghspop_v1.py` |
| No Source+Copy | Strip-based aggregation, `del raw` | `ghspop_v1.py` |

### Known non-compliant code (not in scope for this ADR)

- `grid_compilation.py` uses `table.to_pydict()` (C-144). Currently safe because UCDP/ACLED event counts are ~2.3M, but will violate Principle 1 as the consolidated store grows. Fix when the trigger fires.
- `ucdp_v1.py` loads full consolidated store via `pq.read_table()` (C-145). Currently safe on the server. Fix when store exceeds ~5M rows.

### Falsification tests

`tests/test_falsification_ghspop_memory.py` encodes the principles as executable assertions (AST checks for `del` targets, `.to_pylist()` absence, `maxworkers` usage). Future pipelines should add similar structural tests when processing datasets >1M rows.

### Review checklist (for code review, not automated enforcement)

When reviewing code that processes >1M rows:

- [ ] Does the code convert Arrow/numpy data to Python objects? If so, is there a columnar alternative?
- [ ] Are large intermediate representations released after the derived representation is created?
- [ ] Does any transformation create a full-size copy of a large array? If so, can it be done in-place or in chunks?

---

## Validation & Monitoring

- **Short-term:** The falsification tests in `test_falsification_ghspop_memory.py` enforce compliance for GHS-POP.
- **Medium-term:** When the 4th data source is implemented, review its pipeline against this ADR's three principles before deployment.
- **Long-term:** The Rust migration (ADR-030) will make Principles 2 and 3 compiler-enforced for raster I/O. Principle 1 (columnar representation) remains a Python-side concern regardless.

---

## Open Questions

1. **Should Principle 1 have a hard row-count threshold?** The current text says ">1M rows." This is a heuristic. At 100K rows, Python lists cost ~8 MB (harmless). At 10M rows, they cost ~800 MB (noticeable). At 60M rows, they cost ~6.5 GB (fatal). The threshold could be lower, but setting it too low makes the principle noisy for small utilities.

2. **Should we add a `peak_memory_mb` field to ViewpointResult / CompilationResult?** This would create a feedback loop — each run reports its peak memory, and operators can track trends. Deferred until we have a memory measurement mechanism (`tracemalloc` snapshots or `/proc/self/status` reads).

3. **Does this ADR apply to the UCDP/ACLED viewpoint builders?** In spirit, yes. In practice, their data volumes are small enough that the violations are harmless. The ADR applies when the trigger fires (C-144, C-145).

---

## References

- C-165, C-170, C-171, C-172: GHS-POP OOM incidents that motivated this ADR
- C-144, C-145: Known non-compliant code in UCDP/ACLED paths (deferred)
- ADR-003 (Authority of Declarations): Semantic discipline as convention, not enforcement
- ADR-009 (Boundary Contracts): Validation at entry — this ADR extends the same thinking to resource management
- ADR-011 (Fail Loud): OOM is the loudest possible failure — this ADR aims to prevent it
- ADR-030 (Raster Tooling): Rust long-term for predictable memory — this ADR covers the Python interim
- Kleppmann & Riccomini, *Designing Data-Intensive Applications*, 2nd ed., O'Reilly 2026:
  - Ch.3 pp.67-72: Column-oriented storage — the performance difference between row and column representations
  - Ch.10 pp.397-399: Batch processing input immutability — derived outputs replace atomically, inputs are not modified
  - Ch.12 pp.491-495: Derived data systems — materialized views are rebuildable, so intermediate representations are dispensable
- *The Rustonomicon*, "Ownership and Lifetimes": The three Rust properties (ownership, move, borrow) that inform Principles 1-3 as Python conventions
