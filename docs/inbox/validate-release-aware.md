# validate-release-aware — the validator judges every file under its OWN release (issue #50)

Stream: cleanup session follow-up, 2026-08-09 (cloud, fresh clone). Charter
(#50): `tools/rvt_validate.py` / `rvt.validate.validate_file` and
`tools/rvt_analyze.py` must read a 2025 / 2024 / 2023 file with *that*
release's framing ordinals, so the certified pinned bases stop reporting
spurious errors. Territory: `src/rvt/validate.py`, `tools/rvt_analyze.py`,
new `tests/test_validate_release.py`, `tests/test_rvt_analyze.py` (+2
tests), `tests/ci_shard.txt` (+2 lines), this record, regenerated mirror
`plugin/lib/src/rvt/validate.py`. No hot files (`src/rvt/versions/` is only
*called*; what it should grow is written down below as follow-ups).

## The defect (found while verifying #44 from a fresh clone)

The canonical validator CLI was release-blind: `rvt.partitions` carries the
2026 framing ordinals as module constants and nothing on the CLI path
activated the file's own. Every Revit 2025/2024 file — including the
certified, viewer-accepted bases we ship — came back `FAIL`:

| input (tracked, certified) | before | after |
|---|---|---|
| `plugin/assets/genesis/G_ABPD.rvt` (2026) | OK, 0 errors / 1 warning | OK, 0 / 1 (unchanged) |
| `plugin/assets/genesis/G_ABPD_2025.rvt` | **FAIL, 4 errors** (`unexpected Partitions header: v=9 cls=0x391`, walker ×2, `PartitionTable class ordinal 0xc40`) + 1 warning ("not the canonical Revit 2026 schema") | **OK, 0 errors / 0 warnings**, info `canonical Revit 2025 archive schema (byte-identical)` |
| `plugin/assets/genesis/G_ABPD_2024.rvt` | **FAIL, 4 errors** (`cls=0x37b`, `0xbec`) + 1 warning | **OK, 0 / 0**, info `canonical Revit 2024 …` |

`tools/rvt_analyze.py` had the same blindness twice over: its `validation`
section inherited the 4 errors, and its `census` section silently became
`{"error": …}` on any non-2026 file (the text report just omitted the
census lines) while the `release` line above it correctly said 2025.

The front door was never affected (`release_ctx` validates inside
`V.reading(base_path)`), which is exactly why the CLI verdict and the
front-door verdict disagreed on the same bytes — an instrument defect, not
a file defect (CLAUDE.md §4 evidence discipline: fix the instrument, don't
reinterpret the reading).

## What was built

* `src/rvt/validate.py`
  * New public helper `enter_own_release(stack, path)` puts the file's OWN
    release framing in force on an `ExitStack` via a three-rung ladder:
    (1) `rvt.versions.records32.reading32(path)` — the documented "read ANY
    release correctly" entry (own framing ordinals from the file's own
    `Formats/Latest`, by name; plus the 32-bit record layer iff the schema
    declares `Identifier` v1, i.e. ≤ 2023); (2) if the schema cannot settle
    it (damaged / truncated schema stream), `detect_release(path)` +
    `reading(year=…)` — the pinned table of the release `BasicFileInfo`
    declares, so a damaged 2025 file is still judged as a 2025 file;
    (3) nothing (non-CFB / unknown release) — the built-in latest-release
    constants. It returns `None` when the schema resolved it, else one
    sentence naming the rung and the cause; it never raises.
    `validate_file()` runs the `Validator` inside it and records that
    sentence as an INFO finding `[structure] release: …`; the real cause is
    still the ERROR the structure layer already reports. Constants are
    restored on exit; nest-safe inside a caller's own `reading` (front
    door, parity). Rung 2 exists because verification showed rung 1 → 3
    alone mis-describes a truncated 2025 file: `reading32` raises
    `VersionError("schema lacks the partition-framing classes …")`,
    `versions.framing_for` deliberately re-raises `VersionError` rather than
    falling back, and the file was then read with 2026 ordinals — 12 errors
    of which 2 were fiction (`unexpected Partitions header: v=9 cls=0x391`,
    `PartitionTable class ordinal 0xc40`) and 0 blocks walked. With rung 2:
    11 errors, all real (truncation), 4 blocks / 3317 records walked.
  * The schema identity note is release-aware: sha256 of the inflated
    schema is looked up in `rvt.versions.KNOWN_RELEASES` →
    `canonical Revit {year} archive schema (byte-identical)` (the 2026
    string is byte-for-byte the old one); anything else is one WARNING
    naming the pinned releases it was compared against. The private
    `SCHEMA_2026_SIZE/_SHA256` copies in `validate.py` are gone — the
    single source of truth is `KNOWN_RELEASES` (`frontdoor/standalone.py`
    keeps its own constant, untouched, used by its tests).
  * The block-trailer error message names the trailer tag actually in force
    for the file (`partitions.TRAILER_TAG`, read live) instead of a
    hard-coded `0x0f21`; module + `validate_file` docstrings state the
    own-release rule generically ("any release, pinned or not") and the
    degradation. `REQUIRED_STREAMS`' comment still says "Revit-2026 stream
    inventory" — left, it is a statement about where the list was mined.
