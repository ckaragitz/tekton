# Manipulation — editing / moving / retyping / deleting EXISTING elements

Stream: `manipulate` (wave: writer). Module: `src/rvt/manipulate.py`.
Tests: `tests/test_manipulate.py` (8). Proof harness:
`experiments/manipulate/make_proofs.py` (M1–M4 on two files) +
`experiments/manipulate/robustness.py` (six-file read-only pass).
Companion: `docs/writer/mutation-plan.md` (the CREATE path this extends).
Confidence tags: **[V]** verified on the corpus / by structural proof,
**[H]** hypothesis (needs Revit acceptance), **[D]** design decision.

## 0 · TL;DR

The create path (`rvt.mutate` + `rvt.commit`) appends new elements. This
module is the CHANGE / DELETE path for elements that already exist in a
user's uploaded project. Every operation takes a
`rvt.mutate.Document.from_file(path)` and returns a JSON-able **plan**
carrying framed record bytes; `commit_plans(src, out, plans)` re-emits
save-unit 0 of `Partitions/<N>` and `Global/ElemTable`, re-frames both with
real CRCIO ECC and rewrites the container; `verify_manipulated(out, ...)`
proves the result structurally and the change is confirmed semantically by
re-opening the output with `Document.from_file`.

```
doc  = rvt.mutate.Document.from_file("project.rvt")

plan = delete_element(doc, eid, cascade=False)   -> DeletePlan   (fails LOUDLY if dependents)
plan = delete_element(doc, eid, cascade=True)    -> DeletePlan   (closure + referrer edits)
plan = modify_element(doc, eid, {"json.path": v}) -> ModifyPlan
plan = set_level_elevation(doc, level_id, ft)     -> ModifyPlan
plan = set_param(doc, eid, param_id, value)       -> ModifyPlan  (rename_panel / set_mark)
plan = move_instance(doc, eid, (dx,dy,dz), rotation, delta=True) -> ModifyPlan
plan = retype_instance(doc, eid, new_symbol_id)   -> ModifyPlan

commit_plans(src, out, [plans...])     # or commit_session(doc, out)
verify_manipulated(out, deleted_ids=..., edited_ids=...)
```

Proven **[V]** end-to-end (writer + structural verify + semantic re-read)
on `rmebasicsampleproject.rvt` AND on `racadvancedsampleproject.rvt` (a
file the tools were never developed against): see §7 and
`experiments/manipulate/proofs.json`. Autodesk-Viewer acceptance of the
eight M-files is pending (the orchestrator uploads them) **[H]**.

## 1 · The physical model of an edit / delete (what changes on disk)

| stream | delete | modify / move / retype |
|---|---|---|
| `Partitions/<N>` save-unit 0 | the element's THREE records (seq 101 `ElementHeader` / seq 102 object / seq 103 rep) removed from their per-seq segments; every referrer's records REPLACED with neutralised copies; unit 0 re-blocked (`chunk_segment`, ≤131,072-byte inflated blocks, flags 4/6/7/5, `ISIZE == hdr_len(seq)*A + C + adj(flags)`); units 1..k (embedded families) and every other stream copied byte-for-byte; per-seq sentinel (id −1) stays last | the element's edited record(s) re-encoded (`rvt.encode`, byte-exact codec) with a fresh `stamp = adler32(u16 class ‖ object)` and spliced at the same position (record length may change ⇒ unit 0 re-blocked); other seqs of the element are only rewritten when the edit touches them (move: 101 bbox / 102 Trf / 103 rep; retype: all three) |
| `Global/ElemTable` | the deleted rows removed, `count` decremented, **id watermark (`IdentifierSource.m_last`) kept** so ids are never re-issued | untouched (re-emitted identically) |
| partition stream header | `u32 elem_table_count` (offset 14) = new ElemTable count | = unchanged count |
| ECC / container | both re-emitted streams re-paged with real 353-byte CRCIO trailers (`ecc.frame_stream`); CFB re-written (`cfb_writer.write_cfb`) | same |
| save-history (`History` / `DocumentIncrementTable` / `BasicFileInfo`) | **not touched** [D]: edited/deleted elements keep their existing episodes, so the History invariant (`count == max(modified_ep)+1`) still holds — the same minimal-commit policy as `commit.commit_new_elements`; a full save can be layered later with `streams_edit.record_save()` | same |

