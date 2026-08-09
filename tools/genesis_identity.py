#!/usr/bin/env python
"""genesis_identity.py -- G2 identity RUNGS for the pinned composed genesis bases
(issue #134, the fresh-clone half of #19; TRACKER P0 gate G2 "own the identity block").

WHY.  The three certified composed bases shipped in plugin/assets/genesis/
(G_ABPD = 2026, G_ABPD_2025, G_ABPD_2024) still carry the Autodesk sample's
identity on four METADATA surfaces, byte-inherited from the rst sample and
never touched by the reduction / substitution / compose lineage (genesis-audit
'ORCHESTRATOR VERDICTS #47' premise correction; the batch-51 FLAG):

  I_bfi  BasicFileInfo             author "Autodesk Revit", client "RevitApplication",
                                   last_save_path = an employee's Desktop path
  I_dit  Global/DocumentIncrementTable   every save episode signed by an Autodesk
                                   employee username (21-22 rows)
  I_pi   ProjectInformation        the PartAtom ZIP member NAME is an employee's
                                   AppData temp path; the XML says "rstbasicsampleproject",
                                   Client "Autodesk", "Sample House"
  I_td   TransmissionData          LastSavedAbsolutePath = C:\\Users\\<employee>\\... /
                                   C:\\ProgramData\\Autodesk\\RVT 20xx\\... absolute paths

Everything the front door builds inherits the PI / TD surfaces (it re-owns BFI
author + DIT usernames per output, rvt.commit).  The base is CERTIFIED, so a
scrub is a NEW base that must itself be re-certified by Autodesk's reader
(hard rule 4) -- and verdict #36 showed the only earlier single-surface identity
probes (E4 = BFI, E5 = DIT) FAILED for an unrelated reason (they lacked the
64-byte 0x0f3f footer blob), so BFI / DIT have never been convicted or
acquitted IN ISOLATION on a composed base.  Hence: one rung per surface, each =
the pinned base's bytes with exactly ONE identity field family rewritten to
ours and every other CFB stream byte-identical, plus I_all (all four) as the
candidate base, the untouched pin as the byte-identical CONTROL.

WHAT THIS TOOL DOES (fresh clone, no samples/, no viewer):
  build   write experiments/identity_g2/<year>/I_<fam>_<year>.rvt for every
          family + I_all (+ optional I_guid), then `check`
  check   assert per rung: changed-stream set == intended, rvt_validate 0
          errors under the file's own release, rvt.provenance identity
          violations, decode round-trips, and a byte scan of every raw /
          de-paged / inflated stream for inherited usernames and absolute
          foreign paths; write <year>/rungs.json and regenerate the stream-wide
          experiments/identity_g2/probes.json from every rungs.json present
          (I_all = kind candidate-base, singles = probes, base = the LEDGER
          relpath of the pin)
  gate    tools/probe_batch.py check (default) or stage (--stage) one batch per
          release straight from probes.json: I_all as --candidate-base, the
          singles as probes, control cut from the pinned base of that release;
          a rung that is missing, stale (sha256 != probes.json) or failed its
          checks is refused here.  Sessions STAGE and stop at READY; a human
          uploads and records verdicts (CLAUDE.md §1 rule 4).
  ready   the #19 one-command = build + gate --stage for every release
          (--batch N pins the batch numbers so a re-run on another machine
          reproduces the committed batch_<n>.json manifests md5-for-md5).

It uses the engine READ-ONLY and the same identity functions the certified
front-door commit path uses (rvt.identity.own_basic_file_info with the CURRENT
document GUID so History[0] stays coherent, rvt.identity.own_increment_table_
stream with username ''), so every rung's mechanism is one already viewer-
proven on the 2026 wall/edit lineage (V30/V31/V32) -- what is untested is each
surface on a COMPOSED base, which is exactly what the rungs isolate.
PRODUCT_AUTHOR_PLACEHOLDER is used as-is (counsel C1, hard rule 6): nothing
here invents an author string.  No pin, ledger, bundle or KNOWLEDGE change.

Rung file names carry the release (I_bfi_2026.rvt, not 2026/I_bfi.rvt alone)
because the acceptance folder and the viewer key on BASENAME: three releases'
I_bfi.rvt would collide in experiments/acceptance/ (probe_batch refuses it).

USAGE (repo root):
  .venv/bin/python tools/genesis_identity.py build --release all [--with-guid] [--json]
  .venv/bin/python tools/genesis_identity.py check --release 2025
  .venv/bin/python tools/genesis_identity.py gate  --release all            # probe_batch check
  .venv/bin/python tools/genesis_identity.py gate  --release all --stage    # STAGE (stop at READY)
  .venv/bin/python tools/genesis_identity.py ready --batch 60               # #19's one command
Exit code: 0 = every rung passed its assertions (gate: admissible), 2 = a rung
failed an assertion / the gate refused, 1 = error.
"""
from __future__ import annotations

import argparse
import dataclasses
import functools
import glob
import io
import json
import os
import re
import struct
import sys
import time
import uuid
import zipfile
from collections import Counter
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Sequence, Tuple
from xml.sax.saxutils import escape as _xml_escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import probe_batch as PB                                         # noqa: E402  (stdlib-only: rel, digests, pins, gate)
from rvt import ecc                                              # noqa: E402
from rvt import identity as ID                                   # noqa: E402
from rvt import stream_encoders as se                            # noqa: E402
from rvt.cfb_writer import write_cfb                             # noqa: E402
from rvt.container import open_rvt                               # noqa: E402
from rvt.genesis.house_standard import PROJECT_INFO              # noqa: E402
from rvt.meta import parse_project_info, parse_transmission      # noqa: E402
from rvt.provenance import AUTODESK_EMPLOYEE_USERNAMES           # noqa: E402
from rvt.provenance import identity_report as prov_identity      # noqa: E402
from rvt.roundtrip import read_entries                           # noqa: E402
from rvt.validate import validate_file                           # noqa: E402
from rvt.versions import detect_release                          # noqa: E402
from rvt.writer import gzip_member                               # noqa: E402

