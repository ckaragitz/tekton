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
# Needs: root (setpriv/unshare/chown/flock), util-linux unshare with --kill-child, python3, tar; the repo venv (or
# SESSION_CI_PYTHON) readable by nobody. Scratch defaults to REPO/.git/session-ci (root-only); override with SESSION_CI_DIR.
# Prints one JSON object: {pr, head, merge_with_main, portable_paths, plugin_drift, plugin_structure,
# shard_rc, shard_summary, seconds, sandbox, verdict: pass|fail}; exit 0 either way (read the verdict).
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
mkdir -p "$JAIL" && chown root:root "$JAIL" && chmod 755 "$JAIL" && [ ! -L "$JAIL" ] || { echo "refusing $JAIL" >&2; exit 2; }
cd "$REPO" || exit 2
exec 9>"$LOCK"; flock -n 9 || { echo "{\"pr\":$PR,\"error\":\"another session_ci run holds PR $PR\"}"; exit 2; }   # one run per PR at a time
rm -f "$LOG" "$OUT"; : > "$LOG"; rm -rf "$BOX" "$TMPBOX"; git worktree remove --force "$WT" >/dev/null 2>&1; rm -rf "$WT"; git worktree prune
git fetch -q origin main 2>>"$LOG" || echo "(warning: could not refresh origin/main; merge test uses the local copy)" >> "$LOG"
HEAD=$(git rev-parse "refs/pr/$PR") || { echo "{\"pr\":$PR,\"error\":\"no ref refs/pr/$PR\"}" > "$OUT"; cat "$OUT"; exit 2; }

# 1) trusted: merge result of head + origin/main in a root-owned worktree (what GitHub's merge ref tested)
git worktree add --detach "$WT" "$HEAD" >/dev/null 2>&1 || { echo "{\"pr\":$PR,\"error\":\"worktree\"}" > "$OUT"; cat "$OUT"; exit 2; }
MERGE=clean
if [ "$(git -C "$WT" rev-list --count HEAD..origin/main)" != "0" ]; then
  git -C "$WT" -c core.hooksPath=/dev/null -c user.name=ci -c user.email=ci@local merge --no-edit origin/main >>"$LOG" 2>&1 || MERGE=conflict
fi
# 2) trusted script, PR data: portable path names (stdlib-only checker from THIS checkout, run by absolute path)
echo "=== portable_paths (main's checker over the PR tree)" >> "$LOG"
if (cd "$WT" && python3 -I "$REPO/tools/dev/check_portable_paths.py") >> "$LOG" 2>&1; then P=ok; else P=FAIL; fi
# The shard list is PR-controlled TEXT: read it here, on the trusted side, from the git blob (never from the box,
# where sandboxed code could have swapped the file for a symlink into root-only files); accept only plain test
# files under tests/ (no smuggled pytest flags such as -k/--co/--rootdir that could fake a green run, no `..`),
# refuse an empty list (bare `pytest` would collect the whole suite), and end option parsing with `--` later.
mapfile -t SHARD < <(git -C "$WT" show HEAD:tests/ci_shard.txt 2>>"$LOG" | grep -vE '^\s*(#|$)')
BADSHARD=""; for f in "${SHARD[@]}"; do { [[ "$f" =~ ^tests/[A-Za-z0-9_./-]+\.py$ ]] && [[ "$f" != *..* ]]; } || BADSHARD="$BADSHARD $f"; done
# 3) export the merged tree (no .git, no remotes) into the box, then hand the box to nobody
mkdir -m 755 "$BOX" "$TMPBOX" && git -C "$WT" ls-files -z | (cd "$WT" && tar --null -T - -cf -) | tar -xf - -C "$BOX"
git worktree remove --force "$WT" >/dev/null 2>&1; rm -rf "$WT"
chown -R nobody:nogroup "$BOX" "$TMPBOX"      # chown -R does not follow symlinks inside the tree
sandbox() {  # run "$@" as nobody: no network, own PID + mount namespaces (children die with the step), no caps, no setuid gain
  unshare -n -m -p -f --mount-proc --kill-child \
    setpriv --reuid=65534 --regid=65534 --clear-groups --inh-caps=-all --bounding-set=-all --no-new-privs \
    env -i PATH=/usr/local/bin:/usr/bin:/bin HOME="$TMPBOX" TMPDIR="$TMPBOX" LANG=C.UTF-8 \
        PYTHONPATH="$BOX/src" PYTHONDONTWRITEBYTECODE=1 RVT_SKIP_LARGE=1 GIT_CONFIG_GLOBAL="$TMPBOX/.gitconfig" \
    bash -c 'cd "$0" && exec "$@"' "$BOX" "$@"
}
sandbox git init -q >>"$LOG" 2>&1 && sandbox git add -A >>"$LOG" 2>&1 && \
  sandbox git -c user.name=ci -c user.email=ci@local commit -qm export >>"$LOG" 2>&1 || echo "(box git init failed — tests needing git ls-files may fail)" >> "$LOG"
step() { local name=$1; shift; echo "=== $name" >> "$LOG"; if sandbox "$@" >> "$LOG" 2>&1; then echo ok; else echo FAIL; fi; }
t0=$(date +%s)
D=$(step plugin_drift "$PY" tools/sync_plugin.py --check)
V=$(step plugin_structure "$PY" plugin/scripts/validate_plugin.py)
if [ -n "$BADSHARD" ] || [ "${#SHARD[@]}" = "0" ]; then
  echo "=== shard REFUSED: ${#SHARD[@]} entries, invalid:${BADSHARD:- (empty list)}" >> "$LOG"; RC=3; TAIL="shard list refused (${#SHARD[@]} entries; see log)"
else
  echo "=== shard (${#SHARD[@]} files, sandboxed: uid nobody, no network, own pid/mount ns)" >> "$LOG"
  sandbox timeout 1500 "$PY" -m pytest -q -p no:cacheprovider --durations=5 -- "${SHARD[@]}" >> "$LOG" 2>&1; RC=$?
  # The summary line is sandbox OUTPUT (untrusted text): keep only a pytest-shaped tally, never arbitrary log content.
  TAIL=$(grep -oE '[0-9]+ (passed|failed|error|errors)(, [0-9]+ [a-z]+)* in [0-9.]+s( \([0-9:]+\))?' "$LOG" | tail -1)
fi
t1=$(date +%s)
python3 - "$OUT" "$PR" "$HEAD" "$MERGE" "$P" "$D" "$V" "$RC" "$TAIL" "$((t1-t0))" <<'PYEOF'
import json,sys
out,pr,head,merge,p,d,v,rc,tail,secs=sys.argv[1:]
r={"pr":int(pr),"head":head,"merge_with_main":merge,"portable_paths":p,"plugin_drift":d,"plugin_structure":v,
   "shard_rc":int(rc),"shard_summary":tail.strip(),"seconds":int(secs),"sandbox":"uid=nobody,net+pid+mnt ns,no caps,no-new-privs,env scrubbed,tree exported"}
import re
green = re.match(r"^\d+ passed\b", r["shard_summary"]) and not re.search(r"(^|, )\d+ (failed|errors?)\b", r["shard_summary"])   # "3 xfailed" is not a failure
r["verdict"]="pass" if (merge=="clean" and p=="ok" and d=="ok" and v=="ok" and r["shard_rc"]==0 and green) else "fail"
json.dump(r,open(out,"w")); print(json.dumps(r))
PYEOF
rm -rf "$BOX" "$TMPBOX"; flock -u 9
