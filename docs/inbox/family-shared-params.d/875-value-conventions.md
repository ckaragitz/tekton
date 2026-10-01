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
  - Review round 1 (#889) added 10 tests, 23 in all:
    - `unparse` brackets a tree without stored parentheses by precedence (6 shapes, each evaluated);
    - an empty string constant is no formula, including the `'""'` spelling in a profile written earlier;
    - a malformed row costs only its own parameter, not the whole profile;
    - a convention formula over a parameter the family lacks is named in a "NOT written" note and stays blank (#875 DONE 3);
    - every filled value carries `refs["provenance"]` (`library` cited to the profile, or `given`), is listed in a provenance note, and the written family validates VALID at 0 errors (DONE 2 and 4).
- **Broader suites** (famgen, param-profile, extractor, formula, clearance, detail, router, plugin sync): 416 passed / 22 skipped. `sync_plugin.py --check` is in sync.
- **The owner's library, private run (counts only):**
  - 4,890 own-parameter rows. 2,637 carry a formula. 3,787 carry a value.
    - 89 formulas are reported unread, never spelled.
      - 26 use unpinned functions or built-in references.
      - 63 name a parameter whose caption the parser cannot read back: it starts like a number, or it holds a quote.
    - None is an empty string constant, so the formula count is not inflated by "no formula" rows.
    - The earlier "2,611 carry a formula" counted only the spelled ones.
  - **Round-trip check:** every formula row of every family (11,233 rows, all parameters, not only shared ones) was spelled with `unparse`, parsed back, and evaluated with the family's stored values.
    - 10,213 are spelled.
    - 6,190 both evaluate and re-parse. All 6,190 give the same value as the stored tree: **0 differ**.
    - Before this round's fixes, 20 differed. Constants were printed to 12 decimals, so a constant stored a few ulps above a round number came back as the round number and flipped a `>`. Constants are now spelled with their exact shortest digits.
    - 229 are refused at re-parse by our own unit rule (a conduit, cable-tray or pipe size mixed with a length). They are never written: the build names them in a "NOT written" note.
    - 3,794 do not evaluate outside Revit (text formulas, unpinned functions, values not stored).
  - A 45 kVA transformer against the 16 electrical-equipment families gets 1 of its 13 library parameters filled by convention: the category id, which all 16 hold the same.
  - Mirroring the library's own transformer family fills its 4 identity parameters that are set by string formulas. Its product-specific constants are not copied.
- **Correction to `866-extract-library.md`:** "0 left out of the TXT (after `FORCE` joined the table)" was wrong. 15 conduit-size and cable-tray-size parameters are left out, by design, until those tokens' spelling is evidenced.

## Open

- Text formulas (#870) turn the "left out, said" cases into real formulas.
- Captions the parser cannot read back (a leading digit, a quote) need Revit's own spelling for such names before they can be written; they stay unread until that spelling is evidenced.
- Size specs (conduit, cable tray, pipe) mixed with lengths need the unit rule widened; that is the same evidence gap as the TXT tokens above.
- The rest of #886.
- #876: dimension labels, beyond formula links.

## BRANCH STATE

Branch `claude/eager-franklin-xgzgda`, from main after #888.
- Written: `src/rvt/famgen/formula.py`, `src/rvt/famgen/param_profile.py`, `tools/shared_params_from_rfa.py`, `tests/test_param_profile_875.py`, `tests/ci_shard.d/875-param-conventions.txt`, this fragment, and the `plugin/lib` mirrors.
- Carried from #888's review nits: a `schemas()` docstring line on release context (`src/rvt/estorage.py`), and a corrected count in `866-estorage-rfa.md`.
- Staged: nothing.
- No certification claim.
