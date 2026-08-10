#!/usr/bin/env bash
# tools/dev/ci_fresh.sh <pr> [<head-sha>] — is PR <pr>'s stored sandboxed-CI verdict still valid against the CURRENT origin/main?
#
# tools/dev/session_ci.sh tests the PR head MERGED with the origin/main it saw, and records that trunk SHA as
# "main" in .git/session-ci/ci/<pr>.json (same SESSION_CI_DIR default as that script). The verdict says nothing
# about a main that has moved since: #476 was a red trunk from two PRs that were each green against the main of
# their own run and collided semantically once both landed (a textually clean merge; GitHub called it mergeable
# too). So the tick's merge rule (#487, .github/prompts/tick.md §2, docs/process/AUTONOMY.md §12c) is: merge only
# when the JSON for the exact head says pass AND this helper says FRESH right before the merge; STALE -> re-run
# session_ci.sh (merges serialise behind CI runs; reviews stay parallel, they are diff-scoped).
# Tolerated drift = what cannot change a gate's outcome: files ADDED or MODIFIED under docs/**, except the docs
# files shard tests open for content (SHARD_READS: the certification ledger and rendered matrix — tests/test_router.py,
# test_probe_batch.py, test_frontdoor_manifest_pin.py; AUTONOMY.md — needles in tests/test_techlead.py; the list is
# pinned against the shard's real docs/ reads by tests/test_ci_fresh.py). A docs DELETION is drift too:
# src/rvt/frontdoor/matrix.py cites docs/inbox records by existence. So is a docs file ADDED on main whose name
# collides, compared lower-cased, with a path the PR itself adds: the same name is an add/add conflict, and case-only
# twins are the one cross-file law of tools/dev/check_portable_paths.py, so portable_paths would redden only after the
# merge (#496); if main added docs files and the recorded head is not in this clone, that cannot be ruled out — STALE
# too. Anything else is STALE. A filter or interpreter failing on the way is "cannot judge", never FRESH.
# With <head-sha> (what `git ls-remote` says the PR head is right now) it also refuses a JSON computed for another
# head or whose verdict is not pass — so one call is the whole pre-merge check of the CI side.
#
# Trusted side only: git plumbing on THIS checkout (main, plus the file NAMES the recorded PR head adds — the same
# names-only reading session_ci.sh's portable_paths step does) + a stdlib read of our own JSON. It never checks
# out, imports or executes anything from the PR. Needs git, python3, awk (POSIX: mawk, gawk and busybox agree), and
# network to `git fetch origin main`.
# Prints one line. Exit 0 FRESH | 4 STALE (main moved under the verdict, or the recorded main is unknown here) |
# 5 the JSON is for another head / not a pass | 3 MISSING (no JSON, or one from before "main" was recorded) |
# 2 bad PR number / cannot judge (fetch or diff failed) — every non-zero exit means "do not merge on this verdict".
set -uo pipefail
SHARD_READS='^docs/(coverage/|product/PERMUTATION-MATRIX[.]md$|process/AUTONOMY[.]md$)'   # [.] not \.: gawk warns on "\." in a -v string and reads it as "." (#496)
PR=${1:?usage: tools/dev/ci_fresh.sh <pr-number> [<head-sha>]}; WANT=${2:-}
[[ "$PR" =~ ^[0-9]+$ ]] || { echo "usage: PR must be a number" >&2; exit 2; }
REPO=$(cd "$(dirname "$0")/../.." && pwd)          # the trusted checkout this script lives in (main)
S=${SESSION_CI_DIR:-$REPO/.git/session-ci}; OUT=$S/ci/$PR.json
cd "$REPO" || exit 2
[ -f "$OUT" ] || { echo "MISSING $OUT (no CI verdict stored for PR $PR: run tools/dev/session_ci.sh $PR)"; exit 3; }
read -r WAS HEAD VERDICT < <(python3 -I -c 'import json,sys; r=json.load(open(sys.argv[1])); print(*(r.get(k) or "-" for k in ("main","head","verdict")))' "$OUT" 2>/dev/null)
[[ "$WAS" =~ ^[0-9a-f]{40}$ ]] || { echo "MISSING \"main\" in $OUT (a verdict from before #487: re-run tools/dev/session_ci.sh $PR)"; exit 3; }
if [ -n "$WANT" ]; then
  [ "$HEAD" = "$WANT" ] || { echo "WRONG-HEAD json=$HEAD now=$WANT (the stored run is for another head: run tools/dev/session_ci.sh $PR)"; exit 5; }
  [ "$VERDICT" = pass ] || { echo "NOT-PASS verdict=$VERDICT for head $HEAD (nothing to merge on)"; exit 5; }
