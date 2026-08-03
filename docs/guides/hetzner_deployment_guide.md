# Hetzner Deployment Guide

Step-by-step instructions for setting up the VIEWS data server.
Follow these in order. Each step builds on the previous one.

Read `data_serving_guide.md` first if you haven't — it explains
what all of this means.

---

## Quick Deploy (updating an existing server)

If the server is already set up and you're just deploying a tag that **already exists**:

> **Cutting the release is not described here any more.** This section used to open with a
> local `git merge development --ff-only` on `main` followed by `git push origin development`.
> **Branch protection has made both of those impossible** since 2026-07-31: `development` and
> `main` require a pull request, admins are not exempt, and force-pushes are refused. The
> commands would fail at the push.
>
> The release ritual — bump, promote, tag, publish, back-merge — lives in
> [`publishing_to_pypi.md`](publishing_to_pypi.md) and **only** there. Do not reinstate a git
> sequence here: two guides describing the same procedure is how they came to contradict each
> other (see #402). This guide owns the **server**, from the deploy tag onwards.

```bash
# 1. SSH into the server (replace <your-user> with your username)
ssh <your-user>@204.168.219.108

# 2. Start tmux (pipeline runs 3-4 hours; SSH will drop without a multiplexer)
tmux new -s deploy

# 3. Deploy and run
sudo -u views-deploy bash -c '
  source ~/.profile
  echo "vX.Y.Z" > ~/.views-deploy-tag
  cd ~/views-datafactory
  git fetch --tags
  git checkout -- uv.lock
  git checkout vX.Y.Z
  uv sync
  bash scripts/refresh_pipeline.sh 2>&1 | tee -a logs/refresh.log
'
```

Pre-flight checks will validate credentials and disk space before
any work starts. Output streams to your terminal and logs to file.
If SSH drops, reconnect and reattach: `tmux attach -t deploy`.
See [How to deploy a new version](#how-to-deploy-a-new-version)
for details, or [How to roll back](#how-to-roll-back) if something
breaks.

**Tip:** To prevent SSH idle disconnects, add to your local `~/.ssh/config`:
```
Host views-datafactory-00
    HostName 204.168.219.108
    User <your-user>
    ServerAliveInterval 60
    ServerAliveCountMax 3
```

Everything below is the full setup guide (one-time, ~1,200 lines).

---

## Server Details

| Property | Value |
|----------|-------|
| **Name** | `views-datafactory-00` |
| **IP** | `204.168.219.108` |
| **Location** | Helsinki (eu-central) |
| **Type** | CPX42 (8 vCPU, 16 GB RAM, 240 GB SSD) |
| **OS** | Ubuntu 24.04 |
| **Project** | views-datafactory (Hetzner console) |
| **Backups** | Enabled (daily) |
| **Cost** | ~€12.60/month (server + IPv4 + backups) |
| **SSH** | `ssh <your-user>@204.168.219.108` (root login disabled) |

---

## Prerequisites

- The `UCDP_API_TOKEN` environment variable (must be in `~/.profile`,
  not `~/.bashrc` — see Phase 4 for why)
- The `ACLED_USERNAME` and `ACLED_PASSWORD` environment variables
  (must be in `~/.profile` — see `credential_setup.md`)
- A domain name pointing to the server (e.g., `data.views.uu.se`)
  OR willingness to use the IP address directly (current)

---

## Phase 1: Server setup (one-time)

### 1.0 Server provisioned (DONE)

- Hetzner project: `views-datafactory`
- Server: `views-datafactory-00` at `204.168.219.108`
- SSH key registered: `<user>@<workstation>`
- Backups enabled

### 1.1 SSH into the server

> **Historical:** Phase 1 was performed as root during initial setup.
> Root login is now disabled — see Phase 6.3. Current access uses
> named accounts (e.g., `ssh <your-user>@204.168.219.108`).

```bash
ssh root@204.168.219.108
```

### 1.2 Update the system

```bash
sudo apt update && sudo apt upgrade -y
```

### 1.3 Install Python and uv

```bash
# Install Python 3.10+
sudo apt install -y python3 python3-pip git

# Install uv (fast Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.cargo/env  # or restart shell
```

### 1.4 Clone the repository

```bash
cd ~
git clone https://github.com/views-platform/views-datafactory.git
cd views-datafactory
```

### 1.5 Install dependencies

```bash
uv sync
```

### 1.6 Set API token

> See [`credential_setup.md`](credential_setup.md) for the full credential management guide and ADR-026 for the architectural decision.

```bash
# Add to ~/.profile (NOT .bashrc — .bashrc exits early in non-interactive
# shells like cron, making env vars unreachable for automated jobs)
echo 'export UCDP_API_TOKEN="your-token-here"' >> ~/.profile
echo 'export ACLED_USERNAME="your-email@example.com"' >> ~/.profile
echo 'export ACLED_PASSWORD="your-password-here"' >> ~/.profile
source ~/.profile
```

---

## Phase 2: Run the pipeline (first time)

### 2.1 Run the full pipeline

```bash
cd ~/views-datafactory
bash scripts/refresh_pipeline.sh
```

This takes 25-45 minutes (harvesting calls external APIs and downloads
large raster files). Watch the output — each step prints PASS or FAIL.

**Note:** The pipeline includes ACLED (8 features), GHS-POP
population data (1 feature), GHS-BUILT-S built-up surface data
(1 feature), V-Dem democracy indicators (22 features), and
SHDI subnational human development indices (4 features).
Pre-flight checks (`scripts/preflight.py`) validate all credentials
before any step runs.

**ACLED API courtesy:** The ACLED harvester fetches data year-by-year.
On monthly cron runs only the current year is fetched (~80 pages).
When redeploying outside the monthly cron (especially after a data
wipe), the full date range is re-fetched (~480 pages across 6 years).
If doing a full re-fetch, email Katayoun at ACLED with a heads-up:
"We're redeploying our data pipeline and will fetch ACLED data in full.
This is a one-time operation, not our regular monthly cron."

**GHS-POP (population):** Downloads 12 GeoTIFF epochs from the EU JRC
(open access, no credentials). First run downloads ~5.3 GB of raster
data (~6 minutes). Subsequent runs cache — existing files are skipped.
The viewpoint step (~5 minutes) aggregates 30-arcsecond pixels to
PRIO-GRID cells and interpolates to monthly. No consolidation layer
(single release R2023A, ADR-029). Ensure at least 8 GB free disk
space before first run.

**GHS-BUILT-S (built-up surface):** Downloads 12 GeoTIFF epochs from
the EU JRC (open access, no credentials). First run downloads ~2 GB of
raster data (~3 minutes). Subsequent runs cache — existing files are
skipped. The viewpoint step (~5 minutes) aggregates 30-arcsecond pixels
to PRIO-GRID cells and interpolates to monthly. No consolidation layer
(single release R2023A, ADR-034). Same disk requirements as GHS-POP.

**V-Dem (democracy indicators):** Downloads V-Dem v16 CSV (~300 MB) from
v-dem.net (open access, CC-BY-SA 4.0, no credentials). The viewpoint
step broadcasts country-year values to PRIO-GRID cells via the GAUL
ISO3 crosswalk and expands annual values to monthly. No consolidation
layer (single annual release, ADR-035). Minimal disk requirements.

**SHDI (subnational human development):** Downloads SHDI data via the
GDL API (requires `GDL_API_TOKEN`). The viewpoint step broadcasts GDL
region-year values to PRIO-GRID cells via the `gdl_to_pgid` crosswalk
and expands annual values to monthly. No consolidation layer (single
periodic release, ADR-036). 4 features: SHDI composite, health index,
education index, income index — all bounded [0, 1].

### 2.2 Verify the output

```bash
# Check the zarr store exists
ls -lh data/assembled/grid.zarr/

# Check the parquet exists
ls -lh data/compiled/dataframe.parquet

# Quick test with Python
uv run python -c "
import xarray as xr
ds = xr.open_zarr('data/assembled/grid.zarr')
print(ds)
print(f'Total fatalities: {float(ds[\"ged_sb_best\"].sum()):.0f}')
"
```

---

## Phase 3: Install and configure Caddy (web server)

### 3.1 Install Caddy

```bash
apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
apt update
apt install caddy
```

### 3.2 Create a data directory for serving

```bash
# Create a directory that Caddy will serve
mkdir -p /srv/views-data

# Symlink the exports into it
ln -sf ~/views-datafactory/data/assembled/grid.zarr /srv/views-data/grid.zarr
ln -sf ~/views-datafactory/data/compiled/dataframe.parquet /srv/views-data/dataframe.parquet
ln -sf ~/views-datafactory/data/status.html /srv/views-data/status.html
```

**Important:** Caddy runs as user `caddy`, so it must be able to traverse
the symlink path. If data lives under `/root/`, you need:
```bash
chmod o+x /root   # Allow traversal only (not read)
```

### 3.3 Generate a password hash

```bash
caddy hash-password
# Type your password twice (plaintext never stored)
# Copy the bcrypt hash output ($2a$14$...)
```

### 3.4 Configure Caddy

Edit `/etc/caddy/Caddyfile`:

**Option A: With a domain name (recommended)**

When a domain points to the server, Caddy auto-provisions a Let's Encrypt
TLS certificate. No manual cert management needed.

```
data.views.uu.se {
    root * /srv/views-data

    @protected not path /status.html
    basicauth @protected {
        views <paste-bcrypt-hash-here>
    }

    file_server browse

    header Access-Control-Allow-Origin *
    header Access-Control-Allow-Methods "GET, HEAD, OPTIONS"
}
```

**Option B: Without a domain name (HTTP only) — current setup**

Without a domain, `tls internal` does not work reliably (Caddy's
internal CA needs a hostname for SNI; raw IPs fail the TLS handshake).
Serve over HTTP instead. Basic auth still protects access — the only
risk is password interception on the wire, acceptable for internal
single-user access.

```
:80 {
    root * /srv/views-data

    # Public pages: status.html is accessible without auth (ADR-038).
    # Add future public pages to this matcher.
    @protected not path /status.html
    basicauth @protected {
        views <paste-bcrypt-hash-here>
    }

    file_server browse

    header Access-Control-Allow-Origin *
    header Access-Control-Allow-Methods "GET, HEAD, OPTIONS"
}
```

The `@protected` matcher exempts `/status.html` from authentication
(ADR-038). Data artifacts (grid.zarr, dataframe.parquet) remain
auth-gated. To add more public pages, extend the matcher:
`@protected not path /status.html /health.html`.

Upgrade to Option A when a domain name is available.

### 3.5 Start Caddy

```bash
systemctl enable caddy    # Start on boot
systemctl restart caddy   # Start now
systemctl status caddy    # Check it's running
```

### 3.6 Test

```bash
# Status page — should return 200 (public, no auth — ADR-038)
curl -s -o /dev/null -w "%{http_code}" http://localhost/status.html

# Data artifacts — should return 401 (auth required)
curl -s -o /dev/null -w "%{http_code}" http://localhost/grid.zarr/.zmetadata

# Data artifacts with auth — should return zarr JSON metadata
curl -s -u views http://localhost/grid.zarr/.zmetadata | head -10

# From your laptop — status page public
curl -s -o /dev/null -w "%{http_code}" http://204.168.219.108/status.html

# From your laptop — data requires auth
curl -s -o /dev/null -w "%{http_code}" http://204.168.219.108/grid.zarr/.zmetadata
```

**Critical:** If the status page returns 401 instead of 200, the
Caddyfile is missing the `@protected not path /status.html` matcher.
If it returns 404, the symlink in step 3.2 is missing or broken —
verify with `ls -la /srv/views-data/status.html`.

---

## Phase 4: Automate monthly updates

### 4.1 Create a log directory

```bash
mkdir -p ~/views-datafactory/logs
```

### 4.2 Add cron job

```bash
crontab -e
```

Add this line (runs on the 21st of every month at midnight UTC):

```
0 0 21 * * cd /home/views-deploy/views-datafactory && bash scripts/refresh_pipeline.sh 2>&1 | tee -a logs/refresh.log
# Note: refresh_pipeline.sh sources ~/.profile (not .bashrc) and adds
# ~/.cargo/bin to PATH. Environment variables like UCDP_API_TOKEN must
# be in ~/.profile, not .bashrc — .bashrc exits early in non-interactive
# shells before reaching env var exports.
```

### 4.3 Add daily status page cron

The pipeline runs monthly, but the status page should refresh daily to
catch staleness. Add a second cron entry (runs at 06:00 UTC every day):

```bash
crontab -e
```

Add this line:

```
0 6 * * * cd /home/views-deploy/views-datafactory && bash -c 'source ~/.profile && uv run python scripts/generate_status.py --output data/status.html' 2>&1 | logger -t views-status
# Output goes to syslog: grep views-status /var/log/syslog
```

The status page is also regenerated after every pipeline run via an EXIT
trap in `refresh_pipeline.sh` — this daily cron catches staleness between
monthly runs.

### 4.4 Verify cron is set

```bash
crontab -l
```

### 4.5 Test manually

```bash
cd ~/views-datafactory
bash scripts/refresh_pipeline.sh 2>&1 | tee -a logs/refresh.log
```

### 4.6 Configure external monitoring (C-131)

The pipeline cron runs silently. If cron dies, the server reboots without
re-enabling cron, or `views-deploy` is deleted, nobody is alerted.
`refresh_pipeline.sh` pings an external monitoring URL on successful
completion (lines 251-254). The operator must create the external check
and set `HEARTBEAT_URL` on the server.

We use [healthchecks.io](https://healthchecks.io) (free tier: 20 checks).
See ADR-018 for the rationale.

#### Create the check

1. Log in to healthchecks.io (credentials in PRIO password manager,
   project: `views-datafactory`)
2. Create a check (or verify the existing one):
   - **Name:** `views-datafactory pipeline refresh`
   - **Period:** 30 days (matches the `0 0 21 * *` cron)
   - **Grace period:** 48 hours (pipeline runs 2-3 hours; 48h covers
     delays, restarts, and weekend non-response)
   - **Tags:** `views`, `datafactory`, `hetzner`
3. Copy the ping URL: `https://hc-ping.com/<uuid>`

#### Set the environment variable

```bash
# Run as a named admin user, not as views-deploy directly
sudo -u views-deploy bash -c 'source ~/.profile && \
  echo "export HEARTBEAT_URL=https://hc-ping.com/<uuid>" >> ~/.profile'
```

Verify:

```bash
sudo -u views-deploy bash -c 'source ~/.profile && echo $HEARTBEAT_URL'
# Expected: https://hc-ping.com/<uuid>
```

The variable must be in `~/.profile`, not `~/.bashrc` — same reason as
`UCDP_API_TOKEN` (cron runs non-interactive shells where `.bashrc` exits
early; see section 4.2 note).

#### How it works

After a successful pipeline run, `refresh_pipeline.sh` does:

```bash
if [ -n "${HEARTBEAT_URL:-}" ]; then
    curl -fsS --max-time 10 "$HEARTBEAT_URL" >/dev/null 2>&1 || true
fi
```

- If `HEARTBEAT_URL` is unset: nothing happens (safe default).
- If the curl fails: the pipeline still succeeds (`|| true`).
- healthchecks.io expects a ping every 30 days. If no ping arrives
  within 30 days + 48 hours grace, it sends an alert.

#### What to do when healthchecks.io alerts

A missed-ping alert means the pipeline did not complete successfully
within the expected window. Check in this order:

1. **SSH to the server** and check if cron ran:
   ```bash
   sudo -u views-deploy bash -c 'cat ~/views-datafactory/logs/refresh.log | tail -50'
   ```
2. **Check the failure sentinel:**
   ```bash
   sudo -u views-deploy bash -c 'cat ~/views-datafactory/logs/pipeline_failure.json 2>/dev/null || echo "No failure sentinel"'
   ```
3. **Check if cron is running:**
   ```bash
   sudo -u views-deploy crontab -l
   systemctl status cron
   ```
4. **Check the status page** — it is generated on every exit (success
   or failure) via the EXIT trap:
   ```bash
   curl -s http://204.168.219.108/status.html | head -20
   ```

If the server is unreachable, check Hetzner Cloud console for the
server status (views-datafactory-00, Helsinki, CPX42).

#### Verify monitoring is working

After the next successful pipeline run (manual or cron on the 21st),
check healthchecks.io — it should show a green status with the ping
timestamp matching the pipeline completion time.

---

## Phase 5: Set up credentials and verify consumer access

### 5.1 Consumer credential setup (one-time, per machine)

> See [`credential_setup.md`](credential_setup.md) for the consolidated credential guide.

All data access uses HTTP basic auth. Credentials are stored in
`~/.netrc` — the standard Unix credential file, read natively by
`curl`, Python `requests`, and the verification script.

**Revocation is server-side:** removing a user's hash from the
Caddyfile immediately blocks their access, regardless of what's
in their `~/.netrc`.

```bash
cat >> ~/.netrc << 'EOF'
machine 204.168.219.108
login views
password yourpassword
EOF
chmod 600 ~/.netrc
```

After this, `curl` and `requests` just work — no credentials in code:
```bash
curl -n http://204.168.219.108/grid.zarr/.zmetadata | head -10
```

**For xarray**, auth requires an `aiohttp.BasicAuth` object in
`storage_options`. A helper function reads `~/.netrc` and constructs
it (see section 5.3 below). This is a 3-line wrapper, not boilerplate
in every script — call it once per session.

#### Adding a new consumer

1. Admin: `caddy hash-password` on server, add `username $hash` to Caddyfile
2. Consumer: add entry to their `~/.netrc`, `chmod 600`
3. No code changes anywhere

### 5.2 Run the automated verification script

```bash
uv run python scripts/verify_remote.py
```

This runs 10 checks against the remote server:

| Check | What it verifies |
|-------|-----------------|
| 1. Connectivity | TCP connection to server port 80 |
| 2. Auth enforcement | Unauthenticated request returns 401 |
| 3. Netrc credentials | `~/.netrc` has entry for server |
| 4. Metadata | `.zmetadata` returns valid JSON |
| 5. Dataset attributes | CRS, resolution, source, feature count |
| 6. Dimensions | 456 months, 360 lat, 720 lon |
| 7. Variables | 6 UCDP + 8 ACLED + 1 GHS-POP + 1 GHS-BUILT-S + 22 V-Dem + 4 SHDI + 34 static + 3 admin = 79 |
| 8. Data access | xarray opens store, loads 1 chunk |
| 9. Data sanity | ged_sb_best has plausible non-zero values |
| 10. Parquet | dataframe.parquet downloadable |

The script reads credentials from `~/.netrc` for HTTP checks and
constructs `aiohttp.BasicAuth` for the xarray check.

After `verify_remote.py` passes, run the data correctness check:

```bash
uv run python scripts/verify_remote_data.py
```

This compares feature sums between the local assembled grid and the remote zarr store at representative time steps. It catches failures where metadata checks pass but the actual data values are wrong (e.g., stale zarr chunks from a partial export). See C-138.

### 5.3 Consumer examples

**xarray (zarr) — reads credentials from ~/.netrc:**

```python
import aiohttp
import xarray as xr
from netrc import netrc
from pathlib import Path

# Read credentials from ~/.netrc (one-time per session)
nrc = netrc(str(Path.home() / ".netrc"))
login, _, password = nrc.authenticators("204.168.219.108")
auth = aiohttp.BasicAuth(login, password)

# Open dataset — only downloads metadata, not data
ds = xr.open_zarr(
    "http://204.168.219.108/grid.zarr",
    storage_options={"client_kwargs": {"auth": auth}},
)

# Slice: Ethiopia fatalities 2020 (downloads ~1 MB, not 19 GB)
eth = ds["ged_sb_best"].sel(
    time="2020", lat=slice(3, 15), lon=slice(33, 48)
)
print(f"Ethiopia 2020 total: {float(eth.sum()):.0f}")
```

**Why the `aiohttp.BasicAuth` wrapper?** xarray uses fsspec, which
uses aiohttp for HTTP. aiohttp requires a `BasicAuth` object, not
a `(user, pass)` tuple. The `netrc` module returns the raw values;
`aiohttp.BasicAuth()` wraps them. This is 3 lines of boilerplate
that could be extracted to a helper if it recurs across scripts.

**pandas (parquet) — via requests (reads ~/.netrc automatically):**

```python
import pandas as pd
import requests

# Auth handled by ~/.netrc — no explicit credentials
resp = requests.get(
    "http://204.168.219.108/dataframe.parquet",
)
with open("dataframe.parquet", "wb") as f:
    f.write(resp.content)
df = pd.read_parquet("dataframe.parquet")
print(df.head())
```

---

## Troubleshooting

**"Connection refused"** — Caddy isn't running.
```bash
sudo systemctl status caddy
sudo journalctl -u caddy --no-pager -n 20
```

**"401 Unauthorized"** — Wrong username or password.
Check the Caddyfile credentials match what you're sending.

**"403 Forbidden"** — Caddy can't read the files. Check that
the `caddy` user can traverse the symlink path (`chmod o+x /root`
if data is under `/root/`).

**"Certificate error"** — If using a domain, DNS must point to
the server. Caddy gets certificates automatically but needs DNS
to be correct. If using IP only, use HTTP (Option B) — `tls internal`
does not work with raw IPs.

**"Pipeline failed"** — Check which step failed in the log:
```bash
tail -50 logs/refresh.log
cat logs/pipeline_failure.json  # machine-readable: step, exit code, timestamp
```

**"Cron job didn't run" or "command not found"** — Cron has a
minimal environment. Three common issues:
1. `uv: command not found` — PATH doesn't include `~/.cargo/bin`.
   Fixed in `refresh_pipeline.sh` (exports PATH explicitly).
2. `PS1: unbound variable` — `.bashrc` references PS1 which is
   unset in cron. Fixed in `refresh_pipeline.sh` (`set +u` around source).
3. `UCDP_API_TOKEN` missing — `.bashrc` exits early in non-interactive
   shells. Put env vars in `~/.profile` instead.

Check cron ran: `grep CRON /var/log/syslog | tail -5`

**"UCDP API timeout"** — The API is occasionally slow. The
harvester has built-in retry (3 attempts with exponential
backoff). If it still fails, try again later.

**"Disk full"** — The full data pipeline needs about 35 GB.
Check with `df -h`.

**"OOM killed" (exit code 137)** — A pipeline step exceeded
physical RAM. The CPX42 has 16 GB RAM + 16 GB swap. See the
Swap Configuration section in `server_operations.md` for setup
instructions.

---

## What you've built

After completing all phases, you have:

1. **A server** (Hetzner) running 24/7
2. **A web server** (Caddy) serving data over HTTP (HTTPS when domain assigned)
3. **Authentication** (basic auth) controlling access
4. **Two consumer formats:**
   - Zarr store — lazy loading, subset access, xarray interface
   - Parquet file — full download, pandas interface
5. **Monthly refresh** — cron job runs the pipeline automatically
6. **Monitoring** — `check_health.py` reports data freshness; healthchecks.io alerts on missed pipeline runs (section 4.6)

Consumers access the data with:
```python
# Zarr (subsets, lazy loading)
ds = xr.open_zarr("http://204.168.219.108/grid.zarr", ...)

# Parquet (full download)
df = pd.read_parquet("http://204.168.219.108/dataframe.parquet")
```

---

## Access model

The system has two distinct access layers:

### Data consumers (HTTP basic auth)

Anyone who needs to read zarr or parquet data. Current setup:

- **Auth method:** Caddy basic auth (`~/.netrc` on client side)
- **Current credentials:** Single shared `views` account
- **Adding a consumer:** (1) Generate hash: `caddy hash-password` on server,
  (2) Add `username $hash` line to Caddyfile, (3) Consumer adds entry to
  their `~/.netrc`
- **Revoking access:** Remove the user's line from the Caddyfile

No server SSH access needed. No code changes needed per consumer.

### Server administrators (SSH)

People who maintain the pipeline, debug failures, or update code.
See **Phase 6: Server hardening** below for the multi-user setup.

---

## Deployment and releases

This section explains how the server decides which version of the
code to run, how to deploy a new version, and how to roll back if
something goes wrong.

### What is a git tag?

A git **tag** is a permanent bookmark on a specific commit. Think of
it as a named snapshot: `v1.0.0` always points to exactly the same
code, forever. Unlike a **branch** (which moves forward every time
someone pushes a new commit), a tag never moves.

When we say "deploy v1.1.0", we mean: run the code that was frozen
at the moment we created the `v1.1.0` tag. Even if 100 more commits
are pushed to main after that, `v1.1.0` still points to the original
code.

### What is "detached HEAD"?

When you check out a tag on the server, git will say:

```
HEAD is now at 9fc36ce Merge PR #6: ...
```

And `git branch` will show:

```
* (HEAD detached at v1.1.0)
  development
  main
```

**This is normal and expected.** It means the server is looking at
a frozen snapshot (the tag), not a moving branch. Nothing is broken.
You are not "on" any branch — you are on a specific tagged release.

This is exactly what we want: the server runs a known, tested version,
not whatever happens to be at the tip of a branch.

### How the deployment gate works

`refresh_pipeline.sh` has a **deployment gate** at the top of the
script. Before running any pipeline steps, it:

1. Reads the file `~/.views-deploy-tag` (contains a tag name, e.g., `v1.1.0`)
2. Runs `git fetch --tags` to download any new tags from GitHub
3. Checks that the tag exists
4. Runs `git checkout v1.1.0` to switch to that exact version
5. Then runs the 14 pipeline steps (pre-flight, harvest, consolidate, viewpoint, compile UCDP, compile ACLED, compile GHS-POP, compile GHS-BUILT-S, compile V-Dem, compile SHDI, assemble, export, health check, verify remote data)

If the `.views-deploy-tag` file is missing, empty, or contains a tag
that doesn't exist, the script prints `FATAL` and stops immediately.
It will never run an unknown version. This is the "fail-loud" principle
(ADR-011): crash visibly rather than run the wrong code silently.

### Terminology: bump vs tag

**Bump** and **tag** are two separate operations that happen in a
fixed order:

1. **Bump** = changing `version` in `pyproject.toml` (e.g. `1.3.0`
   → `1.4.0`). This is a normal code change: feature branch → PR →
   merge to `development`. It happens during development, well before
   deployment.

2. **Promote** = a pull request from `development` into `main`, merged
   as a **merge commit**. This is the release ceremony; `main` only
   moves forward at release time. It used to be a local fast-forward,
   which is why older text here said "fast-forward" — branch protection
   ended that in 2026-07-31 (see the note under Quick Deploy).

3. **Tag** = `git tag vX.Y.Z` on the merge commit on `main`. This
   is a git label, not a code change. The version in `pyproject.toml`
   and the tag name must agree (`version = "1.4.0"` → `v1.4.0`).

4. **Back-merge** = a pull request from `main` back into `development`,
   also a merge commit. The promotion in step 2 leaves one commit on
   `main` that is not on `development`; without this step the branches
   diverge a little further after **every** release, and
   `git log main..development` starts counting work that already shipped.

5. **Deploy** = update `~/.views-deploy-tag` on the server to the
   new tag. The pipeline checks out whatever tag that file contains.

**Why this order:** If you tag before bumping, the tag points at code
with the old version string — wrong. If you tag on `development`
instead of `main`, the canonical release branch falls behind. Bump
first, promote second, tag third, back-merge fourth.

### How to deploy a new version

**On your laptop:** follow the release ritual in
[`publishing_to_pypi.md`](publishing_to_pypi.md) — bump, promote, tag, publish, back-merge.

> The git sequence that used to sit here (`git merge development --ff-only`,
> `git push origin development`) **cannot be executed any more.** Both branches require a
> pull request, admins included, and force-pushes are refused. It is deleted rather than
> corrected, because a second copy of the procedure is what let the two guides drift apart
> in the first place (#402). One procedure, one home.

**On the server** (SSH in):

```bash
# Update the deploy tag file
echo 'vX.Y.Z' > ~/.views-deploy-tag
```

That's it. The next cron run (21st of the month) will automatically
use the new tag. If you want to apply it right now instead of waiting:

```bash
# Run the pipeline manually (same command cron uses)
cd ~/views-datafactory
bash scripts/refresh_pipeline.sh 2>&1 | tee -a logs/refresh.log
```

### How to roll back

If a new version breaks the pipeline:

```bash
# On the server — point back to the previous version
echo 'vPREVIOUS' > ~/.views-deploy-tag
```

The next pipeline run will check out that tag and run its code
instead. The old version is always available — git never deletes tags.

You can also run the pipeline manually to roll back immediately
instead of waiting for the next cron run.

### How to check what version is deployed

```bash
# What version is the server configured to run?
cat ~/.views-deploy-tag

# What version is actually checked out right now?
git describe --tags --exact-match 2>/dev/null || git log --oneline -1

# When did the last pipeline run happen?
tail -5 logs/refresh.log
```

### Log rotation

`/etc/logrotate.d/views-datafactory` rotates `logs/refresh.log` **monthly**, keeps 12, compresses,
and re-creates the file `0640 views-deploy:views-deploy`.

Two lines in it are load-bearing and should not be "tidied away":

- **`su views-deploy views-deploy`** — logrotate refuses to touch files in a directory it does not
  own. Without this it fails rather than rotates.
- **No `missingok`** — deliberately absent. That option is why the previous config, which pointed at
  `/root/views-datafactory/logs/refresh.log` after the pipeline had moved to the service account,
  exited successfully every night for four months while rotating nothing (C-330). A wrong path
  should be loud.

Check it without changing anything:

```bash
sudo logrotate --debug /etc/logrotate.d/views-datafactory
```

`Handling 1 logs` and the correct path in the `rotating pattern:` line mean it is working.

### What happens if the pipeline fails

The script has an error trap. If any step fails:

1. A file `logs/pipeline_failure.json` is written with the step name,
   exit code, and timestamp
2. The console/log shows `PIPELINE FAILED at step: <name>`
3. If `ALERT_EMAIL` is set and `mail` is installed, an email is sent

**Data is never corrupted by a failure.** The old data from the
previous month stays in place. Consumers continue to see the last
successful export. The data becomes *stale* (one month behind) but
not *wrong*.

To investigate: `cat logs/pipeline_failure.json` and
`tail -100 logs/refresh.log`.

### Cron timing

The cron job runs on the **21st of every month at midnight UTC**.
Changes to `~/.views-deploy-tag` take effect on the next cron run.
They do NOT take effect immediately — cron only runs at the
scheduled time.

To apply a version change immediately, run the pipeline manually
(see "How to deploy a new version" above).

### Version history

| Tag | Date | What changed |
|-----|------|-------------|
| `v1.0.0` | 2026-04-02 | First production release |
| `v1.1.0` | 2026-04-06 | Deployment gate, Registry[T], 411 tests, server hardening docs |
| `v1.2.0`–`v1.2.10` | 2026-04 | ACLED harvester, compilation, grid verification, assembly integration |
| `v1.2.11` | 2026-05 | Source registry, pre-flight checks, deployment hardening |

For a complete list: `git tag -l 'v*' --sort=-version:refname`

### Why this design?

See **ADR-022** for the full rationale, alternatives considered
(branch tracking, Docker, CI/CD, systemd), and DDIA references.
The short version: the server should run a known, tested version —
never whatever happens to be at the tip of a branch.

---

## Phase 6: Server hardening (before 2nd user access)

Resolves C-84 through C-88. Follow PRIO IT security guidance.
All commands run as `root` on the Hetzner server.

### 6.1 Create service account (C-84)

#### What `views-deploy` IS

A non-root Unix user dedicated to running the data pipeline. It owns:

- `/home/views-deploy/views-datafactory/` — the repository clone (code + scripts)
- `/home/views-deploy/views-datafactory/data/` — all harvested, consolidated, compiled, and exported data (~35 GB)
- `/home/views-deploy/views-datafactory/logs/` — pipeline execution logs
- `/home/views-deploy/.views-deploy-tag` — the deployment gate file (ADR-022)
- `/home/views-deploy/.profile` — environment variables (UCDP_API_TOKEN, ACLED_USERNAME, ACLED_PASSWORD)
- `/home/views-deploy/.ssh/id_ed25519` — repo-scoped deploy key (Phase 6.2)

The pipeline cron job runs as `views-deploy`. The `refresh_pipeline.sh` script uses `$HOME` throughout, so all paths resolve to `/home/views-deploy/` automatically.

#### What `views-deploy` CANNOT do

- **Cannot install packages.** Not in the sudo group. `apt install`, `pip install --system`, and `uv tool install --global` all fail with permission denied.
- **Cannot modify system configuration.** `/etc/caddy/Caddyfile`, `/etc/ssh/sshd_config`, and firewall rules are owned by root. `views-deploy` cannot change how the server serves data or accepts connections.
- **Cannot read other users' files.** `/root/` has permissions `drwx------` (700). Other named accounts' homes are similarly restricted. `views-deploy` cannot access SSH keys, credentials, or data belonging to other accounts.
- **Cannot push to GitHub.** The deploy key (Phase 6.2) is registered as read-only on the `views-platform/views-datafactory` repository. `git push` fails. The account can only `git fetch --tags` and `git checkout`.
- **Cannot escalate privileges.** Not in the sudo group, not in the admin group, no SUID binaries, no sudoers entry.

#### Why `views-deploy` exists

**1. Blast radius limitation.** A bug in a pipeline script — or a compromised dependency — can write, delete, and execute anything the running user can. As `root`, that means the entire operating system. As `views-deploy`, damage is confined to `/home/views-deploy/`. The OS, Caddy, SSH config, and other users' data are untouched.

**2. Credential isolation.** The current setup has Simon's personal GitHub SSH key on the server. Anyone with root access can use that key to push to any repository on Simon's account, read private repos, and impersonate Simon on GitHub. The `views-deploy` account uses a repo-scoped deploy key that can only read this one repository.

**3. Audit trail.** System logs show which user performed an action. With only `root`, all actions appear as "root." With `views-deploy` + named accounts, pipeline operations are attributed to `views-deploy`, and administrative actions to the specific human who performed them.

**4. Least privilege (principle of minimal authority).** The pipeline needs exactly three capabilities: (a) read/write files in the data directory, (b) make HTTP requests to UCDP/PRIO-GRID APIs, and (c) fetch git tags. It does not need to install packages, change firewall rules, or modify the web server. `views-deploy` has exactly the first three and none of the rest.

**5. Multi-user safety.** When a second researcher gets server access, they get their own named account (Phase 6.3). They can `sudo` for system administration and `su views-deploy` for pipeline operations. They cannot accidentally break the pipeline by modifying files as their own user, and the pipeline cannot accidentally break their work.

#### Permission model

```
root (system administration only — never for routine operations)
├── /etc/caddy/Caddyfile       — web server configuration
├── /etc/ssh/sshd_config       — SSH daemon configuration
├── Package management (apt)   — system packages
└── Firewall (ufw / Hetzner)   — network access control

views-deploy (pipeline operations — non-interactive, no sudo)
├── ~/views-datafactory/       — repository clone + all data
├── ~/.views-deploy-tag        — deployment gate (which tag to run)
├── ~/.ssh/id_ed25519          — deploy key (read-only, repo-scoped)
├── ~/.profile                 — UCDP_API_TOKEN
├── ~/.cargo/bin/uv            — Python tool manager
└── crontab                    — monthly pipeline refresh

caddy (web server — systemd-managed, runs as 'caddy' user)
├── Reads /srv/views-data/     — static file serving root
│   ├── grid.zarr → /home/views-deploy/.../data/assembled/grid.zarr
│   └── dataframe.parquet → /home/views-deploy/.../data/compiled/...
└── Traverses /home/views-deploy/ (requires o+x permission)

simon, <colleague> (human operators — named accounts with sudo)
├── SSH access with personal keys
├── sudo for system administration
└── su views-deploy (or sudo -u views-deploy) for pipeline operations
```

#### Step-by-step procedure

All commands run as `root` on the Hetzner server.

```bash
# ── Step 1: Create the user ──
# -m creates a home directory at /home/views-deploy
# -s /bin/bash gives the account a login shell (needed for cron, su)
# No password is set — the account cannot be used for SSH login directly.
# Operators access it via: su - views-deploy (from a named account)
useradd -m -s /bin/bash views-deploy

# ── Step 2: Copy the repository ──
# rsync copies the repo with correct permissions and symlinks.
# --exclude='data/' because data is ~35 GB — we move it instead of copying.
rsync -a --exclude='data/' /root/views-datafactory/ /home/views-deploy/views-datafactory/

# ── Step 3: Move the data directory ──
# mv is atomic on the same filesystem — no duplication, no data loss.
# This transfers ownership of the ~35 GB data directory in one operation.
mv /root/views-datafactory/data /home/views-deploy/views-datafactory/data

# ── Step 4: Set ownership ──
# Everything under the service account's home must be owned by it.
# -R is recursive. This covers code, data, logs, provenance, everything.
chown -R views-deploy:views-deploy /home/views-deploy/views-datafactory

# ── Step 5: Install uv ──
# The pipeline uses uv to manage Python dependencies and run scripts.
# This installs uv to /home/views-deploy/.cargo/bin/uv.
# refresh_pipeline.sh adds $HOME/.cargo/bin to PATH (line 47).
su - views-deploy -c "curl -LsSf https://astral.sh/uv/install.sh | sh"

# ── Step 6: Copy environment variables ──
# UCDP_API_TOKEN and ACLED credentials are required by harvester scripts.
# We put them in .profile (not .bashrc) because cron runs non-interactive
# shells where .bashrc exits early when PS1 is unset.
# refresh_pipeline.sh sources $HOME/.profile explicitly (lines 52-55).
# IMPORTANT: Replace values with actual credentials.
echo 'export UCDP_API_TOKEN="<token>"' >> /home/views-deploy/.profile
echo 'export ACLED_USERNAME="<email>"' >> /home/views-deploy/.profile
echo 'export ACLED_PASSWORD="<password>"' >> /home/views-deploy/.profile

# ── Step 7: Copy the deployment gate file ──
# ~/.views-deploy-tag tells refresh_pipeline.sh which git tag to run.
# Without this file, the pipeline refuses to start (ADR-022).
# The file must be owned by views-deploy so operators can update it
# via: sudo -u views-deploy sh -c 'echo "v1.2.0" > ~/.views-deploy-tag'
cp /root/.views-deploy-tag /home/views-deploy/.views-deploy-tag
chown views-deploy:views-deploy /home/views-deploy/.views-deploy-tag

# ── Step 8: Update Caddy symlinks ──
# Caddy serves data from /srv/views-data/ which contains symlinks.
# These symlinks currently point to /root/views-datafactory/data/...
# We update them to point to /home/views-deploy/views-datafactory/data/...
# -sf overwrites the old symlink atomically.
ln -sf /home/views-deploy/views-datafactory/data/assembled/grid.zarr /srv/views-data/grid.zarr
ln -sf /home/views-deploy/views-datafactory/data/compiled/dataframe.parquet /srv/views-data/dataframe.parquet
ln -sf /home/views-deploy/views-datafactory/data/status.html /srv/views-data/status.html

# Caddy runs as the 'caddy' user. To follow the symlinks, it must be
# able to traverse /home/views-deploy/ (execute permission on directory).
# o+x grants "others" execute-only — they can cd through the directory
# but cannot list its contents (no o+r). This is the minimum permission
# Caddy needs to resolve symlink paths.
chmod o+x /home/views-deploy

# ── Step 9: Migrate the cron job ──
# The pipeline cron currently runs in root's crontab.
# We move it to views-deploy's crontab so it runs as the service account.
# $HOME in refresh_pipeline.sh will now resolve to /home/views-deploy.

# Add to views-deploy's crontab:
crontab -u views-deploy -l 2>/dev/null | {
    cat
    echo "0 0 21 * * cd /home/views-deploy/views-datafactory && bash scripts/refresh_pipeline.sh 2>&1 | tee -a logs/refresh.log"
    echo "0 6 * * * cd /home/views-deploy/views-datafactory && bash -c 'source ~/.profile && uv run python scripts/generate_status.py --output data/status.html' 2>&1 | logger -t views-status"
} | crontab -u views-deploy -

# Remove from root's crontab:
# Open root's crontab and delete the pipeline line.
crontab -e
# Delete the line containing refresh_pipeline.sh, save, and exit.
```

#### Verification

After completing all steps, verify the migration:

```bash
# 1. Pipeline runs as views-deploy
su - views-deploy -c "cd views-datafactory && uv run pytest"
# Expected: all tests pass (currently ~1157)

# 2. Cron is in views-deploy's crontab
crontab -u views-deploy -l | grep refresh_pipeline
# Expected: shows the cron entry

# 3. Root crontab does NOT have the pipeline
crontab -l | grep refresh_pipeline
# Expected: no output (empty grep)

# 4. Deploy tag file is accessible
su - views-deploy -c "cat ~/.views-deploy-tag"
# Expected: v1.1.0 (or current tag)

# 5. Data serving still works
uv run python scripts/verify_remote.py
# Expected: 10/10 checks pass

# 6. views-deploy cannot sudo
su - views-deploy -c "sudo ls /"
# Expected: permission denied (not in sudo group)

# 7. Automated verification (run on server)
python3 scripts/verify_server_hardening.py
# Expected: all checks pass
```

#### Rollback

If anything goes wrong, revert in 3 commands:

```bash
# Move data back to root
mv /home/views-deploy/views-datafactory/data /root/views-datafactory/data

# Restore symlinks to root's paths
ln -sf /root/views-datafactory/data/assembled/grid.zarr /srv/views-data/grid.zarr
ln -sf /root/views-datafactory/data/compiled/dataframe.parquet /srv/views-data/dataframe.parquet
ln -sf /root/views-datafactory/data/status.html /srv/views-data/status.html

# Restore root's cron
crontab -e  # Re-add the pipeline line
```

The service account can be removed later with `userdel -r views-deploy`.

### 6.2 Deploy key for GitHub (C-85, C-86)

#### What a deploy key IS

An SSH key pair registered on a single GitHub repository. The server
holds the private key; GitHub holds the matching public key. When
the server runs `git fetch`, SSH presents the private key. GitHub
checks it against registered deploy keys and grants access to that
one repo only.

| Property | Personal SSH key (before) | Deploy key (after) |
|----------|-------------------------|--------------------|
| Scope | All repos the person can access | This one repo only |
| Write access | Yes (push, delete branches) | No (read-only) |
| Identity | A human (Simon) | A machine (views-datafactory-00) |
| Stored at | `/root/.ssh/id_ed25519` | `/home/views-deploy/.ssh/id_ed25519` |
| If compromised | All repos exposed | One repo, read-only, revoke in 30s |

The pipeline needs exactly two git operations: `git fetch --tags`
(download tag list) and `git checkout v1.1.0` (switch to a release).
Both are read-only. The deploy key grants exactly this.

#### Why it replaces the personal key

The personal SSH key at `/root/.ssh/id_ed25519` is registered on
Simon's GitHub account. Anyone with root access can use it to push
to any repository Simon has write access to, read private repos,
and impersonate Simon. The deploy key eliminates this risk: it is
repo-scoped, read-only, and owned by the service account.

#### Prerequisite: GitHub org policy

Deploy keys may be disabled at the organization level. Before
proceeding, verify the setting:

1. Go to `https://github.com/organizations/views-platform/settings/member_privileges`
2. Find **"Deploy keys"** section
3. Ensure **"Enabled"** is selected
4. Click **Save** if changed

You need **org owner** permissions for this. If "Disabled" and you
cannot change it, ask an org admin. Without this, the repo settings
page will show "Disabled by views-platform" and the "Add deploy key"
button will be absent.

#### Step-by-step procedure

```bash
# ── Step 1: Generate the key pair ──
# Run as views-deploy (the service account).
# -t ed25519: modern, fast, small key.
# -C: comment field — a human-readable label baked into the public
#     key so you can tell keys apart. Not used for authentication.
# -f: output path. Goes in views-deploy's .ssh, not root's.
# -N "": empty passphrase. The pipeline runs unattended via cron —
#        there is nobody to type a passphrase at 00:00 on the 21st.
su - views-deploy
ssh-keygen -t ed25519 -C "views-deploy@views-datafactory-00" -f ~/.ssh/id_ed25519 -N ""

# ── Step 2: Copy the public key ──
# This is the key you paste into GitHub. The private key (without .pub)
# NEVER leaves the server.
cat ~/.ssh/id_ed25519.pub
exit
```

Copy the output line (starts with `ssh-ed25519 AAAA...`).

```
# ── Step 3: Register on GitHub (web UI) ──
```

1. Go to `https://github.com/views-platform/views-datafactory/settings/keys`
2. Click **"Add deploy key"**
3. Title: `views-datafactory-00 (views-deploy)`
4. Key: paste the public key from Step 2
5. **Leave "Allow write access" UNCHECKED** — the server only needs
   read access. Checking this would allow the service account to push
   code, which violates least privilege.
6. Click **"Add key"**

```bash
# ── Step 4: Test SSH authentication ──
# First connection to github.com will prompt to accept the host
# fingerprint. Type "yes". GitHub's ED25519 fingerprint is:
# SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU
# (documented at docs.github.com/en/authentication)
su - views-deploy -c "ssh -T git@github.com"
# Expected: "Hi views-platform/views-datafactory! You've
# successfully authenticated, but GitHub does not provide
# shell access."
#
# If it says "Hi <username>!" instead, the personal key is
# being used — check ~/.ssh/config or key ordering.

# ── Step 5: Test git operations ──
su - views-deploy -c "cd views-datafactory && git fetch --tags && git tag -l 'v*' | tail -3"
# Expected: lists the latest tags (e.g., v1.0.0, v1.1.0).

# ── Step 6: Remove the personal key from root ──
# ONLY after Steps 4-5 succeed. This is irreversible — if the
# deploy key doesn't work, you'll lose git access to the server.
rm /root/.ssh/id_ed25519 /root/.ssh/id_ed25519.pub
```

#### Verification

```bash
python3 /home/views-deploy/views-datafactory/scripts/verify_server_hardening.py
# Expected: 21/21 checks pass
# Check 20: "Personal SSH key removed from /root — removed"
# Check 21: "Deploy key exists for service user"
```

#### Revocation

If the server is compromised:
1. Go to `https://github.com/views-platform/views-datafactory/settings/keys`
2. Click **"Delete"** next to the deploy key
3. The key is dead instantly — no token rotation, no credential
   propagation, no other repos affected

### 6.3 Named user accounts (C-87)

#### What named user accounts ARE

Per-human Unix accounts on the server. Each account belongs to one person:
- Owns their own home directory (`/home/<username>/`)
- Has their own SSH key for login
- Has their own password for `sudo`
- Has their own audit trail in system logs

These are distinct from `views-deploy` (the pipeline service account)
and from `root` (the system administrator account, which we will
eventually disable for SSH).

#### What named accounts CANNOT do

Without `sudo`, a named account:
- Cannot read other users' home directories (700 perms enforce this)
- Cannot modify `/etc/` (system config)
- Cannot restart services (Caddy, sshd, cron)
- Cannot impersonate `views-deploy` (must use `sudo su - views-deploy` or `sudo -u views-deploy`)

With `sudo`, the account can do everything root can — but every
sudo invocation is logged with the human's username, providing
the audit trail that shared `root` lacks.

#### Why each admin needs BOTH a key AND a password

This is the most common mistake. The two are separate authentication
paths for different purposes:

| Auth path | Used for | Required |
|-----------|----------|----------|
| **SSH key** | Logging into the server | Yes (no password prompt at SSH) |
| **Password** | Running `sudo` | Yes (`sudo` always requires a password, even after key-based SSH) |

If you set up only the SSH key (which is what `useradd -m` produces),
the user can SSH in but `sudo` fails with "no password set". The
account is functionally crippled — they can read files but not
administer anything.

`useradd -m` creates an account in **locked** state (`passwd -S`
shows `L`). You must set a password explicitly with `chpasswd` or
`passwd`. The break-glass `emergency` account in this guide uses
`passwd`; admin accounts should use the safer flow below.

#### Why named accounts exist

1. **Audit trail** — system logs show *who* did what. With shared
   `root`, every action is "root did it." With named accounts, you
   know which human ran every sudo command.
2. **Personal credentials** — each user manages their own SSH key
   and password independently. No shared secret.
3. **Revocation simplicity** — `userdel <username>` removes one
   person's access without affecting anyone else.
4. **Sudo accountability** — `/var/log/auth.log` records each sudo
   invocation by username, command, and timestamp.

#### Step-by-step procedure

You need three things from the new user before starting:
1. **Preferred username** (lowercase, e.g., `firstname` or `firstname_org`)
2. **SSH public key** (their `cat ~/.ssh/id_ed25519.pub` output)
3. **Whether they need sudo** (admin access) or pipeline-only

Then on the server as `root`:

```bash
# ── Step 1: Create the user ──
# -m creates /home/<username>
# -s /bin/bash gives a login shell
useradd -m -s /bin/bash <username>

# ── Step 2: Grant sudo (if they need admin access) ──
# Adds the user to the 'sudo' group (Debian/Ubuntu).
# Skip this if they only need pipeline operations via su views-deploy.
usermod -aG sudo <username>

# ── Step 3: Install their SSH public key ──
# Permissions matter. SSH refuses to read .ssh if it's world-readable.
# 700 on the directory, 600 on authorized_keys.
mkdir -p /home/<username>/.ssh
echo "<their-public-key>" > /home/<username>/.ssh/authorized_keys
chmod 700 /home/<username>/.ssh
chmod 600 /home/<username>/.ssh/authorized_keys
chown -R <username>:<username> /home/<username>/.ssh

# ── Step 4: Set a temporary password and force first-login change ──
# REQUIRED for sudo to work. Without this, the account is locked
# (passwd -S shows 'L'). SSH login still works via key, but sudo
# fails with "no password set".
#
# We use a generated random temp password + chage -d 0 to force
# the user to change it on first authentication. This avoids:
#   - sending the user our chosen password (weak credential reuse)
#   - asking the user for a password we then know (we shouldn't)
#   - leaving the temp password valid for any meaningful time
TEMP_PW=$(openssl rand -base64 18)
echo "Temp password: $TEMP_PW"  # send to user via Slack DM
echo "<username>:$TEMP_PW" | chpasswd
chage -d 0 <username>  # forces change on next auth
unset TEMP_PW  # don't leave it in the shell environment
```

#### Credential delivery (the temp password)

The temp password from Step 4 must be delivered to the user
**out-of-band** — not in the same channel you use for code.

| Channel | Acceptable? |
|---------|-------------|
| Slack DM | Yes |
| Signal | Yes |
| Password manager share | Yes (best) |
| Email | **No** (logged, archived, often unencrypted) |
| Public Slack channel | **No** |
| Issue tracker / git commit | **No** (permanent record) |

The password is single-use: `chage -d 0` forces the user to change
it on first authentication. Within minutes of delivery, the temp
password is dead.

#### What the new user does

Send them this checklist:

```bash
# 1. SSH to the server (uses your key — no password prompt)
ssh <username>@204.168.219.108

# 2. The system will say:
#    "You are required to change your password immediately"
#    (current) UNIX password: ← type the temp password from Slack
#    New password:            ← choose your real password
#    Retype new password:     ← confirm
#
# 3. SSH will close the connection after the password change.
#    This is normal — the auth stage finished but no shell opened.
#    SSH back in (no password prompt this time, key-based auth):
ssh <username>@204.168.219.108

# 4. Test sudo
sudo whoami
# Expected: "root" (sudo will prompt for your new password the first time)

# 5. Test pipeline operations as views-deploy
sudo su - views-deploy
cd views-datafactory
uv run pytest --co -q | tail -3
exit  # back to your own shell
```

#### Verify on the server (as admin)

After the user confirms their access works:

```bash
ssh <your-user>@204.168.219.108 "sudo passwd -S <username>"
# Expected output:
#   <username> P <today's date> 0 99999 7 -1
# The 'P' means password is set (not 'L' = locked).
# The date is when the user changed it (should be today).
```

Or run the automated check:

```bash
python3 /home/views-deploy/views-datafactory/scripts/verify_server_hardening.py
# Looks for named accounts with sudo, verifies each has a password
# and an authorized_keys file.
```

#### Break-glass emergency account

In addition to per-human accounts, create one shared `emergency`
account whose password is stored in the PRIO password manager. This
is the "break the glass" account used only when normal admin
accounts are inaccessible (forgot password, key lost, etc.).

```bash
useradd -m -s /bin/bash emergency
usermod -aG sudo emergency
passwd emergency  # interactive — type a strong password
# Store the password in PRIO password manager, NOT in a file.
```

#### Disabling root SSH login

After at least one named admin account is verified working, disable
root SSH:

```bash
# DO NOT RUN until a named account has been verified end-to-end:
#   - SSH login works
#   - Password change worked (passwd -S shows 'P')
#   - sudo whoami returns "root"
#
# Test from a SECOND SSH session before disabling. If something
# is wrong with sshd_config, you don't want to lose your only
# way in.
sed -i 's/^PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
systemctl restart sshd
```

If you disable root SSH before verifying the named account works,
you may lock yourself out and need Hetzner console access to recover.

### 6.4 SSH IP restriction (C-88)

Restrict SSH to PRIO and Uppsala VPN IP ranges via Hetzner firewall:

**Option A: Hetzner Cloud Firewall (recommended)**

1. Hetzner Console → Firewalls → Create Firewall
2. Name: `views-datafactory-ssh`
3. Inbound rules:
   - SSH (port 22): Allow from PRIO VPN range (get from IT)
   - SSH (port 22): Allow from Uppsala VPN range (get from IT)
   - HTTP (port 80): Allow from any (data consumers)
   - HTTPS (port 443): Allow from any (for when domain is added)
4. Apply to server `views-datafactory-00`

**Option B: ufw on the server (fallback)**

```bash
ufw allow from <prio-vpn-cidr> to any port 22
ufw allow from <uppsala-vpn-cidr> to any port 22
ufw allow 80/tcp    # HTTP for data consumers
ufw allow 443/tcp   # HTTPS for future domain
ufw default deny incoming
ufw enable
```

**Get the IP ranges from PRIO IT before configuring.** Test SSH from
a whitelisted IP before applying the deny-all default.

### 6.5 Verification checklist

After completing all hardening steps:

- [ ] Pipeline runs as `views-deploy`, not root
- [ ] `crontab -u views-deploy -l` shows the monthly cron
- [ ] `ssh -T git@github.com` works as `views-deploy` (deploy key)
- [ ] `/root/.ssh/id_ed25519` no longer exists (personal key removed)
- [ ] Named accounts can SSH and sudo
- [ ] Root SSH login disabled (`PermitRootLogin no`)
- [ ] Break-glass `emergency` account works
- [ ] SSH from non-whitelisted IP is blocked
- [ ] `verify_remote.py` passes 10/10 (data serving unaffected)
- [ ] `verify_remote_data.py` passes all feature sum comparisons (C-138)
- [ ] `cat /home/views-deploy/.views-deploy-tag` returns the current deploy tag

---

## Next steps (when ready)

- **Add data consumers:** See access model above — Caddyfile + netrc
- **Get a domain name:** Switch Caddy to Option A for automatic HTTPS
- **Monitor health remotely:** `ssh server 'cd views-datafactory && uv run python scripts/check_health.py --json'`
- **Change update frequency:** Edit the cron schedule (e.g., weekly: `0 3 * * 1`)
- **Verify after pipeline run:** `uv run python scripts/verify_remote.py` (metadata) and `uv run python scripts/verify_remote_data.py` (data correctness)
- **Add a query API:** See `data_serving_guide.md` section 9
- **Add MCP:** See `data_serving_guide.md` section 9
