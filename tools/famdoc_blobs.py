#!/usr/bin/env python
"""famdoc_blobs.py -- THE BLOB-CARRYING FAMDOC BISECTION (famdoc-blobs
stream, 2026-08-05).

WHY THIS LADDER EXISTS (genesis-audit VERDICTS #36/#37).  The envelope
round (batch 42) ended the presence hunt: Autodesk's open-time audit
requires the 0x0f3f 64-byte per-unit footer blob to be PRESENT on any unit
an instance walks into, and does NOT verify its content (E1b: a random
64-byte blob passes).  The fix is in core (``factory.build_family_save_unit``
emits the deterministic nonce; both loaders ride it).  But DEMO v5 -- our
generated famdoc content WITH blobs -- still FAILS, so the blob is
NECESSARY, NOT SUFFICIENT: our famdoc CONTENT carries a residual defect.
CRITICALLY, batch 37's famdoc hybrid bisection is VOID for content
attribution: every hybrid carried an EMPTY blob, which alone fails any
instanced unit.  The bisection design was right; this tool RE-RUNS IT WITH
BLOBS.

THE LADDER (staging/reading order = maximum information first):

  B7   the H7 recipe rebuilt: the Autodesk M_Concrete-Square-Column famdoc
       (id-rebased only) famload-loaded into its own rst sample + ONE
       template instance -- NOW blob-carrying.  The anchor: E1b proved
       native-famdoc + registration + instance + PRESENT blob passes under
       the H12 byte-copy machinery; B7 asks the same question of the
       famload machinery (authored host flavour + unit re-encode + rebase).
  B0   the product-shape anchor: G_ABPD + ONE famgen panelboard family
       (the demo's PP-1) + ONE instance -- the BXhf_f1i1 recipe verbatim
       (famgen loader chain under famload_hostfix.corpus_symbol_form, the
       demo's own stage_equipment placement), rebuilt through the fixed
       writer.  B0 PASS => the demo path merely needs propagation: rebuild
       DEMO v6 + acceptance immediately.
  B1   the H1 recipe + blob: B7's famdoc + OUR GEOMETRY subtree
       (ExtrusionElem + VarSketch + 4 CurveElems + SketchPlane).  Prime
       prior (famdoc_diff.json: m_geomSteps/m_pGeomTable differ on the
       famdoc's OWN form elements).
  B2   + OUR PARAMETER/TYPE layer.       B3  + OUR REFERENCE/DATUM layer.
  B4   + OUR VIEW constellation.         B5  + OUR CONNECTOR layer.
  B6   B7's document with the DONOR's OWN inline ADocument carried.

Every hybrid recipe is ``tools/famdoc_bisect.py``'s own machinery
(imported, never edited) with its output dirs repointed into THIS stream's
territory; the ONE new ingredient everywhere is the fixed writer stamping
the 64-byte 0x0f3f blob -- and this tool MACHINE-VERIFIES that on every
emitted file: every save unit of every probe (and of every intermediate
load file) must carry a 64-byte blob, the ADDED unit's blob must
BYTE-MATCH ``famdoc_adoc.build_footer`` recomputed from the unit's own
seq-102 segment (proving OUR deterministic nonce -- zero donor bytes), and
any raw-splice path that bypassed the writer would fail the census.

PROOF-ONLY: B1..B7 embed Autodesk sample content and stay quarantined in
experiments/ (zero donors in shipped output); the staged batch is the
certified probe mechanism.  STAGE ONLY -- the orchestrator uploads.

USAGE (repo root)::

    .venv/bin/python tools/famdoc_blobs.py build            # all 8 probes
    .venv/bin/python tools/famdoc_blobs.py build --only B7,B0
    .venv/bin/python tools/famdoc_blobs.py verify           # re-run gates
    .venv/bin/python tools/famdoc_blobs.py stage            # probe_batch + 2 controls

TERRITORY: this file, ``experiments/famdoc_blobs/**``,
``tests/test_famdoc_blobs.py``, ``docs/inbox/famdoc-blobs.md``, plus the
staging copies probe_batch itself writes under ``experiments/acceptance/``
(its designed output).  IMPORTS (never edits): tools/famdoc_bisect.py,
tools/bisect_instance_bug.py, tools/probe_batch.py, rvt.famload_hostfix,
rvt.famgen.famdoc_adoc, rvt.partitions.  No Autodesk install dirs, no
browser, no full-suite runs.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import importlib.util
import json
import os
import re
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

OUT_DIR = os.path.join(ROOT, "experiments", "famdoc_blobs")
BUILD_DIR = os.path.join(OUT_DIR, "_build")
H_DIR = os.path.join(OUT_DIR, "_h")          # famdoc_bisect's repointed output
ACCT = os.path.join(OUT_DIR, "accounting.json")

RST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
G_ABPD = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "compose",
                      "G_ABPD.rvt")
DEMO_PROMPT = "an electrical room rated for 250V with 6 panels"

#: staging/reading order = maximum information first
LADDER = ("B7", "B0", "B1", "B2", "B3", "B4", "B5", "B6")

#: which famdoc_bisect rung each hybrid B-rung rebuilds (B0 has its own path)
H_OF = {"B7": "H7", "B1": "H1", "B2": "H2", "B3": "H3", "B4": "H4",
        "B5": "H5", "B6": "H6"}

AXES = {
    "B7": "control-A with blob: the Autodesk famdoc (id-rebased only) "
          "through famload + template instance",
    "B0": "control-B with blob: the PRODUCT shape (G_ABPD + ONE famgen "
          "family + ONE instance, the BXhf_f1i1 recipe)",
    "B1": "our GEOMETRY subtree added (+ blob)",
    "B2": "our PARAMETER/TYPE layer added (+ blob)",
    "B3": "our REFERENCE/DATUM layer added (+ blob)",
    "B4": "our VIEW constellation added (+ blob)",
    "B5": "our CONNECTOR layer added (+ blob)",
    "B6": "control-A with the donor's OWN inline ADocument carried (+ blob)",
}


def log(msg: str) -> None:
    print(f"[blobs] {msg}", flush=True)


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


def _fb():
    """tools/famdoc_bisect.py with its output dirs repointed into THIS
    stream's territory (module attrs only -- the file is never edited; the
    famdoc-bisect stream's own emitted evidence is never touched)."""
    import famdoc_bisect as FB
    FB.OUT_DIR = H_DIR
    FB.BUILD_DIR = os.path.join(H_DIR, "_build")
    return FB


