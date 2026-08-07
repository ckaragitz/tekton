"""pal_census.py -- KEYED corpus census of the palette bucket's classes
(PropertySetElement + MaterialElem) across the six 2026 samples + K4 + Y9.

Purpose (genesis-palette-fix stream, THE ONE NAMED CONSTRUCTOR DEFECT): the
pooled linter (rvt.objlint) flattens ParamValueSet arrays positionally and so
misses KEYED structure.  This census keys every ParamValueSet entry by its
m_paramId and mines, per class + shape:

  * the SHAPE SIGNATURE of each PropertySetElement = (m_propertySetType, the
    sorted tuple of double / int / string / elementid / bool param IDS, and
    which sub-set containers are PRESENT-empty vs NULL);
  * per (shape, param id): is the VALUE constant across every instance in the
    corpus (=> format DEFAULT / machinery, reproduce) or varying (=> a FREE
    physical value, ours to state);
  * the on-disk ORDER of param ids within each set (the serialisation order
    the corpus exhibits);
  * per MaterialElem: the appearance / structural / thermal linkage web
    (m_appearanceAssetId, m_structuralPropertySetId, m_assetMap.
    m_sharedAssetIdMap, m_oStructuralPropertySetNew) so the referential
    surgery an in-place material rung performs is stated exactly.

Read-only.  Writes ``pal_census.json`` next to itself.  Reproduce:

    .venv/bin/python experiments/genesis/subst_k4/palette_fix/pal_census.py
"""
from __future__ import annotations

import collections
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.mutate import Document  # noqa: E402

SAMPLES = [
    "rstbasicsampleproject", "rstadvancedsampleproject",
    "racbasicsampleproject", "racadvancedsampleproject",
    "rmebasicsampleproject", "dach-sample-project",
]
EXTRA_FILES = {
    "K4": os.path.join(ROOT, "experiments/genesis/triage/K4.rvt"),
    "Y9": os.path.join(ROOT, "experiments/genesis/subst_k4/Y9.rvt"),
}
OUT_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pal_census.json")


def log(m):
    print(m, flush=True)


def _paramset_entries(v):
    """Return {container: (present, [(paramId, value), ...])} for the five
    ParamValueSet containers of a PropertySetElement's m_oParamSet."""
    ps = ((v.get("m_oParamSet") or {}).get("value") or {})
    out = {}
    for key in ("m_pDoubleParams", "m_pIntParams", "m_pAStringParams",
                "m_pElementIdParams", "m_pBoolParams"):
        sub = ps.get(key)
        if sub is None:
            out[key] = (False, [])
        else:
            arr = ((sub.get("value") or {}).get("m_paramSet") or [])
            out[key] = (True, [(int(x.get("m_paramId")), x.get("m_value")) for x in arr])
    return out


def shape_signature(v):
    ents = _paramset_entries(v)
    pst = v.get("m_propertySetType")
    sig = {"m_propertySetType": pst}
    for key, (present, arr) in ents.items():
        ids = tuple(pid for pid, _ in arr)
        sig[key] = {"present": present, "n": len(arr), "ids": ids}
    return sig, ents


