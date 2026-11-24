# ADR-054: views-datafactory is a Program that Publishes a Self-Describing Artifact, Not a Library

**Status:** Proposed
**Date:** 2026-11-24
**Deciders:** Simon Polichinel von der Maase
**Applies:** ADR-001 (Ontology of the Repository), ADR-011 (Fail Loud), ADR-012 (Four-Layer Data Architecture), ADR-021 (Zarr Export Format), ADR-022 (Tag-Based Deployment Gate), ADR-050 (Consumer Contract Export)

> **This ADR answers a question that fifty-three ADRs left open.** Nothing in this repository
> states whether it is a library that consumers install or a program that serves them. It has been
> both since the server arrived, by accident of order rather than by decision, and the question has
> been re-litigated in conversation roughly once per incident.

> **The decision below is derived, not preferred.** Three evidence sources were consulted and
> nothing else: what is failing now, what has failed before as recorded in the risk register and
> the GitHub issues, and what seven works say: Hohpe & Woolf's *Enterprise Integration Patterns*,
> Newman's *Building Microservices*, Kleppmann's *Designing Data-Intensive Applications*,
> Ousterhout's *A Philosophy of Software Design*, Sculley et al.'s *Machine Learning: The
> High-Interest Credit Card of Technical Debt*, Gebru et al.'s *Datasheets for Datasets*, and
> Nygard's *Release It!* Each is cited by chapter at the point of use. Each claim carries
> its source. Where the three sources agree, the decision follows; where they do not, the
> disagreement is recorded in *Open Questions* rather than resolved by taste.

---

## Context

### What is not working

This repository pays the cost of two integration models simultaneously. It runs a monthly pipeline
on a single host and publishes a 3.1 GB zarr store over HTTP, and it also publishes a Python
distribution to PyPI that consumers install in order to read that store. Nothing decided that both
should exist. The read client was written as a Python function before there was a server, and when
the server arrived the function was not removed.

The cost is not theoretical and it is not evenly distributed between the two halves. It is recorded
in this repository's own register, and it has changed delivered fatality figures twice.

### Evidence class 1 — what is failing now

Established in the session of 2026-11-22 to 2026-11-24.

| Finding | How established |
|---|---|
| Eighteen model runs in a downstream repository spanned two different store builds without anyone noticing. The runs recorded **our client library version** in their manifests as the provenance of the data they read. That version says nothing about the data: the values are compiled by the pipeline, not by the query client. | Reported by the views-models session; the store-build dates and the fix's tag date verified against git and the served store by this session |
| PyPI's latest release is **1.18.1**, while `v1.19.0` and `v1.20.0` are both tagged. Two tagged releases are unpublished, and no consumer noticed, because publication is irrelevant to the numbers. | Checked against the PyPI JSON API and `git tag`, 2026-11-24 |
| The wheel ships **nine** packages. A consumer uses **three**: the query client, the grid config, and the frame adapters. The other six are pipeline internals that no consumer calls. | Checked: `[tool.hatch.build.targets.wheel]` in `pyproject.toml` against the internal imports of `datafactory_query` |
| `load_region_pgids` resolves some arguments from JSON bundled in the wheel and raises for others, reading a **relative** path that cannot exist in an installed environment. Only `global`, `land` and `land_gaul` work from a plain install. | Checked in `regions.py`; already recorded independently as **#590**, filed 2026-11-21 |

### Evidence class 2 — what has failed before

From the risk register and the GitHub issues, open and closed. The entries divide cleanly by which
half of the repository caused them.

**Costs caused by being a library.** Every one is a version-skew cost, and the mechanism is always
that a consumer resolves a version of ours, or ours resolves a version of someone else's, at a
moment nobody chose.

| Entry | Cost |
|---|---|
| **C-365** (Tier 2, fired 2026-11-02) | A frozen lockfile pin in this repository left it the last constraint holding `views-frames` below 3.0.0 for ten weeks. The forecast lane silently resolved the reconciler that loses 2.9–7.3% of fatality mass. A packaging decision here changed delivered fatality figures. |
| **C-337** (resolved, with a 2026-11-02 addendum) | A loose dependency floor *froze* an estimator version for roughly six weeks: `uv lock` keeps an existing pin while it still satisfies the constraint. The guard written to resolve it expires an exemption only when the lock leaves the floor, never when upstream does. Ten weeks, no error. |
| **C-334** (Tier 3) | Removing a runtime dependency from a published library breaks dependents that relied on it transitively. The reasoning that failed — "nothing under `src/` imports it" — is correct for a program and wrong for a library. `pip install --upgrade` never reproduces the failure, because pip does not prune orphaned transitive dependencies. |
| **C-325 / C-326** (Tier 4) | CI tests one pandas major version while a clean consumer install resolves another, and the `[pandas]` extra introduced to prevent this gates nothing, because `xarray` is a required dependency and carries pandas regardless. |
| **#619**, checked 2026-11-21 | Live version skew on a **credential fix**: consumer environments declared `>=1.9.0` while the fix that stopped a netrc credential crossing a redirect landed in 1.13.0. The server being one login away prevented nothing, because the broken code was in the installed wheel. |
| **#587, #586, #583** | The wheel declares `Typing :: Typed` and ships no `py.typed`, so every consumer type-checks against `Any`; and nothing checks that a package is in the wheel's build list, so an omission ships a broken wheel with the suite green. |

