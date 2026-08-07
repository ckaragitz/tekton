# The job runner — `tools/rvt_job.py` (the product FRONT DOOR)

Stream: `job-runner`. Module: `tools/rvt_job.py`. Tests: `tests/test_job.py`
(6). Proofs: `experiments/job/{create,create_hosted,from_ifc,edit}.rvt` +
`*.manifest.json` + `*.validation.json`. Confidence tags: **[V]** verified
by the run + validator, **[H]** needs Autodesk acceptance, **[D]** design
decision.

## 0 · What it is

The ONE deterministic pipeline the product promise runs through:

> a simple prompt, or uploaded project files + requirements, in → a valid
> Revit file out.

There is **no LLM inside the runner**. The LLM lives in the plugin skill,
which turns a prompt into a `spec.json` (or an `ops.json`, or hardens the
user's IFC) and then invokes `rvt_job.py`. The runner is what makes the
promise honest: every output is committed by the proven writer, then run
through **hard gates**, and the truth of what it is (product vs. proof) is
written into a **deliverable manifest** next to the file. It never claims
more than the gates proved.

```
rvt_job.py create   --spec job.json  [--base base.rvt] -o out.rvt   # (A)
rvt_job.py edit     in.rvt --ops ops.json           -o out.rvt   # (B)
rvt_job.py from-ifc design.ifc   [--base base.rvt] -o out.rvt   # (C)
```

Every mode writes:

| file | what |
|---|---|
| `out.rvt` | the generated / edited Revit file |
| `out.rvt.manifest.json` | the DELIVERABLE MANIFEST — inputs, elements created / edited, every gate's status + evidence, provenance status, warnings |
| `out.rvt.validation.json` | the full `rvt.validate` layered report (L1 structure / L2 consistency / L3 semantic) |
| `out.rvt.spec.json` | (from-ifc only) the spec derived from the IFC — the auditable intermediate |

## 1 · The three entry modes

### (A) CREATE — `create --spec job.json [--base base.rvt] -o out.rvt`

The building/room **spec** (metres, degrees — the same format
`tools/ifc_to_spec.py` emits and `tools/spec_to_rvt.py` consumes: levels,
walls, equipment, circuits, doors, rooms) is authored against a **base**
project (a firm seed via `--base`, else the research template's sample).

Pipeline:

1. **Seed / content audit** (`tools/seed_audit.audit`) — inventories the
   base and matches every level / wall type / door / equipment the job
   asks for. `SEED NOT READY` **blocks** (exit 2, gap list + plain-English
   fixes in the manifest, `--allow-not-ready` overrides); `SEED USABLE
   WITH GAPS` proceeds with the gaps recorded (`gates.seed_audit.gaps`).
2. **Build** — the viewer-certified `spec_to_rvt.build` recipe
   (`Document.add_wall` / `add_family_instance` / `add_circuit`, then
   `serialize`). If any equipment item asks to be wall-mounted (§3) the
   runner's hosting-extended builder mounts it through `rvt.hosting`
   instead (SketchPlane + face-hosted instance); everything else is the
   certified path.
3. **Commit** — `rvt.commit.commit_new_elements(base, out, records, plans,
   identity={document_guid: History[0]})` — see §5 for why the identity
   scrub is handed the History-head GUID.
4. **Gates** (§4) → manifest.

Flags: `--base` (default: `spec_to_rvt.TEMPLATES[--template].sample`, i.e.
`samples/rmebasicsampleproject.rvt`), `--auto-circuits` (one circuit per
transformer/switchboard off the first panelboard), `--offset-m X Y` (spec
origin → world, default `10 -25`), `--wall-type ID`, `--panel-host ID`
(free-path SketchPlane), `--plane-ref {dummy,geom}` (hosting face-plane
style), `--allow-not-ready`.

### (B) EDIT — `edit in.rvt --ops ops.json -o out.rvt`

`ops.json` is a list (or `{"ops": [...]}`) applied to an existing project.
Manipulate ops are planned by `rvt.manipulate` on ONE `Document` session
and committed in **ONE `commit_plans`** call; `add-*` ops then run as a
create stage (`rvt.mutate` + `commit_new_elements`) on that result.

| `op` | fields | engine |
|---|---|---|
| `delete` | `id`, `cascade` (bool) | `manipulate.delete_element` — `cascade:false` fails **loudly** with the dependents report in the manifest (exit 2, nothing written) |
| `rename` / `rename-panel` | `id`, `name` | `manipulate.rename_panel` (Panel Name BIP) |
| `set-mark` | `id`, `mark` | `manipulate.set_mark` |
| `set-level` | `id`, `elevation_ft` \| `elevation_m` | `manipulate.set_level_elevation` |
| `set-param` | `id`, `param_id`, `value` | `manipulate.set_param` (any built-in param id) |
| `move` | `id`, `to:[x,y,z]` \| `delta:[dx,dy,dz]`, `rotation_deg` | `manipulate.move_instance` |
| `retype` | `id`, `symbol`, `allow_family_change` | `manipulate.retype_instance` |
| `add-instance` | `name`, `symbol`, `level` (opt), `position_ft` \| `position_m`, `rotation_deg`, `host` (opt), `template_instance` (opt) | `mutate.add_family_instance` |
| `add-circuit` | `panel`, `load` (= `add-instance` names of THIS run), `number`, `description`, `rating`, `poles` | `mutate.add_circuit` — circuiting EXISTING elements is phase 2 (in-place connector edits) and is logged as SKIPPED |

Any op that cannot be planned raises before anything is written — a
partial edit is worse than none.

### (C) FROM-IFC — `from-ifc design.ifc [--base base.rvt] -o out.rvt`

The Claude-Design path (the user's Chicago-plenum flow):
`tools/ifc_to_spec.extract(ifc)` (levels ← storeys, walls ← `IfcWall`
axis/geometry or a synthesized room shell, equipment ← the electrical
classes with placement + psets) → `out.rvt.spec.json` → the (A) pipeline
unchanged. Best results on a **hardened** IFC (`skills/revit-bridge/
scripts/harden_ifc.py` recovers real insertion points), which is what the
proof uses. `--spec-out PATH` overrides where the derived spec lands.

## 2 · Common flags

| flag | effect |
|---|---|
| `--no-validate` | skip `rvt.validate` — a debugging run, never shippable |
| `--layers a,b` | validator layers subset (default all three) |
| `--strict-validate` | validator strict mode (one-way connector links, stale stamps, the block-counter defect become errors) |
| `--no-provenance` | skip the P0 ledger; the manifest then reports the output as **NOT-DELIVERABLE (unproven)** — skipping the ledger can never manufacture deliverability |
| `--require-deliverable` | exit 6 unless the base passes the genesis provenance check (for CI on a certified genesis base) |

## 3 · Wall-mounted equipment (the `rvt.hosting` hook)

An equipment item in the spec carrying **`"hostWall": "<spec wall id>"`**
(or `"mounting": "wall"` = mount on the nearest wall created in this run)
is placed by `rvt.hosting.host_instance_on_wall` instead of free-standing:
a `SketchPlane` on the wall face + a face-hosted (`m_workPlaneBased`,
`m_hostId = SketchPlane`) instance. The runner derives the mount
parameters from the spec geometry: `distance_along_ft` = the item's
position projected onto the wall's location line, `elevation_ft` = the
item's spec elevation above the wall base, `side` = the face facing the
item's own position (`hosting.side_facing_point`), `plane_ref` from
`--plane-ref` (`dummy` default = the regeneration-independent H3 fallback;
`geom` = a true `GeomOnPlaneRef` association, H1/H2). If the named wall
was not created in the run, or hosting raises, the runner logs a `WARN`
and falls back to free-standing — the job never silently drops equipment.
Proven: `experiments/job/create_hosted.rvt` (six panelboards mounted on
the north wall + three transformer circuits, all gates PASS) **[V]**.

## 4 · The gates and the manifest

Every gate lands in `manifest.gates.<name>` with a `status` and its
evidence; the roll-up is `manifest.status` / `hard_gates_passed` /
`deliverable`.

| gate | pass criterion | on failure |
|---|---|---|
| `seed_audit` (A/C) | verdict ≠ `SEED NOT READY` (`WARN` = usable with gaps) | exit 2, gap list + fixes in manifest |
| `structural` | `verify_written` / `verify_manipulated`: 0 CRC failures, 0 ECC mismatches, 0 walker errors, stamps ok, ElemTable count == header count, sentinels last, deleted ids gone, new/edited ids decode clean. (The known reader-tolerated block A/C counter defect is a recorded **warning** here — its severity is owned by the validator, §6.) | exit 3 |
| `validation` | `rvt.validate.validate_file` = **ZERO errors** (warnings allowed); full report → `out.rvt.validation.json` | exit 4 |
| `identity` | BasicFileInfo asserts **our** identity: `author` / `client_app_name` == `rvt-writer`, `username` empty, `last_save_path` = the bare output name (no directories), `central_model_path` empty; document GUID coherent with `History[0]` | exit 5 |
| `base_provenance` | P0 gate G1 (`rvt.provenance`): the output ledgered against its base carries NO Autodesk-derived expression | **status only** — `PROOF-ONLY, NOT-DELIVERABLE`; exit 6 only with `--require-deliverable` |

`manifest.status` ∈ `DELIVERABLE` \| `PROOF-ONLY, NOT-DELIVERABLE (hard
gates PASSED)` \| `FAILED (<gates>)`; `manifest.deliverable` is `true` only
when all hard gates pass **and** G1 passes.

**Honesty by construction [D]:** the runner cannot report a product it did
not prove. `--no-provenance` degrades to NOT-DELIVERABLE, an unavailable
optional module (seed audit / provenance) degrades that gate to
`SKIPPED`/`DEGRADED` and says so, and today's every base being an Autodesk
sample project means every current output is stamped
`PROOF-ONLY, NOT-DELIVERABLE` — which the plugin SOP must relay to the user
verbatim (docs/inbox/job-runner.md).

Exit codes: `0` all hard gates passed (status may be PROOF-ONLY), `1`
usage/unexpected, `2` planning/seed/spec, `3` structural, `4` validation,
`5` identity, `6` not deliverable under `--require-deliverable`.

## 5 · The identity–coherence resolution (found while building the door)

Building the front door surfaced a real conflict between two other
agents' modules **[V]**: the G2 identity scrub (`rvt.identity`) mints a
FRESH Unique Document GUID, but the writer's minimal commit reuses the
CURRENT save episode (no new `History` row), so the L2 validator invariant
*"BasicFileInfo Unique Document GUID == History entry[0] GUID"* breaks —
`rvt.validate` reports it as an **error**. Proof: the Autodesk-**accepted**
files `experiments/acceptance/V30_own_identity_keep_author.rvt` and
`V31_own_identity_own_author.rvt` both validate with `errors=1` (this exact
finding), contradicting the validator's stated calibration ("every accepted
file validates with ZERO errors"). Neither module is in this stream's
territory, so the runner resolves it **without touching either**: it hands
the identity scrub the base's `History[0]` GUID
(`commit_new_elements(..., identity={"document_guid": History[0]})`, or a
post-commit `scrub_identity(out, document_guid=History[0])` in edit mode,
since `commit_plans` never touches BasicFileInfo). Result: OUR authorship
strings + scrubbed path/username **and** GUID coherence, so both the
identity gate and the validator pass at once. This is principled, not a
patch — the document's identity episode legitimately IS the History head
the minimal commit is still on. The clean phase-2 upgrade is the proposed
hook in `docs/inbox/job-runner.md` §"proposed hooks": the identity scrub
should record a full save (`streams_edit.record_save`) minting a new
episode, after which a fresh GUID stays coherent.

## 6 · Structural-gate calibration note

`verify_manipulated` reports `isize_identity_mismatches` — the block-header
`ISIZE == hdr_len(seq)·A + C + adj(flags)` identity. Every
`commit_new_elements` output violates it on its three spliced blocks (the
`commit.py` off-by-4·A counter defect), yet all such files (V20–V29 + this
stream's proofs) are **accepted by Autodesk's reader**; the calibrated
validator therefore classifies it a WARNING (an error only under
`--strict-validate`). The runner's structural gate follows the same
calibration: it records the defect as a warning and lets the validator own
the severity, so a create-stage edit is not falsely failed **[D]**. (First
run of the add-instance edit tripped exactly this; the fix is deliberate.)

## 7 · The proofs (`experiments/job/`)

| file | mode | proves | hard gates | status |
|---|---|---|---|---|
| `create.rvt` | (A) `usecases/.../room-spec.json` | 3 walls + 6 panelboards + 3 transformers + 3 auto circuits (15 elements) on the MEP sample; proxies (hangers) SKIPPED with the seed gap recorded | structural PASS, validation 0 errors / 2 warnings, identity PASS | PROOF-ONLY (G1: sample base) |
| `create_hosted.rvt` | (A) hosted variant (`hostWall: W-north`) | the `rvt.hosting` hook: 6 SketchPlanes + 6 face-hosted panels on the created north wall + 3 circuits (21 elements) | all PASS | PROOF-ONLY |
| `from_ifc.rvt` | (C) `hardened.ifc` (Claude Design) | zero-hand-authoring path: 4 shell walls + 6 panels + 3 transformers from the customer's own IFC | all PASS | PROOF-ONLY |
| `edit.rvt` | (B) `experiments/job/ops.json` on `rmebasicsampleproject.rvt` | rename panel 581483 → `PP-1B-JOB` + Mark, move+rotate transformer 624416 (+5 ft X, verified), delete air terminal 430715 — ONE manipulate commit | all PASS (0 errors / 1 warning) | PROOF-ONLY |

Timing on this Mac: ~75 s per run (build/commit ~55 s, validation ~12 s,
provenance ~3 s). The rst-basic edit smoke in the tests is ~10 s.

## 8 · Reproduction

```
P=/Users/ck/dev/things/rev-revit/.venv/bin/python; cd /Users/ck/dev/things/rev-revit
$P tools/rvt_job.py create --spec usecases/chicago-plenum-electrical-room/room-spec.json \
    -o experiments/job/create.rvt --auto-circuits
$P tools/rvt_job.py create --spec experiments/job/create-hosted-spec.json \
    -o experiments/job/create_hosted.rvt --auto-circuits
$P tools/rvt_job.py from-ifc usecases/chicago-plenum-electrical-room/hardened.ifc \
    -o experiments/job/from_ifc.rvt
$P tools/rvt_job.py edit samples/rmebasicsampleproject.rvt \
    --ops experiments/job/ops.json -o experiments/job/edit.rvt
$P -m pytest tests/test_job.py -q            # 6 passed (~36 s)
```

## 9 · Unknowns / follow-ups

* **[H]** Autodesk-viewer acceptance of the four job proofs (the
  orchestrator certifies): they use only certified verbs (create =
  V23–V29 recipe, edit = the certified M-ops, identity = V30/V31), so
  acceptance is expected — the hosted variant additionally exercises the
  H2/H3 hosting recipe.
* The identity/validator conflict (§5) should be closed at the source: the
  identity scrub minting a real save episode (proposed hook), and the
  validator's calibration re-checked against V30/V31 — until then the
  runner's History-GUID handoff is the compatible resolution.
* A genesis base (P0 G1) needs its own certification path — G1 as written
  ledgers a candidate against the *sample it descends from*; a genesis
  base has no such ancestor, so "the base passes the genesis provenance
  check" needs the genesis stream's certificate wired in (today: no such
  base exists, status is always PROOF-ONLY).
* `add-circuit` in EDIT mode wires only elements created in the same ops
  run (circuiting existing gear = in-place connector edits, phase 2).
* Equipment kinds beyond `panelboard/switchboard/transformer/lightfixture`
  (e.g. `proxy` hangers) are skipped by the writer and surface as
  `NEEDS-FAMILY` seed gaps — the manifest never hides an omission.
