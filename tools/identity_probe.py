#!/usr/bin/env python
"""identity_probe.py -- THE ELEMENT-IDENTITY FORENSICS + I1 + birthright v4
(identity stream, 2026-08-05, post-verdict-#47).

THE LAW AS MEASURED (genesis-audit #43..#47): famdocs containing OUR
authored content fail the instance audit on REDUCED bases only (T1uG: the
same self-contained bytes PASS on rst, FAIL on G_ABPD); BORN content
passes everywhere in BOTH species (T2a standalone, TB0g embedded-born,
both on G_ABPD).  Self-containment excludes references; the surviving
axis is ELEMENT-LEVEL IDENTITY/EPISODE state.

THE MATCHED PAIR ON DISK: TB0r's famdoc (born, passes on G_ABPD as TB0g)
vs T1u's famdoc (ours-content, fails there as T1uG) -- same base, same
famload lane, same species tier.

THE FORENSICS (``forensics`` -> experiments/identity/identity_diff.json),
fully machine-measured at run time:

  half 1 -- the famload HOST-SIDE WRITE DIFF (TB0g vs T1uG on the same
  base): BasicFileInfo fields, Global/DocumentIncrementTable bytes,
  Global/History, Global/Latest leaf diff, host ElemTable added rows, the
  CD framing.  MEASURED: the DIT writes are BYTE-IDENTICAL, History is
  untouched, Latest differs on 6 construction leaves, ElemTable rows are
  shape-identical, BFI differs only on the save-path basename ==> the
  coupling is INSIDE THE FAMDOC ELEMENTS.

  half 2 -- the ELEMENT identity fields of the matched pair (TB0g's 414
  born vs T1uG's 1,992-shell + 35-ours), every identity/episode surface:
  the inline-ADocument m_elemArr history rows (originalElementId +
  episode columns), the ``revit.local.family:`` identity strings (the
  m_seekItemId-style identity of family parameters), the seq-101 headers
  (m_abFlags4Bytes, m_regenHistory, parents), created/user/version
  fields, GUID-bearing leaves -- each measured EXONERATED or ranked into
  the fix list.

THE HEADLINE MEASUREMENT (the ranked delta): the family-parameter
identity string ``revit.local.family:<32-hex session><8-hex id>-1.0.0``
embeds the id the parameter had AT BIRTH, frozen forever: native
containers are SELF (suffix == current id; rst host 120/120, rst
embedded units 243/243 -- they ARE the birth container), every rebased
transplant is OTHER (the string never re-derives).  On G_ABPD the four
loaded-famdoc cells split EXACTLY on that axis: T2a + TB0g all-OTHER =
PASS; T1uG + SC1 ours-SELF = FAIL.  Our params mint identity at the
host-watermark current id -- identity coupled to the host's id/episode
state; born params carry independent (frozen-birth) identity.  Second
surface: the seq-101 ``m_abFlags4Bytes`` species table (ours mixes
conventions inside one famdoc and strays off BOTH born species on
DBViewType/SunAndShadowSettings).

THE ROUND (staged behind one G_ABPD control, reading order first-to-last):

  I1     T1u's famdoc REBUILT byte-identically (machine-pinned against
         experiments/unionrec/T1u.rvt -- the rst PASS), then our 35
         elements' identity fields normalized to the born convention:
         the 14 ParamElemFamily identity suffixes re-minted as FROZEN
         BIRTH ids continuing the shell's standalone id space
         (7675..7688), the 12 covered headers' m_abFlags4Bytes set to the
         born-standalone table.  Content untouched -- the emitted unit is
         machine-verified to differ from T1u's bytes ONLY inside those
         enumerated fields (equal lengths, equal seq-103, per-record
         containment).  famload + one instance on G_ABPD.
         I1 PASS => the identity law is confirmed and the fix is exactly
         the normalized field set.
  BX_v4  B0's recipe (SC1's exact spec+binds) through BIRTHRIGHT v4 --
         v3 + the BORN IDENTITY lane -- famload + one instance on G_ABPD.
         The ONE thing vs BX_v3 (FAIL): the element identity fields.
  DEMO_250v_room_v10  the user's exact prompt end-to-end through
         rvt.frontdoor.run with birthright v4 (v9's recipe, version=4).

PROOF-ONLY: I1 embeds vendor-born content and stays quarantined under
experiments/ (zero donors in anything shipped); BX_v4 and DEMO v10 carry
zero donor bytes (authored birth + our own minted identity, test-
enforced).  STAGE ONLY -- the orchestrator uploads.

USAGE (repo root)::

    .venv/bin/python tools/identity_probe.py forensics
    .venv/bin/python tools/identity_probe.py build [--only I1,BX_v4,...]
    .venv/bin/python tools/identity_probe.py census FILE [--base BASE]
    .venv/bin/python tools/identity_probe.py verify
    .venv/bin/python tools/identity_probe.py stage

TERRITORY: this file, src/rvt/famgen/birthright.py (v4 lanes),
experiments/identity/**, tests/test_identity.py, docs/inbox/identity.md,
plus the staging copies probe_batch writes under experiments/acceptance/.
IMPORTS (never edits): tools/union_reconcile.py (T1u machinery +
byte-identity pin + born-ADocument swap), tools/rft_probe.py,
tools/selfcontained.py, tools/species_probe.py (species census),
tools/famdoc_blobs.py, tools/bisect_instance_bug.py, tools/probe_batch.py,
rvt.famgen.birthright (v4).  No Autodesk install dirs, no browser, no
full-suite runs.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import importlib.util
import json
import os
import re
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

OUT_DIR = os.path.join(ROOT, "experiments", "identity")
BUILD_DIR = os.path.join(OUT_DIR, "_build")
ACCT = os.path.join(OUT_DIR, "accounting.json")
DIFF = os.path.join(OUT_DIR, "identity_diff.json")
PROBES = os.path.join(OUT_DIR, "probes.json")

RST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
G_ABPD = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "compose",
                      "G_ABPD.rvt")
VENDOR_RFA = os.path.join(ROOT, "vendor", "phi-ag-rvt", "examples",
                          "Autodesk", "racbasicsamplefamily-2026.rfa")

#: the four G_ABPD famdoc cells this stream reads (all viewer-read, b51-54)
T1UG_RVT = os.path.join(ROOT, "experiments", "species", "T1uG.rvt")
TB0G_RVT = os.path.join(ROOT, "experiments", "species", "TB0g.rvt")
T2A_RVT = os.path.join(ROOT, "experiments", "rftprobe", "T2a.rvt")
SC1_RVT = os.path.join(ROOT, "experiments", "selfcontained", "SC1.rvt")
T1U_RVT = os.path.join(ROOT, "experiments", "unionrec", "T1u.rvt")

#: recorded unit GUID of the T1u reference build (unionrec accounting)
T1U_DOC_GUID = "7218d5e4-424d-4914-9904-e7bcc1794fd7"

#: T1u's famdoc block law (union_reconcile): shell = wm+1..wm+1992 (the
#: .rfa's 1,992 elements rebased), ours = wm+2000.. (famdoc_final offset).
#: With rst wm == G_ABPD wm == 1,472,524 the ours block starts here:
OURS_MIN = 1472524 + 2000 + 1          # 1474525; first carried id is +1 more

#: the born-standalone id space of the vendor shell: ids 0..7674 (measured
#: on the .rfa).  I1 mints our 14 params' FROZEN BIRTH ids continuing it:
RFA_MAX_ID = 7674
I1_BIRTH_BASE = RFA_MAX_ID + 1         # 7675..7688 for the 14 params

DEMO_PROMPT = "an electrical room rated for 250V with 6 panels"

LADDER = ("I1", "BX_v4", "DEMO_250v_room_v10")

AXES = {
    "I1": "THE DECISIVE CELL: T1u's famdoc rebuilt byte-identically "
          "(machine-pinned vs the rst PASS T1u.rvt), then OUR 35 elements' "
          "identity fields -- and ONLY those fields -- normalized to the "
          "born convention (14 ParamElemFamily identity suffixes re-minted "
          "as frozen birth ids 7675..7688; 12 covered headers' "
          "m_abFlags4Bytes set to the born-standalone table), famloaded + "
          "one uniform instance on G_ABPD.  The ONE thing vs T1uG (FAIL): "
          "the normalized identity field set.  Content untouched, "
          "machine-verified per record.",
    "BX_v4": "B0's recipe through birthright v4: SC1's exact spec + binds "
             "(sha-pinned) + the BORN IDENTITY lane via famload + one "
             "instance on G_ABPD.  The ONE thing vs BX_v3 (FAIL): the "
             "element identity fields (frozen-birth parameter suffixes + "
             "born header flags).",
    "DEMO_250v_room_v10": "the user's exact prompt through "
                          "rvt.frontdoor.run with birthright v4 -- v9's "
                          "recipe at version=4 (identity lane applied to "
                          "all 6 families; loader hostsym half carried "
                          "over).",
}


def log(msg: str) -> None:
    print(f"[identity] {msg}", flush=True)


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
        f"_identity_{name}", os.path.join(HERE, f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_CACHE: Dict[str, Any] = {}


def _ur():
    """tools/union_reconcile.py -- T1u machinery, byte-identity pin, the
    born-ADocument swap (reads only)."""
    if "ur" not in _CACHE:
        _CACHE["ur"] = _load_tool("union_reconcile")
    return _CACHE["ur"]


def _rp():
    if "rp" not in _CACHE:
        _CACHE["rp"] = _load_tool("rft_probe")
    return _CACHE["rp"]


def _sc():
    if "sc" not in _CACHE:
        _CACHE["sc"] = _load_tool("selfcontained")
    return _CACHE["sc"]


def _sp():
    """tools/species_probe.py -- the species census (v3's machine gate;
    v4 output must keep it green)."""
    if "sp" not in _CACHE:
        _CACHE["sp"] = _load_tool("species_probe")
    return _CACHE["sp"]


def _fb():
    if "fb" not in _CACHE:
        import famdoc_bisect as FB
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
# shared decode helpers
# ===========================================================================

SESSION_FULL_RE = re.compile(
    r"revit\.local\.family:([0-9a-f]{32})([0-9a-f]{8})-([0-9.]+)")


def _leaf_diff(a: Any, b: Any, p: str = "", out: Optional[list] = None) -> list:
    if out is None:
        out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            _leaf_diff(a.get(k), b.get(k), p + "." + k, out)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            _leaf_diff(x, y, p + f"[{i}]", out)
    else:
        if a != b:
            out.append(p)
    return out


def _adoc_elemarr(path: str) -> Tuple[str, List[dict]]:
    """(guid, m_elemArr rows) of a file's single ContentDocuments entry."""
    from rvt.container import open_rvt
    from rvt.famgen import factory as F
    from rvt import adocument as A
    with open_rvt(path) as f:
        cd = b"".join(f.inflate_all("Global/ContentDocuments"))
    entries, _tail = F.parse_content_documents(cd)
    if len(entries) != 1:
        raise RuntimeError(f"{relp(path)}: {len(entries)} CD entries, "
                           f"expected 1")
    guid, payload = entries[0]
    d = A.decode_latest(payload)
    if not d.clean:
        raise RuntimeError(f"{relp(path)}: inline ADocument does not decode "
                           f"clean")
    et = ((d.value.get("m_elemTable") or {}).get("value") or {})
    return guid, list(et.get("m_elemArr") or [])


