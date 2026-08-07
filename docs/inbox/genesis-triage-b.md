# genesis-triage-b — BUG B: the unit-removal ContentDocuments splice (2026-08-03)

Charter: diff the ladder's unit-removal emission (R9b/R10b: validator-VALID,
reader-FAIL) against the SOLVED `Global/ContentDocuments` grammar field by
field; re-implement unit removal on top of the solved grammar with the
ADocument content-registry reconciliation of verdict #3; emit bisection
probes B1..B4 each one class of change from a known-passing sibling.
Territory touched ONLY: `src/rvt/reduce_v2.py` (new), `tests/test_reduce_v2.py`
(new, 12 pass), `experiments/genesis/triage/{B1..B5.rvt, B*_v2report.json,
probes_bug_b.json, probes.json (MERGED — the sibling triage-a stream shares
this file; our rows were appended, theirs preserved)}`,
`docs/writer/content-splice.md`, this file.  No existing `src/rvt/*.py`, tool
or test edited (old `tools/rvt_reduce.remove_units` IMPORTED read-only for the
B2 control); no browser use.  Python `.venv/bin/python`.

## Result in one screen

**The literal Bug B ("malformed ContentDocuments splice") is FALSE at the
byte level; the real defects are two, neither in the CD grammar.**  The old
path's `Global/ContentDocuments` output is BYTE-IDENTICAL to the
solved-grammar rebuild for the same 38 GUIDs (`assemble(parse(R9) − 38) ==
R9b's CD payload`, 320,897 B); the partition unit splice is byte-clean and
its separator counters are consistent (counter == unit record count).  The
two reader-visible discrepancies between failing R9b/R10b and passing R9:

