# Sprint Plan S3: Hetzner Deployment Batch

**Date:** 2026-05-26
**Branch:** `development` (code changes to deployment scripts + server-side configuration)
**Goal:** Deploy current codebase to Hetzner server, closing or advancing 6 Tier 2 entries that share a single blocker: the server runs a stale build without V-Dem, data boundary metadata, or operational monitoring. Also add swap and run the first production V-Dem pipeline.
**Estimated effort:** Half day (4–5 hours including server access, deployment, verification).
**Source:** `/review-rr prioritize` (2026-05-26, Clusters A + E + F), stale-zarr incident postmortem (2026-04-24), operational monitoring gap analysis.
**Prerequisite:** Sprint S2 (V-Dem documentation) should be completed first so that V-Dem features ship with correct consumer documentation. Sprint S1 (register curation) recommended but not blocking.
**Blocking:** This sprint requires SSH access to the Hetzner server (204.168.219.108) as the `views-deploy` user. All server commands must use `sudo -u views-deploy bash -c 'source ~/.profile && <command>'`.
**Risk:** Server deployment. All changes are deployed to the production server. The deployment guide (`docs/guides/hetzner_deployment_guide.md`) and `refresh_pipeline.sh` define the procedure. Rollback: the previous assembled grid is preserved in `data/assembled/` until explicitly overwritten.

---

## Context

The Hetzner server (CPX32, 8 GB RAM, Helsinki) currently runs a build from approximately v1.2.20 (2026-05-22, GHS-BUILT-S integration). Since then, 4 significant code changes have been made:

1. **V-Dem pipeline** (v1.2.22): Full harvest→viewpoint→compile→assembly integration. 22 new features in the assembled grid. Feature count rises from 53 to 75.
2. **Data boundary metadata** (v1.2.7, code deployed but zarr attrs not set): `last_valid_month_id` in zarr `.zattrs` and npy `provenance.json`. `load_dataset()` warning when `end` exceeds boundary. Health check reads data boundary.
3. **Round-trip integrity** (v1.2.7): `export_zarr.py` now reads back each feature sum after writing.
4. **Consumer parity aggregate totals** (v1.2.7): `assert_consumer_parity()` now checks global sums.

Items 2-4 have been in the code for weeks but the server hasn't been redeployed since the GHS-BUILT-S integration. This sprint batches all pending changes into one deployment.

### Entries addressed

| Entry | Tier | What deployment closes |
|-------|------|----------------------|
| C-130 | 2 | `last_valid_month_id` attr written to zarr `.zattrs` on server |
| C-131 | 2 | Heartbeat URL configured for cron monitoring |
| C-132 | 2 | Health check reads `last_valid_month_id` (enabled by C-130 deploy) |
| C-138 | 2 | `verify_remote_data.py` written and run post-deploy |
| C-149 | 2 | Partial — deploying V-Dem doesn't directly close this, but the new 75-feature grid includes V-Dem's country-level data which exercises the GAUL crosswalk differently |
| C-173 | 3 | Swap added to server (independent of code deploy) |

---

## Task 1: Add Swap to Hetzner Server (C-173)

**Why:** The CPX32 has 8 GB RAM and no swap. Without swap, the Linux OOM killer is the only backstop — any process exceeding available RAM is killed immediately (exit code 137). The GHS-POP viewpoint loads a 6.88 GiB GeoTIFF, leaving ~600 MB headroom. A 2 GB swapfile converts hard kills into degraded performance. This is a 10-minute server-side task with high safety impact.

**Register ref:** C-173 (T3). Already documented in deployment guide troubleshooting section (v1.2.18).

### Steps

SSH to the server as root (or use sudo from the deploy user):

```bash
# 1. Check current swap status
free -h
swapon --show

# 2. Create 2 GB swapfile
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 3. Verify
free -h  # should show ~2.0G swap
swapon --show  # should list /swapfile

# 4. Make persistent across reboots
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# 5. Set swappiness to 10 (prefer RAM, use swap as safety net)
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
sudo sysctl vm.swappiness=10
```

### Verification

