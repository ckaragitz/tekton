# 646-rewrite-entries-folds -- ten of the eleven remaining hand-rolled container re-emits fold onto `rvt.roundtrip.rewrite_entries` byte-identically; the pass grows bytes-like edits and an atomic in-place path (shard-docs-audit stream, eng #646)

**Issue:** #646 (filed by eng #640; Refs #640 / PR #648 for the API, #617, #639). **Date:** 2026-08-11.
**Session:** eng #646 (cloud, `cse_012BkUUL`), started by the tech-lead session. **Base:** `main` @ `697928f` (#651 merged).
Index: `docs/inbox/shard-docs-audit.md` (left untouched -- the README makes the index line optional and that EOF is the
hot spot #636 exists to avoid). Written in this engineer's voice; no other record edited.

## Why

#640 gave the engine ONE entry-rewrite pass and folded `writer.py`'s four variant builders onto it; its record measured
the same `read_entries -> dataclasses.replace -> write_cfb` loop at eleven more sites and filed #646 for them, and the
tech lead's notes on PR #648 added three API points for whoever adopted the in-place *product* site: (a) `src == dst`
must not be able to tear the user's file, (b) `isinstance(edit, bytes)` sent `bytearray` / `memoryview` down the
callable branch, (c) `rewrite_entries` does not `makedirs`.

## What landed

1. **`src/rvt/roundtrip.py::rewrite_entries` -- body + docstring only, signature unchanged.**
   - *(b) bytes-like, decided "accept", not "document louder":* an edit is applied as
     `new = edit(raw) if callable(edit) else edit`; `new` must be `bytes | bytearray | memoryview` (else
     `TypeError("stream '<path>': an edit is bytes-like, a callable returning bytes-like, or None -- got <type>")`)
     and is stored as `bytes(new)`. So a `bytearray` outright, a `memoryview`, or a callable *returning* either, all
     land as the same bytes; a `str` / `int` / callable-returning-`None` is a `TypeError` naming the stream, raised in
     the read loop -- i.e. before `dst` is opened, like the `KeyError`. Why accept rather than refuse: the engine's own
     splicers build `bytearray`s (`manipulate`, `reduce`, `commit`, `mep/*` all `out = bytearray(...)` before
     `bytes(out[...])`), `CfbEntry.data` must be real `bytes` for `write_cfb`'s slicing and for `read_entries` parity,
     and `bytes(x)` on an exact `bytes` object is the identity (no copy) -- so the widening costs nothing on the hot path
     and removes a trap. `StreamEdit` now reads `BytesLike | Callable[[bytes], BytesLike] | None`.
   - *(a) in place is atomic:* when `dst` exists and `os.path.samefile(src, dst)` (the same file however spelled --
     relative vs absolute, a hard link, a symlink), the entries go to `tempfile.mkstemp(prefix=<name>., suffix=.tmp,
     dir=<dir of realpath(dst)>)`, the file's own permission bits are copied onto the temp (`mkstemp` creates 0600),
     and `os.replace(tmp, realpath(dst))` swaps it in only once `write_cfb` returned -- POSIX-atomic because the temp is
     a sibling (same directory => same filesystem). Any exception (the injected `OSError` in the test, a
     `KeyboardInterrupt`) removes the temp and propagates; the source is byte-for-byte what it was. `realpath` so a
     `dst` that is a *link* to `src` rewrites the file and leaves the link a link (the old `open(dst, "wb")` wrote
     through the link too). A distinct `dst` is written directly, exactly as before and as `write_cfb` does -- no temp,
     no rename -- so every non-in-place caller's filesystem behaviour (symlinked outputs, directory permissions) is
     unchanged; the case that gets the extra `rename` is the one where a torn write destroys the *input*.
   - *(c) `dst`'s directory, decided "must exist", documented:* the pass creates streams, not directory trees; a
     mistyped `dst` is a `FileNotFoundError` from `open`, raised before a byte is written, rather than a silently
     materialised tree; `roundtrip()` and the two callers that want `makedirs` (`families.emit_rfa`,
     `famload._load_family_documents`) already do it one line earlier and keep doing so. Pinned by a test row.
   - Module docstring names the engine callers the pass now has.
2. **Ten sites folded** (each the minimal hunk; imports trimmed to what the module still uses):

   | site | fold | notes |
   |---|---|---|
   | `commit.py::commit_new_elements` | `rewrite_entries(src_rvt, out_path, new_streams)` | the early `entries = read_entries(src_rvt)` existed only to find `BasicFileInfo` for the identity step; that lookup is now `doc.raw("BasicFileInfo") if doc.has("BasicFileInfo") else None` inside the `open_rvt` block the function already holds (`RvtDocument.raw` *is* the olefile stream = `CfbEntry.data`), so the source is read once, not twice. Module imports: `write_cfb`, `read_entries` gone; `dataclasses` stays (`CommitReport`). |
   | `manipulate.py::commit_plans` | `rewrite_entries(src_rvt, out_path, new_streams)` | `entries` was passed to `_primary_partition(doc, entries)`, whose second parameter is unused by its body (`records32` and `verify_manipulated` already pass `None`); now `None` here too. Signature of `_primary_partition` left alone (`versions/records32.py` is hot). |
   | `reduce.py::delete_elements` | `rewrite_entries(src_rvt, out_path, new_streams)` | rule 5: `assert_edit_free` lives in the *callers* (`genesis/y2025_b.py:971`, `y2024_b.py:942`, `tools/genesis_deletion.py`) and judges the written file; the fold moves nothing and the file is byte-identical (S3 below), verdicts re-run: EDIT-FREE ×3 before = after. |
   | `reduce_v2.py::remove_units_v2` | `rewrite_entries(src, out_path, new_streams)` | keys: partition, `Global/ContentDocuments`, `Global/Latest`, all just inflated from `src`. |
   | `famload.py::_load_family_documents` (pass 2) | `rewrite_entries(tmp1, stage_out, new_streams)` | keys all read from `tmp1` in the same function. |
   | `families.py::emit_rfa` | `rewrite_entries(src, out, new_data)` | keys are `f.streams()` names of `src`; its own `os.makedirs` line kept. |
   | `mep/conduit.py::commit_created` | `rewrite_entries(src_rvt, out_path, new_streams)` | same `BasicFileInfo`-via-`f.raw` move as `commit.py`; `import dataclasses` dropped (nothing else used it). |
   | `mep/electrical_data.py::commit_electrical` | `rewrite_entries(src_rvt, out_path, new_streams)` | same two moves (`_primary_partition(d, None)`, `bfi = d.raw(...)`), both `own_identity` branches in the sha table. |
   | `adocument.py::write_with_latest` | `rewrite_entries(src_rvt, out_rvt, {STREAM: framed})` | the replaced-exactly-once check went: zero is the API's `KeyError` (was `RuntimeError`; docstring says so, test pins it, no caller catches either), twice cannot happen (paths are unique per `write_cfb`). |
   | `convert/modify_family.py::_patch_partatom` | `rewrite_entries(path, path, {"PartAtom": out_xml.encode("utf-8")})` | THE in-place product site (a user's `.rfa`): now atomic per 1(a); docstring says so. |

   **The one semantic difference, per site** (issue DONE 3): a `new_streams` key that is not a stream of the source used
   to be silently not written; it is now a `KeyError` before the write. At all ten sites every key is a stream that was
   just read (inflated / raw'd / listed) from the very container being rewritten -- `pname` from `partition_streams()`,
   `Global/ElemTable` / `Global/Latest` / `Global/ContentDocuments` from `doc.inflate*`, `BasicFileInfo` only when
   `doc.has` it, `Global/DocumentIncrementTable` only after `doc.raw` succeeded, `emit_rfa`'s names from `f.streams()` --
   so no guard is needed and none was added.
3. **Left, one line each** (issue: "sites whose shape does NOT match are NAMED and LEFT"):
   - `famgen/loader.py:1945-1947` -- shape matches, but `famgen/**` is outside this engineer's territory as briefed, and
     `tests/test_famload_batch.py::_CountWrites` counts the loader's *call-time* `rvt.cfb_writer.write_cfb` import (a
     fold binds `write_cfb` inside `roundtrip` at import and would silently zero that seam) -- a famgen-owned PR should
     move the seam and the loop together.
   - `regadd.py:604` -- holds `self.entries` across many edits (a fold re-reads the file per write); not this shape.
   - `famgen/famdoc_adoc.py:1832`, `famgen/skeleton.py:3185`, `convert/rfa_assemble.py:175` -- entry lists built from
     scratch, no source container; `famgen/geometry.py:3022` -- donor-lineage dev path. Not this shape (as #640 said).
4. **`tests/test_rewrite_entries_646.py`** (new, 13 rows, pinned bases only, `no_release_leak` module-wide) + drop-in
   `tests/ci_shard.d/646-rewrite-entries-folds.txt`: every bytes-like edit form lands as the same bytes and is stored as
   plain `bytes`; four non-bytes-like edits → `TypeError` naming the stream, no file; **an injected `write_cfb` that
   writes half the real output then raises `OSError(28)`**: in place → source byte-identical to before, directory holds
   only the source (temp removed), the dying write was aimed at a sibling temp, never at `src`; the same injection on a
   distinct `dst` → aimed at `dst` directly (no temp for the ordinary case); in place keeps mode 0644 (not 0600), equals
   the apart rewrite, leaves no temp; a symlink `dst` → `src` rewrites the file and stays a link; a `dst` in a missing
   directory → `FileNotFoundError` and the directory is not created; `write_with_latest` replaces only `Global/Latest`
   (re-decodes clean under the pin's release) and a Latest-less source is `KeyError` with nothing written;
   `_patch_partatom` on a container given a `PartAtom` entry: no occurrence → `changed False` and the file untouched,
   a rename → only `PartAtom` differs, counts/bytes reported, no temp behind; `commit_plans(p, p, plan)` in place ==
   `commit_plans(pin, apart, plan)` byte-for-byte. `tests/conftest.rewrite_streams` unchanged; #648's
   `test_cfb_rewrite_entries.py` (10) and #651's `test_conftest_scaffolding.py` law rows green unchanged.

## Evidence

**Byte identity of the folds** -- `origin/main` @ `697928f` vs this branch: sha256 of each folded function's documented
use with deterministic inputs, per pinned base, foreign pins under `host_release_context` (schema installed the way the
front door does, `standalone.install_schema`). Driver kept in the session scratchpad (`sha_table.py <outdir>
before|after|compare`); "before" was run twice on main first (36/36 equal run-to-run, i.e. the inputs are deterministic:
`uuid.uuid4` pinned for famload, fixed basenames so `BasicFileInfo`'s save path agrees), then "after" on the final diff:
**36/36 EQUAL** (32 digests + the 4 n/a cells below, identical error text before and after).

| case \ base (sha256, first 16 hex; before == after) | G_ABPD (2026) | G_ABPD_2025 | G_ABPD_2024 |
|---|---|---|---|
| S1 `commit.commit_new_elements` (one constructed-specimen instance, `identity={"username": ""}`) | 1adc01305864a7e8 | 93a8824540d3f808 | b5108a7e5040a1bf |
| S2 `manipulate.commit_plans` (`set_level_elevation` +1.25 ft, the front door's edit shape) | 202400344606f09f | e9bf8d100350389a | 4c716d6b884b7463 |
| S2b the same with `src == out` (in place; == S2) | 202400344606f09f | e9bf8d100350389a | 4c716d6b884b7463 |
| S3 `reduce.delete_elements([1351691])` (the genesis lanes' deleter) | f0cf7c6850574e80 | c3fd80b1d040ceac | e438cc5deb222d0d |
| S4 `reduce_v2.remove_units_v2(S5's output, [its guid])` | 49ba82e98eba3403 | n/a ¹ | n/a ¹ |
| S4b the same, `reconcile_adocument=False` | be56c2f5ebf87045 | n/a ¹ | n/a ¹ |
| S5 `famload.load_family_documents(pin, [panelboard], out)` | ca2051c6d76f13d7 | 88499a96c36f1138 | 791b5116800f8cea |
| S7 `mep.conduit.commit_created` (a `ConduitPlan` carrying the S1 element ²) | 9785ce33b3c1d0e2 | 70049f1b67bc52c6 | 560652362fb3f09d |
| S8 `mep.electrical_data.commit_electrical(new_elements=[S1 element])` | 104963294b74064c | 16e8b86cc143b530 | 2982cdcb1aab2b12 |
| S8b the same, `own_identity=True` | e8eb85d5344c6675 | 59582759bf004b84 | aa71cd55df89849e |
| S9 `adocument.write_with_latest(pin, out, encode(decode(pin's Latest)))` | 84173b8960b8cbba | 6242c3aaccf86e71 | e4a40671d8b6c649 |
| S6 `families.emit_rfa(<our generated panelboard .rfa>, out)` ³ | 2fc4f6fe4b2c7ef8 | | |
| S10 `modify_family._patch_partatom(<copy of that .rfa>, [(title, title+"-RENAMED-646")])` in place ³ | a7837bd4dc0770e3 | | |
| S11 `modify_family.modify_family(<that .rfa>, "rename the type to …")` -- the route, PartAtom follow included ³ | 74582b084220021b | | |

¹ pre-existing and not this diff: `remove_units_v2` holds a by-value `PART_END_RECORD` (`0x3A3`) and raises
`unexpected partition end record: 9103…` / `7b03…` on the foreign pins, before *and* after -- filed as **#655**
(#467-class, Refs #646). ² the pins carry no conduit specimen to plan from, so the plan carries the constructed instance:
it drives `commit_created`'s splice + ElemTable + identity + write, which is the code that changed. ³ input = one `.rfa`
generated once by `tools/route.py run --prompt "a 400A eaton panelboard family…" --output rfa` and reused for both runs
(the pin axis does not apply).

- Rule 5, the reduction lanes: `reduce_law.check_files(pin, S3 output)` on all three pins, before and after →
  `EDIT-FREE, removed 1, added 0` ×6; the gate in `y2025_b.py` / `y2024_b.py` / `genesis_deletion.py` is untouched
  (`git diff origin/main -- src/rvt/genesis src/rvt/reduce_law.py tools/` empty).
- `git grep -n "write_cfb(" -- src/rvt | wc -l`: **21 → 12**; remaining: `cfb_writer.py` ×3 (def, docstring, self-test),
  `roundtrip.py` ×3 (`roundtrip()`, the pass's two branches), and the six left sites named in 3
  (`convert/rfa_assemble.py:175`, `famgen/famdoc_adoc.py:1832`, `famgen/geometry.py:3022`, `famgen/loader.py:1947`,
  `famgen/skeleton.py:3185`, `regadd.py:604`). `read_entries(` outside `roundtrip.py`: `famgen/geometry.py`,
  `famgen/loader.py`, `regadd.py` only.
- Gate suites (`RVT_SKIP_LARGE=1 … -q -rs -p no:cacheprovider` over `test_cfb_rewrite_entries test_rewrite_entries_646
  test_conftest_scaffolding test_roundtrip test_reduce test_reduce_law test_reduce_v2 test_commit test_manipulate
  test_manipulate_import_context test_convert test_convert_combo test_modify_family_carrier test_adocument test_families
  test_famload test_famload_2025 test_famload_batch test_famload_fix test_mep_conduit test_mep_devices
  test_mep_electrical_data test_edit_own_release test_verify_manipulated_release test_framing_by_name test_objects_plans
  test_hostsym_product test_circuits test_hosting test_genesis2_adocument`): `origin/main` worktree (new file absent)
  **210 passed, 176 skipped** → branch **223 passed, 176 skipped** (= main + the 13 new rows; the 176 skips are absent
  `samples/` / research inputs / `RVT_SKIP_LARGE`, identical lists).
- Whole merged shard, sequential, same VM (`RVT_SKIP_LARGE=1 .venv/bin/python -m pytest -q -p no:cacheprovider $(python3
  tools/dev/shard_list.py --print)`): branch **2293 passed, 134 skipped, 3 xfailed, 3 warnings** in 390 s -- the shard
  now includes the new file's 13 rows, so `origin/main` @ `697928f` is expected at 2280 passed with the same skips /
  xfails (its worktree run was started after this line was written; the PR thread carries the measured figure).
- `/simplify`, `/verify`, sync / validate / portable: see BRANCH STATE.
- Latency (S-2026-08-09-g): no site reads its source more often than before -- the three identity sites lost a full
  `read_entries` in favour of one `raw()` of a stream olefile already had open; the in-place branch adds one `rename` +
  one `chmod`. `read_entries` on a pin is ~1 ms; nothing here is on the measured `surface_bench` paths' critical loop
  beyond that.

## Findings / limits, stated

- The digests are instruments on pins, not Autodesk's reader (rule 4): they prove the fold changed no byte of what
  these functions emit and certify nothing.
- Error types that changed: `write_with_latest` on a Latest-less source `RuntimeError` → `KeyError`; a folded site handed
  a stray key would now raise `KeyError` instead of dropping it (cannot happen at these sites, see 2).
- #655 filed (reduce_v2's by-value end record on 2025/2024).

## /simplify pass (four independent angles) -- taken / not taken

Taken: **simplification** -- `manipulate._primary_partition(doc, entries_by_path=None)`: the second parameter is read
nowhere in the body and every caller now passes nothing / `None` (the two touched here call `_primary_partition(doc)`;
`versions/records32.py`, hot, keeps passing `None` and keeps working) -- the dead positional is now provably dead for the
hot-file PR that may delete it; `roundtrip.py`'s module docstring no longer enumerates callers by name (rots on the next
fold) and the `dst`-directory paragraph says "not created" once, not three ways; `_patch_partatom` encodes the XML once
(`data`), not twice. **Reuse** -- nothing to call instead: no shared atomic-write helper exists in `src/rvt` / `tools`
(the prior temp+`os.replace` spellings are one-offs: `tools/rvt_job.py:256`, `famload.py:1322`, `genesis_compose`,
`fifth_surface`), and `RvtDocument` has only `has` / `raw`. **Efficiency** -- verified clean by count: olefile opens of
the source per function before → after are equal at all ten sites (2 → 2 for the six splice writers, 1 → 1 for
`write_with_latest` / famload pass 2, `_patch_partatom` 2 → 2, `emit_rfa` FamilyIndex+2 both ways); the three identity
sites swap a full `read_entries` held through the compute phase for one ~2 KB `raw()` on the already-open olefile
(compute-phase memory drops by one whole container copy; peak at write time unchanged); `bytes(new)` on exact `bytes` is
the identity on CPython; the in-place branch costs ~8 syscalls only when `samefile` is true (in place 3.8 ms vs distinct
4.4 ms on the 2026 pin -- noise); the common path pays one extra `stat`.

Not taken, with the reason: **altitude (A)** "atomic write belongs one level down, in `cfb_writer.write_cfb`, for every
write" -- a real argument (six other `write_cfb` callers and `roundtrip()` keep the direct write), but it changes the
filesystem contract of every writer in the engine (symlinked outputs, directory permissions, the `.tmp` sibling
appearing next to every deliverable mid-write) and `cfb_writer` is the stdlib leaf #640's review kept out of scope; the
brief fixed the altitude at `rewrite_entries`' in-place case, which is the case where a torn write destroys the *input*.
Recorded here as the standing counter-position for whoever next touches `cfb_writer`. **Altitude (D)** the triplicated
identity block → one `rvt.identity` helper: right, but `identity.py` is outside this fold's territory and G2 work
(#194 / #195) owns that block -- filed **#657**. **Reuse** `tools/rvt_job.py::scrub_identity` is one more hand-rolled
in-place copy (with its own `.idtmp` rename, no cleanup on failure) outside `src/rvt/` -- filed **#656**. **Reuse** the
new test file's `pin` fixture / `_streams` helper are the third verbatim copies (`test_cfb_rewrite_entries.py`,
`test_conftest_scaffolding.py`); the home is `tests/conftest.py`, which this issue's territory excludes by name -- left
for the next conftest PR (noted, not filed: nine lines). **Simplification** `_DiskFull` as a class mirrors
`test_famload_batch._CountWrites`; kept for parity.

## Follow-ups (searched first; task-shaped, Refs #646)

- **#655** -- `reduce_v2`'s by-value `PART_END_RECORD` (`0x3A3`) makes `remove_units_v2` raise on the 2025 / 2024 pins (#467-class).
- **#656** -- `tools/rvt_job.py::scrub_identity` folds onto `rewrite_entries` in place.
- **#657** -- one `rvt.identity` helper for the three "own BasicFileInfo, never break the commit" blocks.

BRANCH STATE (cam/646-rewrite-entries-folds): `src/rvt/roundtrip.py` (`rewrite_entries` body + docstring: bytes-like
edits / `TypeError`, atomic in-place branch, `dst`-dir contract; module docstring; `shutil` / `tempfile` imports),
the ten folds -- `src/rvt/{commit,manipulate,reduce,reduce_v2,famload,families,adocument}.py`,
`src/rvt/mep/{conduit,electrical_data}.py`, `src/rvt/convert/modify_family.py` (minimal hunks + import trims;
`manipulate._primary_partition`'s second parameter defaulted), their eleven `plugin/lib/src/rvt/**` mirrors via
`tools/sync_plugin.py`, `tests/test_rewrite_entries_646.py` (new, 13), `tests/ci_shard.d/646-rewrite-entries-folds.txt`
(new), this fragment (new). Not touched: `tests/conftest.py`, `src/rvt/versions/**`, `src/rvt/frontdoor/base.py`,
`famgen/**`, `src/rvt/ifc/**`, `cfb_writer.py`, any hot file, the stream index. Gates: sha table 36/36 equal; gate
suites 210/176 → 223/176; whole merged shard 2293 passed / 134 skipped / 3 xfailed; `/simplify` RAN (above); `/verify` RAN -- front door
`author --rvt <pin> --edit 'set level "GEN B1 - Basement" elevation to -12 ft'` on all three pins, branch vs an
`origin/main` worktree: output `.rvt` md5 **equal** per pin (`6a0ea9b1…` 2026, `aea6aa7a…` 2025, `0bee95d2…` 2024; the
2025 run repeated on the branch: same md5), each `VALID (no errors)` under its own release (2026: the known DataStorage
decoder-gap warning, unchanged); `tools/route.py run --output rfa --rfa <generated panelboard .rfa> --prompt "rename the
type to …"` (route `rfa_modify`, the in-place PartAtom patch included -- edited PartAtom carries the new name): `.rfa` md5
**equal** branch vs main (`f23ee14f…`); `tools/sync_plugin.py` rebuilt + `--check` clean, `validate_plugin.py` PASS (25
assertions), `check_portable_paths.py` ok. Nothing staged for the viewer; no certification claim (rule 4: digests and
VALID lines are instruments, not Autodesk's reader); `tekton-plugin.zip` regenerated locally, not committed.