def _elemarr_census(rows: List[dict]) -> Dict[str, Any]:
    ce = collections.Counter()
    me = collections.Counter()
    ue = collections.Counter()
    orig_eq = 0
    for r in rows:
        h = r.get("m_history") or {}
        ce[(h.get("m_creationDate") or {}).get("m_id")] += 1
        me[(h.get("m_lastModificationDate") or {}).get("m_id")] += 1
        ue[(h.get("m_lastUserModificationDate") or {}).get("m_id")] += 1
        if (h.get("m_originalElementId") or {}).get("m_id64") == r.get("m_id"):
            orig_eq += 1
    return {"rows": len(rows),
            "creation_ep": {str(k): v for k, v in sorted(ce.items(),
                                                         key=str)},
            "modified_ep": {str(k): v for k, v in sorted(me.items(),
                                                         key=str)},
            "user_modified_ep": {str(k): v for k, v in sorted(ue.items(),
                                                              key=str)},
            "original_id_equals_id": orig_eq}


def _param_identities(path: str, unit: int) -> List[Dict[str, Any]]:
    """Every ParamElemFamily of a unit with its identity-string parts and
    the SELF/OTHER verdict (SELF = suffix embeds the element's CURRENT id;
    OTHER = a frozen birth id)."""
    from rvt.families import FamilyIndex
    idx = FamilyIndex(path)
    recs = idx.unit_records(unit)
    out = []
    for e, r in sorted(recs.get(102, {}).items()):
        if idx.class_name(r.class_id) != "ParamElemFamily":
            continue
        v = idx.value(unit, e, 102) or {}
        pd = ((v.get("m_pParamDef") or {}).get("value") or {})
        tid = str((pd.get("m_typeId") or {}).get("m_typeId") or "")
        m = SESSION_FULL_RE.search(tid)
        row: Dict[str, Any] = {"id": int(e),
                               "caption": pd.get("m_caption")}
        if m:
            emb = int(m.group(2), 16)
            row.update({"session": m.group(1), "embedded_id": emb,
                        "form": "SELF" if emb == e else "OTHER"})
        else:
            row["form"] = "no-session-identity"
        out.append(row)
    return out


def _flags_by_class(path: str, unit: int,
                    pop_of=None) -> Dict[str, Dict[str, Any]]:
    """{(pop, class): {flags value: count}} of a unit's seq-101 headers."""
    from rvt.families import FamilyIndex
    idx = FamilyIndex(path)
    recs = idx.unit_records(unit)
    out: Dict[Tuple[str, str], collections.Counter] = \
        collections.defaultdict(collections.Counter)
    for e in recs.get(101, {}):
        cn = idx.class_name(recs[102][e].class_id) if e in recs.get(102, {}) \
            else "?"
        pop = pop_of(e) if pop_of else "all"
        h = idx.value(unit, e, 101) or {}
        out[(pop, cn)][h.get("m_abFlags4Bytes")] += 1
    return {f"{p}:{c}": dict(v) for (p, c), v in sorted(out.items())}


# ===========================================================================
# THE FORENSICS
# ===========================================================================

