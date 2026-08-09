"""rvt.convert.rfa_load -- LOAD ROUTE: any standalone-born ``.rfa`` -> RVT.

Product wiring of the viewer-certified research lane T2a (issue #99):

* read      the family document (unit 0) of a STANDALONE ``.rfa`` -- ours
            (``start_id=1000`` deliverables) or any Revit-saved family whose
            ElemTable our codec parses -- under the file's OWN release
            (:func:`rvt.global_framing.reading`); owner ids come from the
            ``Global/ElemTable`` STREAM (the standalone ownership law: a
            standalone file's ``Global/Latest`` ADocument carries an EMPTY
            inline elem table, the owners are externalised);
* rebase    every element id into a free block ABOVE the host's id
            watermark by the SCHEMA-TYPED decode-time remap
            (:class:`RemapDecoder`): exactly the values the schema types as
            ``ElementId`` are substituted, nothing else.  The blind int-walk
            the component loader uses on project-embedded donors (ids at
            1.4M) is UNSOUND on the small-id standalone species (ids
            3..~2,500 alias flags / enum values / weakref indices);
* load      the rebased document through the certified four-registry
            loader :func:`rvt.famload.load_family_documents` (embedded save
            unit + ContentDocuments entry + ContentTable record + FamilyMgr
            entry + host Family / FamilySymbol(s) / surrogates / parameter
            twins), no instance placed; project validator afterwards.  The
            ENCODE side runs under the HOST's release (famload's own
            host_release_context), so a 2026-born family lands on a 2025 /
            2024 base through the port layer.

The mechanism is viewer-CERTIFIED (ledger: ``experiments/rftprobe/T2a.rvt``
-- a Revit-born 1,992-element ``.rfa`` famloaded onto the composed base with
a placed instance); THIS lane's own artifacts are not, until a batch of them
is staged and a human records the verdict (rule 4) -- :data:`SUMMARY`
says so and the router relays it.

HONEST LIMITS -- :data:`REFUSED_BY_NAME` (one clear line, never faked).

Zero donor bytes (rule 3): the reader decodes the USER's / OUR file and the
loader re-authors every record from the decoded values; nothing from the
research corpus enters this module.  ``RemapDecoder`` is a codec capability
whose natural home is ``rvt.objects`` once a second product caller exists.

Territory: ``src/rvt/convert/`` (issue #99); read-only ancestry:
``tools/rft_probe.py`` (``load_rft_elements`` / ``_remap_decoder`` /
``template_doc``) and ``tools/famdoc_bisect.py`` (``HybridFamilyDoc``).
"""
from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .add_to_project import ConvertError, _relp

__all__ = [
    "RfaLoadError", "RemapDecoder", "RfaSource", "BornRfaDoc",
    "rfa_id_floor", "host_watermark", "is_standalone_born",
    "load_rfa_into_project", "MECHANISM", "CERTIFIED_BY", "REFUSED_BY_NAME",
]

#: what the manifest / router name as the implementation
MECHANISM = ("schema-typed decode-time id remap + rvt.famload four-registry "
             "load (the T2a mechanism)")
#: the ledger entry that certifies the MECHANISM (not this lane's artifacts)
CERTIFIED_BY = "experiments/rftprobe/T2a.rvt"
#: the by-name refusals, ONE sentence the router relays verbatim
REFUSED_BY_NAME = ("Refused by name: a project (.rvt) passed as a family, a "
                   "GraveyardRec ElemTable footer (codec gap #13), nested family "
                   "documents, seq-103 classes beyond GElement/SerializedDummy, "
                   "records that do not decode against the file's own schema")

_REP_CLASSES_OK = ("GElement", "SerializedDummy")


class RfaLoadError(ConvertError):
    """The .rfa cannot be loaded by this lane; the message names the blocker."""


# ---------------------------------------------------------------------------
# the schema-typed remap decoder
# ---------------------------------------------------------------------------

