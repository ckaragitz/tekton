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

---

## eng #573 — 2026-08-10: `cannot open/plan` names the input by basename (issue #573, Refs #559 #568 #535)

Stream `edit-status`, second pass (engineer session started by the tech-lead
session). Territory: the ONE composing site in
`src/rvt/frontdoor/__init__.py::_route_rvt_inner` (+ its byte-identical mirror
`plugin/lib/src/rvt/frontdoor/__init__.py` via `tools/sync_plugin.py`),
`tests/test_edit_status.py` (rows added), this section. Not touched:
`manifest.py` (settled by #568), `release_ctx.py`, `router.py` (fenced),
`tools/frontdoor.py` (hot), the sibling `edit not understood:` / `edit run
failed:` prefixes (no path in either).

### What changed (one line)

```python
errors.append(f"cannot open/plan {os.path.basename(rvt_path)}: {type(e).__name__}: {e}"
              + (f" ({ctx_note})" if ctx_note else ""))
```

`rvt_path` → `os.path.basename(rvt_path)` in that sentence, nothing else. The
absolute path was never lost by this: it already lives — verified on both
fixtures, CLI and bare unzip — in `manifest.json` as **`inputs.rvt`** and
**`base.input_file`** (there is no `edit.input` key; `edit.spec` is
`{"error": [errors[0]]}` on this path and so follows the sentence). The CLI /
`go` `--json` envelope carries no `inputs` key of its own; it points at
`manifest.json` (`manifest.json`/`.md` paths) and relays `status` + `errors`.
Basename rather than a `…/parent/name` tail: the parent of a cloud upload is a
random tmp segment that tells the user nothing, and the full path is one key
away.

### Evidence (fresh cloud clone, `origin/main` @ 4bd7ecf = #568 merged; fixtures under a 136-char directory, so the input paths are 148 / 150 chars)

Fixtures: `trunc64k.rvt` = the 2025 pin cut at 64 KB; `schema_dmg.rvt` = the
2025 pin re-emitted with 64 bytes of `Formats/Latest` zeroed (built exactly
like `tests/test_release_ctx_refusal.py`'s). Both surfaces = CLI
(`tools/frontdoor.py author --rvt … --edit … --json`, `env -u PYTHONPATH -u
TEKTON_ROOT`) and bare unzip of each side's freshly built `tekton-plugin.zip`
with system Python 3.11.15 (`skills/tekton-author/scripts/_bootstrap.py go
author …`, cwd = the unzip dir). All eight bad-input runs: **rc 3, stderr 0
bytes, one JSON document**, envelope key set `errors files handoff intent_json
manifest ok out_dir release route seconds stamps status` identical main =
branch, `manifest.json` recursive key set identical, `inputs.rvt` ==
`base.input_file` == the absolute path on both sides; values differing:
`generated_at`, `out_dir`, `status`, `errors[0]`, `edit.spec.error[0]` only.

| input (path 148/150 chars) | `status` on `main` (CLI = go) | `status` on this branch (CLI = go) |
|---|---|---|
| `trunc64k.rvt` | `FAILED (cannot open/plan /tmp/claude-0/-home-user-tekton/e98bc27e-…/scratchpad/a-deliberately-long-directory-name-for-issue-573/nested/trun...)` [169] | `FAILED (cannot open/plan trunc64k.rvt: RuntimeError: Partitions/20: walker errors ['no trailer for block at 33759 (B=23663)'] (no release context for...)` [153] |
| `schema_dmg.rvt` | `FAILED (cannot open/plan /tmp/claude-0/-home-user-tekton/e98bc27e-…/scratchpad/a-deliberately-long-directory-name-for-issue-573/nested/sche...)` [169] | `FAILED (cannot open/plan schema_dmg.rvt: ParseError: parse error at 0x603b: class marker != 0 (0x403c) @0x603b: 14 1e d3 f2 96 31 b0 8a 94 42 91 9f 18 51 c1 c2 6a 2c...)` [169] |

`errors[0]` length main → branch: 1040 → 904 (trunc64k), 1315 → 1179
(schema_dmg) — the one path occurrence this site owns; the release note behind
it is untouched (see finding 1).

**Good edit identity ×3** (`set level 311 elevation to 1 ft`), `origin/main`
worktree vs this branch, CLI *and* bare unzip of each side's zip — all four
runs per base agree:

| base | md5 (main = branch, CLI = go) | status | rc |
|---|---|---|---|
| `G_ABPD.rvt` (2026) | `35a940ac94c789065d491791c9037bb9` | `PROOF-ONLY, NOT-DELIVERABLE (hard gates PASSED)` | 0 |
| `G_ABPD_2025.rvt` | `ad02290eb3d4e7a123e4557439476e1d` | same | 0 |
| `G_ABPD_2024.rvt` | `8eb26459e849f1968c2dfbfbb33311ee` | same | 0 |

(the same three md5s #568 recorded — the good path does not pass this line.)

**Tests:** `tests/test_edit_status.py` 7 → 8: the CLI truncation row now runs
under a module-scoped `long_dir` (≥ 100 chars, portable name) and asserts the
#573 contract through `_assert_named_not_pathed` (errors[0] and status start
`cannot open/plan <basename>: `, status ≤ `FAILED (` + 160 + `)`, the long
directory absent from the status, the reason words present in it —
`RuntimeError` + `walker errors` — and `inputs.rvt == base.input_file ==` the
absolute path, `edit.rc None`); NEW
`test_schema_damaged_host_status_names_the_file_and_the_parse_error` (in
process, same helper, reason words `ParseError` + `parse error`, and errors[0]
still whole: `no release context for ` + `Formats/Latest` behind the reason).
Already in the shard via `tests/ci_shard.d/559-edit-status.txt` (no new
drop-in needed). `tests/test_release_ctx_refusal.py` 12 passed unchanged (its
`errors[0].startswith("cannot open/plan ")` + `Formats/Latest in errors[0]`
assertions hold).

### Findings

1. **`Formats/Latest` cannot reach the cut for the schema-damaged host from
   this site — and the DONE hoped it would.** The issue (and #559 §4) assumed
   `errors[0]` reads `cannot open/plan <path>: its Formats/Latest class schema
   cannot be read (ParseError …)`. It does not: the *primary* exception when a
   2025 host's schema is damaged is the raw parser's
   `ParseError: parse error at 0x603b: class marker != 0 (0x403c) @0x603b: <64-byte hex context, ~195 chars>`
   (the read side has no release context, parses the file's own schema, and
   fails); the `Formats/Latest` wording lives only in the appended release note,
   which itself opens with a second absolute path —
   `(no release context for <150-char path>: its Formats/Latest class schema cannot be read (ParseError: <same hex>); read side: own schema unreadable (<same hex>); …)`.
   So after the basename the status carries the parser's reason (`ParseError:
   parse error at 0x603b: class marker != 0 (0x403c)`) — a true reason, inside
   the cut, asserted by the new test — but not the friendlier clause. Getting
   that clause in needs one of two out-of-territory one-liners, filed as
   follow-up **#574** rather than done here: (a) `release_ctx.enter_host_release`
   names `host_path` by basename in its note (`release_ctx.py:335/337`; its
   test pins `note.startswith(f"no release context for {path}: ")`), and/or
   (b) `rvt.schema`'s `ParseError` caps its hex context (`schema.py:367`,
   today 24 + 40 bytes = 193 chars, repeated three times in this one
   sentence: 579 of its 1179 chars are hex). Only with both would the status
   read `cannot open/plan schema_dmg.rvt: ParseError: parse error at 0x603b:
   class marker != 0 (0x403c) … (no release context for schema_dmg.rvt: its
   Formats/Latest…`. Neither changes rc / keys / good-edit bytes.
2. The truncation's sentence still names the absolute path twice inside the
   release note (`no release context for <abs>: base <abs> carries schema
   sha256 e3b0c442… but the Revit 2025 pin is …`) — same site as (a); harmless
   for the cut now that the reason precedes it.
3. /simplify (four angles): reuse / efficiency / altitude clean —
   `basename` is the primitive here (`_rel` / `manifest._relp` fall back to
   the absolute path for anything outside the repo, i.e. exactly the tmp
   inputs this is about; `input_release.py:70` already names a refused input
   by basename); the new fixtures cost 0.05 s. Applied: the assertion helper
   reads `status` / `errors[0]` off `manifest.json` and each caller asserts its
   envelope agrees with the manifest; `long_dir` asserts its own length once;
   a now-implied `rc None` check dropped. Skipped (out of territory, worth a
   task): `schema_dmg` is the fifth per-module copy of
   `test_release_ctx_refusal._rewrite_stream`'s recipe — a `conftest.py`
   `damaged_copy(pin, dst, stream, damage)` helper would retire them all.

### BRANCH STATE

* Branch `cam/573-edit-refusal-basename` from `origin/main` @ 4bd7ecf; one issue, one PR (`Closes #573`).
* Files: `src/rvt/frontdoor/__init__.py` (the one composing line + a two-line comment), `plugin/lib/src/rvt/frontdoor/__init__.py` (sync mirror, byte-identical), `tests/test_edit_status.py` (+`long_dir`/`trunc64k`/`schema_dmg` fixtures, `_assert_named_not_pathed`, the CLI row moved under the long dir, NEW schema-damaged row), this section.
* Gates: `tests/test_edit_status.py` 8 passed + `tests/test_release_ctx_refusal.py` 12 passed (20 in 1.7 s); `tools/sync_plugin.py` rebuilt + `--check` clean ("plugin in sync with source"); `plugin/scripts/validate_plugin.py` PASS (25 assertions); `tools/dev/check_portable_paths.py` ok (2970 paths); whole merged shard (`shard_list.py --print`, 96 files, `RVT_SKIP_LARGE=1 -p no:cacheprovider`): see the PR body for the counts at the reported head.
* Nothing staged for the viewer (sentence wording only; good-edit md5 identity ×3 above). Shipped = the shorter sentence; refused / unverified / PROOF-ONLY compositions byte-identical.