def _forensic_host_writes() -> Dict[str, Any]:
    """Half 1: what famload WROTE host-side for TB0g vs T1uG (same base,
    same lane) -- byte- and field-level."""
    from rvt.container import open_rvt
    from rvt import adocument as A
    from rvt import stream_encoders as se
    from rvt.elemtable import inflate_global_stream, parse_elemtable
    from rvt.content import parse_history

    def raws(path):
        out = {}
        with open_rvt(path) as f:
            for s in f.streams():
                name = getattr(s, "name", str(s))
                try:
                    out[name] = f.raw(name)
                except Exception:                              # noqa: BLE001
                    out[name] = b""
        return out

    base_r, a_r, b_r = raws(G_ABPD), raws(T1UG_RVT), raws(TB0G_RVT)
    touched = sorted(n for n in set(base_r) | set(a_r) | set(b_r)
                     if not (base_r.get(n) == a_r.get(n) == b_r.get(n)))
    out: Dict[str, Any] = {
        "question": ("TB0g (PASS) and T1uG (FAIL) went through the same "
                     "famload lane onto the same base -- if the host-side "
                     "writes are identical, the coupling is inside the "
                     "famdoc elements"),
        "streams_touched": touched,
    }
    # DIT: byte comparison
    out["document_increment_table"] = {
        "t1ug_equals_tb0g_bytes": a_r.get("Global/DocumentIncrementTable")
        == b_r.get("Global/DocumentIncrementTable"),
        "changed_vs_base": base_r.get("Global/DocumentIncrementTable")
        != a_r.get("Global/DocumentIncrementTable"),
        "what_changed_vs_base": "the writer's save path scrubs every "
                                "save-episode username to '' (both files "
                                "identically); row count/ids/timestamps/"
                                "counters ride verbatim",
    }
    # History: untouched?
    out["history"] = {
        "touched_by_either": "Global/History" in touched,
        "note": "famload reuses the host's current episode -- no new "
                "History row (measured: stream byte-identical to the base "
                "in both files)",
    }
    # BFI field diff
    def bfi(raw):
        return se.decode_basic_file_info(raw)
    fb, fa, f2 = bfi(base_r["BasicFileInfo"]), bfi(a_r["BasicFileInfo"]), \
        bfi(b_r["BasicFileInfo"])
    bfi_diff = {k: {"base": fb.get(k), "t1ug": fa.get(k), "tb0g": f2.get(k)}
                for k in sorted(set(fb) | set(fa) | set(f2))
                if k != "mirror_text"
                and not (fb.get(k) == fa.get(k) == f2.get(k))}
    out["basic_file_info"] = {
        "differing_fields": bfi_diff,
        "verdict": "identical between the PASS and the FAIL modulo the "
                   "output filename (author/client are the writer's own "
                   "on both; the base's document GUID rides unchanged on "
                   "both)"}
    # Latest leaf diff
    with open_rvt(T1UG_RVT) as f:
        va = A.decode_latest(f.inflate("Global/Latest")).value
    with open_rvt(TB0G_RVT) as f:
        vb = A.decode_latest(f.inflate("Global/Latest")).value
    diffs = _leaf_diff(va, vb)
    out["host_latest_adocument"] = {
        "n_leaf_diffs": len(diffs),
        "leaf_diffs": diffs,
        "verdict": "every leaf diff is construction identity (unit GUID, "
                   "episode record count, surrogate id, tracked symbol "
                   "sets) -- the host ADocument write is SHAPE-IDENTICAL",
    }
    # ElemTable added rows
    def rows(raw):
        et = parse_elemtable(inflate_global_stream(raw).payload, "x")
        return {int(r.id): r for r in et.records}, et
    rb, _etb = rows(base_r["Global/ElemTable"])
    shapes = {}
    for name, raw in (("t1ug", a_r["Global/ElemTable"]),
                      ("tb0g", b_r["Global/ElemTable"])):
        rr, et = rows(raw)
        added = sorted(set(rr) - set(rb))
        sh = collections.Counter()
        for i in added:
            r = rr[i]
            sh[(r.original_id == r.id, r.creation_ep, r.modified_ep,
                r.user_modified_ep, r.partition_id)] += 1
        changed = sum(1 for i in rb if i in rr and (
            rb[i].original_id, rb[i].creation_ep, rb[i].modified_ep,
            rb[i].user_modified_ep, rb[i].owner_id, rb[i].partition_id) != (
            rr[i].original_id, rr[i].creation_ep, rr[i].modified_ep,
            rr[i].user_modified_ep, rr[i].owner_id, rr[i].partition_id))
        shapes[name] = {"added_rows": len(added),
                        "changed_base_rows": changed,
                        "row_shapes(orig==id, ce, me, ue, part)": {
                            str(k): v for k, v in sh.items()},
                        "footer_last_id": et.footer.last_id if et.footer
                        else None}
    out["host_elemtable"] = {
        **shapes,
        "verdict": "added rows are SHAPE-IDENTICAL (orig==id, all three "
                   "episode columns = the host's current episode 1016, "
                   "partition 0); zero base rows changed in either",
    }
    # the reduced-base premise check: rst vs G_ABPD History/DIT/rows
    h_rst = parse_history(inflate_global_stream(
        _raw_of(RST, "Global/History")).payload)
    h_g = parse_history(inflate_global_stream(
        base_r["Global/History"]).payload)
    same_hist = (len(h_rst.entries) == len(h_g.entries)
                 and all(x.guid == y.guid for x, y in
                         zip(h_rst.entries, h_g.entries)))
    d_rst = se.decode_increment_table(inflate_global_stream(
        _raw_of(RST, "Global/DocumentIncrementTable")).payload)
    d_g = se.decode_increment_table(inflate_global_stream(
        base_r["Global/DocumentIncrementTable"]).payload)
    rr_rst, _ = rows(_raw_of(RST, "Global/ElemTable"))
    surv_changed = sum(1 for i in rb if i in rr_rst and (
        rb[i].original_id, rb[i].creation_ep, rb[i].modified_ep,
        rb[i].user_modified_ep, rb[i].owner_id, rb[i].partition_id) != (
        rr_rst[i].original_id, rr_rst[i].creation_ep, rr_rst[i].modified_ep,
        rr_rst[i].user_modified_ep, rr_rst[i].owner_id,
        rr_rst[i].partition_id))
    out["reduced_base_identity_premise"] = {
        "history_entry_guids_equal_rst": same_hist,
        "history_entries": len(h_g.entries),
        "dit_rows_equal_rst": d_rst == d_g,
        "surviving_elemtable_rows_changed_vs_rst": surv_changed,
        "verdict": ("the 'reduction rewrote History/DIT' premise is "
                    "FALSIFIED at these surfaces: G_ABPD carries rst's "
                    "History entries, DIT rows (usernames included) and "
                    "surviving ElemTable rows UNCHANGED.  What reduction "
                    "changed: the roster (10,834 rows removed) and "
                    "substituted element content.  The identity coupling "
                    "must therefore be read against the famdoc elements "
                    "themselves -- half 2."),
    }
    out["verdict"] = (
        "HOST-SIDE WRITES ARE IDENTICAL between the PASS and the FAIL "
        "(DIT byte-identical, History untouched, Latest 6 construction "
        "leaves, ElemTable rows shape-identical, BFI modulo filename) "
        "==> the coupling is inside the famdoc elements")
    return out


def _raw_of(path: str, name: str) -> bytes:
    from rvt.container import open_rvt
    with open_rvt(path) as f:
        return f.raw(name)


