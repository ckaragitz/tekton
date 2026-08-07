# Inbox — target-2024 (THE 2024 REGISTRY SLOT + VERSION GUARDS + THE THREE-RELEASE STORY) — 2026-08-04

Stream charter: add the guarded 2024 target (registry slot + version guards
+ CLI), extend the test pattern to 2024 with a self-arming finish line,
make the skill's version story honestly three-release, extend counsel C4 to
all three releases' corpora, sync + scan. DONE = guarded 2024 target +
tests + honest skill text + counsel C4 three-release + green sync/scan.

## 1. What shipped

### 1a. The 2024 registry slot (`src/rvt/frontdoor/assets/genesis_base.json`)

* `releases.2024` = the **B2024 lineage slot**: id `G_ABPD_2024`, reserved
  relpath `experiments/genesis/subst_k4_2024/compose/G_ABPD_2024.rvt`,
  `sha256: null`, `bytes: null`, `status: "pending certification"`, the
  same three-source certification requirement as 2025's (slot `certified` +
  slot sha256 pin + `KNOWN_RELEASES[2024].creation_certified`), and an
  honest `pending_reason` (the 2024 campaign has not certified a base yet;
  until it does, `--target-version 2024` = the 2026 build + the fallback
  line + the version-agnostic IFC addition — never a silent 2026 file
  presented as 2024). The lineage field cites verdict #28
  (`docs/inbox/genesis-audit.md`): the certified-2026 genesis recipe
  transfers wholesale across releases (the whole 2025 reduction lineage
  certified in ONE round), which is why a reserved 2024 slot is credible.
* NO code changes were needed in `src/rvt/frontdoor/base.py` — the slot
  machinery from the target-2025 stream (`release_years`, `release_slot`,
  `release_status`, `resolve_base(target_release=N)`, `BaseNotCertified`)
  is data-driven and picked the 2024 slot up as-is. Verified:
  `release_status(2024)` = pending certification / no sha256 /
  `slot_certified False` / `version_model_certified False`;
  `resolve_base(target_release=2024)` raises `BaseNotCertified`.

### 1b. `rvt.versions` — 2024 already mirrored 2025's creation shape; two honest generalizations

* `KNOWN_RELEASES[2024]` ALREADY carried `creation_certified=False` and no
  `genesis_base` (the versions stream built it that way — same shape as
  2025). Asserted by the new tests rather than re-declared; nothing to
  change in the table.
* `creation_status()`'s uncertified-release reason no longer reads as if
  only a 2025 plan exists: the pointer now says
  `docs/writer/genesis-2025-plan.md (the per-release campaign template --
  the recipe transfers across releases, genesis-audit verdict #28)`.
* The comment above `SUPPORTED_CREATION_RELEASES` notes the 2024 campaign
  mirrors the 2025 one.
* `creation_fallback_line()` needed NO change — it was already
  release-parametric; `creation_fallback_line(2024, 2026)` yields exactly
  `target 2024 requested: the 2024 base is pending certification; this
  file targets 2026 -- your Revit 2024 cannot open it; the IFC alongside
  is version-agnostic` (byte-asserted in the new tests).

### 1c. `tools/frontdoor.py` — the CLI gains 2024