```bash
free -h  # Swap: 2.0Gi total
cat /etc/fstab | grep swap  # /swapfile entry present
cat /proc/sys/vm/swappiness  # 10
```

### Acceptance criteria

- `free -h` shows ~2.0G swap.
- `/etc/fstab` has `/swapfile none swap sw 0 0`.
- `vm.swappiness` is 10.
- Server survives reboot with swap intact: `sudo reboot`, wait, SSH back, verify `swapon --show`.

---

## Task 2: Pull Latest Code to Server

**Why:** The server needs the current `development` branch to get V-Dem pipeline, data boundary metadata, round-trip integrity, and consumer parity fixes.

### Steps

```bash
# As views-deploy user
sudo -u views-deploy bash -c 'source ~/.profile && cd /home/views-deploy/views-datafactory && git fetch origin && git checkout development && git pull origin development'

# Verify version
sudo -u views-deploy bash -c 'source ~/.profile && cd /home/views-deploy/views-datafactory && grep "^version" pyproject.toml'
# Expected: version = "1.2.22" (or current)

# Reinstall packages
sudo -u views-deploy bash -c 'source ~/.profile && cd /home/views-deploy/views-datafactory && uv sync'

# Verify V-Dem source is registered
sudo -u views-deploy bash -c 'source ~/.profile && cd /home/views-deploy/views-datafactory && uv run python -c "from datafactory_harvester.sources.vdem import fetch_vdem; print(\"V-Dem source OK\")"'
```

### Acceptance criteria

- `pyproject.toml` shows current version.
- `uv sync` completes without errors.
- V-Dem source import succeeds.
- `uv run pytest tests/test_package_structure.py -v` passes.

---

## Task 3: Run V-Dem Pipeline (First Production Deployment)

**Why:** V-Dem has never been run on the production server. This is the first time the 22 democracy features will be compiled and assembled into the production grid. The pipeline downloads ~80 MB from v-dem.net (open access, no credentials), filters to 22 variables, builds the viewpoint (ISO3→pgid crosswalk + annual→monthly broadcast), and compiles to grid.npy.

**Register ref:** Indirectly closes C-155's "V-Dem deployed to production without verify script" concern (verify script now exists).

### Steps

```bash
# Run the full V-Dem pipeline with verification
sudo -u views-deploy bash -c 'source ~/.profile && cd /home/views-deploy/views-datafactory && uv run python scripts/run_vdem_pipeline.py --verify 2>&1 | tee /tmp/vdem_pipeline.log'
```

**Expected output:**
```
V-Dem PIPELINE (Layers 1, 3, 4)
End year: 2026
Consolidation: skipped (single release, ADR-035)

[1/3] HARVEST
  Outcome: success (or cached)
  Rows: ~37,000+

[2/3] VIEWPOINT
  X rows → data/viewpoint/vdem_v1.parquet

[3/3] COMPILE
  Grid shape: (456, 360, 720, 22)
  Output: data/compiled/vdem

[4/4] VERIFY
  (15 plots generated, all checks PASS)

V-Dem PIPELINE COMPLETE
```

### Verification

```bash
# Grid exists and has correct shape
sudo -u views-deploy bash -c 'source ~/.profile && cd /home/views-deploy/views-datafactory && uv run python -c "
import numpy as np
g = np.load(\"data/compiled/vdem/grid.npy\", mmap_mode=\"r\")
print(f\"Shape: {g.shape}\")
assert g.shape == (456, 360, 720, 22), f\"Wrong shape: {g.shape}\"
print(\"V-Dem grid OK\")
"'

# Verification plots exist
sudo -u views-deploy bash -c 'ls -la /home/views-deploy/views-datafactory/reports/audit_vdem/*.png | wc -l'
# Expected: 15
```

### Acceptance criteria

- `data/compiled/vdem/grid.npy` exists with shape `(456, 360, 720, 22)`.
- `data/compiled/vdem/feature_names.json` lists 22 features.
- Verification script produced 15 plots in `reports/audit_vdem/`.
- Pipeline log shows no errors or FAIL messages.

