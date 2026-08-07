# inbox — render-instances (INSTANCE-RENDER PROBES + THE ROOM'S FAMILY LAYER, BISECTED)

Stream: **render-instances** (2026-08-04).  Charter (ORCHESTRATOR VERDICTS #22):
(A) LOAD IS NOT RENDER — do PLACED INSTANCES of OUR families produce viewable
geometry? build the cleanest render probes on the certified genesis base; and
(B) THE ROOM'S DEFECTIVE FAMILY — one file per family so the viewer names the
one bad family in the electrical room's set.  Territory touched ONLY:
`tools/render_probes.py` (new), `experiments/ifc_room/render_probes/**`,
this record.  No existing `src/rvt/*.py`, tool, test or sample was edited
(`rvt.famgen` / `rvt.famload` / `rvt.mutate` / `rvt.commit` / `rvt.validate`
/ `rvt.ifc` and `tools/ifc_intent.py` are IMPORTED, never modified).  No
browser: the twelve upload files + `probes.json` + a byte-identical control
sit on disk for the orchestrator's viewer gate.

**The charter's premise turned out to be false, and the record leads with
that** (§1).  The deliverables are re-aimed at the REAL failing layer (§2–§4)
and every claim in §1 is reproducible from the file bytes:
`python tools/render_probes.py --only forensics`.

## Result in one screen

* **VERDICT #22'S PREMISE IS REFUTED — from the bytes, not the ledger prose.**
  The verdict reads *"walls + ONE loaded family + a PLACED instance
  (stage_L8_lp4) PASSES => the FULL-family stage failing means ONE family is
  defective."*  Measured: `stage_L8_lp4.rvt` is ZA_deep + **ALL 8 room
  families** (the 2500 A house switchboard INCLUDED), **0 walls, 0 placed
  instances** — 9 save units / 8 ContentDocuments / 0 `SWall` / 0
  `FamilyInstance`.  (`lp4` is only the LAST of the 8 chained
  `load_family_into_project(place=False)` loads; build_record stage L.)  Its
  viewer result was **"Design is empty"** — a symbol-only file the extractor
  short-circuits; NOT an audited pass of the family layer.  Meanwhile
  `walls_only` (0 families, 4 walls) PASSES a real audit, and
  `stage_W_loaded_walls` (8 families + 4 walls) FAILS — and the FAIL file
  differs from `stage_L8_lp4` by **EXACTLY the 4 wall records** (byte-
  identical, modulo id, to the PASSING `walls_only` walls) + 4 ElemTable
  rows + BasicFileInfo identity: **0 existing records changed, 0 lost, the
  8 embedded family units record-identical** (§1).  So: **no family is shown
  defective and none is exonerated; the loaded family layer has never
  survived a real audit on the genesis base — the walls merely FORCED
  one.**  Corollary: "rvt.mutate creation proven on the genesis lineage"
  holds for **walls only** — no file with a placed instance of OUR family
  has ever passed anywhere (the certified loads L1a / L_v2 / L_downlight
  are `place=False`; their 497 instances are the rst sample's own).
* **THE INSTRUMENTS ARE BUILT** (12 files, all `tools/rvt_validate.py`
  **VALID 0 errors**, four registries coherent, identity PASS, `probe_batch
  check` **ADMISSIBLE**, base = certified ZA_deep + a byte-identical control):
  - **3 render probes** `R_inst_{box,panel,downlight}.rvt` = ZA_deep + ONE
    loaded family + ONE placed free-standing instance, **NO walls** — the
    instance is BOTH the render subject AND the model element that forces
    the audit.  The **first clean instance-on-genesis tests** (§3).
  - **8 bisection files** `F_<tag>.rvt` = ZA_deep + ONE room family + the
    room's 4 walls (the audit-forcing agent, proven audit-clean alone) —
    one per family (§4).  Read WITH the R_inst set they separate {a
    defective single family} from {any-family / loader-on-genesis defect}
    from {wall × loaded-family interaction} (matrix in `probes.json`).
* **A BUILT-IN RENDER A/B (found, not designed).**  The two loaders differ
  on the render-relevant axis: `rvt.famgen.loader` (box, panel — the room's
  mechanism) authors the FamilySymbol's seq-103 rep as a real **GElement**
  (3,095 B) with `m_pGeomTable` + `m_geomSteps` on the symbol object =
  **BAKED symbol geometry**; `rvt.famload` (the downlight's own certified
  path) writes a **SerializedDummy** symbol = relies on Revit REGENERATION.
  All three embed the solids in the family document (box 1, panel 1,
  downlight 8 `ExtrusionElem`).  Box/panel render + downlight not => symbol
  geometry must be baked; all render => the extractor draws from the document
  or regenerates; none render => baked geometry is needed on the INSTANCE
  rep or the symbol GElement grammar (loader hypothesis [H]) is off (§3).
* **THE STATIC PER-FAMILY ASSAY FINDS NO DEFECT IN ANY FAMILY, INCLUDING THE
  SWITCHBOARD** (§5): all 8 room `.rfa` are family-mode **VALID 0/0**; the
  house switchboard is composed from the certified transformer's building
  blocks (delta vs the PRL panel = part type 16 vs 14, floor-standing, +2
  parameters, connector on the top cap — nothing structural).  All 8 fail
  the **same 7 v2 provenance checks uniformly** = the OLD emitter's donor-
  graft debt (`FamilyProduct.write` → `skeleton.emit_family_rfa`, 270,336 B,
  not the clean v2 278,528 B) — it does NOT discriminate the switchboard and
  it lives in the STANDALONE `.rfa` only (the loader builds embedded
  documents from the FamilyDoc object).  Our render `.rfa`
  (`render_probe_box.rfa`) went the clean path: **VALID 0/0 + provenance
  fully clean.**
* **A v2-emitter finding for the famgen owner**: `emit_family_rfa_v2`'s
  anti-donor guard is an UNALIGNED i64 byte scan and false-positives on any
  family built at project-scale ids (watermark+1 = `0x16780D…` contains the
  window `78 16 00 00 00 00` → 5752 = a donor id).  Standalone `.rfa` must
  be built at `start_id=1000` (the convention); the guard should scan the
  DECODED id set, not raw bytes (§5.4).

## §1  The premise, refuted (reproducible)

`tools/render_probes.py --only forensics` re-derives, from the six ifc-room
files' own bytes:

| file | family docs | walls | instances | recorded viewer verdict |
|---|--:|--:|--:|---|
| ZA_deep (base) | 0 | 0 | 0 | PASS (certified, control in batches 20/21) |
| **stage_L8_lp4** | **8** | **0** | **0** | 'PASS' — viewer showed **"Design is empty"** |
| walls_only / _unjoined | 0 | 4 | 0 | **PASS** — real audit; tree = the level node |
| **stage_W_loaded_walls** | **8** | **4** | 0 | **FAIL** — Revit-DocumentCorruption, -1073742517 |
| electrical_room_2500a | 8 | 4 | 8 | FAIL (audit) |

**Diff `stage_L8_lp4` (PASS) vs `stage_W_loaded_walls` (FAIL)** — stream by
stream, then record by record over every save unit and all three seqs (the
corrected 12/16-byte record framing):

* streams differing: `BasicFileInfo` (identity GUID/path), `Global/ElemTable`
  (+4 rows), `Partitions/21` (+the wall records).  `Global/Latest`,
  `ContentDocuments`, `History`, DIT, `PartitionTable`, `Formats/Latest` —
  **IDENTICAL**.  The wall commit did the minimal splice: it never touched
  the ADocument or the content registries.
* record delta: unit 0, seqs 101/102/103 each gain the 4 wall records
  (1472996–1472999); **0 existing records changed, 0 lost**, all psize
  trailers intact, 0 leftover bytes, walker clean; **units 1..8 (the 8
  embedded family documents) record-identical.**  ElemTable: exactly 4 new
  rows (episode 1016, matching the loaded rows' pattern), watermark
  1472995 → 1472999, footer/graveyard otherwise identical; the History
  invariant (count == max modified-episode + 1 = 1017) holds in every file.
* **the wall layer is not the discriminator**: the 4 wall objects in the
  FAIL context (`stage_W`) are **byte-identical modulo their own ids** to
  the 4 walls in the PASS context (`walls_only`) — same header, same object,
  same rep, in all three seqs; and both carry the same 11 dangling refs per
  wall (tolerated: `walls_only` PASSED with them).

**Reading.**  The two failing files are (walls) + (loaded families).  The
walls pass alone; the families' only "pass" (`stage_L8_lp4`) is an empty-
design short-circuit — a file with symbols and NO model elements gives the
extractor nothing to regenerate, so Revit's document-corruption audit (the
death mode `-1073742517`) plausibly never ran on the family layer.  Adding
walls (real model elements) forces the audit — and it FAILS.  Nothing in
hand attributes the failure to ONE family (the FULL 8-family load "passes"
its empty non-test with the switchboard aboard), and nothing exonerates any
family (no audited pass exists).  The two open readings — {the loaded family
layer fails the audit for ANY family on the genesis base} vs {a wall ×
loaded-family interaction} vs {one defective family after all} — are
exactly what the R_inst + F_ sets separate.  Note the loader IS audit-proven
on the rst sample base (L1a, L_downlight_loaded, L_v2 — all viewer PASS with
thousands of real elements around them); what has never been audited is the
loader's output ON THE GENESIS BASE ZA_deep.

**Consequences the orchestrator should carry:**
1. Verdict #22's line *"the loading mechanism is exonerated"* and *"suspect:
   the ad-hoc 2500 A house switchboard"* rest on the misreading; retract
   pending the F_/R_inst readout.  The switchboard has NO evidence against
   it (§5) — F_msb tests it under a real audit for the first time.
2. *"rvt.famload + rvt.mutate creation are proven on the family-free genesis
   lineage"* — proven for **walls** (walls_only, both variants).  Family
   INSTANCE placement on ZA_deep is **UNJUDGED** (the only instance file,
   `electrical_room_2500a`, failed, entangled with the family layer).  R_inst
   is the first clean test of `add_family_instance` on the genesis base.
3. The (A) LOAD-IS-NOT-RENDER claim stands for **walls** (walls_only: the
   tree holds only the level node — walls emit no baked geometry).  For
   family **instances** it is UNTESTED: the "walls+panel file translates to
   'Design is empty'" observation was `stage_L8_lp4`, which has NO placed
   instances — an empty design is the correct output for a symbol-only file
   and says nothing about instance geometry.  R_inst answers it.
4. `stage_L8_lp4` is the **newest 'certified' entry**, so `probe_batch stage`
   picks it as the DEFAULT control source — a poor control (its "pass" is
   the empty-design non-test).  Stage this batch with the control pinned to
   ZA_deep (command in §6).

## §2  The R_inst render probes (charter A) — `experiments/ifc_room/render_probes/`

Each = **ZA_deep + ONE loaded family + ONE placed instance, NO walls**,
placement by the room's own stage-E recipe (R5 specimen scaffolding injected,
`Document.add_family_instance` free-standing pattern `symbol == masterSymbol`
/ `host −1` / level 311, the intent-style orientation frame in `m_Trf`, the
cross-category specimen residue scrubbed — category patched, the door
`FamInstSpec` dropped, **0 dangling refs**), committed by
`commit_new_elements`.  Decoded read-back of every file confirms the pattern.

(md5 prefixes are of the committed build; `probes.json` / `render_probes.json`
hold the authoritative full hashes — any rerun re-mints GUIDs, so re-hash
after a rebuild.)

| probe | family (loader) | symbol / family / instance | placement | symbol seq-103 rep | md5 |
|---|---|---|---|---|---|
| **R_inst_box** | OUR **bare solid box** — 1 `ExtrusionElem`, 3 dim params, one type, **no connector, no contract** (`rvt.famgen.loader`, core ids [124, 113160]) | 1472558 / 1472553 / 1472560 | free at (2, −2, 0) m, yaw 0, Electrical Equipment, no connector manager | **GElement** 3,095 B, geom table + steps = **BAKED** | `c21f390e` |
| **R_inst_panel** | the room's **PRL1X (LP-4)** '225A MCB 42ckt' (`rvt.famgen.loader`, core [124, 113944]) | 1472582 / 1472566 / 1472584 | LP-4's intent point (4.455, −0.55, 1.543) m, the intent's UPRIGHT 3×3, Electrical Equipment, connector manager | **GElement** 3,095 B = **BAKED** | `6d8a34af` |
| **R_inst_downlight** | the IFC-derived **downlight** 'CP-6-LED', 8 solids (`rvt.famload`, core [127] = the Lighting-Fixtures projection row, present in ZA_deep) | 1472638 / 1472615 / 1472639 | free at (0, −2, 2.4) m (ceiling height), yaw 0, Lighting Fixtures, no manager | **SerializedDummy** = regeneration-only | `2aefe4ce` |

`R_inst_box` is the purest subject: no category subtlety (the Electrical
Equipment row 124 the room binds), no connector, no tagging contract — one
baked six-face solid, placed.  `R_inst_panel` reproduces the room's exact
LP-4 placement minus the walls it would sit on.  `R_inst_downlight` reads
LAST (its own loader, dummy symbol).  **Expected model tree if an instance
RENDERS** (written into `probes.json` per probe): level node
`'L1 - Ground Floor [311]'` → a CATEGORY node ('Electrical Equipment' /
'Lighting Fixtures') → the family → the type → ONE instance node with an eye
toggle, and the 3D view shows the box / the panel enclosure / the downlight
assembly at the stated position.  If the file translates but the tree still
holds only the level node → LOAD-but-no-RENDER for instances (the symbol
geometry is not drawn).  If it FAILS with `-1073742517` → the family/loader
layer fails the audit with NO walls present (the deeper (B) finding).

**Wall-hosted variant — NOT built, recorded.**  It needs walls + a face-
SketchPlane specimen (`rvt.hosting`); walls + a loaded family is the very
combination that FAILS, so a wall-hosted probe would read on two confounded
variables — and an instance hosted to an UN-RENDERED wall has nothing to sit
on.  The free-standing set is primary; wall-hosting waits behind the F_
bisection and behind baked wall geometry (`probes.json` carries the entry as
`kind: not_built` with the reason).

## §3  The render A/B — what the loaders bake

Measured on the three built files (`render_reps` in `probes.json`):

* famgen loader (box, panel): the FamilySymbol's seq-103 record is a
  **GElement (0x89e, 3,095 B, 1 subnode)**, and the seq-102 symbol object
  carries **`m_pGeomTable` + `m_geomSteps`** — `build_symbol_geometry`
  authors "the seq-103 GElement the placed instances display" from OUR
  extrusion's solid (grammar inferred from one specimen — its acceptance
  hypothesis [H], now testable).  The instance rep = the formulaic 300-byte
  GElement{GInstance{InstanceInfo}}.
