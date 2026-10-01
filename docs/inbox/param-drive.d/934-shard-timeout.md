# 934 — the sandboxed CI shard's wall-clock cap is configurable and recorded

Stream: **param-drive** (fragment; the process change rides PR #933 because a session
may hold one PR at a time). Issue **#934**.

## Why
On 2026-10-01 the session's container restarted twice. The new container runs about
**1.4×** slower: `test_archetype_alias_order_812`'s two `contradicted_dimension` cases
take 124–125 s on both main `9cdb82d` and #933's head `63b8653`, against about 90 s under
load before the restart. The shard (about 1,110–1,180 s on the old machine) then cannot
finish inside the hard-coded `timeout 1500`:

| Run | Load | Reached | `shard_rc` |
|---|---|---|---|
| #933 run 1 | with a benchmark and a profiling agent | 97% | 124 |
| #933 run 2 | alone | 80% | 124 |

That makes every head red regardless of its content.

## What changed (`tools/dev/session_ci.sh`)
- **`SESSION_CI_SHARD_TIMEOUT`.** An integer from 600 to 3600, default **1500 (unchanged)**,
  that sets the shard's cap. Anything else exits 2 before a run starts.
- **The cap is recorded.** It is written to the verdict JSON as `shard_timeout`, so every
  posted verdict shows whether an override applied.
- **A timeout names itself.** `shard_rc` 124 now writes `shard_summary` as
  `timeout after N s`, instead of an empty string. It still fails, because only an
  "N passed" tally can be green.

The override is for a slower machine, never for a slower suite. #934 stays open for
the real headroom work: the shard on an idle machine in ≤ 900 s.

## BRANCH STATE
- `tools/dev/session_ci.sh`; this fragment.
- Gates: `test_ci_fresh`, `test_techlead` and `test_shard_list` pass; `bash -n` is ok.
- Shipped with PR #933. Its CI ran with `SESSION_CI_SHARD_TIMEOUT=2700`, recorded in the
  verdict.
