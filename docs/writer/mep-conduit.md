# Conduit + cable tray — linear MEP curves (MEP stream: conduit)

Module: `src/rvt/mep/conduit.py`. Tests: `tests/test_mep_conduit.py` (12).
Proof harness: `experiments/mep/conduit/make_conduit.py` → five proof files +
`manifest.json`. Ground truth: `samples/rmebasicsampleproject.rvt` (Revit
2026) — 20 `RbsConduitCurve` in 8 `ConduitRun`s joined by 13 elbow
`FamilyInstance`s, every curve owning a `SegmentCenterLine`, every elbow a
`ConduitFittingCenterLine`.
Confidence tags: **[V]** verified byte-for-byte / on every corpus specimen,
**[H]** hypothesis (needs Autodesk acceptance), **[D]** design decision.

## 0 · TL;DR

The conduit "run" a contractor draws is FIVE cooperating element kinds,
all decoded and all writable:

| kind | class (id) | category | rep (seq 103) | owner |
|---|---|---|---|---|
| straight segment | `RbsConduitCurve` 0x0d63 | −2008132 `OST_Conduit` | `GElement` (extrusion solid) | — |
| elbow fitting | `FamilyInstance` 0x07c5 | −2008128 `OST_ConduitFitting` | `GElement` (GInstance → shared symbol clone) | — |
| run (path) | `ConduitRun` 0x0368 | −2008149 | `SerializedDummy` | its FIRST conduit |
| segment centre-line | `SegmentCenterLine` 0x0f20 | −2008139 | `GElement` (2 GPoints = bbox corners) | its conduit |
| fitting centre-line | `ConduitFittingCenterLine` 0x0366 | −2008141 | `GElement` (2 GPoints) | its elbow |

CREATE = clone real specimens of each kind and patch a small enumerated
field set (§4); the connector graph is authored MUTUAL (§3). MODIFY /
MOVE / DELETE ride on `rvt.manipulate` with conduit-aware plan builders
(§6). Every proof file passes `tools/rvt_validate.py` with ZERO errors and
the structural verifiers (`verify_written` / `verify_manipulated`) — see the
cell table in `docs/inbox/mep-conduit.md`.

Cable trays share the ENTIRE `RbsCurve` chain with conduits (schema §7) but
have **no specimen in any 2026 sample**; they are synthesised by class
morphing a conduit and are structurally valid but Autodesk-unproven [H].

## 1 · The conduit curve (`RbsConduitCurve`, seq 102) — decoded

Class chain [V, `Formats/Latest`]: `Element` (20) → `HostObj`
(`m_hostObjMiscData, m_oGeomToElemMap, m_roomBounding`) → `RbsCurve` (15)
→ `RbsSingleCurve` → `LineAndArcRunMember` (`m_lineAndArcRunId`) →
`RbsCableTrayConduitBase` (`m_runId`) → `RbsConduitCurve`
(`m_pDesignPropManager`).

