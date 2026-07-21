# Server Operations Runbook

Day-to-day operations for the Hetzner data server.
For initial setup, see `hetzner_deployment_guide.md`.

---

## Quick Reference

| What | Command |
|------|---------|
| SSH in | `ssh simmaa_prio@204.168.219.108` |
| Check current version | `cat /home/views-deploy/.views-deploy-tag` |
| Set version to deploy | `echo "v1.2.3" \| sudo tee /home/views-deploy/.views-deploy-tag` |
| Run pipeline | `sudo -u views-deploy bash -c 'source ~/.profile && cd ~/views-datafactory && bash scripts/refresh_pipeline.sh'` |
| Check pipeline logs | `sudo -u views-deploy cat /home/views-deploy/views-datafactory/logs/refresh.log` |
| Check last failure | `sudo -u views-deploy cat /home/views-deploy/views-datafactory/logs/pipeline_failure.json` |
| List raw data | `sudo -u views-deploy ls -la /home/views-deploy/views-datafactory/data/raw/ucdp_annual/` |
| Check grid totals | See "Verify data" section below |
| View pipeline status page | `http://204.168.219.108/status.html` (public, no auth — ADR-038) |
| Regenerate status page | `sudo -u views-deploy bash -c 'source ~/.profile && cd ~/views-datafactory && uv run python scripts/generate_status.py --output data/status.html'` |

---

## Key Concepts

### What is `views-deploy`?

A dedicated service account (not a person). Think of it as a robot
employee with exactly three permissions:

1. Read code from GitHub (via a read-only deploy key)
2. Read/write data files under its home directory
3. Make HTTP requests to external APIs (UCDP, ACLED, PRIO-GRID, GAUL)

It **cannot** install software, change system settings, or access
your files. It exists so that if the pipeline has a bug, the damage
is confined to `/home/views-deploy/` — it cannot break the OS.

### Why do I need `sudo -u views-deploy`?

You log in as `simmaa_prio`. The data files belong to `views-deploy`.
Linux prevents you from reading another user's files. `sudo -u views-deploy`
says "run this command as the views-deploy user." Your `simmaa_prio`
account has `sudo` privileges, so this works.

### What is a git tag?

A permanent label on a specific commit. Unlike a branch (which moves
forward as you add commits), a tag stays on the same commit forever.

```
main:    A → B → C → D → E    ← branch (moves as commits are added)
                    ↑
                  v1.2.3       ← tag (stays on D forever)
```

The server uses tags (not branches) so it always runs a known, frozen
version of the code. `v1.2.3` today is the same code as `v1.2.3` next
month. Branches can change; tags cannot.

---

## Where Everything Lives

```
/home/views-deploy/
├── views-datafactory/           ← git repo checkout
│   ├── scripts/                 ← pipeline scripts
│   ├── src/                     ← Python packages
│   ├── data/
│   │   ├── raw/
│   │   │   ├── ucdp_annual/     ← harvested annual parquet (~57 MB)
│   │   │   ├── ucdp_candidate/  ← candidate monthly parquets
│   │   │   ├── ucdp_dot9/       ← UCDP .9 estimates
│   │   │   ├── acled/           ← ACLED event data
│   │   │   ├── priogrid/        ← PRIO-GRID static features
│   │   │   └── gaul_admin/      ← GAUL admin boundaries
│   │   ├── consolidated/        ← merged UCDP event store
│   │   ├── viewpoint/           ← materialized views
│   │   ├── compiled/            ← PRIO-GRID npy + parquet
│   │   └── assembled/           ← final output
│   │       ├── grid.npy         ← numpy grid (T × H × W × F)
│   │       ├── grid.zarr/       ← zarr store (served over HTTP)
│   │       └── feature_names.json
│   ├── logs/                    ← pipeline run logs
│   └── provenance/              ← JSONL provenance ledgers
├── .views-deploy-tag            ← version to deploy (e.g., "v1.2.3")
├── .profile                     ← env vars (UCDP_API_TOKEN, ACLED_USERNAME, ACLED_PASSWORD, PATH)
└── .ssh/id_ed25519              ← read-only GitHub deploy key

/srv/views-data/                 ← Caddy web server root
├── grid.zarr → symlink → /home/views-deploy/.../grid.zarr
└── dataframe.parquet → symlink → /home/views-deploy/.../dataframe.parquet
```

### How data reaches consumers

```
GitHub tag
  → git fetch on server
    → checkout tagged version
      → harvest APIs (UCDP, ACLED, PRIO-GRID, GAUL)
        → consolidate → compile → assemble
          → export zarr
            → Caddy serves /srv/views-data/
              → bright_starship calls load_dataset(zarr_url)
```

---

## Common Operations