---

## Task 4: Run Full Pipeline Assembly

**Why:** The assembled grid must be rebuilt with V-Dem included (75 features total, up from 53). This runs `refresh_pipeline.sh` or the assembly step manually.

### Steps

Option A — Run the full pipeline via `refresh_pipeline.sh`:
```bash
sudo -u views-deploy bash -c 'source ~/.profile && cd /home/views-deploy/views-datafactory && bash scripts/refresh_pipeline.sh 2>&1 | tee /tmp/refresh_pipeline.log'
```

Option B — Run assembly only (if other sources are already current):
```bash
sudo -u views-deploy bash -c 'source ~/.profile && cd /home/views-deploy/views-datafactory && uv run python scripts/assemble_grid.py --ucdp-grid data/compiled/ucdp --acled-grid data/compiled/acled --ghspop-grid data/compiled/ghspop --ghsbuilts-grid data/compiled/ghsbuilts --vdem-grid data/compiled/vdem 2>&1 | tee /tmp/assembly.log'
```

**Expected output:**
```
Assembled grid shape: (456, 360, 720, 75)
Features: 75 (6 UCDP + 8 ACLED + 34 static + 3 admin + 1 GHS-POP + 1 GHS-BUILT-S + 22 V-Dem)
```

### Verification

```bash
sudo -u views-deploy bash -c 'source ~/.profile && cd /home/views-deploy/views-datafactory && uv run python -c "
import numpy as np, json
g = np.load(\"data/assembled/grid.npy\", mmap_mode=\"r\")
f = json.load(open(\"data/assembled/feature_names.json\"))
print(f\"Grid shape: {g.shape}\")
print(f\"Features: {len(f)}\")
assert g.shape[3] == 75, f\"Expected 75 features, got {g.shape[3]}\"
# Check V-Dem features are present
vdem_features = [x for x in f if x.startswith(\"v2\")]
print(f\"V-Dem features in grid: {len(vdem_features)}\")
assert len(vdem_features) == 22
print(\"Assembly OK\")
"'
```

### Acceptance criteria

- Assembled grid has shape `(456, 360, 720, 75)`.
- `feature_names.json` lists 75 features.
- 22 V-Dem features present in the assembled grid.
- `provenance.json` contains `last_valid_vdem_month_id`.

---

## Task 5: Export Zarr and Verify Round-Trip (C-137)

**Why:** The zarr export step now includes round-trip sum verification (C-137 fix). This is the first time it runs with V-Dem included. The round-trip check will verify that all 75 features survive the zarr write.

### Steps

```bash
sudo -u views-deploy bash -c 'source ~/.profile && cd /home/views-deploy/views-datafactory && uv run python scripts/export_zarr.py 2>&1 | tee /tmp/export_zarr.log'
```

**Expected output includes:**
```
Round-trip verification: 75/75 features match
```

If the round-trip check fails, the script exits with code 1 and the zarr store is not served. This is the C-137 fix in action.

### Verification

```bash
# Zarr store exists and has correct shape
sudo -u views-deploy bash -c 'source ~/.profile && cd /home/views-deploy/views-datafactory && uv run python -c "
import zarr
store = zarr.open(\"data/served/views_data.zarr\", mode=\"r\")
print(f\"Zarr shape: {store[\"grid\"].shape}\")
print(f\"Attrs: {dict(store.attrs)}\")
"'

# Verify last_valid_month_id is in .zattrs (C-130)
sudo -u views-deploy bash -c 'source ~/.profile && cd /home/views-deploy/views-datafactory && uv run python -c "
import zarr
store = zarr.open(\"data/served/views_data.zarr\", mode=\"r\")
lvm = store.attrs.get(\"last_valid_month_id\")
print(f\"last_valid_month_id: {lvm}\")
assert lvm is not None, \"last_valid_month_id not set — C-130 fix not working\"
print(\"C-130 metadata deployed\")
"'
```

### Acceptance criteria

