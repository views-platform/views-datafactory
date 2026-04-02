# Hetzner Deployment Guide

Step-by-step instructions for setting up the VIEWS data server.
Follow these in order. Each step builds on the previous one.

Read `data_serving_guide.md` first if you haven't — it explains
what all of this means.

---

## Server Details

| Property | Value |
|----------|-------|
| **Name** | `views-datafactory-00` |
| **IP** | `204.168.219.108` |
| **Location** | Helsinki (eu-central) |
| **Type** | CPX32 (4 vCPU, 8 GB RAM, 160 GB SSD) |
| **OS** | Ubuntu 24.04 |
| **Project** | views-datafactory (Hetzner console) |
| **Backups** | Enabled (daily) |
| **Cost** | ~€12.60/month (server + IPv4 + backups) |
| **SSH** | `ssh root@204.168.219.108` |

---

## Prerequisites

- The `UCDP_API_TOKEN` environment variable (must be in `~/.profile`,
  not `~/.bashrc` — see Phase 4 for why)
- A domain name pointing to the server (e.g., `data.views.uu.se`)
  OR willingness to use the IP address directly (current)

---

## Phase 1: Server setup (one-time)

### 1.0 Server provisioned (DONE)

- Hetzner project: `views-datafactory`
- Server: `views-datafactory-00` at `204.168.219.108`
- SSH key registered: `simon@simon-XPS-15-9530`
- Backups enabled

### 1.1 SSH into the server

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

```bash
# Add to ~/.profile (NOT .bashrc — .bashrc exits early in non-interactive
# shells like cron, making env vars unreachable for automated jobs)
echo 'export UCDP_API_TOKEN="your-token-here"' >> ~/.profile
source ~/.profile
```

---

## Phase 2: Run the pipeline (first time)

### 2.1 Run the full pipeline

```bash
cd ~/views-datafactory
bash scripts/refresh_pipeline.sh
```

This takes 15-30 minutes (harvesting calls the UCDP API with
rate limiting). Watch the output — each step prints PASS or FAIL.

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
    file_server browse

    basicauth {
        views <paste-bcrypt-hash-here>
    }

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
    file_server browse

    basicauth {
        views <paste-bcrypt-hash-here>
    }

    header Access-Control-Allow-Origin *
    header Access-Control-Allow-Methods "GET, HEAD, OPTIONS"
}
```

Upgrade to Option A when a domain name is available.

### 3.5 Start Caddy

```bash
systemctl enable caddy    # Start on boot
systemctl restart caddy   # Start now
systemctl status caddy    # Check it's running
```

### 3.6 Test

```bash
# From the server — should return 401 (auth required)
curl -s -o /dev/null -w "%{http_code}" http://localhost/grid.zarr/.zmetadata

# From the server — should return zarr JSON metadata
curl -s -u views http://localhost/grid.zarr/.zmetadata | head -10

# From your laptop — should return 401
curl -s -o /dev/null -w "%{http_code}" http://204.168.219.108/grid.zarr/.zmetadata

# From your laptop — should return zarr JSON metadata
curl -s -u views http://204.168.219.108/grid.zarr/.zmetadata | head -10
```

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
0 0 21 * * cd /root/views-datafactory && bash scripts/refresh_pipeline.sh >> logs/refresh.log 2>&1
# Note: refresh_pipeline.sh sources ~/.profile (not .bashrc) and adds
# ~/.cargo/bin to PATH. Environment variables like UCDP_API_TOKEN must
# be in ~/.profile, not .bashrc — .bashrc exits early in non-interactive
# shells before reaching env var exports.
```

### 4.3 Verify cron is set

```bash
crontab -l
```

### 4.4 Test manually

```bash
cd ~/views-datafactory
bash scripts/refresh_pipeline.sh >> logs/refresh.log 2>&1
cat logs/refresh.log
```

---

## Phase 5: Set up credentials and verify consumer access

### 5.1 Consumer credential setup (one-time, per machine)

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
| 7. Variables | 6 UCDP + 34 static + 3 admin = 43 |
| 8. Data access | xarray opens store, loads 1 chunk |
| 9. Data sanity | ged_sb_best has plausible non-zero values |
| 10. Parquet | dataframe.parquet downloadable |

The script reads credentials from `~/.netrc` for HTTP checks and
constructs `aiohttp.BasicAuth` for the xarray check.

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
6. **Monitoring** — `check_health.py` reports data freshness

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
**Not yet set up for multiple users.** Current state: root-only.

Before granting a second admin, resolve these (Tier 2 risk register):
- **C-84:** Create `views-deploy` non-root service account for pipeline
- **C-85/C-86:** Replace personal SSH key with repo-scoped deploy key
- **C-87:** Named SSH accounts per person + break-glass emergency account
- **C-88:** Restrict SSH to PRIO/Uppsala VPN IPs (Hetzner firewall)

These are documented in detail in the technical risk register and
follow the PRIO IT head's security recommendations.

---

## Next steps (when ready)

- **Add data consumers:** See access model above — Caddyfile + netrc
- **Add server admins:** Resolve C-84 through C-88 first
- **Get a domain name:** Switch Caddy to Option A for automatic HTTPS
- **Monitor health remotely:** `ssh server 'cd views-datafactory && uv run python scripts/check_health.py --json'`
- **Change update frequency:** Edit the cron schedule (e.g., weekly: `0 3 * * 1`)
- **Verify after pipeline run:** `uv run python scripts/verify_remote.py`
- **Add a query API:** See `data_serving_guide.md` section 9
- **Add MCP:** See `data_serving_guide.md` section 9