`--target-version` choices `(2026, 2025)` → `(2026, 2025, 2024)`; metavar
and usage line updated; help text generalized ("2025 / 2024 = resolve that
release's genesis base when its campaign certifies; until then ... one
clear line ('target N requested: ...') ... never a silent 2026 file
presented as the target"). A year with no registry slot (e.g. 2023) stays
rejected at the CLI.

**Behavioral proof (live CLI, this session):** `author --prompt "a 400 A
distribution panel" --target-version 2024 --handoff-only` → exit 0,
summary prints `VERSION: target 2024 requested: the 2024 base is pending
certification; this file targets 2026 -- your Revit 2024 cannot open it;
the IFC alongside is version-agnostic`; `prompt_room.ifc` emitted beside
the handoff; `manifest.target_version` = `{status: fallback, requested:
2024, output_release: 2026, base_status.id: G_ABPD_2024, base_status.
status: "pending certification", ifc_addition: <path>}`;
`manifest.honesty.release` == the line (one story, no softer second one).

### 1d. Tests — `tests/test_target2024.py` (the 2025 pattern, third release)

12 tests. 11 run TODAY (all green): the version-model guard refuses 2024
with "Do NOT substitute a newer release"; the generalized fallback line is
byte-exact; `KNOWN_RELEASES[2024]` mirrors 2025's creation shape (flag
False, nothing falsely pinned, full read-side record intact); the registry
slot exists with the reserved relpath and reads pending / no sha256 /
per-source False; **the three-release story is coherent** (2026 certified;
2025 + 2024 each pending on its OWN campaign; registry and version model
agree release by release); `resolve_base(target_release=2024)` raises
`BaseNotCertified`; a 2026 `--base` with a 2024 target is refused
(`VersionError`); the CLI parses 2024 and rejects 2023; the front door
fallback delivers line+IFC (manifest json round-trip + `base_status`
asserted); the explicit-pinned-base (standalone) path still falls back
while a user's R5 base is refused. THE FINISH LINE
(`test_END_STATE_author_2024_produces_a_2024_file`) is `skipif(2024 not in
SUPPORTED_CREATION_RELEASES)` — it ARMS ITSELF when the 2024 campaign
flips the flag, and asserts: build completes, `detect_release(out) ==
2024`, BasicFileInfo build string present, `schema_of(out).sha256 ==
KNOWN_RELEASES[2024].schema_sha256`, `target_version.status == "match"`,
no fallback line. Every TODAY-test is conditioned on the flag (2024's AND
2025's where cross-asserted), so either certification day flips meaning
without breaking anything.

### 1e. Skill body (`plugin/skills/tekton-author/SKILL.md`; frontmatter untouched)

Step 0's version question now offers `{2026,2025,2024}` with honest status
per target: **2026 certified today**; **2025 in certification** (unchanged
text); **2024 guarded target, base not yet in certification** — slot
registered, campaign queued behind 2025, same honest degrade, the exact
2024 line quoted for verbatim relay; **older releases (pre-2024)** = same
degrade but no slot exists, the tool refuses the flag value and the
surface states the degrade itself. Flags list + report-order item 2 +
caveat 1 generalized to name both pending targets.

### 1f. Counsel C4 (`docs/product/COUNSEL-BRIEF.md`) — the three-release corpora

C4 retitled "(present in EVERY Revit file, **per release**, not sample
authorship)" and now states the per-release-constant law plus a table of
one pinned constant of each corpus per release, with pair counts / bytes /
sha256 (short form; full pins cited to `docs/writer/format-2025.md` §1/§3,
`docs/writer/format-2024.md` §1/§3, `experiments/genesis2024/
format_facts_2024.json`, `experiments/genesis2025/format_facts_2025.json`,
`rvt.versions.KNOWN_RELEASES`):

| release | Formats/Latest | ES unit-schema corpus |
|---|---|---|
| 2026 | 4,690 cls / 496,597 B / `6459a9a9…` | 1,315 pairs / 1,333,340 B / `99554c01…` |
| 2025 | 4,600 cls / 484,585 B / `c964f9aa…` | 1,174 pairs / 1,120,410 B / `5331797d…` |
| 2024 | 4,492 cls / 470,502 B / `0bfb947b…` | 1,161 pairs / 890,500 B / `f879bf3d…` |

Timing note: the charter said "poll for format-2024.md, else mark
pending" — the 2024 reduce stream landed `format_facts_2024.json` (23:13)
and `docs/writer/format-2024.md` DURING this stream, so C4 carries the
measured 2024 numbers, not a pending marker. A new ask (4) requests the
ruling state whether it applies uniformly across the three releases'
corpora. The scoped-to-2026 claims (341 descriptive strings; ~91% of a
minimal file) stay scoped to 2026 explicitly.

## 2. Gate results (pasted)

