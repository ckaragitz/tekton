# inbox: manipulate-import-context — the edit layer reads block tags at CALL time (#455)

Stream: eng #455 (issue #455, branch `cam/455-manipulate-tags-at-call-time`).
Territory touched: `src/rvt/manipulate.py` (the import block + `_emit_block`
only), new `tests/test_manipulate_import_context.py`, new shard drop-in
`tests/ci_shard.d/455-manipulate-order.txt`, this record; generated mirror
`plugin/lib/src/rvt/manipulate.py` via `tools/sync_plugin.py`. Nothing under
`src/rvt/versions/**` (hot; only its accessors are READ), nothing in
`frontdoor/`, `validate.py`, `tools/`.

## eng #455 — 2026-08-10 — what was built and why

**The bug (PG1, written bytes).** `src/rvt/manipulate.py:76` did
`from .partitions import BLOCK_TAG, TRAILER_TAG` — a by-value copy taken at
import — and `_emit_block` framed every re-emitted unit-0 block with those two
copies. `rvt.versions.reading()` / `activate()` rebinds
`rvt.partitions.BLOCK_TAG/TRAILER_TAG` **by name** per release and restores
them on exit, which is right for every by-name reader; but a process whose
FIRST `import rvt.manipulate` happens while a non-2026 context is in force kept
the 2024 (`0x0e7c/0x0e75`) or 2023 (`0x0e4e/0x0e47`) tags for the rest of its
life, and every later 2026 `commit_plans` / `commit_session` wrote foreign block
tags and died on its own post-emit re-walk (`ManipulationError: walker errors
after re-emit: ['unexpected tag 0x0e7c at 18']` — loud, no bad file delivered,
but the edit fails). Real code lands the first import inside a context without
any test involved: `records32.reading32(<2023 file>)` → `ids32()` →
`_patch_table()` does `importlib.import_module("rvt.manipulate")` inside the
2023 framing. In the suite it surfaced as ORDER dependence:
`tests/test_objects_plans.py` (module fixture holds `enter_own_release` on the
2024 base while `test_ids32_era_takes_the_walk` enters `ids32()`) before
`tests/test_manipulate.py` → 2 failed + 2 errors on `main` @ a1927c8; and the CI
shard tail run in isolation (`test_out_dir_guard → test_objects_plans →
test_history_head_guid`) → `test_edit_hands_the_identity_scrub_history0_verbatim[2026]`
failed on `main` with the same symptom (the merged shard was green only because
an earlier shard file imports `rvt.manipulate` outside a context first).

**The fix (one variable).** `_emit_block` now reads `_P.BLOCK_TAG` /
`_P.TRAILER_TAG` from `rvt.partitions` at call time (`from . import partitions
as _P`) — the same values the `StreamWalker` re-walk two lines later checks
against, so emit-tag == walk-tag by construction in every context. The module
still exposes `BLOCK_TAG` / `TRAILER_TAG` attributes because four callers
outside this territory `getattr`+`setattr` them as part of their release
contexts (`src/rvt/frontdoor/release_ctx.py:365-366`, `tools/genesis_2025.py`,
`genesis_2024.py`, `genesis_2023.py` `_LOCAL_TAG_PATCHES`) and two tests snapshot
them (`test_edit_own_release._native_constants`, `test_genesis_202{4,5}`); they
are now the deterministic at-rest 2026 values from
`rvt.versions.framing_table(LATEST_RELEASE)` (no longer whatever context the
import sat in) and are documented as inert — nothing in `manipulate` reads them.
Those swaps all sit inside the same `versions.reading()` with the same
ordinals, so they were already equal to `rvt.partitions`' live values; leaving
them in place changes no byte and keeps this PR inside its territory (removing
the now-redundant `swap(MANIP, …)` lines is a follow-up for the streams that own
those files — see below).

**Why no written byte can change on any path that succeeded before.** The
post-emit sanity walk (`manipulate.py` `w2 = StreamWalker(bytes(out)) … raise
ManipulationError("walker errors after re-emit …")`, and the identical check in
`mep/electrical_data.py:1678`) reads `rvt.partitions.BLOCK_TAG`; any call where
the old by-value copy differed from the live `rvt.partitions` value therefore
raised before a file was written. So on every previously-successful path the
two were equal, and reading the live value writes the same two u16s. Pinned
empirically below (three bases, `cmp`).

