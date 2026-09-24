# Family parameter formulas: the stored form

How a Revit family parameter's **formula** is stored in a family document, and what
our writer (`src/rvt/famgen/formula.py`, `FamilyDoc.add_family_parameter(formula=…)`)
emits. The format facts below were read from our own Revit-2026 `Formats/Latest`
schema and confirmed numerically against a private reference pack of 421
Revit-2025-born families (#838 / #850). Only aggregate counts appear here; no name,
value or tree from a reference family is carried.

## Where it lives

- A formula is **not text**. Every `FamilyParamValue` entry carries `m_oExpression`,
  a pointer to a parsed tree of `Expression` classes. This covers both the self
  Family's `m_familyParams` (the current type) and every `FamilyTypeTable` row
  (`m_pFamilyTypes.m_pairs[].params.m_params[]`).
- The entry's `m_value` (or `m_int` for Yes/No) holds the **evaluated result for
  that type**.
- **Every type row repeats the same tree** (2,052 / 2,052 formula entries).
- The `ParamElemFamily` element carries **no formula flag**. Formula and plain
  parameters differ only in identity fields.
- `FamDimConstrMgr.m_paramExprs` is **not** the formula table. It holds linear
  dimension-constraint entries (`m_coef` × `m_paramId`). 39 sampled families have
  formulas and no `m_paramExprs` at all.
- **"No formula"** is a null pointer, or a `StringConstantExpression` whose
  `m_value` is empty.

## Node classes (our 2026 schema)

| class | fields |
|---|---|
| `BinaryOperatorExpression` | `m_binaryOperator`, `m_pLeftSubexpression`, `m_pRightSubexpression` |
| `UnaryOperatorExpression` | `m_unaryOperator` (1 = negation), `m_pSubexpression` |
| `FunctionExpression` | `m_function`, `m_subexpressions[]` |
| `ParenExpression` | `m_pSubexpression` |
| `ParameterExpression` | `m_paramId` (the parameter's element id) |
| `NumberConstantExpression` | `m_value` (internal units), `m_specTypeId` |
| `StringConstantExpression` | `m_value` |

Every node is an owned pointer `{ptr_class, pid: -1, value}`.

## Codes, pinned numerically

Every formula entry of every type row in the pack (24,320 evaluations) was
re-evaluated under candidate meanings and compared with the value Revit stored for
that type. The table gives the **independent re-verification's** single-code counts
(#862 review). That run reads an Integer result rounded from `m_int`; the first pass,
without that allowance, scored `/` 938/942. The first pass also counted `<` across
mixed formulas: 1,445/1,445.

| code | meaning | evaluations matching the stored value |
|---|---|---|
| operator 1 / 2 / 3 / 4 | `+` / `-` / `*` / `/` | 842/842, 901/901, 603/603, 942/942 |
| operator 6 / 7 / 8 | `=` / `>` / `<` | 722/722, 476/476, 1,022/1,022 |
| function 10 | `if(c, a, b)` | 2,405/2,405 |
| function 12 / 11 | `and` / `or` (variadic) | 1,367/1,367, 166/166 (swapped: far lower) |
| function 13 | `not` | 993/993 |
| unary 1 | negation | 12/12 |
| function 18 | `round` (half up) | 88/88 |
| function 3 | `tan` | 30/30 |

Not pinned, so the writer refuses them with the reason:
- operator 5 (probably `^`; 8 uses, none evaluable);
- functions 20 and 9;
- function 21 (4–6 arguments; likely a size lookup, which needs its table);
- the other functions (`sqrt`, `abs`, `roundup`, `sin` …);
- `<=`, `>=`, `<>`.

## Units

The same law holds throughout the pack:
- a constant written **with a unit** (`1'`, `6"`, `300 mm`) is a **length** constant,
  stored in feet;
- a **bare** constant is a **number** (`autodesk.spec.aec:number-1.0.0`);
- `+`, `-` and the comparisons need the same spec on both sides;
- `*` or `/` by a number keeps the other side's spec.

So `Width + 1` is refused, exactly as Revit's own formula editor rejects
inconsistent units.

## What the writer accepts (and refuses)

- **Operands and results are measurable doubles or Yes/No.** Text, Integer and other
  storage kinds are refused. Their stored forms (`m_str`, an element id) are not what
  this writer emits. In the pack, an **Integer**-typed formula result is stored
  *rounded* in `m_int` (the independent review needed that allowance to reach
  24,320/24,320). A future Integer path must do the same.
- **Yes/No is typed.** An `if` condition and the arguments of `and` / `or` / `not`
  must be Yes/No. A Yes/No value never takes `+ - * /`, `= < >`, negation or
  `round`.
- `tan` takes an angle or a number, never a length.
- **Names and unit suffixes match with exact case**, as Revit's do. `5M` and `5MM`
  are refused. Function names are matched case-insensitively. A name followed by
  `(` is a function call, so a parameter named like a function never shadows it.
- **Not supported, and refused with the reason (never a crash):**
  - feet-and-inches literals (`2' 6"`: write `2.5'`);
  - parameter names that start with a digit;
  - trees deeper than 60 levels (`formula.MAX_DEPTH`, far beyond a hand-written
    formula).
- **A formula reads exactly what the file stores.** Each input is taken from the
  entry `family_param_value` will write: Yes/No from `m_int`, measurable values from
  `m_value`. An int given for a length is stored in `m_int` and reads as the 0.0
  Revit will see.
- **A non-finite result** (inf or NaN, from the inputs or from overflow) is not
  evaluable. The formula is then left out.
- **All types, or none.** A formula is written only when it parses, type-checks and
  evaluates on **every** type. Otherwise every row keeps its plain value, with no
  tree next to a value that is not its result, and `notes` says why.
  - A circular formula is refused.
  - A formula that only *reads* a circular one is still written; it reads that
    parameter's plain value.

## Not yet claimed

That Revit **re-evaluates** our trees when a driving parameter changes needs a
desktop verdict (hard rule 4). #850 DONE (3) tracks it.
