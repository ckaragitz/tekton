"""regadd.py -- THE REGISTRATION-CONFORMANT ADD / SUBSTITUTE PATH (genesis-addfix).

WHY THIS MODULE EXISTS.  The genesis line's night of viewer verdicts
(docs/inbox/genesis-audit.md, ORCHESTRATOR VERDICTS #9..#11) ended on:
X0 (Autodesk's OWN pen table, exact bytes, re-inserted through our OLD add
path -- new id 1,500,000, ElemTable row (ep,ep,ep), records appended at the
unit end) FAILS 'Revit-DocumentCorruption'; C0 (Autodesk's own catalog row
verbatim through the same path) FAILS.  This stream's own forensic diff
(experiments/genesis/regadd/*.diff.json + docs/inbox/genesis-addfix.md) then
established that X_pen / X_cat -- the fixer's IN-PLACE payload probes,
which do NOT use the add path at all -- ALSO failed, and that X_pen differs
from the reader-PASSING K1 in exactly ONE record (element 2's pen-table
object doubles).  Every writer module is unchanged since before the last
CERTIFIED file, so the ~00:25 batch (X0, X1u, C0, X_pen, X_cat, ALL fail, NO
positive control uploaded) cannot cleanly separate 'the add path is broken'
from 'our content is rejected' from 'the batch itself failed'.  This module
therefore does two things:

  1. It implements BOTH operations on the mechanics of a KNOWN-PASSING
     writer -- ``rvt.reduce`` (the re-blocker behind K3 / K4 / KD1 / R4s /
     R5 / R9, all viewer-CERTIFIED) -- so a probe's ONLY variable is its
     CONTENT / REGISTRATION, never the block mechanics; and

  2. It ASSERTS the byte-level truth of every emitted file against its
     parent with :func:`stream_diff_report` (per stream, per record, per
     block, per ElemTable row, per ADocument leaf) so no verdict is read
     against an unmeasured delta.

THE TWO OPERATIONS.

* :func:`substitute_element` -- delete-and-add that PRESERVES EVERYTHING but
  the object bytes: same id, same ElemTable row (byte-identical stream),
  same record POSITION in each of the three seq streams, same block
  partition (asserted when the record length is unchanged), Global/Latest
  and every non-partition stream byte-identical to the parent.  The
  operation the substitution ladder actually needs (pure content swap, zero
  registration motion).  ``null=True`` swaps an element for ITS OWN exact
  bytes: the emitted Partitions stream must then be BYTE-IDENTICAL to the
  parent's -- proving the path is zero-motion AND producing a file that is
  content-identical to a known-passing base = the batch's positive control.

* :func:`add_element_like_original` -- the FIXED add path for a NEW element,
  registering it the way a loadable file registers the same class:
    (a) id  -- an explicit ``target_id`` (in-place-style re-add / a chosen
        low id for a birth-vintage singleton) or watermark+1;
    (b) ElemTable row -- creation / modified / user-modified episodes per
        the class's corpus VINTAGE rule (:data:`REG_RULES`; the document-
        birth singletons AllProjectPhases / DBViewProject / the project
        PenWidthTableElem are creation-episode 0 with id < 5,000 in 7/7
        files [MEASURED, m8]; the OLD path stamped the parent's MAX episode
        into all three fields = defect A1) and the class's OWNER (defect:
        the old path wrote owner INVALID where the corpus has an owner --
        FontElem is owned by its annotation-attributes type in 5,982/5,982,
        a Viewer / DBDrawing by its view in 507/507 / 831/831 [objlint]);
        owned children get their rows' owner pointed at the new element;
    (c) record POSITION -- the OLD path appended at the unit end.  MEASURED
        FACT (m1/m2/m7, all six samples + K1): the unit-0 record order is
        NOT id-ascending and NOT episode-ordered (42..222 descents per file,
        identical order in seq 101/102/103); it is Revit's internal storage
        order, which reductions preserve.  Global order is provably NOT a
        hard audit: our appended user-content elements are CERTIFIED (V20..
        V29, T_conduit_types).  What IS reproducible: the document-birth
        low-id run keeps consecutive ids adjacent (K1/rstbasic: ..., 1
        AllProjectPhases, 2 PenWidthTable, 3..6 FillPattern, ...; dach: 3, 6,
        11, 12..).  ``place='auto'`` therefore inserts INTO THE ID HOLE
        between the stream-adjacent id neighbours when they bracket our id
        (reproducing the birth run byte-for-byte), else 'after' the id
        predecessor when it sits in an ascending run, else appends.
        'append' / 'after:<id>' / 'index:<n>' are explicit.  Every choice
        is REPORTED with its neighbourhood.
    (d) ElementHeader -- the caller's header, validated against the class
        rule (m_parents lists per objlint; the pen table's are empty);
    (e) ADocument registries -- ``register`` (settings.apply_adoc_registry,
        the singletons stream's proven surfaces) and / or ``latest_remap``
        (schema-typed old->new leaf remap via the arbiter's typed walker;
        never a byte scan), re-encoded byte-exactly; when neither is asked
        Global/Latest is copied byte-identical.

Both operations REPORT (JSON-able) and never edit save-history streams
(the minimal-commit convention every certified writer uses).

WHAT THE CORPUS RULES ENCODE (:data:`REG_RULES`, measured this session
over all six samples + K1, docs/inbox/genesis-addfix.md sec. M8):
  * per-class vintage: creation_ep policy ('birth' => 0 in every file;
    'any' => in-set at any episode), id band ('<5k' for the three universal
    birth singletons; unconstrained for the built-in GStyle rows -- 9,849
    rows span every band and 83 % are NOT birth), user_modified never
    'never' (0xFFFFFFFF) on any project singleton (7/7);
  * per-class ownership: owner class or None; owned-children classes.
  A rule that the corpus does NOT constrain is recorded as ``None`` -- and
  that is itself a finding: for the built-in GStyle catalog rows EVERY
  property the old add path wrote is IN-CORPUS (see the record: C0's
  failure has no out-of-corpus registration to blame).

Territory: this module + tests/test_regadd.py + experiments/genesis/regadd/*
+ docs/writer/add-path.md + docs/inbox/genesis-addfix.md.  Every dependency
(rvt.reduce / stream_encoders / streams_edit / encode / objects / adocument
/ container / ecc / cfb_writer / genesis.settings) is IMPORTED, never
edited.  Python: ``.venv/bin/python`` from the repo root.

    python -m rvt.regadd --demo            # build the XR_null / XR0 pair + diff
"""
from __future__ import annotations

import collections
import copy
import dataclasses
import hashlib
import json
import os
import struct
import sys
import zlib
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from . import ecc
from . import encode as E
from . import reduce as _reduce
from .cfb_writer import write_cfb
from .container import open_rvt
from .objects import ObjectDecoder, iter_records
from .partitions import StreamWalker
from .reduce import (BLOCK_TARGET, PART_HDR_COUNT_OFF, PART_HDR_LEN, SEQS, Rec,
                     reblock, split_records, unframe_exact)
from .roundtrip import read_entries
from .stream_encoders import decode_elemtable, encode_elemtable, global_prefix
from .streams_edit import INVALID_ID, NO_EPISODE, elemtable_add_element
from .writer import gzip_member

# encode_record / record_bytes / verify_reduced are read via ``E.`` /
# ``_reduce.`` at call time: records32.ids32() rebinds them BY NAME there
# (#467; iter_records + the ElemTable codec above may stay from-imports --
# ids32's patch table lists this module as one of their holders)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INVALID = -1
LATEST_STREAM = "Global/Latest"
ELEMTABLE_STREAM = "Global/ElemTable"


def _hdr_len(seq: int) -> int:
    """Raw record header length before the body (id[8] [+stamp[4]] +psize[4])."""
    return 12 if seq == 101 else 16


