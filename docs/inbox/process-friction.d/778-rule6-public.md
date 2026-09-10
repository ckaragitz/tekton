# process-friction / #778 — hard rule 6 said "keep this repo private" while the repo was public on purpose

Fragment of the `process-friction` stream (index: `docs/inbox/process-friction.md`).
Nobody else appends to this file. Refs #774, #763.

## The friction, measured

A stale hard rule cost **10 days of held work** and is still holding one branch.

`CLAUDE.md` §1 rule 6 read *"**Keep this repo private.** … Nothing here goes to a
public remote."* The repository is public. A tech-lead session found the mismatch
on **2026-08-31** and did the correct thing under hard rule 8 — surfaced it rather
than working around it — filing #763 (`P0`, `needs-decision`) and holding every
push and merge. #763 went unanswered until **2026-09-10**. In that window:

- one session's #762 work (`cam/762-harden-after-report`, one commit) never left
  its laptop;
- this session's #703 and water-closet fixes were written, gated and committed
  locally with nowhere to go;
- this session **pushed once against the hold by accident** (`740ef89`, the PR
  #702 rebase) because it had not read #763 before pushing — logged on #763
  rather than buried.

The rule was not wrong when written; it went stale, and nothing made the staleness
visible except a session stopping dead. Filed as #780.

## What was built

Three auto-loaded instruction files, corrected so no session re-derives the block:

| file | change |
|---|---|
| `CLAUDE.md` §1 rule 6 | rewritten: public **on purpose** (#774), do not hold pushes or propose privacy; keeps what visibility never governed (counsel material, `PRODUCT_AUTHOR_PLACEHOLDER`, never "Autodesk Revit" as our author string); adds the duty public visibility actually creates |
| `docs/PROGRAM.md` | the "Not goals" clause *"No public remote (rule 6)"* corrected |
| `docs/STEERING.md` | standing row **S-2026-09-10-a**, appended newest-last, no existing row rewritten |

The new obligation is the point of the rewrite, not a footnote: **a push to a
public remote is not retractable** — a later flip to private does not un-publish
history — so the rule now forbids *adding* sensitive material (third-party
personal data above all, secrets, fresh counsel analysis) rather than forbidding
the remote.

## Evidence

```
$ grep -rniE "keep this repo private|no public remote|nothing here goes to a public remote" \
      CLAUDE.md docs/PROGRAM.md docs/STEERING.md
docs/STEERING.md:33: … supersedes the "keep this repo private" half of CLAUDE.md hard rule 6 …
```

One hit, in the new steering row, quoting the old rule deliberately to say what it
supersedes. Nothing else in the three files can be read as "make it private".

Gates: `check_portable_paths.py` **ok, 3191 tracked paths**; `sync_plugin.py
--check` **clean** (deny-audit clean, identity scan == allowlist, assets
verified); `validate_plugin.py` **PASS**. No code changed, so no test module
applies; the plugin gates ran because instruction files ride in the bundle's
documentation surface.

## What this deliberately does NOT fix

**What is already public.** #774 records that the decision settles *where the repo
lives*, not that everything rule 6 named belongs in a public history:

- `plugin/assets/genesis/*.rvt` carry Autodesk employee usernames — `hansonje`,
  `loboarch`, `campbes`, `okapaw`, `xuew`, `youyi`, `zhangg`, `gbs_subsuser6` —
  and `C:\Users\…` paths, indexed by the tracked
  `tools/plugin_identity_allowlist.json`. #19 owns the scrub but is scoped as a
  *shipping* concern; public visibility makes it a *disclosure* concern.
- `docs/product/COUNSEL-BRIEF.md` — an inventory of this project's own legal
  exposure — is tracked and publicly readable.

Both predate the decision and sit in every commit since 2026-08-09, so neither is
fixed by editing a rule; retracting them would need a history rewrite. Called out
on #774 rather than silently carried.

## Findings for the process itself

The failure mode is general: **an instruction file can go stale against reality
and nothing notices until a session halts.** Rule 6 was checkable by machine
(repository visibility vs. the rule's claim) and nothing checked it. Worth a
follow-up — a cheap session-start assertion that the hard rules still describe the
world — but that is its own issue, **#780**, not this PR.

## BRANCH STATE

- Branch: `cam/778-rule6-public`, from `main` @ `0119d6b`.
- Files written: `CLAUDE.md`, `docs/PROGRAM.md`, `docs/STEERING.md`, this record.
- Shipped: the three corrections, gated as above.
- Staged, not shipped: nothing.
- Not done: the already-public material (#774, #19); the stale-rule detector (filed #780).
