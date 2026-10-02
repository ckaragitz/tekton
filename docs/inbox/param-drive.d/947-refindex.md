# #947: loaded and nested families never list a "Not a Reference" plane

Branch `fix-947`, based on `main` 96f976f.

## What was wrong

A census of 421 born families (corpus counts only, no specimen named) shows
that a reference plane whose Is-Reference is "Not a Reference"
(`RefPlane.m_refName` 12) is never listed by a loaded or nested family:

- 0 / 1,312 `FamilyReferenceIdxMgr` entries;
- 0 / 3,349 symbol strong references.

Real Is-Reference codes are always listed (Center (Elevation), code 7:
61 / 61 and 11 / 11).

`rvt.famgen.loader` copied every origin-defining plane with an int code into
both lists (`_reference_idx_mgr` and `_symbol_placement_data`'s
`strong_refs`). Every height-driven generated family carries the #787
Case B origin elevation plane (code 12, `m_definesOrigin`), so every such
family loaded into a project, or nested into a family, arrived with an entry
no born file has. Verified on the products: the transformer, the panelboard
and the strut trapeze all have origin planes with codes `[1, 4, 12]`; the
generic model and the wireway have `[1, 4]`.

## The fix

- `src/rvt/famgen/loader.py`: `NOT_A_REFERENCE = 12` and
  `_is_reference_code(code)` (an int other than 12). Both the reference
  index and the strong references use it.
- `src/rvt/famgen/nest.py`: no change needed. It authors the nested Family
  and FamilySymbol through `loader._author_load`, so the same fix covers it
  (proven by the nested test below).
- `src/rvt/famload.py` (loading a Revit-born `.rfa`): its
  `_reference_idx_mgr` listed every origin-defining plane (as code 10). It
  now skips a code-12 plane, which is a template's origin elevation plane.
  Its strong references were already `[]`. There is no born `.rfa` in a
  fresh clone, so this path is proven by a unit test on synthetic planes
  only.

## Evidence (byte change, measured pre-fix vs post-fix on the same inputs)

Each product was loaded with `place=False` (the bundled bases hold no
electrical-equipment instance to template a placement from).

| load | file bytes | changed stream | raw | inflated |
|---|---|---|---|---|
| panelboard -> 2026 | 626,688 -> 622,592 | Partitions/21 | -512 | -79 |
| panelboard -> 2025 | 643,072 (same) | Partitions/20 | -17 | -79 |
| panelboard -> 2024 | 622,592 (same) | Partitions/21 | -16 | -79 |
| transformer -> 2026 | 675,840 (same) | Partitions/21 | 0 | -79 |
| transformer -> 2025 | 696,320 (same) | Partitions/20 | 0 | -79 |
| transformer -> 2024 | 679,936 (same) | Partitions/21 | 0 | -79 |

- In every case 11 of 12 streams are byte-identical: every stream other
  than the one partition named.
- The -79 inflated bytes are one reference-index entry plus one strong
  reference.
- The 2026 panelboard's file is 4,096 B smaller. Its -512 B raw delta is
  consistent with the shorter partition dropping one page; this is
  inferred, not traced.
- Nested (strut trapeze into a generated host `.rfa`, 2026): Partitions/0
  changes by -79 inflated / -16 raw. BasicFileInfo changes by -4 B, but
  only because the two output file names differ in length (`before` vs
  `after`). The file size is unchanged (352,256).
- `tools/rvt_validate.py` on all six post-fix projects: 0 errors. The 2026
  outputs carry 1 warning, the bases' own DataStorage decoder gap, which
  predates this change.
- Nested output: `rvt.validate` reports 0 errors and 0 warnings, and
  `constraint_law.check_file == []`.
- `constraint_law.check_file` reads family documents. It does not apply to
  the loaded `.rvt` projects.
- No test pins the bytes or sha of a loaded or nested output, so nothing
  was re-pinned.

## Test

`tests/test_loader_refindex_947.py` (shard drop-in
`tests/ci_shard.d/947-refindex.txt`) has 7 tests and takes about 14 s. It
loads the transformer into each of the three bundled bases (2026 / 2025 /
2024) and does one native nesting of the strut trapeze. It then reads the
files back under their own release and asserts:

- the product really carries a code-12 origin plane (so a pass is not
  vacuous);
- our Family's index and our symbol's strong references are exactly
  `[1, 4]`;
- no Family or FamilySymbol anywhere in the file lists 12;
- the nested file passes `constraint_law`.

It also covers `famload._reference_idx_mgr` with synthetic planes.

The module follows the #937 leak-guard pattern: `no_release_leak`, the
`release_leak_extra` fixture, and a module fixture that builds everything
before the guard's first snapshot.

With the pre-fix predicate monkeypatched back in, the module fails 5 of 7
tests. So it detects the regression.

Nothing here claims Revit or viewer behaviour (hard rule 4). The change
removes entries that no born file carries. Whether Revit cares about them
has no desktop verdict.

## BRANCH STATE (`fix-947`)

**Files written**

- `src/rvt/famgen/loader.py`: adds `NOT_A_REFERENCE` and
  `_is_reference_code`, and applies them to the reference index and the
  strong references.
- `src/rvt/famload.py`: the reference index skips code 12.
- `plugin/lib/src/rvt/famgen/loader.py` and `plugin/lib/src/rvt/famload.py`:
  regenerated mirrors (`tools/sync_plugin.py`).
- `tests/test_loader_refindex_947.py` and
  `tests/ci_shard.d/947-refindex.txt`: new.
- This record.

**Gates**

- pytest: **157 passed, 30 skipped, 0 failed**, in 170 s, over
  `test_loader_refindex_947`, `test_loader_937_928`, `test_nest_917`,
  `test_nest_locks_917`, `test_trapeze_nested_917`,
  `test_partition_tail_938`, `test_partition_tail_941`,
  `test_famgen_loader`, `test_famgen_loader_release_700`, `test_famload`,
  `test_famload_2025`, `test_famload_batch`,
  `test_famload_determinism_794` and `test_famload_fix`. The skips are
  gated on `samples/`, which is absent here.
- `tests/test_plugin_sync.py`: 9 passed.
- `tools/sync_plugin.py`, then `--check`: in sync (deny-audit clean,
  identity scan == allowlist, assets verified).
- `plugin/scripts/validate_plugin.py`: PASS (25).
- `tools/dev/check_portable_paths.py`: ok.

**Staged / shipped**

Nothing is staged for the viewer. Nothing is certified.
