# target-version-first — the skills ask the Revit YEAR first; ONE `go` call carries the honest per-release story (#24, #123)

Stream: eng #24 (engineer session under the tech-lead session; branch
`cam/24-target-version-first`, from `main@33622e3`). Issue #24 (P1,
`area:plugin`, `hot-file`) + #123 (its engine prerequisite, claimed into the
same PR — see §1). The issue names `docs/inbox/routing-ux.md` as the record;
the tech-lead brief for this run names this file — one record, this one.

Territory used: `plugin/skills/{tekton-author,tekton-edit,tekton-inspect,tekton-native}/SKILL.md`
(**hot files** — this session was the only one cleared to touch them this
round), `plugin/skills/tekton-author/references/REVIT-VERSIONS.md` (new),
`skills/tekton-ifc/SKILL.md` (source of the plugin mirror),
`plugin/skills/_shared/tekton_env.py` (`go` only), `src/rvt/frontdoor/__init__.py`
+ new `src/rvt/frontdoor/target_status.py` (allowed by the brief: "add the
status block at the source"), `tools/frontdoor.py` (**hot**, +9/−9: the
`--target-version` argument only), tests, `tests/ci_shard.txt`.

## 1. What was wrong (measured on `main@33622e3`, bare unzip + system `python3`)

`python3 skills/tekton-author/scripts/_bootstrap.py go author --prompt "an electrical room with 6 panels" --target-version 2025 --out out/j25 --json`

