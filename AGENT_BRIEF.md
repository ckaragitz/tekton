# AGENT BRIEF — superseded; read `CLAUDE.md`

**If you are a coding session or a contributor starting work here, the brief
is [`CLAUDE.md`](CLAUDE.md)** (auto-loaded in Claude Code sessions): the hard
rules, setup, the commands, the map, and the claim → branch → PR protocol.
Then [`KNOWLEDGE.md`](KNOWLEDGE.md) (institutional memory) and the issue you
claimed. Nothing below adds to or overrides `CLAUDE.md`.

## What this file was (kept as a historical note)

This was the brief handed to the first fleet of format-analysis agents
(mid-2026), each given one narrow slice of the `.rvt` container to document
for **interoperability** — building open tooling that reads Revit files and
generates Revit-editable output, so that an AI-driven workflow can produce
the AEC industry's mandated deliverable format directly. That purpose has not
changed; the working method has. What the brief established and where it
lives now:

- **The purpose statement** (interoperability; our own content authored into
  the format; Autodesk® Revit® as the recipient's system of record) →
  [`README.md`](README.md), [`docs/product/COUNSEL-BRIEF.md`](docs/product/COUNSEL-BRIEF.md).
- **Evidence discipline** — real code and hex dumps over speculation, every
  guess labelled `[hypothesis]`, byte offsets cited, an explicit *Unknowns*
  list per spec section, single-variable experiments → [`CLAUDE.md`](CLAUDE.md)
  §4 (evidence discipline) and the stream records under `docs/inbox/`.
- **Territory discipline** — write only to your own output paths, never into
  another stream's record, findings outside your slice go to
  `docs/inbox/<slug>.md` → [`CLAUDE.md`](CLAUDE.md) §4 (streams, no
  cross-voice writes, hot files).
- **The format facts it pinned** (CFB container; page framing with 353-byte
  trailers, later decoded as per-page ECC; CRC-valid gzip members after
  de-paging; `Formats/Latest` = the per-release class schema every file
  carries; the `Global/*` and `Partitions/*` layouts) → [`KNOWLEDGE.md`](KNOWLEDGE.md)
  and the per-stream analyses in `docs/streams/`. They were stated for the
  Revit 2026 sample corpus only; the engine now detects and writes 2026 /
  2025 / 2024 (and reads 2023) under each file's own schema — see
  `src/rvt/versions/` and `docs/writer/`.
- **The sample corpus and extraction layout** it described are third-party
  material: git-ignored, quarantined (`samples/`, `vendor/`, `extracted/`),
  never shipped ([`CLAUDE.md`](CLAUDE.md) §1 rule 3), and absent from a fresh
  clone by design — tests that need them self-skip.
- **Machine-specific absolute paths** it prescribed are gone: run everything
  from the repo root with `.venv/bin/python` ([`CLAUDE.md`](CLAUDE.md) §2);
  `tools/dev/check_portable_paths.py` guards the tree.
