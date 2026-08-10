#!/usr/bin/env bash
# tools/dev/session_ci.sh <pr> — the CI job, run by a tech-lead SESSION instead of a GitHub runner.
#
# Steer #302: this repository has no GitHub-hosted compute (no paid Actions minutes, no self-hosted
# runner). The code -> review -> merge pipeline is session-hosted (docs/process/AUTONOMY.md 12c):
# the tech-lead session fetches a PR head (`git fetch origin "pull/<n>/head:refs/pr/<n>"`), runs THIS
# script, spawns an independent reviewer, and merges through the API only with same-tick evidence.
#
# The privilege boundary a runner used to provide is kept:
#   * PR code (plugin sync check, plugin validation, the test shard) runs as `nobody`, in its own
#     network namespace (no network), with a scrubbed environment, inside an EXPORTED copy of the
#     tree it owns — it cannot reach the GitHub connector, git credentials/proxy, the session's own
#     files, or this trusted checkout.
#   * Only trusted code from THIS checkout runs privileged: git plumbing and this checkout's
#     tools/dev/check_portable_paths.py over the PR's file NAMES.
#   * The privileged side reads back one JSON line and the log as data; nothing from the PR is eval'd.
# What it tests is the PR head MERGED with origin/main (what GitHub's merge ref used to test).
# Runs are serialized machine-wide (#329): every sandboxed step of every PR is the same uid under the same jail
# parent, so besides the per-PR lock (a second run of the SAME PR fails fast) the whole run holds ONE global lock
# ($S/ci/global.lock) — invocations for different PRs queue instead of overlapping. A distinct throwaway uid per run
# would need user namespaces and is out of scope. The test shard is tests/ci_shard.txt + the tests/ci_shard.d/*.txt
# drop-ins (#328), merged by THIS checkout's tools/dev/shard_list.py from the PR head's git blobs.
# Needs: root (setpriv/unshare/chown/flock), util-linux unshare with --kill-child, python3, tar; the repo venv (or
# SESSION_CI_PYTHON) readable by nobody. Scratch defaults to REPO/.git/session-ci (root-only); override with SESSION_CI_DIR
# (all runs on one machine must share it — the global lock lives there).
# Prints one JSON object: {pr, head, main (the origin/main it was merged with — tools/dev/ci_fresh.sh <pr> says
# FRESH/STALE against the current one before a merge, #487), merge_with_main, portable_paths, plugin_drift, plugin_structure,
# shard_rc, shard_summary, seconds, sandbox, verdict: pass|fail}; exit 0 either way (read the verdict) —
# except setup failures (no ref, worktree, tree export, lock timeout): {"pr":N,"error":...} and exit 2.
set -uo pipefail
PR=${1:?usage: tools/dev/session_ci.sh <pr-number>  (fetch it first: git fetch origin "pull/<n>/head:refs/pr/<n>")}
[[ "$PR" =~ ^[0-9]+$ ]] || { echo "usage: PR must be a number" >&2; exit 2; }
REPO=$(cd "$(dirname "$0")/../.." && pwd)          # the trusted checkout this script lives in (main)
# Privileged-side scratch (worktree, log, result JSON): root-only, never under a world-writable dir, never a
# symlink or someone else's directory (a `nobody` process must not be able to pre-create or redirect it).
S=${SESSION_CI_DIR:-$REPO/.git/session-ci}
safe_dir() { [ -d "$1" ] || mkdir -m 700 "$1" 2>/dev/null; [ -d "$1" ] && [ -O "$1" ] && [ ! -L "$1" ] || { echo "refusing scratch dir $1 (not an own, non-symlink directory)" >&2; exit 2; }; chmod 700 "$1"; }
safe_dir "$S"; safe_dir "$S/ci"
PY=${SESSION_CI_PYTHON:-$REPO/.venv/bin/python}; WT=$S/ci/wt-$PR; LOG=$S/ci/$PR.log; OUT=$S/ci/$PR.json; LOCK=$S/ci/$PR.lock
# The sandbox side lives under /tmp/tekton-ci (every parent traversable by `nobody`); the PARENT stays root-owned
# 0755 so `nobody` cannot swap box-<pr>/tmp-<pr> for a symlink between our mkdir and our writes into them.
JAIL=/tmp/tekton-ci; BOX=$JAIL/box-$PR; TMPBOX=$JAIL/tmp-$PR
[ ! -L "$JAIL" ] && mkdir -p "$JAIL" && [ ! -L "$JAIL" ] && [ -d "$JAIL" ] && chown -h root:root "$JAIL" && [ -O "$JAIL" ] && chmod 755 "$JAIL" || { echo "refusing $JAIL (symlink, foreign, or not creatable)" >&2; exit 2; }
cd "$REPO" || exit 2
exec 9>"$LOCK"; flock -n 9 || { echo "{\"pr\":$PR,\"error\":\"another session_ci run holds PR $PR\"}"; exit 2; }   # one run per PR at a time
exec 8>"$S/ci/global.lock"; flock -w 5400 8 || { echo "{\"pr\":$PR,\"error\":\"timed out waiting for the global session_ci lock\"}"; exit 2; }   # one run per MACHINE at a time (#329): held until exit
rm -f "$LOG" "$OUT"; : > "$LOG"; rm -rf "$BOX" "$TMPBOX"; git worktree remove --force "$WT" >/dev/null 2>&1; rm -rf "$WT"; git worktree prune
git fetch -q origin main 2>>"$LOG" || echo "(warning: could not refresh origin/main; merge test uses the local copy)" >> "$LOG"
HEAD=$(git rev-parse "refs/pr/$PR") || { echo "{\"pr\":$PR,\"error\":\"no ref refs/pr/$PR\"}" > "$OUT"; cat "$OUT"; exit 2; }
# The trunk this verdict is valid against (#476/#487): recorded as "main" in the JSON, and the merge test below uses THIS
# sha, never the ref name — so recorded == merged even if tools/dev/ci_fresh.sh (lock-free, same checkout) re-fetches
# origin/main mid-run. ci_fresh.sh <pr> compares it with the origin/main of merge time: STALE -> re-run, never merge.
MAIN=$(git rev-parse --verify -q origin/main) || { echo "{\"pr\":$PR,\"error\":\"no origin/main\"}" > "$OUT"; cat "$OUT"; exit 2; }

