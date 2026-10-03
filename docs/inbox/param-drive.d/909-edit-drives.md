# #909 — a family edit moves the geometry its parameter drives

Stream: param-drive. Refs steers #908 / #913 (*"the rest of the elements need to
be constrained and move with it"*). Closes #909.

## The defect, measured

The rfa edit lane (`rvt.convert.modify_family`, also behind
`rvt.convert.edit_family` and `route run --rfa … --edit`) wrote a parameter's
value into the type table and nothing else. On a default generated strut trapeze,
`Strut Length` = 36 in gave this result: the parameter read 3.0 ft, but its
labelled `LinearDimString` (1543) still stored 2.5 ft. Its two reference
planes, every locked strut edge, and the rods, washers and nuts that follow at
`Rod Inset` all stayed at 30 in. `drive_law` refuses to author that mismatch.
The control test (`test_the_old_lane_left_the_mismatch_the_rebuild_removes`)
pins it: `(stored, value, agree) == (2.5, 3.0, False)`.

The old caveat ("type-table value only … regenerate from the facts sidecar")
named a sidecar that the edit lane never read. No one checked it against Revit.

## Design: rebuild by the family's own generator, proven by reproduction

Re-solving the graph in place would make a second, unverified copy of what the
generators already know: which planes exist, which locks, the followers, the
formula children, and the settle laws. The rebuild route reuses that knowledge.

New module: `src/rvt/convert/family_regen.py`.

1. **Recover the generator and spec from the file.** A generated `.rfa` does not
   carry its famspec, so the spec is read back from the file:
   - **Generator**: the parameter captions are matched against every generator
     we have. These are every `ARCHETYPES` product (`make_archetype`) and the
     #917 nested-hardware children (`make_hex_nut`, `make_washer`).
   - **Values**: parameter value ÷ the unit.
   - **Name**: the PartAtom title.
   - **`start_id`**: the self-`Family` id, which equals `start_id` in every
     generator.
   - **Options**: `nested_hardware` when the file has `FamilyInstance`s, and the
     clearance prompt when `Show Clearance` is present.
