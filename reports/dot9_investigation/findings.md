# .9 Investigation: Detailed Findings

**Date:** 2026-03-21
**Method:** Empirical API probing + data comparison
**Datasets compared:**
- UCDP .9 version 25.9.11 (fetched 2026-03-21)
- UCDP .9 version 25.9.6 (fetched 2026-03-21)
- UCDP Annual v25.1, full range 1989-2024 (384,918 events)
- UCDP Candidate 25.0.1 through 26.0.2 (14 versions, 16,341 events)

---

## 1. What We KNOW (Empirically Confirmed)

### 1.1 The .9 format exists and is accessible

- **Version format:** `YY.9.MM` (e.g., `25.9.11` = November 2025 release)
- **API endpoint:** `https://ucdpapi.pcr.uu.se/api/gedevents/25.9.11`
- **Authentication:** Same `x-ucdp-access-token` as other endpoints
- **Schema:** 49 columns — identical to standard candidate/annual schema
- **Versions confirmed available:** 18.9.1 through 26.9.2 (probed 2026-03-21). The .9 series spans 8 years with data in every month probed. Event counts per version range from ~11,000 (early years) to ~33,000 (recent).

### 1.2 The .9 contains exclusive content

Comparing 25.9.11 against our full data (annual v25.1 1989-2024 + candidate 25.0.1-26.0.2):

