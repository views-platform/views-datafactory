# ADR-018: Operational Resilience Policy

**Status:** Accepted
**Date:** 2026-03-22
**Deciders:** Simon Polichinel von der Maase, Claude Code
**Extends:** ADR-011 (Fail Loud, No Stale Data Serving)

---

## Context

ADR-011 mandates fail-loud with no automatic fallback. This is correct for development and research: incorrect data is worse than no data. The provenance system records every attempt (success and failure), enabling manual identification of the last-known-good output.

As the system approaches production deployment for VIEWS forecasting, operators need a policy for API outages and harvest failures. Expert review (D-03) identified this as the most important unresolved tension: Nygard asks what happens when the UCDP API is down for 3 days.

The core tension: research pipelines need fail-loud (incorrect data is worse than no data). Production forecasting needs bounded staleness (no forecast is also bad). Both positions are correct in their context.

---

## Decision

### Pipeline behavior unchanged

The pipeline remains fail-loud per ADR-008/011. No code changes. When a harvest fails:

1. The failure is logged at ERROR.
2. A provenance ledger entry is recorded with `outcome: "failed"`.
3. No compiled grid is produced or updated.
4. The pipeline does NOT automatically serve stale data.

### Operator-mediated bounded staleness

Operators MAY serve last-known-good compiled data when a harvest fails, provided all of the following conditions are met:

1. **Provenance audit.** The operator has verified the provenance ledger shows the last successful compilation and understands what data it contains.
2. **Staleness threshold.** The last successful compilation is no older than the configured staleness threshold (default: 7 days for monthly data, 24 hours for daily data).
3. **Freshness indicator.** The consumer receives a machine-readable staleness indicator — the age of the compiled data in hours — so downstream models can weight or flag the output.
4. **Alert escalation.** An alert has been raised (via the operator's monitoring system) that fresh data is unavailable. The decision to serve stale data is logged.

### What this ADR does NOT do

- Does NOT add automatic fallback to the pipeline code.
- Does NOT modify ADR-008 or ADR-011.
- Does NOT define alerting infrastructure (that is an operational concern outside this repo).
- Does NOT authorize silent staleness — every use of stale data must be explicit and logged.

---

## Rationale

### Why operator-mediated, not automatic?

Automatic stale-data serving hides problems. An operator who explicitly decides "the 3-day-old data is acceptable for this forecast cycle" is making a documented judgment call. An automated system that silently serves stale data creates a false sense of freshness.

### Why bounded, not unbounded?

Month-old conflict data is misleading for a nowcasting system. The staleness threshold prevents operators from unknowingly serving arbitrarily old data. The default of 7 days for monthly data means at most one missed harvest cycle is tolerable.

### Why freshness indicators?

Downstream models and analysts need to know whether the data is fresh. A staleness age field lets consumers implement their own policies: a research model might accept 14-day-old data; an operational early warning might reject anything older than 48 hours.

---

## Consequences

### Positive

- Pipeline code remains simple and fail-loud — no conditional fallback logic.
- Operators have a documented policy for handling outages.
- Staleness is always explicit and bounded — no silent degradation.
- Freshness indicators enable consumer-specific staleness policies.

### Negative

- Operators must monitor and intervene during outages — no hands-free operation.
- The staleness threshold must be configured per deployment context.
- Freshness indicator format must be agreed with consumers (not yet defined).

These trade-offs are accepted. Operational resilience is an operational concern, not a pipeline concern.

---

## Implementation Notes

No code changes required. This ADR is a policy document that:

1. Preserves ADR-008/011 fail-loud behavior in the pipeline.
2. Defines conditions under which operators may serve stale data.
3. Requires operators to implement monitoring, alerting, and freshness indicators in their deployment infrastructure.

When the system reaches production deployment, the following should be implemented in the deployment layer (not in this repo):

- Monitoring: check provenance ledger for `outcome: "failed"` entries.
- Alerting: fire when no successful compilation exists within the staleness threshold.
- Freshness indicator: compute from the timestamp of the last successful compilation ledger entry.

---

## References

- ADR-008 (Observability and Explicit Failure)
- ADR-011 (Fail Loud, No Stale Data Serving)
- `reports/concerns00.md` D-03
- Expert review 6: Nygard perspective on operational resilience
