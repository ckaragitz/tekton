# genesis-rebase — THE SUBSTITUTION LADDER v3, REBASED on the CERTIFIED base (2026-08-04)

Charter (post ORCHESTRATOR VERDICT #15 — the RETRACTION): the substitution
engine (`tools/genesis_substitute.py`, the X-rungs) is sound machinery
pointed at a BROKEN base (K1 fails on its own; nothing K1-derived ever
passed).  RE-POINT it at a CERTIFIED base — K4 (family-free, four-registry
coherent, viewer-PASSED) — and make every rung the cleanest possible probe:
IN-PLACE substitution (`rvt.regadd.substitute_elements`: zero registration
motion, same id / row / positions / slots), only the seq-102 object bytes
change, `Global/Latest` + `Global/ElemTable` byte-identical, nothing added,
nothing deleted, every rung certified (validator 0 errors + registry parity
100 % + a `rvt.regdiff` registration diff + the `rvt.regadd` byte-delta
assertion table), and the residue honestly censused.

Territory touched ONLY: `tools/genesis_substitute_v3.py` (new — a WRAPPER
importing `genesis_substitute`'s builders / rung machinery; the original is
NOT edited), `experiments/genesis/subst_k4/*` (10 `.rvt` + per-rung `.json`
+ `probes.json` + `Yn.json` + `Yn_provenance.json` + `CTRL_K4_base.rvt`),
`tests/test_genesis_substitute_v3.py` (new, 11 pass),
`docs/writer/substitution-ladder-v3.md` (new — READ IT for the method, the
per-rung table, the findings, the residue and the verdict-reading guide),
this record.  No existing `src/rvt/*.py`, tool or test edited; every
dependency (`genesis_substitute`, `rvt.regadd`, `rvt.regdiff`, `rvt.reduce`,
`rvt.adocument`, `rvt.genesis.*`, `genesis_triage`, `genesis_assemble`) is
IMPORTED.  No browser / viewer use: the eleven files are LEFT ON DISK for
the orchestrator's queue.

## Result in one screen

**The whole Y-ladder is built and VALID from the certified base K4, by
pure in-place substitution: 10 files (Y1..Y9 cumulative + Y_cat), every one
validator-VALID (0 errors), structurally proven, four-registry coherent,
`Global/Latest` + `Global/ElemTable` BYTE-IDENTICAL to its parent, no
element added or removed, registry parity 100 % by construction and
asserted, regdiff registration sample identical, byte-delta assertion holding
(ONLY the landed slots' object records change).**  Reproduce:
`.venv/bin/python tools/genesis_substitute_v3.py` (~33 s; base certification
is asserted first — the tool REFUSES an uncertified base).

Base: `experiments/genesis/triage/K4.rvt` — VERIFIED CERTIFIED
(`docs/coverage/viewer-certified.json` 'certified': "ZERO family documents
(all 52 removed, FOUR-registry coherent) LOADS"); KD1 and K3 also certified;
K4's lineage = R9 (deepest viewer-PASSED reduction of rstbasic) → K3
(usage-null, certified) → K4 (family/document layer removed) — R9, R5, K3,
K4, KD1 all in the certified list.  The batch's standing control
`experiments/genesis/subst_k4/CTRL_K4_base.rvt` is md5-identical to K4
(f4863b9559bd28521c77d816da361053) and is to be uploaded with EVERY batch.

| # | rung | class layer substituted IN PLACE | landed | ours not landed | sample residue | changed | verdict |
|--:|---|---|--:|--:|--:|--:|---|
| 1 | **Y1** | project PenWidthTableElem (id 2) → our pen table (== Y_pen) | 1 | 0 | 0 | 1 | VALID |
| 2 | **Y2** | browser organizations (4 defaults + 2 house schemes) + navigator constellation + reconcile / construction-set | 12 | 0 | 5 | 8 | VALID |
| 3 | **Y3** | StructSettings / wall-join / auto-join / keynote table (EMPTY) + system | 5 | 1 (InitialViewSettings absent in K4) | 0 | 2 | VALID |
| 4 | **Y4** | RbsWire/Pipe/Duct Settings + Sizes (OUR NEC/ASME/ASTM/SMACNA data) + conduit / cable tray | 8 | 0 | 0 | 8 | VALID |
| 5 | **Y5** | 48 remaining settings singleton / tracker classes | 51 | 0 | 3 | 11 (40 byte-identical) | VALID |
| 6 | **Y6** | built-in-category GStyle catalog, row for row (K4 has 1,172 / 1,407 keys) | 1,172 | 235 | 0 | 1,172 | VALID |
| 7 | **Y7** | 23 mat + 9 fill + 7 line ← our 13 + 5 + 4 (role primaries + slot-fill) | 22 | 0 | 63 | 22 | VALID |
| 8 | **Y8** | 2 plan-bearing levels + level type + phases + set + filter; units / true north / sites / geo-locations / base points / project info | 16 | 4 (filters) | 7 (plan-less levels) | 16 | VALID |
| 9 | **Y9** | 19 project view types; project view / '{3D}' / 2 plans + companions; document sun | 46 | 12 (text-type constellation: K4 has no text types) | 11 | 36 | VALID |
| — | **Yn** | residue census of Y9: 1,333 landed / 2,009 residue in 11 named buckets / 0 unclassified | — | — | — | — | RESIDUE-LISTED |
| P | **Y_pen** | == Y1 (K4 + ONLY the pen table) — the single-change control | (Y1) | | | | (Y1) |
| P | **Y_cat** | K4 + ONLY the catalog, row for row (single-change) | 1,172 | 235 | 0 | 1,172 | VALID |

Independent arbiter batch (pasted, this session): `tools/rvt_validate.py
--quiet experiments/genesis/subst_k4/Y*.rvt CTRL_K4_base.rvt` → 11 × `OK
errors=0 warnings=1` (the warning = the pre-existing Extensible-Storage
decode gap on 1 DataStorage element, untouched).

**Upload order (bisection-first, `probes.json:upload_order_bisection_first`):
Y9, Y6, Y_pen (= Y1's file), Y_cat, then Y2, Y3, Y4, Y5, Y7, Y8 — with
`CTRL_K4_base.rvt` in EVERY batch (if the control fails, the batch is VOID
and no probe verdict is read).**

## THE method, and why it is the cleanest possible probe

Every rung is `substitute_elements` in place: our constructor's OBJECT
record (seq-102) replaces the sample's at the SAME element id — same
ElemTable row (episodes / owner / vintage byte-identical), same record
position, same registry slots.  The ONE variable of a rung is the CONTENT
of our objects at Autodesk's own registrations; every registration variable
the K1 night chased (id band, creation episode / vintage, record order,
ElemTable ownership, ADocument slots) is eliminated BY CONSTRUCTION, not by
assertion.  Our records land on their role correspondent (the X-ladder's
correspondence rules; the most-referenced one when several sample elements
share a role) or, without one, on a free same-class donor slot ranked by
inbound reference count (slot-fill); references among our records are
remapped onto the slots; references to our records that found no slot HERE
resolve by (class, name) against the CURRENT file (a Y9 view finds our L1
level in the slot Y8 landed it in) — else are neutralised and REPORTED.
Nothing is added, nothing is deleted: the sample's surplus and our
slot-less records are LISTED (Yn's two queues).  Full design + verified
post-Y9 wiring: `docs/writer/substitution-ladder-v3.md` §3–§5.

## VERIFIED after Y9 (the deepest file) — the in-place wiring holds

Our plan 'L1 - Ground Floor' (at the sample's plan id 1064656) →
`m_genElemId` 311 = our level 'L1 - Ground Floor' (the sample's 'Level 1'
slot); our 'L2 - Second Floor' → 245423 = our L2; our '{3D}' → 'GEN Working
3D' with its Viewer3d / Viewport / DBDrawing / clip box at the companions'
slots; `AllProjectPhases` (id 1) names the two phase slots and its four
phasing overrides reference OUR phase materials at the material slots Y7
landed them in ('GEN Phase - Existing' 137436, '- Demolition' 417, '- New'
519, '- Temporary' 8798); zero dangling ids.  `LevelPlanViewTracking` and
every other ADocument registry are untouched (byte-identical) and still
index the same ids.

## New findings (evidence [V] — merge into KNOWLEDGE.md; full list in the ladder doc §7)

1. **Zero registration motion is achievable for the WHOLE substitution
   program** [V, 10 rungs]: object-only in-place swaps keep both document
   registry streams BYTE-IDENTICAL for the settings / catalog / palette /
   datum / view layers; registry parity is a property of the method.  On
   K4 the certified re-blocker is zero-motion (`null=True` → `Partitions/21`
   byte-identical).
2. **In place, levels/phases (Y8) and views (Y9) become separable rungs**
   [V]: the X9 coupling (plans stranded from NEW level ids) does not exist
   when ids are preserved.
3. **K4 loads with an INCOMPLETE built-in catalog (1,172 / 1,407 keys)**
   [V]: the K6 "catalog must be COMPLETE" reading was on the K1 lineage
   (retracted); Y6 substitutes 1,172 rows 1:1 and adds none.
4. **Level names live in `m_text`** [V]: `genesis_substitute`'s name
   accessors miss it (every level keyed to the empty name → the first Y9
   build pointed both plans at one level).  Never index empty names.
   (Fixed in v3's `_our_record_name` / `_file_name_index`.)
5. **`_rewire_subset`'s purge can emit a NON-round-trippable object** [V]:
   dropped phasing-override entries left `AllProjectPhases.
   m_arrPhasingOverrides` truncated on plain K4.  A pre-emission record
   self-check (encode → decode → re-encode byte-exact) is mandatory; v3's
   `retarget` refuses such records.  In the cumulative ladder the overrides
   resolve to our Y7 materials by name and nothing is dropped.
6. **`build_X9`'s companion sweep is FILE-WIDE** [V, K1 X9.json]: it
   collects every Viewer / Viewport / DBDrawing / Sun in the file — on the
   K1 ladder X9 DELETED the X2 navigator's own viewer/viewport/drawing
   (1600009..11) and purged the navigator's references to them.  A latent
   defect of the X-ladder (moot for v3: protected slots + no deletions).
7. **Many settings constructors reproduce the sample's object
   byte-for-byte** [V]: 40 of Y5's 51 slots, 3 of Y3's 5, and Y2's 4
   default browser organizations are byte-identical to Autodesk's own
   objects (empty machinery with no free value) — nothing of ours to reject
   there; the byte-delta table lists them as landed-but-unchanged.
8. **Temporary-id determinism is not a safe cross-rung key** [V]: every
   rung allocates our temporary ids from the same watermark band, so ids
   collide across rungs; cross-rung record resolution must be by
   (class, name) first, prior-rung correspondence only as a class-checked
   fallback.

## Diffs / hooks proposed for files OUTSIDE this territory (NOT applied)

* **`tools/genesis_substitute.py` (genesis-substitute)** — (a) `build_X9`:
  grow the companion set FROM the view roots (`own_fixpoint`) instead of
  the file-wide `ids_of(_VIEW_COMPANION_CLASSES)` sweep, which swallows the
  navigator's constellation (finding 6); (b) the name helpers
  (`_rec_name` / `SubstContext.name_of` / `_file_element_names`) should read
  `m_text` for Levels and must not key empty names (finding 4); (c)
  `_rewire_subset` should ROUND-TRIP-CHECK the records it purges and refuse
  rather than emit a truncated object (finding 5).
* **`src/rvt/regadd.py` (genesis-addfix)** — `substitute_elements` is the
  right primitive and needs nothing for this ladder; a `seqs` doc note that
  (102,) alone is the "object-only, wiring-kept" mode this stream relies on
  would help the next reader.
* **`src/rvt/validate.py`** — the registry-parity / four-registry-coherence
  layer this ladder asserts per rung is still not in the arbiter (the v2
  ladder's diff, repeated).
* **`docs/coverage/viewer-certified.json` (orchestrator)** — add the ten
  Y files + `CTRL_K4_base.rvt` as they read out; every Y report already
  names its base + certification + control for the record.
* **`tools/sync_plugin.py`** — this stream adds NO `src/` module (a tool
  only), so nothing new to sync; the pre-existing plugin-drift test is
  untouched.

## Open questions (need the viewer / a decision)

* The ten verdicts, IN UPLOAD ORDER (`probes.json:upload_order_bisection_first`);
  every branch of the interpretation is pre-stated per probe
  (`if_PASS` / `if_FAIL`) and in the ladder doc §8.
* If EVERYTHING PASSES: the next variable is REGISTRATION — the ADD path
  for our slot-less records (Y6's 235 catalog rows, Y8's 4 filters, Y9's
  text-type constellation, Y3's InitialViewSettings), now testable ONE
  registration at a time on this certified base with a certified control;
  and Yn's residue queue (definitions removal, the subcategory / curtain /
  annotation constructor gaps, the HVAC product database, datum/room
  content removal, the linked-model removal).
* Whether the two token questions (our solid fill under our own name; no
  'Default'-named material) matter — they ride on Y7's slots (Y6 PASS +
  Y7 FAIL isolates them).
* The container layer (History / DIT / PartitionTable lineage,
  `Formats/Latest`, the Forge corpus inside `Global/Latest`) is untouched by
  design (own-save + counsel territory); an in-place ladder leaves the
  ADocument the sample's byte for byte.

## Proposed next tasks (orchestrator decides)

1. Upload the batch (control + Y9, Y6, Y1(=Y_pen), Y_cat first; the
   intermediates if Y9 fails); read the control FIRST.
2. If Y9 PASSES: build the ADD-PATH ladder on THIS certified base, one
   registration variable per rung (X0-style controls: Autodesk's own row
   verbatim through the add path first, then ours), reusing this tool's
   base-certification + control discipline; and start the residue rungs
   (definitions GC-removal, external-link removal, datum-content removal)
   as further in-place/removal rungs from Y9.
3. Fold findings 4–6 back into `genesis_substitute` (the X-ladder is still
   the constructor library) and finding 1's method into the genesis
   assembler: the genesis base of record should be built the IN-PLACE way
   from a certified skeleton.
4. Add the passing Y files to `viewer-certified.json` as they read out —
   each is a certified base for the next layer.

## Verification

* `tools/rvt_validate.py --quiet experiments/genesis/subst_k4/Y*.rvt
  experiments/genesis/subst_k4/CTRL_K4_base.rvt` → 11 × `OK errors=0
  warnings=1` (pasted above); per-rung reports carry the structural proof,
  the byte-delta assertion table, the parity table, the registration-diff
  sample and the four-registry census.
* `.venv/bin/python -m pytest tests/test_genesis_substitute_v3.py -q` →
  **11 passed** (base-certification gate; the K1 refusal; slot-fill plan
  correctness on X7/K4; protected-slot refusal; the dangling-reference
  refusal; end-to-end Y1/Y_pen with every byte-delta assertion; Y1's
  object is ours + m_id follows the slot; end-to-end Y_cat (1,172 rows,
  235 not added, only those records change, same category keys, our
  values); built-ladder report law; residue accounting; manifest ordering).
* Full suite: see BRANCH STATE.

## BRANCH STATE

No VCS (plain directory).  New, uncommitted files:
`tools/genesis_substitute_v3.py`, `tests/test_genesis_substitute_v3.py` (11
pass), `docs/writer/substitution-ladder-v3.md`,
`docs/inbox/genesis-rebase.md` (this file), and under
`experiments/genesis/subst_k4/`: `Y1 Y2 Y3 Y4 Y5 Y6 Y7 Y8 Y9 Y_cat .rvt`
+ one `.json` report each + `Yn.json` + `Yn_provenance.json` (+ `.txt`)
+ `probes.json` + `CTRL_K4_base.rvt` (md5-identical to the certified base
K4).  Every emitted `.rvt` = validator VALID (0 errors), structural proof
clean, four-registry coherent, `Global/Latest` + `Global/ElemTable`
byte-identical to its parent, registry parity 100 % (asserted), byte-delta
assertion holding.  Full suite this session (`.venv/bin/python -m pytest
tests/ -q --ignore=tests/oracle`): **923 passed, 2 failed** (925 tests,
16:10).  This stream's 11 tests are among the 923.  The 2 failures are the
pre-existing, other-stream ones every recent record lists — both in
`tests/test_provenance.py` (`test_G0_resource_refs_are_counted`,
`test_G0_identity_dit_usernames_still_leak`: STALE assertions pinning the
pre-genesis-2 G0's defects; the rebuilt G0 no longer leaks, owner = the
provenance stream); neither touches this stream's files.  (The
`test_plugin_sync` drift earlier records list did NOT fail this run.)
STOPPED AT READY — the eleven files (control + ten probes) await the
orchestrator's viewer batch; the residue queue + the add-path ladder are the
recorded next work.
