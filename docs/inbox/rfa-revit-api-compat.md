# rfa-revit-api-compat — fresh-clone integrity sweep + bare-surface RFA fix

Charter (session task): diagnose every error a fresh clone / cloud session
hits, fix them, and verify the RFA generation path produces files shaped
for Autodesk's readers.  Branch: `claude/rfa-revit-api-compat-izqaum`.

## What was found and fixed

### 1. Product bugs (engine / tools)

* **`rvt.validate.ecc_verify_stream` hard-required numpy** — on a bare
  zero-pip surface (unzipped plugin + system python) the structure layer
  raised `ImportError`, the loader's `verify_written` treated that as a
  file failure, and **every `go author` job ended `FAILED (no family could
  be loaded)`, exit 3, withholding the combined `.rvt`** — a deliverable-rule
  violation.  Fix: without numpy the stream is unframed with the
  pure-python `ecc.unframe_stream` and ONE warning per report says the ECC
  pages went unverified (environment gap, not file defect); every other
  structure check still runs.  Bare-surface `go author` now: exit 0,
  6/6 families loaded, combined `.rvt` delivered.  (The WRITE path was
  never affected — `ecc.frame_stream` is pure python.)
* **`rvt.schema.load_schema` default path only knew the research corpus**
  (`extracted/`, git-ignored) — `ObjectDecoder()` no-arg died on any clone
  without it, killing `make_family.py`, the router's `prompt->rfa` /
  `spec->rfa` routes, and residue-constructor tests.  Fix: the default-path
  call falls back to the sha-pinned bundled base's embedded
  `Formats/Latest` (`frontdoor.standalone.bundled_schema`), mirroring the
  plugin's lazy fallback.  Explicit paths are honoured verbatim.
* **`frontdoor.standalone.bundled_base_path` and
  `frontdoor.base.GenesisPin.candidate_paths` never tried the repo's own
  `plugin/assets/genesis/`** (the tracked, pinned copies) — a fresh clone
  could not resolve G_ABPD / G_ABPD_2025 / G_ABPD_2024 although they sit in
  git.  Fix: one candidate added in each (still sha-verified against the
  pin).  `--target-version 2025/2024` authoring now works from a fresh
  clone.  NOTE: `frontdoor/base.py` is a hot file — the edit is 2 lines +
  comment; flagging here per the hot-file rule.
* **`versions._release_schema.load_release_schema` required a quarantined
  sample** to load the 2024/2025 schemas even though the plugin bundles
  parsed-schema caches keyed by the pinned sha256
  (`assets/schema_cache/<sha>.tksc`).  Fix: on a machine with no sample it
  reconstructs from the cache and still runs `verify_schema` against the
  pin.  port2024/port2025 adapters now fully exercised on a fresh clone.
* **`tools/make_family.py` never armed the standalone resolvers** — direct
  CLI RFA generation crashed without the corpus.  Fix: `_ensure_standalone()`
  activates `frontdoor.standalone.activate()` only when the corpus is
  absent (owner machine byte-for-bit unchanged).
* **`plugin/scripts/validate_plugin.py` demanded a SKILL.md from
  `skills/_shared`** (the bootstrap helper dir, not a skill) — the
  validator failed on every checkout.  Fix: underscore-prefixed helper
  dirs are skipped.

### 2. Test-suite integrity (fresh clone was 213 failed / 65 errors → 0 / 0)

* `tests/test_residue_b.py` built constructor records at COLLECTION time —
  a fresh clone aborted collection of the ENTIRE suite.  Records are now
  built lazily; the schema fallback seeds only the `genesis.types`
  singleton (never the process-wide chokepoints, which defeated other
  modules' corpus guards for the rest of the run — measured, not guessed:
  the first attempt used `install_schema()` and flipped test_port2024 from
  skip to fail order-dependently).
