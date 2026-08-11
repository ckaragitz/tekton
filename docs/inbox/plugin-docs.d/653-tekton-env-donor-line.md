# #653 -- the bootstrap stops reporting a family donor (`tekton_env.py` readiness line + doctor)

Stream `plugin-docs`, fragment for issue #653 (Refs #511, #498 / steer S-2026-08-10-c). Voice: eng #653.

## What was built
The shipped bootstrap `plugin/skills/_shared/tekton_env.py` no longer computes, reports or advises
the retired `$RVT_FAMILY_DONOR`:

1. **Readiness field dropped, not replaced.** `preflight()` loses `res["family_donor"]` and the
   readiness line loses its `family-donor <status>` segment; `family_donor_status()`,
   `FAMILY_DONOR_ENV`, `FAMILY_DONOR_DIR_REL` and the `__all__` entry are gone. *Why drop rather
   than print a constant `families self-generated`:* the one-line readiness report exists to name
   the one thing that can be wrong; a segment that can never vary carries no information and costs
   bytes on every `go` call's JSON (S-2026-08-09-g). The honest constant statement lives where prose
   belongs -- the doctor. **JSON shape change, said loudly:** the preflight dict (`_bootstrap.py --json`,
   and `go`'s inline preflight) no longer has a `family_donor` key. Consumers checked:
   `git grep '"family_donor"|pf\["family_donor"\]'` over `tools/ src/ plugin/commands plugin/agents
   plugin/README.md plugin/docs skills/` finds none (`go()` reports only `ready`/`preflight_line`;
   `tools/surface_bench.py:138` merely scrubs the env var from the simulated VM's environment --
   harmless, left as is, outside territory); the only reader was `tests/test_bootstrap.py`.
2. **`doctor()`** prints `family container: bundled (genesis base)` unconditionally with a two-line
   constructive-ADocument note in the words `plugin/commands/tekton-doctor.md` item 4 (#654) already
   uses -- "(every family is self-generated: the .rfa ADocument is authored CONSTRUCTIVELY from the
   bundled schema; no donor and no user file is needed or read; nothing under an Autodesk installation
   is ever read or probed)" -- the last clause restored on review so doctor's stdout keeps main's
   never-read-Autodesk assurance (test asserts `"Autodesk" in doc.stdout`). The `($RVT_FAMILY_DONOR stays as an
   expert override, e.g. a non-2026 target release …)` paragraph, the `user-supplied donor (<path>)`
   branch and the stale "empty registries -- desktop acceptance tracked in issue #52" clause are gone
   (the per-release / `--target-version` policy text stays in tekton-doctor.md item 4 only, so the two
   cannot drift -- `/simplify` altitude finding). Nothing else in the bootstrap changed: preflight
   timing, `go` dispatch, exit codes, every other JSON key identical (test asserts the dict with and
   without the variable set is equal modulo `seconds`/`line`).
3. **The four identical `scripts/_bootstrap.py` shims** (`tekton-author/-edit/-inspect/-native`) each
   lose the one re-export line `family_donor_status = _env.family_donor_status` -- unavoidable: with
   the function gone that line raises `AttributeError` at import and the whole bootstrap is dead.
   Shims stay byte-identical to each other (diffed).
4. **`tests/test_bootstrap.py`**: the two donor cases (`user_supplied_env`, `bundled_asset_dir`)
   replaced by `test_retired_family_donor_env_changes_nothing` (preflight JSON equal with/without
   `RVT_FAMILY_DONOR` pointing at a real file, `family_donor` key absent; `doctor` with the variable
   set exits 0, prints the family container line and none of `FAMILY_DONOR` / `family-donor` /
   `user-supplied donor` / `override, e.g.`) -- three subprocesses, the same count the two old tests
   spent; the first preflight test asserts `family_donor` absent from the dict and the line. No other
   test pinned the line (`git grep -n "family-donor\|FAMILY_DONOR" -- tests plugin`).
5. **`plugin/skills/tekton-author/SKILL.md:124` (hot, territory extended by the tech lead on the
   issue):** ONE line, "`family-donor missing` is fine — everything is" → "no family file is ever
   needed — everything is"; frontmatter untouched; `wc -c` 14077 → 14076.
6. **`plugin/agents/tekton-author-agent.md:25-26`** carried the very same clause ("`family-donor
   missing` in the line is normal") -- not named in the territory, but hand-authored, not hot, and
   false the moment (1) lands, so it got the same two-line reword ("No family file is ever needed:
   everything builds from the bundled bases"). Flagged in the PR for the reviewer to veto if they
   would rather have it as its own issue.

## Evidence
* Grep, before → after: `git grep -n "RVT_FAMILY_DONOR\|family_donor\|family.donor" -- plugin/skills plugin/commands plugin/README.md`
  = **18 hits** on `origin/main` @ 9152c86 (`tekton_env.py` ×13 incl. the doctor override line,
  `tekton-author/SKILL.md:124`, the four shims ×1) → **1 hit**: `tekton_env.py:52`, the module
  docstring sentence stating the donor path is retired (#498/#653), which the DONE explicitly allows.
  `plugin/commands` and `plugin/README.md`: 0 → 0.
* Readiness line before → after (repo tree, system python 3.11, numpy absent):
  `tekton: READY | python 3.11.15 | engine bundled | genesis verified (Revit 2026) | family-donor missing | ifc-route needs numpy (…) | out-dir OK | 0.045s`
  → `tekton: READY | python 3.11.15 | engine bundled | genesis verified (Revit 2026) | ifc-route needs numpy (…) | out-dir OK | 0.019s`;
  with `RVT_FAMILY_DONOR=/etc/hostname` the old line said `family-donor user-supplied`, the new line is
  identical to the unset case. Preflight keys: `[engine, extras, family_donor, genesis_base, line, ok,
  out_dir, plugin_root, python, routes, seconds, specimen]` → same minus `family_donor`.
* Gates `RVT_SKIP_LARGE=1 pytest tests/test_bootstrap.py tests/test_coldstart.py tests/test_surface_perf.py
  tests/test_plugin_validate.py tests/test_plugin_sync.py tests/test_records_layout.py -q -rs`:
  **50 passed / 0 skipped (15.0 s) → 49 passed / 0 skipped (14.7 s)** (two donor tests → one).
* `tools/sync_plugin.py` rebuilt the zip (5350 KB → 5349 KB), deny-audit clean, identity scan 82 hits /
  0 mismatches; `--check`: "plugin in sync with source"; `plugin/scripts/validate_plugin.py`: PASS (25
  assertions); `tools/dev/check_portable_paths.py`: ok (3035 tracked paths + this new fragment, name per the
  `docs/inbox/README.md` law; `tests/test_records_layout.py` green).
* Latency (S-2026-08-09-g), `tools/surface_bench.py --zip tekton-plugin.zip --surfaces cowork,local
  --jobs preflight,go-author-6panels` (cowork / local), before → after on the final head: preflight
  0.1 s / 0.1 s → 0.1 s / 0.1 s; go-author-6panels 4.0 s / 4.0 s → 4.0 s / 3.6 s; all 4 job cells PASS
  both runs. Flat, as predicted (one `os.path.isdir` fewer per preflight is below the timer's resolution).
* `/verify` = the bare-unzip drive on the final zip: `unzip tekton-plugin.zip` into a scratch dir with
  a space in its path, system `python3 skills/tekton-author/scripts/_bootstrap.py go author --prompt
  "an electrical room with 6 panels" --out out/j1 --json` → exit 0, wall 4.11 s (4.03 s on the
  pre-simplify head; main's bench 4.0 s), `go.ready true`, `preflight_line` as above (no family
  segment), `result.status` "PROOF-ONLY (self-checks PASS …)", `errors []`, `out/j1/prompt_room.rvt`
  720,896 bytes delivered (validated-not-certified, rule 4 -- unchanged lane); `doctor` from the same
  unzip prints the new three-line family container block.
* Whole merged CI shard: not run here (the tech-lead sandbox runs it on the head).

## Findings / open questions
* `plugin/commands/tekton-doctor.md` item 4 keeps the hedge "any leftover donor/override wording in
  the report changes nothing in the build" -- now vacuous (there is no leftover wording) but still
  true; left alone (commands were #654's territory). A later prose pass may drop the parenthesis.
* `tools/surface_bench.py:138` still scrubs `RVT_FAMILY_DONOR` from the simulated environment; inert.
* `tekton-eval-kit/tekton-plugin/**` is a frozen snapshot of an older plugin and still carries the old
  bootstrap; not shipped by `sync_plugin`, not touched.
* `/simplify` (four angles) -- applied: test collapsed to straight-line code at the old subprocess
  count, doctor note cut from six policy lines to the two-line ADocument note, one "documenting an
  absence" docstring clause dropped. Skipped on purpose: inlining `_supplied_or_bundled` into its one
  remaining caller `specimen_status` (behaviour-preserving but outside "readiness field + doctor text
  only"; a one-screen follow-up if wanted).

### BRANCH STATE
* branch `cam/653-tekton-env-donor-line` from `origin/main` @ 9152c86
* written: `plugin/skills/_shared/tekton_env.py`, `plugin/skills/{tekton-author,tekton-edit,tekton-inspect,tekton-native}/scripts/_bootstrap.py`
  (one identical line each), `tests/test_bootstrap.py`, `plugin/skills/tekton-author/SKILL.md` (one
  line, hot), `plugin/agents/tekton-author-agent.md` (two lines), `docs/inbox/plugin-docs.md` (one
  index line), this fragment
* gates: as above -- 49 passed, sync + `--check` clean, validate_plugin PASS, portable ok, bench flat,
  bare-unzip `go author` READY / exit 0
* shipped vs staged: bootstrap text + one JSON key removal; nothing staged for the viewer; no engine change
