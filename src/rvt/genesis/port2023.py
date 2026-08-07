"""genesis/port2023.py -- the Revit-2023 PORTABILITY LAYER over the 2026
constructors (genesis-2023 campaign, constructor side).

The 2026 constructors (``rvt.genesis.types`` / ``settings`` / ``catalog`` /
``skeleton`` / ``residue_*``) build schema-directed objects against the 2026
archive class map.  This module WRAPS them -- it never edits them (and never
edits ``port2025`` / ``port2024``; where a Revit-2023 layout EQUALS a newer
release's layout it DELEGATES to that layer's machinery, recorded per
delegation):

    adapt(class_name, obj_2026)  ->  obj_2023
    adapt_record(record_2026)    ->  PortedRecord (2023 class ids, 2023-shaped
                                     seq-101/102/103 bodies)

2023 IS THE FIRST 32-BIT-ID RELEASE THE TOOLCHAIN TOUCHES.  Autodesk widened
element ids to 64 bits in Revit 2024; in 2023 and older:

* ``Identifier`` v1 declares ``m_id`` kind 0x04 (i32) -- the 2024+ schema
  declares ``m_id64`` kind 0x0b (i64).  THE FILE'S OWN SCHEMA IS THE
  AUTHORITY on the width (:func:`id_width_from_schema`); the 2026-built
  codec shortcuts (``Reader.element_id`` / ``Writer.element_id``) bake i64
  and must be swapped to i32 for every 2023 decode/encode
  (:func:`id32` -- process-local, restored on exit, re-entrant).
* Partition record framing: headers are ``<iI`` (seq-101, 8 bytes) /
  ``<iII`` (seq-102/103, 12 bytes) -- 4-byte elem id vs 2024's 8 -- with the
  same u32 trailing psize repeat, the same adler32(class||body) stamp
  formula (63,648/63,648 records of the 2023 rst sample), and a 4-byte
  ``-1`` save-unit sentinel (:func:`iter_records_2023`).  With ONLY these
  two width changes the whole read stack runs at parity: the 2023 rst
  sample walks completely (95,631 records, 0 partial segments, 0 sentinel /
  trailer failures) and seq-102 decodes 99.98 % clean (31,817/31,824; the
  7 dirty are the SAME RebarShape/DataStorage Extensible-Storage gaps every
  release shows).
* ``Global/ElemTable``: 28-byte rows (7 x u32) in the 2023 field order
  ``m_id, m_history(orig, ce, me, ue), m_partitionId, m_OwningElementId``
  -- 2024+ rows are 40 bytes, history-first -- plus the same footer
  apparatus with a 4-byte ``IdentifierSource.m_last``
  (:func:`parse_elemtable_2023`; schema-directed decode of the whole
  stream verified against the fixed-width parse).
* Container / pages / gzip / block framing / schema grammar are UNCHANGED:
  CFB v4 4096-byte sectors, 100 % gzip CRC, 0 walker errors with the
  by-name framing ordinals, ``rvt.schema.parse`` reads the 2023
  ``Formats/Latest`` to EOF (462,765 B, 4,418 classes, 0 unresolved).

CONFIRMED PORTABILITY VERDICT (``--verify`` re-derives it; frozen copy:
``experiments/genesis2023/miners/portability-2023.json``).  Method =
port2025's section-6 method re-run for 2023 (own-field signatures by type
NAME, flattened parent-first chain layout, per-class versions, 2026 pin vs
the 2023 pin), each row four-way annotated against BOTH the 2026->2025 and
2026->2024 tables -- nothing is assumed monotonic.

THE HEADLINE RESULT over the same 403-class universe: 280 IDENTICAL /
104 LAYOUT-DELTA / 16 MISSING-2023 / 3 VERSION-ONLY (DataStorage v3->0,
ElementHeader v25->24, FabricationSettings v6->4 -- free: records carry no
version).  The known movers, each established INDEPENDENTLY for 2023:

* ``DBView`` v99->98: 2026-only ``m_viewPositionId`` dropped (same as
  2024/2025) + shared-field ORDER differs + ``m_pDetailDrawOrderMgr``'s
  pointee re-shaped (see DrawOrderMgr below).  Hits every constructed view
  class; all handled by the generic target-chain walk.
* ``DBViewDrafting`` v12->10: drops ``m_sheetCollectionId`` +
  ``m_sheetTitleBlockId`` and -- unlike 2024 -- has NO
  ``m_scheduleInstanceIds`` (that field is 2024-only).  2023 != 2024 here.
* ``Viewport`` v13->10: 2026-only ``m_viewPosition`` / ``m_viewAnchor`` /
  ``m_oPlaceholderBoxOutline`` all dropped.  NOTE: 2024 is ALSO v10 yet
  KEEPS ``m_oPlaceholderBoxOutline`` -- same class version, different
  layout across releases; version numbers cannot be trusted, only the
  file's own schema.
* ``BrowserOrganizationTracking`` v6->5: the same three-ElementId split as
  2024/2025 (port2025's tree-code hooks delegate).
* ``GeomTable``: the same two 2023-only leading ints as 2024/2025; corpus
  default (-1, -1) RE-MINED from the 2023 rst sample.
* Wire/conductor: the 6 conductor-catalog classes (+ 2 data bases) are
  MISSING-2023 exactly as in 2024/2025; ``RbsWireType`` v5->2
  (id -> size-label string); ``RbsWireSettingsElem`` v13->12 carries the
  three sizing doubles (2023-mined values EQUAL 2024/2025's) **with
  shared-field order differing from 2026's** (walk handles);
  ``RbsWireSizesElem`` v8->3 drops ``m_bInitialized``.

2023-NEW DELTAS (not in the 2024 or 2025 tables; established here):

* **THE REORDER WAVE**: ~45 classes (Material, WallType, Floor, CurveElem,
  RoomElem, ColorFillSchema, DimensionStyle, GStyle, GFace, AssemblyType,
  FamilyInstance, ...) have the SAME field set as 2026 but a DIFFERENT
  serialization ORDER -- most without a version bump (Material v13 == v13).
  2024 re-ordered wholesale; the generic target-chain walk (which emits in
  the TARGET schema's order) absorbs every one with no hook.
* ``ParamDef`` v6->5 (base of all 12 ParamDef* storage classes):
  2026 ``m_groupTypeId`` (ForgeTypeId, 'autodesk.parameter.group:*') is
  2023 ``m_groupElemId`` (ElementId -- the classic BuiltInParameterGroup
  constant).  Hooked via :data:`PARAM_GROUP_ELEM_2023`, a deterministic
  18-entry map mined by joining the SAME parameters (by caption) across
  the 2023/2026 rst+rme samples: 460 joined params, zero conflicts.
  Unmined group tokens map to -1 -- the corpus's own no-group value
  (43 corpus params carry -1).
* ``ElectricalLoadClassification`` v7->5: 2026 ``m_signitureType``
  (int enum: 1 motor / 2 other / 3 spare / else 0 -- house_standard
  F-HS-4) becomes two 2023 bools ``m_motor`` / ``m_spare``.  Mined from
  the 2023 rme sample: 'Motor' carries (True, False), 'Spare'
  (False, True), all eight others (False, False).  Hooked both ways from
  the source's own ``m_signitureType``.
* ``StructSettingsElem`` v25->22: EIGHT 2026-only fields dropped (the
  loads-display-scaling block) -- 2024/2025 dropped one.  Free (walk).
* ``GRep`` v6->5 (base of every ``GElement`` seq-103 rep): 2026-only
  ``m_elementId`` (raw i64, kind 0x0b -- itself a 64-bit-era addition)
  dropped.  Free (walk).
* ``DrawOrderMgrBase`` MISSING-2023: its two fields (``m_pADoc`` /
  ``m_pDBView`` weakrefs) live directly on 2023's ``DrawOrderMgr``
  (chain re-shape).  The skeleton's ``m_pDetailDrawOrderMgr`` pointer
  carries the same three fields by name; no hook (2023 corpus: 45/45 rst
  views carry the pointer SET, matching the skeleton's construction).
* ``ElemTable`` v10->9 drops ``m_bLastElementIdOverride`` (2024 HAS it);
  ``ElementParents`` v13->12 drops ``m_computedParametersParents``;
  ``EnergyDataSettings`` v15->14 drops ``m_useCurrentViewOnly``;
  ``ConstructionSetBase`` v4->3 drops ``m_strUndergroundWall``;
  ``ViewportAttributes`` v4->4 (!) drops ``m_preserveTitlePosition``;
  ``IckyExcludedCategoriesSetPtrWrapper`` v18->17 GAINS
  ``m_bMassShellExcluded`` (2023-only; corpus value False 19/19 = the
  schema blank -- no hook).  ``RbsDuctSettingsElem`` v15->13 additionally
  drops 2026-only ``m_enableNetworkBasedCalculations`` on top of the
  2024-style kinematic-viscosity rename (port2024's hook delegates).
  ``FamilyBase`` v48->47 (name-collision harvest row, not constructed):
  drops three 2026 fields, GAINS 2023-only ``m_bAdHoc``.
  ``IndependentTag`` v22->20 (not constructed): drops three head-position
  fields, gains ``m_taggedEntitiesCell`` + ``m_leaderEndCondition``.

MISSING-2023 (16 = the 13 of 2024 + three more):
:data:`MISSING_2023_CONSTRUCTED` lists the constructed ones -- the
conductor catalog (2026-only), the five 2025-era classes 2024 also lacks,
PLUS ``FabricationServiceSettings`` and ``SSEPointVisibilitySettings``
(both constructed by ``settings``; no 2023 twin, no 2023 specimen -- their
constructors emit nothing on a 2023 build).  ``DrawOrderMgrBase`` is
missing but never constructed (chain row; see above).

MINED 2023 corpus constants: every port2024/port2025 mined value RE-MINED
INDEPENDENTLY from the quarantined ``samples/2023`` corpus (specimens
cited per constant below); all equal their 2024/2025 twins.  The 2023-new
mining: the ParamDef group map and the load-classification bool split.
``--mine`` freezes ``builtin_category_enum_2023.json``,
``builtin_style_profile_2023.json``, ``pen_table_2023.json``,
``palette_invariants_2023.json`` AND ``defaults_2023.json`` (the value-
constant census with per-specimen provenance) under
``experiments/genesis2023/miners/``.

DELEGATIONS (recorded; each verified safe for 2023):

* from **rvt.versions** (the reduce stream's mid-stream landings):
  ``schema_2023.load`` for the pinned schema (this module RE-ASSERTS its
  own measured pin on every load, so the two streams cross-check), and
  ``records32`` for the ENTIRE 32-bit read/write context --
  :func:`id32` / :func:`reading_2023` / :func:`iter_records_2023` are now
  thin delegates over ``records32.ids32`` / ``reading32`` /
  ``iter_records32`` (which patch the whole stack, a superset of this
  module's original context).  ONE reference exception:
  :func:`parse_elemtable_2023` (see its docstring -- the schema-declared
  row order vs records32's, byte-indistinguishable on the corpus, fix
  proposed in the stream record).
* from **port2025**: ``PortabilityError`` base; ``_AdaptContext``; the
  dec-parameterised blank machinery (release-agnostic); the pure value
  hooks ``_hook_sort_param_id`` / ``_hook_numbering_min_digits`` /
  ``_hook_numbering_matching`` / ``_browser_tracking_tree``; the numbering
  hooks ``_hook_numbering_partition_creator`` / ``_hook_numbering_type_guid``
  (they build 2025-blank ``ParameterBasedPartitionDescriptionCreator`` /
  ``NumberingSchemaType`` bodies: both classes -- and the nested
  ``ControlledConstDocAccess`` -- are LAYOUT-IDENTICAL 2023==2025,
  asserted by ``tests/test_port2023.py``; the 2023-mined GUID table equals
  the 2025 one, so 2025 blanks ARE 2023 blanks).
* from **port2024**: the seven ``AutoCamSettingsElem`` rename hooks
  (2023's v5 layout is FIELD-FOR-FIELD IDENTICAL to 2024's v5, asserted in
  tests); ``_hook_duct_viscosity`` (same kinematic rename, bit-exact on
  the shared corpus value); ``_hook_mep_network_map`` (same
  segment-map->element-map re-type; empty-only).
* The adapt WALK itself is bound to the 2023 pin here (port2025/port2024's
  walks are hardwired to their singletons; the shape is the verbatim
  method).

Round-trip gate: every adapted object must encode -> decode -> re-encode
BYTE-EXACT under the 2023 schema *inside the id32 context*
(:func:`verify_roundtrip_2023`).  Specimen gate (byte-level, where the
2026 method verified byte-level): :func:`verify_specimen_byte_level`
proves OUR adapted ``AutoCamSettingsElem`` and empty ``MEPNetworkTracker``
BYTE-EXACT against the 2023 rst specimens (102842 / 1468014 -- the same
element ids every release's sample carries), the pen-table layout
byte-exact with the specimen's own vectors re-fed, and specimen
decode -> re-encode round-trips for every ported constructor class.

Territory: this module, tests/test_port2023.py,
experiments/genesis2023/miners/**, docs/inbox/genesis-2023-port.md.
Python: ALWAYS ``.venv/bin/python`` from the repo root.

CLI::

    .venv/bin/python -m rvt.genesis.port2023 --verify    # portability table
    .venv/bin/python -m rvt.genesis.port2023 --mine      # 2023 corpus miners
    .venv/bin/python -m rvt.genesis.port2023 --selftest  # adapt+roundtrip+specimen
"""
from __future__ import annotations

