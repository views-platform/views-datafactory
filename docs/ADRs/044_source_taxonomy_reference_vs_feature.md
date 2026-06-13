# ADR-044: Source Taxonomy — Reference Infrastructure vs Feature Sources

**Status:** Accepted
**Date:** 2026-06-13
**Deciders:** Simon Polichinel von der Maase, Claude Code
**Applies:** ADR-001 (Ontology), ADR-012 (Four-Layer Data Architecture), ADR-014 (Viewpoints as Derived Views)

---

## Context

ADR-012 describes the system as a graph of independent source nodes. ADR-014 Principle 6 states that viewpoint builders must be pure functions of their own source data — no cross-source dependencies. This principle was formalized after a falsification audit (2026-06-13, probe P-6) revealed that V-Dem's viewpoint reads `data/raw/gaul_admin/iso3_code.parquet` to map ISO3 country codes to PRIO-GRID cells.

The principle as stated is too blunt. It treats all data sources as peers, but they are not:

- **PRIO-GRID** defines the 259,200 cells and temporal backbone. Every source places its data onto this grid.
- **GAUL admin** defines country and admin boundaries and their mapping to grid cells. V-Dem (country-year data), and any future country-level source (WDI, World Bank indicators), needs this mapping to go from country identifiers to pgid.
- **UCDP, ACLED, GHS-POP, GHS-BUILT-S, V-Dem, SHDI** provide feature values — conflict counts, population, built-up surface, democracy scores, development indices — measured on the grid.

The first category defines the *coordinate system*. The second provides *values at those coordinates*. A blanket "no cross-source dependencies" rule conflates these fundamentally different roles and forces either duplicated spatial joins (each country-level source reimplements ISO3→pgid independently) or unprincipled exceptions.

---

## Decision

Data sources in the factory are classified into two categories based on their role:

### Reference sources

Define the spatial and temporal units of analysis — the coordinate system on which all features are expressed.

| Source | What it provides |
|--------|-----------------|
| **PRIO-GRID** | 259,200 cells at 0.5° resolution; temporal backbone (month_id); cell properties (landarea, centroid coordinates) |
| **GAUL admin** | Country/admin boundaries (gaul0, gaul1, gaul2); cell-to-country mappings (gaul0_code, iso3_code); admin hierarchy |

Reference sources are infrastructure. They answer *where* and *when*, not *what*.

### Feature sources

Provide measured or observed values on the coordinate system defined by reference sources.

| Source | What it provides |
|--------|-----------------|
| **UCDP** | Conflict event counts and fatalities (state-based, non-state, one-sided) |
| **ACLED** | Conflict and protest event counts and fatalities by type |
| **GHS-POP** | Population count per cell |
| **GHS-BUILT-S** | Built-up surface area per cell |
| **V-Dem** | Democracy and governance indicators (22 indices) |
| **SHDI** | Subnational human development indices (4 features) |
| **PRIO-GRID static** | Geographic features (landarea, crop types, mineral deposits, travel time, etc.) |

Feature sources answer *what* — what is happening or measured at each coordinate.

### The dependency rule

> Feature sources may depend on reference sources for spatial and temporal mapping.
> Feature sources must NOT depend on other feature sources.
> Reference sources may depend on each other and on Layer 0 infrastructure.

This replaces ADR-014 Principle 6's blanket prohibition with a directed rule: dependencies flow from features toward reference infrastructure, never laterally between features.

| Dependency | Allowed? | Example |
|-----------|----------|---------|
| Feature → Reference | Yes | V-Dem reads GAUL's `iso3_code.parquet` for country→pgid mapping |
| Feature → Feature | **No** | V-Dem must not read ACLED data; SHDI must not read GHS-POP data |
| Reference → Reference | Yes | GAUL uses PRIO-GRID cells for area-majority spatial joins |
| Any → Layer 0 | Yes | All sources use `datafactory_provenance` and `datafactory_http` |

### What "depend on" means

A feature source depends on a reference source when:

1. Its viewpoint builder reads reference data from the filesystem (e.g., a crosswalk Parquet file)
2. Its configuration defaults point to a reference source's data directory
3. Its harvester uses reference source outputs to perform spatial or temporal alignment

All such dependencies must be:

- **Declared in the source's ADR** (e.g., "uses GAUL iso3_code.parquet for country→pgid mapping")
- **Configurable** (the path is a config field, not hardcoded inline)
- **Documented in the source's CIC** as an input dependency

---

## Why two categories, not three

