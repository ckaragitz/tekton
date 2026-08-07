# MCP-PATH — productionizing tekton as a hosted MCP server

Status: DESIGN (documented future path — **not built**). Owner: the
orchestrator + user. Feeds Epic G in `TRACKER.md`. Supersedes the transport
and `.rvt`-output sections of `docs/product/architecture.md` (which predate
the "no Autodesk APS" decision recorded in TRACKER Epic C — the engine here is
our own native writer, never APS).

> **Scope of this document.** This is the design for tekton reaching the
> surfaces that CANNOT run our bundled CLI locally — the no-local-install,
> multi-surface case (Claude Design, Claude Chat without a code sandbox,
> ChatGPT Work, Gemini). It does NOT change the shipping decision: **skills
> with bundled scripts ship first** (§4). MCP is the escalation, and the
> non-Anthropic surfaces are the concrete trigger that demands it.

---

## 1. The problem MCP solves — and the one it does not

tekton's product requirement (from the user, TRACKER Epic G / KNOWLEDGE
"Product requirement"): the engine must be drivable from **any AI
surface** — Claude Design, Claude Chat, Claude Cowork, Claude Code, ChatGPT
Work, Gemini — with any of **three inputs**: a natural-language prompt, an
IFC file, or an existing Revit file (`.rvt` / `.rfa`).

Two of those surfaces execute our bundled scripts today; the rest cannot:

| Surface | Can run our CLI in a code sandbox? | Can load a Claude Skill? | Can connect an MCP server? |
|---|---|---|---|
| Claude Code | yes (local shell) | yes | yes |
| Claude Cowork | yes (Linux sandbox) | yes | yes (connector) |
| Claude Chat (claude.ai + analysis) | yes, when the sandbox is on | yes | yes (connector) |
| Claude Chat (no sandbox / mobile) | **no** | reads instructions only | yes |
| **Claude Design** | **no** — Design authors; it is not a script runner | reads instructions only | **consumes tool results** |
| **ChatGPT Work** | its own sandbox, not our packaging | **no** (Skills are a Claude concept) | **yes** (MCP connector) |
| **Gemini** | its own runtime, not our packaging | **no** | **yes** (tool integration) |

So the rule is clean: **the sandboxed Claude surfaces are served by the
skill; every other surface is served ONLY by a hosted engine.** A hosted MCP
server is not "MCP for MCP's sake" — it is the single mechanism by which
ChatGPT Work, Gemini and Claude Design ever call tekton at all. That is the
"concrete need" our standing rule requires before we escalate to MCP
(KNOWLEDGE "Delivery architecture — DECIDED (Skill-first)"; §4).

MCP does **not** solve, and must not be asked to solve: the format-posture
legal questions (counsel C1/C4/C5 — those are about the bytes we emit, and
they are identical whether a sandbox or a server emits them), or the
research residuals (RENDER gate, walls+families combination bug, ~260
Autodesk-authored residue elements). A server ships whatever the engine can
do; it does not make the engine do more.

---

## 2. The tool surface — an exact mirror of the skills

The MCP server exposes precisely the verbs the two skills already expose,
so a session's playbook is transport-agnostic: swap "run this script" for
"call this tool" and nothing else in the workflow changes. **One library,
three front doors** (CLI / skill script / MCP tool) — the standing design
rule, and why lifting is mechanical.

