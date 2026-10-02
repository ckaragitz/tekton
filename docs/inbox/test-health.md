# test-health — index

Stream: keep the test suite honest and the sandboxed CI shard fast (reds outside the shard,
stale pins, shard wall time). Records are fragments under `docs/inbox/test-health.d/`.

- `test-health.d/924-934.md` — #924: four stale pins re-pinned to their laws + a `FamilyDoc`
  deep-copy defect, all into the shard; #934: `resolve_prompt` ~4x faster, byte-identical.
- `test-health.d/965-perf-gate.md` — #965: the flagship 6-panel perf gate is a ratio to a fixed
  machine-speed reference (min of 2 samples, ceiling 24.0); the 8 s wall ceiling is now an 18 s
  runaway guard.
