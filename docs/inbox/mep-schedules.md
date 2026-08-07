# mep-schedules — PANEL SCHEDULE VIEWS + SPACES / ROOMS / TAGS (record)

Stream: `mep-schedules` (MEP CRUD fleet, deliverable-facing elements).
Spec: `docs/writer/mep-views-spaces.md`. Module: `src/rvt/mep/views_spaces.py`.
Tests: `tests/test_mep_views_spaces.py` (15: 14 fast + 1 slow write/verify).
Proof harness: `experiments/mep/schedules/make_views_spaces.py` →
`experiments/mep/schedules/*.rvt` + `experiments/mep/spaces/*.rvt` +
`manifest.json` in each (full verify + validator + semantic readback).

## What was decoded (evidence in the spec §1–3)

* **`PanelScheduleView` (0x0b48) references its panel by
  `TableView.m_targetId`** (24/24 rme views → their panelboard), its
  template by `m_idTemplate` (`PanelScheduleTemplate`: 638860 'Branch
  Panel', 638864 'Switchboard', 638863 'Data Panel', …), name in
  `m_viewName`, freshness `m_outOfDate`.
* **Cell content is COMPUTED-ON-OPEN, not stored** — the ~150 KB
  `m_oTableData` is 4 layout sections whose cells are label texts +
  parameter BINDINGS (`m_paramId`); a full census of view 742926 found
  ZERO `m_oCalculatedValue` and ZERO stored data text. ⇒ creating the
  VIEW element (rewired) is enough; Revit regenerates the table.
* A schedule view is the root of an **8-element OWNED cluster** (Viewer,
  DBDrawing→Viewport, FontElems, CategoryElem→GStyleElem) linked by
  `Global/ElemTable.m_OwningElementId`; the panel's header back-links the
  view in `m_regenOnly`; nothing else references the view (byte search).
* **Space = `RoomElem` (0x0ec8) with category −2003600** (rooms: same
  class, −2000160); POINT-placed (`m_point` + `m_levelId`); name/number =
  AString params −1006900/−1006901; zoned via `m_zoneElementId` ↔
  `ZoneElement.m_spaceIds` (two-sided; Default zone 293242 lists none);
  `RoomTagPlacement.m_offset` = signed distance, right-of-direction
  positive (reproduced exactly on both anchors of 379575).
* **Space tag = `RoomTag` (0x0ecc), category −2000485**, owned by its
  plan view (`m_ownerDBViewId`), `m_taggedRoomElemId → space`,
  `m_symbolId → 351633 'Space Tag'`; 87/87 rme tags follow it.
* Byte-exact codec round trip proven for every class touched: 40/40
  records (PanelScheduleView 153 KB, PanelScheduleTemplate, Viewer,
  DBDrawing, Viewport, FontElem, CategoryElem, GStyleElem, RoomElem +
  its GElement, RoomTag, ElementHeaders).

## What was implemented (spec §4)

`add_panel_schedule_view` (whole-cluster clone, full-tree id remap, panel
back-link), `link_schedule_view_into_existing_panel`,
`rename_panel_schedule_view`, `delete_panel_schedule_view`, `add_zone`,
`add_space` / `add_room` (point + bounding-wall cache + placement anchors
+ zone both sides + rebuilt reference planes, `SerializedDummy` rep,
caches invalidated), `add_space_tag`, `rename_space`, `delete_space`,
`describe_*` readbacks, and `commit_elements` (the create-path writer with
faithful ElemTable OWNER links + identity coherence).

## Findings the orchestrator must act on

1. **Cross-stream defect — identity scrub breaks a validator L2 rule.**
   `rvt.commit.commit_new_elements`' G2 identity step
   (`identity.own_basic_file_info`) mints a FRESH BasicFileInfo *Unique
   Document GUID* but the minimal commit records NO new `Global/History`
   episode ⇒ `validate` L2 error *"Unique Document GUID != History
   entry[0] GUID"* on **every** file the create path now writes (the
   certified H1–H3 predate the scrub). `views_spaces.commit_elements`
   works around it by passing `identity={"document_guid": <History
   entry-0 GUID>}`. Proper fix (owner: commit/identity stream): either
   `history_append_episode` + the DIT row on every commit (a real save),
   or `own_identity_model` defaulting `document_guid` to History[0]
   instead of `uuid4()`. Until then EVERY other stream calling
   `commit_new_elements` directly emits a file that FAILS the arbiter.
