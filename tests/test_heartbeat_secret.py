"""Guard: the heartbeat URL never reaches a command line.

``HEARTBEAT_URL`` is a **capability URL**. Whoever holds it can send a
success ping and mark the monthly pipeline healthy, or silence the
dead-man alert entirely. It is therefore a secret, not configuration —
and ``/proc/<pid>/cmdline`` is world-readable (``-r--r--r--``), while
four accounts hold shells on the production host.

C-331 is what this guards. The fix passes the URL to ``curl`` on stdin
as a config file (``-K -``) instead of as an argv element.

**Why a test and not just the fix.** Reintroducing the argv form breaks
nothing: every ping still lands, the check stays green, no error is
raised anywhere. The regression would be invisible by construction, and
C-343 means it could sit in production for up to two months before a
deploy even carried it. That is the *fails green* class this epic exists
to convert from a sentence into machinery.

**Drilled, not assumed.** The claim that stdin keeps the URL out of
``/proc`` was verified with a canary and a negative control before the
change shipped: the old argv form leaked
``curl -fsS --max-time 20 http://.../CANARY-.../fail`` into
``/proc/<pid>/cmdline``, and the new form showed ``curl -fsS
--max-time 20 -K -`` in flight with no process anywhere carrying the
canary. Without the control, a clean scan would only have proved the
scanner was broken.

**What these tests deliberately do NOT assert:** the ``printf`` text,
``-K -``, ``-fsS``, ``--max-time``, line numbers, or indentation. curl
8.3 added ``--variable``/``--expand-url``, which would be a legitimate
simplification of this mechanism; a guard that reddens on the *how*
rather than the *property* would block it for no reason. Line numbers
specifically are excluded per C-336 — C-331's own Location field cited
lines that had drifted by twenty.

Comment handling: whole-line comments are skipped, trailing comments are
not stripped. Naive splitting on ``#`` breaks on a ``#`` inside a string,
and the failure direction of *not* stripping is a false positive (a
comment mentioning both ``curl`` and ``HEARTBEAT_URL``), which is safe
and obvious to fix.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PIPELINE = REPO / "scripts" / "refresh_pipeline.sh"


def _code_lines() -> list[tuple[int, str]]:
    """Numbered lines that are not blank and not whole-line comments."""
    return [
        (n, line)
        for n, line in enumerate(PIPELINE.read_text().splitlines(), start=1)
        if line.strip() and not line.lstrip().startswith("#")
    ]


class TestHeartbeatUrlIsNotOnTheCommandLine:
    def test_heartbeat_url_is_never_a_curl_argument(self) -> None:
        """The property C-331 is about, stated as an assertion.

        The check is "``HEARTBEAT_URL`` appears **after** the ``curl``
        token", not "the line contains both". The first version of this
        test asserted the latter and failed against the *fixed* script,
        because ``printf … "$HEARTBEAT_URL" | curl …`` legitimately puts
        both on one line. Drilling the guard is what found that; a guard
        only ever run against the state it was written for proves
        nothing.
        """
        offenders = []
        for n, line in _code_lines():
            _head, sep, tail = line.partition("curl")
            if sep and "HEARTBEAT_URL" in tail:
                offenders.append((n, line.strip()))
        assert not offenders, (
            f"These lines put HEARTBEAT_URL on curl's command line: "
            f"{offenders}. Command lines are world-readable via "
            f"/proc/<pid>/cmdline, and the URL is a capability — holding "
            f"it is enough to forge a success ping and silence the "
            f"dead-man alert permanently (C-331). Pass it on stdin "
            f"instead: `printf 'url = \"%s\"\\n' \"$HEARTBEAT_URL\" | "
            f"curl -fsS --max-time 10 -K -`. Keep the quotes — unquoted, "
            f"curl truncates the value at the first whitespace and sends "
            f"the truncated URL anyway, which would turn a /fail ping "
            f"into a success ping."
        )

    def test_all_three_pings_still_exist(self) -> None:
        """Counterweight: deleting the pings must not satisfy the guard above.

        Mechanism-agnostic on purpose — this asserts the three signals
        exist, never how they are sent. Guards C-131 (success), C-317
        (start, resolved by drill 2026-08-10) and the failure ping
        together.
        """
        text = PIPELINE.read_text()
        # The bare form does not match `"${HEARTBEAT_URL:-}"` in the
        # guards, nor the suffixed forms, so each count is exact.
        expected = {
            '"$HEARTBEAT_URL/fail"': "failure ping (C-131)",
            '"$HEARTBEAT_URL/start"': "start ping (C-317, OOM/SIGKILL)",
            '"$HEARTBEAT_URL"': "success ping (C-131, the dead-man switch)",
        }
        wrong = {
            frag: (text.count(frag), why)
            for frag, why in expected.items()
            if text.count(frag) != 1
        }
        assert not wrong, (
            f"Expected exactly one of each heartbeat signal; found "
            f"{wrong} (count, purpose). Removing a ping would silence "
            f"monitoring while leaving every other check green — do not "
            f"delete one to satisfy "
            f"test_heartbeat_url_is_never_a_curl_argument."
        )
