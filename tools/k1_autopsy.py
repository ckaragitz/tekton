#!/usr/bin/env python
"""k1_autopsy.py -- WHY does K1 fail when R5 (its parent) passes?

K1.rvt (experiments/genesis/triage/K1.rvt) = "R5 minus the placed model" and
was the never-uploaded BASE of the entire substitution program.  It FAILS the
Autodesk reader (CRASH signature: extractor exit -1073741831, NO
Revit-DocumentCorruption line, 'Design is empty'), while its parent R5.rvt
PASSES and so does R9.rvt (which removed STRICTLY MORE content).  This tool

  1. DIFFS K1 vs R5 at the element level: removed ids by class, surviving
     ids, and byte-diffs every surviving record (seq 101/102/103) -- a
     reduction should leave survivors byte-identical; K1's does not.
  2. CROSS-REFERENCES every K1 deletion with the CERTIFIED reduction ladder
     v2 (R6..R10) and the passing triage probes (K3/K4): at which certified
     stage was each K1-deleted id also deleted?  which ids did the certified
     files always KEEP?  which surviving-modified records are BYTE-
     VINDICATED by a passing file?
  3. Proves the global streams (Latest / History / ContentDocuments / BFI /
     DIT / PartitionTable / Contents / schema) are byte-identical to R5's and
     that K1's Global/Latest dangling set is R9's tolerated set + 1 room.
  4. BUILDS THE BISECTION LADDER (all derived from certified R5, all
     validator-clean, one variable per rung) that pins the fatal K1 novelty
     in <= 3 viewer rounds -- experiments/genesis/autopsy/*.rvt + probes.json.

THE FINDING (see docs/writer/k1-autopsy.md): K1's difference from the union
of viewer-PASSED files is CONFINED to (a) 22 SURVIVING elements that carry
neutraliser EDITS no passing file carries (5 3D views + 1 section + 1
rendering view: hidden/override/parents maps pruned; 1 graphical column
schedule: whole grid-intersection struct entries dropped; a registry-indexed
default FamilySymbol orphaned (m_familyId -> -1) + its surrogates; a
StairsTriserSymbol with m_hostId -> -1; an InteriorElevArrow attached to
nothing; a LevelRoomPlan / AreaSchemePlanTopologies with a room pruned; 7
sheets whose edit-class IS vindicated), and (b) ONE deleted element every
passing file keeps (an area RoomElem 1004910).  Every other K1 deletion
(2,115 / 2,117) was also made by the certified R9 / R6; every other stream
and survivor byte matches R5.  The neutralise pre-pass (rvt.manipulate
._neutralise: "structured entry mentioning a target is DROPPED") applied to
element classes the certified probes never edited is the mechanism.

Usage (repo root):
  .venv/bin/python tools/k1_autopsy.py --analyze          # evidence JSON only
  .venv/bin/python tools/k1_autopsy.py --build            # ladder + probes.json
  .venv/bin/python tools/k1_autopsy.py                    # both
  .venv/bin/python tools/k1_autopsy.py --build --only K1a_editfree,K1_suspect

Territory: this file, experiments/genesis/autopsy/*, docs/writer/k1-autopsy.md,
docs/inbox/genesis-autopsy.md.  Imports (does NOT modify) genesis_triage /
rvt_reduce / rvt.manipulate / rvt.reduce / rvt.validate / rvt.regdiff.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Optional, Set, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import genesis_triage as GT                                      # noqa: E402
import rvt_reduce as RR                                          # noqa: E402
from rvt.container import open_rvt                               # noqa: E402
from rvt.mutate import Document                                  # noqa: E402
from rvt.reduce import delete_elements, scan_stream_ids, verify_reduced  # noqa: E402

GEN = os.path.join(ROOT, "experiments", "genesis")
TRIAGE = os.path.join(GEN, "triage")
OUTDIR = os.path.join(GEN, "autopsy")
R5 = os.path.join(GEN, "R5.rvt")                    # viewer PASS -- K1's parent
K1 = os.path.join(TRIAGE, "K1.rvt")                 # viewer FAIL (crash) -- subject
STEP1 = os.path.join(TRIAGE, "K1_step1_neutralised.rvt")  # K1's modify-only intermediate
CERT = {                                            # viewer-PASSED anchors
    "R5": R5, "R6": os.path.join(GEN, "R6.rvt"), "R7": os.path.join(GEN, "R7.rvt"),
    "R8": os.path.join(GEN, "R8.rvt"), "R9": os.path.join(GEN, "R9.rvt"),
    "R10": os.path.join(GEN, "R10.rvt"),           # (not viewer-tested; deepest arbiter rung)
    "K3": os.path.join(TRIAGE, "K3.rvt"), "K4": os.path.join(TRIAGE, "K4.rvt"),
}
EVIDENCE_JSON = os.path.join(OUTDIR, "autopsy_evidence.json")

os.makedirs(OUTDIR, exist_ok=True)


# ===========================================================================
# EDIT GROUPS -- the referrer classes K1's neutraliser edited whose records
# SURVIVE in K1 (the transient CurveElem / LinearDimString / Alignment
# referrers are seed members and are deleted; their edits never survive).
# ===========================================================================
GROUPS: Dict[str, dict] = {
    "G4_orphaning": {
        "referrers": {"FamilySymbol", "FamilySurrogate", "FamSymSurrogate",
                      "StairsTriserSymbol"},
        "what": ("ORPHANED family/type objects: the in-place Family (876493) "
                 "is deleted while its FamilySymbol (876569, indexed as a "
                 "category DEFAULT symbol in ADocument SymbolIdMgr) survives "
                 "with m_familyId -> -1 / m_ownerInstanceId -> -1, its "
                 "FamilySurrogate (876494, m_elemId -> -1) and "
                 "FamSymSurrogate (876570) survive, and StairsTriserSymbol "
                 "513310 keeps a stairs element as host with m_hostId -> -1. "
                 "A registry-indexed live type whose family pointer is null: "
                 "the audit passes (the ids exist), the extractor dereferences "
                 "symbol -> family -> null.  RANK 1 for the CRASH signature."),
    },
    "G3_schedule": {
        "referrers": {"DBViewGraphSchedColumn"},
        "what": ("Graphical Column Schedule 1250040: rvt.manipulate._neutralise's "
                 "'structured entry mentioning a target is DROPPED' rule "
                 "removed whole m_visGridIntPntArr struct entries (each named "
                 "a deleted column in m_columnIdArr), collaterally dropping "
                 "their references to STILL-PRESENT grids and their m_pDoc "
                 "weakrefs -- 219 leaf changes; a schedule view state that "
                 "no Autodesk file exhibits (Revit REGENERATES this table). "
                 "RANK 2 (a view the extractor renders)."),
    },
    "G5_topology": {
        "referrers": {"LevelRoomPlan", "AreaSchemePlanTopologies",
                      "InteriorElevArrow"},
        "what": ("Plan-topology / annotation attachments: LevelRoomPlan "
                 "1004909 and AreaSchemePlanTopologies 9744 pruned of area "
                 "RoomElem 1004910 (which the edit then let maxgc DELETE -- the "
                 "ONE element every passing file R9/R10/K3/K4 keeps, and the ONE "
                 "extra Latest-dangling id beyond R9's tolerated set), plus "
                 "InteriorElevArrow 8231 whose m_endAttach0.m_geomRef.m_elemId "
                 "-> -1 (an elevation arrow attached to nothing). RANK 3."),
    },
    "G2_viewmaps": {
        "referrers": {"DBView3d", "DBViewSection", "DBViewRendering"},
        "what": ("Model-view state maps: 5 DBView3d + 1 DBViewSection with "
                 "m_oHiddenElementsViewSettings.m_hiddenElements pruned, "
                 "m_oAdHocOverrides.m_elementMap entries dropped and header "
                 "m_parents.m_deletion webs pruned (up to 459 leaves per view); "
                 "1 DBViewRendering with m_imageInstanceId -> -1.  Closest of "
                 "the groups to Revit's own delete semantics (Revit prunes "
                 "these maps itself). RANK 4."),
    },
    "G1_sheets": {
        "referrers": {"DBViewDrafting"},
        "what": ("8 sheets with m_sheetTitleBlockId -> -1 (their title-block "
                 "FamilyInstances deleted).  BYTE-VINDICATED: sheet 1457028 "
                 "carries this exact record BYTE-IDENTICALLY in the passing "
                 "K3/K4 files, and K4 deletes its title-block instance 1457033 "
                 "and PASSES.  Expected PASS -- the ladder's internal control "
                 "that the neutralise+delete mechanics alone are accepted."),
    },
}
#: G6 -- the TRANSIENT referrers: 381 CurveElem / LinearDimString / Alignment
#: elements whose fields (m_sketchPlaneId, m_miscId, m_assocId, witness
#: refs, m_parents) K1 neutralised and then DELETED.  Their edits leave NO
#: surviving record; their ONLY effect is CUTTING PINS: a pinned seed member
#: (a dimension held by ref planes, an area-boundary curve held by a plan
#: topology) forward-pins the walls / sketch planes it references; nulling
#: those references unlocks whole sketch / dimension / model chains.  Not a
#: rung of its own (editing them without deleting them would manufacture
#: curve-without-sketch-plane states K1 does NOT contain); tested as the
#: COMPLEMENT of K1z_persistent (K1 = K1z + G6).
TRANSIENT_REFERRERS: Set[str] = {"CurveElem", "LinearDimString", "Alignment"}
#: information-value order (strongest single suspect first)
GROUP_ORDER = ["G4_orphaning", "G3_schedule", "G5_topology",
               "G2_viewmaps", "G1_sheets"]
ALL_REFERRER_CLASSES: Set[str] = set().union(*(g["referrers"] for g in GROUPS.values()))


# ===========================================================================
# helpers
# ===========================================================================

def log(msg: str) -> None:
    print(msg, flush=True)


def _relp(p: str) -> str:
    return os.path.relpath(p, ROOT)


def _rec_sha(doc, eid: int, seq: int) -> Optional[str]:
    r = doc.idx[seq].get(eid)
    return None if r is None else hashlib.sha1(r.payload).hexdigest()


def _all_ids(doc) -> Set[int]:
    return set(doc.idx[101]) | set(doc.idx[102]) | set(doc.idx[103])


def _flat(x, pre: str = "") -> Dict[str, object]:
    out: Dict[str, object] = {}
    if isinstance(x, dict):
        for k, v in x.items():
            out.update(_flat(v, f"{pre}.{k}" if pre else k))
    elif isinstance(x, list):
        for i, v in enumerate(x):
            out.update(_flat(v, f"{pre}[{i}]"))
    else:
        out[pre] = x
    return out


def _name(doc, eid: int) -> Optional[str]:
    v = doc.value(eid) or {}
    for f in ("m_viewName", "m_name", "m_text", "m_familyName"):
        if v.get(f):
            return str(v.get(f))
    return None


def _field_root(path: str) -> str:
    """m_parents.value.m_deletion[9] -> m_parents.m_deletion (index-free)."""
    import re
    p = re.sub(r"\[\d+\]", "[]", path)
    return p.replace(".value.", ".")


# ===========================================================================
# 1. ELEMENT-LEVEL DIFF (removed / surviving / modified)
# ===========================================================================

def element_diff(a, b) -> dict:
    """Compare two loaded Documents record-by-record over all three seqs.

    Returns removed / added id sets and, for ids present in BOTH, the ids
    whose records differ (per seq).  Payload equality is the criterion (a
    reduction must leave survivors byte-identical)."""
    ida, idb = _all_ids(a), _all_ids(b)
    modified: Dict[int, List[int]] = {}
    for eid in ida & idb:
        seqs = [s for s in (101, 102, 103)
                if (_rec_sha(a, eid, s), (a.idx[s].get(eid) or _E).class_id)
                != (_rec_sha(b, eid, s), (b.idx[s].get(eid) or _E).class_id)]
        if seqs:
            modified[eid] = seqs
    return {"removed": ida - idb, "added": idb - ida, "modified": modified,
            "ids_a": ida, "ids_b": idb}


class _E:                      # sentinel with a class_id attr for None records
    class_id = None


def field_diff(a, b, eid: int, seq: int, k1ids: Set[int]) -> dict:
    """Decoded field-level diff of one element between two docs, tagging each
    changed id-valued leaf with whether its target still exists in ``b``."""
    va, vb = _flat(a.value(eid, seq) or {}), _flat(b.value(eid, seq) or {})
    keys = sorted(set(va) | set(vb))
    changes = []
    for k in keys:
        x, y = va.get(k, "<absent>"), vb.get(k, "<absent>")
        if x == y:
            continue
        note = None
        if isinstance(x, int) and not isinstance(x, bool) and x > 0:
            note = "target-present" if x in k1ids else "target-deleted"
        changes.append({"path": k, "before": x, "after": y, "target": note})
    ra, rb = a.idx[seq].get(eid), b.idx[seq].get(eid)
    return {"seq": seq, "bytes_before": len(ra.payload) if ra else 0,
            "bytes_after": len(rb.payload) if rb else 0,
            "leaf_changes": len(changes),
            "fields": Counter(_field_root(c["path"]) for c in changes).most_common(12),
            "sample": changes[:6]}


# ===========================================================================
# 2. THE FULL ANALYSIS
# ===========================================================================

def analyze(write: bool = True) -> dict:
    t0 = time.time()
    log("== loading documents ==")
    docs = {n: Document.from_file(p) for n, p in CERT.items() if os.path.exists(p)}
    docs["K1"] = Document.from_file(K1)
    docs["STEP1"] = Document.from_file(STEP1) if os.path.exists(STEP1) else None
    r5, k1 = docs["R5"], docs["K1"]
    k1ids = set(k1.et_by_id)

    ev: dict = {"subject": _relp(K1), "parent": _relp(R5),
                "generated": time.strftime("%Y-%m-%d %H:%M:%S")}

    # ---- 1a. the two-step decomposition (R5 -> STEP1 -> K1)
    d_all = element_diff(r5, k1)
    ev["k1_vs_r5"] = {"removed": len(d_all["removed"]),
                      "added": len(d_all["added"]),
                      "surviving_modified": len(d_all["modified"])}
    log(f"K1 vs R5: removed {len(d_all['removed']):,}, added {len(d_all['added'])}, "
        f"SURVIVING-MODIFIED {len(d_all['modified'])}")
    if docs["STEP1"] is not None:
        d1 = element_diff(r5, docs["STEP1"])      # pure modify
        d2 = element_diff(docs["STEP1"], k1)      # pure delete
        edited = set(d1["modified"])
        ev["decomposition"] = {
            "step1_modify_only": {"removed": len(d1["removed"]), "added": len(d1["added"]),
                                  "edited": len(edited),
                                  "edited_by_class": Counter(r5.class_of(e) for e in edited).most_common()},
            "step2_delete_only": {"removed": len(d2["removed"]),
                                  "survivors_modified": len(d2["modified"])},
            "edited_then_deleted": len(edited & d_all["removed"]),
            "edited_and_surviving": len(edited - d_all["removed"]),
        }
        log(f"  step1 (modify): {len(edited)} elements edited; step2 (delete): "
            f"{len(d2['removed'])} removed, {len(d2['modified'])} survivors touched")
        log(f"  step1-edited then deleted: {len(edited & d_all['removed'])}; "
            f"edited AND surviving: {len(edited - d_all['removed'])}")

    # ---- 1b. removed by class
    removed = d_all["removed"]
    ev["removed_by_class"] = Counter(r5.class_of(e) for e in removed).most_common()

    # ---- 1c. the modified survivors, decoded field-by-field + edit-group tag
    mods = []
    for eid in sorted(d_all["modified"], key=lambda e: (k1.class_of(e) or "", e)):
        cls = k1.class_of(eid) or "?"
        grp = next((g for g, spec in GROUPS.items() if cls in spec["referrers"]), "UNGROUPED")
        entry = {"id": eid, "class": cls, "name": _name(k1, eid), "group": grp,
                 "in_certified_files": {n: (eid in docs[n].et_by_id)
                                        for n in ("R9", "R10", "K3", "K4") if n in docs},
                 "seq_diffs": [field_diff(r5, k1, eid, s, k1ids)
                               for s in d_all["modified"][eid]]}
        # byte-vindication: is K1's record byte-identical to a PASSING file's?
        vind = []
        for n in ("K3", "K4", "R9"):
            if n in docs and eid in docs[n].et_by_id and all(
                    _rec_sha(k1, eid, s) == _rec_sha(docs[n], eid, s) for s in (101, 102, 103)):
                vind.append(n)
        entry["byte_vindicated_by"] = vind
        mods.append(entry)
    ev["modified_survivors"] = mods
    vind_ids = {m["id"] for m in mods if m["byte_vindicated_by"]}
    log(f"  modified survivors: {len(mods)}; byte-vindicated by a passing file: "
        f"{sorted(vind_ids)}")
    log("  edit groups: " + ", ".join(
        f"{g}={sum(1 for m in mods if m['group'] == g)}" for g in list(GROUPS) + ['UNGROUPED']))

    # ---- 2. CERTIFIED CROSS-REFERENCE of every K1 deletion
    I = {n: set(d.et_by_id) for n, d in docs.items() if d is not None}
    stage_of: Dict[int, str] = {}
    for e in removed:
        if e in I["R9"]:
            stage_of[e] = "KEPT_BY_R9"          # certified file keeps it
        elif e in I["R8"]:
            stage_of[e] = "R9"
        elif e in I["R7"]:
            stage_of[e] = "R8"
        elif e in I["R6"]:
            stage_of[e] = "R7"
        else:
            stage_of[e] = "R6"
    ev["deletion_certification"] = {
        "counts": Counter(stage_of.values()).most_common(),
        "kept_by_R9": [{"id": e, "class": r5.class_of(e),
                        "in_R10": e in I["R10"], "in_K3": e in I["K3"], "in_K4": e in I["K4"]}
                       for e in sorted(removed) if stage_of[e] == "KEPT_BY_R9"],
        "R6_deleted_classes": Counter(r5.class_of(e) for e in removed
                                      if stage_of[e] == "R6").most_common(),
    }
    log(f"  deletion certification: {dict(Counter(stage_of.values()))}")
    for x in ev["deletion_certification"]["kept_by_R9"]:
        log(f"    K1 deleted id {x['id']} ({x['class']}) which R9/R10/K3/K4 keep: "
            f"R10={x['in_R10']} K3={x['in_K3']} K4={x['in_K4']}")

    # ---- 3. STREAM-LEVEL identity
    streams = {}
    inv = {}
    for name in ("R5", "R9", "K1"):
        path = CERT.get(name, K1) if name != "K1" else K1
        with open_rvt(path) as f:
            m = {}
            for si in f.streams():
                try:
                    log_ = f.logical(si.name)
                    m[si.name] = hashlib.sha256(log_).hexdigest()
                except Exception as ex:                       # pragma: no cover
                    m[si.name] = f"ERR:{ex!r}"
            inv[name] = m
    for s in sorted(set(inv["R5"]) | set(inv["K1"])):
        streams[s] = {"K1==R5": inv["K1"].get(s) == inv["R5"].get(s),
                      "K1==R9": inv["K1"].get(s) == inv["R9"].get(s)}
    ev["stream_identity"] = streams
    changed = [s for s, v in streams.items() if not v["K1==R5"]]
    log(f"  streams differing from R5: {changed} (all others byte-identical to R5 and R9)")

    # ---- 4. Global/Latest dangling-set inclusion
    with open_rvt(R5) as f:
        latest_r5 = f.inflate("Global/Latest")
    with open_rvt(K1) as f:
        latest_k1 = f.inflate("Global/Latest")
    same_latest = hashlib.sha256(latest_r5).digest() == hashlib.sha256(latest_k1).digest()
    refset = scan_stream_ids(latest_r5, set(r5.et_by_id))
    dang = {n: refset - set(docs[n].et_by_id) for n in ("R5", "R9", "K1")}
    extra = dang["K1"] - dang["R9"]
    ev["latest_dangling"] = {
        "latest_byte_identical_R5_K1": same_latest,
        "R5_live_ids_referenced": len(refset),
        "dangling": {n: len(v) for n, v in dang.items()},
        "K1_subset_of_R9": dang["K1"] <= dang["R9"],
        "K1_minus_R9": [{"id": e, "class": r5.class_of(e)} for e in sorted(extra)],
    }
    log(f"  Latest byte-identical R5/K1: {same_latest}; dangling R5={len(dang['R5'])} "
        f"R9={len(dang['R9'])} K1={len(dang['K1'])}; K1-R9 = "
        f"{[(e, r5.class_of(e)) for e in sorted(extra)]}")
    try:
        import regdiff as RG                                    # tools/ shim
    except Exception:
        from rvt import regdiff as RG                            # type: ignore
    try:
        rdoc = RG.RegDoc(R5)
        surf_ids = sorted(extra) + [876493, 876569, 1457033]
        surf = rdoc.adoc_surface(surf_ids)
        ev["latest_dangling"]["adocument_surface"] = {str(k): v for k, v in surf.items()}
        for k, v in surf.items():
            log(f"    ADocument surface of {k}: {v}")
    except Exception as ex:                                       # pragma: no cover
        ev["latest_dangling"]["adocument_surface_error"] = repr(ex)

    # ---- 5. four-registry / content census (R5 vs K1)
    ev["census"] = {n: {k: c.get(k) for k in
                        ("elements", "save_units", "contentdocs_entries",
                         "contenttable_records", "familymgr_entries",
                         "familymgr_doc_guids", "adocument_clean")}
                    for n, c in (("R5", GT.census(R5)), ("K1", GT.census(K1)),
                                 ("R9", GT.census(CERT["R9"])))}
    log(f"  census: {ev['census']}")

    ev["seconds"] = round(time.time() - t0, 1)
    if write:
        with open(EVIDENCE_JSON, "w") as fh:
            json.dump(ev, fh, indent=1, default=lambda o: sorted(o) if isinstance(o, set) else str(o))
        log(f"== evidence -> {_relp(EVIDENCE_JSON)} ({ev['seconds']}s) ==")
    return ev


# ===========================================================================
# 3. THE BISECTION LADDER
# ===========================================================================

def _placed_targets(st5: dict) -> Set[int]:
    """EXACTLY K1's neutralisation target set (genesis_triage.build_K1)."""
    placed = GT._ids_of_classes(st5, GT.K1_PLACED) | GT._inplace_family_chains(st5)
    return GT._own_fixpoint(st5, placed)


