# datafactory_provenance -- Architecture

## Purpose

Shared foundations for all datafactory packages. Contains provenance utilities and content digest computation. This is Layer 0 of the dependency DAG (ADR-002): every other `datafactory_*` package may import from core, but core imports nothing internal.

## Responsibility Boundary

**Owns:**
- Provenance ledger writing (JSONL append-only)
- Provenance ledger reading (last digest lookup, version-filtered queries)
- Content digest computation (SHA-256, truncated hex)
- Version declaration

**Future (not yet implemented):**
- Configuration validation patterns (frozen dataclasses with `__post_init__`) — if shared patterns emerge
- Common type definitions — if multiple packages need them

**Does NOT own:**
- Grid coordinate generation (datafactory_priogrid)
- Data fetching or API interaction (datafactory_harvester)
- Compilation logic (datafactory_compilation)
- Synthetic data generation (datafactory_synthetic)
- Domain-specific configuration (each package owns its own config)
- I/O beyond provenance ledger append and digest computation

## Dependency Rules

Per ADR-002 (topology and dependency direction):

**May import:** Python standard library, numpy
**Must never import:** Any other `datafactory_*` package

## Key Concepts

| Concept | Description |
|---------|-------------|
| `append_ledger_entry` | JSONL append-only writer. Auto-generates UTC timestamp. Caller defines entry structure. |
| `last_digest` / `last_digest_for_version` | Ledger readers for digest lookup. Tolerate malformed trailing lines. |
| `compute_content_digest` | SHA-256 digest computation, truncated to 16 hex chars by default. Deterministic: same bytes = same digest. |

## Invariants
- **Single-writer access assumed.** No concurrent operations supported (see concerns00.md C-16)

- Zero imports from any other `datafactory_*` package (ADR-002, Layer 0)
- All public symbols declared in `__all__` (ADR-001)
- Provenance ledger entries are append-only; existing entries are never modified or deleted
- Content digest computation is deterministic: same input = same digest regardless of call order
- All configuration validation raises on failure; no silent fallbacks (ADR-003)

## CIC Stubs

### ProvenanceLedger
**Purpose:** Append structured JSONL entries to ledger files for harvest, compilation, and synthetic generation operations.
**Non-goals:** Does not query, aggregate, or visualize ledger data. Does not validate that referenced source files exist.
**Key guarantees:** Entries are always appended (never overwritten). Every entry includes an auto-generated UTC timestamp. Entry structure is caller-defined. Failure to write is both logged and raised (ADR-008).

### ContentDigest
**Purpose:** Compute SHA-256 content digests for data files and configuration snapshots to enable staleness detection and provenance verification.
**Non-goals:** Does not store or cache digests. Does not compare digests (that's the caller's responsibility).
**Key guarantees:** Deterministic: same bytes = same digest. Callers are responsible for consistent serialization order. Returns truncated hex string (16 chars by default). Raises on invalid input (ADR-008).
