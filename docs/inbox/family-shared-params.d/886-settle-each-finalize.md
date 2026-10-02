# 886 — formula provenance settled afresh on every finalize; `_shape` compares values

Stream **family-shared-params** (tech-lead session, 2026-10-02). Refs #886. Carries the review nits of #896, posted on #886, items 1–4.

## What changed

- **`param_profile.settle_formula_provenance` recomputes from the claim; it does not only remove tags.**
  - `apply` records each formula's claim in `refs["formula_provenance"]`: its tag, and the formula text it was made for.
  - Every finalize then sets the tag from that claim. Written means tagged. Refused means untagged and named in a note.
  - The `provenance library (…)` line is rebuilt from the tags.
  - The "… formulas not written" notes are replaced, not appended.
  - So a formula refused on one finalize and written on a later one is tagged and listed again. Settling twice says each thing once.
  - A formula replaced after the profile filled it loses the profile's claim and its tag.
- **A given formula is tagged `by: formula` too** (`{"tier": "given", …, "by": "formula"|"value"}`). A refused one loses its `given` tag, and a "given formulas not written" note names it.
- **`formula._shape` no longer reports false differences**, so `unparse_checked` no longer reports false `formula_unread` rows. Number constants compare by value:
  - an int equals the float;
  - -0.0 equals 0.0;
  - `-(2)` equals a stored `-2.0`, found through parentheses and leading minus signs.

  Parameters compare by integer id, so a string `m_paramId` matches. A different constant is still a different tree.
- **The `unparse_checked` docstring is narrowed** to what the fallback covers: a text that cannot be parsed back, whether refused on the unit rules, deeper than `MAX_DEPTH`, or past the recursion limit.

Not done here, and left on #886: item 5 (the extractor imports the private `skeleton._canonical_spec`) and item 6 (a re-finalize duplicates `_apply_formulas`' own "NOT written" notes). Both need `skeleton.py`, which the #913 constraint program is changing (clkaragitz). They are left for its owner rather than raced.

## Also in this PR — stream equipment-detail (the #960 review nits)

- `equipment_common.positive_finite` now also gives the unit message for a number too large for a float (`10**400`; it used to escape as `OverflowError`).
- It now refuses numpy's bool like Python's (`np.True_` used to pass as 1.0).
- `fan_powered` reuses the float that `positive_finite` returns instead of converting twice.

## Evidence

- `tests/test_param_profile_886.py`, `tests/test_fan_powered_895.py`, `tests/test_fan_coil_893.py` and `tests/test_equipment_drives_913.py` run together: **186 passed**.
  - Of the new #886 cases, 7 fail on main's source and pass here.
- The formula and profile suites (`test_famgen_formula_850`, `test_param_profile_{866,875,886}`, `test_shared_params_from_rfa_866`): **164 passed** before the equipment nits were added, with no change from them.
- **Owner's library, counts only (rule 6).** `tools/shared_params_from_rfa.py --profile` over the private reference corpus gives a **byte-identical profile** on main and on this branch: 2,548 formulas, 89 unread.
  - The false-difference shapes do not occur in that library. The fix is conservative-to-exact, never a different spelling.
- `tools/sync_plugin.py --check`: clean.

## BRANCH STATE

- Files:
  - `src/rvt/famgen/{formula,param_profile,equipment_common,fan_powered}.py` and their `plugin/lib` mirrors;
  - `tests/test_param_profile_886.py`, `tests/test_fan_powered_895.py`;
  - this record.
- Nothing is staged for the viewer; there is no certification claim (hard rule 4).