# ===========================================================================
# 1. THE CORPUS REGISTRATION RULES  (measured, all six samples + K1)
# ===========================================================================
#: Per-class registration rules for the ElemTable row + header + registry.
#:
#: * ``creation_ep``: 'birth' -> creation episode 0 in EVERY file that has the
#:   class (a document-birth element); 'any' -> the corpus shows the class at
#:   many episodes (no vintage audit is possible); an int -> a fixed value.
#: * ``id_band``: the ElementId magnitude the corpus keeps the class in
#:   ('<5k' = below 5,000 in 7/7 files) or None (unconstrained).
#: * ``modified_ep``: 'as_created' (== creation) or 'any'; ``usermod``:
#:   'episode' (a real episode, NEVER the 0xFFFFFFFF 'never' sentinel -- true
#:   of every project singleton, 7/7) or 'never'.
#: * ``owner``: the class of the ElemTable owner ('m_OwningElementId') or
#:   None (un-owned); ``owns``: classes whose rows this element must own.
#: * ``support``: the measurement behind the rule (files / specimens).
#: Rules NOT listed = no constraint mined (use the caller's values).
REG_RULES: Dict[str, dict] = {
    # ---- the universal document-birth singletons: episode 0, id < 5k, 7/7 --
    "AllProjectPhases": {
        "creation_ep": "birth", "id_band": "<5k", "modified_ep": "any",
        "usermod": "episode", "owner": None, "owns": [],
        "support": "7/7 files ce==0, id 1 in every file (m8)"},
    "DBViewProject": {
        "creation_ep": "birth", "id_band": "<5k", "modified_ep": "any",
        "usermod": "episode", "owner": None,
        "owns": ["SunAndShadowSettings", "DBDrawing", "Viewer"],   # objlint OWNED_CHILD
        "support": "7/7 files ce==0, id 230 in every file (m8)"},
    "PenWidthTableElem": {          # the PROJECT pen table (m_famId == -1)
        "creation_ep": "birth", "id_band": "<5k", "modified_ep": "any",
        "usermod": "episode", "owner": None, "owns": [],
        "support": "7/7 project pen tables ce==0, id 2/3/11 (m8); the 58 "
                   "family-scoped copies are owned by @Family, late episodes"},
    # ---- born-later / template-upgrade singletons: NO universal vintage ----
    "KeynoteTable": {"creation_ep": "any", "id_band": None, "modified_ep": "any",
                     "usermod": "episode", "owner": None, "owns": [],
                     "support": "ce==0 in only 1/7 files; bands <5k..<500k (m8)"},
    "KeynotingSystem": {"creation_ep": "any", "id_band": None, "usermod": "episode",
                        "owner": None, "owns": [], "support": "1/7 ce==0 (m8)"},
    "UnitsElem": {"creation_ep": "any", "id_band": None, "usermod": "episode",
                  "owner": None, "owns": [], "support": "1/7 ce==0, bands <5k/<50k (m8)"},
    "ProjectInfo": {"creation_ep": "any", "id_band": None, "usermod": "episode",
                    "owner": None, "owns": [], "support": "1/7 ce==0 (m8)"},
    "TrueNorth": {"creation_ep": "any", "id_band": None, "usermod": "episode",
                  "owner": None, "owns": [], "support": "2/7 ce==0 (m8)"},
    "StructSettingsElem": {"creation_ep": "any", "id_band": None, "usermod": "episode",
                           "owner": None, "owns": [], "support": "1/7 ce==0 (m8)"},
    "RbsDbViewSystemNavigator": {"creation_ep": "any", "id_band": None, "usermod": "episode",
                                 "owner": None, "owns": ["Viewer", "DBDrawing"],
                                 "support": "owns {Viewer, DBDrawing} 6/6 (objlint)"},
    "BrowserOrganization": {"creation_ep": "any", "id_band": None, "usermod": "episode",
                            "owner": None, "owns": [],
                            "support": "3/79 ce==0; bands <5k..<5M (m8)"},
    "ConstructionSetProject": {"creation_ep": "any", "id_band": None, "usermod": "episode",
                               "owner": None, "owns": [], "support": "0/6 ce==0 (m8)"},
    "ReconcileBrowserSettingsElem": {"creation_ep": "any", "id_band": None,
                                     "usermod": "episode", "owner": None, "owns": [],
                                     "support": "0/7 ce==0 (m8)"},
    "AutoJoinTracker": {"creation_ep": "any", "id_band": None, "usermod": "episode",
                        "owner": None, "owns": [], "support": "0/7 ce==0 (m8)"},
    "WallJoinDefaultSetting": {"creation_ep": "any", "id_band": None, "usermod": "episode",
                               "owner": None, "owns": [], "support": "0/7 ce==0 (m8)"},
    "InitialViewSettings": {"creation_ep": "any", "id_band": None, "usermod": "episode",
                            "owner": None, "owns": [], "support": "0/7 ce==0 (m8)"},
    "ElectricalSetting": {"creation_ep": "any", "id_band": None, "usermod": "episode",
                          "owner": None, "owns": [], "support": "0/7 ce==0 (m8)"},
    # ---- ownership webs (the objlint ADD-PATH surface) --------------------
    "TextNoteAttributes": {"creation_ep": "any", "id_band": None, "usermod": "episode",
                           "owner": None, "owns": ["CategoryElem", "FontElem"],
                           "support": "project text types un-owned (68/68); each OWNS "
                                      "{CategoryElem, FontElem} (2,026/2,026 scoped)"},
    "LevelAttributes": {"creation_ep": "any", "id_band": None, "usermod": "episode",
                        "owner": None, "owns": ["CategoryElem", "FontElem"],
                        "support": "owns {CategoryElem, FontElem} 13/13 (objlint)"},
    "FontElem": {"creation_ep": "any", "id_band": None, "usermod": "any",
                 "owner": "annotation-attributes type", "owns": [],
                 "support": "owned in 5,982/5,982 (objlint); the ~1,084 project fonts "
                            "are owned by attribute types too (m8)"},
    "CategoryElem": {"creation_ep": "any", "id_band": None, "usermod": "any",
                     "owner": "attributes type (sub-categories) / None (built-in)",
                     "owns": ["GStyleElem"],
                     "support": "sub-category CategoryElem owns its GStyle (8,225/8,227) and "
                                "is owned by an attributes type (7,542/8,227) (objlint)"},
    "Viewer": {"creation_ep": "any", "id_band": None, "usermod": "episode",
               "owner": "view (DBView*)", "owns": [],
               "support": "owned 507/507 (objlint), 530 project rows (m8)"},
    "Viewport": {"creation_ep": "any", "id_band": None, "usermod": "any",
                 "owner": "DBDrawing", "owns": [],
                 "support": "owner is a DBDrawing 1,028/1,028 (objlint)"},
    "DBDrawing": {"creation_ep": "any", "id_band": None, "usermod": "any",
                  "owner": "view (DBView*)", "owns": ["Viewport"],
                  "support": "owned 831/831 (objlint)"},
    "RevisionNumberingSequence": {"creation_ep": "any", "id_band": None, "usermod": "episode",
                                  "owner": "AllProjectRevisions", "owns": [],
                                  "support": "owned by AllProjectRevisions 14/14 (m8/objlint)"},
    "AllProjectRevisions": {"creation_ep": "any", "id_band": None, "usermod": "episode",
                            "owner": None, "owns": ["RevisionNumberingSequence"],
                            "support": "owns its 2 sequences (objlint)"},
    # ---- the catalog rows: NO vintage / ownership constraint ---------------
    "GStyleElem": {"creation_ep": "any", "id_band": None, "modified_ep": "any",
                   "usermod": "any", "owner": None, "owns": [],
                   "support": "9,849 built-in rows: 1,697 birth / 8,152 later; every id "
                              "band; un-owned (m8) -- registration UNCONSTRAINED"},
    "FillPatternElem": {"creation_ep": "any", "id_band": None, "usermod": "any",
                        "owner": None, "owns": [], "support": "155/766 birth (m8)"},
    "LinePatternElem": {"creation_ep": "any", "id_band": None, "usermod": "any",
                        "owner": None, "owns": [], "support": "91/635 birth (m8)"},
    "MaterialElem": {"creation_ep": "any", "id_band": None, "usermod": "any",
                     "owner": None, "owns": [], "support": "110/1,161 birth (m8)"},
}

#: id-band upper bounds
ID_BANDS = {"<5k": 5_000, "<50k": 50_000, "<500k": 500_000, "<5M": 5_000_000}


def id_band(eid: int) -> str:
    """The magnitude band of an ElementId (matches rvt.objlint.id_band)."""
    n = abs(int(eid))
    for name, thr in ID_BANDS.items():
        if n < thr:
            return name
    return ">=5M"


def reg_rule(class_name: str, *, cohort: str = "project") -> dict:
    """The registration rule for ``class_name`` ({} when the corpus imposes
    no measured constraint).  ``cohort`` matters only for PenWidthTableElem
    (the 'project' table vs family-'scoped' copies)."""
    if class_name == "PenWidthTableElem" and cohort != "project":
        return {"creation_ep": "any", "id_band": None, "owner": "Family",
                "owns": [], "support": "58 family-scoped copies owned by @Family (m8)"}
    return dict(REG_RULES.get(class_name) or {})


def vintage_for(class_name: str, *, parent_max_ep: int, cohort: str = "project",
                creation_ep: Optional[int] = None, modified_ep: Optional[int] = None,
                user_modified_ep: Optional[int] = None) -> Tuple[int, int, int]:
    """Choose (creation_ep, modified_ep, user_modified_ep) for a NEW element
    of ``class_name`` added to a document whose newest episode is
    ``parent_max_ep``.  Explicit arguments win.  Rule 'birth' => creation 0
    (the corpus's 7/7 fact for the birth singletons); everything else =>
    the parent's current episode (the corpus places later-born singletons
    at their own creation save).  ``user_modified`` is ALWAYS a real
    episode (never the 0xFFFFFFFF 'never' sentinel) for a project singleton
    -- 7/7 in every measured class (m8) -- so it defaults to modified_ep."""
    rule = reg_rule(class_name, cohort=cohort)
    if creation_ep is None:
        creation_ep = 0 if rule.get("creation_ep") == "birth" else int(parent_max_ep)
    if modified_ep is None:
        # a NEW element's last modification is its creation save; for a
        # birth-vintage row inserted into an EXISTING document the corpus
        # rows carry a later modification (the pen table was edited later),
        # which we cannot know -- creation is the honest default and matches
        # a freshly-created element.
        modified_ep = int(creation_ep)
    if user_modified_ep is None:
        user_modified_ep = (int(modified_ep) if rule.get("usermod", "episode") == "episode"
                            else NO_EPISODE)
    return int(creation_ep), int(modified_ep), int(user_modified_ep)


