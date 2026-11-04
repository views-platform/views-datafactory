# 04 — Roadmap

**Date:** 2026-11-04 · Phases are **gated**: a phase does not start until the prior gate is green.

```
P0 governance ──► P1 harness ──► P2 spatial (O1) ──┐
                      │                            ├──► P4 declare (O3) ──► P5 promote
                      └──────────► P3 temporal (O2)┘
```
P2 and P3 are independent once P1 is green and may run in either order; **not concurrently** (one
variable at a time).

---

## P0 — Governance: resolve the ADR-049 divergences
**Not research.** An accepted ADR is either live or amended; it cannot be neither.

- Decide: does ADR-049 §6's "on by default" stand, and if so why is `production_parity` the invoked
  profile? Amend ADR-049 with a dated amendment per the repo's editorial rule (amend, never rewrite).
- Correct ADR-049's §Context worked example, which states event 463131 "is spread across 12 months
  by temporal distribution (correct)". It is not spread at all.
- Route both divergences plus the `ceil_split` 0.91% conservation violation to `register-risk`.

**Gate G0:** ADR-049 says what the code does, or says what the code should do and names what will
observe the difference. ⚠️ *The latter is the real lesson of C-365 — a decision with nothing watching
it is how this stayed invisible for four months.*

## P1 — Build the evaluation harness
Everything in `03 §C`. This is the substantive engineering and it blocks every experiment.

- C1 coarsen-and-recover evaluator · C2 three locked baselines · C3 parity-inertness test (seen to
  fail) · C4 ADR-049 golden test (expected red) · C5 conservation assertions.
- `expert-method-review` on `02_design` before pre-registering anything.

**Gate G1:** the four blockers in `03 §D` green; the uniform and oracle baselines frozen as a
fixture; the parity-inertness test demonstrated red when broken.

## P2 — Spatial allocation (O1): make the decided thing live and measure it
The hypothesis is *not* "distribution is better" — ADR-049 already asserted that. The hypothesis is
**"ADR-049's proportional weighting beats uniform allocation by a margin that justifies its extra
assumption."** That is the untested part, and ADR-049's own fallback is uniform, so the control is
free.

- Pre-register. Primary endpoint: earth-mover distance vs truth on the coarsened population, with a
  numeric threshold against the uniform baseline.
- Stratify by event size and conflict intensity — the declared proxy-population confound.

**Gate G2:** proportional beats uniform on the primary endpoint, conservation holds exactly, and
`production_parity` is byte-identical. If proportional does *not* beat uniform, that is a publishable
negative result and ADR-049 needs amending, not defending.

## P3 — Temporal allocation (O2): the genuinely undecided half
17.79% of mass, and the half nobody has decided. This is where the literature gap bites hardest
(`01 §B`: temporal disaggregation/benchmarking, 0 papers).

- **Fetch the gap literature first** (Denton 1971; Chow–Lin 1971; Dagum–Cholette). We should not
  reinvent a 1971 solution; `even_split` is a crude member of a known family.
- Pre-register a comparison: `date_end_only` (control) vs `even_split` (conserving) vs a
  benchmarking-style allocation informed by covariates, if the literature supports one.
- ⚠️ `ceil_split` is **not** a candidate: it does not conserve.

**Gate G3:** a conserving temporal strategy beats `date_end_only` on recovery, and beats uniform-
over-span, with parity untouched.

## P4 — Declare (O3): the per-cell-month provenance flag
Independent of whether P2/P3 change any allocation — and the thing #533 actually asked for.

- Emit per cell-month: concentrated mass, its share of the cell-month, and the coarsest contributing
  `date_prec`/`where_prec`. The two catalog CSVs are already a working prototype of this join.
- Extend the consumer contract (ADR-050) and the boundary declaration (ADR-009). Expect the
  byte-identical fixture gate to go red by design — regenerate deliberately, do not suppress.

**Gate G4:** a downstream consumer can distinguish a real massacre from a reporting artifact without
re-deriving it from the event store. That is the acceptance criterion in #533's own words.

## P5 — Promote
`/rnd-dossier promote`: draft a proposed ADR from `02_design` amending/extending ADR-049, cross-link
this dossier as the evidence trail, route residual methodological risks to `register-risk`, archive
to `reports/archived/`.

---

## Decision points

| # | Decision | Whose | When |
|---|---|---|---|
| D1 | Does the pipeline keep invoking `production_parity` as default? | **Simon, with Håvard** — it moves every published figure | before P2 lands, not before it runs |
| D2 | Is `ceil_split`'s 0.91% inflation in scope? | Simon | P0 |
| D3 | Fetch the five missing literatures (`01 §B`)? | Simon | before P3 |
| D4 | Does O3 ship independently of P2/P3? | Simon | P4 — recommend **yes**, it is provenance, not allocation |

## Explicitly out of scope

Weighted/scale-invariant scoring (O5) and intensity-measure targets (O6) are **downstream**, per the
line ADR-049's *Deferred* section already drew. They are comparators here, never deliverables. Actor-
informed weighting is deferred by ADR-049 and stays deferred.
