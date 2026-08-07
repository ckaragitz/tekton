# ifc-family — THE FIXTURE FAMILY FROM OUR IFC (workstream record, 2026-08-04)

Charter: build the pipeline **IFC-product -> OUR .rfa** for the flagship
luminaire — `inputs/ifc/chicago-plenum-downlight.ifc` (OUR OWN IFC4 of a
Chicago-plenum recessed 6 in downlight: one `IfcLightFixture` with a
`ChicagoPlenumSpecification` Pset and 29 tessellated meshes wearing 5
surface styles) — as (1) a product-FACTS record, (2) OUR generated
recessed-downlight family through the assay-clean family path, (3) that
family LOADED into a certified project base to prove it is instantiable,
and (4) the batch manifest for the viewer gate.

**Territory touched ONLY:** `src/rvt/ifc/__init__.py` (new package),
`src/rvt/ifc/product_facts.py` (new), `src/rvt/ifc/famfrom_ifc.py` (new),
`tests/test_ifc_family.py` (new, 19 pass — 18 fast + 1 slow load),
`experiments/families/ifc/**` (facts records, 2 `.rfa` + reports, 2 loaded
`.rvt` + load reports, `probes.json`, `ifc_family.json`), this record.  No
existing `src/rvt/*.py`, tool, test or sample was edited: `rvt.famgen.
{catalog, skeleton, geometry, factory, famdoc_adoc}` (validation / the
family document / form clusters / the face-hosted connector / the
assay-clean emitter), `rvt.famload` (the four-registry loader),
`rvt.validate`, `rvt.families` and `tools/probe_batch.py` (dry-run only) are
IMPORTED, never modified.  No browser / viewer use — the four upload files
+ `probes.json` are left for the orchestrator's queue.

## Result in one screen

**DONE is met.**  All four charter deliverables land clean, reproducible in
~140 s: `.venv/bin/python -m rvt.ifc.famfrom_ifc` (exit 0).

| # | deliverable | file | gates (all machine-checked) |
|--:|---|---|---|
| 1 | product-FACTS record (catalog schema) | `experiments/families/ifc/chicago_plenum_downlight.facts.json` (+ `.facts.full.json` raw dump) | `rvt.famgen.catalog.validate_line` == [] (schema-valid); every leaf flagged; nulls never `fact`; source `S1` = OUR IFC (VERIFIED, sha256 pinned) |
| 2 | OUR downlight `.rfa` (90 elements, 8 forms, 20 params, 1 connector) | `experiments/families/ifc/chicago_plenum_downlight.rfa` md5 `27105d5a…` | read-back verify OK (0 gzip-CRC / 0 ECC / walker clean); **family-mode validator VALID, 0 errors, 0 warnings**; provenance ledger PASS (all 11 checks: zero donor bytes / ids / names, our identity, our footer, schema constant only); 270/270 records round-trip byte-exact |
| 2b | envelope sibling (50 elements, 2 forms) | `…/chicago_plenum_downlight_min.rfa` md5 `14006435…` | same gates: VALID 0 err / 0 warn, provenance-clean |
| 3 | family LOADED into the certified rst base | `experiments/families/ifc/L_downlight_loaded.rvt` md5 `702ad437…` | `rvt.famload` ok: four registries COHERENT, **ours in all four**, host Family / symbol / 20 param twins ours, core id 127 bound; **project-mode validator VALID, 0 errors** (`tools/rvt_validate.py` exit 0) |
| 3b | (informational) loaded into the MEP sample | `…/L_downlight_loaded_rme.rvt` md5 `e533a7d4…` | loader ok, four registries coherent, core id 127, VALID 0 err |
| 4 | batch manifest | `experiments/families/ifc/probes.json` (+ `ifc_family.json` summary) | `tools/probe_batch.py check` = **ADMISSIBLE** (dry-run pasted below) |

## §1 The IFC and its facts (`rvt.ifc.product_facts`)

