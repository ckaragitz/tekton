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

## Iteration 12 — corner-coincidence joins + classification tables (round 27)

**Round 27 verdicts (probe AD, journals 0037 + screenshots):** the solver
now RUNS -- the crash/serious-error is gone, replaced by Revit's NORMAL
4-message error dialog on value edit: "Can't make Extrusion" / "Base sketch
for extrusion is invalid" / "Internal setting 'Keynote Table' is required
by Revit and has been deleted" / warning "Highlighted lines overlap".

**Two faults, both fixed:**
1. **PP subtype semantics decoded** (donor 2432 measured end-to-end):
   subtype 1 = the (x1,y1) start, 2 = the (x2,y2) end, and each PP names a
   REAL shared corner -- the donor's edges are NOT wound tip-to-tail, so
   copying its index pattern glued the wrong corners of OUR winding and the
   re-solve collapsed the loop.  Joins are now COINCIDENCE-DETECTED from
   the actual endpoints (verified: every PP in the built probe names an
   exactly-coincident corner).
2. **Classification tables** (`AssemblyCodeTable` UET[64] +
   `KeynoteTable` UET[65], donor 2971/2972): authored as MINIMAL EMPTY
   tables -- the donor's carry Autodesk sample keynote text + an
   external-file reference into an Autodesk install path, content we never
   copy; the checker needs the registered element, not the data.

Probe AE (`probe_ae_corners.rfa`) with the owner; VALID 0 errors; suites
112 passed / 35 skipped.

## VERDICT (round 28): IT WORKS

Probe AE desktop-confirmed by the owner: value edits apply cleanly — the
full journey (open, render, zoom, pan, select, Family Types, edit values
incl. geometry-driving Width) works on a generated panelboard in desktop
Revit 2026.  Campaign issue #333 DONE met and exceeded.

## BRANCH STATE (final)

