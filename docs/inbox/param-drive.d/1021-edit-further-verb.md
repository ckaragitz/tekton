# #1021 — a quoted value whose second part only starts with a verb is stored

## What was built
- `rvt._quoted.split_clauses` used to refuse a quoted span that ran across a separator followed by one of the lane's verb words. Both edit lanes therefore refused values such as:
  - `rename LP-1 to "Main; Mark B"`;
  - `set Note = "Hex bolt, set screw included"`.
- It now takes the lane's own `reads` predicate. A span is refused only when the old quote-blind split's fragment after that separator is one the lane would actually have applied:
  - **`.rvt` lane:** `_reads`, its grammar regexes. A fragment shaped like a command, such as `delete later"`, still counts, because the old split refused the whole edit on it as well (`rid`).
  - **Family lane:** new `_reads(inv, …)`. A fragment counts as a further edit if it is any of:
    - a rename;
    - a `set` with an explicit `=`, `to` or `:` (so a mistyped `set Material = steel` is refused);
    - a `set` whose caption is a real parameter (`param_by_caption`);
    - a fragment the grammar itself refuses (the safe side).
    `set screw included` and `set up later` are text.
- The family lane's "cannot read" refusal is **not** narrowed (see the review round below).
- Kept refusals:
  - `'heavy; set Mark = workers'`;
  - `"x; set Mark"`;
  - `'a, rename family to B'`;
  - `mark … as 'heavy; delete 1466502 workers'`;
  - `rename … to "Spare then delete later"`.

## Evidence
- `tests/test_edit_further_verb_1021.py`, 22 cases across both lanes. `test_edit_quoted_split_1017.py` now passes an inventory to `_split_clauses` (the new signature) and is otherwise unchanged.
- **Suites:** the edit, convert and front-door suites (27 modules: the #1014 set plus the 1017, 1019 and 1021 modules and the six front-door modules of #1019) give **849 passed / 41 skipped** with `RVT_SKIP_LARGE=1`. `tools/sync_plugin.py --check` is clean.
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

## Review round 1 (PR #1022, head 9b750f8, 🛑)
- **Blocking.** The family-lane narrowing (unreadable kept-whole clause → `unparsed`) dropped a mistyped edit silently. `set Finsh = "line one\nline two"; set Material = PVC` applied Material only, where main and old both refused.
- The family lane shows no `unparsed` to the user; only the `.rvt` lane's manifest does. My first attempt, a grammar-level test for the narrowing, still missed `set Bend: 'EMT, set aside'`, because a colon after an unknown caption is not matched.
- **Fixed.** The narrowing is reverted in the family lane: a kept-whole clause that this lane cannot read is always refused, as on main. **#1021's DONE bullet 3 is amended accordingly** (comment on #1021).
- **Also fixed (the review's nit 1).** A `set` fragment with an explicit `=`, `to` or `:` counts as a further edit even for an unknown caption: `"x; set Material = steel"` is refused.
- **Re-measured:**
  - Family fuzz against main (`r15/fuzz.py`, 40,000 texts per seed):

    | Seed | Silent fewer ops | Main refused, now applied | Refusal wording changed |
    |---|---|---|---|
    | 23 | **0** | 61 | 96 |
    | 41 | **0** | 29 | 106 |

  - In every "now applied" text, `unparsed` holds only ordinary, never-kept-whole clauses, which the old split also left unparsed.
  - Real conduit (`r18/real/fz.py`, 20,000 texts) against main: 47 main-refused texts now applied, 1 newly refused, 0 silent fewer ops. Against old b0a4de3: the 12 old-refused texts that now apply are `set screw included`-style text inside quotes.

## BRANCH STATE
- Files:
  - `src/rvt/_quoted.py`, `src/rvt/convert/modify_family.py` and `src/rvt/frontdoor/edit.py`, with their `plugin/lib` mirrors;
  - `tests/test_edit_further_verb_1021.py` (new);
  - `tests/ci_shard.d/1021-edit-further-verb.txt` (new);
  - `tests/test_edit_quoted_split_1017.py`, `tests/test_rvt_edit_quoted_split_1019.py` (adjusted);
  - this fragment.
- Staged: nothing. No desktop verdict is claimed (hard rule 4).
