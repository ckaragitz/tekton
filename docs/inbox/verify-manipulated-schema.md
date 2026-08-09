# verify-manipulated-schema — the edit verifier judges a file under its OWN release (issue #11)

Stream: engineer session for #11, 2026-08-09 (cloud, fresh clone; fanned
out by the tech-lead session under steers #58/#61). Charter (#11):
`rvt.manipulate.verify_manipulated` must resolve the schema (and framing)
from the file being verified, for every release, instead of the built-in
2026 constants. Territory: `src/rvt/manipulate.py` (`verify_manipulated`
only), new `tests/test_verify_manipulated_release.py`, `tests/ci_shard.txt`
(+1 line), this record, regenerated mirror `plugin/lib/src/rvt/manipulate.py`.
`src/rvt/versions/records32.py` read as reference only; `src/rvt/versions/`
(hot) is *called*, not edited. Precedent followed: #50 / #51
(`validate.enter_own_release`, `docs/inbox/validate-release-aware.md`).

## The defect, reproduced (before any change, this clone, tracked bases)

Recipe: raise level `1351691` of each pinned base by 1.25 ft through the
product path (`release_build_context(base)` → `Document.from_file` →
`set_level_elevation` → `commit_plans`), then call
`verify_manipulated(out, edited_ids=[1351691])` from three contexts.

| edited file | inside `release_build_context` | inside `V.reading(base)` only | bare (no context — `tools/rvt_edit.py`, `famload`, tests, tools) |
|---|---|---|---|
| 2026 (`G_ABPD`) | Level clean ✔ | Level clean ✔ | Level clean ✔ |
| 2025 (`G_ABPD_2025`) | Level clean ✔ | **101 → `ElementAndGRep` clean=False, 102 → `JoinTrackerAppInfo` clean=False, 103 → `RvtLinkConversionData` clean=False** (false red on a good edit) | **raises `ValueError: unexpected Partitions header: v=9 cls=0x391`** |
| 2024 (`G_ABPD_2024`) | Level clean ✔ | **102 → `LinkLoadContent` clean=False**, 101/103 mis-named likewise | **raises `… cls=0x37b`** |

Two independent causes: (1) the clean-decode probe built `ObjectDecoder()`
over the built-in latest-release schema, so 2025/2024 class ordinals were
looked up in the 2026 table (only the front door happened to mask this,
because `release_ctx` swaps `objects.load_schema`); (2) nothing put the
file's framing ordinals in force, so a bare call could not even parse the
partition header. A third, latent for ≤ 2023 only: the stamp check sliced
the record body at a baked `+16` (64-bit header width) — the same bake
`records32.verify_manipulated32` was written to work around.

## What was built

* `src/rvt/manipulate.py::verify_manipulated`
  * Enters the file's own release for the whole verification through the
    existing three-rung ladder `rvt.validate.enter_own_release(stack, path)`
    (own schema by name via `reading32` — which also arms the 32-bit id
    layer for ≤ 2023 — → the pinned table of the release `BasicFileInfo`
    declares → built-in constants). Nest-safe inside a caller's `reading`;
    `rvt.partitions` constants restored on exit. No ladder was
    re-implemented; the one in `validate.py` is reused as-is.
  * Decodes edited records with `ObjectDecoder(versions.schema_of(d))` —
    the schema the open document itself carries in `Formats/Latest`. If
    that schema cannot be parsed it degrades to `ObjectDecoder()` (built-in)
    and says so.
  * New report key `rep["fallbacks"]: list[str]` — empty when framing and
    schema both came from the file; otherwise one sentence per rung taken
    and why. A label, never a raise (hard rule 1). All existing keys and
    their meaning are unchanged, so `tools/rvt_job.py`'s structural gate,
    `famload`, `mep.electrical_data.verify_electrical` etc. need no change.
  * The seq-102/103 stamp is recomputed as
    `adler32(u16 class_id ‖ payload)` from the parsed `Record` instead of
    slicing `seg[off+16 : …]` — byte-for-byte the same input on 64-bit-id
    files (proven: stamps still all-ok on the three bases, and a
    deliberately wrong stamp is still caught), and no longer width-baked,
    so under `reading32` on a 2023 file the core function is now correct on
    its own (module globals `iter_records` / `decode_elemtable` are already
    swapped by `records32.ids32`). Not exercised here — no 2023 file is
    tracked — hence stated as reasoning, not evidence.
* `tests/test_verify_manipulated_release.py` (7 tests, fresh-clone
  runnable, ~7 s): per release 2024/2025/2026 a real edit committed through
  `release_build_context` verifies **bare** with the exact expected triple
  `{101: ElementHeader, 102: Level, 103: SerializedDummy}` all clean and
  `fallbacks == []`; nested inside `V.reading(year=2025)` a 2024 edit
  verifies the same and the outer ordinals survive the call; a
  **structurally impeccable but semantically corrupted** 2025 edit (8 stray
  bytes appended to the Level object, stamp recomputed, framing valid)
  passes every framing/stamp check and is caught *only* by the own-schema
  decode (`102: {Level, clean: False}`) — the matched pair to the honest
  edit that used to read `clean: False` too; a wrong stamp → `stamps_ok
  False` with the record still decoding clean; a monkeypatched unreadable
  `versions.schema_of` → the verifier still runs, `fallbacks` has exactly
  two sentences (framing: "pinned Revit 2025 framing table"; decode:
  "synthetic schema damage … latest-release schema") and the honest
  consequence (`clean: False` on a 2025 file under the 2026 schema) is
  visible rather than hidden. Autouse fixture asserts the latest-release
  constants are back after every test. Added to `tests/ci_shard.txt`
  (10 → 11 files).

