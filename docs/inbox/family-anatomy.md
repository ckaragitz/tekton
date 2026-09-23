# family-anatomy — profile a family's anatomy, content-free, and rank where ours falls short

Stream **family-anatomy**. Issue **#837** (P1), from steer **#836**
(S-2026-09-23-b): the owner's complex reference families set the bar for
generation. Branch `cam/837-family-anatomy`.

## Built

`tools/family_anatomy.py` — a dev instrument, not mirrored into the plugin.

- **`profile X.rfa [--json]`** reads any family the engine decodes into
  counts and kinds:
  - forms by kind (extrusion / blend / swept blend / revolve / sweep), and
    solids vs voids (`GenSweep.m_cutting`);
  - distinct per-form visibility settings (`m_famElemVisibility.m_flags`);
  - forms assigned a subcategory or a material;
  - reference planes (total, named, defining the origin);
  - dimensions: total and EQ, plus, from the family's `m_oFamDimConstrMgr`,
    labelled (`m_paramExprs`), driven segments and locked references;
  - parameters: instance or type, by ParamDef storage class, by parameter
    group, formulas (`m_oExpression`), reporting;
  - types (`m_pFamilyTypes`), subcategories of the family's own category;
  - class counts for nested instances and families, connectors, materials,
    text, curves, arrays, openings, shared parameters and views.
- **`compare REFERENCE OURS`** lists every measure where the reference has
  more than ours. A feature ours lacks entirely ranks first, then the rest by
  relative gap.
- **Every aspect says how it was read**: `decoded`, `class-count`, or
  `not-yet-readable`. The last covers a Yes/No bound to a form's visibility
  (#690). A record that fails to decode is counted under `undecoded`, never
  skipped.
- **Content-free by construction.** Keys are our own words, a ParamDef class
  name, or the short form of a parameter-group type id. Values are counts.
  There are no names, strings, coordinates, ids or GUIDs.

Also: `tools/sync_plugin.py`'s deny list now names hard rule 3's quarantine
dirs (`/samples/`, `/vendor/`, `/extracted/`) and `reference-families`.
**Before this, a file under `samples/` passed the deny-audit.** Nothing copies
it into the plugin today, since `samples/` is git-ignored, but the audit is the
safety net and did not catch it.

## Evidence

`tests/test_family_anatomy_837.py` has **35 tests**. It builds all six
archetypes through the product route.

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
generated families contain no blends, sweeps, revolves, voids, dimensions,
formulas, nested families or connectors. So the readers for those were written
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

---

## BRANCH STATE

**Files written**
- `tools/family_anatomy.py`: new.
- `tools/sync_plugin.py`: `DENY_PATH_PARTS` gains the quarantine dirs and
  `reference-families`.
- `tests/test_family_anatomy_837.py`: new, 65 tests;
  `tests/ci_shard.d/837-family-anatomy.txt`.
- this record.

**Gates (round 1)**: 65 passed (74 with `test_plugin_sync.py`); 13/13 mutants
killed; `sync_plugin.py --check` in sync.
Full suite **not** run; `session_ci.sh` runs the shard.

**Shipped vs staged**: a dev instrument, shipped to the repo, not to the
plugin. #838 (running it on the owner's families) waits on the files.
