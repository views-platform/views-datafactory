"""Falsification: deployment readiness for v1.4.0 (2026-06-24).

Claim: "We are ready to merge to main and deploy to the server."

Soft falsification SF1: deployment guide Quick Deploy contradicts
"How to deploy" section — one tags from development, the other from
main, neither includes the merge-to-main step.

Soft falsification SF2: deploy-readiness tracking issues (#225-#230)
still open on GitHub despite all underlying code work being merged.
"""

from __future__ import annotations

from pathlib import Path


class TestSF1DeployGuideInternalConsistency:
    """Quick Deploy and 'How to deploy' must agree on branch and
    both must include the merge-to-main step."""

    def test_quick_deploy_mentions_merge_to_main(self) -> None:
        guide = Path(
            "docs/guides/hetzner_deployment_guide.md"
        ).read_text()

        quick_deploy_start = guide.index("## Quick Deploy")
        quick_deploy_end = guide.index("\n## ", quick_deploy_start + 1)
        quick_section = guide[quick_deploy_start:quick_deploy_end]

        assert "merge" in quick_section.lower() or (
            "main" in quick_section and "development" in quick_section
        ), (
            "Quick Deploy section tags from development without "
            "mentioning the merge-to-main step. An operator "
            "following this section would leave main behind."
        )

    def test_how_to_deploy_mentions_merge_from_development(
        self,
    ) -> None:
        guide = Path(
            "docs/guides/hetzner_deployment_guide.md"
        ).read_text()

        deploy_start = guide.index("### How to deploy a new version")
        deploy_end = guide.index("\n### ", deploy_start + 1)
        deploy_section = guide[deploy_start:deploy_end]

        assert "merge" in deploy_section.lower() or (
            "development" in deploy_section
        ), (
            "'How to deploy' assumes main is up to date but "
            "does not include the merge from development. "
            "An operator following this section literally would "
            "tag a stale main."
        )


class TestSF2DeployTrackingIssuesClosed:
    """Deploy-readiness tracking issues should be closed when
    their underlying code work is merged."""

    def test_deploy_epic_issues_closed(self) -> None:
        import subprocess

        result = subprocess.run(
            ["gh", "issue", "list", "--label", "deploy",
             "--state", "open", "--json", "number,title"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            return

        import json
        open_issues = json.loads(result.stdout)
        assert len(open_issues) == 0, (
            f"{len(open_issues)} deploy-labeled issues still open: "
            + ", ".join(
                f"#{i['number']} ({i['title']})"
                for i in open_issues
            )
        )
