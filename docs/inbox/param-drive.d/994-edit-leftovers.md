# #994 — family-edit leftovers from PR #993's re-review

Stream: param-drive. Refs #994 #909 #993. This is a separate fragment so that
`909-edit-drives.md` stays PR #993's own record. The correction to that record
is below.

## Correction to the #909 record (2026-10-03)

`909-edit-drives.md`'s BRANCH STATE says the review fixes are "local, not
pushed". They were pushed: **PR #993 merged as `fd7b67b`**, and the review
fixes went in with it. Everything that record lists as written is on `main`.

## What was wrong and what changed (`src/rvt/convert/modify_family.py`, `family_regen.py`)

1. **A rename-type renamed the family too.** The PartAtom follow was a plain
   text replace. In a generated family the type name equals the family title,
   so "rename the type to Y" also set the title to "Y". "rename the type …;
   rename the family to X" (in that order) ended up titled "Y", and the
   re-read failed. Now `_patch_partatom_scoped` changes only each rename's own
   elements, matched against the input's PartAtom, so order does not matter:
   - a family rename changes the entry's own (first) `<title>` / `<id>`, the
     feature `<A:title>`, and the design file's `OLD.rfa`;
   - a type rename changes only its `<A:type><A:title>` entry, or Revit's
     `<A:part …><title>` entry.

   The last rename on each target wins, and values are XML-escaped (before
   this, `&` was written raw). The rename-family re-read is now an exact match
   (it was a substring test), and the rename-type re-read also checks
   PartAtom's type entry. The old `_patch_partatom` is kept unchanged for its
   #646 caller and test.
2. **The name notes were not true in every case.** `family_regen.rebuild` now
   reports `name_stale` ({old, fresh}) and no longer writes the wording.
   `modify_family._name_note` writes one note per rebuilt edit:
   - It names exactly the names that are still stale: the family title unless
     there was a rename-family, and each type that carried the old name unless
     it was renamed.
   - It names the file that replaces the placed family, because Revit names a
     loaded family by its file name. If the output kept the input's file name
     (`--stem` = the input stem), loading it replaces the placed family.
     Otherwise it says the delivered `X.edited.rfa` loads as a SECOND family
     and to save or load it as the input's file name instead.
   - A rename-family gets no reload advice, because it makes a new family on
     purpose.
   - If no name is stale, there is no note.
3. **Grammar: `set Finish galvanized to spec` is refused, and the refusal
   names the recovery.** The first head of this PR added an exception to
   `_match_set` step (2) (`_bare_value_reading`). It read the words after a
   known caption as a value when the first word was lowercase and no word was
   one of the family's caption words. The independent review showed that rule
   writes to the wrong parameter: `set finish color to black` wrote Finish =
   "color to black", and `set Model number to ABC-1` wrote Model = "number to
   ABC-1". `main` refused both. No rule based on case or vocabulary separates
   a value's words from a mistyped parameter, so the exception is removed:
   - everything before the first `to` / `=` is the parameter, and a parameter
     the family lacks is refused by name;
   - when that name starts with one of the family's captions at a word
     boundary, the refusal adds a hint (`_value_hint`): write the value after
     `=`, as in `set Finish = galvanized to spec`. That form, and `set Finish
     to galvanized to spec`, write Finish = "galvanized to spec".

   A refusal can be recovered. A write to the wrong parameter cannot.
4. **Overridden ops.** In the parse, `_settle_overrides` marks every op that a
   later op in the same edit fully covers with `overridden_by`. "Fully covers"
   means:
   - the same parameter, where an unscoped set covers every type and a scoped
     set covers only its own type;
   - the same type's name; or
   - the family name.

   Each overridden op's notes are replaced by one note: "… is overridden by a
   later op in the same edit (op N: …) -- the last one wins; nothing of op k is
   written". `modify_family` applies and re-reads only `_effective_ops`.

   This also fixed a second bug the probe found on base: every
   "set A; set A" edit failed `self_checks_ok`, because the overridden op's
   re-read wanted its own value.

## Evidence

**Combination probe.** Every subset of size 1–3 of {dimension, rename-family,
rename-type, text, refused value}, in the given order and reversed, on conduit
and strut trapeze: 90 edits. The inputs were:
- dimension: `Length` 20 ft or `Strut Length` 36 in;
- refused value: `Length` 0 ft or `Strut Length` 4 in, which the generator
  refuses, so they go to the value path;