# 1) trusted: merge result of head + origin/main (= "$MAIN") in a root-owned worktree (what GitHub's merge ref tested)
git worktree add --detach "$WT" "$HEAD" >/dev/null 2>&1 || { echo "{\"pr\":$PR,\"error\":\"worktree\"}" > "$OUT"; cat "$OUT"; exit 2; }
MERGE=clean
if [ "$(git -C "$WT" rev-list --count "HEAD..$MAIN")" != "0" ]; then
  git -C "$WT" -c core.hooksPath=/dev/null -c user.name=ci -c user.email=ci@local merge --no-edit "$MAIN" >>"$LOG" 2>&1 || MERGE=conflict
fi
# 2) trusted script, PR data: portable path names (stdlib-only checker from THIS checkout, run by absolute path)
echo "=== portable_paths (main's checker over the PR tree)" >> "$LOG"
if (cd "$WT" && python3 -I "$REPO/tools/dev/check_portable_paths.py") >> "$LOG" 2>&1; then P=ok; else P=FAIL; fi
# The shard list (tests/ci_shard.txt + the tests/ci_shard.d/*.txt drop-ins, #328) is PR-controlled TEXT: it is read
# here, on the trusted side, by THIS checkout's stdlib helper (never the PR's copy) from the git BLOBS of the merged
# head (`git ls-tree`/`cat-file` — never from the box, where sandboxed code could have swapped a file for a symlink
# into root-only files). The helper accepts only plain test files under tests/ (no smuggled pytest flags such as
# -k/--co/--rootdir that could fake a green run, no `..`), collapses duplicates and refuses an empty list (bare
# `pytest` would collect the whole suite); the loop below re-checks every entry so this gate holds even if the helper
# is ever loosened, and option parsing still ends with `--` before the paths later.
SHARD=(); BADSHARD=""
if SHARD_TXT=$(python3 -I "$REPO/tools/dev/shard_list.py" --git "$WT" 2>>"$LOG"); then [ -n "$SHARD_TXT" ] && mapfile -t SHARD <<<"$SHARD_TXT"; else BADSHARD=" (refused by shard_list.py rc=$?; see log)"; fi
for f in "${SHARD[@]}"; do { [[ "$f" =~ ^tests/[A-Za-z0-9_./-]+\.py$ ]] && [[ "$f" != *..* ]]; } || BADSHARD="$BADSHARD $f"; done
# 3) export the merged tree (no .git, no remotes) into the box, then hand the box to nobody. A failed or partial
# export is FATAL (#329): never run the shard over half a tree and call the result a verdict.
mkdir -m 755 "$BOX" "$TMPBOX" && git -C "$WT" ls-files -z | (cd "$WT" && tar --null --verbatim-files-from -T - -cf -) | tar -xf - -C "$BOX"; EXPORT_RC=$?
git worktree remove --force "$WT" >/dev/null 2>&1; rm -rf "$WT"
{ [ "$EXPORT_RC" = 0 ] && [ -f "$BOX/tests/ci_shard.txt" ] && [ -f "$BOX/src/rvt/__init__.py" ]; } || \
  { echo "=== export FAILED (rc=$EXPORT_RC)" >> "$LOG"; rm -rf "$BOX" "$TMPBOX"; echo "{\"pr\":$PR,\"head\":\"$HEAD\",\"error\":\"export\"}" > "$OUT"; cat "$OUT"; exit 2; }
