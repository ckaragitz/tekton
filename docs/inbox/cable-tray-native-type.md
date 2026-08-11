# cable-tray-native-type — issue #608, probes A1/A2 (PARKED)

Stream: #608 (native cable tray). Windows laptop with desktop Revit 2026 on the
same machine, so every verdict below is a real desktop result.

## Why

`Systems > Electrical > Cable Tray` draws a native element whose type is an
`RbsCableTrayType` — a SYSTEM family, which lives in a project and never in a
`.rfa`. Our certified base carries the plumbing (`CableTraySettingsElem` 1,
`CableTraySizesElem` 1) but **zero** types, so the tool has nothing to draw.

## What was built

`src/rvt/genesis/cabletray.py` — `new_cable_tray_type()`, returning a
`TypeRecord` that flows through the existing mutate/commit path.

The record shape is a LAW mined from a Revit-born specimen (an Electrical-
template project saved by the owner; hard rule 3 — mine laws from samples,
author our own equivalents; nothing read from an Autodesk installation, rule 2,
and no donor bytes shipped).

## Measured law: `RbsCableTrayType`

Seven types in the specimen, and only **two** profile classes exist:

| `m_eCableTrayType` | profile class | type names carrying it |
|---|---|---|
| 1 | `UShapeSweepProfile` | Wire Mesh, Solid Bottom, Channel, Trough, Single Rail |
| 2 | `LadderSweepProfile` | Ladder |

`m_Profile.value` is **empty in all seven**. Revit generates the straight run
from `CableTrayExtrusionGStep`. So a "Wire Mesh Cable Tray" is drawn as a plain
U trough whatever it is named: **LOD-400 mesh geometry is not reachable on a
straight run through the native element.** It IS reachable on the FITTINGS,
which are loadable families (the fourteen `m_idDefault*` slots).

Other measured constants: category `-2008130`, `m_dMaxWidth`/`m_dMaxHeight` 8.0,
`m_dMinBendMultiplier` 1.0, `m_dRoughness` 0.0003, `m_symbolInfo.m_name`.

## Probe A1 — FAILED, cause identified exactly

Committed one type into a copy of `G_ABPD.rvt` (watermark 1,472,524 → element
1,472,525; ElemTable 3,102 → 3,103). Validator VALID, 0 errors. Desktop:

```
The id stored in the ElemRec 1472525 does not match the id stored in the Element -1
Assertion failed: line 364 of ...\RevitDB\ElemTable\Unmarshaller.cpp
captureTryCrash 0xe06d7363
```

Cause: the object was built with `blank_object()` alone, which leaves
`m_id = -1`; `element_defaults()` is what stamps it. **The field diff printed
`m_id: ours=-1 theirs=493370` before the build and it was dismissed as
"set on commit". It is not.** Fixed in the constructor, with the journal line
quoted at the call site so the next reader cannot repeat it.

## Probe A2 — FAILED, and it is a clean single-variable result

Same commit with `m_id` correct. Value match against the Revit-born type rose
to 39/47 shared fields (the 8 differences all deliberate: five fitting ids at
-1, no preview element, our name, our id).

Two files identical but for ONE element:

| | control (unmodified base) | A2 (base + our type) |
|---|---|---|
| `Loaded elemStream#21` | 3,102 elements | **3,103** |
| repair prompt | shown → repaired | shown → repaired |
| result | **opens**, plans expand | **fatal crash** |

```
Element Expansion: 30% Opening Plans, 5% In Regenerate, 65% Other
Exception occurred
ExceptionCode=0xc0000005  ExceptionAddress=00007FFCC5F2FBB0
Terminating RevitWorker Processes -> TaskDialog_Fatal_Error_Occured
```

The type's BYTES are accepted — the element stream deserialised and the
document repaired and got into plan expansion and regeneration before the
access violation. The fault is in how Revit USES the type, not how it reads it.

**Prime suspect, and it is an authoring mistake not a mystery:** all fourteen
fitting slots were set to -1. The specimen's own `m_bWithFitting: False`
variant does NOT do that — it still carries real ids for `m_idDefaultElbow`,
`ElbowUp`, `ElbowDown`, `Transition` and `Union`, nulling only tee/cross.
Revit most likely dereferences a default fitting during regeneration.
`m_previewElemId` was also -1 against the specimen's real element id.

Both are configurations the specimen never shows — invented rather than
copied, the exact error the storage-class law exists to prevent.

## Finding for #16 (independent of this stream)

**The unmodified composed base prompts for repair on every desktop open:**

```
TaskDialog_Repair_Missing_Unique_Elements
  "One or more required internal settings are missing from the model."
  -> "Repair and open" -> "Repair ... was successful"
DBG_INFO: Missing unique element: View Referencing Setting
```

It repairs and opens, so it is not fatal — but `UniqueElementsTracking` ships
incomplete, `viewer.autodesk.com` never surfaces it, and it is not in the
ledger. Also warned on every open: `LinePatternTracking is corrupt!
LinePatternElement id 10 is NULL`, `Material 23 is missing!`, `No default
StackedWallType`.

## Open questions

* **A3**: fitting slots exactly as the specimen's without-fitting variant, not
  all null. The families it names do not exist in our base, so this needs a
  decision (author minimal fitting families, or find which slots Revit can
  actually tolerate as -1) rather than another guess.
* `m_previewElemId` — what Revit does with -1 is unmeasured.
* Whether a repaired base still needs `View Referencing Setting` authored, or
  whether Revit's repair is durable once saved.

## BRANCH STATE

* Branch: `ckaragitz12/materials-from-ifc` (shared with the #514 work, PR #607).
* Files written: `src/rvt/genesis/cabletray.py` (new),
  `docs/inbox/cable-tray-native-type.md` (this record).
* Gates: validator VALID 0 errors on both probe files; famgen + IFC suites
  green; `sync_plugin.py --check` in sync.
* Status: **PARKED** at the owner's request after A2. No merge claim for the
  cable tray type — it crashes Revit and must not ship until A3 passes.
