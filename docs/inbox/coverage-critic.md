# coverage-critic — memo on the CRUD x category matrix (2026-08-03)

Role: COVERAGE CRITIC (read-only; no code modified). Inputs read:
`docs/coverage/matrix.md` + `matrix.json` + `README.md`, every
`docs/inbox/mep-*.md`, `docs/inbox/job-runner.md`, `docs/writer/job-runner.md`,
`tools/coverage.py`, `KNOWLEDGE.md`/`AGENT_BRIEF.md`. Work done:

* Ran `tools/coverage.py run` (FULL regen, not `--validate-only`): 168 cells,
  22 ledger files, all 6 registered generators re-ran OK (schedules 490 s,
  conduit 342 s, electrical 355 s, devices 506 s, genesis-types 210 s,
  families 8 s; V19/V20/manipulate/hosting frozen as ledger-certified), all
  51 gated proof files re-validated `errors=0`, all 27 read probes OK.
  **HEADLINE unchanged: 53.3% proven (81/152), 12.5% certified**,
  counts CERT 19 / VAL 62 / UNPR 40 / MISS 31 / NA 16. matrix.json/.md
  rewritten by the run (last-run stamp 2026-08-03 ~15:43).
* Spot-checked SIX proof files (task asked four) with
  `tools/rvt_validate.py` (default AND `--strict`) and by re-reading them
  with `Document.from_file` and diffing element sets against
  `samples/rmebasicsampleproject.rvt` (snapshots copied to a scratch dir
  BEFORE the regen so the checks were not raced by the harness):
  `cable_tray_create.rvt`, `conduit_delete.rvt`, `device_delete.rvt`,
  `panel_schedule_view.rvt`, `space_create.rvt`, `wire_create.rvt`.
* Ran the front door `tools/rvt_job.py` TWELVE times: the three modes with
  good inputs, then adversarially (missing-family spec, malformed ops.json,
  unknown op, ghost element id, non-cascade delete with dependents, corrupt
  IFC, random-bytes IFC, non-OLE base). Log + manifests under my scratch dir.
* Did NOT run the full pytest suite: the harness was regenerating the very
  proof files a test run would read (racing = noise), and this stream ships
  no code. Stream-reported baselines stand: 434 / 377 / 350 passed with the
  same 2-3 FOREIGN failures (plugin-bundle drift → `tools/sync_plugin.py`
  at integration; the intermittent
  `test_mep_views_spaces::test_schedule_view_and_space_write_and_verify`).

---

## 1 · Cells marked better than the evidence supports

### 1.0 Two structural over-credits in the HARNESS (bigger than any one cell)

1. **The gate is a whole-file validator, credited to every cell that names
   the file — with NO per-cell semantic assertion.** `matrix.json` carries
   probes ONLY for read cells (`class_decode`/`category_decode`/`callable`);
   `grep -c 'semantic\|readback\|assert' matrix.json` = 1 (a note), and
   `tools/coverage.py` has no readback path. So `conduit_modify.rvt` earns
   conduit modify + move + retype + fittings move; `device_modify_move.rvt`
   earns receptacle modify + move + retype — because ONE file validates.
   `rvt.validate` proves framing/ECC/reference/connector-graph integrity;
   it cannot know that a diameter went 2"→1" or that a receptacle slid 2 ft
   along ITS wall. The semantic re-reads that would prove it live in each
   stream's `make_*.py` → `manifest.json`, which the harness never reads.
   **Fix:** give every non-read cell a `check` callable (a
   `Document.from_file` assertion returning pass/fail + a fact string) — or
   ingest the streams' `manifest.json` readback verdicts — and make
   VALIDATES require `validator 0 errors AND check passed`.