rel, sha256_of, md5_of = PB.rel, PB.sha256_of, PB.md5_of

OUT_DIR = os.path.join(ROOT, "experiments", "identity_g2")
TOOL = "tools/genesis_identity.py"
#: username written into BFI and every DocumentIncrementTable save episode --
#: '' is what rvt.commit (the certified front-door path) writes
USERNAME = ""
#: fixed timestamps so a rebuild reproduces the candidate sha256 table
TIMESTAMP_ISO = "2026-08-09T12:00:00Z"
ZIP_DATE_TIME = (2026, 8, 9, 12, 0, 0)
#: PartAtom vocabulary (format interface; the VALUES are ours) -- the same
#: element names / namespaces tools/genesis_assemble.our_project_information_zip
#: writes for G0 (which hard-codes product-version 2026 and G0's timestamp);
#: promoting one parameterised encoder into the engine next to
#: rvt.meta.parse_project_info is filed as a follow-up, not done from a tool
PARTATOM_NS = "urn:schemas-autodesk-com:partatom"
ATOM_NS = "http://www.w3.org/2005/Atom"
#: byte-scan needles: inherited usernames (rvt.provenance's employee set) and
#: absolute foreign path stems.  Scanned case-insensitively as UTF-8 and
#: UTF-16LE over every stream's raw, de-paged and inflated bytes.
PATH_NEEDLES: Tuple[str, ...] = (
    "C:\\Users\\", "\\AppData\\Local\\", "ProgramData\\Autodesk",
    "Program Files\\Autodesk", "OneDrive - Autodesk", "\\Desktop\\Downloadable Files",
)
NEEDLES: Tuple[str, ...] = tuple(sorted(AUTODESK_EMPLOYEE_USERNAMES)) + PATH_NEEDLES
#: the committed JSON (rungs.json / probes.json) is a dev-only probe manifest:
#: it is stamped PROOF-ONLY and never repeats a sample maintainer's login --
#: every inherited username decoded from the base is written as <employee_N>
#: (hard rule 3; the record redacts the same way).  In-memory reports keep the
#: raw values so the assertions compare real bytes.
PROOF_ONLY_STAMP = ("PROOF-ONLY -- dev probe manifest of tools/genesis_identity.py; decoded sample "
                    "identity values are redacted (<employee_N> = an Autodesk sample maintainer's "
                    "login, in rvt.provenance.AUTODESK_EMPLOYEE_USERNAMES order); nothing here ships")
_REDACT = {name: f"<employee_{i + 1}>" for i, name in enumerate(sorted(AUTODESK_EMPLOYEE_USERNAMES))}
_REDACT_RE = re.compile("|".join(re.escape(n) for n in sorted(_REDACT, key=len, reverse=True)), re.I)


def redacted(report: Any) -> Any:
    """A deep copy of a JSON-able report with every employee login replaced by
    its <employee_N> placeholder (in keys, values and embedded paths)."""
    text = json.dumps(report, default=str)
    return json.loads(_REDACT_RE.sub(lambda m: _REDACT[m.group(0).lower()], text))


# ---------------------------------------------------------------------------
# the pinned bases: probe_batch's pins + ledger (one resolver for build AND gate)
# ---------------------------------------------------------------------------
@functools.lru_cache(maxsize=None)
def ledger() -> "PB.Ledger":
    return PB.Ledger.load()


@functools.lru_cache(maxsize=None)
def pinned_bases() -> Dict[int, Dict[str, Any]]:
    """{year: {path, ledger_relpath, sha256}} for every genesis pin whose pinned
    relpath is LEDGER-CERTIFIED and whose bytes are on disk (repo compose output
    or plugin/assets/genesis/), sha256-verified -- exactly the file probe_batch
    will cut the batch control from."""
    lg = ledger()
    out: Dict[int, Dict[str, Any]] = {}
    for pin in lg.pins:
        on_disk = lg.pinned_certified_on_disk(pin.release)
        if on_disk:
            out[pin.release] = {"path": PB.abspath(on_disk), "ledger_relpath": pin.relpath,
                                "sha256": pin.sha256}
    return out


def pin_of(year: int) -> Dict[str, Any]:
    pin = pinned_bases().get(int(year))
    if pin is None:
        raise SystemExit(f"release {year}: no ledger-certified, sha-verified genesis pin on disk "
                         f"(have: {sorted(pinned_bases())})")
    return pin


def parse_years(text: str) -> List[int]:
    """'all' | '2026' | '2026,2025' -> release years, newest first."""
    if str(text).strip().lower() == "all":
        return sorted(pinned_bases(), reverse=True)
    years = [int(tok) for tok in str(text).replace(" ", "").split(",") if tok]
    for y in years:
        pin_of(y)                                               # unknown release -> SystemExit naming the known ones
    return years


# ---------------------------------------------------------------------------
# per-family stream authors: (doc, ctx) -> {stream_name: new_raw_bytes}
# ---------------------------------------------------------------------------
class Ctx(NamedTuple):
    year: int
    pinned_name: str        # G_ABPD[_20xx].rvt -- the name #19 re-pins the candidate under
    base_sha256: str


