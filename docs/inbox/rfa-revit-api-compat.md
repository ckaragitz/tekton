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
