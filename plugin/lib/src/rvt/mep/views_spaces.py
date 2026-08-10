"""views_spaces.py — PANEL SCHEDULE VIEWS + MEP SPACES / ROOMS / SPACE TAGS.

The deliverable-facing electrical elements: a project that arrives WITH its
panel schedules and named/numbered spaces is a finished deliverable, not a
model.  Everything here is decoded from the ``rmebasicsampleproject``
corpus (Revit 2026) and follows the writer's clone-and-patch recipe
(``docs/writer/mutation-plan.md``); the full spec is
``docs/writer/mep-views-spaces.md``.

Ground truth (rme):

* ``PanelScheduleView`` (class 0x0b48, ``TableView > DBView > Element``)
  is the SCHEDULE VIEW.  It names its panel by ``TableView.m_targetId``
  (the panel ``FamilyInstance``), its layout by ``m_idTemplate`` (a
  ``PanelScheduleTemplate``: 638860 'Branch Panel', 638863 'Data Panel',
  638864 'Switchboard', ...), carries ``m_viewName`` = the panel name and a
  freshness flag ``m_outOfDate``.  Its ~150 KB ``m_oTableData`` is the
  table LAYOUT (4 ``TableSectionData`` sections: header 10 rows, body =
  circuit rows, summary, footer) with label texts and parameter BINDINGS
  (cellType 2 cells carry ``m_paramId`` = -1140078 Panel Name, -1140053
  CKT, -1140054 Circuit Description, ...) — but ZERO stored VALUES:
  every ``TableCellData.m_oCalculatedValue`` is null and the body data
  cells' ``m_text`` is "".  Circuit descriptions / loads / phase totals are
  COMPUTED BY REVIT ON OPEN from the panel's circuits.  Creating the view
  element (rewired to a panel) is therefore sufficient — Revit renders the
  table.  A view is an 8-element CLUSTER: the ``PanelScheduleView`` + the
  elements it OWNS through ``Global/ElemTable.m_OwningElementId``:
  ``Viewer`` (m_dbViewId -> view), ``DBDrawing`` (m_viewports), the
  ``Viewport`` (owned by the drawing), 2-4 ``FontElem``, one
  ``CategoryElem`` + its ``GStyleElem`` (the per-view colour override in
  ``m_colorToCategoryIdMap``).  ``m_fontIds`` / ``m_dbDrawingId`` /
  ``m_viewerId`` point into the cluster.  The panel's OWN ElementHeader
  lists the view in ``m_parents.m_regenOnly`` (742670 -> 742926).
* An MEP **Space** is a ``RoomElem`` (class 0x0ec8, category OST_MEPSpaces
  -2003600); architectural rooms are the same class with OST_Rooms
  -2000160.  Location is a POINT (``m_point`` xy, elevation from
  ``m_levelId``); the volume is COMPUTED by Revit from bounding walls at
  room-computation time.  Stored caches: ``m_volumeBoundingElems`` (the
  ``RoomBoundingItem`` walls), ``m_referenceFaces`` (2 horizontal planes at
  the point: base z and base+upperOffset, tags 226/227), a ``GElement``
  solid rep, per-space ``LevelRoomPlan`` topology circuit ``m_cachedCircuitId``,
  load/airflow doubles, ``m_loadPerLoadClass``.  Name/number = element
  AString params -1006900 / -1006901 (BuiltInParameter ROOM_NAME /
  ROOM_NUMBER).  Spaces are ZONED: ``m_zoneElementId`` -> a ``ZoneElement``
  whose ``m_spaceIds`` lists its members (two-sided; the project's Default
  zone 293242 lists nothing).  ``m_pPlacement`` (``RoomTagPlacement``)
  anchors the point to two bounding walls: ``m_ref0/1`` = wall ids,
  ``m_offset0/1`` = the signed perpendicular distance from each wall's
  location line, positive to the RIGHT of the drawing direction
  (``(P - start) . (dy, -dx)``; verified on space 379575 vs walls
  573608/573607).
* A **Space Tag** is a ``RoomTag`` (class 0x0ecc) with category
  OST_MEPSpaceTags -2000485 (87 in rme), owned by the plan view it is
  drawn in (``m_ownerDBViewId`` = a ``DBViewPlan``), pointing at the space
  via ``m_taggedRoomElemId.m_linkInstOrHostId``, at the tag symbol via
  ``m_symbolId`` (351633 'Space Tag'), head at the space point
  (``m_oTagOrientationCell.m_headLocation``), placement mirroring the
  space's ``RoomTagPlacement``.

Public API (all creation functions return planned
:class:`rvt.mutate.NewElement` objects registered on the Document; write
them with :func:`commit_elements` or ``rvt.commit.commit_new_elements``)::

    from rvt.mutate import Document
    from rvt.mep import views_spaces as vs

    doc   = Document.from_file("template.rvt")
    panel = doc.add_family_instance(619617, level, position=...)      # NEW panel
    view  = vs.add_panel_schedule_view(doc, panel, name="LP-9")        # 8 NewElements
    walls = [doc.add_wall(...), ...]                                   # a closed room
    zone  = vs.add_zone(doc, name="Electrical")
    space = vs.add_space(doc, level, (x, y), name="ELEC RM", number="101",
                         bounding_walls=walls, zone=zone)
    tag   = vs.add_space_tag(doc, space)
    vs.commit_elements(src, out, doc)                                  # -> proof file

    # existing elements (edit session -> rvt.manipulate.commit_plans):
    vs.rename_space(doc, 379575, name="STORAGE", number="199")
    vs.rename_panel_schedule_view(doc, 709455, "LP-1 REV")
    vs.delete_space(doc, 379575)                 # + its tag (annotation cascade)
    vs.delete_panel_schedule_view(doc, 709455)   # + its owned 7-element cluster

Nothing in ``mutate.py`` / ``commit.py`` / ``manipulate.py`` is edited by
this module (a create-path ownership hook is proposed in the record).
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from ..mutate import Document, NewElement

__all__ = [
    # panel schedule views
    "find_panel_schedule_view_specimen", "owned_cluster",
    "add_panel_schedule_view", "rename_panel_schedule_view",
    "delete_panel_schedule_view", "link_schedule_view_into_existing_panel",
    "panel_schedule_templates", "describe_panel_schedule_view",
    # spaces / rooms / zones / tags
    "find_space_specimen", "add_zone", "add_space", "add_room",
    "add_space_tag", "rename_space", "delete_space", "describe_space",
    "space_tags_of", "placement_from_walls",
    # writing
    "commit_elements",
]

# ---------------------------------------------------------------------------
# constants (all decoded from the rme corpus; see docs/writer/mep-views-spaces.md)
# ---------------------------------------------------------------------------
CLASS_PANEL_SCHEDULE_VIEW = 0x0B48
CLASS_PANEL_SCHEDULE_TEMPLATE = 0x0B45
CLASS_ROOM_ELEM = 0x0EC8            # RoomElem: rooms AND MEP spaces
CLASS_ROOM_TAG = 0x0ECC             # RoomTag: room tags AND space tags
CLASS_ZONE_ELEMENT = 0x11E4

OST_Rooms = -2000160
OST_RoomTags = -2000480
OST_MEPSpaceTags = -2000485
OST_MEPSpaces = -2003600
OST_HVACZones = -2008107
OST_PanelScheduleGraphics = -2001118

BIP_ROOM_NAME = -1006900             # AString element param (spaces + rooms)
BIP_ROOM_NUMBER = -1006901           # AString element param
BIP_RBS_ELEC_PANEL_NAME = -1140078   # 'Panel Name' (schedule header cell + instance param)
BIP_ZONE_NAME = -1114300             # [hypothesis] the ZoneElement AString param ("1"/"0")

#: seq-101 category of a PanelScheduleView header (OST_PanelScheduleGraphics)
SPACE_KIND_CATEGORY = {"space": OST_MEPSpaces, "room": OST_Rooms}


# ---------------------------------------------------------------------------
# generic helpers
# ---------------------------------------------------------------------------
def _remap_all(v: Any, mapping: Dict[int, int]) -> None:
    """Rewrite EVERY int equal to an old element id, anywhere in the tree.

    ``mutate.Document._remap_ids`` only rewrites values under ``*Id*`` keys;
    the schedule-view cluster stores ids under keys like ``"second"``
    (``m_colorToCategoryIdMap`` pairs) and inside plain lists
    (``m_fontIds``, ``m_viewports``, ``m_spaceIds``), so a full-tree remap is
    required.  All old ids are >= 100,000, far above any topology tag /
    slot number / connector index, so a value collision is impossible.
    """
    if isinstance(v, dict):
        for k in list(v.keys()):
            x = v[k]
            if isinstance(x, int) and not isinstance(x, bool) and x in mapping:
                v[k] = mapping[x]
            elif isinstance(x, (dict, list)):
                _remap_all(x, mapping)
    elif isinstance(v, list):
        for i, x in enumerate(v):
            if isinstance(x, int) and not isinstance(x, bool) and x in mapping:
                v[i] = mapping[x]
            elif isinstance(x, (dict, list)):
                _remap_all(x, mapping)


def _elem_id_of(x) -> int:
    """An element handle -> id (NewElement, id, or a plan carrying elem_id)."""
    if isinstance(x, NewElement):
        return x.elem_id
    if hasattr(x, "elem_id"):
        return int(x.elem_id)
    return int(x)


def _is_planned(doc: Document, eid: int) -> Optional[NewElement]:
    for e in doc.new_elements:
        if e.elem_id == eid:
            return e
    return None


def _owner_index(doc: Document) -> Dict[int, List[int]]:
    """owner id -> [owned element ids] from Global/ElemTable.m_OwningElementId."""
    idx = getattr(doc, "_owner_index_cache", None)
    if idx is None:
        idx = {}
        big = 0xFFFFFFFFFFFFFFFF
        for eid, rec in doc.et_by_id.items():
            own = rec.owner_id
            if own not in (None, big) and own >= 0:
                idx.setdefault(own, []).append(eid)
        for lst in idx.values():
            lst.sort()
        doc._owner_index_cache = idx
    return idx


def owned_cluster(doc: Document, root_id: int, max_depth: int = 6) -> List[int]:
    """``root_id`` followed by every element it (transitively) OWNS through
    the ElemTable ownership relation, breadth first, in ascending id order
    per depth.  A ``PanelScheduleView`` cluster is view -> {Viewer,
    DBDrawing, FontElem*, CategoryElem} -> {Viewport (owned by DBDrawing),
    GStyleElem (owned by CategoryElem)}."""
    owners = _owner_index(doc)
    out = [root_id]
    frontier = [root_id]
    depth = 0
    seen = {root_id}
    while frontier and depth < max_depth:
        nxt = []
        for cur in frontier:
            for kid in owners.get(cur, ()):
                if kid not in seen:
                    seen.add(kid)
                    out.append(kid)
                    nxt.append(kid)
        frontier = nxt
        depth += 1
    return out


def _class_id_of(doc: Document, eid: int, seq: int = 102) -> int:
    r = doc.record(eid, seq)
    if r is None:
        raise LookupError(f"element {eid} has no seq-{seq} record")
    return r.class_id


def _astring_param(obj: dict, param_id: int) -> Optional[str]:
    h = obj.get("m_pParamValueSetAString")
    pset = ((h or {}).get("value") or {}).get("m_paramSet") if isinstance(h, dict) else None
    for p in pset or []:
        if isinstance(p, dict) and p.get("m_paramId") == param_id:
            return p.get("m_value")
    return None


def _set_astring_param(obj: dict, param_id: int, value: str) -> None:
    from ..manipulate import upsert_param_row
    upsert_param_row(obj, param_id, value, holder="m_pParamValueSetAString")


def _instance_param_str(obj: dict, param_id: int) -> Optional[str]:
    """A string parameter from a FamilyInstance's m_pInstParams (or its
    element AString set)."""
    h = obj.get("m_pInstParams")
    params = ((h or {}).get("value") or {}).get("m_params") if isinstance(h, dict) else None
    for p in params or []:
        if isinstance(p, dict) and p.get("m_paramId") == param_id and isinstance(p.get("m_str"), str):
            return p["m_str"]
    return _astring_param(obj, param_id)


def _fresh_parents(header: dict) -> dict:
    """The header's ElementParents dict, with every list present (empty)."""
    holder = header.get("m_parents")
    if not isinstance(holder, dict):
        holder = {"ptr_class": "ElementParents", "pid": -1, "value": {}}
        header["m_parents"] = holder
    par = holder.get("value")
    if not isinstance(par, dict):
        par = {}
        holder["value"] = par
    for k in ("m_deletion", "m_regenOnly", "m_regenWildcards",
              "m_nonDetermRegenChildren", "m_dependencyParents",
              "m_appearanceParents", "m_deferredParents",
              "m_deferredPropagationParents", "m_computedParametersParents"):
        par.setdefault(k, [])
    par.setdefault("m_hasNonDetermRegenChildren", False)
    return par


