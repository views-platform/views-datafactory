"""
Failing test stubs from falsification audit: "you understand how to fix what happened"

Claim: The fix plan in #123-#126 is correct, complete, and sufficient to make
the status page publicly accessible.
Audit date: 2026-06-04
Verdict: FALSIFIED (2 hard, 3 soft falsifications)

These tests encode the findings. Each test SHOULD FAIL until the
underlying issue is fixed.
"""

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.falsification

# --- G1: Three-way path disagreement (hard falsification) ---

class TestG1PathDisagreement:
    """generate_status.py docstring says /srv/views-data/www/status.html,
    EXIT trap says data/status.html, #104 says /srv/views-data/status.html.
    The docstring's /www/ subdirectory exists in no other document."""

    def test_docstring_output_path_matches_deployment_guide(self):
        """The script's own usage example should match the actual
        deployment configuration, not a fabricated /www/ path."""
        script = Path("scripts/generate_status.py")
        content = script.read_text()
        assert "/srv/views-data/www/" not in content, (
            "generate_status.py docstring references /srv/views-data/www/ "
            "which exists in no deployment guide, ADR, or issue. "
            "Update to match the actual path: data/status.html (relative) "
            "or document the /www/ path if it's intentional."
        )

    def test_issue_125_resolves_path_disagreement(self):
        """#125 should specify a single canonical output path,
        not defer to 'investigation needed'."""
        result = subprocess.run(
            ["gh", "issue", "view", "125", "--json", "body", "-q", ".body"],
            capture_output=True, text=True,
        )
        body = result.stdout
        assert "Investigation needed" not in body, (
            "#125 defers the key decision (which output path to use) "
            "to investigation. The deployment guide already documents "
            "the server layout (symlinks). #125 should specify the fix."
        )


# --- G2: #125 is investigation, not a fix (soft falsification) ---

class TestG2FixSpecificity:
    """#125 presents conditional options without choosing. The deployment
    guide already documents the answer (per-file symlinks)."""

    def test_issue_125_specifies_concrete_fix(self):
        result = subprocess.run(
            ["gh", "issue", "view", "125", "--json", "body", "-q", ".body"],
            capture_output=True, text=True,
        )
        body = result.stdout
        has_conditional = "If `/srv/views-data` is a symlink" in body
        has_option_a = "Option A" in body
        has_option_b = "Option B" in body
        assert not (has_conditional and has_option_a and has_option_b), (
            "#125 presents Options A and B conditionally. The deployment "
            "guide (line 237-240) already documents the server layout: "
            "/srv/views-data/ is a directory with per-file symlinks. "
            "#125 should specify the fix based on this known state."
        )


# --- G3: Daily cron has no verification (soft falsification) ---

class TestG3DailyCronVerification:
    """#126 adds verification to verify_remote.py (monthly) and
    refresh_pipeline.sh (deployment). The daily 06:00 UTC cron
    runs generate_status.py standalone with no post-check."""

    def test_fix_plan_covers_daily_cron_verification(self):
        for issue_num in (123, 124, 125, 126):
            result = subprocess.run(
                ["gh", "issue", "view", str(issue_num),
                 "--json", "body", "-q", ".body"],
                capture_output=True, text=True,
            )
            body = result.stdout.lower()
            if ("daily" in body and ("verif" in body or "check" in body)
                    and ("cron" in body or "06:00" in body or "0 6" in body)):
                return
        pytest.fail(
            "No fix issue (#123-#126) specifies verification for the "
            "daily cron at 06:00 UTC. The daily cron runs "
            "generate_status.py standalone — if it fails, the status "
            "page goes stale silently."
        )


# --- G4: #104 paths don't match server layout (hard falsification) ---

class TestG4Issue104Paths:
    """#104 specifies --data-dir /srv/views-data and
    --provenance-dir /srv/views-data/provenance. On the server,
    /srv/views-data/ contains only per-file symlinks (no raw/,
    compiled/, provenance/ subdirectories). Following #104
    produces a page showing everything as missing."""

    def test_issue_104_data_dir_path_is_valid(self):
        """#104's --data-dir should point to a location where
        the data directory tree actually exists."""
        result = subprocess.run(
            ["gh", "issue", "view", "104", "--json", "body", "-q", ".body"],
            capture_output=True, text=True,
        )
        body = result.stdout
        assert "--data-dir /srv/views-data" not in body or (
            "--data-dir /srv/views-data/" not in body
            and "--data-dir /srv/views-data\n" not in body
        ), (
            "#104 uses --data-dir /srv/views-data but that directory "
            "only contains per-file symlinks (grid.zarr, dataframe.parquet, "
            "status.html). generate_status.py needs the full data tree "
            "(raw/, compiled/, assembled/). Use the repo's data/ directory."
        )

    def test_issue_104_provenance_dir_exists(self):
        """#104's --provenance-dir should point to a real directory."""
        result = subprocess.run(
            ["gh", "issue", "view", "104", "--json", "body", "-q", ".body"],
            capture_output=True, text=True,
        )
        body = result.stdout
        assert "/srv/views-data/provenance" not in body, (
            "#104 uses --provenance-dir /srv/views-data/provenance but "
            "that directory does not exist. No symlink creates it. "
            "The provenance/ directory is at the repo root "
            "(~/views-datafactory/provenance/). Following #104's "
            "commands produces a status page showing everything as missing."
        )


# --- G5: No end-to-end acceptance test (soft falsification) ---

class TestG5EndToEndAcceptance:
    """No issue defines a single test exercising the full chain:
    generate → file at repo path → symlink → Caddy → HTTP 200."""

    def test_fix_plan_has_e2e_acceptance_test(self):
        combined = ""
        for issue_num in (123, 124, 125, 126):
            result = subprocess.run(
                ["gh", "issue", "view", str(issue_num),
                 "--json", "body", "-q", ".body"],
                capture_output=True, text=True,
            )
            combined += result.stdout
        combined_lower = combined.lower()
        has_e2e = any(
            phrase in combined_lower
            for phrase in [
                "end-to-end",
                "end to end",
                "full chain",
                "integration test",
                "generate and verify",
            ]
        )
        assert has_e2e, (
            "No fix issue specifies an end-to-end test that validates "
            "the full chain: generate_status.py → file exists → symlink "
            "resolves → curl without auth returns 200. Individual checks "
            "exist (#126) but are not composed into one acceptance test."
        )