| field | value / rule | evidence |
|---|---|---|
| `m_assocLevelId` | the reference level (rme: 378117 'Level 1', z 0.309) | 20/20 |
| `m_pConnectorManager` | `RbsCurveConnectorManager` with exactly TWO `Connector`s, `m_nIndex` 0 (start) / 1 (end); modifier `SegmentConnectorPosition.m_paramOnCurve` = 0.0 / 1.0; `SegmentConnectorCalculation` all zero (unassigned) | 20/20 |
| `m_pCurveDriver` | `RbsCurveDriver{m_pCrv: GLine{m_origin, m_dirVec (unit), m_endParams [t0,t1]}}` — endpoints `p_i = origin + dirVec·t_i` (feet, WORLD coords); joins/mid-params empty | 20/20 |
| `m_dWidthOrDiameter` / `m_dHeight` | NOMINAL trade size in feet (2" = 0.16667), both equal for round conduit | 20/20 |
| `m_vNormal` | a unit vector ⟂ the axis: world +Z for the 17 non-vertical conduits, a horizontal perpendicular for the 3 risers | 20/20 |
| **`m_dOffsetStart` / `m_dOffsetEnd`** | **`endpoint.z − level.z`** (feet) — exact on every conduit (residual 0.0) | 20/20 |
| `m_idType` | `RbsConduitType` (all 20 use 662478 'RNC Sch 80', standard 638844) | 20/20 |
| `m_idSystemCategory` / `m_idSegment` | −1 / −1 | 20/20 |
| `m_eHorOffset` / `m_eVertOffset` / `m_iEndReference` | 0 / 0 / 0 (centre justification) | 20/20 |
| `m_runId` | its `ConduitRun` — EVERY conduit is in a run | 20/20 |
| `m_lineAndArcRunId` | −1 | 20/20 |
| `m_pDesignPropManager` | `ConduitDomainDesignPropertyManager{m_idCenterLine (its SegmentCenterLine), m_dInnerDiameter, m_dOuterDiameter, m_sCalculatedSize ('51 mmø')}` | 20/20 |

Inner/outer diameters and the elbow bend radius all come from the
project's `ConduitSizesElem.m_sizes` (container of `pair<ConduitStandardType,
ConduitSizeSet>`), keyed by the type's `m_idStandardType`. RNC Sch 80, 2":
inner 1.939", outer 2.375", **bend radius 0.890625 ft** — the exact
`GArc.m_radius` of every corpus elbow.

Header (`ElementHeader`, seq 101) [V]: `m_categroryId` −2008132; `m_pBBox`
= the axis segment inflated by outer-diameter/2; `m_parents.m_deletion` =
{phase, level, type, self, run, its centre-line, connected fittings /
equipment}; `m_regenOnly` = {UnitsElem 19236, GStyleElem 638782 (the
Conduits object style), ConduitSizesElem 638845, ConduitSettingsElem
638851}; `m_appearanceParents` = {level, GStyle, type};
`m_deferredParents` = {712554 MEPSystemTracker}.

## 2 · The elbow fitting = a flexible-family instance with a SHARED clone

An elbow is an ordinary level-based `FamilyInstance` (host −1,
`m_workPlaneBased` false, `m_assocLevelId` = the level, category
−2008128), NOT a special class. The Revit "flexible fitting" mechanism [V]:

* `m_masterSymbolId` = the real type (662459 'Conduit Elbow: Standard',
  family 668501) = the run type's `RbsConduitType.m_idDefaultElbow`.
* `InstanceInfo.m_symbolId` = an ANONYMOUS per-CONFIGURATION
  `FamilySymbol` clone (679082, ElemTable owner INVALID). All **twelve** 2"
  90° elbows in the file share this ONE clone — the configuration (size,
  angle, radius) compiled by Revit's regenerator. ⇒ a new 2" 90° elbow
  REUSES clone 679082 (the same "reuse an existing cut/geometry clone"
  recipe as doors). A configuration with no clone in the file cannot be
  minted offline (the clone is regenerator output) — `find_elbow_specimen`
  returns None and the corner is left as an open butt joint.
* Instance params `m_pInstParams` (family params 669197…669210): nominal
  diameters (0.16667), OD (0.19792), radius (0.09896), bend radius
  0.890625 (also on BIP −1140116), angle 669202 = 1.5708 rad,
  centre-to-end 669201 = **1.0573 = bendRadius + straightExtension
  (0.16667 = the nominal size)** — cloned wholesale with the specimen.
* Connectors 1 and 2 (`FamilyInstanceConnectorManager`, one ref each,
  `connType 1`); design props `FamInstDesignPropertyManager{m_idCenterLine =
  its ConduitFittingCenterLine, m_sCalculatedSize '51 mmø-51 mmø'}`.

### 2.1 The elbow frame — EXACT [V, all 13 corpus fittings, error < 1e-13]

Let `A` = the conduit on connector 1 and `B` = the conduit on connector 2,
`A_end` / `B_end` their endpoints at the corner, `C` = the intersection of
the two axes (each leg is trimmed back from `C` by exactly
`bendRadius + extension` = 1.0573 ft for 2"):

```
X = unit(C − A_end)      # along leg A, pointing INTO the corner
Y = unit(B_end − C)      # along leg B, pointing AWAY from the corner
Z = X × Y
InstanceInfo.m_Trf.m_or  = C                    (world)
m_instOrigin             = C − (0, 0, level.z)  (level-local mirror)
m_3x3 columns = [X, Y, Z]  ;  m_RefDir = X ;  m_zAxis = Z
```

(`tests/test_mep_conduit.py::test_elbow_frame_formula_reproduces_every_real_elbow`
recomputes this from the raw records and matches the stored `m_3x3` to
1e-9 on every specimen, and the trim = R + ext on every 2" elbow.)

The `ConduitFittingCenterLine.m_CenterCurves` follow directly:
`GLine{origin = C − X·R, dirVec = X, endParams [−ext, 0]}` (leg-A
extension), `GArc{center = C − X·R + Y·R, xVec = −Y, yVec = X, radius R,
endParams [0, π/2]}`, `GLine{origin = B_end, dirVec = Y, endParams
[−ext, 0]}` (leg-B extension). The seq-103 rep of the instance is the small
formulaic `GElement{GGroup, GInstance{InstanceInfo{same Trf, symbolId =
clone}}}` (330 B) — cloned with the transform, tag and boxes rewritten.

## 3 · The connector graph (what "connected" means on disk) [V]

`Connector.m_arrRefs[]` entries are `{m_id, m_nIndex, m_connType}` where
**`m_connType` is the TARGET connector's Revit `ConnectorType`**: 1 = End
(curve / fitting ends), 4 = Logical (circuits — see the electrical stream),
16 = Surface (equipment taps: transformer 624416 connectors 2001/2002,
panelboard 630241 connectors 3001–3003, panels' 5001).

* curve end `i` refs: `[{self, 1−i, 1}]` (its own opposite end — the
  logical link along the segment, 15/20 conduits) `+ [{neighbour, its
  connector index, 1 or 16}]`; an OPEN end keeps just the self link (or is
  empty).
* elbow connector 1 refs `[{A, A's index at the corner, 1}]`, connector 2
  refs `[{B, B's index, 1}]`; the conduits reciprocate (`{elbow, 1 or 2, 1}`).
  In every run the elbow's connector 2 faces the PREVIOUS member and
  connector 1 the NEXT one — the writer mirrors this.
* `ConduitRun.m_elemIdArr` = the ordered path `[conduit, elbow, conduit,
  …]` (run 679090 = [687998, 688027, 679071, 688029, 678659]); `m_typeId` =
  the conduit type; ElemTable owner = its first conduit; rep =
  `SerializedDummy`; header `m_deletion` = {phase, type, self, every
  member}; `m_hasNonDetermRegenChildren` true.

`verify_plan_graph()` / `readback_run()` prove reciprocity on plans and
on written files respectively.

## 4 · The CREATE recipe (`add_conduit_path`, `add_conduit_run`)

Element ids: `run, then per segment (conduit, centre-line), per corner
(elbow, fitting-centre-line)`, all `watermark + 1…`. Every object is a
`deepcopy` of a real specimen with these patches:

| element | patched fields |
|---|---|
| conduit | `m_id`, `m_assocLevelId`, phase, GLine (`origin=p0, dirVec, endParams [0,L]`), `m_dWidthOrDiameter/m_dHeight` (nominal), `m_vNormal`, `m_dOffsetStart/End = z − level.z`, `m_idType`, `m_runId`, both connectors' `m_arrRefs` (+ zeroed calculation modifiers), design props `m_idCenterLine / inner / outer / label`, Mark blanked; header bbox = segment ± OD/2, `m_deletion` = {level, type, self, run, centre-line, neighbours, phase}, `m_appearanceParents` = {level, GStyle(−2008132), type} |
| segment centre-line | `m_id`, `m_OwnerId` = conduit, `m_CenterCurves = [GLine(p0→p1)]`; header category −2008139, bbox, `m_deletion` = {phase, owner, self}, `m_regenOnly` = [level]; rep = 2 GPoints at bbox max/min; **ElemTable owner = conduit** |
| run | `m_id`, `m_typeId`, `m_elemIdArr` (path order); header category −2008149, bbox null, `m_deletion` = {phase, type, self, members}; rep dummy; **ElemTable owner = first conduit** |
| elbow | identity, `m_assocLevelId`, `m_instOrigin`, `m_RefDir/m_zAxis`, `InstanceInfo{m_symbolId = clone, m_Trf}` (§2.1), connectors 1/2 → legs A/B, `m_pDesignPropManager.m_idCenterLine`, Mark blanked; header bbox, `m_deletion` = donor's global parents (family params, master, clone) + {self, its centre-line, A, B, level, phase} (the DONOR's own neighbours/centre-line removed) |
| fitting centre-line | as segment centre-line but `m_CenterCurves = [GLine, GArc, GLine]` (§2.1), category −2008141 |

Corner joint conditions [D]: legs perpendicular (|dot| < 0.035) and each leg
longer than 2× the trim; otherwise the segments meet as an open butt joint
inside the same run (`require_elbows=True` raises instead).

## 5 · Writing (`commit_created`) [V structure]

The commit is `rvt.commit.commit_new_elements`' splice (records inserted
before each unit-0 sentinel, ElemTable rows appended id-sorted, header
count, CRCIO ECC, CFB) with two corrections this stream needed:

1. **ElemTable owners are kept** (a curve owns its centre-line and its
   run) — the generic path drops `owner_id` (see inbox: 3-line diff for
   `commit.py`).
2. **The block-counter identity** the validator checks is
   `ISIZE == hdr_len(seq)·A + C + adj` with the WAVE-1 header lengths
   16 (seq 101) / 20 (seq 102/103); the generic splice recomputes `C` with
   12/16 and leaves the touched blocks' `C` too large by `4·A` (the
   validator's "counter defect" warning on H1 and every hosting file).
   `commit_created` uses 16/20 → the warning is gone on our files.
3. `BasicFileInfo` keeps the EXISTING document GUID (== `History` entry 0)
   while the provenance strings are scrubbed — a minimal commit records no
   new History episode, so a fresh GUID would break the History-coherence
   invariant the validator (correctly) enforces.

## 6 · MODIFY / MOVE / DELETE (existing runs) — plans for `rvt.manipulate`

| verb | what changes |
|---|---|
| `resize_run(id, nominal_ft)` | every curve in the run: `m_dWidthOrDiameter`, `m_dHeight`, design props inner/outer (from the size table) + label ('25 mmø'), header bbox re-inflated. Fittings keep their compiled clone [D] — Revit re-solves them on regeneration |
| `move_run(id, dxyz)` | curves: GLine origin, both level offsets (dz), header bbox; centre-lines: curves, GPoint rep, bboxes; fittings: `manipulate.move_instance` (Trf.or, instOrigin, rep transforms, bbox) — the whole run rigidly |
| `extend_run(curve, delta, end)` | one OPEN end only (a jointed end is refused): GLine origin/dir/params, the moved end's level offset, header bbox, its centre-line |
| `retype_run(id, type)` | `m_idType` on every curve + design props inner/outer per the new standard, `ConduitRun.m_typeId`, header parents old-type → new-type |
| `delete_run(id)` | closure = run + members + their owned centre-lines; `manipulate.delete_element(cascade=True)` per element; referrers neutralised: equipment surface connectors that tapped a deleted conduit (transformer 624416), neighbouring runs, the run member list |
| `delete_fitting(id)` | the elbow + its centre-line; the two conduits' connector refs dropped (two open ends in one run) and the run's `m_elemIdArr` entry removed |
| `delete_conduit(id)` | one curve + its centre-line (+ the run if that curve owns it); prefer `delete_run` |

The referrer/dependent semantics are `rvt.manipulate`'s (see
`docs/writer/manipulation.md`): ownership via `ElemRec.m_OwningElementId`
(centre-lines, runs), connector `m_arrRefs` entries dropped, `m_runId`
scalars → −1, `m_deletion` list mentions removed. Deletion never re-encodes
the target, so even the ES-blob fittings the modify path refuses stay
deletable.

