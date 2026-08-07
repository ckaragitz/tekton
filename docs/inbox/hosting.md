# WALL-HOSTING stream — record

Charter: panels must arrive MOUNTED on walls (face-hosted), not
free-standing. Model documented + H1 written & self-verified => DONE met;
H2 (created-wall case) also achieved, with H3 as its control.

## What was cracked (spec: `docs/writer/hosting.md`)

- Panels are hosted on a **SketchPlane**, never directly on the wall
  (`FamilyInstance.m_hostId = SketchPlane`, `m_workPlaneBased = true`,
  `m_assocLevelId = -1`, `m_scheduleOnlyLevelId = level`).
- The SketchPlane binds to the wall FACE via `m_oPlaneRef =
  GeomOnPlaneRef{ m_geomRef = { m_elemId: WALL, m_geomTag: FACE_TAG,
  m_subTag: -1 } }`. The face reference is a **small stable geometry tag,
  NOT a GUID/topological tag**: `5` = the -leftNormal side face (right of
  the drawing direction = interior for an unflipped wall), `6` = the
  +leftNormal side (exterior). Proven on 10 planes over 3 wall types, and
  on the wall solids' own face tags (`Face.m_GInfo.m_tag` 5/6 = the two
  sides, 7 bottom, 14 top). Corrects mutation-plan §6.3 (which guessed a
  face-tag GeomRef but had only the catalogued specimen 581481 — a
  reference-less DummyPlaneRef, the OTHER real pattern: 218/240 hosting
  planes reference nothing and are merely coincident with the face).
- The plane frame `m_oTrf` (COLUMN-major 3x3): **Z = outward face normal,
  Y = world up, X = up × Z**, origin on the face at wall base z. This
  formula reproduces Autodesk's stored matrix byte-for-byte on ALL 10
  tag-5/6 planes (a row-major reading fails on walls running along -Y —
  the trap this stream avoided). A hosted instance's `InstanceInfo.m_Trf`
  3x3 is IDENTICAL to its plane's; its origin = the mounting point on the
  face.
- **Yes, the SketchPlane header lists the wall in `m_parents.m_deletion`**
  (`= [wall, self]`; `m_regenOnly = [wall_type]`); the hosted instance
  keeps the plane in ITS `m_deletion` and lists the WALL in `m_regenOnly`.

## Code

`src/rvt/hosting.py` — `wall_geometry`, `side_facing_point`,
`add_sketchplane_on_wall(doc, wall, side, at_point_ft, plane_ref="geom"|
"dummy")`, `host_instance_on_wall(doc, symbol_id, wall, distance_along_ft,
elevation_ft, side, ...) -> [sketchplane_el, instance_el]`. `wall` may be
an existing element id OR a wall planned in the same run (NewElement from
`Document.add_wall`). Does not touch mutate.py (uses
`Document.add_family_instance(host_id=...)` + Document internals). 15 tests
in `tests/test_hosting.py` (model proofs against the corpus + API +
one slow commit round-trip), all passing. Full suite: see report.

Integration hint for the pipeline: in `tools/spec_to_rvt.py`, replace the
`hosting == "free"` panelboard branch with
`hosting.host_instance_on_wall(doc, sym, wall=<the room wall the panel
sits on>, distance_along_ft=..., elevation_ft=..., side=
hosting.side_facing_point(doc, wall, room_centroid))` — the wall may be
one just created from the same spec. `spec_to_rvt.py` is outside this
stream's territory, so this is a proposal, not an edit.

## Test files for the acceptance viewer (`experiments/hosting/`)

- `H1_panel_on_existing_wall.rvt` — new SketchPlane 888014
  (GeomOnPlaneRef -> EXISTING wall 573608, tag 6 = the face that looks into
  electrical room 573809, right where the sample's own panels 581482-85
  hang) + new 480 V panelboard 888015 (symbol 619617, "480V MCB Surface
  400 A") hosted on it; 6 ft along the wall, 4 ft above Level 1.
  PROVES: SketchPlane authoring + real face reference + hosted instance.
- `H2_panel_on_created_wall.rvt` — new interior partition 888014 (type
  563416, inside room 573809, x=64.5, y 118->106, 8 ft high) + SketchPlane
  888015 (GeomOnPlaneRef -> the NEW wall, tag 5 = the face looking back at
  the existing panels) + hosted panel 888016. The electrical-room-from-
  scratch case. Face-refs into a NOT-YET-REGENERATED wall are the one
  thing the corpus cannot prove — the viewer decides.
- `H3_panel_on_created_wall_dummyplane.rvt` — identical to H2 but the
  plane is a DummyPlaneRef coincident with the new wall's face (no
  reference into the wall). The regeneration-independent fallback and the
  control for H2 (see the verdict matrix in docs/writer/hosting.md §7).
- `manifest.json` — verify_written report per file: CRC 0 / ECC 0 /
  walker 0 / stamps ok / all new records decode clean in seq 101/102/103 /
  ElemTable count == partition header count / sentinels last, plus a
  decode-readback proving `m_hostId`, `m_workPlaneBased`, the
  GeomOnPlaneRef `{elemId, tag}` and the frames landed on disk.
  ALL OK. Rebuild with `.venv/bin/python experiments/hosting/make_hosting.py`.

## Recommendation

For panels on EXISTING template walls use `plane_ref="geom"` (real
association — Revit reports the wall as host, moving the wall carries the
panels). For panels on walls CREATED in the same run, `geom` is written the
same way (H2); if the viewer rejects it, switch created-wall hosting to
`plane_ref="dummy"` (H3) — the panel is still flush-mounted on the face,
merely "<not associated>". Either way no panel is ever free-standing.

## Open

1. H2 vs H3 acceptance run resolves whether face-refs into created walls
   survive regeneration ordering (the sole honest blocker; recipe + control
   both delivered).
2. `[hypothesis]` a flipped wall (`m_isFlipped=true`, none in corpus) swaps
   tag 5/6; `side_facing_point` sidesteps this by resolving the face
   geometrically from a point in the room.
3. Non-basic walls (curtain / edited profile) unproven — only basic
   straight walls (what `add_wall` makes) are covered.

BRANCH STATE: hosting stream complete — src/rvt/hosting.py + tests/test_hosting.py (15 pass) + docs/writer/hosting.md + experiments/hosting/{H1,H2,H3}.rvt written and self-verified (manifest.json ALL OK); no other stream's files touched; ready for orchestrator viewer upload (H1 primary, H2 test, H3 control).
