
# ADR-000: Use of Architecture Decision Records (ADRs)

**Status:** Accepted
**Date:** 2026-03-17
**Deciders:** Simon Polichinel von der Maase, Claude Code
**Informed:** All contributors

---

## Context

views-datafactory is the data foundation for the VIEWS conflict forecasting platform, a system whose compiled outputs inform humanitarian early warning consumed by organizations including OCHA and FAO.

This project involves:
- long-lived code with evolving research requirements,
- migration of proven patterns from the metric lab into a greenfield architecture,
- multiple contributors (carbon-based and silicon-based),
- and architectural decisions whose consequences propagate into downstream forecasting models.

Many important decisions in such systems are:
- Made under uncertainty
- Revised over time
- Obvious to those present at the time, but opaque later
- Revisited implicitly, often leading to regressions or duplicated debate

Without a shared record of *why* decisions were made, the project risks:
- Re-litigating settled questions (e.g., graph vs. pipeline, npy vs. zarr)
- Accidental reversals of critical design choices (e.g., source independence)
- Accumulating invisible technical and conceptual debt
- Losing institutional memory as contributors change

We therefore need a lightweight but rigorous mechanism to document **significant decisions**, their **rationale**, and their **consequences**.

---

## Decision

We will use **Architecture Decision Records (ADRs)** to document significant technical, architectural, and conceptual decisions in this project.

ADRs are:
- Written in Markdown
- Stored in the repository under `docs/ADRs/`
- Numbered sequentially
- Treated as first-class project artifacts

An ADR records **a decision**, not a discussion or a design proposal.

---

## What Is an ADR?

An ADR is a short, structured document that captures:
- The context in which a decision was made
- The decision itself
- The rationale behind it
- The alternatives that were considered
- The consequences (positive and negative)

An ADR answers the question:

> *"Why is the system the way it is?"*

---not just *"How does it work?"*

---

## When to Write an ADR

Write an ADR when making a decision that:
- Affects system architecture or data layout
- Constrains future design choices
- Changes assumptions or invariants
- Introduces or accepts technical debt
- Is likely to be questioned or revisited later
- Has non-obvious trade-offs

Examples in this project include:
- Choosing npy over zarr for compiled grid output
- Choosing a graph architecture over a linear pipeline
- Choosing JSONL append-only ledgers over database-backed provenance
- Choosing SHA-256 content digests as the staleness detection mechanism
- Choosing filesystem-mediated coupling over code imports between sources and consumers
- Choosing frozen dataclasses with `__post_init__` validation for all configuration

Do **not** write ADRs for:
- Routine refactors
- Purely local implementation details
- Temporary experiments (unless they become permanent)

---

## What an ADR Is *Not*

An ADR is **not**:
- A full design document
- A tutorial or user guide
- A speculative roadmap
- A substitute for code comments
- A place to argue indefinitely

The goal is clarity and finality, not exhaustiveness.

---

## Structure and Template

All ADRs must follow the standard ADR template defined in this repository (`docs/ADRs/adr_template.md`).

The template enforces:
- Clear separation between context, decision, and rationale
- Explicit consideration of alternatives
- Honest accounting of consequences
- Traceability to code and discussions

Consistency matters more than perfection.

---

## Lifecycle of an ADR

ADRs have a status that reflects their lifecycle:

- **Proposed** -- decision under consideration
- **Accepted** -- decision is active and authoritative
- **Superseded** -- replaced by a newer ADR
- **Deprecated** -- decision remains but should no longer be used

Decisions are never deleted.
If a decision changes, it is **superseded**, not erased.

---

## Relationship to Code

ADRs and code must agree.

- Code should implement the decision described in the ADR
- Significant deviations require a new ADR or an update
- ADRs should be referenced from code, issues, or PRs when relevant

If code and ADRs disagree, the ADR is the source of truth -- or a new ADR is required.

---

## Why We Use ADRs

We use ADRs to:
- Preserve institutional memory
- Reduce cognitive load for maintainers
- Make trade-offs explicit
- Enable principled disagreement
- Support onboarding and handover
- Prevent silent erosion of core design principles

ADRs are a tool for **engineering discipline under uncertainty**.

---

## Consequences

### Positive
- Clearer decision-making
- Fewer repeated debates
- Easier onboarding
- Better long-term coherence

### Negative
- Small upfront cost in writing
- Requires discipline to maintain
- Forces explicitness where ambiguity may feel easier

These costs are accepted intentionally.

---

## References

- `docs/ADRs/adr_template.md`
- `CLAUDE.md` (project instructions)
- `reports/product_development_plan02.md`
