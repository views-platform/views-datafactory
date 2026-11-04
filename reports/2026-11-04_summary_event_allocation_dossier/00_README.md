# R&D Dossier — Allocation of summary events in space and time

**Opened:** 2026-11-04 · **Status:** scaffolded; harness audit complete; **not ready to run experiments**
**Prompted by:** #533 (views-hydranet), #484, and the catalog in
`reports/investigation_summary_event_concentration/findings.md`

---

## 1. Purpose

UCDP records some fatality totals as aggregates over a region and a time window — a year of the
Tigray war across three Ethiopian regions, for instance. The viewpoint layer must turn each such
record into cell-month values, and today it assigns the whole total to one 0.5° cell in one month.
**21,766 events carrying 21.95% of all fatality mass are allocated to a cell-month their own UCDP
precision fields disown**, and in 2020–2024 that share is **48.8%**. This program asks what the
defensible allocation options are, how to evaluate them *inside this repo's responsibilities*, and
how they rank under that evaluation.

## 2. Relationship to prior work

This program does **not** start from a blank slate, and the single most important finding of `init`
is how much is already decided:

| Prior art | Relationship |
|---|---|
| **ADR-049** (Accepted 2026-06-28) — *Spatial Distribution of Imprecise UCDP Events* | **Already decided the spatial half**, including the polygon mechanism, proportional weighting by well-located fatalities, conservation, and "on by default". It names cell 148759 and event 463131 explicitly. **It is not live in `production_parity`.** See §3 of `02_design`. |
| **ADR-040** — *Count Conservation and Hierarchical Reconciliation* | Supplies the hard invariants any option must satisfy. `ceil_split`'s 0.91% inflation appears to violate Invariant 1 — routed to the register, not resolved here. |
| **ADR-023** — *Viewpoint Builder Invariants* | Governs temporal distribution decisions. |
| **ADR-016 / ADR-014** — *Viewpoint Profiles / Viewpoints as Derived Views* | The profile mechanism is this program's flag mechanism. |
| **ADR-009** — *Boundary Contracts* | Governs what this repo may declare to consumers; the basis for the per-cell-month flag option. |
| `reports/investigation_summary_event_concentration/findings.md` | The measurement this program reacts to. Not superseded — it is the evidence base. |
| **The legacy `GedLoader` notebook** (ingester3 / `views3`) | Supplied 2026-11-04. Confirms our parity claims are faithful, and exposes a **third** divergence: legacy country-month included `where_prec` 4/6 events (~19% of mass) while ours excludes them. See `08`. |

**Nothing is superseded by this dossier.** It is a staging area, and on `promote` its design
graduates to a proposed ADR amending or extending ADR-049.

## 3. Document index

| # | File | Status |
|---|---|---|
| 00 | `README` | living — this file |
| 01 | `literature` | **drafted** — 840-paper survey + a verified 17-item acquisition list in 3 tiers |
| 02 | `design` | **drafted** — the option space and the repo-boundary cut |
| 03 | `harness_and_invariants` | **drafted** — audit complete, gaps flagged |
| 04 | `roadmap` | **drafted** — gated phases |
| 05 | `analysis_plan` | **stub** — awaits `/rnd-dossier preregister` after a method review |
| 06 | `glossary` | drafted |
| 07 | `experiment_log` | empty (append-only) |
| 08 | `legacy_gedloader` | **drafted** — what the old `views3` ingestion actually did, and the parity divergence it exposes |
| 09 | `library_acquisitions` | **drafted** — the 19-item fetch list, 3 tiers, verified citations |

## 4. Harness at a glance

The audit found **most of the standing harness already in place** — see `03`. In brief:

**Already exists:** an OCP strategy registry (`datafactory_provenance.registry.Registry`) so a new
allocation strategy is registered without touching the builder · profile-based configuration that
makes any new strategy default-off by construction · 2,433-test suite with branch protection and
`enforce_admins` · byte-identical fixture and digest gates (ADR-050) · a synthetic known-answer
pipeline with 25 tests · provenance ledgers with per-exclusion-reason counts · 16 post-mortems, so
negative results have an established home.

**The gaps that block the first experiment:** there is **no evaluation harness for allocation
quality at all** — no locked baseline, no metric protocol, no ground truth. That is the real build,
and it is constructible (see `03 §C` and `02 §5`).

## 5. Current state & next actions

- [x] Measure the problem → `reports/investigation_summary_event_concentration/findings.md`
- [x] Library survey → `01_literature`
- [x] Harness audit → `03_harness_and_invariants`
- [x] Option space + boundary cut → `02_design`
- [ ] **Resolve the three parity/ADR divergences** (blocker). Governance, not research:
      (i) ADR-049 is accepted but not live; (ii) its worked example misdescribes the code
      (`02 §3`); (iii) `production_parity` does not reproduce the legacy country-month path,
      which included `where_prec` 4/6 — ~19% of fatality mass (`08 §3`).
- [ ] **Acquire the Tier 1 literature** (`01 §B`) — 7 items, citations verified 2026-11-04. Two of
      them (Gotway & Young 2002; Heitjan & Rubin 1991) supply frameworks we are currently reasoning
      without; one (Weidmann 2015) has already changed the evaluation design
- [ ] `expert-method-review` on `02_design` — specifically the coarsen-and-recover evaluation and
      its two declared confounds
- [ ] Build the evaluation harness (`03 §C`) — **blocks the first experiment**
- [ ] `/rnd-dossier preregister` the first experiment
- [ ] Route to `register-risk`: the CM/PGM parity divergence; the ADR-049 divergences; the
      `ceil_split` inflation **and** the legacy end-month truncation (both inherited, `08 §1`/`§2c`)

## 6. Conventions

Numbered docs, dated in-header; `00` is living, `07` is append-only. `reports/` is **not** gitignored
in this repo, so no `git add -f` is needed. On close the directory moves to `reports/archived/`.
Every experiment links its pre-registration and states its verdict against pre-committed falsifiers.
Negative results are recorded with the same prominence as wins.
