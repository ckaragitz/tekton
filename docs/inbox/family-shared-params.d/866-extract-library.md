# 866 step 1 — read a user's shared-parameter library back out of their own families

Stream **family-shared-params** (fragment; the index `../family-shared-params.md` is left as is).
Issue #866 (from steer #865). Territory: `tools/shared_params_from_rfa.py` (new),
`tests/test_shared_params_from_rfa_866.py` (new) + its shard drop-in, this fragment.

## What was built

`tools/shared_params_from_rfa.py FAMILY.rfa|DIR ... --txt OUT.txt --profile OUT.json [--json]`
reads every `ParamElemExternal` of each family *inside the file's own release*
(`enter_own_release`, so 2024/2025/2026 families are read alike) and writes:

* a Revit shared-parameter TXT (`*META` / `*GROUP` / `*PARAM`, GUIDs verbatim) that our own
  `read_shared_parameter_file` and `make_family --shared-params` accept; and
* a parameter profile JSON (`tekton.param-profile/1`): per source family, which shared
  parameters it carries, instance or type (from the self Family's `m_familyParams` rows),
  and palette group; per GUID the name, definition class, spec, DATATYPE token, and
  visibility / modifiability / hide-when-empty flags. A GUID seen under two names or two
  datatypes is kept once and listed under `conflicts`, never silently overwritten.

DATATYPE comes from the definition class where the class decides it (`ParamDefString`,
`ParamDefYesNo`, `ParamDefInt`, `ParamDefMaterialBrowse`, `ParamDefURL`,
`ParamDefTextBrowseEdit`, `ParamDefNoOfPoles`), else from the measurable spec. That includes
the `spec.string` / `spec.int64` / `spec.bool` specs our own writer puts on text, integer and
Yes/No parameters. An unknown spec is written as its own spec id and counted as
`datatypes_unmapped`, never guessed.

The module holds **no library content**. The owner's library files are read only at their
request, and the outputs go where they say. For the owner's pack that is the git-ignored
`samples/reference-families/analysis/`; nothing from it is in this repository (rule 6, hard
rule 3).

## Evidence

* Synthetic round trip: our panelboard built with OUR `usecases/eaton-panelboard` shared file,
  extracted, and re-read. All 11 rows give GUID / name / datatype / description / visible
  identical to the source file. All 11 come back as type parameters (how the panelboard binds
  them). A rebuild from the *extracted* TXT carries the same 11 parameters at the same GUIDs.
* The first run of that round trip found a real gap: 7 of 11 datatypes came back as raw spec
  ids (`spec.string` / `spec.int64` were unmapped). Fixed, and pinned by a test.
* The owner's pack, read privately (numbers only): 421 families, 340 shared parameters,
  0 conflicts, 1 datatype written as its spec id.
* `pytest tests/test_shared_params_from_rfa_866.py`: 5 passed.

## Open questions / next (#866)

* Names can repeat under different GUIDs. Our reader rejects duplicate names, so the profile
  application (next PR) keys by GUID, not by the TXT.
* `ParamDefTextBrowseEdit` is written as TEXT. Its browse behaviour has no writer yet.
* Next PRs: the estorage `.rfa` path; `param_profile` application in the writer
  + `make_family` / route flags; regenerate the owner's families privately and validate.
* Carried from the #868 review, for the profile PR that touches `_type_param_entries`: a guard
  for Revit instance built-ins, and a note that `refs["instance"]` is set only by that path.

## BRANCH STATE

Branch `claude/eager-franklin-xgzgda` from main `1264faf`. Written: `tools/shared_params_from_rfa.py`,
`tests/test_shared_params_from_rfa_866.py`, `tests/ci_shard.d/866-shared-params-extract.txt`,
this fragment. `src/` untouched, so the plugin mirror is unaffected (the tool is not in the plugin
bundle). Shipped: the extractor. Staged: nothing. No certification claim.
