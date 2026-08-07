# tekton

**tekton is a pure-Python interoperability library for the Autodesk® Revit®
`.rvt` / `.rfa` file formats.** It AUTHORS our own project content —
settings, styles, category catalog, palette, datum, views, families and
elements — as valid Revit files that a licensed engineer opens in Autodesk's
own software for coordination and QA. `.rvt` is the AEC industry's mandated
deliverable format; tekton is the layer that lets an AI-driven workflow
produce that deliverable directly.

The content that goes into a tekton file is ours (constructor-built, from
our own data and the customer's inputs). Questions about the *format
posture* — writing a proprietary format for interoperability, and the
handful of format-signature tokens every valid file must carry — sit with
counsel, and every output is proof-only until they clear (§ Honest scope).

> **Naming.** The product's display name is *tekton*. Code paths, the
> Python package (`rvt`) and this directory (`tekton/`) keep their old
> names until a single scripted rename after trademark clearance — see
> `RENAME.md`. "tekton for use with Autodesk Revit"; Autodesk and Revit are
> trademarks of Autodesk, Inc.

---

## Drive it from anything, with any of three inputs

The product requirement: tekton is drivable from ANY AI surface (Claude
Design / Chat / Cowork / Code, ChatGPT Work, Gemini …) with any of three
inputs — a **prompt**, an **IFC** file, or an existing **Revit file** — and
all three land in the same gated pipeline: build → structural
verification → the Autodesk-free validator (0 errors required) → identity
→ provenance status → a deliverable manifest next to the output.

**The unified front door is `tools/frontdoor.py`** (landed 2026-08-04;
its stream is still active — the record in `docs/inbox/` closes it):
ONE entrypoint, one intent model, three inputs — exactly one of
`--prompt` / `--ifc` / `--rvt`. Output lands in
`experiments/frontdoor/<name>-<stamp>/` with a deliverable manifest. Always
`.venv/bin/python`, from the repo root:

```bash
# (1) PROMPT   — primary: hands a scene brief + instructions to the AI surface
#                (the user's own prompt -> Three.js <three-d-stage> -> IFC4 flow);
#                fallback: a built-in deterministic parser (no API key)
.venv/bin/python tools/frontdoor.py author --prompt "2500 A electrical room, 480Y/277, one 150 kVA transformer, ..." [-o DIR]
.venv/bin/python tools/frontdoor.py author --prompt "..." --handoff-only     # emit the surface handoff only

# (2) IFC      — the resolved-placement / Pset-join-key route (tagging-contract Psets)
.venv/bin/python tools/frontdoor.py author --ifc inputs/ifc/electrical-room-2500a.ifc

# (3) EXISTING REVIT FILE + an edit — a sentence, an ops.json, or inline JSON ops
.venv/bin/python tools/frontdoor.py author --rvt in.rvt --edit "delete DP-1 with cascade; move LP-2 to 3,4"

# honesty switches
#   --strict   the walls+families OPEN BUG -> TWO coordinated files (shell + equipment)
#              instead of one combined file that would be stamped over the bug
#   --base     author on a supplied base instead of the pinned, hash-verified genesis base
#              (an Autodesk SAMPLE project is REFUSED as a base)
#   --json / --verbose   machine-readable result / streamed build log
```

Under the front door the tested engines are unchanged and still directly
usable: `tools/rvt_job.py` (`create` / `from-ifc` / `edit` — the gated,
manifest-writing runner), `tools/ifc_intent.py` (IFC → intent → families →
room), `tools/rvt_edit.py` (element-level manipulate), and — on every output,
always — `tools/rvt_validate.py out.rvt --json out.validation.json` (0 errors
or it does not ship).

Working inputs on disk: `inputs/ifc/electrical-room-2500a.ifc` (a full 2500 A
electrical room whose `IfcElectricDistributionBoard` Psets follow our tagging
contract `PanelName / Voltage / Phases / Wires / BusRating / MainsType /
FedFrom`) and `inputs/ifc/chicago-plenum-downlight.ifc` (a fixture) — both
authored by the user's own Claude-Design flow.

**Packaging rule:** everything ships INSIDE the plugin (`plugin/`) as skills
with instructions + reference docs — `skills/tekton-native` (native `.rvt`
read/edit/validate/create) and `skills/tekton-ifc` (IFC author/validate/
harden), kept in sync from source by `tools/sync_plugin.py` (`--check` is
the drift guard; a DENY list keeps quarantined third-party data out). A
hosted MCP server is the DOCUMENTED FUTURE path for surfaces that cannot
run the bundled scripts — `docs/product/MCP-PATH.md` — and is not built now.

---

## The milestone just reached: GENESIS LOADS

`experiments/genesis/subst_k4/compose/G_ABPD.rvt` — a Revit project base
whose settings, style catalog, palette, datum (levels / phases / grids),
view constellations and residue layers are **ALL our constructors' output,
composed with NO Autodesk-authored base content** (2,840 landed slots +
240 lawful deletions, composed by `tools/genesis_compose.py`, byte-exact-
anchored) — **LOADS in Autodesk's own reader as a browsable model** (a 3D
view + our sheet `GEN-101`, not empty, not corrupt).

