# datafactory_synthetic -- Architecture

## Purpose

Grid-native synthetic data generation with controllable covariance structure. Produces npy arrays on the same coordinate system and with the same shape contract as compiled authentic data. Used for development, testing, and controlled experimentation -- not for production forecasting. This is a Source Node in the graph architecture (ADR-001) and a Layer 1 package in the dependency DAG (ADR-002).

**Migration source:** `lab_simulation/generators.py` in views-metric-lab (127 LOC). The lab's generators (LatentDataGenerator, EpistemicGenerator) are **panel-native**, not grid-native. This module will be a substantial redesign to operate directly on PRIO-GRID coordinates with more faithful tail distributions.

## Responsibility Boundary

**Owns:**
- Grid-native synthetic data generation (operates on PRIO-GRID cells, not abstract panels)
- Controllable spatial covariance (Matern kernels, exponential, custom)
- Controllable temporal dynamics (AR(1), AR(p), regime-switching)
- Controllable magnitude distributions (GPD/Pareto for heavier tails than Log-Normal)
- Reproducible generation (seed + config = deterministic output)
- Provenance tracking (config hash + seed + generator version)

**Does NOT own:**
- Grid coordinate definition (receives grid parameters via config or file, does not import datafactory_grid)
- Data fetching or harvesting (datafactory_harvester)
- Compilation or format conversion (datafactory_compiler)
- Statistical fidelity validation (future validation node, not this module)
- Model evaluation or calibration (metric lab's domain)

## Dependency Rules

**May import:** `datafactory_core`, numpy
**Must never import:** `datafactory_grid`, `datafactory_harvester`, `datafactory_compiler`, or any consumer

**Design note:** The synthetic module needs grid coordinates (cell positions for spatial correlation). These are passed in via configuration or loaded from file, not obtained by importing `datafactory_grid`. This preserves source node independence (ADR-002).

## Key Concepts

| Concept | Origin / Plan | Description |
|---------|---------------|-------------|
| SyntheticConfig | New (replaces SimulationConfig) | Frozen dataclass: spatial kernel params, temporal AR params, magnitude distribution params, seed, grid dimensions. |
| GridNativeSyntheticGenerator | Replaces LatentDataGenerator | Generates `(n_cells, n_steps, n_features)` directly on PRIO-GRID coordinates. |
| SpatialKernel (Protocol) | New | Pluggable spatial correlation: Matern, exponential, custom. Takes cell positions, returns correlation matrix or applies correlation. |
| TemporalProcess (Protocol) | New | Pluggable temporal dynamics: AR(1), AR(p), regime-switching. Generates time series per cell with specified autocorrelation. |
| MagnitudeDistribution (Protocol) | New (replaces hardcoded Log-Normal) | Pluggable magnitude: GPD, Pareto mixture, Log-Normal. Research question RQ-6 drives the need for heavier tails. |

## Key Differences from Metric Lab

| Aspect | Metric Lab (lab_simulation) | This Module (planned) |
|--------|----------------------------|-----------------------|
| Coordinate system | Abstract panels (n_units x n_steps) | PRIO-GRID native (259,200 cells x time) |
| Spatial correlation | Simple common + individual noise blend | Matern or custom spatial kernels using actual cell positions |
| Tail distribution | Log-Normal (too light per RQ-6) | GPD / Pareto mixture (pluggable) |
| Temporal dynamics | AR(1) only | Pluggable: AR(1), AR(p), regime-switching |
| Output contract | Panel array | Same contract as compiler: (cells, time, features) + coordinate arrays |

## Invariants

- **Same output contract as compiler:** Shape `(n_cells, n_steps, n_features)` with coordinate sidecar arrays (`pgids.npy`, `time_steps.npy`, `feature_names.json`)
- **Deterministic:** seed + config = reproducible output. Fresh RNG per `generate()` call. No global random state.
- **Provenance:** Every generation writes a ledger entry: config hash + seed + generator version -> output digest
- **Config-driven:** All generation parameters come from SyntheticConfig. No hardcoded statistical parameters.
- **Pluggable components:** Spatial kernels, temporal processes, and magnitude distributions are Protocol-based (DIP)
- **No grid import:** Receives grid dimensions/positions via config, not by importing datafactory_grid (ADR-002)
- **Validated config:** `__post_init__` checks: positive variances, valid correlation ranges (0 <= rho <= 1), seed is int, n_cells > 0, n_steps > 0

## CIC Stubs

### SyntheticConfig
**Purpose:** Immutable configuration governing a single synthetic generation run: spatial kernel parameters, temporal process parameters, magnitude distribution parameters, seed, and grid dimensions.
**Non-goals:** Does not generate data. Does not define the grid. Does not validate statistical fidelity of output.
**Key guarantees:** Frozen after construction. `__post_init__` validates: positive variances, valid correlation range, seed is non-negative int, grid dimensions positive. Serializable for provenance (config hash).

### GridNativeSyntheticGenerator
**Purpose:** Generate synthetic conflict data on PRIO-GRID coordinates with controllable spatial correlation, temporal dynamics, and magnitude distributions.
**Non-goals:** Does not define grid coordinates. Does not evaluate statistical fidelity. Does not compile or format output for specific consumers.
**Key guarantees:** Output shape matches declared grid dimensions: `(n_cells, n_steps, n_features)`. Deterministic given seed + config. Coordinate arrays match grid config. Raises on degenerate parameters (zero variance, correlation > 1).
