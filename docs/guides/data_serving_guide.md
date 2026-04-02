# Data Serving Guide — From Files to Online Access

This guide explains how to make data available online, written for
someone who knows Python and numpy but has never deployed anything.
Read this before making any decisions about servers or infrastructure.

---

## The big picture

Right now your data lives on your laptop as files. To make it
accessible to others (people, programs, or AI models), you need
to put those files on a computer that's always on and connected
to the internet, and run software that hands out files when asked.

That's it. Everything else is details.

---

## 1. What is a server?

A server is just a computer that's always on and reachable from
the internet. Your Hetzner box is a server. Right now only you
can reach it (via SSH — the secure shell you use to log in).

When people say "put it on the server," they mean: copy files to
that computer and run software that lets others download them.

**Your setup:** You have a Hetzner Linux box you can SSH into.
That's everything you need.

---

## 2. What is a web server?

A web server is software that runs on your server and listens for
requests. When someone (or some program) asks for a file, the web
server finds it and sends it back.

Think of it as a librarian:
- Someone walks in and says "I want chapter 3 of the conflict data"
- The librarian finds the right file on the shelf
- The librarian hands it over
- The librarian doesn't write books — just finds and serves them

Common web servers:
- **Caddy** — simple, handles HTTPS certificates automatically
- **nginx** — very common, more configuration needed
- **Apache** — older, still widely used

For our use case, **Caddy is recommended** because it requires the
least configuration and handles HTTPS (encrypted connections)
automatically.

**Key point:** A web server does NOT run Python. It serves files.
Your Python pipeline produces the files; the web server hands them
out. These are separate concerns.

---

## 3. What is HTTP and HTTPS?

HTTP is the protocol (set of rules) that web browsers and programs
use to request files from servers. When you visit a website, your
browser sends HTTP requests and gets responses.

HTTPS is the same thing but encrypted — nobody between you and the
server can read the data. All modern services use HTTPS.

A URL like `https://data.views.uu.se/grid.zarr/` means:
- `https://` — use encrypted HTTP
- `data.views.uu.se` — the server's address
- `/grid.zarr/` — the file (or directory) to fetch

---

## 4. How zarr-over-HTTP works (the clever part)

Your zarr store is not one big file. It's a directory of many
small files (chunks), organized like this:

```
grid.zarr/
├── .zmetadata          (what's in this dataset)
├── ged_sb_best/
│   ├── .zarray         (shape, type, chunk layout)
│   ├── 0.0.0           (chunk: months 0-11, all lat, all lon)
│   ├── 1.0.0           (chunk: months 12-23)
│   ├── 2.0.0           (chunk: months 24-35)
│   └── ...             (38 chunks for 456 months ÷ 12)
├── ged_ns_best/
│   ├── .zarray
│   ├── 0.0.0
│   └── ...
└── ... (one directory per feature)
```

When a consumer writes:
```python
ds = xr.open_zarr("https://yourserver/grid.zarr")
ethiopia_2020 = ds["ged_sb_best"].sel(time="2020")
```

Here's what actually happens:
1. xarray downloads `.zmetadata` (tiny file: what features exist,
   what the dimensions are)
2. xarray figures out which chunk contains year 2020 (chunk 2.0.0,
   since 2020 is months 372-383, and chunks are 12 months each)
3. xarray downloads ONLY that one chunk (about 1 MB)
4. Done. The other 37 chunks and 42 other features are never touched.

**This is why zarr is the standard for serving gridded data.**
The web server just serves files. The intelligence is in the format
— xarray knows which files to ask for. No application code needed
on the server.

