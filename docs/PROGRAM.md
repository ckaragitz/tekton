# PROGRAM — what tekton is for, and what the tech leads plan from

Auto-loaded into every coding session (imported by `CLAUDE.md`). This is the *input* to planning:
the tech leads (every session, and the scheduled planner) derive, order and retire the backlog
from the goals below; humans steer it (steers are logged as issues and, when standing, in
`docs/STEERING.md`). Keep it short and true. Change it by PR — small edits as reality moves; a
change of *direction* only on a human steer, cited by number. `TRACKER.md` is the long-form
curated roadmap and history; `KNOWLEDGE.md` is why things are the way they are.

## Mission

Turn Claude into a Revit-fluent teammate: a prompt, an IFC, or an existing Revit file in → a
`.rvt` / `.rfa` that opens *and behaves* in the recipient's Revit release out — with no Revit
install, no Autodesk seat, no APS anywhere in the loop. The product is the **plugin + skills**
(`plugin/`, shipped as `tekton-plugin.zip`) backed by our own engine (`src/rvt/`). Revit is the
last-mile deliverable format; Autodesk's reader is the arbiter of "works" (hard rule 4).

## Program goals (ordered; a lower goal never justifies harming a higher one)

- **PG1 — Trustworthy output.** Every route delivers a file, honestly stamped; certification only
  via the ledger (`docs/coverage/viewer-certified.json`); target release is a first-class input;
  the honest capability table (`tools/route.py matrix`, `docs/product/PERMUTATION-MATRIX.md`)
  never claims more than the evidence.
