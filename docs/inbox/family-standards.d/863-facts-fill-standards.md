# 863 — a constructor's known facts reach its standard parameters

Stream **family-standards** (tech-lead session, 2026-10-02). Closes #863.

## What changed

- **`standards.apply_safe(..., facts=…)`** takes the constructor's `FactSheet`, or every type's sheets. The standard parameters its own known facts establish are filled from it, and the caller's `standard_values` override any of them.
  - The report's `filled_from_facts` names each one with its fact key, tier and source. They are also in `filled`.
  - The mapping is data: `standards.FACT_VALUES`, fact key → standard parameter. Today: `frequency_hz` → **Frequency** and `cri` → **Color Rendering Index**. Each fact is stored in its parameter's internal unit (Hz, a plain number).
  - **Only a known tier fills a standard (S-2026-08-11-a):** `fact`, `given` or `derived`. `assumed`, `nominal` and `ours` never do.
  - **A standard parameter is one value per family.** When the family's types hold different values for a fact, it stays blank and a note says why. Before this, the first type's value would have been written on all.
  - With `standards=False`, nothing is authored from facts and no note names them. The facts were never the caller's offer.
- **Every constructor passes its facts:**
  - the two generic-model paths (`sheet`);
  - panelboard, transformer and luminaire (`sheets`, every type);
  - device (`facts`);
  - fan coil and fan-powered box (`sheet`).

  These are one-line call-site changes in `factory.py`; no other line of the #913 program's files changed.

## DONE 3: the constructor sweep

Which known facts map to a standards-table entry:

| constructor | filled from facts | known facts with no standard to fill, or blanks with no fact |
|---|---|---|
| transformer (45 kVA) | **Frequency = 60 Hz** (`fact`) | Voltage and Wires stay blank by design (two sides; a single value would be a guess). Weight, enclosure and kVA are the constructor's own parameters already. Impedance, Insulation Class, Taps, Sound Level, K-Factor, Mounting: no fact. |
| luminaire (2x4 troffer) | **Color Rendering Index = 82** (`fact`) | Efficacy could be *derived* from lumens ÷ watts (4600 / 38); not done, because a derived standard needs its own rule. Light Loss Factor, Driver Type, Dimming Protocol, IP Rating: no fact. |
| downlight | none | no CRI or frequency fact in its record |
| panelboard | none | Frequency and Enclosure Rating have no fact. Voltage, phases, wires and mains are the constructor's own parameters. |
| device (duplex receptacle) | none | NEMA Configuration and Device Type follow from the device *kind* (5-15R), not from a fact key. That is a candidate for a kind → standard mapping, not done here. |
| generic model / archetype | none | their facts are geometry |
| fan coil / fan-powered box | none | voltage and phases are `assumed`, so never filled; dimensions are `nominal` |

## Evidence

- `tests/test_standards_facts_863.py`: **9 passed**. It covers:
  - 45 kVA transformer: Frequency 60 on every type row, `filled_from_facts` with tier `fact`, Voltage and Wires blank;
  - a caller's 50 Hz wins;
  - luminaire CRI;
  - `assumed`, `nominal` and `ours` never fill;
  - disagreeing types: blank plus a note;
  - `standards=False`.
- **DONE 4:** `test_famgen_standards.py`, `test_famgen_factory.py`, the fan coil and fan-powered suites and `test_plugin_sync`: **258 passed, 5 skipped**. Every other module that mentions filled standards, Frequency or CRI (edit-family mass and size, IFC standards, archetypes, `apply_safe`): **306 passed**.
- `tools/sync_plugin.py --check`: clean.

## Also in this PR: the 🟡 nits of #1029's second review

- **`param_binding.bind_material`** now paints the way `equipment_clearance.apply_material` does: `m_materialId`, every cached face's render style, and the material among the deletion parents. The material the solid wore before is dropped from those parents, so deleting it in Revit no longer deletes the solid. There is a test.
- **The "provenance library (…)" line** now matches its profile source whole, as the "linked by" line does since #1029, so a profile name holding `"): "` cannot split it. There is a test.
- **The proposal tool's tie wording** is now "no axis holds a majority of its families ({…})". Before, it said "split evenly" even with three buckets.
- **The #877 and #876 records** now give current test counts and list every file in BRANCH STATE.

## The #984 evidence guard: a changed generator output, recorded

Session CI caught a change in output. The stage_L8 family set, which `tests/test_matrix_evidence_984.py` rebuilds, now writes the 45 kVA transformer's Frequency from its catalog fact. So the generator fingerprints changed:
- 2026: `ea239c27…` → `be4868dc…`
- 2025: `5fe7308d…` → `8d7055d0…`

The guard's procedure was followed:
- `STAGE_L8_EARLIER_FORM` in `src/rvt/frontdoor/matrix.py` now names the change ("its standard Frequency filled from its catalog fact (#863)");
- so do the matching rows in `docs/product/PERMUTATION-MATRIX.md` (5) and `plugin/docs/HONEST-STATUS.md` (1);
- the new fingerprints are recorded as `reviewed`, with `reviewed_at` set to this branch.

The certified file is untouched. The entry stays uncertified, `certified: None`.

## BRANCH STATE

- Files:
  - `src/rvt/famgen/{standards,factory,fan_coil,fan_powered}.py` and their plugin mirrors;
  - `tests/test_standards_facts_863.py` and the drop-in `tests/ci_shard.d/863-standards-facts.txt`;
  - the #1029 nits: `src/rvt/famgen/{param_binding,param_profile}.py`, `tools/profile_map_from_rfa.py`, `tests/test_{param_binding_877,profile_map_876,profile_map_from_rfa_876}.py`, and the 876/877 records;
  - the #984 guard update: `src/rvt/frontdoor/matrix.py`, `docs/product/PERMUTATION-MATRIX.md`, `plugin/docs/HONEST-STATUS.md`;
  - this record.
- Shipped on merge; nothing is staged. No Revit claim (hard rule 4).
