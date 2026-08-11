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

---

## eng #467 — 2026-08-10 — the rest of the class: no module keeps a by-value copy of a name a release context rebinds by name

Stream: eng #467 (issue #467, `Refs #455`; branch `cam/467-framing-by-name`).
Territory touched: `src/rvt/{reduce,writer,commit,families,manipulate,regadd}.py`,
`src/rvt/mep/{conduit,electrical_data}.py`, `src/rvt/frontdoor/release_ctx.py`
(the swap rows + their four now-unused module imports + the docstring
paragraph naming them — nothing else), `tools/genesis_202{3,4,5}.py` (the six
block-tag rows of `_LOCAL_TAG_PATCHES` only), the named tests
(`test_edit_own_release`, `test_manipulate_import_context`, `test_genesis_2025/2024`,
`test_y2024`, `test_y2025_b`), NEW `tests/test_framing_by_name.py` + drop-in
`tests/ci_shard.d/467-framing-by-name.txt`, this record; generated mirrors
(9 files under `plugin/lib/src/rvt/`) via `tools/sync_plugin.py`. NOT touched:
`src/rvt/versions/**` (hot — read only), `src/rvt/partitions.py` (no accessor
was missing: `FOOTER_TAG` already lives there), anything FENCED
(`src/rvt/famgen/**`, `frontdoor/{router,build,matrix,standalone,famspec}.py`,
`ifc/intent.py`, `tools/route.py`, `tekton-author/SKILL.md`), any hot file,
`tests/ci_shard.txt`, `tests/conftest.py`.

### What was built (one variable per site)

**(a) Block emitters read `rvt.partitions` at CALL time.** `reduce.NewBlock.frame`
(`_P.BLOCK_TAG` / `_P.TRAILER_TAG`; the module literal `BLOCK_TAG = 0x0F28` and the
`from .writer import BLOCK_TRL_TAG` are gone), `writer.regzip_partition_logical`
(the literal `BLOCK_TRL_TAG = 0x0F21` is gone; `_P.TRAILER_TAG`), `commit.commit_new_elements`,
`families._rebuild_partition_logical`, `mep.conduit.commit_created` (their
`from .writer import BLOCK_TRL_TAG` copies → `_P.TRAILER_TAG`) — the pattern
`manipulate._emit_block` (#455) and `global_framing.tokens()` already use, so
emit-tag == the tag the post-emit `StreamWalker` re-walk checks, by construction,
in every context. With no copy left to swap, the six rows went together:
`release_ctx.py` `swap(RED, "BLOCK_TAG")`, `swap(RED, "BLOCK_TRL_TAG")`,
`swap(MANIP, "BLOCK_TAG")`, `swap(MANIP, "TRAILER_TAG")`, `swap(COMMIT, "BLOCK_TRL_TAG")`,
`swap(WRITER, "BLOCK_TRL_TAG")` (+ the `COMMIT/MANIP/RED/WRITER` imports only they
used), and the same six `_LOCAL_TAG_PATCHES` rows in each of `tools/genesis_2025.py`,
`genesis_2024.py`, `genesis_2023.py` (the two `rvt.famgen.factory` CD rows stay; a
3-line comment in the tuple says why the others left; nothing else in those
owner-machine drivers changed — their older prose comments above the tuple are
dated grep notes and were left as history).

**(b) `rvt.manipulate.BLOCK_TAG` / `TRAILER_TAG`** — the inert at-rest handles #455
kept for those four swappers — deleted with them, together with the
`framing_table(LATEST_RELEASE)` import that only fed them, the two snapshot lines in
`tests/test_edit_own_release.py::_native_constants`, the `MP.*` assertions in
`tests/test_genesis_2025.py:82` / `test_genesis_2024.py:90` (those two tests now assert
on `rvt.partitions` — the one binding — and on `writer.BLOCK_TRL_TAG` as an alias, see
below), `tests/test_y2024.py` / `test_y2025_b.py`'s `RED.BLOCK_TAG` probes (→
`P.BLOCK_TAG`), and #455's own `tests/test_manipulate_import_context.py` (its fresh
interpreters now report `hasattr(M, "BLOCK_TAG") == False` instead of the handles'
values; the byte-identity assertions are unchanged).

**(c) The `records32` layer of the same class.** `records32._patch_table` rebinds
names per HOLDING module; a live AST audit against that table (now a test, below)
found these module-level by-value copies in modules the table does not list —
one more than the issue named in each file:
`mep/electrical_data.py:70` `_assert_sentinel_tail` (holder: `rvt.commit`) and `:78`
`decode_elemtable, encode_elemtable` (holders: `stream_encoders`/`commit`/`manipulate`/
`reduce`/`regadd`/`regdiff`); `regadd.py:119` `encode_record, record_bytes` (holder:
`rvt.encode`) and `:122` `verify_reduced` (holder: `rvt.reduce`). All five now read
THROUGH the module at call time (`SE.decode_elemtable(…)`, `_commit._assert_sentinel_tail(…)`,
`E.encode_record(…)`, `E.record_bytes(…)`, `_reduce.verify_reduced(…)`), so no
`versions/**` edit was needed. `regadd`'s `iter_records` / ElemTable-codec
from-imports were left alone on purpose: the table lists `rvt.regadd` as their
holder. One residual outside this territory: `estorage.py:90` `iter_records`
(read-only ES walk) — filed as **#548**, allow-listed by name in the new test.

**The fence and its one consequence.** `src/rvt/famgen/**` is held by the #498
family campaign, so `famgen/skeleton.py:2218-2220`'s three literals,
`famdoc_adoc.py:286`'s inline `0x0F28`, `geometry.py:2729`'s call-time
`from ..writer import BLOCK_TRL_TAG`, and `release_ctx.py`'s three
`swap(FSK, "BLOCK_TAG"|"TRAILER_TAG"|"FOOTER_TAG")` rows are exactly as they were.
Because `geometry.py` still imports the name from `rvt.writer`, `writer` keeps it
resolvable **without holding a value**: a PEP 562 module `__getattr__` returns
`rvt.partitions.TRAILER_TAG` at ACCESS time for the name `BLOCK_TRL_TAG` (and raises
`AttributeError` for anything else). A call-time `from ..writer import BLOCK_TRL_TAG`
inside a 2025 context therefore gets `0x0ED2` with no swap row (the deleted
`swap(WRITER, …)` used to provide that), the dev-only `tools/make_v18.py` /
`make_v19.py` module-level imports keep working, and `"BLOCK_TRL_TAG" not in
vars(rvt.writer)` holds. The alias leaves with the famgen follow-up, filed as
**#547** (`Refs #467`, labelled `blocked` until the campaign releases famgen).
So the DONE grep, `grep -rn "0x0F28\|0x0F21\|BLOCK_TRL_TAG" src/rvt --include=*.py`,
now lists: `partitions.py:103-104`, `versions/__init__.py:155` (table),
`writer.py:33,36,38` (the alias: two docstring lines + `if name == "BLOCK_TRL_TAG"`),
and the fenced `famgen/geometry.py:2729,2821`, `famgen/famdoc_adoc.py:286`,
`famgen/skeleton.py:2218-2219` — nothing else.
One more residual, dev-only and PROOF-ONLY: `experiments/genesis2025/subst/run_ladder2025.py:149`
still `swap(RED, "BLOCK_TRL_TAG", …)` and would now `AttributeError`; it is the
historical predecessor of `tools/genesis_2025.py` (which is fixed) and was not touched.

### Why (a) is not cosmetic — the shape that was red on `main`

The engine's OWN release ladder — `validate.enter_own_release` ==
`versions.reading` + `global_framing.bound`, which every instrument and the edit
layer use — never carried the frontdoor/genesis swap lists. So on `main` @ fdcbf12,
with the modules imported at rest: `reduce.delete_elements(G_ABPD_2025.rvt | _2024.rvt, …)`
inside `enter_own_release(base)` **raised** `RuntimeError: walker errors after
re-block: ['unexpected tag 0x0f28 at 18']` (loud, nothing delivered), and
`writer.build_variant(…, partition_streams=[…])` on the same bases **silently wrote
`0x0f21` trailers into 2025/2024 streams** (its output re-walked under the file's
release: `no trailer for block at 18`). On this head both frame with the file's own
tags (`0x0ed9/0x0ed2`, `0x0e7c/0x0e75`), walk clean, and — for the writer — differ
from `main`'s bytes in exactly the 15 trailer-tag u16s (30 bytes of 577,536 /
557,056; every other byte identical). The front door was never affected (its
`release_ctx` swapped the copies), which is why the prompt job is byte-identical.

### Evidence (numbers)

Fresh cloud clone (no `samples/`), `.venv` from `scripts/cloud-setup.sh` (Python
3.11.15), head = this branch, main = `origin/main` @ fdcbf12; every "main" artefact
was produced from the same checkout **before** the first edit, every "head" one after
the last; `RVT_SKIP_LARGE=1 -p no:cacheprovider` for pytest.

