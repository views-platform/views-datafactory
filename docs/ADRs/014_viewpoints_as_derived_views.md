
# ADR-014: Viewpoints as Derived Views

**Status:** Accepted
**Date:** 2026-03-20
**Deciders:** Simon Polichinel von der Maase, Claude Code

---

## Context

The consolidated event store (ADR-013) preserves every version of every event from every source. This is deliberately unopinionated — it makes no choices about which version is "right" or how to handle temporal ambiguity.

But downstream consumers (the grid compiler, models, evaluations) need a single, clean view: one row per event (or event-month), with definitive values. Producing this view requires opinionated decisions:

- **Survivorship:** When annual and candidate versions of the same event disagree, which wins?
- **Temporal distribution:** How should summary events spanning multiple months be distributed?
- **Uncertainty handling:** Should `date_prec` influence temporal assignment? Should `where_prec` influence spatial assignment?
- **Field selection:** Which fields propagate to the output?

These decisions are research questions, not infrastructure questions. They change as understanding deepens. The rules used today may be wrong tomorrow — and when they change, the underlying data must not need to be re-harvested or re-consolidated.

This motivates treating these opinionated views as **viewpoints**: disposable, rebuildable, and versioned perspectives on the consolidated data. What master data management calls a "golden record" — an authoritative materialized view produced by explicit survivorship rules — this architecture calls a **viewpoint**, because different opinionated perspectives are expected to coexist over the same base data, and the name must communicate that to contributors.

---

## Decision

A viewpoint (Layer 3, ADR-012) is a disposable, rebuildable, versioned materialized view over the consolidated event store. It is implemented by the `datafactory_viewpoint` package.

> The viewpoint builder applies explicit, configurable rules to produce a single view.
> When rules change, the viewpoint is rebuilt from the consolidated store.
> Raw data is sacred. Derived views are disposable.

---

## Principles

### 1. Volatile by Design

The viewpoint builder is expected to change frequently. New survivorship rules, new temporal distribution methods, new uncertainty models — these are research outputs, not bugs. The architecture must make this evolution safe and cheap.

A change to viewpoint rules must not require:
- re-harvesting data,
- re-consolidating the event store,
- modifying the compiler, or
- coordinating with other layers.

### 2. Configurable Survivorship

Rules for choosing between versions of the same event must be:

- **Explicit** — stated in configuration, not hardcoded in logic
- **Configurable** — different rule sets can be applied to the same consolidated store
- **Auditable** — the viewpoint output records which rules produced it

The viewpoint builder never silently prefers one version over another. Every choice is traceable to a declared rule.

### 3. Rebuildable

A viewpoint can be deleted and rebuilt from the consolidated store at any time. This is not an error recovery path — it is the normal operating mode.

Implications:
- A viewpoint must not contain information that is absent from the consolidated store
- The viewpoint builder must be a pure function of (consolidated store + configuration)
- Caching is permitted but must not change semantics

### 4. Versioned

Viewpoint configurations are versioned. Multiple viewpoints can coexist:

- **v1:** "Annual wins, latest candidate for trailing window, fix_summary_events, date_end binning" (production parity target)
- **v2:** "Uncertainty-weighted temporal distribution, proportional fatality spread"
- **v3:** "Nowcasting-adjusted with revision-informed confidence"

Each version is a different materialization of the same consolidated store.

### 5. What the Viewpoint Builder Owns

| Responsibility | Description |
|---------------|-------------|
| Survivorship rules | Which version of an event wins when sources disagree |
| Temporal distribution | How summary events (spanning multiple months) are spread across time |
| Uncertainty handling | Whether and how `date_prec`, `where_prec`, `low`/`high` influence the output |
| Field selection | Which fields from the consolidated store propagate to the viewpoint |
| Month assignment | Whether `date_start` or `date_end` determines the event's month |

### 6. Provenance

The viewpoint output must record:

- Which consolidated store it was built from (content digest)
- Which configuration version was applied
- Timestamp of materialization
- Content digest of the output

Per ADR-008, viewpoint build failures must be logged and raised.

---

## Grounding in Established Frameworks

| Framework | Principle Applied |
|-----------|------------------|
| **MDM Golden Record** (Dreibelbis et al.) | Survivorship rules must be explicit, configurable, auditable. Raw sources preserved. |
| **CQRS** (Young) | Viewpoint = read model (materialized view). Consolidation = write model. Separate concerns. |
| **ISO GUM** (JCGM 100:2008) | Uncertainty metadata must propagate through transformations, not be silently discarded |
| **Materialized views** (database theory) | A derived, rebuildable projection of the source of truth. Disposable by definition. |

---

## Consequences

### Positive

- Research iteration is safe: change rules, rebuild, compare
- Multiple viewpoint versions enable A/B evaluation
- No data loss when rules change
- Clear separation of stable infrastructure from volatile research logic
- Provenance chain extends from raw source through viewpoint to compiled output

### Negative

- Additional computational cost to rebuild viewpoints
- Contributors must understand which decisions live at Layer 3 vs. Layer 2 or Layer 4
- Configuration versioning adds complexity

These costs are accepted. The alternative — embedding volatile research decisions in stable infrastructure — is more expensive in the long run.

---

## Notes

This ADR is **constitutional** — it defines principles for viewpoint building that apply regardless of data source. Source-specific viewpoint rules (e.g., UCDP survivorship logic, summary event handling) are defined in project-specific ADRs (ADR-015+).

This ADR does not prescribe:
- specific survivorship algorithms,
- specific output formats,
- specific configuration schemas,
- or specific versioning schemes.

Those are implementation decisions that evolve with the research.
