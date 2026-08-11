# process-friction -- index (stream record kept as index + fragments, `docs/inbox/README.md`)

Process friction filed and fixed like product bugs (PG7, `area:process`): collisions, stale verdicts, claim races,
anything that costs an engineer round-trip without changing a byte of product. One fragment per PR under
`docs/inbox/process-friction.d/<issue>-<slug>.md`; add a line below when you add one.

- `636-record-fragments.md` -- records may be index + per-PR fragments; per-PR test modules for shared surfaces; the layout law (#636).
- `638-fragment-seams.md` -- the layout law moves into `check_portable_paths.check()` so `ci_fresh.sh` feels it at merge time; worker/techlead/AUTONOMY name the fragment form; `recent_records()` newest-first (#638).
