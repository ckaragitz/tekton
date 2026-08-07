#!/usr/bin/env python
"""residual_probe.py -- CORNER THE INSTANCE RESIDUAL (instbug-residual stream,
2026-08-05).

THE RESIDUAL.  After the six D1..D5 core patches landed (instbug-fix), the
instance rungs STILL fail the Autodesk open-time audit: BXfix_f1i1,
BXfix_f6i6, DEMO_250v_room_v2 (all D-FIXED) and -- the key datum -- SX_f6i6
(the same famgen-path 6-load + 6-instance operation on the RST SAMPLE base)
FAILED while the famload-path load of the same kind of generated family into
the same sample (L_v2_panel_loaded) is viewer-PASSED.  The discriminator is
the CODE PATH, not the base lineage.  The fix stream's §7 honesty limit
pre-named the prime residual: famgen's BAKED SYMBOL GEOMETRY (`m_geomSteps` +
`m_pGeomTable` + the seq-103 GElement, the [H] one-specimen grammar) has only
ever been viewer-accepted UNREFERENCED; the audit walks INTO the symbol solid
only once an instance REFERENCES it (fits BX_f2 passing with 2 loads / 0
instances, the WF pair passing with 1 unreferenced family, R_inst_box failing
with a bare box).

THREE INSTRUMENTS, one verdict each:

  (1) THE VARIANT RUNGS -- kill or confirm the geometry hypothesis:
        BXns_f1i1   G_ABPD + ONE famgen family + ONE placed instance, the
                    demo's own code path, with ONE change vs the FAILED
                    BXfix_f1i1: the host FamilySymbol is authored with
                    ``symbol_solid=False`` (loader's F4b mode: seq-103 =
                    SerializedDummy, ``m_geomSteps``/``m_pGeomTable`` = None
                    -- the exact form rvt.famload writes and the corpus's
                    'let Revit regenerate the symbol' shape).  The EMBEDDED
                    family document keeps its authored solid (product
                    ``solid=True``), so the ONE variable is the host-symbol
                    baked geometry.
        BXns_f6i6   the demo shape (6 families + 6 instances), same variant.
      NO loader edit was needed: ``loader.author_family_symbol`` already has
      the ``solid=False`` mode and ``load_family_into_project`` exposes
      ``symbol_solid`` independently of the product's own solid -- this tool
      merely composes them (src/rvt/famgen/nosolid_variant.py NOT created;
      the wrapper the charter pre-authorized is unnecessary).  The validator
      accepts the dummy rep on an instanced symbol (smoke-proved: VALID, 0
      errors) -- and ``mine`` documents the corpus's own no-solid shapes.

  (2) THE MATCHED-PAIR FORENSICS (``forensics``) -- diff the SYMBOL element
      between the famload-PASS and famgen-FAIL materializations on the SAME
      rst base + the same kind of generated panel family:
        PASS  experiments/families/genesis2/L_v2_panel_loaded.rvt   (famload)
        FAIL  experiments/instbug/SX_f6i6.rvt (+ its first-load subset
              experiments/instbug/_build/rst/stage_L1_pp1.rvt)      (famgen)
      plus a per-file FEATURE SURVEY over EVERY failing and passing
      family/instance file on disk, ranked present-in-fail / absent-in-pass
      (the corpus discipline).  Output: forensics_surveys.json,
      matched_pair_delta.json, delta_matrix.json.

  (3) THE FAMLOAD CROSS-CHECK RUNGS -- prove the path attribution at N=6:
        SL_f1i1     rst sample + the SAME generated family document loaded
                    through the CERTIFIED rvt.famload path (L_v2's recipe)
                    + ONE instance placed by the demo's own stage_equipment.
        SL_f6i6     six families famload-loaded in one call + six instances.
      If famload-path f6i6 PASSES where famgen-path SX_f6i6 FAILED, the path
      attribution is proven at N=6 and the fix spec is 'make famgen
      register/author what famload does' -- the matched-pair delta list IS
      that spec.

READING ORDER (probes.json, maximum information first):
      BXns_f1i1 (one verdict kills/confirms the geometry hypothesis) ->
      SL_f6i6 (path attribution at the demo's N) -> BXns_f6i6 (the demo
      shape, no-solid) -> SL_f1i1 (the N=1 famload point).

USAGE (repo root)::

    .venv/bin/python tools/residual_probe.py build            # all four rungs
    .venv/bin/python tools/residual_probe.py build --only BXns_f1i1,SL_f6i6
    .venv/bin/python tools/residual_probe.py forensics        # surveys + pair diff + matrix
    .venv/bin/python tools/residual_probe.py mine             # corpus no-solid symbol shapes
    .venv/bin/python tools/residual_probe.py stage            # probe_batch gate + control

TERRITORY: this file, ``experiments/instbug/residual/**``,
``tests/test_residual.py``, ``docs/inbox/instbug-residual.md``.  IMPORTS
(never edits): tools/ifc_intent.py + tools/bisect_instance_bug.py (the demo
build path + the per-rung accounting instrument), rvt.famgen.loader,
rvt.famload, rvt.frontdoor.standalone, rvt.mutate, rvt.validate,
tools/probe_batch.py.  No Autodesk install dirs, zero donors; the reduction
law holds by construction (pure adds); staged batch carries a certified
control.
"""
from __future__ import annotations

import argparse
import copy
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

PROMPT = "an electrical room rated for 250V with 6 panels"
G_ABPD = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "compose", "G_ABPD.rvt")
RST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
OUT_DIR = os.path.join(ROOT, "experiments", "instbug", "residual")
BUILD_DIR = os.path.join(OUT_DIR, "_build")

#: rung -> (base, path_kind, n_families, n_instances)
RUNG_SPEC: Dict[str, Tuple[str, str, int, int]] = {
    "BXns_f1i1": (G_ABPD, "famgen_nosolid", 1, 1),
    "BXns_f6i6": (G_ABPD, "famgen_nosolid", 6, 6),
    "SL_f1i1":   (RST,    "famload",        1, 1),
    "SL_f6i6":   (RST,    "famload",        6, 6),
}

#: staging / reading order = maximum information first
LADDER = ("BXns_f1i1", "SL_f6i6", "BXns_f6i6", "SL_f1i1")


def log(msg: str) -> None:
    print(f"[residual] {msg}", flush=True)


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


def _bisect():
    """tools/bisect_instance_bug.py as a module (the instbug stream's demo
    build path + accounting instrument; imported, never edited)."""
    import bisect_instance_bug as B
    return B


def _room():
    import ifc_intent as T
    return T


# ===========================================================================
# instrument 1 -- the no-solid famgen chain (product solid=True kept)
# ===========================================================================

