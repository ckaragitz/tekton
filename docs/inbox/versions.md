# MULTI-VERSION PHASE A — problem (C): Revit 2025/2024 read parity + the version model

Stream: **versions** (2026-08-04).  Target user runs **Revit 2025**; Revit
cannot open newer files, so the certified 2026 pipeline is unusable to him.
Phase A charter: acquire the 2025/2024 Autodesk samples, prove the read
stack at decode parity (or name the exact parser deltas), build the version
model + creation guards, and write the 2025 genesis campaign plan.
**All four delivered; DONE conditions met.**

Deliverables in this record:
1. §1 acquisition (12 files, hashed, quarantined, deny-list verified)
2. §2 the read-parity table (the whole stack, 18 files, 3 releases)
3. §3 what actually differs between releases (the finding)
4. §4 the version model (`src/rvt/versions/`) + guards
5. §5 the 2025 genesis plan + constructor portability (pointer)
6. §6 tests + full-suite run
7. §7 proposed patches for other territories (exact diffs)

---

## 1. ACQUIRE — done, no login needed

Autodesk hosts every release's sample projects on its own CDN, plain HTTPS:

    https://revit.downloads.autodesk.com/download/<YEAR>RVT_RTM/Docs/InProd/<stem>.rvt

Downloaded all six projects per release (rac/rst/rme × basic/advanced;
mandated set = the three basics, advanced kept for corpus parity):

* `samples/2025/` — 6 files, `BasicFileInfo` reads `Format: 2025`
  (build `Development Build`); full sha256 table in `samples/2025/SOURCES.md`.
* `samples/2024/` — 6 files, `Format: 2024`, build `20230308_1635(x64)`;
  table in `samples/2024/SOURCES.md`.

All 12 sha256s re-verified against SOURCES.md this session.  Quarantine:
**DEV-ONLY, never shipped, same rule as the 2026 samples** — enforced three
ways (sync allow-list never sources `samples/`; `.rvt` in `BINARY_EXT`;
`audit_deny` scans the plugin tree).  Verified: no `*sample*.rvt/.rfa/.rte`
under `plugin/` (only our own pinned genesis base + our authored examples);
`tools/sync_plugin.py --check` deny-scan clean (see §6 for the sync run);
`rvt.frontdoor.base.is_autodesk_sample()` refuses them as a base by design.

## 2. READ STACK — full parity, all three releases

`python -m rvt.versions.parity` (new harness, `src/rvt/versions/parity.py`)
runs the ENTIRE read stack per file — container streams → gzip members
(CRC) → ECC page framing → StreamWalker block framing → `rvt.schema.parse`
on the file's `Formats/Latest` → schema-directed object decode →
`rvt.validate` layered validator — with the file's own framing ordinals in
force via `rvt.versions.reading`:

| file | rel | streams | std | gzip (ok/tot) | pages | blocks(err) | schema size/classes | parse | decode clean | records | verdict (E/W) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rstbasicsampleproject.rvt | 2026 | 12 | 11/12 | 422/422 | 108 | 414(0) | 496,597/4,690 | OK | 99.98% (32,011/32,018) | 96,192 | VALID (0/1) |
| racbasicsampleproject.rvt | 2026 | 13 | 12/12 | 1164/1164 | 307 | 1156(0) | 496,597/4,690 | OK | 100.00% (85,814/85,814) | 257,934 | VALID (0/0) |
| rmebasicsampleproject.rvt | 2026 | 13 | 12/12 | 2058/2058 | 506 | 2050(0) | 496,597/4,690 | OK | 99.18% (142,174/143,345) | 427,440 | VALID (0/1) |
| rstbasicsampleproject.rvt | 2025 | 12 | 11/12 | 424/424 | 107 | 416(0) | 484,585/4,600 | OK | 99.98% (31,936/31,943) | 95,967 | VALID (0/2) |
| racbasicsampleproject.rvt | 2025 | 13 | 12/12 | 1165/1165 | 307 | 1157(0) | 484,585/4,600 | OK | 100.00% (85,740/85,740) | 257,712 | VALID (0/1) |
| rmebasicsampleproject.rvt | 2025 | 13 | 12/12 | 2057/2057 | 506 | 2049(0) | 484,585/4,600 | OK | 99.18% (142,112/143,283) | 427,254 | VALID (0/2) |
| rstadvancedsampleproject.rvt | 2025 | 13 | 12/12 | 1020/1020 | 236 | 1012(0) | 484,585/4,600 | OK | 100.00% (64,890/64,890) | 195,213 | VALID (0/1) |
| racadvancedsampleproject.rvt | 2025 | 13 | 12/12 | 1007/1007 | 267 | 999(0) | 484,585/4,600 | OK | 100.00% (59,379/59,379) | 178,503 | VALID (0/1) |
| rmeadvancedsampleproject.rvt | 2025 | 13 | 12/12 | 2588/2588 | 603 | 2580(0) | 484,585/4,600 | OK | 99.41% (189,332/190,448) | 569,277 | VALID (0/2) |
| rstbasicsampleproject.rvt | 2024 | 12 | 11/12 | 423/423 | 107 | 415(0) | 470,502/4,492 | OK | 99.98% (31,842/31,849) | 95,685 | VALID (0/2) |
| racbasicsampleproject.rvt | 2024 | 13 | 12/12 | 1164/1164 | 307 | 1156(0) | 470,502/4,492 | OK | 100.00% (85,538/85,538) | 257,106 | VALID (0/1) |
| rmebasicsampleproject.rvt | 2024 | 13 | 12/12 | 2052/2052 | 503 | 2044(0) | 470,502/4,492 | OK | 99.18% (141,497/142,668) | 425,409 | VALID (0/2) |
| rstadvancedsampleproject.rvt | 2024 | 13 | 12/12 | 1018/1018 | 235 | 1010(0) | 470,502/4,492 | OK | 100.00% (64,669/64,669) | 194,550 | VALID (0/1) |
| racadvancedsampleproject.rvt | 2024 | 13 | 12/12 | 1006/1006 | 267 | 998(0) | 470,502/4,492 | OK | 100.00% (59,221/59,221) | 178,029 | VALID (0/1) |
| rmeadvancedsampleproject.rvt | 2024 | 13 | 12/12 | 2585/2585 | 603 | 2577(0) | 470,502/4,492 | OK | 99.41% (188,869/189,985) | 567,888 | VALID (0/2) |
| 2024_Core_Interior.rvt (3rd-party) | 2024 | 20 | 12/12 | 1652/1652 | 525 | 1644(0) | 470,502/4,492 | OK | 99.99% (49,172/49,177) | 152,184 | INVALID (9/9) |
| racbasicsamplefamily-2025.rfa | 2025 | 13 | 11/12 | 18/18 | 13 | 10(0) | 484,585/4,600 | OK | 100.00% (1,984/1,984) | 5,955 | INVALID (5/1) |
| racbasicsamplefamily-2024.rfa | 2024 | 13 | 12/12 | 18/18 | 13 | 10(0) | 470,502/4,492 | OK | 100.00% (1,975/1,975) | 5,928 | INVALID (5/1) |

**PARITY: every Autodesk 2025/2024 sample project reads VALID with the
same per-discipline decode percentages as the 2026 baseline** (rst 99.98 %,
rac 100 %, rme 99.18/99.41 %) — the only decode failures are the SAME
pre-existing Extensible-Storage blob gaps 2026 has.  100 % gzip CRC, 0
walker errors, every ECC page verifies, schema parses to EOF, validator
VALID — 12/12 sample projects across both new releases.

The three non-VALID rows are **not release deltas** (decode/framing clean on
all three): the third-party magnetar model is a WORKSHARED file whose
consistency-layer counts (partition-header elem_table_count vs ElemTable;
unit-0 ids vs ElemTable) the validator does not yet model — and the two
.rfa rows are file-KIND expectation gaps (families genuinely lack
`ProjectInformation`; the `PartAtom` XML tail block is not CRCIO-framed —
also true of family files generally).  Both are validator follow-ups for
the read-stack stream, noted here, out of this stream's territory.

## 3. THE FINDING — what actually differs between releases

1. **The schema-stream GRAMMAR did NOT change.**  `rvt.schema.parse`
   (written against 2026) reads the 2024 and 2025 `Formats/Latest` to EOF,
   unmodified: zero parse errors, zero unresolved refs.  **There are NO
   schema-parser deltas** — `schema_2025.py` / `schema_2024.py` therefore
   WRAP `rvt.schema.parse` (never fork it) and pin each release's schema
   constant, with an explicit empty `PARSER_DELTAS` tuple as the checkable
   answer to "where are the parser deltas?".
2. **Per-release schema constants** (byte-identical in every file of a
   release, verified across all six samples + the sample-family .rfa, and
   for 2024 also the unrelated third-party model):
   * 2026: 496,597 B, 4,690 classes, sha256 `6459a9a9…`
   * 2025: 484,585 B, 4,600 classes, sha256 `c964f9aa…`
   * 2024: 470,502 B, 4,492 classes, sha256 `0bfb947b…`
