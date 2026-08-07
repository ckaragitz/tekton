# 13 · Stream ENCODERS for the small structured streams

Agent: `stream-encoders`. Code: `src/rvt/stream_encoders.py` (decode/encode
pairs + `python -m rvt.stream_encoders` round-trip matrix),
`src/rvt/streams_edit.py` (mutation helpers + `save_impact`), tests
`tests/test_stream_encoders.py` (89 passing). Verified on all six Revit 2026
corpus files.

## TL;DR

The six small tables the writer must regenerate on every model edit —
`Global/ElemTable`, `Global/History`, `Global/DocumentIncrementTable`,
`Global/PartitionTable`, `Contents`, `BasicFileInfo` — now have byte-exact
encoders: for every stream in every sample,
`encode_<s>(decode_<s>(bytes)) == bytes` (36/36, see §4). Payload here means
the **inflated** bytes, before gzip and before page framing; the 8-byte
`Global/*` constant prefix is a separate, explicit step
(`global_prefix()` / `wrap_global_stream()`: Latest=5,
ContentDocuments/DocumentIncrementTable/History=1, ElemTable/PartitionTable=0).
`Contents` uses the 24-byte class-stream prologue instead (§2.5), and
`BasicFileInfo` is a raw, uncompressed stream (§2.6). Page framing + the
353-byte ECC trailer are delegated to `rvt.ecc.page_trailer()` (stubbed with
zeros in `frame_stream()` until that fleet delivers).

## 1. Model / API contract

```python
from rvt import stream_encoders as se, streams_edit as ed

model  = se.decode_elemtable(payload)      # plain dict, JSON-able
payload = se.encode_elemtable(model)       # byte-exact inverse
se.CODECS  # name -> (decode, encode, kind: 'payload'|'contents'|'raw')

logical = se.wrap_global_stream("ElemTable", payload, level=3)  # prefix + gzip
raw, ecc_valid = se.frame_stream(logical)  # ecc_valid False until rvt.ecc exists
```

Decoders wrap the wave-1 decoders (`elemtable`, `content`, `partitions`,
`meta`) and add exactly the bytes those dropped (all constant-zero in the
corpus, but required for a lossless inverse):

| stream | field ADDED to the model | why | evidence |
|---|---|---|---|
| History | `pad10` (bytes +0x04..0x0d), `pad_u32` (+0x12) | `parse_history` skips them | `00`×10 and `00000000` in 6/6 files |
| DocumentIncrementTable | `records2` (second serialized copy) | wave-1 kept only a `copy2_identical` flag | copy2 == copy1 in 6/6 |
| Contents | own decoder: `zero36`, `zero_a..e`, `one/one_b`, `tail` | `meta.parse_contents` folds them into `misc_zeros` | round-trip 6/6 |
| BasicFileInfo | `worksharing_text`, `is_single_user_cloud_model_text`, `mirror_text` | worksharing-enabled enum text unobserved | all six are "Not enabled"/"False" |
| ElemTable / PartitionTable | none — wave-1 decoders already lossless | | round-trip 6/6 |

No wave-1 source file was modified.

## 2. Per-stream byte layouts (the exact encoder specs)

All little-endian. `ustr` = u32 UTF-16 code-unit count + UTF-16LE.
GUID = 16-byte Windows mixed-endian (`uuid.UUID.bytes_le`).

### 2.1 `Global/ElemTable` (prefix u64 0)

| off | size | field | notes |
|---|---|---|---|
| 0 | 2 | u16 `0x05c9` | ElemTable class |
| 2 | 4 | u32 N | record count |
| 6 | 40·N | ElemRec[N] | sorted ascending by `m_id`; per record: u64 original_id, u32 creation_ep, u32 modified_ep, u32 user_modified_ep (0xFFFFFFFF never), u64 id, u64 owner_id (−1 none), u32 partition_id (0) |
| 6+40N | 4 | u32 graveyard count | 0 in 6/6 (GraveyardRec wire layout unobserved → encoder refuses non-zero) |
| +4 | 4 | u32 `0xFFFFFFFF` | marker |
| +8 | 2 | u16 `0x096a` | trailing class tag |
| +10 | 2 | u16 0 | pad |
| +12 | 8 | u64 last-id **watermark** | highest ElementId ever issued (§6) |
| +20 | 4 | u32 0 | end; payload = 6+40N+24 exactly |

