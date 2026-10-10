"""Replay recorded ACLED responses: cursor and offset agreed (#487).

ACLED removed offset (`&page=N`) pagination on 2026-10-27. Before that
date, `scripts/verify_acled_pagination_parity.py` harvested one slice
both ways against the live API and they returned identical data. **That
comparison can never be made again** -- half of it no longer exists.

These fixtures are the recording, and this module is what keeps the
claim checkable after the deadline rather than leaving it as an
assertion in a commit message.

Two things make this stronger than the hand-built mocks in
`test_acled_harvester.py`: the envelopes are real ACLED responses with
all 31 event fields and all 9 envelope keys, and the cursor values are
the real opaque integers ACLED issued, in the real order. A mock built
from an assumption about the API cannot contradict that assumption;
a recording can.

Slice: Somalia, 2024-03-01 to 2024-03-07, limit=50. Recorded
2026-10-10. Deliberately narrow -- an ACLED event is ~1.4 KB, so the
broad 7,609-event measurement in `parity.json` would have been a 10 MB
file per walk. The narrow slice keeps every oracle checkable at 113 KB.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from datafactory_harvester.event_validation import validate_events
from datafactory_harvester.sources.acled import (
    DIGEST_FIELDS,
    FIELD_TYPES,
    REQUIRED_FIELDS,
    AcledConfig,
    fetch_paginated,
)

_FIXTURES = Path(__file__).parent / "fixtures" / "acled_cursor"
_CURSOR_WALK = _FIXTURES / "cursor_walk.json"
_OFFSET_WALK = _FIXTURES / "offset_walk.json"
_REPORT = (
    Path(__file__).resolve().parents[1]
    / "reports"
    / "investigation_acled_cursor"
    / "parity_fixture_slice.json"
)

# From the recorded run. Hard-coded so a careless regeneration of the
# fixtures fails here instead of silently redefining the baseline.
RECORDED_N_EVENTS = 84
RECORDED_DIGEST = "5b73a9160f8a8256"
RECORDED_PAGES = 2
RECORDED_LIMIT = 50


def _load(path: Path) -> list[dict]:
    return json.loads(path.read_text())


def _events_of(envelopes: list[dict]) -> list[dict]:
    return [e for env in envelopes for e in env["data"]]


def _digest(events: list[dict]) -> str:
    return validate_events(
        events,
        REQUIRED_FIELDS,
        FIELD_TYPES,
        digest_fields=DIGEST_FIELDS,
    ).content_digest


def _mock_responses(envelopes: list[dict]) -> list[MagicMock]:
    """Wrap recorded envelopes as the retry layer's responses."""
    out = []
    for env in envelopes:
        resp = MagicMock()
        resp.json.return_value = env
        resp.raise_for_status = MagicMock()
        out.append(resp)
    return out


def _token_response() -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {
        "access_token": "tok",
        "expires_in": 86400,
    }
    resp.raise_for_status = MagicMock()
    return resp


class TestFixturesPresent:
    """The recording must exist. Its absence is not a skip."""

    def test_both_walks_recorded(self) -> None:
        """Both fixtures exist.

        Not skipif-guarded, deliberately. A missing fixture here means
        the only surviving evidence for the migration is gone, and
        quietly skipping would hide that.
        """
        assert _CURSOR_WALK.exists(), f"missing {_CURSOR_WALK}"
        assert _OFFSET_WALK.exists(), f"missing {_OFFSET_WALK}"


class TestRecordedEnvelopeShape:
    """The structural facts the implementation depends on."""

    def test_next_cursor_is_top_level_on_every_page(self) -> None:
        """Confirms H2 against the recording, not against the notice.

        ACLED's deprecation notice said next_cursor is a body field.
        This asserts it of real responses.
        """
        for i, env in enumerate(_load(_CURSOR_WALK)):
            assert "next_cursor" in env, f"page {i + 1} lacks it"

    def test_next_cursor_is_null_exactly_once_and_last(self) -> None:
        """Confirms H3: the terminator fires once, at the end."""
        cursors = [env["next_cursor"] for env in _load(_CURSOR_WALK)]
        assert cursors[-1] is None
        assert [c for c in cursors if c is None] == [None]

    def test_non_terminal_cursors_are_ints(self) -> None:
        """The cursor is an opaque int, so 0 would be falsy.

        This is why `fetch_paginated` terminates on `is None` and never
        on falsiness.
        """
        cursors = [env["next_cursor"] for env in _load(_CURSOR_WALK)]
        for c in cursors[:-1]:
            assert isinstance(c, int), f"{c!r} is {type(c).__name__}"

    def test_count_and_total_count_are_null(self) -> None:
        """C-153 still stands under cursor pagination.

        ACLED reports no server-side total, so next_cursor is the only
        completeness signal in the response. If this ever starts
        failing, ADR-027's tolerance rule becomes applicable to ACLED
        and C-153 can close -- see #488.
        """
        for env in _load(_CURSOR_WALK):
            assert env["count"] is None
            assert env["total_count"] is None

    def test_final_page_is_short_and_others_are_full(self) -> None:
        """The recorded walk has the shape that matters.

        A full non-terminal page with a live cursor, then a short
        terminal page with a null cursor. Both terminators are
        exercised: the one that was deleted would have agreed here,
        which is exactly why parity held on this slice.
        """
        envelopes = _load(_CURSOR_WALK)
        assert len(envelopes) == RECORDED_PAGES
        for env in envelopes[:-1]:
            assert len(env["data"]) == RECORDED_LIMIT
        assert 0 < len(envelopes[-1]["data"]) < RECORDED_LIMIT