def own_bfi(doc, ctx: Ctx) -> Dict[str, bytes]:
    """BasicFileInfo with OUR identity: author/client = the product placeholder
    (rvt.identity defaults, counsel C1), username '', last_save_path = a bare
    filename, nil central/model identity -- and the CURRENT document GUID kept
    (== Global/History entry 0), exactly as rvt.commit does."""
    raw = doc.logical("BasicFileInfo")
    cur = se.decode_basic_file_info(raw)["unique_document_guid"]
    return {"BasicFileInfo": ID.own_basic_file_info(raw, out_path=ctx.pinned_name,
                                                     username=USERNAME, document_guid=cur)}


def own_dit(doc, ctx: Ctx) -> Dict[str, bytes]:
    """Global/DocumentIncrementTable with every save-episode username ours."""
    name = "Global/DocumentIncrementTable"
    if len(doc.members(name)) != 1:
        raise ValueError(f"{name}: expected exactly one gzip member, found {len(doc.members(name))}")
    return {name: ID.own_increment_table_stream(doc.raw(name), doc.prefix(name), doc.inflate(name, 0),
                                                username=USERNAME)}


def our_project_information_zip(document_guid: str, *, filename: str, product_version: int) -> bytes:
    """OUR ProjectInformation stream: ZIP { Revit<guid>.project.xml } holding a
    PartAtom entry with OUR project-info values (rvt.genesis.house_standard.
    PROJECT_INFO -- the same source the base's ProjectInfo element was authored
    from) and NO directory in the member name."""
    pm, x = PROJECT_INFO, _xml_escape
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<entry xmlns="{ATOM_NS}" xmlns:A="{PARTATOM_NS}">'
        f'<title>{x(os.path.splitext(filename)[0])}</title>'
        f'<updated>{TIMESTAMP_ISO}</updated>'
        '<A:taxonomy><term>adsk:revit</term><label>Autodesk Revit</label></A:taxonomy>'
        '<A:taxonomy><term>adsk:revit:grouping</term>'
        '<label>Autodesk Revit Grouping</label></A:taxonomy>'
        '<link rel="design-2d" type="application/rvt" href=".">'
        '<A:design-file>'
        f'<A:title>{x(filename)}</A:title>'
        '<A:product>Revit</A:product>'
        f'<A:product-version>{int(product_version)}</A:product-version>'
        f'<A:updated>{TIMESTAMP_ISO}</A:updated>'
        '</A:design-file></link>'
        '<A:features><A:feature><A:title>Project Information</A:title>'
        '<A:group><A:title>Identity Data</A:title>'
        f'<Project_Issue_Date displayName="Project Issue Date" type="system" '
        f'typeOfParameter="Text">{x(pm["issue_date"])}</Project_Issue_Date>'
        f'<Project_Status displayName="Project Status" type="system" '
        f'typeOfParameter="Text">{x(pm["project_status"])}</Project_Status>'
        f'<Client_Name displayName="Client Name" type="system" '
        f'typeOfParameter="Text">{x(pm["client_name"])}</Client_Name>'
        f'<Project_Address displayName="Project Address" type="system" '
        f'typeOfParameter="Multiline Text">{x(pm["address"])}</Project_Address>'
        f'<Project_Name displayName="Project Name" type="system" '
        f'typeOfParameter="Text">{x(pm["project_name"])}</Project_Name>'
        f'<Project_Number displayName="Project Number" type="system" '
        f'typeOfParameter="Text">{x(pm["project_number"])}</Project_Number>'
        '</A:group></A:feature></A:features></entry>'
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        zi = zipfile.ZipInfo(f"Revit{document_guid}.project.xml", date_time=ZIP_DATE_TIME)
        zi.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(zi, xml.encode("utf-8"))
    return buf.getvalue()


def own_pi(doc, ctx: Ctx) -> Dict[str, bytes]:
    guid = se.decode_basic_file_info(doc.logical("BasicFileInfo"))["unique_document_guid"]
    return {"ProjectInformation": our_project_information_zip(
        str(guid), filename=ctx.pinned_name, product_version=ctx.year)}


_EFR_RE = re.compile(r"<ExternalFileReference>.*?</ExternalFileReference>", re.S)
_LSP_RE = re.compile(r"<LastSavedPath>(.*?)</LastSavedPath>", re.S)
_LSAP_RE = re.compile(r"<LastSavedAbsolutePath>.*?</LastSavedAbsolutePath>", re.S)


def own_transmission_xml(xml: str) -> Tuple[str, int]:
    """Rewrite each ExternalFileReference's LastSavedAbsolutePath to that
    reference's own (relative) LastSavedPath -- the minimal change that drops
    the inherited absolute foreign paths and keeps every reference, element id,
    path type and load state exactly as the certified base has them.  Returns
    (xml, references_rewritten)."""
    n = 0

    def _fix(m: "re.Match[str]") -> str:
        nonlocal n
        block = m.group(0)
        lsp = _LSP_RE.search(block)
        relative = lsp.group(1) if lsp else ""
        new_block, k = _LSAP_RE.subn(
            lambda _m: f"<LastSavedAbsolutePath>{relative}</LastSavedAbsolutePath>", block)
        n += k
        return new_block

    return _EFR_RE.sub(_fix, xml), n


