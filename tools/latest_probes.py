#!/usr/bin/env python3
"""latest_probes — Global/Latest READER-TOLERANCE probe generator.

Purpose (the empirical shortcut for genesis-2):
    We cannot yet ENCODE the ADocument (``Global/Latest``, the serialized
    document object).  In the genesis candidate ``G0.rvt`` that stream is
    carried VERBATIM from the Autodesk sample (~94 % of G0's bytes) and holds
    (a) the sample project's own naming (rooms 'Hall' / 'Kitchen & Dining',
    sheet 'FOUNDATION-2700', assembly 'L1 wall frame hall 5', materials),
    (b) ~1.3 MB of Autodesk's Forge unit / spec / parameter-group JSON schema
    corpus, and (c) 6,175 references to the sample's element ids (every one
    dangling in G0).  If Autodesk's READER tolerates a SANITIZED Latest we can
    strip that Autodesk / sample expression NOW, before an encoder exists.

    Each probe mutates ONLY ``Global/Latest`` (re-gzip level 3 + sync flush,
    keep the 8-byte prefix u64 5, re-frame with real CRCIO ECC, rebuild the
    container) and every edit is LENGTH-PRESERVING so no byte offset shifts.
    A viewer PASS/FAIL then attributes cleanly to ONE class of content.  We
    cannot learn the answers ourselves — the orchestrator uploads the probes
    to Autodesk's translator; this tool makes them maximally INFORMATIVE and
    offset-safe.

Probe ladder (per base file; the base's own Latest is the control):

    P0_control      Latest re-encoded by us, payload byte-identical.
    P1_names        every PROJECT string (room / sheet / view / assembly /
                    material names, detail & sheet numbers, usernames)
                    replaced by same-length neutral text ('Hall' -> 'Rm09',
                    'FOUNDATION-2700' -> 'Nm0000000000023').
    P2_names_blank  the same strings replaced by same-length spaces.
    P3a_forge_stub  every Forge (typeid, json) pair's JSON body replaced by a
                    length-identical minimal document
                    '{"typeid": "<typeid>" ... }' — keys/typeids intact.
    P3b_forge_blank the same JSON bodies replaced by spaces (invalid JSON).
    P4_ids_null     every ElementId reference (i64) into the sample lineage
                    remapped to -1 (invalid).  In G0 all 6,175 are dangling.
    P5_combined     P1 + P4.
    P6_all          P2 + P3b + P4 + Forge typeids scrubbed + the LB reconcile
                    map strings scrubbed — the maximal length-preserving
                    sanitization ("genesis-2 dream file").

Bases:
    rst  samples/rstbasicsampleproject.rvt      (works — attributes purely to
                                               Latest content; all its ids are
                                               LIVE, so P4 tests "-1 breaks it"
                                               vs G0's "dangling breaks it")
    G0   experiments/genesis/G0.rvt            (Latest byte-identical to rst's;
                                               inventory 100 % ours; the 6,175
                                               ids are DANGLING here)

Outputs (default ``experiments/genesis/latest/probes/``):
    <probe>.rvt / G0_<probe>.rvt   the probe files (validator-VALID)
    <probe>.json / G0_<probe>.json exact byte ranges changed + why + the
                                   structural validator summary
    manifest.json                  the viewer QUEUE, ordered by information
                                   value, with the decision table

Usage:
    .venv/bin/python tools/latest_probes.py                 # both bases, all probes
    .venv/bin/python tools/latest_probes.py --base rst      # one base
    .venv/bin/python tools/latest_probes.py --only P1,P4    # subset
    .venv/bin/python tools/latest_probes.py --analyse       # analysis dump, no files

Record: docs/inbox/adoc-probes.md.  Tests: tests/test_latest_probes.py.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import re
import struct
import sys
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from rvt import ecc                                      # noqa: E402
from rvt.cfb_writer import write_cfb                      # noqa: E402
from rvt.container import open_rvt                        # noqa: E402
from rvt.elemtable import parse_elemtable                 # noqa: E402
from rvt.roundtrip import read_entries                    # noqa: E402
from rvt.writer import gzip_member                        # noqa: E402

STREAM = "Global/Latest"

BASES: Dict[str, Dict[str, str]] = {
    "rst": {
        "path": os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt"),
        "prefix": "",          # P1_names.rvt ...
        "label": "rstbasicsampleproject (working sample; all Latest ids LIVE)",
        # the ElementId universe the Latest references = its own ElemTable
        "id_source": os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt"),
    },
    "G0": {
        "path": os.path.join(ROOT, "experiments", "genesis", "G0.rvt"),
        "prefix": "G0_",       # G0_P1_names.rvt ...
        "label": "G0 genesis candidate (Latest verbatim from rstbasic; its ids "
                 "are all DANGLING here)",
        # G0's Latest is the rstbasic ADocument: its id universe is rstbasic's
        "id_source": os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt"),
    },
}

DEFAULT_OUT = os.path.join(ROOT, "experiments", "genesis", "latest", "probes")


# ===========================================================================
# primitives
# ===========================================================================

@dataclasses.dataclass
class AStr:
    """One serialized AString (u32 char count + UTF-16LE) found in a payload."""
    off: int          # offset of the u32 count
    nchars: int
    text: str
    cls: str = "unclassified"

    @property
    def data_off(self) -> int:
        return self.off + 4

    @property
    def end(self) -> int:
        return self.off + 4 + 2 * self.nchars


def _read_astring(pay: bytes, off: int, max_chars: int,
                  ascii_only: bool = False,
                  allow_surrogates: bool = True) -> Optional[Tuple[int, str]]:
    """If a u32-length-prefixed UTF-16LE string starts at ``off`` return
    (nchars, text).  Rejects NULs and (unless allow_surrogates) unpaired /
    surrogate code units.  ``max_chars`` bounds the length prefix."""
    if off < 0 or off + 4 > len(pay):
        return None
    n = struct.unpack_from("<I", pay, off)[0]
    if n < 1 or n > max_chars or off + 4 + 2 * n > len(pay):
        return None
    raw = pay[off + 4:off + 4 + 2 * n]
    for j in range(0, 2 * n, 2):
        c = raw[j] | (raw[j + 1] << 8)
        if c == 0:
            return None
        if ascii_only:
            if not (c in (9, 10, 13) or 0x20 <= c < 0x7F):
                return None
        else:
            if 0xD800 <= c < 0xE000 and not allow_surrogates:
                return None
            if not (c in (9, 10, 13) or c >= 0x20):
                return None
            if c in (0xFFFE, 0xFFFF):
                return None
    try:
        return n, raw.decode("utf-16-le", errors="surrogatepass")
    except UnicodeDecodeError:
        return None


def _enc_astring_body(text: str) -> bytes:
    return text.encode("utf-16-le", errors="surrogatepass")


# ===========================================================================
# scanning the payload
# ===========================================================================

def census_strings(pay: bytes, min_chars: int = 2) -> List[AStr]:
    """Greedy left-to-right census of plausible ASCII AStrings (>= min_chars).

    Deliberately conservative (ASCII only, >= 2 chars) so binary data is not
    mis-read as CJK "strings".  Single-character project names (detail
    numbers) are recovered separately by the naming-table structural scan.
    """
    out: List[AStr] = []
    i, n = 0, len(pay)
    while i < n - 6:
        r = _read_astring(pay, i, 8000, ascii_only=True)
        if r is not None and r[0] >= min_chars:
            out.append(AStr(i, r[0], r[1]))
            i += 4 + 2 * r[0]
        else:
            i += 1
    return out


def census_short_naming_entries(pay: bytes, exclude: Set[int]) -> List[AStr]:
    """Recover 1..3-char project strings (sheet DETAIL numbers etc.) that the
    conservative census skips, using the naming-table ENTRY structure:

        u32 marker(1|2) | AString name | i64 built_in_id (< -1000) ...

    i.e. the string is immediately preceded by a small u32 marker and
    immediately followed by a NEGATIVE built-in category/parameter id.  This
    is the sheet/detail-number registry; the structural test keeps the
    false-positive rate at zero on binary regions.
    """
    out: List[AStr] = []
    n = len(pay)
    for i in range(4, n - 24):
        if i in exclude:
            continue
        r = _read_astring(pay, i, 3, ascii_only=True)
        if r is None:
            continue
        marker = struct.unpack_from("<I", pay, i - 4)[0]
        if marker not in (1, 2):
            continue
        end = i + 4 + 2 * r[0]
        if end + 8 > n:
            continue
        follow = struct.unpack_from("<q", pay, end)[0]
        if not (-3_000_000 < follow < -1000):
            continue
        if not re.fullmatch(r"[A-Za-z0-9 .\-]{1,3}", r[1]):
            continue
        out.append(AStr(i, r[0], r[1]))
    return out


@dataclasses.dataclass
class ForgePair:
    """One (typeid, json) AString pair of the Forge schema corpus."""
    t: AStr
    j: AStr


def walk_forge_pairs(pay: bytes) -> List[ForgePair]:
    """Find every Autodesk Forge schema document embedded as an
    ``(AString typeid, AString json)`` pair.

    A typeid is an ASCII string beginning ``autodesk.`` (unit / spec /
    symbol / parameter-group / revit-group ids); its document is the AString
    that immediately follows and begins with '{'.  In rstbasic the corpus is
    1,315 such pairs (~84 % of the stream) laid out as consecutive
    dictionaries — no other framing between pairs except tiny per-dictionary
    headers (u32 counts) which this walk simply steps over.
    """
    pairs: List[ForgePair] = []
    n = len(pay)
    i = 0
    while i < n - 8:
        r = _read_astring(pay, i, 400, ascii_only=True)
        if r is not None and (r[1].startswith("autodesk.") or r[1].startswith("adsk.")):
            t = AStr(i, r[0], r[1], "forge.typeid")
            js = t.end
            rj = _read_astring(pay, js, 2_000_000, ascii_only=False)
            if rj is not None and rj[1].startswith("{"):
                j = AStr(js, rj[0], rj[1], "forge.json")
                pairs.append(ForgePair(t, j))
                i = j.end
                continue
            i = js
            continue
        i += 1
    return pairs


def elem_ids_of(path: str) -> Set[int]:
    """The set of ElementIds in a file's Global/ElemTable."""
    with open_rvt(path) as d:
        et = parse_elemtable(d.inflate("Global/ElemTable", 0))
    return {r.id for r in et.records}