* famload (downlight): symbol seq-103 = **SerializedDummy (0xf2c, 2 B)**,
  no geom table/steps — the ifc-family record's H2 ("Revit regenerates the
  symbol graphics from our 8 solids").
* all three: the embedded family document carries the `ExtrusionElem`
  GElement solids (1 / 1 / 8) — baked geometry exists IN THE FILE.

**Calibration from walls (charter A's read-first item, measured):** every
NATIVE sample wall carries a **GElement** seq-103 rep — rst 9/9, rac
60/60, median body **~10–13 KB** = the baked wall solid (they render in the
sample projects).  Every wall WE create is a **SerializedDummy**: `walls_only`
4/4; V22 (certified) = the rme sample's 60 native GElement + OUR 1 dummy;
V26 = 166 + OUR 4 dummy.  So OUR created walls have never carried baked
geometry — including the long-certified V22/V26 ones, whose translation
proved LOAD, never RENDER (nobody ever checked whether OUR wall drew).  This
confirms verdict #22(A) with numbers and gives the render track its wall
target: `add_wall` must author a ~10 KB wall-solid GElement, not a
SerializedDummy.  It also frames the family case exactly: our famgen-loaded
SYMBOLS carry the same KIND of baked GElement native walls render with.

So the set is a controlled A/B on the render mechanism:
- box + panel RENDER, downlight NOT → symbol geometry must be BAKED (the
  extractor does not regenerate — consistent with the walls finding), and
  the famgen loader's symbol GElement is a valid render path;
- all three RENDER → the extractor draws from the family document (or
  regenerates); RENDER is cheap;
- none RENDER → the render path needs baked geometry on the INSTANCE rep,
  or the symbol GElement grammar [H] is off → the render track's next work;
- (the categories differ — Electrical Equipment vs Lighting Fixtures — but
  BOTH projection rows exist in ZA_deep, 124 and 127, and both loaders bound
  their core id, so the category axis is controlled; the Walls row is the
  one truly absent, and walls are the elements known not to render.)

## §4  The F_ per-family bisection set (charter B, re-aimed)

`F_<tag>.rvt` = ZA_deep + ONE room family (rebuilt by the SAME constructor +
kwargs stage L used, loaded `place=False`) + the room's 4 walls (mode
'min' — the exact wall layer of the certified `walls_only`).  The walls are
the audit-forcing agent that `stage_L8_lp4` lacked.  All 8 built and gated:

