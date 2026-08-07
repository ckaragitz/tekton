# terminal-diff — THE EXHAUSTIVE H12-vs-NATIVE WHOLE-FILE DIFF + THE RE-ENVELOPE PROBES (batch 42 staged)

Stream: **terminal-diff** (2026-08-05, post-verdict-#35).  Charter: every
record-level hypothesis is DEAD by single-variable viewer experiments; H12
(the all-native-copy probe) is mostly native bytes, so enumerate EVERY
difference between H12.rvt and the pure native rst sample at EVERY layer,
classify each item TESTED-DEAD / UNTESTED / PARITY, probe the untested
envelope axes one change at a time, stage the round, and prepare the
desktop-Revit kit.

**Territory touched ONLY:** `tools/terminal_diff.py` (new),
`experiments/terminal/**` (new), `tests/test_terminal_diff.py` (new), this
record, and the staging copies `probe_batch` itself writes under
`experiments/acceptance/`.  No existing src module, tool, or test edited.
No browser (STAGE only); no Autodesk install dirs; no full-suite run
(SUITE-COORDINATION adopted: 1697/7/2); all probes PROOF-ONLY
sample-derived dev content quarantined in experiments/.

## Result in one screen

* **THE COMPLETE DIFF IS ENUMERATED AND CLASSIFIED**
  (`experiments/terminal/terminal_diff.json`): 23 axes — 6 measured
  PARITY, 8 TESTED-DEAD (each citing its verdict #31–#35), **8 UNTESTED
  envelope axes** (ranked), 1 not-a-diff note.  Every differing stream,
  every differing CFB directory field, and every partition-frame delta
  lands in exactly one axis (machine-checked decomposition; the same diff
  was run H10-vs-native as the exoneration cross-check).
* **FOUR NEW MEASURED DISCOVERIES** (none visible to any prior
  record-level comparison):
  1. **The 0x0f3f unit footer blob** — all 53 native units carry 64
     high-entropy bytes, **distinct per unit** (not a plain hash of unit
     bytes over 63 tried combos, no GUID embedded); famgen's
     `build_family_save_unit` writes **blen = 0**.  Our unit is the only
     unit in the corpus with an empty blob.  → the TOP untested axis.
  2. **Autodesk's exact gzip member recipes, cracked byte-for-byte**
     (stock zlib level 3, memLevel 8, raw deflate): partition block
     members = `compress + Z_PARTIAL_FLUSH + Z_FINISH`
     (**13,534/13,535** corpus members byte-exact; the 1 miss is one
     historical dach block with a different flush combo); every other
     framed member = `compress + Z_SYNC_FLUSH +` the aligned 3-byte tail
     `02 0c 00` (**48/48** byte-exact).  Our writer's sync+finish ending
     differs on the final 3–7 bytes of EVERY member it emits — 418 blocks
     + 4 global members in H12 (411 of 414 aligned partition blocks differ
     ONLY by this).
  3. **Baked stream-tail junk**: every emit hop re-frames the previous
     read's depage tail junk (final-ECC-block pad+parity) as DATA after
     the 10-byte partition end record — native 0 B, H10 150 B, H12
     **571 B** of high-entropy junk sitting immediately after our unit.
  4. **Two out-of-registry record deltas the four-registry verdicts never
     covered**: BasicFileInfo identity strings (author `'Autodesk
     Revit'`→`'rvt-writer'`, client app `'RevitApplication'`→
     `'rvt-writer'`, last-save path→`'H12.rvt'`) and the
     DocumentIncrementTable **username scrub** (all 44 historical rows'
     usernames blanked in both serialized copies of the table).
* **Measured PARITY kills two suspected layers outright**: the ECC page
  layer (`ecc.unframe/frame` round-trips BOTH files byte-exactly — native
  pads are zero-filled here too) and the gzip member headers (identical
  10-byte constant everywhere).  The decoded-record delta re-verification
  is row-exact: +1 ContentTable row, +1 FamilyMgr entry (surrogate
  1472943), +1 ETD id (symbol 1472961), +1 CD entry, +23 ElemTable rows,
  +23 records in unit-0's three tail blocks, +the 417-record unit — and
  **zero changed common rows anywhere** (full ADocument leaf diff = 3
  container-length changes, keyed sub-diffs empty).
* **EIGHT RE-ENVELOPE PROBES BUILT, GATED, STAGED AS BATCH 42** — each =
  H12 ± exactly ONE envelope change (byte surgery on H12's own bytes; a
  no-edit reassembly identity gate proves the surgeon's hand is clean):
  E1 donor footer blob / E1b random footer blob / E3 Autodesk member
  recipe everywhere / E6 tail junk truncated / E4 native BFI strings /
  E5 native DIT usernames / E2 native CFB directory tree / **E_ALL = all
  of them**.  Every probe: validator **0 errors** (1 standing inherited
  warning `7/32451 seq-102 …`, present on the virgin sample), block
  CONTENTS byte-equal H12, decoded-record identity preserved where
  promised, instance 1472964 present, single-axis stream deltas
  machine-proven.
* **THE TERMINAL STATEMENT (measured on E_ALL)**: with every envelope axis
  flipped, **8 of 12 streams become byte-identical to the pure native
  sample** (including BasicFileInfo and DocumentIncrementTable), **411 of
  414 aligned partition blocks become byte-identical to native**, and the
  first differing logical byte of the partition stream is the LAWFUL
  `elem_table_count` (+23).  E_ALL = "the native file + exactly the
  registered content and nothing else", byte-provable — the closest to
  native any instanced-new-unit probe can get without cracking the
  footer-blob content function.
* Stream-local tests: `tests/test_terminal_diff.py` → **15 passed**.
  Desktop-Revit kit written (`experiments/terminal/REVIT-CHECK-KIT.md` +
  copies of `BXhf_f1i1.rvt` and `H12.rvt`).

## §1  The classified axis table (terminal_diff.json `axes` — the finite list)

| id | layer | difference | class |
|---|---|---|---|
| P1 | gzip envelope | 10-byte member headers (mtime 0, XFL 0, OS 0x0b) identical everywhere | PARITY |
| P2 | ECC | page framing round-trips both files byte-exactly (zero-fill pads both) | PARITY |
| P3 | inventory | same 12 streams | PARITY |
| P4 | partition frame | header/prefix/flags/segmentation/separators/terminator/footer-text; 53 aligned units' separators + blobs byte-equal | PARITY |
| P5 | CFB | v4 constants, 16 entries same SID order, timestamps copied | PARITY |
| P6 | stream bytes | Contents, Formats/Latest, History, PartitionTable, ProjectInformation, TransmissionData byte-equal | PARITY |
| D1–D8 | records | registration rows / inline ADocument / famdoc content / host constellation / CategoryTracking / symbol form / instance shape / ElemTable mechanics | TESTED-DEAD (#31–#35 citations in the JSON) |
| **U1** | unit envelope | **new unit's 0x0f3f footer blob 0 B vs native 64 B (distinct per unit, opaque)** | UNTESTED rank 1 → E1/E1b |
| **U2** | stream tail | **571 B junk baked as data after the end record (native 0)** | UNTESTED rank 2 → E6 |
| **U3** | gzip envelope | **member ending shape: ours sync+finish vs Autodesk partial+finish / sync+`02 0c 00` on every member** | UNTESTED rank 3 → E3 |
| **U4** | out-of-registry records | **BFI identity strings rebranded** | UNTESTED rank 4 → E4 |
| **U5** | out-of-registry records | **DIT usernames scrubbed (44 rows × 2 copies)** | UNTESTED rank 5 → E5 |
| **U6** | CFB | directory red-black tree shape + colors differ | UNTESTED rank 6 → E2 |
| U7 | CFB | sector allocation layout (13 start-sector diffs + header layout fields) | UNTESTED rank 7 — DEFERRED (API-invisible; V15/V20/H10 pass) |
| U8 | CFB | slack content: native heap garbage (1,007–1,367 B in four stream tails) vs our zeros | UNTESTED rank 8 — DEFERRED (API-invisible) |
| N1 | save story | NOT A DIFF: H12 records no new save — byte-equal to native on every save-history surface; semantic oddity noted for the kit | NOT-A-DIFF |

Ranking rationale (recorded per-axis in the JSON): the audit fires only on
instance-walk; unit-scoped envelope items (the blob that exactly our unit
lacks; the junk sitting immediately after our unit) outrank file-global
ones; every untested axis is ALSO present in H10 (PASS), so all
exoneration is uninstanced-only — rank, never exclude (the charter's
explicit caution).  The CFB axes are additionally exonerated INSTANCED on
a native unit by V20 (same writer); only the conjunction
"new-unit + instance + axis" is open anywhere.

## §2  The probes (each ONE change vs H12; upload order = information order)

| probe | the ONE change | expected reading |
|---|---|---|
| **E_ALL** (first — biggest split) | every envelope axis at once (donor blob + truncation + Autodesk recipes + native BFI + native DIT + native dir tree) | PASS ⇒ the objection lives in the envelope/out-of-registry layer (singles name it; all-singles-FAIL+E_ALL-PASS ⇒ conjunction, bisect pairs next); FAIL ⇒ in-file envelope exonerated wholesale EXCEPT the footer-blob CONTENT function (E_ALL carries the donor's blob — wrong if the blob digests unit content) |
| **E1** | new unit's footer blob := donor unit 36's 64 bytes verbatim | PASS convicts the blob axis |
| **E1b** | same := 64 seeded-random bytes | E1 PASS + E1b FAIL ⇒ blob content VERIFIED (crack the function before any port); both PASS ⇒ presence/shape only (port: author any 64-B blob) |
| **E3** | every member re-emitted with the exact Autodesk recipe; 411 untouched blocks become byte-identical to native (gated) | PASS convicts the member-ending shape (port: trivial writer change) |
| **E6** | the 571 junk bytes after the end record removed | PASS convicts the baked tail junk (port: truncate at true end in every emit path) |
| **E4** | BFI author/client/path restored (stream becomes byte-equal native, gated) | PASS convicts the rebrand — port is a PROVENANCE question ('rvt-writer' is truthful; forging Autodesk identity needs counsel — H11's author-string caveat) |
| **E5** | 44 DIT usernames restored in both copies (table field-equal native, gated) | PASS convicts the scrub (port: stop scrubbing, or scrub only rows our saves author) |
| **E2** | directory sector patched to native tree links+colors (zero stream bytes change) | PASS convicts the CFB tree (port: mimic native shape in cfb_writer) |

Full decision table: `experiments/terminal/probes.json →
reading_the_matrix` (CTRL FAIL ⇒ VOID; lattice-inconsistent combos ⇒
oracle noise, re-run).

**STAGED AS BATCH 42** (`experiments/acceptance/batch_42.json`): CTRL =
`CTRL_rstbasicsampleproject_b42.rvt` byte-identical to the untouched rst
sample (md5 `b3235ad2…`, machine-verified) + the eight probes, every
staged copy md5-verified.  **Batch-number note:** the charter says "stage
batch 41"; `batch_41.json` was already consumed by regcorner's H13
(uploaded inside the b40 round, genesis-audit ~04:20), so this round takes
the next campaign-global number — the no-collision law
(`test_batch_manifest_number…`) outranks the charter's literal numeral.
The mapping is recorded in the manifest note and probes.json.

## §3  What was measured that PRIOR comparisons could not see

* Every prior model compared DECODED records; `row_diff.json`'s
  "partition save unit … frame-identical" compared block headers/counters
  and never read the unit FOOTER — the 0-vs-64 blob and the member byte
  shape sat below its instruments.  This stream compared raw bytes at
  every layer and decomposed 100% of them.
* The compressor identification (partial-flush vs sync-flush cadence,
  down to python-zlib's swallowed-empty-flush quirk needing the literal
  `02 0c 00` tail) makes our writer able to emit **bit-exact
  Autodesk-shaped members** for any payload — used by E3/E_ALL and
  available as a lawful product-writer upgrade regardless of verdict.
* The blob is the ONLY remaining opaque unmodeled byte region in the
  entire file.  If the round comes back all-FAIL, the in-file suspect
  space collapses to exactly: the 64-byte blob's content function (+ the
  two API-invisible deferred axes U7/U8).  The kit is the instrument for
  that branch.

## §4  The desktop-Revit kit (experiments/terminal/REVIT-CHECK-KIT.md)

One page for a human with desktop Revit: open `H12.rvt` (the terminal
mystery — all-native copy) and `BXhf_f1i1.rvt` (our product shape),
screenshot every dialog in order, export Manage → Warnings, check the
family/column in the browser + 3D, attempt Save-As, grab the journal on a
crash; a six-row outcome→reading table interprets every result (clean
open ⇒ viewer-side ingest rule; specific dialog ⇒ the fix spec verbatim;
corrupt-with-detail ⇒ localised defect; crash ⇒ journal names the
subsystem; BXhf-vs-H12 same/different ⇒ shared root cause vs additional
famdoc defect).  Both files are copied into the folder (md5s pinned by
the tests); PROOF-ONLY, do-not-redistribute is stated in the kit.

## §5  Verification (how to re-run)

```
.venv/bin/python tools/terminal_diff.py enumerate  # terminal_diff.json (~33 s)
.venv/bin/python tools/terminal_diff.py probes     # E-probes + gates + probes.json (~3 min)
.venv/bin/python tools/terminal_diff.py verify     # re-run gates on emitted bytes
.venv/bin/python tools/terminal_diff.py stage      # batch staging (control = rst copy)
.venv/bin/python tools/terminal_diff.py kit        # REVIT-CHECK-KIT.md + file copies
.venv/bin/python -m pytest tests/test_terminal_diff.py -q   # 15 passed
```

## BRANCH STATE

* **status: DONE — terminal_diff.json COMPLETE AND CLASSIFIED (23 axes:
  6 parity / 8 tested-dead with verdict citations / 8 untested ranked /
  1 not-a-diff), EIGHT RE-ENVELOPE PROBES BUILT + GATED + STAGED AS
  BATCH 42 (the charter's "batch 41" slot — number taken; mapping
  recorded), REVIT-CHECK-KIT written with both files.**  STOPPED AT
  READY: nothing uploaded; the viewer queue is the orchestrator's.
* **no VCS** (working tree, not a git repo).  Files written:
  `tools/terminal_diff.py` (new, ~1,470 lines; enumerate/probes/verify/
  stage/kit), `tests/test_terminal_diff.py` (new, 15 pass),
  `experiments/terminal/` {terminal_diff.json, probes.json,
  REVIT-CHECK-KIT.md, BXhf_f1i1.rvt (copy, md5 `1d6d2dd7`), H12.rvt
  (copy, md5 `80321ae4`), probes/{E_ALL,E1,E1b,E3,E6,E4,E5,E2}.rvt},
  staging copies + `batch_42.json` + `CTRL_rstbasicsampleproject_b42.rvt`
  (byte-identical to the sample, md5 `b3235ad2…`) under
  `experiments/acceptance/` via `probe_batch.stage_batch` (its designed
  output).  Probe md5s (also pinned in probes.json + batch_42.json and
  asserted by the tests): E_ALL `ee0cf709`, E1 `6c0c49ac`, E1b
  `04d43b5c`, E3 `5a4f2e4c`, E6 `9b2e7550`, E4 `f98ed6c8`, E5
  `7f86866c`, E2 `0da908ec`.
* **gates**: every probe validator 0 errors / 1 standing inherited
  warning; no-edit reassembly identity gate; single-axis stream deltas
  machine-proven per probe; decoded-record identity preserved on
  envelope probes; E3/E_ALL 411/411 untouched blocks byte-identical to
  native; E4/E_ALL BFI byte-equal native; E5/E_ALL DIT field-equal
  native; E2/E_ALL directory tree equal native; instance 1472964 present
  everywhere; ECC roundtrip exact everywhere; controls + staged copies
  md5-verified.
* **NOT VIEWER-TESTED**: every claim above is the machine gate; no
  acceptance claim is made.  All probes PROOF-ONLY (quarantined
  sample-derived dev content; never bundled — the deliverable rule's
  dev-only lane).
* **next action (orchestrator)**: upload batch 42 in manifest order
  (**E_ALL first** — the biggest split), read with
  `experiments/terminal/probes.json → reading_the_matrix`; verdicts to
  `docs/coverage/viewer-certified.json`.  In parallel or after an
  all-FAIL: hand `experiments/terminal/REVIT-CHECK-KIT.md` + the two
  files to the user for the desktop-Revit check — on an all-FAIL round
  the kit becomes the decisive instrument (in-file suspect space is then
  exactly the footer-blob content function + API-invisible U7/U8).
