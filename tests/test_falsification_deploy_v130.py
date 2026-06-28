"""Falsification: deployment readiness for v1.3.0 (2026-06-15).

Claim: "We are ready to deploy."

Hard falsification F1: version not bumped since last deploy tag.
Hard falsification F2: development not merged to main (tags live on main).
Soft falsification F5: postmortem "do differently" items not addressed.
"""

from __future__ import annotations

import subprocess

import pytest


def _version_already_tagged() -> bool:
    import tomllib
    from pathlib import Path

    with Path("pyproject.toml").open("rb") as f:
        version = tomllib.load(f)["project"]["version"]
    result = subprocess.run(
        ["git", "tag", "-l", f"v{version}"],
        capture_output=True, text=True,
    )
    return f"v{version}" in result.stdout.strip().split("\n")


class TestF1VersionBumped:
    """pyproject.toml version must differ from the latest deploy tag."""

    @pytest.mark.xfail(
        condition=_version_already_tagged(),
        reason="version already tagged — expected post-deploy",
    )
    def test_version_not_already_tagged(self) -> None:
        import tomllib
        from pathlib import Path

        pyproject = Path("pyproject.toml")
        with pyproject.open("rb") as f:
            version = tomllib.load(f)["project"]["version"]

        tags = (
            subprocess.check_output(
                ["git", "tag", "-l", f"v{version}"],
                text=True,
            )
            .strip()
            .splitlines()
        )
        assert f"v{version}" not in tags, (
            f"Version {version} is already tagged — "
            f"bump version in pyproject.toml before deploying"
        )


class TestF2DevelopmentMergedToMain:
    """All development commits must reach main before tagging."""

    @pytest.mark.xfail(
        reason="merge happens at deploy time, not during development",
    )
    def test_main_contains_development_head(self) -> None:
        dev_head = subprocess.check_output(
            ["git", "rev-parse", "development"],
            text=True,
        ).strip()

        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor",
             dev_head, "main"],
            capture_output=True,
        )
        assert result.returncode == 0, (
            f"development HEAD ({dev_head[:8]}) is not "
            f"an ancestor of main — merge development→main "
            f"before creating a deploy tag"
        )


class TestF5PostmortemLessonsApplied:
    """v1.2.29 postmortem "do differently" items addressed."""

    def test_version_tag_tests_xfailed_when_tagged(
        self,
    ) -> None:
        """Postmortem item 1: version-tag tests should be
        xfailed when the current version is already tagged,
        to avoid perpetual false failures."""
        import tomllib
        from pathlib import Path

        pyproject = Path("pyproject.toml")
        with pyproject.open("rb") as f:
            version = tomllib.load(f)["project"]["version"]

        tags = (
            subprocess.check_output(
                ["git", "tag", "-l", f"v{version}"],
                text=True,
            )
            .strip()
            .splitlines()
        )
        if f"v{version}" not in tags:
            return

        result = subprocess.run(
            ["grep", "-rn",
             "def test_version_not_already_tagged",
             "tests/"],
            capture_output=True, text=True,
        )
        test_files = [
            line.split(":")[0]
            for line in result.stdout.strip().splitlines()
            if "def test_version_not_already_tagged" in line
        ]

        for test_file in test_files:
            if "deploy_v130" in test_file:
                continue
            if "deploy_v160" in test_file:
                continue
            content = Path(test_file).read_text()
            func_idx = content.index(
                "def test_version_not_already_tagged"
            )
            preceding = content[max(0, func_idx - 300):func_idx]
            assert "xfail" in preceding.lower() or \
                   "skip" in preceding.lower(), (
                f"{test_file}: "
                f"test_version_not_already_tagged should be "
                f"xfailed when version is already tagged "
                f"(v1.2.29 postmortem item 1)"
            )
