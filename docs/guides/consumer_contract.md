# Consumer Contract — what `load_dataset` guarantees

**Governance:** ADR-050. **Contract version:** see
`datafactory_query.CONTRACT_VERSION` /
`tests/fixtures/feature_frame_contract/contract.json` (they are
test-pinned to agree). **Stability promise:** existing format
meanings never change; renames/removals are MAJOR, additions MINOR,
for both the package version and `CONTRACT_VERSION`.

## Two adoption paths (both first-class)

1. **Python import** (requires the views-datafactory wheel — note
   it is heavy: xarray, zarr, shapely, matplotlib):

   ```python
   from datafactory_query import (
       CONTRACT_VERSION,
       OutputFormat,
       is_valid_output_format,
       load_dataset,
   )
   ```

2. **No-install** — read the language-neutral contract document and
   vendor the conformance fixture:
   `tests/fixtures/feature_frame_contract/contract.json` +
   `frame/`. Assert your reader round-trips the fixture and that
   the directory digest equals `contract.json.fixture_digest`
   (regeneration procedure in the fixture README).

## Formats

| `OutputFormat` | Returns | Index / identifiers |
|---|---|---|
| `FEATURE_FRAME` (`"feature_frame"`) | `views_frames.FeatureFrame` | `index.time` = VIEWS month_id (epoch 1980: `(year-1980)*12+month`); `index.unit` = `priogrid_id` |
| `DATAFRAME` (`"dataframe"`) | `pandas.DataFrame` | MultiIndex `(month_id, priogrid_id)`; one column per feature |
| `COUNTRY_MONTH` (`"country_month"`) | `pandas.DataFrame` | MultiIndex `(month_id, country_id)`; grid cells summed per country, declared-extensive features only (ADR-048) |

## Contractual data properties

- **dtype:** FeatureFrame values are float32 (platform-accepted;
  views-baseline C-32 decision).
- **Tensor shape:** `(N, F, S)` — rows, features, samples; `S = 1`
  for observed data (views-frames ADR-012).
- **Identifier semantics:** `unit` is `priogrid_id` at PGM level,
  `country_id` at CM level (views-frames ADR-015; the legacy
  `priogrid_gid` name was retired in datafactory #316 /
  pipeline-core seam #258).
- **Pre-coverage honesty:** queries starting before a source's
  first valid month emit a `UserWarning` naming the affected
  features and the zero-filled months (ADR-047; works on both the
  npy and zarr backends since v1.7.1).

## On-disk FeatureFrame layout

The **byte-level layout is owned by views-frames** (ADR-050
ownership split) — its `save()`/`load()` write and read it, so its
documentation is authoritative. Do not rely on prose descriptions
elsewhere (issue #116's own description drifted within three
weeks). The committed fixture at
`tests/fixtures/feature_frame_contract/frame/` is real `save()`
output and is the executable specification; a regeneration-identity
test alarms the moment a views-frames upgrade changes the layout.

Current layout (informative, fixture is normative): `header.json`
(feature_names, level, metadata) + `identifiers.npz` (time, unit) +
`values.npy`.

## Where things live

- Vocabulary + validator: `src/datafactory_query/output_format.py`
- Canonical data form: `tests/fixtures/feature_frame_contract/contract.json`
- Executable layout spec: `tests/fixtures/feature_frame_contract/frame/` (+ README)
- Governance: `docs/ADRs/050_consumer_contract_export.md`
