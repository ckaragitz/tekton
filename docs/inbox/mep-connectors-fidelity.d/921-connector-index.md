# 921 — connector counts and `m_index` span every domain

Stream **mep-connectors-fidelity** (tech-lead session, 2026-10-07). Closes #921, the hand-off from #920 (#894) on #913.

## What changed

**The defect.** Power connectors live in `doc.connectors` and conduit connectors in `doc.mep_connectors`. Three counters looked only at the first:
- `factory.add_connector` numbered `m_index` as `len(doc.connectors) + 1`;
- so did `FamilyDoc.add_electrical_connector`;
- `FamilyProduct.summary()["connectors"]` and the IFC downlight's summary counted only power connectors.

So a power connector added after a conduit connector reused its `m_index`, and the fan coil reported 1 connector while its file held 2. The reference corpus numbers `m_index` continuously across domains. `mep_connectors.add_conduit_connector` already did.

**The fix.** All four now count `len(doc.connectors) + len(doc.mep_connectors)`.

**Shipped output.** Nothing shipped changes byte for byte. The fan coil adds its power connector first (indices 1, 2, 3 before and after), and the other generated families carry no conduit connector. The #984 / #981 evidence fingerprints still pass.

## Evidence

- **`tests/test_connector_index_921.py`: 2 passed.** Both fail on main.
  - conduit → power (`add_connector`) → power (`add_electrical_connector`) gets indices `[1, 2, 3]`;
  - the fan coil's `summary()["connectors"]` equals power + conduit.
- **The wider set: 265 passed, 9 skipped.** It covers:
  - `test_famgen_factory`, `test_fan_coil_893`, `test_fan_powered_895`, `test_famfrom_ifc_standards`;
  - matrix evidence 984 / 981, `test_plugin_sync`, scaffolding;
  - the connector and IFC family modules.
- `tools/sync_plugin.py --check`: clean.

## BRANCH STATE

- Files:
  - `src/rvt/famgen/factory.py` (the `add_connector` index line and the `summary()` count only);
  - `src/rvt/famgen/skeleton.py` (the `add_electrical_connector` index line only);
  - `src/rvt/ifc/famfrom_ifc.py` (the summary count only);
  - their plugin mirrors;
  - `tests/test_connector_index_921.py` and the drop-in `tests/ci_shard.d/921-connector-index.txt`;
  - this record.
- The files are #913's territory. The program has been idle since 2026-10-03, and this was coordinated on #913.
- Shipped on merge; nothing is staged. No Revit claim (hard rule 4).
