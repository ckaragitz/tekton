#!/usr/bin/env python
"""rft_probe.py -- THE BIRTH-STATE PROBE LADDER (rft-probes stream,
2026-08-05).

THE LEAD (field testers, career Revit users).  Desktop Revit cannot create
a family EXCEPT from an ``.rft`` template -- every genuine family document
is BORN with template inheritance.  That maps exactly onto the campaign's
terminal finding (genesis-audit verdicts #36..#42): a donor-DERIVED famdoc
reduced to our exact content PASSES the instance audit (SUB_ALL), our
from-scratch assembly of the same content FAILS (BX_conj: all 12 corpus
separators flipped coherently, still FAIL).  The audit checks something
inherited AT BIRTH that no content diff exposed -- and we have NEVER seen
an ``.rft``: the birth-state is unmeasured.  This ladder measures it.

THE LADDER (materials permitting; buildable-today rungs first):

  TB0   the SMALLEST Autodesk-born famdoc reachable by the PROVEN
        machinery, through the H7 recipe on its own host: the corpus
        census (``census`` subcommand) names M_RPC Female
        (racadvancedsampleproject unit 33, 381 records) -- famload +
        ONE uniform template instance.  MEASURED CAVEAT baked into the
        census: the absolutely smallest famdocs (199..233 records) are
        annotation families whose native instances are IndependentTag
        or view-owned FamilyInstances (m_ownerDBViewId, no level) --
        placing them with the proven level+phase model form would be a
        shape no native file exhibits (a confound, not a datum).  TB0 is
        the smallest famdoc whose native instances are MODEL-form
        (m_assocLevelId > 0).
  TB0r  the same question on the maximally-proven host: the smallest
        model-instanceable famdoc of the rst basic sample itself
        (M_Pile-Steel Pipe, unit 41, 414 records; B7's certified PASS
        is the 417-record concrete column on this exact host+path, so
        TB0r is a single-variable famdoc swap against a certified PASS).
  T0    the T-ladder FAIL anchor, buildable today: OUR famgen panelboard
        famdoc (the demo's PP-1) through the SAME famload + uniform
        template instance ON G_ABPD -- the exact substrate T3 augments,
        minus the birthright.  (H8B = famload + our famdoc on rst
        FAILED, b45; T0 transplants that anchor to this ladder's base
        and placement so every T-rung differs from T0 by ONE thing.)
  T2    the pure-birth control (the ``.rft`` equivalent of H7): the
        template's famdoc UNMODIFIED (id-rebased only), famload onto
        G_ABPD + one instance.  NEEDS samples/rft/ material.
  T1    the decision rung: the template-born famdoc SHELL + OUR
        panelboard content (the same 35-element axis union U16 carried,
        famdoc_bisect/famdoc_final machinery: registered in the
        TEMPLATE's self-Family, our level/views/extrusion ride along,
        only the self-Family reference is repointed) + famload + one
        instance on G_ABPD.  NEEDS samples/rft/ material.
  T3    the zero-donor product fix candidate: OUR famgen famdoc
        AUGMENTED by rvt.famgen.birthright (famgen AUTHORS the template
        birth features per experiments/rft/template_birth.json -- no
        donor bytes), same load + instance on G_ABPD.  NEEDS
        template_birth.json AND a fully-authorable birth delta;
        refuses (listing the gap = the author spec) otherwise.

READING (probes.json carries the full decision table): T2 PASS + T1 PASS
+ T0 FAIL confirms template-birth inheritance as the law and makes the
T1-body-vs-T0 diff the fix spec; T2 PASS + T1 FAIL says our content
poisons even a template-born shell (read against SUB_ALL PASS, which
accepted our content in a project-donor body); T2 FAIL says an unmodified
template famdoc is NOT project-embeddable by our machinery (the .rft
species differs) -- TB0/TB0r/B7 split machinery generality from famdoc
variance; T3 PASS closes the product gap (port birthright into famgen).

PROOF-ONLY: TB0/TB0r/T1/T2 embed Autodesk sample/template content and
stay quarantined in experiments/ (zero donors in shipped output; the
staged batch is the certified probe mechanism).  STAGE ONLY -- the
orchestrator uploads.

USAGE (repo root)::

    .venv/bin/python tools/rft_probe.py poll             # material readiness
    .venv/bin/python tools/rft_probe.py census           # corpus famdoc census
    .venv/bin/python tools/rft_probe.py build            # every buildable rung
    .venv/bin/python tools/rft_probe.py build --only TB0,TB0r,T0
    .venv/bin/python tools/rft_probe.py build --rft samples/rft/X.rft --only T2,T1
    .venv/bin/python tools/rft_probe.py verify           # re-run gates
    .venv/bin/python tools/rft_probe.py stage            # probe_batch + controls

TERRITORY: this file, ``src/rvt/famgen/birthright.py``,
``experiments/rftprobe/**``, ``tests/test_rft_probe.py``,
``docs/inbox/rft-probes.md``, plus the staging copies probe_batch itself
writes under ``experiments/acceptance/`` (its designed output).  IMPORTS
(never edits): tools/famdoc_bisect.py (hybrid machinery),
tools/famdoc_blobs.py (blob gate), tools/famdoc_final.py (union
conventions), tools/bisect_instance_bug.py (account gates),
tools/ifc_intent.py, tools/probe_batch.py, rvt.famload, rvt.families,
rvt.famgen.*.  No Autodesk install dirs, no browser, no full-suite runs.
"""
from __future__ import annotations

import argparse
import copy
import glob
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import time
import traceback
import uuid
from typing import Any, Dict, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (os.path.join(ROOT, "src"), HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

OUT_DIR = os.path.join(ROOT, "experiments", "rftprobe")
BUILD_DIR = os.path.join(OUT_DIR, "_build")
ACCT = os.path.join(OUT_DIR, "accounting.json")
CENSUS = os.path.join(OUT_DIR, "corpus_census.json")

RFT_DIR = os.path.join(ROOT, "samples", "rft")
BIRTH_JSON = os.path.join(ROOT, "experiments", "rft", "template_birth.json")

RST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
RAC_ADV = os.path.join(ROOT, "samples", "racadvancedsampleproject.rvt")
G_ABPD = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "compose",
                      "G_ABPD.rvt")

#: donor pins (measured 2026-08-05 by the ``census`` subcommand; tests pin)
TB0_HOST, TB0_UNIT = RAC_ADV, 33          # M_RPC Female, 381 records
TB0_SELF_FAMILY = 311681
TB0_CATEGORY = -2001370                   # OST entourage
TB0_TYPE = "Cynthia"                      # first host FamilySymbol name
TB0R_HOST, TB0R_UNIT = RST, 41            # M_Pile-Steel Pipe, 414 records
TB0R_SELF_FAMILY = 1224269
TB0R_CATEGORY = -2001300                  # OST structural foundations
TB0R_TYPE = "600mm Diameter"

#: uniform instance placement (the famdoc_bisect H-ladder convention)
PROBE_POSITION_FT = (16.0, -8.0, 0.0)

#: the closest available Revit-BORN standalone family file (provenance
#: measured 2026-08-05: Autodesk build string 20250227_1515(x64)E, a real
#: user save path, 64-byte unit blob) -- T2's dress rehearsal until the
#: .rft lands.  Dev-only donor role precedent: famdoc_adoc.TEMPLATE_DONOR.
VENDOR_RFA = os.path.join(ROOT, "vendor", "phi-ag-rvt", "examples",
                          "Autodesk", "racbasicsamplefamily-2026.rfa")

#: build/staging order = maximum information first
LADDER = ("TB0", "TB0r", "T0", "T2a", "T2", "T1", "T3")

AXES = {
    "TB0": "smallest model-instanceable Autodesk-born famdoc (M_RPC Female, "
           "racadvanced u33, 381 recs) through the H7 recipe on its own host",
    "TB0r": "smallest model-instanceable famdoc of the rst sample itself "
            "(M_Pile-Steel Pipe, u41, 414 recs) -- single-variable famdoc "
            "swap against certified B7 (417-rec column, same host+path)",
    "T0": "FAIL anchor: OUR famgen famdoc (PP-1) via famload + uniform "
          "template instance on G_ABPD (the substrate T3 augments)",
    "T2a": "T2's dress rehearsal: the Revit-BORN standalone .rfa famdoc "
           "(vendor racbasicsamplefamily-2026, 1992 elements, full birth "
           "catalog) UNMODIFIED via famload + instance on G_ABPD",
    "T2": "pure-birth control: the .rft template famdoc UNMODIFIED via "
          "famload + instance on G_ABPD (the .rft equivalent of H7)",
    "T1": "the decision rung: template-born famdoc SHELL + OUR 35-element "
          "content union (registered in the template self-Family) via "
          "famload + instance on G_ABPD",
    "T3": "product fix candidate: OUR famdoc + birthright-AUTHORED template "
          "birth features (zero donor bytes) via famload + instance on "
          "G_ABPD",
}


def log(msg: str) -> None:
    print(f"[rftprobe] {msg}", flush=True)


