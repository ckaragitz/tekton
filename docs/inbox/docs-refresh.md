# docs-refresh — repo-root docs brought up to today's truth (issue #4)

Stream: `docs-refresh` · issue #4 (P1, area:docs) · branch `cam/4-docs-refresh` ·
session `eng4` (engineer session started by the tech-lead session; claim 🔒 comment
5231347933). Docs only; no code, no plugin sources, no hot files.

## What was stale → what it says now

| File | Stale claims found (2026-08-09) | Now |
|---|---|---|
| `README.md` | Front door "landed 2026-08-04; its stream is still active", output under `experiments/frontdoor/<name>-<stamp>/`, only `--prompt/--ifc/--rvt` (no `--target-version`, no `route.py`, no `go`); "milestone just reached: GENESIS LOADS" (2026-only, pre-2025/2024 certification); an *Honest scope* table naming "created walls + loaded family documents" as the open bug (exonerated — the open cell is placed *instances* of generated families on composed bases) and RENDER "in progress"; a CRUD-matrix section quoting a 2026-08-04 `coverage.py` run (13.2 % certified …) as the headline capability measure (superseded by the permutation matrix + ledger); layout table naming `rvt_job.py` as the front door; "read `AGENT_BRIEF.md` before touching anything"; nothing about the plugin being the product, skills asking the year first, REQUIREMENTS.md, AUTONOMY.md or the board. | What tekton is (engine + plugin; plugin is the product → `plugin/README.md`); naming/trademark/private-evaluation posture kept; a **"start here" table** (CLAUDE.md = law, plugin README, `route.py matrix`/PERMUTATION-MATRIX, ledger, PROGRAM/REQUIREMENTS/TRACKER, AUTONOMY + board #56, KNOWLEDGE, COUNSEL-BRIEF); **setup via `scripts/cloud-setup.sh` / `.[test]`** and the three front-door inputs + validate + matrix + the bare-unzip `go author` call — every command is one run in this session (below) with its observed timing/result; **honest scope** = certified (2026/2025/2024 bases, walls, edits, famgen, .rfa load, extract→place, add_to_project) vs the one open cell (#16) vs PROOF-ONLY gates, all pointing at the ledger and the matrix instead of restating numbers; the **8 hard rules one line each → CLAUDE.md §1**; layout; how work is done (3 sentences → CLAUDE.md §4 / AUTONOMY). |
| `AGENT_BRIEF.md` | The wave-1 format-analysis fleet brief: absolute `/Users/ck/dev/things/…` paths, "all files are Revit 2026", instructions to decode from `extracted/` (quarantined, absent on a fresh clone), "never edit tools/ … README", machine-consumed return value. Contradicted CLAUDE.md on setup, paths and process. | Reduced to a **pointer to `CLAUDE.md`** plus a short historical note saying what the brief established and where each part lives now (purpose statement — kept because `docs/product/COUNSEL-BRIEF.md:134` cites this file for the interoperability purpose; evidence/territory discipline → CLAUDE.md §4; format facts → KNOWLEDGE.md / docs/streams, now multi-release; corpus = quarantined; absolute paths gone). |
| `SHARE-README.md` | "CREATE new content into a base file YOU provide (`--template-rvt`); no template ships with this build"; honest-status gates = "legal review + an in-house genesis base in progress" (genesis bases are certified and bundled for three releases now); feature list led with panel schedules/load calcs; no target-version rule; no validator-vs-Autodesk distinction; no open-cell statement. | Private-evaluation framing and the "tell us what Revit says" ask kept (now also asks the Revit year); install one-liners match `plugin/README.md` and point to the README inside the zip; *what works today* = create natively for 2026/2025/2024 (year asked first, older → file + one line + IFC), famgen/load/place incl. into the user's project, edit, inspect/validate, IFC author/validate/harden/convert; *honest status* = PROOF-ONLY as a label with the three gates, validator ≠ acceptance, the open cell stated as the matrix states it (placed instances of generated families on our bases; `--strict`), circuits planned not authored; trademark attribution line. |
| `RENAME.md` | Self-contradictory after the display-name sweep ("tekton / rvt → tekton", "now `~/dev/things/tekton/` → after `~/dev/things/tekton/`"), Step 0 listed as todo (done: `grep -rn '/Users/ck/dev/things' src/` = nothing), genesis strings listed as todo (done: `house_standard.py` says `tekton genesis` / `tekton`). Policy itself still current and cited by `docs/PROGRAM.md` "Not goals". | **Marked, not rewritten:** title fixed and a dated status banner added — what has been executed (display name, repo/dir, manifest, genesis strings, Step 0), what has not and why (C1 author placeholder, package `rvt`, §2-C component names, clearance), that the no-piecemeal rule stands, and that §4's counts are a 2026-08-04 owner-machine snapshot to re-measure. The inventory and runbook body are left as the historical record. |

Out of territory, filed instead of fixed: **#261** (old working name still presented as the product name in `docs/product/architecture.md`, `content-strategy.md` title, `COUNSEL-BRIEF.md:1`, `docs/electrical-calcs.md:143` wrong JSON kind, `docs/writer/house-standard.md:229`, `docs/legal/provenance-memo.md`, `docs/SESSION-REPORT.md`; with the list of hits that must stay as evidence). Searched first: no existing issue (`rev-revit docs/product` → only #4; open `area:docs` list reviewed, #226 is dangling paths, not names). `plugin/README.md` was read as the reference and found current (PR #238); nothing to file there.

## Commands run in this session (fresh cloud clone, no `samples/`), in README order

```
$ bash scripts/cloud-setup.sh
… tekton engine import OK
  WARNING required asset source missing: experiments/genesis/subst_k4/compose/G_ABPD.rvt   (x3: expected on a fresh clone — the plugin's pinned copies are used)
plugin in sync with source (deny-audit clean, assets verified)
ok: 2710 tracked paths are portable
cloud-setup: READY  (.venv/bin/python; run tests with .venv/bin/python -m pytest tests/test_<yours>.py -q)

$ .venv/bin/python -m pytest tests/test_versions.py tests/test_frontdoor.py -q
54 passed, 23 skipped in 0.42s
$ .venv/bin/python -m pytest tests/test_pyproject_extras.py -q          # asserts README.md still installs through ".[test]"
8 passed in 0.07s
$ .venv/bin/python tools/sync_plugin.py --check
plugin in sync with source (deny-audit clean, assets verified)

$ time .venv/bin/python tools/frontdoor.py author --prompt "an electrical room with 6 panels" --out out/demo --json
real 0m9.777s · ok=true · route=prompt · seconds=9.6 · files={combined: out/demo/prompt_room.rvt, families_dir: out/demo/families}
release: output 2026, "Revit 2026 and newer -- never an older Revit", target_support certified-base,
         this_file "validated-not-certified (our gate: combined: VALID 0 errors / 1 warnings; Autodesk acceptance only when … opens it)",
         ask "no --target-version given: … ask the user's Revit version before promising a .rvt (the tekton-author skill asks first)."
status "PROOF-ONLY (self-checks PASS; see honesty.proof_only_stamps + status_gate)"; out/demo has HANDOFF.md MANIFEST.md PROMPT_TO_IFC.md intent.json manifest.json prompt_room.rvt scene-brief.json families/

$ time .venv/bin/python tools/frontdoor.py author --prompt "an electrical room with 6 panels" --target-version 2025 --out out/r25 --json
real 0m8.907s · ok=True · release.output 2025 · this_file "validated-not-certified (… VALID 0 errors …)"

$ time .venv/bin/python tools/frontdoor.py author --ifc inputs/ifc/electrical-room-2500a.ifc --target-version 2024 --out out/r24 --json
real 0m11.831s · ok=True · files.combined out/r24/electrical-room-2500a.rvt · release.output 2024 · "VALID 0 errors / 0 warnings" · status PROOF-ONLY (self-checks PASS; …)

$ time .venv/bin/python tools/frontdoor.py author --rvt out/demo/prompt_room.rvt --edit "move PP-2 to 3,1,4.66" --out out/e --json
real 0m1.874s · ok=True · files.edited out/e/prompt_room.edited.rvt · status "PROOF-ONLY, NOT-DELIVERABLE (hard gates PASSED)"
(first tried CLAUDE.md's example sentence "move DP-1 …" against this file: ok=False, errors ["edit not understood: no element named 'DP-1' in this file"] in 0.25 s —
 correct behaviour, one clear line; the README example therefore names PP-2, which the 6-panel prompt really creates: intent equipment = PP-1..PP-6)

$ time .venv/bin/python tools/rvt_validate.py out/demo/prompt_room.rvt --json out/demo.validation.json
real 0m0.807s · ok true · counts {error: 0, warning: 1, info: 2} · records 10419 · elements_decoded 3466
[WARNING] semantic objects: 1/3466 seq-102 records failed schema decode (DataStorage x1) — known decoder gap

$ .venv/bin/python tools/route.py matrix
21 cells: 17 works / 1 partial / 3 missing … evidence self-audit: every citation checks out against the ledger and the tree (21 cells, 20 stages, 5 chains).

$ .venv/bin/python tools/sync_plugin.py
synced 0 file(s) into plugin/ · deny-audit clean; assets verified · √ Validation passed · rebuilt tekton-plugin.zip (5030 KB)
$ cd <scratch>/bare && unzip -q tekton-plugin.zip && time python3 skills/tekton-author/scripts/_bootstrap.py go author --prompt "an electrical room with 6 panels" --target-version 2025 --out out/j1 --json
real 0m8.187s · exit 0
go = {"one_call": true, "ready": true, "preflight_line": "tekton: READY | python 3.11.15 | engine bundled | genesis verified (Revit 2026) | family-donor missing | out-dir OK | 0.045s", "job_seconds": 8.008, …}
result = ok True · files.combined …/out/j1/prompt_room.rvt · release.output 2025 "Revit 2025 and newer -- never an older Revit" · status PROOF-ONLY (self-checks PASS; …)
```

## Gates

```
$ grep -rniE "rev-revit|APS Design Automation|Design Automation|pip install \./lib" README.md AGENT_BRIEF.md SHARE-README.md RENAME.md    → (nothing, rc=1)
$ git grep -n -i rev-revit -- README.md AGENT_BRIEF.md SHARE-README.md RENAME.md                                                     → (nothing)
$ git grep -n -i rev-revit -- ':!docs/inbox' ':!KNOWLEDGE.md'   → reviewed: 233 files — 206 experiments/ records + manifests (baked historical
    paths), 14 docs/ (filed as #261 or listed there as must-stay evidence), 11 tests/ + tools/make_v18/19 (the V18/V19 marker bytes = certified evidence), 0 root, 0 src/plugin/skills.
$ .venv/bin/python tools/dev/check_portable_paths.py      → ok: 2710 tracked paths are portable   (2711 with this record)
$ .venv/bin/python plugin/scripts/validate_plugin.py      → assertions passed: 24 · RESULT: PASS — plugin structure is valid   (unchanged; plugin untouched)
$ .venv/bin/python tools/sync_plugin.py --check           → plugin in sync with source
```

`/verify` not run — docs-only change with no runtime surface (commit trailer `No-Verification-Needed: docs-only change`).
No `.rvt` shipped by this PR (the outputs above live in git-ignored `out/`); no viewer claim; no hot file touched.

## Findings / open questions

- CLAUDE.md §2's edit example (`--edit "move DP-1 to 3,1,4.66"`) is illustrative; against the flagship 6-panel output it correctly answers "no element named 'DP-1'". Not a bug and CLAUDE.md is hot — noted here only so nobody files it.
- `RENAME.md` is now half history; when counsel answers, the sweep issue should re-measure §4 rather than trust it (said in the banner).

## BRANCH STATE

- Branch `cam/4-docs-refresh` from `origin/main` @ 5a40b22.
- Files written: `README.md`, `AGENT_BRIEF.md`, `SHARE-README.md` (rewritten), `RENAME.md` (title + status banner only), `docs/inbox/docs-refresh.md` (this record). Nothing else.
- Gates: portable paths ok · validate_plugin PASS · sync `--check` clean · `test_versions`+`test_frontdoor` 54 passed/23 skipped · `test_pyproject_extras` 8 passed · grep checks empty.
- Follow-up filed: #261 (`Refs #4`). Shipped vs staged: docs only, nothing staged for the viewer.
- PR: opened ready (not draft) with `Closes #4`; Auto-fix/PR subscription on; serviced until merged.
