# genesis-residue-B — RESIDUE CONSTRUCTORS, GROUP B (M..Z) + the Yn END-GAME (workstream record, 2026-08-04)

## CLAIM (read before you start, Group A)

**GROUP B owns every residue CLASS whose name sorts M..Z** (Yn.json residue
table, by class name — the buckets straddle the alphabet split, so the
claim is PER CLASS, not per bucket).  Group A owns A..L.  Claimed here (29
classes, **997** of Yn's 2,009 residue elements — verified against Y9 with
the ladder's landed-slot reports subtracted; `tests/test_residue_b.py::
test_group_b_owns_exactly_the_M_to_Z_residue_classes` pins it):

| class | Yn residue | Yn bucket | our rung |
|---|--:|---|---|
| ParamElemExternal | 466 | definitions-removal-candidate | ZB1_defs |
| ParamBinding | 209 | definitions-removal-candidate | ZB1_defs |
| ParamElemElectricalLoadClassification | 108 | definitions-removal-candidate | ZB1_defs |
| ParamElemProject | 8 | definitions-removal-candidate | ZB1_defs |
| RbsWireInsulationType | 26 | constructor-exists | ZB2_mepcat |
| RbsWireMaterialType | 4 | constructor-exists | ZB2_mepcat |
| RbsWireTemperatureRatingType | 3 | constructor-exists | ZB2_mepcat |
| RbsPipeScheduleType | 13 | constructor-partial | ZB2_mepcat |
| RbsPipeConnectionType | 8 | constructor-partial | ZB2_mepcat |
| RbsPipeMaterialType | 5 | constructor-partial | ZB2_mepcat |
| PipeSegment | 15 | constructor-partial | ZB2_mepcat |
| PenWidthTableElem | 8 | curtain-systems(no-constructor) — family-scoped | ZB3_pens |
| SectionAttributes | 10 | no-constructor | ZB4_annot |
| ViewportAttributes | 1 | no-constructor | ZB4_annot |
| MaterialElem | 10 | surplus-sample-instances | ZB5_palette |
| PropertySetElement | 28 | no-constructor | ZB5_palette |
| ParameterFilterElement | 7 | no-constructor | ZB6_filters |
| SunAnnotationElem | 3 | surplus-sample-instances | ZB7_machinery |
| NumberingSchema | 3 | no-constructor | ZB7_machinery |
| SlaveSymbolTrackerElem | 1 | curtain-systems(no-constructor) | ZB7_machinery |
| WorksharingViewModeSettings | 1 | surplus-sample-instances | ZB7_machinery |
| PrintSettings | 2 | surplus-sample-instances | ZB7_machinery |
| Viewer | 1 | surplus-sample-instances | ZB7_machinery |
| Viewport | 3 | surplus-sample-instances | ZB7_machinery |
| RefPlane | 21 | content-removal-candidate | ZB8_content |
| SketchPlane | 30 | content-removal-candidate | ZB8_content |
| RoomElem | 1 | content-removal-candidate | ZB8_content |
| RvtLinkSymbol | 1 | external-link-removal-candidate | ENDGAME: delete |
| RvtLinkInstance | 1 | external-link-removal-candidate | ENDGAME: delete |

Extra charge (this stream only): the residue END-GAME design —
`docs/writer/genesis-endgame.md` (the ordered path from Y9 to Yn = 0,
covering BOTH groups' residue and the ADD queue, with the atomicity rule
for the constellations that straddle the alphabet split).

## Result in one screen

**The whole Group-B residue is retired IN PLACE: 995 of its 997 elements
carry OUR constructors' objects in `ZB_deep.rvt` (= Y9 + 8 ZB rungs); the
remaining 2 are the linked-model pair, whose designed retirement is
DELETION.  17 files — the 8-rung cumulative chain, `ZB_deep`, 8
single-change probes — all validator-VALID (0 errors), structurally proven,
four-registry coherent, `Global/Latest` + `Global/ElemTable`
BYTE-IDENTICAL to the parent, nothing added or removed, byte-delta
assertion holding on every rung; the certified control `CTRL_Y9_base.rvt`
(md5-identical to Y9) is staged.**  Reproduce: `.venv/bin/python -m
rvt.genesis.residue_b` (~35 s; refuses an uncertified parent).

Base: `experiments/genesis/subst_k4/Y9.rvt` — viewer-CERTIFIED (ledger
`certified`: "*** THE DEEPEST RUNG LOADS ***", VERDICTS #17).  Every ZB
rung's declared base = Y9; the chain's intermediate files derive from the
previous ZB file (all VALID by the same laws).

| # | rung | what becomes OURS in place | landed | changed | byte-identical (reproduced machinery) | verdict |
|--:|---|---|--:|--:|--:|---|
| 1 | **ZB1_defs** | 466 shared params + 8 project params + 108 load-class params + 209 bindings | 791 | 583 | 208 (bindings) | VALID |
| 2 | **ZB2_mepcat** | wire materials/insulations/ratings + pipe schedules/connections/materials + 15 pipe segments | 74 | 40 | 34 (coinciding designations) | VALID |
| 3 | **ZB3_pens** | the 8 curtain-family pen tables (our ISO-128 series, family scope kept) | 8 | 8 | 0 | VALID |
| 4 | **ZB4_annot** | 10 section-mark types + 1 viewport-title type | 11 | 11 | 0 | VALID |
| 5 | **ZB5_palette** | 10 surplus materials + 17 structural + 11 thermal assets | 38 | 38 | 0 | VALID |
| 6 | **ZB6_filters** | 7 view filters | 7 | 7 | 0 | VALID |
| 7 | **ZB7_machinery** | 3 sun annotations + 3 numbering schemas + 1 slave tracker (REPRODUCED) + worksharing/print setups + drafting viewer/viewports | 14 | 6 | 8 | VALID |
| 8 | **ZB8_content** | 21 reference planes + 30 sketch planes + the room's identity | 52 | 31 | 21 (on-datum sketch planes) | VALID |
| — | **ZB_deep** | = ZB8 (the cumulative deep file): 995 Group-B elements OURS | — | — | — | VALID |
| P | **Z_defs .. Z_content** | 8 single-change probes, each = Y9 + ONE bucket | (as above) | | | 8 x VALID |

Independent arbiter (pasted, this session): `tools/rvt_validate.py --quiet
experiments/genesis/subst_k4/residue_b/*.rvt` -> 18 x `OK errors=0
warnings=1` (the warning = the standing Extensible-Storage decode gap on 1
DataStorage element, untouched).  ZB_deep re-census
(`residue_b/ZB_deep_census.json`): Group-B residue **2** elements —
`RvtLinkSymbol` 1, `RvtLinkInstance` 1 (the endgame's DELETE step 15).

**Upload order (`residue_b/probes.json:upload_order_bisection_first`,
control FIRST): ZB_deep, then Z_defs, Z_mepcat, Z_pens, Z_annot,
Z_palette, Z_filters, Z_machinery, Z_content (each Y9 + one bucket), then
the chain intermediates.  A ZB_deep PASS proves every Group-B constructor
in ONE verdict; a FAIL is bisected by the singles (the first single that
FAILS with the control PASSING convicts exactly that bucket).**

## The method (same physics as the Y-ladder; three new instruments)

Every rung is `substitute_elements` in place, one OUR-record per residue
slot of the same class (role correspondence: catalog symbols by
designation, filters / setups / planes by order, machinery by identity);
the Y-ladder's 1,333 landed slots (and each earlier ZB rung's) are
PROTECTED so nothing of ours is re-landed.  The rung's ONE variable is the
CONTENT of our objects at Autodesk's registrations; the record / row /
position / registry motion is zero and asserted (byte-delta table + parity
+ regdiff sample per report).  New instruments this stream added:

1. **The census** (`residue_b.census_class` + the cross-corpus run over Y9
   / K4 / all six samples): per class, which flattened fields are CONSTANT
   across every instance (format machinery or a shared registration) and
   which VARY (free values) — the honest boundary between 'ours to state'
   and 'reproduce'.  Result table = `GROUP_B_CENSUS` in the module +
   findings F1..F10 below.
2. **Machinery reproduction as an empty-bucket proof**: for classes whose
   census shows NO free value (SunAnnotationElem, NumberingSchema,
   SlaveSymbolTracker, ParamBinding, the drafting viewport), our
   constructor reproduces the object and the rung lands it; the byte-delta
   report then lists the slot as 'landed but byte-identical to the parent'
   — a machine-checked statement that there is NOTHING OF OURS TO REJECT.
   Verified: 208 bindings + 34 catalog symbols + 8 machinery + 21 sketch
   planes byte-identical.
3. **Value-anchored id-block decoding** (the two asset schemas): the
   structural asset's builtin-param ids were decoded EXACTLY through a
   Rosetta twin (material 509467 carries the same physical values twice —
   named inline PhysicalParamSet vs id-keyed ParamSet); the thermal asset's
   ids by UNIT MATCHING published constants over all 11 rst thermal assets
   (steel k 45.000 W/mK, rho 7,850 kg/m3, cp 480 J/kgK; copper 401 / 8,920
   / 385; aluminum 230 / 2,700 / 897 — textbook-exact).  See F6/F7.

## New findings (evidence [V] = verified this session — merge into KNOWLEDGE.md)

1. **Shared-parameter GUIDs are ADocument registry KEYS** [V]:
   `ADocument.m_pAppInfoManager->...->ExternalParamTracking.m_keyDataMap[*]`
   = 466 entries keyed by the shared parameter's GUID (`first.m_guidValue`),
   `second.m_paramId` = the ParamElemExternal id; ALL 791 definition
   elements have an ADocument registry surface (ParamBindingTracking by
   category, ProjectParamTracking id set, ElementTrackingData for the
   load-class params, and 102 shared REBAR parameters keyed a second time
   inside NumberingAppInfo's rebar-numbering `m_paramIdToRoundedDouble`).
   => an in-place rung must KEEP each slot's GUID; changing shared-parameter
   IDENTITY is a registry-rewrite (or deletion) rung, never an object swap
   (endgame §5).
2. **Zero value carriers for all 791 parameter definitions in the family-
   free base** [V]: no ParamValueSet entry anywhere references a definition
   id; the definitions layer is self-contained (bindings <-> params <->
   load classifications + 1 filter rule) — substitution AND deletion are
   both safe as far as VALUES go; deletion's only cost is dangling registry
   entries (tolerated per R5/R9).
3. **The local-parameter typeId grammar** [V]: shared params:
   `revit.local.shared:<GUID without dashes>-1.0.0` with GUID == the
   element's own m_externalParamKey (466/466); project / classification
   params: `revit.local.{project|classification}:<32-hex session GUID>
   <8-hex ELEMENT ID>-<version>` — the 8-hex suffix IS the element id
   (8/8 project, 108/108 classification), the 32-hex prefix a creation-
   session GUID (6 distinct across the 108 = created in 6 batches).
4. **The load-classification companion-parameter role table** [V, 108
   rows]: `m_eType` 0 est-load (apparentPower) / 1 est-current (current) /
   2 actual-space-load (apparentPower) / 3 demand-factor (demandFactor,
   the only read-only role) / 4 total-current / 5 total-load; 18 classes
   x 6 = 108, group `electricalLoads`.  Group A's ElectricalLoadClassification
   and our 6 companions per class point at each other by id and stay
   consistent BY CONSTRUCTION under in-place substitution on both sides.
5. **MEP catalog symbols carry `CellList{PatternHelper}` + a PRESENT
   empty AString param set** [V, 26/26 wire insulation, 13/13 pipe
   schedules, 5/5 pipe materials — `types.new_wire_*` emit `m_cellList
   None`, so the wrapped constructors here add the helper]; the pipe
   MATERIAL type carries its absolute ROUGHNESS as a double under builtin
   `-1140204` in millimetres (carbon steel 0.04572 = 0.0018 in; ductile iron
   0.25908) — the value-first serialisation of ParamValueSetDouble.
6. **The STRUCTURAL-asset param-id schema, EXACT** [V, Rosetta twin]:
   `-1140300..302` Young's modulus x/y/z, `..303..305` Poisson, `..306..308`
   shear modulus, `-1140309` unit weight, `..310..312` thermal expansion,
   `-1140313` damping ratio, `-1140314` concrete compression, `-1140315/316`
   bending / shear reinforcement, `-1140317` shear-strength reduction,
   `-1140318` min yield, `-1140319` min tensile, `-1140320` reduction
   factor, `-1140321` resistance-calc strength, `-1140407..410 / 414` the
   wood set; ints `-1150464` asset class (3 observed) / `-1140322`
   behaviour; strings `-1150466` asset name, `-1150465` subclass,
   `-1140416/417` species / grade.  Revit's internal units: **stress =
   Pa x 0.3048; unit weight = N/m3 x 3.28084/35.3147; alpha raw** (345 MPa
   -> 105,156,000; 200 GPa -> 6.096e10; 77 kN/m3 -> 7,153.5).
7. **The THERMAL-asset param-id schema, by unit matching** [V, all 11 rst
   thermal assets]: `-1152308..311` thermal conductivity (W/mK x 3.28084),
   `-1152312` specific heat (J/kgK x 10.7639), `-1152313` density (kg/m3 x
   0.0283168 = kg/ft3), `-1152320` emissivity, `-1152327` permeability,
   `-1152328` porosity, `-1152329` reflectivity, `-1152330` electrical
   resistivity (ohm m x 3.53147e8 — Autodesk uses a flat 1e-7 for every
   metal); ints `-1152338` compressible / `-1152326` behaviour; strings
   `-1152342` schema id ('category:thermal:solid'), `-1152340` source
   ('Autodesk' = product data; ours 'GEN'), `-1152337` asset-library GUID
   (dropped), `-1150466` name.  `m_propertySetType` 1 = structural asset
   (17/28), 2 = thermal (11/28).
8. **Machinery classes are provably empty** [V]: SunAnnotationElem's class
   body is EMPTY (Element base only; the sun path is regenerated);
   NumberingSchema x3 are `m_builtIn TRUE` built-in rebar / fabric-sheet /
   coupler numbering keyed to built-in categories + parameters, identical
   across all six samples; SlaveSymbolTrackerElem's every map is empty.
   Reproduced -> byte-identical slots (8 in ZB7).  A residue bucket can be
   RETIRED WITHOUT AUTHORING when its class has no free value.
9. **21 of K4's 30 residue sketch planes are already bare machinery** [V]:
   the on-datum SketchPlanes (identity Trf on OUR levels) reproduce
   byte-for-byte from `datum_sketch_plane(datum, elevation)`; only the free /
   view-owned ones and those with non-datum origins carry sample values.
   The RefPlane object = the Level's datum-plane machinery (DatumPlaneGeom
   Step v1 flags 761725, GeomTable row, Face/Plane twin with archive pids
   3/4/5) with a VERTICAL plane whose envelope is the drawn extent; project
   refplanes: `m_refName 14`, category -2000530, free/bubble ends 0 (21/21).
10. **Two identity LEAKS lived in Group-B classes** [V]: the per-user
    WorksharingViewModeSettings copy named the Autodesk username `liqi`; the
    two surplus PrintSettings named the printer `SYDPRN008`.  Both retired by
    ZB7 (our per-user copy 'rvt-writer', our A3 / ANSI-D setups) — the
    provenance ledger's G2 identity policy applies to ELEMENT strings too,
    not only BasicFileInfo / DIT.

## T2 — the cross-corpus census (instances per file: Y9 / K4 / rst / rac / rme / racadv / rstadv / dach)

Run over the six samples + K4 + Y9 with `residue_b.census_class` (the
per-class field-variation summaries are in the reports / F5–F9); K4 == Y9
counts for every class (the Y-ladder deleted nothing).  Selected rows:

| class | Y9=K4 | rst | rac | rme | racadv | rstadv | dach | varying fields (Y9) |
|---|--:|--:|--:|--:|--:|--:|--:|---|
| ParamElemExternal | 466 | 466 | 290 | 8 | 2 | 33 | 434 | 19 (caption / guid / spec / group / flags) |
| ParamBinding | 209 | 209 | 2 | 12 | 8 | 4 | 219 | 4 (id / param / category / kind) |
| ParamElemElectricalLoadClassification | 108 | 108 | 72 | 60 | 18 | 36 | 126 | 10 (6 per classification) |
| RbsWireInsulationType | 26 | 26 | 26 | 2 | 26 | 26 | 26 | 2 (id, name) |
| RbsPipeScheduleType | 13 | 13 | 10 | 10 | 10 | 10 | 10 | 2 (id, name) |
| PipeSegment | 15 | 15 | 12 | 13 | 12 | 12 | 12 | 18 (name / rows / roughness) |
| PenWidthTableElem | 9 | 9 | 9 | 11 | 10 | 9 | 8 | 26 (id / famId / pens) |
| SectionAttributes | 10 | 10 | 10 | 10 | 12 | 11 | 2 | 5 (id / famId / name / font / category) |
| MaterialElem | 23 | 93 | 174 | 192 | 184 | 213 | 212 | 64 |
| PropertySetElement | 28 | 56 | 53 | 20 | 28 | 20 | 67 | 29 |
| ParameterFilterElement | 7 | 7 | 2 | 21 | 2 | 4 | 83 | 11 |
| SunAnnotationElem | 3 | 31 | 22 | 72 | 24 | 25 | 298 | 2 (id, owner view) |
| NumberingSchema | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 7 (id + built-in keys) |
| WorksharingViewModeSettings | 2 | 2 | 2 | 1 | 1 | 1 | 2 | 13 |
| PrintSettings | 3 | 3 | 2 | 1 | 1 | 1 | 10 | 9 |
| Viewer / Viewport | 5 / 8 | 34 / 79 | 24 / 63 | 110 / 157 | 30 / 62 | 37 / 60 | 272 / 607 | 19 / 15 |
| RefPlane | 21 | 21 | 56 | 12 | 13 | 4 | 462 | 33 (geometry) |
| SketchPlane | 32 | 209 | 123 | 487 | 174 | 94 | 1449 | 25 |
| RoomElem | 1 | 31 | 14 | 165 | 116 | 0 | 90 | (1 instance) |
| RvtLinkSymbol / Instance | 1 / 1 | 1 / 1 | 0 | 0 | 0 | 1 / 1 | 1 / 1 | 0 |

Readings: the wire / pipe catalog SYMBOL classes have exactly TWO free
fields (id + name) in every file — pure-name catalogs (F5); the numbering
schemas and sun annotations vary only by id / owner / built-in key
(machinery, F8); the parameter-definition counts are sample-specific (466
in rst, 8 in rme) confirming they are the sample's own shared-parameter
file, not format constants; the link pair exists only in the rst-lineage
files + dach.

## Constructors (src/rvt/genesis/residue_b.py — the module map)

* Definitions: `shared_parameter`, `project_parameter`,
  `load_classification_parameter`, `param_binding`,
  `our_shared_parameter_captions` (a deterministic house library sized to
  the base's storage-kind census), `project_param_type_id`, `_stable_guid`.
* MEP catalog: `wire_material_type` / `wire_insulation_type` /
  `wire_temperature_rating_type` (types-stream wrappers with the corpus
  CellList machinery), `pipe_schedule_type`, `pipe_connection_type`,
  `pipe_material_type` (roughness), `pipe_segment` (+ `PIPE_SIZE_TABLES`:
  ASME B36.10 / B36.19, ASTM B88, ASTM D1785 PVC, AWWA C151),
  `_table_for_schedule`.
* Family pen tables: `family_pen_width_table` (settings.pen_width_table,
  family-scoped).
* Annotation types: `section_attributes`, `viewport_attributes`.
* Palette companions: `extended_material` (+ `EXTENDED_MATERIALS` x10),
  `structural_asset` (+ `STRUCTURAL_ASSETS` x17, `BIP_PHY`), `thermal_asset`
  (+ `THERMAL_ASSETS` x12, `BIP_THM`).
* Filters: `parameter_filter` (+ `HOUSE_VIEW_FILTERS` x7).
* Machinery reproducers: `sun_annotation`, `builtin_numbering_schema`,
  `slave_symbol_tracker`; identity-leak retirement: `house_print_settings`,
  `per_user_worksharing_settings`; drafting companions: `drafting_viewer`,
  `drafting_viewport` (skeleton).
* Content: `reference_plane`, `datum_sketch_plane`, `free_sketch_plane`,
  `room_identity`.
* Rungs: `build_ZB1_defs` .. `build_ZB8_content`, `ZB_CHAIN`, `ZB_SINGLES`,
  `zb_substitute_inplace` (the V3 rung operator's ZB clone), `build_zb_
  ladder`, `census_group_b_residue`, `write_zb_probes_manifest`.

## Diffs / hooks proposed for files OUTSIDE this territory (NOT applied)

* **`src/rvt/genesis/types.py`** — the `_named_symbol_type` MEP-catalog
  constructors emit `m_cellList None`; every corpus catalog symbol carries
  `CellList{PatternHelper}` (F5): add a `cell_list=True` default there so
  the types-stream wire constructors match the corpus without this
  module's wrappers.
* **`tools/genesis_substitute.py` (`_residue_reason`)** — `PropertySetElement`
  should map to `material-companions` (thermal / structural assets), not
  `no-constructor`; `NumberingSchema` / `SunAnnotationElem` /
  `SlaveSymbolTrackerElem` deserve a `format-machinery` bucket ("reproduce,
  do not author"); `ParamElemElectricalLoadClassification` couples to the
  load-classification web (Group A) — worth a note in the reason text.
* **`tools/genesis_substitute_v3.py`** — `substitute_inplace` is not reusable
  with an external builder (its `build_for` knows only the X/Y builds); this
  stream cloned the rung operator (`zb_substitute_inplace`).  A `build_fn`
  parameter on `substitute_inplace` would let both group streams call it
  directly (and Yn's `run_residue_census` could take a chain of report dirs
  so ZA/ZB deep files census through the same code).
* **`docs/coverage/viewer-certified.json` (orchestrator)** — add the ZB
  files as they read out; every report names its base (Y9) + control
  (CTRL_Y9_base.rvt) + the ONE bucket it tests.
* **KNOWLEDGE.md owner** — merge findings 1–10 (the registry-keyed
  parameter identity, the two asset schemas + Revit's internal units for
  stress / unit weight / conductivity / specific heat / density, the
  machinery-reproduction proof method, the identity-leak law for element
  strings).
* **`tools/sync_plugin.py`** — this stream ADDS a `src/` module
  (`rvt/genesis/residue_b.py`); per KNOWLEDGE-adjacent memory, run
  `tools/sync_plugin.py` after framework changes if the plugin bundle should
  carry it (it is a genesis constructor module, not part of the reader
  chain — the orchestrator decides whether the plugin needs it).

## Open questions (need the viewer / a decision)

* The 17 verdicts, in the upload order above (control first; ZB_deep alone
  answers the whole group if it passes).
* The parameter-IDENTITY choice (endgame §5): accept our captions at the
  sample-minted GUID registrations (recommended for release 1), re-key the
  466 registry keys to our GUIDs (a registry-edit rung), or delete the layer
  (endgame step 25 — with the rebar-numbering-key caveat).
* Whether the drafting-view constellation (root DBViewDrafting = Group A)
  is ADOPTED as our 'GEN Typical Details' view (ZB7 already rebuilt its
  companions at the same ids) or deleted atomically (endgame §2).
* The container layer + counsel items (own-save, Formats/Latest, the Forge
  corpus) — untouched by design; endgame §6.
* Two UNPROVEN removal mechanics flagged for isolation before use: system-
  family (curtain) layer removal, and dangling rebar-numbering keys after a
  definitions deletion.
* A cosmetic coherence follow-up (not a load risk): the pipe segments keep
  their SLOT's material wiring, and Y7's slot-fill landed our WOOD / CMU /
  earth materials into the sample's pipe-material MaterialElem slots (e.g.
  segment 137323 'GEN Steel Pipe' -> material 137433 'GEN Wood, Softwood
  Lumber').  Our extended palette (ZB5) now carries our metal / plastic
  materials, so a small in-place RE-WIRING rung (segment m_materialId ->
  our steel / stainless / copper / PVC / ductile-iron slots by role name)
  makes the merged deep file semantically coherent; every reference is
  legal as it stands.

## Proposed next tasks (orchestrator decides)

1. Upload the ZB batch through `tools/probe_batch.py stage` (bases resolve
   to Y9 = certified; the control is staged): read the control FIRST, then
   ZB_deep; only on a ZB_deep FAIL read the singles.
2. On ZB_deep PASS: merge ZA_deep + ZB_deep over Y9 (both are pure in-place,
   ids preserved — replay the two correspondence sets in one substitute_
   elements call) => the ZAB_deep file with EVERY in-place-substitutable
   residue element ours; then start the endgame's Phase II (the ADD queue,
   one registration variable per rung) and Phase III (the deletion set,
   leaf-first) exactly as ordered in `docs/writer/genesis-endgame.md`.
3. Merge findings 1–10 into KNOWLEDGE.md; apply the two proposed hooks
   (types.py CellList default, the residue-reason vocabulary) at the
   framework owners' discretion.
4. Add the passing ZB files to `viewer-certified.json` as they read out —
   ZB_deep is then the certified base for the ZAB merge and Phase II.

## Verification

* `.venv/bin/python -m rvt.genesis.residue_b` -> 17 files, ALL `VALID`
  (validator 0 errors, structural proof, coherence, byte-delta assertion,
  parity, regdiff sample per report); ZB_deep census = 2 Group-B residue
  elements (the link pair).
* `tools/rvt_validate.py --quiet experiments/genesis/subst_k4/residue_b/*.rvt`
  -> 18 x `OK errors=0 warnings=1` (control included).
* `.venv/bin/python -m pytest tests/test_residue_b.py -q` -> **53 passed**
  (the Group-B claim vs Yn; every constructor's byte-exact schema round
  trip (29 kinds); the machinery reproducers value-identical to the
  sample's own objects; the census instrument; the eight builders' plan
  correctness on Y9 — one same-class record per residue slot, no protected
  slot targeted, every record round-trips; one end-to-end single rung with
  the in-place byte-delta law asserted; probes-manifest consistency).
* Full suite: see BRANCH STATE.

## BRANCH STATE

No VCS (plain directory).  New, uncommitted files, this stream's
territory only: `src/rvt/genesis/residue_b.py` (constructors + census +
the ZB rung machinery + driver), `tests/test_residue_b.py` (53 pass),
`docs/writer/genesis-endgame.md` (the Yn = 0 end-game),
`docs/inbox/genesis-residue-B.md` (this file), and under
`experiments/genesis/subst_k4/residue_b/`: `ZB1_defs .. ZB8_content .rvt`
+ `.json`, `ZB_deep.rvt` + `.json` (alias of the deepest chain rung),
`ZB_deep_census.json`, `Z_defs .. Z_content .rvt` + `.json`,
`CTRL_Y9_base.rvt` (md5-identical to Y9), `probes.json`.  Every emitted
`.rvt` = validator VALID (0 errors), structural proof clean, four-registry
coherent, `Global/Latest` + `Global/ElemTable` byte-identical to its
parent, byte-delta assertion holding (only the landed slots' seq-102
records changed; the byte-identical reproduced-machinery slots listed per
rung).  No existing `src/`, tool, test or `.rvt` was edited.  Full suite
this session (`.venv/bin/python -m pytest tests/ -q --ignore=tests/oracle`):
**1050 passed, 2 failed** (1052 tests, 16:16) — this stream's 53 tests
are among the 1050; the 2 failures are the pre-existing, other-stream ones
every recent record lists (`tests/test_provenance.py::
test_G0_resource_refs_are_counted` and `::test_G0_identity_dit_usernames_
still_leak` — stale assertions pinning the pre-genesis-2 G0's defects;
neither touches this stream's files).
STOPPED AT READY — the 17 files + control await the orchestrator's viewer
batch; the endgame document is the recorded queue from ZB_deep to Yn = 0.
