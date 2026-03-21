
# ADR-016: Viewpoint Profiles

**Status:** Accepted
**Date:** 2026-03-21
**Deciders:** Simon Polichinel von der Maase, Claude Code
**Extends:** ADR-014 (Viewpoints as Derived Views)

---

## Context

ADR-014 establishes that viewpoints are disposable, rebuildable, versioned materialized views over the consolidated event store. Each viewpoint applies explicit, configurable rules — survivorship, temporal distribution, uncertainty handling, filtering, nowcasting.

As the research matures, the number of viewpoints will grow to 10+. Each viewpoint is a specific combination of strategy choices. Some will include nowcasting elements, some uncertainty propagation, some both, some neither. Manually tracking which combination of configuration keys produces which viewpoint is unsustainable and error-prone.

Two needs must coexist:
1. **Pick from a menu** — "give me the production-parity viewpoint" without knowing the individual strategy names
2. **Freestyle** — "I want annual_wins survivorship with proportional distribution and no filtering" for one-off experiments

The viewpoint is the last junction where all raw data is accessible. After materialization, version history, uncertainty fields, and alternative temporal distributions are gone. The configuration that produces a viewpoint IS the research decision — it must be named, preserved, and reproducible.

---

## Decision

Viewpoint configurations are managed as **named profiles** — pre-configured sets of research choices that are registered, loaded by name, and recorded in provenance.

> Research choices (strategies, version tag) are separated from runtime plumbing (paths).
> Named profiles are the record — no separate documentation to maintain.
> Freestyle mode always works — profiles are a convenience, not a requirement.

### Profile Mechanics

- Profiles are registered in a module-level registry via `_register(name, **strategy_choices)`
- `load_profile(name, consolidated_path)` returns a complete `ViewpointConfig`
- The version tag automatically matches the profile name
- Overrides allow tweaking individual choices: `load_profile(name, path, distribution_strategy="other")`
- Freestyle mode: construct `ViewpointConfig` directly with any strategy combination
- Provenance records all strategy choices regardless of whether a profile or freestyle was used

### Naming Convention

Profile names are **semantic** — they describe what the viewpoint does, not a sequence number:

- `"production_parity"` — matches production GedLoader behavior
- `"uncertainty_aware"` — propagates date_prec and where_prec into confidence
- `"nowcasting_adjusted"` — applies revision-informed confidence weighting

Not: `"v1"`, `"v2"`, `"v3"`. Opaque version numbers tell researchers nothing about what changed.

---

## Rationale

### Why profiles, not just configs?

A `ViewpointConfig` with 6+ strategy fields gives `N^6` possible combinations. Without named presets, every researcher must know which combination produces the "standard" viewpoint. Profiles make the common case trivial while preserving full flexibility.

### Why a registry, not files?

Profiles are Python code, not TOML/JSON files. This gives:
- Type safety — `load_profile` returns a typed `ViewpointConfig`
- OCP — add profiles with `_register()`, never modify existing ones
- Discoverability — `list_profiles()` shows what's available
- Provenance already captures reproducibility — the ledger records which strategies were used, making the profile format a convenience layer, not the source of truth

### Why semantic names?

When a researcher publishes results using viewpoint data, the methods section should say "we used the production_parity viewpoint" not "we used v3." Semantic names are self-documenting and survive personnel turnover.

---

## Consequences

### Positive

- Researchers pick viewpoints by name without knowing strategy internals
- Combinations are explicit and auditable — the profile IS the specification
- Reproducibility is guaranteed by provenance, not by profile naming
- New profiles are added without modifying existing code (OCP)
- Freestyle experimentation is never constrained

### Negative

- Another registry pattern to understand (though it follows the established pattern from sources, consolidators, builders)
- Profile names become part of the project vocabulary — choosing good names matters
- Risk of profile proliferation if naming discipline isn't maintained

These costs are accepted. The alternative — manual bookkeeping of strategy combinations — is more expensive and error-prone.

---

## Notes

This ADR is **constitutional** — it defines how viewpoint profiles work regardless of data source. The same profile registry pattern applies whether the viewpoint is built from UCDP, ACLED, or any future source.

The profile registry follows the same pattern established by:
- `datafactory_harvester/sources/__init__.py` — source registry
- `datafactory_consolidation/consolidators/__init__.py` — consolidator registry
- `datafactory_viewpoint/builders/__init__.py` — builder registry
- `datafactory_viewpoint/survivorship.py` — strategy registry
- `datafactory_viewpoint/temporal_distribution.py` — strategy registry

This consistency is intentional. The same OCP pattern scales across the entire architecture.