def _register(doc: Document, els: Sequence[NewElement]) -> None:
    for e in els:
        doc.new_elements.append(e)


# ===========================================================================
# PANEL SCHEDULE VIEWS
# ===========================================================================
def panel_schedule_templates(doc: Document) -> List[dict]:
    """Host-document ``PanelScheduleTemplate``s: id, name, target category
    (-2008145 branch panel / -2008146 switchboard / -2008147 data panel)."""
    out = []
    for tid in doc.ids_of_class("PanelScheduleTemplate"):
        v = doc.value(tid) or {}
        out.append({"id": tid, "name": v.get("m_name"),
                    "category": v.get("m_categoryId")})
    return out


def _schedule_views(doc: Document) -> List[int]:
    return doc.ids_of_class("PanelScheduleView")


def find_panel_schedule_view_specimen(doc: Document,
                                      template_id: Optional[int] = None) -> int:
    """A real ``PanelScheduleView`` to clone (its whole owned cluster comes
    along).  Preference: a view already using ``template_id`` (so the cloned
    table layout matches the template), then the SMALLEST owned cluster
    (MDP-1 742926 = 8 elements, 2 fonts), then the smallest object."""
    views = _schedule_views(doc)
    if not views:
        raise LookupError(f"{doc.project}: no PanelScheduleView specimen to clone "
                          "(the template project needs at least one panel schedule)")
    scored = []
    for vid in views:
        v = doc.value(vid) or {}
        tpl = v.get("m_idTemplate")
        rec = doc.record(vid)
        cluster = owned_cluster(doc, vid)
        scored.append((0 if (template_id is not None and tpl == template_id) else 1,
                       len(cluster), rec.body_size if rec else 0, vid))
    scored.sort()
    return scored[0][3]