Structural invariants proven on every output (`verify_manipulated`) [V]:
gzip CRC of every member of every stream = valid; every re-emitted page's
ECC trailer byte-exact; framing walker 0 errors; block ISIZE identity 0
mismatches; header count == ElemTable count; sentinels last in all three
seqs; every seq-102/103 unit-0 record's adler32 stamp valid; deleted ids
absent from unit 0 (all seqs) AND from the ElemTable; ElemTable ids still
ascending; **unit-0 seq-102 id set == ElemTable id set** (the host-document
identity from mutation-plan §1) preserved.

## 2 · The edit session: decode → re-encode byte-exact → patch → re-encode

`session(doc)` attaches an `EditSession` to the Document. Every edit works
on ONE shared decoded working copy per (element, seq) so several plans
against one element compose (move + rename + retype), and each plan's
`RecordEdit` is re-serialised from the working copy; `commit_plans` keeps
the LAST replacement per (seq, elem_id) and a removal beats a replacement.

**Precondition [V]:** before an element is edited, its UNEDITED decoded
object must re-encode byte-exact against the on-disk payload
(`EditSession._orig_bytes_check`); an element that does not decode cleanly
or does not round-trip is REFUSED (`ManipulationError`) — we never write a
lossy record. Robustness pass (§6): sampled host elements re-encode
100.000 % on all files probed; the only class refused in the corpus is the
1,171 rme `FamilyInstance`s carrying Extensible-Storage `ESEntityCell`
blobs (duct fittings / accessories, the known ES limitation) — those can
still be DELETED (deletion never re-encodes the target) but not modified.

## 3 · DELETE: `delete_element(doc, eid, cascade=False)` → `DeletePlan`

### 3.1 Records and table

Remove the element's seq-101/102/103 records from unit 0 (identify by
`elem_id` in each seq stream), drop its 40-byte `ElemRec` from
`Global/ElemTable` (count −1, watermark unchanged), fix the partition header
count. `apply_edits_to_segment` guarantees the sentinel record stays last.

### 3.2 Dependents (the cascade set) — `dependents_of()`

An element X's HARD dependents (things that cannot outlive X) are found
without a global schema of "what depends on what", from three structural
signals; everything else that merely mentions X is a soft REFERRER (§3.3).

| relation | detector | evidence |
|---|---|---|
| **hosted** | another element's object has `m_hostId` / `m_extraHostIds` / `m_explicitHostIds` == X, or a `SketchPlane` whose `m_oPlaneRef.m_geomRef.m_elemId` == X (a face on X) | rme wall 573703 → 2 SketchPlanes on its faces → their 10 face-hosted fixtures at depth 2; racadv wall 144180 → door 145999 |
| **owned** | `ElemRec.m_OwningElementId == X` (ElemTable ownership) or object `m_ownerElemId / m_famId / m_symbolFamilyId / m_superInstanceId == X` | racadv table 180294 → 4 chair sub-instances; rme conduits → `ConduitRun` / `SegmentCenterLine` children |
| **associated-level** | object `m_assocLevelId / m_levelId / m_genLevelId == X` (X is a Level: deleting it deletes the elements placed on it and its plan views) | rstbasic Level 245423 (test) |
| **annotation dependent** | X named in `ElementHeader.m_parents.m_deletion` of a LEAF/annotation class only: `*Tag`, `*DimString`/`*Dimension`, `SpotElev/Coord/Slope`, `PostedWarningElem`, `PanelScheduleView`, openings | racadv wall 144180 → its `IndependentTag` 216554 + door tag 216514 (depth 2) + `LinearDimString` 145958; rme panel 630241 → `PanelScheduleView` |

`dependency_report(doc, eid)` computes the closure breadth-first (bounded by
`max_depth=8` and `max_cascade=2000`, both reported when hit) plus the
referrers; `delete_element(cascade=False)` raises **`DependentsError`**
carrying that report when the closure is non-trivial (the fail-loudly path);
`cascade=True` deletes the whole closure. A capped cascade is refused
outright — a runaway closure is a modelling signal, not a delete to run.

**Why `m_deletion` is NOT a general hard-dependency signal [V]:** Revit's
`ElementParents.m_deletion` list mixes ownership with regenerate/constraint
peers. Evidence: racadv windows 145607/145683 are hosted on wall **139857**
yet list neighbouring wall **144180** in `m_deletion` (a join/constraint
mention); the naive rule (cascade every `m_deletion` mention) deleted them
with 144180 and, on rme, turned an air terminal (379463) delete into the whole
duct network — `RbsHvacSystem` → its 30 members → their systems → 2,300+
elements at depth 8, taking minutes. Only annotation/leaf classes honour
`m_deletion`; hosts, instances, sketches, curves, rooms, plans and MEP
systems are PEERS (`_is_peer_class`: `SWall/RoomElem/SpaceElem/Level/Grid/
CurveElem`, `Rbs*System`, `*System`/`*Network*`/`*Sketch`,
`Rbs{Duct,FlexDuct,Pipe,FlexPipe,Wire}Curve`, `CableTray`, `Conduit`, …).

