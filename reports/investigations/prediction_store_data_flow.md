# Prediction Store Data Flow Investigation

**Date:** 2026-06-01
**Status:** COMPLETE
**Investigator:** Claude (with Simon)
**Purpose:** Map the current UCDP historical data flow from raw source to FAO dashboard. Identify the swap point for replacing VIEWSER with datafactory. Assess migration readiness.

---

## Executive Summary

The historical UCDP target swap (VIEWSER → datafactory) is **narrower and more achievable** than initially feared. The chain has 6 hops across 4 repos, but responsibilities are well-separated and the swap point is a single file replacement — no code changes required downstream.

**The swap:** Replace `forecasting_viewser_df.parquet` (read by the UN FAO postprocessor) with output from datafactory's `generate_consumer_data.py`. The postprocessor, Appwrite upload, and FAO API are all source-agnostic. Parity testing shows 99.98% match on fatality values.

**NaN question resolved:** Both VIEWSER and datafactory produce zero NaN in their consumer-facing output. The `fillna(0.0)` in the consumer bridge is a no-op safety net. Cell sets are identical (13,110 cells) when using the same geographic region.

**Two code changes required:** The plan originally claimed "no code changes." Multi-expert review (2026-06-01) identified two issues that make the file-only swap unworkable as described:
1. The postprocessor's `_read_historical_data()` calls `get_data(use_saved=False)`, which re-fetches from VIEWSER and overwrites any manually placed file.
2. The un_fao postprocessor's column naming convention (`lr_ged_sb`) differs from the consumer bridge output (`lr_sb_best`).

Both are small, targeted fixes. See Stage 7 for the corrected execution plan.

**Verdict:** GO — two small code changes, then the swap is a file-level operation with rollback capability.

---

## Stage 1: The Current Chain (End-to-End Trace)

**Status:** [x] complete
**Question:** What exactly happens today when historical UCDP sb/ns/os reaches the FAO dashboard?

### Findings

The chain has **6 hops** across **4 repos**:

```
HOP 1: UCDP API → views-datafactory
       harvest → consolidate → viewpoint → compile → assemble
       Output: data/assembled/grid.npy [T=456, H=360, W=720, C=75], float32

HOP 2: views-datafactory consumer bridge (generate_consumer_data.py)
       grid_to_dataframe() → column rename → NaN→0 → partition split
       Output: {partition}_viewser_df.parquet
         Index:   MultiIndex(month_id, priogrid_gid)
         Columns: lr_sb_best, lr_ns_best, lr_os_best, c_id, col, row
         Rename:  ged_sb_best→lr_sb_best, ged_ns_best→lr_ns_best,
                  ged_os_best→lr_os_best, gaul0_code→c_id

HOP 3: views-pipeline-core (ViewsDataLoader)
       _detect_data_source() inspects config_queryset.py return type
         Queryset object → VIEWSER path
         Dict with "source":"views-datafactory" → DATAFACTORY path
       Output: pd.DataFrame, MultiIndex(month_id, priogrid_gid), float64

HOP 4: views-postprocessing (UNFAOPostProcessorManager)
       Reads forecasting_viewser_df.parquet from model/data/raw/
       enrich_dataframe_with_pg_info(only_metadata=True)
       Adds 9 geospatial columns from PRIO-GRID/GAUL shapefiles:
         pg_xcoord, pg_ycoord, country_iso_a3,
         admin1_gaul0_code/name, admin1_gaul1_code/name,
         admin2_gaul2_code/name
       Validates all 9 metadata columns present
       Output: historical_dataset_{timestamp}.parquet → Appwrite

HOP 5: Appwrite (cloud storage)
       Parquet file in APPWRITE_UNFAO_BUCKET_ID
       Metadata: {category:"historical", loa:"pgm", targets:[...]}
       Versioned by $createdAt timestamp

HOP 6: views-faoapi (FastAPI)
       PredictionStoreManager.download_latest_file(
         filters={"category":"historical","loa":"pgm"})
       → FAO_PGMDataset (validates 9 metadata columns)
       → GET /data/historical/latest
       3-tier cache: in-memory TTL → disk → Appwrite download
```