- **PG2 — Close the open cell.** Our *generated* families + placed instances on our *composed*
  bases must pass Autodesk's audit (today: fail while byte-equivalent variants pass; 26 logged
  rounds, `docs/inbox/genesis-audit.md`). Highest-information next step is the desktop-Revit
  error dialog (#16). Everything render/geometry-related (the RENDER gate) hangs off this.
- **PG3 — The plugin works for a stranger on any surface.** Bare unzip + system Python, Windows
  and macOS included, cloud sessions included; `go author …` returns READY; skills ask the
  target version first and state per-release honest status; CI is the shared definition of
  green.
- **PG4 — Release coverage.** 2026/2025/2024 composed bases certified and kept certified through
  every writer change; 2023 composed and certified; family loading/placement native on 2025/2024
  framing, not only 2026.
- **PG5 — Deliverability gates** (from `TRACKER.md` P0): G2 own the identity block (no inherited
  Autodesk build strings/usernames/GUIDs), G3 counsel (C1 author string, C4 corpora, C5 footer
  token, trademark — human-gated, tracked in #23), G4 content (our own parametric families from
  manufacturer facts, zero third-party geometry). Until they clear, everything ships stamped
  PROOF-ONLY — delivered, never withheld.
- **PG6 — Engine depth where users hit walls.** Codec gaps that block real edits/conversions
  (GraveyardRec ElemTable, RFA→RFA on foreign families), validator laws promoted from findings
  (0x0f3f footer blob), performance of prompt-only jobs.
- **PG7 — The engineering process runs itself.** Sessions are the tech leads; humans steer; the
  code→merge pipeline needs no human; the board is always current (`docs/process/AUTONOMY.md`).
  Process friction is filed and fixed like product bugs (`area:process`).
- **PG8 — Learn from the family beta** (`docs/product/roadmap.md` Track A): capture willingness,
  time saved, where "editable" matters, and every disappointment in Revit as backlog items with
  their frequency.

## Current objectives (weeks, not months) — each names its evidence of done

1. **O1 Open cell:** get the desktop-Revit dialog text for the failing instance files recorded in
   the audit log (#16, `needs-revit-desktop`); every hypothesis after that is a single-variable
   round with a control. *Done = verdict #49+ in genesis-audit names the failing element/class.*
2. **O2 Windows/macOS/cloud green:** cp1252 text I/O (#29, staged), stdlib zip build (#37/#40),
   then a `windows-latest` CI job. *Done = CI matrix includes Windows and is green on main.*
3. **O3 Target-version-first UX + honest matrix:** #24 (skills ask the year; per-release status)
   and #5 (register convert a/b, certified .rfa-load and extract→place depths). *Done = `route
   matrix` and the skills agree with the ledger for 2024–2026.*
4. **O4 Family generation hygiene:** #10 blank-named host symbols, #12 donor-id false positive,
   #9 determinism, #15 rft_probe remap, #13 GraveyardRec. *Done = each issue's DONE; famgen
   suites green; no regression in the certified .rfa lineage.*
5. **O5 2025 famload/instance lane** (#14). *Done = load + place on G_ABPD_2025 validates 0
   errors under its own release and a batch is STAGED for certification.*
6. **O6 Validator + verification laws:** #7 footer-blob rule, #11 own-schema binding in
   verify_manipulated. *Done = rules fire on synthetic violations, stay silent on the three
   pinned bases.*
7. **O7 Fresh-clone developer experience:** #3 pyproject extras, #4 docs refresh, keep
   `scripts/cloud-setup.sh` and the CI shard the single source of setup truth. *Done = a new
   contributor's first session reaches a green shard with only the README.*
8. **O8 Genesis identity + residue** (#19 identity scrub, #20 style repair, #21 residue, #17 2023
   compose) — owner-machine + viewer-gated; sessions prepare and STAGE, a human uploads.
9. **O9 Autonomy OS landed and boring:** #55 merged; a week of planner/worker/board runs with no
   human intervention except §10 items; follow-ups filed by the planner itself.
10. **O10 Plugin latency as a measured, standing concern** (epic #110, steer #108/S-2026-08-09-g):
    round-trips per skill flow (#111), SKILL.md/reference token weight (#112), and baseline
    coverage of every skill surface including `tekton-ifc` (#113). *Done = each child's DONE, and
    `tools/surface_bench.py` has a recorded before/after for every latency change merged.*
11. **O11 Donor-free families on every route** (P0 steer #498, S-2026-08-10-c): `prompt → rfa` and
    `ifc → rfa` (a full multi-element IFC such as a Claude Design export) emit self-generated
    families carrying every desktop-verified law with no `family_donor` / `$RVT_FAMILY_DONOR`;
    the donor escape hatch stops being needed for any documented flow. Per steer #591
    (S-2026-08-10-e) the prompt lane generates a named product with no dimensions ("create a
    cable tray family") as a real LOD-400 family at standard `nominal` archetype dimensions —
    overridable by the prompt, never reported as a manufacturer fact — rather than refusing or
    asking; per steer #585 (S-2026-08-10-d) a family that fails in Revit is fixed on Revit's own
    path, never by wrapping it in a project; per steer #601 (S-2026-08-11-a) every generated
    family carries its category's standard Revit parameters from a category → standard-parameters
    table sourced from the format itself, values filled only when known. *Done = #498's DONE
    (1)–(3): the structural host-ADocument gate extended to the IFC route, desktop verdicts
    recorded, matrix rows honest; plus #591's DONE (1)–(6) and #601's DONE (1)–(4).*
12. **O12 One prompt in, a specific family out — questions only for the residue** (P0 steers
    #685 and #684, S-2026-08-11-c superseding the emphasis of S-2026-08-11-b): one descriptive
    prompt resolves kind, Revit category, vendor/line, dimensions and standard parameters and
    builds immediately (`route run --prompt "…" --output rfa` is the whole interface); an
    ordered, branching series of questions — derived from the catalog, the #591 archetype
    registry and the #601 standards tables, never written per product — appears only for what
    the prompt left undetermined and the engine cannot default honestly, few and most-decisive
    first (vendor and line where the catalog holds several); the breadth behind it is data, not
    code: an MEP taxonomy (kind → category → standard parameters → catalog-backed /
    archetype-generable / neither) and a vendor directory (maker → lines → which we hold sourced
    facts for), with the standing line that model knowledge supplies taxonomy and standard
    practice but never a manufacturer's dimensions as a `fact`; where standards compete the
    result names the one it followed and offers the other; every value carries its tier and the
    `tekton-author` skill asks conversationally and knows when it has enough. Neither the
    questions nor a thin prompt ever gate delivery, which is how this coexists with O11:
    answering nothing still yields O11's nominal-archetype file with the assumed answers stated.
    *Done = #685's DONE (1)–(6) and #684's DONE (1)–(6).*
13. **O13 A spec sheet in, a functional family out** (P0 steer #687, S-2026-08-11-d): a
    user-supplied PDF/spec sheet is read into `fact`-tier values cited to the sheet (page/row) —
    the honest source for the manufacturer data O12 may not recall — and resolved to a famspec
    that builds, with everything the sheet does not state left `nominal`/blank and an unreadable
    sheet said so while the archetype lane still delivers; and "functional" is met surface by
    surface, each with its own desktop-Revit verdict before any route claims it: parameters that
    genuinely drive the geometry (the #372 constraint chain, re-opened as a probe ladder after
    its desktop failure), visibility/detail-level control per solid, and tag families with
    labels bound to the family's parameters. Four separate streams; the sheet reader is the
    highest-value and unblocked one, the constraint chain the highest-risk. *Done = #687's DONE
    (1)–(6), each item's desktop verdict recorded per hard rule 4.*

## Not goals (decided — do not re-propose without a new steer)

No Autodesk APS / Design Automation (rule 7). No reading Autodesk install directories (rule 2).
No donor bytes in anything shipped (rule 3). No public remote (rule 6). No hosted MCP server yet
(`docs/product/MCP-PATH.md` is the documented future path). No piecemeal rename before trademark
clearance (`RENAME.md`).