def _panel_display_name(doc: Document, panel) -> Optional[str]:
    """The panel's 'Panel Name' parameter (BIP_RBS_ELEC_PANEL_NAME), from
    a planned NewElement or an existing FamilyInstance."""
    if isinstance(panel, NewElement):
        obj = panel.obj
    else:
        pe = _is_planned(doc, _elem_id_of(panel))
        obj = pe.obj if pe is not None else (doc.value(_elem_id_of(panel)) or {})
    return _instance_param_str(obj or {}, BIP_RBS_ELEC_PANEL_NAME)


def add_panel_schedule_view(doc: Document, panel, *,
                            template: Optional[int] = None,
                            name: Optional[str] = None,
                            out_of_date: bool = True,
                            specimen_id: Optional[int] = None) -> List[NewElement]:
    """Create a panel schedule VIEW for ``panel`` and return its element
    cluster ``[view, viewer, drawing, viewport, fonts..., category, gstyle]``
    (the view first) as planned NewElements.

    ``panel``: a NEW panelboard planned in this same session (a
    ``NewElement`` from ``add_family_instance`` / ``hosting``) OR the id of
    an existing panel.  ``template``: an existing ``PanelScheduleTemplate``
    id (default: the specimen view's template — 'Branch Panel').  ``name``:
    the view name (default: the panel's Panel Name parameter, like Revit).
    ``out_of_date``: sets ``PanelScheduleView.m_outOfDate`` and clears the
    slot cache — the honest state for a schedule whose panel's circuits are
    not the specimen's: Revit's schedule updater regenerates the table
    (rows follow the panel's slots) when the file is opened.  Pass
    ``out_of_date=False`` to keep the cloned slot cache as-is (control
    variant).

    The specimen view's ENTIRE owned cluster is cloned with a full id remap
    (specimen panel -> ``panel``), so every internal cross reference
    (m_dbDrawingId / m_viewerId / m_fontIds / m_colorToCategoryIdMap /
    Viewer.m_dbViewId / DBDrawing.m_viewports / ownership) closes over the
    new ids.  If ``panel`` is planned in this session its header gets the
    view added to ``m_parents.m_regenOnly`` (the corpus back-link, e.g.
    panel 742670 -> view 742926); for an EXISTING panel use
    :func:`link_schedule_view_into_existing_panel` in an edit pass.
    """
    panel_id = _elem_id_of(panel)
    planned_panel = panel if isinstance(panel, NewElement) else _is_planned(doc, panel_id)
    if planned_panel is None and not doc.exists(panel_id):
        raise LookupError(f"panel {panel_id} does not exist in template {doc.project}")
    if planned_panel is None and doc.class_of(panel_id) != "FamilyInstance":
        raise TypeError(f"panel {panel_id} is a {doc.class_of(panel_id)!r}, "
                        "not a FamilyInstance panelboard")
    if template is not None:
        if not doc.exists(template):
            raise LookupError(f"panel schedule template {template} not in template file")
        if doc.class_of(template) != "PanelScheduleTemplate":
            raise TypeError(f"element {template} is a {doc.class_of(template)!r}, "
                            "not a PanelScheduleTemplate")

    donor = specimen_id or find_panel_schedule_view_specimen(doc, template)
    dv = doc.value(donor)
    if not dv:
        raise LookupError(f"specimen PanelScheduleView {donor} did not decode")
    donor_target = dv.get("m_targetId")
    cluster = owned_cluster(doc, donor)

    # ---- id allocation + mapping (donor -> new), donor panel -> our panel
    mapping: Dict[int, int] = {}
    for old in cluster:
        mapping[old] = doc.next_id()
    if isinstance(donor_target, int) and donor_target > 0:
        mapping[donor_target] = panel_id
    new_view_id = mapping[donor]

    # ---- clone every cluster member --------------------------------------
    els: List[NewElement] = []
    for old in cluster:
        cls_id = _class_id_of(doc, old)
        cls_name = doc.class_of(old) or "?"
        obj = copy.deepcopy(doc.value(old, 102))
        header = copy.deepcopy(doc.value(old, 101) or {})
        rep = None
        r103 = doc.record(old, 103)
        d103 = doc.decode(old, 103) if r103 is not None else None
        if d103 is not None and d103.clean and doc.class_of(old, 103) == "GElement":
            rep = copy.deepcopy(d103.value)
        if obj is None or not header:
            raise LookupError(f"schedule-view cluster member {old} did not decode")
        _remap_all(obj, mapping)
        _remap_all(header, mapping)
        if rep is not None:
            _remap_all(rep, mapping)
        header["m_regenHistory"] = {"m_historyMap": []}
        obj["m_id"] = mapping[old]
        # ownership: preserve the cluster's OWNER links (fonts/viewer/drawing
        # owned by the view; viewport by the drawing; gstyle by the category)
        rec = doc.et_by_id.get(old)
        owner = -1
        if rec is not None and rec.owner_id not in (None, 0xFFFFFFFFFFFFFFFF):
            owner = mapping.get(rec.owner_id, rec.owner_id)
        er = doc._new_elemrec(mapping[old])
        er.owner_id = owner
        kind = ("panel_schedule_view" if old == donor
                else f"schedule_view_{cls_name.lower()}")
        els.append(NewElement(mapping[old], kind, cls_name, cls_id, header, obj,
                              rep, er, old,
                              notes=[f"cloned from {cls_name} {old} of schedule-view "
                                     f"cluster {donor} (owner {rec.owner_id if rec else '?'} "
                                     f"-> {owner})"]))

    # ---- the view itself: rewire to the new panel -------------------------
    view = els[0]
    vobj = view.obj
    vobj["m_targetId"] = panel_id                 # (also set via mapping when donor_target)
    if template is not None:
        vobj["m_idTemplate"] = template
    view_name = name or _panel_display_name(doc, panel) or f"Panel {panel_id}"
    vobj["m_viewName"] = str(view_name)
    vobj["m_dependentViewIds"] = []
    vobj["m_outOfDate"] = bool(out_of_date)
    if out_of_date:
        vobj["m_cachedSlotNumbers"] = []          # regenerated from the panel's slots
    view.notes.append(
        f"PanelScheduleView for panel {panel_id} (template "
        f"{vobj.get('m_idTemplate')}, name {view_name!r}); table cell VALUES are "
        f"computed by Revit on open (stored table = layout + param bindings, all "
        f"m_oCalculatedValue null); m_outOfDate={bool(out_of_date)}")

    # ---- back-link: a planned panel lists its schedule view in regenOnly ---
    if planned_panel is not None:
        par = _fresh_parents(planned_panel.header)
        if new_view_id not in par["m_regenOnly"]:
            par["m_regenOnly"] = sorted(set(par["m_regenOnly"]) | {new_view_id})
        planned_panel.notes.append(f"header m_regenOnly += schedule view {new_view_id}")
    else:
        view.notes.append(
            f"panel {panel_id} EXISTS in the template: its ElementHeader is not "
            "edited by the create path — add the view to its m_regenOnly with "
            "link_schedule_view_into_existing_panel() in an edit pass")

    _register(doc, els)
    return els


