# 863 — a constructor's known facts reach its standard parameters

Stream **family-standards** (tech-lead session, 2026-10-02). Closes #863.

## What changed

- **`standards.apply_safe(..., facts=…)`** takes the constructor's `FactSheet`, or every type's sheets. The standard parameters its own known facts establish are filled from it, and the caller's `standard_values` override any of them.
  - The report's `filled_from_facts` names each one with its fact key, tier and source. They are also in `filled`.
  - The mapping is data: `standards.FACT_VALUES`, fact key → standard parameter. Today: `frequency_hz` → **Frequency** and `cri` → **Color Rendering Index**. Each fact is stored in its parameter's internal unit (Hz, a plain number).
  - **Only a known tier fills a standard (S-2026-08-11-a):** `fact`, `given` or `derived`. `assumed`, `nominal` and `ours` never do.
  - **A standard parameter is one value per family.** When the family's types hold different values for a fact, it stays blank and a note says why. An earlier head of this PR wrote the first type's value on all. Base main filled nothing from facts.
  - With `standards=False`, nothing is authored from facts and no note names them. The facts were never the caller's offer.
- **These constructors pass their facts:**
  - the two generic-model paths (`sheet`);
  - panelboard, transformer and luminaire, including `make_luminaire(kind="downlight")` (`sheets`, every type);
  - device (`facts`);
  - fan coil and fan-powered box (`sheet`);
  - the IFC route's switchboard (`ifc/intent.py`, `sheet`);
  - the IFC route's downlight (`ifc/famfrom_ifc.py`, `fs`). It fills its photometrics through its own `std_values` as before. Its sheet holds no frequency or CRI fact, so it fills nothing more today.

  Every `apply_safe` caller now passes facts.

  These are call-site-only changes in `factory.py`, some wrapping onto two lines. No other line of the #913 program's files changed.

## DONE 3: the constructor sweep

Which known facts map to a standards-table entry:

| constructor | filled from facts | known facts with no standard to fill, or blanks with no fact |
|---|---|---|
| transformer (45 kVA) | **Frequency = 60 Hz** (`fact`) | Voltage and Wires stay blank by design (two sides; a single value would be a guess). Weight, enclosure, kVA, Temperature Rise, Phases and Primary/Secondary Voltage are the constructor's own parameters already. Impedance, Insulation Class, Taps, Sound Level, K-Factor, Mounting: no fact. |
| luminaire (2x4 troffer) | **Color Rendering Index = 82** (`fact`) | Efficacy could be *derived* from lumens ÷ watts (4600 / 38); not done, because a derived standard needs its own rule. Light Loss Factor, Driver Type, Dimming Protocol, IP Rating: no fact. |
| downlight (`make_luminaire(kind="downlight")`) | none | no CRI or frequency fact in its record |
| panelboard | none | Frequency and Enclosure Rating have no fact. Voltage, phases, wires and mains are the constructor's own parameters. |
| device (duplex receptacle) | none | NEMA Configuration and Device Type follow from the device *kind* (5-15R), not from a fact key. That is a candidate for a kind → standard mapping, not done here. |
| generic model / archetype | none | their facts are geometry |
| fan coil / fan-powered box | none | voltage and phases are `assumed`, so never filled; dimensions are `nominal` |
| switchboard (IFC route, `ifc/intent.py`) | none | its sheet holds no frequency or CRI fact (`facts=` is passed since the #1031 review) |
| downlight (IFC route, `famfrom_ifc`) | none | its sheet holds no frequency or CRI fact (`facts=fs` is passed since #1031's second review) |

## Evidence

- `tests/test_standards_facts_863.py`: **18 passed** (9 plus 9 for the review fixes). It covers:
  - 45 kVA transformer: Frequency 60 on every type row, `filled_from_facts` with tier `fact`, Voltage and Wires blank;
  - a caller's 50 Hz wins;
  - luminaire CRI;
  - `assumed`, `nominal` and `ours` never fill;
  - disagreeing types: blank plus a note;
  - `standards=False`.
- **DONE 4**, at the final head:
  - `test_famgen_standards.py`, `test_famgen_factory.py`, `test_fan_coil_893.py`, `test_fan_powered_895.py` and `test_plugin_sync.py`: **249 passed, 5 skipped**.
  - `test_standards_facts_863.py`, `test_matrix_evidence_984.py`, `test_param_binding_877.py`, `test_profile_map_876.py` and `test_profile_map_from_rfa_876.py`: **94 passed, 1 skipped**. The skip is #981's downlight rows.
  - `test_equipment_drives_913.py`, `test_ifc_intent.py`, `test_standards_apply_safe.py`, `test_famfrom_ifc_standards.py`, the three clearance suites (`test_equipment_clearance_882.py`, `test_lcp_clearance_820.py`, `test_nec_clearance_819.py`) and `test_conftest_scaffolding.py`: **246 passed, 1 skipped**.
- `tools/sync_plugin.py --check`: clean.

## Also in this PR: the 🟡 nits of #1029's second review

- **`param_binding.bind_material`** now paints the way `equipment_clearance.apply_material` does: `m_materialId`, every cached face's render style, and the material among the deletion parents. The material the solid wore before is dropped from those parents, so deleting it in Revit no longer deletes the solid. There is a test.
- **The "provenance library (…)" line** now matches its profile source whole, as the "linked by" line does since #1029, so a profile name holding `"): "` cannot split it. There are two tests: a name holding the separator, and a library line whose parameters all lost their tags.
- **The proposal tool's tie wording** is now "no axis holds a majority of its families ({…})". Before, it said "split evenly" even with three buckets.
- **The #877 and #876 records:** the #877 record's BRANCH STATE now lists #1029's code and test files, and both records' test counts are current. Neither BRANCH STATE was otherwise re-audited.

## Also in this PR: fixes from #1031's own review

- The switchboard passes its facts.
- The record names exactly which constructors pass facts. After the second review, every `apply_safe` caller does, the IFC downlight included.
- A fact is offered only for a parameter the category authors and the document lacks. One that cannot be written is reported as `facts_not_written`, never in the caller's `values_not_placed` / `values_unusable`.
- A note names which filled values came from the family's own catalog facts rather than from the caller.
- When only some types hold a fact, the parameter stays blank with the same note as a disagreement.
- 60, 60.0 and "60" count as one value.
- A multi-type provenance cites every source and every tier, e.g. `fact; derived`, never only the first type's.
- The fact pre-processing runs inside `apply_safe`'s never-block `try`. A value `coerce_value` cannot represent (an `OverflowError`) leaves only that parameter blank and named in `values_unusable`, never the whole standards step.
- The "left blank" note for types that do not agree is written only where the step really authored that parameter blank: not under `skip=`, not when the step did not run.
- `bind_material` / `apply_material` paint through one `_paint`, which drops the previous material from the deletion parents only when that material id is positive. A parent added for another reason that happens to share the id would also be dropped. No writer path does that today.

## The #984 evidence guard: a changed generator output, recorded

Session CI caught a change in output. The stage_L8 family set, which `tests/test_matrix_evidence_984.py` rebuilds, now writes the 45 kVA transformer's Frequency from its catalog fact. So the generator fingerprints changed:
- 2026: `ea239c27…` → `be4868dc…`
- 2025: `5fe7308d…` → `8d7055d0…`

The guard's procedure was followed:
- `STAGE_L8_EARLIER_FORM` in `src/rvt/frontdoor/matrix.py` now names the change ("its standard Frequency filled from its catalog fact (#863)");
- so do the matching rows in `docs/product/PERMUTATION-MATRIX.md` (5) and `plugin/docs/HONEST-STATUS.md` (1);
- the new fingerprints are recorded as `reviewed`, with `reviewed_at` naming #1031.

The certified file is untouched. The entry stays uncertified, `certified: None`.

## BRANCH STATE

- Files:
  - `src/rvt/famgen/{standards,factory,fan_coil,fan_powered}.py` and their plugin mirrors;
  - `tests/test_standards_facts_863.py` and the drop-in `tests/ci_shard.d/863-standards-facts.txt`;
  - the #1029 nits: `src/rvt/famgen/{param_binding,param_profile}.py`, `tools/profile_map_from_rfa.py`, `tests/test_{param_binding_877,profile_map_876,profile_map_from_rfa_876}.py`, and the 876/877 records;
  - the review fixes to two more constructors: `src/rvt/ifc/intent.py` (the switchboard passes `facts=sheet`) and `src/rvt/ifc/famfrom_ifc.py` (the downlight passes `facts=fs`);
  - `src/rvt/famgen/equipment_clearance.py`: `apply_material` paints through `param_binding._paint`. It now raises `BindingError` for a material id ≤ 0 and drops the previous material from the deletion parents;
  - all of the above with their `plugin/lib` mirrors, where mirrored (`tools/profile_map_from_rfa.py` is not);
  - the #984 guard update: `src/rvt/frontdoor/matrix.py`, `docs/product/PERMUTATION-MATRIX.md`, `plugin/docs/HONEST-STATUS.md`;
  - this record.
- Shipped on merge; nothing is staged. No Revit claim (hard rule 4).