def RemapDecoder(schema, idmap: Dict[int, int]):
    """An :class:`rvt.objects.ObjectDecoder` over ``schema`` that substitutes
    ``ElementId``-TYPED values through ``idmap`` DURING the byte decode, so
    the elements are born rebased.  ``.n_remapped`` counts substitutions."""
    from ..objects import ObjectDecoder

    class _Remap(ObjectDecoder):
        def __init__(self, s, m):
            super().__init__(s)
            self._idmap = m
            self.n_remapped = 0

        def _decode_value_class(self, rd, type_id, queue, state, path):
            v = super()._decode_value_class(rd, type_id, queue, state, path)
            if (type_id == self.id_ElementId and isinstance(v, int)
                    and not isinstance(v, bool) and v in self._idmap):
                self.n_remapped += 1
                return self._idmap[v]
            return v

    return _Remap(schema, dict(idmap))


# ---------------------------------------------------------------------------
# cheap classifiers (ElemTable reads only, no partition walk)
# ---------------------------------------------------------------------------

def _elemtable(path: str):
    from ..container import open_rvt
    from ..elemtable import inflate_global_stream, parse_elemtable
    with open_rvt(path) as f:
        raw = f.raw("Global/ElemTable")
    return parse_elemtable(inflate_global_stream(raw).payload, _relp(path))


def host_watermark(host_rvt: str) -> int:
    """The host's id watermark: max(ElemTable footer last_id, highest row
    id) -- THE allocation law of :func:`rvt.famload.survey_host` (which
    also opens the Document; this is its ElemTable-only reading)."""
    et = _elemtable(host_rvt)
    last = int(et.footer.last_id) if et.footer else 0
    return max([last] + [int(r.id) for r in et.records])


def rfa_id_floor(rfa_path: str) -> int:
    """The lowest positive element id the family file has issued."""
    ids = [int(r.id) for r in _elemtable(rfa_path).records if int(r.id) > 0]
    if not ids:
        raise RfaLoadError(f"{_relp(rfa_path)}: Global/ElemTable lists no elements")
    return min(ids)


def is_standalone_born(rfa_path: str, host_rvt: str) -> Tuple[bool, int, int]:
    """(born, rfa id floor, host watermark): ``born`` = the family's ids sit
    at/below the host watermark, so a verbatim splice would collide and the
    remap lane is the one that loads it."""
    floor, wm = rfa_id_floor(rfa_path), host_watermark(host_rvt)
    return floor <= wm, floor, wm


# ---------------------------------------------------------------------------
# the loadable document (famload's FamilyDoc protocol over decoded elements)
# ---------------------------------------------------------------------------

class BornRfaDoc:
    """The famload ``FamilyDoc`` protocol over the rebased elements of a
    standalone-born family: segments are RE-ENCODED from the elements by
    :func:`rvt.famgen.skeleton.build_unit_segments` (the loader's own
    roundtrip gate re-proves every host record; the unit records decode
    clean or the load's verify step says so).  ``types`` is the family's
    RAW type table (blank current-values pair included): the loader applies
    its own real-named-types law to it."""

    finalized = True

    def __init__(self, elements, self_family, *, name: str, category_id: int,
                 part_type: int, types: Sequence[Tuple[str, dict]],
                 current_type: int = 0, document_guid: Optional[str] = None):
        self.elements = list(elements)
        self.self_family = self_family
        self.name = str(name)
        self.category_id = int(category_id)
        self.part_type = int(part_type)
        self.types = list(types)
        self.current_type = int(current_type)
        # a standalone file's unit 0 carries no separator GUID and the same
        # .rfa may be loaded twice into one host: mint the content GUID
        self.document_guid = document_guid or str(uuid.uuid4())
        self.params: Dict[str, Any] = {}

    def finalize(self) -> "BornRfaDoc":
        return self

    def to_embedded_unit(self) -> Dict[str, Any]:
        from ..famgen import skeleton as SK
        return {"content_doc_guid": self.document_guid,
                "record_count": len(self.elements),
                "segments": SK.build_unit_segments(self.elements),
                "self_family_id": self.self_family.elem_id,
                "type_names": [n for n, _v in self.types]}


# ---------------------------------------------------------------------------
# the reader: phase 1 (facts + raw records, under the FILE's own release)
#             phase 2 (build(start_id): typed-remap decode into a block)
# ---------------------------------------------------------------------------