* **D1 — content-registry incoherence (verdict #3, quantified):**
  `Global/Latest` is untouched, so `ContentTable.m_ContentRecSet` (52
  records) and `FamilyMgr.m_arrLoadedFamilyInfo` (AppInfo slot 0, 50 entries)
  — the ONLY two sites a content GUID occupies (measured: every one of the
  52 GUIDs occurs exactly TWICE in R9's ADocument; the embedded documents'
  14,052 element ids occur ZERO times) — still name all 38 removed documents.
* **D2 — NEW: ECC-junk tail accumulation in `Partitions/21`.**  The
  Autodesk-written partition logical stream ends EXACTLY at the 10-byte end
  record `a303 00000000 ffffffff` (ECC-exact via `unframe_exact` on all six
  samples — the older note's "u32 0 + zero pad + high-entropy tail" is the
  final CRCIO block's pad+parity, not content).  Both `delete_elements` and
  `remove_units` write `depage()`'s tail junk back as CONTENT after the end
  record: first-generation R5..R10 carry +58 B (the sample's heap tail) and
  are reader-ACCEPTED; the second-generation R9b carries **+294 B** (58 +
  236 B = R9's own zero-pad + parity), R10b **+506 B**.  Unproven as the
  cause, previously unlogged, and it is the ONLY framing difference between
  the PASS and FAIL rungs besides D1.
* `Global/PartitionTable` is the WORKSET table (byte-identical R9/R9b) —
  the charter's "PartitionTable rows" do not exist for save units; the
  recipe rightly leaves it alone.

**Corrected recipe: `rvt.reduce_v2.remove_units_v2(doc, guids)`** — partition
units spliced from the ECC-EXACT logical stream + canonical 10-byte end
record; `Global/ContentDocuments` re-BUILT by the solved grammar (never
edited in place); `Global/Latest` decoded, ContentTable records + FamilyMgr
GUID lists reconciled, re-encoded byte-exact; post-condition
`verify_content_coherence` (unit GUIDs == CD GUIDs == ContentTable GUIDs ==
FamilyMgr GUIDs, tail junk 0).  Full spec + the 15-row discrepancy table:
**`docs/writer/content-splice.md`**.

## Probes (upload order = information value; all `rvt_validate` VALID 0 errors)

`experiments/genesis/triage/` — manifest `probes_bug_b.json` (durable) and the
merged rows in `probes.json`; per-probe `B*_v2report.json`.  Design: a
byte-exact **2×2 factorial** over (partition tail: exact | junk) × (content
registries: coherent | incoherent) with the removed set FIXED to R9b's 38
documents — all other bytes are identical across R9b/B3/B4/B5 — plus the
n=1 pair B1/B2.

```
             registries incoherent          registries coherent
tail junk    R9b  (KNOWN FAIL, 294 B)        B5  (= R9b + reconciliation only)
tail exact   B4   (= R9b − junk tail only)   B3  (= R9b done right)
```
1. **B3** — R9b's exact 38-document removal by the v2 recipe (coherent +
   canonical end record); vs R9b: ONLY D1+D2 differ.  PASS ⇒ Bug B solved.
2. **B1** — R9 (PASS) minus ONE orphaned document ('M_Concrete-Square-Column',
   unit 36, GUID 09982dbb-…, 47,121 B — rstbasic has no furniture/plumbing
   family; this placed structural-column family, host + instances already
   deleted in R9, no nested children, is the analogue) — coherent, R9's own
   tail byte-preserved: the removal is the ONLY change vs R9.
3. **B4** — B3 with `Global/Latest` NOT reconciled (= R9b minus the junk
   tail only) — isolates D1 vs D2.
4. **B2** — the OLD path on B1's single document (control).
5. **B5** (bonus) — R9b's own bytes + ONLY the Latest reconciliation
   (completes the square; PASS-with-B4-FAIL ⇒ coherence alone rescues R9b).

Reading table (also in `probes_bug_b.json:reading_the_results`): B3 PASS ⇒
solved (B4/B5 attribute D2 vs D1); B4 PASS ⇒ junk tail was the killer;
B4 FAIL & B3 PASS ⇒ coherence is the requirement; B3 FAIL & B1 PASS ⇒ a
specific document (or scale) of the 38 is load-bearing → bisect the set;
B1 FAIL too ⇒ a third coherence surface exists (Bug B deeper than the two
mapped registries).

## Findings (evidence in content-splice.md §2; each RUN this session)

- **[V] CD grammar exonerated:** old and solved emissions byte-identical on
  the same GUID set; all six samples' CD payloads round-trip byte-exact
  through `factory.parse/assemble_content_documents` (old scanner agrees on
  entry counts 52/163/305/121/180/1,243).
- **[V] Partition end record = 10 bytes and NOTHING after** in every Autodesk
  logical stream (`unframe_exact` on 6/6); ≤58 B of trailing junk is
  reader-tolerated (R5, R9 PASS carrying it); the reduction path's
  second-generation files accumulate the parent's ECC block (R9b 294 B /
  R10b 506 B).
- **[V] Content GUID sites in the ADocument = exactly 2** (ContentTable
  record + FamilyMgr `m_familyDocGUIDs`); FamilyMgr = AppInfo slot 0 with 50
  entries (41 non-empty covering all 52 GUIDs — 34 single + 7 multi — and 9
  empty system/in-place entries); embedded-document element ids never appear
  in the host Latest.
- **[V] Separator counter = the unit's REAL record count** (records − 1
  sentinel, on all 52 rst units and all R9b/B* survivors) — no counter
  needs re-writing when whole units are removed.
- **[V] PartitionTable is the workset table** (1 row 'Workset1', 134 B,
  byte-identical R9/R9b) — no unit rows; the charter premise corrected.
- **[V] The v2 codec path is safe:** `encode_latest(decode_latest(x)) == x`
  byte-exact on R9's Latest (gate in `remove_units_v2`); reconciled Latest
  re-decodes clean with 0 removed GUIDs referenced (B3: ContentTable 52→14,
  FamilyMgr 50→22; B1: 52→51, 50→49).

## For KNOWLEDGE.md (proposed merge)

1. Partition-stream framing: the logical stream ends AT the 10-byte end
   record `u16 0x3a3, i32 0, i32 -1`; the writer must terminate there and
   never carry `depage()`'s tail (fix `delete_elements` / `remove_units`:
   both write junk after the end record — 58 B tolerated, growth per
   generation).
2. Content GUID coherence surface = ContentDocuments entries + partition
   unit separators + `ContentTable.m_ContentRecSet` + `FamilyMgr
   .m_arrLoadedFamilyInfo[].m_familyDocGUIDs` — four sets that must stay
   equal; `verify_content_coherence(path)` measures them.
3. `Global/PartitionTable` (worksets) is unrelated to save units.

## Diffs requested outside my territory (NOT applied)

* **`src/rvt/reduce.py::delete_elements` and `tools/rvt_reduce.remove_units`
  (their owners):** build `part_logical` from decoded structure +
  `PART_END_RECORD` instead of `logical[end_offset:]` (D2); the old
  `remove_units` should also call `reconcile_content_registry` (D1) — or be
  retired for `reduce_v2.remove_units_v2` (drop-in: `remove_units_v2(R9,
  guids, out)`).
