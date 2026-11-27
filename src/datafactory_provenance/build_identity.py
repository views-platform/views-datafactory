"""Which build produced an artifact.

The served store records what it contains and when it was exported, but not
which release of this repository produced it. A consumer can therefore say
"I read the store on 25 November" and cannot say "I read v1.20.0" — so two
results cannot be shown to have read the same data (#620, #632, #648).

Martin's Reuse/Release Equivalence Principle is the argument: people "cannot,
and will not" reuse a component that is not given a release number. Under
ADR-054 the artifact consumers reuse is the store, not the wheel, so the
store is what needs the number.

Nothing here raises. A metadata nicety must never fail a seven-hour pipeline
run, so every failure degrades to a recorded reason.
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

# How the identity reached the artifact. "export" means it was written by the
# run that built the data, which is the only fully trustworthy case.
# "stamped" means it was applied to a store that already existed, so it
# asserts a link the pipeline did not itself observe. Consumers can tell them
# apart, which is the point of recording it.
IdentitySource = Literal["export", "stamped"]

_GIT_TIMEOUT_SECONDS = 10


def _git(repo_dir: Path, *args: str) -> str | None:
    """Run a git command, returning None rather than raising."""
    try:
        result = subprocess.run(  # noqa: S603
            ["git", "-C", str(repo_dir), *args],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _package_version() -> str | None:
    try:
        from importlib.metadata import PackageNotFoundError, version
    except ImportError:
        return None
    try:
        return version("views-datafactory")
    except PackageNotFoundError:
        return None


def resolve_build_identity(
    repo_dir: Path,
    source: IdentitySource,
) -> dict[str, object]:
    """Describe the build that is writing or stamping an artifact.

    Args:
        repo_dir: The checkout the pipeline is running from.
        source: "export" when called by the run that built the data,
            "stamped" when applied to a store that already existed.

    Returns:
        A dict safe to merge into zarr ``.zattrs``. Always contains
        ``build_identity_source`` and ``build_identity_resolved_at``;
        the rest are None when they cannot be determined, with the
        reason in ``build_identity_detail``.
    """
    identity: dict[str, object] = {
        "build_tag": None,
        "build_commit": None,
        "build_tree_dirty": None,
        "build_package_version": _package_version(),
        "build_identity_source": source,
        "build_identity_resolved_at": datetime.now(UTC).isoformat(),
        "build_identity_detail": None,
    }

    if not (repo_dir / ".git").exists():
        identity["build_identity_detail"] = (
            f"not a git checkout: {repo_dir}"
        )
        return identity

    identity["build_commit"] = _git(repo_dir, "rev-parse", "HEAD")

    # The exact tag, when HEAD is one. A deploy checks out a tag (ADR-022),
    # so in production this is the release. On a development branch there is
    # no exact tag and the field stays None rather than guessing at the
    # nearest one — a near tag would read as the release and would be wrong.
    identity["build_tag"] = _git(
        repo_dir, "describe", "--tags", "--exact-match",
    )

    status = _git(repo_dir, "status", "--porcelain")
    if status is not None:
        identity["build_tree_dirty"] = bool(status)

    if identity["build_commit"] is None:
        identity["build_identity_detail"] = "git did not answer"
    elif identity["build_tag"] is None:
        identity["build_identity_detail"] = (
            "HEAD is not exactly a tag; this is not a tagged release"
        )

    return identity
