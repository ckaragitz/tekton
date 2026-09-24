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
that type.

| code | meaning | evaluations matching the stored value |
|---|---|---|
| operator 1 / 2 / 3 / 4 | `+` / `-` / `*` / `/` | 842/842, 901/901, 603/603, 938/942 |
| operator 6 / 7 / 8 | `=` / `>` / `<` | 722/722, 476/476, 1,445/1,445 |
| function 10 | `if(c, a, b)` | consistent in every passing run |
| function 12 / 11 | `and` / `or` (variadic) | 6,955/6,955 (swapped: 2,895) |
| function 13 | `not` | consistent |
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

## Not yet claimed

That Revit **re-evaluates** our trees when a driving parameter changes needs a
desktop verdict (hard rule 4). #850 DONE (3) tracks it.
