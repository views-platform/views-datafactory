# Data Source Integration Guide

How to add a new data source to the VIEWS data factory. Distilled from
four source integrations (UCDP, ACLED, GHS-POP, GHS-BUILT-S) and two
pre-deployment post-mortems.

Read this document before writing any code for a new data source.

---

## Before you start

1. Read the most recent pre-deployment post-mortem in `reports/`.
   The "what went wrong" section contains lessons that are easy to
   repeat. The checklist at the bottom is the compressed version of
   this guide.

2. Decide which layers the source traverses. Not all sources go
   through all layers (ADR-012):

   | Path | Example | Layers |
   |------|---------|--------|
   | Event data (API) | UCDP, ACLED | Harvest → Consolidation → Viewpoint → Compilation → Assembly |
   | Raster data (GeoTIFF) | GHS-POP, GHS-BUILT-S | Harvest → Viewpoint → Compilation → Assembly |
   | Static data | PRIO-GRID, GAUL | Harvest → Assembly (loaded directly) |

3. Estimate implementation scope honestly. Production code for a
   same-provider raster source is ~800 lines. Everything around it
   (tests, verification, docs, governance) will be 3-6x that.

---

## Phase 0: Investigation

**Goal:** Eliminate wrong assumptions before writing code.

- Download one file/epoch/snapshot from the provider manually.
- Check: CRS, resolution, format, dtype, nodata convention, file size,
  access method, authentication, rate limits.
- Estimate peak RSS: `n_pixels × sizeof(dtype) × 2` (raw + working).
  If it exceeds server RAM (8 GB), plan the mitigation now.
- Document findings in the ADR (Phase 1).

**Lesson (GHS-POP):** 30 minutes of provider docs eliminated 2 weeks
of wrong assumptions about reprojection and GDAL dependency.

---

## Phase 1: ADR and source registry

**Goal:** Scope the work and declare the source's existence.

- Write the ADR. Focus on: what's in scope, what's out, aggregation
  strategy, which layers are traversed, what differs from existing
  sources. Keep it short — ADR-034 (GHS-BUILT-S) is 137 lines.
- Add `SourceEntry` to `PIPELINE_SOURCES` in
  `src/datafactory_provenance/source_registry.py`.
  The registry entry is the birth certificate — health checks,
  pre-flight, assembly, and remote verification all read from it.

**Do this in the first commit.** Not as a later integration step.

---

## Phase 2: Harvester

**Goal:** Download and cache raw data with full provenance.

- Implement in `src/datafactory_harvester/sources/<source>.py`.
- Frozen dataclass config with `__post_init__` validation.
- `logger.error()` before every `raise` (ADR-008).
- Cache check: file exists + ledger has digest → skip.
- Failure recording: `append_ledger_entry` with `outcome: "failed"`
  in every `except` block (ADR-032).
- Register via `register_source()` at module bottom.

**Reuse:** `request_with_retry` for HTTP, `compute_content_digest`
for provenance, `last_digest_for_version` for cache checks.

---

## Phase 3: Viewpoint (if applicable)

**Goal:** Opinionated, rebuildable derived view.

- Implement in `src/datafactory_viewpoint/builders/<source>_v1.py`.
- For raster sources: spatial aggregation + temporal interpolation.
  Check if `_aggregate_with_alignment()` is reusable. It handles
  JRC GHSL rasters (21384×43201/43202 → 360×720 PRIO-GRID).
- Output: Parquet with `(pgid, month_id, <value_column>)` schema.
- `del` large objects after Arrow table creation (memory discipline).
- `maxworkers=1` on tifffile reads (reduces decompression buffering).
- Register via `register_builder()`.

**Reuse:** `compile_pregridded()` works with any source that produces
the `(pgid, month_id, value)` Parquet schema. Zero changes needed
for GHS-BUILT-S.

---

## Phase 4: Compilation and assembly

**Goal:** Place viewpoint output into the [T, H, W, F] grid.

- Pipeline script with explicit `--end-year` argument. Do not rely
  on `TemporalConfig` defaults.
