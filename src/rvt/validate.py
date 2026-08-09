"""validate.py — the Autodesk-free arbiter of .rvt validity.

Layered checks, each producing findings ``{severity, layer, where, message}``
collected into one :class:`Report`:

L1 STRUCTURE  (``structure``)
    * CFB container opens (olefile), the expected stream inventory is
      present.
    * Page framing / ECC (``rvt.ecc``): every CRCIO block (each full
      64,896-byte page and the final partial block) of every framed stream
      is syndrome-verified against the file's OWN bits (255 bit-interleaved
      shortened-Hamming CRC-11 lanes per page).  Per lane a nonzero
      syndrome is exactly ONE correctable bit; we recover its position and
      classify:
        - correction lands in the trailer/pad region -> data intact ->
          WARNING (Revit's auto-repair "rescues" it; V9 acceptance proof);
        - correction lands in the payload -> the auto-repair rewrites data:
          <= 8 data bits per block (one damaged byte, the proven-accepted
          envelope) -> WARNING; more -> ERROR (uncorrectable / miscorrect);
        - no valid position (partial blocks) -> ERROR (uncorrectable).
      Downstream layers run on the ECC-REPAIRED logical stream — exactly
      what Revit's reader sees after auto-repair.
    * every gzip member of every framed stream inflates with a valid
      CRC32/ISIZE trailer.
    * ``Partitions/<N>`` block walker: zero framing errors, per-block gzip
      CRC ok, the ISIZE identity ``ISIZE == hdr_len(seq)*A + C + adj(flags)``
      holds, the 6-byte 0x0f21 block trailer mirrors B, seq in {101,102,103}.
    * record layer per save unit per seq: the record walk covers the whole
      segment, every record's trailing ``u32 psize`` repeat matches, the
      sentinel (id -1, psize 0) is the LAST record of every unit's per-seq
      segment, and every seq-102/103 record stamp == ``adler32(u16 class_id
      || object bytes)``.  Two of these are READER-TOLERATED (proven by the
      Autodesk oracle) and therefore WARNINGS by default / ERRORS only
      under ``strict``: a stale record stamp (V18 shipped a stale stamp and
      TRANSLATED) and the block-header A/C counter identity (V20-V29 carry
      the commit.py off-by-4*A counter defect and all TRANSLATED).  Every
      other structure finding is an error.

SEVERITY CALIBRATION (docs/writer/validation.md has the full matrix): the
default mode is calibrated to the Autodesk Model Derivative oracle — every
acceptance variant Autodesk PASSED validates with ZERO errors and every one
it FAILED validates with >= 1 error (29/29 experiments/acceptance files).
``strict`` is the stronger, writer-hygiene / circuit-ready gate: it also
escalates one-way connector links, stale stamps and the counter defect.

L2 CONSISTENCY  (``consistency``)
    * ``Global/ElemTable`` decodes; count == number of ElemRecs == the
      partition header count (u32 @ logical 14); ids strictly increasing and
      unique; watermark (footer last_id) >= max id.
    * ``Global/History`` decodes; count == max(ElemRec.modified_ep) + 1;
      format-version list ends with the file's release.
    * ``Global/DocumentIncrementTable`` decodes (both serialized copies
      equal); newest id_pair == (History count - 1, History count).
    * ``Contents`` decodes; its counters == the newest DIT counters with
      index 7 removed and Contents.G == DIT.G; ``BasicFileInfo`` decodes;
      'Unique Document Increments' == central version == DIT count and its
      Unique Document GUID == History entry[0].
    * every ElemTable id has a record in each seq (unit-0 seq-102 ids ==
      ElemTable ids EXACTLY) and the three seqs carry identical id sets in
      every save unit.

L3 SEMANTIC  (``semantic``, schema-driven)
    * every seq-102 record is decoded against the file's own
      ``Formats/Latest`` (``rvt.objects``); decode failures / stubs are
      counted (warning — the only known corpus gap is Extensible-Storage
      entity blobs).
    * REFERENCE INTEGRITY: every ElementId-typed value (schema type
      ``ElementId`` — this covers m_*Id, hostId, symbolId, levelId,
      m_arrRefs.m_id, connector refs, parents lists ...) must be > 0 and
      reference an existing element (any partition record id / ElemTable
      id), or be the invalid sentinel -1 / a negative built-in id.  A
      positive dangling id is an ERROR (0 across all six samples).
    * CONNECTOR GRAPH: for every connector edge A.conn[i] -> {B, j} the
      target element B must own connector j with a back-reference
      {A, i}.  One-way links (the exact defect we once shipped: cloned
      equipment referencing the template's circuits — V23/V27) do NOT make
      a file invalid — Autodesk's translator ACCEPTS such files (V23 and
      V27 both PASS) — but they corrupt the electrical connectivity model,
      so they are a WARNING by default (fix = scrub or complete the links,
      as V28 did) and an ERROR under ``strict=True`` (the "circuit-ready"
      gate that would have blocked the shipped defect).  Edges into a
      target that itself failed to decode are unverifiable (info count).
      A connector reference to an id that does not EXIST at all is a
      dangling ElementId and stays an ERROR (reference integrity).
    * HOSTING / TYPING: FamilyInstance ``m_symbolId`` / ``m_masterSymbolId``
      must resolve to a Symbol-derived class; ``*LevelId`` fields must
      resolve to a Level/DatumPlane; ``m_hostId`` (and all other ids) must
      resolve (covered by reference integrity).
    * CIRCUITS: an ``RbsElectricalSystem`` with a base connector must point
      it at itself with the index of its LAST connector; connectors indices
      unique.

Public API::

    rep = validate_file("model.rvt")          # -> Report
    rep.ok, rep.errors, rep.warnings
    print(rep.format_text())
    json.dump(rep.to_json(), fh)

CLI: ``tools/rvt_validate.py FILE.rvt [--json out.json] [--strict]``
(exit 0 = no errors).
"""
from __future__ import annotations

import struct
import time
import zlib
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

# LAZY (perf-coldstart): numpy is only exercised by the ECC syndrome /
# repair math; the validator's decode-tier checks are numpy-free, and a
# bare sandbox without numpy can still import + run them.
from ._lazyimp import lazy_import

np = lazy_import("numpy", globals(), "np", hint="ECC page syndrome math")

import olefile

from . import ecc
from .partitions import StreamWalker, record_header_len

# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------

SEV_ERROR = "error"
SEV_WARNING = "warning"
SEV_INFO = "info"

L_STRUCTURE = "structure"
L_CONSISTENCY = "consistency"
L_SEMANTIC = "semantic"
ALL_LAYERS = (L_STRUCTURE, L_CONSISTENCY, L_SEMANTIC)

#: streams whose parsers consume every byte as content (NO CRCIO paging)
UNFRAMED_STREAMS = frozenset({
    "BasicFileInfo", "ProjectInformation", "TransmissionData", "RevitPreview4.0",
})

#: the stable Revit-2026 stream inventory (all six samples)
REQUIRED_STREAMS = (
    "BasicFileInfo", "Contents", "ProjectInformation", "TransmissionData",
    "Formats/Latest", "Global/Latest", "Global/ElemTable",
    "Global/PartitionTable", "Global/ContentDocuments", "Global/History",
    "Global/DocumentIncrementTable",
)
OPTIONAL_STREAMS = ("RevitPreview4.0",)

#: known per-stream 8-byte prefixes of the Global/* streams (u64 constant)
GLOBAL_PREFIX_VALUE = {
    "Global/Latest": 5, "Global/ContentDocuments": 1,
    "Global/DocumentIncrementTable": 1, "Global/History": 1,
    "Global/ElemTable": 0, "Global/PartitionTable": 0,
}

#: the canonical Revit-2026 schema (Formats/Latest inflated)
SCHEMA_2026_SIZE = 496_597
SCHEMA_2026_SHA256 = "6459a9a93ebde32c26e4190de2756bf7a4592e63a0d142feca43c392ecdf8ac2"

#: proven-accepted auto-repair envelope: one damaged byte = 8 single-bit
#: corrections (V9: one flipped trailer byte translated successfully)
MAX_SAFE_DATA_REPAIRS_PER_BLOCK = 8

_ISIZE_ADJ = {4: 0, 5: 4, 6: -4, 7: 0}
_INVALID_U64 = 0xFFFFFFFFFFFFFFFF


def _as_int(v: Any) -> Optional[int]:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# findings / report
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    severity: str          # error | warning | info
    layer: str             # structure | consistency | semantic
    where: str             # stream / element / block locator
    message: str

    def to_json(self) -> dict:
        return {"severity": self.severity, "layer": self.layer,
                "where": self.where, "message": self.message}


