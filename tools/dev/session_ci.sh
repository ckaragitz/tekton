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
# Needs: root (setpriv/unshare/chown), python3, tar; the repo venv (or SESSION_CI_PYTHON) readable by nobody.
# Prints one JSON object: {pr, head, merge_with_main, portable_paths, plugin_drift, plugin_structure,
# shard_rc, shard_summary, seconds, sandbox, verdict: pass|fail}; exit 0 either way (read the verdict).
set -uo pipefail
PR=${1:?usage: tools/dev/session_ci.sh <pr-number>  (fetch it first: git fetch origin "pull/<n>/head:refs/pr/<n>")}
REPO=$(cd "$(dirname "$0")/../.." && pwd)          # the trusted checkout this script lives in (main)
S=${SESSION_CI_DIR:-${TMPDIR:-/tmp}/session-ci}; mkdir -p "$S/ci"   # logs + result JSON (privileged side only)
PY=${SESSION_CI_PYTHON:-$REPO/.venv/bin/python}; WT=$S/ci/wt-$PR; LOG=$S/ci/$PR.log; OUT=$S/ci/$PR.json
BOX=/tmp/tekton-ci/box-$PR   # under /tmp: every parent must be traversable by `nobody` (the session scratchpad is root-only)
cd "$REPO" || exit 2
: > "$LOG"; rm -f "$OUT"; rm -rf "$BOX"; git worktree remove --force "$WT" >/dev/null 2>&1; rm -rf "$WT"; git worktree prune
HEAD=$(git rev-parse "refs/pr/$PR") || { echo "{\"pr\":$PR,\"error\":\"no ref\"}" > "$OUT"; exit 2; }

# 1) trusted: merge result of head + origin/main in a root-owned worktree (what GitHub's merge ref tested)
git worktree add --detach "$WT" "$HEAD" >/dev/null 2>&1 || { echo "{\"pr\":$PR,\"error\":\"worktree\"}" > "$OUT"; exit 2; }
MERGE=clean
if [ "$(git -C "$WT" rev-list --count HEAD..origin/main)" != "0" ]; then
  git -C "$WT" -c user.name=ci -c user.email=ci@local merge --no-edit origin/main >>"$LOG" 2>&1 || MERGE=conflict
fi
# 2) trusted script, PR data: portable path names
echo "=== portable_paths (main's checker over the PR tree)" >> "$LOG"
if (cd "$WT" && python3 "$REPO/tools/dev/check_portable_paths.py") >> "$LOG" 2>&1; then P=ok; else P=FAIL; fi
# 3) export the merged tree (no .git, no remotes) into a box owned by nobody, with a throwaway local repo
mkdir -p /tmp/tekton-ci && chmod 755 /tmp/tekton-ci && mkdir -p "$BOX" && git -C "$WT" ls-files -z | (cd "$WT" && tar --null -T - -cf -) | tar -xf - -C "$BOX"
git worktree remove --force "$WT" >/dev/null 2>&1; rm -rf "$WT"
TMPBOX=/tmp/tekton-ci/tmp-$PR; rm -rf "$TMPBOX"; mkdir -p "$TMPBOX"   # tmp OUTSIDE the tree, as on a runner
chown -R nobody:nogroup "$BOX" "$TMPBOX"
sandbox() {  # run "$@" as nobody, no network, scrubbed env, cwd = the box
  unshare -n setpriv --reuid=65534 --regid=65534 --clear-groups --inh-caps=-all \
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
mapfile -t SHARD < <(grep -vE '^\s*(#|$)' "$BOX/tests/ci_shard.txt")
echo "=== shard (${#SHARD[@]} files, sandboxed: uid nobody, no network)" >> "$LOG"
sandbox timeout 1500 "$PY" -m pytest "${SHARD[@]}" -q -p no:cacheprovider --durations=5 >> "$LOG" 2>&1; RC=$?
TAIL=$(grep -E "^=* *[0-9]+ (passed|failed)|[0-9]+ passed|[0-9]+ failed| error" "$LOG" | tail -1 | tr -d '=' | sed 's/^ *//')
t1=$(date +%s)
python3 - "$OUT" "$PR" "$HEAD" "$MERGE" "$P" "$D" "$V" "$RC" "$TAIL" "$((t1-t0))" <<'PYEOF'
import json,sys
out,pr,head,merge,p,d,v,rc,tail,secs=sys.argv[1:]
r={"pr":int(pr),"head":head,"merge_with_main":merge,"portable_paths":p,"plugin_drift":d,"plugin_structure":v,
   "shard_rc":int(rc),"shard_summary":tail.strip(),"seconds":int(secs),"sandbox":"uid=nobody,netns=none,env=scrubbed,tree=export"}
r["verdict"]="pass" if (merge=="clean" and p=="ok" and d=="ok" and v=="ok" and r["shard_rc"]==0) else "fail"
json.dump(r,open(out,"w")); print(json.dumps(r))
PYEOF
rm -rf "$BOX" "$TMPBOX"