@dataclasses.dataclass
class IdHit:
    off: int          # offset of the 8-byte little-endian i64
    value: int
    ctx: str          # neighbourhood classification (id-adjacency)


def scan_id_refs(pay: bytes, valid: Set[int], floor: int = 4700) -> List[IdHit]:
    """Every 8-byte window holding a little-endian i64 that is a KNOWN
    ElementId of the reference lineage (``valid``), above ``floor``.

    Small values are excluded (they collide with counts / enums / class
    ordinals).  In-range NON-id windows exist too (~1,845 in rstbasic), so the
    expected false-positive count is ``non_id_windows * len(valid)/max_id``
    (~17 of 9,602 for rstbasic = 0.18 %) — reported, not zero, and stated as
    the caveat on any P4 verdict.  Overlapping hits never occur (checked).
    """
    hi = max(valid) if valid else 0
    hits: List[IdHit] = []
    n = len(pay)
    off = 0
    while off <= n - 8:
        # cheap pre-filter: high 4 bytes zero (all ids < 2^31 here)
        if pay[off + 4] | pay[off + 5] | pay[off + 6] | pay[off + 7]:
            off += 1
            continue
        v = pay[off] | (pay[off + 1] << 8) | (pay[off + 2] << 16) | (pay[off + 3] << 24)
        if floor < v <= hi and v in valid:
            hits.append(IdHit(off, v, ""))
            off += 8            # ids never overlap; skip the whole window
        else:
            off += 1
    # neighbourhood context for confidence reporting
    idx = {h.off: h for h in hits}
    for h in hits:
        tags = []
        prev = struct.unpack_from("<q", pay, h.off - 8)[0] if h.off >= 8 else None
        nxt = struct.unpack_from("<q", pay, h.off + 8)[0] if h.off + 16 <= n else None
        if prev is not None and (prev in valid or prev == -1 or (h.off - 8) in idx):
            tags.append("id-adjacent")
        elif nxt is not None and (nxt in valid or nxt == -1 or (h.off + 8) in idx):
            tags.append("id-adjacent")
        else:
            tags.append("isolated")
        h.ctx = tags[0]
    return hits


