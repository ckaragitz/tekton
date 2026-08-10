# EDIT-STATUS — the `--rvt … --edit` route's FAILED status names the reason when the edit never ran (issue #559, Refs #535 #176 #209)

Stream: `edit-status` (eng #559, engineer session started by the tech-lead
session, 2026-08-10). Territory: the ONE composing site
`src/rvt/frontdoor/manifest.py::edit_manifest` (status roll-up only) + its
byte-identical mirror `plugin/lib/src/rvt/frontdoor/manifest.py` (written by
`tools/sync_plugin.py`), NEW `tests/test_edit_status.py` + drop-in
`tests/ci_shard.d/559-edit-status.txt`, this record. Not touched:
`src/rvt/frontdoor/__init__.py` (the `errors[0]` composition stays as it is),
`release_ctx.py` / `rvt_selfcheck.py` / `rvt_edit_text.py` (PR #563 in flight),
`router.py` (fenced), `tools/frontdoor.py` (hot), `_rollup_status` (the create
routes' roll-up — see §4).

## 0. Where the sentence is composed (located first, as chartered)

`grep -rn "edit did not complete" src/rvt/frontdoor/ tools/` → exactly one
composing site, `src/rvt/frontdoor/manifest.py:567` inside `edit_manifest`
(the issue's guess was right; `_route_rvt_inner` in `__init__.py` only composes
`errors[0]` and relays `manifest["status"]`). `tools/frontdoor.py:41` is the
exit-code docstring (`3 = build/edit did not complete`), not a status. No test,
skill or reference pinned the old wording (`grep -rn "edit did not complete\|rc None"`
over `tests/ skills/ plugin/skills/ docs/product/`: nothing; three historical
mentions in `docs/inbox/*.md` records, left alone).

## 1. The defect, reproduced (fresh cloud clone, `origin/main` @ 7d04c82)

`edit_manifest` rolled every errors-before-the-job case up as
`FAILED (edit did not complete: rc %s) % run.get("rc")`; when the job never
started `run == {}`, so the status read `rc None` and the cause sat only in
`errors[0]`. Two sample-free inputs reach that path on `main` (CLI
`tools/frontdoor.py author --rvt X --edit … --json`, and the same through a
bare unzip of `tekton-plugin.zip` with system Python 3.11.15,
`skills/tekton-author/scripts/_bootstrap.py go author …`):

| input | rc | stderr | `status` on `main` | `errors[0]` on `main` (start) |
|---|---|---|---|---|
| 64 KB truncation of `G_ABPD_2025.rvt`, edit `move DP-1 to 3,1,4.66` | 3 | empty | `FAILED (edit did not complete: rc None)` | `cannot open/plan …/trunc64k.rvt: RuntimeError: Partitions/20: walker errors ['no trailer for block at 33759 (B=23663)'] (no release context for …` |
| `G_ABPD_2025.rvt`, edit `set level L1 elevation 3.5` (not in the grammar) | 3 | empty | `FAILED (edit did not complete: rc None)` | `edit not understood: no edit understood from the text. Grammar: 'delete <name\|id> [with cascade]', …` |

The two inputs the charter suggested first — a text file named `bad.rvt` and a
**4 KB** truncation of a bundled base — do **not** reach this path: the
input-release precheck (#176) refuses both before anything opens them
(`REFUSED (input release): bad.rvt is not a Revit file tekton can classify (not
an OLE2 compound file: NotOleFileError) …`, exit **2**, the one line on stderr,
the refusal manifest on disk, no JSON on stdout). That is the refused
composition this issue must leave unchanged, so the tests use the 64 KB
truncation (valid CFB header, broken streams → `cannot open/plan`) and the
grammar miss instead.

## 2. The change

`edit_manifest` now distinguishes *the job never started* from *the job ran
and failed*:

```python
if errors and run.get("rc") is None:   # cannot open/plan, edit not understood, the run raised
    status = "FAILED (" + _status_reason(errors[0]) + ")"
elif errors or (run.get("rc") not in (0, None) and not job):
    status = "FAILED (edit did not complete: rc %s)" % (run.get("rc"),)
```

The discriminator is `run.get("rc") is None` — the very value the old sentence
interpolated — rather than `not run`, so a future caller handing over a partial
`run` (degradations, ops_json) for an edit that never ran still gets the reason,
not `rc None` (a /simplify altitude finding, pinned by a test).
`_status_reason(error)` (new, private, next to the site; budget
`_STATUS_REASON_MAX = 160`): the error as one line (whitespace collapsed); whole
when it fits 160 characters, else cut at the last word boundary that keeps at
least a third of it, trailing clause punctuation (` ,;:-(`) dropped, `...`
marking the cut — the reason including the `...` is ≤ 160, never cut mid-word
unless a single token is itself longer than the budget (then the one hard cut;
`textwrap.shorten` would return a bare placeholder there, which is why it is
not used). The refused line still *replaces* the status; the UNVERIFIED-RELEASE
suffix still *appends* to it; `errors`, `edit.rc`, every other key: untouched.
`MANIFEST.md`'s `**Status:**` line renders `m["status"]`, so it follows for
free.

It does not depend on PR #563 and reads well once #563's better `errors[0]`
wording lands: the status is whatever `errors[0]` says, and the tests assert
only on the prefixes `__init__.py` composes (`cannot open/plan `,
`edit not understood: `), never on `release_ctx` wording.

## 3. Evidence (numbers)

**After, same two inputs, CLI and bare unzip (system `python3`, `env -u
PYTHONPATH -u TEKTON_ROOT`, cwd = the unzip dir):** rc **3**, stderr **0
bytes**, stdout one strict JSON document, both surfaces:

| input | `status` after |
|---|---|
| 64 KB truncation | `FAILED (cannot open/plan /tmp/…/trunc64k.rvt: RuntimeError: Partitions/20: walker errors...)` (165 chars = `FAILED (` + 156 + `)`) |
| grammar miss | `FAILED (edit not understood: no edit understood from the text. Grammar: 'delete <name\|id> [with cascade]', 'move <ref> to X,Y[,Z] [ft\|m] [rotation N deg]', 'move...)` |

Envelope identity, before vs after, for both bad inputs: CLI `--json` key set
identical (`errors files handoff intent_json manifest ok out_dir release route
seconds stamps status`), only `status` differs in value (plus the `--out`
paths); `manifest.json` recursive key set identical, `errors` identical,
`edit.rc` `None` both sides; `go` envelope (`go`, `result`) recursive key set
identical.

**Good edit identity ×3** (`set level 311 elevation to 1 ft` = "L1 - Ground
Floor", present on every pin), `origin/main` worktree vs this branch, CLI *and*
bare unzip of each side's freshly built zip — output `.rvt` md5 + status:

| base | md5 (main = branch, CLI = bare unzip) | status (all four runs) | rc |
|---|---|---|---|
| `G_ABPD.rvt` (2026) | `35a940ac94c789065d491791c9037bb9` | `PROOF-ONLY, NOT-DELIVERABLE (hard gates PASSED)` | 0 |
| `G_ABPD_2025.rvt` | `ad02290eb3d4e7a123e4557439476e1d` | same | 0 |
| `G_ABPD_2024.rvt` | `8eb26459e849f1968c2dfbfbb33311ee` | same | 0 |

**Tests:** `tests/test_edit_status.py` — 7 passed in 1.3 s (four pure roll-up
cases: reason whole + partial-`run`-without-rc / long reason cut on a boundary
≤ 160 + hard-cut + one-line / ran-and-failed keeps `rc N` / refused + unverified
composition unchanged; the grammar miss in process; the 64 KB truncation
through the CLI as a subprocess: rc 3, stderr empty, one JSON, status starts
`FAILED (cannot open/plan `, no `rc None`; the good edit in process: ok, status
== main's literal, output written). Whole merged CI shard: see BRANCH STATE.

**/verify at the final head** (front door CLI + bare unzip of the rebuilt zip,
system Python 3.11.15): the two bad inputs rc 3 / stderr 0 / statuses as in the
table above on both surfaces; the refused text file unchanged (rc 2, the one
`REFUSED (input release): …` line on stderr, refusal manifest on disk); good
edits ×3 rc 0, md5s as above, each output `rvt_validate.py` exit 0 / errors=0
under its own release; `go author --prompt "an electrical room with 6 panels"`
from the bare unzip rc 0, `PROOF-ONLY (self-checks PASS; …)`.

## 4. Findings / follow-ups (not done here — outside the one site)

* `cannot open/plan <absolute path>: …` spends most of the 160-character budget
  on the path (a cloud tmp path is ~100 chars), so the walker's actual words get
  cut early. The composition is `__init__.py::_route_rvt_inner`'s (explicitly
  out of territory); relativising the path there (`manifest._relp`, as the
  manifest already does for every other path) would let the reason ride whole.
  #559's DONE hoped #535's test could assert `"Formats/Latest" in doc["status"]`
  — with an absolute tmp path in front that clause may fall past the cut; assert
  on `errors[0]` for the full text, or shorten the path first.
* `_rollup_status` (the create routes) still hard-slices `errors[0][:160]`
  mid-word. Reusing `_status_reason` there is a one-line change but alters the
  create routes' FAILED bytes, which this issue promised to leave identical;
  left for a follow-up if wanted.
* A refused input under `--json` prints nothing on stdout (the line goes to
  stderr, exit 2, manifest on disk). By design per #176's tests; noted only
  because a skill that pipes `--json` straight into a parser gets an empty
  document there — `tools/frontdoor.py` is hot, not touched.

## BRANCH STATE

* Branch `cam/559-edit-status` from `origin/main` @ 7d04c82, rebased onto 6250424 (#563 merged meanwhile; its `tests/test_release_ctx_refusal.py` stays green here, 12 passed); one issue, one PR #568 (`Closes #559`).
* Files: `src/rvt/frontdoor/manifest.py` (+`_STATUS_REASON_MAX`, `_status_reason`, the two-branch roll-up), `plugin/lib/src/rvt/frontdoor/manifest.py` (sync mirror, byte-identical), NEW `tests/test_edit_status.py`, NEW `tests/ci_shard.d/559-edit-status.txt`, NEW `docs/inbox/edit-status.md`.
* Gates: `tests/test_edit_status.py` 7 passed; `tools/sync_plugin.py` rebuilt + `--check` clean ("plugin in sync with source"); `plugin/scripts/validate_plugin.py` PASS (25 assertions); `tools/dev/check_portable_paths.py` ok; whole merged shard (`shard_list.py --print`, 93 files, `RVT_SKIP_LARGE=1 -p no:cacheprovider`): **1916 passed, 134 skipped, 3 xfailed, 0 failed in 494.85 s** on head 0cb943c (an earlier run that my own mid-run rebase disturbed showed one `test_selfcheck_release` failure with mixed old/new `release_ctx.py` frames — a voided reading, re-run clean above).
* Nothing staged for the viewer (status wording only; no `.rvt` bytes change — md5 identity ×3 above). Shipped = the wording; PROOF-ONLY / refused / unverified paths byte-identical.
