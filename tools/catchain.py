#!/usr/bin/env python
"""catchain -- THE CHAIN PROBES (catchain stream, post-verdict-#41).

WHERE THE HUNT STANDS (genesis-audit verdicts #36..#41 + layout-law).  With
unit blobs mandatory (#36), the corpus says: donor-BODY-derived famdocs
PASS in any order / field mix probed; famgen-assembled famdocs FAIL; record
ORDER is exonerated in BOTH directions (M1 FAIL, M2 PASS); and every
single-field byte morph -- order-cell dedup (M3), sparse counters (M4),
partType -1 (M5), m_deletion prefix (M6) -- FAILS alone (#41).  The
surviving candidates from ``experiments/layout/layout_diff.json``'s 12
perfect separators are the ENTANGLED residues a byte morph cannot flip
coherently: the family CATEGORY itself (+ everything category-coupled),
the 1-row-vs-5-row FamilyTypeTable shape, the locked/param BIP group, the
missing materials order-cell group -- possibly a CONJUNCTION (all 12
co-vary in the corpus).

THIS ROUND rebuilds the B0 recipe (G_ABPD + ONE famgen panelboard + ONE
instance, the certified famgen chain under
``famload_hostfix.corpus_symbol_form``) with ONE recipe change each,
through the FULL chain -- no byte surgery; the chain authors every coupled
surface coherently (``src/rvt/famgen/catprobe.py`` is the opt-in override
layer; no shared famgen file is edited):

  BX_conj             ALL famgen-side residues fixed AT ONCE: GM category
                      (+partType -1) + 5-row types + locked BIP + materials
                      group + order-cell dedup + sparse counters +
                      m_deletion prefix + refTypeIds [4] -- machine-checked
                      to flip ALL 12 corpus separators to the PASS side.
                      The conjunction UPPER BOUND: FAIL here = the defect is
                      outside everything the byte-observable corpus
                      enumerates.
  BX_cat_gm           the same panelboard product authored under GENERIC
                      MODEL (-2000151, corpus-verified) end to end: famdoc
                      self-Family category + partType -1, host Family (the
                      self-Family object copy), host FamilySymbol /
                      surrogates / FamilyInstance / ADocument registration
                      under GM, symbol geometry on the host's GM projection
                      GStyle, the placement scrub's category constant.
  BX_types_5          B0 + the donor's FIVE-row FamilyTypeTable: leading
                      blank ' ' current-values pair + 4 real types with
                      distinct names/ratings, m_idx = 1 [mined SUB_ALL/B7].
  BX_bip              B0 + the locked/param BIP group: -1001205 in m_locked
                      + the identityData palette (no value row -- the
                      donor's exact shape).
  BX_conj_minus_cat   BX_conj WITHOUT the category flip (electrical
                      equipment + partType 14 kept) -- pre-built so a
                      conj-PASS round starts its bisection free.
  BX_conj_minus_types BX_conj WITHOUT the 5-row table (1 pair, idx 0).

Every probe: validator 0 errors, blob-carrying (machine-verified nonce),
four-registry coherent, refs resolved, EXACTLY ONE dangling-free instance,
product FamilyInstanceConnectorManager, corpus-lawful symbol form, and the
emitted famdoc's FEATURE VECTOR machine-verified against the intended
recipe (layout_diff's own ``unit_features`` / separator candidates).

STAGE ONLY -- probe_batch staging with a byte-identical certified G_ABPD
control; the orchestrator uploads.  Reading order = probes.json
(BX_conj FIRST -- the biggest split).

TERRITORY: this file, src/rvt/famgen/catprobe.py, experiments/catchain/**,
tests/test_catchain.py, docs/inbox/catchain.md.  IMPORTS (never edits):
tools/layout_diff.py (UnitX/unit_features/CANDIDATES), tools/famdoc_blobs.py
(blob_proof, campaign batch numbering), tools/bisect_instance_bug.py
(demo model, placement, account), tools/ifc_intent.py (build_product,
host_watermark), tools/probe_batch.py, rvt.famload_hostfix, rvt.famgen.*.

USAGE (repo root)::

    .venv/bin/python tools/catchain.py mine              # corpus_shapes.json
    .venv/bin/python tools/catchain.py build             # all 6 probes
    .venv/bin/python tools/catchain.py build --only BX_conj
    .venv/bin/python tools/catchain.py verify            # re-run the gates
    .venv/bin/python tools/catchain.py stage             # probe_batch + control
"""
from __future__ import annotations

import argparse
import contextlib
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

OUT_DIR = os.path.join(ROOT, "experiments", "catchain")
BUILD_DIR = os.path.join(OUT_DIR, "_build")
ACCT = os.path.join(OUT_DIR, "accounting.json")
SHAPES = os.path.join(OUT_DIR, "corpus_shapes.json")

G_ABPD = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "compose",
                      "G_ABPD.rvt")

OST_GENERIC_MODEL = -2000151          # corpus-verified below (mine + build)
OST_ELECTRICAL_EQUIPMENT = -2001040

