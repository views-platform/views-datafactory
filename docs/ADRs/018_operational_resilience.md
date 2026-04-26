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

### Per-source SLO (implemented v1.2.7)

The "default: 7 days" staleness threshold above is a global fallback. In practice, different sources have different release cadences. `SOURCE_SLO` in `datafactory_provenance.health` maps each source to an appropriate threshold:

| Source | SLO | Rationale |
|--------|-----|-----------|
| PRIO-GRID Static / Shapefile | `None` (static) | Dataset is immutable — age alone never indicates staleness |
| UCDP Annual | 8760h (1 year) | Yearly release cycle |
| UCDP Candidate / .9 | 744h (~31 days) | Monthly release cycle |
| Consolidation / Viewpoint / Compilation | 744h (~31 days) | Runs after upstream source updates |
| Export freshness | 168h (7 days) | Global SLO — one missed monthly cycle |

`check_health.py` displays per-source SLO labels (`[SLO: static]`, `[SLO: 1y]`, `[SLO: 31d]`). Static sources report OK regardless of age; dynamic sources are compared against their specific threshold. This eliminates false STALE warnings for datasets that are correct but old by design.

---

## Timeout Policy

HTTP timeouts are sized by expected payload and upstream behavior:

| Source | Timeout | Rationale |
|--------|---------|-----------|
| UCDP annual / candidate / .9 | 120s | Paginated JSON, ~100 KB/page (120s provides margin for slow API responses under rate-limit backoff; config default is 30s) |
| PRIO-GRID static | 60s | Per-variable JSON, ~1 MB |
| PRIO-GRID shapefile | 120s | Zipped shapefile, ~20 MB |
| PRIO-GRID land mask | 60s | Single JSON response |
| GAUL admin | 300s | Zipped shapefiles, ~50 MB each |

All timeouts are per-request (connect + read). Retries use exponential backoff with jitter (`datafactory_http.retry`). When adding a new source, choose a timeout proportional to the expected payload size. Document the choice in the config class.

---

## References

- ADR-008 (Observability and Explicit Failure)
- ADR-011 (Fail Loud, No Stale Data Serving)
- `reports/technical_risk_register_resolved.md` D-03
- Expert review 6: Nygard perspective on operational resilience
- Kleppmann & Riccomini, *Designing Data-Intensive Applications*, 2nd ed., O'Reilly 2026:
  - Ch.1 pp.13-14: SLAs vs SLOs — percentile-based performance targets, not averages
  - Ch.2 p.38: Metastable failures and retry storms — why bounded staleness needs operator judgment
  - Ch.2 pp.41-42: SLOs and SLAs — measurable targets for performance and availability
  - Ch.2 pp.43-44: Fault tolerance — continuing to provide service despite component faults
  - Ch.7 pp.231-232: Exponential backoff for transient errors; retrying overload makes it worse
  - Ch.8 pp.237-240: Snapshot isolation as bounded staleness trade-off
  - Ch.8 pp.289-290: Clock drift bounds (~200 ppm); timestamps have inherent uncertainty