| probe | family | part type | md5 |
|---|---|--:|---|
| F_msb | Switchboard MSB 2500A 480Y/277 (**the accused**) | 16 | `10e6ebb3` |
| F_dp1 / F_dp2 | Distribution Panelboard 400A MB 42sp | 14 | `c20eae0c` / `ef1457ad` |
| F_lp1 / F_lp2 / F_lp3 | Lighting Panelboard 100A MLO 30sp | 14 | `84d96a24` / `40131cdf` / `a37b1deb` |
| F_lp4 | Receptacle Panelboard 225A MB 42sp (PRL1X) | 14 | `ad9dc95f` |
| F_t1 | Dry Type Transformer 150kVA 480-208Y/120 | 15 | `5f6f3866` |

**Reading (also in `probes.json` → `reading_the_matrix`):** exactly one F_
FAILs → THAT family is defective (the charter's hypothesis, now under a
real audit).  **ALL F_ fail** → no single family is guilty: the loader-on-
genesis-base output fails the audit for ANY family once an audit-forcing
element is present — cross-read `R_inst_panel` (same PRL1X family + an
instance, no walls): if it PASSES while `F_lp4` FAILS the fault is the wall ×
loaded-family interaction (the wall commit over a file carrying embedded
family documents); if it too FAILS the fault is the family/loader layer.
All F_ PASS → each family survives alone; the failure needs the 8-family load
or is specific to `stage_W`'s construction (re-upload `stage_W_loaded_walls`
as the confirming control).