def _self_family(idx) -> Optional[dict]:
    """The unit-0 self-Family facts ({id, category, part_type, types}).  A
    standalone family with no nested families carries exactly ONE ``Family``
    element: decode just that row (a 2k-element Revit family would otherwise
    pay a full identity decode of every element only to count references);
    several ``Family`` rows -> the shared reference-count walk
    :func:`rvt.families.self_family_of_unit`."""
    from ..families import self_family_of_unit
    fam_ids = idx.ids_of_class(0, "Family")
    if len(fam_ids) != 1:
        return self_family_of_unit(idx, 0)
    v = idx.value(0, fam_ids[0]) or {}
    ftt = (v.get("m_pFamilyTypes") or {}).get("value") or {}
    return {"id": fam_ids[0], "category": v.get("m_categoryId"),
            "part_type": v.get("m_partType"),
            "types": [{"name": pr.get("name")} for pr in ftt.get("m_pairs") or []]}


@dataclass
class RfaFacts:
    """What phase 1 measured on the family file (reported in the record)."""
    n_elements: int
    self_family: int
    category: int
    part_type: int
    type_names: List[str]                 # the RAW type table, blank pair included
    current_type: int                     # index of the first real-named type
    name: str
    release: Optional[int]
    class_histogram: Dict[str, int] = dc_field(default_factory=dict)