def check_registration(class_name: str, *, elem_id: int, creation_ep: int,
                       owner_class: Optional[str], cohort: str = "project") -> List[str]:
    """Lint a proposed registration against :data:`REG_RULES`; returns the
    list of violations (empty = conformant).  The two KNOWN defects of the
    old add path are exactly these checks: owner INVALID where the corpus has
    an owner; a late episode where the corpus says birth."""
    rule = reg_rule(class_name, cohort=cohort)
    out: List[str] = []
    if not rule:
        return out
    if rule.get("creation_ep") == "birth" and int(creation_ep) != 0:
        out.append(f"{class_name}: corpus says creation episode 0 in EVERY file "
                   f"({rule['support']}); proposed {creation_ep}")
    band = rule.get("id_band")
    if band and abs(int(elem_id)) >= ID_BANDS[band]:
        out.append(f"{class_name}: corpus keeps this class's id {band} "
                   f"({rule['support']}); proposed id {elem_id} ({id_band(elem_id)})")
    want_owner = rule.get("owner")
    if want_owner and owner_class in (None, ""):
        out.append(f"{class_name}: corpus rows are OWNED by {want_owner} "
                   f"({rule['support']}); proposed row is un-owned")
    if want_owner is None and rule and owner_class not in (None, ""):
        out.append(f"{class_name}: corpus rows are un-owned; proposed owner {owner_class}")
    return out


# ===========================================================================
# 2. THE EDIT IMAGE  (a parent file loaded for record-level surgery)
# ===========================================================================

@dataclasses.dataclass
class SeqRun:
    """The unit-0 record stream of one seq: framed records IN ORDER (each a
    ``reduce.Rec``: seq, elem_id, size, data) + a fast id -> index map."""
    seq: int
    recs: List[Rec]

    @property
    def ids(self) -> List[int]:
        return [r.elem_id for r in self.recs if r.elem_id >= 0]

    def index_of(self, eid: int) -> int:
        for i, r in enumerate(self.recs):
            if r.elem_id == eid:
                return i
        raise KeyError(f"seq {self.seq}: element {eid} not in unit 0")


class EditImage:
    """A parent ``.rvt`` opened for record-level surgery on save-unit 0.

    Holds: the container entries, the primary partition stream's logical
    bytes, its unit-0 records per seq (in stream order, as ``reduce.Rec``),
    the unit-0 span (header .. footer offset), the ElemTable model and its
    ORIGINAL logical bytes (so an untouched table is copied byte-identical),
    and lazily the ADocument tree.  ``emit()`` re-blocks unit 0 with
    ``reduce.reblock`` (the CERTIFIED re-blocker) and writes the container.
    """

    def __init__(self, path: str):
        self.path = path
        self.entries = read_entries(path)
        with open_rvt(path) as doc:
            parts = doc.partition_streams()
            if len(parts) != 1:
                raise NotImplementedError(f"{path}: expected one partition stream, got {parts}")
            self.pname = parts[0]
            # the EXACT logical stream (pad-count decoded): the depaged
            # ``logical()`` leaks the final page's ECC pad junk into the tail
            # (61 bytes on K1) -- reader-tolerated but fatal to byte-identity,
            # and every writer that copies logical[footer:] re-frames it as
            # content.  ``unframe_exact`` is the fix (falls back to depage).
            raw = doc.raw(self.pname)
            try:
                self.logical = unframe_exact(raw)
                self.notes_logical = "exact (pad-count decoded)"
            except Exception:                                   # pragma: no cover
                self.logical = doc.logical(self.pname)
                self.notes_logical = "depage (junk tail possible)"
            self.et_logical = doc.logical(ELEMTABLE_STREAM)
            self.et_payload = doc.inflate(ELEMTABLE_STREAM)
            self.latest_payload = doc.inflate(LATEST_STREAM, 0)
        w = StreamWalker(self.logical, inflate=True, keep_data=True)
        if w.errors:
            raise RuntimeError(f"{path}: walker errors on source: {w.errors[:3]}")
        blocks = sorted(w.blocks, key=lambda b: b.hdr_offset)
        u0 = [b for b in blocks if b.unit == 0]
        if not u0 or blocks[0].hdr_offset != PART_HDR_LEN:
            raise RuntimeError(f"{path}: unexpected unit-0 layout (first block not at 18)")
        self.u0_footer = w.units[0].footer_offset
        if self.u0_footer is None:
            raise RuntimeError(f"{path}: unit 0 has no footer")
        self.blocks = blocks
        self.u0_blocks = u0
        self.runs: Dict[int, SeqRun] = {}
        for seq in SEQS:
            seg = b"".join(b.data for b in u0 if b.seq == seq)
            if not seg:
                raise RuntimeError(f"{path}: unit 0 has no seq-{seq} data")
            self.runs[seq] = SeqRun(seq, split_records(seg, seq))
        self.et_model = decode_elemtable(self.et_payload)
        self.et_dirty = False
        self._latest_tree = None
        self._latest_dirty = False
        self._new_latest_payload: Optional[bytes] = None
        self._dec: Optional[ObjectDecoder] = None
        self.notes: List[str] = []

    # -- lookups -----------------------------------------------------------
    @property
    def decoder(self) -> ObjectDecoder:
        if self._dec is None:
            self._dec = ObjectDecoder()
        return self._dec

    @property
    def watermark(self) -> int:
        return int(self.et_model["footer"]["last_id"])

    @property
    def max_episode(self) -> int:
        return max((int(r[2]) for r in self.et_model["records"]), default=0)

    def elemtable_row(self, eid: int) -> Optional[dict]:
        for r in self.et_model["records"]:
            if int(r[4]) == int(eid):
                own = r[5]
                return {"original_id": int(r[0]), "creation_ep": int(r[1]),
                        "modified_ep": int(r[2]), "user_modified_ep": int(r[3]),
                        "elem_id": int(r[4]),
                        "owner_id": (-1 if own in (INVALID_ID, INVALID) else int(own)),
                        "partition_id": int(r[6]) if len(r) > 6 else 0}
        return None

    def has_element(self, eid: int) -> bool:
        return self.elemtable_row(eid) is not None

    def records_of(self, eid: int) -> Dict[int, Rec]:
        """{seq: Rec} for element ``eid`` (only the seqs it appears in)."""
        out = {}
        for seq, run in self.runs.items():
            for r in run.recs:
                if r.elem_id == eid:
                    out[seq] = r
                    break
        return out

    def class_of(self, eid: int) -> Optional[str]:
        recs = self.records_of(eid)
        r = recs.get(102)
        if r is None:
            return None
        cid = struct.unpack_from("<H", r.data, _hdr_len(102))[0]
        return self.decoder.class_name(cid)

    def decode(self, rec: Rec):
        """Schema-decode a record (seq inferred from ``rec.seq``)."""
        hl = _hdr_len(rec.seq)
        cid = struct.unpack_from("<H", rec.data, hl)[0]
        body = rec.data[hl + 2: hl + rec.size]
        return self.decoder.decode_record(cid, body)

    # -- the ADocument (lazy) ----------------------------------------------
    @property
    def latest_tree(self) -> dict:
        if self._latest_tree is None:
            from . import adocument as adoc
            a = adoc.decode_latest(self.latest_payload)
            if not a.clean:
                raise RuntimeError(f"{self.path}: ADocument decode not clean: {a.errors[:1]}")
            self._latest_tree = a.value
        return self._latest_tree

    def set_latest_tree(self, tree: dict) -> None:
        """Install an edited ADocument tree; re-encoded byte-exactly on emit
        (round-trip proven or emit refuses)."""
        from . import adocument as adoc
        payload = adoc.encode_latest(tree)
        back = adoc.decode_latest(payload)
        if not (back.clean and back.value == tree):
            raise RuntimeError("edited ADocument does not round-trip byte-exactly "
                               "-- refusing to emit")
        self._latest_tree = tree
        self._new_latest_payload = payload
        self._latest_dirty = True

    # -- record edits ------------------------------------------------------
    def replace_record(self, seq: int, eid: int, framed: bytes) -> Rec:
        """Replace element ``eid``'s seq-``seq`` record IN PLACE (same position)."""
        run = self.runs[seq]
        i = run.index_of(eid)
        rec = _rec_from_framed(seq, framed)
        if rec.elem_id != eid:
            raise ValueError(f"seq {seq}: replacement record id {rec.elem_id} != {eid}")
        run.recs[i] = rec
        return rec

    def insert_records(self, framed_by_seq: Dict[int, bytes], index_by_seq: Dict[int, int]) -> None:
        """Insert one element's records at the given per-seq indices."""
        for seq, fb in framed_by_seq.items():
            run = self.runs[seq]
            i = int(index_by_seq[seq])
            i = max(0, min(i, len(run.recs) - 1))       # never after the sentinel
            run.recs.insert(i, _rec_from_framed(seq, fb))

    def delete_element_records(self, eid: int) -> Dict[int, int]:
        """Remove element ``eid``'s records from all three seqs; returns the
        positions they occupied (for re-insertion 'in place')."""
        pos = {}
        for seq, run in self.runs.items():
            for i, r in enumerate(run.recs):
                if r.elem_id == eid:
                    pos[seq] = i
                    del run.recs[i]
                    break
        return pos

    # -- ElemTable edits -----------------------------------------------------
    def add_elemtable_row(self, *, elem_id: int, creation_ep: int, modified_ep: int,
                          user_modified_ep: int, owner_id: int = -1,
                          original_id: Optional[int] = None, partition_id: int = 0) -> int:
        own = INVALID_ID if owner_id in (None, -1, INVALID_ID) else int(owner_id)
        ue = NO_EPISODE if user_modified_ep in (None, -1, NO_EPISODE) else int(user_modified_ep)
        idx = elemtable_add_element(self.et_model, int(elem_id), creation_ep=int(creation_ep),
                                    modified_ep=int(modified_ep), user_modified_ep=ue,
                                    original_id=(int(original_id) if original_id is not None
                                                 else int(elem_id)),
                                    owner_id=own, partition_id=int(partition_id))
        self.et_dirty = True
        return idx

    def remove_elemtable_row(self, eid: int) -> Optional[dict]:
        row = self.elemtable_row(eid)
        if row is None:
            return None
        self.et_model["records"] = [r for r in self.et_model["records"]
                                    if int(r[4]) != int(eid)]
        self.et_dirty = True
        return row

    def restore_elemtable_row(self, row: dict) -> int:
        """Re-insert a PREVIOUSLY REMOVED row verbatim (its own episodes /
        owner / original id) -- the in-place / null path keeps the row."""
        return self.add_elemtable_row(
            elem_id=row["elem_id"], creation_ep=row["creation_ep"],
            modified_ep=row["modified_ep"], user_modified_ep=row["user_modified_ep"],
            owner_id=row["owner_id"], original_id=row["original_id"],
            partition_id=row.get("partition_id", 0))

    def set_row_owner(self, eid: int, owner_id: int) -> bool:
        """Point element ``eid``'s ElemTable row's owner at ``owner_id``
        (the owned-children wiring of the fixed add path)."""
        recs = self.et_model["records"]
        for i, r in enumerate(recs):
            if int(r[4]) == int(eid):
                own = INVALID_ID if owner_id in (None, -1, INVALID_ID) else int(owner_id)
                recs[i] = (r[0], r[1], r[2], r[3], r[4], own, r[6] if len(r) > 6 else 0)
                self.et_dirty = True
                return True
        return False

    # -- emission --------------------------------------------------------------
    def emit(self, out_path: str, *, target: int = BLOCK_TARGET) -> dict:
        """Re-block unit 0 with ``reduce.reblock`` (the certified mechanics),
        re-encode the ElemTable ONLY IF EDITED (else copy its bytes),
        install the edited Global/Latest ONLY IF EDITED, re-frame, write."""
        new_streams: Dict[str, bytes] = {}
        # 1. Partitions/<N>
        new_u0 = bytearray()
        blocks_per_seq: Dict[int, int] = {}
        for seq in SEQS:
            run = self.runs[seq]
            _assert_sentinel_last(run)
            nbs = reblock(run.recs, seq, target=target)
            blocks_per_seq[seq] = len(nbs)
            for nb in nbs:
                new_u0 += nb.frame()
        out = bytearray(self.logical[:PART_HDR_LEN]) + new_u0 + self.logical[self.u0_footer:]
        struct.pack_into("<I", out, PART_HDR_COUNT_OFF, len(self.et_model["records"]))
        w2 = StreamWalker(bytes(out), inflate=False, keep_data=False)
        if w2.errors:
            raise RuntimeError(f"walker errors after re-block: {w2.errors[:3]}")
        part_logical = bytes(out[:w2.end_offset + len(w2.end_record)])
        new_streams[self.pname] = ecc.frame_stream(part_logical)
        # 2. Global/ElemTable -- byte-identical when untouched
        if self.et_dirty:
            et_logical = global_prefix(ELEMTABLE_STREAM) + gzip_member(
                encode_elemtable(self.et_model), level=3)
            new_streams[ELEMTABLE_STREAM] = ecc.frame_stream(et_logical)
        # 3. Global/Latest -- byte-identical when untouched
        if self._latest_dirty and self._new_latest_payload is not None:
            from .stream_encoders import wrap_global_stream
            latest_logical = wrap_global_stream(LATEST_STREAM, self._new_latest_payload)
            new_streams[LATEST_STREAM] = ecc.frame_stream(latest_logical)
        out_entries = [dataclasses.replace(e, data=new_streams[e.path])
                       if (e.entry_type == "stream" and e.path in new_streams) else e
                       for e in self.entries]
        write_cfb(out_path, out_entries)
        return {"out": out_path, "partition": self.pname,
                "unit0_blocks_after": blocks_per_seq,
                "elemtable_count": len(self.et_model["records"]),
                "elemtable_rewritten": bool(self.et_dirty),
                "latest_rewritten": bool(self._latest_dirty),
                "streams_replaced": sorted(new_streams)}


