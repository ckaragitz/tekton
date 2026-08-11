# 655-reduce-v2-end-record -- `reduce_v2`'s partition end record is the ContentMarker ordinal in force, not a by-value `0x3a3`; `remove_units_v2` writes on the 2025 / 2024 pins (shard-docs-audit stream, eng #655)

**Issue:** #655 (filed by eng #646 from its S4 cell; Refs #646 / PR #661, #467 the by-name law, #93 the Global-stream
tokens' home, #14 / O5 the 2025 lane). **Date:** 2026-08-11. **Session:** eng #655 (cloud, `cse_017msFYA`), started by
the tech-lead session. **Base:** `main` @ `3ec84d7`. Index: `docs/inbox/shard-docs-audit.md` (left untouched -- the
README makes the index line optional and that EOF is the hot spot #636 exists to avoid). Written in this engineer's
voice; no other record edited.

## Why

`rvt.reduce_v2.remove_units_v2` (one embedded family document removed COHERENTLY from a project: the save unit spliced
out of `Partitions/<N>`, `Global/ContentDocuments` rebuilt by the solved grammar, `ContentTable` + `FamilyMgr`
reconciled in `Global/Latest`) compared the stream's tail against a module constant
`PART_END_RECORD = struct.pack("<Hii", 0x3A3, 0, -1)`. `0x3a3` is `ContentMarker`'s **2026** ordinal; on a 2025 / 2024
file it is `0x391` / `0x37b`, so even inside the caller's `host_release_context` -- where the `StreamWalker` that found
`end_offset` was already reading `rvt.partitions.CONTAINER_CLASS` by name -- `splice_units` raised
`unexpected partition end record: 9103…` / `7b03…` (#646's record, S4 ¹). One more island of the #467 class.

## What landed

1. **`src/rvt/reduce_v2.py` -- the ordinal resolution only.** `PART_END_RECORD` (by value) is gone; `part_end_record()`
   returns `u16 ContentMarker, i32 0, i32 -1` for the release IN FORCE, i.e. `rvt.partitions.CONTAINER_CLASS` read at
   call time -- the binding `rvt.versions.reading` / `host_release_context` set by name from the file's own schema, and
   the value the walker that located `end_offset` used. It is derived through `rvt.global_framing.tokens()` (no
   argument = the ordinals in force), the module whose docstring names itself the one home of the ContentMarker /
   ContentKey tokens: its `FAMILY_END_RECORD` key is byte-for-byte this record (famdoc_adoc decoded it as "the universal
   stream end record" on six projects + the family archetype); the `FAMILY_` prefix is the decoding module's namespace,
   and #93 owns converging the names -- cited, not touched. Call sites: `splice_units` binds it once (check, error text,
   exact tail, junk count), `verify_content_coherence` once, `diff_old_vs_solved` once for its five length uses. The
   error a caller gets *outside* any release context now says what was expected:
   `unexpected partition end record: 9103… (expected a3030000… under the release in force)`. `import struct` left with
   the constant. Module docstring: `u16 0x3a3` → `u16 ContentMarker (0x3a3 on 2026, read per release)`. Nothing else in
   the module changed; `remove_units_v2` still leaves entering the release to its caller, exactly as before (see
   follow-up); no `assert_edit_free` call site exists in or moved through this module (rule 5 is judged below with
   `reduce_law.check_files`).
2. **`tests/test_reduce_v2.py:26-33`** (sample-gated, same stream) follows the rename: `RV.PART_END_RECORD` →
   `RV.part_end_record()` -- two lines, a genuine edit of an existing test (#636's exception), taken instead of keeping a
   PEP 562 `__getattr__` alias alive on engine code for one skipped assertion (the /simplify pass below).
3. **`tests/test_reduce_v2_655.py`** (new, 10 rows, pinned bases only, `no_release_leak` + `ladder_constants`
   module-wide) + drop-in `tests/ci_shard.d/655-reduce-v2-end-record.txt`:
   - *the ordinal comes from the name lookup:* native == `struct.pack("<Hii", framing_table(2026)["CONTAINER_CLASS"], 0, -1)`,
     10 bytes; under `V.reading(year=2025|2024)` it equals that release's ContentMarker form and differs from native;
     `MonkeyPatch` `rvt.partitions.CONTAINER_CLASS = 0x1234` → the record follows it; back to native after; and
     `hasattr(RV, "PART_END_RECORD")` is False (gone, not aliased).
   - *`remove_units_v2` on each certified pin × {reconciled, registries-left}* (6 rows): the module fixture famloads ONE
     constructor-built section head (`famgen.heads.family_load("section_head_open")`, `uuid.uuid4` pinned to a counter,
     fixed basename) onto each pin -- `rvt.famload` enters the host's release itself -- then, under
     `host_release_context(host)` as every lane holds it, removes that document. Asserted: units 2 → 1 and the removed
     GUID is ours; the written stream's tail **is** this release's end record with nothing after it, and its first u16
     is `framing_table(year)["CONTAINER_CLASS"]`; ContentDocuments 1 → 0, grammar round-trip + end record ok; reconciled →
     `coherent` True and no removed GUID left in ContentTable / FamilyMgr, registries-left → `coherent` False with exactly
     our GUID dangling (the B4 probe shape); `validate_file` (release-aware on its own) ok with **0 errors** and no
     `release` fallback finding; `detect_release(out) == year`; `reduce_law.check_files(host, out)` **EDIT-FREE**, added
     0, survivors edited 0, removed == the unit's own record counter (83).
   - *byte identity vs pinned digests* (3 rows, one per pin): sha256[:16] of the famload'ed host is checked first -- if
     famload / commit / the head constructor / the zlib build ever write a different host, the row **skips** naming the
     input drift (not reduce_v2's to judge; the semantic rows still ran); otherwise both outputs must equal
     `OUT_DIGEST`. The 2026 pair is what `main` wrote (table below).

## Evidence

**The sha / validate table** (driver in the session scratchpad, `drive655.py <outdir>`; deterministic input: `uuid4`
pinned, basenames `host{year}.rvt` / `S4_{year}.rvt`; "before" = unmodified `origin/main` @ `3ec84d7` source, run twice
→ tables equal run-to-run; "after" = this branch; the test module reproduces every "after" digest independently):

| pin (host + 1 section head → sha16) | case | before (`main` @ `3ec84d7`) | after (this branch) |
|---|---|---|---|
| G_ABPD (2026), host `a6d27bfaf4b31a58` | S4 `remove_units_v2(host, [guid])` | `199e0f07b2b33e5c` | `199e0f07b2b33e5c` **==** · coherent · tail junk 0 · VALID 0 errors (1 warning: the known DataStorage decoder gap) · EDIT-FREE removed 83 / added 0 / edited 0 |
| | S4b `reconcile_adocument=False` | `87720c3b48997d76` | `87720c3b48997d76` **==** · coherent False (by design) · VALID 0 errors · EDIT-FREE 83 / 0 / 0 |
| G_ABPD_2025, host `d6b06ae72df4fc02` | S4 | `RuntimeError: unexpected partition end record: 910300000000ffffffff00000000` | `4d841ea2a63fe1c9` · coherent · tail junk 0 · units 2 → 1 · VALID **0 errors** / 0 warnings under its own release (own schema, no fallback rung) · EDIT-FREE removed 83 / added 0 / common 3321 / edited 0 |
| | S4b | same RuntimeError | `1d48e58432f3c1bd` · coherent False (by design) · VALID 0 errors · EDIT-FREE 83 / 0 / 0 |
| G_ABPD_2024, host `3ffab85827c48462` | S4 | `RuntimeError: unexpected partition end record: 7b0300000000ffffffff00000000` | `f456924467c26cfc` · coherent · tail junk 0 · units 2 → 1 · VALID **0 errors** / 0 warnings under its own release · EDIT-FREE removed 83 / added 0 / common 3283 / edited 0 |
| | S4b | same RuntimeError | `32341bb256b08e72` · coherent False (by design) · VALID 0 errors · EDIT-FREE 83 / 0 / 0 |

- The 2026 digests differ from #646's S4 / S4b (`49ba82e9…` / `be56c2f5…`) only because the *input* differs (their host
  carried the generated panelboard under their own uuid pin; that driver lived in their scratchpad); the claim that
  matters -- before == after on one fixed input -- holds on mine, and the test module pins mine.
- Rule 5: `remove_units_v2` deletes the document's 83 records *with* the unit and leaves every one of the 3107 / 3321 /
  3283 survivors byte-identical (`check_files` EDIT-FREE ×6); `git grep -n assert_edit_free src/rvt/reduce_v2.py` →
  nothing, before and after (the gate lives with the genesis lanes' callers, untouched: `git diff origin/main --
  src/rvt/genesis src/rvt/reduce.py src/rvt/reduce_law.py tools/` empty).
- Bare call (no context) on the 2025 host, for the record: `ValueError: unexpected Partitions header: v=9 cls=0x391` from
  the walker's header check -- the same first wall every lane hits when called bare on a foreign file, before and after;
  the lanes enter `host_release_context` themselves, `remove_units_v2` never did (follow-up below).
- Gate suites (`RVT_SKIP_LARGE=1 … -q -rs -p no:cacheprovider tests/test_reduce_v2_655.py tests/test_reduce.py
  tests/test_reduce_law.py tests/test_reduce_v2.py tests/test_rewrite_entries_646.py tests/test_records_layout.py`):
  `origin/main` worktree (new file absent) **54 passed, 26 skipped** → branch **64 passed, 26 skipped** (= main + the 10
  new rows; identical skip list: absent `samples/` / genesis ladders, one root-only permission row).
- Whole merged shard, sequential, same VM (`RVT_SKIP_LARGE=1 .venv/bin/python -m pytest -q -p no:cacheprovider $(python3
  tools/dev/shard_list.py --print)`): **2323 passed, 135 skipped, 3 xfailed** in 467 s on the final diff (BRANCH STATE).
- `tools/route.py matrix`: byte-identical to `origin/main` (39 lines, md5 `e9e2cc8d7f15`). `tools/sync_plugin.py` synced
  1 file (`plugin/lib/src/rvt/reduce_v2.py`), deny-audit clean, `--check` in sync; `plugin/scripts/validate_plugin.py`
  PASS (25 assertions); `tools/dev/check_portable_paths.py` ok; `shard_list.py --print` lists the new module (112 files).

## Findings / limits, stated

- Digests and VALID lines are instruments on pins, not Autodesk's reader (rule 4): nothing here certifies that a
  2025 / 2024 project with a document removed *loads*; no viewer batch is staged and no matrix cell changes.
- The one behavioural difference outside 2025 / 2024: the RuntimeError text for a foreign end record gains the
  `(expected … under the release in force)` clause.

## /simplify pass (four independent angles) -- taken / not taken

Taken: **reuse** -- `part_end_record()` derives through `global_framing.tokens()` instead of a fourth `struct.pack` of
the same law (three spellings existed: famdoc's literal, `tokens()`, and this module's); the test's own
`_validate_own_release` wrapper went (`validate_file` enters the file's release itself and reports a fallback as a
`release` finding -- asserted absent instead) and `_sha16` is `frontdoor.base.sha256_of(...)[:16]`.
**Simplification** -- the PEP 562 `__getattr__` alias for `PART_END_RECORD` (first draft) dropped in favour of the
two-line legacy-test edit; `PART_END_RECORD_LEN` dropped (each site binds the record once and takes `len`); the pinned
`UNIT_RECORDS = 83` became `law.removed == the unit's counter`; `uuid4` pinning is a `MonkeyPatch.context()`
contextmanager; the unit row uses `C.FOREIGN`, no mid-test `undo()`. **Efficiency** -- clean as measured by the agent
(`part_end_record()` ≈ 1 µs, 2 calls per removal; famload module-scoped = 3 loads not 6; the module runs in ~7 s).
**Altitude** -- confirmed: a call-time read of `rvt.partitions` is the mechanism `commit.py:168` / `reduce.py:137` use
and the end state `global_framing`'s docstring prescribes; registering one more constant in `bound()`'s patch list would
have been the interim shape and wrong under a bare `versions.reading`.

Not taken, with the reason: **altitude / simplification** "drop the pinned digests from the shard test" (they hash
famload + commit + zlib output, which the program churns) -- the brief asks for 2026 byte identity against a pinned
digest; kept, but moved to their own rows that *skip with the reason* on input drift and go red only when the input is
the pinned one and reduce_v2's bytes moved, so a famload PR never has to re-pin a reduce_v2 test to get green.
**Altitude** "`remove_units_v2` / `verify_content_coherence` should enter the file's own release themselves like every
other path-taking entry" -- agreed and real (`--coherence FILE` on a 2025 file outside a context reads 0 ContentDocuments
entries, the false incoherence `global_framing` warns about), but it is behaviour beyond "the ordinal resolution only" /
the issue's DONE (which is *under `host_release_context`*): filed as a follow-up.

## Follow-ups (searched first; task-shaped, Refs #655)

- **#671** -- `reduce_v2`'s public entries enter the file's own release themselves (`remove_units_v2` under
  `host_release_context(src)`, `verify_content_coherence` / `--coherence` under `enter_own_release`, rung reported), so a
  bare call on a 2025 / 2024 project works and the coherence census stops misreading foreign files (Refs #655 #14 #93 #252).

BRANCH STATE (cam/655-reduce-v2-end-record): `src/rvt/reduce_v2.py` (`part_end_record()` replaces the by-value
`PART_END_RECORD`; three call sites bind it; error text; docstring line; `struct` import gone), its mirror
`plugin/lib/src/rvt/reduce_v2.py` via `tools/sync_plugin.py`, `tests/test_reduce_v2.py` (two lines follow the rename),
`tests/test_reduce_v2_655.py` (new, 10), `tests/ci_shard.d/655-reduce-v2-end-record.txt` (new), this fragment (new).
Not touched: `src/rvt/versions/**`, `global_framing.py`, `reduce.py`, `reduce_law.py`, `genesis/**`, any hot file, the
stream index. Gates: sha table above (2026 2/2 equal before/after; 2025 / 2024 exception → digest + VALID 0 + EDIT-FREE);
gate suites 54/26 → 64/26; whole merged shard on the final diff **2323 passed, 135 skipped, 3 xfailed, 3 warnings in 467 s** (112 files incl. the new module; `origin/main` @ `3ec84d7` is therefore expected at 2313 / 135 / 3 -- branch minus the 10 new rows, same skip list; a first run on the pre-/simplify draft read 2321 / 135 / 3 with its 8 rows); `/simplify` RAN (above); `/verify` RAN --
`remove_units_v2` has no tool / CLI / skill caller (`grep -rn "reduce_v2\|remove_units_v2" tools/ skills/ plugin/skills
plugin/commands` → nothing; `python -m rvt.reduce_v2` offers only the sample-ladder `--probes` / `--diff` and the
read-only `--coherence`), so the only surface is the function itself: driven via the scratchpad driver on the three pins
(table above, re-driven on the final diff: all six "after" cells identical), `python -m rvt.reduce_v2 --coherence` on
the 2026 S4 output (bare: `coherent true`, end record ok, tail junk 0) and `verify_content_coherence` under
`host_release_context` on the 2025 / 2024 S4 outputs (`coherent True`, 1 unit, 0 CD entries, tail junk 0), and the
user-facing validator CLI `tools/rvt_validate.py S4_{2026,2025,2024}.rvt --json …` → `VALID (no errors)` ×3 (2026:
warnings=1, the known DataStorage ES-blob decoder gap; 2025 / 2024: warnings=0, info=2); `tools/provenance.py S4_{year}.rvt
--baseline all --streams` vs the same on its host: element provenance totals identical per pin (2026 `ours-composed
2680 / ours-created 5 / autodesk-sample 422`, 2025 `2391 / 5 / 925`, 2024 `2355 / 5 / 923`), 0 warnings, only the
Autodesk-resource-identifier count drops by the removed document's 430 strings; gate G1 reads FAIL on host and output
alike -- the pins' standing residue / inherited-GUID state (#19 / #21, O8), untouched by a unit removal. The 5
`ours-created` host elements famload added (Family / symbol / surrogates) stay byte-identical after their document goes:
the reduction law's "left byte-identical" branch (deleting hosts first is `reduce.delete_elements`' rung, as R9 → R9b). `tools/sync_plugin.py` rebuilt + `--check` clean, `validate_plugin.py` PASS,
`check_portable_paths.py` ok. Nothing staged for the viewer; no certification claim; `tekton-plugin.zip` regenerated
locally, not committed.
