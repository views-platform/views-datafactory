"""Shared visual style for all visualization scripts.

Provides a Tufte-derived aesthetic: minimal chrome, clear typography,
domain-specific color palettes for conflict data.  All plotting scripts
in ``scripts/`` import from here instead of defining their own constants.

See ADR-019 for rationale and design decisions.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

# ── Resolution ──────────────────────────────────────────────

DPI = 200

# ── Figure sizes ────────────────────────────────────────────

FIG_FULL = (14, 7)
FIG_HALF = (7, 7)
FIG_TALL = (7, 12)
FIG_PANEL_2x2 = (14, 9)
FIG_PANEL_1x3 = (14, 5)
FIG_PANEL_4x3 = (14, 10)

# ── Typography ──────────────────────────────────────────────

FONT_TITLE = 13
FONT_LABEL = 10
FONT_TICK = 8
FONT_ANNOT = 8

# ── Colormaps ───────────────────────────────────────────────

CMAP_SEQ = "YlOrRd"
CMAP_DIV = "RdBu_r"
CMAP_HEAT = "Reds"
CMAP_COV = "viridis"
CMAP_ONSET = "plasma"

# ── Domain colors: UCDP violence types ──────────────────────

COLOR_SB = "#7A8B3C"   # State-based (green)
COLOR_NS = "#4878A8"   # Non-state (blue)
COLOR_OS = "#D4752E"   # One-sided (orange)

# ── Domain colors: ACLED event types ─────────────────────────

COLOR_BATTLES = "#C0392B"      # red
COLOR_EXPLOSIONS = "#E67E22"   # orange
COLOR_VAC = "#8E44AD"          # purple
COLOR_PROTESTS = "#2ECC71"     # green
COLOR_RIOTS = "#3498DB"        # blue
COLOR_STRATEGIC = "#95A5A6"    # gray

# ── Accent / neutral ────────────────────────────────────────

COLOR_ACCENT = "#2C5080"
COLOR_GRAY = "#666666"

# ── Spatial ─────────────────────────────────────────────────

EXTENT = [-180, 180, -90, 90]


# ── Helpers ─────────────────────────────────────────────────


def style_ax(
    ax: object,
    *,
    title: str | None = None,
    xlabel: str | None = None,
    ylabel: str | None = None,
) -> None:
    """Apply Tufte-compliant style: remove top/right spines, set fonts."""
    ax.spines["top"].set_visible(False)  # type: ignore[union-attr]
    ax.spines["right"].set_visible(False)  # type: ignore[union-attr]
    ax.tick_params(labelsize=FONT_TICK)  # type: ignore[union-attr]
    if title:
        ax.set_title(  # type: ignore[union-attr]
            title, fontsize=FONT_TITLE, fontweight="bold",
        )
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=FONT_LABEL)  # type: ignore[union-attr]
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=FONT_LABEL)  # type: ignore[union-attr]


def save_plot(fig: object, output_dir: Path, name: str) -> None:
    """Save figure at shared DPI, tight bbox, white background, then close."""
    import matplotlib.pyplot as plt

    fig.savefig(  # type: ignore[union-attr]
        output_dir / name, dpi=DPI, bbox_inches="tight",
        facecolor="white",
    )
    plt.close(fig)  # type: ignore[arg-type]
    print(f"  \u2192 {name}")


def spatial_imshow(
    ax: object,
    data_2d: np.ndarray,
    ocean_mask: np.ndarray,
    cmap: str,
    *,
    vmin: float | None = None,
    vmax: float | None = None,
    log: bool = False,
    cbar_label: str | None = None,
    fig: object | None = None,
) -> object:
    """Mask ocean, flip, imshow on equirectangular projection.

    Returns the image handle (for further colorbar customization).
    """
    import numpy as np

    display = data_2d.astype(np.float64).copy()
    display[ocean_mask] = np.nan
    if log:
        display = np.where(
            np.isnan(display), np.nan, np.log1p(display),
        )
    display = np.flipud(display)
    im = ax.imshow(  # type: ignore[union-attr]
        display, cmap=cmap, aspect="auto", extent=EXTENT,
        vmin=vmin, vmax=vmax,
    )
    if cbar_label and fig is not None:
        import matplotlib.pyplot as plt

        plt.colorbar(im, ax=ax, label=cbar_label)
    return im


def make_dates(n_t: int, start_year: int = 1989) -> list[dt.date]:
    """Generate monthly date labels starting from *start_year*-01-15."""
    return [
        dt.date(start_year + t // 12, 1 + t % 12, 15)
        for t in range(n_t)
    ]
