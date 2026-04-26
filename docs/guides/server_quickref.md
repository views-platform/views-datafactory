# Server Quick Reference

Copy-paste commands for the Hetzner server. For explanations, see `server_operations.md`.

```
ssh simmaa_prio@204.168.219.108
```

All commands below assume you are on the server.

---

## Deploy a new version

```bash
# Set version
sudo -u views-deploy bash -c 'source ~/.profile && echo v1.2.6 > ~/.views-deploy-tag'

# Pull and checkout
sudo -u views-deploy bash -c 'source ~/.profile && cd ~/views-datafactory && git fetch --tags && git checkout v1.2.6'

# Sync dependencies
sudo -u views-deploy bash -c 'source ~/.profile && cd ~/views-datafactory && uv sync'
```

## Run the pipeline

```bash
# Normal run (skips existing data)
sudo -u views-deploy bash -c 'source ~/.profile && cd ~/views-datafactory && bash scripts/refresh_pipeline.sh >> logs/refresh.log 2>&1'

# Force re-fetch everything
sudo -u views-deploy bash -c 'source ~/.profile && cd ~/views-datafactory && bash scripts/refresh_pipeline.sh --force >> logs/refresh.log 2>&1'

# Tail the log (in a second terminal)
sudo -u views-deploy tail -f ~/views-datafactory/logs/refresh.log
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

Expected totals (UCDP GED v25.1):

| Feature | Expected |
|---------|----------|
| `ged_sb_best` | ~1,955,000 |
| `ged_sb_count` | ~255,000 |
| `ged_ns_best` | ~285,000 |
| `ged_os_best` | ~1,232,000 |

## Check status

```bash
# Current deployed version
sudo -u views-deploy cat ~/.views-deploy-tag

# Last run duration
sudo -u views-deploy cat ~/views-datafactory/logs/pipeline_duration.json

# Last failure
sudo -u views-deploy cat ~/views-datafactory/logs/pipeline_failure.json 2>/dev/null || echo "No recent failure"

# Raw data size
sudo -u views-deploy du -sh ~/views-datafactory/data/raw/*/

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
