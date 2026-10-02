# #918 — the alias-order sweeps scale with the archetype count, and CI reports its shard's budget

Stream: prompt-archetypes. Issue: #918 (found while diagnosing #841's CI timeouts).

## What was wrong
`tests/test_archetype_alias_order_812.py` crosses every 2- and 3-permutation of an archetype's sized
parameters with its aliases, phrasings and separators.
- **The size.** The strut trapeze (#899) has 15 sized parameters, so its prompts were 90,352 of
  the file's 106,696 chains and 227,216 prompts across the six sweep variants
  (90,352 + 2 × 35,840 + 2 × 26,880 + 11,424).
- **The time.** The file took **385 s** on main `1a835d4`, measured alone, against about 30 s
  before #899.
- **The effect on CI.** Session CI kills the shard at 1500 s. Two #841 runs died at 88%: one on a
  shared box, and one alone against `1a0c6aa` with #912's new suites. The only signal was
  `shard_summary: ""`.

## What changed
**Sweeps** (`tests/test_archetype_alias_order_812.py`, generators only, no resolver change):
- **Which archetypes are reduced.** An archetype with more than `_FULL_SWEEP_MAX_PARAMS = 8` sized
  parameters is swept on a deterministic **cover**. Today that is only the trapeze. The cable tray
  has 8.
- **The other six are untouched.** Their prompt sequences are identical to main's in all six
  sweep variants: 16,344 / 18,496 / 18,496 / 13,872 / 13,872 / 2,684 prompts. Their docstrings'
  measured defect counts therefore still describe these generators.
- **What the cover keeps:**
  - every ordered parameter pair, in every sweep;
  - for chains, 390 triples chosen so that every ordered pair stands adjacent in slot 0–1 and in
    slot 1–2 of some triple (the adjacency #812's defect lived in);
  - every alias of every parameter in every sweep, with the alias index rotated per combination;
  - every phrasing and separator, rotated per case instead of crossed. The rotation is skewed one
    step per lap, so every word order meets every combination. Review round 1 found the unskewed
    rotation (`counter % n`, 4 orders over 16 / 8 / 4 options) pinned each order to a quarter of
    them: PPQ only ever ", " with Q number-first, and PQ crosses only number-first. As a result,
    5 of the 7 restatement classes and 5 of the 6 cross classes that #812's defect fails were never
    generated.
- **Size.** The trapeze goes from 227,216 to 13,432 prompts across the six variants:

  | sweep | full | cover |
  |---|---|---|
  | chains | 90,352 | 3,960 |
  | restatements, each `where` | 35,840 | 2,240 |
  | contradictions, each `where` | 26,880 | 1,680 |
  | crossed | 11,424 | 1,632 |
- **New guards:**
  - coverage floors for the trapeze in every `_assert_coverage` call;
  - `test_a_covered_archetype_keeps_the_cover_guarantees` pins the adjacency cover and the alias
    coverage.

**CI** (`tools/dev/session_ci.sh`). While this PR was open, #934 landed on main with three changes:
the cap became configurable (`SESSION_CI_SHARD_TIMEOUT`), the cap now appears in the JSON as
`shard_timeout`, and a killed shard's summary reads "timeout/killed after N s". This PR keeps all of
that unchanged and adds only what is still missing. These fields are added when the shard actually
ran, and are measured against the cap it ran under:
- `shard_seconds`;
- `shard_budget`: `ok`, `near-limit` (over 80% of the cap) or `timeout` (rc 124 or 137, or at the
  cap);
- `shard_slowest`: at most 5 strictly pytest-shaped `--durations` lines, ASCII node ids with no
  spaces, read from the last 400 kB of the untrusted sandbox log;
- `shard_progress` for a killed shard, for example "88%".

The verdict rule is unchanged. `SHARD_RAN` and `SHARD_SECS` start at 0, so a refused shard carries
no budget and a caller's environment cannot leak in. Pinned by `tests/test_session_ci_budget_918.py`,
which runs the result block exactly as the script holds it.

## Evidence
- **Time.**
  - On main `7d2fcde`, alone on a 4-core session box: the file takes **105 s on main and 27 s with
    this PR**, meeting DONE 2's 60 s. #943 has made the resolver itself faster since the issue was
    filed.
  - On `1a835d4`, where #918 was measured: 385 s → about 70 s.
  - The remainder is the six full-swept archetypes. Their docstrings cite defect counts measured
    on exactly these prompts, so they are not thinned.
- **Detection is kept.** #812's defect was put back in a private copy, with alias-first phrasing
  always sorted first. Under the cover, the trapeze fails at the full product's rate. Measured on
  main `7d2fcde`, with the same numbers as on `e7b706d`:

  | sweep | cover | full product |
  |---|---|---|
  | chains | 615 / 3,960 (15.5%) | 15,157 / 90,352 (16.8%) |
  | restatements, `first` | 170 / 2,240 (7.6%) | 2,772 / 35,840 (7.7%) |
  | restatements, `cycle` | 133 / 2,240 (5.9%) | 2,217 / 35,840 (6.2%) |
  | contradictions, `first` | 125 / 1,680 (7.4%) | 2,092 / 26,880 (7.8%) |
  | crossed | 240 / 1,632 (14.7%) | 1,770 / 11,424 (15.5%) |

  Before review round 1's skew, crossed was 141 / 1,632 (8.6%), and 5 of the 7 failing restatement
  classes and 5 of the 6 failing cross classes were never generated.
- **The six other archetypes are byte-identical to main** in all six sweep variants, checked by
  hashing them on `7d2fcde`: 16,344 / 18,496 / 18,496 / 13,872 / 13,872 / 2,684 prompts. The
  trapeze goes from 227,216 prompts to 13,432.
- **The guarantee test** checks four things: the adjacency cover; every alias on its own, after
  longer aliases are removed, so "rod" does not count inside "rod spacing"; and that the rotation
  reaches every option for every order (3 or 4 orders over 4, 8 or 16 options). **It fails on all
  three mutants:**
  - the cover cut at 100 triples;
  - the alias index frozen at 0;
  - the unskewed rotation.
- **The budget JSON**, exercised on fake logs:
  - a killed shard is `timeout` with `shard_progress` "88%", fails, and keeps #934's summary;
  - exit 137 is `timeout` too;
  - 1300 s under a 1500 s cap is `near-limit` and passes;
  - 1300 s under a 2700 s cap is `ok`;
  - a refused shard carries no budget;
  - shell-ish, prose and non-ASCII log lines are dropped from `shard_slowest`.

## Open questions
- **Watch the shard's budget.** Main's shard took 919–931 s on #922's CI runs before #943's speed-up.
  `shard_budget` now flags the next creep at 80% of the cap, before it kills runs.

## BRANCH STATE
- **Files written:**
  - `tests/test_archetype_alias_order_812.py`: the cover, floors and guarantee test;
  - `tools/dev/session_ci.sh`: the budget fields, on top of #934;
  - `tests/test_session_ci_budget_918.py` (new);
  - `tests/ci_shard.d/918-sweep-budget.txt` (new);
  - this fragment.
- **Gates, on the branch rebuilt onto main `7d2fcde`:**
  - `test_archetype_alias_order_812.py`: 200 passed and 5 xfailed in 27 s;
  - `test_session_ci_budget_918.py`, `test_shard_list.py`, `test_ci_fresh.py` and `test_techlead.py`:
    93 passed, 2 skipped;
  - `bash -n` passes, portable paths are OK, and `sync_plugin.py --check` is in sync.
- **Shipped vs staged:** shipped. Test and CI tooling only; no file-format or engine change.