* `tools/sync_plugin.py` (final run): "synced 2 file(s); deny-audit clean;
  assets verified (genesis base == frontdoor pin); Validation passed;
  rebuilt tekton-plugin.zip (2793 KB)"; `--check` → "plugin in sync with
  source". (Run twice: sibling streams landed `src/rvt/genesis/port2024.py`
  and `src/rvt/genesis/y2025_b.py` between my first sync and the check —
  the second sync picked them up; the sync is a shared last-writer gate.)
* Zip constraint scan (both zips; script preserved below in §5): **HARD
  constraints PASS on both** — `tekton-plugin.zip` 295 members /
  `tekton-eval-kit.zip` 309 members; deny-listed member paths 0; banned
  raw-byte strings 0 (`rev-revit`, `anthropic`, `claude-cli-internal`);
  quarantined-content sha256 matches 0 (every member hashed against all
  quarantined sample files incl. samples/2023|2024|2025); unexpected
  `.rvt/.rfa` members 0 (plugin: the genesis asset only; kit: + the 8
  TEST-KIT files); nested zips 0; genesis asset sha256 == front-door pin
  (both); **SKILL.md frontmatter clean 5/5** (keys exactly
  {name, description}, name == folder, description non-empty, ≤1024 chars,
  no `<`/`>` — tekton-author desc_len 694); **plugin.json description 366
  ≤ 500**. HYGIENE (report-only): the 8 pre-existing `/Users/ck` hits,
  unchanged from target-2025 §3.1 (owners already notified there).
* Full suite: **see BRANCH STATE** (run after all edits; count pasted
  there). Stream-adjacent files verified green first:
  `test_target2024.py` + `test_target2025.py` 22 passed / 2 self-arming
  skips; `test_versions.py` + `test_frontdoor.py` +
  `test_frontdoor_standalone.py` + `test_bootstrap.py` 83 passed;
  `test_plugin_sync.py` 7 passed (after the re-sync).

## 3. Cross-territory notes

1. **APPLIED (required by my own change, minimal):**
   `tests/test_target2025.py::test_cli_flag_parses` asserted
   `--target-version 2024` exits with an argparse error — invalidated the
   moment the CLI legitimately gains 2024. Updated the rejected-year
   example to 2023 with a comment naming this stream. No other test in
   that file touched.
2. **APPLIED (adjacent doc describing the file I own):**
   `src/rvt/frontdoor/assets/README.md` per-release-slots paragraph now
   names the 2024 slot beside 2025's (one sentence extended).