Branch `claude/333-varsketch-solver2` (PR #368, from merged main fba7efb).
Files: famgen/{geometry,skeleton,famdoc_adoc}.py, tests, this record,
learned-famdoc-laws.md, plugin mirror.  Gates: famgen suites 112 passed /
35 skipped; sync_plugin + validate_plugin PASS; probe AE VALID 0 errors +
desktop-confirmed.  Follow-ups to file as issues: arc-sketch solver records
(cylinders), LeaderStyle arrow-size warning, SketchGridAppearance UET[40],
Save-As + Load-Family desktop verification sweep.

## Iteration 13 — THE DONOR-LESS BUG (the ckaragitz12 report)

**Report:** a second collaborator generated families from the merged plugin
and they did not work -- while every file the owner desktop-confirmed in
rounds 13-28 did.  The owner's diagnosis was right: every probe was built
with `family_donor=<the owner's uploaded .rfa>`; a normal install has no
donor.

**Root cause:** with no donor the emitter takes the CONSTRUCTIVE path
(`constructive_family_host_tree`), whose AppInfoManager carried **0 of 239
manager slots populated** (a Revit-born famdoc fills 133).  Every registry
wiring added in rounds 13-27 -- `UniqueElementsTracking` [10]/[60]/[64]/
[65]/[85], `PenWidthTableInfo`, `SymbolIdMgr` key 10,
`BrowserOrganizationTracking` -- is guarded by `if isinstance(body, dict)`
and therefore **silently no-opped**.  Host `Global/Latest` shipped at
**252 bytes** (donor path: 65,249) -- the exact stub Revit rejects with
`Failed to load elemStream#0`.

**Correction to round 14:** probe M's 252-byte host was blamed on calling
`prod.write()` instead of `standalone_family_write`.  That was WRONG in an
important way -- the donor-less path produces the same stub through either
entry point.  Round 14's "instrument error" was really this product bug,
seen early and misfiled.

**Why no test caught it:** every famgen test reads the ELEMENT records
(unit 0, seq 101/102/103).  Nothing looked at the host ADocument, so the
element half of each law passed while the registry half was missing.

**Fix:** `_populate_appinfo_managers` fills the constructive tree's manager
slots from a measured index->class map
(`assets/famdoc_appinfo_slots.json`, 133 entries -- class names and slot
indices only, no donor content), each a schema-blank of its class with
`m_pADoc` weakref 1; `UniqueElementsTracking.m_elemIds` is sized to the
donor's 93 positional slots so the id writes land.  Donor-less output now:
133/133 slots, all four registries wired, `Global/Latest` a real document.
Guarded by `test_donorless_host_document_wires_every_registry` (the first
test that reads the host ADocument).

Desktop verdict pending on `donorless_fixed.rfa` / `donorless_troffer.rfa`.

## Iteration 14 — THE FAMILY-VIEW LAW (invisible geometry, sun path, giant text)

**Report:** "i dont see the element whats so ever", across three families
(`hanger_v5`, `panel400_v4`, a generic box) and every view the family ships
— Floor Plan, Ceiling Plan, "View 1" — while a `{3D}` view the owner
created *inside the same file* drew the geometry fine. Plus: "even the
reference lines cover the element" (dimension text at nine inches for a
1'-8" panel) and "what is up with the sun path???".

**What ended the guessing.** Four consecutive single-field rounds (camera
fit, the Viewer3d crop box, the category-exclusion list, the family
draw-order manager) each shipped and each left the report unchanged. The
control the owner ran — a *panelboard*, not the new multi-part path — failed
identically, which exonerated the geometry and convicted the view
constellation. So the views were diffed **field by field** against the
Revit-2026-born donor (views 50/23/27/463, viewers 49/22/26/461) instead of
patched one hypothesis at a time: **75 differing fields across 8 elements.**

**Root causes (all "our views were still PROJECT views"):**

| Field | Ours | Revit-born famdoc | Effect |
|---|---|---|---|
| `m_oaDrawFilters` | `PhasingDrawFilter` + `DesignOptionDrawFilter` present | neither (a bare `None` in the slot) | a famdoc has no phases and no design options, so both filters test state nothing satisfies — **the model never reaches the draw pass**. A freshly created `{3D}` view has neither, which is exactly why THAT view drew. |
| `m_scale` | 0.01 (1:100) | 0.041666666666666664 (1:24) on *every* view | dimension text ~9 in. tall on a 20 in. panel |
| `m_pViewDisplayMgr.m_lights.m_sunAndShadowSettingsId` | a real element | `-1` | the sun path around a 4-inch component |
| `m_pDetailDrawOrderMgr` | `DrawOrderMgr` on plans + project view | `DrawOrderMgr3dFamily` on **all** views | round 13 had converted only the 3D view |
| plan view range | derived from a storey height: cut plane 7.55 ft **above** the 3.94 ft top clip, plus a view-depth cutter | cut 4.0 / top 7.5 (plan), cut 7.5 / top ∞ (ceiling), no depth cutter | inverted range |
| `Viewer3d.m_projMethodType` / `m_viewerFlags` | 2 / 7 (perspective) | 1 / 0 (orthographic) | "View 1" is ortho in Revit; the donor parks its eye 1.7 ft off target and still frames the body |
| `DBView3d` camera frame | the project skeleton's look-down-on-a-building direction | the SE isometric (0.5774, −0.5774, 0.5774) | the earlier "camera fit" framed the right point in the wrong direction |
| `m_analyticalModelsExcluded` (3D) | `True` | `False` | (all four class-exclusion flags are False in every donor family view) |
| `m_pParamValueSetInt` | 3D view had an EMPTY set | `VIEW_DETAIL_LEVEL` = 2 (3D), 1 (plans), absent (project view) | no detail level at all |

**Fix:** one law, `_apply_family_viewer_law` in `famgen/skeleton.py`, applied
to the whole constellation (`DBViewProject` / `DBViewPlan` / `DBView3d` /
`DBViewSection` + their `Viewer`/`Viewer3d`), plus
`_apply_family_plan_range`, `_viewer3d_geom_steps` and per-view-kind
exclusion lists in `assets/family_view_excluded_categories.json` (now
`project` 7 / `plan` 41 / `ceiling` 41 / `3d` 42 / `section` 46 entries —
category ids only, no donor content). Release-shaped throughout: `_put`
writes a field only when the active release's schema defines it.

**Evidence:** every non-id field of all 8 view/viewer elements now matches
the Revit-born donor exactly (`DBViewProject` MATCH, `DBViewPlan.plan`
MATCH, `DBViewPlan.ceiling` MATCH, `DBView3d` MATCH, `Viewer.project`
MATCH, `Viewer.plan` MATCH, `Viewer.ceiling` MATCH, `Viewer3d` MATCH — the
only residue is our own element ids inside `PlanViewRange2`). Builds green
for 2026, 2025 and 2024 (validator family-mode VALID, 0 errors each).

**Still open:** the four elevation views (`DBViewSection` Back/Front/Left/
Right) the donor carries and steer S-2026-08-10-a requires — the family
still ships plan + ceiling + "View 1" only. No constructor yet; next.

### BRANCH STATE
* written: `src/rvt/famgen/skeleton.py` (family-view law, plan range, 3D
  camera frame, per-view-kind exclusions),
  `src/rvt/famgen/assets/family_view_excluded_categories.json` (+3 keys)
* gates: `tests/test_required_settings.py tests/test_identity.py
  tests/test_router_release.py tests/test_famgen_factory.py` 118 passed /
  8 skipped; `tests/test_famgen_skeleton.py test_famgen_adoc.py
  test_famgen_geometry.py test_bare_family_validate.py test_objects_plans.py
  test_famgen_catalog.py` 117 passed / 27 skipped;
  `tests/test_port2023.py test_port2024.py test_port2025.py
  test_famload_2025.py` 53 passed / 36 skipped;
  `tools/sync_plugin.py --check` clean; `plugin/scripts/validate_plugin.py`
  PASS (25 assertions)
* staged, not shipped: desktop verdict on `panel400_v5.rfa` /
  `hanger_v6.rfa` (the owner's two failing cases, rebuilt under the law)

## Iteration 15 — the four elevations (steer S-2026-08-10-a)

The family view set was still missing the elevations the steer requires.
Added `new_elevation_view` (famgen/skeleton.py): per elevation a
`DBViewSection` (`m_sectionViewType` 1, cut plane through the family
origin, `MakeCutterForSectionGStep` flags 7997) + `Viewer` +
fixed `SketchPlane` + `DBDrawing`/`Viewport` + `ExtentElem`, under ONE
shared "Elevation 1" `DBViewType` — the donor's own arrangement (type 1139
for all four). The four camera frames and their cutter x/y vectors are a
measured table, not a derived rule: Revit's Back/Front frames do not follow
the same convention as Left/Right, and deriving them is exactly the guess
that cost four rounds on the view law.

**Evidence:** Back / Left / Right match the donor's `DBViewSection` and
`Viewer` on *every* non-id field; Front differs only in `m_origin` /
`m_pCutter` / the viewer's bounded-space origin, all of which carry the
donor's y = −15 elevation-marker position (where that file's author dragged
the marker) — ours stays symmetric at the origin. `SketchPlane.m_oTrf`
columns are (horz, vert, viewDir) [donor 1885-1888]. `ExtentElem` header
role 26, same as the plans [donor 435-438].

