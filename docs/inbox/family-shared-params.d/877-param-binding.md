# 877 — a family parameter drives a solid's material and visibility

Stream **family-shared-params** (tech-lead session, 2026-10-02). Closes #877: DONE 1–3, with 4 filed and 5 stated.

## Census (DONE 1): the owner's reference library, private, counts only

368 of 421 families carry `FamilyParametrizedElemParamsCell` associations. All 28,126 entries have `m_geomTag` -1 and `m_bIsSymbol` False.

**By target and property:**

| target | property | count |
|---|---|---|
| nested `FamilyInstance` | Visible `-1006205` | 4,266 |
| nested `FamilyInstance` | nested family parameters (positive ids) | the rest of 25,002 |
| `ExtrusionElem` | Visible `-1006205` | 764 |
| `ExtrusionElem` | Material `-1002107` | 367 |
| `CurveElem` | Visible | 396 |
| `Text3dElem` | Visible | 308 |
| `FamilyGeomCombination` | Visible | 170 |
| `FamilyGeomCombination` | Material | 154 |
| `ConnectorElem` | -1133401 / -1133403 / -1133404 / -1133415 | 105 / 123 / 123 / 95 |

`SweepElem`, `BlendElem` and `RevolutionElem` carry both Visible and Material.

**By driving parameter class:**
- Visible: Yes/No, 5,964 of 5,964.
- Material: `ParamDefMaterialBrowse`, 661.

**Law, sampled on every 3rd family:**
- A bound solid lists the parameter among its header's **deletion parents**, for both properties, on every sampled solid (271 + 154 + 36 + 24 + 12 + 8).
- A **material**-bound solid's own `m_materialId` **equals the parameter's current value**: 226 of 226.

## What changed (DONE 2)

- **New `src/rvt/famgen/param_binding.py`.**
  - `bind(element, param, prop)` writes the library's encoding. It adds the entry to the element's parametrized-params cell, creating the cell before the `PatternHelper` when absent. All of an element's bindings go in one cell, and a second binding of the same property replaces the first. It also adds the parameter to the element's deletion parents.
  - `bind_visibility(form, yes_no_param)` and `bind_material(form, material_param, material_id)` act on a form's single solid. Each refuses the wrong kind of parameter. `bind_material` also sets the solid's `m_materialId`.
  - `add_material_parameter(doc, name, material_id)` adds the parameter.
  - `bound(element)` reads bindings back.
- **`equipment_clearance.bind_visibility`** (#690) now delegates to `param_binding.bind`. The built element contents of the transformer, panelboard and fan coil are identical before and after (sha256 over every element's header and object).

## Evidence (DONE 3)

`tests/test_param_binding_877.py`: **5 passed**, under the #707 release-leak guard because the 2025 build enters a release context.
- **The encoding:** both bindings sit in one cell before the `PatternHelper`, with the exact entry shape, the deletion parents and `m_materialId`.
- **Rebinding** does not duplicate.
- **Wrong-kind refusals.**
- **A generic box** with a material parameter driving its solid and a Yes/No driving its visibility, built and written for **2026 and 2025**: VALID with 0 errors and provenance ok. It **reads back** from the written file: both entries, `m_materialId`, and the parameter rows (`m_elemId` = the material, `m_int` 1).

## Also in this PR

The 🟡 nits of #971's second review round, recorded in `876-profile-map.md`.

## Open

- **DONE 4:** nested-family parameter passing (positive property ids on a nested `FamilyInstance`; the census's largest group) is not filed again. #917, closed, built it in `rvt.famgen.nest`: the `{host parameter, twin, geomTag -1, isSymbol False}` association on the nested instance, written by the #913 constraint program. The broader nesting work is #852.
- **Product adoption:** giving the generated equipment a body-material parameter bound to its enclosure is a separate step that changes product output. It is left until a desktop verdict exists.

## Not claimed (DONE 5)

That Revit honours the bindings (the solid hides with the flag, its material follows the parameter) needs a desktop verdict (hard rule 4; S-2026-08-11-d's visibility surface). The visibility binding's own desktop question is #690.

## BRANCH STATE

- Files:
  - `src/rvt/famgen/param_binding.py` (new) and `src/rvt/famgen/equipment_clearance.py`, with their plugin mirrors;
  - `tests/test_param_binding_877.py` and the drop-in `tests/ci_shard.d/877-param-binding.txt`;
  - this record.
- Shipped on merge; nothing is staged.
