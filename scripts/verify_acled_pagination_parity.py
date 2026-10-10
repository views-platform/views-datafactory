#!/usr/bin/env python3
"""Do ACLED's cursor and offset pagination return the same events?

ACLED removed offset (`&page=N`) pagination on 2026-10-27 (#487). This
script is the evidence that the replacement walk returns the same data,
and it can only be run **before that date** — after it, one half of the
comparison no longer exists and no one can ever take this measurement
again.

Pre-registered as H1, H3, H4 and H6 in
`reports/investigation_acled_cursor/pre_analysis_plan.md`.

Both walks live here as sibling functions, and the offset walk is a
deliberate local copy of the loop that production used to run rather
than an import. That is the same construction as
`verify_area_majority_projection.py` and for the same reason: this
script's whole job is to compare against what production did, so
importing it would mean a later change there silently moves the baseline
this measurement was taken against. The copy is frozen; production is
not.

Why the content digest is the oracle: `validate_events` sorts before
hashing, so a different page ordering between the two walks cannot
produce a false mismatch, and it is the exact value the ingestion ledger
records and `_year_is_cached` compares against. It covers only
event_id_cnty and fatalities, so full-record equality is asserted
alongside it.

The slice is deliberately small. A full re-fetch is ~480 pages and owes
ACLED an advance note (`docs/guides/hetzner_deployment_guide.md`); a
normal monthly run is ~80. This is a one-month window at limit=500, so a
handful of pages each way — enough to exercise multi-page termination,
which a max_pages-capped walk would not.

Reads only, from ACLED. Writes one JSON of results and the raw response
envelopes. Never touches the delivered parquets or the provenance
ledger.

Usage:
    uv run python scripts/verify_acled_pagination_parity.py --self-test
    uv run python scripts/verify_acled_pagination_parity.py
    uv run python scripts/verify_acled_pagination_parity.py \
        --event-date 2024-03-01\\|2024-03-31 --limit 500
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from datafactory_harvester.event_validation import (  # noqa: E402
    validate_events,
)
from datafactory_harvester.sources.acled import (  # noqa: E402
    ACLED_API_BASE,
    ACLED_TOKEN_URL,
    DIGEST_FIELDS,
    FIELD_TYPES,
    REQUIRED_FIELDS,
    _acquire_token,
    get_acled_credentials,
)
from datafactory_http.retry import request_with_retry  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger(__name__)

# One week at limit=1000 gives a multi-page walk of a handful of pages
# each way -- enough to exercise termination, which a single-page or
# max_pages-capped walk would not, while staying an order of magnitude
# below a normal monthly run (~80 pages). A full month at limit=500
# would have been 30-40 pages EACH WAY, which is a re-fetch's worth of
# load for no extra evidence.
DEFAULT_EVENT_DATE = "2024-03-01|2024-03-07"
DEFAULT_LIMIT = 1000
DEFAULT_OUT = Path("reports/investigation_acled_cursor/parity.json")
DEFAULT_FIXTURE_DIR = Path("tests/fixtures/acled_cursor")

ID_FIELD = "event_id_cnty"

# A walk that needs more requests than this against a one-month window
# is not walking -- it is looping. Bounds the live run so a termination
# bug costs a few requests rather than a rate-limit ban.
MAX_REQUESTS = 40


# ---- The two walks -------------------------------------------------


def _walk_offset(
    fetch: Any, params: dict, limit: int
) -> tuple[list[dict], list[dict]]:
    """Walk by `&page=N`, terminating on an empty or short page.

    FROZEN COPY of the loop production ran before #487, down to the
    termination order. Do not "fix" this to match the new
    implementation -- the point is that it does not.
    """
    events: list[dict] = []
    envelopes: list[dict] = []
    page = 1

    while page <= MAX_REQUESTS:
        data = fetch({**params, "limit": limit, "page": page})
        envelopes.append(data)

        results = data.get("data", [])
        if not results:
            break

        events.extend(results)

        if len(results) < limit:
            break

        page += 1

    return events, envelopes


def _walk_cursor(
    fetch: Any, params: dict, limit: int
) -> tuple[list[dict], list[dict]]:
    """Walk by `&cursor=X`, terminating only on `next_cursor is None`.

    Mirrors the production implementation in `fetch_paginated()`.
    """
    events: list[dict] = []
    envelopes: list[dict] = []
    cursor: int | str = 0
    requests_made = 0

    while requests_made < MAX_REQUESTS:
        data = fetch({**params, "limit": limit, "cursor": cursor})
        envelopes.append(data)
        requests_made += 1

        results = data.get("data", [])

        if "next_cursor" not in data:
            msg = (
                "response missing 'next_cursor'; keys: "
                f"{sorted(data.keys())}"
            )
            raise ValueError(msg)

        next_cursor = data["next_cursor"]

        if not results and next_cursor is not None:
            msg = (
                f"empty page with live cursor {cursor!r} after "
                f"{len(events)} events"
            )
            raise ValueError(msg)

        events.extend(results)

        if next_cursor is None:
            break

        cursor = next_cursor

    return events, envelopes


# ---- Comparison ----------------------------------------------------


def _digest(events: list[dict]) -> str:
    """Content digest, as the ingestion ledger computes it."""
    return validate_events(
        events,
        REQUIRED_FIELDS,
        FIELD_TYPES,
        digest_fields=DIGEST_FIELDS,
    ).content_digest


def _sorted_records(events: list[dict]) -> list[dict]:
    return sorted(events, key=lambda e: str(e.get(ID_FIELD, "")))


def _compare(
    offset_events: list[dict], cursor_events: list[dict]
) -> dict:
    """Four independent oracles. Parity requires all four to agree."""
    offset_ids = {e.get(ID_FIELD) for e in offset_events}
    cursor_ids = {e.get(ID_FIELD) for e in cursor_events}

    only_offset = sorted(str(i) for i in offset_ids - cursor_ids)
    only_cursor = sorted(str(i) for i in cursor_ids - offset_ids)

    offset_digest = _digest(offset_events)
    cursor_digest = _digest(cursor_events)

    records_equal = _sorted_records(offset_events) == _sorted_records(
        cursor_events
    )

    checks = {
        "count_equal": len(offset_events) == len(cursor_events),
        "id_sets_equal": not only_offset and not only_cursor,
        "records_equal": records_equal,
        "digests_equal": offset_digest == cursor_digest,
    }

    return {
        "offset_n_events": len(offset_events),
        "cursor_n_events": len(cursor_events),
        "offset_content_digest": offset_digest,
        "cursor_content_digest": cursor_digest,
        "only_in_offset": only_offset[:20],
        "only_in_cursor": only_cursor[:20],
        "checks": checks,
        "parity": all(checks.values()),
    }


# ---- Detection drill -----------------------------------------------


def _fake_fetch(pages: list[dict]) -> Any:
    """Serve canned envelopes in order, ignoring the params."""
    state = {"i": 0}

    def fetch(_params: dict) -> dict:
        i = state["i"]
        state["i"] += 1
        return pages[i] if i < len(pages) else {
            "data": [],
            "next_cursor": None,
        }

    return fetch


def _ev(n: int, start: int = 0) -> list[dict]:
    return [
        {
            ID_FIELD: f"TST{i:04d}",
            "event_date": "2024-03-01",
            "event_type": "Battles",
            "sub_event_type": "Armed clash",
            "actor1": "A",
            "country": "Testland",
            "admin1": "T",
            "latitude": 1.0,
            "longitude": 2.0,
            "fatalities": i,
            "notes": "x",
        }
        for i in range(start, start + n)
    ]


def _self_test() -> int:
    """Prove the comparison can see a difference before it reports none.

    Without this, "the digests match" is indistinguishable from a script
    that hashes the same list twice. The repository's existing ACLED
    tests cannot substitute: their mocks return responses from an
    ordered list without inspecting the request, so they cannot tell a
    correct walk from one handed the right answer by accident.

    Three drills: identical input must report parity; a dropped event
    must be caught by every oracle; a single changed FIELD on an event
    that both walks return must be caught by records_equal even where
    the id sets and the counts agree.
    """
    failures: list[str] = []

    # Drill 1 -- identical walks must report parity.
    same = _ev(4)
    result = _compare(same, list(same))
    if not result["parity"]:
        failures.append(
            f"identical input reported a mismatch: {result['checks']}"
        )

    # Drill 2 -- one event dropped must be caught.
    truncated = _ev(4)[:-1]
    result = _compare(_ev(4), truncated)
    if result["parity"]:
        failures.append("a dropped event was reported as parity")
    for oracle in (
        "count_equal",
        "id_sets_equal",
        "records_equal",
        "digests_equal",
    ):
        if result["checks"][oracle]:
            failures.append(
                f"a dropped event did not trip {oracle}"
            )

    # Drill 3 -- same ids, same count, one field changed.
    mutated = _ev(4)
    mutated[2] = {**mutated[2], "latitude": 99.0}
    result = _compare(_ev(4), mutated)
    if result["parity"]:
        failures.append("a changed field was reported as parity")
    if not result["checks"]["records_equal"]:
        pass
    else:
        failures.append(
            "a changed field did not trip records_equal -- the digest "
            "covers only event_id_cnty and fatalities, so records_equal "
            "is the only oracle that can see this"
        )

    # Drill 4 -- the walks themselves. The offset walk must truncate on
    # a short page with a live cursor; the cursor walk must not. If
    # these ever agree, the live comparison is measuring nothing.
    pages = [
        {"data": _ev(2, 0), "next_cursor": 1},
        {"data": _ev(2, 2), "next_cursor": None},
    ]
    off, _ = _walk_offset(_fake_fetch(pages), {}, limit=5000)
    cur, _ = _walk_cursor(_fake_fetch(pages), {}, limit=5000)
    if len(off) != 2:
        failures.append(
            f"frozen offset walk returned {len(off)} events, expected "
            "2 -- it should stop on the short first page"
        )
    if len(cur) != 4:
        failures.append(
            f"cursor walk returned {len(cur)} events, expected 4"
        )
    if len(off) == len(cur):
        failures.append(
            "both walks returned the same count on input designed to "
            "separate them -- the two walks are not actually different"
        )

    if failures:
        log.error("DETECTION DRILL FAILED -- %d problem(s):", len(failures))
        for f in failures:
            log.error("  - %s", f)
        log.error(
            "Per the pre-analysis plan section 4, a parity result from "
            "this script must now be DISCARDED."
        )
        return 1

    log.info("detection drill passed (4 drills) -- the comparison can "
             "see a difference, so a null result means something")
    return 0


# ---- Live run ------------------------------------------------------


def _live_fetch(token: str) -> Any:
    def fetch(params: dict) -> dict:
        resp = request_with_retry(
            ACLED_API_BASE,
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "VIEWS-DataFactory/1.0 (parity-check)",
            },
            params=params,
            max_retries=3,
            timeout=60,
        )
        data = resp.json()
        if not isinstance(data, dict):
            msg = f"ACLED body is {type(data).__name__}, not a dict"
            raise TypeError(msg)
        return data

    return fetch


def _git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, OSError):
        return "unknown"


def _strip(envelopes: list[dict]) -> list[dict]:
    """Envelopes with event payloads replaced by their length."""
    return [
        {
            k: (f"<{len(v)} events>" if k == "data" else v)
            for k, v in env.items()
        }
        for env in envelopes
    ]


def main() -> int:
    """Run the detection drill, then the live comparison."""
    parser = argparse.ArgumentParser(
        description="ACLED cursor-vs-offset pagination parity"
    )
    parser.add_argument("--event-date", default=DEFAULT_EVENT_DATE)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--fixture-dir", type=Path, default=DEFAULT_FIXTURE_DIR
    )
    parser.add_argument(
        "--country",
        default=None,
        help="narrow to one country (used for the committed fixture)",
    )
    parser.add_argument(
        "--write-fixtures",
        action="store_true",
        help=(
            "record the raw envelopes for the CI replay test. Off by "
            "default: an ACLED event is ~1.4 KB, so the broad slice "
            "produces a 10 MB file per walk, which is evidence but a "
            "bad fixture. Use a narrowed slice with this flag."
        ),
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run the detection drill only, make no requests",
    )
    args = parser.parse_args()

    if args.self_test:
        return _self_test()

    # Precondition, not an option. A null result from an instrument
    # that cannot detect the effect is not evidence.
    if _self_test() != 0:
        return 1

    user, pwd = get_acled_credentials()
    state = _acquire_token(user, pwd, ACLED_TOKEN_URL, 60, 3)
    fetch = _live_fetch(state.access_token)

    params = {
        "_format": "json",
        "event_date": args.event_date,
        "event_date_where": "BETWEEN",
    }
    if args.country:
        params["country"] = args.country

    log.info(
        "slice: %s at limit=%d%s",
        args.event_date,
        args.limit,
        f", country={args.country}" if args.country else "",
    )

    log.info("walking by offset (the method ACLED removes 2026-10-27)")
    offset_events, offset_envelopes = _walk_offset(
        fetch, params, args.limit
    )
    log.info(
        "  %d events in %d request(s)",
        len(offset_events),
        len(offset_envelopes),
    )

    log.info("walking by cursor")
    cursor_events, cursor_envelopes = _walk_cursor(
        fetch, params, args.limit
    )
    log.info(
        "  %d events in %d request(s)",
        len(cursor_events),
        len(cursor_envelopes),
    )

    result = _compare(offset_events, cursor_events)

    # H4: did any page come back short while the cursor was still live?
    short_live = [
        {
            "request": i + 1,
            "n_events": len(env.get("data", [])),
            "next_cursor": env.get("next_cursor"),
        }
        for i, env in enumerate(cursor_envelopes)
        if env.get("next_cursor") is not None
        and len(env.get("data", [])) < args.limit
    ]

    report = {
        "question": (
            "Do ACLED's cursor and offset pagination return the same "
            "events?"
        ),
        "pre_analysis_plan": (
            "reports/investigation_acled_cursor/pre_analysis_plan.md"
        ),
        "method": (
            "Harvest one slice twice against live ACLED -- once by "
            "&page=N terminating on a short or empty page (frozen copy "
            "of the pre-#487 production loop), once by &cursor=X "
            "terminating only on next_cursor is None. Compare on four "
            "independent oracles: event count, event_id_cnty set, "
            "full-record equality over the sorted lists, and the "
            "content_digest the ingestion ledger records. A detection "
            "drill runs first as a precondition."
        ),
        "measured_at_utc": datetime.now(UTC).isoformat(),
        "git_sha": _git_sha(),
        "slice": {
            "event_date": args.event_date,
            "limit": args.limit,
            "country": args.country or "all",
            "event_types": "all (no event_type filter)",
        },
        "offset_requests": len(offset_envelopes),
        "cursor_requests": len(cursor_envelopes),
        "h4_short_pages_with_live_cursor": short_live,
        "h5_count_total_count": {
            "count": cursor_envelopes[0].get("count"),
            "total_count": cursor_envelopes[0].get("total_count"),
        },
        **result,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, default=str) + "\n")
    log.info("wrote %s", args.out)

    # The fixtures are the irreversible part: after 2026-10-27 the
    # offset envelopes cannot be recorded by anyone, ever.
    if args.write_fixtures:
        args.fixture_dir.mkdir(parents=True, exist_ok=True)
        for name, envs in (
            ("offset_walk.json", offset_envelopes),
            ("cursor_walk.json", cursor_envelopes),
        ):
            path = args.fixture_dir / name
            path.write_text(
                json.dumps(envs, indent=2, default=str) + "\n"
            )
            log.info(
                "wrote %s (%.0f KB)",
                path,
                path.stat().st_size / 1024,
            )
    else:
        log.info(
            "fixtures NOT written (--write-fixtures off). This slice "
            "would produce ~%.0f KB per walk.",
            len(cursor_events) * 1364 / 1024,
        )

    log.info("envelope shapes: %s", json.dumps(_strip(cursor_envelopes)))

    if short_live:
        log.info(
            "H4 POSITIVE: %d page(s) came back short with a live "
            "cursor. The deleted len(results) < page_size break would "
            "have truncated this walk.",
            len(short_live),
        )
    else:
        log.info(
            "H4 negative: no short page with a live cursor on this "
            "slice. Deleting the short-page break was correct but is "
            "not vindicated by this measurement."
        )

    if result["parity"]:
        log.info("PARITY: both walks returned identical data")
        log.info("  digest %s", result["offset_content_digest"])
        return 0

    log.error("MISMATCH -- the two walks disagree: %s", result["checks"])
    log.error(
        "Per the pre-analysis plan section 4: STOP. Do not ship either "
        "mechanism until it is known which walk is wrong."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
