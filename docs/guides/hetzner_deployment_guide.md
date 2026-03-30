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
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy
```

### 3.2 Create a data directory for serving

```bash
# Create a directory that Caddy will serve
sudo mkdir -p /srv/views-data

# Symlink the exports into it
sudo ln -s ~/views-datafactory/data/assembled/grid.zarr /srv/views-data/grid.zarr
sudo ln -s ~/views-datafactory/data/compiled/dataframe.parquet /srv/views-data/dataframe.parquet
```

### 3.3 Configure Caddy

**Option A: With a domain name (recommended)**

Edit `/etc/caddy/Caddyfile`:

```
data.views.uu.se {
    root * /srv/views-data
    file_server browse

    # Basic auth (username: views, password: generate one)
    basicauth {
        views $2a$14$HASHED_PASSWORD_HERE
    }

    # CORS headers for browser-based consumers
    header Access-Control-Allow-Origin *
    header Access-Control-Allow-Methods "GET, HEAD, OPTIONS"
}
```

To generate the hashed password:
```bash
caddy hash-password
# Enter your chosen password when prompted
# Copy the output into the Caddyfile
```

**Option B: Without a domain name (IP address only)**

```
:443 {
    tls internal  # Self-signed certificate
    root * /srv/views-data
    file_server browse

    basicauth {
        views $2a$14$HASHED_PASSWORD_HERE
    }

    header Access-Control-Allow-Origin *
    header Access-Control-Allow-Methods "GET, HEAD, OPTIONS"
}
```

### 3.4 Start Caddy

```bash
sudo systemctl enable caddy   # Start on boot
sudo systemctl restart caddy   # Start now
sudo systemctl status caddy    # Check it's running
```

### 3.5 Test from your laptop

```bash
# Test with curl (replace URL and credentials)
curl -u views:yourpassword https://data.views.uu.se/

# Test zarr with Python
python -c "
import xarray as xr
ds = xr.open_zarr(
    'https://views:yourpassword@data.views.uu.se/grid.zarr'
)
print(ds)
"
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
0 3 1 * * cd /home/your-username/views-datafactory && bash scripts/refresh_pipeline.sh >> logs/refresh.log 2>&1
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

ds = xr.open_zarr(
    "https://data.views.uu.se/grid.zarr",
    storage_options={"auth": ("views", "yourpassword")},
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

# Download full file (basic auth in URL)
df = pd.read_parquet(
    "https://views:yourpassword@data.views.uu.se/dataframe.parquet"
)
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

**"Certificate error"** — If using a domain, DNS must point to
the server. Caddy gets certificates automatically but needs DNS
to be correct. If using IP, use `tls internal` (self-signed).

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
2. **A web server** (Caddy) serving data over HTTPS
3. **Authentication** (basic auth) controlling access
4. **Two consumer formats:**
   - Zarr store — lazy loading, subset access, xarray interface
   - Parquet file — full download, pandas interface
5. **Monthly refresh** — cron job runs the pipeline automatically
6. **Monitoring** — `check_health.py` reports data freshness

Consumers access the data with:
```python
# Zarr (subsets, lazy loading)
ds = xr.open_zarr("https://data.views.uu.se/grid.zarr", ...)

# Parquet (full download)
df = pd.read_parquet("https://data.views.uu.se/dataframe.parquet")
```

---

## Next steps (when ready)

- **Add more users:** Edit Caddyfile, add more `username hash` lines
- **Monitor health remotely:** `ssh server 'cd views-datafactory && uv run python scripts/check_health.py --json'`
- **Change update frequency:** Edit the cron schedule (e.g., weekly: `0 3 * * 1`)
- **Add a query API:** See `data_serving_guide.md` section 9
- **Add MCP:** See `data_serving_guide.md` section 9
