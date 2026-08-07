"""rvt.famload_hostfix -- THE CORPUS-LAWFUL INSTANCED-SYMBOL FORM (opt-in;
hostpair stream, 2026-08-05).

THE DEFECT THIS TARGETS (genesis-audit verdicts #32/#33 + the hostpair
H9/H10 binary): instances of OUR loaded families fail the viewer's
open-time audit on every base and path while the famdoc content itself is
exonerated (H7) -- the suspect surface is the host FamilySymbol the two
loaders author.  The corpus law, mined from ALL 201 instanced
FamilySymbols across rstbasic / rstadvanced / racbasic / rme
(experiments/hostpair/corpus_geometry_grammar.json, re-mineable via
``python -m rvt.famload_hostfix mine``):

  201/201  seq-103 rep = GElement, root ``GInfo.m_tag`` = the symbol id,
           rep ``m_flags`` = 2; the subNode roster never consists of a
           single GFilter (0/201) and ends with a bare empty ``Geometry``
           node on 193/201 (the other 8 end in GRichText label tails);
           dominant minimal shape, 71/201: empty GFilter + content
           GFilter + trailing empty Geometry.
  201/201  ``m_geomSteps`` = GeomStepList {m_idCounter 2,
           m_latestGStepTypeInPrevRegenCycle [2,2,2,2,2], every other
           list empty, every snapshot null} carrying exactly ONE
           ``BaseFamilySymbolGStep`` {m_id 1}; list m_flags 9 (104) or
           11 (97); step m_version in {7,4,3,6}, m_flags 761725 (150/201).
  201/201  ``m_pGeomTable`` = GeomTable {m_bigTableOwner null,
           m_refPntMirrored False}, one row per symbol-space id
           (m_geomGeneratorId 1 on 34,731 of 34,763 rows).
  201/201  ``m_refFaces`` is NON-EMPTY (min 9, max 82): plane Face
           objects whose ``GInfo.m_tag`` values are the step's type-6
           face-history rows ``[6, tag, -1]`` -- the family's REFERENCE
           PLANES projected into symbol space (measured on rstbasic
           876569: 9 faces == 9 type-6 rows, X/Y/Z plane grid; the
           origin-defining planes carry GInfo flags 2622116, others
           2622180).
  200/201  ``m_hasParamDefValue`` = 0.

WHAT THE TWO LOADERS AUTHOR TODAY (both off-corpus for instanced symbols):

  rvt.famload             SerializedDummy rep + m_geomSteps None +
                          m_pGeomTable None + m_refFaces [] +
                          m_hasParamDefValue 1  (the dummy+no-steps form
                          appears in NO sample file -- tolerated only
                          UNREFERENCED: L1a / L_v2 / L_downlight).
  rvt.famgen.loader       a one-specimen bake that violates three of the
                          mined invariants: rep = ONE GFilter with no
                          trailing empty Geometry node (0/201 corpus
                          support); the two type-6 history rows describe
                          GFilter/Geometry graph nodes instead of
                          reference faces; ``m_refFaces`` stays [] (0/201
                          corpus support).

THE FIX (this module): build the symbol geometry in the corpus-lawful
form -- famgen's proven face/edge/curve tagging pipeline PLUS (a) the
reference-face node rows with matching ``m_refFaces`` Face objects
authored from the family's origin RefPlanes + Ref. Level, (b) the
corpus rep roster (empty GFilter + content GFilter + trailing empty
Geometry), (c) ``m_hasParamDefValue`` 0 -- and graft it onto BOTH
loaders' symbols.

OPT-IN WIRING (default OFF everywhere -- no loader behaves differently
until a caller asks; the viewer verdict on batch 39 decides whether this
becomes the default):

    from rvt import famload_hostfix as HF

    with HF.corpus_symbol_form():          # the flag, famload_fix-style
        L.load_family_into_project(...)    # famgen path, symbols fixed
        FL.load_family_documents(...)      # famload path, symbols fixed

    HF.load_family_into_project(..., hostfix=True)   # convenience wrappers
    HF.load_family_documents(..., hostfix=True)

``corpus_symbol_form()`` patches ``rvt.famgen.loader.author_family_symbol``
and ``rvt.famload.author_family_symbols`` for the duration of the ``with``
block and reverts on exit (the same live-patch wiring rvt.famload_fix
established for D1..D5; the one-line permanent wiring into the loaders'
own signatures is deliberately NOT made until a viewer verdict blesses
the form).

HONEST LIMITS (recorded, not hidden):
  * the reference-face law is authored from TWO deep-read specimens
    (rstbasic 876569 minimal + the native column 1411287) plus the
    201-symbol invariant that m_refFaces is never empty; the corpus also
    carries form-derived reference faces (type-5 rows with GInfo flags
    2621668) that this module does NOT author -- our box family's datum
    set is 3 planes, below the corpus minimum count of 9 (which belongs
    to 3x3-grid families; the count is family-content-derived, not a
    constant).
  * step m_version 4 / list m_flags 9 are kept from famgen's bake (both
    corpus-attested: 72/201 and 104/201).
  * famload symbols beyond the FIRST type keep the dummy form (our
    products are single-type; a multi-type family gets a note).
  * a famload document with no authored ExtrusionElem solid (e.g. a
    foreign famdoc) keeps famload's dummy form untouched, with a note.
"""
from __future__ import annotations

