# inbox — family-skeleton (the family-document skeleton, from scratch)

Stream: THE FAMILY-DOCUMENT SKELETON (2026-08-03). Charter: from-scratch
constructors for what every Revit FAMILY document must contain, in the
field-by-field-from-parameters style of `src/rvt/genesis/skeleton.py`, plus
the two delivery forms (standalone `.rfa` / embedded save unit); proof by
byte-exact reconstruction of specimen skeleton elements and a minimal
skeleton-only `.rfa` (S0) that validates with 0 errors; field map in
`docs/writer/family-skeleton.md`.

Territory touched ONLY: `src/rvt/famgen/__init__.py` (near-bare stub, per
the shared-directory caveat), `src/rvt/famgen/skeleton.py` (new),
`tests/test_famgen_skeleton.py` (new, 14 pass),
`experiments/families/genesis/S0_empty_family.rfa` + `S0_electrical_family
.rfa` (+ their `*_validate.json` reports), `docs/writer/family-skeleton.md`
(new), this file. NO existing `src/rvt/*.py` / `src/rvt/genesis/*` / existing
test edited (the building blocks of `rvt.genesis.skeleton` /
`rvt.genesis.types` and the `rvt.families` reconnaissance API are IMPORTED
only). No browser used; the two `.rfa` outputs are listed for the
orchestrator's viewer / Revit gate.

## Result in one screen

* **The family skeleton is constructible from scratch and is
  byte-exact-proven.** 45 specimen records reconstruct byte-for-byte from
  plain parameter values (adler32 stamps included): the Reference Level, the
  level type, five reference planes (both origin planes among them), three
  `ParamElemFamily` parameters, three electrical connectors (panelboard
  3-pole 208 V; a param-driven 120 V lighting-fixture connector; a
  receptacle) and — the big one — the `.rfa`'s **26,535-byte self-`Family`**
  (4-type `FamilyTypeTable`, parameter set, ordering cell, 1,881-entry
  element index, dimension-expression tables). Table + tags:
  `docs/writer/family-skeleton.md` §0.
* **`FamilyDoc` builder API delivered** (`rvt.famgen.skeleton`):
  `new_family_document(category, name, *, host, origin)` →
  `.add_reference_plane(...)`, `.add_type(name, params)`,
  `.add_family_parameter(name, spec, group)`,
  `.add_electrical_connector(voltage, poles, load_class, apparent_load_va,
  power_factor, bind_voltage_param, bind_load_param)`, `.finalize()`,
  `.to_rfa(path)`, `.to_embedded_unit()`. Constructors:
  `new_self_family`, `new_family_level`, `new_family_level_type`,
  `new_reference_plane`, `new_center_reference_planes`,
  `new_family_parameter`, `family_param_value` / `family_type_table` /
  `family_params_order_cell`, `new_electrical_connector`,
  `electrical_domain`, `build_partition_stream`, `build_part_atom`,
  `emit_family_rfa`, `verify_family_rfa`, `validate_family`,
  `build_embedded_unit`.
* **S0 built and VALID.** `experiments/families/genesis/S0_empty_family.rfa`
  (266,240 B) = the skeleton ONLY (self-Family, Ref. Level + type, the two
  origin reference planes, units, a 1-plan view constellation, Length /
  Width / Height parameters, ONE type with product-data text) — 21
  elements, NO geometry, our partition stream + our Global streams + our
  PartAtom + real ECC + our container. Read-back: 0 gzip CRC failures, 0 ECC
  mismatches, walker clean, 22 records/seq, 21/21 clean decodes, identical
  id sets across the 3 seqs. **`validate_family` = VALID, 0 errors, 0
  warnings** (360 references checked). Under the raw project-calibrated
  `tools/rvt_validate.py` the ONLY 3 findings are the family-file-shape
  gaps (no `ProjectInformation` — an `.rfa` carries `PartAtom` instead;
  `PartAtom` is plain unframed Atom XML ×2) — a strict subset of the FIVE
  the untouched Autodesk `.rfa` shows (its ElemTable/DIT also fail our
  decoders; OURS decode). 6-line `validate.py` family-mode diff proposed
  below / in the field map §13.
