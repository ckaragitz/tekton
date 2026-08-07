# adoc-probes — READER-TOLERANCE PROBES of `Global/Latest` (2026-08-03)

Stream: **latest-probes**. Charter: build the empirical shortcut for genesis-2.
We cannot yet encode the `ADocument` (`Global/Latest`); in the genesis
candidate `G0.rvt` that stream is carried **verbatim** from the rstbasic
sample (~94 % of G0's bytes, per `docs/inbox/genesis-audit.md` §B1). If
Autodesk's READER tolerates a *sanitized* Latest, genesis can strip Autodesk /
sample expression from it **now**, before an encoder exists. This stream builds
the mutation-variant generator, emits 16 validator-clean probe files that each
edit ONLY `Global/Latest` in a length-preserving way, and states below exactly
what each viewer verdict UNLOCKS. **We cannot learn the verdicts ourselves** —
the orchestrator uploads the probes to Autodesk's translator; this record is
the decision table.

Deliverables: `tools/latest_probes.py` (generator, re-runnable, deterministic
except the container mtime), `experiments/genesis/latest/probes/*.rvt` +
`*.json` (16 probes + per-probe change notes) + `manifest.json` (ordered
viewer queue + decision table), `tests/test_latest_probes.py` (9 tests, pass).

---

## 0. One-screen verdict

**16 probe files emitted, every one `tools/rvt_validate.py`-VALID (0
errors).** 8 mutate the working sample (`rstbasicsampleproject.rvt`, a
known-good reader file: the whole-file rewrite V15 already passed), 8 mutate
G0 (whose `Global/Latest` is **byte-identical** to rstbasic's — confirmed,
sha256 `3cf64f8f…`, raw stream identical). Each file rewrites ONLY
`Global/Latest` (prefix u64 5 kept, payload edited in place with every edit
byte-length-preserving so no offset shifts, re-gzipped by our writer at
level 3 + sync-flush, re-framed with real CRCIO page ECC, container rebuilt
with all other streams copied byte-for-byte). Self-verified per file:
inflated payload == the edited buffer, prefix intact, gzip CRC valid, every
full page's ECC re-encodes to the emitted trailer.

The excavation that made the probes possible (all measured this session on
the rstbasic `Global/Latest`, 1,586,246 inflated bytes):

| region / content class | where | share | probe |
|---|---|--:|---|
| prologue, build history, ExServices GUID map, u32-keyed table, pointer run | 0x0–0x1bf7 | 0.4 % | untouched (machinery) |
| `NobleSecondaryData` color-fill entries (stock scheme names + ElementIds) | 0x1bf7–0x8cb3 | 1.8 % | ids only (P4) |
| secondary data: browser-org folders, MEP naming schemes, updater ids, **the sheet / view / assembly naming registry**, id arrays (7,345 of the id refs live here) | 0x8cb3–0x26c0e | 7.8 % | P1/P2 (names), P4 (ids) |
| **Forge corpus: 1,315 `(AString typeid, AString json)` pairs — units 893, parameter groups 422, then aec specs / revit groups; contiguous, CLEAN (no compressed continuation in rstbasic), 1,333,340 bytes** | 0x26c0e–0x16c664 | **84.1 %** | P3a / P3b |
| tail: system-family & numbering-scheme defaults, DB server, `RbsSystem` defaults, `RevisionSettings`, **LB reconcile map (102 `'<id>.<n>.<id>'` keys + 103 JSON records naming sample ids as TEXT)**, room-name table, materials, employee usernames | 0x16c664–EOF | 5.9 % | P1 (names/users), P4 (ids), P6 (LB map) |

Everything the audit flagged is here and is now individually addressable:
the sample's naming (33 sheet/view/assembly/detail-number strings, 11 room
names, 2 materials, 2 Autodesk usernames `liqi` / `macalis`), the Forge corpus
(84 % of the stream, 1.27 MB of JSON bodies), and **9,602 references to 6,175
distinct sample element ids** (the audit's 6,175 = distinct count; all 6,175
dangling in G0, all live in rstbasic — the two bases split "-1 breaks it" from
"dangling breaks it").