### Key Discovery

The geospatial enrichment (Hop 4) joins on `priogrid_id` using PRIO-GRID shapefiles and GAUL boundaries. It does NOT come from the data source. Everything downstream of the swap point is **source-agnostic**.

### SOLID Assessment

The 6-hop chain is well-separated by responsibility:

| Hop | Responsibility | SRP Violation? |
|-----|---------------|----------------|
| 1 | Data acquisition and grid compilation | No — clear layer boundary |
| 2 | Format conversion (grid → consumer DataFrame) | No — adapter pattern |
| 3 | Data loading with strategy dispatch | No — strategy pattern (DIP) |
| 4 | Domain enrichment (geospatial metadata) | No — single transform concern |
| 5 | Persistence (cloud storage) | No — storage concern only |
| 6 | Serving (HTTP API) | No — presentation concern only |

The number of hops is justified. Each could change independently (OCP). The Appwrite layer could be swapped without touching enrichment (DIP). The chain respects ADP (no cycles) and SDP (stability increases downstream).

---

## Stage 2: The Swap Point

**Status:** [x] complete
**Question:** Where exactly would the datafactory replace VIEWSER in this chain?

### Findings

**Two swap strategies exist, at different scopes:**

#### Narrow Strategy (Historical Targets Only) — Achievable Now

The postprocessor reads from a path-manager-derived location:
```
<postprocessor_dir>/data/raw/forecasting_viewser_df.parquet
```

**Two obstacles to a pure file-replacement swap (identified by multi-expert review 2026-06-01):**

1. **`use_saved=False` overwrites:** The postprocessor's `_read_historical_data()` (`unfao.py:53`) calls `self._data_loader.get_data(use_saved=False)`, which re-fetches from VIEWSER and saves to disk BEFORE reading. Manually placing a file would be overwritten.

2. **Hardcoded filename:** `_read_historical_data()` (`unfao.py:62`) reads `f"{run_type}_viewser_df{format}"` — hardcoded to `viewser_df`. But `get_data()` saves with a dynamic cache label (`dataloaders.py:1488-1491`). Changing the postprocessor's config_queryset to return a datafactory dict would cause `get_data()` to save as `forecasting_datafactory_df.parquet`, while the read still looks for `forecasting_viewser_df.parquet`.

**Cleanest fix:** Change the un_fao postprocessor's `config_queryset.py` to return a datafactory dict descriptor (matching the pattern in `bright_starship`), AND fix `unfao.py:62` to use `self._data_loader.cached_data_path` instead of the hardcoded filename. Two small changes in views-models/views-postprocessing.

#### Broad Strategy (All Model Training) — Longer Term

Each model's `config_queryset.py` specifies its data source:
- Queryset object with `.publish()` → VIEWSER path
- Dict with `"source": "views-datafactory"` → DATAFACTORY path

The `ViewsDataLoader._detect_data_source()` dispatches at runtime. Switching individual models is a config change, not a code change. But the **transform gap** blocks this: VIEWSER applies log/lags/spatial transforms via `views_transformation_library`; the datafactory path does rename only.

### Key Finding

The narrow strategy is sufficient for the FAO historical target migration. The broad strategy is a separate concern (model training data source) that doesn't need to be solved first.

---

## Stage 3: Schema Parity Check

**Status:** [x] complete
**Question:** Does datafactory produce identical historical targets compared to VIEWSER?

### Findings

**Parity: 99.98% match** (documented in `reports/consumer_parity_investigation.md`)

| Metric | Value |
|--------|-------|
| Total cells compared | ~5.7M |
| Initial mismatch | 0.033% (1,876 cells) |
| After source-aware distribution fix | 0.014-0.023% per feature |
| Root cause of remaining mismatch | VIEWSER uses older GED annual version for 2010-2012; datafactory has newer .9 data for 2025+ |

