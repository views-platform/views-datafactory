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
