# regcorner — THE FIFTH-SURFACE HUNT + REGISTRATION-ROW FORENSICS (analysis complete)

Stream: **regcorner** (2026-08-05, post-verdict-#34).  Charter: H9 (byte-copied
native host constellation + Autodesk famdoc + V20-shape instance, freshly
registered as a new unit) FAILS while H10 (identical minus the instance)
PASSES and V20 (instance of a natively-registered unit) PASSES — two suspects
remain: (1) the CONTENT of the registration rows famload authors, (2) a FIFTH
SURFACE outside the four-registry model that native units populate and our
loads never do, visited only on the instance walk.  This stream built the
exhaustive identity sweep + the row forensics.  Analysis only — no viewer
probes; output feeds the probe stream.

**Territory touched ONLY:** `tools/fifth_surface.py` (new),
`experiments/regcorner/**` (new), this record.  Read-only over every .rvt;
no src/ file, tool, or test edited; nothing staged or uploaded.

## Result in one screen

* **THE FIFTH SURFACE HAS A NAME: `CategoryTracking`** (project-ADocument
  AppInfo slot 28, measured on the rst sample).  Its
  two arrays are a **COMPLETE 1:1 INDEX of every unit-0 CategoryElem
  (`m_categoryData`) and GStyleElem (`m_gstyleData`) element** — measured
  616/616 + 2183/2183 on rstbasic, 635/635 + 2139/2139 on racbasic,
  1020/1020 + 2459/2459 on rmebasic, **zero untracked anywhere, zero
  derivation mismatches, sort law exact** (rows derive mechanically from the
  elements; see recipe below).  **H9 and H10 are the only files that violate
  the index**: the byte-copied family's 4 CategoryElem twins (1472946/48/52/58)
  + 4 GStyleElem twins (1472949/50/53/59) exist as elements, have ElemTable
  rows — and have **no CategoryTracking rows**.  H10's PASS proves the broken
  index is tolerated UNINSTANCED; the instance walk is what resolves
  category/style state through it.  H7 authors no twins at all (index
  vacuously intact — but the family then lacks the per-family category
  constellation that **41/41 native host families** carry, the same
  subsystem violated from the other side).
* **famload's complete project-ADocument touch surface, machine-measured**
  (241-slot md5 delta, RST vs each of H9/H10/H7): **exactly** slot 0
  `FamilyMgr` + slot 32 `ElementTrackingData` + top field `m_oContentTable`.
  No load path ever writes CategoryTracking — or anything else.
* **The registration-row forensics came back mostly EXONERATING**: after
  remap-normalization the FamilyMgr entry is at **zero-diff parity**; the
  unit separator counter (417 = seq-102 records) is right; project
  History/DIT are untouched; and the one invariant I could construct for
  `m_EpisodeCounts` — **proven 52/52 native: it equals the unit's seq-102
  id-ascending RUN STRUCTURE, newest episode first** — is **coherent for our
  unit too** (single fused run, declared as one episode).  What remains are
  VALUE diffs, ranked in `row_diff.json` (28 entries): `m_author`
  "rvt-writer" vs "Autodesk Revit", single-fresh-episode history vs native
  multi-episode, the embedded ADocument's 0 vs 131 populated registries +
  987 leaf diffs in 11 groups, unit record order (id-ascending fused vs
  native 2-run episode grouping), ElemTable cluster-row episodes.
* Machine-readable deliverables: `experiments/regcorner/fifth_surface.json`
  (per-surface candidate ranking + the CategoryTracking law + slot deltas)
  and `row_diff.json` (row forensics + ranked fields), plus the four raw
  sweeps `sweep_{rst,H9,H10,H7}.json`.

## §1  The sweep instrument (what "exhaustive" means here)

`tools/fifth_surface.py sweep` enumerates, for one file, every surface that
references any of three identity classes of any unit:

* **(a) GUIDs** — 145 identity GUIDs on rst: the 52 content GUIDs + each
  family's `m_famDocGUID` + the embedded DocumentHistory GUIDs
  (creation/detach/upgrade/saveAs).  Every stream is raw-scanned for 5 byte
  forms (bytes_le, ascii, utf-16, both cases); every decodable model is
  tree-walked for typed GUID strings: Global/Latest (full ADocument), every
  ContentDocuments embedded ADocument, History, DocumentIncrementTable,
  PartitionTable, Contents, BasicFileInfo; partition unit segments are
  raw-scanned per unit with record-level attribution (decode-on-hit).
