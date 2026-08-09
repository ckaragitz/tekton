# readers-release-aware — the five read-only entry points open a Revit 2025/2024 file under its own release (issue #121)

Stream: `readers-release-aware` (engineer session `eng121` on #121, started
by the tech-lead session; cloud VM, fresh clone, Python 3.11). Territory:
`src/rvt/census.py`, `src/rvt/render/inspect.py`, `tools/seed_audit.py`,
`src/rvt/inventory.py`, `src/rvt/convert/rvt_to_ifc.py`, new
`tests/test_readers_own_release.py`, `tests/ci_shard.txt` (+1 line), this
record, and the `tools/sync_plugin.py` mirrors of the five files. Builds on
PR #91 (`rvt.global_framing.enter_own_release`, the ladder's single home)
and follows the shape of #50 (`validate_file`), `rvt_analyze`, `famload`
and PR #137 (the edit path): **no third copy of the ladder, no hot file
touched** (`src/rvt/versions/`, `validate.py`, `global_framing.py`,
`tools/frontdoor.py`, `provenance.py`, `make_family.py`, `rvt_edit.py` all
unchanged).

## 0. The defect, reproduced (origin/main @ a0183b7, tracked bases, before any change)

| entry point | `G_ABPD.rvt` (2026) | `G_ABPD_2025.rvt` | `G_ABPD_2024.rvt` |
|---|---|---|---|
| `python -m rvt.census <base>` | rc 0, 0.63 s, `host_records=3102 classes=148 units=1 … coherent=True` | rc **0** but the whole census is one line: `ERROR ValueError('unexpected Partitions header: v=9 cls=0x391')` (0.21 s) | same, `cls=0x37b` |
| `python -m rvt.render.inspect <base>` | rc 0, 0.26 s, 12 Level/Grid rows, `kinds: dummy=12` | rc 1, traceback `mutate.py:233 → partitions.py:243 ValueError … cls=0x391` | rc 1, `cls=0x37b` |
| `tools/seed_audit.py <base>` | rc 0, 0.31 s, `=== SEED AUDIT … levels (9) … wall types: 1` | rc 1, same traceback via `seed_audit.py:104 load_document` | rc 1 |
| `python -m rvt.inventory <base>` | rc 0, 0.20 s, `== inventory of … levels (9) …` | rc 1, same traceback via `inventory.py:682` | rc 1 |
| `python -m rvt.convert.rvt_to_ifc <base> --out-dir D` | rc 0, 1.0 s, `G_ABPD.ifc` + manifest delivered, `format: 2026` | rc 2, `ERROR: cannot read …: ValueError: unexpected Partitions header: v=9 cls=0x391`, **no .ifc** | rc 2, `cls=0x37b`, no .ifc |

And the census DONE point: a 2025 project built in a tmp dir by
`tools/frontdoor.py author --prompt "an electrical room with 6 panels"
--target-version 2025` (19 s) → `python -m rvt.census` printed the same
one-line `ERROR …cls=0x391`; the same `census()` call made *inside*
`enter_own_release` read `CD entries 6 / ContentTable 6 / family docs 6,
coherent=True` — the instrument was blind, not the file.

## 1. What was built (one `with ExitStack()` per entry point, at the top)

* **`src/rvt/census.py`** — `census(path)` self-wraps: it enters
  `enter_own_release(stack, path)` once and runs the unchanged body
  (`_census`); every census now carries `release` (the year
  `versions.detect_release` reads from BasicFileInfo) and, only when the own
  schema could not settle the framing, `release_note` (the ladder's one
  sentence; `_print_census` prints it as a `release:` line). Inside the
  context `_content_documents` parses with the file's tokens and
  `_adocument_facts` → `open_document_object(path)` decodes Global/Latest
  with the file's own schema (`global_framing.bound(schema=…)` swaps
  `adocument._DECODER`), so the coherence tuple is real on any release.
  **`run_certified()` keeps releases apart** (the caveat in
  `docs/inbox/validate-release-aware.md` §Findings): the diff tables
  (`passing_files`, `failing_files`, `mandatory_set`,
  `class_presence_passing`, `suspects_strict/loose`, `streams_units`) moved
  into `_corpus_tables(passing, failing)`; the top-level tables are computed
  over the `reference_release` files only (default
  `versions.LATEST_RELEASE` = 2026 — exactly the population the runner
  measured before, when every older-release file errored out of it), and
  every release seen gets the same tables under `by_release[year]`;
  `censuses` holds every file read. `--certified` prints one extra line per
  non-reference release (`release 2025: passing N failing M mandatory
  classes K (by_release)`); the first line and the mandatory/suspect lines
  are byte-identical to before. New kwarg `reference_release=` for a
  deliberate per-release run.
