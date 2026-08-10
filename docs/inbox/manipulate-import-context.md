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