def neutralise_grouped(st: dict, targets: Set[int], out_path: str, *,
                       allowed: Set[str], name: str) -> dict:
    """K1's step-1 neutraliser (identical mechanics: rvt.manipulate referrers
    + _neutralise + commit_plans + verify), RESTRICTED to referrers whose
    class is in ``allowed``.  Referrers of other classes keep their fields
    (and therefore keep PINNING the targets they name at maxgc time).
    ``allowed = None`` -> edit every referrer (K1's own behaviour)."""
    from rvt import manipulate as MP
    doc = st["doc"]
    refmap = MP.referrers(doc, targets)
    sess = MP.session(doc)
    # the EditSession is cached on the (shared) Document: reset EVERYTHING so
    # no earlier rung's neutralised working copy leaks into this rung.
    sess.plans.clear()
    sess.work = {}
    sess.removed = set()
    plans, edit_log = [], []
    considered = Counter()
    for rid in sorted(refmap):
        if rid in targets or rid not in st["host"]:
            continue
        info = refmap[rid]
        cls = info["class"]
        considered[cls] += 1
        if allowed is not None and cls not in allowed:
            continue
        pl = MP.ModifyPlan(kind="neutralise", elem_id=rid, class_name=cls)
        touched = False
        for seq in sorted(info["refs"]):
            try:
                val = sess.value(rid, seq)
            except Exception as e:                                # left as-is
                edit_log.append({"id": rid, "class": cls, "seq": seq, "error": repr(e)})
                continue
            ed = MP._neutralise(val, targets)
            if not ed:
                continue
            touched = True
            edit_log.append({"id": rid, "class": cls, "seq": seq,
                             "n_edits": len(ed), "edits": ed[:8]})
            pl.record_edits.append(sess.replacement(
                rid, seq, f"{name}: neutralise refs to placed model"))
        if touched:
            plans.append(pl)
    MP.commit_plans(st["src"], out_path, plans)
    ver = MP.verify_manipulated(out_path, edited_ids=[p.elem_id for p in plans])
    return {"referrer_elements_edited": len(plans),
            "edited_by_class": Counter(p.class_name for p in plans).most_common(),
            "candidate_referrers_by_class": considered.most_common(30),
            "edits": edit_log,
            "verify": {k: ver.get(k) for k in ("crc_failures", "ecc_mismatches",
                                                "walker_errors", "stamps_ok",
                                                "elemtable_count",
                                                "isize_identity_mismatches")}}


