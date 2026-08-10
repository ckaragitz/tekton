# Learned: the famdoc laws (issue #333 campaign, desktop rounds 1-28)

One-line context: a generated `.rfa` that satisfies the validator can still
crash desktop Revit; each law below was found by single-variable desktop
probes on the owner's Revit 2026 (journals on #52/#333) and is now enforced
by famgen + guard tests.  For KNOWLEDGE.md when the orchestrator folds.

1. **Required settings singletons** (#52): every famdoc carries
   AutoCamSettingsElem, DefaultDivideSettings, DrawOrder3dElem,
   PenWidthTableElem, wired at UniqueElementsTracking [10]/[60]/[85] +
   PenWidthTableInfo.
2. **Family-viewer law**: `m_boundOffset[2]=(100,0)` on every viewer; the
   plan viewer matches the project viewer's shape (bounds inactive, crop
   on, ortho 1, flags 0, not intentionally placed).  Basis frames stay
   per-view-type.  Symptom: BoundedSpace.cpp:86 warning + pan crash.
3. **Dimension-style law**: a default linear DimensionStyle constellation
   (style + LeaderStyle arrowhead + 4 anonymous CategoryElems each owning
   one GStyleElem + Arial FontElem), registered in
   SymbolIdMgr.m_defElementTypeMap key 10.  Symptom: "Where is the
   DimensionStyle?" + selection assert.
4. **Family-units law**: UnitsElem.m_units carries the full 136-spec
   m_formatOptionsMap (famgen asset); every unit-bearing param spec MUST
   resolve in it.  Symptom: Family Types dialog throws at doModal.
5. **Spec vocabulary**: number = `autodesk.spec.aec:number-1.0.0` (not
   -1.0.1).  Text/integer params are NOT ParamDefValue at all -- text =
   `ParamDefString` (no spec/restriction/boundless fields), integer =
   `ParamDefInt` (+ m_lowBound/m_upBound int32) -- the ParamDef class
   encodes the storage type (the storage-class law).
6. **Order-cell law**: one group per group-type id in
   FamilyParamsOrderCell (normalize_order_cell now runs in finalize).
7. **Solver-state law**: a curve-bearing parametric VarSketch carries
   m_elemRecs (VarSketchLineSegObj per curve, VarParams = endpoints),
   m_constrRecs (HorVer per axis-parallel edge + PP corner joins,
   subtype 1=start/2=end, COINCIDENCE-DETECTED never index-copied),
   primed guess cache, serFlags 32, version 1.  pids follow assign_pids'
   archive numbering.  Symptom chain: "Invalid idx in
   VarSketch::getCurveObj" then "lines overlap / can't make extrusion".
8. **Classification tables**: AssemblyCodeTable + KeynoteTable minimal
   EMPTY singletons at UET [64]/[65] (never copy the donor's sample data /
   external file paths).  Symptom: "Internal setting 'Keynote Table' is
   required by Revit and has been deleted" on edit.
9. **Meta-laws**: Autodesk's error text names the missing subsystem
   verbatim -- read the journal before guessing; a mismatched-pair diff
   (wrong unit/viewer) burns rounds; the host ADocument comes only from
   `standalone_family_write` (a plain write ships a stub host and dies at
   elemStream#0); ForgeTypeId version is ignored by comparison but the
   NAME must exist in Revit's vocabulary.
