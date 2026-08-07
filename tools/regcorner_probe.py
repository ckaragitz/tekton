#!/usr/bin/env python
"""regcorner_probe.py -- THE REGISTRATION-CORNER PROBES H12 / H11 / H11x12
(regcorner stream, 2026-08-05, post-verdict-#34).

THE QUESTION (genesis-audit verdict #34).  H9 (byte-copied native
22-element host constellation + all-Autodesk famdoc + V20-shape instance,
freshly REGISTERED as a new unit) FAILS while H10 (identical minus the
instance) PASSES and V20 (instance of a NATIVELY-registered unit) PASSES.
Symbol form, famdoc content, host elements, instance shape: ALL EXONERATED
by byte-copy.  The audit performs an instance-walk cross-check against
newly-registered units.  Exactly two suspects remain:

  (1) REGISTRATION ROW CONTENT -- the fields inside the ContentDocuments /
      ContentTable / FamilyMgr / partition rows famload authors (episode
      counts, saved-version stamps, key metadata, AppInfo slot content) vs
      the native rows' shapes;
  (2) A FIFTH SURFACE -- some project-ADocument reference keyed on content
      GUID / unit identity outside the four-registry model, whose native
      entries exist for the 52 native units but which our loads never
      populate, visited only on the instance walk.

THE LADDER (all three probes share ONE byte-identical parent load = H9's
exact recipe re-run; each probe then differs from that parent by exactly
its axis + the instance):

  H12    = the COMPLETE-COPY probe: the parent load with famload's all-null
           inline ADocument REPLACED by the donor's own POPULATED inline
           ADocument (131/239 AppInfo registries, ids remapped through the
           same famdoc rebase map, history identity GUIDs re-keyed fresh
           per the measured native law -- famdoc_bisect.swap_inline_adoc,
           the H6 machinery) + ONE V20-shape instance.  Diff vs H9 =
           exactly the inline ADocument.
  H11    = the NATIVE-MODELED REGISTRATION probe: the parent load with
           famload's authored ContentTable row RE-AUTHORED field-for-field
           on the donor's OWN native row (author 'Autodesk Revit', the
           real creation/lastModification episode stamps, the real
           two-episode m_EpisodeCounts [6 @ 1003, 411 @ 1013] whose sum =
           the unit's 417 records -- our unit IS a byte-rebased copy of
           exactly that unit, so the native row's story remains true of
           our unit's bytes), only the ContentKey GUID kept ours (identity
           -forced) + ONE V20-shape instance.  Diff vs H9 = exactly the
           CT row fields.
  H11x12 = the UNION probe: both edits on the same parent + the instance.
           Closes the 'both required' branch: if the killer needs the row
           AND the ADocument together, H11 and H12 each FAIL and only
           H11x12 passes -- without it that outcome would misread as
           'fifth surface'.
  H13    = the FIFTH-SURFACE patch (built only when the surface stream
           names a candidate; `h13` subcommand reads its spec).

MEASURED THIS SESSION (tools/regcorner_probe.py measure -> row_diff.json):
  * famload-vs-native ContentTable row: m_author 'rvt-writer' vs
    'Autodesk Revit' (52/52 native rows); m_history creation==lastMod
    (fresh ep) vs creation<lastMod; m_EpisodeCounts ONE fresh-episode
    bucket [417 @ host-ep] vs the native two-bucket split; every other
    field/keyset identical (native keysets 52/52 uniform).
  * FamilyMgr entry {m_surrogateId, m_familyDocGUIDs:[1 GUID]}: native
    parity already (native entries carry 0..4 GUIDs; 1 is in range).
  * ContentDocuments entry framing: byte-modeled corpus grammar (parse/
    assemble byte-exact); the CONTENT gap is the inline ADocument itself
    (34,870 B / 131 populated registries native vs 18,057 B / 0 ours) --
    that is H12's axis, not a framing axis.
  * Partition save unit: famload's spliced unit is frame-identical to the
    native donor unit (counter 417, 4 blocks, same seq split 418/146+272/
    418, flags 4) -- no partition-row axis exists to probe.
  * CT m_EpisodeCounts vs the inline ADocument's per-element histories:
    NOT a strict corpus law (49/52 native units disagree with both the
    creation and lastMod histograms) -- so H12's famload-row + native-adoc
    pairing is not off-corpus on that pair (de-confounds the H12 FAIL
    reading).
  * The donor's inline ADocument is fully unit-internal (1,611 int refs,
    all in-unit; 0 native-cluster refs, 0 host refs) -- the famdoc rebase
    map alone completes the swap.

READING (probes.json carries the full decision table): see READING below.

PROOF-ONLY: every probe embeds Autodesk sample content and stays in
experiments/ under the quarantine rule (zero donors in shipped output).

USAGE (repo root)::

    .venv/bin/python tools/regcorner_probe.py measure   # row_diff.json (the famload-vs-native row diff)
    .venv/bin/python tools/regcorner_probe.py build     # parent + H12 + H11 + H11x12 (+ gates + probes.json)
    .venv/bin/python tools/regcorner_probe.py verify    # re-run gates on emitted probes
    .venv/bin/python tools/regcorner_probe.py stage     # probe_batch gate + rst control (batch 40)
    .venv/bin/python tools/regcorner_probe.py h13 SPEC  # the fifth-surface patch (surface stream's spec)

TERRITORY: this file, ``experiments/regcorner/probes/**``,
``tests/test_regcorner.py``, ``docs/inbox/regcorner-probes.md``.
IMPORTS (never edits): tools/hostpair_probe.py (build_load -- the H9
recipe verbatim, CLUSTER_ORDER, the copy machinery), tools/famdoc_bisect.py
(build_donor / swap_inline_adoc / place_probe / _install_schema),
tools/bisect_instance_bug.py (account / batch numbering),
tools/probe_batch.py (staging), rvt.adocument, rvt.famgen.factory,
rvt.ecc / stream encoders / cfb writer.  No Autodesk install dirs, no
browser; STAGE only (the orchestrator uploads).
"""
from __future__ import annotations