| symptom | before |
|---|---|
| the skills | tekton-author's Step 0 asked the version but told the model **2025 = "in certification, not yet deliverable", 2024 = "base not yet in certification"** — stale since the 2025/2024 composed bases certified; two calls per job (`_bootstrap.py` preflight, then `run frontdoor.py …`); tekton-edit/-inspect never stated the input's release; tekton-ifc §6.4 warned but named no route |
| `go … --target-version 2025` from the plugin | exit 0, **but** `manifest.target_version = {requested 2025, status fallback, output_release 2026}` + the false line *"the 2025 base is pending certification"* while `base_status` in the same block said `certified: true` and `G_ABPD_2025.rvt` sat in the bundle; `detect_release(output) == 2026`. Root cause two frames deep: the bootstrap exports `RVT_GENESIS_BASE=<plugin>/assets/genesis/G_ABPD.rvt`; `resolve_base(target_release=2025)` honours it as a user override, `require_release` raises, and `_resolve_base_and_version` — which already sha-identifies the file as OUR pinned default — chose the 2026 **fallback** instead of the target's certified slot. (#92 / PR #126 removes the export; #123 is this branch: the engine must not degrade when the "override" is our own default and a certified slot exists.) |
| `--target-version 2019` (or 2023) | `argparse: invalid choice` → exit 2, `result: null` — no explanation, nothing delivered, no nearest year |
| the `--json` result | `route, ok, status, out_dir, files, intent_json, handoff, manifest{paths}, errors, seconds` — **no version block, no stamps**: stating "opens in Revit N" or the PROOF-ONLY stamps needed a second call to read `manifest.json` (steer #108: every extra call is model latency) |
| `--rvt` route without `--target-version` | no version block at all — the detected input release was never surfaced |

## 2. What changed

**Engine (`src/rvt/frontdoor/`)**
- `__init__.py::_resolve_base_and_version` — in the existing `is_our_default`
  branch: mask `$RVT_GENESIS_BASE`, re-resolve `resolve_base(None, target_release=target)`
  (the pinned, sha-verified slot for that release: repo path → `plugin/assets/genesis`
  → `<RVT_PLUGIN_ROOT>/assets/genesis`), restore the env in `finally`; fall back
  only on `BaseNotCertified` / `BaseError`. `base.py` (hot) untouched — #123's
  suggested shape exactly.
- Fallback line is honest for years we do not create for: `certified-base`
  slot unresolvable → the version model's uniform "pending" wording (unchanged);
  `known-not-certified` / `not-supported` → *"target 2019 requested: tekton has
  no certified Revit 2019 creation base (supported: 2024, 2025, 2026); the
  nearest supported target is Revit 2024, which Revit 2019 cannot open either
  -- this file targets 2026 -- your Revit 2019 cannot open it; the IFC
  alongside is version-agnostic (links into Revit 2019+)"*. The block gains
  `target_support`, `nearest_supported`, `supported_targets`.
- `_route_rvt` computes the version block **always** (`requested: null,
  status: detected, input_release, output_release`), not only when a target
  was passed.
- `AuthorResult.as_json()` (= `frontdoor.py --json` = `go`'s `result`) gains
  two compact keys: `release` (see §3) and `stamps` (= `honesty.proof_only_stamps`).
- New leaf `target_status.py`: the vocabulary (`certified-base` /
  `known-not-certified` / `not-supported`; `validated-not-certified` /
  `self-checks-failed` / `not-built` for the file), `supported_targets()`,
  `nearest_supported()`, `roster()`, `release_view(manifest)` — all derived
  from `rvt.versions` + the pin at call time, no year literal in logic.

**CLI (`tools/frontdoor.py`, hot, one argument):** `--target-version` is
`type=int` with no `choices` — any year reaches the engine's guard, which
degrades honestly (hard rule 1) instead of argparse refusing.

**Bootstrap (`plugin/skills/_shared/tekton_env.py`, `go` only):**
`go.inputs = [{path, revit_release, opens_in, note}]` for every existing
`.rvt/.rfa/.rte/.rft` named in the args (BasicFileInfo read, ms) — so
`go rvt_edit.py their.rvt info`, `go rvt_validate.py …`, `go author --rvt …`
all state the detected release in the same JSON. `ensure_engine` is left as
on `main` (PR #126 owns the export removal; the two PRs touch disjoint hunks).

**Skills (hand-authored sources):**
- `tekton-author/SKILL.md` rewritten around *one question, one call*: Step 0
  asks the year once (picker where the surface has one; skip if the request
  names it; unsure/mixed → 2024) with the three-line honest roster; Step 1 is
  ONE `go author … --target-version YEAR` call; Step 2 reports from
  `result.files / release / status / stamps` in that order, relaying
  `release.line` verbatim + the IFC addition when present. Stale 2025/2024
  prose deleted; per-year table + wording moved to
  `references/REVIT-VERSIONS.md` (loaded only when needed).
- `tekton-edit/SKILL.md`: new Step 0 "the release is DETECTED, not asked"
  (`go.inputs[].revit_release`; edit keeps the input's release; honest limit:
  the edit engine opens 2026 project files today, #70); commands switched
  from `run` to `go`; the front door's by-name edit route added.
- `tekton-inspect` / `tekton-native`: state the detected release with every
  verdict; native's "Version reality" names the supported years and the flag.
- `skills/tekton-ifc/SKILL.md` §6.4: when the user wants the `.rvt`, ask the
  year once and hand the validated IFC to `go author --ifc … --target-version YEAR`.

## 3. The contract a skill session now relays (one call, no manifest re-read)

```json
"result": { "status": "PROOF-ONLY (self-checks PASS; …)", "files": {"combined": "…/prompt_room.rvt"},
  "release": { "requested": 2025, "output": 2025, "resolution": "match",
               "opens_in": "Revit 2025 and newer -- never an older Revit",
               "target_support": "certified-base",
               "this_file": "validated-not-certified (our gate: combined: VALID 0 errors / 1 warnings; Autodesk acceptance only when the recipient's Revit / the Autodesk Viewer opens it)",
               "supported_targets": [2024, 2025, 2026] },
  "stamps": ["PROOF-ONLY: walls+families combination unverified", "PROOF-ONLY, NOT-DELIVERABLE"], … }
```
Fallback adds `line` (relay verbatim), `nearest_supported`, `ifc_addition`;
the `--rvt` route adds `input_release` with `resolution: "detected"`; no flag
at all adds `ask`. `go.inputs` rides beside it for any script.

Intended conversation (tekton-author), two model turns around ONE tool call:

> **User:** make me an electrical room with 6 panels
> **Claude:** Which Revit year will open this — 2026, 2025, 2024, or older/unsure? (2026/2025/2024 are built natively on certified bases and open in that year and newer; older years aren't supported for .rvt — you'd get an IFC that links into any Revit; unsure → I'll use 2024.)
> **User:** 2025
> *(one call: `go author --prompt "…6 panels" --target-version 2025 --out out/room`)*
> **Claude:** Here is `out/room/prompt_room.rvt` — built for Revit 2025, opens in 2025 and newer (never older). Status PROOF-ONLY: it passed our validator (0 errors) on the certified 2025 base, but it is not itself Autodesk-certified until you open it (free Autodesk Viewer works), and it carries two stamps: *walls+families combination unverified* and *NOT-DELIVERABLE* (provenance) — labels, the file is yours. 6 panel families generated, 22 elements created; `intent.json` shows what I assumed.

Unsupported year, still one call: *"…target 2019 requested: tekton has no certified Revit 2019 creation base (supported: 2024, 2025, 2026) … your Revit 2019 cannot open it; the IFC alongside is version-agnostic"* → hand over `.rvt` + `.ifc`, recommend the IFC, offer 2024 only if someone there runs it.

## 4. Evidence (after; `tekton-plugin.zip` rebuilt by `tools/sync_plugin.py`, unzipped into an empty dir, `/usr/bin/python3` 3.11, no `RVT_*` in env)

| run (bare unzip) | wall | exit | `result.release` (requested/output/resolution/support) | file check |
|---|---|---|---|---|
| `go author --prompt "…6 panels" --target-version 2025` **cold** (no `__pycache__`) | **19.7 s** | 0 | 2025 / 2025 / match / certified-base | `tools/rvt_analyze.py`: `release: 2025 (format 2025)`, identity ours; `detect_release` 2025; in-job gate VALID 0 errors ¹ |
| same, **warm** (2nd process) | **18.9 s** | 0 | 2025 / 2025 / match / certified-base | — |
| same on `main` (before) | 17.1 s | 0 | *(no `release` key)*; manifest: 2025 / **2026** / **fallback** | `detect_release` **2026** |
| `--target-version 2024`, 1-panel prompt | 5.5 s | 0 | 2024 / 2024 / match | `detect_release` 2024 |
| `--target-version 2019`, 1-panel prompt (full build) | 5.3 s | 0 | 2019 / 2026 / fallback / not-supported, `nearest_supported 2024`, `line` as §2, `ifc_addition` written | `.rvt` + `.ifc` both delivered; before: argparse exit 2, nothing |
| `--handoff-only --target-version {2026,2025,2024,2019}` | ~1 s each | 0 | match ×3 / fallback (2019, IFC emitted from the intent) | — |
| `go author --rvt <2026 output> --edit "move PP-1 to 3,4"` (tekton-edit) | 2.2 s | 0 | null / 2026 / detected, `input_release 2026`; `go.inputs[0].revit_release 2026` | edited `.rvt` written, hard gates PASSED |
| `go rvt_edit.py assets/genesis/G_ABPD_2025.rvt info` | 0.1 s | 1 | `go.inputs[0].revit_release 2025` stated; job: `unexpected Partitions header: v=9 cls=0x391` = #70 (edit engine not release-aware) — pre-existing, now at least announced with the release | — |

¹ `tools/rvt_validate.py` on `main` reports one `FOUR-REGISTRY INCOHERENCE 6/0/0/0` on the 2025/2024 outputs (and `rvt_analyze` "coherence BROKEN") while the in-job, release-aware gate and `validate_file` inside `release_ctx.release_build_context(G_ABPD_2025)` both say VALID 0 errors on the same bytes — the known standalone-instrument false positive on non-2026 loaded content; PR #91 (#14) carries the fix, #93 the deeper one. Not caused or touched here; `this_file` quotes the in-job gate.

**Sizes (bytes) — SKILL.md is what a skill session loads eagerly; references load on demand:**

| file | before | after |
|---|---|---|
| `tekton-author/SKILL.md` | 11,876 | **10,447** (−12 %; description 861 chars, no `<`/`>`) |
| `tekton-edit/SKILL.md` | 6,360 | 7,551 (+ Step 0 + the by-name route) |
| `tekton-inspect/SKILL.md` | 5,859 | 6,100 |
| `tekton-native/SKILL.md` | 8,307 | 8,421 |
| `skills/tekton-ifc/SKILL.md` | 33,541 | 34,143 |
| eager total (5 skills) | 65,943 | 66,662 (+1.1 %) |
| `tekton-author/references/REVIT-VERSIONS.md` (lazy) | — | 3,995 |
| `go` stdout for the 6-panel 2025 job | 1,946 | 2,409 (+`release` +`stamps`; replaces a ≥30 KB `manifest.json` read) |

Round trips per creation job on the documented path: before 2 tool calls
(preflight + `run frontdoor.py`) + 1 read of `manifest.json` for stamps/version
= 3; after **1** (`go author … --target-version Y`).

## 5. Gates

- `plugin/scripts/validate_plugin.py` → **PASS (23 assertions)**.
- `tools/sync_plugin.py` → synced 4–5 mirrors, deny-audit clean, validation
  passed, zip rebuilt (4,982 KB, not committed); `--check` → in sync.
- `tools/dev/check_portable_paths.py` → ok (2,665 tracked; new names portable).
- New `tests/test_target_version_first.py` (bare-copy, `python -I -S`,
  sample-free): **12 passed in 8.5 s** — 2026/2025/2024 → own certified base
  in `result.release`; full 2025 build IS Revit 2025 + stamps in JSON; 2019 →
  exit 0, fallback, THE line, nearest 2024, IFC on disk; `go.inputs` detects
  2025; edit route `detected`/2026 without a flag; vocabulary; the creation
  skills ask the year before Step 1 and name the flag; edit skill states
  detection. Added to `tests/ci_shard.txt`.
- `tests/test_frontdoor.py` +4 (#123's four cases, in-process on the tracked
  bundled bases): env = bundled default + 2025 → match/G_ABPD_2025; + 2024 →
  match/G_ABPD_2024 (env restored after); + 2023 → fallback with the honest
  line; foreign wrong-release `--base` → refused.
- `tests/test_plugin_sync.py tests/test_bootstrap.py tests/test_coldstart.py
  tests/test_surface_perf.py tests/test_frontdoor.py tests/test_versions.py
  tests/test_plugin_validate.py` → 71 passed / 27 skipped (surface_perf's 4 are
  bench-gated skips; frontdoor's are owner-machine fixtures).
- CI shard exactly as CI runs it (`RVT_SKIP_LARGE=1`, every file in
  `tests/ci_shard.txt`) on the final tree → **187 passed / 23 skipped in 49 s**
  (main: 171/23; +12 new file, +4 test_frontdoor).
- `/verify` (front door + plugin surfaces, final tree): repo CLI
  `tools/frontdoor.py author --prompt "…6 panels" --target-version 2025 --json`
  → exit 0, `release` = 2025/2025/match/certified-base, `this_file`
  "validated-not-certified (combined: VALID 0 errors / 0 warnings)", 2 stamps;
  `rvt_analyze` → `release: 2025 (format 2025)`, identity ours. Final zip
  re-unzipped bare, `/usr/bin/python3`: `go author … --target-version 2025` →
  READY, exit 0, 19.7 s, match/2025, `detect_release` 2025; `--target-version
  2019` → exit 0, 4.9 s, THE line + `.rvt` + `.ifc`; `go rvt_edit.py
  assets/genesis/G_ABPD.rvt info` → exit 0, `go.inputs[0].revit_release 2026`.
  Pre-existing on `main`, not from this diff, stated rather than hidden:
  `tools/rvt_validate.py` false four-registry error and `tools/provenance.py`
  `unexpected Partitions header: v=9 cls=0x391` on the 2025 output (PR #91).
- Full suite NOT run (SUITE-COORDINATION). Nothing staged for the viewer: no
  certification claim; the bases used are the already-certified bundled ones.

## 6. Findings / follow-ups

- **Filed nothing new — every out-of-territory finding already has an issue,
  cited instead of duplicated:** bootstrap exports `RVT_GENESIS_BASE` → #92 /
  PR #126 (in flight; disjoint hunks — this branch deliberately leaves
  `ensure_engine` and GENESIS-BASE.md §4 as on `main`); standalone
  validator/analyze false four-registry error on 2025/2024 loaded content →
  PR #91 (#14) / #93; edit engine cannot open 2025/2024 projects → #70 (+#116,
  #121 for the other instruments); plugin agents/commands/README still describe
  the pre-`go` flow and "IFC default" → #119.
- #123 was unassigned + `auto`; claimed into this PR (comment on #123) because
  #24's DONE is unreachable without it and the worker would otherwise duplicate
  it within its 2 h cycle.
- Latency: cold ≈ warm (19.7 vs 18.9 s) — no cross-process warm cache on this
  path; wall time is the per-family sequential load stages (6 panels ≈ 6 × 2.5 s),
  release-independent. Same observation as PR #126's record; not acted on here.
- `tools/frontdoor.py _print_summary` (human mode) prints the version line
  only for `line`/`requested`; the `detected` case shows nothing in text mode.
  Cosmetic, hot file — left for whoever next holds it.

## BRANCH STATE

- Branch `cam/24-target-version-first` from `main@33622e3`; PR `Closes #24`, `Closes #123`.
- Files written: `src/rvt/frontdoor/__init__.py`, `src/rvt/frontdoor/target_status.py` (new),
  `tools/frontdoor.py` (hot, the one argument), `plugin/skills/_shared/tekton_env.py` (`go.inputs`),
  `plugin/skills/tekton-author/SKILL.md`, `plugin/skills/tekton-author/references/REVIT-VERSIONS.md` (new),
  `plugin/skills/tekton-edit/SKILL.md`, `plugin/skills/tekton-inspect/SKILL.md`,
  `plugin/skills/tekton-native/SKILL.md`, `skills/tekton-ifc/SKILL.md`,
  `tests/test_target_version_first.py` (new), `tests/test_frontdoor.py`, `tests/ci_shard.txt`,
  this record; mirrors regenerated by `tools/sync_plugin.py` (`plugin/lib/src/rvt/frontdoor/*`,
  `plugin/lib/tools/frontdoor.py`, `plugin/skills/tekton-author/scripts/frontdoor.py`,
  `plugin/skills/tekton-ifc/SKILL.md`).
- Gates: §5 green. Staged for the viewer: nothing. Shipped: takes effect in the next
  `tekton-plugin.zip` (git-ignored, rebuilt by `tools/sync_plugin.py`).
- Overlap notes for mergers: PR #126 (`tekton_env.py` lines 14-19/125-160/611-626,
  `GENESIS-BASE.md` §4, `tests/ci_shard.txt`) and PR #109 (`tools/frontdoor.py`
  epilog + `matrix` verb) touch the same files in disjoint hunks; whichever lands
  second rebases trivially. After #126 lands, the `is_our_default` branch here is
  belt-and-braces for legacy `--env` shells, as #123 intends.