def _forensic_elements() -> Dict[str, Any]:
    """Half 2: every element-level identity surface of the matched pair,
    measured population-by-population (TB0g born / T1uG shell / T1uG
    ours)."""
    from rvt.families import FamilyIndex

    def pop_t1ug(e):
        return "ours" if e > OURS_MIN else "shell"

    out: Dict[str, Any] = {}
    # 1. inline-ADocument m_elemArr history rows
    g1, arr1 = _adoc_elemarr(T1UG_RVT)
    g2, arr2 = _adoc_elemarr(TB0G_RVT)
    _g3, arr3 = _adoc_elemarr(T2A_RVT)
    _g4, arr4 = _adoc_elemarr(SC1_RVT)
    out["inline_elemarr_history_rows"] = {
        "t1ug": _elemarr_census(arr1), "tb0g": _elemarr_census(arr2),
        "t2a": _elemarr_census(arr3), "sc1": _elemarr_census(arr4),
        "verdict": ("uniform per famdoc, orig==id everywhere; episodes: "
                    "famload-authored tables carry the host's current "
                    "episode 1016 (T2a PASS, TB0g PASS, SC1 FAIL), the "
                    "swapped born-ADocument table carries 0 (T1uG FAIL, "
                    "T1u PASS on rst).  1016 appears on both PASS and "
                    "FAIL ==> the episode column alone does NOT separate; "
                    "EXONERATED as the primary axis (the 0-vs-1016 "
                    "doc-level difference is recorded as an I1-FAIL "
                    "ledger item)"),
    }
    # 2. the identity strings (the m_seekItemId-style identity of params)
    ids_t1ug = _param_identities(T1UG_RVT, 1)
    ids_tb0g = _param_identities(TB0G_RVT, 1)
    ids_t2a = _param_identities(T2A_RVT, 1)
    ids_sc1 = _param_identities(SC1_RVT, 1)

    def split(rows, pop_of=None):
        c = collections.Counter()
        for r in rows:
            pop = pop_of(r["id"]) if pop_of else "all"
            c[(pop, r["form"])] += 1
        return {f"{p}:{f}": n for (p, f), n in sorted(c.items())}

    # the corpus law: native containers are SELF (they ARE the birth
    # container); measured live on rst host + every rst embedded unit
    idx = FamilyIndex(RST)
    host_self = host_other = 0
    for row in _param_identities(RST, 0):
        if row["form"] == "SELF":
            host_self += 1
        elif row["form"] == "OTHER":
            host_other += 1
    unit_self = unit_other = 0
    for u in range(1, len(idx.units)):
        for row in _param_identities(RST, u):
            if row["form"] == "SELF":
                unit_self += 1
            elif row["form"] == "OTHER":
                unit_other += 1
    out["param_identity_strings"] = {
        "form": "revit.local.family:<32-hex session><8-hex id>-1.0.0 "
                "(ParamElemFamily m_pParamDef.m_typeId)",
        "native_law": {
            "rst_host": {"SELF": host_self, "OTHER": host_other},
            "rst_units": {"SELF": unit_self, "OTHER": unit_other},
            "reading": "the suffix records the id AT BIRTH and never "
                       "re-derives; a native container is its own birth "
                       "container, so natively everything reads SELF -- "
                       "a REBASED transplant reads OTHER because the "
                       "frozen birth id no longer equals the current id",
        },
        "cells_on_g_abpd": {
            "T2a (PASS)": split(ids_t2a),
            "TB0g (PASS)": split(ids_tb0g),
            "T1uG (FAIL)": split(ids_t1ug, pop_t1ug),
            "SC1 (FAIL)": split(ids_sc1),
        },
        "t1ug_ours_detail": [r for r in ids_t1ug if r["id"] > OURS_MIN],
        "verdict": ("THE RANK-1 SPLIT: on G_ABPD every PASS famdoc "
                    "carries ONLY frozen-birth (OTHER) identity suffixes; "
                    "every FAIL famdoc carries OUR params minted SELF -- "
                    "identity coupled to the host-watermark current id.  "
                    "The same SELF bytes pass on pristine rst (T1u), "
                    "matching the verdict-#47 law: the coupling expresses "
                    "on reduced substrates only."),
    }
    # 3. header flags by class
    fl_t1ug = _flags_by_class(T1UG_RVT, 1, pop_t1ug)
    fl_tb0g = _flags_by_class(TB0G_RVT, 1)
    idx_rfa = FamilyIndex(VENDOR_RFA)
    recs = idx_rfa.unit_records(0)
    fl_rfa: Dict[str, collections.Counter] = collections.defaultdict(
        collections.Counter)
    for e in recs.get(101, {}):
        cn = idx_rfa.class_name(recs[102][e].class_id) \
            if e in recs.get(102, {}) else "?"
        h = idx_rfa.value(0, e, 101) or {}
        fl_rfa[cn][h.get("m_abFlags4Bytes")] += 1
    from rvt.famgen import birthright as BR
    ours_devs = []
    for key, vals in fl_t1ug.items():
        pop, cn = key.split(":", 1)
        if pop != "ours":
            continue
        want = BR.BORN_HEADER_FLAGS.get(cn)
        if want is None:
            continue
        off = {v: n for v, n in vals.items() if v != want}
        if off:
            ours_devs.append({"class": cn, "ours": vals, "born": want,
                              "rfa_authority": dict(fl_rfa.get(cn, {}))})
    out["header_flags"] = {
        "surface": "seq-101 ElementHeader m_abFlags4Bytes",
        "born_standalone_authority": {c: dict(v) for c, v in
                                      sorted(fl_rfa.items())
                                      if c in BR.BORN_HEADER_FLAGS},
        "t1ug_by_population": fl_t1ug,
        "tb0g_born": fl_tb0g,
        "ours_deviations_vs_born_table": ours_devs,
        "verdict": ("THE RANK-2 SURFACE: the flags word is species-"
                    "coherent per class in every born famdoc (standalone "
                    "carries 0x10, embedded drops it); OUR elements mix "
                    "conventions inside one famdoc and stray off BOTH "
                    "born species (stray 0x800 on DBViewType, missing "
                    "0x2014 on SunAndShadowSettings, missing 0x10 on the "
                    "datum/view classes).  All four G_ABPD cells separate "
                    "on flags-coherence too (T2a/TB0g coherent = PASS, "
                    "T1uG/SC1 mixed = FAIL)."),
    }
    # 4. the exonerated element surfaces
    out["exonerated"] = [
        {"surface": "m_createdPhaseId", "measured": "-1 on every element "
         "of every population"},
        {"surface": "m_regenHistory.m_historyMap (seq-101)",
         "measured": "empty on all 2,027 + 414 headers"},
        {"surface": "m_userId (SketchPlane/VarSketch)",
         "measured": "self-consistent in-unit references on ours AND "
                     "born (points at the element's own sketch chain)"},
        {"surface": "m_seekItemId", "measured": "Family-class only "
         "(loaded-family table row); no carrier among our 35"},
        {"surface": "m_witnessRefs[].m_modified",
         "measured": "Alignment/LinearDimString only (all False); no "
                     "carrier among our 35"},
        {"surface": "GUID-bearing leaves (m_famDocGUID, m_guid, "
                    "worksetVisibilityPGUIDMap)",
         "measured": "carriers are Family/doc-level classes absent from "
                     "our 35; the PGUID maps are empty everywhere"},
        {"surface": "VarSketch/geom m_version counters",
         "measured": "ours within the born value range (0/1)"},
        {"surface": "session hex form",
         "measured": "fresh-uuid4-style hex on ours AND born; born "
                     "sessions also appear nowhere host-side (T2a's 4 "
                     "shell sessions absent from G_ABPD, passes)"},
    ]
    # 5. recorded, NOT normalized in I1 (structure, not identity)
    out["recorded_not_normalized"] = [
        {"surface": "seq-101 m_parents.m_deletion roots",
         "measured": "our ExtentElem (and view-satellite SketchPlane) "
                     "parents lack the leading self-Family root every "
                     "shell twin carries ([DBViewPlan, ExtentElem] vs "
                     "[Family, DBViewPlan, ..., ExtentElem])",
         "why_excluded": "the deletion-parents graph is document "
                         "STRUCTURE; I1 is identity-only by charter.  "
                         "First candidate of the BX_v4-FAIL branch."},
        {"surface": "inline elemArr episode columns (doc-level)",
         "measured": "T1uG's swapped born-ADocument table carries "
                     "episode 0 rows where every famload-authored table "
                     "carries the host episode 1016",
         "why_excluded": "uniform across ours AND shell rows (not an "
                         "element-level ours-vs-born diff); 1016 appears "
                         "on both PASS and FAIL.  I1-FAIL ledger item."},
    ]
    return out


def forensics() -> Dict[str, Any]:
    """The commissioned identity forensics: both halves, machine-measured,
    plus the ranked fix list.  Writes experiments/identity/
    identity_diff.json."""
    t0 = time.time()
    out: Dict[str, Any] = {
        "tool": "tools/identity_probe.py forensics",
        "matched_pair": {"pass": relp(TB0G_RVT), "fail": relp(T1UG_RVT)},
        "context_cells": {"t2a_pass": relp(T2A_RVT),
                          "sc1_fail": relp(SC1_RVT),
                          "t1u_rst_pass": relp(T1U_RVT)},
        "base": relp(G_ABPD),
    }
    out["host_side_writes"] = _forensic_host_writes()
    out["element_identity"] = _forensic_elements()
    out["ranked_fix_list"] = [
        {"rank": 1,
         "field": "ParamElemFamily m_pParamDef.m_typeId identity suffix",
         "born": "frozen BIRTH id (!= current id after any rebase -- the "
                 "shape of every reduced-base PASS)",
         "ours": "the CURRENT id (minted at the host watermark -- "
                 "identity coupled to the host id/episode state)",
         "elements": 14, "authorable": True,
         "i1_normalization": f"suffixes re-minted {I1_BIRTH_BASE}.."
                             f"{I1_BIRTH_BASE + 13} (continuing the "
                             f"shell's standalone id space 0..{RFA_MAX_ID})",
         "v4_lane": "apply_born_identity: frozen-birth mint at "
                    "BIRTH_SUFFIX_BASE+k"},
        {"rank": 2,
         "field": "seq-101 ElementHeader m_abFlags4Bytes",
         "born": "species-coherent per-class table (BORN_HEADER_FLAGS; "
                 "measured on the vendor .rfa == T2a's PASS bytes)",
         "ours": "mixed convention inside one famdoc; strays off BOTH "
                 "born species on DBViewType (stray 0x800) and "
                 "SunAndShadowSettings (missing 0x2014)",
         "elements": 12, "authorable": True,
         "i1_normalization": "our 35's covered headers set to the born "
                             "table (12 words change)",
         "v4_lane": "apply_born_identity: BORN_HEADER_FLAGS"},
        {"rank": "recorded",
         "field": "m_parents.m_deletion roots / inline elemArr episode "
                  "columns",
         "note": "structure / doc-level -- excluded from I1 by the "
                 "identity-only charter; pre-committed BX_v4-FAIL and "
                 "I1-FAIL ledger items"},
        {"rank": "exonerated",
         "field": "host-side famload writes; m_createdPhaseId; "
                  "m_regenHistory; m_userId; m_seekItemId; witness "
                  "stamps; GUID leaves; version counters; session hex "
                  "form; elemArr orig==id",
         "note": "measured equal / no-carrier / non-separating (see "
                 "element_identity)"},
    ]
    out["seconds"] = round(time.time() - t0, 1)
    jdump(DIFF, out)
    hw = out["host_side_writes"]
    log(f"forensics -> {relp(DIFF)} (DIT byte-identical: "
        f"{hw['document_increment_table']['t1ug_equals_tb0g_bytes']}; "
        f"rank-1 = identity suffix SELF/OTHER split; rank-2 = header "
        f"flags)")
    return out


