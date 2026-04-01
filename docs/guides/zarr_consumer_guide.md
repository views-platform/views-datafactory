# Zarr Consumer Guide

How to access VIEWS conflict data from the zarr store.

---

## What is this?

The VIEWS data factory produces a gridded dataset of conflict events
on the 0.5-degree PRIO-GRID (360 rows x 720 columns, monthly from
1989 to 2026). The zarr store makes this data accessible over HTTP
without downloading the entire 19 GB file.

**Key concepts:**

- **zarr** is a storage format that splits arrays into chunks (small
  files in a directory). A web server serves the directory; your code
  downloads only the chunks it needs.

- **xarray** is a Python library for working with labeled
  multi-dimensional data. Think of it as "numpy with named dimensions
  and coordinates." Instead of `grid[120, 50, 100, 3]` you write
  `ds["ged_sb_best"].sel(time="1999-01", lat=15.25, lon=30.25)`.

- **Lazy loading** means xarray does not load data into memory until
  you ask for it. Opening the dataset is instant. Selecting a subset
  downloads only those chunks. Calling `.values` or `.load()` triggers
  the actual download.

---

## Opening the dataset

### From a URL (remote server)

```python
import xarray as xr

ds = xr.open_zarr("http://204.168.219.108/grid.zarr")
print(ds)
```

**Auth:** This requires a one-time credential setup. xarray uses
fsspec as its HTTP backend, which reads `~/.config/fsspec/http.json`:

```bash
mkdir -p ~/.config/fsspec
cat > ~/.config/fsspec/http.json << 'EOF'
{
  "client_kwargs": {
    "auth": ["views", "yourpassword"]
  }
}
EOF
chmod 600 ~/.config/fsspec/http.json
```

After this, `xr.open_zarr(url)` works with no extra arguments.
See `docs/guides/hetzner_deployment_guide.md` Phase 5 for full
setup instructions.

### From a local path

```python
import xarray as xr

ds = xr.open_zarr("data/zarr/grid.zarr")
print(ds)
```

Both return the same Dataset object. The `print(ds)` output looks like:

```
<xarray.Dataset>
Dimensions:       (time: 456, lat: 360, lon: 720)
Coordinates:
  * time          (time) datetime64[M] 1989-01 ... 2026-12
  * lat           (lat) float64 -89.75 -89.25 ... 89.25 89.75
  * lon           (lon) float64 -179.75 -179.25 ... 179.25 179.75
    pgid          (lat, lon) int32 ...
Data variables:
    ged_sb_count  (time, lat, lon) float32 ...
    ged_sb_best   (time, lat, lon) float32 ...
    ged_ns_count  (time, lat, lon) float32 ...
    ... (one variable per feature)
```

**Nothing is in memory yet.** The dataset is a lazy reference.

---

## Selecting data

### By feature name

```python
# One feature — still lazy
fatalities = ds["ged_sb_best"]

# Load into memory (downloads the relevant chunks)
fatalities_array = fatalities.values  # numpy array [456, 360, 720]
```

### By time

```python
# One month
jan_2020 = ds.sel(time="2020-01")

# A year
year_2020 = ds.sel(time="2020")

# A range
decade = ds.sel(time=slice("2010-01", "2019-12"))
```

### By location (lat/lon bounding box)

```python
# Ethiopia (approximate bounding box)
ethiopia = ds.sel(
    lat=slice(3, 15),
    lon=slice(33, 48),
)

# One cell (nearest to a point)
cell = ds.sel(lat=9.0, lon=38.7, method="nearest")
```

### Combining selections

```python
# Ethiopia fatalities in the 2010s
result = ds["ged_sb_best"].sel(
    time=slice("2010-01", "2019-12"),
    lat=slice(3, 15),
    lon=slice(33, 48),
)

# Load into memory
data = result.values  # numpy array, shape depends on selection
```

---

## Common operations

### Total fatalities per month (global)

```python
monthly = ds["ged_sb_best"].sum(dim=["lat", "lon"])
monthly.plot()
```

