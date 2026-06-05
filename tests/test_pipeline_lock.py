"""Tests for pipeline concurrent execution guard.

Verifies that refresh_pipeline.sh uses flock to prevent two
simultaneous runs from clobbering shared state.
"""

from __future__ import annotations

import fcntl
import subprocess
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "refresh_pipeline.sh"


class TestPipelineLockStructural:
    """Verify flock is present and correctly placed in the script."""

    def test_refresh_pipeline_contains_flock(self) -> None:
        """Script must contain a flock call."""
        text = SCRIPT.read_text()
        assert "flock" in text

    def test_flock_before_first_step(self) -> None:
        """flock must appear before the first pipeline step."""
        lines = SCRIPT.read_text().splitlines()
        flock_line = None
        step_line = None
        for i, line in enumerate(lines, 1):
            if "flock" in line and flock_line is None:
                flock_line = i
            if "CURRENT_STEP=" in line and "init" not in line and step_line is None:
                step_line = i
        assert flock_line is not None, "flock not found in script"
        assert step_line is not None, "No pipeline step found"
        assert flock_line < step_line, (
            f"flock (line {flock_line}) must appear before "
            f"first step (line {step_line})"
        )


class TestPipelineLockFunctional:
    """Verify flock actually prevents concurrent execution."""

    def test_concurrent_flock_rejects_second(self) -> None:
        """A second flock attempt on the same lock exits non-zero."""
        with tempfile.NamedTemporaryFile(
            suffix=".lock"
        ) as lock_file:
            lock_path = lock_file.name

            script = (
                f'exec 200>"{lock_path}"\n'
                f'if ! flock -n 200; then\n'
                f'    echo "FATAL: already in progress"\n'
                f'    exit 1\n'
                f'fi\n'
                f'echo "acquired"\n'
            )

            with open(lock_path, "w") as fd:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                try:
                    result = subprocess.run(
                        ["bash", "-c", script],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    assert result.returncode == 1
                    assert "already in progress" in result.stdout
                finally:
                    fcntl.flock(fd, fcntl.LOCK_UN)

    def test_lock_released_after_exit(self) -> None:
        """Lock is released when the holder exits."""
        with tempfile.NamedTemporaryFile(
            suffix=".lock"
        ) as lock_file:
            lock_path = lock_file.name

            script = (
                f'exec 200>"{lock_path}"\n'
                f'flock -n 200 || exit 1\n'
                f'echo "acquired"\n'
            )

            r1 = subprocess.run(
                ["bash", "-c", script],
                capture_output=True,
                text=True,
                timeout=5,
            )
            assert r1.returncode == 0

            r2 = subprocess.run(
                ["bash", "-c", script],
                capture_output=True,
                text=True,
                timeout=5,
            )
            assert r2.returncode == 0