def _rung(name: str, *, allowed: Optional[Set[str]], desc: str, tests: str,
          pass_means: str, fail_means: str, restrict_seed_to_group: bool = False,
          st5: Optional[dict] = None, seed_fn=None) -> dict:
    """Build one rung: R5 -> [grouped neutralisation] -> maxgc -> validate.
    ``seed_fn(st, targets)`` may override the default seed construction."""
    t0 = time.time()
    st5 = st5 or RR.build_state_v2(R5)
    targets = _placed_targets(st5)
    out = os.path.join(OUTDIR, f"{name}.rvt")
    nrep = None
    src_for_gc = R5
    if allowed is None or allowed:            # some neutralisation requested
        step = os.path.join(OUTDIR, f".{name}_step1.rvt")
        nrep = neutralise_grouped(st5, targets, step, allowed=allowed, name=name)
        src_for_gc = step
    st = st5 if src_for_gc == R5 else RR.build_state_v2(src_for_gc)
    if restrict_seed_to_group:
        # MINIMAL probe: seed = only the targets the EDITED referrers named
        edited_ids = {e["id"] for e in (nrep or {}).get("edits", []) if e.get("n_edits")}
        seed: Set[int] = set()
        for rid in edited_ids:
            seed |= (st5["graph"].get(rid, set()) & targets)
        # close FORWARD inside the placed set (the whole assembly the edited
        # referrers touch: the in-place family's instance + children, the
        # stairs' runs/supports/path) so the probe deletes a self-consistent
        # component and reproduces K1's orphaned states exactly.
        front = set(seed)
        while front:
            nxt: Set[int] = set()
            for e in front:
                for t in st5["graph"].get(e, ()):
                    if t in targets and t not in seed:
                        seed.add(t)
                        nxt.add(t)
            front = nxt
        seed = GT._own_fixpoint(st, {e for e in seed if e in st["host"]})
    elif seed_fn is not None:
        seed = seed_fn(st, targets)
    else:
        seed = {e for e in targets if e in st["host"]}
        seed |= GT._ids_of_classes(st, GT.K1_RESIDUE_SWEEP)
        seed = GT._own_fixpoint(st, seed)
    seed = RR._protect_history(st, seed)
    delete, kept, pin_ev = RR.maxgc(st, seed)
    delete_elements(src_for_gc, out, delete)
    struct_ok = verify_reduced(out, delete)
    val = GT.validate(out)
    cen = GT.census(out)
    lat_dangling = len(st["ext"].get("Global/Latest", set()) & delete)
    rep = {
        "rung": name, "kind": ("modify+gc-delete" if nrep else "gc-delete"),
        "base": _relp(R5), "base_certification": "viewer PASS (viewer-certified.json)",
        "out": _relp(out), "description": desc, "tests": tests,
        "if_PASS": pass_means, "if_FAIL": fail_means,
        "neutralisation": {
            "referrer_classes_allowed": (sorted(allowed) if allowed else
                                         ("ALL (K1 semantics)" if allowed is None else "NONE")),
            "referrer_elements_edited": (nrep or {}).get("referrer_elements_edited", 0),
            "edited_by_class": (nrep or {}).get("edited_by_class", []),
            "candidate_referrers_by_class": (nrep or {}).get("candidate_referrers_by_class", []),
            "verify": (nrep or {}).get("verify"),
        },
        "seed": len(seed), "deleted": len(delete), "kept_pinned": len(kept),
        "deleted_by_class": Counter(st["cls_of"].get(e, "?") for e in delete).most_common(60),
        "kept_seed_by_class": Counter(st["cls_of"].get(e, "?") for e in kept).most_common(20),
        "pin_evidence": pin_ev,
        "latest_dangling_ids_created": lat_dangling,
        "structural_ok": bool(struct_ok["ok"]),
        "validator": val, "census": cen,
        "seconds": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUTDIR, f"{name}.json"), "w") as fh:
        json.dump(rep, fh, indent=1, default=lambda o: sorted(o) if isinstance(o, set) else str(o))
    ok = struct_ok["ok"] and val.get("ok") and val.get("errors") == 0
    log(f"[{name}] {desc[:110]}...\n      edited {rep['neutralisation']['referrer_elements_edited']} "
        f"referrers ({dict(rep['neutralisation']['edited_by_class'][:5])}); seed {len(seed):,} "
        f"-> deleted {len(delete):,} (pinned {len(kept)}); {cen['elements']:,} left, "
        f"{cen['file_size']:,} B; structural={struct_ok['ok']} validator_ok={val.get('ok')} "
        f"(errors {val.get('errors')}); Latest-dangling +{lat_dangling}; {rep['seconds']}s")
    if not ok:
        rep["FAILED_SELF_CHECK"] = True
        log(f"[{name}] *** SELF-CHECK FAILED: {val.get('error_messages')} "
            f"{struct_ok if not struct_ok['ok'] else ''}")
        with open(os.path.join(OUTDIR, f"{name}.json"), "w") as fh:
            json.dump(rep, fh, indent=1, default=str)
    return rep