* **`src/rvt/famgen/factory.py` (asset forge):** consider promoting
  `parse/assemble/insert_content_documents` into `rvt/content.py` (already
  requested by the forge); `reduce_v2` imports them from `famgen.factory`.
* **`tools/rvt_validate.py` (validation stream):** a coherence layer
  (`verify_content_coherence`) would have flagged R9b/R10b (registry−docs
  mismatch) — validator-clean ≠ reader-loadable is exactly this gap.
* **orchestrator:** `python tools/sync_plugin.py` (new `reduce_v2.py` joins
  the plugin-drift list); upload B3, B1, B4, B2 (, B5) in that order.
* **Sibling triage-a stream:** their manifest names a `KD1` "coherent unit
  removal" probe; the B-set here is the byte-exact factorial for Bug B —
  if KD1 was built with the OLD `remove_units` it inherits D1+D2.

## Open questions

* Which of D1/D2 killed R9b/R10b — only the viewer (B4 vs B5 vs B3) can say;
  the two-bug model's Bug B may resolve into "coherence" (my prior) or "junk
  tail" or both.
* Does the reader also require the FamilyMgr entries whose `m_surrogateId`
  (host id) is dead to be dropped?  R9 PASSES with dead surrogates, so no —
  but a B3/B1 FAIL would re-open it.
* Nested-document orphans: B1 leaves nothing dangling (unit 36 has no
  children); the R9b set closes over nested children by construction.

## Verification

- `.venv/bin/python -m rvt.reduce_v2 --diff` → the discrepancy JSON (§2 of
  content-splice.md); `--probes` regenerates B1..B5 (~13 s) + manifests;
  `--coherence FILE` measures any project.
- `.venv/bin/python tools/rvt_validate.py --quiet experiments/genesis/triage/B*.rvt`
  → all `OK errors=0 warnings=1` (the corpus-wide DataStorage decode-gap
  warning, present in R9/R9b too).
- `.venv/bin/python -m pytest tests/test_reduce_v2.py -q` → **12 passed**
  (tiling / exact end record / CD grammar identity + old≡solved / registry
  reconciliation semantics / end-to-end coherent removal + validator /
  R9b measured incoherent+junk / family_units lookup).
- Full suite (`.venv/bin/python -m pytest tests/ -q --ignore=tests/oracle`,
  632 s) → **631 passed, 3 failed** — the SAME three pre-existing,
  out-of-territory failures every recent record reports (none touched by
  this stream, all pass/fail identically without my files):
  (1) `tests/test_plugin_sync.py::test_plugin_is_in_sync_with_source` (plugin
  bundle drift; fix = `python tools/sync_plugin.py`, orchestrator-run —
  `src/rvt/reduce_v2.py` now joins the drifted list); (2)
  `tests/test_provenance.py::test_G0_resource_refs_are_counted` and (3)
  `::test_G0_identity_dit_usernames_still_leak` (stale assertions pinning the
  pre-genesis-2 G0's retired leaks; owner = provenance stream, diff in
  docs/inbox/genesis-2.md).

BRANCH STATE: no VCS (plain directory); all work is uncommitted files —
`src/rvt/reduce_v2.py` (remove_units_v2 + splice_units + rebuild_content_
documents + reconcile_content_registry + verify_content_coherence +
family_units + probe driver + diff), `tests/test_reduce_v2.py` (12 pass),
`experiments/genesis/triage/{B1,B2,B3,B4,B5}.rvt` + `B{1,3,4}_v2report.json` +
`probes_bug_b.json` + merged rows in `probes.json`,
`docs/writer/content-splice.md` (the discrepancy list + corrected recipe),
`docs/inbox/genesis-triage-b.md` (this).  Every probe: rvt_validate VALID
0 errors, structural verify OK, coherence as designed (B3/B1/B5 coherent;
B4/B2 deliberately incoherent; B3/B4 exact tail, B1 R9's own tail, B2/B5
junk tail).  Full suite 631 passed / 3 pre-existing out-of-territory failed
(above).  NOTE: `probes.json` is shared with the concurrently-writing
triage-a stream and gets rewritten wholesale by it — re-append our rows with
`.venv/bin/python -m rvt.reduce_v2 --remerge`; the durable copy is
`experiments/genesis/triage/probes_bug_b.json`.  READY — the B-probes await
the viewer; the first B3/B4/B5 verdicts close Bug B.