* **S0e** (`S0_electrical_family.rfa`, 270,336 B) = the electrical variant:
  a panelboard-part-type family whose type carries the panel FACTS as
  parameters (rated voltage, apparent load, enclosure W/H/D + manufacturer /
  model / description text), the document's own load classification and a
  3-pole 208 V power connector ASSOCIATED to the type's voltage / load
  parameters (the family editor's "associate family parameter" mechanism,
  decoded and reproduced byte-exact from the receptacle / luminaire
  specimens). 25 elements, VALID under `validate_family` (0 errors).
* **Both delivery forms are wired.** `to_rfa` emits the standalone file;
  `to_embedded_unit` returns the save-unit bytes (28-byte separator with
  our document GUID + record count, per-seq segments with sentinels) + the
  `Global/ContentDocuments` entry grammar + the host-side element list =
  the loader contract handed to the forge stream.

## Findings (evidence in the field map + tests)

- **The family-document skeleton = 8 constructor families** (self-Family,
  Ref. Level, LevelAttributes, RefPlane, ParamElemFamily + value shapes,
  ConnectorElem + electrical domain, units, plan-view constellation). The
  other 64 classes present in all eight specimen documents are the family
  TEMPLATE's ballast (object-style copies, fonts, dimension styles, 4
  elevations, nested annotation families) — deliberately NOT built (the
  reduction question, exactly like the project skeleton) [V population;
  U acceptance].
- **Family-document deltas from the project skeleton [all V]:** every
  family-doc element carries `m_famId` = the self-Family and OBJECT
  `m_designOptionId` = **-4** (headers keep -1; the self-Family itself and
  a few registry classes in older docs keep -1); the family Level carries a
  present-but-EMPTY `ParamValueSetInt` and `DatumPlaneGeomStep.m_flags` 0
  (projects 1); the family `LevelAttributes` sets
  `m_bRoomComputationHeightAutomatic` True + height 0 and lists BIP
  `-1007109` as a regen parent + its line-category GStyle in deletion.
- **RefPlane fully decoded [V byte-exact]:** Level-shaped datum + tail
  {`m_refName` (the "Is Reference" enum: 0 Left, 1 Center L/R, 2 Right, 3
  Front, 4 Center F/B, 5 Back, 7 Center Elev, 12 Not a Ref, 14 Weak — V
  values), `m_definesOrigin`, `m_deletionByUserAllowed`,
  `m_definesWallClosure`, `m_parentReference`, `m_subcategoryId`}, cellList
  = SketchMembership + PatternHelper, and **every reference plane names the
  plan view it was drawn in (`m_genDbViewId`) and lists it as a deletion
  parent** ⇒ a family document needs at least the 1-plan view
  constellation (S0 reuses the project skeleton's view constructors).
- **The origin trio [V]:** every family document carries "Center
  (Front/Back)" (refName 4, XZ plane) + "Center (Left/Right)" (refName 1,
  YZ plane), both `m_definesOrigin` + locked, + the Ref. Level; their
  intersection is the family origin / insertion point.
- **`ParamElemFamily` [V byte-exact]:** `ParamDefValue{caption, m_typeId =
  "revit.local.family:<32-hex creation-session guid><%08x elem id>-1.0.0",
  m_specTypeId (Forge spec), m_groupTypeId (Forge group), restriction 1}`
  (material-valued params use `ParamDefMaterialBrowse`); VALUES live in the
  self-Family's type rows keyed by the element id; the identity-data
  built-ins (`-1010104` Manufacturer, `-1010103` Model, `-1010109`
  Description, `-1010108` URL, `-1010105` Type Comments, `-1001205` cost)
  are the slots for a manufacturer's FACTS.
- **The self-Family layout is COMPLETELY understood [V byte-exact on the
  .rfa; object byte-exact modulo Autodesk's authoring `m_path` on 3 more
  docs]:** `FamilyTypeTable` (all types of a standalone family; `m_idx` =
  current; per-row `FamilyParamValue` entries), `m_familyParams` = current
  type's values, ONE `FamilyParamsOrderCell` (parameter group ordering),
  `m_familyIds` = element → monotonic absorbed index (`m_nextAbsorbedIndex`
  = max + 1), the ~90-flag behaviour block (`DEFAULT_FAMILY_FLAGS`), the
  header's deletion list = EVERY element of the document. Per-family VALUES
  (omniClass / seek ids — Autodesk taxonomy, deliberately empty in ours;
  m_path — the authoring-path identity leak, empty in ours; render/light
  bits) enumerated in the field map §9.