def census(docs):
    """docs = [(label, Document)]."""
    # shape key -> aggregate
    shapes = {}
    order_witness = collections.defaultdict(collections.Counter)   # (cls,container) -> ('asc'/'desc'/'other') counts
    mat_link = collections.defaultdict(list)
    for label, doc in docs:
        for eid in doc.ids_of_class("PropertySetElement"):
            v = doc.value(eid) or {}
            sig, ents = shape_signature(v)
            skey = json.dumps(sig, sort_keys=True, default=str)
            agg = shapes.setdefault(skey, {
                "shape": sig, "count": 0, "files": collections.Counter(),
                "examples": [], "values": collections.defaultdict(list),
            })
            agg["count"] += 1
            agg["files"][label] += 1
            if len(agg["examples"]) < 6:
                agg["examples"].append([label, int(eid)])
            for key, (present, arr) in ents.items():
                for pid, val in arr:
                    agg["values"][(key, pid)].append(repr(val)[:60])
                # serialisation order of ids within the set
                ids = [pid for pid, _ in arr]
                if len(ids) >= 2:
                    if ids == sorted(ids):
                        order_witness[key]["ascending"] += 1
                    elif ids == sorted(ids, reverse=True):
                        order_witness[key]["descending"] += 1
                    else:
                        order_witness[key]["other"] += 1
        for eid in doc.ids_of_class("MaterialElem"):
            v = doc.value(eid) or {}
            mat = (v.get("m_pMaterial") or {}).get("value") or {}
            am = ((mat.get("m_assetMap") or {}).get("m_sharedAssetIdMap") or [])
            keys = tuple(sorted(str((x.get("first") or {}).get("m_value", "")) for x in am))
            mat_link[label].append({
                "id": int(eid), "name": mat.get("m_name"),
                "appearance": mat.get("m_appearanceAssetId"),
                "structuralPropertySetId": mat.get("m_structuralPropertySetId"),
                "sharedAssetIdMap_keys": keys,
                "sharedAssetIdMap_targets": [x.get("second") for x in am],
                "inlineStructuralNew": bool(mat.get("m_oStructuralPropertySetNew")),
                "pvsAString": bool(v.get("m_pParamValueSetAString")),
                "pvsDouble": bool(v.get("m_pParamValueSetDouble")),
                "aAProperties_len": len(((mat.get("m_asset") or {}).get("m_aAProperties") or [])),
                "asset_sName": (mat.get("m_asset") or {}).get("m_sName"),
            })
    # summarise per-shape value constancy
    shape_rows = []
    for skey, agg in shapes.items():
        const, free = [], []
        for (key, pid), vals in sorted(agg["values"].items()):
            distinct = sorted(set(vals))
            row = {"container": key, "paramId": pid, "distinct": len(distinct),
                   "sample_values": distinct[:5]}
            (const if len(distinct) == 1 else free).append(row)
        shape_rows.append({
            "shape": agg["shape"], "count": agg["count"],
            "files": dict(agg["files"]), "examples": agg["examples"],
            "constant_params": const, "free_params": free,
        })
    shape_rows.sort(key=lambda r: -r["count"])
    return {"propertyset_shapes": shape_rows,
            "param_order_witness": {k: dict(v) for k, v in order_witness.items()},
            "material_linkage": dict(mat_link)}


def main():
    t0 = time.time()
    docs = []
    for p in SAMPLES:
        try:
            docs.append((p, Document.load(p)))
            log(f"  loaded {p}")
        except Exception as ex:                                   # pragma: no cover
            log(f"  !! {p}: {ex}")
    for lab, path in EXTRA_FILES.items():
        docs.append((lab, Document.from_file(path)))
        log(f"  loaded {lab} from {os.path.relpath(path, ROOT)}")
    rep = census(docs)
    with open(OUT_JSON, "w") as fh:
        json.dump(rep, fh, indent=1, default=str)
    log(f"\nwrote {OUT_JSON} ({time.time() - t0:.1f}s)")
    log(f"\n=== PropertySetElement SHAPES (n={len(rep['propertyset_shapes'])}) ===")
    for r in rep["propertyset_shapes"]:
        sh = r["shape"]
        d, s, i, e, b = (sh["m_pDoubleParams"], sh["m_pAStringParams"],
                         sh["m_pIntParams"], sh["m_pElementIdParams"], sh["m_pBoolParams"])
        log(f"\n-- count={r['count']:>3} type={sh['m_propertySetType']} files={r['files']}")
        log(f"   dbl n={d['n']:<3} present={d['present']}  ids [{max(d['ids']) if d['ids'] else '-'} .. {min(d['ids']) if d['ids'] else '-'}]")
        log(f"   str n={s['n']:<3} present={s['present']}  ids {list(s['ids'])}")
        log(f"   int n={i['n']:<3} present={i['present']}  ids {list(i['ids'])}")
        log(f"   eid n={e['n']:<3} present={e['present']}  bool n={b['n']} present={b['present']}")
        cfree = len(r['free_params']); cconst = len(r['constant_params'])
        log(f"   value census: {cfree} FREE params, {cconst} CONSTANT (format-default) params")
        for fp in r["free_params"][:60]:
            log(f"      FREE  {fp['container']:<20} {fp['paramId']:>10}  ({fp['distinct']} distinct) e.g. {fp['sample_values'][:3]}")
        for cp in r["constant_params"][:60]:
            log(f"      CONST {cp['container']:<20} {cp['paramId']:>10}  = {cp['sample_values'][0]}")
        log(f"   examples: {r['examples']}")
    log("\n=== PARAM SERIALISATION ORDER (per container) ===")
    for k, v in rep["param_order_witness"].items():
        log(f"   {k}: {v}")


if __name__ == "__main__":
    main()