import ast
import collections
import contextlib
import copy
import dataclasses
import json
import os
import struct
import sys
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Set, Tuple

from .types import INVALID, NULL_GUID
from .port2025 import (
    PortabilityError,
    _AdaptContext,
    _blank_class25 as _blank_class_for,      # dec-parameterised, release-agnostic
    _blank_field25 as _blank_field_for,
    _blank_scalar25 as _blank_scalar_for,
    _browser_tracking_tree,
    _hook_numbering_matching,
    _hook_numbering_min_digits,
    _hook_numbering_partition_creator,       # 2025 blanks; layout-identical in 2023
    _hook_numbering_type_guid,               # (asserted in tests/test_port2023.py)
    _hook_sort_param_id,
)
from .port2024 import (
    AUTOCAM_RENAMES_2024,                    # 2023 v5 == 2024 v5 field-for-field
    _autocam_hook,
    _hook_duct_viscosity,
    _hook_mep_network_map,
)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
GENESIS_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(ROOT, "experiments", "genesis2023", "miners")
PORTABILITY_JSON = os.path.join(OUT_DIR, "portability-2023.json")
ENUM_2023_JSON = os.path.join(OUT_DIR, "builtin_category_enum_2023.json")
PROFILE_2023_JSON = os.path.join(OUT_DIR, "builtin_style_profile_2023.json")
PEN_2023_JSON = os.path.join(OUT_DIR, "pen_table_2023.json")
PALETTE_2023_JSON = os.path.join(OUT_DIR, "palette_invariants_2023.json")
DEFAULTS_2023_JSON = os.path.join(OUT_DIR, "defaults_2023.json")

#: the quarantined 2023 samples (DEV-ONLY field oracles; never shipped)
SAMPLES_2023 = os.path.join(ROOT, "samples", "2023")
RST_2023 = os.path.join(SAMPLES_2023, "rstbasicsampleproject.rvt")

#: the portability layers are NOT constructors -- excluded from the harvest
_PORT_LAYERS = ("port2025.py", "port2024.py", "port2023.py")


class Missing2023(PortabilityError):
    """The class does not exist in the Revit-2023 archive class map."""


# ---------------------------------------------------------------------------
# THE 2023 PIN (measured this stream, samples/2023/SOURCES.md)
# ---------------------------------------------------------------------------
SCHEMA_SIZE_2023 = 462_765
SCHEMA_SHA256_2023 = "bce7907bbb970c0e4fa6bfea3f0683898a494f1a75b44b543043bc98babfaa95"
CLASS_COUNT_2023 = 4_418
SAMPLE_BUILD_2023 = "20220401_1515(x64)"

#: the six partition-framing ordinals, resolved by name from the 2023 schema
#: (rvt.versions.ordinals_from_schema; cross-checked at _S23() load)
FRAMING_2023 = {"BLOCK_TAG": 0x0E4E, "TRAILER_TAG": 0x0E47, "FOOTER_TAG": 0x0E61,
                "CONTAINER_CLASS": 0x0365, "UNIT_INNER_CLASS": 0x0364,
                "PT_CLASS": 0x0BC0}

#: element-id byte width: 4 in 2023 (Identifier v1 m_id kind 0x04), 8 in 2024+
ID_WIDTH_2023 = 4


def id_width_from_schema(schema) -> int:
    """The element-id byte width THE FILE'S OWN SCHEMA declares: 4 when
    ``Identifier`` (v1) carries ``m_id`` kind 0x04 (i32, releases <= 2023),
    8 when it carries ``m_id64`` kind 0x0b (i64, 2024+)."""
    c = schema.by_name.get("Identifier")
    if c is None or not c.fields:
        raise PortabilityError("schema has no Identifier class -- not a Revit "
                               "Formats/Latest?")
    kind = c.fields[0].kind
    if kind == 0x04:
        return 4
    if kind == 0x0B:
        return 8
    raise PortabilityError(f"Identifier.m_id kind {kind:#x} is neither i32 nor i64")


# ---------------------------------------------------------------------------
# schema / codec singletons (2026 = the genesis default; 2023 = the pin)
# ---------------------------------------------------------------------------
_STATE: Dict[str, Any] = {}


def _S26():
    """(decoder, encoder, schema) for the canonical 2026 map."""
    if "s26" not in _STATE:
        from .types import _S
        _STATE["s26"] = _S()
    return _STATE["s26"]


def _load_schema_2023(source: Optional[str] = None):
    """Parse + PIN-VERIFY the 2023 ``Formats/Latest``.  Loading delegates to
    ``rvt.versions.schema_2023`` (the reduce stream's release handle, landed
    mid-stream -- it verifies against ``KNOWN_RELEASES[2023]``); this module
    then RE-ASSERTS its own independently measured pin (size / sha256 /
    class count / framing ordinals / id width), so the two streams'
    measurements cross-check each other on every load."""
    from .. import versions
    from ..versions import schema_2023
    s = schema_2023.load(source)
    st = s.stats()
    probs = []
    if st["stream_size"] != SCHEMA_SIZE_2023:
        probs.append(f"size {st['stream_size']} != {SCHEMA_SIZE_2023}")
    if st["sha256"] != SCHEMA_SHA256_2023:
        probs.append(f"sha256 {st['sha256'][:16]}.. != {SCHEMA_SHA256_2023[:16]}..")
    if st["class_count"] != CLASS_COUNT_2023:
        probs.append(f"class_count {st['class_count']} != {CLASS_COUNT_2023}")
    if st["unresolved_refs"]:
        probs.append(f"{st['unresolved_refs']} unresolved refs")
    if probs:
        raise PortabilityError("not the pinned Revit-2023 schema: " + "; ".join(probs))
    fr = versions.ordinals_from_schema(s)
    if fr != FRAMING_2023:
        raise PortabilityError(f"2023 framing ordinals drifted: {fr} != {FRAMING_2023}")
    if id_width_from_schema(s) != ID_WIDTH_2023:
        raise PortabilityError("2023 schema does not declare 32-bit Identifier")
    return s


def _S23():
    """(decoder, encoder, schema) for the pinned Revit-2023 map.  NOTE: the
    codec pair still needs :func:`id32` in force for any actual
    decode/encode -- the wrappers below enter it themselves."""
    if "s23" not in _STATE:
        from ..encode import ObjectEncoder
        from ..objects import ObjectDecoder
        dec = ObjectDecoder(_load_schema_2023())
        _STATE["s23"] = (dec, ObjectEncoder(decoder=dec), dec.schema)
    return _STATE["s23"]


def class_id_2023(name: str) -> int:
    """u16 Revit-2023 archive class id of ``name`` (raises Missing2023)."""
    _dec, _enc, schema = _S23()
    cd = schema.by_name.get(name)
    if cd is None:
        raise Missing2023(f"class {name!r} is not in the Revit-2023 archive class map")
    return cd.type_id


def exists_2023(name: str) -> bool:
    _dec, _enc, schema = _S23()
    return name in schema.by_name


def blank_object_2023(class_name: str) -> dict:
    """A complete, 2023-encoder-ready object dict for ``class_name`` (the
    2023 twin of ``types.blank_object`` -- port2025's dec-parameterised
    blank machinery walked with the 2023 decoder)."""
    dec, _enc, schema = _S23()
    cd = schema.by_name.get(class_name)
    if cd is None:
        raise Missing2023(f"class {class_name!r} is not in the Revit-2023 archive class map")
    return _blank_class_for(dec, cd.type_id, 0)


# ---------------------------------------------------------------------------
# THE 32-BIT-ID CONTEXT + the 2023 read stack -- DELEGATED to the
# genesis-2023-reduce stream's ``rvt.versions.records32`` (the generalized,
# stack-wide patch set that landed mid-stream; this module's original
# narrower context is retired in its favour, recorded in
# docs/inbox/genesis-2023-port.md).  ONE exception is kept as a reference
# implementation: :func:`parse_elemtable_2023` reads the ElemTable row in
# the SCHEMA-DECLARED order (id first) where records32's parser reads
# (original_id first) -- byte-indistinguishable on the whole corpus
# (id == original_id in 49,845/49,845 rows across the three basics; the
# elemtable test proves both against the schema-directed decode) but the
# schema order is the authority; the one-line records32 correction is
# proposed in the stream record.
# ---------------------------------------------------------------------------
@contextlib.contextmanager
def id32() -> Iterator[None]:
    """The 32-bit element-id era (Reader/Writer widths, record framing,
    ElemTable codecs, stack-wide) -- ``rvt.versions.records32.ids32``,
    kept under this module's historical name.  Re-entrant by LIFO restore.
    EVERY 2023 decode/encode must run inside this context -- the module's
    own wrappers do."""
    from ..versions import records32
    with records32.ids32():
        yield


def iter_records_2023(seg: bytes, seq: int = 102):
    """The 2023 partition record framing (4-byte elem ids) --
    ``rvt.versions.records32.iter_records32``, delegated."""
    from ..versions import records32
    return records32.iter_records32(seg, seq)


