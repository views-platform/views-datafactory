# datafactory_provenance -- Architecture

## Purpose

Provenance tracking — content digests and JSONL ledger operations. Every `datafactory_*` operation that produces output records provenance through this package. This is Layer 0 of the dependency DAG (ADR-012): every other `datafactory_*` package may import from provenance, but provenance imports nothing internal.

## Responsibility Boundary

**Owns:**
- Provenance ledger writing (JSONL append-only)
- Provenance ledger reading (last digest lookup, version-filtered queries)
- Content digest computation (SHA-256, truncated hex)
- Infrastructure constants (LEDGER_VERSION, DIGEST_SCHEME)
- Version declaration

**Does NOT own:**
- Grid coordinate generation (datafactory_priogrid)
- Data fetching or API interaction (datafactory_harvester)
- Consolidation logic (datafactory_consolidation)
- Viewpoint building (datafactory_viewpoint)
- Compilation logic (datafactory_compilation)
- Domain-specific configuration (each package owns its own config)
- I/O beyond provenance ledger append and digest computation

## Dependency Rules

Per ADR-012 (topology and dependency direction):

**May import:** Python standard library, numpy
**Must never import:** Any other `datafactory_*` package

## Key Concepts

| Concept | Description |
|---------|-------------|
| `append_ledger_entry` | JSONL append-only writer. Auto-generates UTC timestamp. Caller defines entry structure. |
| `last_digest` / `last_digest_for_version` | Ledger readers for digest lookup. Tolerate malformed trailing lines. |
| `compute_content_digest` | SHA-256 digest computation, truncated to 16 hex chars by default. Deterministic: same bytes = same digest. |
| `LEDGER_VERSION` | Centralized constant for ledger schema version. Bump when ledger entry format changes. |
| `DIGEST_SCHEME` | Centralized constant (`"sha256_16"`) recorded in every ledger entry for forward compatibility. |

## Invariants
- **Single-writer access assumed.** No concurrent operations supported (see technical_risk_register_resolved.md C-16)

- Zero imports from any other `datafactory_*` package (ADR-012, Layer 0)
- All public symbols declared in `__all__` (ADR-001)
- Provenance ledger entries are append-only; existing entries are never modified or deleted
- Content digest computation is deterministic: same input = same digest regardless of call order
- All configuration validation raises on failure; no silent fallbacks (ADR-003)

## CIC Stubs

### ProvenanceLedger
**Purpose:** Append structured JSONL entries to ledger files for harvest, consolidation, viewpoint, and compilation operations.
**Non-goals:** Does not query, aggregate, or visualize ledger data. Does not validate that referenced source files exist.
**Key guarantees:** Entries are always appended (never overwritten). Every entry includes an auto-generated UTC timestamp. Entry structure is caller-defined. Failure to write is both logged and raised (ADR-008).

### ContentDigest
**Purpose:** Compute SHA-256 content digests for data files and configuration snapshots to enable staleness detection and provenance verification.
**Non-goals:** Does not store or cache digests. Does not compare digests (that's the caller's responsibility).
**Key guarantees:** Deterministic: same bytes = same digest. Callers are responsible for consistent serialization order. Returns truncated hex string (16 chars by default). Raises on invalid input (ADR-008).
