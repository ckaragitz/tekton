# 875 — a library's value conventions carried into the families we generate

Stream **family-shared-params** (fragment). Issue #875, from steer #873: *"understanding each and every parameter … and building out families that way"*. Owner request in session: *"Fill in the eVolve parameter values like the library does"*.

Territory: `src/rvt/famgen/formula.py` (`unparse`), `src/rvt/famgen/param_profile.py` (`_convention`, `_from_convention`, the notes), `tools/shared_params_from_rfa.py` (value / formula per row), `tests/test_param_profile_875.py` and its drop-in, this fragment, and the `plugin/lib` mirrors.

## What was built

1. **`formula.unparse(tree, names)`**, the inverse of `parse_formula` for everything it pins:
   - operators, unary minus, parentheses, if / and / or / not / round / tan;
   - parameter references by caption;
   - number constants: lengths in feet as `1.5'`, fixed-point, never an exponent;
   - string constants.
   
   Anything unpinned gives None, never a guessed spelling: an angle constant, an unknown code, a parameter with no caption.
2. **The extractor records how each family fills each shared parameter**, from its current type's row:
   - `value`: the stored text, integer, Yes/No or measurable value in internal units. It is None when blank, or when the value is an element id of the source document (a material or a family type).
   - `formula`: Revit text over parameter names.
   - `formula_unread`: set when the row has a formula this reader cannot spell.
3. **`param_profile` selects a convention per parameter.** The rule keeps structure and leaves product data behind:
   - a **formula** is taken when every carrying family uses the same readable one;
   - a **constant** only when two or more families hold it and all agree;
   - a single family's constant is that product's data (a 500 kVA unit's rating must not label a 45 kVA one), so mirroring one family (`--profile-family`) carries its formulas only;
   - materials and family types never carry.
   
   `apply` fills a parameter from its convention when the caller gave no value:
   - A text parameter whose formula is one string constant is written as that value, since text formulas are not stored yet (#870).
   - Any other text formula is left out and said.
   - The caller's own values win.
   - The notes count what came from the caller and what came from the library's conventions.
4. **#886 item 1:** the refusal note for a material value reads "not writable for this storage class". The rest of #886 stays open.

## Evidence

- **`tests/test_param_profile_875.py`** (synthetic profile): 13 passed. It covers:
  - convention selection: agreement, product data, mixed, unread, material, Yes/No, single-family mirroring;
  - filling a written transformer: text, the literal formula as a value, Yes/No, a formula evaluated per type;
  - the text-formula refusal, and the caller's values winning;
  - the extractor reading values and formulas back from a written family;
  - `unparse` round-tripping through `parse` (same spec, same value);
  - `unparse` refusing what it cannot spell.
- **Broader suites** (famgen, param-profile, extractor, formula, clearance, detail, router, plugin sync): 416 passed / 22 skipped. `sync_plugin.py --check` is in sync.
- **The owner's library, private run (counts only):**
  - 4,890 own-parameter rows. 2,611 carry a formula, and 26 of those cannot be spelled yet: unpinned functions or built-in references. 3,787 carry a value.
  - A 45 kVA transformer against the 16 electrical-equipment families gets 1 of its 13 library parameters filled by convention: the category id, which all 16 hold the same.
  - Mirroring the library's own transformer family fills its 4 identity parameters that are set by string formulas. Its product-specific constants are not copied.
- **Correction to `866-extract-library.md`:** "0 left out of the TXT (after `FORCE` joined the table)" was wrong. 15 conduit-size and cable-tray-size parameters are left out, by design, until those tokens' spelling is evidenced.

## Open

- Text formulas (#870) turn the "left out, said" cases into real formulas.
- The rest of #886.
- #876: dimension labels, beyond formula links.

## BRANCH STATE

Branch `claude/eager-franklin-xgzgda`, from main after #888.
- Written: `src/rvt/famgen/formula.py`, `src/rvt/famgen/param_profile.py`, `tools/shared_params_from_rfa.py`, `tests/test_param_profile_875.py`, `tests/ci_shard.d/875-param-conventions.txt`, this fragment, and the `plugin/lib` mirrors.
- Carried from #888's review nits: a `schemas()` docstring line on release context (`src/rvt/estorage.py`), and a corrected count in `866-estorage-rfa.md`.
- Staged: nothing.
- No certification claim.
