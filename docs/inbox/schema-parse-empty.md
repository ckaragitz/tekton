# SCHEMA-PARSE-EMPTY — `rvt.schema.parse` raises its own `ParseError` for input with no class record; `tools/rvt_inspect.py` drops its shim (issue #569, Refs #533)

Stream: `schema-parse-empty` (eng #569, engineer session started by the
tech-lead session, 2026-08-10). Territory: `src/rvt/schema.py` (the
empty/short-input branch of `parse_uncached` — the one bottom every public
entry point and the schema cache's build path go through — plus two docstring
lines; grammar, class decoding and every existing `ParseError` message
untouched), `tools/rvt_inspect.py` (the two-line `#569` shim deleted), their
two `sync_plugin.py` mirrors, NEW `tests/test_schema_empty.py` +
`tests/ci_shard.d/569-schema-empty.txt`, this record. `src/rvt/estorage.py`
carries **no** `#569` shim on `origin/main` @ 6ee6f27 (`git grep -n "#569" --
src tools` finds only the `rvt_inspect.py` pair), so it is untouched; its CLI
line for the truncated case changes through the engine alone (§3). No hot
file, nothing under `versions/**`, `release_ctx.py`, `rvt_edit_text.py`,
`rvt_edit.py`.

## 0. The defect, reproduced (fresh cloud clone, `origin/main` @ 6ee6f27, before any change)

```
$ .venv/bin/python -c "from rvt import schema; s = schema.parse(b''); print(len(s.classes)); s.stats()"
0
  File "src/rvt/schema.py", line 303, in stats
    deepest = max(range(len(depths)), key=lambda i: depths[i])
ValueError: max() arg is an empty sequence
```

`_Parser.run()` loops `while pos < n`; for `n == 0` it never runs, and for an
all-zero input shorter than the 16-byte end-of-stream sentinel it records the
bytes as `trailing_pad` and stops — both return a `Schema` with 0 classes,
which `parse` then memoizes under the empty digest `e3b0c442…`. Byte strings
on `main` (`parse_uncached`):

| input | `main` | this branch |
|---|---|---|
| `b""` | Schema, 0 classes | `ParseError: parse error at 0x0: no class records in 0 bytes of Formats/Latest (an empty or truncated schema stream)` |
| `b"\x00"` … `b"\x00"*15` | Schema, 0 classes, pad 1…15 | same sentence, `in 1 bytes` … `in 15 bytes` |
| `b"\x00"*16` | `ParseError … bad class name len=0 @0x0: …` | unchanged |
| `b"\x01"` / `b"\x00\x00\x05"` | `ParseError … truncated: unpack_from requires …` | unchanged |
| `b"definitely not a schema stream"` | `ParseError … class marker != 0 (0x6564) …` | unchanged |
| a pin's schema cut at 40 bytes (mid first class) | `ParseError … truncated: …` | unchanged |

## 1. What was built

* `src/rvt/schema.py::parse_uncached`: after `p.run()`, `if not s.classes:
  raise ParseError(s.consumed, "no class records in {len(data):,} bytes of
  Formats/Latest (an empty or truncated schema stream)")`. `ParseError`'s own
  `parse error at {offset:#x}: ` prefix and its hex-context format for real
  grammar failures are untouched (eng #574 caps how `release_ctx` quotes it;
  this stream does not touch the class). Placed in `parse_uncached` rather
  than `_Parser.run` so the grammar driver is byte-for-byte `main`'s and the
  one raise covers `parse` (memoized), `parse_uncached` (private copies) and
  `rvt.schema_cache`'s build path alike. A raise inside the memo's `build()`
  is never stored, so the empty digest no longer poisons `_MEMO`.
* **Why raise, not a documented 0-class Schema:** every caller read (`git grep
  "parse_schema(\|schema_mod.parse(\|S.parse("`) either wraps the parse in
  `except Exception` and reports the cause in one sentence
  (`validate._load_schema`, `global_framing.enter_own_release`,
  `release_ctx._codec_triple_from_base`, `frontdoor/input_release`,
  `versions.framing_for`, `rvt_inspect`) or immediately indexes
  `by_name[...]` / builds an `ObjectDecoder` (`mutate.Document.from_file`,
  `families`, `estorage._decoder_for`, `standalone.bundled_schema`, the
  `genesis_*` tools) — none has a use for an empty class map, and the ones
  that catch already print `type: message`. Nothing tested for
  `not sch.classes` except the shim this PR deletes.
* `tools/rvt_inspect.py`: the `if not sch.classes: raise ValueError(...)  #569`
  two-liner is gone; its existing `except Exception` guard now reports the
  engine's `ParseError` (§3). Mirror
  `plugin/skills/tekton-native/scripts/rvt_inspect.py` regenerated.

## 2. Every valid schema parses byte-identically

