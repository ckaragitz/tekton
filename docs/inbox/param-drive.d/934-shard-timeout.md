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

- **Disclosure.** A posted CI line run under a cap other than 1500 names the cap
  (`.github/prompts/tick.md`, `tools/dev/review_brief.md` step 1). The JSON stays
  local; the PR comment is the lasting evidence.

## Review of #933 (head `20a378a`, 🛑)

- **Overflow.** The range check failed open on an overflowing number:
  `99999999999999999999` passed the digits-only `case`, `[ -lt ]` errored, and the run
  went on. The value must now be 3 or 4 digits before any arithmetic, and the range
  test treats an error as a refusal.
- **Killed runs.** A kill after the grace period (rc 137) is named in the summary like
  a timeout (rc 124).
- **Header.** The script header lists `shard_timeout`.

The override is for a slower machine, never for a slower suite. #934 stays open for
the real headroom work: the shard on an idle machine in ≤ 900 s.

## BRANCH STATE
- `tools/dev/session_ci.sh`; this fragment.
- Gates: `test_ci_fresh`, `test_techlead` and `test_shard_list` pass; `bash -n` is ok; the input table was re-checked (overflow, 599, 3601, a space, 9e3 and empty
  are refused; 0900, 900 and 2700 are accepted).
- Shipped with PR #933. Its CI ran with `SESSION_CI_SHARD_TIMEOUT=2700`, recorded in the
  verdict.