* `tools/rvt_analyze.py`: the file's own release is entered **once per
  file** through the same `enter_own_release` ladder — `census`,
  `validation` and `provenance` all run inside it (validation re-enters it
  harmlessly via `validate_file`). Whenever the schema did not settle the
  framing the report grows a `framing: {"fallback": "<sentence>"}` key and
  the text report prints `framing : <sentence>`; a census failure is now
  printed as `census : ERROR …` instead of the census lines silently
  disappearing. The census dict-shaping moved into a `_census(path, top)`
  section helper like its siblings. #50's body said analyze needed no
  change of its own; the silent census failure was found while fixing and
  is the one deliberate widening of territory (tools/, not hot, not
  mirrored into the plugin).
* `tests/test_validate_release.py` (7 tests, fresh-clone runnable on the
  tracked bases): 2026/2025/2024 bases → `ok`, 0 errors, the right
  `canonical Revit {year}` info, no fallback finding, `rvt.partitions`
  constants back to the latest-release values (autouse fixture keyed on
  `framing_table(LATEST_RELEASE)`); CLI `main([2025, 2024, "--quiet"]) == 0`;
  nested inside `V.reading(year=2025)` the outer ordinals survive; a
  64 KiB truncation of the 2025 base (built in `tmp_path`) → `release`
  INFO naming the "Revit 2025 framing table" and no `cls=0x…` /
  "class ordinal" errors (rung 2); a non-CFB temp file → report with the
  container ERROR + the "not resolved" `release` INFO, no exception (rung 3).
* `tests/test_rvt_analyze.py` (+2): the 2025 base analyzes coherently
  (release 2025, no `framing` key, census without error, validation VALID);
  a monkeypatched unreadable schema on the 2026 base → `framing.fallback`
  names the cause and the "Revit 2026 framing table" rung, and the census
  still runs. Both files added to `tests/ci_shard.txt` (8 → 10 files;
  `test_rvt_analyze.py` was fresh-clone runnable already but not in the
  shard).

## Evidence

* Stream-local: `tests/test_validate_release.py` + `tests/test_rvt_analyze.py`
  **14 passed** (14.2 s) on the final diff.
* CI shard (`tests/ci_shard.txt`, now 10 files, `RVT_SKIP_LARGE=1`):
  **103 passed, 23 skipped** (sample-dependent skips), 33.3 s, on the final
  diff. Earlier in the stream, before the analyze restructure:
  `tests/test_frontdoor_standalone.py` + `tests/test_census.py` 15 passed,
  7 skipped (neither file touched since).
