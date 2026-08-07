# regcorner — THE REGISTRATION-CORNER PROBES H12 / H11 / H11x12 (batch 40)

Stream: **regcorner-probes** (2026-08-05, post-verdict-#34).  Charter: H9
(byte-copied native 22-element host constellation + all-Autodesk famdoc +
V20-shape instance, freshly REGISTERED as a new unit) FAILS while H10
(identical minus the instance) PASSES and V20 (instance of a NATIVELY-
registered unit) PASSES — symbol form, famdoc content, host elements and
instance shape are ALL exonerated by byte-copy.  Exactly two suspects
remain: **(1) the registration ROW CONTENT famload authors** (CD/CT/FM/
partition row fields) and **(2) a FIFTH project-ADocument surface** outside
the four-registry model, visited only on the instance walk.  Build the
probes that split them.

**Territory touched ONLY:** `tools/regcorner_probe.py` (new),
`experiments/regcorner/probes/**` (new), `tests/test_regcorner.py` (new),
this record, and the staging copies `probe_batch` itself writes under
`experiments/acceptance/` (batch manifest + probes + control — its designed
output).  No existing src module, tool, or test edited.  No browser (STAGE
only — the orchestrator uploads); no Autodesk install dirs; zero donors in
shipped output (every probe is PROOF-ONLY sample-derived dev content,
quarantined in experiments/, exactly like the H7/H9/SX/SL precedents).

## Result in one screen

* **THE LADDER IS BUILT, GATED, STAGED AS BATCH 40** — CTRL (byte-identical
  untouched rst copy) + **H12** + **H11** + **H11x12**, every probe
  `rvt.validate` **VALID 0 errors / 0 unexpected**, four-registry
  **coherent**, survivor law 0 removed / 0 modified, identity PASS, axis
  proofs green (see §4 for the exact numbers).
* **All three probes share ONE byte-identical parent load** = H9's exact
  recipe re-run verbatim (`hostpair_probe.build_load` imported, not
  reimplemented: same `famdoc_bisect.build_donor` rebase, same 22-element
  byte-copy machinery + ledger, same famload registration).  Each probe =
  that parent + exactly ONE axis edit (proven by per-stream accounting:
  the edit hop changes exactly the axis's stream and zero elements) + one
  V20-shape instance by H7/H9's exact template recipe.
* **H12 — the COMPLETE-COPY probe** (upload FIRST, biggest split): the
  parent with famload's all-null inline ADocument replaced by **the
  donor's own POPULATED inline ADocument** (131/239 AppInfo registries,
  ids remapped through the same famdoc rebase map, history identity
  re-keyed fresh per the measured native law — `famdoc_bisect.
  swap_inline_adoc`, the H6 machinery, now applied in the byte-copy frame
  where machinery is exonerated).  Diff vs H9 = exactly the inline
  ADocument.
* **H11 — the NATIVE-MODELED REGISTRATION probe**: the parent with
  famload's authored ContentTable row **re-authored field-for-field on the
  donor's OWN native row** — author `'Autodesk Revit'`, the real
  creation-948 / lastModification-988 stamps, the real two-bucket
  `m_EpisodeCounts` `[6 @ ep 1003, 411 @ ep 1013]` — only the ContentKey
  GUID kept ours (identity-forced).  Because our unit IS a byte-rebased
  copy of exactly that donor unit, the native row's story remains true of
  our unit's bytes (the 417-record sum, the per-record stamps the payloads
  carry).  Diff vs H9 = exactly the CT row fields.
* **H11x12 — the UNION probe**: both edits on the same parent.  Closes the
  'both required together' branch: without it, "H11 FAIL + H12 FAIL"
  could not be told apart from the fifth surface.
