# MEP-CONNECTORS-FIDELITY — balanced multi-pole loads split per phase, one primary connector per family, sourced from Autodesk's public docs (issue #164)

Stream: **mep-connectors-fidelity** (2026-08-09, issue #164, branch
`cam/164-connector-phase-loads`, engineer session `eng164` started by the tech-lead
session's fan-out). Refs #108 · PG6 · size S.

Charter (issue #164): our electrical connectors booked a balanced multi-pole load
entirely on phase 1 (a 75 kVA transformer secondary: `m_dApparentLoadPhase1` = 75 kVA,
Phase2/3 = 0) and flagged *every* connector primary. The numbers an engineer reads in
Revit's connector properties / panel schedule would be wrong even when the file
opens. DONE required the load and primary laws to be **sourced** (Revit API docs or a
decoded Revit-born 3-phase connector), else stop at `needs-decision`.

**Outcome: sourced, built, decoded back.** No owner machine supplied a Revit-born
3-phase specimen this session; the source is Autodesk's *public* API reference and
product help (allowed by rule 2 — not an install directory; rule 3 — no sample bytes).
Nothing here is a "loads in Revit" claim (rule 4); nothing was staged for the viewer.

---

## 1. The sources (URLs + the one-line quotes the law rests on)

| # | fact | source | quote |
|---|---|---|---|
| S1 | connector system-type codes | Revit API `ElectricalSystemType` enumeration — <https://www.revitapidocs.com/2026/90f62108-9cd1-a66a-a123-8372307f4e7f.htm> | "An enumerated type listing all the possible electrical system types for a connector object." Members: `PowerBalanced 30 — Electrical System Type is PowerBalanced.` / `PowerUnBalanced 31 — Electrical System Type is PowerUnBalanced.` / `PowerCircuit 6 — Electrical System Type is PowerCircuit.` |
| S2 | which load field is live | Revit help *Connector Properties* — <https://help.autodesk.com/cloudhelp/2020/ENU/Revit-Model/files/GUID-3DE410FC-7BB7-44FD-B75E-A02C4F42C1AD.htm> | "Apparent Load — Calculated based on (Voltage) x (Current). Active only when Balanced Load is True and System Type is Power." / "Apparent Load Phase 1 — … Active only when Balanced Load is False and System Type is Power." / "Apparent Load Phase 2 — … and Number of Poles >1." / "Apparent Load Phase 3 — … and Number of Poles >2." / "Number of Poles — Possible values are: 1, 2, or 3." / "System Type — Possible values are: Data, Power - Balanced, Power - Unbalanced, …" |
| S3 | phase sum = total | Revit help *About Load Calculations* — <https://help.autodesk.com/view/RVT/2025/ENU/?guid=GUID-EE3F38E5-44A7-4991-BA99-7AC8732DBEDF> | "Apparent Load Phase A + Apparent Load Phase B + Apparent Load Phase C = Total Connected" |
| S4 | one primary per family | same *Connector Properties* page (S2) | "Primary Connector — Possible values are: True or False (read only). A single connector of each discipline is allowed to be primary in each family. The family's electrical data that displays in a schedule is derived from the primary connector." |
| S5 | primary in the API | `ConnectorElement.IsPrimary` — <https://www.revitapidocs.com/2022/92a0eddf-2414-903f-8872-898442426ded.htm>; `ConnectorElement.AssignAsPrimary` — <https://www.revitapidocs.com/2022/c6c21445-5e95-e15b-743d-f8fdfb369e79.htm> | "Identifies if this is the primary connector in the family." / "This method is used to promote this connector as primary, and the rest of connectors in this system will be assigned as secondary." |
| S6 | circuit-side per-phase loads exist only for Power | `ElectricalSystem.ApparentLoadPhaseA` — <https://www.revitapidocs.com/2023/35b66d8e-eafe-f6ba-1d11-4bcac26c2ea8.htm> | "The ApparentLoadPhaseA value of the Electrical System." / exception: "This property only available when System Type is Power!" |
| S7 | power-factor-state code | Revit API `PowerFactorStateType` — <https://www.revitapidocs.com/2026/bb418213-600f-ca37-e1a0-a09df497ecac.htm> | `Lagging 1 — Power FactorState Type is Lagging.` / `Leading 0 — Power FactorState Type is Leading.` |

**Finding that corrects the skeleton's own docstring:** `m_systemType 31`, byte-verified
on every specimen (rme panelboard 786876, fixture 773363, receptacle 847095), is
**Power-Unbalanced**, not "PowerCircuit" as the `[INFERRED]` tag said (S1:
PowerCircuit = 6, a *circuit's* type). Revit's own equipment/fixture connectors are
therefore unbalanced-type connectors whose load lives per phase — which is exactly why
the fixture/receptacle specimens carry their load on `Phase1` with `m_dApparentLoad`
0.0. The old code had the right bytes for 1-pole and the wrong model for 3-pole.

## 2. The law as built (`src/rvt/famgen/skeleton.py`)

* `ELECTRICAL_SYSTEM_POWER_BALANCED = 30`, `ELECTRICAL_SYSTEM_POWER_UNBALANCED = 31`
  (the old caller-less `ELECTRICAL_SYSTEM_POWER = 31` name is replaced by these),
  `ELECTRICAL_SYSTEM_TYPES = {"power_balanced": 30, "power_unbalanced": 31}` —
  `system_type` takes the name or the code —, `POWER_FACTOR_LAGGING = 1` (S1, S7).
* `phase_loads_va(apparent_load_va, poles) -> [p1, p2, p3]` (VA): a **number** is the
  connector's whole balanced load → equal split over phases 1..poles (S3: the phases
  sum to the total; balanced ≡ equal per pole); a **sequence** is the explicit
  per-phase list, length 1..poles (S2: phase *n* is only active when poles ≥ *n*);
  poles ∈ {1, 2, 3} (S2); the rest 0.
* `electrical_domain(..., apparent_load_va, system_type="power_unbalanced", primary=True)`:
  - `power_unbalanced` (31, default, what every specimen and every factory product is):
    `m_dApparentLoadPhase1..3 = voltamps(phase_loads_va(...))`, `m_dApparentLoad = 0.0`
    (S2 "active only when Balanced Load is True" + **[V] 0.0 on all three specimens**).
  - `power_balanced` (30): `m_dApparentLoad = voltamps(total)` (S2), phase fields = the
    equal split so the two agree whichever a reader shows; a per-phase *list* is refused
    (unequal phases are unbalanced by definition). **Honest limit:** no type-30
    specimen has ever been decoded, so the *on-disk* content of a balanced connector's
    inactive phase fields is UNOBSERVED — the semantics are documented (S2), the storage
    is not. Exposed because the DONE asks for it; **the factory does not emit 30**, so
    no shipped family depends on it. Follow-up filed (§6).
  - `m_bIsConnectorPrimary = primary`; `m_powerFactorState = POWER_FACTOR_LAGGING`.
  - The `[INFERRED]` tags on system type and power-factor state are gone (replaced by
    S1/S7); the removed `balanced_load` kwarg had no callers.
* `new_electrical_connector(..., system_type=, primary=)` passes through. The
  one-primary law has **one** spelling, on the document that owns the connectors:
  `FamilyDoc.has_primary_connector()` / `FamilyDoc.resolve_primary(primary)` — `None`
  → primary iff the doc has none yet; an explicit second primary → `ValueError` (S4/S5).
  `FamilyDoc.add_electrical_connector(..., primary=None)` (the S0e path) and the
  factory both go through it.

`src/rvt/famgen/factory.py`:
* `add_connector(..., primary: Optional[bool] = None)` → `doc.resolve_primary`
  (re-raised as `FactoryError`); `apparent_load_va` may be a number or a per-phase list.
* `make_transformer`: primary winding `primary=True`, secondary `primary=False`; the
  secondary's `kva*1000` is now split 25/25/25 kVA by the skeleton. `make_panelboard` /
  `make_luminaire`: untouched — one connector each, primary by default, identical bytes.

## 3. Evidence — the emitted `.rfa` files decoded back (fresh cloud clone, bundled schema)

Built with the factory (`make_transformer(kva=75, 480, '208Y/120')`,
`make_panelboard(400 A, 42 sp, 480Y/277, MCB)`, `make_luminaire(2x4 troffer, 38 W)`),
written with `validate=True, provenance=True`, then every `ConnectorElem`'s
`ConnectorElemDomainElectrical` decoded from **the file** (`FamilyIndex(path).decode`).
Display VA = internal × 0.3048².

| family / connector | field | before (main @ c8b3aec) | after (this branch) |
|---|---|---|---|
| transformer / 1 "Primary" 480 V 3-pole | Phase1 / Phase2 / Phase3 / ApparentLoad (VA) | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |
| | `m_bIsConnectorPrimary` | True | **True** |
| transformer / 2 "Secondary" 208 V 3-pole | Phase1 / Phase2 / Phase3 (VA) | **75 000 / 0 / 0** (807 293.28 / 0 / 0 internal) | **25 000 / 25 000 / 25 000** (269 097.7604 internal each) |
| | ApparentLoad | 0 | 0 |
| | `m_bIsConnectorPrimary` | **True** | **False** |
| | `m_systemType` | 31 | 31 |
| panelboard / 1 "Panel Feed" 480 V 3-pole | all 14 domain fields | sysType 31, 0/0/0/0 VA, primary True | **identical** (0 field diffs) |
| luminaire / 1 "Power Connection" 120 V 1-pole | all 14 domain fields | sysType 31, P1 38 VA, P2/P3/AL 0, primary True | **identical** (0 field diffs) |
| all three | family-mode validate | VALID, 0 errors | VALID, 0 errors |
| all three | provenance | ok, suspects [] | ok, suspects [] |
| primaries per family (xfmr / panel / lum) | | 2 / 1 / 1 | **1 / 1 / 1** |

Whole-document check (every seq-101/102/103 record of `Partitions/0` decoded and
compared field by field, before vs after): panelboard **0** connector diffs, luminaire
**0**, transformer exactly the **4** intended fields on connector 1042
(`Phase1/2/3`, `m_bIsConnectorPrimary`). The only other differing values in all three
files are the per-build random family GUID inside each `ParamElemFamily.m_typeId`
(`revit.local.family:<guid>…`) and the `Contents` / `Global/History` timestamps —
pre-existing per-build non-determinism (tracked as #9), not this change.

## 4. Gates (this branch, fresh cloud clone, `.venv` from `scripts/cloud-setup.sh`)

| gate | result |
|---|---|
| `pytest tests/test_famgen_skeleton.py tests/test_famgen_factory.py tests/test_famgen_geometry.py tests/test_famgen_adoc.py tests/test_famgen_catalog.py tests/test_bare_family_validate.py tests/test_mep_devices.py tests/test_electrical.py -q` | **173 passed, 50 skipped** (every skip = `samples/` / `vendor/` absent, as designed), 6.2 s |
| `pytest tests/test_plugin_sync.py -q` | **9 passed** |
| `tools/sync_plugin.py` then `--check` | synced 2 files (`plugin/lib/src/rvt/famgen/{skeleton,factory}.py`), deny-audit clean, √ Validation passed, zip rebuilt (not committed); `--check`: **plugin in sync with source** |
| `plugin/scripts/validate_plugin.py` | **PASS** (25 assertions) |
| `tools/dev/check_portable_paths.py` | **ok: 2774 tracked paths are portable** |
| `/verify` (families surface): `tools/make_family.py transformer --kva 75 --primary 480 --secondary 208Y/120`, `… panelboard`, `… luminaire --kind recessed-troffer`, each `--json` | all three `ok=True`, `family_mode=VALID errors=0 warnings=0`, `provenance_ok=True suspects=[]`, connectors 2 / 1 / 1 |
| `tools/rvt_validate.py --family` on each | `ok=True counts={error 0, warning 0, info 2}` ×3 |
| `tools/make_family.py provenance` on each | `"ok": true` ×3 |
| decode of the CLI-built files | xfmr: con 1041 'Primary' 31/3-pole/480 V, 0/0/0/0, **primary True**; con 1042 'Secondary' 31/3-pole/208 V, AL 0, **P1=P2=P3=25 000 VA (269 097.7604 internal)**, **primary False**; panel: 31/3-pole/480 V, 0s, primary True; troffer: 31/1-pole/120 V, P1 38 VA (409.0286), primary True; `m_powerFactorState` 1 everywhere |
| probe: second explicit primary | `FactoryError: the family already has a primary connector (one primary connector per discipline per family)` |
| `/simplify` (4 review angles) | applied: one spelling of the primary law (`FamilyDoc.resolve_primary`), caller-less alias/constant dropped, `system_type` name-or-code, docstrings de-duplicated, tests reuse `FamilyIndex.ids_of_class/value` and stop re-validating an identical build; skipped with reason: keep the `power_balanced` path (DONE requires it), keep explicit `primary=True/False` in `make_transformer` (DONE wording), leave the pre-existing `add_connector`/`add_electrical_connector` overlap (wider refactor) |

New / changed tests: `test_phase_loads_split_a_balanced_load_equally_over_the_poles`,
`test_electrical_domain_load_and_primary_laws` (no schema needed — run in any clone),
`test_only_the_first_s0e_connector_is_primary`,
`test_emitted_transformer_rfa_decodes_three_equal_phase_loads_and_one_primary`
(decodes the **file**), `test_add_connector_allows_one_primary_per_family`, the
transformer composition test's phase/primary asserts, and an on-file "exactly one
primary, all type 31, `m_dApparentLoad` 0" check folded into
`test_every_kind_writes_a_family_mode_valid_provenance_clean_rfa[*]` (all four CLI
kinds; `test_famgen_factory.py` is in the CI shard). The sample-gated
`test_electrical_connectors_byte_exact` now reconstructs each specimen from its
per-phase list + its own primary flag and asserts type 31 / `m_dApparentLoad` 0.0 —
it self-skips without `samples/`; **an owner-machine run of it is the one gate this
session could not execute** (expected byte-exact: every specimen is 1-pole-loaded or
0 VA, so the split is the identity there).

## 5. Findings

1. `m_systemType 31` = Power-**Unbalanced** (S1). Autodesk's stock panelboard,
   lighting-fixture and receptacle connectors are unbalanced-type; "31 = PowerCircuit"
   was wrong (6 is). Docstring + `docs/writer/family-skeleton.md` §7 corrected.
2. For unbalanced connectors the file keeps `m_dApparentLoad` at 0.0 and the load per
   phase — documented (S2) *and* byte-verified; the equal split of a balanced physical
   load is S3 arithmetic, not inference.
3. The transformer's topology question is untouched and worth its own issue: a
   Revit-born dry-type transformer family typically carries **one** (primary-side)
   connector and serves downstream panels through its *secondary distribution system*,
   not a second connector; ours has two. With the primary winding as the primary
   connector at 0 VA, "the family's electrical data that displays in a schedule" (S4)
   is 0 VA @ 480 V. Not changed here (DONE: outputs unchanged except the two laws).

## 6. Follow-ups filed (searched `connector balanced / transformer connector / primary connector` first — none existed)

* **#321** — decode one Revit-born **Power-Balanced (type 30)** connector on an owner
  machine to pin the on-disk value of its inactive phase fields (turns §2's UNOBSERVED
  into [V]) — `P2 owner-machine area:famgen`, Refs #164.
* **#322** — decide the generated transformer's connector topology (two connectors with
  the primary winding primary at 0 VA, vs Revit-born one primary-side connector +
  secondary distribution system; what load an upstream schedule should see) —
  `P2 ready area:famgen`, Refs #164 (§5 finding 3).

## BRANCH STATE

* Branch `cam/164-connector-phase-loads` from `main` @ c8b3aec (PR #316's schema gate
  already in); PR closes #164; engineer session `eng164`, pipeline session-hosted per
  steer #302 (GitHub checks on the PR are runner-less and meaningless; the tech-lead
  session runs the shard on the exact head and merges via the API).
* Files written: `src/rvt/famgen/skeleton.py` (constants, `phase_loads_va`,
  `electrical_domain(system_type=, primary=)`, `new_electrical_connector` passthrough,
  `FamilyDoc.has_primary_connector` / `resolve_primary`, `add_electrical_connector(primary=)`),
  `src/rvt/famgen/factory.py` (`add_connector(primary=, per-phase loads)`,
  `make_transformer` primary True/False + note), `plugin/lib/src/rvt/famgen/{skeleton,factory}.py`
  (regenerated by `tools/sync_plugin.py`, not hand-edited), `tests/test_famgen_skeleton.py`,
  `tests/test_famgen_factory.py`, `docs/writer/family-skeleton.md` §7 (law table with
  URLs + quotes), this record.
* Gates: §4, all green locally; the one gate not runnable here is the sample-gated
  byte-exact specimen test (owner machine).
* Nothing staged for the viewer; no `.rvt`/`.rfa` committed; no ledger change; no hot
  file touched; `tekton-plugin.zip` regenerated locally, not committed.

## 2026-08-09 — addition by stream #330 (review-nit sweep), not the mep-connectors voice

Correction to source row **S3** above (from #323's independent review): the sentence
"Apparent Load Phase A + Apparent Load Phase B + Apparent Load Phase C = Total Connected" is
genuine Autodesk help text but lives on the *Current Calculations* page —
<https://help.autodesk.com/cloudhelp/2023/ENU/Revit-MEPEng/files/GUID-2266E299-35D3-4A1A-8E76-EC17616F2C75.htm>
— not on *About Load Calculations* (GUID-EE3F38E5…). The law itself is unchanged; only the
attribution moves. `docs/writer/family-skeleton.md` §7 (the "unbalanced (31)" row) now cites
the *Current Calculations* URL; the S3 row above is left as its author wrote it and should be
read with this correction. Also from that review: `tests/test_famgen_skeleton.py::
test_electrical_connectors_byte_exact` now additionally asserts
`dom["m_bIsConnectorPrimary"] is True` on each of the three single-connector specimens
(panelboard, lighting fixture, receptacle), so the factory's "first connector is primary"
default stays pinned to Revit's own bytes; the case is `needs_rme`-gated and still self-skips
on a fresh clone ("rme sample absent").
BRANCH STATE: `cam/330-review-nit-sweep`; `tests/test_famgen_skeleton.py` 13 passed /
9 skipped (samples absent) in 0.3 s on a cloud clone; the new assert executes only on the
owner machine (samples present) — nothing else touched in famgen.