`origin/main`'s `schema.py` loaded side by side with the branch's, both run
over the three tracked pinned bases' `Formats/Latest` (canonical digest =
sha256 over `(type_id, name, parent_id, version, len(guids), [(field name,
kind, flags, type_id, count, extra)…])` per class). The test pins the same
fact without magic constants: `verify_schema(KNOWN_RELEASES[y], s)` (size /
sha256 / class count / unresolved) plus `schema_to_payload(fresh parse) ==
schema_to_payload(disk_loader(sha))` — the shipped `plugin/assets/schema_cache/
<sha>.tksc` is `main`'s parse frozen as a tracked asset, untouched by this PR
(`git status plugin/assets` clean after `sync_plugin.py`).

| base | schema sha256 (== `KNOWN_RELEASES[y].schema_sha256`) | classes | top-level | canonical digest | `to_json` dump sha256 | main vs branch |
|---|---|---|---|---|---|---|
| `G_ABPD.rvt` (2026) | `6459a9a93ebde32c…` | 4690 | 3604 | `8c9ec92c…c117d20e` | `efbd5a9e…46816d63` | identical |
| `G_ABPD_2025.rvt` | `c964f9aa2a5f674e…` | 4600 | 3539 | `24048b7d…635195df8` | `65feab12…af858546` | identical |
| `G_ABPD_2024.rvt` | `0bfb947b3c9a0cec…` | 4492 | 3477 | `029e4a34…c6bf67b8a` | `1dd0e381…d7ede6d1` | identical |

`stats()` (minus `sha256`) digests identical too (`7d1c8d5e…`, `eb89d482…`,
`fb7b51bd…`); `consumed + trailing_pad == len(blob)` (pad 8) on all three.

## 3. The CLIs on a 64 KB truncation (`head -c 65536` of each pinned base), before → after

Exit codes unchanged everywhere; the only textual change is the cause inside
the parentheses becoming the engine's sentence.

* `tools/rvt_inspect.py trunc_<base>.rvt` — exit **1** before and after, stderr
  empty, the stream listing prints, then (all three pins):
  * before: `schema (Formats/Latest): unreadable (ValueError: no classes in 0 inflated bytes) -- nothing below the stream listing can be reported`
  * after:  `schema (Formats/Latest): unreadable (ParseError: parse error at 0x0: no class records in 0 bytes of Formats/Latest (an empty or truncated schema stream)) -- nothing below the stream listing can be reported`
* `python -m rvt.estorage trunc_<base>.rvt --report` — exit **1** before and
  after; the final line is unchanged (`ERROR: cannot load …: RuntimeError:
  Partitions/2x: walker errors ['no trailer for block at …']`); on the two
  foreign pins the preceding `enter_files_release` warning changes:
  * before: `warning: own schema unreadable (VersionError: schema lacks the partition-framing classes ['SegmentMarker', 'SegmentCheckback', 'SignatureMarker', 'ContentMarker', 'ContentKey', 'PartitionTable'] -- not a Revit Formats/Latest schema?); checked against the pinned Revit 2025 framing table (the release BasicFileInfo declares)`
  * after:  `warning: own schema unreadable (ParseError: parse error at 0x0: no class records in 0 bytes of Formats/Latest (an empty or truncated schema stream)); checked against the pinned Revit 2025 framing table (the release BasicFileInfo declares)`
  * the native (2026) pin enters nothing and prints no warning — identical.
