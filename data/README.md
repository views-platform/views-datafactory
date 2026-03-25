# Data Directory

This directory contains all data produced by the views-datafactory pipeline.
Everything here is **regenerable** from source APIs — the files are gitignored,
but this README is tracked.

---

## If you want the data: start here

**`assembled/`** — The final product. A single grid combining all data sources.

```
assembled/
├── grid.npy            [T, H, W, F] float32  — the grid (all features)
├── pgids.npy           [H, W] int            — PRIO-GRID cell IDs
├── time_steps.npy      [T] datetime64[M]     — monthly timestamps
├── feature_names.json  list of F strings      — what each feature is
└── provenance.json     build metadata         — source digests, shape, etc.
```

**Dimensions:**
- **T** = months (456: January 1989 through December 2026)
- **H** = rows (360: south pole to north pole, 0.5° each)
- **W** = columns (720: date line westward to date line eastward, 0.5° each)
- **F** = features (~39: conflict counts, fatalities, terrain, admin codes)

**How to open it:**

```python
import numpy as np
import json

grid = np.load("data/assembled/grid.npy")           # [456, 360, 720, 39]
pgids = np.load("data/assembled/pgids.npy")          # [360, 720]
time_steps = np.load("data/assembled/time_steps.npy") # [456]
features = json.loads(open("data/assembled/feature_names.json").read())

# Get state-based fatalities for a specific month and cell
fatalities = grid[120, 50, 300, 1]  # month 120, row 50, col 300, feature 1
```

---

## Export formats — choose your interface

### Option 1: Raw numpy (you're already here)

```python
import numpy as np, json

grid = np.load("data/assembled/grid.npy")
features = json.loads(open("data/assembled/feature_names.json").read())

# Slice by feature name
idx = features.index("ged_sb_best")
fatalities = grid[:, :, :, idx]  # [T, H, W] for that feature
```

### Option 2: xarray / zarr (recommended for exploration and serving)

Generate the zarr store first: `uv run python scripts/export_zarr.py`

```python
import xarray as xr

ds = xr.open_zarr("data/assembled/grid.zarr")

# Named dimensions — no index guessing
ethiopia = ds["ged_sb_best"].sel(
    time=slice("2015", "2024"),
    lat=slice(3, 15),
    lon=slice(33, 48),
)
ethiopia.sum(dim=["lat", "lon"]).plot()
```

See `docs/guides/zarr_consumer_guide.md` for full usage guide.

### Option 3: pandas DataFrame (for tabular analysis)

Generate the Parquet first: `uv run python scripts/export_dataframe.py`

```python
import pandas as pd

df = pd.read_parquet("data/compiled/dataframe.parquet")
# MultiIndex: (month_id, priogrid_gid)
# Columns: one per feature

# Filter to one country (requires joining with admin codes)
# Or use the programmatic API:
from datafactory_adapters import grid_to_dataframe

df = grid_to_dataframe(
    grid, pgids, time_steps, feature_names,
    month_id_epoch=1980,  # VIEWS convention
)
```

### Option 4: FeatureFrame (for VIEWS pipeline / metric lab)

FeatureFrame is the handoff format for models and evaluation.

```python
from datafactory_adapters import FeatureFrame, grid_to_feature_frame
import numpy as np, json

grid = np.load("data/assembled/grid.npy")
pgids = np.load("data/assembled/pgids.npy")
time_steps = np.load("data/assembled/time_steps.npy")
features = json.loads(open("data/assembled/feature_names.json").read())

# Convert grid to FeatureFrame
ff = grid_to_feature_frame(
    grid, pgids, time_steps, features,
    month_id_epoch=1980,  # VIEWS month IDs
)

# ff.y_features: [N, D] numpy array (observations x features)
# ff.identifiers["time"]: month_id array
# ff.identifiers["unit"]: priogrid_gid array
# ff.feature_names: list of D feature name strings

# Save to disk (portable format)
ff.save("data/assembled/feature_frame")

# Load back
ff2 = FeatureFrame.load("data/assembled/feature_frame")

# Or construct directly from the grid (convenience)
ff3 = FeatureFrame.from_grid(
    grid, pgids, time_steps, features,
    month_id_epoch=1980,
)
```

### Option 5: Reconstruct grid from FeatureFrame (roundtrip)

