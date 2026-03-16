# views-datafactory

Data factory for the VIEWS conflict forecasting platform.

## Architecture

The system is a **graph, not a pipeline**:
- **Source nodes** (`datafactory_harvester`, `datafactory_synthetic`) produce raw data independently
- **Compilation edges** (`datafactory_compiler`) transform source data into consumer formats (grid npy now, others later)
- **Consumer nodes** (metric lab, other VIEWS repos) read compiled outputs
- Sources don't know about consumers. Independence is enforced by the filesystem.

## Package Layout (Option B)

Multiple top-level packages under `src/` with `datafactory_` prefix:
- `datafactory_core` — shared foundations, no outbound imports
- `datafactory_grid` — PRIO-GRID spatial + temporal backbone (imports core only)
- `datafactory_harvester` — data ingestion with pluggable sources (imports core only)
- `datafactory_compiler` — source data → grid npy (imports core + grid)
- `datafactory_synthetic` — grid-native synthetic generation (imports core only)

## Tooling

- **Always use `uv run`** to invoke pytest, ruff, and scripts
- Build system: hatchling
- Linting: ruff (line-length 88)
- Type checking: mypy (strict)
- Testing: pytest

## Design Principles

1. **Graph, not pipeline** — sources don't know about consumers
2. **Provenance all the way through** — every node writes JSONL ledger entries (mission-critical)
3. **Config-driven, fail-loud** — frozen dataclasses with `__post_init__` validation
4. **`__init__.py` always defines `__all__`** — public API is explicit
5. **npy now, zarr-ready contracts** — dimension order: (cells, time, features)
6. **No scope creep** — build only what's asked for; don't bolt on convenience features

## Strategic Documents

- `reports/rd_roadmap.md` — Research questions, hypotheses, data agenda, milestones
- `reports/product_development_plan.md` — Users, requirements, architecture, release plan

## Relationship to views-metric-lab

The metric lab (`../views-metric-lab/`) is the first consumer. Grid and harvester code is being migrated from the lab into this repo. The lab retains models, metrics, losses, and evaluation infrastructure.