**Column name mapping — CORRECTION (multi-expert review 2026-06-01):**

The original investigation checked `purple_alien`'s config_queryset (which produces `lr_sb_best`) and concluded the postprocessor expects the same. It does not. The `un_fao` postprocessor has its **own** config_queryset producing different column names:

| Datafactory column | Consumer bridge output | un_fao postprocessor produces | un_fao targets config |
|-------------------|----------------------|------------------------------|----------------------|
| ged_sb_best | lr_sb_best | **lr_ged_sb** | **lr_ged_sb** |
| ged_ns_best | lr_ns_best | **lr_ged_ns** | **lr_ged_ns** |
| ged_os_best | lr_os_best | **lr_ged_os** | **lr_ged_os** |
| gaul0_code | c_id | (not in un_fao queryset) | — |

The un_fao postprocessor's config_queryset (`postprocessors/un_fao/configs/config_queryset.py`) defines:
```python
Column("lr_ged_sb", from_column="ged_sb_best_sum_nokgi")
Column("lr_ged_ns", from_column="ged_ns_best_sum_nokgi")
Column("lr_ged_os", from_column="ged_os_best_sum_nokgi")
```

And `config_meta.py` specifies `targets: ["lr_ged_sb", "lr_ged_ns", "lr_ged_os"]`.

**Resolution:** For the narrow swap, the consumer bridge's FEATURE_RENAME must be adjusted to produce the column names the postprocessor expects, OR the postprocessor's config must be updated. See Stage 7 for the chosen approach.

**Month ID epoch:** Both use 1980. Verified in `generate_consumer_data.py` line 128.

**priogrid_gid vs priogrid_id:** Datafactory emits `priogrid_gid` in the index. The postprocessor's `PGMDataset` auto-renames it to `priogrid_id` (ADR-034 workaround). This works correctly — the mapper receives `priogrid_id` as expected.

### NaN vs Zero — RESOLVED

**Verification method:** Compared actual parquet files from views-models:
- VIEWSER: `purple_alien/data/raw/calibration_viewser_df.parquet` (13,110 cells × 372 months)
- Datafactory: `bright_starship/data/raw/forecasting_datafactory_df.parquet` (13,110 cells × 436 months)
- Datafactory full grid: `heavy_strider/data/raw/validation_datafactory_df.parquet` (64,818 cells × 420 months)

| Source | Total NaN | Unique cells | Cell range |
|--------|-----------|-------------|------------|
| VIEWSER (purple_alien) | **0** | 13,110 | 62356–190511 |
| Datafactory (bright_starship) | **0** | 13,110 | 62356–190511 |
| Datafactory full grid (heavy_strider) | **0** | 64,818 | full PRIO-GRID |

**Key findings:**
1. **Both systems produce zero NaN** in their consumer-facing parquet output
2. **Cell sets are 100% identical** when using the same region config (`africa_me_legacy` = 13,110 cells, shared = 13,110, symmetric difference = 0)
3. The `fillna(0.0)` in `generate_consumer_data.py` line 138 is a **no-op safety net** — no NaN exists to fill
4. VIEWSER only delivers Africa+ME land cells (13,110); it never includes ocean or out-of-scope cells
5. The cell count difference between bright_starship (13,110) and heavy_strider (64,818) is a **region config** difference (`africa_me_legacy` vs `land`), not a NaN issue

**For the narrow swap:** Use `generate_consumer_data.py --region africa_me_legacy` to produce exactly 13,110 cells matching VIEWSER's geographic scope. The output is a drop-in replacement.

### Implications

Parity is confirmed. NaN handling is a non-issue. The swap is safe.

---

## Stage 4: Release Note Constraint Audit

**Status:** [x] complete
**Question:** Which release note commitments would the migration touch?

