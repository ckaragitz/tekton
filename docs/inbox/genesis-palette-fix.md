# genesis-palette-fix — THE ONE NAMED CONSTRUCTOR DEFECT: Group B's PALETTE bucket (workstream record, 2026-08-04)

## RESULT IN ONE SCREEN

**The palette bucket's failure is a single, mechanical, source-level bug —
DIAGNOSED WITH ON-DISK PROOF and FIXED.  `residue_b._int_param_set` swaps
`m_paramId` and `m_value` in EVERY structural and thermal
`PropertySetElement` it emits: the failing `ZB5_palette.rvt` carries 78
swapped int-param entries across all 28 landed property sets — small
POSITIVE `m_paramId` values (3 / 0 / 1) where every built-in id is
negative, i.e. the built-in ids masquerading as `ParameterElement`
ElementIds pointing at document-birth singletons.  The material sub-class
is EXONERATED by prior certification.  Seven probes + the certified control
are built, all validator-VALID, byte-delta-clean and four-registry
coherent; the three diagnostic probes reproduce ZB5's 38 changed records
BYTE-FOR-BYTE; `Z_palette_v2` (= certified Y9 + the whole corrected bucket)
is the deliverable.**  Reproduce: `.venv/bin/python -m
rvt.genesis.residue_b2` (~20 s; refuses an uncertified base).

Base: `experiments/genesis/subst_k4/Y9.rvt` — viewer-CERTIFIED (VERDICTS
#17).  Every probe = Y9 + one substitution set, IN PLACE (seq-102 only;
`Global/Latest` + `Global/ElemTable` byte-identical; the Y-ladder's 1,333
landed slots protected).  Control `CTRL_Y9_base.rvt` md5-identical to Y9.

| # | file (`experiments/genesis/subst_k4/palette_fix/`) | substituted in place | predicted | local verdict |
|--:|---|---|---|---|
| 1 | **Z_palette_v2.rvt** | 10 materials + 17 structural + 11 thermal, ALL CORRECTED | **PASS** | VALID |
| 2 | P_pal_mat.rvt | ONLY the 10 surplus materials (certified constructor) | PASS | VALID |
| 3 | P_pal_struct.rvt | ONLY the 17 structural assets, residue_b's ORIGINAL (swapped) | **FAIL** | VALID |
| 4 | P_pal_thermal.rvt | ONLY the 11 thermal assets, residue_b's ORIGINAL (swapped) | **FAIL** | VALID |
| 5 | P_pal_swapfix.rvt | ZB5's EXACT 38 objects, ONLY the int keying corrected | PASS iff D1 alone | VALID |
| 6 | P_pal_struct_v2.rvt | ONLY the 17 CORRECTED structural assets | PASS | VALID |
| 7 | P_pal_thermal_v2.rvt | ONLY the 11 CORRECTED thermal assets | PASS | VALID |
| — | CTRL_Y9_base.rvt | (control, md5 = Y9) | PASS | — |

Independent arbiter: `tools/rvt_validate.py --quiet
experiments/genesis/subst_k4/palette_fix/*.rvt` → 8 × `OK errors=0
warnings=1` (the warning = the corpus-wide standing ES decode gap; the
certified base carries it too).

**Upload order (`palette_fix/probes.json:upload_order_bisection_first`,
control FIRST): Z_palette_v2, then P_pal_mat, P_pal_struct, P_pal_thermal,
P_pal_swapfix, P_pal_struct_v2, P_pal_thermal_v2.  ONE round both names the
guilty class and tests the fix: Z_palette_v2 PASS closes the defect; the
singles are its falsifiable bisection.**

## The bucket (what ZB5 substituted)

The palette bucket = 38 residue slots of Y9 in THREE sub-classes:

| sub-class | slots | our constructor (residue_b) | ZB5 |
|---|--:|---|---|
| surplus `MaterialElem` (the palette slots Y7 did not fill) | 10 | `extended_material` → `types.new_material` | landed |
| STRUCTURAL `PropertySetElement` (m_propertySetType 1) | 17 | `structural_asset` (LEGACY shape) | landed |
| THERMAL `PropertySetElement` (type 2) | 11 | `thermal_asset` | landed |

