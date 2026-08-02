# Guides

Task-oriented how-to guides. Pick by what you're trying to do.

## Start here

| Guide | One line | Audience |
|-------|----------|----------|
| [model_consumer_quickstart.md](model_consumer_quickstart.md) | Nothing → running a datafactory-backed views-models model | First-time users |
| [credential_setup.md](credential_setup.md) | Every credential: UCDP/ACLED/GDL tokens, data server netrc | Everyone |

## Consuming data

| Guide | One line | Audience |
|-------|----------|----------|
| [consumer_data_guide.md](consumer_data_guide.md) | The full `load_dataset()` API: formats, regions, time ranges | Researchers, model builders |
| [zarr_consumer_guide.md](zarr_consumer_guide.md) | Raw xarray/zarr access over HTTP, no package install needed | Researchers |
| [consumer_contract.md](consumer_contract.md) | The ADR-050 stability promise: formats, identifiers, fixture | Consumer-repo maintainers |
| [viewser_transition_guide.md](viewser_transition_guide.md) | Migrating a workflow from viewser to the data factory | Existing VIEWS users |

## Operating the factory

| Guide | One line | Audience |
|-------|----------|----------|
| [server_quickref.md](server_quickref.md) | One-page cheat sheet for the production server | Operators |
| [server_operations.md](server_operations.md) | Runbook: pipeline, locks, heartbeat, incident response | Operators |
- [`monitoring.md`](monitoring.md) — what watches this system and what each thing does **not** watch: the heartbeat (did the pipeline run?), the Better Stack monitor (is the data reachable?), and the freshness workflow (is what we serve current?). Setup of record for ADR-051, including what to configure if the plan is ever upgraded.
| [data_serving_guide.md](data_serving_guide.md) | How the zarr/parquet endpoints are served (Caddy, auth) | Operators |
| [hetzner_deployment_guide.md](hetzner_deployment_guide.md) | Provisioning the server from scratch | Operators |
| [hetzner_deployment_log.md](hetzner_deployment_log.md) | Historical log of the actual deployment | Operators (reference) |
| [publishing_to_pypi.md](publishing_to_pypi.md) | Release runbook: TestPyPI rehearsal, Trusted Publishing | Maintainers |

## Extending the factory

| Guide | One line | Audience |
|-------|----------|----------|
| [data_source_integration_guide.md](data_source_integration_guide.md) | Adding a new data source end-to-end (read before writing code) | Contributors |
