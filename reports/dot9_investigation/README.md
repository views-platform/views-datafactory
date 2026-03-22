# Investigation: UCDP .9 Consolidated Dataset

**Date:** 2026-03-21
**Investigators:** Simon Polichinel von der Maase, Claude Code
**Status:** Active — findings documented, open questions remain

---

## Executive Summary

VIEWS production forecasting depends on a bespoke UCDP data product called the `.9` version (format `YY.9.MM`). This investigation found that the `.9` contains **42% exclusive content** (13,005 events, 58,159 fatalities) not available through any standard UCDP API endpoint — neither annual releases nor candidate monthly releases.

This is significant because:
1. The `.9` is undocumented — no codebook, no schema specification, no UCDP publication references it
2. The only documentation is one paragraph in a production notebook
3. That paragraph's description ("latest candidate + updated data for last 12 months") is empirically incomplete
4. VIEWS cannot reproduce the production data pipeline without fetching `.9` directly

## Contents

- [findings.md](findings.md) — Full empirical findings: what we know, what we infer, what we don't know
- [reproducibility_note.md](reproducibility_note.md) — Observations on candidate data mutability and implications for scientific reproducibility
- [data_streams.md](data_streams.md) — What each UCDP dataset contains: annual, candidate, .9 — coverage, overlap, relationships
- [parity_results.md](parity_results.md) — Production parity test results: 100% match on non-expanded events, methodology, code path mapping
