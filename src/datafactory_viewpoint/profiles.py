"""Named viewpoint profiles — pre-configured research choice sets.

A profile is a named combination of strategy choices (survivorship,
distribution, etc.) that defines a specific viewpoint. Users either
pick a profile by name or freestyle with individual strategy keys.

Adding a new profile means calling _register() — no changes to the
builder or config classes (OCP).

Usage:
    # Pick from menu
    config = load_profile("production_parity", my_path)

    # Freestyle (no profile)
    config = ViewpointConfig(consolidated_path=my_path, ...)

    # Preset with override
    config = load_profile("production_parity", my_path,
                           distribution_strategy="ceil_split")
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from datafactory_viewpoint.viewpoint_config import ViewpointConfig

if TYPE_CHECKING:
    from datafactory_viewpoint.builders.acled_v1 import (
        AcledViewpointConfig,
    )

logger = logging.getLogger(__name__)

__all__ = [
    "load_profile",
    "load_acled_profile",
    "list_profiles",
    "list_acled_profiles",
]

PROFILES: dict[str, dict[str, Any]] = {}


def _register(name: str, **kwargs: Any) -> None:
    """Register a named viewpoint profile."""
    kwargs["version"] = name  # Version tag always matches profile name
    PROFILES[name] = kwargs
    logger.info("Registered viewpoint profile: %s", name)


def load_profile(
    name: str,
    consolidated_path: Path,
    **overrides: Any,
) -> ViewpointConfig:
    """Load a named viewpoint profile.

    Combines the profile's research choices with the caller's
    runtime paths. Overrides allow tweaking individual choices.

    Args:
        name: Profile name (e.g., "production_parity").
        consolidated_path: Path to the consolidated event store.
        **overrides: Override specific profile choices.

    Returns:
        A fully configured ViewpointConfig.

    Raises:
        KeyError: If the profile name is not registered.
    """
    if name not in PROFILES:
        available = sorted(PROFILES.keys())
        err_msg = (
            f"Unknown viewpoint profile '{name}'. "
            f"Available: {available}"
        )
        logger.error(err_msg)
        raise KeyError(err_msg)

    merged = {**PROFILES[name], **overrides}
    return ViewpointConfig(
        consolidated_path=consolidated_path,
        **merged,
    )


def list_profiles() -> list[str]:
    """Return sorted list of registered profile names."""
    return sorted(PROFILES.keys())


# ---- Registered profiles ----

_register(
    "production_parity",
    survivorship_strategy="dot9_wins",
    distribution_strategy="ceil_split",
    spatial_distribution_strategy="passthrough",
    source_distribution_map={"annual": "date_end_only"},
    filter_stale_versions=True,
    min_priogrid_gid=1,
    max_type_of_violence=3,
    exclude_where_prec=(4, 6),
)


# ADR-049 decided that spatial distribution of geographically imprecise
# events is this data factory's recommended behaviour, and ViewpointConfig
# honours that: ``spatial_distribution_strategy`` defaults to
# ``"proportional"``. But the only profile registered until 2026-11-04 was
# ``production_parity``, which overrides it to ``"passthrough"`` to
# reproduce VIEWSER's GedLoader -- so the recommended behaviour had no name
# anyone could select, and no test asserted either choice. That is how the
# two stayed apart for four months without anything going red.
#
# This profile gives the recommendation a home. It changes exactly one
# concern against ``production_parity`` -- how events whose own
# ``where_prec`` disowns their cell are handled -- which takes two fields,
# because ADR-049 section 6 frames drop/passthrough/distribute as three
# options on one mechanism:
#
#   exclude_where_prec=()  : stop dropping where_prec 4 and 6, so there is
#                            something left for the strategy to distribute.
#                            Side effect: where_prec 7 (276 events) and the
#                            undocumented 99 (19 events) also flow in, both
#                            routed to the country polygon by
#                            ``_COUNTRY_LEVEL``.
#   spatial_distribution_strategy="proportional"
#                          : distribute across the target polygon weighted
#                            by well-located fatalities, conserving totals.
#
# The temporal axis is deliberately left identical to ``production_parity``.
# One variable at a time: the temporal question is its own experiment, and
# ``Denton (1971)`` has already ruled out the candidate we would have
# reached for.
#
# This is NOT what the production pipeline invokes.
# ``scripts/build_viewpoint.py`` still defaults to ``production_parity``,
# and switching that is a separate decision that moves every published
# fatality figure.
_register(
    "kgi_distributed",
    survivorship_strategy="dot9_wins",
    distribution_strategy="ceil_split",
    spatial_distribution_strategy="proportional",
    source_distribution_map={"annual": "date_end_only"},
    filter_stale_versions=True,
    min_priogrid_gid=1,
    max_type_of_violence=3,
    exclude_where_prec=(),
)



# Both axes distributed: the tool for consumers who need summary events
# placed rather than piled. One further step beyond ``kgi_distributed``,
# and the step is the temporal axis:
#
#   distribution_strategy="uniform_span"
#       Spread events UCDP declares temporally imprecise (date_prec >= 4)
#       across the months they span, conserving exactly. Replaces
#       ``ceil_split``, which assigns ceil(v/span) to every month and so
#       inflates -- 0.91% measured across the consolidated store.
#
#   source_distribution_map=None
#       This is the load-bearing change. ``production_parity`` and
#       ``kgi_distributed`` both route annual-source events to
#       ``date_end_only``, reproducing the legacy annual loader's
#       fix_summary_events=False. That override is why the Tigray war's
#       whole-year aggregate (event 463131, 113,368 fatalities,
#       date_prec 5, where_prec 5) lands entirely on December 2021.
#       Dropping it lets the temporal strategy see annual events.
#
# Measured effect on that event: 1 row becomes 12 months x 18 cells,
# conserving all of best, low and high exactly, with the cell-month peak
# falling by roughly two orders of magnitude.
#
# NOT what the pipeline invokes. ``scripts/refresh_pipeline.sh`` names
# ``production_parity`` explicitly and a test asserts it. Select this one
# deliberately:
#
#   uv run python scripts/build_viewpoint.py \
#       --profile kgi_kti_distributed \
#       --output data/viewpoint/kgi_kti_distributed.parquet
_register(
    "kgi_kti_distributed",
    survivorship_strategy="dot9_wins",
    distribution_strategy="uniform_span",
    spatial_distribution_strategy="proportional",
    source_distribution_map=None,
    filter_stale_versions=True,
    min_priogrid_gid=1,
    max_type_of_violence=3,
    exclude_where_prec=(),
)



# Both axes, with the temporal axis weighted by observed activity rather
# than spread flat. One field away from ``kgi_kti_distributed``, and the
# field was earned by measurement rather than argued for: on 20,000 events
# whose true month is known, with each event removed from its own
# indicator, activity weighting cut the mean distance from the true month
# from 4.883 months to 3.305 and raised the share of mass landing in the
# right month from 0.0825 to 0.1525, beating uniform on 64.9% of events
# against 22.9% worse. See scripts/evaluate_temporal_allocation.py --
# that script is also what would falsify the choice.
#
# Honest limit: the gain is in the MEAN, not the median. Median hit share
# is 0.00 for uniform and for activity alike, because most events are
# small enough to land wholly in one month and usually the wrong one. So
# this helps the typical fatality, not the typical event.
#
# The assumption most likely to be wrong: a month with no well-observed
# activity gets zero, because zero weight means zero allocation. That
# says "no observed fighting, so invent none", and absence of
# well-located reporting is not absence of fighting -- 1,760 KTI events
# have at least one zero-activity month inside their span.
#
# NOT what the pipeline invokes.
#
#   uv run python scripts/build_viewpoint.py \
#       --profile kgi_kti_activity \
#       --output data/viewpoint/kgi_kti_activity.parquet
_register(
    "kgi_kti_activity",
    survivorship_strategy="dot9_wins",
    distribution_strategy="activity_weighted",
    spatial_distribution_strategy="proportional",
    source_distribution_map=None,
    filter_stale_versions=True,
    min_priogrid_gid=1,
    max_type_of_violence=3,
    exclude_where_prec=(),
)


# ---- ACLED profiles ----

ACLED_PROFILES: dict[str, dict[str, Any]] = {}


def _register_acled(name: str, **kwargs: Any) -> None:
    """Register a named ACLED viewpoint profile."""
    kwargs["version"] = name
    ACLED_PROFILES[name] = kwargs
    logger.info("Registered ACLED viewpoint profile: %s", name)


def list_acled_profiles() -> list[str]:
    """Return sorted list of registered ACLED profile names."""
    return sorted(ACLED_PROFILES.keys())


def load_acled_profile(
    name: str,
    consolidated_path: Path,
    **overrides: Any,
) -> AcledViewpointConfig:
    """Load a named ACLED viewpoint profile.

    Returns an AcledViewpointConfig (imported lazily to avoid
    circular imports).
    """
    if name not in ACLED_PROFILES:
        available = sorted(ACLED_PROFILES.keys())
        err_msg = (
            f"Unknown ACLED profile '{name}'. "
            f"Available: {available}"
        )
        logger.error(err_msg)
        raise KeyError(err_msg)

    from datafactory_viewpoint.builders.acled_v1 import (
        AcledViewpointConfig,
    )

    merged = {**ACLED_PROFILES[name], **overrides}
    return AcledViewpointConfig(
        consolidated_path=consolidated_path,
        **merged,
    )


_register_acled(
    "acled_violence_only",
    event_type_filter=(
        "Battles",
        "Explosions/Remote violence",
        "Violence against civilians",
    ),
)

_register_acled(
    "acled_all_events",
)
