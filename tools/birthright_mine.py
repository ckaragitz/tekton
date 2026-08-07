#!/usr/bin/env python
"""birthright_mine.py -- THE SUFFICIENCY PROBE + THE BIRTHRIGHT AUTHOR
(birthright stream, post-verdict-#43).

THE CONFIRMED LAW (genesis-audit verdicts #43, docs/inbox/rft-probes.md):
Revit-BORN family documents pass the instance audit through our ENTIRE
pipeline (T2a: the vendor standalone .rfa famdoc famloaded onto composed
G_ABPD + instance = viewer-PASS; TB0/TB0r likewise); our from-scratch
famgen famdocs fail (T0).  THE FIX = BIRTHRIGHT AUTHORING: famgen authors
what a template birth provides -- mined SHAPES re-authored as our own
constructions, zero donor bytes in anything shipped.

THE LADDER (probe reading order = the charter's decision table):

  T1v       DEV-ONLY sufficiency probe, built FIRST: our PANELBOARD
            content (the B0 famdoc's 35 content elements: geometry forms,
            params/types, datums, views, connector) ADDED ALONGSIDE the
            born famdoc SHELL (the vendor .rfa's famdoc UNMODIFIED -- the
            add-alongside variant keeps single-variable reading vs T2a:
            the ONE new thing is our content union riding the born body),
            famloaded onto G_ABPD + ONE instance.  T1v PASS = the birth
            set is SUFFICIENT for our content (the fix is fully
            specified); T1v FAIL = our content itself interacts (bisect
            our axes inside the born shell next).
  BX_birth  the B0 recipe THROUGH birthright: OUR famdoc, OUR authored
            birth set (rvt.famgen.birthright author lanes over the mined
            template_birth.json -- zero donors), famgen chain + ONE
            instance on G_ABPD.
  DEMO_250v_room_v7
            the user's exact prompt ('an electrical room rated for 250V
            with 6 panels') end-to-end through rvt.frontdoor.run with
            birthright enabled.

  Decision table: T1v PASS + BX_birth PASS + v7 PASS = THE CAMPAIGN
  CLOSES; T1v PASS + BX_birth FAIL = the authored birth misses something
  the born shell has (diff authored-vs-born birth field-by-field -- the
  gap list is finite, `diff` emits it); T1v FAIL = content interaction
  (bisect our axes in the born shell).

THE MINER (`mine`): reads the born specimen (the vendor standalone .rfa,
DEV/PROOF-ONLY quarantined mining material) through the proven
schema-TYPED .rfa reader and emits ``experiments/birthright/
template_birth.json`` -- the contract ``rvt.famgen.birthright`` accepts:
the birth element roster famgen never authors (style-catalog
constellation per the annotation-attr ownership law), the blank-pair
type-table shape, the self-Family field residue (incl. the layout-law
12 separators' born-side values), the UnitsElem/view-chain ownership
topology, and the identity strings (marked AUTHOR -- never carried).
Element references inside mined field models are stored SYMBOLICALLY
({"__eid__": born_id}); non-adoptable values are stored as AUTHOR slots
({"__author__": ...}); adoptable values (laws/shapes per the zero-donor
line) are carried as plain JSON.

PROOF-ONLY: T1v embeds the vendor famdoc and stays quarantined in
experiments/ (zero donors in anything shipped); BX_birth / DEMO v7 carry
ZERO donor bytes (their birth set is authored by our writers from the
mined spec).  STAGE ONLY -- the orchestrator uploads.

USAGE (repo root)::

    .venv/bin/python tools/birthright_mine.py t1v          # the sufficiency probe
    .venv/bin/python tools/birthright_mine.py mine         # template_birth.json
    .venv/bin/python tools/birthright_mine.py build        # BX_birth + DEMO v7
    .venv/bin/python tools/birthright_mine.py build --only BX_birth
    .venv/bin/python tools/birthright_mine.py diff         # authored-vs-mined
    .venv/bin/python tools/birthright_mine.py verify       # re-run gates
    .venv/bin/python tools/birthright_mine.py stage        # probe_batch + control

TERRITORY: this file, ``src/rvt/famgen/birthright.py``,
``experiments/birthright/**``, ``tests/test_birthright.py``,
``docs/inbox/birthright.md``, plus the staging copies probe_batch itself
writes under ``experiments/acceptance/``.  IMPORTS (never edits):
tools/rft_probe.py (the .rfa reader + T1-union + placement machinery),
tools/famdoc_bisect.py, tools/famdoc_blobs.py (blob gate),
tools/bisect_instance_bug.py (chain + account), tools/ifc_intent.py,
tools/probe_batch.py, rvt.famload_hostfix, rvt.frontdoor, rvt.famgen.*.
No Autodesk install dirs, no browser, no full-suite runs.
"""
from __future__ import annotations

import argparse
import contextlib
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
from typing import Any, Dict, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (os.path.join(ROOT, "src"), HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

OUT_DIR = os.path.join(ROOT, "experiments", "birthright")
BUILD_DIR = os.path.join(OUT_DIR, "_build")
ACCT = os.path.join(OUT_DIR, "accounting.json")
BIRTH_JSON = os.path.join(OUT_DIR, "template_birth.json")
MINING_REPORT = os.path.join(OUT_DIR, "mining_report.json")
DIFF_JSON = os.path.join(OUT_DIR, "authored_vs_mined_diff.json")

G_ABPD = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "compose",
                      "G_ABPD.rvt")
DEMO_PROMPT = "an electrical room rated for 250V with 6 panels"

#: build / staging / reading order = the charter's decision table
LADDER = ("T1v", "BX_birth", "DEMO_250v_room_v7")

AXES = {
    "T1v": "SUFFICIENCY: our 35-element content union ADDED alongside the "
           "born famdoc shell (vendor .rfa unmodified), famload + ONE "
           "instance on G_ABPD -- the ONE thing vs T2a (PASS): our content "
           "rides the born body",
    "BX_birth": "the B0 recipe through birthright: OUR famdoc + OUR "
                "authored birth set (zero donor bytes), famgen chain + ONE "
                "instance on G_ABPD",
    "DEMO_250v_room_v7": "the user's exact prompt end-to-end through "
                         "rvt.frontdoor.run with birthright enabled",
}


def log(msg: str) -> None:
    print(f"[birthright] {msg}", flush=True)


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


def jdump(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=1, default=str)