This is how ERA5 (the world's most-used climate dataset) and CMIP6
(climate model outputs) are served. Same pattern, same tools.

---

## 5. How parquet download works (simpler)

A parquet file is a single file. The web server serves it like any
other file — consumer downloads the whole thing, opens it in pandas:

```python
import pandas as pd
df = pd.read_parquet("https://yourserver/dataframe.parquet")
```

No slicing. The consumer gets everything. This is fine for tabular
analysis where they want to filter and aggregate themselves.

**Size context:** The dense parquet for all land cells is about
2-4 GB. Downloadable in minutes on a decent connection.

---

## 6. What is authentication?

Authentication means: who is allowed to access this data?

**No auth:** Anyone with the URL can download the data. Fine for
public datasets. Simple.

**Basic auth:** The web server asks for a username and password.
Like a locked room — you give the key (credentials) to people
you trust. The web server checks credentials before serving any
file. No code needed — caddy and nginx support this natively.

**API keys:** Instead of username/password, consumers include a
secret string (key) in their requests. More suitable for programs
than humans. Requires a thin layer of code or a gateway service.

**For VIEWS internal access:** Basic auth is standard and
sufficient. You create one set of credentials and share them
with the team.

---

## 7. What is a cron job?

Cron is a scheduler built into Linux. You tell it "run this
command at this time" and it does it automatically, forever, even
if you're not logged in.

Example: "Run the data pipeline on the 21st of every month at midnight"

```
0 0 21 * * /path/to/refresh_pipeline.sh
```

That line means: minute 0, hour 0, day 21, every month, every
day-of-week. Run the script.

Your pipeline takes about 10-20 minutes (harvesting is the slow
part — it calls the UCDP API). After it finishes, the new zarr
and parquet files are in the same directory the web server serves.
Consumers automatically get the new data on their next request.

**No restart needed.** The web server serves whatever files are
in the directory. When the pipeline replaces them, the next
request gets the new version.

---

## 8. What the simplest deployment looks like

Here's the full picture, step by step:

```
Your laptop                       Hetzner server
──────────                        ──────────────

scripts/refresh_pipeline.sh  ──→  Runs monthly via cron:
                                    1. harvest_ucdp.py
                                    2. consolidate_ucdp.py
                                    3. build_viewpoint.py
                                    4. compile_grid.py
                                    5. assemble_grid.py
                                    6. export_zarr.py
                                    7. export_dataframe.py
                                        │
                                        ▼
                                  data/assembled/grid.zarr/  (1.8 GB)
                                  data/compiled/dataframe.parquet
                                        │
                                        ▼
                                  Caddy web server
                                  (serves files over HTTPS)
                                  (basic auth: username + password)
                                        │
                                        ▼
                                  https://data.views.uu.se/
                                        │
Consumer (Python)  ◀──────────────────────┘
  xr.open_zarr("https://data.views.uu.se/grid.zarr")
  pd.read_parquet("https://data.views.uu.se/dataframe.parquet")
```

**What you install on the Hetzner server:**
1. Python + uv (to run the pipeline)
2. Caddy (to serve files)
3. The views-datafactory repo (git clone)
4. A cron job (to run the pipeline monthly)

**What you DON'T need:**
- Docker / containers
- A database (PostgreSQL, etc.)
- A Python web framework (FastAPI, Flask)
- A cloud platform (AWS, GCP)
- Kubernetes or any orchestration

---

## 9. What comes later (and why not now)

### Query API (FastAPI)

A running Python application that accepts questions like
`/api/data?country=Ethiopia&year=2020` and returns JSON.

**Why not now:** Zarr-over-HTTP already gives subset access.
Adding an API means writing, deploying, and maintaining a Python
application that runs 24/7. Worth it when consumers need queries
the zarr format can't express (e.g., "top 10 deadliest cells
this year"). Not worth it for spatial/temporal slicing.

**When:** When a consumer asks for something zarr can't do.

### MCP (Model Context Protocol)

Lets AI models (like Claude) query your data directly.

**Why not now:** MCP needs an endpoint to connect to. Once the
zarr store is online, an MCP server can be a thin wrapper that
translates natural-language queries to xarray operations. But
the data must be online first.

**When:** After the zarr store is serving successfully.

### Database (PostgreSQL / DuckDB)

Stores data in a way that makes complex queries fast.

**Why not now:** Your data is gridded (lat × lon × time × feature).
Databases are designed for rows and columns with complex joins.
Zarr is the right format for gridded data. A database would be
useful if you needed to query the raw event-level Parquet data
(e.g., "all events in Somalia with >100 fatalities").

**When:** When event-level queries become important.

### Containerization (Docker)

Packages your software + dependencies into a portable box that
runs identically anywhere.

**Why not now:** You have one server. Docker adds complexity
(building images, managing containers, debugging inside
containers) without benefit when you're deploying to one machine.

**When:** When you need to deploy to multiple machines or hand
off deployment to someone who shouldn't need to understand the
codebase.

---

## 10. Glossary

| Term | Meaning |
|------|---------|
| **Server** | A computer that's always on and reachable from the internet |
| **Web server** | Software that hands out files when asked (caddy, nginx) |
| **HTTP/HTTPS** | The protocol for requesting files over the internet |
| **URL** | The address of a file: `https://server/path/to/file` |
| **Port** | A numbered "door" on a server. 443 = HTTPS. 22 = SSH |
| **SSH** | Secure Shell — how you log into the server's terminal |
| **Cron** | Linux scheduler — runs commands at set times |
| **Basic auth** | Username + password to access a web resource |
| **API key** | A secret string that identifies a consumer |
| **Zarr** | A format that splits arrays into small chunk files |
| **xarray** | Python library for labeled multi-dimensional data |
| **HTTPS certificate** | Proof that your server is who it says it is (caddy handles this automatically) |
| **rsync** | A command that copies files to/from a server efficiently |
| **DNS** | Translates names (data.views.uu.se) to IP addresses |
| **Endpoint** | A URL that a program can request data from |
| **MCP** | Model Context Protocol — lets AI models query data |
| **FastAPI** | A Python framework for building query APIs |
| **Docker** | Packages software into portable containers |
