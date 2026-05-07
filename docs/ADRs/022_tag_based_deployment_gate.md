# ADR-022: Tag-Based Deployment Gate

**Status:** Accepted
**Date:** 2026-04-06
**Deciders:** Simon Polichinel von der Maase, Claude Code
**Extends:** ADR-011 (Fail Loud), ADR-018 (Operational Resilience)

---

## Context

The data pipeline runs monthly on a Hetzner server via cron. Before this ADR, the cron job ran whatever code was checked out on the server — typically the tip of a branch. This meant:

- A broken commit pushed to `development` was one `git pull` away from running on the data server.
- There was no mechanism to pin a specific tested version.
- There was no rollback procedure — only "fix forward."
- A second maintainer pushing to the branch could inadvertently change what the server runs.

The falsification audit (2026-04-01, finding F5) identified this as a soft blocker for v1.1 deployment quality. Risk register item C-98 tracked it as Tier 4, deferred until "before 2nd maintainer pushes."

---

## Decision

The pipeline script (`refresh_pipeline.sh`) reads a **deploy tag** from a file on the server (`~/.views-deploy-tag`) and checks out that exact git tag before running any pipeline steps.

### How it works

```
~/.views-deploy-tag  ──→  git fetch --tags  ──→  git checkout <tag>  ──→  run pipeline
     (operator)              (automatic)           (detached HEAD)        (9 steps)
```

1. The operator writes a tag name (e.g., `v1.1.0`) to `~/.views-deploy-tag`.
2. When the pipeline script runs (via cron or manually), it reads this file.
3. The script fetches tags from GitHub, verifies the tag exists, and checks it out.
4. Git enters **detached HEAD** state — HEAD points directly at the tagged commit, not at any branch. This is the intended state: the server is frozen on a known release.
5. The 9 pipeline steps (0: pre-flight, 1: harvest, 2: consolidate, 3: viewpoint, 4: compile UCDP, 5: compile ACLED, 6: assemble, 7: export, 8: health check) run against that exact code.
6. If the file is missing, empty, or the tag doesn't exist, the script exits non-zero immediately (fail-loud per ADR-011).

### What is detached HEAD?

Normally, `HEAD` points to a branch (e.g., `main`), and the branch points to a commit. When you check out a tag, `HEAD` points directly to the commit — there is no branch in between. Git reports this as:

```
* (HEAD detached at v1.1.0)
  development
  main
```

This is **normal and expected on the server**. It means:
- The server is looking at a frozen snapshot, not a moving branch.
- No `git pull` or `git push` can accidentally change what's checked out.
- The only way to change the running version is to update `~/.views-deploy-tag`.

On developer machines, you work on branches as usual. Detached HEAD is only relevant on the deployment server.

---

## Alternatives Considered

### 1. Branch tracking (`git pull origin main`)

The server tracks a branch and pulls the latest on each cron run.

**Rejected because:** any commit pushed to the branch immediately affects the server. No human review gate between "code merged" and "code running in production." A broken commit is one cron cycle away from corrupting data.

### 2. Docker / container images

Build a Docker image per release, push to a registry, pull on the server.

**Rejected because:** Docker adds operational complexity (image building, registry management, container orchestration) that is premature for a single-server research deployment. The project explicitly defers containerization until multi-server deployment is needed (see `data_serving_guide.md` section 10).

### 3. CI/CD pipeline (GitHub Actions deploy)

A GitHub Actions workflow deploys to the server on tag push.

**Rejected because:** requires SSH credentials in GitHub secrets, introduces a dependency on GitHub's availability for deployments, and adds complexity for a monthly cron job. The manual SSH step (writing one line to a file) is simpler and more auditable.

### 4. Systemd service with version pinning

A systemd unit file specifies the version to run.

**Rejected because:** the pipeline is a batch job (runs monthly, exits), not a long-running service. Systemd is designed for services. Cron is the correct tool for periodic batch execution.

---

## Rationale

### Why a file, not an environment variable?

- Survives reboots (env vars in `.profile` can be lost during OS updates).
- Visible to operators: `cat ~/.views-deploy-tag` shows what will run next.
- Changeable without editing the script or restarting any service.
- Auditable: `ls -la ~/.views-deploy-tag` shows when it was last modified.

### Why tags, not commit SHAs?

- Tags are human-readable: `v1.1.0` vs `e8c0bb3e61e0a08971857ecdd813da8da4a41b39`.
- Tags carry semantic meaning (version numbers imply stability).
- Tags are immutable — once created, `v1.1.0` always points to the same commit.
- `git describe --tags --exact-match` confirms you're on a tagged release.

### Why fail-loud on missing file?

Per ADR-011: the system should crash visibly rather than silently run unknown code. A missing `.views-deploy-tag` file means the operator hasn't configured the deployment — running an arbitrary branch tip would be a silent, dangerous default.

---

## Consequences

### Positive

- **Explicit version control.** The operator decides exactly what runs. No surprises from pushed commits.
- **One-line rollback.** `echo 'v1.0.0' > ~/.views-deploy-tag` reverts to the previous release.
- **Audit trail.** The deploy tag file, git log, and provenance ledger together show what version produced what data.
- **Safe for multiple maintainers.** Two people can push to `development` without affecting the server.
- **No infrastructure dependencies.** No Docker registry, no CI/CD pipeline, no deployment service. Just git tags and a text file.

### Negative

- **Manual step required.** Deploying a new version requires SSH access to the server. There is no push-button deployment from a laptop.
- **Detached HEAD is unfamiliar.** Operators who haven't used git tags before may be confused by `(HEAD detached at v1.1.0)`. This ADR and the deployment guide explain the concept.
- **No automatic deployment.** When a new tag is pushed, the server doesn't pick it up until the next cron run (or manual trigger). This is by design — automatic deployment would reintroduce the "pushed code runs immediately" problem.

---

## Deployment Procedure

**Deploy a new version:**

1. On your laptop: `git tag v1.2.0 && git push --tags`
2. On the server: `echo 'v1.2.0' > ~/.views-deploy-tag`
3. Wait for cron (21st of month) or run manually

**Roll back:**

1. On the server: `echo 'v1.0.0' > ~/.views-deploy-tag`
2. Run the pipeline manually or wait for cron

**Verify:**

```bash
cat ~/.views-deploy-tag                    # configured version
git describe --tags --exact-match          # checked-out version
tail -5 logs/refresh.log                   # last run output
```

Full operational procedures are in `docs/guides/hetzner_deployment_guide.md`, section "Deployment and releases."

---

## References

- ADR-011 (Fail Loud, No Stale Data Serving) — justifies fail-loud on misconfiguration
- ADR-018 (Operational Resilience Policy) — operator-mediated bounded staleness
- `scripts/refresh_pipeline.sh` lines 76-98 — implementation
- `reports/technical_risk_register_resolved.md` C-98 — risk that motivated this ADR
- `docs/guides/hetzner_deployment_guide.md` — operational procedures
- `docs/guides/data_serving_guide.md` section 9 — conceptual explanation
- Kleppmann & Riccomini, *Designing Data-Intensive Applications*, 2nd ed., O'Reilly 2026:
  - Ch.8 pp.274-276: Single-node systems should be deterministic — either fully functional or entirely broken
  - Ch.10 p.397: Immutable inputs — batch jobs should never modify their input
  - Ch.10 p.413: Atomic output replacement — write to temp, rename into place
  - Ch.12 pp.524-526: Integrity over timeliness — immutability enables recovery from bugs
