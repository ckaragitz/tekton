# docs/inbox — stream records

One record per stream, `docs/inbox/<stream>.md`, written on the stream's branch and carried in its PR (`CLAUDE.md` §4).
Record shape: what was built · old → new evidence (numbers, file:line, proof paths) · gate numbers verbatim · findings
and open questions · new work items (each also an issue) · `## Proposed KNOWLEDGE entry` · a closing `BRANCH STATE`
block (files written, gates, what is staged vs shipped, tip sha) · for a delegated session, the literal last line
`READY for review — <branch> @ <sha>`. Never write into another stream's record in its voice.

The **direct** session that lands the branch ingests the record: ratify or decline the proposed entries in
`KNOWLEDGE.md` (a `hot-file` PR), open or close the issues, then `git mv` the record to
`docs/archive/<YYYY-MM>/inbox/` — after grepping the repo, because code comments and docs cite records by path.

Not stream records, and live: `genesis-audit.md` (the running viewer verdict log, `## ORCHESTRATOR VERDICTS #N`) and
`SUITE-COORDINATION.md` (the one-canonical-suite-run rule).

**Known backlog (2026-10-08):** the ~150 records already here are from the August 2026 build; their branches are on
`main` and they have not been ingested or archived. The tripwire in `CLAUDE.md` §4 applies to records added after this
date; the August set is tracked as an open front in `docs/ORCHESTRATOR.md`. The two `learned-*.md` notes predate the
one-record rule (proposed ledger entries now ride inside the stream record).
