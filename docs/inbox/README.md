# docs/inbox/ -- stream records, and how parallel PRs stop colliding in them (#636)

Every stream (one issue = one charter) leaves a record here: what was built, the evidence (numbers,
not adjectives), findings, open questions, and a closing `BRANCH STATE` block. `CLAUDE.md` §4 says
*what* goes in a record; this file says *where*, so that five PRs feeding one stream in one evening
never again need keep-both rebases just because they all appended to the same end of file
(#583 → #626 → #627 → #632 → #635 on `ifc-assembly-rfa.md`, 2026-08-11).

## Two shapes, both valid

1. **Single file** -- `docs/inbox/<stream>.md`. Right for a stream one PR (or one session at a
   time) writes. Nothing about the existing ~230 records changes; none are migrated.
2. **Index + fragments** -- preferred as soon as a second PR wants to add a section to a stream
   somebody else may also be writing tonight (the assembly lane, `family-standards`,
   `shard-docs-audit`, `process-friction`, ...):

   ```
   docs/inbox/<stream>.md                       the index: charter, one line per fragment, standing summary
   docs/inbox/<stream>.d/<issue>-<slug>.md      one fragment per PR -- e.g. ifc-assembly-rfa.d/625-fallback-ifc.md
   ```

   * A fragment is written by exactly one PR and **never appended to by anyone else** -- a later
     PR on the same stream adds its *own* fragment. That is the whole trick, the same one
     `tests/ci_shard.d/` plays for the CI shard (#328): new files never conflict, shared EOFs do.
   * The fragment carries everything a single-file record would, including its own closing
     `BRANCH STATE`. The index stays short (think 5-30 lines): what the stream is, and one line per
     fragment (`- 625-fallback-ifc.md -- genuine fallback copies the source IFC beside the .rfa`).
     Adding that one index line is optional and cheap to rebase; the fragment is the record.
   * Converting an existing single-file record: leave its text where it is (it becomes a long
     index) and put your new section in `<stream>.d/<issue>-<slug>.md`. No history rewrite.
   * `learned-<slug>.md` notes for `KNOWLEDGE.md` stay single files at this level, as before.

## The law (pinned by `tests/test_records_layout.py`, in the CI shard)

* every `docs/inbox/<stream>.d/*.md` file name starts with its issue number and a dash:
  `<digits>-<slug>.md`, slug drawn from `[A-Za-z0-9_.-]` (portable on Windows/macOS -- no
  `: ? * " < > |`, no spaces; `tools/dev/check_portable_paths.py` judges the whole tree anyway);
* every `docs/inbox/<stream>.d/` directory has its index `docs/inbox/<stream>.md`
  (create a five-line one in the same PR if the stream is new).

Nothing else is enforced (the law judges file *names* -- direct `<stream>.d/*.md` children -- and
opens nothing; attachments such as `<issue>-evidence.json` and deeper paths are yours to organise):
fragment *content* follows `CLAUDE.md` §4 like any record, and the no-cross-voice rule holds per
fragment (a fragment is one stream's, one PR's, voice).

## Who reads these

`tools/dev/techlead.py brief` lists recently touched records with `git log -- docs/inbox`, a
directory pathspec, so fragments show up exactly like single-file records; nothing in
`tools/dev/coord.py` or `techlead.py` hard-codes the single-file path (checked for #636). The
router's evidence citations (`src/rvt/frontdoor/matrix.py`) name specific existing records and are
unaffected.