Family element count 74 → 99. Builds green for 2026, 2025 and 2024
(validator family-mode VALID, 0 errors each).

**Two count assertions were updated, not loosened:** the viewer-bound law
now sees 7 Viewers (project + 2 plans + 4 elevations, was 3) and the extent
role split now includes `DBViewSection: {26}` — the donor value.

**Known residue, filed not fixed:** the document still carries 3
`SunAndShadowSettings` and 1 `LightSchemeElement` where a Revit-born family
has 1 and 0. The family-view law already unlinks them (every view's
`m_sunAndShadowSettingsId` is −1), so they are unreferenced; removing them
is a *reduction* and must go through `reduce_law` (their headers name the
views as deletion parents), which is a separate change.

### BRANCH STATE (updated)
* written: `src/rvt/famgen/skeleton.py` (+`new_elevation_view`,
  `_FAMILY_ELEVATIONS`), `tests/test_required_settings.py`
  (+`test_family_carries_the_four_elevations`, viewer count 3→7),
  `tests/test_identity.py` (extent roles + `DBViewSection`)
* gates: 13 stream-local files 280 passed / 71 skipped;
  `tests/test_plugin_sync.py test_bootstrap.py test_coldstart.py` 28 passed;
  `tools/sync_plugin.py --check` clean; `plugin/scripts/validate_plugin.py`
  PASS
* staged, not shipped: desktop verdict on `panel400_v6.rfa` /
  `hanger_v7.rfa`

## Iteration 16 — three faults the owner found in the now-VISIBLE family

The family-view law worked: `panel400_v6.rfa` renders shaded in View 1 and
the four elevations are in the Project Browser. Three separate faults were
visible only once the geometry could be seen.

**1. The forms were hidden in Plan/RCP.**
`ExtrusionElem.m_famElemVisibility` = 57398 was measured off the donor and
adopted wholesale — but bit 0 is the "Plan/RCP" checkbox of Family Element
Visibility Settings, and that donor's author had switched it OFF. We shipped
that preference on every form, so a generated family drew nothing in its own
plan and ceiling views regardless of what the views said [owner screenshot:
"Display in 3D views and:" with Plan/RCP unticked, Front/Back and Left/Right
ticked]. 57399 = 57398 | Plan/RCP, and a specimen-adopted value is now
OR-ed with bit 0 too: the bitfield is a format field, but that one bit is a
UI preference and must never be inherited.

**2. Every box reported a NEGATIVE extrusion depth.**
Revit reads -1001800 as "Extrusion Start", -1001801 as "Extrusion End", and
shows Depth = End − Start. The box path traces extrude-DOWN, so its `start`
IS the top, and writing the raw pair put the top in Start: the palette read
Start 0'5 3/4", End 0'0", Depth −0'5 3/4". Now ordered by elevation, not by
the tracer's direction. The B-rep is untouched — same solid, correct
reported depth. (The cylinder path traces extrude-UP and was already right;
the expression is a no-op there.)

**3. The panel was lying on the floor.**
`make_panelboard` traced W (x) × H (y) in the family plane and pushed the
DEPTH along +Z — the convention of a FACE-HOSTED family, whose xy plane is
the wall face. A standalone Electrical Equipment family's xy plane is the
Ref. Level floor plan, so a 5 ft panel lay flat: right solid, wrong axis,
and nonsense in the elevations. Footprint is now W × D with H extruded up,
exactly like the transformer next door; mounting shifts the box in Y about
the wall face at y = 0 (surface 0..D, flush −D..0). The feeder connector
moves to the +z cap, where it lands on tag 1 / edges [3, 6, 10, 14] — byte
for byte the transformer's convention.

**Regression this creates, stated plainly:** the parametric drive now labels
Width and **Depth** (the two sketch dimensions). Height became the extrusion
depth, and driving that needs a built-in-to-family parameter association we
do not author yet. Height is still a real parameter and still sizes the
geometry at generation time, but editing it in Family Types will not move
the box until that association exists. Filed as the next famgen task.

**Still open from the same report:** the solid draws in Shaded but not in
Wireframe, and the shaded solid has no edge lines at all — the cached
B-rep's edges are not reaching the draw pass. Not diagnosed yet; the next
measurement is our extrusion's edge `m_GInfo` / GStyle bindings against the
donor's.