def link_schedule_view_into_existing_panel(doc: Document, panel_id: int, view_id: int):
    """Edit pass for an EXISTING panel: append ``view_id`` to the panel's
    ElementHeader ``m_parents.m_regenOnly`` (the corpus back-link a panel
    keeps to its schedule view).  Returns an ``rvt.manipulate.ModifyPlan``
    on the panel's seq-101 header; commit it (with commit_plans) on the
    file that already contains the view."""
    from .. import manipulate
    hv = doc.value(panel_id, 101) or {}
    par = ((hv.get("m_parents") or {}).get("value")) or {}
    regen = list(par.get("m_regenOnly") or [])
    if view_id not in regen:
        regen = sorted(set(regen) | {int(view_id)})
    return manipulate.modify_element(
        doc, panel_id, {"m_parents.value.m_regenOnly": regen}, seq=101,
        kind="link-schedule-view",
        reason=f"panel {panel_id}: regenOnly += schedule view {view_id}")


def rename_panel_schedule_view(doc: Document, view_id: int, name: str):
    """Rename an existing panel schedule view (``DBView.m_viewName``).
    Returns an ``rvt.manipulate.ModifyPlan``."""
    from .. import manipulate
    if doc.class_of(view_id) != "PanelScheduleView":
        raise TypeError(f"element {view_id} is a {doc.class_of(view_id)!r}, "
                        "not a PanelScheduleView")
    return manipulate.modify_element(doc, view_id, {"m_viewName": str(name)},
                                     kind="rename-schedule-view",
                                     reason=f"rename schedule view {view_id} -> {name!r}")


def delete_panel_schedule_view(doc: Document, view_id: int, *, cascade: bool = True):
    """Delete an existing panel schedule view.  Its owned cluster (viewer,
    drawing, viewport, fonts, category, style) are ElemTable-OWNED dependents
    and go with it; the panel's header mention (m_regenOnly) is neutralised
    as a referrer.  Returns an ``rvt.manipulate.DeletePlan``."""
    from .. import manipulate
    if doc.class_of(view_id) != "PanelScheduleView":
        raise TypeError(f"element {view_id} is a {doc.class_of(view_id)!r}, "
                        "not a PanelScheduleView")
    return manipulate.delete_element(doc, view_id, cascade=cascade)


def describe_panel_schedule_view(doc: Document, view_id: int) -> dict:
    """Readback: the fields that define a panel schedule view + its cluster."""
    v = doc.value(view_id) or {}
    cluster = owned_cluster(doc, view_id)
    return {
        "id": view_id, "class": doc.class_of(view_id),
        "name": v.get("m_viewName"), "target_panel": v.get("m_targetId"),
        "template": v.get("m_idTemplate"), "out_of_date": v.get("m_outOfDate"),
        "cached_slots": len(v.get("m_cachedSlotNumbers") or []),
        "fonts": v.get("m_fontIds"), "drawing": v.get("m_dbDrawingId"),
        "viewer": v.get("m_viewerId"),
        "color_category": [p.get("second") for p in (v.get("m_colorToCategoryIdMap") or [])
                           if isinstance(p, dict)],
        "cluster": [(e, doc.class_of(e)) for e in cluster],
    }


# ===========================================================================
# SPACES / ROOMS
# ===========================================================================
def find_space_specimen(doc: Document, level_id: Optional[int] = None,
                        kind: str = "space") -> int:
    """A real, PLACED space (RoomElem cat -2003600) or room (-2000160) to
    clone; prefer the same level, then the smallest object."""
    want = SPACE_KIND_CATEGORY[kind]
    cands = []
    for eid in doc.ids_of_class("RoomElem"):
        if doc.category_of(eid) != want:
            continue
        v = doc.value(eid) or {}
        if v.get("m_bIsLocationless"):
            continue
        same = 0 if (level_id is not None and v.get("m_levelId") == level_id) else 1
        rec = doc.record(eid)
        cands.append((same, rec.body_size if rec else 1 << 30, eid))
    if not cands:
        raise LookupError(f"{doc.project}: no placed {kind} (RoomElem cat {want}) "
                          "specimen to clone")
    cands.sort()
    return cands[0][2]


def space_tags_of(doc: Document, space_id: int) -> List[int]:
    """Existing RoomTag elements pointing at ``space_id``."""
    out = []
    for tid in doc.ids_of_class("RoomTag"):
        v = doc.value(tid) or {}
        tr = (v.get("m_taggedRoomElemId") or {})
        if tr.get("m_linkInstOrHostId") == space_id:
            out.append(tid)
    return out


def placement_from_walls(doc: Document, point, walls: Sequence) -> dict:
    """Build a ``RoomTagPlacement`` for ``point`` anchored to two bounding
    walls: ``m_offset_i`` = signed distance from wall_i's location line,
    positive to the RIGHT of its drawing direction ``((P-start).(dy,-dx))``
    — verified on space 379575 (offsets -4.5589 / +7.3944 vs walls
    573608 / 573607).  Picks the two walls whose directions are most
    perpendicular (nearest first).  No walls -> refs -1, offsets 0."""
    from .. import hosting
    px, py = float(point[0]), float(point[1])
    infos = []
    for w in walls or ():
        try:
            g = hosting.wall_geometry(doc, w)
        except Exception:
            continue
        dx, dy = g.dir
        off = (px - g.start[0]) * dy + (py - g.start[1]) * (-dx)
        infos.append({"id": g.wall_id, "dir": (dx, dy), "offset": off,
                      "adist": abs(off)})
    plc = {"m_offset0": 0.0, "m_offset1": 0.0, "m_ref0": -1, "m_ref1": -1}
    if not infos:
        return plc
    infos.sort(key=lambda i: i["adist"])
    a = infos[0]
    # the most perpendicular partner (|cross| max), nearest as tie-break
    best, best_key = None, None
    for b in infos[1:]:
        cross = abs(a["dir"][0] * b["dir"][1] - a["dir"][1] * b["dir"][0])
        key = (round(-cross, 6), b["adist"])
        if best_key is None or key < best_key:
            best, best_key = b, key
    plc["m_ref0"], plc["m_offset0"] = a["id"], a["offset"]
    if best is not None:
        plc["m_ref1"], plc["m_offset1"] = best["id"], best["offset"]
    else:
        plc["m_ref1"], plc["m_offset1"] = a["id"], a["offset"]
    return plc