```python
from datafactory_adapters import feature_frame_to_grid

# Back to [T, H, W, F] grid
grid_reconstructed = feature_frame_to_grid(ff, pgids)
```

---

## What each directory contains

The directories follow the pipeline stages (ADR-012). Data flows
downward — each stage reads from the one above and writes below.

```
raw/                    ← Harvested from external APIs
  ├── ucdp_annual/         1 file: UCDP annual release (1989-2024)
  ├── ucdp_candidate/      ~60 files: monthly candidate versions
  ├── ucdp_dot9/           ~78 files: monthly .9 consolidated versions
  ├── priogrid_static/     34 files: terrain, resources, land cover
  ├── gaul_admin/          7 files: country/province/district codes
  └── priogrid/            shapefiles and land mask cache
        │
        ▼
consolidated/           ← All UCDP sources merged into one store
  └── ucdp_store.parquet   vintage-aware: same event from different
                           harvests preserved as distinct records
        │
        ▼
viewpoint/              ← Opinionated rules applied
  └── production_parity.parquet
                           survivorship (which version wins),
                           temporal distribution (how to split
                           multi-month events), filtering
        │
        ▼
compiled/               ← Events placed on the PRIO-GRID
  ├── grid.npy             [T, H, W, C] — UCDP features only (6)
  ├── pgids.npy            cell ID map
  ├── time_steps.npy       timestamps
  └── feature_names.json   6 UCDP features
        │
        ▼
assembled/              ← All sources combined (THIS IS THE FINAL PRODUCT)
  ├── grid.npy             [T, H, W, F] — all features (~39)
  ├── pgids.npy            cell ID map
  ├── time_steps.npy       timestamps
  ├── feature_names.json   ~39 features (UCDP + static + admin)
  └── provenance.json      build metadata
```

---

## Sidecar files explained

Every grid directory has the same sidecar files:

- **`pgids.npy`** — Maps each grid cell to a PRIO-GRID cell ID (integer
  1-259,200). Use this to join grid data with other PRIO-GRID datasets.
  `pgids[row, col]` gives the cell ID at that position.

- **`time_steps.npy`** — Monthly timestamps as numpy datetime64[M].
  `time_steps[0]` = 1989-01, `time_steps[455]` = 2026-12.

- **`feature_names.json`** — List of feature name strings. Position
  matches the last dimension of grid.npy. Example: if
  `feature_names[3]` is `"ged_ns_best"`, then `grid[:, :, :, 3]`
  contains non-state fatality data.

- **`provenance.json`** — What sources were used, their content digests,
  the output shape, and when it was built. Used for reproducibility
  and audit.

---

## Features in the assembled grid

**UCDP conflict (6 features):**

| Index | Name | Description |
|-------|------|-------------|
| 0 | `ged_sb_count` | State-based violence: event count |
| 1 | `ged_sb_best` | State-based violence: best fatality estimate |
| 2 | `ged_ns_count` | Non-state violence: event count |
| 3 | `ged_ns_best` | Non-state violence: best fatality estimate |
| 4 | `ged_os_count` | One-sided violence: event count |
| 5 | `ged_os_best` | One-sided violence: best fatality estimate |

**PRIO-GRID static (~30 features):**
Terrain, resources, land cover. Same value for all months (static in
time). Examples: `landarea`, `mountains_mean`, `ttime_mean`,
`petroleum_s`, `forest_gc`.

**GAUL admin boundaries (3 features):**

| Name | Description |
|------|-------------|
| `gaul0_code` | Country code (categorical integer) |
| `gaul1_code` | Province/state code (categorical integer) |
| `gaul2_code` | District code (categorical integer) |

Admin codes are stored as float32 but are categorical — use them
for masking and grouping, not arithmetic.

---

## How to rebuild

If the data directory is empty, regenerate it by running the pipeline:

```bash
# 1. Harvest raw data from APIs
uv run python scripts/harvest_ucdp.py
uv run python scripts/harvest_priogrid.py
uv run python scripts/harvest_gaul.py

# 2. Consolidate
uv run python scripts/consolidate_ucdp.py

# 3. Build viewpoint
uv run python scripts/build_viewpoint.py

# 4. Compile to grid
uv run python scripts/compile_grid.py

# 5. Assemble all sources
uv run python scripts/assemble_grid.py
```

Each step writes provenance to `provenance/` (JSONL ledger files).
