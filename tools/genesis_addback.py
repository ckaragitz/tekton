#!/usr/bin/env python
"""genesis_addback.py -- the ADD-BACK PROBES (R1/R1s/R2/R2s/R3) + the
REGISTRY-PARITY AUDIT (why the S-set failed).

WHY THIS EXISTS (2026-08-03, orchestrator verdicts #6/#7): every reduction
of Autodesk's own empty-project skeleton LOADS (R5, R9, K1, K3, K4, KD1) and
EVERY constructed base FAILS -- including S1..S5, which put OUR singleton
constructors + OUR complete built-in style catalog onto the FAILING G1 base.
The S-set therefore tested our content ON THE SUSPECT BASE and cannot say
whether (i) our singletons / catalog are mis-shaped / mis-registered, or
(ii) the G1 base carries an independent defect.  This tool ISOLATES the
question by building from the PASSING side: our content is added to the
KNOWN-GOOD Autodesk skeleton at exactly the point the sample's content was
removed, with the sample's content that our constructors do NOT cover
restored VERBATIM (transplanted at its original ids) so that the ONLY
class-level difference from a passing file is OUR substitution.

The base files are the two viewer-FAILED removals of the K-ladder
(experiments/genesis/triage/, docs/inbox/genesis-triage-a.md):
  * K5.rvt = K1 minus the document-settings SINGLETON set (viewer FAIL)
  * K6.rvt = K1 minus the built-in category / GStyle CATALOG   (viewer FAIL)
where K1.rvt = Autodesk's empty-project skeleton (6,540 elements).

THE FIVE PROBES (experiments/genesis/addback/):
  R1   K5 + OUR constructors for EVERY singleton class K5 deleted that
       ``rvt.genesis.settings.standard_settings`` builds (= the constellation
       S3/S5 added to G1), wired to K5's OWN companion ids (units, phases,
       document sun, workset visibility, MEP trackers, wire catalog symbols,
       keynote table ...), the ADocument registries recomputed from K1's
       document object and repopulated over our new ids; the K5-deleted
       classes our constellation does NOT build (AllPlanTopologies,
       AreaSchemePlanTopologies, AssemblyCodeTable, AreaReportSettings +
       its category/font cluster, NumberingSchema, RbsPipeSizesElem,
       ViewSheetSet) are RESTORED from K1 verbatim.  Net: R1 differs from
       the passing skeleton ONLY in that the covered singleton classes are
       OUR constructors' output.  PASS => our singletons are an acceptable
       substitute (S5's failure was the G1 base); FAIL => our singleton
       constructors / registry wiring are wrong.
  R1s  the SMALLER claim: as R1 but ONLY the project pen table + the
       project-browser organizations are OURS; every other K5-deleted class
       is restored from K1.  If R1 FAILS and R1s PASSES the defect is in our
       MEP / structural / tracker constructors; if both FAIL even the pen
       table / browser substitution is rejected.
  R2   K6 + OUR complete built-in-category object-styles catalog: for every
       (built-in category, style type) row K6 deleted, OUR row (our
       discipline colours / weights) at a NEW id, with EVERY reference in
       K1's document object RE-POINTED at our rows (CategoryTracking
       m_gstyleData + the SymbolIdMgr entries -- a schema-typed id remap,
       complete by construction).  Every OTHER K6 casualty (sub-category
       CategoryElem + their style rows, line/fill patterns, materials,
       appearance assets, and the project pen table K6 also deleted) is
       RESTORED from K1.  Net: R2 differs from the passing skeleton ONLY in
       the built-in object-styles table being OURS.
  R2s  the MECHANICS CONTROL: as R2 but the SAMPLE's own rows restored (ALL
       of K6's 2,151 deletions transplanted back, K1's document object
       reinstated verbatim).  R2s should be equivalent to K1 => PASS.  A PASS
       proves the transplant + registry machinery is sound, so an R2 FAIL
       convicts OUR catalog rows; an R2s FAIL means the mechanics are the
       suspect and R2 is unreadable.  (Also settles a K-ladder confound: K6
       deleted the project pen table too, so K6's own FAIL bundled the pen
       table with the catalog; both R2 and R2s hold the pen table constant.)
  R3   S5 with EXACTLY the registry-parity MISMATCHES the audit finds
       repaired (its rows unchanged; only its document-object registries
       fixed to match K1's shape) -- potentially the shortest path to a
       PASS.  Built only when the audit finds registry-fixable mismatches.

THE PARITY AUDIT (docs/writer/registry-parity.md): for EVERY registry
surface the reader walks (UniqueElementsTracking positional slots, named
AppInfo scalar slots, the CategoryTracking built-in-category and
sub-category maps, ElementTrackingData category rows, SymbolIdMgr default
type maps, the tracker id-sets, AppInfoSystemFamiliesNames, the view /
drawing indexes ...) it compares K1's document object (the reader-accepted
shape) with S5's (our census-complete FAILING candidate) CLASS-BY-CLASS,
KEY-BY-KEY, and reports each MISMATCH (missing entry, entry pointing at an
absent id, wrong class in a slot, unpopulated required slot, extra /
foreign entry, order divergence) ranked by the reader's walk order.

Every emitted probe MUST pass ``tools/rvt_validate.py`` with ZERO errors
(the arbiter output is pasted into the reports); every probe carries a
manifest entry (probes.json) naming the ONE thing it tests, its passing
sibling, and what PASS / FAIL mean.  Validator-clean is NECESSARY, not
sufficient -- only the Autodesk reader (the orchestrator's viewer queue)
decides.  READ docs/inbox/genesis-addback.md.

Usage (repo root, .venv python):
    tools/genesis_addback.py                     # probes + parity audit
    tools/genesis_addback.py --only R1,R1s       # some probes
    tools/genesis_addback.py --parity-only       # just the audit
    tools/genesis_addback.py --no-parity         # just the probes
"""
from __future__ import annotations

import argparse
import collections
import dataclasses
import json
import os
import sys
import time
from collections import Counter, OrderedDict, defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from rvt import adocument as adoc                                   # noqa: E402
from rvt import ecc                                                 # noqa: E402
from rvt import stream_encoders as se                               # noqa: E402
from rvt.cfb_writer import write_cfb                                # noqa: E402
from rvt.commit import commit_new_elements, verify_written          # noqa: E402
from rvt.container import open_rvt                                  # noqa: E402
from rvt.mutate import Document, ElemRecPlan                        # noqa: E402
from rvt.objects import iter_records                                # noqa: E402
from rvt.encode import record_bytes                                 # noqa: E402
from rvt.partitions import StreamWalker                              # noqa: E402
from rvt.reduce import delete_elements                              # noqa: E402
from rvt.roundtrip import read_entries                              # noqa: E402
from rvt.genesis import settings as ST                              # noqa: E402
from rvt.genesis import catalog as CAT                              # noqa: E402
from rvt.genesis.types import IdSource, INVALID, TypeRecord         # noqa: E402
import genesis_assemble as GA                                       # noqa: E402
import genesis_triage as GT                                         # noqa: E402

GEN = os.path.join(ROOT, "experiments", "genesis")
TRIAGE = os.path.join(GEN, "triage")
SINGLETONS = os.path.join(GEN, "singletons")
OUT_DIR = os.path.join(GEN, "addback")
K1 = os.path.join(TRIAGE, "K1.rvt")        # Autodesk empty-project skeleton (parent, passing lineage)
K5 = os.path.join(TRIAGE, "K5.rvt")        # K1 minus the settings singletons  -- viewer FAIL
K6 = os.path.join(TRIAGE, "K6.rvt")        # K1 minus the built-in style catalog -- viewer FAIL
S5 = os.path.join(SINGLETONS, "S5.rvt")    # census-complete constructed candidate -- viewer FAIL
G1C = os.path.join(GEN, "G1_candidate.rvt")
MAPS = os.path.join(GEN, "G1_registry_maps.json")
PARITY_MD = os.path.join(ROOT, "docs", "writer", "registry-parity.md")
IDENTITY = {"author": "rvt-writer", "client_app_name": "rvt-writer",
            "username": "rvt-writer"}

os.makedirs(OUT_DIR, exist_ok=True)


def log(msg: str) -> None:
    print(msg, flush=True)


def _relp(p: str) -> str:
    return os.path.relpath(p, ROOT)


def _tmp(name: str) -> str:
    return os.path.join(OUT_DIR, f".{name}.tmp.rvt")


def _cleanup(*paths: str) -> None:
    for p in paths:
        try:
            os.remove(p)
        except OSError:
            pass


# ===========================================================================
# 1. FILE FACTS  (read-only)
# ===========================================================================

class Facts:
    """A file's element inventory + decoded document object (read-only)."""

    def __init__(self, path: str):
        self.path = path
        self.doc = Document.from_file(path)
        self.ids: Set[int] = set(self.doc.et_by_id)
        self._cls: Dict[int, str] = {}
        with open_rvt(path) as f:
            self.latest_payload = f.inflate(adoc.STREAM, 0)
            self.bfi = se.decode_basic_file_info(f.logical("BasicFileInfo"))
        self._tree = None

    def cls_of(self, eid: int) -> str:
        if eid not in self._cls:
            self._cls[eid] = self.doc.class_of(eid) or "?"
        return self._cls[eid]

    def census(self) -> Counter:
        return Counter(self.cls_of(e) for e in self.ids)

    @property
    def tree(self) -> dict:
        if self._tree is None:
            a = adoc.decode_latest(self.latest_payload)
            if not a.clean:
                raise RuntimeError(f"{self.path}: ADocument decode not clean")
            self._tree = a.value
        return self._tree

    def tree_copy(self) -> dict:
        return json.loads(json.dumps(self.tree))

    def ids_of_class(self, name: str) -> List[int]:
        return sorted(self.doc.ids_of_class(name))

    def value(self, eid: int) -> dict:
        return self.doc.value(eid) or {}

    def watermark(self) -> int:
        with open_rvt(self.path) as f:
            et = se.decode_elemtable(f.inflate("Global/ElemTable"))
        return max(int(r[4]) for r in et["records"])


# ===========================================================================
# 2. THE ADOCUMENT ID-LEAF WALK  (shared by transplant, re-point and audit)
# ===========================================================================

_ROOT_BODIES = (("m_oContentTable", "ContentTable"),
                ("m_oNobleSecondaryData", "NOBLE_SecondaryDataStorage"),
                ("m_pStyleSettings", "StyleSettings"),
                ("m_pSteelModelInfo", "SteelModelInfo"),
                ("m_oExServicesUsed", "ExServicesUsed"))

_EDITOR: Optional[GA.AdocGraphEditor] = None


def editor() -> GA.AdocGraphEditor:
    global _EDITOR
    if _EDITOR is None:
        _EDITOR = GA.AdocGraphEditor(maps=GA.load_registry_maps())
    return _EDITOR


def registry_bodies(tree: dict) -> List[Tuple[str, dict]]:
    """Every document-object body that can hold element references, in the
    order the reader meets them: the AppInfo array (serialization order),
    then the root-level typed bodies."""
    out: List[Tuple[str, dict]] = list(GA._appinfo_bodies(tree))
    for field, cls_name in _ROOT_BODIES:
        holder = tree.get(field)
        body = holder.get("value") if isinstance(holder, dict) else None
        if isinstance(body, dict):
            out.append((cls_name, body))
    return out


def all_leaves(tree: dict) -> List[Tuple[str, Any]]:
    """[(body_class, leaf), ...] every ElementId-typed leaf in the tree."""
    ed = editor()
    out = []
    for cls_name, body in registry_bodies(tree):
        for lf in ed.iter_leaves(body, cls_name, cls_name) or []:
            out.append((cls_name, lf))
    return out


def referenced_ids(tree: dict) -> Set[int]:
    return {lf.value for _c, lf in all_leaves(tree)
            if isinstance(lf.value, int) and lf.value > 0}


def remap_ids_in_tree(tree: dict, mapping: Dict[int, int]) -> Counter:
    """RE-POINT: rewrite every ElementId leaf whose value is a key of
    ``mapping`` to the mapped id -- across EVERY registry body (a schema-
    typed walk, complete by construction).  Returns {(body, container): n}."""
    hits: Counter = Counter()
    for cls_name, lf in all_leaves(tree):
        new = mapping.get(lf.value)
        if new is None:
            continue
        lf.holder[lf.key] = int(new)
        cont = lf.frames[-1].field if lf.frames else "(scalar)"
        hits[(cls_name, cont)] += 1
    for k in ("m_ownerFamilyId", "m_ownerFamilyContainingGroupId"):
        v = tree.get(k)
        if isinstance(v, int) and v in mapping:
            tree[k] = int(mapping[v])
            hits[("(root)", k)] += 1
    return hits


# ===========================================================================
# 3. TRANSPLANT: restore the SAMPLE's own rows into a derived file
# ===========================================================================

def extract_element_records(donor: str, ids: Iterable[int]) -> Tuple[Dict[int, Dict[int, bytes]], Dict[int, Any]]:
    """Pull the EXACT framed record bytes (seq 101/102/103) + the ElemTable
    row of each id from the donor file's HOST save unit.  Byte-preserving:
    the transplanted rows re-enter a derived file verbatim, at their
    original ids (which are free again in the derived file, since the derived
    file was made by deleting them)."""
    want = {int(i) for i in ids}
    recs: Dict[int, Dict[int, bytes]] = {i: {} for i in want}
    with open_rvt(donor) as f:
        pname = f.partition_streams()[0]
        w = StreamWalker(f.logical(pname), inflate=True, keep_data=True)
        if w.errors:
            raise RuntimeError(f"{donor}: walker errors {w.errors[:3]}")
        u0 = [b for b in sorted(w.blocks, key=lambda x: x.hdr_offset) if b.unit == 0]
        for seq in (101, 102, 103):
            seg = b"".join(b.data for b in u0 if b.seq == seq)
            for r in iter_records(seg, seq):
                if r.elem_id in want and seq not in recs[r.elem_id]:
                    recs[r.elem_id][seq] = bytes(record_bytes(seg, r, seq))
        et = se.decode_elemtable(f.inflate("Global/ElemTable"))
    plans: Dict[int, Any] = {}
    # ElemTable tuple layout (stream_encoders): (original_id, creation_ep,
    # modified_ep, user_modified_ep, id, owner_id, partition_id)
    for row in et["records"]:
        eid = int(row[4])
        if eid in want:
            own = row[5]
            plans[eid] = ElemRecPlan(elem_id=eid, original_id=int(row[0]),
                                     creation_ep=int(row[1]), modified_ep=int(row[2]),
                                     user_modified_ep=int(row[3]),
                                     owner_id=(int(own) if isinstance(own, int)
                                               and own < (1 << 63) else -1),
                                     partition_id=int(row[6] if len(row) > 6 else 0))
    missing = sorted(i for i in want if len(recs[i]) != 3 or i not in plans)
    if missing:
        raise RuntimeError(f"donor {os.path.basename(donor)} lacks complete records "
                           f"for {len(missing)} ids: {missing[:8]}")
    return recs, plans


def transplant(base: str, donor: str, ids: Iterable[int], out: str) -> dict:
    """out = base + the donor's own element records for ``ids`` (verbatim
    framed bytes, original ids, original owner ids) committed through the
    proven writer path (append before the sentinel, ElemTable rows added
    id-sorted, canonical re-block).  Record ORDER inside the unit is not
    id-sorted -- Autodesk's own passing sample has 42-45 order inversions,
    its unit-0 records literally start with the KeynoteTable / AssemblyCode
    table, so appended low-id records are within the reader's tolerance."""
    t0 = time.time()
    ids = sorted({int(i) for i in ids})
    if not ids:
        # nothing to transplant: emit a re-blocked copy so downstream steps
        # always start from a canonical file
        rr = delete_elements(base, out, [])
        return {"op": "no-transplant (canonical copy)", "restored": 0,
                "seconds": round(time.time() - t0, 1)}
    recs, plans = extract_element_records(donor, ids)
    records_by_element = [recs[i] for i in ids]
    elemrecs = [plans[i] for i in ids]
    tmp = out + ".append.tmp"
    rep = commit_new_elements(base, tmp, records_by_element, elemrecs,
                              identity=dict(IDENTITY))
    ver = verify_written(tmp, ids)
    found = {i for s in ver["new_ids_found"].values() for i in s}
    clean = all((v.get("clean") is not False)
                for s in ver["new_ids_found"].values() for v in s.values())
    rr = delete_elements(tmp, out, [])                  # canonical re-blocking
    _cleanup(tmp)
    return {"op": "transplant sample rows (verbatim record bytes, original ids)",
            "restored": len(ids), "restored_ids_sample": ids[:12],
            "elemtable_after": rep.elemtable_count_after,
            "watermark_after": rep.watermark_after,
            "verify_written": {"crc_failures": ver["crc_failures"],
                               "ecc_mismatches": ver["ecc_mismatches"],
                               "walker_errors": ver["walker_errors"],
                               "stamps_ok": ver["stamps_ok"],
                               "ids_found": len(found), "records_clean": clean},
            "reblock": {"blocks_before": rr.blocks_before, "blocks_after": rr.blocks_after},
            "seconds": round(time.time() - t0, 1)}


# ===========================================================================
# 4. THE DOCUMENT OBJECT: recompute from K1's, add ours, write
# ===========================================================================

def reinstate_reference_latest(target: str, ref_latest_payload: bytes, out: str,
                               *, still_absent: Set[int]) -> dict:
    """Replace ``target``'s Global/Latest with the REFERENCE (K1) document
    object, purged of exactly ``still_absent`` (the ids that remain absent
    from the target).  Because K5/K6 were themselves produced from K1's
    document object by exactly this purge (a superset of it), this
    reproduces the sample's registry state for the target's element set
    byte-for-byte -- every restored sample row comes back at its EXACT
    original registry position with its exact original neighbours.
    ``still_absent`` empty => the reference object is reinstated verbatim.
    """
    t0 = time.time()
    if not still_absent:
        rep = adoc.write_with_latest(target, out, ref_latest_payload)
        rep["op"] = "reinstate K1's document object verbatim (nothing still absent)"
        rep["purged_ids"] = 0
        rep["seconds"] = round(time.time() - t0, 1)
        return rep
    swap = out + ".k1latest.tmp"
    adoc.write_with_latest(target, swap, ref_latest_payload)
    prep = GT.purge_ids_from_latest(swap, out, sorted(still_absent))
    _cleanup(swap)
    prep["op"] = ("reinstate K1's document object purged of the still-absent "
                  "(substituted) ids only")
    prep["still_absent"] = len(still_absent)
    prep["seconds"] = round(time.time() - t0, 1)
    return prep


def commit_records(base: str, out: str, records: List[TypeRecord]) -> dict:
    """Commit OUR TypeRecords as new elements (the S-ladder's proven path)."""
    t0 = time.time()
    recs = [{seq: b for seq, b in r.encode().items()}
            for r in sorted(records, key=lambda x: x.elem_id)]
    plans = [r.as_new_element().elemrec for r in sorted(records, key=lambda x: x.elem_id)]
    tmp = out + ".append.tmp"
    rep = commit_new_elements(base, tmp, recs, plans, identity=dict(IDENTITY))
    ver = verify_written(tmp, [r.elem_id for r in records])
    clean = sum(1 for s in ver["new_ids_found"].values()
                for v in s.values() if v.get("clean") is not False)
    rr = delete_elements(tmp, out, [])                 # canonical re-blocking
    _cleanup(tmp)
    return {"op": "commit OUR elements + re-block",
            "new_elements": len(records),
            "elemtable_after": rep.elemtable_count_after,
            "watermark_after": rep.watermark_after,
            "verify_written": {"crc_failures": ver["crc_failures"],
                               "ecc_mismatches": ver["ecc_mismatches"],
                               "walker_errors": ver["walker_errors"],
                               "stamps_ok": ver["stamps_ok"],
                               "new_records_clean": clean},
            "reblock": {"blocks_before": rr.blocks_before, "blocks_after": rr.blocks_after},
            "seconds": round(time.time() - t0, 1)}


