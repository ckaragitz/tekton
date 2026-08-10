# validator-semantic-perf — the semantic layer's record decode, compiled (issue #427)

Stream: `eng427` (engineer session under the tech-lead session; branch
`cam/427-validator-semantic-perf`, cut from `main @ f05db8b`, final head rebased on
`main @ af15f6c`; merged as 1d63c6b). Closes #427; Refs #266
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

---

## eng #449 — 2026-08-10: hooks are overridden by subclassing; an instance-patched hook now takes the walk too (issue #449, from the #447 review)

Stream: `eng449` (engineer session under the tech-lead session; branch
`cam/449-decoder-hook-guard` from `main @ 855f764`). Closes #449; Refs #427 #447.
(The header of this record now says what #447's final head was actually rebased on —
`af15f6c` — as the issue asked; nothing else above this line was touched.)

### What was built

1. **`ObjectDecoder` (`src/rvt/objects.py`, read path only).** The class docstring now
   states the extension contract in full: override the `_HOOKS` methods **by
   subclassing** (detected at class creation, `cls._hooks_native`); an *instance*-assigned
   hook (`dec._decode_pointer = f`) is tolerated the same way — that instance drops to the
   reference walk from then on; re-binding a hook on an already-created *class*
   (`SomeDecoder._decode_pointer = f`, `monkeypatch.setattr(cls, …)`) is the one thing not
   detected — subclass, or force the walk with `use_plans = False`. The detection chosen is
   not a per-call guard in `decode_record` (which #447 measured to the microsecond) but a
   four-line `__setattr__` on the class: assigning any name in `_HOOKS` (now a
   `frozenset`) on an instance
   also sets that instance's `_hooks_native = False`, which `decode_record` already reads
   (`self._hooks_native` — the instance value now shadows the class value). So the plan
   path's entry test is byte-for-byte the #447 one, a patch made *after* plans were
   compiled and used is honoured from the next record on, other instances and the class
   keep the plan path, and nothing in `src/ tools/ plugin/` changes behaviour (nothing
   there instance-patches a decoder; every override is a subclass — `ESDecoder`
   `_hooks_native False`, `ADocumentDecoder` True, `_RefDecoder`/remap decoders False, as
   before).
2. **`src/rvt/encode.py` comment text only** (module codebook + `Writer.bool`): the
   decoder returns a Python `bool` for kind 0x01 on both paths (`Reader.bool`, and the plan
   path's `"?"` struct char — any non-zero byte → True), so a decoded value re-encodes as
   exactly 0/1 and a non-0/1 wire byte would come back as 1; the byte-for-byte round trips
   the module cites met none. The old text ("the decoder returns the raw int for non-0/1
   bytes") described neither main nor #447. No encoder logic touched; no written byte
   changes.
3. **`tests/test_objects_plans.py` 13 → 14**: `test_instance_patched_hook_takes_the_walk_and_sees_every_field`
   — on the first 300 seq-102 records of the 2025 base, a plain decoder whose
   `_decode_value_class` is patched on the instance *before any decode*, and one patched
   *after* 50 plan-path decodes (plans compiled and cached), both: never enter
   `_decode_record_planned` again (spy), return `_same()` objects as the `_RefDecoder`
   *subclass* (== the walk on every record, test 1), and their patch sees exactly the
   `(full path, id)` stream that subclass override sees (element for element, > 500 ids
   over the sample); a third fresh instance and the class itself stay `_hooks_native`.
   The test fails on `main @ 855f764` (the patched hook saw 0 fields), passes here.
   `/simplify` pass folded in: the test's separate reference pre-pass and fourth decoder
   dropped, the bool fact stated once in `encode.py` (docstring) and referenced from
   `Writer.bool`, the class docstring tightened; skipped (outside territory, held by eng
   #430, ≈0.1 ms): binding `dec.ref_sink` once before `_layer_semantic`'s loop instead of
   per record.

### Evidence

- `tests/test_objects_plans.py`: **14 passed** (8.9 s). Without the `__setattr__` (same
  tree, guard renamed away): the new test fails, 13 pass.
- Per-record identity harness (the #447 `ab.py` idea, scratch script over
  `tests/test_objects_plans._records`, all seq-102 records of the three bundled bases,
  this head): 2024: 3,278 records, 2025: 3,316, 2026: 3,102 = **9,696 records; plan vs
  walk 0 mismatches** (values+types, consumed/total, errors, n_deferred, stub, clean,
  `ref_sink`); **instance-patched decoder vs walk 0 mismatches** and its spy's
  `(leaf, id)` stream == the walk's `ref_sink` on every record; `plan_bails` = `{}` /
  `{}` / `{'_Bail': 1}` (the 2026 DataStorage decode-gap record) — the same single bail
  #447 recorded; the patched decoders' `plan_bails` empty (they never tried).
- `validate_file(G_ABPD_2025.rvt)` in-process wall, one warm-up then medians of 11, three
  rounds each, this venv (3.11): **after 146.3 / 136.6 / 141.5 ms; before (guard removed,
  same tree, run alternately) 139.8 / 140.2 / 140.9 ms** — inside the run-to-run spread
  (min 130–135, max 148–165 either way). The added cost is one Python-level `__setattr__`
  per attribute assignment on a decoder: `timeit` 147 ns vs 17 ns per `dec.ref_sink = []`,
  and the semantic layer does exactly one such assignment per record → 3,316 × 130 ns ≈
  **0.43 ms per 2025 validate (0.3 %)**, below what the harness can resolve; `decode_record`
  itself is unchanged.
- Neighbours: `test_objects test_encode test_adocument test_estorage test_validate_release
  test_validate_footer_blob test_bare_family_validate test_records32 test_mutate
  test_manipulate test_roundtrip` + `test_objects_plans`: 126 passed / 71 skipped / 1
  xfailed when `test_manipulate` runs *before* `test_objects_plans`; in the other order
  `test_manipulate` shows 2 failed + 2 errors **on `main` too** — a pre-existing
  first-import-inside-a-release-context bug in `rvt.manipulate` (by-value `BLOCK_TAG`
  copy), root-caused and filed as **#455** (not this territory: `manipulate.py` is held by
  eng #430). The merged shard runs the alphabetical order and is unaffected.

### Findings

- Why `__setattr__` and not the issue's `type(self)._decode_value_class is not
  self._decode_value_class.__func__` once-per-instance probe: "once" needs a place to run
  (first decode) and misses a patch applied after it; per call it costs a bound-method
  construction per hook per record. Flipping the existing flag at assignment time costs
  nothing on the decode path and catches the patch whenever it happens. Direct
  `vars(dec)[...] = f` writes and class re-binding after creation remain undetected by
  design (documented); a metaclass `__setattr__` could catch the latter but nothing does it
  and pytest's `monkeypatch.setattr(ObjectDecoder, "_decode_record_planned", …)` in this
  very test file shows class patching is a test idiom better left alone.
- #455 is a real (loud, non-corrupting) product edge: a process that reads a ≤ 2023 file
  through `reading32` *first* and edits a 2026 project later fails the edit's own re-walk.

### BRANCH STATE

- Branch `cam/449-decoder-hook-guard` from `main @ 855f764`; PR closes #449.
- Files: `src/rvt/objects.py` (class docstring + `__setattr__`, 1 comment word),
  `src/rvt/encode.py` (two comments), `tests/test_objects_plans.py` (+1 test), this record
  (header fact + this section); mirrors `plugin/lib/src/rvt/{objects,encode}.py` via
  `tools/sync_plugin.py`. No new test *file*, so no shard drop-in (the file is already in
  the shard via `tests/ci_shard.d/427-objects-plans.txt`).
- Gates: see the PR body for the final-head counts (stream-local, merged CI shard,
  `sync_plugin --check`, `validate_plugin`, portable paths, `/verify`).
- Nothing staged for the viewer: read path + comments only; no written byte changes.
- Follow-up filed: #455 (`rvt.manipulate` by-value block tags; Refs #449).

---

## eng #464 — 2026-08-10: `ref_sink` bound once, cleared per record; the #459 tax figure corrected (issue #464, from the #459 review)

Stream: `eng464` (engineer session under the tech-lead session; branch
`cam/464-hoist-ref-sink` from `main @ a1927c8`). Closes #464; Refs #449 #459 #447 #427,
#108 / S-2026-08-09-g. Nothing above this line was touched; the correction the issue asks
for is stated here, in this stream's voice.

### Correction to the eng #449 section's "Evidence" (its 4th bullet)

That bullet prices #459's `ObjectDecoder.__setattr__` guard at "3,316 × 130 ns ≈ **0.43 ms
per 2025 validate (0.3 %)**, below what the harness can resolve". Measured, it is **≈ 1.0–1.5
ms per `validate_file(G_ABPD_2025.rvt)` (≈ 1 % of the call, ≈ 1.5 % of the semantic
layer)** — 2–3× the estimate, and resolvable:

- the independent reviewer of PR #459 (sandboxed, `/usr/bin/python3`, 7 alternating rounds
  of medians): wall 158.6 vs 157.6 ms (+0.7 %), semantic layer +1.7 %; a same-interpreter
  paired A/B pinned the whole delta to the one per-record `dec.ref_sink = []` store in
  `_layer_semantic` (≈ +1.0–1.3 ms; with no per-record store the delta is noise);
- this session, same VM class (4 vCPU cloud session), `/usr/bin/python3` 3.11.15, no numpy,
  vendored olefile: `timeit` per op `dec.ref_sink = []` **174–177 ns** through the guard vs
  **21–22 ns** on a plain object (`sink.clear()` 18–19 ns, a bare `[]` 16–17 ns) → the naive
  product is 3,316 × ~155 ns ≈ 0.5 ms, but the *paired decode loop* (below) loses **1.3–1.4
  ms**, i.e. the store costs more in the hot loop than `timeit` of the bare statement shows
  (the extra list allocation/free per record and the guard's frame on a warm loop are not
  free either). The eng #449 whole-`validate_file` rounds (146.3/136.6/141.5 vs
  139.8/140.2/140.9) were too few and too noisy to see it, which is why that section called
  it unresolvable; it is not.

`decode_record` itself is unchanged by #459 — that part of the bullet stands.

### What was built

`src/rvt/validate.py::_layer_semantic` — the decode loop only: the sink is created and bound
to the decoder **once before the loop** (`sink = []; dec.ref_sink = sink`) and emptied in
place per record (`sink.clear()`), instead of `sink = dec.ref_sink = []` per record. Nothing
else in the function moves (#429/#447/#460 intact; `dec.ref_sink = None` after the loop
kept). Safe because the decoder never replaces the list, only appends to it and, when the
plan path bails, truncates it in place (`del sink[mark:]`, objects.py) — so "the ids of this
record" is exactly what the cleared-then-filled list holds when `decode_record` returns, on
success, on a walk fallback, and on the crash-guard `continue` (the next iteration clears
whatever a crashed record left). Mirror `plugin/lib/src/rvt/validate.py` via
`tools/sync_plugin.py`. Not `objects.py`.

### Evidence

**Report identity** — `validate_file(p).to_json()` minus `timings`, `json.dump(indent=1,
sort_keys=True)`, `main @ a1927c8` (a detached worktree, "before") vs this branch ("after"),
both under `/usr/bin/python3` with `PYTHONPATH=<tree>/src:plugin/skills/_shared/_vendor`:

```
$ diff -r rep_before/ rep_after/ ; echo "exit=$? lines=$(diff -r rep_before rep_after | wc -l)"
exit=0 lines=0
```

| file | diff lines | errors / warnings (both) | refs_checked (both) |
|---|---|---|---|
| `G_ABPD.rvt` (2026 base) | **0** | 0 / 1 (the DataStorage decode-gap record) | 45872 |
| `G_ABPD_2025.rvt` | **0** | 0 / 0 | 50759 |
| `G_ABPD_2024.rvt` | **0** | 0 / 0 | 40579 |
| set-level edit of the 2025 base (`set_level_elevation(1351691, 1.25)` + `commit_plans` in the base's release context) | **0** | 0 / 0 | 50759 |
| dangling copy of the 2025 base (`DBViewPlan.m_assocLevelId` → 987654321) | **0** | 1 / 0 — `1 dangling ElementId reference(s) … (by field: m_assocLevelId x1). e.g. element 245443 DBViewPlan.m_assocLevelId=987654321` | 50759 |

**Timing** — `/usr/bin/python3` 3.11.15, no numpy, vendored olefile, this 4-vCPU cloud VM,
nothing else running. Two instruments:

1. *Same-interpreter paired A/B of exactly the changed lines* (`micro.py`: the layer's decode
   loop over all 3,316 seq-102 records of the 2025 base in the two spellings, one warmed
   decoder each, alternating): **100 reps: re-bind median 65.87 ms (min 63.96) → clear
   median 64.43 ms (min 62.63) = −1.44 ms median, −1.33 ms min; clear faster in 83/100
   pairs** (a first 40-rep run: −1.87 median / −0.79 min, 27/40).
2. *Whole `validate_file(G_ABPD_2025.rvt)`, before/after in separate processes, ALTERNATING
   which goes first, one warm-up then 12 iterations per process* (`ab.py`):

   | run | metric | before median (min) | after median (min) | Δ median | rounds after < before |
   |---|---|---|---|---|---|
   | 20 rounds × 12 = 240/240 samples | `validate_file` | 161.61 (153.33) | **159.17 (147.96)** | **−2.44 ms (−1.5 %)** | 15/20 (median round-delta −2.19) |
   | | semantic layer | 102.38 (97.53) | **100.67 (94.54)** | **−1.72 ms (−1.7 %)** | 17/20 (median round-delta −2.65) |
   | 10 rounds × 12 = 120/120 (first run) | `validate_file` | 161.09 (154.41) | 161.31 (151.84) | +0.22 ms | 6/10 (median round-delta −1.28) |
   | | semantic layer | 102.37 (99.01) | 101.96 (95.50) | −0.41 ms | 7/10 (median round-delta −1.16) |

   Honest reading: the effect (≈ 1–1.5 ms) is the size of this VM's run-to-run spread
   (rounds jump 155 → 190 ms when the host hiccups), so a 10-round whole-call run does not
   resolve it in the pooled median (only in the per-round pairing); 20 rounds do, and the
   paired loop measurement — the one that varies nothing but the two lines — is unambiguous.
   Net: **≈ −1.4 ms per 2025 `validate_file`, the semantic layer back to its pre-#459 cost;
   the guard now costs the validator two attribute stores per file instead of 3,317.**

- Tests: `tests/test_objects_plans.py tests/test_gates_shared_walk.py
  tests/test_validate_release.py` **33 passed**; with neighbours `test_validate_footer_blob
  test_bare_family_validate test_objects`: 85 passed / 10 skipped (corpus / `RVT_SKIP_LARGE`).
- `tools/sync_plugin.py` synced 1 file, deny-audit clean, validation passed; `--check`: in
  sync; `plugin/scripts/validate_plugin.py` PASS (25 assertions); `check_portable_paths` ok
  (2908).

### Findings

- The remaining per-record Python work in the loop is now the dict iteration, the limit
  test, `sink.clear()`, the `decode_record` call and the post-decode bookkeeping; the sink
  handling is at the floor (one C-level method call). No further lever here without touching
  `objects.py`.
- General note for whoever adds state to a decoder inside a hot loop: since #459 every
  instance attribute store on an `ObjectDecoder` (any name, not just the hooks) pays the
  Python-level `__setattr__`; bind once outside the loop and mutate in place.
- `/simplify` (four angles): reuse / efficiency / altitude — no findings (`sink.clear()`
  measured cheapest correct reset: 70 ns vs `del s[:]` 89, `s[:] = ()` 99, the guarded store
  222 in the venv; the in-place idiom is the decoder's own — `del sink[mark:]`); simplification
  — the first draft's 3-line block comment folded into trailing comments (applied).

### Open follow-up (out of territory — `objects.py` is not this stream's; patch offered, not applied)

`src/rvt/objects.py` still *advertises* the per-record re-bind this change removed: the module
docstring example (line ~60, `dec.ref_sink = []  # optional: …`) and the attribute comment
(~343–345, "callers reset it per record"). Neither says that, since #459, an attribute store on a
decoder runs the Python-level `__setattr__`. Suggested wording for whoever next holds
`objects.py` (Refs #464): docstring example → `dec.ref_sink = sink = []  # bind once; sink.clear()
per record (re-binding runs __setattr__)`; attribute comment → "callers bind one list and clear it
in place per record (rvt.validate); re-binding per record goes through `__setattr__`". Cost of not
doing it: the next `ref_sink` consumer copies the docstring pattern and re-pays ≈ 1.4 ms/file.
Comment-only, so not filed as its own issue; fold into the next `objects.py` PR.

### BRANCH STATE

- Branch `cam/464-hoist-ref-sink` from `main @ a1927c8`; PR closes #464.
- Files: `src/rvt/validate.py` (`_layer_semantic` decode loop: +4/−1 lines), its mirror
  `plugin/lib/src/rvt/validate.py` (via `tools/sync_plugin.py`), this record (this section
  only). No new test file → no shard drop-in (behaviour is identity-pinned by
  `tests/test_objects_plans.py`, already in the shard).
- Gates: see above + the PR body for the merged-shard count and `/verify`.
- Nothing staged for the viewer: read path only; no written byte changes.