2. **`commit.verify_written` false positive on the exact-page edge.** When
   a re-framed stream's FINAL block happens to fill a whole 64,896-byte
   page (encoded size = 65,249), the reader's `depage()` treats that last
   block as a full page (pad included), so re-computing
   `ecc.page_trailer(page)` over the padded page mismatches the stored
   final-block trailer in 4 bytes (pad-count field + parity) and
   `ecc_mismatches` reports 1 — but the file is VALID (`rvt_validate`
   structure layer: 506 pages, 0 errors; the validator's decoder honours the
   final block's pad-count field). Hit by an 18-element combined write
   (Partitions logical = 30,436,224 = 469 pages exactly). Suggested fix
   (commit.py `verify_written`, out of territory): skip the trailer
   equality test for the LAST stride-aligned page when the stream's raw
   length is an exact multiple of `PAGE_STRIDE` (or defer to
   `validate.ecc_verify_stream`). My tests judge ECC via the validator.
3. **Plugin bundle drift.** `tests/test_plugin_sync.py` fails because the
   plugin bundle is stale vs the many new `src/rvt/**` files landing from
   the parallel MEP/genesis streams (`lib/src/rvt/mep/views_spaces.py`,
   `.../mep/electrical_data.py`, `.../mep/conduit.py`, `.../mep/devices.py`,
   `.../genesis/*`, identity, provenance, estorage). Run
   `python tools/sync_plugin.py` ONCE at integration (not run here to
   avoid clobbering siblings mid-flight).

## Diffs for the orchestrator to apply (never done here — territory)

* **`src/rvt/commit.py::commit_new_elements`** — pass the planned owner
  through to the ElemTable row (the create path currently writes every
  new `ElemRec` with an INVALID owner; owned clusters need it):
  ```python
  # inside the elemrecs loop
  elemtable_add_element(model, plan.elem_id,
                        creation_ep=creation_ep,
                        modified_ep=creation_ep,
                        user_modified_ep=creation_ep,
                        owner_id=(plan.owner_id if plan.owner_id is not None
                                  and plan.owner_id >= 0 else INVALID_ID),
                        partition_id=plan.partition_id or 0)
  ```
  (`elemtable_add_element` already accepts `owner_id`;
  `views_spaces.commit_elements` currently injects it by wrapping the
  imported name — remove that shim once this lands.)
* **`src/rvt/mep/__init__.py`** docstring — add a bullet for
  `views_spaces` (panel schedule views + spaces/rooms/zones/space tags);
  left untouched because another stream owns that file's edits this wave.
* Optional: `identity.own_identity_model` — default `document_guid` to
  the file's History entry-0 GUID (finding 1) instead of a fresh uuid.

## Honest limits (spec §7)

Acceptance-critical hypotheses only the Autodesk viewer / Revit can judge:
(a) a rewired schedule-view cluster with `m_outOfDate=true` renders a
working panel schedule (control file with the flag false provided);
(b) a POINT-placed space with a `SerializedDummy` rep inside same-run
walls is picked up by Revit's room computation without a
`LevelRoomPlan`/`AllPlanTopologies` registration; (c) a new
`ZoneElement` beside the Default zone; (d) owner links written by the hook
are what Revit expects. Fallbacks: `plane`-style controls exist for (a);
for (b) place the space in an existing enclosed room (`room_id=`,
`bounding_walls=` its walls) or reuse an existing zone (`zone=<id>` +
an edit pass on its member list).

BRANCH STATE: `src/rvt/mep/views_spaces.py`, `tests/test_mep_views_spaces.py`
(15/15 pass), `docs/writer/mep-views-spaces.md`, this record, and 7 proof
files + 2 manifests under `experiments/mep/schedules/` and
`experiments/mep/spaces/` — every proof file **VALID with 0 validator
errors**, structurally verified and semantically re-read; nothing outside
this stream's territory edited; full suite at close = 350 passed + 2
non-territory failures (plugin drift — needs `tools/sync_plugin.py`; and my
slow test's `verify_written` ECC false positive, since fixed → 15/15).
Viewer certification of the 7 files is pending with the orchestrator.

| category | verb | status | proof file | notes |
|---|---|---|---|---|
| PanelScheduleView (+ 8-elem owned cluster) | create | PROVEN-viewer-pending | experiments/mep/schedules/panel_schedule_view.rvt | new 480 V panel + xfmr & receptacle loads + 2 circuits created in the same commit; view rewired to the new panel, template 'Branch Panel', m_outOfDate=true, owner links + panel regenOnly back-link written; validator 0 errors |
| PanelScheduleView (control) | create | PROVEN-viewer-pending | experiments/mep/schedules/panel_schedule_view_current.rvt | same, m_outOfDate=false + cloned slot cache (isolates the freshness flag) |
| PanelScheduleView | modify (rename) | PROVEN-viewer-pending | experiments/mep/schedules/panel_schedule_view_rename.rvt | existing view 709455 'LP-1' → 'LP-1-RENAMED' (DBView.m_viewName; 153 KB byte-exact re-encode); validator 0 errors |
| PanelScheduleView | delete | PROVEN-viewer-pending | experiments/mep/schedules/panel_schedule_view_delete.rvt | existing view 709461 'EP-3' + owned 9-element cluster cascaded (10 removed); panel's regenOnly mention neutralised; validator 0 errors |
| Space (RoomElem OST_MEPSpaces) + Zone + SpaceTag | create | PROVEN-viewer-pending | experiments/mep/spaces/space_create.rvt | 4 new walls closing an electrical room + new ZoneElement + space 'ELECTRICAL ROOM' E101 at the room centre (bounding cache = the walls, placement anchored to 2 of them, ref planes at the point) + its space tag in 'Level 1 HVAC Zone Plan'; zone lists the space; validator 0 errors |
| Space (RoomElem) | modify (rename/renumber) | PROVEN-viewer-pending | experiments/mep/spaces/space_rename.rvt | existing space 379575 'Technology' 28 → 'ELEC EQUIP RM' 128 (params −1006900/−1006901); validator 0 errors |
| Space (RoomElem) | delete | PROVEN-viewer-pending | experiments/mep/spaces/space_delete.rvt | existing space 379575 + its tag 379576 cascaded; zone 379574 member list + plan-topology mentions neutralised; validator 0 errors |
| Room (RoomElem OST_Rooms) | create | VALIDATES (plan-level; unit test) | — | `add_room` = same recipe, unzoned; not written to a proof file this wave |
| Space tag (RoomTag OST_MEPSpaceTags) | create/delete | (rows above) | — | created with the space; deleted by the space cascade (annotation dependent) |
| PanelScheduleTemplate / DBViewSchedule | read | VALIDATES (READ + note) | — | template catalog decoded (`panel_schedule_templates`); plain `DBViewSchedule`s are category queries — no per-target authoring needed |
