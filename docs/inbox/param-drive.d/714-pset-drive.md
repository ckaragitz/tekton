# #714: carried IFC pset parameters drive the part they describe

Stream: param-drive. Issue #714 (P0). Base: `main` 7d2fcde. Branch `fix-714`.

## What was built

#711/#769 put an IFC's property sets on the family as typed parameters, but only as
values. This change makes each LENGTH parameter drive the measured part it describes,
whenever that can be determined without guessing.

- `src/rvt/ifc/pset_drive.py` (new). `plan(parts, collected)` takes the assembly lane's
  measured parts (`AssemblyModel.to_parts()`) and `pset_params.collect()`, and matches
  each carried parameter to a `(part, axis)` pair. A parameter matches only when all of
  these hold:
  - its pset is attached to exactly one product;
  - exactly one measured part has that product's name;
  - the value equals one of that part's spans to `SPAN_TOL` = 1e-6 ft, which is float
    noise and never a snap.

  When a value equals two spans (a square part), only an axis word in the parameter's
  name decides: `Width` = x, `Depth` = y, `Height` = z. Otherwise the parameter stays a
  value. One span cannot be driven by two parameters. Lying cylinders (`cylinder_x/_y`)
  are refused, because their sketch is not what Revit draws (#591 round 4). Polygons and
  vertical cylinders are z only. The plan emits the factory's own declarative specs:
  - **x / y**: `_wire_drive_specs` → `drive_law.wire_linear_drive`, the
    desktop-verified #787 / #904 in-plane law. The planes sit at the part's OWN faces.
    The drive is made symmetric (`wire_symmetric`) only when the part is centred on the
    origin centre plane, which is the multipart way from #913.
  - **z**: `_wire_height_spec_list` → `height_law.wire_height_specs`, #787 Case B. The
    cap faces are locked to two horizontal planes held by a labelled elevation
    dimension. A part off the origin elevation has its base held by a LOCKED unlabelled
    height (the panelboard chain from #914).

  This does NOT use the old #372 `param_drive` chain. Each driven axis carries exactly
  one labelled dimension whose `m_paramId` is the carried parameter.
- `src/rvt/famgen/factory.py`: `make_generic_model(parts=…, settle_drives=True)` makes
  drives ALL OR NOTHING per drive group. The group is the spec's `"group"`, else its
  caption. The factory builds, and finds every group the wiring refused in whole or in
  part. A partial refusal is an in-plane drive whose symmetric EQ failed, or a height
  chain whose held base wired but whose labelled height did not. The factory then
  rebuilds without those groups until nothing is refused. `prod.drive_settle =
  {"wired": [...], "refused": {group: reason}}`. The default is `False`, which leaves
  every existing caller unchanged.
- `src/rvt/ifc/pset_params.py`: each source record also carries
  `"products": [names]` as a list. That way a pset shared by several products, or a
  product name containing a comma, is not misread from the `", "`-joined `product`
  string. Nothing else changed.
- `src/rvt/frontdoor/router.py` (`_assembly_rfa`, the IFC / Claude Design multi-part
  lane): plans when psets were carried, and passes `drives` / `heights` /
  `settle_drives` ONLY when something matched. So an IFC with no matching pset reaches
  the builder with exactly the pre-#714 kwargs. It folds the factory's verdict into the
  rows (`settle_rows`) and reports one caveat per parameter: `X DRIVES <part> along
  <axis>: …` or `X is a value only: <reason>`. It also writes `pset-drives.json` beside
  the `.rfa`. The headline says the chain is AUTHORED, that the family has no
  desktop-Revit verdict, and that nothing is called editable (hard rule 4).
- `tools/self_battery.py`: new row `ifc_pset_drives` (a pad plus an off-centre tank;
  PadWidth x, TankDepth y, TankHeight z with a held base).
- `tests/test_pset_drive_714.py` (new; 15 test functions, 28 cases) and
  `tests/ci_shard.d/714-pset-drive.txt`. The fixture is OURS, authored in-test: a
  millimetre IFC4 with four tessellated boxes shaped like a transformer. It has no
  owner file and no sample.

## Evidence

Per-parameter result on the fixture: route `ifc → rfa`, which defaults to 2026; 2025
and 2024 give the same result.

| parameter | pset on | result | part / axis | reason (abridged) |
|---|---|---|---|---|
| PadWidth | pad_slab | DRIVES | pad_slab x | = x span 78.74 in; symmetric (part centred) |
| PadDepth | pad_slab | DRIVES | pad_slab y | = y span 70.87 in; off-centre, planes free |
| BodyWidth | tank_shell | DRIVES | tank_shell x | = x span 62 in; symmetric |
| BodyDepth | tank_shell | DRIVES | tank_shell y | = y span 39.37 in; off-centre |
| BodyHeight | tank_shell | DRIVES | tank_shell z | = z span 59.06 in; base held at pad top by a locked height |
| FrontClearance | clearance_front_volume | DRIVES | … y | = y span 122 in |
| TopClearance | clearance_top_volume | DRIVES | … z | = z span 36 in; base held |
| BodyLength | tank_shell | value only | | 62.99 in, equal to none of the spans |
| SharedSpan | tank_shell + pad_slab | value only | | pset on 2 products: which one is not stated |
| InsulationClass | tank_shell + pad_slab | value only | | text parameter |

- Read back from the WRITTEN file (2026 / 2025 / 2024): 10 sketch-edge locks, 0 off
  their plane; ≥ 4 cap-face locks, 0 off their plane. `constraint_law.check_file == []`.
  The family-mode validator reports 0 errors. `tools/rvt_validate.py` on the 2026 and
  2025 route outputs: ok, 0 errors / 0 warnings / 2 info.
- Labels: each of the 7 driven parameters labels exactly one `LinearDimString`
  segment. No value-only parameter labels any. The type row keeps the GIVEN values.
- All-or-nothing: a probe refuses BodyWidth's symmetric EQ, then BodyDepth's in-plane
  drive, then BodyHeight's labelled height after its held base wired. In each case the
  victim is reported refused, and the sha256 equals the build with the victim's specs
  never requested. With everything refused, the bytes equal the build with no drives.
  On the route, a refused TopClearance is reported as `value only` with "factory
  refused", and the headline reads 6 of 10.
- Determinism: two builds and two route runs give identical sha256.
- **Other routes are byte-identical to base 7d2fcde.** The same script was run against
  a `git archive` of 7d2fcde and against this branch; sha256 prefixes:

  | product | base | branch |
  |---|---|---|
  | archetype cable_tray | 0121098d8eeb0398 | same |
  | archetype wireway | ce3e7c7a428799ac | same |
  | archetype conduit | f37465c3497af06d | same |
  | single-prism generic | 5602e160cb69148a | same |
  | multipart generic | 0f81709aa2466a19 | same |
  | IFC route, no psets (2026) | 97f8fb1ba066e542 | same |
  | IFC route, no psets (2025) | e3b613484e0d94fc | same |
  | IFC route, text-only pset | 9ad55193ef0ad3ea | same |
  | IFC route, unmatched length pset | 615bee207d630842 | same |
  | `inputs/ifc/chicago-plenum-downlight.ifc` route | 47a0baf19f9ad4ad | same (its 7 psets are text/number: all value only, reported) |

- IFC route build time for the full pset fixture (5 runs in-process, median): base
  0.212 s, branch 0.281 s (+69 ms). That is seven drive chains plus the settle pass,
  which is one build when nothing is refused. The no-pset IFC route is unchanged
  (0.95 s → 0.96 s on a cold first route).

## Gaps / open questions

- **No desktop verdict.** A multi-part family with pset drives (several parts, held
  bases, symmetric and free in-plane drives side by side) has never been opened in
  Revit. "DRIVES" means the chain is AUTHORED. No route calls the result editable
  (hard rule 4). Nothing was staged for the viewer or desktop (steer #765).
- **Per-part Width / Depth / Height drives without psets** (the optional item from
  steer #913) were NOT done. An IFC part with no pset gets no drive, so this remains a
  gap. It needs a naming scheme for per-part parameters that does not collide with the
  assembly's own Width / Depth / Height, which report the bounding box.
- A pset attached to a product that the lane decomposed into several solids
  (`name [i/n]`) stays a value. Driving the decomposition as one body would need a
  shared-plane chain across its solids.
- Matching is exact (1e-6 ft). An IFC value rounded differently from its own mesh,
  such as a 1/64 in rounding, is reported as "off, never snapped" rather than driven.

## BRANCH STATE

- Files: `src/rvt/ifc/pset_drive.py` (new), `src/rvt/ifc/pset_params.py`,
  `src/rvt/famgen/factory.py` (`settle_drives`, `_settled_build`, `_group`),
  `src/rvt/frontdoor/router.py` (`_assembly_rfa`), `tools/self_battery.py` (one row),
  `tests/test_pset_drive_714.py` (new), `tests/ci_shard.d/714-pset-drive.txt` (new),
  `plugin/lib/…` mirrors (sync), and this fragment.
- Not touched: `constraint_law.py`, `geometry.py`, `nest.py`, `angular_law.py`,
  `famload.py`.
- Gates: test_pset_drive_714 + conftest_scaffolding
  + drives_rest_913 + drive_law_904 + height_law_787 + ifc_assembly* +
  pset*/ifc_family + router* (RVT_SKIP_LARGE=1) gave 499 passed / 15 skipped. The one
  failure was test_plugin_sync, run before the sync; it passes after. `sync_plugin.py`
  rebuilt; `--check` clean; `validate_plugin.py` PASS (25); `check_portable_paths` ok; `tools/self_battery.py` 27 / 27 PASS (incl. the new
  `ifc_pset_drives` row); after the sync, plugin_sync + pset_drive_714 +
  conftest_scaffolding: 57 passed.
- Shipped: wired by default on the IFC assembly lane, and only when a pset matches.
  Staged: nothing.
