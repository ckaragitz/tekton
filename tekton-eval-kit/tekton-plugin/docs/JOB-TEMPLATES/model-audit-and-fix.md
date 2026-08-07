# JOB TEMPLATE — Model Audit (and fix) on a native `.rvt`

**Hand this file to Claude with a `.rvt` attached.** For when a GC or owner
sends you a Revit model and you need to know what's in it before you
quote, coordinate, or edit — without opening Revit. Uses the plugin's native
`.rvt` engine (`rvt` package), read-only.

**Honesty line:** reading/auditing a `.rvt` is verified locally against the
Revit 2026 sample corpus and runs in under a second. *Writing changes back*
is proven for text/content edits and whole-file rewrite (rendered by
Autodesk's own reader), but creating **new** equipment inside a `.rvt` is
still in progress — so this template AUDITS; fixes go out as IFC or as
instructions for the Revit user. See `plugin/docs/HONEST-STATUS.md`.

---

## 1. Prompt to type (Cowork / claude.ai / Claude Code)

> Use the **tekton-native** skill to audit the attached Revit file, read-only.
> Give me: element counts by class (top 12), the levels with elevations,
> every electrical system / circuit with the panel it belongs to, its
> voltage, poles and load classification, and the loaded family symbols vs
> placed instances. Then tell me what looks incomplete or wrong for an
> electrical package. Do not modify the file.

## 2. What Claude runs

The engine loads the file's element table + partition records and
decodes every element (this is the reverse-engineered `.rvt` reader).
Element counts, levels, and electrical circuits are read straight out of
the native records — `RbsElectricalSystem` is Revit's circuit object.

```python
from rvt.mutate import Document
from collections import Counter
K = 10.7639104   # Revit stores electrical values in internal (ft-based) units: V, VA, W = internal / K
d = Document.load('rmebasicsampleproject')            # sample .rvt in samples/
host = [i for i in d.idx[102] if i in d.et_by_id]     # host-document elements (== ElemTable)
c = Counter(d.class_of(i) for i in host)
print("host-document elements:", len(host), " distinct classes:", len(c))
for k, v in c.most_common(12): print(f"  {v:>6}  {k}")
for lv in d.levels(): print(f"  {lv['name']:<12} {lv['elevation_ft']:8.3f} ft")
for cls in ("RbsElectricalSystem", "RbsWireCurve", "RbsConduitCurve", "PanelScheduleView"):
    print(f"  {c.get(cls,0):>6}  {cls}")
for i in d.ids_of_class('RbsElectricalSystem')[:8]:
    v = d.value(i) or {}
    print(i, v.get('m_strDescription'), v.get('m_strLoadClassifications'),
          round(v.get('m_dVoltage',0)/K), v.get('m_nPoles'), v.get('m_dRating'),
          round(v.get('m_dApparentLoad',0)/K))
```

## 3. EXAMPLE RESULT — real audit of `samples/rmebasicsampleproject.rvt`

This is actual output from running the audit on the Revit 2026 MEP sample
(2026-08-03). Your job's report will look like this, with your file's
numbers.

```
file: samples/rmebasicsampleproject.rvt   (Revit 2026 MEP sample)
host-document elements: 28,132   (ElemTable rows: 28,132;
                                  all partition records incl. embedded families: 142,174)
distinct element classes: 286

top classes:
    5629  FamilyInstance
    2555  CurveElem
    2459  GStyleElem
    1407  IndependentTag
    1331  ParamElemFamily
    1067  LinearDimString
    1045  RbsWireCurve
    1020  CategoryElem
     750  FontElem
     724  RbsDuctCurve
     632  FamilySymbol
     535  PipeFittingCenterLine

levels (elevation ft):
  Level 1         0.309
  Level 2        12.467
  Level 3        23.950
  Roof Level     35.761

MEP systems / electrical:
     187  RbsElectricalSystem      <- electrical circuits
    1045  RbsWireCurve             <- wire runs
      20  RbsConduitCurve
      24  PanelScheduleView        <- panel schedule views defined in the file
       5  RbsVoltageType
       3  RbsDistributionSysType
      45  RbsHvacSystem
     724  RbsDuctCurve
     491  RbsPipeCurve

family symbols loaded: 632  |  family instances placed: 5,629

circuits (RbsElectricalSystem) - first 8 of 187
       id  panel    load class          V poles A rating   load VA
   623656  PP-1B    Receptacles       208     3       20     21600
   623665  TP-1B    Receptacles       480     3       20     21600
   623674  MP-1B    Other             480     3       20         0
   623695  LP-1B    Other             480     3       20         0
   626306  PP-1B    HVAC; Receptac    208     3       20    144183
   626315  TP-1B    HVAC; Receptac    480     3       20    144183
   626495  MP-3B    Other             480     3       20         0
   626521  LP-3B    Other             480     3       20         0

circuits by load classification: Receptacles=60, HVAC=47, Lighting;Other=38,
  Lighting=18, Other=10, HVAC;Receptacles=4, Cooling=2, ... (14 groups)
```

**How to read it for the customer:** this model has 187 real circuits
across panels PP-1B/TP-1B/MP-1B/LP-1B/…, on 208 V and 480 V systems, 24
panel schedules already defined, 1,045 wire runs and 5,629 placed family
instances over 4 levels. That's the "what am I bidding on" answer in one
paragraph — before anyone opens Revit.

## 4. The "fix" half — what to do with findings

The audit is read-only. Route each finding by what's possible today:

| Finding | Route |
|---|---|
| Missing/wrong equipment, wrong locations | Deliver corrected equipment as **Tier-1 IFC** to link over the model (electrical-room-package template) — the Revit user swaps it in. |
| Data errors on existing elements (a panel name, a title/label text) | **Native `.rvt` content edit** — proven for text/content changes (V18/V19 in the acceptance log). Ask us; version-check first. |
| Add NEW native elements (a new panel family instance, a wall) into the `.rvt` | **Not yet** — element creation via template patching is in progress (TRACKER D7). Deliver IFC + a Tier-2 handoff table instead. |
| Missing circuits / connectors | Tier 2 — Revit-side only. Give the Revit user the circuit table from Section 3. |

Before any `.rvt` write: confirm the recipient's Revit version (a `.rvt`
cannot be opened by any Revit older than the one that saved it — HONEST-STATUS §4).