def _load_tool(name: str):
    spec = importlib.util.spec_from_file_location(
        f"_birthright_{name}", os.path.join(HERE, f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_CACHE: Dict[str, Any] = {}


def _rp():
    """tools/rft_probe.py -- the proven .rfa reader / T1-union / placement
    machinery (its famdoc_bisect output dirs repoint themselves)."""
    if "rp" not in _CACHE:
        _CACHE["rp"] = _load_tool("rft_probe")
    return _CACHE["rp"]


def _fbl():
    if "fbl" not in _CACHE:
        _CACHE["fbl"] = _load_tool("famdoc_blobs")
    return _CACHE["fbl"]


def _bisect():
    if "bisect" not in _CACHE:
        import bisect_instance_bug as B
        _CACHE["bisect"] = B
    return _CACHE["bisect"]


def _pb():
    if "pb" not in _CACHE:
        _CACHE["pb"] = _load_tool("probe_batch")
    return _CACHE["pb"]


# ===========================================================================
# T1v -- the sufficiency probe (born shell + our content, ADD-alongside)
# ===========================================================================

def build_t1v() -> Dict[str, Any]:
    """T1v: rft_probe.template_union_doc on the VENDOR .rfa (the T1 recipe
    with the born standalone as the shell -- our 35-element union carried
    as a self-consistent block, registered in the BORN self-Family), then
    the same famload + uniform instance on G_ABPD as T2a.  ADD-alongside
    variant: the born body is UNMODIFIED (single variable vs T2a PASS)."""
    rp = _rp()
    fbl = _fbl()
    T = rp._room()
    rp._install_schema(G_ABPD)
    wm = T.host_watermark(G_ABPD)
    pdir = os.path.join(BUILD_DIR, "T1v")
    os.makedirs(pdir, exist_ok=True)
    outp = os.path.join(OUT_DIR, "T1v.rvt")
    info: Dict[str, Any] = {"probe": "T1v", "axis": AXES["T1v"],
                            "base": relp(G_ABPD), "watermark": wm,
                            "rfa": relp(rp.VENDOR_RFA),
                            "variant": "ADD-alongside (born body unmodified; "
                                       "single-variable vs T2a)"}
    doc, rep = rp.template_union_doc(rp.VENDOR_RFA, wm)
    info["union"] = {
        "template": {k: rep["template"].get(k) for k in
                     ("template_block", "self_family", "types_authored",
                      "types_from_template")},
        "rfa_facts": {k: rep["template"]["rft_facts"][k] for k in
                      ("sha256", "owner_source", "n_units", "n_elements",
                       "category", "part_type", "type_names")},
        "carried": rep["carried"],
        "n_carried": len(rep["carried"]),
        "repointed": rep["repointed"],
        "registration": rep["registration"],
    }
    info["document_guid"] = doc.document_guid
    info["n_elements"] = len(doc.elements)
    src = os.path.join(pdir, "T1v_load.rvt")
    info["load"] = rp.famload_onto(G_ABPD, doc, src, "T1v")
    info["immediate_parent"] = relp(src)
    sym, fam = info["load"]["symbol_id"], info["load"]["family_id"]
    info["symbol_id"], info["family_id"] = sym, fam
    cat = int(doc.category_id)
    info["instance_category"] = cat
    info["instance"] = rp.place_one(src, outp, host=G_ABPD, symbol_id=sym,
                                    family_id=fam, category=cat)
    info["instance_ids"] = [info["instance"]["instance_id"]]
    info["blob_proof"] = fbl.blob_proof(outp, G_ABPD)
    info["file"] = relp(outp)
    info["md5"] = md5_of(outp)
    return info


# ===========================================================================
# gates (rft_probe's shape: validator + census + survivor + blob + refs)
# ===========================================================================

def _gates(name: str, info: Dict[str, Any], acct: Dict[str, Any]) -> Dict[str, Any]:
    va = (acct.get("validator") or {})
    census_ = (acct.get("census") or {})
    bp = (info.get("blob_proof") or {})
    # per-instance dangling data when the builder measured it (T1v's
    # place_one / BX_birth's place_instances); otherwise every instance
    # must carry a registration row in the account's regdiff
    probes = (info.get("instances_dangling_probe")
              or ([info["instance"]] if info.get("instance") else None)
              or [{"n_dangling": (i or {}).get("n_dangling")}
                  for i in (info.get("equipment") or {}).get("instances")
                  or []])
    if probes:
        inst_ok = all((p or {}).get("n_dangling") == 0 for p in probes)
    else:
        regs = acct.get("registrations") or {}
        ids = [str(i) for i in info.get("instance_ids") or []]
        inst_ok = bool(ids) and all(
            k in regs and (regs[k] or {}).get("row") for k in ids)
    checks = {
        "validator_zero_unexpected": not va.get("unexpected_errors"),
        "census_coherent": bool(census_.get("coherent")),
        "survivor_law_ok": bool(acct.get("survivor_law_ok")),
        "blob_all_units_64B": bool(bp.get("all_units_64B")),
        "blob_added_nonce_ours": bool(bp.get("added_nonce_verified")),
        "instances_resolved": inst_ok,
        "birthright_verified": (
            all((r.get("verify") or {}).get("ok")
                for r in info.get("birthright") or [])
            if info.get("birthright") is not None else True),
    }
    return {"checks": checks, "gates_ok": all(checks.values())}


# ===========================================================================
# build driver
# ===========================================================================

def build(only: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    B = _bisect()
    rp = _rp()
    only = list(only) if only else list(LADDER)
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(BUILD_DIR, exist_ok=True)
    t0 = time.time()
    out: Dict[str, Any] = {"tool": "tools/birthright_mine.py", "built": {},
                           "accounting": {}, "gates": {}, "errors": {}}
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

    builders = {"T1v": build_t1v, "BX_birth": build_bx_birth,
                "DEMO_250v_room_v7": build_demo_v7}
    for name in [n for n in LADDER if n in only]:
        try:
            t1 = time.time()
            info = builders[name]()
            info["seconds"] = round(time.time() - t1, 1)
            out["built"][name] = info
            log(f"{name} BUILT -> {info['file']} (md5 {info['md5'][:8]}, "
                f"{info['seconds']}s)")
        except Exception as e:                                 # noqa: BLE001
            out["errors"][name] = f"{type(e).__name__}: {e}"
            out["errors"][name + ".traceback"] = traceback.format_exc(limit=12)
            log(f"{name} FAILED: {type(e).__name__}: {e}")

    for name, info in list(out["built"].items()):
        if name not in only and name in out["accounting"]:
            continue
        try:
            parent = os.path.join(ROOT, info["immediate_parent"])
            rp._install_schema(G_ABPD)
            rep = B.account(name, os.path.join(ROOT, info["file"]), parent,
                            declared_base=G_ABPD,
                            instance_ids=info.get("instance_ids") or [])
            out["accounting"][name] = rep
            if os.path.abspath(parent) != os.path.abspath(G_ABPD):
                out["accounting"][name + ".hop_load"] = B.account(
                    name + ".hop_load", parent, G_ABPD, declared_base=G_ABPD,
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
# BX_birth + DEMO v7 (the product recipes THROUGH birthright)
# ===========================================================================

def _spec():
    from rvt.famgen import birthright as BR
    if not os.path.isfile(BIRTH_JSON):
        raise SystemExit(f"no {relp(BIRTH_JSON)} -- run `mine` first")
    return BR.read_birth_spec(BIRTH_JSON)


def _slim_birth_reports(reports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for r in reports:
        rep = r.get("report") or {}
        out.append({
            "family": r.get("family"),
            "n_added": r.get("n_added"),
            "verify": r.get("verify"),
            "topology": {k: (rep.get("topology") or {}).get(k)
                         for k in ("flip_classes", "n_flipped")},
            "types": rep.get("types"),
            "fields_set": (rep.get("fields") or {}).get("fields_set"),
            "deletion_prefix": (rep.get("fields") or {}).get(
                "deletion_prefix"),
            "indices": rep.get("indices"),
            "authored": rep.get("authored"),
        })
    return out


def build_bx_birth() -> Dict[str, Any]:
    """BX_birth: the B0 recipe verbatim (G_ABPD + ONE famgen panelboard +
    ONE instance; bisect_instance_bug chain + demo placement under
    famload_hostfix.corpus_symbol_form) with the famdoc authored THROUGH
    birthright -- OUR famdoc, OUR birth set, zero donors."""
    B = _bisect()
    rp = _rp()
    fbl = _fbl()
    from rvt.famgen import birthright as BR
    from rvt import famload_hostfix as HF
    from rvt.mutate import Document
    spec = _spec()
    rp._install_schema(G_ABPD)
    info: Dict[str, Any] = {"probe": "BX_birth", "axis": AXES["BX_birth"],
                            "base": relp(G_ABPD),
                            "recipe": "B0 (BXhf_f1i1) through "
                                      "birthright.enabled: bisect_instance_"
                                      "bug chain+place under famload_hostfix"
                                      ".corpus_symbol_form",
                            "birth_spec": spec.summary(),
                            "birth_spec_sha256": (spec.source or {}).get(
                                "sha256")}
    chain_dir = os.path.join(BUILD_DIR, "BX_birth_chain")
    if os.path.isdir(chain_dir):
        shutil.rmtree(chain_dir)
    outp = os.path.join(OUT_DIR, "BX_birth.rvt")
    with BR.enabled(spec) as br_ctx:
        with HF.corpus_symbol_form():
            model6 = B.demo_model()
            m1 = B.truncate_model(model6, 1)
            l1 = B.build_chain(G_ABPD, chain_dir, m1)
            f1 = B.chain_file(chain_dir, 1, "PP-1")
            e1 = B.place_instances(m1, f1, outp, G_ABPD,
                                   l1.get("_loaded") or {})
    info["birthright"] = _slim_birth_reports(br_ctx["reports"])
    if not info["birthright"]:
        raise RuntimeError("BX_birth: birthright never fired -- the factory "
                           "hook did not run")
    if not all((r.get("verify") or {}).get("ok")
               for r in info["birthright"]):
        raise RuntimeError("BX_birth: authored-vs-mined verify not ok")
    info["load"] = {"loads": [{k: v for k, v in ld.items()
                               if k in ("tag", "ok", "symbol_id", "family_id",
                                        "host_watermark", "out",
                                        "elements_added", "seconds")}
                              for ld in l1.get("loads") or []]}
    insts = e1.get("instances") or []
    info["equipment"] = {"instances": [{k: i.get(k) for k in
                                        ("tag", "elem_id", "symbol", "family",
                                         "n_dangling")} for i in insts]}
    info["instance_ids"] = [i["elem_id"] for i in insts]
    first = (insts or [{}])[0]
    info["symbol_id"] = first.get("symbol")
    info["family_id"] = first.get("family")
    dangling = [i for i in insts if (i.get("n_dangling") or 0) != 0]
    if len(insts) != 1 or dangling:
        raise RuntimeError(f"BX_birth: expected exactly 1 dangling-free "
                           f"instance, got {len(insts)} "
                           f"(dangling: {dangling})")
    info["immediate_parent"] = relp(f1)
    info["file"] = relp(outp)
    info["md5"] = md5_of(outp)
    # the B0 gates: product connector manager + corpus-lawful symbol form
    doc = Document.from_file(outp)
    cm = (doc.value(info["instance_ids"][0]) or {}).get("m_pConnectorManager")
    info["instance_connmgr"] = (cm.get("ptr_class") if isinstance(cm, dict)
                                else cm)
    forms = {}
    for sid in doc.ids_of_class("FamilySymbol"):
        v = doc.value(sid) or {}
        fam = doc.value(v.get("m_familyId") or -1) or {}
        if "PP-" in str(fam.get("m_name") or ""):
            forms[sid] = HF.assert_symbol_form(outp, sid)
    bad = [k for k, f in forms.items() if not f["ok"]]
    if bad or not forms:
        raise RuntimeError(f"BX_birth symbol form check failed: "
                           f"{bad or 'no PP- symbols found'}")
    info["symbol_form"] = {str(k): {"ok": f["ok"], "counts": f["counts"]}
                           for k, f in forms.items()}
    info["blob_proof"] = fbl.blob_proof(outp, G_ABPD)
    return info


def build_demo_v7() -> Dict[str, Any]:
    """DEMO_250v_room_v7: the user's exact prompt end-to-end through
    ``rvt.frontdoor.run`` with birthright enabled (the v3/v5 recipe + the
    authored birth set)."""
    B = _bisect()
    rp = _rp()
    fbl = _fbl()
    from rvt.famgen import birthright as BR
    from rvt import famload_hostfix as HF
    from rvt.mutate import Document
    spec = _spec()
    rp._install_schema(G_ABPD)
    import ifc_intent  # noqa: F401  (registers the demo build module)
    from rvt.frontdoor.build import load_ifc_room_module
    load_ifc_room_module()
    from rvt import frontdoor as FD
    demo_dir = os.path.join(BUILD_DIR, "demo_v7")
    if os.path.isdir(demo_dir):
        shutil.rmtree(demo_dir)
    outp = os.path.join(OUT_DIR, "DEMO_250v_room_v7.rvt")
    info: Dict[str, Any] = {"probe": "DEMO_250v_room_v7",
                            "axis": AXES["DEMO_250v_room_v7"],
                            "base": relp(G_ABPD), "prompt": DEMO_PROMPT,
                            "birth_spec": spec.summary(),
                            "birth_spec_sha256": (spec.source or {}).get(
                                "sha256")}
    with BR.enabled(spec) as br_ctx:
        with HF.corpus_symbol_form():
            req = FD.AuthorRequest(prompt=DEMO_PROMPT, out=demo_dir,
                                   stem="DEMO_250v_room_v7",
                                   no_handoff=True, quiet=True)
            r = FD.run(req)
    combined = (r.files or {}).get("combined")
    if not combined or not os.path.isfile(combined):
        raise RuntimeError(f"front door did not emit the combined file: "
                           f"{r.errors[:3]}")
    shutil.copyfile(combined, outp)
    info["frontdoor_status"] = r.status
    info["out_dir"] = relp(demo_dir)
    info["birthright"] = _slim_birth_reports(br_ctx["reports"])
    if not info["birthright"]:
        raise RuntimeError("DEMO v7: birthright never fired")
    if not all((x.get("verify") or {}).get("ok")
               for x in info["birthright"]):
        raise RuntimeError("DEMO v7: authored-vs-mined verify not ok")
    # the factory fires once per stage-F standalone .rfa AND once per
    # stage-L load; distinct family names = the loaded fleet
    info["n_families"] = len({x.get("family") for x in info["birthright"]})
    info["n_birthright_applications"] = len(info["birthright"])
    # instances + walls measured from the emitted bytes (above-base adds)
    T = rp._room()
    wm = T.host_watermark(G_ABPD)
    doc = Document.from_file(outp)
    inst_ids = [i for i in doc.ids_of_class("FamilyInstance") if i > wm]
    wall_ids = [i for i in doc.ids_of_class("Wall") if i > wm]
    info["instance_ids"] = inst_ids
    info["n_instances"] = len(inst_ids)
    info["n_walls"] = len(wall_ids)
    # per-instance reference resolution rides in the account regdiff
    # (registrations per instance id) -- see _gates
    # symbol form on every PP- symbol (the demo's own invariant)
    forms = {}
    for sid in doc.ids_of_class("FamilySymbol"):
        v = doc.value(sid) or {}
        fam = doc.value(v.get("m_familyId") or -1) or {}
        if "PP-" in str(fam.get("m_name") or ""):
            forms[sid] = HF.assert_symbol_form(outp, sid)
    bad = [k for k, f in forms.items() if not f["ok"]]
    if bad or not forms:
        raise RuntimeError(f"DEMO v7 symbol form check failed: "
                           f"{bad or 'no PP- symbols found'}")
    info["symbol_form_ok"] = {str(k): f["ok"] for k, f in forms.items()}
    info["immediate_parent"] = relp(G_ABPD)
    info["file"] = relp(outp)
    info["md5"] = md5_of(outp)
    info["blob_proof"] = fbl.blob_proof(outp, G_ABPD)
    return info


# ===========================================================================
# probes.json (the decision table)
# ===========================================================================

READING = {
    "CTRL FAIL": "round VOID (oracle/environment) -- interpret nothing",
    "T1v PASS + BX_birth PASS + v7 PASS": "THE CAMPAIGN CLOSES: the birth "
        "set is sufficient for our content AND our authored birth "
        "reproduces it -- birthright becomes the famgen emission default "
        "next; the instance gap is shut with zero donor bytes.",
    "T1v PASS + BX_birth FAIL": "the birth set is sufficient but our "
        "AUTHORED birth misses something the born shell has -- run "
        "`diff`: the authored-vs-mined field diff plus the mined "
        "exclusion list IS the finite gap list; close it constructor by "
        "constructor.",
    "T1v FAIL": "our content INTERACTS with the born shell (SUB_ALL "
        "accepted the same union in a project-donor body; a standalone-"
        "born body does not) -- bisect our axes inside the born shell "
        "(T1v_g/T1v_p/... singles) before trusting any authored birth.",
    "BX_birth PASS + v7 FAIL": "the single-panel authored birth passes "
        "but the 6-panel demo does not -- multi-unit propagation "
        "(chain-order, id-space, or per-unit birth block) is the "
        "remaining axis; bisect panel count.",
}


def write_probes_json(build_out: Dict[str, Any]) -> str:
    onething = {
        "T1v": "the vendor-born famdoc + OUR 35-element content union "
               "(registered in the born self-Family), famload + instance "
               "on G_ABPD.  The ONE thing vs T2a (PASS): our content "
               "rides the born body.",
        "BX_birth": "the B0 recipe (G_ABPD + ONE famgen panelboard + ONE "
                    "instance) with the famdoc AUGMENTED by the authored "
                    "birth set.  The ONE thing vs B0 (FAIL): the birth "
                    "set (zero donor bytes).",
        "DEMO_250v_room_v7": "the user's exact prompt through the real "
                             "front door with birthright enabled.  The "
                             "ONE thing vs DEMO v5 (FAIL): the birth set.",
    }
    expected = {
        "T1v": "PASS = birth set sufficient (T2a accepted the shell; "
               "SUB_ALL accepted the union in a donor body); FAIL = "
               "content interaction",
        "BX_birth": "the product bet: PASS closes the single-panel gap "
                    "with zero donors",
        "DEMO_250v_room_v7": "PASS closes the campaign",
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
            "file": f"experiments/birthright/{name}.rvt",
            "base": relp(G_ABPD),
            "kind": "probe",
            "axis": AXES[name],
            "n_families": info.get("n_families", 1),
            "n_instances": len(info.get("instance_ids") or []),
            "n_walls": info.get("n_walls", 0),
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
        "stream": "birthright (the sufficiency probe + the authored birth)",
        "tool": "tools/birthright_mine.py",
        "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "question": "is the template-birth set SUFFICIENT for our content "
                    "(T1v), and does famgen AUTHORING that birth set (zero "
                    "donor bytes) close the instance gap (BX_birth, DEMO "
                    "v7)?  [verdict #43: born famdocs PASS, ours FAIL]",
        "probes": probes,
        "reading_the_matrix": READING,
        "notes": ["every probe: validator 0 unexpected errors, 64-byte "
                  "0x0f3f blob on every unit (added units carry OUR "
                  "deterministic nonce -- machine-verified), coherent "
                  "four-registry census, references resolved",
                  "T1v embeds the vendor-born famdoc: DEV/PROOF-ONLY, "
                  "quarantined under experiments/ (zero donor bytes in "
                  "anything shipped)",
                  "BX_birth / DEMO v7 carry ZERO donor bytes: every birth "
                  "element re-authored by our writers from the mined "
                  "template_birth.json (adoptable laws/shapes carried; "
                  "identity/content authored fresh)"],
    }
    path = os.path.join(OUT_DIR, "probes.json")
    jdump(path, doc)
    log(f"probes.json -> {relp(path)} ({len(probes)} probes)")
    return path


# ===========================================================================
# verify + stage (rft_probe's staging law: controls FIRST, gate refusal)
# ===========================================================================

def verify() -> Dict[str, Any]:
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
                bp = fbl.blob_proof(f, G_ABPD)
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
    """probe_batch gate + stage: ONE batch, the G_ABPD control FIRST, then
    the probes in reading order T1v, BX_birth, DEMO v7."""
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
    controls = [pb.make_control(ledger, n, out_dir, source=G_ABPD)]
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
        "tool": "tools/birthright_mine.py (via tools/probe_batch.py "
                "primitives)",
        "law": ("every entry's declared base is ITSELF certified; the batch "
                "carries the G_ABPD control FIRST; control FAIL voids its "
                "probes"),
        "ledger": pb.rel(ledger.path),
        "control_count": len(controls),
        "controls": {os.path.basename(c.control_source or ""): c.staged_as
                     for c in controls},
        "note": "birthright: THE SUFFICIENCY PROBE + THE AUTHORED BIRTH.  "
                "Verdict #43 confirmed the birth law (born famdocs PASS "
                "our whole pipeline, famgen famdocs FAIL).  Reading order: "
                "T1v (is the birth set SUFFICIENT for our content?), "
                "BX_birth (our famdoc + OUR authored birth set, zero "
                "donors), DEMO_250v_room_v7 (the user's exact prompt "
                "through birthright).  Read experiments/birthright/"
                "probes.json reading_the_matrix.",
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

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("t1v")
    sub.add_parser("mine")
    b = sub.add_parser("build")
    b.add_argument("--only", help="comma-separated rung names")
    sub.add_parser("diff")
    sub.add_parser("verify")
    st = sub.add_parser("stage")
    st.add_argument("--only", help="comma-separated rung names to stage")
    args = ap.parse_args(argv)
    if args.cmd == "t1v":
        out = build(["T1v"])
        return 0 if not out["errors"] else 1
    if args.cmd == "mine":
        mine()
        return 0
    if args.cmd == "build":
        only = [s.strip() for s in args.only.split(",")] if args.only else None
        out = build(only)
        return 0 if not out["errors"] else 1
    if args.cmd == "diff":
        out = authored_vs_mined_diff()
        return 0 if out.get("ok") else 1
    if args.cmd == "verify":
        out = verify()
        return 0 if out["ok"] else 1
    if args.cmd == "stage":
        stage([s.strip() for s in args.only.split(",")]
              if args.only else None)
        return 0
    return 2


# ===========================================================================
# THE MINER -- born specimen -> template_birth.json (the birthright contract)
# ===========================================================================

#: self-Family obj fields the fields lane must NEVER adopt (ours by
#: construction: product identity, roster-derived registries, machinery
#: pointers, our-param-space lists, identity strings).  Recorded verbatim in
#: the spec as field_policy.exclude so the decision is inspectable.
SELF_FAMILY_EXCLUDE = (
    # product identity (the family IS our product)
    "m_id", "m_categoryId", "m_partType", "m_isWorkPlaneBased",
    "m_name", "m_path", "m_famDocGUID", "m_seekItemId", "m_omniClassCode",
    "m_classificationDescription", "m_dumpSymName", "m_familyNameKeyText",
    "m_structuralCodeName", "m_protectionAccessKey",
    # roster-derived registries (FamilyDoc.finalize / refresh_self_family_index)
    "m_familyIds", "m_nextAbsorbedIndex", "m_deletableElements",
    # types/params lanes + finalize-derived palette (our parameter id space)
    "m_pFamilyTypes", "m_familyParams", "m_cellList", "m_trivialParamIds",
    "m_lockedParameterIdsForDirectManipulation",
    # machinery pointers our constructor authors
    "m_pADoc", "m_oFamDoc", "m_docAccess", "m_oFamDimConstrMgr",
    # born-content references / vendor ballast
    "m_refs", "m_dbviewInfos", "m_oHostFaceGeomRef", "m_oDefaultStretchLine",
    "m_outOfFamilyRefs", "m_outOfFamilyHostIds", "m_outOfFamilyHostGrefs",
    "m_oFamilyReferenceIdxMgr", "m_oldCurveElemsWithBadSketchAndSP",
    "m_surrogateId", "m_ownerSymbolId", "m_regeneratingGroupId",
    "m_keyExtParamId", "m_famCatalogKeys",
)

#: adoptable-string vocabulary prefixes (interface tokens our writers
#: already emit: Forge typeIds, revit local-param ids)
_VOCAB_PREFIXES = ("autodesk.", "revit.")

#: the layout-law 12 separators (experiments/layout/layout_diff.json
#: headline) -- their born-side values are recorded explicitly in the spec
SEPARATORS = (
    "cell_dup_identity_groups", "cell_no_materials_group",
    "hdr_deletion_elements_only", "hdr_deletion_lacks_category",
    "sf_absorbed_dense", "sf_category_is_ours_electrical",
    "sf_locked_no_bip", "sf_partType_set", "sf_predefinedLimitIdx_small",
    "sf_refTypeIds_empty", "sf_single_type_pair", "sf_type_idx_zero",
)


def _tagging_decoder(schema):
    """An ObjectDecoder that wraps every POSITIVE ElementId-typed value as
    ``{"__eid__": v}`` during the byte decode (the rft_probe _remap_decoder
    hook, tagging instead of remapping).  Negative ids (built-in category /
    BIP ids) and -1 stay plain ints -- they are LAWS, not references."""
    from rvt.objects import ObjectDecoder

    class TagDecoder(ObjectDecoder):
        def __init__(self, s):
            super().__init__(s)
            self.n_tagged = 0

        def _decode_value_class(self, rd, type_id, queue, state, path):
            v = super()._decode_value_class(rd, type_id, queue, state, path)
            if (type_id == self.id_ElementId and isinstance(v, int)
                    and not isinstance(v, bool) and v > 0):
                self.n_tagged += 1
                return {"__eid__": v}
            return v

    return TagDecoder(schema)


_GUID_RE = None


def _guid_re():
    global _GUID_RE
    if _GUID_RE is None:
        import re
        _GUID_RE = re.compile(
            r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
    return _GUID_RE


#: field keys whose string values are SCHEMA VOCABULARY (pointer class
#: names) -- authoring them would corrupt the record encode
_CLASSNAME_KEYS = ("ptr_class", "classref")


def _name_stem(s: str) -> Optional[str]:
    """The vocabulary STEM of an unspaced product token: the leading ASCII
    alpha run (>= 8 chars) of a string with no spaces / separators --
    'SecretInternalLinAngDimStyle5p4736185' -> the stem, so the author lane
    can emit stem + OUR suffix (the product's naming convention preserved,
    the specimen's token authored away).  Prose / paths return None."""
    if any(c in s for c in (" ", "\\", "/", ":", ".")):
        return None
    i = 0
    while i < len(s) and (s[i].isalpha() and s[i].isascii()):
        i += 1
    return s[:i] if i >= 8 else None


def _adopt_filter(node: Any, census: Dict[str, Any], path: str = "",
                  class_names: Optional[set] = None, key: str = "") -> Any:
    """The zero-donor adoption line applied to a mined field model:
    laws/shapes carried, references symbolic, identity/content -> AUTHOR
    slots.  ``census`` counts every decision."""
    if isinstance(node, dict):
        if set(node.keys()) == {"__eid__"}:
            census["refs"] = census.get("refs", 0) + 1
            return node
        return {k: _adopt_filter(v, census, f"{path}.{k}", class_names, k)
                for k, v in node.items()}
    if isinstance(node, list):
        return [_adopt_filter(v, census, f"{path}[{i}]", class_names, key)
                for i, v in enumerate(node)]
    if isinstance(node, bool) or node is None:
        census["scalars"] = census.get("scalars", 0) + 1
        return node
    if isinstance(node, (int, float)):
        census["scalars"] = census.get("scalars", 0) + 1
        return node
    if isinstance(node, str):
        if _guid_re().match(node):
            census["authored_guids"] = census.get("authored_guids", 0) + 1
            census.setdefault("author_paths", []).append(path)
            return {"__author__": {"kind": "guid"}}
        if (len(node) <= 24 or node.startswith(_VOCAB_PREFIXES)
                or key in _CLASSNAME_KEYS
                or (class_names and node in class_names)):
            census["strings_adopted"] = census.get("strings_adopted", 0) + 1
            return node
        census["authored_strings"] = census.get("authored_strings", 0) + 1
        census.setdefault("author_paths", []).append(path)
        census.setdefault("authored_string_samples", [])
        if len(census["authored_string_samples"]) < 40:
            census["authored_string_samples"].append(node[:60])
        slot: Dict[str, Any] = {"kind": "string", "shape_len": len(node)}
        stem = _name_stem(node)
        if stem:
            slot["shape_stem"] = stem
        return {"__author__": slot}
    if isinstance(node, (bytes, bytearray)):
        census["authored_bytes"] = census.get("authored_bytes", 0) + 1
        census.setdefault("author_paths", []).append(path)
        return {"__author__": {"kind": "bytes", "shape_len": len(node)}}
    census.setdefault("odd_types", []).append(f"{path}: {type(node).__name__}")
    return {"__author__": {"kind": "opaque", "shape": type(node).__name__}}


def _walk_eids(node: Any, out: set) -> None:
    if isinstance(node, dict):
        if set(node.keys()) == {"__eid__"}:
            out.add(int(node["__eid__"]))
            return
        for v in node.values():
            _walk_eids(v, out)
    elif isinstance(node, list):
        for v in node:
            _walk_eids(v, out)


def _our_doc():
    """The B0 famdoc (the demo's PP-1) at a fixed dev id base -- the
    document whose roster defines 'classes famgen authors'."""
    rp = _rp()
    FB = rp._fb()
    return FB.our_product(1000000).doc


def mine() -> Dict[str, Any]:
    """Mine the born specimen (the vendor standalone .rfa) into
    ``experiments/birthright/template_birth.json`` -- see the module
    docstring for the partition + adoption rules.  Emits the mining report
    alongside (drops, shortfalls, identity census)."""
    rp = _rp()
    from rvt.families import FamilyIndex
    t0 = time.time()
    os.makedirs(OUT_DIR, exist_ok=True)
    rfa = rp.VENDOR_RFA
    els, facts = rp.load_rft_elements(rfa)          # roster + owners (proven)
    by_id = {e.elem_id: e for e in els}
    sf_id = facts["self_family"]
    idx = FamilyIndex(rfa)
    dec = _tagging_decoder(idx.schema)
    recs = idx.unit_records(0)

    def tagged(seq: int, eid: int):
        r = recs.get(seq, {}).get(eid)
        if r is None:
            return None
        o = dec.decode_record(r.class_id, r.payload)
        return o.value if o else None

    # ---- our famdoc: the classes famgen authors + frame ownership --------
    ours = _our_doc()
    our_classes: Dict[str, int] = {}
    for e in ours.elements:
        our_classes[e.class_name] = our_classes.get(e.class_name, 0) + 1
    our_owner_by_class = {
        e.class_name: ("self_family" if e.owner_id == ours.self_family.elem_id
                       else ("top" if (e.owner_id or 0) <= 0 else "other"))
        for e in ours.elements}

    born_classes = dict(facts["class_histogram"])

    # ---- the frame-role map: born singleton -> our singleton -------------
    born_by_class: Dict[str, List[int]] = {}
    for e in els:
        born_by_class.setdefault(e.class_name, []).append(e.elem_id)
    frame_map: Dict[int, str] = {sf_id: "self_family"}
    frame_roles: Dict[str, Dict[str, Any]] = {
        "Family": {"born_id": sf_id, "role": "self_family"}}
    for cls, our_n in our_classes.items():
        if cls == "Family":
            continue
        if our_n == 1 and len(born_by_class.get(cls, [])) == 1:
            bid = born_by_class[cls][0]
            frame_map[bid] = f"role:{cls}"
            frame_roles[cls] = {"born_id": bid, "role": f"role:{cls}"}

    # ---- the birth-candidate partition -----------------------------------
    candidates = [e for e in els
                  if our_classes.get(e.class_name, 0) == 0]
    candidate_ids = {e.elem_id for e in candidates}
    shortfall = {c: n - our_classes.get(c, 0)
                 for c, n in born_classes.items()
                 if our_classes.get(c, 0) > 0 and n > our_classes.get(c, 0)}

    # tagged field models for every candidate (header/obj/rep)
    models: Dict[int, Dict[str, Any]] = {}
    for e in candidates:
        models[e.elem_id] = {
            "header": tagged(101, e.elem_id),
            "obj": tagged(102, e.elem_id),
            "rep": (tagged(103, e.elem_id) if e.rep is not None else None),
        }

    # ref-closure drop iteration: a candidate whose refs/owner reach an
    # element that is neither a candidate nor frame-mapped is DROPPED (with
    # the blocking id recorded) -- the honest v1 line.
    dropped: Dict[int, Dict[str, Any]] = {}
    changed = True
    while changed:
        changed = False
        live = candidate_ids - set(dropped)
        for eid in sorted(live):
            e = by_id[eid]
            refs: set = set()
            m = models[eid]
            _walk_eids(m["header"], refs)
            _walk_eids(m["obj"], refs)
            _walk_eids(m["rep"], refs)
            if (e.owner_id or 0) > 0:
                refs.add(e.owner_id)
            blockers = sorted(r for r in refs
                              if r not in live and r not in frame_map
                              and r != eid)
            if blockers:
                dropped[eid] = {
                    "class": e.class_name,
                    "blocking_refs": [
                        {"id": b,
                         "class": (by_id[b].class_name if b in by_id
                                   else "OUTSIDE-ROSTER"),
                         "why": ("dropped-candidate" if b in candidate_ids
                                 else ("excluded-class" if b in by_id
                                       else "not-in-roster"))}
                        for b in blockers[:6]],
                }
                changed = True

    birth_ids = sorted(candidate_ids - set(dropped))
    birth_els = [by_id[i] for i in birth_ids]

    # ---- adoption filter over the surviving birth elements ---------------
    class_names = set(idx.schema.by_name)
    # the born self-Family's absorbed index per element (a counter SHAPE:
    # reproducing the template's index-history gaps is authorable)
    sf_obj_raw = tagged(102, sf_id)
    born_index: Dict[int, int] = {}
    for p in (((sf_obj_raw or {}).get("m_familyIds") or {}).get("value")
              or {}).get("m_data") or []:
        eid = p.get("m_elementId")
        if isinstance(eid, dict):
            eid = eid.get("__eid__")
        if isinstance(eid, int):
            born_index[eid] = p.get("m_index")
    census: Dict[str, Any] = {}
    entries: List[Dict[str, Any]] = []
    for e in birth_els:
        m = models[e.elem_id]
        owner = e.owner_id if (e.owner_id or 0) > 0 else -1
        if owner in frame_map:
            owner_out: Any = frame_map[owner]
        elif owner in set(birth_ids):
            owner_out = {"__eid__": owner}
        else:
            owner_out = -1
        entries.append({
            "born_id": e.elem_id,
            "class": e.class_name,
            "owner": owner_out,
            "absorbed_index": born_index.get(e.elem_id),
            "header": _adopt_filter(m["header"], census,
                                    f"{e.elem_id}.hdr", class_names),
            "obj": _adopt_filter(m["obj"], census, f"{e.elem_id}.obj",
                                 class_names),
            "rep": (_adopt_filter(m["rep"], census, f"{e.elem_id}.rep",
                                  class_names)
                    if m["rep"] is not None else None),
        })
    author_paths = census.pop("author_paths", [])

    # rewrite frame-mapped refs inside the models as role strings
    def rolify(node):
        if isinstance(node, dict):
            if set(node.keys()) == {"__eid__"} and node["__eid__"] in frame_map:
                return {"__role__": frame_map[node["__eid__"]]}
            return {k: rolify(v) for k, v in node.items()}
        if isinstance(node, list):
            return [rolify(v) for v in node]
        return node

    entries = [dict(e, header=rolify(e["header"]), obj=rolify(e["obj"]),
                    rep=rolify(e["rep"]) if e["rep"] is not None else None)
               for e in entries]

    # ---- the self-Family residue (fields lane material) ------------------
    sf_obj = tagged(102, sf_id)
    sf_hdr = tagged(101, sf_id)
    sf_census: Dict[str, Any] = {}
    fields: Dict[str, Any] = {}
    fields_excluded: Dict[str, str] = {}
    for k, v in (sf_obj or {}).items():
        if k in SELF_FAMILY_EXCLUDE:
            fields_excluded[k] = "policy"
            continue
        refs: set = set()
        _walk_eids(v, refs)
        unresolved = [r for r in refs
                      if r not in frame_map and r not in set(birth_ids)]
        if unresolved:
            fields_excluded[k] = f"refs outside birth set: {unresolved[:4]}"
            continue
        fields[k] = rolify(_adopt_filter(v, sf_census, f"sf.{k}",
                                         class_names))
    # header residue: the deletion prefix (non-roster entries, in order) +
    # scalar header fields
    hdr_fields: Dict[str, Any] = {}
    for k, v in (sf_hdr or {}).items():
        if isinstance(v, (bool, int, float)) or v is None:
            hdr_fields[k] = v
    par = ((sf_hdr or {}).get("m_parents") or {}).get("value") or {}
    dele = par.get("m_deletion") or []
    roster_set = {e.elem_id for e in els}
    deletion_prefix = []
    for x in dele:
        xv = x["__eid__"] if isinstance(x, dict) and "__eid__" in x else x
        if not (isinstance(xv, int) and xv in roster_set):
            deletion_prefix.append(xv)

    # ---- the born type table (blank-pair law) ----------------------------
    ftt = ((sf_obj or {}).get("m_pFamilyTypes") or {}).get("value") or {}
    pairs = ftt.get("m_pairs") or []
    type_names = [(p.get("name") if isinstance(p, dict) else None)
                  for p in pairs]
    type_table = {
        "n_pairs": len(pairs),
        "m_idx": ftt.get("m_idx"),
        "names": type_names,
        "blank_pair_first": bool(type_names
                                 and str(type_names[0] or "") == " "),
        "law": "the born table opens with the blank ' ' current-values "
               "pair; m_idx names the current REAL type (types5 law, "
               "confirmed standalone)",
    }

    # ---- the 12 separators' born-side values -----------------------------
    def _cell_groups(obj):
        cells = (((obj.get("m_cellList") or {}).get("value") or {})
                 .get("m_cells") or [])
        for c in cells:
            cv = (c.get("value") or {}) if isinstance(c, dict) else {}
            sp = cv.get("m_sortedParams")
            if isinstance(sp, list):
                return sp
        return []

    groups = _cell_groups(sf_obj or {})
    gkeys = [str((g.get("m_groupTypeId") or {}).get("m_typeId"))
             for g in groups]
    locked = (sf_obj or {}).get(
        "m_lockedParameterIdsForDirectManipulation") or []
    locked_plain = [x["__eid__"] if isinstance(x, dict) and "__eid__" in x
                    else x for x in locked]
    fam_pairs = ((sf_obj or {}).get("m_familyIds") or {}).get("value") or {}
    fam_idx = sorted(p.get("m_index") for p in fam_pairs.get("m_data") or []
                     if isinstance(p.get("m_index"), int))
    separators_born = {
        "cell_dup_identity_groups": (len([k for k in gkeys
                                          if k.endswith("identityData-1.0.0")])
                                     > 1),
        "cell_no_materials_group": not any(
            k.endswith("materials-1.0.0") for k in gkeys),
        "cell_group_keys": [k.rsplit(":", 1)[-1] for k in gkeys],
        "hdr_deletion_prefix": deletion_prefix,
        "hdr_deletion_elements_only": not deletion_prefix,
        "sf_nextAbsorbedIndex": (sf_obj or {}).get("m_nextAbsorbedIndex"),
        "sf_absorbed_dense": fam_idx == list(range(len(fam_idx))),
        "sf_familyIds": {"n": len(fam_idx),
                         "max_index": (fam_idx[-1] if fam_idx else None),
                         "next_equals_max_plus_1":
                             ((sf_obj or {}).get("m_nextAbsorbedIndex")
                              == (fam_idx[-1] + 1 if fam_idx else 0)),
                         "law": "the born index space carries HISTORY GAPS "
                                "(sparse indices), next = max + 1"},
        "sf_category": ((sf_obj or {}).get("m_categoryId")),
        "sf_locked_has_bip": any(isinstance(x, int) and x < 0
                                 for x in locked_plain),
        "sf_locked": locked_plain,
        "sf_partType": (sf_obj or {}).get("m_partType"),
        "sf_predefinedLimitIdx": (sf_obj or {}).get("m_predefinedLimitIdx"),
        "sf_refTypeIds": (sf_obj or {}).get("m_refTypeIds"),
        "sf_type_pairs": len(pairs),
        "sf_type_idx": ftt.get("m_idx"),
    }

    # ---- ownership topology (the frame lane) -----------------------------
    born_owner_by_class: Dict[str, Dict[str, int]] = {}
    for e in els:
        o = by_id.get(e.owner_id)
        key = ("self_family" if e.owner_id == sf_id
               else (o.class_name if o else "top"))
        d = born_owner_by_class.setdefault(e.class_name, {})
        d[key] = d.get(key, 0) + 1
    topology = {
        "born_owner_by_class": born_owner_by_class,
        "our_owner_by_class": our_owner_by_class,
        "self_family_owned_ours_top": sorted(
            c for c, d in born_owner_by_class.items()
            if our_owner_by_class.get(c) == "top"
            and max(d, key=d.get) == "self_family"),
        "law": "the born famdoc's self-Family OWNS the frame (UnitsElem, "
               "the view chain, datums); our writer leaves them top-level "
               "-- the topology lane flips ours to the born shape",
    }

    # ---- identity census -------------------------------------------------
    identity = {
        "authored_guids": census.get("authored_guids", 0)
                          + sf_census.get("authored_guids", 0),
        "authored_strings": census.get("authored_strings", 0)
                            + sf_census.get("authored_strings", 0),
        "authored_bytes": census.get("authored_bytes", 0)
                          + sf_census.get("authored_bytes", 0),
        "policy": "GUIDs -> fresh uuid4 at author time; long non-vocabulary "
                  "strings -> our own strings; blobs -> empty (the unit "
                  "footer blob is authored separately by the writer)",
        "vocabulary_prefixes": list(_VOCAB_PREFIXES),
        "sample_authored_strings": census.get("authored_string_samples", []),
    }

    spec = {
        "version": 2,
        "source": {
            "rfa": relp(rfa), "sha256": rp.sha256_of(rfa),
            "species": "Revit-BORN standalone .rfa (desktop-saved; the "
                       "closest born specimen on hand -- an .rft, when "
                       "acquired, re-mines through this same tool)",
            "mining": "DEV/PROOF-ONLY: the specimen is MINING material; "
                      "every value in this spec is either an adoptable "
                      "law/shape, a symbolic reference, or an AUTHOR slot "
                      "-- zero donor identity is carried",
            "tool": "tools/birthright_mine.py mine",
            "mined": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        },
        "famdoc": {
            "n_records": len(els),
            "self_family_id": sf_id,
            "category_id": facts.get("category"),
            "part_type": facts.get("part_type"),
            "class_histogram": born_classes,
            "self_family_fields": fields,
            "self_family_header": hdr_fields,
            "layout": {},
        },
        "type_table": type_table,
        "separators_born": separators_born,
        "topology": topology,
        "identity": identity,
        "field_policy": {
            "exclude_self_family": sorted(SELF_FAMILY_EXCLUDE),
            "excluded_with_reason": fields_excluded,
            "deletion_prefix": deletion_prefix,
        },
        "birth_elements": entries,
        "birth_partition": {
            "rule": "birth = born elements of classes famgen never authors "
                    "(ours_count == 0), closed under references: an element "
                    "whose refs/owner reach outside {birth set + frame "
                    "roles + self-Family} is dropped (recorded)",
            "our_classes": our_classes,
            "n_candidates": len(candidates),
            "n_birth": len(birth_ids),
            "n_dropped": len(dropped),
            "count_shortfall_overlapping_classes": shortfall,
            "frame_roles": frame_roles,
        },
    }
    jdump(BIRTH_JSON, spec)
    report = {
        "tool": "tools/birthright_mine.py mine",
        "seconds": round(time.time() - t0, 1),
        "spec": relp(BIRTH_JSON),
        "born": {"elements": len(els), "classes": len(born_classes)},
        "birth": {"elements": len(birth_ids),
                  "classes": sorted({e.class_name for e in birth_els}),
                  "class_counts": {c: sum(1 for e in birth_els
                                          if e.class_name == c)
                                   for c in sorted({e.class_name
                                                    for e in birth_els})}},
        "dropped": {str(k): v for k, v in sorted(dropped.items())},
        "dropped_by_class": {},
        "count_shortfall_overlapping_classes": shortfall,
        "adoption_census": {"birth_elements": census,
                            "self_family": sf_census},
        "n_author_slots_paths": len(author_paths),
        "separators_born": separators_born,
        "topology_flips": topology["self_family_owned_ours_top"],
        "fields_lane_keys": sorted(fields),
        "fields_excluded": fields_excluded,
    }
    for v in dropped.values():
        report["dropped_by_class"][v["class"]] = \
            report["dropped_by_class"].get(v["class"], 0) + 1
    jdump(MINING_REPORT, report)
    log(f"mined {len(birth_ids)}/{len(candidates)} birth elements "
        f"({len(dropped)} dropped), {len(fields)} self-Family residue "
        f"fields -> {relp(BIRTH_JSON)} "
        f"({os.path.getsize(BIRTH_JSON) // 1024} KiB, "
        f"{report['seconds']}s)")
    return report


def authored_vs_mined_diff() -> Dict[str, Any]:
    """THE MACHINE DIFF deliverable: build the B0 famdoc, apply birthright,
    and field-diff the authored birth against the mined spec (equality
    modulo identity: references through the id map, author slots authored
    fresh).  Also re-proves the roundtrip encode of the augmented document.
    Writes ``experiments/birthright/authored_vs_mined_diff.json``."""
    rp = _rp()
    from rvt.famgen import birthright as BR
    rp._install_schema(G_ABPD)
    t0 = time.time()
    spec = _spec()
    doc = _our_doc()
    n_before = len(doc.elements)
    rep = BR.apply_birthright(doc, spec)
    idmap = rep.pop("_idmap", {}) or {}
    ver = BR.birth_verify(doc, spec, idmap, rep.get("roles") or {})
    rt = doc.roundtrip()
    rt_fail = (rt or {}).get("failures")
    out = {
        "tool": "tools/birthright_mine.py diff",
        "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "spec": relp(BIRTH_JSON),
        "spec_source_sha256": (spec.source or {}).get("sha256"),
        "doc": {"n_elements_before": n_before,
                "n_elements_after": len(doc.elements),
                "family": getattr(doc, "name", "?")},
        "lanes": {
            "roster": {k: (rep.get("roster") or {}).get(k)
                       for k in ("n_added", "id_range", "class_histogram")},
            "topology": rep.get("topology"),
            "types": rep.get("types"),
            "fields": rep.get("fields"),
            "indices": rep.get("indices"),
            "authored": rep.get("authored"),
        },
        "verify": {"ok": ver["ok"], "counts": ver["counts"],
                   "n_elements": ver["n_elements"],
                   "n_mismatches": len(ver["mismatches"]),
                   "mismatches_first_40": ver["mismatches"][:40]},
        "roundtrip_encode": {"failures": rt_fail,
                             "ok": not rt_fail},
        "equality_law": "field-model equality MODULO IDENTITY: adoptable "
                        "laws/shapes byte-equal; every element reference "
                        "equals the id-map image; every identity slot "
                        "(GUIDs, long strings, blobs) AUTHORED fresh -- "
                        "counted, never compared to the specimen",
        "ok": bool(ver["ok"] and not rt_fail),
        "seconds": round(time.time() - t0, 1),
    }
    jdump(DIFF_JSON, out)
    log(f"diff -> {relp(DIFF_JSON)} (ok={out['ok']}: "
        f"{ver['counts']} over {ver['n_elements']} elements, "
        f"roundtrip {'clean' if not rt_fail else 'FAILURES'})")
    return out


if __name__ == "__main__":
    raise SystemExit(main())
