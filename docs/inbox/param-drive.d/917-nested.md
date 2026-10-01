# #917: nesting a generated family inside a generated family (first piece)

Stream: param-drive. Issue #917. Branch `nested-917`, based on `lock-915`.

Born families nest their hardware. The reference trapeze nests its rods, nuts and
washers as family instances; it does not draw them as solids. This pass does
three things:

- a census of how born `.rfa` files store and place nested families;
- a check of whether the project loader can take a *family* document as its host;
- the smallest working piece, `rvt.famgen.nest.nest_family`.

The census used the owner's reference library (git-ignored and quarantined, used
only as a development instrument). Only counts and field values are cited here.
No specimen value reaches the output.

## Census (421 born families)

### Storage: same as a family loaded into a project

- **Registries agree in every file.** `rvt.famload.four_registry_census` is
  coherent on **421 / 421** files: save units − 1 equals the ContentDocuments
  entries, the ContentTable records and the FamilyMgr GUIDs, and the GUID sets
  match.
- **4,425 embedded documents** in total. 390 files carry at least one, 31 carry
  none. A nested-of-nested document is hoisted flat into the top file's
  registries.
- **Every embedded component family has the host-side layer**: `Family`,
  `FamilySurrogate`, `FamilySymbol`, `FamSymSurrogate` and `ParamElemFamily`
  twins, plus host-owned copies with `m_famId` set to the nested family:
  - `TextNoteAttributes`, `TagNoteAttributes`, `LeaderStyle`, `CategoryElem`,
    `GStyleElem` and `FontElem`: 1,846 each;
  - `ParamElemFamily`: 1,721.
- **Shared nesting**: `m_bShared` is True on 1,110 of about 1,850 embedded
  component families.
- **Type table**: real types only, `m_idx` 0, with no leading blank row (996 of
  the one-type tables).
- **Header flags in a family host**:
  - nested `Family`: 10 (3,685 / 3,687 placed-instance references);
  - nested `FamilySymbol`: 2472 (3,306); 68008 in 379.
  - The project loader writes 26 / 2488.
- **Tracking data**: nested symbols are **never** in the host
  `ElementTrackingData` (0 / 313 files). Instance ids are mixed: all tracked in
  68 files, some in 103, none in 142.

### Placement (7,845 own nested instances in 313 / 421 files)

| Placement | Instances |
|---|---:|
| Free on the family Level (host −1, not work-plane based) | 3,687 |
| Work-plane based on a SketchPlane | 1,421 |
| Non-work-plane based, hosted on a SketchPlane | 1,794 |
| Neither (no level, no host) | 943 |

A free instance on the Level was decoded in full (3,687). Counts are given per
field; the full list is in the `nest.py` docstring.

- **Object**:
  - `m_famId` is the host's own self-Family; object design option −4.
  - `InstanceInfo{Trf, symbolId, GRepId 0}`; `symbol == masterSymbol` in 1,849
    (1,838 use a slave symbol).
  - `m_instOrigin` equals the transform origin (3,443).
  - `m_elevation` is 0 for unrotated instances (1,143 of 1,251), so the height
    is carried in the transform.
  - `ParamValueSetInt`: Visible (−1006205) in every one. 3,074 also carry
    −1140129 = 2; its meaning is unknown and it is not emitted.
  - `GeomTable` with one empty generator row (3,687).
  - Cells end in `FamilyInstancePatternHelper` (3,687).
  - `FamInstDesignPropertyManager` (3,685); `m_famElemVisibility` 57406 (3,662).
  - `m_pInstParams` has one row per nested instance parameter, keyed by its twin
    (3,658), with instance/reporting flags False (3,684).
- **Header**:
  - category = the nested symbol's (3,687); family = the host self-Family;
  - flags 2856, view flags −4225 (3,685);
  - `regenOnly` = [nested Family] (3,446);
  - appearance = {self-Family, symbol(s), Level};
  - deletion = {self-Family, Level, symbol, self, the instance-parameter twins
    (+ associated host params)};
  - header bounding box equals the rep's (3,687).
- **Rep**: `GElement`, `gElemType` 3, `m_GInfo.m_categoryId` = the host's own
  GStyleElem of the nested category (3,687), flags 557060, one `GInstance`
  (3,639) carrying the same transform (3,687).

### Locks and parameter association

These figures were carried over from this stream's earlier scratch census. They
are not authored in this pass.

- **Locks**: `Alignment` flags 14, view −1. Witness 0 is a host RefPlane
  (`GeomSegInPlaneRef`, constrFlags 4). Witness 1 is the FamilyInstance at a
  reference `geomTag`:
  - 1 = Center L/R (1,343);
  - 4 = Center F/B (1,132);
  - named references (2,000+): these are indices into the symbol's GeomTable
    assigned at regeneration, and how they map to nested planes is **unresolved**.
- **Association**: `FamilyParametrizedElemParamsCell.m_paramDrivenData` entries
  are `{m_famParamId host param, m_elemPropId target, m_geomTag −1, m_bIsSymbol
  False}`. `m_bIsSymbol` is False in every entry.

  | Association | Entries |
  |---|---:|
  | Shared host param → the same `ParamElemExternal` | 10,707 |
  | Local host param → nested twin | 7,616 |
  | → BIP −1006205 (Visible) | 4,266 |

  Both ids are in the instance header's deletion parents in 20,704 / 25,002
  entries; the 4,286 BIP targets are in neither.