class RfaSource:
    """A standalone ``.rfa`` read ONCE (records + owner law + self-Family
    facts, under the file's own release), then buildable any number of
    times at any ``start_id`` (:meth:`build`) -- the ``builder(start_id)``
    the four-registry loader calls with a free block above the watermark."""

    def __init__(self, rfa_path: str, *, name: Optional[str] = None):
        from .. import versions as V
        from ..container import open_rvt
        from ..elemtable import INVALID_ID
        from ..families import FamilyIndex
        from ..global_framing import reading
        from .extract_family import _partatom_title
        self.path = os.path.abspath(rfa_path)
        rp = _relp(self.path)
        if not os.path.isfile(self.path):
            raise RfaLoadError(f"{rfa_path}: file not found")
        # ---- a FAMILY container: every .rfa (Revit's and ours) carries the
        #      PartAtom manifest stream; a project (.rvt) never does ----------
        try:
            with open_rvt(self.path) as f:
                is_family = f.has("PartAtom")
        except Exception as e:                                     # noqa: BLE001
            raise RfaLoadError(f"{rp}: not a readable Revit container "
                               f"({type(e).__name__}: {e})") from e
        if not is_family:
            raise RfaLoadError(f"{rp}: no PartAtom stream -- this is a project "
                               "(.rvt), not a family file (.rfa); extract a family "
                               "from it first (rvt -> rfa --family X)")
        # ---- owner law: Global/ElemTable (release-agnostic framing) ----
        try:
            et = _elemtable(self.path)
        except Exception as e:                                     # noqa: BLE001
            raise RfaLoadError(f"{rp}: Global/ElemTable does not parse "
                               f"({type(e).__name__}: {e}) -- the standalone "
                               "owner law cannot be applied to this file") from e
        if et.footer is not None and int(et.footer.graveyard_count) != 0:
            raise RfaLoadError(
                f"{rp}: the ElemTable footer carries {et.footer.graveyard_count} "
                "GraveyardRec row(s) -- a wire layout never observed in the corpus "
                "(named codec gap, issue #13); refused rather than guessed")
        self._owner_of: Dict[int, int] = {
            int(r.id): (-1 if r.owner_id in (INVALID_ID, None) else int(r.owner_id))
            for r in et.records}
        # ---- records + schema + self-Family, under the file's OWN release --
        try:
            with reading(self.path):
                idx = FamilyIndex(self.path)
                recs = idx.unit_records(0) if idx.units else {}
                sf = _self_family(idx) if idx.units else None
        except Exception as e:                                     # noqa: BLE001
            raise RfaLoadError(f"{rp}: cannot be read as a family document "
                               f"({type(e).__name__}: {e})") from e
        if not idx.units:
            raise RfaLoadError(f"{rp}: no save units (not a family file)")
        if sf is None:
            raise RfaLoadError(f"{rp}: unit 0 has no self-Family element (not a "
                               "family document)")
        if len(idx.units) > 1:
            raise RfaLoadError(
                f"{rp}: the family embeds {len(idx.units) - 1} NESTED family "
                "document(s) (further save units); carrying nested units + their "
                "ContentDocuments entries along is not built in v1 -- refused by name")
        members = sorted(recs.get(102, {}))
        if not members:
            raise RfaLoadError(f"{rp}: unit 0 carries no element records")
        rep_class = {eid: idx.class_name(r.class_id) for eid, r in recs.get(103, {}).items()}
        other_rep = sorted(set(rep_class.values()) - set(_REP_CLASSES_OK))
        if other_rep:
            raise RfaLoadError(
                f"{rp}: unit 0 carries seq-103 classes beyond GElement/"
                f"SerializedDummy ({other_rep}) -- re-encoding them from decoded "
                "values would be lossy; refused by name")
        # keep only what build() needs (record payloads are copies; the
        # FamilyIndex with its inflated partition blocks is not retained)
        self._recs = recs
        self._gelement_reps = {eid for eid, c in rep_class.items() if c == "GElement"}
        self.schema = idx.schema
        self.members: List[int] = members
        self._class_of = {eid: idx.class_name(recs[102][eid].class_id) for eid in members}
        hist: Dict[str, int] = {}
        for c in self._class_of.values():
            hist[c] = hist.get(c, 0) + 1
        type_names = [str(t.get("name") or "") for t in (sf.get("types") or [])]
        # the current type = the first REAL-named pair (a born family's type
        # table opens with the blank ' ' current-values pair; a host symbol is
        # never blank-named -- famload's real_type_names law does the rest)
        cur = next((i for i, n in enumerate(type_names) if n.strip()), 0)
        self.facts = RfaFacts(
            n_elements=len(members), self_family=int(sf["id"]),
            category=int(sf.get("category") if sf.get("category") is not None else -1),
            part_type=int(sf.get("part_type") or 0),
            type_names=type_names, current_type=int(cur),
            name=str(name or _partatom_title(self.path)
                     or os.path.splitext(os.path.basename(self.path))[0]),
            release=V.detect_release(self.path), class_histogram=hist)
        self.last_build: Optional[Dict[str, Any]] = None      # census of build()

    # -- the famload builder ------------------------------------------------
    def idmap_at(self, start_id: int) -> Dict[int, int]:
        """{old id: new id}: the members in id order onto the contiguous
        block ``start_id ..`` (T2a's allocation law: watermark+1 onward)."""
        return {old: int(start_id) + i for i, old in enumerate(self.members)}

    def build(self, start_id: int = 100000) -> BornRfaDoc:
        """Decode every unit-0 record through the typed remap at
        ``start_id`` and wrap the rebased elements in a :class:`BornRfaDoc`."""
        from ..genesis.skeleton import SkelElement
        idmap = self.idmap_at(start_id)
        dec = RemapDecoder(self.schema, idmap)

        def val(r):
            if r is None:
                return None
            o = dec.decode_record(r.class_id, r.payload)
            return o.value if o else None

        r101, r102, r103 = (self._recs.get(s, {}) for s in (101, 102, 103))
        els: List[Any] = []
        undecoded: List[str] = []
        for eid in self.members:
            cname = self._class_of[eid]
            obj = val(r102[eid])
            hdr = val(r101.get(eid))
            rep = val(r103.get(eid)) if eid in self._gelement_reps else None
            if not isinstance(obj, dict):
                undecoded.append(f"{cname} {eid}")
            raw_owner = self._owner_of.get(eid, -1)
            owner = idmap.get(raw_owner, raw_owner) if raw_owner > 0 else -1
            els.append(SkelElement(idmap[eid], cname,
                                   hdr if isinstance(hdr, dict) else {},
                                   obj if isinstance(obj, dict) else {},
                                   rep if isinstance(rep, dict) else None,
                                   owner_id=owner))
        if undecoded:
            raise RfaLoadError(
                f"{_relp(self.path)}: {len(undecoded)} element record(s) do not "
                f"decode against the file's own schema ({undecoded[:6]}) -- "
                "re-authoring them would drop content; refused by name")
        f = self.facts
        sf_new = idmap[f.self_family]
        sf = next(e for e in els if e.elem_id == sf_new)
        doc = BornRfaDoc(els, sf, name=f.name, category_id=f.category,
                         part_type=f.part_type,
                         types=[(n, {}) for n in f.type_names],
                         current_type=f.current_type)
        self.last_build = {"start_id": int(start_id),
                           "block": [int(start_id), int(start_id) + len(els) - 1],
                           "self_family": sf_new,
                           "ids_remapped_values": int(dec.n_remapped),
                           "mode": "schema-typed decode-time remap"}
        return doc


