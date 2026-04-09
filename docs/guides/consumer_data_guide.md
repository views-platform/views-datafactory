# Consumer Data Guide

How to get conflict data from the data factory into your training script, experiment, or notebook.

---

## Which format do you need?

| You want to... | Use | Result |
|----------------|-----|--------|
| **Train a model** (purple_alien, white_ranger) | `generate_consumer_data.py` | Parquet with `lr_*` columns, partitioned by calibration/validation/forecasting |
| **Run metric-lab experiments** | `load_dataset(output_format="feature_frame")` | FeatureFrame (numpy arrays with identifiers) |
| **Explore data interactively** | `load_dataset(output_format="dataframe")` | pandas DataFrame with MultiIndex |
| **Access from remote server** | Any of the above with `data_dir="http://..."` | Same formats, loaded over HTTP |

---

## Quick start

### 3 lines: get a DataFrame

```python
from datafactory_query import load_dataset

df = load_dataset(
    region="africa",
    start=480,        # 2020-01 (VIEWS month_id)
    end=491,          # 2020-12
    features=["ged_sb_best"],
    output_format="dataframe",
)
```

Returns a pandas DataFrame with MultiIndex `(month_id, priogrid_gid)` and one column `ged_sb_best`.

### 3 lines: get a FeatureFrame

```python
from datafactory_query import load_dataset

ff = load_dataset(
    region="land",
    start="2020",
    end="2020",
    output_format="feature_frame",
)
```

Returns a FeatureFrame with `ff.y_features` (numpy array), `ff.identifiers` (time/unit), `ff.feature_names`.

### From the remote server

Same code, different `data_dir`:

```python
df = load_dataset(
    region="africa",
    start=480,
    end=491,
    features=["ged_sb_best"],
    output_format="dataframe",
    data_dir="http://204.168.219.108/grid.zarr",
)
```

