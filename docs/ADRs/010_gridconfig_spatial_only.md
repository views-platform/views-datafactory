# ADR-010: GridConfig Contains Only Spatial Parameters

**Status:** Accepted
**Date:** 2026-03-17
**Deciders:** Simon Polichinel von der Maase, Claude Code

---

## Context

The metric lab's `GridConfig` (`lab_grid/config.py`) mixes three concerns:

1. **Spatial parameters:** resolution, bounding box, CRS -- the grid's identity
2. **Storage paths:** `data_dir`, `provenance_dir` -- where files live on disk
3. **Remote URLs:** `shapefile_url` -- where to download reference data

This grew organically: someone needed to download the shapefile, so the URL was added to the config. Then provenance needed a directory, so that was added too. The result is a config that knows about both grid mathematics and filesystem layout.

When migrating to views-datafactory, this SRP violation would propagate: the harvester imports GridConfig only to read `shapefile_url`, not because it cares about resolution. Tests must construct a full GridConfig with mock paths even when testing spatial logic.

---

## Decision

In views-datafactory, `GridConfig` contains **only spatial parameters**:

- `resolution` (float)
- `west`, `east`, `south`, `north` (float, bounding box)
- `crs` (str, coordinate reference system)
- Derived properties: `nrow`, `ncol`, `n_cells`

Storage paths and remote URLs are **not** part of `GridConfig`. They are injected at call sites:

```python
# Before (metric lab -- overloaded)
fetch_shapefile(config)  # reads config.shapefile_url, config.data_dir

# After (datafactory -- injected)
fetch_shapefile(url=..., data_dir=..., ledger_path=...)
```

---

## Rationale

- **SRP:** GridConfig defines the coordinate system. Where files live is a separate concern.
- **Testability:** Spatial logic can be tested without constructing paths or URLs.
- **Flexibility:** Different environments (CI, local, production) can use different paths with the same spatial config.
- **ADR-001 alignment:** GridConfig belongs to "The Grid" ontological category, not "Configurations" mixed with "Source Nodes."

---

## Considered Alternatives

### Alternative A: Keep metric lab's GridConfig as-is
- **Pros:** Zero migration friction for metric lab consumers.
- **Cons:** Perpetuates SRP violation. Every consumer pays the cognitive cost of path fields they don't use. Tests are noisier.
- **Reason for rejection:** This is a greenfield repo; we know the destination and can do better.

### Alternative B: Composition (GridConfig + PathConfig)
- **Pros:** Both configs exist, composed where needed.
- **Cons:** Adds a PathConfig class that may not justify its existence as a standalone type. Paths are runtime concerns, not architectural ones.
- **Reason for rejection:** Injecting paths at call sites is simpler and sufficient.

---

## Consequences

### Positive
- GridConfig is purely about grid mathematics
- Harvester and validation functions accept explicit path arguments
- Tests are simpler (no mock paths in spatial tests)
- Aligns with ADR-001 ontology categories

### Negative
- Metric lab consumers migrating to datafactory_priogrid must update call sites to pass paths explicitly
- The default paths (`data/priogrid`, `provenance/priogrid`) now live as constants in `harvester.py`, not in a shared config

These costs are accepted intentionally.

---

## Implementation Notes

- `datafactory_priogrid/grid_config.py` contains the slimmed GridConfig
- `datafactory_priogrid/shapefile_harvester.py` accepts `url`, `data_dir`, `ledger_path` as function arguments with sensible defaults
- `datafactory_priogrid/parity_validation.py:record_parity_result` accepts `ledger_path` as argument
- The metric lab's `lab_grid/config.py` is not modified (it remains as-is for the lab's own use)

---

## References

- `src/datafactory_priogrid/grid_config.py` -- the implementation
- `reports/archive/technical_risk_register_resolved.md` -- expert review identified GridConfig overload
- `docs/CICs/GridConfig.md` -- intent contract for the slimmed config