2. **Prove before rebuilding.** The generator runs on the recovered spec and
   writes under the input's own file name. The only path-dependent byte is
   `BasicFileInfo`'s last-save name; the rest is deterministic, measured. The
   output must be sha256-identical to the input. If it is not, nothing is rebuilt
   on a guess. Examples that fail the proof: a Revit-born family, one edited by
   hand since (even a text edit), a spec value that no parameter carries (a
   trapeze's `Lip`), a 2025/2024 file.
3. **Rebuild at the new value.** The output is byte-identical to building at that
   value directly; the tests assert sha256 equality against an independent
   `make_archetype(…)` / `make_hex_nut(…)` call. Every other dimension stays where
   the file had it. Other ops in the same edit are applied on top by value:
   text, renames, non-input parameters.
4. **Derive which parameter is an input, never from a list.** `caption_map`
   perturbs each archetype dimension by one unit:
   - A family parameter (`family_params` / `standard_values`) that moves with
     exactly one dimension, slope = that dimension's unit, **is** that dimension.
   - Anything else is **derived**: `Rod Length` reads seven dimensions, and
     `Nut Across Flats` = 1.5 × rod diameter.
   - **Drivers** are the captions that the archetype's `drives` / `heights` /
     `diameters` / `runs` registries label, including `follow` captions.
5. **Settle law.** A trapeze's settle law ties three values:
   Strut Length = Rod Spacing + 2 × Rod Inset. The edit leaves the first
   non-driver dimension, Rod Spacing, for the generator to re-derive. This is
   what the graph itself does when Strut Length flexes and the rods follow at
   Rod Inset. Editing Rod Spacing, a non-driver, re-derives Strut Length instead.
   The record states which dimension was re-derived (`re_derived_by_generator`).
6. **Name rule** (revised in review, PR #993). The input's family and type
   names are always kept, because a renamed family reloads as a second family
   beside the original. If the input carried the generator's own
   dimension-derived name ("Strut Trapeze 30 in 2 Tier"), the kept name now
   describes the old size. The result says so in `regeneration.name_note` and
   in a degradation, unless the same edit renames the family.

**Formula inputs** (`Nut Across Flats` → `Nut Half Across Flats`, #948):

- **Rebuild path**: the generator rewrites the formula child and the hexagon it
  labels.
- **Value path**: `modify_family._formula_followups` re-evaluates every formula
  parameter fed by an edited value. It uses the file's own `m_oExpression` trees
  (`rvt.famgen.formula.evaluate`) on every row set written (each type row, plus
  the current defaults), and records a note.
- **Setting a formula parameter itself** is refused by name: Revit computes it.

**Value path: never a silent mismatch.** When the rebuild is not possible, every
set-param whose parameter labels a dimension gets an explicit degradation. The
label can be direct, or through a formula parameter (`label_report` over
`LinearDimString` / `RadialDim` / `AngularDim`). The degradation names:

- the dimension(s) and the value they still measure,
- that the planes, locked edges and faces, and followers did not move,
- why no rebuild was possible,
- that Revit's behaviour on such a file is unverified.

An edit of a parameter that the generator computes says that the generator
computes it, and from which inputs.

**Grammar fix found on the way.** `set Strut Length to 36 in` was parsed as
parameter `Strut` with value `Length to 36 in`: the lazy `_RE_SET` cut every
multi-word caption at its first word. `_match_set` now takes the longest caption
of the family's own that the clause starts with. Single-word captions parse
exactly as before.

**Gate added to the edit result.** `validation.rfa.labels = {n, disagree}` is
written on every set-param edit.

## What is supported, and what carries a caveat

| family | an edit of a generator input | otherwise |
|---|---|---|
| archetype products (strut trapeze solid + #917 nested, cable tray, strut channel, wireway, junction box, lighting control panel, conduit) at the native release, unedited since generation | **rebuilt**: planes, labelled dims, locked edges/faces, followers, formula children agree; sha256 = direct build | derived parameter → "the generator computes it from …" |
| #917 children written standalone (hex nut, square washer) | **rebuilt** (the hexagon + its formula child) | formula parameter → refused by name |
| a generated family edited since (any byte changed), or a spec value no parameter carries (e.g. trapeze `Lip` ≠ 0.5 in) | value only + explicit caveat ("does not reproduce the input byte for byte") | |
| catalog equipment, labelled drives measured with `label_report` on each default build: panelboard / transformer / wiring device Width, Depth, Height; luminaire and fan coil Length, Width, Height. The fan-powered box labels no dimension. | value only + explicit caveat ("no generator of ours matches"). Their dimensions are catalog FACTS. | |
| IFC-built families (#714 pset drives), single-prism generic models | value only + explicit caveat (the IFC / caller geometry is not in the file) | |
| a 2025 / 2024 family | the edit lane cannot read it at all yet (`Document.from_file`: "unexpected Partitions header v=9"); a pre-existing gap, refused before any rebuild question arises | |
| a generator refusal at the new value (e.g. Strut Length 4 in, under the 6 in minimum) | delivered by value with the refusal quoted (hard rule 1) | |

## Evidence

Measured in this worktree, native 2026. Every rebuilt file passed: family-mode
VALID with 0 errors; `label_report` with all labels agreeing;
`constraint_law.check_file` == [] (on nested units too); `tools/rvt_validate.py`
with 0 errors; re-read proven; sha256 equal to the direct build.

| edit | route | labels (n / disagree) | wall |
|---|---|---|---|
| trapeze Strut Length 36 in | rebuilt (Rod Spacing re-derived) | 17 / 0 | 2.5 s |
| trapeze Tier Spacing 18 in (height, #787 B) | rebuilt | 17 / 0 | 2.2 s |
| trapeze Rod Diameter 0.5 in (diameter, #916) | rebuilt | 17 / 0 | 1.9 s |
| trapeze Rod Inset 4 in (follow, #904) | rebuilt (Rod Spacing re-derived) | 17 / 0 | 1.9 s |
| trapeze Number of Tiers 3 | rebuilt | 23 / 0 | 2.6 s |
| nested trapeze Rod Diameter 0.5 in | rebuilt (re-nested) | 17 / 0 (+ 2 nested units CL []) | 3.0 s |
| conduit Outside Diameter 1.5 in | rebuilt | 2 / 0 | 0.2 s |
| cable tray Tray Width 18 in | rebuilt | 2 / 0 | 0.6 s |
| junction box Box Width 8 in | rebuilt (Box Height held) | 2 / 0 | 0.4 s |
| hex nut Nut Across Flats 0.75 in (formula input) | rebuilt; Half = 0.375 in | 4 / 0 | 0.3 s |
| trapeze edited since (Material), Strut Length 36 in | value + caveat | 17 / 1 (said) | — |
| renamed hex nut, Nut Across Flats 0.75 in | value + formula followed + caveat | Half label disagrees (said) | — |
| #714 pset family, PadWidth 5 ft | value + caveat | disagree (said) | — |

A rebuild costs one extra build + write, the reproduction proof (about 1–2 s on
a trapeze). A family no generator matches costs only a caption comparison.

## The matrix change (patch; `src/rvt/frontdoor/matrix.py` and `docs/product/PERMUTATION-MATRIX.md` were held by another PR)

*Applied when shipped (PR after #989 / #991 merged): the cell caveat and evidence in `matrix.py` as below; the doc row as one table-cell sentence carrying the same content.*

**`src/rvt/frontdoor/matrix.py`**, the `prompt + rfa -> rfa` (`rfa_modify`) cell.
Replace the caveat string

```python
          "a DIMENSION edit changes the type-table value only (generated "
          "families carry no constraint graph): the geometry-true path is "
          "regeneration from the facts (prompt->rfa) -- recorded on every "
          "length edit",
```

with

```python
          "a DIMENSION edit of a family OUR generators wrote is GEOMETRY-TRUE "
          "(#909): generated families carry driving constraint graphs -- "
          "archetypes (rvt.famgen.archetypes drives/heights/diameters/runs): "
          "strut trapeze Strut Length, Rod Inset (rods/washers/nuts follow), "
          "Tier Spacing, Strut Height, Strut Thickness, Washer Thickness, Rod "
          "Above Top Tier, Rod Below Bottom Nut, Rod Diameter; cable tray Tray "
          "Width, Length; strut channel Section Width, Length; wireway Wireway "
          "Width, Length; junction box Box Width, Box Height; lighting control "
          "panel Cabinet Width, Cabinet Height, Sheet Thickness; conduit Outside "
          "Diameter, Length; the #917 hex nut Nut Across Flats (through the "
          "formula Nut Half Across Flats) and Nut Height, the washer Washer "
          "Size / Thickness; catalog equipment (panelboard, transformer, "
          "luminaire, device, fan coil, fan-powered box) Width / Depth / Height "
          "(luminaire Length / Width / Height); IFC pset drives (#714) -- and an "
          "edit of a GENERATOR INPUT is applied by REBUILDING the family from "
          "its generator, after the generator reproduced the input byte for "
          "byte from the spec recovered from the file (rvt.convert.family_regen; "
          "byte-identical to building at the new value). Not rebuilt -- catalog "
          "equipment, IFC-built families, a family edited since generation, "
          "foreign families, 2025/2024 files: the value changes and an explicit "
          "caveat names every dimension left at the old value. No desktop "
          "verdict exists for an edited or rebuilt family (hard rule 4)",
```

Add the evidence entries

```python
          "test:tests/test_edit_drives_909.py",
          "record:docs/inbox/param-drive.d/909-edit-drives.md",
```

to the cell's evidence tuple (after `"test:tests/test_router.py",`).

**`docs/product/PERMUTATION-MATRIX.md`**, line 84 (`prompt + rfa → rfa`).
Replace the sentence

> Dimension edits change the value only (no constraint graph — regenerate for true geometry).

with

> Dimension edits of families our generators wrote are geometry-true (#909):
> generated families carry driving constraint graphs. The drivers are:
> - archetypes: trapeze Strut Length / Rod Inset / Tier Spacing / Strut Height /
>   Strut Thickness / Washer Thickness / Rod Above / Rod Below / Rod Diameter;
>   tray Tray Width / Length; channel Section Width / Length; wireway Width /
>   Length; junction box Box Width / Height; LCP Cabinet Width / Height / Sheet
>   Thickness; conduit Outside Diameter / Length;
> - the #917 hex nut Across Flats (through its formula child) and the washer;
> - catalog equipment Width / Depth / Height;
> - IFC pset drives (#714).
>
> An edit of a generator input rebuilds the family from its generator, after the
> generator reproduced the input byte for byte (`rvt.convert.family_regen`;
> = the direct build at the new value). Catalog equipment, IFC-built, since-edited,
> foreign and 2025/2024 families change the value only, and an explicit caveat
> names the dimension(s) left at the old value. No desktop verdict for an edited
> family (hard rule 4).

Also add `tests/test_edit_drives_909.py` to that row's evidence column.

## Open questions / follow-ups

- **Catalog equipment** (panelboard Width…): the drives exist, but the
  dimensions are catalog facts. Rebuilding at a user width would break the fact
  tier, so these stay value-only. The honest product question: does an edit of a
  catalog dimension mean "a different catalog item" (re-resolve) or "a custom
  size" (`given`)? That is product-level and needs a steer before any code.
- **Since-edited generated families** do not reproduce, so they are not rebuilt.
  One fix: replay every non-generator difference (text parameters) onto the
  reproduction before comparing. Another: embed the generator spec in the family
  (that changes every generated byte; it needs its own single-variable round).
- **2025 / 2024 families**: the edit lane cannot read them
  (`Document.from_file` on a 2025 partition). The rebuild would need
  `release_build_context` on the year's base. It is wired as a refusal by name
  in `_release_context` until the lane reads those files.
- **Revit's side is unverified.** No desktop verdict exists on whether Revit,
  flexing the original family, produces the same geometry as the rebuild.
  Nor on whether a value-only edit's mismatch is repaired or rejected on open.

## Review fixes (PR #993)

An independent review of PR #993 found two blocking issues and four nits.
All six are fixed on the same branch.

1. **Rule 1 regression: rename after a rebuild (blocking).** After a rebuild,
   `rename-family` stayed in `plan.rest`. A generated family's self-Family
   `m_name` is empty, so the rename changed no record, and
   `apply_family_edits` raised "the ops produced no record changes". The
   route then delivered nothing. `set Length to 20 ft; rename family to
   MyConduit` (either order) and the trapeze equivalent all raised.
   - Fix: `apply_family_edits` treats a family rename that changes no record
     as PartAtom plus file name only. It copies the bytes and patches
     PartAtom. This also fixes `rename the family to X` alone on a generated
     family, which raised on the base too.
   - The post-rebuild step is now `_apply_rest`, wrapped so that any exception
     falls back to the value path for the whole edit. The reason is stated in
     `regeneration.reason` and in the value-only caveat. Nothing is raised and
     nothing is withheld.
   - Tests cover both orders on the conduit and the trapeze, a rename alone,
     a type rename in both orders, and an injected post-rebuild failure.
2. **Matrix overclaim (blocking).** The cell claimed Width / Depth / Height
   drives for the fan-powered box, which labels none, and Depth for the fan
   coil, which labels Length / Width / Height.
   - Fix: the claim is generated from `matrix.EDIT_DRIVES_909`, which lists
     each family's builder and its labelled captions, measured.
   - A parametrized test builds every listed family at its defaults and
     asserts that `label_report`'s captions equal the claim, so the claim
     cannot drift. It also asserts that the archetype claims are the
     generator's own drivers.
   - The fan-powered box is named as labelling no dimension.
   - The doc row in `PERMUTATION-MATRIX.md` is updated to match.
3. **Silent rename on rebuild (nit).** The rebuild kept the auto name only
   when the user had chosen one, so "…30 in…" became "…36 in…" and reloaded as
   a second family.
   - Fix: names are always kept (see Name rule).
   - The byte-identity claim is restated as "identical to a direct build at
     the new value WITH the input's name". The tests build the direct control
     with the input's family name.
4. **Stale LENGTH_CAVEAT (nit).** "Regenerate from the facts sidecar" is gone;
   the lane never read that sidecar.
   - There is one geometry statement per edit. A rebuilt edit gets
     `REBUILT_NOTE`. A value-only edit of a labelling parameter gets only the
     full `VALUE ONLY` caveat, and its unit note drops the short caveat.
   - An unlabelled length keeps the short caveat.
   - The pinned strings in `test_edit_family_mass_659` / `_size_668` were
     updated.
5. **Caption grammar (nit).** A caption match must be followed by an explicit
   delimiter (`to` / `=` / `of type`).
   - Otherwise, a clause with an explicit delimiter names its parameter as
     everything before that delimiter. `set Material Finish to galvanized`
     names `Material Finish`, which is refused by name, and no longer sets
     Material = "Finish to galvanized".
   - Only then does a caption followed by a bare value apply
     (`set Width 600 mm`).
6. **Cleanups.**
   - The `test_conftest_scaffolding.py` key spacing is restored.
   - **Conduit diameters.** The conduit's `Nominal Diameter` and
     `Outside Diameter` both map to the one archetype dimension
     `diameter_in`. Both are recovered as inputs, and an edit of either
     rebuilds the same diameter. Only `Outside Diameter` labels a dimension.
     If one edit sets both to different values, the later op wins.

## BRANCH STATE

Branch `fix-909`, pushed as **PR #993** (head `33853db` at review). The review
fixes are commits on `fix-993` on top of that head, local, not pushed (per the
engineer brief).

**Files written**
- `src/rvt/convert/family_regen.py` (new): `label_report`,
  `formula_followups` / `formula_dependents`, `caption_map`, `recover`,
  `plan_rebuild`, `rebuild` (names kept; `name_note`), `value_only_caveat`,
  `derived_caveat`
- `src/rvt/convert/modify_family.py`:
  - the module docstring's geometry paragraph;
  - `LENGTH_CAVEAT` (stale advice removed) / `REBUILT_NOTE`;
  - one geometry statement per edit;
  - the inventory's `formula` flag, and the refusal of a formula parameter;
  - `_match_set` / `_RE_SET_DELIM` (the multi-word caption grammar, with a
    delimiter required);
  - `_formula_followups` in `apply_family_edits`;
  - the PartAtom-only family rename;
  - `_apply_geometry_true` / `_apply_rest` (with a value-path fallback) /
    `_value_path_caveats` / `_rebind_ops` in `modify_family`;
  - the `labels` gate.
- `src/rvt/frontdoor/matrix.py`: `EDIT_DRIVES_909` + `_EDIT_DRIVES_CLAIM`
  (the `rfa_modify` cell's caveat, generated from measured data) and the
  #909 evidence; `docs/product/PERMUTATION-MATRIX.md` row 84
- `plugin/lib/src/rvt/{convert/family_regen,convert/modify_family,frontdoor/matrix}.py`:
  sync mirrors
- `tests/test_edit_drives_909.py` (new) and
  `tests/ci_shard.d/909-edit-drives.txt`
- `tests/test_conftest_scaffolding.py`: `test_edit_drives_909` added to
  `ADOPTERS`
- `tests/test_edit_family_mass_659.py`, `tests/test_edit_family_size_668.py`:
  the pinned length caveat and the transformer `Width=600 mm` control row
- this fragment

**Gates at review-fix head** (RVT_SKIP_LARGE=1)
- `test_edit_drives_909` alone: 44 passed (19 original + 25 new or
  parametrized cases).
- One run of 15 files: 426 passed / 30 skipped (skips are samples-gated). The
  files are `test_edit_drives_909`, `test_convert`, `test_convert_combo`,
  `test_edit_family_marks_678` / `_mass_659` / `_size_668`,
  `test_edit_own_release`, `test_edit_status`, `test_edit_text_release`,
  `test_router`, `test_router_load_release`, `test_router_release`,
  `test_matrix_evidence_981`, `test_matrix_evidence_984`, and
  `test_conftest_scaffolding`.
- `test_plugin_sync`: 9 passed.
- `tools/sync_plugin.py`, then `--check`: in sync.
- `validate_plugin.py`: PASS (25).
- `check_portable_paths.py`: ok (3485).
- `tools/route.py matrix`: the evidence self-audit is clean (25 cells, 27
  stages, 5 chains).
- `tools/self_battery.py`: 27/27 PASS.

**Gates at the original head `33853db`** (for the record)
- `test_edit_drives_909` + `test_conftest_scaffolding`: 40 passed.
- The other drive and edit suites: 363 passed / 23 skipped (skips are
  samples-gated).
- Router and factory suites with `test_plugin_sync`: 241 passed / 17 skipped.
- `self_battery` 27/27 PASS.

**Shipped vs staged:** nothing staged. No viewer or desktop batch was run. The
rebuilt and value-only families are validator-gated, not certified.