def encode_transmission(xml: str) -> bytes:
    """TransmissionData framing: u32 UTF-16 code-unit count + UTF-16LE XML."""
    body = xml.encode("utf-16-le")
    return struct.pack("<I", len(body) // 2) + body


def own_td(doc, ctx: Ctx) -> Dict[str, bytes]:
    td = parse_transmission(doc.logical("TransmissionData"))
    if not td.get("size_ok"):
        raise ValueError("TransmissionData: u32 char count does not match the stream length")
    xml, _n = own_transmission_xml(td["xml"])
    return {"TransmissionData": encode_transmission(xml)}


def own_guid(doc, ctx: Ctx) -> Dict[str, bytes]:
    """OPTIONAL higher-risk rung: a NEW document GUID, coherent across the two
    streams that carry it (BasicFileInfo unique/central episode GUID and
    Global/History entry 0).  Deterministic (uuid5 of the base digest) so the
    candidate hashes reproduce.  Nothing else in BFI changes on this rung."""
    new_guid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"tekton:genesis-identity:{ctx.base_sha256}"))
    raw_bfi = doc.logical("BasicFileInfo")
    bfi = se.decode_basic_file_info(raw_bfi)
    if se.encode_basic_file_info(bfi, regenerate_mirror=True) != raw_bfi:
        raise ValueError("BasicFileInfo codec is not byte-exact on this base; refusing a GUID-only rung")
    old_guid = str(bfi["unique_document_guid"]).lower()
    hname = "Global/History"
    infl = doc.inflate(hname, 0)
    hist = se.decode_history(infl)
    if se.encode_history(hist) != infl:
        raise ValueError("History codec is not byte-exact on this base; refusing a GUID-only rung")
    entry0_guid, tag = hist["entries"][0]
    if str(entry0_guid).lower() != old_guid:
        raise ValueError("base violates BFI GUID == History[0]; refusing to build on it")
    bfi["unique_document_guid"] = bfi["central_episode_guid"] = new_guid
    hist["entries"][0] = (new_guid, tag)
    return {
        "BasicFileInfo": se.encode_basic_file_info(bfi, regenerate_mirror=True),
        hname: ecc.frame_stream(doc.prefix(hname) + gzip_member(se.encode_history(hist), level=3)),
    }


# ---------------------------------------------------------------------------
# the family registry + rung specs (everything else derives from these two)
# ---------------------------------------------------------------------------
class Family(NamedTuple):
    streams: Tuple[str, ...]        # the CFB streams this family is ALLOWED to change
    author: Callable[[Any, Ctx], Dict[str, bytes]]
    clears: frozenset               # rvt.provenance identity violation fields it must clear
    scrubs: bool                    # rewrites the whole surface => its streams must scan clean


FAMILY: Dict[str, Family] = {
    "bfi": Family(("BasicFileInfo",), own_bfi,
                  frozenset({"author", "client_app_name", "last_save_path", "username"}), True),
    "dit": Family(("Global/DocumentIncrementTable",), own_dit,
                  frozenset({"DocumentIncrementTable.username"}), True),
    "pi": Family(("ProjectInformation",), own_pi, frozenset(), True),
    "td": Family(("TransmissionData",), own_td, frozenset(), True),
    # optional, higher-risk: a NEW document GUID must move BFI and History[0]
    # together (rvt.streams_edit cross-check invariant; validate.py L2 error);
    # it deliberately leaves BFI's other fields as the base has them
    "guid": Family(("BasicFileInfo", "Global/History"), own_guid, frozenset(), False),
}
#: the four single-surface families, in upload order after I_all
FAMILIES: Tuple[str, ...] = ("bfi", "dit", "pi", "td")


def streams_of(families: Sequence[str]) -> List[str]:
    return sorted({s for f in families for s in FAMILY[f].streams})


#: streams a scrubbing family rewrites wholesale: a needle left in one of these
#: after its rung is a tool bug; a hit anywhere else is REPORTED as residue
#: outside the four metadata families (element data in a partition -- record)
OWNED_STREAMS = frozenset(streams_of([f for f in FAMILY if FAMILY[f].scrubs]))


class RungSpec(NamedTuple):
    tag: str
    families: Tuple[str, ...]
    kind: str                       # probe_batch kind
    risk: str

    @property
    def rung(self) -> str:
        return f"I_{self.tag}"

    def path(self, out_dir: str, year: int) -> str:
        return os.path.join(out_dir, str(year), f"{self.rung}_{year}.rvt")


def rung_specs(with_guid: bool = False, only: Optional[Sequence[str]] = None) -> List[RungSpec]:
    """Rungs in upload order: I_all (the candidate base) first, then singles."""
    specs = [RungSpec("all", FAMILIES, "candidate-base", "single surface x4 (the candidate)")]
    specs += [RungSpec(f, (f,), "probe", "single surface") for f in FAMILIES]
    if with_guid:
        specs.append(RungSpec("guid", ("guid",), "probe",
                              "higher (new document GUID; BFI + History[0] together)"))
    return [s for s in specs if only is None or s.tag in only]


SPEC_ORDER = {s.rung: i for i, s in enumerate(rung_specs(with_guid=True))}


def author_streams(base_path: str, families: Sequence[str], ctx: Ctx) -> Dict[str, bytes]:
    """New raw bytes for every stream the given families own."""
    new: Dict[str, bytes] = {}
    with open_rvt(base_path) as doc:
        for fam in families:
            new.update(FAMILY[fam].author(doc, ctx))
    return new


def write_rung(base_path: str, out_path: str, new_streams: Dict[str, bytes]) -> None:
    """The base's CFB entries with ONLY ``new_streams`` replaced (rvt.commit's
    write pattern; write_cfb reproduces an untouched pin byte-for-byte)."""
    entries = read_entries(base_path)
    missing = set(new_streams) - {e.path for e in entries if e.entry_type == "stream"}
    if missing:
        raise ValueError(f"streams not in base: {sorted(missing)}")
    out_entries = [dataclasses.replace(e, data=new_streams[e.path])
                   if (e.entry_type == "stream" and e.path in new_streams) else e
                   for e in entries]
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    write_cfb(out_path, out_entries)


