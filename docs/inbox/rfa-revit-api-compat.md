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