* `tests/conftest.py` gained a `pytest_runtest_makereport` hook: a
  `FileNotFoundError` under `samples/`, `extracted/`, `vendor/` or
  `experiments/` becomes a skip named after the missing path.  Tests that
  BUILD under experiments fail at build time with their own error, so a
  genuine failure cannot be masked by this.
* The "manifest tracked in git, `.rvt` binaries git-ignored" pattern (the
  batch-37 famdoc ladders, staged batches, Y-ladders, probe manifests)
  failed `assert os.path.isfile` on 13 more files.  Uniform guard applied:
  skip when NONE of the referenced binaries exist on this machine, full
  md5/existence checks when any do.  Files: test_famdoc_{blobs,final,bisect},
  test_port2025, test_genesis_{2024,2025,settings}, test_identity,
  test_render_wallgeom, test_residual, test_residue_{a2,c}, test_rft_probe,
  test_species, test_subtractive, test_terminal_diff, test_union_reconcile,
  test_router (evidence self-audit skips only when EVERY problem is a
  missing experiments/ binary and none exist here), test_coverage,
  test_engine, test_families.
* `tests/test_roundtrip.py`: the optional `compoundfiles` cross-check
  reader now skips (not fails) when the package is absent; the strict
  olefile assertions still gate the CFB writer everywhere.
* `tests/test_rft_probe.py` poll tests now monkeypatch `VENDOR_RFA` — they
  asserted the owner machine's vendor file into the expected shape.

### 3. Regenerated (deterministic, by the now-running tests)

* `experiments/genesis2024/miners/portability-2024.json` and
  `experiments/genesis2025/subst/portability-2025.json`: the frozen
  portability tables were stale — they predate `y2024_b.py`'s call sites.
  `portability_table(write=True)` refreshed them; additions are call-site
  rows only.

## Evidence (numbers, not adjectives)

* Full suite, fresh clone, `RVT_SKIP_LARGE=1`: **before** 213 failed /
  1021 passed / 817 skipped / 65 errors (and one run aborted at
  collection); **after** 0 failed / **1042 passed** / 1074 skipped /
  0 errors (~2 min).
* `make_family.py panelboard|transformer|luminaire`: emitted, verify ok
  (crc_fail=0, ecc_mismatch=0, decode 41/41), validator **VALID 0 errors /
  0 warnings** (family mode), provenance **all 11 checks ok** (zero donor
  bytes, identity ours, 64-byte 0x0f3f footer present-and-ours).
* `frontdoor author --prompt "an electrical room with 6 panels"`:
  ok, 6 `.rfa` built + loaded, combined `prompt_room.rvt` validator
  0 errors; same with `--target-version 2025`.
* Bare surface (unzip `tekton-plugin.zip`, system python3 WITHOUT numpy):
  `_bootstrap.py go author ...` → `READY`, exit 0, 6/6 loaded, combined
  delivered (was exit 3, 0/6, no combined).
