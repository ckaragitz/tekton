# 866 step 3 — apply a user's parameter profile to a family we generate

Stream **family-shared-params** (fragment). Issue #866 (from steer #865), DONE 2.
Territory: `src/rvt/famgen/param_profile.py` (new), `src/rvt/famgen/skeleton.py`
(`FamilyDoc.param_profile` field and finalize hook, `SharedParamsArg`, `_is_instance_param`),
`tools/make_family.py` (flags), `tools/shared_params_from_rfa.py` (the #869 review nits),
tests plus shard drop-ins, this fragment, and the regenerated `plugin/lib` mirrors.

## What was built

* **`rvt.famgen.param_profile`:**
  * `load_profile`. It refuses anything but `tekton.param-profile/1`.
  * `select(profile, category=… | family=…, share=0.5)`. It picks the parameters that at least
    `share` of the profile's families of the generated family's category carry *as their own*
    (a label's or nested family's definition, `instance: null`, never counts). Each is bound
    the way most of those families bind it; a tie is said and written by type. `family=NAME`
    mirrors one profile family exactly.
  * `apply(doc, params)`. It adds each as a **blank SHARED parameter** at the profile's GUID,
    carrying its storage class, spec, palette group, visibility / modifiability /
    hide-when-empty flags and instance binding.
* **Blank means no invented value.** A private probe of the reference pack (counts only)
  shows a Revit-born family stores an unfilled parameter as the all-empty row (`m_str` "",
  `m_int` 0, `m_value` 0.0, `m_elemId` -1). That is exactly the row our writer emits, so a
  profile adds definitions and never a value (S-2026-08-11-a).
* **Left out, and said in the notes:**
  * parameters the family already authors, by GUID or by name (the family's own definition
    stands);
  * storage classes this writer does not author: `ParamDefTextBrowseEdit`,
    `ParamDefImageSymbolBrowseEdit`, and `ParamDefFamType` (its value is a nested family's type).
* **Wiring:**
  * A `ProfileRequest` rides the existing `shared_params=` argument every family constructor
    already passes to `new_family_document`, so no factory signature changed.
  * The document applies it **once**, at its first `finalize()`, when its category is known.
  * `rows=` carries a plain shared-parameter TXT alongside.
  * `_is_instance_param` is the one test of "bound per instance", shared by the value rows
    (#868) and the formula check, so a shared instance parameter (`refs["instance"]`) is
    treated alike in both. It carries the comment the #868 review asked for: built-ins are
    not looked up.
* **`make_family {panelboard,transformer,luminaire,device}`** takes four new flags:
  `--param-profile PROFILE.json`, `--profile-family NAME`, `--profile-share F` and
  `--profile-values VALUES.json`.
* **Values** (owner request, "fill in the eVolve parameter values like the library does";
  steer #873, part of #875). `ProfileRequest(values=…)` or `--profile-values` names, per
  parameter (by GUID or name), what to put in it:
  * a constant, which must suit the storage class: text for text / URL, a bool or 0/1 for
    Yes/No, a number in internal units for a measurable value. Anything else is refused
    and said, never coerced.
  * `{"formula": "Width"}`, written as the parameter's formula (#850), so the value tracks
    the family's own parameter in every type.
  * Everything else stays blank. Values for parameters the profile did not select are
    named in the notes.
  * The values file is the *user's* (it can come from their own library's conventions). It
    lives with their private profile, never in this repository.
* **Fix found on the way (`skeleton._apply_formulas`).** A formula's spec was compared
  *with its version suffix*. A library length parameter (`…length-2.0.0`) driven by our
  `Width` (`…length-1.0.0`) was refused as a type mismatch. Specs now compare version-less;
  a genuinely different spec (a length into a current) is still refused, and pinned.

## Evidence

* `tests/test_param_profile_866.py` (synthetic profile; made-up GUIDs and names): 20 passed.
  * **Selection:** the share threshold, majority binding, a tie, `instance: null` excluded,
    one named family, the empty and foreign-schema cases.
  * **Application:** classes, specs, groups, flags and GUIDs checked; the family's own `Width`
    kept; the multi-line kind left out, with a note.
  * **Written transformer:** family-mode VALID 0 errors, provenance ok. Every added value row
    is all-empty. The extractor reads the same bindings and flags back.
  * **Idempotence:** applied once across three finalizes.
  * **No-op:** a profile that selects nothing gives a byte-identical device.
  * **CLI:** `--profile-family` works end to end.
  * **Load + place:** into a front-door host, the placed instance carries exactly 2 more
    instance rows, every row resolves, validator 0 errors.
  * **Values:**
    * a text constant by name and a Yes/No by GUID are written;
    * a length formula over `Width` is written and evaluated per type;
    * a length formula into a current is refused at build;
    * a number offered for text is refused and left blank;
    * an unselected name is reported;
    * the CLI's `--profile-values` works end to end.
* **The owner's 45 kVA transformer, delivered (private run; counts only):**
  * 13 library parameters: 7 given constants (identity text; the catalog number as the
    part number), 3 size parameters driven by formula from `Width` / `Height` / `Depth`,
    3 left blank as the library leaves them.
  * Revit 2026 and 2025 copies, each family-mode VALID 0 errors, provenance ok.
  * The values read back from the written files.
* **The owner's pack, private run** (counts only; outputs in git-ignored `samples/`):
  * 45 kVA transformer with the eVolve profile: 13 shared parameters added (10 per instance),
    family-mode VALID 0 errors, provenance ok.
  * The same for the panelboard.
  * Placed into a front-door host: 11 instance rows, 0 dangling, validator 0 errors.
  * The extractor reads 13 parameters back, 10 instance / 3 type.
* `pytest` famgen suites (skeleton, factory, instance rows, formula, determinism, router):
  333 passed / 22 skipped. `tests/test_shared_params_from_rfa_866.py`: 19 passed (4 new
  pins for the #869 nits).

## Corrections to step 1 (`866-extract-library.md`, #869)

* **`make_family --shared-params` does not accept every extracted TXT.** It accepts rows
  whose DATATYPE `rvt.famgen.skeleton.SHARED_DATATYPE_SPECS` knows and whose caption the
  factory authors by type. A caption the factory authors under another token (e.g. YESNO,
  URL, FAMILYTYPE) or per instance is refused. The profile path above is the route for a
  library's parameters; the TXT is for Revit.
* **"2 GUIDs carry two datatypes"** (the #866 study) was spec-*version* drift. The extractor's
  full-definition check records it as cosmetic variants; identity conflicts are 0.
* GUIDs are copied *normalised to lowercase*. Empty-GUID rows are named in the warnings.
  An empty file-group prefix falls back to `General`.

## Review round 1 (96008fd, 🛑) — fixed

* **A formula on a text / Yes-No / integer parameter was typed as a length.**
  * Cause: the extractor gives those classes no spec; `add_shared_parameter` got `""` and
    `_apply_formulas` fell back to length.
  * Fix: each class is typed by its own storage kind (`param_profile.CLASS_SPEC`). A text or
    integer formula is refused by the formula writer and said; a Yes/No formula is written
    as the Yes/No it is; a material formula is refused before it gets there.
* **NaN / ±inf values** are refused, never written or counted.
* **The share threshold** is an exact ceiling (25 × 0.28 is 7.000000000000001 in floating
  point, so the naive ceiling asked for 8 families). A share outside (0, 1] is refused.
* **A GUID-keyed value** matches in any case.
* **Spec versions are canonical.** Every parameter's spec is read at one schema version in
  the formula step (`_canonical_spec`), so a library `length-2.0.0` also combines with our
  `length-1.0.0` *inside* a formula, not only against the result.
* **Hard rule 1.** A bad profile, family name, share or values file no longer raises
  inside `finalize()`. The family is delivered without the profile and says why.
* **New tests:** 6, one per finding, plus the type-reads-instance refusal. Mutations
  (untyped formula, naive ceiling, NaN allowed, case-sensitive GUID) each fail a test.

## Open questions / next (#866)

* **Values the library derives itself** (#875): category-uniform constants and formulas
  read from the profile, rather than a values file the caller writes.
* **Text formulas** (#870). Until then a text value is a constant.
* **Next PRs:**
  * the prompt/route flag, so `route run --prompt …` can take `--param-profile`;
  * the estorage `.rfa` path (#866 DONE 4);
  * a viewer/desktop batch for a profiled family (no claim before it, hard rule 4).

## BRANCH STATE

Branch `claude/eager-franklin-xgzgda` from main after #869.
* Written: `src/rvt/famgen/param_profile.py`, `src/rvt/famgen/skeleton.py` (profile hook,
  `_is_instance_param`, the Kahn `deque`, `_canonical_spec`, the hard-rule-1 guard),
  `tools/make_family.py`, `tools/shared_params_from_rfa.py`,
  `tests/test_param_profile_866.py`, `tests/test_shared_params_from_rfa_866.py`,
  `tests/ci_shard.d/866-param-profile.txt`, this fragment, and the `plugin/lib` mirrors
  (sync_plugin).
* Shipped: profile application (engine + CLI).
* Staged: nothing. No certification claim.