fi
git fetch -q origin main || { echo "cannot judge PR $PR: git fetch origin main failed (was=$WAS)"; exit 2; }
NOW=$(git rev-parse --verify -q origin/main) || { echo "cannot judge PR $PR: no origin/main"; exit 2; }
[ "$WAS" = "$NOW" ] && { echo "FRESH main=$NOW"; exit 0; }
git cat-file -e "$WAS^{commit}" 2>/dev/null || { echo "STALE was=$WAS now=$NOW changed=? ($WAS is not in this clone: main rewritten, or a JSON from another checkout)"; exit 4; }
DRIFT=$(git diff --name-status --no-renames "$WAS" "$NOW" --) || { echo "cannot judge PR $PR: git diff $WAS $NOW failed"; exit 2; }
# Everything below fails CLOSED: a filter/interpreter that errors is "cannot judge" (exit 2), never an empty list read as FRESH.
name3() { awk 'BEGIN {n=0; s=""} length($0) {n++; if (n<=3) s=s (n>1?",":"") $0} END {if (n>3) s=s ",…"; print s}'; }   # paths, one per line -> first three named, the rest counted as an ellipsis (length, not NF: a name made of blanks still counts)
BLOCK=$(awk -F'\t' -v reads="$SHARD_READS" '!($1 ~ /^[AM]$/ && $2 ~ /^docs\// && $2 !~ reads) {print $2}' <<<"$DRIFT" | name3) || { echo "cannot judge PR $PR: drift filter failed"; exit 2; }   # every path that is NOT tolerated drift
[ -n "$BLOCK" ] && { echo "STALE was=$WAS now=$NOW changed=$BLOCK -> re-run tools/dev/session_ci.sh $PR"; exit 4; }
ADDS=$(awk -F'\t' '$1=="A" {print $2}' <<<"$DRIFT") || { echo "cannot judge PR $PR: drift filter failed"; exit 2; }   # docs files main ADDED: harmless unless the PR adds the same name or a case-twin of it (names the head has and $WAS lacks)
if [ -n "$ADDS" ]; then
  { [[ "$HEAD" =~ ^[0-9a-f]{40}$ ]] && git cat-file -e "$HEAD^{commit}" 2>/dev/null; } || { echo "STALE was=$WAS now=$NOW changed=$(name3 <<<"$ADDS") (main added docs files and the recorded head \"$HEAD\" is not a commit in this clone, so a collision with a path PR $PR adds cannot be ruled out) -> re-run tools/dev/session_ci.sh $PR"; exit 4; }
  PRADDS=$(git diff --name-only --no-renames --diff-filter=A "$WAS" "$HEAD" --) || { echo "cannot judge PR $PR: git diff $WAS $HEAD failed"; exit 2; }
  # both lists on stdin (main's adds, a blank line, the PR's adds — git never emits an empty name), so no argv/env size limit applies; lower() = the checker's own comparison
  TWIN=$(printf '%s\n\n%s\n' "$ADDS" "$PRADDS" | python3 -I -c 'import sys; adds, pr = sys.stdin.read().split("\n\n", 1); low = {p.lower() for p in pr.splitlines()}; print("\n".join(a for a in adds.splitlines() if a.lower() in low))' | name3) || { echo "cannot judge PR $PR: the collision check against the names PR $PR adds failed"; exit 2; }
  [ -n "$TWIN" ] && { echo "STALE was=$WAS now=$NOW changed=$TWIN (added on main; PR $PR adds the same name or a case-twin of it: an add/add conflict or a portable_paths failure after the merge) -> re-run tools/dev/session_ci.sh $PR"; exit 4; }
fi
echo "FRESH(docs-only drift) was=$WAS now=$NOW"; exit 0
