# 876 (part A) — a profile map links a library's size parameters to the family's own

Stream **family-shared-params** (tech-lead session, 2026-10-02). Refs #876: DONE 1, 3, 4 and 5. DONE 2, the map *proposed* from the user's own families, is part B, a separate PR.

## What changed

- **`ProfileRequest(links=…)`** and **`tools/make_family.py --profile-map MAP.json`**. A link maps a profile parameter to the generated family's own parameter it stands for, keyed by GUID or name: `{"<library width GUID>": "Width"}`.
  - The link is written as a **formula naming our parameter**, through `rvt.famgen.formula` (#850). The library parameter therefore carries our value on every type row, and Revit's formula holds them together.
  - It is tagged `{"tier": "given", "source": "the profile map '…'", "by": "formula", "link": "Width"}`.
  - One note lists every link (`linked by the profile map '…' to the family's own parameters …`).
  - A link the finalize step still refuses loses its tag; `settle_formula_provenance` handles that, as for any given formula.
- **A link that cannot hold is refused and said (DONE 3), never coerced:**
  - the family has no such parameter;
  - the name cannot be spelled in a formula;
  - the entry is not a name;
  - another kind of value: a length onto a number, a number onto a length, a length onto a text. Spec kinds are compared without their schema version, so a library `length-2.0.0` links to our `length-1.0.0`;
  - a material on either side.
- **A caller's value for the same parameter wins over the map, said.** A map entry for a parameter the profile did not select is named in a note.
- **`formula.is_spellable(name)`** is the public form of the spelling check, so `param_profile` imports no private name.

## Evidence (DONE 4)

`tests/test_profile_map_876.py`: **13 passed**. Synthetic profile, made-up names and GUIDs. The cases:
- **A link follows every type.** With a second type of Width 3.25 ft, the library width reads 3.25 there and the first type's width in the first. Width and height are both linked. An unmapped size parameter stays blank, with no tree.
- **Six refusals**, each with its exact note: number←length, text←length, length←number, no such parameter, not a name, material.
- **A given value wins:** the constant is written, with no tree, and the note says so.
- **An unselected map entry** is named in a note.
- **The linked transformer validates:** VALID with 0 errors and provenance ok, for 2026 and 2025.
- **A placed linked instance validates:** prompt-built 2026 room, loaded and placed, validator 0 errors.
- **The CLI** (`--profile-map map.json`) writes the parameter-reference tree, and the printed report names the map.

The tests fail on main, which has no `links`.

## Not claimed (DONE 5)

The link is a formula, so the library parameter *reports* our size. That Revit re-evaluates it, and that labelling our own dimensions with the shared parameter would let it *drive* them, both need desktop verdicts (hard rule 4). Labelling is a later item.

## BRANCH STATE

- Files:
  - `src/rvt/famgen/param_profile.py`, `src/rvt/famgen/formula.py` (`is_spellable`), `tools/make_family.py` (`--profile-map`), and their plugin mirrors;
  - `tests/test_profile_map_876.py` and the drop-in `tests/ci_shard.d/876-profile-map.txt`;
  - this record.
- Shipped on merge; nothing is staged for the viewer.