def parse_elemtable_2023(payload: bytes, project: str = "?"):
    """REFERENCE implementation of the 2023 ``Global/ElemTable`` parse, kept
    alongside the delegated runtime path (``records32.parse_elemtable32``)
    because the two disagree on ONE latent point: THIS parser reads the row
    in the SCHEMA-DECLARED field order -- ``m_id`` FIRST, then
    ``m_history(orig, ce, me, ue)``, ``m_partitionId``, ``m_OwningElementId``
    (exactly how the schema-directed object decoder walks the stream, and
    how the 2024 wire provably follows ITS schema order) -- while records32
    reads (original_id, id, ...).  Byte-indistinguishable on the whole 2023
    corpus (id == original_id in 49,845/49,845 rows across the three
    basics); the records32 one-line correction is proposed in
    docs/inbox/genesis-2023-port.md.  Footer: graveyard count, the
    ``IdentifierSource`` pointer (pid -1 + class word), the
    ``m_bExpandAllOnLoad`` byte, then the QUEUED pointee body (4-byte
    ``m_last`` watermark) and the 4-byte stream tail every release carries.
    Returns the same ``rvt.elemtable.ElemTable`` shape the 2026 parser
    returns (owner -1 normalised to the u64 INVALID_ID sentinel).
    [VERIFIED against the schema-directed id32 decode of the whole stream:
    13,821/13,821 rst rows identical, m_last 1,472,302.]"""
    from .. import elemtable as ET
    if len(payload) < 6:
        raise ValueError("payload too short")
    class_tag, count = struct.unpack_from("<HI", payload, 0)
    tbl = ET.ElemTable(project=project, class_tag=class_tag, count=count,
                       payload_len=len(payload))
    off = 6
    need = 6 + count * 28
    if len(payload) < need:
        raise ValueError(f"payload {len(payload)} < needed {need} for {count} rows")
    unpack = struct.Struct("<7I").unpack_from
    recs = tbl.records
    for i in range(count):
        eid, o, ce, me, ue, pid, own = unpack(payload, off)
        if own == 0xFFFFFFFF:
            own = ET.INVALID_ID
        recs.append(ET.ElemRec(i, o, ce, me, ue, eid, own, pid))
        off += 28
    tail = payload[off:]
    if len(tail) >= 19:
        gcnt, marker, tcls = struct.unpack_from("<IIH", tail, 0)
        expand = tail[10]
        last_id, tz = struct.unpack_from("<II", tail, 11)
        tbl.footer = ET.ElemTableFooter(gcnt, marker, tcls, expand, last_id, tz, tail)
    else:
        tbl.footer = ET.ElemTableFooter(0, 0, 0, 0, 0, 0, tail)
    return tbl


@contextlib.contextmanager
def reading_2023(source: Optional[str] = None) -> Iterator[None]:
    """The FULL 2023 read context: the file's framing ordinals + (schema-
    gated) the whole 32-bit record layer -- delegated to
    ``rvt.versions.records32.reading32``.  Everything restores on exit;
    nothing leaks into the 2026 creation path."""
    from ..versions import records32
    with records32.reading32(source or RST_2023):
        yield


def load_document_2023(path: str):
    """A ``rvt.mutate.Document`` over a Revit-2023 file.  NOTE: Document
    decodes lazily -- keep :func:`id32` (or :func:`reading_2023`) in force
    while USING the document, not just while loading it."""
    from ..mutate import Document
    with reading_2023(path):
        return Document.from_file(path)


# ---------------------------------------------------------------------------
# MINED 2023 corpus constants (field oracles; per-specimen provenance in
# each comment; the census artifact is defaults_2023.json).  Everything
# below was DECODED from the quarantined samples/2023 corpus --
# independently RE-MINED, never assumed equal to the 2024/2025 constants.
# ---------------------------------------------------------------------------
#: RbsWireSettingsElem's three 2023-only doubles (same three fields as the
#: 2024/2025 delta).  Decoded from the 2023 rst sample elem 102129 AND the
#: 2023 rme sample elem 293123 (both carry the identical values): the
#: 2 % / 3 % max voltage-DROP sizing fractions and 30 degC ambient in
#: kelvin (303.15000000000003 is the EXACT stored double).
WIRE_SETTINGS_2023 = {
    "m_dMaxVoltageBranchSizing": 0.02,
    "m_dMaxVoltageFeederSizing": 0.03,
    "m_dAmbientTemperature": 303.15000000000003,
}

#: GeomTable's two 2023-only leading ints.  Corpus value for fresh/empty
#: tables is (-1, -1) -- the dominant value across every GeomTable decoded
#: from the 2023 rst sample (census in defaults_2023.json; the handful of
#: non-(-1,-1) tables are live-geometry ones, same as 2024/2025).
GEOMTABLE_2023 = {"m_maxSafeTag": -1, "m_lastCheckedKingsUserModificationDate": -1}

#: NumberingSchema 2023: schemaTypeGuid per scope category, decoded from the
#: 2023 rst sample's three built-in numbering schemas (1218729 rebar /
#: 1457391 couplers / 1218730 fabric sheets) -- identical GUIDs to
#: 2024/2025 (product identity of Revit's numbering machinery).  The same
#: specimens carry m_minimumNumberOfDigits 1, m_isMatchingEnabled True and
#: the ParameterBasedPartitionDescriptionCreator{m_ccda{weakref 1},
#: m_partitionParameterId -1154614} shape port2025's hooks build.
NUMBERING_SCHEMA_TYPE_GUIDS_2023 = {
    -2009000: "e0bc59cf-a1aa-48ae-83a2-637780af923d",   # Rebar Numbering
    -2009060: "396c2ee8-a554-4fed-bf44-c2e648dec011",   # Rebar Couplers Numbering
    -2009016: "f90085e5-ffbd-4dea-aadc-837c93df2943",   # Fabric Sheets Numbering
}

#: ViewDisplayMgr.m_useGDI / ModelGraphicsStyle.m_bUseGDI: False in every
#: decoded 2023 specimen (66/66 ViewDisplayMgr nested in the rst views,
#: 2/2 ModelGraphicsStyle).
USE_GDI_2023 = False

#: ReinforcementSettings.m_numberVaryingLengthRebarsIndividually: the 2023
#: sample default is True (rst elem 137426) -- NOT the blank default.
REINF_NUMBER_INDIVIDUALLY_2023 = True

#: RbsWireType.m_strMaxConductorSize: the 2023 sample stores the bare size
#: label ('2000' on rst elem 55171 and rme elem 261496).  OUR wire types
#: resolve their own conductor-size cell's label; this is the fallback.
WIRE_MAX_SIZE_FALLBACK_2023 = "2000"

#: the pen-table format constants, re-mined for 2023 (project table elem 2
#: in ALL THREE 2023 basics): the six model scale breakpoints, 16 pens per
#: vector, perspective/annotation vectors scale-independent (-1) --
#: IDENTICAL to the 2026/2025/2024 constants, so ``settings.pen_width_table``
#: ports value-unchanged.
PEN_SCALE_BREAKPOINTS_2023 = [10, 20, 50, 100, 200, 500]
PEN_COUNT_2023 = 16

#: ParamDef.m_groupElemId: the classic BuiltInParameterGroup ElementId per
#: 2026 group ForgeTypeId.  MINED by joining the same parameters (caption
#: key, ParamElemExternal / ParamElemProject /
#: ParamElemElectricalLoadClassification) across the 2023 and 2026 rst+rme
#: samples: 460 joined parameters over 18 distinct tokens, ZERO conflicts.
#: '' -> -1 is the corpus's own no-group value (43 corpus parameters).
PARAM_GROUP_ELEM_2023: Dict[str, int] = {
    "": -1,
    "autodesk.parameter.group:analysisResults-1.0.0": -5000161,
    "autodesk.parameter.group:constraints-1.0.0": -5000119,
    "autodesk.parameter.group:construction-1.0.0": -5000103,
    "autodesk.parameter.group:dimensions-1.0.0": -5000101,
    "autodesk.parameter.group:electrical-1.0.0": -5000130,
    "autodesk.parameter.group:electricalLighting-1.0.0": -5000124,
    "autodesk.parameter.group:electricalLoads-1.0.0": -5000125,
    "autodesk.parameter.group:graphics-1.0.0": -5000104,
    "autodesk.parameter.group:greenBuilding-1.0.0": -5000157,
    "autodesk.parameter.group:identityData-1.0.0": -5000100,
    "autodesk.parameter.group:materials-1.0.0": -5000105,
    "autodesk.parameter.group:mechanical-1.0.0": -5000113,
    "autodesk.parameter.group:mechanicalAirflow-1.0.0": -5000127,
    "autodesk.parameter.group:mechanicalLoads-1.0.0": -5000126,
    "autodesk.parameter.group:plumbing-1.0.0": -5000111,
    "autodesk.parameter.group:structural-1.0.0": -5000112,
    "autodesk.parameter.group:text-1.0.0": -5000123,
}
#: group tokens OUR constructors use that the 2023 corpus does not witness
#: (autodesk.parameter.group:general / :data / :electricalCircuiting):
#: mapped to -1, the corpus no-group value, with an adapt note.
PARAM_GROUP_UNWITNESSED_FALLBACK_2023 = -1

#: ElectricalLoadClassification: the 2026 m_signitureType enum values whose
#: 2023 twins are the two bools.  MINED both sides of the rme sample:
#: 2023 'Motor' = (m_motor True, m_spare False), 'Spare' = (False, True),
#: the other eight classifications (False, False); 2026 same names carry
#: m_signitureType 1 / 3 / (0 or 2).  house_standard F-HS-4 documents the
#: enum: 1 = motor, 2 = other, 3 = spare, else 0.
SIGNATURE_MOTOR_2026 = 1
SIGNATURE_SPARE_2026 = 3


# ---------------------------------------------------------------------------
# the 2023-NEW field-map hooks
# ---------------------------------------------------------------------------
def _hook_param_group(src: dict, ctx: _AdaptContext):
    """ParamDef: 2026 ``m_groupTypeId`` (ForgeTypeId) -> 2023
    ``m_groupElemId`` (BuiltInParameterGroup ElementId) via the mined
    corpus join; unwitnessed tokens -> -1 (the corpus no-group value)."""
    gt = src.get("m_groupTypeId")
    token = (gt or {}).get("m_typeId") if isinstance(gt, dict) else (gt or "")
    token = str(token or "")
    if token in PARAM_GROUP_ELEM_2023:
        return PARAM_GROUP_ELEM_2023[token]
    ctx.note(f"ParamDef.m_groupElemId: group token {token!r} not witnessed in the "
             f"2023 corpus join -> {PARAM_GROUP_UNWITNESSED_FALLBACK_2023} (no-group)")
    return PARAM_GROUP_UNWITNESSED_FALLBACK_2023


def _hook_load_class_motor(src: dict, ctx: _AdaptContext):
    return int(src.get("m_signitureType") or 0) == SIGNATURE_MOTOR_2026


def _hook_load_class_spare(src: dict, ctx: _AdaptContext):
    return int(src.get("m_signitureType") or 0) == SIGNATURE_SPARE_2026


