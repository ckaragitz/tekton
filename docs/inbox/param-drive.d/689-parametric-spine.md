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

## What is fact, and what is a ladder

The **structure** is schema fact, read off the file's own class schema — no donor, no
guess:

```
FamDimConstrMgrImpl
  m_paramExprs      pair<ElementIdIntPair, ParamExpr>
  m_drivenDimSegs   pair<ElementIdIntPair, DimValueExprOwner>   <- the flex
  m_fixedRefs       pair<ElementIdIntPair, GrefAndDir>
  m_dimSegDataMap   map -> DimSegData
ParamExpr           m_entries:[ParamExprEntry{m_coef, m_paramId}], m_elemId, m_msgId
DimValueExpr        m_entries:[DimValueExprEntry{m_coeff, m_dimId, m_seg,
                                                 m_mayBeDriven}], m_offset
```

It is a linear-expression system: a value is `sum(coefficient x term) + offset`, so a
1:1 drive is one entry at coefficient 1.0 and offset 0.

The **values** are not fact, and four of them decide whether Revit solves. Each is one
variable, so each is one rung with a control (`famdim.RUNGS`, D0–D4): which side of
`m_drivenDimSegs` is the driver; whether `m_paramExprs` needs the mirror entry; whether
`m_fixedRefs` must pin the opposite reference; and the polarity of `m_mayBeDriven`.
**Nothing in this stream claims a family flexes.** The default rung is D0 — the control,
which must *not* flex — and every surface stays silent about editability (hard rule 4).

Two encoding facts cost a build each and are recorded so they cost nobody else one:
`m_oDimValueExpr` is a **pointer** field (kind 14), so it needs
`{"ptr_class": …, "pid": -1, "value": …}` — a bare dict raises `EncodeError: bad pointer
token`. And `Element.m_constrInfo` is an **array** (kind 14, flags 81), not an int:
setting it to `1` raises `TypeError: object of type 'int' has no len()`. D4 was re-aimed
at `m_mayBeDriven` and `m_constrInfo`'s array element type is recorded as unknown —
the schema leaves it unnamed and every element we author carries `[]`.

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
opposite reference pinned in `m_fixedRefs`, which is unsettled rung D3, so it is refused
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
- `src/rvt/famgen/famdim.py` — the driver tables: `RUNGS` D0–D4, `labelled_dims`,
  `driver_tables`, `apply_to_doc`. Opt-in; default rung D0 is the control.
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
