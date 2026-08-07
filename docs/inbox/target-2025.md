# Inbox — target-2025 (VERSION-TARGETED FRONT DOOR + THE 2025 PRODUCT PATH) — 2026-08-04

Stream charter: wire the version model into the front door; make the 2025
story honest end to end (skill, kit, tests); leave the finish line
executable so G25-5 flips it on with data, not code.

## 1. What shipped

### 1a. `--target-version` through the whole front door

* `tools/frontdoor.py author --target-version {2026,2025}` (choices
  enforced; help text carries the honest 2025 story). The CLI summary
  prints a `VERSION:` line whenever a target was requested — the fallback
  line verbatim when the target is pending.
* `rvt.frontdoor.AuthorRequest.target_version` + route wiring
  (`_resolve_base_and_version`, `src/rvt/frontdoor/__init__.py`) with FOUR
  reachable states, all recorded in `manifest.target_version`:
  - `unspecified` — no target given; output targets the certified default
    (2026); manifest says so and points at `--target-version`.
  - `match` — target's base certified + resolved (2026 today; 2025 the
    moment its slot pins). The resolved base is release-checked
    (`rvt.versions.require_release`) — a mispinned slot cannot slip through.
  - `fallback` — target pending certification: the 2026 build is DELIVERED
    (deliverable rule), plus **THE line** (see 1c), plus the
    **version-agnostic IFC addition** (see 1d). Exit code stays 0.
  - `refused` — a user-supplied `--base`/`$RVT_GENESIS_BASE` whose release
    != the target (never author a wrong-release file while promising the
    target), or an unresolvable default base.
  - Standalone nuance: the plugin's `author_standalone` passes the BUNDLED
    base as an explicit `--base`; when that explicit file is byte-for-byte
    the pinned default (sha256 == pin) a wrong-release target degrades to
    `fallback` (it is the default arriving via a path, not a user
    override) — any other wrong-release base stays `refused`. Both paths
    are tested.
* `--rvt` (edit) route: `--target-version` yields an honest
  `target_version` block too — an edit PRESERVES the input file's release;
  a 2025 target on a 2026 input gets its own clear line (no IFC pretence).

### 1b. The base registry gained the per-release slots

* `src/rvt/frontdoor/assets/genesis_base.json` → new `"releases"` section:
  `2026` = the certified default (G_ABPD); `2025` = the **B2025 lineage
  slot** (`G_ABPD_2025`, reserved relpath
  `experiments/genesis/subst_k4_2025/compose/G_ABPD_2025.rvt`, `sha256:
  null`, `status: "pending certification"`, pending_reason + certification
  requirements spelled out).
* `src/rvt/frontdoor/base.py`: `GenesisPin.release_years()/release_slot()`,
  `release_status(year)` (certified ONLY when THREE sources agree: slot
  status `certified` + slot sha256 pinned + `rvt.versions.KNOWN_RELEASES
  [year].creation_certified`), `resolve_base(..., target_release=N)`
  (slot resolution, sha256 pin verify, release re-check), and
  `BaseNotCertified(BaseError)` so the front door can degrade honestly
  instead of failing the request.

### 1c. The guard + the ONE line (owned by the version model)

`rvt.versions.creation_fallback_line(target, produced)` (new) returns
exactly:

    target 2025 requested: the 2025 base is pending certification; this
    file targets 2026 -- your Revit 2025 cannot open it; the IFC alongside
    is version-agnostic

It appears verbatim in: the CLI summary (`VERSION:` line),
`manifest.target_version.line`, `manifest.honesty.release`, and
MANIFEST.md's "Target Revit version" section. A 2025 target can no longer
produce a silent 2026 file: either the message rides with the delivery, or
the request is refused with the reason (wrong-release `--base`).

### 1d. The IFC addition is REAL (new `src/rvt/frontdoor/ifc_out.py`)

* `--ifc` route fallback: the input IFC is copied beside the build (it IS
  the version-agnostic artifact).
