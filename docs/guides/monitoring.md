# Monitoring — setup of record

*What watches this system, what each thing does **not** watch, and how to rebuild it all without
logging into anyone's dashboard. Decision of record: **ADR-051**. Live since 2026-08-03.*

**No secrets in this file.** Everything here is either public (the status page is unauthenticated
by ADR-038) or a setting, not a credential. That is deliberate — see §6. §7 *discusses* the one
genuine secret in this system without containing it, which is the distinction to preserve if you
edit this page.

---

## 1. Three questions, three mechanisms

The single most important thing on this page. These are **not** redundant, and none of them
substitutes for another:

| Mechanism | Answers | Cadence | Reaches you by |
|---|---|---|---|
| healthchecks.io heartbeat | *did the monthly pipeline run?* | push; 30-day period + 48 h grace | e-mail |
| Better Stack monitor | *is the data reachable right now?* | poll, 3 min | e-mail |
| `serving-freshness.yml` | *is what it serves still current?* | daily 07:00 UTC | opens a GitHub issue |

The pipeline writes files on the host. Caddy serves them over HTTP. **They fail independently.**
Before 2026-08-03 only the first existed, so Caddy could stop while the pipeline kept succeeding
and pinging — green light, no data, detected never. That was C-335.

**No mechanism alerts on another's failure.** If the status page is unreachable, the freshness
workflow logs it and exits *without* opening an issue, because Better Stack has already alerted
within three minutes. Two alarms for one event is how people learn to ignore both.

## 2. Better Stack account

| | |
|---|---|
| Provider | Better Stack (Uptime product), https://betterstack.com |
| Owner | Simon Polichinel (PRIO) — same account as views-faoapi |
| Plan | **Free tier.** 10 monitors, 3-minute checks, e-mail alerting |
| Credentials | Team password manager, not here |

The account also holds views-faoapi's monitor. Monitor names are prefixed so they do not get
confused during an incident.

## 3. The monitor, exactly as configured

| Field | Value |
|---|---|
| URL | `http://204.168.219.108/status.html` |
| Alert type | `URL becomes unavailable` |
| Interval | 3 minutes |
| Escalation | Notify the primary responder |
| Notify by | E-mail |
| If unacknowledged | Do nothing |

**`http`, not `https`.** The data server has no TLS certificate (C-318). Setting `https://` makes
the monitor fail immediately and look like a permanent outage.

**No credential is stored in Better Stack.** The status page is public by ADR-038 — it carries
source names, stage labels, coloured dots and timestamps, nothing sensitive. views-faoapi cannot do
this: its `/health` endpoint needs an `X-API-Key`, which therefore lives in the vendor's dashboard.
Ours does not.

**Verified at setup, not assumed:** monitor reached **Up** (~27 ms from Europe) and a test alert
was delivered and read. If you add a monitor later, do the same — a monitor that can detect a
problem but cannot reach anyone is not a monitor.

> **Add the sender to your safe-senders list.** The first test alert arrived with *"Some content in
> this message has been blocked because the sender isn't in your Safe senders list."* An alert that
> lands in junk is an alert you will not act on.

## 4. The freshness workflow

`.github/workflows/serving-freshness.yml` — daily plus `workflow_dispatch`.

Fetches the public page and flags two things:

1. **Age** — the `Generated <ISO8601>` marker older than **40 days**. The pipeline cron runs 00:00
   on the 21st, so ~31 days is a normal maximum; 40 allows one grace window, mirroring the
   heartbeat's 30 d + 48 h.
2. **Stage status** — parses the per-cell `title="<status>"` attributes and flags anything outside
   `{ok, not_applicable}`. It also flags finding **no** status cells at all, because a check that
   silently inspects nothing is worse than no check.

On a problem it opens **one reusable issue** and closes it automatically on recovery.

> **Do not "simplify" this to a text search for "stale".** It was written that way first and the
> drill caught it: the page has a legend — `● OK ● Stale ● Missing` — explaining the dot colours,
> so those words appear on every healthy page. The first version reported one of each against a
> perfectly healthy server. ADR-051's original specification had the same bug, so buying the paid
> keyword monitor would not have saved us.

## 5. If we move to a paid Better Stack tier

Recorded so the decision is ready-made rather than re-derived. In rough order of value:

1. **Keyword/content monitor on `status.html`** — would let freshness live beside availability, and
   `serving-freshness.yml` could be retired. Note it must match on the **status cells**, not the
   page text, for the reason in §4.
2. **Phone/SMS escalation on the availability monitor.** Today it is e-mail only. Reachability of
   the data is the one failure worth waking someone for; staleness is not.
3. **Multi-region checks**, so one probe's network blip stops looking like an outage. views-faoapi
   saw three `/ping` timeouts in a single day (2026-07-30) that may well have been this.
