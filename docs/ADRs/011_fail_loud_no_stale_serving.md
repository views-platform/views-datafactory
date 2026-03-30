# ADR-011: Fail Loud, No Stale Data Serving

**Status:** Accepted
**Date:** 2026-03-18
**Deciders:** Simon Polichinel von der Maase, Claude Code

---

## Context

ADR-003 and ADR-008 establish fail-loud as the system's error handling philosophy: all structural failures must raise exceptions and log at ERROR or higher. No silent fallbacks.

This raises an operational question: when a harvest or compilation fails, what happens to consumers? Do they receive the last-known-good compiled grid (stale data), or does the system refuse to serve anything?

For a humanitarian early warning system, both options carry risk:
- **Stale data** may mislead analysts if conflict patterns have changed since the last successful compilation.
- **No data** blocks analysts entirely, which is also harmful if the failure is transient.

---

## Decision

The system **crashes and fails loud**. No stale data is served. When a harvest or compilation fails:

1. The failure is logged at ERROR (ADR-008).
2. A provenance ledger entry is recorded with `outcome: "failed"` (already implemented).
3. No compiled grid is produced or updated.
4. Consumers must handle the absence of fresh data in their own error paths.

**No automatic fallback to previous data is implemented.**

---

## Rationale

- The system is pre-production. Operational resilience features add complexity before the failure modes are understood.
- Stale data serving requires versioning, staleness thresholds, and consumer-visible freshness indicators — all of which are premature at this stage.
- The provenance system records every attempt (success and failure), so operators can manually identify the last-known-good compilation if needed.
- Fail-loud is the safer default: it makes problems visible immediately rather than hiding them behind stale outputs.

---

## Future Work

A future ADR should address graceful degradation when the system approaches production deployment. Specifically:

- **Staleness thresholds:** How old can compiled data be before it should be considered invalid?
- **Freshness indicators:** Should compiled grids carry a "data age" metadata field that consumers can check?
- **Fallback policy:** Should the system serve the last-known-good grid with a staleness warning, or refuse entirely?
- **Alerting:** Should failed harvests or compilations trigger alerts (Slack, email, etc.)?

These decisions require operational experience and stakeholder input (OCHA/FAO) that is not yet available.

---

## Consequences

### Positive
- Simple, predictable behavior — failures are always visible
- No hidden staleness risk
- Provenance chain remains clean (no "maybe stale" entries)

### Negative
- Consumers must handle missing data gracefully
- Transient API failures block the entire pipeline until manually retried
- No automated recovery

These trade-offs are accepted intentionally for the pre-production phase.

---

## References

- ADR-003 (Authority of Declarations — fail-loud invariant)
- ADR-008 (Observability and Explicit Failure)
- `reports/technical_risk_register_resolved.md` C-15, D-03
- Kleppmann & Riccomini, *Designing Data-Intensive Applications*, 2nd ed., O'Reilly 2026:
  - Ch.2 pp.43-44: Fault vs failure distinction; crash-stop fault model
  - Ch.2 pp.46-47: Software faults — systematic, correlated, lie dormant until triggered
