"""
Failing test stubs from falsification audit: "you understand what happened"

Claim: The diagnosis of the status page deployment failure is complete and accurate.
Audit date: 2026-06-04
Verdict: FALSIFIED (1 hard, 3 soft falsifications)

These tests encode the findings. Each test SHOULD FAIL until the
underlying issue is fixed.
"""

import subprocess

import pytest

pytestmark = pytest.mark.falsification

# --- F1: Symlink as distinct step (soft falsification) ---

class TestF1SymlinkAsDistinctStep:
    """#125 treats the symlink as 'investigation needed' but the deployment
    guide already documents it as a specific required command."""

    def test_issue_125_identifies_symlink_as_required_step(self):
        """#125 should state the symlink command from the deployment guide
        as a concrete fix step, not an open investigation question."""
        result = subprocess.run(
            ["gh", "issue", "view", "125", "--json", "body", "-q", ".body"],
            capture_output=True, text=True,
        )
        body = result.stdout
        assert "ln -sf" in body or "ln -s" in body, (
            "#125 should include the symlink command as a required step, "
            "not defer it to investigation"
        )
        assert "Investigation needed" not in body, (
            "#125 frames a documented deployment step as an open question"
        )


# --- F2: #104 contradiction (soft falsification) ---

class TestF2Issue104Contradiction:
    """#104 says 'Caddy configuration changes (none needed)' which directly
    contradicts ADR-038 and #124."""

    def test_issue_104_does_not_claim_no_caddy_changes_needed(self):
        result = subprocess.run(
            ["gh", "issue", "view", "104", "--json", "body", "-q", ".body"],
            capture_output=True, text=True,
        )
        body = result.stdout
        assert "none needed" not in body.lower(), (
            "#104 claims no Caddy changes needed, contradicting ADR-038. "
            "Update or close #104 with a note pointing to #124."
        )

    def test_issue_104_references_adr_038(self):
        result = subprocess.run(
            ["gh", "issue", "view", "104", "--json", "body", "-q", ".body"],
            capture_output=True, text=True,
        )
        body = result.stdout
        assert "ADR-038" in body or "adr-038" in body.lower(), (
            "#104 should reference ADR-038 since it governs Caddy config "
            "for the status page"
        )


# --- F3: Communication failure not acknowledged (hard falsification) ---

class TestF3CommunicationFailureAcknowledged:
    """The tracking issue (#123) documents technical root causes but omits
    the communication failure: the user was told 'yes, it will be live'
    when three manual steps were still required."""

    def test_issue_123_acknowledges_communication_gap(self):
        result = subprocess.run(
            ["gh", "issue", "view", "123", "--json", "body", "-q", ".body"],
            capture_output=True, text=True,
        )
        body = result.stdout
        has_comms_language = any(
            phrase in body.lower()
            for phrase in [
                "manual steps",
                "post-pipeline",
                "not automatic",
                "communication",
                "miscommunication",
                "promised",
            ]
        )
        assert has_comms_language, (
            "#123 should acknowledge that the status page requires manual "
            "post-pipeline steps and that this was not made clear. The "
            "diagnosis covers technical failures but omits the communication "
            "breakdown that caused the user's experience."
        )


# --- F4: Daily cron orphaned (soft falsification) ---

class TestF4DailyCronCoverage:
    """The daily cron at 06:00 UTC is documented in ADR-038 and the
    deployment guide but is not covered by #123-#126. #104 covers it
    but has stale assumptions about Caddy."""

    def test_cron_covered_by_fix_issues(self):
        for issue_num in (123, 124, 125, 126):
            result = subprocess.run(
                ["gh", "issue", "view", str(issue_num),
                 "--json", "body", "-q", ".body"],
                capture_output=True, text=True,
            )
            if "cron" in result.stdout.lower() and "06:00" in result.stdout:
                return
        pytest.fail(
            "None of #123-#126 cover the daily cron at 06:00 UTC. "
            "The requirement is documented in ADR-038 and the deployment "
            "guide but fell through the gap between old (#104) and new issues."
        )

    def test_issue_104_caddy_claim_is_current(self):
        """#104 should not contain stale claims about Caddy that contradict
        ADR-038. If #104 is superseded, it should be closed."""
        result = subprocess.run(
            ["gh", "issue", "view", "104", "--json", "state", "-q", ".state"],
            capture_output=True, text=True,
        )
        state = result.stdout.strip()
        if state == "OPEN":
            body_result = subprocess.run(
                ["gh", "issue", "view", "104",
                 "--json", "body", "-q", ".body"],
                capture_output=True, text=True,
            )
            assert "none needed" not in body_result.stdout.lower(), (
                "#104 is OPEN with a false claim about Caddy. Either update "
                "the body or close the issue with a pointer to #123."
            )