* `tools/rvt_validate.py` — text output **identical** before/after on the three
  truncated pins (exit 1; `structure Formats/Latest: schema does not inflate`,
  `semantic Formats/Latest: no schema — semantic layer cannot run`: the
  validator's `_payload` is `None` before any parse) and on the three bases
  themselves (exit 0, 0 errors, same warnings). The one place the new sentence
  reaches the validator is the INFO finding at `release` for a foreign
  truncated file (the same `enter_own_release` note as estorage's warning),
  which the text CLI does not print; `test_validate_release` asserts only
  `"Revit 2025 framing table" in message` and passes.

## 4. Findings / side effects worth a reviewer's eye

* `versions.framing_for(source)` (hot, untouched): with `prefer_schema` it
  re-raises `VersionError` but swallows any other exception into "no schema →
  use the release table". A truncated file used to raise `VersionError` there
  (by-name lookup over the empty map); it now takes the documented fallback to
  the pinned table of the detected release. That is the function's stated
  contract ("if the schema is unavailable falls back to the precomputed
  table"); its only in-repo caller is `versions.reading(source)`, whose
  callers already sit under `enter_own_release`'s ladder. Recorded, not acted
  on (outside territory).
* `release_ctx._codec_triple_from_base` on a truncated foreign host used to
  reach the sha-pin comparison with `e3b0c442…` and raise
  `ReleaseContextError("… refusing to build on an unpinned schema")`; it now
  raises `UnreadableHost("its Formats/Latest class schema cannot be read
  (ParseError: …)")` from the `except` two lines earlier — the truthful one.
  `tests/test_release_ctx_refusal.py` (12) and `tests/test_edit_status.py`
  pass unchanged (their 64 KB row is cut before the schema is reached:
  `RuntimeError … walker errors`).
* No follow-up issue filed: the `estorage.py` shim the charter anticipated
  does not exist on `main`, and no other `not sch.classes` guard exists in
  `src/` or `tools/` (the /simplify altitude pass re-verified all 14
  `parse`/`parse_schema(` call sites).
* /simplify pass (reuse · simplification · efficiency · altitude): applied —
  the test's home-made canonical digest + three hard-coded hex constants
  replaced by the engine's own `verify_schema` + `schema_to_payload` equality
  against the shipped `.tksc`; the two parse entry points parametrized instead
  of looped; a duplicated `str(e)` assertion, a derived `FOREIGN` constant and
  a redundant trailing comment in `rvt_inspect.py` dropped; `parse`'s
  docstring reworded. Skipped, with reason: (a) deleting
  `test_inspect_release.py::test_truncated_file_is_reported_not_raised` /
  folding `b""` into `test_schema_memo.py`'s junk test as duplicate coverage
  — both files are other streams' and the issue's DONE explicitly wants the
  former to keep passing; (b) promoting the now five file-local "64 KB head of
  a pin" fixtures (`test_edit_status`, `test_inspect_release`,
  `test_validate_release`, `test_readers_own_release`, this file) into one
  `conftest.truncated_pin(year, dir)` helper — a shared-file edit across four
  other streams' tests, three lines each; noted here for whoever next touches
  `tests/conftest.py`, not worth an issue of its own; (c) `ParseError(0, …)`
  instead of `ParseError(s.consumed, …)` — kept `s.consumed`, the module's
  convention of passing the parser's position.

## BRANCH STATE

* Branch `cam/569-schema-parse-empty` from `origin/main` @ 6ee6f27, rebased onto bdedb95 (#581) before pushing; one issue, one PR (`Closes #569`).
* Files: `src/rvt/schema.py` (+3 lines in `parse_uncached`, docstrings), `tools/rvt_inspect.py` (−2/+1), mirrors `plugin/lib/src/rvt/schema.py` + `plugin/skills/tekton-native/scripts/rvt_inspect.py` (byte-identical, via `tools/sync_plugin.py`), NEW `tests/test_schema_empty.py` (23 tests), NEW `tests/ci_shard.d/569-schema-empty.txt`, NEW this record.
* Gates: `tests/test_schema_empty.py` 23 passed (0.9 s; 19 before the /simplify parametrization); neighbours `test_inspect_release test_schema_memo test_schema_gate test_coldstart test_estorage test_validate_release test_readers_own_release test_release_ctx_refusal test_edit_status test_versions test_plugin_sync test_bootstrap` together with it: 147 passed, 31 skipped (dev samples absent), 0 failed in 27.8 s; `tools/sync_plugin.py` rebuilt + `--check` clean ("plugin in sync with source"); `plugin/scripts/validate_plugin.py` PASS (25 assertions); `tools/dev/check_portable_paths.py` ok (2976 paths); whole merged shard (`shard_list.py --print`, 99 files incl. the new drop-in, `RVT_SKIP_LARGE=1 -p no:cacheprovider`): **1991 passed, 134 skipped, 3 xfailed, 0 failed in 497.94 s** — run on the engine line exactly as committed (the /simplify pass after it changed only the test file (19 → 23 tests, re-run green together with `test_inspect_release test_plugin_sync test_bootstrap test_coldstart test_surface_perf`: 75 passed in 21.8 s), one comment in `rvt_inspect.py` and two docstring lines in `schema.py`; mirrors re-synced, `--check` clean again).
* /verify at the committed engine line — repo (`.venv`, 3.11) AND a bare unzip of the rebuilt `tekton-plugin.zip` under `env -i` system Python 3.11.15 (`skills/tekton-native/scripts/_bootstrap.py run rvt_inspect.py …`): truncated pins ×3 → rc 1, stderr 0 B, stream listing then exactly the §3 "after" line on both surfaces; intact bases ×3 → rc 0, `4690 / 4600 / 4492 classes`, `--records 5` → `decode summary: {'clean': 5}` on both surfaces; `python -m rvt.estorage trunc_* --report` ×3 → rc 1, stdout 0 B, stderr exactly the §3 lines (native: 1 line, foreign: warning + ERROR); estorage on the intact bases unchanged (rc 0; 2 / 2 / 0-with-#576-reason schemas); `tools/rvt_validate.py` → truncated ×3 rc 1 (2025: 11 errors / 1 warning / 2 infos, the `release` INFO now quoting the ParseError sentence), bases ×3 rc 0 with 0 errors (2026: 1 known DataStorage warning); bare-unzip `_bootstrap.py run rvt_validate.py trunc_2025` rc 1, no traceback; `python3 -c "from rvt import schema; schema.parse(b'')"` from `lib/src` → `rvt.schema.ParseError: parse error at 0x0: no class records in 0 bytes of Formats/Latest (an empty or truncated schema stream)`.
* Nothing staged for the viewer (no output byte changes: parse results and validator output identical on every valid file). Shipped = the typed sentence at the parser boundary; the tool shim removed.