## §5  Static per-family assay (charter B: "you may find the defect statically")

Every check ran NOW on the room's 8 `.rfa` as built
(`experiments/ifc_room/families/`), results in `render_probes.json` →
`stages.assay`:

1. **Certified family-mode validator: VALID, 0 errors, all 8** (+ 0
   warnings).  The raw project-mode arbiter shows the known family-shape
   calibration residuals the authentic Autodesk donor `.rfa` also shows
   (worse) — a calibration gap, not a defect.
2. **v2 provenance ledger (`provenance_scan_v2`): all 8 FAIL the SAME 7
   checks, uniformly** — `zero_dangling_element_refs`,
   `zero_donor_id_byte_hits`, `zero_donor_name_strings`,
   `owner_family_is_ours`, `footer_blob_not_donor`, `no_donor_end_parity`,
   `end_record_is_constant`.  That is the assay's known signature: the room's
   stage F emits through the OLD `FamilyProduct.write` →
   `skeleton.emit_family_rfa` (donor `Global/Latest` = Autodesk's table
   family document + donor footer + 82 B of donor parity; every file is
   **270,336 B** = the old emitter's size, vs **278,528 B** for the clean v2
   families).  Uniform across all 8 → **it does not single out the
   switchboard**; and it is confined to the STANDALONE `.rfa` — the stage-L
   loader builds each embedded family document from the `FamilyDoc` object,
   so the loaded/failing project files contain OUR constructed documents,
   not the donor Latest.  (Recommendation §6: switch stage F to
   `emit_family_rfa_v2`.)  Our own `render_probe_box.rfa`, emitted through
   the clean path, is **VALID 0/0 + provenance fully clean** — the clean path
   works when used.
