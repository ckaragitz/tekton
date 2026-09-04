# 769 — an IFC's own property sets reach the family as real parameters

Refs #769. Stream: `ifc-assembly-rfa`.

## The report

The owner modelled a pad-mounted transformer in Claude Design, attached
`Pset_TransformerClearances` to it, converted it, and asked to make sure the
parameters came through. They had not. The delivered family carried eight
parameters — `Width`, `Depth`, `Height`, `Material`, `Weight`, `Finish`,
`Part Numbers`, `Source IFC` — and **none of the ten the author had specified**.

Worse than the loss: nothing said it had happened. The route read those psets (it
uses them for the bill of materials), took what it wanted, and dropped the rest
silently. A caller had no way to know their own input had been discarded.

## The fix

`rvt/ifc/pset_params.py` collects every single-value property across the IFC's
products and returns typed parameter declarations:

* **spec by measure class** — `IfcLengthMeasure` → a length parameter,
  `IfcReal`/`IfcInteger`/etc → a number, anything else text. A length reads as a
  length in Revit rather than a bare number.
* **value in the file's own unit** — converted to internal feet via the IFC's
  `IfcUnitAssignment`, never assumed to be metres. An IFC in millimetres would
  otherwise have put a 36-inch clearance 3000 feet away.
* **source recorded** — pset, product, IFC type and raw value per parameter, all
  at tier `given`: the caller stated it, we carry it verbatim. Never a catalog
  `fact`, never a manufacturer claim (steer S-2026-08-11-c).

`factory` grew `numeric_params` symmetric to the existing `text_params`, and the
assembly lane in `router` passes what it collected and reports it as a caveat.

**Name collisions are skipped and named, not silently resolved.** A pset property
called `Width` would otherwise overwrite the overall bounding-box `Width` the
geometry depends on. Reserved names are refused with the reason, so the loss can
never be silent a second time.

## Evidence — the owner's file

```
before:  8 params  (none of the author's)
after : 18 params  (8 + all 10 of Pset_TransformerClearances)

TopClearance    36.0 in     FrontClearance  120.0 in
BodyWidth       62.0 in     BodyDepth        48.0 in    BodyHeight  55.0 in
PadWidth        84.0 in     PadDepth         72.0 in    PadHeight    6.0 in
TopClearance in / FrontClearance in -> numbers, NOT scaled as lengths
```

Every converted length matches the file's own `_in` companion property exactly,
which is the check that proves the unit conversion rather than asserting it.

Delivered family: VALID (0 errors), constraint graph coherent.

## Two reader traps, recorded

`steplite` entities expose `id` and `is_a` as **methods**, not attributes. Reading
them as attributes yields the bound method — which silently poisoned a dict keyed
on `id` (every pset landed under the same key) and made every type check fall
through to text. `_eid()` and `_type_name()` handle both shapes, since
`ifcopenshell` exposes them differently.

## BRANCH STATE

**Files written**
- `src/rvt/ifc/pset_params.py` — new: `collect`, `summarise`, unit resolution.
- `src/rvt/famgen/factory.py` — `numeric_params` on the multi-part builder and
  `make_generic_model`; authored with the right storage class and set on the type row.
- `src/rvt/frontdoor/router.py` — the assembly lane collects and passes them, and
  reports the carry-through (and any skip) as a caveat.
- `tests/test_ifc_pset_params.py` (8 tests) + `tests/ci_shard.d/769-ifc-pset-params.txt`.

**Gates**
- `tests/test_ifc_pset_params.py` — 8 passed.
- with `tests/test_famgen_factory.py` — passed.
- `tools/sync_plugin.py` — deny-audit clean, validation passed.
- End-to-end on the owner's IFC: 10/10 parameters, correct units, VALID 0 errors.

**Not done:** the carried parameters are values on the type, not geometry drivers —
`TopClearance` does not move anything. Driving them needs the #689 spine wired into
the factories, which is a separate piece.

## Review round 1 (#771, head be4b6e1) — the text-value blocker

The independent reviewer measured the exact failure class this issue exists to
fix, one layer down: `factory`'s type-row loop did `float(v)` for every carried
value, so a `("text", "ONAN")` entry raised, `except: pass` swallowed it, and
the TEXT parameter kept `add_family_parameter`'s numeric `0.0` — while
`summarise()` told the user every value was carried. Fixed:

* text-spec params are authored via `_text` under **identity** (not `_num`
  under dimensions) and their row value stored verbatim as `str(v)`;
* `_length_to_ft` now delegates to `steplite.calculate_unit_scale` (the full
  conversion-factor walk) instead of a name-sniffing re-implementation, keeping
  the metres-assumed note for files that declare no length unit;
* the conversion is CI-proven by a tracked fixture `tests/fixtures/pset_mm_unit.ifc`
  (914.4 mm → 3.0 ft, text/boolean carried, reserved name skipped) — the prior
  conversion test self-skipped without the untracked transformer IFC.

Gates after the fix: `tests/test_ifc_pset_params.py` **10 passed** (was 7+1skip);
`tests/test_famgen_standards.py` + `tests/test_edit_family_size_668.py`
**109 passed**; sync --check clean.
