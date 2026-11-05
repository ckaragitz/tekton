# self-battery — every declared family product × every release × every instrument (#796)

`Closes #796` · Refs #765 (S-2026-09-04-a), steer #1084, #838 (the 421 reference
families as the conformance corpus) · program goals PG1 / PG4 / PG7

Hard rule 4 frames everything below. Every instrument here is ours. "0 errors",
"conforms" and "deterministic" are facts about our bytes. None of them is evidence
that Revit opens or behaves with a file, and nothing in this record is a
certification claim.

## What was built

1. **`tools/self_battery.py`, rewritten.** The hand-written 27-row catalog is gone,
   because it broke DONE 1. The matrix is now **enumerated from what the engine
   declares**. `report.declarations` names each source and its counts.

   | source | what declares it | cases per release |
   |---|---|---|
   | `make_family` | Every **generator** subcommand of `tools/make_family.py`, read from its own argparse tree. A subcommand counts as a generator if it has an optional `--output` plus `--no-validate` and `--json`. Today that is panelboard, transformer, luminaire, device, fan-coil, fan-powered-box and panel-can. Axes are every option with `choices` and every `store_true` flag, plus luminaire `--size`. `--size` is the one free-text option, and `AXIS_SOURCES` binds it to `factory.held_troffer_sizes()`. The full product is used unless it exceeds 64 combinations; then each factor is varied one at a time. A non-generator that still takes `--output` is a **FAIL row** unless `NON_FAMILY_SUBCOMMANDS` says why it writes no family (today `load`, `load-device` and `loader`). | 46 |
   | `famspec` | `famspec.KINDS`. A kind is skipped here if it is already a make_family subcommand, or if its constructor is driven by another source (`archetype` → archetype; `generic_model` → part_shape + prism). Anything else must build bare or become a FAIL row. Today the only case is `downlight`, built and written by the famspec lane's own `build` / `write`. | 1 |
   | `archetype` | The #591 registry (`AR.keys()`). Each archetype gets its nominal, every standard size of its primary parameter, each boolean keyword of `make_archetype` (`solid`, `standards`, `nested_hardware`) flipped once, and the NEC working space where `working_space` is set (today `lighting_control_panel`). | 55 |
   | `part_shape` | `GENERIC_PART_SHAPES + COMPOSITE_SHAPES`, checked against the famspec schema's shape enum (a mismatch is a FAIL row). Each shape is built as one universal part that carries every field the schema declares for a part, × `work_plane` ∈ {level, vertical}. | 16 |
   | `prism` | The single-prism lane: the schema's two footprints (rectangle, ring) × its `prism_drive` enum, plus each boolean keyword of `make_generic_model` flipped once on the rectangle. | 10 |
   | `ifc_route` | Every tracked `inputs/ifc/*.ifc` through `router.route(…, "rfa", target_version=y)`. Every `.rfa` it writes becomes its own row (9 per release). A route that reports not-ok or raises is a FAIL row of its own, even when it wrote files. | 2 inputs |
   | `evidence` | Every family of every `family_set` recipe in `rvt.frontdoor.matrix.EVIDENCE_FORMS` (#984): the constructor and kwargs the matrix declares for the certified room's eight families. This is where the taxonomy's `house:` builder, the switchboard, is declared with buildable arguments. | 8 |
   | `taxonomy` | A **coverage check**, not a builder. Every build mechanism the MEP taxonomy declares (`famspec:` / `archetype:` / `house:`) must be driven by a source above, or it is a FAIL row naming the builder. Today all 16 mechanisms are covered. | 0 |

   **Releases.** A release runs if it is in `KNOWN_RELEASES` and is
   `creation_certified`. Its base must then resolve through
   `resolve_base(target_release=y)` to a pinned, certified base. A
   creation-certified release whose base does **not** resolve is a **FAIL row**
   (`release:base@Y`), never a silent skip. Today 2026, 2025 and 2024 run, and 2023
   is skipped ("not creation-certified").

   **Adding things needs no edit here.** A new constructor flag, choice, archetype,
   shape, schema field, taxonomy builder or release adds its cases on its own. The
   tests pin this:
   - adding an archetype or a device kind adds its cases;
   - a shape the schema does not declare becomes a FAIL row;
   - an uncovered taxonomy builder becomes a FAIL row;
   - an unexplained non-generator with `--output` becomes a FAIL row.

   The hand-written values are listed in the report. They are:
   - two literals the engine does not export, under `report.declarations.literals`: `work_plane` ∈ {None, "vertical"} and the universal part's numbers;
   - the routing tables `_DRIVES` and `OUTPUT_ONLY`;
   - the `NON_FAMILY_SUBCOMMANDS` allow-list.

2. **Instruments per case** (DONE 2). Each records `pass` / `fail` / `refused` /
   `skip` / `not_run` with a detail line:
   - **build** and **write**: inside that release's `release_build_context`; one context per case, exited before the read-back.
   - **release**: `detect_release` must equal the target.
   - **verify**: `verify_family_rfa`, read in the file's own release.
   - **validate**: `rvt.validate.validate_file(family=True)`, 0 errors required.
   - **provenance**: `provenance_scan_v2` (donor = that release's base) **and** `factory.provenance_scan`. Every check must pass, `identity_is_ours` included.
   - **law**: `constraint_law.check_file` on the family and on every nested family document it carries.
   - **conformance**: against the born corpus. It fails if any `question` is raised, if any record of the checked classes decoded only partly or not at all, **or if 0 rules were evaluated** (an inert check is a FAIL, not a pass).
   - **determinism**: the same case is built and written again under the same basename (#168), and the sha256 is compared. The rebuild runs in the **determinism twin**, a second long-lived Python process that differs from the parent in two ways:
     - it runs with another `PYTHONHASHSEED` (fixed at 796 when the parent's seed is random, the parent's seed + 1 otherwise);
     - its clock (`time.*` and `datetime.now`) runs **+400 d 1 h 1 min 1.5 s** ahead, past a year, hour, minute and second boundary.

     The twin re-enumerates the matrix and rebuilds the case by its id while the parent runs the read-back instruments. A case it cannot re-enumerate (a test's closure) is rebuilt in-process under the same clock shift, and the detail says which mode was used.

   An instrument that crashes is a FAIL, never a skip.

   **Aliases.** Every family case is written as `<slug>/a/battery.rfa`. The basename
   is part of the bytes, so it has to be identical across cases. A case whose bytes
   equal an earlier case of the same release is an alias. An alias **passes only
   if the alias pin `tools/self_battery_aliases.json` groups the two keys**. The pin
   holds 20 release-free groups and 25 relations, and it is regenerated from a full
   run with `--pin-aliases`. An unpinned alias is a FAIL on `build`: "the variant
   had no effect". A pinned group whose members are no longer byte-identical is
   reported as drift; that is a note, not a failure. The text summary lists every
   alias pair.

3. **Third state, `refused`** (DONE 4). A build is `refused`, not failed, **only**
   when it raises the port layer's named `PortabilityError` family (`Missing2025` /
   `Missing2024` / `Missing2023`). Everything else is a FAIL, and that includes
   `ReleaseContextError`, `BaseNotCertified` and `UnsupportedTarget`.
   `ReleaseContextError` is also raised for real defects: a context nested inside
   another, a base whose schema hash misses its pin, or a base whose release cannot
   be detected. The battery only runs releases whose certified base resolved, so
   the other two would be defects as well.

4. **Report** (DONE 3).
   - The JSON report is `out/self-battery.json` by default (`--report`), with a `.txt` summary beside it.
   - It gives totals, totals per release, a pass/fail/refused/skip/not_run table per instrument, **every failing tuple** (`{source, product, variant, release}` plus the instrument and a detail line), every alias pair, the determinism mode, and the alias pin in force.
   - Each row carries a `repro`: the make_family argv, the constructor kwargs, or the route call.
   - **Exit 1** when any case fails, any pinned probe fails, a corpus given with `--corpus` fails to mine (missing, empty or all-undecodable), or **nothing ran** (0 cases, for example an `--only` typo). An empty run is never a pass.
   - `main` restores `SOURCE_DATE_EPOCH` however the run ends.

5. **`--quick`** (DONE 5): the native release, every archetype at its nominal, all
   instruments, with the twin judging determinism. It runs in the CI shard through
   `tests/test_self_battery_796.py` (drop-in `tests/ci_shard.d/796-self-battery.txt`).
   Full mode is not in the shard.

6. **Pinned probes.** `_catalog()` and `_run_one()` keep the regression pins of lanes
   no declaration enumerates, and keep `tests/test_constraint_law_910.py` working
   unchanged:
   - the desktop-verified trapeze-from-prompt;
   - the one-box drive pair P/C (#907 / #910);
   - a multi-type panelboard (#163);
   - the #714 pset-drive plan.

   They run after the matrix in an unfiltered full run, the twin rebuilds them by
   key, they are listed under `report.pinned`, and they are never counted in the
   matrix.

## The conformance instrument defect (the only `src/` change)

**This was a defect in an instrument, not in engine output.** No family's bytes
change.

`rvt.famgen.conformance.mine()` had three problems:
- it globbed only `*.rft`;
- it opened each file under the session's native framing;
- it skipped, with `continue`, any file that failed to open.

On the 2025 `.rfa` reference corpus it would therefore have mined **0 files and said
nothing**. Measured as a control: our own 2025 family raises `unexpected Partitions
header` when read that way. Read inside its own release, it decodes.

Fixed in `src/rvt/famgen/conformance.py`:

- **`iter_objects(path, classes)`** decodes inside `enter_own_release`. It returns the release note, and it counts what did not decode instead of skipping it:
  - `undecoded_records`: the decoder raised;
  - `partial_records`: the decoder returned an object that is not `clean`. Such a record is **left out**: on the corpus side a field missing from a partial decode would read as "absent", and on our side it would go unchecked.
  - A third counter, `missing_records`, was dropped in review. Its ids come from the same seq-102 table the records are read from, so it was 0 by construction and was not a measurement.
- **`mine()`** now reads `*.rfa` and `*.rft`. A file that fails is counted in `failed` and `failure_types`; its path is kept in memory only and never serialized. The `Oracle` gains `attempted`, `fallbacks`, the two record counters, `releases`, and `classes_without_specimens()`.
  - `summary()` states `files/attempted` and every counter, names any requested class with 0 specimens, and prefixes `NOTHING MINED:` when the count is 0/N.
  - `to_json()` / `from_json()` give a cache form that holds no paths.
- **`check_file(path, invariants, stats=…)`** checks the **written** file, decoded in its own release, rather than the builder's in-memory document. The 2025 and 2024 port layers add fields the in-memory document never had.
- **`check_doc(…, stats=…)`** reports `elements` and `rules_evaluated`, so an inert check is visible.
- The old signatures still work, and `tests/test_conformance.py` is unchanged and still passes.

**The battery's cache.** The battery caches the mined invariants by a sha256 over:
- the corpus bytes;
- the miner's class list;
- **every `.py` of the `rvt` package**, so a decoder fix in `objects`, `families`, `global_framing` or any other module re-mines rather than reading a stale cache.

**On the corpus** (`samples/reference-families/`, git-ignored and quarantined; counts only):
- **421 / 421** files decoded, all of release 2025: 0 failed, 0 via a fallback rung, 0 undecoded records, 0 partly decoded, 0 missing.
- **478 invariants** over **11 classes**. `DBView` is requested but has 0 specimens, and the summary now says so.
- A fresh mine takes about 65 s; a cache hit takes under 1 s.
- The report carries only counts and the field names *our* files diverge on. It contains no corpus file names and no corpus values.

**Not inert.** On every checked file of the full run (329), at least 733 rule ×
element checks ran, and at most 29,896. No checked file of ours had a partly
decoded record.

## Review round: what the independent checks found and what changed

Two independent checks of the first cut (honesty and gates) found 10 problems and
one red gate. Each is fixed here, with a test.

| # | finding | fix | test |
|---|---|---|---|
| 1 | `refused` also covered `ReleaseContextError`, `UnsupportedTarget` and `BaseNotCertified`; a nested-context defect exited 0 | `REFUSALS` = the `PortabilityError` family only | `test_anything_but_a_port_refusal_is_a_failure` (×4) |
| 2 | a broken tracked base, a 0-case run, or an explicit `--corpus` that is missing or empty each exited 0 | a `release:base@Y` FAIL row; exit 1 on 0 cases or a failed explicit corpus | `test_a_broken_base_or_an_empty_run_fails`, `test_a_corpus_that_mines_nothing_or_is_missing_fails_when_asked_for` |
| 3 | the tests never ran a fail path: 13 of 16 mutations survived | tests that make each instrument fail: a 16-byte corruption fails verify and validate; a doctored constant, an inert check and a partial decode fail conformance; a failing scan fails provenance; a nested error fails law; a not-ok route fails | 21 mutations, all killed (below) |
| 4 | determinism compared two builds in one process, seconds apart | the twin process: another hash seed, clock +400 d 1 h 1 min 1.5 s | `test_the_twin_runs_on_another_hash_seed_and_a_shifted_clock`, `test_determinism_catches_a_build_that_reads_the_wall_clock` |
| 5 | the cache key ignored the decoder code | key covers every `.py` of `rvt` | `test_load_oracle_caches_by_corpus_bytes_and_decoder_source` |
| 6 | partly decoded records were observed as complete; `summary()` hid missing records and classes with 0 specimens | `partial_records` counted and left out; the summary names both | `test_partly_decoded_records_are_counted_and_left_out`, `test_a_requested_class_with_no_specimens_is_named` |
| 7 | the house switchboard was covered only by luck; a new non-generator with `--output` would vanish silently | the `evidence` source plus the `taxonomy` coverage check; unexplained non-generators with `--output` are FAIL rows | `test_every_declared_source_contributes_cases`, `test_an_uncovered_taxonomy_builder_is_a_failing_row`, `test_a_non_generator_with_output_must_say_why` |
| 8 | a variant that stops working became an "ok" alias | the alias pin; an unpinned alias FAILS; pairs are listed in the summary | `test_byte_identical_cases_are_aliases_only_when_pinned`, `test_the_alias_pin_names_enumerated_cases_only` |
| 9 | record accuracy: the field appeared in 52 rows, not 49; some follow-ups had no issue number | the numbers below; follow-ups filed below (#1085, #1086, #1087) or commented on their owners | — |
| 10 | `main` popped `SOURCE_DATE_EPOCH` and never restored it | restored in a `finally` | asserted in `test_a_broken_base_or_an_empty_run_fails` |
| gates | `tests/test_conftest_scaffolding.py` was red: the new test file entered a release context without the #707 leak guard | `pytestmark = usefixtures("no_release_leak")` with `release_leak_extra` = ladder + context constants, plus a module warm-up write; all 35 tests pass alone, too | the scaffolding test itself |

**Mutation check.** Each mutation below was applied alone to the tool or to
`conformance.py`, and then `tests/test_self_battery_796.py` was run. All 21 were
killed:
- verify, validate or provenance always returning pass;
- the law check skipping nested documents;
- conformance never raising a question, or passing when inert;
- partial records observed as complete;
- `load_oracle` accepting a corpus that mined nothing;
- a cache key without the corpus bytes;
- a not-ok route ignored;
- the working-space case dropped;
- `refused` widened, or never used;
- a broken base skipped;
- an empty run passing;
- `SOURCE_DATE_EPOCH` not restored;
- an unpinned alias accepted;
- the clock shift at 0;
- the twin inheriting the parent's hash seed;
- an uncovered taxonomy builder ignored;
- an unexplained `--output` subcommand ignored.

**Observation, not a defect.** A **single** flipped byte in a gzip payload is a
validator *warning* ("auto-repairable by CRCIO ECC; Revit repairs on load"), while
`verify_family_rfa` fails it. Both are right about different things: the validator
models Revit's ECC repair. The corruption test therefore flips 16 bytes, which is
past the proven repair envelope, and both instruments then fail.

## Full run (2026-11-05, worktree of `main` 793806d, the tool as in this change)

`tools/self_battery.py --out <scratch>/full2/rfa --report <scratch>/full2/battery.json`,
with a fresh corpus mine (a cache miss after the key change): **435 rows in 296 s**
on this machine, about 65 s of which was the mine. Exit code 1. The pinned probes
are not counted in the 435; see the review round below for their count after review.

| | 2026 | 2025 | 2024 | total |
|---|---|---|---|---|
| cases enumerated | 138 | 138 | 138 | 414 |
| rows (route cases expand to one row per written family) | 145 | 145 | 145 | 435 |
| aliases (all pinned, 0 drift) | 25 | 25 | 20 | 70 |
| distinct documents | | | | 365 |
| pass | 98 | 98 | 79 | 275 |
| **fail** | 22 | 22 | 46 | **90** |
| refused | 0 | 0 | 0 | 0 |

Rows by source: make_family 138, archetype 165, part_shape 48, prism 30, ifc_route
27, evidence 24, famspec 3. No taxonomy or release FAIL rows: all 16 taxonomy
mechanisms are covered and every base resolved.

| instrument (365 distinct documents) | pass | fail | not_run (build/write failed) |
|---|---|---|---|
| build | 331 | 34 | 0 |
| write | 329 | 2 | 34 |
| release | 329 | 0 | 36 |
| verify | 329 | 0 | 36 |
| validate | 329 | 0 | 36 |
| provenance (incl. `identity_is_ours`) | 329 | 0 | 36 |
| law (incl. nested documents) | 329 | 0 | 36 |
| conformance | 275 | 54 | 36 |
| determinism (all 329 in the twin: PYTHONHASHSEED 796 vs random, clock +400 d 1 h 1 min 1.5 s) | 329 | 0 | 36 |

Every file the battery could build was also written, read back, validated,
provenance-clean, coherent under the constraint law, and byte-identical when rebuilt
in another process under another hash seed and a clock 400 days ahead, at every
release. That includes the eight evidence families, the switchboard among them, at
2026, 2025 and 2024.

The 90 failures are **the same 90 (case, instrument, message) tuples** as the first
cut's full run (411 rows, 251 pass / 90 fail / 70 alias, with a cached oracle). An
independent re-run of that first cut with a fresh mine reproduced them exactly. The
new rows (24 evidence) all pass. The failures fall into five classes.

### Every failure class, and where it is tracked

Each class is filed, or measured onto the existing issue that already owns it.
The links and comments are dated 2026-11-05.

1. **`build` — `KeyError: "class 'ArcElemCell' not in the archive class map"` at 2024 — 34 cases.**
   - Affected tuples, all at 2024:
     - `archetype:conduit`: 12 (the nominal, 8 sizes, `solid=no`, `standards=no`, `nested_hardware=yes`);
     - `archetype:strut_trapeze`: 9 (the nominal, 5 strut lengths, the 3 flags; the rod is round);
     - `part_shape` cylinder, cylinder_x, cylinder_y, sphere, dome and cone, each × 2 work planes: 12;
     - `famspec:downlight`: 1.
   - It is raised in `genesis/types.py blank_object` ← `famgen/geometry.py _owned` ← `new_arc_curve_elem` ← `new_full_arc_curve_elem` ← `full_arc_cylinder_form`. Every family that carries a circle fails during **build** at 2024.
   - **#241** (open) names this KeyError for the downlight only. The battery measures its scope: every arc-bearing constructor. The *load* lane already raises the named `Missing2024` (#786). The build lane raises a bare `KeyError`, so by DONE 4 these are **fail**, not refused.
   - The IFC route still delivers a 2024 `.rfa` for the downlight IFC by degrading to the assembly lane.
   - **Tracked:** the measured scope is commented on **#241**, where the 34 cases widen the downlight to every arc-bearing constructor, and cross-referenced on **#786**. Until a 2024 twin exists, the minimum honest step is for the build lane to raise `Missing2024` by name, as the load lane does.
2. **`write` — `FileNotFoundError: family container source not found …` — 2 cases**, `famspec:downlight` at 2026 and 2025.
   - `famfrom_ifc.make_downlight().write_rfa` still defaults to the owner-machine vendor container instead of the bundled genesis base.
   - At 2024 the same case fails earlier, at build (class 1).
   - **Tracked:** this is **#94** DONE 1. It is commented there, and no new issue was filed.
3. **`conformance` — `ExtrusionElem.m_sideRefPlaneCurveBased` is False in ours and True on every born extrusion (2,161 / 2,161) — 52 rows.**
   - On **49** rows this is the failing question. They are:
     - at 2026 and at 2025, 19 each:
       - `make_family:fan-powered-box` × 6 variants;
       - `part_shape` box, cylinder, polygon, cylinder_x, cylinder_x vertical, cylinder_y, cylinder_y vertical, sphere, dome and cone;
       - `prism:rect prism_drive=none` and `prism:ring prism_drive=372`;
       - `ifc_route:chicago-plenum-downlight/Chicago_plenum_downlight`;
     - at 2024, 11: the 6 fan-powered-box variants, `part_shape` box and polygon, the same 2 prisms, and the IFC downlight. The circle shapes fail earlier at 2024 (class 1).
   - The **3** `prism:rect prism_drive=372` rows also carry this question; they are counted under class 4.
   - By lane, the 52 rows are: part_shape 22, make_family 18, prism 9, ifc_route 3. The fan-powered boxes carry 14–18 such questions each; sphere, dome and cone carry 3 each.
   - `rvt.famgen.drive_law` (#904 item 4) already sets the field to True, but only on **driven** forms. These lanes author undriven extrusions and keep False, because `geometry.py` sets False at both authoring sites.
   - **Filed: #1085**, "Undriven extrusions author ExtrusionElem.m_sideRefPlaneCurveBased True, as every born extrusion does" (refs #904 / #787). It is a single-variable probe, and per S-2026-09-04-a any desktop check is batched, not a click ladder.
4. **`conformance` — `Alignment.m_dimVersion` is 1 in ours and 6 on every born dimension (8,972) — 3 cases**: `prism:rect prism_drive=372` at 2026, 2025 and 2024.
   - Each file carries 5 questions (this one and `m_sideRefPlaneCurveBased`) and 8 notes. The notes are `CurveElem.m_constrInfo` / `RefPlane.m_constrInfo` filled, where the corpus has them always empty.
   - This is the **#372 chain**, which `drive_law` item 5 already names as differing from every born specimen.
   - **Tracked:** this is **#1076** (open), "retire the `'372'` options", and it is commented there. No new issue was filed.
5. **`conformance` — `FamilySymbol.m_refFaces` is empty in ours and non-empty on every born `FamilySymbol` (5,571) — 2 cases**: `archetype:strut_trapeze nested_hardware=yes` at 2026 and 2025. At 2024 the trapeze fails earlier, at build.
   - The two nested symbols, our own washer and hex-nut families (#917), carry no reference faces. The option is opt-in, off by default, and unverified on the desktop.
   - **Filed: #1086**, "Nested hardware symbols (washer / hex nut) carry FamilySymbol.m_refFaces, as every born FamilySymbol does" (refs #917).

One instrument follow-up is also filed, **#1087**: "rvt.famgen.factory exports
WORK_PLANES and the self-battery reads it". That removes one of the two battery
literals.

**Aliases (70, all pinned, 0 drift) are not failures**, and each one is by design:
- `troffer` ≡ `recessed-troffer` and `downlight` ≡ `recessed-downlight`;
- `--size` on a downlight (size is a troffer axis);
- `nested_hardware=True` on a non-trapeze, which only adds a note (factory: "never a refusal");
- `work_plane=vertical` on a non-run shape (a note, on the Ref. Level);
- `prism:rect drive=yes` and `settle_drives=yes` ≡ the default law prism;
- `prism:ring prism_drive=None` ≡ `'372'`, because the 372 chain only applies to a rectangle.

2026 and 2025 show all 25 pinned relations. 2024 shows 20, because five pairs
involve a circle shape or the conduit, and those fail at build there.

**Observation, not filed:** `famspec.validate({"kind": "generic_model"})` returns no
problems, yet the constructor refuses it by name ("needs a positive height_ft").
famspec documents that its constructors refuse bad values by name, so this is the
intended split. The battery does not build a bare `generic_model`, because the
part_shape and prism sources drive that constructor.

## Independent review of #1088 (head `02840eb`), and what changed

The review had four lenses: instrument honesty, the conformance module, tests and CI, and rules and the record. Skeptics then re-checked each blocking candidate. It found two real defects and a set of guards worth carrying.

| # | finding | fix | test (R1–R5, R7 and R8's tests fail on `02840eb`; R10's are guards of behaviour that was already right) |
|---|---|---|---|
| R1 | **`refused` was granted to the base `PortabilityError`.** A bare one is raised for our own encoder gaps: "unsupported field kind", a drifted 2023 pin, an id that does not fit 32 bits. So a writer change the 2024/2025 adapters cannot express would have turned every case into a "known-good refusal" and stayed green. One skeptic upheld this; another called it hardening, because no case hits it today. | `REFUSALS` = the named `Missing2025` / `Missing2024` / `Missing2023` only | `test_anything_but_a_port_refusal_is_a_failure[PortabilityError]`, `test_every_named_missing_class_refuses` |
| R2 | **A stale file passed every instrument.** `produce()` checked only `os.path.isfile(path)`. A file left by an earlier run (fixed `--out`, `--keep`) let a writer that wrote nothing pass `write`, every read-back instrument and determinism. | `produce` removes `path` first; `_run_family` removes the case directory (`a/` and the twin's `b/`) before building | `test_a_stale_file_from_an_earlier_run_is_never_graded` |
| R3 | A hung twin hung the whole battery, because `readline()` had no deadline | a reader thread and `collect(timeout)`, `TWIN_TIMEOUT_S` = 600 s. On expiry the twin is killed, restarted for the next case, and that case's determinism FAILS. | `test_a_hung_twin_fails_determinism_instead_of_hanging` |
| R4 | A file of ours read on a fallback rung (its own schema did not resolve its release) passed `verify` and `conformance` with only a note | both now FAIL it: our output must name its release itself | `test_a_file_of_ours_read_on_a_fallback_rung_fails_verify_and_conformance` |
| R5 | A corpus that mined only partly (some files failed) was `ok` | state `partial`: its invariants are used, the run exits 1, and the summary says PARTIAL | `test_a_corpus_that_mines_only_partly_fails_the_run` |
| R6 | `missing_records` was 0 by construction: the ids come from the same seq-102 table, so it was not a measurement | dropped, along with the dead `o is None` branch | the summary assertions |
| R7 | The cache round trip compared only invariants and three counters; `to_json` returned `stats` by reference | the test compares `summary()`, `releases` and `failure_types`; `to_json` returns a snapshot | `test_the_oracle_cache_form_round_trips_and_carries_no_path` |
| R8 | `make_family proofs` writes families with no `--output`, so it slipped past the declaration check | the check covers any subcommand that takes `--output` **or** `--no-validate`; `proofs` is listed with its reason (the panelboard / transformer / luminaire generators run the same constructors) | `test_a_non_generator_with_output_must_say_why` |
| R9 | The rewrite dropped the old catalog's mixed multi-part family and the 600 A panelboard | both restored as pinned probes | the full run below |
| R10 | No test made `release`, `write`, route determinism, a failing pinned probe or an unpinned base fail | tests for each; the exit rule is one function, `exit_code` | `test_the_release_and_write_instruments_can_fail`, `test_route_determinism_fails_when_the_second_run_differs[...]`, `test_the_exit_code_fails_on_every_failure_kind`, `test_an_unpinned_or_uncertified_base_is_broken_not_skipped`, `test_records_the_decoder_cannot_read_are_counted_and_fail_conformance` |
| R11 | Record hygiene: the drop-in said "~7 s" (measured about 14 s), the shard evidence did not name its head, and the territory exception was not stated | corrected here and in BRANCH STATE | — |

**Territory.** #796 says the battery is read-only on `src/`. The one exception is `src/rvt/famgen/conformance.py`, the instrument the battery reads. It is taken under steer #1084 because the instrument mined a silent zero. No engine output changes.

**After the fixes**, a full run on the fixed tool with a fresh mine gives **the same 435 rows: 275 pass / 90 fail / 0 refused / 70 alias**, in 294 s, with the corpus mined 421/421.
- No case was hiding behind the wider refusal rule: the 34 build failures are `KeyError`s, not port refusals.
- No file of ours needed a fallback rung.
- The **7 pinned probes give 6 pass, 1 fail**: the restored `shape_mixed_assembly` fails conformance on `ExtrusionElem.m_sideRefPlaneCurveBased`, which is class 3 below, fixed by #1085. That is the restored probe working, not a new defect.

## Quick mode (the CI shard)

`tools/self_battery.py --quick --no-corpus`, measured on 2026-11-05: **7 cases** (one
per archetype) at **2026**. Result: **7 pass, 0 fail**, every instrument passing, and
determinism judged by the twin. It takes about 4 s. With the corpus it takes about
65 s on a cache miss, and about 4 s afterwards.

## Limits

- The battery builds each **declared** axis. It does not build every *value* of a free-numeric option, such as `--mains`, `--kva` or inch dimensions; those are pinned by catalog and constructor tests. Catalog-member sweeps (every held variant of every vendor line) are not enumerated. That would be a further source, bounded by the same `MAX_PRODUCT` rule.
- **Conformance is a question, not a verdict.** The corpus is one release (2025) and one family population (the reference set, about three quarters electrical rough-in, #838). A CONSTANT the corpus never varies may still be legal for another kind of family.
- In-process rebuilds (only for cases the twin cannot re-enumerate, such as test closures) shift the `time` module's clock but not the hash seed or `datetime`. Every matrix case and pinned probe goes through the twin.
- Nothing here exercises Revit (hard rule 4). The battery narrows where to look and makes desktop rounds rare and batched (#765). It never replaces them.

## Open questions

- Should a conformance `question` fail a case, or only be listed? This record treats it as a FAIL, so a divergence cannot hide in a green total (#805 "zero issues"). Classes 3–5 are the result.

## BRANCH STATE

- **Files:**
  - `src/rvt/famgen/conformance.py` — the instrument fix; no engine output changes.
  - `plugin/lib/src/rvt/famgen/conformance.py` — mirror, regenerated by `tools/sync_plugin.py`.
  - `tools/self_battery.py` — rewritten.
  - `tools/self_battery_aliases.json` — new: the alias pin (20 groups, 25 relations; our own case keys only).
  - `tests/test_self_battery_796.py` — new: 49 tests, about 14 s, under the #707 leak guard.
  - `tests/ci_shard.d/796-self-battery.txt` — new.
  - this record.
- **Gates:**
  - `pytest tests/test_self_battery_796.py tests/test_conformance.py tests/test_constraint_law_910.py tests/test_conftest_scaffolding.py tests/test_plugin_sync.py`: 106 passed, 1 skipped. The skip is the old `samples/rft` test; there is no `samples/rft` here. This was re-run on the trunk checkout. There, `make_family_module()` first had to put `tools/` back on `sys.path`, because the test file pops it after importing the battery; it now does, and the run is plain `pytest` from the repo root.
  - Each of the first cut's 35 tests also passed when run alone, under the guard (re-checked by the review in reversed order and with `PYTHONHASHSEED=0`).
  - After the review round: `tests/test_self_battery_796.py` 49 passed; `tests/test_conformance.py tests/test_constraint_law_910.py tests/test_conftest_scaffolding.py tests/test_plugin_sync.py tests/test_bootstrap.py tests/test_coldstart.py` 94 passed, 1 skipped.
  - `tests/test_bootstrap.py tests/test_coldstart.py`: 23 passed.
  - `tools/sync_plugin.py`, then `--check`: rc 0, in sync (deny-audit clean, identity scan == allowlist).
  - `plugin/scripts/validate_plugin.py`: PASS.
  - `tools/dev/check_portable_paths.py`: ok.
  - Full CI shard (`shard_list.py --print`, `RVT_SKIP_LARGE=1`):
    - In the worktree, on the first cut plus its leak-guard fix: rc 0, 6631 passed, 156 skipped, 11 xfailed in 1071 s. The first cut's very first shard run had 1 failure, the missing leak guard (fixed above).
    - The tech-lead sandboxed CI on head `02840eb`: rc 0, **6658 passed, 152 skipped, 11 xfailed** in 1072 s.
    - The review-round head is re-run by the same sandboxed CI before merge.
  - `tools/self_battery.py --quick`: 7 / 7.
  - Full run: 435 rows, 275 pass / 90 fail / 0 refused / 70 alias, with every failure class listed above. Re-run after the review round: identical, and pinned 6/7 (the one fail is class 3, #1085).
- **Not done here:**
  - Engine findings are deliberately not fixed. #796 makes the battery read-only on `src/`, apart from the instrument.
  - The follow-ups above are filed or commented:
    - #1085 (`m_sideRefPlaneCurveBased`);
    - #1086 (`m_refFaces`);
    - #1087 (`WORK_PLANES`);
    - the measured scope on #241 / #786, #94 and #1076.
- **Staged / shipped:** nothing staged for the viewer.