import argparse
import copy
import dataclasses
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import time
import traceback
import uuid
from typing import Any, Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (os.path.join(ROOT, "src"), HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

RST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
OUT_DIR = os.path.join(ROOT, "experiments", "regcorner", "probes")
BUILD_DIR = os.path.join(OUT_DIR, "_build")

#: where the surface stream publishes its rankings / fifth-surface candidates
SURFACE_DOC = os.path.join(ROOT, "docs", "inbox", "regcorner-surface.md")
SURFACE_JSON_GLOB = os.path.join(ROOT, "experiments", "regcorner")

LADDER = ("H12", "H11", "H11x12")
AXES = {
    "H12": "the COMPLETE-COPY probe: parent load + the donor's own POPULATED "
           "inline ADocument (H6 swap law) + one V20-shape instance",
    "H11": "the NATIVE-MODELED REGISTRATION probe: parent load + the "
           "ContentTable row re-authored field-for-field on the donor's own "
           "native row (GUID kept ours) + one V20-shape instance",
    "H11x12": "the UNION probe: both edits (native-modeled CT row + populated "
              "inline ADocument) + one V20-shape instance",
}

#: the CT-row fields the retrofit replaces (everything except identity)
CT_IDENTITY_FIELDS = ("m_ContentKey",)


def log(msg: str) -> None:
    print(f"[regcorner] {msg}", flush=True)


def relp(p: str) -> str:
    try:
        r = os.path.relpath(p, ROOT)
        return r if not r.startswith("..") else p
    except ValueError:                                     # pragma: no cover
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


def jload(path: str) -> Any:
    with open(path) as fh:
        return json.load(fh)


def _hp():
    import hostpair_probe as HP
    return HP


def _fdb():
    import famdoc_bisect as FDB
    return FDB


def _bisect():
    import bisect_instance_bug as B
    return B


# ===========================================================================
# shared decoding helpers
# ===========================================================================

def _latest_value(path: str):
    from rvt import adocument as A
    from rvt.container import open_rvt
    with open_rvt(path) as f:
        payload = f.inflate("Global/Latest")
    lat = A.decode_latest(payload)
    if not lat.clean:
        raise RuntimeError(f"{relp(path)}: Global/Latest does not decode clean")
    return lat, payload


def _ct_rows(latest_value: dict) -> List[dict]:
    return (((latest_value.get("m_oContentTable") or {}).get("value") or {})
            .get("m_ContentRecSet") or [])


def _ct_row_for(latest_value: dict, guid: str) -> Optional[dict]:
    for r in _ct_rows(latest_value):
        g = str((r.get("m_ContentKey") or {}).get("m_guidKey") or "")
        if g.lower() == guid.lower():
            return r
    return None


def _appinfo_slot(latest_value: dict, class_name: str) -> Optional[dict]:
    mgr = (latest_value.get("m_pAppInfoManager") or {}).get("value") or {}
    for x in mgr.get("m_appInfoArr") or []:
        if isinstance(x, dict) and x.get("ptr_class") == class_name:
            return x.get("value")
    return None


def _cd_entries(path: str):
    from rvt.container import open_rvt
    from rvt.famgen import factory as F
    with open_rvt(path) as f:
        cd = b"".join(f.inflate_all("Global/ContentDocuments"))
    ents, tail = F.parse_content_documents(cd)
    return ents, tail, cd


def _leaf_diff(a: Any, b: Any, path: str, out: List[Tuple[str, Any, Any]]) -> None:
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            _leaf_diff(a.get(k), b.get(k), f"{path}.{k}", out)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for j, (x, y) in enumerate(zip(a, b)):
            _leaf_diff(x, y, f"{path}[{j}]", out)
    elif a != b:
        out.append((path, a, b))


# ===========================================================================
# measure: the famload-vs-native registration-row diff (row_diff.json)
# ===========================================================================

def measure() -> Dict[str, Any]:
    """The four-surface famload-vs-native row diff: ContentTable row,
    FamilyMgr entry, ContentDocuments entry, partition unit frames.  A = the
    NATIVE donor row (rst unit 36); B = famload's authored row (read from
    the freshly built parent load when present, else documented from the
    hostpair H9_load evidence)."""
    from rvt import adocument as A
    from rvt.families import FamilyIndex
    HP = _hp()
    FDB = _fdb()
    FDB._install_schema()                                  # noqa: SLF001

    idx = FamilyIndex(RST)
    donor_guid = str(idx.units[HP.DONOR_UNIT].guid).lower()
    lat, _pay = _latest_value(RST)
    native_row = _ct_row_for(lat.value, donor_guid)
    if native_row is None:
        raise RuntimeError("native donor CT row not found")
    rows = _ct_rows(lat.value)
    authors: Dict[str, int] = {}
    ec_lens: Dict[int, int] = {}
    keysets: Dict[str, int] = {}
    for r in rows:
        authors[str(r.get("m_author"))] = authors.get(str(r.get("m_author")), 0) + 1
        ec = r.get("m_EpisodeCounts") or []
        ec_lens[len(ec)] = ec_lens.get(len(ec), 0) + 1
        keysets[str(tuple(sorted(r.keys())))] = keysets.get(str(tuple(sorted(r.keys()))), 0) + 1
    fm = _appinfo_slot(lat.value, "FamilyMgr") or {}
    lfi = fm.get("m_arrLoadedFamilyInfo") or []
    fm_guid_lens = sorted({len(e.get("m_familyDocGUIDs") or []) for e in lfi})

    ents, _tail, _cd = _cd_entries(RST)
    donor_adoc = next(a for g, a in ents if str(g).lower() == donor_guid)
    dec = A.decode_latest(donor_adoc)
    arr = ((dec.value.get("m_pAppInfoManager") or {}).get("value") or {}).get("m_appInfoArr") or []

    # famload's authored row: read from our parent load if built
    parent = os.path.join(BUILD_DIR, "RC_parent_load.rvt")
    ours_row = None
    ours_adoc = None
    if os.path.isfile(parent) and os.path.isfile(parent + ".regcorner.json"):
        plan = jload(parent + ".regcorner.json")["plan"]
        plat, _pp = _latest_value(parent)
        ours_row = _ct_row_for(plat.value, plan["guid"])
        pents, _t2, _c2 = _cd_entries(parent)
        blob = next(a for g, a in pents if str(g).lower() == plan["guid"].lower())
        pdec = A.decode_latest(blob)
        parr = ((pdec.value.get("m_pAppInfoManager") or {}).get("value") or {}).get("m_appInfoArr") or []
        ours_adoc = {"bytes": len(blob), "appinfo_slots": len(parr),
                     "appinfo_populated": sum(1 for x in parr if x)}

    field_diff: List[Dict[str, Any]] = []
    if ours_row is not None:
        leaves: List[Tuple[str, Any, Any]] = []
        _leaf_diff(native_row, ours_row, "row", leaves)
        for pth, a, b in leaves:
            field_diff.append({"path": pth, "native": a, "famload": b,
                               "identity_forced": ".m_ContentKey." in pth + "."})

    out = {
        "law": "A = the NATIVE donor ContentTable row (rst unit 36, the "
               "V20-certified lineage); B = famload's authored row (the "
               "regcorner parent load = H9's exact recipe).  H11 re-authors "
               "B to byte-parity with A on every field except the identity "
               "-forced ContentKey GUID.",
        "native_donor_guid": donor_guid,
        "native_donor_ct_row": native_row,
        "native_ct_census": {"rows": len(rows), "authors": authors,
                             "episode_count_lens": ec_lens, "keysets": keysets},
        "native_fm_census": {"entries": len(lfi), "guid_list_lens": fm_guid_lens,
                             "note": "famload's {m_surrogateId, m_familyDocGUIDs:"
                                     "[1 GUID]} entry is native-parity (1 in "
                                     "range 0..4); no FM axis to probe"},
        "native_cd_entry": {"adoc_bytes": len(donor_adoc),
                            "adoc_decodes_clean": bool(dec.clean),
                            "appinfo_slots": len(arr),
                            "appinfo_populated": sum(1 for x in arr if x)},
        "famload_ct_row": ours_row,
        "famload_cd_entry": ours_adoc,
        "ct_row_field_diff": field_diff,
        "partition_frames": "famload's spliced unit is frame-identical to the "
                            "native donor unit (counter 417, 4 blocks, seq "
                            "split 418/146+272/418, flags 4) -- measured "
                            "2026-08-05; no partition axis to probe",
        "coherence_note": "CT m_EpisodeCounts vs inline-ADocument per-element "
                          "histories is NOT a strict corpus law (49/52 native "
                          "units disagree with both the creation and lastMod "
                          "histograms) -- H12's famload-row + native-adoc "
                          "pairing is therefore not off-corpus on that pair",
    }
    path = os.path.join(OUT_DIR, "row_diff.json")
    jdump(path, out)
    log(f"row_diff.json -> {relp(path)}")
    return out


# ===========================================================================
# the two stream edits (each = ONE axis on the shared parent)
# ===========================================================================

def _replace_stream(path_in: str, path_out: str, stream: str, payload: bytes) -> None:
    from rvt import ecc
    from rvt.cfb_writer import write_cfb
    from rvt.roundtrip import read_entries
    from rvt.stream_encoders import wrap_global_stream
    framed = ecc.frame_stream(wrap_global_stream(stream, payload, level=3))
    ents = read_entries(path_in)
    out_entries = [dataclasses.replace(e, data=framed)
                   if (e.entry_type == "stream" and e.path == stream) else e
                   for e in ents]
    write_cfb(path_out, out_entries)


def retrofit_ct_row(path_in: str, path_out: str, *, guid: str,
                    mold_row: dict) -> Dict[str, Any]:
    """H11: re-author famload's ContentTable row for ``guid`` to
    field-for-field parity with ``mold_row`` (the donor's own native row),
    keeping ONLY the identity-forced ContentKey GUID ours.  The edit is
    proven minimal: the codec's byte-idempotence is gated first
    (encode(decode(Latest)) == Latest), so the written delta is exactly the
    row fields; the exhaustive old->new leaf ledger is returned."""
    from rvt import adocument as A
    lat, payload = _latest_value(path_in)
    re_enc = A.encode_latest(lat.value, trailer=lat.trailer)
    if re_enc != payload:
        raise RuntimeError("Global/Latest codec is not byte-idempotent on the "
                           "parent load -- retrofit refused (delta would not "
                           "be attributable to the row edit alone)")
    row = _ct_row_for(lat.value, guid)
    if row is None:
        raise RuntimeError(f"no ContentTable row for {guid}")
    old = copy.deepcopy(row)
    for k in list(row.keys()):
        if k in CT_IDENTITY_FIELDS:
            continue
        row.pop(k)
    for k, v in mold_row.items():
        if k in CT_IDENTITY_FIELDS:
            continue
        row[k] = copy.deepcopy(v)
    leaves: List[Tuple[str, Any, Any]] = []
    _leaf_diff(old, row, "row", leaves)
    if any(".m_ContentKey" in p for p, _a, _b in leaves):
        raise RuntimeError("retrofit touched the identity GUID")
    new_latest = A.encode_latest(lat.value, trailer=lat.trailer)
    back = A.decode_latest(new_latest)
    if not back.clean:
        raise RuntimeError("edited Latest does not re-decode clean")
    if _ct_row_for(back.value, guid) != row:
        raise RuntimeError("edited row did not round-trip")
    _replace_stream(path_in, path_out, "Global/Latest", new_latest)
    return {"guid": guid, "fields_replaced": sorted(k for k in mold_row
                                                    if k not in CT_IDENTITY_FIELDS),
            "leaf_deltas": [{"path": p, "old": a, "new": b} for p, a, b in leaves],
            "mold": "the donor's own native ContentTable row (unit 36)",
            "identity_kept": list(CT_IDENTITY_FIELDS)}


def swap_adoc(path_in: str, path_out: str, *, guid: str, adoc_value: dict,
              idmap: Dict[int, int], self_family_new: int) -> Dict[str, Any]:
    """H12: famdoc_bisect.swap_inline_adoc (the H6 machinery, verbatim) +
    the regcorner gates: CD parse/assemble byte-idempotence on the parent
    first, populated-slot count == the native 131, owner-family remap
    proven."""
    from rvt.famgen import factory as F
    FDB = _fdb()
    ents, tail, cd = _cd_entries(path_in)
    if F.assemble_content_documents(ents, tail=tail or F.CD_END_RECORD) != cd:
        raise RuntimeError("ContentDocuments parse/assemble is not "
                           "byte-idempotent on the parent load -- swap refused")
    rep = FDB.swap_inline_adoc(path_in, path_out, guid=guid,
                               adoc_value=adoc_value, idmap=idmap,
                               self_family_new=self_family_new)
    if rep["appinfo_populated"] != 131:
        raise RuntimeError(f"swapped inline ADocument carries "
                           f"{rep['appinfo_populated']} populated AppInfo "
                           f"slots (native donor law: 131)")
    if rep["owner_family_id"] != self_family_new:
        raise RuntimeError(f"swapped inline ADocument ownerFamilyId "
                           f"{rep['owner_family_id']} != rebased self-family "
                           f"{self_family_new}")
    return rep


# ===========================================================================
# build driver
# ===========================================================================

def _build_parent() -> Tuple[str, Dict[str, Any]]:
    """The shared parent load = H9's exact recipe (hostpair_probe.build_load,
    verbatim import -- byte-copies + famload registration, fresh GUIDs), plus
    the re-derivation proof of the famdoc rebase map the edits need."""
    HP = _hp()
    FDB = _fdb()
    parent = os.path.join(BUILD_DIR, "RC_parent_load.rvt")
    lrep = HP.build_load(parent)
    wm = int(lrep["watermark"])
    donor_els, anchors, idmap, adoc_value, _census = FDB.build_donor(wm + 1)
    lo, hi = lrep["famdoc"]["id_range"]
    if [min(idmap.values()), max(idmap.values())] != [lo, hi]:
        raise RuntimeError("re-derived famdoc rebase map disagrees with the "
                           "parent build's id range")
    if len(donor_els) != int(lrep["famdoc"]["records"]):
        raise RuntimeError("re-derived donor element count disagrees")
    plan = lrep["plan"]
    side = {"plan": plan, "watermark": wm,
            "anchors": anchors,
            "famdoc_idmap_size": len(idmap),
            "host_idmap": lrep["host_idmap"],
            "copy_ledger": lrep["copy_ledger"],
            "registrations": lrep.get("pass2_registrations"),
            "verify": lrep.get("verify")}
    jdump(parent + ".regcorner.json", side)
    return parent, {"lrep": lrep, "idmap": idmap, "adoc_value": adoc_value,
                    "anchors": anchors, "plan": plan}


def build() -> Dict[str, Any]:
    HP = _hp()
    FDB = _fdb()
    B = _bisect()
    FDB._install_schema()                                  # noqa: SLF001
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(BUILD_DIR, exist_ok=True)
    t0 = time.time()
    out: Dict[str, Any] = {"tool": "tools/regcorner_probe.py", "base": relp(RST),
                           "built": {}, "accounting": {}, "errors": {}}
    try:
        parent, ctx = _build_parent()
        plan = ctx["plan"]
        sym, fam = plan["symbol_ids"][0], plan["host_family_id"]
        out["parent"] = {"file": relp(parent), "md5": md5_of(parent),
                         "plan_guid": plan["guid"], "symbol_id": sym,
                         "family_id": fam,
                         "recipe": "hostpair_probe.build_load (H9-verbatim; "
                                   "fresh GUIDs per rebuild)"}
        log(f"parent load BUILT -> {relp(parent)} "
            f"(md5 {out['parent']['md5'][:8]}, guid {plan['guid'][:8]})")

        # the native mold row (measured fresh from the base)
        from rvt.families import FamilyIndex
        idx = FamilyIndex(RST)
        donor_guid = str(idx.units[HP.DONOR_UNIT].guid).lower()
        nat_lat, _p = _latest_value(RST)
        mold = _ct_row_for(nat_lat.value, donor_guid)
        if mold is None:
            raise RuntimeError("native donor CT row not found")

        loads = {}
        # ---- H12 load: adoc swap only --------------------------------------
        l12 = os.path.join(BUILD_DIR, "H12_load.rvt")
        rep12 = swap_adoc(parent, l12, guid=plan["guid"],
                          adoc_value=ctx["adoc_value"], idmap=ctx["idmap"],
                          self_family_new=ctx["anchors"]["self_family"])
        loads["H12"] = (l12, {"adoc_swap": rep12})
        # ---- H11 load: CT-row retrofit only --------------------------------
        l11 = os.path.join(BUILD_DIR, "H11_load.rvt")
        rep11 = retrofit_ct_row(parent, l11, guid=plan["guid"], mold_row=mold)
        loads["H11"] = (l11, {"ct_retrofit": rep11})
        # ---- H11x12 load: both ---------------------------------------------
        lu_tmp = os.path.join(BUILD_DIR, "H11x12_swap.tmp.rvt")
        repu_a = swap_adoc(parent, lu_tmp, guid=plan["guid"],
                           adoc_value=ctx["adoc_value"], idmap=ctx["idmap"],
                           self_family_new=ctx["anchors"]["self_family"])
        lu = os.path.join(BUILD_DIR, "H11x12_load.rvt")
        repu_b = retrofit_ct_row(lu_tmp, lu, guid=plan["guid"], mold_row=mold)
        os.remove(lu_tmp)
        loads["H11x12"] = (lu, {"adoc_swap": repu_a, "ct_retrofit": repu_b})

        # ---- one V20-shape instance on each --------------------------------
        for name in LADDER:
            src, edits = loads[name]
            probe = os.path.join(OUT_DIR, f"{name}.rvt")
            prec = FDB.place_probe(src, probe, symbol_id=sym, family_id=fam,
                                   category=HP.DONOR_CATEGORY)
            out["built"][name] = {
                "probe": name, "axis": AXES[name], "base": relp(RST),
                "file": relp(probe), "md5": md5_of(probe),
                "immediate_parent": relp(src),
                "shared_parent": relp(parent),
                "symbol_id": sym, "family_id": fam,
                "instance_ids": [prec["instance_id"]],
                "instance": prec, "document_guid": plan["guid"],
                "edits": edits,
                "placement": "famdoc_bisect.place_probe (H7/H9-verbatim)"}
            log(f"{name} BUILT -> {relp(probe)} "
                f"(md5 {out['built'][name]['md5'][:8]}, "
                f"instance {prec['instance_id']})")
    except Exception as e:                                 # noqa: BLE001
        out["errors"]["build"] = f"{type(e).__name__}: {e}"
        out["errors"]["build.traceback"] = traceback.format_exc(limit=12)
        log(f"BUILD FAILED: {type(e).__name__}: {e}")
        jdump(os.path.join(OUT_DIR, "accounting.json"), out)
        return out

    # ---- gates: load hop (vs shared parent) + instance hop (vs own load) --
    for name in LADDER:
        info = out["built"][name]
        try:
            load_path = os.path.join(ROOT, info["immediate_parent"])
            acc_load = B.account(f"{name}_load", load_path, parent,
                                 declared_base=RST, instance_ids=[],
                                 with_regdiff=False)
            acc_probe = B.account(name, os.path.join(ROOT, info["file"]),
                                  load_path, declared_base=RST,
                                  instance_ids=info["instance_ids"])
            out["accounting"][name] = {"load_vs_parent": acc_load,
                                       "probe_vs_load": acc_probe}
            prf = axis_proofs(name, os.path.join(ROOT, info["file"]), info)
            out["built"][name]["axis_proofs"] = prf
            va = acc_probe["validator"]
            vl = acc_load["validator"]
            log(f"{name}: validator {va['n_errors']} err probe / "
                f"{vl['n_errors']} err load (unexpected "
                f"{len(va['unexpected_errors'])}/{len(vl['unexpected_errors'])}), "
                f"census coherent {acc_probe['census']['coherent']}, survivor "
                f"{'OK' if acc_probe['survivor_law_ok'] else 'VIOLATED'}, "
                f"streams changed by edit: "
                f"{[c['stream'] for c in acc_load['streams_changed']]}, "
                f"axis proofs {'OK' if prf['ok'] else 'FAILED'}")
            if not prf["ok"]:
                raise RuntimeError(f"axis proofs failed: {prf['failures']}")
        except Exception as e:                             # noqa: BLE001
            out["errors"][name + ".gates"] = f"{type(e).__name__}: {e}"
            out["errors"][name + ".gates.tb"] = traceback.format_exc(limit=8)
            log(f"{name} GATES FAILED: {type(e).__name__}: {e}")
    out["seconds"] = round(time.time() - t0, 1)
    jdump(os.path.join(OUT_DIR, "accounting.json"), out)
    write_probes_json(out)
    return out


# ===========================================================================
# axis proofs (read back from the emitted bytes)
# ===========================================================================

def axis_proofs(name: str, path: str, info: Dict[str, Any]) -> Dict[str, Any]:
    """Per-probe proofs read back from the emitted file: the edited axis is
    present (populated inline adoc / native-modeled row), the untouched axis
    is famload's (the axes stay independent), and the instance carries the
    V20 shape against the copied symbol."""
    from rvt import adocument as A
    from rvt.mutate import Document
    HP = _hp()
    guid = info["document_guid"]
    failures: List[str] = []
    prf: Dict[str, Any] = {}

    lat, _p = _latest_value(path)
    row = _ct_row_for(lat.value, guid)
    prf["ct_row"] = row
    ents, _tail, _cd = _cd_entries(path)
    blob = next((a for g, a in ents if str(g).lower() == guid.lower()), None)
    if blob is None:
        failures.append("no ContentDocuments entry for our GUID")
        arr = []
    else:
        dec = A.decode_latest(blob)
        if not dec.clean:
            failures.append("our inline ADocument does not decode clean")
        arr = ((dec.value.get("m_pAppInfoManager") or {}).get("value") or {}) \
            .get("m_appInfoArr") or []
    populated = sum(1 for x in arr if x)
    prf["inline_adoc"] = {"bytes": len(blob or b""), "appinfo_slots": len(arr),
                          "appinfo_populated": populated}

    wants_adoc = name in ("H12", "H11x12")
    wants_row = name in ("H11", "H11x12")
    if wants_adoc and populated != 131:
        failures.append(f"populated inline adoc expected (131), got {populated}")
    if not wants_adoc and populated != 0:
        failures.append(f"famload's all-null adoc expected (0), got {populated}")
    if row is None:
        failures.append("no ContentTable row for our GUID")
    else:
        if wants_row:
            if row.get("m_author") != "Autodesk Revit":
                failures.append("native-modeled row expected author "
                                "'Autodesk Revit'")
            if len(row.get("m_EpisodeCounts") or []) < 2:
                failures.append("native-modeled row expected the two-bucket "
                                "m_EpisodeCounts")
        else:
            if row.get("m_author") != "rvt-writer":
                failures.append("famload's row expected author 'rvt-writer'")
            if len(row.get("m_EpisodeCounts") or []) != 1:
                failures.append("famload's row expected one m_EpisodeCounts "
                                "bucket")

    # the V20 instance shape (the H9-certified read-back)
    doc = Document.from_file(path)
    iid = info["instance_ids"][0]
    inst = doc.value(iid) or {}
    hdr = doc.value(iid, 101) or {}
    dele = ((hdr.get("m_parents") or {}).get("value") or {}).get("m_deletion") or []
    sym = info["symbol_id"]
    checks = {
        "instance_class": doc.class_of(iid) == "FamilyInstance",
        "master_symbol": inst.get("m_masterSymbolId") == sym,
        "phase": inst.get("m_createdPhaseId") == 86961,
        "connmgr_none": inst.get("m_pConnectorManager") is None,
        "deletion_shape": dele == sorted({311, 86961, sym, iid}),
        "symbol_class": doc.class_of(sym) == "FamilySymbol",
        "symbol_geomSteps_populated": isinstance(
            (doc.value(sym) or {}).get("m_geomSteps"), dict),
        "symbol_rep_GElement": doc.class_of(sym, 103) == "GElement",
        "family_name_h9": (doc.value(info["family_id"]) or {}).get("m_name")
                          == HP.H9_NAME,
    }
    prf["instance_shape"] = checks
    failures.extend(k for k, v in checks.items() if not v)
    prf["failures"] = failures
    prf["ok"] = not failures
    return prf


# ===========================================================================
# probes.json (the decision table)
# ===========================================================================

READING = {
    "CTRL FAIL": "round VOID (oracle/environment) -- interpret nothing",
    "H12 PASS": "the all-null inline ADocument was H9's killer -- the ONE "
                "delta vs H9 is the donor's populated inline ADocument.  "
                "Fix = author a POPULATED inline ADocument in the product "
                "load path (port spec in docs/inbox/regcorner-probes.md: "
                "extend rvt.famgen.factory.author_embedded_adocument to "
                "populate the family-editor registries, modeled on the "
                "corpus 131-slot census).  Expect H11x12 PASS too (superset); "
                "H11 verdict then only measures whether the row ALSO "
                "matters.",
    "H12 FAIL + H11 PASS": "the registration ROW CONTENT was the killer -- "
                           "the ONE delta vs H9 is the ContentTable row "
                           "re-authored on the native mold.  Before porting, "
                           "run the field split (H11a author-only / H11b "
                           "episode-shape-only, pre-branched in the record): "
                           "the product path must NOT forge 'Autodesk Revit' "
                           "authorship, so the lawful fix depends on WHICH "
                           "field discriminates.  Expect H11x12 PASS "
                           "(superset).",
    "H12 FAIL + H11 FAIL + H11x12 PASS": "BOTH surfaces are required "
                                         "together (row + populated inline "
                                         "ADocument); port both mechanisms.",
    "ALL THREE FAIL": "neither suspect-(1) surface (alone or united) cures "
                      "H9 => the FIFTH SURFACE is convicted by elimination: "
                      "a project-ADocument reference keyed on content GUID / "
                      "unit identity outside the four-registry model, "
                      "visited only on the instance walk.  The surface "
                      "stream's candidate list (docs/inbox/regcorner-"
                      "surface.md) drives H13 (`h13` subcommand).",
    "H11x12 FAIL while H11 or H12 PASS": "lattice-inconsistent (the union "
                                         "of a passing edit failed) -- "
                                         "oracle noise; re-run the round.",
    "H13 (staged separately, batch 41)": "H13 = H11 + the surface stream's "
                                         "top fifth-surface candidate "
                                         "(CategoryTracking rows for our "
                                         "cluster).  H13 PASS where H11 "
                                         "FAILED convicts the fifth "
                                         "surface; H13 FAIL alongside an "
                                         "all-FAIL batch 40 moves the hunt "
                                         "to the next donor-covered "
                                         "candidate on the ranking.",
}


def write_probes_json(build_out: Dict[str, Any]) -> str:
    onething = {
        "H12": "ONE delta vs H9: famload's all-null inline ADocument (0/239 "
               "AppInfo registries) replaced by the donor's own POPULATED "
               "one (131/239, ids remapped, fresh history identity).  "
               "Registration rows stay famload's.  PASS convicts the "
               "all-null inline ADocument; FAIL leaves rows / fifth "
               "surface.",
        "H11": "ONE delta vs H9: famload's ContentTable row re-authored "
               "field-for-field on the donor's own native row (author "
               "'Autodesk Revit', creation<lastMod stamps, two-bucket "
               "m_EpisodeCounts summing to the unit's 417 records), GUID "
               "kept ours.  Inline ADocument stays famload's all-null.  "
               "PASS convicts the row content; FAIL leaves adoc / fifth "
               "surface.",
        "H11x12": "the union of both edits on the same byte-identical "
                  "parent.  Separates 'both required together' from 'fifth "
                  "surface' when H11 and H12 both FAIL.",
    }
    expected = {
        "H12": "the biggest split: the inline-ADocument axis (H6's FAIL was "
               "uninterpretable -- shared machinery; this re-tests it in "
               "the byte-copy frame where machinery is exonerated)",
        "H11": "the registration-row axis (suspect 1 verbatim)",
        "H11x12": "the union rung (closes the both-required branch)",
        "H13": "the fifth-surface rung (H11 + the CategoryTracking rows; "
               "staged as its own batch after batch 40)",
    }
    onething["H13"] = ("H11's exact load + the donor cluster's "
                       "CategoryTracking rows (4 categoryData + 4 "
                       "gstyleData) remapped for our copies at the "
                       "law-derived positions -- the surface stream's top "
                       "donor-covered instance-walk candidate.  The ONE "
                       "thing vs H11: the fifth surface's entries.")
    ladder = list(LADDER) + (["H13"] if "H13" in (build_out.get("built") or {})
                             else [])
    probes = []
    for i, name in enumerate(ladder, 1):
        info = (build_out.get("built") or {}).get(name) or {}
        acct = ((build_out.get("accounting") or {}).get(name) or {})
        va = ((acct.get("probe_vs_load") or {}).get("validator")) or {}
        vl = ((acct.get("load_vs_parent") or {}).get("validator")) or {}
        prf = info.get("axis_proofs") or {}
        probes.append({
            "order": i, "rung": name,
            "file": f"experiments/regcorner/probes/{name}.rvt",
            "base": relp(RST), "kind": "probe",
            "axis": AXES.get(name) or info.get("axis"),
            "n_families": 1, "n_instances": len(info.get("instance_ids") or []),
            "n_walls": 0,
            "the_ONE_thing_it_tests": onething[name],
            "expected": expected[name],
            "md5": info.get("md5"),
            "symbol_id": info.get("symbol_id"),
            "family_id": info.get("family_id"),
            "instance_ids": info.get("instance_ids"),
            "immediate_parent": info.get("immediate_parent"),
            "shared_parent": info.get("shared_parent"),
            "gates": {
                "validator_errors_probe": va.get("n_errors"),
                "validator_unexpected_probe": len(va.get("unexpected_errors") or []),
                "validator_errors_load": vl.get("n_errors"),
                "four_registry_coherent": ((acct.get("probe_vs_load") or {})
                                           .get("census") or {}).get("coherent"),
                "survivor_law_ok": (acct.get("probe_vs_load") or {}).get("survivor_law_ok"),
                "identity": (((acct.get("probe_vs_load") or {})
                              .get("identity_gate") or {}).get("status")),
                "streams_changed_by_edit": [c.get("stream") for c in
                                            ((acct.get("load_vs_parent") or {})
                                             .get("streams_changed") or [])],
                "axis_proofs_ok": prf.get("ok"),
            },
        })
    manifest = {
        "stream": "regcorner: the registration-corner probes (post-verdict-"
                  "#34).  H9 FAIL + H10 PASS + V20 PASS leaves exactly two "
                  "suspects: the registration ROW CONTENT famload authors, "
                  "or a FIFTH project-ADocument surface visited only on the "
                  "instance walk.  H12/H11/H11x12 split them.",
        "base": relp(RST),
        "note": "all three probes share ONE byte-identical parent load = "
                "H9's exact recipe re-run (hostpair_probe.build_load, fresh "
                "GUIDs); each probe = parent + exactly its axis edit + one "
                "V20-shape instance by H7/H9's exact template recipe.  "
                "PROOF-ONLY: sample-derived content, quarantined, never "
                "shipped.  Fresh GUIDs are minted per rebuild -- re-hash "
                "after any rerun.",
        "upload_order_max_information_first": ladder,
        "control": {"source": relp(RST),
                    "note": "control = byte-identical copy of the UNTOUCHED "
                            "rst sample (probe_batch stage --control-from)"},
        "recorded_context": {
            "H9": "FAIL (byte-copied host constellation + famload "
                  "registration + instance, batch 38)",
            "H10": "PASS (H9 minus the instance, batch 38)",
            "V20": "PASS (instance of the NATIVE symbol, no load)",
            "H6": "FAIL but uninterpretable (populated-adoc axis on "
                  "famload-authored hosts; H7 FAILED so machinery was the "
                  "confound, batch 37)",
        },
        "reading_the_matrix": READING,
        "companion_evidence": {
            "accounting": "experiments/regcorner/probes/accounting.json",
            "row_diff": "experiments/regcorner/probes/row_diff.json",
            "parent_side_report": "experiments/regcorner/probes/_build/"
                                  "RC_parent_load.rvt.regcorner.json",
        },
        "probes": probes,
    }
    path = os.path.join(OUT_DIR, "probes.json")
    jdump(path, manifest)
    log(f"probes.json -> {relp(path)}")
    return path


# ===========================================================================
# H13: the fifth-surface patch (surface-stream-driven)
# ===========================================================================

#: the surface the H13 build authors -- asserted against the surface
#: stream's top donor-covered reach-3 candidate before building
H13_SURFACE_PREFIX = ("Latest:ADocument.m_pAppInfoManager->AppInfoManager"
                      ".m_appInfoArr[]->CategoryTracking.")


def _category_tracking(latest_value: dict) -> dict:
    ct = _appinfo_slot(latest_value, "CategoryTracking")
    if ct is None:
        raise RuntimeError("host ADocument has no CategoryTracking appinfo")
    return ct


def fifth_surface_rows(host_idmap: Dict[int, int]) -> Dict[str, Any]:
    """The donor cluster's own CategoryTracking rows (measured from the
    virgin rst), remapped through the host copy idmap = the native-modeled
    rows our unit's cluster is missing.  MEASURED LAWS (2026-08-05):
    m_categoryData is 30 parent-keyed CONTIGUOUS runs, ascending
    m_categoryId within a run (donor run: parent -2000059, indices
    117..486); m_gstyleData is globally ascending by (m_categoryId,
    m_gstyleId); the donor cluster contributes 4 + 4 rows (its family-
    scoped CategoryElem / GStyleElem twins)."""
    lat, _p = _latest_value(RST)
    ct = _category_tracking(lat.value)
    cat_twins = sorted(k for k in host_idmap
                       if k in set(_hp().NATIVE_RESOURCE_TWINS))
    from rvt.mutate import Document
    doc = Document.from_file(RST)
    cats = [t for t in cat_twins if doc.class_of(t) == "CategoryElem"]
    gss = [t for t in cat_twins if doc.class_of(t) == "GStyleElem"]
    cd_rows = [copy.deepcopy(r) for r in ct.get("m_categoryData") or []
               if r.get("m_categoryId") in cats]
    gd_rows = [copy.deepcopy(r) for r in ct.get("m_gstyleData") or []
               if r.get("m_categoryId") in cats or r.get("m_gstyleId") in gss]
    if len(cd_rows) != len(cats) or len(gd_rows) != len(gss):
        raise RuntimeError(f"donor CategoryTracking rows drifted: "
                           f"{len(cd_rows)}/{len(cats)} cat, "
                           f"{len(gd_rows)}/{len(gss)} gstyle")
    for r in cd_rows + gd_rows:
        for k, v in list(r.items()):
            if isinstance(v, int) and v in host_idmap:
                r[k] = host_idmap[v]
    parents = {r.get("m_parentCategoryId") for r in cd_rows}
    if len(parents) != 1:
        raise RuntimeError(f"donor cat rows carry != 1 parent: {parents}")
    return {"cat_rows": cd_rows, "gs_rows": gd_rows,
            "parent_category": next(iter(parents)),
            "donor_cat_twins": cats, "donor_gs_twins": gss}


def patch_category_tracking(path_in: str, path_out: str, *,
                            cat_rows: List[dict], gs_rows: List[dict],
                            parent_category: int) -> Dict[str, Any]:
    """Insert the remapped rows at their law-derived positions: cat rows at
    the ascending position inside the parent's contiguous run; gstyle rows
    at the global (categoryId, gstyleId) sorted position.  Codec
    byte-idempotence gated first; the post-edit laws are re-asserted."""
    from rvt import adocument as A
    lat, payload = _latest_value(path_in)
    if A.encode_latest(lat.value, trailer=lat.trailer) != payload:
        raise RuntimeError("Global/Latest codec is not byte-idempotent on "
                           "the base -- patch refused")
    ct = _category_tracking(lat.value)
    cd = ct.get("m_categoryData")
    gd = ct.get("m_gstyleData")
    have = {r.get("m_categoryId") for r in cd}
    if have & {r["m_categoryId"] for r in cat_rows}:
        raise RuntimeError("our cat rows already present")
    run = [i for i, r in enumerate(cd)
           if r.get("m_parentCategoryId") == parent_category]
    if not run or run != list(range(run[0], run[-1] + 1)):
        raise RuntimeError(f"parent {parent_category} run is not contiguous")
    run_ids = [cd[i]["m_categoryId"] for i in run]
    if run_ids != sorted(run_ids):
        raise RuntimeError("parent run is not ascending")
    at = run[-1] + 1
    for j, r in enumerate(sorted(cat_rows, key=lambda r: r["m_categoryId"])):
        if r["m_categoryId"] <= run_ids[-1]:
            raise RuntimeError("cat row id not above the run max -- "
                               "position law would need a mid-run insert")
        cd.insert(at + j, r)
    key = lambda r: (r.get("m_categoryId"), r.get("m_gstyleId"))  # noqa: E731
    for r in sorted(gs_rows, key=key):
        i = len(gd)
        while i > 0 and key(gd[i - 1]) > key(r):
            i -= 1
        gd.insert(i, r)
    # re-assert the measured laws post-edit
    run2 = [i for i, r in enumerate(cd)
            if r.get("m_parentCategoryId") == parent_category]
    ids2 = [cd[i]["m_categoryId"] for i in run2]
    if run2 != list(range(run2[0], run2[-1] + 1)) or ids2 != sorted(ids2):
        raise RuntimeError("post-edit cat run law violated")
    pos = [key(r) for r in gd if (r.get("m_categoryId") or 0) > 0]
    if pos != sorted(pos):
        raise RuntimeError("post-edit gstyle ascending law violated")
    new_latest = A.encode_latest(lat.value, trailer=lat.trailer)
    if not A.decode_latest(new_latest).clean:
        raise RuntimeError("edited Latest does not re-decode clean")
    _replace_stream(path_in, path_out, "Global/Latest", new_latest)
    return {"cat_rows_inserted": len(cat_rows), "cat_insert_index": at,
            "gs_rows_inserted": len(gs_rows),
            "categoryData_rows_after": len(cd),
            "gstyleData_rows_after": len(gd),
            "parent_category": parent_category}


def build_h13(spec_path: str) -> Dict[str, Any]:
    """H13 = H11's load + the top-ranked fifth-surface candidate's entries
    authored for our unit's cluster (native-modeled on the donor's own
    rows) + one V20-shape instance.  Reads the surface stream's published
    ranking and ASSERTS the top donor-covered candidate is the
    CategoryTracking surface this build authors -- refuses on drift."""
    FDB = _fdb()
    B = _bisect()
    FDB._install_schema()                                  # noqa: SLF001
    if not os.path.isfile(spec_path):
        raise SystemExit(
            f"fifth-surface spec not found: {relp(spec_path)}\n"
            f"H13 is built from the surface stream's candidate list "
            f"(experiments/regcorner/fifth_surface.json).  Poll "
            f"docs/inbox/regcorner-surface.md + experiments/regcorner/"
            f"*.json; when the ranking lands, pass it here.")
    spec = jload(spec_path)
    cands = [c for c in spec.get("candidates_missing_for_new_unit") or []
             if c.get("reach_score") == 3 and c.get("donor_unit_covered")]
    if not cands:
        raise SystemExit("the surface stream's ranking carries no "
                         "donor-covered reach-3 candidate -- nothing to patch")
    top = cands[0]
    if not str(top.get("surface", "")).startswith(H13_SURFACE_PREFIX):
        raise SystemExit(f"ranking drift: top donor-covered candidate is "
                         f"{top.get('surface')!r}, not the CategoryTracking "
                         f"surface this build authors -- re-derive H13")
    acct_path = os.path.join(OUT_DIR, "accounting.json")
    out = jload(acct_path)
    if "H11" not in (out.get("built") or {}):
        raise SystemExit("H11 not built -- run build first")
    parent = os.path.join(BUILD_DIR, "RC_parent_load.rvt")
    h11_load = os.path.join(BUILD_DIR, "H11_load.rvt")
    side = jload(parent + ".regcorner.json")
    host_idmap = {int(k): v for k, v in side["host_idmap"].items()}
    plan = side["plan"]
    t0 = time.time()
    try:
        rows = fifth_surface_rows(host_idmap)
        l13 = os.path.join(BUILD_DIR, "H13_load.rvt")
        prep = patch_category_tracking(
            h11_load, l13, cat_rows=rows["cat_rows"], gs_rows=rows["gs_rows"],
            parent_category=rows["parent_category"])
        probe = os.path.join(OUT_DIR, "H13.rvt")
        sym, fam = plan["symbol_ids"][0], plan["host_family_id"]
        prec = FDB.place_probe(l13, probe, symbol_id=sym, family_id=fam,
                               category=_hp().DONOR_CATEGORY)
        info = {
            "probe": "H13",
            "axis": "the FIFTH-SURFACE patch: H11's load + the donor "
                    "cluster's CategoryTracking rows remapped for our "
                    "copies (the surface stream's top donor-covered "
                    "candidate) + one V20-shape instance",
            "base": relp(RST), "file": relp(probe), "md5": md5_of(probe),
            "immediate_parent": relp(l13), "shared_parent": relp(parent),
            "symbol_id": sym, "family_id": fam,
            "instance_ids": [prec["instance_id"]], "instance": prec,
            "document_guid": plan["guid"],
            "edits": {"ct_retrofit": out["built"]["H11"]["edits"]["ct_retrofit"],
                      "category_tracking": {**prep,
                                            "rows": rows["cat_rows"] + rows["gs_rows"]}},
            "surface_spec": {"source": relp(spec_path),
                             "candidate": top.get("surface"),
                             "companions": [c.get("surface") for c in cands[1:3]]},
            "placement": "famdoc_bisect.place_probe (H7/H9-verbatim)"}
        out["built"]["H13"] = info
        log(f"H13 BUILT -> {relp(probe)} (md5 {info['md5'][:8]}, "
            f"instance {prec['instance_id']})")
        acc_load = B.account("H13_load", l13, h11_load, declared_base=RST,
                             instance_ids=[], with_regdiff=False)
        acc_probe = B.account("H13", probe, l13, declared_base=RST,
                              instance_ids=info["instance_ids"])
        out["accounting"]["H13"] = {"load_vs_parent": acc_load,
                                    "probe_vs_load": acc_probe}
        prf = axis_proofs_h13(probe, info, rows)
        info["axis_proofs"] = prf
        va, vl = acc_probe["validator"], acc_load["validator"]
        log(f"H13: validator {va['n_errors']} err probe / {vl['n_errors']} "
            f"err load (unexpected {len(va['unexpected_errors'])}/"
            f"{len(vl['unexpected_errors'])}), census coherent "
            f"{acc_probe['census']['coherent']}, survivor "
            f"{'OK' if acc_probe['survivor_law_ok'] else 'VIOLATED'}, "
            f"streams changed by edit: "
            f"{[c['stream'] for c in acc_load['streams_changed']]}, "
            f"axis proofs {'OK' if prf['ok'] else 'FAILED'}")
        if not prf["ok"]:
            raise RuntimeError(f"H13 axis proofs failed: {prf['failures']}")
    except SystemExit:
        raise
    except Exception as e:                                 # noqa: BLE001
        out.setdefault("errors", {})["H13"] = f"{type(e).__name__}: {e}"
        out["errors"]["H13.traceback"] = traceback.format_exc(limit=12)
        log(f"H13 BUILD FAILED: {type(e).__name__}: {e}")
        jdump(acct_path, out)
        return out
    out["h13_seconds"] = round(time.time() - t0, 1)
    jdump(acct_path, out)
    write_probes_json(out)
    return out


def axis_proofs_h13(path: str, info: Dict[str, Any],
                    rows: Dict[str, Any]) -> Dict[str, Any]:
    """H13 = H11's proofs + the CategoryTracking rows present for our
    copies, laws intact."""
    prf = axis_proofs("H11", path, info)      # native row + null adoc + V20
    failures = list(prf["failures"])
    lat, _p = _latest_value(path)
    ct = _category_tracking(lat.value)
    cd = ct.get("m_categoryData") or []
    gd = ct.get("m_gstyleData") or []
    want_cat = {r["m_categoryId"] for r in rows["cat_rows"]}
    want_gs = {(r["m_categoryId"], r["m_gstyleId"]) for r in rows["gs_rows"]}
    got_cat = {r.get("m_categoryId") for r in cd} & want_cat
    got_gs = {(r.get("m_categoryId"), r.get("m_gstyleId"))
              for r in gd} & want_gs
    prf["category_tracking"] = {
        "cat_rows_present": len(got_cat), "gs_rows_present": len(got_gs),
        "categoryData_rows": len(cd), "gstyleData_rows": len(gd)}
    if got_cat != want_cat:
        failures.append(f"cat rows missing: {sorted(want_cat - got_cat)}")
    if got_gs != want_gs:
        failures.append(f"gstyle rows missing: {sorted(want_gs - got_gs)}")
    prf["failures"] = failures
    prf["ok"] = not failures
    return prf


def stage_h13() -> Dict[str, Any]:
    B = _bisect()
    spec = importlib.util.spec_from_file_location(
        "_regcorner_probe_batch13", os.path.join(HERE, "probe_batch.py"))
    pb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pb)
    f = os.path.join(OUT_DIR, "H13.rvt")
    if not os.path.isfile(f):
        raise SystemExit("H13 not built (run h13 first)")
    manifest = pb.stage_batch(
        [f], control_from=RST,
        batch_n=B._campaign_global_next_batch(),           # noqa: SLF001
        note="regcorner H13: the fifth-surface patch.  The surface "
             "stream's ranking (experiments/regcorner/fifth_surface.json) "
             "names CategoryTracking (host-ADocument AppInfo slot 28: "
             "family-cluster CategoryElem/GStyleElem rows; 41/52 native "
             "units incl. the donor; absent for every famload unit; "
             "outside the four-registry model) as the top donor-covered "
             "instance-walk candidate.  H13 = H11's load (native-modeled "
             "CT row) + the donor cluster's 4+4 rows remapped for our "
             "copies at the law-derived positions + one V20-shape "
             "instance.  Read with batch 40's matrix: H13 PASS where "
             "H11 FAILED convicts the fifth surface (CategoryTracking); "
             "H13 FAIL extends the elimination to the next candidate.")
    log(f"STAGED H13 batch {manifest['batch']} -> {manifest['manifest_path']}")
    for e in manifest["entries"]:
        log(f"  [{e['order']}] {e.get('staged_as')} (base {e.get('base')}, "
            f"{e.get('kind')})")
    return manifest