(residue_b's ZB5 docstring says thermal is "LEFT as residue"; the code
lands it — a stale docstring.  All 38 landed, 38 changed.)

## The diagnosis — evidence

### D1 — PRIMARY, CERTAIN: the int-param swap [VERIFIED on the failing file]

`residue_b._int_param_set(pairs)` iterates `for k, v in pairs` expecting
`(param_id, value)`.  Both call sites (lines 1360 and 1481) build the
tuples as `(VALUE, param_id)` and pass them through the NO-OP comprehension
`[(v, k) for v, k in ints]` — it unpacks `v, k` and re-emits `(v, k)`
unchanged, so `k` = the VALUE and `v` = the ID land in
`{"m_paramId": k, "m_value": v}` — SWAPPED.  (The AString call site's
identical-looking `[(k, v) for k, v in strs]` is also a no-op, but its
input is already `(id, value)`, so the strings are correct.  The DOUBLE
helper serialises value-first from `(value, id)` inputs and is correct too.)

On disk, from the field-by-field diff of ZB5 slot 194585 vs Y9 (parent →
ours):

    parent m_pIntParams:  {m_paramId: -1150464, m_value: 3}
                          {m_paramId: -1140322, m_value: 0}
    ours   m_pIntParams:  {m_paramId: 3, m_value: -1150464}      <- SWAPPED
                          {m_paramId: 0, m_value: -1140322}      <- SWAPPED

`rvt.genesis.residue_b2.diagnose_zb5()` scans `residue_b/ZB5_palette.rvt`
as emitted: **78 swapped int-param entries; 28 of 28 landed
PropertySetElements carry the swap** (17 structural × 2 + 11 thermal × 4).
Every built-in param id in the corpus is NEGATIVE; a POSITIVE
`m_paramId` is read as the ElementId of a `ParameterElement`, and ids
0 / 1 / 3 land on document-birth singletons (id 1 = `AllProjectPhases`) —
a dangling typed reference resolved LATE, when the extractor walks the
material / asset library.  That is precisely the observed signature: the
viewer builds the whole view tree (3D view + sheet S101) and THEN dies —
subtle, late, not structural.

**Confinement:** `_int_param_set` has exactly TWO call sites — the two
palette constructors.  No passing bucket uses it: `pipe_material_type`'s
roughness goes through the DOUBLE set (Z_mepcat PASSES), the room's
identity through the STRING set (Z_content PASSES).  The defect is confined
to exactly the failing bucket, and to both of its PropertySetElement
constructors — which is why Z_palette alone fails and ZB_deep dies
partially.

### D2 — SECONDARY: three corpus-universal invariants violated [MEASURED]

A KEYED census over every `PropertySetElement` in the six samples + K4 + Y9
(`palette_fix/pal_census.json`, 300 param sets, 16 shapes — the pooled
linter cannot see these, see §Tooling):

* **(a) Order.** ALL 300 param sets are serialised in ASCENDING param-id
  order — `ascending: 300`, zero exceptions, in all three containers.  Ours
  emits DESCENDING (`dbl.sort(key=..., reverse=True)`); residue_b's inline
  comment `[VERIFIED corpus order]` (line 1465) is inverted.
* **(b) The ElementId set.** `m_pElementIdParams` is a PRESENT-empty
  `ParamValueSetElementId` (n=0, present=True) in all 16 shapes — 300/300;
  `m_pBoolParams` is null everywhere.  Ours emits `m_pElementIdParams:
  None`.  (`rvt.genesis.types.element_defaults(elemid_params={})` already
  produces the present-empty set; residue_b bypassed it.)
* **(c) The class enum.** `-1150464` = Revit's `StructuralAssetClass`
  (VERIFIED on all 17 Y9 structural slots: soil 1, plywood-generic 2,
  metals 3, concrete 4, wood 5, plastic 8; thermal 3 = `ThermalMaterial
  Type` Solid).  residue_b emitted 3 on EVERYTHING — its concrete assets
  shipped as class Metal.

