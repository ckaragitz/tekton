# inbox — MEP stream: CONDUIT + CABLE TRAY (2026-08-03)

Territory: `src/rvt/mep/conduit.py` (new), `tests/test_mep_conduit.py` (new,
12 tests), `experiments/mep/conduit/*` (new: `make_conduit.py` + 5 proof
`.rvt` + `manifest.json`), `docs/writer/mep-conduit.md` (new — the full
spec / evidence doc; READ IT FIRST), this record. `src/rvt/mep/__init__.py`
already existed (another stream's namespace docstring) and was NOT edited.
No core module was touched.

## What the stream cracked

* **Every conduit lives in a run and owns a centre-line.** A drawn "run" is
  five element kinds: `RbsConduitCurve` (0x0d63, −2008132) + `ConduitRun`
  (0x0368, −2008149, owned by its first conduit) + `SegmentCenterLine`
  (0x0f20, −2008139, owned by / `m_OwnerId` = its conduit) + elbow
  `FamilyInstance` (−2008128) + `ConduitFittingCenterLine` (0x0366,
  −2008141, owned by its elbow). All 5 recipes decoded and written.
* **The elbow model is CLOSED-FORM.** Elbows are flexible-family instances:
  `m_masterSymbolId` = the type's `m_idDefaultElbow` (662459) while
  `InstanceInfo.m_symbolId` = one anonymous per-CONFIGURATION geometry
  clone SHARED by all twelve 2" 90° elbows (679082) ⇒ new elbows REUSE the
  clone. The frame is exact: corner `C` = the axes' intersection,
  `X = unit(C − A_end)` (leg on connector 1), `Y = unit(B_end − C)` (leg on
  connector 2), `Z = X×Y`; `m_or = C`, `m_instOrigin = C − (0,0,level.z)`;
  both legs trimmed by `bendRadius + straightExtension` (2": 0.890625 +
  0.16667 = 1.0573 ft — the bend radius comes from `ConduitSizesElem`).
  Reproduces the stored `m_3x3` of ALL 13 corpus fittings to < 1e-13
  (`test_elbow_frame_formula_reproduces_every_real_elbow`).
* **Connector semantics**: `m_arrRefs[].m_connType` = the TARGET connector's
  Revit `ConnectorType` — 1 End (curve/fitting), 4 Logical (circuits), 16
  Surface (equipment taps: transformer 624416 conn 2001/2002, panel 630241
  conns 3001–3003); a curve end also carries its own opposite-end link
  `{self, 1−i, 1}`; graphs are mutual. `m_dOffsetStart/End =
  endpoint.z − level.z` (exact 20/20).
* **Cable tray = conduit with a 3-field leaf** (`m_calculatedSize`,
  `m_oDesignPropManager`, `m_rungSpace`) — schema-verified. But **no cable
  tray element exists in ANY 2026 sample**, so trays are SYNTHESISED by
  class-morphing a conduit specimen (structurally valid; acceptance
  genuinely unknown). `OST_CableTrayRun = −2008147` / `OST_CableTrayCenterLine
  = −2008137` are INFERRED (from the confirmed +2 conduit↔tray category
  interleave); flagged in the file's own notes.

## API delivered (`rvt.mep.conduit`)

READ `inventory_runs / run_report / conduit_types / cable_tray_types /
conduit_standards / size_row / elbow_specimens / curve_geometry /
fitting_geometry`; CREATE `add_conduit_run(doc, p0, p1, level, type_or_size)`,
`add_conduit_path(doc, points, level, type, size)` (elbows),
`add_cable_tray_run(...)`, `commit_created(src, out, doc, plans)`,
`verify_plan_graph`; MODIFY `resize_run / move_run / set_run_elevation /
extend_run / retype_run`; DELETE `delete_run / delete_conduit /
delete_fitting`; read-back `readback_run`.

## Proof files (all: verifier clean + `tools/rvt_validate.py` ZERO errors)

Full manifest: `experiments/mep/conduit/manifest.json`. Validator summary
(`tools/rvt_validate.py … --quiet`, all three layers):

```
OK   experiments/mep/conduit/conduit_create.rvt           errors=0 warnings=1
OK   experiments/mep/conduit/conduit_create_straight.rvt  errors=0 warnings=1
OK   experiments/mep/conduit/conduit_modify.rvt           errors=0 warnings=1
OK   experiments/mep/conduit/conduit_delete.rvt           errors=0 warnings=1
OK   experiments/mep/conduit/cable_tray_create.rvt        errors=0 warnings=1
```

The single warning on every file is the pre-existing ES-blob decode gap of
the SOURCE sample (1,171 rme fittings the decoder cannot resolve), present
in the untouched sample too — not caused here.

| file | operation | structural | validator | semantic re-read |
|---|---|---|---|---|
| `conduit_create.rvt` | 3-segment 2" run + 2 real 90° elbows (clone 679082) + 5 centre-lines + run (11 new els) | CRC/ECC/walker/stamps clean, 11/11 clean in seqs 101/102/103, count 28143 | 0 errors | graph mutual, both elbows reuse clone, run lists path order |
| `conduit_create_straight.rvt` | 3 disjoint straight runs (2" horiz, 1" riser, sloped 3" RMC) — fitting-free fallback | clean, 9/9 | 0 errors | all 3 read back |
| `conduit_modify.rvt` | RESIZE 686270 2"→1"; MOVE run 679175 (+4,+3,0) rigid (3 conduits, 2 elbows, 5 CLs); EXTEND 686514 open end +3 ft; RETYPE run 688539 → 662475 | `verify_manipulated` clean | 0 errors | resized (25 mmø), moved rigidly + graph still mutual, extended, retyped — all true |
| `conduit_delete.rvt` | DELETE run 679090 (11 els; transformer 624416's tap ref neutralised) + DELETE elbow 688548 (fitting + CL; conduits' refs + run list neutralised) | 13 ids gone from unit 0 + ElemTable (28132→28119), referrers decode clean | 0 errors | all removed, transformer no longer refs 678659, run 688539 dropped the elbow |
| `cable_tray_create.rvt` | EXPERIMENTAL 2 straight cable-tray runs (Ladder 12"x4", Channel 6"x3.5"), class-morphed | clean, 6/6 | 0 errors | class `CableTray`, `CableTrayRun`, read back |

## Findings that affect other agents / the core (please act)

1. **`rvt.commit.commit_new_elements` block-counter defect.** The touched
   unit-0 blocks' `C` is recomputed with record-header lengths 12/16, but
   the corpus identity `ISIZE == hdr_len(seq)·A + C + adj` uses the WAVE-1
   lengths 16 (seq 101) / 20 (seq 102/103) ⇒ `C` is written `4·A` too
   large ⇒ the validator's "3 block(s) whose header counters A/C violate…"
   WARNING on H1 and every generic-created file. Fix (`src/rvt/commit.py`,
   inside the splice, only for the C recompute — keep `_hdr_len` 12/16 for
   the sentinel size):
   ```
   -                c_new = len(payload) - _hdr_len(b.seq) * a_new - adj
   +                c_new = len(payload) - (16 if b.seq == 101 else 20) * a_new - adj
   ```
   (`manipulate.chunk_segment` already uses the wave-1 lengths; only
   `commit.py` is off.) My `commit_created` carries the fix and my files are
   warning-free.
2. **Identity scrub vs History coherence.** `commit.py` (and the manipulate
   path? — check) now call `identity.own_basic_file_info`, which mints a
   FRESH document GUID; that no longer equals `Global/History` entry 0, and
   the validator flags it as an **ERROR** ("BasicFileInfo Unique Document
   GUID != History entry[0] GUID"). H1/M-files predate the scrub so they
   pass; any file the CURRENT `commit_new_elements` writes will FAIL the
   validator. Two consistent fixes: (a) minimal commits pass
   `document_guid=<existing GUID>` (what my `commit_created` does — scrub
   provenance, keep the GUID that pairs with History[0]); or (b) mint the
   GUID AND prepend the matching History episode (the full `record_save()`
   path). Suggested (a) diff for `src/rvt/commit.py`:
   ```
   -            new_streams["BasicFileInfo"] = own_basic_file_info(
   -                bfi.data, out_path=out_path, **(identity or {}))
   +            from .stream_encoders import decode_basic_file_info
   +            cur = decode_basic_file_info(bfi.data).get("unique_document_guid")
   +            ident = dict(identity or {})
   +            ident.setdefault("document_guid", cur)
   +            new_streams["BasicFileInfo"] = own_basic_file_info(
   +                bfi.data, out_path=out_path, **ident)
   ```
3. **ElemTable owners are dropped by the generic create commit.**
   `commit_new_elements` calls `elemtable_add_element` without `owner_id`,
   so companion elements (centre-lines owned by their curve, a run owned by
   its first curve, a SketchPlane…) land with owner INVALID. Diff:
   ```
   -            elemtable_add_element(model, plan.elem_id,
   -                                  creation_ep=creation_ep,
   -                                  modified_ep=creation_ep,
   -                                  user_modified_ep=creation_ep)
   +            own = plan.owner_id if getattr(plan, "owner_id", -1) not in (None, -1) \
   +                else 0xFFFFFFFFFFFFFFFF
   +            elemtable_add_element(model, plan.elem_id,
   +                                  creation_ep=creation_ep,
   +                                  modified_ep=creation_ep,
   +                                  user_modified_ep=creation_ep,
   +                                  owner_id=own)
   ```
   With those three fixed, my `commit_created` can be deleted and the stream
   can use `commit_new_elements` directly.

## Test suite

`tests/test_mep_conduit.py`: 12 passed (9.6 s). Full suite
(`pytest tests -q`, 2026-08-03): **434 passed, 2 failed** — neither
failure is this stream's: (a) `test_plugin_sync.py` — `plugin/` has
drifted from source for **12 files across ~5 concurrent streams**
(provenance/identity/estorage/genesis/mep incl. this module); left for the
orchestrator to run `python tools/sync_plugin.py` after merging the streams
(running it now would sweep other agents' in-flight modules into the
bundle); (b) `test_mep_views_spaces.py::test_schedule_view_and_space_write_and_verify`
— another stream's test; **passes when run alone** (15 passed), a
transient interaction during the concurrent full run.

## Honest gaps (see mep-conduit.md §8)

Cached extrusion solid: created curves ship a `SerializedDummy` seq-103 (the
regenerator path the accepted created walls used) — the acceptance-critical
question for the viewer run. No non-90° elbows / tees / crosses / unions (no
specimens). Created runs have OPEN ends — tapping a created conduit into
existing equipment surface connectors needs an in-place equipment edit
(phase 2). Cable trays: experimental (above).

## Reproduction

```
.venv/bin/python -m rvt.mep.conduit samples/rmebasicsampleproject.rvt
.venv/bin/python experiments/mep/conduit/make_conduit.py     # ~6 min, writes 5 files
.venv/bin/python -m pytest tests/test_mep_conduit.py -q       # 12 passed
```

BRANCH STATE: conduit CRUD complete and self-verified on the rme sample —
5/5 proof files structurally valid with ZERO validator errors and true
semantic re-reads; cable-tray create is an experimental synthesis (no corpus
specimen); Autodesk-viewer certification of all five is the orchestrator's
next gate.

CELL TABLE:

| category | verb | status | proof file | notes |
|---|---|---|---|---|
| conduit run (RbsConduitCurve + ConduitRun + centre-lines) | create | PROVEN-viewer-pending | experiments/mep/conduit/conduit_create.rvt | 3 segments + 2 elbows; also fitting-free variant conduit_create_straight.rvt |
| conduit fitting (elbow) | create | PROVEN-viewer-pending | experiments/mep/conduit/conduit_create.rvt | 2" 90° via shared clone 679082; other sizes/angles need a clone in the template |
| conduit run | read | VALIDATES | (inventory_runs; tests) | full run/graph/size/level inventory |
| conduit run | modify (resize / extend / retype) | PROVEN-viewer-pending | experiments/mep/conduit/conduit_modify.rvt | 686270→1"; 686514 +3 ft; run 688539 → 662475 |
| conduit run | move | PROVEN-viewer-pending | experiments/mep/conduit/conduit_modify.rvt | run 679175 rigid (+4,+3,0) incl. elbows + CLs |
| conduit run | delete | PROVEN-viewer-pending | experiments/mep/conduit/conduit_delete.rvt | run 679090; equipment tap neutralised |
| conduit fitting (elbow) | delete | PROVEN-viewer-pending | experiments/mep/conduit/conduit_delete.rvt | elbow 688548 out of run 688539 |
| conduit type | read / retype | VALIDATES | experiments/mep/conduit/conduit_modify.rvt | 10 types, 5 standards, size tables |
| cable tray run (CableTray + CableTrayRun) | create | VALIDATES | experiments/mep/conduit/cable_tray_create.rvt | EXPERIMENTAL synthesis, no corpus specimen; run/CL category ids inferred |
| cable tray run | read / modify / move / retype / delete | VALIDATES | (same generic verbs) | code paths shared with conduit; no specimen to exercise on |
| cable tray fitting | create | BLOCKED | — | no geometry clone anywhere; the loaded tray-elbow master 662384 has no instance |
| conduit ↔ equipment tap (surface connector) | create | BLOCKED | — | needs an in-place equipment edit (phase 2); created runs have open ends |