## 7 · Cable trays — EXPERIMENTAL SYNTHESIS [H]

`CableTray` (0x02b6) vs `RbsConduitCurve` (0x0d63): identical from
`Element` up through `RbsCableTrayConduitBase`; ONLY the leaf differs:

| CableTray leaf field | kind | written value |
|---|---|---|
| `m_calculatedSize` | AString | e.g. `'305 mmx102 mm'` (cosmetic label) |
| `m_oDesignPropManager` | owned `CableTrayDomainDesignPropertyManager` (whose only field is the inherited `m_idCenterLine`) | `{m_idCenterLine: its SegmentCenterLine}` |
| `m_rungSpace` | double (ft) | 0.75 |

The synthesis (`add_cable_tray_run`) deep-copies a conduit specimen,
drops `m_pDesignPropManager`, adds the three leaf fields, swaps
`ConduitExtrusionGStep → CableTrayExtrusionGStep` (field-identical
GeomStep), sets rectangular `m_dWidthOrDiameter = width` / `m_dHeight =
height` / `m_vNormal = +Z`, `m_idType` = an `RbsCableTrayType` (7 exist:
Channel / Ladder / Wire Mesh / Solid Bottom / Trough / Single Rail),
header category −2008130 [V from the tray types] with cable-tray regen
parents (GStyle 638780, CableTraySizesElem, CableTraySettingsElem), a
`CableTrayRun` (0x02c2, same layout as `ConduitRun`) and a
`SegmentCenterLine`. No fittings (a tray elbow needs a compiled geometry
clone; the loaded tray-elbow master 662384 has NO instance/clone in the
file).