def _hook_wire_max_size_2023(src: dict, ctx: _AdaptContext):
    """RbsWireType: id-of-catalog-cell -> the bare size-label string (the
    2023 corpus form, rst 55171 / rme 261496)."""
    sid = src.get("m_idMaxConductorSize", INVALID)
    if isinstance(sid, int) and sid not in (None, INVALID) and ctx.resolve_name:
        nm = ctx.resolve_name(int(sid))
        if nm:
            ctx.note(f"RbsWireType.m_strMaxConductorSize <- conductor-size cell "
                     f"{sid} name {nm!r}")
            return str(nm)
    ctx.note("RbsWireType.m_strMaxConductorSize <- fallback "
             f"{WIRE_MAX_SIZE_FALLBACK_2023!r} (max-size cell not resolvable)")
    return WIRE_MAX_SIZE_FALLBACK_2023


#: (declaring class, 2023 field) -> value hook(src_2026_obj, ctx).
#: A hook OVERRIDES both carry-over and the blank default.  The
#: same-as-2024/2025 block re-states those hooks against the 2023-mined
#: constants (values verified equal); the delegated hooks are the other
#: layers' own functions (layout preconditions asserted in tests).
#: DELIBERATELY ABSENT (like port2024, unlike port2025):
#: ("GeomStep", "m_oExtraData") -- 2023 has no extra-data field at all
#: (v15, same as 2024); it drops by construction.
HOOKS_2023: Dict[Tuple[str, str], Callable[[dict, _AdaptContext], Any]] = {
    # -- same delta as 2024/2025, 2023-mined values ---------------------------
    ("GeomTable", "m_maxSafeTag"): lambda s, c: GEOMTABLE_2023["m_maxSafeTag"],
    ("GeomTable", "m_lastCheckedKingsUserModificationDate"):
        lambda s, c: GEOMTABLE_2023["m_lastCheckedKingsUserModificationDate"],
    ("RbsWireSettingsElem", "m_dMaxVoltageBranchSizing"):
        lambda s, c: WIRE_SETTINGS_2023["m_dMaxVoltageBranchSizing"],
    ("RbsWireSettingsElem", "m_dMaxVoltageFeederSizing"):
        lambda s, c: WIRE_SETTINGS_2023["m_dMaxVoltageFeederSizing"],
    ("RbsWireSettingsElem", "m_dAmbientTemperature"):
        lambda s, c: WIRE_SETTINGS_2023["m_dAmbientTemperature"],
    ("RbsWireType", "m_strMaxConductorSize"): _hook_wire_max_size_2023,
    ("BrowserOrganization", "m_sortParamId"): _hook_sort_param_id,
    ("ModelGraphicsStyle", "m_bUseGDI"): lambda s, c: USE_GDI_2023,
    ("ViewDisplayMgr", "m_useGDI"): lambda s, c: USE_GDI_2023,
    ("ReinforcementSettings", "m_numberVaryingLengthRebarsIndividually"):
        lambda s, c: REINF_NUMBER_INDIVIDUALLY_2023,
    ("NumberingSchema", "m_oPartitionDescriptionCreator"): _hook_numbering_partition_creator,
    ("NumberingSchema", "m_minimumNumberOfDigits"): _hook_numbering_min_digits,
    ("NumberingSchema", "schemaTypeGuid"): _hook_numbering_type_guid,
    ("NumberingSchema", "m_isMatchingEnabled"): _hook_numbering_matching,
    ("BrowserOrganizationTracking", "m_currentBrOrgViews"):
        lambda s, c: _browser_tracking_tree(s, 0),
    ("BrowserOrganizationTracking", "m_currentBrOrgSheets"):
        lambda s, c: _browser_tracking_tree(s, 1),
    ("BrowserOrganizationTracking", "m_currentBrOrgSchedules"):
        lambda s, c: _browser_tracking_tree(s, 3),
    # -- same delta as 2024 (delegated; layout preconditions in tests) --------
    ("RbsDuctSettingsElem", "m_dAirViscosity"): _hook_duct_viscosity,
    ("MEPNetworkTracker", "m_component2BaseElementMap"): _hook_mep_network_map,
    # -- 2023-new deltas ------------------------------------------------------
    ("ParamDef", "m_groupElemId"): _hook_param_group,
    ("ElectricalLoadClassification", "m_motor"): _hook_load_class_motor,
    ("ElectricalLoadClassification", "m_spare"): _hook_load_class_spare,
}
for _dst in AUTOCAM_RENAMES_2024:                    # 2023 v5 == 2024 v5
    HOOKS_2023[("AutoCamSettingsElem", _dst)] = _autocam_hook(_dst)


#: classes genesis CONSTRUCTS that have NO Revit-2023 twin: the conductor
#: catalog (2026-only), the five 2025-era classes 2024 also lacks, PLUS the
#: two 2023-new settings classes.  Their constructors emit nothing on a
#: 2023 build.  (DrawOrderMgrBase is also MISSING-2023 but never
#: constructed -- a chain row; its fields live on 2023's DrawOrderMgr.)
MISSING_2023_CONSTRUCTED: Tuple[str, ...] = (
    # 2026-only (also missing in 2024/2025): the conductor catalog
    "CustomElement", "NamingCell", "RbsConductorMaterial",
    "RbsConductorTemperatureRating", "RbsConductorInsulationMaterial",
    "RbsConductorSize",
    # present in 2025, absent in 2024 AND 2023:
    "SheetCollection", "SheetsInSheetCollectionTracker", "MEPNetworkDataElem",
    "STEPExportSettings", "BuildingOperatingYearSchedule",
    # present in 2024/2025, ABSENT in 2023 (this stream's finding):
    "FabricationServiceSettings", "SSEPointVisibilitySettings",
)


# ---------------------------------------------------------------------------
# the generic schema-pair adapter, bound to the 2023 pin (the walk shape is
# port2025's verbatim method; port2025/port2024's walks are hardwired to
# their own singletons, so the walk lives here)
# ---------------------------------------------------------------------------
def adapt(class_name: str, obj: dict, *,
          resolve_name: Optional[Callable[[int], Optional[str]]] = None,
          _ctx: Optional[_AdaptContext] = None) -> dict:
    """A Revit-2023 object dict for ``class_name`` from a 2026-built one.

    Walks the 2023 class chain; carries same-name fields (recursively
    adapting nested class values), applies :data:`HOOKS_2023`, blanks the
    rest.  The source is never mutated.  Raises :class:`Missing2023` when
    the class (or a pointed-to class inside it) has no 2023 twin.
    """
    ctx = _ctx or _AdaptContext(resolve_name=resolve_name)
    _dec23, _enc, schema23 = _S23()
    cd = schema23.by_name.get(class_name)
    if cd is None:
        raise Missing2023(f"class {class_name!r} is not in the Revit-2023 archive "
                          "class map")
    return _adapt_class(class_name, cd.type_id, obj or {}, ctx)


def _adapt_class(class_name: str, type_id: int, src: dict, ctx: _AdaptContext) -> dict:
    from ..objects import field_key
    dec23, _enc, _s = _S23()
    out: dict = {}
    for cd in dec23.chain(type_id):
        for f in cd.fields:
            key = field_key(cd, f, out)
            hook = HOOKS_2023.get((cd.name, f.name))
            if hook is not None:
                out[key] = hook(src, ctx)
                continue
            if key in src:
                out[key] = _adapt_field(f, src[key], ctx, f"{class_name}.{key}")
            elif f.name in src:                       # shadow-key fallback
                out[key] = _adapt_field(f, src[f.name], ctx, f"{class_name}.{f.name}")
            else:
                out[key] = _blank_field_for(dec23, f, 0)
    return out


def _adapt_field(f, v: Any, ctx: _AdaptContext, path: str):
    kind, flags = f.kind, f.flags
    shape = flags >> 4
    dec23, _enc, schema23 = _S23()
    if kind == 0x08:                                   # AString (scalar or list)
        if shape in (1, 5):
            return [str(x) for x in (v or [])]
        return "" if v is None else str(v)
    if kind == 0x0D:                                   # inline array wrapper
        if not isinstance(v, list):
            ctx.note(f"{path}: expected list for array field, got "
                     f"{type(v).__name__} -> blank []")
            return _blank_field_for(dec23, f, 0)
        return [_adapt_field(f.element, x, ctx, f"{path}[{i}]")
                for i, x in enumerate(v)]
    if shape == 5:                                     # growable container
        if not isinstance(v, list):
            ctx.note(f"{path}: expected container, got {type(v).__name__} -> []")
            return []
        return [_adapt_scalar(f, kind, flags & 0x0F, x, ctx, f"{path}[{i}]")
                for i, x in enumerate(v)]
    if shape == 1:                                     # fixed array
        vals = v if isinstance(v, list) else []
        n = f.count or 0
        out = [_adapt_scalar(f, kind, flags & 0x0F, x, ctx, f"{path}[{i}]")
               for i, x in enumerate(vals[:n])]
        while len(out) < n:
            out.append(_blank_scalar_for(dec23, f, kind, flags & 0x0F, 0))
        return out
    return _adapt_scalar(f, kind, flags & 0x0F, v, ctx, path)


def _adapt_scalar(f, kind: int, indir: int, v: Any, ctx: _AdaptContext, path: str):
    from ..objects import _PRIM_FMT
    dec23, _enc, schema23 = _S23()
    if kind == 0x01:
        return bool(v)
    if kind in _PRIM_FMT:
        return v if isinstance(v, (int, float)) else (0.0 if kind in (0x06, 0x07) else 0)
    if kind == 0x08:
        return "" if v is None else str(v)
    if kind == 0x09:
        return str(v) if v else NULL_GUID
    if kind == 0x0A:                                   # classref
        name = v.get("classref") if isinstance(v, dict) else v
        if name and name not in schema23.by_name:
            raise Missing2023(f"{path}: classref {name!r} has no 2023 twin")
        return {"classref": name or "Element"}
    if kind == 0x0E:
        if indir == 0:                                 # inline value class
            tid = f.type_id
            if tid in (dec23.id_ElementId, dec23.id_Identifier):
                iv = int(v) if isinstance(v, (int, float)) else INVALID
                if not (-(1 << 31) <= iv < (1 << 31)):
                    raise PortabilityError(
                        f"{path}: element id {iv} does not fit the 32-bit 2023 "
                        "id space -- allocate 2023-build ids below 2**31")
                return iv
            if tid == dec23.id_XYZ:
                return list(v) if isinstance(v, list) else [0.0, 0.0, 0.0]
            if tid == dec23.id_UV:
                return list(v) if isinstance(v, list) else [0.0, 0.0]
            if tid == dec23.id_GUIDvalue:
                return str(v) if v else NULL_GUID
            cname = dec23.class_name(tid)
            if not isinstance(v, dict):
                ctx.note(f"{path}: inline {cname} source is {type(v).__name__} "
                         "-> 2023 blank")
                return _blank_class_for(dec23, schema23.by_name[cname].type_id, 1)
            return _adapt_class(cname, tid, v, ctx)
        if indir == 3:                                 # weak pointer
            if isinstance(v, dict) and "weakref" in v:
                return {"weakref": int(v["weakref"])}
            return {"weakref": int(v or 0)}
        # owned / poly pointer
        if v is None:
            return None
        if isinstance(v, dict) and "backref_pid" in v:
            return dict(v)
        if isinstance(v, dict) and "ptr_class" in v:
            pcls = v["ptr_class"]
            cd = schema23.by_name.get(pcls)
            if cd is None:
                raise Missing2023(f"{path}: pointed-to class {pcls!r} has no 2023 twin")
            body = v.get("value")
            return {"ptr_class": pcls, "pid": v.get("pid", -1),
                    "value": (None if body is None
                              else _adapt_class(pcls, cd.type_id, body, ctx))}
        ctx.note(f"{path}: unrecognised pointer token {type(v).__name__} -> null")
        return None
    raise PortabilityError(f"{path}: unsupported field kind {kind:#x}")