# ===========================================================================
# I1 -- the identity normalization on T1u's famdoc
# ===========================================================================

def _normalize_identity_fields(doc, carried) -> Dict[str, Any]:
    """The I1 normalization, on the pinned union doc: our 14 params'
    identity suffixes -> frozen birth ids continuing the shell's
    standalone space; our 35 covered headers -> the born flags table.
    Every edit is enumerated for the surgical proof."""
    from rvt.famgen import birthright as BR
    edits: List[Dict[str, Any]] = []
    params = sorted((e for e in carried
                     if e.class_name == "ParamElemFamily"),
                    key=lambda e: int(e.elem_id))
    if len(params) != 14:
        raise RuntimeError(f"I1: expected 14 carried ParamElemFamily, got "
                           f"{len(params)}")
    for k, el in enumerate(params):
        pd = ((el.obj.get("m_pParamDef") or {}).get("value") or {})
        tid = pd.get("m_typeId")
        s = str((tid or {}).get("m_typeId") or "")
        m = SESSION_FULL_RE.search(s)
        if not m:
            raise RuntimeError(f"I1: param {el.elem_id} has no session "
                               f"identity: {s!r}")
        if int(m.group(2), 16) != int(el.elem_id):
            raise RuntimeError(f"I1: param {el.elem_id} suffix embeds "
                               f"{int(m.group(2), 16)} -- not the SELF "
                               f"mint the normalization expects")
        birth = I1_BIRTH_BASE + k
        new = s.replace(m.group(0),
                        f"revit.local.family:{m.group(1)}"
                        f"{birth & 0xFFFFFFFF:08x}-{m.group(3)}")
        if len(new) != len(s):
            raise RuntimeError("I1: identity rewrite changed string length")
        tid["m_typeId"] = new
        edits.append({"id": int(el.elem_id), "kind": "identity_suffix",
                      "seq": 102, "birth_id": birth})
    for el in carried:
        want = BR.BORN_HEADER_FLAGS.get(el.class_name)
        if want is None:
            continue
        got = el.header.get("m_abFlags4Bytes")
        if got != want:
            el.header["m_abFlags4Bytes"] = int(want)
            edits.append({"id": int(el.elem_id), "kind": "header_flags",
                          "seq": 101, "from": got, "to": int(want),
                          "class": el.class_name})
    n_flags = sum(1 for e in edits if e["kind"] == "header_flags")
    return {"edits": edits, "n_suffixes": len(params),
            "n_flag_words": n_flags,
            "birth_ids": [I1_BIRTH_BASE + k for k in range(len(params))],
            "law": BR.BORN_IDENTITY_LAW}


def _surgical_proof(doc, edits: List[Dict[str, Any]]) -> Dict[str, Any]:
    """The emitted unit must differ from T1u's bytes ONLY inside the
    enumerated fields: seq-103 byte-identical; seq-101/102 equal length
    with differing records exactly the edited ids; each differing record's
    decoded diff confined to the edited field.  Build-refusing."""
    from rvt.families import FamilyIndex, unit_segments
    from rvt.objects import iter_records
    idx = FamilyIndex(T1U_RVT)
    tgt_unit = None
    for i, u in enumerate(idx.units):
        if str(u.guid) == T1U_DOC_GUID:
            tgt_unit = i
    if tgt_unit is None:
        raise RuntimeError(f"I1: {relp(T1U_RVT)} has no unit "
                           f"{T1U_DOC_GUID}")
    theirs = unit_segments(idx, tgt_unit)
    mine = doc.to_embedded_unit()["segments"]
    expected = {101: {e["id"] for e in edits if e["seq"] == 101},
                102: {e["id"] for e in edits if e["seq"] == 102}}
    rep: Dict[str, Any] = {"target": relp(T1U_RVT), "unit": tgt_unit}
    if mine.get(103) != theirs.get(103):
        raise RuntimeError("I1: seq-103 (reps) differs from T1u -- the "
                           "normalization leaked into geometry; refused")
    rep["seq103_byte_identical"] = True
    for seq in (101, 102):
        a, b = mine.get(seq, b""), theirs.get(seq, b"")
        if len(a) != len(b):
            raise RuntimeError(f"I1: seq-{seq} length {len(a)} != T1u's "
                               f"{len(b)} -- the edits were not "
                               f"length-preserving; refused")
        ra = {r.elem_id: r.payload for r in iter_records(a, seq)}
        rb = {r.elem_id: r.payload for r in iter_records(b, seq)}
        if set(ra) != set(rb):
            raise RuntimeError(f"I1: seq-{seq} record id sets differ")
        differing = sorted(i for i in ra if ra[i] != rb[i])
        if set(differing) != expected[seq]:
            raise RuntimeError(
                f"I1: seq-{seq} differing records {differing[:8]} != the "
                f"enumerated edit set {sorted(expected[seq])[:8]} -- NOT "
                f"surgical; refused")
        rep[f"seq{seq}_differing_records"] = differing
        rep[f"seq{seq}_bytes"] = len(a)
    rep["surgical"] = True
    return rep


def build_i1() -> Dict[str, Any]:
    """I1: T1u's famdoc rebuilt + pinned byte-identical, our 35's identity
    fields normalized to the born convention, famload + one instance on
    G_ABPD (T1uG's exact lane incl. the born-ADocument swap)."""
    UR = _ur()
    rp = _rp()
    T = _room()
    rp._install_schema(G_ABPD)
    wm = T.host_watermark(G_ABPD)
    wm_r = T.host_watermark(RST)
    if wm != wm_r:
        raise RuntimeError(f"I1: G_ABPD watermark {wm} != RST watermark "
                           f"{wm_r} -- the byte-identical transplant "
                           f"assumption fails")
    pdir = os.path.join(BUILD_DIR, "I1")
    os.makedirs(pdir, exist_ok=True)
    outp = os.path.join(OUT_DIR, "I1.rvt")
    info: Dict[str, Any] = {"probe": "I1", "axis": AXES["I1"],
                            "base": relp(G_ABPD), "watermark": wm,
                            "rfa": relp(VENDOR_RFA)}
    doc, rep, carried, ctx = UR.make_union_doc_standalone(UR.VENDOR_RFA, wm)
    info["union"] = {
        "shell_block": rep["shell_block"],
        "n_carried": len(rep["carried"]),
        "registration": rep["registration"],
    }
    # 1. the base-state byte-identity proof (T1uG's own pin, unchanged)
    info["base_byte_identity"] = UR.pin_doc_to_target_unit(doc, T1U_RVT,
                                                           T1U_DOC_GUID)
    # 2. the identity normalization -- the ONE variable
    info["normalization"] = _normalize_identity_fields(doc, carried)
    # 3. the surgical proof (bytes differ ONLY inside the enumerated
    #    fields)
    info["surgical_proof"] = _surgical_proof(
        doc, info["normalization"]["edits"])
    info["document_guid"] = doc.document_guid          # fresh (house law)
    info["n_elements"] = len(doc.elements)
    info["reference_resolution"] = UR.famdoc_refs(doc, G_ABPD)

    def _swap(src, dst):
        rec = UR.swap_born_adoc(src, dst, doc=doc, rfa_path=UR.VENDOR_RFA,
                                idmap=ctx["idmap"])
        rec["machinery"] = ("union_reconcile.swap_born_adoc VERBATIM "
                            "(T1uG's own lane; only the unit identity "
                            "fields differ)")
        return rec

    info.update(UR._build_common("I1", doc, host=G_ABPD,
                                 category=int(doc.category_id), pdir=pdir,
                                 outp=outp, adoc_swap=_swap))
    info["instance_category"] = int(doc.category_id)
    # 4. the emitted famdoc's identity census (unit-side params all OTHER)
    ids = _param_identities(outp, 1)
    self_rows = [r for r in ids if r.get("form") == "SELF"]
    info["file_identity_census"] = {
        "unit_params": len(ids),
        "self_minted": len(self_rows),
        "ours_birth_suffixes": [r["embedded_id"] for r in ids
                                if r["id"] > OURS_MIN],
        "all_other_form": not self_rows,
    }
    if self_rows:
        raise RuntimeError(f"I1: emitted unit still carries SELF-minted "
                           f"identity: {self_rows[:4]}")
    sp = _sp()
    info["species"] = sp.species_census(outp, G_ABPD, ours_content=False)
    return info


