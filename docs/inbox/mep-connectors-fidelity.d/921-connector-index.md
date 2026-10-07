# 921 — connector counts and `m_index` span every domain

Stream **mep-connectors-fidelity** (tech-lead session, 2026-10-07). Closes #921, the hand-off from #920 (#894) on #913.

## What changed

**The defect.** Power connectors live in `doc.connectors` and conduit connectors in `doc.mep_connectors`. Three counters looked only at the first:
- `factory.add_connector` numbered `m_index` as `len(doc.connectors) + 1`;
- so did `FamilyDoc.add_electrical_connector`;
- `FamilyProduct.summary()["connectors"]` and the IFC downlight's summary counted only power connectors.

So a power connector added after a conduit connector reused its `m_index`, and the fan coil reported 1 connector while its file held 2. The reference corpus numbers `m_index` continuously across domains. `mep_connectors.add_conduit_connector` already did.

**The fix.** All four now count `len(doc.connectors) + len(doc.mep_connectors)`.

**Shipped output.** It is byte-identical. The fan coil and the fan-powered box each add their power connector before their conduit connector, so their indices are `[1, 2]` before and after. No other generated family carries a conduit connector. The #984 / #981 evidence fingerprints still pass, and #1039's reviewer rebuilt both families from main and from this head: the sha256 values match.

## Evidence

- **`tests/test_connector_index_921.py`: 3 passed.** All three fail on main.
  - conduit → power (`add_connector`) → power (`add_electrical_connector`) gets indices `[1, 2, 3]`;
  - the fan coil's `summary()["connectors"]` equals power + conduit.
  - nesting refuses a child whose only connectors are conduit ones.
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

## Also fixed after #1039's review

- **`nest.py`'s guard** ("nesting a family with connectors is not supported") read power connectors only. A conduit-only child would have got past it. It now reads every domain. There is a test.
- **The `solid_box_brep` docstring** names the `[1,i,0]` rail as on the cap at the higher offset (the End cap there), not "the start rail".
- **Not changed:** `tools/render_probes.py` still counts `len(prod.doc.connectors)` in four dev-probe summaries. Those are panel/box probes with no conduit connector, so no number they print is wrong today. They are named here so a future conduit probe counts both lists.

## BRANCH STATE

- Files:
  - `src/rvt/famgen/factory.py` (the `add_connector` index line and the `summary()` count only);
  - `src/rvt/famgen/skeleton.py` (the `add_electrical_connector` index line only);
  - `src/rvt/ifc/famfrom_ifc.py` (the summary count only);
  - their plugin mirrors;
  - `tests/test_connector_index_921.py` and the drop-in `tests/ci_shard.d/921-connector-index.txt`;
  - #1038's nits: `src/rvt/famgen/{standards,geometry}.py` (and mirrors), `tests/test_standards_facts_863.py`;
  - `src/rvt/famgen/nest.py` (the connector guard line only, and its mirror);
  - this record.
- The files are #913's territory. The program has been idle since 2026-10-03, and this was coordinated on #913.
- Shipped on merge; nothing is staged. No Revit claim (hard rule 4).