def add_zone(doc: Document, *, name: Optional[str] = None,
             level_id: Optional[int] = None,
             template_id: Optional[int] = None,
             phase_id: Optional[int] = None) -> NewElement:
    """Create a NEW HVAC ``ZoneElement`` (member list starts empty; spaces
    are appended by :func:`add_space` with ``zone=<this NewElement>``).

    Cloned from a real member-holding zone (rme 379574).  Calculated loads /
    perimeter are zeroed (Revit recomputes); ``m_bDefault`` is False (the
    project's Default zone 293242 is unique).  ``name`` sets the zone's
    AString parameter -1114300 [hypothesis: the zone name field].
    """
    tpl = template_id
    if tpl is None:
        best = None
        for zid in doc.ids_of_class("ZoneElement"):
            v = doc.value(zid) or {}
            if v.get("m_bDefault"):
                continue
            n = len(v.get("m_spaceIds") or [])
            key = (0 if n > 0 else 1, n, zid)
            if best is None or key < best[0]:
                best = (key, zid)
        if best is None:
            raise LookupError(f"{doc.project}: no ZoneElement specimen to clone")
        tpl = best[1]
    tv = doc.value(tpl)
    if not tv:
        raise LookupError(f"zone specimen {tpl} did not decode")
    zid = doc.next_id()
    obj = copy.deepcopy(tv)
    obj["m_id"] = zid
    obj["m_spaceIds"] = []
    if level_id is not None:
        obj["m_assocLevelId"] = level_id
    if phase_id is not None:
        obj["m_phaseId"] = phase_id
    obj["m_bDefault"] = False
    for k in list(obj.keys()):
        if k.startswith("m_dCalculated") or k in ("m_perimeter",):
            obj[k] = 0.0 if not k.endswith("Flow") else -1.0
    obj["m_dCalculatedHydronicCoolingFlow"] = -1.0
    obj["m_dCalculatedHydronicHeatingFlow"] = -1.0
    obj["m_ptPointXYZ"] = [0.0, 0.0, 0.0]
    obj["m_bRefPointDefined"] = False
    if name is not None:
        _set_astring_param(obj, BIP_ZONE_NAME, str(name))

    header = copy.deepcopy(doc.value(tpl, 101) or {})
    header["m_regenHistory"] = {"m_historyMap": []}
    par = _fresh_parents(header)
    lvl = obj.get("m_assocLevelId", -1)
    phase = obj.get("m_phaseId", -1)
    scheme = obj.get("m_zoneSchemeId", -1)
    deletion = {zid}
    for x in (lvl, phase, scheme):
        if isinstance(x, int) and x > 0:
            deletion.add(x)
    par["m_deletion"] = sorted(deletion)
    par["m_appearanceParents"] = sorted({p for p in par.get("m_appearanceParents") or []
                                          if doc.exists(p) and doc.class_of(p) != "RoomElem"}
                                         | ({lvl} if isinstance(lvl, int) and lvl > 0 else set()))
    par["m_regenOnly"] = [p for p in par.get("m_regenOnly") or [] if doc.exists(p)]
    for k in ("m_regenWildcards", "m_nonDetermRegenChildren", "m_dependencyParents",
              "m_deferredParents", "m_deferredPropagationParents",
              "m_computedParametersParents"):
        par[k] = []
    par["m_hasNonDetermRegenChildren"] = False
    header["m_pBBox"] = None

    el = NewElement(zid, "zone", "ZoneElement", _class_id_of(doc, tpl), header,
                    obj, None, doc._new_elemrec(zid), tpl,
                    notes=[f"HVAC zone cloned from ZoneElement {tpl}; member list "
                           "starts empty (spaces append themselves); loads/"
                           "perimeter zeroed (recomputed by Revit)"])
    doc.new_elements.append(el)
    return el


