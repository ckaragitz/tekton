# Stream plugin-frontmatter — the shipped agents/commands/README route creation through `go author` (issue #119)

Date: 2026-08-09. Issue: #119 (P0, `area:plugin` `area:docs`, from steer #108).
Territory: `plugin/agents/*.md`, `plugin/commands/*.md`, `plugin/README.md`,
`plugin/docs/HONEST-STATUS.md`, `plugin/scripts/validate_plugin.py`,
`tests/test_plugin_validate.py`, this record. NOT touched: `plugin/skills/*/SKILL.md`
(hot, #24/#173), the repo-root README / AGENT_BRIEF (#4), anything generated.

## Why

Hard rule 1 + PG3. The hand-authored plugin front matter was untouched since
the initial import and contradicted the certified front door: the job
orchestrator agent and `/tekton-job` said native `.rvt` was "only for editing
an existing `.rvt` — creation of new elements in `.rvt` is not yet available;
say so and route to IFC"; the author agent's first step was `pip install ./lib`
and it "states plainly that new-element creation is in-progress and not
deliverable"; the README listed two of five skills and called creation "still
in progress"; HONEST-STATUS graded IFC/spec → `.rvt` "in-progress … today
deliver Tier-1 IFC instead". A stranger running `/tekton-job "make me an
electrical room .rvt"` would have been handed an IFC instead of the requested
`.rvt` — the exact swap rule 1 forbids — while `go author` builds and delivers
that room on a certified base in one call.

## What shipped

1. **`plugin/agents/bim-job-orchestrator.md`** — rewritten around the
   deliverable rule. Intake asks the **Revit year first** whenever a
   `.rvt`/`.rfa` is the output (2026 · 2025 · 2024 = supported
   `certified-base`; older = not supported for creation, still delivered +
   one clear line + IFC beside it; unsure → 2024). Pipeline: build = dispatch
   `tekton-author-agent` for ONE `go author --prompt | --ifc | --rvt --edit …
   --target-version YEAR --out … --json` call; IFC = `ifc-hardening-agent`
   only when the IFC *is* the deliverable, was supplied, or the year is
   unsupported (an addition, never a replacement); QA on every artifact
   (`rvt_validate.py` for `.rvt`/`.rfa`, `validate_ifc.py` for `.ifc`) where a
   failed `.rvt` gate changes the label, not the delivery. Delivery report =
   tekton-author SKILL.md "Step 2" order: files first → version story
   (`target_support` certified vs `this_file` validated-not-certified,
   `release.line` verbatim) → `result.status` verbatim → stamps (PROOF-ONLY in
   one sentence) → standing caveats (open cell, LOAD ≠ RENDER, circuits
   planned) → counts / `intent.json` defaults → IFC Tier statement when
   applicable → numbers only.
2. **`plugin/agents/tekton-author-agent.md`** — now the create + edit agent
   over the tekton-author / tekton-edit skills. "Setup: there is none on the
   hot path" (no pip/venv/preflight; `go.ready` false → relay
   `preflight_line`, point at `/tekton-doctor`); year as an input; the three
   `go author` forms; exit codes 0/2/3/4 with 4 = deliver WITH the failing
   report; return order = files, release, status + stamps verbatim, counts,
   wall time; the lines it holds (deliver then caveat, two tiers, never
   substitute, never touch inputs in place).
3. **`plugin/commands/tekton-job.md`** — the `/tekton-job` intake flow
   (rendered below): year first, one build call, IFC as addition, QA, deliver
   in the reporting order.
4. **`plugin/commands/tekton-validate.md`** — the `.rvt`/`.rfa` branch no
   longer starts with `pip install ./lib`; it is ONE
   `skills/tekton-inspect/scripts/_bootstrap.py go rvt_validate.py FILE --json …`
   call (readiness inline, three validator layers, the file's release from
   `go.inputs[].revit_release`, LOAD-vs-RENDER pointer). IFC branch unchanged
   except naming `/tekton-doctor --install` as the equivalent one-time install.
5. **`plugin/agents/qa-validation-agent.md`** — `.rvt`/`.rfa` gate switched
   from `rvt_selfcheck.py` (four low-level checks, tekton-native) to the
   layered validator via the tekton-inspect bootstrap (the actual shipping
   gate, 0 errors), states the release, and spells out rule 1: a failed
   `.rvt`/`.rfa` gate is reported and sent back to the builder but the file
   is still handed over; a schema-broken IFC goes back to hardening.
   `ifc-hardening-agent.md`, `tekton-harden.md`, `tekton-doctor.md`: unchanged
   (already consistent; the IFC authoring extras remain the one optional
   install).
