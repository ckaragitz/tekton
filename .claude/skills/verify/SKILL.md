---
name: verify
description: tekton's build-and-drive recipe for runtime verification before a commit — how to run the engine's real surfaces (front door CLI, validator/analyzer, router matrix, bare-unzip plugin `go` dispatch, family tools, the tech-lead process CLIs) from a fresh clone or cloud session, what output proves a change works, and what never counts as proof here (rule 4: only Autodesk's reader certifies "loads").
---

# Verify a tekton change by running it

This is a **process** skill (like `.claude/commands/*`), not a product skill — CLAUDE.md §3b's
"no product skills under `.claude/skills/`" still holds. It exists so every session drives the same
real surfaces the same way instead of re-deriving the recipe (or stalling on "no verify skill").
Verification here = runtime observation of OUR CLIs and files. It never certifies that Revit opens a
file (hard rule 4: only `docs/coverage/viewer-certified.json` does); say "validates 0 errors", never
"loads".

## Handle (setup, ≤ 1 min in a prepared cloud session)

```bash
[ -x .venv/bin/python ] || bash scripts/cloud-setup.sh          # venv + engine + pytest/numpy; idempotent
PY=.venv/bin/python
mkdir -p out/verify                                              # git-ignored working dir for outputs
```
Fresh clones have no `samples/`, `extracted/`, `vendor/` (quarantined corpora) and no built ladders
under `experiments/` — anything that needs them is owner-machine work, not verifiable here. What IS in
git and drives almost everything: the three certified composed bases
`plugin/assets/genesis/G_ABPD.rvt` (2026), `G_ABPD_2025.rvt`, `G_ABPD_2024.rvt`, and the schema caches.
Never read an Autodesk install directory (rule 2; the front door has a tripwire).

## Surfaces — pick the one your diff reaches

| Diff touches | Drive this | Healthy output |
|---|---|---|
| `src/rvt/frontdoor/**`, `tools/frontdoor.py`, prompt grammar, IFC intake | `$PY tools/frontdoor.py author --prompt "an electrical room with 6 panels" --out out/verify/p --json` (add `--target-version 2025` / `2024` for release work; `--ifc file.ifc` or `--rvt X.rvt --edit "move DP-1 to 3,1,4.66"` for those inputs) | JSON status `READY`, a `.rvt` (+ `.rfa`s) written, manifest stamped; then validate ↓ |
| anything that writes `.rvt` / `.rfa` (writer, mutate/manipulate, genesis ports, famgen, convert) | `$PY tools/rvt_validate.py out/verify/p/*.rvt --json out/verify/v.json` · families: `$PY tools/rvt_validate.py --family X.rfa` · `$PY tools/provenance.py X.rvt --baseline all --streams --json out/verify/prov.json` · `$PY tools/rvt_analyze.py X.rvt` | `errors=0` (exit 0) under the file's OWN release; provenance clean / 0 suspects (zero donor bytes, rule 3); analyze shows the expected release + census |
| validator / analyzer themselves (`src/rvt/validate.py`, `tools/rvt_*`) | run them on all three pinned bases + one deliberately damaged copy (`head -c 65536 base > out/verify/trunc.rvt`) + a non-CFB file | bases: `OK 0` exit 0; damaged: real errors + a stated fallback, no traceback; junk: 1 container error, exit 1 |
| router / matrix (`src/rvt/frontdoor/{router,matrix}.py`, `tools/route.py`) | `$PY tools/route.py matrix` · `$PY tools/route.py explain --output rvt --inputs prompt` · `$PY tools/route.py run --output rvt --prompt "an electrical room with 6 panels" --out out/verify/r --json` (inputs: `--prompt/--ifc/--rvt/--rfa/--spec`; `--target-version`, `--via`, `--strict` as needed) | the honest table; no cell claims "works" without evidence (`verify_evidence()` backs it) |
| edits (`src/rvt/manipulate.py`, `mutate.py`, `tools/rvt_edit.py`) | `$PY tools/rvt_edit.py …` or `frontdoor --rvt plugin/assets/genesis/G_ABPD_2025.rvt --edit "…" --out out/verify/e` | edited file validates 0 errors under its own release; the manifest names the edit |
| families (`src/rvt/famgen/**`, `famload.py`, `tools/make_family.py`) | `$PY tools/make_family.py …` / `$PY -m rvt.famload …` / the 6-panel prompt above (it generates + loads + places) · `$PY tools/make_family.py provenance X.rfa` | `.rfa` validates in `--family` mode, provenance clean, host symbol / registry tables as the record expects |
| plugin / skills / bootstrap (`plugin/**` sources, `skills/**`, `tools/sync_plugin.py`, `_shared/tekton_env.py`) | `$PY tools/sync_plugin.py` (rebuilds `tekton-plugin.zip`), then EITHER `$PY tools/surface_bench.py --zip tekton-plugin.zip --json out/verify/bench.json` OR by hand: `rm -rf out/verify/pz && mkdir -p out/verify/pz && cd out/verify/pz && unzip -q ../../../tekton-plugin.zip && python3 skills/tekton-author/scripts/_bootstrap.py go author --prompt "an electrical room with 6 panels" --out out/j1 --json; cd -` | `go` returns `READY` with system Python from a bare unzip (no repo on the path); families load; combined `.rvt` delivered. If this is not READY the product is broken whatever the tests say |
| process tooling (`tools/dev/techlead.py`, `coord.py`, `.claude/**`, workflows' inline bash) | `python3 tools/dev/techlead.py hello` · `… steer "text" --dry-run` · `… config pipeline.quiet_minutes` · `python3 tools/dev/coord.py queue --issues i.json --prs p.json` / `taskshape < body` · extract a workflow step's helper functions from the YAML and run them in `bash` (see `docs/inbox/autonomy.md` for the pattern) | banner in < 1 s and offline-safe; clean one-line errors (no tracebacks); queue order P0 > P1 > rest; helpers behave on real-shaped payloads. Workflows themselves only run from `main` — say so rather than faking it |
| viewer / certification claims | `$PY tools/probe_batch.py check|stage …` — STAGE only, stop at READY | a staged batch (certified base + byte-identical control); a human uploads; you record nothing in the ledger yourself |

## Probes worth one extra minute

Wrong `--target-version` for an older base (must warn/refuse honestly, never emit a 2026 file as
"2025"); empty/typo'd prompt; `--ifc` on a non-IFC file; validator on a truncated file (fallback
stated, no crash); `go` with no numpy on the path (ECC degrades with a warning, still delivers —
rule 1); running the same build twice (determinism where the record promises it).

## Report

Inline in your PR body under "Gates run": the exact commands and the numbers they printed
(`READY`, `errors=0`, provenance `0 suspects`, bench wall time). A file path alone is not evidence
for a reviewer who cannot open your sandbox — paste the lines that matter.
