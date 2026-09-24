# family-formulas: generated families carry parameter formulas (#850)

Stream record for #850. It follows from steer #836 and the reference-pack
measurement in #838 (99% of the owner's reference families use formulas, median 20;
ours had 0). The format facts are in `docs/writer/formulas.md`.

## What was built (this PR)

- **`src/rvt/famgen/formula.py`: formula text → the expression tree Revit stores.**
  - It uses only the numerically pinned codes (`+ - * /`, `= < >`, `if`, `and`,
    `or`, `not`, `round`, `tan`, negation, parentheses).
  - Parameter names may contain spaces; the longest name wins.
  - Constants follow Revit's unit law.
  - It includes an evaluator with Revit's semantics (comparisons give Yes/No,
    `round` is half up) and `referenced_params` for dependency order.
  - Anything unpinned or unit-inconsistent raises `FormulaError` with the reason.
- **`FamilyDoc.add_family_parameter(formula=…)`** (`src/rvt/famgen/skeleton.py`) was
  "formula NOT serialized" and is now written.
  - At `build`, `_apply_formulas` parses every formula and orders the formulas by
    dependency (a cycle is refused). For each type row it writes the same
    `m_oExpression` tree plus that row's evaluated value (`m_value`, or `m_int` for
    Yes/No), and the current-type set carries it too.
  - A formula that cannot be stored keeps its plain value, and the reason goes to
    `doc.notes`; the family is still built (hard rule 1).

## Review round 1 (🛑), fixed

- **A text formula stopped the build** (`ValueError` / `TypeError` in `finalize`).
  Now text and integer operands are refused at parse time, every per-type
  evaluation and coercion sits inside one `try` that also catches `TypeError`, and
  the family is always built.
- **A Yes/No input given as an entry dict `{"m_int": 1}` was read as 0.** Yes/No
  is now read from `m_int` in every form.
- **A type that could not be evaluated kept the tree next to a value that was not
  its result.** Now a formula is written only if it evaluates on every type;
  otherwise it is left out everywhere and said.
- **Yes/No positions were untyped.** `if(Width, …)`, `and(Width, …)`, `not(Count)`
  and `-Is Tall` were accepted and are now refused.
- **Nits:**
  - names now match case-sensitively;
  - a function call wins over a same-named parameter;
  - "formula ends where a value is expected" replaces "unknown name ''";
  - dead code removed;
  - a formula reading a circular one is no longer called circular.
- **The reviewer independently re-verified the pinned codes** on the pack with
  trusted `main` code:
  - 24,320 / 24,320 trees identical across type rows;
  - `+` 842/842, `-` 901/901, `*` 603/603, `/` 942/942, `=` 722/722, `>` 476/476,
    `<` 1,022/1,022;
  - `if` 2,405/2,405, `and` 1,367/1,367, `or` 166/166, `not` 993/993;
  - negation 12/12, `round` 88/88, `tan` 30/30;
  - these hold with the Integer-rounded-in-`m_int` allowance noted in
    `docs/writer/formulas.md`.

## Review round 2 (🛑), fixed

- **Yes/No was still usable as a number.** `Flag + Flag`, `Is Tall * 2` and
  `Is Tall < Flag2` were accepted. Now `+ - * /` and `= < >` refuse Yes/No operands.
- **A formula read the raw input, not the stored entry.** An int for a length was
  stored as `m_value 0.0` but computed with as 2; `1.0` for a Yes/No was stored as
  No but computed with as Yes. Now every input is read from the
  `family_param_value` entry that is actually written.
- **`finalize()` could still raise** (`RecursionError` at 200 nested `if`s, 200
  parentheses, a 500-term sum, 900 minus signs). Now `MAX_DEPTH` 60 is enforced
  with an iterative depth walk, `RecursionError` is caught in parse and evaluate,
  and `referenced_params` is iterative.
- **Nits:**
  - non-finite results are refused;
  - unit suffixes are exact case;
  - `tan` of a length is refused;
  - the code tables in `formula.py`, `docs/writer/formulas.md` and this record now
    use one run's numbers and say which;
  - the unsupported forms are documented.
- The reviewer confirmed that families **without** formulas are byte-identical to
  `main` (`make_family` panelboard sha256 `a160d2a4…` on both).

## Evidence

- **Reference pack (private, git-ignored `samples/`; counts only).**
  - 421 self families; about 131,000 expression nodes; 24,320 formula evaluations
    used to pin the codes (table in `docs/writer/formulas.md`).
  - Type rows repeat the tree: 2,052 / 2,052.
  - No `ParamElemFamily` formula flag.
  - `m_paramExprs` is not the formula table.
- **Our output.** A probe family (Width, Height; `Half Width = Width / 2`,
  `Is Tall = Height > 4'`, `Cover Height = if(Is Tall, Height - 6", Height + Half Width)`)
  with two types:
  - evaluates to 250 / 300 mm, no / yes, and 1150 / 1647.6 mm;
  - `doc.roundtrip()` gives 0 failed;
  - written with `emit_family_rfa_v2` on our bundled base and read back from disk,
    the trees and values are intact;
  - `rvt_validate` VALID, 0 errors; provenance `ok: true`.
- **`tests/test_famgen_formula_850.py`: 77 passed.**
  - It has 37 round-0 tests, 17 round-1 pins (14 of them fail on `604ce8f`) and 23
    round-2 pins (all 23 fail on `f61a076`). It covers the parser, unit
  constants, unit refusals, unpinned refusals, operator and function codes, the
  evaluator, dependency order, the writer on every type row, refusal notes, the cycle
  refusal, the schema round-trip, and an emitted `.rfa` read back and validated.
- **Family suites.** `test_famgen_skeleton`, `_factory`, `_archetypes`,
  `_determinism_168`, `_parametric`, `_standards`, `_adoc`, `test_yesno_param_710`,
  `test_constraint_law`, `test_conformance` plus the new file give
  **496 passed, 26 skipped, 0 failed** (round 2) (`RVT_SKIP_LARGE=1`, no samples).
- `tools/sync_plugin.py --check` clean; `validate_plugin.py` PASS;
  `check_portable_paths.py` ok.

## Open (this issue)

1. #850 DONE (2): archetypes declare derived parameters as formulas (the ladder
   tray's rung count, a box's derived dimension).
2. #850 DONE (3): a desktop verdict that Revit re-evaluates our trees when a driving
   parameter changes. A batch must be STAGED (`probe_batch.py`, `/batches`
   reservation); until then nothing claims formulas work in Revit.

## BRANCH STATE

- Branch: `claude/eager-franklin-xgzgda`, from `main` @ `2466f38`.
- Files written:
  - `src/rvt/famgen/formula.py` (new; + its mirror)
  - `src/rvt/famgen/skeleton.py` (`add_family_parameter` docstring, `_apply_formulas`; + its mirror)
  - `tests/test_famgen_formula_850.py`
  - `tests/ci_shard.d/850-famgen-formula.txt`
  - `docs/writer/formulas.md`
  - this record
- Shipped: the formula encoder and the writer integration.
- Staged, not shipped: nothing. The desktop batch is still to be reserved and staged.
