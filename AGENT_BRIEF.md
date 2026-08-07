# AGENT BRIEF — read this first, entirely

You are one of a fleet of analysis agents reverse-engineering the Autodesk
Revit `.rvt` file format for **interoperability** (a legitimate purpose:
building open tooling that reads Revit files and generates Revit-editable
output). You have one narrow slice of the format to crack. Be exhaustive
within your slice. Cite byte offsets. Prefer verified facts to guesses;
label every guess `[hypothesis]`.

## Project root

`/Users/ck/dev/things/tekton` — always use absolute paths.

- Python: `/Users/ck/dev/things/tekton/.venv/bin/python` (3.12, `olefile`
  installed). Install extra pure-Python deps with
  `uv pip install --python /Users/ck/dev/things/tekton/.venv/bin/python <pkg>`.
- Read `KNOWLEDGE.md` and `README.md` in the root before starting — they hold
  every established fact. Do NOT re-derive what is already there.

## The corpus (already extracted for you — do not re-extract)

Six Revit 2026 sample projects. For each, `extracted/<file>/` contains:

- `<Stream__Name>.bin` — the RAW OLE stream, still page-framed. Do not
  decode from this unless you are studying the page framing itself.
- `<Stream__Name>.logical.bin` — the DE-PAGED logical stream (353-byte
  page trailers stripped). **Decode from this.**
- `<Stream__Name>.gz/NNN.bin` — every gzip member of the LOGICAL stream,
  inflated and **CRC-verified** (13,583/13,583 valid). `index.json` gives
  each member's offset in the logical stream, consumed length, inflated
  size, crc_ok.
- `manifest.json` — raw/logical sizes, sha256 of logical, member counts.

Prefer the canonical reader over the files when convenient:
`from rvt.container import open_rvt` (package installed editable; run with
`/Users/ck/dev/things/tekton/.venv/bin/python`). It de-pages, enumerates
CRC-verified members, and exposes `logical()`, `inflate()`, `concat()`.
Wave-1 decoders already exist: `src/rvt/{meta,elemtable,partitions,content,
global_latest,strings_scan,schema_a,schema_b}.py`; prior art is cloned in
`vendor/{rvt-rs,phi-ag-rvt,magnetar-revit-test-datasets}`.

The six samples: `dach-sample-project` (huge, 139 MB, worksharing-ish),
`racadvancedsampleproject`, `racbasicsampleproject` (good default subject),
`rmebasicsampleproject` (MEP), `rstadvancedsampleproject`,
`rstbasicsampleproject` (structural, smallest at 6.7 MB — great for fast
iteration).

## Facts you must not contradict without hard evidence

- Container is OLE2/CFB. All files are Revit **2026** (build 20250227_1515).
- Storage: every raw stream is **page-framed** (64,896-byte pages, each
  followed by a 353-byte opaque trailer at raw offsets 64896 + k*65249).
  De-page first; then every gzip member has a VALID CRC. The old belief
  ("corrupt trailer, raw-inflate") was wrong and is fixed corpus-wide. Read
  the KNOWLEDGE.md "Storage layering — CORRECTED" section before you start.
- `Formats/Latest` is a **byte-identical, per-release schema** — **496,597
  bytes** inflated (sha256 6459a9a9…) — the on-disk archive class map:
  length-prefixed class names, ordered field records, C++ type strings,
  u16 type ids by definition order (+0x0c). Expect ~4,600 classes.
  `ADocument`'s fields correspond to the top-level `Global/*` streams.
- `Global/*` streams = 8-byte per-name constant prefix + gzip.
  `Partitions/<N>` = 44-byte header + ~128 KB gzip blocks with 26-byte
  block headers, three parallel record streams (seq 101/102/103), records
  `{i64 id, u32 stamp, u32 size, u32 class_word}` spanning blocks — see
  KNOWLEDGE.md "Partitions" section and `src/rvt/partitions.py`.

## How to work

1. Do the analysis with real code and hex dumps, not speculation. Show your
   evidence (offsets, hex, decoded values, statistics across all six files).
2. Write your deliverables ONLY to the exact output paths named in your task.
   Never edit `tools/`, `KNOWLEDGE.md`, `TRACKER.md`, `README.md`, or
   `AGENT_BRIEF.md`. Never touch another agent's output files.
3. Any code you write must run against the venv python above and print
   something useful (a table, a decoded dump). Include a `if __name__ ==
   "__main__":` demo that runs on `racbasicsampleproject` and, where cheap, all
   six files.
4. Your markdown doc must be a real spec section: layout tables
   (offset / size / type / meaning / evidence), worked examples with hex,
   confidence per claim, and an explicit **"Unknowns"** list.
5. If you discover something outside your slice, write it to
   `docs/inbox/<your-slug>.md` — do not act on it.

## Your return value

Your final message is machine-consumed, not human-facing. Return exactly the
structured object your task requests (summary, key findings, files written,
confidence, open questions, next steps). No pleasantries.