3. **Switchboard vs a factory panelboard (structure)**: `make_house_switchboard`
   uses the SAME building blocks as the certified `make_transformer` (floor-
   standing box + top-cap connector) and `make_panelboard` (the 11-name
   tagging contract).  Measured delta MSB vs LP-4: part type 16 vs 14;
   `work_plane_based` False vs True (like T1); +2 parameters (`Sections`,
   `FeederEntry`, 16 vs 14 ParamElemFamily); 43 vs 41 elements; 1
   connector each.  **Nothing structural distinguishes it from families that
   load; the assay finds no per-family discriminator anywhere in the set.**

**§5.4 — v2 emitter guard finding (for the famgen owner).**  Building the
render box at `start_id = watermark + 1` (1472525 = `0x16780D`),
`emit_family_rfa_v2` raised *"donor element ids survive in the payload:
{hits: 3, distinct: 1, examples: [5752]}"*.  Element 5752 in the donor
archetype is a `LeaderStyle` ("Diagonal 1/8\""), which our document does not
reference — the guard's donor-id detector scans the ADocument payload as
UNALIGNED little-endian i64 windows, and the byte window `78 16 00 00 00 00`
inside our project-scale ids reads as `0x1678` = 5752 when followed by a zero
byte.  The same box at `start_id=1000` emits cleanly, and every other
stream's standalone `.rfa` is built at `start_id=1000`, which is why nobody
tripped it.  Effect: the v2 emitter cannot re-emit a family from a project-
scale build.  Suggested fix (their territory): decode the payload's id set /
scan aligned typed leaves rather than raw unaligned windows.  Our tool follows
the convention (standalone `.rfa` at `start_id=1000`, the LOADED copy rebuilt
at watermark+1, as the room's stage L does).

## §6  Requests for the orchestrator

1. **Correct verdict #22 in the ledger / KNOWLEDGE.md**: `stage_L8_lp4` = the
   FULL 8-family load, no walls, no instances; its "PASS" = "Design is
   empty" = an unaudited symbol-only translation; the "one defective family"
   reading and the switchboard's blame are unsupported; creation-on-genesis is
   proven for WALLS only; instance placement on ZA_deep is unjudged (§1).
2. **VIEWER-GATE this batch** — control pinned to ZA_deep (NOT the gate's
   default, `stage_L8_lp4`, whose "certification" is the non-test):
   ```
   .venv/bin/python tools/probe_batch.py stage \
       experiments/ifc_room/render_probes/R_inst_box.rvt \
       experiments/ifc_room/render_probes/R_inst_panel.rvt \
       experiments/ifc_room/render_probes/F_lp4.rvt \
       experiments/ifc_room/render_probes/F_msb.rvt \
       experiments/ifc_room/render_probes/F_{dp1,dp2,lp1,lp2,lp3,t1}.rvt \
       experiments/ifc_room/render_probes/R_inst_downlight.rvt \
       --control-from experiments/genesis/subst_k4/residue_a/ZA_deep.rvt
   ```
   Reading order: **CTRL** (round validity) → **R_inst_box** (purest render +
   first clean instance-on-genesis test) → **R_inst_panel** → **F_lp4** (one
   loaded family under a real audit) → **F_msb** → the rest of the F_ set as
   budget allows → **R_inst_downlight** last.  Read the model tree of the
   R_inst files (a rendered instance = a node under the level; §2), not just
   the card verdict.  The verdict matrix is in `probes.json` →
   `reading_the_matrix`.
3. **KNOWLEDGE.md lines to merge:** (i) *the two loaders differ on symbol
   geometry — `rvt.famgen.loader` bakes a GElement symbol rep (+ geom table
   / steps on the symbol object) from our solid; `rvt.famload` writes a
   SerializedDummy symbol relying on regeneration; both embed the solids in
   the family document* (§3); (ii) *a symbol-only file (loaded families, no
   model elements) yields "Design is empty" — an extractor short-circuit that
   is NOT an audited pass; certifying a family layer requires an audit-forcing
   model element (a wall or a placed instance) in the same file* (§1); (iii)
   *the v2 emitter's donor-id guard false-positives on project-scale start
   ids; standalone `.rfa` are built at `start_id=1000`* (§5.4).
4. **Route to owners** (not this territory): switch `tools/ifc_intent.py`
   stage F from `FamilyProduct.write` to `emit_family_rfa_v2` (the family-
   genesis stream's standing request — the room's 8 `.rfa` still carry the
   donor debt, §5.2); the guard fix in `rvt.famgen.famdoc_adoc` (§5.4).
5. **Plugin sync** (standing, not this territory): `tools/render_probes.py`
   is a new tool the plugin bundle guard may or may not track;
   `python tools/sync_plugin.py` remains the known fix for the pre-existing
   `test_plugin_sync` failure.

## §7  Reproduce

```
.venv/bin/python tools/render_probes.py                   # all four stages, ~35 s
.venv/bin/python tools/render_probes.py --only forensics  # §1: the matrix + the PASS/FAIL diff
.venv/bin/python tools/render_probes.py --only assay      # §5: per-family static assay
.venv/bin/python tools/render_probes.py --only rinst      # §2/§3: the render probes
.venv/bin/python tools/render_probes.py --only fset       # §4: the F_ bisection set
.venv/bin/python tools/rvt_validate.py experiments/ifc_room/render_probes/<f>.rvt   # 0 errors each
.venv/bin/python tools/probe_batch.py check experiments/ifc_room/render_probes/{R_inst_*,F_*}.rvt  # ADMISSIBLE
```

Full suite this session (`.venv/bin/python -m pytest tests/ -q
--ignore=tests/oracle`): see BRANCH STATE.

## BRANCH STATE

* **status**: DONE — READY FOR THE VIEWER QUEUE (nothing uploaded; the gate
  check is ADMISSIBLE).  Stopped at READY.
* **the load-bearing finding**: verdict #22's premise is refuted from the
  bytes (§1, reproducible via `--only forensics`); the deliverables were
  re-aimed accordingly and BOTH charter items still land — three R_inst
  render probes (charter A) and one F_ file per family + the static per-
  family verdict (charter B) — now correctly framed.
* **files** (all under `experiments/ifc_room/render_probes/`, md5 in §2/§4;
  each rebuild mints fresh GUIDs, re-hash after any rerun):
  `R_inst_box.rvt`, `R_inst_panel.rvt`, `R_inst_downlight.rvt`, `F_msb.rvt`,
  `F_dp1.rvt`, `F_dp2.rvt`, `F_lp1.rvt`, `F_lp2.rvt`, `F_lp3.rvt`, `F_lp4.rvt`,
  `F_t1.rvt`, `CTRL_ZA_deep_render.rvt` (md5 `56308637…` == ZA_deep),
  `probes.json`, `render_probes.json` (the full build/assay/forensics
  record), `families/render_probe_box.rfa` (clean, VALID 0/0, provenance
  clean); `_build/` holds the intermediate loaded files + per-load reports.
* **gates passed (all 12 files)**: `tools/rvt_validate.py` VALID 0 errors
  (1 warning each = ZA_deep's own inherited ES-blob decoder gap); four
  registries coherent; identity PASS; `probe_batch check` ADMISSIBLE, every
  probe's base = ZA_deep `[certified]`; control byte-identical to the base.
* **static per-family verdict**: NO defect found in any of the 8 (family-mode
  VALID 0/0; the switchboard structurally clean; the shared old-emitter
  provenance debt is uniform, standalone-only, and non-discriminating).
* **next action (orchestrator)**: the §6.2 stage command; the readout names
  the layer per `probes.json` → `reading_the_matrix`.  If `R_inst_box` PASSES
  and its model tree shows the instance node, RENDER is a real second gate
  and the render track has its baseline; if the whole F_ set FAILS the
  frontier is the loader-on-genesis-base under audit, not any family.
* **NOT VIEWER-TESTED**: every "VALID" here is the machine gate; no
  acceptance claim is made.  Status of every file: PROOF-ONLY (the base is
  the sample-derived genesis lineage; our added layer — families, walls,
  instances — is ours).
* **full suite** (`.venv/bin/python -m pytest tests/ -q --ignore=tests/oracle`,
  17:07): **1206 passed, 3 failed** — the SAME 3 pre-existing cross-stream
  failures every sibling record lists (`test_plugin_sync.py::
  test_plugin_is_in_sync_with_source` = the standing plugin-bundle drift,
  fix `tools/sync_plugin.py`; and the two `test_provenance.py::test_G0_*`
  checks written against the pre-rebuild G0), **ZERO new failures**.  This
  stream adds NO test file (`tests/` is outside the territory); the tool is
  exercised end to end by the pipeline run itself, whose every output
  passes the certified validator + registry + identity + batch gates.
