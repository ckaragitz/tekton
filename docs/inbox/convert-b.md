# inbox: convert-b — COMBINATION INPUTS: creating INTO existing files

Stream: convert-B (the permutation mandate's combined-input cells).
Territory: `src/rvt/convert/{__init__,add_to_project,merge_ifc,
modify_family}.py`, `tests/test_convert_combo.py`,
`experiments/convert_combo/**`, this note.  Everything else imported, never
edited (constraint honoured: no changes to tools/frontdoor.py,
plugin/skills, src/rvt/frontdoor/base.py, src/rvt/versions/).

## What was delivered — three combination routes, all composition

The design rule followed: a combination route is a RETARGETING of the
already-certified stages, never per-route authoring code.

### (1) prompt + RVT -> RVT  (`rvt.convert.add_to_project`)

"add a 100 A lighting panel to my project" against the user's own file.
Composes: `rvt.frontdoor.prompt_intent.prompt_to_intent` (the certified
rules-first vocabulary) -> retarget onto the TARGET -> `tools/ifc_intent.py`
stage F/L/W/E (loaded as a module; the certified build stages) pointed at
the target instead of the genesis base -> gates.

The TARGET is the authority:

* RELEASE — `rvt.versions.detect_release`; output = a splice of the input,
  so the release is preserved BY CONSTRUCTION and re-verified on every
  output (`validation.*.release.preserved`).  A target whose release has no
  certified creation base is REFUSED with
  `rvt.versions.creation_status(...)`'s own reason (no silent
  newer-release file).
* SCHEMA — the target's own `Formats/Latest` installed at the codec
  chokepoints (`standalone.install_schema`); a byte-different schema in the
  same process fails RED (`ensure_target_schema`).
* LEVELS — placement on the target's own level (`--level` index/name;
  default nearest elevation 0); the level's elevation is folded into the
  equipment z.
* WALLS/CONTENT — target surveyed into a content bbox (walls via their own
  `VWallDriver` GLines + instance origins); new equipment lands in free
  floor space just outside it (deterministic rule, recorded), `--at X Y`
  overrides.
* SPECIMENS — `standalone.ConstructedSpecimens(base_path=TARGET)`: the
  zero-donor constructed templates, built against the target's own
  level/phase/wall-type.  Nothing cloned from any Autodesk-authored
  element, on any target.

Proof A1 (our own file): target = the front door's acceptance output
`experiments/frontdoor/ifc-electrical-room-2500a/electrical-room-2500a.rvt`.
`experiments/convert_combo/A1_add_own/`: LP-1 generated (.rfa deliverable,
famgen validate VALID + provenance ok), four-registry loaded (census
coherent, 10 units / 9 GUIDs consistent), placed free-standing 1 m east of
the room (x=19.21 ft), validator **VALID 0 errors**, release 2026 -> 2026
preserved.  Elements: instance 1473067, symbol 1473065, family 1473049.

Proof A2 (QUARANTINED foreign sample, dev-only):
target = `samples/rmebasicsampleproject.rvt` (32.6 MB, the MEP sample).
`experiments/convert_combo/A2_add_rme_devonly/` — RESULTS BELOW (§A2).

### (2) IFC + RVT -> RVT merge  (`rvt.convert.merge_ifc`)

The IFC resolved by the certified resolver (`rvt.ifc.intent.resolve_intent`
via `rvt.frontdoor.intent.intent_from_ifc`), the WHOLE intent translated by
a deterministic DISJOINT offset (incoming content lands east of the
target's bbox + margin, y-centred; `--offset DX DY` overrides; recorded
pre/post), then the same build-into-target engine.

Proof B1: `inputs/ifc/electrical-room-2500a.ifc` merged into a COPY of the
acceptance output (`experiments/convert_combo/B1_merge_ifc_into_own/`):
offset (+12.309, −1.115) m — the incoming room's walls land at x 7.7–16.9 m,
strictly clear of the target's [−4.6, 4.6] m; 8 families generated+loaded,
4 walls appended, 8 instances placed.  Validator **VALID 0 errors** (1
warning = the target's own pre-existing DataStorage ES-blob decode gap,
inherited, not introduced), four-registry coherent (17 units), release
preserved, the walls+families OPEN-BUG stamp applied exactly as the front
door does (`mode=stamp-proof-only`, stamp in the manifest; `--strict`
gives the two-file degrade).  Created ids (28): 1473051…1473490 — full list
in `out/manifest.json` `created_ids`.

