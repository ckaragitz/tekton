# Donor-free generation + arbitrary geometry (issue #498)

Owner steer: "no more donor referencing ... when i go to claude design and
ask it to build me a 3d object you should be able to fully convert that to
a rfa file with no issues."

## State found (after #480)

* `ifc -> rfa` and `prompt -> rfa` already ran DONOR-FREE and produced
  law-complete families (audited: settings singletons, dimension style,
  classification tables, browser orgs, both plans + 3D view, drive dims /
  alignments / planes, solver records, 133/133 manager slots, all four
  registries).  #480 was the fix that made this true; nothing else was
  required for the catalog kinds.
* The stale part was the MESSAGING: `standalone_family_write` still emitted
  a caveat claiming "all registries ship empty ... supply $RVT_FAMILY_DONOR",
  and `tekton_env.family_donor_status` documented "when missing the skill
  asks the user for one .rfa".  Both are now false and both are corrected.

## Changed

1. **No implicit donor.** `FamilyProduct.write` no longer reads
   `$RVT_FAMILY_DONOR`; a donor is only an explicit
   `standalone_family_write(family_donor=...)` argument for format-parity
   experiments.  The caveat text now states the constructive path IS the
   supported one (desktop-verified on two machines).
2. **Arbitrary geometry.** `polygon_profile()` accepts any closed ring
   (N >= 3, either winding, auto-normalised CCW, repeated closing point
   dropped); `RectProfile.width/depth` are now bounding-box derived so they
   stay meaningful for a non-rectangular ring (identical for rectangles).
   `add_polygon_form()` + `make_generic_model()` compose a Generic Model
   family from vertices + height (or width/depth + height), dimensions
   flagged GIVEN with their source -- never presented as catalog facts.
3. `prism_form` was already N-gon generic and the round-18 solver law
   (coincidence-detected corner joins) generalises: measured 6 curves /
   6 solver records / 12 constraints on a CONCAVE L-shape and on a hexagon.

## Known gap (recorded, not hidden)

The cached six-face B-rep (`solid_box_brep`) is the rectangular case only,
so a non-rectangular profile ships the REGENERATION rep (Revit rebuilds the
solid from sketch + depth on open).  Generalising the cached rep to N-gons
is issue #499.  Desktop verdict pending on the L-shape / hexagon probes.

Luminaires remain unreachable from a free-text room prompt (recognised but
not built -- pre-existing issue #150); they ARE generatable via the famspec
route (`route run --rfa troffer.famspec.json --output rfa`, verified).
