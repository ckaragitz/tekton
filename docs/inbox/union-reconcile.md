# union-reconcile — U16 (PASS) vs T1v (FAIL), split into single variables

Stream: union-reconcile (workstream agent, 2026-08-05)
Territory: `tools/union_reconcile.py`, `experiments/unionrec/**`,
`tests/test_union_reconcile.py`, this record.
Status: **STAGED (batch 52) — READY for upload; STOP at READY.**

## The contradiction (verdicts #38–#44)

| cell | shell species | union machinery | base | verdict |
|---|---|---|---|---|
| U16 (b45) | born EMBEDDED donor (rst concrete column) | famdoc_final.make_union_doc + donor-inline-ADocument swap | rst | **PASS** |
| U12345 (b45) | born EMBEDDED donor | same union, AUTHORED inline ADocument | rst | **PASS** |
| T2a (b50) | born STANDALONE vendor .rfa, UNMODIFIED | (none) | G_ABPD | **PASS** |
| T1v (b51) | born STANDALONE vendor .rfa | rft_probe.template_union_doc, AUTHORED inline ADocument | G_ABPD | **FAIL** |

Both carry the same 35-element ours-content union. Three variables differ
between U16 and T1v at once: (a) machinery, (b) species, (c) base. T2a
exonerates species-alone and base-alone for the no-union case; U12345
exonerates the authored-ADocument flavour on the embedded shell.

## The round (batch 52, staged 2026-08-05)

Every probe: validator 0 errors / 0 unexpected, coherent four-registry
census, +1 unit on the load hop / +0 on the instance hop, survivor law
both hops, identity gate PASS, 64-byte 0x0f3f blob on every unit with OUR
deterministic nonce on the added unit, schema-typed references
0 unresolved, instance 0 dangling. Gates recorded in
`experiments/unionrec/accounting.json`; manifest
`experiments/unionrec/probes.json`; staged
`experiments/acceptance/batch_52.json` (reading order: CTRL_rst,
CTRL_G_ABPD, T1u, T1r, U16g; both controls byte-identical certified
copies; staged md5s re-verified).

| rung | one thing it tests | vs | md5 | ids (sym/fam/inst) |
|---|---|---|---|---|
| T1u | STANDALONE shell under U16's own machinery, on rst | U16 (species axis) | e671ea0f5bfd0e763a453b9032a8e2ae | 1474588 / 1474565 / 1474589 |
| T1r | T1v's byte-identical famdoc, on rst | T1v (base axis, failing side) | c749ada0fa6019c0a3ee68188c574561 | 1672588 / 1672565 / 1672589 |
| U16g | U16's byte-identical famdoc + full recipe, on G_ABPD | U16 (base axis, proven side) | 47c9af2e6fb443a59eac6c542ac1bf8d | 1474584 / 1474565 / 1474585 |