## Is the project loader usable with a family host?

Yes, for the load half. `rvt.famgen.loader` (L1–L5) pointed at a generated
`.rfa`:

- writes all four registries and the host-side layer;
- produces a file that `rvt_validate` reports VALID with 0 errors.

Its own `verify_loaded_project` fails only on project-only checks
(ProjectInformation, PartAtom framing). It cannot *place* an instance in a family,
for two reasons:

- it clones a template instance of the category, and a generated family has
  none;
- `extract_family` / `rfa_load` refuse nested units.

## Built: `src/rvt/famgen/nest.py`

`nest_family(host_rfa, out_rfa, child, points)` runs these steps:

1. **Checks before anything is written**:
   - the host is an existing `.rfa`;
   - the output is a different `.rfa`;
   - points are 1–512 finite (x, y, z) triples;
   - the host has exactly one self-Family and one Level;
   - the child's ids lie above the host watermark;
   - the child has no connectors;
   - the host carries a GStyleElem for the child's category.
2. Loads the child through the loader's `_author_load(place=False)`.
3. Applies the family-host flavour: nested Family header flags 10, nested
   FamilySymbol 2472, and no ElementTrackingData symbol row.
4. Authors N free, unrotated `FamilyInstance`s plus their `GElement` reps from
   `blank_object`, with the field values above.
5. Round-trip-gates every record.
6. Does the loader's single container write. That write now takes an `identity`
   argument, so the host keeps its own BasicFileInfo username and gets its own
   last-save name. The project path is unchanged when the argument is omitted.
7. **Verifies the written file**:
   - the nested Family, symbol and instances decode clean and point at each
     other;
   - the FamilyMgr and ContentDocuments entries are present;
   - the four registries agree;
   - `rvt_validate` in family mode reports 0 errors;
   - `constraint_law.check_file` returns `[]`.

   On any failure the output is deleted and `NestError` is raised.

**Evidence** (all read back from the written file):

- A square washer (2 instances), then a hex nut (2 instances), nested into the
  generated strut trapeze, on **2026 and 2025**. Each file is VALID with 0
  errors and 0 warnings, the constraint law is `[]`, the registries agree, and
  there are 3 save units after both nests.
- `make_family provenance` reports `ok`, and the BasicFileInfo author is ours.
- Deterministic: two runs are byte-identical in every stream except
  BasicFileInfo, which carries the output's own file name.

**Not wired into the trapeze.** The archetype still draws its nuts and washers as
solids. Swapping them for nested instances is a follow-up, opt-in only. Every
existing test must stay green, and the nested instances need locks first, or they
will not follow Rod Inset.

## Gaps, stated plainly

1. **No locks.** Nested instances are not aligned to the host's planes. The next
   piece is `Alignment` witnesses on the instance at geomTag 1/4, the fixed
   Center references. `constraint_law` would then also need to judge
   instance-reference witnesses, which it does not yet read.
2. **No parameter association** (`FamilyParametrizedElemParamsCell`). For
   example, host Rod Diameter does not drive the nut's size.
3. **Free placement only.** Work-plane-based, rotated, SketchPlane-hosted and
   slave-symbol placements are not authored.
4. **The type table still has the project loader's leading blank row and
   `m_idx` 1.** Born nested families have real types only. FamilySurrogate and
   FamSymSurrogate flags were not censused.
5. **Unchecked and refused inputs:**
   - the child must be built under the host's release, and this is not checked;
   - children with connectors, and children whose category the host lacks, are
     refused.
6. **No desktop verdict.** Whether Revit opens a family with nested instances
   is unknown (hard rule 4). Validator green and an empty constraint-law report
   are facts about the file. Per steer #913, no probe family goes to the owner.
7. **Finding outside this territory: the project loader stamps the temp file
   name into BasicFileInfo.** It writes last-save path `<out>.pass1.tmp` because
   `commit_new_elements` runs against the temp file. This pass fixes it only for
   the nesting path (`identity=`). Changing the default would change every
   loaded project's bytes, so it should be its own issue.

## BRANCH STATE

**Files written**
- `src/rvt/famgen/nest.py`: new.
- `src/rvt/famgen/loader.py`: `_commit_and_write` gains an optional `identity`.
  With the default, behaviour is unchanged.
- `plugin/lib/src/rvt/famgen/{nest,loader}.py`: sync mirrors.
- `tests/test_nest_917.py` (13 tests) and `tests/ci_shard.d/917-nest.txt`: new.
- This fragment.

**Gates**
- `sync_plugin.py`, then `--check`: in sync.
- `validate_plugin.py`: PASS (25).
- `pytest` on these files: 303 passed, 13 skipped (rme sample absent):
  - this pass: `test_nest_917`;
  - lock, drive and archetype suites: `test_conftest_scaffolding`,
    `test_lock_column_915`, `test_diameter_916`, `test_panel_drives_914`,
    `test_height_law_787`, `test_archetype_drives_913`, `test_drive_follow_904`,
    `test_drive_law_904`, `test_strut_trapeze_899`;
  - plugin: `test_plugin_sync`;
  - loader and famload suites: `test_famgen_loader`,
    `test_famgen_loader_release_700`, `test_famload_batch`,
    `test_famload_determinism_794`, `test_famload_2025`.

**Shipped vs staged:** the API ships, but no route uses it. Nothing is staged and
no viewer or desktop batch has been run.
