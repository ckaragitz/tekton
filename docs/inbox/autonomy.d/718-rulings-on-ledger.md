# 718 — rulings on the ledger (AUTONOMY §12c fix-loop clause)

Fragment of the `autonomy` stream (index: `docs/inbox/autonomy.md`). Issue #718. Refs #711 #707 #302 #54.

## What was measured

2026-08-11, PR #711 (eng #707; the wave-40 ledger comment is on the board issue #56). The tech-lead
session ruled — in a cross-session `send_message` only — that the engineer's territory was extended
to a small `tests/conftest.py` re-aim (dropping two snapshotted native caches from
`context_constants()`, adding three `GF.bound()` tokens to `ladder_constants()`). When the engineer
wrote that ruling into its stream record, its own policy layer refused the edit. The refusal, as the
engineer reported it, is quoted verbatim in a public comment on #718
(https://github.com/ckaragitz/tekton/issues/718#issuecomment-5261613237); its core:

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
  posted on the PR/issue at the moment they are made; a `send_message` is transport, not the ledger;
  the engineer's record cites the public comment, never a session message; #711 cited as the case.
- Same section, "What an engineer session does differently": the engineer acts on a finding or
  ruling once it is visible on the PR/issue and cites the comment that shows it in its record.
- `.claude/commands/fanout.md`: the engineer-brief template gains the same sentence, and the
  fan-out instructions tell the tech lead to post whatever changes an engineer's remit on its PR in
  the same breath as the message.
- `tools/dev/review_brief.md` (the recipe the tech lead runs each tick), step 3: post the findings
  on the PR first or in the same breath as sending them; same for rulings and territory extensions.
- `tests/test_techlead.py::test_rulings_and_findings_go_on_the_ledger_when_made`: pins the rule by
  invariant tokens in those three files ("transport, not the ledger"; "at the moment they are made";
  "never a session message"), the way #342's rule is pinned — so a later trim cannot silently drop it.

The last two items are outside the territory #718 was filed with; the extension was recorded on
#718 (the comment linked above) before they were written — the rule applied to itself. No other
tooling change is needed: `add_issue_comment` is already how every evidence comment lands, and the
reviewers already read PR threads.

## Why this is the right altitude

S-2026-08-09-b/-h already say nothing may live only in a live session and everything decided is
logged on GitHub. The wave ledger (#342) applied that to *who is doing what*; this applies it to
*what they were told they may do*. The alternative — teaching engineer sessions to trust session
messages as authorization — is exactly backwards. Messages are unauthenticated and invisible; PR
comments are unauthenticated too (all sessions write under one identity, as §12c's Merge row already
says), but they are visible to every later reader, reviewer and record, which is the property a
citation needs.

## BRANCH STATE

- Branch `cam/718-rulings-on-ledger` from `main` @ `eac9772`; files: `docs/process/AUTONOMY.md`
  (§12c: one table row extended, one paragraph clause), `.claude/commands/fanout.md` (two
  sentences), `tools/dev/review_brief.md` (step 3 reworded), `tests/test_techlead.py` (one new
  test), this fragment (new; index `docs/inbox/autonomy.md` untouched).
- No `src/`, `plugin/`, `skills/` or hot file touched; the only `tools/` file is the review recipe
  (markdown), the only test change is the added pin.
- Gates: `python3 tools/dev/check_portable_paths.py` ok (3105 tracked paths with this fragment);
  `tests/test_records_layout.py` + `tests/test_techlead.py` green (see the PR for counts).
- Shipped on merge; nothing staged.