**Costs caused by being a program.** Every one is a staleness or identification cost.

| Entry | Cost |
|---|---|
| **C-343** (Tier 2) | Writing the deploy tag is not deploying. The server ran v1.10.0 for five days while every signal said v1.11.0. |
| **#638** (open) | A change merged to `development` lands on **no** run until somebody writes a new tag into the pinned tag file. The source-parity check therefore did not run on the release that introduced it. |
| **C-372** (resolved 2026-11-22) | Nothing compared a published total against the source's own published total. A defect ran four and a half months and was found by an external reader. |
| **#620, #632, #533, #609** (open) | A consumer cannot name which release produced the grid they read, which editorial choices shaped it, or which profile built it. |

The asymmetry is the finding. The library half has twice changed numbers we delivered. The program
half has twice served numbers later than it should have, and has never changed one.

### Evidence class 3 — what the literature says

Every passage below was read in the source text itself during this session, chapter by chapter, and
not relayed from another session's summary. Edition and chapter are named at each citation and
again in full under *References*.

**We already have a name.** Hohpe & Woolf, *Enterprise Integration Patterns*, ch. 2, sets out four
integration styles: File Transfer, Shared Database, Remote Procedure Invocation, and Messaging.
Publishing a file that consumers read is **File Transfer**. Their verdict on it:

> File Transfer achieves the strongest decoupling of any integration style — applications need no
> knowledge of each other's internals and the files become each application's interface — but at
> the cost of timeliness and consistency.

Every program-half cost in Evidence class 2 is a timeliness or consistency cost. They are the
documented price of the style, not evidence that the style was wrong.

**The style is endorsed for exactly our case.** Newman, *Building Microservices*, 2nd ed., ch. 4,
on communication through common data:

> Another major sweet spot for this pattern is in sharing large volumes of data.

We publish a 3.1 GB store monthly. This is the case the pattern is for.

**The literature argues against the library half on precisely the mechanism our register records.**
Newman, ch. 5, verbatim:

> If your use of shared code ever leaks outside your service boundary, you have introduced a
> potential form of coupling.

> The really important point about sharing code via libraries is that you cannot update all uses of
> the library at once. […] So if you are using libraries for code reuse across microservice
> boundaries, you have to accept that multiple different versions of the same library might be out
> there at the same time.

> If you really do need to update that code for all users at exactly the same time, then you'll
> actually want to look at reusing code via a dedicated microservice instead.

The credential fix in Evidence class 2 is the case where we needed to update all users at once and
could not. Newman's own test therefore returns the answer directly.

**And specifically against a client library written by the server's authors**, which is our exact
arrangement — Newman, ch. 5:

> The problem, of course, is that if the same people create both the server API and the client API,
> there is a danger that logic that should exist on the server will start leaking into the client. I
> should know: I've done this myself. The more logic that creeps into the client library, the more
> cohesion starts to break down, and you find yourself having to change multiple clients to roll out
> fixes to your server.

Issue #590 is that leak, already measured: the wheel carries bundled region data and a relative
filesystem path, so region resolution is partly a client-side concern that belongs on the server.

Newman's counter-model is the AWS SDK, and he names why it works:

> These SDKs, though, are written by the wider community, or else by people inside AWS other than
> those who work on the API itself. This degree of separation seems to work […] Part of the reason
> this works so well is that the client is in charge of when the upgrade happens.

Neither condition holds here. The same author writes both halves, and C-365 is the case where the
client was *not* in charge of the upgrade.

**The artifact must carry its own identity.** Kleppmann, *Designing Data-Intensive Applications*,
ch. 4, on encoding and evolution, states the governing fact in four words: **data outlives code.**
A reader's schema and a writer's schema differ, and the schema travelling with the data is what
makes the difference survivable. Gebru et al., *Datasheets for Datasets*, gives the form: a dataset
ships documentation of its motivation, composition, collection, preprocessing, uses, distribution
and maintenance.

