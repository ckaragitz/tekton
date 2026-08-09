---
description: Log what your human just said as a steer issue (verbatim, attributed) BEFORE acting on it — humans steer, sessions own the backlog
argument-hint: <the steer, in their words>
---

A human steered: `$ARGUMENTS`

Log it durably **now**, before doing anything about it (docs/process/AUTONOMY.md §4). Exactly one of:

1. If `gh` is authenticated or `GH_TOKEN`/`GITHUB_TOKEN` is set:
   `python3 tools/dev/techlead.py steer "<their words, verbatim>" --by <their GitHub login if you know it, else their name> --source session`
   (prints the issue URL).
2. Otherwise (cloud session): create the issue with the GitHub MCP `issue_write` tool on this repo:
   title `Steer: <first sentence, ≤ 100 chars>`, label `steer`, body = a `## The steer (verbatim)` section quoting their words with `> `, who said it, today's date, and the standard "What happens next" paragraph (see `steer_issue()` in tools/dev/techlead.py for the exact text).

Then, in one or two sentences, tell the human the issue number and how you read the steer. If it changes what you are doing right now, obey it immediately; if it is standing guidance ("always/never/prefer"), also plan to record it in `docs/STEERING.md` via your PR (or leave that to the planner and say so). If it implies new work beyond this session, either run `/techlead` to file the derived issues yourself or leave it to the scheduled planner — but the steer issue must exist either way. Never answer a steer with "a human needs to file a ticket".