Read directly with `ifcopenshell` 0.8.5 (the `tools/ifc_to_spec.py`
precedent) — the file is OUR OWN authoring (`three-d-stage IFC writer`), so
provenance is **ours end to end**: every value taken from it is a `fact`
whose source is the file itself (`sources.S1`, verification `VERIFIED`,
sha256 `60596560594272e1210c922e48eeb0c0c032cb98e117fa7d7544ed1713d77858`
pinned, accessed 2026-08-04).

* IDENTITY [fact] — `IfcLightFixture` "Chicago-plenum recessed downlight - 6 in
  housing", tag `CP-6-LED`, POINTSOURCE, GlobalId `3ShKvoAgO_ioLP6_WZIZn8`,
  contained in storey "Level 1", placement **identity** (bboxes are the
  product-local frame = world here).
* PSET `ChicagoPlenumSpecification` [fact, TYPED] — Rating (`IfcLabel`)
  "Chicago plenum (CCEA), airtight, gasketed junction box"; Aperture "6 in
  (152 mm) round"; Housing; Trim; Mounting "Telescoping bar hangers, 16-24
  in joist spacing"; Lamp "Integrated LED module"; OverallHeightMeters
  `0.244` (`IfcReal` -> float).
* GEOMETRY [fact, MEASURED] — 29 `IfcTriangulatedFaceSet` meshes / 8,760
  faces; overall envelope 0.666 x 0.246 x 0.228 m = **2.185 x 0.807 x 0.748
  ft** (the bar hangers set the width); a bounding box PER MESH (each mesh
  is a named sub-part via its `IfcStyledItem`: `housing_can`,
  `trim_reflector`, `lens`, `plaster_frame`, `junction_box`, `driver_box`,
  `hanger_bar_front/back`, + 21 hardware / lip / flag meshes) in metres,
  feet AND inches (m->ft consistency is a test); `classify_part` maps each
  name to OUR functional role (can / trim / lens / frame / junction_box /
  driver_box / hanger / hardware).
* STYLES [fact] — 5 `IfcSurfaceStyle` colours: galvanized_steel (frame /
  boxes / hangers), gunmetal_steel (the can / gasket), zinc_hardware
  (screws / locknuts / conduit), white_enamel (the trim), frosted_lens.
* DERIVED downlight geometry (`downlight_geometry`) [fact = measured]: can
  Ø 7.32 in x 7.48 in tall from base z 0.24 in; trim OD 7.46 in; lens
  Ø 4.61 in at z 2.44 in; plaster frame 13.39 x 7.87 in at z 0.79 in;
  junction box 4.33 x 3.94 x 2.36 in centred x +4.13 in from the frame;
  driver box atop the can; bar hangers span 25.98 in, ±4.21 in from centre.
  STATED-vs-MEASURED honesty: the pset says overall height **0.244 m**;
  the tessellation measures **0.228 m** — BOTH are recorded (the family's
  `Overall Height` parameter carries the STATED 0.244 m; the report notes
  the measured 0.228 m).  The aperture "6 in (152 mm)" is a STATED nominal
  (parsed from the label — the label writes both 6 in and 152 mm); the can
  itself measures 7.32 in Ø.
* NOT SOURCED (and never invented) — the IFC carries **no electrical or
  photometric pset**: wattage, delivered lumens, colour temperature, input
  voltage are `null` (provenance `assumed` = the catalog's NOT-SOURCED
  convention: a null is never a fact).  They ride as unset (0) family
  parameters; voltage is a connector JOB parameter (120 V default, kind
  `given` = UNVERIFIED).  No photometric web (IES) exists — the family
  exposes an empty `Photometric Web File` REFERENCE parameter (a path/URL
  the user supplies; never an embedded `.ies`, per the facts-store rule).

