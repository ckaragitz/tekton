# 689 — the driver tables, and the parametric spine that declares them

Refs #689. Stream: `param-drive`.

## The finding that opened this

`param_drive` (#372) authors what a flexing family appears to need — side reference
planes, alignments binding the solid's sketch to them, a labelled `LinearDimString`
whose segment carries `m_paramId`. It validates 0 errors. On the owner's Revit 2026 it
*"did not work what so ever"*: the family opened, the parameter was there, changing it
moved nothing.

The cause is not a donor and not the dimension. Every family this engine writes carries

```python
mgr = blank_object("FamDimConstrMgrImpl")     # skeleton.new_self_family
```

with **every table empty**. `genesis/residue_c` even names it *"the corpus-lawful EMPTY
`Family.m_oFamDimConstrMgr`"*, and `skeleton.py:1736` already said the quiet part —
*"formulas live in the FamDimConstrMgrImpl expression tables which this skeleton leaves
empty"* — written about formulas, but it is the flex as well. Revit is handed a
labelled dimension and an empty driver table: nothing tells it the parameter *drives*
the geometry.

## Which table is the drive — settled by reading the schema, no specimen

The first cut of this ladder enumerated table combinations because the field *names* look
ambiguous. Their **types** are not, and every file carries its own class schema — so this
needed no donor and no specimen, only reading what was already in hand:

| table | value type | what it actually expresses |
|---|---|---|
| `m_paramExprs` | `ParamExpr{m_entries:[{m_coef, m_paramId}], m_elemId}` | a linear expression **in parameters**, owned by the element `m_elemId` names — *"this segment = 1.0 × Width"*. **This is the parameter drive.** |
| `m_drivenDimSegs` | `DimValueExpr{m_entries:[{m_coeff, m_dimId, m_seg, …}]}` | an expression in **other dimension segments** — dimension-to-dimension equality, *not* parameter drive |
| `m_dimSegDataMap` | `DimSegData{m_dimDir, m_grefArr:[GeomRef], m_coefArr}` | **which geometry** the segment spans, and with what signs |

That exposed two real bugs in the first cut, both now fixed:

1. **The opening rung was aimed at the wrong table.** Old D1 populated `m_drivenDimSegs`
   alone — dim-to-dim equality, which cannot make a parameter move geometry.
2. **`m_paramExprs` was keyed by the parameter.** Backwards: `ParamExpr` is an expression
   *in* parameters, so the key is the segment whose value is computed and `m_elemId` is
   the dimension that owns it. The parameter appears only inside `m_entries`.
3. **`m_dimSegDataMap` was never populated at all** — so even a correct expression would
   have told the solver a number with nothing to move.

## What remains a ladder, and what it now is

The reasoning fixes *which* tables and *how they are keyed*. It does not prove Revit's
solver is satisfied by the minimum, so the rungs now vary only how much is declared:

| rung | adds | a PASS proves |
|---|---|---|
| **P0** | nothing (the control — must NOT flex) | the premise is wrong if it flexes |
| **P1** | `m_paramExprs` | the solver-side binding is the whole missing piece |
| **P2** | + `m_dimSegDataMap` | the span must be declared in the manager too |
| **P3** | + `m_fixedRefs` | the solver needs an anchor |
| **P4** | + `m_drivenDimSegs` | that table doubles as a registry (schema says it is the wrong axis, so it is last) |

**The default is now P2**, the reasoned candidate — the smallest set that tells the
solver both what the value is and what moves — not the empty control. That is a
derivation, **not a verdict**: no rung has been confirmed in Revit and nothing claims a
family flexes (hard rule 4).

### Built and round-tripped at every rung

On a real panelboard document (2 labelled dims, each with exactly 2 witness refs,
directions +X and +Y):

```
P0 {}                                             P0: VALID (0 errors)
P1 {'m_paramExprs': 2}                            P1: VALID (0 errors)
P2 {'m_paramExprs': 2, 'm_dimSegDataMap': 2}      P2: VALID (0 errors)
P3 (= P2 + pins when given)                       P3: VALID (0 errors)
P4 {+ 'm_drivenDimSegs': 2}                       P4: VALID (0 errors)
```

Read back out of the written `.rfa`, P2 carries exactly the reasoned model:
key `(dim 1113, seg 0)`, expression `1.0 × param 1082` with `m_elemId = 1113` (the
dimension), and segment data spanning ref planes `1105`/`1106` with coefficients
`[-1.0, +1.0]` along `[1, 0, 0]`.

Two encoding facts, each of which cost a build: `m_oDimValueExpr` is a **pointer** field
(kind 14), so it needs `{"ptr_class": …, "pid": -1, "value": …}`; and
`Element.m_constrInfo` is an **array** (kind 14, flags 81), not an int.

## The templates do not answer this

Revit's 108 default `.rft` templates (`docs/inbox/rft-mining.md`) all carry an **empty**
`FamDimConstrMgr`, and `m_constrInfo` is `[]` on every dimension in every one of them. A
template has no user geometry, so it has recorded no flex. Negative result, worth
stating: **the thing that would settle the rungs by direct reading is a Revit-born
`.rfa` with a working parametric flex** — any parametric family from Revit's own
library. Reading its self-Family's populated tables settles all four unknowns at once
and replaces the ladder with a measurement.

## The spine (`src/rvt/famgen/parametric.py`)

Fixing the tables alone would have left the real limitation in place: `param_drive`'s
only entry point is `wire_panelboard_drive`, which assumes two axes *named* Width and
Height on a four-line axis-aligned rectangle. A third axis, a channel profile, a tray
with a rung pitch, or a parameter added later had nowhere to go — so "build anything at
LOD 400 and associate any parameter at any time" was not expressible.

The spine is the missing declaration in the middle. You say what the product is
parametric *in*; the planes, parameters, dimensions, alignments and driver tables are
derived, and the result is bound to the category's own Revit template:

```python
model = ParametricModel(
    category="cable_tray",
    axes=(DrivenAxis("width",  "Width",  (1, 0, 0), value=2.0),
          DrivenAxis("height", "Height", (0, 1, 0), value=0.5)),
    params=(FreeParam("Rung Spacing", value=0.75),
            FreeParam("Load Rating", spec=SPEC_NUMBER)))
plan(model)          # the whole authoring plan, no document in hand
wire(doc, model)     # author it
```

Adding a parameter at any time is `model.with_param(...)` / `.with_axis(...)`: the model
is immutable, the plan is recomputed, nothing is hand-wired. `plan()` needs **no
document**, so a caller can see exactly what a parameter would add before authoring
anything — and `check_model()` says up front whether it is authorable.

**The template binding** (`template_binding`) ties a model to the category's own Revit
template through `category_facts` when present, falling back to the resolver table and
reporting which. It never raises on an unknown category — a caller must still be able to
deliver (hard rule 1). The import is soft, so this branch does not stack on #698; the
`rft` evidence tier lights up automatically once that merges.

## What is refused, and why refusing is the point

An axis parallel to the **extrusion direction** is named, not authored
(`OUT_OF_PLANE_GAP`). Revit drives extrusion depth from the form's extrusion end — a
different binding this module does not author. Authoring a sketch-style drive for it
would produce a parameter that changes nothing, which is *exactly the failure #689 was
opened for*. Likewise `symmetric=False` (one plane moving from a fixed origin) needs the
opposite reference pinned in `m_fixedRefs`, which is unsettled rung P3, so it is refused
with that reason rather than silently authored.

`wire(strict=False)` authors what it can and returns the problems, for callers that must
deliver regardless and will carry the caveat.

## Open questions

- Which rung solves. Needs a desktop verdict or a born specimen (above).
- `m_constrInfo`'s array element type — unnamed in the schema.
- The out-of-plane (extrusion-end) binding, and non-rectangular profiles: both need
  their own measured wiring. Neither is invented here.

## BRANCH STATE

**Files written**
- `src/rvt/famgen/famdim.py` — the driver tables: the reasoned `RUNGS` P0–P4,
  `labelled_dims` (now also extracting witness `GeomRef`s and the dimension direction),
  `driver_tables`, `apply_to_doc`. Opt-in; default rung P2 is the reasoned candidate,
  P0 the control.
- `src/rvt/famgen/parametric.py` — new: `DrivenAxis`, `FreeParam`, `ParametricModel`,
  `check_model`, `template_binding`, `plan`, `explain`, `wire`, `box_model`.
- `tests/test_famgen_parametric.py` (25 tests) + `tests/ci_shard.d/689-parametric.txt`.
- this record.

**Gates**
- `tests/test_famgen_parametric.py` — **25 passed**.
- `tests/test_famgen_parametric.py tests/test_famgen_factory.py` — **82 passed, 5 skipped**.
- `tools/sync_plugin.py` — deny-audit clean, validation passed.
- A test-matcher bug caught in review of my own run: `test_a_z_axis_is_not_reported_as_
  parallel` matched the bare word "parallel", which `OUT_OF_PLANE_GAP` itself contains,
  so it passed for the wrong reason. Tightened to the exact complaint. The underlying
  code bug it was written to catch was real — `check_model` used only the z component of
  the cross product, which reads any z axis as parallel to both in-plane axes.

**Staged vs shipped:** shipped, and inert by default. No route calls `wire()` yet; the
default rung is the control. Nothing claims a family flexes until a verdict says so.