# ===========================================================================
# verify + stage
# ===========================================================================

def verify() -> Dict[str, Any]:
    B = _bisect()
    _fdb()._install_schema()                               # noqa: SLF001
    acct_path = os.path.join(OUT_DIR, "accounting.json")
    if not os.path.isfile(acct_path):
        raise SystemExit("no accounting.json -- run build first")
    out = jload(acct_path)
    fresh = {}
    for name, info in (out.get("built") or {}).items():
        child = os.path.join(ROOT, info["file"])
        load_path = os.path.join(ROOT, info["immediate_parent"])
        if not (os.path.isfile(child) and os.path.isfile(load_path)):
            fresh[name] = {"error": "file(s) missing"}
            continue
        r = B.account(name, child, load_path, declared_base=RST,
                      instance_ids=info.get("instance_ids") or [],
                      with_regdiff=False)
        prf = axis_proofs(name, child, info)
        fresh[name] = {"account": r, "axis_proofs": prf}
        va = r["validator"]
        log(f"{name}: validator {va['n_errors']} err (unexpected "
            f"{len(va['unexpected_errors'])}), coherent "
            f"{r['census']['coherent']}, survivor "
            f"{'OK' if r['survivor_law_ok'] else 'VIOLATED'}, axis proofs "
            f"{'OK' if prf['ok'] else 'FAILED'}")
    return fresh


