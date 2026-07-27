# Transitioning from viewser to views-datafactory

This guide is for VIEWS researchers who have a working viewser-based model and want to understand what changes when switching to the data factory.

---

## What stays the same

Your model is fine. The data factory replaces *how data reaches your model*, not the model itself.

- **Model architecture** — HydraNet, LightGBM, whatever you use. Unchanged.
- **Training loop** — Same code, same manager, same `run.sh`.
- **Partitions** — Same calibration (121-492), validation (121-540), forecasting (dynamic). Same month_id encoding: `(year - 1980) * 12 + month`.
- **Spatial grid** — Same 0.5-degree PRIO-GRID, same pgid numbering (1-259,200).
- **Parquet interface** — Your model still reads `{run_type}_viewser_df.parquet` from `data/raw/`. The file format, MultiIndex `(month_id, priogrid_gid)`, and column layout are identical.
- **Feature names in the parquet** — The parquet now uses factory source names: `ged_sb_best`, `ged_ns_best`, `ged_os_best`, `gaul0_code`, `row`, `col`. If your model expects `lr_*` names, rename in `config_queryset.py`.

---

## What changes

Six things are different. None affect your model code — they affect the data that enters it.

| # | Change | Impact |
|---|--------|--------|
| 1 | [Data source](#1-data-source) | Where the parquet comes from |
| 2 | [Column naming](#2-column-naming) | Internal plumbing (invisible to your model) |
| 3 | [Country identity (c_id)](#3-country-identity-c_id) | Different coding system, same role |
| 4 | [Data freshness](#4-data-freshness) | ~0.1% of conflict cells may differ |
| 5 | [NaN handling](#5-nan-handling) | Same result, explicit mechanism |
| 6 | [ACLED features](#6-acled-features) | 8 new features not available in VIEWSER |

---

## Side-by-side: viewser vs datafactory

| Operation | viewser | datafactory |
|-----------|---------|-------------|
| **Define data needs** | `Queryset("name", "priogrid_month")` with `.with_column(...)` | `config_queryset.py` with `FACTORY_FEATURES` list |
| **Fetch data** | `queryset.publish().fetch()` (PostgreSQL) | `load_dataset(data_dir="http://...")` (zarr over HTTP) |
| **Data location** | PRIO PostgreSQL server | Hetzner server (204.168.219.108) |
| **Authentication** | SSH tunnel + PRIO VPN | `~/.netrc` (HTTP Basic Auth) |
| **Column names** | `gleditsch_ward`, `ged_sb_best_sum_nokgi` | `gaul0_code`, `ged_sb_best` |
| **Country codes** | Gleditsch & Ward / C-Shapes | FAO GAUL |
| **Caching** | viewser's local DB cache | Parquet file in `data/raw/` |
| **Update frequency** | When PRIO updates the DB | 21st of each month (automated cron) |
| **Dependencies** | `viewser`, `ingester3`, PRIO VPN | `views-datafactory`, `~/.netrc` |

---

## 1. Data source

**viewser:** Your model's `config_queryset.py` defines a `Queryset` object. When the parquet cache is missing, the pipeline calls `queryset.publish().fetch()`, which connects to PRIO's PostgreSQL database over an SSH tunnel.

**datafactory:** Your model's `config_queryset.py` defines feature lists and a `fetch_data()` function. When the parquet cache is missing, `main.py` calls `fetch_data()`, which calls `load_dataset()` from the `datafactory_query` package. This fetches data from the Hetzner zarr store over HTTP.

The parquet file that lands in `data/raw/` has the same schema either way. Your model reads it the same way.

### What you need

1. Install `views-datafactory` (from PyPI — house convention is a release
   floor pin, never a git branch):
   ```bash
   pip install "views-datafactory>=1.9.0"
   ```

2. Set up `~/.netrc` for the Hetzner server:
   ```
   machine 204.168.219.108
       login <your-username>
       password <your-password>
   ```
   Then: `chmod 600 ~/.netrc`. Contact the VIEWS team for credentials.

3. You no longer need the PRIO VPN or SSH tunnel for data access.

---

## 2. Column naming

The data factory emits source column names. The `lr_*` / `c_id` vocabulary from VIEWSER is not applied — consumer-side renaming is the model's responsibility via `config_queryset.py`.

| Parquet column | What it is |
|----------------|------------|
| `ged_sb_best` | State-based fatalities (best estimate) |
| `ged_ns_best` | Non-state fatalities (best estimate) |
| `ged_os_best` | One-sided violence fatalities (best estimate) |
| `gaul0_code` | Country identifier (GAUL Level 0) |

If your existing model expects `lr_sb_best`, add the rename in your `config_queryset.py`. The factory uses UCDP's canonical names because they're unambiguous and documented.

---

## 3. Country identity (`c_id`)

This is the most substantive difference. It affects the *values* in the `c_id` column, though not how the model uses them.

### The old system (viewser)

viewser's `c_id` comes from the **Gleditsch & Ward (G&W) state system list**, mapped to grid cells through the **ETH C-Shapes** project. These codes are **time-varying**: a grid cell's country assignment changes as political borders change.

This was intentional. The idea was to track countries as they changed over time — for example, grid cells in what is now South Sudan would have Sudan's G&W code before 2011 and South Sudan's code after. The audit script found that a single grid cell can have up to 7 different `c_id` values across the calibration partition (months 121-492).

### The problem

This design conflated two things:

1. **Spatial identity** — "which country does this cell belong to?" (metadata for grouping and tracing)
2. **Temporal political signal** — "has this cell's sovereignty changed?" (a predictive feature)

HydraNet's architecture treats `c_id` as an **identity column** — it's carried through the pipeline for bookkeeping but not used as a training feature. A column that changes value over time is a feature pretending to be metadata. If the model learned from those changes, it would be learning from an undocumented, uncontrolled signal.

### The new system (datafactory)

The data factory's `c_id` uses **FAO GAUL 2024 codes** (Global Administrative Unit Layers). The boundary shapefiles and country codes come from FAO's official distribution at `https://storage.googleapis.com/fao-maps-catalog-data/boundaries/GAUL_2024_L{1,2}.zip` (CC-BY-4.0 license). The data factory harvester downloads these shapefiles and performs a spatial join (point-in-polygon against PRIO-GRID centroids) to assign each grid cell a `gaul0_code`.

GAUL codes are **time-invariant**: each grid cell maps to exactly one country code across all months. This means `c_id` is a reliable spatial grouping key. You can group predictions by country, aggregate evaluation metrics by country, or filter by country — and the grouping is consistent regardless of which month you look at.

### What about historical borders?

If you need signal about how borders changed over time — for example, that Sudan and South Sudan used to be one country, or that Eritrea separated from Ethiopia in 1993 — that signal should be an explicit, named feature. Something like `sovereignty_transition_year` or `border_change_since_1990`, with documented semantics.

This is a better design: the feature appears in your feature list, you can inspect its values, you can decide whether to include it in training, and you can reason about what the model is learning from it. It's not hidden inside a column labeled "identity."

No such feature exists yet. When it's needed, it will be built as a proper feature in the data factory.

### Practical impact

- **If your model doesn't use `c_id` for training** (it shouldn't — it's an identity column): no impact. The column exists, has valid values, and HydraNet carries it through.
- **If you aggregate by `c_id` for evaluation**: your groupings will use GAUL country codes instead of G&W codes. The groups are slightly different (GAUL has 79 unique codes in Africa+ME, G&W had 90) because they use different boundary definitions.
- **If you use `output_format="country_month"`**: 603 coastal/island cells in africa_me_legacy have `gaul0_code = -1` (centroid falls outside any GAUL polygon) and are excluded from CM aggregation. This drops ~4% of fatalities relative to PGM totals. See the [Consumer Data Guide](consumer_data_guide.md#country-month-aggregation-caveat) for details.
- **If you join predictions from a factory model with predictions from a viewser model on `c_id`**: they won't match. You'd need a GAUL-to-G&W mapping table.

See [ADR-025](../ADRs/025_country_identity_gaul.md) for the full design rationale.

---

## 4. Data freshness

viewser's data reflects whatever UCDP annual version was loaded into PRIO's PostgreSQL database at the time you fetched. The data factory uses **UCDP annual v25.1** (the latest as of 2026).

This means ~0.05-0.14% of conflict event cells may have different values between a viewser-sourced parquet and a factory-sourced parquet. The differences are real — UCDP revises fatality estimates between annual releases. They are not pipeline bugs.

The audit script reports these differences per column:

```
lr_sb_best: 6,811/4,876,920 cells differ (0.140%)
lr_ns_best: 2,454/4,876,920 cells differ (0.050%)
lr_os_best: 4,745/4,876,920 cells differ (0.097%)
```

For model training, this level of variation is well within normal data noise. If exact reproducibility with a specific viewser snapshot matters for your analysis, note which UCDP version your viewser data used.

---

## 5. NaN handling

**viewser:** Missing values are handled by viewser's `.transform.missing.replace_na()`, which fills NaN with 0. This happens inside the queryset definition.

**datafactory:** Missing values are filled with `df.fillna(0.0)` explicitly in `config_queryset.py`'s `fetch_data()` function.

The result is the same: no NaN values in the parquet. The difference is that the datafactory approach is explicit and visible in the model's config, rather than hidden in a viewser transform chain.

---

## 6. ACLED features

The data factory provides 8 ACLED-derived features that have no equivalent in VIEWSER: `acled_count`, `acled_battles`, `acled_explosions`, `acled_vac`, `acled_protests`, `acled_riots`, `acled_strategic`, and `acled_fatalities`. These are compiled as cell-month aggregates on the same PRIO-GRID and are available alongside the UCDP features in the assembled grid.

---

## How to verify

bright_starship includes an audit script that fetches data from the Hetzner server and compares it against purple_alien's viewser data:

```bash
cd views-datafactory
uv run python ../views-models/models/bright_starship/scripts/audit_data_parity.py
```

This checks structure (index, shape, columns), spatial coordinates (row, col), country identity (c_id coding), event values (with tolerance for UCDP version differences), and dtypes. Expected result: PASS with documented expected differences.

---

## bright_starship: the reference implementation

`models/bright_starship/` in views-models is a working example of a datafactory-powered model. It's a clone of purple_alien with the data source rewired. Key files:

| File | What it does |
|------|-------------|
| `main.py` | Calls `_ensure_data()` before HydranetManager — fetches from Hetzner if parquet is missing |
| `configs/config_queryset.py` | Defines `fetch_data()` — the bridge between the factory and the model's expected parquet format |
| `requirements.txt` | Adds `views-datafactory` as a dependency |
| `scripts/audit_data_parity.py` | Compares factory data against viewser data |

To migrate your own model, use bright_starship's `config_queryset.py` and `main.py` as templates.

---

## Further reading

- [Consumer Data Guide](consumer_data_guide.md) — full `load_dataset()` API reference, partitions, features
- [Zarr Consumer Guide](zarr_consumer_guide.md) — working with xarray and the zarr store directly
- [ADR-025: Country identity uses GAUL codes](../ADRs/025_country_identity_gaul.md) — design rationale for the c_id change