#: staging / reading order = maximum information first (the biggest split
#: FIRST: conj partitions "inside the enumerated residues" from "outside")
LADDER = ("BX_conj", "BX_cat_gm", "BX_types_5", "BX_bip",
          "BX_conj_minus_cat", "BX_conj_minus_types")

#: per-probe recipe: category override (None = keep electrical equipment)
#: + catprobe.apply_residues flags
RECIPES: Dict[str, Dict[str, Any]] = {
    "BX_conj": {
        "category": OST_GENERIC_MODEL, "part_type": -1,
        "residues": dict(types5=True, bip=True, materials=True,
                         dedup_cell=True, sparse_counters=True,
                         deletion_prefix=True, ref_type_ids=True),
    },
    "BX_cat_gm": {
        "category": OST_GENERIC_MODEL, "part_type": -1,
        "residues": {},
    },
    "BX_types_5": {
        "category": None, "part_type": None,
        "residues": dict(types5=True),
    },
    "BX_bip": {
        "category": None, "part_type": None,
        "residues": dict(bip=True),
    },
    "BX_conj_minus_cat": {
        "category": None, "part_type": None,
        "residues": dict(types5=True, bip=True, materials=True,
                         dedup_cell=True, sparse_counters=True,
                         deletion_prefix=True, ref_type_ids=True),
    },
    "BX_conj_minus_types": {
        "category": OST_GENERIC_MODEL, "part_type": -1,
        "residues": dict(bip=True, materials=True, dedup_cell=True,
                         sparse_counters=True, deletion_prefix=True,
                         ref_type_ids=True),
    },
}

AXES = {
    "BX_conj": "CONJUNCTION upper bound: every enumerated famgen-side "
               "residue fixed at once through the chain (all 12 corpus "
               "separators flipped to the PASS side, machine-checked)",
    "BX_cat_gm": "the CATEGORY axis alone: the panelboard product authored "
                 "under Generic Model (-2000151) + partType -1 through "
                 "every coupled surface of the chain",
    "BX_types_5": "the TYPE-TABLE axis alone: the donor's 5-pair shape "
                  "(blank ' ' current-values pair first, 4 real types with "
                  "distinct names/ratings, m_idx 1)",
    "BX_bip": "the LOCKED/PARAM BIP axis alone: -1001205 in m_locked + the "
              "identityData palette (the donor's exact shape: no value row)",
    "BX_conj_minus_cat": "BX_conj minus the category flip (bisection "
                         "pre-build: category NECESSARY iff this FAILS "
                         "while BX_conj PASSES)",
    "BX_conj_minus_types": "BX_conj minus the 5-row table (bisection "
                           "pre-build: the table shape NECESSARY iff this "
                           "FAILS while BX_conj PASSES)",
}

#: the 12 perfect separators of layout_diff.json (candidate-name ->
#: True = the FAIL-side value).  Every probe's emitted famdoc is
#: machine-checked against its intended vector before staging.
SEP12 = (
    "cell_dup_identity_groups",
    "cell_no_materials_group",
    "hdr_deletion_elements_only",
    "hdr_deletion_lacks_category",
    "sf_absorbed_dense (no history gap)",
    "sf_category_is_ours_electrical",
    "sf_locked_no_bip",
    "sf_partType_set (not -1)",
    "sf_predefinedLimitIdx_small",
    "sf_refTypeIds_empty",
    "sf_single_type_pair",
    "sf_type_idx_zero",
)

#: which separators each recipe axis flips to the PASS side (False)
_FLIPS = {
    "category": ("sf_category_is_ours_electrical", "sf_partType_set (not -1)"),
    "types5": ("sf_single_type_pair", "sf_type_idx_zero"),
    "bip": ("sf_locked_no_bip",),
    "materials": ("cell_no_materials_group",),
    "dedup_cell": ("cell_dup_identity_groups",),
    "sparse_counters": ("sf_absorbed_dense (no history gap)",
                        "sf_predefinedLimitIdx_small"),
    "deletion_prefix": ("hdr_deletion_elements_only",
                        "hdr_deletion_lacks_category"),
    "ref_type_ids": ("sf_refTypeIds_empty",),
}


def expected_separators(name: str) -> Dict[str, bool]:
    """The intended separator vector of one probe (True = FAIL-side/B0
    value kept, False = flipped to the PASS side)."""
    spec = RECIPES[name]
    vec = {c: True for c in SEP12}
    axes = list(spec["residues"].keys())
    if spec["category"] is not None:
        axes.append("category")
    for ax in axes:
        for cand in _FLIPS.get(ax, ()):
            vec[cand] = False
    return vec


def log(msg: str) -> None:
    print(f"[catchain] {msg}", flush=True)


def relp(p: str) -> str:
    try:
        r = os.path.relpath(p, ROOT)
        return r if not r.startswith("..") else p
    except ValueError:                                     # pragma: no cover
        return p


def jdump(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=1, default=str)
        fh.write("\n")


def _mod(fname: str, alias: str):
    spec = importlib.util.spec_from_file_location(alias, os.path.join(HERE, fname))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