# (Edit.note for id edits carries "<id> (<ctx>)"; the compact note form keeps
# just the ctx word)


# ===========================================================================
# classification of strings
# ===========================================================================

# Autodesk / Revit PRODUCT strings — machinery, never project data
_MACHINERY = re.compile(
    r"^(Autodesk Revit|Revit( \d{4}.*)?|ADSK|AREXRevitStart|AREXContentGenerator"
    r"|Revit Default DB Server|http[s]?://.*"
    r"|ColorFillSecondaryData|NobleDocWarnings|Rbs[A-Za-z]+|FamilyInstance"
    r"|PanelScheduleView|RevisionSettings|DBView[A-Za-z]*|IndependentTag"
    r"|LB_[A-Za-z]+|Element-Watching-Internal-Updater|ObjectNumberingUpdater"
    r"|TextNoteUpdater|.*Updater|Identity|TCHAR|AnalysisId|ResultsInvalid|int"
    r"|DaylightingAnalysisInfo|WireSizes\.xml)$")

# stock category / parameter / naming-scheme labels — Revit product content,
# NOT the sample project's authored expression (deliberately excluded from P1)
_CATEGORY = re.compile(
    r"^(Color Fills?|(Rooms|Areas|Spaces|HVAC Zones|Ducts|Pipes|Zones)( )?:( )?.*"
    r"|Space Name|Space Number|Size|(Connected |Demand )?(Apparent Power|Current)"
    r"|Number of Circuits|.*Numbering|Stairs System|Unassigned|Generic"
    r"|Room|Space|Zone|Level|3D Views|Renderings|Structural Plans|Floor Plans"
    r"|Ceiling Plans|Detail Views \(Detail\)|Drafting Views \(Detail\)"
    r"|Elevations \(Building Elevation\)|Sections \(Building Section\)"
    r"|Graphical Column Schedules|Schedules?|Legends?|Sheets?( \(all\))?)$")

# the LB reconcile map: '<elementId>.<n>.<counter>' text keys
_LBMAP = re.compile(r"^\d{4,9}\.\d{1,3}\.\d{4,9}$")

# a lowercase login-style username token
_USERNAME = re.compile(r"^[a-z][a-z0-9_.\-]{2,11}$")

# material-name signal
_MATERIAL = re.compile(r"(MPa|Concrete|Steel|Timber|Glass|Aluminium|Aluminum"
                       r"|Brick|Gypsum|Plaster|Insulation)", re.I)


def classify(strings: List[AStr], pairs: List[ForgePair], pay: bytes,
             build_range: Tuple[int, int]) -> None:
    """Assign a class to every census string (in place).

    Classes:
      forge.typeid / forge.json   the Forge corpus                (P3)
      build                       m_storedByRevitBuild strings   (machinery)
      machinery                   Autodesk / Revit product ids    (never touched)
      category                    stock category / param labels  (excluded)
      lb-map                      the reconcile-map id strings   (P6 only)
      user                        login usernames (lineage)       (P1)
      project.naming              sheet/view/assembly names+nos   (P1)
      project.room                room names                      (P1)
      project.material            material names                  (P1)
      unclassified                everything else (left alone)
    """
    forge_off = {}
    spans: List[Tuple[int, int]] = []
    for p in pairs:
        forge_off[p.t.off] = "forge.typeid"
        forge_off[p.j.off] = "forge.json"
        spans.append((p.t.off, p.j.end))
    spans.sort()
    starts = [a for a, _ in spans]
    b0, b1 = build_range
    import bisect
    for s in strings:
        if s.off in forge_off:
            s.cls = forge_off[s.off]
            continue
        k = bisect.bisect_right(starts, s.off) - 1
        if k >= 0 and spans[k][0] <= s.off < spans[k][1]:
            s.cls = "forge.inner"       # fragment inside a corpus document
            continue
        t = s.text
        if b0 <= s.off < b1:
            s.cls = "build"
        elif t.startswith('{"Id":'):
            s.cls = "lb-json"          # LB reconcile / metadata JSON records
        elif _MACHINERY.match(t):
            s.cls = "machinery"
        elif _LBMAP.match(t):
            s.cls = "lb-map"
        elif _CATEGORY.match(t):
            s.cls = "category"
        elif _USERNAME.match(t) and _is_username_context(pay, s):
            s.cls = "user"
        elif _is_naming_table_entry(pay, s):
            s.cls = "project.naming"
        elif _MATERIAL.search(t) and len(t) <= 40:
            s.cls = "project.material"
        elif re.fullmatch(r"[A-Z][A-Za-z0-9 &'\-]{2,30}", t):
            # residual capitalised free-text name in a name table (rooms live
            # in the ADocument's room-name table) -> project room/space name
            s.cls = "project.room"
        else:
            s.cls = "unclassified"
    # proximity pass: the LAST entry of the sheet/detail naming table is not
    # followed by a built-in id (the table ends), so admit any short
    # marker-prefixed name string within 48 bytes of an accepted naming entry.
    naming_spans = [(s.off, s.end) for s in strings if s.cls == "project.naming"]
    if naming_spans:
        for s in strings:
            if s.cls != "unclassified" or s.off < 4:
                continue
            if struct.unpack_from("<I", pay, s.off - 4)[0] not in (1, 2):
                continue
            if not re.fullmatch(r"[A-Za-z0-9 .&'()\-]{1,40}", s.text):
                continue
            if any(abs(s.off - e) <= 48 or abs(s.off - a) <= 48 for a, e in naming_spans):
                s.cls = "project.naming"