4. **A second monitor pattern** if we ever expose an authenticated health endpoint, following
   views-faoapi's `/health` design — with the credential-custody cost that implies.

## 6. What we deliberately do not use

- **No on-host cron check.** It would share fate with the box it watches, and cannot see DNS, the
  network path, or TLS. ADR-051 rejects it explicitly.
- **No stored token for the workflow.** It uses `GITHUB_TOKEN` with `issues: write`. A personal
  access token was rejected: it adds a credential with a rotation burden, days after a sprint spent
  removing exactly that (ADR-026, C-324).
- **No merge-blocking checks for any of this.** Monitoring failures must never redden a pull
  request; that is C-320's lesson.

## 7. The ping URL is a secret

`HEARTBEAT_URL` is a **capability URL**. There is no account behind it and no credential to
present: whoever holds the string can send a success ping, mark the monthly pipeline healthy, and
silence the dead-man alert permanently. Treat it exactly as you would a password.

**It is never passed on a command line.** `/proc/<pid>/cmdline` is world-readable (`-r--r--r--`),
and four accounts have shells on the box, so a `curl "$HEARTBEAT_URL"` is readable by any of them
for the life of the request. All three pings hand the URL to curl on **stdin** instead:

```bash
printf 'url = "%s"\n' "$HEARTBEAT_URL/fail" | curl -fsS --max-time 10 -K -
```

**The quotes are load-bearing, and this is not a style preference.** Measured against curl 7.81.0
with a value carrying a stray space:

| form | result |
|---|---|
| `url=%s` (unquoted) | truncates at the whitespace and **sends the truncated URL** — a `/fail` ping silently becomes a *success* ping |
| `url = "%s"` (quoted) | exit 3, nothing sent |

A trailing space or CR is the realistic contamination for a hex-UUID URL: a CRLF-edited `.profile`,
a copy-paste. The unquoted form is what C-331's own register entry originally prescribed; it was
superseded once this was drilled, because it fails *green* and the quoted form fails *safe*.

**Verified, with a control.** The `/proc` claim was drilled before the change shipped, using a
canary against an unrouted address. The old form leaked
`curl -fsS --max-time 20 http://.../CANARY-.../fail` into `/proc/<pid>/cmdline`; the new form showed
`curl -fsS --max-time 20 -K -` in flight with no process anywhere carrying the canary. The negative
control ran first — without it, a clean scan proves only that the scanner is broken.

**What this does not close.** The URL is still in the process *environment*
(`/proc/<pid>/environ`, mode `-r--------`, so owner and root only). Never `echo` the value to a
terminal — it lands in scrollback and in any pasted transcript.

**The `~/.profile` question was asked, and the answer was bad.** Checked 2026-08-10 rather than
assumed: the file was mode **644** inside a **751** home, and `test -r` from a second account
returned readable. Every credential in it — not just this URL — had been readable by all four shell
accounts continuously. Fixed with `chmod 600`, verified from both directions (unreadable by the
other account, still readable by the owner, pipeline path intact). That is **C-344**, and it was a
strictly larger exposure than the one this section is about. The setup guides now carry the `chmod`
that would have prevented it.

Guarded by `tests/test_heartbeat_secret.py`. See ~~C-331~~.

## 8. Silence lies

**Silence = healthy only while something is actually checking.** A paused, deleted, or expired
monitor is also quiet, and quiet is what you have been trained to read as fine.

Once every few weeks, spend ten seconds confirming the Better Stack **Monitors** page shows the row
as *Up* and actively checking — not *Paused* — and that the freshness workflow has recent runs in
the Actions tab. This warning is lifted from views-faoapi's runbook, where it was learned the hard
way.

## 9. How to leave

Nothing here is locked in. The availability monitor is one URL and one alert rule — reproducible on
any uptime provider in five minutes from §3. The freshness workflow is a file in this repo and
depends on nothing but `curl`, `python3` and `gh`. The heartbeat is three `printf | curl -K -` pings in
`scripts/refresh_pipeline.sh` (§7 explains why the URL goes on stdin). Losing the Better Stack account costs §3 and nothing else.

## 10. References

- **ADR-051** — the decision, including the 2026-08-03 amendment recording what was actually built
- **ADR-018** — bounded staleness, per-source SLO, and what the heartbeat does *not* detect
- **ADR-038** — why `status.html` is public, which is what makes credential-free polling possible
- ~~**C-335**~~ — the serving-path gap this closes
- `scripts/refresh_pipeline.sh` — the three heartbeat signals (`/start`, success, `/fail`), each a
  `printf | curl -K -` so the URL never reaches a command line (§7)
- views-faoapi `reports/ops/betterstack_{deployment,monitoring}.md` — the sibling setup this mirrors