import contextlib
import copy
import json
from typing import Any, Dict, List, Optional, Sequence, Tuple

INVALID = -1

#: GInfo flags of a reference Face [V rstbasic 876569 + 1411287]:
#: origin-defining planes 2622116, other datum planes (levels) 2622180.
REF_FACE_FLAGS_ORIGIN = 2622116
REF_FACE_FLAGS_DATUM = 2622180

#: the node shapes [V rstbasic 876569, byte-identical across the minimal
#: corpus shape]
GINFO_NEUTRAL = {"m_categoryId": -1, "m_tag": -1, "m_controlCommand": 0,
                 "m_flags": 557060}

#: the mined invariants (see module docstring; mine() re-derives them)
MINED = {
    "instanced_symbols": 201,
    "rep": {"class": "GElement", "flags": 2, "root_tag_is_self": "201/201",
            "trailing_empty_geometry": "193/201 (8 end in GRichText tails)",
            "single_gfilter_roster": "0/201"},
    "geom_steps": {"idCounter": 2, "latest": [2, 2, 2, 2, 2],
                   "one_BaseFamilySymbolGStep": "201/201", "step_id": 1,
                   "list_flags": {9: 104, 11: 97},
                   "step_version": {7: 98, 4: 72, 3: 21, 6: 10},
                   "step_flags_modal": 761725},
    "geom_table": {"bigTableOwner": None, "refPntMirrored": False,
                   "row": {"m_geomGeneratorId": 1},
                   "rows_equals_id_space": "183/201 exact"},
    "ref_faces": {"min": 9, "max": 82, "empty": "0/201",
                  "tags_are_type6_rows": "[V 876569: 9 == 9]"},
    "hasParamDefValue": {0: 200, 1: 1},
}


def _ptr(cls: str, value: dict, pid: int = -1) -> dict:
    return {"ptr_class": cls, "pid": pid, "value": value}


def _weak(ref: int) -> dict:
    return {"weakref": int(ref)}


# ---------------------------------------------------------------------------
# reference-face specs from the family document
# ---------------------------------------------------------------------------