def _bisect():
    import bisect_instance_bug as B
    return B


def _pb():
    spec = importlib.util.spec_from_file_location(
        "_blobs_probe_batch", os.path.join(HERE, "probe_batch.py"))
    pb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pb)
    return pb


# ===========================================================================
# the blob proof (the ONE new gate of this round -- machine, per file)
# ===========================================================================

def unit_footer_census(path: str, *, with_data: bool = False) -> Dict[str, Any]:
    """Every save unit of every ``Partitions/*`` stream of ``path``:
    (stream, index, guid, footer blob length), plus -- with ``with_data`` --
    the per-unit seq-102 segment bytes for the nonce recomputation."""
    from rvt.container import open_rvt
    from rvt.partitions import StreamWalker
    units: List[Dict[str, Any]] = []
    seg102: Dict[str, bytes] = {}
    with open_rvt(path) as f:
        names = sorted(s.name for s in f.streams()
                       if s.name.startswith("Partitions/"))
        for nm in names:
            w = StreamWalker(f.logical(nm), inflate=with_data,
                             keep_data=with_data)
            if w.errors:
                raise RuntimeError(f"{relp(path)} {nm}: walker errors "
                                   f"{w.errors[:3]}")
            for u in w.units:
                g = str(uuid.UUID(bytes_le=u.guid)) if u.guid else None
                units.append({"stream": nm, "index": u.index, "guid": g,
                              "blob_len": len(u.footer_blob),
                              "blob_sha256": hashlib.sha256(
                                  u.footer_blob).hexdigest() if u.footer_blob
                              else None})
                if with_data and g is not None:
                    blocks = w.blocks[u.first_block:u.first_block + u.n_blocks]
                    buf = bytearray()
                    for b in sorted((b for b in blocks if b.seq == 102),
                                    key=lambda b: b.hdr_offset):
                        buf.extend(b.data or b"")
                    seg102[g] = bytes(buf)
    out: Dict[str, Any] = {"file": relp(path), "units_total": len(units),
                           "blob_len_histogram": {}, "units": units}
    for u in units:
        k = str(u["blob_len"])
        out["blob_len_histogram"][k] = out["blob_len_histogram"].get(k, 0) + 1
    if with_data:
        out["_seg102"] = seg102
    return out