# ---------------------------------------------------------------------------
# record-level adaptation (what a Revit-2023 build path consumes)
# ---------------------------------------------------------------------------
@dataclasses.dataclass
class PortedRecord:
    """A 2026 TypeRecord-shaped record re-expressed for Revit 2023: 2023
    class ids, 2023-shaped seq-101/102/103 bodies.  NOTE any record FRAMING
    of these bodies must use the 2023 framing (4-byte ids,
    :func:`iter_records_2023`'s layout) inside :func:`id32`."""
    elem_id: int
    kind: str
    class_name: str
    class_id: int                     # 2023 ordinal
    obj: dict                         # seq-102 body (2023 shape)
    header: dict                      # seq-101 body (2023 shape)
    rep: Optional[dict]               # seq-103 GElement body or None (dummy)
    rep_class_id: int                 # 2023 ordinal (GElement / SerializedDummy)
    rep_class_name: str
    refs: dict = dataclasses.field(default_factory=dict)
    notes: List[str] = dataclasses.field(default_factory=list)

    def records(self) -> list:
        return [(101, class_id_2023("ElementHeader"), self.header),
                (102, self.class_id, self.obj),
                (103, self.rep_class_id, self.rep if self.rep is not None else {})]


def adapt_record(rec, *, resolve_name: Optional[Callable[[int], Optional[str]]] = None
                 ) -> PortedRecord:
    """Adapt one 2026 constructor record into a :class:`PortedRecord`.
    Raises :class:`Missing2023` for :data:`MISSING_2023_CONSTRUCTED` classes
    (callers emit nothing for those on a 2023 build)."""
    cname = rec.class_name
    if not exists_2023(cname):
        raise Missing2023(f"{cname} (record {rec.elem_id}) has no Revit-2023 "
                          "twin -- emit nothing on a 2023 build")
    if not (-(1 << 31) <= int(rec.elem_id) < (1 << 31)):
        raise PortabilityError(f"record id {rec.elem_id} does not fit the 32-bit "
                               "2023 id space")
    ctx = _AdaptContext(resolve_name=resolve_name)
    obj23 = _adapt_class(cname, _S23()[2].by_name[cname].type_id,
                         copy.deepcopy(rec.obj or {}), ctx)
    hdr23 = adapt("ElementHeader", copy.deepcopy(rec.header or {}),
                  resolve_name=resolve_name, _ctx=ctx)
    rep = getattr(rec, "rep", None)
    if rep is not None:
        rep23 = adapt("GElement", copy.deepcopy(rep), resolve_name=resolve_name,
                      _ctx=ctx)
        rep_cid, rep_cn = class_id_2023("GElement"), "GElement"
    else:
        rep23, rep_cid, rep_cn = None, class_id_2023("SerializedDummy"), "SerializedDummy"
    return PortedRecord(
        elem_id=int(rec.elem_id), kind=str(getattr(rec, "kind", "")),
        class_name=cname, class_id=class_id_2023(cname), obj=obj23,
        header=hdr23, rep=rep23, rep_class_id=rep_cid, rep_class_name=rep_cn,
        refs=dict(getattr(rec, "refs", {}) or {}),
        notes=list(getattr(rec, "notes", []) or []) + ctx.notes)


def verify_roundtrip_2023(class_id: int, obj: dict) -> dict:
    """Encode ``obj`` under the 2023 schema, decode it back, re-encode:
    the port2023 round-trip gate (clean + byte-exact required), run INSIDE
    the i32 codec context."""
    dec, enc, _s = _S23()
    with id32():
        body = enc.encode_object(class_id, obj or {})
        got = dec.decode_record(class_id, body)
        body2 = enc.encode_object(class_id, got.value) if got.clean else b""
    return {"class": dec.class_name(class_id), "bytes": len(body),
            "clean": bool(got.clean), "byte_exact": body == body2,
            "errors": list(got.errors or [])[:3],
            "ok": bool(got.clean) and body == body2}


def verify_ported(pr: PortedRecord) -> dict:
    """Round-trip every seq body of a :class:`PortedRecord` under 2023."""
    rep = {}
    for seq, cid, body in pr.records():
        rep[seq] = verify_roundtrip_2023(cid, body or {})
    rep["ok"] = all(rep[s]["ok"] for s in (101, 102, 103))
    return rep


# ---------------------------------------------------------------------------
# the CONFIRMED portability table (four-way: 2026 vs 2023, annotated vs the
# 2026->2025 AND 2026->2024 tables)
# ---------------------------------------------------------------------------
def harvest_constructed_classes() -> Dict[str, List[str]]:
    """{class name: [where]} harvested from the genesis sources -- port2025's
    harvest rule, with ALL THREE portability layers excluded (they carry
    class names as field-map keys, not constructors)."""
    _d, _e, s26 = _S26()
    out: Dict[str, Set[str]] = collections.defaultdict(set)
    for fn in sorted(os.listdir(GENESIS_DIR)):
        if not fn.endswith(".py") or fn in _PORT_LAYERS:
            continue
        src = open(os.path.join(GENESIS_DIR, fn)).read()
        tree = ast.parse(src)
        doc_positions: Set[int] = set()
        for node in ast.walk(tree):
            body = getattr(node, "body", None)
            if isinstance(body, list) and body and isinstance(body[0], ast.Expr) and \
                    isinstance(body[0].value, ast.Constant) and \
                    isinstance(body[0].value.value, str):
                doc_positions.add(id(body[0].value))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                    and id(node) not in doc_positions:
                v = node.value
                if v in s26.by_name and v.strip() == v and " " not in v:
                    out[v].add(f"{fn}:{node.lineno}")
    return {k: sorted(v) for k, v in sorted(out.items())}


def _field_sig(f, schema):
    tn = None
    if f.type_id is not None:
        c = schema.by_id.get(f.type_id)
        tn = c.name if c else f.type_name
    el = _field_sig(f.element, schema) if f.element is not None else None
    return (f.name, f.kind, f.flags, f.count, tn, f.extra, el)


def diff_class(name: str) -> dict:
    """One class's CONFIRMED 2026-vs-2023 verdict: IDENTICAL / VERSION-ONLY /
    LAYOUT-DELTA (with exact field deltas) / MISSING-2023."""
    dec26, _e26, s26 = _S26()
    dec23, _e23, s23 = _S23()
    a = s26.by_name.get(name)
    if a is None:
        return {"class": name, "verdict": "NOT-IN-2026"}
    b = s23.by_name.get(name)
    if b is None:
        return {"class": name, "verdict": "MISSING-2023", "version_2026": a.version}
    ca, cb = dec26.chain(a.type_id), dec23.chain(b.type_id)
    flat26 = [(c.name, _field_sig(f, s26)) for c in ca for f in c.fields]
    flat23 = [(c.name, _field_sig(f, s23)) for c in cb for f in c.fields]
    chain26, chain23 = [c.name for c in ca], [c.name for c in cb]
    out: Dict[str, Any] = {"class": name, "version_2026": a.version,
                           "version_2023": b.version, "chain": chain26}
    if flat26 == flat23 and chain26 == chain23:
        out["verdict"] = ("IDENTICAL" if a.version == b.version else "VERSION-ONLY")
        return out
    out["verdict"] = "LAYOUT-DELTA"
    if chain26 != chain23:
        out["chain_2023"] = chain23
    deltas = []
    for c26 in ca:
        c23 = next((c for c in cb if c.name == c26.name), None)
        if c23 is None:
            deltas.append({"base": c26.name, "delta": "base class missing in 2023"})
            continue
        f26 = [_field_sig(f, s26) for f in c26.fields]
        f23 = [_field_sig(f, s23) for f in c23.fields]
        if f26 == f23 and c26.version == c23.version:
            continue
        n26, n23 = {t[0] for t in f26}, {t[0] for t in f23}
        d = {"base": c26.name, "version": f"{c26.version}->{c23.version}",
             "only_2026": [t[0] for t in f26 if t[0] not in n23],
             "only_2023": [t[0] for t in f23 if t[0] not in n26],
             "changed": [t[0] for t in f26
                         if t[0] in n23 and next(u for u in f23 if u[0] == t[0]) != t]}
        shared26 = [t[0] for t in f26 if t[0] in n23]
        shared23 = [t[0] for t in f23 if t[0] in n26]
        if shared26 != shared23:
            d["order_differs"] = True
        deltas.append(d)
    out["deltas"] = deltas
    out["hooked"] = sorted({f for (c, f) in HOOKS_2023
                            if c in chain26 or c == name})
    return out


def _norm_deltas(row: dict, year_label: str) -> tuple:
    """Delta shape normalised for cross-release comparison (only_20XX keyed
    positionally so any two release tables compare)."""
    ds = []
    for d in row.get("deltas", []):
        if "delta" in d:
            ds.append((d["base"], d["delta"].replace(year_label, "X")))
        else:
            ds.append((d["base"], tuple(d.get("only_2026") or []),
                       tuple(d.get(f"only_{year_label}") or []),
                       tuple(d.get("changed") or []),
                       bool(d.get("order_differs"))))
    return tuple(ds)


def _vs_release(name: str, row23: dict, other_mod, other_year: str) -> str:
    """How this class's 2023 delta relates to another release's delta."""
    r_other = other_mod.diff_class(name)
    v23, vo = row23["verdict"], r_other["verdict"]
    if v23 == "LAYOUT-DELTA" and vo == "LAYOUT-DELTA":
        return (f"same-as-{other_year}"
                if _norm_deltas(row23, "2023") == _norm_deltas(r_other, other_year)
                else f"differs-from-{other_year}")
    if v23.replace("2023", other_year) == vo:
        return f"both-{vo}"
    return f"{other_year}={vo}"