3. **What broke reading was six "magic tags" in `rvt.partitions` that are
   actually CLASS ORDINALS** — per-release type ids of stable-NAMED classes.
   Classes are inserted mid-order between releases, so every ordinal drifts:

   | partitions constant | schema class | 2024 | 2025 | 2026 |
   |---|---|---|---|---|
   | BLOCK_TAG | SegmentMarker | 0x0e7c | 0x0ed9 | 0x0f28 |
   | TRAILER_TAG | SegmentCheckback | 0x0e75 | 0x0ed2 | 0x0f21 |
   | FOOTER_TAG | SignatureMarker | 0x0e8f | 0x0eee | 0x0f3f |
   | CONTAINER_CLASS | ContentMarker | 0x037b | 0x0391 | 0x03a3 |
   | UNIT_INNER_CLASS | ContentKey | 0x037a | 0x0390 | 0x03a2 |
   | PT_CLASS | PartitionTable | 0x0bec | 0x0c40 | 0x0c80 |

   Fixed-offset arithmetic is WRONG (even "low" ordinals move: XYZ 172→88,
   UV 1861→239 between 2024 and 2025); the only correct model resolves
   ordinals BY NAME from the file's own schema.
4. **The document-machinery layer is field-identical 2026→2025** (ADocument,
   ElemTable/ElemRec/GraveyardRec, DocumentHistory, DocumentIncrementTable,
   DocumentStorageIndexImpl, PartitionTable, ESSchemaStorage, Element,
   Symbol, ElementHeader, GElement, SerializedDummy, the framing classes) —
   so the ADocument codec, four-registry law, re-blocker and record
   encoders port to 2025 with zero field-map work.  2024 adds:
   ESSchemaStorage + FamilySymbol layout deltas, ElementHeader v25→24 and
   FamilyInstance v39→37 version-only stamps.

## 4. THE VERSION MODEL — `src/rvt/versions/` (new package, my territory)

* `__init__.py` — `Release` records + `KNOWN_RELEASES` {2024, 2025, 2026}
  (schema pins, sample builds, framing ordinals, anchor ordinals, samples
  dir, creation certification);
  `detect_release` (BasicFileInfo `Format` year first — release-authoritative,
  unframed, layout-stable — then the schema signature);
  `ordinals_from_schema` / `framing_for` (BY-NAME resolution, the authority;
  precomputed tables are a cross-checked cache — a mismatch raises);
  `reading(...)` context manager — binds a file's ordinals into
  `rvt.partitions` (module globals looked up at call time; `TERMINATOR`
  recomputed; the `\x28\x0f` resync search replaced by a version-aware one),
  restores on exit, nests safely, cannot leak into the 2026 creation path;
  **the guards**: `require_creation_release` (refuses any target without a
  certified genesis base — today that is everything but 2026 — so no
  creation path can silently emit 2026 for a 2025 target),
  `require_release` (no release mixing inside one build),
  `check_openable(file_release, users_revit)` (refuses handing a user a
  file newer than their Revit — the exact problem-(C) trap),
  `creation_status` (honest per-target report), `describe`, CLI
  (`python -m rvt.versions <file>` via new `__main__.py`).
* `_release_schema.py` — shared per-release schema-handle machinery
  (pinned-signature verification, quarantined-sample discovery).
* `schema_2025.py` / `schema_2024.py` — the per-release handles: pins,
  `PARSER_DELTAS = ()` (the documented no-fork answer), `load()`/`verify()`.
* `parity.py` — the §2 harness (`--json` / `--md`; exit 1 on any bad row).

Nothing outside `src/rvt/versions/`, `tests/test_versions.py`,
`samples/2024|2025/`, `docs/writer/genesis-2025-plan.md` and this record was
edited.  `rvt.partitions` / `rvt.schema` / genesis are untouched — the model
wraps them (per charter).

## 5. THE 2025 GENESIS PLAN — `docs/writer/genesis-2025-plan.md`

The mechanized re-run of the certified lineage on
`samples/2025/rstbasicsampleproject.rvt`: harvest+measure the 2025 format
corpora → reduction ladder → family-free K4-2025 → retarget constructors →
substitution Y-rungs → compose `G_ABPD_2025` → certify, register in
`rvt.frontdoor.base`, flip `creation_certified`.  Certification discipline
carried over: the base itself viewer-certified before building on it, ≥1
certified control per upload round.