* **H13 (fifth-surface patch) IS BUILT AND STAGED AS BATCH 41** — the
  surface stream's ranking (`experiments/regcorner/fifth_surface.json`)
  landed AFTER batch 40 staged; its top donor-covered reach-3 candidate is
  **CategoryTracking** (host-ADocument AppInfo slot 28: per-family-cluster
  CategoryElem/GStyleElem rows; **41/52 native units incl. the donor;
  absent for EVERY famload unit — H9, H10 and H7 alike; outside the
  four-registry model**).  H13 = H11's load + the donor cluster's 4
  `m_categoryData` + 4 `m_gstyleData` rows remapped for our copies at the
  law-derived positions + one V20-shape instance (§8).

## §1  What was measured first (row_diff.json — the famload-vs-native registration diff)

`experiments/regcorner/probes/row_diff.json` (re-runnable:
`tools/regcorner_probe.py measure`).  A = the native donor row (rst unit
36, the V20 lineage); B = famload's authored row (the parent load).

| surface | native (A) | famload (B) | verdict |
|---|---|---|---|
| ContentTable row `m_author` | `'Autodesk Revit'` (**52/52 rows**) | `'rvt-writer'` | **THE row-content axis** (H11) |
| CT row `m_history` | creation 948 **<** lastMod 988 (per-unit values; lastMod 988 shared) | creation == lastMod == fresh host episode | H11 |
| CT row `m_EpisodeCounts` | **two buckets** `[{1003: 6}, {1013: 411}]`, sum = 417 = unit records (corpus: 43/52 rows 2 buckets, 9/52 3; never 1) | ONE bucket `[{fresh_ep: 417}]` | H11 |
| CT row keyset / `m_pHostDocument` | 5-key set, weak 1 (52/52 uniform) | identical | parity |
| FamilyMgr entry | `{m_surrogateId, m_familyDocGUIDs}`; GUID-list lens 0..4 | same shape, 1 GUID | **parity** (1 in native range) — no FM axis |
| ContentDocuments entry framing | corpus grammar (parse/assemble byte-exact) | identical framing | parity — the CONTENT is the axis |
| ContentDocuments inline ADocument | **34,870 B, 131/239 AppInfo registries POPULATED** | 18,057 B, **0/239 populated** | **THE ADocument axis** (H12) |
| Partition save unit | counter 417, 4 blocks, seq split 418 / 146+272 / 418, flags 4 | **frame-identical** | parity — no partition axis exists to probe |

Two de-confounding measurements, both load-bearing for the reading:

* **CT `m_EpisodeCounts` vs the inline ADocument's per-element histories is
  NOT a strict corpus law**: 49/52 native units disagree with BOTH the
  creation and the lastModification histograms of their own inline
  ElemTable.  So H12's pairing (famload row + native adoc) is not
  off-corpus on that pair — an H12 FAIL cannot be blamed on an introduced
  row↔adoc incoherence.
* **The donor's inline ADocument is fully unit-internal**: 1,611 integer id
  references, ALL inside the unit's id space; **0** references to the
  native host cluster, **0** to other host ids.  The famdoc rebase map
  alone therefore completes the H12 swap (no host-idmap pass needed), and
  `m_ownerFamilyId` remaps to the rebased self-family (gated).

## §2  The build (shared parent, single-axis edits, machine-proven)

* Parent = `hostpair_probe.build_load` verbatim (fresh GUIDs per rebuild;
  the re-derived famdoc rebase map is gated against the parent's recorded
  id range).  The parent carries H9's full copy ledger (284 id-remapped
  leaves + 5 declared content moves, zero undeclared — the byte-copy
  machinery re-proves it on every run) and famload's registration.
* Edit gates, per probe, before any bytes are written:
  * `Global/Latest` codec **byte-idempotence** on the parent
    (`encode(decode(x)) == x`) — so H11's written delta is attributable to
    the row edit alone; the exhaustive old→new leaf ledger is recorded and
    refuses if the identity GUID moved.
  * `Global/ContentDocuments` **parse/assemble byte-idempotence** on the
    parent — so H12's written delta is the one entry's payload; the swap
    gates populated-slot count == the native 131 and the remapped
    `m_ownerFamilyId` == the rebased self-family.
