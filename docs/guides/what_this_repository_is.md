# What this repository is

A reader arriving cold should be able to tell what kind of thing this is
before reading any code. This document says so, and **gives the source for
every term**, so you can disagree with the book rather than with us.

Written 2026-11-27 for issue #654. Minimum viable version: it covers what
this is, what it is not, and the handful of words that keep being used
loosely. It does not try to define everything.

---

## In one sentence

**A batch program that builds a dataset once a month and publishes it as
files over HTTP.** It is not a library, not a database, and not a service you
can call.

## The integration style has a name — in fact two

What this repository does has been a named pattern since 2003. Both names
describe the same arrangement.

**File Transfer** — Hohpe & Woolf, *Enterprise Integration Patterns* (2003),
ch. 2: "Have each application produce files of shared data for others to
consume." The sentence that matters most for us:

> "The files effectively become the interface of each application."

and the property we are trying to get back:

> "Each application can make internal changes freely without affecting other
> applications, **providing they still produce the same data in the files in
> the same format**."

**Communication Through Common Data** — Newman, *Building Microservices*, 2nd
ed. (2021), ch. 4: "one microservice puts data into a defined location, and
another microservice … then makes use of the data." Newman names our case as
the pattern's strongest:

> "Another major sweet spot for this pattern is in **sharing large volumes of
> data**."

We publish a 3.1 GB store and a 29.5-million-row table. That is the sweet
spot, literally.

## We are also a custodian of reference data

Helland (2005), "Data on the Outside versus Data on the Inside", §4:

> "**Reference data** refers to a type of information that is created and/or
> managed by a single service and **published to other services for their
> use.** … For each piece, there is exactly one publishing service."

§4.2 names the role — a "Shared Collection" has one **custodian**. We are the
custodian of the GAUL crosswalk for this platform. Custodianship means
publishing versions, not shipping a reader.

## What this repository is not

Each of these has been assumed at some point, which is why each is stated.

**Not a database.** No query engine, no transactions, no concurrent writers,
no schema server. It plays the *role* of one for downstream code, which is a
different claim.

**Not Remote Procedure Invocation** (Hohpe & Woolf ch. 2). We expose no
procedures. There is nothing to call.

**Not Messaging** (Hohpe & Woolf ch. 2). No channels, no queues, nothing is
pushed. Consumers fetch.

**Not a Shared Database** (Hohpe & Woolf ch. 2) — one writer, many readers.
**But the coupling resembles one**, and that is worth admitting: every
consumer is bound to the store's internal structure. Their warning applies to
us without our having chosen the style:

> "coming up with a unified schema that can meet the needs of multiple
> applications is a very difficult exercise"

**Not microservices** (Newman ch. 1).

**Not a library.** This is ADR-054's decision, and ADR-050 reached it first
on dependency grounds: requiring a consumer to install this for three strings
"is not acceptable (Common Reuse Principle violation)". A wheel is published,
and it is what the operator installs on the server to run the pipeline.

## Words we keep using loosely

| Word | What it means here | Source |
|---|---|---|
| **consumer** | anyone reading our published data. Prefer this over "client" and "downstream", which are used for the same thing. | house convention |
| **operator** | whoever runs the pipeline on the server. The other actor, with different needs. | Martin, *Clean Architecture* (2017), ch. 7 — SRP is about answering to one actor |
| **the interface** | the served files, not the Python API | Hohpe & Woolf ch. 2 |
| **store** | the zarr artifact at `grid.zarr` | ours |
| **build** | one pipeline run's output | ours |
| **release** | a tagged version. The *store* needs one as much as the wheel does. | Martin ch. 13, REP: people "cannot, and will not" reuse a component without release numbers |
| **reference data** | tables that explain the data, published by us as custodian | Helland (2005) §4 |
| **stable data** | data whose interpretation does not change across space and time | Helland (2005) §3.3 |
| **extensive / intensive / static** | whether a feature may be summed across cells | ADR-048 |
| **viewpoint / compilation / assembly** | internal pipeline stages, in order | ours |

"Data factory" is **our** term, not a borrowed one. Said plainly so it is not
mistaken for something with a literature behind it.

## Why any of this matters

Two documents answered the same question in different words and reached
opposite conclusions (#619 and #577), partly because no shared vocabulary
existed. That is the cost this document is meant to remove.

## Where to go next

- **Reading our data:** the README's "Reading our data" section.
- **The decision this rests on:** ADR-054.
- **The plan and its dates:** `reports/roadmap_clean_enough_to_copy.md`.
- **What is still open:** #654 for the full vocabulary, #644 for retirement.