def build_pairs(pairs: List[str], st5: Optional[dict] = None) -> Dict[str, dict]:
    """Round-2 helper: build a rung per 'G2_viewmaps+G3_schedule' pair (the
    INTERACTION probes, used only if K1a and EVERY single-group rung PASS).
    Each is R5 + the two groups' edits + maxgc -- named K1p_<a>_<b>.rvt."""
    st5 = st5 or RR.build_state_v2(R5)
    reports: Dict[str, dict] = {}
    for pair in pairs:
        gs = [g.strip() for g in pair.split("+")]
        for g in gs:
            if g not in GROUPS:
                raise SystemExit(f"unknown group {g!r}; choose from {list(GROUPS)}")
        allowed: Set[str] = set().union(*(GROUPS[g]["referrers"] for g in gs))
        short = lambda g: g.split("_", 1)[0]                      # noqa: E731
        name = "K1p_" + "_".join(short(g) for g in gs)
        reports[name] = _rung(
            name, allowed=allowed, st5=st5,
            desc=(f"INTERACTION PROBE: R5 with the edit classes of {gs} applied "
                  f"together, then the maximal-GC of the placed model -- the "
                  f"deletions unlocked ONLY when both groups un-pin them."),
            tests=(f"Whether the combination {gs} (each innocent alone) kills "
                   f"-- i.e. the killer lives in their interaction-unlocked "
                   f"deletion set."),
            pass_means="This pair is innocent; test the next pair by interaction volume.",
            fail_means=(f"The killer is a deletion unlocked only by {gs} together; "
                        f"round 3 bisects that interaction set (the LAW then "
                        f"names a NEVER-REMOVE-WITHOUT-ITS-REFERRER content class)."))
    return reports


#: contingency HALVES of K1's removal set (round 2, used only if K1a AND every
#: single-group rung PASS => the killer is an interaction-unlocked deletion).
#: The classes of K1's 2,117 actually-deleted elements, split ~50/50:
HALF_STRUCTURAL = {
    "SWall", "Floor", "ContFooting", "DPart", "PartMaker", "Rebar",
    "RebarInSystem", "RebarSystem", "JoistSystem", "StairsElement",
    "StairsRun", "StairsPathElement", "StairsSupport", "AnalyticalMember",
    "AnalyticalPanel", "LineLoad", "AreaLoad", "PointLoad",
    "BoundaryConditions", "Hub", "HubsTracker", "GCSTracker",
    "RegenSplitterElem", "PostedWarningElem", "MassLevelData", "FormElem",
    "VarSketch", "SketchPlane", "NonPlanarSketch", "ZoneElement",
}