### (3) prompt + RFA -> RFA  (`rvt.convert.modify_family`)

Natural-language family edits through rvt.manipulate's certified modify
path applied to the family document's self-`Family` record — an `.rfa`
carries the same stream set as a project (partition + ElemTable +
Global/Latest), so `mutate.Document.from_file` + `manipulate.modify_element`
+ `commit_plans` work on it directly (spiked + proven).  Value carriers
verified on our generated families: `m_value` (doubles, internal units),
`m_int` (int64 specs), `m_str` (string specs) — ratings, counts AND
names/strings all editable.  Unit conversion is SPEC-driven from the
parameter's own `m_specTypeId`: amps as-is, volts ×1/0.3048² (the
skeleton's verified constant), lengths to feet with an EXPLICIT unit
required (never guessed), kVA ×1000×factor.  Renames also patch the
`PartAtom` Atom-XML (title/type title) through the container writer.

Vocabulary: text ("rename the type to X; set BusRating 225; set PanelName
DP-7"), inline JSON, or ops.json — three shapes, one ops vocabulary
(`rename-type | rename-family | set-param`).

Proof C1 (our own generated family):
`experiments/convert_combo/C1_modify_own/` — rename type + BusRating 225 +
MainsRating 225 + PanelName DP-7 on `dp1_eaton_prl2x_400a_42sp_480y_277.rfa`:
family-mode validator **VALID 0 errors 0 warnings**, structural verify
clean (0 CRC / 0 ECC / 0 walker, stamps ok, ElemTable == header), release
2026 preserved, every edit proven by semantic RE-READ, PartAtom followed
(old type name gone).

Proof C2 (family rename + voltage):
`experiments/convert_combo/C2_rename_family/` — "rename the family to
Lighting Panelboard LP-9 208Y120 100A; set Voltage 208 V; rename the type"
=> new file name, PartAtom title ×4 occurrences replaced, Voltage internal
2238.8934 (== the verified 208 V constant), all gates green.

Proof C3 (FOREIGN Autodesk .rfa, dev-only, vendor donor): OPEN + INVENTORY
work (`--inventory` lists the table family's 4 types and 8 params, captions
+ specs resolved), parse works; COMMIT is blocked by a named gap:
`stream_encoders.decode_elemtable` refuses the foreign family's 600-byte
ElemTable footer / 18-entry GRAVEYARD ("GraveyardRec wire layout not
observed in corpus").  Honest per-cell status: our own .rfa = WORKS;
foreign .rfa = PARTIAL (read/parse yes, write blocked on the graveyard
codec — follow-up filed below).

## Per-cell status (honest)

| cell | status | evidence |
| --- | --- | --- |
| prompt+RVT->RVT, our own target | WORKS | A1: validator VALID 0 err, census coherent, release preserved, re-runnable CLI |
| prompt+RVT->RVT, foreign sample target (dev-only) | WORKS | A2 (§below): VALID 0 err on the 32.7 MB rme output, census coherent 308 units, release preserved |
| IFC+RVT->RVT merge, our own target | WORKS | B1: 28 created ids, VALID 0 err, open-bug stamp honest |
| IFC+RVT->RVT merge, foreign sample target (dev-only) | WORKS | B2 (§below): 8 families + 4 walls + 8 instances into rst, VALID 0 err, open-bug stamp, release preserved |
| prompt+RFA->RFA, our own family | WORKS | C1/C2: VALID 0 err, re-read proofs, PartAtom in step; C4 = convert-a's ops surface over the same engine |
| prompt+RFA->RFA, foreign family (dev-only) | PARTIAL | C3: read+parse yes; commit blocked: ElemTable graveyard codec gap |
| non-2026 targets (2024/2023/2025) | REFUSED HONESTLY | `creation_status` reason quoted; the release fleets own those bases |

## Findings / decisions

1. **An .rfa is a project-shaped container.**  Same stream set (partition,
   ElemTable, Global/Latest, BasicFileInfo…), one save unit; the manipulate
   pipeline (modify → one commit → re-block → re-emit ElemTable → CRCIO)
   runs on it unchanged, including VARIABLE-LENGTH edits (type renames).
   This makes family editing a composition, not new machinery.
2. **Family param value carriers**: `m_value` / `m_int` / `m_str` split by
   spec type (verified on generated families: PanelName in m_str='DP-1',
   Phases in m_int=3, BusRating in m_value=400.0).  The caption lives on
   `ParamElemFamily.m_pParamDef.value.m_caption`.
3. **ConstructedSpecimens generalises to any target** — it only needs the
   target's schema + a Level (+ optionally a BasicWallType); template ids
   990000001/2 are far above real watermarks.  This is the zero-donor
   answer for foreign files too.
4. **`install_schema` is install-once per process** — a second call with a
   different base is a silent no-op for the SINGLETONS.
   `ensure_target_schema` therefore sha-compares and fails RED on
   mismatch, with the snapshot-order subtlety in finding 7.
5. **The open-bug stamp composes**: merge into an existing file uses the
   SAME `combination_check` degrade (verdict recorded, stamp ridden, or
   `--strict` two files).  When the target already carries native walls
   and this run only LOADS families, the record notes the L1a precedent
   (foreign host load) instead of claiming the bug shape.
6. **Foreign real-world ElemTables carry GRAVEYARD footers** our
   stream_encoders refuse (C3; also expected on aged user projects).  The
   named blocker is in the codec, not the route.
7. **`install_schema`'s shared state is overwritten by a second call's
   `bundled_schema` step even though the SINGLETONS stay on the first
   schema** — a naive after-the-call comparison always passes.
   `ensure_target_schema` therefore snapshots the state BEFORE installing
   (guard covered by `test_schema_mismatch_fails_red`).
8. **Type-scoped parameter edits** landed after C3 exposed the wart:
   `set X of type "T" V` (quotes required for names with spaces) and the
   JSON `"type"` key scope the edit to one type-table pair; scoped edits
   deliberately skip the `m_familyParams` (current-defaults) mirror.
   convert-a's `normalize_ops` passes the scope through (their ack).

## Requests / follow-ups (proposed tickets)

1. **GraveyardRec wire layout** in `rvt.stream_encoders.decode_elemtable`
   (+ encode round-trip): unlocks foreign-.rfa edits and any foreign file
   with a populated graveyard.  Exact signature: "ElemTable footer is 600
   bytes / graveyard 18 — GraveyardRec wire layout not observed in corpus"
   on `vendor/phi-ag-rvt/examples/Autodesk/racbasicsamplefamily-2026.rfa`.
2. **Viewer acceptance run** for the convert_combo outputs (A1, A2, B1,
   B2 — .rvt) and a famload smoke of the edited C1 .rfa into a base: the
   viewer is the only oracle above self-checks.  All files declare
   certified-base ancestry via their targets; controls per the probe_batch
   contract.
2b. **`tools/sync_plugin.py` needs an orchestrator re-run**: the sync
   mappings already cover `lib/src/rvt/convert/*` (synced mid-stream), and
   `test_plugin_is_in_sync_with_source` now reports 3 drifted files
   (modify_family / edit_family / add_to_project — this stream's late
   edits).  Deferred to the orchestrator exactly as the manipulate stream
   did: a stream-run sync would sweep other streams' in-progress files
   into plugin/.
3. **Face-hosting fidelity**: wall-mount panels are placed free-standing
   upright (certified shape); hosting onto the TARGET's own walls = the H1
   SketchPlane recipe over `resolve_target`'s wall survey.
4. **Vocabulary merge with convert-a — ALREADY COMPOSED** (landed
   mid-stream): their `rvt.convert.edit_family` structured-ops surface
   calls this stream's engine (`inventory_family` / `apply_family_edits` /
   the JSON vocabulary); proven live in C4.  The NL grammar deliberately
   stays in `modify_family` (their docstring defers it); the delegation
   hook (`parse_family_edit` polls a sibling export) stays dormant until a
   shared contract is agreed.  No action needed beyond keeping the JSON op
   shapes stable.
5. **Dimension edits are value-only** on generated families (no constraint
   graph): geometry-true resizing = regenerate from the facts sidecar
   (`families/<stem>.json`).  Recorded as a caveat on every length edit.
   (Plugin re-sync: covered by 2b above.)

## KNOWLEDGE.md proposal (append)

> ## Combination inputs (rvt.convert, 2026-08-04)
> - Any "X into existing file" route = retarget the certified stages onto
>   the target: target's schema installed (sha-guarded), specimens
>   CONSTRUCTED against the target, stage F/L/W/E from tools/ifc_intent
>   pointed at it, release preserved by splice + re-verified.
> - .rfa files are project-shaped: rvt.manipulate commits (including
>   variable-length type renames) work on them unchanged; keep PartAtom in
>   step when names change.  Param carriers: m_value/m_int/m_str by spec.
> - Foreign real-world ElemTables may carry graveyard footers our codec
>   refuses — the current foreign-file editability ceiling alongside
>   ES-blobs.

## A2 — the quarantined foreign-sample proof (rme) — GREEN

`experiments/convert_combo/A2_add_rme_devonly/` — target =
`samples/rmebasicsampleproject.rvt` (32.6 MB, watermark ~888k, an Autodesk
MEP project the tools were not built against; QUARANTINED stamp applied):

* prompt "add a 100 A lighting panel and a 75 kVA transformer to my
  project" -> LP-1 (.rfa, famgen validate VALID + provenance ok) + T1
  (.rfa, same);
* four-registry LOAD into the sample: LP-1 234.6 s, T1 331.0 s (chained;
  host ids 888055/888071, 888112/888125);
* placed FREE-STANDING east of the sample's content bbox
  ([−15.1, 53.1] m -> offset +54.1, +19.9 m): LP-1 upright at
  (183.81, 65.4, 4.97) ft, T1 yaw at (178.75, 65.4, 0.64) ft — elements
  888127 / 888128, 0 dangling refs each;
* GATES on the 32.7 MB output: validator **VALID 0 errors**, four-registry
  census coherent (**308 units / 307 ContentDocuments** — the sample's own
  306 + our 2, all four registries agreeing), release 2026 -> 2026
  preserved; total 877 s.
* the single warning is the sample's own PRE-EXISTING Extensible-Storage
  decode gap (1171/142289 seq-102 FamilyInstances, the manipulate stream's
  documented ~4.2 % rme ceiling) — inherited, not introduced.

This composes M2_rac (foreign-file edit) + L1a (foreign-host family load)
+ stage-E placement into ONE runnable route on a real foreign project.

## C4 — the two-stream vocabulary composition — GREEN

convert-a's `rvt.convert.edit_family` (structured-ops surface) landed
mid-stream and CALLS this stream's `modify_family` engine
(inventory_family / apply_family_edits / the JSON ops vocabulary).  Proven
live: `experiments/convert_combo/C4_ops_surface/` — their CLI
(`--set "BusRating=225" --rename-type "225A MLO 30ckt"`) over our engine:
family-mode VALID 0 errors, re-read ok.  No conflict: NL grammar stays in
`modify_family` (their docstring defers it deliberately); their ops
normalise into the same JSON shapes `parse_family_edit` accepts.

## B2 — merge into a quarantined sample (rst) — GREEN + determinism control

Charter proof: `experiments/convert_combo/B2_merge_rst_devonly/` (this
stream's run) — the electrical-room IFC merged into
`samples/rstbasicsampleproject.rvt` (6.7 MB, the L1a lineage sample;
QUARANTINED stamp applied):

* 8/8 families generated + four-registry loaded (census coherent, **61
  save units** = rst's 53 native + our 8);
* 4 walls appended + 8 instances placed at the auto-disjoint offset
  (+32.773, −5.945) m — the incoming room lands strictly east of rst's
  content bbox ([−11.5, 25.1] m);
* validator **VALID 0 errors** (1 warning = rst's own pre-existing 7
  ES-blob records: RebarShape ×6 + DataStorage ×1 — inherited);
* release 2026 -> 2026 preserved; `mode=stamp-proof-only` with the
  walls+families OPEN-BUG stamp (this run creates walls AND loads
  families — stamped exactly as the front door does);
* 28 created ids reported in `manifest.json` `created_ids`
  (1472568…1473007); 519.5 s.

DETERMINISM CONTROL (unplanned but valuable): a sibling stream (the
perm-matrix stream, per the orchestrator relay in this record's co-edits)
independently ran the SAME merge through the same CLI into
`experiments/convert_combo/B2_merge_ifc_rst_devonly/` — also VALID 0
errors / census coherent / release preserved / open-bug stamped (517 s).
Cross-comparison of the two runs: `created_ids` IDENTICAL (all 28), same
offset/mode/gate verdicts, output byte SIZES IDENTICAL (6,766,592); ONLY
the sha256 differs — the per-load MINTED identity (uuid4
content-document / famDoc / session GUIDs), deliberate fresh identity,
not route nondeterminism.  Two independent runs of the combination engine
converge on the same elements at the same ids.

RUN ATTRIBUTION — DISK EVIDENCE (adjudicable, identity-claims aside):
the session task records on disk settle WHICH TASK wrote WHICH dir:

* task `bg8zh5iun` (launched 23:34) -> `B2_merge_rst_devonly/` — its
  output names only that dir; the stream writing this record holds this
  task id in its own transcript (it also ran A1/A2/B1/C1–C4 and authored
  their sections);
* task `bsb65kfwu` (launched 23:35) -> `B2_merge_ifc_rst_devonly/` — its
  output names only that dir; this task id does NOT appear in this
  stream's transcript.

ADJUDICATED (coordinator, docs/inbox/FLEET-RULES.md): exactly ONE
convert-b was chartered — the stream whose transcript holds `bg8zh5iun`
(this record's author).  The paragraph that spoke in convert-b's voice
about `bsb65kfwu` was NOT convert-b; both disputed artifacts (that
paragraph and the `B2_merge_ifc_rst_devonly` run) are attributed to the
perm-matrix stream pending its own report.  Per the fleet rule minted from
this incident, cross-record additions must sit under a header naming the
writing stream.  The A2 / C4 sections and per-cell table updates above
were co-written by that same co-editor; every number in them was verified
by convert-b against the run manifests before being kept.  NO technical
conclusion depends on the attribution: both B2 runs are green and the
determinism comparison is symmetric.

## Suite

Per the BINDING `docs/inbox/SUITE-COORDINATION.md`: the full suite is
repo-global; the orchestrator designated the 23:23 run (pid 27375)
CANONICAL and barred new full-suite runs — a stream's "run the full suite
before finishing" is SATISFIED by adopting the canonical count published
in that file.  Stream-local FINAL run (convert-b, after all fixes, no
skip flags): `pytest tests/test_convert_combo.py` = **12 passed in
52.6 s** — INCLUDING both heavy end-to-ends (prompt+RVT into the
acceptance output; IFC merge into a copy of it), the schema-mismatch RED
guard, the type-scoping vocabulary, and the modify-family e2e.  (An
earlier co-editor line reported 10 passed + 2 env-gated skips — that was
the RVT_SKIP_LARGE=1 fast run, superseded by the unskipped final run.)
One suite-visible note for the orchestrator:
`test_plugin_sync.py::test_plugin_is_in_sync_with_source` reports 3
drifted convert files (see follow-up 2b — orchestrator sync re-run).

CANONICAL COUNT (adopted from SUITE-COORDINATION.md when published):
pending at this record's close — the first canonical run (27375) completed
but its output was unreachable, and the ORCHESTRATOR relaunched the single
canonical suite with owned output (per that file, ~00:55).  The number
publishes there; this record adopts it BY REFERENCE, per the binding
"'run the full suite before finishing' is SATISFIED by adopting the
canonical count" rule.  Stream-local evidence stands on its own:
tests/test_convert_combo.py 10 passed + 2 env-gated (whose end-to-end
paths have recorded proofs A1/B1 and re-run in ~3 min without the env).

BRANCH STATE: convert-b DONE — three combination routes built in NEW
modules (`src/rvt/convert/{add_to_project,merge_ifc,modify_family}.py` +
additive `__init__.py` shared with convert-a), all three PROVEN runnable
on BOTH our own and (dev-only, quarantine-stamped) sample targets:
A1 prompt+RVT into our acceptance output (VALID 0 err), A2 prompt+RVT into
the rme sample (32.7 MB output, VALID 0 err, census coherent 308 units,
877 s), B1 IFC merged into a copy of our acceptance output (28 created
ids, VALID 0 err, open-bug stamp), B2 IFC merged into the rst sample
(VALID 0 err; independently reproduced by a sibling — created ids
IDENTICAL, only minted GUIDs differ), C1/C2 prompt+RFA edits on our
generated families (family-mode VALID 0 err, re-read proven, PartAtom in
step), C4 convert-a's ops surface over this stream's engine (green).
Honest partials: foreign .rfa WRITES blocked on the ElemTable
GraveyardRec codec gap (C3, ticket filed); non-2026 targets refused with
`creation_status`'s reason (the release fleets own those bases);
wall-mount placement is free-standing (face-hosting = H1 follow-up).
Releases preserved on every output (verified per file); every output
delivered with stamps-after per the deliverable rule.  Frozen files
untouched (tools/frontdoor.py, plugin/skills, base.py, versions/).
Tests: tests/test_convert_combo.py **12 passed** (final unskipped run,
both heavy end-to-ends executed); full-suite count adopted from
SUITE-COORDINATION.md (canonical run, orchestrator-published; pending at
close).  Remaining oracle: viewer acceptance of A1/A2/B1/B2 + the edited
C1 .rfa (follow-up 2).