def _is_naming_table_entry(pay: bytes, s: AStr) -> bool:
    """u32 marker(1|2) precedes the string and a negative built-in id
    (category / parameter) immediately follows it => the sheet / view /
    assembly / detail-number registry."""
    if s.off < 4:
        return False
    marker = struct.unpack_from("<I", pay, s.off - 4)[0]
    if marker not in (1, 2):
        return False
    if s.end + 8 > len(pay):
        return False
    follow = struct.unpack_from("<q", pay, s.end)[0]
    return -3_000_000 < follow < -1000


def _is_username_context(pay: bytes, s: AStr) -> bool:
    """Usernames appear as a lone lowercase token preceded by a small u32
    marker (u32 1) — the DocumentIncrement / worksharing owner strings."""
    if s.off < 4:
        return False
    marker = struct.unpack_from("<I", pay, s.off - 4)[0]
    return marker in (1, 2, 3, 4)


# ===========================================================================
# analysis bundle
# ===========================================================================

@dataclasses.dataclass
class Analysis:
    base: str
    path: str
    payload: bytes
    prefix: bytes
    strings: List[AStr]
    pairs: List[ForgePair]
    id_hits: List[IdHit]
    valid_ids: Set[int]
    own_ids: Set[int]

    @property
    def p1_strings(self) -> List[AStr]:
        return [s for s in self.strings
                if s.cls in ("project.naming", "project.room", "project.material", "user")]

    @property
    def lbmap_strings(self) -> List[AStr]:
        return [s for s in self.strings if s.cls == "lb-map"]

    @property
    def lbjson_strings(self) -> List[AStr]:
        return [s for s in self.strings if s.cls == "lb-json"]

    def summary(self) -> Dict[str, Any]:
        from collections import Counter
        c = Counter(s.cls for s in self.strings)
        ids = {h.value for h in self.id_hits}
        return {
            "base": self.base, "path": os.path.relpath(self.path, ROOT),
            "latest_inflated_bytes": len(self.payload),
            "latest_sha256": hashlib.sha256(self.payload).hexdigest(),
            "prefix_hex": self.prefix.hex(),
            "string_classes": dict(c),
            "forge_pairs": len(self.pairs),
            "forge_bytes": sum((p.t.end - p.t.off) + (p.j.end - p.j.off) for p in self.pairs),
            "id_ref_hits": len(self.id_hits),
            "id_distinct": len(ids),
            "id_dangling_in_this_file": len(ids - self.own_ids),
            "id_hits_adjacent": sum(1 for h in self.id_hits if h.ctx == "id-adjacent"),
        }


def _build_string_range(pay: bytes) -> Tuple[int, int]:
    """The m_storedByRevitBuild list: right after the 0x53-byte prologue,
    u32 count then that many AStrings."""
    p = 0x53
    n = struct.unpack_from("<I", pay, p)[0]
    q = p + 4
    for _ in range(min(n, 64)):
        r = _read_astring(pay, q, 400, ascii_only=True)
        if r is None:
            break
        q += 4 + 2 * r[0]
    return p, q


def analyse(base: str, latest_path: Optional[str] = None) -> Analysis:
    cfg = BASES[base]
    path = latest_path or cfg["path"]
    with open_rvt(path) as d:
        prefix = d.prefix(STREAM)
        payload = d.inflate(STREAM, 0)
    valid = elem_ids_of(cfg["id_source"])
    own = elem_ids_of(path)
    strings = census_strings(payload)
    pairs = walk_forge_pairs(payload)
    covered = set()
    for s in strings:
        covered.update(range(s.off, s.end))
    for x in census_short_naming_entries(payload, {s.off for s in strings}):
        if not (covered & set(range(x.off, x.end))):
            strings.append(x)
    strings.sort(key=lambda s: s.off)
    classify(strings, pairs, payload, _build_string_range(payload))
    id_hits = scan_id_refs(payload, valid)
    return Analysis(base, path, payload, prefix, strings, pairs, id_hits, valid, own)


# ===========================================================================
# edits (all length-preserving)
# ===========================================================================

@dataclasses.dataclass
class Edit:
    off: int            # payload offset of the FIRST changed byte
    old: bytes
    new: bytes
    kind: str           # 'name' | 'json' | 'typeid' | 'id' | 'lb-map'
    note: str = ""

    def to_json(self) -> Dict[str, Any]:
        d = {"offset": self.off, "length": len(self.old), "kind": self.kind}
        if self.kind in ("name", "typeid", "lb-map"):
            d["before"] = self.old.decode("utf-16-le", "replace")
            d["after"] = self.new.decode("utf-16-le", "replace")
        elif self.kind in ("json", "lb-json"):
            d["before_head"] = self.old[:60].decode("utf-16-le", "replace")
            d["after_head"] = self.new[:60].decode("utf-16-le", "replace")
        elif self.kind == "id":
            d["before_id"] = struct.unpack("<q", self.old)[0]
            d["after_id"] = -1
        if self.note:
            d["note"] = self.note
        return d


def apply_edits(payload: bytes, edits: Sequence[Edit]) -> bytes:
    """Apply length-preserving byte edits; asserts nothing overlaps or shifts."""
    buf = bytearray(payload)
    spans: List[Tuple[int, int]] = []
    for e in edits:
        assert len(e.old) == len(e.new), f"edit @{e.off} changes length"
        assert bytes(buf[e.off:e.off + len(e.old)]) == e.old, \
            f"edit @{e.off} old bytes mismatch (overlap?)"
        buf[e.off:e.off + len(e.new)] = e.new
        spans.append((e.off, e.off + len(e.new)))
    spans.sort()
    for a, b in zip(spans, spans[1:]):
        assert a[1] <= b[0], f"overlapping edits {a} / {b}"
    assert len(buf) == len(payload)
    return bytes(buf)