### BRANCH STATE (updated)
* written: `src/rvt/famgen/geometry.py` (visibility bit + elevation-ordered
  extrusion offsets), `src/rvt/famgen/factory.py` (standing panelboard +
  top-face connector + Width/Depth drive), `tests/test_famgen_geometry.py`,
  `tests/test_famgen_factory.py`
* gates: 14 stream-local files 295 passed / 58 skipped;
  `tools/sync_plugin.py --check` clean
* staged, not shipped: desktop verdict on `panel400_v7.rfa` / `hanger_v8.rfa`

## Iteration 17 — THE OBJECT-STYLE LAW (no outline in any display mode)

**Report:** "when graphics display is on i can not see the outlining of the
geometry. i should be able to see it not only in shaded." The panel's own
3D screenshot shows the tell: a flat shaded body with **no edge lines at
all**, which is not how Revit draws a solid. So this was never a
wireframe-mode problem — the edges were not reaching the draw pass in any
mode, and Shaded happened to be the one mode that needs no line style.

**Measurement** (our extrusion vs the Autodesk library panelboard's three,
`m_subNodes[0]` = the `Geometry` node, GInfo field by field):

| GInfo field | Autodesk | Ours |
|---|---|---|
| `m_categoryId` | 17866 / 18446 (GStyleElem ids) | **−1** |
| `m_controlCommand` | 67108864 (+ per-element bits) | **0** |
| `m_flags` | 573444 | 573444 (match) |

`17866` is a `GStyleElem` whose own `m_categoryId` is **−2001040** — the
family's BUILT-IN category, not a CategoryElem id the way our
dimension-style copies are — with gstyleType 1, pen 1, colour 0, line
pattern −3000010, header role 67110926.

**Root cause:** a solid's `Geometry` node names the graphics style Revit
draws its EDGES with, and our documents deliberately carried none —
`geometry_context()` said so in as many words: *"reference the family's own
category style (-1: our documents carry no object-style copies -- the S0
reduction)"*. The reduction was invisible until the geometry itself became
visible.

**Fix:** `new_object_style` builds the family-category `GStyleElem` into
every famdoc (`doc.object_style_id`), and `geometry_context` hands its id to
every form as `geometry_style_id` with `solid_control_command` 67108864.
Verified on a built panelboard: object style 1075 → category −2001040, and
the extrusion's Geometry node names 1075 with cmd 67108864.

Guarded by `test_solids_name_the_family_object_style`. Family element count
99 → 100. Builds green for 2026, 2025 and 2024.

### BRANCH STATE (updated)
* written: `src/rvt/famgen/skeleton.py` (`new_object_style`,
  `FamilyDoc.object_style_id`), `src/rvt/famgen/factory.py`
  (`geometry_context` binds it), `tests/test_required_settings.py`
* gates: 13 stream-local files 279 passed / 55 skipped + the new guard;
  `tools/sync_plugin.py --check` clean
* staged, not shipped: desktop verdict on `panel400_v8.rfa` / `hanger_v9.rfa`

## Iteration 18 — the retouch styles (edges still not drawn)

The object style (iteration 17) was necessary and not sufficient: the owner
reports the solid is still invisible in Wireframe.

**One hypothesis killed by measuring it.** Our extrusion's `Edge` GInfo
flags read 557572 against the Autodesk panelboard's first extrusion at
557060 — a single bit (9) apart, and a tempting answer. Checking ALL THREE
of that file's extrusions instead of the first killed it: two of the three
carry **557572, exactly ours**. The 557060 one is the 28-edge shape, so the
bit tracks topology, not visibility. Edge flags are exonerated; recorded so
nobody re-suspects them. Our box B-rep is structurally sound as well —
6 Faces / 6 EdgeLoops / 12 Edges, the correct census for a box.

**What the same comparison did show.** Every family view's `RetouchTable`
in a Revit-born file names two graphics styles:

| | owner's donor | Autodesk panelboard | ours |
|---|---|---|---|
| `m_invisibleGStyleId` | 146 → category −2000064 | 17968 → −2000064 | **−1** |
| `m_notSilhouetteGStyleId` | 1266 → category −2000082 | 83898 → −2000082 | **−1** |

Both styles: gstyleType 1, ownerId −1, pen 2, colour 8355711, no line
pattern. Two independently authored files agreeing on the same pair makes
this format law rather than one author's setting — the test that the earlier
`m_famElemVisibility` mistake taught us to run.

**Fix:** `new_object_style` generalised (pen / colour / line pattern), the
two retouch styles built into every famdoc, and `_bind_retouch_styles`
points every view's table at them (the views are composed before the styles
exist, so it binds afterwards). Verified: styles 1076 (−2000064) and 1077
(−2000082), named by all 8 views.

Guarded by `test_every_view_names_the_retouch_styles`. Element count
100 → 102. Green on 2026, 2025, 2024.

**Honest status:** this is a measured difference against two Revit-born
files, not a proven cause. If Wireframe is still empty, the remaining
untested difference in the render path is the `Geometry` node's own
`m_flags` (573444, identical in both) and the seq-101 header role of the
extrusion — and at that point the right instrument is a Revit-born file
containing a form built the way ours is, not another field diff.

