# Note on Reproducibility of UCDP Candidate Data

**Date:** 2026-03-21
**Status:** Preliminary — based on limited observation (single day, two query rounds)
**Confidence:** Findings are empirical but the observation window is short. Conclusions should be treated as hypotheses requiring further observation, not established facts.

---

## What We Observed

On 2026-03-21, we re-queried the UCDP API for candidate versions we had fetched approximately 24 hours earlier. The results were unexpected:

- **14 candidate versions from 2025-2026** (25.0.1 through 26.0.2) each gained exactly +1,000 events
- **12 candidate versions from 2024** (24.0.1 through 24.0.12) were unchanged

The uniform +1,000 delta across all 14 recent versions suggests a bulk update operation by UCDP, not incremental data addition.

## What This May Imply for Reproducibility

If these observations generalize — and we stress that a single day's observation is not sufficient to confirm a pattern — they raise questions about the reproducibility of analyses based on UCDP candidate data:

1. **Version identifiers may not uniquely identify datasets.** Querying `25.0.6` at different times may return different event counts, fatality totals, and spatial distributions. A version number alone may be insufficient to reproduce a prior analysis.

2. **There may be an undocumented stability boundary.** Our observation is consistent with a policy where versions older than approximately one year become immutable, while more recent versions remain subject to updates. We have not confirmed this boundary and it is not documented in any UCDP codebook we could find.

3. **Snapshot timing may matter more than version numbering.** If candidate data is mutable, the *date of download* is as important as the *version identifier* for reproducibility purposes.

## What We Do NOT Know

We want to be explicit about the limits of our evidence:

- **We observed one update event.** We do not know how frequently UCDP updates candidate versions, whether this was a routine operation or exceptional, or whether all updates follow the same pattern.

- **We do not know UCDP's internal policies.** There may be a documented freeze policy that we have not found. UCDP may consider candidate data explicitly provisional and expect consumers to re-fetch periodically.

- **We have not tested annual data mutability.** Our observations concern only candidate versions (`YY.0.MM`). The annual GED releases (`YY.MM`) may follow different stability guarantees — they are published with DOIs and codebooks, which implies a stronger stability contract.

- **We have not tested .9 mutability.** The `.9` versions (`YY.9.MM`) were not re-queried in this investigation. Their mutability is unknown.

- **We do not know whether the +1,000 pattern is typical.** This may have been a one-time correction, a monthly batch, or a daily process. More observation points are needed.

## What This Means for views-datafactory

Our provenance system (ADR-008, ADR-013) records content digests and timestamps for every fetch. This means:

- Every snapshot we store is a point-in-time archive with a verifiable digest
- If the upstream data changes, our next fetch will detect the change via digest comparison
- Our consolidated store preserves the data as it was at the time of ingestion

This provenance chain does not solve the upstream reproducibility question, but it ensures that our own analyses are traceable to specific data states.

## Recommendations

1. **Record download timestamps alongside version identifiers** in any analysis that uses UCDP candidate data. A citation should read "UCDP Candidate 25.0.6, downloaded 2026-03-20, digest af880f77" rather than just "UCDP Candidate 25.0.6."

2. **Establish a re-harvesting cadence.** If candidate versions are mutable, periodic re-fetching is necessary to capture updates. The frequency should match UCDP's update cadence (which we have not yet determined).

3. **Seek clarification from UCDP.** These observations should be shared with UCDP to understand their intended data lifecycle for candidate versions. There may be a documented policy we have not found, or this may be an opportunity to establish one.

4. **Monitor over time.** A single observation does not establish a pattern. We should re-query the same versions at regular intervals (weekly, monthly) to characterize the update frequency and magnitude.

---

## Evidence Summary

| Observation | Source | Date |
|------------|--------|------|
| 25.0.1-26.0.2 each gained +1,000 events | API re-query | 2026-03-21 |
| 24.0.1-24.0.12 unchanged | API re-query | 2026-03-21 |
| All 14 versions changed by identical delta | API re-query | 2026-03-21 |
| Provenance ledger shows stability across ~3 hours | Ledger analysis | 2026-03-20/21 |
| No UCDP documentation found on version mutability | Web search, codebook review | 2026-03-21 |
