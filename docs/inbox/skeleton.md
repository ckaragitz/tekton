# skeleton — workstream record (GENESIS: the project scaffolding, 2026-08-03)

Charter: from the reduction ladder + KNOWLEDGE + the samples, produce the
SPEC and the CONSTRUCTORS for the non-type skeleton of a valid Revit
project — levels, phases, project info, the view constellations, the site
skeleton, the units registry, and the six table streams of a MINIMAL
one-episode document. Territory touched ONLY:
`src/rvt/genesis/skeleton.py`, `tests/test_genesis_skeleton.py`,
`docs/writer/genesis-skeleton.md`, this file. Nothing outside it edited
(the `rvt/genesis/__init__.py` created by the types stream was left as-is;
see coordination note C1).

## Deliverables

| item | path | state |
|---|---|---|
| constructors + minimal Global streams | `src/rvt/genesis/skeleton.py` | done, `python -m rvt.genesis.skeleton` demo green |
| tests | `tests/test_genesis_skeleton.py` | 20 tests, pass |
| spec (VERIFIED/INFERRED/UNKNOWN-tagged) | `docs/writer/genesis-skeleton.md` | done |

## Headline results

1. **The skeleton is fully constructible from scratch.** Every skeleton
   class has a field-by-field Python constructor (plain parameters in,
   schema-shaped dict out — no `.rvt` opened, nothing cloned). Feeding
   the constructors the specimens' own parameter values reproduces the
   ORIGINAL record bytes (adler32 stamp included) for 40 records across 19
   classes of rstbasic: Level (obj+header+rep), LevelAttributes,
   ProjectPhase ×2, AllProjectPhases (+header), PhaseFilterElem ×5,
   ProjectInfo (+header), DBViewType ×2, the project view's Viewer
   (+header) / DBDrawing / Viewport (+header), ExtentElem (+header),
   SunAndShadowSettings, SketchPlane (+header), LightSchemeElement,
   ModelClipBox, TrueNorth (+header), GeoSite, GeoLocation header,
   BasePoint, and the 36 KB UnitsElem (136 format entries). Spec §0.
2. **The composed minimal skeleton** (`build_minimal_skeleton`: units,
   level type + 2 levels, 2 phases + AllProjectPhases + 5 filters,
   ProjectInfo, document sun, project view + one 3D view + one plan per
   level = 42 elements) encodes and decodes 126/126 records clean.
3. **The six minimal table streams** (`minimal_globals`) satisfy the
   KNOWLEDGE cross-stream save invariants by construction and round-trip
   through `rvt.stream_encoders`; plus the empty
   `Global/ContentDocuments` payload (14 B, from the .rfa) and OUR
   BasicFileInfo identity (never a template's).
4. **What a document contains at BIRTH** (episode-0 census, 3/3
   templates): styles/patterns/categories/materials/fonts, the phase set
   (id 1) + 5 filters, the pen table (id 2), ONE level + its type, a few
   annotation-type defaults, one wall type — and **the project view
   constellation (DBViewProject 230 / Viewer 231 / Viewport 232 /
   DBDrawing 233), the only view a document is born with.** All templates
   share this ancestor's ids (the birth History episode GUID is a
   year-2001 GUID). Spec §1.
5. **VIEW DEFINITION vs GENERATED content is now cleanly separated**: the
   DBView base is 461/474 leaves of product-default settings + ~15
   definition fields (name, view family type, camera/plan frame, scale,
   genElemId = the level for a plan, satellite links, phase params); the
   only generated payload is the Viewer3d camera-symbol GElement (we emit
   SerializedDummy). Spec §4.
6. **Zero views is UNRESOLVED** and ranked unknown #1: the project view is
   present at birth everywhere and never deleted by the v2 ladder; no
   viewer test of a zero-user-view file exists (deepest PASS on record is
   still R4s). Spec §4.6.

## Evidence log (short)

- E1 pid rule reproduced by construction: archive object 1 = ADocument,
  2 = the element, ≥3 registered in pointer-token order (Level: Face 3,
  Plane 4, deferred Plane 5) — byte-exact.