### BRANCH STATE (updated)
* written: `src/rvt/famgen/skeleton.py` (`RETOUCH_STYLES`,
  `_bind_retouch_styles`, parameterised `new_object_style`,
  `FamilyDoc.retouch_style_ids`), `tests/test_required_settings.py`
* gates: 13 stream-local files 249 passed / 83 skipped, plus
  `test_required_settings.py` + `test_identity.py` 50 passed;
  `tools/sync_plugin.py --check` clean
* staged, not shipped: desktop verdict on `panel400_v9.rfa` / `hanger_v10.rfa`

## Iteration 19 — WIREFRAME WORKS, and the hosting flag that was lying

**Owner verdict on iteration 18: "looks like v9 for the panel displays in
wireframe!"** The retouch styles were the missing piece. The full chain that
took a generated family from "nothing visible anywhere" to "renders in every
display mode" is now: the family-view law (#17 above) -> Plan/RCP visibility
bit -> the family object style -> the two retouch styles.

**Then a finding that partly reverses iteration 16.** Measuring the Autodesk
rme panelboard to build the Height->extrusion association showed:

* `m_isWorkPlaneBased` **True**, part type 14 -- byte-identical hosting flags
  to ours;
* its extrusions span **1.667 x 1.667 x 0.479 ft with the depth on Z** --
  i.e. it traces the panel FACE in the family XY, exactly the convention
  iteration 16 changed away from;
* `m_constrInfo` empty on all three, so no parameter association there
  either -- the Height drive will have to come from somewhere else.

So our original axes were not a mistake: they were a face-hosted family
behaving like one. It lies flat in the family editor **on purpose** and
stands up when you place it on a wall face.

**The actual inconsistency** was that we set work-plane-based AND place
instances on LEVELS rather than by picking a face, so the panel really did
end up lying on the floor of the project. Iteration 16 fixed the symptom and
left the flag claiming something the geometry no longer matched.

`make_panelboard` is now free-standing (`work_plane_based=False`) so the
geometry and the hosting flag agree, per the owner's steer ("it should be
pointed up especially if its in those elevation views"). The face-hosted
alternative is one flag plus the W x H axis swap, and the note in the
product says so in as many words.

**Open:** Height still does not drive the box. The association is NOT on the
extrusion (`m_constrInfo` empty in the reference), so the next measurement is
where a Revit-born family stores "Extrusion End = <family parameter>" --
likely a dimension or a constraint element rather than a field on the form.

### BRANCH STATE (updated)
* written: `src/rvt/famgen/factory.py` (panelboard free-standing + the
  measured note), `tests/test_famgen_factory.py`
* gates: 14 stream-local files 297 passed / 58 skipped;
  `tools/sync_plugin.py --check` clean
* shipped for verdict: `panel400_v10.rfa`

## Iteration 20 — famdiff: stop hand-rolling the comparison

**Owner steer (2026-08-10): "we reverse engineered the format. thats the
whole rvt python library we built from the ground up we should be able to
compute this."** Correct, and the record above proves the point against
itself: every law in iterations 14-19 was found by decoding a file where the
behaviour works, decoding one where it does not, and comparing -- and every
one of those comparisons was hand-written as throwaway Python in a heredoc,
explored once, and discarded. The knowledge was never missing. The
INSTRUMENT was.

`tools/famdiff.py` makes it a command:

    python tools/famdiff.py REFERENCE.rfa OURS.rfa [--class C] [--rep] [--all]

* pairs elements by CLASS and ROLE (view name, plan type, category,
  symbol name), never by id;
* diffs recursively, optionally into the seq-103 B-rep;
* classifies each leaf so the noise removes itself: **id** (both sides hold
  an element id live in their own file -- 1075 vs 17866 is renumbering, not
  a finding), **float** (equal within 1e-9 -- 3.999999999999994 vs 4.0),
  **real**;
* RANKS real differences by how many paired elements show them, and labels
  a difference present in EVERY pair `LAW`. That ranking is the automated
  form of the check that saved this campaign from "fixing" an edge-flag bit
  two of three reference extrusions turned out to share with ours.

**It paid for itself on the first run.** Four differences in
`m_pViewDisplayMgr`, present in every paired view, that every hand-written
diff in this campaign had **explicitly skipped** because the subtree is long
and looks stock:

| field | references | ours |
|---|---|---|
| `m_exposure.m_crushBlacks` | 0.2 | 1.0 |
| `m_exposure.m_exposureDouble` | 14.0 | 15.0 |
| `m_oStaticRRTRenderSettings.m_BkIamgeSettings.m_FitType` | 0 | 43 |
| `m_shadows.m_ambientShadows` | False | True |

Both reference families agree on all four -> law, now applied. The same run
shows `m_annotationsExcluded` DISAGREEING between the two references, so
that one is an author's choice and is deliberately left alone -- the tool
makes that distinction cheap instead of a judgement call.

**Residual after applying them: zero.** `famdiff` against the Revit-born
donor over `DBViewPlan`, `DBViewSection` and `Viewer` reports "the two agree
on every paired element".

