# ADR-051: Two monitoring mechanisms, because there are two failure modes

**Status:** Accepted
**Date:** 2026-08-01
**Deciders:** Simon (operator), views-datafactory maintainers
**Consulted:** ADR-011 (fail-loud), ADR-018 (operational resilience, bounded staleness), ADR-038 (public status page via Caddy path exemption), views-faoapi ADR-032 (Better Stack for a live API)
**Supersedes:** nothing. **Extends** ADR-018's "External monitoring" section.

---

## Context

`views-datafactory` monitors its monthly pipeline with a **dead-man switch**: `refresh_pipeline.sh`
pings healthchecks.io on `/start` (`:163`), on success (`:290`), and on `/fail` (`:92`). Period 30
days, grace 48 hours. It is drilled — the 2026-07-19 live test flipped the check red in seconds — and
it closed C-131.

Meanwhile `views-faoapi` adopted **Better Stack** (their ADR-032) for a different job: polling a live
API's `/ping` from outside every 3 minutes, plus a second monitor doing a keyword check on `/health`
to catch stale forecasts served behind a healthy service.

The operator asked the reasonable question: that looks general — should this repo migrate to it too?

Investigating the question surfaced something more important than the answer.

## The two mechanisms are not substitutes

|  | **Heartbeat (push)** | **Poll (pull)** |
|---|---|---|
| Who initiates | the job, outward | the vendor, inward |
| Answers | "did the scheduled thing run?" | "is the thing answering right now?" |
| Detects | cron dead, host rebooted, job crashed | DNS, TLS, reverse proxy down, host gone |
| Structurally blind to | anything between runs | anything that is not a live endpoint |

A poller cannot tell you a monthly cron failed to fire — there is nothing to poll that says so. A
heartbeat cannot tell you the web server died three weeks ago — the job that pings is not the process
that serves. Choosing between them is a category error; they see disjoint failures.

## The gap this exposed (C-335)

We have **two** systems, and we monitor **one**. The pipeline writes data on the host; Caddy serves it
over HTTP. They fail independently.

- **Host down** — pipeline cannot run, no ping, healthchecks fires after period + grace. Worst case
  ≈ **32 days**. Slow, bounded, and it does alert.
- **Caddy down, host up** — the pipeline runs, succeeds, pings. **The check stays green.** Consumers
  get nothing. Detection: **never**, absent a human complaint.

The second case is why this is worth an ADR. The system does not merely fail to report a problem; it
*actively reports health* while broken, and a green light gets used as evidence. views-faoapi hit this
exact shape — a 139-day-old artifact served behind green health (their C-50/C-170) — which is why
their ADR-032 has a second, content-checking monitor rather than liveness alone. We should learn it
from their incident rather than from our own.

## Decision

### 1. Keep the push heartbeat where it is

The pipeline heartbeat stays on healthchecks.io. It works, it is drilled, and migrating it would cost
something concrete:

**Better Stack heartbeats have no `/start` equivalent.** Verified against their documentation
(2026-08-01): the documented signals are the success ping, `/fail`, and `/$?` for exit codes. There is
no "run in progress" signal.

That matters specifically here. `/start` is what PR #359 shipped for **C-317**: a `SIGKILL` — the OOM
killer being the realistic case — bypasses the bash `ERR` and `EXIT` traps, so no `/fail` is ever sent.
The `/start` ping is what allows a checker to notice that a run began and never finished. Migrating
would discard a mitigation we shipped deliberately, for a failure mode we have already reasoned about,
in exchange for vendor tidiness. C-317 is still open pending its live drill; migrating would close it
by deletion rather than by fixing it.

### 2. Add an external poll for the serving path

Poll the **public status page** (`status.html`) from outside the host.

`status.html` is unauthenticated by deliberate decision (ADR-038: it carries source names, stage
labels, coloured dots, and timestamps — nothing sensitive). This gives us an advantage views-faoapi
does not have: **no credential is handed to the monitoring vendor.** Their `/health` monitor must
store an `X-API-Key` in Better Stack; ours needs nothing.

Two checks on one target:

| Check | Alerts when | Catches |
|---|---|---|
| Availability | `status.html` does not return HTTP 200 | Caddy down, host down, DNS/TLS/network path broken |
| Content | the body does not contain the healthy marker | pipeline stages stale or missing while serving fine |

The content check is the direct analogue of views-faoapi's freshness monitor, and it closes a second
gap: today, *staleness* is visible only to someone who opens the page and looks at the dots.

---