chown -R nobody:nogroup "$BOX" "$TMPBOX"      # chown -R does not follow symlinks inside the tree
sandbox() {  # run "$@" as nobody: no network, own PID + mount namespaces (children die with the step), no caps, no setuid gain
  unshare -n -m -p -f --mount-proc --kill-child \
    setpriv --reuid=65534 --regid=65534 --clear-groups --inh-caps=-all --bounding-set=-all --no-new-privs \
    env -i PATH=/usr/local/bin:/usr/bin:/bin HOME="$TMPBOX" TMPDIR="$TMPBOX" LANG=C.UTF-8 \
        PYTHONPATH="$BOX/src" PYTHONDONTWRITEBYTECODE=1 RVT_SKIP_LARGE=1 GIT_CONFIG_GLOBAL="$TMPBOX/.gitconfig" \
    bash -c 'cd "$0" && exec "$@"' "$BOX" "$@" 8>&- 9>&- </dev/null   # the two flock fds and stdin never reach PR code
}
sandbox timeout -k 30 120 git init -q >>"$LOG" 2>&1 && sandbox timeout -k 30 300 git add -A >>"$LOG" 2>&1 && \
  sandbox timeout -k 30 300 git -c user.name=ci -c user.email=ci@local commit -qm export >>"$LOG" 2>&1 || echo "(box git init failed — tests needing git ls-files may fail)" >> "$LOG"
step() { local name=$1; shift; echo "=== $name" >> "$LOG"; if sandbox timeout -k 30 600 "$@" >> "$LOG" 2>&1; then echo ok; else echo FAIL; fi; }   # time-boxed: a hanging PR step must not stall the tick
t0=$(date +%s)
D=$(step plugin_drift "$PY" tools/sync_plugin.py --check)
V=$(step plugin_structure "$PY" plugin/scripts/validate_plugin.py)
if [ -n "$BADSHARD" ] || [ "${#SHARD[@]}" = "0" ]; then
  echo "=== shard REFUSED: ${#SHARD[@]} entries, invalid:${BADSHARD:- (empty list)}" >> "$LOG"; RC=3; TAIL="shard list refused (${#SHARD[@]} entries; see log)"
else
  echo "=== shard (${#SHARD[@]} files, sandboxed: uid nobody, no network, own pid/mount ns)" >> "$LOG"
  sandbox timeout -k 30 1500 "$PY" -m pytest -q -p no:cacheprovider --durations=5 -- "${SHARD[@]}" >> "$LOG" 2>&1; RC=$?
  # The summary line is sandbox OUTPUT (untrusted text): keep only a pytest-shaped tally, never arbitrary log content.
  TAIL=$(grep -oE '[0-9]+ (passed|failed|error|errors)(, [0-9]+ [a-z]+)* in [0-9.]+s( \([0-9:]+\))?' "$LOG" | tail -1 | cut -c1-160)   # bounded: it gets posted
fi
t1=$(date +%s)
python3 - "$OUT" "$PR" "$HEAD" "$MAIN" "$MERGE" "$P" "$D" "$V" "$RC" "$TAIL" "$((t1-t0))" <<'PYEOF'
import json,sys
out,pr,head,main,merge,p,d,v,rc,tail,secs=sys.argv[1:]
r={"pr":int(pr),"head":head,"main":main,"merge_with_main":merge,"portable_paths":p,"plugin_drift":d,"plugin_structure":v,
   "shard_rc":int(rc),"shard_summary":tail.strip(),"seconds":int(secs),"sandbox":"uid=nobody,net+pid+mnt ns,no caps,no-new-privs,env scrubbed,tree exported"}
import re
green = re.match(r"^\d+ passed\b", r["shard_summary"]) and not re.search(r"(^|, )\d+ (failed|errors?)\b", r["shard_summary"])   # "3 xfailed" is not a failure
r["verdict"]="pass" if (merge=="clean" and p=="ok" and d=="ok" and v=="ok" and r["shard_rc"]==0 and green) else "fail"
json.dump(r,open(out,"w")); print(json.dumps(r))
PYEOF
rm -rf "$BOX" "$TMPBOX"; flock -u 9; flock -u 8