# ---------------------------------------------------------------------------
# assertions on a built rung
# ---------------------------------------------------------------------------
def stream_diff(base_path: str, rung_path: str) -> Dict[str, Any]:
    """Entry-by-entry comparison: which streams changed, and whether every
    other directory entry (order, type, CLSID, state bits, FILETIMEs) is
    identical."""
    a, b = read_entries(base_path), read_entries(rung_path)
    out: Dict[str, Any] = {"changed": [], "identical": [], "structure_ok": True, "problems": []}
    if [(e.path, e.entry_type) for e in a] != [(e.path, e.entry_type) for e in b]:
        out["structure_ok"] = False
        out["problems"].append("directory entry list differs (paths / order / types)")
        return out
    for ea, eb in zip(a, b):
        for attr in ("clsid", "state_bits", "ctime", "mtime"):
            if getattr(ea, attr, None) != getattr(eb, attr, None):
                out["structure_ok"] = False
                out["problems"].append(f"{ea.path or '<root>'}: {attr} differs")
        if ea.entry_type == "stream":
            (out["identical"] if ea.data == eb.data else out["changed"]).append(ea.path)
    return out


def byte_scan(path: str, needles: Sequence[str] = NEEDLES) -> Dict[str, Any]:
    """Scan every stream's raw, de-paged and inflated bytes for inherited
    usernames + absolute foreign path stems (case-insensitive, UTF-8 and
    UTF-16LE).  Returns {hits: {stream: {needle: {view: count}}}, owned_hits,
    residual_hits} where 'owned' = the four metadata streams this tool rewrites
    and 'residual' = anywhere else (reported, never hidden)."""
    variants = {n: (n.lower().encode("utf-8"), n.lower().encode("utf-16-le")) for n in needles}
    hits: Dict[str, Dict[str, Dict[str, int]]] = {}
    with open_rvt(path) as doc:
        for s in doc.streams():
            views: Dict[str, bytes] = {"raw": doc.raw(s.name)}
            try:
                logical = doc.logical(s.name)
                if logical != views["raw"]:                     # unframed streams: logical IS raw
                    views["logical"] = logical
            except Exception:                                   # undecodable: raw only
                pass
            try:
                for i in range(len(doc.members(s.name))):
                    views[f"inflated{i}"] = doc.inflate(s.name, i)
            except Exception:
                pass
            for view, blob in views.items():
                low = blob.lower()
                for n, vs in variants.items():
                    c = sum(low.count(v) for v in vs)
                    if c:
                        hits.setdefault(s.name, {}).setdefault(n, {})[view] = c
    return {"needles": list(needles), "hits": hits,
            "owned_hits": {k: v for k, v in hits.items() if k in OWNED_STREAMS},
            "residual_hits": {k: v for k, v in hits.items() if k not in OWNED_STREAMS}}


def decode_identity(path: str) -> Dict[str, Any]:
    """What the four surfaces of ``path`` say, decoded (for round-trip checks
    and the record's inherited-fields table)."""
    out: Dict[str, Any] = {}
    with open_rvt(path) as doc:
        raw_bfi = doc.logical("BasicFileInfo")
        bfi = se.decode_basic_file_info(raw_bfi)
        out["bfi"] = {**ID.identity_report(raw_bfi),
                      **{k: bfi.get(k) for k in ("central_version_number", "central_model_identity",
                                                 "model_identity")}}
        dit = se.decode_increment_table(doc.inflate("Global/DocumentIncrementTable", 0))
        out["dit"] = {"records": len(dit.get("records") or []),
                      "records2_equal": (dit.get("records2") or dit.get("records")) == dit.get("records"),
                      "usernames": dict(Counter(r.get("username", "") for r in dit.get("records") or []))}
        hist = se.decode_history(doc.inflate("Global/History", 0))
        out["history"] = {"count": hist.get("hdr_count"), "entry0_guid": hist["entries"][0][0]}
        pi = parse_project_info(doc.logical("ProjectInformation"))
        out["pi"] = {"members": [m["filename"] for m in pi.get("members", [])],
                     "title": pi.get("title"), "updated": pi.get("updated"),
                     "design_file": (pi.get("link") or {}).get("design_file"),
                     "params": pi.get("params")}
        td = parse_transmission(doc.logical("TransmissionData"))
        out["td"] = {"size_ok": td.get("size_ok"), "is_transmitted": td.get("is_transmitted"),
                     "version": td.get("version"),
                     "references": [{k: r.get(k) for k in ("ElementId", "ExternalFileReferenceType",
                                                          "LastSavedPath", "LastSavedAbsolutePath",
                                                          "LastSavedLoadState")}
                                    for r in td.get("references", [])]}
    return out


def violation_fields(idr: Dict[str, Any]) -> List[str]:
    return sorted({v["field"] for v in idr["violations"]})