### 2.2 `Global/History` (prefix u64 1)

| off | size | field |
|---|---|---|
| 0x00 | 2 | u16 `0x0538` |
| 0x02 | 2 | u16 version = 1 |
| 0x04 | 10 | `pad10` = zeros |
| 0x0e | 4 | u32 entry count |
| 0x12 | 4 | u32 `pad_u32` = 0 |
| 0x16 | 5×16 | header GUIDs: G, G, G, ZERO, G |
| 0x66 | 4 | u32 nver |
| 0x6a | 4·nver | u32[] ascending upgrade format versions (ends 2662 = 2026) |
| … | 4 | u32 nent (== +0x0e) |
| … | 17·nent | entries **newest first**: GUID(16) + u8 tag `0x28` |
| … | 4 | u32 0 (`trailing`) |

### 2.3 `Global/DocumentIncrementTable` (prefix u64 1)

`u16 0x053c | u32 N | Record[N] | u32 N | Record[N] (copy 2, byte-identical) | 8×00`.

Record: `u32 npairs | (i32 key, i32 value)[npairs] | ustr username | u32 0 |
u32 id_pair.a | u32 id_pair.b (= a+1) | u32 0 | u32 unix_timestamp | u32 sequence |
u32 elem_id_repeat | i32 counters[10] | i32 −1 | u32 counter_g | u8 flag`.

The −1 terminator makes a counter value of −1 unrepresentable (never occurs).

### 2.4 `Global/PartitionTable` (prefix u64 0)