Watermark law that makes the transplants exact: **RST wm == G_ABPD wm ==
1472524** (measured), so a famdoc built above one is byte-valid above the
other. T1r reproduced T1v's entire host-side allocation on the other base
(symbol/family/instance 1672588/1672565/1672589 — T1v's own numbers);
U16g reproduced U16's (1474584/1474565).

### Byte-identity, machine-verified (not asserted)

- Unit segments carry NO GUID (measured: rebuilt segments byte-match the
  shipped units; the GUID lives only in host-side registration + the
  footer nonce). "Byte-identical famdoc" therefore = segments 101/102/103
  byte-equal, and the build REFUSES otherwise.
- The one nondeterminism inside the segments is the per-creation-session
  `revit.local.family:<32-hex>` GUID our famgen mints into ParamElemFamily
  `m_typeId` (14 records). The build discovers the fresh↔target hex pair
  by set difference against the target unit and pins it, then verifies:
  - T1r vs `experiments/birthright/_build/T1v/T1v_load.rvt` unit
    3b21dfd9…: **101 ✓ 102 ✓ 103 ✓** (session hex pinned to T1v's
    3c5faf44…).
  - U16g vs `experiments/famdoc_final/U16.rvt` unit ffee468e…:
    **101 ✓ 102 ✓ 103 ✓** (session hex pinned to U16's 8217b592…).
- U16g's swapped inline ADocument is diffed field-for-field against U16's
  shipped entry: **4 diff paths, all inside the four history identity
  GUIDs** (fresh per build — U16's own law; the swap runs
  `famdoc_final.swap_inline_adoc_union` VERBATIM).
- Unit GUIDs are FRESH per house law ("fresh GUIDs per rebuild") — a
  reused unit GUID risks viewer-side content dedupe replaying the old
  verdict and faking the read. Recorded per probe.

## The machinery-axis port (T1u) — exactly what was done

The charter flagged the rebase choice as part of the machinery axis.
Documented decisions, each species-forced departures from U16's literal
code or verbatim reuse:

1. **Shell rebase = schema-TYPED decode-time remap** (rft_probe's
   `load_rft_elements`). famdoc_final's blind int-walk is measured-unsound
   for the standalone species (original ids 3..7674 alias ordinary small
   integers — e.g. `m_devBranchInfo.m_syncVersion` 2662 sits inside that
   range; rft_probe's own founding measurement). This is the ONE machinery
   element that cannot be held fixed across species; it is identical to
   T1v's rebase, so it cancels out of T1u-vs-T1r and rides into
   T1u-vs-U16 by necessity. 17,548 typed values remapped.
2. **Our block at wm+2000** (famdoc_final's offset; T1v used wm+200000).
   The 1,992-element shell tops at wm+1992; an overlap gate refuses
   collision. Because the two watermarks are equal, T1u's carried block
   lands on U16's EXACT element ids (1474526..1474564), and the famload
   allocation puts T1u's host Family row at U16's exact id (1474565).
3. **Union + registration verbatim**: carried set = axes H1..H5 union
   (35 elements), only the self-Family reference repointed, famdoc_final's
   dangling gate, `register_added` + `register_param_rows`
   (with_negatives=True — U16's own condition). Registration outcome:
   17 param rows, 4 type pairs extended, locked 7, order ids 6 — appended
   into the BORN self-Family's own rosters (deletion 1919, familyIds 1916,
   absorbed indices 3170..3204).
4. **Axis 6 ported — the born document object swapped inline.** The
   standalone species has no inline ContentDocuments ADocument; its born
   document object is `Global/Latest` (same 19 top-level keys as the
   donor's inline value, measured; `m_elemTable`/`m_pHistory` NULL —
   externalized to the Global/ElemTable + Global/History streams per the
   standalone-ownership law; AppInfoManager **131/239 registries
   POPULATED**; 9 `m_storedByRevitBuild` build strings; ContentRecSet
   empty — no nested docs; `m_pHostDocument` already `weakref 1`). Port:
   - Global/Latest decoded through a schema-TYPED remapping
     `ADocumentDecoder` (the unit-records remap law extended to the
     document object). **Calibrated on the donor's inline ADocument**
     (1.4M ids — zero false positives): the typed remap reproduces the
     blind walk's 1,194 substitutions EXACTLY, except
     `m_elemArr[].m_history.m_originalElementId.m_id64` — an id64-typed
     (non-ElementId) field inside the elem table, which the port authors
     anyway. On the born value: 1,888 values remapped, **0 positive
     ElementIds outside the idmap** (the born object references only
     allocated elements).
   - Inline `ElemTable` + inline `DocumentHistory` transplanted from
     `factory.author_embedded_adocument` over the full hybrid element
     list (2,027 rows, owners from the ElemTable-stream law + carried
     owners; IdentifierSource raised to 1474564) — the embedded form the
     species externalizes; rows cover shell + carried exactly like U16's
     row-append.
   - Four history identity GUIDs set to ONE fresh identity independent of
     the unit GUID (`swap_inline_adoc_union`'s measured native law; the
     born standalone carries NO history GUIDs — species finding).
   - Gates: key-set equality vs the embedded form, owner-family remap
     check (17 → 1472539), host-weakref check, re-decode-clean, entry
     count preserved (53).
5. **Identity pins**: carried ParamElemFamily session hex pinned to
   U16's (14 substitutions) so the carried records are byte-comparable to
   U16's; shell facts (category -2000080, part_type 0, first non-blank
   type "0610 x 0160mm") from the .rfa itself — the same facts T2a
   PASSED with (a standalone shell has no native host row to take them
   from, which is where U16's literal code read the donor's).

## The byte audit (`experiments/unionrec/byte_audit.json`)

Instruments: each union file diffed record-by-record against its own
certified-PASS unmodified-shell baseline on the IDENTICAL id layout
(same wm, same shell block): **T1v vs T2a** and **U16 vs B7**. Each diff
is exactly what that machinery did to that shell.

Findings, ranked:

1. **The one separable machinery delta is HOST-SIDE: the
   inline-ADocument flavour.** T1v shipped the authored form (0/239
   AppInfo registries — `author_embedded_adocument`'s own docstring calls
   empty registries THE OPEN QUESTION; history identity = unit GUID;
   `m_storedByRevitBuild` []); U16 shipped the donor's BORN document
   object (131/239 registries populated, donor build strings, independent
   history identity). U12345 (PASS) exonerated the authored form on the
   EMBEDDED shell + rst only. T1u vs T1r splits this axis on the
   standalone shell.
2. **template_union_doc touched exactly ONE shell record** (the born
   self-Family, seqs 101+102) — nothing else in the 1,992-element shell.
   Zero machinery artifacts.
3. **famdoc_final's machinery likewise touched exactly ONE shell record**
   (the donor self-Family) — the two machineries are byte-symmetric in
   shell treatment.
4. **Carried 35 pairwise: 35/35 structurally IDENTICAL** through the id
   correspondence (T1v ids ↔ U16 ids + self-Family anchors), after
   normalizing the per-identity `revit.local.family:<session><elemid>`
   strings. No framing, no rebase artifacts, no registration-side
   differences in the carried content.
5. **Registration touched EXACTLY the same six self-Family surfaces in
   both** (header deletion list, cellList, familyIds, familyParams,
   locked list, type pairs) — no surface touched by one machinery only.
6. **Small-id residue: ZERO** typed small ids (≤7674) in T1v's unit — and
   zero in T2a's. No aliased id escaped the typed rebase; nothing dangles
   into the .rfa's original id space.

**Smoking-gun verdict: NO unit-content smoking gun; no T1w warranted.**
The famdoc mutations the two machineries produce are structurally
identical; if the machinery axis convicts, the ADocument flavour (rank 1)
is the suspect list, and it is exactly what T1u-vs-T1r measures.

## The decision table (all 8 outcomes pre-committed)

Full text in `experiments/unionrec/probes.json` `reading_the_matrix`.
Summary — with U16/U12345/T2a/T1v as the known cells:

- **T1u P, T1r P, U16g P** → conjunction: standalone species × G_ABPD
  base under the union (every single axis innocent alone).
- **T1u P, T1r P, U16g F** → BASE convicted from the proven side
  (G_ABPD × union; T2a says no-union survives it).
- **T1u P, T1r F, U16g P** → MACHINERY convicted on the standalone
  shell; byte-audit rank 1 (ADocument flavour) is the fix spec.
- **T1u F, T1r F, U16g P** → SPECIES convicted (standalone + union fails
  under BOTH machineries on rst; embedded passes everywhere) — the
  birthright mining must add what the embedded species carries.
- **T1u F, T1r P, U16g P** → the born-ADocument PORT is prime suspect;
  bisect T1u minus the swap (= U12345's form on the standalone shell).
- Mixed U16g-F rows: base conviction stacks on the above; either control
  FAIL voids its base's probes.

## Evidence index

- `experiments/unionrec/probes.json` — manifest + decision table.
- `experiments/unionrec/accounting.json` — per-probe build records,
  accounting vs immediate parent + load hop, blob proofs, gates.
- `experiments/unionrec/byte_audit.json` — the machinery delta, measured.
- `experiments/unionrec/_build/<rung>/` — load stages (+ swapped stages).
- `experiments/acceptance/batch_52.json` — the staged round.
- `tests/test_union_reconcile.py` — 20 tests, all passing (pins the
  ladder, byte-identity evidence, audit verdict, staged batch shape).

PROOF-ONLY: all three probes embed Autodesk sample / vendor-born content;
quarantined under `experiments/`; zero donors in anything shipped.

## Proposed follow-ups (orchestrator's call, post-verdicts)

- On a machinery conviction (T1r FAIL, T1u PASS): the authored
  inline-ADocument's empty-registry surface becomes the fix target —
  birthright should learn to AUTHOR the populated registry set (the born
  .rfa's 131 registries are the mining source; zero donor bytes).
- On a species conviction: T1u-minus-swap (U12345's form on the
  standalone shell) and a registry-transplant single-variable rung are
  the next bisection pair.
- On a base conviction (U16g FAIL): G_ABPD × union interaction — retest
  U16g's recipe on G_ABPD_2025/2024 (both certified) to see whether the
  composed lineage or this base instance carries it.

## BRANCH STATE

- No git repo in this workspace (per env) — no branch. All work is in
  the working tree under the stream's territory:
  `tools/union_reconcile.py` (new), `tests/test_union_reconcile.py`
  (new, 20/20 passing), `experiments/unionrec/**` (new: 3 probes + 2
  load stages each + accounting.json + probes.json + byte_audit.json),
  `experiments/acceptance/batch_52.json` + 5 staged files (probe_batch's
  own designed output), this record.
- Batch 52 is STAGED, gates green, md5-verified. NOT uploaded — the
  orchestrator uploads (stage-only law).
- Nothing else touched; famdoc_final/rft_probe/famdoc_bisect imported,
  never edited.