def reference_specs(elements: Sequence[Any], lo: Sequence[float],
                    hi: Sequence[float]) -> List[Dict[str, Any]]:
    """The family's datum planes as symbol-space reference-face specs, in
    the corpus order (X planes, then Y, then Z) [V 876569's 3x3 grid runs
    X,X,X / Y,Y,Y / Z,Z,Z with the plane orientation laws below].

    Our families carry 2 origin RefPlanes (Is-Reference codes 1 =
    Center Left/Right = the constant-X plane, 4 = Center Front/Back =
    the constant-Y plane) + the Ref. Level (constant-Z at elevation 0).
    """
    lo = [float(x) for x in lo]
    hi = [float(x) for x in hi]
    have_x = have_y = have_level = False
    for e in elements:
        if e.class_name == "RefPlane" and (e.obj or {}).get("m_definesOrigin"):
            code = (e.obj or {}).get("m_refName")
            if code == 1:
                have_x = True
            elif code == 4:
                have_y = True
        elif e.class_name == "Level":
            have_level = True
    specs: List[Dict[str, Any]] = []
    if have_x:
        specs.append({
            "kind": "origin_plane_x", "flags": REF_FACE_FLAGS_ORIGIN,
            "origin": [0.0, 0.0, 0.0], "x_vec": [0.0, 1.0, 0.0],
            "y_vec": [0.0, 0.0, 1.0],
            "envelope": [[lo[1], lo[2]], [hi[1], hi[2]]]})
    if have_y:
        specs.append({
            "kind": "origin_plane_y", "flags": REF_FACE_FLAGS_ORIGIN,
            "origin": [0.0, 0.0, 0.0], "x_vec": [0.0, 0.0, 1.0],
            "y_vec": [1.0, 0.0, 0.0],
            "envelope": [[lo[2], lo[0]], [hi[2], hi[0]]]})
    if have_level:
        specs.append({
            "kind": "ref_level", "flags": REF_FACE_FLAGS_DATUM,
            "origin": [0.0, 0.0, 0.0], "x_vec": [1.0, 0.0, 0.0],
            "y_vec": [0.0, 1.0, 0.0],
            "envelope": [[lo[0], lo[1]], [hi[0], hi[1]]]})
    return specs


def _ref_face(tag: int, spec: Dict[str, Any]) -> dict:
    """One ``m_refFaces`` Face [V shape rstbasic 876569 refFaces[0]]."""
    return _ptr("Face", {
        "m_GInfo": {"m_categoryId": -1, "m_tag": int(tag),
                    "m_controlCommand": 0, "m_flags": int(spec["flags"])},
        "m_pFirstLoop": None,
        "m_faceRegions": [],
        "m_pGFilling": None,
        "m_oBackgroundFilling": None,
        "m_renderStyleId": -1,
        "m_cutType": 0,
        "m_faceFlags_v9": 0,
        "m_pSurf": _ptr("Plane", {
            "m_Envelope": {"m_corners": [list(spec["envelope"][0]),
                                         list(spec["envelope"][1])]},
            "m_orientFlag": True,
            "m_origin": list(spec["origin"]),
            "m_xVec": list(spec["x_vec"]),
            "m_yVec": list(spec["y_vec"]),
        }),
    })


def _empty_gfilter() -> dict:
    """[V 876569 subNodes[0]]"""
    return _ptr("GFilter", {"m_GInfo": dict(GINFO_NEUTRAL), "m_subNodes": [],
                            "m_oConditions": [],
                            "m_bIsNestedDetailFamily": False})


def _trailing_geometry() -> dict:
    """The bare Geometry node every corpus rep ends with [V 876569/1411287]."""
    return _ptr("Geometry", {
        "m_GInfo": dict(GINFO_NEUTRAL),
        "m_pFaces": [],
        "m_flags": 7,
        "m_geometryTag": -1,
        "m_tessEpsCntrl": {"m_type": 0, "m_TessEpsCntrlVersion": 1},
        "m_pEdges": [],
        "m_sharedSurfInfo": [],
    })


# ---------------------------------------------------------------------------
# the corpus-lawful symbol geometry builder
# ---------------------------------------------------------------------------

#: history-table entry types [V famgen.loader + the corpus rows]
HIST_EDGE = 3
HIST_FACE = 5
HIST_NODE = 6
HIST_FORM = 65


