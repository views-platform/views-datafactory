# 06 — Glossary

| Term | Definition |
|---|---|
| **Summary event** | A UCDP record whose fatality total refers to an aggregate over a period and/or a region rather than to a single located incident. UCDP flags the temporal case as `date_prec = 5`; `_SUMMARY_DATE_PREC` in `temporal_distribution.py` encodes it. |
| **Concentrated by measurement** | This program's operational definition: an event assigned wholly to one cell-month while its own UCDP precision fields declare it is not resolved to that cell-month. Two independent mechanisms — temporal (**T**) and spatial (**S**) — and the severe class is **T+S**. |
| **Allocation** | Turning one coarse record into cell-month values. Unavoidable and always a modelling decision, including when the decision is "assign it all to one cell-month". |
| **`date_prec`** | UCDP temporal precision: 1 exact day · 2 ±2 days · 3 week · 4 month · 5 year or coarser. |
| **`where_prec`** | UCDP spatial precision: 1 exact point · 2 ≤25 km · 3 admin-2 · 4 admin-1 · 5 larger than admin-1 · 6 country · 7 international. |
| **Well-located** | `where_prec ≤ 3` (admin-2 or better). ADR-049's weighting source, and this program's ground truth when combined with `date_prec ≤ 2`. |
| **Passthrough** | The current spatial strategy: return the event unchanged whatever its `where_prec`, so it lands on its centroid cell. |
| **`date_end_only`** | The current temporal strategy for annual-source events: one output row at the `date_end` month, whatever the span. |
| **`ceil_split` / `even_split` / `floor_split`** | Span-spreading temporal strategies. `even_split` **conserves** the total; `ceil_split` rounds up per month and **does not** (0.91% inflation measured). |
| **Coarsen-and-recover** | This program's evaluation design: synthetically degrade a well-located event to region × year, re-allocate it, and score the recovery against known truth. |
| **Conservation** | ADR-040 Invariant 1: `placed + excluded = input`, every exclusion declared and quantified. A hard gate, not a metric. |
| **Effective sample size (ESS)** | The participation ratio `(Σc)²/Σc²` over per-cell values in a slice: equals the cell count under equal contribution, 1.0 when one cell carries everything. hydranet's instrument in #533. |
| **Reconciliation family** | ADR-040: administrative levels from one source system sharing a proper containment hierarchy. |
| **Parity / `production_parity`** | The profile reproducing VIEWSER `GedLoader`. A **contract**, not a recommendation — ADR-049 §6 established that parity is achievable via configuration rather than being the only behaviour. |
| **Proxy-population confound** | The declared threat to the evaluation: coarsened well-located events may not resemble genuine summary events, so allocation skill measured on the former may not transfer. |