def portability_table(*, write: bool = True) -> dict:
    """The CONFIRMED constructor-portability table 2026 -> 2023, four-way
    annotated against port2025's and port2024's tables.  Frozen to
    :data:`PORTABILITY_JSON`."""
    from . import port2024 as P24
    from . import port2025 as P25
    dec26, _e, s26 = _S26()
    harvest = harvest_constructed_classes()
    names: Set[str] = set(harvest)
    for n in list(names):
        cd = s26.by_name.get(n)
        if cd:
            names.update(c.name for c in dec26.chain(cd.type_id))
    rows = {}
    for n in sorted(names):
        r = diff_class(n)
        if r["verdict"] in ("LAYOUT-DELTA", "MISSING-2023", "VERSION-ONLY"):
            r["vs_2025"] = _vs_release(n, r, P25, "2025")
            r["vs_2024"] = _vs_release(n, r, P24, "2024")
        rows[n] = r
    counts = collections.Counter(r["verdict"] for r in rows.values())
    reorder_only = sorted(
        n for n, r in rows.items() if r["verdict"] == "LAYOUT-DELTA"
        and all(not d.get("only_2026") and not d.get("only_2023")
                and not d.get("changed") and "delta" not in d
                for d in r["deltas"]))
    table = {
        "generator": "rvt.genesis.port2023.portability_table",
        "method": "port2025's method re-run for 2023: own-field signatures by "
                  "type NAME + flattened parent-first chain + class versions, "
                  "2026 pin vs the port2023 in-module 2023 pin; every "
                  "LAYOUT-DELTA / MISSING / VERSION-ONLY row four-way annotated "
                  "vs the 2026->2025 AND 2026->2024 tables (vs_2025 / vs_2024)",
        "id_model": {
            "element_id_bytes": ID_WIDTH_2023,
            "identifier_declaration": "Identifier v1 m_id kind 0x04 (i32); "
                                      "2024+ is v2 m_id64 kind 0x0b (i64)",
            "record_headers": "seq101 <iI (8B) / seq102+103 <iII (12B); "
                              "4-byte -1 sentinel; same adler32 stamp",
            "elemtable_row": "28 bytes, order id/history/partition/owner",
        },
        "universe": {"harvested": len(harvest), "with_chain_expansion": len(names)},
        "counts": dict(counts),
        "non_monotonic_findings": {
            "reorder_only_classes": reorder_only,
            "deltas_that_differ_from_2024": sorted(
                n for n, r in rows.items()
                if r.get("vs_2024") == "differs-from-2024"),
            "deltas_that_differ_from_2025": sorted(
                n for n, r in rows.items()
                if r.get("vs_2025") == "differs-from-2025"),
            "viewport_note": "2023 v10 drops m_oPlaceholderBoxOutline; 2024 is "
                             "ALSO v10 and keeps it -- same class version, "
                             "different layout across releases",
            "dbviewdrafting_note": "2023 v10 has NO m_scheduleInstanceIds "
                                   "(2024-only field)",
            "draworder_note": "DrawOrderMgrBase missing in 2023; its two weakref "
                              "fields live on DrawOrderMgr itself (chain "
                              "re-shape, name-carry handles; 45/45 rst views "
                              "carry the pointer set)",
            "constructed_missing_2023": list(MISSING_2023_CONSTRUCTED),
        },
        "mined_constants": {
            "WIRE_SETTINGS_2023": WIRE_SETTINGS_2023,
            "GEOMTABLE_2023": GEOMTABLE_2023,
            "NUMBERING_SCHEMA_TYPE_GUIDS_2023": NUMBERING_SCHEMA_TYPE_GUIDS_2023,
            "USE_GDI_2023": USE_GDI_2023,
            "REINF_NUMBER_INDIVIDUALLY_2023": REINF_NUMBER_INDIVIDUALLY_2023,
            "WIRE_MAX_SIZE_FALLBACK_2023": WIRE_MAX_SIZE_FALLBACK_2023,
            "PEN_SCALE_BREAKPOINTS_2023": PEN_SCALE_BREAKPOINTS_2023,
            "PEN_COUNT_2023": PEN_COUNT_2023,
            "PARAM_GROUP_ELEM_2023": PARAM_GROUP_ELEM_2023,
            "SIGNATURE_ENUM": {"motor": SIGNATURE_MOTOR_2026,
                               "spare": SIGNATURE_SPARE_2026},
        },
        "classes": rows,
        "harvest_provenance": harvest,
    }
    if write:
        os.makedirs(OUT_DIR, exist_ok=True)
        with open(PORTABILITY_JSON, "w") as fh:
            json.dump(table, fh, indent=1)
    return table


# ---------------------------------------------------------------------------
# 2023 corpus miners (the same derivations as rvt.genesis.catalog /
# port2024/port2025, run over the quarantined samples/2023 corpus INSIDE the
# 2023 read context)
# ---------------------------------------------------------------------------
def _sample_documents_2023(names: Sequence[str] = ("rstbasicsampleproject",
                                                   "rmebasicsampleproject",
                                                   "racbasicsampleproject")):
    """(stem, Document) per local 2023 basic sample.  The CALLER must hold
    :func:`id32` open while consuming the documents (decode is lazy)."""
    for n in names:
        p = os.path.join(SAMPLES_2023, f"{n}.rvt")
        if not os.path.exists(p):
            continue
        yield n, load_document_2023(p)


def derive_builtin_category_enum_2023(verbose: bool = True) -> dict:
    """The Revit-2023 graphic-category ENUM (catalog's derivation over the
    2023 samples): every built-in category id carrying a host object-style
    row + its cuttability, asserted identical across the samples."""
    per: Dict[str, Dict[int, set]] = {}
    with id32():
        for s, doc in _sample_documents_2023():
            rows: Dict[int, set] = collections.defaultdict(set)
            for gid in doc.ids_of_class("GStyleElem", host_only=True):
                v = doc.value(gid) or {}
                if v.get("m_famId", -1) != -1:
                    continue
                cid = v.get("m_categoryId")
                if isinstance(cid, int) and cid < 0:
                    rows[cid].add(int(v.get("m_gstyleType", 1)))
            per[s] = dict(rows)
            if verbose:
                print(f"   [enum-2023] {s}: {len(rows)} built-in categories, "
                      f"{sum(1 for t in rows.values() if 2 in t)} cuttable")
    base = None
    for s, rows in per.items():
        norm = {k: tuple(sorted(v)) for k, v in rows.items()}
        if base is None:
            base = norm
        elif norm != base:
            diff = set(norm) ^ set(base)
            raise RuntimeError(f"2023 graphic-category enum differs in {s}: "
                               f"{len(diff)} ids differ")
    cats = [{"id": int(cid), "cut": 2 in ts} for cid, ts in sorted((base or {}).items())]
    return {"generator": "rvt.genesis.port2023.derive_builtin_category_enum_2023",
            "derived_from": sorted(per), "release": 2023,
            "count": len(cats), "cuttable": sum(1 for c in cats if c["cut"]),
            "categories": cats}


def derive_builtin_style_profile_2023(verbose: bool = True) -> dict:
    """The per-(category, style-type) STRUCTURAL profile of the 2023
    object-styles table (catalog.derive_builtin_style_profile's rules over
    the 2023 samples).  Structure only."""
    from .catalog import AB_CELLLIST_BIT, BUILTIN_SOLID_PATTERN, _modal
    per: Dict[Tuple[int, int], dict] = collections.defaultdict(lambda: {
        "ab": collections.Counter(), "vis": collections.Counter(),
        "pat_val": collections.Counter(), "pat_kind": collections.Counter(),
        "mat_val": collections.Counter(), "mat_kind": collections.Counter(),
        "scr": collections.Counter(), "pen": collections.Counter(), "files": set()})
    n_rows = 0
    with id32():
        for s, doc in _sample_documents_2023():
            seen = 0
            for gid in doc.ids_of_class("GStyleElem", host_only=True):
                v = doc.value(gid) or {}
                if v.get("m_famId", -1) != -1 or v.get("m_ownerId", -1) != -1:
                    continue
                cid = v.get("m_categoryId")
                if not (isinstance(cid, int) and cid < 0):
                    continue
                gt = int(v.get("m_gstyleType", 1))
                p = per[(int(cid), gt)]
                p["files"].add(s)
                gs = ((v.get("m_pGStyle") or {}).get("value") or {})
                pat, mat, pen = (gs.get("m_linePatternId"), gs.get("m_materialElemId"),
                                 gs.get("m_penNumber"))
                p["pat_kind"]["null" if pat == INVALID else
                              ("builtin" if isinstance(pat, int) and pat < 0 else "elem")] += 1
                if isinstance(pat, int) and pat < 0 and pat != INVALID:
                    p["pat_val"][int(pat)] += 1
                p["mat_kind"]["null" if mat == INVALID else
                              ("builtin" if isinstance(mat, int) and mat < 0 else "elem")] += 1
                if isinstance(mat, int) and mat < 0 and mat != INVALID:
                    p["mat_val"][int(mat)] += 1
                p["scr"][bool(gs.get("m_isScreenSized"))] += 1
                if isinstance(pen, int):
                    p["pen"][int(pen)] += 1
                h = doc.decode(gid, 101)
                if h and getattr(h, "clean", False) and h.value:
                    p["ab"][int(h.value.get("m_abFlags4Bytes") or 0)] += 1
                    p["vis"][int(((h.value.get("m_viewRules") or {})
                                  .get("m_nVisibleViewFlags") or 0))] += 1
                seen += 1
            n_rows += seen
            if verbose:
                print(f"   [profile-2023] {s}: {seen} built-in object-style rows")
    keys = {}
    for (cid, gt), p in sorted(per.items()):
        clean = collections.Counter({a: c for a, c in p["ab"].items()
                                     if not (a & AB_CELLLIST_BIT)})
        ab = _modal(clean)
        if ab is None:
            ab = (_modal(p["ab"]) or 0) & ~AB_CELLLIST_BIT
        vis = _modal(p["vis"])
        kinds = set(p["pat_kind"])
        if kinds == {"null"}:
            pattern = "null"
        elif kinds == {"elem"}:
            pattern = "elem"
        elif "builtin" in kinds:
            if BUILTIN_SOLID_PATTERN in p["pat_val"]:
                pattern = "solid"
            elif kinds == {"builtin"}:
                pattern = f"builtin:{_modal(p['pat_val'])}"
            else:
                pattern = "solid"
        else:
            pattern = "nullwire"
        mkinds = set(p["mat_kind"])
        if mkinds == {"null"}:
            material = "null"
        elif mkinds == {"elem"}:
            material = "elem"
        elif mkinds == {"builtin"}:
            material = f"builtin:{_modal(p['mat_val'])}"
        else:
            material = "nullwire"
        pens = set(p["pen"])
        keys[f"{cid}:{gt}"] = {
            "cat": cid, "type": gt, "files": len(p["files"]),
            "ab": int(ab), "ab_set": sorted(int(x) for x in p["ab"]),
            "vis": int(vis) if vis is not None else -32768,
            "pattern": pattern, "material": material,
            "screen_sized": (set(p["scr"]) == {True}),
            "pen": ("null0" if pens == {0} else
                    ("nullneg1" if pens == {-1} else "ours")),
        }
    return {"generator": "rvt.genesis.port2023.derive_builtin_style_profile_2023",
            "release": 2023, "rows_analysed": n_rows, "count": len(keys),
            "keys": keys}


