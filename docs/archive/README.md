# docs/archive — history, kept for provenance (do not read unless an id, a row key or an issue sends you here)

Everything below was true once and is superseded now. It stays in the repo so `git blame`, row-key citations in code
and old PR links keep resolving. **Rule (`CLAUDE.md` §4, archive rule):** when a direct session makes a doc stale it
`git mv`s it here, under `<YYYY-MM>/<the same relative path>`, adds one line to this table, and fixes live references —
in the same commit.

| Archived | What | Why / superseded by |
|---|---|---|
| 2026-10-08 → `2026-10/TRACKER-2026-10.md` | The August 2026 work queue and roadmap: P0 shipping gates G1–G4 with residuals r1–r5, Epic P (packaging / front door), F (Design→Revit bridge), G (productization), A (decode), B (open-format generator), C (APS, removed), D (native writer), E (verification), open questions, coverage hardening H1–H4. Last edited 2026-08-07. | Queue is GitHub Issues (`CLAUDE.md` §4); state and the P0 gate status moved to `docs/ORCHESTRATOR.md`. Row keys cited in code, manifests and docs (`TRACKER G2`, `TRACKER D4` …) resolve in this file. |

Not archived on purpose: `docs/coverage/` (the certification ledger and CRUD matrix that tools and tests read),
`docs/inbox/genesis-audit.md` (the running verdict log) and `docs/inbox/SUITE-COORDINATION.md` (a live rule), and the
August stream records in `docs/inbox/` (cited by path from code comments and docs; un-ingested — see
`docs/ORCHESTRATOR.md`, open fronts).
