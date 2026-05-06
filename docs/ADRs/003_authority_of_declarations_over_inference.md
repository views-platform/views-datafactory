
# ADR-003: Authority of Declarations Over Inference

**Status:** Accepted
**Date:** 2026-03-17
**Deciders:** Simon Polichinel von der Maase, Claude Code

---

## Context

In a conflict data factory, the same concept often appears in multiple representations:
- raw event data vs. compiled grid values,
- configuration vs. artifact metadata,
- intended dataset version vs. file path naming conventions.

When these representations diverge, systems often attempt to **infer intent** after the fact.

Such inference is especially dangerous here because:
- compiled grid values inform forecasts used by humanitarian organizations (OCHA, FAO),
- UCDP data undergoes revisions, so the "current" version of a dataset is a declared property, not something to guess from timestamps,
- grid coordinates must come from GridConfig, not from reverse-engineering array shapes,
- and silent errors in provenance tracking undermine the entire audit chain.

A clear rule is required to define **where semantic authority lives**, and how ambiguity is resolved.

---

## Decision

In this repository:

> **All meaningful semantics must be explicitly declared.
> Inference of semantics across component boundaries is forbidden.**

When multiple representations of the same concept exist, **a single source of truth must be designated**.

If required semantics are missing, ambiguous, or contradictory, the system **must not guess**.

---

## Global Invariant: Fail Loud on Semantic Ambiguity

In this repository, **silent failure is considered a bug**.

Whenever required semantics are:
- missing,
- ambiguous,
- contradictory,
- or inconsistent across representations,

the system **must fail loudly and immediately**.

This includes, but is not limited to:
- raising explicit runtime errors,
- failing validation or consistency checks,
- refusing to proceed without explicit declaration.

Warning-only behavior, implicit fallbacks, or "best-effort" inference are **forbidden**
for any decision-relevant semantics.

This rule applies regardless of environment:
development, experimentation, evaluation, or production.

---

## Rules of Semantic Authority

The following rules apply throughout the repository:

- Semantics must be **declared**, not inferred.
- Transformations are owned by the component that performs them.
- Metadata overrides naming conventions.
- Compilation consumes **declared semantics only**.
- No component may guess another component's intent.

Inference is permitted **only within a component's internal logic**, never across component boundaries.

---

## Examples of Forbidden Behavior

- Inferring grid resolution from the shape of a compiled npy array instead of reading `GridConfig.resolution`
- Inferring the UCDP dataset version from a file path instead of from `HarvesterConfig.version`
- Inferring whether a compiled grid is stale by checking file modification times instead of comparing content digests against the provenance ledger
- Inferring the temporal range of compiled data from array length instead of from `TemporalConfig.start_year` / `TemporalConfig.end_year`
- Proceeding with compilation when a source Parquet file exists but its digest does not match the provenance ledger entry
- Inferring that data is "current" because the last harvest was recent, rather than verifying the content digest
- Inferring aggregation strategy from feature names rather than from the declared `CompilationConfig`
- Using a "sensible default" for a missing configuration field rather than raising

If behavior matters, it must be declared.

---

## Consequences

### Positive
- Eliminates silent semantic drift
- Improves reproducibility and debuggability
- Makes disagreements explicit and resolvable
- Enables principled failure under uncertainty
- Protects the provenance chain from implicit assumptions

### Negative
- Requires more explicit configuration and metadata
- Some convenience patterns are disallowed
- Errors may surface earlier and more frequently

These costs are accepted intentionally.

---

## Implementation Notes

The canonical implementation of declaration-over-inference is `src/datafactory_provenance/source_registry.py`. It provides `SourceEntry` (a frozen dataclass declaring each source's name, env vars, features, and SLO), `PIPELINE_SOURCES` (an immutable tuple of all declared sources), and `validate_preflight()` (which fails loud if any declared source is misconfigured or missing required environment variables).

---

## Notes

This ADR does not define:
- what concepts exist (ADR-001),
- or how components depend on each other (ADR-012).

It defines **who is allowed to say what something means**,
and mandates **loud failure over silent misinterpretation**.

## References

- Kleppmann & Riccomini, *Designing Data-Intensive Applications*, 2nd ed., O'Reilly 2026:
  - Ch.4 p.125: Schema versioning database — "a useful thing to have in any case, since it acts as documentation"
  - Ch.4 p.127: Merits of schemas — "the schema is required for decoding, you can be sure that it is up to date (whereas manually maintained documentation may easily diverge from reality)"
  - Ch.4 pp.129-130: Data outlives code — forward compatibility needed because "a value in the database may be written by a newer version of the code, and subsequently read by an older version"
