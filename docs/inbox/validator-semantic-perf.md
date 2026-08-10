# validator-semantic-perf — the semantic layer's record decode, compiled (issue #427)

Stream: `eng427` (engineer session under the tech-lead session; branch
`cam/427-validator-semantic-perf` from `main @ f05db8b`). Closes #427; Refs #266
(whose measurement located the time here), #110, #108 / S-2026-08-09-g.

## 1. What was built

1. **`rvt.objects.ObjectDecoder` gets a compiled read path** (`src/rvt/objects.py`,
   READ path only — no encoder, no written byte touched). `decode_record` now runs a
   per-class *plan*, compiled once per class id from exactly `self.chain()` (parent-first)
   and cached on the decoder:
   - the chain's dict keys are precomputed (`field_key`'s shadowing rule is static per
     chain), so no per-record `field_key` calls and no per-field path f-strings;
   - every run of consecutive **fixed-size** fields (bool/char/short/int/uint/float/
     double/int64, `ElementId`/`Identifier`, `XYZ`, `UV`, `GUID`/`GUIDvalue`, weak
     pointers, class refs, schema-count fixed arrays of primitives/ids) is fused into
     **one `struct.Struct`** with one slot per key → `out.update(zip(keys, vals))`, plus a
     short fix-up tuple for the slots that arrive packed (`24s` → `[x, y, z]`, `16s` →
     GUID string, fixed arrays) or must be reported (ElementIds);
   - variable-size fields (AString, containers, pointers, nested value classes, `0x0D`
     inline arrays) are small op tuples mirroring `_decode_field` / `_decode_scalar`
     one-for-one; containers of primitives/ids read with one memoized `Struct` per
     (item, count);
   - **every check the reference walk makes is made too** (truncation via `struct.error`,
     `count32`'s exact plausibility cap, the AString length bound, unknown pointer class,
     `MAX_DEPTH`), as an exception — and `decode_record` answers *any* exception from the
     plan path by re-decoding the record from byte 0 with the untouched field-by-field
     **reference walk** (`_decode_record_walked` = the old body of `decode_record`,
     verbatim), which stays the one and only error reporter. So a record either decodes to
     the very same `DecodedObject` (values *and* their Python types, `consumed`, `clean`,
     `stub`, `n_deferred`) or is reported by the code that always reported it;
   - the walk's hook methods (`_decode_class/_field/_scalar/_value_class/_pointer` and
     `class_name`) are now the *documented* extension API (`_HOOKS`, class docstring):
     a subclass overriding any of them (`ADocumentDecoder`, `ESDecoder`,
     `rfa_load._Remap`, the tools' remap/tag decoders) is detected once per class
     (`__init_subclass__` → `cls._hooks_native`) and **always** takes the reference
     walk, so every override sees every field exactly as before, at the speed it had;
     `ObjectDecoder.use_plans = False` forces the walk for A/B checks;
   - the **32-bit-id era** (`rvt.versions.records32`, Revit ≤ 2023) swaps
     `Reader.element_id` process-globally; plans assume the 64-bit read, so while that
     patch is in force every record takes the walk — through the patched method, exactly
     as before plans existed (found by the review pass; test added);
   - `dec.plan_bails` counts, by exception type, the records the plan path handed back
     (`python -m rvt.objects` prints it); anything but `_Bail`/`struct.error` there is a
     plan bug, and the new test asserts exactly that on the bundled bases;
   - new optional **`dec.ref_sink: list`** — when set, every ElementId-typed value read
     is appended as `(field name, id)` in field order (schema-typed, both paths; an
     inline array's anonymous element reports as its wrapper field, = the leaf of the
     walk's path, `objects.leaf_name`). This is what the validator needs from a record,
     without a hook override and without path strings; with no sink the id-only
     fix-ups are not even visited.
   `Reader.guid` and the plan path share one `_fmt_guid`/`_S_GUID`; both record paths
   share one `_is_stub`; `_fixed_slot` (which fields fuse) is *derived* from
   `_compile_elem` so the flattened-value-class ladder exists once in the compiler.
2. **`rvt.validate._layer_semantic`** decodes through the plain decoder + `ref_sink`
   instead of the `_RefDecoder` hook subclass: `refs_checked` = ids read; typed
   symbol/level checks classify by field name (`_typed_need`); dangling ids are
   detected inline against the (already complete) id universe, and **only the owners
   that hold one are re-read with `_RefDecoder`** (kept, lazily built) so the ERROR
   message names each dangling id by its exact full field path, in the same owner order
   and field order as before — zero re-reads on a healthy file, one per damaged owner
   otherwise. `_check_loaded_content` lost its dead `dec.refs = []`. `WalkedFile` /
   #429 untouched (rebased on, intact).
3. **`tests/test_objects_plans.py`** (NEW, 13 tests, ~9 s, fresh-clone safe: bundled
   bases + `tmp_path`; in the shard via `tests/ci_shard.d/427-objects-plans.txt`): on
   **every seq-102 record of the three bundled bases** (9,696 records) plan path ==
   reference walk == the validator's path-recording `_RefDecoder` on all `DecodedObject`
   fields and `repr(value)` (types, key order, NaN-safe), and `ref_sink` == the walk's
   == the leaf of the override's full paths; bails ≤ 2, == the walk-faulted records, and
   only of the two legitimate types; a hook (or `class_name`) override never enters the
   plan path (spy); the `ids32()` era never enters it and reads identically to the walk;
   the flattened value classes never compile as nested classes; >2,000 truncation
   depths + smashed/zeroed/over-long/shifted payloads + an unknown root class report
   identical error dicts; a bailing record leaves no half-read ids in the sink; the
   AString codec shortcut == `Reader.astring` on lone surrogates/BOM/empty/null;
   `validate_file(...).to_json()` minus timings is identical with `use_plans`
   False/True on the three bases and on a synthesized dangling-`m_assocLevelId` copy
   whose message keeps `element <id> DBViewPlan.m_assocLevelId=987654321`.

Candidate cuts from the issue, each single-variable against the byte-identical report:

| candidate | verdict |
|---|---|
| per-class decode plans cached on the decoder | **kept** — the bulk of the win (decode-all 184 → 75 ms) |
| `struct.Struct` instances instead of format-string `unpack_from` | **kept**, folded into the plans (fused runs; per-item Structs; memoized n-item Structs) |
| skip building values the validator never reads / no path strings through `_RefDecoder` | **kept in its honest form**: no path strings at all on the plan path (`ref_sink` names), exact paths re-derived only for dangling owners; values are still built (they are `clean`'s definition and feed the connector/circuit/family checks) |
| skip seq-102 records of classes with no ElementId-typed field | **rejected**: `clean` (= all bytes consumed, no error) needs the full read of every record and is what the decode-failure WARNING counts; with the plan path a no-id record costs ~10 µs, so there is nothing left to buy |
| one dispatch less per single-element field + pointer-first element dispatch | kept (75 → 67 ms) |
| one slot per key in fused runs (packed `Ns` members + fix-ups) instead of a two-mode spread | kept — same speed, one insertion path |
| review pass: `codecs.utf_16_le_decode` shortcut in `_astring` (no per-call codec-registry lookup); a sink-less fix-up tuple per run so callers without a sink skip id-only visits; `max()` out of `_count32` | kept (decode-all, no sink: 67 → 60 ms) |
| `_iter_seg_records` with `slots`/`Struct` objects | rejected: 8.2 → 7.7 ms over all three layers, not worth touching a shared helper |
| reuse one `_Cx`/deque per decoder; unpack steps in the `for` | rejected: at the noise floor (±3 %), pins the last payload on the instance |

## 2. Evidence

Host: this cloud VM (4 vCPU), `/usr/bin/python3` 3.11.15 **without numpy or olefile**
(`PYTHONPATH=src:plugin/skills/_shared/_vendor`, i.e. the interpreter and the vendored
olefile a bare surface has); the venv reads the same ±5 %.

**Report identity — `validate_file(p).to_json()` minus `timings`, `json.dump(indent=1,
sort_keys=True)`, main's decoder ("before") vs this branch ("after"), `diff | wc -l`:**

| file | diff lines | errors / warnings (both) | notable finding kept verbatim |
|---|---|---|---|
| `G_ABPD.rvt` (2026 base) | **0** | 0 / 1 | `1/3102 seq-102 records failed schema decode (DataStorage x1)` — the one record the plan path declines, reported by the walk as ever |
| `G_ABPD_2025.rvt` | **0** | 0 / 0 | — |
| `G_ABPD_2024.rvt` | **0** | 0 / 0 | — |
| set-level edit of each base (level 1351691 +1.25 ft, `manipulate` + `commit_plans` in the base's release context) ×3 | **0 / 0 / 0** | 0 / 1, 0 / 0, 0 / 0 | — |
| hard-damaged copy of the 2025 edit (64 payload bytes destroyed in the partition's first block) | **0** | 3 / 1 | ECC beyond envelope; `1/15 block gzip member(s) fail CRC32/ISIZE`; A/C identity; `save unit 0: the three seqs carry different id sets (101^102 differ by 913 …)` |
| semantic damage 1: `DBViewPlan.m_assocLevelId` → a non-existent id | **0** | 1 / 0 | `1 dangling ElementId reference(s) … (by field: m_assocLevelId x1). e.g. element 245443 DBViewPlan.m_assocLevelId=987654321` (exact path, via the one-owner re-read) |
| semantic damage 2: `m_assocLevelId` → an existing non-Level element | **0** | 1 / 0 | `1 level id(s) resolve to non-Level elements. e.g. element 245443 m_assocLevelId=1064656 (DBViewPlan)` |

Stats identical everywhere (`elements_decoded` 3102/3316/3278, `refs_checked`
45872/50759/40579, `decode_failures`, `connector_edges`, `circuits`).
Plan path vs reference walk per record (the new test, and `ab.py` over all nine files,
26,024 records): 0 mismatches; records declined by the plan path: 1 (the 2026
DataStorage decode-gap record) — i.e. the fallback is not doing the work.

**cProfile, `validate_file(G_ABPD_2025.rvt)`, top self-time (same interpreter; profiler
overhead inflates absolute numbers ~1.5×):**

| # | before (2.02 M calls, 1.12 s profiled) | after (0.68 M calls, 0.46 s profiled) |
|---|---|---|
| 1 | `objects._decode_class` 0.163 s (21,569 calls) | `objects._run_plan` 0.073 s (21,569) |
| 2 | `objects.Reader._unpack` 0.111 s (160,054) | `objects._x_elem` 0.038 s (53,768) |
| 3 | `objects._decode_field` 0.101 s (139,864) | `validate._iter_seg_records` 0.038 s (26,544 — all three layers) |
| 4 | `objects._decode_scalar` 0.084 s (141,728) | `validate._layer_semantic` (own loop) 0.027 s |
| 5 | `validate._layer_semantic` (own loop) 0.079 s | `objects._fixup` 0.020 s (15,057) |
| — | `struct.unpack_from` 0.054 s (241,871); `_RefDecoder._decode_value_class` 0.051 s (62,746); `field_key` 0.028 s (139,489) | `Struct.unpack_from` 0.017 s (84,724) + `struct.unpack_from` 0.014 s (81,305); `_astring` 0.013 s |

**In-process wall, medians of 12 `validate_file` iterations after one warm-up (ms):**

| file | semantic before → after | validate_file total before → after | L1 / L2 (unchanged) |
|---|---|---|---|
| `G_ABPD_2025.rvt` | **270.4 → 101.4 (−62 %)** (min 260.5 → 95.8) | 315.4 → 148.5 (−53 %) | 28 / 16 |
| `G_ABPD.rvt` (2026) | 219.8 → 84.4 (−62 %) | 263.8 → 125.3 | 26 / 15 |
| `G_ABPD_2024.rvt` | 260.0 → 95.6 (−63 %) | 303.8 → 136.8 | 27 / 15 |
| edit of 2025 base | 253.9 → 96.6 | 298.2 → 138.4 | 27 / 15 |
| edit of 2026 / 2024 base | 215.8 → 82.7 / 241.3 → 96.7 | 258.9 → 122.8 / 284.7 → 138.5 | |
| hard-damaged / dangling / mistyped copies | 247.6 → 95.7 / 262.5 → 98.3 / 259.6 → 97.4 | 289.0 → 135.9 / 308.2 → 139.8 / 307.1 → 138.9 | |

Pieces of the 2025 layer (`micro.py`, medians of 9): index pass 7 ms (unchanged); decode
of all 3,316 records **184 → 67 ms** (the old `_RefDecoder` hook subclass: 203 ms);
everything after the decode loop ~25 ms (unchanged: sink loop ≈ 6, connectors, loaded
content, four registries). The issue asked for ≥ 30 % / ≥ 120 ms off `validate_file` on
its (slower) reference machine; here the layer loses 62 % and `validate_file` 167 ms of
315.

*Final head (after the review pass), same harness, same nine files:* semantic medians
86.0 / **98.3** / 95.7 ms (2026 / 2025 / 2024 bases), 86.5 / 96.4 / 96.5 (edits), 96.1 /
96.5 / 95.0 (damaged copies); `validate_file` on the 2025 base 141.2 ms; decode-all 60 ms
(no sink) — and **0 diff lines** against main's nine reports again. Profile top-5 at the
final head: `_run_plan` 0.068 s, `_iter_seg_records` 0.037, `_x_elem` 0.035,
`_layer_semantic` own loop 0.029, `_fixup` 0.019 (0.67 M calls, 0.43 s profiled).

**Bare unzip, `tools/surface_bench.py --zip before.zip|after.zip --surfaces
cowork,codeexec --jobs go-edit,author-prompt,validate,go-author-prompt --python-bare
/usr/bin/python3`, before/after ALTERNATING, 5 runs each** (`before.zip` built by
`tools/sync_plugin.py` in a worktree of `main @ f05db8b`, `after.zip` from this branch;
wall = whole shell call incl. interpreter start; in-call = the job's own clock; `edit` /
`validation` = `go edit`'s breakdown; medians (min)):

| surface | job | before: wall med (min) · in-call · edit · validation, s | after: wall med (min) · in-call · edit · validation, s | Δ wall (med) | status |
|---|---|---|---|---|---|
| cowork | **go-edit** | 1.031 (1.011) · 0.864 · 0.514 · 0.300 | **0.863** (0.847) · 0.700 · 0.346 · 0.100 | **−168 ms (−16 %)** | PASS/PASS |
| codeexec (fresh extract per call) | **go-edit** | 1.001 (0.986) · 0.844 · 0.520 · 0.300 | **0.813** (0.809) · 0.658 · 0.335 · 0.100 | **−188 ms (−19 %)** | PASS/PASS |
| cowork | **validate** (`run rvt_validate.py` on the authored .rvt) | 0.533 (0.529) | **0.370** (0.364) | **−163 ms (−31 %)** | PASS/PASS |
| codeexec | **validate** | 0.722 (0.707) | **0.574** (0.563) | −148 ms (−20 %) | PASS/PASS |
| cowork | author-prompt | 2.123 (2.112) | 1.956 (1.936) | −167 ms (−8 %) | PASS/PASS |
| codeexec | author-prompt | 2.399 (2.327) | 2.197 (2.171) | −202 ms | PASS/PASS |
| cowork | go-author-prompt | 1.917 (1.887) · in-call 1.814 | 1.745 (1.698) · 1.640 | −172 ms (−9 %) | PASS/PASS |
| codeexec | go-author-prompt | 2.400 (2.350) · 2.264 | 2.223 (2.175) · 2.095 | −177 ms | PASS/PASS |

Individual runs (s) — `go-edit` cowork before 1.04 1.01 1.03 1.03 1.04, after 0.86 0.87
0.85 0.86 0.90; codeexec before 1.02 1.00 0.99 0.99 1.06, after 0.91 0.81 0.81 0.86 0.81;
`validate` cowork before 0.53 0.53 0.53 0.53 0.55, after 0.36 0.40 0.37 0.37 0.38;
codeexec before 0.72 0.72 0.71 0.75 0.73, after 0.57 0.57 0.56 0.62 0.59; `author-prompt`
cowork before 2.13 2.14 2.11 2.12 2.12, after 1.94 1.97 1.96 1.98 1.94. On the two jobs
this issue targets **every after-run is faster than every before-run**; the validation
gate inside `go edit` (rounded to 0.1 s by `rvt_edit.py`) reads 0.3 → 0.1 s.

`rvt.mutate.Document` decodes through the same plain decoder, so the *edit* half of `go
edit` (0.51 → 0.35 s in-call) and the create routes' gates got cheaper too — not only the
validation gate this issue targeted; that is where `author-prompt`'s −170..200 ms comes
from.

## 3. Findings

- #266's diagnosis holds exactly: the semantic layer *was* the interpretive per-field
  walk (`_decode_class → _decode_field → _decode_scalar → _unpack`, ~1.3 µs/field ×
  140 k fields) plus 140 k path f-strings nobody read on a healthy file. Fusing fixed
  runs takes the field count out of the Python loop; the remaining Python-level work is
  per variable-size field (pointers 31 k, strings 11 k, containers 11 k, nested classes
  11 k per 2025 base).
- What is left in the layer (~100 ms on the 2025 base): decode 67 (of which pointer
  tokens + deferred bodies dominate), record index 7, post-decode checks 25. The next
  lever, if ever wanted, is absorbing single-run nested value classes into the parent run
  (6.3 k of the 10.7 k nested-class reads are one fused run) — skipped here because it
  needs static depth bookkeeping to keep the `MAX_DEPTH` bail exact and buys < 10 ms.
- The plan path is a strict *superset raiser*: it may decline records the walk would
  have decoded (costing time, never correctness), and must never accept one the walk
  faults — the truncation/corruption tests pin the second property; the "declined ≤ 2 of
  9,696" assertion watches the first.

## 4. Open questions / follow-ups (from the review pass; noted, not filed — none is user-facing today)

- **A first-class `id_map` primitive on the decoder** would retire the five
  near-identical `_decode_value_class` *remap* subclasses (`convert/rfa_load._Remap` —
  the extract→place lane — `tools/rft_probe.py`, `union_reconcile.py`,
  `selfcontained.py`; `birthright_mine.py` only observes and could use `ref_sink` now)
  and put them on the plan path. Worth an issue the day extract→place latency matters.
- `Reader` is no longer the *only* place the read laws live: `_count32`/`_astring` mirror
  `Reader.count32`/`astring` on the plan cursor (kept separate for call overhead; the
  A/B tests are the guard). A later cleanup could hoist the two laws (plausibility cap,
  AString bound) into shared module constants/predicates.
- The walk derives a sink entry's field name from its display path (`leaf_name`); a
  structural `state.leaf` would decouple it from path formatting. Test-guarded today.
- 32-bit era: plans are simply off there (walk speed, as before). Era-aware plans (id
  struct char threaded through the compiler) are possible if the 2023 lane ever needs
  the speed.

## BRANCH STATE

- Branch `cam/427-validator-semantic-perf` from `main @ f05db8b`; PR #447 closes #427.
- Files: `src/rvt/objects.py` (compiled plan path, `ref_sink`, `plan_bails`, `leaf_name`;
  reference walk kept as `_decode_record_walked` — only its stub line and GUID/`{1,2}`
  spellings now go through the shared helpers), `src/rvt/validate.py` (`_layer_semantic`
  on `ref_sink`, one-owner path re-read, `_typed_need`; `_check_loaded_content` dead
  line), `tests/test_objects_plans.py` (new), `tests/ci_shard.d/427-objects-plans.txt`
  (new), this record; mirrors `plugin/lib/src/rvt/{objects,validate}.py` via
  `tools/sync_plugin.py`.
- Gates (final head): `tests/test_objects_plans.py` 13 passed; stream-local
  (`test_objects_plans test_validate_release test_validate_footer_blob
  test_bare_family_validate test_gates_shared_walk test_objects test_encode test_adocument
  test_estorage test_plugin_sync`) 96 passed / 42 skipped (sample-gated); regression net
  (`famgen_factory/loader/adoc/catalog, famload/_2025/_fix/_batch, manipulate, mutate,
  convert, convert_combo, roundtrip, verify_manipulated_release, stream_encoders,
  genesis2_adocument, records32`) 190 passed / 186 skipped / 1 xfailed; whole merged CI
  shard (`pytest -q $(python3 tools/dev/shard_list.py --print)`, `RVT_SKIP_LARGE=1`): **1507 passed, 134 skipped, 3 xfailed, 0 failed** (4 m 37 s); 2023-era `test_genesis_2023 test_port2023` 16 passed / 41 skipped; `tools/sync_plugin.py` run + `--check` clean;
  `plugin/scripts/validate_plugin.py` PASS; `check_portable_paths` ok (2900).
- `/verify` (final head): `rvt_validate --quiet` on the three bases OK errors=0 (0.2/0.2/0.1 s);
  64 KB-truncated 2025 base FAIL errors=11 exit 1, no traceback; non-CFB junk FAIL 1 container
  error exit 1; the dangling copy prints `element 245443 DBViewPlan.m_assocLevelId=987654321`;
  `frontdoor.py author --rvt G_ABPD_2025.rvt --edit "set level 1351691 elevation to 5 ft"` →
  delivered, `PROOF-ONLY, NOT-DELIVERABLE (hard gates PASSED)`, edited file validates 0 errors
  (refs_checked 50759); bare unzip of `tekton-plugin.zip`, `env -i` `/usr/bin/python3`
  `_bootstrap.py go edit assets/genesis/G_ABPD_2025.rvt set-level --id 1351691 --elevation-ft 5.0`
  → ok, in-call 0.33 s, structural PASS, validation PASS (0 errors, 0 warnings) in 0.1 s.
- Nothing staged for the viewer (read path only; no written byte changes — pinned by the
  roundtrip/encode/manipulate suites and by the byte-identical edit outputs' reports).