- E2 `AllProjectPhases.m_phaseIds` carries the phase ORDER; phases have
  no sequence field; phasing overrides key on `m_elementOnPhaseStatus`
  2/3/4/5 and reference the four Phase materials + patterns (the phase
  set's only registry dependencies).
- E3 `DBViewType.m_systemFamilyIdx` table (102 3D View … 109 Floor Plan,
  111 Ceiling Plan, 120 Structural Plan) identical in 3 templates.
- E4 `Contents.creation_guid == PartitionTable Workset1 GUID` (6/6);
  History header GUID slots = a lineage GUID, entry[0] = the newest
  episode = BFI GUID (6/6); DIT newest id_pair = (Hcount−1, Hcount).
- E5 UnitsElem = 136 spec→FormatOptions keyed by Forge unit ids; the
  constructor + the specimen's format list = byte-exact 35,993 B.

## For KNOWLEDGE.md merge (proposed)

1. Every corpus template descends from ONE Autodesk ancestor document
   (shared infrastructure ids 1, 2, 230–233, 305, 311, 371–375, 397, 19236,
   49504, 54520, 55150, …; birth episode GUID `e3e052f9-0156-11d5-…`).
   Episode-0 elements = the birth set; UnitsElem/ProjectInfo/site were
   later format-upgrade additions.
2. The birth (mandatory) view = `DBViewProject` (+ Viewer + DBDrawing +
   Viewport), `m_dbViewTypeId = -1`, name '???'; its ViewDisplayMgr points
   at the document-wide SunAndShadowSettings (54520).
3. `AllProjectPhases.m_phaseIds` = phase order; `PhasingOverrides.
   m_elementOnPhaseStatus` 2/3/4/5 = Existing/Demolished/New/Temporary.
4. `DBViewType.m_systemFamilyIdx` view-family table (spec §4.5).
5. A plan view's `m_genElemId` = its Level; its fixed SketchPlane's
   `m_datumPlaneId` = the view; view range = PlanViewRange2 offsets/level
   ids mirrored in `m_cutPlaneElev`/`m_topClipElev`/`m_bottomClipElev`.
6. `ElementHeader` category field is spelled `m_categroryId` (typo);
   GNode/GInfo's is `m_categoryId`.
7. Empty `Global/ContentDocuments` payload = `a3 03 00 00 00 00 ff ff ff ff
   00 00 00 00` (2026 .rfa).

## Coordination notes for the orchestrator

- **C1 (package init):** the types stream created `src/rvt/genesis/__init__.py`
  importing `.types`. My tests import `rvt.genesis.skeleton` normally with
  a file-loader fallback so they never depend on sibling modules. If the
  orchestrator wants `from rvt.genesis import skeleton` /
  `SkelElement` exported, add to `__init__.py` (not my territory):
  ```python
  from . import skeleton  # noqa: F401
  from .skeleton import (SkelElement, ViewSpec, IdSource, Skeleton,
      build_minimal_skeleton, minimal_globals, encode_minimal_globals,
      new_level, new_level_type, new_phase, new_all_project_phases,
      new_phase_filter, default_phase_filters, new_project_info,
      new_view_type, new_project_view, new_3d_view, new_plan_view,
      new_units_elem, new_true_north, new_base_point, new_geo_site,
      new_geo_location, new_document_sun_settings)
  ```
- **C2 (record shape):** `SkelElement` mirrors `types.TypeRecord`
  (elem_id/kind/class_name/class_id/category_id/obj/header/rep/refs/notes,
  `.records()`, `.as_tuple()`, `.roundtrip()`) plus `owner_id` for the
  ElemRec owner column and adapters `as_type_record()` /
  `as_new_element()`. `IdSource` here answers both `.next()` and
  `.next_id()`; `_alloc()` accepts either (and a `mutate.Document`).
- **C3 (assembler contract):** the assembler needs from this stream:
  `skeleton.elements` (records + ElemRec rows), `encode_minimal_globals(
  skeleton.globals_models)` (six inflated payloads + the Contents
  prologue + the empty ContentDocuments payload); it must supply
  `Formats/Latest` (copied constant), `Global/Latest` (ADocument — NOT
  produced here) and the framing/paging. `Partitions/<N>` name for a
  one-save document is INFERRED `Partitions/0` (N = increment − 1).
- **C4 (types stream inputs):** for a phase set without −1 material ids
  the composer needs from the types stream the four 'Phase - Exist/Demo/
  New/Temporary' materials, one dash line pattern and two fill patterns
  (spec §3, §8); views' RetouchTable wants two GStyleElem ids
  (invisible-lines / not-silhouette); the level type wants a font + the
  level-line sub-category. All are `-1`-defaulted parameters today.
- **C5 (full-suite note):** full pytest at handoff = **434 passed, 2
  failed** — neither in this stream's code: (a) `tests/test_mep_views_
  spaces.py::test_schedule_view_and_space_write_and_verify` (an ECC
  mismatch in the MEP views stream's write test); (b) `tests/test_plugin_
  sync.py::test_plugin_is_in_sync_with_source` — the plugin bundle has
  drifted by 12 new source files from the concurrent streams
  (`genesis/skeleton.py`, `genesis/types.py`, `genesis/__init__.py`,
  `mep/*`, `provenance.py`, `identity.py`, `estorage.py`). The fix is the
  orchestrator's ONE run of `python tools/sync_plugin.py` after all
  streams land (deliberately NOT run here: it touches `plugin/`, outside
  this territory, and would race the sibling streams).

## Files the orchestrator should viewer-test (in this order)

None emitted by this stream (DONE excludes assembling a whole file — the
assembler does that). Cheapest probes toward the ranked unknowns, all
buildable by the existing V-track tooling on a template copy: (1) DIT
counters rewritten to all-1 / sequence 1; (2) History format list
truncated to [2662]; (3) AllProjectPhases materials → −1; (4) one Viewer3d
rep → SerializedDummy; (5) delete every user view but keep DBViewProject
230 (zero-user-view probe). See spec §11.

## Open questions

Spec §11 (ranked): zero user views; DIT counter semantics; −1 phase
materials; Viewer3d camera rep; History version list; PartitionTable
id_a/id_b + Contents hdr5; level-type head symbol −1; zero
ContentDocuments in a project; `Partitions/0` naming; id ranges; header
flag bits; droppability of worksharing/revision/keynote/browser
singletons (ADocument-blocked).

BRANCH STATE: git repo present, uncommitted files at the paths above —
`src/rvt/genesis/skeleton.py`, `tests/test_genesis_skeleton.py`,
`docs/writer/genesis-skeleton.md`, `docs/inbox/skeleton.md`. Suite at
handoff: `tests/test_genesis_skeleton.py` 20/20 green; full suite 434
passed / 2 failed (both in other streams' territory, see C5). READY.