def _rec_from_framed(seq: int, framed: bytes) -> Rec:
    """Wrap framed record bytes as a ``reduce.Rec`` (size == the u32 psize)."""
    hl = _hdr_len(seq)
    eid = struct.unpack_from("<q", framed, 0)[0]
    size = struct.unpack_from("<I", framed, hl - 4)[0]
    if hl + size + 4 != len(framed):
        raise ValueError(f"seq {seq} id {eid}: framed length {len(framed)} != "
                         f"hdr {hl} + psize {size} + 4")
    return Rec(seq, int(eid), int(size), bytes(framed))


def _assert_sentinel_last(run: SeqRun) -> None:
    if not run.recs or not run.recs[-1].is_sentinel:
        raise ValueError(f"seq {run.seq}: unit-0 run does not end with the sentinel")
    for r in run.recs[:-1]:
        if r.is_sentinel:
            raise ValueError(f"seq {run.seq}: a sentinel record sits before the end")


# ===========================================================================
# 3. RECORD SOURCES (what to write) -- TypeRecord / dicts / raw bytes
# ===========================================================================

def framed_records_from(records: Any, elem_id: int) -> Dict[int, bytes]:
    """Normalize ``records`` to ``{seq: framed_record_bytes}`` for ``elem_id``.

    Accepts: a ``TypeRecord``-like (``.encode()`` after its ``elem_id`` is set),
    a ``{seq: bytes}`` map (used verbatim, ids asserted), or a
    ``{seq: (class_id, value_dict)}`` map (encoded via ``rvt.encode``)."""
    if hasattr(records, "encode") and hasattr(records, "elem_id"):
        rec = records
        if int(rec.elem_id) != int(elem_id):
            rec = copy.copy(rec)
            rec.elem_id = int(elem_id)
            # the object's own m_id must follow the id
            if isinstance(getattr(rec, "obj", None), dict) and "m_id" in rec.obj:
                rec.obj = copy.deepcopy(rec.obj)
                rec.obj["m_id"] = int(elem_id)
        return {int(s): bytes(b) for s, b in rec.encode().items()}
    out: Dict[int, bytes] = {}
    for seq, item in dict(records).items():
        seq = int(seq)
        if isinstance(item, (bytes, bytearray)):
            fb = bytes(item)
            got = struct.unpack_from("<q", fb, 0)[0]
            if got != int(elem_id):
                raise ValueError(f"seq {seq}: framed record carries id {got}, expected {elem_id}")
            out[seq] = fb
        else:
            cid, value = item
            out[seq] = E.encode_record(seq, int(elem_id), None, int(cid), value)
    return out


# ===========================================================================
# 4. PLACEMENT (the 'position' half of the add path)
# ===========================================================================

def choose_position(run: SeqRun, new_id: int, place: str = "auto") -> Tuple[int, dict]:
    """Choose the insertion index in one seq's unit-0 run for element
    ``new_id``.  Returns (index, explanation).

    Policies:
      * 'append'      -- immediately before the sentinel (the OLD path; PROVEN
                         for user-content classes: V20..V29, T_conduit_types).
      * 'after:<eid>' -- right after element ``eid`` (an anchor the caller knows).
      * 'index:<n>'   -- an absolute record index (clamped before the sentinel).
      * 'auto'        -- the ID-HOLE policy: if the run contains ids A < new_id
                         < B with A and B STREAM-ADJACENT and A the greatest id
                         below new_id / B the least above (the document-birth
                         low-id run keeps consecutive ids adjacent: measured
                         K1/rstbasic ..., 1, 2, 3, 4, 5, 6, ...; dach ..., 3,
                         6, 11, 12, 13 ...), insert INTO the hole (reproduces
                         the corpus layout byte-for-byte); else, if the id
                         predecessor A exists and sits inside a locally
                         ASCENDING stretch (A's next neighbour has a higher
                         id than A), insert right after A; else append.
    """
    recs = run.recs
    live = [(i, r.elem_id) for i, r in enumerate(recs) if r.elem_id >= 0]
    sentinel_at = len(recs) - 1
    info: Dict[str, Any] = {"policy": place, "seq": run.seq}
    if place == "append":
        info["reason"] = "appended before the sentinel (proven for user-content classes)"
        return sentinel_at, info
    if place.startswith("after:"):
        anchor = int(place.split(":", 1)[1])
        i = run.index_of(anchor)
        info["anchor"] = anchor
        info["reason"] = f"inserted immediately after anchor {anchor} (position {i})"
        return i + 1, info
    if place.startswith("index:"):
        i = max(0, min(int(place.split(":", 1)[1]), sentinel_at))
        info["reason"] = f"absolute index {i}"
        return i, info
    if place != "auto":
        raise ValueError(f"unknown place policy {place!r}")
    # 'auto': id-hole
    below = [(i, e) for i, e in live if e < new_id]
    above = [(i, e) for i, e in live if e > new_id]
    if below and above:
        a_i, a_e = max(below, key=lambda t: t[1])          # greatest id below ours
        b_i, b_e = min(above, key=lambda t: t[1])          # least id above ours
        info["id_predecessor"] = {"id": a_e, "index": a_i}
        info["id_successor"] = {"id": b_e, "index": b_i}
        if b_i == a_i + 1:
            info["reason"] = (f"ID-HOLE: id neighbours {a_e} and {b_e} are stream-adjacent "
                              f"(positions {a_i}, {b_i}) -- inserted between them, "
                              f"reproducing the corpus's consecutive-id run")
            return b_i, info
    if below:
        a_i, a_e = max(below, key=lambda t: t[1])
        nxt = None
        if a_i + 1 < len(recs) and recs[a_i + 1].elem_id >= 0:
            nxt = recs[a_i + 1].elem_id
        info["id_predecessor"] = {"id": a_e, "index": a_i, "next": nxt}
        if nxt is not None and nxt > a_e:
            info["reason"] = (f"AFTER-PREDECESSOR: id predecessor {a_e} at {a_i} sits in an "
                              f"ascending stretch (next {nxt}); inserted after it")
            return a_i + 1, info
    info["reason"] = ("APPEND fallback: no id-hole / ascending anchor found "
                      "(proven placement for user-content classes)")
    return sentinel_at, info