def check_rung(base_path: str, path: str, spec: RungSpec, year: int) -> Dict[str, Any]:
    """Every assertion the DONE names, as data + one 'ok' verdict."""
    families = spec.families
    expected = streams_of(families)
    problems: List[str] = []
    # 1. stream diff
    sd = stream_diff(base_path, path)
    problems += sd["problems"]
    if sorted(sd["changed"]) != expected:
        problems.append(f"changed streams {sorted(sd['changed'])} != intended {expected}")
    # 2. own-release validation
    detected = detect_release(path)
    if detected != int(year):
        problems.append(f"BasicFileInfo declares release {detected}, expected {year}")
    vrep = validate_file(path).to_json()
    verrors = [f for f in vrep.get("findings", []) if f.get("severity") == "error"]
    if verrors:
        problems.append(f"rvt_validate: {len(verrors)} error(s): "
                        + "; ".join(str(f.get('message') or f)[:120] for f in verrors[:3]))
    # 3. provenance identity policy: this rung's families clear their fields
    idr = prov_identity(path)
    viol = violation_fields(idr)
    still = sorted(set(viol) & frozenset().union(*(FAMILY[f].clears for f in families)))
    if still:
        problems.append(f"provenance identity violations this rung should have cleared: {still}")
    # 4. decode round-trips of what we wrote
    dec = decode_identity(path)
    if "bfi" in families:
        b = dec["bfi"]
        if (b["author"], b["client_app_name"]) != (ID.DEFAULT_AUTHOR, ID.DEFAULT_CLIENT_APP):
            problems.append(f"BFI author/client decode as {b['author']!r}/{b['client_app_name']!r}")
        if "\\" in (b["last_save_path"] or "") or "/" in (b["last_save_path"] or ""):
            problems.append(f"BFI last_save_path still a path: {b['last_save_path']!r}")
        if b["username"] != USERNAME:
            problems.append(f"BFI username {b['username']!r} != {USERNAME!r}")
    if str(dec["bfi"]["unique_document_guid"]).lower() != str(dec["history"]["entry0_guid"]).lower():
        problems.append("BFI unique_document_guid != Global/History entry 0 (coherence broken)")
    if "dit" in families:
        if set(dec["dit"]["usernames"]) != {USERNAME}:
            problems.append(f"DIT usernames decode as {dec['dit']['usernames']}")
        if not dec["dit"]["records2_equal"]:
            problems.append("DIT copy 2 != copy 1")
    if "pi" in families:
        problems += [f"ProjectInformation member name is still a path: {m!r}"
                     for m in dec["pi"]["members"] if "\\" in m or "/" in m]
    if "td" in families:
        if not dec["td"]["size_ok"]:
            problems.append("TransmissionData u32 count mismatch")
        for r in dec["td"]["references"]:
            ap = r.get("LastSavedAbsolutePath") or ""
            if re.match(r"^[A-Za-z]:\\", ap) or ap.startswith("\\\\"):
                problems.append(f"TransmissionData still absolute: {ap!r}")
    # 5. byte scan: a stream this rung REWROTE wholesale must carry no needle
    scan = byte_scan(path)
    scrubbed = set(streams_of([f for f in families if FAMILY[f].scrubs]))
    touched_dirty = {k: v for k, v in scan["owned_hits"].items() if k in scrubbed}
    if touched_dirty:
        problems.append(f"needles remain in rewritten stream(s): {touched_dirty}")
    return {
        "rung": spec.rung, "kind": spec.kind, "risk": spec.risk,
        "file": rel(path), "base": rel(base_path), "release": int(year),
        "families": list(families), "intended_streams": expected,
        "sha256": sha256_of(path), "md5": md5_of(path), "bytes": os.path.getsize(path),
        "stream_diff": {"changed": sd["changed"], "identical_count": len(sd["identical"]),
                        "structure_ok": sd["structure_ok"]},
        "validate": {"release_detected": detected, "counts": vrep["counts"],
                     "fallback": vrep.get("release_fallback"), "errors": verrors[:5]},
        "provenance_identity": {"ok": idr["ok"], "violation_fields": viol,
                                "dit_usernames": idr["dit_usernames"], "advisories": idr["advisories"]},
        "decoded": dec,
        "byte_scan": {"owned_hits": scan["owned_hits"], "residual_hits": scan["residual_hits"]},
        "problems": problems,
        "ok": not problems,
    }


# ---------------------------------------------------------------------------
# build / check a release  (build = author + write, then the SAME check)
# ---------------------------------------------------------------------------
def check_release(year: int, *, out_dir: str = OUT_DIR, with_guid: bool = False,
                  only: Optional[Sequence[str]] = None, verbose: bool = True) -> Dict[str, Any]:
    """Assert every rung of ``year`` under ``out_dir`` and (re)write
    <out_dir>/<year>/rungs.json -- the one report build, check, probes.json and
    the gate all read."""
    pin = pin_of(year)
    base = pin["path"]
    t0 = time.time()
    base_idr = prov_identity(base)
    base_scan = byte_scan(base)
    rungs: List[Dict[str, Any]] = []
    for spec in rung_specs(with_guid, only):
        path = spec.path(out_dir, year)
        if not os.path.isfile(path):
            rep: Dict[str, Any] = {"rung": spec.rung, "kind": spec.kind, "risk": spec.risk,
                                   "file": rel(path), "ok": False,
                                   "problems": ["not built (run `build` first)"]}
        else:
            rep = check_rung(base, path, spec, year)
        rungs.append(rep)
        if verbose:
            print(f"  [{'ok ' if rep['ok'] else 'FAIL'}] {rep['file']:48s} "
                  + (f"changed={rep['stream_diff']['changed']} "
                     f"validate={rep['validate']['counts'].get('error', 0)}err "
                     f"identity_violations={rep['provenance_identity']['violation_fields']} "
                     f"sha256={rep['sha256'][:12]}" if "sha256" in rep else ""))
            for p in rep["problems"]:
                print(f"         ! {p}")
    report = {
        "stamp": PROOF_ONLY_STAMP, "tool": TOOL, "release": int(year),
        "base": {"ledger_relpath": pin["ledger_relpath"], "on_disk": rel(base),
                 "sha256": pin["sha256"], "identity": decode_identity(base),
                 "provenance_identity": {"ok": base_idr["ok"],
                                         "violation_fields": violation_fields(base_idr),
                                         "dit_usernames": base_idr["dit_usernames"]},
                 "byte_scan": {"owned_hits": base_scan["owned_hits"],
                               "residual_hits": base_scan["residual_hits"]}},
        "username": USERNAME, "timestamp_iso": TIMESTAMP_ISO, "with_guid": bool(with_guid),
        "rungs": rungs,
        "ok": all(r["ok"] for r in rungs),
        "seconds": round(time.time() - t0, 1),
    }
    os.makedirs(os.path.join(out_dir, str(year)), exist_ok=True)
    with open(os.path.join(out_dir, str(year), "rungs.json"), "w") as fh:
        json.dump(redacted(report), fh, indent=1)
    return report