### Deploy a new version

On your laptop:
```bash
# 1. Tag the release (from main branch)
git tag v1.2.4
git push origin v1.2.4
```

On the server:
```bash
# 2. SSH in
ssh simmaa_prio@204.168.219.108

# 3. Set the new version
echo "v1.2.4" | sudo tee /home/views-deploy/.views-deploy-tag

# 4. Run the pipeline
sudo -u views-deploy bash -c 'source ~/.profile && cd ~/views-datafactory && bash scripts/refresh_pipeline.sh'
```

### Run individual pipeline steps manually

Use this when you need to run specific steps instead of the full
pipeline — for example, after adding a new source whose pipeline
script isn't in `refresh_pipeline.sh` yet, or when re-running only
one stage after a failure.

**Important:** `assemble_grid.py` silently skips any source whose
`--*-grid` flag is omitted. If you run it without flags you get a
UCDP + static + admin grid only (~42 features instead of ~79).
There is no error or warning — the output looks correct but is
incomplete.

```bash
# 1. Source pipelines (run whichever sources need updating)
sudo -u views-deploy bash -c 'source ~/.profile && cd ~/views-datafactory && uv run python scripts/run_vdem_pipeline.py'
sudo -u views-deploy bash -c 'source ~/.profile && cd ~/views-datafactory && uv run python scripts/run_ghspop_pipeline.py'
sudo -u views-deploy bash -c 'source ~/.profile && cd ~/views-datafactory && uv run python scripts/run_ghsbuilts_pipeline.py'
sudo -u views-deploy bash -c 'source ~/.profile && cd ~/views-datafactory && uv run python scripts/run_acled_pipeline.py'

# 2. Assemble — pass ALL source flags to get the full grid
sudo -u views-deploy bash -c 'source ~/.profile && cd ~/views-datafactory && uv run python scripts/assemble_grid.py \
    --acled-grid data/compiled/acled \
    --ghspop-grid data/compiled/ghspop \
    --ghsbuilts-grid data/compiled/ghsbuilts \
    --vdem-grid data/compiled/vdem'

# 3. Export
sudo -u views-deploy bash -c 'source ~/.profile && cd ~/views-datafactory && uv run python scripts/export_zarr.py'
sudo -u views-deploy bash -c 'source ~/.profile && cd ~/views-datafactory && uv run python scripts/export_dataframe.py'

# 4. Health check
sudo -u views-deploy bash -c 'source ~/.profile && cd ~/views-datafactory && uv run python scripts/check_health.py'

# 5. Verify feature count
sudo -u views-deploy bash -c 'source ~/.profile && cd ~/views-datafactory && uv run python -c "
import json
f = json.load(open(\"data/assembled/feature_names.json\"))
print(f\"Features: {len(f)}\")
for i, name in enumerate(f):
    print(f\"  {i}: {name}\")
"'
# Expected: 79 features (6 UCDP + 8 ACLED + 1 GHS-POP + 1 GHS-BUILT-S
#   + 22 V-Dem + 4 SHDI + 34 static + 3 admin)
```

If you only need to re-run assembly (all sources already compiled),
skip step 1. If `refresh_pipeline.sh` is up to date with all sources,
prefer that instead — it handles flags and step ordering automatically.

### Verify data after pipeline run

Check that the assembled grid has the right totals:

```bash
sudo -u views-deploy bash -c 'source ~/.profile && cd ~/views-datafactory && uv run python3 -c "
import numpy as np, json
grid = np.load(\"data/assembled/grid.npy\", mmap_mode=\"r\")
features = json.loads(open(\"data/assembled/feature_names.json\").read())
for i, name in enumerate(features):
    if name.startswith(\"ged_\"):
        print(f\"{name}: {grid[:,:,:,i].sum():,.0f}\")
"'
```

Expected totals (as of v1.2.7, UCDP GED v25.1, verified 2026-04-26):

| Feature | Expected total |
|---------|---------------|
| `ged_sb_best` | ~1,956,320 |
| `ged_ns_best` | ~285,346 |
| `ged_os_best` | ~1,232,241 |

The script also prints `ged_sb_count`, `ged_ns_count`, and `ged_os_count`
(event counts per violence type). These are not listed above because
they were not independently verified — compare against prior runs rather
than a fixed reference value.

From your laptop (verifies the HTTP-served zarr):

```bash
uv run python3 -c "
from datafactory_query import load_dataset
from datafactory_query.defaults import DEFAULT_REMOTE
df = load_dataset(region='africa_me_legacy', start=121, end=492,
    features=['ged_sb_best'], output_format='dataframe',
    data_dir=DEFAULT_REMOTE.zarr_url, month_id_epoch=1980)
print(f'Remote ged_sb_best: {df[\"ged_sb_best\"].sum():,.0f}')
print(f'Expected:           ~744,956')
"
```

