---
description: Show the live state of the queue (the same data as the pinned 📋 board issue) and say what this session should do next
---

1. Print the brief: `python3 tools/dev/techlead.py brief` (falls back, in a cloud session without `gh`/`GH_TOKEN`, to reading the issue labelled `board` with the GitHub MCP `issue_read` tool — its body is the rendered board).
2. From it, tell your human in ≤ 8 lines: what is in progress and by whom, which PRs are stuck and on what, how many `ready` issues are free (vs the floor), any untriaged steers, and anything waiting on a person.
3. Recommend this session's next move per CLAUDE.md §4 session-start order: service own PRs → triage steers (`/techlead`) → replenish if below floor → otherwise `/next` (or name the top queue item).
