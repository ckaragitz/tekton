# 657-identity-helper -- the three writers' "own BasicFileInfo, keep the document GUID, never let identity break a commit" blocks are ONE `rvt.identity.own_streams(doc, …)`, byte-identically on the three pins (shard-docs-audit stream, eng #657)

**Issue:** #657 (filed by eng #646's altitude pass; Refs #646 / PR #661, #194, #195). **Date:** 2026-08-11.
**Session:** eng #657 (cloud, `cse_01SZVQtEuzWDocr4dCo3ALiJ`), started by the tech-lead session. **Base:** `main` @ `3ec84d7`
(#661 and #664 merged) for every measurement below; rebased onto `fd3ecdf` (#665, `convert/modify_family.py` +
`tools/rvt_job.py` only -- disjoint from the three writers) before the PR opened, new module re-run green there. Index: `docs/inbox/shard-docs-audit.md` (left untouched -- the README makes the index line optional
and that EOF is the hot spot #636 exists to avoid). Written in this engineer's voice; no other record edited.

## Why

After #661 folded the container re-emits onto `rewrite_entries`, `commit.commit_new_elements` (step 3 / 3b),
`mep.conduit.commit_created` and `mep.electrical_data.commit_electrical` each still carried their own copy of the identity
step. Gate G2 (#194 / #195: TransmissionData, the ProjectInformation zip entry, a History-coherent GUID mint) will grow that
step again, and three hunks that must change together is how one gets missed. #657: one helper in `rvt.identity`, each
site keeping exactly its current policy as arguments, outputs byte-identical on the three pinned bases.

## The three blocks, side by side (main @ `3ec84d7`) -- common shape and the honest differences

Common to all three: inside the writer's `open_rvt(src)` block `bfi = doc.raw("BasicFileInfo") if doc.has("BasicFileInfo")
else None`; after it `try: … new_streams["BasicFileInfo"] = own_basic_file_info(bfi, out_path=out_path, <kwargs>) except
Exception as exc: warnings.warn(f"identity scrub skipped: {exc}")` -- "never let identity break a commit".
The differences (issue DONE 2: "parametrize honestly, do not force it"):

| site | on? | `<kwargs>` to `own_basic_file_info` | document GUID | more |
|---|---|---|---|---|
| `commit.commit_new_elements` | always | `**identity` (caller's dict) | **kept**: `identity.setdefault("document_guid", <current BFI GUID>)` (History[0] coherence) | step 3b: `Global/DocumentIncrementTable` usernames := `identity["username"]` (default `""`) via `own_increment_table_stream`, in its own `try` with its own warning `increment-table identity scrub skipped: …`, reading the stream through a **second** `open_rvt(src)`; guarded by a dead `if "Global/DocumentIncrementTable" not in new_streams` |
| `mep.conduit.commit_created` | always | `document_guid=<current>` only | **kept** | -- (== the commit.py block with `identity=None`) |
| `mep.electrical_data.commit_electrical` | opt-in `own_identity=False` (bfi read only when on) | `**(identity or {})` | **fresh uuid4** unless `identity` names one -- the documented reason `own_identity` defaults off (breaks BFI GUID == History[0], validator L2) | -- |

## What landed

1. **`src/rvt/identity.py::own_streams(doc, out_path="", *, identity=None, keep_document_guid=True, increment_table=False)
   -> {stream: new_raw}`** (added; nothing else in the module touched -- `PRODUCT_AUTHOR_PLACEHOLDER`, `own_identity_model`,
   `own_basic_file_info`, `own_increment_table_stream` byte-for-byte as they were; two stream-name constants `BFI_STREAM` /
   `INCREMENT_TABLE_STREAM` added next to it). Takes the OPEN container document (`has` / `raw` / `prefix` / `inflate`),
   returns the identity streams for the writer's `rewrite_entries` map: `BasicFileInfo` when present ->
   `own_basic_file_info(raw, out_path=out_path, **identity)` with, under `keep_document_guid`, `document_guid` defaulted to
   the file's current Unique Document GUID (an explicit `identity["document_guid"]` still wins; the caller's dict is copied,
   never written to); `Global/DocumentIncrementTable` when `increment_table` -> usernames := `identity["username"]` (default
   `""`). Never raises: each stream in its own `try`, left out with exactly the old warning texts (`identity scrub skipped:
   <exc>` / `increment-table identity scrub skipped: <exc>`); the increment table still comes back when BasicFileInfo fails,
   as before (two independent `try`s then, two now). The GUID decode happens whenever `keep_document_guid` is on -- also
   when `identity` already names a GUID -- because `commit.py`'s `setdefault("document_guid", _dbfi(bfi)…)` evaluated it
   unconditionally too, so the failure surface (which exception text lands in the warning) is unchanged; the increment
   table reads `prefix`, `inflate`, `raw` in the old order for the same reason.
2. **The three sites** (minimal hunks; the call moved INSIDE the writer's existing `open_rvt` block, after the partition
   splice, i.e. at the same point in the sequence -- identity is computed after the splice succeeded, before the write):
   - `commit.py`: `new_streams.update(own_streams(doc, out_path, identity=identity, increment_table=True))`; module-level
     `from .identity import own_streams`; the `bfi = …` pre-read, both `try` blocks, the second `open_rvt(src_rvt)` and the
     dead `not in new_streams` guard are gone (the helper's streams now simply win on `update` -- said in the comment; no
     writer puts either stream in `new_streams` itself). Module docstring corrected: it claimed BasicFileInfo and the
     increment table were "deliberately NOT modified", false since 2026-08-03.
   - `mep/conduit.py::commit_created`: `new_streams.update(own_streams(f, out_path))` (defaults == its policy); lazy import
     next to the function's other lazy imports.
   - `mep/electrical_data.py::commit_electrical`: `if own_identity: new_streams.update(own_streams(d, out_path,
     identity=identity, keep_document_guid=False))`; module-level import; the `own_identity` docstring now names the helper
     and drops its stale clause ("the same conflict any post-2026-08-03 `commit_new_elements` output hits" -- commit.py has
     kept the GUID since), pointing at #195 for the coherent mint. `keep_document_guid=False` exists for this one legacy
     opt-in policy; #195 (mint coherently with History) is the issue that deletes the knob, not this one (DONE: no
     behaviour change).
3. **`tests/test_identity_helper_657.py`** (new, 17 rows, pinned bases only, `no_release_leak` module-wide, foreign pins under
   `release_build_context`) + drop-in `tests/ci_shard.d/657-identity-helper.txt`. Contract rows: default -> exactly
   `{BasicFileInfo}`, GUID kept (== central episode GUID), save path = the output's basename, username `""`, author ==
   client == `PRODUCT_AUTHOR_PLACEHOLDER`, build marker and increments untouched, bytes == the re-implemented commit.py AND
   conduit blocks; `keep_document_guid=False` -> the (pinned) fresh uuid4, bytes == the re-implemented electrical block; an
   explicit `document_guid` wins under both settings and the caller's dict is not mutated; `increment_table` -> both
   streams, bytes == the re-implemented 3b block, every decoded save-episode username rewritten; an undecodable
   BasicFileInfo -> warning + BFI left out + the table still returned; a document without either stream -> `{}` silently
   for BFI, the increment-table warning when asked. Site rows (× 3 certified pins each): one deterministic new element (a
   level work plane, `mep.devices.add_level_datum_plane`) committed by each writer; the emitted `BasicFileInfo` (and, for
   commit.py, the increment table) == the in-test re-implementation of that writer's pre-fold block applied to the pin, and
   NO stream other than {partition, `Global/ElemTable`, those} differs from the pin; `commit_electrical` without
   `own_identity` touches no identity stream, with it takes the fresh GUID, with `identity` the given GUID + username. The
   "never break a commit" row: a pin whose BasicFileInfo is 3 bytes -> all three writers write, warn `identity scrub
   skipped: …`, carry the bad stream verbatim (commit.py still owns the increment table).

## Evidence

**Byte identity of the fold** -- driver `sha_table.py <outdir> before|after|compare` (session scratchpad; #646's shape):
per certified pin, foreign pins under `release_build_context`, one deterministic new element (`add_level_datum_plane` on
the pin's first level at (1, 2)), fixed output basenames (BasicFileInfo's save path is the basename), `uuid.uuid4` pinned
for the fresh-GUID case. "before" = `main` @ `3ec84d7` run twice (36/36 equal run-to-run), "after" = the final diff
(re-run after the /simplify edits): **36/36 EQUAL** = 27 sha256 digests + 9 warning-text lists.

| case \ pin (sha256, first 16 hex; before == after) | G_ABPD (2026) | G_ABPD_2025 | G_ABPD_2024 |
|---|---|---|---|
| S1 `commit_new_elements(pin, out, [recs], [elemrec], identity={"username": ""})` | d27d574463edb141 | c7cea28a12c86603 | 8451eaa31273fad5 |
| S1n the same, `identity=None` | aedd8147418f68b4 | 8b68862fce679092 | 0a6e962ae1e19003 |
| S7 `conduit.commit_created(pin, out, doc, [ConduitPlan("conduit", curves=[el])])` | e205c8d178d7798e | c7ee151e2313af66 | 04ef3af156ed5771 |
| S8 `commit_electrical(pin, out, doc, new_elements=[el])` | 3990158fe146b496 | 5459eb90dd25e5f3 | c1e1d13354ad7b1f |
| S8b the same, `own_identity=True` (uuid4 pinned) | 87d19fc2102bb236 | a44a0330904a491a | 941603c35e814adf |
| S8c the same, `own_identity=True, identity={"username": "u657", "document_guid": <fixed>}` | c934f0bb14ac1576 | db2cc91dd5899449 | 2026b125ea8aae12 |
| W1 S1 on a copy of the pin whose BasicFileInfo is 3 bytes (written; warns) | 2f8ecf3188cb0136 | 2b000d95ba211f88 | 8399d27af01d8b26 |
| W7 S7 on that copy (written; warns) | 3deb8303ea96db07 | eb736e713f399ad4 | f63770791cf4bccc |
| W8b S8b on that copy (written; warns) ¹ | 3deb8303ea96db07 | eb736e713f399ad4 | f63770791cf4bccc |
| W1 / W7 / W8b warning texts (each `["identity scrub skipped: unpack_from requires a buffer of at least 4 bytes …"]`) | equal | equal | equal |

¹ W7 == W8b is expected: with the BFI rewrite skipped both writers emit the same splice of the same element and no
identity stream. The 12 rows the brief asked for (S1, S7, S8, S8b × 3 pins) are rows 1, 3, 4, 5: **12/12 equal**.

- `git grep -n "identity scrub skipped" -- src/rvt/commit.py src/rvt/mep`: **4 → 0** (three BFI copies + the
  increment-table one); the two `warnings.warn` calls now live only in `identity.py::own_streams` (plus their mention in
  its docstring); `git grep -n "own_basic_file_info(" -- src/rvt` outside `identity.py`: 3 call sites → 0 (one docstring
  mention in `stream_encoders.py` remains).
- Gate suites (`RVT_SKIP_LARGE=1 … -q -rs -p no:cacheprovider` over `test_identity_helper_657 test_identity
  test_genesis_identity test_commit test_mep_conduit test_mep_devices test_mep_electrical_data test_mep_views_spaces
  test_rewrite_entries_646 test_records_layout test_edit_own_release`): `origin/main` worktree (new file absent) **94 passed,
  73 skipped** → branch **111 passed, 73 skipped** (= main + the 17 new rows; the 73 skips are absent `samples/` /
  `RVT_SKIP_LARGE` / the root-vs-read-only row of #646, identical lists).
- Whole merged shard, sequential, same VM (`RVT_SKIP_LARGE=1 .venv/bin/python -m pytest -q -p no:cacheprovider $(python3
  tools/dev/shard_list.py --print)`): branch **2330 passed, 135 skipped, 3 xfailed, 3 warnings** in 540 s -- the shard
  now includes the new file's 17 rows, so `origin/main` @ `3ec84d7` is expected at 2313 / 135 / 3 (its worktree run was
  started after this line was written; the PR thread carries the measured figure).
- `tools/route.py matrix`: byte-identical branch vs `origin/main` worktree (3181 bytes).
- Latency (S-2026-08-09-g): `commit_new_elements` opens the source container one time fewer (the second `open_rvt` for the
  increment table is gone; `RvtDocument.raw` on the already-open olefile is cached); nothing added to any import path that
  was not already imported (`rvt.identity` pulls `os` / `uuid` / `warnings` / `stream_encoders`, all already loaded by
  `commit.py` / `electrical_data.py`; `conduit.py` keeps it lazy). No `surface_bench` path changes shape.

## Findings / limits, stated

- The digests are instruments on pins, not Autodesk's reader (rule 4): they prove the fold changed no byte and certify
  nothing. No `.rvt` is shipped by this PR.
- One observable non-byte difference, stated: the warnings are now raised from `identity.py` (one source line each)
  instead of three writer lines, so Python's default once-per-location filter shows a repeated "identity scrub skipped"
  once per process where it used to show it once per writer; message text and category (`UserWarning`) are unchanged and
  every test matches by message.
- `commit_electrical(own_identity=True)`'s fresh-GUID policy is preserved, not endorsed: it is the one caller of
  `keep_document_guid=False`, and #195's coherent mint is where that knob goes away.

## /simplify pass (four independent angles) -- taken / not taken

Taken: **simplification** -- `commit.py`'s module docstring no longer says BasicFileInfo / the increment table are "NOT
modified" (false since 2026-08-03; the fold rewrote the adjacent comment, so the contradiction was ours to fix);
`commit_electrical`'s `own_identity` docstring drops its stale `commit_new_elements` clause and names the helper + #195;
`own_streams`' docstring cut from 27 to 20 lines and re-framed so `increment_table=True` reads as the norm for a
deliverable (altitude note: the next writer must not copy conduit's bare call and ship Autodesk usernames); the
`update()` precedence (helper wins; the old dead `not in new_streams` guard pointed the other way) is one comment line at
the commit.py call. **Efficiency** -- verified clean: import weight nil, one olefile open fewer, BFI decoded twice under
`keep_document_guid` exactly as commit.py / conduit already did (decode-once would be byte-identical but rewrites
`own_basic_file_info`'s internals -- outside "add the helper, touch nothing else"). **Altitude** -- open doc (not bytes /
path) is the seam #195's History rewrite needs; `keep_document_guid: bool` rather than a `document_guid=KEEP|None|str`
tri-state, because `identity["document_guid"]` already is the explicit value and a tri-state creates a precedence question
for a knob with one transitional caller; never-raise inside the helper (it IS the policy being centralised); pure
`{stream: bytes}` return, caller owns precedence -- all keep-as-is.

Not taken, with the reason: **simplification** `own_increment_table_stream(framed_raw, …)` never reads its first
parameter, so `own_streams` does one `doc.raw` only to fill it -- dropping the parameter edits an existing `identity.py`
function and its two `tools/genesis_*` callers (territory: "add the helper; touch nothing else there"); noted for #195,
which rewrites that neighbourhood. **Simplification** the test's `old_conduit_bfi` is `old_commit_bfi(…, None)` -- kept as
two verbatim re-implementations on purpose (the row asserts they agree). **Reuse** `tools/genesis_identity.py::own_bfi /
own_dit` and `tools/genesis_addpath_probes.py::identity_scrub_streams` spell the same block in #19's probe tooling -- not
folded and not filed: probe authors must RAISE on a stream they cannot scrub (a silently skipped scrub voids a viewer
round), the helper's never-raise contract is the writer's, and a `strict=` knob with no writer caller is investment in the
wrong direction; recorded here as the counter-position for whoever next touches those tools. **Reuse** the fourth copy of
the `pin` fixture / `_streams` reader → filed **#670** (conftest hoist; `tests/conftest.py` is outside this territory).
**Altitude** an unknown key in `identity` degrades to the warning rather than a `TypeError` (the never-raise contract
covering argument validation) -- pre-existing at commit.py / electrical, byte-identity forbids changing it here; noted for
#195.

## Follow-ups (searched first; task-shaped, Refs #657)

- **#670** -- `pin` fixture + `_streams(path)` reader hoisted into `tests/conftest.py` (four copies today).
- For #195 (commented there is not needed -- its territory line already names `src/rvt/identity.py` + `commit.py`): the
  GUID/History mint now has ONE call path to change (`own_streams`), and `keep_document_guid=False` +
  `own_increment_table_stream`'s dead first parameter are its to retire.

BRANCH STATE (cam/657-identity-helper): `src/rvt/identity.py` (+`own_streams`, +`BFI_STREAM` / `INCREMENT_TABLE_STREAM`,
+`import warnings`; nothing else touched), `src/rvt/commit.py` (identity steps 3/3b → one call inside the `open_rvt`
block; module import; module docstring corrected), `src/rvt/mep/conduit.py::commit_created` and
`src/rvt/mep/electrical_data.py::commit_electrical` (identity block → one call each; import; the `own_identity` docstring),
their four `plugin/lib/src/rvt/**` mirrors via `tools/sync_plugin.py`, `tests/test_identity_helper_657.py` (new, 17),
`tests/ci_shard.d/657-identity-helper.txt` (new), this fragment (new). Not touched: `src/rvt/versions/**`,
`src/rvt/frontdoor/base.py`, `tools/frontdoor.py`, `tools/rvt_job.py` (#656), `tools/genesis_identity.py` (#19),
`tests/conftest.py`, any hot file, the stream index. Gates: sha table 36/36 equal (12/12 on the brief's rows); gate suites
94/73 (main) → 111/73 (branch); whole merged shard: branch **2330 passed / 135 skipped / 3 xfailed**, `origin/main` @
`3ec84d7` expected 2313 / 135 / 3 (measured figure on the PR thread);
`tools/route.py matrix` byte-identical; `/simplify` RAN (above); `/verify` RAN -- front door `author --rvt <pin> --edit 'set
level "GEN B1 - Basement" elevation to -12 ft' --out <d> --json` on all three pins, branch vs an `origin/main` worktree:
output `.rvt` md5 **equal** per pin (`6a0ea9b1…` 2026, `aea6aa7a…` 2025, `0bee95d2…` 2024 -- the same digests #646
recorded), status `PROOF-ONLY, NOT-DELIVERABLE (hard gates PASSED)` (delivered, stamped -- rule 1), each `VALID (no
errors)` under its own release (2026: the known DataStorage decoder-gap warning, unchanged); and, because the edit lane
does not reach the three writers on a family-free pin, the flagship `author --prompt "an electrical room with 6 panels"
--out <d> --json` (its stage W walls and stage E placement ARE `commit_new_elements`, `identity=None`) on branch and on the
`origin/main` worktree: status `PROOF-ONLY (self-checks PASS …)` both, `prompt_room.rvt` `VALID (no errors)`, and its
`BasicFileInfo` + `Global/DocumentIncrementTable` streams **byte-identical branch vs main** (sha256 `6238f9a1…` /
`4369cefc…`; GUID == the base's, save path `prompt_room.rvt`, username `''`, author the product placeholder, every DIT
username `''`) while the only differing streams are the three that carry per-run family GUIDs (`Partitions/21`,
`Global/ContentDocuments`, `Global/Latest` -- 9/12 equal, as any two main runs are); `tools/rvt_job.py create --spec` was
tried first and writes nothing on the pins (`SEED NOT READY` / no wall types -- pre-existing, not this diff); `tools/sync_plugin.py` rebuilt
+ `--check` clean (identity scan == allowlist, 0 mismatches), `plugin/scripts/validate_plugin.py` PASS (25 assertions),
`tools/dev/check_portable_paths.py` ok, the drop-in resolves (`shard_list.py --print` lists the new file).
Nothing staged for the viewer; no certification claim; `tekton-plugin.zip` regenerated locally, not committed.
