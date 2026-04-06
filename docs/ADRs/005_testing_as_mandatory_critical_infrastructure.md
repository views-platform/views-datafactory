
# ADR-005: Testing as Mandatory Critical Infrastructure

**Status:** Accepted
**Date:** 2026-03-17
**Deciders:** Simon Polichinel von der Maase, Claude Code

---

## Context

views-datafactory produces compiled grid data that informs conflict forecasts consumed by humanitarian organizations (OCHA, FAO). In such systems, failure is not limited to crashes or exceptions.

Failures may also include:
- silent data corruption (wrong grid cell assignments, missed schema changes),
- stale compilations served to consumers without detection,
- incorrect provenance records that break the audit chain,
- synthetic data with unrealistic statistical properties used to evaluate models.

Given this, testing is not a convenience or a quality signal.
It is **critical infrastructure** for data integrity.

The absence of rigorous, multi-perspective testing constitutes unacceptable risk.

---

## Decision

This repository treats **testing as mandatory critical infrastructure**.

All non-trivial functionality **must be covered by tests**.

Testing is not limited to correctness under ideal conditions, but must explicitly address:
- adversarial behavior,
- realistic misuse,
- and system robustness under expected operation.

To achieve this, tests are explicitly divided into **three complementary categories**:

- Red team tests (adversarial)
- Beige team tests (realistic, neutral misuse)
- Green team tests (supportive, resilience-oriented)

Each category serves a distinct purpose and **none may substitute for another**.

---

## Test Taxonomy

### Red Team Tests -- Adversarial Testing

Red team tests deliberately attempt to **break, exploit, or misuse the system** by assuming hostile or worst-case behavior.

- **Goal:** expose failure modes, vulnerabilities, unsafe behaviors
- **Mindset:** *"How could this go wrong?"*

Examples in this project:
- UCDP API returning malformed JSON, partial responses, or changed schema (missing required fields)
- Source Parquet files with duplicate event IDs
- Compilation input with NaN values in coordinate arrays
- Synthetic generator configured with degenerate covariance (zero variance, correlation > 1.0)
- Provenance ledger with entries referencing non-existent source files
- Grid config with resolution that does not evenly divide the spatial extent

Red team tests are expected to fail the system until weaknesses are addressed.

---

### Beige Team Tests -- Realistic, Neutral Usage

Beige team tests focus on **boring, realistic, non-adversarial usage patterns** that are neither friendly nor hostile -- but still dangerous if mishandled.

- **Goal:** catch failures caused by normal human behavior
- **Mindset:** *"What will regular users actually do?"*

Examples in this project:
- Running compilation with a config that references a source Parquet file that does not exist
- Harvester config with `end_year < start_year`
- Running the compiler when the provenance digest does not match the source file on disk
- Compiling with an aggregation strategy not implemented for the declared feature set
- Configuring a synthetic generator with a seed but forgetting to specify covariance parameters
- Attempting to use compiled grid output without checking coordinate sidecar arrays

Beige team tests are mandatory for any component that accepts user configuration.

---

### Green Team Tests -- Supportive, Resilience-Oriented Testing

Green team tests focus on **ensuring the system works as intended** under expected conditions and degrades safely.

- **Goal:** ensure reliability, robustness, and trustworthiness
- **Mindset:** *"How do we make this solid?"*

Examples in this project:
- Grid generation produces exactly 259,200 cells with correct pgid sequence (1-indexed, row-major from bottom-left)
- Temporal backbone produces correct month_id sequence for 1989-2024
- Bit-identical compilation: same inputs + same config = identical npy output + identical SHA-256 digest
- Provenance ledger entries contain all required fields (timestamp, source digests, config snapshot, output digest)
- Content digest computation is deterministic and order-independent
- Compiled grid output shape is always (n_cells, n_steps, n_features)
- Coordinate sidecar arrays match the dimensions of the data array

Green team tests are expected to pass continuously and form the backbone of CI.

---

## Relationship to Other ADRs

This ADR reinforces and operationalizes:

- **ADR-001 (Ontology):** tests must respect declared concepts and stability expectations
- **ADR-012 (Four-Layer Architecture):** tests must not bypass architectural boundaries
- **ADR-003 (Authority & Semantics):** tests must fail loudly on semantic ambiguity
- **ADR-004 (Deferred):** future evolution rules must account for test coverage obligations

Testing is a primary mechanism by which these ADRs are enforced.

---

## Enforcement Rules

- Code that meaningfully affects behavior **must not be merged without tests**
- Tests that only cover happy paths are insufficient
- Warning-only behavior in tests is unacceptable for decision-relevant semantics
- If a failure mode is known and untested, it is considered technical debt and must be tracked explicitly

The absence of appropriate tests is valid grounds for blocking a change.

---

## Consequences

### Positive
- Reduced risk of silent data corruption
- Earlier detection of schema drift and stale compilations
- Increased trustworthiness of compiled outputs
- Clearer system boundaries and guarantees

### Negative
- Higher upfront development cost
- Slower iteration if tests are neglected
- Requires cultural discipline and reviewer enforcement

These costs are accepted intentionally.

---

## Implementation Convention

Test categories are organized by **class naming convention**, not by pytest markers:

- `TestXxxGreen` -- green team (correctness, resilience)
- `TestXxxBeige` -- beige team (realistic misuse)
- `TestXxxRed` -- red team (adversarial)

This keeps categories visible in test output without requiring marker infrastructure.

---

## Notes

Testing in this repository is not merely about correctness.

It is about **preventing silent data corruption in systems that inform humanitarian decisions**.

## References

- Kleppmann & Riccomini, *Designing Data-Intensive Applications*, 2nd ed., O'Reilly 2026:
  - Ch.10 p.413: Immutable inputs enable safe rerun — if a bug is found, fix the code and reprocess; the old output is still available
  - Ch.12 pp.524-526: Integrity over timeliness — violations of integrity are permanent and unrecoverable; violations of timeliness are eventual consistency
  - Ch.12 p.526: Deterministic derivation from logged inputs enables reconstruction after bugs
