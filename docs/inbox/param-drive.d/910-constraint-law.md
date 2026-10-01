# 910 — the constraint law stops demanding back-edges, and checks the drive's shape instead

Stream: **param-drive** (fragment; index `../param-drive.md`). Issue **#910**
(Refs #787, #904, #907).

## Why

The #787 census found `m_constrInfo == []` on every element of all 421 Revit-born
reference families: 0 of 421 files carry a back-edge. The old rule CG2 required
them, so it reported 38 and 20 errors on two born specimens. It also reported
22 on the #907 trapeze, which the owner's desktop had verified as driving.
`tools/self_battery.py` runs this law, so the verified trapeze would have shown
as broken.

## What changed

- **`src/rvt/famgen/constraint_law.py`**
  - **CG2 retired.** A document without back-edges is never an error, and no
    back-edge is ever demanded. `RETIRED_RULES = ("CG2",)` keeps the id from
    being reused.
  - **Kept:**
    - CG1: a witness names an element that exists.
    - CG3: warning on an inert constraint.
    - CG4: a back-edge that is present must point at a real constraint.
  - **Added, the corpus-attested shape of the in-plane drive:**
    - **CG5, shape.**
      - An `Alignment` has exactly two witnesses.
      - A labelled `LinearDimString` has at least two witnesses and one
        segment per gap.
      - Its `m_paramId` exists in the document.
    - **CG6, registration.**
      - A sketch lock (an `Alignment` carrying `SketchMembership`) appears in
        its sketch's `m_dimIds`.
      - Every id in `m_dimIds` is also in the sketch header's
        `m_parents.m_deletion`.
      - The sketch itself exists.
    - **CG7, on-plane.** A sketch lock's curve lies on its `RefPlane`, within
      1e-5 ft. The plane passes through `m_freeEnd` and is spanned by
      `m_bubbleEnd - m_freeEnd` and `m_cutVec`.
      - `GLine` with witness geomTag 0: both ends `m_origin + m_dirVec·t`,
        for each `t` in `m_endParams`.
      - `GArc` with geomTag 1: `m_center`.
      - Any other case is not judged, never guessed.
  - **API.**
    - `check_graph` accepts optional 4-tuples carrying the element header.
    - A new `universe=` argument means ids the caller did not decode still
      count as "in the document".
    - `check_file` now decodes `VarSketch` headers (seq 101) and passes every
      element id of the file as the universe. Before this, a lock to a
      class the law does not decode, such as a Level, would have been a false
      CG1.
- **`src/rvt/famgen/famdim.py`.** `apply_constraint_back_edges` is kept only
  for documents without the born drive law. `skeleton.finalize` already skips
  it when `doc.born_drive_law` is set. The function now carries a comment
  citing the 0/421 count.
  - It is not removed because `skeleton.finalize` still calls it for non-law
    chains (the panelboard, #372). Removing it would change those families'
    bytes, which belongs to their own lane's change.
  - No test or tool calls it directly.
- **`tools/self_battery.py`.** New catalog rows run the law on the
  desktop-verified chains:
  - `archetype_strut_trapeze` (the #907 trapeze);
  - `drive_one_box_law` and `drive_one_box_control`, the #787 probe pair:
    `make_generic_model(parts=[box], drive=True)` plus
    `drive_law.apply_born_inplane_law`, with `regen_edge` True and False.
- **Tests.**
  - `tests/test_constraint_law.py`: the three tests that pinned CG2 now pin
    that it is gone. A one-directional graph passes, a plane without a
    back-edge passes, and `"CG2" in RETIRED_RULES`. The other tests were moved
    to two-witness alignments so CG5 does not mask them.
  - New `tests/test_constraint_law_910.py`, with drop-in
    `tests/ci_shard.d/910-constraint-law.txt`:
    - synthetic CG5, CG6 and CG7 cases (GLine, a skewed GLine, GArc centre,
      and an unknown case that is not judged) and the `universe` argument;
    - the trapeze and both probe-pair members pass both `check_doc` and
      `check_file` with zero back-edges;
    - three deliberately broken chains fail, both in memory and from the
      written `.rfa`: a curve moved 0.25 ft off its plane (CG7), a lock
      removed from `m_dimIds` (CG6), and a lock dropped from the sketch's
      `m_deletion` (CG6);
    - `self_battery._run_one` passes the three verified rows and fails a
      broken one.

## Finding: the panelboard chain locks edges to planes they are not on

The new CG7 fires on `make_panelboard`, in all three battery variants:
`panelboard`, `panelboard_types` and `panelboard_600A`.

- `param_drive.wire_panelboard_drive` puts the bottom and top side planes at
  y = ±H/2.
- The profile spans y = 0..H (0..0.479 ft), so the bottom and top locks sit
  **0.2396 ft off their planes**. The x locks are on their planes.
- The old law passed this file with 0 errors, because it only looked at
  back-edges.
- This is a contradiction in the file's own geometry. It is the first
  in-session explanation for why the panel chain has never flexed on the
  desktop (#372) and for the 2026-08-11 click failure (#689). Neither cause is
  verified; hard rule 4 applies.
- It is outside #910's territory (`param_drive.py`). It is pinned by a strict
  xfail, `test_the_panelboard_chain_is_coherent`, so the fix flips it. It needs
  its own follow-up issue.
- Result: the battery reads 18/21 on this branch. The 3 failures are this
  finding, not regressions. On `main` the same three files pass the old law
  with 0 errors.

## Evidence

- Trapeze: the old law gave 22 CG2 errors; the new law gives 0 in `check_doc`
  and 0 in `check_file`.
- One-box P and C: 0 findings each. Each has 4 sketch locks and 0 elements with
  `m_constrInfo`.
- Broken chains, in both the document and the written file: off-plane gives
  `[CG7]`, unregistered gives `[CG6]`, and deletion-dropped gives `[CG6]`.
- `tools/self_battery.py`: 18/21 pass. The trapeze and the one-box P and C
  pass. The 3 panelboard variants FAIL on CG7, as described above.

## Open questions

- CG5's "exactly two witnesses per `Alignment`" matches every specimen in the
  #787 decode (sketch locks and face locks). It was not re-counted across all
  421 files in this session, because the corpus is not in this sandbox.
- CG7 judges only GLine/geomTag 0 and GArc/geomTag 1. Other witness tags (line
  endpoints, for example) are skipped until a specimen names them.

## BRANCH STATE

- **Files:**
  - `src/rvt/famgen/constraint_law.py`
  - `src/rvt/famgen/famdim.py` (comment and docstring only)
  - `tools/self_battery.py`
  - `tests/test_constraint_law.py`
  - `tests/test_constraint_law_910.py` (new)
  - `tests/ci_shard.d/910-constraint-law.txt` (new)
  - the plugin mirrors `plugin/lib/src/rvt/famgen/{constraint_law,famdim}.py`,
    regenerated by `tools/sync_plugin.py`
  - this record
- **Gates:**
  - `tools/sync_plugin.py`, then `--check`: in sync.
  - `plugin/scripts/validate_plugin.py`: PASS (25 assertions).
  - `pytest` on `tests/test_constraint_law.py`, `tests/test_constraint_law_910.py`,
    `tests/test_famgen_parametric.py`, `tests/test_drive_law_904.py`,
    `tests/test_strut_trapeze_899.py` and `tests/test_plugin_sync.py`:
    168 passed, 1 xfailed.
  - `tests/test_family_anatomy_837.py`, `tests/test_famload_fix.py`,
    `tests/test_residue_c.py` and `tests/test_bootstrap.py`: 165 passed,
    9 skipped.
- **Staged / shipped:** nothing staged for the viewer. This is an instrument
  change only, and no family's bytes change.
