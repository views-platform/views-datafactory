# Hetzner Deployment Log — What We Did, Learned, and Still Need

**Date:** 2026-03-27 to 2026-03-30
**Server:** views-datafactory-00 at 204.168.219.108 (Helsinki, CPX32)
**Status:** Pipeline runs end-to-end. Caddy not yet configured. Data not yet served.

This is a detailed record of the first deployment attempt — what worked,
what broke, how we fixed it, and what we learned. Written for future
reference when rebuilding, debugging, or onboarding someone.

---

## 1. Server Provisioning (2026-03-27)

### What we did

Created a Hetzner Cloud project (`views-datafactory`) and provisioned
a CPX32 server:

| Property | Value | Why |
|----------|-------|-----|
| Type | CPX32 (4 vCPU, 8 GB RAM, 160 GB SSD) | RAM for pipeline; disk for ~50 GB data + growth |
| Location | Helsinki (eu-central) | Close to Uppsala/PRIO (Nordics), EU data residency |
| OS | Ubuntu 24.04 | Standard, best documentation, Caddy support |
| Backups | Enabled (daily, +20% cost) | IT head: "you need to be able to rebuild from scratch" |

### What we learned

- **Hetzner projects are separate sandboxes.** An existing FAO API project
  was on the same account. Creating a new project kept things isolated.
- **SSH key registration is per-project, not per-account.** Had to add
  the same public key to the new project explicitly.
- **CPX22 (80 GB) would have been too small.** Raw data alone is ~35 GB.
  With assembled grid (19 GB) + zarr (1.8 GB) + OS + tools, we'd be at
  75%+ capacity immediately. CPX32 (160 GB) gives breathing room for
  V-Dem, ACLED, WID expansion.

---

## 2. Base System Setup (2026-03-27)

### What we did

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip git
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### What went wrong

- **`source ~/.cargo/env`** failed — uv installed itself to `~/.local/bin`,
  not `~/.cargo/`. The install script output told us, but we ran the wrong
  command from the deployment guide. `uv --version` confirmed it worked
  regardless.

### What we learned

- **Don't blindly follow documentation.** Check the actual install output
  for the correct PATH setup command.

---

## 3. Repository Cloning (2026-03-27 to 2026-03-29)

### What we tried first (HTTPS with token)

```bash
git clone https://TOKEN@github.com/views-platform/views-datafactory.git
```

This worked for the initial clone but caused persistent problems:

- `git fetch` and `git pull` asked for username/password
- The token was embedded in the remote URL but wasn't being passed correctly
- Only `main` was checked out; `development` wasn't available locally

### What we tried second (switch to SSH)

```bash
git remote set-url origin git@github.com:views-platform/views-datafactory.git
git fetch origin
```

This failed with `Permission denied (publickey)` because the server
had no SSH key registered on GitHub.

### What we finally did

Generated a new SSH key on the server, registered it on Simon's
personal GitHub account:

```bash
ssh-keygen -t ed25519 -C "views-datafactory-00"
cat ~/.ssh/id_ed25519.pub
# → Added to GitHub Settings → SSH keys
```

Then:

```bash
git remote set-url origin git@github.com:views-platform/views-datafactory.git
git fetch origin
git checkout development
```

### What we learned

- **HTTPS tokens are fragile.** They expire, they don't always propagate
  to fetch/pull, and they embed credentials in the remote URL (visible
  in `git remote -v`). SSH is more reliable for servers.
- **SSH key setup was forgotten.** We generated a key during Hetzner
  provisioning but it was the laptop's key for the Hetzner console,
  not a key on the server for GitHub. Two different things.
- **This is a security concern.** The server's SSH key is registered on
  Simon's personal GitHub account, not as a repo-scoped deploy key.
  Tracked as C-85/C-86 in the risk register. Must be fixed before
  granting anyone else server access.
- **Everything runs as root.** No named user accounts exist. Tracked as
  C-84/C-87. Must be fixed before sharing access.