# -- replacement text generators (deterministic, same char count) ---------

def neutral_name(cls: str, index: int, length: int) -> str:
    """Same-length neutral replacement, unique within its class.

    'Hall'(room)->'Rm09'; 'FOUNDATION-2700'(naming)->'Nm0000000000023';
    'macalis'(user)->'us00003'; 'Concrete 10 MPa'(material)->'Mt0000000000002'.
    Very short names (1..2 chars, e.g. sheet detail numbers) get distinct
    base-36 tokens of the same width ('a', 'b', ... / 'aa', 'ab', ...).
    """
    if length <= 0:
        return ""
    if length <= 2:
        alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
        n = index
        chars = []
        for _ in range(length):
            chars.append(alphabet[n % 36])
            n //= 36
        return "".join(reversed(chars))
    tag = {"project.room": "Rm", "project.naming": "Nm",
           "project.material": "Mt", "user": "us", "lb-map": "lb"}.get(cls, "Nx")
    body = str(index)
    s = tag + body.rjust(length - len(tag), "0")
    return s[-length:] if len(s) > length else s.ljust(length, "-")


def json_stub(typeid: str, length: int) -> str:
    """Length-identical minimal-but-VALID JSON self-stub for a Forge document:
    '{"typeid": "<typeid>"   ...   }' padded with spaces INSIDE the braces.
    Falls back to '{   }' when the typeid does not fit."""
    core = '{"typeid": "' + typeid + '"'
    if len(core) + 1 <= length:
        return core + " " * (length - len(core) - 1) + "}"
    return "{" + " " * (length - 2) + "}"


def scrub_lbmap(text: str, index: int) -> str:
    """'1046264.1.1471776' -> '9<index padded>.9.9<index padded>' keeping the
    exact dotted digit-field widths (neutral, unique per index)."""
    fields = text.split(".")
    out = []
    for k, f in enumerate(fields):
        if len(f) == 1:
            out.append("9")
        else:
            out.append(("9" + str(index).rjust(len(f) - 1, "0"))[-len(f):])
    return ".".join(out)


# -- edit builders ---------------------------------------------------------

def edits_names(an: Analysis, blank: bool) -> List[Edit]:
    edits: List[Edit] = []
    counters: Dict[str, int] = {}
    for s in an.p1_strings:
        key = (s.cls, s.nchars) if s.nchars <= 2 else (s.cls, 0)
        i = counters.get(key, 0)
        counters[key] = i + 1
        new = (" " * s.nchars) if blank else neutral_name(s.cls, i + 1, s.nchars)
        assert len(new) == s.nchars
        edits.append(Edit(s.data_off, _enc_astring_body(s.text), _enc_astring_body(new),
                          "name", f"{s.cls}"))
    return edits


def edits_forge(an: Analysis, mode: str) -> List[Edit]:
    """mode: 'stub' (valid minimal JSON, keys intact) | 'blank' (JSON ->
    spaces) | 'scrub' (JSON -> spaces AND typeids -> unique neutral)."""
    edits: List[Edit] = []
    for k, p in enumerate(an.pairs):
        if mode == "stub":
            new_j = json_stub(p.t.text, p.j.nchars)
        else:
            new_j = " " * p.j.nchars
        assert len(new_j) == p.j.nchars
        edits.append(Edit(p.j.data_off, _enc_astring_body(p.j.text),
                          _enc_astring_body(new_j), "json"))
        if mode == "scrub":
            new_t = ("nid." + str(k + 1)).ljust(p.t.nchars, "-")[:p.t.nchars]
            edits.append(Edit(p.t.data_off, _enc_astring_body(p.t.text),
                              _enc_astring_body(new_t), "typeid"))
    return edits


def edits_ids(an: Analysis) -> List[Edit]:
    minus1 = struct.pack("<q", -1)
    return [Edit(h.off, an.payload[h.off:h.off + 8], minus1, "id", h.ctx)
            for h in an.id_hits]


def edits_lbmap(an: Analysis) -> List[Edit]:
    """Scrub the LB reconcile map: the '<id>.<n>.<id>' keys AND their
    '{"Id":..,"LocalId":..,"ExternalId":..}' JSON records (which name the
    sample's element ids as TEXT — invisible to the binary id scan)."""
    edits: List[Edit] = []
    for i, s in enumerate(an.lbmap_strings):
        new = scrub_lbmap(s.text, i + 1)
        assert len(new) == s.nchars
        edits.append(Edit(s.data_off, _enc_astring_body(s.text), _enc_astring_body(new),
                          "lb-map"))
    for i, s in enumerate(an.lbjson_strings):
        m = re.match(r'\{"Id":\s*(\d+)', s.text)
        core = '{"Id":' + (m.group(1) if m else str(i + 1))
        if len(core) + 1 <= s.nchars:
            new = core + " " * (s.nchars - len(core) - 1) + "}"
        else:
            new = "{" + " " * (s.nchars - 2) + "}"
        assert len(new) == s.nchars
        edits.append(Edit(s.data_off, _enc_astring_body(s.text), _enc_astring_body(new),
                          "lb-json"))
    return edits


# ===========================================================================
# probe definitions
# ===========================================================================