Constructor portability (class-by-class schema diff of all **208 classes
`rvt.genesis` constructs**, method + full tables in the plan):
**185/208 (89 %) port AS-IS** (identical fields, chain layout and class
versions — only ordinals differ, resolved by name); **17 LAYOUT-DELTA**
(the big ones: the wire family — 2025 keeps wire-sizing settings on
`RbsWireSettingsElem` and a STRING max-conductor-size on `RbsWireType`;
`NumberingSchema` reworked; `GeomStep` base renamed `m_oExtraDatas`→
`m_oExtraData` affecting 5 GStep constructors; the rest are 1-2 field
drops/renames); **6 MISSING in 2025** (the 2026-invented conductor catalog:
`CustomElement`, `NamingCell`, 4 `RbsConductor*` cells — their 2025
representation is the string field, so the 4 conductor constructors are
2026-only).  The retarget mechanism is one schema injection into
`rvt.genesis.types._S()` because skeleton+encode are already schema-directed
by name (sketch in plan §4).

## 6. TESTS + SUITE

* **`tests/test_versions.py` — 34 tests, all passing** (~1.2 s): release-table
  invariants; ordinal drift asserted; guards (incl. the problem-(C) trap);
  schema pins + `PARSER_DELTAS == ()`; by-name ordinals == tables for all
  three releases; `reading()` activation/nesting/restoration (incl. on
  exception); bounded read-parity probes (block walk + 400-record
  schema-directed decode ≥95 % clean) for 2024/2025/2026; a NEGATIVE control
  (the same 2025 bytes refuse to frame under 2026 ordinals — the model is
  load-bearing, not decorative); quarantine discipline (SOURCES.md complete,
  no sample binaries under `plugin/`).  Sample-backed tests skip cleanly off
  the dev machine.
* **Full suite** (`.venv/bin/python -m pytest -q --continue-on-collection-errors`):
  RUN IN PROGRESS at the time of this line — final counts are appended in
  the SUITE RESULT block just above BRANCH STATE.  One outcome is already
  known and pre-existing: `tests/test_engine.py` fails COLLECTION — it
  still points at `skills/revit-bridge/scripts`, renamed to
  `skills/tekton-ifc/scripts` (a rename regression that predates this
  stream; the module cache even shows the old `rev-revit` path).  Exact
  fix in §7.3.
* **Plugin sync**: `src/rvt/versions/` is inside the sync allow-list mirror
  of `src/rvt`, so the module ships in the plugin automatically once
  `tools/sync_plugin.py` (the mandated mechanism) runs.  It ran during this
  session — outside this stream (orchestrator/packaging side) — and this
  stream VERIFIED the end state: `--check` exit 0, deny-audit clean,
  `samples/` excluded (three ways, §1), mirror + `tekton-plugin.zip`
  carrying the versions module.  Details in the SUITE RESULT block.

## 7. PROPOSED PATCHES (other territories — exact diffs, not applied)

### 7.1 Wire the guard into the front door (`tools/frontdoor.py`)

The guards exist but nothing calls them yet.  Add a target-release flag and
refuse early — one flag + two lines at the head of the author route:

```diff
     pol.add_argument("--base", default=None, metavar="FILE.rvt", ...)
+    pol.add_argument("--target-release", type=int, default=2026,
+                     metavar="YEAR",
+                     help="Revit release the OUTPUT must open in (the user's "
+                          "Revit year). Refused unless a certified genesis "
+                          "base exists for that release; never silently "
+                          "answered with a newer file. [default 2026]")
```
and where the build starts (before any base is opened):
```python
from rvt import versions
rel = versions.require_creation_release(args.target_release)   # UnsupportedTarget for 2025/2024 today
base_path = args.base or <pinned>
versions.require_release(versions.detect_release(base_path), rel.year, what="genesis base")
```
The `--rvt` edit route keeps the INPUT's release (read/edit is
version-agnostic) but should stamp the manifest with
`versions.describe(input)["release"]` and call
`versions.check_openable(out_release, args.target_release)` before handing
over the file.  Per the deliverable rule: this guard REFUSES with one clear
line naming the single missing input (the certified 2025 base) — it is a
genuine-impossibility report, never a silent IFC substitution.

### 7.2 Genesis constructor retarget (`src/rvt/genesis/types.py`)

Schema injection for `_S()` — sketch in `docs/writer/genesis-2025-plan.md`
§4 (phase B, G25-3).

### 7.3 Rename regression fix (`tests/test_engine.py`, line 31)

```diff
-SCRIPTS = os.path.join(ROOT, "skills", "revit-bridge", "scripts")
+SCRIPTS = os.path.join(ROOT, "skills", "tekton-ifc", "scripts")
```
(This is the only module keeping the full suite from collecting clean; it
predates this stream and `skills/tekton-ifc/scripts/bridge_lib.py` exists.)