def stage() -> Dict[str, Any]:
    B = _bisect()
    spec = importlib.util.spec_from_file_location(
        "_regcorner_probe_batch", os.path.join(HERE, "probe_batch.py"))
    pb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pb)
    files = [os.path.join(OUT_DIR, f"{n}.rvt") for n in LADDER]
    missing = [f for f in files if not os.path.isfile(f)]
    if missing:
        raise SystemExit(f"missing probes (run build): {[relp(m) for m in missing]}")
    manifest = pb.stage_batch(
        files, control_from=RST,
        batch_n=B._campaign_global_next_batch(),           # noqa: SLF001
        note="regcorner: the registration-corner probes (post-verdict-#34). "
             "H9 FAIL + H10 PASS + V20 PASS => two suspects: registration "
             "row content vs a fifth ADocument surface.  All three probes "
             "share one byte-identical H9-recipe parent; H12 = + the "
             "donor's POPULATED inline ADocument (H6 swap law); H11 = + the "
             "ContentTable row re-authored on the donor's own native row "
             "(GUID kept ours); H11x12 = both.  Upload in manifest order "
             "(H12 first); read experiments/regcorner/probes/probes.json "
             "reading_the_matrix.")
    log(f"STAGED batch {manifest['batch']} -> {manifest['manifest_path']}")
    for e in manifest["entries"]:
        log(f"  [{e['order']}] {e.get('staged_as')} (base {e.get('base')}, "
            f"{e.get('kind')})")
    return manifest