### Findings

Audited all release notes (01-02) and prerelease notes (01-05):

| Classification | Count | Summary |
|---------------|-------|---------|
| **SAFE** | 28 | Architectural, methodological, or contractual — source-independent |
| **VERIFY** | 9 | Need to confirm datafactory equivalence |
| **RISK** | 9 | Could break if data differs from VIEWSER |

**Critical distinction:** The RISK items are almost entirely about **model training and evaluation**, not about **historical target serving**:

| RISK Constraint | Applies to Historical Target Swap? |
|----------------|--------------------------------------|
| Validation period metric thresholds (5% CRPS superiority) | **No** — evaluation framework, not data serving |
| 1% non-inferiority on guardrail metrics | **No** — model selection, not data serving |
| UCDP reconciliation version and timing | **Yes** — but datafactory uses same UCDP source |
| Magnitude Calibration Ratio baseline | **No** — model evaluation |
| Monthly update cycle alignment | **Yes** — datafactory pipeline runs on same schedule |

**For the narrow swap (historical targets only):** 28 SAFE + most VERIFY items are non-issues. The only binding RISK items are UCDP version alignment (verified — both use the same UCDP API) and update timing (verified — both use monthly cadence with annual reconciliation).

**For the broad swap (model training):** The RISK items become relevant because model evaluation metrics are calibrated against VIEWSER data. Retraining models on datafactory data would require re-evaluating against the locked thresholds.

### Implications

The narrow swap does not violate any release note commitments. The broad swap would require formal release note revision for the evaluation framework.

---

## Stage 5: The Historical Upload Path

**Status:** [x] complete
**Question:** How does historical data specifically reach Appwrite today?

### Findings

**Entry point:** Manual script at `views-models/postprocessors/un_fao/main.py`
- Constructs `PostprocessorPathManager`
- Instantiates `UNFAOPostProcessorManager`
- Calls `manager.run()` → `_read()` → `_transform()` → `_validate()` → `_save()`

**Data path is NOT hardcoded:**
```python
path_raw = self._model_path.data_raw  # PathManager-derived
historical_df = read_dataframe(
    path_raw / f"{run_type}_viewser_df{PipelineConfig.dataframe_format}"
)
```

**The swap requires two small code changes** (see Stage 2 for details). The postprocessor's `_read_historical_data()` re-fetches from VIEWSER before reading, and uses a hardcoded filename. These must be fixed for the datafactory source to take effect.

**Upload is automatic:** `_save()` runs unconditionally after `_validate()` passes.

**Versioning:** Each upload gets a unique timestamp filename (`historical_dataset_20260601_135958.parquet`). Old uploads persist in Appwrite — they're not overwritten. The FAO API retrieves the latest by `$createdAt` timestamp.

**Rollback:** Delete the bad upload via `delete_file(bucket_id, file_id)`. The FAO API automatically falls back to the previous upload (next-latest by timestamp). No code changes needed.

### Implications

1. The swap requires two small code changes in views-models and views-postprocessing (see Stage 2 and Stage 7)
2. Rollback is available via Appwrite file deletion
3. A/B comparison is possible: upload datafactory-sourced historical data, compare against existing VIEWSER-sourced data in the same bucket
4. The postprocessor is the gatekeeper: if `_validate()` passes, the data is accepted — note that `_validate()` only checks metadata column presence, not target column correctness (NaN checks commented out at unfao.py:211-212)

---

## Stage 6: Appwrite Client Duplication Assessment

**Status:** [x] complete
**Question:** How bad is the duplication, and does views-appwrite solve it?

### Findings

| Implementation | Location | LOC | SDK Compat |
|---------------|----------|-----|------------|
| AppWriteFileModule | views-pipeline-core/modules/appwrite/file.py | ~3,047 | SDK 13 only |
| AppWriteFileManager | views-faoapi/managers/appwrite.py | ~2,000 | SDK 13 + 14 |
| views-appwrite | Planned (README spec only) | 0 | Planned: 13 + 14 |