def build_corpus_symbol_geometry(form_rep: dict, *, absorbed_form_index: int,
                                 symbol_id: int, category_gstyle: int,
                                 ref_specs: Sequence[Dict[str, Any]],
                                 g_elem_type_default: int = 3) -> Dict[str, Any]:
    """The corpus-lawful three-surface symbol geometry from one authored
    solid ``GElement`` (the family form's seq-103 rep).

    famgen's proven pipeline (flat symbol id space; faces/edges retagged
    with symbol ids; type-5/3 rows mapping back to (kind, original tag,
    absorbed form index); the Geometry node's type-65 row) with the mined
    corrections: the leading type-6 rows are the family's REFERENCE FACES
    (one per datum plane, with a matching ``m_refFaces`` Face), and the
    rep roster is [empty GFilter, content GFilter, trailing bare Geometry].
    """
    if not ref_specs:
        raise ValueError("corpus law: m_refFaces is never empty on an "
                         "instanced symbol (0/201) -- the family document "
                         "carries no datum planes to author them from")
    solid = copy.deepcopy(form_rep)
    bb = solid.get("m_bBox") or solid.get("m_tightbBox")
    if not bb:
        raise ValueError("form rep carries no bbox")
    lo = [float(x) for x in bb[0]]
    hi = [float(x) for x in bb[1]]

    counter = [0]

    def nid() -> int:
        v = counter[0]
        counter[0] += 1
        return v

    # -- the reference-face node rows (ids 0..n-1) + m_refFaces -------------
    node_hist: List[dict] = []
    ref_faces: List[dict] = []
    for spec in ref_specs:
        rid = nid()
        node_hist.append({"m_id": rid, "m_faceHist": {
            "m_keys": [HIST_NODE, int(rid), -1]}})
        ref_faces.append(_ref_face(rid, spec))

    # -- retag the solid's faces / edges; record history --------------------
    face_hist: List[dict] = []
    edge_hist: List[dict] = []
    geom_nodes = [x for x in (solid.get("m_subNodes") or [])
                  if isinstance(x, dict) and x.get("ptr_class") == "Geometry"]
    if not geom_nodes:
        raise ValueError("form rep carries no Geometry node")
    curve_entry = None
    for gnode in geom_nodes:
        gv = gnode.get("value") or {}
        for f in gv.get("m_pFaces") or []:
            fv = f.get("value") or {}
            gi = fv.get("m_GInfo") or {}
            tag = gi.get("m_tag", -1)
            sid = nid()
            gi["m_tag"] = sid
            gi["m_categoryId"] = -1
            fv["m_GInfo"] = gi
            face_hist.append({"m_id": sid, "m_faceHist": {
                "m_keys": [HIST_FACE, int(tag), int(absorbed_form_index)]}})
        for ed in gv.get("m_pEdges") or []:
            ev = ed.get("value") or {}
            gi = ev.get("m_GInfo") or {}
            tag = gi.get("m_tag", -1)
            sid = nid()
            gi["m_tag"] = sid
            gi["m_categoryId"] = -1
            ev["m_GInfo"] = gi
            edge_hist.append({"m_id": sid, "m_edgeHist": {
                "m_keys": [HIST_EDGE, int(tag), int(absorbed_form_index), -1]}})
        gtag = nid()
        gv["m_geometryTag"] = gtag
        curve_entry = {"m_id": gtag, "m_curveHist": {
            "m_keys": [HIST_FORM, int(absorbed_form_index), -1, -1, -1]}}
        ggi = gv.get("m_GInfo") or {}
        ggi["m_categoryId"] = -1
        ggi["m_tag"] = -1
        ggi["m_controlCommand"] = 32768                # solid node [V specimen]
        gv["m_GInfo"] = ggi
    n_ids = counter[0]

    # -- the rep: [empty GFilter, content GFilter, trailing Geometry] -------
    root_flags = int((solid.get("m_GInfo") or {}).get("m_flags", 557060))
    content_gfilter = _ptr("GFilter", {
        "m_GInfo": {"m_categoryId": -1, "m_tag": -1, "m_controlCommand": 0,
                    "m_flags": root_flags},
        "m_subNodes": [x for x in solid.get("m_subNodes") or []],
        "m_oConditions": [],
        "m_bIsNestedDetailFamily": False,
    })
    rep = {
        "m_GInfo": {"m_categoryId": int(category_gstyle
                                        if category_gstyle != INVALID else -1),
                    "m_tag": int(symbol_id), "m_controlCommand": 0,
                    "m_flags": root_flags},
        "m_subNodes": [_empty_gfilter(), content_gfilter, _trailing_geometry()],
        "m_bBox": [lo, hi],
        "m_tightbBox": [lo, hi],
        "m_elementId": int(symbol_id),
        "m_gElemType": int(solid.get("m_gElemType", g_elem_type_default)),
        "m_flags": int(solid.get("m_flags", 2)),
    }

    # -- geomSteps + geomTable [famgen's lawful constants kept] -------------
    step = _ptr("BaseFamilySymbolGStep", {
        "m_faceHistTable": node_hist + face_hist,
        "m_curveHistTableSet": [curve_entry] if curve_entry else [],
        "m_edgeHistTable": edge_hist,
        "m_edgeHistTableReverse": [],
        "m_id": 1,
        "m_version": 4,
        "m_flags": 761725,
        "m_pElem": _weak(2),
        "m_oExtraDatas": None,
    })
    geom_steps = _ptr("GeomStepList", {
        "m_nonBRepGList": [],
        "m_bRepFormGList": [step],
        "m_bRepAdjustGList": [],
        "m_bRepCutOutGList": [],
        "m_bRepPostCutOutGList": [],
        "m_bRepTweakGList": [],
        "m_bRepFormSnapshot": None,
        "m_bRepAdjustSnapshot": None,
        "m_bRepCutOutSnapshot": None,
        "m_bRepPostCutOutSnapshot": None,
        "m_pElem": _weak(2),
        "m_latestGStepTypeInPrevRegenCycle": [2, 2, 2, 2, 2],
        "m_idCounter": 2,
        "m_flags": 9,
    })
    geom_table = _ptr("GeomTable", {
        "m_refPntMirrored": False,
        "m_table": [{"m_geomGeneratorId": 1} for _ in range(n_ids)],
        "m_bigTableOwner": None,
        "m_materialMarkers": [],
        "m_faceTypeMarkers": [],
    })
    return {
        "rep": rep,
        "geom_steps": geom_steps,
        "geom_table": geom_table,
        "ref_faces": ref_faces,
        "bbox": (lo, hi),
        "geometry_tag": (curve_entry or {}).get("m_id", -1),
        "n_symbol_ids": n_ids,
        "history": {"ref_nodes": len(node_hist), "faces": len(face_hist),
                    "edges": len(edge_hist),
                    "curves": 1 if curve_entry else 0,
                    "geom_table_rows": n_ids},
    }


