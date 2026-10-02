# test-health — index

Stream: keep the test suite honest and the sandboxed CI shard fast (reds outside the shard,
stale pins, shard wall time). Records are fragments under `docs/inbox/test-health.d/`.

- `test-health.d/924-934.md` — #924: four stale pins re-pinned to their laws + a `FamilyDoc`
  deep-copy defect, all into the shard; #934: `resolve_prompt` ~4x faster, byte-identical.