def relp(p: str) -> str:
    try:
        r = os.path.relpath(p, ROOT)
        return r if not r.startswith("..") else p
    except ValueError:
        return p


def md5_of(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def jdump(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=1, default=str)


def _load_tool(name: str):
    spec = importlib.util.spec_from_file_location(
        f"_rftprobe_{name}", os.path.join(HERE, f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_CACHE: Dict[str, Any] = {}


def _fb():
    """tools/famdoc_bisect.py with its output dirs repointed into THIS
    stream's territory (module attrs only; the famdoc-bisect stream's own
    evidence is never touched)."""
    if "fb" not in _CACHE:
        import famdoc_bisect as FB
        FB.OUT_DIR = os.path.join(BUILD_DIR, "_fb")
        FB.BUILD_DIR = os.path.join(BUILD_DIR, "_fb", "_build")
        _CACHE["fb"] = FB
    return _CACHE["fb"]


def _fbl():
    if "fbl" not in _CACHE:
        _CACHE["fbl"] = _load_tool("famdoc_blobs")
    return _CACHE["fbl"]


def _bisect():
    if "bisect" not in _CACHE:
        import bisect_instance_bug as B
        _CACHE["bisect"] = B
    return _CACHE["bisect"]


def _room():
    if "room" not in _CACHE:
        import ifc_intent as T
        _CACHE["room"] = T
    return _CACHE["room"]


def _pb():
    if "pb" not in _CACHE:
        _CACHE["pb"] = _load_tool("probe_batch")
    return _CACHE["pb"]


# ===========================================================================
# material polling
# ===========================================================================

def poll() -> Dict[str, Any]:
    """What the acquire stream has landed; which rungs are buildable NOW."""
    rfts = sorted(glob.glob(os.path.join(RFT_DIR, "**", "*.rft"),
                            recursive=True)) if os.path.isdir(RFT_DIR) else []
    birth = os.path.isfile(BIRTH_JSON)
    out = {
        "samples_rft_dir": os.path.isdir(RFT_DIR),
        "rft_files": [relp(p) for p in rfts],
        "template_birth_json": relp(BIRTH_JSON) if birth else None,
        "buildable_now": ["TB0", "TB0r", "T0"]
                         + (["T2a"] if os.path.isfile(VENDOR_RFA) else [])
                         + (["T2", "T1"] if rfts else [])
                         + (["T3"] if birth else []),
        "waiting_on": ([] if rfts else ["samples/rft/*.rft (T2, T1)"])
                      + ([] if birth else
                         ["experiments/rft/template_birth.json (T3)"]),
    }
    if birth:
        try:
            from rvt.famgen import birthright as BR
            spec = BR.read_birth_spec(BIRTH_JSON)
            out["birth_spec"] = spec.summary()
        except Exception as e:                                # noqa: BLE001
            out["birth_spec"] = {"error": f"{type(e).__name__}: {e}"}
    return out


# ===========================================================================
# the corpus census (the TB0 selection is MEASURED, not assumed)
# ===========================================================================

CORPUS = ("rstbasicsampleproject", "rmebasicsampleproject",
          "racbasicsampleproject", "rstadvancedsampleproject",
          "racadvancedsampleproject")


def census() -> Dict[str, Any]:
    """Every embedded famdoc of the six root samples: record count, nested
    content docs, seq-103 rep classes, and -- the selection axis -- how the
    family's NATIVE instances appear in the host (model-form FamilyInstance
    with a level vs view-owned vs IndependentTag vs none)."""
    from rvt.families import FamilyIndex, family_documents
    rows: List[Dict[str, Any]] = []
    for name in CORPUS:
        path = os.path.join(ROOT, "samples", f"{name}.rvt")
        idx = FamilyIndex(path)
        host = idx.unit_records(0)
        fi_cd = idx.schema.by_name["FamilyInstance"].type_id
        tag_cd = (idx.schema.by_name["IndependentTag"].type_id
                  if "IndependentTag" in idx.schema.by_name else None)
        model_by_sym: Dict[int, int] = {}
        view_by_sym: Dict[int, int] = {}
        tag_by_sym: Dict[int, int] = {}
        for eid, r in host.get(102, {}).items():
            if r.class_id == fi_cd:
                v = idx.value(0, eid) or {}
                sid = v.get("m_masterSymbolId")
                if (v.get("m_assocLevelId") or -1) > 0:
                    model_by_sym[sid] = model_by_sym.get(sid, 0) + 1
                else:
                    view_by_sym[sid] = view_by_sym.get(sid, 0) + 1
            elif tag_cd is not None and r.class_id == tag_cd:
                v = idx.value(0, eid) or {}
                sid = v.get("m_symbolId")
                if sid is not None:
                    tag_by_sym[sid] = tag_by_sym.get(sid, 0) + 1
        for fam in family_documents(idx):
            unit = fam.get("unit")
            if unit is None:
                continue
            recs = idx.unit_records(unit)
            s103: Dict[str, int] = {}
            for eid, r in recs.get(103, {}).items():
                c = idx.class_name(r.class_id)
                s103[c] = s103.get(c, 0) + 1
            loadable = set(s103) <= {"GElement", "SerializedDummy"}
            syms = [s["symbol_id"] for s in fam.get("symbols") or []]
            rows.append({
                "sample": name, "unit": unit,
                "family": fam.get("family_name"),
                "category": fam.get("category"),
                "part_type": fam.get("part_type"),
                "n_records": fam.get("n_records"),
                "n_nested_families": fam.get("n_nested_families"),
                "seq103_loadable": loadable,
                "seq103_other": sorted(set(s103) - {"GElement",
                                                    "SerializedDummy"}),
                "native_instances": {
                    "model_form": sum(model_by_sym.get(s, 0) for s in syms),
                    "view_owned": sum(view_by_sym.get(s, 0) for s in syms),
                    "independent_tag": sum(tag_by_sym.get(s, 0) for s in syms),
                },
            })
    rows.sort(key=lambda r: (r["n_records"] or 0, r["sample"], r["unit"]))
    model_rows = [r for r in rows if r["native_instances"]["model_form"] > 0
                  and r["seq103_loadable"]]
    out = {
        "tool": "tools/rft_probe.py census",
        "n_famdocs": len(rows),
        "smallest_overall": rows[:8],
        "smallest_model_instanceable": model_rows[:8],
        "selection": {
            "TB0": {"sample": "racadvancedsampleproject", "unit": TB0_UNIT,
                    "why": "smallest famdoc whose native instances are "
                           "MODEL-form (level-owned) FamilyInstances -- the "
                           "proven placement envelope"},
            "TB0r": {"sample": "rstbasicsampleproject", "unit": TB0R_UNIT,
                     "why": "smallest model-instanceable famdoc on the "
                            "maximally-proven host; single-variable pair "
                            "with certified B7"},
        },
        "annotation_finding": (
            "the corpus's absolutely smallest famdocs (199..233 records) are "
            "annotation families; their native 'instances' are "
            "IndependentTag elements or view-owned FamilyInstances "
            "(m_ownerDBViewId set, no level/phase) -- forms the proven "
            "level+phase template path does NOT produce.  Reaching them "
            "honestly needs view-owned placement grammar: proposed "
            "follow-up, not smuggled into this round."),
        "rows": rows,
    }
    jdump(CENSUS, out)
    log(f"census -> {relp(CENSUS)} ({len(rows)} famdocs; smallest "
        f"model-instanceable: {model_rows[0]['family']} "
        f"{model_rows[0]['n_records']} recs)" if model_rows else "census empty")
    return out


# ===========================================================================
# generalized machinery (famdoc_bisect's, parameterized by host)
# ===========================================================================

def _install_schema(host: str) -> None:
    from rvt.frontdoor import standalone as SA
    SA.install_schema(host)


def host_family_row(host: str, unit: int) -> Dict[str, Any]:
    """The HOST Family element facts of an embedded unit (name, category,
    part_type, symbols)."""
    from rvt.families import FamilyIndex, family_documents
    idx = FamilyIndex(host)
    for fam in family_documents(idx):
        if fam.get("unit") == unit:
            return fam
    raise RuntimeError(f"{relp(host)}: no host Family row for unit {unit}")


def born_doc_from_unit(host: str, unit: int, self_family_id: int, wm: int, *,
                       name: str, category_id: int, part_type: int,
                       type_name: str):
    """The H7 form generalized: ONE embedded Autodesk famdoc, id-rebased to
    a contiguous block above the host watermark, wrapped in the FamilyDoc
    protocol.  Returns (HybridFamilyDoc, report)."""
    FB = _fb()
    els, adoc_value, _idx = FB.load_unit_elements(host, unit)
    member = sorted(e.elem_id for e in els)
    idmap = {old: wm + 1 + i for i, old in enumerate(member)}
    new_els, census_ = FB.rebase_elements(els, idmap)
    sf_new = idmap[self_family_id]
    sf = next(e for e in new_els if e.elem_id == sf_new)
    doc = FB.HybridFamilyDoc(new_els, sf, name=name, category_id=category_id,
                             part_type=part_type, types=[(type_name, {})],
                             current_type=1)
    report = {"donor_host": relp(host), "donor_unit": unit,
              "donor_block": [wm + 1, wm + len(new_els)],
              "self_family": sf_new, "n_elements": len(new_els),
              "remap_census": census_,
              "adoc_appinfo_populated": sum(
                  1 for x in (((adoc_value.get("m_pAppInfoManager") or {})
                               .get("value") or {}).get("m_appInfoArr") or [])
                  if x)}
    return doc, report


def famload_onto(host: str, doc, out_path: str, key: str) -> Dict[str, Any]:
    """famdoc_bisect.famload_doc generalized over the host."""
    from rvt import famload as FL
    res = FL.load_family_documents(host, [FL.FamilyLoad(key=key, doc=doc)],
                                   out_path, validate=True,
                                   report_path=out_path + ".load.json")
    if not res.ok:
        raise RuntimeError(f"{key}: famload failed: {res.stop_reason}")
    p = res.plans[0]
    ver = (res.proofs.get("verify_written") or {})
    return {"family_id": p.host_family_id, "symbol_id": p.symbol_id,
            "surrogate": p.surrogate_id, "guid": p.guid,
            "doc_id_range": list(p.doc_id_range),
            "type_names": list(p.type_names or []),
            "verify_ok": bool(ver.get("ok")),
            "validate_errors": ((ver.get("validate") or {}).get("n_errors"))}


def place_one(src: str, out_path: str, *, host: str, symbol_id: int,
              family_id: int, category: int) -> Dict[str, Any]:
    """famdoc_bisect.place_probe generalized over the host: ONE instance by
    the uniform template machinery (ConstructedSpecimens built from the
    HOST's own facts + Document.add_family_instance + commit), instance
    category = the family's own."""
    from rvt.frontdoor import standalone as SA
    from rvt.mutate import Document
    from rvt.commit import commit_new_elements, verify_written
    T = _room()
    doc = Document.from_file(src)
    sp = SA.ConstructedSpecimens(SA.CONSTRUCTED, base_path=host)
    sp.inject_into(doc)
    lvl = T._pick_level(doc, 0.0)
    el = doc.add_family_instance(symbol_id, lvl, position=PROBE_POSITION_FT,
                                 rotation=0.0,
                                 template_instance_id=sp.instance_id)
    T._apply_frame(el, [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                   PROBE_POSITION_FT)
    scrub = T._scrub_instance(el, doc, our_symbol=symbol_id,
                              our_family=family_id,
                              spec_symbol=sp.instance_symbol,
                              spec_category=sp.instance_category,
                              category=category)
    dangling = doc.check_references(el)
    recs = doc.serialize(el)
    if recs is None:
        raise RuntimeError("rvt.encode unavailable")
    crep = commit_new_elements(src, out_path, [dict(recs)], [el.elemrec])
    ver = verify_written(out_path, [el.elem_id])
    cm = el.obj.get("m_pConnectorManager")
    return {"instance_id": el.elem_id, "level": lvl,
            "position_ft": list(PROBE_POSITION_FT),
            "connmgr": (cm.get("ptr_class") if isinstance(cm, dict) else cm),
            "scrub": scrub, "n_dangling": len(dangling),
            "watermark_after": crep.watermark_after,
            "verify": {k: ver.get(k) for k in ("crc_failures",
                                               "ecc_mismatches",
                                               "walker_errors", "stamps_ok")}}


# ===========================================================================
# the .rft reader (unit 0 of a standalone family/template container)
# ===========================================================================

def _remap_decoder(schema, idmap: Dict[int, int]):
    """An ObjectDecoder that substitutes ElementId-TYPED values through
    ``idmap`` DURING the byte decode (schema-driven typing, the validator's
    _RefDecoder hook).  THE REASON THIS EXISTS (measured 2026-08-05 on the
    vendor-born .rfa): a STANDALONE-born famdoc's element ids are SMALL
    (3..~2500 -- a fresh document id space), so the proven blind int-walk
    rebase (famgen loader's _walk_replace_ids; sound for project-embedded
    donors whose ids sit at 1.4M) ALIASES ordinary small integers -- flags,
    enum values, weakref indices -- into the id block and corrupts the
    records (first symptom: GeomStepList.m_flags encode overflow).  Typed
    substitution remaps exactly the values the schema says are element
    references, nothing else."""
    from rvt.objects import ObjectDecoder

    class RemapDecoder(ObjectDecoder):
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

    return RemapDecoder(schema, idmap)


def load_rft_elements(rft_path: str, idmap: Optional[Dict[int, int]] = None):
    """Decode the famdoc of a STANDALONE family/template file (its unit 0)
    into SkelElements.  Owner ids come from the ``Global/ElemTable`` stream
    (the standalone ownership law -- see below); the same seq-103 refusal
    gate as famdoc_bisect applies.  With ``idmap``, every record is decoded
    through the schema-TYPED remap decoder so the elements are BORN rebased
    (no post-hoc int walk -- unsound for the small-id standalone species).
    Returns (elements, facts)."""
    from rvt import adocument as A
    from rvt.container import open_rvt
    from rvt.elemtable import inflate_global_stream, parse_elemtable
    from rvt.families import FamilyIndex, self_family_of_unit
    from rvt.genesis.skeleton import SkelElement
    idx = FamilyIndex(rft_path)
    if not idx.units:
        raise RuntimeError(f"{relp(rft_path)}: no save units")
    unit = 0
    # OWNERSHIP LAW OF STANDALONE FAMILY FILES (measured 2026-08-05 on the
    # vendor racbasicsamplefamily-2026.rfa AND our own v2-emitted .rfa):
    # Global/Latest carries an EMPTY ADocument m_elemTable (externalized);
    # owner ids live in the Global/ElemTable STREAM.  Projects keep the
    # embedded famdoc's owners in the inline ContentDocuments ADocument --
    # a standalone file has no such entry.
    with open_rvt(rft_path) as f:
        latest = f.inflate("Global/Latest")
        et_raw = f.raw("Global/ElemTable")
    ad = A.decode_latest(latest)
    if not ad.clean:
        raise RuntimeError(f"{relp(rft_path)}: Global/Latest ADocument does "
                           f"not decode clean")
    owner_of: Dict[int, int] = {}
    owner_source = "Global/ElemTable"
    try:
        from rvt.elemtable import INVALID_ID
        et = parse_elemtable(inflate_global_stream(et_raw).payload,
                             relp(rft_path))
        for r in et.records:
            owner_of[int(r.id)] = (-1 if r.owner_id == INVALID_ID
                                   else int(r.owner_id))
    except Exception as e:                                     # noqa: BLE001
        raise RuntimeError(f"{relp(rft_path)}: Global/ElemTable does not "
                           f"parse ({type(e).__name__}: {e}) -- the "
                           f"standalone owner law needs re-measuring on "
                           f"this species") from e
    # fallback census only (record, never silently prefer): an inline-style
    # populated ADocument elem table would be a species difference
    inner = ((ad.value.get("m_elemTable") or {}).get("value") or {})
    adoc_rows = inner.get("m_elemArr") or []
    if adoc_rows:
        owner_source += f" (+ADocument elem table UNEXPECTEDLY populated: " \
                        f"{len(adoc_rows)} rows -- species finding)"
    recs = idx.unit_records(unit)
    idmap = dict(idmap or {})
    dec = _remap_decoder(idx.schema, idmap) if idmap else None

    def val(seq: int, eid: int):
        if dec is None:
            return idx.value(unit, eid, seq)
        r = recs.get(seq, {}).get(eid)
        if r is None:
            return None
        o = dec.decode_record(r.class_id, r.payload)
        return o.value if o else None

    els: List[SkelElement] = []
    other_rep: set = set()
    for eid in sorted(recs.get(102, {})):
        cname = idx.class_name(recs[102][eid].class_id)
        obj = val(102, eid)
        hdr = val(101, eid)
        rep = None
        r3 = recs.get(103, {}).get(eid)
        if r3 is not None:
            c3 = idx.class_name(r3.class_id)
            if c3 == "GElement":
                rv = val(103, eid)
                rep = rv if isinstance(rv, dict) else None
            elif c3 != "SerializedDummy":
                other_rep.add(c3)
        new_id = idmap.get(eid, eid)
        raw_owner = owner_of.get(eid, -1)
        owner = idmap.get(raw_owner, raw_owner) if raw_owner > 0 else -1
        els.append(SkelElement(new_id, cname,
                               hdr if isinstance(hdr, dict) else {},
                               obj if isinstance(obj, dict) else {}, rep,
                               owner_id=owner))
    if other_rep:
        raise RuntimeError(
            f"{relp(rft_path)} unit 0 carries seq-103 classes beyond "
            f"GElement/SerializedDummy: {sorted(other_rep)} -- the "
            f"SkelElement re-encode would be lossy; refused (REAL FINDING: "
            f"record it in docs/inbox/rft-probes.md)")
    sf = self_family_of_unit(idx, unit)
    if not sf:
        raise RuntimeError(f"{relp(rft_path)}: unit 0 has no Family element")
    hist: Dict[str, int] = {}
    for e in els:
        hist[e.class_name] = hist.get(e.class_name, 0) + 1
    facts = {"rft": relp(rft_path), "sha256": sha256_of(rft_path),
             "owner_source": owner_source,
             "n_units": len(idx.units), "n_elements": len(els),
             "self_family": sf["id"], "category": sf.get("category"),
             "part_type": sf.get("part_type"),
             "type_names": [t.get("name") for t in sf.get("types") or []
                            if t.get("name")],
             "class_histogram": hist,
             "rebase": ({"mode": "schema-typed decode-time remap",
                         "ids_remapped_values": dec.n_remapped}
                        if dec is not None else {"mode": "none"})}
    return els, facts


def pick_rft(explicit: Optional[str] = None) -> str:
    """The .rft to probe: an explicit path, else prefer an ELECTRICAL
    template (matches our panelboard content's category for T1), else the
    first .rft alphabetically."""
    if explicit:
        p = explicit if os.path.isabs(explicit) else os.path.join(ROOT, explicit)
        if not os.path.isfile(p):
            raise SystemExit(f"--rft {explicit}: not found")
        return p
    rfts = sorted(glob.glob(os.path.join(RFT_DIR, "**", "*.rft"),
                            recursive=True))
    if not rfts:
        raise SystemExit("no samples/rft/*.rft yet -- the acquire stream has "
                         "not landed; run 'poll'")
    for p in rfts:
        if "electrical" in os.path.basename(p).lower():
            return p
    return rfts[0]


def template_doc(rft_path: str, wm: int, *, name: str):
    """The template famdoc as a loadable HybridFamilyDoc (id-rebased above
    ``wm`` by the schema-TYPED remap -- the blind int-walk is unsound for
    the small-id standalone species), content otherwise UNMODIFIED.
    Returns (doc, report, ctx) where ctx carries the rebased elements +
    anchors for the T1 union."""
    FB = _fb()
    from rvt.families import FamilyIndex
    member = sorted(FamilyIndex(rft_path).unit_records(0).get(102, {}))
    idmap = {old: wm + 1 + i for i, old in enumerate(member)}
    new_els, facts = load_rft_elements(rft_path, idmap)
    census_ = facts["rebase"]
    sf_new = idmap[facts["self_family"]]
    sf = next(e for e in new_els if e.elem_id == sf_new)
    # first NON-BLANK type name: the famdoc type table opens with the
    # corpus blank pair ' ' (types5 law) but native HOST FamilySymbols
    # carry real names -- a ' '-named host symbol would be a shape no
    # native host exhibits
    named = [n for n in facts["type_names"] if str(n).strip()]
    types = [(named[0], {})] if named else [(name, {})]
    part_type = int(facts.get("part_type") if facts.get("part_type")
                    is not None else -1)
    doc = FB.HybridFamilyDoc(new_els, sf, name=name,
                             category_id=int(facts["category"]),
                             part_type=part_type,
                             types=types, current_type=1)
    report = {"rft_facts": facts,
              "template_block": [wm + 1, wm + len(new_els)],
              "self_family": sf_new, "remap_census": census_,
              "types_authored": types,
              "types_from_template": bool(facts["type_names"])}
    ctx = {"elements": new_els, "self_family": sf_new, "idmap": idmap,
           "facts": facts}
    return doc, report, ctx


# ===========================================================================
# T1: the template shell + OUR content union (U16's add-form on the shell)
# ===========================================================================

def template_union_doc(rft_path: str, wm: int):
    """The template famdoc + the UNION of ALL FIVE of our content axes
    (famdoc_final's U16 recipe with the template body as the donor): our 35
    elements carried as a self-consistent block -- level/views/extrusion
    ride along, ONLY the self-Family reference is repointed to the
    template's -- registered in the TEMPLATE self-Family exactly like U16
    registered in the donor's."""
    FB = _fb()
    from rvt.famgen.loader import _walk_replace_ids
    from rvt.genesis.skeleton import SkelElement

    tdoc, treport, ctx = template_doc(rft_path, wm, name="T1 shell")
    tpl_els = ctx["elements"]
    sf = next(e for e in tpl_els if e.elem_id == ctx["self_family"])

    prod = FB.our_product(wm + 200000)
    ours = prod.doc
    sets = FB.axis_sets(ours)
    carried_ids: set = set()
    for a in (1, 2, 3, 4, 5):
        carried_ids |= set(sets[f"H{a}"])
    carried_ids = sorted(carried_ids)
    by_id = {e.elem_id: e for e in ours.elements}

    repoint = {ours.self_family.elem_id: ctx["self_family"]}
    carried: List[Any] = []
    carried_set = set(carried_ids)
    for i in carried_ids:
        e = by_id[i]
        h, o = copy.deepcopy(e.header), copy.deepcopy(e.obj)
        r = copy.deepcopy(e.rep) if e.rep is not None else None
        for node in (h, o, r):
            if node is not None:
                _walk_replace_ids(node, repoint)
        owner = e.owner_id
        if owner in repoint:
            owner = repoint[owner]
        elif owner == ours.self_family.elem_id:
            owner = ctx["self_family"]
        carried.append(SkelElement(e.elem_id, e.class_name, h, o, r,
                                   owner_id=owner if (owner or 0) > 0 else -1,
                                   kind=e.kind))

    # dangling gate (famdoc_bisect's law)
    hybrid_ids = {e.elem_id for e in tpl_els} | carried_set
    our_ids = {e.elem_id for e in ours.elements}
    blocks_top = max(our_ids)
    dangling: List[Tuple[str, int]] = []

    def scan(node, path=""):
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(v, bool):
                    continue
                if isinstance(v, int) and wm < v <= blocks_top \
                        and v not in hybrid_ids:
                    dangling.append((path + "." + k, v))
                else:
                    scan(v, path + "." + k)
        elif isinstance(node, list):
            for j, v in enumerate(node):
                if isinstance(v, bool):
                    continue
                if isinstance(v, int) and wm < v <= blocks_top \
                        and v not in hybrid_ids:
                    dangling.append((f"{path}[{j}]", v))
                else:
                    scan(v, f"{path}[{j}]")

    for e in carried:
        scan(e.header, f"{e.elem_id}.hdr")
        scan(e.obj, f"{e.elem_id}.obj")
        if e.rep is not None:
            scan(e.rep, f"{e.elem_id}.rep")
    if dangling:
        raise RuntimeError(f"T1: carried union leaves dangling "
                           f"above-watermark refs: {dangling[:6]}")

    report = {"template": treport, "carried":
              [{"id": e.elem_id, "class": e.class_name, "kind": e.kind}
               for e in carried],
              "repointed": {str(k): v for k, v in repoint.items()},
              "dangling_above_watermark": 0, "registration": {}}

    # register in the template self-Family exactly like U16 did in the donor
    report["registration"]["membership"] = FB.register_added(
        sf, sorted(carried_set))
    param_ids = {e.elem_id for e in carried
                 if e.class_name == "ParamElemFamily"}
    our_sf = ours.self_family.obj
    fp_rows = (((our_sf.get("m_familyParams") or {}).get("value") or {})
               .get("m_params") or [])
    rows = [r for r in fp_rows
            if r.get("m_paramId") in param_ids
            or (isinstance(r.get("m_paramId"), int)
                and r.get("m_paramId") < 0)]
    locked = [i for i in (our_sf.get(
        "m_lockedParameterIdsForDirectManipulation") or []) if i in param_ids]
    groups: List[Dict[str, Any]] = []
    cells = ((our_sf.get("m_cellList") or {}).get("value") or {}) \
        .get("m_cells") or []
    for c in cells:
        cv = (c.get("value") or {}) if isinstance(c, dict) else {}
        for g in cv.get("m_sortedParams") or []:
            if not isinstance(g, dict):
                continue
            keep = [pid for pid in (g.get("m_paramIds") or [])
                    if pid in param_ids
                    or (isinstance(pid, int) and pid < 0)]
            if keep:
                groups.append({"m_groupTypeId":
                               copy.deepcopy(g.get("m_groupTypeId")),
                               "m_paramIds": keep})
        break
    # rows/locked/groups ride in OUR id space verbatim -- the carried param
    # elements keep their ids, exactly famdoc_final.make_union_doc's proven
    # treatment (U16 viewer-PASS)
    report["registration"]["params"] = FB.register_param_rows(
        sf, rows, locked, groups)

    elements = sorted(list(tpl_els) + carried, key=lambda e: e.elem_id)
    facts = ctx["facts"]
    named = [n for n in facts["type_names"] if str(n).strip()]
    types = [(named[0], {})] if named else [("T1", {})]
    doc = FB.HybridFamilyDoc(
        elements, sf, name="T1 template shell + our content",
        category_id=int(facts["category"]),
        part_type=int(facts.get("part_type") if facts.get("part_type")
                      is not None else -1),
        types=types, current_type=1)
    return doc, report


# ===========================================================================
# gates (blob proof + validator/account + census)
# ===========================================================================

def _gates(name: str, info: Dict[str, Any], acct: Dict[str, Any]) -> Dict[str, Any]:
    va = (acct.get("validator") or {})
    census_ = (acct.get("census") or {})
    bp = (info.get("blob_proof") or {})
    checks = {
        "validator_zero_unexpected": not va.get("unexpected_errors"),
        "census_coherent": bool(census_.get("coherent")),
        "survivor_law_ok": bool(acct.get("survivor_law_ok")),
        "blob_all_units_64B": bool(bp.get("all_units_64B")),
        "blob_added_nonce_ours": bool(bp.get("added_nonce_verified")),
        "instance_zero_dangling": (info.get("instance") or {}).get(
            "n_dangling") == 0,
    }
    return {"checks": checks, "gates_ok": all(checks.values())}


# ===========================================================================
# rung builders
# ===========================================================================

def _build_born(name: str, host: str, unit: int, self_family: int,
                category: int, type_name: str) -> Dict[str, Any]:
    """TB0 / TB0r: one Autodesk-born famdoc through the H7 recipe on its
    own host."""
    T = _room()
    fbl = _fbl()
    _install_schema(host)
    fam_row = host_family_row(host, unit)
    wm = T.host_watermark(host)
    pdir = os.path.join(BUILD_DIR, name)
    os.makedirs(pdir, exist_ok=True)
    outp = os.path.join(OUT_DIR, f"{name}.rvt")
    info: Dict[str, Any] = {"probe": name, "axis": AXES[name],
                            "base": relp(host), "watermark": wm,
                            "donor": {k: fam_row.get(k) for k in
                                      ("family_id", "family_name", "category",
                                       "part_type", "n_records", "unit")}}
    part_type = int(fam_row.get("part_type") or 0)
    doc, drep = born_doc_from_unit(
        host, unit, self_family, wm,
        name=f"{fam_row.get('family_name')} {name}",
        category_id=category, part_type=part_type, type_name=type_name)
    info["hybrid"] = drep
    info["document_guid"] = doc.document_guid
    info["n_elements"] = len(doc.elements)

    src = os.path.join(pdir, f"{name}_load.rvt")
    info["load"] = famload_onto(host, doc, src, name)
    info["immediate_parent"] = relp(src)
    sym, fam = info["load"]["symbol_id"], info["load"]["family_id"]
    info["symbol_id"], info["family_id"] = sym, fam
    info["placement"] = ("uniform template path (ConstructedSpecimens on "
                         "the probe's own host + add_family_instance + "
                         "commit; category = the family's own)")
    info["instance"] = place_one(src, outp, host=host, symbol_id=sym,
                                 family_id=fam, category=category)
    info["instance_ids"] = [info["instance"]["instance_id"]]
    info["blob_proof"] = fbl.blob_proof(outp, host)
    info["file"] = relp(outp)
    info["md5"] = md5_of(outp)
    return info


def build_tb0() -> Dict[str, Any]:
    return _build_born("TB0", TB0_HOST, TB0_UNIT, TB0_SELF_FAMILY,
                       TB0_CATEGORY, TB0_TYPE)


def build_tb0r() -> Dict[str, Any]:
    return _build_born("TB0r", TB0R_HOST, TB0R_UNIT, TB0R_SELF_FAMILY,
                       TB0R_CATEGORY, TB0R_TYPE)


def build_t0() -> Dict[str, Any]:
    """T0: OUR famgen famdoc (PP-1) via famload + uniform instance on
    G_ABPD -- the T-ladder FAIL anchor and T3's substrate."""
    FB = _fb()
    T = _room()
    fbl = _fbl()
    _install_schema(G_ABPD)
    wm = T.host_watermark(G_ABPD)
    pdir = os.path.join(BUILD_DIR, "T0")
    os.makedirs(pdir, exist_ok=True)
    outp = os.path.join(OUT_DIR, "T0.rvt")
    info: Dict[str, Any] = {"probe": "T0", "axis": AXES["T0"],
                            "base": relp(G_ABPD), "watermark": wm}
    from rvt import famload as FL
    products: Dict[str, Any] = {}

    def mk(start_id):
        prod = FB.our_product(start_id)
        products["T0"] = prod
        return prod.doc

    src = os.path.join(pdir, "T0_load.rvt")
    res = FL.load_family_documents(G_ABPD, [FL.FamilyLoad(key="T0",
                                                          builder=mk)],
                                   src, validate=True,
                                   report_path=src + ".load.json")
    if not res.ok:
        raise RuntimeError(f"T0: famload failed: {res.stop_reason}")
    p = res.plans[0]
    info["load"] = {"family_id": p.host_family_id, "symbol_id": p.symbol_id,
                    "guid": p.guid, "type_names": list(p.type_names or []),
                    "part_type": p.part_type}
    info["immediate_parent"] = relp(src)
    doc = products["T0"].doc
    info["our_category"] = int(doc.category_id)
    info["document_guid"] = doc.document_guid
    info["n_elements"] = len(doc.elements)
    info["placement"] = ("uniform template path on G_ABPD (category = our "
                         "famdoc's own)")
    info["instance"] = place_one(src, outp, host=G_ABPD,
                                 symbol_id=p.symbol_id,
                                 family_id=p.host_family_id,
                                 category=int(doc.category_id))
    info["instance_ids"] = [info["instance"]["instance_id"]]
    info["symbol_id"], info["family_id"] = p.symbol_id, p.host_family_id
    info["blob_proof"] = fbl.blob_proof(outp, G_ABPD)
    info["file"] = relp(outp)
    info["md5"] = md5_of(outp)
    return info


def build_t2a() -> Dict[str, Any]:
    """T2a: the Revit-born standalone .rfa famdoc unmodified via famload +
    instance on G_ABPD (the T2 recipe on the closest born standalone
    species available today)."""
    T = _room()
    fbl = _fbl()
    _install_schema(G_ABPD)
    wm = T.host_watermark(G_ABPD)
    pdir = os.path.join(BUILD_DIR, "T2a")
    os.makedirs(pdir, exist_ok=True)
    outp = os.path.join(OUT_DIR, "T2a.rvt")
    info: Dict[str, Any] = {"probe": "T2a", "axis": AXES["T2a"],
                            "base": relp(G_ABPD), "watermark": wm,
                            "rfa": relp(VENDOR_RFA)}
    doc, rep, _ctx = template_doc(VENDOR_RFA, wm, name="T2a rfa born")
    info["template"] = {k: rep[k] for k in ("template_block", "self_family",
                                            "remap_census", "types_authored",
                                            "types_from_template")}
    info["rfa_facts"] = {k: rep["rft_facts"][k] for k in
                         ("sha256", "owner_source", "n_units", "n_elements",
                          "category", "part_type", "type_names")}
    info["document_guid"] = doc.document_guid
    info["n_elements"] = len(doc.elements)
    src = os.path.join(pdir, "T2a_load.rvt")
    info["load"] = famload_onto(G_ABPD, doc, src, "T2a")
    info["immediate_parent"] = relp(src)
    sym, fam = info["load"]["symbol_id"], info["load"]["family_id"]
    info["symbol_id"], info["family_id"] = sym, fam
    cat = int(rep["rft_facts"]["category"])
    info["instance"] = place_one(src, outp, host=G_ABPD, symbol_id=sym,
                                 family_id=fam, category=cat)
    info["instance_ids"] = [info["instance"]["instance_id"]]
    info["blob_proof"] = fbl.blob_proof(outp, G_ABPD)
    info["file"] = relp(outp)
    info["md5"] = md5_of(outp)
    return info


def build_t2(rft_path: str) -> Dict[str, Any]:
    """T2: the template famdoc UNMODIFIED via famload + instance on
    G_ABPD."""
    T = _room()
    fbl = _fbl()
    _install_schema(G_ABPD)
    wm = T.host_watermark(G_ABPD)
    pdir = os.path.join(BUILD_DIR, "T2")
    os.makedirs(pdir, exist_ok=True)
    outp = os.path.join(OUT_DIR, "T2.rvt")
    info: Dict[str, Any] = {"probe": "T2", "axis": AXES["T2"],
                            "base": relp(G_ABPD), "watermark": wm,
                            "rft": relp(rft_path)}
    doc, rep, _ctx = template_doc(rft_path, wm, name="T2 template born")
    info["template"] = rep
    info["document_guid"] = doc.document_guid
    info["n_elements"] = len(doc.elements)
    src = os.path.join(pdir, "T2_load.rvt")
    info["load"] = famload_onto(G_ABPD, doc, src, "T2")
    info["immediate_parent"] = relp(src)
    sym, fam = info["load"]["symbol_id"], info["load"]["family_id"]
    info["symbol_id"], info["family_id"] = sym, fam
    cat = int(rep["rft_facts"]["category"])
    info["instance"] = place_one(src, outp, host=G_ABPD, symbol_id=sym,
                                 family_id=fam, category=cat)
    info["instance_ids"] = [info["instance"]["instance_id"]]
    info["blob_proof"] = fbl.blob_proof(outp, G_ABPD)
    info["file"] = relp(outp)
    info["md5"] = md5_of(outp)
    return info


def build_t1(rft_path: str) -> Dict[str, Any]:
    """T1: template shell + our content union via famload + instance on
    G_ABPD."""
    T = _room()
    fbl = _fbl()
    _install_schema(G_ABPD)
    wm = T.host_watermark(G_ABPD)
    pdir = os.path.join(BUILD_DIR, "T1")
    os.makedirs(pdir, exist_ok=True)
    outp = os.path.join(OUT_DIR, "T1.rvt")
    info: Dict[str, Any] = {"probe": "T1", "axis": AXES["T1"],
                            "base": relp(G_ABPD), "watermark": wm,
                            "rft": relp(rft_path)}
    doc, rep = template_union_doc(rft_path, wm)
    info["union"] = rep
    info["document_guid"] = doc.document_guid
    info["n_elements"] = len(doc.elements)
    src = os.path.join(pdir, "T1_load.rvt")
    info["load"] = famload_onto(G_ABPD, doc, src, "T1")
    info["immediate_parent"] = relp(src)
    sym, fam = info["load"]["symbol_id"], info["load"]["family_id"]
    info["symbol_id"], info["family_id"] = sym, fam
    cat = int(doc.category_id)
    info["instance"] = place_one(src, outp, host=G_ABPD, symbol_id=sym,
                                 family_id=fam, category=cat)
    info["instance_ids"] = [info["instance"]["instance_id"]]
    info["blob_proof"] = fbl.blob_proof(outp, G_ABPD)
    info["file"] = relp(outp)
    info["md5"] = md5_of(outp)
    return info


def build_t3() -> Dict[str, Any]:
    """T3: OUR famdoc + birthright-authored template birth features (zero
    donor bytes) via famload + instance on G_ABPD.  Refuses -- listing the
    gap, which IS the author spec -- when the birth delta is not fully
    authorable yet."""
    FB = _fb()
    T = _room()
    fbl = _fbl()
    from rvt.famgen import birthright as BR
    _install_schema(G_ABPD)
    spec = BR.read_birth_spec(BIRTH_JSON)
    wm = T.host_watermark(G_ABPD)
    pdir = os.path.join(BUILD_DIR, "T3")
    os.makedirs(pdir, exist_ok=True)
    outp = os.path.join(OUT_DIR, "T3.rvt")
    info: Dict[str, Any] = {"probe": "T3", "axis": AXES["T3"],
                            "base": relp(G_ABPD), "watermark": wm,
                            "birth_spec": spec.summary()}
    prod = FB.our_product(wm + 1)
    doc = prod.doc
    delta = BR.birth_delta(doc, spec)
    info["birth_delta"] = delta
    if delta.get("unauthorable"):
        jdump(os.path.join(OUT_DIR, "birthright_author_spec.json"),
              {"probe": "T3", "refused": True, "delta": delta,
               "note": "the unauthorable list IS the famgen author spec: "
                       "each entry needs a constructor registered in "
                       "rvt.famgen.birthright.CONSTRUCTORS"})
        raise RuntimeError(
            f"T3: birth delta not fully authorable yet -- "
            f"{len(delta['unauthorable'])} birth feature(s) lack famgen "
            f"constructors (see experiments/rftprobe/"
            f"birthright_author_spec.json); T3 refused, not faked")
    rep = BR.apply_birthright(doc, spec)
    info["birthright_applied"] = rep
    src = os.path.join(pdir, "T3_load.rvt")
    info["load"] = famload_onto(G_ABPD, doc, src, "T3")
    info["immediate_parent"] = relp(src)
    sym, fam = info["load"]["symbol_id"], info["load"]["family_id"]
    info["symbol_id"], info["family_id"] = sym, fam
    info["instance"] = place_one(src, outp, host=G_ABPD, symbol_id=sym,
                                 family_id=fam,
                                 category=int(doc.category_id))
    info["instance_ids"] = [info["instance"]["instance_id"]]
    info["blob_proof"] = fbl.blob_proof(outp, G_ABPD)
    info["file"] = relp(outp)
    info["md5"] = md5_of(outp)
    return info


BUILDERS = {"TB0": build_tb0, "TB0r": build_tb0r, "T0": build_t0,
            "T2a": build_t2a}


def base_of(name: str) -> str:
    return {"TB0": TB0_HOST, "TB0r": TB0R_HOST}.get(name, G_ABPD)


# ===========================================================================
# build driver
# ===========================================================================

def build(only: Optional[Sequence[str]] = None,
          rft: Optional[str] = None) -> Dict[str, Any]:
    B = _bisect()
    ready = poll()
    only = list(only) if only else list(ready["buildable_now"])
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(BUILD_DIR, exist_ok=True)
    t0 = time.time()
    out: Dict[str, Any] = {"tool": "tools/rft_probe.py",
                           "material": {k: ready[k] for k in
                                        ("rft_files", "template_birth_json")},
                           "built": {}, "accounting": {}, "gates": {},
                           "errors": {}}
    if os.path.isfile(ACCT):                       # merge partial (--only) runs
        try:
            with open(ACCT) as fh:
                prev = json.load(fh)
            out["built"] = {k: v for k, v in (prev.get("built") or {}).items()
                            if k not in only}
            out["accounting"] = {k: v for k, v in
                                 (prev.get("accounting") or {}).items()
                                 if k.split(".")[0] not in only}
            out["gates"] = {k: v for k, v in (prev.get("gates") or {}).items()
                            if k not in only}
        except Exception:                          # noqa: BLE001
            pass

    for name in [n for n in LADDER if n in only]:
        try:
            t1 = time.time()
            if name in BUILDERS:
                info = BUILDERS[name]()
            elif name == "T2":
                info = build_t2(pick_rft(rft))
            elif name == "T1":
                info = build_t1(pick_rft(rft))
            elif name == "T3":
                info = build_t3()
            else:
                raise RuntimeError(f"unknown rung {name}")
            info["seconds"] = round(time.time() - t1, 1)
            out["built"][name] = info
            log(f"{name} BUILT -> {info['file']} (md5 {info['md5'][:8]}, "
                f"{info['seconds']}s)")
        except Exception as e:                                 # noqa: BLE001
            out["errors"][name] = f"{type(e).__name__}: {e}"
            out["errors"][name + ".traceback"] = traceback.format_exc(limit=10)
            log(f"{name} FAILED: {type(e).__name__}: {e}")

    for name, info in list(out["built"].items()):
        if name not in only and name in out["accounting"]:
            continue
        try:
            base = base_of(name)
            parent = os.path.join(ROOT, info["immediate_parent"])
            _install_schema(base)
            rep = B.account(name, os.path.join(ROOT, info["file"]), parent,
                            declared_base=base,
                            instance_ids=info.get("instance_ids") or [])
            out["accounting"][name] = rep
            out["accounting"][name + ".hop_load"] = B.account(
                name + ".hop_load", parent, base, declared_base=base,
                instance_ids=[], with_regdiff=False)
            out["gates"][name] = _gates(name, info, rep)
            va = rep["validator"]
            log(f"{name}: validator {va['n_errors']} err "
                f"(unexpected {len(va['unexpected_errors'])}), census "
                f"coherent {rep['census']['coherent']}, gates "
                f"{'OK' if out['gates'][name]['gates_ok'] else 'RED'}")
        except Exception as e:                                 # noqa: BLE001
            out["errors"][name + ".accounting"] = f"{type(e).__name__}: {e}"
            out["errors"][name + ".accounting.tb"] = \
                traceback.format_exc(limit=8)
            log(f"{name} ACCOUNTING FAILED: {type(e).__name__}: {e}")

    out["seconds"] = round(time.time() - t0, 1)
    jdump(ACCT, out)
    write_probes_json(out)
    return out


# ===========================================================================
# probes.json (the decision table)
# ===========================================================================

READING = {
    "CTRL FAIL": "round VOID (oracle/environment) -- interpret nothing",
    "TB0/TB0r PASS": "the H7-recipe machinery generalizes beyond the "
                     "concrete column: even the smallest model-instanceable "
                     "Autodesk-born famdocs pass famload + instance -- "
                     "birth-inheritance holds for every born body probed; "
                     "the proven envelope widens (new host racadvanced, new "
                     "categories).",
    "TB0 FAIL + TB0r PASS": "host generality broken (racadvanced), famdoc "
                            "generality intact on rst -- machinery, not "
                            "birth; fix before reading T-rungs on other "
                            "hosts.",
    "TB0r FAIL": "REOPENS machinery suspicion: a single-variable famdoc "
                 "swap against certified B7 (same host, same path) fails "
                 "-- famdoc-specific variance the machinery mishandles; "
                 "bisect the pile famdoc vs the column famdoc.",
    "T0 FAIL": "expected (B0/H8B lineage): our famdoc still fails under "
               "the T-ladder's exact base+path -- the ladder is anchored.",
    "T0 PASS": "SURPRISE: our famdoc passes famload+template-placement on "
               "G_ABPD while failing famgen-loader (B0) and famload-on-rst "
               "(H8B) -- the defect would be in the OTHER load paths, not "
               "the famdoc; re-read the whole campaign before proceeding.",
    "T2 PASS + T1 PASS + T0 FAIL": "TEMPLATE-BIRTH INHERITANCE CONFIRMED "
                                   "as the law: a template-born shell "
                                   "accepts our exact content while our "
                                   "assembly of the same content fails.  "
                                   "The fix spec = the T1-body-vs-T0-body "
                                   "diff (template birth elements + "
                                   "self-Family/header field residues); "
                                   "T3/birthright is the product fix.",
    "T2 PASS + T1 FAIL": "our content poisons even a template-born shell "
                         "-- read against SUB_ALL PASS (project-donor body "
                         "accepted the same 35 elements): the delta "
                         "TEMPLATE-vs-PROJECT-DONOR body is the next "
                         "bisection axis.",
    "T2 FAIL": "an UNMODIFIED template famdoc through our machinery fails: "
               "either the .rft famdoc species differs from "
               "project-embedded famdocs (type table? category-coupled "
               "infrastructure?) or the machinery mishandles .rft-born "
               "content.  TB0/TB0r/B7 split machinery from famdoc: if they "
               "PASS, the .rft species itself is the finding.",
    "T3 PASS": "the zero-donor birthright authoring closes the gap: port "
               "rvt.famgen.birthright into the product path (opt-in), "
               "rebuild DEMO, close the campaign's last bug.",
    "T3 FAIL (T1 PASS)": "the authored birth set is incomplete/wrong -- "
                         "diff T3's famdoc vs T1's body against "
                         "template_birth.json; iterate birthright.",
}


def write_probes_json(build_out: Dict[str, Any]) -> str:
    onething = {
        "TB0": "the corpus-smallest model-instanceable Autodesk-born famdoc "
               "(M_RPC Female, racadvanced u33, 381 recs) famload-loaded "
               "into its OWN host + one uniform template instance.  The ONE "
               "new thing vs certified B7: the famdoc (and its host).",
        "TB0r": "the smallest model-instanceable famdoc of rst basic itself "
                "(M_Pile-Steel Pipe u41, 414 recs) through B7's exact "
                "host+path.  The ONE new thing vs B7: the famdoc alone.",
        "T0": "OUR famgen famdoc via famload + uniform template instance on "
              "G_ABPD.  The T-ladder's FAIL anchor: every T-rung differs "
              "from T0 by one declared thing.",
        "T2a": "the Revit-BORN standalone .rfa famdoc (1992 elements, the "
               "full birth catalog: 1477 GStyleElem + 70 CategoryElem + "
               "materials/fonts) UNMODIFIED via famload + instance on "
               "G_ABPD.  The ONE thing vs T0: the famdoc is BORN (saved by "
               "desktop Revit as a standalone family).",
        "T2": "the .rft template famdoc UNMODIFIED (id-rebase only) via the "
              "same famload + instance on G_ABPD.  The ONE thing vs T0: "
              "the famdoc is template-BORN.",
        "T1": "T2's template body + OUR 35-element content union registered "
              "in the template self-Family, same load + instance.  The ONE "
              "thing vs T2: our content rides a born shell; the ONE thing "
              "vs T0: the shell is born.",
        "T3": "OUR famdoc + birthright-AUTHORED birth features (zero donor "
              "bytes), same load + instance.  The ONE thing vs T0: the "
              "authored birth set.",
    }
    expected = {
        "TB0": "PASS (every born famdoc probed so far passes with a blob; "
               "FAIL reopens machinery generality)",
        "TB0r": "PASS (single-variable vs certified B7)",
        "T0": "FAIL (the B0/H8B lineage verdict reproduces)",
        "T2a": "PASS extends birth-inheritance to standalone-born bodies "
               "on G_ABPD; FAIL is a standalone-species finding that "
               "reframes T2 before any .rft is spent",
        "T2": "the hypothesis-bearing control: PASS frames T1; FAIL is a "
              "species finding",
        "T1": "THE DECISION RUNG: PASS confirms template-birth inheritance",
        "T3": "the product bet: PASS closes the gap",
    }
    probes = []
    order = 0
    for name in LADDER:
        info = (build_out.get("built") or {}).get(name)
        if not info:
            continue
        order += 1
        acct = (build_out.get("accounting") or {}).get(name) or {}
        va = acct.get("validator") or {}
        gates = (build_out.get("gates") or {}).get(name) or {}
        probes.append({
            "order": order,
            "rung": name,
            "file": f"experiments/rftprobe/{name}.rvt",
            "base": relp(base_of(name)),
            "kind": "probe",
            "axis": AXES[name],
            "n_families": 1, "n_instances": 1, "n_walls": 0,
            "the_ONE_thing_it_tests": onething[name],
            "expected": expected[name],
            "md5": info.get("md5"),
            "symbol_id": info.get("symbol_id"),
            "family_id": info.get("family_id"),
            "instance_ids": info.get("instance_ids"),
            "validator": {"n_errors": va.get("n_errors"),
                          "unexpected": len(va.get("unexpected_errors")
                                            or [])},
            "gates_ok": gates.get("gates_ok"),
        })
    doc = {
        "stream": "rft-probes (the birth-state probe ladder)",
        "tool": "tools/rft_probe.py",
        "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "material": build_out.get("material"),
        "question": "is TEMPLATE-BIRTH INHERITANCE the law behind the "
                    "instance audit's rejection of famgen-assembled "
                    "famdocs (verdicts #36-#42: SUB_ALL passes, BX_conj "
                    "fails)?",
        "probes": probes,
        "reading_the_matrix": READING,
        "notes": ["every probe: validator 0 unexpected errors, 64-byte "
                  "0x0f3f blob on every unit (added units carry OUR "
                  "deterministic nonce -- machine-verified), coherent "
                  "four-registry census, references resolved, ONE family + "
                  "ONE instance",
                  "TB0/TB0r embed Autodesk sample famdocs; T1/T2 embed "
                  ".rft template content -- ALL quarantined under "
                  "experiments/ (zero donor bytes in anything shipped)",
                  "T2b escalation (unbuilt): carry the .rft's own "
                  "Global/Latest ADocument as the inline ContentDocuments "
                  "entry (famdoc_bisect.swap_inline_adoc) if T2 fails and "
                  "the inline-ADoc axis needs re-splitting for .rft-born "
                  "bodies"],
    }
    path = os.path.join(OUT_DIR, "probes.json")
    jdump(path, doc)
    log(f"probes.json -> {relp(path)} ({len(probes)} probes)")
    return path


# ===========================================================================
# verify + stage
# ===========================================================================

def verify() -> Dict[str, Any]:
    """Re-run the cheap gates on the emitted probes (blob census + md5 vs
    accounting)."""
    fbl = _fbl()
    if not os.path.isfile(ACCT):
        raise SystemExit("no accounting.json -- run build first")
    with open(ACCT) as fh:
        acct = json.load(fh)
    out: Dict[str, Any] = {"checked": {}, "ok": True}
    for name, info in (acct.get("built") or {}).items():
        f = os.path.join(ROOT, info["file"])
        row: Dict[str, Any] = {}
        row["exists"] = os.path.isfile(f)
        if row["exists"]:
            row["md5_match"] = md5_of(f) == info.get("md5")
            try:
                bp = fbl.blob_proof(f, os.path.join(ROOT, base_of(name))
                                    if not os.path.isabs(base_of(name))
                                    else base_of(name))
                row["blob_ok"] = bool(bp.get("all_units_64B")
                                      and bp.get("added_nonce_verified"))
            except Exception as e:                             # noqa: BLE001
                row["blob_ok"] = False
                row["blob_error"] = f"{type(e).__name__}: {e}"
        ok = row.get("exists") and row.get("md5_match") and row.get("blob_ok")
        row["ok"] = bool(ok)
        out["checked"][name] = row
        out["ok"] = out["ok"] and row["ok"]
        log(f"{name}: {'OK' if row['ok'] else 'RED'} {row}")
    return out


def next_batch_number() -> int:
    pb = _pb()
    ns = []
    for p in glob.glob(os.path.join(pb.ACCEPTANCE, "batch_*.json")):
        m = os.path.basename(p)
        try:
            ns.append(int(m[len("batch_"):-len(".json")]))
        except ValueError:
            pass
    return (max(ns) + 1) if ns else 1


def stage(only: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """probe_batch gate + stage with a control per DISTINCT BASE used by the
    built probes (G_ABPD + the sample hosts), one batch, CONTROLS FIRST.
    ``only`` stages a subset (already-uploaded rungs stay out of the new
    batch -- the viewer never re-reads a staged file under a new name)."""
    pb = _pb()
    import datetime as _dt
    if not os.path.isfile(ACCT):
        raise SystemExit("no accounting.json -- run build first")
    with open(ACCT) as fh:
        acct = json.load(fh)
    built = acct.get("built") or {}
    names = [n for n in LADDER if n in built
             and (only is None or n in only)]
    if not names:
        raise SystemExit("nothing built")
    files = [os.path.join(ROOT, built[n]["file"]) for n in names]
    bad = [n for n in names
           if not (acct.get("gates") or {}).get(n, {}).get("gates_ok")]
    if bad:
        raise SystemExit(f"gates not green for {bad} -- stage refused")
    ledger = pb.Ledger.load()
    entries, violations = pb.check_batch(files, ledger)
    if violations:
        raise pb.GateRefusal(violations)
    n = next_batch_number()
    out_dir = pb.ACCEPTANCE
    bases: List[str] = []
    for name in names:
        b = relp(base_of(name))
        if b not in bases:
            bases.append(b)
    controls = [pb.make_control(ledger, n, out_dir,
                                source=os.path.join(ROOT, b)) for b in bases]
    ordered = controls + [e for e in entries if e.kind == "probe"]
    for i, e in enumerate(ordered):
        e.order = i
        if e.kind == "control":
            continue
        src = pb.abspath(e.file)
        dst = os.path.join(out_dir, os.path.basename(e.file))
        if os.path.abspath(src) != os.path.abspath(dst):
            if os.path.exists(dst) and md5_of(dst) != e.md5:
                raise pb.GateRefusal(
                    [f"{e.file}: a DIFFERENT file already sits at "
                     f"{pb.rel(dst)}; rename the probe -- never overwrite a "
                     f"staged file the viewer may already have read"])
            shutil.copyfile(src, dst)
        e.staged_as = pb.rel(dst)
    manifest = {
        "batch": n,
        "created": _dt.datetime.now().astimezone()
                   .isoformat(timespec="seconds"),
        "tool": "tools/rft_probe.py (via tools/probe_batch.py primitives)",
        "law": ("every entry's declared base is ITSELF certified (or an "
                "Autodesk sample source); the batch carries one CONTROL "
                "per distinct base, CONTROLS FIRST; control FAIL voids its "
                "probes"),
        "ledger": pb.rel(ledger.path),
        "control_count": len(controls),
        "controls": {os.path.basename(c.control_source or ""): c.staged_as
                     for c in controls},
        "note": "rft-probes: THE BIRTH-STATE LADDER.  Revit only creates "
                "families FROM .rft templates -- every genuine famdoc is "
                "born with template inheritance; verdicts #36-#42 left "
                "exactly that unmeasured (SUB_ALL donor-derived PASS vs "
                "BX_conj famgen FAIL).  Reading order: TB0/TB0r (born-"
                "famdoc machinery generality), T0 (FAIL anchor), T2 "
                "(pure-birth control), T1 (THE DECISION RUNG), T3 "
                "(birthright product fix).  Read "
                "experiments/rftprobe/probes.json reading_the_matrix.",
        "reading_order": [os.path.basename(e.staged_as or e.file)
                          for e in ordered],
        "entries": [e.to_json() for e in ordered],
    }
    path = os.path.join(out_dir, f"batch_{n}.json")
    with open(path, "w") as fh:
        json.dump(manifest, fh, indent=1)
    manifest["manifest_path"] = pb.rel(path)
    log(f"STAGED batch {n} -> {manifest['manifest_path']}")
    for e in ordered:
        log(f"  [{e.order}] {e.staged_as} ({e.kind})")
    for e in ordered:
        got = md5_of(os.path.join(ROOT, e.staged_as))
        if got != e.md5:
            raise RuntimeError(f"staged copy md5 mismatch: {e.staged_as}")
    log("staged copies md5-verified")
    return manifest


# ===========================================================================
# selftest: the T2/T1 code path proven BEFORE any .rft exists
# ===========================================================================

def selftest() -> Dict[str, Any]:
    """Drive the ENTIRE T2 code path on a stand-in: emit OUR OWN famgen
    famdoc as a standalone family container (zero donor bytes), read it
    back through ``load_rft_elements`` (the exact .rft reader), rebase,
    famload onto G_ABPD, place one instance, run the gates.  When the real
    ``.rft`` lands, the only untested surface is the .rft species itself.
    The output stays in _build/ -- it is a plumbing proof, NOT a probe
    (its famdoc is ours; as a viewer question it would duplicate T0)."""
    FB = _fb()
    T = _room()
    fbl = _fbl()
    _install_schema(G_ABPD)
    pdir = os.path.join(BUILD_DIR, "selftest")
    os.makedirs(pdir, exist_ok=True)
    out: Dict[str, Any] = {"selftest": "T2-path on our own .rfa stand-in"}
    wm = T.host_watermark(G_ABPD)
    prod = FB.our_product(wm + 1)
    rfa = os.path.join(pdir, "standin.rfa")
    from rvt.famgen import famdoc_adoc as FA
    # donor = the composed genesis base (the product recipe,
    # standalone.write_family_bundled): schema constant from it, every other
    # stream ours; the default vendor TEMPLATE_DONOR's id space collides
    # with docs built above G_ABPD's watermark (provenance scan false hit)
    FA.emit_family_rfa_v2(prod.doc, rfa, donor=G_ABPD, write_reports=False)
    out["standin_rfa"] = relp(rfa)
    els, facts = load_rft_elements(rfa)
    out["read_back"] = {k: facts[k] for k in ("n_units", "n_elements",
                                              "self_family", "category",
                                              "part_type", "type_names")}
    ours = {e.elem_id: e.class_name for e in prod.doc.elements}
    theirs = {e.elem_id: e.class_name for e in els}
    if ours != theirs:
        raise RuntimeError(
            f"selftest: read-back roster differs from the emitted famdoc "
            f"(only in ours: {sorted(set(ours) - set(theirs))[:5]}; only in "
            f"read-back: {sorted(set(theirs) - set(ours))[:5]})")
    out["roster_roundtrip"] = f"{len(ours)}/{len(ours)} ids+classes equal"
    owner_mismatch = [e.elem_id for o, e in zip(
        sorted(prod.doc.elements, key=lambda x: x.elem_id),
        sorted(els, key=lambda x: x.elem_id))
        if (o.owner_id if (o.owner_id or 0) > 0 else -1)
        != (e.owner_id if (e.owner_id or 0) > 0 else -1)]
    out["owner_roundtrip"] = ("OK" if not owner_mismatch
                              else f"MISMATCH {owner_mismatch[:6]}")
    if owner_mismatch:
        raise RuntimeError(f"selftest: owner ids diverge for "
                           f"{owner_mismatch[:6]}")
    doc, rep, _ctx = template_doc(rfa, wm, name="selftest standin")
    out["template_doc"] = {"block": rep["template_block"],
                           "types": rep["types_authored"]}
    src = os.path.join(pdir, "selftest_load.rvt")
    out["load"] = famload_onto(G_ABPD, doc, src, "SELFTEST")
    probe = os.path.join(pdir, "selftest_probe.rvt")
    out["instance"] = place_one(src, probe, host=G_ABPD,
                                symbol_id=out["load"]["symbol_id"],
                                family_id=out["load"]["family_id"],
                                category=int(doc.category_id))
    out["blob_proof"] = {k: fbl.blob_proof(probe, G_ABPD)[k]
                         for k in ("all_units_64B", "added_nonce_verified",
                                   "units_total")}
    from rvt.validate import validate_file
    v = validate_file(probe)
    out["validator"] = {"n_errors": len(v.errors),
                        "first": [str(e)[:120] for e in v.errors[:3]]}
    ok = (not owner_mismatch and out["blob_proof"]["all_units_64B"]
          and out["blob_proof"]["added_nonce_verified"]
          and out["validator"]["n_errors"] == 0
          and out["instance"]["n_dangling"] == 0)
    out["ok"] = bool(ok)
    jdump(os.path.join(OUT_DIR, "selftest.json"), out)
    log(f"selftest {'OK' if ok else 'RED'} -> "
        f"{relp(os.path.join(OUT_DIR, 'selftest.json'))}")
    return out


# ===========================================================================

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("poll")
    sub.add_parser("census")
    b = sub.add_parser("build")
    b.add_argument("--only", help="comma-separated rung names")
    b.add_argument("--rft", help="explicit .rft path for T1/T2")
    sub.add_parser("verify")
    st = sub.add_parser("stage")
    st.add_argument("--only", help="comma-separated rung names to stage")
    sub.add_parser("selftest")
    args = ap.parse_args(argv)
    if args.cmd == "poll":
        print(json.dumps(poll(), indent=1))
        return 0
    if args.cmd == "census":
        census()
        return 0
    if args.cmd == "build":
        only = [s.strip() for s in args.only.split(",")] if args.only else None
        out = build(only, rft=args.rft)
        return 0 if not out["errors"] else 1
    if args.cmd == "verify":
        out = verify()
        return 0 if out["ok"] else 1
    if args.cmd == "stage":
        stage([s.strip() for s in args.only.split(",")]
              if args.only else None)
        return 0
    if args.cmd == "selftest":
        return 0 if selftest()["ok"] else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