* Instance = `famdoc_bisect.place_probe` verbatim (ConstructedSpecimens +
  `add_family_instance` + commit; category = the family's own −2001330;
  connmgr None; the V20-certified shape re-read from the emitted bytes:
  master symbol → the copied symbol, phase 86961, header deletion
  `[311, 86961, symbol, instance]`).
* Accounting per probe, TWO hops: the **edit hop** (variant load vs the
  shared parent — proves exactly-one-stream-changed, zero element churn,
  registry-silent) and the **instance hop** (probe vs its own load — the
  H9-established +1-ElemTable-row shape), each with the full
  `bisect_instance_bug.account` battery (validator / four-registry census /
  survivor law / identity / per-stream bytes / regdiff).

## §3  The decision table (probes.json `reading_the_matrix`, staged)

* **CTRL FAIL** → round VOID.
* **H12 PASS** → the all-null inline ADocument was H9's killer (the one
  delta vs H9).  Fix = author a POPULATED inline ADocument in the product
  load path (§5 port spec).  H11x12 expected PASS (superset); H11's
  verdict then only measures whether the row ALSO matters.
* **H12 FAIL + H11 PASS** → the registration row content was the killer.
  Before porting, run the pre-branched field split (§5): the product path
  must NOT forge `'Autodesk Revit'` authorship, so the lawful fix depends
  on WHICH field discriminates.
* **H12 FAIL + H11 FAIL + H11x12 PASS** → both surfaces required together;
  port both mechanisms.
* **ALL THREE FAIL** → neither suspect-(1) surface, alone or united, cures
  H9 → **the FIFTH SURFACE is convicted by elimination**; the surface
  stream's candidate list drives H13 (`regcorner_probe.py h13 <spec>`).
* **H11x12 FAIL while H11 or H12 PASS** → lattice-inconsistent; oracle
  noise; re-run.

## §4  Gates (all machine, per probe; no acceptance claim)

Build 99.3 s, zero errors.  Parent `RC_parent_load.rvt` md5 `f6a94004…`,
plan GUID `ceaaa6e7…`, symbol 1472961, family 1472942 (fresh GUIDs are
minted per rebuild — the STAGED bytes are canonical; re-hash after any
rerun).  Every probe places instance **1472964** (same id — same parent
watermark by construction).

