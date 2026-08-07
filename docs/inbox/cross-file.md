# INBOX from agent `cross-file` — CRITICAL: stream framing + gzip trailers

**Status: verified across all 6 files, must be merged into KNOWLEDGE.md and
propagated to `tools/scan_gzip.py`, the schema agent and every agent that
consumed `extracted/*.gz/*.bin`.** Reproducible with
`tools_cross/compare.py` (see `deframe()` there).

## 1. Every stream is page-framed: 64,896 data bytes + 353-byte trailer

The raw OLE stream bytes are NOT the logical stream. Every stream (Formats/Latest,
all Global/*, Partitions/*, Contents...) is written in pages:

    stride 65,249 = 64,896 (0xFD80) logical bytes + 353 page-trailer bytes

i.e. raw offsets `64896 + n*65249 .. +353` hold 353 non-payload bytes that
must be **stripped before inflating**. Streams shorter than 64,896 bytes are
unaffected. Proof:

* Removing exactly 353 bytes at raw offsets 64,896 and 130,145 of
  `Formats/Latest` (unique solution found by exhaustive splice search)
  makes the deflate stream inflate to exactly the gzip trailer's ISIZE
  (496,597) with matching CRC32 (0x26852216). Same offsets/length fix the
  independently-compressed copy of the SAME schema in
  `vendor/phi-ag-rvt/.../racbasicsamplefamily-2026.rfa` (its trailer also
  reads CRC 0x26852216 / ISIZE 496,597).
* The model (`PAGE_DATA=64896`, `PAGE_TRAILER=353`) then validates every
  stream in every file: Global/Latest, Global/ContentDocuments (109 frames
  in dach), the four streams that previously would not inflate at all
  (dach ContentDocuments/ElemTable, racadv ContentDocuments, rme ElemTable),
  and 196/196 sampled Partitions members across the 129 MB dach Partitions/84.
* The 353-byte block is physically contiguous inside the CFB stream data
  (checked file offsets), so it is Revit's own paged writer, not an OLE
  artifact.

## 2. gzip trailers are VALID (KNOWLEDGE.md is wrong on this point)

After de-framing, every gzip member ends with a **standard, valid 8-byte
trailer** (CRC32 LE + ISIZE LE). The "corrupt/absent trailer" and the
"~270-712 bytes of undecoded trailing data" in KNOWLEDGE.md are artifacts of
inflating framed data. What follows the gzip trailer is only zero padding +
the final (partial-page) trailer block (~353 x lastPageLen/65249 bytes, min
~37-91).

## 3. Consequence: the existing `extracted/*.gz/*.bin` corpus is corrupt

`tools/scan_gzip.py` raw-inflates the framed stream. zlib silently
mis-decodes past the first frame boundary (LZ garbage), or raises. In
particular **`Formats/Latest.gz/000.bin` (the schema) is wrong from byte
138,858 onward**: the true schema is **496,597 bytes** (sha256
`6459a9a93ebde32c26e4190de2756bf7a4592e63a0d142feca43c392ecdf8ac2`), not
498,766. Everything the schema/class-ordinal work derived beyond offset
138,858 (and any class ordinal from that region) needs re-deriving from the
de-framed inflate. Same for Global/Latest (true 1,500,644 bytes in racbasic,
not 1,506,910), ElemTable, ContentDocuments, History-of-large-files, and any
Partitions member whose compressed extent crosses a frame (90 of 400 sampled
members in racbasic Partitions/15).

Fix recipe (also in `tools_cross/compare.py`):

```python
def deframe(raw):
    out = bytearray(); pos = 0; off = 64896
    while off < len(raw):
        out += raw[pos:off]; pos = off + 353; off += 65249
    out += raw[pos:]
    return bytes(out)
# then find 1f 8b 08 in the de-framed bytes, skip the 10-byte header,
# zlib.decompressobj(-15), and CHECK crc32/isize from the 8 bytes after.
```

Open: what the 353-byte per-page block encodes (deterministic per page
content, first byte 0x00, size ~0.54% of page for partial pages — [hypothesis]
compressed per-page integrity/ECC data). Not needed for reading; will be
needed to write native .rvt.
