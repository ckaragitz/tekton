# inbox — family-geometry (parametric geometry generators)

Stream: FAMILY GEOMETRY GENERATORS, 2026-08-03 (two passes: box + cylinder).
Territory touched: `src/rvt/famgen/geometry.py` (sibling module of the
existing `rvt.famgen` package — its `__init__.py` / `catalog.py` /
`skeleton.py` / `factory.py` untouched), `tests/test_famgen_geometry.py`
(19 pass), `experiments/families/genesis/G_*` (`G_box_solid.rfa`,
`G_box_dummy.rfa`, `G_cyl_solid.rfa`, `G_cyl_dummy.rfa`, `G_report.json`,
opportunistic `G_box_on_S0.rfa`), `docs/writer/family-geometry.md` (the
spec: layouts, tables, evidence, unknowns), this note. NO edits to any
existing `src/rvt/*.py`, `genesis/*`, other tests, tools, KNOWLEDGE or
TRACKER (genesis skeleton / types / families / encode / partitions /
commit only imported).

## Findings (evidence in docs/writer/family-geometry.md + G_report.json)

- **A family FORM = the element cluster** built from parameters:
  SketchPlane (on the 'Ref. Level' datum), VarSketch (drawn profile),
  the profile's model CurveElems (OST_Lines), ExtrusionElem (start/end
  offsets −1001800/−1001801, traced loop copy, geometry-history tag map)
  [V, three specimen clusters]. Every element is constructed FIELD BY
  FIELD (no cloned payload) in the SkelElement record shape shared with
  rvt.genesis. Box = 7 elements; circle-profile cylinder = 5 (2 half-arc
  CurveElems joined to each other at both ends).
- **The box B-rep is a fixed topology template** [V]: 2 caps + 4 sides,
  12 edges, EdgeLoop/Plane per face, formulaic pids and history tags,
  per-face uv coedges. `solid_box_brep(vertices, start, end)` rebuilds
  BOTH Autodesk box solids (rme unit 243, 786837 & 786867) from their
  dimensions: 533/533 leaves structurally exact (modulo one volatile
  GInfo bit that differs between the two specimens themselves), max
  float dev 1e-13, byte-identical after snapping floats at 1e-9.
- **The CYLINDER B-rep is now DONE and proven the same way** [V]:
  `solid_cylinder_brep(circles, start, end)` — 2 planar caps (one
  EdgeLoop per circle CHAINED by m_nextLoop), 2 CylSurf half-cylinder
  faces per circle, 6 edges per circle (4 curved rails with a
  deterministic 7-chord / 6-chord interior tessellation, 2 straight seams
  with GInfo flags 557796), extrude-UP frame, TOP cap serialized first,
  bbox from the tessellation nodes. `reproduce_specimen_cylinders` rebuilds
  the sample .rfa's 4-leg extrusion 614 (10 faces / 24 edges / 16 loops)
  from its four circles + offsets: **1,421 leaves structurally exact, 678
  geometric floats exact (max 1.5e-14, incl. every curved-edge interior
  point), only the 104 cap/loop envelope corners differ by ≤1.17e-4 ft**
  — Revit computes envelopes from a finer display tessellation than the
  stored edge points (a cache class, like the box's volatile bit).
- **How Revit draws/traces a circle** [V]: two half arcs (U = [0,π]
  drawn first, L = [−π,0]); the tracer walks (L, U); frame vertices
  V1 = θ=0 point, V0 = θ=π point; history tags per circle = the box
  formula with n=2 (base 2+8j clean; specimen 614 carries editing-history
  bases 114/122/130/138 — deleted attempts keep tag reservations).
- **Arc CurveElem anatomy** [V rfa 3736]: driver GArc + `m_oArcCntr`
  centre-marker GLine (tag 1) + `ArcElemCell` + 2 curve hists + 2-entry
  GeomTable; joins end0↔partner end1. Header fidelity fixes applied to
  BOTH shapes: CurveElem `m_miscId` = its sketch id and
  `m_hasNonDetermRegenChildren = true` (both specimen documents); the
  standalone-.rfa flavour also carries header bboxes on VarSketch /
  CurveElem / ExtrusionElem (added).
- **Two solid-graphics facts**: `Geometry.m_flags` = 7 on the two
  all-planar box specimens and 6 on both rfa solids with curved faces
  (fillet top 82, legs 614) [V observed, H semantics]; the donor's
  `tessEpsCntrl` version (0 rfa / 1 rme) is now read into the context and
  matched. Material surface FILLINGS (`GFilling` per face, render style =
  the material) are pattern-cache state (CylSurf placer floats are not
  derivable); our forms carry none, exactly like both ACCEPTED box
  specimens — `_strip_fillings` + `renumber_pids` (pid renumbering with
  weakref remapping) canonicalize the specimen for comparison.
- **Archive pid numbering SOLVED** [V]: `assign_pids` reproduces the
  pointer index of every object in 6,296/6,296 specimen records; new this
  pass: `renumber_pids` (edit a graph, renumber, remap weakrefs) and a
  symbolic-weakref graph builder (`_number_graph`) used by the multi-loop
  cylinder constructor. General enablers for authoring any object graph —
  they belong in `rvt.encode` eventually (see requests).
- **Writer counter defect fixed**: `emit_form_rfa` computed the touched
  blocks' C counter with the 12/16-byte record-header convention; the
  validator's identity (`ISIZE == hdr_len(seq)*A + C + adj`, 16/20-byte
  headers, as `rvt.commit` now uses) flagged 3 blocks (a WARNING the donor
  does not carry). Fixed; emitted files now validate with **0 warnings**.