| gate | H12 `80321ae4` | H11 `b4a8900c` | H11x12 `231e86d0` |
|---|---|---|---|
| edit hop: streams changed vs the shared parent | **ContentDocuments only** (+4,094 B inflated) | **Latest only** (+16 B inflated; account's member-size delta 0) | both, same deltas |
| edit hop: elements added/removed/modified | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| edit hop: four-registry delta | 0/0/0/0 (registry-silent) | 0/0/0/0 | 0/0/0/0 |
| edit hop: validator | 0 errors | 0 errors | 0 errors |
| instance hop: validator | **0 errors** / 1 warning* | 0 / 1* | 0 / 1* |
| instance hop: census coherent / survivor / identity | True / OK / PASS | True / OK / PASS | True / OK / PASS |
| instance hop: ElemTable adds | [1472964] only | same | same |
| axis: inline-adoc populated slots (want) | **131** (131) | **0** (0) | **131** (131) |
| axis: CT row author / EpisodeCounts buckets (want) | rvt-writer / 1 (famload) | **Autodesk Revit / 2** (native) | **Autodesk Revit / 2** |
| instance V20 shape (master symbol / phase 86961 / deletion `[311, 86961, sym, self]` / connmgr None / symbol GElement+geomSteps) | all green | all green | all green |

\* the 1 warning = the standing inherited decoder gap present in the
untouched sample itself (`7/32011 seq-102 records failed schema decode` on
virgin rst; `7/32451` here — the H7/H9 precedent warning, not ours).

Sharp facts read back from the emitted bytes:

* The swapped inline ADocument re-encodes to **exactly the native byte
  length (34,870)** — the remap is width-neutral; 131/239 populated slots,
  53 CD entries, `m_ownerFamilyId` == the rebased self-family (gated),
  4 history identity GUIDs re-keyed to one fresh GUID (the measured native
  law: identity GUIDs equal each other, independent of the unit GUID).
* H11's row equals the donor's native row **field-for-field** (live test
  `test_h11_row_is_the_native_mold_except_guid`), GUID excepted; the
  retrofit leaf ledger = exactly 4 deltas (author, creationDate, lastMod,
  EpisodeCounts), `m_pHostDocument` byte-equal, identity GUID untouched.
* Codec byte-idempotence gates held on the parent (`encode(decode(x)) ==
  x` for Global/Latest; parse/assemble roundtrip for ContentDocuments) —
  the written deltas are attributable to the axis edits alone.

**STAGED AS BATCH 40** (`experiments/acceptance/batch_40.json`): CTRL =
`CTRL_rstbasicsampleproject_b40.rvt`, **byte-identical to the untouched
rst sample** (md5 `b3235ad2…`, machine-verified); reading order CTRL →
H12 → H11 → H11x12; every staged copy md5-verified against its source and
the manifest.  Stream-local tests: `tests/test_regcorner.py` → **16
passed** (row-diff pins, shared-parent design, single-axis stream deltas,
axis-independence matrix, the H11 mold-parity live read, V20 instance
shape, gates, decision table, staged batches + controls, H13 axes +
batch).  Full suite NOT run (SUITE-COORDINATION hard rule; canonical
count 1697/7/2 adopted).

## §5  Pre-branched follow-ups (specs recorded now, built only on verdict)

* **H12 mechanism → product port** (if H12 or H11x12 convicts the
  ADocument): extend `rvt.famgen.factory.author_embedded_adocument` with a
  populated-registry mode (opt-in, default OFF — the famload_hostfix
  wiring precedent): author the family-editor AppInfo registries for OUR
  famdoc content, modeled on the corpus census of WHICH of the 131
  populated slots are universal vs content-dependent (the surface stream's
  slot census is the spec source when it lands; `famdoc_bisect.
  famdoc_diff.json` §6 already quantifies the gap).  DO NOT build DEMO v4
  until the verdict picks the mechanism (charter rule).
* **H11 mechanism → field split first** (if H11 convicts the row): H11a =
  author-only (`'Autodesk Revit'`, famload's history/counts), H11b =
  episode-shape-only (native history/counts, author `'rvt-writer'`) — the
  same retrofit machinery with a partial mold (one-line changes to
  `CT_IDENTITY_FIELDS` / the mold dict).  If the discriminator is the
  episode SHAPE, the lawful product port = derive `m_EpisodeCounts` from
  the unit's actual per-record episode stamps (a truthfulness fix:
  famload's fresh single bucket is already truthful for freshly-authored
  famgen units; for REBASED donor units the donor's stamps are the truth).
  If the discriminator is the AUTHOR STRING, the product path cannot ship
  it — forged Autodesk authorship in deliverables is a provenance/counsel
  question, recorded here for the orchestrator.
* **H13 mechanism → product port** (if H13 convicts CategoryTracking):
  famload/famgen author the cluster's `m_categoryData`/`m_gstyleData` rows
  at load time for every family-scoped CategoryElem/GStyleElem they emit,
  next to the ETD symbol row they already author — the row shapes and
  position laws are §8's measured constants; `patch_category_tracking` is
  the reference implementation.  (H13 was BUILT this session — see §8 —
  the moment the surface stream's ranking landed; this bullet is its port
  spec.)

## §6  Verification (how to re-run)

```
.venv/bin/python tools/regcorner_probe.py measure   # row_diff.json
.venv/bin/python tools/regcorner_probe.py build     # parent + H12 + H11 + H11x12 (+ gates + probes.json)
.venv/bin/python tools/regcorner_probe.py verify    # re-run gates on emitted probes
.venv/bin/python tools/regcorner_probe.py stage     # batch 40 (control = untouched rst copy)
.venv/bin/python tools/regcorner_probe.py h13       # H13 from experiments/regcorner/fifth_surface.json
.venv/bin/python tools/regcorner_probe.py stageh13  # batch 41 (control = untouched rst copy)
.venv/bin/python -m pytest tests/test_regcorner.py -q   # 16 passed
```

## §7  The surface stream (polled; consumed for H13 the moment it landed)

Timeline: batch 40 was built and staged while
`docs/inbox/regcorner-surface.md` and any ranking were still absent (only
their working sweeps `sweep_{rst,H7,H9,H10}.json` existed — identity-GUID
raw scans + typed walks, no verdicts), exactly the charter's "build the
parts that need no ranking" ordering.  **Immediately after batch 40
staged, their `fifth_surface.json` landed**: 203 native per-unit surfaces
censused, 136 candidate surfaces missing for the new unit, ranked by
instance-walk reach (3 = holds symbol/family-cluster element ids … 0 =
unit-internal self-references).  Top donor-covered reach-3 candidates =
the three **CategoryTracking** paths (`m_categoryData[].m_categoryId`,
`m_gstyleData[].m_categoryId`, `m_gstyleData[].m_gstyleId` — one registry,
217 cluster-owned occurrences, 41/52 units, donor covered, missing for the
new unit in H9/H10/H7 alike).  H13 consumes exactly that (§8); the build
ASSERTS the top candidate still matches and refuses on ranking drift.
Runner-up donor-covered candidate NOT built (noted for the next round):
`Partitions:unit0:seq102:AnalyticalMember[other].m_sectionType` — a host
USAGE reference (6 units, 90 occ), not a registration surface; famload's
`repoint_usage` is the existing vehicle if it ever ranks.  `row_diff.json`
remains MY measurement of the row axis; no row_diff/ranking of theirs
contradicts it (their census is GUID/ElementId-surface-shaped, not
row-field-shaped — complementary, not overlapping).

## §8  H13 — the fifth-surface patch (built + staged as batch 41)

Measured laws the patch enforces (re-runnable in
`regcorner_probe.fifth_surface_rows` / `patch_category_tracking`):

* `m_categoryData` (616 rows) = 30 parent-keyed CONTIGUOUS runs, ascending
  `m_categoryId` within a run; the donor cluster's 4 rows sit in the
  `-2000059` run (indices 117..486) as `{m_parentCategoryId: -2000059,
  m_categoryId: <CategoryElem twin>}`.
* `m_gstyleData` (2,183 rows) = globally ascending by `(m_categoryId,
  m_gstyleId)`; the donor cluster's 4 rows are `{catTwin, gstyleTwin,
  m_gstyleType: 1}` pairs.
* Our byte-copied cluster carries 4 CategoryElem + 4 GStyleElem twins
  (1472946/48/52/58 + 1472949/50/53/59) — PRESENT as elements, absent
  from the registry (the K5/K6/P4/P6 lesson in miniature: registries must
  index present rows; here the rows are simply missing).

H13 = `H11_load` + the donor's 8 rows remapped through the host copy
idmap, inserted at the end of the `-2000059` run (our ids exceed the run
max — the ascending law's position) and at the global sorted positions
(ditto), with the codec byte-idempotence gate first and the run/ascending
laws re-asserted post-edit + one V20-shape instance.  **H13.rvt md5
`ae3712ef…`, instance 1472964; validator 0 errors / 0 unexpected (probe
and load); edit hop vs `H11_load` = Global/Latest ONLY, zero element
churn, registry-silent; census coherent; survivor OK; identity PASS; axis
proofs: native CT row + famload's null adoc + all 8 CategoryTracking rows
present with laws intact + the V20 instance shape.**  Staged as **batch
41** (`CTRL_rstbasicsampleproject_b41.rvt` byte-identical to the sample +
H13.rvt, md5-verified).

Reading H13 against batch 40 (also in probes.json): **H13 PASS where H11
FAILED** convicts the fifth surface (CategoryTracking specifically —
port = famload/famgen author the cluster's registry rows at load time,
next to the ETD symbol row they already author).  **H13 FAIL alongside an
all-FAIL batch 40** extends the elimination to the ranking's next
donor-covered candidate.  H13 carries H11's row edit too (charter shape:
"H11 plus the missing surface entries"), so an H13 PASS + H11 FAIL + H12
FAIL leaves {row+fifth together} vs {fifth alone} split by the NEXT round
(H13b = parent + CategoryTracking only), noted pre-branched.

## BRANCH STATE

* **status: DONE — BATCH 40 (H12 + H11 + H11x12, untouched-rst control)
  AND BATCH 41 (H13, the fifth-surface patch from the surface stream's
  published ranking) BUILT, GATED, STAGED, with the decision table in
  probes.json and here (§3, §8).**  STOPPED AT READY: nothing uploaded;
  the viewer queue is the orchestrator's.  DEMO v4 deliberately NOT built
  (charter rule: verdict picks the mechanism first; §5 + §8 carry the
  pre-branched port specs for all three mechanisms).
* **no VCS** (working tree, not a git repo).  Files written:
  `tools/regcorner_probe.py` (new, 1,208 lines; measure/build/verify/
  stage/h13/stageh13), `tests/test_regcorner.py` (new, 16 pass),
  `experiments/regcorner/probes/` {H12.rvt md5 `80321ae4`, H11.rvt
  `b4a8900c`, H11x12.rvt `231e86d0`, H13.rvt `ae3712ef`, probes.json,
  accounting.json, row_diff.json, `_build/**` (RC_parent_load.rvt + side
  report + the four per-axis load files)}, this record, and staging
  copies + `batch_40.json` + `batch_41.json` +
  `CTRL_rstbasicsampleproject_b40/b41.rvt` (each byte-identical to the
  sample, md5 `b3235ad2…`) under `experiments/acceptance/` via
  `probe_batch.stage` (its designed output).  No existing src module,
  tool, or test edited; `experiments/regcorner/*.json` top-level (the
  surface stream's) read, never written.
* **gates**: every probe validator VALID 0 errors / 0 unexpected (1
  standing inherited warning, present in the virgin sample); four-registry
  coherent; survivor law 0/0; identity PASS; single-axis stream deltas
  machine-proven per probe (edit hop: exactly the axis's stream, zero
  element churn, registry-silent); codec byte-idempotence gated before
  every edit; axis proofs green (131-slot adoc / native-mold row / both /
  +8 CategoryTracking rows with laws re-asserted); V20 instance shape
  read back from the emitted bytes on all four; controls + staged copies
  md5-verified.
* **NOT VIEWER-TESTED**: every claim above is the machine gate; no
  acceptance claim is made.  All probes PROOF-ONLY (quarantined
  sample-derived content; never bundled — the deliverable rule's dev-only
  lane).
* **next action (orchestrator)**: upload batch 40 in manifest order
  (**H12 first** — the biggest split), then batch 41 (H13); verdicts to
  `docs/coverage/viewer-certified.json`, read with
  `experiments/regcorner/probes/probes.json → reading_the_matrix` (§3/§8
  mirror).  H12 PASS ⇒ the inline-ADocument port (§5); H11 PASS ⇒ the
  H11a/H11b field split before any port (author-string provenance
  caveat); H13 PASS with H11 FAIL ⇒ the fifth surface is
  CategoryTracking — port = author the cluster's registry rows in
  famload/famgen next to the ETD row; all four FAIL ⇒ move to the
  ranking's next donor-covered candidate (H13b design pre-branched, §8).
