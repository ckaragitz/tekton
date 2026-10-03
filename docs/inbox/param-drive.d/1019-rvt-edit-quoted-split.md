# #1019 — an .rvt edit's quoted mark / name / value keeps its `;` / newline / `then`

## What was built
- `src/rvt/_quoted.py` is a new stdlib-only leaf. It holds #1018's quote rules, `quoted_spans`, and a door-agnostic `split_clauses(text, sep, further, refuse, joined)`.
- Both edit lanes now call it, so the rules cannot drift between them:
  - The family lane (`modify_family._split_clauses`) passes its `;` / newline / `then` / `, set|rename` separators and `set|rename` as its edit verbs. Its behaviour is unchanged; the one difference is that the refusal's JSON hint reads "a JSON op".
  - The `.rvt` lane (`frontdoor/edit._parse_text`) passes its `;` / newline / `then` / `and then` separators and its verbs: delete, remove, drop, move, rotate, rename, set, mark, retype.
- `mark 742670 as "A; B"` now stores the mark `A; B`, where main stored `A` and left `B"` unparsed. `rename … to "Panel; spare"` and `set parameter … to "a; b"` behave the same way.
- **The safety net is narrower in this lane, deliberately.** A clause kept whole across a separator inside quotes that no grammar reads is refused only when some fragment of main's split of that clause reads, so that main would have applied a cut part of it. A clause that main could read no part of stays in `unparsed`, as before, and the other edits still apply.
- This is #1018's third-review optional nit 1, applied here. The family lane keeps its broader refusal for now.

## Evidence
- `tests/test_rvt_edit_quoted_split_1019.py`, 15 cases:
  - quoted marks, names and parameter values with `;`, `then` and `and then`;
  - apostrophes and unit marks splitting as before;
  - two "runs across a further edit" refusals;
  - two "cannot read" refusals;
  - one kept-whole clause staying unparsed;
  - one plain multi-clause edit unchanged.
- Front door, edit and plugin suites (`test_edit_own_release`, `test_frontdoor`, `test_frontdoor_json_strict`, `test_one_job_module`, `test_release_ctx_refusal`, `test_stagelog`, this module, `test_edit_quoted_split_1017`, `test_edit_colon_1014`, `test_conftest_scaffolding`, `test_plugin_sync`): **295 passed / 6 skipped** with `RVT_SKIP_LARGE=1`.
- `test_bootstrap` + `test_coldstart`: 23 passed. `validate_plugin.py` passes, and `tools/sync_plugin.py --check` is clean.
- **Fuzz differential** of `parse_edit_spec`, main a207a13 against this tree. The fuzzer is `scratchpad/q19/fz.py`: 30,000 random multi-clause texts over this lane's heads, separators and quote atoms, for each of two seeds.

  | Seed | Silent fewer ops | Now refused | Same op count, value kept whole |
  |---|---|---|---|
  | 3 | **0** | 2,024 | 1,325 |
  | 9 | **0** | 2,141 | 1,344 |

  - About 1,800 of the refusals per seed are "cannot read", where main wrote a cut value (a mark `p` from `'p\nq'`, a mark `a` from `"a; b"`).
  - About 130 to 150 per seed are "runs across a further edit".
  - The rest are a kept-whole clause that then reads as one edit with an unresolvable reference.
  - Before the narrowing, the new refusals were 24% of texts; most of those were clauses main could read no part of.

## Open
- `Then` / `THEN` was never a separator, in either lane. That is a pre-existing case-sensitivity, unchanged here.
- Whether the family lane should take the narrower net is #1018's optional nit 1. It is not changed here.

## BRANCH STATE
- Files:
  - `src/rvt/_quoted.py` (new), `src/rvt/frontdoor/edit.py` and `src/rvt/convert/modify_family.py`, with their `plugin/lib` mirrors;
  - `tests/test_rvt_edit_quoted_split_1019.py` (new);
  - `tests/ci_shard.d/1019-rvt-edit-quoted-split.txt` (new);
  - this fragment.
- Staged: nothing. No desktop verdict is claimed (hard rule 4).
