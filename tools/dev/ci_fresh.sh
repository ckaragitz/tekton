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
# src/rvt/frontdoor/matrix.py cites docs/inbox records by existence. So is a docs file ADDED on main when the
# post-merge name set no longer passes tools/dev/check_portable_paths.py — THE names-only gate session_ci.sh ran, its
# own check() imported from this checkout and re-run here, not a re-derived law (#522) — over the names the merge will
# hold, taken from objects only: ls-tree of the new main, minus the names the PR deletes, plus the names it adds (an
# approximation of the merged tree's names that needs no merge; a name added on both sides stays in twice = add/add).
# A case-only twin of a path the PR adds would redden portable_paths only after the merge (#496); any other law the
# checker has or gains is felt the same way. If main added docs files and the recorded head is not in this clone, none
# of that can be ruled out — STALE too.
# Anything else (code, a docs deletion, a SHARD_READS doc) is drift the shard could feel: STALE — unless
# tools/dev/ci_fresh_drift.py (#539; read its header once: the numbered rules and what it leaves unjudged) can show
# from objects alone that no test can meet both changes at once: main's drift and the PR's own change are DISJOINT
# path sets of plain added/modified names, neither touches the shard machinery, a whole-tree checker or a SHARD_READS
# doc (a shard drop-in only when it enrols nothing but the side's own changed tests), no changed .py file of either
# side imports a module the other side changed or builds module/path names at run time, no changed file names a path
# the other side changed, `git merge-tree --write-tree` (git >= 2.38, a merge in the object store, no checkout) is
# clean, and the merged tree's names pass check_portable_paths.check() — then FRESH(disjoint drift), naming both file
# counts. Any doubt on that path (a deletion or rename, > 200 files a side, an odd name, the head not in this clone)
# is STALE; git failing under it is "cannot judge"; CI_FRESH_STRICT=1 in the environment switches the whole path off
# (code drift = STALE, as before #539). A filter or interpreter failing anywhere is "cannot judge", never FRESH.
# With <head-sha> (what `git ls-remote` says the PR head is right now) it also refuses a JSON computed for another
# head or whose verdict is not pass — so one call is the whole pre-merge check of the CI side.
#
# Trusted side only: git plumbing on THIS checkout (main, plus the file NAMES the recorded PR head adds and deletes —
# the same names-only reading session_ci.sh's portable_paths step does — and, on the code-drift path only, the TEXT of
# the files each side changed, read out of git blobs as data by the judge: regex over import lines and names, never
# imported, never executed), this checkout's own check_portable_paths.py, and a stdlib read of our own JSON. It never
# checks out or runs anything from the PR. Needs git (>= 2.38 for the disjoint-drift path; older git cannot judge it),
# python3, awk (POSIX: mawk, gawk and busybox agree), and network to `git fetch origin main`.
# Prints one line. Exit 0 FRESH / FRESH(docs-only drift) / FRESH(disjoint drift) | 4 STALE (main moved under the
# verdict in a way the shard could feel, or the recorded main is unknown here) | 5 the JSON is for another head / not
# a pass | 3 MISSING (no JSON, or one from before "main" was recorded) | 2 bad PR number / cannot judge (fetch, diff
# or the judge's git failed) — every non-zero exit means "do not merge on this verdict".
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
if [ -n "$BLOCK" ]; then   # code drift: STALE -- unless the disjoint-drift judge can show, from objects only, that nothing the shard runs meets both changes (#539; its header states the rules and what stays unjudged); it prints ONE payload line, this script owns the envelope
  [ -z "${CI_FRESH_STRICT:-}" ] || { echo "STALE was=$WAS now=$NOW changed=$BLOCK (CI_FRESH_STRICT is set: code drift is never judged, only re-run) -> re-run tools/dev/session_ci.sh $PR"; exit 4; }
  SAYS=$(python3 -IB "$REPO/tools/dev/ci_fresh_drift.py" "$WAS" "$NOW" "$HEAD" "$PR" "$SHARD_READS"); RC=$?
  SAYS=${SAYS%%$'\n'*}   # one line, whatever it printed
  case "$RC" in
    0) [ -n "$SAYS" ] && { echo "FRESH(disjoint drift) was=$WAS now=$NOW $SAYS"; exit 0; };;
    4) [ -n "$SAYS" ] && { echo "STALE was=$WAS now=$NOW changed=$BLOCK ($SAYS) -> re-run tools/dev/session_ci.sh $PR"; exit 4; };;
    2) echo "cannot judge PR $PR: ${SAYS:-?} (was=$WAS now=$NOW changed=$BLOCK)"; exit 2;;
  esac
  echo "cannot judge PR $PR: the disjoint-drift judge failed (rc=$RC; was=$WAS now=$NOW changed=$BLOCK)"; exit 2