# ---------------------------------------------------------------------------
# grafting the form onto an authored symbol element
# ---------------------------------------------------------------------------

def apply_to_symbol(el, form_el, *, absorbed_form_index: int,
                    category_gstyle: int, note: str) -> Dict[str, Any]:
    """Graft the corpus-lawful geometry onto one authored ``FamilySymbol``
    SkelElement IN PLACE (works on famgen's baked symbol and famload's
    dummy alike).  Returns the build summary."""
    from .famgen.geometry import assign_pids
    if form_el is None or form_el.rep is None:
        raise ValueError("no authored solid rep to build symbol geometry from")
    bb = form_el.rep.get("m_bBox") or form_el.rep.get("m_tightbBox")
    specs = None
    doc_elements = getattr(el, "_hostfix_doc_elements", None)
    if doc_elements is None:
        raise ValueError("apply_to_symbol needs the family document elements "
                         "(set el._hostfix_doc_elements)")
    specs = reference_specs(doc_elements, bb[0], bb[1])
    bundle = build_corpus_symbol_geometry(
        form_el.rep, absorbed_form_index=absorbed_form_index,
        symbol_id=el.elem_id, category_gstyle=category_gstyle,
        ref_specs=specs)
    o = el.obj
    o["m_geomSteps"] = bundle["geom_steps"]
    o["m_pGeomTable"] = bundle["geom_table"]
    o["m_refFaces"] = bundle["ref_faces"]
    o["m_geomTag2MaterialId"] = [{"first": int(bundle["geometry_tag"]),
                                  "second": -1}]
    o["m_hasParamDefValue"] = 0                       # 200/201 instanced law
    lo, hi = bundle["bbox"]
    o["m_outline"] = {"m_minmax": [list(lo), list(hi)]}
    cx = (lo[0] + hi[0]) / 2.0
    cy = (lo[1] + hi[1]) / 2.0
    o["m_origin"] = [cx, cy, 0.0]
    o["m_rotCenter"] = [cx, cy, 0.0]
    el.rep = bundle["rep"]
    assign_pids(o)
    assign_pids(el.rep)
    el.notes.append(note)
    # refresh the header bbox to the geometry extents
    hv = el.header
    if isinstance(hv, dict) and "m_pBBox" in hv:
        bbv = hv.get("m_pBBox")
        if isinstance(bbv, dict) and isinstance(bbv.get("value"), dict):
            bbv["value"]["m_minmax"] = [list(lo), list(hi)]
    return {"applied": True, "history": bundle["history"],
            "geometry_tag": bundle["geometry_tag"],
            "n_symbol_ids": bundle["n_symbol_ids"],
            "n_ref_faces": len(bundle["ref_faces"])}