**~90% identical code** between pipeline-core and faoapi. Differences:
- faoapi has SDK 14 compatibility layer (`_as_dict()`, `_get()`)
- faoapi has configurable timeouts
- Class naming: `AppWriteFileModule` vs `AppWriteFileManager`

**views-appwrite status:** README with migration roadmap (4 phases). No implementation yet.

### Critical Answer: Migration Does NOT Require Touching Appwrite

The Appwrite layer is **completely downstream** of the swap point. The postprocessor reads a parquet file, enriches it, and uploads. Whether the parquet came from VIEWSER or datafactory is invisible to Appwrite.

Appwrite consolidation (views-appwrite) is a **parallel concern** — good hygiene, but not a prerequisite for the historical target migration.

### SOLID Assessment of Duplication

The duplication violates **REP** (Reuse/Release Equivalence — reused code should be released together) and **CCP** (Common Closure — things that change together should live together). When SDK 14 compatibility was added to faoapi, pipeline-core didn't get it. This is exactly the drift that views-appwrite would prevent.

However, this is **technical debt**, not a blocker. The migration doesn't depend on fixing it.

---

## Stage 7: Migration Readiness Assessment

**Status:** [x] complete
**Question:** Is views-datafactory operationally ready?

### Readiness Criteria

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Data parity | PASS | 99.98% match, source-aware distribution fix applied |
| Schema compatibility | PASS (with fix) | Column names need FEATURE_RENAME adjustment; priogrid_gid auto-renamed |
| NaN semantics | PASS | Both systems produce 0 NaN; fillna(0.0) is a no-op safety net |
| Cell set identity | PASS | 13,110 cells match exactly (region=africa_me_legacy) |
| Operational stability | PASS | v1.2.23 deployed, 1492 tests passing, pipeline green |
| Rollback path | PASS | Appwrite versioning, delete_file() for bad uploads |
| Release compliance | PASS | Narrow swap doesn't violate any release note commitments |
| Scope clarity | PASS | Two small code changes + file replacement, no architecture changes |

### NaN Verification: RESOLVED

NaN counts verified empirically on actual model data files in views-models (see Stage 3). Both VIEWSER and datafactory produce zero NaN. Cell sets are identical (13,110 cells) when using the same geographic region.

### Column Name Verification: CORRECTED (multi-expert review 2026-06-01)

The original investigation compared `purple_alien` columns (`lr_sb_best`) and concluded the postprocessor expected the same. The un_fao postprocessor has its own config_queryset producing `lr_ged_sb`, `lr_ged_ns`, `lr_ged_os`. The consumer bridge FEATURE_RENAME must be adjusted. See Stage 3 for the full column mapping.

### Verdict: GO

All readiness criteria are met after two prerequisite code changes.

**Prerequisites (before executing):**

| # | Change | Repo | File | Effort |
|---|--------|------|------|--------|
| 1 | Change un_fao `config_queryset.py` to return a datafactory dict descriptor (matching `bright_starship` pattern) with feature rename `ged_sb_best→lr_ged_sb`, etc. | views-models | `postprocessors/un_fao/configs/config_queryset.py` | 5 min |
| 2 | Fix `_read_historical_data()` to use `self._data_loader.cached_data_path` instead of hardcoded `viewser_df` filename | views-postprocessing | `views_postprocessing/unfao/managers/unfao.py:62` | 5 min |

**Execution plan:**
1. Apply prerequisites 1 and 2 above
2. Run the postprocessor: `python views-models/postprocessors/un_fao/main.py` — it will now fetch from datafactory via the zarr store, save as `forecasting_datafactory_df.parquet`, and read it back correctly
3. Postprocessor enriches with GAUL metadata, uploads to Appwrite
4. FAO API automatically serves the new upload
5. Verify: download the new upload from Appwrite, diff against the previous VIEWSER-sourced upload. Confirm differences are within the expected 0.02% (~1,140 cell-months from GED version differences). Spot-check a known conflict cell (e.g., Syria 2016) against UCDP source data
6. Wait for FAO API cache TTL to expire, then verify the API serves the new data
7. If wrong: `delete_file()` on the new upload, FAO API falls back to previous VIEWSER-sourced upload