- Add `--<source>-grid` argument to `scripts/assemble_grid.py`.
- Temporal alignment: find the source's start date in the UCDP
  timeline, copy the source grid into the correct time slice,
  zero-fill outside the source's coverage range.

---

## Phase 5: Operational integration — SAME COMMIT as Phase 2-4

This is the phase that gets missed. Three times running (GHS-POP
CIC drift, GHS-POP deployment guide, GHS-BUILT-S pipeline+guide),
operational integration trailed code implementation. C-192 now
enforces items 1-2 via automated tests, but the discipline is:
**do this in the same commit as the code, not as a follow-up.**

1. **`scripts/refresh_pipeline.sh`** — add harvest step, compile
   step, assembly flag. Renumber all step labels.
2. **`docs/guides/hetzner_deployment_guide.md`** — add a paragraph
   with download size, timing, credentials, disk requirements.
   Compute these numbers from actual data, not estimates.
3. **CIC for config dataclass(es)** — write alongside the config,
   not after. The CIC forces you to articulate invariants during
   design, not as a compliance exercise 20 hours later.
4. **Catalog card** in `docs/sources/<source>.md` — provider, DOI,
   license, features produced, pipeline path.
5. **Run `test_operational_integration.py`** — confirms items 1-2
   automatically. If it fails, you missed something.

---

## Phase 6: Testing

**Goal:** Proportional coverage calibrated to risk.

### Unit and integration tests

- Config validation (beige): every `__post_init__` branch.
- Happy path (green): full flow with synthetic data.
- Failure modes (red): bad input, missing files, corrupt data.
- Follow `tests/test_<source>_harvester.py`, `test_<source>_viewpoint.py`,
  `test_<source>_compilation.py` naming convention.

### Falsification — risk-calibrated

Do not apply the same intensity to every source.

- **Same provider, same format, proven pipeline:** 1 round, focused
  on operational integration and data-specific correctness. ~3-5
  probes. GHS-BUILT-S did not need 3 rounds and 12 files.
- **New provider, new format, or memory-constrained:** 3 rounds with
  full category coverage. ~15-25 probes. GHS-POP earned this.

### Verification script (raster sources)

- Visual audit with plots for spatial distribution and temporal trends.
- Reference values computed from actual raw data, never guessed.
  C-190 (GHS-BUILT-S) was caused by fabricating reference numbers.

---

## Phase 7: Verification

- `uv run ruff check .`
- `uv run pytest`
- `uv run mypy src/`
- `test_operational_integration.py` passes (enforcement, not advice)

---

## Common mistakes

| Mistake | Source | Consequence |
|---------|--------|-------------|
| Checklist not read | GHS-BUILT-S | 3 items missed, caught late by falsification |
| Reference values guessed | GHS-BUILT-S (C-190) | Off by 6-7x, false sense of validation |
| Numbers copied from another source | GHS-BUILT-S (C-193) | ~5 GB claimed, actual ~2 GB |
| `logger.error` before `raise` omitted | GHS-BUILT-S (C-194) | ADR-008 violation in both GHS-POP and GHS-BUILT-S |
| Pipeline script not updated | GHS-BUILT-S (C-191) | Feature dead on arrival in production |
| CIC written after the code | GHS-BUILT-S, GHS-POP | Compliance exercise, not design tool |
| OOM not estimated | GHS-POP (C-165) | 22 GB peak on 8 GB server |
| Source registry added late | GHS-POP (C-166) | verify_remote.py blind to new source |
| Temporal range default used | GHS-POP, GHS-BUILT-S (C-168) | 24-month mismatch with UCDP |

---

## Post-mortems

After each source integration, write a pre-deployment post-mortem
in `reports/`. The post-mortem documents what went right, what went
wrong, and updates this guide's lessons. Existing post-mortems:

- [GHS-POP (v1.2.15)](../../reports/pre_deploy_post_mortem.md)
- [GHS-BUILT-S (v1.2.20)](../../reports/pre_deploy_post_mortem_ghsbuilts.md)