def build_halves(st5: Optional[dict] = None) -> Dict[str, dict]:
    """ROUND-2 CONTINGENCY (upload ONLY if CTRL PASSES, K1a PASSES and EVERY
    single-group rung PASSES): the charter's 'R5 minus HALVES of K1's removal
    set'.  Both files carry ALL of K1's persistent survivor edits (== K1's 23
    edited survivors); H1 then maxgc-collects only the STRUCTURAL half of
    K1's actual deletion set (walls/floors/rebar/analytical/stairs/hubs/
    sketches), H2 only the CONTENT half (family instances/rooms/loads/ref-
    points/curves/dims/images).  Elements of the other half PIN what they
    still reference, so each half's deletion is dangling-free (the collectable
    part of that half).  A FAILing half is bisected again next round."""
    st5 = st5 or RR.build_state_v2(R5)
    targets = _placed_targets(st5)
    step = os.path.join(OUTDIR, ".halves_step1.rvt")
    nrep = neutralise_grouped(st5, targets, step, allowed=set(ALL_REFERRER_CLASSES),
                              name="K1halves")
    st = RR.build_state_v2(step)
    seed_full = {e for e in targets if e in st["host"]}
    seed_full |= GT._ids_of_classes(st, GT.K1_RESIDUE_SWEEP)
    seed_full = RR._protect_history(st, GT._own_fixpoint(st, seed_full))
    D, _kept, _ev = RR.maxgc(st, seed_full)         # == K1's exact 2,117
    reports: Dict[str, dict] = {}
    for name, pick in (("K1h1_structural", HALF_STRUCTURAL),
                       ("K1h2_content", None)):
        half = {e for e in D if (st["cls_of"].get(e) in HALF_STRUCTURAL) == (pick is not None)}
        t0 = time.time()
        delete, kept, ev = RR.maxgc(st, half)
        out = os.path.join(OUTDIR, f"{name}.rvt")
        delete_elements(step, out, delete)
        struct_ok = verify_reduced(out, delete)
        val = GT.validate(out)
        cen = GT.census(out)
        rep = {
            "rung": name, "kind": "modify(all persistent groups)+gc-delete(HALF of K1's removal set)",
            "base": _relp(R5), "out": _relp(out), "round": "2 (contingency)",
            "description": (
                f"ALL of K1's persistent survivor edits (its 23 edited survivors) "
                f"+ maxgc-deletion of ONLY the {'STRUCTURAL' if pick else 'CONTENT'} "
                f"half of K1's actual 2,117-element removal set "
                f"({len(half)} candidates, {len(delete)} collectable dangling-free)."),
            "tests": (f"Whether the fatal element lives in the {'structural' if pick else 'content'} "
                      f"half of K1's removal set (used only if K1a and EVERY single-group "
                      f"rung PASSED => the killer is an interaction-unlocked DELETION)."),
            "if_PASS": "The killer is in the OTHER half (or needs both halves gone -- read the sibling).",
            "if_FAIL": "The killer is in THIS half -- bisect it again by class next round.",
            "half_candidates": len(half), "deleted": len(delete), "kept_pinned": len(kept),
            "deleted_by_class": Counter(st["cls_of"].get(e, "?") for e in delete).most_common(60),
            "pin_evidence": ev, "structural_ok": bool(struct_ok["ok"]),
            "validator": val, "census": cen, "seconds": round(time.time() - t0, 1),
            "neutralisation": {"referrer_elements_edited": nrep["referrer_elements_edited"],
                               "edited_by_class": nrep["edited_by_class"]},
        }
        with open(os.path.join(OUTDIR, f"{name}.json"), "w") as fh:
            json.dump(rep, fh, indent=1, default=lambda o: sorted(o) if isinstance(o, set) else str(o))
        reports[name] = rep
        log(f"[{name}] half {len(half)} -> deleted {len(delete)}; {cen['elements']:,} left; "
            f"validator_ok={val.get('ok')} (errors {val.get('errors')})")
    try:
        os.remove(step)
    except OSError:
        pass
    return reports


