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

**What it is:** Monthly installments of newly-coded conflict events, primarily covering one calendar month.

**Coverage:** Each version primarily contains events from one calendar month (~98-99% of events). However, every version checked also includes a small number of events from other months (0.1-1.4%), sometimes from several months earlier. This appears to be by design — UCDP incorporates late-coded or corrected events into the version being released at the time.

**Event count per version:** ~900-2,500 events per month (varies by conflict intensity).

**Update cadence:** Monthly. One new version per month.

**Characteristics:**
- Each version primarily covers one calendar month, with a small number of events from other months
- Event ID overlap between versions is generally absent (1,952 of 1,953 checked pairs have zero overlap)
- One known exception: 21.0.4 and 21.0.5 share 606 event IDs — likely a data anomaly from early 2021 when the candidate system was being established
- To get "all candidate data for 2025," you need ALL 12 monthly versions
- Versions are additive — like magazine issues, not revised editions
- Older versions (2018-2020) may return zero events when fetched (possibly expired from the API)
- Early versions (21.0.1 through 21.0.4) have unusually low event counts, suggesting the system was not fully operational

**ID overlap (exhaustive check across 63 versions, 1,953 pairs):**

| Check | Result |
|-------|--------|
| Total pairs checked | 1,953 |
| Pairs with zero overlap | 1,952 (99.95%) |
| Pairs with overlap | 1 (21.0.4 ∩ 21.0.5 = 606 shared IDs) |

**Date ranges (each primarily covers ~1 month, with outliers):**

| Version | Primary month | Events from primary month | Events from other months |
|---------|--------------|--------------------------|-------------------------|
| 25.0.1 | Jan 2025 | 1,158 (99.9%) | 1 from Dec 2024 |
| 25.0.6 | Jun 2025 | 1,273 (99.8%) | 3 from May 2025 |
| 25.0.12 | Dec 2025 | 907 (99.5%) | 5 from Jan/Oct/Nov 2025 |
| 24.0.11 | Nov 2024 | 1,375 (98.6%) | 19 from Jan/Sep/Oct 2024 |
| 24.0.12 | Dec 2024 | 1,103 (99.4%) | 7 from Jan/Jun/Jul/Nov 2024 |

**Analogy:** Monthly magazine issues. Each issue primarily has that month's articles, but occasionally includes a correction or late addition from a prior month.

---

## 3. The .9 Consolidated Monthly (e.g., 25.9.11)

**What it is:** A rolling consolidated window produced by UCDP, typically covering ~13 months of events.

**Coverage:** Each version is a COMPLETE snapshot of its window. It is self-contained — you don't need previous .9 versions to use it. Window length is typically 13 months (~90% of versions), but ranges from 13 to 25 months across the full history (see falsification results below).

**Event count per version:** 11,000-33,000 events (varies by year and conflict levels).

**Update cadence:** Monthly. Each new version slides the window forward by one month.

**Characteristics:**
- Each version is a complete snapshot of its window (NOT additive like candidates)
- Consecutive .9 versions typically overlap ~88-93% in recent years (2022-2024), but overlap varies from 41.5% to 100% across the full history
- Contains exclusive events not in the annual release — count varies from ~350 to ~2,600 per version (3-12% of content), depending on year and conflict levels
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
| 18.9.1 vs 18.9.2 | 12,841 | 100% |
| 21.9.1 vs 21.9.2 | 10,917 | 41.5% |
| 24.9.2 vs 24.9.3 | 23,498 | ~90% |
| 24.9.5 vs 24.9.6 | 24,887 | ~88% |

**Known anomalies:**
- 21.9.1 spans 25 months (Jan 2019 – Jan 2021) instead of ~13 — likely related to the Tigray conflict escalation
- 5 versions span 14 months, 2 span 15 months — minor boundary variations
- Window length distribution: 13 months (70 versions), 14 months (5), 15 months (2), 25 months (1)

**Analogy:** A security camera with a recording loop that's usually ~13 months but occasionally stretches longer. Each month, the oldest footage typically drops off and new footage is added. Some footage is exclusive — not in any archive.

---

## How They Relate to Each Other

### Annual ↔ Candidate: No ID Overlap (Different Time Periods)

The annual v25.1 covers through 2024. Candidates from 2025+ contain events primarily from 2025 onward. No shared event IDs have been observed. However, some candidate versions contain a small number of events with dates in 2024 (e.g., 25.0.1 has 1 event from Dec 2024), so there is minor temporal overlap even though event IDs are disjoint.

### Annual ↔ .9: Partial Overlap

The .9 rolling window overlaps with the tail end of the annual's coverage. Empirically (annual v25.1 vs .9 24.9.6):
- 25,546 events shared (66% of .9)
- 2,593 events exclusive to .9 (9.2% of .9 content)
- 359,372 events only in annual (the historical base)

### Candidate ↔ .9: No ID Overlap in Most Data

For most of our harvested data, candidates (2025+) and .9 versions (through mid-2024) cover different time windows and share no event IDs. However, .9 versions that cover the same months as candidates (e.g., 25.9.11 covering Nov 2024 – Nov 2025) may share events with candidates from that same period.

### Visual Timeline

```
1989                          2024    2025    2026
 |                              |       |       |
 ████████████████████████████████       |       |    ANNUAL v25.1
                                |       |       |
                                ════════════╗   |    .9 (rolling ~13-month window)
                                 ════════════╗  |    Each .9 slides by 1 month
                                  ════════════╗ |
                                |       |       |
                                |  · · · · · · ··    CANDIDATES (monthly, mostly independent)
                                |  Each dot ≈ 1 month, generally no ID overlap
```

---

## What This Means for Production

VIEWS production fetches ONE .9 version per month and processes it. The .9 is self-contained — it has everything needed for the trailing ~13 months (typically). Annual data provides the historical base (before the .9 window). Candidates are not used in production — they're a subset of what the .9 already contains.

For our `production_parity` profile: consolidate all three sources, but the `dot9_wins` survivorship will prefer .9 data in its window, falling back to annual for historical data. Candidates are kept for vintage analysis but won't win survivorship in the .9 window.
