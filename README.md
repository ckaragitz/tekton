# tekton

**tekton is a pure-Python interoperability engine plus a Claude plugin that
reads, creates, edits, validates and converts Autodesk® Revit® `.rvt` /
`.rfa` files — without a Revit install, an Autodesk seat, or any cloud
conversion service in the loop.** A prompt, an IFC, or an existing Revit
file goes in; a `.rvt` / `.rfa` (or IFC) that a licensed engineer opens in
their own Revit release for QA comes out. Revit is the last-mile
*deliverable* format; the content inside a tekton file is ours
(constructor-built from our own data and the user's inputs).

**The product is the plugin** — the skills, commands and agents under
[`plugin/`](plugin/README.md), shipped as `tekton-plugin.zip` and backed by
the engine in `src/rvt/`. If you want to *use* tekton, read
[`plugin/README.md`](plugin/README.md) (install on Claude Code / Cowork /
claude.ai, the 5-minute quickstart, the honest status). This file is the map
of the *repository* for the people and coding sessions that build it.

> **Naming and posture.** The display name is *tekton*; the Python package
> stays `rvt` (it names the file format it handles) and nothing else is
> renamed piecemeal — see [`RENAME.md`](RENAME.md). "tekton, for use with
> Autodesk® Revit®" is referential use; Autodesk and Revit are registered
> trademarks of Autodesk, Inc. This is a **private evaluation build**: every
> output is stamped `PROOF-ONLY` until the deliverability gates clear
> (§ Honest scope), and the repository itself stays private
> ([`CLAUDE.md`](CLAUDE.md) §1 rule 6).

---

## Start here — which document answers what

| You want to… | Read |
|---|---|
| work in this repo (human or coding session) — rules, setup, commands, process | [`CLAUDE.md`](CLAUDE.md) — **the working guide and the law**; if anything here disagrees with it, `CLAUDE.md` wins |
| install and use the product | [`plugin/README.md`](plugin/README.md) |
| know exactly what works, per input → output, with evidence | `.venv/bin/python tools/route.py matrix` (machine truth) / [`docs/product/PERMUTATION-MATRIX.md`](docs/product/PERMUTATION-MATRIX.md) |
| know what Autodesk's reader has actually accepted | [`docs/coverage/viewer-certified.json`](docs/coverage/viewer-certified.json) (the certification ledger) + [`docs/inbox/genesis-audit.md`](docs/inbox/genesis-audit.md) (verdict log) |
| see the goals and the requirement map | [`docs/PROGRAM.md`](docs/PROGRAM.md), [`docs/product/REQUIREMENTS.md`](docs/product/REQUIREMENTS.md), [`TRACKER.md`](TRACKER.md) (curated roadmap) |
| understand how work is planned, claimed, reviewed and merged | [`CLAUDE.md`](CLAUDE.md) §4, [`docs/process/AUTONOMY.md`](docs/process/AUTONOMY.md), the pinned 📋 board issue [#56](https://github.com/ckaragitz/tekton/issues/56) |
| understand *why* things are the way they are (format laws, dead ends, verdicts) | [`KNOWLEDGE.md`](KNOWLEDGE.md) |
| see the counsel posture (author string, corpora, footer token, trademark) | [`docs/product/COUNSEL-BRIEF.md`](docs/product/COUNSEL-BRIEF.md) |

---

## Setup and a first run (fresh clone, no samples needed)

Python 3.11+; the only declared runtime dependency is `olefile`. Always run
from the repo root with `.venv/bin/python`.

```bash
bash scripts/cloud-setup.sh                     # = python3 -m venv .venv && .venv/bin/pip install -e ".[test]", plus drift/portability checks; ends "cloud-setup: READY"
# (uv users: uv venv .venv && uv pip install --python .venv/bin/python -e ".[test]")
.venv/bin/python -m pytest tests/test_versions.py tests/test_frontdoor.py -q    # fresh-clone-safe files (~1 s); the per-PR shard is tests/ci_shard.txt
.venv/bin/python tools/sync_plugin.py --check   # plugin mirror drift guard: "plugin in sync with source"
```

Extras in `pyproject.toml`: `test` (pytest + numpy — what the suite needs),
`geometry` (numpy), `ifc` (ifcopenshell — **optional**, IFC *authoring* only;
IFC *reading* uses the stdlib reader `rvt.ifc.steplite`), `dev`, `all`. The
full suite is ~1,700 tests / ~25 min and is coordinated — run your
stream-local files, not `tests/` ([`CLAUDE.md`](CLAUDE.md) §2).

**The front door** — one entrypoint, exactly one of `--prompt` / `--ifc` /
`--rvt --edit`, `--target-version {2026,2025,2024}` as a first-class input
(Revit cannot open a file saved by a newer Revit, so the recipient's year is
always asked). Each writes the file, a manifest and one JSON result:

```bash
.venv/bin/python tools/frontdoor.py author --prompt "an electrical room with 6 panels" --out out/demo --json
#   -> out/demo/prompt_room.rvt + families/ + manifest.json, ~10 s, "ok": true, release.output 2026,
#      status "PROOF-ONLY (self-checks PASS; …)", this_file "validated-not-certified (… VALID 0 errors …)"
.venv/bin/python tools/frontdoor.py author --ifc inputs/ifc/electrical-room-2500a.ifc --target-version 2024 --out out/r24 --json
#   -> out/r24/electrical-room-2500a.rvt as a native Revit 2024 file, ~12 s
.venv/bin/python tools/frontdoor.py author --rvt out/demo/prompt_room.rvt --edit "move PP-2 to 3,1,4.66" --out out/e --json
#   -> out/e/prompt_room.edited.rvt, ~2 s; the file keeps its own release
.venv/bin/python tools/rvt_validate.py out/demo/prompt_room.rvt --json out/demo.validation.json
#   -> 0 errors required on everything we produce (necessary, never sufficient — see below)
.venv/bin/python tools/route.py matrix          # the honest capability table: any of {prompt, ifc, rvt, rfa, spec} -> {rvt, rfa, ifc}
```

**The product path, exactly as a skill session runs it** — bare unzip,
system Python, no repo on the path:

```bash
.venv/bin/python tools/sync_plugin.py           # mirror src/ + skills into plugin/, deny-audit, validate, rebuild tekton-plugin.zip
cd "$(mktemp -d)" && unzip -q /path/to/tekton/tekton-plugin.zip
python3 skills/tekton-author/scripts/_bootstrap.py go author --prompt "an electrical room with 6 panels" --target-version 2025 --out out/j1 --json
#   -> {"go": {"ready": true, "preflight_line": "tekton: READY | python 3.11 | engine bundled | genesis verified …", …},
#       "result": {"ok": true, "files": {"combined": "…/out/j1/prompt_room.rvt", …}, "release": {"output": 2025, "opens_in": "Revit 2025 and newer -- never an older Revit"}, …}}   (~8 s)
```

If `go` is not `READY` from a bare unzip, the product is broken regardless of
what the repo tests say. Everything else — viewer rounds
(`tools/probe_batch.py`), provenance, the plugin gates, env vars — is in
[`CLAUDE.md`](CLAUDE.md) §2 and §3b.

---

## Honest scope — certified vs. validated vs. open

The rule under everything: **Autodesk's reader is the arbiter.** A file is
*certified* only when `viewer.autodesk.com` or desktop Revit loaded that
exact file and the verdict is in
[`docs/coverage/viewer-certified.json`](docs/coverage/viewer-certified.json).
"Validator 0 errors" is our shipping gate — necessary, never presented as
acceptance. The per-route truth, with evidence and caveats per cell, is
`tools/route.py matrix` / [`PERMUTATION-MATRIX.md`](docs/product/PERMUTATION-MATRIX.md)
(a test fails if a "works" claim loses its evidence); the summary:

- **Certified by Autodesk's reader:** our composed genesis project bases for
  Revit **2026 / 2025 / 2024** (no Autodesk-authored base content; 2023 base
  certified, compose pending); native creation of projects and walls
  (LOAD, and RENDER where the solid is authored) and edits, including on
  foreign files; family **generation** (`.rfa`); loading Revit-born `.rfa`
  and extract → place onto our bases; our generated equipment placed **into
  existing projects** (`add_to_project`).
- **The one open cell:** *our generated* families + placed instances on
  *our composed* bases fail Autodesk's audit while byte-equivalent variants
  pass (26 single-variable rounds logged in `docs/inbox/genesis-audit.md`;
  issue #16, next signal = desktop Revit's own error dialog). Every equipment
  prompt produces exactly that shape, so those deliveries carry the stamp
  and `--strict` splits shell + equipment — delivered either way.
- **PROOF-ONLY:** until the deliverability gates clear — G2 identity block,
  G3 counsel (author string C1, corpora C4, footer token C5, trademark),
  G4 content — every manifest stamps `PROOF-ONLY, NOT-DELIVERABLE`. The
  stamp is a label applied *after* delivery, never a refusal
  ([`docs/PROGRAM.md`](docs/PROGRAM.md) PG5).

## The hard rules, one line each (full text and the reasons: [`CLAUDE.md`](CLAUDE.md) §1)

1. **Deliver, then caveat** — status gates are labels, never refusal logic; never swap an IFC for a requested `.rvt`.
2. **Never read an Autodesk installation directory** — a runtime tripwire enforces it.
3. **Zero donor bytes in anything shipped** — we mine laws from samples and author our own; sample-derived material stays in git-ignored quarantine dirs.
4. **Autodesk's reader is the arbiter, not our validator** — certification only via the ledger, every viewer round with a certified base + byte-identical control.
5. **The reduction law** — a referrer of removed content is deleted with it or left byte-identical, never "neutralised".
6. **Keep this repo private**; never present "Autodesk Revit" or a template's identity as our author string.
7. **No Autodesk APS / cloud automation services** — the writer is our own; decided, not up for re-proposal.
8. **A task declined by a policy layer is surfaced verbatim**, never reworded around.

## Layout

| Path | What |
|---|---|
| `src/rvt/` | the engine: container/codec layers, per-file schema, validator, `versions/`, `genesis/`, `frontdoor/`, `famgen/`, `famload`, `convert/`, `ifc/` (incl. the stdlib `steplite` reader), `reduce_law` |
| `tools/` | CLIs: `frontdoor.py`, `route.py`, `rvt_validate.py`, `sync_plugin.py`, `probe_batch.py`, `provenance.py`, `surface_bench.py`, per-release `genesis_*`, forensic instruments; `tools/dev/` = process tooling (`techlead.py`, `coord.py`, portable-path check) |
| `plugin/` | **the product** — skills (`tekton-author`, `-edit`, `-inspect`, `-native`, `-ifc`), commands, agents, the certified bases under `assets/genesis/`, the mirrored engine under `lib/`. Hand-edited vs generated paths: [`CLAUDE.md`](CLAUDE.md) §3b |
| `skills/tekton-ifc/` | source of the IFC skill (mirrored into the plugin) |
| `spec/`, `inputs/ifc/`, `usecases/` | the building/room spec schema, the worked IFC inputs, use-case material (copied into the plugin as examples) |
| `docs/product/` | user-facing truth: `PERMUTATION-MATRIX`, `REQUIREMENTS`, `SURFACE-PLAYBOOK`, `MCP-PATH` (documented future path, not built), `COUNSEL-BRIEF`, `roadmap` |
| `docs/process/AUTONOMY.md` | the operating system: roles, labels, bots, what still needs a human and why |
| `docs/inbox/` | one record per workstream (evidence, findings, `BRANCH STATE`); `genesis-audit.md` = the verdict log |
| `docs/coverage/` | the viewer-certification ledger (+ the historical CRUD matrix) |
| `docs/writer/`, `docs/streams/` | format facts per release; the original per-stream format analyses (historical) |
| `experiments/` | probes and proof files per stream (binaries git-ignored; the ledger cites them) |
| `tests/` | ~1,700 tests; `tests/ci_shard.txt` = the fast no-samples shard CI runs on 3.11 + 3.12 |
| git-ignored on purpose | `samples/ vendor/ extracted/` (third-party, quarantined), `experiments/**/*.rvt|rfa`, `out/`, caches, zips |

## How work is done (short form; the protocol is [`CLAUDE.md`](CLAUDE.md) §4)

GitHub Issues are the queue; the pinned 📋 board ([#56](https://github.com/ckaragitz/tekton/issues/56))
is the live picture. Coding sessions are the tech leads — they log every
human steer, keep the queue stocked from [`docs/PROGRAM.md`](docs/PROGRAM.md),
claim one issue (`/next` or `/claim`, one holder enforced), work on one
branch cut from `main`, and open one PR with `Closes #N` and the stream
record; CI, review, fix passes and squash-merge are automated
([`docs/process/AUTONOMY.md`](docs/process/AUTONOMY.md)). `main` is
protected; nothing is claimed by editing a markdown file; hot files
(`CLAUDE.md`, `KNOWLEDGE.md`, `TRACKER.md`, `plugin/skills/*/SKILL.md`,
`docs/coverage/viewer-certified.json`, …) change only through small
dedicated PRs.