Requires `~/.netrc` credentials (see [Remote access](#remote-access) below).

---

## Training script parquet: `generate_consumer_data.py`

Training scripts (purple_alien, white_ranger, and all views-models) expect parquet files with specific column names, partition splits, and derived columns. This script generates them.

### What it does

1. Calls `load_dataset()` to get data from the assembled grid
2. Renames columns to match the VIEWSER convention models expect
3. Derives `row` and `col` from `priogrid_gid` (PRIO-GRID spatial coordinates)
4. Fills NaN with 0 (matches VIEWSER's `.transform.missing.replace_na()`)
5. Saves one parquet per partition (calibration, validation, forecasting)

### How to run

```bash
# Generate all three partitions
uv run python scripts/generate_consumer_data.py

# Generate only calibration
uv run python scripts/generate_consumer_data.py --partition calibration

# Generate from remote server
uv run python scripts/generate_consumer_data.py --data-dir http://204.168.219.108/grid.zarr

# Output to a specific directory (e.g., a model's data/raw/)
uv run python scripts/generate_consumer_data.py --output-dir ../views-models/models/purple_alien/data/raw
```

### What it produces

```
data/consumer/
├── calibration_viewser_df.parquet    (~64 MB, months 121-492)
├── validation_viewser_df.parquet     (~76 MB, months 121-540)
└── forecasting_viewser_df.parquet    (dynamic, months 121-current+36)
```

Each parquet has:
- **Index:** `(month_id, priogrid_gid)` — both integers, sorted
- **Columns:** `lr_sb_best`, `lr_ns_best`, `lr_os_best`, `c_id`, `row`, `col`

### Column rename mapping

The data factory uses UCDP's original field names. Training scripts use VIEWSER's `lr_*` convention. The script renames automatically:

| Data factory name | Training script name | What it is |
|-------------------|---------------------|-----------|
| `ged_sb_best` | `lr_sb_best` | State-based conflict fatalities (best estimate) |
| `ged_ns_best` | `lr_ns_best` | Non-state conflict fatalities (best estimate) |
| `ged_os_best` | `lr_os_best` | One-sided violence fatalities (best estimate) |
| `gaul0_code` | `c_id` | Country identifier (GAUL administrative code) |

`row` and `col` are derived from `priogrid_gid`:
- `row = (priogrid_gid - 1) // 720 + 1` (1-indexed, south to north)
- `col = (priogrid_gid - 1) % 720 + 1` (1-indexed, west to east)

---

## Partitions

Training scripts split data into three time ranges for train/test evaluation:

### Standard partitions

| Partition | Train range | Test range | Purpose |
|-----------|------------|------------|---------|
| **Calibration** | 121-444 (1990-01 to 2016-12) | 445-492 (2017-01 to 2020-12) | Model selection and hyperparameter tuning |
| **Validation** | 121-492 (1990-01 to 2020-12) | 493-540 (2021-01 to 2024-12) | Out-of-sample performance estimation |
| **Forecasting** | 121 to last month | Next 36 months | Production predictions |

The forecasting partition is computed dynamically from the current date.

### VIEWS month_id

Month IDs encode year and month as a single integer:

```
month_id = (year - 1980) * 12 + month
```

Examples:

| month_id | Date |
|----------|------|
| 1 | 1980-01 |
| 121 | 1990-01 |
| 444 | 2016-12 |
| 492 | 2020-12 |
| 540 | 2024-12 |

To convert back:
```python
year = 1980 + (month_id - 1) // 12
month = (month_id - 1) % 12 + 1
```

---

## `load_dataset()` reference

```python
from datafactory_query import load_dataset

result = load_dataset(
    region="land",                          # geographic filter
    start=None,                             # time range start (inclusive)
    end=None,                               # time range end (inclusive)
    features=None,                          # feature subset (None = all 43)
    output_format="feature_frame",          # "feature_frame" or "dataframe"
    data_dir=Path("data/assembled"),        # local path or zarr URL
    gaul_dir=Path("data/raw/gaul_admin"),   # GAUL admin data
    month_id_epoch=1980,                    # VIEWS convention
)
```

### `region` parameter

Predefined macro-regions:

| Name | Coverage |
|------|----------|
| `"land"` | All land cells (64,818 cells) — **default** |
| `"global"` | All 259,200 cells including ocean |
| `"africa"` | 56 African countries |
| `"middle_east"` | 14 Middle Eastern countries |
| `"africa_me"` | Africa + Middle East combined |
| `"americas"` | 30 countries in North/South America |
| `"europe"` | 46 European countries |
| `"asia_oceania"` | 40 countries in Asia and Oceania |

Or pass a country name: `region="Ethiopia"`, `region="Colombia"`. Country lookup uses GAUL admin boundaries.

### `start` and `end` parameters

Accepts multiple formats:

| Format | Example | Meaning |
|--------|---------|---------|
| VIEWS month_id (int) | `480` | Exact month (2020-01) |
| Year string | `"2020"` | January through December 2020 |
| Year-month string | `"2020-06"` | June 2020 |
| Full date string | `"2020-06-15"` | June 2020 (day ignored) |
| `None` | `None` | Dataset start or end |

### `output_format` parameter

**`"feature_frame"`** (default) — for metric-lab and array-based pipelines:
- `result.y_features`: numpy array `[N, D]` (N observations, D features), float32
- `result.identifiers`: dict with `"time"` and `"unit"` arrays (month_id and priogrid_gid)
- `result.feature_names`: list of D feature name strings

**`"dataframe"`** — for pandas-based analysis and training scripts:
- MultiIndex: `(month_id, priogrid_gid)`
- Columns: requested features
- Sorted by index

### `data_dir` parameter

| Value | Source |
|-------|--------|
| `Path("data/assembled")` | Local npy files (default, fastest) |
| `"data/assembled/grid.zarr"` | Local zarr store |
| `"http://204.168.219.108/grid.zarr"` | Remote server (requires `~/.netrc`) |

---

## Remote access

### Prerequisites

Create a `~/.netrc` file with the server credentials:

```bash
cat >> ~/.netrc << EOF
machine 204.168.219.108
login views
password <your-password>
EOF
chmod 600 ~/.netrc
```

Ask the data factory administrator for the password. The `chmod 600` is required — `~/.netrc` with open permissions is rejected by most tools.

### How it works

`load_dataset()` reads `~/.netrc` automatically when given an HTTP URL. No boilerplate code needed. Under the hood, it creates an `aiohttp.BasicAuth` from the netrc entry and passes it to xarray/fsspec.

The remote path uses **lazy subsetting**: if you request a time range and specific features, only those chunks are downloaded from the server — not the full 1.8 GB store.

### Error messages

| Error | Meaning | Fix |
|-------|---------|-----|
| `PermissionError: Authentication failed... Check ~/.netrc credentials.` | Wrong password or missing netrc entry | Verify `~/.netrc` has correct credentials for the server hostname |
| `FileNotFoundError: Cannot open zarr store...` | Server unreachable or URL wrong | Check network connectivity and URL spelling |
| `FileNotFoundError: Zarr store not found...` | Store doesn't exist at that path | Verify the URL path (should end in `/grid.zarr`) |

---

## GAUL country codes

The assembled grid includes three GAUL (Global Administrative Unit Levels) columns from the FAO:

| Column | Level | Example |
|--------|-------|---------|
| `gaul0_code` | Country | Ethiopia = 79, Colombia = 57 |
| `gaul1_code` | Province / State | |
| `gaul2_code` | District / County | |

These are **NOT** the same as Gleditsch-Ward (GW) codes used in VIEWSER. GAUL and GW use different numbering systems. The `c_id` column in training script parquet files contains GAUL country codes, not GW codes. Models use `c_id` as a grouping identifier, not for external lookups, so the different numbering is functionally equivalent.

To filter by country, use the `region` parameter:

```python
df = load_dataset(region="Ethiopia", output_format="dataframe")
```

This uses the GAUL admin boundary Parquet files to identify which PRIO-GRID cells belong to the country.

---

## Server endpoints: zarr vs parquet

The server at `http://204.168.219.108` serves two endpoints with **different feature sets**:

| Endpoint | Features | Source | Use case |
|----------|----------|--------|----------|
| `/grid.zarr` | **43 features** (6 UCDP + 34 static + 3 GAUL) | `data/assembled/` | Full grid access, `load_dataset()`, research |
| `/dataframe.parquet` | **6 features** (UCDP conflict only) | `data/compiled/` | Lightweight conflict-only download |

This is intentional. The zarr store contains the full assembled grid (all data sources). The parquet export contains only the compiled UCDP conflict features (counts + best estimates for state-based, non-state, and one-sided violence). Use zarr for training and analysis; use parquet for quick conflict-data checks.

---

## Feature inventory

The assembled grid contains 43 features across three groups:

### UCDP conflict events (6 features)

| Feature | Description |
|---------|-------------|
| `ged_sb_count` | State-based conflict events (count) |
| `ged_sb_best` | State-based conflict fatalities (best estimate) |
| `ged_ns_count` | Non-state conflict events (count) |
| `ged_ns_best` | Non-state conflict fatalities (best estimate) |
| `ged_os_count` | One-sided violence events (count) |
| `ged_os_best` | One-sided violence fatalities (best estimate) |

These are monthly counts and fatality estimates from UCDP/GED, filtered by the production parity viewpoint (priogrid_gid >= 1, type_of_violence <= 3, where_prec not in {4, 6}).

### PRIO-GRID static variables (34 features)

| Feature | Description |
|---------|-------------|
| `agri_gc` | Agricultural land cover (%) |
| `aquaveg_gc` | Aquatic vegetation cover (%) |
| `barren_gc` | Barren land cover (%) |
| `cmr_max`, `cmr_mean`, `cmr_min`, `cmr_sd` | Child mortality rate (max/mean/min/stdev) |
| `diamprim_s`, `diamsec_s` | Diamond deposits (primary/secondary) |
| `forest_gc` | Forest cover (%) |
| `gem_s` | Gemstone deposits |
| `goldplacer_s`, `goldsurface_s`, `goldvein_s` | Gold deposits (placer/surface/vein) |
| `growend`, `growstart` | Growing season (end/start month) |
| `harvarea` | Harvested area |
| `herb_gc` | Herbaceous cover (%) |
| `imr_max`, `imr_mean`, `imr_min`, `imr_sd` | Infant mortality rate (max/mean/min/stdev) |
| `landarea` | Land area (km2) |
| `maincrop` | Main crop type |
| `mountains_mean` | Mountain terrain (mean elevation) |
| `petroleum_s` | Petroleum deposits |
| `rainseas` | Rainfall seasonality |
| `shrub_gc` | Shrub cover (%) |
| `ttime_max`, `ttime_mean`, `ttime_min`, `ttime_sd` | Travel time to nearest city (max/mean/min/stdev) |
| `urban_gc` | Urban land cover (%) |
| `water_gc` | Water cover (%) |

These are time-invariant — the same value for every month in the grid.

### GAUL administrative boundaries (3 features)

| Feature | Description |
|---------|-------------|
| `gaul0_code` | Country code (GAUL level 0) |
| `gaul1_code` | Province/state code (GAUL level 1) |
| `gaul2_code` | District/county code (GAUL level 2) |

These are categorical integers, not continuous values. Use them for grouping and filtering, not as model inputs.
