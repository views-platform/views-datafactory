# UCDP Data Streams: What Each Dataset Contains

**Date:** 2026-03-21
**Method:** Empirical analysis of actual Parquet files
**Data source:** `data/full_harvest/` and `data/smoke_test/`

---

## Overview

UCDP provides conflict event data through three distinct streams. Each has different temporal coverage, update cadence, and overlap characteristics. Understanding these differences is essential for consolidation and viewpoint design.

---

## 1. Annual (e.g., v25.1)

**What it is:** A single, comprehensive, curated historical snapshot.

**Coverage:** All conflict events from 1989 to the end of the prior year (currently 1989-2024).

**Event count:** 384,918 events in v25.1.

**Update cadence:** Roughly once per year. Each new version (v26.1, v27.1, etc.) replaces the previous and may revise events from prior years.

**Characteristics:**
- ONE file, ONE version at a time
- Authoritative — published with codebooks and DOIs
- May revise events from prior years compared to the previous annual release
- Does NOT contain events from the current year (v25.1 ends at Dec 2024)

**Events per year (sample from v25.1):**

| Year | Events |
|------|--------|
| 1989 | 2,624 |
| 2000 | 4,193 |
| 2010 | 6,685 |
| 2020 | 13,818 |
| 2022 | 20,774 |
| 2023 | 26,486 |
| 2024 | 28,816 |

**Analogy:** A textbook updated once per year. Each edition is the complete, authoritative reference.

---

## 2. Candidate Monthly (e.g., 25.0.1 through 25.0.12)

**What it is:** Independent monthly installments of newly-coded conflict events.

**Coverage:** Each version contains ONLY events that became known in that calendar month. There is **zero overlap** between consecutive candidate versions.

**Event count per version:** ~900-2,500 events per month (varies by conflict intensity).

**Update cadence:** Monthly. One new version per month.

**Characteristics:**
- Each version is an independent, disjoint set of events
- No event ID appears in more than one candidate version
- To get "all candidate data for 2025," you need ALL 12 monthly versions
- Versions are additive — like magazine issues, not revised editions
- Older versions (2018-2020) may return zero events when fetched (possibly expired from the API)

**Empirically confirmed (zero overlap between versions):**

| Version pair | Shared event IDs |
|-------------|-----------------|
| 25.0.1 vs 25.0.2 | 0 |
| 25.0.1 vs 25.0.6 | 0 |
| 25.0.2 vs 25.0.3 | 0 |

**Date ranges (each covers ~1 month):**

| Version | Date range | Events |
|---------|-----------|--------|
| 25.0.1 | 2024-12-30 to 2025-01-31 | 1,159 |
| 25.0.6 | 2025-05-27 to 2025-06-30 | 1,276 |
| 25.0.12 | 2025-11-22 to 2025-12-31 | 912 |

**Analogy:** Monthly magazine issues. Each issue has new articles. You collect them all to have the full year.

---

## 3. The .9 Consolidated Monthly (e.g., 25.9.11)

**What it is:** A rolling 13-month consolidated window produced by UCDP, containing all events from the trailing ~13 months.

**Coverage:** Each version is a COMPLETE snapshot of its 13-month window. It is self-contained — you don't need previous .9 versions to use it.

**Event count per version:** 11,000-33,000 events (varies by year and conflict levels).

**Update cadence:** Monthly. Each new version slides the window forward by one month.

**Characteristics:**
- Each version is a complete 13-month snapshot (NOT additive like candidates)
- Consecutive .9 versions overlap ~88% (the window slides by 1 month)
- Contains ~2,600 events per version NOT in the annual release (exclusive content)
- Available from 18.9.1 (Jan 2018) through at least 26.9.2 (Feb 2026)
- Produced by UCDP specifically for VIEWS — undocumented in any codebook
- This is what VIEWS production uses for monthly forecasting

**Rolling window pattern:**

| Version | Window | Events |
|---------|--------|--------|
| 24.9.1 | Jan 2023 – Jan 2024 | 25,963 |
| 24.9.2 | Feb 2023 – Feb 2024 | 25,290 |
| 24.9.3 | Mar 2023 – Mar 2024 | 25,790 |
| 24.9.4 | Apr 2023 – Apr 2024 | 25,780 |
| 24.9.5 | May 2023 – May 2024 | 26,842 |
| 24.9.6 | Jun 2023 – Jun 2024 | 28,139 |

**Overlap between consecutive versions:**

| Version pair | Shared IDs | Overlap % |
|-------------|-----------|-----------|
| 24.9.1 vs 24.9.2 | 22,915 | ~88% |
| 24.9.2 vs 24.9.3 | 23,498 | ~90% |
| 24.9.5 vs 24.9.6 | 24,887 | ~88% |

**Analogy:** A security camera with a 13-month recording loop. Each month, the oldest footage drops off and new footage is added. Some footage is exclusive — not in any archive.

---

## How They Relate to Each Other

### Annual ↔ Candidate: No Overlap

The annual covers through 2024. Candidates start at 2025. Different time periods → different event IDs → zero overlap.

### Annual ↔ .9: Partial Overlap

The .9 rolling window overlaps with the tail end of the annual's coverage. Empirically (annual v25.1 vs .9 24.9.6):
- 25,546 events shared (66% of .9)
- 2,593 events exclusive to .9 (9.2% of .9 content)
- 359,372 events only in annual (the historical base)

### Candidate ↔ .9: No Overlap (in current data)

Candidates cover 2025+. Available .9 versions cover through mid-2024. Different windows → zero overlap.

However, future .9 versions (25.9.x) would overlap with 25.0.x candidates. We confirmed this with 25.9.11: it overlaps with candidate data from the same period.

### Visual Timeline

```
1989                          2024    2025    2026
 |                              |       |       |
 ████████████████████████████████       |       |    ANNUAL v25.1
                                |       |       |
                                ════════════╗   |    .9 (rolling 13-month window)
                                 ════════════╗  |    Each .9 slides by 1 month
                                  ════════════╗ |
                                |       |       |
                                |  · · · · · · ··    CANDIDATES (monthly, independent)
                                |  Each dot = 1 month, no overlap
```

---

## What This Means for Production

VIEWS production fetches ONE .9 version per month and processes it. The .9 is self-contained — it has everything needed for the trailing 13 months. Annual data provides the historical base (before the .9 window). Candidates are not used in production — they're a subset of what the .9 already contains.

For our `production_parity` profile: consolidate all three sources, but the `dot9_wins` survivorship will prefer .9 data in its window, falling back to annual for historical data. Candidates are kept for vintage analysis but won't win survivorship in the .9 window.