# ---------------------------------------------------------------------------
# the opt-in wiring (famload_fix-style live patches; default OFF)
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def corpus_symbol_form(*, fix_famgen: bool = True, fix_famload: bool = True):
    """Author corpus-lawful instanced-symbol geometry on BOTH loaders for
    the duration of the ``with`` block (reverted on exit; nothing outside
    the block changes -- the opt-in flag, default OFF)."""
    from .famgen import loader as L
    from . import famload as FL

    saved: List[tuple] = []

    def patch(obj, name, fn):
        saved.append((obj, name, getattr(obj, name)))
        setattr(obj, name, fn)

    if fix_famgen:
        orig_sym = L.author_family_symbol

        def sym_fixed(product, plan, host, type_rows, **kw):
            el, geo = orig_sym(product, plan, host, type_rows, **kw)
            if geo is None:                    # the solid=False variant: keep
                el.notes.append("famload_hostfix: no-solid variant untouched")
                return el, geo
            form = L._form_bundle(product)                     # noqa: SLF001
            ai = plan.abs_index.get(form.elem_id)
            el._hostfix_doc_elements = list(product.doc.elements)  # noqa: SLF001
            rep = apply_to_symbol(
                el, form, absorbed_form_index=int(ai),
                category_gstyle=int(host.category_gstyle),
                note="famload_hostfix: corpus-lawful symbol form (ref-face "
                     "node rows + m_refFaces + trailing Geometry roster; "
                     "201-symbol mined law)")
            del el._hostfix_doc_elements
            geo = dict(geo or {})
            geo["hostfix"] = rep
            return el, geo
        patch(L, "author_family_symbol", sym_fixed)

    if fix_famload:
        orig_syms = FL.author_family_symbols

        def syms_fixed(doc, plan):
            els = orig_syms(doc, plan)
            form = next((e for e in doc.elements
                         if e.class_name == "ExtrusionElem"
                         and e.rep is not None), None)
            if form is None:
                for el in els:
                    el.notes.append("famload_hostfix: document carries no "
                                    "authored ExtrusionElem solid -- dummy "
                                    "form kept")
                return els
            ai = plan.abs_index.get(form.elem_id)
            if ai is None:
                for el in els:
                    el.notes.append("famload_hostfix: form has no absorbed "
                                    "index -- dummy form kept")
                return els
            gstyle = plan.core_ids[0] if plan.core_ids else INVALID
            for i, el in enumerate(els):
                if i > 0:
                    el.notes.append("famload_hostfix: non-first type symbol "
                                    "keeps the dummy form (single-type law)")
                    continue
                el._hostfix_doc_elements = list(doc.elements)  # noqa: SLF001
                apply_to_symbol(
                    el, form, absorbed_form_index=int(ai),
                    category_gstyle=int(gstyle),
                    note="famload_hostfix: corpus-lawful symbol form over "
                         "famload's dummy (GElement + geomSteps + geomTable "
                         "+ refFaces; hasParamDefValue 0)")
                del el._hostfix_doc_elements
            return els
        patch(FL, "author_family_symbols", syms_fixed)

    try:
        yield
    finally:
        for obj, name, fn in reversed(saved):
            setattr(obj, name, fn)