def add_space(doc: Document, level_id: int, point,
              name: Optional[str] = None, number: Optional[str] = None, *,
              upper_offset: Optional[float] = None,
              upper_level_id: Optional[int] = None,
              lower_offset: float = 0.0,
              bounding_walls: Sequence = (),
              zone: Union[str, int, NewElement, None] = "new",
              room_id: int = -1,
              phase_id: Optional[int] = None,
              kind: str = "space",
              template_id: Optional[int] = None) -> NewElement:
    """Create an MEP SPACE (``kind='space'``) or an architectural ROOM
    (``kind='room'``) as a POINT-placed ``RoomElem`` whose extents Revit
    computes from the bounding elements at room-computation time (the same
    regeneration model as walls: the object carries the regeneration recipe
    ``m_geomSteps``; the seq-103 rep is a SerializedDummy).

    ``point``: the location point (x, y) in project feet — must lie
    INSIDE the enclosing walls (Revit floods from this point).
    ``upper_offset``: height of the space above the level (default: the
    specimen's, typically level-to-level); ``bounding_walls``: the walls
    (existing ids or same-run NewElements) that enclose the space — used
    for the ``m_volumeBoundingElems`` cache, the ``RoomTagPlacement``
    anchors and the header's deletion parents (empty is allowed: Revit
    finds the walls itself, but the point must still be enclosed).
    ``zone``: 'new' (default: a fresh :func:`add_zone` per space session,
    shared by later calls with ``zone=<that NewElement>``), a NewElement
    zone, an EXISTING zone id (its member list is NOT edited — the create
    path never edits existing records; pair it with a modify pass), or
    None / -1 for no zone (how rooms are stored).  ``room_id``: the
    architectural room the space sits in (``m_SpaceRoomLocationInfo``),
    -1 when there is none.

    Name / number = the ROOM_NAME (-1006900) / ROOM_NUMBER (-1006901)
    AString parameters (also the rename path).  Load / airflow caches are
    zeroed and the plan-topology circuit cache invalidated — all recomputed
    by Revit.
    """
    if kind not in SPACE_KIND_CATEGORY:
        raise ValueError("kind must be 'space' or 'room'")
    if not doc.exists(level_id):
        raise LookupError(f"level {level_id} not in template {doc.project}")
    tpl = template_id or find_space_specimen(doc, level_id, kind=kind)
    tv = doc.value(tpl)
    if not tv:
        raise LookupError(f"space specimen {tpl} did not decode")
    px, py = float(point[0]), float(point[1])
    base_z = doc._level_elevation(level_id)

    sid = doc.next_id()
    obj = copy.deepcopy(tv)
    obj["m_id"] = sid
    obj["m_levelId"] = level_id
    obj["m_assocLevelId"] = level_id
    obj["m_upperLevelId"] = upper_level_id if upper_level_id is not None else level_id
    obj["m_point"] = [px, py]
    obj["m_famId"] = -1
    obj["m_designOptionId"] = -1
    obj["m_demolishedPhaseId"] = -1
    obj["m_areaSpaceElemId"] = -1
    obj["m_areaSchemeId"] = -1
    if phase_id is not None:
        obj["m_phaseId"] = phase_id
        obj["m_createdPhaseId"] = phase_id if obj.get("m_createdPhaseId", -1) != -1 else -1
    up = float(upper_offset) if upper_offset is not None else float(
        obj.get("m_upperOffset") or (obj.get("m_height") or 8.0))
    if up <= 0:
        raise ValueError(f"non-positive space upper offset {up}")
    obj["m_upperOffset"] = up
    obj["m_lowerOffset"] = float(lower_offset)
    obj["m_height"] = up - float(lower_offset)          # computed height cache
    obj["m_bIsLocationless"] = False
    # zone
    zone_el = None
    if kind == "room":
        zone = None                                      # rooms are never zoned
    if isinstance(zone, NewElement):
        zone_el = zone
        obj["m_zoneElementId"] = zone.elem_id
    elif zone == "new":
        # one fresh zone shared by every space added in this session
        zone_el = getattr(doc, "_vs_default_zone", None)
        if zone_el is None:
            zone_el = add_zone(doc, name="1", level_id=level_id, phase_id=phase_id)
            doc._vs_default_zone = zone_el
        obj["m_zoneElementId"] = zone_el.elem_id
    elif isinstance(zone, int) and not isinstance(zone, bool) and zone > 0:
        if not doc.exists(zone):
            raise LookupError(f"zone {zone} not in template {doc.project}")
        obj["m_zoneElementId"] = int(zone)
    else:                                                # no zone (rooms)
        obj["m_zoneElementId"] = -1
    # name / number
    if name is not None:
        _set_astring_param(obj, BIP_ROOM_NAME, str(name))
    if number is not None:
        _set_astring_param(obj, BIP_ROOM_NUMBER, str(number))
    # the architectural room this space lies in (rooms: never)
    obj["m_SpaceRoomLocationInfo"] = {
        "ptr_class": "RoomBoundingItem", "pid": -1,
        "value": {"m_linkInstOrHostId": int(room_id) if room_id else -1,
                  "m_linkRef": {"m_id64": -1}}}
    # bounding-wall cache + tag placement anchors
    walls = list(bounding_walls or ())
    wall_ids = [_elem_id_of(w) for w in walls]
    obj["m_volumeBoundingElems"] = [
        {"m_linkInstOrHostId": w, "m_linkRef": {"m_id64": -1}} for w in wall_ids]
    plc = placement_from_walls(doc, (px, py), walls)
    holder = obj.get("m_pPlacement")
    if isinstance(holder, dict) and isinstance(holder.get("value"), dict):
        holder["value"].update(plc)
    else:
        obj["m_pPlacement"] = {"ptr_class": "RoomTagPlacement", "pid": -1,
                               "value": dict(plc)}
    # location reference planes (base + top of the volume) at the new point
    faces = obj.get("m_referenceFaces") or []
    zs = [base_z, base_z + up]
    for i, f in enumerate(faces[:2]):
        surf = (((f or {}).get("value") or {}).get("m_pSurf") or {}).get("value")
        if isinstance(surf, dict):
            surf["m_origin"] = [px, py, zs[i] if i < 2 else base_z]
            surf.setdefault("m_xVec", [1.0, 0.0, 0.0])
            surf.setdefault("m_yVec", [0.0, 1.0, 0.0])
    # computed caches -> zero / invalid (Revit recomputes them)
    obj["m_loadPerLoadClass"] = []
    for k in list(obj.keys()):
        if k.startswith("m_dActual") or k.startswith("m_dDesign") or \
                k.startswith("m_dCalculated") or k in (
                    "m_dEstimatedIllumination", "m_dRoomCavityRatio",
                    "m_dOutdoorAirflow", "m_dPrimaryAirflow"):
            obj[k] = 0.0
    obj["m_cachedCircuitId"] = {"m_id": 0}         # plan-topology circuit: unassigned
    # element param caches: doubles zeroed, name/number kept
    dh = ((obj.get("m_pParamValueSetDouble") or {}).get("value") or {})
    for p in dh.get("m_paramSet") or []:
        if isinstance(p, dict) and isinstance(p.get("m_value"), float):
            p["m_value"] = 0.0

    # ---- header --------------------------------------------------------------
    header = copy.deepcopy(doc.value(tpl, 101) or {})
    header["m_regenHistory"] = {"m_historyMap": []}
    header["m_categroryId"] = SPACE_KIND_CATEGORY[kind]
    par = _fresh_parents(header)
    deletion = {sid, level_id}
    phase = obj.get("m_phaseId", -1)
    for x in (phase, obj.get("m_zoneSchemeId", -1), obj.get("m_zoneElementId", -1),
              obj.get("m_gbxmlSpaceTypeId", -1), int(room_id) if room_id else -1,
              upper_level_id or -1):
        if isinstance(x, int) and x > 0:
            deletion.add(x)
    deletion.update(w for w in wall_ids if isinstance(w, int) and w > 0)
    par["m_deletion"] = sorted(deletion)
    keep_regen = [p for p in par.get("m_regenOnly") or [] if doc.exists(p)
                  and doc.class_of(p) not in ("RoomElem", "SWall")]
    par["m_regenOnly"] = keep_regen
    app = {p for p in par.get("m_appearanceParents") or [] if doc.exists(p)
           and doc.class_of(p) not in ("RoomElem", "SWall", "Level")}
    app.add(level_id)
    par["m_appearanceParents"] = sorted(app)
    for k in ("m_regenWildcards", "m_nonDetermRegenChildren", "m_dependencyParents",
              "m_deferredParents", "m_deferredPropagationParents",
              "m_computedParametersParents"):
        par[k] = []
    par["m_hasNonDetermRegenChildren"] = False
    # bounding box estimate: from the bounding walls' location lines if any,
    # else a 10 ft cube around the point; z = the volume
    xs, ys = [], []
    if walls:
        from .. import hosting
        for w in walls:
            try:
                g = hosting.wall_geometry(doc, w)
            except Exception:
                continue
            xs += [g.start[0], g.start[0] + g.dir[0] * g.length]
            ys += [g.start[1], g.start[1] + g.dir[1] * g.length]
    if not xs:
        xs, ys = [px - 5.0, px + 5.0], [py - 5.0, py + 5.0]
    header["m_pBBox"] = {"ptr_class": "Outline", "pid": -1,
                         "value": {"m_minmax": [[min(xs), min(ys), base_z],
                                                [max(xs), max(ys), base_z + up]]}}

    el = NewElement(sid, kind, "RoomElem", _class_id_of(doc, tpl), header, obj,
                    None, doc._new_elemrec(sid), tpl,
                    notes=[f"{kind} cloned from RoomElem {tpl}: point ({px:.3f}, "
                           f"{py:.3f}) on level {level_id} (z {base_z:.3f}), "
                           f"upper offset {up:.3f} ft, {len(wall_ids)} bounding "
                           f"walls, zone {obj.get('m_zoneElementId')}, room "
                           f"{room_id}; name={name!r} number={number!r}",
                           "seq103 = SerializedDummy: the space solid + area/"
                           "volume/loads are computed by Revit's room "
                           "computation from the point + bounding elements "
                           "(regeneration hypothesis, like walls); plan-"
                           "topology circuit cache invalidated (m_cachedCircuitId 0)"])
    doc.new_elements.append(el)
    # two-sided zone membership for a planned zone
    if zone_el is not None:
        zone_el.obj.setdefault("m_spaceIds", [])
        if sid not in zone_el.obj["m_spaceIds"]:
            zone_el.obj["m_spaceIds"].append(sid)
        zpar = _fresh_parents(zone_el.header)
        zpar["m_deletion"] = sorted(set(zpar["m_deletion"]) | {sid})
        zpar["m_appearanceParents"] = sorted(set(zpar["m_appearanceParents"]) | {sid})
        if not zone_el.obj.get("m_bRefPointDefined"):
            zone_el.obj["m_ptPointXYZ"] = [px, py, 0.0]
            zone_el.obj["m_bRefPointDefined"] = True
        zone_el.notes.append(f"member space {sid} added (m_spaceIds + parents)")
    return el


