"""layout_law -- the famdoc PHYSICAL-LAYOUT normalization pass (layout-law
stream, post-verdict-#40).  OPT-IN, default OFF: nothing in the default
emission pipeline calls this module; a caller applies it explicitly between
``finalize()`` and delivery (``to_rfa`` / the loader), the same injection
point SUB_O1 used.

WHAT IT DOES
------------
``normalize_doc(doc, order="donor_frame_first")`` renumbers the finalized
document's element ids (a pure bijection over the SAME id block, the
famgen loader's own conservative int-walk) so that ascending-id order --
which is the writer's physical record order (``build_unit_segments`` sorts
by elem id) -- follows the record-order convention of the MEASURED PASS
matched-pair anchor SUB_ALL:

    self-Family,
    project Viewer, DBViewProject, DBDrawing, Viewport   (donor sequence),
    UnitsElem,
    then every remaining element in famgen allocation order.

This mirrors exactly what the M1 morph probe does to F1's emitted unit
(tools/layout_diff.py), with monotone ids -- the shape SUB_ALL (PASS)
exhibits.  ``normalize_order_cell(doc)`` separately applies the M3 fix:
the self-Family FamilyParamsOrderCell merged to ONE group per group-type id
(famgen's finalize emits user identityData params and built-in ids as TWO
groups with the same key -- no measured PASS file carries a duplicate key)
with electrical before-last and identity groups merged in place.

EVIDENCE STATUS (read layout_diff.json + docs/inbox/layout-law.md before
turning this on): the record-order axis is corpus-EXONERATED as a sole law
(SUB_O1 FAIL carries a donor-convention order; B7 PASS carries the donor's
native order) -- this pass exists so the M1/BX probes' convention is
authorable the moment a morph verdict demands it, not because the corpus
already does.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .loader import _walk_replace_ids
from .skeleton import param_type_id

__all__ = ["ORDER_CONVENTIONS", "layout_order_ids", "normalize_doc",
           "normalize_order_cell"]

#: the supported order conventions.  "off" is the explicit no-op (the
#: default pipeline behaviour: famgen allocation order).
ORDER_CONVENTIONS = ("off", "donor_frame_first")

_LOCALFAM_RE = re.compile(
    r"^(revit\.local\.family:[0-9a-f]{32})([0-9a-f]{8})(-.+)$")


def _frame_roles(doc) -> Dict[str, Any]:
    """The six frame elements of a finalized famgen famdoc, by role.
    Raises when the document does not carry the standard constellation
    (a caller on an exotic document should not silently half-normalize)."""
    els = list(doc.elements)
    by_id = {e.elem_id: e for e in els}
    fam = doc.self_family
    if fam is None:
        raise ValueError("layout_law: document has no self-Family")
    proj = next((e for e in els if e.class_name == "DBViewProject"), None)
    if proj is None:
        raise ValueError("layout_law: no DBViewProject (project view) -- "
                         "the donor_frame_first convention needs the view "
                         "constellation (with_views=True)")
    viewer = next((e for e in els if e.class_name == "Viewer"
                   and e.owner_id == proj.elem_id), None)
    drawing = next((e for e in els if e.class_name == "DBDrawing"
                    and e.owner_id == proj.elem_id), None)
    viewport = None
    if drawing is not None:
        viewport = next((e for e in els if e.class_name == "Viewport"
                         and e.owner_id == drawing.elem_id), None)
    units = next((e for e in els if e.class_name == "UnitsElem"), None)
    missing = [n for n, e in (("proj_viewer", viewer), ("proj_drawing", drawing),
                              ("proj_viewport", viewport), ("units", units))
               if e is None]
    if missing:
        raise ValueError(f"layout_law: frame roles missing: {missing}")
    assert fam.elem_id in by_id
    return {"self_family": fam, "proj_viewer": viewer, "proj_view": proj,
            "proj_drawing": drawing, "proj_viewport": viewport, "units": units}


def layout_order_ids(doc, order: str = "donor_frame_first") -> List[int]:
    """The element ids of ``doc`` in the target PHYSICAL record order.

    donor_frame_first (the SUB_ALL / M1 convention): self-Family, project
    Viewer, DBViewProject, DBDrawing, Viewport, UnitsElem, then everything
    else in current ascending-id (famgen allocation) order.
    """
    if order not in ORDER_CONVENTIONS:
        raise ValueError(f"unknown order convention {order!r}; "
                         f"one of {ORDER_CONVENTIONS}")
    ids = sorted(e.elem_id for e in doc.elements)
    if order == "off":
        return ids
    roles = _frame_roles(doc)
    head = [roles[r].elem_id for r in ("self_family", "proj_viewer",
                                       "proj_view", "proj_drawing",
                                       "proj_viewport", "units")]
    head_set = set(head)
    return head + [i for i in ids if i not in head_set]


def _heal_param_type_ids(doc) -> int:
    """Re-derive every ParamElemFamily's ``revit.local.family:`` type id
    from its (possibly renumbered) element id, keeping the family GUID part.
    The project loader rewrites these at load time anyway; the standalone
    .rfa path serializes the baked strings, so a renumbering pass must heal
    them [measured law: suffix == own element id, 8 hex, in every corpus
    famdoc]."""
    healed = 0
    for e in doc.elements:
        if e.class_name != "ParamElemFamily":
            continue
        pd = ((e.obj.get("m_pParamDef") or {}).get("value") or {})
        tt = pd.get("m_typeId")
        cur = (tt or {}).get("m_typeId") if isinstance(tt, dict) else None
        if not isinstance(cur, str):
            continue
        m = _LOCALFAM_RE.match(cur)
        if not m:
            continue
        want = f"{m.group(1)}{e.elem_id & 0xFFFFFFFF:08x}{m.group(3)}"
        if want != cur:
            tt["m_typeId"] = want
            healed += 1
    return healed


def normalize_doc(doc, *, order: str = "donor_frame_first") -> Dict[str, Any]:
    """Renumber the FINALIZED document's element ids so ascending-id order
    (== the writer's physical record order) follows ``order``.  A pure
    bijection over the document's existing id block: the id SET is
    unchanged, every id occurrence in headers/objects/reps is remapped
    (conservative int-walk), owner links and the doc's cached view ids
    follow, and id-embedded ``revit.local.family`` suffixes are re-derived.

    Returns a report (n_moved, permutation, class orders).  ``order="off"``
    is a recorded no-op.  Idempotent for a given convention.
    """
    if order not in ORDER_CONVENTIONS:
        raise ValueError(f"unknown order convention {order!r}")
    if not getattr(doc, "finalized", False):
        raise ValueError("layout_law.normalize_doc wants a FINALIZED doc "
                         "(registries are seeded at finalize; renumbering "
                         "before would go stale)")
    els = list(doc.elements)
    order_before = [(e.elem_id, e.class_name)
                    for e in sorted(els, key=lambda e: e.elem_id)]
    target_ids = layout_order_ids(doc, order)
    ordered_ids = sorted(e.elem_id for e in els)
    by_id = {e.elem_id: e for e in els}
    ranked = [by_id[i] for i in target_ids]
    perm = {e.elem_id: ordered_ids[i] for i, e in enumerate(ranked)}
    if sorted(perm) != sorted(perm.values()):
        raise RuntimeError("layout_law: permutation is not a bijection on "
                           "the id block")
    moved = sum(1 for a, b in perm.items() if a != b)
    if moved:
        for e in els:
            _walk_replace_ids(e.header, perm)
            _walk_replace_ids(e.obj, perm)
            if e.rep is not None:
                _walk_replace_ids(e.rep, perm)
            if (e.owner_id or 0) > 0:
                e.owner_id = perm.get(e.owner_id, e.owner_id)
            e.elem_id = perm[e.elem_id]
        doc.elements.sort(key=lambda e: e.elem_id)
        if getattr(doc, "plan_view_id", None) in perm:
            doc.plan_view_id = perm[doc.plan_view_id]
        for k, v in list(getattr(doc, "view_ids", {}).items()):
            if v in perm:
                doc.view_ids[k] = perm[v]
    healed = _heal_param_type_ids(doc)
    order_after = [(e.elem_id, e.class_name) for e in doc.elements]
    return {"order": order, "n_elements": len(els), "n_moved": moved,
            "param_type_ids_healed": healed,
            "permutation": {str(k): v for k, v in sorted(perm.items())},
            "class_order_before": [c for _i, c in order_before],
            "class_order_after": [c for _i, c in order_after]}


def normalize_order_cell(doc) -> Dict[str, Any]:
    """The M3 fix: the self-Family FamilyParamsOrderCell reduced to ONE
    group per group-type id (duplicate-key groups merged into the first
    occurrence, param id sequences concatenated in place) and re-ranked
    with identityData/electrical last exactly as the measured PASS
    convention orders them (dimensions < identityData < electrical).
    Content-preserving: the multiset of param ids is unchanged."""
    fam = doc.self_family
    cells = (((fam.obj.get("m_cellList") or {}).get("value") or {})
             .get("m_cells") or [])
    report = {"cells": 0, "merged_groups": 0, "order_before": [],
              "order_after": []}
    for c in cells:
        cv = (c.get("value") or {}) if isinstance(c, dict) else {}
        sp = cv.get("m_sortedParams")
        if not isinstance(sp, list):
            continue
        report["cells"] += 1

        def key_of(g: Dict[str, Any]) -> str:
            return str((g.get("m_groupTypeId") or {}).get("m_typeId"))
        before_ids = [pid for g in sp for pid in (g.get("m_paramIds") or [])]
        report["order_before"] = [key_of(g) for g in sp]
        merged: List[Dict[str, Any]] = []
        by_key: Dict[str, Dict[str, Any]] = {}
        for g in sp:
            k = key_of(g)
            if k in by_key:
                by_key[k].setdefault("m_paramIds", []).extend(
                    g.get("m_paramIds") or [])
                report["merged_groups"] += 1
            else:
                by_key[k] = g
                merged.append(g)

        def rank(g: Dict[str, Any]) -> int:
            tid = key_of(g)
            if "electrical" in tid:
                return 2
            if "identity" in tid.lower():
                return 1
            return 0
        merged.sort(key=rank)
        sp[:] = merged
        after_ids = [pid for g in sp for pid in (g.get("m_paramIds") or [])]
        if sorted(before_ids) != sorted(after_ids):
            raise RuntimeError("normalize_order_cell changed the param id "
                               "multiset -- refusing")
        report["order_after"] = [key_of(g) for g in sp]
        break                                     # first order cell only
    return report