Category ids that no specimen can confirm — inferred from the +2
conduit↔cable-tray interleave that IS confirmed (curve −2008132/−2008130,
fitting −2008128/−2008126) and the Revit API enum: `OST_CableTrayRun =
−2008147` [H], `OST_CableTrayCenterLine = −2008137` [H]. A GStyleElem
exists in the file for both ids, so they are real categories; whether they
are the RIGHT ones is exactly what viewer acceptance of
`cable_tray_create.rvt` tests. Everything else about the tray file is the
proven conduit pipeline.

## 8 · Confidence / unknowns

| claim | status |
|---|---|
| conduit / run / centre-line / elbow object recipes (§1–4) | **V** structurally (byte-exact specimens, validator + verifiers clean); creation from real clones |
| elbow frame formula, trim = R + ext, shared clone reuse | **V** (13/13 fittings, 1e-13) |
| connector-type semantics (1 End / 4 Logical / 16 Surface) and the self opposite-end link | **V** pattern; the self link is present on 15/20 conduits — we always write it [D] |
| Autodesk regenerates the created conduits' solids from the GStep recipe with a `SerializedDummy` seq-103 rep | **H** — the same regeneration path the ACCEPTED created walls (V25/V26) used; every corpus conduit does carry a cached GElement |
| a run with butt-jointed segments (no elbow) opens | **H** |
| elbow record shape as authored (clone Trf, connectors, params) is accepted | **H** — the acceptance-critical test in `conduit_create.rvt` |
| resize without re-solving fittings; move/extend/retype field sets suffice | **H** (same field families the accepted create/manipulate paths write) |
| deletes leave the model referentially clean (equipment tap freed, run list trimmed) | **V** decode-side / **H** Revit-side |
| cable-tray synthesis + inferred run/centre-line categories | **H — experimental** |

Unknowns / open items: **U1** whether Revit demands the conduit's cached
extrusion solid (fallback = clone-and-stretch the donor GElement — not
implemented, the BRep has 6 faces/edge loops); **U2** the meaning of the
inconsistent self opposite-end link (present 15/20, absent on 5 conduits
that terminate on equipment); **U3** `MEPSystemTracker` (712554, all its
queues empty at save time) — untouched; **U4** connecting a created conduit
to EXISTING equipment surface connectors (needs an in-place record edit of
the equipment — phase 2; created runs have open ends); **U5** non-90°
elbows / tees / crosses / unions (types name default symbols 662467 tee,
662463 cross, 673823 union — no instances in the sample); **U6** the true
`OST_CableTrayRun` / `OST_CableTrayCenterLine` ids and the tray
`m_calculatedSize` label format.

## 9 · Reproduction

```
.venv/bin/python -m rvt.mep.conduit samples/rmebasicsampleproject.rvt   # run inventory
.venv/bin/python experiments/mep/conduit/make_conduit.py                  # 5 proof files + manifest.json
.venv/bin/python -m pytest tests/test_mep_conduit.py -q                    # 12 passed
.venv/bin/python tools/rvt_validate.py experiments/mep/conduit/*.rvt       # zero errors each
```
