# provenance — workstream record (THE PROVENANCE LEDGER, 2026-08-03)

Charter: build the instrument that makes the P0 cutover gate (G1 GENESIS
BASELINE, `docs/product/content-strategy.md`) CHECKABLE — classify every
element's authorship, roll it up into the legally-relevant categories, and
compute a PASS/FAIL. Territory touched ONLY: `src/rvt/provenance.py`,
`tools/provenance.py`, `tests/test_provenance.py`,
`experiments/genesis/provenance/*`, `docs/writer/provenance-ledger.md`, this
file. No orchestrator-owned or other-stream file edited (inventory.py etc.
read-only; name-resolution extensions live locally in provenance.py).

## Deliverables

| item | path | state |
|---|---|---|
| library: taxonomy (18 legal categories, 410 explicit classes + ancestry rules, 0 unmapped across all six samples), per-element verdicts (4 provenances + unmatched/unbaselined), two-detector clone lineage (references + shingle similarity), embedded family-document units, G1 gate (+ `strict`), text renderer | `src/rvt/provenance.py` | done |
| CLI: `tools/provenance.py FILE.rvt --baseline PATH\|auto\|self [--json] [--strict] [-q]`, exit 0 pass / 2 fail (CI-gateable) | `tools/provenance.py` | done |
| the three commissioned reports (+1) | `experiments/genesis/provenance/{rme_self_baseline, V29_room_with_circuits, R4s_deepest_viewer_passed, R4_deepest_skeleton}.json` | on disk |
| human ledger (results, gap list, design decisions, limits) | `docs/writer/provenance-ledger.md` | done |
| tests (11: taxonomy coverage, all four provenances on real files, wrong-baseline safety, gate logic, CLI e2e) | `tests/test_provenance.py` | pass |

Reproduce (repo root, `.venv/bin/python`):
```
tools/provenance.py samples/rmebasicsampleproject.rvt --baseline self
tools/provenance.py experiments/acceptance/V29_room_with_circuits.rvt --baseline samples/rmebasicsampleproject.rvt
tools/provenance.py experiments/genesis/R4.rvt --baseline samples/rstbasicsampleproject.rvt
```
Runtime 0.3–4 s per file. No `.rvt` is emitted by this stream (read-only
instrument), so `tools/rvt_validate.py` had nothing to arbitrate — inputs are
the existing samples / acceptance / genesis files.

## Results — the three commissioned runs

1. **Fresh sample vs itself** (`rmebasicsampleproject`): 28,132/28,132
   `autodesk-sample`, 305 Autodesk embedded family documents, G1 FAIL
   (27,880 derived in expression-bearing categories). Calibration: the
   instrument reads a pristine sample as 100 % Autodesk in every category.
2. **`V29_room_with_circuits.rvt` vs rme:** 28,132 `autodesk-sample` +
   **16 `transitive-cloned`**, 0 created, 0 modified — the honest current
   state. Lineage recovered per element: 4 walls -> sample `BasicWallType
   563416 "MW 11.5"` (+84–86 % clones of `SWall 573735`); 6 panels ->
   sample `FamilySymbol 619617 "400 A"` (M_Lighting and Appliance
   Panelboard, 87–88 % clones of instance 742670); 3 transformers -> sample
   `FamilySymbol 621228 "45 kVA"`; 3 circuits -> sample `RbsCableType 887996
   "XHHW"`. G1 FAIL (27,896). Confirms content-strategy §1: what we create
   today is derived expression until the FAMILY / TYPE is ours.
3. **Deepest reductions** (rstbasic baseline). `R4s` (deepest that PASSED the
   viewer): 13,138 pure sample survivors, 52 Autodesk family docs, G1 FAIL
   (12,986) across all 15 gated categories — the safe sweep is garbage
   collection, not de-authoring. `R4` (deepest skeleton, 2,839 elements) =
   **THE GAP LIST for the assembler**: object styles **2,801** (2,183
   GStyleElem + 616 CategoryElem + 2), **52 embedded Autodesk family
   documents** (the reducer only deletes HOST elements — every reduction
   keeps 100 % of embedded families byte-for-byte), 14 phases/options, 13
   project-info/settings, 9 levels, 1 DBViewType, 1 KeynoteTable. Assembler
   work queue, ordered: style/category catalog encoder -> family-document
   removal + our-family loader (ContentDocuments encoder + id remap) ->
   phases/settings/levels/view-type authoring.

## Evidence log

### E1. All four provenance classes fire on real files
- `autodesk-sample`: any untouched sample vs itself (byte-identical
  seq-102 object + seq-101 header + seq-103 rep at the same id/class).
- `transitive-cloned`: V29's 16 created elements (above rme's watermark
  888,013) — both detectors agree (type/symbol references AND 84–89 %
  shingle similarity to a named sample specimen). H2 also flags a created
  `SketchPlane` as a clone of a sample sketch plane.
- `ours-modified`: `M3_modify.rvt` vs rme -> exactly 2: Level 378118 and
  FamilyInstance 581483, "differs in object" (M4/M2/M1 likewise show
  1–4 modified). Proves the byte-compare separates edits from clones.
