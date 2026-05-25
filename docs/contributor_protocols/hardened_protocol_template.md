# The Hardened Protocol: Contributor Governance for Data Integrity

This document defines mandatory engineering and numerical standards for the views-datafactory repository. Adherence to this protocol is required for all contributions to guarantee data integrity, provenance fidelity, and deterministic reproducibility.

---

## 1. Core Principles

### A. The Authority of Declarations (ADR-003)
**"Never infer; only trust declarations."**
All meaningful semantics (grid configurations, harvester parameters, compilation configs, seeds) must be explicitly declared in frozen dataclass configurations validated at construction time.
- **Prohibited:** File-path-based logic, array-shape inference, timestamp-based staleness detection.
- **Requirement:** If a parameter affects compiled output identity, it must be a mandatory field in the relevant config dataclass.

### B. The Fail-Loud Mandate (ADR-008, ADR-011)
**"A crash is a successful defense of data integrity."**
Silent failures, implicit fallbacks, and "best-effort" corrections are forbidden.
- **Requirement:** Violations of schema, digest, configuration, or shape invariants must raise an explicit exception immediately.
- **Prohibited:** Using `nan_to_num`, silent clipping, default substitution for missing config fields, or proceeding when digests do not match.

### C. The Numerical Airlock
All data entering the system must pass through validation boundaries.
- **Requirement:** Grid data arrays use `float32`. Coordinate arrays use `int32` (pgids) and `datetime64[M]` (time steps).
- **Requirement:** Detect and raise errors on NaN or Inf values at every boundary (harvest validation, compilation input, compilation output).
- **Requirement:** Shape validation at every boundary: compiled output is always `[T, H, W, C]` (time, height=360, width=720, channels/features).

### D. Deterministic Compilation
**"Same inputs + same config = bit-identical output."**
- **Requirement:** Compilation must be deterministic. The SHA-256 digest of the output must be reproducible given the same source data and config.
- **Requirement:** Synthetic generation must be deterministic given seed + config. Fresh RNG per `generate()` call.
- **Prohibited:** Order-dependent aggregation, floating-point accumulation order sensitivity, or any source of non-determinism in compilation.

---

## 2. Contributor Requirements

### Adding a New Component (Source, Aggregation Strategy, Output Format)
1. **Define the Config:** Register mandatory parameters in a frozen dataclass with `__post_init__` validation.
2. **Respect the DAG:** Place the component in the correct package per ADR-002 topology rules.
3. **Create CIC:** Write the Class Intent Contract (ADR-006) if the component is non-trivial.
4. **Write Tests:** Cover green (correctness), beige (misconfiguration), and red (adversarial) scenarios per ADR-005.
5. **Record Provenance:** Every operation that produces output must append a JSONL ledger entry.

---

## 3. Mandatory Testing Taxonomy (ADR-005)

Every Pull Request must include tests covering the following three perspectives:

### Green Team (Stability & Correctness)
* **Goal:** Ensure the system works as intended and remains stable.
* **Examples:** Grid produces 259,200 cells, bit-identical compilation, correct pgid sequence, provenance entries contain all required fields.

### Beige Team (Configuration & Human Error)
* **Goal:** Catch failures caused by common configuration mistakes or missing parameters.
* **Examples:** Missing config fields, end_year < start_year, digest mismatch at compilation input, aggregation strategy not implemented for declared features.

### Red Team (Adversarial)
* **Goal:** Expose failure modes by deliberately trying to make the system produce wrong data silently.
* **Examples:** Malformed API responses, duplicate event IDs in source data, NaN injection in coordinate arrays.

---

## 4. Operational Invariants

- **Content-Addressed Provenance:** Every compiled output has a SHA-256 digest. Every provenance entry links input digests + config to output digest. Rebuild fidelity: deleting outputs and rebuilding from raw data + provenance produces bit-identical results.
- **Append-Only Ledgers:** Provenance JSONL files are append-only and git-tracked. Entries are never modified or deleted.

---

**"In this repository, we value data integrity over convenient execution."**
