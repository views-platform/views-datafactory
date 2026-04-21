# Verification Examples

Executable scripts that verify every user-facing capability of the datafactory.
Each script calls the public API with specific parameters and asserts on the
output contract. Run them with `run_examples.sh` for a PASS/FAIL summary.

## Quick start

```bash
bash examples/run_examples.sh                    # local backends only
bash examples/run_examples.sh --include-remote   # also test remote zarr
```

## Scripts

### Output formats

| Script | Capability | What it asserts |
|--------|-----------|-----------------|
| `ex_dataframe_output.py` | `output_format="dataframe"` | MultiIndex, correct columns, float dtypes, sorted, no NaN |
| `ex_feature_frame_output.py` | `output_format="feature_frame"` | FeatureFrame shape, dtype, identifiers, feature_names |

### Region subsetting

| Script | Capability | What it asserts |
|--------|-----------|-----------------|
| `ex_region_predefined.py` | Predefined macro-regions | global=259200, land=64818, africa_me_legacy=13110 cells |
| `ex_region_country.py` | Country-name lookup (GAUL) | Ethiopia resolves, case-insensitive, unknown raises |

### Time parsing

| Script | Capability | What it asserts |
|--------|-----------|-----------------|
| `ex_time_month_id.py` | VIEWS month_id (int) | Correct month range, month_id 481 = Jan 2020 |
| `ex_time_iso_string.py` | ISO strings | Year-only, year-month, full-date truncation |
| `ex_time_none.py` | `start=None, end=None` | Returns full dataset time range |

### Feature selection

| Script | Capability | What it asserts |
|--------|-----------|-----------------|
| `ex_feature_subset.py` | `features=[...]` | Only requested columns present; None = all 43 |

### Data backends

| Script | Capability | What it asserts |
|--------|-----------|-----------------|
| `ex_npy_backend.py` | Local npy directory | DataFrame/FeatureFrame consistency |
| `ex_zarr_local.py` | Local zarr store | Correct output structure |
| `ex_zarr_remote.py` | Remote zarr over HTTP | Correct output structure (requires .netrc) |

### Consumer integration

| Script | Capability | What it asserts |
|--------|-----------|-----------------|
| `ex_partitions.py` | Partition generation | cal/val/fc structure, correct month_id ranges |
| `ex_consumer_bridge.py` | Full bridge pattern | load -> rename -> derive row/col -> fillna -> parquet round-trip |

### Documented gaps (xfail)

| Script | Gap | Risk register |
|--------|-----|---------------|
| `ex_xfail_country_month.py` | No country_month aggregation | C-125 |
| `ex_xfail_transforms.py` | No feature transform layer | C-126 |

## Prerequisites

- Assembled grid at `data/assembled/` (npy files)
- Local zarr store at `data/assembled/grid.zarr` (for `ex_zarr_local.py`)
- `~/.netrc` credentials (for `ex_zarr_remote.py` with `--include-remote`)

## Adding new examples

When a new capability is added to `load_dataset()`:

1. Create `examples/ex_<capability>.py`
2. Follow the pattern: import, call API, assert on contract, print PASS/FAIL
3. The runner auto-discovers `ex_*.py` files — no registration needed

When a documented gap is resolved, convert its `ex_xfail_*.py` to a passing test.

## Full documentation

- [Consumer data guide](../docs/guides/consumer_data_guide.md)
- [Viewser transition guide](../docs/guides/viewser_transition_guide.md)
- [Zarr consumer guide](../docs/guides/zarr_consumer_guide.md)