## Evidence

* Matched pair on the instrument itself: the new module against the
  **pre-fix** `manipulate.py` (git stash of the one file) → **7 failed**
  (2025/2024: `unexpected Partitions header`; 2026 only for the missing
  `fallbacks` key); against the fix → **7 passed** (7.3 s).
* After the fix the reproduction table above reads `Level clean ✔`,
  `fallbacks: []` in all nine cells, and `partitions.BLOCK_TAG == 0x0f28`
  after each release's run (no leak).
* Neighbouring suites: `tests/test_manipulate.py tests/test_versions.py
  tests/test_validate_release.py tests/test_frontdoor.py` → 52 passed, 28
  skipped (sample-dependent self-skips; `test_manipulate.py`'s end-to-end
  cases need `samples/rstbasicsampleproject.rvt`, absent in a cloud clone —
  the new module is the fresh-clone coverage for the verifier).
* Outputs written by the recipe (scratch copies of exactly what the tests
  write): `tools/rvt_validate.py edit_2026.rvt edit_2025.rvt edit_2024.rvt`
  → OK 0 errors / 1 warning (the base's own), OK 0/0, OK 0/0. No claim that
  anything "loads" (rule 4); nothing staged for the viewer — read-path
  change only, no output byte changes.
* Cost (warm, median of 3, `verify_manipulated` on the edited 2026 base):
  0.23 s → 0.36 s. The +0.13 s is two schema parses (one inside
  `reading32`'s `schema_of`, one for the decoder) where the old code paid
  ~0 (cached built-in schema). On the plugin surface both parses are
  `schema_cache` hits. Halving it needs `reading32` to accept/yield the
  parsed schema — the `versions/` (hot) follow-up already written down in
  `docs/inbox/validate-release-aware.md` §Findings (a); not done here.
* Gates: see BRANCH STATE.

## Findings / follow-ups (filed as issues, not done here)

* **The bare edit *write* path is still release-blind.** `tools/rvt_edit.py`
  (shipped in the plugin as `skills/tekton-edit/scripts/rvt_edit.py`) calls
  `Document.from_file` + `commit_plans` with no release context; on a 2025
  /2024 input `from_file` raises walker errors and `commit_plans` re-emits
  blocks with the module-level `BLOCK_TAG`/`TRAILER_TAG` from-imports
  (2026) — reproduced here: `commit_plans` inside plain `V.reading(base)`
  on the 2025 base → `ManipulationError: walker errors after re-emit:
  ['unexpected tag 0x0f28 at 18']`. Only `release_build_context` (front
  door / `go`) swaps those. That is the same class of defect as this issue
  on the write side; filed as its own task issue (#70, `Refs #11`) because it
  touches `mutate.py` + the emit helpers + a tool, not the verifier.
* `records32.verify_manipulated32` is now functionally redundant (the core
  verifier binds the own schema, is width-independent for stamps, and picks
  up the swapped `iter_records`/`decode_elemtable`); the patch-table entry
  `(M, "verify_manipulated", verify_manipulated32)` still routes 2023
  callers to it, harmlessly. Retiring it is a `versions/` (hot) edit for
  whoever next holds that directory with a 2023 sample to prove parity —
  noted, not filed separately (it belongs with follow-up (a) above).
* `docs/inbox/genesis-audit.md`'s "LATENT CORE BUG … QUEUED for the
  manipulate territory + a re-verification sweep of any 2024/2025
  manipulate evidence": the core bug is this PR; the sweep half is moot for
  tracked evidence — every 2024/2025 manipulate verdict in the repo was
  taken inside `release_build_context` (front door) or via
  `verify_manipulated32` (genesis-2023 ladder), the two paths shown correct
  in the table above. Owner-machine experiment JSONs were not re-read.

## BRANCH STATE

* Branch `cam/11-verify-own-schema` from `main@af59d26`; PR closes #11.
* Files: `src/rvt/manipulate.py` (verify_manipulated only),
  `tests/test_verify_manipulated_release.py` (new, 7 tests),
  `tests/ci_shard.txt` (+1 line), `docs/inbox/verify-manipulated-schema.md`
  (this), regenerated `plugin/lib/src/rvt/manipulate.py`.
* Gates (final diff): stream-local 7 passed; neighbours 52 passed / 28
  skipped; `tools/sync_plugin.py` synced 1 file, deny-audit clean,
  validation passed, zip rebuilt (not committed); `--check` in sync;
  `plugin/scripts/validate_plugin.py` PASS; `tools/dev/check_portable_paths.py`
  ok; CI shard (`tests/ci_shard.txt`, 11 files, `RVT_SKIP_LARGE=1`) green —
  counts in the PR body.
* Shipped vs staged: everything in the PR; no experiments, no assets, no
  zip, no viewer batch.