**"Something else" is not microservices.** Newman, ch. 1, holds that independent deployability is
the only essential property of a microservice architecture, that the monolith is the sensible
default architectural style, and that microservices are often a bad choice for small teams.
Ousterhout, *A Philosophy of Software Design*, ch. 9, names four distinct complexities that
subdivision adds. Sculley et al., *Machine Learning: The High-Interest Credit Card of Technical
Debt*, records that at most 5% of a mature machine-learning system does machine learning and that
configuration debt commonly exceeds code debt. There is one maintainer with roughly two hours a
week for every server job in the platform. Nothing in the literature supports splitting this
repository into services, and three sources argue against it.

### Why now

Issue **#619** has carried this question since 2026-11-21 without a decision. In the three days
since, the question stopped being architectural: a downstream repository produced a paper's worth
of model runs against two different store builds, because the only provenance a consumer could
record was our library version, which is not provenance at all. The next monthly run is
2026-12-21. A decision taken after it is a decision taken after the same failure can recur.

---

## Decision

**views-datafactory is a program. It publishes one self-describing artifact over HTTP. It is not a
library, and nothing installable from this repository is on the data path.**

Explicitly in scope:

1. **No consumer installs anything from this repository in order to read data.** The artifact on
   the wire is the whole interface. This confirms as governance the decision the operator stated on
   2026-11-22 and extends it from *fetching* to the full data path.
2. **The artifact must be self-describing.** A consumer must be able to determine, from the served
   store alone, which build they are reading and which code produced it. Today `.zattrs` carries
   `source_digest` (a content digest of the assembled grid) and `export_timestamp`; it does not
   carry the pipeline version or the deploy tag. It must.