- `unmatched` / wrong baseline: rme vs the rst baseline -> 26,900
  unattributable, overlap 0.04, `WARNING: baseline mismatch`, gate refuses.
  `--baseline auto` (ElemTable id-set Jaccard over samples/*.rvt) picks the
  right sample for every acceptance file tested.

### E2. Creation cannot be detected by episode — only by id watermark
`commit.py` reuses an existing episode for new ElemRecs (KNOWLEDGE §commit
layer), so `creation_ep` never marks our elements. The reliable signal is
"absent from baseline AND id > baseline `IdentifierSource.m_last`". V29's
16 created ids = 888,014..888,029, exactly watermark+1.. .

### E3. Reference collection has geometry-index false positives
`mutate._collect_ids` over a decoded SWall returns face/edge indices
(`m_geomSteps…m_bRepFormSnapshot…m_faces[i].m_id` = 3,4,5,…) that collide
with real small element ids (FillPatternElem 3–7, LinePatternElem 10–18).
The lineage detector excludes any path containing
m_geomSteps/m_faces/m_edges/m_geomTops/Snapshot/HistTable/m_pBBox. (Flag for
the reduce/commit owners: `reference_graph()` shares this — a wall would be
seen to "reference" fill patterns 3–18. Not my territory to fix.)

### E4. Embedded family documents survive every reduction
StreamWalker units 1..k enumerated per partition stream; unit separator
GUID == host `Family.m_oFamDoc.m_contentDocGUID` (bytes_le UUID; 41/52 rst
units, 147/305 rme units link this way — the rest are nested/annotation
family docs reached via a different path). R4/R4s both retain all 52
Autodesk family documents => genesis needs an explicit unit-removal +
own-family-load step, not just element deletion.

### E5. Object styles are the numerical bulk of the irreducible core
In the R4 skeleton, 2,801 of 2,839 host survivors (98.7 %) are
CategoryElem/GStyleElem. `docs/writer/genesis.md` §4.3 argues these are
deterministic per release+template and should be REGENERATED by our
encoder, not authored — the ledger will read them `ours-created` the day
that encoder writes them. (Concurrent stream `genesis/object_styles.json`
appears to be building exactly that catalog.)

## Gotchas found (for KNOWLEDGE.md merge)

1. **`creation_ep` is not a creation marker** (commit reuses episodes) —
   authorship-by-id needs the baseline's watermark, i.e. provenance is
   inherently RELATIVE to a supplied reference sample. Store which sample a
   file descends from (BasicFileInfo / History[0] make it recoverable; the
   ledger's `--baseline auto` recovers it by ElemTable overlap).
2. **The reducer's blind spot:** deleting host elements never removes an
   embedded family document; the deepest possible reduction still ships 52
   Autodesk `.rfa`s inside. G1 cannot be reached by reduction.
3. **`_collect_ids` geometry-index false positives** (E3) — anyone using
   `reference_graph()` for closure over-links walls/regions to low-id
   pattern elements.
4. **Report-only vs gated is a legal knob, not code truth.** Datums and
   bookkeeping are ungated by default (`--strict` gates them); the
   `expression_bearing` flags in `CATEGORIES` are the surface counsel edits.

## Full-suite result at handoff

`pytest -q`: **293 passed, 1 failed, 4 min 59 s.** The single failure is
`tests/test_plugin_sync.py::test_plugin_is_in_sync_with_source` — the
`plugin/` source bundle has drifted from `src/` by 9 files: MY new
`provenance.py` (auto-detected as a plugin module) plus 8 files owned by
OTHER concurrent streams (`identity.py`, `mep/*`, `genesis/*`). This is an
integration step, not a defect: `plugin/` is outside every worker's
territory and syncing mid-flight would clobber concurrent streams. **The
orchestrator should run `python tools/sync_plugin.py` ONCE after all
streams land** (memory: rev-revit plugin bundles source copies). All 11
provenance tests pass; no pre-existing test changed.

## Proposed next tasks (orchestrator decides)

1. **Wire the gate into the milestone loop**: every genesis candidate
   commits `experiments/genesis/provenance/<name>.json`; "DONE" for a
   genesis stream = `tools/provenance.py … -q` exits 0. Consider a
   `verify`-skill hook so no candidate is claimed without a ledger.
2. **The assembler's queue, from the R4 gap list**: (a) object-style /
   category catalog ENCODER (2,801 objects) — the biggest block; (b) drop
   embedded family units + load OUR families (ContentDocuments encoder + id
   remap); (c) author phases / settings / levels / one view + view type.
   Re-run the ledger after each; the gap list is the burndown.
3. **Provenance ledger for the family-document side**: today units are
   attributed only by GUID membership; once ContentDocuments decodes, ledger
   each embedded document's own elements the same way (a synthesized `.rfa`
   is the first thing that should read all-`ours-created`).
4. **Fold E3's path-exclusion list into `mutate._collect_ids`** (owner:
   commit/reduce streams) so `reference_graph` stops over-linking.
5. **Legal review of the taxonomy**: hand counsel `docs/writer/
   provenance-ledger.md` §5 — which categories are gated is the review
   surface (`CATEGORIES` expression_bearing flags), especially the
   "format constant vs expression" call on object styles / category tables.

BRANCH STATE: no VCS (plain directory); all work uncommitted at:
src/rvt/provenance.py, tools/provenance.py, tests/test_provenance.py,
experiments/genesis/provenance/{rme_self_baseline,V29_room_with_circuits,
R4s_deepest_viewer_passed,R4_deepest_skeleton}.json,
docs/writer/provenance-ledger.md, docs/inbox/provenance.md. Suite: 293
pass / 1 fail (plugin-sync drift — orchestrator's `tools/sync_plugin.py`
step, shared across 4 streams). READY.