def build_ladder(only: Optional[Set[str]] = None) -> Dict[str, dict]:
    reports: Dict[str, dict] = {}
    st5 = RR.build_state_v2(R5)

    def want(n: str) -> bool:
        return only is None or n in only

    # -- the batch's CERTIFIED CONTROL (hard law): byte-identical R5 copy
    ctrl = os.path.join(OUTDIR, "CTRL_R5_recheck.rvt")
    if want("CTRL_R5_recheck"):
        shutil.copyfile(R5, ctrl)
        reports["CTRL_R5_recheck"] = {
            "rung": "CTRL_R5_recheck", "kind": "control (byte-identical copy)",
            "base": _relp(R5), "out": _relp(ctrl),
            "md5": hashlib.md5(open(ctrl, "rb").read()).hexdigest(),
            "same_md5_as_R5": hashlib.md5(open(ctrl, "rb").read()).hexdigest()
                              == hashlib.md5(open(R5, "rb").read()).hexdigest(),
            "description": ("Byte-identical copy of the certified R5.rvt -- the "
                            "batch's oracle-health / base-certification "
                            "control (the standing-controls hard law: every "
                            "batch uploads >= 1 certified control)."),
            "tests": "Nothing new -- confirms the oracle is healthy and R5 (the ladder's base) still passes.",
            "if_PASS": "Oracle healthy; every rung's verdict is real.",
            "if_FAIL": "ORACLE / environment fault -- discard every verdict of this batch and retry.",
        }
        log(f"[CTRL_R5_recheck] byte-identical copy of R5 -> {_relp(ctrl)}")

    common = dict(st5=st5)
    if want("K1a_editfree"):
        reports["K1a_editfree"] = _rung(
            "K1a_editfree", allowed=set(), **common,
            desc=("R5 (viewer PASS) minus the maximal-GC-collectable placed model "
                  "with ZERO survivor edits (K1's neutralise pre-pass NOT run).  "
                  "Every survivor is BYTE-IDENTICAL to R5; the model elements that "
                  "unedited survivors still reference (columns hidden in the 3D "
                  "views, the schedule's columns, sheet title blocks, the area "
                  "room, the in-place family, the stairs, the rendering image, "
                  "the elevation-arrow's wall) are PINNED and survive.  Every "
                  "deletion here is one the certified R9/R6 also made."),
            tests=("K1 with its ENTIRE novelty (the 23 survivor edits) removed.  "
                   "Is K1's DELETION SET, in the views-present context, fatal on "
                   "its own?  This is the LADDER BASE."),
            pass_means=("The deletion set is innocent (as the certified cross-"
                        "reference predicts); K1's defect is in the survivor "
                        "EDITS => the K1b..K1f single-group rungs name it."),
            fail_means=("The deletion set itself is fatal in the views-present "
                        "context although R9 made the same deletions without "
                        "views => an untouched surviving VIEW cannot render an "
                        "empty model / a class-context interaction; next "
                        "ladder bisects the deletion set by class group."))
    for gname in GROUP_ORDER:
        rung = "K1" + {"G1_sheets": "b_sheets", "G2_viewmaps": "c_viewmaps",
                       "G3_schedule": "d_schedule", "G4_orphaning": "e_orphaning",
                       "G5_topology": "f_topology"}[gname]
        if not want(rung):
            continue
        spec = GROUPS[gname]
        reports[rung] = _rung(
            rung, allowed=set(spec["referrers"]), **common,
            desc=(f"R5 with ONLY the {gname} neutralisation edits applied "
                  f"(referrer classes {sorted(spec['referrers'])}), then the "
                  f"same maximal-GC of the placed model as K1: = K1a_editfree "
                  f"+ this group's edits + the extra deletions those edits "
                  f"unlock.  {spec['what']}"),
            tests=f"Whether the {gname} edit class (and only it) breaks a PASSING file.",
            pass_means=f"{gname} is innocent -- the killer is another group.",
            fail_means=(f"{gname} IS a fatal edit class: the LAW must forbid it "
                        f"(delete these referrers WITH their content, or keep "
                        f"the content, instead of neutralising).  If several "
                        f"single-group rungs fail, several independent laws."))
    if want("K1z_persistent"):
        reports["K1z_persistent"] = _rung(
            "K1z_persistent", allowed=set(ALL_REFERRER_CLASSES), **common,
            desc=("R5 with ALL FIVE persistent edit groups applied (the 12 "
                  "referrer classes G1..G5) but NOT the transient G6 class "
                  "(CurveElem / LinearDimString / Alignment pin-cutting), then "
                  "the maximal-GC of the placed model.  = K1 with ONLY the G6 "
                  "mechanism reverted: every surviving-edited element of K1 is "
                  "present here in K1's exact state; the sketch / dimension / "
                  "model chains that only G6's pin-cutting unlocked SURVIVE.  "
                  "The top-level split of K1's novelty: {no edits: K1a} < "
                  "{persistent edits: K1z} < {+ transient pin-cutting: K1}."),
            tests=("With every surviving edit K1 carries but WITHOUT the ~800 "
                   "deletions the transient CurveElem/dim/alignment edits "
                   "unlock -- does the file load?"),
            pass_means=("(K1 FAILS, K1z PASSES) => the killer is the G6 mechanism: "
                        "nulling m_sketchPlaneId / m_miscId / m_assocId / witness "
                        "refs of PINNED curves/dims, releasing whole sketch and "
                        "constraint chains -- next round splits CurveElem vs "
                        "LinearDimString vs Alignment.  If instead a single "
                        "K1b..K1f rung FAILED, that group is named directly and "
                        "K1z is expected to FAIL with it."),
            fail_means=("The killer is within the persistent groups G1..G5 -- "
                        "read the single-group rungs (exactly one should FAIL; "
                        "if none does, the killer is an INTERACTION of two "
                        "groups: next round pairs them)."))
    if want("K1v_delete_referrers"):
        # THE CONSTRUCTIVE FIX CANDIDATE: the certified rule (maxgc DELETE, zero
        # survivor edits) applied to K1's goal -- delete the 23 persistent
        # referrers (5 3D views + section + rendering + graphical column
        # schedule + 8 sheets + the in-place family's symbol/surrogates + the
        # stairs riser symbol + the room/area topologies + the elevation
        # arrow) TOGETHER WITH the placed model they reference, as Revit's
        # own delete cascade and the R6/R9 ladder do.  Whatever is still pinned
        # from outside (a marker owning the arrow, a viewport, ...) survives
        # UNEDITED.  Every element is either byte-identical to R5 or GONE.
        st_k = RR.build_state_v2(K1)                     # K1's 23 modified survivors
        k1doc, r5doc = st_k["doc"], st5["doc"]
        d = element_diff(r5doc, k1doc)
        referrers23 = {e for e in d["modified"] if e in st5["host"]}
        extra = GT._own_fixpoint(st5, set(referrers23))

        def _seed_with_referrers(st: dict, targets: Set[int]) -> Set[int]:
            s = {e for e in targets if e in st["host"]}
            s |= {e for e in extra if e in st["host"]}
            s |= GT._ids_of_classes(st, GT.K1_RESIDUE_SWEEP)
            return GT._own_fixpoint(st, s)
        reports["K1v_delete_referrers"] = _rung(
            "K1v_delete_referrers", allowed=set(), **common,
            seed_fn=_seed_with_referrers,
            desc=("THE DELETE-ONLY MAXIMUM (the certified rule, no neutralise "
                  "pre-pass): R5 minus the placed model AND minus K1's 23 "
                  "edited referrers, seeded for deletion WITH the content they "
                  "reference (+ ownership children) -- Revit's own delete "
                  "cascade / the R6-R9 pattern.  ZERO survivor edits: every "
                  "survivor is byte-identical to R5.  Its RESIDUE is the "
                  "finding: the model-viewing 3D/section views are themselves "
                  "PINNED by viewports on the surviving unedited sheets and the "
                  "browser/project constellation, so their state maps keep "
                  "pinning the model -- 'the empty project that KEEPS the "
                  "sample's model-referencing view constellation' is NOT "
                  "reachable by deletion (R9's certified shape deletes those "
                  "views with the model)."),
            tests=("The best model reduction achievable with ZERO edits when "
                   "referrers are deleted rather than neutralised; a zero-edit "
                   "sibling of K1a with the referrer layer also gone."),
            pass_means=("Delete-only stays certified even with the referrer layer "
                        "removed; the CORRECTED K1 recipe is then mechanical: for "
                        "every edit group whose single rung FAILED, DELETE that "
                        "group's referrers with their content instead of "
                        "neutralising them; keep the groups whose rungs PASSED "
                        "(their edits are proven reader-legal)."),
            fail_means=("A zero-edit sibling of K1a fails => the extra referrer "
                        "deletions (a 3D view / the schedule / the surrogates as "
                        "a UNIT) are the culprit -- compare its deletion delta "
                        "against K1a's (both are R5-derived, differing only in "
                        "the referrer layer)."))
    if want("K1_suspect"):
        # ONE hypothesis, ONE file: the in-place family trio only (the stairs
        # riser symbol -- also a G4 referrer -- is left completely untouched
        # here; K1e_orphaning carries the whole group in K1's full context).
        reports["K1_suspect"] = _rung(
            "K1_suspect", allowed={"FamilySymbol", "FamilySurrogate", "FamSymSurrogate"},
            restrict_seed_to_group=True, **common,
            desc=("THE MINIMAL SINGLE-SUSPECT PROBE: R5 (PASS) minus ONLY the "
                  "in-place Family 876493 ('building option', an in-place "
                  "massing family) + its instance 876571 + its sketches / "
                  "curves / ref points, with its three referrers neutralised "
                  "EXACTLY as K1 did -> the registry-indexed category-DEFAULT "
                  "FamilySymbol 876569 ORPHANED (m_familyId -> -1, "
                  "m_ownerInstanceId -> -1), FamilySurrogate 876494 "
                  "(m_elemId -> -1), FamSymSurrogate 876570 (regenOnly "
                  "pruned) -- byte-identical to K1's records for these three.  "
                  "The whole rest of the model, the stairs, every view and "
                  "every catalog stay byte-identical to R5 (delta = 83 deleted "
                  "elements + 3 edited).  One hypothesis, one file."),
            tests=("Does orphaning a live, registry-indexed FamilySymbol (its "
                   "family DELETED, family pointer -1) crash the extractor, "
                   "with nothing else changed?"),
            pass_means=("G4 alone (at this minimal scope) is NOT sufficient to "
                        "kill; read K1e_orphaning (G4 in the full-deletion "
                        "context) and the other single-group rungs."),
            fail_means=("PROVEN: orphaning a type object (nulling m_familyId / "
                        "m_hostId / a surrogate's m_elemId while KEEPING the "
                        "referrer) is FATAL.  LAW: family objects are removed "
                        "TOGETHER (Family + FamilySymbol + surrogates + m_famId "
                        "children + instances) or not at all; never neutralise "
                        "a Symbol->Family / Surrogate->Family / TriserSymbol->"
                        "host link."))
    return reports


# ===========================================================================
# 4. THE MANIFEST
# ===========================================================================

PROBE_ORDER = ["CTRL_R5_recheck", "K1a_editfree", "K1_suspect",
               "K1e_orphaning", "K1d_schedule", "K1f_topology",
               "K1c_viewmaps", "K1b_sheets", "K1v_delete_referrers"]
# (K1z_persistent -- all 12 persistent classes, no G6 -- was BUILT and found to
#  be record-for-record identical to K1 itself: the transient G6 pin-cutting is
#  REDUNDANT.  It is therefore NOT a probe (it would only re-test K1); the
#  equivalence is recorded in autopsy_evidence.json / the report.)


# ===========================================================================
# 5. IN-MEMORY UNLOCK SIMULATOR (which deletions each group SET unlocks)
# ===========================================================================