### D3 — EXONERATED: the material sub-class [VERIFIED by prior certification]

The 10 surplus materials use `types.new_material` — the SAME constructor
Y7 landed on K4's 13 ACTIVE material slots.  Those 13 K4 slots ALL carried
appearance assets (`m_appearanceAssetId` = 171886 / 174486 / …) and 8 of
them carried `m_assetMap.m_sharedAssetIdMap` links (417 → 174487/174488,
519 → 174509/174510, 102856 → 174577/174578, 137433 → 174586/174566, …) to
structural + thermal property sets.  Y7 performed the IDENTICAL referential
surgery — appearance → −1, `sharedAssetIdMap` → [], param sets → null,
inline structural set → null — and Y9, which CONTAINS those 13, is
viewer-CERTIFIED.  ZB5's 10 surplus slots undergo the same operation with
the same constructor: 13 prior certified instances prove it.  (ZA_deep
additionally certifies materials that DO point at appearance assets — ours
— so BOTH linkage states load.)  P_pal_mat is the material control
regardless.

### The asset schema, decoded (what a correct constructor must reproduce)

Two REAL structural shapes coexist — this stream's shape census:

* **13 MODERN structural** (43–47 doubles, 10 strings, 4–5 ints): the
  legacy `-1140xxx` PHY block AND a unified `-1152301..-1152318` block,
  decoded HERE by within-object value matching (the two blocks coexist in
  the same objects) + physical-unit anchoring: `-1152301/302` = Young's
  modulus, `-1152303/304` Poisson, `-1152305` shear, `-1152306/307` thermal
  expansion, `-1152308..311` CONDUCTIVITY (steel 174586 = 170.6 = 52 W/mK ×
  3.28084 — the modern structural asset EMBEDS thermal scalars), `-1152312`
  specific heat, `-1152313` DENSITY in kg/ft³ (steel 222.85 = 7,870 kg/m³,
  copper 253.15 = 8,940, aluminum 76.74 = 2,710, concrete 68.17 = 2,407,
  wood 15.83 = 559 — textbook-exact), `-1152315/316` wood rupture / shear
  (the 47-dbl wood shape only), `-1152317` = E again.  10 strings incl.
  `-1152342` schema TOKEN (`'structural:concrete'`, `'C10100:structural:
  metal'`, …), `-1152340` = `'Autodesk'` source, `-1152337` = an
  asset-library GUID, `-1150466/465/481` name/subclass/description,
  `-1140416/417` = the `'Douglas Fir (West)'` / `'Standard'` wood-schema
  defaults carried by EVERY asset.
* **4 LEGACY structural** (194585 `'345 MPa'`, 1028776, 1177773, 1352644):
  15–26 doubles in the `-1140xxx` block only, 2–4 strings, no schema token —
  residue_b's constructor emitted THIS shape for all 17 slots (a real corpus
  shape, so the shape downgrade is itself unproven-fatal; v2 removes the
  question by reproducing each slot's OWN shape).
* **11 THERMAL** (10 × 11 doubles in `-1152308..-1152330`; 600685 × 12
  incl. legacy `-1140309`), 7 strings, 4 ints.

CRUCIAL: the SAME id `-1140309` holds DIFFERENT quantities per shape — in
the LEGACY shape the material's unit weight (194585 steel = 7,153.53 = 77
kN/m³ in N-flavour), but in the MODERN shape a leftover schema DEFAULT
(7.15101 on EVERY Y9 modern asset, steel / concrete / wood / soil alike =
default steel 7,850 kg/m³ × g in kN-flavour), the material's true density
living at `-1152313`.  Values must be placed BY THE SLOT'S OWN SHAPE, never
by a fixed layout.

## The fix (src/rvt/genesis/residue_b2.py)