One might argue for a third category: "static features" (PRIO-GRID's landarea, mountain coverage, crop types). These are time-invariant geographic properties attached to grid cells. However, they are already cleanly handled: they are feature values provided by the same source (PRIO-GRID) that defines the coordinate system. PRIO-GRID has a dual role — it defines the cells *and* provides static features about those cells. This dual role is an implementation detail of one source, not an architectural category. No other source needs to read static features to produce its own output, so they do not need special dependency rules.

If a future source requires reading static features from PRIO-GRID (e.g., a source that adjusts its values based on landarea), that would be a feature→feature dependency and should be handled downstream in the model layer, not in the data factory.

---

## Rationale

### The coordinate system is foundational

Every feature source must place its data onto the PRIO-GRID. Some sources (GHS-POP, GHS-BUILT-S) do this via raster aggregation — they have native spatial resolution and aggregate to 0.5° cells. Others (V-Dem, SHDI) have coarser spatial units (countries, admin-1 regions) and need a crosswalk to map to pgid. The crosswalk is reference infrastructure — it defines the mapping between coordinate systems, not a feature value.

Duplicating this mapping per source is the wrong kind of independence. If V-Dem and WDI both produce their own ISO3→pgid crosswalks independently, they might disagree on edge cases (which cells belong to which country). GAUL provides the authoritative mapping (ADR-025); feature sources should use it, not reinvent it.

### Lateral independence prevents hidden couplings

Feature sources must not read each other because:

1. **Independent rebuilding**: if V-Dem's viewpoint depends on ACLED, rebuilding V-Dem requires ACLED to be current. The graph loses its independence property (ADR-012).
2. **Circular risk**: feature→feature dependencies can form cycles (A reads B, B reads A), which makes rebuild ordering undefined.
3. **Scope creep**: cross-feature dependencies are a signal that feature engineering is happening in the data factory, which belongs downstream (model layer).

Reference dependencies do not carry these risks because reference data changes rarely (GAUL releases are infrequent; PRIO-GRID resolution is stable) and reference sources form a small, well-defined set.

### Grounding in established frameworks

Kleppmann & Riccomini (DDIA 2nd ed., 2026) distinguish between *system of record* (authoritative source) and *derived data* (computed from the system of record). Reference sources are systems of record for spatial identity — they define the ground truth for "cell 12345 belongs to country X." Feature sources produce derived data that is expressed in terms of those identities. The dependency direction (derived → authoritative) is the standard data systems pattern.

---

## Consequences

### Positive

- V-Dem's dependency on GAUL is architecturally sanctioned, not an ad hoc exception
- Future country-level sources (WDI, World Bank indicators) have a clear pattern: use GAUL's crosswalk
- The "no cross-source dependencies" principle becomes precise and enforceable
- ADR-014 Principle 6 can be stated in terms of a testable invariant: "feature sources do not read other feature sources"

### Negative

- Reference sources become load-bearing: a bug in GAUL's crosswalk silently affects all country-level feature sources. Mitigated by GAUL's existing test coverage (15 tests for `_compute_cell_polygon_map`, area-majority validation) and the crosswalk's infrequent regeneration.
- Adding a new reference source (unlikely — the coordinate system is stable) requires updating this ADR's taxonomy table.

### ADR-014 amendment

Principle 6 ("No Cross-Source Dependencies") should be restated as:

> A viewpoint builder must not read from other **feature** sources' data. It may read from **reference** sources (PRIO-GRID, GAUL admin) for spatial and temporal mapping, provided the dependency is declared in the source's ADR and configurable in its config class. See ADR-044 for the taxonomy.

This is a refinement, not a reversal. The intent of Principle 6 (prevent hidden couplings between features) is preserved. The blanket prohibition is narrowed to match architectural reality.

---

## Implementation notes

### Current state

| Source | Category | Cross-source reads | Status |
|--------|----------|-------------------|--------|
| PRIO-GRID | Reference | None | Correct |
| GAUL admin | Reference | PRIO-GRID cells (for spatial join) | Correct |
| UCDP | Feature | None | Correct |
| ACLED | Feature | None | Correct |
| GHS-POP | Feature | None | Correct |
| GHS-BUILT-S | Feature | None | Correct |
| V-Dem | Feature | GAUL `iso3_code.parquet` | **Now sanctioned** (was violation of old P6) |
| SHDI | Feature | None (uses own `gdl_to_pgid.parquet`) | Correct |

### Test enforcement

The falsification test `TestNoCrossSourceDependencies::test_vdem_does_not_read_gaul_data` should be rewritten to enforce the correct invariant: feature sources do not read other *feature* sources. Reading reference sources is permitted.

---

## References

- ADR-001: Ontology of views-datafactory (source nodes, the grid)
- ADR-012: Four-Layer Data Architecture (graph, not pipeline)
- ADR-014: Viewpoints as Derived Views (Principle 6, to be amended)
- ADR-025: Country Identity Uses GAUL Codes (GAUL as authoritative identity)
- Kleppmann & Riccomini, *Designing Data-Intensive Applications*, 2nd ed., O'Reilly 2026:
  - Ch.1 pp.10-11: System of record vs derived data
  - Ch.12 pp.499-501: Multiple valid paths through a data system
- GitHub: #168 (C-283)
