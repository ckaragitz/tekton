# inbox — schema-full (wave 2) notes for the orchestrator

Deliverable summary: `Formats/Latest` is fully decoded (`src/rvt/schema.py`,
`docs/streams/01-schema.md`, `extracted/_schema/{schema.json,type_ids.json,
mep_classes.txt}`). 4,690 classes, 12,558 fields, parses to EOF with 0
gaps / 0 unresolved refs; id model = definition order + 0x0c, 16/16
anchors, no ±1 drift.

Out-of-scope findings worth merging into KNOWLEDGE.md:

1. **The "±1 drift" is not real.** ContentMarker/ContentRec: the ordinals
   0x3a2/0x3a3 observed in Global/Partitions are correct; the wave-1
   *names* were one slot off. True: 0x3a2 = `ContentKey`, 0x3a3 =
   `ContentMarker`, 0x3a4 = `ContentRec`. The 28-byte separator
   `a3 03, -1, a2 03, u32 counter, GUID` = ContentMarker(0x3a3) then
   ContentKey(0x3a2) — ContentKey should carry the counter+GUID; check
   its field list in schema.json. Likewise Contents item word 0x53e =
   `DocumentStorageIndexImpl` (0x53d is the interface class).
2. **AString = 0x1f = `AStringWrapper`** — the ZDI registered-class name
   "AString" is the runtime type; the schema class is the wrapper. Any
   partition class word 0x1f is a wrapped AString object.
3. **rvt-rs's tag column = our id + 1** (their "tag" is really the
   inline-defined base class's id). 60/60. Useful for cross-release id
   estimation: their 11-release CSV gives base-class ids per year, so a
   2016–2025 id map can be bootstrapped without those schema blobs.
4. `KNOWLEDGE.md` "The schema (Formats/Latest)" section still says
   "498,766 bytes inflated / sha256 8f551c2218c6e015" — stale (paging
   artefact). True: 496,597 bytes, sha256 6459a9a9…. Also "~27,900
   strings": there are 4,690 class names + 12,558 field names.
5. **Element base = id 0x25, 895 descendants** — element-decoder agents
   can map every partition class word ≥ 0x0c straight through
   `extracted/_schema/type_ids.json`; class words < 0x0c are impossible
   as object leads. `ElementHeader` (0x5e5) has fields worth reading for
   the seq-101 record body.
6. Top-level class names are stored in strict ASCII sort order — writing
   a schema for a synthetic file must preserve that ordering (and the
   inline-definition placement) or ids shift.
7. Kind codebook correction vs schema-a/rvt-rs: **0x02 = char (byte),
   0x03 = short** (ground truth from `std::pair< short, X >` /
   `std::pair< X, char >` synthetic classes). schema-a's "0x03 =
   uint16" and rvt-rs's "0x02 = u16, 0x03 = deprecated i32" are wrong.

Suggested next tasks: (a) join `type_ids.json` into `partitions.py`
class-word histograms to name every element record; (b) diff against a
2025/2024 schema blob when one is available to build a real tag-drift
table; (c) decode `ADocument`'s 1,509-GUID table (format-episode ids?).