def load_family_into_project(*args, hostfix: bool = False, **kw):
    """``rvt.famgen.loader.load_family_into_project`` with the opt-in
    ``hostfix`` flag (default OFF = byte-identical behaviour)."""
    from .famgen import loader as L
    if not hostfix:
        return L.load_family_into_project(*args, **kw)
    with corpus_symbol_form(fix_famload=False):
        return L.load_family_into_project(*args, **kw)


def load_family_documents(*args, hostfix: bool = False, **kw):
    """``rvt.famload.load_family_documents`` with the opt-in ``hostfix``
    flag (default OFF = byte-identical behaviour)."""
    from . import famload as FL
    if not hostfix:
        return FL.load_family_documents(*args, **kw)
    with corpus_symbol_form(fix_famgen=False):
        return FL.load_family_documents(*args, **kw)


# ---------------------------------------------------------------------------
# assertions (machine-checkable form of the mined law, for tests + gates)
# ---------------------------------------------------------------------------

def assert_symbol_form(path: str, symbol_id: int) -> Dict[str, Any]:
    """Read ``symbol_id`` back from the emitted file and prove the corpus
    form: GElement rep ending in a bare Geometry node, GeomStepList with
    one BaseFamilySymbolGStep, table rows == id space, non-empty refFaces
    whose tags == the type-6 rows, hasParamDefValue 0."""
    from .mutate import Document
    doc = Document.from_file(path)
    v = doc.value(symbol_id) or {}
    rep = doc.value(symbol_id, 103) or {}
    out: Dict[str, Any] = {"symbol": symbol_id}
    checks: Dict[str, bool] = {}
    checks["rep_is_GElement"] = doc.class_of(symbol_id, 103) == "GElement"
    subs = rep.get("m_subNodes") or []
    last = subs[-1] if subs else {}
    lastv = (last.get("value") or {}) if isinstance(last, dict) else {}
    checks["rep_trailing_bare_geometry"] = (
        isinstance(last, dict) and last.get("ptr_class") == "Geometry"
        and not (lastv.get("m_pFaces") or []) and not (lastv.get("m_pEdges") or []))
    checks["rep_roster_not_single_gfilter"] = len(subs) >= 2
    checks["root_tag_is_self"] = ((rep.get("m_GInfo") or {}).get("m_tag")
                                  == symbol_id)
    gs = ((v.get("m_geomSteps") or {}).get("value") or {})
    steps = gs.get("m_bRepFormGList") or []
    checks["one_step"] = (len(steps) == 1 and steps[0].get("ptr_class")
                          == "BaseFamilySymbolGStep")
    checks["idCounter_2"] = gs.get("m_idCounter") == 2
    sv = (steps[0].get("value") or {}) if steps else {}
    fh = sv.get("m_faceHistTable") or []
    eh = sv.get("m_edgeHistTable") or []
    ch = sv.get("m_curveHistTableSet") or []
    node_tags = [r.get("m_id") for r in fh
                 if ((r.get("m_faceHist") or {}).get("m_keys") or [None])[0] == 6]
    gt = ((v.get("m_pGeomTable") or {}).get("value") or {})
    checks["table_rows_eq_id_space"] = (len(gt.get("m_table") or [])
                                        == len(fh) + len(eh) + len(ch))
    rf = v.get("m_refFaces") or []
    checks["ref_faces_nonempty"] = len(rf) > 0
    rf_tags = [((f.get("value") or {}).get("m_GInfo") or {}).get("m_tag")
               for f in rf]
    checks["ref_face_tags_are_node_rows"] = sorted(rf_tags) == sorted(node_tags)
    checks["hasParamDefValue_0"] = v.get("m_hasParamDefValue") == 0
    out["checks"] = checks
    out["counts"] = {"subs": len(subs), "faceHist": len(fh),
                     "edgeHist": len(eh), "curveHist": len(ch),
                     "table": len(gt.get("m_table") or []),
                     "refFaces": len(rf)}
    out["ok"] = all(checks.values())
    return out


