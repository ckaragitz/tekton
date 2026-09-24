# family-anatomy — profile a family's anatomy, content-free, and rank where ours falls short

Stream **family-anatomy**. Issue **#837** (P1), from steer **#836**
(S-2026-09-23-b): the owner's complex reference families set the bar for
generation. Branch `cam/837-family-anatomy`.

## Built

`tools/family_anatomy.py` — a dev instrument, not mirrored into the plugin.

- **`profile X.rfa [--json]`** reads any family the engine decodes into
  counts and kinds:
  - forms by kind (extrusion / blend / swept blend / revolve / sweep, and
    `other` for any GenSweep subclass the table does not name), solids vs
    voids (`GenSweep.m_cutting`);
  - distinct per-form visibility settings (`m_famElemVisibility.m_flags`);
  - forms assigned a subcategory or a material;
  - reference planes (total, named, defining the origin), and their
    Is-Reference setting (strong / weak / other), `inferred`;
  - dimensions by concrete class: linear, angular, radial, arc length,
    spot elevation, `other`, and alignments (locks) apart. Also `inferred`:
    labelled vs unlabelled, the EQ option, and the family's
    `m_oFamDimConstrMgr` lists;
  - parameters: instance or type, by ParamDef storage class, by parameter
    group, formulas (`m_oExpression`), reporting;
  - types (`m_pFamilyTypes`), subcategories of the family's own category;
  - class counts for nested instances and families, connectors, materials,
    text, curves, arrays, openings, shared parameters and views.
- **`compare REFERENCE OURS`** lists every measure where the reference has
  more than ours. A feature ours lacks entirely ranks first, then the rest by
  relative gap.