PROBES: List[Dict[str, Any]] = [
    {"id": "P0_control", "order": 0,
     "title": "control: Latest re-encoded by us (gzip level 3 + sync-flush, real ECC), payload byte-identical",
     "question": "Is OUR re-encoding of Global/Latest (nothing else) accepted?  (V15 whole-file precedent says yes.)",
     "unlocks": "Nothing new — this is the yardstick.  If it FAILS the whole set is void and the fault is our Latest framing, not content."},
    {"id": "P1_names", "order": 1,
     "title": "every PROJECT-data name string replaced by same-length neutral text",
     "question": "Can the sample project's authored names (rooms, sheet nos/names, view names, assembly, materials, usernames) be renamed inside the ADocument without an encoder?",
     "unlocks": "PASS => genesis can strip ALL sample naming from Latest by length-preserving substitution TODAY (retires audit exhibit B2 'the sample's room/sheet names survive').  Bonus tell: if the sheet list still shows 'FOUNDATION-2700'/'S206', the Latest name registry is not the display source."},
    {"id": "P2_names_blank", "order": 3,
     "title": "the same project strings replaced by same-length SPACES",
     "question": "Must names be non-blank / unique, or is the text irrelevant?",
     "unlocks": "PASS => names need not even be meaningful (blank is fine).  FAIL while P1 passes => a non-empty / uniqueness rule exists; genesis must emit distinct neutral names, not blanks."},
    {"id": "P3a_forge_stub", "order": 2,
     "title": "every Forge (typeid, json) document body -> length-identical minimal valid JSON self-stub {\"typeid\": ...}; keys intact",
     "question": "Is the CONTENT of the ~1.3 MB Autodesk Forge unit/spec/parameter-group JSON corpus load-bearing, or a cache the reader ignores/rebuilds?",
     "unlocks": "PASS => the Forge corpus is NOT expression we must carry: genesis can regenerate it as trivial self-stubs (retires the audit's 78 % Forge byte share and counsel item (a)).  FAIL => document content is validated; test P3b next only if P3a passes."},
    {"id": "P3b_forge_blank", "order": 4,
     "title": "every Forge JSON body -> same-length SPACES (invalid JSON); keys intact",
     "question": "Are the JSON bodies PARSED at all at open time?",
     "unlocks": "PASS => bodies are never parsed (pure inert bytes) => the corpus can be blanked outright.  FAIL while P3a passes => JSON must be well-formed but content is free."},
    {"id": "P4_ids_null", "order": 1,
     "title": "every ElementId reference (i64) into the sample lineage remapped to -1 (invalid)",
     "question": "Are the ADocument's ~6,175 element-id references (registries / tables) load-bearing?  In G0 all are dangling; in rst all are live.",
     "unlocks": "G0_P4 PASS while G0 FAILS => the dangling ids were the killer and nulling them is the fix.  rst P4 PASS => id registries can be nulled wholesale (a -1 is tolerated even for live objects).  Both PASS => the id arrays are inert."},
    {"id": "P5_combined", "order": 2,
     "title": "P1 (names -> neutral) + P4 (ids -> -1) combined",
     "question": "Do the two most likely genesis operations compose?",
     "unlocks": "PASS => genesis-2 can ship a Latest with OUR names and NO sample-id references immediately (the whole 'sample lineage' complaint minus the Forge corpus)."},
    {"id": "P6_all", "order": 5,
     "title": "MAXIMAL sanitization: names blanked + Forge corpus blanked (typeids scrubbed too) + ids nulled + LB reconcile map (keys + JSON records) scrubbed",
     "question": "Can the ENTIRE Autodesk/sample expression inside Latest be removed length-preservingly with no encoder at all?",
     "unlocks": "PASS => the genesis-2 assembler needs NO ADocument encoder to close audit sections B1/B2 for Latest — a scrubbed Latest is shippable now.  FAIL with P1/P3b/P4 passing => the interaction or the typeid/LB scrub is at fault; bisect."},
]
PROBE_BY_ID = {p["id"]: p for p in PROBES}


def build_edits(an: Analysis, probe: str) -> List[Edit]:
    if probe == "P0_control":
        return []
    if probe == "P1_names":
        return edits_names(an, blank=False)
    if probe == "P2_names_blank":
        return edits_names(an, blank=True)
    if probe == "P3a_forge_stub":
        return edits_forge(an, "stub")
    if probe == "P3b_forge_blank":
        return edits_forge(an, "blank")
    if probe == "P4_ids_null":
        return edits_ids(an)
    if probe == "P5_combined":
        return edits_names(an, blank=False) + edits_ids(an)
    if probe == "P6_all":
        return (edits_names(an, blank=True) + edits_forge(an, "scrub")
                + edits_ids(an) + edits_lbmap(an))
    raise KeyError(probe)


# ===========================================================================
# emission
# ===========================================================================

def rewrite_latest(src_path: str, out_path: str, new_payload: bytes,
                   prefix: bytes) -> Dict[str, Any]:
    """Write ``out_path`` = ``src_path`` with ONLY Global/Latest replaced by
    prefix + gzip(new_payload) re-framed with real CRCIO ECC."""
    logical = prefix + gzip_member(new_payload, level=3, sync_flush=True)
    raw = ecc.frame_stream(logical)
    entries = read_entries(src_path)
    out_entries = []
    hit = False
    for e in entries:
        if e.entry_type == "stream" and e.path == STREAM:
            out_entries.append(dataclasses.replace(e, data=raw))
            hit = True
        else:
            out_entries.append(e)
    if not hit:
        raise RuntimeError(f"{src_path}: no {STREAM} stream")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    write_cfb(out_path, out_entries)
    return {"logical_bytes": len(logical), "raw_bytes": len(raw),
            "gzip_bytes": len(logical) - len(prefix)}


def self_verify(out_path: str, expect_payload: bytes, prefix: bytes) -> Dict[str, Any]:
    """Re-open the written probe: payload identity, prefix, gzip CRC, and a
    page-ECC re-encode check of the rewritten stream."""
    with open_rvt(out_path) as d:
        pay = d.inflate(STREAM, 0)
        pre = d.prefix(STREAM)
        members = d.members(STREAM)
        raw = d.raw(STREAM)
    ecc_bad = 0
    n_full = len(raw) // ecc.PAGE_STRIDE
    for k in range(n_full):
        page = raw[k * ecc.PAGE_STRIDE:k * ecc.PAGE_STRIDE + ecc.PAGE_PAYLOAD]
        tr = raw[k * ecc.PAGE_STRIDE + ecc.PAGE_PAYLOAD:(k + 1) * ecc.PAGE_STRIDE]
        if ecc.page_trailer(page) != tr:
            ecc_bad += 1
    return {
        "payload_identical_to_edited": pay == expect_payload,
        "payload_sha256": hashlib.sha256(pay).hexdigest(),
        "prefix_hex": pre.hex(),
        "prefix_ok": pre == prefix,
        "gzip_members": len(members),
        "gzip_crc_ok": all(m.crc_ok for m in members),
        "full_pages_ecc_checked": n_full,
        "full_pages_ecc_bad": ecc_bad,
    }


