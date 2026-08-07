# THE GENESIS END-GAME — from Y9 to Yn = 0 Autodesk-authored elements

Author: the genesis-residue-B stream (2026-08-04).  Companions: the ZB rungs
(`experiments/genesis/subst_k4/residue_b/`, record `docs/inbox/
genesis-residue-B.md`), Group A's ZA rungs (`docs/inbox/genesis-residue-
A.md`), the Y-ladder (`docs/writer/substitution-ladder-v3.md`), Yn
(`experiments/genesis/subst_k4/Yn.json`).

## 0. What this document is

Y9 (viewer-CERTIFIED, VERDICTS #17) is K4 with **1,333** of its 3,342 host
elements OURS in place; the **RESIDUE = 2,009** Autodesk-authored elements in
11 buckets.  This is the ORDERED PATH from that census to a document with
**zero** Autodesk-authored elements — for EVERY residue element (and for our
own not-yet-landed records) the ONE operation that retires it, in the order
the operations must run, under **THE REDUCTION LAW** (KNOWLEDGE.md): a
referrer of removed content is DELETED WITH the content or LEFT
BYTE-IDENTICAL — never edited into a state no Autodesk file exhibits; the
only sanctioned reduction generator is maxgc; a base is CERTIFIED before
anything is built on it.

There are exactly THREE retiring operations, and every residue element is
assigned exactly one:

| operation | mechanism (certified) | what it retires | registry effect |
|---|---|---|---|
| **IN-PLACE** | `rvt.regadd.substitute_elements` (the Y/ZA/ZB ladders) | a slot whose CONTENT can be ours | none — Global/Latest + ElemTable byte-identical |
| **DELETE-WITH-CONTENT** | `rvt.reduce.delete_elements` + `reblock` (the R/K reduction ladder's edit-free maxgc) | content a genesis file does not want, together with every referrer that dies with it (a CONSTELLATION, atomically) | the ADocument's registry entries are LEFT DANGLING (R5 / R9 prove thousands of dangling ADocument refs are tolerated); the four content registries are reconciled |
| **ADD** | `rvt.regadd.add_element_like_original` (the registration-conformant add path; V20..V29 / T_conduit_types are its certified user-content precedents) | OUR records that found NO in-place slot (Yn's ours-not-landed queue) | a new ElemTable row (corpus vintage / ownership rules) + optional registry registration |

A fourth operation exists only for the CONTAINER layer (identity /
history / the Forge corpus / Formats/Latest): **OWN-SAVE + counsel** — out
of every element rung's scope (§6).

## 1. Where we stand (2026-08-04, after ZA_deep + ZB_deep)

* **Y9** (certified): 1,333 landed / 2,009 residue / 0 unclassified.
* **ZB_deep** (this stream; validator VALID, awaiting the viewer): +995 of
  Group B's 997 residue elements are OURS in place; Group B's residue = **2**
  (`RvtLinkSymbol` + `RvtLinkInstance` — DELETE, §3.4).  Machinery classes
  are REPRODUCED (byte-identical slots) and thereby honestly emptied.
* **ZA_deep** (Group A's stream): the A..L classes (1,012 elements) — read
  `docs/inbox/genesis-residue-A.md` for their landing count; this document
  assigns their retiring operation by class regardless of which stream
  lands them.
* **Ours-not-landed** (the ADD queue, Yn): 252 of our records — the 235
  built-in catalog rows the R9 lineage GC'd away, 4 phase filters, our 3
  system text types + 9 companions, InitialViewSettings (§4).

So the end-game after the two deep files is: **(a)** land the ADD queue,
**(b)** run the DELETION SET, **(c)** the container's own-save.  Nothing
else stands between the corpus-derived base and a fully authored document.

## 2. THE ATOMICITY RULE (why the alphabet split does not split constellations)

The A / B stream split is by CLASS NAME, but the document is made of
CONSTELLATIONS whose members must retire TOGETHER (the reduction law's
delete-with-content, and the substitution ladder's companion sweeps).  These
constellations straddle the split and are ATOMIC — one operation per
constellation, executed by whichever stream owns the ROOT, listing every
member:

| constellation | root (owner) | members (both groups) | operation |
|---|---|---|---|
| the placed ROOM | RoomElem (B) | LevelRoomPlan (A), its 5 area-boundary CurveElems (A), the boundary sketch plane 245433 (B), the AreaSchemePlanTopologies rows referencing it (A) | DELETE-WITH-CONTENT (or keep: ZB8 proved the room's identity strings load as ours) |
| the DRAFTING VIEW 'Framing Plans' | DBViewDrafting 1457028 (A) | Viewer 1457029 (B), Viewports 1457030/1457043/1457044 (B), DBDrawing 1457031 (A), its fixed SketchPlane 1457032 (B) | IN-PLACE as ONE view constellation (the X9/Y9 view-builder pattern) — ZB7 already rebuilt the B companions wired to the view id; Group A rebuilds the root + drawing at the same ids, or the whole constellation is DELETED atomically |
| the dimensioned refplane group | LinearDimString 763420 (A) | RefPlanes 699327 / 699381 / 763366 (B — ours after ZB8), the dimension's DimensionStyle (A) | DELETE-WITH-CONTENT (a dimension referencing sample datums) or keep with our refplanes |
| the 8 curtain SYSTEM families | Family x8 (A) | FamilySurrogate x8 (A), their 72 family-scoped DBViewTypes (A), their 8 pen tables (B — ours after ZB3), the family-scoped SectionAttributes (B — ours after ZB4), SlaveSymbolTracker (B, via FabricSheetType) | the FAMILY layer is atomic (KNOWLEDGE.md 'The family/type layer is atomic'): DELETE the whole system-family layer WITH its scoped types (K3/K4's proven operation), or KEEP it entire; our scoped tables ride along either way |
| a surplus MATERIAL and its assets | MaterialElem (B — ours after ZB5) | its PropertySetElement assets (B — ours after ZB5), its AppearanceAssetElem (A) | now OURS in place except the 18 appearance assets: DELETE the appearance assets (companions our materials do not bind) or Group A reproduces them; the material itself no longer needs deleting |
| the load-classification web | ElectricalLoadClassification x18 (A) | their 6-per-class ParamElemElectricalLoadClassification (B — ours after ZB1), ElectricalDemandFactorDefinition x21 (A) | IN-PLACE both sides: ids preserved, so the B companions' m_idLoadClassification and the classifications' 6 param-id fields keep pointing at each other BY CONSTRUCTION — the cleanest cross-group case |
| the parameter-definition layer | ParamElemExternal / Project (B) | ParamBinding (B), the one ParameterFilterElement rule referencing a shared param (B — ours after ZB6; our filters carry no parameter rules) | IN-PLACE done (ZB1); the layer's IDENTITY (shared-parameter GUIDs = the ExternalParamTracking registry keys) retires only by DELETION or a registry re-key rung (§5) |

Rule: **a constellation is never half-deleted and never half-substituted
across streams.**  When the two streams' deep files are MERGED (ZA_deep's
records + ZB_deep's records over Y9 — both are pure in-place, ids
preserved, so the merge is well-defined: replay both correspondence sets),
each constellation must be in ONE of the two end states above.

## 3. THE ORDERED QUEUE (Y9 -> Yn = 0)

Order principle: certified base first, ONE variable per rung, every rung
carries the certified CONTROL (probe_batch.py gate); in-place rungs before
deletions (deletions change the referrer graph; substitutions do not), the
ADD queue last (it needs the final id watermark and registry state).

### 3.1  Phase I — IN-PLACE completion (no registration motion)

Everything here keeps Global/Latest + Global/ElemTable byte-identical.

| step | rung | elements | owner | state |
|--:|---|--:|---|---|
| 1 | Y1..Y9 | 1,333 | ladder v3 | CERTIFIED (VERDICTS #17) |
| 2 | ZB1_defs — parameter definitions + bindings | 791 | B | VALID (this stream) |
| 3 | ZB2_mepcat — wire + piping catalog | 74 | B | VALID |
| 4 | ZB3_pens — family-scoped pen tables | 8 | B | VALID |
| 5 | ZB4_annot — section-mark + viewport-title types | 11 | B | VALID |
| 6 | ZB5_palette — surplus materials + structural / thermal assets | 38 | B | VALID |
| 7 | ZB6_filters — view filters | 7 | B | VALID |
| 8 | ZB7_machinery — reproduced machinery + surplus setups + drafting companions | 14 | B | VALID |
| 9 | ZB8_content — refplanes / sketch planes / room identity | 52 | B | VALID |
| 10 | ZA rungs — the A..L layer | ≤ 1,012 | A | see genesis-residue-A |

After steps 1–10 the in-place-substitutable universe is exhausted.  What
CANNOT retire in place is exactly: content a genesis file does not want,
product-data layers with no constructor, the external link, and the
constellations of §2 chosen for deletion.

**The Group-B classes that Phase I fully retires** (995 elements): every
ParamElemExternal / ParamBinding / ParamElemProject / ParamElemElectrical-
LoadClassification (791), the whole MEP wire + piping catalog (74), the 8
family pen tables, 10 SectionAttributes + 1 ViewportAttributes, 10
surplus materials + 28 property sets, 7 filters, 3 SunAnnotationElem + 3
NumberingSchema + 1 SlaveSymbolTracker (reproduced machinery), 1
WorksharingViewModeSettings + 2 PrintSettings (identity leaks retired), 1
Viewer + 3 Viewports, 21 RefPlanes + 30 SketchPlanes + 1 RoomElem.  See
§7 for what "ours" means per class (free values vs reproduced machinery
vs kept registration).

### 3.2  Phase II — the ADD QUEUE (registration variables, one at a time)

Yn's `ours_not_landed_across_ladder` — OUR records with NO slot in the
base.  Each is landed by the FIXED add path (regadd.add_element_like_
original) on the certified deep file, ONE registration variable per rung
(the K1-night lesson: an X0-style control first — Autodesk's own row
verbatim through the add path — then ours).

| step | rung | records | why no slot | note |
|--:|---|--:|---|---|
| 11 | ADD-cat — the 235 built-in catalog rows | 235 | the R9 lineage GC'd 235 (category, type) keys; K4 loads with 1,172/1,407 | the CategoryTracking category->style registry gains 235 leaves = a REGISTRY EDIT rung (register=True); its X0 control: one Autodesk row re-added verbatim |
| 12 | ADD-filters — our 4 remaining phase filters | 4 | K4 carries 1 PhaseFilterElem | positional UET / phase-filter registry surface |
| 13 | ADD-text — our 3 system text types + 3 fonts + 3 categories + 3 styles | 12 | the R9 lineage carries no project text types | an ownership WEB (attributes type OWNS its CategoryElem + FontElem; regadd REG_RULES 'owns' wiring); the SymbolIdMgr default-text-type registry leaf |
| 14 | ADD-ivs — InitialViewSettings | 1 | absent in K4 | positional UET slot 32 (measured in the singletons stream) |

Phase II is the campaign's remaining REGISTRATION frontier — the only place
where 'the ADD path is the bug' (verdict #9..#11, RETRACTED with K1) can be
re-examined cleanly: certified base, certified control, one variable.

### 3.3  Phase III — THE DELETION SET (delete-with-content, atomic constellations)

Everything a family-free electrical genesis file does NOT want, removed by
the certified reduction machinery (`rvt.reduce.delete_elements` + reblock
+ four-registry reconciliation; ADocument references left dangling —
tolerated per R5 / R9).  Ordered by (a) constellation atomicity, (b)
referrer count (leaves first), (c) evidence value.  Each row = ONE removal
rung on the previous certified file.

| step | removal rung | elements retired (both groups) | law notes |
|--:|---|---|---|
| 15 | DEL-link — the linked model | RvtLinkSymbol 1250029 + RvtLinkInstance 1250030 (**the last 2 Group-B residue elements**) | its referrers (view link-instance lists in OUR views, CopyWatchProperties, the navigator, KeynoteTable, AreaSettings) are LEFT BYTE-IDENTICAL with dangling ids — never edited (K1's crime); a linked model names an external Autodesk sample file + path: it must go |
| 16 | DEL-room — the placed room constellation | RoomElem 1004910 + LevelRoomPlan 1004909 + CurveElem 1004904..08 + SketchPlane 245433 + the AreaSchemePlanTopologies rows that reference the room's plan topology | atomic (§2); a genesis file authors its own rooms/spaces via the add path (MEP spaces are user content) |
| 17 | DEL-dim — the dimensioned refplane group | LinearDimString 763420 (+ optionally RefPlanes 699327/699381/763366, ours since ZB8) | a dimension is annotation CONTENT; if our refplanes stay, only the dimension goes |
| 18 | DEL-datum — sample datum / legend content Group A owns | Grid x3, RefPlane group already ours, CurveElem x5, LegendComponent x4, the 7 plan-less Levels + their referencing SketchPlanes (ours since ZB8) | levels are atomic with their views / sketch planes: the 7 plan-less levels have no views (X9/Y9 kept only the 2 plan-bearing storeys) but 23 sketch planes sit on levels — delete a level WITH its sketch planes or keep both; our L1/L2 stay |
| 19 | DEL-surplus — surplus instances of substituted classes (Group A) | the 5 sample browser schemes, 4 fill + 3 line patterns beyond our palette, DBViewDrafting 1457028 + DBDrawing 1457031 (if the drafting constellation is not adopted, §2) | zero-referrer leaves except the drafting view (referenced by our plans: the plans' references die dangling — tolerated, or the view is kept as ours) |
| 20 | DEL-appearance — material-companion assets | AppearanceAssetElem x18 | no material of ours binds an appearance asset (m_appearanceAssetId -1): zero live referrers after ZB5 |
| 21 | DEL-annotation-types — attribute types with no constructor | DimensionStyle x12, CalloutTag x9, InteriorElevAttributes x9, LeaderStyle x5, GridAttributes, ColorFillSchema x10, LinearDimString (with step 17), + their FontElem / CategoryElem / GStyleElem companions (the 'no-constructor' + FontElem buckets, ~120 elements) | each attribute type is a constellation with its own FontElem + line-style CategoryElem/GStyleElem (like our text types own theirs): delete type + companions ATOMICALLY (the header m_deletion set names them: e.g. SectionAttributes 26029 -> {26029, 26030, 26031, 26032}) |
| 22 | DEL-curtain — the curtain SYSTEM family layer | Family x8 + FamilySurrogate x8 + their 72 family-scoped DBViewTypes + SlaveSymbolTracker + (our) 8 family pen tables + family-scoped section types | THE FAMILY LAYER IS ATOMIC (KNOWLEDGE.md); K3/K4 already proved the family-USAGE nulling + whole-layer removal on the loadable families — the curtain systems are the same operation on system families [the one unproven point: system-family removal has no viewer-passed precedent — probe it as its own rung with the K4 control] |
| 23 | DEL-hvac — Autodesk's HVAC / energy DATABASE | HVACLoadSpaceTypeElem x125, HVACLoadBuildingTypeElem x33, HVACLoadScheduleElem x27, BuildingOperatingYearSchedule x27 (212, 'product-data') | pure product data (a shipped database, like the keynote table our empty KeynoteTable retired); referrers: HVACLoadBuildingType <-> its schedules die together; RoomElem references a building type (dies at step 16) |
| 24 | DEL-misc — the remaining no-constructor machinery | AreaTypeElem x8, AreaSchemePlanTopologies x6, AreaReportSettingsElem, AssemblyCodeTable (UniFormat product data), DataStorage (an Extensible-Storage vendor blob — the arbiter's standing warning), LoadCaseElem x8, LoadNatureElem x8, MEP fabrication settings not ours, PropertySetLibrary | each is either a leaf (zero live referrers) or a small self-contained set; the AssemblyCodeTable is Autodesk's shipped UniFormat table = product data (counsel item C-class) |
| 25 | DEL-defs (OPTIONAL — the alternative to keeping our ZB1 substitution) | the whole parameter-definition layer (791, ours in place after ZB1) IF the genesis file should carry NO shared parameters at all | 0 value carriers (measured); the referrers = the ADocument trackers (left dangling: ExternalParamTracking / ParamBindingTracking / ProjectParamTracking maps) + the rebar-numbering key map (102 shared params keyed there — NumberingAppInfo; leaving those keys dangling is UNPROVEN — probe as its own rung) + the ElectricalLoadClassifications' 6 companion-param ids (Group A must then null or delete WITH them: an EDIT question — hence prefer keeping the substituted definitions, or re-keying, §5) |

### 3.4  What remains after step 24 (or 25)

**Nothing Autodesk-authored.**  The document's every element is one of:
our in-place constructors' output (Y + ZA + ZB), our add-path records
(Phase II), or a REPRODUCED format-machinery object (byte-identical to the
sample's own — the numbering schemes, sun annotations, trackers, bindings,
viewports: format constants, not authorship).  §7 states precisely which
classes are 'reproduced machinery' so the claim 'Yn = 0 authored elements'
is auditable and not a slogan.

## 4. The ADD queue in detail (Yn's second queue)

From `Yn.json:ours_not_landed_across_ladder` (unchanged by ZB — Group B
built one record per residue slot and dropped nothing; ZB adds ZERO to
this queue):

* **Y6 — 235 GStyleElem rows**: the built-in (category, type) keys the R9
  lineage GC'd away.  Landing them = 235 element additions + 235
  CategoryTracking registry leaves.  This is the ONE add rung whose registry
  edit is unavoidable — and the C0 forensic diff (genesis-addfix) shows every
  ElemTable property the old path wrote for GStyle rows is in-corpus, so the
  add rung's variable is genuinely the record + the registry leaf, nothing
  hidden.
* **Y8 — 4 PhaseFilterElem**: the phase-filter registry (AllProjectPhases /
  the UET filter slots).
* **Y9 — the text-type constellation** (3 TextNoteAttributes + 3 FontElem +
  3 CategoryElem + 3 GStyleElem): the ownership web the objlint OWNED_CHILD
  law describes; the SymbolIdMgr default-type registry leaf.
* **Y3 — InitialViewSettings**: one positional UET slot.

## 5. The parameter-IDENTITY question (the one registry variable ZB left standing)

ZB1 substituted the CONTENT of 466 shared parameters (captions / specs /
groups) but KEPT each slot's GUID, because the GUID is the KEY of
`ExternalParamTracking.m_keyDataMap` in Global/Latest [MEASURED: 466/466
GUIDs are the map keys; the map's `second.m_paramId` = the element id] —
an in-place rung cannot move a registry key.  Three futures, in
increasing cost:

1. **Accept**: our captions at Autodesk-minted GUID identities (the GUID is
   registration machinery like the element id; the counsel question is
   whether a random GUID is authorship — it is not creative content).
2. **Re-key**: ONE registry-rewrite rung — rewrite the 466 map keys to OUR
   deterministic GUIDs (`residue_b._stable_guid('shared', caption)`) AND
   the elements' m_externalParamKey / typeId tokens in the same commit
   (regadd's `latest_remap`-style typed leaf edit + object edit).  This is a
   REGISTRY EDIT, i.e. a Phase-II-class rung with its own control.
3. **Delete** (step 25): the layer is unreferenced by any value carrier; the
   trackers dangle.

Recommendation: 1 for the first genesis release (zero risk, already
certified-VALID); 2 as the follow-up rung once Phase II proves registry
edits load; 3 only if counsel objects to the GUIDs.

The same reasoning applies to the load-classification / project parameter
typeId tokens ('revit.local.classification:<session-guid><element-id>'):
the embedded element id we already own (in place, ids are ours); the
session-GUID prefix is a re-key candidate of the same rung.

## 6. The CONTAINER layer (out of every element rung's scope)

Untouched by design across the whole in-place programme (Global/Latest is
the sample's ADocument byte for byte; Formats/Latest is Autodesk's
per-release schema; the Forge JSON unit-schema corpus inside Latest is
Autodesk product data; History / DocumentIncrementTable / BasicFileInfo
carry the sample's identity — the provenance ledger's advisories).  Its
retirement is the OWN-SAVE step: `streams_edit.record_save()` (our identity,
our episode, our GUIDs) + the counsel decisions on the schema and the Forge
corpus (KNOWLEDGE.md 'Forge JSON corpus' item).  It comes LAST, after Yn =
0, so the identity save covers the finished document.

## 7. Audit table — what 'ours' means per Group-B class after ZB_deep

(so the Yn = 0 claim is checkable per element)

| class | count | after ZB | free values (OURS) | machinery reproduced / registration kept |
|---|--:|---|---|---|
| ParamElemExternal | 466 | ours in place | caption, description, group, spec (kind-compatible) | GUID + typeId token + element id + binding ids (REGISTRATION) |
| ParamBinding | 209 | reproduced | — (pure machinery: 208/209 byte-identical) | param id, category id, binding kind |
| ParamElemElectricalLoadClassification | 108 | ours in place | the caption phrasing | role (m_eType), spec, classification id, typeId token |
| ParamElemProject | 8 | ours in place | caption, group, kind | typeId token, bindings |
| Wire catalog (3 classes) | 33 | ours | designation names (industry facts) + our selection | CellList{PatternHelper} machinery (34/74 MEP slots byte-identical where designations coincide) |
| Pipe catalog (3 classes) + PipeSegment | 41 | ours | schedule / material designations, published roughness, ASME/ASTM/AWWA rows, segment names | segment -> material / schedule wiring (kept per slot) |
| PenWidthTableElem (family) | 8 | ours | pen widths (our ISO-128 series) | m_famId (the curtain family) |
| SectionAttributes / ViewportAttributes | 11 | ours | names, tail dimensions, title options | own FontElem / line-category ids, family scope |
| MaterialElem (surplus 10) | 10 | ours | everything (name, colour, class strings) | — |
| PropertySetElement | 28 | ours | asset name, subclass, all physical constants (published) | the two builtin-param id blocks (decoded schema) |
| ParameterFilterElement | 7 | ours | name, category set | — |
| SunAnnotationElem | 3 | reproduced | — (empty class body: byte-identical) | owner view id |
| NumberingSchema | 3 | reproduced | — (built-in machinery: byte-identical) | built-in category / parameter keys |
| SlaveSymbolTrackerElem | 1 | reproduced | — (empty maps: byte-identical) | master id |
| WorksharingViewModeSettings | 1 | ours | status colours, m_user ('rvt-writer') | regen edge to the project element |
| PrintSettings | 2 | ours | names, paper, orientation, filters | — |
| Viewer / Viewport (drafting) | 4 | ours (viewport 1457030 byte-identical machinery) | crop / camera frame | view / drawing / title wiring |
| RefPlane | 21 | ours | plane geometry, names | datum-plane machinery (GeomStep / Face / Plane twin) |
| SketchPlane | 30 | ours (21 byte-identical: already bare machinery) | free planes' origin | datum id (level) kept; identity frame |
| RoomElem | 1 | ours (identity) | number / name | topology wiring (level / scheme / boundary / placement) |
| RvtLinkSymbol / Instance | 2 | RESIDUE -> DELETE (step 15) | — | — |

'Reproduced' rows are the honest answer to 'is this Autodesk-authored?': the
object is a format constant (the same bytes any Revit would write) — there
is no authorship in it to attribute.  The provenance ledger's element
classifier (which reads ElemTable rows / id bands) counts in-place rows as
'sample' by construction; for this programme the per-rung landed / residue
accounting (Yn + the ZA/ZB censuses) is the authority.

## 8. Probes and controls for the end-game rungs

Every deletion / add / re-key rung above ships through the batch gate
(`tools/probe_batch.py stage`): its declared `base` = the previous
CERTIFIED deep file, its control = a byte-identical copy of that file,
control read FIRST, a control FAIL voids the round.  Deletion rungs are
probed leaf-first (steps 15–24 as listed), so a FAIL convicts one
constellation; the two UNPROVEN mechanics are flagged for isolation:
(a) system-family (curtain) layer removal (step 22), (b) the rebar
numbering registry's shared-parameter keys left dangling (step 25 only).