**DONE item 3 — other by-value copies of patched names.** `grep` over `src/rvt/`
for module-level from-imports of `BLOCK_TAG|TRAILER_TAG|FOOTER_TAG|CONTAINER_CLASS|
UNIT_INNER_CLASS|PT_CLASS|TERMINATOR|RECORD_HDR_*` from `rvt.partitions`: the
only match was `manipulate.py:76` (now gone). Every other `from .partitions
import …` imports `StreamWalker` / `record_header_len` / `parse_partition_table`
(functions/classes that read the module globals at call time — fine). The
records32 patch table's by-value targets (`iter_records`, `decode_elemtable`,
`encode_elemtable`, `_record_spans`, `EditSession.frame`, …) are patched per
holding module by `_patch_table` itself, so they are covered by design.
Observations outside this territory, not bugs of this kind (release-pinned
literals, consistently swapped by the release contexts, never import-order
dependent): `reduce.py:59 BLOCK_TAG = 0x0F28`, `writer.py:161 BLOCK_TRL_TAG`,
`commit.py`/`families.py`/`mep/conduit.py`/`famgen/geometry.py` importing
`writer.BLOCK_TRL_TAG`, `famgen/skeleton.py:2218-2220`, `famdoc_adoc.py:286`.

## Evidence (numbers)

All on this branch's head vs `main` @ a1927c8, fresh cloud clone (no `samples/`),
`.venv` from `scripts/cloud-setup.sh`, `RVT_SKIP_LARGE=1`, `-p no:cacheprovider`.

| Check | main | head |
|---|---|---|
| `pytest tests/test_objects_plans.py tests/test_manipulate.py` (that order, one process) | **2 failed, 24 passed, 5 skipped, 2 errors** (`unexpected tag 0x0e7c at 18`) | **28 passed, 5 skipped** (skips = `samples/rstbasicsampleproject.rvt` cases) |
| shard tail in isolation `tests/test_out_dir_guard.py tests/test_objects_plans.py tests/test_history_head_guid.py` | **1 failed, 49 passed** (`test_edit_hands_the_identity_scrub_history0_verbatim[2026]`) | **50 passed** in 13.4 s |
| new `tests/test_manipulate_import_context.py` | **4 failed** (3 fresh-interpreter cases: `unexpected tag 0x0e7c` ×2, `0x0e4e` for the 2023+ids32 door; + the unit law) | **4 passed** in 2.2 s |
| `tools/rvt_edit.py <base> set-level --id 1351691 --elevation-ft 12.0 -o …` on `G_ABPD.rvt` / `_2025` / `_2024` | — | outputs **byte-IDENTICAL to main's** (`cmp`): 581,632 B `ffb9790e2c770c49…`, 598,016 B `4dfa3d4756235b98…`, 577,536 B `5e046246639e1b20…` |

The regression test's three doors (each in a FRESH interpreter via
`subprocess`, asserting `rvt.manipulate` is not yet imported, then importing it
for the first time inside the context): `versions.reading(G_ABPD_2024.rvt)`;
`validate.enter_own_release(G_ABPD_2024.rvt)`; `versions.reading(year=2023)` +
`records32.ids32()` (no explicit import — `_patch_table` does it, asserted).
After the context: `rvt.partitions` restored to the 2026 table, `manipulate`'s
at-rest handles == the 2026 table, a `set_level_elevation` edit of `G_ABPD.rvt`
commits, `verify_manipulated` walker/crc/ecc 0 + stamps ok + edited records
clean, `validate_file` 0 errors, the block tags on disk are exactly `{0x0f28}`,
and the output is **byte-identical** to the same edit made in the pytest
process (import outside any context). Plus a unit law: `_emit_block` under
`reading(year=Y)` frames with Y's tags for every known release and with 2026's
at rest.

Gates on the final head: see BRANCH STATE.

## Follow-ups (searched first; filed task-shaped where new)