| MCP tool | Mirrors (skill · script) | Input | Output |
|---|---|---|---|
| `author` | rvt-native · the unified front door `tools/frontdoor.py author` (`--prompt` / `--ifc` / `--rvt --edit`, landed 2026-08-04; `tools/rvt_job.py` remains the gated engine under it) | `mode: prompt \| ifc \| rvt`; `prompt` text **or** an `ifc` artifact ref **or** a base `rvt` artifact ref; optional `base` (seed `.rvt`) artifact ref; options (`strict`, `stages`, …) | job id → on completion: `.rvt` artifact ref + `manifest.json` + `validation.json` |
| `edit` | rvt-native · `frontdoor.py author --rvt … --edit …` / `rvt_job.py edit` / `tools/rvt_edit.py` (delete / rename / set-mark / set-level / set-param / move / retype / add-instance / add-circuit; a plain edit sentence is parsed) | source `rvt` artifact ref + `ops[]` **or** an edit sentence | job id → edited `.rvt` ref + manifest + validation |
| `validate` | rvt-native · `tools/rvt_validate.py` (three layers) + `rvt_selfcheck.py` (four self-checks) | `rvt` artifact ref; `layers`, `strict` | validation report (JSON) — structure / consistency / semantic, error and warning lists |
| `inspect` | rvt-native · `rvt_inspect.py`, `rvt_edit.py info` / `deps`, `seed_audit.py` | `rvt` artifact ref; `query` (inventory / classes / records / deps / seed-audit against a job) | structured inventory JSON (levels, wall types, families/types by category, dependents, seed verdict) |
| `catalog_lookup` | rvt-native · the family/product-facts store (`rvt.famgen` facts + `house_standard`) | equipment description or tagging-contract Pset (`PanelName`, `Voltage`, `Phases`, `Wires`, `BusRating`, `MainsType`, `FedFrom`, ratings) | the matching family constructor + its parameter contract; `NOT SOURCED` fields called out |
| `ifc_validate` | revit-bridge · `validate_ifc.py` | `ifc` artifact ref | Tier score + issues (the Revit-import-fidelity linter) |
| `ifc_harden` | revit-bridge · `harden_ifc.py` (+ `report.py`) | `ifc` artifact ref | hardened `ifc` artifact ref + delivery report |
| `job_status` / `job_result` | (server plumbing, no skill analogue) | `job_id` | state → `queued \| running \| succeeded \| failed`; result refs |

**The `author` tool's three modes are the three product inputs, one
verb.** They differ only in the first stage of the same pipeline:

- `mode: prompt` — the surface (or the server, when the surface is a bare
  chat) turns the prompt into either a `spec.json` conforming to
  `spec/building.schema.json`, or — via the user's own established path —
  a Three.js `<three-d-stage>` scene exported to IFC4, which then rejoins
  the `ifc` mode. Prompt→spec authoring is an LLM step and stays with the
  calling model; the server takes structured input, never free prose it
  must interpret (a deliberate boundary: the engine is deterministic).
- `mode: ifc` — `ifc_to_spec` / `rvt.ifc.intent` (positions from world-baked
  vertices, the tagging-contract Psets as the join key, the feeder tree,
  our family mapping) → the create pipeline. This is the electrical-room
  end-to-end (`docs/inbox/ifc-room.md`, `inputs/ifc/electrical-room-2500a.ifc`).
- `mode: rvt` — an uploaded project is the base; ops author against it
  (`rvt.manipulate` / `rvt.mutate`), or it seeds a new job as the firm's
  content template (the `--base` / seed-audit path).

**Every tool result carries the honest status verbatim.** The manifest's
`PROOF-ONLY, NOT-DELIVERABLE` stamp, the validation error/warning lists, and
the RENDER caveat travel in the tool output as first-class fields — the
server never launders a proof into a deliverable. A tool that cannot run
(missing entitlement, oversize input) returns a structured refusal, not a
degraded silent success (automation fails RED, never skips green).

**Long jobs are asynchronous.** `author` and `edit` return a `job_id`
immediately; the surface polls `job_status` (or the client's MCP
transport streams progress notifications). A 32 MB validate is ~12 s and
fits a synchronous call; a full author + validate + provenance run does
not, and Design / ChatGPT surfaces have request timeouts we do not
control. Async-by-default keeps every surface working.

---

## 3. File-transfer model — artifacts, not payloads

MCP tool arguments and results are size-limited (varies by surface; assume
low single-digit MB) and `.rvt` projects run 6.7 MB → 139 MB in our own
corpus. Files therefore never travel in the tool payload except the
smallest (a `spec.json`, a manifest, a report). Everything else moves by
**artifact reference**:

```
1. surface -> `artifact_open(kind, size, sha256)`  -> { artifact_id, upload_url (signed PUT, TTL 15 min) }
2. surface uploads the bytes DIRECTLY to the storage endpoint (bypassing the MCP payload)
   — or, where the surface cannot PUT (Design / bare Chat), the user attaches the file
     in-conversation and the surface's own file-attachment mechanism hands us the bytes.
3. surface -> `author { mode: ifc, input: artifact_id, ... }`  -> { job_id }
4. surface polls `job_status(job_id)`             -> { state: succeeded, result: [artifact_id...] }
5. surface -> `artifact_url(artifact_id)`          -> { download_url (signed GET, TTL 1 h) }
6. the user downloads the .rvt from the URL (or Cowork saves it to the mounted folder).
```

Rules:

- **Artifacts are tenant-scoped and TTL'd.** Uploads and results live in a
  per-tenant namespace (`t/<tenant_id>/…`); nothing is world-readable; the
  signed URL is the only capability and it expires. Default retention:
  inputs 24 h, results 7 days, then purge (configurable per tenant; a
  contractor may need results to persist to a client folder).
- **Content-address for idempotency.** `sha256` on open lets the server
  dedupe an unchanged base `.rvt` across a session's ten edits — the
  second `edit` against the same base does not re-upload it.
- **The genesis base is a server-side warm asset, never uploaded.** The
  composed genesis project base (`experiments/genesis/subst_k4/compose/
  G_ABPD.rvt`, viewer-certified — TRACKER P0 / verdict #24) is the default
  `author` base when the caller supplies none. It is a fixed, versioned
  artifact the server holds resident; jobs COPY-on-write from it. Same for
  the family catalog and any tenant-uploaded seed library (§6).
- **Two-tier output, always.** Every job emits the `.rvt` AND its
  `manifest.json` + `validation.json` as separate artifacts, so the
  surface can show the honest verdict without downloading the model.

---

## 4. Why skills-with-bundled-scripts ship FIRST

This is the project's standing preference (KNOWLEDGE "Delivery
architecture — DECIDED (Skill-first)"; the user's rule that for Cowork /
claude.ai users we default to a Skill with bundled scripts, and reach for
MCP only when secrets, local-disk access, or heavy compute demand it). The
reasons, restated for tekton specifically:

1. **The sandbox already runs the CLI.** Claude Code, Cowork, and claude.ai's
   analysis tool execute Python in a Linux sandbox — the same runtime that
   powers Anthropic's docx/xlsx/pdf skills. Our engine is pure Python with
   one dependency (`olefile`); `ifcopenshell` ships manylinux wheels. There
   is nothing to host: the skill folder IS the deployment.
2. **Zero infrastructure until the market answers.** The roadmap (Track A)
   forbids building auth, billing or hosting before the family beta proves
   willingness-to-pay. A server has a monthly cost and an on-call surface;
   a zip has neither.
3. **The three MCP triggers, checked against tekton today:**
   - *Secrets* — we hold none. The APS-credential trigger in the old
     architecture is void: **no APS** (TRACKER Epic C, user decision, firm,
     twice). The engine needs no key to run.
   - *Local disk* — Cowork mounts the user's folder; the skill writes there
     directly. Not a trigger.
   - *Heavy compute* — a 32 MB validate is ~12 s of pure Python; the room
     job (families + walls + boards on the genesis base) built in ~11 s
     (`docs/inbox/ifc-room.md`). Well inside sandbox limits. Not a trigger
     — with one caveat: the 139 MB workshared project (`dach`) is untested
     against Cowork's memory ceiling, and that empirical check (TRACKER F8)
     is the honest gate on this claim.
4. **What DOES trigger MCP is reach, not capability** (§1): ChatGPT Work,
   Gemini and Claude Design cannot load a Skill or run our scripts. The
   moment the product must serve them, the hosted engine is required —
   and that is a business milestone (a paying non-Claude customer), not a
   technical one. Until then the skill is complete, cheaper, and testable.