---

## 4. First Pipeline Run — Failures (2026-03-28 to 2026-03-29)

### Failure 1: Missing shapefile (Step 1 — Harvest)

**Symptom:**
```
FileNotFoundError: Centroid shapefile not found:
data/raw/priogrid/shapefile/priogrid_centroid.shp
```

**Root cause:** The GAUL admin boundary harvester requires a PRIO-GRID
centroid shapefile for spatial joins. The download code existed
(`shapefile_harvester.py:fetch_shapefile()`) but was never wired into
a script or the pipeline. On the development laptop, the file existed
from a manual run. On a fresh server, it didn't.

**Fix:** Created `scripts/harvest_shapefile.py` and added it to
`refresh_pipeline.sh` before the GAUL harvest step. Also fixed the
`ShapefileHarvesterConfig.data_dir` default from `data/priogrid` to
`data/raw/priogrid` to match the path convention.

**Lesson:** If a pipeline step depends on an artifact, the pipeline
must produce that artifact. "It exists on my laptop" is not a valid
deployment strategy.

### Failure 2: harvest_ucdp.py always exited 0 (Step 1 → Step 2)

**Symptom:** Annual harvest failed (API timeout), but the pipeline
continued to consolidation, which crashed trying to read non-existent
Parquet files.

**Root cause:** `harvest_ucdp.py` always returned `sys.exit(0)`
regardless of whether any source failed. The `set -euo pipefail`
in `refresh_pipeline.sh` relies on non-zero exit codes to stop.

**Fix:** Changed exit code to `return 1 if n_failed > 0 else 0`.

**Lesson:** Every script in the pipeline must return non-zero on
failure. `set -e` is only as good as the exit codes it checks.

### Failure 3: UCDP API rate limiting (Step 1 — Annual harvest)

**Symptom:** Annual harvest fetched 38-94 pages successfully, then
received HTTP 400 Bad Request.

**Root cause:** The UCDP API rate-limits after approximately 40
requests, regardless of delay between them. Our default `page_size=1000`
meant 386 pages (386 requests) for 385,918 events. Increasing the
delay from 0s to 0.5s to 2.0s didn't help — the limit appears to be
on total request count, not request rate.

**Investigation:** The production GedLoader notebook uses
`pagesize=50000`, resulting in only 8 pages. This was the key insight —
production had never hit the rate limit because it made far fewer
requests.

**Fix progression:**
1. Added `page_delay=0.5s` between pages → still failed at page 38
2. Increased to `page_delay=2.0s` → still failed at page 46
3. Increased `page_size` to 10000 (39 pages) → still failed
4. Increased `page_size` to 50000 (8 pages) → **success**

**Final config:**
```python
UcdpAnnualConfig(
    timeout=120,       # 30s default too short for large pages
    page_size=50000,   # API rate-limits after ~40 requests
    page_delay=2.0,    # Extra safety margin between pages
)
```

**Lesson:** When an API rate-limits, reducing request count is more
effective than increasing delay. Check how production does it before
inventing your own approach.

### Failure 4: Viewpoint builder OOM (Step 3)

**Symptom:** Process killed with exit code 137 (OOM killer).

**Root cause:** `build_ucdp_v1()` converted the entire 2.3M-row
consolidated Parquet table to a Python dict-of-lists, then created
2.3M individual Python dicts (one per event), then grouped them by
event ID. Peak memory: ~4.5 GB for the dicts alone, plus the PyArrow
table (~500 MB). Total exceeded 8 GB.

**Fix:** Refactored to sorted-group processing. Sort the table by
event ID (PyArrow columnar operation, no Python dicts). Walk the
sorted ID column to find group boundaries. Slice each group (typically
1-5 rows) and only create dicts for that small group. Stream
survivorship winners through distribution and filtering directly to
output columns.

Peak memory dropped from ~4.5 GB to ~700 MB. Verified by running on
laptop and comparing output digest (identical: `821528d140360ac1`).

