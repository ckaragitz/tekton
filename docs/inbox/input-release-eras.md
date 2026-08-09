# INPUT-RELEASE-ERAS — `author --rvt FILE --edit …` classifies the input's era on every job (issue #176)

Stream: `input-release-eras` (engineer session eng176 on #176, started by the
tech-lead session). Territory: `src/rvt/meta.py` (`classify_bfi_era`), the new
`src/rvt/frontdoor/input_release.py`, `src/rvt/frontdoor/__init__.py`
(`_route_rvt` precheck only), `src/rvt/frontdoor/manifest.py` (status wording +
the `## Input release` section), `tests/test_input_release.py` + one line at the
end of `tests/ci_shard.txt`, `docs/product/PERMUTATION-MATRIX.md` (the
`prompt + rvt → rvt` row's rvt-read note), regenerated `plugin/lib/**`, this
record. Not touched: `src/rvt/versions/**`, `src/rvt/frontdoor/base.py`,
`tools/frontdoor.py`, `src/rvt/frontdoor/edit.py`, `tools/rvt_edit.py`
(all hot / #70's). Builds on #70 / #14 (`release_ctx.enter_host_release`) and
#121 (`global_framing.enter_own_release`) — both already on `main`, called,
never edited.

## 0. The defect, reproduced (origin/main @ 950d4b6, fresh cloud clone)

```
$ printf 'not a cfb at all\n' > garbage.rvt
$ tools/frontdoor.py author --rvt garbage.rvt --edit "move DP-1 to 3,1,4.66" --out o --json
Traceback (most recent call last):
  … release_ctx.py:301 _release_context → :231 _classify_release → versions/__init__.py:295
  detect_release → :277 _open_doc → container.py:108 → olefile … NotOleFileError:
  not an OLE2 structured storage file
exit=1        (no manifest, no JSON, a 20-line traceback)
```

Read, not guessed: `_route_rvt` entered `enter_host_release` before any look
at the input; `enter_host_release` only catches `ReleaseContextError`, and
`V.detect_release(path)` opens the container *outside* its own try (only the
BFI/schema reads are guarded), so a non-CFB input escapes as a raw olefile
exception. A truncated-but-CFB 2026 file already failed honestly (`FAILED
(edit did not complete)`, exit 3, "walker errors" named) — that path is fine.
`meta.parse_basic_file_info` decodes only the 2019+ (`structure_version` 14)
layout; nothing classified the 2008–2018 `Revit Build:` layout, and a 2019–2022
year (outside `KNOWN_RELEASES`) fell through `enter_host_release`'s refusal
note into a native (2026-framed) `Document.from_file`.

## 1. What was built

- **`rvt.meta.classify_bfi_era(raw) -> {'era': '2019+'|'2008-2018'|'unknown', 'year': int|None}`**
  — searches the raw stream for the UTF-16LE markers `Format:` (2019+) then
  `Revit Build:` (2008–2018) as byte substrings (so the odd byte offset the
  mirror text sits at is irrelevant), and reads the first `20xx` on *that
  mirror line only* (a `Format:` line with no year never borrows the `Build:`
  stamp below it). Total — never raises. Constants `BFI_ERA_2019/2008/UNKNOWN`.
  Source of the grammar: `docs/prior-art.md` P1 (Archive Team era table) / P3
  (DROID container signatures) — public, sample-free.
- **`rvt.frontdoor.input_release.input_release_block(path)`** — the manifest's
  `input_release` block `{path, era, year, floor, status, note|stamp|line}`,
  decided from the two cheap signals (BFI era/year by marker; else
  `V.detect_release(doc)` on the *open* container — the detector every other
  consumer uses: BFI's binary `format`, then the `Formats/Latest` signature):
  - `known` — year ∈ `KNOWN_RELEASES` → proceeds exactly as before. Cost on the
    pinned 2026 base: **0.26 ms measured** (one container open + one raw stream
    read; no schema parse added to the common path — S-2026-08-09-g); the year it
    found is handed to `_rvt_route_version_block(target, year)` so the route no
    longer detects the input's release a third time.
  - `unverified` — 2019+ layout, year outside the roster (older *or* newer),
    and `V.ordinals_from_schema(global_framing.schema_of(path))` succeeds (the
    memoised parse the read ladder reuses) → proceeds; block carries
    `stamp = UNVERIFIED-RELEASE: no file of this release has been read by tekton
    before; validate before trusting`.
  - `refused` — era `2008-2018`; no `Formats/Latest`; no year from either
    signal; own schema unparseable; or not an OLE2 file → `line` = ONE line:
    `REFUSED (input release): <name> is <era/year phrase> (<reason>); tekton
    reads Revit 2023+ and edits Revit 2024+ (2024, 2025, 2026) -- re-save it in
    Revit 2023 or newer, or hand over an IFC export of it instead (frontdoor
    author --ifc FILE.ifc)`. The floor numbers come from `verified_floor()` =
    `{"read": sorted(KNOWN_RELEASES), "edit": target_status.supported_targets()}`
    — no year literal, one vocabulary with the skills' `supported_targets`.
- **`_route_rvt`** computes the block first on every job. `refused` → writes the
  refusal manifest (`edit_manifest(..., input_release=blk)`, status = the line,
  `## Input release` in MANIFEST.md) and raises **`InputReleaseRefused(FrontDoorError)`**
  whose `str()` is the line and whose `.result` is the `AuthorResult` — the CLI's
  existing `except FD.FrontDoorError` prints `[frontdoor] usage error: <line>` and
  returns `EX_USAGE` = **2**; no traceback; `tools/frontdoor.py` untouched.
  Whenever `enter_host_release` returns its refusal note (no authoring context:
  an uncertified or out-of-roster year), the read side is now put under the
  file's own schema with `global_framing.enter_own_release` (the instruments'
  lenient ladder, #121) so open/plan are schema-directed rather than 2026-framed;
  a non-trivial rung is appended to the note. Keyed on the *condition* (no
  context), not on the new label — so a 2023 input (known, uncertified) would get
  the same read framing as a 2021 one; its edit still cannot be authored (no
  context) and is expected to stop honestly at re-emit (`FAILED (edit did not
  complete…)`) instead of at open — **not exercised here: no 2023 file exists in a
  fresh clone** (samples/ absent), so that expectation is reasoning, not a reading.
  2024–2026 enter the host context and never reach this rung (outputs
  byte-identical, §2a); the synthetic 2020 input does reach it and delivers (§2b).
- **`manifest.edit_manifest(input_release=…)`**: the block rides as
  `m['input_release']`; the status is computed once (job status → FAILED override
  → refused line | `; UNVERIFIED-RELEASE (input Revit <year>)` suffix via the
  exported `UNVERIFIED_TAG`); the stamp and the refusal line are *inputs* to
  `_honesty(extra_stamps=, release_line=)` — the honesty box stays the one home
  (so `--json` `stamps` carries the stamp via the existing `as_json`, and a refused
  2014 input's `honesty.release` is the refusal line, not "Revit 2026 target …").
  `MANIFEST.md` gains a `## Input release` section.

Rule-1 nuance (stated in the issue): refusing an *unreadable* input withholds
nothing — there is no output to withhold; every readable input still delivers,
stamped. Rule 3: every test byte is authored in-test (marker grammar) or is our
own tracked composed base re-encoded by our own encoder; no sample is read.

## 2. Evidence

### 2a. Known releases: outputs byte-unchanged, manifest only GAINS the block

Same edit (`set level 1351691 elevation to 5 ft`, `SOURCE_DATE_EPOCH=1780000000`)
on copies of the three pinned bases, `origin/main` worktree vs this branch:

| input | exit before/after | output sha256[:16] before → after | manifest diff (normalised for out-dir/timestamps) | `--json release` | validator on output |
|---|---|---|---|---|---|
| `G_ABPD.rvt` (2026) | 0 / 0 | `da9b3c9080de987e` → `da9b3c9080de987e` | added `input_release` only; 0 keys changed/removed | equal | ok, 0 errors / 1 warning (known DataStorage ES gap) |
| `G_ABPD_2025.rvt` | 0 / 0 | `2eadf79e27e0e5c8` → same | added `input_release` only | equal | ok, 0 / 0 |
| `G_ABPD_2024.rvt` | 0 / 0 | `059014e614993495` → same | added `input_release` only | equal | ok, 0 / 0 |

`input_release` on each: `{status: known, era: 2019+, year: 2026|2025|2024, note:
"Revit N: a release tekton reads", floor, path}`; status string unchanged
(`PROOF-ONLY, NOT-DELIVERABLE (hard gates PASSED)`); stamps `[]`. Re-run after the
`/simplify` pass: same three output hashes, same manifest diff (only `input_release`
added).

### 2b. Unverified: a synthetic "Revit 2020" input proceeds, delivered + stamped

Input = our `G_ABPD.rvt` rewritten by `cfb_writer.write_cfb` with its
`BasicFileInfo` re-encoded (`encode_basic_file_info`) to `Format: 2020`:

```
exit=0   status: PROOF-ONLY, NOT-DELIVERABLE (hard gates PASSED); UNVERIFIED-RELEASE (input Revit 2020)
stamps: ['UNVERIFIED-RELEASE: no file of this release has been read by tekton before; validate before trusting']
files: {edited: …/as2020.edited.rvt}      validator: ok, 0 errors / 1 warning
input_release: {status: unverified, era: 2019+, year: 2020, stamp: UNVERIFIED-RELEASE: …,
                note: "Revit 2020 is older than any release tekton has read (2023-2026); its own class
                schema parses, so the job proceeds under that schema"}
stderr: one `[rvt_job] warning: no release context … Revit 2020 is not a certified creation release …` line, no traceback
```
(A real 2020 file's edit may still fail downstream in the 2026-tagged re-emit —
then it fails *honestly* as `FAILED (edit did not complete …)` with the reason,
still stamped; nobody has such a file here to say more. That is what
UNVERIFIED means.)

### 2c. Refused: pre-2019 layout and garbage → exit 2, one line, manifest, no traceback

```
$ tools/frontdoor.py author --rvt pre2019.rvt --edit "move DP-1 to 3,1,4.66" --out o --json     # synthetic CFB: BFI 'Revit Build: Revit Architecture 2014 (Build: …)', dummy Formats/Latest
[frontdoor] usage error: REFUSED (input release): pre2019.rvt is a Revit 2014 file in the pre-2019 BasicFileInfo layout (Revit 2008-2018 write BasicFileInfo as 'Revit Build: ...'; tekton decodes only the 2019+ 'Format: ...' layout and has never read a file of this era); tekton reads Revit 2023+ and edits Revit 2024+ (2024, 2025, 2026) -- re-save it in Revit 2023 or newer, or hand over an IFC export of it instead (frontdoor author --ifc FILE.ifc)
exit=2
$ tools/frontdoor.py author --rvt garbage.rvt --edit … --out o --json                          # 17 bytes of text
[frontdoor] usage error: REFUSED (input release): garbage.rvt is not a Revit file tekton can classify (not an OLE2 compound file: NotOleFileError); tekton reads Revit 2023+ and edits Revit 2024+ (2024, 2025, 2026) -- re-save it in Revit 2023 or newer, or hand over an IFC export of it instead (frontdoor author --ifc FILE.ifc)
exit=2         o/manifest.json status == that line; o/MANIFEST.md has "## Input release"; input_release.status == refused
```

### 2d. Tests

`tests/test_input_release.py` — **28 passed in 1.5 s** (in `tests/ci_shard.txt`):
12 synthetic-stream classifier cases (both eras, odd/even offset, marker without
year, both markers, empty/zero/foreign bytes), our three bases classify as
2019+/their year (parametrized), `verified_floor` derived from the version model, 6 refusal
shapes of the block (pre-2019, no year, unread year + unparseable schema, no
schema, empty CFB, non-CFB) each asserting the one line's contents, known =
cheap + unstamped, unverified older *and* newer, the route's three branches
(refusal: `InputReleaseRefused` is a `FrontDoorError` carrying the result +
manifest on disk whose `honesty.release` is the line + CLI `main()` returns 2 with no `Traceback` on stderr; known:
ok, block present, no stamp, #24's `target_version.input_release` unchanged;
unverified: delivered + stamp in manifest, status and `--json` stamps), and the
shard listing. Gates: `tests/test_frontdoor.py tests/test_readers_own_release.py
tests/test_versions.py tests/test_edit_own_release.py tests/test_input_release.py`
→ **134 passed, 23 skipped** (all skips = `samples/` absent), 36 s, `RVT_SKIP_LARGE=1`.

## 2e. `/simplify` pass (4 review angles) — applied vs. deferred

Applied: block slimmed to keys something reads (`known`, `*_min`, `year_source`,
`read_ladder` dropped; stamp no longer repeated inside `note`); `verified_floor`
reuses `target_status.supported_targets()`; year fallback = `V.detect_release(doc)`
on the already-open container (context-managed) instead of a hand-rolled copy of
its evidence order; `_refusal_line(blk, reason)`; `UNVERIFIED_TAG` exported (no
`split(':')` of a sentence); stamps/release line passed *into* `_honesty` and the
edit status computed in one place; `_refuse_rvt_input -> NoReturn`; the third
per-job release detection removed (`_rvt_route_version_block(target, year)`); read
ladder keyed on `ctx_note`; `classify_bfi_era` = one marker loop + one compiled
line-bounded regex; matrix wording narrowed to `frontdoor author --rvt` (the
`go edit`/`rvt_edit.py`/`rvt_job.py edit` entries don't have the gate yet). Measured
by the efficiency reviewer: precheck 0.26 ms on a ~670 ms known-release job (0.04 %),
no schema inflate/parse or new heavy import on the common path; refused path strictly
cheaper than before. Deferred (right home is outside this territory → follow-ups
below): a shared `versions.classify_release` / `detect_release` not leaking
`NotOleFileError`; `enter_host_release` composing the read ladder itself; the CLI
printing the refusal `--json`; `reading32` taking the memoised schema (~5 ms on the
rare unverified branch, #251's neighbourhood).

## 3. Findings / open questions (filed where task-shaped: **#334** hot-file `detect_release` non-OLE + CLI `--json` on refusal; **#335** `go edit` / `rvt_edit.py` / `rvt_job.py edit` share the gate + `enter_host_release` composes the read ladder)

- `V.detect_release(path)` still lets a non-CFB path escape as `NotOleFileError`
  (its docstring promises None/`UnknownRelease`); the front door no longer reaches
  it with such a path, but `tools/rvt_edit.py info garbage.rvt`, `rvt_job.py edit`
  and `release_ctx.needs_release_context` still would. `src/rvt/versions/` is hot
  and `rvt_edit.py` is #70's — **patch for a hot-file PR**, not applied here:
  ```diff
  --- a/src/rvt/versions/__init__.py  detect_release()
  -    doc, must_close = _open_doc(source)
  +    try:
  +        doc, must_close = _open_doc(source)
  +    except Exception as e:            # not an OLE2 file at all
  +        if strict:
  +            raise UnknownRelease(f"cannot open {source!r} as a Revit compound file: {e}") from e
  +        return None
  ```
  and for `tools/rvt_edit.py` (#70's territory) the same three-way precheck is one call:
  ```diff
  +    from rvt.frontdoor.input_release import input_release_block
  +    blk = input_release_block(a.file)
  +    if blk["status"] == "refused":
  +        print(blk["line"], file=sys.stderr); return 2
  ```
- Optional UX follow-up for the hot CLI (`tools/frontdoor.py`): on
  `InputReleaseRefused` with `--json`, also print `e.result.as_json()` so `go`
  gets a `result` object instead of `null` + the stderr line. Two lines inside the
  existing `except FD.FrontDoorError` arm; exit code stays 2. Not required by the
  DONE (the skills document exit 2 = usage with no result).
- The `rvt → ifc` / `rvt → rfa` cells read through `rvt.convert`, not `_route_rvt`;
  they get #121's ladder but not this era precheck. Same one-call adoption as
  `rvt_edit.py` above if wanted (`rvt.convert` is convert-a's territory).
- Year heuristic for the 2008–2018 line: the first `20xx` on the `Revit Build:`
  line is the product year when present ("… Architecture 2014 (Build: 2013…)"
  → 2014); a product string without a year yields the build-stamp year. Only
  used for the refusal wording — the era, not the year, drives the decision.

## BRANCH STATE

- Branch `cam/176-input-release-eras` from `main` @ 950d4b6.
- Files: `src/rvt/meta.py` (+`classify_bfi_era`, era constants, `import re`),
  `src/rvt/frontdoor/input_release.py` (new), `src/rvt/frontdoor/__init__.py`
  (`InputReleaseRefused`, `_route_rvt` precheck, `_refuse_rvt_input`,
  `_route_rvt_inner(in_rel)`), `src/rvt/frontdoor/manifest.py`
  (`edit_manifest(input_release=)`, md section), `tests/test_input_release.py`
  (new), `tests/ci_shard.txt` (+1 line at the end), `docs/product/PERMUTATION-MATRIX.md`
  (row `prompt + rvt → rvt`), `plugin/lib/**` regenerated by `tools/sync_plugin.py`,
  this record.
- Gates: see §2d, plus after the `/simplify` pass: `tests/test_frontdoor.py test_readers_own_release.py test_versions.py test_edit_own_release.py test_input_release.py test_router.py test_plugin_sync.py test_bootstrap.py test_coldstart.py test_surface_perf.py test_go_edit.py` → **237 passed, 39 skipped** (samples-only cases + the bare-numpy perf gate on this host), 51 s; `tools/sync_plugin.py` then `--check` clean;
  `plugin/scripts/validate_plugin.py` PASS; `tools/dev/check_portable_paths.py` clean.
- Follow-ups filed: #334, #335.
- Nothing staged for the viewer (no new artifact shape: known-release outputs are
  byte-identical to `main`'s; the unverified/refused branches produce no
  certifiable claim).
