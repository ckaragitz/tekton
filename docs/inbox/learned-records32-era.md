# learned: the 32-bit-id era + width-aware instruments (genesis-2023-reduce)

For KNOWLEDGE.md merge (orchestrator).  Full evidence:
`docs/inbox/genesis-2023-reduce.md`, `docs/writer/format-2023.md`.

1. **The version model gained a second axis.**  Release differences are no
   longer just class-ordinal drift: at 2023↔2024 the ELEMENT-ID WIDTH
   changed (32→64 bit), rippling into record framing headers, in-body
   ElementId values and the ElemTable wire (row size AND field order).
   The file's own schema declares the width — `Identifier` v1
   `{m_id:i32}` vs v2 `{m_id64:i64}` — so the law extends cleanly:
   *resolve ordinals by name; resolve the id width from the Identifier
   declaration; never key either off the year.*
   `rvt.versions.records32.reading32(path)` is the one-call read context
   for any release.
2. **Instruments must be width-aware or they lie in BOTH directions.**
   Baked `<q`/`+16`-era offsets made (a) `scan_stream_ids` silently find
   ~nothing (false-clean `latest_dangling` metric) and (b)
   `verify_reduced`/`verify_manipulated` flag EVERY stamp bad on a file
   whose 9,618 stamps were perfect (false-red).  Both silent-miss and
   false-alarm variants were caught only because rung gates fail RED and
   an independent audit re-measured the raw bytes.  Follow-up for the
   manipulate territory: `verify_manipulated` decodes edited records
   against the CANONICAL 2026 schema — a latent verification bug for
   2024/2025 files too (records32.verify_manipulated32 binds the file's
   own schema; the core fix is still open).
3. **Locks over memos.**  Written territory splits failed twice in one
   session (raced whole-file rung writes); a 12-line pid lockfile in the
   tool's mutating entrypoints ended it permanently.  Same lesson as
   certify-the-base: a rule a process can violate silently must be a gate
   the tool enforces.  Also: batch numbering must scan EVERY campaign dir
   (`experiments/**/batch_*.json`), not a hand-kept list — the hand list
   collided with the 2024 fleet's numbering within hours.
4. **The recipe is now proven THREE releases deep** (2026 → 2025 → 2023,
   2024 in flight): same seeds, same K3/K4 shapes, per-rung deltas within
   ~1 element of the certified 2025 ladder.  Cross-release cost when a
   genuine format delta appears ≈ one reversible patch layer + faithful
   instrument variants; core modules stay untouched.
5. **Counsel/C4**: the per-release ESSchemaStorage product corpus now has
   FOUR pinned constants (2023 `48e9c7b3…` 1,038 pairs/922,774 B; 2024
   `f879bf3d…`; 2025 `5331797d…`; 2026 `99554c01…`), and the History
   terminal 2662 is NOT a release marker anywhere (froze before 2023) —
   release identity is `BasicFileInfo Format:` alone.
