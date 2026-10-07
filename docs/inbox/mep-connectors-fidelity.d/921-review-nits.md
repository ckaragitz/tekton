# 921 follow-up — the final review nits of #1039

Stream **mep-connectors-fidelity** (tech-lead session, 2026-10-07). Refs #921 #1037.

- **A test for the IFC downlight's summary** (`DownlightProduct.summary()`), which #1039 changed without one. It now counts both connector lists: `test_the_ifc_downlight_summary_counts_every_domain`.
- **The `solid_box_brep` docstring** names both branches. The `[1,i,0]` rail sits on the cap at the higher offset: the End cap with `end_on_top`, the Start cap without.
- **The #921 record's 13-module count** is 418, not 417: the nest test was added after the count was taken.

## Evidence

- `tests/test_connector_index_921.py`: **4 passed**.
- `tools/sync_plugin.py --check`: clean.

## BRANCH STATE

- Files:
  - `src/rvt/famgen/geometry.py` (a docstring only) and its mirror;
  - `tests/test_connector_index_921.py`;
  - `docs/inbox/mep-connectors-fidelity.d/921-connector-index.md` (one count);
  - this record.
- Shipped on merge. No behaviour change, no Revit claim.