> ### Amendment, 2026-08-03 — what was actually built
>
> The table above specifies two checks. **One of them was built as described; the other could not
> be, and is now somewhere else.** Recorded rather than rewritten: the gap between what was decided
> and what was buildable is the useful part.
>
> **Availability — built.** Better Stack monitor on `http://204.168.219.108/status.html`, 3-minute
> interval, alert type `URL becomes unavailable`, e-mail to the primary responder. Verified live:
> **Up**, ~27 ms from Europe, and a test alert was delivered and read. This closes the unbounded
> failure C-335 was about.
>
> **Content — not built here.** Better Stack gates keyword matching behind a paid plan; the
> create-monitor form says *"We recommend the keyword matching method. Upgrade your account to
> enable more options."* Rather than pay, that half moved to
> `.github/workflows/serving-freshness.yml` — a daily scheduled workflow that fetches the page,
> checks its `Generated` timestamp against a 40-day limit, and inspects the per-cell status
> attributes. It runs on GitHub, not on the monitored host, so it satisfies this ADR's own
> requirement that the poller not share fate with what it watches.
>
> **The specification in the table above was itself wrong**, and would have been wrong on the paid
> tier too. It says the content check should alert when *"the body does not contain the healthy
> marker"*. The page carries a **legend** — `● OK ● Stale ● Missing` — explaining the dot colours,
> so the words `Stale` and `Missing` appear on every healthy page. A body-text check reported one
> of each against a perfectly healthy server during the drill and would have opened an issue every
> day until somebody muted it. The workflow parses the per-cell `title="<status>"` attributes
> instead. Not buying the feature cost us nothing; specifying the check without testing it nearly
> cost us a monitor nobody trusts.
>
> **Division of labour, now three-way:**
>
> | Mechanism | Question | Cadence |
> |---|---|---|
> | healthchecks.io heartbeat | did the monthly pipeline run? | push, 30 d + 48 h grace |
> | Better Stack monitor | is the data reachable right now? | 3 min, can phone |
> | `serving-freshness.yml` | is what it serves still current? | daily, opens an issue |
>
> None alerts on another's failure. If the page is unreachable the workflow logs and exits without
> opening an issue, because Better Stack has already alerted — duplicate alarms for one event are
> how people learn to ignore both.
>
> Setup of record: `docs/guides/monitoring.md`, which also lists what we would configure if the
> account is ever upgraded. C-335 closed; the residual is registered.

### 3. Vendor choice is deliberately not the decision here

What matters is that **something outside the host polls the serving path**. Better Stack is the
default because a sibling repo already runs it, the operator knows the interface, the free tier fits
(10 monitors, 3-minute checks, email + one phone call), and it is EU-resident. Any equivalent poller
satisfies this ADR.

### 4. This is explicitly not the end state

Recorded because the operator asked for it in those words, and because it is true:

> Two monitoring vendors for one small system is a compromise, not an architecture.

The compromise is accepted **only** because BetterStack cannot express `/start`. That is a vendor
limitation, not a law. **Revisit when any of these becomes true:**

- Better Stack (or the poller of the day) gains a run-started/in-progress signal → consolidate onto one
  vendor and retire healthchecks.io.
- C-317 is closed by a mechanism that does not depend on `/start` — for example the pipeline recording
  its own run-state to a file the content check can read → the `/start` argument evaporates and
  consolidation becomes free.
- Either free tier changes such that the split costs money.
- A third repo needs monitoring → the platform should decide once, not three times.
- Operating two dashboards demonstrably causes a miss (see the failure mode below) → collapse to one
  even at the cost of coverage, and say so explicitly.

## Alternatives rejected

| Alternative | Why not |
|---|---|
| **Migrate everything to Better Stack** | Loses `/start`, therefore loses C-317's mitigation. Legitimate *if* C-317 is first solved another way — that path is written into the revisit triggers above, not closed off. |
| **Change nothing** | Leaves the unbounded Caddy-down case undetected. The cost of closing it is browser-only setup; the cost of not closing it is consumers silently getting nothing. |
| **Poll from a cron on the same host** | Would catch the Caddy-down case, since the host is up by definition. But it shares fate with the host for everything else, and cannot see DNS, the network path, or TLS. Monitoring that dies with the thing it monitors is the classic mistake. |
| **Self-host a monitor elsewhere** | A second box to maintain, patch, and monitor. The recursion has to stop at a vendor eventually; it may as well stop at the first one. |

## Consequences

**Positive**

- The unbounded failure case (green while unreachable) becomes a detected one.
- Staleness becomes visible from outside, not only to someone reading dots on a page.
- No code change, no release, no server access — this is operator setup, which also means nothing in
  this decision can break the pipeline.
- No credential is given to the monitoring vendor.
- C-317's mitigation survives.

**Negative**

- **Two vendors, two dashboards, two free tiers, for one operator.** This is the real cost and it
  should not be minimised.
- **The specific way this bites:** both tools treat *silence* as *health*. A paused, deleted, or
  expired monitor is also silent. views-faoapi's own runbook flags this ("silence lies if nothing is
  watching") and it now applies in two places instead of one. Mitigation: the same 10-second habit
  their doc prescribes — occasionally confirm the monitors are actually *checking*, not merely
  *quiet*.
- Two places to remember to un-pause after planned work.

## References

- **C-335** — the serving-path gap this ADR responds to
- **C-317** — SIGKILL bypasses the traps; the reason `/start` is load-bearing
- ~~**C-131**~~ — external monitoring for cron, resolved; C-335 is the sibling gap it did not cover
- **ADR-018** — operational resilience, bounded staleness, per-source SLO; this ADR extends its
  "External monitoring" section
- **ADR-038** — why `status.html` is public, which is what makes a credential-free poll possible
- **ADR-011** — fail-loud
- `scripts/refresh_pipeline.sh` — the three heartbeat signals: the `/fail` ping in
  `on_failure()`, the `/start` ping after the `flock`, and the bare success ping before the
  duration record. Cited by symbol, not line: the line numbers here were `92,163,290` and had
  drifted to 112/182/309 without anything noticing (C-336)
- views-faoapi **ADR-032** and `reports/ops/betterstack_{deployment,monitoring}.md` — the sibling
  decision this was weighed against; their C-50/C-170 is the incident we are learning from
- Better Stack heartbeat documentation, checked 2026-08-01 — grace periods and `/fail` supported, no
  run-started signal