---

## 1. The probe ladder (per base) and what each verdict UNLOCKS

Base `rst` = rstbasic (working file; every verdict attributes purely to the
Latest edit). Base `G0` = the genesis candidate (identical Latest payload;
inventory 100 % ours; **its ids are all dangling**). G0's own viewer status is
UNMEASURED — upload `experiments/genesis/G0.rvt` itself as the control for the
G0 set.

| probe | edits | bytes changed | reader question | PASS unlocks for genesis-2 |
|---|--:|--:|---|---|
| **P0_control** | 0 | 0 | is OUR re-encoding of Latest accepted at all? | nothing new (yardstick). FAIL => whole set void, fault = our Latest framing, not content |
| **P1_names** | 48 | 230 | can the project's authored names be renamed inside the ADocument? | genesis can strip ALL sample naming from Latest by length-preserving substitution TODAY (audit B2/B3 naming exhibits retired) |
| **P2_names_blank** | 48 | 219 | must names be non-blank / distinct? | names carry no reader rule at all; FAIL-while-P1-passes => emit distinct non-empty names |
| **P3a_forge_stub** | 1,315 | 512,059 | is the CONTENT of the 1.3 MB Forge unit/spec/parameter-group JSON corpus load-bearing? | corpus is NOT carried expression: regenerable as trivial self-stubs (audit's 78 % Forge share retired; counsel item (a) shrinks to "may we emit stubs naming Autodesk typeids") |
| **P3b_forge_blank** | 1,315 | 511,074 | are the JSON bodies PARSED at open at all? | corpus can be blanked outright (stronger than P3a) |
| **P4_ids_null** | 9,602 | 76,765 | are the ~6,175 element-id references load-bearing? | id registries can be nulled (-1) wholesale; on G0 removes the last id lineage into the sample; `G0_P4 PASS` while `G0 FAILS` => dangling ids were G0's blocker |
| **P5_combined** | 9,650 | 76,995 | do P1 + P4 compose? | OUR names + NO sample-id refs in one Latest |
| **P6_all** | 12,485 | 655,178 | can the ENTIRE Autodesk/sample expression be removed length-preservingly (names blanked, Forge blanked + typeids scrubbed, ids nulled, LB map scrubbed)? | **genesis-2 needs NO ADocument encoder to close the Latest stream ledger — ship the scrubbed Latest, defer the encoder** |

The same eight exist as `G0_P0_control` … `G0_P6_all`.

### Decision table (the return value of this stream)

* **P1 passes** ⇒ genesis renames every project string (rooms, sheet
  nos/names, view names, assembly, materials, usernames) by length-preserving
  substitution — no encoder needed. *Bonus tell:* if the viewer's sheet list
  still shows `FOUNDATION-2700` / `S206` after P1, the Latest name registry is
  not the display source (names come from the sheet elements) — Latest's copy
  is a cache and can be anything.
* **P3a passes** ⇒ the Forge corpus content is not load-bearing; regenerate it
  as `{"typeid": ...}` stubs (or per **P3b**, blank it) — the 84 %-of-Latest
  Autodesk corpus and its licence question both collapse.
* **P4 passes** ⇒ the id registries can be nulled; the 6,175 dangling
  references (audit §B2) are not the reader's business.
* **P6 passes** ⇒ the maximal sanitization is accepted: a genesis Latest
  with NO sample naming, NO Forge JSON, NO sample id references and NO LB map
  is achievable TODAY by pure substitution. The ADocument encoder drops off
  the critical path for the G1 gate's Latest exhibit.
* **Everything fails but P0 passes** ⇒ ADocument content is validated in
  detail ⇒ the ADocument decoder→encoder (genesis.md §6.3) is unavoidably the
  critical path. Even then the failure PATTERN localizes it (names vs corpus
  vs ids).

---

## 2. Viewer queue — ordered by information value

Upload in this order; each is validator-VALID and one attributable class
beyond the last. Stop early once the pattern is clear. (Also in
`experiments/genesis/latest/probes/manifest.json`.)

1. `probes/P0_control.rvt` — yardstick (expected PASS).
2. `probes/P1_names.rvt` — the cheapest big win (48 edits, 230 bytes).
3. `probes/P4_ids_null.rvt` — the dangling-id question, isolated on a live file.
4. `probes/P3a_forge_stub.rvt` — the 84 %-of-the-stream question.
5. `probes/P5_combined.rvt` — composition of the two headline operations.
6. `probes/P2_names_blank.rvt` — blank vs neutral names (refinement of P1).
7. `probes/P3b_forge_blank.rvt` — blank vs stub JSON (refinement of P3a).
8. `probes/P6_all.rvt` — the moonshot: everything sanitized at once.
9. `experiments/genesis/G0.rvt` — **control for the G0 set** (no G-rung has a
   recorded viewer verdict; the audit §B6 retracted the R4s claim).
10. `probes/G0_P1_names.rvt`, 11. `probes/G0_P4_ids_null.rvt`,
12. `probes/G0_P3a_forge_stub.rvt`, 13. `probes/G0_P5_combined.rvt`,
14. `probes/G0_P2_names_blank.rvt`, 15. `probes/G0_P3b_forge_blank.rvt`,
16. `probes/G0_P6_all.rvt` — the G0 mirror set; only meaningful against #9.

Reading G0 outcomes: if **G0 FAILS but G0_P4 PASSES**, dangling ids were the
G0 blocker and nulling fixes it (genesis-2 assembles G0 + P4-style nulling
immediately). If **G0 PASSES**, the reader ignores dangling ids and the G0_
set measures whether sanitizing on top of a fully-ours inventory holds.

---

## 3. Method — why every probe is offset-safe and one-class-attributable

* **Length preservation everywhere.** AString edits replace the UTF-16 code
  units, never the u32 count ('Hall'→'Rm07', 'FOUNDATION-2700'→
  'Nm0000000000003', 15 units each side); JSON bodies are replaced by
  same-count text ('{"typeid": "<same typeid>"' + spaces + '}' for P3a,
  spaces for P3b); ids become i64 −1 in place; the LB `'<id>.<n>.<id>'` keys
  keep their exact dotted digit-field widths ('1046264.1.1471776'→
  '9000001.9.9000001'). `apply_edits()` asserts equal lengths and no overlap;
  the payload byte length never changes, so no length-prefix / pointer /
  offset anywhere in the stream needs recomputation. Uniqueness of
  replacements is preserved within each class (index-based tokens) so a
  duplicate-name / duplicate-key rule cannot masquerade as a content rule.
* **Classification, not guessing.** Every ASCII AString in the payload
  (3,521, plus 21 single-character detail numbers recovered by the naming-table
  structural rule) is assigned one class: `forge.typeid`/`forge.json` (the
  1,315-pair walk), `build`, `machinery` (Autodesk/Revit class names,
  updaters, `WireSizes.xml`, DB server…), `category` (413 stock category /
  parameter / naming-scheme labels — deliberately NOT touched: 'Rooms : Name',
  'Color Fill', 'Space Name', browser-organization folder names, 'Unassigned',
  'Generic'), `lb-map`/`lb-json`, `user`, `project.naming` (u32 marker{1,2} +
  string + negative built-in category/parameter id = the sheet/view/detail
  numbering registry), `project.room`, `project.material`. **Zero strings are
  left unclassified** (asserted by the test suite). P1's target set = the 48
  `project.*` + `user` strings; the exact before→after map is in
  `P1_names.json`.
* **The Forge corpus in rstbasic is CLEAN.** Contrary to the racbasic-tuned
  region heuristics in `docs/streams/03-global-latest.md` (which posited an
  LZ-compressed continuation), rstbasic's dictionary is exactly the declared
  893 `(typeid, json)` unit pairs, then a 466-byte Extensible-Storage schema
  table (2 entities: `Identity`/`TCHAR`/`AREXContentGenerator`,
  `DaylightingAnalysisInfo`), then a second dictionary of 422 parameter-group
  and spec pairs — 1,315 contiguous clean pairs = 1,333,340 bytes (84.1 % of
  the stream), the only inter-pair gaps being tiny per-dictionary headers.
  Every JSON body is therefore individually replaceable at exact length.
  (One json contains a surrogate-pair emoji symbol; the walker's AString
  reader accepts surrogates — the old `plausible_astring` did not, which is
  why the framing pass under-counted here.)
* **The id scan and its stated caveat.** References are found by scanning
  every byte offset for a little-endian i64 whose value is a known rstbasic
  ElemTable id above 4,700 (small values collide with counts/enums/class
  ordinals). 9,602 hits, 6,175 distinct, **zero overlapping hits** (no
  alignment ambiguity), 54 % adjacent to another id/−1. In-range NON-id
  windows exist too (1,845), so the expected false-positive count is
  1,845 × (13,936 / 1,472,524) ≈ **17 of 9,602 (0.18 %)** — a P4/P5/P6 *FAIL*
  carries this small ambiguity (some non-id field may have been clobbered);
  a *PASS* is unaffected. The per-hit context tag is recorded in the compact
  `id_ranges_compact` list of each note so a follow-up can bisect the
  isolated hits if needed.
* **One stream, one writer.** `rewrite_latest()` = the accepted V15 recipe on
  a single stream: `prefix + gzip_member(payload, level=3, sync_flush=True)` →
  `ecc.frame_stream` → `write_cfb`. P0 (zero content change) isolates the
  re-encode itself; every other rst-base failure is therefore content, and
  the class is named by the probe id.

---

## 4. New format facts found (for KNOWLEDGE.md merge)

1. **The sheet / view / assembly NAMING REGISTRY** lives in `Global/Latest`
   (rstbasic 0xc740–0xcc38): a run of entries `u32 marker(1|2) | AString name
   | i64 built-in category id (e.g. −2,008,113) | i64 built-in parameter id
   (e.g. −1,001,405) | [i64 −1]`, holding sheet numbers ('S206'), sheet names
   ('FOUNDATION-2700'), view names ('Elevation 1', 'Section 1'), assembly
   names ('L1 wall frame hall 5') and the used detail numbers ('52', '8',
   '101'…). This is the document's used-name-per-category index (Revit's
   duplicate-name checker), a COPY of names owned by the elements.
