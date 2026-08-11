# #511 -- the shipped plugin text stops offering a family donor (steer #498 / S-2026-08-10-c)

Stream `plugin-docs`, one PR. Refs #480 / #505 (the engine change this documents), #510 (the
review that found the stale lines), follow-up #653 (the bootstrap *code* still reports a donor).

## What was wrong
#505 removed the `$RVT_FAMILY_DONOR` lookup from famgen; the text a stranger reads still offered it:
`plugin/commands/tekton-doctor.md` item 4 ("only a non-2026 target release needs one `.rfa`/`.rvt` of
their own; set `$RVT_FAMILY_DONOR`"), `plugin/skills/tekton-author/SKILL.md:194` and
`plugin/skills/tekton-native/SKILL.md:99` (the variable listed as an expert override -- it does
nothing), and `docs/product/PERMUTATION-MATRIX.md` had no donor-free line on the two `→ rfa` rows.

## What changed (docs only; no cell, no engine, no other SKILL.md)
1. **tekton-doctor item 4** rewritten to the per-release truth taken from `tools/route.py matrix` +
   the matrix doc's prompt → rfa row: bundled container is the normal state; every family is
   self-generated on every release, no donor / user file needed or read, "the donor path is
   retired; any leftover donor/override wording in the report changes nothing in the build — never
   ask for one" (the doctor *code* still prints such a line until #653); a non-2026 recipient needs only `--target-version`
   (2026/2025/2024 emit AS that release -- validator-gated, not viewer-certified, PROOF-ONLY;
   2023/unknown delivered at 2026 + the one line; no year → 2026 and the JSON says to ask); the
   Autodesk-directory prohibition kept verbatim. The frontmatter description and item 2 say
   "family container" instead of "family-donor status". The variable is not named (so the line
   stays true after #653 lands).
2. **SKILL.md ×2 (hot):** pure removals of the `$RVT_FAMILY_DONOR` token, plus (review nit)
   `tekton-native/SKILL.md:53` "any donor/template file comes from the plugin's own assets or from
   the user" → "any template file comes from the plugin's own assets"; frontmatter untouched.
   `wc -c` before → after: tekton-author 14078 → 14077, tekton-native 8421 → 8396 (S-2026-08-09-g:
   weight not increased; descriptions unchanged, so no `surface_bench` token run needed).
   Review nit also folded into doctor item 4: the degrade-once case (a family needing a class the
   older schema lacks — arc profiles at 2024, #241 — is delivered at 2026 with the one line).
3. **PERMUTATION-MATRIX.md** prompt → rfa and ifc → rfa caveat cells open with **donor-free
   (self-generated)** + evidence pointers, stated no higher than the records: #480 (record
   `rfa-revit-api-compat.md` iteration 13, guard `test_donorless_host_document_wires_every_registry`),
   #505 (record `donorless-ifc.md`: "desktop-verified on two machines"; #480's own pair logged
   "verdict pending"), the assembly lane's recorded desktop open (`ifc-assembly-rfa.md`: "it opened
   and all the slots for the channel are in"); and the one recorded gap on ifc → rfa -- the
   single-product downlight archetype still emits on the research-corpus container (owner disk,
   #94), a container source, never a user file. Nothing of this is in the viewer ledger, so both
   rows keep "validator-gated + PROOF-ONLY". Status columns untouched (`test_router.py` pins them).
4. **`docs/inbox/learned-donorless-host-adoc.md`** -- the #480 lesson (a famdoc law has an element
   half and a host-ADocument half; no famgen test read the host document until the desktop
   failure; probes a human opens must be built the way a stranger's install builds them) for the
   tech-lead loop to fold into KNOWLEDGE.md. KNOWLEDGE.md / TRACKER.md not touched here.
5. This index + fragment (`docs/inbox/plugin-docs.md` is new: no plugin-docs stream index existed).

## Evidence
* the DONE grep, before:
  ```
  plugin/commands/tekton-doctor.md:37:   one `.rfa`/`.rvt` of their own; set `$RVT_FAMILY_DONOR` or pass the
  plugin/skills/tekton-author/SKILL.md:194:   `$RVT_FAMILY_DONOR`).
  plugin/skills/tekton-native/SKILL.md:99:  base; no donor or specimen file is needed (`$RVT_FAMILY_DONOR` /
  ```
  after (`plugin/commands plugin/skills/*/SKILL.md plugin/README.md plugin/docs`): **nothing** (exit 1).
  With `docs/product` added: exactly the two matrix rows, each saying no lane reads
  `family_donor` / `$RVT_FAMILY_DONOR` (the retired-path statement the DONE allows).
* `plugin/scripts/validate_plugin.py`: PASS, 25 assertions. `tools/sync_plugin.py`: validation
  passed, zip rebuilt (5348 KB), identity scan 0 mismatches; `--check`: in sync, exit 0; no tracked
  drift after the sync (docs under `plugin/commands` and `plugin/skills/*/SKILL.md` are sources).
* `RVT_SKIP_LARGE=1 pytest tests/test_plugin_validate.py tests/test_plugin_sync.py tests/test_router.py
  tests/test_router_release.py tests/test_router_load_release.py tests/test_records_layout.py -q -rs`
  → **189 passed, 12 skipped** (11 × `RVT_SKIP_LARGE`/worked .rvt absent, 1 × chmod-as-root), 65 s.
  (`tests/test_matrix*.py` does not exist; `test_router.py` is the file that pins the doc rows
  against the machine matrix and runs `verify_evidence()`.)
* `tools/route.py matrix`: byte-identical before/after (21 cells: 18 works / 1 partial / 2 missing;
  evidence self-audit clean).
* `tools/dev/check_portable_paths.py`: ok, 3026 → 3029 tracked paths portable.
* Whole merged CI shard: not run here (docs-only under `plugin/` + `docs/`; the tech-lead sandbox runs it).

## Findings / follow-ups
* **#653 (filed, `Refs #511`)**: `plugin/skills/_shared/tekton_env.py` still *reports* the variable
  (`family-donor <status>` in the readiness line; doctor prints "$RVT_FAMILY_DONOR stays as an expert
  override, e.g. a non-2026 target release") and `tests/test_bootstrap.py` pins that. Code, outside
  this issue's docs-only territory.
* `src/rvt/frontdoor/matrix.py` cell text mentions donors only as "zero donors" / "donor-free" --
  nothing to retire there.
* Not in scope, noted for the planner: the prompt → rfa doc row still says "catalog-backed kinds only
  … anything without facts is refused by name", which steer #591 (nominal archetypes) is changing;
  whoever lands #591's matrix wording owns that sentence.

### BRANCH STATE
* branch `cam/511-donor-free-docs` from `origin/main` @ 697928f
* written: `plugin/commands/tekton-doctor.md`, `plugin/skills/tekton-author/SKILL.md`,
  `plugin/skills/tekton-native/SKILL.md`, `docs/product/PERMUTATION-MATRIX.md` (two rows),
  `docs/inbox/learned-donorless-host-adoc.md` (new), `docs/inbox/plugin-docs.md` (new index),
  this fragment
* gates: as above -- validate_plugin PASS (25), sync + `--check` clean, 189 passed / 12 skipped,
  route matrix unchanged, portable paths ok
* shipped vs staged: docs only, nothing staged for the viewer; `/verify` skipped (plugin prose +
  docs, no runtime surface -- commit trailer says so); `/simplify` = a re-read of the diff