**What still cannot be computed, stated precisely so nobody re-litigates
it:** the mapping from a value to a Revit BEHAVIOUR. The schema says
`m_flags` is a 32-bit int; nothing in any file says bit 0 means "draw in
Plan/RCP". That needs an oracle -- desktop Revit, or two files that differ
in exactly one behaviour. What famdiff computes is the CANDIDATE SET, which
is the expensive part; the oracle then costs one open.

### BRANCH STATE (updated)
* written: `tools/famdiff.py` (new instrument),
  `src/rvt/famgen/skeleton.py` (`_FAMILY_VIEW_DISPLAY`,
  `_FAMILY_VIEW_BK_FIT_TYPE` + their application)
* gates: 14 stream-local files 297 passed / 58 skipped; 2026/2025/2024 build
  VALID 0 errors; `tools/sync_plugin.py --check` clean;
  `check_portable_paths.py` ok (2934 paths)
* shipped for verdict: `panel400_v11.rfa`

## Iteration 21 — the regeneration rep is a MYTH, and the N-gon prism

**The probe and its verdict.** A three-part family (concave L-bracket +
cylinder + cap) was built to test one question: does Revit rebuild a family
form's solid from its sketch when the file ships the SerializedDummy
"regeneration" rep? Owner screenshot: the cylinder and the cap render, and
**the L-bracket is absent**. Clean negative, single variable (the two that
rendered carry cached B-reps, the one that vanished does not).

**This kills a belief that had been load-bearing since the box work.** The
code asserted, in `add_polygon_form`, that "the extrusion is fully defined
by its sketch + depth and Revit rebuilds the solid on open (the variant
already accepted for walls)". Accepted for WALLS, never once verified for a
family form. Consequences:

* every non-4-gon part a generated family has ever contained was
  **invisible**, silently -- including the owner's early hangers;
* the shortcut to revolves/sweeps ("author the definition, skip the B-rep")
  does not exist. Every form needs a real cached solid.

**The fix needed no reference file at all** -- the point of the owner's
steer, and the proof of it. `solid_box_brep` was never rectangle-specific:
`_box_tags(n)` was already written for N, the frames, envelopes, edge order,
pid numbering and uv projections are all expressed in `n`, and a prism over
an N-gon is exactly the box topology with N sides (N+2 faces, 3N edges).
Only the guard said 4. Removed; `add_polygon_form`'s REP_DUMMY fallback
removed with it.

Verified: triangle, pentagon, hexagon, 12-gon and the concave L all build
cached B-reps with the right census (N+2 faces, 3N edges) and round-trip
clean. The three-part probe now reports cached B-rep for all three parts.

**Contract change, deliberate:** a RAW vertex ring handed to
`solid_box_brep` is now winding-NORMALISED rather than refused (an IFC
profile's winding follows its own axis convention, and `polygon_profile`
already did this for `add_polygon_form`). A pre-built `RectProfile` must
still be CCW -- the caller asserted an order -- and degenerate or collinear
rings still raise. The guard test now documents all three.

**Open, and now correctly scoped:** revolve / sweep / blend still need their
own cached B-reps, i.e. the surface-of-revolution and swept topologies. That
IS a measurement problem (`ConeSurf` exists; no sphere or torus surface
class is visible in the schema), unlike the N-gon, which was pure arithmetic.

### BRANCH STATE (updated)
* written: `src/rvt/famgen/geometry.py` (N-gon prism), `factory.py` (no
  regeneration fallback), `tests/test_famgen_geometry.py`
  (+`test_ngon_prism_solid_is_cached`, rewritten winding guard)
* gates: 14 stream-local files 301 passed / 58 skipped; 2026/2025/2024 build
  VALID 0 errors; `tools/sync_plugin.py --check` clean
* shipped for verdict: `concave_probe_v2.rfa`, `ngon_probe.rfa`

## Iteration 22 — the L renders; the second probe is inconclusive and that is MY fault

**Owner screenshots, two files.**

`concave_probe_v2.rfa`: **the concave L-bracket renders as a solid**, with
the cylinder and cap. Iteration 21's N-gon prism is confirmed in Revit.
Arbitrary closed profiles are live.

`ngon_probe.rfa`: unreadable as evidence. The two prisms look like open
shells, but every invariant computable from the solid says otherwise, and
the probe was badly designed by me:

* two shapes, both SQUAT (1.2 ft across x 0.4 ft tall, and 1 x 0.9 x 0.3),
* horizontally OFFSET from each other -- raw vertex rings were given in the
  +x/+y quadrant while every box and cylinder we build centres on the
  origin, so nothing lines up,
* stacked so they SHARE a plane at z = 0.3 (coincident faces).

Three variables at once. Unreadable by construction; a control would have
caught it. Rebuilt as `hex_solo.rfa`: ONE hexagonal prism, centred,
1.0 ft across x 1.0 ft tall, nothing touching it.

**What was checked before asking for another open** (all pass, n = 3..12
and the concave L):

| invariant | result |
|---|---|
| Euler V-E+F = 2 (2N vertices) | holds |
| every edge names exactly 2 faces | holds |
| every face bounded by >= 3 edges (caps N, sides 4) | holds |
| every face loop CLOSES following `m_next` | holds |
| endpoint uv agrees between an edge's two faces | max 6.7e-16 ft |
| default 3D camera outside the geometry bbox | holds, both probes |