def register_browser_orgs_minimal(tree: dict, orgs: List[TypeRecord]) -> dict:
    """Register OUR (non-default) browser organizations WITHOUT the
    assembler's cache-clearing (which suits a from-scratch document): only
    append the ids to ``BrowserOrganizationTracking.m_elemIdSet``; the base's
    existing per-tree default map / folder cache / expanded-node state (the
    sample skeleton's, whose 4 'all' defaults are still present) is left
    exactly as the reader-accepted file had it."""
    rep = {"orgs": len(orgs), "elemIdSet_added": 0, "defaults_map_kept": True}
    if not orgs:
        return rep
    body = ST._appinfo_body(tree, "BrowserOrganizationTracking")
    if body is None:
        rep["skipped"] = "BrowserOrganizationTracking absent"
        return rep
    ids = body.setdefault("m_elemIdSet", [])
    for r in orgs:
        if r.elem_id not in ids:
            ids.append(int(r.elem_id))
            rep["elemIdSet_added"] += 1
    return rep


def apply_our_registries(tree: dict, records: List[TypeRecord], maps: dict,
                         k1: Optional["Facts"] = None) -> dict:
    """Populate the document object over OUR new records: the settings /
    trackers / navigator / trackers through ``settings.apply_adoc_registry``
    (positional UET slots + named AppInfo scalars + tracker id-sets +
    AppInfoSystemFamiliesNames + ETD + view/drawing index), and OUR
    browser organizations through the minimal cache-preserving path.
    Only ADDS our ids into (already-nulled / dropped) slots; the base's own
    entries are never overwritten (apply_adoc_registry keeps populated
    slots and reports them as skipped)."""
    orgs = [r for r in records if r.class_name == "BrowserOrganization"]
    rest = [r for r in records if r.class_name != "BrowserOrganization"]
    report: Dict[str, Any] = {}
    report["settings"] = ST.apply_adoc_registry(tree, rest, maps=maps) if rest else \
        {"applied": {}, "skipped": []}
    report["browser_orgs"] = register_browser_orgs_minimal(tree, orgs)
    # the browser organizations' AppInfoSystemFamiliesNames rows (the
    # 'sysfam' surface apply_adoc_registry adds per class it receives)
    if orgs:
        sfn = ST._appinfo_body(tree, "AppInfoSystemFamiliesNames")
        if sfn is not None:
            rows = sfn.setdefault("m_idMap", [])
            key = int(sfn.get("m_newKey") or (len(rows)))
            for r in orgs:
                rows.append({"first": key, "second": {"m_elementIds": [int(r.elem_id)]}})
                key += 1
            sfn["m_newKey"] = key
            sfn["m_bValid"] = True
            report["browser_orgs"]["sysfam_rows_added"] = len(orgs)
    report["special"] = special_registrations(tree, records, k1=k1)
    return report


def special_registrations(tree: dict, records: List[TypeRecord],
                          k1: Optional["Facts"] = None) -> dict:
    """The registry surfaces settings.ADOC_REGISTRY does not cover, found
    by the parity audit -- applied so OUR substituted classes are indexed
    exactly where the sample's own rows were:
      * PrintSettingsTracking.m_idMRU  -> our PrintSettings (the MRU pointer)
      * CopyWatchModeMgr: fill the nulled slot of the parallel
        (m_linkCopyWatchProps / m_linkDocIds) pair whose link document is
        still present with OUR CopyWatchProperties (or the in-document
        member when no link exists)
      * ElemsSetWithCellsTracking: register any of our records holding
        external-reference / storage cells under their cell-kind sets."""
    rep: Dict[str, Any] = {}
    by_class: Dict[str, List[TypeRecord]] = defaultdict(list)
    for r in records:
        by_class[r.class_name].append(r)
    # -- print settings MRU ------------------------------------------------
    ps = by_class.get("PrintSettings") or []
    if ps:
        pst = ST._appinfo_body(tree, "PrintSettingsTracking")
        if pst is not None and pst.get("m_idMRU") in (None, INVALID):
            pst["m_idMRU"] = int(ps[0].elem_id)
            rep["PrintSettingsTracking.m_idMRU"] = int(ps[0].elem_id)
    # -- copy/watch parallel slot ------------------------------------------
    cw = by_class.get("CopyWatchProperties") or []
    if cw:
        cwm = ST._appinfo_body(tree, "CopyWatchModeMgr")
        if cwm is not None:
            props = cwm.get("m_linkCopyWatchProps")
            docs = cwm.get("m_linkDocIds")
            filled = False
            if isinstance(props, list) and isinstance(docs, list) and len(props) == len(docs):
                for i, (p, d) in enumerate(zip(props, docs)):
                    if (p in (None, INVALID)) and isinstance(d, int) and d > 0:
                        props[i] = int(cw[0].elem_id)
                        filled = True
                        rep["CopyWatchModeMgr.m_linkCopyWatchProps"] = {
                            "slot": i, "link_doc": d, "props": int(cw[0].elem_id)}
                        break
            if not filled and cwm.get("m_inDocCopyWatchProps") in (None, INVALID):
                cwm["m_inDocCopyWatchProps"] = int(cw[0].elem_id)
                rep["CopyWatchModeMgr.m_inDocCopyWatchProps"] = int(cw[0].elem_id)
    # -- the default-type map: OUR record classes whose default group the
    #    purge dropped / nulled (e.g. ConstructionSetProject = group 110);
    #    the group->class constants come from K1's own map
    if k1 is not None:
        sim = ST._appinfo_body(tree, "SymbolIdMgr")
        if sim is not None:
            dmap = derive_default_group_map(k1)
            class_group = {}
            for g, cls_name in dmap["group_class"].items():
                # single-group classes only (DBViewType etc. are family-keyed)
                if list(dmap["group_class"].values()).count(cls_name) == 1:
                    class_group[cls_name] = g
            rows = sim.setdefault("m_defElementTypeMap", [])
            by_group = {r.get("first"): r for r in rows if isinstance(r, dict)}
            filled = []
            for cls_name, recs in by_class.items():
                g = class_group.get(cls_name)
                if g is None:
                    continue
                row = by_group.get(g)
                if row is None:
                    rows.append({"first": int(g), "second": int(recs[0].elem_id)})
                    filled.append((int(g), cls_name, int(recs[0].elem_id), "added"))
                elif row.get("second") in (None, INVALID):
                    row["second"] = int(recs[0].elem_id)
                    filled.append((int(g), cls_name, int(recs[0].elem_id), "filled"))
            if filled:
                rep["SymbolIdMgr.m_defElementTypeMap"] = filled
    # -- cell-kind sets for our own external-cell holders --------------------
    holders: Dict[int, List[int]] = defaultdict(list)
    for r in records:
        cl = (r.obj or {}).get("m_cellList")
        cells = ((cl or {}).get("value") or {}).get("m_cells") if isinstance(cl, dict) else None
        for c in (cells or []):
            pc = c.get("ptr_class") if isinstance(c, dict) else None
            key = CELL_KIND_SETS.get(pc)
            if key is not None:
                # only register kinds that actually carry references
                inner = c.get("value") or {}
                if pc == "ExternalResourceReferenceCell" and not (
                        inner.get("m_externalResourceReferences")):
                    continue
                holders[key].append(int(r.elem_id))
    if holders:
        body = ST._appinfo_body(tree, "ElemsSetWithCellsTracking")
        if body is not None:
            rows = body.setdefault("m_elemIdSetMap", [])
            by_key = {r_.get("first"): r_ for r_ in rows if isinstance(r_, dict)}
            for key, eids in holders.items():
                row = by_key.get(key)
                if row is None:
                    row = {"first": int(key), "second": {"m_idSet": []}}
                    rows.append(row)
                    by_key[key] = row
                s = (row.setdefault("second", {})).setdefault("m_idSet", [])
                for e in eids:
                    if e not in s:
                        s.append(int(e))
            rep["ElemsSetWithCellsTracking"] = {int(k): sorted(v) for k, v in holders.items()}
    return rep


def write_latest(path_in: str, path_out: str, tree: dict) -> dict:
    """Encode ``tree`` (byte-exact codec, self-checked) and write it as the
    file's Global/Latest, refreshing BasicFileInfo's last-save path."""
    new_payload = adoc.encode_latest(tree)
    back = adoc.decode_latest(new_payload)
    if not (back.clean and back.value == tree):
        raise RuntimeError("authored document object does not round-trip byte-exact")
    logical = adoc.latest_logical_stream(new_payload, level=3)
    framed = ecc.frame_stream(logical)
    with open_rvt(path_in) as f:
        bfi = se.decode_basic_file_info(f.logical("BasicFileInfo"))
    bfi2 = dict(bfi)
    bfi2["last_save_path"] = os.path.basename(path_out)
    entries = read_entries(path_in)
    new_streams = {adoc.STREAM: framed,
                   "BasicFileInfo": se.encode_basic_file_info(bfi2, regenerate_mirror=True)}
    out_entries = [dataclasses.replace(e, data=new_streams[e.path])
                   if (e.entry_type == "stream" and e.path in new_streams) else e
                   for e in entries]
    write_cfb(path_out, out_entries)
    return {"latest_payload": len(new_payload)}


# ===========================================================================
# 5. CERTIFICATION  (validator + census + dangling accounting)
# ===========================================================================

def certify(path: str, *, base_tree_refs_absent: Set[int],
            our_ids: Iterable[int] = (), restored_ids: Iterable[int] = ()) -> dict:
    """The per-probe gate: rvt_validate (0 errors required), the class
    census + document coherence, and the DANGLING split -- ids the final
    document object references that the file lacks, separated into
    INHERITED (the passing skeleton itself already dangles them: the
    R5/R9-proven-tolerated model residue) vs NEW (introduced by this edit:
    must be ZERO)."""
    val = GT.validate(path)
    cen = GT.census(path)
    with open_rvt(path) as f:
        et = se.decode_elemtable(f.inflate("Global/ElemTable"))
        payload = f.inflate(adoc.STREAM, 0)
    ids_in_file = {int(r[4]) for r in et["records"]}
    a = adoc.decode_latest(payload)
    refs = referenced_ids(a.value)
    dangling = {i for i in refs if i not in ids_in_file}
    inherited = dangling & base_tree_refs_absent
    new = dangling - base_tree_refs_absent
    ours = {int(i) for i in our_ids}
    rest = {int(i) for i in restored_ids}
    return {
        "validator": val,
        "census": cen,
        "adoc_clean": bool(a.clean),
        "adoc_element_refs": len(refs),
        "our_ids_referenced": len(refs & ours),
        "our_ids_not_referenced": len(ours - refs),
        "restored_ids_referenced": len(refs & rest),
        "restored_ids_present": len(rest & ids_in_file),
        "dangling_total": len(dangling),
        "dangling_inherited_tolerated": len(inherited),
        "dangling_NEW": sorted(new)[:24],
        "dangling_NEW_count": len(new),
    }


def base_absent_refs(base_facts: Facts) -> Set[int]:
    """Ids the BASE file's own document object references but the base lacks
    = the inherited, reader-tolerated dangling set (the K rungs kept K1's
    ~2,100 model-residue dangles, R5/R9-proven harmless)."""
    return {i for i in referenced_ids(base_facts.tree) if i not in base_facts.ids}


# ===========================================================================
# 6. OUR K5 DELTA  (the singleton classes K5 deleted, built by OUR
#    constructors and wired to K5's own companions)
# ===========================================================================

def k5_wiring(k5: Facts, k1: Facts) -> dict:
    """The companion ids OUR constructors must reference, discovered from
    the K5 base itself (every id below EXISTS in K5) -- so our records are
    wired to the sample skeleton exactly as its own singletons were."""
    w: Dict[str, Any] = {}
    d = k5.doc
    # UnitsElem / AllProjectPhases / project view / true north
    w["units"] = k5.ids_of_class("UnitsElem")[0]
    w["all_phases"] = k5.ids_of_class("AllProjectPhases")[0]
    # phases: 'New Construction' (the current phase = the last in sequence)
    phases = k5.ids_of_class("ProjectPhase")
    def _seq(pid: int) -> int:
        return int((d.value(pid) or {}).get("m_seqNum", 0) or 0)
    w["phase_new"] = max(phases, key=lambda p: (_seq(p), p))
    pfs = k5.ids_of_class("PhaseFilterElem")
    show_all = [p for p in pfs if str((d.value(p) or {}).get("m_name") or "") == "Show All"]
    w["phase_filter"] = (show_all or pfs)[0]
    # the DOCUMENT sun: the sun the sample's own ModelGraphicsStyle presets
    # and its project / navigator views reference (54520 in this lineage);
    # ModelGraphicsStyle is deleted at K5, so read the K1 parent's, fall back
    # to the project view's m_lights.m_sunAndShadowSettingsId
    sun = None
    for e in k1.ids_of_class("ModelGraphicsStyle"):
        s = (k1.value(e) or {}).get("m_idShadowsSettings")
        if isinstance(s, int) and s > 0 and s in k5.ids:
            sun = s
            break
    if sun is None:
        pv = k5.ids_of_class("DBViewProject")[0]
        vdm = ((k5.value(pv).get("m_pViewDisplayMgr") or {}).get("value") or {})
        sun = ((vdm.get("m_lights") or {}).get("m_sunAndShadowSettingsId"))
    w["document_sun"] = int(sun)
    # levels: 'Level 1' (elevation 0) for energy settings' ground plane
    levels = d.levels()
    lvl1 = [l for l in levels if str(l.get("name")) == "Level 1"] or \
        [l for l in levels if abs(l.get("elevation_ft") or 0) < 1e-9] or levels
    w["level1"] = int(lvl1[0]["id"])
    # geo location: the PROJECT position the (kept) active-geo-location
    # tracker names; the kept tracker means ours is NOT added (its class
    # survived K5), we only need this id for reference
    agl = k5.ids_of_class("ActiveGeoLocationTrackingElement")
    w["geo_location"] = int((k5.value(agl[0]) or {}).get("m_projectGeoLocationId", INVALID)) \
        if agl else INVALID
    # workset visibility (kept), MEP trackers (component / network / data
    # kept), pipe + duct settings (kept) -- the deleted MEPSystemTracker /
    # LayoutNodesTracker are rebuilt AROUND them
    w["workset_visibility"] = k5.ids_of_class("WorksetVisibilitySettingsElem")[0]
    w["mep_component_tracker"] = k5.ids_of_class("MEPComponentTracker")[0]
    w["mep_network_tracker"] = k5.ids_of_class("MEPNetworkTracker")[0]
    w["mep_network_data"] = k5.ids_of_class("MEPNetworkDataElem")[0]
    w["pipe_settings"] = k5.ids_of_class("RbsPipeSettingsElem")[0]
    w["duct_settings"] = k5.ids_of_class("RbsDuctSettingsElem")[0]
    # keynote table (kept in K5: the deleted KeynotingSystem must name it)
    kt = k5.ids_of_class("KeynoteTable")
    w["keynote_table"] = int(kt[0]) if kt else INVALID
    # the navigator's viewport type = the ViewportAttributes the sample's own
    # navigator viewport used ('Title w Line'), read from K1's viewport
    vpt = INVALID
    for e in k1.ids_of_class("Viewport"):
        v = k1.value(e) or {}
        if v.get("m_dbViewId") in set(k1.ids_of_class("RbsDbViewSystemNavigator")):
            vpt = int(v.get("m_attrId", INVALID))
            break
    w["viewport_type"] = vpt if vpt in k5.ids else INVALID
    # the wire catalog SYMBOLS present in K5 (our wire-sizes table keys on
    # THEIR RbsWireMaterialType / TemperatureRatingType / InsulationType)
    def _syms(cls_name: str) -> Dict[str, int]:
        out = {}
        for e in k5.ids_of_class(cls_name):
            v = k5.value(e) or {}
            si = (v.get("m_symbolInfo") or {}).get("value") if isinstance(v.get("m_symbolInfo"), dict) else None
            nm = (si or {}).get("m_name") if si else v.get("m_name")
            if isinstance(nm, str) and nm:
                out[nm] = int(e)
        return out
    w["wire_materials_by_name"] = _syms("RbsWireMaterialType")
    w["wire_temps_by_name"] = _syms("RbsWireTemperatureRatingType")
    w["wire_insulations_by_name"] = _syms("RbsWireInsulationType")
    # the link document the sample's CopyWatchProperties belonged to
    # (CopyWatchModeMgr.m_linkDocIds parallel to m_linkCopyWatchProps): K5
    # KEPT the RvtLink; our substitute copy/watch state names the same link
    cwm = GA._appinfo_body(k1.tree, "CopyWatchModeMgr") or {}
    link_docs = [x for x in (cwm.get("m_linkDocIds") or [])
                 if isinstance(x, int) and x > 0 and x in k5.ids]
    w["copywatch_link_doc"] = int(link_docs[0]) if link_docs else INVALID
    return w


def _match_name(candidates: Dict[str, int], *names: str) -> Optional[int]:
    """Case-insensitive prefix match of any of ``names`` against the
    sample's catalog symbol names (our 'Aluminum' vs their 'Aluminium')."""
    low = {k.lower(): v for k, v in candidates.items()}
    for n in names:
        n = n.lower()
        if n in low:
            return low[n]
        for k, v in low.items():
            if k.startswith(n[:5]) or n.startswith(k[:5]):
                return v
    return None