* **(b) unit index/partition number** — observable only through typed
  fields (an int scan is unbounded noise); the unit separators and per-block
  unit numbers are structural framing, recorded as the
  `Partitions:unit-separator` surface.  The host ElemTable's
  `partition_id` column is the WORKSET id (all 0), not the unit number —
  measured, so the four-registry unit separator remains the only
  number-keyed unit reference.
* **(c) element ids** — 19,209 identity ids on rst: 41 host Family ids +
  105 symbols + 41 surrogates (from FamilyMgr) + 947 cluster-owned
  (ElemTable owner-chains: the resource twins) + 18,075 famdoc record ids
  (measured file-wide unique: zero overlap between units or with unit 0).
  Schema-typed ElementId leaves ONLY (`rvt.regdiff.TypedIdWalker` — no
  noisy int matching) over: the project ADocument, every embedded
  ADocument, and **every unit-0 record in seqs 101+102** (13,936 × 2
  decoded).

**Stated limits** (also in every sweep JSON's `coverage_notes`): seq-103
GElement bodies are raw-scanned for GUIDs but not typed-walked (geometry
reps carry tags, not ElementIds); Formats/Latest (the schema) raw-scanned
only; surfaces keyed purely by BUILT-IN category ids carry no per-unit
identity and are outside a per-unit sweep by construction.

Result on rst: **203 surfaces**.  Negatives worth recording: content GUIDs
appear NOWHERE outside Global/Latest, Global/ContentDocuments and the
partition units — History GUIDs are episode GUIDs, DIT/PartitionTable/
Contents/BasicFileInfo/TransmissionData/Formats carry no unit identity.

## §2  The crosscheck (native coverage vs the new unit) and the ranking

`crosscheck` re-runs the sweep on H9 / H10 / H7 (new unit = the GUID not
among the native 52) and asks, per surface: native units have entries —
does the new unit?  **136 surfaces missing / 67 covered** for H9
(`fifth_surface.json`, ranked by instance-walk reachability: 3 = holds
family-cluster element ids, 2 = keyed by unit GUID, 1 = unit machinery,
0 = self-references inside the unit's own content).  The covered list
doubles as an instrument check — it reproduces the known build facts
(byte-copied twins present in H9/H10 but not H7; instances present in
H9/H7 but not H10; all four registries covered everywhere).

**Candidates with reach 3 + donor coverage** (the only ones that can explain
the donor-based H9 fail):

1. **`Latest:…CategoryTracking.m_categoryData[].m_categoryId` +
   `…m_gstyleData[].{m_categoryId,m_gstyleId}`** — 41/41 native host
   families, donor covered, missing for the new unit in H9 AND H10 AND H7.
   Totality/derivation/sort laws in §3.  Reachability chain:
   FamilyInstance → FamilySymbol 1472961 → Family 1472942 →
   `m_familyIds`/`m_big2SmallMap2`/ElemTable owner rows → the CategoryElem/
   GStyleElem twins → the index that claims to know every one of them.
2. `Latest:…SymbolIdMgr.m_defCatSymIds` (23u) — per-category default
   symbol; **donor NOT covered natively** while V20 passed ⇒ not required
   per-family; secondary.
3. `Partitions:unit0:seq102:AnalyticalMember[other].m_sectionType` (6u,
   donor covered) — native structural framing referencing donor's symbol as
   a section type.  Usage by other content, not registration; cannot be the
   common cause (the failed electrical-family probes SL/BX have no
   analytical surface at all); recorded, ranked below.
4. Everything else with reach 3 is donor-UNcovered family-content variance
   (FilledRegion twins, image twins, schedule refs … present only for the
   families that have that content) — cannot explain H9.

The other 100+ "missing" rows are the R0 `ContentDocuments:adoc[self]`
surfaces — the embedded ADocument's own 131 registries, i.e. registry #1
ROW CONTENT (fed to §4), not a fifth surface.

**The unified reading** (why this fits every recorded verdict): every FAILED
instance probe violates the family-category subsystem in one of two ways —
famload-path probes (H7, H8, SL, BX*, DEMO*, ROOM2025_full) author NO
per-family CategoryElem/GStyleElem constellation (native law: 41/41 host
families have one); the byte-copy probes (H9) carry the constellation but
leave the project index unaware of it.  Every PASSED probe satisfies it:
V20-V29 (native constellation + native index rows), L_v2/BX_f2/H10 (no
instance — nothing walks category resolution).  **No counterexample exists
in the recorded matrix.**  H6's FAIL also fits: swapping the inline
ADocument populated registries INSIDE the unit but never the project-side
index.

## §3  The CategoryTracking law (the fix recipe, measured not guessed)

All in `fifth_surface.json → category_tracking_law` (6 files):

* `m_categoryData`: one row per unit-0 CategoryElem —
  `{m_parentCategoryId: elem.m_pCategory->Category.m_parentCategoryId,
  m_categoryId: elem id}`, sorted by `(m_parentCategoryId, m_categoryId)`
  ascending.  0 derivation mismatches / 3,271 rows across three samples.
* `m_gstyleData`: one row per unit-0 GStyleElem —
  `{m_categoryId: elem.m_categoryId, m_gstyleId: elem id,
  m_gstyleType: elem.m_gstyleType}`, sorted by `(m_categoryId, m_gstyleId)`
  ascending.  0 mismatches / 6,781 rows.
* For H9's copied twins the 8 rows are therefore fully determined:
  categoryData `(-2000059, 1472946/48/52/58)` — tail of the −2000059 parent
  group (our ids exceed every native id); gstyleData
  `(1472946→1472949, 1472948→1472950, 1472952→1472953, 1472958→1472959,
  type 1)` — tail of the array (positive category ids sort last).
* Donor twin rows sit natively at categoryData indices 406–409 — mid-array,
  id-ordered within their parent group — so INSERTION AT SORT POSITION is
  the authoring law, not append.

**Delivery to the probe stream — CONSUMED LIVE.**  The probe half of this
axis (`experiments/regcorner/probes/`, its own record) built the
H12/H11/H11x12/H13 lattice while this analysis landed; its **H13 = row-fix
+ the CategoryTracking rows from this ranking**.  Cross-verified with THIS
stream's instrument (read-only, `category_tracking_forensics` over the
staged probe bytes): **H11 / H12 / H11x12 each carry exactly the 8
untracked twins (axis isolation correct); H13 indexes 620/620 + 2187/2187
with ZERO untracked, zero derivation mismatches, sort laws exact** — the 8
rows were authored to precisely the §3 recipe.  H13 PASS ⇒ fifth surface
confirmed; product fix = a CategoryTracking pass in
`register_in_host_adocument` (+ the hostfix/famgen side authoring the twin
constellation so famload-path families have rows to index).  H13 FAIL
alongside an all-FAIL batch ⇒ move to the next donor-covered candidate on
the `fifth_surface.json` ranking; row-content verdicts read §4's order.

## §4  Row forensics (native donor unit 36 rows vs famload's H9 rows)

`row_diff.json`; remap-normalized (22-id host map + monotone famdoc rebase +
declared GUID/name moves), so every listed diff is CONTENT.  H9's authored
row shape is byte-stable across H9/H7 (masked-shape equality) — one flavour
to fix.  Ranked (28 entries, `ranked_fields`):

1. **`m_EpisodeCounts` law — PROVEN, and our row is COHERENT.**  52/52
   native units: the row equals the unit's seq-102 id-ascending run
   structure (newest episode first; donor: runs [411, 6] == declared
   [(1003, 6), (1013, 411)]).  H9: 53/53 including ours ([417] == [(1016,
   417)]).  Falsified en route (recorded in the JSON): the u32 record
   "stamp" is NOT an episode (unique checksum-like values, 0/52), and the
   embedded ElemTable's modification-episode histogram matches only 3/52.
   The REAL native/ours diff on this axis is the fused single run — legal
   under the law, but the donor's two-run episode grouping is lost.
2. **ContentTable row values**: `m_author` "rvt-writer" vs "Autodesk
   Revit"; `m_history` creation/lastModification = 1016/1016 vs 948/988;
   one episode-count pair vs two.
3. **The embedded ADocument** (registry #1's payload): 0 vs 131 populated
   AppInfo registries (independently reconfirms famdoc-bisect's 131/239);
   987 leaf diffs in 11 groups — every element's inline history flattened
   to (1016, 1016, −1) vs native (975…, 1003/1013, 992…);
   `m_storedByRevitBuild` [] vs 2 entries; `m_devBranchInfo.m_syncVersion`
   2662 vs 2660; `IdentifierSource.m_last` 1472941 (host watermark!) vs
   native 15726; fresh history GUIDs (forced — uniqueness).
4. **Unit stream shape**: record order id-ascending-fused vs native
   episode-run order in all three seqs; per-record stamps differ (checksums
   over remapped bytes — expected); blocks 4 = 4, separator counter
   417 = 417.
5. **Host ElemTable cluster rows**: 22/22 episodes (948→1016 creation,
   1013→1016 modified, 976→1016 user) — the standard new-element shape
   V20-certified elsewhere; owner remap correct.
6. **Exonerated at parity**: FamilyMgr entry (zero diffs normalized; native
   histogram 9×0-GUID system surrogates / 34×1 / 7 multi-GUID nested-unit
   entries — famload's 1-GUID shape is the correct non-nested form);
   project History (1017 = 1017, untouched); DIT rows structurally equal
   (usernames scrubbed "" vs Autodesk employees' — the commit identity
   policy, exonerated by V20-V29 passing through the same path).

## §5  Honest limits

* Reachability ranks are PRIORS (how plausibly the open-time audit's
  instance walk consults a surface), not measurements of Revit's reader —
  the viewer verdict on H13 is the only decider.
* The unit-0 typed id sweep covers seqs 101+102 fully; 103 only via raw
  GUID scan (stated above).  A fifth surface encoded purely inside seq-103
  geometry blobs, keyed by neither GUID bytes nor typed ids, would evade
  the instrument; nothing in the corpus suggests one.
* The CategoryTracking totality law is 3-sample (rst/rac/rme basic).  The
  advanced/dach samples were not swept (time-boxed); the law's 3-for-3
  perfection + the H9/H10 violation being unique in-file makes further
  confirmation cheap but non-urgent (`sweep` accepts any path).
* `m_EpisodeCounts` was law-tested on seq-102 runs only; seqs 101/103 run
  structures were captured (`unit_shape`) but not law-fitted.
* The H9/H7 probe files on disk were verified in-sweep to carry exactly one
  new unit each with the GUIDs the build reports recorded; sweeps bind to
  those bytes (md5s inside each JSON), not to the build logs.

## §6  Verification (how to re-run)

```
.venv/bin/python tools/fifth_surface.py sweep samples/rstbasicsampleproject.rvt
.venv/bin/python tools/fifth_surface.py crosscheck   # 4 sweeps + fifth_surface.json  (~2 min)
.venv/bin/python tools/fifth_surface.py rowdiff      # row_diff.json                  (~40 s)
.venv/bin/python tools/fifth_surface.py all
```

## BRANCH STATE

* **status: DONE — both rankings delivered with byte evidence; exhaustive
  per-surface coverage stated (and its limits).**  Analysis stream: nothing
  built for the viewer, nothing staged, nothing uploaded.
* **no VCS** (working tree).  Files written: `tools/fifth_surface.py`
  (new, ~1,100 lines; sweep / crosscheck / rowdiff / all),
  `experiments/regcorner/` {`fifth_surface.json` 282 KB, `row_diff.json`
  67 KB, `sweep_rst.json`, `sweep_H9.json`, `sweep_H10.json`,
  `sweep_H7.json`}, this record.  No src/tests edits (territory honored;
  stream-local tests not part of the charter's territory — the tool's
  subcommands are the re-run harness).
* **key numbers**: 203 native surfaces; 136 missing / 67 covered for H9's
  new unit; CategoryTracking 616+2183 rows = 616+2183 elements native
  (3 samples perfect), 8 untracked twin elements in H9/H10 (the only
  violations anywhere); loader touch surface = FamilyMgr +
  ElementTrackingData + m_oContentTable (241-slot delta, 3 probes);
  m_EpisodeCounts run-structure law 52/52 native + 53/53 H9; FamilyMgr
  entry zero-diff at parity; 28 ranked row fields.
* **suite**: full suite NOT run (SUITE-COORDINATION hard rule; canonical
  1697/7/2 adopted).  This stream added no tests and edited no tested code.
* **next action (orchestrator)**: the probe stream has ALREADY built and
  staged the H12/H11/H11x12/H13 lattice (`experiments/regcorner/probes/`,
  upload order in its probes.json) — H13 carries this stream's
  CategoryTracking fix, cross-verified here against the staged bytes
  (8 untracked twins in H11/H12/H11x12; 0 in H13, totality law perfect).
  Upload in the probe stream's manifest order; read verdicts with its
  `reading_the_matrix` + this record's §2 unified reading.  Row-content
  verdicts take `row_diff.json → ranked_fields` (m_author +
  multi-episode history + embedded-adoc registries first).
