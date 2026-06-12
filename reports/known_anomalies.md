# Known Anomalies

Things that look wrong in pipeline output but are expected. Check here before investigating.

**Purpose:** Prevent re-investigation of known quirks. If pipeline output looks alarming, search this document first. If the anomaly is listed here with a matching signature, it is understood and not a bug.

**When to add:** Any time you see unexpected output, investigate it, and conclude it is benign — log it here so the next person doesn't repeat the investigation.

**When to remove:** If the root cause is fixed (e.g., crosswalk updated, code changed), strike through the entry and note the fix date.

---

## A-1: V-Dem countries not in GAUL crosswalk (9 codes dropped)

**First observed:** 2026-06-10 (v1.2.29 deployment)
**Pipeline output:**
```
9 V-Dem countries not in GAUL crosswalk: ['DDR', 'GMB', 'LUX', 'PSG', 'SGP', 'SML', 'XKX', 'YMD', 'ZZB']
```

**Why it happens:** The V-Dem viewpoint builder maps V-Dem country codes to GAUL admin boundaries. These 9 codes have no match in the crosswalk table, so their V-Dem data is dropped during the viewpoint build.

**Why it's expected:**

| Code | Entity | Reason for no GAUL match |
|------|--------|--------------------------|
| DDR | East Germany | Dissolved state (1990) |
| YMD | South Yemen | Dissolved state (1990) |
| LUX | Luxembourg | Microstate — below PRIO-GRID cell resolution |
| SGP | Singapore | Microstate — below PRIO-GRID cell resolution |
| XKX | Kosovo | Partially recognized territory |
| SML | Somaliland | Unrecognized state |
| PSG | Palestine/Gaza | Contested territory |
| ZZB | Zanzibar | Sub-national entity (part of Tanzania) |
| GMB | Gambia | Likely crosswalk coding mismatch — worth investigating if Gambia data is needed |

**Data impact:** V-Dem features are missing for these 9 entities in the assembled grid. For dissolved states and sub-national entities this is correct (no PRIO-GRID cells to assign to). For GMB, this may be a fixable crosswalk gap.

**When to worry:** If the list changes between runs (new codes appearing or existing ones disappearing), investigate — it could indicate a V-Dem data model change.

---

## A-2: Stale lock file removal during pipeline run

**First observed:** 2026-06-10 (v1.2.29 deployment)
**Pipeline output:**
```
Removing stale lock file provenance/viewpoint/vdem_v1_ledger.jsonl.lock (age: 122772s)
```

**Why it happens:** The `file_lock` module uses `fcntl.flock()` with a lock file for concurrent access protection. If a previous pipeline run was killed (`kill -9`, server reboot, OOM) without releasing the lock, the lock file persists on disk. The stale lock cleanup detects lock files older than 5 minutes and removes them.

**Why it's expected:** The lock age (122,772s = ~34 hours) indicates the previous run was interrupted. The cleanup mechanism is working as designed — it prevents stale locks from permanently blocking the pipeline.

**When to worry:** If you see this message on every run with a short age (under 5 minutes), it could indicate a concurrency issue (two pipeline instances running simultaneously) or a crash loop. Check `crontab -l` for duplicate entries and `ps aux | grep refresh_pipeline` for concurrent processes.

---

## A-3: GDL crosswalk maps 2,874 pgids to ocean cells (landarea=0)

**First observed:** 2026-06-12 (SHDI visual audit investigation)
**Compiled grid signature:** 138 cells with non-NaN SHDI values at grid locations where `landarea=0` in GHS-POP.

**Why it happens:** The GDL shapefiles define subnational boundaries using vector polygons. The SHDI harvester's spatial join (`gdl_to_pgid.parquet`) assigns a pgid to any 0.5° grid cell whose centroid falls inside a GDL polygon. GDL polygons extend over coastal water, fjords, and ice sheet — the polygon boundary is the political border, not the coastline. Meanwhile, `landarea` in GHS-POP classifies cells at 0.5° resolution using a different raster source, so cells that are politically part of a territory can have `landarea=0`.

**Breakdown of the 2,874 ocean-mapped pgids:**

| GDL region | Count | What it is |
|------------|-------|------------|
| GRLt (Greenland) | 2,630 | Fjords, ice sheet, Arctic coast |
| SJMt (Svalbard) | 102 | Arctic archipelago |
| RUSr102/107/108 (Russia) | 113 | Arctic coast (Siberia, Kamchatka) |
| FRAr127 (French Guiana) | 17 | Coastal overshoot into Atlantic |
| FRAr128 (Réunion) | 1 | Island cell below GHS-POP resolution |
| IDNr112/129/130 (Indonesia) | 3 | Small island cells |
| TKMr103 (Turkmenistan) | 3 | Caspian Sea coast |
| Other (PYF, ERIr103, TCA, BHS, JEY) | 5 | Small islands, Eritrea Red Sea coast |

Of the 2,874, only **138** receive non-NaN SHDI values (the rest are outside the GDL-to-PRIO spatial join despite being inside the GDL polygon — a second filtering layer).

**Forecast impact:** Only **2 cells** fall in the Africa+ME forecast bounding box:

| pgid | Location | SHDI | GAUL code | Conflict events |
|------|----------|------|-----------|-----------------|
| 99112 | Réunion (lat -21.2, lon 55.8) | 0.857 | 153 (France) | 60 ACLED events |
| 152362 | Eritrea coast (lat 15.8, lon 40.8) | 0.408 | 122 (Eritrea) | 0 |

Both have valid GAUL codes (>0) and are included in country-month aggregation. Neither is open ocean — they are coastal territory that falls below GHS-POP's land detection threshold at 0.5° resolution.

**Why it's expected:** This is the same raster-vector misalignment phenomenon documented in the C-149 postmortem (GAUL centroids falling in water). The GDL crosswalk uses centroid-in-polygon, which is geometrically correct — the cells really are inside the GDL region boundary. The mismatch is between political boundaries (vector) and land classification (raster). SHDI is an intensive quantity (ADR-040), so broadcasting an index value to a coastal cell does not corrupt sums or counts.

**When to worry:**
- If adding an ocean-focused data source (maritime events, sea surface temperature): these 138 cells would have both SHDI values and ocean data, potentially confusing models that assume ocean cells have no socioeconomic features. Filter on `landarea > 0` to exclude them.
- If a new data source uses `landarea=0` as a mask to skip cells: SHDI data in those 138 cells would be silently ignored. Ensure the mask logic is documented.
- If the count changes significantly between SHDI versions: re-investigate — it could indicate a GDL shapefile boundary change.

**Cross-refs:** C-149 (resolved — GAUL coastal cells), ADR-039 (area-majority), ADR-040 (intensive quantities), ADR-036 (SHDI source selection).