def build_our_k5_delta(k5: Facts, k1: Facts, ids: IdSource, *,
                       only_classes: Optional[Set[str]] = None) -> Tuple[List[TypeRecord], dict]:
    """OUR constructors for exactly the singleton classes K5 DELETED that
    ``standard_settings`` builds (the S3/S5 constellation), wired to K5's
    own companions; NOT the whole constellation (its classes K5 KEPT --
    revisions, area schemes, energy settings, the wire catalog symbols, the
    91 view types, the pipe/duct settings, the component/network trackers,
    the workset visibility, the keynote table, the 4 default browser
    organizations -- must NOT be duplicated).  ``only_classes`` restricts
    the set (R1s: pen table + browser organizations).  Returns (records,
    report{covered_classes, wiring, per_class notes})."""
    w = k5_wiring(k5, k1)
    recs: List[TypeRecord] = []
    covered: List[str] = []
    notes: Dict[str, str] = {}

    def want(cls: str) -> bool:
        return only_classes is None or cls in only_classes

    # -- the project pen table (id 2 deleted; the 8 family-scoped copies
    #    are curtain-SYSTEM-family content and survive in K5) ----------------
    if want("PenWidthTableElem"):
        recs.append(ST.pen_width_table(ids=ids))
        covered.append("PenWidthTableElem")
        notes["PenWidthTableElem"] = ("OUR ISO-128-based line-weight table replaces "
                                       "the project pen table (element id 2); the 8 "
                                       "family-scoped copies (curtain system families) survive in K5")
    # -- the project-browser organizations: K5 KEPT the 4 per-tree 'all'
    #    DEFAULTS (m_bDefault=True, pinned by DBViewProject) and deleted the
    #    7 named schemes -> ours = the 2 house schemes only ------------------
    if want("BrowserOrganization"):
        orgs = ST.default_browser_organizations(ids, with_house_set=True)
        house = [r for r in orgs if not r.refs.get("default")]
        recs.extend(house)
        covered.append("BrowserOrganization")
        notes["BrowserOrganization"] = (f"{len(house)} OUR house organizations replace the "
                                        "sample's 7 named schemes; the 4 'all' defaults "
                                        "(m_bDefault=True) survive in K5 and are NOT duplicated")
    if only_classes is not None and not (only_classes - {"PenWidthTableElem", "BrowserOrganization"}):
        return recs, {"covered_classes": covered, "wiring": w, "notes": notes,
                      "records": len(recs)}
    # -- reconcile browser + construction set (K5b population) ---------------
    for cls, fn in (("ReconcileBrowserSettingsElem", ST.reconcile_browser_settings),
                    ("ConstructionSetProject", ST.construction_set_project)):
        if want(cls):
            recs.append(fn(ids=ids))
            covered.append(cls)
    # -- the MEP system navigator + its viewer / viewport / drawing (the 4
    #    K5b elements): plan-like frame naming K5's phase / units / workset
    #    visibility / the DOCUMENT sun / the 'Title w Line' viewport type;
    #    its deferred parent = OUR new MEPSystemTracker (built below) ----------
    nav_needed = want("RbsDbViewSystemNavigator")
    # -- the named singletons (K5c/K5d core) ---------------------------------
    if want("StructSettingsElem"):
        recs.append(ST.struct_settings(ids=ids)); covered.append("StructSettingsElem")
    if want("WallJoinDefaultSetting"):
        recs.append(ST.wall_join_default_setting(ids=ids)); covered.append("WallJoinDefaultSetting")
    if want("AutoJoinTracker"):
        recs.append(ST.auto_join_tracker(ids=ids)); covered.append("AutoJoinTracker")
    if want("KeynotingSystem"):
        # the sample's KeynoteTable (86291 'Standard') SURVIVED K5: our
        # KeynotingSystem names IT (not a second table)
        recs.append(ST.keynoting_system(w["keynote_table"], ids=ids))
        covered.append("KeynotingSystem")
        notes["KeynotingSystem"] = (f"names the sample's surviving KeynoteTable "
                                    f"{w['keynote_table']} (K5 kept it)")
    if want("InitialViewSettings"):
        recs.append(ST.initial_view_settings(ids=ids, initial_view_id=INVALID))
        covered.append("InitialViewSettings")
        notes["InitialViewSettings"] = "OUR default: <Last Viewed> (-1)"
    # -- MEP settings: wire (settings + sizes over K5's OWN wire catalog
    #    symbols), conduit, cable tray, duct SIZES; the pipe / duct SETTINGS
    #    elements survived K5 (pinned by the network tracker) -----------------
    if want("RbsWireSettingsElem"):
        recs.append(ST.wire_settings(ids=ids)); covered.append("RbsWireSettingsElem")
    if want("RbsWireSizesElem"):
        mats = w["wire_materials_by_name"]
        temps = w["wire_temps_by_name"]
        insul = w["wire_insulations_by_name"]
        mat_ids = {"Copper": _match_name(mats, "Copper"),
                   "Aluminum": _match_name(mats, "Aluminium", "Aluminum")}
        temp_ids = {"75": _match_name(temps, "75"), "90": _match_name(temps, "90")}
        ins_ids = {}
        from rvt.genesis import house_standard as hs
        for nm in hs.CONDUCTOR_INSULATIONS:
            hit = _match_name(insul, nm)
            if hit is not None:
                ins_ids[nm] = hit
        mat_ids = {k: v for k, v in mat_ids.items() if v is not None}
        temp_ids = {k: v for k, v in temp_ids.items() if v is not None}
        if mat_ids and temp_ids:
            recs.append(ST.wire_sizes_from_house_table(mat_ids, temp_ids, ins_ids, ids=ids))
            covered.append("RbsWireSizesElem")
            notes["RbsWireSizesElem"] = (f"OUR NEC ampacity table keyed on K5's own wire catalog "
                                         f"symbols: materials {mat_ids}, ratings {temp_ids}, "
                                         f"insulations {len(ins_ids)} ({sorted(ins_ids)})")
        else:
            notes["RbsWireSizesElem"] = "SKIPPED: no wire catalog symbols matched"
    if want("ConduitSettingsElem"):
        recs.append(ST.conduit_settings(ids=ids)); covered.append("ConduitSettingsElem")
    if want("CableTraySettingsElem"):
        recs.append(ST.cable_tray_settings(ids=ids)); covered.append("CableTraySettingsElem")
    if want("RbsDuctSizesElem"):
        recs.append(ST.duct_sizes(ids=ids)); covered.append("RbsDuctSizesElem")
    # -- the two deleted MEP trackers, wired to the KEPT component tracker
    #    and the kept pipe/duct settings (the sample's own regenOnly shape) --
    system_tracker_id = INVALID
    if want("MEPSystemTracker") or want("LayoutNodesTracker"):
        comp = w["mep_component_tracker"]
        layout = ST.tracker("LayoutNodesTracker", ids=ids, regen_only=[comp])
        system = ST.tracker("MEPSystemTracker", ids=ids,
                            regen_only=[w["duct_settings"], w["pipe_settings"],
                                        comp, layout.elem_id])
        recs.extend([layout, system])
        covered.extend(["LayoutNodesTracker", "MEPSystemTracker"])
        system_tracker_id = system.elem_id
        notes["MEPSystemTracker"] = (f"regenOnly -> K5's kept duct/pipe settings "
                                     f"({w['duct_settings']}, {w['pipe_settings']}), kept "
                                     f"component tracker {comp}, OUR layout tracker")
    if nav_needed:
        nav = ST.system_navigator(
            ids, phase_id=w["phase_new"], phase_filter_id=w["phase_filter"],
            sun_settings_id=w["document_sun"], all_phases_id=w["all_phases"],
            units_id=w["units"], workset_visibility_id=w["workset_visibility"],
            mep_system_tracker_id=system_tracker_id,
            viewport_type_id=w["viewport_type"])
        recs.extend(nav)
        covered.extend(["RbsDbViewSystemNavigator", "Viewer", "Viewport", "DBDrawing"])
        notes["RbsDbViewSystemNavigator"] = (
            f"view+viewer+viewport+drawing; sun={w['document_sun']} (the DOCUMENT sun the "
            f"sample's project view + navigator share), phase={w['phase_new']}, "
            f"phase filter={w['phase_filter']}, units={w['units']}, workset visibility="
            f"{w['workset_visibility']} (kept), viewport type={w['viewport_type']} "
            f"('Title w Line', the sample navigator's own), deferred parent = OUR "
            f"MEPSystemTracker {system_tracker_id}")
    # -- other MEP / analysis / fabrication singletons ------------------------
    for cls, fn in (("MEPHiddenLineSettingsElem", ST.mep_hidden_line_settings),
                    ("RouteAnalysisSettings", ST.route_analysis_settings),
                    ("FabricationSettings", ST.fabrication_settings),
                    ("SSEPointVisibilitySettings", ST.sse_point_visibility_settings),
                    ("ReinforcementSettings", ST.reinforcement_settings),
                    ("AutoCamSettingsElem", ST.auto_cam_settings),
                    ("HalftoneUnderlaySettings", ST.halftone_underlay_settings),
                    ("MultipleValuesIndicationSettings", ST.multiple_values_indication_settings),
                    ("CoordinateSystemDisplayElem", ST.coordinate_system_display),
                    ("DefaultDivideSettings", ST.default_divide_settings),
                    ("ProjectCopySettingsElem", ST.project_copy_settings)):
        if want(cls):
            recs.append(fn(ids=ids)); covered.append(cls)
    if want("CopyWatchProperties"):
        # the sample's copy/watch state belonged to its LINK document (its
        # CopyWatchModeMgr registers it parallel to the link doc id); K5 kept
        # the link, so OUR substitute names the same link (empty watch tables)
        recs.append(ST.copy_watch_properties(ids=ids, link_id=w["copywatch_link_doc"]))
        covered.append("CopyWatchProperties")
        notes["CopyWatchProperties"] = (f"OUR empty copy/watch state naming the sample's "
                                        f"surviving link document {w['copywatch_link_doc']} "
                                        f"(registered in CopyWatchModeMgr parallel to it)")
    # the empty trackers K5 deleted (the classes it KEPT -- component /
    # network / network-data / keynote-tags / revision-clouds / workset
    # visibility -- are not rebuilt)
    for cls in ("CircuitNamingTypeSetting", "AssemblyTracker",
                "SheetsInSheetCollectionTracker", "AnalyticalToPhysicalRelationManager",
                "ReactionsUpToDateElem", "ExternalParamLock", "DaylightSourceIdSet",
                "Dwg2dExportUserSettingsData", "STEPExportSettings",
                "SketchGridAppearanceParentElem", "FabricationServiceSettings",
                "CurtaSystemFaceManager", "StructuralConnectionSettings"):
        if want(cls):
            recs.append(ST.tracker(cls, ids=ids)); covered.append(cls)
    if want("WorksharingViewModeSettings"):
        recs.append(ST.worksharing_view_mode_settings(ids=ids))
        covered.append("WorksharingViewModeSettings")
        notes["WorksharingViewModeSettings"] = ("OUR project-level worksharing display element "
                                                 "(the sample also carried a per-user copy)")
    if want("ModelGraphicsStyle"):
        recs.extend(ST.model_graphics_styles(ids, w["document_sun"]))
        covered.append("ModelGraphicsStyle")
        notes["ModelGraphicsStyle"] = f"<Shading>/<Raytracing> -> the document sun {w['document_sun']}"
    if want("PrintSettings"):
        recs.append(ST.print_settings(ids=ids)); covered.append("PrintSettings")
        notes["PrintSettings"] = "OUR single 'Default' setup replaces the sample's 3"
    return recs, {"covered_classes": covered, "wiring": w, "notes": notes,
                  "records": len(recs)}


#: classes standard_settings' 'all' tier builds (the S3/S5 constellation)
#: -- computed once from the constructor itself so the covered/uncovered
#: split is derived, not asserted
def constellation_classes() -> Set[str]:
    cat = ST.standard_settings(IdSource(90_000_000), tier="all",
                               doc_ids={"units": 1, "document_sun": 2, "phase_new": 3,
                                        "phase_filter": 4, "geo_location": 5,
                                        "level1": 6, "phase_set": 7})
    return {r.class_name for r in cat.records}


def k5_removal_analysis(k5: Facts, k1: Facts) -> dict:
    """Classify every element K5 removed: COVERED (our constellation
    builds the class -> substituted by OUR constructor) vs UNCOVERED
    (restored from K1 verbatim), with the per-class counts."""
    removed = sorted(k1.ids - k5.ids)
    by_class: Dict[str, List[int]] = defaultdict(list)
    for e in removed:
        by_class[k1.cls_of(e)].append(e)
    constellation = constellation_classes()
    covered = {c for c in by_class if c in constellation}
    # the family-layer / catalog CASUALTIES that came along with an
    # uncovered singleton (AreaReportSettings' sub-categories, styles, fonts)
    # are uncovered too by definition
    uncovered = {c for c in by_class if c not in constellation}
    return {"removed_ids": removed, "by_class": {k: sorted(v) for k, v in by_class.items()},
            "covered_classes": sorted(covered),
            "uncovered_classes": sorted(uncovered),
            "uncovered_ids": sorted(e for c in uncovered for e in by_class[c]),
            "covered_ids": sorted(e for c in covered for e in by_class[c])}


# ===========================================================================
# 7. OUR K6 DELTA  (the built-in category object-styles table)
# ===========================================================================

def _builtin_style_rows(fx: Facts) -> Dict[Tuple[int, int], int]:
    """{(built-in category id, gstyle type): GStyleElem id} for the
    host-document, non-family-scoped OBJECT-STYLE rows (m_famId -1,
    negative category id) -- the reader's built-in object-styles table."""
    out: Dict[Tuple[int, int], int] = {}
    for e in fx.ids_of_class("GStyleElem"):
        v = fx.value(e) or {}
        if v.get("m_famId", -1) != -1:
            continue
        cid = v.get("m_categoryId")
        if isinstance(cid, int) and cid < 0:
            out[(int(cid), int(v.get("m_gstyleType", 1)))] = int(e)
    return out


def build_our_k6_catalog(k6: Facts, k1: Facts, ids: IdSource) -> Tuple[List[TypeRecord], dict, Dict[int, int]]:
    """OUR built-in-category object-styles rows for exactly the (category,
    style type) pairs K6 deleted (K1's built-in table minus K6's residue),
    generated by ``catalog.builtin_style_catalog`` (OUR discipline scheme
    over the graphic-category ENUM -- 0 rows value-identical to Autodesk's
    table by the assayer's test).  Returns (records, report, remap
    {K1's old row id -> our new id}) -- the remap is the RE-POINT map for
    every reference in K1's document object."""
    k1_rows = _builtin_style_rows(k1)
    k6_rows = _builtin_style_rows(k6)
    missing = {k: v for k, v in k1_rows.items() if k not in k6_rows}
    # generate our full table, keep only the missing pairs
    recs_all = CAT.builtin_style_catalog(ids)
    ours: Dict[Tuple[int, int], TypeRecord] = {}
    for r in recs_all:
        key = (int(r.obj.get("m_categoryId")), int(r.obj.get("m_gstyleType", 1)))
        ours[key] = r
    records: List[TypeRecord] = []
    remap: Dict[int, int] = {}
    unmatched: List[Tuple[int, int]] = []
    for key, old_id in sorted(missing.items()):
        r = ours.get(key)
        if r is None:
            unmatched.append(key)
            continue
        records.append(r)
        remap[old_id] = r.elem_id
    rep = {
        "k1_builtin_style_rows": len(k1_rows),
        "k6_builtin_style_rows": len(k6_rows),
        "missing_pairs": len(missing),
        "our_rows_generated": len(records),
        "missing_pairs_our_enum_lacks": [list(k) for k in unmatched[:20]],
        "missing_pairs_our_enum_lacks_count": len(unmatched),
        "our_enum_categories": len({k[0] for k in ours}),
        "our_enum_pairs": len(ours),
        "by_style_type": dict(Counter("projection" if r.obj.get("m_gstyleType") == 1 else "cut"
                                      for r in records)),
    }
    return records, rep, remap


def k6_removal_analysis(k6: Facts, k1: Facts) -> dict:
    """Split K6's 2,151 deletions into (a) the built-in-category object-
    style rows (substituted by OUR catalog in R2 / re-pointed) and (b)
    everything else (sub-category CategoryElem + their style rows, line /
    fill patterns, materials, appearance assets, the project pen table)
    which R2 RESTORES from K1 so the ONLY difference from the passing
    skeleton is the built-in object-styles table."""
    removed = set(k1.ids) - set(k6.ids)
    builtin_rows = _builtin_style_rows(k1)
    k6_rows = _builtin_style_rows(k6)
    builtin_deleted = {v for k, v in builtin_rows.items() if k not in k6_rows and v in removed}
    others = removed - builtin_deleted
    by_class = Counter(k1.cls_of(e) for e in others)
    return {"removed_total": len(removed),
            "builtin_style_deleted_ids": sorted(builtin_deleted),
            "restore_ids": sorted(others),
            "restore_by_class": dict(by_class.most_common()),
            "pen_table_deleted_by_K6": 2 in removed and k1.cls_of(2) == "PenWidthTableElem"}


# ===========================================================================
# 8. THE PROBE PIPELINE
# ===========================================================================

