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
    source_distribution_map={"annual": "date_end_only"},
    filter_stale_versions=True,
    min_priogrid_gid=1,
    max_type_of_violence=3,
    exclude_where_prec=(4, 6),
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