**Landed as `geometry.check_solid()` and wired into `prism_form`**, which
now REFUSES to emit a form whose solid is not a closed manifold. This is
the gap that let a bad solid reach Revit with "0 errors": `rvt_validate`
checks records and references and knows nothing about B-rep topology.
`test_check_solid_catches_an_open_shell` deletes a face and asserts the
check fails, so the check is evidence rather than decoration.

**Honest limit:** these invariants prove a solid is closed and
self-consistent. They cannot prove Autodesk's reader likes it (hard rule 4).
What they do is make "the validator was green" stop meaning nothing here.

### BRANCH STATE (updated)
* written: `src/rvt/famgen/geometry.py` (`check_solid` + the `prism_form`
  gate), `tests/test_famgen_geometry.py` (+3 tests incl. the negative)
* gates: 14 stream-local files 309 passed / 58 skipped;
  `tools/sync_plugin.py --check` clean
* shipped for verdict: `hex_solo.rfa` (single variable, centred, control-shaped)

## Iteration 23 — hex_solo is invisible, and nothing computable explains it

**Owner: `hex_solo.rfa` shows nothing at all.** One hexagonal prism, centred,
1 ft across x 1 ft tall -- absent. The SAME generator, same code path and
same n = 6 produced the concave L that rendered in iteration 22.

**Everything checkable says the file is sound.** Compared against
`concave_probe_v2.rfa` (which renders), via `tools/famdiff.py` and a class
census:

* the ExtrusionElem is identical in kind: `m_famElemVisibility` flags 57399,
  categoryId -1, a seq-103 rep present, **8 faces** = 6 sides + 2 caps;
* `check_solid` passes (closed manifold, loops close, uv consistent);
* the sketch curves are right -- each `m_origin`/`m_dirVec`/`m_endParams`
  triple reconstructs the correct hexagon vertex;
* famdiff over EVERY class reports only coordinate differences. No class is
  present in one file and missing from the other;
* class census: only `CurveElem` 12/6, `ExtrusionElem` 3/1, `SketchPlane`
  9/7, `VarSketch` 3/1 -- all exactly proportional to part count
  (1 sketch plane + 1 VarSketch + 1 curve-per-edge per part, over a
  6-element baseline). Every other class is equal;
* the 3D camera sits outside the geometry bbox in both files.

hex_solo is a strict structural SUBSET of the file that renders. No defect
is computable from the file, so the difference is in something only Revit
evaluates.

**Four variables were confounded** between "L renders" and "hex does not":
concave vs convex, 1.5 ft vs 1 ft, offset into +x/+y vs centred on the
origin, and accompanied vs alone. Iteration 22 already criticised exactly
this and then shipped `hex_solo` with four changes at once.

Two probes, ONE variable each, both against the file known to render:

| probe | changed vs `concave_probe_v2` | in-file control |
|---|---|---|
| `probe_A_hex_in_place.rfa` | the L profile -> a hexagon, same footprint, same z | cylinder + cap, unchanged |
| `probe_B_L_alone.rfa` | companions removed | none -- that IS the variable |

Reading: A hides the hexagon but shows cylinder+cap -> convexity or the
profile itself. A shows everything -> the shape was never the problem. B
hides the L -> being the only form in the file is the problem, which would
also explain `hex_solo` and would make it a document-level bug, not
geometry.

### BRANCH STATE (updated)
* written: no engine change this iteration -- diagnosis only
* gates: unchanged from iteration 22 (309 passed / 58 skipped, sync clean)
* shipped for verdict: `probe_A_hex_in_place.rfa`, `probe_B_L_alone.rfa`

## Iteration 24 — convexity and aloneness both exonerated

**Owner opened both single-variable probes; BOTH render.**

* `probe_A_hex_in_place.rfa` -- the hexagon renders as a clean solid, with
  the cylinder and cap controls. **Convexity is not the cause**; a convex
  N-gon prism is fine.
* `probe_B_L_alone.rfa` -- the L renders by itself. **Being the only form in
  the file is not the cause**; there is no document-level bug.

Two of the four confounded variables from `hex_solo` are dead. What is left,
and it is the pair nobody had looked at:

| | rendered so far | `hex_solo` (invisible) |
|---|---|---|
| position | offset into +x/+y | **centred on the origin** |
| aspect | flat slab, 0.25 ft thick | **1.0 ft tall on a 1.0 ft footprint** |

Every single form this project has ever seen render is a FLAT SLAB sitting
away from the origin. That is not a deliberate choice, it is an accident of
how the probes were written -- and it means "tall" and "centred" have never
once been tested. The panelboard's enclosure is 1.667 ft tall and centred,
which makes this directly relevant to the product rather than a curiosity.

`probe_C_origin_vs_tall.rfa` separates them in ONE file (parts render
independently, so same document, same views, same camera = the cleanest
possible comparison):

1. `control-box` at x = -2, flat -- the shape that has never failed;
2. `hex-at-origin`, r = 0.5, **flat**, centred exactly on (0, 0);
3. `hex-tall` at x = +2, r = 0.5, **1.0 ft tall**.