* `--prompt` route fallback: the resolved intent is re-emitted as a
  deterministic IFC4 file (`write_intent_ifc`) — project/site/building/
  storey, the room shell proxy with `wall_<i>` box solids +
  `RoomInformation` pset, one product per equipment (body/enclosure +
  nameplate front-feature boxes, world-baked `IfcTriangulatedFaceSet`),
  tagging-contract psets (PanelSchedule / SwitchboardSchedule /
  TransformerSchedule) incl. `FedFrom`. Plain-text STEP writer, no new
  dependency; deterministic GlobalIds + pinned header stamp (same intent +
  same filename = byte-identical file).
* PROVEN by round trip through OUR OWN `--ifc` resolver
  (`rvt.ifc.intent.resolve_intent`): the worked 2500 A room prompt →
  emitted IFC → intent with **identical tags, kinds (7/7), walls (4/4) and
  feeder edges (7/7, incl. UTILITY→MSB)**; insertion points and front
  normals recovered. This is a fast test in the suite now.
* AND proven end to end: `author --prompt "a 400 A distribution panel"
  --target-version 2025` (full build, 4.3 s) delivered `prompt_room.rvt`
  (2026, validator VALID) + the line + `prompt_room.ifc`; feeding THAT IFC
  back through `author --ifc` built a native `.rvt` again (self-checks
  PASS, 4.2 s) — the addition is a working input, not decoration.

### 1e. Skill body (`plugin/skills/tekton-author/SKILL.md`; frontmatter untouched)

"Step 0 — ask the Revit version FIRST, then pass it to the tool": the
version question is the first step; per-target honest status (2026
certified / 2025 in certification with the exact fallback behaviour + the
line to relay verbatim / older = same degrade); `--target-version` added to
the flags list; report-order updated (relay `target_version.line` with the
files); caveat 1 updated (user file needed only for an uncertified target
release — 2025 in certification).

### 1f. Tests — the executable finish line (`tests/test_target2025.py`)

12 tests. 11 run TODAY (all green): the version-model guard refuses 2025
with the "Do NOT substitute a newer release" message; the fallback line is
byte-exact; the registry slot reads pending with NO sha256; `resolve_base
(target_release=2025)` raises `BaseNotCertified`; a 2026 `--base` with a
2025 target is refused (`VersionError`); the CLI flag parses (and 2024 is
rejected); the front door fallback delivers line+IFC (manifest json
round-trip included); the explicit-pinned-base (standalone) path still
falls back while a user's R5 base is refused; a 2026 target matches with
no addition; the IFC addition round-trips the intent. THE FINISH LINE
(`test_END_STATE_author_2025_produces_a_2025_file`) is `skipif(2025 not in
SUPPORTED_CREATION_RELEASES)` — it ARMS ITSELF when G25-5 flips the flag,
and asserts: build completes, `detect_release(out) == 2025` (BasicFileInfo
Format), BasicFileInfo build string present, `schema_of(out).sha256 ==
KNOWN_RELEASES[2025].schema_sha256`, `target_version.status == "match"`,
no fallback line. Every TODAY-test is conditioned on the flag (not on the
calendar), so certification day flips them to their certified meaning
instead of breaking them.

### 1g. Eval kit refreshed (`tekton-eval-kit/` + `tekton-eval-kit.zip`)

* `tekton-eval-kit/tekton-plugin/` = EXACTLY the current
  `tekton-plugin.zip` contents (unzipped folder, no nested zip; verified:
  the only `.rvt` inside is the pin-checked genesis base asset).
* `INSTALL.md` / `EMAIL-DRAFT.md` / `REPORT-CARD.md`: the stale "Not
  standalone yet / specimen ancestor not found" boundary REPLACED with the
  truth (native `.rvt` creation from a prompt/IFC now runs fully standalone
  from bundled assets, zero donors) + the VERSION caveat made first-class
  ("Zeroth question — which Revit version do you run?"; files are 2026
  format; 2025-native kit in certification; the refusal dialog text is
  itself useful data; prompt 8 now says the build runs on the reviewer's
  machine and mentions the IFC-on-2025 behaviour).