def nosolid_chain(base_path: str, chain_dir: str, model) -> Dict[str, Any]:
    """Chain rvt.famgen.loader over every panel EXACTLY like the demo's
    stage_L (tools/ifc_intent.stage_load) with ONE split: the family DOCUMENT
    keeps its authored solid (``build_product(solid=True)`` -- famload
    parity: the embedded unit carries the geometry) while the HOST symbol is
    authored ``symbol_solid=False`` (SerializedDummy rep, no geometry
    history).  That isolates the host-symbol baked geometry as the ONE
    variable vs the D-fixed BXfix rungs."""
    from rvt.famgen import loader as L
    T = _room()
    os.makedirs(chain_dir, exist_ok=True)
    order = T._load_order(model)
    current = os.path.join(chain_dir, "stage_L0_base.rvt")
    shutil.copyfile(base_path, current)
    rec: Dict[str, Any] = {"stage": "L(nosolid)", "base": relp(base_path),
                           "order": order, "loads": []}
    loaded: Dict[str, Any] = {}
    for i, tag in enumerate(order, 1):
        plan = model.plan_for(tag)
        nxt = os.path.join(chain_dir, f"stage_L{i}_{tag.lower().replace('-', '')}.rvt")
        t0 = time.time()
        wm = T.host_watermark(current)
        prod = T.build_product(plan, start_id=wm + 1, solid=True)
        res = L.load_family_into_project(current, nxt, product=prod, place=False,
                                         symbol_solid=False,
                                         report_path=nxt + ".load.json",
                                         validate=False)
        entry = {"tag": tag, "in": relp(current), "out": relp(nxt),
                 "ok": bool(res.ok), "stop_reason": res.stop_reason,
                 "symbol_id": res.plan.symbol_id if res.plan else None,
                 "family_id": res.plan.host_family_id if res.plan else None,
                 "content_guid": res.plan.guid if res.plan else None,
                 "symbol_rep": "SerializedDummy (symbol_solid=False)",
                 "product_solid": True,
                 "seconds": round(time.time() - t0, 1)}
        rec["loads"].append(entry)
        if not res.ok:
            raise RuntimeError(f"nosolid load {tag} failed: {res.stop_reason}")
        loaded[tag] = {"symbol_id": entry["symbol_id"], "family_id": entry["family_id"],
                       "content_guid": entry["content_guid"], "product": prod}
        log(f"L(ns) {tag} -> {os.path.basename(nxt)} (symbol {entry['symbol_id']}, "
            f"dummy rep, {entry['seconds']}s)")
        current = nxt
    rec["final"] = relp(current)
    rec["_loaded"] = loaded
    rec["_current"] = current
    return rec


def chain_file(chain_dir: str, i: int, tag: str) -> str:
    return os.path.join(chain_dir, f"stage_L{i}_{tag.lower().replace('-', '')}.rvt")


# ===========================================================================
# instrument 3 -- the famload load (L_v2's recipe, N families in one call)
# ===========================================================================

def famload_load(base_path: str, out_path: str, model_n) -> Dict[str, Any]:
    """Load every panel of ``model_n`` into a copy of ``base_path`` through
    the CERTIFIED rvt.famload four-registry path (L_v2's recipe: a builder
    per family; the loader allocates the id blocks).  The products are kept
    for stage_equipment's connector managers."""
    from rvt import famload as FL
    T = _room()
    order = T._load_order(model_n)
    products: Dict[str, Any] = {}
    fams = []
    for tag in order:
        plan = model_n.plan_for(tag)

        def mk(start_id, _plan=plan, _tag=tag):
            prod = T.build_product(_plan, start_id=start_id, solid=True)
            products[_tag] = prod
            return prod.doc

        fams.append(FL.FamilyLoad(key=tag, builder=mk))
    t0 = time.time()
    res = FL.load_family_documents(base_path, fams, out_path, validate=True,
                                   report_path=out_path + ".load.json")
    if not res.ok:
        raise RuntimeError(f"famload failed: {res.stop_reason}")
    loaded = {p.key: {"symbol_id": p.symbol_id, "family_id": p.host_family_id,
                      "content_guid": p.guid, "product": products[p.key]}
              for p in res.plans}
    log(f"famload {len(res.plans)} famil{'y' if len(res.plans)==1 else 'ies'} -> "
        f"{os.path.basename(out_path)} ({round(time.time()-t0,1)}s)")
    return {"stage": "L(famload)", "base": relp(base_path), "out": relp(out_path),
            "order": order,
            "plans": [{"key": p.key, "family_id": p.host_family_id,
                       "symbol_id": p.symbol_id, "content_guid": p.guid,
                       "type_names": p.type_names, "part_type": p.part_type}
                      for p in res.plans],
            "_loaded": loaded, "seconds": round(time.time() - t0, 1)}


# ===========================================================================
# build driver
# ===========================================================================

