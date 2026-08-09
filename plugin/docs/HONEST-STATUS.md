# HONEST STATUS — what is certified, what is validated, what is open

One truth table. Every row is tied to evidence you can open. Nothing here
claims more than the engine's own capability table (`tools/route.py matrix`
in the repo, rendered as `docs/product/PERMUTATION-MATRIX.md`) and the
certification ledger (`docs/coverage/viewer-certified.json`). If a row is not
what a customer needs, say so — and still deliver the file that was asked
for: every status below is a **label stated with the delivery, never a reason
to withhold a `.rvt`/`.rfa` or to swap in another format**.

Status legend (two tiers that are never merged):
- **certified** — that artifact (or the base it names) passed **Autodesk's
  own reading pipeline** (viewer.autodesk.com translation = PASS) and is
  recorded in the ledger `docs/coverage/viewer-certified.json`. Only the
  ledger certifies; a session's opinion does not.
- **validated** — the route runs end to end and its output passes **our**
  layered validator (0 errors) plus the route's own gates; runnable evidence
  (tests, worked manifests) is cited by the machine matrix. *Validated is not
  certified*: Autodesk accepts a specific output only when the recipient's
  Revit / the Autodesk Viewer opens it. Every such output ships stamped
  `PROOF-ONLY` (see §4) — delivered, labelled, never withheld.
- **open** — a named gap or open bug; the route says so in one clear line or
  a stamp, and delivers what it can.

## 1. Creating Revit files (the tekton-author front door: `go author …`)

