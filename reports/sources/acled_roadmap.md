# R&D Roadmap: ACLED (Armed Conflict Location & Event Data)

**Date:** 2026-03-26
**Status:** Investigation
**Priority:** High (second conflict source, high research value)
**Blocker:** Requires ACLED Research tier access (registration + possible institutional affiliation)

---

## 1. What is ACLED?

ACLED is a real-time conflict and protest monitoring platform. It
records individual events — battles, explosions, violence against
civilians, protests, riots, troop movements — with specific dates,
locations (lat/lon), actors, and fatality estimates.

It's broader than UCDP: UCDP tracks only organized violence with
25+ fatalities per conflict-year. ACLED tracks everything from a
single protest to a large-scale battle, including non-violent political
events.

In plain terms: ACLED answers "what happened, where, when, and who
was involved?" at a daily granularity. UCDP answers the same question
but only for the most severe organized violence.

---

## 2. Why does VIEWS need it?

ACLED as a second conflict source enables critical research:

- **Coverage comparison.** UCDP misses low-intensity violence and
  protests. ACLED captures these. Do protests predict later violence?
  Does low-intensity conflict escalate?
- **Temporal granularity.** ACLED is daily; UCDP is monthly. Daily
  data enables finer temporal analysis.
- **Actor information.** ACLED tracks specific armed groups, political
  parties, and protest movements. UCDP has less actor detail.
- **Cross-source validation.** Where UCDP and ACLED overlap (armed
  violence), comparing them reveals data quality characteristics.
- **Broader political violence picture.** Protests, demonstrations,
  and government responses may be leading indicators for the type
  of organized violence VIEWS forecasts.

---

## 3. What data is available?

- **Event types:**
  - Battles (armed clashes between organized groups)
  - Explosions / remote violence (IEDs, shelling, airstrikes)
  - Violence against civilians
  - Protests (peaceful demonstrations)
  - Riots (violent demonstrations)
  - Strategic developments (troop movements, agreements, arrests)
- **Coverage:**
  - Africa: 1997-present (most complete)
  - Asia, Middle East, Europe, Americas: varies, most from 2018+
  - Western Europe: 2020+
- **Resolution:** Individual events with date + lat/lon coordinates
- **Fields:** event_id, event_date, event_type, sub_event_type,
  actor1, actor2, country, admin1-3, location, latitude, longitude,
  fatalities, notes, source, source_scale
- **Size:** ~1M+ events globally (growing daily)
- **Update frequency:** Daily for partner/enterprise; 12-month lag
  for research tier

---

## 4. How is it accessed?

- **Registration required.** Create account at acleddata.com.
- **Tiered access model:**
  - **Free tier:** Aggregated data only (dashboards, summaries).
    Not sufficient for our use case.
  - **Research tier:** Disaggregated event data with ~12-month lag.
    May require institutional affiliation.
  - **Partner tier:** Near real-time data, curated exports.
  - **Enterprise tier:** Full API, real-time, custom deliverables.
- **API:** REST API at `acleddata.com/api/` with query filters
  (country, date range, event type). 5,000 row default limit,
  pagination available.
- **Authentication:** OAuth tokens (24-hour expiry, 14-day refresh).
- **Export formats:** JSON or CSV.

**Critical unknown:** What tier does the VIEWS project qualify for?
Research tier is likely sufficient (12-month lag is acceptable for
historical analysis). Need to check if Uppsala University /
VIEWS partnership qualifies for partner access.

---

## 5. Research questions this enables

### RQ-8: Does ACLED's broader event coverage predict UCDP-tracked violence?

ACLED captures protests, riots, and low-level violence that UCDP
doesn't track. Do these events precede the organized violence that
VIEWS forecasts? Specifically:

- Do protest counts in month t predict UCDP fatalities in month t+1?
- Does the ratio of non-violent to violent ACLED events indicate
  conflict trajectory (escalation vs de-escalation)?
- Can ACLED's real-time updates provide early warning signals for
  UCDP-scale violence?

### RQ-10: How do UCDP and ACLED compare where they overlap?

For armed violence events, both sources should record similar
patterns. Comparing them reveals:
- Coverage gaps in each source
- Systematic differences in fatality estimation
- Geographic regions where sources disagree
- Whether one source is more timely or accurate

---

## 6. Open questions

1. **Access tier.** What ACLED tier does VIEWS qualify for? Research
   tier (12-month lag) vs partner (near real-time). This gates the
   entire integration.

2. **Event type scope.** Should we harvest all ACLED event types or
   only violence? Including protests makes the dataset much larger
   but enables RQ-8. This is a research design decision.

3. **UCDP deduplication.** Some events appear in both UCDP and ACLED.
   How do we handle overlap? Options: keep both (cross-reference),
   prefer one source, or create a merged view. This needs ADR-level
   decision.

4. **Temporal alignment.** ACLED is daily; our grid is monthly. Sum
   events per month (like UCDP)? Or preserve daily granularity in
   the consolidated store and aggregate at viewpoint time?

5. **Actor data.** ACLED's actor fields are valuable but don't fit
   the current grid model (grid cells have features, not actor
   lists). How to encode actor information? Possible: count of
   distinct actors per cell-month.

6. **Regional quality.** ACLED warns that data quality varies by
   region. Should we include a quality indicator per event or per
   country-year? How does this affect model training?

---

## 7. Integration phases

### Phase A1: Access Negotiation
- Register for ACLED account
- Determine available tier (Research / Partner)
- Review terms of use and data sharing restrictions
- Get API credentials
- **Blocker:** Cannot proceed without at least Research tier access

### Phase A2: Investigation (with access)
- Explore API: event types, fields, pagination, rate limits
- Download sample data for one country (e.g., Somalia 2020)
- Compare ACLED and UCDP events for the same country/period
- Quantify: how many ACLED events per UCDP event?
- Document event type taxonomy and field schema

### Phase A3: Harvester
- `src/datafactory_harvester/sources/acled.py`
- `AcledConfig` dataclass (API credentials, event types, date range)
- OAuth authentication handling (token refresh)
- Paginated API fetching (adapt UCDP pattern)
- Per-country or per-year Parquet storage
- Provenance ledger entries

### Phase A4: Consolidation
- Decide: separate ACLED store or combined with UCDP?
- If separate: straightforward (like UCDP consolidation)
- If combined: need cross-source dedup strategy (new ADR)
- Tag events with `_source_type="acled"` for traceability

### Phase A5: Viewpoint and Compilation
- Event type filtering (violence-only profile, all-events profile)
- Compile to grid: same spatial binning as UCDP (lat/lon → pgid)
- New features: `acled_battle_count`, `acled_protest_count`,
  `acled_fatalities`, etc.

### Phase A6: Cross-Source Analysis
- Compare UCDP and ACLED on the same grid
- Quantify agreement/disagreement by region and time
- Publish RQ-8 and RQ-10 findings

---

## 8. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Access denied (Research tier) | Low | Critical | Contact ACLED directly; mention VIEWS partnership with Uppsala |
| Research tier has 12-month lag | Likely | Medium | Acceptable for historical analysis; pursue partner tier later |
| API rate limiting | Medium | Low | Same retry + rate limit pattern as UCDP |
| Event volume overwhelming | Low | Medium | Filter by event type; paginate; store per-country |
| UCDP/ACLED overlap confusion | Medium | High | Keep sources separate; cross-reference in viewpoint |
| Terms of use restrict redistribution | Medium | High | Review before serving via zarr; may need separate access |
