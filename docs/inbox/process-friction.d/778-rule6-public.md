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

Three auto-loaded instruction files plus the README, corrected so no session
re-derives the block:

| file | change |
|---|---|
| `CLAUDE.md` §1 rule 6 | rewritten: public **on purpose** (#774), do not hold pushes or propose privacy; keeps what visibility never governed (counsel material, `PRODUCT_AUTHOR_PLACEHOLDER`, never "Autodesk Revit" as our author string); adds the duty public visibility actually creates |
| `docs/PROGRAM.md` | the "Not goals" clause *"No public remote (rule 6)"* corrected |
| `docs/STEERING.md` | standing row **S-2026-09-10-a**, appended newest-last, no existing row rewritten |
| `README.md` (two places: the front-matter posture block and §hard rules) | the same correction on the **public front page** — the copy an outsider and a fresh-clone session read first. Both found by this PR's independent reviews, not by its author: §hard rules because the first evidence grep was scoped to the three auto-loaded files, and the front-matter block — which cited rule 6 as authority for *"the repository itself stays private"* — because the second grep still only knew the exact phrase "keep this repo private". |

The new obligation is the point of the rewrite, not a footnote: **a push to a
public remote is not retractable** — a later flip to private does not un-publish
history — so the rule now forbids *adding* sensitive material (third-party
personal data above all, secrets, fresh counsel analysis) rather than forbidding
the remote.

## Evidence

Repo-wide and deliberately over-wide — a narrow grep is what let two of these
survive earlier passes. `README.md` was missed by a grep scoped to the three
auto-loaded files; `README.md:25` was then missed *again* by a grep whose
pattern only knew the exact phrase "keep this repo private", 111 lines above
the line that had just been fixed. Both were found by this PR's independent
reviews, not by its author. The pattern below is the widened one; this record
excludes itself, since it quotes every phrase it searches for:

```
$ grep -rniE "keep this repo private|no public remote|nothing here goes to a public remote|stays private|repo private" \
      --include="*.md" . | grep -v "process-friction.d/778"
docs/STEERING.md:33                   | S-2026-09-10-a | … The repository is **public on purpose** and stays that way …
docs/inbox/process-friction.md:9      … hard rule 6 said "keep this repo private" while the repo was public on purpose …
docs/product/architecture.md:59       - **What stays private:** the Python engine, the schema/paging/ECC/object-
docs/inbox/rvt-to-ifc-param-carrier.md:27   … `_KIND_OF_CARRIER` stays private there —
```

The first two are this stream's own prose quoting the old rule to say what it
supersedes. The last is a Python scoping remark, unrelated. `architecture.md:59`
is a real stale line and is listed below as deliberately not fixed here.

**No instruction file still tells a session to make this repo private** — which
is the claim that matters, and is narrower than "no file contains the word".

Gates: `check_portable_paths.py` **ok, 3191 tracked paths**; `sync_plugin.py
--check` **clean** (deny-audit clean, identity scan == allowlist, assets
verified); `validate_plugin.py` **PASS**. No code changed, so no test module
applies. The plugin gates ran because they are cheap and this branch must not
be the one that lets drift through — *not* because these files ship in the
bundle: `tools/sync_plugin.py` mirrors none of `CLAUDE.md`, `docs/PROGRAM.md`
or `docs/STEERING.md` (an earlier draft of this record claimed it did; it does
not).

## What this deliberately does NOT fix

**What is already public.** #774 records that the decision settles *where the repo
lives*, not that everything rule 6 named belongs in a public history:

- `plugin/assets/genesis/*.rvt` carry **eight Autodesk employee usernames and
  their `C:\Users\…` paths**, every one of them enumerated in the tracked
  `tools/plugin_identity_allowlist.json` — cited there rather than restated
  here, which is what the rule this PR writes asks of a new file. #19 owns the
  scrub but is scoped as a *shipping* concern; public visibility makes it a
  *disclosure* concern.
- `docs/product/COUNSEL-BRIEF.md` — an inventory of this project's own legal
  exposure — is tracked and publicly readable.

Both predate the decision and sit in every commit since 2026-08-09, so neither is
fixed by editing a rule; retracting them would need a history rewrite. Called out
on #774 rather than silently carried.

**The trust model of the model-backed runs — filed as #781.** The second
independent review of this PR found `docs/process/AUTONOMY.md:176` and
`.github/workflows/worker.yml:164` still asserting that those runs' inputs are
*"this private repository's files and issues/comments written by its
collaborators"*. Public-on-purpose means anyone with a GitHub account can now
write an issue or comment, so the untrusted-input surface of any model-backed
run is wider than the document claims — a stale **security premise**, not a
wording slip. Out of this PR's territory (the three auto-loaded instruction
files), so it is filed rather than fixed here. `docs/product/architecture.md:59`
("what stays private: the Python engine …") is stale the same way and rides on
the same issue.

## Findings for the process itself

The failure mode is general: **an instruction file can go stale against reality
and nothing notices until a session halts.** Rule 6 was checkable by machine
(repository visibility vs. the rule's claim) and nothing checked it. Worth a
follow-up — a cheap session-start assertion that the hard rules still describe the
world — but that is its own issue, **#780**, not this PR.

This PR is its own best evidence for why that issue is worth doing. Three stale
statements of the same rule survived an author who was *specifically looking for
them*: `README.md` §hard rules, `README.md:25`, and the trust-model premise now
on #781. Each was caught by a reader who had not written the previous fix, and
each time the miss was a **grep scoped too narrowly** — to three files, then to
one exact phrase. A human-run grep is not a check; #780's is.

## BRANCH STATE

- Branch: `cam/778-rule6-public`, from `main` @ `0119d6b`.
- Files written: `CLAUDE.md`, `docs/PROGRAM.md`, `docs/STEERING.md`, `README.md`,
  this record.
- Shipped: the three corrections, gated as above.
- Staged, not shipped: nothing.
- Not done: the already-public material (#774, #19); the stale-rule detector
  (filed #780); the model-run trust model and `architecture.md` (filed #781).
