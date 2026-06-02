# Sprint Plan: Admin-1 Crosswalk Builder (SHDI Integration Prerequisite)

**Date:** 2026-05-29
**Status:** Draft — developing iteratively
**Branch:** TBD (from `development`)
**Register entries:** Unlocks SHDI integration (new entry TBD); related: C-164 (WET debt, trigger fired for 6th source)
**Estimated effort:** ~6-10 hours (crosswalk mapping is the hard unknown)

---

## Problem Statement

The next data source is **GDL Subnational HDI (SHDI)** from
[globaldatalab.org](https://globaldatalab.org/shdi/table/shdi/).
SHDI provides ~4 features (SHDI composite, health index, education
index, income index) at **admin-1 resolution** — 1,805 subnational
regions across 188 countries, 1990-2023, annual.

The existing crosswalk infrastructure only handles **country-level**
resolution. V-Dem uses `_build_iso3_to_pgids()` in
`src/datafactory_viewpoint/builders/vdem_v1.py:126-152`, which reads
`data/raw/gaul_admin/iso3_code.parquet` (203 unique ISO3 codes →
86,091 pgids). This maps every PRIO-GRID cell to a country.

SHDI needs an **admin-1 → pgid** crosswalk. The GAUL infrastructure
already provides the spatial side: `data/raw/gaul_admin/gaul1_code.parquet`
maps 86,091 pgids to 2,366 unique GAUL admin-1 codes. The hard problem
is mapping GDL's 1,805 region codes to GAUL's 2,366 admin-1 codes.

**Falsification reference:** `tests/test_falsification_shdi_ordering.py`
(F-2) confirms no admin-1 viewpoint builder exists yet.

---

## What We Have

### GAUL admin-1 infrastructure (ready)

- **`data/raw/gaul_admin/gaul1_code.parquet`** — 86,091 rows,
  columns `(gid: int32, value: int32)`, 2,366 unique GAUL admin-1
  codes. Every PRIO-GRID cell has exactly one gaul1 assignment (no
  nulls, no unmatched cells).
- **`gaul1_name.parquet`** — 2,280 unique admin-1 names (some codes
  map to multiple names due to GAUL revisions).
- **`gaul0_code.parquet`** / **`iso3_code.parquet`** — country-level
  equivalents, used by V-Dem today.
- **`src/datafactory_harvester/sources/gaul_admin.py`** — the
  harvester that produces all gaul Parquets via spatial join
  (centroid-in-polygon using STRtree). Lines 187-264 implement the
  spatial join; lines 320-443 extract individual variables.

### V-Dem crosswalk pattern (template to follow)

- **`vdem_v1.py:126-152`** — `_build_iso3_to_pgids(crosswalk_path)`
  reads iso3_code.parquet, returns `dict[str, list[int]]` mapping
  ISO3 alpha-3 → pgids.
- **`vdem_v1.py:199-268`** — uses the crosswalk in the builder loop:
  1. Load crosswalk once at init
  2. For each source row, extract region code (ISO3)
  3. Look up pgids for that code
  4. Expand to `(pgid, month_id, variables)` with step function
     (constant within year, 12 monthly rows per year-region)

### Assembly integration (ready)

- **`scripts/assemble_grid.py:62-64`** — admin features already
  configured: `admin_numeric_fields = ("gaul0_code", "gaul1_code",
  "gaul2_code")`. gaul1_code is already a channel in the assembled
  grid, broadcast across all T time steps.
- Lines 407-442: Admin Parquets loaded, placed into (360×720) arrays
  using gid→(row,col) lookup, then broadcast across time dimension.

---

## The Hard Problem: GDL → GAUL Mapping

GDL uses its own region coding system (1,805 regions). GAUL uses
numeric admin-1 codes (2,366 regions). These are not the same
classification. The cardinality difference alone tells us the mapping
is not 1:1.

### What we need to investigate

1. **GDL region code format:** Download SHDI data, inspect the region
   identifier column. Is it ISO 3166-2? A proprietary GDL code? A
   GADM identifier? The answer determines the mapping strategy.

2. **GDL documentation:** Does GDL publish a codebook mapping their
   region IDs to any standard classification (GAUL, GADM, ISO 3166-2)?

3. **Boundary alignment:** GAUL 2024 admin-1 boundaries may not align
   with GDL's region definitions. Some GDL regions may span multiple
   GAUL admin-1 units, or vice versa. This requires spatial analysis.

### Mapping strategies (to evaluate)

- **If GDL uses ISO 3166-2:** Build ISO 3166-2 → GAUL admin-1 lookup
  table. This is a well-defined mapping problem.
- **If GDL uses GADM codes:** GADM and GAUL have overlapping but
  non-identical admin boundaries. Need GADM→GAUL correspondence table.
- **If GDL uses proprietary codes:** Most complex case. Options:
  a. Name matching (GDL region names → GAUL admin-1 names) with
     manual review of mismatches
  b. Spatial join (GDL region centroids/polygons → GAUL polygons)
  c. Country + admin-1 name fuzzy matching

### Cardinality analysis

- GAUL: 2,366 admin-1 codes across 203 countries
- GDL: 1,805 regions across 188 countries
- 15 countries in GAUL but not GDL (likely small states/territories)
- ~561 fewer regions in GDL → GDL likely aggregates some GAUL units
  (e.g., treating island groups as one region)

---

## Proposed Architecture

### Crosswalk function

Following the V-Dem pattern, implement in the SHDI viewpoint builder:

```python
def _build_gaul1_to_pgids(
    crosswalk_path: Path,
) -> dict[int, list[int]]:
    """Build GAUL admin-1 code → list[pgid] mapping.

    Reads gaul1_code.parquet with columns (gid, value) where
    gid is pgid and value is GAUL admin-1 code (int32).
    """
    table = pq.read_table(crosswalk_path)
    gids = table.column("gid").to_pylist()
    gaul1s = table.column("value").to_pylist()
    mapping: dict[int, list[int]] = {}
    for gid, gaul1 in zip(gids, gaul1s, strict=True):
        if gaul1 is None or gaul1 < 0:
            continue
        mapping.setdefault(int(gaul1), []).append(int(gid))
    return mapping
```

### GDL → GAUL correspondence table

A static Parquet file in `data/raw/shdi/` mapping GDL region codes
to GAUL admin-1 codes. This is the artifact that requires manual
investigation and validation.

### Viewpoint builder

`src/datafactory_viewpoint/builders/shdi_v1.py` — follows V-Dem
pattern:
1. Load SHDI source data (CSV/Parquet)
2. Load GDL→GAUL correspondence table
3. Load GAUL→pgid crosswalk (`gaul1_code.parquet`)
4. Compose: GDL region → GAUL admin-1 → pgids
5. Expand to `(pgid, month_id, shdi, healthindex, edindex, incindex)`
6. Step function temporal model (annual → 12 months)

### Memory estimate

SHDI: 4 features × 0.44 GB/feature = **1.8 GB** compile. Well within
16 GB server RAM. Bounded-memory compilation (C-223) is NOT a
prerequisite for SHDI. (Falsification F-1 confirmed.)

---

## Task Breakdown (Draft)

### Phase 0: Data Investigation
- [ ] Download SHDI data from GDL (requires free registration)
- [ ] Inspect region identifier format and column schema
- [ ] Determine GDL→GAUL mapping strategy based on actual data
- [ ] Document findings before proceeding

### Phase 1: Harvester
- [ ] `src/datafactory_harvester/sources/shdi.py` — download handler
- [ ] `scripts/harvest_shdi.py` — harvest script wrapper
- [ ] Provenance: JSONL ledger entries for SHDI snapshots
- [ ] Follow `docs/guides/data_source_integration_guide.md` Phase 1

### Phase 2: GDL→GAUL Correspondence
- [ ] Build correspondence table (strategy depends on Phase 0 findings)
- [ ] Validate coverage: what % of GDL regions map to GAUL codes?
- [ ] Document unmapped regions and decide on handling (skip vs. manual)
- [ ] Write correspondence Parquet to `data/raw/shdi/`

### Phase 3: Viewpoint Builder
- [ ] `src/datafactory_viewpoint/builders/shdi_v1.py`
- [ ] `_build_gaul1_to_pgids()` crosswalk function
- [ ] GDL→GAUL→pgid composition
- [ ] Step function temporal expansion (annual → monthly)
- [ ] Config: `ShdiViewpointConfig` frozen dataclass
- [ ] Follow ADR-031 resource management: columnar arrays, explicit `del`

### Phase 4: Compilation + Assembly Integration
- [ ] Add SHDI to compilation config
- [ ] Add SHDI grid to assembly script
- [ ] Feature names: `shdi`, `shdi_health`, `shdi_education`, `shdi_income`
- [ ] Update `PIPELINE_SOURCES` in source registry

### Phase 5: Operational Integration
- [ ] Pipeline runner or pipeline step
- [ ] Verification/visual audit script
- [ ] CIC for SHDI viewpoint builder
- [ ] ADR for SHDI integration decisions

---

## Open Questions

1. What is GDL's region coding system? (Blocks Phase 2)
2. Does GDL require attribution or have API rate limits?
3. Should SHDI skip consolidation like V-Dem (single annual release)?
4. How do we handle GDL regions that don't map to any GAUL admin-1?
5. Should the GDL→GAUL correspondence table be harvester-produced or
   manually curated?
6. Does C-164 trigger firing (6th source) require WET extraction
   before SHDI, or can SHDI proceed with WET debt?

---

## Dependencies

- **Blocks:** Nothing — this is new capability
- **Blocked by:** GDL data download (requires registration)
- **Related:** C-164 (WET debt, trigger fired for 6th source),
  C-223 (bounded-memory — NOT a prerequisite for SHDI)
- **Pattern source:** V-Dem viewpoint builder (`vdem_v1.py`)