def derive_pen_table_2023(verbose: bool = True) -> dict:
    """The 2023 project pen-table FORMAT constants, mined from every basic
    sample's project table (m_famId -1): the model scale-breakpoint set,
    pens per vector, perspective/annotation scale sentinels."""
    tables = []
    with id32():
        for s, doc in _sample_documents_2023():
            for gid in doc.ids_of_class("PenWidthTableElem", host_only=True):
                v = doc.value(gid) or {}
                if v.get("m_famId", -1) != -1:
                    continue
                t = ((v.get("m_pPenWidthTable") or {}).get("value") or {})
                model = t.get("m_modelPenInfo") or []
                widths = [w for x in model for w in (x.get("m_pens") or [])]
                widths += list((t.get("m_perspectiveModelPenInfo") or {}).get("m_pens") or [])
                widths += list((t.get("m_draftPenInfo") or {}).get("m_pens") or [])
                row = {
                    "file": s, "elem_id": int(gid),
                    "scales": sorted(int(x.get("m_invertedScale")) for x in model),
                    "pens_per_vector": sorted({len(x.get("m_pens") or []) for x in model}),
                    "perspective_scale": (t.get("m_perspectiveModelPenInfo") or {}).get("m_invertedScale"),
                    "draft_scale": (t.get("m_draftPenInfo") or {}).get("m_invertedScale"),
                    "width_ft_range": [min(widths), max(widths)] if widths else None,
                }
                tables.append(row)
                if verbose:
                    print(f"   [pen-2023] {s} id {gid}: scales={row['scales']} "
                          f"pens={row['pens_per_vector']} persp={row['perspective_scale']}")
    scale_sets = {tuple(r["scales"]) for r in tables}
    pen_counts = {tuple(r["pens_per_vector"]) for r in tables}
    if scale_sets != {tuple(PEN_SCALE_BREAKPOINTS_2023)}:
        raise RuntimeError(f"2023 pen-table scale keys differ from the pinned "
                           f"constant: {scale_sets}")
    if pen_counts != {(PEN_COUNT_2023,)}:
        raise RuntimeError(f"2023 pen count differs from {PEN_COUNT_2023}: {pen_counts}")
    return {"generator": "rvt.genesis.port2023.derive_pen_table_2023",
            "release": 2023, "project_tables": tables,
            "scale_breakpoints": PEN_SCALE_BREAKPOINTS_2023,
            "pens_per_vector": PEN_COUNT_2023,
            "perspective_draft_scale": -1,
            "matches_2026_constant": True}


def derive_palette_invariants_2023(verbose: bool = True) -> dict:
    """The 2023 PropertySetElement (palette) serialisation invariants --
    residue_b2's corpus laws, re-measured over the 2023 samples: param-id
    ASCENDING order per container, built-in ids NEGATIVE, m_pElementIdParams
    PRESENT-EMPTY, the property-set-type census."""
    asc = collections.Counter()
    eidset = collections.Counter()
    pstype = collections.Counter()
    neg = collections.Counter()
    per_file = {}
    n_sets = 0
    with id32():
        for s, doc in _sample_documents_2023():
            seen = 0
            for e in doc.ids_of_class("PropertySetElement", host_only=True):
                v = doc.value(e) or {}
                pstype[int(v.get("m_propertySetType", -1))] += 1
                ps = ((v.get("m_oParamSet") or {}).get("value") or {})
                for key in ("m_pDoubleParams", "m_pIntParams", "m_pAStringParams"):
                    arr = ((((ps.get(key) or {}).get("value") or {}).get("m_paramSet")) or [])
                    ids = [x.get("m_paramId") for x in arr]
                    asc[ids == sorted(ids)] += 1
                    for i in ids:
                        neg[bool(isinstance(i, int) and i < 0)] += 1
                eid = ps.get("m_pElementIdParams")
                present_empty = (isinstance(eid, dict) and eid.get("value") is not None
                                 and not (eid["value"].get("m_paramSet") or []))
                eidset["present_empty" if present_empty
                       else ("null" if eid is None else "nonempty")] += 1
                n_sets += 1
                seen += 1
            per_file[s] = seen
            if verbose:
                print(f"   [palette-2023] {s}: {seen} PropertySetElements")
    out = {"generator": "rvt.genesis.port2023.derive_palette_invariants_2023",
           "release": 2023, "property_sets": n_sets, "per_file": per_file,
           "type_census": {str(k): v for k, v in sorted(pstype.items())},
           "param_containers_ascending": {str(k): v for k, v in asc.items()},
           "param_ids_negative": {str(k): v for k, v in neg.items()},
           "element_id_set": dict(eidset),
           "laws_hold": (set(asc) <= {True} and set(neg) <= {True}
                         and set(eidset) <= {"present_empty"})}
    if not out["laws_hold"]:
        raise RuntimeError(f"2023 palette invariants VIOLATED: {out}")
    return out


def derive_defaults_2023(verbose: bool = True) -> dict:
    """The 2023 value-constant CENSUS with per-specimen provenance: every
    mined constant above re-derived mechanically (wire settings, GeomTable
    extras, GDI flags, reinforcement flag, wire size label, numbering
    oracle, the ParamDef group map witnesses, the load-classification bool
    split).  The frozen artifact behind the in-module constants."""
    out: Dict[str, Any] = {"generator": "rvt.genesis.port2023.derive_defaults_2023",
                           "release": 2023}
    with id32():
        docs = dict(_sample_documents_2023())
        rst = docs.get("rstbasicsampleproject")
        rme = docs.get("rmebasicsampleproject")
        # wire settings
        ws = {}
        for nm, d in (("rst", rst), ("rme", rme)):
            if d is None:
                continue
            for e in d.ids_of_class("RbsWireSettingsElem", host_only=True):
                v = d.value(e) or {}
                ws[f"{nm}:{e}"] = {k: v.get(k) for k in WIRE_SETTINGS_2023}
        out["wire_settings"] = ws
        assert all(row == WIRE_SETTINGS_2023 for row in ws.values()), ws
        # GeomTable extras: full census over every decoded rst value tree
        hits = collections.Counter()

        def walk(v):
            if isinstance(v, dict):
                if "m_maxSafeTag" in v and "m_lastCheckedKingsUserModificationDate" in v:
                    hits[(v.get("m_maxSafeTag"),
                          v.get("m_lastCheckedKingsUserModificationDate"))] += 1
                for x in v.values():
                    walk(x)
            elif isinstance(v, list):
                for x in v:
                    walk(x)
        if rst is not None:
            for e in list(rst.idx[102]):
                walk(rst.value(e) or {})
        out["geomtable_census_rst"] = {str(k): c for k, c in hits.most_common()}
        top = hits.most_common(1)[0][0] if hits else None
        assert top == (-1, -1), f"GeomTable dominant value {top}"
        out["geomtable_dominant"] = [-1, -1]
        # GDI
        gdi = {"ModelGraphicsStyle": collections.Counter(),
               "ViewDisplayMgr": collections.Counter()}

        def walk_gdi(v):
            if isinstance(v, dict):
                if "m_useGDI" in v:
                    gdi["ViewDisplayMgr"][bool(v.get("m_useGDI"))] += 1
                for x in v.values():
                    walk_gdi(x)
            elif isinstance(v, list):
                for x in v:
                    walk_gdi(x)
        if rst is not None:
            for e in rst.ids_of_class("ModelGraphicsStyle", host_only=True):
                gdi["ModelGraphicsStyle"][bool((rst.value(e) or {}).get("m_bUseGDI"))] += 1
            for cls in ("DBViewPlan", "DBViewProject", "DBViewDrafting",
                        "DBView3d", "DBViewSection"):
                for e in rst.ids_of_class(cls, host_only=True):
                    walk_gdi(rst.value(e) or {})
        out["use_gdi"] = {k: {str(b): n for b, n in c.items()} for k, c in gdi.items()}
        assert all(set(c) <= {False} for c in gdi.values()), gdi
        # reinforcement
        reinf = {}
        if rst is not None:
            for e in rst.ids_of_class("ReinforcementSettings", host_only=True):
                reinf[e] = (rst.value(e) or {}).get(
                    "m_numberVaryingLengthRebarsIndividually")
        out["reinforcement_number_individually"] = reinf
        assert set(reinf.values()) == {True}, reinf
        # wire type size label
        wl = {}
        for nm, d in (("rst", rst), ("rme", rme)):
            if d is None:
                continue
            for e in d.ids_of_class("RbsWireType", host_only=True):
                wl[f"{nm}:{e}"] = (d.value(e) or {}).get("m_strMaxConductorSize")
        out["wire_max_size_labels"] = wl
        # numbering oracle
        num = {}
        if rst is not None:
            for e in rst.ids_of_class("NumberingSchema", host_only=True):
                v = rst.value(e) or {}
                num[e] = {"scope": v.get("m_scopeCategories"),
                          "guid": (v.get("schemaTypeGuid") or {}).get("m_value"),
                          "minDigits": v.get("m_minimumNumberOfDigits"),
                          "matching": v.get("m_isMatchingEnabled")}
        out["numbering_schemas"] = num
        got_guids = {int((r["scope"] or [0])[0]): r["guid"] for r in num.values()}
        assert got_guids == NUMBERING_SCHEMA_TYPE_GUIDS_2023, got_guids
        # load classifications (2023 side of the bool split)
        lc = {}
        if rme is not None:
            for e in rme.ids_of_class("ElectricalLoadClassification", host_only=True):
                v = rme.value(e) or {}
                lc[v.get("m_name")] = {"motor": v.get("m_motor"),
                                       "spare": v.get("m_spare")}
        out["load_classifications"] = lc
        if lc:
            assert lc.get("Motor", {}).get("motor") is True
            assert lc.get("Spare", {}).get("spare") is True
            assert all((n in ("Motor", "Spare")) or
                       (r["motor"] is False and r["spare"] is False)
                       for n, r in lc.items()), lc
        # ParamDef group witnesses (2023 side; the join key is the caption --
        # the 2026 side lives in the constructors' ForgeTypeId strings)
        gw = collections.Counter()
        for d in (rst, rme):
            if d is None:
                continue
            for cls in ("ParamElemExternal", "ParamElemProject",
                        "ParamElemElectricalLoadClassification"):
                for e in d.ids_of_class(cls, host_only=True):
                    v = d.value(e) or {}
                    pd = ((v.get("m_pParamDef") or {}).get("value") or {})
                    if "m_groupElemId" in pd:
                        gw[pd.get("m_groupElemId")] += 1
        out["param_group_witnesses"] = {str(k): c for k, c in sorted(gw.items())}
        assert set(PARAM_GROUP_ELEM_2023.values()) <= set(gw), \
            "mined group map cites unwitnessed ids"
    if verbose:
        print(f"   [defaults-2023] wire={len(out['wire_settings'])} specimens, "
              f"geomtables={sum(hits.values())}, loadclasses={len(out['load_classifications'])}, "
              f"group-witness-ids={len(out['param_group_witnesses'])}")
    return out


def mine_all(verbose: bool = True) -> dict:
    """Freeze EVERY 2023 miner artifact under experiments/genesis2023/miners."""
    os.makedirs(OUT_DIR, exist_ok=True)
    results = {}
    for path, derive in ((ENUM_2023_JSON, derive_builtin_category_enum_2023),
                         (PROFILE_2023_JSON, derive_builtin_style_profile_2023),
                         (PEN_2023_JSON, derive_pen_table_2023),
                         (PALETTE_2023_JSON, derive_palette_invariants_2023),
                         (DEFAULTS_2023_JSON, derive_defaults_2023)):
        if os.path.exists(path):
            with open(path) as fh:
                results[os.path.basename(path)] = json.load(fh)
            continue
        data = derive(verbose)
        with open(path, "w") as fh:
            json.dump(data, fh, indent=1)
        results[os.path.basename(path)] = data
    return results


