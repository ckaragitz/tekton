# #1023 — a family edit with a clause the grammar cannot read says so

## What was built
- **The silent drop.** `parse_family_edit` (`src/rvt/convert/modify_family.py`) put unreadable clauses into `parsed["unparsed"]`, which nothing showed the user. So `set Length; set Material = PVC` applied Material and dropped the bare `set Length` silently. The `.rvt` lane shows its unparsed clauses in its manifest; the family lane did not.
- **Now:** each unparsed clause becomes a note, `not applied: '<clause>' was not understood, nothing was changed for it (say: …grammar…)`. `modify_family` already reports notes as degradations, so the note reaches the record and the status the skill relays.
- **The family is still delivered** with the clauses that did read (hard rule 1). The note is the honest label, and refusing the whole edit was the alternative not taken. An edit in which nothing reads is still refused, as before.
- **The optional nits from the PR #1022 review, carried here:**
  1. A caption inside a quoted value that is a near-miss of a parameter (`difflib` ratio of at least 0.8, e.g. `Widht`, `Notes`), or that several parameters contain (`Diameter`), counts as a further edit. So `"x; set Widht 600 mm"` is refused, as the old split refused it, while `set screw included` and `set up later` stay text.
  2. `rvt._quoted.split_clauses` reads a fragment both with and without the span's closing quote. So `rename … to "x then move 1466502 by 1,0,0 ft"` is refused again. That PR had rewritten the #1019 test case to `…ft then spare"` to keep it refusing; this record now says so.
  3. **Correction to the #1021 record.** It says `test_edit_quoted_split_1017.py` was "otherwise unchanged". Its `_inv()` also gained the captions `Finish` and `Length`, which changes which fragments read.

## Evidence
- `tests/test_edit_unparsed_note_1023.py`, 12 cases:
  - three "not applied" notes;
  - one fully read edit with no note;
  - three near-miss refusals;
  - two texts still stored;
  - the closing-quote fragment;
  - a delivered-record degradation on a generated conduit.
- An ADOPTERS row is added, plus the drop-in `tests/ci_shard.d/1023-edit-unparsed-note.txt`.
- **Suites:** `tests/test_edit_*.py`, `test_rvt_edit_quoted_split_1019`, `test_modify_family*`, `test_conftest_scaffolding`, `test_convert`, `test_router`, `test_convert_combo`, `test_reduce`, `test_frontdoor`, `test_frontdoor_json_strict`, `test_one_job_module`, `test_release_ctx_refusal`, `test_stagelog` and `test_plugin_sync` give **892 passed / 41 skipped** with `RVT_SKIP_LARGE=1`. `tools/sync_plugin.py --check` is clean.
- **Fuzz differentials against main a1e8d54:**

  | Lane / instrument | Seed | Texts | Silent fewer ops | Now accepted | Now refused | Refusal wording changed |
  |---|---|---|---|---|---|---|
  | Family, `r15/fuzz.py` | 5 | 40,000 | **0** | 0 | 9 | 40 |
  | Family, `r15/fuzz.py` | 77 | 40,000 | **0** | 0 | 12 | 34 |
  | `.rvt`, `q19/fz.py` | 5 | 30,000 | **0** | 0 | 10 | 7 |
  | `.rvt`, `q19/fz.py` | 77 | 30,000 | **0** | 0 | 11 | 6 |
  | Real conduit, `r18/real/fz.py` | 7 | 20,000 | **0** | 0 | 10 | 44 |

  Every new refusal is the safe side of nits 1–2: a leading apostrophe that pairs with a later possessive, now read as a further edit once the closing quote is stripped (for example, `'90s; mark 742670 as workers'`), or a near-miss caption.

## BRANCH STATE
- Files:
  - `src/rvt/convert/modify_family.py` and `src/rvt/_quoted.py`, with their `plugin/lib` mirrors;
  - `tests/test_edit_unparsed_note_1023.py` (new);
  - `tests/ci_shard.d/1023-edit-unparsed-note.txt` (new);
  - `tests/test_conftest_scaffolding.py` (an ADOPTERS row);
  - this fragment.
- Staged: nothing. No desktop verdict is claimed (hard rule 4).