| Capability | Status | Evidence |
|---|---|---|
| The composed genesis **project bases** every new `.rvt` is authored on — Revit **2026**, **2025**, **2024** (bundled under `assets/genesis/`) | **certified** | ledger: `G_ABPD.rvt` (2026, batch 27 control re-confirmed), `G_ABPD_2025.rvt` (batch 29), `G_ABPD_2024.rvt` (batch 36) — each certifies its whole substitution chain by bytes |
| **prompt → `.rvt`** (room + walls + switchboard / distribution / lighting / receptacle panelboards / transformers, feeders planned) with `--target-version {2026,2025,2024}` | **validated** on a certified base (matrix: *works*) | matrix row `prompt_to_rvt`; `tests/test_frontdoor.py`; ledger: `ROOM2025_walls.rvt` (a native **2025** file authored from a prompt by this route loads in Autodesk's reader), `W1_gabpd_wall_solid.rvt` / `RSOLID_walls_A_solid.rvt` (created walls load **and render** on the genesis lineage), `stage_L8_lp4.rvt` (family load + instance placement on the genesis lineage) |
| **IFC → `.rvt`** (a Claude Design export or any tagging-contract IFC; product IFCs fall back to the family chain) | **validated** on a certified base (matrix: *works*) | matrix row `ifc_to_rvt`; ledger: `V25_room_from_ifc.rvt`, `V26_room_from_ifc_with_walls.rvt` (template era); worked `skills/tekton-author/examples/electrical-room-2500a.ifc` |
| **spec JSON → `.rvt`** (chain spec → IFC → intent → `.rvt`) | **validated** (matrix: *works*) | matrix row `spec_to_rvt`; ledger: `V23_electrical_room.rvt` (legacy direct build); `tests/test_job.py` |
| **Family generation → `.rfa`** from a prompt, an IFC or a spec (catalog-backed kinds: panelboard, transformer, luminaire/downlight, house switchboard) | **validated** (family-mode validator 0 errors; matrix: *works*) | matrix rows `prompt_to_rfa` / `ifc_to_rfa` / `spec_to_rfa`; `tests/test_famgen_factory.py`, `tests/test_ifc_family.py`; ledger: `L_downlight_loaded.rvt` (our downlight `.rfa` built from OUR OWN IFC's facts instantiates and loads — PASS), `L1a_rstbasic_loaded_levelhead.rvt` (our generated family loaded via the four-registry loader) |
| **Loading a family into a project** (`.rfa` → `.rvt`, four-registry loader; default host = the pinned certified base) | **certified at base level** for Revit-born and extracted families; famspec lane validated | ledger: `T2a.rvt` (a Revit-born standalone `.rfa`, 1,992 elements, famloaded onto our composed `G_ABPD` with a placed instance — accepted), `TB0g.rvt` (an embedded-born famdoc extracted and placed on the composed base — accepted); matrix row `rfa_load` (the any-`.rfa` id-remap lane is certified in research, product wiring tracked as its own issue → one clear line today) |
| **Older targets (2023 and earlier)** | **open** — format read (2023 base `B2023_K4.rvt` certified), no composed creation base yet | the run still DELIVERS: default-release `.rvt` + `result.release.line` verbatim + a version-agnostic IFC beside it (`skills/tekton-author/references/REVIT-VERSIONS.md`) |
| **Created walls AND our generated placed families in ONE file** | **open (the one open cell)** — each alone passes Autodesk's audit, the combination is rejected; 26 single-variable rounds logged, next signal is desktop Revit's dialog (repo issue #16) | default = one combined file stamped `PROOF-ONLY: walls+families combination unverified`; `--strict` = two coordinated files (shell + equipment); ledger controls `WF_fix.rvt` / `WF_nofix.rvt` |
| **Circuits / Revit-native panel schedules** in created projects | **open** — planned in the manifest (feeder tree resolved), not emitted as working circuits on the genesis bases | ledger `V29_room_with_circuits.rvt` proved circuit creation on the template era only; the front door states "circuits are a named blocker (plan delivered, never faked)" |
| **LOAD vs RENDER** of created geometry | walls: **certified to render** with authored solids (`W1_gabpd_wall_solid.rvt`); other created categories: check per element | `tekton-inspect` render check (`render_inspect.py`) reports LOADED vs RENDERED per element — run it before promising a picture |

## 2. Editing an existing `.rvt` (tekton-edit / `go author --rvt X --edit "…"`)

| Capability | Status | Evidence |
|---|---|---|
| Modify parameters, move, retype, re-level, delete **with cascade** — by element name (front door) or id (`rvt_edit.py`); the input's release is detected and **kept** | **certified** (the edit pipeline's outputs passed Autodesk's reader) | ledger: `M3_modify.rvt`, `M4_move_retype.rvt`, `M2_delete_cascade.rvt`, `M2_delete_cascade_rac.rvt` (cascade delete on a *foreign* architectural file); matrix row `rvt_edit`; by-name route edits 2026/2025/2024 files, id-based commands open 2026 files today (one clear line otherwise) |
| **Add our generated equipment INTO an existing project** ("add a 75 kVA transformer to my project") | **validated** (VALID 0 errors, release preserved, census coherent) — no add-into artifact has been through Autodesk's reader; the added instance is the open cell's shape | matrix row `rvt_edit` (add branch, `rvt.convert.add_to_project`); worked `A1_add_own` / `A2_add_rme_devonly`; `tests/test_convert_combo.py` |
| **Merge an IFC's content INTO an existing `.rvt`** at a disjoint offset | **validated** (matrix: *works*), viewer-unverified as a merged artifact | matrix row `ifc_merge_into_rvt`; `tests/test_convert_combo.py` |
| **`.rvt` → IFC** export (levels, straight walls, electrical equipment + tagging-contract values, feeders; the rest counted as not-extracted) and **extract a family** `.rvt` → `.rfa` | **validated** (round trip through our own resolver is the acceptance; extract → place certified at base level by `TB0g.rvt`) | matrix rows `rvt_to_ifc`, `extract_family`; `tests/test_convert.py`, `tests/test_router.py` |
| Authored text/content edit inside a native record; whole-file rewrite (every framed byte ours) | **certified** | ledger: `V18_first_authored_change.rvt`, `V19_authored_change_stamped.rvt`, `V15_regzip_ecc_full.rvt` |
| Rename / set-mark on *our own created* instances | **open** — no parameter rows on created instances yet (named edit blocker) | matrix caveat on `rvt_edit` |

## 3. Reading, validating, IFC

| Capability | Status | Evidence |
|---|---|---|
| Open any 2023–2026 `.rvt`/`.rfa`, detect its release, decode every element against the file's own schema; audits, panel schedules, seed audits | **validated** (version-agnostic by design) | `tests/test_versions.py`, `tests/test_rvt_analyze.py`; the validator's three layers (`skills/tekton-inspect/SKILL.md`) |
| The layered validator (`rvt_validate.py`: structure / consistency / semantic; corpus laws E1–E3; the 0x0f3f footer-blob law) = our shipping gate | **validated** — necessary, never sufficient: Autodesk's reader is the arbiter | `tests/test_validate_release.py`, `tests/test_validate_footer_blob.py`; silent on the three pinned bases |
| IFC authoring in Claude Design (v2 exporter), validate → score/tier, harden to Tier 1, spec → IFC, psets → shared parameters | **validated** (Tier 1 by construction; deterministic) | `skills/tekton-ifc/tests/`; worked `examples/chicago-plenum-electrical-room/`, `examples/eaton-panelboard/` with their delivery reports |
| IFC **reading** without ifcopenshell (stdlib steplite fallback) | **validated** (byte-identical outputs on both reference IFCs); the `--ifc` route's placement resolution still needs `numpy` — a Python without it gets one clear line and `/tekton-doctor --install` (repo issue #127 to remove) | `tests/test_steplite.py`; `tools/surface_bench.py` author-ifc row |

**What Tier 1 is (IFC):** correctly-categorized, correctly-placed Revit
elements (DirectShape in the right category) with your schedule data as
instance parameters — movable, taggable, schedulable, on sheets. **What it
is not:** native families with working connectors/circuits (Tier 2) — those
never come from any IFC, which is why the native `.rvt` route exists.

## 4. The rules that don't change

- **Deliver first, caveat after.** Every route hands over the file it was
  asked for plus its manifest; `PROOF-ONLY …`, validator verdicts and version
  lines ride *after* the hand-over. `DELIVERABLE …` is the only status string
  meaning shippable to third parties. **Why PROOF-ONLY today:** the bases are
  certified as ours but their lineage still discloses Autodesk-derived
  residue, and the identity (own build strings/GUIDs), legal-review and
  content gates are still open — until they clear, outputs are stamped, not
  withheld.
- **Target version first.** A `.rvt`/`.rfa` opens in the release that saved
  it or newer — never older, and there is no save-down. Ask the recipient's
  year before any creation job; build 2026/2025/2024 natively; unsure → 2024;
  older → deliver + one clear line + IFC addition. Existing files keep their
  release. Never present a 2026 file as openable in 2025.
- **Two tiers, always separate:** "our validator: VALID 0 errors" vs
  "accepted by Autodesk" (only after their Revit / the Viewer opens it).
- **IFC is an addition, never a substitute** for a requested `.rvt`.
- **No Autodesk APS / Design Automation, no Revit install, no reading of any
  Autodesk installation directory, zero donor bytes in anything shipped.**
  The writer and the content are our own.
- **No install on the job path.** `go …` is preflight + job + one JSON in one
  call on the system Python; `/tekton-doctor --install` (optional IFC extras)
  is the single sanctioned install, run once, off the hot path.

## 5. Recommended defaults, right now

| Job | Do this today |
|---|---|
| "Make me an electrical room / equipment layout as a Revit file" | Ask the Revit year → `tekton-author` `go author --prompt "…" --target-version YEAR` → deliver the `.rvt` + families, the release story, `result.status` verbatim, stamps and the open-cell / LOAD-vs-RENDER caveats after. Offer `--strict` (two files) and the IFC/handoff as additions. |
| "Turn this IFC (Claude Design export) into Revit" | Same, with `go author --ifc their.ifc --target-version YEAR`; add `/tekton-harden` if they also want the IFC linked as Tier 1. |
| "Change / move / delete things in this .rvt they sent us" | `tekton-edit` (`go author --rvt their.rvt --edit "…"` by name, or `rvt_edit.py` by id); release kept; certified edit pipeline. |
| "What's in this Revit file? Is it valid? Will it show?" | `tekton-inspect`: `rvt_validate.py`, render check, audits — read-only, any release. |
| "A single panelboard / transformer / downlight family" | `tekton-author` prompt/IFC → `.rfa` (catalog-backed kinds); load into their project with the `rfa + rvt` route. |
| Coordination model / submittal where an IFC is what the GC wants | `tekton-ifc`: Design → v2 export → harden → Link IFC (Tier 1). Templates in `docs/JOB-TEMPLATES/`. |

*Reconciled with `tools/route.py matrix` (21 cells: 17 works / 1 partial / 3
missing) and `docs/coverage/viewer-certified.json` on 2026-08-09. When the
open cell closes or a new release base certifies, the matrix and the ledger
move first; this page follows them, never the other way round —
`scripts/validate_plugin.py` fails the plugin build if this page drifts back
to a retired claim.*
