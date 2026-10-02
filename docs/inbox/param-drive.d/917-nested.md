# #917: nesting a generated family inside a generated family (first piece)

Stream: param-drive. Issue #917. Branch `claude/pull-latest-main-1cmo56` (PR #936; built on a local `nested-917`), based on `lock-915`.

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

---

# #917 second pass: locks and parameter association (gaps 1 and 2)

Branch `claude/pull-latest-main-1cmo56` (PR #936; built locally as `nest-locks-917` on `nested-917` 422dbd9). Gaps 1 and 2 above
are closed in the file; gap 6 (no desktop verdict) is not, and does not move
here either (hard rule 4, steer #913: no probe family goes to the owner).

The census reads the same owner reference library (421 born families,
git-ignored, development instrument only). Only counts and field values are
cited; no specimen name, parameter name or value reaches the output.

## Census: how a born host locks a nested instance

**Which locks.** 1,378 `Alignment`s in the first 40 files witness a nested
instance; across the whole library the centre-reference ones (instance
witness `m_geomTag` 0-8) to a host `RefPlane` are 1,297 Center (Left/Right),
1,084 Center (Front/Back), 11 Center (Elevation) and 1 Bottom. Named
references (any other geomTag, 2,000+) are left alone (below).

**What geomTag means.** It is the child document's Is-Reference code
(`RefPlane.m_refName`):

- geomTag 1: the child carries exactly one origin-defining plane with
  `m_refName` 1, in 1,340 / 1,340 locks;
- geomTag 4: two planes carry code 4 in 1,153 / 1,165 (one defines the
  origin, one does not); the origin one is the one placed on the host plane;
- the nested `Family`'s `m_oFamilyReferenceIdxMgr` lists the code in every
  one (1,340 / 1,340 and 1,165 / 1,165); the code is never the reference
  INDEX (0 of them).

**Placement holds.** Placed by the instance transform, the child plane lies on
the host plane in every judged lock: 1,297 / 1,297, 1,084 / 1,084, 11 / 11
(plane read from `m_pSurface`; 347 of the first 406 host planes are
surface-only, zero drawn ends). The transform reads as
`world_k = m_or_k + m_3x3[k] . v`: under it the child plane's drawn ends land
on the host plane in 2,393 / 2,393; the transposed reading leaves 249
non-parallel and 135 ends off the plane. The instance witness's own old
segment ends are NOT the transformed child ends (0 / 2,393 equal), so they
are a cache; ours carry the transformed child ends, which lie on the plane.

**The instance witness `GeomRef`** (912 / 912 free-placed locks):
`m_elemId` = the instance, `m_geomTag` = the code, `m_subTag` -1,
`m_famMemberIdx` -1, `m_ownerDBViewId` -1, `m_flags` 1,
`m_intermediateTags` [], no next ref, `GeomSegInPlaneRef` with `m_sideOfArc`
False. The plane witness: geomTag 0, flags 0.

**The `Alignment`** (free-placed instance, 912: 546 Center (Left/Right),
355 Center (Front/Back), 11 Center (Elevation); each field 912 / 912 unless
counted):

- `m_flags` 14, `m_dimVersion` 6, no cell list, `m_ownerDBViewId` -1,
  `m_lastTrf` identity, `m_dimSketchPlaneId` -1, design option -4;
- only pointer `m_pDimLine`: GLine pid 3, endParams [0, 0], GInfo flags
  524292, origin = `m_oldOrigin`, direction perpendicular to the host normal;
- `m_constrDir` parallel to the host normal; `m_planeNormal` perpendicular
  to it; both `m_refPnts`, `m_oldOrigin` and both witnesses' old segment ends
  on the host plane;
- one segment: flags 1, three values (two trailing -1), param -1, locked 0;
  equality array empty; `m_lastDimSegInfoId` {0, -1} and `m_lastUsedId` 1 in
  532 / 912 (the rest {0, 1} or {1, -1});
- witness order: plane first (constrFlags 4, end index 0), instance second
  (constrFlags 2, end index 0) in 620 / 912; the rest put the instance
  first (mostly constrFlags 8 / 1) or vary an end index. Gaps 1/192 ft and
  1/128 ft as every other lock.

**Its header** (912 / 912): category -2000262, flags 10, view flags -4225,
owner view -1, family = the host self-Family, design option -1;
deletion = exactly {itself, DimensionStyle, self-Family, instance, plane};
regenOnly = {nested symbol, Level, UnitsElem} (hosted instances: SketchPlane
in place of the Level); appearance = {DimensionStyle, instance, plane,
UnitsElem}. No back-edge: neither the instance's nor the plane's header
names the lock (912 / 912), and a locked free instance keeps regenOnly =
[nested Family] (675 / 675) -- it does not regenerate from its planes.

## Census: parameter association

`FamilyParametrizedElemParamsCell` on 4,606 nested instances, 25,002
entries, every one `{m_famParamId, m_elemPropId, m_geomTag -1, m_bIsSymbol
False}`:

- cell list: `[FamilyParametrizedElemParamsCell, FamilyInstancePatternHelper]`
  in 3,432 / 4,606; the rest put analytical/cover/group cells first, never
  after the pattern helper;
- targets: 8,349 are the nested family's own parameter twins, and **every
  one is an INSTANCE parameter** of the nested family (8,349 / 8,349); the
  rest go to shared parameters (same `ParamElemExternal` on both sides) or
  built-ins. Host side: type parameters drive nested instance parameters too
  (2,087 + 94);
- the instance's `m_pInstParams` row for the target carries the host
  parameter's current value: 3,880 / 3,880 numbers, 4,467 / 4,467 Yes/No; no
  row carries an expression (8,347 / 8,347);
- definition class and spec agree in 8,014 of 8,349 (331 differ only in
  spec, 4 in class);
- the host parameter is a deletion parent of the instance in 24,992 /
  25,002; entries are in no sorted order;
- 30 nested **symbols** carry the cell too (77 entries, targets that are not
  instance twins): association to a nested TYPE parameter lives there. Not
  censused far enough to author.

## Built

**`src/rvt/famgen/nest.py`** (additive; the default call is unchanged):

- `nest_family(..., locks=[Lock(i, "center_lr" | "center_fb" |
  "center_elevation", host_plane_id) | (i, ref, id)], associate={host caption:
  nested caption})`;
- every lock is planned before anything is written and **refused** unless the
  child carries one origin plane with that code, the target is a host
  RefPlane, and the child plane placed at the instance already lies on the
  host plane (parallel, within 1e-5 ft) -- a lock that would contradict the
  geometry is never written;
- an association is refused unless the host parameter exists, the nested
  parameter exists and is an INSTANCE parameter, it has a host twin, and both
  are the same kind (definition class + spec);
- authoring follows the census modes above; `host_reference_planes(path)`
  lists a family's planes (id, name, code, origin flag, point, normal);
- `verify_nested` also checks every lock decodes and witnesses a placed
  instance, and every instance carries exactly its association entries.

**`src/rvt/famgen/constraint_law.py`** (additive; CG1-CG7 unchanged):

- **CG8**: an instance lock's child reference, placed by the instance
  transform, lies on the host plane it is locked to. `check_file` resolves
  instance -> symbol -> nested Family -> its content document -> the
  `RefPlane` with that code (origin one where two share it). Named
  references and anything that does not resolve are not judged;
- `plane_of_any` (surface first, then drawn ends) and `transform_plane`;
  CG7 still uses `plane_of`.
- Run over the whole born library: **2,393 locks judged, 0 CG8 findings**
  (421 files, 2,511 instance references resolved).

**Child generator:** unchanged. Our families already carry Center
(Left/Right) = code 1 and Center (Front/Back) = code 4 on their
origin-defining planes, and the loader's reference index lists both; the
census asked for nothing more. None has a Center (Elevation) plane, so an
elevation lock is refused rather than invented.

## Evidence (read back from the written files)

Generated strut trapeze, two nut-sized children at the rod planes
(x = -1 / +1 ft), each locked by Center (Left/Right) to its rod plane and by
Center (Front/Back) to the origin plane; host Rod Diameter (a type
parameter) associated to the child's instance parameter. On **2026 and
2025**:

- `rvt_validate` (family mode) VALID, 0 errors, 0 warnings;
- `constraint_law.check_file` == [], with all four locks JUDGED by CG8
  (four resolved instance references, not skipped);
- registries agree; the nested Family's reference index carries codes 1 and 4;
- the instance row carries Rod Diameter's value, not the child's own;
- deterministic (two runs byte-identical except BasicFileInfo);
- every refusal (12 cases) leaves no output and the host byte-identical
  (SHA-256).

## Gaps, stated plainly (second pass)

1. **No desktop verdict.** Whether Revit honours these locks (instances
   following Rod Inset) or the association is unknown. Validator green and an
   empty CG8 report are facts about the file (hard rule 4; steer #913: no
   probe family to the owner).
2. **The association moves a value, not geometry, in our children.** No
   generated child yet has an instance parameter that drives its own solid,
   so a nut whose `Nut Size` follows Rod Diameter does not resize. The
   tests use a probe child built for the purpose.
3. **Not wired into the trapeze** (optional step 4, skipped): the archetype
   draws its nuts and washers as solids that #904 already locks to the rod
   planes; swapping them for nested instances means reworking those drive
   followers, which is its own change. Default unchanged.
4. **Not authored:** named-reference locks (geomTag beyond 0-8, mapping
   unresolved), instance-first witness order, rotated / hosted /
   work-plane-based instances, association to a nested TYPE parameter
   (symbol-side cell), Center (Elevation) on our children.
5. First-pass gaps 3, 4, 5 and 7 stand as written above.

## Review of #936 (head `0526ec8`, 🟡; fixed in this PR)

- **Duplicate family names.** A second family with a name the host already holds
  (nesting "Hex Nut" twice) is now refused before writing. Revit requires family names
  in one document to be unique. Before the fix, the file validated with 0 errors and
  `[]` anyway.
- **One refusal type.** Every failure is now a `NestError`: a `None` child, a child
  callable that raises, something that is not a FamilyProduct, a loader step outside
  `LoaderError`. A crash inside the read-back removes the written output, and the
  pre-write steps touch no file.
- **Release check for a prebuilt child.** A prebuilt child's build release is not
  checked against the host's (a FamilyProduct does not record it), and the result now
  carries a note saying so. A child passed as a callable is built inside the host's
  release context.
- **Still open, unchanged.** #917 DONE 1 is not met: the leading blank type row
  remains (gap 4). The project loader has the same duplicate-name gap, filed as #937.

## BRANCH STATE (PR #936, branch `claude/pull-latest-main-1cmo56`)

**Files written**
- `src/rvt/famgen/nest.py`: locks, association, `host_reference_planes`.
- `src/rvt/famgen/constraint_law.py`: CG8, `plane_of_any`, `transform_plane`.
- `plugin/lib/src/rvt/famgen/{nest,constraint_law}.py`: sync mirrors.
- `tests/test_nest_locks_917.py` (23 tests) and
  `tests/ci_shard.d/917-nest-locks.txt`: new.
- This section.

**Gates**
- `sync_plugin.py`, then `--check`: in sync; `validate_plugin.py`: PASS (25).
- `pytest`: 310 passed, 0 failed -- `test_nest_locks_917` (23),
  `test_conftest_scaffolding`, `test_nest_917`, `test_lock_column_915`,
  `test_diameter_916`, `test_panel_drives_914`, `test_height_law_787`,
  `test_archetype_drives_913`, `test_drive_follow_904`, `test_drive_law_904`,
  `test_strut_trapeze_899`, `test_constraint_law`, `test_constraint_law_910`,
  `test_plugin_sync`.
- CG8 over the born library (scratch instrument): 2,393 judged, 0 findings.

**Shipped vs staged:** the API ships; no route uses it. Nothing is staged; no
viewer or desktop batch has been run.

---

# #917 third pass: real types only (DONE 1) and the trapeze's nested hardware (DONE 5, opt-in)

Branch `trapeze-nested-917`, based on `origin/main` 3bb380f. This pass adds no
census; the figures it relies on are the ones above.

## DONE 1: the nested type table holds real types only

`nest._family_host_flavour` now passes the nested `Family`'s `m_pFamilyTypes`
through `nested_type_table`. The table keeps only its named pairs, and
`m_idx` points at the same current pair it pointed at before. On a one-type
table that is one pair at `m_idx` 0, the born form (996 / 996). A table with no
named type is refused (`NestError`).

The project loader is untouched: a family loaded into a project still gets the
leading `' '` row, and a test pins that. Before and after this change, these
bytes are identical (SHA-256, base `src/` from `git archive 3bb380f` against
this branch):

| Output | SHA-256 prefix |
|---|---|
| project load into the bundled `G_ABPD.rvt` (`place=False`) | `d2ddb644ec1b950c` |
| default trapeze, 2026 | `28313e4cf7734e37` |
| default trapeze, 2025 | `90b636b87a009252` |
| wireway | `a14e446899f25cf4` |

## Defect found and fixed: a nested host did not end on the family end record

`provenance_scan_v2` flagged `end_record_is_constant` = False on every nested
output, including those of the first two passes. That check is not in
`verify_nested`, which is why it went unseen.

**Cause.** Pass 1 (`commit_new_elements`) keeps the walker's `end_record`,
which is everything from the end offset on. That includes the host's old
final-block CRCIO parity. The parity was re-framed as content, and the nested
unit was spliced in ahead of it. A single nest left 91 stray bytes after the
end record.

**Fix.** `loader._commit_and_write(exact_partition=True)` is used by the nest
path only:

- it splices into `ecc.unframe_stream` content;
- it cuts that content right after the 10-byte family end record;
- with the default `False`, the project bytes are unchanged (table above).

`verify_nested` now also checks that the partition's exact content ends on
`FAMILY_END_RECORD`. Both nested trapezes now pass the end-record check
(`end_record_is_constant`) on 2026 and 2025, and the write report's own provenance
(run inside the write context) is `ok` on both. A standalone `provenance_scan_v2` on
the 2025 file still reports `formats_latest_is_format_constant=False`, the same as the
2025 solid trapeze on main. That is an instrument limit, not this change: the
read-side release ladder does not swap the Formats/Latest constant, so it is
recorded on #864, together with the CLI's 2025 read failure.

**Open question.** Pass 1 may carry the same stale parity into project loads.
That path is outside this territory and is not judged here.

## DONE 5: `make_archetype(product="strut_trapeze", nested_hardware=True)`

The implementation is a new module, `src/rvt/famgen/trapeze_nested.py`, plus a
small opt-in hook in `factory.make_archetype`.

**The host.** `strip_hardware` removes the 16 washer and nut solids from the
host. Rod Inset now follows the two rods only; `wire_follow` still makes the
two Rod Inset planes. The height chain keeps every plane: Rod Below Bottom Nut
still chains from the bottom nut's plane, but no washer or nut face is locked
to it.

**The children.** Both are our own families. No donor or reference family is
read.

| Child | Instance parameters | Drives |
|---|---|---|
| `Square Strut Washer` (one box) | `Washer Size`, `Washer Thickness` | `Washer Size` labels two symmetric in-plane drives (x and y) and so resizes the plan; `Washer Thickness` is a Case B cap-face height drive |
| `Hex Nut` (one hex prism) | `Nut Height`, `Nut Across Flats` | `Nut Height` is a Case B height drive; `Nut Across Flats` carries a value only (the in-plane drive takes rectangles, so no current mechanism resizes a hexagon) |

**What `write()` does.**

1. Writes the stripped host.
2. Calls `nest_family` with the washers: 8 instances, each locked by
   Center (Left/Right) to its Rod Inset plane and by Center (Front/Back) to the
   origin plane, with host `Washer Size` and `Washer Thickness` associated.
3. Calls `nest_family` with the nuts: 8 instances, the same locks, with host
   `Nut Across Flats` associated.

Each instance is placed where the solid version draws that part: the part's
centre at its bottom face, checked part for part.

**On failure.** Any failure at any step writes the solid trapeze at the same
path, with `nested_hardware: {ok: False, refused}` and a caveat (hard rule 1).
A refusal while building also returns the solid product.

**Scope.** No route passes the flag yet, and `nested_hardware` on any other
product is a note only.

**Evidence** (read back from the written files, on **2026 and 2025**):

- `rvt_validate` in family mode: VALID, 0 errors, 0 warnings.
- `provenance_scan_v2`: clean.
- `constraint_law.check_file` == []. **CG8 judged all 32 nested locks**: the 16
  instances × {code 1, code 4} resolve, and none is skipped.
- `four_registry_census` is coherent, with 3 save units.
- Each lock's target is the Rod Inset plane on the instance's side (x = ∓1 ft),
  or the origin Center (Front/Back) plane (`m_refName` 4).
- Every washer row carries the host's Washer Size and Washer Thickness values.
  Every nut row carries the host's Nut Across Flats.
- Both nested type tables are `[family name]` with `m_idx` 0.
- Each child, written on its own, is VALID with constraint law [] and has
  every drive caption labelling ≥ 1 dimension (Washer Size labels 2).
- Determinism: two writes into different directories are byte-identical in
  **every** stream, BasicFileInfo included.
- The default trapeze is a plain `FamilyProduct` and is byte-identical to
  `nested_hardware=False` and to the base.

**Timings** (median of 3, in seconds, warm process, this sandbox):

| Release | Version | Build | Write | Total | File size |
|---|---|---:|---:|---:|---:|
| 2026 | solid | 0.60 | 0.70 | 1.30 | 327,680 B |
| 2026 | nested | 0.51 | 1.88 | 2.40 | 339,968 B |
| 2025 | solid | 1.46 | 1.39 | 2.96 | 323,584 B |
| 2025 | nested | 0.93 | 2.85 | 3.73 | 335,872 B |

**Why the default stays solid.** The nested version is not strictly better:

- **Height.** Its instances do not follow the host's height drives. Our
  children carry no Center (Elevation) reference to lock, so Tier Spacing,
  Strut Height and Washer Thickness move the host's planes but not the nested
  washers and nuts. The solid washers and nuts do ride those planes.
- **Nut sizing.** The nut's across-flats association moves a value only.
- **Cost.** The nested build is about 1.8× slower on 2026 and about 1.3×
  slower on 2025.
- **Verdict.** It has no desktop verdict. Neither does the solid assembly
  (#904).

## Gaps (third pass)

1. **No desktop verdict** for nested families, their locks or their
   associations (hard rule 4). Per steer #913, no probe family goes to the
   owner.
2. **No vertical follow.** Fixing it needs a Center (Elevation) (code 7) origin
   plane on our children. That has only 11 born locks behind it and is not
   authored. An elevation lock is still refused rather than invented.
3. **The nut's across-flats drives nothing**, as described above.
4. **Not reachable from the route or prompt.** It is an API flag only, and the
   archetype's `lod_note` and `limits` still describe the solid version. The
   nested product's own notes state the nested truth.
5. **The project loader may carry stale end parity** (the open question
   above). Unjudged.
6. **The washer is one family for both positions.** Below the channel and on
   the lips use the same nested family (8 instances), which born hosts also
   do; no shared nesting (`m_bShared`).

## BRANCH STATE (`trapeze-nested-917`)

**Files written**
- `src/rvt/famgen/nest.py`:
  - `nested_type_table`, used by the family-host flavour;
  - the end-record check in `verify_nested`;
  - `exact_partition=True` on the write;
  - docstring.
- `src/rvt/famgen/loader.py`: `_commit_and_write(exact_partition=False)`.
  The default is byte-identical.
- `src/rvt/famgen/factory.py`: `make_archetype(nested_hardware=False)`. The
  default is byte-identical.
- `src/rvt/famgen/trapeze_nested.py`: new.
- `plugin/lib/src/rvt/famgen/{nest,loader,factory,trapeze_nested}.py`: sync
  mirrors.
- `tests/test_trapeze_nested_917.py` (18 tests) and
  `tests/ci_shard.d/917-trapeze-nested.txt`: new.
- This section.

**Gates**
- `sync_plugin.py`, then `--check`: in sync.
- `validate_plugin.py`: PASS (25).
- `pytest`: **293 passed, 13 skipped** (rme sample absent), 0 failed, over
  these files:
  - `test_trapeze_nested_917`, `test_nest_917`, `test_nest_locks_917`;
  - `test_strut_trapeze_899`, `test_drive_follow_904`,
    `test_archetype_drives_913`;
  - `test_constraint_law`, `test_constraint_law_910`;
  - `test_famgen_loader`, `test_famgen_loader_release_700`,
    `test_famload_batch`, `test_famload_2025`, `test_famload_determinism_794`;
  - `test_conftest_scaffolding`, `test_plugin_sync`, `test_surface_perf`.

**Shipped vs staged:** the opt-in API ships; no route uses it. Nothing is
staged, and no viewer or desktop batch has been run.