### 3.3 Referrers — `referrers()` + `_neutralise()`

Any OTHER host-document element whose records mention a deleted id gets an
edited copy with the id neutralised, so no dangling reference survives:

* a scalar id field inside a dict (`m_hostId`, `m_upToLevelId`, …) → `-1`;
* a bare id inside an id list (`m_deletion`, `m_appearanceParents`, …) →
  removed from the list;
* a structured entry inside a list that mentions the id anywhere (a join
  record, an `m_arrRefs` connector reference, an `m_component2BaseSegmentMap`
  pair, an `m_pathNodes` node, an `m_rgSections` entry) → the entry is
  dropped;
* EXCEPT pointed-to sub-objects (`ptr_class`/`pid` holders such as a
  `Connector` or `RbsDuctSection`) which are KEPT and neutralised INSIDE —
  dropping a `Connector` from `m_connPtrArray` would shift the positional
  `m_nIndex` back-references other elements hold into that array [D].

Detection is byte-first (a false negative is impossible: `ElementId`
serialises as a flattened little-endian i64): `_ref_index` builds a one-time
haystack over the host-document records per seq (rme: 6.5 / 46 / 38 MB) and
`candidate_referrers` runs one `bytes.find` sweep per target id; candidates
are then DECODED and only genuine `ElementId` paths count (a `_NOT_ELEMENT_ID`
key list excludes geometry topology tags, indices, pointer bookkeeping
`pid`/`weakref`). Referrer classes seen in the proofs: joined `SWall`s
(their join records drop), `VarSketch` (ceiling sketch constraints drop —
the ceiling KEEPS its sketch), `RoomElem`/`LevelRoomPlan` (room topology
segments), `RbsPipeCurve`/`RbsFlexDuctCurve` (connector `m_arrRefs`),
`RbsHvacSystem`/`RbsPipingSystem`/`MEPNetworkDataElem` (member connector
refs / segment map), `ElementGroup` (member list), `CurveElem`.

## 4 · MODIFY: `modify_element(doc, eid, {json_path: value})` → `ModifyPlan`

Generic: any field of the decoded seq-102 object (or 101/103 via `seq=`) is
set by JSON path (`"m_pSurface.value.m_origin[2]"`, `[i]` list indexes),
the record re-encoded byte-exact with a fresh adler32 stamp and spliced at
its position (unit 0 re-blocked, so a longer/shorter record — e.g. a longer
name string — is handled). Built on it:

| helper | edit | field |
|---|---|---|
| `set_level_elevation(doc, level, ft)` | a Level's datum height | BOTH cached copies: `m_pSurface.value.m_origin[2]` and `m_pFace.value.m_pSurf.value.m_origin[2]` (Plane origin z, project feet) |
| `set_param(doc, eid, param_id, value)` / `find_param` | a built-in / project parameter by id | Element param sets `m_pParamValueSet{Double,Int,AString,ElementId}.value.m_paramSet[i].m_value`, and instance `m_pInstParams.value.m_params[i]` (`m_str`/`m_value`/`m_int`/`m_elemId` by python type) |
| `rename_panel(doc, eid, name)` | 'Panel Name' | `BIP_RBS_ELEC_PANEL_NAME = -1140078` (AString) |
| `set_mark(doc, eid, mark)` | 'Mark' | `BIP_ALL_MODEL_MARK = -1001203` (AString) |
| `instance_placement(doc, eid)` | (read) `{m_or, m_3x3, m_symbolId, m_masterSymbolId, m_hostId}` | |

Semantic caveat [D]: derived caches Revit recomputes are NOT rewritten (a
renamed panel's name is copied into its circuits' `m_strDescription`; a
level's associated elements move on regen; a retyped instance's
`m_pInstParams`/rep geometry are those of the old type until regenerated).

## 5 · MOVE / RETYPE an instance

