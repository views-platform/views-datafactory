# Instantiation Checklist

Bootstrapped from base_docs templates on 2026-03-17 for views-datafactory.

---

## Before You Start

- [x] Decide which adoption phase you're targeting (see `ADRs/README.md` -- Recommended Adoption Order)
- [x] Identify your project's ontological categories (Source Nodes, The Grid, Compilation Edges, Configurations, Provenance Records)

---

## ADR Adaptation

### All adopted ADRs
- [x] Update Status from `--template--` to `Accepted` (except ADR-004: `Deferred`)
- [x] Fill in Date (2026-03-17), Deciders (Simon Polichinel von der Maase, Claude Code)

### Per-ADR adaptation notes
- [x] **ADR-000:** Updated `ADRs/` path to `docs/ADRs/`. Grounded in humanitarian data context.
- [x] **ADR-001:** Defined 5 ontological categories: Source Nodes, The Grid, Compilation Edges, Configurations, Provenance Records. Explicit non-entities adapted to graph architecture.
- [x] **ADR-002:** Defined DAG topology: core (L0) -> grid/harvester/synthetic (L1) -> compiler (L2). Filesystem-mediated data flow. Forbidden patterns grounded in project domain.
- [x] **ADR-003:** Adapted forbidden behavior examples to data factory domain (grid resolution inference, digest mismatch, etc.)
- [x] **ADR-004:** Kept as Deferred. Trigger: when metric lab formally depends on this repo.
- [x] **ADR-005:** Adapted test taxonomy with project-specific examples (grid cell count, bit-identical compilation, malformed API responses, etc.)
- [x] **ADR-006:** Listed priority CIC candidates: GridConfig, TemporalConfig, SpatioTemporalGrid, HarvesterConfig, ValidationResult, CompilationConfig.
- [x] **ADR-007:** Adapted for Claude Code as primary tool. Added heightened scrutiny areas. Referenced `uv run` for enforcement gates.
- [x] **ADR-008:** Grounded in JSONL provenance as primary observability. Domain-specific fail-loud examples.
- [x] **ADR-009:** Adapted boundary examples: GridConfig `__post_init__`, harvester-to-filesystem, filesystem-to-compiler, compiled output shape contract.

---

## CICs

- [x] Replace placeholder active contracts list in `CICs/README.md` with priority candidates
- [ ] Create intent contracts for non-trivial classes as they are implemented (GridConfig, HarvesterConfig, etc.)

---

## Contributor Protocols

- [x] Review and adapt `contributor_protocols/silicon_based_agents.md` -- Claude Code as primary tool, `uv run` for gates, heightened scrutiny areas
- [x] Review and adapt `contributor_protocols/carbon_based_agents.md` -- solo researcher context, humanitarian data responsibility
- [x] Adapt `contributor_protocols/hardened_protocol_template.md` -- numpy dtypes, deterministic compilation, SHA-256 digests, entropy locking

---

## Standards

- [x] Review `standards/logging_and_observability_standard.md` -- adapted scope to JSONL provenance ledgers, data factory operations
- [x] Skip `standards/physical_architecture_standard.md` -- not applicable (graph-node layout, not 1-class-1-file)

---

## Final Verification

- [x] No files still have Status `--template--` (ADR-004 is intentionally `Deferred`)
- [ ] No phantom references to non-existent files (run `validate_docs.sh`)
- [ ] All cross-ADR references resolve correctly (run `validate_docs.sh`)
- [ ] Run `validate_docs.sh` to check internal consistency