def blob_proof(path: str, base_path: str) -> Dict[str, Any]:
    """The per-file blob gate: every unit carries a 64-byte 0x0f3f blob, the
    ADDED unit(s) (guid diff vs ``base_path``) carry OUR deterministic nonce
    (``famdoc_adoc.build_footer`` recomputed from the unit's own seq-102
    segment, byte-equal).  Raises on any violation -- a probe with an empty
    or foreign blob never leaves the build."""
    from rvt.famgen.famdoc_adoc import FOOTER_BLOB_LEN, build_footer
    child = unit_footer_census(path, with_data=True)
    base = unit_footer_census(base_path)
    seg102 = child.pop("_seg102")
    base_guids = {u["guid"] for u in base["units"]}
    added = [u for u in child["units"] if u["guid"] not in base_guids]
    bad = [u for u in child["units"] if u["blob_len"] != FOOTER_BLOB_LEN]
    if bad:
        raise RuntimeError(
            f"{relp(path)}: {len(bad)} unit(s) without a {FOOTER_BLOB_LEN}-byte "
            f"0x0f3f blob (the verdict-#36 voiding condition): "
            f"{[(u['stream'], u['index'], u['blob_len']) for u in bad[:4]]}")
    nonce_checks = []
    for u in added:
        expected = build_footer(guid=u["guid"], payload=seg102.get(u["guid"], b""))
        ok = hashlib.sha256(expected).hexdigest() == u["blob_sha256"]
        nonce_checks.append({"guid": u["guid"], "stream": u["stream"],
                             "index": u["index"], "nonce_match": ok,
                             "seg102_bytes": len(seg102.get(u["guid"], b""))})
        if not ok:
            raise RuntimeError(
                f"{relp(path)} unit {u['index']} ({u['guid']}): footer blob is "
                f"NOT our deterministic nonce (build_footer over the unit's own "
                f"seq-102 segment) -- a bypassing splice or donor bytes; refused")
    return {"file": child["file"], "base": relp(base_path),
            "units_total": child["units_total"],
            "blob_len_histogram": child["blob_len_histogram"],
            "units_added_vs_base": len(added),
            "added_units": nonce_checks,
            "all_units_64B": True,
            "added_nonce_verified": all(c["nonce_match"] for c in nonce_checks),
            "law": "verdict #36: the audit needs the 64-byte 0x0f3f blob "
                   "PRESENT on any instanced unit (content not verified -- "
                   "E1b); ours is the deterministic sha512 nonce, zero donor "
                   "bytes"}


# ===========================================================================
# builders
# ===========================================================================

def build_hybrid(name: str) -> Dict[str, Any]:
    """B7 / B1..B6: the famdoc_bisect rung rebuilt through the fixed writer,
    emitted under this stream's name."""
    FB = _fb()
    import ifc_intent as T
    hname = H_OF[name]
    wm = T.host_watermark(RST)
    os.makedirs(H_DIR, exist_ok=True)
    info = FB.build_probe(hname, wm)
    src = os.path.join(H_DIR, f"{hname}.rvt")
    dst = os.path.join(OUT_DIR, f"{name}.rvt")
    os.replace(src, dst)
    info["probe"] = name
    info["rebuilds"] = hname
    info["file"] = relp(dst)
    info["md5"] = md5_of(dst)
    info["axis"] = AXES[name]
    return info


