# inbox: manipulate — edit / move / retype / delete EXISTING elements

Stream: MANIPULATE ANY GIVEN FILE (a user uploads a project; we edit it and
hand it back). Territory touched: `src/rvt/manipulate.py`,
`experiments/manipulate/*`, `tests/test_manipulate.py`,
`docs/writer/manipulation.md`, this note. No edits to
`mutate.py`/`commit.py`/`objects.py`/`encode.py` or any existing test.

## What was delivered

`src/rvt/manipulate.py` (change/delete path over `mutate.Document.from_file`):

* `delete_element(doc, eid, cascade=False)` → `DeletePlan` — 3 records
  (seq 101/102/103) removed from unit 0, `ElemRec` dropped (count −1,
  **watermark kept**), partition-header count fixed; `dependency_report`
  builds the hard-dependency closure (host / owned / associated-level /
  annotation-leaf, §3.2 of the doc) + the soft referrers; without cascade a
  non-trivial closure raises `DependentsError` carrying the full report
  (fail-loudly); `cascade=True` deletes the closure (bounded `max_depth=8`,
  `max_cascade=2000`, both surfaced) and NEUTRALISES every referrer
  (scalar id → −1, id-in-list removed, structured entry dropped, but
  pointed-to sub-objects such as `Connector`s are kept and cleaned inside so
  positional `m_nIndex` back-refs stay valid).
* `modify_element(doc, eid, {json_path: value})`, `set_level_elevation`,
  `set_param` / `rename_panel` (BIP −1140078) / `set_mark` (BIP −1001203),
  `find_param`, `describe`.
* `move_instance(doc, eid, xyz, rotation, delta, include_owned)` — rewrites
  `InstanceInfo.m_Trf.m_or` (+3x3), mirrored `m_instOrigin`, seq-103 rep
  transforms + boxes, seq-101 header bbox; owned child instances (a table's
  chairs) move rigidly with it.
* `retype_instance(doc, eid, new_symbol_id)` — free/face pattern only;
  same-category check, same-family unless `allow_family_change`; rewrites
  `m_symbolId`/`m_masterSymbolId`, rep `GInstance` symbol ids, header
  appearance/deletion parents. Host-cut doors/windows raise (phase 2).
* `commit_plans` / `commit_session` — re-emit unit 0 (re-blocked,
  `ISIZE == hdr*A + C + adj(flags)`), re-emit `Global/ElemTable`, ECC-frame
  both, `write_cfb`. Embedded family units copied byte-for-byte. Save-history
  streams untouched (minimal-commit policy, same as `commit.py`).
* `verify_manipulated(out, deleted_ids, edited_ids)` — CRC / ECC / walker /
  ISIZE identity / stamps / sentinels / header count / id-set identity /
  deleted-gone / edited-decode-clean.
* Precondition: an element is only edited if its unedited object re-encodes
  byte-exact (`EditSession._orig_bytes_check`); ES-blob elements refuse
  loudly (still deletable).

## Evidence

* **8/8 proofs PASS** (`experiments/manipulate/proofs.json`, `README.md`):
  M1–M4 on rmebasic AND M1–M4 on racadvanced (a file the tools were never
  developed against): each output has 0 CRC failures, 0 ECC mismatches, 0
  walker errors, 0 ISIZE mismatches, stamps ok, sentinels last, header count
  == ElemTable count, unit-0 seq-102 ids == ElemTable ids, and a semantic
  re-read (`Document.from_file(out)`) proving the change (element gone /
  elevation, name, mark re-read / Δ = (5,0,0) ft, symbol swapped).
* `tests/test_manipulate.py`: 8 passed. Full suite: **272 passed, 1
  pre-existing failure** — `test_plugin_is_in_sync_with_source` (plugin
  bundle drift for `families.py` (another stream), `validate.py` (another
  stream) and now `manipulate.py`). I did NOT run `tools/sync_plugin.py`
  because it would ship the other streams' in-progress files into `plugin/`
  and rebuild `rev-revit.zip` (not my territory) — **orchestrator: run
  `python tools/sync_plugin.py` once the parallel streams land.**
* Six-file robustness (`experiments/manipulate/robustness.json`):
  `Document.from_file` + full host-document decode + byte-exact re-encode
  sample + manipulate smoke on ALL SIX samples incl. dach (132 MB, loads in
  2.4 s) — 0 walker/framing errors anywhere; re-encode sample 100.000 %
  exact on every file; seq-102 clean rates 100/100/95.84/100/100/96.50 % —
  every failure is the same Extensible-Storage `ESEntityCell.m_blob` case.

## Findings that correct / extend the plan

1. `ElementParents.m_deletion` is NOT a general "delete-with" relation.
   Counter-examples: racadv windows 145607/145683 hosted on wall 139857 list
   the NEIGHBOUR wall 144180; an rme air terminal's `m_deletion` chain
   (`RbsHvacSystem` → 30 members → their systems…) reached 2,300+ elements
   at depth 8 (a whole duct network). Hard dependents must come from
   structure (hosting / ownership / level association) + annotation-leaf
   classes only; everything else that mentions a deleted id is a peer to
   neutralise. This is the load-bearing modelling decision of the stream.
