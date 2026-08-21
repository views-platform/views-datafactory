# Quickstart: Run a datafactory-backed VIEWS model

You are a first-time user. You want to train or run a model from
[views-models](https://github.com/views-platform/views-models) that gets its
data from the VIEWS data factory (not from the legacy viewser backend). This
guide takes you from nothing to a running model.

**What you do NOT need:** this repository, any harvest credentials
(UCDP/ACLED/GDL tokens), or a local copy of the data. Models read features
directly from the remote data server; `views-datafactory` is installed
automatically as a dependency of the model you run.

---

## Step 0 — Two things you must get from a human

Everything else in this guide is self-service. These two are not:

1. **The data server password.** The served data is protected by HTTP basic
   auth. Ask the data factory administrator for the credentials.
2. **Weights & Biases access.** Model runs log to the VIEWS team's
   [wandb](https://wandb.ai) organisation — ask to be added, or create an
   account first at wandb.ai.

## Step 1 — Clone views-models

```bash
git clone https://github.com/views-platform/views-models.git
cd views-models
```

This is the only repository you need.

## Step 2 — Set up data server authentication

Create (or append to) `~/.netrc` with the credentials from Step 0. The
current server address is `204.168.219.108` (this is the one place the
address appears — code never hardcodes it):

```bash
cat >> ~/.netrc << 'EOF'
machine 204.168.219.108
login views
password <the-password-from-step-0>
EOF
chmod 600 ~/.netrc
```

The `chmod 600` is required — tools reject netrc files with open permissions.

**Verify** (should print JSON metadata, not an auth error):

```bash
curl -n http://204.168.219.108/grid.zarr/.zmetadata | head -5
```

## Step 3 — Log in to Weights & Biases

```bash
wandb login
```

Paste your API key from wandb.ai/authorize when prompted.

## Step 4 — Pick a datafactory-backed model and run it

A model uses the datafactory backend when its `configs/config_queryset.py`
returns a dict descriptor with `"source": "views-datafactory"` (viewser models
return a `Queryset` object instead). On views-models `main` today that is
`bright_starship`, `heavy_freighter`, `heavy_strider`, `light_strider` and
`shining_codex` — five of the eighty models there. Example: `light_strider`.

```bash
cd models/light_strider
./run.sh -r calibration -t -e
```

> **If you cloned views-models `main`, this step may fail before it trains**, with a
> `KeyError` about `skip_predictions_delivery` from the config sniffer. That is a
> views-models branch-sync gap, not a datafactory problem: the config key that
> avoids it exists on their `development` for 55 models and has not reached `main`.
> Reported as #455. Nothing in this guide works around it — the fix is theirs to
> ship.
>
> This guide previously named `warring_cleric`, which is datafactory-backed but
> exists **only** on views-models `development`. A clean-install reader following
> `main` could not find it at all. Named models here must be verified against
> `git ls-tree origin/main models/` before being written down.

`run.sh` builds the model's environment on first run — installing
`views-datafactory` from PyPI per the model's `requirements.txt` — then
trains (`-t`) and evaluates (`-e`) on the calibration partition. See the
views-models README for the full flag reference (`-r validation`,
`-f` forecast, etc.).

## Step 5 — Know what just happened (so errors make sense)

The dataloader fetched features straight from the remote zarr store over
HTTP — no local data directory, no harvesting, no 19 GB download. Zarr splits
the grid into chunks and your query downloads only the chunks it touches, so
the first fetch takes minutes, not hours.

Errors you might see, all self-describing:

| Error | Meaning | Fix |
|-------|---------|-----|
| `PermissionError: Authentication failed` | `~/.netrc` missing or wrong | Redo Step 2; check `chmod 600` |
| `ImportError: views-datafactory ... is required ... or too old` | Model env predates the consumer contract | Reinstall using the command in the error message |
| `wandb: ERROR api_key not configured` | Not logged in to wandb | Redo Step 3 |
| Fetch is slow | First-run chunk download, or the monthly pipeline is running on the server (a few hours around the 21st) | Wait; subsequent runs hit the cache |

## Step 6 (optional) — Explore the data directly

You don't need a model to look at the data:

```bash
pip install "views-datafactory[pandas]"
```

The `[pandas]` part is needed because the example below asks for
`output_format="dataframe"`. If you work with FeatureFrames instead
(`output_format="feature_frame"`), plain `pip install views-datafactory`
is enough — pandas is an optional extra, not a requirement.

```python
from datafactory_query import load_dataset
from datafactory_query.defaults import DEFAULT_REMOTE

df = load_dataset(
    region="africa",
    start=480,            # 2020-01 (VIEWS month_id, epoch Jan 1980)
    end=491,              # 2020-12
    features=["ged_sb_best"],
    output_format="dataframe",
    data_dir=DEFAULT_REMOTE.zarr_url,
)
print(df.describe())
```

`DEFAULT_REMOTE` is the canonical server location — always use it instead of
typing a URL, so your code survives a future server move. For the full query
API (regions, time formats, FeatureFrames, country-month aggregation), see the
[consumer data guide](consumer_data_guide.md).

---

## Where to go next

- **[consumer_data_guide.md](consumer_data_guide.md)** — the full
  `load_dataset()` API: formats, regions, partitions
- **[zarr_consumer_guide.md](zarr_consumer_guide.md)** — raw xarray/zarr
  access without installing views-datafactory
- **[credential_setup.md](credential_setup.md)** — all credentials, including
  the harvest tokens you'd need to run the pipeline yourself
- **[consumer_contract.md](consumer_contract.md)** — the stability promise
  behind the column names and formats your model depends on
- **[PLATFORM-001](https://github.com/views-platform/views-appwrite/blob/main/docs/ADRs/platform/PLATFORM-001_identity_secrets_configuration_contract.md)**
  — the identity/secrets contract for the platform's *other* seam (Appwrite
  forecast storage). Running a model touches only this guide's seam; running
  the full delivery chain needs both seams' credentials in one environment