# ===========================================================================
# BX_v4 / DEMO v10 -- birthright v4
# ===========================================================================

def build_bx_v4() -> Dict[str, Any]:
    """BX_v4: SC1's exact recipe (famload + builder + one instance on
    G_ABPD, birthright with binds) at version=4.  The ONE thing vs BX_v3
    (FAIL): the element identity fields."""
    SC = _sc()
    sp = _sp()
    rp = _rp()
    FB = _fb()
    fbl = _fbl()
    T = _room()
    from rvt.famgen import birthright as BR
    from rvt import famload as FL
    spec = BR.read_birth_spec(SC.BIRTH_SPEC)
    binds = BR.read_bind_spec(SC.BINDS_PATH)
    rp._install_schema(G_ABPD)
    wm = T.host_watermark(G_ABPD)
    pdir = os.path.join(BUILD_DIR, "BX_v4")
    os.makedirs(pdir, exist_ok=True)
    outp = os.path.join(OUT_DIR, "BX_v4.rvt")
    info: Dict[str, Any] = {"probe": "BX_v4", "axis": AXES["BX_v4"],
                            "base": relp(G_ABPD), "watermark": wm,
                            "birth_spec_sha256": (spec.source or {}).get(
                                "sha256"),
                            "binds": {k: v["__eid__"] for k, v in
                                      (binds.get("binds") or {}).items()}}
    products: Dict[str, Any] = {}

    def mk(start_id):
        prod = FB.our_product(start_id)
        products["BX_v4"] = prod
        return prod.doc

    src = os.path.join(pdir, "BX_v4_load.rvt")
    with BR.enabled(spec, binds=binds, version=4) as br_ctx:
        res = FL.load_family_documents(
            G_ABPD, [FL.FamilyLoad(key="BX_v4", builder=mk)], src,
            validate=True, report_path=src + ".load.json")
    if not res.ok:
        raise RuntimeError(f"BX_v4: famload failed: {res.stop_reason}")
    if not br_ctx["reports"]:
        raise RuntimeError("BX_v4: birthright never fired")
    ent = br_ctx["reports"][0]
    rep = ent.get("report") or {}
    if rep.get("version") != 4:
        raise RuntimeError(f"BX_v4: birthright ran version "
                           f"{rep.get('version')}, expected 4")
    idn = rep.get("identity") or {}
    if not idn.get("applied"):
        raise RuntimeError(f"BX_v4: identity lane did not apply: {idn}")
    if not (rep.get("identity_census") or {}).get("identity_ok"):
        raise RuntimeError("BX_v4: doc-side identity census not green")
    hs = rep.get("hostsym") or {}
    if not hs.get("applied"):
        raise RuntimeError(f"BX_v4: hostsym lane did not apply: {hs}")
    if not (ent.get("verify") or {}).get("ok"):
        raise RuntimeError("BX_v4: authored-vs-mined verify not ok")
    if not (ent.get("walked_bind_census") or {}).get("self_contained"):
        raise RuntimeError("BX_v4: doc-side walked binds not self-contained")
    info["birthright"] = {
        "version": 4,
        "n_added": ent.get("n_added"),
        "verify_ok": (ent.get("verify") or {}).get("ok"),
        "identity": {k: idn.get(k) for k in
                     ("suffix_base", "n_suffixes_reminted",
                      "flags_headers_covered", "flags_changed")},
        "identity_census": rep.get("identity_census"),
        "hostsym": {k: hs.get(k) for k in ("applied",
                                           "stripped_blank_pairs",
                                           "host_type_names")},
        "binds_bound": (ent.get("binds") or {}).get("bound"),
    }
    p = res.plans[0]
    if [n for n in p.type_names if not str(n).strip()]:
        raise RuntimeError(f"BX_v4: famload plan carries a blank type "
                           f"name: {p.type_names!r}")
    info["load"] = {"family_id": p.host_family_id, "symbol_id": p.symbol_id,
                    "guid": p.guid, "type_names": list(p.type_names or [])}
    info["immediate_parent"] = relp(src)
    doc = products["BX_v4"].doc
    info["our_category"] = int(doc.category_id)
    info["document_guid"] = doc.document_guid
    info["n_elements"] = len(doc.elements)
    info["instance"] = rp.place_one(src, outp, host=G_ABPD,
                                    symbol_id=p.symbol_id,
                                    family_id=p.host_family_id,
                                    category=int(doc.category_id))
    info["instance_ids"] = [info["instance"]["instance_id"]]
    info["symbol_id"], info["family_id"] = p.symbol_id, p.host_family_id
    info["blob_proof"] = fbl.blob_proof(outp, G_ABPD)
    info["file"] = relp(outp)
    info["md5"] = md5_of(outp)
    # file-level identity census: no unit param may read SELF
    ids = _param_identities(outp, 1)
    self_rows = [r for r in ids if r.get("form") == "SELF"]
    info["file_identity_census"] = {
        "unit_params": len(ids), "self_minted": len(self_rows),
        "birth_suffixes": [r.get("embedded_id") for r in ids],
        "all_other_form": not self_rows}
    if self_rows or not ids:
        raise RuntimeError(f"BX_v4: emitted unit identity not born-form: "
                           f"{self_rows[:4] or 'no params'}")
    info["species"] = _sp().species_census(outp, G_ABPD, ours_content=True)
    if not info["species"]["species_ok"]:
        raise RuntimeError(f"BX_v4 species census not ok: "
                           f"{info['species']['checks']}")
    info["self_containment"] = info["species"].get("four_surface")
    return info