The record is written in the `rvt.famgen.catalog` facts-store schema
(`docs/writer/facts-store.md` §2): `vendor: own-ifc`, `line:
chicago-plenum-downlight`, one variant `CP-6-LED` (`ratings` / `dims_in` /
`options` / `field_provenance` / `source`), plus `line_facts` (ifc_source,
geometry_representation, overall_bbox_ft, part_bboxes_ft, surface_colours,
housing_geometry_ft, aperture_nominal_in, overall_height_stated_ft,
photometry_reference, electrical_ratings).  `validate_record` = the
catalog validator + the store's provenance hygiene (nulls never `fact`,
VERIFIED needs `accessed`); the writer refuses an invalid record.
NOTE: the record lives in `experiments/families/ifc/` (my territory), NOT
in `src/rvt/famgen/facts/` (the catalog stream's directory) — the catalog
API does not load it (the schema is honoured, the store is not touched).

## §2 The family (`rvt.ifc.famfrom_ifc.make_downlight`)

**The archetype question the brief posed.**  `rvt.famgen.factory.
make_luminaire` is the luminaire ARCHETYPE and its exercised form is the
recessed **troffer** (a rectangular box housing —
`experiments/families/genesis2/troffer_2x4_v2.rfa`).  The factory also
carries a stub `downlight` branch, but it is welded to the Lithonia LDN6
catalog record (all-`assumed`, housing dims `null`) and — more importantly —
it hosts its connector on a CYLINDER via the BOX face template
(`add_connector` -> `box_face("top")` = the rectangular topology's tag map),
an untested combination that has never emitted a file.  Per the charter
("add a make_downlight recessed-can variant IN YOUR MODULE rather than
editing the factory"), `make_downlight` composes the recessed-can housing
from `rvt.famgen.geometry` form clusters, driven by the IFC facts, editing
NO factory line — and side-steps the cylinder-connector question entirely.

**Coordinate frame (a decision).**  The IFC product's own origin is the
plaster-frame centre; the can is offset −0.055 m from it (the J-box sits on
the +x side within the frame).  For a downlight family the insertion point
a designer places on the ceiling grid is the LIGHT CENTRE, so the family
origin = the **can / aperture axis**: every part keeps the product's REAL
relative layout, translated by (+0.1804, 0) ft so the can axis is (0, 0);
z 0 = the trim / ceiling plane, all housing above it (work-plane-based,
category OST_LightingFixtures, part type 0).  The translation is recorded.

**Form clusters** (`detail="standard"`, 8 forms / 50 form elements):

| form | primitive | sized from | role |
|---|---|---|---|
| housing can | `G.cylinder` (r 0.305, h 0.623, base z 0.0197 ft) | `housing_can` bbox | sealed steel can |
| trim ring | `G.cylinder` (r 0.311, h = frame z, base 0) | `trim_reflector` OD | white baffle trim flange at the ceiling |
| lens | `G.cylinder` (r 0.192, t 1/8 in at the lens z) | `lens` bbox | frosted lens disc |
| frame | `G.plate` (1.115 x 0.656 ft, at z 0.066) | `plaster_frame` bbox | plaster / mounting frame plate |
| junction box | `G.box` (0.361 x 0.328 x 0.197 ft) | `junction_box` bbox | gasketed integral J-box — **connector host** |
| driver box | `G.box` (0.295 x 0.180 x 0.105 ft, atop the can) | `driver_box` bbox | LED driver enclosure |
| 2 bar hangers | `G.box` (2.165 x 0.039 x 0.085 ft, y ±0.351) | `hanger_bar_front/back` | telescoping bar hangers |

The 21 sub-inch hardware meshes (frame lips, nail flags, knockouts, cover
screws, locknuts, conduit connector, gasket, cover) are RECORDED in the
facts (bbox / role / colour) and NOT modelled (below a family's level of
detail — listed by name in the report).  Honest gap **H5**: the trim is a
solid DISC of the trim OD — the annular aperture void through the flange
needs a void/cut form the geometry stream does not have (phase 2); the
6 in aperture rides as the `Aperture Diameter` parameter, not as a cut.
`detail="envelope"` = can + trim ring only (2 forms) — the attribution
sibling `chicago_plenum_downlight_min.rfa` (with a datum-hosted connector,
the S0e pattern, since the envelope has no box face).

**Parameters BY NAME** (20 `ParamElemFamily`, one type row `CP-6-LED`):
the CCEA specification contract — `CCEA Rating` = "Chicago plenum (CCEA),
airtight, gasketed junction box", `Aperture` = "6 in (152 mm) round",
`Housing`, `Trim`, `Mounting`, `Lamp` (text, from the pset);  the dimension
set — `Aperture Diameter` 0.5 ft (STATED), `Housing Diameter` / `Housing
Height` (measured can), `Overall Height` 0.8005 ft (STATED 0.244 m), `Frame
Length` / `Frame Width`, `Trim Diameter`, `Lens Diameter`, `Bar Hanger
Span`;  electrical / photometric — `Wattage` 0 (NOT SOURCED), `Voltage`
120 V (job default), `Lumens` 0, `Color Temperature` 0, `Photometric Web
File` = "" (an unset REFERENCE — never an embedded IES).  Identity: `Model`
= "CP-6-LED", `Description` = the IFC description; **`Manufacturer` is
deliberately NOT written** — the design is ours, the IFC names no
manufacturer, and an identity value we cannot source is not invented.
`FactSheet.unverified()` surfaces `voltage_v / wattage_w / lumens_lm /
cct_k / photometric_web / manufacturer` as the UNVERIFIED set.

**The connector** — one single-phase LIGHTING connector on the junction
box's **top face**, via the factory's proven face-referenced mechanism (the
box template): `m_geomRef.m_elemId` = the J-box `ExtrusionElem` (1066),
`m_geomTag` 1 (the box's top cap), edge-loop tags [3, 6, 10, 14]; voltage
bound to `Voltage`, apparent load = the wattage (0 = not sourced) bound to
`Wattage`, power factor 0.95, our `Lighting` load classification.  That is
where the branch-circuit conductors physically enter (the knockouts /
conduit connector sit on the J-box) — semantically truer than the
factory's housing-top convention, and it uses ONLY the certified box-face
mechanism.

**Emission** — `DownlightProduct.write_rfa` -> `famdoc_adoc.
emit_family_rfa_v2` (THE ASSAY-CLEAN PATH the charter names): OUR family
ADocument (constructed, 1,342,699 B, decodes clean, 0 dangling ids,
registries repopulated over our elements — DatumTracking 3, connector /
load-classification / units slots; the Forge unit-schema corpus CARRIED
in `candidate` mode per the G4b policy), OUR partition footer + the
universal signature token + the decoded 10-byte end record, our identity
(`rvt.identity`), PartAtom ours; the ONLY carried stream is the
sha256-checked per-release schema constant `Formats/Latest`.  Then
`famdoc_adoc.validate_family_file` (the certified family gate = `rvt.
validate` + the two family-shape adjustments) and `provenance_scan_v2`.
Result: **family-mode VALID / 0 errors**; provenance **PASS** (every check
true: adocument decodes clean, zero dangling refs, zero donor-id byte
hits, zero donor name strings, owner-family ours, identity ours, footer
not donor, no donor end parity, end record = the constant, signature
present, Formats/Latest = the format constant).  The raw project-mode
arbiter shows 3 errors = the known family-shape calibration gap the
authentic Autodesk donor `.rfa` also shows (worse) — the certified family
gate is family mode.  SEMANTIC READ-BACK (a test): the file's family
document decodes to 8 `ExtrusionElem`, 26 `CurveElem` (5 boxes x 4 lines +
3 cylinders x 2 arcs), 8 `VarSketch`, the 20 captions, the `CP-6-LED` type
row and 1 connector — the content survives the container.

## §3 The LOAD (`load_into_project` -> `rvt.famload.load_family_document`)

The charter's step 3.  Host choice (a decision, stated): the certified
project base = **`samples/rstbasicsampleproject.rvt`** — an Autodesk sample
source (a certified BASE per the `probe_batch` ledger's `is_sample_source`)
AND the EXACT host on which the four-registry loader is **viewer-PROVEN**
(`experiments/genesis/loader/L1a_rstbasic_loaded_levelhead.rvt`, ledger
`certified`).  Loading into rst therefore changes ONE variable vs the
certified L1a — the family document (a MODEL lighting fixture with 8
solids + a face-hosted connector instead of the level-head ANNOTATION
family) — the textbook one-variable probe.  (K4 / Y9 / ZA_deep are also
certified project bases; loading there would move TWO variables at once
— base + content — so they are not the primary host.  A K4-hosted variant
is a one-line rerun once the rst-hosted file certifies.)

The load is the `famdoc_adoc._load_v2_panel` precedent (a MODEL equipment
family into rst by `famload`, VALID) with our doc.  Mechanics observed:
family document ids 1,472,525..1,472,614 (above the rst watermark
1,472,524 — the L1a id-space pattern); host Family 1,472,615, one
FamilySymbol, 20 `ParamElemFamily` twins, the surrogates; the family
became an embedded save unit + a `ContentDocuments` entry + a
`ContentTable` record + a `FamilyMgr` entry — **four registries
COHERENT, our GUID in all four** (`verify_loaded_project`); `rvt.validate`
project mode **VALID / 0 errors** (the 1 warning is the sample's OWN
known ES-blob decoder gap — RebarShape / DataStorage — present in the
untouched rst, not ours).

**Core-id finding (small, but real).**  With a doc-BUILDER the loader
cannot know the family's category before building it, so its host survey
gets no categories and binds NO core id ("no host GStyleElem for
category −2001120: core-id binding omitted") — the same thing happens to
the panel precedent.  Declaring the category through the public
`FamilyLoad.core_categories` (which `load_into_project` now does, default
OST_LightingFixtures) makes the survey find the host's built-in
Lighting-Fixtures **projection GStyle row** and bind it as the family's
core id — element **127** on BOTH the rst AND the rme samples (verified:
`m_categoryId` −2001120, `m_gstyleType` 1 in each; Autodesk's shipped
category catalog is laid out identically across the samples).  The
certified L1a bound ITS category's row (23795) the same way, so with the
declared category our load reproduces L1a's pattern EXACTLY — no `famload`
edit needed.  (Recorded as an observation for the loader stream: an
undeclared-builder load silently binds nothing.)

**The rme-hosted variant** (`L_downlight_loaded_rme.rvt`, informational):
the same loader + family on the MEP sample (the electrical project that
already carries luminaire families).  Loader ok, four registries coherent,
VALID 0 errors.  It is a HOST probe (the four-registry loader is not
viewer-proven on rme), read only after the rst file.

## §4 probes.json + the gate reading

`docs/coverage/viewer-certified.json` has **ZERO `.rfa` entries** — no
family file has EVER been through the oracle (the famdoc_adoc FG1..FG5
uploads never ran).  So the .rfa artefacts cannot be probes on a
certified family base; they are staged as **candidate-bases** ("certify me
/ fail me"), ARCHETYPE FIRST, and the loaded `.rvt` is a **probe** on the
certified rst source:

| id | file | kind | declared base / lineage | reads |
|---|---|---|---|---|
| **IFA0** | `experiments/families/genesis2/troffer_2x4_v2.rfa` | candidate-base | (the luminaire ARCHETYPE through the clean emitter; ledger `unknown`) | FIRST family file: does the oracle read a family at all / does the clean-path lighting-fixture layer load? IFA1's verdict is moot until this is judged |
| **IFA1** | `experiments/families/ifc/chicago_plenum_downlight.rfa` | candidate-base | derived_from IFA0 | ONE change vs the archetype: the multi-form recessed-can composition + the CCEA / dimension / photometric-web parameter set |
| **IFA1m** | `experiments/families/ifc/chicago_plenum_downlight_min.rfa` | candidate-base | derived_from IFA0 | envelope sibling (2 forms): attributes an IFA1 FAIL to composition vs parameters |
| **IFA2** | `experiments/families/ifc/L_downlight_loaded.rvt` | **probe** | `samples/rstbasicsampleproject.rvt` (sample = certified base) + passing sibling L1a | **THE DONE PROBE**: our IFC-derived family is INSTANTIABLE as a project's embedded document; a FAIL convicts our family document's content (vs L1a's head) |
| IFA3 | `experiments/families/ifc/L_downlight_loaded_rme.rvt` | probe | `samples/rmebasicsampleproject.rvt` (sample) | the host is the variable (loader not proven on rme); read after IFA2 |

Dry-run of the gate (pasted, `tools/probe_batch.py check ... --candidate-base
...`): **ADMISSIBLE — `stage` will add the certified control and write
the manifest.**  Recommended staging (control matched to the probe's
mechanism, not the ledger's newest file):

```
.venv/bin/python tools/probe_batch.py stage \
    experiments/families/ifc/L_downlight_loaded.rvt \
    experiments/families/ifc/L_downlight_loaded_rme.rvt \
    --candidate-base experiments/families/genesis2/troffer_2x4_v2.rfa \
    --candidate-base experiments/families/ifc/chicago_plenum_downlight.rfa \
    --candidate-base experiments/families/ifc/chicago_plenum_downlight_min.rfa \
    --control-from experiments/genesis/loader/L1a_rstbasic_loaded_levelhead.rvt
```

Reading order: CONTROL first (control FAIL => whole round VOID); IFA2 (the
load proof, the DONE probe); IFA0 (does a family reach the oracle at
all?); then IFA1 / IFA1m; IFA3 last.  Hypotheses carried on the family
artefacts (also in `probes.json`): H1 the embedded ADocument's all-null
239-slot AppInfoManager (famload's standing L3 question); H2 the loaded
FamilySymbol rep is a SerializedDummy — Revit regenerates the symbol
graphics from our 8 solids; H3 the connector face-hosting + our load
classification; H4 no ImposterLight light source (photometrics as
parameters); H5 the disc trim (no aperture void).

## §5 What is honestly NOT done / open

* **Viewer verdicts pending** — nothing here has been uploaded (by
  design; the orchestrator uploads).  Every "VALID" above is the
  machine gate, not the oracle.  The whole family layer (any `.rfa`) is
  unjudged.
* **No aperture VOID** in the trim (H5) — needs a void/cut form the
  geometry stream lacks; the aperture is a parameter, not geometry.
* **No light source object** (ImposterLight / photometric) — the skeleton
  exposes no constructor; photometrics are parameters, the web a REFERENCE.
* **No materials** — the 5 IFC colours are carried in the record only
  (the S0 discipline: our documents author no MaterialElem / object-style
  copies).  Faces render in the category's default appearance.
* **Electrical ratings unsourced** — the flagship IFC has no
  electrical/photometric pset; a future exporter revision should emit
  `Pset_LightFixtureTypeCommon` (voltage / wattage / lumens / CCT) so the
  connector and photometrics come from the IFC instead of a job default.
* **Manufacturer identity** intentionally blank (own design, no source).
* **The K4/Y9/ZA_deep-hosted load** is not emitted (rst = the proven
  loader host = the one-variable probe); a genesis-base-hosted rung is a
  rerun of `load_into_project(host=...)` once IFA2 certifies.
* **`rvt.objlint` was NOT run on the family** — its mined invariant corpus
  is PROJECT-document specimens; the family-form classes (`ConnectorElem`,
  `ExtrusionElem`, `VarSketch`, `CurveElem`, `ParamElemFamily`, `Family`,
  `RefPlane`) have no mined invariants (they exist only in family
  documents) and the shared skeleton classes carry family-flavour values
  (`m_designOptionId` −4) that project invariants would mis-flag.  The
  family assay is the family-mode validator + provenance ledger +
  read-back + the geometry stream's topology reproduction — a
  family-specimen invariant corpus is a possible future assay.

## §6 Needed changes / observations OUTSIDE this territory (exact, none made)

0. **PLUGIN SYNC (must run — not my territory):** the shipped plugin
   bundles copies of `src/` (`tests/test_plugin_sync.py` guards it; it was
   ALREADY failing at baseline for other streams' new modules).  My three
   new files add to the drift the guard now reports:
   `lib/src/rvt/ifc/{__init__.py, product_facts.py, famfrom_ifc.py}`
   (alongside the sibling streams' `rvt/ifc/intent.py` and
   `rvt/genesis/residue_a2.py` / `residue_b2.py`).  The fix is exactly:
   `.venv/bin/python tools/sync_plugin.py` (re-validates the manifest,
   rebuilds `rev-revit.zip`) — `tools/` and `plugin/` are outside my
   territory, so it is left for the orchestrator / the plugin stream.
   Until it runs, `test_plugin_is_in_sync_with_source` stays red for
   EVERY stream (it is red at baseline; not caused by this stream alone).
0b. **Package coexistence:** a sibling workstream is active in the SAME
   `src/rvt/ifc/` package (`intent.py`, the project-side placement /
   mapping resolver) and other streams are writing `rvt/genesis/
   residue_a2.py` / `residue_b2.py` in parallel.  The package
   `__init__.py` (which this stream created, being first) is kept
   IMPORT-FREE and non-exclusive — it now lists all three modules and
   notes the sibling convention (the same discipline `rvt/famgen/
   __init__.py` uses); neither `rvt.ifc` module imports the other, so
   there is no coupling to break.  No sibling file was edited.
1. **famload builder loads bind no core id unless the category is
   declared** (§3).  Callers passing a bare builder to
   `load_family_document` get "core-id binding omitted" on EVERY host.
   Suggested doc/API note for the loader stream: recommend
   `FamilyLoad(core_categories=[doc-category])`, or have `_resolve_docs`
   re-survey the category GStyles after the docs are built.  (The panel
   precedent `L_v2_panel_loaded.rvt` bound no core id for this reason.)
2. **`factory.make_luminaire`'s downlight branch hosts a connector on a
   CYLINDER through the BOX face template** (`add_connector` /
   `box_face`) — a cylindrical solid's cap / rail tags differ from the
   rectangular template (`_circle_loop_tags`), so that connector's
   `m_geomTag` / edge-loop tags would be wrong for its host.  Never
   emitted, so never caught.  If the factory keeps a cylinder-hosted
   connector it needs a `cylinder_face()` tag map (start cap tag 1 /
   end cap tag 0 per `extrusion_gstep_circles`).  This stream avoided it
   by hosting on the J-box (a box).
3. **The IFC exporter** (`ifc-export.js` in the Design project) states no
   electrical / photometric pset on light fixtures and no manufacturer —
   the KNOWLEDGE.md "fix the exporter at the source" item now has a
   concrete field list: `Pset_LightFixtureTypeCommon` + a manufacturer /
   model reference so downstream families carry sourced ratings.

## §7 Reproduce

```
.venv/bin/python -m rvt.ifc.product_facts                # step 1: facts record (schema-valid)
.venv/bin/python -m rvt.ifc.famfrom_ifc                  # steps 1-4 end to end (~140 s), exit 0
.venv/bin/python -m rvt.ifc.famfrom_ifc --no-load        # facts + .rfa only (~15 s)
.venv/bin/python tools/rvt_validate.py experiments/families/ifc/L_downlight_loaded.rvt   # 0 errors
.venv/bin/python -m pytest tests/test_ifc_family.py -q   # 19 pass (1 slow ~24 s; RVT_SKIP_LARGE=1 skips it)
.venv/bin/python tools/probe_batch.py check experiments/families/ifc/L_downlight_loaded.rvt \
    experiments/families/ifc/L_downlight_loaded_rme.rvt \
    --candidate-base experiments/families/genesis2/troffer_2x4_v2.rfa \
    --candidate-base experiments/families/ifc/chicago_plenum_downlight.rfa \
    --candidate-base experiments/families/ifc/chicago_plenum_downlight_min.rfa   # ADMISSIBLE
```

Full suite this session (`.venv/bin/python -m pytest tests -q`, 17 min):
BEFORE my changes = **1,082 passed / 3 failed**; AFTER = **1,132 passed /
3 failed** — the SAME 3 pre-existing failures and ZERO new ones
(`test_plugin_sync.py::test_plugin_is_in_sync_with_source` — the plugin
bundle is out of sync with source, a standing item outside this territory,
see §6.0; and two `test_provenance.py::test_G0_*` checks).  All 19 of this
stream's tests pass (18 fast + the slow rst-load proof).  The extra +31
passes beyond baseline+19 are the parallel sibling streams' new tests
(`test_residue_a2.py` / `test_residue_b2.py`), collected in the same run.

## BRANCH STATE

* **status**: DONE — READY FOR THE VIEWER QUEUE (nothing uploaded; the
  gate dry-run is ADMISSIBLE).  Stopped at READY per the charter.
* **files (repo-relative, md5 of the four upload candidates)**:
  * `experiments/families/ifc/chicago_plenum_downlight.rfa`      `27105d5a6bf29442f4440cc0fbee92e3`  (candidate-base IFA1)
  * `experiments/families/ifc/chicago_plenum_downlight_min.rfa`  `140064359ecd39fdea3f1adfc41e44e3`  (candidate-base IFA1m)
  * `experiments/families/ifc/L_downlight_loaded.rvt`             `702ad437eb406475823828d838a0faf7`  (**probe IFA2 = DONE**, base `samples/rstbasicsampleproject.rvt`)
  * `experiments/families/ifc/L_downlight_loaded_rme.rvt`         `e533a7d4ba858747b04822db08e5c807`  (probe IFA3, base `samples/rmebasicsampleproject.rvt`)
  * archetype to certify FIRST (not mine, unmodified): `experiments/families/genesis2/troffer_2x4_v2.rfa` (IFA0)
  * + `experiments/families/ifc/{chicago_plenum_downlight.facts.json, chicago_plenum_downlight.facts.full.json, chicago_plenum_downlight.json, chicago_plenum_downlight_min.json, L_downlight_loaded_load.json, L_downlight_loaded_rme_load.json, probes.json, ifc_family.json}`
  * code: `src/rvt/ifc/{__init__.py, product_facts.py, famfrom_ifc.py}`, `tests/test_ifc_family.py`
  * (each `.rfa`/`.rvt` rebuild mints fresh GUIDs => the md5s above are the
    state committed at record time; re-hash after any rebuild)
* **gates passed (all)**: facts schema-valid; both `.rfa` family-mode
  VALID / 0 errors + provenance-clean + read-back verify; both loaded
  `.rvt` project-mode VALID / 0 errors (`tools/rvt_validate.py` exit 0) +
  four registries coherent + ours in all four; probe_batch dry-run
  ADMISSIBLE; 19/19 stream tests pass.
* **next action (orchestrator)**: stage the batch with the `stage` command
  in §4 (control = a copy of the certified L1a), upload in the reading
  order CTRL → IFA2 → IFA0 → IFA1 → IFA1m → IFA3, and read the round with
  `read_batch_verdicts()`.  IFA0/IFA1/IFA1m PASS => the first CERTIFIED
  family files (add to the ledger; IFA1 then re-reads as a probe on IFA0).
  IFA2 PASS => the IFC → facts → family → loaded-project bridge is
  reader-proven end to end.
* **if IFA2 FAILs (with the control passing)**: our family DOCUMENT's
  content is the delta vs L1a — bisect with the acceptance hypotheses
  (H2 symbol regeneration for a solid-bearing family, H3 the connector,
  H1 the embedded AppInfoManager), the IFA1m envelope, and a doc-only
  variant (`detail="envelope"` load).  If IFA0 FAILs: the lighting-fixture
  family layer itself is the finding (bisect against the panel / xfmr v2
  siblings); IFA1 is moot until it is fixed.