`move_instance(doc, eid, xyz, rotation=None, delta=True, include_owned=True)`
rewrites the placement everywhere it is cached — exactly the fields
`add_family_instance` sets on creation [V vs the create path]:
`m_pInstanceInfo.value.m_Trf.m_or` (+ `Rz(rotation) · m_3x3` when
rotating), the mirrored `m_instOrigin`, the seq-103 cached `GElement`
(`m_subNodes[*].GInstance.InstanceInfo.m_Trf` + `m_bBox`/`m_tightbBox`
translated), and the seq-101 header `m_pBBox.value.m_minmax` (translated).
`include_owned` moves ElemTable-owned child instances rigidly with it (a
nested table's chairs).

`retype_instance(doc, eid, new_symbol_id)` points a free / face-hosted
instance (`symbolId == masterSymbolId` pattern) at another loaded
`FamilySymbol` of the SAME category (and same family unless
`allow_family_change`): rewrites `InstanceInfo.m_symbolId` +
`m_masterSymbolId`, the seq-103 rep's `GInstance` symbol ids, and the
header's `m_appearanceParents` / `m_deletion` lists (old symbol → new;
`_remap_in_lists`). Host-cut instances (doors/windows, whose `m_symbolId` is
a per-host geometry-symbol CLONE ≠ `m_masterSymbolId`, mutation-plan §6.4)
raise — retyping them needs the cut-clone recipe (phase 2).

## 6 · Robustness on foreign files (`experiments/manipulate/robustness.json`)

`Document.from_file` (partition walk, ElemTable, schema) + a decode of
EVERY host-document element in all three seqs + a byte-exact re-encode
sample (4,000 elements × 3 seqs) + manipulate smoke calls, on all six
samples:

| file | MB | load s | host elems | seq-101/102/103 clean % | re-encode exact | notes |
|---|---:|---:|---:|---|---|---|
| rstbasicsampleproject | 6.4 | 0.1 | 13,936 | 100 / 99.95 / 100 | 12,000/12,000 | 7 undecodable: `RebarShape`×6, `DataStorage`×1 |
| racbasicsampleproject | 18.8 | 0.3 | 8,401 | 100 / 100 / 100 | 12,000/12,000 | — |
| rmebasicsampleproject | 31.1 | 0.6 | 28,132 | 100 / **95.84** / 100 | 11,915/11,915 (85 skipped) | 1,171 `FamilyInstance` (duct fittings/accessories −2008010/−2008049) carry `ESEntityCell.m_blob` Extensible-Storage blobs → refused for modify, deletable |
| racadvancedsampleproject | 16.3 | 0.2 | 17,231 | 100 / 100 / 100 | 12,000/12,000 | not a development file; fully clean |
| rstadvancedsampleproject | 14.4 | 0.2 | 13,855 | 100 / 100 / 100 | 12,000/12,000 | not a development file; fully clean |
| dach-sample-project | 132.5 | 2.4 | 49,776 | 100 / **96.50** / 100 | 11,999/11,999 (1 skipped) | German locale, worksharing-ish; the 1,741 undecodable objects are ALL the ES-blob case, spread over 8 classes (`FamilyInstance` 1,284, `Rebar` 122, `AnalyticalMember` 81, `AnalyticalPanel` 40, `RebarSystem` 30, `FabricSheet` 27, `CurveElem` 24, `Floor` 21, plus `SWall`/`DBView3d`/`FamilySymbol`/`ProjectInfo`) |

