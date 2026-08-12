# Publishing `views-datafactory` to PyPI

A practical runbook for releasing this package, modelled on the views-frames /
views-reporting routine. Written to be followed **solo, cold, months later** —
every command is copy-paste-able. If you only need to ship a routine update,
the cheat sheet is enough.

> Build tooling: **hatchling + uv** (see `pyproject.toml`, CLAUDE.md). Release
> automation: `.github/workflows/publish_package.yml` (Trusted Publishing / OIDC).
> Release ritual: feature branch → PR → development → version bump →
> development→main PR → tag → GitHub Release (which triggers the publish).

---

## What is special about this package (read once)

| Thing | What | Why it matters |
|---|---|---|
| **One project, nine packages** | The single `views-datafactory` wheel bundles all nine `datafactory_*` packages (`provenance`, `http`, `priogrid`, `harvester`, `consolidation`, `viewpoint`, `compilation`, `adapters`, `query`) | `pip install views-datafactory` makes all of them importable. There are no per-layer PyPI projects. |
| **Code only, never data** | Wheel = `src/` packages; sdist `include = ["/src"]`. No `data/`, `docs/`, `reports/`, `tests/` | The package leaks nothing. Data access stays netrc-gated on the data server (see `credential_setup.md`). |
| **Versions are write-once** | Once `X.Y.Z` is on PyPI it can never be re-uploaded (only "yanked") | Always **bump the version first**. For repeated TestPyPI rehearsals use a throwaway like `1.9.0.dev1`. |
| **uv + hatchling, NOT poetry** | Build backend is `hatchling.build`; tooling is `uv` | Use `uv build` / `uv publish`. Do not copy the legacy Poetry workflows from older views repos. |
| **Consumers pin floors** | House convention: `views-datafactory>=X.Y.Z`, never `git+...@development` | The consumer contract (ADR-050) has a version floor that only a release pin can enforce. |

---

## TL;DR — release an update (the automated way)

Normal releases are published **by CI** when you publish a **GitHub Release** — you do
**not** run `uv publish` by hand. Auth is PyPI Trusted Publishing (no token); see
`.github/workflows/publish_package.yml`.

```bash
# 1. bump the version per the house release ritual (bump branch -> PR -> development,
#    then development -> main PR). You can NEVER reuse a published version.

# 2. (optional, wise for big changes) rehearse on TestPyPI first — see §A

# 3. tag and cut the GitHub Release FROM main — the Release triggers the publish workflow:
git checkout main && git pull --ff-only
git tag vX.Y.Z && git push origin vX.Y.Z    # if not already tagged by the ritual
gh release create vX.Y.Z --target main --title "views-datafactory X.Y.Z" --notes "what changed"

# 4. confirm: Actions tab shows "Publish Package" green, then
#    https://pypi.org/project/views-datafactory/

# 5. BACK-MERGE main into development — do not skip, see below
gh pr create --base development --head main --title "chore: sync main back into development after vX.Y.Z"
# merge it as a MERGE COMMIT, never squash
```

The workflow guards the version (must beat PyPI), `uv build`s, and `uv publish`es via
Trusted Publishing — **no token needed**. First-ever setup requires the one-time PyPI
trusted-publisher config — see Prerequisites.

---

## Branch protection — why a merge can refuse you

Since 2026-07-31 both long-lived branches are protected, and **admins cannot bypass**
(this is deliberate: see C-320 in the risk register — two merges landed with CI still
pending because nothing at the platform level said no).

| Branch | Required checks | Other |
|--------|-----------------|-------|
| `development` | `lint`, `typecheck`, `test` | PR required (0 approvals), no force-push, no deletion, admins included |
| `main` | `lint`, `typecheck`, `test`, `import-enforcement` | same |

`import-enforcement` is required on `main` only — its job-level
`if: github.base_ref == 'main'` in `.github/workflows/ci.yml` means it merely reports
*skipped* on development PRs.

Consequences for the release ritual: the bump PR into `development` waits on three
checks, the `development` → `main` PR waits on four (drilled 2026-07-31 — all four do
report, and `--admin` does not get past them), and neither can be forced through.
Creating and pushing a tag (`git push origin vX.Y.Z`) and the Release-triggered publish
workflow still work normally.