_LD = _BLOBS = None


def _ld():
    """tools/layout_diff.py (UnitX, unit_features, CANDIDATES) -- imported,
    never edited; its module body only defines helpers."""
    global _LD
    if _LD is None:
        _LD = _mod("layout_diff.py", "_catchain_layout_diff")
    return _LD


def _blobs():
    """tools/famdoc_blobs.py (blob_proof + campaign batch numbering)."""
    global _BLOBS
    if _BLOBS is None:
        _BLOBS = _mod("famdoc_blobs.py", "_catchain_famdoc_blobs")
    return _BLOBS


def md5_of(path: str) -> str:
    return _blobs().md5_of(path)


# ===========================================================================
# mine -- the corpus shapes (the donor laws the recipes reproduce)
# ===========================================================================

def mine() -> Dict[str, Any]:
    """Extract the donor-side self-Family shapes the recipes reproduce
    (SUB_ALL = the matched-pair PASS anchor; B7 = the pure donor famdoc;
    B0 = the famgen FAIL anchor) into ``corpus_shapes.json``."""
    LD = _ld()
    out: Dict[str, Any] = {"generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                           "tool": "tools/catchain.py mine", "files": {}}
    paths = {"SUB_ALL": LD.SUB_ALL,
             "B7": os.path.join(ROOT, "experiments", "famdoc_blobs", "B7.rvt"),
             "B0": LD.FAIL_FILES["B0"]}
    for name, path in paths.items():
        u = LD.UnitX(path)
        rec, sf = u.self_family()
        hdr = u.header_of(rec["eid"])
        unit_ids = set(u.ids(102))
        dele = ((hdr.get("m_parents") or {}).get("value") or {}).get("m_deletion") or []
        ftt = ((sf.get("m_pFamilyTypes") or {}).get("value") or {})
        pairs = ftt.get("m_pairs") or []
        fp = ((sf.get("m_familyParams") or {}).get("value") or {}).get("m_params") or []
        cells = []
        for g in (LD._cell_groups(sf) if pairs is not None else []):
            cells.append({"group": (g.get("m_groupTypeId") or {}).get("m_typeId"),
                          "param_ids": list(g.get("m_paramIds") or [])})
        out["files"][name] = {
            "file": relp(path),
            "sf_categoryId": sf.get("m_categoryId"),
            "sf_partType": sf.get("m_partType"),
            "type_table": {
                "m_idx": ftt.get("m_idx"),
                "pairs": [{"name": p.get("name"),
                           "n_rows": len(((p.get("params") or {}).get("m_params")) or [])}
                          for p in pairs],
                "pair0_rows_equal_familyParams": (
                    (((pairs[0].get("params") or {}).get("m_params")) or []) == fp
                    if pairs else None),
            },
            "familyParams_rows": [{k: r.get(k) for k in
                                   ("m_paramId", "m_value", "m_int", "m_str",
                                    "m_elemId", "m_instance")} for r in fp],
            "locked": sf.get("m_lockedParameterIdsForDirectManipulation"),
            "refTypeIds": sf.get("m_refTypeIds"),
            "fsdos": sf.get("m_fsdos"),
            "nextAbsorbedIndex": sf.get("m_nextAbsorbedIndex"),
            "predefinedLimitIdx": sf.get("m_predefinedLimitIdx"),
            "cell_groups": cells,
            "hdr_deletion_nonelement_in_order": [
                d for d in dele if isinstance(d, int) and d not in unit_ids],
            "features": LD.unit_features(u),
        }
    # the GM category id, corpus-verified: the host's own GStyleElem rows
    from rvt.mutate import Document
    doc = Document.from_file(G_ABPD)
    gm = [(gid, (doc.value(gid) or {}).get("m_gstyleType"))
          for gid in doc.ids_of_class("GStyleElem")
          if (doc.value(gid) or {}).get("m_categoryId") == OST_GENERIC_MODEL]
    out["generic_model_category"] = {
        "id": OST_GENERIC_MODEL,
        "verified_in_schema": "rvt.famgen.skeleton.OST_GENERIC_MODEL "
                              "[VERIFIED from the specimens' m_categoryId + "
                              "the shared BIC list]",
        "verified_on_host": {"file": relp(G_ABPD),
                             "gstyle_rows_(id, m_gstyleType)": gm,
                             "projection_gstyle_present": any(t == 1 for _g, t in gm)},
    }
    out["laws"] = {
        "types5": "donor famdoc table = leading blank ' ' pair whose rows == "
                  "m_familyParams rows, then the real types; m_idx = 1 "
                  "[SUB_ALL and B7 both: 5 pairs, idx 1]",
        "bip": "-1001205 in m_locked (sorts first) + the identityData "
               "palette of the order cell; NO value row [SUB_ALL locked "
               "[-1001205, 3 dims]; B7 locked [-1001205, 1 dim]]",
        "materials": "-1005500 INSTANCE value row on every type + current "
                     "values (m_elemId = material, MAY dangle outside the "
                     "unit [SUB_ALL: 1177727 not a unit id, PASS]); "
                     "MaterialFSDO {category, material, famParam}; "
                     "materials group FIRST in the order cell",
        "counters": "m_nextAbsorbedIndex 3165 / m_predefinedLimitIdx 1963 "
                    "(sparse edit history; index pairs stay dense = the M4 "
                    "morph surface)",
        "deletion": "header m_deletion opens with the non-element parents "
                    "[category, -1005500, -1001205, <material elem>] before "
                    "the element ids",
        "refTypeIds": "[4] on SUB_ALL and B7; [] on B0",
        "category": "the donor famdoc is structural-column -2001330 with "
                    "partType -1; the GM probe authors -2000151 + partType "
                    "-1 (partType follows the category; 14 is the "
                    "electrical panelboard value)",
    }
    jdump(SHAPES, out)
    log(f"corpus shapes -> {relp(SHAPES)}")
    return out


# ===========================================================================
# build -- one probe through the FULL chain
# ===========================================================================

def build_probe(name: str) -> Dict[str, Any]:
    """The B0/BX_layout recipe with this probe's ONE recipe change:
    corpus_symbol_form + (category_override?) + build_product +
    apply_residues + famgen load + demo placement."""
    import bisect_instance_bug as B
    import ifc_intent as T
    from rvt import famload_hostfix as HF
    from rvt.famgen import loader as L
    from rvt.famgen import catprobe as CP
    from rvt.mutate import Document

    spec = RECIPES[name]
    info: Dict[str, Any] = {
        "probe": name, "axis": AXES[name], "base": relp(G_ABPD),
        "recipe": "B0 (G_ABPD + ONE famgen panelboard + ONE instance, "
                  "famgen loader under corpus_symbol_form, demo "
                  "stage_equipment placement) with the probe's recipe "
                  "change applied through the chain",
        "category_override": spec["category"],
        "part_type": spec["part_type"],
        "residues": {k: v for k, v in spec["residues"].items() if v},
    }
    chain_dir = os.path.join(BUILD_DIR, f"{name}_chain")
    if os.path.isdir(chain_dir):
        shutil.rmtree(chain_dir)
    os.makedirs(chain_dir, exist_ok=True)
    outp = os.path.join(OUT_DIR, f"{name}.rvt")

    with contextlib.ExitStack() as st:
        st.enter_context(HF.corpus_symbol_form())
        if spec["category"] is not None:
            ctx = st.enter_context(CP.category_override(
                int(spec["category"]), part_type=int(spec["part_type"]),
                also=[(T, "OST_ELECTRICAL_EQUIPMENT")]))
            info["category_patches"] = ctx["patched"] + ["ifc_intent.OST_ELECTRICAL_EQUIPMENT"]
        model6 = B.demo_model()
        m1 = B.truncate_model(model6, 1)
        current = os.path.join(chain_dir, "stage_L0_base.rvt")
        shutil.copyfile(G_ABPD, current)
        wm = T.host_watermark(current)
        prod = T.build_product(m1.plan_for("PP-1"), start_id=wm + 1, solid=True)
        if not prod.doc.finalized:
            prod.doc.finalize()
        if info["residues"]:
            info["residue_report"] = CP.apply_residues(prod.doc, **spec["residues"])
        # doc-level roundtrip proof AFTER the recipe (every record encodes
        # and decodes back byte-exact -- no residue broke the schema)
        rt = prod.doc.roundtrip()
        info["doc_roundtrip"] = {k: rt.get(k) for k in
                                 ("records", "roundtrip_ok", "failed")}
        if rt.get("failed"):
            raise RuntimeError(f"{name}: residue recipe broke the record "
                               f"roundtrip: {rt.get('failures', [])[:3]}")
        nxt = os.path.join(chain_dir, "stage_L1_pp1.rvt")
        res = L.load_family_into_project(current, nxt, product=prod,
                                         place=False, symbol_solid=True,
                                         report_path=nxt + ".load.json",
                                         validate=False)
        if not res.ok:
            raise RuntimeError(f"{name}: famgen load failed: {res.stop_reason}")
        info["load"] = {"symbol_id": res.plan.symbol_id,
                        "family_id": res.plan.host_family_id,
                        "content_guid": res.plan.guid,
                        "host_watermark": wm,
                        "host_category": res.proofs.get("plan", {}).get("resolved", {})
                                             .get("category_gstyle")}
        loaded = {"PP-1": {"symbol_id": res.plan.symbol_id,
                           "family_id": res.plan.host_family_id,
                           "content_guid": res.plan.guid,
                           "product": prod}}
        erec = B.place_instances(m1, nxt, outp, G_ABPD, loaded)

    insts = erec.get("instances") or []
    info["instance_ids"] = [i["elem_id"] for i in insts]
    info["symbol_id"] = (insts or [{}])[0].get("symbol")
    info["family_id"] = (insts or [{}])[0].get("family")
    dangling = [i for i in insts if (i.get("n_dangling") or 0) != 0]
    if len(insts) != 1 or dangling:
        raise RuntimeError(f"{name}: expected exactly 1 dangling-free "
                           f"instance, got {len(insts)} (dangling: {dangling})")
    info["immediate_parent"] = relp(os.path.join(chain_dir, "stage_L1_pp1.rvt"))
    info["file"] = relp(outp)
    info["md5"] = md5_of(outp)

    # the instance's connector manager class, read from the EMITTED bytes
    doc = Document.from_file(outp)
    cm = (doc.value(info["instance_ids"][0]) or {}).get("m_pConnectorManager")
    info["instance_connmgr"] = (cm.get("ptr_class") if isinstance(cm, dict) else cm)
    # instance header category, read from the EMITTED bytes
    want_cat = spec["category"] if spec["category"] is not None \
        else OST_ELECTRICAL_EQUIPMENT
    info["instance_header_category"] = doc.category_of(info["instance_ids"][0])
    # corpus-lawful symbol form (the BXhf/B0 invariant)
    from rvt import famload_hostfix as HF2
    forms = {}
    for sid in doc.ids_of_class("FamilySymbol"):
        v = doc.value(sid) or {}
        fam = doc.value(v.get("m_familyId") or -1) or {}
        if "PP-" in str(fam.get("m_name") or "") or sid == info["symbol_id"]:
            forms[sid] = HF2.assert_symbol_form(outp, sid)
    bad = [k for k, f in forms.items() if not f["ok"]]
    if bad or not forms:
        raise RuntimeError(f"{name}: symbol form check failed: "
                           f"{bad or 'no PP- symbols found'}")
    info["symbol_form"] = {str(k): {"ok": f["ok"]} for k, f in forms.items()}
    info["expected_instance_category"] = want_cat
    return info


# ===========================================================================
# the FEATURE gate -- the emitted famdoc against the intended recipe
# ===========================================================================

def feature_gate(name: str, path: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    """Decode the emitted probe's added famdoc unit and machine-verify the
    feature vector against the probe's intended recipe -- the layout-law
    stream's own instruments (UnitX / unit_features / CANDIDATES)."""
    LD = _ld()
    u = LD.UnitX(path)
    feats = LD.unit_features(u)
    want = expected_separators(name)
    got = {c: bool(LD.CANDIDATES[c](feats)) for c in SEP12}
    mism = {c: {"want": want[c], "got": got[c]} for c in SEP12
            if want[c] != got[c]}
    rep: Dict[str, Any] = {"features": feats, "separators": got,
                           "separator_mismatches": mism}
    # exact-value checks per active axis
    checks: Dict[str, bool] = {}
    res = spec["residues"]
    cat = spec["category"] if spec["category"] is not None else OST_ELECTRICAL_EQUIPMENT
    checks["categoryId"] = feats["sf_categoryId"] == cat
    checks["partType"] = feats["sf_partType"] == (
        spec["part_type"] if spec["category"] is not None else 14)
    if res.get("types5"):
        checks["five_pairs_idx1"] = (feats["sf_n_type_pairs"] == 5
                                     and feats["sf_type_idx"] == 1)
        _rec, sf = u.self_family()
        pairs = (((sf.get("m_pFamilyTypes") or {}).get("value") or {})
                 .get("m_pairs") or [])
        fp = ((sf.get("m_familyParams") or {}).get("value") or {}).get("m_params")
        checks["blank_pair_first"] = bool(pairs) and pairs[0].get("name") == " "
        checks["blank_rows_equal_current_values"] = (
            bool(pairs) and (((pairs[0].get("params") or {}).get("m_params")) or []) == fp)
    if res.get("bip"):
        _rec, sf = u.self_family()
        locked = sf.get("m_lockedParameterIdsForDirectManipulation") or []
        checks["locked_has_cost_bip"] = -1001205 in locked
        cellids = [pid for g in LD._cell_groups(sf)
                   for pid in (g.get("m_paramIds") or [])]
        checks["palette_has_cost_bip"] = -1001205 in cellids
    if res.get("materials"):
        checks["materials_group_present"] = feats["cell_has_materials"]
        checks["familyParams_18_rows"] = feats["sf_familyParams_rows"] == 18
        checks["material_fsdo"] = feats["sf_fsdos_len"] == 1
    if res.get("dedup_cell"):
        checks["no_dup_cell_keys"] = not feats["cell_dup_group_keys"]
    if res.get("sparse_counters"):
        checks["donor_counters"] = (feats["sf_nextAbsorbedIndex"] == 3165
                                    and feats["sf_predefinedLimitIdx"] == 1963)
    if res.get("deletion_prefix"):
        want_pref = sorted([cat] + ([-1005500] if res.get("materials") else [])
                           + ([-1001205] if res.get("bip") else []))
        checks["deletion_nonelement_parents"] = (
            feats["hdr_deletion_nonelement"] == want_pref)
    if res.get("ref_type_ids"):
        checks["refTypeIds_len_1"] = feats["sf_refTypeIds_len"] == 1
    rep["exact_checks"] = checks
    rep["features_ok"] = not mism and all(checks.values())
    return rep


# ===========================================================================
# accounting + gates (the certified B0 instruments)
# ===========================================================================

def _accounting(name: str, info: Dict[str, Any]) -> Dict[str, Any]:
    import bisect_instance_bug as B
    FB = _blobs()
    child = os.path.join(ROOT, info["file"])
    parent = os.path.join(ROOT, info["immediate_parent"])
    out: Dict[str, Any] = {}
    out["probe"] = B.account(name, child, parent, declared_base=G_ABPD,
                             instance_ids=info.get("instance_ids") or [])
    out["hop_load"] = B.account(name + ".hop_load", parent, G_ABPD,
                                declared_base=G_ABPD, instance_ids=[],
                                with_regdiff=False)
    out["blob_proof"] = FB.blob_proof(child, G_ABPD)
    out["blob_proof_parent"] = FB.blob_proof(parent, G_ABPD)
    return out


def _gates(name: str, info: Dict[str, Any], acct: Dict[str, Any],
           feat: Dict[str, Any]) -> Dict[str, Any]:
    rep = acct["probe"]
    hop = acct["hop_load"]
    va = rep["validator"]
    bp = acct["blob_proof"]
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
        "instance_present": len(info.get("instance_ids") or []) == 1,
        "instance_connmgr_ok": info.get("instance_connmgr")
                               == "FamilyInstanceConnectorManager",
        "instance_category_ok": info.get("instance_header_category")
                                == info.get("expected_instance_category"),
        "symbol_form_ok": all(f.get("ok") for f in (info.get("symbol_form") or {}).values())
                          and bool(info.get("symbol_form")),
        "doc_roundtrip_ok": (info.get("doc_roundtrip") or {}).get("failed") == 0,
        "features_ok": bool(feat.get("features_ok")),
        "separator_mismatches": feat.get("separator_mismatches"),
    }
    ok = (g["validator_errors"] == 0 and g["validator_unexpected"] == 0
          and g["four_registry_coherent"] is True
          and g["load_hop_units_added"] == 1
          and g["instance_hop_units_added"] == 0
          and g["survivor_law_ok"] and g["identity"] == "PASS"
          and g["blob_all_units_64B"] and g["blob_added_nonce_verified"]
          and g["blob_units_added"] == 1
          and g["instance_present"] and g["instance_connmgr_ok"]
          and g["instance_category_ok"] and g["symbol_form_ok"]
          and g["doc_roundtrip_ok"] and g["features_ok"])
    g["gates_ok"] = bool(ok)
    return g


# ===========================================================================
# build / verify drivers
# ===========================================================================

def _install_schema() -> None:
    from rvt.frontdoor import standalone as SA
    SA.install_schema(G_ABPD)


def build(only: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    _install_schema()
    only = list(only) if only else list(LADDER)
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(BUILD_DIR, exist_ok=True)
    if not os.path.isfile(SHAPES):
        mine()
    t0 = time.time()
    out: Dict[str, Any] = {"tool": "tools/catchain.py", "base": relp(G_ABPD),
                           "built": {}, "accounting": {}, "features": {},
                           "gates": {}, "errors": {}}
    if os.path.isfile(ACCT):                     # merge partial (--only) runs
        try:
            with open(ACCT) as fh:
                prev = json.load(fh)
            for k in ("built", "accounting", "features", "gates"):
                out[k] = {n: v for n, v in (prev.get(k) or {}).items()
                          if n not in only}
        except Exception:                          # noqa: BLE001
            pass
    for name in [n for n in LADDER if n in only]:
        try:
            t1 = time.time()
            info = build_probe(name)
            info["seconds"] = round(time.time() - t1, 1)
            out["built"][name] = info
            log(f"{name} BUILT -> {info['file']} (md5 {info['md5'][:8]}, "
                f"{info['seconds']}s)")
            feat = feature_gate(name, os.path.join(ROOT, info["file"]),
                                RECIPES[name])
            out["features"][name] = feat
            acct = _accounting(name, info)
            out["accounting"][name] = acct
            g = _gates(name, info, acct, feat)
            out["gates"][name] = g
            log(f"{name}: validator {g['validator_errors']} err "
                f"(unexpected {g['validator_unexpected']}), coherent "
                f"{g['four_registry_coherent']}, features "
                f"{'OK' if g['features_ok'] else 'MISMATCH ' + str(g['separator_mismatches'])}, "
                f"connmgr {'OK' if g['instance_connmgr_ok'] else info.get('instance_connmgr')}, "
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


def verify() -> Dict[str, Any]:
    _install_schema()
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
            got = md5_of(child)
            if got != info["md5"]:
                raise RuntimeError(f"file drifted since build ({got} vs {info['md5']})")
            feat = feature_gate(name, child, RECIPES[name])
            acct = _accounting(name, info)
            g = _gates(name, info, acct, feat)
            out["features"][name] = feat
            out["accounting"][name] = acct
            out["gates"][name] = g
            fresh[name] = g
            log(f"{name}: gates_ok {g['gates_ok']} (validator "
                f"{g['validator_errors']} err, features "
                f"{'OK' if g['features_ok'] else 'MISMATCH'})")
        except Exception as e:                                 # noqa: BLE001
            fresh[name] = {"error": f"{type(e).__name__}: {e}"}
            log(f"{name} VERIFY FAILED: {type(e).__name__}: {e}")
    jdump(ACCT, out)
    write_probes_json(out)
    return fresh


# ===========================================================================
# probes.json -- the decision table the orchestrator reads
# ===========================================================================

READING = {
    "CTRL FAIL": "round VOID (oracle/environment) -- interpret nothing; "
                 "re-stage.",
    "BX_conj PASS": "the law LIVES INSIDE the enumerated famgen residues -- "
                    "the corpus's byte-observable suspect list is CONFIRMED "
                    "sufficient.  Read the singles to name it: any single "
                    "PASS names its axis outright; all singles FAIL => the "
                    "law is a conjunction of >= 2 axes -- read the "
                    "pre-built minus probes: BX_conj_minus_cat FAIL => the "
                    "category axis is NECESSARY (and with BX_cat_gm FAIL, "
                    "not sufficient); BX_conj_minus_cat PASS => category "
                    "UNNECESSARY (the law sits in types/bip/materials/"
                    "dedup/counters/deletion/refTypeIds -- next round "
                    "bisects those, same minus pattern, conj-minus-one per "
                    "axis).  Symmetrically for BX_conj_minus_types.",
    "BX_conj FAIL": "the defect is OUTSIDE everything enumerated: every one "
                    "of the corpus's 12 perfectly-separating byte residues "
                    "was authored to the PASS side through the coherent "
                    "chain and the audit still rejects.  The byte-diff "
                    "instrument is exhausted at this scale; the honest next "
                    "instrument is the desktop-Revit kit (observe the "
                    "audit's actual complaint on B0/BX_conj directly).  "
                    "Singles/minus probes then serve only as corroboration.",
    "BX_cat_gm PASS": "the CATEGORY axis is the law: the audit demands "
                      "category-consistent infrastructure our "
                      "electrical-equipment famdoc lacks (partType-14 "
                      "panelboards imply panel-schedule machinery).  Fix "
                      "fork: ship GM-category equipment families (works "
                      "today; schedules/tags lose the category filter) or "
                      "author the electrical infra the category implies "
                      "(next stream).",
    "BX_types_5 PASS": "the TYPE-TABLE law: multi-pair table with the "
                       "leading blank current-values pair.  famgen fix = "
                       "author the blank pair + m_idx 1 in finalize "
                       "(catprobe.apply_types5 is the fix, promoted).",
    "BX_bip PASS": "the LOCKED/BIP law: the identity palette + locked cost "
                   "BIP.  famgen fix = catprobe.apply_bip_lock promoted "
                   "into finalize.",
    "minus-probe reading": "each minus probe removes ONE axis from the "
                           "conjunction: minus FAIL while conj PASS => the "
                           "removed axis is NECESSARY; minus PASS => "
                           "UNNECESSARY given the rest.  Only meaningful "
                           "when BX_conj PASSES.",
    "singles all FAIL + conj FAIL": "consistent with #41's trajectory: the "
                                    "residue enumeration is complete and "
                                    "insufficient -- desktop-Revit kit next.",
}

EXPECTED = {
    "BX_conj": "the round's verdict-bearing rung: PASS => bisect down "
               "(minus probes pre-built); FAIL => the enumerated residue "
               "space is exhausted, desktop-Revit kit next",
    "BX_cat_gm": "unknown (the top unprobed candidate: category-coupled "
                 "infrastructure demand)",
    "BX_types_5": "unknown",
    "BX_bip": "unknown",
    "BX_conj_minus_cat": "read only under BX_conj PASS (bisection start)",
    "BX_conj_minus_types": "read only under BX_conj PASS (bisection start)",
}


def write_probes_json(acct: Dict[str, Any]) -> str:
    probes = []
    for i, name in enumerate(LADDER, 1):
        info = (acct.get("built") or {}).get(name) or {}
        gates = (acct.get("gates") or {}).get(name) or {}
        feat = (acct.get("features") or {}).get(name) or {}
        bp = ((acct.get("accounting") or {}).get(name) or {}).get("blob_proof") or {}
        probes.append({
            "order": i,
            "rung": name,
            "file": f"experiments/catchain/{name}.rvt",
            "base": relp(G_ABPD),
            "kind": "probe",
            "axis": AXES[name],
            "recipe": {"category": RECIPES[name]["category"],
                       "part_type": RECIPES[name]["part_type"],
                       "residues": {k: v for k, v in RECIPES[name]["residues"].items() if v}},
            "n_families": 1, "n_instances": 1, "n_walls": 0,
            "the_ONE_thing_it_tests": AXES[name],
            "expected": EXPECTED[name],
            "separators_flipped_to_PASS_side": sorted(
                c for c, keep in expected_separators(name).items() if not keep),
            "md5": info.get("md5"),
            "symbol_id": info.get("symbol_id"),
            "family_id": info.get("family_id"),
            "instance_ids": info.get("instance_ids"),
            "immediate_parent": info.get("immediate_parent"),
            "instance_connmgr": info.get("instance_connmgr"),
            "features_ok": feat.get("features_ok"),
            "blob_proof": {k: bp.get(k) for k in
                           ("units_total", "blob_len_histogram",
                            "units_added_vs_base", "added_nonce_verified")},
            "gates": gates,
        })
    manifest = {
        "stream": "catchain: THE CHAIN PROBES (post-verdict-#41).  Batch 47 "
                  "exonerated pure order both directions and every "
                  "single-field byte morph; the survivors are the ENTANGLED "
                  "residues only a full famgen-chain rebuild can flip "
                  "coherently: the family category (+ partType), the "
                  "type-table shape, the locked/param BIP group, the "
                  "materials group -- possibly a conjunction.  Every probe "
                  "here is the B0 recipe rebuilt through the FULL chain "
                  "with ONE recipe change (no byte surgery); the emitted "
                  "famdoc's feature vector is machine-verified against the "
                  "intended recipe (layout_diff unit_features).",
        "base": relp(G_ABPD),
        "upload_order_max_information_first": list(LADDER),
        "controls": {"g_abpd": {"source": relp(G_ABPD),
                                "voids": "ALL probes on CTRL FAIL"}},
        "reading_the_matrix": READING,
        "companion_evidence": {
            "accounting": "experiments/catchain/accounting.json",
            "corpus_shapes": "experiments/catchain/corpus_shapes.json",
            "separator_ranking": "experiments/layout/layout_diff.json",
            "prior_round": "experiments/layout/probes.json (batch 47: M2 "
                           "PASS, everything else FAIL)",
            "record": "docs/inbox/catchain.md",
        },
        "probes": probes,
    }
    path = os.path.join(OUT_DIR, "probes.json")
    jdump(path, manifest)
    log(f"probes.json -> {relp(path)}")
    return path


# ===========================================================================
# stage -- probe_batch + the certified G_ABPD control (STAGE ONLY)
# ===========================================================================

def stage() -> Dict[str, Any]:
    pb = _mod("probe_batch.py", "_catchain_probe_batch")
    FB = _blobs()
    import datetime as _dt
    files = [os.path.join(OUT_DIR, f"{n}.rvt") for n in LADDER]
    missing = [f for f in files if not os.path.isfile(f)]
    if missing:
        raise SystemExit(f"missing probes (run build): "
                         f"{[relp(m) for m in missing]}")
    with open(ACCT) as fh:
        acct = json.load(fh)
    bad = [n for n in LADDER
           if not (acct.get("gates") or {}).get(n, {}).get("gates_ok")]
    if bad:
        raise SystemExit(f"gates not green for {bad} -- stage refused")
    ledger = pb.Ledger.load()
    entries, violations = pb.check_batch(files, ledger)
    if violations:
        raise pb.GateRefusal(violations)
    n = FB.next_batch_number()
    out_dir = pb.ACCEPTANCE
    ctrl = pb.make_control(ledger, n, out_dir, source=G_ABPD)
    ordered = [ctrl] + [e for e in entries if e.kind == "probe"]
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
        "tool": "tools/catchain.py (via tools/probe_batch.py primitives)",
        "law": ("every entry's declared base is ITSELF in "
                "viewer-certified.json 'certified'; the batch carries >= 1 "
                "CONTROL = a byte-identical copy of a certified file; "
                "control FAIL => every verdict VOID"),
        "ledger": pb.rel(ledger.path),
        "control_count": 1,
        "controls": {"g_abpd": ctrl.staged_as,
                     "note": "the G_ABPD control gates every probe (all "
                             "ride the same base); CTRL FAIL voids the round"},
        "note": "catchain: the famgen-CHAIN residue probes (post-#41).  "
                "Reading order BX_conj (conjunction upper bound -- the "
                "biggest split) FIRST, then BX_cat_gm / BX_types_5 / "
                "BX_bip singles, then the pre-built bisection rungs "
                "BX_conj_minus_cat / BX_conj_minus_types (read only under "
                "BX_conj PASS).  Read "
                "experiments/catchain/probes.json reading_the_matrix; "
                "corpus shapes in experiments/catchain/corpus_shapes.json.",
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
    sub.add_parser("mine", help="mine the donor corpus shapes -> corpus_shapes.json")
    b = sub.add_parser("build", help="build the 6 chain probes")
    b.add_argument("--only", default=None, help="comma-separated probe subset")
    sub.add_parser("verify", help="re-run the gates on the emitted probes")
    sub.add_parser("stage", help="probe_batch gate + stage (G_ABPD control)")
    a = ap.parse_args(argv)
    if a.cmd == "mine":
        mine()
        return 0
    if a.cmd == "build":
        only = [s.strip() for s in a.only.split(",")] if a.only else None
        badp = [r for r in (only or []) if r not in LADDER]
        if badp:
            ap.error(f"unknown probe(s): {badp}; choose from {list(LADDER)}")
        out = build(only)
        n_err = len([k for k in out["errors"] if not k.endswith(".traceback")])
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