The same code serves both because **CLI, skill script and MCP tool are
three thin front doors onto ONE library** (`docs/product/architecture.md`,
"Phased plan" — Phase 0's whole point). Nothing built for the skill is
throwaway; Phase 2 wraps it, it does not rewrite it.

---

## 5. Auth, tenancy, entitlement, metering

Deferred until Gate A→B passes (roadmap), but designed now so the tool
shapes above never need to change.

- **Auth: OAuth 2.1 per the MCP authorization spec.** The server publishes
  authorization-server metadata; surfaces do the standard flow (dynamic
  client registration where the surface supports it). The bearer token
  identifies the *user*; the user maps to a *tenant* (their firm) and a
  *seat*. No API keys pasted into skill folders — every credential lives
  in the surface's own connector store, which is exactly the secret the
  skill model cannot hold (and one of the three legitimate MCP triggers).
- **Tenancy = the firm.** Tenant boundary encloses: artifacts (§3), the
  seed/template library the tenant uploads (their standards `.rvt`, their
  shared-parameter file, their tagging-contract overrides), and the audit
  log of jobs. Cross-tenant reads are structurally impossible (namespaced
  storage keys, tenant id derived server-side from the token, never taken
  from tool arguments).
- **Entitlement is per-tool, per-tier** (roadmap tier hypothesis): the
  free tier meters `author`/`ifc_harden` calls per month; `inspect` and
  `validate` are cheap read-side features that plausibly stay generous
  (they are also the demo). A revoked seat fails the next tool call with a
  structured `entitlement_denied` — the surface tells the user, no silent
  degrade.
- **Metering unit** is an open product decision (`architecture.md`
  "Product decisions" #1): per-seat subscription vs per-generation credits
  vs hybrid. The server emits a usage event per completed job either way;
  billing chooses what to charge for later. Design the event, defer the
  price.
- **Audit/provenance travels with the job.** Every `author`/`edit` result
  carries the identity block (author string per counsel C1, scrubbed
  paths) and the provenance status; the server persists the manifest with
  the job record so a delivered file is always traceable to the inputs,
  base, and engine version that made it.

---

## 6. Compute profile — what the server must actually run

Grounded numbers (measured in this repo, single-threaded pure Python):

| Operation | Measured cost | Server implication |
|---|---|---|
| `rvt.validate` full three-layer report | ~12 s / 32 MB project | synchronous-safe under a 30 s cap; parallelizes trivially per file |
| Four self-checks (CRC / ECC / walker / stamps) | seconds; ECC re-frame is the hot loop | CPU-bound; the ECC coder (`rvt.ecc.frame_stream`, 255-lane CRC-11 per 65,249-B page) is the one candidate for a native extension IF profiling ever demands it — not before |
| Room job: 8 families + walls + boards onto the genesis base | ~11 s | fine synchronous, run async anyway for surface-timeout safety |
| Family generation (`rvt.famgen`, per `.rfa`) | ~1 s each | catalog families are pre-generated warm assets, not per-request |
| Coverage full regeneration (all proof drivers) | ~40 min | a CI job, never a tool call |
| Whole-file rewrite of the largest sample (139 MB) | unmeasured on server hardware | THE sizing question — memory (decode holds the object graph) matters more than CPU |

Warm assets held resident (versioned, copy-on-write per job):

- **The genesis project base** (`G_ABPD.rvt` and its certified lineage) —
  the day-one, no-base-required starting point. Recomposing it per job is
  wasted work; it is a fixed input.
- **The family catalog** (our constructors' pre-generated `.rfa`, the
  product-facts store).
- **Per-tenant seed libraries** (uploaded once, seed-audited on ingest,
  reused across jobs).
- **The per-release class schemas** we support (Revit 2026 today; each new
  release adds one ~500 KB blob — see Version reality below).

Profile: worker processes with a bounded memory ceiling (the 139 MB
project is the sizing test), a job queue for `author`/`edit`, synchronous
handlers for `validate`/`inspect`/`catalog_lookup`, object storage for
artifacts, and a small relational store for jobs/tenants/entitlements. No
GPU. No Windows. No Autodesk software anywhere in the stack — the
Autodesk-free validator is the whole point; viewer/desktop acceptance
remains the customer's own QA seat, exactly as in the skill workflow.

**Version reality carries over unchanged.** Revit cannot open a newer
file; the server, like the skill, edits in place at the input's version
and asks the user's Revit version before any job. Supporting a release =
holding its `Formats/Latest` class map (captured from one sample file per
release) — a data drop, not a code change.

---

## 7. Phased migration

Each phase changes the transport, never the engine, and each is
independently shippable.

**Phase 1 — Skills carry everything (NOW, shipping).**
The plugin (`plugin/`, synced by `tools/sync_plugin.py` with its `--check`
drift guard and DENY list) bundles `skills/rvt-native`, `skills/revit-bridge`,
the `rvt` engine (`plugin/lib`), the `/revit-*` commands and agent
templates. The sandbox runs the CLI. Reaches Claude Code, Cowork, and
sandboxed claude.ai. Cost: zero infrastructure. This is the family beta and
the design-partner phase (roadmap Tracks A/B).

**Phase 2 — A thin MCP wrapper over the SAME CLIs.**
A hosted MCP server whose tool handlers do exactly what the skill's
instructions tell Claude to do: fetch the artifact, shell out to the same
front door (`frontdoor.py author` / `rvt_job.py` / `rvt_validate.py` /
`rvt_edit.py` / the bridge scripts), collect the manifest, return
artifact refs. The wrapper adds only §3 (transport) and §5 (auth,
tenancy, metering). Trigger: the first surface the skill cannot reach —
ChatGPT Work / Gemini / Design — or Cowork's sandbox failing the F8
reality test on large models. Design constraint carried from Phase 1: keep
every CLI's contract (`--json` reports, exit codes 0/2/3/4/5/6, the
manifest schema) stable, because the wrapper depends on parsing exactly
those. **The skills stay** — their instructions grow a section: "if a
tekton MCP server is connected, prefer the tool of the same name; else run
the bundled script." One playbook, two transports.

**Phase 3 — A stateful service.**
The wrapper's shell-outs become in-process library calls; the warm assets
(§6) live resident instead of on disk; a real job queue with resumable
long-running authoring; tenant seed libraries; usage metering wired to
billing; the family catalog served as `catalog_lookup` against a live
store rather than a bundled JSON. This is roadmap Track C and is gated on
its economics (Gate C: hosting + compute vs price).

What NEVER migrates: the honesty invariants. The `PROOF-ONLY /
NOT-DELIVERABLE` gate, the fail-RED-not-skip-green rule, the identity and
provenance blocks, the render/load distinction — these are properties of
the engine's output and appear in every phase's tool results identically.

---

## 8. What changes for each surface

| Surface | Phase 1 (skill + bundled scripts) | Phase 2 (thin MCP wrapper) | Phase 3 (stateful service) |
|---|---|---|---|
| **Claude Code** | Full workflow today: plugin loads, sandbox runs every CLI, files on local disk. **Reference environment.** | Unchanged by default (local is faster and offline); MCP available for a shared team catalog / cloud-only assets. | Same as Phase 2; local-first stays the developer path. |
| **Claude Cowork** | Full workflow today: skill folder + Linux sandbox; results dropped in the mounted folder. The family-beta surface. | Adds the connector for jobs exceeding sandbox limits (the F8 large-model case) and for shared seed libraries; small jobs stay local. | Firm seed library resident server-side; Cowork mounts results back to the user's folder. |
| **Claude Chat (claude.ai)** | Works today WHERE the analysis sandbox is on: skill + scripts, IFC/`.rvt` attached in-chat. Mobile / no-sandbox: instructions-only — **cannot author.** | The connector serves no-sandbox chat and mobile: attach IFC/`.rvt`, tools do the work server-side, download link returned. Chat becomes fully served. | Unchanged from Phase 2, plus resumable long jobs. |
| **Claude Design** | Design AUTHORS (the user's Three.js `<three-d-stage>` scene → IFC4 export) but does not run our scripts. The IFC is carried to a runner surface by hand. | Design calls `author { mode: ifc }` on its own export directly — no hand-carry. The prompt→scene step stays in Design. | Design projects can register their tagging-contract overrides tenant-side; round trip in one surface. |
| **ChatGPT Work** | **Not reachable** (no Skills, our scripts not packaged for its sandbox). | **First served in Phase 2:** MCP connector; `author`/`edit`/`validate`/`inspect` all available. Prompt→spec authoring is ChatGPT's model; the server takes structured input. | Full parity with Claude surfaces. |
| **Gemini** | **Not reachable.** | **First served in Phase 2** via its tool integration to the same MCP endpoint. Same structured-input boundary. | Full parity. |

The invariant across the whole table: **the workflow the user experiences
is identical — describe / attach → get a validated `.rvt` + an honest
manifest.** Only where the bytes are computed moves.

---

## 9. Open decisions (route to the user; not decided here)

1. Metering unit (seat / generation / hybrid) — `architecture.md` #1.
2. Multi-tenant SaaS vs single-tenant deployments for the first design
   partners — `architecture.md` #5. (This doc assumes multi-tenant
   namespacing is cheap enough to build regardless.)
3. Result-artifact retention defaults per tier (24 h / 7 d proposed).
4. Whether prompt→spec authoring should EVER move server-side (a hosted
   LLM step) for bare-chat surfaces, or stay strictly with the calling
   model. Recommendation: keep the server deterministic; surfaces without a
   model are not tekton's target.
5. The offline / air-gapped SKU (`architecture.md` Phase 4) — only if a
   firm's IT forbids the connector; Phase 1's on-machine skill already
   covers most of that need for Claude Code / Cowork users.

## 10. Explicitly out of scope for the MCP path

- Autodesk APS Design Automation — removed by user decision (Epic C).
- Any change to what the engine can lawfully emit (counsel C1/C4/C5,
  trademark clearance for the tekton name) — those gates apply to skill and
  server identically.
- The RENDER gate, the walls+families combination bug, and the residue
  program — engine work, tracked in `TRACKER.md`, not transport work.