@dataclass
class Report:
    path: str
    findings: List[Finding] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)
    timings: Dict[str, float] = field(default_factory=dict)
    layers: Tuple[str, ...] = ALL_LAYERS

    # -- collection --------------------------------------------------------
    def add(self, severity: str, layer: str, where: str, message: str) -> None:
        self.findings.append(Finding(severity, layer, where, message))

    def error(self, layer: str, where: str, message: str) -> None:
        self.add(SEV_ERROR, layer, where, message)

    def warn(self, layer: str, where: str, message: str) -> None:
        self.add(SEV_WARNING, layer, where, message)

    def info(self, layer: str, where: str, message: str) -> None:
        self.add(SEV_INFO, layer, where, message)

    # -- views ---------------------------------------------------------------
    @property
    def errors(self) -> List[Finding]:
        return [f for f in self.findings if f.severity == SEV_ERROR]

    @property
    def warnings(self) -> List[Finding]:
        return [f for f in self.findings if f.severity == SEV_WARNING]

    @property
    def infos(self) -> List[Finding]:
        return [f for f in self.findings if f.severity == SEV_INFO]

    @property
    def ok(self) -> bool:
        return not self.errors

    def by_layer(self, layer: str) -> List[Finding]:
        return [f for f in self.findings if f.layer == layer]

    def messages(self, severity: Optional[str] = None,
                 layer: Optional[str] = None) -> List[str]:
        return [f.message for f in self.findings
                if (severity is None or f.severity == severity)
                and (layer is None or f.layer == layer)]

    # -- output ----------------------------------------------------------
    def to_json(self) -> dict:
        return {
            "path": self.path,
            "ok": self.ok,
            "layers": list(self.layers),
            "counts": {"error": len(self.errors), "warning": len(self.warnings),
                       "info": len(self.infos)},
            "stats": self.stats,
            "timings": {k: round(v, 3) for k, v in self.timings.items()},
            "findings": [f.to_json() for f in self.findings],
        }

    def format_text(self, max_findings: int = 60) -> str:
        lines = []
        verdict = "VALID (no errors)" if self.ok else f"INVALID ({len(self.errors)} error(s))"
        lines.append(f"rvt-validate: {self.path}")
        lines.append(f"  verdict: {verdict}; warnings={len(self.warnings)} "
                     f"info={len(self.infos)}; layers={','.join(self.layers)}")
        for k in ("streams", "pages_checked", "gzip_members", "partition_blocks",
                  "records", "elements_decoded", "decode_failures",
                  "refs_checked", "connector_edges"):
            if k in self.stats:
                lines.append(f"  {k}: {self.stats[k]}")
        if self.timings:
            t = ", ".join(f"{k}={v:.1f}s" for k, v in self.timings.items())
            lines.append(f"  timings: {t}")
        shown = 0
        for f in self.findings:
            if f.severity == SEV_INFO:
                continue
            if shown >= max_findings:
                lines.append(f"  ... {len(self.errors) + len(self.warnings) - shown} more")
                break
            lines.append(f"  [{f.severity.upper():7s}] {f.layer:11s} {f.where}: {f.message}")
            shown += 1
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# L1 — ECC / page framing (numpy syndrome decoder)
# ---------------------------------------------------------------------------

_SIG_CACHE: Dict[Tuple[int, int, int], Dict[int, int]] = {}


def _signature_table(m: int, poly: int, period: int) -> Dict[int, int]:
    """syndrome -> distance-from-end for a single-bit error (per lane)."""
    key = (m, poly, period)
    tab = _SIG_CACHE.get(key)
    if tab is None:
        tab = {}
        c = poly                      # state right after injecting a 1-bit
        for d in range(period):
            tab.setdefault(c, d)
            fb = c & 1
            c >>= 1
            if fb:
                c ^= poly
        _SIG_CACHE[key] = tab
    return tab