- Zarr export completes with exit code 0.
- Round-trip verification passes for all 75 features.
- `last_valid_month_id` is present in zarr `.zattrs` (C-130 closure).
- `last_valid_vdem_month_id` is present in zarr `.zattrs`.

---

## Task 6: Configure Heartbeat Monitoring (C-131)

**Why:** The monthly pipeline runs via cron (`0 0 21 * *`). If cron crashes or the `views-deploy` user is deleted, the pipeline silently stops. `refresh_pipeline.sh` already has heartbeat support (pings `$HEARTBEAT_URL` on successful completion), but the URL hasn't been configured.

**Register ref:** C-131 (T2).

### Steps

1. **Create a healthchecks.io check** (or cronitor, or uptime-kuma):
   - Name: `views-datafactory monthly pipeline`
   - Schedule: monthly, expected around the 21st
   - Grace period: 48 hours (pipeline may take several hours)
   - Copy the ping URL (e.g., `https://hc-ping.com/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)

2. **Set the URL on the server:**
   ```bash
   # Add to views-deploy's environment
   echo 'export HEARTBEAT_URL="https://hc-ping.com/YOUR-UUID-HERE"' | sudo -u views-deploy tee -a /home/views-deploy/.profile
   ```

3. **Verify the heartbeat fires:**
   ```bash
   # Manual test
   sudo -u views-deploy bash -c 'source ~/.profile && curl -fsS -m 10 --retry 5 "$HEARTBEAT_URL" > /dev/null && echo "Heartbeat OK"'
   ```

4. **Check healthchecks.io dashboard:** The check should show a green "UP" status after the manual ping.

### Acceptance criteria

- `$HEARTBEAT_URL` is set in `views-deploy`'s `.profile`.
- Manual curl to `$HEARTBEAT_URL` returns HTTP 200.
- Healthchecks.io (or equivalent) shows the check as "UP."
- Next cron run will automatically ping on success (via `refresh_pipeline.sh`).

---

## Task 7: Run Health Check (C-132)

**Why:** The health check (`check_health.py`) now reads `last_valid_month_id` from zarr `.zattrs` (C-132 fix). After deploying C-130's metadata (Task 5), the health check should report data boundary status for the first time.

**Register ref:** C-132 (T2).

### Steps

```bash
sudo -u views-deploy bash -c 'source ~/.profile && cd /home/views-deploy/views-datafactory && uv run python scripts/check_health.py 2>&1'
```

**Expected output includes:**
```
Data boundary: month XXX (expected >= YYY) — CURRENT
```

If it shows `STALE`, investigate — the data boundary should be current after a fresh pipeline run.

### Acceptance criteria

- Health check completes without errors.
- `data_boundary_current` is `True` (or shows `CURRENT`).
- `last_valid_month_id` is reported (not None).

---

## Task 8: Write and Run `verify_remote_data.py` (C-138)

**Why:** The health check validates metadata freshness but never checks whether the data values in the served zarr store are correct. The stale-zarr incident (2026-04-24) showed that a zarr store can pass all metadata checks while containing wrong values. `verify_remote_data.py` fetches a small slice from the HTTP endpoint and compares totals against the local assembled grid.

**Register ref:** C-138 (T2). Resolution described in the entry: "Add a `verify_remote_data.py` script that fetches a small slice from the HTTP endpoint and compares totals against the local grid. Run as pipeline step 8."

### Steps

1. **Write `scripts/verify_remote_data.py`** with the following logic:
   - Load the local assembled grid (`data/assembled/grid.npy`)
   - Open the remote zarr store via the HTTP endpoint (using credentials from `.netrc`)
   - Select 3-5 representative time steps (first, middle, last valid, and one random)
   - For each time step, compare the sum of each feature between local and remote
   - Assert sums match within floating-point tolerance (`rtol=1e-5`)
   - Report per-feature results and overall PASS/FAIL
   - Exit with code 0 on PASS, 1 on FAIL

2. **Run on server:**
   ```bash
   sudo -u views-deploy bash -c 'source ~/.profile && cd /home/views-deploy/views-datafactory && uv run python scripts/verify_remote_data.py 2>&1'
   ```

3. **Add to `refresh_pipeline.sh`** as the final step (after export_zarr, before heartbeat).

### Acceptance criteria

- `scripts/verify_remote_data.py` exists and runs.
- Output shows feature-by-feature comparison for 3-5 time steps.
- All features PASS (sums match between local and remote).
- Script is referenced in `refresh_pipeline.sh` as the final verification step.

---

## Task 9: Update Risk Register

**Why:** After Tasks 1-8, several entries can be closed or advanced.

### Entry status updates

| Entry | Before | After | Rationale |
|-------|--------|-------|-----------|
| C-130 | T2 RESOLVING | **RESOLVED** | `last_valid_month_id` now in zarr `.zattrs` on server |
| C-131 | T2 RESOLVING | **RESOLVED** | Heartbeat URL configured, manual ping verified |
| C-132 | T2 RESOLVING | **RESOLVED** | Health check reads data boundary, confirmed CURRENT |
| C-137 | T2 → resolved in S1 | Already RESOLVED | Confirmed working in production (round-trip check passed) |
| C-138 | T2 DEFER | **RESOLVED** | `verify_remote_data.py` written, run, and added to pipeline |
| C-173 | T3 DEFER | **RESOLVED** | 2 GB swap active, persistent across reboots |

### Header count impact (cumulative with S1)

If S1 was done first (60 open):
- Resolve C-130, C-131, C-132, C-138 (all T2): 60 → 56 open, T2: 6 → 2
- Resolve C-173 (T3): 56 → 55 open, T3: 15 → 14

Remaining Tier 2 after S3: C-88 (SSH restriction, blocked on PRIO IT), C-149 (unmapped GAUL cells, partial).

### Acceptance criteria

- All 6 entries are struck through in the summary table.
- Resolution notes reference the deployment date and verification results.
- Header counts are updated.
- Tier 2 open count drops to 2.

---

## Rollback Plan

If any task fails:

1. **Swap (Task 1):** `sudo swapoff /swapfile && sudo rm /swapfile`. Remove fstab entry.
2. **Code pull (Task 2):** `git checkout <previous-commit-hash>` and `uv sync`.
3. **V-Dem pipeline (Task 3):** Delete `data/compiled/vdem/` — previous assembly still uses old feature set.
4. **Assembly (Task 4):** Re-run assembly without `--vdem-grid` flag — reverts to 53-feature grid.
5. **Zarr export (Task 5):** The previous zarr store is overwritten during export. If export fails (exit code 1 from round-trip check), the partial store should not be served. Restore from backup or re-export without V-Dem.
6. **Heartbeat (Task 6):** Remove `HEARTBEAT_URL` from `.profile`. No runtime impact.
7. **Health check (Task 7):** No rollback needed — read-only.
8. **Verify remote (Task 8):** No rollback needed — read-only verification script.

---

## Commit Strategy

Two commits before deployment:

1. **`verify_remote_data.py` creation** (if needed):
   ```
   feat: add post-deploy remote data verification script (C-138)
   ```

2. **Register updates** (after deployment):
   ```
   docs: resolve C-130, C-131, C-132, C-138, C-173 after Hetzner deployment
   ```

---

## Final Verification Checklist

```bash
# On server:
free -h                          # Swap: ~2.0G
swapon --show                    # /swapfile listed
cat /proc/sys/vm/swappiness      # 10

# Data:
ls -la data/compiled/vdem/grid.npy          # exists
ls -la data/assembled/grid.npy              # exists, recent timestamp
ls -la data/served/views_data.zarr/.zattrs  # exists

# Metadata:
uv run python -c "import zarr; s=zarr.open('data/served/views_data.zarr','r'); print(dict(s.attrs))"
# Should show last_valid_month_id, last_valid_vdem_month_id, feature_count=75

# Health:
uv run python scripts/check_health.py      # All checks pass, data boundary CURRENT

# Remote verification:
uv run python scripts/verify_remote_data.py # All features PASS

# Heartbeat:
curl -fsS -m 10 "$HEARTBEAT_URL"           # HTTP 200
```