def build_release(year: int, *, out_dir: str = OUT_DIR, with_guid: bool = False,
                  only: Optional[Sequence[str]] = None, verbose: bool = True) -> Dict[str, Any]:
    pin = pin_of(year)
    ctx = Ctx(int(year), os.path.basename(pin["ledger_relpath"]), pin["sha256"])
    for spec in rung_specs(with_guid, only):
        write_rung(pin["path"], spec.path(out_dir, year), author_streams(pin["path"], spec.families, ctx))
    return check_release(year, out_dir=out_dir, with_guid=with_guid, only=only, verbose=verbose)


# ---------------------------------------------------------------------------
# probes.json: a pure function of every <year>/rungs.json under out_dir
# ---------------------------------------------------------------------------
EXPECTED_READING = (
    "Upload order per release: CONTROL (byte-identical pinned base) first, then I_all; the "
    "singles only if I_all FAILS. Prior evidence: V30/V31 (docs/acceptance-log.md) -- the reader "
    "does NOT gate on the author/client strings and accepts a scrubbed path + regenerated GUIDs "
    "on the rst lineage; V32 -- scrubbed DIT usernames PASS on that lineage; genesis-audit "
    "VERDICTS #36 -- the only single-surface identity probes on a composed base (E4 = BFI, "
    "E5 = DIT) FAILED as empty-footer-blob artefacts, so BFI/DIT are UNTESTED in isolation "
    "there; #47 premise correction -- G_ABPD's identity surfaces are byte-inherited from rst. "
    "Expected: I_all PASS (=> #19 re-pins it); if I_all FAILS the singles name the surface."
)


def load_rungs(out_dir: str = OUT_DIR) -> Dict[int, Dict[str, Any]]:
    """{year: rungs.json report} for every release built under out_dir."""
    out: Dict[int, Dict[str, Any]] = {}
    for p in glob.glob(os.path.join(out_dir, "*", "rungs.json")):
        with open(p) as fh:
            rep = json.load(fh)
        out[int(rep["release"])] = rep
    return out


def write_probes_json(out_dir: str = OUT_DIR) -> str:
    reports = load_rungs(out_dir)
    releases: Dict[str, Any] = {}
    probes: List[Dict[str, Any]] = []
    for year in sorted(reports, reverse=True):
        rep = reports[year]
        base = rep["base"]
        releases[str(year)] = {
            "base": base["ledger_relpath"], "base_on_disk": base["on_disk"], "base_sha256": base["sha256"],
            "base_identity_violations": base["provenance_identity"]["violation_fields"],
            "base_residual_needle_hits": base["byte_scan"]["residual_hits"], "ok": rep["ok"],
        }
        for r in sorted(rep["rungs"], key=lambda r: SPEC_ORDER.get(r["rung"], len(SPEC_ORDER))):
            if "sha256" not in r:                                # not built: nothing to declare
                continue
            probes.append({
                "name": os.path.splitext(os.path.basename(r["file"]))[0],
                "rung": r["rung"], "file": r["file"], "kind": r["kind"], "release": int(year),
                "base": base["ledger_relpath"], "base_on_disk": base["on_disk"],
                "base_sha256": base["sha256"],
                "axis": r["families"], "changed_streams": r["stream_diff"]["changed"],
                "sha256": r["sha256"], "md5": r["md5"], "bytes": r["bytes"],
                "validate_errors": r["validate"]["counts"].get("error", 0),
                "identity_violations_left": r["provenance_identity"]["violation_fields"],
                "residual_needle_hits": r["byte_scan"]["residual_hits"],
                "risk": r["risk"], "checks_ok": r["ok"],
            })
    manifest = {
        "schema": "tekton.identity-g2.probes/1", "stamp": PROOF_ONLY_STAMP,
        "tool": TOOL, "issue": "#134 (candidates + instrument) -> #19 (upload, re-pin, ledger)",
        "purpose": ("G2 identity rungs on the pinned composed genesis bases: each probe = the "
                    "base's bytes with exactly ONE identity field family rewritten to ours; "
                    "I_all = all four = the candidate base; the untouched pin is the control."),
        "kinds": {"I_all": "candidate-base", "I_bfi|I_dit|I_pi|I_td": "probe",
                  "I_guid": "probe (optional, higher-risk: new document GUID)"},
        "expected_reading": EXPECTED_READING,
        "gate": ("tools/genesis_identity.py gate --release <year> [--stage] == tools/probe_batch.py "
                 "check|stage <singles> --candidate-base <I_all> --manifest experiments/identity_g2/probes.json"),
        "releases": releases,
        "probes": probes,
    }
    path = os.path.join(out_dir, "probes.json")
    with open(path, "w") as fh:
        json.dump(manifest, fh, indent=1, default=str)
    return path


