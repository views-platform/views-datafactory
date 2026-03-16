<div style="width: 100%; max-width: 1500px; height: 400px; overflow: hidden; position: relative;">
  <img src="https://github.com/user-attachments/assets/1ec9e217-508d-4b10-a41a-08dface269c7" alt="VIEWS Twitter Header" style="position: absolute; top: -50px; width: 100%; height: auto;">
</div>

# views-datafactory

**Data factory for the VIEWS conflict forecasting platform — harvesting, grid construction, compilation, and synthetic generation.**

Part of the [VIEWS Platform](https://github.com/views-platform) ecosystem.

---

## Table of Contents

- [Overview](#overview)
- [Role in VIEWS Platform](#role-in-views-platform)
- [Architecture](#architecture)
- [Packages](#packages)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Strategic Documents](#strategic-documents)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

views-datafactory provides the data foundation for conflict forecasting in the VIEWS platform. It handles the full lifecycle of spatiotemporal conflict data — from raw ingestion through to compiled grid arrays ready for model consumption.

The system is designed as a **graph of independent nodes**, not a linear pipeline. Source nodes (harvesters, synthetic generators) produce data independently. Compilation edges transform source data into consumer-specific formats. Consumer nodes read compiled outputs. This architecture ensures that adding a new data source or output format never requires changing existing components.

### Key Capabilities

- **Auditable data harvesting** with schema validation, drift detection, and JSONL provenance ledgers
- **PRIO-GRID spatial backbone** — pure-numpy generation of the standard 259,200-cell global grid at 0.5° resolution, validated cell-by-cell against the official PRIO reference shapefile
- **Temporal backbone** with VIEWS month_id adapters (epoch: January 1980)
- **Deterministic compilation** of raw event data onto the spatiotemporal grid as npy arrays
- **Synthetic data generation** with controllable spatiotemporal covariance structure
- **End-to-end provenance** — every value in a compiled grid is traceable back to the specific source records and compilation config that produced it

---

## Role in VIEWS Platform

views-datafactory is the upstream data provider for the VIEWS forecasting pipeline. It produces the compiled grid arrays that models consume for training and inference.

### Integration with Other Repositories

- **[views-metric-lab](https://github.com/views-platform/views-metric-lab):** First consumer — uses compiled grids for evaluation metric research and model stress-testing
- **[views-hydranet](https://github.com/views-platform/views-hydranet):** Will consume compiled grids for production neural forecasting (HydraNet v2)
- **[views-pipeline-core](https://github.com/views-platform/views-pipeline-core):** Central pipeline infrastructure — may depend on views-datafactory for standardised data access
- **[views-evaluation](https://github.com/views-platform/views-evaluation):** May consume compiled grids for benchmarking

### Data Flow

```
UCDP/GED API ──→ datafactory_harvester ──→ Raw Parquet + Provenance
                                                    │
PRIO-GRID ──────→ datafactory_grid ─────────────────┤
                                                    │
                                           datafactory_compiler ──→ Compiled grid.npy
                                                    │
                  datafactory_synthetic ────────────→ Synthetic grid.npy
                                                    │
                                           ┌────────┴────────┐
                                           │   Consumers     │
                                           │  (metric lab,   │
                                           │   hydranet,     │
                                           │   pipeline)     │
                                           └─────────────────┘
```

---

## Architecture

The architecture is a **graph**, not a pipeline. Each node is a self-contained package with explicit dependencies:

```
Level 0 — Foundation (no internal imports):
  datafactory_core

Level 1 — Independent nodes (import only core):
  datafactory_grid          Spatial + temporal backbone
  datafactory_harvester     Data ingestion with pluggable sources
  datafactory_synthetic     Grid-native synthetic generation

Level 2 — Compilation (imports core + grid, reads files from Level 1):
  datafactory_compiler      Source data → populated grid arrays
```

**Dependency rules:**
- `datafactory_core` imports nothing internal
- `datafactory_grid`, `datafactory_harvester`, `datafactory_synthetic` import only from `datafactory_core`
- `datafactory_compiler` imports `datafactory_core` and `datafactory_grid`; reads harvester/synthetic outputs as **files**, not code imports
- Independence is enforced by the filesystem — each package is a separate top-level module

### Design Principles

| Principle | Description |
|-----------|-------------|
| **Graph, not pipeline** | Sources don't know about consumers. Compilation edges are consumer-driven. |
| **Provenance all the way through** | Every node that produces data writes a JSONL ledger entry. Mission-critical. |
| **Config-driven, fail-loud** | Frozen dataclasses with `__post_init__` validation. No silent defaults. |
| **npy now, zarr-ready** | Dimension order: `(cells, time, features)`. Coordinate arrays shipped alongside data. |

---

## Packages

| Package | Purpose | Status |
|---------|---------|--------|
| `datafactory_core` | Shared foundations — base configs, provenance utilities | Scaffold |
| `datafactory_grid` | PRIO-GRID spatial + temporal backbone (259,200 cells, monthly) | Migrating from metric lab |
| `datafactory_harvester` | Data harvesting framework with pluggable sources (UCDP/GED) | Migrating from metric lab |
| `datafactory_compiler` | Compilation node — places source data onto grid, outputs npy | Planned |
| `datafactory_synthetic` | Synthetic data generation with controlled covariance structure | Planned |

---

## Project Structure

```
views-datafactory/
├── pyproject.toml                              # hatchling + uv
├── CLAUDE.md                                   # AI assistant context
├── src/
│   ├── datafactory_core/                       # Shared foundations
│   │   └── __init__.py
│   ├── datafactory_grid/                       # Spatial + temporal backbone
│   │   └── __init__.py
│   ├── datafactory_harvester/                  # Data ingestion framework
│   │   ├── __init__.py
│   │   └── sources/                            # One module per data source
│   │       └── __init__.py
│   ├── datafactory_compiler/                   # Source data → grid npy
│   │   └── __init__.py
│   └── datafactory_synthetic/                  # Synthetic generation
│       └── __init__.py
├── tests/                                      # Test suite
│   └── test_core.py
├── reports/                                    # Strategic documents
│   ├── rd_roadmap.md                           # R&D roadmap
│   └── product_development_plan.md             # Product development plan
├── provenance/                                 # JSONL ledgers (git-tracked)
└── data/                                       # Raw + compiled data (gitignored)
```

---

## Installation

```bash
# Clone the repository
git clone https://github.com/views-platform/views-datafactory.git
cd views-datafactory

# Install with uv
uv sync

# Verify
uv run pytest -v
```

> **Note:** This project uses [uv](https://github.com/astral-sh/uv) for dependency management and [hatchling](https://hatch.pypa.io/) as the build backend.

---

## Quick Start

```python
# Import any package directly — they are independent top-level modules
from datafactory_grid import GridConfig
from datafactory_harvester import HarvesterConfig

# Each package's public API is defined in __init__.py via __all__
```

---

## Strategic Documents

The `reports/` directory contains living documents that define the project's direction:

- **[R&D Roadmap](reports/rd_roadmap.md)** — Research questions, hypotheses, data agenda, experimentation framework, and milestones. Focuses on what must be *discovered*.
- **[Product Development Plan](reports/product_development_plan.md)** — Users, requirements, system architecture, data infrastructure, and release plan. Focuses on what must be *built*.

---

## Contributing

Contributions are welcome. Please consult the [VIEWS Platform contributing guidelines](https://github.com/views-platform) before submitting pull requests.

When adding new packages, follow the existing `datafactory_*` naming convention and ensure the new package:
- Has an `__init__.py` with `__all__` defined
- Is listed in `pyproject.toml` under `[tool.hatch.build.targets.wheel] packages`
- Imports only from `datafactory_core` (or core + grid for compilation nodes)
- Has corresponding tests in `tests/`

---

## License

This project is part of the VIEWS Platform. See [LICENSE](LICENSE) for details.

---

## Acknowledgements

Built as part of the [VIEWS](https://viewsforecasting.org/) (Violence & Impacts Early-Warning System) project, providing early warning for conflict to support humanitarian response and prevention.

Data sources:
- **[UCDP/GED](https://ucdp.uu.se/)** — Uppsala Conflict Data Program / Georeferenced Event Dataset
- **[PRIO-GRID](https://grid.prio.org/)** — Peace Research Institute Oslo global grid structure
