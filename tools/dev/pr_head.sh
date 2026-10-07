#!/usr/bin/env bash
# tools/dev/pr_head.sh <pr> — make refs/pr/<pr> the PR's CURRENT head before anything tests it (#1034).
#
# session_ci.sh tests refs/pr/<pr>. Fetched once and never again, that ref silently stays on the head of an
# earlier push: on #1031 four consecutive ~20-minute runs tested 1499a8b while the PR had moved on four times,
# and ci_fresh.sh (main-only) still said FRESH. So the PR's head is read from origin (`git ls-remote`, no
# objects) and the ref re-fetched whenever it differs.
#
# Prints the head SHA refs/pr/<pr> now holds, on stdout. Notes go to stderr. Exit 0 ok | 2 refusal:
#   * origin cannot be read (offline, auth): refuse rather than test a ref known to be possibly stale;
#   * origin holds no refs/pull/<pr>/head (not GitHub, a test rig, a deleted PR) and there is no local
#     refs/pr/<pr> either. With a local ref, that ref is used as is and stderr says so.
set -uo pipefail
PR=${1:?usage: tools/dev/pr_head.sh <pr-number>}
[[ "$PR" =~ ^[0-9]+$ ]] || { echo "usage: PR must be a number" >&2; exit 2; }
REMOTE=$(git ls-remote origin "refs/pull/$PR/head") || { echo "cannot read PR $PR's head from origin (git ls-remote failed)" >&2; exit 2; }
REMOTE=${REMOTE%%[[:space:]]*}
LOCAL=$(git rev-parse -q --verify "refs/pr/$PR" 2>/dev/null || true)
if [[ "$REMOTE" =~ ^[0-9a-f]{40}$ ]]; then
  if [ "$LOCAL" != "$REMOTE" ]; then
    git fetch -q origin "+pull/$PR/head:refs/pr/$PR" || { echo "refs/pr/$PR is not the PR's head $REMOTE and re-fetching it failed" >&2; exit 2; }
    echo "refreshed refs/pr/$PR: ${LOCAL:-none} -> $(git rev-parse "refs/pr/$PR")" >&2
  fi
else
  [ -n "$LOCAL" ] || { echo "no refs/pr/$PR here and origin has no refs/pull/$PR/head" >&2; exit 2; }
  echo "origin has no refs/pull/$PR/head: refs/pr/$PR is used as is" >&2
fi
git rev-parse "refs/pr/$PR"
