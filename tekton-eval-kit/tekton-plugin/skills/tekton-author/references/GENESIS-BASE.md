# GENESIS-BASE — the certified project base tekton authors ON

Every `.rvt` tekton produces is grown ON A BASE document. The product
rule (research repo `docs/inbox/genesis-audit.md`, ORCHESTRATOR VERDICTS
#24, 2026-08-04) is that the default base is **OUR composed genesis
project — never an Autodesk sample project.** This file says exactly what
that base is, what its certification proves, what it does NOT prove, and
what the `PROOF-ONLY` stamp in a job manifest means.

## 1. The asset

| | |
|---|---|
| File | `assets/genesis/G_ABPD.rvt` (bundled with this plugin; 581,632 bytes) |
| sha256 | `84173b8960b8cbba1b096a42ad4a97ed24deba9476ccb05eb8853d4c6d06df50` |
| md5 | `1f1ff65bd68415a05228d6b6ac2bf271` |
| Composer record | `assets/genesis/G_ABPD.compose.json` (the composer's own manifest: base, phases, per-invariant evidence) |
| Composed by | `scripts/genesis_compose.py` — one certified base + several IN-PLACE rung sets + a lawful deletion set → one candidate, with every campaign invariant asserted and a manifest of exactly what was composed |
| Revit release | 2026 (the per-release class schema; a file targets the same release as its base) |

**What is in it — all our constructors' output:** the project settings,
the style catalog (1,407-row catalog + palette), the datum (levels /
phases / grids), the view constellations, sub-categories, annotation
types, fonts, patterns, appearance assets, parameter definitions, MEP
categories, pens, filters, machinery and content layers — 2,840 landed
slots plus 240 lawful maxgc deletions, composed with NO Autodesk-authored
base content supplied. It inventories (`skills/tekton-inspect`) as 9 GEN
datum levels (`L1 - Ground Floor` id 311 at 0, `L2 - Second Floor` id
245423 at 12 ft), one wall type (`GEN Wall - Interior Partition 121mm`, id
600634, none placed), 0 loaded family symbols, two phases. It is a
**family-free project base**: equipment lands on it only after tekton
LOADS its own generated families (the front door's L stage).

## 2. What its certification proves

Ledger entry (`docs/coverage/viewer-certified.json` in the research repo,
the ONLY thing that counts — a claim written in prose does not):

> `experiments/genesis/subst_k4/compose/G_ABPD.rvt` — ***THE COMPOSED
> GENESIS PROJECT BASE LOADS***: G_ABP + the 240-element lawful maxgc
> deletion set; validator VALID 0 errors, EDIT-FREE, four-registry
> coherent; the Autodesk viewer opens it as a browsable model (3D view +
> sheet 'GEN-101 - GEN OVERALL PLAN', not empty, not corrupt).

Verdict #24: batch 23 (control `CTRL_ZCdeep_b23` PASS, `G_ABP` PASS,
`G_ABPD` PASS) — confirmed NOT the empty-design short-circuit: the viewer
OPENS it as a browsable model with our sheet vocabulary. **The user's
day-one target is met: no Autodesk base FILE is required.** Re-verify
locally any time (Autodesk-free arbiter):

```bash
python scripts/rvt_validate.py assets/genesis/G_ABPD.rvt   # -> VALID (no errors); ~0.3 s
```

## 3. What it does NOT prove — say these out loud

1. **PROOF-ONLY, NOT-DELIVERABLE (the stamp).** The job runner's
   provenance gate (`rvt.provenance` gate G1, in the manifest as
   `gates.base_provenance`) ledgers every output against the base it
   descends from. The genesis LINEAGE descends from a sample project
   reduced and substituted in place; verdict #24 discloses the residue
   honestly — ~260 remaining Autodesk-authored elements + 4 named
   stragglers (a link symbol, a DataStorage blob, one topology, a link
   instance) + the two shipped PRODUCT corpora present in EVERY Revit file
   (the `Formats/Latest` class schema and the ESSchemaStorage unit schemas —
   counsel question C4, not element authorship). Until gate G1 passes, EVERY
   output — however clean — is stamped **PROOF-ONLY, NOT-DELIVERABLE**: an
   internal proof, never a third-party deliverable. The manifest says so
   and the skill repeats it to the user. Deliverability is decided by the
   provenance gate and counsel, never assumed.
2. **LOAD is not RENDER.** "The viewer opens it" (LOAD) is the first gate.
   Whether an ADDED element DRAWS is a separate second gate: baked geometry
   lives in each element's seq-103 `GElement` B-rep record. Our loaded
   family symbols and instances carry real solids (the instance layer
   renders); created WALLS historically carried a `SerializedDummy` rep
   (nothing to draw) — `rvt.render.wallgeom` authors the wall solid and
   is being certified. Use `skills/tekton-inspect` (`render_inspect.py`)
   to see per element `kind = brep | instance-ref | dummy` before promising
   a picture.
3. **THE OPEN BUG — walls + loaded families TOGETHER.** Verdict #24
   retracted #22's "one defective family": the failing delta is *created
   walls AND loaded family documents in the same file* (walls alone
   PASS — `electrical_room_2500a_walls_only.rvt` certified; families
   alone PASS — `stage_L8_lp4.rvt` certified). The mechanism is under
   bisection. The front door (`rvt.frontdoor.intent.combination_check`)
   therefore never silently ships that combination: `--strict` emits
   TWO coordinated files (`shell` = walls only; `equipment` = loaded
   families + their instances), each a viewer-certified SHAPE; the default
   emits ONE combined file whose manifest is STAMPED `PROOF-ONLY:
   walls+families combination unverified`. Report which mode ran.
4. **Placement scaffolding needs a SPECIMEN ANCESTOR.** The family-free
   base carries no placed wall / instance to clone, and `rvt.mutate`
   creates by cloning a real specimen of the target class. The front door
   resolves a *specimen ancestor* (`R5`, the same certified lineage, ids
   continuous, wall type 600634 + level 311 in both) as a CLONE TEMPLATE
   ONLY — never emitted. **`R5.rvt` is a research-repo file
   (`experiments/genesis/R5.rvt`) and is NOT bundled in this plugin
   build**; from the plugin alone, wall/instance PLACEMENT needs
   `--specimens <path-to-a-lineage-file>`. Family generation, family LOAD,
   read, validate, edit and schedules are all self-contained. (Template-
   free wall / instance constructors are the milestone that removes this.)

## 4. How the front door finds it (pin + resolution order)

`rvt.frontdoor.base` pins the base by sha256 (the pin file shipped in
the engine at `lib/src/rvt/frontdoor/assets/genesis_base.json`) and
resolves, in order:

1. `--base <path>` (the user's authority; an Autodesk SAMPLE project is
   REFUSED; if the file's sha256 equals the pin it is asserted as the
   certified genesis base, otherwise accepted-but-not-certified).
2. `$RVT_GENESIS_BASE` (same pin check).
3. The pinned research-repo path, then a plugin-bundled copy
   (`<plugin-root>/lib/genesis/G_ABPD.rvt`).

Because this plugin ships the base at `assets/genesis/G_ABPD.rvt`, the
skill points the front door at it explicitly — either export
`RVT_GENESIS_BASE="<plugin-root>/assets/genesis/G_ABPD.rvt"` once, or pass
`--base assets/genesis/G_ABPD.rvt`. The bytes are the pinned bytes, so both
routes resolve as `certified_genesis_base: true`. A hash MISMATCH is a hard
refusal ("re-pin after re-certification"), never a silent substitution —
if you ever see it, the bundled asset drifted from source; run
`python tools/sync_plugin.py` in the research repo.

## 5. Bring your own base (a firm's certified template)

A firm may author on ITS OWN base: `--base their-template.rvt` (or
`$RVT_GENESIS_BASE`). It is accepted on the user's authority, checked by
`is_autodesk_sample` (a sample is refused outright), provenance-ledgered,
and audited by `skills/tekton-inspect`'s seed audit for the content the
job needs. Its deliverability is again the provenance gate's decision,
recorded in the manifest — not this skill's promise.