Tags carry their own rule: **"Release tags are immutable"** blocks *deletion* and
*update* of `refs/tags/v*`, with no bypass. Create as many new version tags as you like;
you cannot move or delete one that has been published. This matches PyPI, where a
version number can never be reused.

Merge a PR with `gh pr merge <n> --auto --squash` — repo-level auto-merge is enabled, so
this arms and GitHub merges the moment the checks go green. Do not babysit CI in a shell
loop: a watcher that dies on a network hiccup looks exactly like a watcher that saw
green, which is how C-320 recurred.

**Break-glass** (CI provider outage, or a required check that can never report). Lift,
act, restore immediately — the API leaves an audit trail:

```bash
gh api -X DELETE repos/views-platform/views-datafactory/branches/<branch>/protection
# ... do the thing, then restore from the table above:
gh api -X PUT repos/views-platform/views-datafactory/branches/<branch>/protection \
  --input protection.json
```

```json
{
  "required_status_checks": {"strict": false, "contexts": ["lint", "typecheck", "test"]},
  "enforce_admins": true,
  "required_pull_request_reviews": {"required_approving_review_count": 0,
    "dismiss_stale_reviews": false, "require_code_owner_reviews": false},
  "restrictions": null,
  "required_linear_history": false,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "required_conversation_resolution": false
}
```

(For `main`, add `"import-enforcement"` to `contexts`.)

---

## Work orphaned on a merged branch — detected, not prevented

A pull request auto-merges the instant CI goes green. Push a follow-up commit and it lands on a
branch with no open PR: `git push` reports success and the work is simply not on `development`.
That is C-340 mechanism 2, and it has happened twice — #416, and again on #437 while #437 was
fixing it.

**There is no client-side guard, deliberately.** A pre-push hook was written four times and
abandoned; each version was defeated by a different property of the environment. A client check
races GitHub's asynchronous branch deletion, which is a property of the system rather than a bug to
iterate out. The register entry for C-340 records all four so nobody rebuilds them.

**It is not yet running.** GitHub executes a `schedule` trigger from the **default branch only**, and
this repository's default branch is `main`. The check lands on `development`, so the 06:00 cron goes
on running `main`'s copy until the next release promotion carries it across (C-350). Until then,
trigger it by hand:

```bash
gh workflow run release-topology.yml
```

**What it checks, once live.** `delete_branch_on_merge` is on, so a branch normally disappears when
its pull request merges. `release-topology.yml` therefore asks one question of every remote branch:
**is there an open pull request for it?** If not, it says so, and folds the branch into the same
tracking issue as the other release-hygiene checks.

That is deliberately blunter than "is this work orphaned". A first version tried to establish
orphan-ness properly — matching the merged pull request, comparing head SHAs, counting commits
beyond it — and two review rounds found fifteen defects in it, each from a different property of
git, `gh`, or GitHub. Precision there requires inferring state we cannot see. This version reports a
branch you pushed before opening its PR, which is not really a false positive: it is a branch with
work on it and no route to `development`.

**Clearing it takes one command, either way:**

```bash
gh pr create --base development --head <branch>
```

```bash
git push origin --delete <branch>
```

If a branch is already gone but its work never reached `development`, recover it the way #417 did —
cherry-pick onto a new branch and open a pull request. Both real incidents were recovered inside an
hour.

## Arming auto-merge — use the script, not `gh pr merge`

```bash
scripts/arm_automerge.sh <pr-number> <merge|squash|rebase>
```

`gh pr merge --auto --<method>` on an **already-armed** PR silently refuses to change the method. It
prints nothing and exits 0. During v1.10.0 a `development` → `main` promotion was armed `squash`,
re-armed with `--merge`, and stayed `squash` — caught only by reading the value back. **A squash onto
`main` rewrites the release SHAs** and permanently breaks the ancestry the back-merge maintains; it
would not have surfaced until a later release diffed against a base that never existed.

The script uses the GraphQL disable/enable pair, which does honour the method, then **reads the
method back and exits non-zero if it disagrees**. Reading back is the point; arming is the easy part.

## Prerequisites (one-time setup) — Trusted Publishing

The release workflow authenticates with **Trusted Publishing (OIDC)** — there is **no
stored token**. A project owner enables it **once** on PyPI.

**For the first-ever release (project does not exist on PyPI yet), use a _pending_
publisher** (PyPI lets you trust a publisher for a project that does not exist yet;
the first OIDC publish then creates the project):