2. **The READ column is 27/27 free greens.** `class_decode` passes if the
   corpus has ≥1 element of the class and 3–5 sampled records decode
   without exception; `category_decode` (doors/windows, columns/beams,
   lighting fixtures) decodes NOTHING — it counts category ids
   (columns/beams passed on `-2001320=0, -2001330=138`: ZERO elements in
   the structural-columns category, contradicting the cell note "131
   structural columns" — the constant or the note is wrong; the probe
   didn't care). "doors/windows read ✅" therefore proves only that 200
   elements carry two category ids. Strip the free reads and the mutating
   verbs stand at **54/125 = 43.2%** (81−27 proven of 152−27 applicable).
   **Fix:** read probes should decode ≥N records with 0 dirty AND assert
   the fields a downstream verb needs (host id, level, type, curve/point,
   connector count) are present and self-consistent.
3. **"53.3% PROVEN" merges VALIDATES (viewer-PENDING) with CERTIFIED.**
   Only 19 cells (12.5%) have Autodesk's reader on record; the conduit
   (6/6) and devices (6/6) rows show "100%" with ZERO certified cells. The
   report says this in prose, but the row column reads as a claim. Lead the
   headline with certified % and print `proven-uncertified` separately.
4. **Strict-gate blindness.** `coverage.py` calls `validate_file()`
   non-strict and prints only `errors=`. Under `--strict` two of my four
   .rvt spot files FAIL — `panel_schedule_view.rvt` and `space_create.rvt`
   (structure ERROR, `Partitions/14`: 3 blocks whose A/C header counters
   violate the ISIZE identity — the known `commit.py` off-by-4·A defect, all
   three MEP streams diffed the same fix). `cable_tray_create.rvt`,
   `device_delete.rvt`, `conduit_delete.rvt`, `wire_create.rvt` are
   strict-clean (the conduit/electrical streams' local commits carry the
   fix; the schedules/spaces create path does not). Reader-tolerated ⇒ the
   default verdict is fine, but the matrix should record the strict verdict
   + warning text per file so "warning=1" (the corpus ES-decode gap) is
   distinguishable from "strict-INVALID (writer counter defect)".

### 1.1 Cell-by-cell (evidence weaker than the glyph)

| cell | marked | what the evidence actually is |
|---|---|---|
| cable tray · create (+ read/modify/move/retype/delete) | ✅ VAL / VAL / UNPR×4 | The `CableTray` record IS substantive (my re-read: width 1.0 ft × height 0.333 ft, `m_calculatedSize` "305 mmx102 mm", rungSpace 0.75, own connector manager + centre-line, `m_idType 643893`). But NO cable-tray element exists in ANY 2026 sample: the run/CL category ids `-2008147/-2008137` are INFERRED, the class was morphed from a conduit, and the "read ✅" cell reads 7 tray TYPES (no instance is readable anywhere). VALIDATES here measures self-consistency of a synthesis, not conformance to anything Revit wrote. Whole row should be EXPERIMENTAL/UNPROVEN pending a real specimen or viewer acceptance. |
| tags/annotation · modify | 🏆 CERT | Proof = V18/V19: a title-block RTF label rewritten by `tools/make_v19.py` (size-preserving byte edit + adler32 record stamp). An authored-text stunt on a title-block instance — no `rvt.*` API implements tag/text/dimension MODIFY (leader, host, tagged element, tag type). The row name implies tag editing; the evidence is one hand-stamped byte patch. |
| tags/annotation · create | ✅ VAL | = a `RoomTag` (space tag) placed with its space in `space_create.rvt`. `IndependentTag` (the 1,407 device/panel/circuit tags a set is made of), `TextNote`, dimensions: not creatable. Row shows 4/6 (67%); annotation authoring is effectively 0. |
| views/sheets · modify + delete | ✅ VAL ×2 | Both borrowed from the PanelScheduleView proofs (rename / cluster-delete of a *panel schedule view*). No plan/3D/section/SHEET has ever been created, edited or deleted; row reads 3/5 (60%) while sheets are 0. |
| panel schedules · create ×2 | ✅ VAL (row 4/5, 80%) | My re-read: view 888019 → target = NEW panel 888014, template 638860, `m_outOfDate=true`, name EP-NEW-1 — correctly wired. But the deliverable behaviour (Revit REGENERATES the ~150 KB cell table for a rewired clone) is computed-on-open and un-testable by any validator; the stream itself lists it as acceptance hypothesis (a). VALIDATES cannot speak to it; this row's real evidence is "structure OK, function unknown". |
| walls · create | 🏆 CERT | Correct via V22/H2 — but note `space_create.rvt` is ALSO listed as a wall-create proof: that ONE file is credited to four cells (walls create, rooms/spaces create, tags create, and it is the space row's evidence). Fine for the ledger; misleading as a count of independent proofs. |
| rooms/spaces · create | 🏆 CERT | The CERTIFIED files (V23/V25/V26) create ROOMs from IFC; the MEP SPACE + ZoneElement + space-tag path (`space_create.rvt`) is only VALIDATES and its acceptance-critical hypothesis (a `SerializedDummy` point space is picked up by room computation without `LevelRoomPlan` registration) is untested. Report the space sub-cell separately. |
| electrical equipment · create | 🏆 CERT | Fine (V23–V29/H1/H2 viewer-PASS). But the row's 83% hides that a placed panel/transformer CANNOT be deleted (delete UNPR; a panel's circuits/wires/schedule need a cascade nobody wrote) — the row is create-heavy, retire-blind. |
| levels · modify | 🏆 CERT | M3 rewrites the level's two datum-plane origins ONLY; nothing hosted on the level is re-solved (viewer PASSed because hosted elements keep absolute Z). The note should say "datum re-labelled; hosted elements do NOT follow" — a contractor reads "level modify" as "raise the floor and everything on it". |
| fittings · create | ✅ VAL | ONE geometry: 2" 90° elbows reusing the shared clone 679082 (other size/angle needs a clone the template lacks; tees/crosses/unions absent; cable-tray fitting BLOCKED). The 4/6 (67%) row is one specimen deep. |
| circuits · delete / equipment · delete / types · delete / families · delete / phases · delete … | ⚠️ UNPR ×12 | Correctly UNPR, but the note pattern "generic delete_element" recurs 12× as if a proof were a formality. For circuits, equipment, levels, types and families the delete is a CASCADE PROBLEM (loads' back-links, every hosted element, every instance of a type), not a missing test — several will need new neutralisers, and `device_delete.rvt` already shows the residue: circuit 469428's `ElectricalLoadClassificationsData` cache still carries 17,437.5 (internal VA) after its receptacle was deleted (Revit recomputes, so it validates — but "delete-when-emptied" (devices O4) is a live policy hole, not a footnote). |
| electrical fixtures/devices · 6/6 (100%) | ✅ VAL ×6 | Honest on receptacles/switches. But the row LABEL implies the whole device family (data/comm/fire-alarm/security/j-boxes); the stream's own table says those have NO proof (no loaded family in the template) — the row is receptacle-only at 100%. |

### 1.2 Cells where the evidence held up (spot-check verdicts)

* `device_delete.rvt` — 467291 / 444176 absent; validator graph
  (2.57 M refs, 15,315 connector edges) 0 errors, strict-clean; no dangling
  reference. Honest delete.
* `conduit_delete.rvt` — 0 errors default + strict; the equipment surface
  tap neutralisation is real.
* `wire_create.rvt` — the two new wires carry FRESH GLine geometry (not the
  specimen's) and reference real devices (466882…) with mutual connector
  refs. Genuine create, strict-clean.
* `space_create.rvt` — 4 SWalls 888014-17 + ZoneElement 888018 + RoomElem
  888019 (`m_volumeBoundingElems` = the 4 walls, zone/level/point set) +
  RoomTag 888020. Real structure; only the acceptance hypothesis is open
  (and strict-FAIL on the counter defect, §1.0-4).

---

## 2 · Categories entirely ABSENT from the matrix that an electrical / MEP contractor's deliverable needs

The matrix's 28 rows are model-element rows. The DELIVERABLE (a sheet set)
and half the electrical workflow have no row at all:

* **Sheets as an authored thing** — sheet (DBDrawing) create, title-block
  instance, VIEWPORT placement (a plan / a panel schedule ON a sheet), sheet
  numbering, sheet issue/revisions. The `views/sheets` row exists but is
  read + two borrowed schedule-view proofs; nothing sheet-shaped is written.
* **Schedules other than panel schedules** — `DBViewSchedule` CREATE with
  fields/filter/sort: equipment schedule, lighting-fixture schedule, device
  schedule, conduit/cable-tray run schedule, SHEET LIST. The panel_schedules
  read note waves these off as "category queries — no per-target authoring
  needed"; a contractor set is 30–50% schedules.
* **Legends** (DBViewLegend + legend components / symbol legend) — no row.
* **One-line / riser diagrams** — drafting views (DBViewDrafting) + detail
  lines / detail items / detail components — no row; the single-line is
  the first sheet of every electrical package.
* **General annotation authoring** — TextNote create, dimensions
  (LinearDimString etc.), keynotes, revision clouds + revision settings /
  schedule, callouts / section marks / elevation marks, spot elevations —
  the tags row's "create" is only the space tag.
* **Grids** (GridElement) + reference planes / scope boxes — no row;
  every plan is located to grid.
* **Electrical analytical loads** (Revit ≥2023 analytical distribution:
  ElectricalAnalyticalNode / area-based & equipment loads, load sets) and
  **load calculations / demand results** (what the panel schedule totals
  come from) — no row; the settings row stops at demand-FACTOR
  definitions.
* **Openings / penetrations / sleeves** (wall/floor/shaft openings) — no
  row; a coordination deliverable.
* **Device kinds beyond receptacle/switch/light** as their OWN evidence
  rows — fire alarm, data/comm, security, nurse call, communication;
  junction/pull boxes; disconnects; motor connections (mechanical
  equipment carrying electrical connectors). Currently a "same code path,
  no loaded family, no proof" footnote inside the devices row.
* **Equipment kinds beyond panelboard/switchboard/transformer/lightfixture**
  — generators, ATS, UPS, MCC, VFD, switchgear lineups, motors. The job
  runner literally SKIPs `kind: generator` (`NEEDS-FAMILY`).
* **Fittings breadth** — cable-tray fittings (BLOCKED), conduit tees /
  crosses / unions / non-90° and non-2" elbows: one fitting geometry today.
* **Duct / pipe write verbs** exist as rows but create/move/retype MISS —
  irrelevant to a pure electrical shop, blocking for "MEP contractor".
* **Groups / assemblies** (Group + GroupType, AssemblyInstance/-Type) — the
  standard-room reuse pattern; no row.
* **Family LOADING into a project** (insert a Family + FamilySymbols from an
  .rfa) — the families row measures .rfa round-trip and marks "create"
  = from-scratch authoring MISS, but the everyday operation ("this seed
  lacks the trapeze family — load it") is neither row nor cell, and it is
  exactly what every job-runner NEEDS-FAMILY gap resolves to.
* **Project info + shared/project parameters** (ParamElemProject/External
  + ParamBinding create) — the parameters row admits authoring is absent;
  circuit-tag / install-status parameters bound to categories are routine.
* **Design options, worksharing / central models, Revit LINK create, CAD
  imports (ImportInstance)** — worksets/links row is read-only; a real firm
  base is workshared and LINKS the architectural model (today the proofs
  edit the arch sample in place, which no live project permits).

---

## 3 · The front door `tools/rvt_job.py` — three modes + gate loudness

12 runs. What holds:

* All three good runs (create room-spec `--auto-circuits`, edit ops.json,
  from-ifc hardened.ifc) exit 0, and EVERY manifest — including the four
  adversarial ones that produced a file — carries
  `gates.base_provenance = PROOF-ONLY, NOT-DELIVERABLE` with the G1 count
  (27,879–27,895 sample-derived elements) and `deliverable: false`. **The
  PROOF-ONLY truth is honest and unskippable.** ✔
* Loud where it should be: unknown op → exit 2 + FAILED manifest
  (`planning: unknown op 'levitate' (allowed: [...])`); ghost id → exit 2 +
  FAILED manifest (`element 999999999 has no seq-102 record`); non-cascade
  delete of wall 573703 → exit 2 + FAILED manifest + dependents report,
  nothing written. ✔

What does NOT fail loudly:

1. **The missing-family spec is a SOFT GREEN.** My spec asked for four
   things: a wall of type `NO SUCH WALL TYPE 900mm UNOBTAINIUM`, a
   `TotallyFictional Panel XZ-9000 - 6000A` panelboard, a `generator`, a
   `trapeze`. Result: **exit 0, "hard gates PASSED"**, and the file contains
   a wall built on a THICKNESS-ONLY substitute (`STB 20.0`), the panel as a
   "WEAK" stand-in (`M_Lighting and Appliance Panelboard - 208V MCB… 400 A`
   — the audit itself says it "shares no voltage/rating with the spec
   type"), and 2 of 4 equipment items SKIPPED (`NEEDS-FAMILY`). Half the
   requested scope silently omitted, wrong types on the other half, console
   and exit code green; the ONLY record is `gates.seed_audit.gaps` (verdict
   WARN — `missing_or_unsupported: 0` because NEEDS-FAMILY skips and
   no-name-match substitutions are classified WARNING). `--allow-not-ready`
   had nothing to override (byte-identical outcome). **This is the
   "automation fails RED, never skips green" violation:** NEEDS-FAMILY
   skips and THICKNESS-ONLY / WEAK substitutions must escalate to
   `SEED NOT READY` (exit 2) unless the spec item is marked optional (or the
   override flag is passed), and even then the manifest status must read
   `… WITH OMISSIONS (2/4 equipment skipped, 2 type substitutions)` with
   `elements.skipped` populated — not a bare "hard gates PASSED".
2. **Input-parse failures bypass the manifest contract.** Malformed
   ops.json (JSONDecodeError), an unparseable IFC (`ifcopenshell.Error:
   Unable to parse IFC SPF header` + a secondary `Exception ignored in
   __del__ … KeyError`), and a non-OLE base (`NotOleFileError`) all die
   with raw Python tracebacks, **exit 1 ("usage/unexpected", not 2), and
   write NO manifest.** The plugin SOP is "read the manifest, not the
   console" — for the most likely user error (a bad attachment) there is no
   manifest to read. Catch these, exit 2, emit `status: FAILED (input)`
   with the parse message in `gates.input`.
3. Minor: `edit` accepted an `.ifc` path as its base and only failed deep
   in olefile — no upfront magic-byte / extension check. `from-ifc` does
   not run the harden step the SOP describes (the SOP hardens; the runner
   assumes a hardened file), so a syntactically valid but un-hardened IFC
   flows straight to the seed audit with degenerate insertion points.

---

## 4 · Single highest-leverage next cell, per row

Ordered by product leverage, not row order; one cell each.

| row | next cell | why it moves the most |
|---|---|---|
| **circuits / electrical systems** | circuit an EXISTING device onto an EXISTING panel (the phase-2 two-sided connector edit; blocked in devices O1 / conduit / job runner) | THE electrical workflow; today every circuiting proof also creates its loads |
| **views / sheets** | CREATE sheet + place a viewport (a plan and a panel schedule on a title-blocked sheet) | turns 51 proof files into a deliverable set; nothing else in the matrix produces the thing the client receives |
| **families (.rfa)** | LOAD a family (+ symbols) into a project from an .rfa | resolves every NEEDS-FAMILY / "place one instance" gap the job runner reports; unblocks generators, trapezes, j-boxes, data devices |
| **electrical equipment** | DELETE a panel WITH its circuits/wires/schedule view (cascade + neutralise) | the row is 83% but a placed panel can't be retired |
| **wires** | MODIFY (wire type / gauge / vertex reroute) | wires are the most-edited electrical element; row is create/delete only |
| **panel schedules** | viewer-open `panel_schedule_view.rvt` (does Revit regenerate the table for a rewired clone?) — a certification, not code; then RETYPE (template swap) | the whole 4/5 row rests on an untested computed-on-open hypothesis |
| **tags / annotation** | IndependentTag CREATE (device / panel / circuit tags in a plan view) | replaces the title-block-RTF "CERT" with real annotation authoring; unlocks tagged plans |
| **conduit** | conduit ↔ equipment surface-connector tap (BLOCKED) after viewer cert of `conduit_create.rvt` | an open-ended run is a drawing, not a raceway system; the 6/6 row is 0/6 certified until the cached-extrusion (SerializedDummy) question is answered by the viewer |
| **cable tray** | acquire ONE real cable-tray specimen (author it in Revit into a fixture file / hunt dach-sample) and re-anchor the class morph + confirm the OST ids | every tray cell is currently self-referential |
| **fittings** | TEE + a second elbow clone (branching, other sizes/angles) via the closed-form frame | conduit trees cannot branch |
| **electrical fixtures / devices** | one proof file on a template with data / fire-alarm / j-box families loaded (the code path exists) + viewer cert of `receptacle_wall_hosted.rvt` | makes the row label true |
| **lighting fixtures** | switched lighting circuit (fixture + its switch, switch-id on the system) — subsumes the pending light MOVE/RETYPE proofs (cheap, code exists) | lighting is delivered as switched circuits, not fixtures |
| **rooms / spaces** | viewer-open `space_create.rvt` (hypothesis: point space + SerializedDummy is picked up by room computation) before more space code | 3 of the row's 5 cells are viewer-pending on one hypothesis |
| **walls** | MOVE (location-line translate + hosted-plane/fixture rehost) | first system-host move; the pattern generalises to floors/ceilings |
| **doors / windows** | CREATE wall-hosted door (opening + host regen) | every electrical room needs its door (panic hardware, clearance) |
| **floors / roofs / ceilings** | CREATE floor by sketch loop | slab under the electrical room, housekeeping pads, floor-device hosting on a real slab |
| **levels** | CREATE level in a host project (with its LevelRoomPlan / plan view) | the job runner already FELL BACK on a missing level ("T.O. Structure") in the good create run |
| **types** | DELETE type guarded by dependency_report (purge-unused shape) | first non-instance delete; template hygiene |
| **parameters** | shared / project parameter CREATE (ParamElemProject / External + ParamBinding to categories) | custom circuit / status parameters are on every real template |
| **worksets / links** | Revit LINK create (RvtLinkSymbol + RvtLinkInstance of the arch model) | every real electrical model links the architect; today the proofs mutate the arch sample directly |
| **family instances (generic)** | viewer-certify `M1_delete.rvt` / `M1_delete_rac.rvt` (delete is the row's only VAL) | closes the row at 6/6 CERT for the cost of an upload |
| **columns / beams** | column MOVE proof (move_instance already handles point instances) + cert `M1_delete_rac` | cheap; but low priority for an electrical shop |
| **materials** | none — mark out-of-scope for the electrical bar | spend nothing |
| **curtain walls / stairs & railings** | none — mark rows out-of-scope (architectural authoring) | removes 12 red cells that will never matter to this product from the denominator |
| **duct / pipe** | port `move_run/retype_run/delete_run` from conduit to RbsDuctCurve (same run model, 4 cells per port) — DEFER until the electrical bar is met | only relevant to "MEP", not "electrical" |
| **phases** | MODIFY (rename/description via set_param) or mark the row NA | trivial proof or honest exclusion; either way it's a row that never blocks a job |
| **panel data (equipment · modify)** | already CERT — next is the panel schedule TEMPLATE retype (see panel schedules row) | — |

BRANCH STATE: coverage-critic memo written to `docs/inbox/coverage-critic.md`;
`tools/coverage.py run` (full regen) executed clean — headline reproduced at
53.3% proven / 12.5% certified with all 6 generators re-run; 6 proof files
spot-checked (2 strict-INVALID on the shared counter defect, cable-tray row
found self-referential, one stale circuit-load cache after delete);
`tools/rvt_job.py` exercised in all 3 modes + 8 adversarial inputs (soft-green
on missing families / substituted types, no manifest on parse failures, loud
elsewhere, PROOF-ONLY provenance truthful throughout); no code modified.

| category | verb | status | proof file | notes |
|---|---|---|---|---|
| coverage harness (`tools/coverage.py`) | run | VALIDATES | docs/coverage/matrix.{json,md} (regenerated this run) | full regen 168 cells / 51 proofs / 27 probes clean; headline 53.3%; harness lacks per-cell semantic checks, strict verdicts and honest read probes (§1.0) |
| front door (`tools/rvt_job.py`) | create / edit / from-ifc | VALIDATES | scratch: job/good_{create,edit,fromifc}.rvt (+ manifests) | all 0 validator errors, PROOF-ONLY stamped truthfully |
| front door | fail-loud gates | BLOCKED (partial) | scratch: job/bad_*.rvt + run.log | loud on unknown-op / ghost-id / dependents; SOFT-GREEN on missing families + type substitution; parse failures die with tracebacks and NO manifest (§3) |
