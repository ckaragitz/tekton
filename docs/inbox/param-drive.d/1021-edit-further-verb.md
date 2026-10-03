# #1021 — a quoted value whose second part only starts with a verb is stored

## What was built
- `rvt._quoted.split_clauses` used to refuse a quoted span that ran across a separator followed by one of the lane's verb words. Both edit lanes therefore refused values such as:
  - `rename LP-1 to "Main; Mark B"`;
  - `set Note = "Hex bolt, set screw included"`.
- It now takes the lane's own `reads` predicate. A span is refused only when the old quote-blind split's fragment after that separator is one the lane would actually have applied:
  - **`.rvt` lane:** `_reads`, its grammar regexes. A fragment shaped like a command, such as `delete later"`, still counts, because the old split refused the whole edit on it as well (`rid`).
  - **Family lane:** new `_reads(inv, …)`. A fragment counts if it is a rename, or a `set` whose caption is a real parameter (`param_by_caption`), or if the grammar itself refuses it (the safe side). `set screw included` names no parameter, so it is text.
- The family lane's "cannot read" refusal now matches the `.rvt` lane from #1020. A kept-whole clause no part of which reads stays in `unparsed`, and the other edits apply. For example, `also set Note = "a; b"; set Mark = 2` applies Mark.
- Kept refusals:
  - `'heavy; set Mark = workers'`;
  - `"x; set Mark"`;
  - `'a, rename family to B'`;
  - `mark … as 'heavy; delete 1466502 workers'`;
  - `rename … to "Spare then delete later"`.

## Evidence
- `tests/test_edit_further_verb_1021.py`, 15 cases across both lanes. `test_edit_quoted_split_1017.py` now passes an inventory to `_split_clauses` (the new signature) and is otherwise unchanged.
- **Suites:** the edit, convert and front-door suites (27 modules: the #1014 set plus the 1017, 1019 and 1021 modules and the six front-door modules of #1019) give **842 passed / 41 skipped** with `RVT_SKIP_LARGE=1`. `tools/sync_plugin.py --check` is clean.
- **Fuzz differentials against main 001a8b9:**
  - Family lane (`r15/fuzz.py`, 40,000 texts per seed):

    | Seed | Silent fewer ops | Main refused, now applied | Refusal wording changed |
    |---|---|---|---|
    | 7 | **0** | 194 | 142 |
    | 11 | **0** | 211 | 127 |

  - `.rvt` lane (`q19/fz.py`, 30,000 texts per seed):

    | Seed | Silent fewer ops | Main refused, now applied | Both refuse |
    |---|---|---|---|
    | 3 | **0** | 34 | 34 |
    | 9 | **0** | 41 | 32 |

  - In every "now applied" text, main refused over a kept-whole clause that had no readable fragment on the old split. That clause now stays unparsed, as it did before #1018.

## BRANCH STATE
- Files:
  - `src/rvt/_quoted.py`, `src/rvt/convert/modify_family.py` and `src/rvt/frontdoor/edit.py`, with their `plugin/lib` mirrors;
  - `tests/test_edit_further_verb_1021.py` (new);
  - `tests/ci_shard.d/1021-edit-further-verb.txt` (new);
  - `tests/test_edit_quoted_split_1017.py`, `tests/test_rvt_edit_quoted_split_1019.py` (adjusted);
  - this fragment.
- Staged: nothing. No desktop verdict is claimed (hard rule 4).
