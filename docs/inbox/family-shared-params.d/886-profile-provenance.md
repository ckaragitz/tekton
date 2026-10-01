# 886 — profile provenance stays truthful; the formula reader never spells a different tree

Stream **family-shared-params** (tech-lead session, 2026-10-01). It carries the nits from #889's second independent review (the #875 PR) under the #886 umbrella.

## What changed

1. **A refused library formula carries no library provenance.**
   - `param_profile.settle_formula_provenance` runs in the finalize step after the formulas are written.
   - A parameter tagged "by formula" whose formula was refused loses its `refs["provenance"]`.
   - It also leaves the "provenance library (…)" line, and a note names it.
   - It is idempotent and wrapped, so a note's accuracy never blocks delivery.
2. **A Yes/No convention of 0 (No) is reported.** It equals the blank row byte for byte, but the library said so, so it is tagged and counted.
3. **`formula.unparse_checked(tree, names, table)`** parses the spelling back against the family's own name table, and refuses a spelling that reads back as a different tree.
   - The case: a caption that holds two others and an operator, `A - B` beside `A` and `B`.
   - The extractor builds that table per family, with each caption's own spec. A caption defined twice gives the family's own id.
   - A spelling the parser refuses on its unit rules cannot be checked, so it is kept. The writer refuses it by the same rules, so it is never written wrong.
4. **A tree deeper than the recursion limit gives None** from `unparse`. Before, it raised `RecursionError`, which the extractor's per-file guard turned into a dropped family.
5. **Docstrings.** `apply` now describes conventions and provenance, and `formula._subs` reads function arguments in one place.

## Evidence

- `tests/test_param_profile_886.py` (synthetic): 4 passed. With the param-profile, extractor and formula suites: 164 passed.
- **The owner's library, private run (counts only):** re-extracting with the checked spelling leaves the unread count at 89 of 2,637 own-row formulas. Not one library formula spells into a different tree.

## BRANCH STATE

Branch `claude/eager-franklin-xgzgda`, from main after #889.
- Written:
  - `src/rvt/famgen/formula.py`, `src/rvt/famgen/param_profile.py`, `src/rvt/famgen/skeleton.py` (the settle call), `tools/shared_params_from_rfa.py`;
  - `tests/test_param_profile_886.py` and its `tests/ci_shard.d/` drop-in;
  - this fragment, and the `plugin/lib` mirrors.
- Staged: nothing.
- No certification claim.
