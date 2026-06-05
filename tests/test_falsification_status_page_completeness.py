"""
Failing test stubs from falsification audit: "we now know what happened
and how to fix it"

Claim: After two rounds of falsification and risk registration, the
combined understanding is complete and sufficient.
Audit date: 2026-06-04
Verdict: FALSIFIED (2 hard, 3 soft falsifications)

These tests encode the findings. Each test SHOULD FAIL until the
underlying issue is fixed.
"""

import subprocess

import pytest

# --- H2: Round 1 hard falsification (F3) still unresolved ---

class TestH2PriorFalsificationResolved:
    """Round 1 found hard falsification: #123 doesn't acknowledge the
    communication failure. The user was told 'yes, it will be live'
    when 3 manual server steps were still required. This was the
    defining feature of the user's experience. It remains unaddressed."""

    def test_issue_123_acknowledges_manual_steps_required(self):
        result = subprocess.run(
            ["gh", "issue", "view", "123", "--json", "body", "-q", ".body"],
            capture_output=True, text=True,
        )
        body = result.stdout.lower()
        has_acknowledgment = any(
            phrase in body
            for phrase in [
                "manual steps",
                "not automatic",
                "post-pipeline",
                "server-side steps",
                "required after deployment",
            ]
        )
        assert has_acknowledgment, (
            "#123 still does not acknowledge that the status page requires "
            "manual post-pipeline server steps. This was a hard falsification "
            "in round 1 (F3) and remains unresolved. Update #123 to state "
            "that the page cannot go live without: (1) Caddyfile change, "
            "(2) symlink creation, (3) running generate_status.py."
        )


# --- H4: Fix issues not updated with audit findings ---

class TestH4AuditFindingsInIssues:
    """Two audits found 3 hard + 6 soft falsifications. Zero findings
    have been applied to the issues that someone would actually work from."""

    def test_docstring_www_path_tracked_in_issues(self):
        """G1 finding: docstring /www/ path. Should be in an issue."""
        combined = ""
        for i in (123, 124, 125, 126):
            result = subprocess.run(
                ["gh", "issue", "view", str(i),
                 "--json", "body", "-q", ".body"],
                capture_output=True, text=True,
            )
            combined += result.stdout
        assert "docstring" in combined.lower() or "/www/" in combined, (
            "G1 finding (docstring /www/ path in generate_status.py:9) is "
            "not tracked in any fix issue. It lives only in C-240 and "
            "the test stubs. Add it to #125 or create a new sub-issue."
        )

    def test_issue_104_broken_paths_addressed(self):
        """G4 finding: #104 paths don't match server layout."""
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
            body = body_result.stdout
            has_warning = any(
                phrase in body.lower()
                for phrase in [
                    "superseded",
                    "do not follow",
                    "paths are incorrect",
                    "see #123",
                    "stale",
                ]
            )
            assert has_warning, (
                "#104 is OPEN with broken --data-dir and --provenance-dir "
                "paths (C-239, Tier 2). Either close it or add a warning. "
                "Following its commands produces a status page showing "
                "everything as 'missing'."
            )

    def test_issue_125_no_longer_investigation(self):
        """G2 finding: #125 defers the key decision."""
        result = subprocess.run(
            ["gh", "issue", "view", "125", "--json", "body", "-q", ".body"],
            capture_output=True, text=True,
        )
        body = result.stdout
        assert "Investigation needed" not in body, (
            "#125 still says 'Investigation needed.' The deployment guide "
            "(line 237-240) documents the server layout. Rewrite #125 "
            "as a concrete fix specifying the symlink command."
        )

    def test_daily_cron_verification_in_issues(self):
        """G3 finding: daily cron has no verification."""
        combined = ""
        for i in (123, 124, 125, 126):
            result = subprocess.run(
                ["gh", "issue", "view", str(i),
                 "--json", "body", "-q", ".body"],
                capture_output=True, text=True,
            )
            combined += result.stdout.lower()
        has_daily_cron_verify = (
            ("daily" in combined or "06:00" in combined or "0 6" in combined)
            and ("verif" in combined or "check" in combined)
        )
        assert has_daily_cron_verify, (
            "No fix issue covers verification of the daily cron output. "
            "#126 adds checks for verify_remote.py (monthly) and "
            "refresh_pipeline.sh (deployment), but the daily 06:00 UTC "
            "cron runs standalone with no post-check."
        )


# --- H1, H3, H5: Soft falsifications ---

class TestSoftFalsifications:
    """These test the meta-level gaps: unverified server state,
    scattered knowledge, operational inaccessibility."""

    @pytest.mark.xfail(
        reason="Requires SSH to server — deferred to deployment phase",
        strict=False,
    )
    def test_server_state_verified(self):
        """H1: The diagnosis is hypothesis, not observation."""
        pytest.fail(
            "Six server-side facts remain unverified: (1) does "
            "data/status.html exist? (2) what is in the Caddyfile? "
            "(3) does the symlink exist? (4) is any cron set up? "
            "(5) did the EXIT trap run? (6) what are the permissions? "
            "SSH into the server and check before asserting the "
            "diagnosis is correct."
        )

    def test_fix_runbook_exists(self):
        """H3: 13 documents contain pieces of the fix. No single
        document describes the complete sequence."""
        result = subprocess.run(
            ["gh", "issue", "view", "123", "--json", "body", "-q", ".body"],
            capture_output=True, text=True,
        )
        body = result.stdout.lower()
        has_runbook = "runbook" in body or "complete fix" in body
        has_code_fixes = "code fix" in body or "docstring" in body
        has_server_steps = "caddyfile" in body and "symlink" in body
        has_verification = "verif" in body and "curl" in body
        all_sections = (
            has_code_fixes and has_server_steps and has_verification
        )
        assert has_runbook or all_sections, (
            "#123 should include a consolidated runbook with ALL steps: "
            "code fixes, server changes (Caddyfile, symlink, cron), "
            "and verification commands."
        )
