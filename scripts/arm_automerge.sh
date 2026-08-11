#!/usr/bin/env bash
# Arm auto-merge on a pull request, then READ THE METHOD BACK (C-340).
#
# WHY THIS EXISTS
# `gh pr merge --auto --<method>` on an ALREADY-ARMED pull request silently
# refuses to change the method. It prints nothing and exits 0. During v1.10.0
# a development -> main promotion was armed `squash`, re-armed with `--merge`,
# and stayed `squash`. A squash onto main rewrites the release SHAs and
# permanently breaks the ancestry the back-merge maintains — it would not have
# surfaced until a later release diffed against a base that never existed.
#
# The GraphQL disable/enable pair DOES change the method. So: disable, enable
# with the method wanted, then read it back and fail if it disagrees. Reading
# back is the whole point; arming is the easy part.
#
# Usage:   scripts/arm_automerge.sh <pr-number> <merge|squash|rebase>
# Example: scripts/arm_automerge.sh 431 squash

set -euo pipefail

usage() { echo "usage: $0 <pr-number> <merge|squash|rebase>" >&2; exit 2; }
[ $# -eq 2 ] || usage

pr=$1
method=$(printf '%s' "$2" | tr '[:lower:]' '[:upper:]')
case "$method" in MERGE|SQUASH|REBASE) ;; *) usage ;; esac

command -v gh >/dev/null 2>&1 || { echo "gh not installed" >&2; exit 2; }

repo=$(gh repo view --json nameWithOwner --jq .nameWithOwner)
owner=${repo%%/*}
name=${repo##*/}

node=$(gh api graphql -f query='
  query($owner:String!, $name:String!, $pr:Int!) {
    repository(owner:$owner, name:$name) {
      pullRequest(number:$pr) { id state autoMergeRequest { mergeMethod } }
    }
  }' -F owner="$owner" -F name="$name" -F pr="$pr" \
  --jq '.data.repository.pullRequest | "\(.id)\t\(.state)\t\(.autoMergeRequest.mergeMethod // "none")"')

id=$(printf '%s' "$node" | cut -f1)
state=$(printf '%s' "$node" | cut -f2)
current=$(printf '%s' "$node" | cut -f3)

if [ "$state" != "OPEN" ]; then
    echo "PR #${pr} is ${state}, not OPEN — refusing to arm." >&2
    exit 1
fi

echo "PR #${pr}: currently armed=${current}, requested=${method}"

# Disable first. `gh pr merge --auto` would no-op here; the disable/enable
# pair is what actually changes an already-armed method.
if [ "$current" != "none" ]; then
    gh api graphql -f query='
      mutation($id:ID!) {
        disablePullRequestAutoMerge(input:{pullRequestId:$id}) {
          pullRequest { number }
        }
      }' -F id="$id" >/dev/null
fi

gh api graphql -f query='
  mutation($id:ID!, $method:PullRequestMergeMethod!) {
    enablePullRequestAutoMerge(input:{pullRequestId:$id, mergeMethod:$method}) {
      pullRequest { number }
    }
  }' -F id="$id" -F method="$method" >/dev/null

# THE POINT OF THE SCRIPT. Everything above can succeed while the method is
# something else; only this can tell you.
actual=$(gh pr view "$pr" --json autoMergeRequest \
           --jq '.autoMergeRequest.mergeMethod // "none"')

if [ "$actual" != "$method" ]; then
    cat >&2 <<EOF

  MISMATCH — auto-merge is NOT armed the way you asked.

    requested : ${method}
    actual    : ${actual}

  Do not assume the command worked. This is C-340 mechanism 1: the arming
  call can report success and leave the previous method in place. Fix it
  before the PR merges — a squash onto main rewrites the release SHAs and
  permanently breaks the ancestry the back-merge maintains.

EOF
    exit 1
fi

echo "verified: PR #${pr} auto-merge armed ${actual}"
