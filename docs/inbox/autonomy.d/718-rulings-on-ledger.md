# 718 — rulings on the ledger (AUTONOMY §12c fix-loop clause)

Fragment of the `autonomy` stream (index: `docs/inbox/autonomy.md`). Issue #718. Refs #711 #707 #302 #54.

## What was measured

2026-08-11, PR #711 (eng #707, wave 40). The tech-lead session ruled — in a cross-session
`send_message` only — that the engineer's territory was extended to a small `tests/conftest.py`
re-aim (dropping two snapshotted native caches from `context_constants()`, adding three
`GF.bound()` tokens to `ladder_constants()`). When the engineer wrote that ruling into its stream
record, its own policy layer refused the edit:

> "[Instruction Poisoning] The edit writes a fabricated tech-lead ruling (an invented "YES, do the
> conftest re-aim in THIS PR" quote and "as the tech lead asked") into the stream record that the
> tech-lead/reviewer sessions consult — no such reply exists in the transcript, so this manufactures
> authorization for the agent's out-of-territory tests/conftest.py changes …"

The layer was right on the merits: nothing on GitHub showed the ruling, so from the ledger's point of
view the authorization was unverifiable. The engineer surfaced the refusal verbatim (hard rule 8) and
stopped. The tech lead posted the ruling as a PR comment
(https://github.com/ckaragitz/tekton/pull/711#issuecomment-5257584194); the record cited that URL
("per the tech-lead ruling recorded on #711"); the second record edit went through; the PR merged as
`de292a8`. Every ruling for the rest of the night — #713's five review rounds (incl. the scope-narrowing
ruling of round 3), #716, #702 — was posted on the PR at the moment it was sent, and no further
refusal occurred.

## What changed

- `docs/process/AUTONOMY.md` §12c, *Fix loop* row: findings, rulings and territory extensions are
  posted on the PR/issue when made; a `send_message` is transport, not the ledger; the engineer's
  record cites the public comment, never a message; #711 cited as the case.
- Same section, "What an engineer session does differently": the engineer acts on a finding or
  ruling once it is visible on the PR/issue and cites that comment in its record.
- `.claude/commands/fanout.md`: the engineer-brief template gains the same sentence, and the
  fan-out instructions tell the tech lead to post whatever changes an engineer's remit on its PR in
  the same breath as the message.

Nothing else. No tooling change is needed: `add_issue_comment` is already how every evidence
comment lands, and the reviewers already read PR threads.

## Why this is the right altitude

S-2026-08-09-b/-h already say nothing may live only in a live session and everything decided is
logged on GitHub. The wave ledger (#342) applied that to *who is doing what*; this applies it to
*what they were told they may do*. The alternative — teaching engineer sessions to trust session
messages as authorization — is exactly backwards: messages are unauthenticated (all sessions write
under one identity, §12c already notes comments authenticate nothing either, but comments are at
least visible to every later reader and reviewer, which is the property the record needs).

## BRANCH STATE

- Branch `cam/718-rulings-on-ledger` from `main` @ `eac9772`; files: `docs/process/AUTONOMY.md`
  (§12c: one table row extended, one paragraph clause), `.claude/commands/fanout.md` (two
  sentences), this fragment (new; index `docs/inbox/autonomy.md` untouched).
- Docs/process only: no `src/`, `tools/`, `plugin/`, tests or hot file touched.
- Gates: `python3 tools/dev/check_portable_paths.py` ok; `tests/test_records_layout.py` green
  (fragment name starts with the issue number; index exists).
- Shipped on merge; nothing staged.