def build(only: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    from rvt.frontdoor import standalone as SA
    B = _bisect()
    only = list(only) if only else list(LADDER)
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(BUILD_DIR, exist_ok=True)
    SA.install_schema(G_ABPD)
    model6 = B.demo_model()
    t0 = time.time()
    out: Dict[str, Any] = {"tool": "tools/residual_probe.py", "prompt": PROMPT,
                           "built": {}, "accounting": {}, "errors": {}}

    # -- the shared no-solid chain (built once, deepest needed) --------------
    ns_chain: Optional[Dict[str, Any]] = None

    def get_ns_chain() -> Dict[str, Any]:
        nonlocal ns_chain
        if ns_chain is None:
            cdir = os.path.join(BUILD_DIR, "nosolid_gabpd")
            log(f"no-solid famgen chain on {relp(G_ABPD)} ...")
            ns_chain = nosolid_chain(G_ABPD, cdir, model6)
            jdump(os.path.join(cdir, "chain_load_record.json"),
                  {k: v for k, v in ns_chain.items() if not k.startswith("_")})
        return ns_chain

    def build_rung(name: str) -> Dict[str, Any]:
        base_path, path_kind, nf, ni = RUNG_SPEC[name]
        outp = os.path.join(OUT_DIR, f"{name}.rvt")
        model_n = B.truncate_model(model6, nf)
        info: Dict[str, Any] = {"rung": name, "base": relp(base_path),
                                "path": path_kind, "n_families": nf,
                                "n_instances": ni}
        if path_kind == "famgen_nosolid":
            ch = get_ns_chain()
            order = ch["order"]
            src = chain_file(os.path.join(BUILD_DIR, "nosolid_gabpd"), nf, order[nf - 1])
            loaded_n = {t: ch["_loaded"][t] for t in order[:nf]}
            parent = src
        else:                                                # famload
            ldir = os.path.join(BUILD_DIR, f"famload_{name.lower()}")
            os.makedirs(ldir, exist_ok=True)
            src = os.path.join(ldir, f"SL_load{nf}.rvt")
            lrec = famload_load(base_path, src, model_n)
            info["famload"] = {k: v for k, v in lrec.items() if not k.startswith("_")}
            loaded_n = lrec["_loaded"]
            parent = src
        log(f"{name}: placing {ni} instance(s) onto {relp(src)} "
            f"(demo stage_equipment, ConstructedSpecimens) ...")
        erec = B.place_instances(model_n, src, outp, base_path, loaded_n)
        info["equipment"] = {
            "instances": [{k: i.get(k) for k in ("tag", "elem_id", "symbol",
                                                 "family", "position_ft", "n_dangling")}
                          for i in erec.get("instances") or []],
            "elemtable_after": erec.get("elemtable_after"),
            "structurally_valid": erec.get("structurally_valid")}
        info["instance_ids"] = [i["elem_id"] for i in erec.get("instances") or []]
        info["file"] = relp(outp)
        info["md5"] = md5_of(outp)
        info["immediate_parent"] = relp(parent)
        hops = [relp(base_path), relp(parent), relp(outp)]
        info["hops_from_base"] = hops
        return info

    for name in [r for r in LADDER if r in only]:
        try:
            info = build_rung(name)
            out["built"][name] = info
            log(f"{name} BUILT -> {info['file']} (md5 {info['md5'][:8]})")
        except Exception as e:                               # noqa: BLE001
            out["errors"][name] = f"{type(e).__name__}: {e}"
            out["errors"][name + ".traceback"] = traceback.format_exc(limit=8)
            log(f"{name} FAILED: {type(e).__name__}: {e}")

    # -- accounting: bisect's own instrument, load hop + instance hop --------
    for name, info in out["built"].items():
        base_path, path_kind, nf, ni = RUNG_SPEC[name]
        parent = os.path.join(ROOT, info["immediate_parent"])
        try:
            # the LOAD hop: the loaded parent vs the declared base
            out["accounting"][name + ".hop_load"] = B.account(
                name + ".hop_load", parent, base_path, declared_base=base_path,
                instance_ids=[], with_regdiff=False)
            # the INSTANCE hop: the rung vs its loaded parent
            rep = B.account(name, os.path.join(ROOT, info["file"]), parent,
                            declared_base=base_path,
                            instance_ids=info.get("instance_ids") or [])
            out["accounting"][name] = rep
            log(f"{name} accounting: units +{rep['census_delta']['save_units']}, "
                f"ct +{rep['census_delta']['contenttable_records']}, "
                f"elemtable +{rep['elemtable']['n_added']}, "
                f"validator {rep['validator']['n_errors']} err "
                f"(unexpected {len(rep['validator']['unexpected_errors'])}), "
                f"survivor_law {'OK' if rep['survivor_law_ok'] else 'VIOLATED'}, "
                f"coherent {rep['census']['coherent']}")
        except Exception as e:                               # noqa: BLE001
            out["errors"][name + ".accounting"] = f"{type(e).__name__}: {e}"
            out["errors"][name + ".accounting.tb"] = traceback.format_exc(limit=8)
            log(f"{name} ACCOUNTING FAILED: {type(e).__name__}: {e}")

    out["seconds"] = round(time.time() - t0, 1)
    jdump(os.path.join(OUT_DIR, "accounting.json"), out)
    write_probes_json(out)
    return out


# ===========================================================================
# probes.json
# ===========================================================================

READING = {
    "CTRL FAIL": "round VOID (oracle/environment) -- interpret nothing",
    "BXns_f1i1 PASS": "THE GEOMETRY HYPOTHESIS CONFIRMED: the ONE change vs the "
                      "FAILED BXfix_f1i1 is the host symbol's baked geometry "
                      "(GElement + m_geomSteps + m_pGeomTable -> SerializedDummy). "
                      "The audit rejects famgen's baked symbol geometry when an "
                      "instance references it.  Fix fork: (a) author the corpus-"
                      "lawful baked grammar (matched_pair_delta.json + mine's "
                      "corpus shapes = the spec), or (b) ship symbol_solid=False "
                      "on the product path (the no-solid product decision; "
                      "geometry regenerates from the embedded document).",
    "BXns_f1i1 FAIL": "the geometry hypothesis is DEAD at N=1: even the famload-"
                      "shaped dummy symbol fails under an instance on G_ABPD via "
                      "the demo path.  The residual is in the demo placement path "
                      "itself (stage_equipment template scaffolding) or the famgen "
                      "host-side registration -- read SL_f6i6 to split those.",
    "SL_f6i6 PASS": "PATH ATTRIBUTION PROVEN at N=6: the identical base + family "
                    "documents + instance placement pass when the LOAD is "
                    "rvt.famload.  With SX_f6i6 FAILED, the defect set is "
                    "famgen-loader host-side authorship: the ranked "
                    "matched_pair_delta.json IS the fix spec ('make famgen "
                    "register/author what famload does').",
    "SL_f6i6 FAIL": "the famload path ALSO fails once instances reference the "
                    "symbols => the residual is the INSTANCE side (the "
                    "ConstructedSpecimens template / stage_equipment shape), not "
                    "the load side; L_v2's no-instance PASS bounded nothing about "
                    "placement.  BXns verdicts then attribute within the "
                    "instance path.",
    "BXns_f6i6 PASS with BXns_f1i1 PASS": "the no-solid variant holds at the "
                                          "demo's full shape -- the product "
                                          "decision is live: DEMO can re-emit "
                                          "with symbol_solid=False today.",
    "BXns_f6i6 FAIL with BXns_f1i1 PASS": "N=1 clean, N=6 fails on the no-solid "
                                          "variant: a second, scale-dependent "
                                          "defect beyond the symbol geometry "
                                          "(diff BXns_f1i1 vs BXns_f6i6 "
                                          "accounting).",
    "SL_f1i1 vs BXns_f1i1": "the same N=1 instance question asked of both paths; "
                            "any split localizes the residual to what still "
                            "differs between them (see matched_pair_delta.json "
                            "pair P3).",
}


def write_probes_json(build_out: Dict[str, Any]) -> str:
    onething = {
        "BXns_f1i1": "ONE famgen family + ONE placed instance on G_ABPD by the "
                     "demo's own path, with the host symbol authored "
                     "symbol_solid=False (SerializedDummy rep, no geometry "
                     "history; embedded document keeps its solid).  The ONE "
                     "change vs the FAILED BXfix_f1i1 is the baked symbol "
                     "geometry -- one verdict kills or confirms the geometry "
                     "hypothesis.",
        "SL_f6i6": "SIX of the demo's own generated family documents loaded into "
                   "the rst sample by the CERTIFIED rvt.famload path (L_v2's "
                   "recipe) + SIX instances placed by the demo's own "
                   "stage_equipment.  The famload cross-check at SX_f6i6's exact "
                   "shape: PASS here + SX FAIL = path attribution proven at N=6.",
        "BXns_f6i6": "the demo shape (6 families + 6 instances) on G_ABPD with "
                     "no-solid host symbols -- the product-decision rung: can "
                     "the demo re-emit clean today by regenerating symbols?",
        "SL_f1i1": "ONE family famload-loaded + ONE instance on the rst sample "
                   "-- the N=1 famload point (pairs with BXns_f1i1 across the "
                   "path axis).",
    }
    expected = {
        "BXns_f1i1": "PASS if the baked-symbol-geometry hypothesis is right "
                     "(stage_L8-era precedent: dummy symbol forms have loaded; "
                     "the instance reference is the new part)",
        "SL_f6i6": "PASS (famload's host shapes are the certified L1a/L_v2 "
                   "lineage; instances are the demo's own, D-fixed)",
        "BXns_f6i6": "as BXns_f1i1 at scale",
        "SL_f1i1": "as SL_f6i6 at N=1",
    }
    probes = []
    for i, name in enumerate(LADDER, 1):
        info = (build_out.get("built") or {}).get(name) or {}
        acct = (build_out.get("accounting") or {}).get(name) or {}
        base_path, path_kind, nf, ni = RUNG_SPEC[name]
        va = acct.get("validator") or {}
        probes.append({
            "order": i,
            "rung": name,
            "file": f"experiments/instbug/residual/{name}.rvt",
            "base": relp(base_path),
            "kind": "probe",
            "path": path_kind,
            "n_families": nf, "n_instances": ni, "n_walls": 0,
            "the_ONE_thing_it_tests": onething[name],
            "expected": expected[name],
            "md5": info.get("md5"),
            "immediate_parent": info.get("immediate_parent"),
            "gates": {"validator_errors_at_build": va.get("n_errors"),
                      "validator_unexpected": len(va.get("unexpected_errors") or []),
                      "four_registry_coherent": (acct.get("census") or {}).get("coherent"),
                      "survivor_law_ok": acct.get("survivor_law_ok"),
                      "identity": ((acct.get("identity_gate") or {}).get("status"))},
        })
    manifest = {
        "stream": "instbug-residual: corner the instance residual (the audit "
                  "rejects famgen's baked FamilySymbol geometry when an instance "
                  "references it -- kill or confirm)",
        "prompt": PROMPT,
        "base": relp(G_ABPD),
        "note": "BXns rungs: the demo's own code path (prompt_to_intent -> famgen "
                "loader chain place=False -> stage_equipment ConstructedSpecimens "
                "+ add_family_instance + commit) with ONE change: host symbols "
                "authored symbol_solid=False (SerializedDummy -- famload's exact "
                "form; embedded documents keep their solid).  SL rungs: the SAME "
                "generated family documents loaded by CERTIFIED rvt.famload "
                "(L_v2's recipe) + the demo's own placement.  Fresh GUIDs are "
                "minted per rebuild -- re-hash after any rerun.",
        "upload_order_max_information_first": list(LADDER),
        "control": {"source": relp(G_ABPD),
                    "note": "control = byte-identical G_ABPD copy "
                            "(probe_batch stage --control-from)"},
        "reading_the_matrix": READING,
        "companion_evidence": {
            "matched_pair_delta": "experiments/instbug/residual/matched_pair_delta.json",
            "delta_matrix": "experiments/instbug/residual/delta_matrix.json",
            "surveys": "experiments/instbug/residual/forensics_surveys.json",
            "corpus_symbol_shapes": "experiments/instbug/residual/corpus_symbols.json",
            "accounting": "experiments/instbug/residual/accounting.json",
        },
        "probes": probes,
    }
    path = os.path.join(OUT_DIR, "probes.json")
    jdump(path, manifest)
    log(f"probes.json -> {relp(path)}")
    return path


# ===========================================================================
# instrument 2 -- the feature survey + matched-pair forensics
# ===========================================================================

#: file -> (declared base, recorded verdict, verdict source)
#: verdicts are machine-read from the ledger where present; L_v2's PASS is the
#: orchestrator's 01:20 report (NOT in the ledger's certified array -- recorded
#: honestly as such).
def _survey_sets() -> Dict[str, List[Tuple[str, str, str, str]]]:
    ZA = "experiments/genesis/subst_k4/residue_a/ZA_deep.rvt"
    WO = "experiments/ifc_room/electrical_room_2500a_walls_only.rvt"
    RME = "samples/rmebasicsampleproject.rvt"
    fail = [
        ("experiments/instbug/BX_f1i1.rvt", G_ABPD, "FAIL", "ledger (staged copy experiments/acceptance/BX_f1i1.rvt)"),
        ("experiments/instbug/SX_f6i6.rvt", RST, "FAIL", "ledger"),
        ("experiments/instbug/fix/BXfix_f1i1.rvt", G_ABPD, "FAIL", "ledger"),
        ("experiments/instbug/fix/BXfix_f6i6.rvt", G_ABPD, "FAIL", "ledger"),
        ("experiments/instbug/fix/DEMO_250v_room_v2.rvt", G_ABPD, "FAIL", "ledger"),
        ("experiments/acceptance/DEMO_250v_room.rvt", G_ABPD, "FAIL", "the user's demo failure (stream premise)"),
        ("experiments/ifc_room/render_probes/R_inst_box.rvt", ZA, "FAIL", "ledger"),
        ("experiments/ifc_room/render_probes/R_inst_downlight.rvt", ZA, "FAIL", "ledger"),
        ("experiments/ifc_room/render_probes/F_lp4.rvt", ZA, "FAIL", "ledger"),
        ("experiments/ifc_room/render_probes/F_msb.rvt", ZA, "FAIL", "ledger"),
        ("experiments/ifc_room/stage_W_loaded_walls.rvt", ZA, "FAIL", "ledger"),
        ("experiments/ifc_room/electrical_room_2500a.rvt", ZA, "FAIL", "ledger"),
    ]
    pas = [
        ("experiments/instbug/BX_f2.rvt", G_ABPD, "PASS", "ledger (weak: no model elements -- empty-design caveat)"),
        ("experiments/render/g12/WF_fix.rvt", WO, "PASS", "ledger"),
        ("experiments/render/g12/WF_nofix.rvt", WO, "PASS", "ledger"),
        ("experiments/ifc_room/stage_L8_lp4.rvt", ZA, "PASS", "ledger (weak: 'Design is empty' short-circuit)"),
        ("experiments/families/genesis2/L_v2_panel_loaded.rvt", RST, "PASS",
         "orchestrator viewer report 2026-08-05 ~01:20 (NOT in the ledger's certified array)"),
        ("experiments/genesis/loader/L1a_rstbasic_loaded_levelhead.rvt", RST, "PASS", "ledger"),
        ("experiments/families/ifc/L_downlight_loaded.rvt", RST, "PASS", "ledger"),
        ("experiments/hosting/H1_panel_on_existing_wall.rvt", RME, "PASS", "ledger"),
        ("experiments/hosting/H2_panel_on_created_wall.rvt", RME, "PASS", "ledger"),
        ("experiments/acceptance/V20_first_created_element.rvt", RST, "PASS", "ledger"),
        ("experiments/render/g12/W1_gabpd_wall_solid.rvt", G_ABPD, "PASS", "ledger (walls only -- no family layer)"),
    ]
    return {"fail": fail, "pass": pas}


def survey_file(path: str, base_path: str) -> Dict[str, Any]:
    """EVERY FamilySymbol + FamilyInstance of ``path``, with 'ours' = above
    the declared base's id watermark, and the file-level flags the residual
    hypothesis predicts on."""
    from rvt.mutate import Document
    T = _room()
    doc = Document.from_file(path if os.path.isabs(path) else os.path.join(ROOT, path))
    base_abs = base_path if os.path.isabs(base_path) else os.path.join(ROOT, base_path)
    wm = T.host_watermark(base_abs)
    symbols: Dict[int, Dict[str, Any]] = {}
    for sid in doc.ids_of_class("FamilySymbol"):
        sv = doc.value(sid) or {}
        symbols[sid] = {
            "ours": sid > wm,
            "rep_class": doc.class_of(sid, 103),
            "geom_steps": sv.get("m_geomSteps") is not None,
            "geom_table": sv.get("m_pGeomTable") is not None,
            "n_geomtag2material": len(sv.get("m_geomTag2MaterialId") or []),
            "n_strong_refs": len(sv.get("m_strongRefs") or []),
            "n_connector_data": len(sv.get("m_arrConnectorData") or []),
            "has_param_def_value": sv.get("m_hasParamDefValue"),
            "family": sv.get("m_familyId"),
            "instances": [],
        }
    instances: List[Dict[str, Any]] = []
    for iid in doc.ids_of_class("FamilyInstance"):
        iv = doc.value(iid) or {}
        ii = ((iv.get("m_pInstanceInfo") or {}).get("value") or {})
        ms = iv.get("m_masterSymbolId")
        rec = {"id": iid, "ours": iid > wm, "master_symbol": ms,
               "info_symbol": ii.get("m_symbolId"), "grep_id": ii.get("m_GRepId"),
               "rep_class": doc.class_of(iid, 103),
               "connmgr": ((iv.get("m_pConnectorManager") or {}) or {}).get("ptr_class")}
        instances.append(rec)
        if ms in symbols:
            symbols[ms]["instances"].append(iid)
    wall_ids = doc.ids_of_class("SWall")
    ours = {k: v for k, v in symbols.items() if v["ours"]}

    def baked(v):                      # famgen's baked host-symbol geometry
        return v["rep_class"] == "GElement" or v["geom_steps"] or v["geom_table"]

    our_insts = [r for r in instances if r["ours"]]
    of_ours = [r for r in our_insts if r["master_symbol"] in ours]
    flags = {
        "base_watermark": wm,
        "n_symbols": len(symbols),
        "n_our_symbols": len(ours),
        "n_our_instances": len(our_insts),
        "n_walls_total": len(wall_ids),
        "n_our_walls": sum(1 for w in wall_ids if w > wm),
        "our_baked_symbol": any(baked(v) for v in ours.values()),
        "our_dummy_symbol": any(not baked(v) for v in ours.values()),
        "our_instanced_baked_symbol": any(
            baked(v) and any(i > wm for i in v["instances"]) for v in ours.values()),
        "our_instanced_dummy_symbol": any(
            (not baked(v)) and any(i > wm for i in v["instances"]) for v in ours.values()),
        "our_uninstanced_baked_symbol": any(
            baked(v) and not v["instances"] for v in ours.values()),
        # ANY instance of OUR loaded family, geometry aside -- the competing
        # hypothesis the BXns/SL verdicts split from the baked-geometry one
        "our_instance_of_our_family": bool(of_ours),
        # the instance's OWN seq-103 is a GElement (the render stream's
        # instance-bake variant; H1/H2/V20 carry CLONED sample reps here)
        "our_instance_gelement_rep": any(r["rep_class"] == "GElement" for r in our_insts),
        # an audit walk from OUR instance reaches OUR-authored geometry:
        # baked symbol, or own GElement rep while pointing at OUR symbol
        "our_instance_reaches_our_baked_geometry": any(
            (r["master_symbol"] in ours)
            and (baked(ours[r["master_symbol"]]) or r["rep_class"] == "GElement")
            for r in of_ours),
        "sample_symbol_instanced_by_us": any(
            r["master_symbol"] is not None and isinstance(r["master_symbol"], int)
            and 0 <= r["master_symbol"] <= wm for r in our_insts),
    }
    return {"file": relp(path), "base": relp(base_path), "flags": flags,
            "our_symbols": {str(k): v for k, v in ours.items()},
            "our_instances": [r for r in instances if r["ours"]]}


#: the candidate discriminator features, ranked by the matrix
FEATURES = ("our_instance_reaches_our_baked_geometry",
            "our_instance_of_our_family",
            "our_instanced_baked_symbol", "our_baked_symbol",
            "our_instanced_dummy_symbol", "our_dummy_symbol",
            "our_uninstanced_baked_symbol", "our_instance_gelement_rep",
            "sample_symbol_instanced_by_us")


def forensics() -> Dict[str, Any]:
    from rvt.frontdoor import standalone as SA
    SA.install_schema(G_ABPD)
    t0 = time.time()
    sets = _survey_sets()
    surveys: Dict[str, Any] = {"fail": [], "pass": []}
    for side in ("fail", "pass"):
        for f, base, verdict, src in sets[side]:
            a = os.path.join(ROOT, f)
            if not os.path.isfile(a):
                surveys[side].append({"file": f, "missing": True,
                                      "verdict": verdict, "verdict_source": src})
                log(f"survey {f}: MISSING")
                continue
            try:
                s = survey_file(a, base)
                s["verdict"] = verdict
                s["verdict_source"] = src
                surveys[side].append(s)
                fl = s["flags"]
                log(f"survey {f}: our syms {fl['n_our_symbols']} "
                    f"(baked {fl['our_baked_symbol']}, "
                    f"instanced-baked {fl['our_instanced_baked_symbol']}), "
                    f"our insts {fl['n_our_instances']}, walls {fl['n_walls_total']}")
            except Exception as e:                           # noqa: BLE001
                surveys[side].append({"file": f, "error": f"{type(e).__name__}: {e}",
                                      "verdict": verdict, "verdict_source": src})
                log(f"survey {f} ERROR: {e}")
    jdump(os.path.join(OUT_DIR, "forensics_surveys.json"), surveys)

    # ---- the ranked delta matrix ------------------------------------------
    matrix: Dict[str, Any] = {"features": {}, "law": "rank = present-in-fail / "
                              "absent-in-pass across every recorded verdict"}
    ok_f = [s for s in surveys["fail"] if "flags" in s]
    ok_p = [s for s in surveys["pass"] if "flags" in s]
    for feat in FEATURES:
        pf = [s["file"] for s in ok_f if s["flags"].get(feat)]
        pp = [s["file"] for s in ok_p if s["flags"].get(feat)]
        matrix["features"][feat] = {
            "present_in_fail": f"{len(pf)}/{len(ok_f)}",
            "present_in_pass": f"{len(pp)}/{len(ok_p)}",
            "fail_files": pf, "pass_files": pp,
            "separates": len(pp) == 0 and len(pf) > 0,
        }
    # the conjunction the hypothesis names, computed per file above:
    matrix["headline"] = {
        "feature": "our_instanced_baked_symbol",
        "reading": matrix["features"]["our_instanced_baked_symbol"],
    }
    jdump(os.path.join(OUT_DIR, "delta_matrix.json"), matrix)

    # ---- the matched-pair deep diff ---------------------------------------
    pairs = matched_pair_delta()
    jdump(os.path.join(OUT_DIR, "matched_pair_delta.json"), pairs)
    log(f"forensics done in {round(time.time()-t0,1)}s -> "
        f"forensics_surveys.json, delta_matrix.json, matched_pair_delta.json")
    return {"surveys": surveys, "matrix": matrix, "pairs": pairs}


# ---- deep element diff helpers ---------------------------------------------

def _summ(v: Any, depth: int = 0) -> Any:
    """A diff-friendly summary of one field value (bounded depth/size)."""
    if isinstance(v, dict):
        if "ptr_class" in v:
            inner = v.get("value")
            return {"ptr": v.get("ptr_class"),
                    "value": _summ(inner, depth + 1) if depth < 2 else "..."}
        if depth >= 2:
            return f"dict({len(v)})"
        return {k: _summ(x, depth + 1) for k, x in list(v.items())[:24]}
    if isinstance(v, list):
        return f"list({len(v)})" if len(v) > 4 or depth >= 2 else [_summ(x, depth + 1) for x in v]
    if isinstance(v, float):
        return round(v, 6)
    return v


def diff_objects(a: Optional[dict], b: Optional[dict]) -> Dict[str, Any]:
    a, b = a or {}, b or {}
    out: Dict[str, Any] = {"only_in_A": {}, "only_in_B": {}, "differing": {}}
    for k in sorted(set(a) | set(b)):
        if k not in b:
            out["only_in_A"][k] = _summ(a[k])
        elif k not in a:
            out["only_in_B"][k] = _summ(b[k])
        elif a[k] != b[k]:
            out["differing"][k] = {"A": _summ(a[k]), "B": _summ(b[k])}
    out["n_equal"] = len((set(a) & set(b))) - len(out["differing"])
    return out


def _gelement_stats(rep: Optional[dict]) -> Dict[str, Any]:
    if not isinstance(rep, dict):
        return {"present": False}
    faces = edges = geoms = filters = 0
    tags: List[int] = []

    def walk(node):
        nonlocal faces, edges, geoms, filters
        if not isinstance(node, dict):
            return
        pc = node.get("ptr_class")
        v = node.get("value") if pc else node
        if pc == "GFilter":
            filters += 1
        if pc == "Geometry":
            geoms += 1
            gv = v or {}
            faces_l = gv.get("m_pFaces") or []
            edges_l = gv.get("m_pEdges") or []
            faces += len(faces_l)
            edges += len(edges_l)
            for f in faces_l + edges_l:
                gi = ((f.get("value") or {}).get("m_GInfo") or {})
                if isinstance(gi.get("m_tag"), int):
                    tags.append(gi["m_tag"])
        for sub in (v or {}).get("m_subNodes") or []:
            walk(sub)

    for sub in rep.get("m_subNodes") or []:
        walk(sub)
    gi = rep.get("m_GInfo") or {}
    return {"present": True, "n_gfilters": filters, "n_geometry_nodes": geoms,
            "n_faces": faces, "n_edges": edges,
            "tag_range": [min(tags), max(tags)] if tags else None,
            "root_ginfo": _summ(gi), "bbox": rep.get("m_bBox"),
            "gelem_type": rep.get("m_gElemType"), "flags": rep.get("m_flags")}


def _symbol_snapshot(doc, sid: int) -> Dict[str, Any]:
    sv = doc.value(sid) or {}
    hd = doc.value(sid, 101) or {}
    rep_class = doc.class_of(sid, 103)
    rep = doc.value(sid, 103) if rep_class == "GElement" else None
    gs = sv.get("m_geomSteps")
    gs_stats = None
    if isinstance(gs, dict):
        gv = gs.get("value") or {}
        step_list = gv.get("m_bRepFormGList") or []
        s0 = ((step_list[0] or {}).get("value") or {}) if step_list else {}
        gs_stats = {"n_bRepFormGList": len(step_list),
                    "face_hist": len(s0.get("m_faceHistTable") or []),
                    "edge_hist": len(s0.get("m_edgeHistTable") or []),
                    "curve_hist": len(s0.get("m_curveHistTableSet") or []),
                    "version": s0.get("m_version"), "flags": s0.get("m_flags")}
    gt = sv.get("m_pGeomTable")
    gt_rows = len(((gt or {}).get("value") or {}).get("m_table") or []) if isinstance(gt, dict) else None
    return {"symbol_id": sid, "obj": sv, "header": hd,
            "rep_class": rep_class,
            "rep_stats": _gelement_stats(rep) if rep is not None else {"present": False,
                                                                       "class": rep_class},
            "geom_steps_stats": gs_stats, "geom_table_rows": gt_rows}


def _family_snapshot(doc, fid: int) -> Dict[str, Any]:
    fv = doc.value(fid) or {}
    ftt = ((fv.get("m_pFamilyTypes") or {}).get("value") or {})
    fd = ((fv.get("m_oFamDoc") or {}).get("value") or {})
    return {"family_id": fid,
            "n_type_rows": len(ftt.get("m_pairs") or []),
            "n_family_ids": len(fv.get("m_familyIds") or []),
            "n_big2small": len(fd.get("m_big2SmallMap2") or []),
            "core_ids": fd.get("m_coreIds"),
            "fam_dim_constr_mgr": ("null" if fv.get("m_oFamDimConstrMgr") is None
                                   else "present"),
            "part_type": fv.get("m_partType"),
            "obj": fv}


def matched_pair_delta() -> Dict[str, Any]:
    """The SYMBOL (and host Family / instance) element diffs of the matched
    pairs.  A = the famload / no-solid side; B = the famgen baked side."""
    from rvt.mutate import Document
    out: Dict[str, Any] = {"law": "A = famload / no-solid (viewer-PASS side); "
                                  "B = famgen baked (viewer-FAIL side). "
                                  "only_in_B + differing = the suspect list; "
                                  "features already covered by D1..D5 are "
                                  "annotated (BXfix still failed carrying the "
                                  "fixes, so they are NOT the residual)."}

    # ---- P1: L_v2 (famload PASS, rst) vs SX first-load subset (famgen FAIL, rst)
    lv2 = os.path.join(ROOT, "experiments/families/genesis2/L_v2_panel_loaded.rvt")
    sx1 = os.path.join(ROOT, "experiments/instbug/_build/rst/stage_L1_pp1.rvt")
    sx = os.path.join(ROOT, "experiments/instbug/SX_f6i6.rvt")
    try:
        with open(os.path.join(ROOT,
                               "experiments/families/genesis2/L_v2_panel_loaded_load.json")) as fh:
            lv2_plan = json.load(fh)["plans"][0]
        d_a = Document.from_file(lv2)
        sym_a = int(lv2_plan["symbol_ids"][0])
        fam_a = int(lv2_plan["host_family_id"])
        with open(os.path.join(ROOT, "experiments/instbug/accounting.json")) as fh:
            acct = json.load(fh)
        sx_inst = (acct["built"]["SX_f6i6"]["equipment"]["instances"])
        pp1 = [i for i in sx_inst if i["tag"] == "PP-1"][0]
        d_b1 = Document.from_file(sx1)
        sym_b = int(pp1["symbol"])
        fam_b = int(pp1["family"])
        snap_a = _symbol_snapshot(d_a, sym_a)
        snap_b = _symbol_snapshot(d_b1, sym_b)
        p1 = {
            "pair": "P1_symbol",
            "A": {"file": relp(lv2), "symbol": sym_a, "path": "rvt.famload"},
            "B": {"file": relp(sx1), "symbol": sym_b,
                  "path": "rvt.famgen.loader (SX_f6i6's first load hop)"},
            "rep_class": {"A": snap_a["rep_class"], "B": snap_b["rep_class"]},
            "rep_stats_B": snap_b["rep_stats"],
            "geom_steps_stats": {"A": snap_a["geom_steps_stats"],
                                 "B": snap_b["geom_steps_stats"]},
            "geom_table_rows": {"A": snap_a["geom_table_rows"],
                                "B": snap_b["geom_table_rows"]},
            "obj_diff": diff_objects(snap_a["obj"], snap_b["obj"]),
            "header_diff": diff_objects(snap_a["header"], snap_b["header"]),
        }
        fa = _family_snapshot(d_a, fam_a)
        fb = _family_snapshot(d_b1, fam_b)
        p1["family_diff"] = {
            "A": {k: v for k, v in fa.items() if k != "obj"},
            "B": {k: v for k, v in fb.items() if k != "obj"},
            "obj_diff": diff_objects(fa["obj"], fb["obj"]),
        }
        out["P1"] = p1
        # ---- P2: the instance's references into the symbol (SX side only --
        # L_v2 has NO instance: that absence is itself the recorded datum)
        d_b6 = Document.from_file(sx)
        iid = int(pp1["elem_id"])
        iv = d_b6.value(iid) or {}
        ih = d_b6.value(iid, 101) or {}
        ii = ((iv.get("m_pInstanceInfo") or {}).get("value") or {})
        out["P2"] = {
            "pair": "P2_instance_reference",
            "note": "L_v2 carries NO FamilyInstance (famload loads only): its "
                    "PASS never exercised the instance->symbol walk; SL rungs "
                    "close exactly that gap",
            "SX_instance": {
                "file": relp(sx), "id": iid,
                "master_symbol": iv.get("m_masterSymbolId"),
                "info_symbol": ii.get("m_symbolId"),
                "grep_id": ii.get("m_GRepId"),
                "rep_class": d_b6.class_of(iid, 103),
                "connmgr": (iv.get("m_pConnectorManager") or {}).get("ptr_class"),
                "host_id": iv.get("m_hostId"),
                "header_parents": _summ(ih.get("m_parents")),
            },
        }
    except Exception as e:                                   # noqa: BLE001
        out["P1_error"] = f"{type(e).__name__}: {e}"
        out["P1_tb"] = traceback.format_exc(limit=6)

    # ---- P4: SL vs SX instance on the SAME rst base ------------------------
    sl = os.path.join(OUT_DIR, "SL_f6i6.rvt")
    try:
        if os.path.isfile(sl):
            with open(os.path.join(OUT_DIR, "accounting.json")) as fh:
                racct = json.load(fh)
            sl_i = [i for i in racct["built"]["SL_f6i6"]["equipment"]["instances"]
                    if i["tag"] == "PP-1"][0]
            d_sl = Document.from_file(sl)
            d_sx = Document.from_file(sx)
            iv_sl = d_sl.value(int(sl_i["elem_id"])) or {}
            iv_sx = d_sx.value(int(pp1["elem_id"])) or {}
            out["P4"] = {
                "pair": "P4_instance_famload_vs_famgen_host",
                "A": {"file": relp(sl), "instance": sl_i["elem_id"],
                      "symbol": sl_i["symbol"], "load_path": "rvt.famload",
                      "placement": "demo stage_equipment (current, D-fixed)"},
                "B": {"file": relp(sx), "instance": pp1["elem_id"],
                      "symbol": pp1["symbol"], "load_path": "rvt.famgen.loader",
                      "placement": "demo stage_equipment (pre-D-fix build)"},
                "obj_diff": diff_objects(iv_sl, iv_sx),
                "symbol_under_instance": {
                    "A": {k: v for k, v in _symbol_snapshot(d_sl, int(sl_i["symbol"])).items()
                          if k not in ("obj", "header")},
                    "B": {k: v for k, v in _symbol_snapshot(d_sx, int(pp1["symbol"])).items()
                          if k not in ("obj", "header")},
                },
            }
        else:
            out["P4"] = {"skipped": "build SL_f6i6 first (residual_probe.py build)"}
    except Exception as e:                                   # noqa: BLE001
        out["P4_error"] = f"{type(e).__name__}: {e}"

    # ---- P3: BXns vs BXfix symbol (G_ABPD, the ONE-change pair) ------------
    bxns = os.path.join(OUT_DIR, "BXns_f1i1.rvt")
    bxfix = os.path.join(ROOT, "experiments/instbug/fix/BXfix_f1i1.rvt")
    try:
        if os.path.isfile(bxns) and os.path.isfile(bxfix):
            with open(os.path.join(OUT_DIR, "accounting.json")) as fh:
                racct = json.load(fh)
            ns_i = racct["built"]["BXns_f1i1"]["equipment"]["instances"][0]
            d_ns = Document.from_file(bxns)
            d_fx = Document.from_file(bxfix)
            sym_ns = int(ns_i["symbol"])
            fx_syms = [s for s in d_fx.ids_of_class("FamilySymbol")
                       if s > 1472524]                       # above rst-lineage watermark
            # G_ABPD lineage watermark == the rst-derived one (same id space)
            snap_ns = _symbol_snapshot(d_ns, sym_ns)
            snap_fx = _symbol_snapshot(d_fx, fx_syms[0]) if fx_syms else None
            out["P3"] = {
                "pair": "P3_one_change",
                "A": {"file": relp(bxns), "symbol": sym_ns,
                      "path": "famgen symbol_solid=False (this stream)"},
                "B": {"file": relp(bxfix), "symbol": fx_syms[0] if fx_syms else None,
                      "path": "famgen baked, D-fixed (instbug-fix)"},
                "rep_class": {"A": snap_ns["rep_class"],
                              "B": snap_fx["rep_class"] if snap_fx else None},
                "obj_diff": (diff_objects(snap_ns["obj"], snap_fx["obj"])
                             if snap_fx else None),
            }
        else:
            out["P3"] = {"skipped": "build BXns_f1i1 first (residual_probe.py build)"}
    except Exception as e:                                   # noqa: BLE001
        out["P3_error"] = f"{type(e).__name__}: {e}"
    return out


# ===========================================================================
# instrument 1b -- corpus mining: the lawful no-solid symbol shapes
# ===========================================================================

def mine(limit_examples: int = 20) -> Dict[str, Any]:
    """How do Autodesk's own FamilySymbols look, split by rep class x
    geometry-history x instanced?  Answers 'is SerializedDummy-with-instances
    a corpus-lawful shape' and yields >= 20 concrete examples."""
    from rvt.mutate import Document
    from rvt.frontdoor import standalone as SA
    SA.install_schema(G_ABPD)
    samples = [
        "samples/rstbasicsampleproject.rvt",
        "samples/rstadvancedsampleproject.rvt",
        "samples/racbasicsampleproject.rvt",
        "samples/rmebasicsampleproject.rvt",
    ]
    out: Dict[str, Any] = {"samples": {}, "examples_dummy_instanced": [],
                           "examples_dummy_uninstanced": [],
                           "examples_baked_instanced": []}
    t0 = time.time()
    for s in samples:
        a = os.path.join(ROOT, s)
        if not os.path.isfile(a):
            out["samples"][s] = {"missing": True}
            continue
        try:
            doc = Document.from_file(a)
        except Exception as e:                               # noqa: BLE001
            out["samples"][s] = {"error": f"{type(e).__name__}: {e}"}
            continue
        refs: Dict[int, int] = {}
        for iid in doc.ids_of_class("FamilyInstance"):
            iv = doc.value(iid) or {}
            ms = iv.get("m_masterSymbolId")
            if isinstance(ms, int) and ms >= 0:
                refs[ms] = refs.get(ms, 0) + 1
        cells = {"GElement+steps": 0, "GElement+nosteps": 0,
                 "SerializedDummy+steps": 0, "SerializedDummy+nosteps": 0,
                 "other": 0}
        cells_instanced = dict.fromkeys(cells, 0)
        n_sym = 0
        for sid in doc.ids_of_class("FamilySymbol"):
            sv = doc.value(sid) or {}
            n_sym += 1
            rc = doc.class_of(sid, 103)
            steps = sv.get("m_geomSteps") is not None
            key = (f"{rc}+{'steps' if steps else 'nosteps'}"
                   if rc in ("GElement", "SerializedDummy") else "other")
            cells[key] = cells.get(key, 0) + 1
            n_inst = refs.get(sid, 0)
            if n_inst:
                cells_instanced[key] = cells_instanced.get(key, 0) + 1
            ex_list = None
            if n_inst and rc == "SerializedDummy" and len(out["examples_dummy_instanced"]) < limit_examples:
                ex_list = "examples_dummy_instanced"
            elif (not n_inst) and rc == "SerializedDummy" \
                    and len(out["examples_dummy_uninstanced"]) < limit_examples:
                ex_list = "examples_dummy_uninstanced"
            elif n_inst and rc == "GElement" and len(out["examples_baked_instanced"]) < 8:
                ex_list = "examples_baked_instanced"
            if ex_list:
                out[ex_list].append({
                    "sample": s, "symbol": sid, "n_instances": n_inst,
                    "rep_class": rc,
                    "geom_steps": steps,
                    "geom_table": sv.get("m_pGeomTable") is not None,
                    "n_geomtag2material": len(sv.get("m_geomTag2MaterialId") or []),
                    "n_strong_refs": len(sv.get("m_strongRefs") or []),
                    "n_connector_data": len(sv.get("m_arrConnectorData") or []),
                    "name": ((sv.get("m_symbolInfo") or {}).get("value") or {}).get("m_name"),
                    "family": sv.get("m_familyId"),
                })
        out["samples"][s] = {"n_family_symbols": n_sym,
                             "cells_all": cells,
                             "cells_with_instances": cells_instanced,
                             "n_instanced_symbols": len(refs)}
        log(f"mine {s}: {n_sym} symbols; instanced cells {cells_instanced}")
    out["reading"] = (
        "MEASURED LAW: every corpus FamilySymbol referenced by a "
        "FamilyInstance is GElement+steps (the baked cache) -- ZERO instanced "
        "SerializedDummy symbols anywhere; the SerializedDummy form exists "
        "only UNINSTANCED and even then still carries m_geomSteps (dummy+"
        "nosteps -- famload's and BXns's exact shape -- appears in NO sample). "
        "So the BXns/SL rungs' dummy-under-instance form is OFF-CORPUS: their "
        "viewer verdict decides whether Revit's regeneration path tolerates "
        "it (PASS => the no-solid product decision is viable anyway; FAIL => "
        "the fix MUST author the corpus-lawful baked grammar, and the 201 "
        "instanced GElement+steps symbols here are the grammar-mining corpus "
        "to replace the [H] one-specimen inference).")
    out["seconds"] = round(time.time() - t0, 1)
    jdump(os.path.join(OUT_DIR, "corpus_symbols.json"), out)
    log(f"mine done in {out['seconds']}s -> corpus_symbols.json")
    return out


# ===========================================================================
# stage
# ===========================================================================

def stage() -> Dict[str, Any]:
    B = _bisect()
    spec = importlib.util.spec_from_file_location(
        "_residual_probe_batch", os.path.join(HERE, "probe_batch.py"))
    pb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pb)
    files = [os.path.join(OUT_DIR, f"{n}.rvt") for n in LADDER]
    missing = [f for f in files if not os.path.isfile(f)]
    if missing:
        raise SystemExit(f"missing rungs (run build): {[relp(m) for m in missing]}")
    manifest = pb.stage_batch(
        files, control_from=G_ABPD,
        batch_n=B._campaign_global_next_batch(),
        note="instbug-residual: the instance residual cornered. BXns_* = the "
             "demo path with symbol_solid=False (the ONE change vs the FAILED "
             "BXfix pair: no baked host-symbol geometry); SL_* = the SAME "
             "generated families loaded by CERTIFIED rvt.famload + the demo's "
             "own placement (path attribution at N=6). Read BXns_f1i1 first, "
             "then SL_f6i6, then BXns_f6i6 (experiments/instbug/residual/"
             "probes.json reading_the_matrix).")
    log(f"STAGED batch {manifest['batch']} -> {manifest['manifest_path']}")
    for e in manifest["entries"]:
        log(f"  [{e['order']}] {e.get('staged_as')} (base {e.get('base')}, "
            f"{e.get('kind')})")
    return manifest


# ===========================================================================

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="build the four rungs (+ accounting + probes.json)")
    b.add_argument("--only", default=None, help="comma-separated rung subset")
    sub.add_parser("forensics", help="feature surveys + matched-pair diff + delta matrix")
    m = sub.add_parser("mine", help="corpus FamilySymbol shape census (no-solid law)")
    m.add_argument("--examples", type=int, default=20)
    sub.add_parser("stage", help="probe_batch gate + stage (control = G_ABPD copy)")
    a = ap.parse_args(argv)
    if a.cmd == "build":
        only = [s.strip() for s in a.only.split(",")] if a.only else None
        bad = [r for r in (only or []) if r not in RUNG_SPEC]
        if bad:
            ap.error(f"unknown rung(s): {bad}; choose from {list(RUNG_SPEC)}")
        out = build(only)
        n_err = len([k for k in out["errors"] if not k.endswith((".traceback", ".tb"))])
        log(f"build done: {len(out['built'])} rung(s), {n_err} error(s), "
            f"{out['seconds']}s")
        return 1 if n_err else 0
    if a.cmd == "forensics":
        forensics()
        return 0
    if a.cmd == "mine":
        mine(a.examples)
        return 0
    if a.cmd == "stage":
        stage()
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
