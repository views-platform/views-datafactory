# 05 — Analysis plan

**Status: STUB — deliberately empty.**

No experiment may be pre-registered until **Gate G1** in `04_roadmap.md` is green, because a
pre-registration without a locked baseline and a working evaluator cannot state a numeric pass/fail
threshold, and a plan whose falsifiers cannot fire is theatre.

The first plan will be written with `/rnd-dossier preregister` and will cover **P2 — spatial
allocation (O1)**, testing the one part ADR-049 asserted but never measured:

> **H:** ADR-049's proportional weighting by well-located fatalities recovers the true spatial
> allocation of a coarsened event better than uniform allocation over the same polygon, by a margin
> that justifies its additional assumption.

Pre-committed skepticism to carry into that plan (from `02 §5` and `01 §A3`):

1. The coarsened well-located population is a **proxy** for genuine summary events and may not
   transfer — genuine summary events are larger, war-concentrated, and differently reported.
2. Proportional weighting **reinforces existing spatial concentration** by construction (ADR-049
   names this as a known property). A gain on earth-mover distance could coexist with a worsened
   effective sample size — the remedy moving the spike rather than removing it.
3. `Vesco2026`: large aggregates are the **most** accurately counted values we hold. Any apparent
   improvement that comes from shrinking them is masking.
4. Beating `passthrough` is a low bar. **Uniform is the real control.**
5. `Weidmann (2015)`: UCDP-GED locational accuracy **degrades sharply below district scale**, and our
   cells are ~55 km. The ground truth we score against carries its own error, the oracle is not a
   true ceiling, and the metric must tolerate small displacement (`02 §5`, confound C-b).

Per `templates.md`, the plan must carry a primary endpoint with a numeric threshold, a control that
rules out the obvious confound, and falsifiers that are pre-committed and not rescued.
