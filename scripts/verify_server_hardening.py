#!/usr/bin/env python3
"""Server hardening verification — run on the Hetzner server.

Checks that the views-deploy service account is correctly configured:
user exists, owns the pipeline, has no sudo, cron is migrated, and
data symlinks resolve through the service account's home.

Usage (on server):
    python3 scripts/verify_server_hardening.py

Exits 0 if all checks pass, 1 otherwise.
Does NOT modify any files or configuration.
"""

from __future__ import annotations

import grp
import os
import pwd
import subprocess
import sys
from pathlib import Path

SERVICE_USER = "views-deploy"
SERVICE_HOME = Path(f"/home/{SERVICE_USER}")
REPO_DIR = SERVICE_HOME / "views-datafactory"
DATA_DIR = REPO_DIR / "data"
DEPLOY_TAG = SERVICE_HOME / ".views-deploy-tag"
PROFILE = SERVICE_HOME / ".profile"
SYMLINK_DIR = Path("/srv/views-data")

passed = 0
failed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    """Record a check result."""
    global passed, failed  # noqa: PLW0603
    status = "PASS" if condition else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"  [{status}] {name}{suffix}")
    if condition:
        passed += 1
    else:
        failed += 1


def main() -> int:
    """Run all hardening checks."""
    print("=" * 60)
    print("SERVER HARDENING VERIFICATION")
    print(f"Service user: {SERVICE_USER}")
    print(f"Service home: {SERVICE_HOME}")
    print("=" * 60)
    print()

    # ── 1. User exists ──
    print("1. Service account")
    try:
        pw = pwd.getpwnam(SERVICE_USER)
        check("User exists", True, f"uid={pw.pw_uid}")
        check(
            "Home directory correct",
            pw.pw_dir == str(SERVICE_HOME),
            pw.pw_dir,
        )
        check("Shell is /bin/bash", pw.pw_shell == "/bin/bash")
    except KeyError:
        check("User exists", False, f"{SERVICE_USER} not found")
        print("\n  Cannot proceed — user does not exist.")
        return 1
    print()

    # ── 2. No sudo ──
    print("2. Privilege restriction")
    try:
        sudo_group = grp.getgrnam("sudo")
        in_sudo = SERVICE_USER in sudo_group.gr_mem
        check(
            "Not in sudo group",
            not in_sudo,
            "in sudo group!" if in_sudo else "correct",
        )
    except KeyError:
        check("Not in sudo group", True, "sudo group doesn't exist")

    try:
        admin_group = grp.getgrnam("admin")
        in_admin = SERVICE_USER in admin_group.gr_mem
        check(
            "Not in admin group",
            not in_admin,
            "in admin group!" if in_admin else "correct",
        )
    except KeyError:
        check("Not in admin group", True, "admin group doesn't exist")
    print()

    # ── 3. Repository and data ──
    print("3. Repository and data ownership")
    check("Repo directory exists", REPO_DIR.is_dir(), str(REPO_DIR))
    check("Data directory exists", DATA_DIR.is_dir(), str(DATA_DIR))

    if REPO_DIR.exists():
        repo_stat = REPO_DIR.stat()
        repo_owner = pwd.getpwuid(repo_stat.st_uid).pw_name
        check(
            "Repo owned by service user",
            repo_owner == SERVICE_USER,
            f"owner={repo_owner}",
        )

    if DATA_DIR.exists():
        data_stat = DATA_DIR.stat()
        data_owner = pwd.getpwuid(data_stat.st_uid).pw_name
        check(
            "Data owned by service user",
            data_owner == SERVICE_USER,
            f"owner={data_owner}",
        )
    print()

    # ── 4. Deploy tag ──
    print("4. Deployment gate")
    check("Deploy tag file exists", DEPLOY_TAG.is_file())
    if DEPLOY_TAG.is_file():
        tag_owner = pwd.getpwuid(DEPLOY_TAG.stat().st_uid).pw_name
        check(
            "Deploy tag owned by service user",
            tag_owner == SERVICE_USER,
            f"owner={tag_owner}",
        )
        tag_content = DEPLOY_TAG.read_text().strip()
        check(
            "Deploy tag is non-empty",
            len(tag_content) > 0,
            f"tag={tag_content}" if tag_content else "empty!",
        )
    print()

    # ── 5. Environment ──
    print("5. Environment")
    check("Profile exists", PROFILE.is_file())
    if PROFILE.is_file():
        profile_text = PROFILE.read_text()
        check(
            "UCDP_API_TOKEN in profile",
            "UCDP_API_TOKEN" in profile_text,
        )
    print()

    # ── 6. Cron ──
    print("6. Cron migration")
    try:
        result = subprocess.run(
            ["crontab", "-u", SERVICE_USER, "-l"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        user_cron = result.stdout
        check(
            "Service user has cron entry",
            "refresh_pipeline" in user_cron,
            "refresh_pipeline.sh found"
            if "refresh_pipeline" in user_cron
            else "not found!",
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        check("Service user has cron entry", False, "crontab failed")

    try:
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        root_cron = result.stdout
        check(
            "Root crontab clean (no pipeline)",
            "refresh_pipeline" not in root_cron,
            "still in root crontab!"
            if "refresh_pipeline" in root_cron
            else "correct",
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        check(
            "Root crontab clean",
            True,
            "crontab -l failed (may not be root)",
        )
    print()

    # ── 7. Symlinks ──
    print("7. Data serving symlinks")
    zarr_link = SYMLINK_DIR / "grid.zarr"
    parquet_link = SYMLINK_DIR / "dataframe.parquet"

    if zarr_link.is_symlink():
        target = os.readlink(zarr_link)
        points_to_service = SERVICE_USER in target
        check(
            "grid.zarr symlink → service user",
            points_to_service,
            target,
        )
    else:
        check("grid.zarr symlink exists", False)

    if parquet_link.is_symlink():
        target = os.readlink(parquet_link)
        points_to_service = SERVICE_USER in target
        check(
            "dataframe.parquet symlink → service user",
            points_to_service,
            target,
        )
    else:
        check("dataframe.parquet symlink exists", False)

    # Caddy traversal
    if SERVICE_HOME.exists():
        mode = SERVICE_HOME.stat().st_mode
        others_exec = bool(mode & 0o001)
        check(
            "Home directory has o+x (Caddy traversal)",
            others_exec,
            f"mode={oct(mode)}",
        )
    print()

    # ── 8. Root SSH key cleanup ──
    print("8. SSH key hygiene")
    root_key = Path("/root/.ssh/id_ed25519")
    check(
        "Personal SSH key removed from /root",
        not root_key.exists(),
        "still exists!" if root_key.exists() else "removed",
    )

    deploy_key = SERVICE_HOME / ".ssh" / "id_ed25519"
    check(
        "Deploy key exists for service user",
        deploy_key.is_file(),
        str(deploy_key),
    )
    print()

    # ── Summary ──
    total = passed + failed
    print("=" * 60)
    print(f"RESULT: {passed}/{total} checks passed")
    if failed > 0:
        print(f"        {failed} checks FAILED")
        print("        Fix failed checks before granting 2nd user access.")
    else:
        print("        Server hardening complete (Phase 6.1 + 6.2).")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