> PyPI → your account → **Publishing** → **Add a pending publisher (GitHub)**:
> - **PyPI Project Name:** `views-datafactory`
> - **Owner:** `views-platform`  ·  **Repository:** `views-datafactory`
> - **Workflow name:** `publish_package.yml`  ·  **Environment:** *(leave blank)*

After the first release creates the project, the same entry appears under the project's
**Settings → Publishing** as a normal trusted publisher. Until this is configured, the
workflow's publish step fails with an auth error — that's the only gap between merging
the workflow and it working.

### Creating an API token (for the TestPyPI rehearsal §A)

TestPyPI (https://test.pypi.org) is a **separate account with a separate token** from
real PyPI — a TestPyPI token gets a `403` on real PyPI and vice-versa.

1. Log in at test.pypi.org. Click your **username** (top-right) → **Account settings**.
2. **API tokens** → **Add API token**. Name it e.g. `views-datafactory-rehearsal`.
3. **Scope:** "Entire account" for a first-ever upload (PyPI cannot scope to a project
   that does not exist yet). **Create token**, copy it — shown once only.

🔒 Paste the token **only** into your own terminal — never into a chat, PR, or commit.
Prefer `export UV_PUBLISH_TOKEN=…` (with a leading space to skip shell history) over
`--token` on the command line.

---

## A. TestPyPI dress rehearsal (optional, recommended for big releases)

Use a **throwaway version** so the rehearsal never burns a real version number:
edit `[project].version` to e.g. `1.9.0.dev1` locally, do **not** commit it.

```bash
rm -rf dist && uv build
uvx --from twine twine check dist/*            # both files must say PASSED

# upload to TestPyPI (your terminal; token via UV_PUBLISH_TOKEN — never in chat)
uv publish --publish-url https://test.pypi.org/legacy/ dist/*

# clean-room install back (TestPyPI for this pkg, real PyPI for the dependencies)
uv venv --clear --python 3.12 /tmp/tp-check && source /tmp/tp-check/bin/activate
uv pip install --index-url https://test.pypi.org/simple/ \
               --extra-index-url https://pypi.org/simple/ views-datafactory
python -c "from datafactory_query import load_dataset, CONTRACT_VERSION; print('OK', CONTRACT_VERSION)"
deactivate && rm -rf /tmp/tp-check

# afterwards: revert the local version edit (git checkout -- pyproject.toml)
```

> The two index URLs are both required — TestPyPI only hosts *your* package; numpy,
> pandas, etc. live on real PyPI.

---

## B. Break-glass — manual first upload (if not using a pending publisher)

```bash
git checkout main && git pull --ff-only
rm -rf dist && uv build && uvx --from twine twine check dist/*
uv publish dist/*        # UV_PUBLISH_TOKEN = a REAL-PyPI token
curl -s https://pypi.org/pypi/views-datafactory/json | \
  python3 -c "import sys,json;d=json.load(sys.stdin)['info'];print(d['name'],d['version'])"
```

After the first manual upload, switch to the automated path for every future release,
and delete the over-privileged "entire account" token from your PyPI account settings.

---

## C. Future updates (the repeatable loop — automated)

0. **Credential review check** — is anything in ADR-026 §7 past its review date?

   ```bash
   date -I    # compare against the "Next review" column
   grep -A8 "### 7. Every credential" docs/ADRs/026_credential_management.md
   ```

   If a date has passed: rotate the credential, then move the date. **Moving the date without
   rotating is the failure this check exists to prevent** — so if you are about to do that, write
   why in the register instead.

   This lives here, and not in the test suite, on purpose (#392). A test can only read a date
   someone typed; it cannot see whether a credential was rotated, and its cheapest green path
   would be editing the date. It would also block every merge on a calendar event, with no admin
   override — C-320's lesson. A release is a deliberate, low-frequency moment where a human is
   already paying attention, which is what the check actually needs.

1. **Bump `version`** in `pyproject.toml` via the house release ritual (bump branch →
   PR → development; development → main PR). SemVer; you cannot reuse a published version.
2. (Optional) rehearse on TestPyPI (§A) with a throwaway `X.Y.Z.dev1`; revert before merge.
3. **Tag and cut the GitHub Release from `main`** — triggers `publish_package.yml`:
   ```bash
   gh release create vX.Y.Z --target main --title "views-datafactory X.Y.Z" --notes "what changed"
   ```
4. **Verify:** Actions → *Publish Package* green, then https://pypi.org/project/views-datafactory/.
   Verify by **installing the published artifact into a clean venv**, not by reading a green tick.
5. **Back-merge `main` into `development`** — the step that is easiest to skip and was skipped
   after every release before v1.10.0:
   ```bash
   gh pr create --base development --head main \
     --title "chore: sync main back into development after vX.Y.Z"
   # merge as a MERGE COMMIT — never squash
   ```

### Why step 5 exists (do not delete it again)

Promoting `development` → `main` through a PR creates a **merge commit on `main` that does not
exist on `development`**. A protected branch offers merge-commit, squash, or rebase; squash and
rebase rewrite the release SHAs, so merge-commit is the only acceptable option — and it always
diverges by exactly one commit.

Left unhealed, the divergence accumulates: `git log main..development` counts work that already
shipped, and the next release's diff starts from a base that no longer reflects reality.
`tests/test_falsification_deploy_v160_r2.py::TestDF1MergeTopology` asserts the invariant.

**Squashing step 5 defeats it entirely** — a squash creates yet another commit that is not `main`,
so `main` still is not an ancestor.

Detection is automated by `.github/workflows/release-topology.yml` (display name **Release
hygiene** since 2026-08-11 — the filename is kept so run history and existing citations stay
valid). It runs on every published release and daily, with full git history, and opens **one**
tracking issue covering everything it finds.

It checks more than topology now (#424): the deploy gates that used to run only where someone typed
`pytest` — remote stale release branches, issue hygiene, and the conflict-free back-merge — run
there too, with `GH_TOKEN` so the `gh`-dependent one can answer instead of skipping.

Two gates deliberately do **not** run there, and the reasons matter more than the coverage number:

- **Local-clone branch hygiene** skips on CI. A fresh runner has one local branch, so it would pass
  without inspecting anything — a green tick claiming coverage it does not have.
- **version-not-already-tagged** is `xfail`, so it cannot fail a suite anywhere. #425 owns that.

None of it runs in the PR test job — that would make every PR red between a release and its
back-merge, which is C-320's permanently-red CI all over again. The one merge-blocking check added
alongside is `uv lock --check` in `ci.yml`, and it is different in kind: it reddens only when the
pull request itself left `uv.lock` stale, which is that PR's own fault and fixable inside it.

Merged branches now delete themselves (`delete_branch_on_merge`), so no cleanup step is needed;
eleven stale branches had accumulated before that was switched on.

> Under the hood: `release: published` → `permissions: id-token: write` mints an OIDC
> token → PyPI checks the GitHub claim against the trusted publisher → upload. The version
> guard fails the run if `[project].version` isn't higher than what's on PyPI, so "forgot
> to bump" is a loud error, not a wasted version.

> **This guide is the only home for the release ritual.** `hetzner_deployment_guide.md` used to
> carry a second copy that prescribed `git merge development --ff-only` and
> `git push origin development`; branch protection made both impossible in 2026-07-31 and nobody
> noticed, because the two copies had drifted apart. That guide now owns the server only (#402).

---

## Troubleshooting

| Symptom | Cause → fix |
|---|---|
| `403 Forbidden` on the automated publish | Trusted publisher not configured (or name mismatch). Re-check Prerequisites (owner `views-platform`, repo `views-datafactory`, workflow `publish_package.yml`). |
| `400 … File already exists` | That version is already uploaded — **versions are write-once**. Bump `version` and rebuild. |
| Version guard fails the run | `[project].version` ≤ current PyPI version. Bump it. |
| `twine check` fails on metadata | Stale build — `rm -rf dist && uv build` and re-check. |
| TestPyPI install can't resolve numpy/pandas | Missing `--extra-index-url https://pypi.org/simple/`. |
| Release created but no workflow run | The Release must be **published** (not draft); workflow triggers on `release: published`. |

---

## Provenance

- This guide and `.github/workflows/publish_package.yml` mirror the views-frames
  routine (`views-frames/docs/guides/publishing-to-pypi.md`), adapted: Python floor
  3.12, nine bundled packages, and the code-only wheel/sdist guarantee.
- First exercised by the `v1.9.0` release (2026-07) — the first PyPI publish of this
  project.
