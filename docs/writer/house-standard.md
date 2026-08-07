# HOUSE STANDARD — our own default content and the resource-identifier ledger

Stream: **own-content** (2026-08-03). Module: `src/rvt/genesis/house_standard.py`.
Tests: `tests/test_house_standard.py` (12). Record: `docs/inbox/own-content.md`.
Serves TRACKER P0 gate G1 sub-gates **G1b (own default content)** and
**G1c (resource identifiers)**, opened by `docs/inbox/genesis-audit.md`.

---

## 0. What this is, in one paragraph

The genesis constructors (`rvt.genesis.types` / `rvt.genesis.skeleton`) build
schema-valid elements field by field — the audit did not fault them. It faulted
their **inputs**: the first genesis candidate fed them Autodesk's stock values
(ElectricalSetting 46/49 leaves identical to the rme sample's; the project view a
0.91 structural clone of racbasic's; base points 0.95; the phase filters, load
classifications, sun and site defaults all Revit's) and let them emit Autodesk
resource identifiers (`assetlibrary_base.fbx`, `SunAndSky-002`, the `%1!s!`
MACH label strings, Autodesk-HQ site coordinates). `house_standard.py` is the
single source of OUR default content: every value is **plain data with a stated
provenance** — a physical or regulatory FACT (cited), a public STANDARD (cited),
or a value INVENTED BY US — and it DRIVES the existing constructors without
editing them. A companion table dispositions every Autodesk identifier the
package can emit (drop / replace / required-format-token), applying the drops
and replacements as documented shims until the owning streams parameterise
them. Measured against **all six** Autodesk 2026 samples with the ledger's own
16-byte-shingle metric: **0 of 234 elements is a similarity violation** (3
elements ≥ 0.85, all in classes that provably leave no free choice); every
value-bearing class the audit named dropped from ~0.8 to below 0.4. And the
whole thing assembles: driven through the unmodified `genesis_assemble` ladder,
the house-standard content produces G0a…G0 files that all pass
`tools/rvt_validate.py` with **0 errors**.

## 1. The three provenance classes — and the rule

Every value in the module is exactly one of:

| class | meaning | examples in the standard |
|---|---|---|
| **FACT** | a physical / regulatory / product fact anyone would state identically; cited | ANSI C84.1 Range A voltage limits (±5 %); NEC Ch.9 Table 4 conduit diameters and Table 2 bend radii; NEC 310.16 ampacities; NEMA VE-1 tray widths; ISO 3098 lettering heights; ISO 2533 standard-atmosphere temperature; the manufactured elbow angles of conduit fittings; 5/8 in gypsum board / 92 mm stud / 190 mm CMU dimensions |
| **STANDARD** | a public convention we adopt (cited) | drafting line-weight logic (cut heavier than projection); IEC 60445 line-conductor labels L1/L2/L3; NEC branch-circuit rating 20 A |
| **OURS** | invented by us — our house convention | every `GEN …` name; the discipline colour/pen scheme; hatch spacings; material colours; our phase wording and filter SET; label phrasing; storey height 12 ft; plan cut 4 ft / top 8 ft; south-45° study sun; the neutral 0°/0° site |

**Rule (G1b):** nothing is copied from an Autodesk sample or template. Where a
class leaves NO free choice — a survey point *is* the origin, a copper
conductor *is* named "Copper", an object-style row is 60 bytes of fixed
serialization around 8 authorable bytes — the module says so
(`NO_FREE_CHOICE`) instead of pretending an authored value exists.

## 2. Inventory (234 elements) with provenance per section

| module section | elements | classes | provenance basis |
|---|--:|---|---|
| §1 identity `PROJECT_INFO` | 1 | ProjectInfo | OURS (job placeholders) |
| §2 units registry (24 imperial formats; 17-entry metric alternate) | 1 | UnitsElem | choices OURS; the typeIds are REQUIRED FORMAT TOKENS (§6 row `forge-typeids`), every string VERIFIED present in the 2026 corpus |
| §3 site & sun | 6 | GeoSite ×2, GeoLocation ×2, TrueNorth, SunAndShadowSettings (doc) | neutral: lat/long 0/0, UTC, no weather station, ISO-2533 temperatures (FACT); names OURS |
| §4 levels | 3 | Level ×2, LevelAttributes | "L1 - Ground Floor" / "L2 - Second Floor" at 0 / 12 ft (OURS); datums are report-only in the ledger |
| §5 phases | 8 | ProjectPhase ×2, AllProjectPhases, PhaseFilterElem ×5 | our wording + our filter SET built from the **decoded** vector semantics (F-HS-5); phasing-override graphics OURS |
| §6 patterns | 9 | LinePatternElem ×4, FillPatternElem ×5 | dash rhythms / hatch spacings OURS |
| §7 materials | 13 | MaterialElem | representational colours OURS; asset descriptor DROPPED (§6) |
| §8 system-family types | 6 | BasicWallType ×3, Floor/Roof/Ceiling ×1 each | our assemblies; layer thicknesses = product dimensions (FACT) |
| §9 electrical | 40 | voltages 6, distribution 5, demand factors 5, load classes 6, ElectricalSetting, conduit standards 4 + sizes + types 5, tray sizes + types 3, conductor cells 9, wire types 3 | tables FACT (ANSI C84.1, NEC), names + assembly OURS |
| §10 text types | 12 | TextNoteAttributes ×3 (+ font, category, style each) | ISO 3098 heights (FACT); font name = third-party font reference (§6) |
| §11 object styles | 102 | GStyleElem ×94, CategoryElem ×4 (+ their styles) | HOUSE_SCHEME pens/colours OURS; category/cuttability = format enum |
| §12 views | 33 | DBViewProject, DBView3d, DBViewPlan ×2, DBViewType ×3 + 26 satellites | our names/camera/scale/view range; render descriptors DROPPED; visibility policy OURS |
| **total** | **234** | 47 classes | ids 1,500,000–1,500,233; 234/234 encode→decode **byte-exact**; **0** dangling references |

The full per-element manifest (id / class / kind / name / parameters) is
`HouseCatalog.manifest`; the units-registry label states the **emitted** count
(24), retiring the audit's "136-vs-8" accounting error (B6) for good — a test
pins label to reality.

## 3. The values, with sources (highlights per section)

**Electrical (§9).** Voltages 120/208/240/277/480/600 V, min/max = ANSI C84.1
Range A service voltage (±5 % of nominal; 120 V → 114/126). *(Finding F-HS-2:
`types.NOMINAL_VOLTAGE_RANGES` claims NEC/ANSI provenance but its 110/130,
200/220, 460/490 ranges are exactly the rme template's rounded values — the
standard bypasses it by always passing explicit min/max.)* Distribution systems
= the ANSI C84.1 Table 1 service configurations (120/240 1φ 3W; 208Y/120 3φ
4W; 480Y/277 3φ 4W; 480 3φ 3W Δ; 600 3φ 3W Δ). Demand factors: continuous
loads 125 % (NEC 210.19(A)/215.2(A)); receptacles first 10 kVA @ 100 %,
remainder @ 50 % (NEC 220.44, load-range rule 4 with the threshold in internal
power units 10,000 × 10.7639 = 107,639.1 — decoded from rme); motors 125 % of
largest + 100 % of rest (NEC 430.24, count rule 3); commercial kitchen (NEC
220.56 table, count rule — encoding *[hypothesis]*); no-diversity 100 %. Load
classifications = the standard load families with our labels and the correct
semantic enums decoded this session (space-load-class 1 = lighting, 2 =
receptacle; signature 1 = motor, 3 = spare — F-HS-4). ElectricalSetting: phase
labels L1/L2/L3 (IEC 60445, our convention over the samples' A/B/C), circuit
rating 20 A (NEC 210.3 fact), wiring-path offset 8 ft AFF (ours), fitting
angles 11.25/15/22.5/30/45/60/90° (manufactured elbow angles — fact), our
schedule policies (spares excluded from totals, multi-pole merged). Conduit:
EMT/IMC/RMC/PVC-40 with NEC Ch.9 Table 4 inner diameters, product-standard
outer diameters and NEC Ch.9 Table 2 bend radii. Cable tray widths 6–36 in
(NEMA VE-1). Conductor cells and wire types: Cu THWN-2 75 °C, Cu THHN 90 °C, Al
XHHW-2 75 °C (500 / 750 kcmil max, NEC Ch.9 Table 8 diameters). The NEC 310.16
ampacity table (Cu/Al, 75/90 °C columns) ships as `WIRE_AMPACITY_TABLE` DATA —
no `RbsWireSizesElem` constructor exists yet; the record proposes it.

**Phases (§5).** Two phases, our wording ("Existing Conditions" / "New Work"
with descriptions). Five filters, our names and our SET, built from the
presentation-vector semantics **decoded this session** (F-HS-5: slots 2/3/4/5 =
Existing/Demolished/New/Temporary; 0 = not displayed, 1 = by category, 2 =
overridden — proven on the three "Show New / Show Complete / Show All" vectors
identical across rst/rme/rac). Four of our five vectors occur in no shipped
Autodesk filter; "GEN New Work Only" necessarily equals the corpus 'Show New'
vector because *show only new work* has exactly one encoding (documented, not
copied). Phase-status graphics (the AllProjectPhases override table) = our
drafting convention (existing light grey, demolition grey dashed, new full
black weight, temporary blue-grey), referencing OUR phase materials and OUR
demolition dash pattern.

**Views / site / sun (§3, §12).** Neutral site at 0°/0° (WGS-84 origin), UTC,
no weather station, ISO 2533 15 °C in every climate slot — replacing the
Autodesk-HQ Waltham MA coordinates and stock design-day arrays that the
skeleton defaults inherit (F-HS-6). Our still sun (south, 45°) with our name on
every view. Views: '{3D}' → "GEN Working 3D"; plans named for their levels; our
plan view range (cut 4 ft / top 8 ft), 1/8" = 1'-0" plan scale; our visibility
policy = **no** categories excluded by default (the sample-template exclusion
lists gone); reference label "SIM."; the project view keeps its REQUIRED name
'???' (identical in every corpus file including the German ones).

**Object styles (§11).** The discipline-coded HOUSE_SCHEME (architectural
black 1/4, structural oxblood 2/5, electrical navy 1/3, mechanical green,
piping steel-blue, site brown, annotation 1/1) over 61 built-in categories +
four `GEN` sub-categories. Autodesk's extracted 1,074-row table stays
QUARANTINED (`experiments/genesis/reference/`) and is never read.

## 4. The similarity report (G1b acceptance) — all six samples

Instrument: `similarity_report(cat)` = for every record, the maximum
16-byte-shingle overlap (the provenance ledger's own metric,
`rvt.provenance._CloneIndex.best_match`) against every same-class element of
each of the six sample documents (`rstbasic`, `rmebasic`, `racbasic`,
`racadvanced`, `rstadvanced`, `dach`). Payload-based, so it needs no id
watermark and works against dach too (the ledger's created/cloned classifier
cannot — dach's watermark 4 M+ exceeds our ids, so it calls everything
'unmatched'). Reproduce:
`.venv/bin/python -m rvt.genesis.house_standard --similarity`.

**Result: 3 / 234 elements ≥ 0.85, 0 violations** (all three in NO_FREE_CHOICE):

| id | class | max sim | vs | why no free choice exists |
|---|---|--:|---|---|
| 1500191 | BasePoint (survey point) | 0.946 | rme 584700 | a base document's survey point sits at the model origin (0,0,0) with the fixed point-marker rep; the only value IS the origin |
| 1500206 | Viewer (project view's) | 0.902 | rac 231 | a crop/camera frame with no user-facing definition; every corpus template carries the same frame |
| 1500190 | BasePoint (project base) | 0.892 | rme 584697 | as above |

Distribution: **98 < 0.50, 133 in 0.50–0.85, 3 ≥ 0.85** (was 50 / 151 / 4 on
the old inline content). Before/after, max similarity per class (old = the
`genesis_assemble.build_our_content` values the audit measured; HS = this
standard):

| class | old max | HS max | Δ | reading |
|---|--:|--:|--:|---|
| ElectricalSetting | 0.79 | **0.17** | −0.62 | our values (audit's 46/49-leaves finding retired) |
| ProjectPhase | 0.79 | **0.18** | −0.60 | our wording |
| ElectricalLoadClassification | 0.81 | **0.24** | −0.57 | our labels + decoded enums |
| PhaseFilterElem | 0.84 | **0.39** | −0.45 | our set + names |
| DBViewType | 0.71 | **0.30** | −0.41 | our names + reference label |
| SunAndShadowSettings | 0.71 | **0.32** | −0.39 | our sun everywhere |
| DBViewPlan / GeoLocation | 0.70 / 0.65 | 0.44 / 0.39 | −0.26 | our range/policy/names |
| CableTraySizesElem | 0.52 | **0.27** | −0.25 | NEMA VE-1 width list (ours differs) |
| DBViewProject | 0.91 | **0.70** | −0.21 | render descriptors dropped + our policy — no longer ≥ 0.85 |
| Level | 0.67 | 0.47 | −0.21 | our naming |
| MaterialElem | 0.51 | **0.36** | −0.16 | Autodesk asset descriptor dropped |
| DBView3d / AllProjectPhases | 0.62 / 0.74 | 0.51 / 0.63 | −0.12 | mostly machinery |
| BasePoint / Viewer | 0.95 / 0.90 | 0.95 / 0.90 | 0 | **no free choice** (registry) |
| GStyleElem / CustomElement / ModelClipBox | 0.83 / 0.82 / 0.80 | same | 0 | machinery-dominated, below 0.85, registered defensively |
| every type/pattern/electrical class | ≤ 0.62 | ≤ 0.61 | ≈0 | were already ours; ConduitStandardType 0.61 = a name-only class |
| GeoSite | 0.16 | 0.26 | +0.10 | neutral zeros ≈ short repeated values; irrelevant (< 0.5) |

**The ledger's own view** (its 0.50 heuristic, five baselines — dach is
unattributable by id): the HS-driven G0 reads **99 / 234 created against ALL
five samples** (was 51 / 205 = 25 %) and 135 cloned-vs-any, and every one of
those 135 is a machinery class this document names (90 GStyleElem, 9
conductor cells, ~24 view satellites, 2 base points, 4 conduit-standard
name-cells, 3 tray types, 2 text + 3 fonts + 3 categories, 1 units, 1 phase
set, 1 project view). Every VALUE-bearing class the audit named now reads
`ours-created` against every sample. The 0.50 heuristic on machinery classes is
the counsel/definition-field question the audit already routed (§D-4); this
stream's job — the values — no longer feeds it.

## 5. The classes that leave no free choice (`NO_FREE_CHOICE`)

| class | measured max | reason (verbatim summary) |
|---|--:|---|
| BasePoint | 0.95 | the base document's project base / survey points are the model origin with the fixed marker rep; the coordinate is the only value |
| Viewer (project view) | 0.90 | a bound/camera frame with nothing user-facing; identical in every template |
| DBViewProject | 0.70 | 461/474 leaves are display machinery; name is the required '???'; our authorable share is a few dozen bytes of ~2 kB — the rest needs the view-display constructor parameters (§7 diffs) |
| GStyleElem | 0.83 | ~60 bytes of fixed serialization around ~8 authorable bytes (category / pen / colour / pattern) — ours change every one of them |
| CustomElement | 0.82 | name-only conductor cells whose names ('Copper', '75', 'THWN-2', '500') are physical/code designations, not authorship |
| ModelClipBox | 0.80 | the section box = axis-aligned half-extents owned by the Viewer3d |

`test_house_standard` asserts every ≥ 0.85 element's class is in this registry,
so a future value change that clones a specimen fails CI.

## 6. Resource-identifier disposition table (G1c)

Method: source grep of the genesis package + `identifier_scan()` (a UTF-16
string scan of every serialized record) + a whole-file scan of the assembled
HS G0. `disposition`: **drop** (a) / **replace** (b) / **required** = required
format token, argued for counsel (c). *shim* = applied by `house_standard`
over constructor output pending the constructor diff (§7).

| identifier | where emitted | count | disposition | action | probe |
|---|---|--:|---|---|:-:|
| Material asset descriptor `'Generic'` + `'assetlibrary_base.fbx'` + type 4 | `types.new_material` | 13 | **drop** | descriptor blanked (name/library "", type 0); materials are graphics-only, shade by colour | yes |
| View render assets `'SunAndSky-002'`, `'Generic'` ×2, all with `'assetlibrary_base.fbx'` | `skeleton._grender_settings` via every view | 32 | **drop** | asset names/libraries blanked; numeric render properties kept neutral | yes |
| Load-classification labels `'Actual %1!s! Load'` … (6 MACH strings) | `types.new_load_class` (hard-coded) | 36 | **replace** | our phrasing (`LOAD_LABEL_TEMPLATES`) | — |
| the `%1!s!` placeholder itself | inside those labels | 36 | **required** | Windows FormatMessage substitution SYNTAX the reader expands the name into | — |
| Forge typeIds `autodesk.spec.aec:*`, `autodesk.unit.unit:*`, `…symbol:*` | UnitsElem format map (`UNIT_FORMATS_*`) | ~68 | **required** | the KEYS/vocabulary the reader looks units up by (identical in every 2026 file); the *choices* are ours; identifier-set licence = counsel (audit D-3(a)) | — |
| Site defaults: Waltham MA coords, station `'52939_2004'`, stock design-day temps | `skeleton.new_geo_site` defaults | 2 sites | **replace** | neutral SITE (0°/0°, UTC, ISO-2533 climate) | — |
| Sun name `'<In-session, Still>'` + stock 135°/35° | `skeleton.new_sun_and_shadow_settings` | 4 | **replace** | our SUN on document + view suns | — |
| Phase names / filter names + vectors | `skeleton.DEFAULT_PHASE_FILTERS` (unused here) | 2 + 5 | **replace** | `PHASES` / `PHASE_FILTERS` (decoded semantics) | — |
| `'{3D}'` view name, `'Sim'` reference label | assembler / `skeleton.new_view_type` | 1 + 3 | **replace** | "GEN Working 3D"; `'SIM.'` | — |
| DBViewProject name `'???'` | `skeleton.new_project_view` | 1 | **required** | identical in EVERY corpus file incl. German — an internal token, not text | — |
| Wall system-family designator `'Basic Wall'` | `types.new_wall_type` param −1010105 | 3 | **required** | names the kernel system family (vs Curtain/Stacked); `family_name=None` fallback probe available | opt |
| BuiltInCategory/Parameter ids, −3000010 sentinel | throughout | many | **required** | the public enum every interoperator keys on | — |
| Font name `'Arial'` | `TEXT_FONT` → `new_text_type` | 3 | **required** | an OS font reference (third-party, not Autodesk); OFL swap available | — |
| *outside the package:* partatom `urn:schemas-autodesk-com:partatom`, `adsk:revit`, `<A:product>Revit</A:product>` | `genesis_assemble` ProjectInformation | 1 | **required** | XML schema namespace / taxonomy the reader parses; product-name mark = counsel G3 | — |
| *outside:* Revit version/build `2026` + `20250227_1515(x64)`, History format list …2662 | `skeleton.REVIT_2026_BUILD`, `rvt.identity` | 1 | **required** | reader gates opening on it (`identity.py`) | — |
| *outside:* Formats/Latest (Autodesk's class map, byte-identical) | container | 1 | **required** | not this stream's; audit D-3(b) / counsel C4 | — |
| *outside, found by the whole-file scan:* save-unit signature banner **`'Data generated by Autodesk® Revit®'`** + application GUID `34b22600-…` inside `Partitions/21` (docs/streams/05-partitions.md) | commit / stream framing carried from the base | 1 per save unit | **counsel + probe** | either a required framing record OR an authorship claim we must not assert — probe a G0 with the banner AString replaced by ours; counsel alongside C1 | **yes** |

After the shims, `identifier_scan()` of the catalog reports only: our six label
templates (containing the required `%1!s!` token), the required Forge
typeIds, and our own `rev-revit` strings. `test_house_standard` forbids
`assetlibrary_base.fbx`, `SunAndSky-002`, `52939_2004`, the six Autodesk label
strings, `<In-session`, and a whole-string `Generic` from ever reappearing.

## 7. Constructor diffs that retire the shims (`CONSTRUCTOR_DIFFS`)

| file :: function / constant | change | retires |
|---|---|---|
| `types.py :: new_material` | `asset_name=''`, `asset_library=''`, `asset_type=0` kwargs replacing the hard-coded overlay (types.py ≈ 995–999) | material-asset-descriptor |
| `types.py :: new_load_class` | `labels: dict = None` for the six `m_*Label` fields + `signature_type: int = 0` (`m_signitureType` is hard-coded 0, so Motor=1 / Spare=3 are inexpressible) | load-class-labels, F-HS-4 |
| `types.py :: new_demand_factor` | correct the rule-type map: corpus has 3 = count ranges, 4 = load ranges in internal power units; `'load': 2` is unobserved (F-HS-3) | — |
| `skeleton.py :: _grender_settings / view_display_mgr / dbview_base / new_project_view / new_3d_view / new_plan_view` | `render_env_name=''`, `asset_library=''` (+ background/sky/ground colour) threaded from the three view constellations | view-render-assets |
| `skeleton.py :: new_project_view / new_3d_view / new_plan_view` | `excluded_categories=None` (default = DRAW_EXCLUDED_CATEGORIES[kind]) + pass sun name/azimuth/altitude to the satellite SunAndShadowSettings | visibility policy + sun-defaults |
| `skeleton.py :: new_geo_site` | climate params (summer/wet-bulb/mean-daily arrays, winter dry bulb, clearness) defaulting to the ISO-atmosphere neutral set | site-location-defaults |
| `skeleton.py :: new_view_type` | `ref_label='Sim'` (m_refLabelStr) | view-terminology |
| `skeleton.py :: new_true_north` | `poche_depth_ft` (hard-coded −3 m product default) | true-north poche |
| `skeleton.py :: DEFAULT_UNIT_FORMATS` | replace with `house_standard.UNIT_FORMATS_IMPERIAL`; its spec keys (`…length-2.0.0`, `current-2.0.0`) and `feetFractionalInches` unit **do not occur in the 2026 corpus** (F-HS-1) | — |
| `types.py :: NOMINAL_VOLTAGE_RANGES` | relabel/replace: the values are Autodesk's template ranges, not ANSI C84.1 (F-HS-2) | — |
| **`tools/genesis_assemble.py :: build_our_content`** | **replace the inline values with `house_standard.build_catalog(start_id)`** — same OurContent shape (`.elements/.manifest/.ids/.roundtrip/.dangling`); proven this session (§8) | **integration** |

## 8. Assembly proof — the HS content builds a validator-clean ladder

The unmodified `tools/genesis_assemble.py :: build_ladder` was driven with
`build_our_content` monkeypatched to `house_standard.build_catalog` (the exact
integration in §7's last row), writing into the session scratchpad (not
`experiments/` — no repo output changed):

```
== base R10b.rvt: lineage watermark 1,472,524; our ids from 1,500,000
== OUR content: 234 elements (ids 1,500,000..1,500,233); round-trip 234/234; dangling refs 0
== G0a insert  -> G0b maximal GC -> G0c remove all family docs -> G0d 2nd GC -> G0 own-save
   (9.3 s total)
tools/rvt_validate.py on each rung:
  G0a  VALID (no errors); warnings=1 (the base's known ES-decode gap), records 21,882
  G0b  VALID (no errors); warnings=0, records 13,311
  G0c  VALID (no errors); warnings=0, records 1,200
  G0d  VALID (no errors); warnings=0, records 705
  G0   VALID (no errors); warnings=0, records 705   (380,928 bytes)
```

The HS G0's `Partitions/21` contains **no** `assetlibrary_base.fbx` /
`SunAndSky-002` / `Generic` / Autodesk label strings; the only Autodesk string
in our partition stream is the save-unit banner (§6 last row — outside this
stream's territory, now on the counsel list).

## 9. Findings for the owning streams

| id | finding | owner |
|---|---|---|
| F-HS-1 | `skeleton.DEFAULT_UNIT_FORMATS` typeIds (`autodesk.spec.aec:length-2.0.0`, `…current-2.0.0`, `feetFractionalInches-1.0.0`) do not occur in the 2026 corpus; the samples key `…length-1.0.0` / `…current-1.0.0`, and feet-and-inches is a **symbol** (`autodesk.unit.symbol:feetAndInches-1.0.1`) | skeleton |
| F-HS-2 | `types.NOMINAL_VOLTAGE_RANGES` = Autodesk's rme template ranges (110/130 …), not ANSI C84.1 (±5 % → 114/126) despite the "NEC/ANSI facts" label | types |
| F-HS-3 | demand-factor `m_ruleType` on the corpus: 0 constant, **3 = count ranges** (motor "largest 1 at 125 %"), **4 = load ranges in internal power units** (10 kVA stored as 107,639.104 = ×10.7639); `{'load': 2}` unobserved | types |
| F-HS-4 | `ElectricalLoadClassification` semantic enums decoded (rme): `m_spaceLoadClass` 1 = lighting, 2 = power/receptacle; `m_signitureType` 1 = motor, 2 = other, 3 = spare; `new_load_class` hard-codes signature 0 | types |
| F-HS-5 | phase-filter presentation vector **decoded** (was INFERRED with the value order reversed): slots 2/3/4/5 = Existing/Demolished/New/Temporary; 0 = not displayed, 1 = by category, 2 = overridden | skeleton |
| F-HS-6 | GeoSite/GeoLocation naming: corpus GeoSite symbol names are EMPTY; 'Internal'/'Project' live on the GeoLocation instances and are localized free text (German 'Intern'/'Projekt', with an English 'Internal' coexisting in dach); skeleton's default coordinates ARE Autodesk HQ (Waltham) — the corpus stock site | skeleton |
| F-HS-7 | the save-unit terminator banner `'Data generated by Autodesk® Revit®'` (+ app GUID `34b22600-…`) is present in every G-file's `Partitions/21`, carried by the commit/framing layer — a resource identifier / authorship claim no stream currently owns | commit + counsel |

## 10. Wire ampacity data pending a constructor (RbsWireSizesElem)

`WIRE_AMPACITY_TABLE` (Cu/Al × 75/90 °C, NEC 310.16 ampacities, NEC Ch.9
Table 8 diameters) is DATA ONLY. The target class structure is now known
(decoded from rme 293190): `RbsWireSizesElem.m_mapMaterials = [{first:
material-cell id, second: {m_mapTemperatureRatings: [{first: rating-cell id,
second: {m_arrWireSizes: [{m_strSize, m_dAmpacity, m_dDiameter (ft),
m_bInUse}]}], …}}]` (plus the analogous insulation map). A `wire_sizes_element(
by_material_and_rating)` constructor in `types.py` (the electrical-catalog
stream's queue) consumes the table directly; the record files it as a
proposal, since a constructor is beyond a diff to an existing one.

## 11. Reproduction

```
.venv/bin/python -m rvt.genesis.house_standard                 # build + roundtrip + identifier scan
.venv/bin/python -m rvt.genesis.house_standard --similarity    # + six-sample similarity (0.85 gate)
.venv/bin/python -m pytest tests/test_house_standard.py -q     # 12 tests (incl. the six-sample gate)
```
