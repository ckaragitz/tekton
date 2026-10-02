# 913 — equipment families built with their parts constrained (transformer, troffer, device, fan coil, switchboard)

Stream: **param-drive** (fragment; index `../param-drive.md`). Steer **#913** (*"structure
our code off the reference families … until everything is complete"*): every generated
family should have its parts constrained to parameter drives. This change carries the
panelboard's law (#914, `914-panel-drives.md`) to the next constructors, in product
order. No probe families were made and nothing was sent to the owner, per the steer.

## The survey: every family constructor, drives before and after

| Constructor (route) | Before this change | After (default) | Old behaviour kept |
|---|---|---|---|
| `make_panelboard` (famspec, IFC intent, prompt) | drive_law W/D + height_law H, front + zones ride (#914) | unchanged (byte-identical) | `drive="372"` / `None` |
| **`make_transformer`** (famspec, IFC intent, prompt) | **none** | Width / Depth symmetric, Height; all 41 parts + both zones ride or span | `drive=None` (byte-identical to base) |
| **`make_luminaire` troffer** (famspec, prompt, taxonomy build) | #372 first-solid chain (Length/Width on the housing; back-edges) | Length / Width symmetric, Height | `drive="372"` (byte-identical to base) / `None` |
| **`make_luminaire` downlight** (4-gon can) | none | Height only (the diamond has no axis-aligned edge) | `drive="372"` and `None` (both byte-identical to base) |
| **`make_device`** (famspec, IFC intent device plan, prompt) | none — and no dimension parameters at all | new Width / Height / Depth parameters; Width / Height on the plate with the box spanning, Depth (box back face from the wall plane) | `drive=None` (byte-identical to base; no dimension parameters) |
| **`fan_coil.make_fan_coil_unit`** (`tools/make_family.py`) | none | Width (airflow depth) / Length symmetric, Height; all 13 box parts ride | `drive=None` (byte-identical to base) |
| **`ifc.intent.make_house_switchboard`** (IFC intent) | #372 first-solid chain | Width / Depth symmetric, Height | `drive="372"` (byte-identical to base) / `None` |
| `make_archetype` cable tray / wireway / junction box / strut channel | drive_law in-plane (#919) | unchanged (byte-identical) | — |
| `make_archetype` lighting control panel, strut trapeze | in-plane + heights (+ diameters on the trapeze) | unchanged (byte-identical) | — |
| `make_archetype` conduit | none (a horizontal cylinder) | **unchanged — gap** | — |
| `make_generic_model` single prism (spec-sheet lane, prompt shapes) | #372 first-solid chain on rectangles | **unchanged — gap** | — |
| `make_generic_model(parts=…)` (IFC assembly, Claude Design export) | only caller-supplied `drives=` / `heights=` | **unchanged — gap** (no route supplies specs yet) | — |
| `ifc.famfrom_ifc.make_downlight` (facts → rfa) | none (measured cylinder/arc parts) | **unchanged — gap** | — |
| `heads.build_head_family` (annotation/tag heads) | n/a (no solids) | n/a | — |

## What was built

- **Shared helpers in `factory.py`** (new, beside `_wire_drive_specs`):
  - `_unique_names`: one drive name per part, `role k` when a role repeats.
  - `_plan_drive_spec`: a symmetric in-plane spec read off the parts' extents.
    - A part on both planes is a drive part.
    - `span` parts stretch at their insets; `stay` parts are left alone.
    - Any other part rides the end on its side; a centred unlisted part stays.
  - `_height_drive_specs`: the panelboard's Case B chain, generalised. The caption runs
    origin → top, and the `top_both` / `top_end` / `top_start` faces ride the top by
    locked heights, one plane per distinct z. A part standing on the top (`above`, a
    clearance zone) rides it too.
  - `_wire_equipment_drives` + `_born_law_after_finalize`: wire, mark
    `born_drive_law`, and note when every spec was refused; run the born in-plane law
    after `finalize`.
  - `_form_extents`: read x/y off the form's own sketch and z off its extrusion, so a
    spec never disagrees with what was drawn.
  - `_label_driven_note`: the multi-type note says the rows label the drives
    (the #914 wording).
- **Transformer** (`_transformer_drive_specs`):
  - **Width:** the body, the slot band and the top zone lie on both planes. The drip
    lid, the slot louvers and the access panel span them. The skids, cheeks, side
    louver banks and bolts ride their side. The nameplate keeps its x. The front
    working space tracks Width where it was drawn at the box's width (NEC 110.26(A)(2):
    the greater of the equipment width or 30 in; from 75 kVA up). At its 30 in minimum
    (a narrower box) it stays. The family's note states which case applies (#933 review).
  - **Depth:** the body, the skids and the top zone lie on both planes. The lid, the
    band and the side louvers span. The front hardware and the working space ride the
    front plane.
  - **Height:** origin (the skids' feet) → the top of the lid. The vent slot, lid,
    upper louver bank, upper bolts and the body's / access panel's top faces ride the
    top. The top zone stands on it.
- **Troffer:** Length / Width symmetric on the housing; Height origin → top.
  **Downlight:** Height only.
- **Device:**
  - New Width / Height / Depth parameters, valued at the record's envelope (plate W × H,
    box depth). They are 'assumed', and are surfaced in the existing UNVERIFIED note
    like the geometry.
  - Width / Height lie on the plate, and the box spans them.
  - Depth: the box's back face from the wall (origin) plane; the box front and the
    plate back are locked to that plane.
- **Fan coil** (`fan_coil.fan_coil_drive_specs`):
  - **Width / Length:** symmetric, with every box part riding or spanning.
  - **Height:** the hangers ride the top, as do the collar's, filter rack's, control
    box's and working space's top faces.
  - **Not tied:** the round parts (coil and drain stubs, conduit hub) are not tied to
    the drives, and a note says so.
- **Switchboard:** Width / Depth / Height on the lineup box.

## Evidence

- **Wired chains** (`prod.drives` / `prod.heights`, 2026 in-process):

  | Family | In-plane (edge locks; attach parts / planes / locks) | Heights (specs, face locks, locked) |
  |---|---|---|
  | transformer | Width 6; 36 / 14 / 72 · Depth 8; 37 / 10 / 74 | 23, 42, 22 |
  | transformer solid=False | Width 2 · Depth 2 | 1, 2, 0 |
  | troffer 2x4 | Length 2 · Width 2 | 1, 2, 0 |
  | downlight | — | 1, 2, 0 |
  | duplex receptacle | Width 2; 1 / 2 / 2 · Height 2; 1 / 2 / 2 | 1, 3, 0 |
  | fan coil | Width 2; 12 / 13 / 24 · Length 2; 12 / 11 / 24 | 3, 14, 2 |
  | switchboard | Width 2 · Depth 2 | 1, 2, 0 |

- **Read-back from the written file, 2026 and 2025**
  (`test_every_written_sketch_lock_lies_on_its_plane`, 13 builds × 2 releases):
  - Every sketch lock's GLine ends lie on its plane, and the count read equals the
    count authored.
  - `constraint_law.check_file == []` for every build.
  - No refusal note on any build.
  - Builds: transformer 160 locks, two-type 156, solid=False 4; troffer 2x4 / 2x2 4;
    downlight 0 (height only); receptacle / switch / junction box 8; fan coil and
    non-fused 52; cabinet-only 6; switchboard 4.
- **`tools/rvt_validate.py`:** OK, errors=0 warnings=0. That covers the transformer
  (single, types, solid=False), troffer 2x4 / 2x2 / types, downlight, receptacle,
  switch, junction box, fan coil (fused, non-fused, cabinet-only), each for 2026 and
  2025 (26 files). Each switchboard write also validated with 0 family-mode errors.
- **`tools/self_battery.py`:** 21/21 PASS.
- **Byte identity, base `ba9d57b` vs this branch** (sha256 prefix, same inputs):

  | Build | sha256 prefix (both builds) |
  |---|---|
  | transformer `drive=None` | `d9f2740a6ce820cb` |
  | two-type transformer `drive=None` | `9d5b4d200dd6611a` |
  | transformer solid=False `drive=None` | `ff24afd8fb6694c0` |
  | troffer 2x4 `drive="372"` | `e8a57f5453474cbf` |
  | troffer 2x2 `drive="372"` | `9245eccf19fa5ddb` |
  | downlight `drive="372"` | `d5035ba1ef11074a` |
  | receptacle `drive=None` | `4ea84028e583d5e4` |
  | switch `drive=None` | `cc3f007aa1395b57` |
  | junction box `drive=None` | `a8cc2a80dffae6ac` |
  | fan coil `drive=None` | `1b15927bb93ded36` |
  | non-fused fan coil `drive=None` | `3631aefc87c8130a` |
  | switchboard `drive="372"` | `947df4499f6528fe` |
  | switchboard solid=False `drive="372"` | `2cb1e63f708184eb` |

  Untouched constructors are byte-identical at their defaults: panelboard
  `d545dc0cdb4dd20b`, flush panelboard `60ce978d0581ce4e`, LCP `f95587400cfcc066`, cable
  tray `c70d141359c7aa85`, trapeze `8a81179ef44fd5cf`, conduit `1e3fc4fa8260640f`, generic
  box `31d8bad84961a904`.
- **Refusals are SHA-identical** (`tests/test_equipment_drives_913.py`, transformer and fan
  coil):
  - a part name that matches nothing, or planes off the row, equals the build without
    that spec;
  - an attach naming a missing part equals the drive without its attach;
  - a locked height off every face equals the build without it;
  - every spec refused equals `drive=None`, plus a "drives NOT wired" note.
- **Latency** (`write` included, min of 3, warmed; measured while a pytest batch ran
  on the same 4 cores, so noisy). Base → branch: transformer 0.58 → 1.00 s, troffer
  0.16 → 0.22 s, device 0.15 → 0.21 s, fan coil 0.28 → 0.51 s. The transformer's 23
  height specs are most of its cost. This is not a `surface_bench` measurement.

## Re-pinned on purpose

- `tests/test_famgen_factory.py::test_device_family_composition`: the constructor's own
  parameter list (standards=False) gains Width / Height / Depth under the default
  `drive="law"`. The old three-parameter list is pinned beside it for `drive=None`. The
  reason is written in the test.
- `spec/famspec.schema.json` gains a per-kind `drive` field: panelboard / luminaire
  `law | 372 | null`, transformer / device `law | null`.
  - `test_router::test_famspec_schema_mirrors_the_constructor_kwargs` requires the
    schema to equal each constructor's keywords.
  - The panelboard case was already red on base `ba9d57b`, because #914 added `drive=`
    without the schema field. It is green again, with the transformer, luminaire and
    device beside it.
  - The plugin's mirrored copy was re-synced.

## Honest limits

- **No desktop verdict for any of this** (hard rule 4). The family is authored; the
  assembled family is unverified. These have never been probed:
  - the transformer's 36-part Width attach;
  - the fan coil's 12-part attaches;
  - the device's Depth, a Case B drive on a work-plane-based family whose z is out of
    the wall;
  - the downlight's Height on a 4-gon can.

  The notes say "assembled family unverified" and "#787 Case B, NO desktop verdict".
- **Transformer:**
  - The front working space is not re-derived across the 30 in boundary. Tracking
    Width, it can be flexed below 30 in; staying, it can be outgrown by a wider box.
    The note says which. Its height is not re-derived either.
  - The nameplate, the lower louvers and the lower bolts keep their heights.
  - The connectors are face-hosted on the lid's top face and not separately
    constrained.
- **Fan coil:**
  - The round parts (coil / drain stubs, the conduit hub, all arc profiles) do not
    follow any drive. The hub sits on the disconnect, so a Width / Length flex leaves
    it behind until circles ride by their arc centres (#904 P4).
  - The disconnect keeps its height, because it is centred on the cabinet's height.
  - On a release without arcs (2024) the squared stubs are boxes and DO ride; the
    pinned counts are 2026.
- **Device:**
  - The plate's thickness is not driven.
  - Mounting Height remains a placement value, not geometry.
  - Width / Height / Depth are new standard-less parameters. The Electrical Fixtures
    table carries none, and the values are the record's assumed envelope.
- **Downlight** (`make_luminaire`): its Aperture / Housing Diameter are not driven. The
  4-gon is not a circle; a true can is `diameter_law` work.
- **Not wired here (gaps for the queue):**
  - the conduit archetype;
  - the single-prism `make_generic_model`, which still uses the #372 chain on the
    spec-sheet lane;
  - `make_generic_model(parts=…)` from the IFC / Claude Design routes;
  - `famfrom_ifc.make_downlight`.

## Review of #935 (🟡)

- **One source for the note.** Whether the working space tracks is now read from the
  wired Width spec (is the zone one of its drive parts), not recomputed separately.
- **Crossing types are named.** In a multi-type family the zone is wired for the
  primary type. Any type row whose Width lands on the other side of the 30 in line is
  now named in the note: tracking, a row under 30 in; staying, a row over 30 in. Test:
  `test_a_multi_type_transformer_names_the_rows_that_cross_30_in`.
- **Not acted on.** `_DRIVE_EPS` (1e-6 ft) could matter only for a box within
  1.2e-5 in of 30 in, but not equal to it. Catalog widths are 2-decimal inches.

## BRANCH STATE

**Files written**
- `src/rvt/famgen/factory.py`:
  - the shared helpers above;
  - `make_transformer(drive=)` and `_transformer_drive_specs`;
  - `make_luminaire(drive=)`;
  - `make_device(drive=)`.
- `src/rvt/famgen/fan_coil.py`: `make_fan_coil_unit(drive=)` and `fan_coil_drive_specs`.
- `src/rvt/ifc/intent.py`: `make_house_switchboard(drive=)`.
- `plugin/lib/…`: mirrors (`tools/sync_plugin.py`).
- `tests/test_equipment_drives_913.py` (new) and
  `tests/ci_shard.d/913-equipment-drives.txt` (new).
- `tests/test_famgen_factory.py`: the device re-pin above.
- This fragment.

- `spec/famspec.schema.json` and its plugin mirror: the `drive` field.

**Gates**
- `tools/sync_plugin.py` rebuilt the plugin; `--check` is clean.
- `plugin/scripts/validate_plugin.py` PASS (25 assertions); `check_portable_paths` ok.
- `rvt_validate`: 0 errors / 0 warnings on 26 files.
- `self_battery`: 21/21.
- **pytest batch 1:** 1400 passed / 0 failed / 58 skipped. Files: the new file,
  `conftest_scaffolding`, `constraint_law` + 910, `panel_drive_law_914`,
  `panel_drives_914`, `archetype_drives_913`, `family_anatomy_837`, `ifc_intent` +
  units + `classify_equipment`, `intent_device_plan` / `faulted` /
  `schedule_scalars`, `prompt_intent` + 775, `famgen_factory`, `fan_coil_893`,
  `mep_devices` / `conduit`, `place_fixtures`, `famfrom_ifc_standards`,
  `famgen_archetypes` / `catalog`, `ifc_pset_params`, maker 739 / 742, prompt 845 /
  855, taxonomy ×4, `rvt_to_ifc_kind_agreement`, `provenance`, `height_law_787`,
  `drive_law_904`, `plugin_sync`, `bootstrap`, `coldstart`.
- **pytest batch 2:** 775 passed / 4 failed / 47 skipped. Files: `router`,
  `frontdoor`, `convert` + combo, `electrical`, `engine`, `job`,
  `router_load_release`, `drive_follow_904`, `famgen_parametric`, transformer
  879 / 630, `luminaire_sizes_682`, clearance 882 / 819, standards ×3, `instance_rows`,
  `param_profile` ×3, determinism 168 / 794, `identity`, `edit_family_mass`,
  `estorage` / `shared_params` 866.
  - The 4 failures were the famspec schema test above (panelboard already red on base).
    The schema fix turned them green.
- **After the fix**, `router` + `plugin_sync` + `bootstrap` + `coldstart` +
  `conftest_scaffolding` + the new file: 262 passed / 5 skipped.

**Shipped vs staged:** wired by default. No viewer or desktop batch was staged (steer
#913: no probe families to the owner). Authored; the assembled family is unverified.