fi
ADDS=$(awk -F'\t' '$1=="A" {print $2}' <<<"$DRIFT") || { echo "cannot judge PR $PR: drift filter failed"; exit 2; }   # docs files main ADDED: new names, harmless unless the post-merge name set now fails the names-only gate (below; needs the head's names)
if [ -n "$ADDS" ]; then
  { [[ "$HEAD" =~ ^[0-9a-f]{40}$ ]] && git cat-file -e "$HEAD^{commit}" 2>/dev/null; } || { echo "STALE was=$WAS now=$NOW changed=$(name3 <<<"$ADDS") (main added docs files and the recorded head \"$HEAD\" is not a commit in this clone, so a collision with a path PR $PR adds cannot be ruled out) -> re-run tools/dev/session_ci.sh $PR"; exit 4; }
  # The program below (stdin carries it, argv the checker's path + three SHAs + the PR number; it re-reads the names it needs with
  # git -z itself: no argv/env size limit, and names git would quote stay intact) prints nothing when the set is clean, else
  # line 1 = the reason to show and one name per line after it. A main-added name colliding with a PR-added one keeps #496's
  # wording (message continuity only); anything else the checker rejects shows the checker's own first problem line.
  HIT=$(python3 -IB - "$REPO/tools/dev/check_portable_paths.py" "$WAS" "$NOW" "$HEAD" "$PR" <<'PY'
import importlib.util, subprocess, sys
spec = importlib.util.spec_from_file_location("check_portable_paths", sys.argv[1]); checker = importlib.util.module_from_spec(spec); spec.loader.exec_module(checker)
was, now, head, pr = sys.argv[2:]
def names(*args): return subprocess.run(["git", *args], check=True, stdout=subprocess.PIPE).stdout.decode("utf-8", "replace").split("\0")[:-1]
def moved(how, tip): return names("diff", "--name-only", "-z", "--no-renames", "--diff-filter=" + how, was, tip, "--")   # names Added / Deleted from the recorded main to tip
adds, pradds, gone = moved("A", now), moved("A", head), set(moved("D", head))                                              # adds = $ADDS above, re-read NUL-clean
findings = checker.check([p for p in names("ls-tree", "-r", "--name-only", "-z", now) if p not in gone] + pradds)
twinned = {p for _, involved in findings if not set(involved).isdisjoint(pradds) for p in involved}                        # every name of a finding that holds a PR-added name
twins = [a for a in adds if a in twinned]
if twins: print("added on main; PR %s adds the same name or a case-twin of it: an add/add conflict or a portable_paths failure after the merge" % pr, *twins, sep="\n")
elif findings: print("tools/dev/check_portable_paths.py rejects the post-merge name set: %s%s" % (findings[0][0], " (+%d more)" % (len(findings) - 1) if findings[1:] else ""), *dict.fromkeys(p for _, involved in findings for p in involved), sep="\n")
PY
  ) || { echo "cannot judge PR $PR: the collision check against the names PR $PR adds failed"; exit 2; }
  [ -n "$HIT" ] && { NAMED=$(name3 <<<"${HIT#*$'\n'}") || { echo "cannot judge PR $PR: drift filter failed"; exit 2; }; echo "STALE was=$WAS now=$NOW changed=$NAMED (${HIT%%$'\n'*}) -> re-run tools/dev/session_ci.sh $PR"; exit 4; }
fi
echo "FRESH(docs-only drift) was=$WAS now=$NOW"; exit 0