# ===========================================================================

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("measure", help="row_diff.json (famload vs native rows)")
    sub.add_parser("build", help="parent + H12 + H11 + H11x12 (+ gates + probes.json)")
    sub.add_parser("verify", help="re-run gates on the emitted probes")
    sub.add_parser("stage", help="probe_batch gate + stage (control = rst copy)")
    p13 = sub.add_parser("h13", help="build the fifth-surface patch from the "
                                     "surface stream's spec")
    p13.add_argument("spec", nargs="?",
                     default=os.path.join(ROOT, "experiments", "regcorner",
                                          "fifth_surface.json"),
                     help="path to the surface stream's candidate ranking "
                          "(default: experiments/regcorner/fifth_surface.json)")
    sub.add_parser("stageh13", help="probe_batch gate + stage H13 as its own "
                                    "batch (control = rst copy)")
    a = ap.parse_args(argv)
    if a.cmd == "measure":
        measure()
        return 0
    if a.cmd == "build":
        out = build()
        n_err = len([k for k in out["errors"]
                     if not k.endswith((".traceback", ".tb"))])
        log(f"build done: {len(out['built'])} probe(s), {n_err} error(s), "
            f"{out.get('seconds')}s")
        return 1 if n_err else 0
    if a.cmd == "verify":
        fresh = verify()
        bad = [n for n, r in fresh.items()
               if r.get("error") or not (r.get("axis_proofs") or {}).get("ok")]
        log(f"verify done: {len(fresh)} probe(s), failures: {bad or 'none'}")
        return 1 if bad else 0
    if a.cmd == "stage":
        stage()
        return 0
    if a.cmd == "h13":
        out = build_h13(a.spec)
        return 1 if (out.get("errors") or {}).get("H13") else 0
    if a.cmd == "stageh13":
        stage_h13()
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