3. **NOT applied — for the eval-kit stream:**
   `tekton-eval-kit/tekton-plugin/skills/tekton-author/SKILL.md` (and the
   kit's INSTALL/EMAIL/REPORT-CARD version framing, PDF) still carry the
   two-release story (`{2026,2025}`); the kit is refreshed wholesale from
   `tekton-plugin.zip` by its own stream — refresh at the next kit tick.
   The kit zip still HARD-PASSES the constraint scan meanwhile (version
   lag, not a violation).
4. **At the 2024 campaign's certification tick** the flip is DATA + one
   flag, mirroring target-2025 §3.2: `KNOWN_RELEASES[2024]`
   `creation_certified=True` + `genesis_base=<relpath>`;
   `genesis_base.json` `releases.2024` `sha256` + `bytes` +
   `status: "certified"` (relpath already reserved — update if the
   campaign lands the file elsewhere); packager bundles the 2024 base
   beside the 2026 one (`asset_mappings()`); nothing else —
   `tests/test_target2024.py`'s finish line arms itself, the TODAY-tests
   flip to their certified branches, `--target-version 2024` starts
   resolving the 2024 base, the fallback line disappears on its own.
5. **For the 2024 compose fleet (when it launches):** the reserved compose
   territory is `experiments/genesis/subst_k4_2024/` and the registry
   expects `compose/G_ABPD_2024.rvt` there (the 2025 fleet's layout,
   s/2025/2024/). This stream created NO files under experiments/ (the
   2025 fleet's `subst_k4_2025/` untouched, per charter).

## 4. Files touched (this stream)

* `src/rvt/frontdoor/assets/genesis_base.json` (the 2024 slot)
* `src/rvt/frontdoor/assets/README.md` (one sentence: 2024 beside 2025)
* `src/rvt/versions/__init__.py` (creation_status pointer generalized +
  SUPPORTED_CREATION_RELEASES comment; NO table/logic change)
* `tools/frontdoor.py` (--target-version choices/metavar/help + usage line)
* `plugin/skills/tekton-author/SKILL.md` (body only; frontmatter untouched)
* `tests/test_target2024.py` (NEW)
* `tests/test_target2025.py` (minimal cross-territory fix, §3.1)
* `docs/product/COUNSEL-BRIEF.md` (C4 three-release)
* `docs/inbox/target-2024.md` (this record)
* (plugin/** copies: via `tools/sync_plugin.py`, not by hand)

## 5. The zip constraint scan (reproducible)

Session scratchpads die with the session; the exact script run for §2 is
archived at `docs/inbox/results/zip_constraint_scan_target2024.py` (copied
from the scratchpad, byte-identical to the run). Invocation:
`.venv/bin/python docs/inbox/results/zip_constraint_scan_target2024.py`
(scans `tekton-plugin.zip` + `tekton-eval-kit.zip`, exits non-zero on any
HARD failure).

## BRANCH STATE

* Working tree: NOT a git repo (untracked files on disk under
  `/Users/ck/dev/things/tekton`); all edits as listed in §4. Parallel
  streams were landing 2024-campaign files (tools/genesis_2024.py,
  docs/writer/format-2024.md, experiments/genesis2024/**,
  src/rvt/genesis/port2024.py) and 2025-compose files (y2025_b.py) during
  this stream; none of my files was touched by them (mtimes verified
  before each edit), and my final sync includes their src/ state.
* Suite: FULL RUN **IN FLIGHT at record close** over the final tree —
  `.venv/bin/python -m pytest tests/ -q`, log at
  `/private/tmp/claude-502/-Users-ck-dev-things/91c616fc-3cee-49e7-be61-74bc4edd8fdb/scratchpad/suite-target2024.log`
  (read the log's last line for the count — do not retire this stream on
  anything else). Verified GREEN already, on the final code, before launch:
  `test_target2024.py` + `test_target2025.py` 22 passed / 2 self-arming
  skips; `test_versions.py` + `test_frontdoor.py` +
  `test_frontdoor_standalone.py` + `test_bootstrap.py` 83 passed;
  `test_plugin_sync.py` 7 passed. No file of MINE changed after the full
  run launched; sibling streams keep landing files (see next bullet).
* `tools/sync_plugin.py --check`: clean TWICE during this stream (after
  each of my syncs). At record close the check reports fresh drift on
  `lib/src/rvt/frontdoor/router.py` — a NEW sibling-stream file being
  edited live (not mine, not previously in the tree); its owner (or the
  integrator) runs the sync when it lands — the sync gate is a shared
  last-writer race under an active fleet. My four syncs this stream also
  carried sibling landings (port2024.py, y2025_b.py, genesis_2024 tool,
  compose_2025 test) into the plugin. Zip constraint scan: HARD PASS both
  zips (§2), run when the tree held all of MY final content.
* Behavioral proof: live `--target-version 2024` CLI run = fallback line +
  IFC addition + honest manifest (§1c).
* DONE per charter: guarded 2024 target ✓ (slot + guards + CLI + live
  proof); tests ✓ (11 today-green + self-arming finish line); honest
  skill text ✓ (three releases, each status stated); counsel C4
  three-release ✓ (measured pins for all three, incl. the just-landed
  2024 corpus); sync ✓ + scan ✓ green (twice, on my final content); FULL
  suite in flight (targeted + adjacent runs green: 112 passed / 2
  self-arming skips across the six stream-adjacent files; read the
  suite log's final line to close this box — the one remaining
  verification).
