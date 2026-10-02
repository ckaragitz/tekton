# #932: the 6-panel prompt job back under its ceiling, output bytes identical

**Why:** on main `9cdb82d`, `tests/test_surface_perf.py::test_bare_go_author_6panels_under_ceiling`
failed on this container. The run took 9.45 s against an 8.0 s ceiling, and `job_seconds` was
9.27 s. #931, which drove the panelboard through drive_law, added about 1.2 s to the 6-panel
flow, and this container is about 1.4x slower than the last one. Per steer S-2026-08-09-g,
latency counts as done only with a measured before/after from a bare surface. The ceiling
was not touched.

## What was measured (profile of the 6-panel flow, main `9cdb82d`)

We timed it in-process with wall-clock timers on named functions (no profiler overhead).
Total: 9.2 s.

| Function | Calls | Wall |
|---|---|---|
| `stage_families` | 1 | 3.6 s |
| `stage_load_batched` | 1 | 3.5 s |
| `partition_payloads` (record encode) | 30 | 2.1 s |
| `build_product` / `make_panelboard` | 12 | 1.9 s |
| `validate_file` | 14 | 1.3 s |
| `_author_load` | 6 | 1.1 s |
| `emit_family_rfa_v2` | 6 | 1.05 s |
| `verify_loaded_projects` | 1 | 0.9 s |
| `provenance_scan_v2` | 6 | 0.84 s |
| `finalize` | 12 | 0.83 s |

A GC callback found the largest single line of all: the cyclic collector. On the
partially optimised branch it ran 12 full (gen-2) collections costing 0.84–0.97 s of a
~6.6 s job. Those passes re-walked the long-lived decoded trees and caches and found
almost no garbage.

## What changed (each change gives the same answer more cheaply)

1. **Encoder** (`encode.py`, `estorage.py`):
   - Per-class field plans. Shadowed-name keying is resolved once per class, not once per
     object.
   - Single-value fields (primitives, bools, ids, XYZ, weak pointers, primitive arrays) are
     packed directly. Any failure re-runs the general path from a clean buffer.
   - Field paths are built lazily as tuples and rendered only in an `EncodeError`
     (`path_str`).
2. **Record cache** (`famgen/skeleton.py`): `build_unit_segments(cache=)` is a per-document
   cache keyed on each record's exact pickled content. The GUID seal, the standalone emit
   and the embedded unit re-encode only the records that changed. The cache restarts when
   the encoder changes.
3. **pid self-check** (`famgen/geometry.py`): `_assert_pid_stable` is now a read-only twin
   of `assign_pids` (same traversal, same rule), with no deepcopy. The copy form is kept as
   the test reference.
4. **Shared decoder plans** (`objects.py`): decoder plans are shared by every decoder of the
   same `Schema` object (weak-keyed).
5. **`decode_memo()` scope** (`objects.py`, new): inside the scope, a plain
   `ObjectDecoder` decodes each distinct (schema, switches, class, payload) once. A hit
   replays the `ref_sink` entries and `plan_bails` of the first decode. The scope is opened
   only around read-only consumers:
   - the validator's two runs plus the provenance scan in `standalone_family_write`;
   - `verify_loaded_projects`.
6. **Container** (`container.py`):
   - `members()` keeps the payloads it has to inflate anyway, and `inflate` / `inflate_all`
     serve them. Before, every stream was inflated twice per open.
   - `_inflate_at` reads the tail through a `memoryview` instead of copying it.
7. **`iter_records`** (`objects.py`): uses precompiled `Struct`s, and the payload is sliced
   once.
8. **Donor caches** (`famgen/famdoc_adoc.py`):
   - `donor_element_ids` is cached per donor file, keyed on (abspath, mtime_ns, size), and
     returns a fresh list on each call.
   - The donor-window index of `_longest_common_run` is cached the same way.
9. **Loader `_dc`** (`famgen/loader.py`): a pickle round-trip, which is the same deep copy
   with sharing kept. It falls back to deepcopy.
10. **`gcpolicy.build_gc()`** (new `src/rvt/gcpolicy.py`): GC thresholds
    (50 000, 20, 100) for one job, restored when the outermost scope exits. It wraps
    `frontdoor.run` and `router.route`. Collection still runs; only its pacing changes, and
    the collector never decides what is written.

Changes 1–4 and 9 came from the killed earlier attempt. I reviewed each against the general
path it replaces and kept all of them. The equivalence tests in
`tests/test_build_latency_932.py` pin them. Changes 5–8 and 10 are new in this pass. All
changes are general (encoder, decoder, container, every `standalone_family_write`, every
front-door/router job), so #933's transformer, fan coil and device drives benefit too.

## Evidence