3. **Anything a consumer genuinely needs that is not derivable from the artifact must be served as
   part of the artifact**, not bundled into a distribution. Region-to-cell resolution (#590) is the
   known instance.
4. **Publication of the Python distribution ceases to be part of the release ritual.** The existing
   distribution is frozen at its current contract — `CONTRACT_VERSION 1.0.0` under ADR-050 — and
   receives no new consumer-facing capability.

Explicitly out of scope:

5. **This is not a decision to delete the distribution.** It cannot be deleted while consumers
   import `load_dataset` and while the wheel carries reference data that is not yet on the wire
   (#590, #589). Freezing it is the decision; retiring it is a later one, conditional on §3.
6. **This is not a decision to become microservices.** No service decomposition, no second repo, no
   per-feature endpoint, no RPC. One program, one artifact, one unattended monthly run. The
   literature in Evidence class 3 argues against the alternative on three independent grounds.
7. **This does not alter ADR-022.** The pinned-tag deployment gate stands; a reviewed tag, not a
   tracked branch, is what reaches the host.
8. **This does not alter ADR-050's contract** for the consumers who hold the wheel today. It
   forbids extending that contract, not honouring it.

---

## Rationale

The decision follows from a single asymmetry in Evidence class 2, which the literature in Evidence
class 3 then explains.

Both halves of this repository have cost us. The two costs are not the same kind. Being a program
has made us serve data later than we should have — C-343, #638, C-372 — and Hohpe & Woolf name
timeliness and consistency as exactly the price of the File Transfer style. That price is payable
inside the style: an artifact that states its own build identity lets the consumer detect staleness
without anyone watching, which is the only kind of check that survives two hours a week.

Being a library has twice changed the numbers we delivered. C-365 moved fatality mass by 2.9–7.3%
in the forecast lane for ten weeks. The credential fix in #619 left a known-broken client in
production consumers while the server was correct. Newman's chapter 5 explains why neither was a
discipline failure: you cannot update all uses of a library at once, so multiple versions are
always live, and the only remedy he offers for the case where you must update everyone at once is
to stop using a library.

So the program half has a documented price that we can pay with machinery, and the library half has
a documented price that we cannot pay at all with one maintainer. That is the whole derivation.

Three further points, each held because a source says so rather than because it is appealing:

- **The artifact, not a client, carries the version.** Kleppmann's "data outlives code" is the
  reason the fix for the 2026-11-24 incident is two fields in `.zattrs` and not a better release
  process. The consumer that recorded our library version was doing the only thing available to it.
- **Minimalism is a constraint, not an aesthetic.** Newman's defence of the monolith and
  Ousterhout's four complexities of subdivision both bear on a repository with one maintainer, and
  they rule out the architecturally fashionable answer.
- **The wheel's remaining contents are a leak, not a feature.** Newman predicted server logic
  creeping into a client library written by the server's authors; #590 is that prediction, measured,
  filed before this ADR was drafted.

---

## Considered Alternatives

### Alternative A: Keep both halves as they are
- **Pros:** Zero work today. C-365's guard exists. Consumers are unbroken.
- **Cons:** Every entry in Evidence class 2's library table remains live, and the mechanism behind
  the 2026-11-24 incident is untouched. Leaves the question open to be re-litigated at the next
  incident, which is the specific failure this ADR exists to end.
- **Reason for rejection:** it is the status quo whose cost Evidence class 2 prices at two
  fatality-figure changes.

### Alternative B: Split the distribution into a thin transport client plus a separate data package
- **Pros:** Closest to Newman's AWS separation; confines version fan-out to the half that changes
  rarely. Listed as option 2 on #619.
- **Cons:** Newman's AWS model works because the client's authors are *not* the server's authors
  and the client controls its own upgrade timing. Neither becomes true by splitting our own package
  in two. It also multiplies release units for one maintainer, against Ousterhout ch. 9.
- **Reason for rejection:** it buys a fraction of the benefit at more than the whole cost.
  **Revisit if** a party outside this project maintains the client.

### Alternative C: Decompose into services with per-concern endpoints
- **Pros:** Removes bundled data from clients entirely; a query endpoint could do subsetting
  server-side.
- **Cons:** Newman ch. 1 holds the monolith to be the sensible default and microservices a poor
  choice for small teams; Ousterhout ch. 9 prices subdivision; Sculley prices the surrounding
  machinery. No source in the library supports it at this scale.
- **Reason for rejection:** the literature argues against it on three independent grounds.
  **Revisit if** the artifact grows past what a consumer can usefully fetch whole.

### Alternative D: Retire the distribution immediately
- **Pros:** Removes the version-pin surface at once. Option 3 on #619.
- **Cons:** #590 and #589 record reference data living only in the wheel; a paper is mid-flight in
  views-models; `load_dataset` is imported today. Immediate retirement breaks live consumers to fix
  a problem that freezing already stops from growing.
- **Reason for rejection:** correct destination, wrong sequence. It is what §3 of the Decision
  makes reachable.

---

## Consequences

### Positive
- The question is settled and citable. Future sessions answer "library or service?" from this
  document instead of improvising, which is the inconsistency this ADR was asked to end.
- The class behind the 2026-11-24 incident closes once §2 is implemented: a consumer can detect a
  stale read from the artifact alone, with nobody watching.
- No new entry of the C-365 / C-337 / C-334 / C-325 family can arise on the data path, because no
  consumer resolves a version of ours to read data.
- Epic #576 gets an answer to its unstated premise. #577 asks whether identity lookup earns a tenth
  package; under this decision it does not — it earns a served file.

### Negative
- Consumers who hold the wheel keep holding it, so the library costs do not vanish today. They stop
  growing; they do not stop.
- Served reference data is new work that only exists because of this decision (§3). Without it the
  wheel cannot retire, so the staged plan has a real unfinished middle.
- A consumer writing its own reader duplicates a few dozen lines of request and decode code in each
  repository. This is accepted deliberately: Newman ch. 5 treats that duplication as the price of
  not coupling across the boundary, and the register prices the alternative higher.
- ADR-050's reasoning is now partly superseded. It saw this cost — it records that requiring a
  consumer to install the wheel "for three strings is not acceptable" — and routed around it with a
  JSON side-channel rather than deciding. That compromise stands for existing consumers and is not
  extended.

---

## Implementation Notes

Nothing in this ADR requires a change to `src/` on acceptance. The two code changes it implies are
small and independently useful:

1. **Add the pipeline version and the deploy tag to the served store's attributes**, beside the
   `source_digest` and `export_timestamp` that `export_zarr.py` already writes. This is §2 and it
   is the remedy for the 2026-11-24 incident. Tracked as **#620** inside epic **#632**.
2. **Have the pipeline compare its pinned deploy tag against the newest release tag and fail loudly
   through the existing heartbeat if it is behind.** This is the #638 class, and it is reported by
   the machine rather than remembered by a person. `refresh_pipeline.sh` already pings `/start`, a
   failure path, and success, so the channel exists.

Then, in order and not before:

3. Move region-to-cell resolution onto the wire (§3), which unblocks #590 and makes the wheel's
   bundled data redundant.
4. Remove the six pipeline-internal packages from the distribution's build list. No consumer
   imports them.
5. Stop publishing on release, once 3 and 4 have landed.

Guardrails against regression:

- The release ritual in the server quick reference must stop naming publication as a step.
- Any proposal to add a consumer-facing capability to the distribution is answered by §4 of the
  Decision, and the proposal becomes a served-artifact proposal instead.
- No check introduced under this ADR may require a human to read a number and compare it by eye.
  ADR-027's residue is the counter-example: an expected count an operator is meant to read off
  stdout, which with two hours a week is equivalent to no check.

---

## Validation & Monitoring

This decision is correct if, after one full release cycle:

- A consumer can name the store build it read using only the served store, and at least one
  downstream repository asserts it the way views-models asserts its cell fingerprint today.
- No new register entry describes a consumer resolving a version of ours at a moment nobody chose.
- The pipeline, not a person, is what reports a deploy-tag gap.

It should be reconsidered if:

- A consumer demonstrates a need that cannot be met by a served file, which would make Alternative B
  or C live again.
- The artifact's self-description proves insufficient to detect a stale read after it exists, which
  would mean the diagnosis in Evidence class 1 was wrong.
- A party outside this project takes over maintenance of a client, which restores both of Newman's
  conditions for the AWS model.

---

## Open Questions

- **Is the distribution eventually deleted, or frozen indefinitely?** This ADR freezes it and does
  not decide. #619's options 2 and 3 remain the live pair, and §3 of the Decision is the gate.
- **Does region resolution become a served file or a separate data-only package?** A data-only
  package has none of the version-skew properties argued against above, because it would carry no
  logic. Not decided here.
- **What are the two new attributes called, and who asserts them?** The views-models session has
  offered to assert them downstream once named. #620 is where that is settled.
- **Does `provenance.json` get served or get removed from the documentation?** It returns 404 on the
  served store today while code and docs still refer to it.
- **Does the monthly artifact need to be fetchable in parts?** Only this would make a query endpoint
  worth its cost, and nothing has asked for it.

---

## References

**This repository.** Issues #619 (the open decision this answers), #620 and epic #632 (a consumer
cannot tell what produced the number they read), #638 (a merged change lands on no run), #590 and
#589 (bundled region data in the wheel), #587, #586, #583 (wheel-quality defects), #577 and epic
#576 (identity lookup), #533 and #609 (the artifact does not disclose its own editorial choices).
Register entries C-365, C-337, C-334, C-325, C-326 (the library costs), C-343, C-372 (the program
costs), C-320 (a permanently red check is indistinguishable from a broken build).

**Prior decisions.** ADR-001 (ontology: sources, compilation edges, consumer nodes), ADR-011 (fail
loud, no stale serving), ADR-021 (zarr export format), ADR-022 (tag-based deployment gate), ADR-050
(consumer contract export, whose compromise this ADR declines to extend).

**Literature.** Cited by chapter above; in full here.

- Hohpe & Woolf, *Enterprise Integration Patterns* (2003), ch. 2 "Integration Styles" — the four
  styles and the price of File Transfer. Also ch. 11 "System Management" on management data
  travelling on separate channels from application data.
- Newman, *Building Microservices*, 2nd ed. (2021), ch. 1 "What Are Microservices?", ch. 4
  "Microservice Communication Styles" (communication through common data), ch. 5 "Implementing
  Microservice Communication" (shared code across boundaries; client libraries; the AWS model).
- Kleppmann, *Designing Data-Intensive Applications* (2017), ch. 4 "Encoding and Evolution" (data
  outlives code), ch. 5 "Replication" (the consistency anomalies conflated as eventual
  consistency).
- Ousterhout, *A Philosophy of Software Design* (2018), ch. 9 "Better Together or Better Apart?".
- Sculley et al., *Machine Learning: The High-Interest Credit Card of Technical Debt* (2014) — glue
  code, data dependencies, configuration debt.
- Gebru et al., *Datasheets for Datasets* (2021) — the form a self-describing dataset takes.
- Nygard, *Release It!* (2007), ch. 17 "Transparency" — a system without transparency cannot survive
  in production.

**Literature not held, and which would strengthen or challenge this decision:**
data-as-a-product and data mesh (Dehghani), consumer-driven contract testing, and a treatment of
semantic versioning as a discipline. Named so they can be acquired: Dehghani, *Data Mesh*
(O'Reilly, 2022); Wilkinson et al., "The FAIR Guiding Principles for scientific data management and
stewardship", *Scientific Data* 3 (2016); Raemaekers et al., "Semantic versioning versus breaking
changes"; and any treatment of consumer-driven contract testing. Every "FAIR" match currently held
is fair scoring rules for forecasts, which is a different subject entirely.
