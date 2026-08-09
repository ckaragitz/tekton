# pyproject-extras — issue #3

## What was built

`pyproject.toml` now declares its optional dependency sets instead of leaving
them to prose. `dependencies` stays exactly `["olefile>=0.47"]` (CLAUDE.md §2:
the only declared runtime dep); everything heavier is an extra:

| extra | contents | for |
|---|---|---|
| `test` | `pytest>=7`, `numpy>=1.26,<3` | running the suite (most tests reach the geometry/intent math, so numpy rides along) |
| `geometry` | `numpy>=1.26,<3` | the author/intent routes' math at runtime, without pytest |
| `ifc` | `ifcopenshell==0.8.5`, `numpy>=1.26,<3` | IFC **authoring** (tekton-ifc skill) and `ifcopenshell.validate` only — pins mirror `skills/tekton-ifc/scripts/requirements.txt` |
| `dev` | test + geometry | a coding session's install, no heavy optional backend |
| `all` | dev + ifc | everything |

`ifcopenshell` is in `ifc`/`all` only — never a runtime dependency, never in an
extra a contributor installs by default. IFC *reading* stays zero-install via
`rvt.ifc.steplite` (product requirement, `docs/product/SURFACE-PLAYBOOK.md`;
`docs/writer/dependency-audit.md` F2: an installed ifcopenshell taxes every
process +0.3 s warm / +4.5 s first).

The three setup surfaces now install through the same extra:

- `scripts/cloud-setup.sh`: `pip install -e ".[test]"`, then the optional,
  non-fatal `pip install -e ".[ifc]" || note` (the pin now has one home).
- `README.md` "Reproduce": `-e ".[test]"` for uv and plain venv/pip, a
  fresh-clone-safe test file instead of "full suite", the owner-machine
  absolute python path replaced by the repo's `.venv/bin/python`, one
  paragraph naming the extras. (The wider README refresh is #4's territory
  and was left alone.)
- `CLAUDE.md` §2: the two install lines and the parenthetical only — the old
  comment "test/geometry extras are NOT declared in pyproject" would have
  become false. Hot-ish file; diff is 3 lines out, 4 in.

Guard: `tests/test_pyproject_extras.py` (8 tests, 0.07 s, fresh-clone safe,
added to `tests/ci_shard.txt`): olefile-only runtime deps; the five extras
exist and mean the table above; ifcopenshell never in `test`/`geometry`/`dev`
or `dependencies`; `ifc` pins == the tekton-ifc `requirements.txt` lines
(bump both together); every requirement string is valid PEP 508; README,
CLAUDE.md and cloud-setup.sh all contain `.[test]`.

Not touched, on purpose: `.github/workflows/ci.yml` still installs
`-e .` + `pytest numpy` by hand (works; workflow files cannot be bot-merged)
→ filed as **#100**. `plugin/lib/pyproject.toml` is a separate hand-authored
manifest for the bundled engine (its own `verify` extra), not a mirror of the
root file — `sync_plugin.py --check` stays clean.

## Evidence

Fresh environments, this branch's tree, PyPI through the sandbox proxy:

| environment | command | result |
|---|---|---|
| `python3 -m venv` (3.11.15, pip 26.2.1) | `pip install -e ".[test]"` | exit 0 in 9.7 s; installed rvt 0.1.0 (editable) + olefile 0.47 + pytest 9.1.1 + numpy 2.4.6; `import ifcopenshell` → `ModuleNotFoundError` (as intended) |
| same venv | `pytest tests/test_versions.py tests/test_pyproject_extras.py -q` (the issue's *How to verify*) | `23 passed, 19 skipped in 0.15s` (skips = samples-gated version cases) |
| same venv | `pip install --dry-run -e ".[all]"` / `".[ifc]"` / `".[geometry]"` / `".[dev]"` / `".[test,ifc]"` | all exit 0; `all` resolves ifcopenshell 0.8.5 + isodate, lark, python-dateutil, six, shapely 2.1.2, typing_extensions |
| `uv venv --python 3.12` (uv 0.8.17) | `uv pip install -e ".[test]"` (the README/CLAUDE.md spelling) | exit 0 in 2.1 s; numpy 2.5.1, olefile 0.47, pytest 9.1.1, rvt 0.1.0; same two test files `23 passed, 19 skipped in 0.26s` |
| worktree, no `.venv` | `bash scripts/cloud-setup.sh` | `cloud-setup: READY` in 27.1 s; installed the test extra and (network available) ifcopenshell 0.8.5 + shapely via the optional `ifc` extra; second run idempotent, READY in 7.6 s |

Repo gates (canonical interpreter `/home/user/tekton/.venv/bin/python`):

```
tests/test_pyproject_extras.py -q          8 passed in 0.07s
tools/sync_plugin.py --check               plugin in sync with source (deny-audit clean, assets verified)   exit 0
tools/dev/check_portable_paths.py          ok: 2667 tracked paths are portable
plugin/scripts/validate_plugin.py          assertions passed: 23 / RESULT: PASS
CI shard (16 files, RVT_SKIP_LARGE=1)      178 passed, 23 skipped in 66.67s
```

No `src/`, `tools/`, `skills/` or `plugin/` file changed, so there were no
mirrors to regenerate. No `.rvt`/`.rfa` is produced *by this change*; the one
built during verification below validated `error: 0` and is not shipped. No
certification claim.

## Verification (runtime, per `.claude/skills/verify`)

**Verdict: PASS.** Claim = "a fresh clone sets up through the declared extras
and the resulting venv is a working handle on the engine; ifcopenshell stays
optional and non-fatal". Method: the verify skill's own handle step *is* the
changed script, so the surface is a contributor's documented setup commands,
then one real front-door job from the venv they produce.

1. ✅ `bash scripts/cloud-setup.sh` in the worktree (no `.venv`) → `tekton engine import OK … plugin in sync … ok: 2665 tracked paths are portable … cloud-setup: READY` (27.1 s).
2. ✅ From that venv: `.venv/bin/python tools/frontdoor.py author --prompt "an electrical room with 6 panels" --out out/verify/p --json` → exit 0 in 35 s, `ok: True`, `status: PROOF-ONLY (self-checks PASS …)`, delivered `prompt_room.rvt` + 6 `.rfa` + manifest/handoff; `tools/rvt_validate.py out/verify/p/prompt_room.rvt` → `counts = {'error': 0, 'warning': 1, 'info': 2}`, exit 0 (the warning is the known DataStorage Extensible-Storage decoder gap). Validates 0 errors; no "loads" claim.
3. 🔍 Typo'd extra, `pip install --dry-run -e ".[tests]"` → `WARNING: rvt 0.1.0 does not provide the extra 'tests'`, exit **0**, would install rvt only. `uv` likewise: `warning: … does not have an extra named `tests``, exit 0. (Finding below.)
4. 🔍 The optional line offline: `python -m pip install -q -e ".[ifc]" --no-index 2>/dev/null || echo "note: …"` in a venv without ifcopenshell → prints `note: ifcopenshell not installed (optional; IFC authoring only)`, compound exit 0; afterwards `import rvt, rvt.frontdoor.build, numpy` still fine and `find_spec('ifcopenshell') is None` — a failed optional step leaves the engine install intact.
5. 🔍 Console entry point from the extras venv: `v/bin/rvtinspect --help` → `usage: rvtinspect [-h] {ls,hexdump,dump,strings} ...`.
6. 🔍 Idempotency: second `bash scripts/cloud-setup.sh` → READY in 7.6 s, no reinstall churn.

### Findings

- ⚠️ pip and uv only *warn* on an unknown extra name and exit 0, so a
  contributor who types `.[tests]` gets an engine with no pytest and one easy
  to miss warning line. Nothing pyproject can do about it; the mitigation is
  that README, CLAUDE.md and cloud-setup.sh all spell the exact extra and the
  guard test keeps them spelling the same one.
- `cloud-setup.sh` with network *does* install ifcopenshell (as it did before
  this change, now pinned). Per dependency-audit F2 that costs every later
  process ~0.3 s of import. Kept as-is because changing the cloud posture was
  not this issue; if prompt-only latency in cloud sessions matters, dropping
  the optional line (or gating it behind `TEKTON_WITH_IFC=1`) is a one-line
  follow-up worth its own issue and a measured before/after.
- `out/` at the repo root is untracked but **not** git-ignored (only
  `experiments/out/` and `tests/out/` are); the verify skill writes there. I
  deleted it before committing. Worth an ignore line some day; not in this
  territory.

## Open questions / follow-ups

- **#100** — CI installs through `pip install -e ".[test]"` (workflow file →
  `session-merge` path), optionally guarded by adding `ci.yml` to the setup-
  surfaces parametrization in the guard test.

## BRANCH STATE

- Branch: `cam/3-pyproject-extras`, cut from `origin/main` @ 35529eb, rebased
  onto 33622e3 before pushing (clean; guard, portable paths and drift check
  re-run green on the rebased tree), not stacked.
- Files written: `pyproject.toml`, `scripts/cloud-setup.sh`, `README.md`
  ("Reproduce" section only), `CLAUDE.md` (§2 install lines only),
  `tests/test_pyproject_extras.py` (new), `tests/ci_shard.txt` (+1 line),
  `docs/inbox/pyproject-extras.md` (this record).
- Gates: guard 8 passed; `sync_plugin.py --check` in sync; portable paths ok;
  `validate_plugin.py` PASS (23 assertions); CI shard 178 passed / 23 skipped;
  fresh-venv installs (pip 3.11, uv 3.12) and `cloud-setup.sh` READY as above.
- Staged vs shipped: shipped (metadata, setup script, docs, test). No viewer
  certification claim; nothing STAGED.
- Follow-up filed: #100 (CI uses the extra).
