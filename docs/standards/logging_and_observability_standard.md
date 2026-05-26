# Logging & Observability Standard

**Status:** Active
**Governing ADRs:** ADR-003 (Authority of Declarations), ADR-005 (Testing), ADR-008 (Observability and Explicit Failure)

---

## 1. Purpose

This document defines operational standards for:

- Logging behavior
- Log levels
- Error propagation patterns
- Observability expectations

This standard operationalizes:

> Structural failures must be raised explicitly and logged persistently. (ADR-008)

It does not redefine architectural principles.

---

## 2. Core Principles

### 2.1 Fail Loud and Persist

- Structural failures must:
  - be logged at `ERROR` or higher
  - be raised as exceptions
- Logging is not a substitute for raising.
- Raising is not a substitute for logging.

Silent degradation is prohibited.

### 2.2 Provenance Ledgers as Primary Observability

In views-datafactory, the JSONL provenance ledgers (`provenance/`) are the primary observability mechanism:

- `provenance/priogrid/ingestion_ledger.jsonl` -- grid shapefile provenance (implemented)
- `provenance/ucdp_annual/ingestion_ledger.jsonl` -- UCDP annual harvest provenance (implemented)
- `provenance/ucdp_candidate/ingestion_ledger.jsonl` -- candidate monthly provenance (implemented)
- `provenance/consolidation/ledger.jsonl` -- consolidation provenance (implemented)
- `provenance/viewpoint/ledger.jsonl` -- viewpoint provenance (implemented)
- `provenance/compilation/ledger.jsonl` -- one entry per compilation (implemented)
- `provenance/acled/ingestion_ledger.jsonl` -- ACLED harvest provenance (implemented)
- `provenance/consolidation/acled_ledger.jsonl` -- ACLED consolidation provenance (implemented)
- `provenance/viewpoint/acled_v1_ledger.jsonl` -- ACLED viewpoint provenance (implemented)
- `provenance/ucdp_dot9/ingestion_ledger.jsonl` -- UCDP .9 harvest provenance (implemented)
- `provenance/compilation/acled_ledger.jsonl` -- ACLED compilation provenance (implemented)
- `provenance/ghspop/ingestion_ledger.jsonl` -- GHS-POP harvest provenance (implemented)
- `provenance/ghsbuilts/ingestion_ledger.jsonl` -- GHS-BUILT-S harvest provenance (implemented)
- `provenance/gaul_admin/ingestion_ledger.jsonl` -- GAUL admin harvest provenance (implemented)
- `provenance/priogrid_static/ingestion_ledger.jsonl` -- PRIO-GRID static harvest provenance (implemented)
- `provenance/viewpoint/ghspop_v1_ledger.jsonl` -- GHS-POP viewpoint provenance (implemented)
- `provenance/viewpoint/ghsbuilts_v1_ledger.jsonl` -- GHS-BUILT-S viewpoint provenance (implemented)
- `provenance/compilation/ghspop_ledger.jsonl` -- GHS-POP compilation provenance (implemented)
- `provenance/compilation/ghsbuilts_ledger.jsonl` -- GHS-BUILT-S compilation provenance (implemented)
- `provenance/vdem/ingestion_ledger.jsonl` -- V-Dem harvest provenance (implemented)
- `provenance/viewpoint/vdem_v1_ledger.jsonl` -- V-Dem viewpoint provenance (implemented)
- `provenance/compilation/vdem_ledger.jsonl` -- V-Dem compilation provenance (implemented)

Each entry records: timestamp, operation type, input references + digests, config snapshot, output path + digest, validation results (including errors and warnings).

Python `logging` at WARNING/ERROR/CRITICAL levels supplements but does not replace ledger entries.

---

### 2.3 Logs Must Support Understanding

Logs must:
- provide sufficient context to reconstruct state
- include relevant identifiers (source name, config hash, digest, etc.)
- avoid ambiguity

Logs must not:
- rely on implicit assumptions
- require tribal knowledge to interpret

---

### 2.4 Logs Must Not Leak Sensitive Data

- API keys must never be logged.
- Full API response bodies should be logged at DEBUG only.
- Sensitive raw inputs must not be logged unless explicitly approved.

---

## 3. Log Levels (Normative Definitions)

### DEBUG
- Development diagnostics.
- Detailed internal state (array shapes, intermediate values, API pagination progress).
- Must not be required to understand production failures.

### INFO
- High-level lifecycle events.
- Start/finish of harvest, compilation, generation operations.
- Source identifiers and configuration summaries.
- Content digest values.

### WARNING
- Unexpected but recoverable conditions.
- UCDP fatality bound violations (best > high or low > best) -- data quality issues that do not prevent processing.
- Degraded behavior that does not violate invariants.

Warnings must not be used to hide invariant violations.

### ERROR
- Structural failure within a component.
- Schema validation failures, digest mismatches, missing required files.
- Operation failed and cannot proceed correctly.
- Must be raised and logged.

### CRITICAL
- System-wide failure.
- Provenance ledger corruption, irrecoverable state.
- Immediate attention required.

---

## 4. Error Propagation Pattern

Structural errors must follow this minimal pattern:

1. Construct a clear, descriptive error message.
2. Log the error (`ERROR` or `CRITICAL`).
3. Raise the appropriate exception with the same message.

Example:

```python
err_msg = f"Content digest mismatch for {source_path}: expected {expected}, got {actual}"
logger.error(err_msg)
raise ValueError(err_msg)
```

Clarity and consistency are required. Spacing conventions are not mandated.

---

## 5. Logging Scope Expectations

### 5.1 Required Logging

The following must be logged:

* Harvest operation start/finish (INFO)
* Compilation operation start/finish (INFO)
* Validation outcomes -- pass or fail (INFO/ERROR)
* Configuration summaries at operation start (INFO)
* Content digest values (INFO)
* All structural failures (ERROR/CRITICAL)
* Provenance ledger writes (DEBUG)

### 5.2 Optional Logging

* API pagination progress (DEBUG)
* Intermediate array shapes during compilation (DEBUG)
* Performance timing for individual operations (DEBUG)
* Snapshot comparison details (DEBUG)

---

## 6. Log Structure and Context

Log entries should include:

* Timestamp
* Level
* Module or component name
* Relevant identifiers (source name, config hash, digest, operation type)

Structured logging (JSON or key-value format) is recommended where possible.

---

## 7. Alerting

Not applicable at this stage. When operational deployment is needed, alerting should be built on `ERROR` and `CRITICAL` log levels.

---

## 8. Testing Requirements

Logging behavior must be testable where meaningful.

Tests should verify:

* Errors are both logged and raised.
* Provenance ledger entries are written for every operation.
* Validation failures produce structured error messages.

Logging tests must not rely on manual inspection.

---

## 9. Anti-Patterns (Prohibited)

* Swallowing exceptions without logging
* Logging and continuing after invariant violation
* Downgrading errors to warnings to "keep things running"
* Using `print()` for structural diagnostics
* Logging entire objects without context
* Treating provenance ledger writes as optional

---

## 10. Evolution

This document may evolve independently of ADRs.

If logging semantics change in a way that affects system meaning,
ADR-008 must be revisited.