- **Every aspect says how it was read**: `decoded`, `inferred`, `class-count`
  (the exact class, not its subclasses), or `not-yet-readable`. The last covers a Yes/No bound to a form's visibility
  (#690). A record that fails to decode is counted under `undecoded`, never
  skipped.
- **Content-free by construction.** A key is one of:
  - one of our own words (`VOCABULARY`);
  - a ParamDef class name the file's own schema defines;
  - the last token of a full `autodesk.…:token-N.N.N` parameter-group or
    spec type id. Values are counts.
  There are no names, strings, coordinates, ids or GUIDs.

Also: `tools/sync_plugin.py`'s deny list now names hard rule 3's quarantine
dirs (`/samples/`, `/vendor/`, `/extracted/`) and `reference-families`.
**Before this, a file under `samples/` passed the deny-audit.** Nothing copies
it into the plugin today, since `samples/` is git-ignored, but the audit is the
safety net and did not catch it.

## Evidence

*Round 0 (first push); the counts are now 87 tests. See the round sections
below.* `tests/test_family_anatomy_837.py` builds all six archetypes through
the product route.

- **Content-free:** every string the family carries (captions, type names, the
  description) is absent from its profile. The collector sees 18 such strings
  on the lighting control panel, so the check is not vacuous. Keys are drawn
  only from the allowed vocabulary.
- **Nothing guessed:** every aspect carries `how`; `undecoded` is empty; a
  simulated decode failure is counted (7 ExtrusionElem) instead of shrinking
  the form count.
- **Comparison:** ours vs ours gives 0 gaps for all six. Cable tray vs lighting
  control panel shows the tray as richer (16 vs 7 extrusions), with missing
  features ranked first.
- **CLI:** the JSON report is written; a non-family exits 1 with one line and no
  traceback.
- **Quarantine:** `samples/reference-families/` is git-ignored; the deny-audit
  refuses five quarantined path shapes and still passes the real plugin.

| mutant (anchor asserted = 1, bytecode off) | result |
|---|---|
| captions leaked as group keys | killed (12) |
| equal counts reported as gaps | killed (7) |
| a missing feature ranked last | killed (1) |
| undecoded records not counted | killed (1), after adding the simulated-failure test (it survived first) |
| deny list without the quarantine dirs | killed (5) |
| forms not counted | killed (2) |

## What is NOT verified — read this before trusting a profile

**Only the aspects our own families contain have been exercised.** Our
generated families contain no blends, sweeps, revolves, voids, formulas or
nested families. *(Round 3 correction: this used to say "no dimensions or
connectors". That was false. The catalog panelboard and luminaire each carry 2
labelled `LinearDimString`, 4 `Alignment` and 1 connector, and the
transformer carries 2 connectors. The reader looked for the wrong class and
read 0.)* So the readers for those were written
from the schema's field names (for example `GenSweep.m_cutting`,
`Dimension.m_useEqualityFormula`, `FamDimConstrMgr.m_paramExprs`) and have
**never been run against a family that has them**. The first profile of a
Revit-born reference family (#838) is also the first test of those readers.
Any count that disagrees with what Revit's own UI shows for that family is an
instrument bug, and it voids the readings taken with it.

## Round 1 — what the review found, and what changed

🛑 on `bb88ec3`. **The record over-claimed in three places, and every one was
a real bug:**

1. **"Never skipped" was false.** The decoder reports a bad record through
   `errors` / `clean`; it never raises. `val()` treated the `{}` it returned
   as an empty record, so forms silently vanished and nothing was counted. My
   test simulated a *raise*, a failure the decoder never produces. Now every
   record goes through `fi.decode()`, and anything with errors or not clean is
   counted under `undecoded` and left out of the other counts. `compare`
   prints a WARNING and records `undecoded_warning` when either side has any.
   The test now simulates the real failure mode.
2. **Two readings were wrong by the schema.**
   - Sweeps are `SweepElem`; `GenSweep` is the base of all five form classes,
     so Revit-born sweeps were never counted.
   - `RefPlane.m_refName` is the Is-Reference enum, not a name, so a plane
     set to "Left" (0) counted as unnamed. The name is `DatumPlane.m_text`.
     Planes now report named / is-reference / strong / weak.
3. **A project was profiled, not refused.** Passing the eval kit's project
   (7 loaded families) exited 0 with a random loaded family's counts. A
   family's own `Family` element has a nil `m_famDocGUID`, and every loaded
   one carries a real GUID (measured on that project, the kit's Eaton `.rfa`,
   and ours). A file with none is now `NotAFamily`, and the CLI exits 1 in one
   line.

**Also fixed:**
- **The deny-list change broke the build for a clone under a folder named
  `vendor`, `samples` or `extracted`**, because `_denied` matched absolute
  paths. It now matches the path relative to the repo.
- **Readings of uncertain meaning are marked `inferred`:** the equality-display
  option, parameter-driven segments and anchored references, which were
  reported before as "EQ", "labelled" and "locked".
- **Aspects DONE(1) asked for that are missing are now reported, not
  omitted.**
  - Newly decoded: spec kind, from the ParamDef's `m_specTypeId`, and
    view-specific elements, from `m_ownerDBViewId`.
  - Listed as `not-yet-readable`: connectors by domain, shared nested
    families, material parameters, and symbolic vs model lines.
- **DONE(4).** Every archetype is now taken from the registry, and four
  catalog families are built with `make_family.py`.
- **Keys** built from file data are whitelisted (`[A-Za-z0-9_]`, anything else
  becomes `other`). The leak test exempts only the profile's own vocabulary.
- **The CLI** turns any error into one line.

Tests: **65 passed** in `test_family_anatomy_837.py` (74 with
`test_plugin_sync.py`). There are ten families, six archetypes and four
catalog, plus these tests:
- the lighting control panel pinned aspect by aspect;
- decode failures, a void, a subcategory, and plane names and reference
  settings, each simulated through the decoder;
- both a genesis base and a 7-family project refused;
- the form table checked against the schema's inheritance;
- the key sanitiser;
- the deny-audit under a `/vendor/` clone.

Mutants: **13/13 killed**, including all 8 the reviewer found alive.

The honest limit stands and is now visible in the output as well as here:
blends, sweeps, revolves, real dimensions, formulas and nested families have
never been read from a family that has them. The first Revit-born profile
(#838) will be their first real test.

## Round 2 — what the review found, and what changed

🛑 on `2a8a3d8`. The round-1 record said "65 passed" and "13/13 mutants
killed"; both were true only for the tests and mutants I chose, and the
reviewer found seven problems:

1. **A test failed in the repo's own CI.** The git-ignore test ran
   `git check-ignore` on the working tree. `session_ci.sh` tests an export
   with no `.git`, so it failed there (64/1). It now copies `.gitignore` into
   a throwaway `git init` under `tmp_path`.
2. **`_denied` still depended on the current directory.** A relative path
   went through `abspath()`, so running `--check` from a folder named
   `vendor` refused the genesis base. A relative path is now judged as given.
   The test runs from a `vendor/` cwd.
3. **Keys could leak captions.** The cleaner accepted any single word, so a
   mutant writing "Width" / "Height" as keys passed. A key from file data is
   now either a token parsed out of a full `autodesk.…:…-N.N.N` schema id, a
   ParamDef class name the file's own schema defines, `none`, or `other`.
   Every other key must be in a fixed `VOCABULARY`. The key test enforces
   this.
4. **Two readings were wrong but labelled `decoded`.**
   - "View-specific elements" counted parts of the views themselves (a
     sketch plane, sun settings, an extent). It is now `not-yet-readable`.
   - Spec kinds are now kept apart. The tracked Eaton panelboard is pinned
     exactly: 14 type parameters, 0 instance,
     `{current 2, int64 3, length 3, number 1, potential 1, string 4}`.
5. **Readings without a test.** Each now has one:
   - instance/type, pinned on the Eaton family;
   - type count, on the two-type catalog panelboard;
   - strong/weak, five asymmetric pairings (a symmetric one let the swap
     live);
   - per-form visibility;
   - spec kind;
   - storage class not in the schema, which counts as `other`.
6. **An undecodable Family record passed as the self family.** The nil-GUID
   test now requires `m_famDocGUID` to be present in a cleanly decoded
   record. The test simulates the failure on the eval kit's 7-family project,
   which is still refused.
7. **Limits** — added below.

Mutants (anchor asserted = 1, bytecode off, `tools` restored after each):
**11/11 killed**. They are:
- instance inverted;
- types forced to 1;
- strong/weak swapped;
- visibility collapsed;
- spec kind forced to none;
- a loose group key;
- the self-family guard dropped;
- the relative-path deny back through `abspath`;
- unclean records counted;
- storage class unchecked;
- voids never counted.

Strong/weak and storage class **survived at first**. I added their tests
after that.

Tests: **79 passed** in `test_family_anatomy_837.py`.

**Limits, stated plainly.** Everything else in this record is subject to
them.
- ~~**Dimension counts are unexercised.**~~ *Retracted in round 3.* The
  families do carry dimensions. `Dimension` is an abstract base that no
  record carries, so the reader read 0, and that 0 is why the mutant
  survived.
- **Nested families are unverified.** No tracked family nests one, and none
  was built here. The self-family rule (nil `m_famDocGUID`) has been checked
  on flat families, one 7-family project (eval kit 04) and the G_ABPD base only.
- **Revit-born projects with in-place or system families** have not been
  tried.
- **2024/2025 families are unverified.** `FamilyIndex` cannot open the 2024
  and 2025 genesis bases ("Partitions header v=9"), so every family profiled
  here is 2026-framed.

## Round 3 — dimensions read from an abstract class

🛑 on `e65cb3b`. All seven round-2 fixes were confirmed, and a new blocker was
found. **The dimension reader counted records of class `Dimension`, an
abstract base that no record carries.** Real dimensions are
`LinearDimString`, `RadialDim`, `AngularDim` and the other 8 subclasses the
schema lists. So `dimensions` read 0, labelled `decoded`, on every family:
- The catalog panelboard carries 2 `LinearDimString` + 4 `Alignment` and read 0.
- The Revit-born oracle summaries carry thousands of these records.
- The EQ count read the same wrong class.

**This is the round-1 `GenSweep` mistake again:** a base class in a table of
record classes. The record then explained the surviving mutant with a false
"the true count is 0", which I have retracted above.

**Fix:**
- Dimensions and forms are now found by **schema inheritance**
  (`descends`).
- A subclass the table does not name counts as `other`, never dropped.
- Alignments are reported apart from real dimensions.
- Labelled vs unlabelled is read from the segment's `m_paramId`, which is how
  our writer labels a dimension. It is marked `inferred` for Revit-born
  families.
- The catalog panelboard is pinned exactly: 2 linear dimensions, both
  labelled, 4 alignments, 1 connector.

**Also:**
- **The Is-Reference enum is now its own `inferred` aspect,
  `reference_strength`.** `skeleton.REF_NAME` marks only the values as
  verified. Codes other than 12/13/14 (Left … Top, and the unmapped 9–11)
  count as `other_reference` instead of blending into strong/weak.
- **Two or more nil-GUID Family elements are refused as ambiguous.** The
  "most referenced" tie-break nothing exercised is gone.
- **New tests, each of which killed a mutant that survived round 3's review:**
  - formulas and reporting;
  - per-form subcategory and material;
  - the `clean` flag;
  - the multi-self refusal;
  - unlabelled and EQ dimensions;
  - an unnamed dimension or form class.
- The stale Evidence text, the key description and the "two 7-family
  projects" line are corrected in place above.

Tests: **87 passed** in `test_family_anatomy_837.py`. Mutants: see BRANCH
STATE.

**Limits** (round 2's stand, except the retracted dimension line):
- nested families;
- Revit-born projects with in-place or system families;
- 2024/2025 families;
- **`class-count` aspects count the exact class only.** `CurveElem` has 4
  subclasses and `DBView3d` has 2 that are not counted under it.
- **Dimension kinds other than linear, the EQ option and a real formula
  have only been read through simulated records, never from a family that
  has them** (#838).

## Round 4 — shared parameters never read, and nested families' parameters counted

🛑 on `feaeb80`. Every round-3 fix was confirmed. The reviewer then audited
every class the tool reads against the schema and the Revit-born class
counts. **The same mistake turned up a third time, in the parameter loop.**

1. **A shared family parameter is a `ParamElemExternal`, not a
   `ParamElemFamily`.** Our own panelboard, built with
   `--shared-params`, read **10** of its 21 parameters. `compare` against the
   local build showed 11 gaps between families with identical parameter
   sets. Manufacturer reference families lean on shared parameters, so #838
   would have read them low.
2. **The loop was not limited to the family.** A loaded family's
   parameters sit in the host's unit. With one of eval-kit project 04's
   Family elements passed off as the self family, the profile read
   **100** parameters for a family that lists 19.

**Fixes:**
- **Parameters are every `ParamElem` subclass, found by inheritance, and
  only those the self family's `m_familyParams` lists** (by `m_paramId`).
  They are reported as `local` / `shared` / `other_kind`.
- **Instance vs type is still read from the local parameter's own
  `m_instanceParam`.** A shared parameter has no such flag, so its count goes
  to `instance_or_type_unread`. I did not take it from the family table's
  `m_instance`: on our own catalog panelboard that field disagrees with
  `m_instanceParam` for one parameter, so it does not mean the same thing.
- **The `shared_parameters` class count is gone**, replaced by the filtered
  `parameters.shared`.
- **An undecodable self Family now says so** ("N Family element(s) could not
  be decoded") instead of calling the file a project.

**Measured:**
- The local/shared panelboard pair reads 21 = 21 + 0 and 21 = 10 + 11, with
  identical parameter groups.
- **Their storage and spec kinds still differ**, because shared parameters are
  declared as `ParamDefValue` with spec `int64` / `string` where our local
  ones are `ParamDefInt` / no spec. That is a real difference in the files,
  not a reading error, and `compare` shows it.
- The project simulation reads 16: the 16 `ParamElemFamily` records among the
  19 ids that family lists (3 are built-in).

**Also (non-blocking):**
- **New tests:**
  - undecoded parameters, planes and dimensions are left out of their counts
    (only forms were tested before);
  - `compare` never ranks `undecoded` as a gap;
  - the undecodable-self message.
- **Stated limits:** see the list below.

Tests: **102 passed** (15 new, including both panelboard builds, which also
run through the content-free and key tests).

Mutants: **6/6 killed**:
- no listed filter;
- local only;
- shared never counted;
- unread forced to 0;
- no undecodable message;
- every local parameter read as instance.

**Limits, updated.** Everything above is subject to them.
- **The `m_oFamDimConstrMgr` lists read 0 even where our writer labels
  dimensions.** The catalog panelboard has 2 labelled dimensions and all
  three lists are empty. That reading is `inferred` and shows nothing yet.
- **These are read only through simulated records, never from a family that
  has them:**
  - voids;
  - per-form subcategory, material and visibility;
  - strong/weak planes;
  - dimension kinds other than linear;
  - the EQ option;
  - formulas;
  - reporting.
- **`class-count` counts the exact class.** These subclasses are not counted
  under their bases:
  - `CurveElem` (4 subclasses);
  - `DBView3d` (2);
  - `BaseArray` → `Pattern` (6 in the Revit-born racbasic sample);
  - `Opening` → `ShaftOpening`.
- **`RefPlane` is read by exact class.** Its sibling `ProfileRefPlane` (218 in
  racbasic) is left out, and whether it belongs in a family's reference-plane
  count is open until a reference family is profiled.
- **Subcategories and forms are not filtered to the self family.** A nested
  family's subcategory under the same category would be counted. Parameters
  are filtered now; the rest waits on a family that nests one (#838).
- **Nested families, Revit-born projects with in-place or system families,
  and 2024/2025 families** remain unverified, as in round 2.

---

## BRANCH STATE

**Files written**
- `tools/family_anatomy.py`: new.
- `tools/sync_plugin.py`: `DENY_PATH_PARTS` gains the quarantine dirs and
  `reference-families`.
- `tests/test_family_anatomy_837.py`: new, 102 tests;
  `tests/ci_shard.d/837-family-anatomy.txt`.
- this record.

**Gates (round 4)**: 102 passed; 6/6 round-4 mutants killed.

**Gates (round 3)**
- 87 passed; 96 with `test_plugin_sync.py`.
- `sync_plugin.py --check` is in sync.
- **25/25 mutants killed.** These are the 11 from round 2, the reviewer's
  round-3 survivors, and 8 against the new readings.
- **Two survived at first:**
  - The `clean` test assigned to a read-only property. The resulting raise,
    not the check, made it pass.
  - The self-family guard test was satisfied by the new ambiguity refusal.

  Both tests are fixed. Round 1 was 13/13.
Full suite **not** run; `session_ci.sh` runs the shard.

**Shipped vs staged**: a dev instrument, shipped to the repo, not to the
plugin. #838 (running it on the owner's families) waits on the files.