def add_room(doc: Document, level_id: int, point, name: Optional[str] = None,
             number: Optional[str] = None, **kw) -> NewElement:
    """An architectural ROOM (RoomElem cat OST_Rooms) — same recipe as
    :func:`add_space` with the room category and no zone."""
    kw.setdefault("zone", None)
    return add_space(doc, level_id, point, name, number, kind="room", **kw)


def rename_space(doc: Document, space_id: int, *, name: Optional[str] = None,
                 number: Optional[str] = None) -> list:
    """Rename / renumber an existing space or room (its ROOM_NAME /
    ROOM_NUMBER parameters).  Returns the ``rvt.manipulate.ModifyPlan``s."""
    from .. import manipulate
    if doc.class_of(space_id) != "RoomElem":
        raise TypeError(f"element {space_id} is a {doc.class_of(space_id)!r}, "
                        "not a RoomElem space/room")
    plans = []
    if name is not None:
        plans.append(manipulate.set_param(doc, space_id, BIP_ROOM_NAME, str(name)))
    if number is not None:
        plans.append(manipulate.set_param(doc, space_id, BIP_ROOM_NUMBER, str(number)))
    if not plans:
        raise ValueError("rename_space: give name and/or number")
    return plans


def delete_space(doc: Document, space_id: int, *, cascade: bool = True):
    """Delete an existing space/room.  Its tag(s) are annotation dependents
    (they honour m_deletion) and are removed by the cascade; the zone's and
    the plan-topology's mentions are neutralised as referrers.  Returns an
    ``rvt.manipulate.DeletePlan``."""
    from .. import manipulate
    if doc.class_of(space_id) != "RoomElem":
        raise TypeError(f"element {space_id} is a {doc.class_of(space_id)!r}, "
                        "not a RoomElem space/room")
    return manipulate.delete_element(doc, space_id, cascade=cascade)


def describe_space(doc: Document, space_id: int) -> dict:
    """Readback: the fields that define a space/room."""
    v = doc.value(space_id) or {}
    plc = (v.get("m_pPlacement") or {}).get("value") or {}
    return {
        "id": space_id, "class": doc.class_of(space_id),
        "category": doc.category_of(space_id),
        "name": _astring_param(v, BIP_ROOM_NAME),
        "number": _astring_param(v, BIP_ROOM_NUMBER),
        "point": v.get("m_point"), "level": v.get("m_levelId"),
        "upper_level": v.get("m_upperLevelId"),
        "upper_offset": v.get("m_upperOffset"), "height": v.get("m_height"),
        "zone": v.get("m_zoneElementId"),
        "room": (v.get("m_SpaceRoomLocationInfo") or {}).get("value", {}).get("m_linkInstOrHostId")
                if isinstance(v.get("m_SpaceRoomLocationInfo"), dict) else None,
        "bounding": [b.get("m_linkInstOrHostId") for b in (v.get("m_volumeBoundingElems") or [])],
        "placement": {k: plc.get(k) for k in ("m_ref0", "m_ref1", "m_offset0", "m_offset1")},
        "locationless": v.get("m_bIsLocationless"),
        "tags": space_tags_of(doc, space_id),
    }


# ===========================================================================
# SPACE TAGS
# ===========================================================================
def _plan_views_for_level(doc: Document, level_id: int) -> List[int]:
    """DBViewPlan ids generated at ``level_id`` (their genLevel / assoc)."""
    out = []
    for vid in doc.ids_of_class("DBViewPlan"):
        v = doc.value(vid) or {}
        if v.get("m_genElemId") == level_id or v.get("m_assocLevelId") == level_id:
            out.append(vid)
    return out


def _space_tag_specimen(doc: Document, level_id: Optional[int]) -> Tuple[int, Optional[int]]:
    """(a real space-tag id, its owner plan view) — preferring a tag whose
    space is on ``level_id`` so its view is a plan of that level."""
    best = None
    for tid in doc.ids_of_class("RoomTag"):
        if doc.category_of(tid) != OST_MEPSpaceTags:
            continue
        v = doc.value(tid) or {}
        sp = (v.get("m_taggedRoomElemId") or {}).get("m_linkInstOrHostId")
        lvl = (doc.value(sp) or {}).get("m_levelId") if isinstance(sp, int) and sp > 0 else None
        key = (0 if (level_id is not None and lvl == level_id) else 1, tid)
        if best is None or key < best[0]:
            best = (key, tid, v.get("m_ownerDBViewId"))
    if best is None:
        raise LookupError(f"{doc.project}: no space-tag (RoomTag cat "
                          f"{OST_MEPSpaceTags}) specimen to clone")
    return best[1], best[2]


