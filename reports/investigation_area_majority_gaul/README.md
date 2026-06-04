# Investigation: Area-Majority GAUL Assignment

**Issue:** #115
**Branch:** `investigation/115-area-majority-spatial-join`
**Risk register:** C-149 (Tier 2 — silent data gap)
**Started:** 2026-06-04
**Investigators:** Simon Polichinel von der Maase, Claude Code
**Status:** Investigation phase — evidence gathered, pre-analysis plan registered

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