def build_b0() -> Dict[str, Any]:
    """B0: the BXhf_f1i1 recipe verbatim through the fixed writer -- G_ABPD +
    ONE famgen panelboard family (the demo's PP-1) + ONE instance, famgen
    loader chain under famload_hostfix.corpus_symbol_form, the demo's own
    stage_equipment placement (product FamilyInstanceConnectorManager)."""
    B = _bisect()
    from rvt import famload_hostfix as HF
    from rvt.mutate import Document
    info: Dict[str, Any] = {"probe": "B0", "axis": AXES["B0"],
                            "base": relp(G_ABPD),
                            "recipe": "BXhf_f1i1 (hostpair batch 39) through "
                                      "the FIXED writer: bisect_instance_bug "
                                      "chain+place under "
                                      "famload_hostfix.corpus_symbol_form"}
    chain_dir = os.path.join(BUILD_DIR, "B0_chain")
    if os.path.isdir(chain_dir):
        shutil.rmtree(chain_dir)
    outp = os.path.join(OUT_DIR, "B0.rvt")
    with HF.corpus_symbol_form():
        model6 = B.demo_model()
        m1 = B.truncate_model(model6, 1)
        l1 = B.build_chain(G_ABPD, chain_dir, m1)
        f1 = B.chain_file(chain_dir, 1, "PP-1")
        e1 = B.place_instances(m1, f1, outp, G_ABPD, l1.get("_loaded") or {})
    info["load"] = {"loads": [{k: v for k, v in ld.items()
                               if k in ("tag", "ok", "symbol_id", "family_id",
                                        "host_watermark", "out")}
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
        raise RuntimeError(f"B0: expected exactly 1 dangling-free instance, "
                           f"got {len(insts)} (dangling: {dangling})")
    info["placement"] = ("demo stage_equipment (the BXhf_f1i1 recipe: product "
                         "connector manager, intent position)")
    info["immediate_parent"] = relp(f1)
    info["file"] = relp(outp)
    info["md5"] = md5_of(outp)
    # read back the instance's connector manager class from the emitted bytes
    doc = Document.from_file(outp)
    cm = (doc.value(info["instance_ids"][0]) or {}).get("m_pConnectorManager")
    info["instance_connmgr"] = (cm.get("ptr_class") if isinstance(cm, dict)
                                else cm)
    # the corpus-lawful symbol form gate (the BXhf recipe's own invariant)
    forms = {}
    for sid in doc.ids_of_class("FamilySymbol"):
        v = doc.value(sid) or {}
        fam = doc.value(v.get("m_familyId") or -1) or {}
        if "PP-" in str(fam.get("m_name") or ""):
            forms[sid] = HF.assert_symbol_form(outp, sid)
    bad = [k for k, f in forms.items() if not f["ok"]]
    if bad or not forms:
        raise RuntimeError(f"B0 symbol form check failed: "
                           f"{bad or 'no PP- symbols found'}")
    info["symbol_form"] = {str(k): {"ok": f["ok"], "counts": f["counts"]}
                           for k, f in forms.items()}
    return info


# ===========================================================================
# build driver (per-probe: build + accounting + blob proof)
# ===========================================================================

def _accounting(name: str, info: Dict[str, Any]) -> Dict[str, Any]:
    """The famdoc-bisect stream's own instrument (bisect_instance_bug
    .account) on the emitted probe + its load hop, PLUS this round's blob
    proof on both files."""
    B = _bisect()
    base = RST if name != "B0" else G_ABPD
    child = os.path.join(ROOT, info["file"])
    parent = os.path.join(ROOT, info["immediate_parent"])
    out: Dict[str, Any] = {}
    out["probe"] = B.account(name, child, parent, declared_base=base,
                             instance_ids=info.get("instance_ids") or [])
    out["hop_load"] = B.account(name + ".hop_load", parent, base,
                                declared_base=base, instance_ids=[],
                                with_regdiff=False)
    out["blob_proof"] = blob_proof(child, base)
    out["blob_proof_parent"] = blob_proof(parent, base)
    return out


def _gates(name: str, info: Dict[str, Any], acct: Dict[str, Any]) -> Dict[str, Any]:
    rep = acct["probe"]
    hop = acct["hop_load"]
    va = rep["validator"]
    bp = acct["blob_proof"]
    unresolved = None
    if name != "B0":
        unresolved = (((info.get("dev_rfa") or {}).get("reference_resolution")
                       or {}).get("unresolved_anywhere"))
    g = {
        "validator_errors": va["n_errors"],
        "validator_unexpected": len(va["unexpected_errors"]),
        "four_registry_coherent": rep["census"]["coherent"],
        "load_hop_units_added": hop["census_delta"]["save_units"],
        "instance_hop_units_added": rep["census_delta"]["save_units"],
        "survivor_law_ok": bool(rep["survivor_law_ok"]) and bool(hop["survivor_law_ok"]),
        "identity": (rep.get("identity_gate") or {}).get("status"),
        "blob_all_units_64B": bp["all_units_64B"],
        "blob_added_nonce_verified": bp["added_nonce_verified"],
        "blob_units_added": bp["units_added_vs_base"],
        "famdoc_refs_unresolved_anywhere": unresolved,
    }
    ok = (g["validator_errors"] == 0 and g["validator_unexpected"] == 0
          and g["four_registry_coherent"] is True
          and g["load_hop_units_added"] == 1
          and g["instance_hop_units_added"] == 0
          and g["survivor_law_ok"] and g["identity"] == "PASS"
          and g["blob_all_units_64B"] and g["blob_added_nonce_verified"]
          and g["blob_units_added"] == 1
          and (unresolved in (0, None)))
    g["gates_ok"] = bool(ok)
    return g


def build(only: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    FB = _fb()
    FB._install_schema()                                       # noqa: SLF001
    only = list(only) if only else list(LADDER)
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(BUILD_DIR, exist_ok=True)
    t0 = time.time()
    out: Dict[str, Any] = {"tool": "tools/famdoc_blobs.py",
                           "bases": {"hybrids": relp(RST), "B0": relp(G_ABPD)},
                           "built": {}, "accounting": {}, "gates": {},
                           "errors": {}}
    if os.path.isfile(ACCT):                     # merge partial (--only) runs
        try:
            with open(ACCT) as fh:
                prev = json.load(fh)
            for k in ("built", "accounting", "gates"):
                out[k] = {n: v for n, v in (prev.get(k) or {}).items()
                          if n not in only}
        except Exception:                          # noqa: BLE001
            pass
    for name in [n for n in LADDER if n in only]:
        try:
            t1 = time.time()
            info = build_b0() if name == "B0" else build_hybrid(name)
            info["seconds"] = round(time.time() - t1, 1)
            out["built"][name] = info
            log(f"{name} BUILT -> {info['file']} (md5 {info['md5'][:8]}, "
                f"{info['seconds']}s)")
            acct = _accounting(name, info)
            out["accounting"][name] = acct
            g = _gates(name, info, acct)
            out["gates"][name] = g
            log(f"{name}: validator {g['validator_errors']} err "
                f"(unexpected {g['validator_unexpected']}), coherent "
                f"{g['four_registry_coherent']}, +{g['load_hop_units_added']}u "
                f"load hop, blob 64B x{acct['blob_proof']['units_total']} "
                f"(added nonce {'OK' if g['blob_added_nonce_verified'] else 'BAD'}), "
                f"gates_ok {g['gates_ok']}")
            if not g["gates_ok"]:
                out["errors"][name + ".gates"] = f"gates_ok False: {g}"
        except Exception as e:                                 # noqa: BLE001
            out["errors"][name] = f"{type(e).__name__}: {e}"
            out["errors"][name + ".traceback"] = traceback.format_exc(limit=10)
            log(f"{name} FAILED: {type(e).__name__}: {e}")
    out["seconds"] = round(time.time() - t0, 1)
    jdump(ACCT, out)
    write_probes_json(out)
    return out


# ===========================================================================
# probes.json (the decision table the orchestrator reads)
# ===========================================================================

READING = {
    "CTRL FAIL (either)": "round VOID (oracle/environment) -- interpret "
                          "nothing; the rst control voids B1..B7, the G_ABPD "
                          "control voids B0.",
    "B7 PASS": "the famload machinery (authored host flavour + unit "
               "re-encode + id rebase + registration) is LAWFUL WITH THE "
               "BLOB on a lawful famdoc -- batch 37's H7 FAIL is fully "
               "explained by its empty blob.  B1..B6 now carry clean "
               "one-axis content information.",
    "B7 FAIL": "even blob-carrying, famload's own treatment poisons a "
               "lawful Autodesk famdoc: content attribution of B1..B6 is "
               "VOID (they ride the same machinery).  The E-round already "
               "proved the H12 byte-copy machinery + blob PASSES, so the "
               "suspect space = exactly the delta famload authors vs H12's "
               "byte-copies (host Family/FamilySymbol flavour, inline "
               "ADocument, re-encoded unit bytes, registration row "
               "content).  B0 still reads alone (different loader).",
    "B0 PASS": "THE PRODUCT SHAPE PASSES WITH THE BLOB: the famgen loader + "
               "our famdoc content + blob is lawful at 1 family / 1 "
               "instance.  Immediate action (this stream's charter): "
               "rebuild DEMO v6 through tools/frontdoor.py with the user's "
               "exact prompt, machine-verify blobs on all units, stage it "
               "-- v6 PASS closes the hunt; v6 FAIL localises the defect "
               "to demo-scale composition (multi-family / walls / feeders "
               "interaction), bisected next by the demo's own stages.",
    "B0 FAIL + B7 PASS + any Bn (B1..B6) FAIL": "the round is fully "
               "bracketed and the FAILING axis rung(s) name our guilty "
               "famdoc subtree(s) -- with blobs present the conviction is "
               "clean.  Fix in deep-walk rank order B1 > B2 > B3 > B5 > "
               "B4; the fix spec starts at "
               "experiments/famdoc_bisect/famdoc_diff.json's ranked "
               "entries for that axis (headline: m_geomSteps/m_pGeomTable "
               "on our form elements).",
    "B0 FAIL + B7 PASS + B1..B6 ALL PASS": "no single added axis "
               "reproduces the failure: the defect lives in what only B0 "
               "carries -- our WHOLE-document composition (the S0 skeleton "
               "itself, element ordering, the units/registry singletons), "
               "the famgen-loader flavour (vs famload -- B0 is the only "
               "famgen-loader rung), the G_ABPD base, or an axis "
               "interaction.  Next ladder: our famdoc through famload on "
               "rst (the old H8 with blob) to split loader vs content, "
               "then pairwise axis unions / the inverse bisection.",
    "B6 verdict": "with B7 PASS it is corroboration (both inline-ADocument "
                  "forms lawful with blobs); with B7 FAIL it splits the "
                  "inline-ADocument axis from the rest of the famload "
                  "flavour.",
    "multiple axis FAILs": "each failing axis is independently convicted "
                           "(the hybrids are ADD-form unions, mutually "
                           "independent).",
}

EXPECTED = {
    "B7": "PASS (E1b's law: presence-only blob check; every other "
          "ingredient certified -- famdoc native, famload = L1a/L_v2, "
          "placement = V20; batch 37's H7 FAIL is attributed to its empty "
          "blob)",
    "B0": "the product verdict rung: PASS => DEMO v6 immediately; FAIL = "
          "the residual content defect at minimal scale (v5's shape)",
    "B1": "the hypothesis-bearing rung: FAIL convicts our geometry grammar "
          "(prime prior: m_geomSteps/m_pGeomTable on form elements)",
    "B2": "unknown", "B3": "unknown", "B4": "unknown", "B5": "unknown",
    "B6": "PASS if B7 passes (corroboration)",
}

ONETHING = {
    "B7": "batch 37's H7 rebuilt through the FIXED writer: the Autodesk "
          "M_Concrete-Square-Column famdoc (id-rebased, otherwise verbatim) "
          "famload-loaded into its own rst sample + ONE template instance, "
          "the added unit NOW carrying the 64-byte 0x0f3f blob.  The ONE "
          "thing it tests: the famload machinery under an instance WITH the "
          "blob.",
    "B0": "the BXhf_f1i1 recipe rebuilt through the FIXED writer: G_ABPD + "
          "ONE famgen panelboard family (the demo's PP-1, corpus-lawful "
          "symbol form) + ONE instance (product connector manager), the "
          "added unit blob-carrying.  The ONE thing it tests: OUR famdoc "
          "content at minimal product scale WITH the blob.",
    "B1": "B7 + OUR geometry subtree (ExtrusionElem + VarSketch + 4 "
          "CurveElems + SketchPlane) added to the donor famdoc, registered "
          "like its own members -- with blob.",
    "B2": "B7 + OUR parameter/type layer (14 ParamElemFamily + our rows in "
          "all four self-Family parameter surfaces) -- with blob.",
    "B3": "B7 + OUR reference/datum layer (2 origin RefPlanes + Level + "
          "LevelAttributes) -- with blob.",
    "B4": "B7 + OUR plan-view constellation (8 elements) -- with blob.",
    "B5": "B7 + OUR connector layer (ConnectorElem + "
          "ElectricalLoadClassification + the apparent-load param) -- with "
          "blob.",
    "B6": "B7's document with the DONOR's OWN inline ADocument (131 "
          "populated registries, remapped) instead of our authored all-null "
          "one -- with blob.",
}


def write_probes_json(build_out: Dict[str, Any]) -> str:
    probes = []
    for i, name in enumerate(LADDER, 1):
        info = (build_out.get("built") or {}).get(name) or {}
        gates = (build_out.get("gates") or {}).get(name) or {}
        bp = ((build_out.get("accounting") or {}).get(name) or {}).get(
            "blob_proof") or {}
        probes.append({
            "order": i,
            "rung": name,
            "file": f"experiments/famdoc_blobs/{name}.rvt",
            "base": relp(G_ABPD) if name == "B0" else relp(RST),
            "kind": "probe",
            "axis": AXES[name],
            "rebuilds": info.get("rebuilds") or ("BXhf_f1i1" if name == "B0"
                                                 else None),
            "n_families": 1, "n_instances": 1, "n_walls": 0,
            "the_ONE_thing_it_tests": ONETHING[name],
            "expected": EXPECTED[name],
            "md5": info.get("md5"),
            "symbol_id": info.get("symbol_id"),
            "family_id": info.get("family_id"),
            "instance_ids": info.get("instance_ids"),
            "immediate_parent": info.get("immediate_parent"),
            "blob_proof": {k: bp.get(k) for k in
                           ("units_total", "blob_len_histogram",
                            "units_added_vs_base", "added_nonce_verified")},
            "gates": gates,
        })
    manifest = {
        "stream": "famdoc-blobs: batch 37's famdoc hybrid bisection RE-RUN "
                  "WITH BLOBS (verdict #37: the empty 0x0f3f blob alone "
                  "voided every batch-37 hybrid for content attribution; "
                  "the fixed writer stamps the 64-byte nonce on every "
                  "emitted unit, machine-verified per probe).  Whichever "
                  "hybrid FAILS with a blob names our guilty famdoc "
                  "subtree.",
        "bases": {"hybrids": relp(RST), "B0": relp(G_ABPD)},
        "note": "B7/B1..B6 = untouched rst sample + ONE loaded famdoc + ONE "
                "placed instance (famdoc_bisect's own hybrid machinery, "
                "output repointed; donor = the sample's own "
                "M_Concrete-Square-Column).  B0 = G_ABPD + ONE famgen "
                "family + ONE instance (the BXhf_f1i1 recipe).  EVERY "
                "probe's added unit carries the 64-byte 0x0f3f footer blob "
                "(raw-scanned + nonce-verified against "
                "famdoc_adoc.build_footer -- zero donor bytes).  PROOF-ONLY "
                "sample-derived content, quarantined, never shipped.  Fresh "
                "GUIDs are minted per rebuild -- re-hash after any rerun.",
        "upload_order_max_information_first": list(LADDER),
        "controls": {
            "rst": {"source": relp(RST),
                    "voids": "B7,B1..B6 on CTRL FAIL"},
            "g_abpd": {"source": relp(G_ABPD),
                       "voids": "B0 on CTRL FAIL"},
        },
        "reading_the_matrix": READING,
        "companion_evidence": {
            "accounting": "experiments/famdoc_blobs/accounting.json",
            "ranked_diff_checklist": "experiments/famdoc_bisect/famdoc_diff.json",
            "per_probe_hybrid_reports": "experiments/famdoc_blobs/_h/_build/<Hn>/hybrid_report.json",
            "b0_chain": "experiments/famdoc_blobs/_build/B0_chain/",
            "prior_round": "experiments/famdoc_bisect/probes.json (batch 37, "
                           "VOID for content attribution -- empty blobs)",
        },
        "probes": probes,
    }
    path = os.path.join(OUT_DIR, "probes.json")
    jdump(path, manifest)
    log(f"probes.json -> {relp(path)}")
    return path


# ===========================================================================
# verify + stage
# ===========================================================================

def verify() -> Dict[str, Any]:
    """Re-run every gate (accounting + blob proof) on the emitted probes."""
    FB = _fb()
    FB._install_schema()                                       # noqa: SLF001
    if not os.path.isfile(ACCT):
        raise SystemExit("no accounting.json -- run build first")
    with open(ACCT) as fh:
        out = json.load(fh)
    fresh: Dict[str, Any] = {}
    for name, info in (out.get("built") or {}).items():
        child = os.path.join(ROOT, info["file"])
        parent = os.path.join(ROOT, info["immediate_parent"])
        if not (os.path.isfile(child) and os.path.isfile(parent)):
            fresh[name] = {"error": "file(s) missing"}
            continue
        try:
            acct = _accounting(name, info)
            g = _gates(name, info, acct)
            out["accounting"][name] = acct
            out["gates"][name] = g
            fresh[name] = g
            log(f"{name}: gates_ok {g['gates_ok']} (validator "
                f"{g['validator_errors']} err, blob nonce "
                f"{'OK' if g['blob_added_nonce_verified'] else 'BAD'})")
        except Exception as e:                                 # noqa: BLE001
            fresh[name] = {"error": f"{type(e).__name__}: {e}"}
            log(f"{name} VERIFY FAILED: {type(e).__name__}: {e}")
    jdump(ACCT, out)
    write_probes_json(out)
    return fresh


def next_batch_number() -> int:
    """CAMPAIGN-GLOBAL and collision-proof: max over (a) every
    batch_<n>.json under experiments/ and (b) every staged _b<n> file tag
    under experiments/acceptance/ (the orchestrator's b43 round staged
    controls without a manifest), + 1."""
    B = _bisect()
    n = B._campaign_global_next_batch() - 1                    # noqa: SLF001
    for p in glob.glob(os.path.join(ROOT, "experiments", "acceptance", "*_b[0-9]*.*")):
        m = re.search(r"_b(\d+)\.[A-Za-z0-9]+$", os.path.basename(p))
        if m:
            n = max(n, int(m.group(1)))
    return n + 1


def stage() -> Dict[str, Any]:
    """probe_batch gate + stage with TWO controls (byte-identical untouched
    rst copy for the hybrids + a G_ABPD copy for B0), one batch."""
    pb = _pb()
    import datetime as _dt
    files = [os.path.join(OUT_DIR, f"{n}.rvt") for n in LADDER]
    missing = [f for f in files if not os.path.isfile(f)]
    if missing:
        raise SystemExit(f"missing probes (run build): "
                         f"{[relp(m) for m in missing]}")
    with open(ACCT) as fh:
        acct = json.load(fh)
    bad = [n for n in LADDER if not (acct.get("gates") or {}).get(n, {}).get("gates_ok")]
    if bad:
        raise SystemExit(f"gates not green for {bad} -- stage refused")
    ledger = pb.Ledger.load()
    entries, violations = pb.check_batch(files, ledger)
    if violations:
        raise pb.GateRefusal(violations)
    n = next_batch_number()
    out_dir = pb.ACCEPTANCE
    ctrl_rst = pb.make_control(ledger, n, out_dir, source=RST)
    ctrl_g = pb.make_control(ledger, n, out_dir, source=G_ABPD)
    ordered = [ctrl_rst, ctrl_g] + [e for e in entries if e.kind == "probe"]
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
                     f"{pb.rel(dst)} (md5 {md5_of(dst)} vs {e.md5}); rename "
                     f"the probe -- never overwrite a staged file the viewer "
                     f"may already have read"])
            shutil.copyfile(src, dst)
        e.staged_as = pb.rel(dst)
    manifest = {
        "batch": n,
        "created": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "tool": "tools/famdoc_blobs.py (via tools/probe_batch.py primitives)",
        "law": ("every entry's declared base is ITSELF in "
                "viewer-certified.json 'certified' (or is an Autodesk sample "
                "source); the batch carries >= 1 CONTROL = a byte-identical "
                "copy of a certified file; read the round with "
                "read_batch_verdicts(): control FAIL => every verdict VOID"),
        "ledger": pb.rel(ledger.path),
        "control_count": 2,
        "controls": {"rst": ctrl_rst.staged_as, "g_abpd": ctrl_g.staged_as,
                     "note": "the rst control gates B7/B1..B6; the G_ABPD "
                             "control gates B0 -- either control FAIL voids "
                             "its probes"},
        "note": "famdoc-blobs: batch 37's famdoc hybrid ladder RE-RUN WITH "
                "BLOBS (verdict #37: every batch-37 hybrid carried an empty "
                "0x0f3f blob, which alone fails any instanced unit -- "
                "content attribution was VOID).  Every probe's added unit "
                "now carries the 64-byte deterministic nonce "
                "(machine-verified, see "
                "experiments/famdoc_blobs/accounting.json blob_proof).  "
                "Reading order B7 (machinery anchor), B0 (product shape), "
                "B1 (geometry, prime prior), B2..B6.  Read "
                "experiments/famdoc_blobs/probes.json reading_the_matrix; "
                "the fix spec source is "
                "experiments/famdoc_bisect/famdoc_diff.json.",
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
    # staged-copy md5 verification (control + every probe)
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
    b = sub.add_parser("build", help="build the 8 blob-carrying probes")
    b.add_argument("--only", default=None, help="comma-separated probe subset")
    sub.add_parser("verify", help="re-run the gates on the emitted probes")
    sub.add_parser("stage", help="probe_batch gate + stage (2 controls)")
    a = ap.parse_args(argv)
    if a.cmd == "build":
        only = [s.strip() for s in a.only.split(",")] if a.only else None
        bad = [r for r in (only or []) if r not in LADDER]
        if bad:
            ap.error(f"unknown probe(s): {bad}; choose from {list(LADDER)}")
        out = build(only)
        n_err = len([k for k in out["errors"]
                     if not k.endswith((".traceback", ".tb"))])
        log(f"build done: {len(out['built'])} probe(s), {n_err} error(s), "
            f"{out['seconds']}s")
        return 1 if n_err else 0
    if a.cmd == "verify":
        fresh = verify()
        bad = [n for n, r in fresh.items()
               if r.get("error") or not r.get("gates_ok")]
        log(f"verify done: {len(fresh)} probe(s), gate failures: {bad or 'none'}")
        return 1 if bad else 0
    if a.cmd == "stage":
        stage()
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
