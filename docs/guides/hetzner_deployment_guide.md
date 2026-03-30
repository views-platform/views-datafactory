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

- The `UCDP_API_TOKEN` environment variable
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
# Add to ~/.bashrc so it's always available
echo 'export UCDP_API_TOKEN="your-token-here"' >> ~/.bashrc
source ~/.bashrc
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

Add this line (runs on the 1st of every month at 3 AM):

```
0 3 1 * * cd /root/views-datafactory && bash scripts/refresh_pipeline.sh >> logs/refresh.log 2>&1
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

## Phase 5: Verify consumer access

### For xarray (zarr) consumers

```python
import xarray as xr

# With domain + HTTPS (Option A):
ds = xr.open_zarr(
    "https://data.views.uu.se/grid.zarr",
    storage_options={"auth": ("views", "yourpassword")},
)

# With IP + HTTP (Option B, current setup):
ds = xr.open_zarr(
    "http://204.168.219.108/grid.zarr",
    storage_options={"client_kwargs": {"auth": ("views", "yourpassword")}},
)

# Slice: Ethiopia fatalities 2020
eth = ds["ged_sb_best"].sel(
    time="2020", lat=slice(3, 15), lon=slice(33, 48)
)
print(f"Ethiopia 2020 total: {float(eth.sum()):.0f}")
```

### For pandas (parquet) consumers

```python
import pandas as pd
import requests

# Download with auth
resp = requests.get(
    "http://204.168.219.108/dataframe.parquet",
    auth=("views", "yourpassword"),
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
```

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

## Next steps (when ready)

- **Add more users:** Edit Caddyfile, add more `username hash` lines
- **Monitor health remotely:** `ssh server 'cd views-datafactory && uv run python scripts/check_health.py --json'`
- **Change update frequency:** Edit the cron schedule (e.g., weekly: `0 3 * * 1`)
- **Add a query API:** See `data_serving_guide.md` section 9
- **Add MCP:** See `data_serving_guide.md` section 9