### Spatial heatmap (total over all time)

```python
total = ds["ged_sb_best"].sum(dim="time")
total.plot(cmap="YlOrRd")
```

### Time series for one cell

```python
cell = ds["ged_sb_best"].sel(
    lat=9.0, lon=38.7, method="nearest"
)
cell.plot()
```

### Compare two features

```python
import matplotlib.pyplot as plt

fig, axes = plt.subplots(1, 2, figsize=(14, 5))
ds["ged_sb_best"].sum("time").plot(ax=axes[0], cmap="YlOrRd")
ds["ged_ns_best"].sum("time").plot(ax=axes[1], cmap="YlOrRd")
axes[0].set_title("State-based fatalities")
axes[1].set_title("Non-state fatalities")
```

### Convert to pandas DataFrame

```python
# One feature, one region, as a table
df = ds["ged_sb_best"].sel(
    lat=slice(3, 15), lon=slice(33, 48)
).to_dataframe()
```

---

## Understanding the coordinates

### time

Monthly timestamps from 1989-01 to 2026-12. Stored as
`datetime64[M]`. Use string slicing: `"2020"`, `"2020-01"`,
`slice("2015", "2020")`.

### lat, lon

Cell centers at 0.5-degree resolution. Latitude runs from -89.75
(south pole) to 89.75 (north pole). Longitude runs from -179.75
(date line west) to 179.75 (date line east).

### pgid

PRIO-GRID cell ID — a non-dimension coordinate of shape (lat, lon).
Maps each grid cell to its integer cell ID (1 to 259,200). Useful
for joining with other PRIO-GRID datasets:

```python
# Get pgid for a specific cell
pgid = int(ds["pgid"].sel(lat=9.0, lon=38.7, method="nearest"))
```

---

## Data variables (features)

The dataset contains ~39 features from three sources:

**UCDP conflict (6 features):**
- `ged_sb_count` / `ged_sb_best` — state-based violence (type 1)
- `ged_ns_count` / `ged_ns_best` — non-state violence (type 2)
- `ged_os_count` / `ged_os_best` — one-sided violence (type 3)

**PRIO-GRID static (~30 features):**
Terrain, resources, land cover variables. Static across time
(same value for all months). Examples: `landarea`, `mountains_mean`,
`ttime_mean`, `petroleum_y`.

**GAUL admin boundaries (3 features):**
- `gaul0_code` — country code
- `gaul1_code` — province/state code
- `gaul2_code` — district code

These are categorical integers stored as float32. Use them for
masking (e.g., select all cells in country X), not arithmetic.

---

## Performance tips

1. **Select before loading.** `ds["ged_sb_best"].sel(time="2020").values`
   downloads one chunk. `ds["ged_sb_best"].values` downloads everything.

2. **Use `.sel()` not integer indexing.** `ds.sel(lat=9.0)` is clear;
   `ds.isel(lat=199)` is fragile.

3. **Check chunk sizes.** `ds["ged_sb_best"].encoding` shows the chunk
   layout. Each chunk is ~12 MB (12 months x 360 x 720 x 4 bytes).

4. **For bulk analysis, load features individually.** Loading one
   feature at a time is memory-efficient. Loading the full dataset
   (`ds.load()`) requires ~19 GB RAM.

---

## Installing xarray

```bash
pip install xarray zarr
# or
uv add xarray zarr
```

No other dependencies needed for reading zarr stores.

---

## Troubleshooting

**"No module named 'xarray'"** — Install it: `pip install xarray zarr`

**"FileNotFoundError" on open_zarr** — Check the path. For local:
`data/zarr/grid.zarr`. For remote: the full URL including `.zarr`.

**"Out of memory"** — You're loading too much. Use `.sel()` to subset
before `.values` or `.load()`.

**Data looks wrong (rotated map)** — Check that you're using lat/lon
coordinates, not integer indices. `ds.sel(lat=9.0)` is correct;
`ds.isel(lat=9)` gives a different cell.