Certification ledger entry: `docs/coverage/viewer-certified.json` →
`experiments/genesis/subst_k4/compose/G_ABPD.rvt`. Verdict record:
`docs/inbox/genesis-audit.md` § "***** ORCHESTRATOR VERDICTS #24 — GENESIS
LOADS". The user's day-one target is met: **no base file required.**

---

## Honest scope — what is proven, what is not

| Claim | Status | Evidence |
|---|---|---|
| Read / decompose ANY `.rvt`; class schema loaded from the file itself | **PROVEN** | container round-trips 6/6; schema 4,690 classes, 0 gaps |
| Whole-file re-write, every framed byte ours (gzip + block framing + per-page ECC + CFB) | **PROVEN** | V15, `docs/acceptance-log.md` |
| Authored content edits Autodesk renders; element creation; manipulation (delete/modify/move/retype); circuits; wall-hosting | **PROVEN (LOAD)** | V18–V31, M2–M4, H1–H2 — see the acceptance log |
| Genesis project base (no Autodesk base content) LOADS | **PROVEN (LOAD)** | verdict #24, ledger `G_ABPD.rvt` |
| **RENDER** (viewable baked geometry from OUR created elements) | **IN PROGRESS** | LOAD is not RENDER: our created walls carried a 2-byte placeholder rep; the seq-103 GElement B-rep is decoded (`rvt.render.wallgeom` reproduces native walls with zero differing leaves) and is being wired. Every certification to date is a LOAD pass. |
| Created walls + loaded family documents together | **OPEN BUG** | the combination fails while each alone passes; under bisection (`docs/inbox/render-instances.md`) |
| Genesis residue | **~260 elements** still Autodesk-authored + 4 named stragglers | verdict #24; each = a constructor + an in-place rung |
| The two shipped product corpora (`Formats/Latest` class schema + ESSchemaStorage unit schemas, byte-identical in EVERY Revit file) | **COUNSEL C4** | not element authorship; ship-verbatim vs regenerate is a counsel ruling |
| **Deliverability of ANY output** | **PROOF-ONLY until the P0 gates clear** | every manifest stamps `PROOF-ONLY, NOT-DELIVERABLE`; counsel C1 (author string), C4, C5 (format-signature token) + trademark clearance for "tekton" are the gates (`TRACKER.md` P0, `docs/product/COUNSEL-BRIEF.md`) |

The rule underneath the table: a claim is PROVEN only when Autodesk's own
reader (the Viewer or Revit) accepted the exact file, and the file is in the
certification ledger. Validator-clean is necessary, never sufficient.

---

## The CRUD mandate — measured, not claimed

Everything tekton touches must be **creatable, editable AND deletable.**
`tools/coverage.py` measures this as a 28-category × 6-verb matrix
(`docs/coverage/matrix.md`, source of truth `matrix.json`), where a cell
counts as proven only when a proof `.rvt` passes the validator with ZERO
errors, and CERTIFIED only when the ledger records Autodesk-reader
acceptance of that exact file.

Fresh run (2026-08-04 12:09, `coverage.py run --validate-only`, 168 cells):

- **13.2% CERTIFIED** by Autodesk's own reader (20 of 152 applicable cells).
- **42.7% of the MUTATING verbs proven** (53/124 — create/modify/move/
  retype/delete only, all 28 free read cells stripped so the number is not
  padded by trivial reads).
- The old "53.3% proven" (81/152) merges viewer-PENDING validation with
  real certification and is retired as a headline (coverage-critic H3).
- 0 REGRESSED, 0 FAILS; 40 UNPROVEN, 31 MISSING — the honest to-do list,
  category by category, in the matrix.

Reproduce: `.venv/bin/python tools/coverage.py run --validate-only`
(~6 min, validates the proofs on disk) or `run` (~40 min, regenerates
them). `tools/coverage.py report` re-renders without work.

---

## Layout

| Path | What |
|---|---|
| `src/rvt/` | the engine — container, schema, object codec, ECC, writer, genesis, famgen, ifc, render, mep |
| `tools/` | front door (`rvt_job.py` → `frontdoor.py`), edit / validate / IFC / genesis / coverage / sync CLIs |
| `plugin/` | the shippable Claude Code plugin (skills + engine + commands + agents), synced from source |
| `spec/` | `building.schema.json` — the versioned building/room spec the front door consumes |
| `inputs/ifc/` | the user's Claude-Design IFC exports (the IFC path's real inputs) |
| `experiments/` | proof files and their manifests (the certification ledger's referents) |
| `docs/coverage/` | the CRUD matrix + the viewer-certification ledger |
| `docs/product/` | architecture, roadmap, MCP-PATH (future), COUNSEL-BRIEF, content strategy |
| `TRACKER.md` / `KNOWLEDGE.md` | work queue / institutional memory (orchestrator-edited) |
| `RENAME.md` | the tekton rename plan (not executed; gated on trademark clearance) |

## Reproduce

```bash
uv venv .venv && uv pip install --python .venv/bin/python -e .   # installs `rvt` (dep: olefile)
.venv/bin/python -m pytest tests/ -q                              # full suite
.venv/bin/python tools/sync_plugin.py --check                     # plugin drift guard
```

Python: **always** `/Users/ck/dev/things/tekton/.venv/bin/python`, from
the repo root. Read `AGENT_BRIEF.md`, `KNOWLEDGE.md`, `TRACKER.md` before
touching anything.