def add_space_tag(doc: Document, space, *, view_id: Optional[int] = None,
                  symbol_id: Optional[int] = None,
                  template_id: Optional[int] = None,
                  head_offset: Tuple[float, float] = (0.0, 0.0)) -> NewElement:
    """Tag a space (planned NewElement or existing id) in a plan view.

    ``view_id``: the ``DBViewPlan`` the tag is drawn in (default: the
    specimen tag's own view when the space is on that level, else the first
    plan view of the space's level).  ``symbol_id``: the tag ``FamilySymbol``
    (default: the specimen's, rme 351633 'Space Tag').  The tag head sits at
    the space point (+ ``head_offset``); ``m_pPlacement`` mirrors the
    space's ``RoomTagPlacement`` (Revit keeps them identical).
    """
    space_id = _elem_id_of(space)
    sp_el = space if isinstance(space, NewElement) else _is_planned(doc, space_id)
    sobj = sp_el.obj if sp_el is not None else (doc.value(space_id) or {})
    if not sobj:
        raise LookupError(f"space {space_id} not found / not decodable")
    lvl = sobj.get("m_levelId")
    pt = sobj.get("m_point") or [0.0, 0.0]

    tpl, tview = (template_id, None) if template_id else _space_tag_specimen(doc, lvl)
    tv = doc.value(tpl)
    if not tv:
        raise LookupError(f"space-tag specimen {tpl} did not decode")
    if tview is None:
        tview = tv.get("m_ownerDBViewId")
    if view_id is None:
        # keep the specimen's view when it is a plan of the space's level,
        # else the first plan view generated at that level
        candidates = _plan_views_for_level(doc, lvl) if isinstance(lvl, int) else []
        if tview in candidates or (isinstance(tview, int) and tview > 0 and not candidates):
            view_id = tview
        elif candidates:
            view_id = candidates[0]
        else:
            view_id = tview if isinstance(tview, int) and tview > 0 else -1
    if not (isinstance(view_id, int) and view_id > 0 and doc.exists(view_id)):
        raise LookupError(f"no plan view for the space tag (level {lvl}); pass view_id=")
    sym = symbol_id or tv.get("m_symbolId")
    if not (isinstance(sym, int) and sym > 0 and doc.exists(sym)):
        raise LookupError(f"space-tag symbol {sym} not in template {doc.project}")

    tid = doc.next_id()
    obj = copy.deepcopy(tv)
    obj["m_id"] = tid
    obj["m_ownerDBViewId"] = view_id
    obj["m_symbolId"] = sym
    obj["m_taggedRoomElemId"] = {"m_linkInstOrHostId": space_id,
                                 "m_linkRef": {"m_id64": -1}}
    hx, hy = float(pt[0]) + float(head_offset[0]), float(pt[1]) + float(head_offset[1])
    toc = ((obj.get("m_oTagOrientationCell") or {}).get("value"))
    if isinstance(toc, dict):
        toc["m_headLocation"] = [hx, hy, 0.0]
        toc["m_relHeadLocation"] = [0.0, 0.0, 0.0]
        toc["m_isSpatialElementTag"] = True
    obj["m_leaderAnchor"] = [0.0, 0.0, 0.0]
    obj["m_tagOffset"] = [0.0, 0.0, 0.0]
    obj["m_elbowOffset"] = [0.0, 0.0, 0.0]
    obj["m_bLeader"] = False
    obj["m_bIsInRoom"] = True
    # placement mirrors the space's
    splc = ((sobj.get("m_pPlacement") or {}).get("value")) or {}
    plc = {"m_offset0": float(splc.get("m_offset0", 0.0)),
           "m_offset1": float(splc.get("m_offset1", 0.0)),
           "m_ref0": int(splc.get("m_ref0", -1)), "m_ref1": int(splc.get("m_ref1", -1))}
    holder = obj.get("m_pPlacement")
    if isinstance(holder, dict) and isinstance(holder.get("value"), dict):
        holder["value"].update(plc)
    else:
        obj["m_pPlacement"] = {"ptr_class": "RoomTagPlacement", "pid": -1,
                               "value": dict(plc)}
    zscheme = sobj.get("m_zoneSchemeId")
    if isinstance(zscheme, int) and zscheme > 0:
        obj["m_zoneSchemeId"] = zscheme

    header = copy.deepcopy(doc.value(tpl, 101) or {})
    header["m_regenHistory"] = {"m_historyMap": []}
    header["m_categroryId"] = OST_MEPSpaceTags if doc.category_of(tpl) == OST_MEPSpaceTags \
        else header.get("m_categroryId", OST_RoomTags)
    header["m_ownerViewId"] = view_id
    par = _fresh_parents(header)
    deletion = {tid, space_id, view_id, sym}
    for x in (zscheme, plc["m_ref0"], plc["m_ref1"]):
        if isinstance(x, int) and x > 0:
            deletion.add(x)
    par["m_deletion"] = sorted(deletion)
    regen = [p for p in par.get("m_regenOnly") or [] if doc.exists(p)
             and doc.class_of(p) not in ("RoomElem",)]
    room_ref = ((sobj.get("m_SpaceRoomLocationInfo") or {}).get("value") or {}).get("m_linkInstOrHostId") \
        if isinstance(sobj.get("m_SpaceRoomLocationInfo"), dict) else None
    if isinstance(room_ref, int) and room_ref > 0:
        regen = sorted(set(regen) | {room_ref})
    par["m_regenOnly"] = regen
    par["m_appearanceParents"] = sorted({sym, space_id})
    for k in ("m_regenWildcards", "m_nonDetermRegenChildren", "m_dependencyParents",
              "m_deferredParents", "m_deferredPropagationParents",
              "m_computedParametersParents"):
        par[k] = []
    par["m_hasNonDetermRegenChildren"] = False
    header["m_pBBox"] = None                     # annotation: no model bbox

    el = NewElement(tid, "space_tag", "RoomTag", _class_id_of(doc, tpl), header,
                    obj, None, doc._new_elemrec(tid), tpl,
                    notes=[f"space tag cloned from RoomTag {tpl}: tags {space_id} in "
                           f"plan view {view_id}, symbol {sym}, head at ({hx:.3f}, "
                           f"{hy:.3f})",
                           "seq103 = SerializedDummy (annotation graphics are "
                           "drawn from the tag symbol by Revit)"])
    doc.new_elements.append(el)
    if sp_el is not None:
        sp_el.notes.append(f"tagged by RoomTag {tid} in view {view_id}")
    return el


# ===========================================================================
# COMMIT (create path) — commit_new_elements with ElemTable OWNER links
# ===========================================================================
def commit_elements(src_rvt: str, out_path: str, doc: Document,
                    elements: Optional[Sequence[NewElement]] = None, *,
                    identity: Optional[dict] = None):
    """Serialize + write ``elements`` (default: everything planned on
    ``doc``) into a copy of ``src_rvt`` via ``rvt.commit.commit_new_elements``.

    ``commit_new_elements`` writes every ElemRec with an INVALID owner; the
    schedule-view cluster relies on ``Global/ElemTable.m_OwningElementId``
    (fonts / viewer / drawing / category are OWNED by the view — the
    delete-cascade signal).  Rather than edit ``commit.py`` (out of this
    module's territory), the ownership is injected here by wrapping the
    ``elemtable_add_element`` name that ``commit`` imports, so each new row
    is written with its planned ``owner_id``.  The equivalent one-line
    ``commit.py`` change is recorded in docs/inbox/mep-schedules.md.
    """
    from .. import commit as _commit
    els = list(elements) if elements is not None else list(doc.new_elements)
    dangling = {e.elem_id: doc.check_references(e) for e in els}
    bad = {k: v for k, v in dangling.items() if v}
    if bad:
        raise ValueError(f"referential integrity: dangling ids {bad}")
    # identity coherence: commit.commit_new_elements' identity scrub mints a
    # FRESH BasicFileInfo document GUID but this minimal commit records NO
    # new History episode, tripping the validator's L2 rule "BFI Unique
    # Document GUID == History entry[0]".  Keep the two coherent by reusing
    # History entry 0's GUID unless the caller passes document_guid=.
    identity = dict(identity or {})
    if "document_guid" not in identity:
        from ..stream_encoders import history_head_guid
        hist0 = history_head_guid(src_rvt)
        if hist0:
            identity["document_guid"] = hist0
    records, plans = [], []
    for e in els:
        recs = doc.serialize(e)
        if recs is None:
            raise RuntimeError(f"encoder unavailable / element {e.elem_id} not serializable")
        records.append(dict(recs))
        plans.append(e.elemrec)
    owner_by_id = {p.elem_id: (p.owner_id if p.owner_id is not None else -1)
                   for p in plans}
    orig_add = _commit.elemtable_add_element

    def _add_with_owner(model, element_id, **kw):
        own = owner_by_id.get(element_id, -1)
        if own is not None and own >= 0:
            kw["owner_id"] = own
        return orig_add(model, element_id, **kw)

    _commit.elemtable_add_element = _add_with_owner
    try:
        report = _commit.commit_new_elements(src_rvt, out_path, records, plans,
                                              identity=identity)
    finally:
        _commit.elemtable_add_element = orig_add
    return report