`u16 0x0c80 | u32 version=1 | u32 count | entries`; entry =
`GUID(16) | u32 0 | u32 id_a | u32 id_b | i32 −1 | u32 kind (0 user, 1 Project
Standards, 2 title-block) | u8 flag=0 | ustr name | u32[5] = 1,1,0,1,0`. No
trailing bytes. (id_b == first DIT record's `id_pair.a` in 6/6 — see inbox.)

### 2.5 `Contents` (raw = 24-byte prologue + gzip; NO 8-byte prefix)

Prologue: `u32 0x05221962 | u32 0x1c | u32 1 | u32 0 | u32 0x05221962 | u32
class_ref` (183/213/424/178/264/430 per file — per-document, kept in the
model). Inflated payload (240 B, +4+2n with a username):

| field | notes |
|---|---|
| u16 `0x053e` | type tag |
| u32 has_username [+ ustr username] | racadv/rme "A", rstadv "Steven Campbell" |
| u32 0, u32 0 | `zero_a`, `zero_b` |
| ustr `"GLOBAL"` | partition name |
| 36×00 | `zero36` |
| u32 1 | `one` |
| GUID creation_guid | document creation GUID |
| u16 ws marker | 0xFFFF without username, 0 with |
| u32 0, u8 0 | `zero_c`, `zero_d` |
| ustr build | `20250227_1515(x64)` |
| hdr5 = u32,u32,u32,i32(−1),u32 | (7, a, b, −1, 3) — dach (7,76,1,−1,3) |
| u8 1, u16 0 | `one_b`, `zero_e` |
| i32 counters[9] + i32 −1 | = newest DIT record's 10 counters with index 7 removed |
| u32 counter_g | = newest DIT record's G |
| (i32 −1, u16) ×2 | (−1,1420) (−1,1426) constant |
| 28×00 | `tail` — pads to the fixed record length |

`encode_contents_stream(prologue, model)` = prologue + our gzip; the ~42
bytes of stale heap slack Autodesk leaves after the trailer are not
reproduced (irrelevant — the reader stops at the gzip trailer).

### 2.6 `BasicFileInfo` (raw, uncompressed)

Packed record: `u32 14 | u16 worksharing_state | ustr username | ustr
central_model_path | ustr format | ustr build | ustr last_save_path | u32
open_workset_default | u8 project_spark_file | ustr central_model_identity |
ustr locale | u8 all_local_changes_saved | u32 central_version_number | ustr
central_episode_guid | ustr unique_document_guid | ustr
unique_document_increments (string!) | ustr model_identity | u8
is_single_user_cloud_model | ustr author | ustr client_app_name`, then ASCII
`0d 0a` + UTF-16LE mirror text + ASCII `0d 0a`. The mirror is a fixed 19-line
`Key: Value` template (`basic_file_info_mirror_text()`), **regenerated from
the fields byte-exact for all six files** — so a writer changing
`last_save_path`, the increment count or the GUIDs gets a self-consistent
stream for free.

## 3. Worked example — racbasic ElemTable footer / History header

```
ElemTable payload[6+40*8401:]  00 00 00 00 ff ff ff ff 6a 09 00 00
                                c3 c4 10 00 00 00 00 00 00 00 00 00
  graveyard=0, marker=-1, class 0x96a, pad 0, watermark 0x10c4c3=1,098,947, 0
History payload[0x00:0x18]     38 05 01 00 |00*10| 50 03 00 00 |00 00 00 00| G...
  0x538, ver 1, pad10 zeros, count 0x350=848, pad_u32 0, then 5 GUID slots
```

## 4. Round-trip pass matrix (byte-exact, `python -m rvt.stream_encoders`)

| stream | racbasic | racadvanced | rmebasic | rstbasic | rstadvanced | dach |
|---|---|---|---|---|---|---|
| ElemTable (336,070 … 1,991,070 B) | PASS | PASS | PASS | PASS | PASS | PASS |
| History | PASS | PASS | PASS | PASS | PASS | PASS |
| DocumentIncrementTable | PASS | PASS | PASS | PASS | PASS | PASS |
| PartitionTable | PASS | PASS | PASS | PASS | PASS | PASS |
| Contents (payload + 24-B prologue) | PASS | PASS | PASS | PASS | PASS | PASS |
| BasicFileInfo (raw stream, regenerated mirror) | PASS | PASS | PASS | PASS | PASS | PASS |

**36/36 = 100 %.** Pytest: `89 passed` (36 payload round-trips + 6 mirror
regenerations + 6 prologue round-trips + 36 prefix/gzip checks +
mutation/coordinated-save tests). Also verified: the 8-byte prefix constants
match every extracted logical stream (36 checks) and
`wrap_global_stream()` output inflates strictly (gzip CRC) back to the input.

## 5. What changes on save — evidence for the writer's checklist

Cross-stream invariants that hold in **all six** files (asserted by
`probe`/tests) and therefore constrain any coordinated edit:

| invariant | racbasic | racadv | rme | rstbasic | rstadv | dach |
|---|---|---|---|---|---|---|
| History count == max(ElemRec.modified_ep)+1 | 848=847+1 | 617 | 796 | 1017 | 579 | 2740 |
| DIT newest `id_pair` == (count−1, count) | (847,848) | (616,617) | (795,796) | (1016,1017) | (578,579) | (2739,2740) |
| BFI increments == central_version_number == DIT records | 16 | 14 | 15 | 22 | 13 | 86 |
| BFI Unique Document GUID == History entry[0] | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| Contents counters == DIT newest counters − index 7; G equal | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| ElemTable ids ascending, watermark ≥ max id | +96 | +0 | +0 | +0 | +0 | +0 |

Per-save deltas observed between consecutive DIT records (160 record pairs
across the six files): counters[1..9] follow "previous + 1, index 7 only
when flag=1" in **160/160**; counters[0] usually +1 but stalls in a run of
early dach saves; `counter_g` +1 in 160/160; `sequence` +1; only the newest
record carries a non-zero `elem_id_repeat` (== its `(-1, X)` pair value; on
flag=1 saves X ≈ the element record count, e.g. racbasic 85,814 = seq-102
records); older records show `elem_id_repeat = 0` and gain extra
`(key, count)` pairs — the final pair is `(own sequence, 0)` in only 88/160,
so that key's meaning is `[hypothesis / open]`.

Hence when a save adds **N new elements** (`streams_edit.save_impact(N)`):

MUST change — `ElemTable` (+N 40-B records, count, watermark),
`History` (+1 episode prepended, count+1), `DocumentIncrementTable`
(+1 record in both copies; previous newest normalised), `Contents` (counter
mirror + G), `BasicFileInfo` (increment count/version + episode GUIDs +
regenerated mirror), plus out-of-slice `Partitions/<N>` (the objects; its
header count) and `Global/Latest`.

CONSTANT — `Formats/Latest` (per-release schema), `Global/PartitionTable`
(worksets), `Global/ContentDocuments` (loaded content), `ProjectInformation`,
`TransmissionData`, `RevitPreview4.0`, all 8-byte prefixes, and the
`Contents` prologue/`class_ref`/creation GUID/build.

`streams_edit.record_save(models, new_element_ids=…)` applies the whole set
in one call and is exercised by the coordinated-save test (racbasic,
rstadv): allocate episode E = old History count → tag new ElemRecs with E →
DIT record with `id_pair=(E, E+1)`, counters+1, G+1, flag 1 → Contents
mirror → BFI fields; all six invariants above still hold afterwards.

## 6. ElementId allocation rule

| file | records | max id | watermark | Δ |
|---|---|---|---|---|
| racbasic | 8,401 | 1,098,851 | 1,098,947 | +96 |
| racadv | 17,231 | 438,567 | 438,567 | 0 |
| rme | 28,132 | 888,013 | 888,013 | 0 |
| rstbasic | 13,936 | 1,472,524 | 1,472,524 | 0 |
| rstadv | 13,855 | 271,237 | 271,237 | 0 |
| dach | 49,776 | 4,294,190 | 4,294,190 | 0 |

The footer u64 is a **monotonic highest-ever-issued watermark** (racbasic:
96 ids issued to elements deleted before the save). Rule adopted:
`next_element_id = watermark + 1`, and `elemtable_add_element` raises the
watermark to the inserted id. Confidence: allocation direction verified;
the off-by-one convention (is the stored value "last issued" or "next
free"?) is `[hypothesis]` — the racbasic Δ=+96 strictly proves only "≥ max
issued". Recommended acceptance probe once ECC lands: allocate at
watermark+1 vs watermark+2 and let the Viewer arbitrate.

## 7. Confidence

| claim | confidence |
|---|---|
| six layouts + byte-exact encoders (36/36) | verified |
| 8-byte prefix constants per stream name | verified (6/6 files) |
| coordinated-save invariants (§5 table) | verified (6/6 files) |
| DIT counter/G/sequence progression on save | verified 160/160 (idx 0: usually) |
| DIT older-record extra pair key = own sequence | weak (88/160) — hypothesis |
| next id = watermark + 1 | strong (direction verified, ±1 open) |
| GraveyardRec / worksharing-enabled BFI wire forms | unobserved (encoders refuse / need text override) |

## 8. Unknowns

1. `GraveyardRec` array wire layout (count 0 in every sample) — encoder
   raises rather than guess.
2. Semantics of the 10 DIT counters, `hdr5`, the extra `(key,count)` pairs,
   and the flag=0 "small −1 value" saves.
3. BFI mirror line text for `worksharing_state != 0` (all corpus files are
   "Not enabled"); model carries `worksharing_text` for that case.
4. Whether Revit tolerates a `Contents` stream without the trailing slack
   (it should — the reader stops at the gzip trailer; unverified until ECC).
5. `History` header GUID G (slots 0,1,2,4) meaning; kept verbatim.