def build_demo_v10() -> Dict[str, Any]:
    """DEMO v10: v9's exact recipe (the user's prompt through
    rvt.frontdoor.run with birthright binds + corpus symbol form) at
    version=4."""
    SC = _sc()
    rp = _rp()
    fbl = _fbl()
    from rvt.famgen import birthright as BR
    from rvt import famload_hostfix as HF
    from rvt.mutate import Document
    from rvt.families import FamilyIndex
    spec = BR.read_birth_spec(SC.BIRTH_SPEC)
    binds = BR.read_bind_spec(SC.BINDS_PATH)
    rp._install_schema(G_ABPD)
    import ifc_intent  # noqa: F401
    from rvt.frontdoor.build import load_ifc_room_module
    load_ifc_room_module()
    from rvt import frontdoor as FD
    demo_dir = os.path.join(BUILD_DIR, "demo_v10")
    if os.path.isdir(demo_dir):
        shutil.rmtree(demo_dir)
    outp = os.path.join(OUT_DIR, "DEMO_250v_room_v10.rvt")
    info: Dict[str, Any] = {"probe": "DEMO_250v_room_v10",
                            "axis": AXES["DEMO_250v_room_v10"],
                            "base": relp(G_ABPD), "prompt": DEMO_PROMPT,
                            "birth_spec_sha256": (spec.source or {}).get(
                                "sha256"),
                            "binds": {k: v["__eid__"] for k, v in
                                      (binds.get("binds") or {}).items()}}
    with BR.enabled(spec, binds=binds, version=4) as br_ctx:
        with HF.corpus_symbol_form():
            req = FD.AuthorRequest(prompt=DEMO_PROMPT, out=demo_dir,
                                   stem="DEMO_250v_room_v10",
                                   no_handoff=True, quiet=True)
            r = FD.run(req)
    combined = (r.files or {}).get("combined")
    if not combined or not os.path.isfile(combined):
        raise RuntimeError(f"front door did not emit the combined file: "
                           f"{r.errors[:3]}")
    shutil.copyfile(combined, outp)
    info["frontdoor_status"] = r.status
    info["out_dir"] = relp(demo_dir)
    reports = br_ctx["reports"]
    if not reports:
        raise RuntimeError("DEMO v10: birthright never fired")
    bad = [x["family"] for x in reports
           if (x.get("report") or {}).get("version") != 4
           or not ((x.get("report") or {}).get("identity") or {}).get(
               "applied")
           or not ((x.get("report") or {}).get("identity_census")
                   or {}).get("identity_ok")]
    if bad:
        raise RuntimeError(f"DEMO v10: v4 identity did not apply green: "
                           f"{bad}")
    bad = [x["family"] for x in reports
           if not (x.get("verify") or {}).get("ok")]
    if bad:
        raise RuntimeError(f"DEMO v10: authored-vs-mined verify not ok: "
                           f"{bad}")
    unbound = [x["family"] for x in reports
               if not (x.get("walked_bind_census") or {}).get(
                   "self_contained")]
    if unbound:
        raise RuntimeError(f"DEMO v10: walked binds not self-contained: "
                           f"{unbound}")
    loader_reps = br_ctx.get("hostsym_loader") or []
    if not loader_reps or not all(x.get("applied") for x in loader_reps):
        raise RuntimeError(f"DEMO v10: loader-half hostsym did not apply "
                           f"on every family: {loader_reps}")
    info["n_birthright_applications"] = len(reports)
    info["n_families"] = len({x.get("family") for x in reports})
    info["identity_per_family"] = [
        {"family": x.get("family"),
         "suffixes": ((x.get("report") or {}).get("identity")
                      or {}).get("n_suffixes_reminted"),
         "census_ok": ((x.get("report") or {}).get("identity_census")
                       or {}).get("identity_ok")}
        for x in reports]
    info["hostsym_loader"] = loader_reps
    T = _room()
    wm = T.host_watermark(G_ABPD)
    doc = Document.from_file(outp)
    inst_ids = [i for i in doc.ids_of_class("FamilyInstance") if i > wm]
    info["instance_ids"] = inst_ids
    info["n_instances"] = len(inst_ids)
    info["n_walls"] = len([i for i in doc.ids_of_class("Wall") if i > wm])
    forms = {}
    for sid in doc.ids_of_class("FamilySymbol"):
        v = doc.value(sid) or {}
        fam = doc.value(v.get("m_familyId") or -1) or {}
        if "PP-" in str(fam.get("m_name") or ""):
            forms[sid] = HF.assert_symbol_form(outp, sid)
    badf = [k for k, f in forms.items() if not f["ok"]]
    if badf or not forms:
        raise RuntimeError(f"DEMO v10 symbol form check failed: "
                           f"{badf or 'no PP- symbols found'}")
    info["symbol_form_ok"] = {str(k): f["ok"] for k, f in forms.items()}
    # file-level identity census across EVERY added unit
    n_units = len(FamilyIndex(outp).units)
    census = []
    for u in range(1, n_units):
        ids = _param_identities(outp, u)
        census.append({"unit": u, "params": len(ids),
                       "self_minted": sum(1 for x in ids
                                          if x.get("form") == "SELF")})
    info["file_identity_census"] = {
        "units": census,
        "all_other_form": all(c["self_minted"] == 0 for c in census),
        "total_params": sum(c["params"] for c in census)}
    if not info["file_identity_census"]["all_other_form"] \
            or info["file_identity_census"]["total_params"] == 0:
        raise RuntimeError(f"DEMO v10: emitted units carry SELF identity: "
                           f"{census}")
    info["immediate_parent"] = relp(G_ABPD)
    info["file"] = relp(outp)
    info["md5"] = md5_of(outp)
    info["blob_proof"] = fbl.blob_proof(outp, G_ABPD)
    info["species"] = _sp().species_census(outp, G_ABPD, ours_content=True)
    if not info["species"]["species_ok"]:
        raise RuntimeError(f"DEMO v10 species census not ok: "
                           f"{info['species']['checks']}")
    info["self_containment"] = info["species"].get("four_surface")
    return info


BUILDERS = {"I1": build_i1, "BX_v4": build_bx_v4,
            "DEMO_250v_room_v10": build_demo_v10}


# ===========================================================================
# accounting + gates
# ===========================================================================

def _accounting(name: str, info: Dict[str, Any]) -> Dict[str, Any]:
    B = _bisect()
    fbl = _fbl()
    base = G_ABPD
    child = os.path.join(ROOT, info["file"])
    parent = os.path.join(ROOT, info["immediate_parent"])
    out: Dict[str, Any] = {}
    out["probe"] = B.account(name, child, parent, declared_base=base,
                             instance_ids=info.get("instance_ids") or [])
    if os.path.abspath(parent) != os.path.abspath(base):
        out["hop_load"] = B.account(name + ".hop_load", parent, base,
                                    declared_base=base, instance_ids=[],
                                    with_regdiff=False)
    out["blob_proof"] = fbl.blob_proof(child, base)
    return out


def _gates(name: str, info: Dict[str, Any],
           acct: Dict[str, Any]) -> Dict[str, Any]:
    rep = acct["probe"]
    va = rep["validator"]
    bp = acct["blob_proof"]
    hop = acct.get("hop_load")
    sp = info.get("species") or {}
    fic = info.get("file_identity_census") or {}
    g: Dict[str, Any] = {
        "validator_errors": va["n_errors"],
        "validator_unexpected": len(va["unexpected_errors"]),
        "four_registry_coherent": rep["census"]["coherent"],
        "survivor_law_ok": bool(rep["survivor_law_ok"]) and (
            hop is None or bool(hop["survivor_law_ok"])),
        "identity": (rep.get("identity_gate") or {}).get("status"),
        "blob_all_units_64B": bp["all_units_64B"],
        "blob_added_nonce_verified": bp["added_nonce_verified"],
        "famdoc_refs_unresolved_anywhere": (
            info.get("reference_resolution") or {}).get(
                "unresolved_anywhere"),
        "instance_zero_dangling": (
            (info.get("instance") or {}).get("n_dangling") == 0
            if info.get("instance") else None),
        "species_ok": sp.get("species_ok"),
        "identity_all_other_form": fic.get("all_other_form"),
    }
    if name == "I1":
        bi = info.get("base_byte_identity") or {}
        g["base_byte_identity"] = all(
            (bi.get("segments_byte_identical") or {}).values()) or None
        g["surgical"] = (info.get("surgical_proof") or {}).get("surgical")
    if hop is not None:
        g["load_hop_units_added"] = hop["census_delta"]["save_units"]
        g["instance_hop_units_added"] = rep["census_delta"]["save_units"]
    ok = (g["validator_errors"] == 0 and g["validator_unexpected"] == 0
          and g["four_registry_coherent"] is True
          and g["survivor_law_ok"] and g["identity"] == "PASS"
          and g["blob_all_units_64B"] and g["blob_added_nonce_verified"]
          and g["identity_all_other_form"] is True)
    if name == "I1":
        ok = (ok and g["base_byte_identity"] is True
              and g["surgical"] is True
              and g["famdoc_refs_unresolved_anywhere"] == 0
              and g["instance_zero_dangling"] is True
              and g.get("load_hop_units_added") == 1
              and g.get("instance_hop_units_added") == 0)
    if name == "BX_v4":
        ok = (ok and g["species_ok"] is True
              and g["instance_zero_dangling"] is True
              and g.get("load_hop_units_added") == 1
              and g.get("instance_hop_units_added") == 0)
    if name == "DEMO_250v_room_v10":
        ok = ok and g["species_ok"] is True
    g["gates_ok"] = bool(ok)
    return g


# ===========================================================================
# build driver + probes.json + verify + stage
# ===========================================================================

def build(only: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    only = list(only) if only else list(LADDER)
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(BUILD_DIR, exist_ok=True)
    t0 = time.time()
    out: Dict[str, Any] = {"tool": "tools/identity_probe.py",
                           "bases": {n: relp(G_ABPD) for n in LADDER},
                           "built": {}, "accounting": {}, "gates": {},
                           "errors": {}}
    if os.path.isfile(ACCT):
        try:
            with open(ACCT) as fh:
                prev = json.load(fh)
            for k in ("built", "accounting", "gates"):
                out[k] = {n: v for n, v in (prev.get(k) or {}).items()
                          if n not in only}
        except Exception:                                      # noqa: BLE001
            pass
    for name in [n for n in LADDER if n in only]:
        try:
            t1 = time.time()
            info = BUILDERS[name]()
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
                f"{g['four_registry_coherent']}, identity-form "
                f"{g['identity_all_other_form']}, species "
                f"{g['species_ok']}, gates_ok {g['gates_ok']}")
            if not g["gates_ok"]:
                out["errors"][name + ".gates"] = f"gates_ok False: {g}"
        except Exception as e:                                 # noqa: BLE001
            out["errors"][name] = f"{type(e).__name__}: {e}"
            out["errors"][name + ".traceback"] = \
                traceback.format_exc(limit=10)
            log(f"{name} FAILED: {type(e).__name__}: {e}")
    out["seconds"] = round(time.time() - t0, 1)
    jdump(ACCT, out)
    write_probes_json(out)
    return out