* `Tekton-Eval-Kit-Instructions.pdf` REGENERATED to match (generator:
  `tekton-eval-kit/_make_instructions_pdf.py`, reportlab; underscore files
  are excluded from the kit zip so it never ships).
* `tekton-eval-kit.zip` rebuilt: 309 members (was 388 — `__pycache__`
  droppings excluded now), TEST-KIT 8 files intact and unchanged.

## 2. Gate results (pasted)

* `tools/sync_plugin.py` → "synced 9 file(s); deny-audit clean; assets
  verified (genesis base == frontdoor pin); Validation passed; rebuilt
  tekton-plugin.zip (2740 KB)"; `--check` → "plugin in sync with source".
* Full suite: **see BRANCH STATE** (run after all edits; count pasted
  there).
* Zip constraint scan (both zips; script in the session scratchpad,
  reproduced below): **HARD constraints PASS on both** —
  `tekton-plugin.zip` 241 members / `tekton-eval-kit.zip` 253 members;
  deny-listed member paths 0 (samples/, extracted/, quarantine,
  /reference/, autodesk-extracted); banned raw-byte strings 0 (old
  working name + internal identifiers); quarantined-content sha256 matches
  0 (every member hashed against all 15 quarantined sample files);
  unexpected `.rvt/.rfa` members 0 (allow-list: the genesis asset + the 8
  TEST-KIT files); nested zips 0; genesis asset sha256 == front-door pin;
  SKILL.md frontmatter clean 5/5 (keys exactly {name, description}, name
  == folder, description non-empty).
* HYGIENE finding (stream-added check, PRE-EXISTING content, reported not
  fixed — cross-territory): the raw byte string `/Users/ck` (personal lab
  path) appears in 8 shipped members (mirrored in both zips):
  `examples/USECASES-OVERVIEW.md`, 4× `examples/chicago-plenum-electrical-
  room/*.json`, `examples/eaton-panelboard/panelboard-validation.json`,
  `lib/README.md`, `assets/genesis/G_ABPD.compose.json`. See §3.

## 3. Cross-territory proposals (diffs for their owners, NOT applied)

1. **Scrub `/Users/ck` from shipped artifacts** (usecase-runner /
   plugin-packager / genesis streams own the sources). Sources:
   `usecases/chicago-plenum-electrical-room/{generated-validation,
   validation-before,validation-after,harden-report}.json`,
   `usecases/eaton-panelboard/panelboard-validation.json`,
   `plugin/examples/USECASES-OVERVIEW.md`, `plugin/lib/README.md`,
   `experiments/genesis/subst_k4/compose/G_ABPD.manifest.json` (the
   compose provenance record — its owner should decide whether to scrub or
   have sync redact-on-copy). Mechanical fix per file:
   `python - <<'EOF'` replace `"/Users/ck/dev/things/tekton/" -> "<repo>/"`
   and bare `"/Users/ck" -> "<home>"`, then `tools/sync_plugin.py`.
   Alternative: teach `tools/sync_plugin.py` a redact-on-copy for
   `examples/**` + the compose manifest (keeps sources as-is, breaks no
   byte-equality test — none covers these members).