- **Four proof families built + self-verified** [V mechanism, H
  acceptance]: `G_box_solid/dummy.rfa` (500×300×700 mm cabinet) and
  `G_cyl_solid/dummy.rfa` (6 in × 190 mm recessed can) = the sample .rfa +
  our form; `emit_form_rfa` splices records + ElemTable rows + header
  count exactly like the accepted project commit (V20). Read-back: 0 gzip
  CRC failures, 0 ECC mismatches, walker clean, every element decodes,
  donor ids preserved, VALIDATOR PARITY (the untouched Autodesk sample
  itself reports 5 family-file errors — validator gaps; our files add
  none and now carry 0 warnings).
- **ElemTable family-file graveyard tail DECODED** [V structure] (first
  pass): `.rfa` ElemTables end with `u32 count | count×32 B GraveyardRec |
  20-byte footer` — the cause of one of the validator's baseline
  family-file errors; my appender preserves it verbatim.
- Composition with the genesis family skeleton works (opportunistic,
  first pass): `G_box_on_S0.rfa` = the family-skeleton stream's
  from-scratch `S0_empty_family.rfa` + our box (CRC/ECC/decode clean).
- The parametric hooks (labeled dimension = `LinearDimString` segment
  `m_ArrSegInfo[].m_paramId` = the ParamElemFamily id, witnesses =
  `GeomSegInPlaneRef` to the solid's face tag + a RefPlane) remain a
  DECODED recipe (spec §5); tonight's geometry is fixed-dimension (the
  generator regenerates the cluster for a new size).

## Honest status vs DONE

- box / plate / cylinder generators + `solid_box_brep` +
  `solid_cylinder_brep` + all four proof variants validating (parity, 0
  warnings) + BOTH topology reproductions (2 box specimens + the 4-leg
  cylinder specimen): **DONE**.
- "0 validator errors" is not attainable for ANY .rfa today: the untouched
  Autodesk sample reports 5 family-file gaps that belong to the `validate`
  / `stream_encoders` streams (PartAtom framing, missing
  ProjectInformation, family ElemTable graveyard, DIT layout). The achieved
  and tested gate is PARITY with the donor + zero warnings.
- parametric hooks: recipe documented with specimen evidence (deferred,
  as the brief allows).

## Requests for the orchestrator

1. **ACCEPTANCE-TEST** all four proof files in
   `experiments/families/genesis/`: `G_box_solid.rfa`, `G_box_dummy.rfa`,
   `G_cyl_solid.rfa`, `G_cyl_dummy.rfa` (Revit family editor / APS
   translator). Expectation: the 'table end' family opens and now also
   shows (box files) a 500×300×700 mm cabinet 3 m from the origin, (cyl
   files) a 6 in-dia × 190 mm cylinder at (3 m, 1 m); their sketch curves
   appear on the Ref. Level plan. Each solid/dummy PAIR answers F4: solid
   only → we must author solids; dummy also → Revit regenerates forms.
   Then `G_box_on_S0.rfa` (our document + our form).
2. `rvt.validate` / `stream_encoders.decode_elemtable` could adopt the
   family-file conventions (the `.rfa` ElemTable graveyard layout is
   documented in the spec §7) — removes the 5 baseline family-file
   validator errors so ".rfa validates with 0 errors" becomes achievable.
3. `assign_pids`, `renumber_pids`, the REGISTERED class set and the
   symbolic-weakref graph builder are format-generic; suggest promoting
   them into `rvt.encode` (the encoder needs given pids today).
4. Plugin drift: `tests/test_plugin_sync.py` fails because the plugin
   bundle predates this pass (my module is among the drifted files) —
   run `tools/sync_plugin.py` once this tick's streams are integrated.

## Verification

- `.venv/bin/python -m pytest tests/test_famgen_geometry.py -q` →
  **19 passed** (3.3 s): tag formulas (box + circle), pid mimic over
  1,000+ donor records, box B-rep structure + BOTH specimen boxes
  reproduced from dimensions (exact / canonical byte-exact), cylinder
  B-rep structure + the 7/6-chord tessellation rule + the 4-leg specimen
  cylinder reproduced from dimensions, bundle schema round-trips (box
  solid+dummy, plate, polygonal cylinder, true cylinder solid+dummy),
  emit + read-back for both shapes (counts, ElemTable/watermark, graveyard
  preserved, our solid decodes with the right face/surface kinds),
  validator parity for both.
- `.venv/bin/python -m rvt.famgen.geometry` regenerates both topology
  proofs + all four `.rfa` files + `G_report.json` (~15 s).
- Full suite (`pytest tests/ -q --ignore=tests/oracle`): **631 passed,
  3 failed** — none in this territory: (a) `test_plugin_sync` = the
  expected plugin drift (request 4), (b/c) two `tests/test_provenance.py`
  G0 tests belonging to the parallel provenance / genesis streams (they
  import `rvt.provenance` / `experiments/genesis/G0.rvt`, not famgen).

BRANCH STATE: no git repo (working tree); deliverables complete —
src/rvt/famgen/geometry.py (box/plate/cylinder generators, solid_box_brep,
solid_cylinder_brep, assign_pids/renumber_pids, FormBundle, emit_form_rfa
+ verify_emitted + validate_parity, reproduce_specimen_solid,
reproduce_specimen_cylinders), tests/test_famgen_geometry.py (19 pass),
docs/writer/family-geometry.md (spec, §4 cylinder done), experiments/
families/genesis/{G_box_solid, G_box_dummy, G_cyl_solid, G_cyl_dummy,
G_box_on_S0}.rfa + G_report.json; READY — the four G_* files await the
Revit / viewer acceptance gate (the F4 solid-vs-regeneration question);
next code step after acceptance = the labeled-dimension parametric
constructor (spec §5).