class TestRecordedParity:
    """The claim itself: the two walks returned the same data."""

    def test_event_counts_match(self) -> None:
        offset = _events_of(_load(_OFFSET_WALK))
        cursor = _events_of(_load(_CURSOR_WALK))
        assert len(offset) == len(cursor) == RECORDED_N_EVENTS

    def test_event_id_sets_are_identical(self) -> None:
        offset = {e["event_id_cnty"] for e in _events_of(_load(_OFFSET_WALK))}
        cursor = {e["event_id_cnty"] for e in _events_of(_load(_CURSOR_WALK))}
        assert offset == cursor
        assert not offset.symmetric_difference(cursor)

    def test_every_record_is_field_for_field_equal(self) -> None:
        """Stronger than the digest, which covers only two fields."""

        def keyed(events: list[dict]) -> list[dict]:
            return sorted(events, key=lambda e: e["event_id_cnty"])

        assert keyed(_events_of(_load(_OFFSET_WALK))) == keyed(
            _events_of(_load(_CURSOR_WALK))
        )

    def test_content_digests_match_each_other_and_the_record(self) -> None:
        """The oracle the ingestion ledger actually uses.

        Order-insensitive (validate_events sorts before hashing), so a
        different page ordering between the walks cannot produce a
        false mismatch.
        """
        offset_digest = _digest(_events_of(_load(_OFFSET_WALK)))
        cursor_digest = _digest(_events_of(_load(_CURSOR_WALK)))
        assert offset_digest == cursor_digest
        assert cursor_digest == RECORDED_DIGEST


class TestProductionLoopAgainstRecordedResponses:
    """Drive the real `fetch_paginated` with real ACLED responses."""

    def _run(self, envelopes: list[dict]) -> tuple[list[dict], MagicMock]:
        config = AcledConfig(
            start_year=2024,
            end_year=2024,
            page_size=RECORDED_LIMIT,
            data_dir=Path("/nonexistent"),
            ledger_path=Path("/nonexistent/ledger.jsonl"),
        )
        with (
            patch(
                "datafactory_http.retry.requests.request",
                side_effect=[
                    _token_response(),
                    *_mock_responses(envelopes),
                ],
            ) as mock_req,
            patch("datafactory_harvester.sources.acled.time.sleep"),
        ):
            events = fetch_paginated(config, "user", "pass")
        return events, mock_req

    def test_walk_returns_every_recorded_event(self) -> None:
        """The production loop, fed the real recording, loses nothing."""
        events, _ = self._run(_load(_CURSOR_WALK))
        assert len(events) == RECORDED_N_EVENTS
        assert _digest(events) == RECORDED_DIGEST

    def test_walk_sends_the_cursors_acled_actually_issued(self) -> None:
        """Cursor threading, checked against the real values.

        Request 1 sends 0; request n+1 sends the next_cursor response n
        carried. Hand-built mocks can only check this against a value
        the test itself invented.
        """
        envelopes = _load(_CURSOR_WALK)
        _, mock_req = self._run(envelopes)

        sent = [
            call[1]["params"]["cursor"]
            for call in mock_req.call_args_list[1:]
        ]
        expected = [0] + [
            env["next_cursor"] for env in envelopes[:-1]
        ]
        assert sent == expected

    def test_walk_sends_no_page_parameter(self) -> None:
        """`page` must be absent, not merely ignored.

        ACLED silently lets cursor win when both are supplied, so a
        stale page number would be invisible in production.
        """
        _, mock_req = self._run(_load(_CURSOR_WALK))
        for call in mock_req.call_args_list[1:]:
            assert "page" not in call[1]["params"]

    def test_walk_stops_without_an_extra_request(self) -> None:
        """Terminates on the null cursor, not by exhausting the mock.

        If the loop asked for one more page the side_effect list would
        be exhausted and this would raise StopIteration -- so the
        request count is the assertion, not the event count.
        """
        _, mock_req = self._run(_load(_CURSOR_WALK))
        assert mock_req.call_count == RECORDED_PAGES + 1  # + token

    def test_truncating_the_recording_is_detected(self) -> None:
        """The replay can fail -- a detection drill for this module.

        Drop the final page from the recording and the walk must come
        up short. Without this, every assertion above would also pass
        against a loop that silently stopped early, because the mock
        hands back whatever comes next regardless of what was asked.
        """
        envelopes = _load(_CURSOR_WALK)
        truncated = envelopes[:-1]
        # The last remaining page still has a LIVE cursor, so the loop
        # asks for another page and runs the mock dry.
        assert truncated[-1]["next_cursor"] is not None
        with pytest.raises(StopIteration):
            self._run(truncated)
