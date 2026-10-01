# 894 — conduit connectors, learned from the corpus (the fan coil's feeder first)

Stream **equipment-detail** (tech-lead session, 2026-10-01). Issue #894, under steer #913 ("structure our code off the reference families"). Partial: conduit only.

## Corpus study (counts only; the corpus stays quarantined)

The owner's 421 reference families were each read inside its own release. They hold:

| domain | connectors | families |
|---|---|---|
| `ConnectorElemDomainCableTrayConduit` | 392 | 166 |
| `ConnectorElemDomainElectrical` | 57 | 57 |
| `ConnectorElemDomainPiping` | 9 | 7 |
| `ConnectorElemDomainHvac` (duct) | 0 | 0 |

**What the 392 conduit specimens pin:**
- `m_eSystemType` is 32 in all 392.
- `m_eProfileType` is 0 (round) in 262 and 1 (rectangular) in 125.
- `m_ePlacementType` is 0 in 387.
- Round connectors keep width = height = 1.0.
- **`m_dConnectorDiameter` stores the diameter.** Bound to a family parameter through the diameter property (−1133415), the two are equal (90/90). Through the radius property (−1133401), the stored value is twice the parameter (104/104).
- **Hosting:** 207 are hosted on an extrusion face, the hosting our power connectors use.

**The connector shell is shared across domains.** Category −2007000, the geometry-step flags, the marker size and the absent value sets are identical across the corpus's electrical, piping and conduit connectors. They are release or regeneration state, not domain. So a conduit connector is our desktop-verified power-connector shell with the conduit domain record. Its 12 fields match the born field set exactly.

**Not pinned:**
- **Piping:** every piping-domain specimen sits on a conduit fitting or box (category −2008128), so their system codes (7, 19, 22, 29) cannot be read as hydronic supply, return or condensate.
- **Duct:** there is no specimen at all.

Both wait for a born mechanical family in the quarantined corpus. A system classification is never guessed.

## What was built

- **`rvt.famgen.mep_connectors`:**
  - `conduit_domain(diameter_ft, primary=, description=)`;
  - `add_conduit_connector(doc, host=, face=, location=, direction=, u_axis=, diameter_ft=, bind_diameter_param=, primary=)`. This builds the power-connector shell (`skeleton.new_electrical_connector`, no load classification) and swaps in the conduit domain. A bound diameter parameter is written as the `{param, −1133415}` association, with the parameter in the header's deletion parents.
  - Conduit connectors are kept in `doc.mep_connectors`, because the document's primary law reads the electrical field name. The first conduit connector is the primary one of its domain.
- **The fan coil:**
  - A "Conduit Diameter" length parameter (nominal 3/4 in, the common branch-circuit trade size, stamped `nominal`).
  - The conduit connector sits on the disconnect's top at the feeder entry, the same point as the power connector, driven by that parameter. It sits on the cabinet's electrical end when the cabinet is too small for the disconnect.

## Evidence

- `tests/test_fan_coil_893.py` adds 3 tests: the domain fields and the binding, read-back from the written file, and the refused diameter. With the scaffolding test: 65 passed.
- **2026, 2025 and 2024 fan coil builds:** VALID with 0 errors and provenance ok. Each carries one power and one conduit connector, read back from the file.

## Open

- **Hydronic and duct connectors** need a born mechanical specimen (any fan coil, VAV box, pump or AHU family) in the quarantined corpus, as a development instrument.
- **Rectangular (cable tray) connectors:** their width and height bindings (−1133403 / −1133404) are not yet paired with a stored-value law.
- **Conduit connectors on the junction box, wireway and cable tray archetypes** come next, outside the #913 constraint files.
- **"Conduit routes to it"** needs a desktop verdict (hard rule 4).

## BRANCH STATE

Branch `claude/eager-franklin-xgzgda`.
- Written: `src/rvt/famgen/mep_connectors.py` (new), `src/rvt/famgen/fan_coil.py`, `tests/test_fan_coil_893.py`, this fragment and its index line, and the mirrors.
- Staged: nothing.
- No certification claim.