* Independent reader (revit-skill `rvt_read.py`, separate implementation):
  parses the generated `.rfa` — version 2026, correct streams, author
  `rvt-writer`; PartAtom XML carries category + type (that reader's
  category heuristic expects Autodesk's scheme attr; not a file defect).
* Gates: `sync_plugin.py --check` clean; `validate_plugin.py` 23/23 PASS;
  `check_portable_paths.py` 2609 ok.

## Open questions / follow-ups (proposed, not claimed)

* The viewer-certification arbiter still applies: nothing here changes the
  open instance-audit cell (#31–#48).  The bare-surface numpy degradation
  means a bare machine cannot itself ECC-verify — `doctor --install numpy`
  remains the full-verification path; consider surfacing the warning in
  the `go` result's honesty block explicitly.
* `plugin/lib/tools/make_family.py` mirror not shipped in skills' scripts;
  if a skill later shells to it, it inherits `_ensure_standalone()`.

## Iteration 2 — analysis tooling (same branch)

* **`rvt_validate --family` LANDED** — the request recorded in
  `famdoc_adoc.validate_family_file` ("the 6-line diff that would make it a
  certified `rvt_validate --family` mode").  `rvt.validate.Validator` now
  takes `family=` (instance-scoped stream sets, no global mutation): PartAtom
  unframed, ProjectInformation not required; everything else identical.  The
  CLI auto-enables it for `.rfa`/`.rft` (`--project` forces it off);
  `skeleton.validate_family` now calls the parameter instead of patching
  module globals.  Generated `.rfa`: family mode 0 errors; forced project
  mode still shows exactly the two family-shape calibration findings.
* **`tools/rvt_analyze.py` NEW** — one-shot analysis report (text + JSON)
  for any `.rvt`/`.rfa`/`.rft`: identity (BFI, release, ours?), the file's
  own schema signature, stream inventory, element-class census + the
  coherence tuple + family documents (via `rvt.census`), layered validation
  in the right mode, optional famgen provenance scan.  Read-only; works
  from a fresh clone.
* Tests: `tests/test_rvt_analyze.py` (5 tests, all runnable on a fresh
  clone: bundled base + factory-generated family).  Full suite after:
  1047 passed / 0 failed / 0 errors.

### Autodesk-account question (asked by the owner this session)

No Autodesk account is needed for anything the engine, the plugin, or this
analysis tooling does — that independence is the product.  The ONE place an
Autodesk login matters is **viewer certification** (hard rule 4): a human
with viewer.autodesk.com access uploads staged batches
(`tools/probe_batch.py stage` → `tools/serve_acceptance.py`) and records
verdicts in the ledger.  I can STAGE batches from a session but must stop at
READY — the upload is the orchestrating human's step.  APS / Design
Automation stays off the table (decided twice; hard rule 7).

## Iteration 3 — issue #52: the desktop-Revit crash, root-caused and fixed

**The first desktop-Revit verdict on the bare-.rfa surface** (owner, Revit
2026): File>Open AND Insert>Load Family both terminate with the generic
unrecoverable-error dialog.  The journal names it: `Cannot get
AutoCamSettingsElem from the ADoccument!` (DBG_WARN), then **`Assertion
failed: EditModeMgr.cpp:333`** on view activation → 0xe06d7363 →
termination.

**Root cause (measured):** the crashed `.rfa`'s host ADocument populated
AppInfo slot set was IDENTICAL to the bundled PROJECT base's — 241 slots,
180 populated, exact set match.  `standalone_family_write` passes the
bundled genesis base (a project) as `emit_family_rfa_v2`'s ADocument
archetype donor; `family_template_tree` faithfully templated a
project-shaped registry set into a family container.  The family editor
reads project furniture where family-editor state belongs and asserts.
Dev builds never showed it (default donor = the Revit-born vendor `.rfa`);
certification never caught it (every certified family win is a
load-into-project where OUR loader authors the embedded famdoc — the
`.rfa`'s own host ADocument is only read on desktop open/load).

**Fix (Track A):** `emit_family_rfa_v2` now discriminates the donor
(`container_is_family`: PartAtom stream).  A project donor no longer
templates the ADocument; instead `constructive_family_host_tree` builds
the famdoc tree from the SCHEMA ALONE — the verified
`factory.author_embedded_adocument` construction (the L1a-certified
lineage: 239-slot all-null AppInfoManager) lifted to host form (inline
ElemTable/History dropped; authorship set by the normal step 5).  The
existing purge/repopulate/gates pipeline runs unchanged over it.
Measured on the emitted candidate: 239 slots / 0 populated, host tables
None, owner family ours, product build stamp, ADocument payload 1,333 B
(was ~78 KB of project registries), decodes clean, round-trips, all
instruments green.  Family-container donors (dev machine,
$RVT_FAMILY_DONOR) keep the archetype path byte-for-byte.

**Fix (Track B, honesty):** `standalone_family_write` reports now carry
`adocument_archetype` + an explicit `caveats` entry when the constructive
path is used; the skill preflight says the same out loud.  Deliverable
rule kept: always deliver, caveat spoken.

**Evidence:** famgen/famdoc/frontdoor/analyze suites 108 passed; bare
unzip + system python `go author` exit 0 with famdoc-shaped (239/0)
ADocuments in the emitted `.rfa`s; full suite 1067 passed / 0 failed.
**Desktop acceptance of the all-null-registry shape is the open
verification** — the owner re-tests in Revit 2026 (minutes, journal on
failure); issue #52 stays open until that verdict.

## Iteration 4 — desktop round 2: the archive-numbering law

Round-2 desktop verdict on the constructive candidate (owner, Revit 2026):
**no more termination** — a clean, SPECIFIC refusal:
`TaskDialog_Bad_Load_Reference` / `CArchiveException code=119: unresolved
pointer references` / `ModelState: CorruptElemStream`.

**Measured cause:** in a HOST ``Global/Latest`` stream the ADocument is
archive object 1 and every self-reference points there — the
load-surviving file carries **196/196 weakrefs == 1**.  The constructive
tree had kept the EMBEDDED form's numbering (self = object 2, host = 1):
12 pointers at a nonexistent object → "many unresolved pointer
references".  Fix: ``constructive_family_host_tree`` renumbers every
weakref to 1.  Candidate B: 13/13 weakrefs == 1, famdoc shape kept
(239/0 slots), all instruments green.

Law for KNOWLEDGE.md once #52 closes: **the ADocument archive-object
numbering is CONTEXT-DEPENDENT** — host Latest stream: self = 1;
embedded ContentDocuments entry: host = 1, self = 2.  A tree lifted from
one context into the other must be renumbered; our instruments cannot
catch it (the pointers decode fine — they just point at an object the
TARGET context does not carry).  Desktop Revit's load-time reference
check is the only oracle, and its dialog names it.

## BRANCH STATE

* Branch `claude/rfa-revit-api-compat-izqaum`; all work committed and
  pushed; no PR opened (not requested).
* Files written: `src/rvt/{schema.py,validate.py}`,
  `src/rvt/frontdoor/{base.py,standalone.py}`,
  `src/rvt/versions/_release_schema.py`, `tools/make_family.py`,
  `plugin/scripts/validate_plugin.py`, `plugin/lib/**` (sync mirror),
  `tests/conftest.py` + 24 test files (guards only),
  2 regenerated portability JSONs, this record.
* Gates at close: full suite 1042/0/0; sync --check clean; plugin
  validator PASS; portable paths ok.  Hot-file touches:
  `src/rvt/frontdoor/base.py` (2-line candidate add) — needs owner eyes.
* Nothing staged for viewer rounds; no certification claims made.

## Iteration 5 — the desktop bisect campaign distilled into famgen (issue #52)

Ten owner-driven desktop rounds (journals + minidumps on #52) turned into
shipped famgen law:

* **`skeleton.new_required_settings`** — every family document now carries
  the four singletons desktop Revit demands: `DefaultDivideSettings` +
  `DrawOrder3dElem` (the repair-dialog pair), `AutoCamSettingsElem` (the
  standing DBG_WARN), `PenWidthTableElem` (OUR ISO-128 series; its absence
  was the `PenWidthTableGetter.cpp:62` draw assert).  Desktop-verified on
  candidate E: no repair prompt, no pen assert, family opens with live
  category/parameters.
* **`famdoc_adoc` registry wiring** — `UniqueElementsTracking` [10]/[60]/
  [85] and `PenWidthTableInfo.m_penWidthTableElemId` re-pointed at OUR
  elements after the purge (indices measured on the owner's Revit-born
  donor; fires on populated-registry trees, no-ops on the constructive
  all-null tree).
* **RefPlane `m_cutVec` = the plane NORMAL** (donor law: every Revit-born
  plane carries [0,0,1]; the old x-cross-normal put an in-plane vector).
* **Element headers carry NO `m_pBBox`** on curves/sketch (donor law;
  ours were zero-thickness Outlines — the `BoundedSpace` warning's shape).
* Tests: `tests/test_required_settings.py` (6, fresh-clone runnable).

**Corrected misread (recorded so nobody repeats it):** curve rep GInfo
`m_categoryId` is a MEMBER GStyleElem ELEMENT id (the T2a self-contained-
binds law), NOT a category constant — donor's "164" is its own style row.
Reverted; `walked_bind_census` now guards it in the new tests.

**THE OPEN LEAD for the click-crash:** the donor famdoc carries 1,499
`GStyleElem` rows (plus CategoryElem/FontElem etc. — the whole style
subsystem); our lean famdoc carries ZERO.  Style resolution during click
hit-testing has nothing to walk.  Next candidate: author minimal
in-document GStyleElem rows for the categories the famdoc uses and bind
curve/solid reps to them in-unit (the binds law already viewer-certified
in-unit binds).  Probe K (all drawables stripped) is with the owner as the
bisection splitter.

Suite: 1625 passed / 1 failed — `test_cli_flag_parses_2024`, PRE-EXISTING
on clean origin/main (verified in a pristine worktree), not this branch's.

## BRANCH STATE (iteration 5)

Branch `claude/issue-52-family-required-settings` (from main a5a853f).
Files: famgen/{skeleton,geometry,factory,famdoc_adoc}.py,
tests/test_required_settings.py, this record, plugin mirror (sync clean).
Gates: settings+selfcontained+famgen+analyze suites green; full suite
1625/1/0 (the 1 = upstream); sync_plugin --check clean; validate_plugin
PASS.  Desktop evidence chain: issue #52 comments (rounds 1–10).

## Iteration 6 — the FAMILY-VIEWER LAW (round 13; issue #333)

Rounds 11–12 (probes K/K2: ALL drawables stripped, still crashed on the
first canvas click) proved the fault lives in the view furniture, and the
round-12 diff blamed `Viewer.m_boundedSpace`'s basis.  **Round 13
correction: that diff compared a mismatched pair** — OUR project viewer
against the DONOR's plan viewer.  Measured properly (donor viewers 22/26 =
plan, 49 = project vs ours 1010/1005):

* The basis frames are EXONERATED — the donor keeps the project skeleton's
  per-view-type frames (plan frame on plan viewers, elevation frame on the
  project viewer), numerically identical to ours.
* Every donor viewer's `m_boundOffset[2]` is `(100.0, 0.0)` — the z
  interval sits on the reference level.  Ours: `(100,-100)` on the project
  viewer, `(1000, 0.1)` on the plan viewer.
* The donor's PLAN viewers match the project viewer's SHAPE: bounds
  inactive (`m_boundActive` all False; ours True on x/y), crop ON
  (`m_isOn` True; ours False), ortho (`m_projMethodType` 1; ours 2),
  `m_viewerFlags` 0 (ours 7), `m_intentionallyPlaced` False (ours True).
  Every crash journal warns `BoundedSpace.cpp:86`.

**Consequence for probes L1/L2** (delivered before the correction): their
patch forces the PROJECT viewer into a plan frame — donor-contradicted, so
their verdicts are non-conclusive on the BoundedSpace hypothesis.
Superseded by probe M.

**Landed:** `_apply_family_viewer_law` in `famgen/skeleton.py`
(family-doc override only; the project skeleton's `[VERIFIED vs rstbasic]`
values are untouched), guarded by `test_family_viewer_bound_law`.
**Probe M** (`probe_m_viewerlaw.rfa`, full panelboard, ONE composite
variable = the viewer law) is with the owner; control = `main_smoke.rfa`
(same engine, law absent).  Validator VALID 0 errors, provenance ok on
both.

## BRANCH STATE (iteration 6)

Branch `claude/333-family-viewer-law` (from main efcf81c).
Files: src/rvt/famgen/skeleton.py (`_apply_family_viewer_law`),
tests/test_required_settings.py (+1 test), this record, plugin mirror.
Gates: required_settings+famgen_skeleton+famgen_factory+selfcontained →
79 passed / 17 skipped; sync_plugin run (zip rebuilt) + validate_plugin
PASS; probe M validator VALID 0 errors + provenance ok.  Awaiting the
owner's desktop verdict on probe M (File > Open + canvas click).

## Iteration 7 — viewer law CONVICTED; the DIMENSION-STYLE LAW (rounds 14-15)

**Round 14 void:** probe M was an instrument error (plain `prod.write()` →
252-byte host-ADocument stub → `Failed to load elemStream#0` on both open
paths).  Voided; corrected pair M2 (law) / M0 (control) built via
`standalone_family_write`, both host ADocument 65,249 B.

**Round 15 verdicts (journals 0024/0025) — the cleanest pair yet:**
* **M0 (control):** BoundedSpace + safeSqrt warnings present; middle-mouse
  pan → 0xc0000005 in ViewManipEditor (same as L1/L2).
* **M2 (viewer law):** ZERO BoundedSpace/safeSqrt warnings — first time in
  the campaign; zoom + first click fine; **the viewer law is convicted and
  fixed** (PR #336 now carries desktop evidence).  New, LATER failure:
  selecting the panel body → `DBG_WARN: Where is the DimensionStyle?
  (LinearDimStringState.cpp:106)` then `LinearDimString.cpp:331` assert,
  0xe06d7363 — temporary dimensions can't resolve a default style.

**The dimension-style law (measured on the donor's EMBEDDED famdoc, unit 1
ids 2642-2652 + its inline ADocument):** the default linear DimensionStyle
is registered in `SymbolIdMgr.m_defElementTypeMap` under key 10; the style's
constellation is DimensionStyle + LeaderStyle ("Diagonal" arrowhead) + 4
anonymous CategoryElems (parent -2000059, type 4; leader/text/tick/
centerline) each owning ONE GStyleElem line style + FontElem (Arial 3/32").
Our M2 file's map had 0 entries and no style elements — the literal state
of the warning.  (This is also the first authored slice of the in-document
style subsystem — the standing GStyleElem lead.)

**Landed:** `new_dimension_style_constellation` in `famgen/skeleton.py`
(11 schema-built elements, donor-measured constants only) + famdoc_adoc
step 4c registering key 10.  **Probe N** (`probe_n_dimstyle.rfa`, = M2 +
this law) with the owner; validator VALID 0 errors; famgen suites 87
passed / 28 skipped.  Donor structure note for the record: the donor .rfa
is TWO units (unit 0 = the 2,054-element host/editor doc, unit 1 = the
224-element embedded famdoc — the true minimal family inventory) + a
ContentDocuments inline ADocument; our flat single-unit shape has no
ContentDocuments row (accepted by load-into-project so far).

## Iteration 8 — dimension-style law HOLDS; the FAMILY-UNITS LAW (round 16)

**Round 16 verdict (journal 0026, probe N):** open, zoom, SELECT the panel
body, middle-mouse PAN — all clean, zero warnings (the dimension-style law
holds).  New crash: the Family Types ribbon button (`ID_FAMILY_TYPE`) →
`ADialog::doModal start` → immediate 0xe06d7363, no DBG_WARN.

**Diagnosis (instrumented, no desktop round needed):** the dialog formats
every parameter value through `UnitsElem.m_units.m_formatOptionsMap`.
Donor famdoc: **136** spec entries.  Ours: **8**, and with MISMATCHED spec
versions — the table spoke `current-2.0.0`/`potential-2.0.0` while our
ParamElemFamily defs declare `-1.0.0` specs.  First electrical lookup
missed → throw at doModal.

**Landed:** `src/rvt/famgen/assets/family_units.json` (the donor-measured
136-spec table; pure unit configuration — spec/unit type ids, accuracies,
rounding; no identity strings, verified by string scan) +
`_apply_family_units_law` replacing the project-derived 8-entry table in
`new_family_document`.  **Probe O** (`probe_o_units.rfa` = N + this law)
with the owner; validator VALID 0 errors; famgen suites 87 passed / 28
skipped.

Ladder so far: viewer law (convicted round 15) → dimension-style law
(holds round 16) → units law (probe O pending).  Each round's crash has
been strictly LATER in the user journey: open → click → pan → select →
Family Types dialog.

## Iteration 9 — the PARAM-SPEC/UNITS COHERENCE fix (round 17)

**Round 17 verdict (journal 0027, probe O):** Family Types still crashed at
`ADialog::doModal` (0xe06d7363) even with the full 136-spec units table.

**Root cause (instrumented):** our `ShortCircuitRatingkA` param declared
spec `autodesk.spec.aec:number-1.0.1`, but Revit 2026's registry AND the
donor units table both use `number-1.0.0`.  `factory.py`'s SPEC map had
`number-1.0.1` (labelled "corpus") while `skeleton.py` already defined the
correct `SPEC_NUMBER = number-1.0.0` -- an internal disagreement.  The
dialog formats every param value; the `-1.0.1` lookup missed the table and
threw.

**Fix:** `factory.py` SPEC["number"] now points at `SK.SPEC_NUMBER`
(`number-1.0.0`).  Every unit-bearing param spec our families declare now
resolves against the units table (verified: 0 missing).  Guarded forever by
`test_units_table_covers_every_param_spec` (asserts every non-unitless
ParamElemFamily spec has a format entry).

**Probe P** (`probe_p_numberspec.rfa`) with the owner; validator VALID 0
errors; famgen+ifc suites 104 passed / 31 skipped.

Ladder: viewer law (round 15) → dimension-style law (round 16) → units
table (round 16) → param-spec/units coherence (round 17).  If Family Types
opens on P, the next frontiers are value-edit and Save-As.

## Iteration 10 — the ORDER-CELL law: one group per group-type id (round 18)

**Round 18 verdict (journal 0028, probe P):** Family Types STILL crashed at
`ADialog::doModal` (0xe06d7363) with the spec fix.  Ruled out by instrument:
param ref integrity clean (14 params, all m_familyParams / cell / locked ids
resolve), param field structure matches the donor, all three group-type ids
(dimensions/electrical/identityData -1.0.0) confirmed present in a real Revit
corpus.

**Root cause:** the self-Family's `FamilyParamsOrderCell.m_sortedParams`
listed `identityData-1.0.0` **twice** -- once for the user identity params
(PanelName, Mounting) and again for the built-in identity BIPs
(-1010109/-1010104/-1010103).  The Family Types dialog builds its tree keyed
by parameter group; a duplicate group key collides -> throw at doModal.  The
donor has each group exactly once.

**The fix already existed but was unwired:** `layout_law.normalize_order_cell`
(the "M3 fix") merges duplicate group keys and re-ranks (dimensions <
identity < electrical), content-preserving.  It was only called from a probe
path; `tools/layout_diff.py` even carried a note "defect: make
normalize_order_cell part of [the build]".  Now called from
`FamilyDoc.finalize`, so every family is deduped by construction.  Guarded by
`test_order_cell_has_one_group_per_group_type`; `test_order_cell_merge`
updated (the build no longer emits duplicates, so the merge is now tested on
a synthetic duplicate).

**Probe Q** (`probe_q_ordercell.rfa`) with the owner; group keys now unique
+ ranked; validator VALID 0 errors; famgen+layout suites 120 passed / 28
skipped.

Ladder: viewer (r15) -> dim-style (r16) -> units table (r16) ->
param-spec/units coherence (r17) -> order-cell dedup (r18).  Five real
famdoc laws, each crash strictly later than the last.

## Iteration 11 — the STORAGE-CLASS LAW (rounds 22-24; the owner's specimen)

**Rounds 22-23:** spec-version hypothesis falsified (probe W: -2.0.0 also
crashed; Revit API docs confirm ForgeTypeId comparison ignores version).
Probes Y/Z: text-only AND integer-only both crash; probe U: all
double-valued params fine.  Probe AA (ints re-specced as number doubles)
OPENED the dialog — the crash axis is the VALUE STORAGE CLASS.

**Round 24 — the owner supplied the missing specimen** (`Test.rfa`: blank
Generic Model + one Text + one Integer param, made in Revit 2026), and it
ended the guessing in one measurement:

* A TEXT family parameter's def is a **`ParamDefString`** — carrying NO
  `m_specTypeId`, NO `m_restriction`, NO `m_boundless`.
* An INTEGER param's def is a **`ParamDefInt`** — same three fields absent,
  plus `m_lowBound=-2147483648`, `m_upBound=2147483647` (int32 bounds).
* Only measurable (double-valued) specs use `ParamDefValue` (+spec id +
  restriction 1 + boundless False) — the ONLY shape we knew, verified on
  all-double specimens, and wrongly stamped onto every param.  The dialog
  read our text/int params as measurable and formatted their values through
  the units path -> 0xe06d7363 at doModal.
* Value entries (m_familyParams / type rows) keep the SAME FamilyParamValue
  union shape for all storage classes.

**Landed:** `new_family_parameter` branches on storage class (SPEC_TEXT ->
ParamDefString, new SPEC_INTEGER sentinel -> ParamDefInt with int32 bounds,
else ParamDefValue); factory's "integer" spec now the sentinel (was the
INFERRED spec.int64 id, whose comment even claimed "a wrong spec id only
affects units display" — false: it crashed the dialog).  **Probe AB** (full
panelboard, every param in its native def class) with the owner; validator
VALID 0 errors; suites 97 passed / 28 skipped.

Remaining open threads: the recoverable "serious error" the owner hit while
EDITING values in probe AA (may vanish with the real law — AB tests it);
`Sketch Grid Appearance` (UET slot 40) follow-up singleton.

## Iteration 11 — the SOLVER-STATE law (round 26; the value-edit fix)

**Round 25-26 verdicts:** Family Types opens on the full panelboard (storage-
class law confirmed); editing ANY value raises the recoverable serious-error
dialog.  Journal 0036 names it: `DBG_WARN: Invalid idx in
VarSketch::getCurveObj (VarSketch.cpp:634)` -- regen resolves each curve
through the sketch's SOLVER RECORDS, and `new_var_sketch` emitted them EMPTY
(the "[H: Revit re-solves on edit]" hypothesis, now falsified).

**Donor law (VarSketch 2432 vs curve-less 2400):** a curve-bearing
parametric sketch carries `m_elemRecs` (one `VarSketchLineSegObj` per curve:
4 `VarParam`s = x1,y1,x2,y2, m_objId = the CurveElem), `m_constrRecs`
(closed-loop interleave: HV0, PP(1,0)[2,1], HV1, PP(2,1)[2,1], HV2,
PP(3,0)[1,2], PP(3,2)[2,1], HV3), a guess cache primed with the parameter
vector (useCount 29), `m_serFlags` 32 and `m_version` 1.  Weakrefs address
solver objects by archive pid (plane 3, GLines 4..3+n, LineSegObj i =
4+n+i); `assign_pids` reproduces the numbering -- verified our build lands
pids 8-11/12-19/20/21-36 byte-identical to the donor layout.

**Landed:** solver state authored in `new_var_sketch` (famgen/geometry.py).
Probe AD (`probe_ad_solver.rfa`) with the owner; validator VALID 0 errors;
famgen suites 124 passed / 35 skipped.  Open follow-up: the arc sketch
(`new_var_sketch_curves`, cylinders) still emits an empty solver -- needs
`VarSketchArcObj` records (same law, arc shape) before troffer/xfmr edits.
