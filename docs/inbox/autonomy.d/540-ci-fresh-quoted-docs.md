# 540 — `ci_fresh.sh` reads non-ASCII docs names as docs drift, not code drift

Fragment of the `autonomy` stream (index: `docs/inbox/autonomy.md`, whose "eng #496" and "eng #522" sections hold the
helper's earlier outcome tables). Issue #540. Refs #522 #496 #487.

## What was wrong (measured, not inferred)

`tools/dev/ci_fresh.sh` classified the `was..now` drift from `git diff --name-status` under git's default
`core.quotePath=true`. Git C-quotes any name holding a byte above 0x7f, so `docs/inbox/café notes.md` added on `main`
arrived as `"docs/inbox/caf\303\251 notes.md"` — leading double quote — failed the awk `^docs/` test and was read as
**code** drift: `STALE … changed="docs/inbox/caf\303\251 notes.md",…`, exit 4, one needless sandboxed CI re-run for
every in-flight PR per such docs merge. Fail-closed (never a wrong FRESH), and `git ls-files` holds no such name today,
hence P2 — but records are free-form names.

## What changed

- `tools/dev/ci_fresh.sh`: the `DRIFT` diff runs as `git -c core.quotePath=false diff --name-status --no-renames …`.
  Non-ASCII names now print raw and classify exactly like ASCII ones (tolerated when added/modified under `docs/**`
  outside `SHARD_READS`; named raw where the drift is refused for another reason). Names git quotes *regardless* of
  that flag — holding `"`, `\`, TAB, LF or another control character — still arrive as `"docs/…"`, still fail `^docs/`
  and stay STALE — fail-closed exactly as before, and now always informative: `tools/dev/check_portable_paths.py`
  refuses exactly those names, so the re-run such a name costs is the run that shows `main` went red. **Probing found
  the one byte on which that was not yet true: DEL (0x7f)** — git C-quotes it even with quotePath off, while the
  checker's `BAD = [<>:"|?*\\\x00-\x1f]` stopped at 0x1f and let it through. Fixed at the layer that owns the law
  (territory extended on #540 first, https://github.com/ckaragitz/tekton/issues/540#issuecomment-5271411810):
  `BAD` gains `\x7f`, and `tests/test_portable_paths.py` pins the whole class — TAB, 0x1f, DEL, `"`, `\` refused;
  café, ü, NBSP accepted — so the two gates agree byte for byte. The three awk calls now run under `LC_ALL=C`: with
  quotePath off they see raw 8-bit names, and byte semantics keep mawk/gawk/busybox agreeing (gawk warns on invalid
  multibyte input in a UTF-8 locale; `^docs/` and `[AM]` are ASCII, so nothing is lost). The merge-time collision
  program was already NUL-clean (`git … -z`, #522) and needed nothing.
- `tests/test_ci_fresh.py`: two rows. (1) `docs/inbox/café notes.md` + `docs/ünïcode.md` added on main → `FRESH(docs-only
  drift)` for PR 7 (called with its expected head, the tick's real call shape); the same drift for PR 17, whose recorded
  head this clone lacks, stays STALE (docs ADDED, collision cannot be ruled out — #496's rule, untouched) and names both
  files raw. (2) `docs/inbox/we"ird.md` + `docs/tab<TAB>here.md` added beside a café record →
  `STALE … changed="docs/inbox/we\"ird.md","docs/tab\there.md"` — the two unportable names as git spells them, the café
  record tolerated and not named (skipped on win32, where such names cannot exist). The rig's `GIT_CONFIG_GLOBAL=/dev/null`
  means only the helper's own `-c` can make row 1 pass. The unknown-head expected line became one module constant
  (`UNKNOWN_HEAD_LINE`) shared with #496's pre-existing row, the way `TWIN_LINE` already is. **Engine swap:** both rows
  run over `main`'s helper fail for the right reason (row 1: `(4, 'STALE …')` ≠ `(0, 'FRESH(docs-only drift) …')`; row 2:
  `changed=` wrongly leads with `"docs/inbox/caf\303\251 notes.md"`); over the fixed helper the module is 26 passed, 2
  skipped (the gawk and busybox rows: only mawk is installed here). A `/simplify` pass dropped two assertions that pinned
  nothing new: a no-head twin of row 1's call (the head argument is consumed before the drift is read, so both shapes
  walk one path) and a trailing "modify the café record" step (`git diff was now` is tree-to-tree, so a name absent at
  `was` stays `A` — the drift text was byte-identical to the step before it).

## Evidence — outcome table, BEFORE (main @ `54228cb`) vs AFTER, one deterministic rig

Fixed author/committer dates → identical SHAs run to run; upstream + clone with the helper and the checker copied into
the clone; PR 7 = `origin/main` + `docs/inbox/foo.md` + `src/new.py` with a pass JSON for its real head; PR 17 = a pass
JSON for the never-fetched head `eeee…`. Each `up` step is one more commit on upstream `main`, so drift accumulates.

```
--- unchanged:                                     FRESH main=a90a05d2…   exit=0                                  (identical)
--- unchanged, expected head given:                FRESH main=a90a05d2…   exit=0                                  (identical)
--- docs-only drift (record + note), ASCII:        FRESH(docs-only drift) was=a90a05d2… now=837b120f…   exit=0    (identical)
--- docs-only drift + non-ASCII docs ADDED:
    BEFORE  STALE was=a90a05d2… now=6147482a… changed="docs/inbox/caf\303\251 notes.md","docs/\303\274n\303\257code.md" -> re-run tools/dev/session_ci.sh 7   exit=4
    AFTER   FRESH(docs-only drift) was=a90a05d2… now=6147482a…   exit=0
--- same, head unknown here (pr 17):
    BEFORE  STALE … changed="docs/inbox/caf\303\251 notes.md","docs/\303\274n\303\257code.md" -> re-run tools/dev/session_ci.sh 17   exit=4
    AFTER   STALE … changed=docs/inbox/café notes.md,docs/inbox/record.md,docs/ünïcode.md (main added docs files and the recorded head "eeee…" is not a commit in this clone, so a collision with a path PR 17 adds cannot be ruled out) -> re-run tools/dev/session_ci.sh 17   exit=4
--- non-ASCII docs MODIFIED after those ADDs (17):  same pair as the row above (the earlier ADDs are still inside was..now)   exit=4 both
--- docs names git still quotes (" and TAB):
    BEFORE  STALE … changed="docs/inbox/caf\303\251 notes.md","docs/inbox/we\"ird.md","docs/tab\there.md",… -> re-run tools/dev/session_ci.sh 7   exit=4
    AFTER   STALE … changed="docs/inbox/we\"ird.md","docs/tab\there.md" -> re-run tools/dev/session_ci.sh 7   exit=4
--- code drift on top:
    BEFORE  STALE … changed="docs/inbox/caf\303\251 notes.md","docs/inbox/we\"ird.md","docs/tab\there.md",… -> re-run tools/dev/session_ci.sh 7   exit=4
    AFTER   STALE … changed="docs/inbox/we\"ird.md","docs/tab\there.md",src/a.py -> re-run tools/dev/session_ci.sh 7   exit=4
```

`diff BEFORE AFTER`: rows 1–3 byte-identical; rows 4–8 differ exactly as above — row 4 is the fix; rows 5–6 keep their
(correct, #496) STALE but now for the stated reason and with `docs/inbox/record.md` no longer hidden behind the misread
names; rows 7–8 keep STALE and merely stop mis-naming the café record. In that table the only exit code that changes is
row 4's `4 → 0` — because its one MODIFY happens after ADDs. The other `4 → 0` this issue is about, **a non-ASCII record
MODIFIED alone** (nothing docs-ADDED inside `was..now`), needs the record to exist at `was`, so it was measured on a
second deterministic rig seeded with `docs/inbox/résumé.md`, for the head-unknown PR 17 (the strictest caller — no
collision program can rescue it) — and is what `tests/test_ci_fresh.py`'s non-ASCII row now opens with:

```
--- non-ASCII record MODIFIED alone, head unknown (17):
    BEFORE  STALE was=7cf2634c… now=b01edcae… changed="docs/inbox/r\303\251sum\303\251.md" -> re-run tools/dev/session_ci.sh 17   exit=4
    AFTER   FRESH(docs-only drift) was=7cf2634c… now=b01edcae…   exit=0
```

## Verification — the CLI driven, and probed around the change

The final tree's outcome table is byte-identical to AFTER above (the `/simplify` edits changed no behaviour). Probes, each
in a throwaway repo with `git -c core.quotePath=false diff --cached --name-status | cat -A` beside the checker's own
`check()` on the same name: backslash → `"docs/back\\slash.md"` (quoted → STALE) and refused by the checker (consistent);
NBSP 0xa0 → `docs/nbsp<C2><A0> x.md` raw (tolerated) and accepted (consistent); **DEL 0x7f → `"docs/del\177name.md"`
(quoted → STALE) yet accepted by the checker** — the one name on which the two gates disagreed; fixed in the checker (above)
rather than excused in prose. The live helper in this checkout: `ci_fresh.sh 702 56e260d8…` → `NOT-PASS verdict=fail …`
exit 5 (that PR's stored run is red); `ci_fresh.sh 9999` → `MISSING …` exit 3; `ci_fresh.sh x` → usage, exit 2 — clean
one-liners, no tracebacks.

## BRANCH STATE

- Branch `cam/540-ci-fresh-quoted-docs` from `main` @ `54228cb`; files: `tools/dev/ci_fresh.sh` (one `-c
  core.quotePath=false` on the `DRIFT` diff with a short pointer comment, `LC_ALL=C` on the three awk calls, header
  lines), `tools/dev/check_portable_paths.py` (`\x7f` into `BAD` + docstring; territory extended on the issue first),
  `tests/test_ci_fresh.py` (+2 tests; `UNKNOWN_HEAD_LINE` defined beside `TWIN_LINE` and used by the new row and #496's
  row; the rig's seed gains `docs/inbox/résumé.md` so a MODIFIED non-ASCII record can be pinned), `tests/test_portable_paths.py`
  (+1 test), this fragment (new; index `docs/inbox/autonomy.md` untouched). Both test modules are already in the shard
  (`tests/ci_shard.d/487-ci-fresh.txt`, `tests/ci_shard.d/522-portable-paths.txt`); no new drop-in.
- No `src/`, `plugin/`, `skills/`, workflow or hot file touched. Gates: `bash -n tools/dev/ci_fresh.sh` OK;
  `tests/test_ci_fresh.py` + `tests/test_portable_paths.py` + `tests/test_records_layout.py` + `tests/test_techlead.py`
  → 71 passed, 2 skipped locally on every pushed head (the sandboxed shard's counts for the merged head are in the PR's
  merge comment); `check_portable_paths.py` ok, 3109 tracked paths with this fragment;
  `tools/sync_plugin.py --check` in sync (nothing under `src/` moved).
- Follow-ups surfaced by the `/simplify` altitude pass, filed as their own issues: **#722** the drift reader unified onto
  the NUL-clean `-z` + `check()` program (retiring the awk layer); **#723** `tools/dev/coord.py:459` (fail-open batch
  reader) / `tools/dev/techlead.py:974` line-wise readers of git name output; **#724** an encoding/normalisation law for
  the checker (invalid UTF-8, NFC/NFD twins) — until it lands, a docs name whose high bytes are not valid UTF-8 is
  tolerated drift here (raw now, accepted by `check()`), which the helper's header states.
- Independent review of `d99b55b` (PR #725): 🟡 nits, all taken on the same branch — "contains that byte set" (the
  checker's class is a strict superset of git's quoting set: git quotes `01-1f,22,5c,7f`, `check()` refuses those plus
  `<>:|?*`, measured by the reviewer over every byte 0x01–0xff; zero quoted-but-accepted names), the drop-in's real
  name above, the follow-up numbers here, a pinned MODIFIED non-ASCII row, and the invalid-UTF-8 sentence. The
  reviewer also ran the module under gawk 5.2.1 and busybox 1.36.1 shims (28 passed each; `name3` output byte-identical
  across flavour × locale, and gawk without `LC_ALL=C` does warn on such input — the prefix is load-bearing).
  Round 2 on `7a406c5`: 🟡 nits, taken — the MODIFIED-alone BEFORE/AFTER pair above (the reviewer measured the same
  pair independently), the docstring naming both cases, and `rig.fresh` decoding the helper's stdout as UTF-8 explicitly
  (`text=True` alone uses the locale codec, which would mismatch the raw `café` expectations under cp1252 the day O2's
  Windows job runs this module). Gate counts for the merged head are in the PR's merge comment (same-tick evidence).
- Shipped on merge; nothing staged.