| Probe (each on G_ABPD.rvt / G_ABPD_2025.rvt / G_ABPD_2024.rvt) | main | head |
|---|---|---|
| `tools/rvt_edit.py <base> set-level --id 1351691 --elevation-ft 12.0 -o … --json` | rc 0 ×3, stderr 0 B | rc 0 ×3; **md5-identical to main** ×3 (`8f9321bd…` 581,632 B / `17cc046e…` 598,016 B / `188355bc…` 577,536 B) |
| `tools/rvt_job.py edit <copy> --ops '[{"op":"set-level","id":1351691,"elevation_ft":12.0}]' -o … --json` | rc 0 ×3 | rc 0 ×3; **md5-identical** ×3 (`b6885702…` / `03adcb81…` / `447c298c…`) |
| `reduce.delete_elements(base, out, [1351691])` inside `enter_own_release(base)` | 2026: rc 0 (`34901cd9…`); **2025/2024: RuntimeError `unexpected tag 0x0f28 at 18`** | 2026 **md5-identical** (`34901cd9…`); 2025/2024 now succeed (`fd5e0eec…` 598,016 B / `c88068bb…` 577,536 B): hdr/trl tags `{0xed9}/{0xed2}` and `{0xe7c}/{0xe75}`, walker 0 errors, `rvt_validate` structural layers clean (1 *semantic* error = the 5 views referencing the level this raw probe deleted without closure — identical finding on the 2026 output on main) |
| `writer.build_variant(base, out, [], trailer_copy, partition_streams=[P])` inside `enter_own_release(base)` | rc 0 ×3, but 2025/2024 outputs re-walk `no trailer for block at 18` (2026 trailer tag in a 2025/2024 stream) | 2026 **md5-identical** (`05b578fb…`); 2025/2024 differ from main in **exactly 15 two-byte runs `21 0f → d2 0e` / `21 0f → 75 0e`** (30 B each), same size, walk clean |
| `families.emit_rfa(tekton-eval-kit/TEST-KIT/08_eaton_panelboard_family.rfa, out)` (2026, ours) | rc 0 | **md5-identical** (`2c03319d…`) |
| `tools/frontdoor.py author --prompt "an electrical room with 6 panels" --target-version {2026,2025,2024} --json` | `PROOF-ONLY (self-checks PASS …)` ×3; **NOT byte-deterministic run-to-run on main itself**: of 30 output files only the 3 `stage_P_identity.rvt` repeat; per-stream, `Global/ContentDocuments`, `Global/Latest` and the partition payload differ (minted family/document GUIDs), `.rfa` `PartAtom <updated>` stamps differ | — |
| the same three jobs through a 30-line entropy-pinning wrapper (`uuid.uuid4` → counter, `time.time/gmtime/localtime/strftime` frozen, `random.seed`, `PYTHONHASHSEED=0`; scratch-only, nothing committed) | deterministic: two main runs → **30/30 files md5-identical** | **30/30 files md5-identical to main's pinned run** — 3 combined `prompt_room.rvt` (`8a5f34f0…` 2026 / `6c97cb94…` 2025 / `b1eaa1ef…` 2024), 9 `_stages/*.rvt`, 18 `families/*.rfa`; status line identical ×3 |
| `tests/test_framing_by_name.py` (new, 10 tests) | **9 failed, 1 passed** (engine stashed to main, test file from head): literals present, `writer` holds a copy, `_rebuild_partition_logical` on 2025/2024 → `no trailer for block`, the own-release reduce door → `unexpected tag 0x0f28`, both source laws list offenders; the one green = the #455 door (a literal is import-order-proof by nature) | **10 passed** in 4.8 s |
| stream-local + neighbours: `test_manipulate_import_context test_edit_own_release test_records32 test_genesis_2025/2024/2023 test_y2024 test_y2025_b test_versions test_manipulate test_regadd test_mep_electrical_data test_edit_text_release test_target2025 test_famload_2025` | — | **186 passed, 138 skipped, 1 xfailed** (54 s). The skips are the `samples/`-gated cases: all of `test_genesis_2025/2024/2023`'s context tests (`needs_sample`) and `test_mep_electrical_data` self-skip in a fresh clone — so the rewritten genesis assertions are exercised only on an owner machine; `test_y2024` / `test_y2025_b` / `test_edit_own_release` / `test_edit_text_release` (which reads `W.BLOCK_TRL_TAG` through the alias) ran and passed |