* **Runtime verification at the CLI surface (before = a worktree of
  `origin/main@5c5242e`, same venv, same tracked bases; after = this
  branch).** `tools/rvt_validate.py G_ABPD.rvt G_ABPD_2025.rvt G_ABPD_2024.rvt`:
  before → 2026 VALID (1 warning), 2025 **INVALID 4 errors** + "not the
  canonical Revit 2026 schema" warning with `partition_blocks: 0 records: 0`,
  2024 **INVALID 4 errors** (`cls=0x37b`, `0xbec`), exit 1; after (older
  releases first, to exercise the restore) → 2025 VALID 0/0,
  `partition_blocks 15, records 9951, elements_decoded 3316, refs_checked
  50759`; 2024 VALID 0/0, `records 9837, elements 3278, refs 40579`; 2026
  VALID with the identical single warning; exit 0. `--json` on the 2025
  base: `ok: true`, findings = INFO `RevitPreview4.0: optional stream absent`
  + INFO `Formats/Latest: canonical Revit 2025 archive schema
  (byte-identical)`. `tools/rvt_analyze.py G_ABPD_2025.rvt --top 5`: before
  → no census/families/coherence lines at all, `INVALID (4 errors, 1
  warnings)`, exit 1; after → `census : 3316 host records in 145 classes`,
  `families : 8 host families`, `coherence : OK`, `VALID (0 errors, 0
  warnings, project mode)`, exit 0.
  Probes: (a) a 380-byte non-CFB file → `rvt_validate` INVALID, 1 error
  `container: not an OLE2/CFB compound file`, INFO `release: own-release
  framing not resolved (NotOleFileError: …); checked against the built-in
  latest-release constants`, exit 1; `rvt_analyze` still dies in the
  (pre-existing, unguarded) `_identity` section with `NotOleFileError`,
  exit 1 — unchanged, out of scope. (b) the first 64 KiB of the 2025 base
  → with only rungs 1+3: 12 errors incl. the two fictitious 2026-framing
  ones, 0 blocks; with the ladder: INFO `release: own schema unreadable
  (VersionError: …); checked against the pinned Revit 2025 framing table
  (the release BasicFileInfo declares)`, 11 real errors, `partition_blocks
  4, records 3317`, exit 1; `rvt_analyze` prints the same sentence on its
  `framing :` line, `census : ERROR ValueError("'Formats/Latest': no gzip
  members …")`, validation INVALID 11. (c) the three bases re-run after the
  ladder change: unchanged (OK/OK/OK, exit 0); `rvt_analyze
  G_ABPD_2024.rvt --no-census` → release 2024, schema release 2024, VALID.
  No `.claude/skills/verify/SKILL.md` was written to persist this recipe:
  CLAUDE.md §3b says the repo intentionally has no `.claude/skills/`; the
  recipe is the paragraph above (drive `tools/rvt_validate.py` /
  `tools/rvt_analyze.py` on `plugin/assets/genesis/*.rvt`, compare against
  a `git worktree` of `origin/main`). If the owner wants a project verify
  skill despite that convention, it is a one-file follow-up.
* Gates: `tools/sync_plugin.py` → synced 1 file (`plugin/lib/src/rvt/validate.py`),
  deny-audit clean, validation passed, zip rebuilt (not committed);
  `--check` → "plugin in sync with source"; `plugin/scripts/validate_plugin.py`
  PASS (23 assertions); `tools/dev/check_portable_paths.py` ok (2628 paths).
* Cost (measured, same process, warm, median of 3 on `G_ABPD.rvt`): bare
  `Validator.run` 0.49 s → `validate_file` 0.60 s. The +0.11 s is one extra
  container open + schema parse inside `reading32`'s `schema_of`; the
  validator parses the schema again lazily for the semantic layer. Sharing
  the one parse was reviewed and **not** done here: it needs either
  re-implementing `reading32`'s body inside `validate_file` (exactly the
  duplication noted below in `versions/parity.py`) or a `versions/` API
  change (`reading32(source, schema=…)` passthrough, or yielding the parsed
  schema) — a hot-file follow-up, listed below.

## Findings / open questions (proposed follow-ups, not done here)

* **census stays release-blind when called bare.** `rvt.census.census()`,
  `run()`, `run_certified()` / `python -m rvt.census [--certified]` and
  `FamilyIndex.open()` still read with whatever ordinals are active; only
  `validate_file`, `rvt_analyze`, the front door and parity enter the
  file's release. Making `census()` self-wrap like `validate_file` is two
  lines but was deliberately deferred: today `run_certified()` *errors* on
  the older-release certified files and thereby (accidentally) keeps them
  out of the mandatory-set computation; making it succeed silently changes
  what `--certified` reports (class inventories differ per release). That
  wants its own issue with that caveat stated, not a rider on this PR.