def validate_probe(out_path: str) -> Dict[str, Any]:
    """Structural + consistency + semantic validation (tools/rvt_validate.py)."""
    from rvt.validate import validate_file
    rep = validate_file(out_path)
    st = rep.stats
    line = (f"{'OK  ' if rep.ok else 'FAIL'} {os.path.relpath(out_path, ROOT)}  "
            f"errors={len(rep.errors)} warnings={len(rep.warnings)} | "
            f"streams={st.get('streams')} pages_checked={st.get('pages_checked')} "
            f"gzip_members={st.get('gzip_members')} partition_blocks={st.get('partition_blocks')} "
            f"records={st.get('records')} elements_decoded={st.get('elements_decoded')} "
            f"decode_failures={st.get('decode_failures')} refs_checked={st.get('refs_checked')}")
    return {"ok": rep.ok, "errors": len(rep.errors), "warnings": len(rep.warnings),
            "summary": line,
            "error_messages": [f.message for f in rep.errors][:8],
            "warning_messages": [f.message for f in rep.warnings][:4]}


def emit_probe(an: Analysis, probe: str, out_dir: str, run_validator: bool = True) -> Dict[str, Any]:
    cfg = BASES[an.base]
    pd = PROBE_BY_ID[probe]
    name = f"{cfg['prefix']}{probe}"
    out_rvt = os.path.join(out_dir, name + ".rvt")
    out_json = os.path.join(out_dir, name + ".json")
    edits = build_edits(an, probe)
    new_payload = apply_edits(an.payload, edits)
    t0 = time.time()
    sizes = rewrite_latest(an.path, out_rvt, new_payload, an.prefix)
    verify = self_verify(out_rvt, new_payload, an.prefix)
    val = validate_probe(out_rvt) if run_validator else {"ok": None, "summary": "not run"}
    # per-kind edit summary
    from collections import Counter
    kinds = Counter(e.kind for e in edits)
    kind_bytes = Counter()
    for e in edits:
        kind_bytes[e.kind] += len(e.old)
    note: Dict[str, Any] = {
        "probe": probe,
        "file": os.path.relpath(out_rvt, ROOT),
        "base": {"id": an.base, "path": os.path.relpath(an.path, ROOT),
                 "label": cfg["label"]},
        "title": pd["title"],
        "reader_question": pd["question"],
        "verdict_unlocks": pd["unlocks"],
        "method": ("ONLY Global/Latest is rewritten: prefix u64 5 kept, payload edited "
                   "in place (every edit byte-length-preserving => no offset shifts), "
                   "re-gzipped by our writer (zlib level 3 + sync-flush, mimics Revit), "
                   "re-framed with real CRCIO page ECC, container rebuilt with all other "
                   "streams copied byte-for-byte."),
        "latest": {"inflated_bytes": len(new_payload),
                   "sha256_base": hashlib.sha256(an.payload).hexdigest(),
                   "sha256_probe": hashlib.sha256(new_payload).hexdigest(),
                   "bytes_changed": sum(1 for a, b in zip(an.payload, new_payload) if a != b),
                   **sizes},
        "edits": {"count": len(edits), "by_kind": dict(kinds),
                  "bytes_by_kind": dict(kind_bytes),
                  # id edits are all "8 bytes at offset -> i64 -1"; kept compact as
                  # [offset, previous_id, context] triples; everything else in full
                  "id_ranges_compact": [[e.off, struct.unpack("<q", e.old)[0], e.note]
                                        for e in edits if e.kind == "id"],
                  "ranges": [e.to_json() for e in edits if e.kind != "id"]},
        "self_verification": verify,
        "validator": val,
        "elapsed_s": round(time.time() - t0, 2),
    }
    if probe.startswith("P4") or probe in ("P5_combined", "P6_all"):
        note["id_scan_caveat"] = (
            "id references are found by scanning every byte offset for a little-endian "
            "i64 whose value is a known ElemTable id of the lineage (> 4700); in-range "
            "NON-id windows also exist, so ~0.2 % of the nulled positions "
            "(~17 of 9,602 in rstbasic) may be non-id fields whose value coincides with a "
            "live id.  A PASS is unaffected; a FAIL carries this small ambiguity.")
    with open(out_json, "w") as f:
        json.dump(note, f, indent=2)
    return note


# ===========================================================================
# manifest / viewer queue
# ===========================================================================