### Verify raw data totals after harvest

After a harvest completes, verify the annual event count matches the
API's expected total. A shortfall here means downstream data will be
silently wrong (see post-mortem: 2026-04-25 stale zarr store).

```bash
sudo -u views-deploy bash -c 'source ~/.profile && cd ~/views-datafactory && uv run python3 -c "
import pyarrow.parquet as pq
t = pq.read_table(\"data/raw/ucdp_annual/ged_v25_1.parquet\")
print(f\"Annual events: {len(t):,}\")
# Expected: 384,918 for GED v25.1 (page_size=1000 with rate-limit backoff)
# If significantly lower, the harvest hit the page_size=50000 truncation bug
# or rate limiting silently truncated results.
"'
```

### Run health check

After any pipeline run, check per-source freshness and export SLO:

```bash
sudo -u views-deploy bash -c 'source ~/.profile && cd ~/views-datafactory && uv run python scripts/check_health.py'
```

Output shows per-source status with SLO labels:
- `[SLO: static]` — PRIO-GRID datasets; never stale from age
- `[SLO: 1y]` — UCDP Annual; yearly release cycle
- `[SLO: 31d]` — UCDP Candidate/.9, consolidation, viewpoint, compilation; monthly cycle
- `[SLO: 168h]` — export freshness (ADR-018 default)

For JSON output (monitoring integration): add `--json` flag.

### Force a full data rebuild

If you suspect stale data, delete the assembled output and re-run:

```bash
sudo -u views-deploy bash -c 'cd ~/views-datafactory && rm -rf data/assembled data/compiled data/viewpoint data/consolidated'
sudo -u views-deploy bash -c 'source ~/.profile && cd ~/views-datafactory && bash scripts/refresh_pipeline.sh'
```

This forces every step to re-run from raw harvested data.

### Check pipeline health

```bash
# Last run status
sudo -u views-deploy cat /home/views-deploy/views-datafactory/logs/pipeline_duration.json

# Last failure (if any)
sudo -u views-deploy cat /home/views-deploy/views-datafactory/logs/pipeline_failure.json 2>/dev/null || echo "No recent failure"

# Zarr metadata (from your laptop)
curl -s -u $(grep -A2 '204.168.219.108' ~/.netrc | awk '/login/{l=$2} /password/{p=$2} END{print l":"p}') \
  http://204.168.219.108/grid.zarr/.zattrs | python3 -m json.tool
```

### View pipeline logs

```bash
# Full log (can be long)
sudo -u views-deploy tail -100 /home/views-deploy/views-datafactory/logs/refresh.log

# Just the last run
sudo -u views-deploy bash -c 'cd ~/views-datafactory && cat logs/pipeline_duration.json'
```

---

## Pipeline Writer Lock (C-316, #353)

One lock, `/var/lock/views-pipeline.lock`, serializes everything
that writes shared data directories. `refresh_pipeline.sh` holds
it for the whole run; standalone writer scripts (assemble, export,
run_*_pipeline, consumer bridge) acquire it via
`datafactory_provenance.hold_pipeline_lock()` and **refuse to
start** if a run is in progress:

```
PipelineLockHeldError: Pipeline lock ... is held (holder pid N) —
a pipeline run is in progress. Wait for it to finish ...
```

That refusal is the system working — wait for the run (status
page), don't fight it. `--force-no-lock` exists on every writer
script as a deliberate recovery escape hatch; it logs loudly and
you own the collision risk.

Crash safety is kernel-level: an flock dies with its holder, so a
crashed run's lock releases instantly and a live run's lock can
never be stolen. There is no age-based staleness (the old 300s
heuristic misfired on slow runs and was removed — C-267).

## Dead-Man Heartbeat Monitoring (C-131, #324)

The pipeline pings an external monitoring service so that failures
alert a human even when nobody is watching a terminal. Two signals:

- **Success ping** — end of `refresh_pipeline.sh`: `curl "$HEARTBEAT_URL"`.
  If the ping does not arrive on schedule (cron missed, server down,
  pipeline hung), the service alerts after its grace period. This is
  the dead-man switch: silence itself is the alarm.
- **Failure ping** — `on_failure()` trap: `curl "$HEARTBEAT_URL/fail"`.
  Flips the check to failing immediately instead of waiting for the
  missed schedule.
- **Start ping** — after lock acquisition: `curl "$HEARTBEAT_URL/start"`.
  Covers the SIGKILL blind spot (C-317): the OOM killer bypasses
  bash traps entirely, so a killed run sends neither success nor
  failure — but a dangling "started" state alerts at the grace
  timeout (~24h) instead of the next monthly schedule (~31d).