def _syndromes(blocks: np.ndarray, first: int, second: int, poly: int) -> np.ndarray:
    """Per-lane CRC syndromes for a batch of encoded blocks.

    ``blocks``: (P, block_bytes) uint8.  Returns (P, second) uint16; a valid
    codeword has an all-zero syndrome row.  Bit p of the codeword belongs to
    lane p % second, round p // second (bit-interleaved).
    """
    P = blocks.shape[0]
    nb = first * second
    bits = np.unpackbits(blocks[:, :(nb + 7) // 8], axis=1, bitorder="little")[:, :nb]
    bits = bits.reshape(P, first, second).transpose(1, 0, 2).reshape(first, P * second)
    c = np.zeros(P * second, dtype=np.uint16)
    p16 = np.uint16(poly)
    for r in range(first):
        fb = (c ^ bits[r]) & np.uint16(1)
        c >>= np.uint16(1)
        c ^= fb * p16
    return c.reshape(P, second)


@dataclass
class _BlockGeom:
    params: Tuple[int, int, int, int]
    data_len: int
    first: int
    second: int


def _candidate_final_geometries(tail: bytes) -> List[_BlockGeom]:
    """Every CRCIO parameter class whose pad-count field self-consistently
    decodes this final (partial) block's data length.  The right one is the
    candidate whose syndrome check comes out clean (or, for a damaged block,
    the one needing the fewest corrections)."""
    L = len(tail)
    out: List[_BlockGeom] = []
    for params in ecc.PARAM_CLASSES:
        m, poly, period, align = params
        pre, N = ecc._block_data_len(L, params)
        if pre <= N or (pre + 7) // 8 > L:
            continue
        fpos = pre - N
        pad = 0
        for k in range(N):
            q = fpos + k
            if (tail[q >> 3] >> (q & 7)) & 1:
                pad |= 1 << k
        data_len = ((pre - N) >> 3) - pad
        if not (0 <= data_len <= L):
            continue
        if ecc.select_params(data_len) != params:
            continue
        if ecc.encoded_size(data_len, m, period, align, N) != L:
            continue
        first, second = ecc.geometry(data_len, m, period, align, N)
        out.append(_BlockGeom(params, data_len, first, second))
    return out


@dataclass
class _EccStreamResult:
    logical: bytes
    pages: int = 0
    lanes_corrected: int = 0
    data_bits_repaired: int = 0
    trailer_bits_repaired: int = 0
    uncorrectable_blocks: int = 0


def _repair_block(block: bytearray, syn_row: np.ndarray, geom_first: int,
                  geom_second: int, params, data_len: int) -> Tuple[int, int, int, bool]:
    """Apply the per-lane single-bit corrections implied by the syndromes.

    Returns (n_lanes_corrected, n_data_flips, n_other_flips, uncorrectable).
    ``block`` is mutated in place.
    """
    m, poly, period, _align = params
    tab = _signature_table(m, poly, period)
    n_corr = n_data = n_other = 0
    uncorrectable = False
    data_bits = data_len * 8
    for lane in np.nonzero(syn_row)[0]:
        s = int(syn_row[lane])
        d = tab.get(s)
        n_corr += 1
        if d is None or (geom_first - 1 - d) < 0:
            uncorrectable = True
            continue
        r = geom_first - 1 - d
        p = r * geom_second + int(lane)
        if (p >> 3) < len(block):
            block[p >> 3] ^= 1 << (p & 7)
        if p < data_bits:
            n_data += 1
        else:
            n_other += 1
    return n_corr, n_data, n_other, uncorrectable


def _numpy_available() -> bool:
    if "_np_ok" not in _NP_STATE:
        try:
            import numpy                                     # noqa: F401
            _NP_STATE["_np_ok"] = True
        except ImportError:
            _NP_STATE["_np_ok"] = False
    return _NP_STATE["_np_ok"]


_NP_STATE: dict = {}


def ecc_verify_stream(name: str, raw: bytes, rep: Report,
                      batch: int = 64) -> _EccStreamResult:
    """Syndrome-verify every CRCIO block of a framed stream and return the
    ECC-repaired logical stream.  Emits ECC findings on ``rep``.

    Without numpy (a bare zero-pip surface) the syndrome math cannot run:
    the stream is unframed with the pure-python reader and ONE warning per
    report says the ECC pages went unverified -- an unavailable checker is
    an environment gap, not a file defect (the deliverable rule), and every
    other structure check still runs on the logical bytes."""
    res = _EccStreamResult(b"")
    out = bytearray()
    n_full = len(raw) // ecc.PAGE_STRIDE
    where = f"{name}"

    if not _numpy_available():
        res.logical = ecc.unframe_stream(raw)
        res.pages += n_full + (1 if raw[n_full * ecc.PAGE_STRIDE:] else 0)
        if not getattr(rep, "_ecc_skip_warned", False):
            rep._ecc_skip_warned = True
            rep.warn(L_STRUCTURE, where,
                     "ECC page verification SKIPPED: numpy not installed "
                     "(pages unframed without syndrome checks; install numpy "
                     "for full verification)")
        return res

    # ---- full pages (fixed params, batched) --------------------------------
    if n_full:
        params = ecc.PARAM_CLASSES[0]                       # (11,0x500,2047,2)
        first, second = 2047, 255
        arr = np.frombuffer(raw[:n_full * ecc.PAGE_STRIDE],
                            dtype=np.uint8).reshape(n_full, ecc.PAGE_STRIDE)
        syn_all = []
        for s0 in range(0, n_full, batch):
            syn_all.append(_syndromes(arr[s0:s0 + batch], first, second, params[1]))
        syn = np.concatenate(syn_all) if syn_all else np.zeros((0, second), np.uint16)
        bad_pages = np.nonzero(syn.any(axis=1))[0]
        pages_mut = None
        for k in bad_pages:
            if pages_mut is None:
                pages_mut = bytearray(raw[:n_full * ecc.PAGE_STRIDE])
            blk = bytearray(pages_mut[k * ecc.PAGE_STRIDE:(k + 1) * ecc.PAGE_STRIDE])
            nc, nd, nt, unc = _repair_block(blk, syn[k], first, second, params,
                                            ecc.PAGE_PAYLOAD)
            if _correctable(nd, unc):
                # single-bit-per-lane repairs Revit itself performs: hand the
                # repaired page to the downstream layers (what Revit sees)
                pages_mut[k * ecc.PAGE_STRIDE:(k + 1) * ecc.PAGE_STRIDE] = blk
            # else: beyond the auto-repair envelope — the "corrections" are
            # guesses (a zeroed/foreign trailer), so keep the ORIGINAL bytes
            res.lanes_corrected += nc
            res.data_bits_repaired += nd
            res.trailer_bits_repaired += nt
            _classify_block(rep, where, f"page {k}", nc, nd, nt, unc, res)
        if pages_mut is not None:
            src = bytes(pages_mut)
            for k in range(n_full):
                out += src[k * ecc.PAGE_STRIDE:k * ecc.PAGE_STRIDE + ecc.PAGE_PAYLOAD]
        else:
            for k in range(n_full):
                out += raw[k * ecc.PAGE_STRIDE:k * ecc.PAGE_STRIDE + ecc.PAGE_PAYLOAD]
        res.pages += n_full

    # ---- final partial block --------------------------------------------------
    tail = raw[n_full * ecc.PAGE_STRIDE:]
    if tail:
        cands = _candidate_final_geometries(tail)
        if not cands:
            rep.error(L_STRUCTURE, where,
                      f"final block ({len(tail)} bytes) is not CRCIO-framed "
                      "(no size class + pad-count field decodes it)")
            out += tail          # fall back: pass the raw tail through
        else:
            best = None
            best_syn = None
            arr = np.frombuffer(tail, dtype=np.uint8)[None, :]
            for g in cands:
                syn = _syndromes(arr, g.first, g.second, g.params[1])[0]
                if best is None or int((syn != 0).sum()) < int((best_syn != 0).sum()):
                    best, best_syn = g, syn
                if not syn.any():
                    break
            g, syn = best, best_syn
            blk = bytearray(tail)
            if syn.any():
                nc, nd, nt, unc = _repair_block(blk, syn, g.first, g.second,
                                                g.params, g.data_len)
                res.lanes_corrected += nc
                res.data_bits_repaired += nd
                res.trailer_bits_repaired += nt
                _classify_block(rep, where, "final block", nc, nd, nt, unc, res)
                if not _correctable(nd, unc):
                    blk = bytearray(tail)      # keep original bytes downstream
            out += bytes(blk[:g.data_len])
            res.pages += 1
    res.logical = bytes(out)
    return res


def _correctable(nd: int, unc: bool) -> bool:
    """True when the syndromes describe damage inside the proven-accepted
    CRCIO auto-repair envelope (single-bit-per-lane, <= one damaged data
    byte per block) — the exact class of file V9 proved Autodesk repairs."""
    return (not unc) and nd <= MAX_SAFE_DATA_REPAIRS_PER_BLOCK


def _classify_block(rep: Report, where: str, blk: str, nc: int, nd: int,
                    nt: int, unc: bool, res: _EccStreamResult) -> None:
    if unc:
        res.uncorrectable_blocks += 1
        rep.error(L_STRUCTURE, where,
                  f"{blk}: ECC uncorrectable ({nc} damaged lane(s) with no valid "
                  f"error position) — data corrupt beyond CRCIO auto-repair")
    elif nd > MAX_SAFE_DATA_REPAIRS_PER_BLOCK:
        res.uncorrectable_blocks += 1
        rep.error(L_STRUCTURE, where,
                  f"{blk}: ECC damage across {nc} lane(s) implies rewriting "
                  f"{nd} payload bits — beyond the proven auto-repair envelope "
                  f"({MAX_SAFE_DATA_REPAIRS_PER_BLOCK}); treated as uncorrectable "
                  f"(a zeroed/foreign trailer looks exactly like this)")
    elif nd:
        rep.warn(L_STRUCTURE, where,
                 f"{blk}: {nd} payload bit(s) + {nt} trailer bit(s) auto-repairable "
                 f"by CRCIO ECC ({nc} lane(s)); Revit repairs on load — regenerate "
                 f"the file to make it clean")
    else:
        rep.warn(L_STRUCTURE, where,
                 f"{blk}: trailer damaged ({nt} parity bit(s) in {nc} lane(s)); "
                 f"payload intact, single-bit-per-lane correctable (Revit rescues "
                 f"these) — regenerate to make it clean")


# ---------------------------------------------------------------------------
# L1 — gzip members of a logical stream
# ---------------------------------------------------------------------------

_GZIP_MAGIC = b"\x1f\x8b\x08"


def _gzip_members(logical: bytes) -> List[Tuple[int, int, int, bool]]:
    """[(offset, consumed, inflated_len, crc_ok)] of every gzip member."""
    out = []
    pos = 0
    while True:
        i = logical.find(_GZIP_MAGIC, pos)
        if i < 0:
            return out
        d = zlib.decompressobj(16 + zlib.MAX_WBITS)
        try:
            payload = d.decompress(logical[i:]) + d.flush()
            consumed = len(logical) - i - len(d.unused_data)
            out.append((i, consumed, len(payload), True))
            pos = i + max(consumed, 1)
        except zlib.error:
            # not inflatable with the strict wrapper: try raw (CRC not verified)
            d2 = zlib.decompressobj(-zlib.MAX_WBITS)
            try:
                payload = d2.decompress(logical[i + 10:]) + d2.flush()
                consumed = len(logical) - i - len(d2.unused_data)
                out.append((i, consumed, len(payload), False))
                pos = i + max(consumed, 1)
            except zlib.error:
                pos = i + 1


def _inflate_first(logical: bytes) -> Optional[bytes]:
    """Payload of the FIRST gzip member (CRC verified) or None."""
    i = logical.find(_GZIP_MAGIC)
    if i < 0:
        return None
    d = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        return d.decompress(logical[i:]) + d.flush()
    except zlib.error:
        return None


# ---------------------------------------------------------------------------
# record layer helpers
# ---------------------------------------------------------------------------

@dataclass
class _Rec:
    seq: int
    unit: int
    elem_id: int
    stamp: int
    body_size: int
    class_id: int
    payload_off: int          # offset of the payload (class id) in the segment
    trailer_ok: bool


def _iter_seg_records(seg: bytes, seq: int, unit: int) -> Iterable[_Rec]:
    """Uniform record framing (see rvt.objects.iter_records)."""
    hlen = 12 if seq == 101 else 16
    p = 0
    n = len(seg)
    while p + hlen + 4 <= n:
        if seq == 101:
            eid, size = struct.unpack_from("<qI", seg, p)
            stamp = 0
        else:
            eid, stamp, size = struct.unpack_from("<qII", seg, p)
        if not (-1 <= eid < (1 << 40)) or size > (1 << 30):
            return
        if p + hlen + size + 4 > n:
            return
        tail = p + hlen + size
        rep_ok = struct.unpack_from("<I", seg, tail)[0] == size
        cls = struct.unpack_from("<H", seg, p + hlen)[0] if size >= 2 else 0
        yield _Rec(seq, unit, eid, stamp, size, cls, p + hlen, rep_ok)
        p = tail + 4


# ---------------------------------------------------------------------------
# the validator
# ---------------------------------------------------------------------------

class Validator:
    """Runs the layered checks over one .rvt file and fills a Report."""

    def __init__(self, path: str, layers: Iterable[str] = ALL_LAYERS,
                 decode_limit: Optional[int] = None, strict: bool = False,
                 family: bool = False):
        self.path = path
        self.layers = tuple(l for l in ALL_LAYERS if l in set(layers))
        self.decode_limit = decode_limit
        # strict = the "circuit-ready" gate: one-way connector links (which
        # Autodesk's translator tolerates) become errors instead of warnings
        self.strict = strict
        # family = the TWO family-shape adjustments (the long-recorded
        # `rvt_validate --family` request): a family file carries PartAtom
        # (plain unframed Atom XML) in place of ProjectInformation.  Every
        # other check -- container, ECC, gzip, walker, schema decode, table
        # decodes, reference integrity -- is identical in both modes.
        self.family = bool(family)
        self.required_streams = (tuple(s for s in REQUIRED_STREAMS
                                       if s != "ProjectInformation")
                                 if family else REQUIRED_STREAMS)
        self.unframed_streams = (frozenset(set(UNFRAMED_STREAMS) | {"PartAtom"})
                                 if family else UNFRAMED_STREAMS)
        self.rep = Report(path, layers=self.layers)
        self.ole: Optional[olefile.OleFileIO] = None
        self.names: List[str] = []
        self.logical: Dict[str, bytes] = {}          # ECC-repaired logical streams
        # decoded structures shared between layers
        self.elemtable: Optional[Dict[str, Any]] = None
        self.et_ids: List[int] = []
        self.part_walkers: Dict[str, StreamWalker] = {}
        self.unit_segments: Dict[str, Dict[Tuple[int, int], bytes]] = {}
        self.schema = None

    # ------------------------------------------------------------------
    def run(self) -> Report:
        t0 = time.time()
        try:
            self._open()
            if L_STRUCTURE in self.layers:
                t = time.time()
                self._layer_structure()
                self.rep.timings["structure"] = time.time() - t
            if L_CONSISTENCY in self.layers:
                t = time.time()
                self._layer_consistency()
                self.rep.timings["consistency"] = time.time() - t
            if L_SEMANTIC in self.layers:
                t = time.time()
                self._layer_semantic()
                self.rep.timings["semantic"] = time.time() - t
        finally:
            if self.ole is not None:
                self.ole.close()
        self.rep.timings["total"] = time.time() - t0
        return self.rep

    # -- container -----------------------------------------------------------
    def _open(self) -> None:
        rep = self.rep
        if not olefile.isOleFile(self.path):
            rep.error(L_STRUCTURE, "container", "not an OLE2/CFB compound file")
            raise _Abort()
        try:
            self.ole = olefile.OleFileIO(self.path)
        except Exception as e:                       # pragma: no cover
            rep.error(L_STRUCTURE, "container", f"CFB open failed: {e}")
            raise _Abort()
        self.names = ["/".join(p) for p in self.ole.listdir(streams=True, storages=False)]
        self.rep.stats["streams"] = len(self.names)

    def raw(self, name: str) -> bytes:
        assert self.ole is not None
        return self.ole.openstream(name.split("/")).read()

    def partition_names(self) -> List[str]:
        return sorted(n for n in self.names if n.startswith("Partitions/"))

    # ==================================================================
    # L1 STRUCTURE
    # ==================================================================
    def _layer_structure(self) -> None:
        rep = self.rep
        names = set(self.names)
        # -- inventory --------------------------------------------------------
        for req in self.required_streams:
            if req not in names:
                rep.error(L_STRUCTURE, req, "expected stream is missing")
        if not self.partition_names():
            rep.error(L_STRUCTURE, "Partitions/<N>", "no Partitions/<N> stream")
        for opt in OPTIONAL_STREAMS:
            if opt not in names:
                rep.info(L_STRUCTURE, opt, "optional stream absent (allowed)")

        # -- ECC + logical extraction for every stream --------------------------
        pages = 0
        for name in self.names:
            raw = self.raw(name)
            if name in self.unframed_streams:
                self.logical[name] = raw
                continue
            res = ecc_verify_stream(name, raw, rep)
            pages += res.pages
            self.logical[name] = res.logical
        rep.stats["pages_checked"] = pages

        # -- gzip members ---------------------------------------------------------
        n_members = 0
        for name in self.names:
            if name in self.unframed_streams or name.startswith("Partitions/"):
                continue
            logical = self.logical[name]
            members = _gzip_members(logical)
            n_members += len(members)
            if not members:
                rep.error(L_STRUCTURE, name, "no gzip member found in framed stream")
                continue
            bad = [m for m in members if not m[3]]
            if bad:
                rep.error(L_STRUCTURE, name,
                          f"{len(bad)}/{len(members)} gzip member(s) fail CRC32/ISIZE "
                          f"(first bad at logical offset {bad[0][0]})")
            # Global/* prefix constants
            if name in GLOBAL_PREFIX_VALUE and len(logical) >= 8:
                v = struct.unpack_from("<Q", logical, 0)[0]
                if v != GLOBAL_PREFIX_VALUE[name]:
                    rep.warn(L_STRUCTURE, name,
                             f"stream prefix u64 = {v}, expected "
                             f"{GLOBAL_PREFIX_VALUE[name]} (per-stream constant)")
        rep.stats["gzip_members"] = n_members

        # -- schema stream identity (informational) --------------------------------
        if "Formats/Latest" in self.logical:
            sch = _inflate_first(self.logical["Formats/Latest"])
            if sch is None:
                rep.error(L_STRUCTURE, "Formats/Latest", "schema does not inflate")
            else:
                import hashlib
                if len(sch) == SCHEMA_2026_SIZE and \
                        hashlib.sha256(sch).hexdigest() == SCHEMA_2026_SHA256:
                    rep.info(L_STRUCTURE, "Formats/Latest",
                             "canonical Revit 2026 archive schema (byte-identical)")
                else:
                    rep.warn(L_STRUCTURE, "Formats/Latest",
                             f"schema is {len(sch):,} bytes, not the canonical Revit "
                             f"2026 schema ({SCHEMA_2026_SIZE:,}); the semantic layer "
                             f"runs against the file's own schema")

        # -- partitions: block framing, gzip CRC, ISIZE identity, records --------
        n_blocks = 0
        n_records = 0
        for pname in self.partition_names():
            logical = self.logical.get(pname, b"")
            if len(logical) < 18:
                rep.error(L_STRUCTURE, pname, "partition stream too short")
                continue
            try:
                w = StreamWalker(logical, inflate=True, keep_data=True)
            except Exception as e:
                rep.error(L_STRUCTURE, pname, f"partition header/framing: {e}")
                continue
            self.part_walkers[pname] = w
            for msg in w.errors:
                rep.error(L_STRUCTURE, pname, f"block walker: {msg}")
            n_blocks += len(w.blocks)
            n_records += self._check_blocks_and_records(pname, w)
        rep.stats["partition_blocks"] = n_blocks
        rep.stats["records"] = n_records

    # ------------------------------------------------------------------
    def _check_blocks_and_records(self, pname: str, w: StreamWalker) -> int:
        rep = self.rep
        crc_bad = isize_bad = trl_bad = seq_bad = 0
        for b in w.blocks:
            if b.crc_ok is False:
                crc_bad += 1
            if b.data is not None and len(b.data) != b.intended_len:
                isize_bad += 1
            if not b.trailer_ok:
                trl_bad += 1
            if b.seq not in (101, 102, 103):
                seq_bad += 1
        if crc_bad:
            rep.error(L_STRUCTURE, pname, f"{crc_bad}/{len(w.blocks)} block gzip member(s) "
                      "fail CRC32/ISIZE")
        if isize_bad:
            # The block payload inflates with a VALID CRC32/ISIZE (else crc_bad
            # fires), so the data is intact; only the header counters A/C
            # disagree with Autodesk's convention (exact on all 13,535 corpus
            # blocks).  Revit's reader tolerates this (our accepted files
            # V20-V29 carry exactly this off-by-4*A on their 3 rewritten
            # blocks: commit.py computes C with the 12/16-byte header
            # convention instead of 16/20) — so it is a writer defect to
            # fix, not a rejection: WARNING (ERROR under strict).
            emit = rep.error if self.strict else rep.warn
            emit(L_STRUCTURE, pname, f"{isize_bad} block(s) whose header counters A/C "
                 "violate the corpus identity hdr_len(seq)*A + C + adj(flags) == "
                 "inflated length (payload CRC-valid; tolerated by Revit's reader — "
                 "proven by the accepted V20-V29 — but a writer counter defect; "
                 f"{'ERROR under strict' if self.strict else 'strict makes it an error'})")
        if trl_bad:
            rep.error(L_STRUCTURE, pname, f"{trl_bad} block(s) whose 6-byte 0x0f21 trailer "
                      "does not mirror B / is displaced")
        if seq_bad:
            rep.warn(L_STRUCTURE, pname, f"{seq_bad} block(s) with a seq id outside "
                     "101/102/103")

        # -- per unit, per seq: segments, record walk, sentinels, stamps ------------
        seg: Dict[Tuple[int, int], bytearray] = defaultdict(bytearray)
        for b in sorted(w.blocks, key=lambda x: x.hdr_offset):
            if b.data:
                seg[(b.unit, b.seq)] += b.data
        segments = {k: bytes(v) for k, v in seg.items()}
        self.unit_segments[pname] = segments
        n_records = 0
        stamp_bad = 0
        rep_bad = 0
        walk_partial: List[str] = []
        sentinel_bad: List[str] = []
        for (unit, s), buf in sorted(segments.items()):
            last: Optional[_Rec] = None
            endp = 0
            for r in _iter_seg_records(buf, s, unit):
                n_records += 1
                last = r
                endp = r.payload_off + r.body_size + 4
                if not r.trailer_ok:
                    rep_bad += 1
                if s != 101:
                    body = buf[r.payload_off:r.payload_off + r.body_size]
                    if (zlib.adler32(body) & 0xFFFFFFFF) != r.stamp:
                        stamp_bad += 1
            if endp != len(buf):
                walk_partial.append(f"u{unit}/seq{s} ({endp:,}/{len(buf):,})")
            if last is None or not (last.elem_id == -1 and last.body_size == 0):
                sentinel_bad.append(f"u{unit}/seq{s}")
        if walk_partial:
            rep.error(L_STRUCTURE, pname, "record walk does not cover the segment: "
                      + ", ".join(walk_partial[:6])
                      + (f" (+{len(walk_partial)-6})" if len(walk_partial) > 6 else ""))
        if sentinel_bad:
            rep.error(L_STRUCTURE, pname, "save-unit sentinel (id -1, psize 0) is not "
                      "the LAST record of: " + ", ".join(sentinel_bad[:8])
                      + (f" (+{len(sentinel_bad)-8})" if len(sentinel_bad) > 8 else ""))
        if stamp_bad:
            # V18 (a deliberate STALE stamp) TRANSLATED in the Autodesk Viewer:
            # the reader does NOT validate record stamps.  A stale stamp is a
            # writer-hygiene defect (we always emit correct stamps), not a
            # rejection => WARNING by default, ERROR under strict.
            emit = rep.error if self.strict else rep.warn
            emit(L_STRUCTURE, pname, f"{stamp_bad} seq-102/103 record stamp(s) != "
                 "adler32(class_id||body) (stale/deleted stamp: tolerated by "
                 "Autodesk's reader — proven by the accepted V18 — but a writer "
                 f"hygiene defect; {'ERROR under strict' if self.strict else 'strict makes it an error'})")
        if rep_bad:
            rep.error(L_STRUCTURE, pname, f"{rep_bad} record(s) whose trailing u32 psize "
                      "repeat does not match")
        return n_records

    # ==================================================================
    # L2 CONSISTENCY
    # ==================================================================
    def _payload(self, name: str) -> Optional[bytes]:
        """Inflated payload of a small framed stream (from the repaired logical)."""
        logical = self.logical.get(name)
        if logical is None:
            if name not in self.names:
                return None
            raw = self.raw(name)
            if name in self.unframed_streams:
                self.logical[name] = raw
            else:
                self.logical[name] = ecc_verify_stream(name, raw, self.rep).logical
            logical = self.logical[name]
        return _inflate_first(logical)

    def _walkers(self) -> Dict[str, StreamWalker]:
        if not self.part_walkers:
            for pname in self.partition_names():
                logical = self.logical.get(pname)
                if logical is None:
                    logical = ecc_verify_stream(pname, self.raw(pname), self.rep).logical
                    self.logical[pname] = logical
                try:
                    w = StreamWalker(logical, inflate=True, keep_data=True)
                except Exception as e:
                    self.rep.error(L_CONSISTENCY, pname, f"partition walker: {e}")
                    continue
                self.part_walkers[pname] = w
                seg: Dict[Tuple[int, int], bytearray] = defaultdict(bytearray)
                for b in sorted(w.blocks, key=lambda x: x.hdr_offset):
                    if b.data:
                        seg[(b.unit, b.seq)] += b.data
                self.unit_segments[pname] = {k: bytes(v) for k, v in seg.items()}
        return self.part_walkers

    def _layer_consistency(self) -> None:
        rep = self.rep
        from .stream_encoders import (decode_basic_file_info, decode_contents,
                                      decode_elemtable, decode_history,
                                      decode_increment_table, decode_partition_table)

        # -- ElemTable -------------------------------------------------------------
        et_payload = self._payload("Global/ElemTable")
        et = None
        if et_payload is None:
            rep.error(L_CONSISTENCY, "Global/ElemTable", "cannot inflate ElemTable")
        else:
            try:
                et = decode_elemtable(et_payload)
            except Exception as e:
                rep.error(L_CONSISTENCY, "Global/ElemTable", f"ElemTable does not decode: {e}")
        if et is not None:
            self.elemtable = et
            recs = et["records"]
            ids = [r[4] for r in recs]
            self.et_ids = ids
            declared = struct.unpack_from("<I", et_payload, 2)[0]
            if declared != len(recs):
                rep.error(L_CONSISTENCY, "Global/ElemTable",
                          f"declared count {declared} != {len(recs)} ElemRecs decoded")
            if any(ids[i] >= ids[i + 1] for i in range(len(ids) - 1)):
                rep.error(L_CONSISTENCY, "Global/ElemTable",
                          "ElementIds are not strictly increasing (sorted & unique)")
            if len(set(ids)) != len(ids):
                rep.error(L_CONSISTENCY, "Global/ElemTable", "duplicate ElementIds")
            wm = et["footer"]["last_id"]
            if ids and wm < max(ids):
                rep.error(L_CONSISTENCY, "Global/ElemTable",
                          f"watermark (footer last_id {wm}) < max id {max(ids)}")
            if et.get("graveyard_count", 0) != 0:
                rep.warn(L_CONSISTENCY, "Global/ElemTable",
                         f"graveyard count {et['graveyard_count']} != 0 (never observed)")

        # -- partition header count vs ElemTable -----------------------------------
        walkers = self._walkers()
        hdr_counts = {}
        for pname in walkers:
            logical = self.logical[pname]
            hdr_counts[pname] = struct.unpack_from("<I", logical, 14)[0]
        if et is not None and hdr_counts:
            best = max(hdr_counts.values())
            if best != len(et["records"]):
                rep.error(L_CONSISTENCY, "Partitions/<N>",
                          f"partition header elem_table_count {best} != ElemTable "
                          f"count {len(et['records'])} ({hdr_counts})")
            for pname, c in hdr_counts.items():
                if c not in (best, 0):
                    rep.warn(L_CONSISTENCY, pname,
                             f"secondary partition header count {c} (expected 0 or {best})")

        # -- History ------------------------------------------------------------------
        hist = None
        p = self._payload("Global/History")
        if p is None:
            rep.error(L_CONSISTENCY, "Global/History", "cannot inflate History")
        else:
            try:
                hist = decode_history(p)
            except Exception as e:
                rep.error(L_CONSISTENCY, "Global/History", f"History does not decode: {e}")
        if hist is not None and et is not None and et["records"]:
            max_mod = max(r[2] for r in et["records"])
            if hist["hdr_count"] != max_mod + 1:
                rep.error(L_CONSISTENCY, "Global/History",
                          f"episode count {hist['hdr_count']} != max(ElemRec."
                          f"modified_ep)+1 = {max_mod + 1}")
            if len(hist["entries"]) != hist["hdr_count"]:
                rep.error(L_CONSISTENCY, "Global/History",
                          f"header count {hist['hdr_count']} != {len(hist['entries'])} "
                          "episode entries")

        # -- DocumentIncrementTable ----------------------------------------------------
        dit = None
        p = self._payload("Global/DocumentIncrementTable")
        if p is None:
            rep.error(L_CONSISTENCY, "Global/DocumentIncrementTable",
                      "cannot inflate DocumentIncrementTable")
        else:
            try:
                dit = decode_increment_table(p)
                if dit["records2"] != dit["records"]:
                    rep.error(L_CONSISTENCY, "Global/DocumentIncrementTable",
                              "the two serialized copies of the table differ")
            except Exception as e:
                rep.error(L_CONSISTENCY, "Global/DocumentIncrementTable",
                          f"DocumentIncrementTable does not decode: {e}")
        newest = None
        if dit is not None and dit["records"]:
            newest = dit["records"][-1]
            if hist is not None:
                exp = (hist["hdr_count"] - 1, hist["hdr_count"])
                if tuple(newest["id_pair"]) != exp:
                    rep.error(L_CONSISTENCY, "Global/DocumentIncrementTable",
                              f"newest increment id_pair {tuple(newest['id_pair'])} != "
                              f"(History count-1, count) = {exp}")

        # -- Contents ------------------------------------------------------------------
        con = None
        p = self._payload("Contents")
        if p is None:
            rep.error(L_CONSISTENCY, "Contents", "cannot inflate Contents")
        else:
            try:
                con = decode_contents(p)
            except Exception as e:
                rep.error(L_CONSISTENCY, "Contents", f"Contents does not decode: {e}")
        if con is not None and newest is not None:
            c2 = [x for i, x in enumerate(newest["counters"]) if i != 7]
            if con["counters"] != c2:
                rep.error(L_CONSISTENCY, "Contents",
                          f"counters {con['counters']} != newest DIT counters minus "
                          f"index 7 {c2}")
            if con["counter_g"] != newest["counter_g"]:
                rep.error(L_CONSISTENCY, "Contents",
                          f"G {con['counter_g']} != DIT G {newest['counter_g']}")

        # -- BasicFileInfo ---------------------------------------------------------------
        bfi = None
        if "BasicFileInfo" in self.names:
            try:
                bfi = decode_basic_file_info(self.raw("BasicFileInfo"))
            except Exception as e:
                rep.error(L_CONSISTENCY, "BasicFileInfo",
                          f"BasicFileInfo does not decode: {e}")
        if bfi is not None:
            if dit is not None:
                n = len(dit["records"])
                inc = _as_int(bfi["unique_document_increments"])
                cvn = _as_int(bfi["central_version_number"])
                if inc != n or cvn != n:
                    rep.error(L_CONSISTENCY, "BasicFileInfo",
                              f"Unique Document Increments {bfi['unique_document_increments']}"
                              f" / central version {bfi['central_version_number']} != "
                              f"DIT record count {n}")
            if hist is not None and hist["entries"]:
                if str(bfi["unique_document_guid"]).lower() != \
                        str(hist["entries"][0][0]).lower():
                    rep.error(L_CONSISTENCY, "BasicFileInfo",
                              "Unique Document GUID != History entry[0] GUID")

        # -- PartitionTable (workset table) decode ----------------------------------------
        p = self._payload("Global/PartitionTable")
        if p is None:
            rep.error(L_CONSISTENCY, "Global/PartitionTable", "cannot inflate")
        else:
            try:
                decode_partition_table(p)
            except Exception as e:
                rep.error(L_CONSISTENCY, "Global/PartitionTable",
                          f"workset table does not decode: {e}")

        # -- id-set invariants across seqs and vs ElemTable ------------------------------
        for pname, segs in self.unit_segments.items():
            units = sorted({u for (u, _s) in segs})
            # an EMPTY later partition (e.g. dach Partitions/85, header count 0)
            # legitimately holds no host-document records
            empty_partition = hdr_counts.get(pname, 0) == 0
            for u in units:
                idsets = {}
                for s in (101, 102, 103):
                    buf = segs.get((u, s), b"")
                    idsets[s] = {r.elem_id for r in _iter_seg_records(buf, s, u)
                                 if r.elem_id >= 0}
                if not (idsets[101] == idsets[102] == idsets[103]):
                    d12 = len(idsets[101] ^ idsets[102])
                    d23 = len(idsets[102] ^ idsets[103])
                    rep.error(L_CONSISTENCY, pname,
                              f"save unit {u}: the three seqs carry different id sets "
                              f"(101^102 differ by {d12}, 102^103 by {d23})")
                if u == 0 and self.et_ids and not empty_partition:
                    ets = set(self.et_ids)
                    if idsets[102] != ets:
                        missing = ets - idsets[102]
                        extra = idsets[102] - ets
                        rep.error(L_CONSISTENCY, pname,
                                  f"save unit 0 seq-102 ids != ElemTable ids "
                                  f"({len(missing)} ElemTable ids without records, "
                                  f"{len(extra)} unit-0 records absent from ElemTable)")

    # ==================================================================
    # L3 SEMANTIC
    # ==================================================================
    def _load_schema(self):
        if self.schema is not None:
            return self.schema
        from .schema import parse as parse_schema
        blob = self._payload("Formats/Latest")
        if blob is None:
            self.rep.error(L_SEMANTIC, "Formats/Latest",
                           "no schema — semantic layer cannot run")
            return None
        try:
            self.schema = parse_schema(blob, source=self.path)
        except Exception as e:
            self.rep.error(L_SEMANTIC, "Formats/Latest", f"schema does not parse: {e}")
            return None
        return self.schema

    def _layer_semantic(self) -> None:
        rep = self.rep
        schema = self._load_schema()
        if schema is None:
            return
        walkers = self._walkers()
        if not self.unit_segments:
            return
        # ElemTable ids (for the id universe) — decode lazily if L2 was skipped
        if self.elemtable is None:
            try:
                from .stream_encoders import decode_elemtable
                p = self._payload("Global/ElemTable")
                if p is not None:
                    self.elemtable = decode_elemtable(p)
                    self.et_ids = [r[4] for r in self.elemtable["records"]]
            except Exception:
                pass

        dec = _RefDecoder(schema)
        # -- index every seq-102 record file-wide ---------------------------------------
        recs102: Dict[int, Tuple[int, bytes, int]] = {}      # id -> (class, payload, unit)
        universe: Set[int] = set(self.et_ids)
        for pname, segs in self.unit_segments.items():
            for (u, s), buf in segs.items():
                if s != 102:
                    if s == 101:
                        for r in _iter_seg_records(buf, s, u):
                            if r.elem_id >= 0:
                                universe.add(r.elem_id)
                    continue
                for r in _iter_seg_records(buf, s, u):
                    if r.elem_id < 0:
                        continue
                    universe.add(r.elem_id)
                    if r.body_size >= 2:
                        recs102[r.elem_id] = (
                            r.class_id,
                            buf[r.payload_off + 2:r.payload_off + r.body_size], u)

        # -- decode + collect ---------------------------------------------------------
        clean: Set[int] = set()
        failures: Counter = Counter()
        fail_examples: Dict[str, str] = {}
        refs: List[Tuple[int, str, int]] = []                     # (owner, field, target)
        conns: Dict[int, Dict[int, List[Tuple[int, int, int]]]] = {}
        circuits: List[Tuple[int, dict]] = []
        typed_checks: List[Tuple[int, str, int, str]] = []       # (owner, field, target, need)
        limit = self.decode_limit
        n = 0
        for eid, (cls, payload, unit) in recs102.items():
            if limit is not None and n >= limit:
                break
            n += 1
            dec.refs = []
            try:
                obj = dec.decode_record(cls, payload)
            except Exception as e:                    # decoder crash guard
                failures[dec.class_name(cls)] += 1
                fail_examples.setdefault(dec.class_name(cls), f"{eid}: {e}")
                continue
            if not (obj.clean or obj.stub):
                cname = dec.class_name(cls)
                failures[cname] += 1
                if obj.errors:
                    fail_examples.setdefault(cname, f"{eid}: {obj.errors[0]['error']}")
                continue
            clean.add(eid)
            for path, val in dec.refs:
                refs.append((eid, path, val))
            v = obj.value
            for path, val in dec.refs:
                fname = path.rsplit(".", 1)[-1].split("[", 1)[0]
                if isinstance(val, int) and val > 0:
                    if fname in ("m_symbolId", "m_masterSymbolId"):
                        typed_checks.append((eid, fname, val, "Symbol"))
                    elif "LevelId" in fname or fname == "m_levelId":
                        typed_checks.append((eid, fname, val, "Level"))
            cm = _connector_map(v)
            if cm is not None:
                conns[eid] = cm
            if dec.class_name(cls) == "RbsElectricalSystem":
                circuits.append((eid, v))

        rep.stats["elements_decoded"] = n
        n_fail = sum(failures.values())
        rep.stats["decode_failures"] = n_fail
        if n_fail:
            top = ", ".join(f"{c} x{k}" for c, k in failures.most_common(6))
            ex = "; ".join(f"{c}: {fail_examples[c]}" for c in list(failures)[:2])
            rep.warn(L_SEMANTIC, "objects",
                     f"{n_fail}/{n} seq-102 records failed schema decode "
                     f"({top}) — known decoder gap = Extensible-Storage entity "
                     f"blobs; these elements' references/connectors are unverifiable. "
                     f"e.g. {ex}")

        # -- reference integrity ---------------------------------------------------------
        dangling = find_dangling_refs(refs, universe)
        rep.stats["refs_checked"] = len(refs)
        if dangling:
            byfield = Counter(p.rsplit(".", 1)[-1].split("[", 1)[0]
                              for _o, p, _t in dangling)
            ex = "; ".join(f"element {o} {p.split('->')[-1]}={t}"
                           for o, p, t in dangling[:4])
            rep.error(L_SEMANTIC, "references",
                      f"{len(dangling)} dangling ElementId reference(s) to elements "
                      f"that do not exist (by field: "
                      + ", ".join(f"{f} x{c}" for f, c in byfield.most_common(6))
                      + f"). e.g. {ex}")

        # -- typed resolution: symbols / levels -------------------------------------------
        cls_chain_cache: Dict[int, Set[str]] = {}

        def chain_names(class_id: int) -> Set[str]:
            got = cls_chain_cache.get(class_id)
            if got is None:
                got = {c.name for c in dec.chain(class_id)}
                cls_chain_cache[class_id] = got
            return got

        sym_bad = []
        lvl_bad = []
        for owner, fname, target, need in typed_checks:
            rec = recs102.get(target)
            if rec is None:
                continue                      # dangling — already reported
            names = chain_names(rec[0])
            if need == "Symbol" and "Symbol" not in names:
                sym_bad.append((owner, fname, target, dec.class_name(rec[0])))
            elif need == "Level" and not ({"Level", "DatumPlane"} & names):
                lvl_bad.append((owner, fname, target, dec.class_name(rec[0])))
        if sym_bad:
            ex = "; ".join(f"element {o} {f}={t} ({c})" for o, f, t, c in sym_bad[:4])
            rep.error(L_SEMANTIC, "symbols",
                      f"{len(sym_bad)} instance symbol id(s) resolve to non-Symbol "
                      f"elements. e.g. {ex}")
        if lvl_bad:
            ex = "; ".join(f"element {o} {f}={t} ({c})" for o, f, t, c in lvl_bad[:4])
            rep.error(L_SEMANTIC, "levels",
                      f"{len(lvl_bad)} level id(s) resolve to non-Level elements. e.g. {ex}")

        # -- connector graph symmetry ---------------------------------------------------------
        edges, viol, unverifiable, viol_ex = check_connector_graph(conns, universe, clean)
        rep.stats["connector_edges"] = edges
        if unverifiable:
            rep.info(L_SEMANTIC, "connectors",
                     f"{unverifiable} connector edge(s) point at elements that did "
                     f"not decode cleanly (back-link unverifiable)")
        if viol:
            emit = rep.error if self.strict else rep.warn
            emit(L_SEMANTIC, "connectors",
                 f"{viol} one-way connector link(s): a connector references an "
                 f"EXISTING element whose connector does not reference it back "
                 f"(the cloned-template-connector defect: Autodesk's translator "
                 f"accepts such files, but the electrical connectivity model is "
                 f"corrupt — {'ERROR (strict / circuit-ready gate)' if self.strict else 'warning; run with strict/--strict to gate on it'}). "
                 f"e.g. " + "; ".join(viol_ex))

        # -- circuits ------------------------------------------------------------------------
        circ_bad = check_circuits(circuits, conns)
        if circ_bad:
            rep.error(L_SEMANTIC, "circuits",
                      f"{len(circ_bad)} circuit(s) with an invalid base connector: "
                      + "; ".join(circ_bad[:4]))
        rep.stats["circuits"] = len(circuits)

        # -- loaded-content consistency (the product-path laws) -------------------------------
        self._check_loaded_content(recs102, dec)

    def _check_loaded_content(self, recs102, dec) -> None:
        """Loaded-family / placed-instance consistency — the rules Autodesk's
        open-time corruption audit enforces that this validator historically
        did not (instbug-fix stream, 2026-08-05; evidence in
        docs/inbox/instbug-fix.md):

        E1  FOUR-REGISTRY COHERENCE (ERROR) — a content-document GUID lives in
            four places (Partitions save unit, Global/ContentDocuments entry,
            ADocument ContentTable record, ADocument FamilyMgr entry); counts
            and GUID sets must agree.  PROVEN audit law: R9b (2-of-4 splice)
            viewer-FAILED while KD1 (same removal, all four reconciled)
            viewer-PASSED — the one SOUND fail of the verdict-integrity audit.
        E2  ContentTable.m_ContentRecSet ascending by ContentKey GUID
            (bytes_le) (ERROR, checked when the file carries >= 2 content
            documents) — the six-sample corpus order; every N>=2 chained
            famgen load violated it and every viewer-PASSED file obeys it.
        E3  FamilyInstance.m_pConnectorManager ptr class must be null or
            FamilyInstanceConnectorManager (ERROR) — 13,636/13,636 corpus
            instances; the base-class ConnectorManager appeared only in
            audit-FAILED files (DEMO_250v_room, electrical_room_2500a).
        W1  host Family.m_oFamDimConstrMgr null (WARNING — corpus 831/831
            present, but WF_nofix viewer-PASSED carrying the null).
        W2  host FamilySymbol.m_pMoveRestrictions null (WARNING — corpus
            2710/2710 present; same WF_nofix caveat).
        W3  ConnectorDataCell with a relevant-params table below the corpus
            floor (11 rows) (WARNING — corpus 228/228 cells carry 11..21).
        """
        rep = self.rep
        targets: Dict[str, List[Tuple[int, int, bytes]]] = {
            "Family": [], "FamilySymbol": [], "FamilyInstance": []}
        for eid, (cls, payload, unit) in recs102.items():
            if unit != 0:
                continue
            name = dec.class_name(cls)
            if name in targets:
                targets[name].append((eid, cls, payload))
        fam_null: List[int] = []
        sym_null: List[int] = []
        mgr_bad: List[Tuple[int, Any]] = []
        cell_low: List[Tuple[int, int]] = []
        for name, rows in targets.items():
            for eid, cls, payload in rows:
                try:
                    dec.refs = []
                    obj = dec.decode_record(cls, payload)
                except Exception:
                    continue
                if not (obj.clean or obj.stub):
                    continue
                v = obj.value or {}
                if name == "Family":
                    if v.get("m_oFamDimConstrMgr") is None:
                        fam_null.append(eid)
                    cl = ((v.get("m_cellList") or {}).get("value") or {})
                    for c in cl.get("m_cells") or []:
                        if isinstance(c, dict) and c.get("ptr_class") == "ConnectorDataCell":
                            prm = (((c.get("value") or {}).get("m_oRelevantParams") or {})
                                   .get("value") or {}).get("m_params") or []
                            if len(prm) < 11:
                                cell_low.append((eid, len(prm)))
                elif name == "FamilySymbol":
                    if v.get("m_pMoveRestrictions") is None:
                        sym_null.append(eid)
                else:   # FamilyInstance
                    cm = v.get("m_pConnectorManager")
                    if isinstance(cm, dict) and \
                            cm.get("ptr_class") != "FamilyInstanceConnectorManager":
                        mgr_bad.append((eid, cm.get("ptr_class")))
        if mgr_bad:
            ex = "; ".join(f"instance {e}: {c}" for e, c in mgr_bad[:4])
            rep.error(L_SEMANTIC, "loaded-content",
                      f"{len(mgr_bad)} placed FamilyInstance(s) carry a connector "
                      f"manager of an unlawful class (corpus 13,636/13,636 = "
                      f"FamilyInstanceConnectorManager or null). e.g. {ex}")
        if fam_null:
            rep.warn(L_SEMANTIC, "loaded-content",
                     f"{len(fam_null)} host Family element(s) with "
                     f"m_oFamDimConstrMgr = null (corpus: present 831/831; the "
                     f"lawful empty form is rvt.genesis.residue_c.famdim_constr_empty). "
                     f"ids {fam_null[:6]}")
        if sym_null:
            rep.warn(L_SEMANTIC, "loaded-content",
                     f"{len(sym_null)} host FamilySymbol element(s) with "
                     f"m_pMoveRestrictions = null (corpus: present 2710/2710). "
                     f"ids {sym_null[:6]}")
        if cell_low:
            ex = "; ".join(f"family {e}: {n} rows" for e, n in cell_low[:4])
            rep.warn(L_SEMANTIC, "loaded-content",
                     f"{len(cell_low)} ConnectorDataCell(s) below the corpus "
                     f"relevant-params floor (11..21 rows in 228/228 corpus cells). {ex}")

        # ---- E1 + E2: the four registries + ContentTable order -----------------
        try:
            from .famgen.factory import parse_content_documents
            cd_payload = self._payload("Global/ContentDocuments")
            cd_guids = ([g.lower() for g, _a in parse_content_documents(cd_payload)[0]]
                        if cd_payload else [])
        except Exception as e:
            rep.warn(L_SEMANTIC, "loaded-content",
                     f"ContentDocuments does not parse ({e}); four-registry "
                     f"coherence unverifiable")
            return
        # unit GUIDs from the partition walkers
        unit_guids: List[str] = []
        try:
            import uuid as _uuid
            for pname, w in self._walkers().items():
                for u in w.units:
                    if u.index != 0 and u.guid:
                        unit_guids.append(str(_uuid.UUID(bytes_le=u.guid)).lower())
        except Exception:
            pass
        need_latest = bool(cd_guids or unit_guids)
        if not need_latest:
            return
        try:
            from .adocument import decode_latest
            lat = decode_latest(self._payload("Global/Latest"))
            lv = lat.value
        except Exception as e:
            rep.warn(L_SEMANTIC, "loaded-content",
                     f"Global/Latest does not decode ({e}); content-registry "
                     f"coherence unverifiable")
            return
        ct = ((lv.get("m_oContentTable") or {}).get("value") or {})
        recs = ct.get("m_ContentRecSet")
        ct_guids = ([str((r.get("m_ContentKey") or {}).get("m_guidKey") or "").lower()
                     for r in recs] if isinstance(recs, list) else [])
        fm_guids: List[str] = []
        mgr = (lv.get("m_pAppInfoManager") or {}).get("value") or {}
        for slot in mgr.get("m_appInfoArr") or []:
            if isinstance(slot, dict) and slot.get("ptr_class") == "FamilyMgr":
                for e in (slot.get("value") or {}).get("m_arrLoadedFamilyInfo") or []:
                    fm_guids.extend(str(g).lower() for g in (e.get("m_familyDocGUIDs") or []))
        su, sc, st_, sf = set(unit_guids), set(cd_guids), set(ct_guids), set(fm_guids)
        if not (len(unit_guids) == len(cd_guids) == len(ct_guids) == len(fm_guids)
                and su == sc == st_ == sf):
            rep.error(L_SEMANTIC, "loaded-content",
                      f"FOUR-REGISTRY INCOHERENCE: save units {len(unit_guids)} / "
                      f"ContentDocuments {len(cd_guids)} / ContentTable {len(ct_guids)} / "
                      f"FamilyMgr GUIDs {len(fm_guids)} — counts and GUID sets must "
                      f"agree (audit law, R9b-FAIL vs KD1-PASS). "
                      f"units-not-in-CD {sorted(su - sc)[:2]}; CT-dangling {sorted(st_ - su)[:2]}; "
                      f"FM-dangling {sorted(sf - su)[:2]}")
        if len(cd_guids) >= 2 and isinstance(recs, list):
            import uuid as _uuid
            try:
                keys = [_uuid.UUID(g).bytes_le for g in ct_guids]
            except Exception:
                keys = []
            if keys and keys != sorted(keys):
                rep.error(L_SEMANTIC, "loaded-content",
                          f"ContentTable.m_ContentRecSet is NOT ascending by "
                          f"ContentKey GUID (corpus order; rvt.famload sorts, "
                          f"chained rvt.famgen.loader loads did not). order: "
                          f"{[g[:8] for g in ct_guids][:8]}")


class _Abort(Exception):
    pass


# ---------------------------------------------------------------------------
# ElementId-capturing decoder
# ---------------------------------------------------------------------------

_REF_DECODER_CLS = None


def _RefDecoder(schema):
    """Instantiate an ObjectDecoder subclass that records every
    ElementId-typed value with its field path (schema-driven typing, not
    field-name guessing).  Defined lazily so importing this module does not
    load the object decoder."""
    global _REF_DECODER_CLS
    if _REF_DECODER_CLS is None:
        from .objects import ObjectDecoder

        class RefDecoder(ObjectDecoder):
            def __init__(self, schema):
                super().__init__(schema)
                self.refs: List[Tuple[str, int]] = []

            def _decode_value_class(self, rd, type_id, queue, state, path):
                v = super()._decode_value_class(rd, type_id, queue, state, path)
                if type_id == self.id_ElementId:
                    self.refs.append((path, v))
                return v

        _REF_DECODER_CLS = RefDecoder
    return _REF_DECODER_CLS(schema)


# ---------------------------------------------------------------------------
# connector helpers
# ---------------------------------------------------------------------------

def _connector_map(v: dict) -> Optional[Dict[int, List[Tuple[int, int, int]]]]:
    """{connector nIndex: [(target_id, target_index, connType), ...]} for an
    element that owns a connector manager, else None."""
    if not isinstance(v, dict):
        return None
    mgrs = []
    for key in ("m_pConnectorMgr", "m_pConnectorManager"):
        h = v.get(key)
        if isinstance(h, dict) and isinstance(h.get("value"), dict):
            mgrs.append(h["value"])
    if not mgrs:
        return None
    out: Dict[int, List[Tuple[int, int, int]]] = {}
    for mgr in mgrs:
        for c in mgr.get("m_connPtrArray") or []:
            cv = c.get("value") if isinstance(c, dict) else None
            if not isinstance(cv, dict):
                continue
            idx = cv.get("m_nIndex")
            if not isinstance(idx, int):
                continue
            refs = []
            for rr in cv.get("m_arrRefs") or []:
                if isinstance(rr, dict):
                    tid = rr.get("m_id")
                    tix = rr.get("m_nIndex")
                    ct = rr.get("m_connType", 0)
                    if isinstance(tid, int) and tid > 0 and isinstance(tix, int):
                        refs.append((tid, tix, ct))
            out.setdefault(idx, []).extend(refs)
    return out


def _same_connector(targets, elem_id: int, index: int) -> bool:
    return bool(targets) and any(t == elem_id and j == index for (t, j, _c) in targets)


# ---------------------------------------------------------------------------
# pure L3 checks (unit-testable without a file)
# ---------------------------------------------------------------------------

def find_dangling_refs(refs: Iterable[Tuple[int, str, Any]],
                       universe: Set[int]) -> List[Tuple[int, str, int]]:
    """REFERENCE INTEGRITY.  ``refs`` = (owner_id, field_path, value) for every
    schema-typed ElementId value; ``universe`` = every existing element id
    (all partition record ids + ElemTable ids).  A POSITIVE id that is not in
    the universe is a dangling reference; ``-1`` (invalid sentinel), ``0`` and
    negative built-in ids (categories, parameters) are legal by construction.
    """
    return [(owner, path, int(target)) for owner, path, target in refs
            if isinstance(target, int) and target > 0 and target not in universe]


def check_connector_graph(conns: Dict[int, Dict[int, List[Tuple[int, int, int]]]],
                          universe: Set[int], clean: Set[int],
                          max_examples: int = 4) -> Tuple[int, int, int, List[str]]:
    """CONNECTOR GRAPH SYMMETRY.

    ``conns`` = {element_id: {connector nIndex: [(target_id, target_index,
    connType), ...]}} for every element owning a connector manager;
    ``universe`` = all existing ids; ``clean`` = ids whose objects decoded
    cleanly.  Every edge A.conn[i] -> {B, j} must be answered by a back-edge
    B.conn[j] -> {A, i}.  Returns ``(edges, one_way_violations,
    unverifiable, examples)``: an edge into a NON-EXISTENT id is left to the
    reference-integrity check (dangling ElementId); an edge into an element
    that failed to decode is unverifiable (counted, not a violation).
    """
    edges = viol = unverifiable = 0
    examples: List[str] = []
    for a, m in conns.items():
        for i, targets in m.items():
            for (b, j, _ct) in targets:
                edges += 1
                if b == a and _same_connector(m.get(j), a, i):
                    continue                                   # consistent self-loop
                tgt = conns.get(b)
                if tgt is not None:
                    back = tgt.get(j)
                    if back is not None and any(t == a and jj == i for (t, jj, _c) in back):
                        continue                               # symmetric — fine
                if b not in universe:
                    continue                                   # dangling id (other check)
                if b not in clean:
                    unverifiable += 1                          # target failed to decode
                    continue
                viol += 1
                if len(examples) < max_examples:
                    why = ("target has no connector %d" % j
                           if (tgt is None or j not in tgt) else "no back-reference")
                    examples.append(f"element {a} conn[{i}] -> element {b} conn[{j}]"
                                    f" ({why})")
    return edges, viol, unverifiable, examples


def check_circuits(circuits: Iterable[Tuple[int, dict]],
                   conns: Dict[int, Dict[int, List[Tuple[int, int, int]]]]) -> List[str]:
    """RbsElectricalSystem invariants: connector indices unique and, when the
    circuit is assigned to a panel, ``m_baseConnectorIdArray == [{self, LAST
    connector index}]`` (the base/panel connector is the circuit's last)."""
    bad: List[str] = []
    for cid, v in circuits:
        bca = (v or {}).get("m_baseConnectorIdArray") or []
        own = conns.get(cid, {})
        if not own:
            continue
        idx = sorted(own)
        if len(idx) != len(set(idx)):
            bad.append(f"circuit {cid}: duplicate connector indices")
        if not bca:
            continue                       # unassigned circuit (no panel): legal
        b0 = bca[0] if isinstance(bca[0], dict) else {}
        if len(bca) != 1 or b0.get("m_id") != cid or b0.get("m_nIndex") != max(idx):
            bad.append(f"circuit {cid}: base connector "
                       f"{b0.get('m_id')}:{b0.get('m_nIndex')} is not "
                       f"{{self, LAST index {max(idx)}}}")
    return bad


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def validate_file(path: str, layers: Iterable[str] = ALL_LAYERS,
                  decode_limit: Optional[int] = None, strict: bool = False,
                  family: bool = False) -> Report:
    """Validate a .rvt file and return the layered Report.

    ``strict=True`` is the "circuit-ready" gate: one-way connector links
    (tolerated by Autodesk's translator, so a WARNING by default) become
    errors.  ``family=True`` applies the TWO family-shape adjustments
    (PartAtom unframed; ProjectInformation not required) for ``.rfa``/
    ``.rft`` streams sets.  Everything else is identical in all modes.
    """
    v = Validator(path, layers=layers, decode_limit=decode_limit, strict=strict,
                  family=family)
    try:
        return v.run()
    except _Abort:
        v.rep.timings.setdefault("total", 0.0)
        return v.rep


def main(argv=None) -> int:
    import argparse
    import json
    import os
    import sys

    ap = argparse.ArgumentParser(prog="rvt_validate",
                                 description="Autodesk-free .rvt validator")
    ap.add_argument("files", nargs="+", help=".rvt file(s) to validate")
    ap.add_argument("--json", dest="json_out", help="write the report(s) as JSON")
    ap.add_argument("--layers", default=",".join(ALL_LAYERS),
                    help="comma list of layers to run (structure,consistency,semantic)")
    ap.add_argument("--decode-limit", type=int, default=None,
                    help="cap the number of seq-102 records decoded (semantic layer)")
    ap.add_argument("--strict", action="store_true",
                    help="circuit-ready gate: one-way connector links become errors "
                         "(default: warnings — Autodesk accepts such files)")
    ap.add_argument("--family", dest="family", action="store_true", default=None,
                    help="family mode: PartAtom unframed, ProjectInformation not "
                         "required (auto-enabled for .rfa/.rft files)")
    ap.add_argument("--project", dest="family", action="store_false",
                    help="force project mode even for a .rfa/.rft extension")
    ap.add_argument("--quiet", action="store_true", help="only print the verdict line")
    a = ap.parse_args(argv)
    layers = [s.strip() for s in a.layers.split(",") if s.strip()]
    reports = []
    worst = 0
    for f in a.files:
        fam = a.family
        if fam is None:
            fam = os.path.splitext(f)[1].lower() in (".rfa", ".rft")
            if fam and not a.quiet:
                print(f"[{os.path.basename(f)}] family mode auto-enabled by "
                      "extension (force off with --project)")
        rep = validate_file(f, layers=layers, decode_limit=a.decode_limit,
                            strict=a.strict, family=fam)
        reports.append(rep)
        if a.quiet:
            print(f"{'OK  ' if rep.ok else 'FAIL'} {f}  errors={len(rep.errors)} "
                  f"warnings={len(rep.warnings)}  ({rep.timings.get('total', 0):.1f}s)")
        else:
            print(rep.format_text())
        if not rep.ok:
            worst = 1
    if a.json_out:
        payload = reports[0].to_json() if len(reports) == 1 else \
            {"files": [r.to_json() for r in reports]}
        with open(a.json_out, "w") as fh:
            json.dump(payload, fh, indent=1)
    return worst


if __name__ == "__main__":
    import sys
    sys.exit(main())
