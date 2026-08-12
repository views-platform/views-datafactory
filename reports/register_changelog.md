# Risk register — change log

Narrative history of how `technical_risk_register.md` evolved: what was registered, what
was corrected, and what was retracted. Newest first.

**Why this file exists.** The register header used to carry this narrative inline, where it
competed for space with the header's other job — being an index. The search-window guard
(`test_falsification_merge_readiness.py`, 8000 chars) then forced someone to delete history
whenever the two collided. On 2026-08-02 two entries were retired purely to reclaim 1200
characters, not because they had stopped being true. **Both are restored below.** Separating
the two jobs keeps the index findable and lets this record grow without anything being
deleted to make room (#404).

**The corrections are the valuable part.** An entry registered, then retracted, then partly
re-confirmed by observation (C-330) says more about how this project reasons than any clean
entry could.

---

## `/code-review max` — the detector was never going to run, and three of my own corrections were wrong (2026-08-12)

Second review round on #439. Fifteen findings, verified empirically rather than argued: the shell
step was extracted from the YAML and executed under `bash -e` against synthetic repositories with a
stubbed `gh`. **The round is worth more than the story.**

**C-350 — the deliverable would not have run.** GitHub fires `schedule` from the **default branch
only**. This repository's default branch is `main`; all work goes through `development`. So the
detector merges to `development` and the 06:00 cron keeps executing `main`'s copy, which contains no
detector, until an irregular release promotion carries it over. Measured: `origin/main`'s workflow
has **zero** occurrences of `orphan`, and every `event: schedule` run has `headBranch: main`.

Meanwhile the guide, this changelog and C-340's narrowing all stated *"checks daily"* as present
fact, and the four new guards assert properties of the **branch's** file, so they go green on every
pull request while the branch that runs the cron has none of it. Every verification performed was
true and none of them was the question. A `workflow_dispatch` run proves the code works; it says
nothing about whether anything will ever call it. All three claims corrected.

**C-351 — a live red gate nobody was reading.** `serving-freshness.yml` has failed every scheduled
run since at least 2026-08-08: no `actions/checkout` step, so a git command aborts with `fatal: not
a git repository`. Freshness alerting for the served artefacts has been dead for five days. Recorded
immediately rather than as a review aside, because *"pre-existing"* is not a disposition this
project accepts.

**Three of my own guards could not fail for what they claimed.** `"answered="` is a **substring** of
`"unanswered="`, so the counting assertion passed with every `answered` counter deleted; and a bare
`"::error::" in run` searching a 130-line body was satisfied by an unrelated guard a hundred lines
below, so deleting *both* branch-enumeration guards kept the suite green. The class comment three
lines above warns against asserting "the how, not the what" and cites C-336. Rewritten with a
lookbehind, anchored patterns, and step lookup by stable `id:` rather than by a substring of the
body under test — then drilled against the exact three defeats the review demonstrated.

Rewriting them produced a fourth instance of the same thing: the first replacement matched the
step's own **comments**, which quote the anti-patterns they warn against, so it reddened the *fixed*
file. Caught by the control run. Comments are now stripped before matching — which is what
`test_heartbeat_secret.py` already learned, in this same epic.

**The C-345 addendum written this morning was wrong, and is retracted in place.** It claimed pytest
colourises its summary so `grep -cE '^FAILED'` cannot match. pytest does **not** colourise into a
file; the ANSI codes came from `FORCE_COLOR=3` exported in this operator's shell. Measured both
ways: with it, `grep -cE '^FAILED'` returns 0 on a failing run; with `env -u FORCE_COLOR`, it
returns 1 and there are zero ANSI lines. **C-345's original prescription was fine in a plain shell
and in CI.** An anomaly produced by an uncontrolled environment variable was diagnosed as a defect
in the tool and escalated into a general claim about this register — *"the second time an entry has
prescribed a defective remedy"* — which is withdrawn. That is C-347, committed inside the commit
registering C-347. `--color=no` stays, because removing a dependency on the caller's environment is
right for the reason the wrong diagnosis inverted.

**C-349 undercounted its own locations.** It named three `JSONDecodeError` sites; `grep -rn
JSONDecodeError src/` returns seven, and `digests_and_ledgers.py` — the provenance package's own
ledger reader — **already logs the skip**, falsifying the entry's central *"nothing anywhere records
that it happened"*. An entry that undercounts gets closed after a partial fix. Corrected, with the
grep written into the Location field so the count is re-derivable rather than asserted.

**What is not fixed, and why the story stops here.** Nine verified behavioural findings remain — the
recovery the issue body prescribes never clears the alert, so the cron would go permanently red and
the shared issue permanently open; a partial scan writes an unqualified `orphans=false` that
auto-closes a genuine orphan issue; the issue-reuse path never renders the orphan section at all, so
the daily comment names no branch; `merge-base` exit 128 is booked as a definite answer *inside* the
accounting added to fix C-347; two `sed` parsers depend on `gh`'s compact JSON; `--limit 1` orders
by `createdAt`, not `mergedAt`; and a bare branch name in `git fetch` resolves against
`refs/tags/` first.

**The pattern is the finding.** Round one: five defects. Round two: fifteen, each from a different
property of git, of `gh`, or of GitHub. That is the signature that ended the pre-push hook after
four versions, reappearing in its replacement — and the panel's argument then applies unchanged now:
the failure has occurred twice in ~440 pull requests and both times was recovered by cherry-pick
inside the hour. **Continuing to iterate is the tired answer, not the engineering one.** The design
question goes back to the operator rather than being resolved by a third round.

---

## C-347, C-348 registered and C-345 corrected — the detector arrived with three fails-green defects (2026-08-12)

Epic #421 Story 5 (#439), the `/code-review` round on the fix for C-340. **The cluster grew out of an
attempt to shrink it.** That is the honest result and Story 7 (#428) has to report it.

**Three defects in the replacement, none of which would have reddened anything.** The orphan
detector was drilled end-to-end the night before and reported working. Review found: (1) the
workflow's `permissions:` block never granted `pull-requests`, and an explicit block sets every
unlisted scope to `none` — so both `gh pr list` calls would 403, swallowed by `2>/dev/null || continue`,
and the step would report "No orphaned branches" on a daily cron forever; (2) merged PRs were matched
by **branch name alone**, the same property that defeated hook v1 — and reuse is real here
(`chore/version-bump-1.2.13`, `docs/roadmap-plan-v11`, `feat/acled-phase2` have each headed more than
one PR), with the old head absent from the new branch's ancestry so `git rev-list` errored and was
reported as `? commit(s)`; (3) `for branch in $(git ls-remote ...)` hides a failure of the
substitution completely — GitHub runs `bash -e {0}` and `set -uo pipefail` does not remove `-e`, but a
`for` word list is exempt. Verified: `bash -e -c 'for x in $(false | sed s/a/b/); do echo BODY; done; echo END'`
prints only `END`.

**C-347 — why the drill could not have caught any of this.** It ran under the operator's personal `gh`
credentials, which carry full scope; production runs under `GITHUB_TOKEN` with `pull-requests`
revoked. The drill obtained and reported its result *correctly*; it simply ran in the wrong world.
That is not C-345 (an instrument misreading a result it did obtain) and it is not C-336 (a guard whose
claim is narrower than its property) — it is a third thing, and it has now fired four times in one
week, each from a different environment property: `gh` never hidden because it lives in
`~/.local/bin`; a `git checkout` silently refused so a "want FAIL" case ran on-tag; `pytest` run from
the main repo while the test shelled out to `git describe` in the wrong tree; and this. **A drill is
an experiment, and it silently inherits every variable you did not control.**

**C-348 — the deletion took a guard with it.** `tests/test_git_hooks.py` was deleted with the hook,
correctly for the hook's own assertions. It also held the only guard on `scripts/arm_automerge.sh`'s
executable bit — a script the same pull request deliberately *keeps*. A test module is an
organisational unit that quietly doubles as a coverage unit, and only the first is visible when you
delete it. Tier 4: the loss surfaces loudly as `Permission denied`. Registered because two more
deletions are scheduled in this epic.

**C-345's own prescribed mitigation is defective, and the drill is what proved it.** The entry
recommends `grep -cE '^FAILED' out.txt` as a second independent reader. pytest **colourises** its
summary, so the line is `\033[31mFAILED\033[0m tests/...` and the caret never matches. The harness
built for these drills required both `rc != 0` and `FAILED >= 1`, and reported *"DID NOT CATCH"* four
times while all four drills had in fact caught. Had it trusted only the grep — the reading C-345
recommends — a red suite would have read green. Corrected to `--color=no` at the source rather than an
ANSI-aware regex, which would only be one more narrow claim. **This is the second time an entry in
this register has prescribed a defective remedy** (C-331's unquoted `printf 'url=%s'` turned a failure
ping into a success ping). A mitigation written into an entry is untested code that inherits the
entry's credibility without earning it — worth saying out loud, because the corrections are the
valuable part.

**All four new guards were drilled against the broken state, with a control.** Revoke the permission,
restore the blind loop, move the fetch step after the detector, strip the executable bit: each
reddened exactly the guard aimed at it, and the fixed tree stayed green.

**Then `/review-diff` found the same defect one level down, and C-349 came out of generalising it.**
The permission fix removed the *systematic* 403, but every per-branch `|| continue` still converted
"could not check this branch" into "this branch is fine" — a rate limit or a 502 would skip branches
and the step would still print a confident all-clear. The detector now counts what it answered for,
qualifies a partial result, and **exits non-zero if it answered for nothing**: a clean report resting
on zero observations is the defect itself, not a degraded mode of it.

Grepping for that shape in production code found it three times — `acled.py`, `ucdp.py` and
`health.py` all drop an unparseable ledger line with a bare `except json.JSONDecodeError: continue`,
uncounted, while `grid_compilation.py` twenty lines of a different module away already does it
correctly with `n_skipped_spatial += 1`. Since the consolidators use the ledger to decide what to
consolidate, a dropped line means a successful harvest is silently not consolidated. Registered as
**C-349** and deliberately **not fixed here** — #439 is a CI story, and an untested change to
consolidation does not belong in a pull request about a workflow.

**The reused-name fix was drilled in a scratch repository**, since git ancestry semantics do not
differ between the operator's machine and the runner (the C-347 caveat is about credentials and
environment, not about git). Squash-merge a branch, push a follow-up to it, then delete the branch
and cut a fresh one reusing the name: the new logic reports the genuine orphan as 1 stranded commit
and **skips** the namesake, where the old logic reported the namesake as 3 commits stranded.

**The permission fix was then verified the way C-347 says to verify things** — by dispatching the
workflow (run 31590304501) rather than running its body locally. It reported *"Checked 1 branch(es);
0 could not be answered for."* Had the scope still been revoked, `gh pr list` would have 403'd into
`|| continue` and the new zero-answers rule would have turned the run red. Writing C-347 and then
*not* dispatching would have been the entry's own failure mode, committed in the commit that
registers it.

One guard was also loosened rather than tightened: the ls-remote assertion had matched the exact
wording of a log message, which would redden on a reword for no behavioural reason. It now checks
that a failure path exists at all. Asserting the *how* instead of the *what* is C-336's second
addendum, and it is easy to commit while writing a guard against something else.

---

## C-340 NARROWED — four versions of a guard, abandoned for a detector (2026-08-12)

Epic #421 Story 5 (#426, #437, #438 closed unmerged, #439). The most instructive entry of the epic,
because the deliverable is a **removal**.

**Mechanism 1 resolved.** `scripts/arm_automerge.sh` arms via GraphQL disable/enable and reads the
method back. Reproduced live on #437 before shipping: `gh pr merge --auto --squash` against an
already-`MERGE`-armed PR exited **0** and changed nothing.

**Mechanism 2: four client-side attempts, four different defeats.** v1 read `git rev-parse HEAD`
instead of the refs git supplies on stdin *and* matched on branch name, permanently refusing names
reused from old PRs. v2 used ancestry — defeated because a merge-commit merge puts the head into the
base branch forever. v3 used `remote_sha` — defeated because `delete_branch_on_merge` removes the
branch first, so git reports `0000…`. v4 was never shipped. The test suite was **vacuous**:
reconstructing v1 and running all seven behavioural tests passed every one.

**It recurred while being fixed.** #437 auto-merged carrying broken v1; the review fixes were pushed
to that branch afterwards and orphaned. The same defect, inside the pull request addressing it. The
hook was not installed in that clone — `core.hooksPath` is per-clone config git does not version,
which is itself the argument against an install-it-yourself guard.

**Why it was abandoned rather than fixed a fifth time.** Four failures from four *different*
environment properties is the signature of inferring state you cannot see, not of carelessness. A
multi-expert panel converged independently: Kleppmann (a client check races an asynchronous
deletion — a property, not a bug), Ousterhout (a shallow module whose complexity is entirely special
cases; four versions are four attempts to enumerate them), Beck (twice in ~440 PRs, both recovered
by cherry-pick inside the hour — the guard had already cost more than the failures). Their verdict
on the *warning* variant was the sharpest: a notice printed on every push goes invisible in a week,
which is the exact fails-green shape this epic exists to remove, and shipping it would have created
a precedent to cite later.

**The framing was the error, and that was the finding.** The orphaned *state* is unambiguous once
things settle — a remote branch with commits beyond its merged PR's head and no open PR. Two
questions, no ancestry subtleties, no merge-method dependence, nothing to install, and it cannot
block anyone's work. `release-topology.yml` already had `fetch-depth: 0`, `issues: write`, a daily
cron and one-reusable-issue machinery.

**Drilled end-to-end against live state**, with the body extracted from the workflow rather than
retyped: it found the genuine orphan (*"1 commit(s) pushed AFTER PR #437 merged, no open PR"*),
correctly ignored a branch whose PR was closed-unmerged, and reported clean once that branch was
deleted. Measured against the merged PR's head rather than `development` — merges here are squashes,
so a branch's own commits are never ancestors of `development` and the naive comparison would flag
every merged branch.

**Left open on the residue**, and #428 must say so: this is detection, not prevention, and nothing
forces `arm_automerge.sh` — `gh pr merge --auto` is one keystroke away.

---

## C-341 RESOLVED by deleting the gate, and C-346 — four more that cannot fail (2026-08-11)

Epic #421 Story 4 (#425), which also closes #363. The instruction was "delete F1". It turned out
not to be one deletion.

**The gate could not fail, and that was structural rather than accidental.** `TestF1VersionBumped`
asserted *"the current version is not already tagged"*. Version here is bumped only at release time,
so from the moment a release lands until the next bump the version **is** a tag that exists — the
entire inter-release period. Measured in both states rather than argued:

| state | result | suite exit |
|---|---|---|
| version tagged (steady state) | XFAIL | 0 |
| version untagged (just bumped) | XPASS | 0 |

Green either way. It asked *"have you bumped yet?"*, which repo state cannot answer, because *"about
to release"* is not knowable from the repo — only from the tag that triggers a release.

**So it was deleted rather than given a runner**, and replaced by the two halves that *are*
answerable: `TestVersionMatchesItsTag` (if HEAD is on a tag, the version must equal it) and an
**unskippable** guard in `publish_package.yml` comparing `github.ref_name` to the version before the
build. The new test was drilled to a genuine failure in an isolated worktree checked out at
v1.11.0 — `rc=1`, naming both values. Its predecessor could not fail in any state.

**Grepping for the thing being deleted found four more.** `test_version_not_already_tagged` also
lives in three other deploy suites, using a *conditional* `xfail` that reads as more rigorous and is
worse: it runs only when the version is untagged, then asserts the version is untagged — asserting
the condition that selected it. Registered as **C-346**, Tier 4, and deliberately left in place:
removing four classes across unrelated suites plus the meta-test that *enforces* the marker is its
own change, and the replacement now exists.

**Two drills of my own were wrong before they were right, both the same way.** A `git checkout
v1.11.0` was silently refused because of uncommitted changes, so the "want FAIL" case ran with HEAD
not on a tag, skipped, and returned `rc=0` — which I would have recorded as a result. Redone in a
worktree, with the setup verified (`HEAD tag=v1.11.0`) before the assertion ran. Then the same again:
pytest was invoked from the main repo while the test shells out to `git describe` in the *current
directory*, so it still answered about the wrong tree. Fourth and fifth instances this week of a
drill whose setup did not happen while the exit code looked fine — the C-345 family.

**The replacement had a fails-green of its own, caught by review not by me.** `_head_tag()` used
`git describe --tags --exact-match HEAD`, which returns **exactly one** tag — the lexicographically
smallest — and a commit can carry several. Reproduced: tag one commit `v1.11.0` and `checkpoint`,
and `describe` answers `checkpoint`, regardless of creation order or tag type. The release tag is
then invisible, the test skips, and **it skips precisely when a real mismatch is sitting on that
commit**. Switched to `git tag --points-at`, which lists all of them, and drilled the multi-tag case
that had no drill before: mismatch with a stray non-`v` tag present now fails `rc=1`.

Worth noting where it was *not* a problem: the `publish_package.yml` guard compares
`github.ref_name` directly and never shells out to `git describe`, so the unskippable half was
immune. The two halves failing differently is the argument for having both.

**And the publish guard had a real bug the drill caught.** It read the version with bare `python3 -c
"import tomllib"`. `tomllib` needs ≥ 3.11; local `python3` is 3.10, and the runner's is whatever the
image ships. Pinned to `uv run --no-project --python 3.12`, matching the guard beside it. That one
would have surfaced at a release — the single worst moment, against an immutable tag.

---

## C-342 RESOLVED, C-341 NARROWED — the gates run somewhere, and the one that still does not is named (2026-08-11)

Epic #421 Story 3 (#424). The story shipped smaller than its issue described, and the reason is the
interesting part.

**The issue's own table was wrong, and measuring it is what showed that.** #424 claimed four gates
would start running once the workflow got a step and a token. Simulating a runner checkout first:

- `actions/checkout` leaves exactly **one** local branch, so the gates' bare
  `git merge-base --is-ancestor main development` exits **128** and they skip themselves — *even at
  `fetch-depth: 0`*, which the workflow already had. Two `git branch -f` lines fix it, and without
  them the step would have run, passed, and asserted nothing.
- The local-clone branch gate would have **passed trivially** on a runner rather than skipped. That
  is worse than skipping: it reports coverage it does not have. It now skips with a reason.
- `TestF1VersionBumped` is `xfail`. It cannot fail a suite anywhere, so scheduling it would add a
  green tick and no information.

So of the four gates named, one was redundant, one needed unblocking, one needed *demoting to a
skip*, and one cannot be made meaningful without #425. **C-341 is narrowed, not closed** — closing
it would claim a coverage the xfail denies. The back-merge conflict-free check, which nothing was
running anywhere, is a straight gain the issue never mentioned.

**C-342 resolved**: `uv lock --check` in the `test` job, before `uv sync`. Drilled clean/dirty/clean.
It is the one merge-blocking check added, and it is different in kind from the deploy gates: those
redden for reasons unrelated to the change, this reddens only when the PR itself left the lock
stale. Confirmed on its own change — this PR adds `pyyaml` to the dev group, and the check agreed
after re-locking.

**A near-miss worth recording.** The `uv lock --check` step was first inserted between
`- name: Install dependencies` and its `run:`, producing a step with a **duplicate `run:` key**.
`yaml.safe_load` reported *"YAML parses"* — PyYAML silently keeps the last duplicate — so the
syntax check passed while the lock check had been overwritten by `uv sync` and would never have
run. Twenty minutes after registering C-345, the same defect in the same shape: **a parse is not a
verification.** `tests/test_ci_gates.py` now asserts step well-formedness for exactly this.

**And the drill of that guard was itself wrong first.** Its pass criterion was `rc != 0`, which
cannot tell "the guard caught it" from "the test file failed to import" — and the file *was* failing
to import, because `pyyaml` was not a dependency. All four mutations reported CAUGHT while nothing
ran. Re-drilled with `rc == 1` meaning caught and `rc >= 2` meaning error; five mutations, five
genuine catches.

---

## C-345 — the instrument that detects this cluster is a member of it (2026-08-11)

`/register-risk` after #432. Tier 2, and the only entry so far found by watching **my own
verification** rather than the system.

**Twice in one session a failing suite was reported as passing.** First
`uv run pytest -q | tail -2; echo "EXIT=$?"` — a pipeline's status is its *last* element's, so `tail`
returned 0 while pytest had exited 1. Then a backgrounded run's task notification said *"exit code
0"* for the same reason: the command ended in an `echo`. The second was caught only by reading the
output file, and by then the user had already been told the suite was running and would be folded
in. One step from reporting green on red.

**Why it is registered rather than remembered.** The suite is the gate on every story in this epic;
a false green means a defect merges, and per C-343 a `refresh_pipeline.sh` change reaches production
only at the next cron run after a deploy — a further month later still if the deploy is tag-file-only.
The precedent for registering a workflow hazard rather than a code one is C-339, an assistant-authored
command that destroyed a production log.

**A claim was cut from this entry during review, and the cut is worth recording.** The first draft
justified the tier partly on *"two recorded false-readiness incidents that each cost a full day"*.
Those incidents are real and known to the operator — but **nothing in this repository records them**.
A grep of the register, the changelog and every post-mortem returns only the sentence making the
claim. It also attributed "two months in production" to C-343, which says *one* month and never
derives the larger figure. Both were caught by fact-checking the entry against the repo rather than
against memory. Citing evidence a reader cannot find is precisely how a register stops being
checkable, and the same overreach had already shipped inside C-331 in #432 — corrected here too.

**The shape is the cluster's own, which is the uncomfortable part.** C-330 was a nightly no-op
exiting 0. C-337 was a lockfile frozen with no error. C-343 was a deploy that deployed nothing. This
is the same defect in the instrument used to find all three. An epic about mechanisms that report
success while doing nothing spent a week using one.

**Mitigation adopted, and explicitly not a control:** redirect to a file, capture `$?` unpiped, grep
`^FAILED` as a second independent reader. A habit is not machinery — nothing stops the next pipeline
masking a status the same way. The instrument would refuse to report a result it did not obtain
unpiped; proposed for #424.

**Two findings from the same session deliberately not registered.** The guard-narrower-than-the-
property pattern (three versions of `test_heartbeat_secret.py`, each failing green) went to C-336 as
a second addendum — same mechanism, new location. And an unbounded `until … sleep 30` poll that died
on a transient DNS failure was fixed by bounding the loop; a one-line workflow correction with no
consequence, below the register's bar.

---

## C-331 RESOLVED — and the entry's own prescribed fix was the bug (2026-08-10)

Epic #421 Story 2 (#423). The heartbeat URL now reaches `curl` on stdin via `-K -` at all three
ping sites, never as an argv element.

**The correction is the valuable part, again.** C-331 did not merely describe the problem — it
prescribed the fix, in its own body: `printf 'url=%s\n' "$HEARTBEAT_URL" | curl -K -`. Unquoted.
Measured against curl 7.81.0 before shipping it, with a value carrying a stray space:

| form | result |
|---|---|
| `url=%s` | parses `http://h/uuid`, **drops the `/fail`, and sends it anyway** |
| `url = "%s"` | exit 3, nothing sent |

A trailing space or CR — a CRLF-edited `.profile`, a copy-paste — would have turned the **failure**
ping into a **success** ping. Silently. The register's own remedy for a fails-green concern
contained a fails-green defect, and it had sat there unexamined since 2026-07-31 because a
prescribed fix reads like a settled thing. The shipped form is quoted, and the reason is in the
script's comment rather than only here, so it survives the next rewrite.

**The `/proc` claim was drilled with a negative control**, because the issue insisted on it and
because a clean scan otherwise proves only that the scanner is broken. Canary against an unrouted
RFC1918 address, so the request hangs and stays in flight while `/proc` is walked. Control leaked
`curl -fsS --max-time 20 http://.../CANARY-.../fail`; the fix showed `curl -fsS --max-time 20 -K -`
in flight with nothing anywhere carrying the canary, three times, once per ping. A local listener
then confirmed all three paths arrive byte-exact — the server log is the evidence, not curl's exit
code.

**The guard was wrong first, and drilling it is what found that.** `tests/test_heartbeat_secret.py`
initially asserted "no line contains both `curl` and `HEARTBEAT_URL`" — which fails against the
*fixed* script, because `printf … "$HEARTBEAT_URL" | curl …` legitimately puts both on one line.
The property is "`HEARTBEAT_URL` never appears **after** the `curl` token". A guard only ever run
against the state it was written for proves nothing.

**Two stale line citations fixed, and the hole that hid them closed.** ADR-018 cited a line range in
`refresh_pipeline.sh` that had drifted ~55 lines; ADR-051 cited three line numbers of which one had
never been right; C-331's own Location field read `93,163,290` against real lines 112/182/309 — in
an entry whose trigger was *"next edit to this file"*. `tests/test_docs_citations.py` could not see
any of them: its pattern was `\.py:\d+`, **`.py` only**. Widened to `\.(?:py|sh):\d+` and drilled;
those three were the only offenders, so it starts green.

**Also corrected:** `server_operations.md` described "two signals" while listing three, and stated a
24-hour grace where the live check is 48 hours. Its two operator verification commands used the argv
form — running, on the box, the exact exposure this story removes. Replaced with the stdin form,
quoting verified against a local listener before being written down.

**Not live on the server.** #423's note said no server change was required. Per C-343 that is false:
the change reaches production at the first cron run after a deploy, and a further month later if the
deploy is tag-file-only — weeks to months depending on when the next release happens. (This read "two
months from merge" when written; corrected in #433 — C-343 says one month and never derives the
larger figure.)
Recorded rather than quietly assumed, and the issue has been corrected.

**The residual was checked, and it was worse than the concern.** C-331's entry flagged that
`HEARTBEAT_URL` also lives in `~/.profile`. Rather than note it and move on, the operator ran three
commands. `/home/views-deploy/.profile` was mode **644** inside a **751** home, and `test -r` from
`simmaa_prio` returned **readable** — so `UCDP_API_TOKEN`, `ACLED_USERNAME`, `ACLED_PASSWORD`,
`GDL_API_TOKEN` and `HEARTBEAT_URL` had all been readable by three other accounts continuously since
deployment. Not a window. A standing condition. Registered as **C-344**, Tier 2, and fixed the same
session with verification in both directions.

The shape is worth keeping: a Tier 4 story about a ≤10 s exposure surfaced a Tier 2 one about a
permanent exposure, and only because the residual paragraph was treated as a question to answer
rather than a caveat to write down. One hypothesis raised in the same sweep — group-writable
`.local` on the pipeline's `PATH`, which would have been code execution rather than disclosure —
was tested and **killed**: the group has no other members.

**Rotation was raised, and declined.** The question was put to the operator rather than answered
for them: they were readable by more parties than intended for months, and C-322's GDL token was
rotated on weaker evidence. The answer was no — the three accounts belong to known colleagues and
there is no indication any of them read the file.

Recorded with its basis, because the basis is the part that can expire: this rests on *who holds the
accounts*, not on evidence of non-access. No audit record exists that could establish the latter,
and none was consulted. Reasonable on a single-team research host; it would not survive the accounts
being held outside the team. Revisit if a new shell account appears (C-88).

---

## C-317 RESOLVED — the drill that had been pending for weeks (2026-08-10)

Epic #421 Story 6 (#427). **The first entry in the "fails green" cluster closed by observation
rather than by argument**, which is the only way a cluster about untested mechanisms should ever
lose a member.

**What was unverified.** PR #359 added a `/start` ping to `refresh_pipeline.sh` on the theory that
healthchecks.io would flag a run that began and never finished — the OOM-kill case, where `SIGKILL`
bypasses both the `ERR` and `EXIT` traps so neither the success nor the `/fail` ping ever fires.
Nobody had watched that happen. The entry had read *"OPEN pending live grace-timeout drill"* since
July. Closing it on the strength of *the ping is sent* would have been the cluster's own mistake:
the ping firing was never in doubt; what healthchecks.io **does** with a dangling start was.

**Method.** Throwaway check, period 5 minutes and grace 1 minute, so the timeout was observable in
about a minute rather than the production check's 30 days + 48 hours. Production `HEARTBEAT_URL` and
the production check untouched. One `/start`, then nothing.

**Prediction recorded before the ping:** red within ~1 minute, e-mail arrives.

**Observed:** *"…is DOWN (success signal did not arrive on time, grace time passed)"*, **Last Ping
Type: Started**, 03:35:56 +0200. Detection latency for an OOM kill drops from ~32 days to the grace
window. Throwaway deleted.

**Two things found that nobody was looking for.** healthchecks.io's own schedule dialog states the
mechanism outright — *"Grace Time — when a check is late, **or has received a 'start' signal**, how
long to wait to send an alert"* — so the behaviour was documented by the vendor the whole time and
simply never read. Worth sitting with: a week of uncertainty was resolvable by reading a tooltip.

And the sample check repurposed for the drill had sat **grey, never red**, for two months while
permanently overdue, because it had never been pinged. **A check that has never received a ping does
not alert.** A monitor created and never wired up is indistinguishable, from the dashboard, from one
that is fine — which is `monitoring.md` §7 "Silence lies", found by accident rather than by looking.

**Not closed by this.** The status page is still not regenerated on `SIGKILL`, so `status.html`
stays stale after an OOM kill until the next run — that is the serving path, C-338's territory. And
detection is not prevention: C-173 (memory headroom) is what stops the kill.

---

## C-343 — the deploy that wasn't (2026-08-08)

Registered Tier 2 — the first Tier 2 added since C-337, and the only entry in the fails-green
cluster found by **looking at production** rather than by reading the repository.

**How it surfaced.** While sizing the blast radius of a Story 2 (#423) change, the question came up
of when an edit to `refresh_pipeline.sh` actually reaches the server. Reasoning about it produced a
hypothesis; a throwaway git repository tested it; the test said bash buffers the script and never
re-reads it, so shell changes lag one run. That prediction implied the deploy procedure might be
ambiguous, so the operator was asked to run one command on the host. It came back `v1.11.0` — the
tag file. The next command came back `v1.10.0` — the working tree. The third came back
`views_frames-1.0.0.dist-info`.

**The release cut specifically to fix C-337 had been inert on the server for five days,** and the
floor it raised was still the frozen 1.0.0 that C-337 is about. The tag file read correctly. The
pipeline was green. Nothing anywhere had a failure mode that said otherwise.

**A retraction inside the same hour.** On seeing views-frames 1.0.0 the first framing was *"the
first fails-green instance with production consequences."* That was wrong, and checking the diff
before believing it showed why: `git diff v1.10.0..v1.11.0` spans 31 files but touches no `src/` file
and no pipeline script; outside `docs/`, `reports/` and `tests/` it is only `pyproject.toml`,
`uv.lock`, and three GitHub workflows that never run on the host.
Production imports four non-estimator symbols from views_frames. No number was ever wrong, and PyPI
consumers were never exposed, because the published wheel carried the correct floor throughout. The
damage was to what could be *claimed*, not to what was produced. The corrected framing is in the
entry.

**Remediated the same session**, with the operator at the keyboard: the three documented steps ran,
`uv sync` moved views-frames 1.0.0 → 1.10.2 and views-datafactory 1.10.0 → 1.11.0, and
`FeatureFrame` was imported on the host afterwards — because a ten-minor-version jump that nobody
has watched import is a belief, not an observation. The entry stays **open**: nothing prevents
recurrence.

**One method note.** The `uv sync` command was first given as `sudo -u views-deploy sh -c …`, which
does not source `~/.profile`, so `uv` was not on the PATH and it failed. That mistake is already a
recorded lesson in this project. It failed loudly and cost thirty seconds — which is the whole
difference between it and everything else in this cluster.

---

## C-342 — the lockfile nobody can catch being stale (2026-08-08)

`/register-risk` after `/code-review medium` on **#430**, the first story of epic #421.

**One entry registered.** C-342, Tier 3: `uv sync` rewrites `uv.lock` in place whenever
`pyproject.toml` has moved, and `.github/workflows/ci.yml` runs it before every job — so a pull
request whose committed lock disagrees with its committed `pyproject.toml` passes CI, because CI
repairs the lock in its own checkout, tests the repaired version, and discards it. The stale lock
stays in git. Verified by doing it: `uv lock --check` says *"The lockfile at `uv.lock` needs to be
updated"* where `uv sync` silently fixes and proceeds. Added to the **mechanisms that fail green**
cluster, which is now nine.

**Where it came from is the point.** It was not found by looking for it. It surfaced while
drilling the guard for C-337 — the cluster's own rule (*drill every guard by breaking it*) turning
up a defect adjacent to the one being guarded, for the second time in a week.

**It also weakens the guard that found it,** and the entry says so: `test_dependency_floors.py`
reads the committed lock, and only the way the suite happens to be invoked (`uv run` / `uv sync`
refresh first) makes that a real resolution rather than a stale one.

**Deliberately not fixed in #430.** The instrument is `uv lock --check` in CI, and a pytest cannot
substitute — by the time pytest runs, the lock has already been repaired. Proposed for **#424**
(Story 3, gates that run somewhere other than one laptop). Fixing it inside a story scoped to one
test file would have been the scope creep the epic's own conventions forbid.

**C-342 was wrong when first written, and `/review-diff` caught it the same hour.** The entry said
*"CI runs `uv sync` before every job … passes all four jobs."* `ci.yml` has **five** jobs. `docs` runs
bash only and needs no `uv`; `import-enforcement` is gated to `main`. A pull request to
`development` runs `uv sync` in **three**. The claim was not observed — it was inferred from four
`grep` hits, which is the exact move C-336 is about, committed inside an entry describing a
different flavour of the same thing. Corrected, and the `ci.yml:24,42,60,99` citation replaced with
the job names, since C-336's own lesson is that line citations rot. Recorded here rather than
buried, because an entry that was wrong on the day it was written says more about how this project
reasons than a clean one does.

**Six findings from the same review were not registered.** Two were fixed in place in #430 as
defects in its own docstring — a claim that `packaging` is guaranteed by matplotlib, which
`pyproject.toml` itself marks for removal (C-334); and `test_allow_list_has_not_rotted` passing
unconditionally once its allow-list empties, which is the "test that cannot fail" standard the same
file invokes to justify deleting two other guards. Two were documentation-rot observations below
the register's bar after the 2026-08-04 curation cut it from 45 open to 39. Two were refuted on
inspection: a dict-collision path that this project's single `requires-python` and marker-free
dependencies cannot reach, and a `SpecifierSet` ordering claim that is simply wrong — `packaging`
canonicalises to a sorted tuple.

---

## `/review-rr strategic` — curation (2026-08-04)

**C-324 resolved as stale.** It described a live credential in a server log; the token was revoked
2026-08-01 (GDL allows one per account, so issuing the replacement forced it), the leaking harvester
was superseded when the server moved to v1.11.0, and the log itself no longer exists — destroyed by
C-339. Every remediation the entry prescribed had happened. **The register had gone stale in exactly
the way it keeps warning about**, and a reader would have acted on exposure that ended three days
earlier.

**The "fails green" cluster named** — eight open entries (C-317, C-331, C-336, C-337, C-338, C-339,
C-340, C-341) that are symptoms of one root cause: mechanisms that report success while not doing
the thing. Individually small; together they say this project's characteristic failure is *silence,
not error*. The cluster carries a design rule rather than eight separate fixes: absence of an error
is not evidence of success, so any new mechanism needs an answer to "how would I know if this
silently did nothing?" before it ships.

**Five triggers rewritten** — C-332 (was perpetual, "any change to these files"; now names the act
that creates the exposure), C-70, C-72, C-333, and C-339 (which had stated a *rule* where a trigger
belongs).

**Five demoted to tech-debt backlog** following the C-136 precedent: C-46, C-116, C-117, C-147,
C-155 — mechanical, single-file, never fired, and loud rather than silent if they ever do. C-70 and
C-72 were on the demotion list and were kept, because their triggers had just been made concrete;
demoting an entry immediately after making it actionable is incoherent.

**Not registered, per skill rules** — blind spots go in the report, not the register: bus factor (one
person holds every credential, all server access, and the operational knowledge; unnamed across 341
entries), upstream source discontinuation, and whether a past release's grid can still be rebuilt.

Counts: 45 → 39 open, Tier 3 12→11, Tier 4 25→20, struck-through 110→115.

**Method note.** The cluster table first used `| C-317 |` as its leading column, which collides with
the summary-row format, and the repair used `replace(..., 1)` — which hit the *first* match and
silently bolded eight real summary rows. Two edits, both plausible, both wrong, neither raising an
error. The guards caught it. The cluster demonstrated itself during its own authoring.

## C-340 and C-341 registered (2026-08-04)

Two findings from the v1.11.0 close-out that had been acted on but never tracked. Both share the
property that made this whole week's work necessary: **they fail green.**

**C-340 — auto-merge fails silently, two ways.** `gh pr merge --auto --<method>` refuses to change
the method on an already-armed PR and reports nothing; during v1.10.0 that left `squash` armed on a
`development` → `main` promotion, which would have rewritten the release SHAs permanently. Caught
only by reading `auto_merge.merge_method` back. Separately, pushing a follow-up commit to a branch
whose PR has already auto-merged orphans the work — #416 merged the instant CI went green, and two
files were simply not on `development`, with `git push` reporting success. The only signal was
`commits=1` contradicting a remembered second push. Tier 3: recoverable, but live on every PR here.

**C-341 — deploy gates run only where someone types pytest.** The unexamined residual of C-320's own
fix: gates that could not answer in CI were made to skip with a reason, which was right, and the
consequence was that they now assure only whoever runs the suite at the right moment. After v1.10.0
the branch divergence went undetected for four hours and had been silently true after every prior
release. Partially mitigated by `release-topology.yml`; the rest remain local-only. Tier 4.

Skipped as duplicates or out of scope: the unchecked `numpy`/`pyarrow`/`zarr` floors (already inside
C-337 as its open residual), the views-faoapi monitor observations (different repo), and the
four-year-old `gh` (resolved; the residual is the operator's machine). Counts: 339→341 IDs, 43→45
open, Tier 3: 11→12, Tier 4: 24→25.

## C-330 resolved, C-339 registered (2026-08-03)

**C-330 was right, then corrected into being wrong, then confirmed right.** Observed on the server:
the logrotate config rotated `/root/views-datafactory/logs/refresh.log`, a path the pipeline left when
it moved to the service account, and `missingok` made it exit successfully every night for four
months. The file mode was `644` — world-readable, exactly as originally claimed and later downgraded
to "inferred, not observed". The 2026-07-31 retraction found an archived plan saying rotation was
configured, which was true, and concluded the alarm was false. **Existence was never the question;
efficacy was.** Fixed: correct path, `monthly`, `create 0640`, `su views-deploy`, and `missingok`
removed so a wrong path is loud. Verified by dry run.

**C-339 — I destroyed the log while fixing its rotation.** I handed the operator a multi-line
`sudo tee ... <<'EOF'` heredoc to paste; their terminal joined the first two lines, so `tee` took the
log path as a second output file and, running as root, overwrote it. 528 KB → 150 bytes,
unrecoverable — there was no rotated copy, because the rotation being fixed had never run. Lost:
four months of run output. Not lost: provenance ledgers, status page, ping history, git. Tier 3 for
the *mechanism*, not the damage: a root-privileged command whose failure mode is writing to an
unintended path, handed over to be pasted blind. Standing rule adopted — commands given to a human
are one line; multi-line content goes in an editor. Counts: 338→339 IDs, 43 open unchanged,
Tier 3: 10→11, Tier 4: 25→24.

## C-335 resolved, C-338 registered (2026-08-03)

The serving-path monitor is live: Better Stack on the public `status.html`, 3-minute interval,
verified **Up** at ~27 ms with a test alert delivered and read. The unbounded case C-335 was about —
Caddy stops, pipeline keeps succeeding and pinging, nothing ever notices — is closed.

Two qualifications kept in the closure rather than smoothed away: detection is by e-mail, not phone;
and the **freshness half is not in the vendor at all**, because Better Stack gates keyword matching
behind a paid plan. That half became `.github/workflows/serving-freshness.yml` — daily, on GitHub, so
genuinely external. Registered as C-338 (Tier 4: late notice of stale data, not wrong data).

**ADR-051's specification of the content check was itself wrong, and paying would not have fixed it.**
It said to alert when the body "does not contain the healthy marker". The page carries a legend —
`● OK ● Stale ● Missing` — so those words appear on *every healthy page*; the first implementation
reported one of each against a perfectly healthy server and would have opened an issue every day
until someone muted it. Caught by drilling the check against the live page before shipping. The
workflow parses per-cell `title="<status>"` attributes instead. Counts: 337→338 IDs, 43 open
unchanged (one closed, one opened), Tier 2: 3→2, Tier 4: 24→25.

## C-337 registered (2026-08-02)

A loose dependency floor **froze** an estimator version. `views-frames>=1.0` let `uv.lock` pin
**1.0.0**, and `uv lock` keeps an existing pin while it still satisfies the constraint — so every
CI run and local test since June executed against pre-amendment MAP/HDI semantics (`tip_mass` 0.5,
pre-1.2.0 HDI tower, pre-1.3.0 zeroing). views-frames changed the statistics three times in 1.2.0,
1.3.0 and 1.9.0, all shipped MINOR, so nothing looked breaking. **The audit that checked this floor
got it wrong**: it asked "what does this package import?" (four symbols, no estimators), verified
they work at 1.0.0, and stopped. A floor constrains the resolver, not the import list — and the
audit never opened `uv.lock`, which is where the damage was. Same failure class as C-336, committed
inside the audit written about it, one day later; caught by the operator, who knew the estimator
history. Floor raised to `>=1.10.2`, lock moved, guard added. Counts: 336→337 IDs, 42→43 open,
Tier 2: 2→3.

## C-336 registered (2026-08-02)

Full base-docs audit — all 54 ADRs and 34 CICs checked against the code as it exists. Three
drift mechanisms, all fixed: (1) ten `file.py:NNN` citations, three already pointing at blank
lines, all replaced by symbol names; (2) ADR-006/ADR-010 cite `lab_grid/`, a package
**views-metric-lab deleted** in their commit `6e1a34d` — ADR-010 even asserts it "remains as-is
for the lab's own use", a claim about another repo that stopped being true without anything here
failing; (3) a CIC cited a test file that has never existed, hedged with "(if present)" — a claim
qualified into unfalsifiability, which is why nobody ever corrected it. Also written:
`docs/CICs/load_dataset.md`, the public contract per ADR-050, absent while 32 config dataclasses
had contracts — the CICs had been written where writing was cheap, not where dependency was heavy.
**Near-miss recorded:** `audit_data_parity.py` was on the stale list until checked — it exists in
views-models. Deleting it would have been C-330's error committed inside the audit written to catch
it, so the new guard deliberately does not assert that every referenced path exists. Counts:
335→336 IDs, 41→42 open, Tier 4: 23→24.

## C-335 registered (2026-08-01)

**nothing watches the serving path.** The heartbeat answers "did the pipeline run?"; nothing answers "can a consumer read anything?" If Caddy stops serving while the host stays up, the pipeline still succeeds and still pings, so the check stays green while every consumer gets nothing — detected never. Host-death is bounded (~32d: 30d period + 48h grace); Caddy-death is not. Tier 2 because it reports healthy while broken, the shape of views-faoapi's C-50/C-170. ADR-051: keep the push heartbeat (Better Stack has **no `/start`** — verified — so migrating would discard C-317's OOM mitigation) and add an external poll. Counts: 334→335 IDs, 40→41 open, Tier 2: 1→2.

## C-330 corrected (2026-07-31, hours after registering it)

the falsification audit caught my own error: the sweep grepped the repo for logrotate config, found none, and concluded the log was unrotated and growing without bound. `reports/archive/product_development_plan03.md:97,136,177` says rotation was configured on the server on 2026-03-31. **Absence in the repo was read as absence in the world** — the third instance of that failure mode in this repo inside a week (with the "zero secrets in git" audit behind þing-02's Á-1, and ADR-026:97 behind #391). The entry is retitled and narrowed: what survives is that the rotation is documented *only* in an archived March product plan and nowhere in `docs/guides/`, which is why the sweep missed it and the next reader will too; and that the file-mode claim was inferred from the absence of `chmod`/`umask` in scripts, never observed. Counts unchanged.

## Five-angle security sweep (2026-07-31, #388)

seven entries, none urgent, all grounded in file:line. C-327: a Caddy basic-auth password was published in git history (3 commits, ancestors of main, public since 2026-07-27) — **tested live and dead (401)**; residual is a password *pattern*, and the process lesson that the pre-public audit searched code and config but not post-mortem *prose*. C-328: HEAD re-publishes the username the go-public redaction removed. C-329 (Tier 3, highest consequence): the PyPI-publishing job runs unpinned actions while holding OIDC rights — a poisoned wheel needs no secret to leak. C-330: `refresh.log` world-readable and unrotated (`logs/` gitignored same day, closing the accidental-commit path). C-331: HEARTBEAT_URL capability URL on the curl command line. C-332 (Tier 3): redaction incomplete — `_redact_url` ignores URL userinfo, `zarr_path` interpolated raw into 7 messages, netrc exceptions log contents, `BasicAuth`/`_TokenState` reprs. C-333: UCDP's custom auth header survives cross-host redirects. Verified clean: no `.env`/`.netrc`/key ever committed, harvest tokens never in git, heartbeat URL never committed, no CI authenticates to the data server, zero `${{ secrets.* }}`, OIDC-only publishing, no `pull_request_target`, ledgers and zarr attrs carry no URLs. Header counts: 326→333 IDs, 32→39 open, Tier 3: 7→9, Tier 4: 18→23.

## CI enforcement at the platform (2026-07-31)

C-320's recurrence note corrected: the first diagnosis (`;` vs `&&` in the merge chain) was falsified by PR #372, where `gh pr merge --auto --squash` merged with `test` still pending. Real cause: neither `development` nor `main` had branch protection (404 Branch not protected) and repo auto-merge was disabled, so every PR was mergeable on open and `--auto` degraded to a plain merge. Fixed same day: required checks `lint`/`typecheck`/`test` on development, plus `import-enforcement` on main, `enforce_admins: true` on both, PRs required (0 approvals), force-push/deletion off, auto-merge enabled; documented in `docs/guides/publishing_to_pypi.md`. Rule of record: a client-side gate is advisory; enforcement lives in required status checks.

## Epic #376

pandas becomes an output format, not a dependency (2026-07-31). pandas moved to `[project.optional-dependencies]` and matplotlib to the dev group (zero `src/` imports); imports made lazy so `from datafactory_query.defaults import DEFAULT_REMOTE` — a stdlib-only module and 29 of the 35 datafactory imports across views-models — no longer loads pandas; `tests/test_import_purity.py` guards it, and the guard was **observed red** before being trusted. C-325 registered (Tier 4: CI locks pandas 2.3.3 while fresh installs resolve 3.0.5 — mitigated by running the full suite under 3.0.5: 2301 passed, 0 failed, counts identical to the locked run). C-326 registered (Tier 4: the extra gates nothing today — xarray is the sole pandas carrier, verified per-package in a clean venv — so this makes pandas *not imported*, not *not installed*; the `ImportError` paths are unreachable until #381 resolves; REP/CRP condition recorded — one wheel, two audiences). D-42 registered-and-resolved (relocating the pandas adapters to views-pipeline-core: rejected — breaks the published ADR-050 contract, ADR-040/048 semantics belong beside the registry, no reduction in version votes; end state is deletion, not relocation, which #379's file split made cheap). Header counts: 324→326 IDs, 30→32 open, Tier 4: 16→18, disagreements 41→42.

---

## Where the findings came from

Every audit, review, and incident that contributed entries to the register, oldest first.
This list lived on the register's `**Source:**` header line and grew by one item per audit
— 71 entries and 2783 characters by 2026-08-02. The search-window guard's own docstring
named it as a growth vector (*"wide enough to find 'N open concerns' despite Source-line
growth"*), so the header was being defended against this list rather than relieved of it.
Moved here as part of #404; the header keeps a pointer.

- Multi-expert engineering review
- repo assimilation
- falsification audits
- expert code review (Martin
- GoF
- Feathers
- Nygard
- Kleppmann
- Ousterhout
- Hickey
- Beck)
- magic-values compliance audit
- stale-zarr incident 2026-04-24
- pipeline verification audit 2026-04-30
- ACLED integration test review 2026-05-02
- ACLED test review 2026-05-03
- ACLED compilation test review 2026-05-05
- base documentation review 2026-05-07
- ACLED harvester test review 2026-05-07
- GHS-POP harvester test review 2026-05-18
- GHS-POP viewpoint test review 2026-05-19
- PR #53 review 2026-05-20
- GHS-POP memory falsification + expert code review 2026-05-20
- repo-assimilation 2026-05-20
- ADR-031 compliance review 2026-05-21
- harvest caching expert code review 2026-05-21
- PR #59 falsification audit round 2 2026-05-21
- provenance/shapefile expert code review 2026-05-21
- GHS-BUILT-S review-rr triage 2026-05-22
- GHS-BUILT-S coverage parity falsification 2026-05-22
- GHS-BUILT-S visual audit falsification 2026-05-22
- GHS-BUILT-S visual audit run 2026-05-22
- C-190 resolution 2026-05-23
- GHS-BUILT-S merge-readiness falsification 2026-05-23
- pre-merge sprint (C-191/C-192/C-168/C-174) 2026-05-23
- GHS-BUILT-S merge-readiness falsification round 2 2026-05-23
- repo-assimilation v1.2.20 2026-05-24
- tech-debt-cleanup investigation 2026-05-24
- review-rr strategic + prioritize 2026-05-24
- review-base-docs 2026-05-25
- V-Dem test coverage parity falsification 2026-05-26
- V-Dem ADR/guide compliance falsification 2026-05-26
- V-Dem SOLID/package/file-org falsification 2026-05-26
- review-rr strategic curation 2026-05-26
- review-base-docs 2026-05-26
- V-Dem visual audit falsification 2026-05-26
- V-Dem visual audit documentation falsification 2026-05-26
- sprint S4 standalone fixes (C-175/C-129/C-149) 2026-05-27
- merge-readiness falsification (C-222) 2026-05-27
- review-rr strategic curation 2026-05-28
- SHDI review-diff 2026-05-29
- expert code review C-164 2026-05-30
- digest verification expert code review + 3 falsification audits 2026-06-02
- preflight netrc falsification 2026-06-02
- status page understanding falsification 2026-06-04
- status page fix plan falsification 2026-06-04
- ADR-040 scoping 2026-06-05
- test-review area-majority effort 2026-06-05
- review-base-docs area-majority effort 2026-06-05
- review-rr strategic curation 2026-06-06
- pre-deployment audit 2026-06-07
- derived-artifact drift expert-code-review 2026-06-08
- data soundness expert-method-review 2026-06-08
- content-addressed skip investigation 2026-06-09
- pipeline gap audit 2026-06-10
- tech-debt-cleanup pre-deploy 2026-06-10
- test-review deep coverage audit 2026-06-10
- review-rr strategic curation 2026-06-10
- repo-assimilation v1.3.0 2026-06-16
- expert-code-review register-risk 2026-06-18
- test-review v1.4.0 2026-06-24

---

Earlier history: `git log reports/technical_risk_register.md`.
