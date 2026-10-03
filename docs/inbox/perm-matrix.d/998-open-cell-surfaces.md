# #998: the open cell, its stamp and the walls + families shape on every remaining surface

Refs #998 (widened after the review of #999), #996, PG1.

## What was built
The independent review of #999 found surfaces outside #996's territory that still described the **old** cell and its dead stamp:
- the old cell: "created walls AND our generated placed families in ONE file … each alone passes";
- the dead stamp: `PROOF-ONLY: walls+families combination unverified`. The engine has not emitted it since the stamp was keyed to placed instances.

One surface also called the `--strict` pair "TWO coordinated **proven** files". That overclaims: the equipment file is the open cell.

Every surface now states the same three things:
- the open cell: PLACED INSTANCES of our generated families on our composed base (genesis-audit #48, issue #16);
- the stamp: `OPEN_CELL_STAMP`;
- the walls + families shape, exactly as `matrix.WALLS_FAMILY_SHAPE` states it.

The surfaces:
- `plugin/skills/tekton-author/SKILL.md` item 3 (hot file);
- `tools/frontdoor.py`: the module docstring and the `--strict` help (hot file);
- `plugin/README.md`: the open-cell bullet, and the `go author` example's stamps;
- `plugin/agents/bim-job-orchestrator.md`, `plugin/agents/tekton-author-agent.md`;
- `src/rvt/convert/add_to_project.py`:
  - the docstrings and the `--strict` help;
  - two runtime degradation strings: the walled-target note now says walls + families is "certified only as walls + one loaded family, verdict #27", and the collapse note no longer says "proven-shaped";
- `src/rvt/convert/merge_ifc.py`: the docstring and the `--strict` help;
- `tools/route.py`: the `--strict` help.

Small items from the same review:
- `SKILL.frontdoor.md` gets its missing verb ("… verdict #27) PASS").
- `combination_check` says "1 loaded family" in the singular (`intent._fams`).
- The #990 guard's docstring names its known false-pass classes: a negated caveat, a caveat that belongs to an unregistered file, and a separator group.

## Evidence
- `tests/test_open_cell_996.py` covers more:
  - `QUOTING` adds the tekton-author SKILL.md, the README, the orchestrator agent and `tools/frontdoor.py`.
  - `SCANNED` adds `plugin/README.md`, `plugin/agents/*.md`, `plugin/commands/*.md`, `src/rvt/convert/*.py`, `tools/frontdoor.py` and `tools/route.py`.
  - The overclaim pattern adds the dead stamp, the old cell sentence, "walls+families open bug" and "coordinated proven/certified files".
  - Each new pattern is pinned to fire on the old text.
- Token weight of the shipped text, in bytes (S-2026-08-09-g):

  | file | before | after |
  |---|---|---|
  | tekton-author SKILL.md | 15,898 | 16,154 (+256) |
  | README | 17,050 | 17,366 |
  | orchestrator agent | 10,419 | 10,645 |
  | author agent | 7,199 | 7,254 |

  The growth is the full stamp, which replaced a shorter dead one.
- Gates (`RVT_SKIP_LARGE=1`): test_open_cell_996 + test_doc_caveats_990 + test_frontdoor + test_router + test_convert + test_convert_combo + test_plugin_sync + test_plugin_validate + test_target_version_first + test_sync_zip + test_bootstrap: **389 passed / 34 skipped**. `sync_plugin.py --check` in sync; `validate_plugin.py` PASS.

## BRANCH STATE
- Files:
  - the surfaces listed above, and their `plugin/lib` mirrors (sync);
  - `src/rvt/frontdoor/{intent.py,SKILL.frontdoor.md}`;
  - `tests/test_open_cell_996.py`, `tests/test_doc_caveats_990.py` (docstring);
  - this fragment.
- Staged: nothing. Wording certifies nothing (hard rule 4).