**Lesson:** Never create N Python dicts from an N-row table when N
is in the millions. Process in groups or use columnar operations.
This was the same pattern as C-24 (compiler OOM, resolved months
earlier with the same approach).

### Failure 5: Assemble grid OOM (Step 5)

**Symptom:** Process killed with exit code 137 (OOM killer) again,
this time at the assembly step.

**Root cause:** `assemble_grid.py` allocated a `np.zeros([456, 360, 720, 43])`
array — 4.6 GB of float32 — in memory. Then it copied the UCDP grid
(1.3 GB mmap'd) into it. Peak was ~6 GB, exceeding available RAM.

**Fix:** Replaced in-memory `np.zeros()` with `np.lib.format.open_memmap()`,
which creates the output `.npy` file on disk and returns a memory-mapped
array. All writes go through the page cache directly to disk. Peak
memory dropped from ~6 GB to ~150 MB.

Verified parity: output digest `821528d140360ac1` matches exactly.
Assembly takes ~27 minutes (slower due to disk I/O) but doesn't OOM.

**Lesson:** For arrays larger than half the available RAM, use
memory-mapped files. `np.lib.format.open_memmap()` produces a standard
`.npy` file that `np.load()` reads without knowing it was mmap'd.

### Failure 6: Data path mismatch (Step 2)

**Symptom:** Consolidator found 0 source files in `data/raw/ucdp_annual`.

**Root cause:** `harvest_ucdp.py` had `--data-dir` defaulting to
`Path("data")` and appended `/ "ucdp_annual"`, writing to `data/ucdp_annual`.
The consolidator expected `data/raw/ucdp_annual`. The harvest script was
the one file missed during the `data/raw/` path normalization.

**Fix:** Changed harvest script default from `Path("data")` to
`Path("data/raw")`. Moved existing data on server from `data/ucdp_*`
to `data/raw/ucdp_*`.

**Lesson:** Path normalization must be verified end-to-end, not file by
file. A fresh deployment is the best test — it reveals every hardcoded
or mismatched path.

---

## 5. Successful Pipeline Run (2026-03-30)

### Timeline (clean run from empty data/)

| Step | Duration | Notes |
|------|----------|-------|
| Harvest annual | ~20 min | 8 pages × 50,000 events, 2s delay between |
| Harvest candidate | ~4 min | 63 versions served, 35 no longer available |
| Harvest dot9 | ~85 min | 98 versions, full fetch |
| Harvest priogrid/shapefile/gaul | ~2 min | Static data, cached after first run |
| Consolidate | ~23 sec | 2,295,643 records |
| Build viewpoint | ~2.5 min | 398,383 output rows |
| Compile grid | ~24 sec | [456, 360, 720, 6] |
| Assemble | ~27 min | [456, 360, 720, 43] via mmap |
| Export zarr | ~14 min | 1.8 GB store |
| Export parquet | ~13 sec | 29.5M rows |
| Health check | <1 sec | Reports status |

**Total: approximately 2.5 hours for a clean run.**

Subsequent runs are much faster because most data is cached (only new
UCDP versions are fetched).

### What's on the server now

```
data/
├── raw/                    ~5 GB (UCDP + static + admin + shapefile)
├── consolidated/           ~300 MB (ucdp_store.parquet)
├── viewpoint/              ~50 MB (production_parity.parquet)
├── compiled/               ~1.3 GB (UCDP-only grid + sidecars)
└── assembled/              ~21 GB (full grid + zarr + sidecars)
    ├── grid.npy            19 GB
    ├── grid.zarr/          1.8 GB
    ├── pgids.npy
    ├── time_steps.npy
    ├── feature_names.json
    └── provenance.json
```

---

## 6. What Still Needs to Be Done

### Immediate (before serving data)

1. **Install and configure Caddy** — the web server that serves the zarr
   store over HTTPS. See Phase 3 in `hetzner_deployment_guide.md`.
2. **Set up cron job** — monthly pipeline refresh. See Phase 4.
3. **Test consumer access** — verify `xarray.open_zarr()` works from
   a remote machine. See Phase 5.

### Before sharing server access (Tier 2 risk register items)

4. **C-84: Create non-root service account** — all operations currently
   run as root. Create a `views-deploy` user for the pipeline.
5. **C-85/C-86: Replace personal SSH key with deploy key** — current
   GitHub access uses Simon's personal key. Create a repo-scoped
   read-only deploy key instead.
6. **C-87: Create named user accounts** — one per person, plus a
   break-glass emergency account.
7. **C-88: Restrict SSH to PRIO/Uppsala IPs** — configure Hetzner
   firewall or fail2ban.

### Before production deployment

8. **D-03: Implement alerting** — `refresh_pipeline.sh` writes a failure
   sentinel (`logs/pipeline_failure.json`) but nobody checks it.
   Configure email alerts via `ALERT_EMAIL` env var, or set up a
   monitoring check.
9. **DNS setup** — get a domain name (e.g., `data.views.uu.se`) pointed
   at the server IP. Requires Uppsala IT cooperation.

---

## 7. Key Lessons

### About deployment

1. **A fresh server is the ultimate integration test.** Every path
   mismatch, missing dependency, and implicit assumption surfaced
   during the first deployment. No amount of local testing would have
   caught the shapefile gap or the data path mismatch.

2. **Memory is the bottleneck, not CPU.** The pipeline's CPU usage is
   modest (fetching, parsing, compiling). But creating millions of Python
   objects or allocating multi-GB arrays kills the process on 8 GB RAM.
   Memory-mapped I/O and columnar processing are the solutions.

3. **API rate limits are about request count, not request rate.** The
   UCDP API doesn't care about delay between requests — it cares about
   total requests. Fewer, larger pages solve the problem.

4. **Check how production does it.** The GedLoader notebook had the
   answer (`pagesize=50000`) all along. We spent 3 attempts with
   different delays before looking at the source.

### About security

5. **Root is a bad habit.** It's fast and convenient during setup but
   creates a security debt that's expensive to fix later. Should have
   created a service account from the start.

6. **Personal SSH keys on shared servers are a liability.** Deploy keys
   exist for exactly this purpose — repo-scoped, read-only by default,
   and not tied to a person's account.

7. **Document the IT guidance upfront.** The PRIO IT head's security
   recommendations (IP whitelisting, named accounts, dependency
   tracking, rebuild documentation) should have been the deployment
   checklist, not an afterthought.

### About the pipeline

8. **`set -euo pipefail` is only as good as your exit codes.** If a
   script returns 0 on failure, the pipeline continues on bad data.
   Every script must exit non-zero on failure.

9. **tmux/screen is essential for long-running server operations.**
   The SSH connection dropped during the 2.5-hour viewpoint step.
   Without tmux, the process would have been killed.

10. **Failure sentinels work.** `logs/pipeline_failure.json` with
    timestamp, exit code, and step name made debugging straightforward
    across SSH disconnects.

---

## 8. Commits Made During Deployment

| Commit | Fix |
|--------|-----|
| `3a24fbd` | datafactory_http package, shapefile harvester, deployment resilience |
| `5cbf520` | Retry jitter, 4xx fail-fast, doc alignment, stale ref cleanup |
| `03d7d47` | Increase annual timeout to 120s, log server hardening concerns |
| `9fab694` | Add page_delay=0.5s (didn't solve rate limiting) |
| `858852b` | Fix harvest data-dir default data/ → data/raw/ |
| `092f41f` | page_size 1000 → 10000 (still hit rate limit) |
| `63b9dc2` | page_size 10000 → 50000 (solved rate limiting) |
| `af8c02c` | Viewpoint builder OOM — sorted-group processing |
| `934a016` | Assemble grid OOM — mmap output |
| `bb52dbf` | page_delay 0.5 → 2.0 (before discovering page_size fix) |
