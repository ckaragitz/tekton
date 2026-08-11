# tests-release-scaffolding — the own-release test scaffolding lives once, in `tests/conftest.py` (stream record pointer)

**Stream:** eng #579 (issue #579; Refs #566, #533, #518, #451). Issue #579's Territory names this path as the
record; the wave brief that started the engineer session asked for the record to sit under a dated `eng #579`
header in `docs/inbox/shard-docs-audit.md` (the file that already records the two earlier `tests/conftest.py`
hoists, #523 / #542). The full record — what landed, the before/after tables, the shard totals, the follow-up list
and the closing `BRANCH STATE` — is that section:

- `docs/inbox/shard-docs-audit.md` § "2026-08-10 — eng #579: the own-release test scaffolding lives once, in `tests/conftest.py`"

One-paragraph summary for a reader who lands here first: `tests/conftest.py` now exports `FOREIGN_FIRST` /
`FOREIGN`, `native_constants()` / `ladder_constants()`, the opt-in `no_release_leak` fixture (+ its additive,
overridable `release_leak_extra`), `rewrite_stream` / `partition_of`, and the damaged-copy recipes
(`zero_partition_header`, `zero_schema_bytes`, `truncated_copy`, `cfb_header_zeroed_copy`); the six files that
carried private copies (`test_selfcheck_release`, `test_inspect_release`, `test_edit_text_release`,
`test_natively_framed`, `test_estorage_cli_release`, `test_edit_own_release`) import them, with every collected
id, assertion and outcome unchanged; `tests/test_conftest_scaffolding.py` is the AST law that keeps a seventh copy
from creeping back. `tests/test_rvt_edit_refusal.py`, `tests/test_release_ctx_refusal.py` and
`tests/test_edit_status.py` still carry theirs (eng #587's territory this wave) — the follow-up is listed there.