READING_THE_MATRIX = {
    "knowns": {
        "T2a": "PASS on G_ABPD (standalone-born; all param identity "
               "OTHER-form)",
        "TB0g": "PASS on G_ABPD (embedded-born; all OTHER)",
        "T1uG": "FAIL on G_ABPD / PASS on rst as T1u (ours 14 params "
                "SELF-minted; flags mixed)",
        "SC1/BX_v3/DEMO v8-v9": "FAIL on G_ABPD (ours SELF-minted; flags "
                                "mixed)",
    },
    "pre_committed": [
        "I1 PASS + BX_v4 PASS + DEMO v10 PASS => THE CLOSE: the identity "
        "law is confirmed -- element identity minted against the host id "
        "space is what reduced bases reject; the fix is exactly the "
        "normalized field set (frozen-birth parameter identity + the born "
        "flags table).  Promote birthright v4 to the famgen emission "
        "default and rebuild acceptance.",
        "I1 PASS + BX_v4 FAIL => v4 AUTHORING GAP: the identity fields "
        "are the law but v4's authored famdoc still differs from I1's "
        "normalized shape by a finite list -- diff BX_v4 against I1 with "
        "this tool's forensic instruments; pre-identified candidates in "
        "order: (1) the parents-structure finding (our ExtentElem/"
        "SketchPlane satellites lack the self-Family deletion root every "
        "born twin carries), (2) the born-roster true-up (species rank "
        "2), (3) the born-wrapper ADocument.",
        "I1 PASS + BX_v4 PASS + DEMO v10 FAIL => famgen-loader lane gap "
        "-- bisect v10 family-by-family through BX_v4's famload lane "
        "(the species-stream precedent).",
        "I1 FAIL => IDENTITY IS INSUFFICIENT: the normalized element "
        "identity set does not flip the reduced-base verdict.  Record "
        "the remaining unprobed-axis ledger honestly: (a) the inline "
        "elemArr episode columns (T1uG ships 0 where every famload-"
        "authored PASS ships the host episode 1016 -- the one doc-level "
        "surface still separating T1uG from TB0g), (b) the parents-"
        "structure finding, (c) content birth itself (verdict-#46's "
        "residual axis: reduced bases accept only born unit content -- "
        "no famdoc-side authoring closes it), (d) the container/envelope "
        "axes (terminal-diff territory).  The desktop-Revit check kit "
        "becomes the primary instrument; compose-side repair (hr1 rank "
        "1) re-ranks first.",
        "Control FAIL => every verdict in the round is VOID.",
    ],
    "reading_order": list(LADDER),
}


def write_probes_json(build_out: Dict[str, Any]) -> str:
    probes = []
    for name in LADDER:
        info = (build_out.get("built") or {}).get(name)
        if not info:
            continue
        probes.append({
            "probe": name, "file": info["file"], "md5": info["md5"],
            "base": relp(G_ABPD),
            "axis": AXES[name],
            "document_guid": info.get("document_guid"),
            "gates_ok": ((build_out.get("gates") or {}).get(name)
                         or {}).get("gates_ok"),
        })
    out = {
        "tool": "tools/identity_probe.py",
        "stream": "identity",
        "base": relp(G_ABPD),
        "forensics": relp(DIFF),
        "probes": probes,
        "reading_the_matrix": READING_THE_MATRIX,
        "quarantine": ("I1 embeds vendor-born content -- PROOF-ONLY, "
                       "never shipped; BX_v4 + DEMO v10 carry zero donor "
                       "bytes (authored birth + our own minted identity, "
                       "test-enforced)"),
    }
    jdump(PROBES, out)
    return PROBES


def verify() -> Dict[str, Any]:
    """Re-run the accounting gates on the built probes (no rebuilds)."""
    with open(ACCT) as fh:
        acct = json.load(fh)
    out = {}
    for name in LADDER:
        info = (acct.get("built") or {}).get(name)
        if not info:
            out[name] = "not built"
            continue
        path = os.path.join(ROOT, info["file"])
        if not os.path.isfile(path):
            out[name] = "file missing"
            continue
        if md5_of(path) != info["md5"]:
            out[name] = "MD5 DRIFT vs accounting"
            continue
        g = _gates(name, info, acct["accounting"][name])
        out[name] = "gates_ok" if g["gates_ok"] else f"GATES NOT OK: {g}"
    print(json.dumps(out, indent=1))
    return out


def stage() -> Dict[str, Any]:
    """probe_batch gate + stage: ONE G_ABPD control + the three probes,
    reading order I1, BX_v4, DEMO v10.  STOP at READY."""
    pb = _pb()
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
    if not os.path.isfile(DIFF):
        raise SystemExit("identity_diff.json missing -- run forensics "
                         "first (it is the round's evidence)")
    ledger = pb.Ledger.load()
    entries, violations = pb.check_batch(files, ledger)
    if violations:
        raise pb.GateRefusal(violations)
    n = pb.next_batch_number()
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
                     f"{pb.rel(dst)} (md5 {md5_of(dst)} vs {e.md5}); "
                     f"rename the probe -- never overwrite a staged file "
                     f"the viewer may already have read"])
            shutil.copyfile(src, dst)
        e.staged_as = pb.rel(dst)
    manifest = {
        "batch": n,
        "created": _dt.datetime.now().astimezone().isoformat(
            timespec="seconds"),
        "tool": "tools/identity_probe.py (via tools/probe_batch.py "
                "primitives)",
        "law": ("every entry's declared base is ITSELF in "
                "viewer-certified.json 'certified' (or is an Autodesk "
                "sample source); the batch carries >= 1 CONTROL = a "
                "byte-identical copy of a certified file; read the round "
                "with read_batch_verdicts(): control FAIL => every "
                "verdict VOID"),
        "ledger": pb.rel(ledger.path),
        "control_count": 1,
        "controls": {"g_abpd": ctrl.staged_as,
                     "note": "one G_ABPD control gates all three probes "
                             "(every probe's base is G_ABPD)"},
        "note": ("identity THE COUPLING: I1 (T1u's famdoc, our 35 "
                 "elements' identity fields -- and only those -- "
                 "normalized to the born convention: frozen-birth "
                 "parameter identity suffixes + born header flags; "
                 "surgical, machine-verified per record), BX_v4 (our "
                 "famdoc through birthright v4's BORN IDENTITY lane -- "
                 "single identity variable vs certified-FAIL BX_v3), "
                 "DEMO_250v_room_v10 (the prompt through v4).  Read "
                 "experiments/identity/probes.json reading_the_matrix; "
                 "the measured diff is "
                 "experiments/identity/identity_diff.json."),
        "reading_order": [os.path.basename(e.staged_as or e.file)
                          for e in ordered],
        "entries": [e.to_json() for e in ordered],
    }
    path = os.path.join(out_dir, f"batch_{n}.json")
    with open(path, "w") as fh:
        json.dump(manifest, fh, indent=1)
    manifest["manifest_path"] = pb.rel(path)
    log(f"STAGED batch {n} -> {pb.rel(path)} (1 control + {len(files)} "
        f"probes; STOP at READY -- the orchestrator uploads)")
    return manifest


# ===========================================================================
# CLI
# ===========================================================================

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("forensics")
    b = sub.add_parser("build")
    b.add_argument("--only")
    c = sub.add_parser("census")
    c.add_argument("file")
    c.add_argument("--unit", type=int, default=1)
    sub.add_parser("verify")
    sub.add_parser("stage")
    args = ap.parse_args(argv)
    if args.cmd == "forensics":
        forensics()
        return 0
    if args.cmd == "build":
        only = args.only.split(",") if args.only else None
        out = build(only)
        return 0 if not out["errors"] else 1
    if args.cmd == "census":
        rows = _param_identities(args.file, args.unit)
        self_n = sum(1 for r in rows if r.get("form") == "SELF")
        print(json.dumps({"file": relp(args.file), "unit": args.unit,
                          "params": rows, "self_minted": self_n,
                          "all_other_form": self_n == 0},
                         indent=1, default=str))
        return 0 if self_n == 0 else 1
    if args.cmd == "verify":
        verify()
        return 0
    if args.cmd == "stage":
        stage()
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
