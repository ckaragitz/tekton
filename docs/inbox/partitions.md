# inbox: partitions — cross-cutting findings for the orchestrator

From agent `partitions`. Full detail in `docs/streams/05-partitions.md`;
code in `src/rvt/partitions.py`. Items are ordered by blast radius.

## 1 · CRITICAL, corpus-wide: streams are paged (64,896 + 353) — the carved corpus is partly corrupt

Every OLE stream is written as 64,896-byte (0xFD80) payload pages, each
full page followed by a 353-byte opaque page-trailer record; the last
partial page has no trailer. The "corrupt gzip trailer" and the
"~270–712 bytes of trailing data" in KNOWLEDGE.md are both artefacts of
this. Proof: after excising 353 bytes at raw offsets 64,896 + k·65,249,
every one of the 13,535 gzip members in the seven `Partitions/*` streams
validates against its stored CRC32/ISIZE, and `Formats/Latest` inflates to
exactly its stored ISIZE 496,597 bytes with CRC match (the current
`extracted/*/Formats__Latest.gz/000.bin` = 498,766 bytes is garbled from
byte ~64 K of the *compressed* stream onward — that is why late class names
looked like `HVACnTexScheduleEm_s`, `ablPatteeee`).

Impact: any inflated member that crosses a page boundary in
`extracted/*/*.gz/NNN.bin` decodes correctly up to the boundary and is
silently wrong after it. Affected for sure: `Formats/Latest` (schema, A2),
`Global/Latest`, `Global/ContentDocuments`, `Global/ElemTable` in some
files, and 15–25 % of partition blocks. `Global/PartitionTable`,
`DocumentIncrementTable`, `Contents`, `History` are below one page in most
files and unaffected.

Recommended action: add a de-paging step to the corpus tooling and
re-carve. Reference implementation (`rvt.partitions.depage`):

```python
PAGE_SIZE, PAGE_TRAILER = 64896, 353
def depage(raw):
    out, trailers, pos = bytearray(), [], 0
    while pos < len(raw):
        out += raw[pos:pos + PAGE_SIZE]
        if pos + PAGE_SIZE < len(raw):
            trailers.append(raw[pos + PAGE_SIZE:pos + PAGE_SIZE + PAGE_TRAILER])
        pos += PAGE_SIZE + PAGE_TRAILER
    return bytes(out), trailers
```

Then the gzip trailers are real: use CRC32/ISIZE to validate every
carve. Page-trailer content: byte 0 always 0x00, byte 1 a multiple of 0x10,
351 high-entropy bytes; undecoded (candidate: per-page signature/MAC). For
a future *writer* (Epic D) these must be reproduced, so someone should
own decoding them.

## 2 · Streams start with a u16 schema class ordinal

The first two bytes of an inflated `Global/*` payload (and of many nested
records) are a class ordinal into `Formats/Latest`. Confirmed 0x1c = 28 =
`ADocument` leads `Global/Latest`. Others (drift ±1 in my quick scan; A2
should confirm): 0x5c9 → `ElemTable` (leads `Global/ElemTable` with a u32
count next), 0x53c → `DocumentIncrementTable`, 0x538 → `DocumentHistory`
(`Global/History`), 0x53e → `DocumentStorageIndex[Impl]` (`Contents`),
0x0c80 → `PartitionTable`, 0x03a3/0x03a2 → `ContentRec`/`ContentMarker`
(`Global/ContentDocuments` and the Partitions container framing). Ordinals
appear to be assigned by first appearance of each class definition in the
schema starting at 12 (primitives below), including nested type-string
definitions — an exact enumeration is the A2 agent's job now that the blob
decompresses cleanly.

## 3 · `Global/DocumentIncrementTable` first u32 = highest `Partitions/<N>` + 1

`3c 05 <u32 next> 02 00 00 00 …` with next = 16/14/15/13/22/86 for partition
ids 15/13/14/12/21/{84,85}. So `<N>` is the document-increment counter.
The record then holds a UTF-16 user name (`zhangg`, `sujuu`, `mrozp`,
`pe@cad…`) and, in racbasic, the value 824 which equals
`PartitionTable.id_b` — worth a look by whoever owns A3.

## 4 · `Global/PartitionTable` is the workset table, not a partition index

One entry (GUID, ids, kind, UTF-16 name "Workset1" / "Family : Title
Blocks : A0 metric" / "Project Standards" / "Architektur"). It never
mentions `<N>`. Layout in 05-partitions §2.

## 5 · Save-unit GUIDs link `Partitions`, `Global/Latest` and `Global/ContentDocuments`

Each incremental-save unit inside a partition is introduced by
`a3 03 ff ff ff ff a2 03 <u32> <GUID16>`. racbasic unit 1's GUID
`{34B22600-3ED6-44B3-B4F1-6596F4D52B43}` (bytes `00 26 b2 34 …`) occurs
2× in `Global/Latest` and 1× in `Global/ContentDocuments`, whose payload
starts with the same `a3 03 -1 a2 03 -1 <GUID>` record. So `ContentDocuments`
enumerates the same content/save records — the A7 agent can pivot on
this. `Global/History` did **not** contain these GUIDs.

## 6 · Element data model, for the A4/A5 agents

Partition records use a 40-bit-ish id space (max 1,098,851 in racbasic)
of which `Global/ElemTable` (8,401 × 40-byte records after a 6-byte
header `c9 05 <u32 count>`) is a subset (8,223/8,401 present among
partition record ids; partition ids ⊃ ElemTable ids). Each object is
serialized as three records with the same id, one per segment 101/102/103
(header / object / graphics-or-dummy). `Global/Latest`'s `ADocument`
should therefore reference partition record ids beyond the ElemTable set.

## 7 · Tooling note

`tools/scan_gzip.py`'s `index.json` misses ~8 % of gzip members (racbasic:
1068 carved vs 1156 real) because it resumes scanning after `consumed`
bytes and its raw-mode `consumed` is short when a member is corrupted by
a page trailer. After de-paging, anchoring on the framing (block header
`B` field + `21 0f <B>` trailer marker) or on validated CRC/ISIZE avoids
both problems.