def unlock_table(max_order: int = 2) -> dict:
    """Simulate 'neutralise the referrer classes of group-set S, then maxgc'
    on the R5 reference graph WITHOUT writing files: the deletion set of a
    group-set = maxgc over the graph with the (S-class survivor -> placed
    target) edges removed.  Validated against the REAL rung reports on disk
    (their deletion counts), then used to tabulate every single / pair
    (/ triple) unlock -- the interaction structure that decides round 2 if
    every single-group rung PASSES."""
    import itertools
    st5 = RR.build_state_v2(R5)
    targets = _placed_targets(st5)
    seed = {e for e in targets if e in st5["host"]}
    seed |= GT._ids_of_classes(st5, GT.K1_RESIDUE_SWEEP)
    seed = GT._own_fixpoint(st5, seed)
    seed = RR._protect_history(st5, seed)
    cls_of, graph = st5["cls_of"], st5["graph"]

    def sim(allowed: Set[str]) -> Set[int]:
        # cut edges from allowed-class NON-seed survivors into the placed targets
        cut_graph = {}
        for e, outs in graph.items():
            if e not in seed and cls_of.get(e) in allowed:
                outs2 = {t for t in outs if t not in targets}
                if len(outs2) != len(outs):
                    cut_graph[e] = outs2
        g2 = dict(graph)
        g2.update(cut_graph)
        refs: Dict[int, Set[int]] = defaultdict(set)
        for e, outs in g2.items():
            for t in outs:
                refs[t].add(e)
        st2 = {"graph": g2, "referrers": refs, "cls_of": cls_of}
        delete, _kept, _ev = RR.maxgc(st2, seed)
        return delete

    gnames = list(GROUP_ORDER)
    results: dict = {"validation": {}, "singles": {}, "pairs": {}, "all5": None,
                     "editfree": None}
    base_del = sim(set())
    results["editfree"] = len(base_del)
    single_del: Dict[str, Set[int]] = {}
    for g in gnames:
        d = sim(set(GROUPS[g]["referrers"]))
        single_del[g] = d
        results["singles"][g] = {"deleted": len(d), "unlocked_vs_editfree": len(d - base_del)}
    all5 = sim(set(ALL_REFERRER_CLASSES))
    results["all5"] = len(all5)
    union_singles: Set[int] = set().union(*single_del.values())
    results["union_of_singles"] = len(union_singles)
    results["interaction_only"] = len(all5 - union_singles)
    # validation against the real rungs on disk
    real = {"K1a_editfree": ("editfree", None), "K1b_sheets": ("singles", "G1_sheets"),
            "K1c_viewmaps": ("singles", "G2_viewmaps"), "K1d_schedule": ("singles", "G3_schedule"),
            "K1e_orphaning": ("singles", "G4_orphaning"), "K1f_topology": ("singles", "G5_topology"),
            "K1z_persistent": ("all5", None)}
    for rung, (kind, g) in real.items():
        rep = _load(rung)
        if not rep:
            continue
        simd = (results["editfree"] if kind == "editfree" else
                results["all5"] if kind == "all5" else results["singles"][g]["deleted"])
        results["validation"][rung] = {"real_deleted": rep.get("deleted"),
                                       "simulated_deleted": simd,
                                       "match": rep.get("deleted") == simd}
    if max_order >= 2:
        for a, b in itertools.combinations(gnames, 2):
            d = sim(set(GROUPS[a]["referrers"]) | set(GROUPS[b]["referrers"]))
            extra = len(d - single_del[a] - single_del[b] - base_del)
            results["pairs"][f"{a}+{b}"] = {"deleted": len(d),
                                              "interaction_unlock": extra}
    log(f"[unlock] editfree {results['editfree']}, singles "
        f"{ {g: v['deleted'] for g, v in results['singles'].items()} }, "
        f"all5 {results['all5']}, union-of-singles {results['union_of_singles']}, "
        f"interaction-only {results['interaction_only']}")
    log(f"[unlock] simulator vs real rungs: {results['validation']}")
    return results


def verify_recomposition() -> dict:
    """RECOMPOSITION PROOF: rebuild 'K1' from R5 with ALL referrer classes
    (persistent G1..G5 + transient G6) neutralised, then the same maximal-GC,
    and compare against the real K1.rvt: identical deleted-id set and
    identical surviving records => the six edit classes account for K1's
    ENTIRE difference from R5 (the ladder is complete).  The file is a
    diagnostic (not for upload) and is deleted afterwards."""
    st5 = RR.build_state_v2(R5)
    rep = _rung(
        "K1_recomposed", allowed=set(ALL_REFERRER_CLASSES) | TRANSIENT_REFERRERS, st5=st5,
        desc="RECOMPOSITION CHECK: R5 with all six edit classes neutralised + maxgc (should == K1)",
        tests="internal", pass_means="n/a", fail_means="n/a")
    out = os.path.join(OUTDIR, "K1_recomposed.rvt")
    a = Document.from_file(out)
    b = Document.from_file(K1)
    d = element_diff(a, b)
    res = {
        "recomposed_deleted": rep["deleted"],
        "ids_only_in_recomposed": len(d["removed"]),   # deleted by K1, kept here
        "ids_only_in_K1": len(d["added"]),             # deleted here, kept by K1
        "records_differing": len(d["modified"]),
        "identical": (not d["removed"] and not d["added"] and not d["modified"]),
    }
    if d["removed"]:
        r5 = Document.from_file(R5)
        res["only_in_recomposed_by_class"] = Counter(
            r5.class_of(e) for e in d["removed"]).most_common(20)
    if d["added"]:
        r5 = Document.from_file(R5)
        res["only_in_K1_by_class"] = Counter(
            r5.class_of(e) for e in d["added"]).most_common(20)
    if d["modified"]:
        res["records_differing_by_class"] = Counter(
            b.class_of(e) for e in d["modified"]).most_common(20)
    log(f"[recomposition] recomposed==K1: {res['identical']} "
        f"(kept-here-but-deleted-by-K1 {res['ids_only_in_recomposed']}, "
        f"deleted-here-but-kept-by-K1 {res['ids_only_in_K1']}, "
        f"records differing {res['records_differing']})")
    for f in ("K1_recomposed.rvt", "K1_recomposed.json"):
        try:
            os.remove(os.path.join(OUTDIR, f))
        except OSError:
            pass
    return res