- text: `set Finish galvanized to spec`.

| | runs | raised | family-mode VALID | `rvt_validate` 0 errors | self_checks_ok | names true | geometry statements true | override notes true |
|---|---|---|---|---|---|---|---|---|
| head | 90 | **0** | 90 | 90 | 90 | 90 | 90 | 90 |
| base `fd7b67b` | 90 | 42 | 48 | (not run) | 30 | 18 | 48 | 36 |

On head, 34 edits were regenerated, 48 went to the value path, and 8 were
renames only. A "names true" pass required all of the following:
- the title, types and file name are the expected ones;
- if there is a stale-name note, it names exactly the stale names;
- it has reload advice exactly when there was no rename-family, and that
  advice names the output and input file names;
- it never says "reloads over the original".

A "geometry statements true" pass required all of the following:
- every disagreeing labelled dimension has a `VALUE ONLY` caveat;
- no `REBUILT` note is attached to a disagreeing caption;
- a regenerated edit has 0 disagreements;
- the last dimension op's value and the Finish text are in the file.

On base, the 42 raises were all `set Finish galvanized to spec` refused by
name. Of the 48 edits that delivered, 18 failed self-checks; each one was
either a rename-type before a rename-family or an overridden set.

**Tests.** `tests/test_edit_leftovers_994.py` is new, with 27 cases covering
every item, and has the shard drop-in `tests/ci_shard.d/994-edit-leftovers.txt`.
It is listed in `ADOPTERS` in `tests/test_conftest_scaffolding.py`, because
`MF.modify_family` enters `host_release_context` inside the engine.

## BRANCH STATE

Branch `fix-994` from `fd7b67b`, committed locally and not pushed (per the
engineer brief).

**Files written**
- `src/rvt/convert/modify_family.py`: `_match_set` (no bare-value
  exception) + the refusal's `_value_hint`; `_settle_overrides` / `_effective_ops` and the per-op
  notes in `parse_family_edit`; the scoped PartAtom follow in
  `apply_family_edits` (`_patch_partatom_scoped`, `_partatom_type_titles`);
  exact rename-family and PartAtom-aware rename-type re-reads; `_name_note`
- `src/rvt/convert/family_regen.py`: `rebuild` reports `name_stale` instead
  of the misleading note; docstring and comment corrected
- `plugin/lib/src/rvt/convert/{modify_family,family_regen}.py`: sync mirrors
- `tests/test_edit_leftovers_994.py`, `tests/ci_shard.d/994-edit-leftovers.txt`,
  `tests/test_conftest_scaffolding.py` (the `ADOPTERS` row)
- this fragment

**Gates** (RVT_SKIP_LARGE=1)
- `test_edit_leftovers_994` alone: 27 passed.
- One run of 13 files: 394 passed / 30 skipped (the skips need `samples/`).
  The files: `test_convert`, `test_convert_combo`, `test_edit_drives_909`,
  `test_edit_family_marks_678` / `_mass_659` / `_size_668`,
  `test_edit_leftovers_994`, `test_edit_own_release`, `test_edit_status`,
  `test_edit_text_release`, `test_router`, `test_conftest_scaffolding`,
  `test_rewrite_entries_646`.
- `test_plugin_sync`: 9 passed.
- `tools/sync_plugin.py`, then `--check`: in sync.
- `validate_plugin.py`: PASS (25).
- `check_portable_paths.py`: ok.

**Review round (PR #997, 2026-10-03).** The independent review was 🛑, with
one blocking finding (item 3 above, now fixed) and two nits, both fixed:
- `_partatom_title` returns the title unescaped (`Fam & X`, not
  `Fam &amp; X`), so `_name_note`'s comparison sees a stale title;
- in a Revit-born PartAtom, `<A:feature><A:title>` is a parameter group, so a
  rename-family patches it only in our own form (which has `<A:type>`).

Tests: `test_edit_leftovers_994` 37 passed; the 14-file edit-lane set (the 13 above + `test_plugin_sync`) 413 passed / 30 skipped. The `set Finish galvanized to
spec` legs of the combination probe now raise by design, as they do on base.
The reviewer's 54-edit probe used `set Finish galvanized to spec` as its text
op, so it was not re-run in that form.

**Shipped vs staged:** nothing is staged, and no viewer or desktop batch was
run. Every claim here comes from our own validator and checks; none is a
certification (hard rule 4).
