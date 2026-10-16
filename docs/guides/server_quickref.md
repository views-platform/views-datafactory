# Server Quick Reference

Copy-paste commands for the Hetzner server. For explanations, see `server_operations.md`.

```
ssh <your-user>@204.168.219.108
```

All commands below assume you are on the server.

---

## Deploy a new version

**All four blocks. Step 1 alone is not a deploy (C-343)** — the pipeline's own
`git checkout` lands a change to `refresh_pipeline.sh` one run later, and never
runs `uv sync` at all.

```bash
# 1. Set version
sudo -u views-deploy bash -c 'source ~/.profile && echo v1.2.6 > ~/.views-deploy-tag'

# 2. Pull and checkout (git checkout -- uv.lock discards platform-local lock changes)
sudo -u views-deploy bash -c 'source ~/.profile && cd ~/views-datafactory && git fetch --tags && git checkout -- uv.lock && git checkout v1.2.6'

# 3. Sync dependencies
sudo -u views-deploy bash -c 'source ~/.profile && cd ~/views-datafactory && uv sync'

# 4. Verify — all three must name the same version.
#    Every path goes inside bash -c: a bare ~ is expanded by YOUR shell
#    before sudo runs, so it reads your home, not views-deploy's.
sudo -u views-deploy bash -c 'cat ~/.views-deploy-tag'
sudo -u views-deploy bash -c 'cd ~/views-datafactory && git describe --tags --exact-match 2>/dev/null || git log --oneline -1'
sudo -u views-deploy bash -c 'ls ~/views-datafactory/.venv/lib/python*/site-packages | grep views_datafactory'
```

A **rollback is a deploy**: same four blocks, previous tag.

## Run the pipeline

```bash
# Normal run (output streams to terminal + logs to file)
sudo -u views-deploy bash -c 'source ~/.profile && cd ~/views-datafactory && bash scripts/refresh_pipeline.sh 2>&1 | tee -a logs/refresh.log'

# Force re-fetch: delete data first, then run normally
# (there is no --force flag; the pipeline skips existing data by default)
```

## Nuke and rebuild

```bash
# Delete all data
sudo -u views-deploy bash -c 'rm -rf ~/views-datafactory/data/*'

# Then run the pipeline with --force (see above)
```

## Verify data

```bash
# Check assembled grid totals
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

| Feature | Expected |
|---------|----------|
| `ged_sb_best` | ~1,956,320 |
| `ged_ns_best` | ~285,346 |
| `ged_os_best` | ~1,232,241 |

The script also prints `ged_sb_count`, `ged_ns_count`, `ged_os_count`
— compare against prior runs rather than a fixed reference value.

## Check health

```bash
# Per-source freshness + export SLO (run after any pipeline run)
sudo -u views-deploy bash -c 'source ~/.profile && cd ~/views-datafactory && uv run python scripts/check_health.py'
```

## Check status

```bash
# Every path goes inside bash -c — see the note in step 4 above.

# Version the server is CONFIGURED to run (intent, not evidence —
# use all three checks in §"Deploy a new version" step 4 to confirm)
sudo -u views-deploy bash -c 'cat ~/.views-deploy-tag'

# Last run duration
sudo -u views-deploy bash -c 'cat ~/views-datafactory/logs/pipeline_duration.json'

# Last failure. The fallback is INSIDE bash -c on purpose: outside it, an
# unreadable path makes `cat` fail and the || branch print "No recent
# failure" — a permission error reported as good news.
sudo -u views-deploy bash -c 'cat ~/views-datafactory/logs/pipeline_failure.json 2>/dev/null || echo "No recent failure"'

# Raw data size
sudo -u views-deploy bash -c 'du -sh ~/views-datafactory/data/raw/*/'

# Zarr metadata (from laptop)
curl -s http://204.168.219.108/grid.zarr/.zattrs | python3 -m json.tool
```

## Troubleshooting

```bash
# "uv: command not found" → you forgot source ~/.profile
# Always start with: source ~/.profile &&

# "Permission denied" → you forgot sudo -u views-deploy
# Always prefix with: sudo -u views-deploy bash -c '...'

# Check if symlinks are intact
sudo -u views-deploy ls -la /srv/views-data/

# Recreate broken zarr symlink
sudo ln -sf /home/views-deploy/views-datafactory/data/assembled/grid.zarr /srv/views-data/grid.zarr
```