def write_manifest(reports: Dict[str, dict]) -> str:
    probes = []
    for i, name in enumerate(PROBE_ORDER, 1):
        p = os.path.join(OUTDIR, f"{name}.rvt")
        if not os.path.exists(p):
            continue
        r = reports.get(name) or _load(name) or {}
        probes.append({
            "order": i, "file": _relp(p), "rung": name,
            "base": _relp(R5),
            "base_certification": ("R5.rvt is VIEWER-CERTIFIED (docs/coverage/"
                                   "viewer-certified.json: 'Latest-DANGLING "
                                   "variant accepted'); every rung of this "
                                   "ladder is derived from R5 in ONE step "
                                   "(no rung stacks on an untested rung)."),
            "kind": r.get("kind"),
            "the_one_thing_tested": r.get("tests"),
            "vs_passing_sibling": (
                "R5.rvt (identical file)" if name == "CTRL_R5_recheck" else
                "R5.rvt -- differs only by the maximal-GC deletion of the "
                "placed model, ZERO survivor edits (every deletion also in "
                "certified R9/R6)" if name == "K1a_editfree" else
                "K1a_editfree.rvt -- ALSO deletes the 23 referrers (with "
                "the extra content they release); still ZERO edits"
                if name == "K1v_delete_referrers" else
                "K1a_editfree.rvt -- differs only by ONE neutralisation "
                "edit class (+ the deletions those edits unlock)"),
            "if_PASS": r.get("if_PASS"), "if_FAIL": r.get("if_FAIL"),
            "elements": (r.get("census") or {}).get("elements"),
            "deleted": r.get("deleted"),
            "referrers_edited": (r.get("neutralisation") or {}).get("referrer_elements_edited"),
            "validator": ({"ok": True, "errors": 0, "note": "byte-identical copy of validated R5"}
                          if name == "CTRL_R5_recheck" else
                          {k: (r.get("validator") or {}).get(k) for k in ("ok", "errors", "warnings")}),
            "structural_ok": r.get("structural_ok", True),
        })
    contingency = {
        "note": ("Round-2 probes are built ON DEMAND from R5 by this tool "
                 "(no untested base): '--pair Gx+Gy' for a group-pair rung. "
                 "Removal-set 'halves' were built and DISCARDED: the placed "
                 "model is ONE connected pin-component (a half seeds only "
                 "61-205 collectable deletions), so K1's removal set cannot "
                 "be halved dangling-free -- the constructive K1v probe (delete "
                 "referrers WITH content) replaces them."),
        "if_K1a_PASS_and_all_singles_PASS": (
            "The killer is an interaction of >= 2 edit groups (pairwise "
            "unlocks: G3+G2 = 28, G4+G2 = 18; the remaining ~755 need >= 3 groups "
            "-- see autopsy_evidence.json 'unlock_table'). Build "
            "--pair G3_schedule+G2_viewmaps,G4_orphaning+G2_viewmaps and the "
            "triple G2+G3+G4; K1v's verdict decides whether to bypass the whole "
            "question by deleting instead of neutralising."),
    }
    manifest = {
        "purpose": ("THE K1 AUTOPSY BISECTION LADDER.  K1.rvt (R5 minus the "
                    "placed model, via a NEUTRALISE-then-maxgc build) FAILS the "
                    "Autodesk reader with the CRASH signature (extractor exit "
                    "-1073741831, no Revit-DocumentCorruption line) while its "
                    "parent R5 PASSES.  The autopsy (docs/writer/k1-autopsy.md) "
                    "closes the accounting: 2,115 of K1's 2,117 deletions are "
                    "also made by the certified R9/R6, every global stream is "
                    "byte-identical to R5's, and K1's ENTIRE novelty is 23 "
                    "surviving elements EDITED by the neutraliser pre-pass "
                    "(22 in states no viewer-PASSED file carries; 1 byte-"
                    "vindicated) plus ONE deleted room every passing file "
                    "keeps.  This ladder rebuilds K1 from certified R5 one "
                    "edit-class at a time."),
        "base_certification_law": ("Every rung derives from R5.rvt (viewer-"
                                   "PASSED) in ONE step; CTRL_R5_recheck (a "
                                   "byte-identical R5 copy) rides in the same "
                                   "batch as the standing certified control.  "
                                   "No probe is built on an untested base."),
        "death_signatures": {"CRASH": "'Design is empty' + TranslationWorker-InternalFailure exit -1073741831, NO corruption line (K1, X0k, XR0)",
                             "AUDIT": "'Revit-DocumentCorruption / The file is corrupt' + exit -1073742517 (K1's heavier-modified children)"},
        "ordered_by": "information value; upload ALL in ONE batch (they are mutually independent siblings of R5)",
        "batch_gate": ("Stage the upload through tools/probe_batch.py (genesis-discipline "
                       "stream): every probe below declares its base = experiments/genesis/R5.rvt, "
                       "which IS in viewer-certified.json 'certified'; CTRL_R5_recheck is the "
                       "batch's byte-identical certified control."),
        "probes": probes,
        "round_2_contingency": contingency,
        "reading_the_results": {
            "CTRL FAILS": "Oracle sick -- discard the batch, retry.",
            "K1a_editfree PASS + exactly ONE K1x FAIL":
                "That group's edit class is THE law-breaking mechanism; its "
                "'if_FAIL' text is the law.  (K1_suspect PASS/FAIL then says "
                "whether the minimal G4 scope alone suffices.)",
            "K1a_editfree PASS + several K1x FAIL":
                "Several independent fatal edit classes; each names its own law.",
            "K1a_editfree PASS + ALL K1x PASS":
                "The killer is an INTERACTION of two edit groups (an element "
                "released only when two groups both un-pin it); next round "
                "pairs the groups (10 combinations, pre-computable).",
            "K1a_editfree FAIL":
                "The deletion set itself is fatal WITH VIEWS PRESENT although R9 "
                "made the same deletions WITHOUT views: an untouched surviving "
                "view / class cannot survive an emptied model.  Next round "
                "bisects the DELETION set by class group (halves of "
                "K1_PLACED) on the R5 base -- pre-computable by this tool.",
            "K1_suspect FAIL": "Orphaning a live type (family -> -1) is fatal at ANY scope; the strongest single law.",
        },
        "expected_by_prior": {"CTRL_R5_recheck": "PASS", "K1b_sheets": "PASS (byte-vindicated by K3/K4)",
                              "K1a_editfree": "PASS (2,115/2,117 deletions R9-vindicated)",
                              "top_suspects": ["K1e_orphaning / K1_suspect (registry-indexed orphan symbol)",
                                               "K1d_schedule (dropped grid-intersection structs)",
                                               "K1f_topology (room every passing file keeps + arrow attached to nothing)"]},
    }
    path = os.path.join(OUTDIR, "probes.json")
    with open(path, "w") as fh:
        json.dump(manifest, fh, indent=1, default=str)
    log(f"[manifest] {_relp(path)}: {len(probes)} probes, in upload order:")
    for p in probes:
        log(f"    {p['order']}. {p['rung']:16} elements={p['elements']} "
            f"validator={p['validator']}")
    return path


def _load(name: str) -> Optional[dict]:
    p = os.path.join(OUTDIR, f"{name}.json")
    if os.path.exists(p):
        with open(p) as fh:
            return json.load(fh)
    return None


# ===========================================================================
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--analyze", action="store_true", help="run the diff/cross-reference analysis only")
    ap.add_argument("--build", action="store_true", help="build the bisection ladder only")
    ap.add_argument("--only", default=None,
                    help="comma list of rungs to build (CTRL_R5_recheck,K1a_editfree,K1z_persistent,"
                         "K1_suspect,K1b_sheets,K1c_viewmaps,K1d_schedule,K1e_orphaning,K1f_topology)")
    ap.add_argument("--recompose", action="store_true",
                    help="run the recomposition proof (all six edit classes must reproduce K1 exactly)")
    ap.add_argument("--unlock", action="store_true",
                    help="compute the in-memory single/pair unlock (interaction) table")
    ap.add_argument("--pair", default=None,
                    help="ROUND-2 ONLY: comma list of group pairs to build, e.g. "
                         "'G2_viewmaps+G3_schedule,G2_viewmaps+G4_orphaning'")
    ap.add_argument("--halves", action="store_true",
                    help="build the round-2 CONTINGENCY halves of K1's removal set (K1h1/K1h2)")
    a = ap.parse_args(argv)
    if a.halves:
        build_halves()
        write_manifest({})
        return 0
    explicit = a.analyze or a.build or a.recompose or a.unlock or a.pair
    do_a = a.analyze or not explicit
    do_b = a.build or not explicit
    do_r = a.recompose or not explicit
    do_u = a.unlock or not explicit
    if do_a:
        analyze(write=True)
    if do_r or do_u:
        try:
            ev = json.load(open(EVIDENCE_JSON)) if os.path.exists(EVIDENCE_JSON) else {}
        except Exception:
            ev = {}
        if do_r:
            ev["recomposition_proof"] = verify_recomposition()
        if do_u:
            ev["unlock_table"] = unlock_table()
        with open(EVIDENCE_JSON, "w") as fh:
            json.dump(ev, fh, indent=1, default=str)
    if a.pair:
        reps = build_pairs([p for p in a.pair.split(",") if p.strip()])
        for name, r in reps.items():
            log(f"  built {name}: deleted {r['deleted']}, validator ok={r['validator'].get('ok')}")
        return 0
    if do_b:
        only = set(a.only.split(",")) if a.only else None
        reports = build_ladder(only)
        write_manifest(reports)
        # cleanup step intermediates
        for f in os.listdir(OUTDIR):
            if f.startswith(".") and f.endswith("_step1.rvt"):
                try:
                    os.remove(os.path.join(OUTDIR, f))
                except OSError:
                    pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
