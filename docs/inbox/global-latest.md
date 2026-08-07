# Inbox — findings outside the `global-latest` slice

From agent `global-latest` (framing of `Global/Latest`). Not acted on; for
the orchestrator / the owning agents.

## For schema-a: the "corrupted" tail of `Formats/Latest` is very likely *compressed*, not corrupt

`Global/Latest` contains the Autodesk Forge units-schema JSON dictionary in
two encodings: (1) plain `u32 charcount + UTF-16LE` AStrings and (2) a
compressed form. In the compressed form:

- the u32 length prefix has its high bytes set to 0xff (e.g. `26 ff ff ff`
  = flag | 38 chars) — see rme `Global/Latest`+0x265644;
- inside, some UTF-16 code units keep the ASCII char in the low byte but
  set the **high byte to 0xff** (`22 ff`='"', `20 ff`=' ', `69 ff`='i');
  masking that byte reconstructs racbasic's plain JSON exactly;
- deeper in, literal runs appear at both even and odd byte offsets with
  dropped substrings — a byte-oriented LZ back-reference stream
  ("MincCentimeter…seterseter", "annotnn\"1").

The "identifiers with dropped characters, letter runs, mis-aligned framing"
you observe from `Formats/Latest`+0x21e61 to EOF ("GaalltegupheMMMMMMM",
"WildcartWorktholm…") is the same visual signature. Hypothesis: one
Autodesk text/string LZ codec used in both places. Cracking it once would
finish both the schema decode and the units dictionary. Candidate model:
LZSS-style byte codec whose control/flag bytes are what land in the odd
(high) byte positions of UTF-16 text.

## For elem-table (A4): record layout hint from an ElementId cross-check

Element id 99859 (`13 86 01 00 00 00 00 00`) occurs in `Global/ElemTable`
exactly twice, 24 bytes apart, both inside one ~40-byte record at
`Global/ElemTable`+0xce6e:

```
00ce6e: 13 86 01 00 00 00 00 00   id (u64)
        89 01 00 00               0x189 (393)
        1a 03 00 00               0x31a (794)  ← class-id-like
        09 03 00 00               0x309 (777)
        13 86 01 00 00 00 00 00   id again (u64)
        ff ff ff ff ff ff ff ff   -1 (u64)
        00 00 00 00
00ce96: 14 86 01 00 …             next record: id 99860
```
Records are 40 bytes apart (0xce6e, 0xce96, 0xcebe for 99859/99860/99861).
The value 0x189 (393) also appears as an int-map value in `Global/Latest`'s
GUID-keyed map (key 0x341 → 0x189/0xe0/…), so it may be a shared
level/workset/category index.

## For A9 (strings/GUID orientation)

- The `BasicFileInfo` document GUID (`e6a03f8e-9e4e-4cfc-ae41-c3c559e42d55`)
  does **not** occur in `Global/Latest` (searched LE/BE binary and UTF-16
  text). The 163 GUIDs there are keyed to vendor "Autodesk Revit".
- `Formats/Latest` has, right after the `ADocument` class record
  (offset 0x644), `e5 05 00 00` followed by what looks like a table of
  1,509 16-byte GUIDs (ends just before the `APIAppInfo` record at
  0x649d). Per-class type GUIDs? Not in my slice.