# ---------------------------------------------------------------------------
# the probe_batch gate (check / stage), one batch per release, FROM probes.json
# ---------------------------------------------------------------------------
def gate_release(year: int, *, out_dir: str = OUT_DIR, stage: bool = False, note: str = "",
                 acceptance_dir: str = PB.ACCEPTANCE, batch_n: Optional[int] = None) -> Dict[str, Any]:
    manifest = os.path.join(out_dir, "probes.json")
    declared = []
    if os.path.isfile(manifest):
        with open(manifest) as fh:
            declared = [p for p in json.load(fh).get("probes", []) if int(p["release"]) == int(year)]
    violations: List[str] = []
    if not declared:
        violations.append(f"Revit {year}: nothing declared in {rel(manifest)} -- run `build` first")
    for p in declared:                                          # our own verdicts gate first
        a = PB.abspath(p["file"])
        if not os.path.isfile(a):
            violations.append(f"{p['file']}: declared in probes.json but not on disk -- rebuild")
        elif sha256_of(a) != p["sha256"]:
            violations.append(f"{p['file']}: bytes differ from probes.json (stale build) -- rebuild")
        if not p["checks_ok"]:
            violations.append(f"{p['file']}: FAILED its own build/check assertions -- never staged")
    cands = [p["file"] for p in declared if p["kind"] == "candidate-base"]
    probes = [p["file"] for p in declared if p["kind"] == "probe"]
    out: Dict[str, Any] = {"release": int(year), "mode": "stage" if stage else "check",
                           "candidate_base": cands, "probes": probes,
                           "control_source": ledger().control_source(year)}
    entries: List[Any] = []
    if not violations:
        if stage:
            try:
                man = PB.stage_batch(probes, candidate_bases=cands, manifest_override=manifest,
                                     ledger=ledger(), out_dir=acceptance_dir, batch_n=batch_n,
                                     note=note or f"#134 G2 identity rungs, Revit {year}: I_all "
                                                  f"candidate-base + single-surface probes on the pinned base")
                out.update(batch=man["batch"], manifest_path=man["manifest_path"],
                           reading_order=man["reading_order"],
                           control_source=man["entries"][0]["control_source"])
                out["entries"] = [e for e in man["entries"] if e["kind"] != "control"]
            except PB.GateRefusal as g:
                violations = list(g.violations)
        else:
            entries, violations = PB.check_batch(probes, ledger(), candidate_bases=cands,
                                                 manifest_override=manifest)
    out.setdefault("entries", [e.to_json() for e in entries])
    out.update(violations=violations, admissible=not violations)
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _run_build(args: argparse.Namespace) -> bool:
    ok = True
    for y in args.years:
        print(f"== Revit {y}: building identity rungs into {rel(os.path.join(args.out, str(y)))}/")
        ok = build_release(y, out_dir=args.out, with_guid=args.with_guid)["ok"] and ok
    print(f"probes.json: {rel(write_probes_json(args.out))}")
    if args.json:
        print(json.dumps({y: r for y, r in load_rungs(args.out).items() if y in args.years},
                         indent=1, default=str))
    print("BUILD:", "OK -- every rung passed its assertions" if ok else "FAIL -- see ! lines")
    return ok


def _run_check(args: argparse.Namespace) -> bool:
    ok = True
    for y in args.years:
        print(f"== Revit {y}: checking {rel(os.path.join(args.out, str(y)))}/")
        ok = check_release(y, out_dir=args.out, with_guid=args.with_guid)["ok"] and ok
    print(f"probes.json: {rel(write_probes_json(args.out))}")
    if args.json:
        print(json.dumps({y: r for y, r in load_rungs(args.out).items() if y in args.years},
                         indent=1, default=str))
    print("CHECK:", "OK" if ok else "FAIL")
    return ok


def _run_gate(args: argparse.Namespace, stage: Optional[bool] = None) -> bool:
    stage = args.stage if stage is None else stage
    results = {}
    for i, y in enumerate(args.years):
        g = results[y] = gate_release(y, out_dir=args.out, stage=stage, note=args.note,
                                      batch_n=(args.batch + i) if args.batch is not None else None)
        extra = f" -> STAGED batch {g['batch']} ({g['manifest_path']}); READY for upload" if g.get("batch") else ""
        print(f"== Revit {y}: probe_batch {g['mode']}: {'ADMISSIBLE' if g['admissible'] else 'REFUSED'}{extra}")
        for v in g["violations"]:
            print(f"   x {v}")
        for e in g["entries"]:
            print(f"   {e['kind']:15s} {e['file']:52s} base={e.get('base')} [{e.get('base_status')}]")
        print(f"   control source: {g['control_source']}")
        if g.get("reading_order"):
            print(f"   upload order: {' -> '.join(g['reading_order'])}  (singles only if I_all FAILS)")
    if args.json:
        print(json.dumps(results, indent=1, default=str))
    return all(g["admissible"] for g in results.values())


def _run_ready(args: argparse.Namespace) -> bool:
    ok = _run_build(args) and _run_gate(args, stage=True)
    print("READY: upload each batch CONTROL first, then I_all; the singles only if I_all FAILS; "
          "record verdicts with tools/probe_batch.py verdicts" if ok else "REFUSED: see ! / x lines")
    return ok


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    runners = {"build": _run_build, "check": _run_check, "gate": _run_gate, "ready": _run_ready}
    for name, help_ in (("build", "write the rungs, then check"),
                        ("check", "assert built rungs; (re)write rungs.json + probes.json"),
                        ("gate", "tools/probe_batch.py check (default) or --stage, one batch per release"),
                        ("ready", "the #19 one-command: build + assert + STAGE every release (stop at READY)")):
        p = sub.add_parser(name, help=help_)
        p.add_argument("--release", default="all", help="2026 | 2025 | 2024 | 2026,2025 | all (default)")
        p.add_argument("--out", default=OUT_DIR, help="output dir (default experiments/identity_g2)")
        p.add_argument("--with-guid", action="store_true", help="also build/check the optional I_guid rung")
        p.add_argument("--json", action="store_true", help="print the JSON report")
        if name in ("gate", "ready"):
            p.add_argument("--note", default="")
            p.add_argument("--batch", type=int, default=None,
                           help="batch number of the FIRST release (next releases +1, +2); default: next free")
        if name == "gate":
            p.add_argument("--stage", action="store_true", help="STAGE into experiments/acceptance (stop at READY)")
    args = ap.parse_args(argv)
    args.years = parse_years(args.release)
    args.out = os.path.abspath(args.out)
    return 0 if runners[args.cmd](args) else 2


if __name__ == "__main__":
    sys.exit(main())