# ---------------------------------------------------------------------------
# the miner (re-derive the corpus law from the samples)
# ---------------------------------------------------------------------------

def mine(out_path: Optional[str] = None) -> Dict[str, Any]:
    """Re-mine the instanced-symbol geometry grammar from the four samples
    (the numbers in MINED / the module docstring).  Read-only."""
    import collections
    import os
    from .mutate import Document
    root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         "..", ".."))
    samples = [os.path.join(root, "samples", n) for n in
               ("rstbasicsampleproject.rvt", "rstadvancedsampleproject.rvt",
                "racbasicsampleproject.rvt", "rmebasicsampleproject.rvt")]
    rows: List[Dict[str, Any]] = []
    for s in samples:
        doc = Document.from_file(s)
        used: collections.Counter = collections.Counter()
        for iid in doc.ids_of_class("FamilyInstance"):
            ms = (doc.value(iid) or {}).get("m_masterSymbolId")
            if isinstance(ms, int) and ms > 0:
                used[ms] += 1
        for sid in doc.ids_of_class("FamilySymbol"):
            if not used.get(sid):
                continue
            v = doc.value(sid) or {}
            rep = doc.value(sid, 103) or {}
            gs = ((v.get("m_geomSteps") or {}).get("value") or {})
            gt = ((v.get("m_pGeomTable") or {}).get("value") or {})
            steps = gs.get("m_bRepFormGList") or []
            subs = [x.get("ptr_class") for x in (rep.get("m_subNodes") or [])
                    if isinstance(x, dict)]
            rows.append({
                "sample": os.path.basename(s), "symbol": sid,
                "rep_class": doc.class_of(sid, 103),
                "trailing_geometry": bool(subs) and subs[-1] == "Geometry",
                "n_subs": len(subs),
                "n_steps": len(steps),
                "step_class": (steps[0].get("ptr_class") if steps else None),
                "list_flags": gs.get("m_flags"),
                "idCounter": gs.get("m_idCounter"),
                "step_version": ((steps[0].get("value") or {}).get("m_version")
                                 if steps else None),
                "n_table": len(gt.get("m_table") or []),
                "n_ref_faces": len(v.get("m_refFaces") or []),
                "hasParamDefValue": v.get("m_hasParamDefValue"),
                "root_tag_is_self": ((rep.get("m_GInfo") or {}).get("m_tag")
                                     == sid),
            })
    agg = {
        "instanced_symbols": len(rows),
        "rep_GElement": sum(1 for r in rows if r["rep_class"] == "GElement"),
        "trailing_geometry": sum(1 for r in rows if r["trailing_geometry"]),
        "single_subnode": sum(1 for r in rows if r["n_subs"] < 2),
        "one_step": sum(1 for r in rows if r["n_steps"] == 1),
        "idCounter_2": sum(1 for r in rows if r["idCounter"] == 2),
        "ref_faces_empty": sum(1 for r in rows if r["n_ref_faces"] == 0),
        "ref_faces_min": min((r["n_ref_faces"] for r in rows), default=None),
        "hasParamDef_0": sum(1 for r in rows if r["hasParamDefValue"] == 0),
        "root_tag_is_self": sum(1 for r in rows if r["root_tag_is_self"]),
        "list_flags": dict(collections.Counter(r["list_flags"] for r in rows)),
        "step_version": dict(collections.Counter(r["step_version"] for r in rows)),
    }
    out = {"law": "see module docstring / MINED", "samples": len(samples),
           "aggregate": agg, "rows": rows}
    if out_path:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".",
                    exist_ok=True)
        with open(out_path, "w") as fh:
            json.dump(out, fh, indent=1, default=str)
    return out


if __name__ == "__main__":                             # pragma: no cover
    import sys as _sys
    if len(_sys.argv) > 1 and _sys.argv[1] == "mine":
        rep = mine("experiments/hostpair/corpus_geometry_grammar.json")
        print(json.dumps(rep["aggregate"], indent=1, default=str))
    else:
        print(__doc__)
