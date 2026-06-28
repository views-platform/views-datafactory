# ADR-048: Declared Feature Aggregation Types

**Status:** Accepted
**Date:** 2026-06-28
**Deciders:** Simon Polichinel von der Maase, Claude Code
**Related:** ADR-003 (declarations over inference), ADR-040 (count conservation), ADR-045 (data soundness invariants)

---

## Context

ADR-045 establishes a three-way feature type distinction — extensive (counts, sum-meaningful), intensive (indices, sum-meaningless), and static (categorical) — and ADR-040 scopes count conservation to extensive features only. But neither ADR prescribes *where this classification is declared* or *how it flows to downstream consumers*.

In practice, three modules infer feature types from name prefixes:

| Module | Prefix list | Purpose |
|--------|-------------|---------|
| `grid_to_country_month.py` | `_INTENSIVE_PREFIXES` | Warn when intensive features are summed |
| `_conservation.py` | `_EXTENSIVE_PREFIXES` | Identify which features to conservation-check |
| `dataset.py` | `_SOURCE_PREFIXES` | Map provenance keys to features for pre-coverage warnings |

This is a direct violation of ADR-003 line 110, which lists "Inferring aggregation strategy from feature names rather than from the declared CompilationConfig" as **forbidden behavior**.

The prefix lists are also buggy: `_INTENSIVE_PREFIXES` contains `"ghs_built_"` which does not match the actual feature name `"ghsbuilts_built_area"`, silently disabling the intensive warning for GHS-BUILT-S. It also contains dead entries (`"healthindex"`, `"edindex"`, `"incindex"`) already matched by the `"shdi"` prefix.

The root cause is that `SourceEntry` declares each source's features but not their aggregation types. `FeatureSpec.strategy` in `CompilationConfig` carries per-cell aggregation semantics (`count`/`sum_field`/`max_field`) but this metadata evaporates at the assembly boundary — it is never written to provenance.

---

## Decision

### 1. Feature type taxonomy

Every feature in the assembled grid belongs to exactly one type:

| Type | Semantics | CM aggregation | Conservation | Examples |
|------|-----------|----------------|--------------|----------|
| `extensive` | Counts or sums; sum across cells is meaningful | Sum | Yes (ADR-040) | `ged_sb_best`, `acled_count`, `ghspop_pop_count` |
| `intensive` | Indices or ratios; sum across cells is meaningless | Forbidden (fail-loud) | No | `vdem_*`, `shdi_*`, `ghsbuilts_built_area` |
| `static` | Categorical or geographic identifiers | Not aggregated | No | `gaul0_code`, PRIO-GRID static variables |

### 2. Single source of truth: `SourceEntry.feature_agg_types`

`SourceEntry` in the source registry (`source_registry.py`) gains a `feature_agg_types: tuple[str, ...]` field. Each entry is one of `"extensive"`, `"intensive"`, `"static"`. The tuple must have the same length as `features`, with a 1:1 positional correspondence.

`get_feature_agg_type_map()` returns a `dict[str, str]` mapping every feature name to its declared type.

### 3. Assembly propagation

`assemble_grid.py` writes `feature_agg_types` to provenance alongside `feature_names`, and writes `feature_agg_types.json` to the output directory alongside `feature_names.json`. The types are read from the registry via `get_feature_agg_type_map()`.

### 4. Consumer contract

Downstream consumers read `feature_agg_types` from provenance. No consumer may infer feature types from name prefixes, column position, or any other heuristic.

`grid_to_country_month()` accepts a `feature_agg_types` parameter and raises `ValueError` if intensive features are included — fail-loud per ADR-003/ADR-011, not warn-and-proceed.

`assert_cm_conservation()` accepts a `feature_agg_types` parameter and derives extensive feature indices from declared types instead of prefix matching.

### 5. Prefix lists deleted

`_INTENSIVE_PREFIXES`, `_EXTENSIVE_PREFIXES`, and `_SOURCE_PREFIXES` are deleted. No replacement prefix list is created. `_SOURCE_DISPLAY_NAMES` is retained — it maps source keys to human-readable names for warning messages, not for inference.

---

## Feature Classification (79 features)

| Source | Count | Type | Features |
|--------|-------|------|----------|
| UCDP | 6 | `extensive` | `ged_sb_count`, `ged_sb_best`, `ged_ns_count`, `ged_ns_best`, `ged_os_count`, `ged_os_best` |
| ACLED | 8 | `extensive` | `acled_count`, `acled_battles`, `acled_explosions`, `acled_vac`, `acled_protests`, `acled_riots`, `acled_strategic`, `acled_fatalities` |
| GHS-POP | 1 | `extensive` | `ghspop_pop_count` |
| GHS-BUILT-S | 1 | `intensive` | `ghsbuilts_built_area` |
| V-Dem | 22 | `intensive` | All `vdem_*` features |
| SHDI | 4 | `intensive` | `shdi_shdi`, `shdi_healthindex`, `shdi_edindex`, `shdi_incindex` |
| PRIO-GRID Static | 34 | `static` | All PRIO-GRID static variables |
| GAUL Admin | 3 | `static` | `gaul0_code`, `gaul1_code`, `gaul2_code` |

---

## Consequences

### Positive

- Eliminates three ADR-003 violations and the `ghs_built_` typo bug
- Adding a new data source automatically propagates its feature types to all consumers — no manual prefix list maintenance
- Fail-loud behavior for intensive features prevents silent production of meaningless sums
- Conservation checks automatically cover new extensive features without code changes

### Negative

- `SourceEntry` gains a new required field; existing callers that construct `SourceEntry` with features must also provide `feature_agg_types`
- Backward compatibility requires a migration period where `feature_agg_types=None` falls back to old behavior

These costs are accepted. The migration period is bounded to one PR.

---

## Implementation Notes

The canonical implementation is the `feature_agg_types` field on `SourceEntry` in `src/datafactory_provenance/source_registry.py`, propagated through `scripts/assemble_grid.py` into provenance, and consumed by `src/datafactory_adapters/grid_to_country_month.py` and `src/datafactory_adapters/_conservation.py`.