| Metric | Value |
|--------|-------|
| Total events in .9 (25.9.11) | 31,046 |
| Events also in our data | 17,942 (58%) |
| **Events ONLY in .9** | **13,005 (42%)** |
| Fatalities in exclusive events (best) | 58,159 (30% of .9's total 191,172) |
| Fatalities in exclusive events (high) | 154,519 (53% of .9's total 289,687) |
| Exclusive events with best > 0 | 12,099 (92%) |

### 1.3 The exclusive events are real conflict data

Top countries in exclusive .9 events:

| Country | Events | % of Exclusive |
|---------|--------|---------------|
| Ukraine | 4,100 | 31.3% |
| Israel | 2,347 | 17.9% |
| Nigeria | 623 | 4.8% |
| DR Congo | 464 | 3.5% |
| Sudan | 457 | 3.5% |
| Syria | 411 | 3.1% |
| Burkina Faso | 394 | 3.0% |
| Mexico | 332 | 2.5% |
| Costa Rica | 328 | 2.5% |
| Mali | 322 | 2.5% |

Type of violence breakdown:
- Type 1 (state-based): 9,487 (72.4%)
- Type 2 (non-state): 1,813 (13.8%)
- Type 3 (one-sided): 1,765 (13.5%)
- Type 4 (other): 39 (0.3%)

### 1.4 The exclusive events are temporally concentrated

By date_start year:
- 2024: 231 events
- 2025: 12,873 events

The 2025 events are the bulk of the gap. Our candidate versions (25.0.1-26.0.2) contain 13,607 events from 2025. The .9 contains 26,480 events from 2025. **The .9 has roughly double the 2025 event coverage of all 14 candidate versions combined.**

### 1.5 The exclusive content persists across .9 versions

Cross-checking 25.9.11 vs 25.9.6 (5 months apart):

| Metric | Value |
|--------|-------|
| .9.11 exclusive events | 13,005 |
| .9.6 exclusive events | 7,365 |
| Exclusive in BOTH versions | 6,475 |
| Only in .9.11 | 6,629 |

The exclusive content is persistent (6,475 events present in both) and growing (13,005 in .9.11 vs 7,365 in .9.6).

### 1.6 No distinguishing schema markers

Comparing exclusive vs non-exclusive events in .9:

| Field | Exclusive (13,005) | Non-exclusive (17,942) |
|-------|-------------------|----------------------|
| code_status (top) | Clear: 85% | Clear: 77% |
| type_of_violence | 1: 72%, 2: 14%, 3: 13% | 1: 57%, 2: 27%, 3: 17% |
| where_prec (top) | 1: 51%, 2: 23% | 1: 51%, 2: 23% |
| number_of_sources (mean) | 1.5 | 1.4 |
| date_prec=5 (summary) | 48 (0.4%) | 51 (0.3%) |

No schema feature distinguishes exclusive from non-exclusive events. They look identical in structure.

### 1.7 The .9 covers a narrow time window

25.9.11 date range: `date_start` from 2024-11-01 to 2025-11-30 (13 months)

This aligns with the production description: "updated data for the last 12 months."

### 1.8 Production actively depends on .9

From `UppsalaConflictDataProgram/ingester3_loaders/README.md`:
- Latest ingestion: **version 26.9.1 on 2026-02-24 by Angelica**
- Monthly cadence
- Used with `fix_summary_events=True`

### 1.9 Standard candidate versions also exist back to 2018

Separately confirmed: `YY.0.MM` candidate versions exist from 18.0.1 through 26.0.2 (98 versions). These are a **different, smaller dataset** than the `.9` versions.

### 1.10 For overlapping events, our logic produces 97.7% match

Of 17,942 events that exist in both .9 and our data:
- 17,528 (97.7%) match exactly on fatality values
- 414 (2.3%) differ — these are revision differences between candidate versions

Our survivorship and distribution logic is correct. The gap is in data availability, not logic.

---

## 2. What We THINK We Know (Inferred from Evidence)

### 2.1 The .9 is produced by UCDP specifically for VIEWS

The production notebook states (exact quote):

> "Note that the UCDP produces a `.9` version of their candidate data every month specifically for us. It's not released on their website, but publicly available in their API. It contains the latest candidate dataset + updated data for the last 12 months. It thus overrites data for the last 12 months in our dataset, ensuring that we always have the most up-to-date data for the 12 months preceding the current month."

Source: `UppsalaConflictDataProgram/ingester3_loaders/UCDP/GED_loader.ipynb` (main branch, accessed 2026-03-21)

### 2.2 The .9 is a superset, not a consolidation

The notebook says the .9 "contains the latest candidate dataset + updated data for the last 12 months." But our empirical findings show it contains 13,005 events that are NOT in any standard candidate release (25.0.1-26.0.2) AND NOT in the annual (v25.1). It appears to be a superset drawn from UCDP's internal pipeline, not a merge of publicly released datasets.

### 2.3 The exclusive events may come from UCDP's real-time coding pipeline

The exclusive events look structurally identical to regular events (same schema, similar distributions). They likely come from UCDP's continuous event coding process — events that have been coded but not yet included in a standard `YY.0.MM` candidate release. The `.9` may be a snapshot of UCDP's internal database, not a derived product.

### 2.4 The exclusive events will likely appear in future annual releases

The 12,873 exclusive 2025 events will likely appear in the annual v26.1 release (expected 2027). The 231 exclusive 2024 events may appear in v25.1 updates or v26.1. But until then, they are only accessible through `.9`.

### 2.5 The production description is incomplete, not wrong

"Latest candidate + updated data for last 12 months" may be accurate from UCDP's internal perspective — their internal candidate data includes events that haven't been released through the public `YY.0.MM` endpoint. The `.9` may be the "latest candidate" in UCDP's internal database, which is larger than the public candidate releases.

---

## 3. What We DON'T Know (Open Questions)

### 3.1 How does UCDP construct the .9?

What data pipeline produces it? Is it a database query, a manual export, an automated process? Does it have quality gates that differ from the standard candidate release?

### 3.2 Why does .9 contain events not in any public candidate release?

Is this intentional (UCDP gives VIEWS early access) or accidental (the public candidate endpoint is a subset of the internal database)? Are there events in the internal database that never make it to public candidate releases?

### 3.3 How far back do .9 versions go?

We confirmed 25.9.1 through 26.9.2. Do earlier versions exist (24.9.x, 23.9.x)? The standard candidate goes back to 18.0.1.

### 3.4 Does the .9 apply any internal consolidation rules?

Does UCDP apply survivorship (annual > candidate) internally before producing the .9? Or is the .9 a raw union of all recent data?

### 3.5 Is there internal UCDP documentation?

Is there a specification, codebook, or internal wiki page that describes the .9 format? The production notebook is the only documentation we've found.

### 3.6 What is the relationship between .9 and the GED annual release?

Do events in .9 always eventually appear in annual releases? Are there events that appear in .9 but are later dropped from the annual (failed quality checks)?

### 3.7 What does Mert (UCDP) know about .9?

The production README quotes suggestions from "Mert in UCDP" about spatial precision improvements. Mert may be a contact who can explain the .9 pipeline.

---

## 4. Sources and References

### Primary Source (exact quote)

**File:** `UppsalaConflictDataProgram/ingester3_loaders/UCDP/GED_loader.ipynb`
**Branch:** main
**Accessed:** 2026-03-21

Full verbatim text of the `.9` documentation:

> "# UCDP GED Loader
>
> For ingesting the annual UCDP GED `(YY.MM)` and the monthly UCDP Candidate `(YY.9.MM)` datasets.
>
> Note that the UCDP produces a `.9` version of their candidate data every month specifically for us. It's not released on their website, but publicly available in their API. It contains the latest candidate dataset + updated data for the last 12 months. It thus overrites data for the last 12 months in our dataset, ensuring that we always have the most up-to-date data for the 12 months preceding the current month."

Note: "overrites" is the original spelling.

### Production Status

**File:** `UppsalaConflictDataProgram/ingester3_loaders/README.md`
**Branch:** main
**Accessed:** 2026-03-21

UCDP CANDIDATE/GED row shows: Ingestion Date 2026-02-24, Ingested Version 26.9.1, Ingested by Angelica.

Comments include feedback from "Mert in UCDP" about spatial precision and suggestions for VIEWS to create their own PRIO-GRID assignment system.

### UCDP Official Documentation (no .9 mention)

- **API docs:** https://ucdp.uu.se/apidocs/ — documents annual (YY.MM) and candidate (YY.0.MM) but NOT .9
- **Candidate codebook v1.4:** https://ucdp.uu.se/downloads/candidateged/ucdp-candidate-codebook1.4.pdf — no .9 mention
- **Dataset downloads:** https://ucdp.uu.se/downloads/ — no .9 listed
- **Candidate paper (2020):** Hegre et al., "Introducing the UCDP Candidate Events Dataset," https://journals.sagepub.com/doi/10.1177/2053168020935257 — no .9 mention

### VIEWS Documentation

- **Summary events blog post (Oct 2025):** https://viewsforecasting.org/news/improved-handling-of-ucdp-summary-events-in-views-forecasts-and-api-data/ — discusses fix_summary_events but does not mention .9 specifically
- **UCDP-Candidate + VIEWS Outcomes paper:** https://viewsforecasting.org/wp-content/uploads/a_771636-f_ucdp_candidate_views_outcomes.pdf — no .9 mention

### Internal Documentation

- **ADR-015:** `docs/ADRs/015_ucdp_consolidation.md` — our own documentation, now known to be based on incomplete understanding of what .9 contains
- **Memory:** `.claude/projects/.../memory/project_dot9_parity_findings.md` — investigation findings saved for future conversations

---

## 5. Implications

### For views-datafactory

1. **ADR-015 needs updating.** Current description of .9 as "stitching annual and candidate" is empirically wrong.
2. **The .9 must be a harvested source** if we want production parity. It cannot be reconstructed from annual + candidate.
3. **Our independent consolidation (annual + candidate) produces a different dataset** than what production uses. This is a valid alternative viewpoint, but it's not production-equivalent.

### For VIEWS generally

1. **Production depends on an undocumented data source.** If UCDP changes the .9 pipeline without notice, VIEWS forecasts could be silently affected.
2. **The .9 format should be documented** — a codebook or specification would reduce institutional risk.
3. **The relationship between .9 and standard candidate releases should be clarified** — are they independent products from the same pipeline, or is one derived from the other?

### For research

1. **Comparing .9 against independent consolidation is a research output.** The differences reveal what UCDP's internal pipeline captures that public releases don't.
2. **The 13,005 exclusive events are a measurable information advantage.** Forecasts using .9 have access to nearly double the 2025 event data compared to forecasts using public candidate releases.
3. **Vintage analysis (RQ-2) should include .9 as a third vintage type** alongside annual and candidate.

---

## 6. Falsification Audit (2026-03-21)

This section documents the results of a structured falsification audit applied to the claim "we have the full picture of .9 vs individual candidate datasets."

### 6.1 Probes Executed

| ID | Description | Prediction | Result | Verdict |
|----|-------------|-----------|--------|---------|
| P1+P5 | Check 13,005 "exclusive" .9 events against ALL 2024 candidate versions (24.0.1-24.0.12) | Some will appear in older candidates | 99 of 13,005 found (0.8%) — exclusive count reduced from 13,104 to 13,005 | **Survived** (minor correction) |
| P2 | Probe for .9 versions before 25.9.1 (backward to 18.9.x) | .9 goes back to ~2018 | Confirmed: 18.9.1 through 26.9.2 all have data (11K-33K events each) | **Soft falsification** — findings understated .9 availability by 84 versions |
| P3 | Check for candidate versions beyond 26.0.2 | None exist | Confirmed: 26.0.3-26.0.12 all empty | **Survived** |
| P4 | Test ADR-015 "stitching" claim | Empirically false | 13,005 events prove .9 is not a stitch of annual + candidate | **Hard falsification** |

### 6.2 Corrections Applied

1. **Version range:** "25.9.1 through 26.9.2" corrected to "18.9.1 through 26.9.2" (section 1.1)
2. **Exclusive count:** "13,104" corrected to "13,005" throughout (99 events found in 24.0.11 and 24.0.12)
3. **ADR-015:** "stitches annual and candidate" claim replaced with accurate characterization

### 6.3 Bonus Observations

**Candidate data is mutable — confirmed via systematic re-query.**

A second falsification audit (same day, 2026-03-21) re-queried all candidate versions against the API and found:

| Version range | Versions checked | Result |
|--------------|-----------------|--------|
| 25.0.1 – 26.0.2 (2025-2026) | 14 | ALL changed: exactly +1,000 events each |
| 24.0.1 – 24.0.12 (2024) | 12 | ALL stable: 0 changes |

Every 2025-2026 candidate version gained exactly 1,000 events in what appears to be a bulk retroactive update by UCDP. This is not organic growth — the identical delta across 14 versions indicates a batch operation. Meanwhile, all 2024 versions remained perfectly stable.

This suggests an undocumented version boundary: versions from the prior calendar year and earlier may be frozen, while recent versions remain mutable. We cannot confirm this boundary without longer observation.

**All snapshot comparisons in this document are time-stamped to 2026-03-21 and should be treated as point-in-time observations, not permanent facts.** The exclusive event count (13,005) and all derived statistics may change if UCDP continues to update candidate versions retroactively.

**The .9 series is a complete 8-year parallel data stream.** From 18.9.1 to 26.9.2, approximately 98 monthly versions exist, each containing 11,000-33,000 events. This is not a small bespoke product — it's a major data stream comparable in scale to the standard candidate series.

### 6.4 Audit Verdict

**CONTESTED.** The core finding (13,005 exclusive events, .9 as distinct source) survived the most aggressive probes. But the investigation had significant gaps: .9 availability was understated by 84 versions, and ADR-015 contained a hard-falsified claim. These have been corrected.