`property_set_v2` builds each corrected `PropertySetElement` OVER THE
SLOT'S OWN DECODED SKELETON — a deep copy carrying the slot's exact
param-id set, its corpus ascending order and its present-empty ElementId
set / null Bool set (D2(a)/(b) satisfied BY CONSTRUCTION; `rvt.encode`
round-trips every decoded element record byte-exact) — and RE-VALUES every
param whose quantity our library states: the physical constants of the
substance from `residue_b.STRUCTURAL_ASSETS` / `THERMAL_ASSETS` (BOTH id
blocks: the legacy block per F6, the unified block per `BIP_UNIFIED`
above, PLUS the four `-1140xxx`-range DUPLICATES `-1140401/-1140412/
-1140413/-1140415` = E/ν/G/α that residue_b's `BIP_PHY` does not name —
found by this stream's leak audit, see finding 9), our identity strings,
our provenance (`-1152340` source cleared — no Autodesk token; `-1152337` =
`HOUSE_ASSET_LIBRARY_GUID`, a deterministic uuid5 in our namespace;
`-1152339` sustainability cleared).  Entries are re-valued in place,
NEVER re-paired → D1 satisfied by construction.  The `-1150464` class enum
and `-1152342` schema token stay the slot's own (D2(c) resolved by
CORRESPONDENCE): `structural_role_v2` / `thermal_role_v2` constrain the
role to the slot's authoritative class family (token → `StructuralAsset
Class` enum → own-name keywords), so class-correlated machinery
(wood/concrete-schema defaults, the shape flags, `-1140309`'s modern
default, `-1140320` = 1.66) transfers correctly.  The materials reuse the
certified `types.new_material` unchanged.

**Leak audit (the machinery proof):** for every one of the 28 slots, every
param the constructor KEEPS was tested for constancy across the same-shape
instances of the certified lineage (Y9 + K4 + rstbasic).  After the four
duplicates were forced, NO per-substance physical quantity remains in the
kept set: every kept param is (i) a deliberate schema-identity keep
(`-1152342` token, `-1150464` enum — family-enforced), (ii) a class-
correlated 0/1 shape flag (`-1152338 / -1152326 / -1152314 / -1152319 /
-1140322 / -1140323`), or (iii) a schema DEFAULT (the wood / concrete
sub-block defaults, `-1140317`, `-1140320` = 1.66, `-1140309` = 7.15101 on
every Y9 modern slot) — the defaults occurring in TWO library flavours
(imperial `731.52` vs metric `735532.7`), the slot's own flavour being what
is reproduced.  A same-class replacement therefore carries the same class
defaults its slot did; no sample-authored value survives.

Verified on all six shape variants in Y9 (legacy-16/15/26, modern-43/29/
47, thermal-11/12): schema-clean + byte-exact round trip; 0 swapped ints;
ascending; ElementId set present.  Z_palette_v2's provenance ledger
(`Z_palette_v2.json:build_info.revalue_traces`): 28 traces (13 modern, 10
thermal, 4 legacy, 1 thermal-uw), **28/28 class-family matches**, 740 of
1,073 param values OURS (69%), 333 reproduced machinery, D-law violations
0/0/0.
Spot-checks (v2 vs Y9): modern concrete 174481 → E 24.5 GPa = 7.468e9, ρ
2,400 kg/m³ = 67.96 kg/ft³, k 1.7 W/mK = 5.577, f'c 25 MPa = 7.62e6, enum 4
+ token + `-1140309` 7.15101 + `'Douglas Fir (West)'` KEPT, source cleared,
house GUID; legacy 194585 → E kept 6.096e10, unit weight 7,153.5 (legacy
N-flavour), `-1140320` KEPT at 1.66 (residue_b had invented 1.0); aerated
600685 → unit-weight FLAVOUR auto-selected by log-distance to the slot's own
magnitude (1,640 N-flavour vs parent 528).

### The integrity proofs of the probe set [VERIFIED]

* **Bisection reproduces the failing file:** `P_pal_mat` + `P_pal_struct` +
  `P_pal_thermal` regenerate ZB5's 38 changed seq-102 records
  **BYTE-FOR-BYTE (38/38)** — the diagnostic probes are true bisections of
  the failing artefact, not some other object set.
* **The swap-alone isolate is exact:** `P_pal_swapfix`'s materials are
  byte-identical to ZB5's (10/10); its 28 property sets equal ZB5's with
  ONLY the int keying corrected (28/28).
* **The laws on the outputs:** Z_palette_v2 = 0 swapped / 0 descending / 0
  null-ElementId; P_pal_swapfix = 0 swapped but 28 descending / 28 null (KEPT
  by design); P_pal_struct = 34 swapped entries (17 × 2); P_pal_thermal = 44
  (11 × 4).
* Every file: validator VALID (0 errors), structural proof clean, byte-delta
  assertion holds (only `Partitions/21` differs; ElemTable + ADocument
  byte-identical; only the 38/10/17/11 landed slots' records changed),
  four-registry coherent (1 save unit / 0 / 0 = family-free coherent),
  regdiff sample 6/6 registration-identical.

## New findings (evidence [V] = verified this session — merge into KNOWLEDGE.md)

1. **The palette FAIL is the int-param swap** [V, on-disk]: 78 swapped
   entries / 28 objects in ZB5_palette.rvt; positive `m_paramId` (3/0/1) =
   built-in ids masquerading as ParameterElement ElementIds → dangling typed
   refs to document-birth singletons; late-resolved (view tree built, then
   death).  Confined to the two palette constructors (the only
   `_int_param_set` call sites).
2. **`-1150464` = `StructuralAssetClass`** [V, all 17 Y9 slots]: 1 Basic,
   2 Generic, 3 Metal, 4 Concrete, 5 Wood, (6 Liquid, 7 Gas), 8 Plastic;
   thermal `-1150464` = `ThermalMaterialType` (3 Solid, 2 Liquid, 1 Gas).
   Corrects residue-B F6's "3 on every sampled asset" reading (its sample
   set was all metal + one legacy concrete = 4).
3. **The unified `-1152xxx` STRUCTURAL block, decoded** [V, 13 modern
   instances + unit anchoring]: `-1152301/302` E, `-1152303/304` ν,
   `-1152305` G, `-1152306/307` α, `-1152308..311` thermal CONDUCTIVITY,
   `-1152312` specific heat, `-1152313` DENSITY kg/ft³, `-1152315/316`
   wood rupture/shear, `-1152317` E, `-1152318` placeholder 3.048.  The
   modern structural asset carries the legacy PHY block AND this block AND
   embeds thermal scalars.
4. **`-1140309` is SHAPE-dependent** [V]: legacy shape = the material's
   unit weight (N-flavour); modern shape = a leftover schema default
   (7.15101 = default steel weight, constant across every Y9 modern asset
   regardless of material), true density at `-1152313`.  A fixed-layout
   constructor cannot be correct across shapes; only slot-shape-faithful
   emission is.
5. **Corpus-universal PropertySetElement laws** [V, 300 param sets / 16
   shapes / six samples + K4 + Y9]: every param set is ASCENDING by param
   id (300/300); `m_pElementIdParams` present-empty (300/300);
   `m_pBoolParams` null (300/300).
6. **The pooled linter is blind to keyed structure** [V]: `rvt.objlint`
   mines 79 rules from 244 `PropertySetElement` specimens and reports ZERO
   findings on the failing ZB5 objects (and on Y9's, and on ours) — a
   positionally-flattened, pooled miner cannot see a swapped
   `m_paramId`/`m_value` at a variable array position.  The KEYED census
   (`palette_fix/pal_census.py`, key = `m_paramId`) and the D1/D2 detectors
   (`swapped_int_entries`, `param_ids_ascending`) are the complementary
   instruments; the fixer's "per-KEY structural profile" lesson is
   confirmed again on a second class.
7. **residue_b's structural role picker mis-classes 5 of 17 slots** [V]:
   `structural_asset_role`'s `'cast'` token (meant for cast iron) matches
   `'Cast-in-Place'` concrete, and its hint concatenates the REFERRING
   material names — which the Y-ladder has already replaced with unrelated
   GEN materials (Y7's slot-fill landed our wood / CMU / earth into the
   sample's pipe-material slots; the Plastic slot's referrer is now
   `'GEN Steel, Structural'`, so it picked steel; the HDPE thermal slot
   likewise).  Result in ZB5: steel_345 landed on every concrete + plastic
   slot (174481, 174577, 600684, 1177773, 1407838).  NOT the crash (values,
   not structure) but it defeats class-faithful re-valuing; v2's role
   pickers read only the asset's OWN token / enum / name → 28/28 family
   matches.  General law: **in-place role hints must never read a slot's
   referrers' names — the ladder rewrites them.**
8. **The `sharedAssetIdMap` schema GUIDs** [V, 10 surplus + 13 K4
   materials]: `m_assetMap.m_sharedAssetIdMap` = {schema-GUID → property-
   set id}: `edc9f62d-48e4-4a9e-abb9-22c8664c012c` → the STRUCTURAL asset,
   `164800ec-0722-4b26-a235-04ffc53660d5` → the THERMAL asset (fixed
   Autodesk schema GUIDs); legacy materials additionally carry
   `m_structuralPropertySetId` (194585 is shared by 509467 AND 1168302).
   After a material rung the property sets are ORPHANED (nothing references
   them) — tolerated (R5/R9); a coherence follow-up, not a load risk.
9. **Four undocumented per-material DUPLICATES in the modern shape** [V,
   value-equal within all 13 Y9 modern assets across six materials]:
   `-1140401` == `-1140300` (E), `-1140412` == `-1140303` (ν), `-1140413`
   == `-1140306` (G), `-1140415` == `-1140310` (α).  A constructor covering
   only `BIP_PHY` states OUR E at `-1140300` while `-1140401` keeps the
   SAMPLE's — an asset with two different Young's moduli and a leaked
   sample value.  Caught by the leak audit BEFORE upload (adversarial
   self-review of the built v2, then a lineage-constancy sweep over every
   kept param); forced in `structural_value_map`; pinned by a test.  The
   general instrument: after any re-valuing constructor is built, sweep
   every KEPT param for cross-slot constancy — a per-material value that
   varies is a leak the field-diff of one slot will not show.

## The residue_b.py diff (NOT applied — outside this territory; owner applies)

The corrected constructors live in `residue_b2.py` (this territory) and
supersede `structural_asset` / `thermal_asset` for the palette rung.  The
MINIMAL upstream diff to residue_b.py that would make its two constructors
lawful (for reference; v2's shape-faithful approach is preferred, since a
fixed-layout constructor cannot satisfy finding 4):

    --- src/rvt/genesis/residue_b.py  (structural_asset)
    @@ ~1350
    -    dbl.sort(key=lambda t: t[1], reverse=True)
    +    dbl.sort(key=lambda t: t[1])                  # corpus is ASCENDING (300/300)
    -    ints = [(PROPSET_ASSET_CLASS_OBSERVED, BIP_PHY["material_class_int"]),
    -            (1 if spec.get("lightweight") else 0, BIP_PHY["behavior_int"])]
    +    ints = [(_asset_class_enum(spec), BIP_PHY["material_class_int"]),   # 3 metal/4 concrete/5 wood
    +            (1 if spec.get("lightweight") else 0, BIP_PHY["behavior_int"])]
    @@ ~1360
    -        "m_pIntParams": _int_param_set([(v, k) for v, k in ints]),
    +        "m_pIntParams": _int_param_set([(k, v) for v, k in ints]),      # THE D1 FIX: (id, value)
    -        "m_pBoolParams": None, "m_pElementIdParams": None,
    +        "m_pBoolParams": None,
    +        "m_pElementIdParams": _ptr("ParamValueSetElementId", {"m_paramSet": []}),  # present-EMPTY

    --- src/rvt/genesis/residue_b.py  (thermal_asset)
    @@ ~1465
    -    dbl.sort(key=lambda t: t[1], reverse=True)   # -1152308 first .. -1152330 last [VERIFIED corpus order]
    +    dbl.sort(key=lambda t: t[1])                 # ASCENDING: -1152330 first .. -1152308 last (300/300)
    @@ ~1481
    -        "m_pIntParams": _int_param_set([(v, k) for v, k in ints]),
    +        "m_pIntParams": _int_param_set([(k, v) for v, k in ints]),      # THE D1 FIX
    -        "m_pBoolParams": None, "m_pElementIdParams": None,
    +        "m_pBoolParams": None,
    +        "m_pElementIdParams": _ptr("ParamValueSetElementId", {"m_paramSet": []}),

    --- src/rvt/genesis/residue_b.py  (structural_asset dbl list, ~1328)
    +    # the -1140xxx-range DUPLICATES of E / nu / G / alpha (finding 9) --
    +    # state them or the object carries two moduli:
    +    for pid in (-1140401,):                 dbl.append((E, pid))
    +    for pid in (-1140412,):                 dbl.append((nu, pid))
    +    for pid in (-1140413,):                 dbl.append((G, pid))
    +    for pid in (-1140415,):                 dbl.append((alpha, pid))
    NB: even so, a FIXED-LAYOUT constructor cannot be correct across the
    corpus's two coexisting structural shapes (finding 4: -1140309 changes
    meaning per shape); the shape-faithful re-valuing in residue_b2 is the
    real fix and supersedes structural_asset / thermal_asset.

    --- src/rvt/genesis/residue_b.py  (structural_asset_role, ~1525)
    Check the CONCRETE tokens BEFORE the metal tokens (drop 'cast' from the
    metal list or place ("concrete", "precast", "cast-in-place", "aci") first);
    and in build_ZB5_palette stop concatenating `_mat_name(ctx, r)` of the
    slot's referrers into the hint -- those names were rewritten by Y7.

    --- src/rvt/genesis/residue_b.py  (build_ZB5_palette docstring, ~2390)
    "The THERMAL assets (type 2, 11 slots) are LEFT as residue" -- STALE:
    the code lands all 11.  Correct the docstring.

## Proposed hooks for files OUTSIDE this territory (NOT applied)

* **`src/rvt/objlint.py`** — add a KEYED param-set profile: for classes
  carrying `ParamValueSet*` containers, mine per `m_paramId` (never by array
  position): the id sign law (built-in ids negative), the per-(class, shape,
  id) value constancy, the container order law (ascending) and the
  present-empty ElementId set.  The pooled positional miner reports zero on
  the failing objects (finding 6).
* **`docs/coverage/viewer-certified.json`** (orchestrator) — record the
  seven verdicts as they read out; on Z_palette_v2 PASS the palette bucket
  joins the seven clean B buckets and ZAB composition can proceed.
* **KNOWLEDGE.md owner** — merge findings 1–8 (the swap signature and its
  late-death mode, the StructuralAssetClass enum, the unified structural
  block, the shape-dependent `-1140309`, the three corpus laws, the linter
  blind spot, the referrer-name role-hint law, the asset schema GUIDs).
* **`tools/sync_plugin.py`** — this stream ADDS `src/rvt/genesis/
  residue_b2.py` (a genesis constructor module); run after framework
  changes if the plugin bundle should carry it.

## Open questions (need the viewer / a decision)

* The seven verdicts, in the upload order above (control first).  Reading:
  Z_palette_v2 PASS = defect closed (the singles are corroboration).
  P_pal_swapfix decides whether D1 ALONE was the whole defect (PASS) or a
  D2 shape correction carried by v2 is also load-bearing (FAIL); the
  P_pal_struct / P_pal_thermal FAILs (predicted) name the sub-class on the
  record.
* On Z_palette_v2 PASS: compose Y9 + ZA_deep's Group-A layer + Group B's
  seven clean buckets + the corrected palette → the ZAB deep file (replay
  the correspondence sets in one `substitute_elements` call; all pure
  in-place, ids preserved).
* The 28 property sets are ORPHANED after any material rung (finding 8) —
  a later coherence rung may either re-wire our materials' asset maps to our
  property sets or delete the property sets with their materials; every
  reference is legal as it stands.
* Whether residue_b's role-picker fix (finding 7) is applied upstream or
  the palette rung is simply re-pointed at residue_b2's builder (this
  module's `build_pal_v2` is drop-in as ZB5's `build`).

## Verification

* `.venv/bin/python -m rvt.genesis.residue_b2` → 7 files, ALL `VALID`;
  `--diagnose` → the ZB5 on-disk swap census (78 / 28 / 28 / 28).
* `tools/rvt_validate.py --quiet experiments/genesis/subst_k4/palette_fix/*.rvt`
  → 8 × `OK errors=0 warnings=1` (control included).
* `.venv/bin/python -m pytest tests/test_residue_b2.py -q` → **32 passed**
  (the diagnosis pinned on the failing file and on the original constructors
  at the source; the corrected helpers incl. positive-id refusal; the
  corrected constructor over all six shape variants — byte-exact round
  trip, laws on the output, our provenance, our values landing; the
  one-value-per-quantity law across the duplicate ids (finding 9); the
  class-constrained pairing 28/28; the residue-B role-picker defect pinned;
  the material constructor's certified shape; the bisection-reproduces-
  ZB5 and swapfix-equals-ZB5-minus-swap proofs; the manifest contract).
* Determinism: rebuilding a probe reproduces its bytes exactly (md5 equal)
  — the house GUID is a uuid5, the temporary-id band is fixed by the base's
  watermark, the pairing is order-stable.
* Full suite: see BRANCH STATE.

## BRANCH STATE

No VCS (plain directory).  New, uncommitted files, this stream's
territory only: `src/rvt/genesis/residue_b2.py` (the corrected
constructors + role pickers + the D1/D2 instruments + probe driver),
`tests/test_residue_b2.py` (32 pass), `docs/inbox/genesis-palette-fix.md`
(this file), and under `experiments/genesis/subst_k4/palette_fix/`:
`Z_palette_v2.rvt` + `.json`, `P_pal_mat / P_pal_struct / P_pal_thermal /
P_pal_swapfix / P_pal_struct_v2 / P_pal_thermal_v2 .rvt` + `.json`,
`CTRL_Y9_base.rvt` (md5-identical to Y9), `probes.json`, and the census
instrument `pal_census.py` + its output `pal_census.json`.  Every emitted
`.rvt` = validator VALID (0 errors), structural proof clean, byte-delta
assertion holding (only the landed slots' seq-102 records changed;
`Global/Latest` + `Global/ElemTable` byte-identical to Y9), four-registry
coherent.  NO existing `src/rvt/*.py`, tool, test or `.rvt` was edited
(residue_b.py's fix is written above as an exact diff for its owner);
`Y9.rvt`, `ZB5_palette.rvt` and every file this stream must not touch keep
their pre-session mtimes.  Full suite this session (`.venv/bin/python -m
pytest tests/ -q --ignore=tests/oracle`): **1122 passed, 3 failed** (1,125
tests, 17:06) — this stream's 32 tests are among the 1122; NONE of the 3
failures is caused by this stream's code:
  * `tests/test_provenance.py::test_G0_resource_refs_are_counted` and
    `::test_G0_identity_dit_usernames_still_leak` — the two PRE-EXISTING,
    other-stream failures every recent record lists (stale assertions
    pinning the pre-genesis-2 G0's defects);
  * `tests/test_plugin_sync.py::test_plugin_is_in_sync_with_source` — the
    expected new-module signal: its drift list names `residue_b2.py` (this
    stream) ALONGSIDE the parallel streams' unsynced modules
    (`residue_a2.py`, four `src/rvt/ifc/*`); resolved by the owner's standard
    `python tools/sync_plugin.py` step after the parallel streams merge (it
    writes `plugin/` and rebuilds `rev-revit.zip` — outside this territory —
    so this stream documents it rather than running it mid-fan-out).
NB: the suite ran DURING a live fan-out (three sibling streams editing
`src/rvt/genesis/residue_a2.py`, `src/rvt/ifc/*` and their tests
concurrently — see the mtime audit), so their test outcomes reflect
in-flux code, not this stream's.
STOPPED AT READY — the seven probes + control await the orchestrator's
viewer batch (predicted verdicts recorded per probe).