- **The connector's "associate family parameter" mechanism [V]:**
  `FamilyParametrizedElemParamsCell{ m_paramDrivenData[]: { m_famParamId,
  m_elemPropId (-1140002 voltage / -1140005 apparent load), m_geomTag -1,
  m_bIsSymbol } }` + the driving user params in the header deletion list —
  the receptacle's connector voltage is driven by its 'Switch Voltage'
  parameter and its load by 'Load'; the recessed light's load by the
  wattage BIP `-1140004`. S0e uses it so the panel's rated-voltage /
  apparent-load type parameters drive the connector.
- **Electrical unit rule re-confirmed [V]:** internal V / VA / W =
  display ÷ 0.3048² (208 V → 2238.89; 120 V → 1291.67; 180 VA → 1937.50;
  64 W → 688.89).
- **The single-unit partition stream is now buildable from scratch**
  (`build_partition_stream`): header + per-seq whole-record blocks (flags
  4, A/B/C by the corpus identity) + terminator + footer + end record;
  `Partitions/<N>` name from OUR increment table (N = DIT records − 1 ⇒
  `Partitions/0` for a one-episode document) [V framing / I the N a
  reader expects].
- **`rvt.genesis.skeleton.minimal_globals` is now proven end to end in a
  real container** (the project stream never assembled its minimal
  globals into a file — G0 rode on a sample's): ElemTable / History / DIT /
  PartitionTable / ContentDocuments / Contents / BasicFileInfo all decode
  and satisfy the cross-stream save invariants inside S0 (test
  `test_rfa_streams_are_ours`).

## Recommendation

The family-document skeleton is DONE at the same maturity as the project
skeleton: constructors proven byte-exact, a from-scratch assembler, and a
validating skeleton-only file. Next steps, in order:
1. **VIEWER / REVIT-GATE S0 and S0e** (below) — the family analogue of the
   project skeleton's open ladder; the answer decides whether the ballast
   reduction ladder (§10 of the field map: object-style copies →
   elevations → fonts …) is needed at all.
2. **The ADocument encoder (TRACKER G1a)** is now the shared block of BOTH
   genesis paths: S0's `Global/Latest` is the donor `.rfa`'s exactly as
   G0's is the sample project's; the embedded route additionally needs
   the ADocument to write the `ContentDocuments` entry. One codec unblocks
   both.
3. The **geometry stream** authors `ExtrusionElem` / profile sketches onto
   this document (`FamilyDoc` is the surface: it hands over the self-Family
   id, the origin planes for sketch planes and the id source) and re-points
   the connector's host face (`m_oPlaneRef.m_geomRef`) from the Ref. Level
   datum to the real top face.
4. The **forge stream** implements the project-side loader against
   `FamilyDoc.to_embedded_unit()`'s contract.

## Requests for the orchestrator

1. **VIEWER/REVIT-TEST** (both self-verify green + validate 0 errors in
   family mode; ordered by confidence):
   - `experiments/families/genesis/S0_empty_family.rfa` — a Furniture
     family, ONE type 'Standard' (600 × 300 × 150 mm Length/Width/Height +
     description / manufacturer / model text), NO geometry. Expectation
     if the skeleton suffices: the family editor opens it showing the two
     centre reference planes and the Ref. Level; Family Types lists
     'Standard' with the three lengths. A pass proves the whole
     from-scratch family document (our partition stream + our Globals + our
     PartAtom + our container). A fail isolates §12's ranked unknowns
     (view/ballast reduction, foreign `Global/Latest`, `Partitions/0`).
   - `experiments/families/genesis/S0_electrical_family.rfa` — an
     Electrical Equipment (panelboard part type) family, type '225 A MLO'
     (Panel Voltage 208 V, Apparent Load, 508 × 1524 × 146 mm), a 3-pole
     power connector associated to those parameters, referenced to the Ref.
     Level datum (no solid yet — the one deliberate UNKNOWN of the
     electrical path).
2. **Core diff for `src/rvt/validate.py` (6 lines; not my territory):**
   family mode — treat `PartAtom` as an UNFRAMED stream and drop
   `ProjectInformation` from `REQUIRED_STREAMS` when `PartAtom` is present.
   Exact diff in `docs/writer/family-skeleton.md` §13. Until then
   `rvt.famgen.skeleton.validate_family(path)` applies the same two
   adjustments at runtime (both S0 files: 0 errors) and reports the raw
   project-mode result beside it.
3. **`tools/sync_plugin.py`:** `tests/test_plugin_sync.py` will report drift
   for the new `src/rvt/famgen/` package (my change) plus the other in-flight
   streams' files. Left for the orchestrator to run once this tick's
   streams are integrated (running it now would re-zip the plugin around
   other streams' unfinished work). Recorded, not applied.
4. `KNOWLEDGE.md` additions worth merging: (a) the family-document deltas
   (`m_designOptionId` -4 on element objects, `m_famId` = self-Family,
   family Level/LevelAttributes deltas); (b) the RefPlane "Is Reference"
   enum + the origin trio + the plan-view dependency; (c) the connector
   "associate family parameter" cell + the `-1140002` / `-1140005`
   element-property ids; (d) the identity-data type BIPs; (e) `Partitions/N`:
   N = DIT record count − 1; (f) the standalone `.rfa`'s types live in the
   self-Family's `FamilyTypeTable` (already in families.md) with the
   `FamilyParamValue` entry shape.
5. **Open ADocument gate (G1a) now blocks two streams' next steps** (this
   one's Global/Latest + ContentDocuments entry; genesis's Global/Latest) —
   worth a dedicated codec stream. Every input byte of the embedded
   ADocument is addressable (`families.content_document_adoc`), and the
   inline↔externalized transform is specified (family-authoring §2.1).

## Verification

- `.venv/bin/python -m rvt.famgen.skeleton` regenerates
  `experiments/families/genesis/S0_empty_family.rfa` +
  `S0_electrical_family.rfa` + their `*_validate.json` (~6 s): prints the
  63/63 record round-trip, read-back verification and both validator
  verdicts (family mode VALID; project mode = the 3 known .rfa-shape gaps).
- `.venv/bin/python -m pytest tests/test_famgen_skeleton.py -q` → **14
  passed**: byte-exact specimen reconstruction (Ref. Level, LevelAttributes
  ×2, RefPlanes ×3, ParamElemFamily ×3, ConnectorElem ×3, self-Family),
  S0 / S0e round-trip + closure (no dangling references), type / parameter
  authoring, unit helpers, S0 / S0e emission + `validate_family` 0 errors,
  our Global streams decode + save invariants, the embedded-unit contract.
- Full suite (`.venv/bin/python -m pytest tests/ -q --ignore=tests/oracle`,
  10:29): **569 passed, 1 failed** — the single failure is
  `tests/test_plugin_sync.py` (plugin drift listing 14 new/changed source
  files: my `src/rvt/famgen/{__init__,skeleton}.py` PLUS other in-flight
  streams' `famgen/{catalog,geometry}.py`, `famgen/facts/*`,
  `genesis/house_standard.py`, `provenance.py` — the known cross-stream
  drift left for the orchestrator's `tools/sync_plugin.py` run, request 3).
  No other stream's test is affected.

BRANCH STATE: no git repo (working tree); deliverables complete —
src/rvt/famgen/{__init__.py, skeleton.py} (the FamilyDoc builder +
constructors + partition assembler + .rfa emitter + embedded-unit contract
+ family-mode validation), tests/test_famgen_skeleton.py (14 pass),
docs/writer/family-skeleton.md (the field map + validate.py diff),
experiments/families/genesis/{S0_empty_family.rfa, S0_electrical_family.rfa,
S0_empty_family_validate.json, S0_electrical_family_validate.json}; READY —
S0 + S0e await the viewer/Revit acceptance gate; the next code steps are the
ADocument codec (G1a, shared with genesis) and the geometry stream's forms
onto `FamilyDoc`.
