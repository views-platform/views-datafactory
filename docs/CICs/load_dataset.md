# Class Intent Contract: load_dataset

**Status:** Active
**Owner:** Simon Polichinel von der Maase
**Last reviewed:** 2026-08-02
**Related ADRs:** ADR-050 (consumer contract), ADR-047 (temporal anchor), ADR-048 (feature aggregation types), ADR-018 (bounded staleness), ADR-026 (credentials), ADR-011 (fail-loud)

> **Why this contract was missing until now.** `load_dataset` is the primary consumer
> entry point and the surface ADR-050 declares a public contract, yet the base-docs audit
> (2026-08-02) found it had no CIC while 32 config dataclasses did. ADR-006 requires a
> contract for anything that "produces compiled output that downstream models consume" —
> this qualifies twice over. The CICs had been written for the classes that were easy to
> describe, not the ones most depended upon.

---

## 1. Purpose

> Loads a subset of the assembled PRIO-GRID by region, time range, and feature selection,
> and returns it in one of three declared output formats. This is the function downstream
> models call; everything else in this repository exists to make its output correct.

---

## 2. Non-Goals (Explicit Exclusions)

- **Does not transform.** No lags, no rolling windows, no spatial neighbourhood features,
  no normalisation. Feature engineering is a modelling concern and lives downstream
  (see the deliberate xfail in `tests/test_falsification_viewser_replacement.py`).
- **Does not impute.** Missing data stays missing. A `NaN` means the source had no value
  for that cell-month, and the consumer decides what that means.
- **Does not write.** Read-only. It never mutates the store, the ledger, or any cache.
- **Does not own the byte layout.** `FeatureFrame`'s in-memory layout belongs to
  views-frames; this repository owns the *query vocabulary* and hosts the conformance
  fixture (ADR-050).
- **Does not authenticate on the caller's behalf beyond resolution.** It resolves
  credentials via the documented order; it does not prompt, cache, or store them.

---

## 3. Responsibilities and Guarantees

1. **Format is declared, not inferred.** `output_format` must be a member of
   `OutputFormat` (`feature_frame`, `dataframe`, `country_month`). An unknown value raises
   `ValueError` listing the valid set — it never guesses.
2. **Subsetting is applied before materialisation for zarr.** Time range and feature
   selection are pushed into the zarr read so a remote store is not downloaded in full to
   return a slice.
3. **Coverage is announced, not silently padded.** Requesting months beyond the last
   observed data, or before a source's first coverage, emits a `UserWarning` naming the
   months and the source. Zeros that are absence-of-data are never presented as
   observation (ADR-047).
4. **Aggregation respects declared types.** `country_month` sums extensive features and
   refuses to sum intensive ones, using `feature_agg_types` from provenance rather than
   inferring from the feature name (ADR-048, ADR-003).
5. **`gaul0_code` is auto-included** when `country_month` is requested with an explicit
   feature list, because the aggregation cannot be performed without it.

---

## 4. Inputs and Assumptions

| Parameter | Contract |
|---|---|
| `region` | Predefined region, `"global"`, `"land"`, or a GAUL country name. Unknown values raise. |
| `start` / `end` | `"YYYY"`, `"YYYY-MM"`, `"YYYY-MM-DD"`, VIEWS `month_id` int, or `None` for the dataset bound. Inclusive. |
| `features` | Feature names; `None` means all. An unknown name raises `ValueError` listing what is available. |
| `output_format` | Must be an `OutputFormat` value. |
| `data_dir` | A `Path` to an npy directory, or a string path/URL ending `.zarr`. |
| `storage_options` | fsspec options for **remote** stores. Added v1.10.0 (#394) so a new data source can bring its own credentials instead of waiting on a netrc entry on our server. |
| `month_id_epoch` | Defaults to 1980 (VIEWS convention). |

**Assumption:** the assembled grid exists and carries provenance. A store without
`last_valid_month_id` / `first_valid_month_ids` degrades the coverage warnings to silence,
which is why assembly writes them (ADR-047).

### `storage_options` — the non-obvious rule

Passing `storage_options` for a **local** path is an error in xarray, not a no-op. The
implementation therefore resolves to `None` for local stores regardless of what the caller
passed, and only forwards options for remote ones. This was found by a test before the code
shipped: an earlier version forwarded them unconditionally and turned every local zarr read
into a `FileNotFoundError`.

---

## 5. Outputs and Side Effects

- Returns `FeatureFrame` (default), `pandas.DataFrame`, or a country-month `DataFrame`.
- **pandas is an optional extra.** The `dataframe` and `country_month` formats require it.
  Importing this module does not import pandas (guarded by
  `tests/test_import_purity.py`, which probes in a subprocess because an in-process
  assertion is meaningless once pytest has loaded the module).
- Side effects: log lines and `UserWarning`s. Nothing else.

---

## 6. Failure Modes and Loudness

| Condition | Behaviour |
|---|---|
| Unknown `output_format` | `ValueError` with the valid set — loud |
| Unknown feature name | `ValueError` listing available features — loud |
| Unknown region | `ValueError` — loud |
| Missing store / unreadable path | `FileNotFoundError` — loud |
| Requested range exceeds observed data | `UserWarning`, returns zeros for the excess — **loud but not fatal** |
| Requested range precedes a source's coverage | `UserWarning` naming source and months — loud but not fatal |
| Remote store unreachable / 401 | Underlying transport error, with credentials redacted from the message (`datafactory_http.retry`) |

The two warning cases are deliberately not exceptions: a consumer may legitimately want a
window that overhangs coverage. What is forbidden is *silence* (ADR-011).

---

## 7. Boundaries and Interactions

- **Upstream:** the assembled grid written by `scripts/assemble_grid.py`.
- **Downstream:** views-models training scripts; views-pipeline-core.
- **Sibling:** `views-frames` owns `FeatureFrame`; this function constructs one but does
  not define its layout.
- **Credentials:** netrc for the data server, resolved per ADR-026; `storage_options` is
  the caller-supplied alternative.

---

## 8. Examples of Correct Usage

```python
from datafactory_query import load_dataset

ff = load_dataset(region="africa_me", start="2020-01", end="2023-12")

df = load_dataset(region="Ethiopia", start=2020, output_format="country_month")

remote = load_dataset(
    data_dir="https://example.org/grid.zarr",
    storage_options={"client_kwargs": {"headers": {"Authorization": "Bearer ..."}}},
)
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG — format guessed from a string that is not in the vocabulary
load_dataset(output_format="pandas")        # ValueError; use "dataframe"

# WRONG — storage_options on a local path; xarray rejects them
load_dataset(data_dir=Path("data/assembled"),
             storage_options={"anon": True})  # ignored by design, not honoured

# WRONG — treating zeros beyond coverage as observed
ff = load_dataset(end="2030-12")            # warns; the tail is padding, not data
```

---

## 10. Test Alignment

| Guarantee | Test |
|---|---|
| Format vocabulary is closed | `tests/test_query.py` |
| `storage_options` seam, local vs remote | `tests/test_query.py::TestStorageOptionsSeam` |
| Coverage warnings fire | `tests/test_query.py`, `tests/test_falsification_staleness.py` |
| Aggregation type respected | `tests/test_country_month.py` |
| pandas not imported at rest | `tests/test_import_purity.py` (subprocess) |
| Contract version / vocabulary | `tests/test_output_format.py` |

---

## End of Contract