def neighbourhood(run: SeqRun, index: int, decoder: Optional[ObjectDecoder] = None,
                  radius: int = 4) -> List[dict]:
    """The ids (+ classes) around a stream position, for the report."""
    dec = decoder or ObjectDecoder()
    out = []
    for j in range(max(0, index - radius), min(len(run.recs), index + radius + 1)):
        r = run.recs[j]
        if r.elem_id < 0:
            out.append({"pos": j, "id": -1, "class": "<sentinel>"})
            continue
        try:
            cid = struct.unpack_from("<H", r.data, _hdr_len(run.seq))[0]
            cls = dec.class_name(cid)
        except Exception:
            cls = "?"
        out.append({"pos": j, "id": r.elem_id, "class": cls,
                    **({"HERE": True} if j == index else {})})
    return out


# ===========================================================================
# 5. ADOCUMENT REGISTRY HELPERS
# ===========================================================================

def _typed_editor():
    """The arbiter's SCHEMA-TYPED ElementId leaf walker (never a byte scan:
    id 2 is byte-mentioned by ~40 geometry-step counters that are NOT ids).
    Lives in the tools tree (genesis_assemble.AdocGraphEditor, the walker
    that certified the K-ladder purges + the X-ladder parity); imported
    lazily so this module stays importable without the tools directory."""
    tools = os.path.join(ROOT, "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import genesis_assemble as GA                                    # noqa: E402
    return GA.AdocGraphEditor(decoder=None, maps=GA.load_registry_maps())


def latest_leaves_with(tree: dict, ids: Iterable[int]) -> Dict[int, List[str]]:
    """{id: [typed leaf paths]} -- the ADocument REGISTRY SURFACE of each id."""
    ed = _typed_editor()
    want = {int(i) for i in ids}
    out: Dict[int, List[str]] = collections.defaultdict(list)
    for lf in (ed.iter_leaves(tree, "ADocument") or []):
        if isinstance(lf.value, int) and lf.value in want:
            out[lf.value].append(lf.path)
    return {k: sorted(v) for k, v in out.items()}


def latest_remap_ids(tree: dict, mapping: Dict[int, int]) -> List[dict]:
    """Rewrite every ElementId-TYPED leaf holding a key of ``mapping`` to its
    value, IN PLACE.  Returns the edit log (path, old, new)."""
    ed = _typed_editor()
    edits = []
    for lf in (ed.iter_leaves(tree, "ADocument") or []):
        v = lf.value
        if isinstance(v, int) and v in mapping:
            lf.holder[lf.key] = int(mapping[v])
            edits.append({"path": lf.path, "old": v, "new": int(mapping[v])})
    return edits


def register_in_latest(tree: dict, records: Sequence[Any]) -> dict:
    """Populate the class registry surfaces for OUR new records (the
    singletons stream's proven :func:`rvt.genesis.settings.apply_adoc_registry`
    -- UET slots / AppInfo scalars & sets / browser / navigator / ETD /
    def-type / sysfam / CategoryTracking).  Returns its report."""
    from .genesis import settings as ST
    maps = {}
    try:
        tools = os.path.join(ROOT, "tools")
        if tools not in sys.path:
            sys.path.insert(0, tools)
        import genesis_assemble as GA                                # noqa: E402
        maps = GA.load_registry_maps()
    except Exception:                                              # pragma: no cover
        maps = {}
    return ST.apply_adoc_registry(tree, list(records), maps=maps)


# ===========================================================================
# 6. substitute_element  --  IN-PLACE CONTENT SWAP (zero registration motion)
# ===========================================================================

@dataclasses.dataclass
class SubstituteReport:
    op: str
    parent: str
    out: str
    target_id: int
    class_name: Optional[str]
    seqs_replaced: List[int]
    null_mode: bool
    row_before: Optional[dict]
    row_after: Optional[dict]
    positions_before: Dict[int, int]
    positions_after: Dict[int, int]
    record_len_delta: Dict[int, int]
    identity_at_original: Optional[dict]
    emit: dict
    diff: Optional[dict] = None
    validator: Optional[dict] = None
    structural: Optional[dict] = None
    problems: List[str] = dataclasses.field(default_factory=list)
    verdict: str = "?"
    notes: List[str] = dataclasses.field(default_factory=list)

    def to_json(self) -> dict:
        return dataclasses.asdict(self)


def substitute_element(src_rvt: str, out_path: str, target_id: int, records: Any = None,
                       *, seqs: Sequence[int] = (101, 102, 103), null: bool = False,
                       keep_row: bool = True, vintage: Optional[Tuple[int, int, int]] = None,
                       verify: bool = True, diff: bool = True) -> SubstituteReport:
    """SUBSTITUTE the content of an EXISTING element IN PLACE and write ``out_path``.

    The element keeps its id, its ElemTable row (``keep_row=True``; pass
    ``vintage=(ce, me, ue)`` to rewrite only the episodes), its record
    POSITION in each seq stream and every registry slot (Global/Latest is
    copied byte-identical).  ``records`` = a TypeRecord (its object /
    header / rep, encoded at ``target_id``) or ``{seq: framed bytes}`` /
    ``{seq: (class_id, value)}``; only the seqs in ``seqs`` are replaced.

    ``null=True`` ignores ``records`` and re-writes the element with ITS
    OWN exact bytes: the emitted Partitions stream must be BYTE-IDENTICAL to
    the parent's (asserted in the report) -- the zero-motion proof and the
    batch's positive control.
    """
    return substitute_elements(src_rvt, out_path, {int(target_id): (None if null else records)},
                               seqs=seqs, null=null, keep_row=keep_row,
                               vintage={int(target_id): vintage} if vintage else None,
                               verify=verify, diff=diff)


def substitute_elements(src_rvt: str, out_path: str, records_by_id: Dict[int, Any], *,
                        seqs: Sequence[int] = (101, 102, 103), null: bool = False,
                        keep_row: bool = True,
                        vintage: Optional[Dict[int, Tuple[int, int, int]]] = None,
                        verify: bool = True, diff: bool = True) -> SubstituteReport:
    """BATCH in-place substitution: ``records_by_id`` = {existing id: records}
    (records ignored when ``null=True``).  One EditImage, one emission --
    the whole-catalog / settings-layer rungs (XR2 / XR3) ride on this."""
    img = EditImage(src_rvt)
    vintage = vintage or {}
    rep_rows = {}
    positions_before: Dict[int, Dict[int, int]] = {}
    len_delta: Dict[int, Dict[int, int]] = {}
    identity: Dict[int, dict] = {}
    seqs_replaced: Dict[int, List[int]] = {}
    for target_id, records in records_by_id.items():
        target_id = int(target_id)
        old = img.records_of(target_id)
        if not old:
            raise KeyError(f"{src_rvt}: element {target_id} not in save unit 0")
        positions_before[target_id] = {s: img.runs[s].index_of(target_id) for s in old}
        if null:
            framed = {s: r.data for s, r in old.items()}
            identity[target_id] = _verify_byte_identity(img, target_id, old)
        else:
            if records is None:
                raise ValueError(f"element {target_id}: records required unless null=True")
            framed = framed_records_from(records, target_id)
        rep_seqs = []
        deltas = {}
        for seq in seqs:
            if seq not in old or seq not in framed:
                continue
            deltas[seq] = len(framed[seq]) - len(old[seq].data)
            img.replace_record(seq, target_id, framed[seq])
            rep_seqs.append(seq)
        seqs_replaced[target_id] = rep_seqs
        len_delta[target_id] = deltas
        if vintage.get(target_id) is not None:
            ce, me, ue = vintage[target_id]
            row = img.remove_elemtable_row(target_id)
            if row is not None:
                nr = dict(row, creation_ep=int(ce), modified_ep=int(me),
                          user_modified_ep=(NO_EPISODE if ue in (None, -1, NO_EPISODE)
                                            else int(ue)))
                img.restore_elemtable_row(nr)
        elif not keep_row:
            raise ValueError("keep_row=False requires an explicit vintage per element")
        rep_rows[target_id] = img.elemtable_row(target_id)
    emit_rep = img.emit(out_path)
    ids = sorted(records_by_id)
    first = ids[0]
    rep = SubstituteReport(
        op=("substitute_elements" if len(ids) > 1 else "substitute_element"),
        parent=src_rvt, out=out_path, target_id=first,
        class_name=img.class_of(first),
        seqs_replaced=sorted({s for v in seqs_replaced.values() for s in v}),
        null_mode=bool(null), row_before=rep_rows.get(first), row_after=rep_rows.get(first),
        positions_before=positions_before.get(first, {}),
        positions_after={s: img.runs[s].index_of(first) for s in positions_before.get(first, {})},
        record_len_delta=(len_delta.get(first) or {}),
        identity_at_original=(identity.get(first) if len(ids) == 1
                              else {"elements": len(identity),
                                    "all_identical": all(v.get("all_identical")
                                                         for v in identity.values())}
                              if identity else None),
        emit=emit_rep,
        notes=[f"{len(ids)} element(s) substituted in place: ids "
               f"{ids[:8]}{'...' if len(ids) > 8 else ''}"] + list(img.notes))
    _certify(rep, src_rvt, out_path, verify=verify, want_diff=diff,
             expect_only_ids=set(ids),
             expect_streams_identical=([LATEST_STREAM, ELEMTABLE_STREAM]
                                       if (keep_row and not vintage) else [LATEST_STREAM]),
             null_partition_identical=null)
    return rep


def _verify_byte_identity(img: EditImage, eid: int, recs: Dict[int, Rec]) -> dict:
    """decode -> re-encode of each of the element's records equals its
    original framed bytes (the honesty gate for 'verbatim' claims)."""
    out: Dict[str, Any] = {"element": int(eid), "seqs": {}}
    ok = True
    for seq, r in recs.items():
        hl = _hdr_len(seq)
        if r.size < 2:                                  # empty dummy
            out["seqs"][str(seq)] = {"identical": True, "empty": True}
            continue
        cid = struct.unpack_from("<H", r.data, hl)[0]
        body = r.data[hl + 2: hl + r.size]
        dec = img.decoder.decode_record(cid, body)
        if not dec.clean:
            out["seqs"][str(seq)] = {"identical": False, "decode_clean": False}
            ok = False
            continue
        re = E.encode_record(seq, int(eid), None, cid, dec.value)
        same = (re == r.data)
        ok = ok and same
        entry = {"identical": same, "class": img.decoder.class_name(cid), "bytes": len(r.data)}
        if not same:
            n = min(len(re), len(r.data))
            entry["first_divergence"] = next((i for i in range(n) if re[i] != r.data[i]), n)
        out["seqs"][str(seq)] = entry
    out["all_identical"] = ok
    return out


# ===========================================================================
# 7. add_element_like_original  --  THE FIXED ADD PATH
# ===========================================================================

@dataclasses.dataclass
class AddReport:
    op: str
    parent: str
    out: str
    elem_id: int
    class_name: str
    replaced_old_id: Optional[int]
    elemtable_row: dict
    corpus_rule: dict
    rule_violations: List[str]
    placement: Dict[str, Any]
    owned_children_wired: List[int]
    registry: dict
    emit: dict
    diff: Optional[dict] = None
    validator: Optional[dict] = None
    structural: Optional[dict] = None
    problems: List[str] = dataclasses.field(default_factory=list)
    verdict: str = "?"
    notes: List[str] = dataclasses.field(default_factory=list)

    def to_json(self) -> dict:
        return dataclasses.asdict(self)


def add_element_like_original(src_rvt: str, out_path: str, records: Any, *,
                              class_name: str,
                              new_id: Optional[int] = None,
                              replace_old_id: Optional[int] = None,
                              place: str = "auto",
                              cohort: str = "project",
                              creation_ep: Optional[int] = None,
                              modified_ep: Optional[int] = None,
                              user_modified_ep: Optional[int] = None,
                              preserve_row_of: Optional[int] = None,
                              owner_id: int = -1,
                              owned_child_ids: Sequence[int] = (),
                              register: bool = False,
                              latest_remap: Optional[Dict[int, int]] = None,
                              verify: bool = True, diff: bool = True,
                              strict_rules: bool = False) -> AddReport:
    """ADD a NEW element the way a loadable file registers the same class.

    ``records`` = a TypeRecord (encoded at the chosen id) or a per-seq map.
    ``new_id`` = the target id (default: watermark + 1).  ``replace_old_id``
    = an existing element to DELETE in the same commit (its records and row
    are removed BEFORE ours are added -- the delete-and-add form; when
    ``replace_old_id == new_id`` this is a same-id re-insert).
    ``preserve_row_of`` = an element id whose ElemTable row (episodes /
    owner / original id) our new row COPIES (the null / verbatim re-add:
    the row a loadable file already had for this element).  Otherwise the
    row's vintage comes from :func:`vintage_for` (the corpus rule for the
    class; explicit ``creation_ep`` / ``modified_ep`` / ``user_modified_ep``
    win) and its owner from ``owner_id``.  ``owned_child_ids`` get their
    OWN rows' owner pointed at the new element (the ownership web the OLD
    path never wired).  ``place`` = the position policy (see
    :func:`choose_position`).  ``register=True`` populates the class's
    ADocument registry surfaces (settings.apply_adoc_registry) for the new
    id; ``latest_remap`` = {old_id: new_id} schema-typed leaf remaps applied
    first (the re-point of an old element's registry slots to the new id).
    When neither is given Global/Latest is copied byte-identical.
    ``strict_rules=True`` refuses to emit a registration that violates
    :data:`REG_RULES` (otherwise violations are only REPORTED).
    """
    img = EditImage(src_rvt)
    notes: List[str] = []
    # ---- id --------------------------------------------------------------
    if new_id is None:
        new_id = img.watermark + 1
        notes.append(f"new_id defaulted to watermark+1 = {new_id}")
    new_id = int(new_id)
    # ---- the row we may copy (preserve) BEFORE any deletion ---------------
    preserved_row = None
    if preserve_row_of is not None:
        preserved_row = img.elemtable_row(int(preserve_row_of))
        if preserved_row is None:
            raise KeyError(f"preserve_row_of {preserve_row_of}: no ElemTable row in parent")
    # ---- delete the old element (delete-and-add form) -----------------------
    old_positions: Dict[int, int] = {}
    old_row = None
    if replace_old_id is not None:
        old_positions = img.delete_element_records(int(replace_old_id))
        old_row = img.remove_elemtable_row(int(replace_old_id))
        notes.append(f"deleted old element {replace_old_id} (records at {old_positions}, "
                     f"row {old_row})")
    if img.has_element(new_id):
        raise ValueError(f"element id {new_id} already exists in {src_rvt}")
    # ---- the ElemTable row ------------------------------------------------
    if preserved_row is not None:
        row = dict(preserved_row, elem_id=new_id, original_id=new_id)
        # a re-add at a NEW id keeps the row's vintage but its original_id
        # follows the new id (renumbering semantics); at the SAME id it is
        # exactly the parent's row
        if preserve_row_of == new_id:
            row["original_id"] = preserved_row["original_id"]
        ce, me, ue = row["creation_ep"], row["modified_ep"], row["user_modified_ep"]
        row_owner = row["owner_id"]
        notes.append(f"ElemTable row COPIED from element {preserve_row_of}: "
                     f"(orig {row['original_id']}, ce {ce}, me {me}, ue {ue}, "
                     f"owner {row_owner})")
    else:
        ce, me, ue = vintage_for(class_name, parent_max_ep=img.max_episode, cohort=cohort,
                                 creation_ep=creation_ep, modified_ep=modified_ep,
                                 user_modified_ep=user_modified_ep)
        row_owner = int(owner_id) if owner_id not in (None, -1) else -1
        row = {"elem_id": new_id, "original_id": new_id, "creation_ep": ce,
               "modified_ep": me, "user_modified_ep": ue, "owner_id": row_owner,
               "partition_id": 0}
    img.add_elemtable_row(elem_id=new_id, creation_ep=row["creation_ep"],
                          modified_ep=row["modified_ep"],
                          user_modified_ep=row["user_modified_ep"],
                          owner_id=row.get("owner_id", -1),
                          original_id=row.get("original_id", new_id),
                          partition_id=row.get("partition_id", 0))
    # owned children: their rows' owner = the new element
    wired: List[int] = []
    for kid in owned_child_ids:
        if img.set_row_owner(int(kid), new_id):
            wired.append(int(kid))
        else:
            notes.append(f"owned child {kid}: no ElemTable row to re-point (skipped)")
    # ---- lint the registration against the corpus rule ---------------------
    owner_cls = img.class_of(row_owner) if row_owner not in (None, -1) else None
    violations = check_registration(class_name, elem_id=new_id, creation_ep=row["creation_ep"],
                                    owner_class=owner_cls, cohort=cohort)
    if violations and strict_rules:
        raise ValueError("registration violates the corpus rule(s): " + "; ".join(violations))
    # ---- the records + placement -------------------------------------------
    framed = framed_records_from(records, new_id)
    missing = [s for s in SEQS if s not in framed]
    if missing:
        raise ValueError(f"records must cover all three seqs; missing {missing}")
    placement: Dict[str, Any] = {"policy": place, "per_seq": {}}
    # a same-id re-insert (or an explicit index/anchor) may point INTO the
    # hole the deletion left: for place='auto' with replace_old_id == new_id
    # we re-insert at the old positions (the true in-place re-add)
    index_by_seq: Dict[int, int] = {}
    for seq in SEQS:
        run = img.runs[seq]
        if place == "auto" and replace_old_id is not None and int(replace_old_id) == new_id \
                and seq in old_positions:
            idx, info = old_positions[seq], {"policy": "same-id-in-place",
                                              "reason": "re-inserted at the deleted element's "
                                                        "own position (zero motion)"}
        elif place == "old-position" and seq in old_positions:
            idx, info = old_positions[seq], {"policy": "old-position",
                                              "reason": (f"inserted at the position element "
                                                         f"{replace_old_id} occupied")}
        else:
            pol = "auto" if place == "old-position" else place
            idx, info = choose_position(run, new_id, pol)
        index_by_seq[seq] = idx
        placement["per_seq"][seq] = {"index": idx, "of": len(run.recs), **info,
                                      "neighbourhood_after": None}
    img.insert_records(framed, index_by_seq)
    for seq in SEQS:
        placement["per_seq"][seq]["neighbourhood_after"] = neighbourhood(
            img.runs[seq], img.runs[seq].index_of(new_id), img.decoder)
    # ---- ADocument registries ---------------------------------------------
    registry_rep: Dict[str, Any] = {"latest_touched": False}
    if latest_remap or register:
        tree = json.loads(json.dumps(img.latest_tree))
        if latest_remap:
            edits = latest_remap_ids(tree, {int(k): int(v) for k, v in latest_remap.items()})
            registry_rep["remap_edits"] = len(edits)
            registry_rep["remap_examples"] = edits[:12]
        if register:
            registry_rep["registration"] = register_in_latest(tree, [records])
        img.set_latest_tree(tree)
        registry_rep["latest_touched"] = True
    else:
        # zero-motion mode: prove the surface if the id already had one
        if replace_old_id is not None and int(replace_old_id) == new_id:
            registry_rep["note"] = ("same-id re-insert: Global/Latest untouched "
                                    "(byte-identical); every registry slot naming "
                                    f"{new_id} indexes the re-added element")
        else:
            registry_rep["note"] = ("Global/Latest untouched (byte-identical): no "
                                    "registration / remap requested for this element")
    # ---- emit + certify -----------------------------------------------------
    emit_rep = img.emit(out_path)
    rep = AddReport(
        op="add_element_like_original", parent=src_rvt, out=out_path, elem_id=new_id,
        class_name=class_name, replaced_old_id=replace_old_id,
        elemtable_row=img.elemtable_row(new_id) or {},
        corpus_rule=reg_rule(class_name, cohort=cohort),
        rule_violations=violations, placement=placement, owned_children_wired=wired,
        registry=registry_rep, emit=emit_rep, notes=notes + list(img.notes))
    identical = [] if registry_rep.get("latest_touched") else [LATEST_STREAM]
    expect_ids = {new_id}
    if replace_old_id is not None:
        expect_ids.add(int(replace_old_id))
    _certify(rep, src_rvt, out_path, verify=verify, want_diff=diff,
             expect_only_ids=expect_ids, expect_streams_identical=identical,
             null_partition_identical=False)
    return rep


# ===========================================================================
# 8. CERTIFICATION + THE STREAM DIFF REPORT (the K1 byte-diff assertions)
# ===========================================================================

def _run_validator(path: str) -> dict:
    from .validate import validate_file
    rep = validate_file(path)
    errs = rep.errors
    return {"ok": bool(rep.ok), "errors": len(errs), "warnings": len(rep.warnings),
            "error_messages": [f"[{f.layer}] {f.where}: {f.message}"[:400] for f in errs[:6]],
            "stats": {k: v for k, v in rep.stats.items()
                      if k in ("streams", "records", "elements_decoded", "refs_checked",
                               "partition_blocks", "decode_failures")}}


def _certify(rep, src: str, out: str, *, verify: bool, want_diff: bool,
             expect_only_ids: set, expect_streams_identical: List[str],
             null_partition_identical: bool) -> None:
    problems: List[str] = []
    if verify:
        try:
            val = _run_validator(out)
            rep.validator = val
            if not (val["ok"] and val["errors"] == 0):
                problems.append(f"validator errors={val['errors']}")
        except Exception as e:                                    # pragma: no cover
            rep.validator = {"error": repr(e)[:300]}
            problems.append("validator crashed")
        try:
            st = _reduce.verify_reduced(out, [])
            rep.structural = {k: st.get(k) for k in ("ok", "crc_failures", "ecc_mismatches",
                                                    "walker_errors", "counts_match",
                                                    "seq_id_sets_equal", "stamps_bad",
                                                    "isize_identity_ok")}
            if not st.get("ok"):
                problems.append("structural proof failed")
        except Exception as e:                                    # pragma: no cover
            rep.structural = {"error": repr(e)[:300]}
            problems.append("structural proof crashed")
    if want_diff:
        d = stream_diff_report(src, out)
        rep.diff = d
        # -- the assertions --------------------------------------------------
        touched = set(d["records"]["changed_ids"]) | set(d["records"]["added_ids"]) \
            | set(d["records"]["removed_ids"])
        stray = sorted(touched - {int(i) for i in expect_only_ids})
        if stray:
            problems.append(f"record ids touched beyond the target(s): {stray[:8]}")
        for s in expect_streams_identical:
            if s in d["streams"]["differing"]:
                problems.append(f"{s} differs from the parent but must be byte-identical")
        if null_partition_identical and not d["partition_logical_identical"]:
            problems.append("NULL mode: Partitions logical stream is NOT byte-identical to the "
                            "parent's (the path is not zero-motion)")
        if not d["records"]["id_order_identical"] and not d["records"]["added_ids"] \
                and not d["records"]["removed_ids"]:
            problems.append("unit-0 id order changed although no record was added/removed")
    rep.problems = problems
    rep.verdict = "VALID" if not problems else "NOT-CLEAN"


def _unit0_index(path: str):
    """Everything the diff needs about a file: per-(seq,id) framed record
    bytes, per-seq id order, per-seq block partition, embedded-unit digests,
    the ElemTable model, and every stream's comparable bytes."""
    out = {}
    order = {}
    with open_rvt(path) as f:
        pname = f.partition_streams()[0]
        raw_part = f.raw(pname)
        try:
            logical = unframe_exact(raw_part)
        except Exception:                                        # pragma: no cover
            logical = f.logical(pname)
        w = StreamWalker(logical, inflate=True, keep_data=True)
        blocks = sorted(w.blocks, key=lambda b: b.hdr_offset)
        u0 = [b for b in blocks if b.unit == 0]
        block_partition = {s: [(b.flags, b.n_records, len(b.data)) for b in u0 if b.seq == s]
                           for s in SEQS}
        others = collections.defaultdict(bytes)
        for b in blocks:
            if b.unit != 0 and b.data:
                others[b.unit] += b.data
        embedded = {u: hashlib.sha256(v).hexdigest()[:16] for u, v in others.items()}
        for seq in SEQS:
            seg = b"".join(b.data for b in u0 if b.seq == seq)
            ids = []
            for r in iter_records(seg, seq):
                out[(seq, r.elem_id)] = bytes(E.record_bytes(seg, r, seq))
                if r.elem_id >= 0:
                    ids.append(r.elem_id)
            order[seq] = ids
        # per-stream identity is judged on the RAW (page-framed) bytes: the
        # depaged 'logical' leaks junk after the true end, so two files
        # with identical content can depage to different tails
        streams = {}
        for si in f.streams():
            s = si.name
            try:
                streams[s] = f.raw(s)
            except Exception:                                    # pragma: no cover
                streams[s] = b""
        et_model = decode_elemtable(f.inflate(ELEMTABLE_STREAM))
        latest = f.inflate(LATEST_STREAM, 0)
    return {"records": out, "order": order, "streams": streams, "logical": logical,
            "partition": pname, "blocks": block_partition, "embedded": embedded,
            "elemtable": et_model, "latest": latest}


def _decode_field_diff(a_bytes: bytes, b_bytes: bytes, seq: int,
                       dec: ObjectDecoder, limit: int = 30) -> List[dict]:
    """Field-level diff of two framed records of the same (seq, id)."""
    hl = _hdr_len(seq)
    try:
        psA = struct.unpack_from("<I", a_bytes, hl - 4)[0]
        psB = struct.unpack_from("<I", b_bytes, hl - 4)[0]
        cidA = struct.unpack_from("<H", a_bytes, hl)[0]
        cidB = struct.unpack_from("<H", b_bytes, hl)[0]
        va = dec.decode_record(cidA, a_bytes[hl + 2: hl + psA])
        vb = dec.decode_record(cidB, b_bytes[hl + 2: hl + psB])
    except Exception as e:                                        # pragma: no cover
        return [{"path": "<decode>", "error": repr(e)[:200]}]
    out: List[dict] = [{"class_ours": dec.class_name(cidA),
                        "class_parent": dec.class_name(cidB)}]

    def rec(a, b, path):
        if len(out) > limit:
            return
        if isinstance(a, dict) and isinstance(b, dict):
            for k in sorted(set(a) | set(b)):
                if k not in a or k not in b:
                    out.append({"path": f"{path}.{k}", "ours": repr(a.get(k, "<absent>"))[:80],
                                "parent": repr(b.get(k, "<absent>"))[:80]})
                else:
                    rec(a[k], b[k], f"{path}.{k}")
        elif isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                out.append({"path": f"{path}[len]", "ours": len(a), "parent": len(b)})
            for i, (x, y) in enumerate(zip(a, b)):
                rec(x, y, f"{path}[{i}]")
        elif a != b:
            out.append({"path": path, "ours": repr(a)[:80], "parent": repr(b)[:80]})
    rec(va.value, vb.value, "")
    return out


def stream_diff_report(parent: str, out: str, *, max_examples: int = 12) -> dict:
    """The K1 BYTE-DIFF REPORT: per stream identical/differing; unit-0
    records added / removed / changed (with field-level decode diffs);
    per-seq id order + block partition identity; ElemTable rows added /
    removed / changed; ADocument (Global/Latest) identity and, if it differs,
    its typed ElementId leaf changes.  Used to ASSERT what a probe changed."""
    A = _unit0_index(parent)
    B = _unit0_index(out)
    dec = ObjectDecoder()
    # ---- streams ------------------------------------------------------------
    identical, differing = [], []
    for s in sorted(set(A["streams"]) | set(B["streams"])):
        a, b = A["streams"].get(s), B["streams"].get(s)
        (identical if a == b else differing).append(s)
    part_logical_identical = (A["logical"] == B["logical"])
    # ---- records ------------------------------------------------------------
    keys = set(A["records"]) | set(B["records"])
    added = sorted(k for k in B["records"] if k not in A["records"])
    removed = sorted(k for k in A["records"] if k not in B["records"])
    changed = sorted(k for k in keys if k in A["records"] and k in B["records"]
                     and A["records"][k] != B["records"][k])
    ch_ex = []
    for (seq, eid) in changed[:max_examples]:
        ra, rb = B["records"][(seq, eid)], A["records"][(seq, eid)]
        n = min(len(ra), len(rb))
        first = next((i for i in range(n) if ra[i] != rb[i]), n)
        entry = {"seq": seq, "id": eid, "len_ours": len(ra), "len_parent": len(rb),
                 "first_diff_byte": first}
        if seq in (101, 102):
            entry["field_diff"] = _decode_field_diff(ra, rb, seq, dec)
        ch_ex.append(entry)
    order_same = {s: (A["order"][s] == B["order"][s]) for s in SEQS}
    # common-subsequence order preservation (when ids were added/removed)
    common_order = {}
    for s in SEQS:
        sa, sb = set(A["order"][s]), set(B["order"][s])
        common_order[s] = ([x for x in A["order"][s] if x in sb]
                           == [x for x in B["order"][s] if x in sa])
    added_pos = {f"{s}/{e}": {"index": B["order"][s].index(e), "of": len(B["order"][s])}
                 for (s, e) in added if e in B["order"][s]}
    removed_pos = {f"{s}/{e}": {"index": A["order"][s].index(e), "of": len(A["order"][s])}
                   for (s, e) in removed if e in A["order"][s]}
    # ---- block partition ----------------------------------------------------
    blocks = {}
    for s in SEQS:
        ba, bb = A["blocks"][s], B["blocks"][s]
        blocks[s] = {"parent": len(ba), "out": len(bb), "identical": ba == bb,
                     "differing": [i for i, (x, y) in enumerate(zip(ba, bb)) if x != y][:12]}
    # ---- ElemTable ----------------------------------------------------------
    def rows(m):
        return {int(r[4]): tuple(int(x) if isinstance(x, int) else x for x in r)
                for r in m["records"]}
    ra, rb = rows(A["elemtable"]), rows(B["elemtable"])
    et_added = sorted(set(rb) - set(ra))
    et_removed = sorted(set(ra) - set(rb))
    et_changed = sorted(k for k in set(ra) & set(rb) if ra[k] != rb[k])
    et = {"rows_parent": len(ra), "rows_out": len(rb),
          "added": [{"id": i, "row": list(rb[i])} for i in et_added[:12]],
          "removed": [{"id": i, "row": list(ra[i])} for i in et_removed[:12]],
          "changed": [{"id": i, "parent": list(ra[i]), "out": list(rb[i])} for i in et_changed[:12]],
          "watermark_parent": A["elemtable"]["footer"]["last_id"],
          "watermark_out": B["elemtable"]["footer"]["last_id"],
          "identical": (not et_added and not et_removed and not et_changed
                        and A["elemtable"]["footer"] == B["elemtable"]["footer"])}
    # ---- ADocument ----------------------------------------------------------
    latest = {"identical": A["latest"] == B["latest"],
              "len_parent": len(A["latest"]), "len_out": len(B["latest"])}
    if not latest["identical"]:
        try:
            from . import adocument as adoc
            ta = adoc.decode_latest(A["latest"]).value
            tb = adoc.decode_latest(B["latest"]).value
            ed = _typed_editor()
            la = collections.Counter()
            lb = collections.Counter()
            for lf in (ed.iter_leaves(ta, "ADocument") or []):
                if isinstance(lf.value, int):
                    la[(lf.path, lf.value)] += 1
            for lf in (ed.iter_leaves(tb, "ADocument") or []):
                if isinstance(lf.value, int):
                    lb[(lf.path, lf.value)] += 1
            gone = [ {"path": p, "id": v} for (p, v) in (la - lb).keys()][:20]
            new = [ {"path": p, "id": v} for (p, v) in (lb - la).keys()][:20]
            latest["typed_leaf_changes"] = {"removed": gone, "added": new,
                                            "removed_n": sum((la - lb).values()),
                                            "added_n": sum((lb - la).values())}
        except Exception as e:                                    # pragma: no cover
            latest["typed_leaf_changes"] = {"error": repr(e)[:200]}
    return {
        "parent": parent, "out": out,
        "streams": {"identical": identical, "differing": differing},
        "partition_logical_identical": part_logical_identical,
        "records": {
            "parent_count": len(A["records"]), "out_count": len(B["records"]),
            "added": [{"seq": s, "id": e, "len": len(B["records"][(s, e)])} for (s, e) in added],
            "removed": [{"seq": s, "id": e, "len": len(A["records"][(s, e)])} for (s, e) in removed],
            "changed": ch_ex,
            "changed_count": len(changed),
            "added_ids": sorted({e for (_s, e) in added}),
            "removed_ids": sorted({e for (_s, e) in removed}),
            "changed_ids": sorted({e for (_s, e) in changed}),
            "id_order_identical": all(order_same.values()),
            "id_order_identical_per_seq": order_same,
            "common_order_preserved": common_order,
            "added_positions": added_pos, "removed_positions": removed_pos,
        },
        "blocks": blocks,
        "elemtable": et,
        "latest": latest,
        "embedded_units_identical": (A["embedded"] == B["embedded"]),
    }


# ===========================================================================
# 9. CLI / demo
# ===========================================================================

def _demo() -> int:                                              # pragma: no cover
    """Smallest end-to-end demonstration on the K-ladder's K1: the NULL
    substitution of the project pen table (zero motion => Partitions
    byte-identical) and its diff report."""
    k1 = os.path.join(ROOT, "experiments", "genesis", "triage", "K1.rvt")
    if not os.path.exists(k1):
        print(f"demo needs {k1}")
        return 1
    out_dir = os.path.join(ROOT, "experiments", "genesis", "regadd")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "demo_null.rvt")
    rep = substitute_element(k1, out, 2, null=True)
    print(json.dumps({"verdict": rep.verdict, "problems": rep.problems,
                      "identity": (rep.identity_at_original or {}).get("all_identical"),
                      "partition_identical": (rep.diff or {}).get("partition_logical_identical"),
                      "streams_differing": (rep.diff or {}).get("streams", {}).get("differing")},
                     indent=1))
    return 0 if rep.verdict == "VALID" else 1


def main(argv=None) -> int:                                       # pragma: no cover
    import argparse
    ap = argparse.ArgumentParser(description="regadd -- the registration-conformant "
                                             "add / substitute path")
    ap.add_argument("--demo", action="store_true", help="run the K1 null-substitution demo")
    ap.add_argument("--diff", nargs=2, metavar=("PARENT", "OUT"),
                    help="print the stream diff report of OUT vs PARENT")
    ap.add_argument("--rule", metavar="CLASS", help="print the corpus rule for CLASS")
    args = ap.parse_args(argv)
    if args.rule:
        print(json.dumps(reg_rule(args.rule), indent=1))
        return 0
    if args.diff:
        rep = stream_diff_report(args.diff[0], args.diff[1])
        print(json.dumps(rep, indent=1, default=str))
        return 0
    if args.demo:
        return _demo()
    ap.print_help()
    return 0


if __name__ == "__main__":                                        # pragma: no cover
    sys.exit(main())