No walker errors, no framing errors, no schema-anchor failures on any file;
every framing walk that `Document.from_file` performs was clean, and the
re-encode precondition held for every decodable element sampled. **The one
recurring gap is Extensible-Storage:** every non-clean object on every file
fails at `...CellList.m_cells[0]->ESEntityCell.m_entityMap[0].second.m_blob`
(`pointer token pid=-1 to unknown class`) — a runtime ES schema the archive
schema does not define. On rme/dach those elements are un-MODIFIABLE by
this layer (refused loudly) though still deletable; an opaque-blob
passthrough in the decoder/encoder (their runtime ES schemas live in
`Global/Latest`'s `ADocument` ES-schema table, KNOWLEDGE §A10) would lift the
limit — filed as the top follow-up.

## 7 · The proofs (`experiments/manipulate/proofs.json`, `make_proofs.py`)

Each file below is written by the real writer and passes ALL structural
checks (0 CRC failures, 0 ECC mismatches, 0 walker errors, 0 ISIZE
mismatches, stamps ok, sentinels last, header count == ElemTable count,
unit-0 ids == ElemTable ids), and the semantic re-read confirms the change.

| file | source | proves |
|---|---|---|
| `M1_delete.rvt` | rmebasic | delete an isolated instance (air terminal 430715, no dependents/referrers): 3 records + ElemRec gone, watermark kept |
| `M2_delete_cascade.rvt` | rmebasic | delete `SWall` 573703 WITH dependents: `DependentsError` report (2 face SketchPlanes → 10 face-hosted fixtures, 4 dims, a room tag) then `cascade=True` → 18 elements removed, 37 referrers neutralised (pipes' connectors, piping systems, rooms, ceiling sketches, joined walls) |
| `M3_modify.rvt` | rmebasic | Level 2 (378118) elevation +2 ft (both Plane origins); panelboard 581483 renamed `PP-1B-RENAMED`, Mark `15-EDITED` |
| `M4_move_retype.rvt` | rmebasic | transformer 624416 moved +5 ft X (Trf, `m_instOrigin`, header bbox, cached GElement) and retyped 500 kVA (621242) → 75 kVA (621232) |
| `M1_delete_rac.rvt` | racadv | delete an isolated structural framing instance (201309) |
| `M2_delete_cascade_rac.rvt` | racadv | delete `SWall` 144180 hosting door 145999: report (door + door's tag + wall tag + dimension), cascade of 5; 12 referrers neutralised (joined walls, neighbour walls' windows, ceiling sketches, room plan) |
| `M3_modify_rac.rvt` | racadv | level '03 - Floor' (136342) +1 ft; door 147834 Mark `130A` → `130A-EDITED` |
| `M4_move_retype_rac.rvt` | racadv | dining table 180360 moved +5 ft X together with its 4 owned chairs; retyped 0915 mm → 1525 mm (180237) |

## 8 · Performance (M-series, this Mac)

`Document.from_file`: 0.1–0.6 s for the ≤31 MB samples. A modify commit
= re-emit unit 0 + ElemTable + ECC + CFB write: ~6 s (rstbasic), ~30 s
(rme, 32.6 MB out). `dependency_report`: 0.2–4 s (byte haystack + decode of
the candidates). `verify_manipulated`: 5–30 s.

## 9 · Confidence / unknowns

| claim | status |
|---|---|
| delete = remove 3 records + ElemRec, count −1, watermark kept, header count follows | **V** (structural + re-read, both files) |
| unit-0 re-block preserves the block identities / sentinels / stamps | **V** (`verify_manipulated`, `test_chunk_and_edit_segment_roundtrip`) |
| byte-exact re-encode precondition for edited records | **V** (12,000/12,000 per file, 100 % on 4 files) |
| dependents model (host/owned/level/annotation) + referrer neutralisation are what Revit needs | **H** — internally consistent and referentially clean; only Revit acceptance can judge (the M-files are queued for the viewer) |
| `m_deletion` mixes ownership with peer/constraint mentions | **V** (racadv 145607/145683 counter-example; rme system explosion) |
| moving = rewriting Trf / instOrigin / rep transforms / header bbox suffices | **H** (same fields the accepted creation path sets; regen re-derives caches) |
| retype = symbol ids + parents remap suffices for free/face instances | **H** |
| Extensible-Storage instances (rme fittings) editable | **NO** — refused loudly (ES blob not encodable); deletable |
| host-cut door/window retype / move along the host wall | **not implemented** (phase 2, cut-clone recipe) |

**Unknowns / open items:** O1 whether Revit tolerates our neutralised
referrers (e.g. a `Connector` with an emptied `m_arrRefs`, a room whose
segment lists shrank) or regenerates/complains — needs the acceptance run;
O2 whether deletes should also record a new save episode (we reuse existing
episodes, like the create path's minimal commit); O3 group membership
edits (`ElementGroup` member lists shrink — group type/instances may need
regen); O4 the `-2001320`/detail-item categories deleted in M1_rac are
low-risk stand-ins — a plainer furniture delete would be nicer but the
architectural sample had no isolated furniture; O5 circuiting-side effects
of deleting circuit members (the circuit keeps an empty member connector —
Revit may delete the empty circuit itself); O6 `BIP` id → name table beyond
the four ids used here.

## 10 · Reproduction

```
.venv/bin/python experiments/manipulate/make_proofs.py        # 8 files + proofs.json
.venv/bin/python experiments/manipulate/robustness.py         # 6-file read-only pass
.venv/bin/python -m pytest tests/test_manipulate.py -q         # 8 passed
.venv/bin/python -m rvt.manipulate samples/rmebasicsampleproject.rvt report 573703
.venv/bin/python -m rvt.manipulate samples/rmebasicsampleproject.rvt describe 581483
```
