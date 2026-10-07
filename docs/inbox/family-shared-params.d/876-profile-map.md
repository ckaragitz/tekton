# 876 (part A) — a profile map links a library's size parameters to the family's own

Stream **family-shared-params** (tech-lead session, 2026-10-02). Refs #876: DONE 1, 3, 4 and 5. DONE 2, the map *proposed* from the user's own families, is part B (`876-map-proposal.md`), in the same PR (#971).

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

`tests/test_profile_map_876.py`: **13 passed** as first shipped; **18** after the #971 review rounds (see below). Synthetic profile, made-up names and GUIDs. The cases:
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

## #971 review round 1 (🛑): every link announced is one the family carries

- **The finding:** `_link` accepted links that the formula step then refused, while the "linked by … follows every type" note announced them.
  - The cases: a type library parameter onto one of our *instance* parameters, and an integer on either side.
  - `_link` now makes those refusals itself, up front, with the reason.
  - `settle_formula_provenance` rebuilds the "linked by" line, per map, from the tags that still carry a `link`, the same way the library line is rebuilt. A link the finalize step refuses for any other reason is no longer announced, and the line says `none written` when nothing remains.
- **A refused link keeps the library's convention.** Before, a map typo blanked the parameter. The note now says `the library's convention is written instead`.
- **`_spec_kind`** follows `skeleton._canonical_spec`'s version rule. A target with no spec is read as a length, as `skeleton._formula_spec` reads it.
- **The proposal tool:**
  - Primary-per-axis now ranks by the families labelling *that* axis, not by every family the parameter labels.
  - A family whose labels run equally along two axes votes "mixed" and counts for no axis. Before, the first-inserted axis won.
  - Rerun on the owner's library (counts only): still **3 proposed** for electrical equipment.
- **Tests:** a type→instance link and an integer link refused with no contradicting "NOT written" note; the linked line rebuilt; a refused link keeping the convention; axis ranking by own votes; a mixed family.
  - The test helper now copies the module's parameter table. Before, an extended profile leaked between tests, and the new tests showed it.

## #971 review round 2 (🟡), carried in the #877 PR

- **A refused link's fallback note** now reads "the library's convention is used instead (a formula is checked when the family is finalized)". A convention formula that finalize then refuses is named in the "not written" note, so the first note no longer claims it was written.
- **The "linked by" line is matched by its whole head, per map source** (`_linked_head`), no longer by splitting at the first `"): "`. A map file named `odd): name.json` rebuilds correctly; there is a test.
- **`make_family`** says so on stderr when `--profile-map`, `--profile-values` or `--profile-family` is given without `--param-profile`. Before, the flag was ignored silently; there is a test.
- **The proposal tool:** families split evenly between two axes count as "mixed" and nothing is proposed, below the default share too (`--min-share 0.5`).
- **Test counts:** `test_profile_map_876.py` 18 and `test_profile_map_from_rfa_876.py` 18 collected at #1029's first head. `test_profile_map_876.py` collects 21 after the #1029 and #1031 review rounds. The additions are the replaced-formula linked line (#1029), the profile name holding the separator, and the library line whose parameters all lost their tags (both #1031).

## #962 review nits carried here

- **Recorded:** what #870 changed for profile users. A library **string constant**, such as `"Box"`, is now written as the formula the library stores. Before, it was flattened to a value. As a formula, the parameter is **formula-driven in Revit**: it cannot be edited per type until the formula is cleared, exactly as in the library's own families.
  - The reviewer's related point predates #870 and is filed as #968: a one-family constant formula, such as a rating in quotes, is carried as structure under `family=` mirroring.
- **Recorded:** #870 extended past the territory its issue named, to `param_profile.py`, the `_formula_spec` helper in `skeleton.py`, and the 875/886 tests. Each follows from the change, and #870's record describes them.
- `("")`, like `""`, is refused as Revit's "no formula": parentheses are unwrapped before the check.
- A caption that *starts* with `"` cannot be named in a formula, because the quote opens a text constant. This is pinned by a test and stated in `docs/writer/formulas.md`.
- Two docstrings that still described text formulas as unwritten are updated: `formula.unparse` and the `param_profile.CLASS_SPEC` comment.
- `test_famgen_formula_850`'s "Pick" case is flipped to a positive test rather than dropped.

## BRANCH STATE

- Files:
  - `src/rvt/famgen/param_profile.py`, `src/rvt/famgen/formula.py` (`is_spellable`), `tools/make_family.py` (`--profile-map`), and their plugin mirrors;
  - `tests/test_profile_map_876.py` and the drop-in `tests/ci_shard.d/876-profile-map.txt`;
  - this record.
- Shipped on merge; nothing is staged for the viewer.
