# datafactory_core -- Architecture

## Purpose

Shared foundations for all datafactory packages. Contains provenance utilities, configuration base patterns, content digest computation, and common types. This is Layer 0 of the dependency DAG (ADR-002): every other `datafactory_*` package may import from core, but core imports nothing internal.

## Responsibility Boundary

**Owns:**
- Provenance ledger writing (JSONL append-only)
- Content digest computation (SHA-256)
- Configuration validation patterns (frozen dataclasses with `__post_init__`)
- Common type definitions shared across packages
- Version declaration

**Does NOT own:**
- Grid coordinate generation (datafactory_grid)
- Data fetching or API interaction (datafactory_harvester)
- Compilation logic (datafactory_compiler)
- Synthetic data generation (datafactory_synthetic)
- Domain-specific configuration (each package owns its own config)
- I/O beyond provenance ledger append and digest computation

## Dependency Rules

**May import:** Python standard library, numpy
**Must never import:** Any other `datafactory_*` package

## Key Concepts

| Concept | Description |
|---------|-------------|
| ProvenanceLedger | JSONL append-only writer. Each entry: timestamp, operation type, input references + digests, config snapshot, output path + digest, validation results. |
| ContentDigest | SHA-256 digest computation for staleness detection and provenance tracking. Deterministic and order-independent. |
| BaseConfig pattern | Frozen dataclass with `__post_init__` validation. Fail-loud on missing or invalid fields. No hidden defaults. |

## Invariants

- Zero imports from any other `datafactory_*` package (ADR-002, Layer 0)
- All public symbols declared in `__all__` (ADR-001)
- Provenance ledger entries are append-only; existing entries are never modified or deleted
- Content digest computation is deterministic: same input = same digest regardless of call order
- All configuration validation raises on failure; no silent fallbacks (ADR-003)

## CIC Stubs

### ProvenanceLedger
**Purpose:** Append structured JSONL entries to ledger files for harvest, compilation, and synthetic generation operations.
**Non-goals:** Does not query, aggregate, or visualize ledger data. Does not validate that referenced source files exist.
**Key guarantees:** Entries are always appended (never overwritten). Every entry includes a timestamp and operation type. Failure to write raises immediately (ADR-008).

### ContentDigest
**Purpose:** Compute SHA-256 content digests for data files and configuration snapshots to enable staleness detection and provenance verification.
**Non-goals:** Does not store or cache digests. Does not compare digests (that's the caller's responsibility).
**Key guarantees:** Deterministic: same bytes = same digest. Returns hex string (or truncated hex per convention). Raises on I/O errors.