# ---------------------------------------------------------------------------
# the load (no placement)
# ---------------------------------------------------------------------------

def load_rfa_into_project(rfa_path: str, host_rvt: str, out_rvt: str, *,
                          name: Optional[str] = None,
                          validate: bool = True) -> Dict[str, Any]:
    """LOAD a standalone-born ``.rfa`` into a copy of ``host_rvt`` ->
    ``out_rvt`` through :func:`rvt.famload.load_family_documents` (the
    loader invokes :meth:`RfaSource.build` with the free block above the
    host watermark and binds the family's own category style row as a core
    id when the host carries one -- T2a's recipe).  Writes the loader's
    report beside the output (``out_rvt + '.load.json'``).  Returns the
    load record (ok / stop_reason / plan ids / census / validator summary /
    ``summary`` = the one honest line for a manifest); raises
    :class:`RfaLoadError` only for a file this lane refuses by name."""
    from .. import famload as FL
    t0 = time.time()
    src = RfaSource(rfa_path, name=name)
    report_path = out_rvt + ".load.json"
    res = FL.load_family_documents(host_rvt, [FL.FamilyLoad(key=src.facts.name,
                                                            builder=src.build)],
                                   out_rvt, validate=validate, report_path=report_path)
    plan = res.plans[0] if res.plans else None
    ver = dict(res.proofs.get("verify_written") or {})
    v = ver.get("validate") or {}
    reg = ver.get("registries") or {}
    wm = (res.proofs.get("host") or {}).get("watermark")
    rb = src.last_build or {}
    summary = (f"STANDALONE-BORN .rfa (ids from {src.members[0]} <= host watermark "
               f"{wm}): loaded by the schema-typed id remap ({rb.get('ids_remapped_values')} "
               f"ElementId values -> block {rb.get('block')}) + rvt.famload. The "
               f"MECHANISM is viewer-certified ({CERTIFIED_BY}: a Revit-born "
               "1,992-element .rfa on the composed base + instance); THIS artifact is "
               "not -- it validates, certification stays with the ledger "
               "(docs/coverage/viewer-certified.json)")
    return {
        "ok": bool(res.ok), "stop_reason": res.stop_reason or None,
        "mechanism": MECHANISM, "certified_by": CERTIFIED_BY, "summary": summary,
        "out": _relp(out_rvt), "rfa": _relp(rfa_path), "host": _relp(host_rvt),
        "facts": dict(src.facts.__dict__), "rebase": src.last_build,
        "ids": None if plan is None else {
            "host_family": plan.host_family_id, "symbols": list(plan.symbol_ids),
            "symbol": plan.symbol_id, "surrogate": plan.surrogate_id,
            "twins": len(plan.twin_of), "core_ids": list(plan.core_ids),
            "content_guid": plan.guid, "doc_id_range": list(plan.doc_id_range)},
        "host_watermark": wm,
        "elements_added": int((res.proofs.get("host_elements") or {}).get("count") or 0),
        "registries": {k: reg.get(k) for k in (
            "save_units", "contentdocs_entries", "contenttable_records",
            "familymgr_entries", "coherent", "units_added", "ours_in_all_four")
            if k in reg} or None,
        "family_inventory_ok": (ver.get("family_inventory") or {}).get("ok"),
        "verify_ok": bool(ver.get("ok")),
        "validate": ({"verdict": v.get("verdict"), "n_errors": v.get("n_errors"),
                      "n_warnings": v.get("n_warnings")} if v else None),
        "report": _relp(report_path),
        "seconds": round(time.time() - t0, 1),
    }
