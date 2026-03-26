
# ADR-019: Visualization Style Guide

**Status:** Accepted
**Date:** 2026-03-24
**Deciders:** Simon

---

## Context

Visualization scripts (`visualize_audit.py`, `presentation_plots.py`)
each defined their own style constants and helpers.
This produced inconsistencies (DPI 150 vs 200), duplicated code (`style_ax`,
`save_plot`, `make_dates` appear in multiple files), and no single source
of truth for the project's visual identity.

As more plots are added — audit, presentation, diagnostic — drift will
worsen.  A shared style definition ensures all output looks like it came
from the same project.

---

## Decision

All visualization scripts import style constants and helpers from a shared
module: **`scripts/viz_style.py`**.

**In scope:**
- Resolution (DPI)
- Figure sizes (FIG_FULL, FIG_HALF, etc.)
- Typography (FONT_TITLE, FONT_LABEL, FONT_TICK, FONT_ANNOT)
- Colormaps (CMAP_SEQ, CMAP_DIV, CMAP_HEAT, CMAP_COV, CMAP_ONSET)
- Domain colors: violence types (COLOR_SB, COLOR_NS, COLOR_OS), accent, gray
- Spatial extent (EXTENT)
- Shared helpers: `style_ax`, `save_plot`, `spatial_imshow`, `make_dates`

**Out of scope:**
- No `src/datafactory_*` package for visualization.  Viz is a consumer tool
  that lives in `scripts/`, outside the package graph (ADR-012).
- No `.mplstyle` file.  Most of our style is domain-specific (violence-type
  colors, spatial helpers, figure-size presets) which rcParams cannot express.
  One module is simpler than two mechanisms.
- Script-specific domain data (PEAK_EVENTS, REGION_BOUNDS, GAUL codes)
  stays in the scripts that use it — that is content, not style.

---

## Rationale

- **Single source of truth** prevents aesthetic drift across scripts.
- **Module over `.mplstyle`** because our needs are mostly domain-specific
  constants and helper functions, not generic rcParams.
- **`scripts/` not `src/`** because visualization code sits outside the
  data graph (ADR-012) and does not need to be an installable package.
- **Tufte-derived aesthetic** (minimal chrome, no top/right spines, restrained
  color) is appropriate for research-grade conflict data visualization.

---

## Considered Alternatives

### Alternative A: `.mplstyle` file only
- **Pros:** Native matplotlib mechanism, well-known.
- **Cons:** Cannot express domain colors, figure-size presets, or helper
  functions.  Would still need a companion module for the rest.
- **Reason for rejection:** One mechanism simpler than two.

### Alternative B: New `src/datafactory_viz` package
- **Pros:** Installable, testable, importable from anywhere.
- **Cons:** Viz is a consumer tool, not part of the data graph.  Adding a
  `src/` package for scripts violates ADR-012 layer separation.
- **Reason for rejection:** Architectural mismatch.

### Alternative C: Constants in each script (status quo)
- **Pros:** No coupling between scripts.
- **Cons:** Already producing drift (DPI 150 vs 200), duplicated code.
- **Reason for rejection:** Does not scale.

---

## Consequences

### Positive
- Consistent appearance across all plots
- DPI, fonts, colors defined once
- Helpers (`style_ax`, `save_plot`, `spatial_imshow`) maintained in one place
- New scripts get the shared style with a single import

### Negative
- Scripts now depend on `viz_style.py` — moving or renaming it requires
  updating imports (low cost, `scripts/` is a flat directory)

---

## Implementation Notes

- `scripts/viz_style.py` exports constants and helpers
- `visualize_audit.py` and `presentation_plots.py` import from it instead
  of defining their own
- DPI standardized to 200 across all scripts
- New visualization scripts should `from viz_style import ...`

---

## Validation & Monitoring

- `ruff check scripts/viz_style.py` passes
- Grep for `DPI =`, `FONT_TITLE =` in consuming scripts should return
  zero matches (all definitions live in `viz_style.py`)
- Visual spot-check: existing plots unchanged in appearance

---

## Open Questions

- Whether to add a color palette for country-pair comparisons (currently
  defined ad hoc in presentation scripts).  Deferring until the palette
  stabilizes.

---

## References

- ADR-012: Four-layer data architecture (viz sits outside the graph)
- `scripts/viz_style.py`: Implementation