2. **The room-name table** (0x176ecc…): `AString name` + fixed-width numeric
   records per room ('Bathroom', 'Hall', 'Kitchen & Dining', 'Master
   Bedroom'…), separate from the room elements in the partitions.
3. **The LB reconcile map** (tail): 102 keys `'<localElementId>.1.<counter>'`
   each paired with a JSON record `{"Id":n,"LocalId":"<id>",…,"ExternalId":
   "<id>",…}` + a final `LB_MetaData` record `{"Id":1,"ProjectId":"",
   "LineageId":"",…}` — sample element ids referenced **as text**, invisible
   to any binary id scan and to `provenance.py`.
4. **rstbasic's Forge corpus is 84.1 % of `Global/Latest`** and fully clean:
   dictionary 1 = 893 unit/dimension/symbol schemas (declared count 893
   exactly), a 466-byte ES schema table, dictionary 2 = parameter groups
   (count 422) + aec specs / disciplines / revit groups; 1,315 pairs total,
   json lengths 161–2,191 chars.
5. **Two Autodesk usernames inside Latest itself**: 'liqi' (0x26a1a, marker
   u32 1 + AString + i64 element id) and 'macalis' (0x16d91d, tail, next to
   the numbering-scheme partition) — the audit's DIT usernames have Latest
   siblings the DIT scrub does not reach.
6. `Level 1` / `Level 2` / 'A1 metric' / 'Framing Plans' do NOT occur in
   `Global/Latest` — level and most view names live only in the elements;
   Latest carries sheet/view names only in the naming registry (item 1).

---

## 5. Files, ordered by what each proves (the viewer queue lives in §2)

| item | path | state |
|---|---|---|
| generator (analysis + classification + edit machinery + 8 probes × 2 bases + notes + manifest) | `tools/latest_probes.py` | done, deterministic |
| 16 probe files + 16 change notes + manifest | `experiments/genesis/latest/probes/` | on disk, all `rvt_validate` VALID |
| tests: replacement generators, length-preserving edits + overlap rejection, census/classification & id scan on synthetic payloads, rstbasic analysis facts (11 rooms, 6,175 distinct ids, ≥1,300 forge pairs, 0 unclassified), end-to-end generation of 3 probes with structural + consistency validation | `tests/test_latest_probes.py` | 9/9 pass |
| this record | `docs/inbox/adoc-probes.md` | — |

Validator summary pasted (`.venv/bin/python tools/rvt_validate.py --quiet
experiments/genesis/latest/probes/*.rvt experiments/genesis/G0.rvt`): all 17
lines `OK … errors=0`; the rst-base files carry `warnings=1` = the source's
own known Extensible-Storage decode gap ("7/32011 seq-102 records failed
schema decode (RebarShape x6, DataStorage x1)"), present in untouched
rstbasic too; the G0-base files are `warnings=0`.

Reproduce: `.venv/bin/python tools/latest_probes.py` (~60 s, both bases,
all 8 probes each); `--analyse` for the analysis dump only; `--only
P1_names,P4_ids_null` for a subset; `--base rst|G0`.

## 6. Unknowns / follow-ups

1. The verdicts themselves (viewer only) — this stream's whole point.
2. Color-fill scheme names ('HVAC Zones : Schema 1', 'Spaces : Schema 1')
   and browser-organization folder names were classified `category` (stock
   Autodesk naming) and are NOT touched by any probe. If genesis wants those
   authored too, add a `P1b_schemes` variant — one line in the classifier.
3. The GUID-keyed ExServices map (52 Autodesk service GUIDs), the u32-keyed
   manager table and the `NobleSecondaryData` object framing are machinery
   and untouched; whether they can be REDUCED (not just tolerated) is a
   different experiment (needs the ADocument decoder).
4. The 466-byte Extensible-Storage schema table between the two Forge
   dictionaries (`Identity`, `AREXContentGenerator`, `DaylightingAnalysisInfo`)
   is left intact by every probe; blanking it is a candidate P7 if P6 passes.
5. If P4 FAILS, bisect isolated-context hits (2,848) vs id-adjacent (5,215)
   using the `id_ranges_compact` context tags — one flag to add.
6. The G0 base is only interpretable relative to `G0.rvt`'s own verdict
   (never measured) — hence #9 in the queue.

## Diffs requested outside my territory

None required for correctness — the tool uses only public APIs
(`rvt.container.open_rvt`, `rvt.elemtable.parse_elemtable`,
`rvt.writer.gzip_member`, `rvt.ecc`, `rvt.cfb_writer.write_cfb`,
`rvt.roundtrip.read_entries`, `rvt.validate.validate_file`). Two doc
corrections for the owner of `docs/streams/03-global-latest.md`: (a) the
rstbasic units dictionary is CLEAN (893 pairs, no compressed continuation);
the "opaque LZ blob" hypothesis is a racbasic/rme phenomenon at most; (b) its
racbasic-tuned region map mislabels rstbasic's tail (rooms/materials/LB map)
as "units degraded / opaque".

BRANCH STATE: repo has no VCS (plain directory); all work is new uncommitted
files: `tools/latest_probes.py`, `tests/test_latest_probes.py`,
`docs/inbox/adoc-probes.md` (this), `experiments/genesis/latest/probes/`
(16 `.rvt` + 16 `.json` + `manifest.json`). No existing `src/rvt/*.py`,
`tools/`, tracker or knowledge file modified. `tests/test_latest_probes.py`
9/9 pass. Full suite (`.venv/bin/python -m pytest tests/ -q
--ignore=tests/oracle`): **503 passed, 1 failed** — the single failure is
the PRE-EXISTING `tests/test_plugin_sync.py::test_plugin_is_in_sync_with_source`
(plugin bundle stale vs a concurrent stream's new `src/rvt/genesis/*` and
`famgen/facts/*`; fix = `python tools/sync_plugin.py`, orchestrator/plugin
territory, already flagged by the genesis-audit and genesis-reduction
records). READY.