The new test's doors, for the reviewer: (1) unit laws in-process — `NewBlock.frame`
under a bare `versions.reading(year=Y)` for every known release; `writer.BLOCK_TRL_TAG`
is an access-time alias (`not in vars(W)`, follows every release, exact — unknown names
still raise); no emitter module has a `*_TAG` attribute; `regzip_partition_logical` +
`_rebuild_partition_logical` on the 2025 and 2024 bases under a bare `reading(base)` →
only that release's tags, walker clean, payloads untouched. (2) two FRESH interpreters
(subprocess, asserting none of reduce/writer/commit/families/manipulate is imported
before the door): first import of all five INSIDE `reading(G_ABPD_2024)` then a 2026
`delete_elements` → 2026 tags on disk and byte-identical to the same reduce made
in-process; and the user-visible door — imports at rest, then `enter_own_release(2024
base)` + `delete_elements(2024 base)` → 2024 tags, walker clean, `rvt.partitions`
restored after. (3) two source laws over `src/rvt/**` minus the fenced `famgen/`: no
`from .partitions|.writer import <TAG>` at any depth and no module-level
`*_TAG = <framing ordinal>` literal outside `partitions.py`; and every module-level
from-import of a name in the LIVE `records32._patch_table()` sits in a listed holder
(allowlist: the one #548 residual) — so a re-introduced copy, a new patched name, or
a new holder is judged without editing the test. Plus the (c) pin: `electrical_data` /
`regadd` hold none of the five names and, inside `ids32()`, the functions they will
call are not the at-rest ones.

### Follow-ups (searched first)

* **#547** — famgen's framing copies + `release_ctx`'s three `swap(FSK, …_TAG)` rows +
  `writer.__getattr__` alias, blocked on the #498 campaign releasing `src/rvt/famgen/**`
  (`Refs #467`; sibling of #93 / #71).
* **#548** — `estorage.py:90` `iter_records` by-value copy vs `ids32()` (`ready`,
  `good-first-pick`; empties the new test's allowlist).
* Not filed (dev-only, PROOF-ONLY): `experiments/genesis2025/subst/run_ladder2025.py:149`
  and `tools/make_v18.py` / `make_v19.py` still spell the old names; the latter two keep
  working through the alias, the former is superseded by `tools/genesis_2025.py`.

### /simplify and /verify (eng #467)

`/simplify` (4 angles — reuse, simplification, efficiency, altitude). Applied: the
new test reuses `conftest.pinned_base` / `ROOT` instead of a hand-rolled `BASES` +
skipif (so a `$RVT_GENESIS_BASE` override skips honestly), drops an unused import,
parses the `src/rvt` tree once for both source laws (`lru_cache`; ~1 s per shard run),
and says plainly that the literal law covers the two shapes seen so far, not every
way to bake an ordinal; the five explanatory comment blocks in `electrical_data` /
`regadd` / `manipulate` / `reduce` / `release_ctx` shrank to 1–4 lines; `writer.__getattr__`'s
docstring names #547 as its removal trigger; the stale "these four modules keep their
OWN copies … reduce.py:59 …" grep paragraphs directly above each genesis driver's
`_LOCAL_TAG_PATCHES` were rewritten (comment-only) instead of leaving a tombstone
inside the tuple. Skipped, with reason: hoisting `_tags` + the fresh-interpreter
harness shared by `test_manipulate_import_context.py` and the new file into
`tests/conftest.py` (conftest is another engineer's territory this wave — eng #523);
folding `from .partitions import StreamWalker` into `_P.StreamWalker` in
`reduce`/`commit` (style churn, a class is never rebound); the now-dead `ords[spec]`
string-spec branch in the genesis drivers' context loops (owner-machine logic —
rows-only mandate); migrating `tools/make_v18.py` / `make_v19.py` off the alias
(outside territory; folded into #547); altitude verdict "right depth" for the
call-time reads, with one deeper follow-up filed: **#551** — shrink
`records32._patch_table` to origin rows by converting its remaining *holder* modules
to module reads (hot file, its own tiny PR); the genesis drivers' `format-202x.md`
generators still print the historical patch table (past tense, owner-machine docs).

`/verify` on the post-simplify head (fresh cloud clone, no `samples/`):
`tools/frontdoor.py author --rvt <G_ABPD{,_2025,_2024}.rvt> --edit "set level 1351691
elevation to 5 ft" --json` → rc 0 ×3, stderr 0 B, `PROOF-ONLY, NOT-DELIVERABLE (hard
gates PASSED)`, output release 2026/2025/2024 = input's, `tools/rvt_validate.py` on each
edited file → `VALID (no errors)` (0/0/0 errors, 1/0/0 warnings); `tools/frontdoor.py
author --prompt "an electrical room with 6 panels" --target-version {2026,2025,2024}
--json` → rc 0 ×3, stderr 0 B, `PROOF-ONLY (self-checks PASS …)` ×3, combined `.rvt`
validates 0 errors ×3, `tools/provenance.py --baseline all --streams` rc 2 ×3 = the two
standing G2 identity findings (`unique_document_guid` / `central_episode_guid` inherited
from the composed base, #19) — the identical two findings and rc on the main-built file;
bare unzip of the rebuilt `tekton-plugin.zip`, `env -i /usr/bin/python3` (3.11.15):
`skills/tekton-edit/scripts/_bootstrap.py go edit <base copy> set-level --id 1351691
--elevation-ft 12.0 --json` ×3 → rc 0, `tekton: READY`, result.ok=True, stderr 0 B, wall
1.05 / 0.68 / 0.68 s, outputs **md5-identical to main's repo `rvt_edit` outputs**
(`8f9321bd…` / `17cc046e…` / `188355bc…`); `skills/tekton-author/scripts/_bootstrap.py go
author --prompt "an electrical room with 6 panels" --target-version 2025 --json` → rc 0,
`tekton: READY`, ok=True, `PROOF-ONLY (self-checks PASS …)`, combined `.rvt` + 12 family
files delivered, wall 5.7 s.

## BRANCH STATE (eng #467)

* Branch `cam/467-framing-by-name` from `main` @ fdcbf12; PR body starts `Closes #467`.
* Files written — sources: `src/rvt/reduce.py` (`_P` import; literal + `BLOCK_TRL_TAG`
  import gone; `NewBlock.frame` reads `_P.*`), `src/rvt/writer.py` (`_P` import, PEP 562
  `__getattr__` alias, literal gone, `regzip_partition_logical` reads `_P.*`),
  `src/rvt/commit.py`, `src/rvt/families.py`, `src/rvt/mep/conduit.py` (the
  `BLOCK_TRL_TAG` from-imports → `_P.TRAILER_TAG`), `src/rvt/manipulate.py` (inert
  handles + their import gone), `src/rvt/mep/electrical_data.py` + `src/rvt/regadd.py`
  (module reads for the ids32-rebound names), `src/rvt/frontdoor/release_ctx.py` (six
  swap rows + four imports gone, docstring/comment updated — nothing else),
  `tools/genesis_2025.py` / `genesis_2024.py` / `genesis_2023.py` (six `_LOCAL_TAG_PATCHES`
  rows gone + the comment paragraph above the tuple; nothing else); tests:
  `tests/test_framing_by_name.py` (new, 10 tests), `tests/ci_shard.d/467-framing-by-name.txt`
  (new), `tests/test_manipulate_import_context.py`, `tests/test_edit_own_release.py`,
  `tests/test_genesis_2025.py`, `tests/test_genesis_2024.py`, `tests/test_y2024.py`,
  `tests/test_y2025_b.py`; this record. Generated mirrors re-synced (`tools/sync_plugin.py`):
  `plugin/lib/src/rvt/{commit,families,manipulate,reduce,regadd,writer}.py`,
  `plugin/lib/src/rvt/mep/{conduit,electrical_data}.py`, `plugin/lib/src/rvt/frontdoor/release_ctx.py`.
* Not touched: `src/rvt/versions/**`, `src/rvt/partitions.py`, `src/rvt/famgen/**` and every
  other FENCED / NO-GO / hot file, `tests/ci_shard.txt`, `tests/conftest.py`.
* Residuals stated above: famgen's copies + `release_ctx`'s three `swap(FSK, …_TAG)` rows +
  the `writer` alias (#547, blocked on #498's campaign); `estorage.py:90` (#548);
  `records32` holder rows (#551); dev-only `experiments/genesis2025/subst/run_ladder2025.py`,
  `tools/make_v18.py`, `tools/make_v19.py`.
* Shipped vs staged: everything ships with the PR; nothing for the viewer — no byte of any
  front-door / edit output changes (three-base `cmp` + the pinned 30-file prompt job); the
  only outputs that change are ones `main` could not produce (reduce on a 2025/2024 file under
  the engine's own release ladder) or produced wrong (writer trailers there).
* Gates on the final head (`RVT_SKIP_LARGE=1 -p no:cacheprovider`): `tests/test_framing_by_name.py`
  10 passed (main: 9 failed / 1 passed); stream-local + neighbours 186 passed / 138 skipped /
  1 xfailed pre-simplify and the touched subset (`test_framing_by_name
  test_manipulate_import_context test_edit_own_release test_regadd test_y2024 test_y2025_b
  test_edit_text_release`) 89 passed / 29 skipped post-simplify; **whole merged CI shard**
  (`python3 tools/dev/shard_list.py --print`, 88 files incl. the new drop-in) →
  **1815 passed, 133 skipped, 3 xfailed in 493 s** on the first commit's code and
  **1815 passed, 133 skipped, 3 xfailed in 467 s** again on the final (post-simplify) code;
  `tools/sync_plugin.py` synced 9 then 6 files, `--check` clean; `plugin/scripts/validate_plugin.py`
  PASS (25 assertions); `tools/dev/check_portable_paths.py` ok (2943 paths). Follow-ups
  filed: #547, #548, #551.


## eng #548 — 2026-08-10 — the last residual of the class: `rvt.estorage` walks records with the walker in force

Stream: eng #548 (issue #548, `Refs #467 #455`; branch `cam/548-estorage-ids32` from `main` @ 7d04c82,
after PR #554 / #467 had merged as 074af6b). Written in eng #548's voice; the sections above are untouched.

### What was built (one variable)

`src/rvt/estorage.py:89-92` no longer takes a module-level by-value copy of `iter_records`
(`from .objects import (…, iter_records, field_key)` → the same import without `iter_records`, plus
`from . import objects as O`); its four seq-102 walks (`harvest_token_guids` :534, `es_report` :1050,
`verify_document` :1172, `collect_entity_closures` :1249) call `O.iter_records(seg, 102)` — a read
THROUGH `rvt.objects` at CALL time, the route the issue preferred, so `records32.ids32()`'s by-name
rebind of `objects.iter_records → iter_records32` now reaches the Extensible-Storage entity walk of a
≤ 2023 file. Nothing under `src/rvt/versions/**` changed and no `records32._patch_table` row became
redundant (estorage was never a listed holder; the eight `iter_records` holder rows are exactly as #551
found them). `tests/test_framing_by_name.py:271-272`: `KNOWN_RESIDUAL_IDS32` is now the empty set (the one
allow-listed pair `("src/rvt/estorage.py", "iter_records")` is gone), so #467's live AST source law covers
`estorage.py` like every other engine module. Read path only: no byte any route writes can change.

### Evidence (numbers)

* **New doors, red on `main`, green on the head** — `tests/test_estorage_ids32.py` (3 tests, synthetic
  32/64-bit seq-102 segments packed in the file from `docs/writer/format-2023.md`; no Autodesk bytes;
  in the shard via `tests/ci_shard.d/548-estorage-ids32.txt`):
  1. binding: `"iter_records" not in vars(rvt.estorage)`; `estorage.O.iter_records is iter_records32`
     inside `ids32()` and `is objects.iter_records` before/after;
  2. behaviour through the estorage entry point `harvest_token_guids(seg, decoder)` with a recording
     decoder: under `ids32()` a 32-bit segment visits exactly the `(class_id, payload)` pairs
     `iter_records32` yields (`[(0x0576, b"\x01\x02\x03"), (0x0819, b"")]`, sentinel skipped); outside
     the context the same bytes do NOT (matched fail half — the 64-bit walker yields `[]` on them), and a
     64-bit segment at rest yields the pair list;
  3. the #455 fresh-interpreter shape: a subprocess whose FIRST `import rvt.estorage` happens inside
     `ids32()` walks the 32-bit segment inside, and after exit walks the 64-bit segment == this
     process's in-context-free result and the 32-bit one != it. On `main`'s `estorage.py` that
     subprocess reports `after64 == []` — the by-value copy taken inside the context froze
     `iter_records32` for the life of the process (no engine module imports `rvt.estorage` at module
     level, so a first import inside `reading32` was a real possibility, e.g. `python -m rvt.estorage`
     on a 2023 file once #566 lands); with the head it is `[[1398,"010203"],[2073,""]]`.
  With `main`'s `src/rvt/estorage.py` stashed back in: `test_estorage_ids32.py` **3 failed** +
  `test_framing_by_name.py::test_every_module_level_copy_of_an_ids32_patched_name_is_a_listed_holder`
  **failed** (offender `src/rvt/estorage.py:90 … import iter_records (holders: [… rvt.regdiff])`);
  on the head all green (below).
* **Identity, head vs `main`, the one door that exercises estorage** (`grep -rn estorage src tools skills
  plugin/skills tests` → only `src/rvt/estorage.py` itself, its CLI, and `tests/test_estorage*.py`;
  `import rvt.validate, rvt.frontdoor` leaves `rvt.estorage` out of `sys.modules`, so `rvt_validate` /
  the front door cannot move): `python -m rvt.estorage <base> --report --walk --roundtrip`, entered under
  each base's own release (`with versions.reading(path)`, scratch driver — the bare CLI does not do that
  yet, filed as **#566**), stdout+stderr with the `in N.NNs` timing masked:
  `G_ABPD.rvt` (2026) **byte-identical** (md5 040f21a174b6…; 3102 host elements, 2 schemas
  `AREXContentGenerator` 6 tracked / `DaylightingAnalysisInfo` 1 tracked, walk host 1 `DataStorage`,
  round-trip examined 1 / entities 1 / clean 1 / undecodable 0 / byte-exact 1);
  `G_ABPD_2025.rvt` **byte-identical** (md5 dff650de68d5…; 2 schemas, 0 ES records, exit 0);
  `G_ABPD_2024.rvt` identical **except three traceback line numbers** (+1 from the added import line):
  both sides exit 1 in `schemas() → locate_schema_map` with the pre-existing
  `ESSchemaError: archive schema lacks 'std::pair< GUIDvalue, SchemaUsageInfo >'`, i.e. before any record
  walk — also in #566's DONE.
* `tools/rvt_validate.py` on the three bundled bases at the head: `G_ABPD` VALID, warnings=1 (the known
  `DataStorage x1` ES decoder-gap warning, element 1382860 — unchanged), `G_ABPD_2025` VALID warnings=0,
  `G_ABPD_2024` VALID warnings=0 — necessarily identical to `main` (estorage is not on that import path).

### Follow-ups (searched first: "estorage CLI own release", "python -m rvt.estorage" → only #548)

* **#566** (new, `Refs #548`, P2 · area:engine · ready · good-first-pick): `python -m rvt.estorage PATH`
  enters the file's own release (2025/2024 bases die on `unexpected Partitions header: v=9 cls=0x37b`
  today) and reports an honest empty catalog on the 2024 base instead of the `ESSchemaError` traceback.
* Nothing for #551: no holder row is made redundant by this change.

### /simplify and /verify (eng #548)

* `/simplify` (four review angles on the diff): reuse — clean (test helpers come only from
  `conftest.py` by convention; `test_records32`'s `rec32` is 32-bit only and importing that module would
  drag six engine modules into the fresh-interpreter door; no stub decoder exists to reuse); efficiency —
  clean (`O.iter_records` is one attribute read per walk, ~3 ns; `rvt.objects` was already imported by
  the next line; the one subprocess costs ~0.1 s); simplification/altitude — applied: one `seg(id_fmt)`
  builder + `SEG32`/`SEG64` constants instead of two copy-pasted builders, the tautological
  `ES.O is O …` conjuncts and the derivable fourth assertion of the subprocess door dropped, the import
  trailer in `estorage.py` cut to sibling density, the allow-list comment stripped of history narration,
  and the child asserts `"rvt.estorage" not in sys.modules` before its door so "FIRST import" is checked,
  not assumed. **Not applied, noted for the file's next owner (#551 reworks the holder rows and will touch
  this test):** two reviewers would delete the now-empty `KNOWN_RESIDUAL_IDS32` constant *and* its
  `not in` clause (`tests/test_framing_by_name.py:272,294`, 3 lines) so the source law is absolute; kept
  here because the issue's DONE is literally "becomes the empty set and the test stays green" and the
  brief granted this stream that single line of #467's file. Patch, for whoever takes it:
  delete `:271-272` and the `and (rel.replace(os.sep, "/"), a.name) not in KNOWN_RESIDUAL_IDS32` conjunct.
* `/verify` on the final tree: the tool this diff reaches is `rvt.estorage`'s own CLI —
  `python -m rvt.estorage plugin/assets/genesis/G_ABPD.rvt --report --walk` → 2 schemas, walk host 1
  `DataStorage`, exit 0; the scratch own-release driver on `G_ABPD` / `G_ABPD_2025` → output byte-identical
  to `main`'s (re-checked post-simplify with `cmp`). Because `src/` changed: `tools/sync_plugin.py`
  (synced `plugin/lib/src/rvt/estorage.py`, zip rebuilt 5288 KB), then a **bare unzip of
  `tekton-plugin.zip` with system `python3`**: `skills/tekton-author/scripts/_bootstrap.py go author
  --prompt "an electrical room with 6 panels" --out out/j1 --json` → `tekton: READY | python 3.11.15 |
  engine bundled | genesis verified (Revit 2026) | …`, exit 0, `result.ok: true`,
  `PROOF-ONLY (self-checks PASS …)`, 4.4 s wall (estorage is not on that path; this only shows the
  shipped mirror still boots).

## BRANCH STATE (eng #548)

* Branch `cam/548-estorage-ids32` from `main` @ 7d04c82, rebased onto 6250424 (#563, no file overlap) before
  the PR opened — stream-local files + #563's `test_release_ctx_refusal.py` re-run there: 57 passed / 1 xfailed,
  `sync_plugin.py --check` clean; PR body starts `Closes #548`.
* Files written — source: `src/rvt/estorage.py` (`from . import objects as O`; `iter_records` dropped
  from the `from .objects import (…)` list; four call sites → `O.iter_records(seg, 102)`; nothing else);
  tests: `tests/test_estorage_ids32.py` (new, 3 tests), `tests/ci_shard.d/548-estorage-ids32.txt` (new
  drop-in), `tests/test_framing_by_name.py` (`KNOWN_RESIDUAL_IDS32` → empty set + its comment; nothing
  else); this record (this section only). Generated mirror re-synced (`tools/sync_plugin.py`):
  `plugin/lib/src/rvt/estorage.py`.
* Not touched: `src/rvt/versions/**` (no table row added or removed), every NO-GO / FENCED / hot file
  of the brief, `tests/ci_shard.txt`, `tests/conftest.py`.
* Shipped vs staged: everything ships with the PR; nothing for the viewer — read path only, no byte any
  route writes can change (2026/2025 estorage door byte-identical to `main`; the three bases validate as
  before: VALID / warnings 1 (the known DataStorage ES gap) / 0 / 0).
* Gates on the final head (`RVT_SKIP_LARGE=1 -p no:cacheprovider`): `tests/test_estorage_ids32.py`
  3 passed (on `main`'s `estorage.py`: 3 failed) + `tests/test_framing_by_name.py` 10 passed (on `main`'s
  `estorage.py` with the empty allow-list: 1 failed); stream-local + neighbours
  (`test_estorage_ids32 test_framing_by_name test_records32 test_manipulate_import_context
  test_shard_list`) 72 passed / 1 xfailed, and `tests/test_estorage.py` 12 skipped (sample-backed, as on
  a fresh clone); **whole merged CI shard** (`python3 tools/dev/shard_list.py --print`, 93 files incl.
  the new drop-in) → **1900 passed, 134 skipped, 3 xfailed in 387 s** on the final tree (an earlier run
  started before the /simplify edits read 1899 passed / 1 failed only because the test file was renamed
  under the running child process — `T.seg32` → `T.SEG32`; re-run clean); `tools/sync_plugin.py` synced
  1 file, `--check` clean; `plugin/scripts/validate_plugin.py` PASS (25 assertions);
  `tools/dev/check_portable_paths.py` ok (2960 paths). Follow-up filed: #566.

## eng #566 — 2026-08-10 — `python -m rvt.estorage` reads a file under its OWN release; the 2024 catalog is an honest "0 schemas (reason)"

Stream: eng #566 (issue #566, `Refs #548 #533`; branch `cam/566-estorage-cli-release` from `main` @ 4bd7ecf,
i.e. after #570 / #548 and #572 / #533 had merged). Written in eng #566's voice; the sections above are untouched.

### What was built (two things, both inside `src/rvt/estorage.py`; nothing else in `src/`)

1. **The CLI enters the file's own release — the `tools/rvt_inspect.py` (#572) shape.** `main()` resolves the
   argument to a path (`_doc_path`: a `.rvt` path, or `samples/<project>.rvt`; a bare corpus project name still
   goes to `Document.load` with no context, as before), returns **2** on a missing path, and asks
   `_natively_framed(path)` — every `Partitions/<N>` header parses with the container class bound in
   `rvt.partitions` right now (2 ms on the 2026 base). A native file enters nothing and imports nothing extra;
   anything else lazily imports `rvt.global_framing.enter_own_release` and enters it ONCE on an `ExitStack` that
   wraps the load **and** every walk (`--report` / `--walk` / `--roundtrip` moved verbatim into `_report(doc,
   target, flags)` so the body did not re-indent), printing the ladder's note as `warning: …` on stderr when there
   is one (never on a certified pin). A file that then still cannot be loaded is `ERROR: cannot load <path>:
   <Type>: <message>` on stderr, exit **1** — a stated verdict, never a traceback. `print_catalog(cat, stream=None)`
   now resolves `sys.stdout` at call time (its old `stream=sys.stdout` default was bound at import, so a
   captured/redirected stdout lost the catalog block — found by the new test's `capsys`, invisible on a terminal).
   `_natively_framed` is the same predicate as `tools/rvt_inspect.natively_framed`; **note for eng #567**: once your
   predicate lands in `rvt/global_framing.py`, `estorage._natively_framed` (path-taking: it opens the container
   itself) can become a call to it — not adopted here because #567 had not merged at 4bd7ecf and that file is yours.
2. **The catalog locator's absent case reports instead of raising.** `locate_schema_map`'s no-class branch returns
   its documented "nothing located" triple `(-1, 0, {})` instead of `raise ESSchemaError("archive schema lacks
   'std::pair< GUIDvalue, SchemaUsageInfo >'")`; `schemas()` stamps the new `ESSchemaCatalog.note` (default `""`)
   with one derived sentence whenever the catalog comes back empty (`_no_map_reason(schema)`: pair class present
   but no entry located / no `ESSchemaStorage` at all / `ESSchemaStorage` present with a different ESSchema map —
   it names the member it finds, it does not guess); `print_catalog` prints `ES schema catalog: 0 schemas (<note>)`
   for an empty noted catalog and the unchanged `N schemas (map count …)` line otherwise. Harvest, tracking,
   entity codec, `es_report`, `verify_document`, `collect_entity_closures`: untouched (an empty catalog was already
   a legal input to all of them — the 2025 base has run that way since #548's by-hand driver).
   **Which of the issue's two alternatives, and why:** the class is *not* "merely named differently" on 2024. The
   2024 base's own `Formats/Latest` (4492 classes) has **no `SchemaUsageInfo` class**; its `ESSchemaStorage`
   (0x537) is `{m_storedForgeSchemas : pair<AString,AString>, m_storedParameterSchemas : pair<AString,AString>,
   m_storedSchemas : std::pair< GUIDvalue, ESSchema >, m_dirty}` — the catalog value is a bare `ESSchema` (0x536,
   same eight members as 2026's 0x56e), without the 2025+ `SchemaUsageInfo{m_contentDocsKeys, m_schema,
   m_usedInHost}` wrapper (2026: `ESSchemaStorage` 0x56f `m_schemaUsageMap`; the 2025 base has the 2026 layout).
   Reading that layout is new harvest semantics (a second entry shape for `_decode_pair_at` / `_schema_from_pair`),
   outside this issue's "empty/absent case only" territory → filed as **#576**; until then the report is the honest
   `0 schemas (this file's archive schema has no 'std::pair< GUIDvalue, SchemaUsageInfo >' -- its ESSchemaStorage
   keeps m_storedSchemas : std::pair< GUIDvalue, ESSchema >, an older catalog layout this module does not read
   yet, #576)` — quoted verbatim from the head's 2024 run.

### Evidence (numbers)

* **Before/after, the three bundled bases, `python -m rvt.estorage <base> --report --walk --roundtrip`**
  (stdout+stderr; scratch transcripts kept for the PR):
  `G_ABPD.rvt` (2026) — main: exit 0; head: exit 0, **byte-identical, unmasked** (`cmp` clean, md5 `36c9475fed40…`
  both sides incl. the `in 0.0s` timing; 3102 host elements, 2 schemas `AREXContentGenerator` 6 tracked /
  `DaylightingAnalysisInfo` 1 tracked, walk host 1 `DataStorage`, round-trip examined 1 / clean 1 / byte-exact 1).
  `G_ABPD_2025.rvt` — main: `ValueError: unexpected Partitions header: v=9 cls=0x391` from `Document.from_file →
  StreamWalker` (exit 1, pre-walk); head: exit 0, no stderr, `loaded G_ABPD_2025: 3316 host elements`, 2 schemas
  (map count 2 @0xe690f; tracking @0x137e0a; the same two GUIDs as 2026), ES report 2 schemas, round-trip examined
  0 records (0 ES entity records in this base — the same reading #548's by-hand `versions.reading` driver got).
  `G_ABPD_2024.rvt` — main: `… cls=0x37b` (exit 1, pre-walk; and behind it the locator's `ESSchemaError`); head:
  exit 0, no stderr, `loaded G_ABPD_2024: 3278 host elements`, the `0 schemas (…)` line quoted above, `ES report:
  0 schemas`, round-trip examined 0.  Wall time 0.44 / 0.66 / 0.44 s.
* **Damaged / absent inputs, head** (all seven: a stated line, no traceback): partition header zeroed (first 16
  bytes of `Partitions/<N>`, re-emitted with `cfb_writer`) on the 2026 and on the 2025 base → `ERROR: cannot load
  …: ValueError: unexpected Partitions header: v=0 cls=0x0`, exit 1 (the 2026 copy is not natively framed any
  more, climbs the ladder, resolves its own schema silently, then the load states the verdict); `Formats/Latest`
  mangled → 2026 copy: `ERROR: cannot load …: ParseError: …` exit 1; 2025 copy: `warning: own schema unreadable
  (ParseError …); checked against the pinned Revit 2025 framing table (the release BasicFileInfo declares)` then
  the same ERROR, exit 1; CFB header zeroed → `warning: own-release framing not resolved (NotOleFileError …)` +
  `ERROR: cannot load …: NotOleFileError`, exit 1; 64 KiB truncation → warning (VersionError: schema lacks the
  partition-framing classes) + `ERROR: … RuntimeError: Partitions/20: walker errors [...]`, exit 1; missing path →
  `ERROR: no such file: …`, exit 2.
* **Import weight of the 2026 (native) CLI path unchanged:** `-X importtime -m rvt.estorage G_ABPD.rvt --report`
  imports the **identical set of 107 modules** on main and head (`diff` of the sorted module lists empty; the 8
  `rvt.*` modules are `rvt, container, elemtable, encode, mutate, objects, partitions, schema` — no
  `global_framing`, no `versions`; `contextlib`, the one new module-level import, was already in the set); summed
  import self-time median of 5: main 120 ms / head 128 ms (run-to-run noise ±10 ms on this VM). The foreign path
  (2025/2024) imports 135 modules: + `rvt.global_framing`, `rvt.versions`, `rvt.versions.records32`,
  `rvt.adocument` and the famgen/genesis token holders `global_framing.bound()` rebinds — exactly what
  `rvt_inspect --records` pulls on the same files.
* **Validator on the three bases unchanged** (estorage is not on `rvt.validate`'s import path; run anyway):
  `G_ABPD` VALID errors 0 / warnings 1 (the known `DataStorage x1` ES decoder-gap warning, element 1382860),
  `G_ABPD_2025` VALID 0/0, `G_ABPD_2024` VALID 0/0.
* **New doors** — `tests/test_estorage_cli_release.py` (11 tests, 2.3 s, bundled bases only, in the shard via
  `tests/ci_shard.d/566-estorage-cli-release.txt`): full `--report --walk --roundtrip` on each certified pin
  (foreign first) with the catalog line derived from the pin's own schema (usage-map class present → `N schemas
  (map count`; absent → the honest `0 schemas (this file's archive schema has no …` + the member it names);
  `schemas(path)` / `locate_schema_map` from the library on each pin (empty + note + `(-1, 0, {})` where absent);
  the native pin never reaches `enter_own_release` (monkeypatched to raise); the real `-m` door in a fresh
  interpreter on the oldest foreign pin; header-zeroed copies of a foreign and the native pin → exit 1 + the ERROR
  line, stdout empty; missing path → exit 2; an autouse no-leak fixture (framing table, `active_release`,
  `objects.iter_records`, ADocument decoder, `FAMILY_END_RECORD` identical before/after every test).
  **Against `main`'s `estorage.py`: 11 failed** — [2024]/[2025] full report and the `-m` door on the
  `unexpected Partitions header` ValueError (the bug), [2024] library on the `ESSchemaError` (the bug), the two
  header-zeroed and the missing-path cases on raw `ValueError` / `FileNotFoundError` tracebacks (the bug),
  and [2026] full report / native-pin / [2025]-[2026] library only on the harness-visible differences (the
  import-time-bound `stream=sys.stdout` default hid the catalog block from `capsys`; `cat.note` did not exist).
  On the head: 11 passed.

### Follow-ups (searched first: "m_storedSchemas", "estorage 2024 catalog", "rvt.estorage own release" → only #566 / #548 / #50)

* **#576** (new, `Refs #566 #548`, P2 · area:engine · ready): read the ≤ 2024 `ESSchemaStorage.m_storedSchemas`
  layout so the 2024 base lists its schemas instead of the honest 0 (findings above are in its body).
* For **eng #567** (no issue needed — a one-line adoption inside their open stream): `estorage._natively_framed`
  is a by-path twin of `rvt_inspect.natively_framed`; fold it onto the `global_framing` predicate when it exists.

### /simplify and /verify (eng #566)

* `/simplify` — four review angles on the diff (reuse, simplification, efficiency, altitude), then applied:
  `_load_doc` dropped (its only caller had already resolved `_doc_path`; `main` now loads inline and resolves the
  path once); the missing-path check hoisted above the `ExitStack` (one nesting level gone); `print_catalog`'s
  lambda is `print(*a, file=stream)` (`file=None` already means the current `sys.stdout`); `_no_map_reason` folded
  from three branches to two (pair class present / absent — the absent branch derives the member list from
  whatever `ESSchemaStorage` the schema has, or says "no ESSchema map at all"); `locate_schema_map`'s docstring cut
  to one clause; `_natively_framed`'s docstring points at its intended engine home (`rvt.native_framing`, #567 /
  PR #577) instead of citing a tool as canonical; in the test: the native "ladder never reached" check folded into
  the parametrized full-report run (one 0.3 s CLI run fewer → 10 tests, 2.0 s), the restated `"0 schemas" not in`
  and catalog-offset assertions dropped. **Reviewed and kept, with the reason:** (efficiency) `_natively_framed`
  reads + de-pages every partition stream only to parse 18 header bytes, and `Document.from_file` then re-reads
  them — measured 0.47 ms on the pins (0.1 % of a 350–420 ms run) but linear, ≈3 ms/MB of partition data on a
  *native* file (162 ms on a synthetic 50 MB partition); the zero-cost alternative (EAFP: load first, enter the
  ladder and retry only on the header `ValueError`) was declined to keep the exact predicate semantics of the two
  sibling instruments and of #577's shared `natively_framed(doc)` this folds onto — the real cure is an O(1)
  stream-head accessor in `container.py` that would make the shared predicate O(partitions) for all three callers
  (noted on #567's thread; not filed separately — it belongs to whoever measures #577's callers on a large project);
  (altitude) the locator collapsing "class absent" and "nothing located" into one triple while `schemas()`
  re-derives which — acceptable while both read the same `by_name` fact, to be revisited when #576 gives the
  locator a second layout branch (then it should return the reason itself); (simplification) `if not len(cat) and
  cat.note` keeps its `len` guard on purpose — a note on a non-empty catalog must never print "0 schemas";
  (reuse) the test scaffolding is now a sixth copy → filed **#579** rather than a seventh next time.
* `/verify` on the final tree — the surface this diff reaches is `rvt.estorage`'s own CLI: the three bases with
  `--report --walk --roundtrip` → exit 0 / 0 / 0, four sections each, no stderr; 2026 stdout `cmp`-identical to
  `origin/main`'s; the two header-zeroed copies → the `ERROR: cannot load …: ValueError: unexpected Partitions
  header: v=0 cls=0x0` line, exit 1; a missing path → `ERROR: no such file`, exit 2; mirror `cmp`-identical to
  source. Because `src/` changed: `tools/sync_plugin.py` (1 file synced, zip rebuilt 5292 KB), then a **bare unzip
  of `tekton-plugin.zip`, `env -i` system `python3` 3.11**: `skills/tekton-author/scripts/_bootstrap.py go author
  --prompt "an electrical room with 6 panels" --out out/j1 --json` → rc 0, `result.ok: true`, 4.5 s wall (estorage
  is not on that path; this shows the shipped mirror still boots); and the mirrored CLI itself from the unzip
  (`PYTHONPATH=lib/src:skills/_shared/_vendor python3 -m rvt.estorage assets/genesis/<base> --report --walk
  --roundtrip`) → exit 0 ×3, four sections, no warnings, 2026 stdout identical to the repo's. Honest footnote:
  without the vendored `olefile` dir on the path that bare `-m` invocation dies at `import olefile` — on `main` too
  (`Document.from_file` imports `rvt.container`); the dev CLI is not a bootstrap-wrapped skill script and needs the
  engine's one runtime dependency, as documented.

### Fold onto `rvt.native_framing` after #577 merged (tech-lead ruling, same branch, rebased onto `main` @ 6084e78)

* `estorage._natively_framed(path)` is **deleted**; `main()` now opens the container once for the probe and hands
  the open document to the shared helper — `with open_rvt(path) as f: note = enter_files_release(stack, f, path)`
  (`rvt.native_framing`, default ladder = `global_framing.enter_own_release`, imported inside that function only when
  the predicate says foreign; a note, never a raise) — then loads. No third variant was added to `native_framing.py`.
  The open + probe + load sit in one `try`, so a file that cannot even be opened as a container is the same single
  `ERROR: cannot load …: NotOleFileError: …` line, exit 1 (before the fold that case printed a redundant ladder
  `warning:` first; every other transcript is byte-identical to the pre-fold head: the three bases `cmp` clean —
  2026 still `cmp`-identical to `main`@4bd7ecf's unmasked — header-zeroed ×2, schema-mangled, truncated, missing).
  This is also where the record states plainly the **one library-visible change of this PR**: `schemas()` (and
  `locate_schema_map`) return an empty, noted catalog / the `(-1, 0, {})` triple on a schema without the pair class
  where they used to raise `ESSchemaError` — accepted by the tech lead as inside the issue's territory.
* `-X importtime`, native 2026 `-m rvt.estorage … --report` path: `main`@4bd7ecf 107 modules → head **108: exactly
  +1, `rvt.native_framing`** (self 0.22 ms; nothing else added or removed — still no `global_framing` / `versions`);
  the 2025 (foreign) path 135 → 136, the same +1.
* Gates after the fold: `tests/test_estorage_cli_release.py` 10 passed, `tests/test_natively_framed.py` 16 passed,
  `tests/test_estorage_ids32.py` 3 passed (29 in 2.4 s); neighbours `test_inspect_release` 13 / `test_selfcheck_release`
  9 / `test_framing_by_name` 10 passed, `test_estorage` 2 passed 12 skipped; `tools/sync_plugin.py` synced 1 file,
  `--check` clean; `validate_plugin.py` PASS; portable paths ok (2976). (`test_natively_framed`'s AST "no private
  copy" law lists the two tools; adding `src/rvt/estorage.py` to it is a one-line follow-up for that file's next
  owner — not in this stream's territory.)

## BRANCH STATE (eng #566)

* Branch `cam/566-estorage-cli-release` from `origin/main` @ 4bd7ecf (after #570/#548 and #572/#533), rebased onto
  6084e78 once #577 (#567) merged and folded onto `rvt.native_framing` (above); PR #580, body starts `Closes #566`.
* Files written — source: `src/rvt/estorage.py` (module docstring CLI paragraph; `import contextlib`;
  `ESSchemaCatalog.note`; `locate_schema_map` no-class branch → `(-1, 0, {})` + docstring; `schemas()` stamps
  `cat.note` via new `_no_map_reason`; CLI section: `_doc_path`, `print_catalog(stream=None)` +
  its empty-catalog line, `main` (exit-2 check, `ExitStack`, one `open_rvt` + `native_framing.enter_files_release`, load verdict) and the old body as
  `_report`); tests: `tests/test_estorage_cli_release.py` (new, 10 tests), `tests/ci_shard.d/566-estorage-cli-release.txt`
  (new drop-in); this record (this section only). Generated mirror re-synced: `plugin/lib/src/rvt/estorage.py`.
* Not touched: `src/rvt/versions/**`, `src/rvt/global_framing.py` (#567's), `objects.py`, `mutate.py`,
  `container.py`, every NO-GO / FENCED / hot file of the brief, `tests/ci_shard.txt`, `tests/conftest.py`.
* Shipped vs staged: everything ships with the PR; nothing for the viewer — read path + a dev CLI only, no byte any
  route writes can change (2026 CLI stdout byte-identical to `main`; the three bases validate as before: VALID,
  warnings 1 / 0 / 0).
* Follow-ups filed: **#576** (read the ≤ 2024 `m_storedSchemas` catalog layout), **#579** (hoist the own-release
  test scaffolding into `conftest.py`); hand-off comment on **#567** (fold `estorage._natively_framed` onto
  `rvt.native_framing` once #577 is on main).
* Gates on the final head (`RVT_SKIP_LARGE=1 -p no:cacheprovider`): `tests/test_estorage_cli_release.py` **10 passed**
  (2.0 s; against `main`'s `estorage.py` the pre-simplify 11-test form was 11 failed, see Evidence); stream-local +
  neighbours (`test_estorage_cli_release test_estorage_ids32 test_estorage test_framing_by_name test_inspect_release
  test_shard_list test_manipulate_import_context`) **66 passed / 12 skipped** (the 12 = `test_estorage.py`'s
  sample-backed cases, as on any fresh clone) before /simplify, re-run after: see below; **whole merged CI shard**
  (`python3 tools/dev/shard_list.py --print`, 97 files incl. the new drop-in): **1942 passed, 134 skipped, 3 xfailed in 403 s**, 0 failed;
  `tools/sync_plugin.py` synced 1 file, `--check` clean; `plugin/scripts/validate_plugin.py` PASS (25 assertions);
  `tools/dev/check_portable_paths.py` ok (2972 tracked paths). (An earlier whole-shard run, started before the
  /simplify edits and overlapping them, read 1941 passed / 2 failed — `test_plugin_sync` on the not-yet-re-synced
  mirror and the `-m` subprocess door catching the tree mid-edit (`NameError: _load_doc`); both artefacts of editing
  under a running shard, the mistake #548's record also confesses — the canonical run above was taken on the frozen
  final tree.)

## eng #576 — 2026-08-11 — `rvt.estorage` reads the Revit ≤ 2024 catalog layout (`ESSchemaStorage.m_storedSchemas`): the 2024 base lists its 2 schemas

Stream: eng #576 (issue #576, `Refs #566 #548`; branch `cam/576-estorage-catalog-2024` from `main` @ db32071).
Written in eng #576's voice; the sections above are untouched. Read-only forensic capability on our own bundled base:
no writer change, no byte any route writes can change, nothing sample-derived checked in.

### What was built (all inside `src/rvt/estorage.py`'s catalog locate/decode section; harvest / entity codec / verify / closures / CLI untouched)

1. **The layout is read off the file's own `ESSchemaStorage`.** New `CatalogLayout` (frozen dataclass: `member`,
   `pair_class`, `pair_id` in THIS file's schema, `tail` = bytes of one entry after `ESSchema.m_guid`, `tail_re` =
   the GUID-free anchor pattern) and `catalog_layout(schema) -> CatalogLayout | None`: of the two layouts the module
   chains — `m_schemaUsageMap : std::pair< GUIDvalue, SchemaUsageInfo >` (2025+, tail 9 = read u32 + write u32 +
   usedInHost u8) and `m_storedSchemas : std::pair< GUIDvalue, ESSchema >` (≤ 2024, tail 8, the value IS the schema)
   — the first whose pair class exists in the file's schema **and** is the type of an `ESSchemaStorage` member wins
   (membership matters: the 2025 base defines an unused `std::pair< GUIDvalue, ESSchema >` 0x1187 next to its real
   `m_schemaUsageMap`; a schema with no `ESSchemaStorage` at all still accepts the pair class alone, as before). The
   module constant `_PAIR_CLASS` and the module-level `_TAIL_RE` are gone (folded into the `_LAYOUTS` table).
   `locate_schema_map` / `_decode_pair_at` / `_chain_map` / `_tail_scan_seeds` take the layout instead of a bare
   `pair_id`; the entries are still decoded by the generic `ObjectDecoder` against the file's own `Formats/Latest` —
   no hand-written byte layout anywhere. `_entry_schema(v)` returns `(ESSchema dict, SchemaUsageInfo dict | None)`
   for either value shape; `_schema_from_pair` builds the same `ESSchemaDef` from both, with `used_in_host = None`
   (type widened to `Optional[bool]`) and `content_docs_keys = []` on the older layout — absent, never invented;
   `print_catalog` prints `usage-unrecorded` for `None` (2025/2026 lines unchanged: `used` / `unused`).
   `_no_map_reason` names `ESSchemaStorage.<member>` when a layout exists but nothing was located, else lists both
   known pair classes and what the file's `ESSchemaStorage` keeps. `ESSchemaCatalog`'s shape is unchanged (`note`
   is `""` on all three pins now).
2. **Two locator laws the older layout exposed** (both measured on the 2024 base, both fixed for both layouts, both
   provably output-neutral on 2025/2026 — below): (a) `_chain_map`'s backward walk no longer stops on "u32 before the
   first recovered entry == entries recovered so far" — on the older layout the u32 before an *inner* entry is the
   previous entry's `m_writeAccessLevel` (1..3), so a seed on entry 2 alone returned a 1-entry "map" (count 1
   "verified" by entry 1's write level); it now places the previous entry whenever one decodes ending exactly at the
   current first entry (GUID taken `16 + tail` bytes back, low-entropy GUIDs skipped) and stops only when none does —
   the u32 then in front is the container count (`_run_length` went with the old rule); (b) `locate_tracking(gl,
   guids, skip=(lo, hi))`: `schemas()` passes the catalog map's own byte span, because an entry key followed by
   `m_documentation = ""` reads as a tracking item with 0 ids and, on the older layout, the u32 before entry 2's key
   (entry 1's write level = 1) "verified" it as a 1-item table at 0xfe72b — which beat the real, unverifiable table.
3. **Finding (documented, not coded around):** the 2024 base's real `EStorageTracking.m_trackingItems` has **7**
   items (count @0xff92e): five leading items keyed by structured GUIDs that are in no catalog and occur nowhere in
   the 2025/2026 bases (`30000001-6e79-430c-adf9-634f716c5f5d`, `30000001-62e6-416d-a34a-bb3064350b62`,
   `20000002-6e79-…`, `20000002-62e6-…`, `10000005-db1a-45fc-9eed-810262792b5b`; 0/1 ids each, element 49504), then
   the two catalogued items — byte-identical to the 2025 base's two. Only catalogued GUIDs anchor items, so the 2024
   table comes back through the pre-existing unverified-count fallback (right ids: 6 / 1; `tracking_offset` = run
   start − 4 = 0xff9a2, not the count offset) — written up with offsets in `docs/writer/extensible-storage.md` §2.1b
   and filed as a follow-up rather than widening this stream into the tracking reader.
4. `docs/writer/extensible-storage.md`: new §2.1b (the ≤ 2024 layout, class ids, the 8-byte tail, a byte-for-byte
   worked hexdump of `G_ABPD_2024` entry 1 @0xfe67d with count 2 @0xfe679, the two locator consequences, the 7-item
   tracking table), §2.2's chain/tail sentences generalised, §2.4 gains the three bundled bases' rows. Whether Revit
   ≤ 2023 shares the 2024 layout is **unmeasured** (no 2023 base in the bundle) and the doc says so.
5. **Tech-lead-authorised territory extension** (asked and answered in-session before pushing):
   `tests/test_estorage_cli_release.py` hard-coded the old 2024 verdict (`ES._PAIR_CLASS`, "0 schemas (…)",
   `len(cat) == 0`) and would be 6-red on this head whatever the new file says; issue #576's own DONE bullet 3 says its
   2024 branch flips. Exactly four hunks changed there — the predicate (`_has_usage_map_class` →
   `_has_catalog_layout()` = `ES.catalog_layout(schema) is not None`), the two else-branch strings, the docstring
   bullet — and nothing in the scaffolding helpers eng #579 is hoisting. All new rows live in the new file.

### Evidence (numbers)

* **`python -m rvt.estorage plugin/assets/genesis/<base>.rvt --report --walk --roundtrip`, before → after** (stdout+stderr,
  scratch transcripts kept): `G_ABPD_2024` — main @db32071: exit 0, `ES schema catalog: 0 schemas (this file's archive
  schema has no 'std::pair< GUIDvalue, SchemaUsageInfo >' -- its ESSchemaStorage keeps m_storedSchemas : std::pair<
  GUIDvalue, ESSchema >, an older catalog layout this module does not read yet, #576)`, `ES report: 0 schemas`;
  head: exit 0, no stderr,
  `ES schema catalog: 2 schemas (map count 2 @0xfe679 in Global/Latest; tracking @0xff9a2)` /
  `  4c817959-0028-4a83-b3e7-cd1e832a459a  'AREXContentGenerator' vendor='' usage-unrecorded fields=1 read=Public write=Public tracked_elements=6` / `      [ 0] Identity: TCHAR` /
  `  5d9588ee-e6c7-4c96-87dc-df2a5fbe6613  'DaylightingAnalysisInfo' vendor='ADSK' usage-unrecorded fields=2 read=Public write=Vendor tracked_elements=1` / `      [ 0] AnalysisId: TCHAR` / `      [ 1] ResultsInvalid: int` /
  `ES report: 2 schemas` with `'AREXContentGenerator' …: tracked elements 6 (first [1372292, 1372482, 1375817, 1376990, 1377250])` and
  `'DaylightingAnalysisInfo' …: tracked elements 1 (first [1382860])`, `round-trip: examined 0 records` (0 ES entity records in this
  base, as on 2025). `G_ABPD` (2026) and `G_ABPD_2025`: exit 0 both sides, stdout+stderr **byte-identical to main** with the
  `in N.NNs` timing masked (`diff` empty; 2026: 2 schemas, walk host 1 `DataStorage`, round-trip examined 1 / clean 1 / byte-exact 1;
  2025: 2 schemas @0xe690f, tracking @0x137e0a, 0 ES records).
* **Library seam:** `schemas(path)` under `global_framing.reading(path)`: 2024 → 2 entries, `.note == ""`, `.order == [4c817959…,
  5d9588ee…]`, `used_in_host is None` ×2, tracking `{…459a: 6 ids, …6613: [1382860]}`; sha256[:16] of `to_json()` minus `source`,
  head vs main: 2026 `2d621ae50133432e` == `2d621ae50133432e`, 2025 `43f8ad756ff22977` == `43f8ad756ff22977` (entry count 2 / map
  count 2 / map offset / tracking offset identical), 2024 `2f5ede2e29d13ec4` (main: empty catalog `67430599e05e72ac`).
* **New doors** — `tests/test_estorage_catalog_2024.py` (9 tests, 1.2 s; bundled bases + synthetic schemas only; in the shard via
  `tests/ci_shard.d/576-estorage-catalog-2024.txt`): [2024] layout `m_storedSchemas`/tail 8, catalog = the two expected schemas
  (GUIDs, names, vendor, field names/types), note empty, `used_in_host None` / `contentDocsKeys []`, tracking 6 / `[1382860]`;
  [2024] CLI `--report` lists both lines verbatim, no `0 schemas`; [2025][2026] layout `m_schemaUsageMap`, `used_in_host is True`,
  `(len, map_count, digest) == MAIN_DIGEST`; [2024][2025][2026] the map **re-encoded by our own `ObjectEncoder`** between junk →
  GUID-free scan finds it at the exact count offset AND a seed on the LAST entry alone chains back to the first (the row that was
  red until law (a): `(214, 1) != (36, 2)` on the 2024 layout), junk alone → `(-1, 0, {})`; synthetic schemas: both pair classes +
  `ESSchemaStorage{m_schemaUsageMap}` → usage layout, `ESSchemaStorage{m_storedSchemas}` → older layout (tail 8, its pair id), a
  pair class `ESSchemaStorage` does not hold → `None` + the note names what it keeps, pair class with no `ESSchemaStorage` → still a
  layout, neither → `None`; `_entry_schema` / `_schema_from_pair` on both value shapes. **Against `main`'s `estorage.py`: 9 failed**
  (the 2024 rows on the behaviour, the rest on the missing seam); on the head 9 passed. `tests/test_estorage_cli_release.py`
  (the four authorised hunks): 10 passed on the head (6 failed before the hunks, on `ES._PAIR_CLASS` / the old 2024 strings).
* Validator on the three bases (estorage is not on `rvt.validate`'s import path; run anyway): `G_ABPD` VALID warnings=1 (the known
  `DataStorage x1` ES decoder-gap warning, element 1382860), `G_ABPD_2025` VALID 0, `G_ABPD_2024` VALID 0 — unchanged.

### Follow-ups (searched first: "EStorageTracking", "locate_tracking", "m_trackingItems", "uncatalogued" → nothing open)

* Filed: `locate_tracking` verifies a table led by uncatalogued items (the 2024 base: 7 items @0xff92e, 5 internal GUIDs) so
  `tracking_offset` is the true count offset and the uncatalogued tracked GUIDs are reported rather than dropped — task-shaped,
  `Refs #576`, P2 · area:engine · S (number in BRANCH STATE below).

### /simplify and /verify (eng #576)

* `/simplify` — four review angles on the diff (reuse, simplification, efficiency, altitude), then applied: `_LAYOUTS` is a
  tuple of `CatalogLayout` prototypes (`pair_id` filled by `dataclasses.replace` in `catalog_layout`; `tail_re` typed
  `re.Pattern[bytes]`) instead of anonymous 4-tuples unpacked positionally in two places; the "pair class alone, no
  `ESSchemaStorage`" third mode is gone (altitude: it re-admitted exactly the ambiguity the 2025 base's stray 0x1187 pair
  shows — a schema without `ESSchemaStorage` now has no layout and the note says so); the backward walk is a
  `_place_previous()` helper (`while _place_previous(...): pass` + one return, no while/else) with an **O(1) tail
  pre-check** (`lay.tail_re.match(gl, first - tail)`) and a shared `_plausible_guid()` (also used by `_tail_scan_seeds`)
  before any `bytes.find` — efficiency had measured the always-walk-back rule at +360 failing find+decode attempts /
  +14 ms per `schemas()` on the 2025/2026 pins (the 16 bytes in front of the map are UTF-16 JSON text occurring 360× in
  the window); with the pre-check `locate_schema_map` on the pins is back to **exactly `origin/main`'s 638 decode attempts,
  36–38 ms best-of-5 (main 36 ms)**, and 651 attempts / 68 ms on 2024 (new capability); the older layout's anchor regex is
  the consuming 8-byte pattern, not a zero-width lookahead (3× fewer candidates: 2024 no-seed path 1807 → 651 decodes,
  149 → 68 ms, and `max_hits` covers the same stream length per hit density as the 9-byte pattern); `content_docs_keys`
  needs no conditional; `map_span` hi is `entries[max(entries)][0]`; the print token is a plain conditional;
  `ESSchemaCatalog.layout` (member name) records which layout a catalog was read with (data only — not printed in the
  header and not in `to_json()`, so 2025/2026 stdout and digests stay identical); module docstring states both layouts up
  front. Tests: the restated `to_json()["usedInHost"]` assertion dropped, layout bound once, `cat.layout` asserted, the
  pair-alone row flipped to `None`. **Reviewed and kept, with the reason:** (altitude) `tail` stays a stated per-layout
  constant rather than derived from field kinds — a wrong tail cannot produce a false entry (every entry is a full decode +
  key == `m_guid`), it can only locate nothing, which is already an honest noted empty catalog; (altitude) `skip=(lo, hi)`
  on `locate_tracking` is the correctly-oriented stopgap (tracking stays catalog-agnostic) until #595 verifies tables led
  by uncatalogued items — its docstring says it removes the known false positive only; (simplification) the now-dead
  `else:` branches of `tests/test_estorage_cli_release.py`'s two layout checks were NOT deleted — the tech lead authorised
  exactly four hunks in that file (eng #579 is hoisting its scaffolding); patch for its next owner: drop
  `_has_catalog_layout` and both `else:` arms, the absent-layout path is covered synthetically in
  `tests/test_estorage_catalog_2024.py`; (simplification) `MAIN_DIGEST` keeps `(len, map_count, digest)` for a readable
  failure message.
* `/verify` on the final tree — the surface this diff reaches is `rvt.estorage`'s CLI and library: the three bases with
  `--report --walk --roundtrip` → exit 0 ×3, no stderr, 2026/2025 stdout identical to `origin/main`'s (timing masked),
  2024 the catalog lines quoted in Evidence; library digests as in Evidence; a 64 KiB truncation of the 2024 base →
  `warning: own schema unreadable (ParseError …); checked against the pinned Revit 2024 framing table …` + `ERROR: cannot
  load …: RuntimeError: Partitions/21: walker errors […]`, exit 1; a missing path → `ERROR: no such file`, exit 2. Because
  `src/` changed: `tools/sync_plugin.py` (1 file synced, mirror `cmp`-identical, zip rebuilt 5299 KB), then a **bare unzip
  of `tekton-plugin.zip`, `env -i` system `python3` 3.11**: `skills/tekton-author/scripts/_bootstrap.py go author --prompt
  "an electrical room with 6 panels" --out out/j1 --json` → rc 0, `go.ready true`, preflight `tekton: READY | python
  3.11.15 | engine bundled | genesis verified (Revit 2026) | …`, `result.ok true`, `PROOF-ONLY (self-checks PASS …)`,
  4.4 s wall (estorage is not on that path; it shows the shipped mirror still boots); and the mirrored CLI itself from the
  unzip (`PYTHONPATH=lib/src:skills/_shared/_vendor python3 -m rvt.estorage assets/genesis/<base>.rvt --report --walk
  --roundtrip`) → rc 0 ×3, 2024 lists the 2 schemas, 2026 stdout identical to the repo run.

## BRANCH STATE (eng #576)

* Branch `cam/576-estorage-catalog-2024` from `origin/main` @ db32071; PR body starts `Closes #576`.
* Files written — source: `src/rvt/estorage.py` (module docstring; `ESSchemaDef.used_in_host: Optional[bool]`;
  `ESSchemaCatalog.layout`; `_entry_schema`; `_schema_from_pair` for both shapes; `CatalogLayout` + `_LAYOUTS` +
  `catalog_layout` + `_plausible_guid`; `_decode_pair_at` / `_chain_map` (+ new `_place_previous`, `_run_length` gone) /
  `_tail_scan_seeds` / `locate_schema_map` take the layout; `_PAIR_CLASS` and `_TAIL_RE` gone; `locate_tracking(skip=)`;
  `schemas()` sets `layout` and passes the map span; `_no_map_reason`; `print_catalog`'s usage token — nothing in the entity
  codec, `ESDecoder`/`ESEncoder`, `es_report`, `verify_document`, closures or the CLI flow); tests:
  `tests/test_estorage_catalog_2024.py` (new, 9 tests), `tests/ci_shard.d/576-estorage-catalog-2024.txt` (new drop-in),
  `tests/test_estorage_cli_release.py` (the four tech-lead-authorised hunks: predicate, two strings, docstring bullet);
  docs: `docs/writer/extensible-storage.md` (§2.1b new, §2.2 two sentences, §2.4 two rows), this record (this section
  only). Generated mirror re-synced: `plugin/lib/src/rvt/estorage.py`.
* Not touched: `src/rvt/versions/**`, `objects.py`, `schema.py`, `tests/conftest.py`, every NO-GO / FENCED / hot file of
  the brief, `tests/ci_shard.txt`, `TRACKER.md`, `KNOWLEDGE.md`.
* Shipped vs staged: everything ships with the PR; nothing for the viewer — read path of a forensic instrument only, no
  byte any route writes can change (2026/2025 CLI stdout and catalog digests identical to `main`; the three bases validate
  as before: VALID, warnings 1 / 0 / 0).
* Follow-up filed: **#595** (`locate_tracking` verifies a table led by uncatalogued items; 2024 base: 7 items @0xff92e).
* Gates on the final head (`RVT_SKIP_LARGE=1 -p no:cacheprovider`): stream-local
  `tests/test_estorage_catalog_2024.py tests/test_estorage_cli_release.py tests/test_estorage_ids32.py tests/test_estorage.py`
  → **24 passed, 12 skipped** (the 12 = `test_estorage.py`'s sample-backed cases + its `RVT_SKIP_LARGE` case, as on any
  fresh clone; new file 9 passed — 9 failed against `main`'s `estorage.py`); **whole merged CI shard**
  (`python3 tools/dev/shard_list.py --print`, 101 files incl. the new drop-in): first run on the pre-/simplify tree
  **2021 passed, 134 skipped, 3 xfailed, 0 failed in 432 s**; canonical re-run on the frozen final tree: see the PR body;
  `tools/sync_plugin.py` synced 1 file, `--check` clean; `plugin/scripts/validate_plugin.py` PASS (25 assertions);
  `tools/dev/check_portable_paths.py` ok (2983 tracked paths); `tools/rvt_validate.py` on the three bases VALID 1/0/0 warnings.
