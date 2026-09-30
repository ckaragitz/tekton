# 866 step 1 — read a user's shared-parameter library back out of their own families

Stream **family-shared-params** (fragment; the index `../family-shared-params.md` is left as is).
Issue #866 (from steer #865). Territory: `tools/shared_params_from_rfa.py` (new),
`tests/test_shared_params_from_rfa_866.py` (new) + its shard drop-in, this fragment.

## What was built

`tools/shared_params_from_rfa.py FAMILY.rfa|DIR ... --txt OUT.txt --profile OUT.json [--json]`
reads every `ParamElemExternal` of each family *inside the file's own release*
(`enter_own_release`, so 2024/2025/2026 families are read alike) and writes:

* a Revit shared-parameter TXT (`*META` / `*GROUP` / `*PARAM`, GUIDs verbatim) that our own
  `read_shared_parameter_file` and `make_family --shared-params` accept **unless a name is
  carried by two GUIDs** (counted; see below); and
* a parameter profile JSON (`tekton.param-profile/1`): per source family, which shared
  parameters it carries and how it binds each, read from the document's OWN Family element's
  (`m_surrogateId == -1`) `m_familyParams` rows. The binding is instance, type, or `null`: the
  document only *defines* the parameter for a label or a nested family, so it is not a parameter
  of the family itself. The profile also gives the palette group. Per GUID it records the
  definition: name, definition class, spec, DATATYPE and its basis, the Family-Type category,
  and the flags.

DATATYPE is **never guessed**:
* It comes from the definition class where the class decides it (`ParamDefString`, `YesNo`,
  `Int`, `MaterialBrowse`, `URL`, `NoOfPoles`, and `FamType` → `FAMILYTYPE` with DATACATEGORY =
  its `m_categoryId`). Otherwise it comes from the measurable spec, including the
  `spec.string` / `spec.int64` / `spec.bool` specs our own writer uses.
* Two browse-edit classes are mapped by **inference**, counted as `datatypes_inferred`:
  `ParamDefTextBrowseEdit` → `MULTILINETEXT` and `ParamDefImageSymbolBrowseEdit` → `IMAGE`. The
  evidence is that both are `ParamDefBrowseEdit` subclasses with no fields of their own (the
  "…" dialog editor), and the text one stores its value in `m_str`. No shared-parameter file
  written by Revit was observed.
* A parameter with no known token stays in the profile but is left **out** of the TXT and
  named. Tokens whose spelling could not be vouched for (conduit / cable-tray / wire / pipe
  sizes) are deliberately absent from the table.

Per-GUID variance is split in two, and the first-seen definition is kept in both cases:
* **conflicts**: the identity differs (name, class, version-less spec, datatype, category);
* **variants**: cosmetic drift between files (a spec version, a description, a flag).

The summary also counts:
* names carried by two GUIDs. That is legal in Revit's file, but OUR `read_shared_parameter_file`
  refuses such a TXT, so the profile application keys by GUID;
* rows that are not the family's own parameters;
* files whose own release could not be entered, or with other than one own Family element.

Directory arguments match `.rfa` in any case; a file named twice is read once; two files with
one name are kept apart by path; an empty directory is an error (exit 1).

The module holds **no library content**. The owner's library files are read only at their
request, and the outputs go where they say. For the owner's pack that is the git-ignored
`samples/reference-families/analysis/`; nothing from it is in this repository (rule 6, hard
rule 3).

## Evidence

* **Synthetic round trip:** our panelboard, built with OUR `usecases/eaton-panelboard` shared
  file, is extracted and re-read. All 11 rows give GUID / name / datatype / description /
  visible identical to the source, all 11 as type parameters. A rebuild from the *extracted*
  TXT carries the same GUIDs.
* **Synthetic instance family:** our device carries two shared parameters, one bound per
  instance with every flag the other way round (hidden, not user-modifiable,
  hide-when-empty). Instance and all three flags read back from the written file and reach the
  TXT columns.
* **Fake-index tests:** a nested family's surrogate rows never decide the binding; two own
  Family elements are counted and warned about, not merged.
* **Mutations (review of the first head):** each of these now fails at least one test:
  instance hard-coded to False, the self-Family filter removed, VISIBLE / USERMODIFIABLE /
  HIDEWHENNOVALUE constant, a NUMBER guess for unknown classes, FAMILYTYPE unmapped, own
  Families merged, the conflict check disabled.
* **The owner's pack, read privately (counts only):**
  * 421 families, 340 shared parameters.
  * **0 conflicts.** The first head's name+datatype check also said 0; the full-definition
    check finds 269 **cosmetic variants**: 181 description only, 50 visible only, 29 a newer
    spec *version* of the same spec.
  * 8 names on two GUIDs, so our reader refuses the TXT (expected; profile application keys
    by GUID).
  * 1 datatype inferred (the one multi-line text parameter).
  * 0 left out of the TXT, after `FORCE` joined the table for the one structural-force
    parameter.
  * 1633 of 6523 rows are not the family's own parameters. The first head counted these as
    the "1633 None" rows; a probe shows they are referenced by tag labels'
    `m_paramDataFormattingArr` or by nested families' surrogate rows.
  * 0 warnings, 0 unreadable.
* `pytest tests/test_shared_params_from_rfa_866.py`: 15 passed.

## Open questions / next (#866)

* Names can repeat under different GUIDs. Our reader rejects duplicate names, so the profile
  application (next PR) keys by GUID, not by the TXT.
* `MULTILINETEXT` / `IMAGE` are inferred. A shared-parameter file written by Revit that
  carries them would settle it. Our writer authors neither kind yet.
* The size tokens (conduit, cable tray, wire, pipe) are absent until their spelling is
  evidenced.
* Next PRs: the estorage `.rfa` path; `param_profile` application in the writer
  + `make_family` / route flags; regenerate the owner's families privately and validate.
* Carried from the #868 review, for the profile PR that touches `_type_param_entries`: a guard
  for Revit instance built-ins, and a note that `refs["instance"]` is set only by that path.

## BRANCH STATE

Branch `claude/eager-franklin-xgzgda` from main `1264faf`. Written: `tools/shared_params_from_rfa.py`,
`tests/test_shared_params_from_rfa_866.py`, `tests/ci_shard.d/866-shared-params-extract.txt`,
this fragment; and (the #869 CI fix, second commit) `src/rvt/famgen/formula.py` + its `plugin/lib`
mirror, `tests/test_famgen_formula_850.py`, `docs/inbox/family-formulas.md`. Shipped: the extractor. Staged: nothing. No certification claim.