def viewer_queue(notes: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Order the emitted probes by information value for the viewer queue.

    rst-base probes first (rst is a KNOWN-GOOD reader file, so every rst
    verdict attributes purely to the Latest edit); within a base by the
    probe's declared order; the G0 set follows, gated on G0.rvt's own
    (still unmeasured) viewer verdict.
    """
    rows = []
    for name, n in notes.items():
        pid = n["probe"]
        base = n["base"]["id"]
        rows.append({
            "file": n["file"], "probe": pid, "base": base,
            "order": (0 if base == "rst" else 1, PROBE_BY_ID[pid]["order"]),
            "title": n["title"], "question": n["reader_question"],
            "unlocks": n["verdict_unlocks"],
            "validator_ok": n["validator"]["ok"],
        })
    rows.sort(key=lambda r: r["order"])
    for i, r in enumerate(rows, 1):
        r["queue_position"] = i
        r["order"] = list(r["order"])
    return rows


DECISION_TABLE = [
    {"if": "P0_control PASSES", "then": "our Latest re-encode is sound (expected: whole-file V15 precedent); every other verdict is about CONTENT"},
    {"if": "P1_names PASSES", "then": "genesis can RENAME every project string in Latest by length-preserving substitution today — no encoder needed to retire the sample's room/sheet/view/material names and usernames (audit B2/B3 naming exhibits)"},
    {"if": "P2_names_blank PASSES", "then": "names carry no reader rule at all (blank is fine); if P2 FAILS but P1 PASSES, names must merely be non-empty/distinct"},
    {"if": "P3a_forge_stub PASSES", "then": "the ~1.3 MB Forge unit/spec/parameter-group JSON corpus is NOT load-bearing content: it can be regenerated as trivial self-stubs (retires the audit's 78 % Forge byte share; counsel question (a) shrinks to 'may we emit stubs naming Autodesk typeids')"},
    {"if": "P3b_forge_blank PASSES", "then": "the JSON bodies are never parsed at open — the corpus can be blanked outright (stronger than P3a)"},
    {"if": "P4_ids_null PASSES", "then": "the ADocument's element-id registries can be NULLED (-1) wholesale; on G0 this removes all 6,175 dangling sample-id references — the last id lineage into the sample"},
    {"if": "G0_P4 PASSES while G0 (unmodified) FAILS", "then": "dangling ids were G0's blocker and nulling is the fix"},
    {"if": "P5_combined PASSES", "then": "the two headline genesis operations compose: OUR names + NO sample-id references in one Latest"},
    {"if": "P6_all PASSES", "then": "MAXIMAL sanitization is accepted: genesis-2 needs NO ADocument encoder to close the Latest stream ledger — ship the scrubbed Latest, defer the encoder"},
    {"if": "everything FAILS but P0 passes", "then": "the ADocument content is validated in detail => the ADocument decoder->encoder (genesis.md 6.3) is unavoidably the critical path"},
]


# ===========================================================================
# CLI
# ===========================================================================

def print_analysis(an: Analysis) -> None:
    s = an.summary()
    print(f"== {an.base}: {s['path']}")
    print(f"   Latest inflated {s['latest_inflated_bytes']:,} bytes  sha256 {s['latest_sha256'][:16]}  prefix {s['prefix_hex']}")
    print(f"   strings by class: {json.dumps(s['string_classes'], sort_keys=True)}")
    print(f"   forge pairs {s['forge_pairs']:,} = {s['forge_bytes']:,} bytes "
          f"({100.0 * s['forge_bytes'] / max(1, s['latest_inflated_bytes']):.1f}% of stream)")
    print(f"   id refs {s['id_ref_hits']:,} occurrences / {s['id_distinct']:,} distinct ids; "
          f"dangling in this file: {s['id_dangling_in_this_file']:,}; "
          f"id-adjacent context: {s['id_hits_adjacent']:,}")
    print("   P1 target strings:")
    for x in an.p1_strings:
        print(f"     {x.cls:16s} @0x{x.off:06x}  {x.text!r}")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base", choices=["rst", "G0", "both"], default="both")
    ap.add_argument("--only", default="", help="comma list of probe ids (e.g. P1_names,P4_ids_null)")
    ap.add_argument("--out-dir", default=DEFAULT_OUT)
    ap.add_argument("--analyse", action="store_true", help="print the analysis and exit (no files)")
    ap.add_argument("--no-validate", action="store_true", help="skip the structural validator")
    a = ap.parse_args(argv)

    bases = ["rst", "G0"] if a.base == "both" else [a.base]
    only = [x.strip() for x in a.only.split(",") if x.strip()]
    probe_ids = only or [p["id"] for p in PROBES]
    for pid in probe_ids:
        if pid not in PROBE_BY_ID:
            print(f"unknown probe {pid!r}; known: {[p['id'] for p in PROBES]}")
            return 2

    notes: Dict[str, Dict[str, Any]] = {}
    analyses: Dict[str, Any] = {}
    for b in bases:
        if not os.path.exists(BASES[b]["path"]):
            print(f"[skip] base {b}: {BASES[b]['path']} not found")
            continue
        an = analyse(b)
        analyses[b] = an.summary()
        print_analysis(an)
        if a.analyse:
            continue
        for pid in probe_ids:
            t0 = time.time()
            n = emit_probe(an, pid, a.out_dir, run_validator=not a.no_validate)
            v = n["validator"]
            print(f"   -> {n['file']:60s} edits={n['edits']['count']:>6,} "
                  f"changed={n['latest']['bytes_changed']:>9,} B  "
                  f"{v.get('summary', '')[:80]}  ({time.time() - t0:.1f}s)")
            notes[os.path.basename(n["file"])] = n
    if a.analyse or not notes:
        return 0
    manifest = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tool": "tools/latest_probes.py",
        "purpose": ("Reader-tolerance probes of Global/Latest: what does Autodesk's "
                    "reader actually REQUIRE of the ADocument?  Each file edits ONLY "
                    "Global/Latest (length-preserving); a viewer PASS/FAIL attributes "
                    "to one class of content."),
        "bases": analyses,
        "viewer_queue": viewer_queue(notes),
        "decision_table": DECISION_TABLE,
        "prerequisite": ("Upload G0.rvt itself as the CONTROL for the G0_ set: no "
                         "G-rung has a recorded viewer verdict.  The rst set needs no "
                         "control beyond P0 (rstbasic is a known-good sample; the "
                         "whole-file rewrite V15 already passed)."),
        "probes": {k: {"file": v["file"], "edits": v["edits"]["count"],
                       "bytes_changed": v["latest"]["bytes_changed"],
                       "validator_ok": v["validator"]["ok"]}
                   for k, v in notes.items()},
    }
    mp = os.path.join(a.out_dir, "manifest.json")
    with open(mp, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nmanifest: {os.path.relpath(mp, ROOT)}  ({len(notes)} probes emitted)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