* The four `swap(MANIP, "BLOCK_TAG"/"TRAILER_TAG", …)` / `_LOCAL_TAG_PATCHES`
  entries in `frontdoor/release_ctx.py` and `tools/genesis_202{3,4,5}.py` are now
  provably redundant (inert handles); removing them — and, by the same call-time
  pattern, `reduce.BLOCK_TAG` / `writer.BLOCK_TRL_TAG`'s by-value importers — would
  shrink every release context's patch list. Not done here (outside territory;
  `release_ctx.py` is frontdoor, the genesis tools are owner-machine campaign
  drivers). Filed as **#467** (`Refs #455`, P2 area:engine), which also carries
  the /simplify altitude review's widening of the class: by-value from-imports of
  names `records32._patch_table` rebinds per holding module, in modules the table
  does not list (`mep/electrical_data.py:78` `decode/encode_elemtable`,
  `regadd.py:119` `encode_record`/`record_bytes`) — overlaps #174. Sibling, not
  duplicate: #93 (Global-stream ContentDocuments tokens).

## BRANCH STATE

* Branch `cam/455-manipulate-tags-at-call-time` from `main` @ a1927c8; PR links `Closes #455`.
* Files written: `src/rvt/manipulate.py` (import block: `from . import partitions as _P`,
  `from .versions import LATEST_RELEASE, framing_table`, the two inert at-rest handles +
  comment; `_emit_block` reads `_P.BLOCK_TAG/_P.TRAILER_TAG` + docstring — nothing else,
  #460's `verify_manipulated` untouched), `tests/test_manipulate_import_context.py` (new,
  4 tests), `tests/ci_shard.d/455-manipulate-order.txt` (new: the new file +
  `tests/test_manipulate.py`, both fresh-clone safe — bundled bases only, `samples/`
  cases self-skip), `docs/inbox/manipulate-import-context.md` (this record). Generated
  mirror re-synced: `plugin/lib/src/rvt/manipulate.py`.
* Not touched: `src/rvt/versions/**`, `src/rvt/frontdoor/**`, `src/rvt/validate.py`,
  `tools/**`, `tests/ci_shard.txt`, `tests/conftest.py`, `tests/test_history_head_guid.py`,
  any hot file.
* Shipped vs staged: everything ships with the PR; nothing for the viewer (no written
  byte changes on any path — three-base `cmp` above).
* PR #469 (not draft). Follow-up filed: #467.
* Gates (fresh cloud clone, `RVT_SKIP_LARGE=1 -p no:cacheprovider`): stream-local +
  neighbours (`test_manipulate_import_context test_manipulate test_edit_own_release
  test_genesis_2025/2024/2023 test_versions test_records32 test_target2025 test_y2024
  test_y2025_b test_famload_2025 test_objects_plans test_history_head_guid`) → **178 passed,
  114 skipped, 1 xfailed** (39 s); whole merged CI shard (`python3 tools/dev/shard_list.py
  --print`, incl. the new drop-in) → **1609 passed, 139 skipped, 3 xfailed in 404 s** on the
  first commit 0dcf03b and **1609 passed, 139 skipped, 3 xfailed in 394 s** again on the final code (f61fc1a); `tools/sync_plugin.py`
  synced 1 file, `--check` clean; `plugin/scripts/validate_plugin.py` PASS (25 assertions);
  `tools/dev/check_portable_paths.py` ok (2908 paths). `/simplify`: 4 angles, fixes applied
  (one `framing_table()` call, 4-line note, test script by concatenation, `_tags()` helper);
  altitude verdict "right depth". `/verify` on the post-simplify code: `tools/rvt_edit.py
  <G_ABPD{,_2025,_2024}.rvt> set-level --id 1351691 --elevation-ft 12.0 --json` → rc 0,
  stderr 0 B, ok=True, structural PASS | validation PASS ×3, outputs byte-identical to
  main's (`cmp`, sizes/sha256 in the Evidence table), `tools/rvt_validate.py` VALID errors=0
  ×3; `tools/frontdoor.py author --rvt G_ABPD_2025.rvt --edit "set level 1351691 elevation
  to 5 ft" --json` → rc 0, stderr 0 B, `PROOF-ONLY, NOT-DELIVERABLE (hard gates PASSED)`,
  release 2025, edited file VALID; bare unzip of the rebuilt `tekton-plugin.zip`, `env -i
  /usr/bin/python3` (3.11.15) `skills/tekton-edit/scripts/_bootstrap.py go edit <2026 base
  copy> set-level … --json` ×3 → rc 0, stderr 0 B, `tekton: READY`, result.ok=True,
  structural PASS | validation PASS (0 errors, 1 warning), wall 0.98 / 0.64 / 0.62 s, output
  byte-identical to the repo/main output.