Both are no-ops when `HEARTBEAT_URL` is unset, and both are guarded
with `|| true` — an unreachable monitoring service must never mask
the pipeline's own exit code.

### Setup (one-time, operator)

1. Create a check at [healthchecks.io](https://healthchecks.io)
   (free tier, one check). Schedule: match the cron cadence
   (currently monthly, 21st at 00:00). Grace period: 24 hours —
   the full run can take ~8 hours.
2. Add the ping URL to the deploy user's profile:

   ```bash
   echo 'export HEARTBEAT_URL="https://hc-ping.com/<uuid>"' | \
     sudo tee -a /home/views-deploy/.profile
   ```

3. Verify both directions:

   ```bash
   # Failure signal → check goes red, email arrives
   sudo -u views-deploy bash -c 'source ~/.profile && curl -fsS "$HEARTBEAT_URL/fail"'
   # Success signal → check returns to healthy
   sudo -u views-deploy bash -c 'source ~/.profile && curl -fsS "$HEARTBEAT_URL"'
   ```

### What an alert means

The pipeline failed or never ran. First response:

```bash
sudo -u views-deploy cat /home/views-deploy/views-datafactory/logs/pipeline_failure.json
sudo -u views-deploy tail -50 /home/views-deploy/views-datafactory/logs/refresh.log
```

Then check the status page: http://204.168.219.108/status.html
(regenerates on every pipeline exit, success or failure).

To rotate the URL: create a new check, update `~/.profile`, delete
the old check.

**Vendor portability (#340):** the only coupling to healthchecks.io
is the `HEARTBEAT_URL` value in `/home/views-deploy/.profile` — the
ping semantics (`/start`, `/fail`, bare success) are the same
convention Uptime Kuma and Better Stack heartbeats accept. Swapping
vendors is a one-line URL change plus recreating the check + alert
recipients on the new vendor's side (recipients live in the vendor
dashboard; keep a note of them here when they change: currently the
operator's PRIO address).

---

## Swap Configuration

The CPX32 has 8 GB RAM. Assembly with 75+ features (UCDP + ACLED +
GHS-POP + GHS-BUILT-S + V-Dem + static + admin) peaks around 9-10 GB,
which causes the OOM killer to terminate the process. Adding swap lets
the kernel spill excess pages to NVMe, which is fast enough for the
occasional overflow without upgrading the server plan.

### Add 4 GB swap (one-time setup)

```bash
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

The last line makes it persistent across reboots.

### Verify swap is active

```bash
free -h
# Should show: Swap: 4.0Gi total
```

### Remove swap (if upgrading server plan instead)

```bash
sudo swapoff /swapfile
sudo rm /swapfile
sudo sed -i '/swapfile/d' /etc/fstab
```

### Alternative: rescale the server

In the Hetzner Cloud console, click **Rescale** to upgrade to CPX42
(8 vCPU, 16 GB RAM, ~27 EUR/mo). Requires a power-off (~30 seconds).
CPU/RAM can be scaled back down later; disk resize is one-way.

---

## Troubleshooting

### "Permission denied" when accessing views-deploy files

You need `sudo -u views-deploy` before any command that touches
their files. You cannot `cd` into `/home/views-deploy/` directly.

```bash
# Wrong:
ls /home/views-deploy/views-datafactory/data/
# → Permission denied

# Right:
sudo -u views-deploy ls /home/views-deploy/views-datafactory/data/
```

### Pipeline ran but data didn't change

Check if the harvest step actually downloaded new data:
```bash
sudo -u views-deploy ls -la /home/views-deploy/views-datafactory/data/raw/ucdp_annual/
```
The annual parquet should be ~57 MB. If it's much smaller or missing,
the harvest step may have failed silently (check logs).

### Pipeline fails with "uv: command not found"

The pipeline runs as `views-deploy`, which has `uv` in `~/.cargo/bin`.
Make sure the command sources `~/.profile` first:

```bash
# Wrong:
sudo -u views-deploy bash -c 'cd ~/views-datafactory && bash scripts/refresh_pipeline.sh'

# Right (note: source ~/.profile):
sudo -u views-deploy bash -c 'source ~/.profile && cd ~/views-datafactory && bash scripts/refresh_pipeline.sh'
```

### Zarr store exists but HTTP returns 403

The Caddy web server serves from `/srv/views-data/` via symlinks.
Check that the symlinks are intact and permissions allow traversal:

```bash
ls -la /srv/views-data/
# Should show symlinks to /home/views-deploy/...

# If broken, recreate:
sudo ln -sf /home/views-deploy/views-datafactory/data/assembled/grid.zarr /srv/views-data/grid.zarr
```