* **`versions/` (hot) follow-ups, patch-in-record:**
  (a) give `records32.reading32` the same degrade ladder `framing_for` has
  (schema by name → detected-year table → built-in) plus a `schema=`
  passthrough / yield, so callers stop paying a second parse and stop
  hand-assembling `reading(path, schema=…)` + `ids32()` —
  `versions/parity.py:140-161` does exactly that before calling
  `validate_file`, which now nests its own `reading32` (results identical,
  one redundant `schema_of` ≈ 0.1 s/file parity can drop);
  (b) the docstring examples at `versions/__init__.py:480-481` /
  `versions/records32.py:72-73` still show `with reading(path):
  validate_file(path)` — now an unnecessary (harmless) wrapper.
* The same "pinned to 2026" smell exists, untouched, at
  `src/rvt/frontdoor/standalone.py:95` (`SCHEMA_2026_SHA256`) and
  `src/rvt/famgen/factory.py:1239` (`FORMATS_LATEST_SHA256_PREFIX`,
  hot-swapped per release by `frontdoor/release_ctx.py:403-405`); both work
  today because their callers set the release context — candidates for the
  same `KNOWN_RELEASES` treatment when someone is in those files anyway.
* The E1–E3 corpus laws and `REQUIRED_STREAMS` are still described as the
  "Revit-2026 inventory"; they hold unchanged on the 2025/2024 bases (0
  findings), so no release split was needed today.
* Longer-term altitude note from review: readers that self-activate the
  file's release (as `validate_file` now does) engine-wide would retire all
  of the above wrappers; that is a `versions/`-owned design change, not a
  validator fix.
* `/simplify` review (reuse / simplification / efficiency / altitude, four
  agents) ran before commit. **Applied:** `try` in `validate_file` narrowed
  to the context entry only (an import failure in `records32` must stay
  loud, not become the silent 2026 fallback this PR removes), single
  return, module docstring de-duplicated against `validate_file`'s, test
  assertions de-tautologised with the autouse "constants restored"
  fixture, per-file (not per-section) release entry in `rvt_analyze` with a
  stated `framing` degrade, generic release wording, live `TRAILER_TAG` in
  the trailer message. **First skipped, then applied on evidence:** the
  altitude note asked for a middle fallback rung; it was initially parked
  as "belongs in `reading32`", but the truncated-2025 verification probe
  (Evidence, probe b) showed the user-visible cost of not having it, so it
  landed here as `enter_own_release` — in `validate.py`, shared by
  `validate_file` and `rvt_analyze`, using only public `versions` calls
  (`detect_release`, `reading(year=)`), no hot-file edit. Moving the ladder
  down into `reading32` itself remains the `versions/` follow-up (a) above.
  **Skipped, with reasons:** swapping the public `KNOWN_RELEASES` scan for
  the private `versions._SCHEMA_SIGNATURES` map (same 4-entry table; a
  private import buys nothing); `detect_release_from_schema` for the
  identity note (its size-only fallback would make "byte-identical" false);
  sharing the parsed schema (efficiency, see Cost — hot-file API); the
  `census()` self-wrap (belongs in a census issue, reasons above).

## BRANCH STATE

* Branch `claude/team-status-check-ezhl90`, rebased on `main@5c5242e`
  before push; PR closes #50.
* Files: `src/rvt/validate.py`, `tools/rvt_analyze.py`,
  `tests/test_validate_release.py` (new, 7 tests), `tests/test_rvt_analyze.py`
  (+2 tests), `tests/ci_shard.txt` (+2 lines),
  `docs/inbox/validate-release-aware.md` (this), regenerated
  `plugin/lib/src/rvt/validate.py`.
* Gates green as listed above (`sync_plugin.py` synced 1 file + `--check`
  in sync, `validate_plugin.py` PASS 23 assertions, portable paths ok 2628,
  stream-local 14 passed, shard 103 passed / 23 skipped); nothing staged
  for the viewer (read-path only — no output bytes change, so no
  certification round is implied).
* Shipped vs staged: everything in the PR; no experiments, no assets, no
  zip.