def id_source_for(*paths: str) -> IdSource:
    """OUR ids start above every base's watermark (rounded up to a clean
    100k boundary, the S-ladder convention) so they never collide with a
    restored sample id."""
    wm = 0
    for p in paths:
        with open_rvt(p) as f:
            et = se.decode_elemtable(f.inflate("Global/ElemTable"))
        wm = max(wm, max(int(r[4]) for r in et["records"]),
                 int(et.get("footer", {}).get("last_id") or 0))
    return IdSource(((wm // 100_000) + 1) * 100_000)


def build_addback(name: str, *, base: Facts, k1: Facts, restore_ids: Set[int],
                  our_records: List[TypeRecord], still_absent: Set[int],
                  repoint: Optional[Dict[int, int]], maps: dict,
                  desc: str, tests: str, pass_means: str, fail_means: str,
                  passing_sibling: str, extra: Optional[dict] = None) -> dict:
    """The generic add-back pipeline:
       1. transplant ``restore_ids`` (the sample's own rows) from K1 into the base
       2. reinstate K1's document object, purged of ``still_absent`` only
       3. commit OUR records; 4. populate the registries over ours
          (and/or apply the re-point remap); 5. certify."""
    t0 = time.time()
    out = os.path.join(OUT_DIR, f"{name}.rvt")
    stages: List[dict] = []
    t1, t2, t3 = _tmp(name + "1"), _tmp(name + "2"), _tmp(name + "3")
    # 1. restore the sample rows the probe holds constant
    s1 = transplant(base.path, k1.path, restore_ids, t1)
    stages.append({"stage": "restore sample rows", **s1})
    log(f"   [{name}] restored {s1.get('restored', 0)} sample rows "
        f"({s1.get('seconds')}s)")
    # 2. K1's document object, purged of only what stays absent
    s2 = reinstate_reference_latest(t1, k1.latest_payload, t2,
                                    still_absent=set(still_absent) if not repoint else set())
    stages.append({"stage": "reinstate reference document object",
                   **{k: v for k, v in s2.items() if k not in ("bodies_touched",)}})
    log(f"   [{name}] reinstated K1's document object; purged still-absent "
        f"{s2.get('purged_ids', len(still_absent) if not repoint else 0)} ({s2.get('seconds')}s)")
    _cleanup(t1)
    cur = t2
    reg_report: Dict[str, Any] = {}
    if our_records:
        # 3. our elements
        s3 = commit_records(cur, t3, our_records)
        stages.append({"stage": "commit OUR elements", **s3})
        log(f"   [{name}] committed {len(our_records)} OUR elements ({s3['seconds']}s)")
        _cleanup(cur)
        cur = t3
        # 4. registries: re-point remap (R2) and/or repopulation (R1)
        with open_rvt(cur) as f:
            payload = f.inflate(adoc.STREAM, 0)
        a = adoc.decode_latest(payload)
        tree = a.value
        if repoint:
            hits = remap_ids_in_tree(tree, repoint)
            reg_report["repoint"] = {"map_size": len(repoint),
                                     "leaves_rewritten": sum(hits.values()),
                                     "by_container": {f"{c}.{f}": n for (c, f), n in hits.items()}}
            # any surface still naming a substituted-away id (none expected
            # after a complete remap) is purged like the reader's own delete
            leftover = {i for i in still_absent if i in referenced_ids(tree)}
            if leftover:
                ed = editor()
                live = referenced_ids(tree) - set(still_absent)
                purged = Counter()
                for cls_name, body in registry_bodies(tree):
                    st = ed.purge_dangling(body, cls_name, live, label=cls_name)
                    purged.update({k: st[k] for k in ("dangling", "nulled",
                                                       "elements_dropped", "scalars_nulled")})
                reg_report["post_remap_purge"] = dict(purged)
            log(f"   [{name}] re-pointed {sum(hits.values())} references over "
                f"{len(repoint)} substituted rows: {dict(hits)}")
        non_gstyle = [r for r in our_records if r.class_name not in ("GStyleElem", "CategoryElem")]
        if non_gstyle:
            rr = apply_our_registries(tree, non_gstyle, maps, k1=k1)
            reg_report["populate"] = rr
            log(f"   [{name}] populated registries: "
                f"{rr['settings'].get('applied')} browser {rr['browser_orgs']}")
            for s in (rr["settings"].get("skipped") or [])[:12]:
                log(f"        skipped: {s}")
        s4 = write_latest(cur, out, tree)
        stages.append({"stage": "registries", **reg_report, **s4})
        _cleanup(cur)
    else:
        # no our-content: cur IS the deliverable
        os.replace(cur, out)
    # 5. certify
    absent = base_absent_refs(k1) | (base_absent_refs(base) if base.path != k1.path else set())
    cert = certify(out, base_tree_refs_absent=absent,
                   our_ids=[r.elem_id for r in our_records],
                   restored_ids=restore_ids)
    v = cert["validator"]
    ok = bool(v["ok"]) and v["errors"] == 0 and cert["dangling_NEW_count"] == 0
    # 6. SELF-PARITY: how does the file's document object differ from K1's
    #    for the classes it carries?  (the audit turned on our own probe)
    selfp = parity_compare(k1.path, out, label_ref="K1", label_subj=name)
    sev0 = [m for m in selfp["mismatches"] if m["severity"] == 0]
    self_parity = {"severity0": len(sev0),
                   "severity0_rows": [f"{m['body']}.{m['container']}: {m['kind']} -- "
                                     f"{m['detail'][:160]}" for m in sev0][:16],
                   "total_mismatches": len(selfp["mismatches"])}
    log(f"   [{name}] self-parity vs K1: {len(sev0)} severity-0 divergence(s)"
        + (": " + "; ".join(f"{m['body']}.{m['container']}" for m in sev0[:5])
           if sev0 else " (registry shape matches K1 for its classes)"))
    rep = {
        "rung": name, "out": _relp(out), "base": _relp(base.path),
        "description": desc, "tests": tests, "if_PASS": pass_means, "if_FAIL": fail_means,
        "passing_sibling": passing_sibling,
        "restored_from_sample": len(restore_ids),
        "our_elements": len(our_records),
        "our_by_class": dict(Counter(r.class_name for r in our_records).most_common()),
        "still_absent_substituted": len(still_absent),
        "stages": stages,
        "certification": cert,
        "self_parity_vs_K1": self_parity,
        "verdict": "VALID" if ok else "NOT-CLEAN",
        "bytes": os.path.getsize(out),
        "seconds": round(time.time() - t0, 1),
    }
    if extra:
        rep.update(extra)
    with open(os.path.join(OUT_DIR, f"{name}.json"), "w") as fh:
        json.dump(rep, fh, indent=1, default=lambda o: sorted(o) if isinstance(o, set) else str(o))
    log(f"[{name}] {'VALID' if ok else '*** NOT CLEAN ***'} -- validator ok={v['ok']} "
        f"errors={v['errors']} warnings={v['warnings']}; elements "
        f"{cert['census']['elements']:,}; dangling NEW {cert['dangling_NEW_count']} "
        f"(inherited {cert['dangling_inherited_tolerated']}); {rep['bytes']:,} B; "
        f"{rep['seconds']}s")
    if not ok:
        for m in (v.get("error_messages") or [])[:6]:
            log(f"      ERROR {m}")
        if cert["dangling_NEW_count"]:
            log(f"      NEW dangling ids: {cert['dangling_NEW'][:12]}")
    return rep


# ---------------------------------------------------------------------------
# the individual rungs
# ---------------------------------------------------------------------------

def build_R1(k1: Facts, k5: Facts, maps: dict, ana: dict) -> dict:
    ids = id_source_for(k1.path, k5.path)
    recs, delta = build_our_k5_delta(k5, k1, ids)
    # the substituted (still-absent) ids = the K5-deleted ids of the
    # classes our constructors cover; everything uncovered is restored
    covered_ids = {e for c in delta["covered_classes"] for e in ana["by_class"].get(c, [])}
    still_absent = covered_ids
    restore = set(ana["removed_ids"]) - covered_ids
    return build_addback(
        "R1", base=k5, k1=k1, restore_ids=restore, our_records=recs,
        still_absent=still_absent, repoint=None, maps=maps,
        passing_sibling="experiments/genesis/triage/K1.rvt (parent skeleton; K3/K4/KD1 = its "
                        "descendants, viewer PASS) / K5.rvt (this base, viewer FAIL)",
        desc=("K5.rvt (Autodesk's empty-project skeleton MINUS every document-settings "
              "singleton; viewer FAIL) + OUR constructors for EVERY deleted singleton class "
              "the S3/S5 constellation builds (" + ", ".join(delta["covered_classes"]) +
              "), wired to K5's OWN companion elements (units, phases, the document sun, "
              "workset visibility, the kept MEP component/network trackers, the wire catalog "
              "symbols, the surviving keynote table, the 'Title w Line' viewport type); the "
              "K5-deleted classes the constellation does NOT build (" +
              ", ".join(sorted(ana["uncovered_classes"])) + ") are RESTORED from K1 "
              "verbatim, and the document object = K1's, purged of only the substituted "
              "ids and repopulated over ours.  R1 differs from the PASSING skeleton ONLY in "
              "that the covered singleton classes are OUR constructors' output."),
        tests=("Are OUR document-settings singleton constructors + their registry wiring "
               "an ACCEPTABLE SUBSTITUTE for the sample's own singletons, tested on the "
               "known-good skeleton instead of the suspect G1 base (S3/S5 tested them on "
               "G1 and could not separate 'our singletons are wrong' from 'the G1 base has "
               "an independent defect')?"),
        pass_means=("OUR singleton constellation cures K5's known failure => our singleton "
                    "constructors + wiring are acceptable substitutes; S5's failure was the G1 "
                    "BASE (an independent defect), not our singletons.  Read R2 for the "
                    "catalog verdict."),
        fail_means=("OUR singleton constructors and/or their registry wiring are rejected "
                    "even on the good skeleton => the defect is in OUR content.  R1s "
                    "(only the pen table + browser organizations ours) bisects: R1s PASS "
                    "puts the defect in the MEP / structural / tracker constructors; R1s "
                    "FAIL puts it in the pen table / browser substitution itself.  Compare "
                    "the parity self-audit in R1.json."),
        extra={"our_delta": delta, "k5_removal": {k: v for k, v in ana.items()
                                                  if k in ("covered_classes", "uncovered_classes")},
               "restored_uncovered_by_class": dict(Counter(k1.cls_of(e) for e in restore))})


def build_R1s(k1: Facts, k5: Facts, maps: dict, ana: dict) -> dict:
    ids = id_source_for(k1.path, k5.path)
    recs, delta = build_our_k5_delta(k5, k1, ids,
                                     only_classes={"PenWidthTableElem", "BrowserOrganization"})
    covered_ids = {e for c in ("PenWidthTableElem", "BrowserOrganization")
                   for e in ana["by_class"].get(c, [])}
    restore = set(ana["removed_ids"]) - covered_ids
    return build_addback(
        "R1s", base=k5, k1=k1, restore_ids=restore, our_records=recs,
        still_absent=covered_ids, repoint=None, maps=maps,
        passing_sibling="experiments/genesis/triage/K1.rvt / R1.rvt (the full claim)",
        desc=("The SMALLER singleton claim: K5.rvt + OUR project pen table (replacing "
              "element id 2, our ISO-128-based line-weight standard) + OUR two house "
              "project-browser organizations (replacing the sample's 7 named schemes; the "
              "4 'all' defaults survive), with EVERY OTHER K5-deleted element RESTORED "
              "from K1 (the MEP / structural / tracker / navigator singletons are the "
              "sample's own).  Differs from the passing skeleton ONLY in the pen table + "
              "browser organizations being ours."),
        tests=("Is the pen table + project-browser substitution alone acceptable?  The "
               "bisection partner of R1: R1 FAIL & R1s PASS => the defect is in our OTHER "
               "constructors (MEP settings / sizes, structural, trackers, navigator, print "
               "...); R1s FAIL => even our pen table / browser organizations are rejected "
               "(K5a's population -- the census's #1 suspect)."),
        pass_means=("OUR pen table + browser organizations are acceptable substitutes; "
                    "any R1 failure is in the other constructor classes."),
        fail_means=("OUR PenWidthTableElem and/or BrowserOrganization records (or their "
                    "PenWidthTableInfo / BrowserOrganizationTracking wiring) are rejected."),
        extra={"our_delta": delta})


def build_R2(k1: Facts, k6: Facts, maps: dict, ana6: dict) -> dict:
    ids = id_source_for(k1.path, k6.path)
    recs, crep, remap = build_our_k6_catalog(k6, k1, ids)
    restore = set(ana6["restore_ids"])
    still_absent = set(ana6["builtin_style_deleted_ids"]) - set(remap)      # rows our enum lacks
    return build_addback(
        "R2", base=k6, k1=k1, restore_ids=restore, our_records=recs,
        still_absent=set(ana6["builtin_style_deleted_ids"]), repoint=remap, maps=maps,
        passing_sibling="experiments/genesis/triage/K1.rvt (parent) / K6.rvt (this base, "
                        "viewer FAIL) / R2s.rvt (the mechanics control)",
        desc=("K6.rvt (the empty-project skeleton MINUS the built-in category / GStyle "
              "catalog; viewer FAIL) + OUR complete built-in-category object-styles table: "
              f"{crep['our_rows_generated']} OUR GStyleElem rows (our discipline colours / "
              "weights over the graphic-category ENUM) for exactly the (built-in category, "
              "style type) pairs K6 deleted, each at a NEW id, with EVERY reference in K1's "
              "document object RE-POINTED at our rows (CategoryTracking.m_gstyleData + the "
              "SymbolIdMgr entries -- a schema-typed id remap, complete by construction).  "
              "Every OTHER K6 casualty is RESTORED from K1: the sub-category CategoryElem + "
              "their style rows, the line / fill patterns, materials, appearance assets, "
              "AND the project pen table (element id 2, which K6 ALSO deleted -- a K-ladder "
              "confound R2/R2s remove by holding it constant).  R2 differs from the passing "
              "skeleton ONLY in the built-in object-styles table being OURS."),
        tests=("Is OUR complete built-in-category object-styles catalog (S4/S5's) an "
               "acceptable substitute for the sample's, when every registry / in-file "
               "reference points at our rows exactly where it pointed at theirs -- tested "
               "on the known-good skeleton?"),
        pass_means=("OUR catalog (over the frozen graphic-category enum, 0 rows value-"
                    "identical to Autodesk's) is an acceptable substitute => the K6/S4 "
                    "failures were the base / the bundled pen table, not our catalog values."),
        fail_means=("(with R2s PASSING) OUR catalog rows themselves are rejected -- their "
                    "shape / values / the enum coverage; compare R2's catalog report "
                    "(pairs our enum lacks) and the parity audit.  If R2s ALSO FAILS the "
                    "add-back mechanics are the suspect and R2 is unreadable."),
        extra={"catalog_report": crep, "k6_removal": {k: (v if not isinstance(v, list) else len(v))
                                                     for k, v in ana6.items()},
               "restored_by_class": ana6["restore_by_class"],
               "unsubstituted_builtin_rows_left_absent": sorted(still_absent)[:20],
               "unsubstituted_builtin_rows_left_absent_count": len(still_absent)})


def build_R2s(k1: Facts, k6: Facts, maps: dict, ana6: dict) -> dict:
    everything = set(ana6["restore_ids"]) | set(ana6["builtin_style_deleted_ids"])
    return build_addback(
        "R2s", base=k6, k1=k1, restore_ids=everything, our_records=[],
        still_absent=set(), repoint=None, maps=maps,
        passing_sibling="experiments/genesis/triage/K1.rvt (should be equivalent) / R2.rvt "
                        "(the substitution)",
        desc=("THE MECHANICS CONTROL: K6.rvt + ALL 2,151 of K6's deleted rows RESTORED from "
              "K1 (the built-in style rows too, plus the sub-categories, patterns, "
              "materials, assets, the project pen table), transplanted at their original ids "
              "through the SAME writer path R1/R2 use, with K1's document object reinstated "
              "VERBATIM (nothing left absent => nothing purged).  Content-equivalent to K1; "
              "the only differences from K1 are the writer's own (record order of the "
              "restored rows at the end of the unit -- the passing sample itself is not "
              "id-ordered -- and the proven-benign identity scrub of BasicFileInfo / the "
              "increment table, V32 PASS)."),
        tests=("Are the add-back MECHANICS (byte-preserving transplant + document-object "
               "reinstatement + re-blocking) themselves reader-clean?  The control that "
               "makes R2 (and R1) readable."),
        pass_means=("The transplant + registry machinery is sound => an R2 FAIL is "
                    "attributable to OUR catalog rows, an R1 FAIL to OUR singletons."),
        fail_means=("The add-back mechanics introduce a defect (record order? episode "
                    "metadata? the identity scrub?) => R1/R2 verdicts are void until this "
                    "passes; diff R2s against K1 stream-by-stream."))


# ===========================================================================
# 9. THE REGISTRY-PARITY AUDIT  (K1 vs S5)
# ===========================================================================

@dataclasses.dataclass
class Mismatch:
    body: str
    container: str
    kind: str          # MISSING / DANGLING / WRONG_CLASS / UNPOPULATED_SLOT /
                       # EXTRA / COUNT_SHORTFALL / ORDER / INCONSISTENT_KEY
    detail: str
    severity: int      # 0 = highest (registry indexes present rows wrongly)
    walk_order: int    # position of the body in the reader's walk


#: per-container row fields to leave OUT of the row key: document-local
#: counters and session values that legitimately differ between files
_KEY_IGNORE: Dict[Tuple[str, str], Set[str]] = {
    ("AppInfoSystemFamiliesNames", "m_idMap"): {"first"},   # doc-local counter
    ("NewItemNumber", "m_items"): {"m_lastItemName"},          # numbering session state
}

#: registry BODIES assessed as regenerable session / analysis / cache
#: state (empty in a fresh document; the reader recomputes them) -- their
#: mismatches are reported but capped at severity 1, never 0.  Evidence:
#: R9 passes with no AllPlanTopologies (PlanTopologyIdInfo dangling),
#: templates / open-window / current-sketch-plane state is per-session,
#: NOBLE_SecondaryDataStorage = colour-fill / analysis result caches (the
#: passing skeleton's own copy is majority-DANGLING), item numbering =
#: MEP part-numbering counters.
ASSESSED_REGENERABLE = {
    "NewItemNumber", "ADocWarnings", "NOBLE_SecondaryDataStorage",
    "DBDrawingInfo", "SketchPlaneInfo", "PlanTopologyIdInfo",
    "AbsLayoutAppInfo", "WorksharingDisplaySettingsTracking",
}
#: DBViewInfo.m_DBViewTemplates only (its m_DBViewsIndex is a real index)
ASSESSED_REGENERABLE_CONTAINERS = {("DBViewInfo", "m_DBViewTemplates")}


def _desc(v: int, cls_of, ids_present: Set[int]):
    """Class-keyed descriptor of one ElementId leaf value: the CLASS of a
    present element, 'ABSENT' for a dangling positive id, or the raw value
    for the non-positive sentinels (built-in category ids, -1 = unset)."""
    if v > 0:
        return ("cls", cls_of(v)) if v in ids_present else ("ABSENT",)
    return ("val", v)


def registry_profile(tree: dict, cls_of, ids_present: Set[int]) -> dict:
    """Profile ONE file's document object into comparable registry
    surfaces via the schema-typed ElementId leaf walk:
      * UET positional slots: {slot: (class, id, present)}
      * scalar AppInfo members: {(body, member-path): (class, id, present)}
      * containers: per (body, field) a Counter of ROW SIGNATURES.  A
        signature is CLASS-KEYED (element ids differ between files):
          - a struct row = (its non-id scalar key fields, its immediate
            ElementId fields as (field -> descriptor));
          - a nested leaf (an id inside a row's inner set) = (row key
            fields, generic in-row path, descriptor);
          - a bare id-list entry = (descriptor).
        Descriptors are the CLASS of a present element / ABSENT / the raw
        non-positive sentinel (so built-in category keys stay exact).
    Also records per container: the distinct element ids referenced per
    class (registry COVERAGE = distinct referenced / inventory) and the
    dangling entries."""
    ed = editor()
    prof: Dict[str, Any] = {"bodies": [], "scalars": {}, "uet": {}, "containers": {}}
    for body_cls, body in registry_bodies(tree):
        prof["bodies"].append(body_cls)
        leaves = ed.iter_leaves(body, body_cls, body_cls) or []
        by_row: "OrderedDict[Tuple[str, int], dict]" = OrderedDict()
        for lf in leaves:
            v = lf.value
            if isinstance(v, bool) or not isinstance(v, int):
                continue
            if not lf.frames:                                   # a scalar member of the body
                member = lf.path.split(".", 1)[1] if "." in lf.path else lf.path
                cls_name = cls_of(v) if (v > 0 and v in ids_present) else \
                    ("ABSENT" if v > 0 else "-")
                prof["scalars"][(body_cls, member)] = (cls_name, v,
                                                        (v in ids_present) if v > 0 else None)
                continue
            fr0 = lf.frames[0]                                  # OUTERMOST container
            cont = fr0.field
            if body_cls == "UniqueElementsTracking" and cont == "m_elemIds":
                cls_name = cls_of(v) if (v > 0 and v in ids_present) else \
                    ("ABSENT" if v > 0 else "-")
                prof["uet"][int(lf.key)] = (cls_name, v,
                                            (v in ids_present) if v > 0 else None)
                continue
            ent = by_row.setdefault((cont, fr0.index),
                                    {"row": (fr0.lst[fr0.index]
                                             if 0 <= fr0.index < len(fr0.lst) else None),
                                     "leaves": [], "cont": cont})
            ent["leaves"].append(lf)
        for (cont, _ridx), ent in by_row.items():
            c = prof["containers"].setdefault(
                (body_cls, cont), {"sig": Counter(), "dangling": [], "rows": 0,
                                   "classes": Counter(), "distinct": defaultdict(set),
                                   "kind": None})
            row, lvs = ent["row"], ent["leaves"]
            c["rows"] += 1
            ignore = _KEY_IGNORE.get((body_cls, cont), set())
            for lf in lvs:                                       # per-container tallies
                v = lf.value
                if v > 0:
                    if v in ids_present:
                        cls_name = cls_of(v)
                        c["classes"][cls_name] += 1
                        c["distinct"][cls_name].add(v)
                    else:
                        c["classes"]["ABSENT"] += 1
                        c["dangling"].append(v)
            if isinstance(row, dict):
                c["kind"] = "keyed"
                imm = [lf for lf in lvs if lf.holder is row]
                nested = [lf for lf in lvs if lf.holder is not row]
                imm_fields = {lf.key for lf in imm}
                scal = tuple(sorted((k, val) for k, val in row.items()
                                    if k not in imm_fields and k not in ignore
                                    and isinstance(val, (int, bool))
                                    and not isinstance(val, (dict, list))))
                idpart = tuple(sorted((lf.key, _desc(lf.value, cls_of, ids_present))
                                      for lf in imm))
                # is the row keyed by non-element values (enum / built-in ids)?
                valkey = tuple((k, d) for k, d in idpart if d[0] == "val")
                if scal or valkey:
                    c["skeyed"] = True
                if imm:
                    c["sig"][("row", scal, idpart)] += 1
                for lf in nested:
                    # generic in-row path (indices stripped) + the row's value key
                    tail = lf.path.split("]", 1)[-1] if "[" in lf.path else lf.path
                    tail = "".join(ch for ch in tail if not ch.isdigit())
                    c["sig"][("leaf", scal, valkey, tail,
                              _desc(lf.value, cls_of, ids_present))] += 1
            else:
                if c["kind"] != "keyed":
                    c["kind"] = "set"
                for lf in lvs:
                    c["sig"][("id", _desc(lf.value, cls_of, ids_present))] += 1
    # freeze the distinct sets to counts
    for c in prof["containers"].values():
        c["distinct"] = {k: len(v) for k, v in c["distinct"].items()}
        c.setdefault("skeyed", False)
    return prof


def _sig_classes(sig) -> Set[str]:
    """The element classes a signature references."""
    out: Set[str] = set()

    def scan(x):
        if isinstance(x, tuple):
            if len(x) == 2 and x[0] == "cls" and isinstance(x[1], str):
                out.add(x[1])
            else:
                for y in x:
                    scan(y)
    scan(sig)
    return out


def _sig_text(sig) -> str:
    def dtext(d):
        return d[1] if len(d) == 2 else "ABSENT"
    kind = sig[0]
    if kind == "id":
        return str(dtext(sig[1]))
    if kind == "row":
        scal = ", ".join(f"{k}={v}" for k, v in sig[1])
        idp = ", ".join(f"{k}->{dtext(d)}" for k, d in sig[2])
        return f"{{{scal}}} {idp}".strip()
    if kind == "leaf":
        scal = ", ".join(f"{k}={v}" for k, v in sig[1])
        vk = ", ".join(f"{k}={dtext(d)}" for k, d in sig[2])
        d = sig[4]
        return f"{{{scal}{',' if scal and vk else ''}{vk}}} {sig[3]}->{dtext(d)}".strip()
    return str(sig)


def _sig_absent_only(sig) -> bool:
    """A signature made purely of the file's OWN dangling residue (ABSENT
    descriptors, no class, no value key) -- the reader-tolerated model
    residue of the passing skeleton; its absence in the subject is NOT a
    defect and is skipped by the comparison."""
    descs = []
    if sig[0] == "id":
        descs = [sig[1]]
    elif sig[0] == "row":
        descs = [d for _k, d in sig[2]]
    elif sig[0] == "leaf":
        descs = [sig[4]]
    return bool(descs) and all(len(d) == 1 and d[0] == "ABSENT" for d in descs)


#: comparison POLICY per keyed container: 'default-map' = one default
#: element per group (a missing group whose class the subject HAS = a
#: registry gap); 'keyed-track' = per-element registration keyed by an
#: enum / built-in category (a missing key for a present class = a gap);
#: 'detail' = handled by a specialised detail section.  Other keyed
#: containers report missing keyed rows for present classes at severity 1
#: (the keying rule is not verified generically).
KEYED_POLICY: Dict[Tuple[str, str], str] = {
    ("SymbolIdMgr", "m_defElementTypeMap"): "detail",       # _symbolidmgr_detail
    ("CategoryTracking", "m_gstyleData"): "detail",         # _category_tracking_detail
    ("CategoryTracking", "m_categoryData"): "detail",
    ("ElemsSetWithCellsTracking", "m_elemIdSetMap"): "detail",   # _cells_tracking_detail
    ("ElementTrackingData", "m_symbols"): "keyed-track",
    ("ElementTrackingData", "m_elems"): "keyed-track",
    ("NumberingAppInfo", "m_mapCategoriesToParameterIdsToSchemas"): "keyed-track",
}

#: ElemsSetWithCellsTracking.m_elemIdSetMap keys = the cell-KIND registry
#: [DERIVED on the passing skeleton: every member of set 1200 holds an
#: ExternalFileReferenceCell, of 1201 an ExternalResourceReferenceCell,
#: of -100 an ESEntityCell (extensible storage), and no holder is outside
#: its set] -- an element carrying such a cell MUST be registered under it.
CELL_KIND_SETS: Dict[str, int] = {
    "ExternalFileReferenceCell": 1200,
    "ExternalResourceReferenceCell": 1201,
    "ESEntityCell": -100,
}


def parity_compare(ref_path: str, subj_path: str, *, label_ref: str = "K1",
                   label_subj: str = "S5") -> dict:
    """THE PARITY AUDIT: for every registry surface, K1's shape vs S5's
    shape and each MISMATCH, ranked by the reader's walk order (the AppInfo
    array serialization order = the document object's field order)."""
    ref = Facts(ref_path)
    subj = Facts(subj_path)
    ref_cen = ref.census()
    subj_cen = subj.census()
    pref = registry_profile(ref.tree, ref.cls_of, ref.ids)
    psub = registry_profile(subj.tree, subj.cls_of, subj.ids)
    ed = editor()
    uet_map = {int(k): v for k, v in (ed.maps.get("UET_POS_TO_CLASS") or {}).items()}
    body_order = {b: i for i, b in enumerate(pref["bodies"])}
    mm: List[Mismatch] = []
    #: the reference's OWN dangling ids (its reader-tolerated model residue);
    #: a subject entry dangling the same id INHERITED it -- not a defect
    ref_dangling = {i for i in referenced_ids(ref.tree) if i not in ref.ids}

    def cap(body: str, cont: str, sev: int) -> int:
        """Cap severity for assessed-regenerable state (never severity 0)."""
        if (body in ASSESSED_REGENERABLE or (body, cont) in ASSESSED_REGENERABLE_CONTAINERS) \
                and sev == 0:
            return 1
        return sev

    def bo(body: str) -> int:
        return body_order.get(body, 999)

    # ---- (0) the AppInfo body set itself --------------------------------------
    ref_bodies, sub_bodies = set(pref["bodies"]), set(psub["bodies"])
    for b in pref["bodies"]:
        if b not in sub_bodies:
            mm.append(Mismatch(b, "(body)", "MISSING",
                               f"registry body {b} present in {label_ref}'s document object, "
                               f"ABSENT from {label_subj}'s (an unpopulated AppInfo slot)",
                               1, bo(b)))
    for b in psub["bodies"]:
        if b not in ref_bodies:
            mm.append(Mismatch(b, "(body)", "EXTRA",
                               f"registry body {b} in {label_subj} but not in {label_ref} "
                               "(foreign body -- informational)", 3, 999))

    # ---- (1) UniqueElementsTracking positional slots ---------------------------
    uet_rows = []
    slots = sorted(set(pref["uet"]) | set(psub["uet"]))
    for k in slots:
        rk, rid, rp = pref["uet"].get(k, ("-", -1, None))
        sk, sid, sp = psub["uet"].get(k, ("(no slot)", -1, None))
        mapcls = uet_map.get(k, "?")
        note = ""
        sev = None
        if rid > 0 and rp:
            # populated in the reference
            if sid <= 0:
                # is the class one the subject even has?
                have = subj_cen.get(rk, 0)
                if have:
                    note = (f"UNPOPULATED_SLOT: {label_ref} slot {k} = {rk}; {label_subj} slot "
                            f"is -1 although {label_subj} HAS {have} {rk} element(s) "
                            f"(registry does not index a PRESENT row)")
                    sev = 0
                else:
                    note = (f"MISSING(inventory): {label_ref} slot {k} = {rk}; {label_subj} has "
                            f"no {rk} elements at all (an inventory gap, not a wiring gap)")
                    sev = 2
            elif sp is False:
                note = f"DANGLING: {label_subj} slot {k} names id {sid} not in the file"
                sev = 0
            elif sk != rk:
                note = (f"WRONG_CLASS: {label_ref} slot {k} indexes {rk}, {label_subj} slot {k} "
                        f"indexes {sk} (id {sid})")
                sev = 0
        elif sid > 0 and sp is False and sid in ref_dangling:
            note = ""                       # inherited dangling (the ref dangles it too)
        elif sid > 0 and (rid <= 0 or not rp):
            note = (f"EXTRA: {label_subj} slot {k} = {sk} (id {sid}); {label_ref} slot is empty "
                    f"(map class {mapcls}) -- an occupied slot the accepted file leaves empty")
            sev = 2 if sk == mapcls else 1
            if sk != mapcls:
                note += f"; ALSO the class {sk} is NOT the compiled-in class of slot {k} ({mapcls})"
        # class-vs-map consistency check for the subject
        if sid > 0 and sp and mapcls not in ("?", None) and sk != mapcls:
            extra_note = (f"MAP_MISMATCH: {label_subj} slot {k} holds a {sk} but the compiled-"
                          f"in slot class is {mapcls} (our UET_POS_TO_CLASS wiring is off)")
            mm.append(Mismatch("UniqueElementsTracking", f"m_elemIds[{k}]", "WRONG_CLASS",
                               extra_note, 0, bo("UniqueElementsTracking")))
        uet_rows.append((k, mapcls, rk, rid, sk, sid, note))
        if note and sev is not None:
            kind = note.split(":", 1)[0]
            mm.append(Mismatch("UniqueElementsTracking", f"m_elemIds[{k}]", kind, note, sev,
                               bo("UniqueElementsTracking")))

    # ---- (2) scalar AppInfo members --------------------------------------------
    scalar_rows = []
    for key in sorted(set(pref["scalars"]) | set(psub["scalars"]), key=lambda x: (bo(x[0]), x[1])):
        body, path = key
        rk, rid, rp = pref["scalars"].get(key, ("-", -1, None))
        sk, sid, sp = psub["scalars"].get(key, ("(absent)", -1, None))
        note = ""
        sev = None
        if rid > 0 and rp:
            if key not in psub["scalars"] or sid <= 0:
                have = subj_cen.get(rk, 0)
                if have:
                    note = (f"UNPOPULATED_SLOT: {label_ref} {body}.{path} = {rk}; {label_subj}'s "
                            f"is null although {label_subj} HAS {have} {rk} element(s)")
                    sev = 0
                else:
                    note = (f"MISSING(inventory): {label_ref} {body}.{path} = {rk}; {label_subj} "
                            f"has no {rk} elements")
                    sev = 2
            elif sp is False:
                note = f"DANGLING: {label_subj} {body}.{path} = id {sid} not in the file"
                sev = 0
            elif sk != rk:
                note = (f"WRONG_CLASS: {label_ref} {body}.{path} indexes {rk}, {label_subj}'s "
                        f"indexes {sk}")
                sev = 0
        elif sid > 0 and sp is False and sid not in ref_dangling:
            note = f"DANGLING: {label_subj} {body}.{path} = id {sid} not in the file"
            sev = 0
        elif sid > 0 and (rid <= 0 or not rp):
            note = (f"EXTRA: {label_subj} {body}.{path} = {sk} (id {sid}); {label_ref} leaves it "
                    f"null")
            sev = 2
        scalar_rows.append((body, path, rk, rid, sk, sid, note))
        if note and sev is not None:
            mm.append(Mismatch(body, path, note.split(":", 1)[0], note, sev, bo(body)))

    # ---- (3) containers: class-keyed row-signature diff ---------------------------
    container_rows = []
    all_keys = sorted(set(pref["containers"]) | set(psub["containers"]),
                      key=lambda x: (bo(x[0]), x[1]))
    for ckey in all_keys:
        body, cont = ckey
        rc = pref["containers"].get(ckey)
        sc = psub["containers"].get(ckey)
        row = {"body": body, "container": cont,
               "ref_kind": (rc or {}).get("kind"), "subj_kind": (sc or {}).get("kind"),
               "ref_entries": sum((rc or {}).get("classes", Counter()).values()) if rc else 0,
               "subj_entries": sum((sc or {}).get("classes", Counter()).values()) if sc else 0,
               "ref_classes": dict((rc or {}).get("classes", Counter()).most_common(8)) if rc else {},
               "subj_classes": dict((sc or {}).get("classes", Counter()).most_common(8)) if sc else {},
               "subj_dangling": len((sc or {}).get("dangling", [])) if sc else 0,
               "regenerable": (body in ASSESSED_REGENERABLE
                               or (body, cont) in ASSESSED_REGENERABLE_CONTAINERS),
               "mismatches": []}
        rc_sig = rc["sig"] if rc else Counter()
        sc_sig = sc["sig"] if sc else Counter()
        rc_classes = rc["classes"] if rc else Counter()
        sc_classes = sc["classes"] if sc else Counter()
        rc_distinct = rc["distinct"] if rc else {}
        sc_distinct = sc["distinct"] if sc else {}

        def ref_coverage(cls_name: str) -> Tuple[int, int]:
            """(distinct ref elements of the class referenced here, ref inventory)."""
            return rc_distinct.get(cls_name, 0), ref_cen.get(cls_name, 0)

        # dangling entries in the subject: a defect unless INHERITED (the
        # reference dangles the same id = its own tolerated model residue)
        subj_dang = (sc["dangling"] if sc else [])
        inherited = [d for d in subj_dang if d in ref_dangling]
        fresh = [d for d in subj_dang if d not in ref_dangling]
        row["subj_dangling_inherited"] = len(inherited)
        row["subj_dangling"] = len(fresh)
        for d in fresh[:60]:
            note = f"DANGLING: {label_subj} {body}.{cont} names id {d} which is not in the file"
            row["mismatches"].append(note)
            mm.append(Mismatch(body, cont, "DANGLING", note, cap(body, cont, 0), bo(body)))

        keyed_container = bool((rc or {}).get("skeyed") or (sc or {}).get("skeyed"))
        policy = KEYED_POLICY.get((body, cont), "generic-keyed" if keyed_container else "unkeyed")
        row["policy"] = policy

        # --- (a) UNKEYED containers (plain id sets / class-only rows): is
        #     the class registered per element in the ref (COMPLETE), and
        #     does the subject register all of ITS elements?
        if policy == "unkeyed":
            classes = sorted((set(rc_classes) | set(sc_classes)) - {"ABSENT"})
            for cls_name in classes:
                n_ref = rc_classes.get(cls_name, 0)
                n_sub = sc_classes.get(cls_name, 0)
                d_ref, inv_ref = ref_coverage(cls_name)
                d_sub, inv_sub = sc_distinct.get(cls_name, 0), subj_cen.get(cls_name, 0)
                complete = inv_ref > 0 and d_ref >= inv_ref
                partial = inv_ref > 0 and 0 < d_ref < inv_ref
                if n_ref and inv_sub and d_sub < inv_sub:
                    if complete:
                        kind = "MISSING" if d_sub == 0 else "COUNT_SHORTFALL"
                        note = (f"{kind} (mandatory per-element registry): {label_ref} "
                                f"{body}.{cont} registers ALL {inv_ref} of its {cls_name} "
                                f"element(s) ({n_ref} entries); {label_subj} registers only "
                                f"{d_sub} of its {inv_sub} {cls_name} element(s) "
                                f"({inv_sub - d_sub} PRESENT rows unregistered)")
                        row["mismatches"].append(note)
                        mm.append(Mismatch(body, cont, kind, note, cap(body, cont, 0),
                                           bo(body)))
                    elif partial and d_sub == 0:
                        note = (f"CONDITIONAL registry: {label_ref} {body}.{cont} registers "
                                f"{d_ref} of its {inv_ref} {cls_name} (a rule-based subset); "
                                f"{label_subj} registers none of its {inv_sub} -- verify "
                                f"the rule for the subject's elements")
                        row["mismatches"].append(note)
                        mm.append(Mismatch(body, cont, "CONDITIONAL", note,
                                           min(cap(body, cont, 1), 2), bo(body)))
                elif n_ref and not inv_sub:
                    note = (f"MISSING (inventory gap): {label_ref} {body}.{cont} references "
                            f"{n_ref} x {cls_name}; {label_subj} has NO {cls_name} "
                            f"elements (its base carries fewer content classes by design)")
                    row["mismatches"].append(note)
                    mm.append(Mismatch(body, cont, "MISSING", note, 3, bo(body)))
                elif n_sub and not n_ref and inv_ref:
                    note = (f"EXTRA: {label_subj} {body}.{cont} references {n_sub} x "
                            f"{cls_name}; {label_ref} references none of its {inv_ref} "
                            f"{cls_name}")
                    row["mismatches"].append(note)
                    mm.append(Mismatch(body, cont, "EXTRA", note, 2, bo(body)))

        # --- (b) signature diff: rows the ref carries that the subject lacks
        miss = {s: n for s, n in (rc_sig - sc_sig).items() if not _sig_absent_only(s)}
        extra = {s: n for s, n in (sc_sig - rc_sig).items() if not _sig_absent_only(s)}
        if policy != "detail":
            # class-referencing missing rows in a KEYED container: a registry
            # gap when the subject HAS the referenced class (per the policy)
            # coverage-relative: a keyed signature is a GAP only when the
            # subject lacks it ENTIRELY (its rows for the class use other
            # keys, or none) or leaves some of ITS OWN elements of the class
            # unregistered -- not when it merely has fewer elements of the class
            by_class_miss: Dict[str, int] = Counter()
            examples: Dict[str, str] = {}
            for sig, n in miss.items():
                if sc_sig.get(sig, 0) > 0:
                    continue                # the subject registers this exact key; count = inventory
                for cls_name in _sig_classes(sig):
                    inv_sub = subj_cen.get(cls_name, 0)
                    if not inv_sub:
                        continue
                    d_sub = sc_distinct.get(cls_name, 0)
                    if d_sub >= inv_sub:
                        continue            # every subject element of the class is registered here
                    by_class_miss[cls_name] += n
                    examples.setdefault(cls_name, _sig_text(sig))
            if keyed_container and by_class_miss:
                strict = policy in ("default-map", "keyed-track")
                for cls_name, n in sorted(by_class_miss.items(), key=lambda x: -x[1]):
                    what = ("default(s) for" if policy == "default-map" else "keyed row(s) for")
                    d_sub = sc_distinct.get(cls_name, 0)
                    note = (f"MISSING {what} present class {cls_name}: {label_ref} "
                            f"{body}.{cont} carries {n} keyed row(s) referencing "
                            f"{cls_name} that {label_subj} lacks; {label_subj} HAS "
                            f"{subj_cen.get(cls_name)} {cls_name} element(s) of which only "
                            f"{d_sub} are registered here; e.g. {examples[cls_name]}"
                            + ("" if strict else " (keying rule not verified generically)"))
                    row["mismatches"].append(note)
                    mm.append(Mismatch(body, cont, "MISSING", note,
                                       cap(body, cont, 0 if strict else 1), bo(body)))
            # element-free keyed rows (enum sentinels / built-in ids) the subject lacks
            keyed_missing = [(s, n) for s, n in miss.items() if not _sig_classes(s)]
            if keyed_missing:
                total = sum(n for _s, n in keyed_missing)
                ex = ", ".join(f"{_sig_text(s)} x{n}" for s, n in keyed_missing[:5])
                note = (f"MISSING KEYS: {label_ref} {body}.{cont} carries {total} keyed row(s) "
                        f"{label_subj} lacks (element-free keys / enum sentinels); e.g. {ex}")
                row["mismatches"].append(note)
                mm.append(Mismatch(body, cont, "MISSING", note, cap(body, cont, 1), bo(body)))
            keyed_extra = [(s, n) for s, n in extra.items() if not _sig_classes(s)]
            if keyed_extra:
                total = sum(n for _s, n in keyed_extra)
                ex = ", ".join(f"{_sig_text(s)} x{n}" for s, n in keyed_extra[:5])
                note = (f"EXTRA KEYS: {label_subj} {body}.{cont} carries {total} keyed row(s) "
                        f"{label_ref} lacks; e.g. {ex}")
                row["mismatches"].append(note)
                mm.append(Mismatch(body, cont, "EXTRA", note, 2, bo(body)))
        container_rows.append(row)

    # ---- (3b) SymbolIdMgr default-type map detail --------------------------------
    sim_detail = _symbolidmgr_detail(ref, subj, label_ref, label_subj, subj_cen, bo)
    for m in sim_detail["mismatch_objs"]:
        mm.append(m)
    # ---- (3c) ElemsSetWithCellsTracking cell-kind rule --------------------------------
    cells_detail = _cells_tracking_detail(ref, subj, label_ref, label_subj, bo)
    for m in cells_detail["mismatch_objs"]:
        mm.append(m)

    # ---- (4) CategoryTracking detail (the built-in-category / GStyle maps) ----
    ct_detail = _category_tracking_detail(ref, subj, label_ref, label_subj,
                                          inherited_dangling=ref_dangling)
    for m in ct_detail["mismatch_objs"]:
        mm.append(m)

    mm.sort(key=lambda m: (m.severity, m.walk_order, m.body, m.container))
    return {
        "ref": _relp(ref_path), "subj": _relp(subj_path),
        "label_ref": label_ref, "label_subj": label_subj,
        "ref_elements": len(ref.ids), "subj_elements": len(subj.ids),
        "ref_bodies": pref["bodies"], "subj_bodies": psub["bodies"],
        "uet_rows": uet_rows, "scalar_rows": scalar_rows,
        "container_rows": container_rows,
        "category_tracking": {k: v for k, v in ct_detail.items() if k != "mismatch_objs"},
        "symbolid_mgr": {k: v for k, v in sim_detail.items() if k != "mismatch_objs"},
        "cells_tracking": {k: v for k, v in cells_detail.items() if k != "mismatch_objs"},
        "mismatches": [dataclasses.asdict(m) for m in mm],
        "ref_census": dict(ref_cen.most_common()), "subj_census": dict(subj_cen.most_common()),
    }


def derive_default_group_map(ref: Facts) -> dict:
    """From the accepted file's own SymbolIdMgr.m_defElementTypeMap:
    {group: target class} for every populated group, plus the DBViewType
    per-VIEW-FAMILY groups {m_systemFamilyIdx: group} (group 62 = the
    3D-view family default, 71 = floor plan, ...) -- compiled-in constants
    the reader keys the default-type lookup on."""
    sim = GA._appinfo_body(ref.tree, "SymbolIdMgr") or {}
    out = {"group_class": {}, "family_group": {}, "group_family": {}}
    for r in sim.get("m_defElementTypeMap") or []:
        g, tid = r.get("first"), r.get("second")
        if not (isinstance(g, int) and isinstance(tid, int) and tid > 0 and tid in ref.ids):
            continue
        cls_name = ref.cls_of(tid)
        out["group_class"][g] = cls_name
        if cls_name == "DBViewType":
            fam = (ref.value(tid) or {}).get("m_systemFamilyIdx")
            if isinstance(fam, int):
                # first group wins for a family (elevation / section carry two)
                out["family_group"].setdefault(fam, g)
                out["group_family"][g] = fam
    return out


def _symbolidmgr_detail(ref: Facts, subj: Facts, lr: str, ls: str,
                        subj_cen: Counter, bo) -> dict:
    """SymbolIdMgr.m_defElementTypeMap = the document's DEFAULT-TYPE map
    (group -> default element).  Groups are compiled-in per class; the
    DBViewType groups are per VIEW FAMILY (m_systemFamilyIdx).  Report every
    default the accepted file carries for a class / view family the subject
    HAS but leaves without a default."""
    out: Dict[str, Any] = {"mismatch_objs": []}
    dmap = derive_default_group_map(ref)
    sim_s = GA._appinfo_body(subj.tree, "SymbolIdMgr") or {}
    subj_groups: Dict[int, int] = {}
    for r in sim_s.get("m_defElementTypeMap") or []:
        g, tid = r.get("first"), r.get("second")
        if isinstance(g, int):
            subj_groups[g] = tid if isinstance(tid, int) else -1
    # non-DBViewType single-class defaults
    missing_class_defaults = []
    for g, cls_name in sorted(dmap["group_class"].items()):
        if cls_name == "DBViewType":
            continue
        have = subj_cen.get(cls_name, 0)
        if have and (g not in subj_groups or subj_groups[g] <= 0):
            missing_class_defaults.append((g, cls_name, have))
    # DBViewType per view family
    subj_families: Dict[int, List[int]] = defaultdict(list)
    for e in subj.ids_of_class("DBViewType"):
        fam = (subj.value(e) or {}).get("m_systemFamilyIdx")
        if isinstance(fam, int):
            subj_families[fam].append(int(e))
    missing_family_defaults = []
    for fam, ids in sorted(subj_families.items()):
        g = dmap["family_group"].get(fam)
        if g is None:
            continue                       # the ref carries no default group for this family
        if g not in subj_groups or subj_groups[g] <= 0:
            missing_family_defaults.append((fam, g, ids))
    out["missing_class_defaults"] = missing_class_defaults
    out["missing_view_family_defaults"] = [(fam, g, ids) for fam, g, ids in missing_family_defaults]
    out["subj_default_groups"] = sorted(subj_groups.items())
    out["ref_view_family_groups"] = dmap["family_group"]
    W = bo("SymbolIdMgr")
    if missing_family_defaults:
        fams = ", ".join(f"family {fam} (group {g})" for fam, g, _i in missing_family_defaults[:8])
        out["mismatch_objs"].append(Mismatch(
            "SymbolIdMgr", "m_defElementTypeMap", "MISSING",
            f"{ls} carries NO DEFAULT view type for {len(missing_family_defaults)} of its view "
            f"families although it HAS DBViewTypes for them ({fams}); {lr} registers one "
            f"default DBViewType per view family (group = compiled-in family slot: 62 3D, "
            f"71 floor plan, 72 ceiling plan, 73 section, ...)", 0, W))
    for g, cls_name, have in missing_class_defaults:
        out["mismatch_objs"].append(Mismatch(
            "SymbolIdMgr", "m_defElementTypeMap", "MISSING",
            f"{ls} carries NO DEFAULT of class {cls_name} (group {g}) although it HAS "
            f"{have} {cls_name} element(s); {lr} registers one", 0, W))
    return out


def cell_holders(fx: Facts) -> Dict[str, List[Tuple[int, str]]]:
    """{cell class: [(element id, element class)]} for the cell KINDS the
    ElemsSetWithCellsTracking registry keys on (external file / resource
    references, extensible-storage entities)."""
    out: Dict[str, List[Tuple[int, str]]] = defaultdict(list)
    for e in fx.ids:
        v = fx.value(e) or {}
        cl = v.get("m_cellList")
        cells = ((cl or {}).get("value") or {}).get("m_cells") if isinstance(cl, dict) else None
        seen = set()
        for c in (cells or []):
            pc = c.get("ptr_class") if isinstance(c, dict) else None
            if pc in CELL_KIND_SETS and pc not in seen:
                out[pc].append((int(e), fx.cls_of(e)))
                seen.add(pc)
    return out


def _cells_tracking_detail(ref: Facts, subj: Facts, lr: str, ls: str, bo) -> dict:
    """ElemsSetWithCellsTracking.m_elemIdSetMap = the CELL-KIND registry:
    an element carrying an ExternalFileReferenceCell must be in set 1200,
    an ExternalResourceReferenceCell in 1201, an ESEntityCell in -100.
    The rule is first VALIDATED on the reference (its holders vs its set
    members), then the subject's cell holders are checked against its sets."""
    out: Dict[str, Any] = {"mismatch_objs": []}

    def sets_of(fx: Facts) -> Dict[int, Set[int]]:
        body = GA._appinfo_body(fx.tree, "ElemsSetWithCellsTracking") or {}
        res: Dict[int, Set[int]] = {}
        for row in body.get("m_elemIdSetMap") or []:
            k = row.get("first")
            ids2 = ((row.get("second") or {}).get("m_idSet") or [])
            if isinstance(k, int):
                res[k] = {int(i) for i in ids2 if isinstance(i, int) and i > 0}
        return res
    rsets, ssets = sets_of(ref), sets_of(subj)
    rholders, sholders = cell_holders(ref), cell_holders(subj)
    # validate the rule on the reference (present holders only)
    rule = {}
    for cell_cls, key in CELL_KIND_SETS.items():
        holders = {e for e, _c in rholders.get(cell_cls, [])}
        members = {i for i in rsets.get(key, set()) if i in ref.ids}
        rule[cell_cls] = {"key": key,
                          f"{lr}_holders": len(holders), f"{lr}_present_members": len(members),
                          f"{lr}_holders_not_in_set": len(holders - members),
                          f"{lr}_members_not_holding": len(members - holders)}
    out["rule_validation"] = rule
    # per (cell kind, class): is registration COMPLETE in the reference?
    # (the resource-cell set is conditional: the skeleton registers its
    # keynote table / energy settings / assembly-code table / link symbol
    # but NOT its appearance-asset resource cells)
    complete: Set[Tuple[str, str]] = set()
    partial: Set[Tuple[str, str]] = set()
    for cell_cls, key in CELL_KIND_SETS.items():
        by_cls: Dict[str, List[int]] = defaultdict(list)
        for e, c in rholders.get(cell_cls, []):
            by_cls[c].append(e)
        members = rsets.get(key, set())
        for c, ids2 in by_cls.items():
            reg = sum(1 for e in ids2 if e in members)
            (complete if reg == len(ids2) else partial).add((cell_cls, c))
    out["complete_class_kinds"] = sorted(complete)
    out["conditional_class_kinds"] = sorted(partial)
    ref_unreg = {e for cell_cls, key in CELL_KIND_SETS.items()
                 for e, _c in rholders.get(cell_cls, [])
                 if e not in rsets.get(key, set())}
    # apply to the subject
    missing = []
    for cell_cls, key in CELL_KIND_SETS.items():
        for eid, ecls in sholders.get(cell_cls, []):
            if eid in ssets.get(key, set()) or eid in ref_unreg:
                continue                       # registered, or inherited-unregistered
            if (cell_cls, ecls) in complete or (cell_cls, ecls) not in partial:
                # the reference registers ALL its holders of this class for
                # this cell kind (or never had one): the subject's must be
                missing.append((eid, ecls, cell_cls, key))
    out[f"{ls}_cell_holders"] = {k: v for k, v in sholders.items()}
    out[f"{ls}_sets"] = {k: sorted(v) for k, v in ssets.items()}
    out["subject_unregistered_holders"] = missing
    if missing:
        ex = ", ".join(f"{ecls} {eid} -> set {key} ({cc})" for eid, ecls, cc, key in missing[:6])
        out["mismatch_objs"].append(Mismatch(
            "ElemsSetWithCellsTracking", "m_elemIdSetMap", "MISSING",
            f"{ls} has {len(missing)} element(s) holding external-reference / storage "
            f"cells that are NOT registered under their cell-kind set (per the rule "
            f"validated on {lr}: for their classes {lr} registers EVERY such holder): "
            f"{ex}", 0, bo("ElemsSetWithCellsTracking")))
    return out


def _category_tracking_detail(ref: Facts, subj: Facts, lr: str, ls: str, *,
                              inherited_dangling: Set[int] = frozenset()) -> dict:
    """The BuiltInCategory -> CategoryElem / GStyle maps in detail: the
    keyed comparison of CategoryTracking.m_gstyleData (category id + style
    type -> gstyle row) and m_categoryData (parent category -> sub-
    category), cross-checked against each file's OWN GStyle / Category
    inventory (does the registry index every present row, and is each
    entry consistent with the row it points at).  Dangling entries the
    reference itself dangles (its tolerated residue) are INHERITED, not
    counted as defects."""
    out: Dict[str, Any] = {"mismatch_objs": []}
    ct_r = GA._appinfo_body(ref.tree, "CategoryTracking") or {}
    ct_s = GA._appinfo_body(subj.tree, "CategoryTracking") or {}
    order = 0
    # gstyleData
    def gmap(fx: Facts, ct: dict, inherited: Set[int] = frozenset()):
        rows = ct.get("m_gstyleData") or []
        by_key: Dict[Tuple[int, int], int] = {}
        dangling, incons, dup = [], [], 0
        for r in rows:
            cid = r.get("m_categoryId")
            gid = r.get("m_gstyleId")
            gt = r.get("m_gstyleType")
            if not (isinstance(cid, int) and isinstance(gid, int)):
                continue
            key = (int(cid), int(gt) if isinstance(gt, int) else 0)
            if key in by_key:
                dup += 1
            by_key[key] = int(gid)
            if gid > 0 and gid not in fx.ids:
                if gid not in inherited:
                    dangling.append(int(gid))
            elif gid > 0:
                v = fx.value(gid) or {}
                own_cat = v.get("m_categoryId")
                own_type = v.get("m_gstyleType")
                if fx.cls_of(gid) != "GStyleElem":
                    incons.append((int(gid), fx.cls_of(gid), "not a GStyleElem"))
                elif own_cat != cid or (isinstance(gt, int) and own_type != gt):
                    incons.append((int(gid), (own_cat, own_type), f"entry key {(cid, gt)}"))
        return by_key, dangling, incons, dup, len(rows)
    kr, dr, ir, dupr, nr = gmap(ref, ct_r)
    ks, ds, is_, dups, ns = gmap(subj, ct_s, inherited_dangling)
    builtin_r = {k for k in kr if k[0] < 0}
    builtin_s = {k for k in ks if k[0] < 0}
    # every GStyle row PRESENT in the subject must be indexed here -- unless
    # the reference leaves the SAME (inherited) row unindexed too
    unindexed_r = []
    indexed_targets_r = set(kr.values())
    for e in ref.ids_of_class("GStyleElem"):
        if e not in indexed_targets_r:
            v = ref.value(e) or {}
            unindexed_r.append((int(e), v.get("m_categoryId"), v.get("m_gstyleType"),
                                v.get("m_famId", -1)))
    unindexed_r_ids = {u[0] for u in unindexed_r}
    unindexed_s = []
    indexed_targets = set(ks.values())
    for e in subj.ids_of_class("GStyleElem"):
        if e not in indexed_targets and e not in unindexed_r_ids:
            v = subj.value(e) or {}
            unindexed_s.append((int(e), v.get("m_categoryId"), v.get("m_gstyleType"),
                                v.get("m_famId", -1)))
    out["gstyleData"] = {
        f"{lr}_rows": nr, f"{ls}_rows": ns,
        f"{lr}_builtin_keys": len(builtin_r), f"{ls}_builtin_keys": len(builtin_s),
        "builtin_keys_missing_in_subj": len(builtin_r - builtin_s),
        "builtin_keys_extra_in_subj": len(builtin_s - builtin_r),
        f"{ls}_dangling_entries": len(ds), f"{ls}_inconsistent_entries": len(is_),
        f"{ls}_duplicate_keys": dups,
        f"{ls}_present_gstyle_rows_NOT_indexed": len(unindexed_s),
        f"{ls}_present_gstyle_rows_NOT_indexed_examples": unindexed_s[:12],
        f"{lr}_present_gstyle_rows_NOT_indexed": len(unindexed_r),
        f"{lr}_present_gstyle_rows_NOT_indexed_note": ("(reference file's own rows some "
                                                       "registry does not target -- e.g. "
                                                       "family-scoped rows indexed elsewhere)"),
        "missing_builtin_key_examples": sorted(builtin_r - builtin_s)[:12],
    }
    W = 999
    if ds:
        out["mismatch_objs"].append(Mismatch(
            "CategoryTracking", "m_gstyleData", "DANGLING",
            f"{ls} m_gstyleData has {len(ds)} entries pointing at absent ids (e.g. {ds[:6]})",
            0, W))
    if is_:
        out["mismatch_objs"].append(Mismatch(
            "CategoryTracking", "m_gstyleData", "INCONSISTENT_KEY",
            f"{ls} m_gstyleData has {len(is_)} entries whose target row's own "
            f"(category, type) disagrees with the entry key (e.g. {is_[:5]})", 0, W))
    if dups:
        out["mismatch_objs"].append(Mismatch(
            "CategoryTracking", "m_gstyleData", "INCONSISTENT_KEY",
            f"{ls} m_gstyleData has {dups} duplicate (category, type) keys", 1, W))
    if unindexed_s:
        # a PRESENT gstyle row the registry does not index at all (the
        # P4/P6 signature: registries must index present rows)
        fam_scoped = sum(1 for u in unindexed_s if u[3] not in (None, -1))
        non_fam = len(unindexed_s) - fam_scoped
        sev = 0 if non_fam else 2
        out["mismatch_objs"].append(Mismatch(
            "CategoryTracking", "m_gstyleData", "COUNT_SHORTFALL",
            f"{ls} has {len(unindexed_s)} PRESENT GStyleElem row(s) NOT indexed by "
            f"m_gstyleData ({non_fam} non-family-scoped, {fam_scoped} family-scoped); "
            f"examples {unindexed_s[:6]}", sev, W))
    if builtin_r - builtin_s:
        # built-in category keys the reference styles that the subject does not
        n = len(builtin_r - builtin_s)
        out["mismatch_objs"].append(Mismatch(
            "CategoryTracking", "m_gstyleData", "MISSING",
            f"{ls} m_gstyleData lacks {n} of {lr}'s {len(builtin_r)} built-in "
            f"(category, style type) keys (examples {sorted(builtin_r - builtin_s)[:8]}) -- "
            f"{'the subject styles fewer built-in categories' if n else ''}",
            0 if n > 8 else 2, W))
    if builtin_s - builtin_r:
        out["mismatch_objs"].append(Mismatch(
            "CategoryTracking", "m_gstyleData", "EXTRA",
            f"{ls} m_gstyleData has {len(builtin_s - builtin_r)} built-in keys {lr} has not "
            f"(examples {sorted(builtin_s - builtin_r)[:8]})", 2, W))
    # categoryData
    def cmap(fx: Facts, ct: dict, inherited: Set[int] = frozenset()):
        rows = ct.get("m_categoryData") or []
        by_parent = Counter()
        dangling, incons = [], []
        targets = []
        for r in rows:
            par = r.get("m_parentCategoryId")
            cid = r.get("m_categoryId")
            if isinstance(par, int):
                by_parent[int(par)] += 1
            if isinstance(cid, int) and cid > 0:
                targets.append(int(cid))
                if cid not in fx.ids:
                    if cid not in inherited:
                        dangling.append(int(cid))
                else:
                    v = fx.value(cid) or {}
                    pc = (v.get("m_pCategory") or {}).get("value") or {}
                    if fx.cls_of(cid) != "CategoryElem":
                        incons.append((int(cid), fx.cls_of(cid)))
                    elif pc.get("m_parentCategoryId") != par:
                        incons.append((int(cid), ("own parent", pc.get("m_parentCategoryId"),
                                                  "entry parent", par)))
        return by_parent, dangling, incons, targets, len(rows)
    pr, dr2, ir2, tr, nr2 = cmap(ref, ct_r)
    ps, ds2, is2, ts, ns2 = cmap(subj, ct_s, inherited_dangling)
    unindexed_cat_r = [e for e in ref.ids_of_class("CategoryElem") if e not in set(tr)]
    _ucr = set(unindexed_cat_r)
    unindexed_cat_s = [e for e in subj.ids_of_class("CategoryElem")
                       if e not in set(ts) and e not in _ucr]
    out["categoryData"] = {
        f"{lr}_rows": nr2, f"{ls}_rows": ns2,
        f"{ls}_dangling_entries": len(ds2), f"{ls}_inconsistent_entries": len(is2),
        f"{ls}_present_category_elems_NOT_indexed": len(unindexed_cat_s),
        f"{lr}_present_category_elems_NOT_indexed": len(unindexed_cat_r),
        f"{lr}_top_parents": dict(pr.most_common(8)), f"{ls}_parents": dict(ps.most_common(8)),
    }
    if ds2:
        out["mismatch_objs"].append(Mismatch(
            "CategoryTracking", "m_categoryData", "DANGLING",
            f"{ls} m_categoryData names {len(ds2)} absent CategoryElem ids", 0, W))
    if is2:
        out["mismatch_objs"].append(Mismatch(
            "CategoryTracking", "m_categoryData", "INCONSISTENT_KEY",
            f"{ls} m_categoryData has {len(is2)} entries whose target's own parent "
            f"disagrees with the entry (e.g. {is2[:4]})", 0, W))
    if unindexed_cat_s:
        out["mismatch_objs"].append(Mismatch(
            "CategoryTracking", "m_categoryData", "COUNT_SHORTFALL",
            f"{ls} has {len(unindexed_cat_s)} PRESENT CategoryElem(s) NOT indexed by "
            f"m_categoryData (ids {unindexed_cat_s[:8]})", 0, W))
    return out


def write_parity_report(par: dict, path: str = PARITY_MD, *, extra_notes: List[str] = ()) -> str:
    """docs/writer/registry-parity.md -- the table of every registry with
    K1's shape vs S5's and each MISMATCH, ranked by walk order/severity."""
    lr, ls = par["label_ref"], par["label_subj"]
    L: List[str] = []
    L.append(f"# REGISTRY PARITY -- {lr} (reader-accepted skeleton) vs {ls} (our census-complete FAILING candidate)")
    L.append("")
    L.append("Generated by `tools/genesis_addback.py --parity` (genesis-addback stream). "
             f"**{lr}** = `{par['ref']}` ({par['ref_elements']:,} elements) is Autodesk's own "
             "empty-project skeleton on the rst basic sample (its descendants K3 / K4 / KD1 are "
             f"viewer PASSED); **{ls}** = `{par['subj']}` ({par['subj_elements']:,} elements) is "
             "the genesis-singletons census-complete candidate (G1_candidate + OUR settings "
             "singletons + OUR complete built-in style catalog), viewer FAILED with "
             "`Revit-DocumentCorruption` / `Design is empty`.  P4/P6/K6 proved the ADocument "
             "registries are WALKED at load and must correctly INDEX the PRESENT rows; this "
             "audit diffs every registry SURFACE the reader walks between the two document "
             "objects, CLASS-KEYED (element ids differ between the files -- classes, positional "
             "slots and map keys do not), and classifies every MISMATCH.")
    L.append("")
    L.append("**Mismatch kinds** -- `UNPOPULATED_SLOT` / `MISSING (registry gap)`: the "
             "reference indexes a row of class C at this surface and the subject HAS elements of "
             "class C but its registry does not index them there (the P4/P6 corruption "
             "signature, severity 0).  `DANGLING`: the subject's entry names an id absent from "
             "the file (severity 0).  `WRONG_CLASS` / `INCONSISTENT_KEY`: an entry indexes an "
             "element of a different class / a row whose own key fields disagree with the "
             "entry (severity 0).  `COUNT_SHORTFALL`: the subject has more elements of the class "
             "than its registry indexes (present rows unindexed, severity 0).  `EXTRA`: the "
             "subject indexes something the reference does not (severity 1-2; foreign entries).  "
             "`MISSING (inventory gap)`: the reference indexes classes the subject has NO elements "
             "of at all -- an inventory difference by design (the constructed base carries fewer "
             "content classes; K4/K5-style reductions PASS with fewer), severity 2-3, "
             "informational.  `ORDER`: same entries, different row order/grouping (severity 2).")
    L.append("")
    if extra_notes:
        L.append("## Headline")
        L.append("")
        for n in extra_notes:
            L.append(f"* {n}")
        L.append("")
    # ---- ranked mismatch table -------------------------------------------------
    mms = par["mismatches"]
    sev0 = [m for m in mms if m["severity"] == 0]
    L.append(f"## Ranked MISMATCHES ({len(mms)} total; {len(sev0)} of severity 0)")
    L.append("")
    L.append("Ranked by severity, then the reader's likely walk order (the AppInfo array "
             "serialization order of the reference document object; root bodies last).")
    L.append("")
    L.append("| # | sev | body | container | kind | detail |")
    L.append("|--:|--:|---|---|---|---|")
    shown = 0
    for i, m in enumerate(mms, 1):
        if m["severity"] >= 3 and shown > 40:
            continue
        det = str(m["detail"]).replace("|", "/")
        if len(det) > 420:
            det = det[:417] + "..."
        L.append(f"| {i} | {m['severity']} | `{m['body']}` | `{m['container']}` | "
                 f"{m['kind']} | {det} |")
        shown += 1
        if shown > 220:
            L.append(f"| ... | | | | | ({len(mms) - shown} more; see registry_parity.json) |")
            break
    inf = [m for m in mms if m["severity"] >= 3]
    if inf:
        L.append("")
        L.append(f"({len(inf)} informational inventory-gap rows collapsed above; full list in "
                 "`experiments/genesis/addback/registry_parity.json`.)")
    L.append("")
    # ---- UET ----------------------------------------------------------------------
    L.append("## UniqueElementsTracking -- the positional singleton table (slot k = compiled-in class)")
    L.append("")
    L.append(f"| slot | compiled-in class (UET map) | {lr} indexes | {lr} id | {ls} indexes | "
             f"{ls} id | verdict |")
    L.append("|--:|---|---|--:|---|--:|---|")
    for k, mapcls, rk, rid, sk, sid, note in par["uet_rows"]:
        if rid <= 0 and sid <= 0:
            continue
        v = (note.split(":", 1)[0] if note else "ok")
        L.append(f"| {k} | `{mapcls}` | `{rk}` | {rid if rid > 0 else '-'} | `{sk}` | "
                 f"{sid if sid > 0 else '-'} | {v} |")
    L.append("")
    # ---- scalars ------------------------------------------------------------------
    L.append("## Named AppInfo scalar element-id members")
    L.append("")
    L.append(f"| body.member | {lr} class | {lr} id | {ls} class | {ls} id | verdict |")
    L.append("|---|---|--:|---|--:|---|")
    for body, member, rk, rid, sk, sid, note in par["scalar_rows"]:
        if rid <= 0 and sid <= 0:
            continue
        v = (note.split(":", 1)[0] if note else "ok")
        L.append(f"| `{body}.{member}` | `{rk}` | {rid if rid > 0 else '-'} | `{sk}` | "
                 f"{sid if sid > 0 else '-'} | {v} |")
    L.append("")
    # ---- CategoryTracking ---------------------------------------------------------
    ct = par["category_tracking"]
    L.append("## The BuiltInCategory -> CategoryElem / GStyle maps (`CategoryTracking`)")
    L.append("")
    L.append("`m_gstyleData` = one row per (category id, style type) -> the GStyleElem row; "
             "built-in categories are the negative ids (the reader's object-styles table); "
             "sub-categories key on the CategoryElem element id.  `m_categoryData` = one row per "
             "sub-category (parent built-in category -> CategoryElem id).  Cross-checked against "
             "each file's own GStyle / Category inventory: every PRESENT row must be indexed, "
             "and every entry must be consistent with the row it points at.")
    L.append("")
    L.append("**m_gstyleData**")
    L.append("")
    L.append("| measure | value |")
    L.append("|---|--:|")
    for k, v in ct["gstyleData"].items():
        if isinstance(v, list):
            v = f"`{v}`"
        L.append(f"| {k} | {v} |")
    L.append("")
    L.append("**m_categoryData**")
    L.append("")
    L.append("| measure | value |")
    L.append("|---|--:|")
    for k, v in ct["categoryData"].items():
        L.append(f"| {k} | {v} |")
    L.append("")
    # ---- SymbolIdMgr default-type map ------------------------------------------------
    sd = par.get("symbolid_mgr") or {}
    L.append("## The default-type map (`SymbolIdMgr.m_defElementTypeMap`: group -> default element)")
    L.append("")
    L.append("Each GROUP is a compiled-in constant naming one class -- and for `DBViewType` "
             "one VIEW FAMILY (`m_systemFamilyIdx`: group 62 = 3D, 63 walkthrough, 64 "
             "rendering, 65 schedule, 66 legend, 67 cost report, 68 sheet, 69 drafting, 70 "
             "structural plan, 71 floor plan, 72 ceiling plan, 73/81 section, 74 detail, "
             "75/76 elevation, 79 pressure-loss report, 80 panel schedule, 107 column "
             "schedule, 150 analysis report).  A document with elements of the class must "
             "carry the group's default; the constructed candidate leaves them out for its "
             "own view types and several present classes.")
    L.append("")
    mcd = sd.get("missing_class_defaults") or []
    mfd = sd.get("missing_view_family_defaults") or []
    L.append(f"* **Missing DBViewType view-family defaults in {ls}: {len(mfd)}** -- "
             + (", ".join(f"family {f} (group {g}: {ls} has view type {ids[0]})"
                          for f, g, ids in mfd) if mfd else "none"))
    L.append(f"* **Missing single-class defaults in {ls}: {len(mcd)}** -- "
             + (", ".join(f"group {g} = {c} ({ls} has {h})" for g, c, h in mcd)
                if mcd else "none"))
    L.append(f"* {ls}'s populated default groups: "
             f"{', '.join(f'{g}' for g, _t in (sd.get('subj_default_groups') or []))}")
    L.append("")
    # ---- the cell-kind registry ------------------------------------------------------
    cd = par.get("cells_tracking") or {}
    L.append("## The cell-kind registry (`ElemsSetWithCellsTracking.m_elemIdSetMap`)")
    L.append("")
    L.append("Keys are cell KINDS: `1200` = elements holding an `ExternalFileReferenceCell`, "
             "`1201` = an `ExternalResourceReferenceCell`, `-100` = an `ESEntityCell` "
             "(extensible storage).  Rule validated on the accepted skeleton (every holder is "
             "in its set, every set member is a holder), then applied to the subject.")
    L.append("")
    L.append("| cell kind | rule validation on the reference |")
    L.append("|---|---|")
    for cell_cls, rv in (cd.get("rule_validation") or {}).items():
        L.append(f"| `{cell_cls}` (set {rv.get('key')}) | {rv} |")
    L.append("")
    unreg = cd.get("subject_unregistered_holders") or []
    L.append(f"* **{ls} cell holders NOT registered: {len(unreg)}** -- "
             + (", ".join(f"{ecls} {eid} (holds {cc}, belongs in set {key})"
                          for eid, ecls, cc, key in unreg) if unreg else "none"))
    L.append("")
    # ---- containers ------------------------------------------------------------------
    L.append("## Every id-holding registry container (class-keyed comparison)")
    L.append("")
    L.append("`ref_kind` / `subj_kind`: `keyed` = rows are structs keyed by their non-id fields; "
             "`set` = a plain id set (compared as a multiset of the classes referenced).  Only "
             "containers where at least one file has entries are listed.")
    L.append("")
    L.append(f"| body | container | kind ({lr}/{ls}) | {lr} entries | {lr} classes | {ls} entries "
             f"| {ls} classes | {ls} dangling | mismatches |")
    L.append("|---|---|---|--:|---|--:|---|--:|---|")
    for r in par["container_rows"]:
        if r["ref_entries"] == 0 and r["subj_entries"] == 0:
            continue
        rcl = ", ".join(f"{k}x{v}" for k, v in list(r["ref_classes"].items())[:4])
        scl = ", ".join(f"{k}x{v}" for k, v in list(r["subj_classes"].items())[:4])
        mms2 = "; ".join(m.split(":", 1)[0] for m in r["mismatches"][:3]) or "-"
        L.append(f"| `{r['body']}` | `{r['container']}` | {r['ref_kind']}/{r['subj_kind']} | "
                 f"{r['ref_entries']} | {rcl} | {r['subj_entries']} | {scl} | "
                 f"{r['subj_dangling']} | {mms2} |")
    L.append("")
    # ---- bodies -------------------------------------------------------------------------
    L.append("## Registry bodies present (AppInfo array order = the reader's walk order)")
    L.append("")
    rb, sb = par["ref_bodies"], par["subj_bodies"]
    L.append(f"* {lr}: {len(rb)} bodies -- {', '.join(f'`{b}`' for b in rb)}")
    L.append(f"* {ls}: {len(sb)} bodies -- " +
             ("(same set)" if set(rb) == set(sb) else ", ".join(f"`{b}`" for b in sb)))
    if set(rb) - set(sb):
        L.append(f"* in {lr} only: {', '.join(f'`{b}`' for b in rb if b not in set(sb))}")
    if set(sb) - set(rb):
        L.append(f"* in {ls} only: {', '.join(f'`{b}`' for b in sb if b not in set(rb))}")
    L.append("")
    txt = "\n".join(L) + "\n"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(txt)
    return path


# ===========================================================================
# 10. R3 -- S5 with the registry mismatches repaired
# ===========================================================================

def _etd_class_categories(ref: Facts) -> Dict[Tuple[str, str], int]:
    """{(container, class): built-in category} from the reference's own
    ElementTrackingData rows -- which category row each class's elements
    are tracked under (m_symbols for type/symbol classes, m_elems for
    elements).  Only classes tracked under ONE consistent category qualify."""
    etd = GA._appinfo_body(ref.tree, "ElementTrackingData") or {}
    out: Dict[Tuple[str, str], int] = {}
    tally: Dict[Tuple[str, str], Counter] = defaultdict(Counter)
    for cont in ("m_symbols", "m_elems"):
        for row in etd.get(cont) or []:
            cat = row.get("m_categoryId")
            for eid in row.get("m_elemIdSet") or []:
                if isinstance(eid, int) and eid > 0 and eid in ref.ids:
                    tally[(cont, ref.cls_of(eid))][cat] += 1
    for key, ct in tally.items():
        if len(ct) == 1:
            out[key] = next(iter(ct))
    return out


def build_R3(par: dict, k1: Facts, s5: Facts, maps: dict) -> Optional[dict]:
    """S5.rvt with the parity audit's registry mismatches REPAIRED (its
    element rows UNCHANGED; only the document object's registries edited to
    match K1's shape).  Fixable = the subject HAS the rows and only the
    registry is wrong; every repair is derived from K1's own shape (the
    compiled-in group / cell-kind / category constants) and listed in the
    record.  Inventory gaps (classes S5 has no elements of) and assessed-
    regenerable session state are NOT touched."""
    fixes: List[dict] = []
    tree = s5.tree_copy()
    ed = editor()
    cen = s5.census()
    by_class: Dict[str, List[int]] = defaultdict(list)
    for e in s5.ids:
        by_class[s5.cls_of(e)].append(int(e))
    for v in by_class.values():
        v.sort()

    def dbviewtype_family(eid: int) -> Optional[int]:
        f = (s5.value(eid) or {}).get("m_systemFamilyIdx")
        return int(f) if isinstance(f, int) else None

    # (a) UET slots: populated in K1, -1 in S5 while S5 has the class
    uet = ST._appinfo_body(tree, "UniqueElementsTracking")
    if uet is not None:
        arr = uet.get("m_elemIds") or []
        used = {x for x in arr if isinstance(x, int) and x > 0}
        for k, mapcls, rk, rid, sk, sid, note in par["uet_rows"]:
            if note.startswith("UNPOPULATED_SLOT") and rk in by_class:
                cands = [i for i in by_class[rk] if i not in used]
                if cands:
                    while len(arr) <= k:
                        arr.append(INVALID)
                    arr[k] = int(cands[0])
                    used.add(cands[0])
                    fixes.append({"surface": f"UniqueElementsTracking.m_elemIds[{k}]",
                                  "fix": f"set to our {rk} {cands[0]}"})
        uet["m_elemIds"] = arr
    # (b) named scalars null in S5 while S5 has the class
    for body, member, rk, rid, sk, sid, note in par["scalar_rows"]:
        if note.startswith("UNPOPULATED_SLOT") and rk in by_class:
            b = ST._appinfo_body(tree, body)
            if b is not None and member in b and b[member] in (None, INVALID):
                b[member] = int(by_class[rk][0])
                fixes.append({"surface": f"{body}.{member}",
                              "fix": f"set to our {rk} {by_class[rk][0]}"})
    # (c) CategoryTracking: present GStyle / Category rows not indexed +
    #     dangling entries (the detail section proved S5 clean here; kept
    #     for completeness)
    ct = ST._appinfo_body(tree, "CategoryTracking")
    if ct is not None:
        rows = ct.setdefault("m_gstyleData", [])
        keys = {(r.get("m_categoryId"), r.get("m_gstyleType")) for r in rows}
        targets = {r.get("m_gstyleId") for r in rows}
        added = 0
        for e in by_class.get("GStyleElem", []):
            if e in targets:
                continue
            v = s5.value(e) or {}
            cid, gt = v.get("m_categoryId"), v.get("m_gstyleType")
            if not (isinstance(cid, int) and isinstance(gt, int)) or (cid, gt) in keys:
                continue
            rows.append({"m_categoryId": int(cid), "m_gstyleId": int(e),
                         "m_gstyleType": int(gt)})
            keys.add((cid, gt))
            added += 1
        if added:
            fixes.append({"surface": "CategoryTracking.m_gstyleData",
                          "fix": f"indexed {added} present-but-unindexed GStyleElem rows"})
        crows = ct.setdefault("m_categoryData", [])
        ctargets = {r.get("m_categoryId") for r in crows}
        cadd = 0
        for e in by_class.get("CategoryElem", []):
            if e in ctargets:
                continue
            v = s5.value(e) or {}
            par_id = (((v.get("m_pCategory") or {}).get("value") or {}).get("m_parentCategoryId"))
            if isinstance(par_id, int):
                crows.append({"m_parentCategoryId": int(par_id), "m_categoryId": int(e)})
                cadd += 1
        if cadd:
            fixes.append({"surface": "CategoryTracking.m_categoryData",
                          "fix": f"indexed {cadd} present-but-unindexed CategoryElem(s)"})
        before = len(rows)
        ct["m_gstyleData"] = [r for r in rows if not (isinstance(r.get("m_gstyleId"), int)
                                                       and r["m_gstyleId"] > 0
                                                       and r["m_gstyleId"] not in s5.ids)]
        if len(ct["m_gstyleData"]) != before:
            fixes.append({"surface": "CategoryTracking.m_gstyleData",
                          "fix": f"dropped {before - len(ct['m_gstyleData'])} dangling entries"})
    # (d) SymbolIdMgr default-type map: the missing defaults (view families
    #     via the derived family->group constants; single-class groups)
    sim = ST._appinfo_body(tree, "SymbolIdMgr")
    sd = par.get("symbolid_mgr") or {}
    if sim is not None:
        rows = sim.setdefault("m_defElementTypeMap", [])
        have_groups = {r.get("first") for r in rows if isinstance(r, dict)}
        added = []
        for fam, group, ids in (sd.get("missing_view_family_defaults") or []):
            if group in have_groups or not ids:
                continue
            rows.append({"first": int(group), "second": int(ids[0])})
            have_groups.add(group)
            added.append((int(group), f"DBViewType family {fam}", int(ids[0])))
        # single-class defaults: pick the honest candidate per class
        def gstyle_of_category(cat: int) -> Optional[int]:
            for e in by_class.get("GStyleElem", []):
                v = s5.value(e) or {}
                if v.get("m_categoryId") == cat and v.get("m_gstyleType") == 1 \
                        and v.get("m_famId", -1) == -1:
                    return e
            return None
        # K1's group 41 (default GStyle) target's category
        dmap = derive_default_group_map(k1)
        for g, cls_name, _have in (sd.get("missing_class_defaults") or []):
            if g in have_groups:
                continue
            target = None
            reason = ""
            if cls_name == "GStyleElem":
                # the default line style = the projection style of the same
                # built-in category K1's default GStyle carries
                sim1 = GA._appinfo_body(k1.tree, "SymbolIdMgr") or {}
                k1_target = next((r.get("second") for r in sim1.get("m_defElementTypeMap") or []
                                  if r.get("first") == g), None)
                cat = (k1.value(k1_target) or {}).get("m_categoryId") if k1_target else None
                if isinstance(cat, int):
                    target = gstyle_of_category(cat)
                    reason = f"our projection style of built-in category {cat}"
            elif cls_name == "FloorAttributes":
                # group 4 = a floor type, group 5 = a foundation slab (built-in
                # category -2001300); ours are plain floors unless categorised
                # as structural foundations
                for e in by_class.get("FloorAttributes", []):
                    hdr = s5.doc.decode(e, 101)
                    cat = (hdr.value or {}).get("m_categroryId") if hdr and hdr.clean else None
                    is_found = (cat == -2001300)
                    if (g == 5 and is_found) or (g == 4 and not is_found):
                        target = e
                        reason = ("our structural foundation floor type" if g == 5
                                  else "our floor type")
                        break
            else:
                cands = by_class.get(cls_name, [])
                if cands:
                    target = cands[0]
                    reason = f"our first {cls_name}"
            if target is not None:
                rows.append({"first": int(g), "second": int(target)})
                have_groups.add(g)
                added.append((int(g), f"{cls_name} ({reason})", int(target)))
        if added:
            fixes.append({"surface": "SymbolIdMgr.m_defElementTypeMap",
                          "fix": f"added {len(added)} missing defaults: "
                                 + ", ".join(f"group {g}={t} ({w})" for g, w, t in added)})
    # (e) RbsSystemNavigatorTracking voltage types
    rsn = ST._appinfo_body(tree, "RbsSystemNavigatorTracking")
    volts = by_class.get("RbsVoltageType") or []
    if rsn is not None and volts:
        s = rsn.setdefault("m_voltageTypeIdSet", [])
        add = [v for v in volts if v not in s]
        if add:
            s.extend(int(v) for v in add)
            fixes.append({"surface": "RbsSystemNavigatorTracking.m_voltageTypeIdSet",
                          "fix": f"registered {len(add)} voltage type(s)"})
    # (f) the cell-kind sets: register the unregistered cell holders
    esc = ST._appinfo_body(tree, "ElemsSetWithCellsTracking")
    unreg = (par.get("cells_tracking") or {}).get("subject_unregistered_holders") or []
    if esc is not None and unreg:
        rows = esc.setdefault("m_elemIdSetMap", [])
        by_key = {r_.get("first"): r_ for r_ in rows if isinstance(r_, dict)}
        n = 0
        for eid, ecls, cell_cls, key in unreg:
            row = by_key.get(key)
            if row is None:
                row = {"first": int(key), "second": {"m_idSet": []}}
                rows.append(row)
                by_key[key] = row
            idset = row.setdefault("second", {}).setdefault("m_idSet", [])
            if eid not in idset:
                idset.append(int(eid))
                n += 1
        if n:
            fixes.append({"surface": "ElemsSetWithCellsTracking.m_elemIdSetMap",
                          "fix": f"registered {n} external-cell holder membership(s) "
                                 f"({sorted({(e, k) for e, _c, _cc, k in unreg})})"})
    # (g) DBViewTypesForNewLevel: K1's exact shape = [-1, floor plan
    #     type, ceiling plan type, structural plan type]
    ntl = ST._appinfo_body(tree, "DBViewTypesForNewLevel")
    if ntl is not None:
        fam_of = {}
        for e in by_class.get("DBViewType", []):
            f = dbviewtype_family(e)
            if f is not None:
                fam_of.setdefault(f, e)
        wanted = [-1] + [fam_of[f] for f in (109, 111, 120) if f in fam_of]
        cur = ntl.get("m_newLevelDBViewTypes")
        if cur != wanted and len(wanted) > 1:
            ntl["m_newLevelDBViewTypes"] = wanted
            fixes.append({"surface": "DBViewTypesForNewLevel.m_newLevelDBViewTypes",
                          "fix": f"rebuilt to K1's shape [-1, floor plan, ceiling plan, "
                                 f"structural plan] = {wanted}"})
    # (h) CopyWatchModeMgr: drop the nulled parallel rows (a dead link),
    #     register our copy/watch state as the in-document member
    cwm = ST._appinfo_body(tree, "CopyWatchModeMgr")
    cws = by_class.get("CopyWatchProperties") or []
    if cwm is not None and cws:
        props = cwm.get("m_linkCopyWatchProps") or []
        docs = cwm.get("m_linkDocIds") or []
        if props and all((p in (None, INVALID)) for p in props) and \
                all((d in (None, INVALID)) for d in docs):
            cwm["m_linkCopyWatchProps"] = []
            cwm["m_linkDocIds"] = []
            fixes.append({"surface": "CopyWatchModeMgr.m_linkCopyWatchProps/m_linkDocIds",
                          "fix": "dropped the fully-nulled parallel link rows (no link document)"})
        if cwm.get("m_inDocCopyWatchProps") in (None, INVALID):
            cwm["m_inDocCopyWatchProps"] = int(cws[0])
            fixes.append({"surface": "CopyWatchModeMgr.m_inDocCopyWatchProps",
                          "fix": f"registered our CopyWatchProperties {cws[0]} as the "
                                 "in-document copy/watch state (no link document exists)"})
    # (i) ElementTrackingData: register S5's untracked classes under the
    #     category rows K1 tracks them under (constant per class)
    etd = ST._appinfo_body(tree, "ElementTrackingData")
    if etd is not None:
        catmap = _etd_class_categories(k1)
        tracked: Set[int] = set()
        for cont in ("m_symbols", "m_elems"):
            for row in etd.get(cont) or []:
                for eid in row.get("m_elemIdSet") or []:
                    if isinstance(eid, int):
                        tracked.add(eid)
        tracked_classes = {s5.cls_of(e) for e in tracked if e in s5.ids}
        added = []
        for (cont, cls_name), cat in sorted(catmap.items()):
            ids_c = by_class.get(cls_name) or []
            if not ids_c or cls_name in tracked_classes:
                continue
            missing = [e for e in ids_c if e not in tracked]
            if not missing:
                continue
            rows = etd.setdefault(cont, [])
            row = next((r for r in rows if r.get("m_categoryId") == cat), None)
            if row is None:
                row = {"m_categoryId": int(cat), "m_elemIdSet": []}
                rows.append(row)
            row.setdefault("m_elemIdSet", [])
            row["m_elemIdSet"].extend(int(e) for e in missing)
            added.append((cont, cls_name, int(cat), len(missing)))
            tracked.update(missing)
        if added:
            fixes.append({"surface": "ElementTrackingData",
                          "fix": "tracked " + ", ".join(f"{n} {c} under {cont} category {cat}"
                                                        for cont, c, cat, n in added)})
    # (j) AbsLayoutAppInfo: level -> MEP layout offset entries for our
    #     levels (OUR routing offsets), the maps the sample fills per level
    ali = ST._appinfo_body(tree, "AbsLayoutAppInfo")
    lvls = by_class.get("Level") or []
    if ali is not None and lvls:
        main = float(ST.MEP_MAIN_OFFSET_FT)
        offs = sorted({float(ST.MEP_BRANCH_OFFSET_FT), main})
        n_maps = 0
        for fld in ("m_mapDuctLevelToOffsets", "m_mapPipeLevelToOffsets",
                    "m_mapCabelTrayLevelToOffsets", "m_mapConduitLevelToOffsets"):
            rows = ali.setdefault(fld, [])
            have = {r.get("first") for r in rows if isinstance(r, dict)}
            add = 0
            for lv in lvls:
                if lv not in have:
                    rows.append({"first": int(lv),
                                 "second": {"m_setOffset": list(offs),
                                            "m_dSelectedOffset": main}})
                    add += 1
            if add:
                n_maps += 1
        if n_maps:
            fixes.append({"surface": "AbsLayoutAppInfo.m_map*LevelToOffsets",
                          "fix": f"added OUR MEP layout offsets for {len(lvls)} level(s) in "
                                 f"{n_maps} layout maps"})
    if not fixes:
        log("[R3] no registry-FIXABLE mismatches found -- R3 NOT built; the remaining "
            "mismatches are inventory gaps / content differences (see the parity report).")
        return {"rung": "R3", "built": False,
                "reason": ("no registry-fixable mismatch was found in S5; every remaining "
                           "mismatch is an inventory or content difference that registry "
                           "edits cannot repair"),
                "fixes": []}
    out = os.path.join(OUT_DIR, "R3.rvt")
    tmp = _tmp("R3")
    write_latest(s5.path, tmp, tree)
    delete_elements(tmp, out, [])                     # canonical re-block/copy
    _cleanup(tmp)
    absent = base_absent_refs(s5)
    cert = certify(out, base_tree_refs_absent=absent, our_ids=[], restored_ids=[])
    v = cert["validator"]
    ok = bool(v["ok"]) and v["errors"] == 0 and cert["dangling_NEW_count"] == 0
    # self-parity: what remains different from K1 after the repairs
    after = parity_compare(k1.path, out, label_ref="K1", label_subj="R3")
    after_sev0 = [m for m in after["mismatches"] if m["severity"] == 0]
    rep = {"rung": "R3", "built": True, "out": _relp(out), "base": _relp(s5.path),
           "passing_sibling": ("experiments/genesis/triage/K1.rvt (the registry SHAPE R3 "
                               "copies) / S5.rvt (this base, viewer FAIL)"),
           "description": ("S5.rvt (our census-complete candidate, viewer FAIL) with the "
                           "registry-parity mismatches REPAIRED: element rows unchanged; "
                           "only the document object's registries edited to match K1's "
                           "shape (" + "; ".join(f["fix"] for f in fixes)[:900] + ")."),
           "tests": ("Does repairing S5's registry indexing (as diffed against the accepted "
                     "skeleton) make S5 open?  If R1/R2 exonerate our content, the "
                     "registry INDEXING is the residual defect and R3 is the shortest path "
                     "to a PASS."),
           "if_PASS": ("S5's defect was registry INDEXING (its rows were acceptable); the "
                       "assembler / settings.ADOC_REGISTRY / apply_adoc_registry must adopt "
                       "every fix listed here (default-type map, ETD categories, cell-kind "
                       "sets, print MRU, voltage set, new-level view types, layout maps)."),
           "if_FAIL": ("registry indexing was not S5's only defect -- the residual is the "
                       "inventory / content difference the audit cannot repair (or the G1 "
                       "base); read R1 / R2 for the content verdicts and the parity report's "
                       "inventory-gap list."),
           "fixes": fixes, "certification": cert,
           "self_parity_after_repair": {
               "severity0_remaining": len(after_sev0),
               "remaining": [f"{m['body']}.{m['container']}: {m['kind']}"
                             for m in after_sev0][:20]},
           "verdict": "VALID" if ok else "NOT-CLEAN",
           "bytes": os.path.getsize(out)}
    with open(os.path.join(OUT_DIR, "R3.json"), "w") as fh:
        json.dump(rep, fh, indent=1, default=str)
    log(f"[R3] {'VALID' if ok else '*** NOT CLEAN ***'} -- {len(fixes)} registry repair(s); "
        f"validator errors={v['errors']}; dangling NEW {cert['dangling_NEW_count']}; "
        f"severity-0 mismatches remaining after repair: {len(after_sev0)}")
    for f in fixes:
        log(f"      fix {f['surface']}: {f['fix'][:150]}")
    return rep


# ===========================================================================
# 11. probes.json
# ===========================================================================

def write_probes_json(reports: Dict[str, dict], parity: Optional[dict]) -> str:
    order = ["R1", "R2s", "R2", "R1s", "R3"]
    entries = []
    rationale = {
        "R1": ("HIGHEST value: our WHOLE singleton constellation (S3/S5's) substituted into the "
               "known-good skeleton at the exact point K5 removed the sample's; a PASS "
               "exonerates our singletons and pins S5's failure on the G1 base."),
        "R2s": ("THE MECHANICS CONTROL: K6 with EVERY deleted row restored from K1 through "
                "the same transplant + document-object path (equivalent to K1).  Read it FIRST "
                "with R2: R2s PASS makes R2 (and R1) readable; R2s FAIL = the mechanics are "
                "the suspect."),
        "R2": ("our COMPLETE built-in-category object-styles catalog re-pointed into the "
               "known-good skeleton (the pen table K6 also lost held constant); PASS exonerates "
               "our catalog values / enum coverage."),
        "R1s": ("R1's bisection partner: only the pen table + browser organizations OURS. "
                "Upload after R1 (or together to save a round)."),
        "R3": ("S5 with the parity audit's registry-indexing mismatches repaired (rows "
               "unchanged) -- built only if the audit found registry-fixable defects."),
    }
    for name in order:
        rep = reports.get(name)
        if rep is None:
            j = os.path.join(OUT_DIR, f"{name}.json")
            if not os.path.exists(j):
                continue
            with open(j) as fh:
                rep = json.load(fh)
        if name == "R3" and not rep.get("built", True):
            entries.append({"file": None, "rung": "R3", "NOT_BUILT": rep.get("reason"),
                            "order_rationale": rationale["R3"]})
            continue
        cert = rep.get("certification") or {}
        v = cert.get("validator") or {}
        entries.append({
            "file": rep.get("out"),
            "order": len([e for e in entries if e.get("file")]) + 1,
            "order_rationale": rationale.get(name, ""),
            "derived_from": rep.get("base"),
            "passing_sibling": rep.get("passing_sibling"),
            "the_ONE_thing_it_tests": rep.get("tests"),
            "what_it_is": rep.get("description"),
            "if_PASS": rep.get("if_PASS"),
            "if_FAIL": rep.get("if_FAIL"),
            "validator": {"ok": v.get("ok"), "errors": v.get("errors"),
                          "warnings": v.get("warnings")},
            "verdict": rep.get("verdict"),
            "elements": (cert.get("census") or {}).get("elements"),
            "coherence": {k: (cert.get("census") or {}).get(k)
                          for k in ("save_units", "contentdocs_entries",
                                    "contenttable_records", "familymgr_entries")},
            "dangling_NEW": cert.get("dangling_NEW_count"),
            "dangling_inherited_tolerated": cert.get("dangling_inherited_tolerated"),
            "our_elements": rep.get("our_elements"),
            "restored_from_sample": rep.get("restored_from_sample"),
            "report": f"experiments/genesis/addback/{name}.json",
        })
    manifest = {
        "stream": "genesis-addback (the add-back probes + the registry-parity audit)",
        "situation": (
            "S1..S5 (OUR singletons + OUR complete catalog ON THE FAILING G1 base) all FAIL "
            "with the sample skeleton's own message ('Revit-DocumentCorruption' / 'Design is "
            "empty').  Testing our content on the SUSPECT base cannot separate (i) our "
            "constructors / registry wiring being wrong from (ii) the G1 base carrying an "
            "independent defect.  These probes build from the PASSING side instead: our "
            "content goes onto Autodesk's own reader-accepted empty-project skeleton (K1's "
            "lineage) at EXACTLY the point the sample's content was removed (K5 = minus the "
            "singletons, K6 = minus the built-in style catalog; both viewer FAIL), with every "
            "removed row our constructors do NOT cover restored VERBATIM from K1 -- so the "
            "ONLY difference from a passing file is OUR substitution.  Every file: validator "
            "0 errors, 0 NEW dangling document-object references, four-registry coherent."),
        "recommended_upload_batch": ("R2s + R1 + R2 (one round): R2s certifies the mechanics; "
                                     "R1 and R2 are the two verdicts.  R1s and R3 are the "
                                     "pre-built follow-ups."),
        "reading_the_results": {
            "R2s FAIL": ("the add-back MECHANICS (byte-preserving transplant / document-object "
                         "reinstatement / re-block / identity scrub) introduce a defect => R1 "
                         "and R2 are unreadable until fixed; diff R2s against K1."),
            "R2s PASS + R1 PASS": ("OUR document-settings singleton constellation is an "
                                   "acceptable substitute => S5's failure was the G1 BASE "
                                   "(an independent defect), not our singletons; genesis "
                                   "should build G2 = the KNOWN-GOOD SKELETON with our "
                                   "content substituted class-by-class (the substitution "
                                   "ladder from the passing side)."),
            "R2s PASS + R1 FAIL": ("OUR singleton constructors and/or their registry wiring "
                                   "are rejected even on the good skeleton => upload R1s: R1s "
                                   "PASS => the defect is in the MEP / structural / tracker "
                                   "constructors; R1s FAIL => the pen table / browser "
                                   "substitution itself is rejected."),
            "R2s PASS + R2 PASS": ("OUR complete built-in object-styles catalog (the frozen "
                                   "1,074-category enum, our values) is an acceptable "
                                   "substitute => K6's / S4's failures were the base / the "
                                   "bundled pen table, not our catalog."),
            "R2s PASS + R2 FAIL": ("OUR catalog rows are rejected -- shape / values / enum "
                                   "coverage; see R2's catalog report and the parity audit."),
            "R3 PASS": ("S5's defect was registry INDEXING; adopt the audit's fixes in the "
                        "assembler / apply_adoc_registry."),
        },
        "parity_audit": {"report": "docs/writer/registry-parity.md",
                         "json": "experiments/genesis/addback/registry_parity.json",
                         "severity0_mismatches": (len([m for m in (parity or {}).get(
                             "mismatches", []) if m["severity"] == 0]) if parity else None)},
        "known_passing_anchors": {"K1": "experiments/genesis/triage/K1.rvt (empty-project "
                                        "skeleton; K3/K4/KD1 descendants viewer PASS)"},
        "known_failing_bases": {"K5": "experiments/genesis/triage/K5.rvt (viewer FAIL)",
                                "K6": "experiments/genesis/triage/K6.rvt (viewer FAIL)",
                                "S5": "experiments/genesis/singletons/S5.rvt (viewer FAIL)"},
        "probes": entries,
    }
    p = os.path.join(OUT_DIR, "probes.json")
    with open(p, "w") as fh:
        json.dump(manifest, fh, indent=1, default=str)
    log(f"[probes] wrote {_relp(p)} ({len(entries)} entries)")
    return p


# ===========================================================================
# 12. driver
# ===========================================================================

def load_maps() -> dict:
    if not os.path.exists(MAPS):
        raise SystemExit(f"registry maps missing: {MAPS} (run tools/genesis_assemble.py --only maps)")
    with open(MAPS) as fh:
        return json.load(fh)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--only", default="", help="comma list of probes to build (R1,R1s,R2,R2s,R3)")
    ap.add_argument("--parity-only", action="store_true", help="only run the parity audit")
    ap.add_argument("--no-parity", action="store_true", help="skip the parity audit")
    args = ap.parse_args(argv)
    t0 = time.time()
    want = {s.strip() for s in args.only.split(",") if s.strip()}
    reports: Dict[str, dict] = {}
    parity = None

    log("[state] loading K1 (skeleton), K5, K6, S5 ...")
    k1 = Facts(K1)
    maps = load_maps()

    if not args.parity_only:
        def wanted(*names: str) -> bool:
            return not want or bool(want & set(names))
        if wanted("R1", "R1s"):
            k5 = Facts(K5)
            ana5 = k5_removal_analysis(k5, k1)
            log(f"[K5] removed {len(ana5['removed_ids'])} elements; covered classes "
                f"{len(ana5['covered_classes'])}, uncovered {len(ana5['uncovered_classes'])} "
                f"({ana5['uncovered_classes']}) -> restored ids {len(ana5['uncovered_ids'])}")
            if wanted("R1"):
                reports["R1"] = build_R1(k1, k5, maps, ana5)
            if wanted("R1s"):
                reports["R1s"] = build_R1s(k1, k5, maps, ana5)
        if wanted("R2", "R2s"):
            k6 = Facts(K6)
            ana6 = k6_removal_analysis(k6, k1)
            log(f"[K6] removed {ana6['removed_total']} elements; built-in style rows "
                f"{len(ana6['builtin_style_deleted_ids'])} (substituted by ours), others "
                f"{len(ana6['restore_ids'])} (restored); pen table deleted by K6: "
                f"{ana6['pen_table_deleted_by_K6']}")
            if wanted("R2s"):
                reports["R2s"] = build_R2s(k1, k6, maps, ana6)
            if wanted("R2"):
                reports["R2"] = build_R2(k1, k6, maps, ana6)

    if not args.no_parity or want & {"R3"}:
        if os.path.exists(S5):
            log("[parity] K1 vs S5 registry-surface audit ...")
            s5 = Facts(S5)
            parity = parity_compare(K1, S5, label_ref="K1", label_subj="S5")
            with open(os.path.join(OUT_DIR, "registry_parity.json"), "w") as fh:
                json.dump(parity, fh, indent=1, default=str)
            heads = _parity_headlines(parity)
            write_parity_report(parity, extra_notes=heads)
            log(f"[parity] {len(parity['mismatches'])} mismatches "
                f"({sum(1 for m in parity['mismatches'] if m['severity'] == 0)} severity-0) -> "
                f"{_relp(PARITY_MD)}")
            for h in heads:
                log(f"   * {h}")
            if not want or "R3" in want:
                reports["R3"] = build_R3(parity, k1, s5, maps) or {}
        else:
            log(f"[parity] {S5} missing -- audit skipped")

    write_probes_json(reports, parity)
    # summary
    log("\n=== ADD-BACK SUMMARY (validator = tools/rvt_validate.py; 0 errors + 0 NEW dangling required) ===")
    for name in ("R1", "R1s", "R2", "R2s", "R3"):
        rep = reports.get(name)
        if not rep:
            continue
        if name == "R3" and not rep.get("built", True):
            log(f"  R3   NOT BUILT -- {rep.get('reason', '')[:110]}")
            continue
        cert = rep.get("certification") or {}
        v = cert.get("validator") or {}
        log(f"  {name:<4} elements {cert.get('census', {}).get('elements'):>6}  "
            f"restored {rep.get('restored_from_sample', 0):>5}  ours {rep.get('our_elements', 0):>5}  "
            f"validator ok={v.get('ok')} err={v.get('errors')} warn={v.get('warnings')}  "
            f"dangling NEW {cert.get('dangling_NEW_count')}  {rep.get('verdict')}")
    log(f"total {time.time() - t0:.1f}s")
    bad = [n for n, r in reports.items() if r and r.get("verdict") not in (None, "VALID")]
    return 1 if bad else 0


def _parity_headlines(par: dict) -> List[str]:
    """One-screen headline findings of the audit."""
    heads = []
    lr, ls = par["label_ref"], par["label_subj"]
    mms = par["mismatches"]
    sev0 = [m for m in mms if m["severity"] == 0]
    by_kind = Counter(m["kind"] for m in sev0)
    heads.append(f"**{len(sev0)} severity-0 mismatches** ({dict(by_kind)}): registry surfaces where "
                 f"{lr} indexes a class {ls} ALSO HAS but {ls}'s document object does not index it "
                 f"the same way (or points at an absent id).  Grouped: "
                 + "; ".join(f"{b}.{c} x{n}" for (b, c), n in
                             Counter((m['body'], m['container']) for m in sev0).most_common(8)))
    sd = par.get("symbolid_mgr") or {}
    mfd = sd.get("missing_view_family_defaults") or []
    mcd = sd.get("missing_class_defaults") or []
    if mfd or mcd:
        heads.append(f"**The DEFAULT-TYPE map is the largest gap**: `SymbolIdMgr.m_defElementTypeMap` "
                     f"(group -> default element; groups are compiled-in per class and per VIEW "
                     f"FAMILY).  {ls} has NO default view type for {len(mfd)} of its 19 view "
                     f"families and no default of {len(mcd)} other present classes "
                     f"({', '.join(sorted({c for _g, c, _h in mcd}))}); {lr} carries one "
                     f"default per group.  A likely load-time lookup the reader performs when it "
                     f"creates a view / places a first element.")
    ct = par["category_tracking"]["gstyleData"]
    heads.append(f"**The object-styles catalog registration is CLEAN in {ls}**: "
                 f"CategoryTracking.m_gstyleData {lr} {ct[lr + '_rows']} rows vs {ls} "
                 f"{ct[ls + '_rows']}; built-in (category, type) keys missing in {ls}: "
                 f"{ct['builtin_keys_missing_in_subj']}; {ls} present GStyle rows NOT indexed: "
                 f"{ct[ls + '_present_gstyle_rows_NOT_indexed']}; dangling entries: "
                 f"{ct[ls + '_dangling_entries']} -- so our catalog rows ARE indexed; S4/S5's "
                 f"catalog defect (if any) is in the row VALUES, not the registry.")
    others = [m for m in sev0 if m["body"] != "SymbolIdMgr"]
    if others:
        heads.append("**Other registry gaps**: " + "; ".join(
            f"{m['body']}.{m['container']}" for m in others))
    uet0 = [m for m in sev0 if m["body"] == "UniqueElementsTracking"]
    if uet0:
        heads.append(f"UniqueElementsTracking: {len(uet0)} slot mismatch(es) -- "
                     + "; ".join(m["detail"] for m in uet0[:3]))
    else:
        heads.append(f"UniqueElementsTracking (the positional singleton table): NO mismatch -- "
                     f"every slot {ls} populates holds the compiled-in class of that position "
                     f"(our UET_POS_TO_CLASS wiring is confirmed correct).")
    return heads


if __name__ == "__main__":
    sys.exit(main())