Reading: 2 missing -> a form centred on the family origin is invisible
(suspect the reference planes / sketch-plane association at the origin).
3 missing -> tall extrusions are invisible (suspect the start > end
"extrude-down" convention, or a view range / cut plane). Both present ->
the cause is the COMBINATION, and the next probe is a tall hexagon centred
on the origin, i.e. `hex_solo` minus nothing.

### BRANCH STATE (updated)
* written: no engine change -- diagnosis only
* gates: unchanged (309 passed / 58 skipped, sync clean)
* shipped for verdict: `probe_C_origin_vs_tall.rfa`

## Iteration 25 — all four variables exonerated individually; testing the combination

**Owner: `probe_C_origin_vs_tall.rfa` renders ALL THREE parts.** The control
box, the flat hexagon centred exactly on the origin, and the 1.0 ft tall
hexagon are all present and correct.

So every variable that distinguished `hex_solo` from a rendering file has
now been cleared **on its own**:

| variable | verdict | evidence |
|---|---|---|
| convex profile | fine | probe A hexagon renders |
| only form in the file | fine | probe B, L alone, renders |
| centred on the family origin | fine | probe C middle hexagon renders |
| 1.0 ft tall (not a flat slab) | fine | probe C right hexagon renders |

`hex_solo` is exactly *centred + tall + alone*, and each of those three is
individually harmless. Either the COMBINATION is the fault, or the original
file was not what its recipe says it was.

Both are now testable, and the second one first because it is cheaper:

* `probe_E_hex_solo_again.rfa` -- `hex_solo` rebuilt from the identical
  recipe. It comes out **225,280 bytes, exactly the original's size**, and
  `famdiff` between the two reports no differences at all. So E *is*
  hex_solo. If E renders, the original open was the fluke (stale file,
  wrong view, cached thumbnail) and there is no geometry bug at all. If E
  is also empty, the failure is reproducible and real.
* `probe_D_tall_centred.rfa` -- the exact same tall centred hexagon plus a
  flat control box off to the side. If the hexagon appears here but E is
  empty, then "alone" matters only in combination with tall + centred, and
  the bug is in whatever the document does differently when a single form
  is the entire family.

**Note on cost:** this is the fifth consecutive round spent on one invisible
hexagon, each round costing the owner an open. The four exonerations are
real progress and each was single-variable, but the honest read is that
`hex_solo` may simply have been a bad file, and iteration 22 should have
re-sent it once before building three probes on top of it.

### BRANCH STATE (updated)
* written: no engine change -- diagnosis only
* gates: unchanged (309 passed / 58 skipped, sync clean)
* shipped for verdict: `probe_D_tall_centred.rfa`, `probe_E_hex_solo_again.rfa`

## Iteration 26 — hex_solo was a viewing fluke; the N-gon prism is CONFIRMED

**Owner opened both. BOTH RENDER.** `probe_E_hex_solo_again.rfa` -- the
byte-identical rebuild of the file that appeared empty -- shows a clean tall
hexagonal prism. `probe_D_tall_centred.rfa` shows control box + tall centred
hexagon.

**There was never a geometry bug.** The original `hex_solo` open was a
mis-read: the owner's Revit screenshot shows ~14 open view tabs across
several files (`Ref. Level` / `View 1` repeating), so the empty view was
another document's. Iterations 23-25 cost three opens chasing it.

**The rule this cost us, written down so it is not paid twice:** when a
file that every computable check says is sound appears broken, RE-SEND THE
SAME FILE ONCE before building probes on top of the observation. Iteration
23 had already established that hex_solo was a strict structural subset of a
rendering file with no computable defect -- that was the moment to suspect
the observation, not the file. A negative result from a human's screen is a
measurement, and measurements get repeated before they get theorised about.

**What IS confirmed, and it is a lot.** The N-gon prism is now verified in
Autodesk Revit 2026.4 across every axis that was ever in doubt:

| axis | verified |
|---|---|
| sides | 4 (box), 6 (hex), and the concave 6-gon L; 3/5/8/12 build + pass `check_solid` |
| convexity | convex AND concave both render |
| position | centred exactly on the family origin, and offset into +x/+y |
| aspect | flat slab (0.25 ft) and tall (1.0 ft on a 1.0 ft footprint) |
| company | alone in the file, and beside boxes/cylinders |

**And the finding from iteration 21 stands, because it had an in-file
control:** the SerializedDummy "regeneration" rep draws NOTHING. In
`concave_probe.rfa` the cylinder and cap (cached B-reps) rendered while the
L (regeneration rep) did not -- same file, same view, same camera, one
variable. That is why every form now ships a real cached solid.

**Net from this arc:** two real findings (the regeneration rep is a myth;
the N-gon prism is the box topology with N sides), two permanent
instruments (`tools/famdiff.py`, `geometry.check_solid`), and one wasted
ghost hunt.

### BRANCH STATE (updated)
* written: no engine change -- this iteration is the verdict + the lesson
* gates: unchanged (309 passed / 58 skipped, sync clean)
* status: arbitrary closed profiles are CONFIRMED shippable geometry
