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
- **The wider set: 265 passed, 9 skipped** before the nits below; with them, 13 modules (921, 863, standards, apply_safe, factory, fan coil, fan-powered, IFC standards, matrix 984 / 981, cap tags, plugin sync, scaffolding) give **417 passed, 6 skipped**. The first set covers:
  - `test_famgen_factory`, `test_fan_coil_893`, `test_fan_powered_895`, `test_famfrom_ifc_standards`;
  - matrix evidence 984 / 981, `test_plugin_sync`, scaffolding;
  - the connector and IFC family modules.
- `tools/sync_plugin.py --check`: clean.

## Also in this PR: #1038's review nits

- **`standards.apply()`** reads a bare-string `skip=` as one name. Before, `p.name in "Voltage Rating"` was a substring test, so it also skipped a row named `Voltage`. #1038 normalised it only on the `apply_safe` path. Test: `test_apply_itself_reads_a_bare_string_skip_as_one_name`, which fails without the fix.
- **The `solid_box_brep` docstring** now gives the whole GStep law #1037 measured:
  - face tag 0 = key `[2]` (End), tag 1 = key `[1]` (Start);
  - edge tag 3 = `[1,i,0]`, where `i` is the loop's first curve.

## BRANCH STATE

- Files:
  - `src/rvt/famgen/factory.py` (the `add_connector` index line and the `summary()` count only);
  - `src/rvt/famgen/skeleton.py` (the `add_electrical_connector` index line only);
  - `src/rvt/ifc/famfrom_ifc.py` (the summary count only);
  - their plugin mirrors;
  - `tests/test_connector_index_921.py` and the drop-in `tests/ci_shard.d/921-connector-index.txt`;
  - #1038's nits: `src/rvt/famgen/{standards,geometry}.py` (and mirrors), `tests/test_standards_facts_863.py`;
  - this record.
- The files are #913's territory. The program has been idle since 2026-10-03, and this was coordinated on #913.
- Shipped on merge; nothing is staged. No Revit claim (hard rule 4).