**(a) Byte identity, base `9cdb82d` vs this branch:**
- 44 family files are sha256-identical, 22 on 2026 and 22 on 2025 (each built and written
  inside `release_build_context`):
  - panelboard: law default, flush, types, 600A, `solid=False`, `drive="372"`,
    `drive=None`;
  - the 7 archetypes;
  - trapeze at 1, 2 and 3 tiers;
  - LCP, troffer, transformer, device;
  - switchboard (`ifc.intent.make_house_switchboard`);
  - generic box with `drive=True`.
- Every write's report JSON is identical except its `seconds` field.
- The 6-panel `author --prompt` output is byte-identical on both `--target-version 2026`
  and `2025`: `prompt_room.rvt`, the three stage `.rvt`s and the six `.rfa`s.
  - 2026: `prompt_room.rvt` = `a9d0d665464ae001…`
  - 2025: `prompt_room.rvt` = `102a9df858ed18d2…`
  - The outputs carry no timestamps or paths.
- Every text file (`build.log`, `intent.json`, `HANDOFF.md`, families' JSON,
  `stage_L .load.json`) is identical. The exceptions are `manifest.json` / `MANIFEST.md`,
  which differ only in `generated_at` and timing fields.

**(b) Gates:**
- **Targeted pytest batch: 642 passed / 69 skipped / 1 xfailed / 0 failed.** It covered:
  - `build_latency_932` (19);
  - `panel_drive_law_914`, `panel_drives_914`, `drive_law_904`, `drive_follow_904`,
    `height_law_787`, `archetype_drives_913`, `diameter_916`, `lock_column_915`;
  - `constraint_law` and `constraint_law_910`, `family_anatomy_837`;
  - `famgen_loader` and `famgen_loader_release_700`;
  - `famload`, `famload_2025`, `famload_batch`, `famload_determinism_794`, `famload_fix`;
  - `conftest_scaffolding`, `plugin_sync`, `bootstrap`, `coldstart` and
    `coldstart_locale_210`;
  - `encode`, `objects`, `objects_plans`, `roundtrip`, `frontdoor_standalone`, `router`,
    `validate_release`.
- **`tests/test_surface_perf.py` run alone: 8 passed, including
  `test_bare_go_author_6panels_under_ceiling`.**
- `tools/sync_plugin.py`: rebuilt. `--check`: in sync (deny-audit clean).
- `plugin/scripts/validate_plugin.py`: PASS (25).
- `check_portable_paths`: ok.

**(c) `tools/surface_bench.py`, base vs head, interleaved, 3 runs each, medians.** Each tree
ran its own bench and zip with bare python `/usr/bin/python3`. Values are wall / `job_seconds`.

| Surface | Job | Base `9cdb82d` | Head |
|---|---|---|---|
| local | go-author-6panels | 9.37 / 9.21 s | **6.04 / 5.82 s** |
| local | go-author-prompt | 3.05 / 2.88 s | 2.35 / 2.14 s |
| cowork (the test's surface) | go-author-6panels | 10.54 / 10.32 s | **6.82 / 6.55 s** |
| cowork | go-author-prompt | 3.20 / 3.01 s | 2.38 / 2.18 s |

The bare `go` was also run directly from an unzip (`env -i`, `/usr/bin/python3`), 3 runs
interleaved: `job_seconds` was 9.05–9.24 on base and 5.69–6.00 on head.

**Instrument note:** `surface_bench --surfaces local` ignores `--zip`. It runs the bench's
own repo `plugin/` tree. A local base-vs-head comparison is valid only when each tree runs
its own `tools/surface_bench.py`, which is what the table above does. An earlier
single-bench local comparison measured head twice and is void.

## Open

- Each panel family is still built twice: once standalone at id 1000 and once for the
  loader at the host watermark. Re-iding one build is not obviously byte-safe, so it was
  not attempted.
- `provenance_ours` decodes our unit records once per load pass, and the final
  `validate_rvt` decodes the whole project again outside any memo scope, because a mutating
  stage runs in between.
- The ADocument walk decoder (`decode_latest`) is not on the compiled-plan path. The edited
  project ADocument is decoded 4× per job (~0.06 s each).

## BRANCH STATE

- Branch `latency-932` (worktree `.claude/worktrees/agent-af6b40be23d0a41ea`), on main
  `9cdb82d`. It must land before #933.
- **Files:**
  - `src/rvt/{container,encode,estorage,objects,gcpolicy}.py`
  - `src/rvt/famgen/{famdoc_adoc,geometry,loader,skeleton}.py`
  - `src/rvt/frontdoor/{__init__,router,standalone}.py`
  - the `plugin/lib` mirrors
  - `tests/test_build_latency_932.py` and `tests/ci_shard.d/932-build-latency.txt`
  - this record
- **Gates:** as above.
- **Shipped vs staged:** latency only. No output byte changes, nothing staged for the
  viewer, no claims about Revit behaviour.