def load_2023_catalog_constants(*, derive_if_missing: bool = True) -> Tuple[dict, dict]:
    """(enum, profile) for a 2023 catalog rung -- frozen JSON, derived on
    first use."""
    out = []
    for path, derive in ((ENUM_2023_JSON, derive_builtin_category_enum_2023),
                         (PROFILE_2023_JSON, derive_builtin_style_profile_2023)):
        if os.path.exists(path):
            with open(path) as fh:
                out.append(json.load(fh))
            continue
        if not derive_if_missing:
            raise FileNotFoundError(path)
        data = derive()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            json.dump(data, fh, indent=1)
        out.append(data)
    return out[0], out[1]


# ---------------------------------------------------------------------------
# specimen validation (byte-level, where the 2026 method verified byte-level)
# ---------------------------------------------------------------------------
def verify_specimen_byte_level(verbose: bool = True) -> dict:
    """The byte-level specimen gate against the 2023 rst sample:

    1. OUR adapted ``auto_cam_settings`` seq-102 body BYTE-EXACT vs specimen
       102842 (the 2026 constructor's byte-exact claim, re-proven on 2023
       through the port2024-delegated rename hooks).
    2. OUR adapted empty ``MEPNetworkTracker`` BYTE-EXACT vs specimen
       1468014 (through the map re-type hook).
    3. OUR ``pen_width_table`` LAYOUT byte-exact vs specimen 2 when the
       specimen's own vectors are re-fed (widths are values, not format).
    4. Specimen decode -> re-encode round-trip (byte-exact under the 2023
       codec inside id32) for one host specimen of EVERY class the
       constructor battery ports -- the 2023 encode stack is proven on real
       bodies, 32-bit ids included.
    """
    if not os.path.exists(RST_2023):
        return {"skipped": "quarantined 2023 samples not present"}
    dec, enc, s23 = _S23()
    doc = load_document_2023(RST_2023)
    from . import settings as st
    rep: Dict[str, Any] = {}
    with id32():
        def compare(name, elem_id, rec):
            r = doc.record(elem_id, 102)
            pr = adapt_record(rec)
            body = enc.encode_object(pr.class_id, pr.obj)
            ok = (r is not None and body == r.payload)
            rep[name] = {"elem_id": elem_id, "byte_exact": ok,
                         "ours": len(body), "specimen": len(r.payload) if r else None}
            if verbose:
                print(f"   [specimen] {name:<24} vs {elem_id}: byte_exact={ok} "
                      f"({len(body)} B)")
            return ok

        ok = True
        # 1. auto-cam: fresh home state is value-identical to the specimen
        ok &= compare("AutoCamSettingsElem", 102842, st.auto_cam_settings(elem_id=102842))
        # 2. the empty MEP network tracker
        ok &= compare("MEPNetworkTracker", 1468014,
                      st.tracker("MEPNetworkTracker", elem_id=1468014))
        # 3. pen table layout with the specimen's own vectors re-fed
        sp = doc.value(2) or {}
        t = ((sp.get("m_pPenWidthTable") or {}).get("value") or {})
        model_ft = {int(x["m_invertedScale"]): list(x["m_pens"])
                    for x in (t.get("m_modelPenInfo") or [])}
        persp_ft = list((t.get("m_perspectiveModelPenInfo") or {}).get("m_pens") or [])
        draft_ft = list((t.get("m_draftPenInfo") or {}).get("m_pens") or [])
        ok &= compare("PenWidthTableElem", 2,
                      st.pen_width_table(elem_id=2, model_pens_ft=model_ft,
                                         perspective_pens_ft=persp_ft,
                                         annotation_pens_ft=draft_ft))
        # 4. specimen re-encode round-trip per ported constructor class
        classes = ["BasicWallType", "FloorAttributes", "MaterialElem", "LinePatternElem",
                   "FillPatternElem", "RbsWireType", "RbsWireSettingsElem",
                   "RbsWireSizesElem", "NumberingSchema", "BrowserOrganization",
                   "StructSettingsElem", "KeynoteTable", "ReinforcementSettings",
                   "PenWidthTableElem", "AutoCamSettingsElem", "RbsDuctSettingsElem",
                   "MEPNetworkTracker", "RbsDistributionSysType", "GStyleElem",
                   "PropertySetElement", "DBViewDrafting", "ParamElemExternal",
                   "ElectricalLoadClassification"]
        rt: Dict[str, Any] = {}
        for cls in classes:
            ids = doc.ids_of_class(cls, host_only=True)
            if not ids:
                rt[cls] = "no-specimen"
                continue
            e = ids[0]
            r = doc.record(e, 102)
            got = dec.decode_record(r.class_id, r.payload)
            rt[cls] = {"elem_id": e, "clean": bool(got.clean),
                       "byte_exact": (bool(got.clean)
                                      and enc.encode_object(r.class_id, got.value) == r.payload)}
            ok &= (rt[cls]["clean"] and rt[cls]["byte_exact"])
            if verbose:
                print(f"   [roundtrip] {cls:<24} specimen {e}: clean={rt[cls]['clean']} "
                      f"byte_exact={rt[cls]['byte_exact']}")
    rep["specimen_roundtrips"] = rt
    rep["ok"] = bool(ok)
    return rep


# ---------------------------------------------------------------------------
# self-test battery: adapt + 2023 round-trip over representative constructors
# ---------------------------------------------------------------------------
def selftest(verbose: bool = True) -> dict:
    """Build a battery of 2026 constructor records, adapt each to 2023, and
    round-trip every body under the 2023 codec; then run the refusal
    battery and the specimen gate."""
    from . import settings as st
    from . import types as T
    from .residue_b import BUILTIN_NUMBERING_SCHEMES, builtin_numbering_schema
    ids = T.IdSource(9_000_000)
    battery: List[Any] = [
        T.new_wall_type("P23 Wall", [("structure", 200, INVALID)], ids=ids),
        T.new_material("P23 Concrete", (120, 120, 120), ids=ids),
        T.new_line_pattern("P23 Dash", [("dash", 3.175), ("space", 1.5875)], ids=ids),
        T.new_fill_pattern("P23 Solid", [], ids=ids),
        T.new_floor_type("P23 Floor", [("structure", 150, INVALID)], ids=ids),
        T.new_wire_type("P23 THWN", ids=ids),
        T.new_distribution_system("P23 480/277", ids=ids),
        builtin_numbering_schema(BUILTIN_NUMBERING_SCHEMES[0], ids=ids),
    ]
    battery += [
        st.pen_width_table(ids=ids),
        st.browser_organization("all", ids=ids),
        st.struct_settings(ids=ids),
        st.keynote_table(ids=ids),
        st.wire_settings(ids=ids),
        st.reinforcement_settings(ids=ids),
        st.auto_cam_settings(ids=ids),
        st.duct_settings(ids=ids),
        st.tracker("MEPNetworkTracker", ids=ids),
    ]
    rows = []
    ok = True
    for rec in battery:
        try:
            pr = adapt_record(rec)
            v = verify_ported(pr)
            rows.append({"class": pr.class_name, "elem_id": pr.elem_id,
                         "ok": v["ok"],
                         "seq102": {k: v[102][k] for k in ("clean", "byte_exact", "bytes")},
                         "notes": pr.notes[:4]})
            ok = ok and v["ok"]
            if verbose:
                s = v[102]
                print(f"   {pr.class_name:<28} seq102 {s['bytes']:>6} B clean={s['clean']} "
                      f"byte_exact={s['byte_exact']} all-ok={v['ok']}")
        except Missing2023 as ex:
            rows.append({"class": rec.class_name, "elem_id": rec.elem_id,
                         "missing_2023": str(ex)})
            if verbose:
                print(f"   {rec.class_name:<28} MISSING-2023 (see "
                      "MISSING_2023_CONSTRUCTED)")
    # the refusal battery: constructors whose classes 2023 lacks must raise
    refusals = []
    for build in (lambda: T.new_conductor_size("12", 2.05, ids=ids),
                  lambda: st.tracker("SheetsInSheetCollectionTracker", ids=ids),
                  lambda: st.tracker("MEPNetworkDataElem", ids=ids),
                  lambda: st.tracker("STEPExportSettings", ids=ids),
                  lambda: st.sse_point_visibility_settings(ids=ids)):
        try:
            rec = build()
        except Exception as ex:                        # pragma: no cover
            refusals.append({"build_error": str(ex)})
            continue
        try:
            adapt_record(rec)
            refusals.append({"class": rec.class_name, "refused": False})
            ok = False
        except Missing2023:
            refusals.append({"class": rec.class_name, "refused": True})
            if verbose:
                print(f"   {rec.class_name:<28} REFUSED (Missing2023) -- correct")
    spec = verify_specimen_byte_level(verbose=verbose)
    if "skipped" not in spec:
        ok = ok and spec["ok"]
    return {"ok": ok, "records": rows, "refusals": refusals, "specimen": spec}


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--verify", action="store_true",
                    help="derive + freeze the CONFIRMED portability table")
    ap.add_argument("--mine", action="store_true",
                    help="derive + freeze the 2023 miners (enum / profile / pen / "
                         "palette / defaults)")
    ap.add_argument("--selftest", action="store_true",
                    help="adapt + 2023 round-trip + refusal + specimen battery")
    args = ap.parse_args(argv)
    rc = 0
    if args.verify or not (args.mine or args.selftest):
        t = portability_table(write=True)
        print(f"[portability] {t['universe']} -> {t['counts']}  "
              f"-> {os.path.relpath(PORTABILITY_JSON, ROOT)}")
        nm = t["non_monotonic_findings"]
        print(f"[four-way] reorder-only classes: {len(nm['reorder_only_classes'])}; "
              f"deltas differing from 2024: {nm['deltas_that_differ_from_2024']}")
    if args.mine:
        res = mine_all()
        enum = res[os.path.basename(ENUM_2023_JSON)]
        prof = res[os.path.basename(PROFILE_2023_JSON)]
        print(f"[mine] enum-2023 {enum['count']} categories ({enum['cuttable']} cuttable) "
              f"-> {os.path.relpath(ENUM_2023_JSON, ROOT)}")
        print(f"[mine] profile-2023 {prof['count']} keys over {prof['rows_analysed']} rows "
              f"-> {os.path.relpath(PROFILE_2023_JSON, ROOT)}")
        pen = res[os.path.basename(PEN_2023_JSON)]
        print(f"[mine] pen-2023 scales {pen['scale_breakpoints']} x {pen['pens_per_vector']} "
              f"pens -> {os.path.relpath(PEN_2023_JSON, ROOT)}")
        pal = res[os.path.basename(PALETTE_2023_JSON)]
        print(f"[mine] palette-2023 {pal['property_sets']} sets, laws_hold="
              f"{pal['laws_hold']} -> {os.path.relpath(PALETTE_2023_JSON, ROOT)}")
        dfl = res[os.path.basename(DEFAULTS_2023_JSON)]
        print(f"[mine] defaults-2023 census -> {os.path.relpath(DEFAULTS_2023_JSON, ROOT)}")
    if args.selftest:
        rep = selftest()
        print(f"[selftest] ok={rep['ok']} over {len(rep['records'])} records "
              f"+ {len(rep['refusals'])} refusals")
        rc = 0 if rep["ok"] else 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
