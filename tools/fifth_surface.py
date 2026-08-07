#!/usr/bin/env python
"""fifth_surface.py -- THE FIFTH-SURFACE HUNT + REGISTRATION-ROW FORENSICS
(regcorner stream, 2026-08-05, post-verdict-#34).

THE QUESTION.  H9 (byte-copied native host constellation + Autodesk famdoc +
V20-shape instance, freshly REGISTERED as a new unit) FAILS the open-time
audit while H10 (identical minus the instance) PASSES and V20 (instance of a
NATIVELY-registered unit) PASSES.  Symbol form, famdoc content, host
elements, instance shape: all exonerated by byte-copy.  Exactly two suspects
remain: (1) the CONTENT of the registration rows famload authors
(ContentDocuments entry / ContentTable record / FamilyMgr entry / the
partition unit itself) vs the native rows' shapes; (2) a FIFTH SURFACE --
some project-side reference keyed on content GUID / unit identity outside
the four-registry model, populated for the 52 native units but never by our
loads, visited only on the instance walk.

WHAT THIS TOOL DOES (read-only over every .rvt; writes JSON only):

  sweep       The exhaustive identity sweep of ONE file: every stream,
              every surface that references (a) a content-document GUID of
              any unit (bytes_le + ascii + utf-16, typed tree walks of
              Global/Latest, every ContentDocuments embedded ADocument,
              every decoded side-stream model, every partition unit
              segment), (b) any per-unit identity GUID (famDocGUID +
              embedded DocumentHistory GUIDs), (c) a host Family /
              FamilySymbol / FamilySurrogate / famdoc element id
              (schema-typed ElementId leaves only -- no noisy int scans).
              Aggregated surface-by-surface with per-unit coverage.

  crosscheck  sweep the native sample + H9 + H10 + H7; for every surface
              where native units have entries, ask whether the NEWLY
              REGISTERED unit has one; rank the missing surfaces by
              instance-walk reachability.  -> fifth_surface.json

  rowdiff     Field-by-field forensics of the four registration surfaces
              for the SAME famdoc: the donor unit's native rows (rst
              sample, unit 36) vs the rows famload authored in H9 (and the
              H7 flavour), remap-normalized so only CONTENT differences
              remain; plus the episode-stamp coherence law (m_EpisodeCounts
              vs the unit's actual record stamps) measured across all 52
              native units and our unit.  -> row_diff.json

Territory: this tool + experiments/regcorner/** + docs/inbox/
regcorner-surface.md.  Nothing under src/ is edited; no .rvt is written.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import sys
import time
import uuid
from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (os.path.join(ROOT, "src"), HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

RST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
H9 = os.path.join(ROOT, "experiments", "hostpair", "H9.rvt")
H10 = os.path.join(ROOT, "experiments", "hostpair", "H10.rvt")
H7 = os.path.join(ROOT, "experiments", "famdoc_bisect", "H7.rvt")
OUT_DIR = os.path.join(ROOT, "experiments", "regcorner")

DONOR_UNIT = 36
DONOR_GUID = "09982dbb-c022-48fc-a116-6d8ba6867fdb"

GUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
NIL_GUID = "00000000-0000-0000-0000-000000000000"
IDX_RE = re.compile(r"\[\d+\]")


def relp(p: str) -> str:
    try:
        return os.path.relpath(p, ROOT)
    except ValueError:                                    # pragma: no cover
        return p


def md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1, sort_keys=False, default=_json_default)
    os.replace(tmp, path)
    print(f"  wrote {relp(path)} ({os.path.getsize(path):,} B)")


def _json_default(o: Any) -> Any:
    if isinstance(o, (bytes, bytearray)):
        return o.hex()
    if isinstance(o, set):
        return sorted(o)
    return str(o)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ===========================================================================
# generic tree walking (decoded object values)
# ===========================================================================

def iter_tree(value: Any, path: str = ""):
    """Yield (path, scalar) for every leaf of a decoded value tree.
    Pointer holders render as ->Class, lists as [i]."""
    if isinstance(value, dict):
        if "ptr_class" in value:
            yield from iter_tree(value.get("value"), f"{path}->{value['ptr_class']}")
            return
        if "weakref" in value and len(value) == 1:
            yield (f"{path}.weakref", value["weakref"])
            return
        for k, v in value.items():
            yield from iter_tree(v, f"{path}.{k}" if path else k)
        return
    if isinstance(value, (list, tuple)):
        for i, x in enumerate(value):
            yield from iter_tree(x, f"{path}[{i}]")
        return
    yield (path, value)


def guid_leaves(value: Any, path: str = "") -> List[Tuple[str, str]]:
    """(path, guid-lower) for every string leaf that IS a GUID."""
    out = []
    for p, v in iter_tree(value, path):
        if isinstance(v, str) and len(v) == 36 and GUID_RE.match(v):
            out.append((p, v.lower()))
    return out


def surface_sig(path: str) -> str:
    """Normalize a concrete path to its surface signature ([N] -> [])."""
    return IDX_RE.sub("[]", path)


# ===========================================================================
# per-file identity model
# ===========================================================================

class Identity:
    """Everything that names a unit: GUIDs + registration-relevant ids."""

    def __init__(self, path: str, decode_embedded: bool = True):
        from rvt.families import FamilyIndex, family_documents, content_document_adoc
        from rvt import adocument as A
        from rvt.container import open_rvt
        from rvt.stream_encoders import decode_elemtable
        log(f"identity: {relp(path)}")
        self.path = path
        self.idx = FamilyIndex(path)
        self.units = self.idx.units                       # UnitInfo list
        self.unit_guids: List[str] = [u.guid.lower() for u in self.units
                                      if u.guid]
        self.guid_to_unit: Dict[str, int] = {u.guid.lower(): u.index
                                             for u in self.units if u.guid}
        self.fams = family_documents(self.idx)
        with open_rvt(path) as f:
            self.et = decode_elemtable(f.inflate("Global/ElemTable"))
            latest = f.inflate("Global/Latest")
        self.et_rows: Dict[int, tuple] = {r[4]: r for r in self.et["records"]}
        self.adoc = A.decode_latest(latest)
        if not self.adoc.clean:                           # pragma: no cover
            raise RuntimeError(f"{path}: ADocument decode not clean")
        # famdoc record ids per unit (seq 102 keys)
        self.famdoc_ids: Dict[int, List[int]] = {}
        for u in self.units:
            if u.index == 0:
                continue
            self.famdoc_ids[u.index] = sorted(
                self.idx.unit_records(u.index).get(102, {}).keys())
        # surrogate map from FamilyMgr (native + loaded entries)
        self.surrogate_of_guid: Dict[str, List[int]] = defaultdict(list)
        fm = self._appinfo("FamilyMgr") or {}
        for e in fm.get("m_arrLoadedFamilyInfo") or []:
            for g in e.get("m_familyDocGUIDs") or []:
                self.surrogate_of_guid[str(g).lower()].append(
                    int(e.get("m_surrogateId", -1)))
        # id -> (unit guid, ref_kind)
        self.id_map: Dict[int, Tuple[str, str]] = {}
        for row in self.fams:
            if row["unit"] is None:
                continue
            g = (row["content_doc_guid"] or "").lower()
            self.id_map[int(row["family_id"])] = (g, "family")
            for s in row["symbols"]:
                self.id_map[int(s["symbol_id"])] = (g, "symbol")
        for g, surs in self.surrogate_of_guid.items():
            for s in surs:
                if s > 0:
                    self.id_map.setdefault(int(s), (g, "surrogate"))
        # ElemTable owner-chain descendants of each family id -> cluster-owned
        children: Dict[int, List[int]] = defaultdict(list)
        for r in self.et["records"]:
            if r[5] > 0:
                children[r[5]].append(r[4])
        fam_ids = [i for i, (_g, k) in list(self.id_map.items()) if k == "family"]
        for fid in fam_ids:
            g = self.id_map[fid][0]
            stack = list(children.get(fid, []))
            while stack:
                x = stack.pop()
                if x not in self.id_map:
                    self.id_map[x] = (g, "cluster-owned")
                    stack.extend(children.get(x, []))
        for u_index, ids in self.famdoc_ids.items():
            g = (self.units[u_index].guid or "").lower()
            for i in ids:
                self.id_map.setdefault(int(i), (g, "famdoc"))
        # per-unit identity GUIDs beyond the content GUID
        self.aux_guids: Dict[str, Tuple[str, str]] = {}   # guid -> (unit guid, label)
        for row in self.fams:
            if row["unit"] is None:
                continue
            g = (row["content_doc_guid"] or "").lower()
            fdg = (row["fam_doc_guid"] or "").lower()
            if fdg and fdg != NIL_GUID:
                self.aux_guids[fdg] = (g, "famDocGUID")
        self.embedded_adocs: Dict[str, Any] = {}          # content guid -> decoded value
        if decode_embedded:
            for g in self.unit_guids:
                if self.guid_to_unit.get(g) == 0:
                    continue
                blob = content_document_adoc(self.idx, g)
                if not blob:
                    continue
                try:
                    ad = A.decode_latest(blob)
                except Exception:                          # pragma: no cover
                    continue
                self.embedded_adocs[g] = ad.value
                hist = ((ad.value.get("m_pHistory") or {}).get("value") or {})
                for fld in ("m_creationGUID", "m_detachGUID", "m_upgradeGUID",
                            "m_saveAsGUID", "m_previousUpgradeGUID"):
                    hv = hist.get(fld) or {}
                    hg = str(hv.get("m_guid", "")).lower()
                    if hg and hg != NIL_GUID and hg not in self.guid_to_unit:
                        self.aux_guids.setdefault(hg, (g, f"embHistory.{fld}"))

    def _appinfo(self, class_name: str) -> Optional[dict]:
        for x in self.adoc.appinfo_array():
            if isinstance(x, dict) and x.get("ptr_class") == class_name:
                return x.get("value")
        return None

    def wanted_guids(self) -> Dict[str, Tuple[str, str]]:
        """guid -> (owning unit guid, label)."""
        out: Dict[str, Tuple[str, str]] = {}
        for g in self.unit_guids:
            if self.guid_to_unit.get(g, -1) != 0:
                out[g] = (g, "contentGUID")
        out.update(self.aux_guids)
        return out


# ===========================================================================
# the sweep
# ===========================================================================

class Sweep:
    def __init__(self, ident: Identity):
        self.ident = ident
        # surface -> unit guid -> count
        self.cov: Dict[str, Dict[str, int]] = defaultdict(Counter)
        self.kinds: Dict[str, str] = {}
        self.examples: Dict[str, List[dict]] = defaultdict(list)
        self.ref_kinds: Dict[str, Counter] = defaultdict(Counter)

    def hit(self, surface: str, kind: str, unit_guid: str, ref_kind: str,
            example: dict) -> None:
        self.cov[surface][unit_guid] += 1
        self.kinds[surface] = kind
        self.ref_kinds[surface][ref_kind] += 1
        ex = self.examples[surface]
        if len(ex) < 5 and unit_guid not in {e.get("unit") for e in ex}:
            example = dict(example)
            example["unit"] = unit_guid
            ex.append(example)

    def as_json(self) -> Dict[str, Any]:
        surfaces = {}
        for s in sorted(self.cov):
            per_unit = self.cov[s]
            surfaces[s] = {
                "kind": self.kinds[s],
                "ref_kinds": dict(self.ref_kinds[s]),
                "occurrences": int(sum(per_unit.values())),
                "unit_count": len(per_unit),
                "units_covered": sorted(per_unit),
                "examples": self.examples[s],
            }
        return surfaces


def _needle_forms(g: str) -> Dict[str, bytes]:
    lo, up = g.lower(), g.upper()
    return {
        "bytes_le": uuid.UUID(g).bytes_le,
        "ascii": lo.encode("ascii"),
        "ascii_upper": up.encode("ascii"),
        "utf16": lo.encode("utf-16-le"),
        "utf16_upper": up.encode("utf-16-le"),
    }


def _find_all(data: bytes, needle: bytes) -> List[int]:
    out, i = [], data.find(needle)
    while i != -1:
        out.append(i)
        i = data.find(needle, i + 1)
    return out


def sweep_file(path: str, *, native: Optional[Identity] = None,
               ident: Optional[Identity] = None,
               out_path: Optional[str] = None) -> Dict[str, Any]:
    """The exhaustive identity sweep of one file.  ``native`` (when given)
    marks which unit GUIDs are the native ones -- units NOT in that set are
    the newly loaded unit(s)."""
    from rvt.container import open_rvt
    from rvt.regdiff import TypedIdWalker
    from rvt import adocument as A

    ident = ident or Identity(path)
    sw = Sweep(ident)
    wanted_guids = ident.wanted_guids()
    guid_needles = {g: _needle_forms(g) for g in wanted_guids}
    id_map = ident.id_map
    native_guids = set(native.unit_guids) if native else set(ident.unit_guids)
    new_units = [g for g in ident.unit_guids
                 if g not in native_guids and ident.guid_to_unit.get(g, -1) != 0]

    log(f"sweep: {relp(path)} ({len(ident.unit_guids)-1} famdoc units, "
        f"{len(wanted_guids)} identity GUIDs, {len(id_map)} identity ids, "
        f"new units: {new_units or 'none'})")

    with open_rvt(path) as f:
        stream_names = [s.name for s in f.streams()]
        payloads: Dict[str, bytes] = {}
        raws: Dict[str, bytes] = {}
        for name in stream_names:
            raws[name] = f.raw(name)
            if name.startswith("Partitions/"):
                continue
            try:
                payloads[name] = b"".join(f.inflate_all(name))
            except Exception:
                payloads[name] = b""

    # ---- 1. raw byte scans (every stream; partitions handled per unit) ----
    for name in stream_names:
        if name.startswith("Partitions/"):
            continue
        for data, tag in ((payloads.get(name) or b"", "payload"),
                          (raws[name], "raw")):
            if not data or (tag == "raw" and payloads.get(name)):
                # scan raw only when we could not inflate (avoid double count)
                if tag == "raw":
                    continue
            for g, forms in guid_needles.items():
                unit_g, label = wanted_guids[g]
                for form, needle in forms.items():
                    offs = _find_all(data, needle)
                    if offs:
                        sw.hit(f"{name}:RAW:{form}", "guid-raw", unit_g, label,
                               {"guid": g, "offsets": offs[:4],
                                "n": len(offs), "space": tag})

    # ---- 2. Global/Latest typed sweep ----
    aw = TypedIdWalker(A.get_decoder())
    for p, g in guid_leaves(ident.adoc.value, "ADocument"):
        if g in wanted_guids:
            unit_g, label = wanted_guids[g]
            sw.hit(f"Latest:{surface_sig(p)}", "guid-typed", unit_g, label,
                   {"path": p, "guid": g})
    for lf in aw.leaves(ident.adoc.value, "ADocument"):
        tgt = id_map.get(int(lf.value)) if isinstance(lf.value, int) else None
        if tgt:
            unit_g, kind = tgt
            sw.hit(f"Latest:{surface_sig(lf.path)}", "elemid-typed", unit_g,
                   kind, {"path": lf.path, "id": lf.value})

    # ---- 3. ContentDocuments: entries + embedded ADocument sweeps ----
    from rvt.famgen.factory import parse_content_documents
    cd_payload = payloads.get("Global/ContentDocuments") or b""
    entries, _tail = parse_content_documents(cd_payload)
    for order, (g, blob) in enumerate(entries):
        gl = g.lower()
        sw.hit("ContentDocuments:entry", "guid-typed", gl, "contentGUID",
               {"order": order, "adoc_bytes": len(blob)})
    for gl, val in ident.embedded_adocs.items():
        for p, g in guid_leaves(val, "adoc"):
            if g in wanted_guids:
                unit_g, label = wanted_guids[g]
                rel = "self" if unit_g == gl else "cross"
                sw.hit(f"ContentDocuments:adoc[{rel}]:{surface_sig(p)}",
                       "guid-typed", unit_g, label,
                       {"path": p, "guid": g, "entry": gl})
        for lf in aw.leaves(val, "ADocument"):
            tgt = id_map.get(int(lf.value)) if isinstance(lf.value, int) else None
            if tgt:
                unit_g, kind = tgt
                rel = "self" if unit_g == gl else "cross"
                sw.hit(f"ContentDocuments:adoc[{rel}]:{surface_sig(lf.path)}",
                       "elemid-typed", unit_g, kind,
                       {"path": lf.path, "id": lf.value, "entry": gl})

    # ---- 4. decoded side-stream models (guid walk over each model) ----
    for name, model in _side_models(path, payloads, raws).items():
        for p, g in guid_leaves(model, name.split("/")[-1]):
            if g in wanted_guids:
                unit_g, label = wanted_guids[g]
                sw.hit(f"{name}:{surface_sig(p)}", "guid-typed", unit_g, label,
                       {"path": p, "guid": g})

    # ---- 5. ElemTable rows of identity ids ----
    for eid, (unit_g, kind) in id_map.items():
        if kind == "famdoc":
            continue                       # famdoc ids live in units, not here
        if eid in ident.et_rows:
            sw.hit("ElemTable:row", "elemid-typed", unit_g, kind,
                   {"id": eid, "row": list(ident.et_rows[eid])})

    # ---- 6. partition stream: per-unit segments ----
    _sweep_partitions(sw, ident, guid_needles, wanted_guids, id_map)

    surfaces = sw.as_json()
    result = {
        "file": relp(path),
        "md5": md5(path),
        "streams": stream_names,
        "units": [{"unit": u.index, "guid": (u.guid or "").lower() or None,
                   "counter": u.counter, "n_blocks": u.n_blocks}
                  for u in ident.units],
        "new_units": new_units,
        "identity_guids": {g: {"unit": wanted_guids[g][0],
                               "label": wanted_guids[g][1]}
                           for g in sorted(wanted_guids)},
        "identity_id_kinds": dict(Counter(k for _g, k in id_map.values())),
        "surfaces": surfaces,
        "coverage_notes": COVERAGE_NOTES,
    }
    if out_path:
        write_json(out_path, result)
    return result


COVERAGE_NOTES = {
    "raw_scan": "every non-Partitions stream scanned as inflated payload "
                "(or raw bytes when not deflate-framed) for 5 byte-forms of "
                "every identity GUID (bytes_le / ascii / utf-16, both cases)",
    "typed_guid": "generic tree walk over decoded values: Global/Latest "
                  "ADocument, every ContentDocuments embedded ADocument, "
                  "History / DocumentIncrementTable / PartitionTable / "
                  "Contents / BasicFileInfo / TransmissionData models",
    "typed_elemid": "schema-typed ElementId leaves only (rvt.regdiff."
                    "TypedIdWalker): Global/Latest, embedded ADocuments, "
                    "and EVERY unit-0 record in seqs 101+102",
    "partitions": "per-unit inflated segments raw-scanned for all GUID "
                  "forms (all seqs incl. 103); unit-0 seq 101+102 records "
                  "fully decoded + typed-walked; famdoc-unit record hits "
                  "attributed by decoding the containing record",
    "limits": "seq-103 GElement bodies are raw-scanned (GUID forms) but not "
              "typed-walked (geometry reps carry tags, not ElementIds); "
              "int-valued unit INDEX references are only observable through "
              "typed fields (no raw int scan -- unbounded noise); "
              "Formats/Latest (schema) raw-scanned only",
}


def _side_models(path: str, payloads: Dict[str, bytes],
                 raws: Dict[str, bytes]) -> Dict[str, Any]:
    from rvt import stream_encoders as se
    models: Dict[str, Any] = {}
    try:
        models["History"] = se.decode_history(payloads["Global/History"])
    except Exception as ex:
        models["History"] = {"decode_error": repr(ex)}
    try:
        models["DocumentIncrementTable"] = se.decode_increment_table(
            payloads["Global/DocumentIncrementTable"])
    except Exception as ex:
        models["DocumentIncrementTable"] = {"decode_error": repr(ex)}
    try:
        models["PartitionTable"] = se.decode_partition_table(
            payloads["Global/PartitionTable"])
    except Exception as ex:
        models["PartitionTable"] = {"decode_error": repr(ex)}
    try:
        models["Contents"] = se.decode_contents(payloads["Contents"])
    except Exception as ex:
        models["Contents"] = {"decode_error": repr(ex)}
    try:
        models["BasicFileInfo"] = se.decode_basic_file_info(raws["BasicFileInfo"])
    except Exception as ex:
        models["BasicFileInfo"] = {"decode_error": repr(ex)}
    return models


def _sweep_partitions(sw: Sweep, ident: Identity,
                      guid_needles: Dict[str, Dict[str, bytes]],
                      wanted_guids: Dict[str, Tuple[str, str]],
                      id_map: Dict[int, Tuple[str, str]]) -> None:
    from rvt.families import unit_segments
    from rvt.objects import iter_records
    from rvt.regdiff import TypedIdWalker
    idx = ident.idx
    walker = TypedIdWalker(idx.dec)

    for u in ident.units:
        if u.guid:                              # the unit separator itself
            sw.hit("Partitions:unit-separator", "guid-typed",
                   u.guid.lower(), "contentGUID",
                   {"unit": u.index, "counter": u.counter,
                    "n_blocks": u.n_blocks})
        segs = unit_segments(idx, u.index)
        owner_g = (u.guid or "").lower()
        for seq, seg in segs.items():
            if not seg:
                continue
            # raw GUID scan of the whole unit segment
            hit_offsets: Dict[str, List[Tuple[str, int]]] = defaultdict(list)
            for g, forms in guid_needles.items():
                for form, needle in forms.items():
                    for off in _find_all(seg, needle):
                        hit_offsets[g].append((form, off))
            if not hit_offsets and u.index != 0:
                continue
            # record framing for attribution
            hlen = 12 if seq == 101 else 16
            recs = [r for r in iter_records(seg, seq) if r.elem_id >= 0]
            rec_at = [(r.seg_offset, r.seg_offset + hlen + r.body_size + 4, r)
                      for r in recs]

            def _owning(off: int):
                for start, end, r in rec_at:
                    if start <= off < end:
                        return r
                return None

            for g, offs in hit_offsets.items():
                unit_g, label = wanted_guids[g]
                rel = "self" if unit_g == owner_g else "cross"
                for form, off in offs:
                    r = _owning(off)
                    if r is None:
                        sw.hit(f"Partitions:unit[{rel}]:seq{seq}:framing",
                               "guid-raw", unit_g, label,
                               {"guid": g, "form": form, "offset": off,
                                "in_unit": u.index})
                        continue
                    cls = idx.dec.class_name(r.class_id) if r.body_size >= 2 else "?"
                    concrete = None
                    if form in ("ascii", "ascii_upper", "utf16", "utf16_upper",
                                "bytes_le") and r.body_size >= 2 and seq == 102:
                        try:
                            v = idx.dec.decode_record(r.class_id, r.payload)
                            val = v.value if hasattr(v, "value") else v
                            for pth, gg in guid_leaves(val, cls):
                                if gg == g:
                                    concrete = pth
                                    break
                        except Exception:
                            concrete = None
                    sig = (f"Partitions:unit[{rel}]:seq{seq}:{surface_sig(concrete)}"
                           if concrete else
                           f"Partitions:unit[{rel}]:seq{seq}:{cls}:RAW")
                    sw.hit(sig, "guid-typed" if concrete else "guid-raw",
                           unit_g, label,
                           {"guid": g, "record": int(r.elem_id), "class": cls,
                            "in_unit": u.index, "form": form})

        # unit-0 typed ElementId sweep over seqs 101 + 102
        if u.index == 0:
            for seq in (101, 102):
                seg = segs.get(seq) or b""
                for r in iter_records(seg, seq):
                    if r.elem_id < 0 or r.body_size < 2:
                        continue
                    cls = idx.dec.class_name(r.class_id)
                    try:
                        v = idx.dec.decode_record(r.class_id, r.payload)
                    except Exception:
                        continue
                    val = v.value if hasattr(v, "value") else v
                    if not isinstance(val, dict):
                        continue
                    for lf in walker.leaves(val, cls):
                        tgt = id_map.get(int(lf.value)) if isinstance(lf.value, int) else None
                        if tgt is None:
                            continue
                        unit_g, kind = tgt
                        referrer = id_map.get(int(r.elem_id))
                        rel = ("self" if referrer and referrer[0] == unit_g
                               else "other")
                        sig = (f"Partitions:unit0:seq{seq}:{cls}[{rel}]"
                               f".{surface_sig(lf.path.split('.', 1)[1] if '.' in lf.path else lf.path)}")
                        sw.hit(sig, "elemid-typed", unit_g, kind,
                               {"referrer": int(r.elem_id), "class": cls,
                                "path": lf.path, "id": lf.value})


# ===========================================================================
# the CategoryTracking / slot-delta forensics (the decisive candidate)
# ===========================================================================

def _class_ids(path: str, classes: Sequence[str]) -> Dict[str, Dict[int, dict]]:
    """{class: {unit-0 element id: decoded value}} for the given classes."""
    from rvt.regdiff import RegDoc
    d = RegDoc(path)
    out: Dict[str, Dict[int, dict]] = {c: {} for c in classes}
    for r in d.host_records(102):
        if r.body_size < 2:
            continue
        cn = d.dec.class_name(r.class_id)
        if cn in out:
            v = d.dec.decode_record(r.class_id, r.payload)
            out[cn][int(r.elem_id)] = v.value if hasattr(v, "value") else v
    return out


def category_tracking_forensics(paths: Dict[str, str]) -> Dict[str, Any]:
    """The CategoryTracking index law, measured on every given file:
    m_categoryData is a COMPLETE 1:1 index of every unit-0 CategoryElem
    (row = {parentCategoryId from the elem's Category, categoryId = elem id},
    sorted by (parent, id)); m_gstyleData the same for GStyleElem
    (row = {m_categoryId / m_gstyleType from the elem, gstyleId = elem id},
    sorted by (categoryId, gstyleId))."""
    from rvt.container import open_rvt
    from rvt import adocument as A
    rep: Dict[str, Any] = {"law": category_tracking_forensics.__doc__}
    for name, path in paths.items():
        with open_rvt(path) as f:
            a = A.decode_latest(f.inflate("Global/Latest"))
        ct = next((x["value"] for x in a.appinfo_array()
                   if isinstance(x, dict) and x.get("ptr_class") == "CategoryTracking"),
                  None)
        if ct is None:
            rep[name] = {"error": "no CategoryTracking slot"}
            continue
        elems = _class_ids(path, ("CategoryElem", "GStyleElem"))
        cat, gs = elems["CategoryElem"], elems["GStyleElem"]
        cd = ct.get("m_categoryData") or []
        gd = ct.get("m_gstyleData") or []
        cd_ids = {r["m_categoryId"] for r in cd}
        gd_ids = {r["m_gstyleId"] for r in gd}
        deriv_cd = sum(
            1 for r in cd
            if r["m_categoryId"] in cat
            and ((cat[r["m_categoryId"]].get("m_pCategory") or {}).get("value") or {})
                .get("m_parentCategoryId") != r["m_parentCategoryId"])
        deriv_gd = sum(
            1 for r in gd
            if r["m_gstyleId"] in gs
            and (gs[r["m_gstyleId"]].get("m_categoryId") != r["m_categoryId"]
                 or gs[r["m_gstyleId"]].get("m_gstyleType") != r["m_gstyleType"]))
        cd_pairs = [(r["m_parentCategoryId"], r["m_categoryId"]) for r in cd]
        gd_pairs = [(r["m_categoryId"], r["m_gstyleId"]) for r in gd]
        rep[name] = {
            "file": relp(path),
            "categoryelem_elements": len(cat), "categorydata_rows": len(cd),
            "gstyleelem_elements": len(gs), "gstyledata_rows": len(gd),
            "untracked_categoryelem": sorted(set(cat) - cd_ids),
            "untracked_gstyleelem": sorted(set(gs) - gd_ids),
            "rows_without_element": sorted(cd_ids - set(cat))[:8],
            "derivation_mismatches_categorydata": deriv_cd,
            "derivation_mismatches_gstyledata": deriv_gd,
            "categorydata_sorted_by_parent_then_id": cd_pairs == sorted(cd_pairs),
            "gstyledata_sorted_by_category_then_gstyle": gd_pairs == sorted(gd_pairs),
        }
    return rep


def slot_delta(native_path: str, loaded_path: str) -> Dict[str, Any]:
    """Which of the 241 project-ADocument appinfo slots (and which non-slot
    top fields) changed between the native file and a loaded probe -- the
    loader's COMPLETE project-ADocument touch surface."""
    from rvt.container import open_rvt
    from rvt import adocument as A
    trees = []
    for p in (native_path, loaded_path):
        with open_rvt(p) as f:
            trees.append(A.decode_latest(f.inflate("Global/Latest")))
    a, b = trees

    def sig(x):
        return hashlib.md5(json.dumps(x, sort_keys=True,
                                      default=_json_default).encode()).hexdigest()
    slots_changed = []
    for i, (xa, xb) in enumerate(zip(a.appinfo_array(), b.appinfo_array())):
        if sig(xa) != sig(xb):
            cls = (xa or xb or {}).get("ptr_class") if isinstance(xa or xb, dict) else None
            slots_changed.append({"slot": i, "class": cls})
    top_changed = [k for k in sorted(set(a.value) | set(b.value))
                   if k != "m_pAppInfoManager"
                   and sig(a.value.get(k)) != sig(b.value.get(k))]
    return {"native": relp(native_path), "loaded": relp(loaded_path),
            "appinfo_slots_changed": slots_changed,
            "non_appinfo_top_fields_changed": top_changed}


# ===========================================================================
# crosscheck: native coverage vs new-unit presence
# ===========================================================================

KNOWN_FOUR = (
    "ContentDocuments:entry",
    "Latest:ADocument.m_oContentTable->ContentTable.m_ContentRecSet[].m_ContentKey.m_guidKey",
    "Latest:ADocument.m_pAppInfoManager->AppInfoManager.m_appInfoArr[]->FamilyMgr.m_arrLoadedFamilyInfo[].m_familyDocGUIDs[]",
    "Partitions:unit-separator",
)


def _reach_score(sig: str, ref_kinds: Dict[str, int]) -> Tuple[int, str]:
    """How plausibly does the instance walk visit this surface?
    3 = holds SYMBOL/FAMILY/INSTANCE element ids (element-reachable from
        FamilyInstance -> symbol -> Family);
    2 = keyed by content/famdoc GUID (reachable via Family.m_oFamDoc);
    1 = per-unit but reached only through unit machinery (framing, streams);
    0 = self-references inside the unit's own content."""
    if "unit[self]" in sig or "adoc[self]" in sig:
        return 0, "self-reference inside the unit's own content"
    kinds = set(ref_kinds)
    if kinds & {"symbol", "family", "surrogate", "cluster-owned"}:
        return 3, "holds host family-cluster element ids (walk-adjacent)"
    if kinds & {"contentGUID", "famDocGUID"}:
        return 2, "keyed by unit identity GUID (reachable via Family.m_oFamDoc)"
    if kinds & {"famdoc"}:
        return 1, "references in-unit famdoc element ids"
    return 1, "per-unit entry (embedded history GUID or framing)"


def crosscheck(out_path: str, sweep_dir: str) -> Dict[str, Any]:
    native_ident = Identity(RST)
    native_sw = sweep_file(RST, ident=native_ident,
                           out_path=os.path.join(sweep_dir, "sweep_rst.json"))
    files = [("H9", H9), ("H10", H10), ("H7", H7)]
    loaded: Dict[str, Dict[str, Any]] = {}
    for name, p in files:
        loaded[name] = sweep_file(
            p, native=native_ident,
            out_path=os.path.join(sweep_dir, f"sweep_{name}.json"))

    native_surfaces = native_sw["surfaces"]
    donor = DONOR_GUID
    rows = []
    for sig, info in sorted(native_surfaces.items()):
        per_file = {}
        for name, swp in loaded.items():
            new_gs = swp["new_units"]
            got = swp["surfaces"].get(sig)
            present = bool(got and any(g in got["units_covered"] for g in new_gs))
            per_file[name] = {
                "present_for_new_unit": present,
                "surface_exists": bool(got),
                "new_units": new_gs,
            }
        score, why = _reach_score(sig, info["ref_kinds"])
        rows.append({
            "surface": sig,
            "kind": info["kind"],
            "ref_kinds": info["ref_kinds"],
            "native_unit_count": info["unit_count"],
            "donor_unit_covered": donor in info["units_covered"],
            "occurrences_native": info["occurrences"],
            "known_four_registry": sig in KNOWN_FOUR or "FamilyMgr" in sig
                                   or "m_oContentTable" in sig
                                   or sig == "ContentDocuments:entry",
            "reach_score": score,
            "reach_note": why,
            "per_file": per_file,
            "examples_native": info["examples"][:2],
        })

    candidates = [r for r in rows
                  if not r["per_file"]["H9"]["present_for_new_unit"]]
    covered = [r for r in rows if r["per_file"]["H9"]["present_for_new_unit"]]
    candidates.sort(key=lambda r: (-r["reach_score"],
                                   -int(r["donor_unit_covered"]),
                                   -r["native_unit_count"]))
    # surfaces present ONLY in loaded files (we author, natives don't)
    only_ours = []
    for name, swp in loaded.items():
        for sig, info in swp["surfaces"].items():
            if sig not in native_surfaces and any(
                    g in info["units_covered"] for g in swp["new_units"]):
                only_ours.append({"file": name, "surface": sig,
                                  "kind": info["kind"],
                                  "examples": info["examples"][:2]})

    log("crosscheck: CategoryTracking forensics + slot deltas")
    ct_law = category_tracking_forensics({
        "rstbasic": RST, "racbasic": os.path.join(ROOT, "samples", "racbasicsampleproject.rvt"),
        "rmebasic": os.path.join(ROOT, "samples", "rmebasicsampleproject.rvt"),
        "H9": H9, "H10": H10, "H7": H7})
    deltas = {n: slot_delta(RST, p) for n, p in files}

    result = {
        "question": "which per-unit surfaces do native units populate that "
                    "our freshly registered unit (H9/H10/H7) does not?",
        "native": {"file": native_sw["file"], "md5": native_sw["md5"],
                   "units": len(native_sw["units"]) - 1,
                   "surfaces": len(native_surfaces)},
        "headline": {
            "finding": "CategoryTracking (project-ADocument appinfo slot) is "
                       "a COMPLETE 1:1 index of every unit-0 CategoryElem "
                       "(m_categoryData) and GStyleElem (m_gstyleData) "
                       "element -- 0 untracked in rst/rac/rme basic.  H9/H10 "
                       "carry the byte-copied family's 4 CategoryElem + 4 "
                       "GStyleElem twins UNTRACKED (the only index "
                       "violations in the file); famload's project-ADocument "
                       "touch surface is exactly FamilyMgr + "
                       "ElementTrackingData + m_oContentTable, so no load "
                       "path ever populates CategoryTracking.  H7 authors no "
                       "twins at all (index intact but the family lacks the "
                       "native per-family category constellation).  H10 "
                       "PASS proves the broken index is tolerated "
                       "UNINSTANCED; the instance walk is what resolves "
                       "category/style state.",
            "untracked_in_H9": {
                "categoryelem": ct_law.get("H9", {}).get("untracked_categoryelem"),
                "gstyleelem": ct_law.get("H9", {}).get("untracked_gstyleelem")},
            "row_recipe": {
                "m_categoryData": "one row per unit-0 CategoryElem: "
                    "{m_parentCategoryId: elem.m_pCategory->Category."
                    "m_parentCategoryId, m_categoryId: elem id}, sorted by "
                    "(m_parentCategoryId, m_categoryId) ascending",
                "m_gstyleData": "one row per unit-0 GStyleElem: "
                    "{m_categoryId: elem.m_categoryId, m_gstyleId: elem id, "
                    "m_gstyleType: elem.m_gstyleType}, sorted by "
                    "(m_categoryId, m_gstyleId) ascending"},
        },
        "category_tracking_law": ct_law,
        "loader_project_adocument_touch_surface": deltas,
        "loaded_files": {n: {"file": s["file"], "md5": s["md5"],
                             "new_units": s["new_units"]}
                         for n, s in loaded.items()},
        "donor_guid": donor,
        "ranking_criteria": _reach_score.__doc__,
        "candidates_missing_for_new_unit": candidates,
        "surfaces_covered_for_new_unit": covered,
        "surfaces_only_in_loaded": only_ours,
        "coverage_notes": COVERAGE_NOTES,
    }
    write_json(out_path, result)
    return result


# ===========================================================================
# rowdiff: registration-row forensics (native donor rows vs famload's rows)
# ===========================================================================

def _tree_diff(a: Any, b: Any, path: str, out: List[dict],
               norm=lambda x: x, max_out: int = 100000) -> None:
    """Recursive diff a (native) vs b (ours); values normalized via norm."""
    if len(out) >= max_out:
        return
    na, nb = norm(a), norm(b)
    if isinstance(na, dict) and isinstance(nb, dict):
        if "ptr_class" in na and "ptr_class" in nb:
            if na.get("ptr_class") != nb.get("ptr_class"):
                out.append({"path": path, "native": na.get("ptr_class"),
                            "ours": nb.get("ptr_class"), "what": "ptr_class"})
                return
            _tree_diff(na.get("value"), nb.get("value"),
                       f"{path}->{na['ptr_class']}", out, norm, max_out)
            return
        for k in sorted(set(na) | set(nb)):
            pa, pb = na.get(k, "<absent>"), nb.get(k, "<absent>")
            if isinstance(pa, str) and pa == "<absent>":
                out.append({"path": f"{path}.{k}", "native": "<absent>",
                            "ours": _clip(pb), "what": "only-ours"})
            elif isinstance(pb, str) and pb == "<absent>":
                out.append({"path": f"{path}.{k}", "native": _clip(pa),
                            "ours": "<absent>", "what": "only-native"})
            else:
                _tree_diff(pa, pb, f"{path}.{k}", out, norm, max_out)
        return
    if isinstance(na, (list, tuple)) and isinstance(nb, (list, tuple)):
        if len(na) != len(nb):
            out.append({"path": path, "what": "length",
                        "native": len(na), "ours": len(nb)})
        for i in range(min(len(na), len(nb))):
            _tree_diff(na[i], nb[i], f"{path}[{i}]", out, norm, max_out)
        return
    if na != nb:
        out.append({"path": path, "native": _clip(na), "ours": _clip(nb),
                    "what": "value"})


def _clip(v: Any, n: int = 120) -> Any:
    if isinstance(v, (bytes, bytearray)):
        v = v.hex()
    if isinstance(v, str) and len(v) > n:
        return v[:n] + f"...({len(v)} chars)"
    if isinstance(v, (dict, list, tuple)):
        s = json.dumps(v, default=_json_default)
        return s[:n] + f"...({len(s)} chars)" if len(s) > n else json.loads(s)
    return v


def _group_diffs(diffs: List[dict]) -> List[dict]:
    groups: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
    for d in diffs:
        groups[(surface_sig(d["path"]), d.get("what", "value"))].append(d)
    out = []
    for (sig, what), items in sorted(groups.items(),
                                     key=lambda kv: -len(kv[1])):
        out.append({"path_sig": sig, "what": what, "count": len(items),
                    "examples": items[:3]})
    return out


def _unit_shape(ident: Identity, unit: int) -> Dict[str, Any]:
    from rvt.families import unit_segments
    from rvt.objects import iter_records
    u = ident.units[unit]
    segs = unit_segments(ident.idx, unit)
    shape: Dict[str, Any] = {
        "unit": unit, "guid": (u.guid or "").lower(), "counter": u.counter,
        "n_blocks": u.n_blocks, "seqs": {},
    }
    for seq, seg in sorted(segs.items()):
        recs = list(iter_records(seg, seq))
        host = [r for r in recs if r.elem_id >= 0]
        sent = [r for r in recs if r.elem_id < 0]
        stamps = Counter(r.stamp for r in host) if seq != 101 else Counter()
        shape["seqs"][str(seq)] = {
            "records": len(host),
            "sentinels": len(sent),
            "sentinel_stamps": sorted({r.stamp for r in sent}) if seq != 101 else None,
            "stamp_histogram": {str(k): v for k, v in sorted(stamps.items())},
            "bytes": len(seg),
            "id_ascending": all(host[i].elem_id <= host[i+1].elem_id
                                for i in range(len(host)-1)),
            "id_range": [int(host[0].elem_id), int(host[-1].elem_id)] if host else None,
        }
    return shape


def _content_row(adoc_value: dict, guid: str) -> Optional[dict]:
    ct = (adoc_value.get("m_oContentTable") or {}).get("value") or {}
    for r in ct.get("m_ContentRecSet") or []:
        g = str((r.get("m_ContentKey") or {}).get("m_guidKey") or "").lower()
        if g == guid.lower():
            return r
    return None


def _fm_entry(ident: Identity, guid: str) -> Optional[dict]:
    fm = ident._appinfo("FamilyMgr") or {}
    for e in fm.get("m_arrLoadedFamilyInfo") or []:
        if any(str(g).lower() == guid.lower()
               for g in e.get("m_familyDocGUIDs") or []):
            return e
    return None


def _episode_law(ident: Identity) -> Dict[str, Any]:
    """THE m_EpisodeCounts LAW (measured, 52/52 on the native rst sample):
    a unit's seq-102 records are stored in id-ascending RUNS, one run per
    save episode, NEWEST episode first; the ContentTable row's
    m_EpisodeCounts lists (episode, run size) in ASCENDING episode order --
    i.e. the run-size sequence reversed.  (Falsified alternative, recorded:
    the u32 record 'stamp' field is NOT an episode -- native stamps are
    unique checksum-like values, 0/52 units match; the embedded ElemTable's
    m_lastModificationDate histogram matches only 3/52.)"""
    from rvt.families import unit_segments
    from rvt.objects import iter_records
    out: Dict[str, Any] = {"per_unit": {}, "law": _episode_law.__doc__}
    ok = 0
    total = 0
    for u in ident.units:
        if u.index == 0 or not u.guid:
            continue
        g = u.guid.lower()
        row = _content_row(ident.adoc.value, g)
        if row is None:
            out["per_unit"][g] = {"unit": u.index, "error": "no ContentTable row"}
            continue
        declared = [(int(p["first"]["m_id"]), int(p["second"]))
                    for p in row.get("m_EpisodeCounts") or []]
        seg = unit_segments(ident.idx, u.index).get(102) or b""
        ids = [int(r.elem_id) for r in iter_records(seg, 102) if r.elem_id >= 0]
        runs: List[int] = []
        cur = 0
        for i in range(1, len(ids) + 1):
            if i == len(ids) or ids[i] <= ids[i - 1]:
                runs.append(i - cur)
                cur = i
        match = runs == [c for _e, c in reversed(declared)]
        total += 1
        ok += int(match)
        out["per_unit"][g] = {
            "unit": u.index, "declared_episode_counts": declared,
            "seq102_run_structure_newest_first": runs,
            "records": len(ids), "match": match,
        }
    out["law_holds"] = (f"{ok}/{total} units: m_EpisodeCounts == the unit's "
                        "seq-102 id-ascending run structure (newest first)")
    out["ok"] = ok
    out["total"] = total
    return out


def rowdiff(out_path: str) -> Dict[str, Any]:
    from rvt.families import content_document_adoc
    from rvt import adocument as A

    log("rowdiff: native donor rows (rst unit 36) vs famload rows (H9, H7)")
    nat = Identity(RST)
    h9 = Identity(H9)
    h7 = Identity(H7)

    donor = DONOR_GUID
    new9 = [g for g in h9.unit_guids
            if g not in set(nat.unit_guids) and h9.guid_to_unit.get(g, -1) != 0]
    new7 = [g for g in h7.unit_guids
            if g not in set(nat.unit_guids) and h7.guid_to_unit.get(g, -1) != 0]
    if len(new9) != 1 or len(new7) != 1:
        raise RuntimeError(f"expected exactly one new unit: H9={new9} H7={new7}")
    g9, g7 = new9[0], new7[0]
    u_nat = nat.guid_to_unit[donor]
    u_9 = h9.guid_to_unit[g9]
    u_7 = h7.guid_to_unit[g7]
    log(f"  donor unit {u_nat} ({donor}); H9 unit {u_9} ({g9}); "
        f"H7 unit {u_7} ({g7})")

    # ---- normalization: remap + declared moves --------------------------
    idmap9: Dict[int, int] = {}
    nat_ids = nat.famdoc_ids[u_nat]
    h9_ids = h9.famdoc_ids[u_9]
    if len(nat_ids) == len(h9_ids):
        idmap9.update(dict(zip(sorted(nat_ids), sorted(h9_ids))))
    cr_path = os.path.join(ROOT, "experiments", "hostpair", "copy_report.json")
    host_map: Dict[int, int] = {}
    if os.path.exists(cr_path):
        cr = json.load(open(cr_path))
        for e in cr.get("ledger", {}).get("elements", []):
            host_map[int(e["native_id"])] = int(e["new_id"])
    idmap9.update(host_map)
    guid_eq = {donor: g9}
    fam_nat = next((r for r in nat.fams if r["unit"] == u_nat), {})
    fam_9 = next((r for r in h9.fams if r["unit"] == u_9), {})
    if fam_nat.get("fam_doc_guid") and fam_9.get("fam_doc_guid"):
        guid_eq[str(fam_nat["fam_doc_guid"]).lower()] = str(fam_9["fam_doc_guid"]).lower()
    name_eq = {str(fam_nat.get("family_name")): str(fam_9.get("family_name"))}

    def norm9(v: Any) -> Any:
        if isinstance(v, int) and not isinstance(v, bool) and v in idmap9:
            return idmap9[v]
        if isinstance(v, str):
            lv = v.lower()
            if lv in guid_eq:
                return guid_eq[lv]
            if v in name_eq:
                return name_eq[v]
        return v

    result: Dict[str, Any] = {
        "question": "field-by-field: the donor famdoc's NATIVE registration "
                    "rows (rst sample, unit 36) vs the rows famload authored "
                    "for the SAME famdoc in H9 (byte-copied host pair) and "
                    "H7 (famload-authored host pair)",
        "normalization": {
            "id_remap_pairs": len(idmap9),
            "guid_equivalences": guid_eq,
            "name_equivalences": name_eq,
            "note": "native ids/GUIDs/names mapped to their H9 equivalents "
                    "before diffing -- remaining diffs are CONTENT, not remap",
        },
        "files": {"native": {"file": relp(RST), "md5": md5(RST)},
                  "H9": {"file": relp(H9), "md5": md5(H9)},
                  "H7": {"file": relp(H7), "md5": md5(H7)}},
    }

    # ---- 1. ContentTable row -------------------------------------------
    row_nat = _content_row(nat.adoc.value, donor)
    row_9 = _content_row(h9.adoc.value, g9)
    row_7 = _content_row(h7.adoc.value, g7)
    d_ct: List[dict] = []
    _tree_diff(row_nat, row_9, "ContentRec", d_ct, norm9)

    def _mask(v: Any) -> Any:
        if isinstance(v, dict):
            return {k: _mask(x) for k, x in v.items()}
        if isinstance(v, list):
            return [_mask(x) for x in v]
        if isinstance(v, int) and not isinstance(v, bool):
            return "<int>"
        if isinstance(v, str) and GUID_RE.match(v):
            return "<guid>"
        return v
    result["content_table_row"] = {
        "native": row_nat, "ours_H9": row_9, "ours_H7": row_7,
        "diffs_native_vs_H9": d_ct,
        "famload_row_shape_stable_across_H9_H7": _mask(row_9) == _mask(row_7),
    }

    # ---- 2. FamilyMgr entry --------------------------------------------
    e_nat = _fm_entry(nat, donor)
    e_9 = _fm_entry(h9, g9)
    e_7 = _fm_entry(h7, g7)
    d_fm: List[dict] = []
    _tree_diff(e_nat, e_9, "LoadedFamilyInfo", d_fm, norm9)
    fm_nat_all = (nat._appinfo("FamilyMgr") or {}).get("m_arrLoadedFamilyInfo") or []
    guid_hist = dict(Counter(len(e.get("m_familyDocGUIDs") or [])
                             for e in fm_nat_all))
    multi = [e for e in fm_nat_all if len(e.get("m_familyDocGUIDs") or []) > 1]
    result["familymgr_entry"] = {
        "native": e_nat, "ours_H9": e_9, "ours_H7": e_7,
        "diffs_native_vs_H9": d_fm,
        "native_guid_count_histogram": guid_hist,
        "native_entries_with_multiple_guids": multi,
        "note": "native FamilyMgr: 50 entries / 52 GUIDs -- 9 zero-GUID "
                "entries (system-family surrogates), 34 one-GUID, and 7 "
                "multi-GUID entries (a parent family's entry lists its "
                "NESTED famdoc units' GUIDs too: 4x2 + 2x3 + 1x4 = the 11 "
                "units without their own host Family); famload's 1-GUID "
                "entry is the correct non-nested shape",
    }

    # ---- 3. ContentDocuments entry: framing + embedded ADocument -------
    from rvt.famgen.factory import parse_content_documents
    from rvt.container import open_rvt
    with open_rvt(RST) as f:
        cd_nat = parse_content_documents(b"".join(f.inflate_all("Global/ContentDocuments")))[0]
    with open_rvt(H9) as f:
        cd_9 = parse_content_documents(b"".join(f.inflate_all("Global/ContentDocuments")))[0]
    pos_nat = next(i for i, (g, _b) in enumerate(cd_nat) if g.lower() == donor)
    pos_9 = next(i for i, (g, _b) in enumerate(cd_9) if g.lower() == g9)
    blob_nat = cd_nat[pos_nat][1]
    blob_9 = cd_9[pos_9][1]
    ad_nat = A.decode_latest(blob_nat).value
    ad_9 = A.decode_latest(blob_9).value
    d_adoc: List[dict] = []
    _tree_diff(ad_nat, ad_9, "adoc", d_adoc, norm9)
    slots_nat = _emb_slots(ad_nat)
    slots_9 = _emb_slots(ad_9)
    result["contentdocuments_entry"] = {
        "framing": {"native": {"order_index": pos_nat, "adoc_bytes": len(blob_nat)},
                    "ours_H9": {"order_index": pos_9, "adoc_bytes": len(blob_9)}},
        "embedded_appinfo_slots": {
            "native_populated": len([s for s in slots_nat if s]),
            "ours_populated": len([s for s in slots_9 if s]),
            "native_classes": sorted({s for s in slots_nat if s}),
            "ours_classes": sorted({s for s in slots_9 if s}),
            "slots_total": len(slots_nat),
        },
        "diffs_grouped": _group_diffs(d_adoc),
        "diff_leaf_count": len(d_adoc),
    }

    # ---- 4. unit stream shape ------------------------------------------
    sh_nat = _unit_shape(nat, u_nat)
    sh_9 = _unit_shape(h9, u_9)
    sh_7 = _unit_shape(h7, u_7)
    result["unit_shape"] = {"native": sh_nat, "ours_H9": sh_9, "ours_H7": sh_7}

    # ---- 5. host ElemTable rows of the cluster -------------------------
    et_rows = []
    for nat_id, new_id in sorted(host_map.items()):
        rn = nat.et_rows.get(nat_id)
        r9 = h9.et_rows.get(new_id)
        et_rows.append({
            "native_id": nat_id, "new_id": new_id,
            "native_row": list(rn) if rn else None,
            "ours_row": list(r9) if r9 else None,
            "fields": ["original_id", "creation_ep", "modified_ep",
                       "user_modified_ep", "id", "owner_id", "partition_id"],
        })
    inst_ids = [i for i in h9.et_rows if i not in nat.et_rows
                and i not in set(host_map.values())
                and i not in set(h9.famdoc_ids.get(u_9, []))]
    result["elemtable_rows"] = {
        "cluster": et_rows,
        "extra_new_rows": [{"id": i, "row": list(h9.et_rows[i])}
                           for i in sorted(inst_ids)],
    }

    # ---- 6. project-side History / DIT deltas --------------------------
    from rvt import stream_encoders as se
    with open_rvt(RST) as f:
        hist_nat = se.decode_history(f.inflate("Global/History"))
        dit_nat = se.decode_increment_table(f.inflate("Global/DocumentIncrementTable"))
    with open_rvt(H9) as f:
        hist_9 = se.decode_history(f.inflate("Global/History"))
        dit_9 = se.decode_increment_table(f.inflate("Global/DocumentIncrementTable"))
    d_hist: List[dict] = []
    _tree_diff(hist_nat, hist_9, "History", d_hist, norm9)
    d_dit: List[dict] = []
    _tree_diff(dit_nat, dit_9, "DIT", d_dit, norm9)
    ct_9 = row_9 or {}
    our_eps = [int(p["first"]["m_id"]) for p in ct_9.get("m_EpisodeCounts") or []]
    result["project_history"] = {
        "history_entries_native": len(hist_nat.get("entries") or []),
        "history_entries_H9": len(hist_9.get("entries") or []),
        "history_diffs": _group_diffs(d_hist),
        "increment_records_native": len(dit_nat.get("records") or []),
        "increment_records_H9": len(dit_9.get("records") or []),
        "increment_diffs": _group_diffs(d_dit),
        "our_row_references_episodes": our_eps,
        "native_row_references_episodes": [
            int(p["first"]["m_id"]) for p in (row_nat or {}).get("m_EpisodeCounts") or []],
        "note": "commit_new_elements reuses an EXISTING episode; History/DIT "
                "are deliberately untouched by the load",
    }

    # ---- 7. the episode-count law across all units ---------------------
    law_nat = _episode_law(nat)
    law_9 = _episode_law(h9)
    result["episode_count_law"] = {
        "native": {"law_holds": law_nat["law_holds"],
                   "donor_unit": law_nat["per_unit"].get(donor)},
        "H9": {"law_holds": law_9["law_holds"],
               "our_unit": law_9["per_unit"].get(g9),
               "mismatched_units": {g: v for g, v in law_9["per_unit"].items()
                                    if not v.get("match", True)}},
    }

    # ---- ranked findings ------------------------------------------------
    result["ranked_fields"] = _rank_rowdiff(result)
    write_json(out_path, result)
    return result


def _emb_slots(adoc_value: dict) -> List[Optional[str]]:
    mgr = (adoc_value.get("m_pAppInfoManager") or {}).get("value") or {}
    out = []
    for x in mgr.get("m_appInfoArr") or []:
        if x is None:
            out.append(None)
        elif isinstance(x, dict) and "ptr_class" in x:
            out.append(x["ptr_class"])
        else:
            out.append("?")
    return out


def _rank_rowdiff(res: Dict[str, Any]) -> List[dict]:
    """Rank the differing registration-row fields for the probe stream."""
    ranked: List[dict] = []

    def add(rank_hint: int, surface: str, field: str, native: Any, ours: Any,
            note: str) -> None:
        ranked.append({"surface": surface, "field": field,
                       "native": _clip(native), "ours": _clip(ours),
                       "note": note, "rank_hint": rank_hint})

    law9 = res["episode_count_law"]["H9"]
    our_unit_law = law9.get("our_unit") or {}
    if our_unit_law and not our_unit_law.get("match", True):
        add(1, "ContentTable.row <-> unit records",
            "m_EpisodeCounts vs seq-102 run structure",
            our_unit_law.get("declared_episode_counts"),
            our_unit_law.get("seq102_run_structure_newest_first"),
            "our declared episode counts DISAGREE with our unit's actual "
            "record-run structure -- native law holds "
            + res["episode_count_law"]["native"]["law_holds"])
    elif our_unit_law:
        add(2, "ContentTable.row <-> unit records",
            "m_EpisodeCounts run-structure law",
            (res["episode_count_law"]["native"].get("donor_unit") or {})
            .get("seq102_run_structure_newest_first"),
            our_unit_law.get("seq102_run_structure_newest_first"),
            "COHERENT on our unit too (single fused id-ascending run, "
            "declared as one episode) -- the native donor keeps its 2-run "
            "episode history; a value diff, not a broken invariant")
    for d in res["content_table_row"]["diffs_native_vs_H9"]:
        add(2, "ContentTable.row", d["path"], d.get("native"), d.get("ours"),
            d.get("what", "value"))
    fr = res["contentdocuments_entry"]
    add(3, "ContentDocuments.entry.adoc", "AppInfoManager populated slots",
        fr["embedded_appinfo_slots"]["native_populated"],
        fr["embedded_appinfo_slots"]["ours_populated"],
        "family-editor registries inside the embedded ADocument")
    for g in fr["diffs_grouped"][:40]:
        add(4, "ContentDocuments.entry.adoc", g["path_sig"],
            (g["examples"][0].get("native") if g["examples"] else None),
            (g["examples"][0].get("ours") if g["examples"] else None),
            f"{g['count']} leaf diffs ({g['what']})")
    sh_n, sh_9 = res["unit_shape"]["native"], res["unit_shape"]["ours_H9"]
    for seq in sorted(set(sh_n["seqs"]) | set(sh_9["seqs"])):
        a, b = sh_n["seqs"].get(seq), sh_9["seqs"].get(seq)
        if not a or not b:
            add(5, "Partitions.unit", f"seq{seq} present", bool(a), bool(b),
                "seq roster differs")
            continue
        for k in ("records", "stamp_histogram", "sentinel_stamps", "id_ascending"):
            if a.get(k) != b.get(k):
                add(5, "Partitions.unit", f"seq{seq}.{k}", a.get(k), b.get(k),
                    "unit stream shape")
    if sh_n.get("counter") != sh_9.get("counter"):
        add(5, "Partitions.unit", "separator.counter", sh_n.get("counter"),
            sh_9.get("counter"), "unit separator counter")
    if sh_n.get("n_blocks") != sh_9.get("n_blocks"):
        add(6, "Partitions.unit", "n_blocks", sh_n.get("n_blocks"),
            sh_9.get("n_blocks"), "block layout")
    for d in res["familymgr_entry"]["diffs_native_vs_H9"]:
        add(6, "FamilyMgr.entry", d["path"], d.get("native"), d.get("ours"),
            d.get("what", "value"))
    cl = res["elemtable_rows"]["cluster"]
    ep_fields = ("original_id", "creation_ep", "modified_ep",
                 "user_modified_ep", "id", "owner_id", "partition_id")
    diff_cols: Counter = Counter()
    for r in cl:
        rn, r9 = r["native_row"], r["ours_row"]
        if not rn or not r9:
            continue
        for i, f in enumerate(ep_fields):
            if f in ("id", "original_id"):
                continue
            if rn[i] != r9[i]:
                diff_cols[f] += 1
    for f, n in diff_cols.most_common():
        ex = next(r for r in cl if r["native_row"] and r["ours_row"]
                  and r["native_row"][ep_fields.index(f)] != r["ours_row"][ep_fields.index(f)])
        add(7, "ElemTable.cluster-rows", f,
            ex["native_row"][ep_fields.index(f)],
            ex["ours_row"][ep_fields.index(f)],
            f"{n}/22 cluster rows differ in {f}")
    ranked.sort(key=lambda r: r["rank_hint"])
    for i, r in enumerate(ranked, 1):
        r["rank"] = i
    return ranked


# ===========================================================================
# CLI
# ===========================================================================

def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("sweep", help="identity sweep of one file")
    sp.add_argument("file")
    sp.add_argument("--out", default=None)
    sp.add_argument("--native", default=None,
                    help="native file whose units define 'native' (for "
                         "loaded probes; default: the file itself)")
    sub.add_parser("crosscheck", help="native vs H9/H10/H7 -> fifth_surface.json")
    sub.add_parser("rowdiff", help="registration-row forensics -> row_diff.json")
    sub.add_parser("all", help="crosscheck + rowdiff")
    args = ap.parse_args(argv)

    os.makedirs(OUT_DIR, exist_ok=True)
    if args.cmd == "sweep":
        out = args.out or os.path.join(
            OUT_DIR, f"sweep_{os.path.splitext(os.path.basename(args.file))[0]}.json")
        native = Identity(args.native) if args.native else None
        sweep_file(args.file, native=native, out_path=out)
        return 0
    if args.cmd in ("crosscheck", "all"):
        crosscheck(os.path.join(OUT_DIR, "fifth_surface.json"), OUT_DIR)
    if args.cmd in ("rowdiff", "all"):
        rowdiff(os.path.join(OUT_DIR, "row_diff.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
