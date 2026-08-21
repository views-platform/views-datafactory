# Investigation: Area-Majority GAUL Assignment

**Issue:** #115
**Branch:** `investigation/115-area-majority-spatial-join`
**Risk register:** C-149 (Tier 2 — silent data gap)
**Started:** 2026-06-04
**Investigators:** Simon Polichinel von der Maase, Claude Code
**Status:** Complete — ADR-039 accepted, pipeline integrated, all consumers verified.
**Reopened 2026-08-21** for H6 (projection sensitivity, #465/#387): **falsified**, 9 of 3,591
high-latitude border cells rank differently under true area, all nine at `gaul2` or below, none
at `gaul0`. Result in `projection_sensitivity.json`, narrative in `progress_log.md`, tracked as
C-353. **The delivered artifact was deliberately not corrected** — see the §4 decision table.

---

## Problem

The datafactory assigns PRIO-GRID cells to GAUL countries using centroid-in-polygon spatial join (`gaul_admin.py:183-260`). 149 coastal cells have centroids in water, receiving `gaul0_code = -1` (unassigned). These cells carry 409,743 fatalities (~3.9% of the state-based total), which are silently dropped from country-level aggregations. FAO requires area-majority assignment (Release Note 02, locked decision).

Root cause analysis: `reports/postmortem_cm_unmapped_gaul_cells.md`

## Contents

- [pre_analysis_plan.md](pre_analysis_plan.md) — Pre-registered hypotheses, decision criteria, and expected outcomes (commit before experiments)
- [approach_evaluation.md](approach_evaluation.md) — Five spatial join approaches evaluated with benchmarks and evidence
- [implementation_roadmap.md](implementation_roadmap.md) — Phased work plan with effort estimates and sequencing
- [definitions_of_done.md](definitions_of_done.md) — Unambiguous exit criteria for each implementation phase
- [progress_log.md](progress_log.md) — Timestamped record of what happened, what changed, and why
- [draft_adr_039_area_majority_gaul.md](draft_adr_039_area_majority_gaul.md) — Draft Architecture Decision Record (moves to `docs/ADRs/` when finalized)

## Methodology Note

This investigation uses **pre-registration**: hypotheses and decision criteria are stated before experiments are run, and deviations are logged explicitly. This follows the Statistical Analysis Plan (SAP) framework adapted for software engineering, ensuring methodology changes are principled rather than post-hoc rationalized. The pre-analysis plan must be committed before any implementation code is written.
