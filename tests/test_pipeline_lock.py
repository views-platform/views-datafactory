"""Tests for pipeline concurrent execution guard.

Verifies that refresh_pipeline.sh uses flock to prevent two
simultaneous runs from clobbering shared state.
"""

from __future__ import annotations

import fcntl
import subprocess
import tempfile
from pathlib import Path

import pytest

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


# ---- Python-side writer lock (C-316) + kernel crash-safety ----


class TestHoldPipelineLock:
    """C-316: standalone writers honor the shared pipeline lock."""

    def test_refuses_when_held_by_live_process(
        self, tmp_path: Path,
    ) -> None:
        import subprocess
        import sys as _sys
        import time as _time

        from datafactory_provenance import (
            PipelineLockHeldError,
            pipeline_lock,
        )

        lock = tmp_path / "pipe.lock"
        holder = subprocess.Popen(
            [
                _sys.executable, "-c",
                "import fcntl, sys, time\n"
                f"f = open({str(lock)!r}, 'a+')\n"
                "fcntl.flock(f, fcntl.LOCK_EX)\n"
                "f.seek(0); f.truncate()\n"
                "import os; f.write(str(os.getpid())); f.flush()\n"
                "print('held', flush=True)\n"
                "time.sleep(30)\n",
            ],
            stdout=subprocess.PIPE,
            text=True,
        )
        try:
            assert holder.stdout is not None
            assert holder.stdout.readline().strip() == "held"
            with pytest.raises(
                PipelineLockHeldError, match="in progress",
            ), pipeline_lock(lock):
                pass
        finally:
            holder.kill()
            holder.wait()
            _time.sleep(0.1)

    def test_crashed_holder_releases_instantly(
        self, tmp_path: Path,
    ) -> None:
        """Kernel-level crash safety: SIGKILL the holder → the
        very next acquisition succeeds. No staleness heuristic,
        no waiting period."""
        import signal
        import subprocess
        import sys as _sys

        from datafactory_provenance import pipeline_lock

        lock = tmp_path / "pipe.lock"
        holder = subprocess.Popen(
            [
                _sys.executable, "-c",
                "import fcntl, time\n"
                f"f = open({str(lock)!r}, 'a+')\n"
                "fcntl.flock(f, fcntl.LOCK_EX)\n"
                "print('held', flush=True)\n"
                "time.sleep(30)\n",
            ],
            stdout=subprocess.PIPE,
            text=True,
        )
        assert holder.stdout is not None
        assert holder.stdout.readline().strip() == "held"
        holder.send_signal(signal.SIGKILL)
        holder.wait()

        # Lock FILE still exists (leftover) — flock is gone.
        assert lock.exists()
        with pipeline_lock(lock):
            pass  # acquired immediately despite leftover file

    def test_live_holder_never_stolen_despite_age(
        self, tmp_path: Path,
    ) -> None:
        """The C-267 fix: a live holder's lock is unstealable no
        matter how old the lock file looks (the old 300s age
        heuristic deleted live locks under load)."""
        import os as _os
        import subprocess
        import sys as _sys

        from datafactory_provenance import (
            PipelineLockHeldError,
            pipeline_lock,
        )

        lock = tmp_path / "pipe.lock"
        holder = subprocess.Popen(
            [
                _sys.executable, "-c",
                "import fcntl, time\n"
                f"f = open({str(lock)!r}, 'a+')\n"
                "fcntl.flock(f, fcntl.LOCK_EX)\n"
                "print('held', flush=True)\n"
                "time.sleep(30)\n",
            ],
            stdout=subprocess.PIPE,
            text=True,
        )
        try:
            assert holder.stdout is not None
            assert holder.stdout.readline().strip() == "held"
            # Backdate the lock file far past the old threshold.
            old = 1_000_000_000
            _os.utime(lock, (old, old))
            with pytest.raises(PipelineLockHeldError), \
                    pipeline_lock(lock):
                pass
        finally:
            holder.kill()
            holder.wait()

    def test_force_bypasses(self, tmp_path: Path) -> None:
        from datafactory_provenance import pipeline_lock

        lock = tmp_path / "pipe.lock"
        # force=True never touches the lock file at all
        with pipeline_lock(lock, force=True):
            assert not lock.exists()

    def test_parent_held_env_bypasses(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Child scripts of refresh_pipeline.sh must not contend
        with their own parent's flock."""
        from datafactory_provenance import (
            hold_pipeline_lock,
            pipeline_lock,
        )

        monkeypatch.setenv("VIEWS_PIPELINE_LOCK_HELD", "1")
        lock = tmp_path / "pipe.lock"
        with pipeline_lock(lock):
            assert not lock.exists()
        hold_pipeline_lock(lock)
        assert not lock.exists()

    def test_lock_file_records_holder_pid(
        self, tmp_path: Path,
    ) -> None:
        import os as _os

        from datafactory_provenance import pipeline_lock

        lock = tmp_path / "pipe.lock"
        with pipeline_lock(lock):
            assert lock.read_text().strip() == str(_os.getpid())


class TestFileLockKernelCrashSafety:
    """file_lock's stale-deletion heuristic is gone (C-267):
    crash safety is kernel-level."""

    def test_leftover_lock_file_from_dead_holder_is_harmless(
        self, tmp_path: Path,
    ) -> None:
        import os as _os

        from datafactory_provenance.digests_and_ledgers import (
            file_lock,
        )

        target = tmp_path / "data.parquet"
        target.touch()
        stale = tmp_path / "data.parquet.lock"
        stale.write_text("99999999")
        old = 1_000_000_000
        _os.utime(stale, (old, old))

        # Acquires instantly — no holder, age irrelevant.
        with file_lock(target, timeout=2.0):
            pass

    def test_live_holder_blocks_until_timeout_despite_age(
        self, tmp_path: Path,
    ) -> None:
        import os as _os
        import subprocess
        import sys as _sys

        from datafactory_provenance.digests_and_ledgers import (
            file_lock,
        )

        target = tmp_path / "data.parquet"
        target.touch()
        lock = tmp_path / "data.parquet.lock"
        holder = subprocess.Popen(
            [
                _sys.executable, "-c",
                "import fcntl, time\n"
                f"f = open({str(lock)!r}, 'a+')\n"
                "fcntl.flock(f, fcntl.LOCK_EX)\n"
                "print('held', flush=True)\n"
                "time.sleep(30)\n",
            ],
            stdout=subprocess.PIPE,
            text=True,
        )
        try:
            assert holder.stdout is not None
            assert holder.stdout.readline().strip() == "held"
            old = 1_000_000_000
            _os.utime(lock, (old, old))
            with pytest.raises(TimeoutError), \
                    file_lock(target, timeout=1.0):
                pass
        finally:
            holder.kill()
            holder.wait()

    def test_hold_is_idempotent_within_process(
        self, tmp_path: Path,
    ) -> None:
        """A script's main() invoked twice in one interpreter
        (e.g. in-process tests) must not deadlock against its own
        held lock."""
        from datafactory_provenance import hold_pipeline_lock

        lock = tmp_path / "pipe.lock"
        hold_pipeline_lock(lock)
        hold_pipeline_lock(lock)  # no-op, not PipelineLockHeldError