**What this does NOT require:**
- No changes in views-datafactory
- No Appwrite client changes
- No release note revisions
- No model retraining
- No views-appwrite consolidation

**Should-do (not blocking):**
- Add `source: "views-datafactory"` to Appwrite upload metadata in `unfao.py:266` for provenance tracking
- Capture a golden-file snapshot of the current VIEWSER-sourced upload before executing, for regression comparison

---

## Appendix: File Reference

### views-datafactory
- `scripts/generate_consumer_data.py` — consumer bridge: grid → viewser_df.parquet
- `src/datafactory_adapters/grid_to_dataframe.py` — grid_to_dataframe(), grid_to_feature_frame()
- `src/datafactory_adapters/grid_to_country_month.py` — country-level aggregation
- `src/datafactory_query/dataset.py` — load_dataset() entry point
- `src/datafactory_query/regions.py` — geographic subsetting
- `src/datafactory_query/temporal.py` — time range parsing
- `reports/consumer_parity_investigation.md` — parity test results

### views-pipeline-core
- `views_pipeline_core/modules/dataloaders/dataloaders.py` — ViewsDataLoader
- `views_pipeline_core/data/handlers.py` — PGMDataset (ADR-034 priogrid rename)
- `views_pipeline_core/configs/prediction_store.py` — Appwrite env vars
- `views_pipeline_core/managers/prediction/io.py` — PredictionIOManager
- `views_pipeline_core/modules/datastore/datastore.py` — DatastoreModule
- `views_pipeline_core/modules/appwrite/file.py` — AppWriteFileModule (~3000 LOC)

### views-postprocessing
- `views_postprocessing/unfao/managers/unfao.py` — UNFAOPostProcessorManager
- `views_postprocessing/unfao/mapping/mapping.py` — enrich_dataframe_with_pg_info()

### views-faoapi
- `src/views_faoapi/managers/prediction.py` — PredictionStoreManager
- `src/views_faoapi/managers/appwrite.py` — AppWriteFileManager (~2000 LOC)
- `src/views_faoapi/managers/api.py` — FAOApiManager (FastAPI routes)
- `src/views_faoapi/data/handlers.py` — FAO_PGMDataset

### views-models
- `models/*/configs/config_queryset.py` — per-model data source
- `models/purple_alien/data/raw/calibration_viewser_df.parquet` — VIEWSER-sourced (13,110 cells, 0 NaN), columns: lr_sb_best
- `models/bright_starship/data/raw/forecasting_datafactory_df.parquet` — datafactory-sourced, region=africa_me_legacy (13,110 cells, 0 NaN), columns: lr_sb_best
- `models/heavy_strider/data/raw/validation_datafactory_df.parquet` — datafactory-sourced, region=land (64,818 cells, 0 NaN)
- `postprocessors/un_fao/main.py` — historical upload entry point
- `postprocessors/un_fao/configs/config_queryset.py` — **produces lr_ged_sb (NOT lr_sb_best)**
- `postprocessors/un_fao/configs/config_meta.py` — targets: ["lr_ged_sb", "lr_ged_ns", "lr_ged_os"]
- `postprocessors/un_fao/configs/config_partitions.py` — partition boundaries (cal: 121-444/445-492)

### FAO Release Notes
- `release_notes/fao_02_release_note_01/` — API schema (LOCKED)
- `release_notes/fao_02_release_note_02/` — Spatial aggregation (LOCKED)
- `prerelease_notes/fao_02_pre_release_note_05/` — Evaluation framework (pending FAO confirmation)