2. **At G25-5 (the 2025 campaign's certification tick)** the certified
   flip is DATA + one flag, all in one place each:
   * `rvt.versions.KNOWN_RELEASES[2025]`: `creation_certified=True`,
     `genesis_base=<relpath>`;
   * `src/rvt/frontdoor/assets/genesis_base.json` `releases.2025`:
     `sha256`, `bytes`, `status: "certified"` (relpath already reserved:
     `experiments/genesis/subst_k4_2025/compose/G_ABPD_2025.rvt` — if the
     campaign lands the file elsewhere, update the slot relpath);
   * plugin packager: bundle the 2025 base next to the 2026 one
     (`tools/sync_plugin.py` `asset_mappings()` gains the pair; the
     resolver already looks in `assets/genesis/` by basename);
   * nothing else: `tests/test_target2025.py` finish line arms itself, the
     TODAY-tests flip to their certified branches, the front door's
     `--target-version 2025` starts resolving the 2025 base, and the
     fallback line disappears on its own.
3. **`rvt.versions` samples_dir note**: `KNOWN_RELEASES[2025].sample_build
   == "Development Build"` (what Autodesk's own 2025 samples carry) — when
   the campaign defines OUR 2025 authoring string (plan §G25-5, counsel
   G2/C1), consider recording it beside the pin so identity checks have a
   constant to assert.

## 4. Files touched (this stream)

* `src/rvt/versions/__init__.py` (creation_fallback_line + export)
* `src/rvt/frontdoor/assets/genesis_base.json` (releases registry)
* `src/rvt/frontdoor/base.py` (slots, release_status, BaseNotCertified,
  target-release resolution, release re-check)
* `src/rvt/frontdoor/ifc_out.py` (NEW: the deterministic intent→IFC4
  emitter)
* `src/rvt/frontdoor/__init__.py` (target_version, _resolve_base_and_
  version, _emit_ifc_addition, _rvt_route_version_block, route wiring)
* `src/rvt/frontdoor/manifest.py` (version block in both manifests +
  honesty release line + MANIFEST.md section)
* `src/rvt/frontdoor/assets/README.md` (documents the per-release slots +
  the degrade contract)
* `tools/frontdoor.py` (--target-version, VERSION summary line)
* `plugin/skills/tekton-author/SKILL.md` (body only)
* `tests/test_target2025.py` (NEW)
* `tekton-eval-kit/**` (plugin folder from current zip; 3 docs; PDF;
  `_make_instructions_pdf.py` generator) + `tekton-eval-kit.zip`
* `docs/inbox/target-2025.md` (this record)
* (plugin/lib/** copies of the src changes: via `tools/sync_plugin.py`,
  not by hand)

Note on territory: the charter named `tools/frontdoor.py`,
`src/rvt/frontdoor/base.py`, `src/rvt/versions/`; wiring the flag through
the front door also required `src/rvt/frontdoor/__init__.py`,
`manifest.py` and the new `ifc_out.py` — all inside the front-door
package, which has no other active stream this session. No file outside
`src/rvt/{versions,frontdoor}`, `tools/frontdoor.py`, the named skill
body, tests, the kit, and this record was modified.

## BRANCH STATE

* Working tree: NOT a git repo (whole project is untracked files on disk;
  no branch to name). All edits are on disk under
  `/Users/ck/dev/things/tekton` as listed in §4.
* Suite: FULL RUN **IN FLIGHT at record time** — `nohup .venv/bin/python
  -m pytest tests/ -q` (pid 14336) over the FINAL tree, log at
  `/private/tmp/claude-502/-Users-ck-dev-things/91c616fc-3cee-49e7-be61-74bc4edd8fdb/scratchpad/suite.log`
  (a completion monitor is armed; read the log's last line for the count —
  do not retire this stream on anything else). Verified GREEN already, on
  the final code: `tests/test_target2025.py` 11 passed + 1 self-arming
  skip; the five stream-adjacent files (`test_frontdoor.py`,
  `test_versions.py`, `test_target2025.py`, `test_plugin_sync.py`,
  `test_bootstrap.py`) 89 passed / 3 skipped / 0 failed; no source file
  changed after the full run launched. Count before this stream: 1340
  passed / 0 failed.
* `tools/sync_plugin.py --check`: clean (plugin in sync, deny-audit clean,
  assets verified).
* Zip constraint scan: HARD PASS both zips (details §2); 8 pre-existing
  `/Users/ck` hygiene hits reported to their owners (§3.1).
* Behavioral proof: full `author --prompt "a 400 A distribution panel"
  --target-version 2025` run delivers the 2026 `.rvt` + manifest with the
  fallback line + `prompt_room.ifc` addition (see §2/§1d); handoff-only
  and match/unspecified paths exercised in tests.
* DONE per charter: version-guarded front door ✓; honest 2025 messaging
  (CLI + manifest + skill + kit) ✓; executable finish line ✓; refreshed
  kit ✓; sync ✓ + scan ✓ green; FULL suite in flight (targeted +
  adjacent runs green; read the log's final line to close this box —
  the one remaining verification).