2. Neutralisation must not drop pointed-to sub-objects (a `Connector` in a
   system's `m_connPtrArray`, an `RbsDuctSection` in `m_rgSections`):
   other elements hold positional back-references (`m_nIndex`) into those
   arrays — clean the object's own id references instead.
3. Object-pointer bookkeeping (`pid`, `weakref`) collides numerically with
   small ElementIds (racbasic Level 311, phase 86961, small pids): id
   scanners must skip those keys (added to `_NOT_ELEMENT_ID`) or a
   neutralise pass would corrupt pointer indexes.
4. Performance: a per-record python scan of 142k records × N target ids
   is the cascade bottleneck (minutes); a one-time byte haystack over the
   host-document records + `bytes.find` per target (`_ref_index`) makes a
   report 0.2–4 s.
5. Extensible Storage is the practical editability ceiling on real-world
   files: 4.2 % of rme and 3.5 % of dach host elements (incl. some walls /
   floors / views on dach) carry `ESEntityCell` blobs and cannot be
   re-encoded today.

## Requests to the orchestrator / other streams

* **Viewer acceptance run** for `experiments/manipulate/M{1..4}*.rvt` (8
  files; notes per file in `experiments/manipulate/README.md`). This is the
  only oracle that can grade the dependents/neutralisation model **[H]**.
* **`objects.py` / `encode.py` (decoder stream): ES-blob passthrough.**
  Decode `ESEntityCell.m_entityMap[*].second.m_blob` as an opaque byte
  span (its runtime ES schema is in `Global/Latest`'s `ADocument`
  ES-schema table per KNOWLEDGE §"Object decoding") and re-emit it
  verbatim. That single fix would make the 1,171 rme + 1,741 dach elements
  modifiable. Exact failure signature on every one:
  `field ...CellList.m_cells[0]->ESEntityCell.m_entityMap[0].second.m_blob,
  error 'pointer token pid=-1 to unknown class 0x????'` (the "class id" is
  really blob content).
* **`tools/sync_plugin.py`** must be re-run (plugin drift test).
* No changes were needed in `mutate.py` / `commit.py`; `manipulate` imports
  `commit.PART_HDR_COUNT_OFF` and the shared writer chain only.

## KNOWLEDGE.md proposal (append)

> ## Manipulating EXISTING elements (wave 3+, `src/rvt/manipulate.py`)
>
> - Delete = remove the element's seq-101/102/103 records from unit 0, drop
>   its ElemRec (count −1, id watermark KEPT), fix the partition header
>   count; every other stream copied. Structurally proven + re-read on
>   rmebasic AND racadvanced (M1–M4, experiments/manipulate/proofs.json).
> - `ElementParents.m_deletion` MIXES ownership with regenerate/constraint
>   peers (racadv windows on wall 139857 list neighbour wall 144180; an rme
>   air terminal's chain reaches the whole duct network via
>   `RbsHvacSystem`). Hard dependents = structural only: hosted (m_hostId /
>   SketchPlane on a face), owned (ElemRec owner / m_ownerElemId / m_famId /
>   m_superInstanceId), placed-on-Level (m_assocLevelId / m_levelId /
>   m_genLevelId), + annotation leaves (tags/dims/warnings/its schedule
>   view) whose m_deletion names X. Everything else that mentions X is
>   NEUTRALISED (scalar id → −1, id-in-list removed, structured entry
>   dropped) — except pointed-to sub-objects (Connectors) which are kept and
>   cleaned inside so `m_nIndex` back-refs stay valid.
> - Modify = decode → require byte-exact re-encode of the UNEDITED object
>   → patch by json path → re-encode + fresh adler32 stamp → splice (record
>   may resize; unit 0 re-blocked). Move = Trf.m_or (+3x3) + m_instOrigin +
>   rep transforms/boxes + header bbox. Retype = symbol/master ids + rep
>   GInstance symbol + header parents remap (free/face pattern only).
> - Editability ceiling on real files = Extensible Storage:
>   `ESEntityCell.m_blob` objects (rme 4.2 %, dach 3.5 % of host elements,
>   incl. some walls/floors/views) do not re-encode today → un-modifiable
>   (deletable). ES-blob passthrough in objects/encode is the top follow-up.
> - Sample id landmarks: rme panel 581483 'PP-1B' (BIP −1140078 name,
>   −1001203 mark), rme transformer 624416 (free, symbol 621242, siblings
>   621226/28/30/32), rme wall 573703 (2 face SketchPlanes + 10 fixtures),
>   racadv wall 144180 (door 145999), racadv table 180360 (4 owned chairs,
>   sibling type 180237).

## Follow-ups (proposed tickets)

1. ES-blob passthrough in the codec (see above) — unlocks the last 3–4 %.
2. Host-cut door/window: move-along-host (`m_hostParam`) + retype via the
   per-host cut-clone symbol (mutation-plan §6.4) — phase 2.
3. Optional full-save bookkeeping on manipulate commits
   (`streams_edit.record_save`) — currently the same minimal-commit policy
   as `commit_new_elements` (existing episodes reused).
4. Propagate derived caches on edits (a renamed panel's circuits'
   `m_strDescription`; a re-typed instance's `m_pInstParams` defaults) —
   Revit regenerates these; only needed if the viewer/Revit balks.
5. `ElementGroup` membership: deleting a grouped element shrinks the
   group's member list — group definition consistency (other placements of
   the same group type) is unhandled; acceptance-test a grouped delete.
6. A `Document`-level `delete/modify/move/retype` façade + CLI verbs on
   `python -m rvt.manipulate` (`report`/`describe` exist today) so the
   skill can call it directly.

BRANCH STATE: manipulate DONE — 4 operations (delete no-deps, delete
with-dependents cascade, modify parameters, move+retype) proven structurally
+ by semantic re-read on rmebasic AND racadvanced (8/8 M-files pass, in
experiments/manipulate/); tests/test_manipulate.py 8/8; full suite 272
passed + 1 pre-existing plugin-drift failure (needs orchestrator
`tools/sync_plugin.py`); six-file robustness pass clean except the known
Extensible-Storage blob decode gap (filed as follow-up #1); viewer
acceptance of the 8 files is the remaining oracle.