* **`src/rvt/render/inspect.py`** — `_is_file_source()` factors the existing
  "path vs corpus name vs Document" test out of `_open`; `_enter_release`
  enters the ladder for a file source (a `Document` or corpus name has no
  file to read a release from). `inspect(source, …)` self-wraps (open +
  decode inside the context); `main()` enters once before anything is
  opened, prints `release: <sentence>` only when a fallback rung was taken,
  and runs the unchanged report body (`_report`). The two documentary
  constants `CLASS_GELEMENT` / `CLASS_SERIALIZED_DUMMY` are not used for
  classification (it is by class *name* through the file's own decoder), so
  nothing else was release-pinned.
* **`tools/seed_audit.py`** — `audit(seed, spec)` enters the ladder when
  `seed` is a file on disk and runs the unchanged body (`_audit`); a
  fallback is `report["release_note"]` and a `release:` line under the
  `=== SEED AUDIT` header. Mirrored into `plugin/lib/tools/` and the
  `tekton-{inspect,author,native}` skill `scripts/`.
* **`src/rvt/inventory.py`** — the library functions take an open
  `Document` (the caller's context applies, e.g. `seed_audit`,
  `rvt_to_ifc`); the CLI `main()` enters the ladder once for a `.rvt` path
  and runs the unchanged body (`_main`); a fallback is `release_note` in
  `--json` and a `release:` line in the text form.
* **`src/rvt/convert/rvt_to_ifc.py`** — `convert_rvt_to_ifc()` enters the
  ladder once around the whole route (provenance → extract → emit → round
  trip → manifest; body `_convert_rvt_to_ifc`), and `extract_intent()`
  self-wraps for library callers (body `_extract_intent`; nested inside the
  route it joins the same release). The manifest already names the source
  release at `input.provenance.format` (read from BasicFileInfo); a fallback
  rung, if taken, is a `degradations` entry `source release: <sentence>` —
  a caveat after delivery, never a refusal (hard rule 1).
* Docstrings of all five state the own-release rule generically ("any
  release we can frame"), per #50's wording.
* **`tests/test_readers_own_release.py`** (22 tests, 30 s, sample-free, in
  `tests/ci_shard.txt`): per entry point × {2026, 2025, 2024} on the bundled
  bases in `main([...])` / library form (census: `release == year`, > 3000
  host records, coherent, ADocument decoded; render.inspect: ≥ 9 Level/Grid
  dummy rows + CLI rc 0; seed_audit: `--json` report, 9 levels, one named
  wall type with thickness; inventory: `--json` + text rc 0, 9 levels, the
  two phases; rvt_to_ifc: rc 0, an `ISO-10303-21` .ifc, manifest
  `provenance.format == str(year)`, levels cell `works/9`, no errors, no
  `source release:` caveat); a module fixture builds the 2025 six-panel room
  through the front door and pins **census 6/6/6 coherent**, render.inspect
  `brep == 6` symbols, inventory 6/6 named symbols, rvt_to_ifc equipment
  count 6 and (round trip ran) `6/6 all_survived`; `run_certified` with a
  monkeypatched ledger of the three bases → `reference_release 2026`,
  top-level == `by_release[2026]`, 2025 under `by_release[2025].passing`,
  2024 under `by_release[2024].failing`; census nested inside
  `V.reading(year=2025)` leaves the outer ordinals in force; a 64 KiB
  truncation of the 2025 base through `rvt_to_ifc.main` → rc 2, manifest
  caveat `source release: own schema unreadable … pinned Revit 2025 framing
  table`, and the error is the real truncation (`no trailer for block`),
  never `cls=0x…`. An autouse fixture asserts the latest-release framing
  table, `factory.CD_SEPARATOR/CD_END_RECORD` and `adocument._DECODER` are
  back after every test. Sanity: with the five source changes stashed the
  five `[2025]` per-base tests fail with the original `ValueError`; with
  them, 22/22 pass.

## 2. Evidence (this cloud VM, Python 3.11.15; measured on main@a0183b7 + this, re-checked after the rebase onto main@21a9c49)

* **After, repo checkout, `.venv/bin/python`** (wall time incl. interpreter start):

  | entry point | 2026 | 2025 | 2024 |
  |---|---|---|---|
  | `rvt.census` | rc 0, 0.63 s — output **byte-identical** to before | rc 0, 0.81 s, `host_records=3316 classes=145 units=1 CD entries=0 ContentTable=0 coherent=True`, `host families=8`, `DBViewType n=91` | rc 0, 0.53 s, `host_records=3278 classes=142 … coherent=True` |
  | `rvt.render.inspect` | rc 0, 0.76 s — identical | rc 0, 0.45 s, 12 Level/Grid rows, `kinds: dummy=12` (same shape as 2026) | rc 0, 0.47 s, same |
  | `tools/seed_audit.py` | rc 0, 0.76 s — identical | rc 0, 0.47 s, `levels (9) … wall types: 1 (1 named) CL_W1 280 mm … phases [Existing Conditions, New Work]` | rc 0, 0.48 s, same |
  | `rvt.inventory` | rc 0, 0.56 s — identical | rc 0, 0.47 s, `levels (9) … wall types: 1/1 named … phases …` | rc 0, 0.47 s, same |
  | `rvt.convert.rvt_to_ifc` | rc 0, 1.97 s — **.ifc byte-identical** to before; manifest identical modulo out-path/seconds/traceback line no. | rc 0, 1.17 s, `G_ABPD_2025.ifc` delivered, manifest `provenance.format "2025"`, levels `works/9`, FOREIGN stamp, no errors | rc 0, 1.08 s, `G_ABPD_2024.ifc`, `format "2024"` |

  (The 2026 column's times are the first, cold-cache invocations of the run;
  the per-call cost of the ladder is one `schema_of` parse ≈ 0.1 s, memoised
  per path inside `global_framing`.)
* **The 2025 six-panel room** (`frontdoor author --prompt … --target-version
  2025`, tmp): census `units=7 (family docs 6) CD entries=6 ContentTable=6
  coherent=True, host families=14 (with doc 6, system/no-doc 8)`;
  render.inspect `28 elements: 6 carry baked/referenced geometry … kinds:
  dummy=22, brep=6`; inventory `symbols: 6/6 named (100.0%) … category
  sources {'builtin-verified': 6}`; rvt_to_ifc 1.3 s → `round trip:
  equipment 6/6, walls 4/4, all_survived=True`.
* **Degraded input** (first 64 KiB of the 2025 base): `rvt_to_ifc` rc 2,
  manifest + MANIFEST.md written, `degradations = ["source release: own
  schema unreadable (VersionError: schema lacks the partition-framing classes
  …); checked against the pinned Revit 2025 framing table (the release
  BasicFileInfo declares)"]`, `errors[0]` = the real `RuntimeError:
  Partitions/20: walker errors ['no trailer for block at 33759 …']`;
  `rvt.census` → `ERROR ValueError("'Formats/Latest': no gzip members …")`
  (a census needs the schema itself, so it fails on the real cause; no
  fictitious `cls=0x391`); `rvt.inventory` → the same real walker error.
* **Bare unzip of the rebuilt `tekton-plugin.zip`, system `python3` 3.11,
  `TEKTON_ROOT` unset, copies of the 2025 base and the 2025 room as "the
  user's files"** (the `tekton-inspect` skill's documented commands, steer
  #108 wall times): `skills/tekton-inspect/scripts/_bootstrap.py run
  seed_audit.py user2025.rvt` → rc 0, **0.94 s** (first call) / 0.38 s on the
  room (`walls placed: 4`); `… run render_inspect.py user2025.rvt` → rc 0,
  **0.33 s**, `12 elements … dummy=12` / 0.62 s on the room, `brep=6`;
  `… run seed_audit.py userroom2025.rvt --job examples/electrical-job.json`
  → full COVERAGE section, `the writer would pick TODAY: wall type 600634
  'CL_W1'; equipment {'panelboard': 'Panelboard PP-1 480Y/277 225A MLO 42sp
  :: 225A MLO 42ckt'}`, verdict line printed; `… run rvt_validate.py` on both
  → `OK errors=0 warnings=0`. Before this change the first two died with the
  §0 traceback from the same launcher (it delegates to
  `rvt.render.inspect` / the mirrored `seed_audit.py`).
* **Tests:** `tests/test_readers_own_release.py` **22 passed** (31.6 s) on
  the final diff. Adjacent (`RVT_SKIP_LARGE=1`): `test_census test_inventory
  test_render_inspect test_convert test_validate_release test_rvt_analyze
  test_famload_2025 test_plugin_sync test_bootstrap test_coldstart
  test_surface_perf` → **63 passed / 41 skipped / 0 failed** (43.5 s; the
  skips are the sample-dependent cases). CI shard exactly as CI runs it
  (`RVT_SKIP_LARGE=1 … $(grep -vE '^\s*(#|$)' tests/ci_shard.txt)`) on the
  rebased branch → **553 passed / 31 skipped / 1 xfailed** in 190.8 s.
* **After `/simplify`, re-verified:** the five commands × three bases again
  rc 0 (0.5–1.2 s each); 2026 text outputs and the 2026 `.ifc` still
  byte-identical to *before the PR*; 2025/2024 outputs byte-identical to the
  pre-simplify run. Bare unzip of the rebuilt zip, system `python3`:
  `skills/tekton-author/scripts/_bootstrap.py go author --prompt "an
  electrical room with 6 panels" --target-version 2025 --out out/j25 --json`
  → `ready true`, preflight `tekton: READY … 0.102s`, job 18.4 s, `result.ok
  true`; on that output `… tekton-inspect …/_bootstrap.py run seed_audit.py
  <room>` rc 0 0.44 s, `… run render_inspect.py <room> --class FamilySymbol`
  → `6 elements: 6 carry baked/referenced geometry … kinds: brep=6` 0.38 s,
  `… run rvt_validate.py <room> --quiet` → `OK errors=0 warnings=0`.
* **Plugin:** `tools/sync_plugin.py` → 8 files synced
  (`plugin/lib/src/rvt/{census,inventory}.py`, `…/render/inspect.py`,
  `…/convert/rvt_to_ifc.py`, `plugin/lib/tools/seed_audit.py`,
  `plugin/skills/tekton-{author,inspect,native}/scripts/seed_audit.py`),
  deny-audit clean, validation passed, zip rebuilt (not committed);
  `--check` → in sync; `plugin/scripts/validate_plugin.py` PASS (24
  assertions); `tools/dev/check_portable_paths.py` ok (2702 → 2704 paths).

## 3. Findings / follow-ups (filed as issues, not done here)

* **#252 — the deeper fix.** With this PR there are ~ten `public()` →
  `with ExitStack(): enter_own_release; _body()` shims across engine and
  tools. Root cause one layer down: `mutate.Document.from_file` /
  `families.FamilyIndex` bind the file's own *schema* for object decoding
  but neither activate nor remember its *release*, so every caller must hold
  a module-global context open around construction **and all later
  decoding** (why `render.inspect.main` keeps the context across
  `inspect(doc)`). Out of territory (`mutate.py`, `families.py`,
  `objects.py`, possibly hot `versions/`); filed with a design-note DONE.
* **#251 — the ladder parses the schema twice per entry** (efficiency
  review, measured): `global_framing.reading()` calls `reading32(source)`
  (unmemoised `versions.schema_of`) then `bound(schema=schema_of(source))`
  (memoised, cold) → 2 opens + 2 parses ≈ 0.19 s; `census(G_ABPD)` 0.18 s →
  0.40 s in-process. Also filed there: `enter_own_release` should report the
  year it resolved (census re-runs `detect_release`, +0.6 ms) and be a no-op
  for a non-file source (each entry point here guards with
  `os.path.isfile`), and one documented key for the fallback sentence
  (today `release_note` here + famload + rvt_job, INFO `release` in
  validate, `framing.fallback` in rvt_analyze, `degradations` in the IFC
  manifest). `global_framing.py` is out of this PR's territory.
* `census()` on an input whose schema stream is unreadable cannot produce a
  census at all (`FamilyIndex` parses `Formats/Latest` for the class table),
  so `release_note` only appears on a file whose schema parses but lacks
  the framing classes — rare; the error `run()` records names the real
  cause. The library `render.inspect.inspect(path)` returns rows only, so a
  fallback taken there is not surfaced (the CLI prints it). Not widened.
* `census` JSON gains two additive keys (`release`; `release_note` when
  degraded); the text output for a healthy file of any release is
  unchanged. `run_certified` gains `reference_release` + `by_release`; the
  reference defaults to the release with the most accepted files read
  (later year on a tie, `LATEST_RELEASE` when none) rather than a hard-coded
  latest, so a future `LATEST_RELEASE` bump with no certified files of that
  year cannot silently empty the top-level tables (altitude review); it is
  printed and keyed, and `reference_release=` pins it.
* `rvt.render.inspect` still documents `CLASS_GELEMENT = 0x089E` /
  `CLASS_SERIALIZED_DUMMY = 0x0F2C` (2026 ordinals) in a comment block; the
  classifier is by class *name*, so they are documentation only. Left.
* Non-CFB input (a text file named `.rvt`): census → `ERROR
  NotOleFileError(...)` line; rvt_to_ifc → `ERROR: cannot read …
  NotOleFileError`, rc 2, manifest written; render.inspect / inventory /
  seed_audit → the pre-existing unguarded `NotOleFileError` traceback, rc 1
  — unchanged by this PR (same class as `rvt_analyze._identity` in #50), not
  filed separately: #252's reader objects are where a one-line guard belongs.
* CI cost: the `room2025` module fixture is 19 s of this file's 31 s, on
  both shard jobs (comparable to `test_edit_own_release`, 28 s). The DONE
  asks for exactly this build; sharing one session-scoped 2025 room across
  `test_famload_2025` / `test_go_target_version` / this file via a
  `tests/conftest.py` is a test-infra follow-up worth doing when a fourth
  consumer appears.
* `/simplify` (reuse / simplification / efficiency / altitude, four agents)
  ran before the closing commit. **Applied:** the route calls
  `_extract_intent` directly (no nested re-entry: 5 opens/4 parses → 4/3
  per conversion); `inventory.main` and `render.inspect.main` keep the body
  inline under the one `with` (no 3-/7-argument private helpers); one
  `os.path.isfile` rule decides whether there is a file whose release to
  enter (was four spellings); `run_certified`'s reference-release default
  and plain `sorted` years; docstrings trimmed to a cross-reference.
  **Skipped, with reasons:** reusing `provenance.reading_own_release` as the
  contextmanager (would import the provenance ledger into census/inspect and
  is circular for inventory — the `ExitStack` form is what famload /
  rvt_analyze standardised on); moving the guards / year / double parse into
  `global_framing` (#251, territory); a shared conftest room fixture (above).
* The base-branch red seen mid-stream (`tests/test_revit_kit.py` ×3 on
  `main@a0183b7`, #248) was fixed by #249 while this ran; rebased onto
  `main@21a9c49`, shard green (§BRANCH STATE).

## SUITE RESULT

Per `docs/inbox/SUITE-COORDINATION.md`: no full-suite run. Stream-local +
adjacent + the CI shard only. Expected full-suite delta: +22 tests; no
native-release behaviour change (2026 outputs byte-identical before/after).

## BRANCH STATE

* Branch `cam/121-readers-own-release`, cut from `origin/main@a0183b7`,
  rebased onto `origin/main@21a9c49` (after #249) before the closing push;
  PR `Closes #121`. Follow-ups filed: #251, #252 (`Refs #121`).
* Files: `src/rvt/census.py`, `src/rvt/render/inspect.py`,
  `tools/seed_audit.py`, `src/rvt/inventory.py`,
  `src/rvt/convert/rvt_to_ifc.py`, `tests/test_readers_own_release.py`
  (new, 22 tests), `tests/ci_shard.txt` (+1), this record, plus the 8
  `sync_plugin.py` mirrors listed in §2.
* Gates on the final diff: stream-local 22 passed; adjacent 63 passed / 41
  skipped; CI shard as CI runs it **553 passed / 31 skipped / 1 xfailed / 0
  failed** (190.8 s; was 3 failed on `test_revit_kit` before the rebase —
  #248, fixed on main by #249, not this diff); `sync_plugin.py --check` in
  sync; `validate_plugin.py` PASS 24; portable paths ok (2703).
* DONE check against #121: the five commands complete on the 2025 and 2024
  bases with the 2026 output shape, .ifc delivered with the manifest naming
  2025/2024, 2026 byte-for-byte unchanged ✓; each enters
  `global_framing.enter_own_release` once at the top, binds the own schema
  where it decodes (ADocument decoder + tokens via the ladder; object
  decoders were already own-schema), states the fallback sentence when
  degraded, restores constants (autouse fixture) and nests (test) ✓;
  `census()` self-wraps, the 2025 six-panel room reads 6/6 (6/6/6
  coherent), `run_certified` keeps releases apart via `reference_release` +
  `by_release` with the #50 caveat honoured and stated ✓; fresh-clone tests
  over the three bases per entry point in the shard, `sync_plugin --check`
  clean, this record with before/after transcripts ✓.
* Nothing staged for the viewer (read paths only — no output `.rvt` bytes
  change, so no certification round is implied); no assets, no zip
  committed; every `.ifc` ships with its stamps as before.
