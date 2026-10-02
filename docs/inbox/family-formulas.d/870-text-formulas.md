# 870 — text-parameter formulas are written

Stream **family-formulas** (tech-lead session, 2026-10-02). Closes #870. It also carries the 🟡 nits of #961's independent review.

## Census (DONE 1) — the owner's full reference library, private, counts only

421 files were read. 418 carry formulas with a text constant, **4,002** in all.

| shape | count |
|---|---|
| a bare string constant | 3,278 |
| `if()` chains over Yes/No conditions (a Yes/No parameter, `=`/`>` against a number, `and`/`not`) choosing between texts | 623 |
| a formula holding `size_lookup` (function 21) with a column-name string | 101 |

- **Value rows (3,866 with a non-empty result):** every one is `m_str` = the result, with `m_value` 0.0, `m_int` 0 and `m_elemId` -1.
- **Re-evaluation:** 3,901 of 4,002 re-evaluate exactly to the stored `m_str`. The other 101 contain `size_lookup`, which is unpinned and stays refused.
- **`if()` branches:** 9,481 string constants, 8,357 nested functions, 27 numbers (inside `size_lookup`), 26 parameter references, 5 binary operators.

## Encoding (DONE 2)

- `StringConstantExpression` holds `{m_value: str}` only, with no spec. Measured from the census: 12,944 nodes, all with that one field.
- A text `if()` is the ordinary function 10 (pinned in #850) with text branches.
- A text parameter reference is the ordinary `ParameterExpression`.

## What changed (DONE 3)

- **`formula.py`:**
  - a `"…"` literal is parsed to a `StringConstantExpression`;
  - text parameters may be named (integer and material storage are still refused);
  - `if()` may choose between texts, and mixing text with a number is refused, said;
  - no operator takes text (`+ - * / = < >` and negation), because none is pinned;
  - `""` alone is refused, since Revit stores it as *no formula*;
  - `evaluate` returns the text;
  - new public names: `SPEC_TEXT`, `is_text`.
- **`skeleton._apply_formulas`** (the territory #870 names):
  - a text result goes to `m_str`, with `m_value` 0.0 and `m_int` 0, on every row under the same tree;
  - a text parameter reads its `m_str`;
  - a material parameter is read as `tekton.storage:material-browse` through a new `_formula_spec` helper. It never becomes text, even though `param_profile` names a `ParamDefMaterialBrowse` with a text spec.
- **`param_profile._from_convention`:** the library's text formulas are written as the formulas they are. Before this, a string constant was flattened to a value and anything else was left out (#875's interim rule).
- **`docs/writer/formulas.md`** has the text rules.

### #961 review nits carried here

- `settle_formula_provenance` rebuilds each `provenance library (<source>)` line from that source's own parameters only.
- The `_shape` docstring now says a constant's unit spec is not compared, and why that is safe.
- A test goes through `finalize`'s real exception path: `_apply_formulas` raises once, then a later finalize re-tags.
- Not here: the stale `formulas NOT written (…)` note after such a failure. It lives in `skeleton.finalize` (#913 territory) and was added to #886 item 6.

## Evidence (DONE 4)

- `tests/test_famgen_formula_870.py`: **24 passed**. It covers:
  - the encoder;
  - `if` chains evaluated per branch;
  - every refusal;
  - spell-back to the same tree;
  - on a written family: every row's `m_str`, the blank numeric fields, the same tree, a text formula on a length or material refused and said;
  - an emitted `.rfa` that reads back field-for-field and validates with 0 errors.
- **Existing tests updated where they pinned the old refusal:**
  - `test_famgen_formula_850`: text references are no longer refused, and "Pick = LabelA" is now written.
  - `test_param_profile_875`: `'"Box"'` is now a formula, `Zz Label` is written, 5 conventions.
  - `test_param_profile_886`: 5 conventions.
- **Formula and profile suites** (`test_famgen_formula_{850,870}`, `test_param_profile_{866,875,886}`, `test_shared_params_from_rfa_866`) plus `test_plugin_sync`: **206 passed**. Every module that mentions formulas or profiles (14 modules): **422 passed, 39 skipped**.
- **Owner's library, counts only:**
  - The extractor's profile is **byte-identical** to main's (2,548 formulas, 89 unread).
  - Mirroring each of the 421 library families onto a transformer (`ProfileRequest(family=…)`) now writes **1,736 text formulas**. Before, they were flattened or left out.
    - 244 are refused, almost all because they name a *local* library parameter the mirror does not carry ("unknown name"). That is the same reason as the 1,006 refused numeric ones, whose count is unchanged.
  - The four mirrored families with the most text formulas (10, 10, 9, 1), written for 2026 and 2025: **VALID, 0 errors, provenance ok** on all 8.

## Not claimed (DONE 5)

- That Revit shows and re-evaluates a text formula needs a desktop verdict (hard rule 4). The numeric formulas' own desktop verdict (#850 DONE 3) does not cover text.
- Nothing is staged: per S-2026-09-04-a, a desktop check goes into the next batched verdict round rather than to the owner as a probe.

## BRANCH STATE

- Files:
  - `src/rvt/famgen/{formula,skeleton,param_profile}.py` and their `plugin/lib` mirrors;
  - `docs/writer/formulas.md`;
  - `tests/test_famgen_formula_870.py` and the drop-in `tests/ci_shard.d/870-text-formulas.txt`;
  - `tests/test_famgen_formula_850.py`, `tests/test_param_profile_{875,886}.py`;
  - this record.
- Shipped on merge; nothing staged for the viewer.
