"""Pipeline-level writer lock — shared with refresh_pipeline.sh (C-316).

refresh_pipeline.sh holds an exclusive flock on
``/var/lock/views-pipeline.lock`` for the duration of a run
(C-285/C-147). Standalone writer scripts (assemble, export,
run_*_pipeline, consumer bridge) must honor the same lock so a
manual invocation cannot collide with the monthly cron — the
2026-07-21 incident: a manual export read a half-rewritten
grid.npy mid-cron-assembly and survived only because the digest
gate ABORTed (C-316).

Semantics are refuse-fast, not queue: a writer script started
while the pipeline runs should tell the operator to wait, not
silently block for hours. Crash safety is kernel-level (flock
dies with its holder — see file_lock's rationale); there is no
staleness heuristic to misfire.

Usage in a writer script::

    from datafactory_provenance import pipeline_lock

    with pipeline_lock(force=args.force_no_lock):
        ...  # write shared data directories

``force=True`` skips acquisition entirely — a deliberate operator
escape hatch (logged loudly) for recovery scenarios.
"""

from __future__ import annotations

import fcntl
import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

__all__ = [
    "PIPELINE_LOCK_PATH",
    "PipelineLockHeldError",
    "hold_pipeline_lock",
    "pipeline_lock",
]

logger = logging.getLogger(__name__)

# Must match LOCK_FILE in scripts/refresh_pipeline.sh — the whole
# point is that bash and Python contend on the SAME file.
PIPELINE_LOCK_PATH = Path("/var/lock/views-pipeline.lock")

# Set by refresh_pipeline.sh after IT acquires the flock: child
# scripts it invokes are cooperating parts of the same run and
# must not contend with their own parent.
_LOCK_HELD_ENV = "VIEWS_PIPELINE_LOCK_HELD"


def _parent_holds_lock() -> bool:
    return os.environ.get(_LOCK_HELD_ENV) == "1"


class PipelineLockHeldError(RuntimeError):
    """Raised when another pipeline process holds the writer lock."""


@contextmanager
def pipeline_lock(
    lock_path: Path = PIPELINE_LOCK_PATH,
    *,
    force: bool = False,
) -> Iterator[None]:
    """Hold the pipeline writer lock, or refuse immediately.

    Args:
        lock_path: Lock file shared with refresh_pipeline.sh.
        force: Skip locking entirely (operator escape hatch;
            logged as a warning).

    Raises:
        PipelineLockHeldError: If the lock is held by another
            process (typically the monthly cron pipeline).
    """
    if force:
        logger.warning(
            "Pipeline lock BYPASSED (--force-no-lock) — caller "
            "accepts collision risk with a running pipeline",
        )
        yield
        return

    if _parent_holds_lock():
        logger.debug(
            "Pipeline lock already held by parent run "
            "(%s=1) — proceeding as part of the run",
            _LOCK_HELD_ENV,
        )
        yield
        return

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+") as lock_file:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            holder = ""
            try:
                lock_file.seek(0)
                holder = lock_file.read(32).strip()
            except OSError:
                pass
            msg = (
                f"Pipeline lock {lock_path} is held"
                f"{f' (holder pid {holder})' if holder else ''} — "
                f"a pipeline run is in progress. Wait for it to "
                f"finish (watch the status page), or re-run with "
                f"--force-no-lock if you accept the collision "
                f"risk (see C-316)."
            )
            raise PipelineLockHeldError(msg) from None
        try:
            lock_file.seek(0)
            lock_file.truncate()
            lock_file.write(str(os.getpid()))
            lock_file.flush()
            yield
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


# Held-for-process-lifetime locks, keyed by resolved path (keeps
# fds referenced AND makes hold_pipeline_lock idempotent within a
# process — re-acquiring a lock you already hold is a no-op, e.g.
# a script's main() invoked twice in one interpreter).
_held_locks: dict[str, object] = {}


def hold_pipeline_lock(
    lock_path: Path = PIPELINE_LOCK_PATH,
    *,
    force: bool = False,
) -> None:
    """Acquire the pipeline writer lock for the process lifetime.

    The one-liner for writer scripts' main(): acquire-or-refuse,
    then hold until the process exits (the kernel releases the
    flock when the fd closes at exit — no cleanup needed, and a
    crash releases it just the same).

    Raises:
        PipelineLockHeldError: If another process holds the lock.
    """
    if force:
        logger.warning(
            "Pipeline lock BYPASSED (--force-no-lock) — caller "
            "accepts collision risk with a running pipeline",
        )
        return

    if _parent_holds_lock():
        logger.debug(
            "Pipeline lock already held by parent run "
            "(%s=1) — proceeding as part of the run",
            _LOCK_HELD_ENV,
        )
        return

    key = str(lock_path.resolve())
    if key in _held_locks:
        logger.debug(
            "Pipeline lock %s already held by this process — "
            "no-op",
            lock_path,
        )
        return

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = open(lock_path, "a+")  # noqa: SIM115 — held for process lifetime
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        holder = ""
        try:
            lock_file.seek(0)
            holder = lock_file.read(32).strip()
        except OSError:
            pass
        lock_file.close()
        msg = (
            f"Pipeline lock {lock_path} is held"
            f"{f' (holder pid {holder})' if holder else ''} — "
            f"a pipeline run is in progress. Wait for it to "
            f"finish (watch the status page), or re-run with "
            f"--force-no-lock if you accept the collision risk "
            f"(see C-316)."
        )
        raise PipelineLockHeldError(msg) from None
    lock_file.seek(0)
    lock_file.truncate()
    lock_file.write(str(os.getpid()))
    lock_file.flush()
    _held_locks[key] = lock_file