6. **`plugin/README.md`** — intro leads with creation; "What's in the box"
   lists all five skills (`tekton-author`, `tekton-edit`, `tekton-inspect`,
   `tekton-native`, `tekton-ifc`), the four commands, agents, the certified
   `assets/genesis/` bases, examples, engine; a new "honest truth, today" box
   (creation delivered on certified 2026/2025/2024 bases; validator PASS ≠
   Autodesk acceptance; PROOF-ONLY in one sentence; target version asked
   first with the older-year fallback; LOAD ≠ RENDER; the open walls+families
   cell named with `--strict` and repo issue #16; circuits planned; Tier 1 vs
   Tier 2). Install sections drop the engine install entirely (bootstrap finds
   `lib/` + bases; `/tekton-doctor --install` = optional IFC extras only);
   Cowork / claude.ai upload instructions now include `_shared/`, `lib/`,
   `assets/`; quickstart is the bare `go author` electrical-room run with the
   real numbers from this session (below) followed by the Eaton IFC one;
   phrasing examples and the two standing rules rewritten (year first;
   deliver first, caveat after); tree updated (five skills, `_shared/`,
   `assets/`).
7. **`plugin/docs/HONEST-STATUS.md`** — regraded with a certified /
   validated / open legend that keeps the two tiers apart and cites the
   ledger: bases `G_ABPD` / `G_ABPD_2025` / `G_ABPD_2024` certified;
   prompt/IFC/spec → `.rvt` validated on a certified base (matrix *works*;
   `ROOM2025_walls`, `W1_gabpd_wall_solid`, `RSOLID_walls_A_solid`,
   `stage_L8_lp4`, `V25`/`V26`, `V23`); family generation validated
   (`L_downlight_loaded`, `L1a`); family loading certified at base level
   (`T2a`, `TB0g`); older targets open (delivered + line + IFC); the open cell
   open (#16, `WF_fix`/`WF_nofix` controls); circuits open; LOAD vs RENDER;
   edits certified (`M2`/`M3`/`M4`/`M2_rac`), add-into / merge-into / rvt→ifc
   / extract validated, text edit + rewrite certified (`V15`/`V18`/`V19`);
   read/validate/IFC rows; §4 rules (deliver first, target version first, two
   tiers, IFC = addition, no APS/install-dir/donor bytes, no install on the
   job path); §5 defaults start with "make me an electrical room .rvt" →
   `go author`. Nothing beyond `tools/route.py matrix` (21 cells: 17 works /
   1 partial / 3 missing, evidence self-audit clean in this clone).
8. **`plugin/scripts/validate_plugin.py` — stale-claim guard.**
   `STALE_CLAIMS` (regex, why) scanned case-insensitively, one failure per
   line hit with `file:line: stale claim '…' -- why`, over `STALE_CLAIM_DOCS`
   = `agents/*.md`, `commands/*.md`, `README.md`, `docs/HONEST-STATUS.md`;
   `stale_claim_hits(root)` is the pure function, `check_stale_claims()` is
   wired into `main()` (so `tools/sync_plugin.py`'s validation step and CI go
   red on a regression). The regexes:

   | regex (re.I) | why |
   |---|---|
   | `not yet available` | creation is delivered by `go author` |
   | `in-progress and not deliverable` | creation is delivered (stamped), never "not deliverable" |
   | `route (?:it \|them \|the \w+ )?to IFC` | IFC is an addition, never a replacement (rule 1) |
   | `deliver Tier-1 IFC instead` | never swap an IFC for a requested .rvt |
   | `pip install \./lib` | no install on the hot path (doctor --install is the only install) |
   | ``creation of new elements in `?\.rvt`? is not`` | creation is delivered by the tekton-author flow |
   | `still in progress` | grade certified / validated / open with evidence |

9. **`tests/test_plugin_validate.py`** (+3 tests, file already in
   `tests/ci_shard.txt`): the guard is silent on a minimal current-wording
   tree; a fixture carrying the old orchestrator/author-agent/README/
   HONEST-STATUS phrases yields a hit for every one of the seven patterns,
   each formatted `file:line: stale claim … -- why`, and the clean command
   file stays clean; the shipped `plugin/` tree has zero hits and
   `check_stale_claims()` is called from `main()`.

## The rendered `/tekton-job` intake flow (as a session now runs it)

> **/tekton-job make me an electrical room .rvt with 6 panels**
>
> 1. *Intake (one round).* "Which Revit year will open this — **2026, 2025,
>    2024**, or older/unsure? (2026/2025/2024 build natively on that year's
>    certified base; older isn't supported for creation — you'd still get a
>    file, a clear line that your Revit can't open it, and an IFC beside it;
>    unsure → 2024.) Anything specific about the room size, service rating,
>    panel names/ratings/voltages? Otherwise I'll default them and tell you
>    what I assumed." → user: "2025, defaults are fine."
> 2. *Build — one call (tekton-author-agent):*
>    `python <plugin>/skills/tekton-author/scripts/_bootstrap.py go author --prompt "an electrical room with 6 panels" --target-version 2025 --out job/eroom/out --json`
> 3. *QA (qa-validation-agent):*
>    `python <plugin>/skills/tekton-inspect/scripts/_bootstrap.py go rvt_validate.py job/eroom/out/prompt_room.rvt --json job/eroom/out/qa-report.json`
> 4. *Deliver (DELIVERY.md):* **Files:** `prompt_room.rvt`, `families/` (6
>    `.rfa`), manifests, + the AI-surface handoff (`HANDOFF.md`,
>    `scene-brief.json`, `PROMPT_TO_IFC.md`) as an extra. **Version:** built
>    for Revit 2025; opens in Revit 2025 and newer — never an older Revit;
>    base `certified-base` (Autodesk's reader certified G_ABPD_2025); this
>    file `validated-not-certified` (our gate: VALID 0 errors / 0 warnings;
>    Autodesk acceptance only when your Revit / the Autodesk Viewer opens it).
>    **Status (verbatim):** `PROOF-ONLY (self-checks PASS; see
>    honesty.proof_only_stamps + status_gate)`; **stamps:** `PROOF-ONLY:
>    walls+families combination unverified`, `PROOF-ONLY, NOT-DELIVERABLE` —
>    the file is yours; PROOF-ONLY means the base lineage still discloses
>    Autodesk-derived residue and our identity/legal-review gates are open.
>    **Caveats:** walls + our placed families in one file is the open cell
>    (say the word and I'll re-run `--strict` for two coordinated files);
>    created walls load but may not draw yet (I can run the render check);
>    circuits are planned in the manifest, not live Revit circuits.
>    **Understood/defaulted:** from `intent.json`. **QA:** VALID 0 errors,
>    warnings=0, Revit 2025. **Wall time:** 15.6 s. Want the IFC as well?

## Evidence

- DONE grep: `grep -rniE "not yet available|in-progress and not deliverable|route to IFC|deliver Tier-1 IFC instead|pip install \./lib" plugin/agents plugin/commands plugin/README.md plugin/docs/HONEST-STATUS.md`
  → **no output** (exit 1), in the repo and in the unzipped bundle.
- `plugin/scripts/validate_plugin.py` → `assertions passed: 24 … RESULT: PASS`
  (83 referenced plugin-relative paths resolve; stale-claim guard: 7 retired
  phrases absent). Same PASS from `scripts/validate_plugin.py` inside the
  unzipped `tekton-plugin.zip`.
- `tools/sync_plugin.py --check` → `plugin in sync with source (deny-audit
  clean, assets verified)` (only hand-authored files touched);
  `tools/sync_plugin.py` → `√ Validation passed … rebuilt tekton-plugin.zip (5012 KB)`.
- `pytest tests/test_plugin_validate.py tests/test_plugin_sync.py -q` → **13 passed**.
- `tools/dev/check_portable_paths.py` → `ok: 2694 tracked paths are portable`.
- **Bare-surface runtime check** (fresh unzip of the rebuilt zip into the
  scratch dir, `env -i PATH=/usr/bin:/bin`, system `python3` 3.11, no repo on
  the path): the changed `agents/*.md`, `commands/*.md`, `README.md`,
  `docs/HONEST-STATUS.md` are in the bundle;
  `python3 skills/tekton-author/scripts/_bootstrap.py go author --prompt "an electrical room with 6 panels" --target-version 2025 --out out/j --json`
  → exit 0, **wall 15.6 s** (first run of the session 17.0 s; steer #108),
  `go.preflight_line = "tekton: READY | python 3.11.15 | engine bundled | genesis verified (Revit 2026) | family-donor missing | out-dir OK | 0.058s"`,
  `result.status = "PROOF-ONLY (self-checks PASS; see honesty.proof_only_stamps + status_gate)"`,
  `result.release = {requested 2025, output 2025, opens_in "Revit 2025 and newer -- never an older Revit", target_support "certified-base", this_file "validated-not-certified (our gate: combined: VALID 0 errors / 0 warnings; …)"}`,
  stamps `['PROOF-ONLY: walls+families combination unverified', 'PROOF-ONLY, NOT-DELIVERABLE']`,
  files `prompt_room.rvt` + `families/` (6 `.rfa`) + handoff. The QA call the
  docs now prescribe, `skills/tekton-inspect/scripts/_bootstrap.py go rvt_validate.py out/j/prompt_room.rvt --json out/report.json`
  → exit 0 in 1.0 s, `VALID (no errors); warnings=0`, `go.inputs[0].revit_release = 2025`.
  These are the exact strings the README quickstart and the agents describe.
- `tools/route.py matrix` in this clone: 21 cells 17/1/3, "evidence
  self-audit: every citation checks out against the ledger and the tree".
- `/verify` (plugin surface): `tools/sync_plugin.py` → `√ Validation passed`,
  then `tools/surface_bench.py --zip tekton-plugin.zip --json out/verify/bench.json`
  (61 s): preflight 1 call 0.1 s on all three simulations; `go-author-prompt`
  1 call 3.7 s cowork / 4.3 s codeexec / 4.4 s local; `author-prompt` 4.2 /
  4.5 / 4.8 s; `edit-roundtrip` 3 calls 1.7 / 2.4 / 1.6 s; `validate` 0.8 /
  1.1 / 0.8 s; session totals **10.9 s / 8 calls (cowork)**, 12.9 s (codeexec),
  35.5 s (local). One non-PASS row, **pre-existing and unrelated to this
  diff**: `author-ifc` FAILs on the two numpy-less simulations (exit 3 in
  0.4 s with `FAILED (IFC intent failed: ImportError: numpy is required here
  (IFC placement / geometry resolution) … doctor --install)`), PASS 23.8 s on
  local where numpy exists — reproduced by hand on the bare bundle; already
  tracked as #127. Consequence for THIS stream: the README / author agent /
  HONEST-STATUS now say honestly that the `--ifc` input route needs `numpy`
  (one `/tekton-doctor --install`), never `ifcopenshell`, instead of the old
  README's "IFC read routes need no pip install at all".

## Findings / open questions (filed or noted, not done here)

- `plugin/lib/README.md` and `plugin/skills/tekton-native/SKILL.md` still
  describe `pip install ./lib` as the install path (out of this territory:
  lib README ownership unclear; SKILL.md is #24's hot file). The README now
  points developers at `lib/README.md` without repeating the phrase; the
  guard deliberately does not scan `lib/` or `skills/`.
- The `.rvt` QA gate in the agents is now the layered validator; the four
  low-level self-checks (`rvt_selfcheck.py`) remain available under
  tekton-native for byte-level work. If the orchestrator should run both, that
  is a one-line follow-up once someone measures whether selfcheck ever catches
  something the validator's STRUCTURE layer does not.

## BRANCH STATE

- Branch `cam/119-plugin-frontmatter` from `main` @ 730fe5a; PR closes #119.
- Files written: `plugin/agents/bim-job-orchestrator.md`,
  `plugin/agents/tekton-author-agent.md`, `plugin/agents/qa-validation-agent.md`,
  `plugin/commands/tekton-job.md`, `plugin/commands/tekton-validate.md`,
  `plugin/README.md`, `plugin/docs/HONEST-STATUS.md`,
  `plugin/scripts/validate_plugin.py`, `tests/test_plugin_validate.py`,
  `docs/inbox/plugin-frontmatter.md`.
- Gates: validate_plugin PASS (repo + bundle); sync `--check` clean;
  test_plugin_validate + test_plugin_sync 13 passed; portable paths ok; bare
  `go author` READY/exit 0/15.6 s. Nothing staged for the viewer (docs +
  validator only; no `.rvt` bytes changed). `tekton-plugin.zip` regenerated
  locally, not committed (git-ignored).