### 7.4 Validator follow-ups (read-stack stream)

.rfa kind-awareness (`ProjectInformation` not expected; `PartAtom` XML tail
exempt from CRCIO framing) and workshared-file consistency modelling
(partition-header elem_table_count vs central ElemTable) — the three
non-VALID §2 rows, none release-related.

## Open questions carried forward

* Does the Autodesk viewer accept 2025 uploads?  (G25-1 round 1 control
  answers it; blocks nothing now.)
* The 2025 `Global/Latest` unit/spec corpus + `ESSchemaStorage` pins
  (campaign step G25-0; counsel C4 applies per release).
* TRACKER "Open questions" first bullet (which Revit the brothers run) is
  ANSWERED by the charter: **2025** — and the "need one small file from that
  version" want is now satisfied by six full samples + a pinned schema.

---

## SUITE RESULT (final, 2026-08-04 19:49)

`.venv/bin/python -m pytest -q --continue-on-collection-errors` from repo
root: **1,284 passed, 4 failed, 5 skipped, 1 collection error — 31:45 wall.**

All five defects are PRE-EXISTING and in other streams' territories; none
involves `rvt.versions` (verified: the ONLY file in the repo importing
`rvt.versions` is `tests/test_versions.py` — this stream is purely
additive):

1. `tests/test_engine.py` — COLLECTION ERROR: imports from
   `skills/revit-bridge/scripts` (renamed to `skills/tekton-ifc/scripts`).
   Rename fallout; one-line fix in §7.3.
2. `tests/test_electrical.py::test_committed_room_schedules_exist` —
   expects kind `rev-revit.electrical-summary`, source now emits
   `tekton.electrical-summary` (rename sweep half-applied; RENAME.md says
   don't rename piecemeal — this pair drifted).
3. `tests/test_genesis_types.py::test_no_cloned_payload_source` — line 25
   bakes `ROOT = "/Users/ck/dev/things/rev-revit"` (the RENAME.md Step-0
   baked-absolute-path class; the folder is now `tekton`).
4. + 5. `tests/test_provenance.py::test_G0_resource_refs_are_counted` /
   `::test_G0_identity_dit_usernames_still_leak` — G0-era expectations
   (asset-library-fbx pattern present; DIT username still leaking) no
   longer match what `rvt.provenance` reports on the unchanged Aug-3
   `G0.rvt`; expectation drift for the provenance stream to refresh.

`tests/test_versions.py`: **34/34 green** (in-suite and standalone).

**Plugin sync state (verified after the suite):**
`tools/sync_plugin.py --check` → **"plugin in sync with source (deny-audit
clean, assets verified)", exit 0.**  The `plugin/lib/src/rvt/versions/`
mirror now carries all six module files and `tekton-plugin.zip` was
rebuilt (19:38) — the sync itself was executed during this session's suite
window by the sync tool outside this stream (the orchestrator/packaging
side; no test performs a wholesale sync).  Independently re-asserted:
deny-audit clean, `samples/` absent from the plugin tree, the only bundled
.rvt binaries are our own genesis base + authored examples
(`tests/test_plugin_sync.py` 7/7 green in the same run).

## BRANCH STATE

* Repo: `/Users/ck/dev/things/tekton`, no branch work — the repo has a git
  dir but NO commits yet (nothing was committed by this stream; integration
  is the orchestrator's).
* NEW (this stream's territory):
  * `samples/2025/{6 .rvt}` + `SOURCES.md`, `samples/2024/{6 .rvt}` +
    `SOURCES.md` (DEV-ONLY quarantine, hashes verified)
  * `src/rvt/versions/{__init__.py, __main__.py, _release_schema.py,
    schema_2025.py, schema_2024.py, parity.py}`
  * `tests/test_versions.py` (34 tests, green)
  * `docs/writer/genesis-2025-plan.md`
  * this record
* Touched OUTSIDE source territory: NOTHING.  No existing `src/rvt/*.py`,
  tools or tests edited; the plugin mirror pickup of `src/rvt/versions/`
  happened via `tools/sync_plugin.py` run outside this stream (see SUITE
  RESULT), and this stream only VERIFIED the result (`--check` exit 0,
  deny-audit clean).
* Suite: see the SUITE RESULT block above.  `tests/test_versions.py` 34/34.
* DONE check: 2025 AND 2024 read at decode parity (no parser deltas — the
  checkable claim `PARSER_DELTAS == ()`); version model + guards live and
  tested; genesis-2025 plan with the 208-class constructor portability
  table delivered.  STOP at READY: no 2025 campaign rungs were run.
