"""rvt.frontdoor.levels -- stage D: bind the intent's levels to the base's
building-story datums (issue #147).

Every pinned genesis base carries exactly two ``is_building_story`` Level
datums ('L1 - Ground Floor' at 0 ft, 'L2 - Second Floor' at 12 ft, each with
its floor plan view) among its 'GEN ...' reference datums.  A job's intent
names its own storeys (prompt: 'two storey ... floor to floor 14 ft' ->
Level 1 @ 0 / Level 2 @ 14 ft; IFC: the ``IfcBuildingStorey`` names and
elevations), so the build BINDS intent levels to those story datums in
elevation order and makes each datum say what the intent says: the level's
name (``Level.m_text``) and its elevation (the two datum-plane origins,
:func:`rvt.manipulate.set_level_elevation`) -- the certified MODIFY shape
(matrix cell M3: an existing element's seq-102 record replaced, one commit,
nothing added or removed).  No Level constructor runs: storeys beyond the
base's story datums are NOT created; they are returned as ``not_built``
(the manifest states it; hard rule 1 -- the file is still delivered) and
their equipment binds to the top built datum at the storey's own elevation.

The stage runs right after stage P (base -> ``_stages/stage_D_levels.rvt``)
so walls (W) and instances (E) grow on the re-elevated datums:
:func:`level_map` hands them ``{intent level id: (base Level id, datum z
ft)}`` -- ``rvt.mutate.add_wall`` reads the wall's base z from the datum,
``stage_equipment`` adds the datum z to the item's level-relative z and sets
``m_assocLevelId``.  When nothing differs -- every job whose prompt / IFC
says nothing about levels (one DEFAULTED storey, which asserts no name), or
an intent that already matches -- no file is written, the caller keeps its
input, and the output stays byte-identical to a build without this stage.

Territory: ``src/rvt/frontdoor/`` (front-door stream).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

__all__ = ["FT_PER_M", "ELEV_TOL_FT", "bind_levels", "level_map", "stage_levels"]

FT_PER_M = 3.280839895013123
#: elevations closer than this (ft) are 'the same datum' -- no re-elevation
ELEV_TOL_FT = 1e-6


def _story_levels(doc) -> List[dict]:
    """The base's building-story datums, lowest first (every level when the
    base flags none -- a foreign base)."""
    levels = doc.levels()                                   # sorted by elevation
    return [lv for lv in levels if lv.get("is_building_story")] or levels


def bind_levels(doc, intent_levels: Sequence[dict]) -> Tuple[List[dict], List[dict]]:
    """Pair intent levels (lowest first) with the base's story datums.

    Returns ``(bound, not_built)``.  ``bound[i]`` = ``{"id", "name",
    "elevation_ft", "base_id", "base_name", "base_elevation_ft", "rename",
    "move"}``; ``not_built[j]`` = an intent level with no datum left:
    ``{"id", "name", "elevation_ft", "base_id" (the top bound datum),
    "reason"}``.  A level the intent merely DEFAULTED (``"default": True``
    -- a prompt / IFC that said nothing about levels) asserts no name: it
    binds to its datum and keeps the datum's own name.  An empty intent
    binds the first storey as 'Level 1' @ 0."""
    stories = _story_levels(doc)
    if not stories:
        raise ValueError("the base carries no Level datum to bind the intent's levels to")
    want = sorted((dict(lv) for lv in (intent_levels or [{"id": "L1", "name": "Level 1",
                                                          "elevation": 0.0}])),
                  key=lambda lv: float(lv.get("elevation") or 0.0))
    bound: List[dict] = []
    not_built: List[dict] = []
    for i, lv in enumerate(want):
        elev_ft = round(float(lv.get("elevation") or 0.0) * FT_PER_M, 6)
        name = str(lv.get("name") or f"Level {i + 1}")
        lid = str(lv.get("id") or f"L{i + 1}")
        if i < len(stories):
            st = stories[i]
            if lv.get("default"):
                name = st.get("name") or name
            bound.append({"id": lid, "name": name, "elevation_ft": elev_ft,
                          "base_id": int(st["id"]), "base_name": st.get("name"),
                          "base_elevation_ft": float(st.get("elevation_ft") or 0.0),
                          "rename": name != (st.get("name") or ""),
                          "move": abs(elev_ft - float(st.get("elevation_ft") or 0.0)) > ELEV_TOL_FT})
        else:
            top = bound[-1]
            not_built.append({
                "id": lid, "name": name, "elevation_ft": elev_ft, "base_id": top["base_id"],
                "reason": (f"{name} ({elev_ft:g} ft) NOT created: the base carries "
                           f"{len(stories)} building-story datums and the create path binds "
                           "storeys to them (rename + re-elevate, the certified modify shape) "
                           "-- it does not add Level datums / plan views yet; equipment on it "
                           f"is placed at its elevation, associated to {top['name']} "
                           f"(Level {top['base_id']})")})
    return bound, not_built


def level_map(bound: Sequence[dict], not_built: Sequence[dict] = ()) -> Dict[str, Tuple[int, float]]:
    """``{intent level id: (base Level id, datum z in ft)}`` for stages W / E.
    A not-built storey maps to the top bound datum at the storey's OWN z."""
    out = {b["id"]: (int(b["base_id"]), float(b["elevation_ft"])) for b in bound}
    out.update({nb["id"]: (int(nb["base_id"]), float(nb["elevation_ft"])) for nb in not_built})
    return out


def stage_levels(src_rvt: str, out_path: str, intent_levels: Sequence[dict]) -> Dict[str, Any]:
    """Stage D: bind ``intent_levels`` to ``src_rvt``'s story datums and
    write the renamed / re-elevated datums -> ``out_path``.

    One :func:`rvt.manipulate.set_level_elevation` and/or one ``m_text``
    :func:`rvt.manipulate.modify_element` per bound datum that differs, ONE
    commit (:func:`rvt.manipulate.commit_plans`); the written file is
    re-opened and its levels decoded again, proving every name and elevation
    landed and nothing else moved (replaced records == the edited datums,
    ElemTable count unchanged).  ``rec["written"]`` is False when no datum
    differed (no file; the caller keeps ``src_rvt``).  ``ok`` False +
    ``blocker`` on any failure -- the caller degrades to the unedited datums
    (``level_map`` then carries the base's own elevations), never withholds."""
    from .. import manipulate as M
    from ..mutate import Document

    rec: Dict[str, Any] = {"stage": "D", "in": src_rvt, "out": out_path, "ok": False,
                           "written": False, "levels": [], "not_built": [], "level_map": {}}
    try:
        doc = Document.from_file(src_rvt)
        bound, not_built = bind_levels(doc, intent_levels)
        rec["levels"], rec["not_built"] = bound, not_built
        # until the edit lands, the map speaks the base's own elevations
        rec["level_map"] = level_map([dict(b, elevation_ft=b["base_elevation_ft"]) for b in bound],
                                     not_built)
        plans = []
        for b in bound:
            if b["move"]:
                plans.append(M.set_level_elevation(doc, b["base_id"], b["elevation_ft"]))
            if b["rename"]:
                plans.append(M.modify_element(doc, b["base_id"], {"m_text": b["name"]},
                                              kind="level-name",
                                              reason=f"level name -> {b['name']!r}"))
        edited = sorted({b["base_id"] for b in bound if b["move"] or b["rename"]})
        rec["edited_ids"] = edited
        if not plans:
            rec["ok"] = True
            rec["level_map"] = level_map(bound, not_built)
            return rec
        crep = M.commit_plans(src_rvt, out_path, plans)
        rec["written"] = True
        rec["commit"] = {"replaced": [list(r) for r in crep.replaced],
                         "removed_ids": list(crep.removed_ids),
                         "elemtable_count_before": crep.elemtable_count_before,
                         "elemtable_count_after": crep.elemtable_count_after,
                         "watermark": crep.watermark}
        after = {int(lv["id"]): lv for lv in Document.from_file(out_path).levels()}
        rec["mismatch"] = {}
        for b in bound:
            got = after.get(b["base_id"]) or {}
            if got.get("name") != b["name"] or abs(float(got.get("elevation_ft") or 0.0)
                                                   - b["elevation_ft"]) > ELEV_TOL_FT:
                rec["mismatch"][b["id"]] = {"wanted": [b["name"], b["elevation_ft"]],
                                           "got": [got.get("name"), got.get("elevation_ft")]}
        rec["ok"] = bool(sorted(e for _s, e in crep.replaced) == edited
                         and all(s == 102 for s, _e in crep.replaced)
                         and not crep.removed_ids
                         and crep.elemtable_count_before == crep.elemtable_count_after
                         and not rec["mismatch"])
        if rec["ok"]:
            rec["level_map"] = level_map(bound, not_built)
        else:
            rec["blocker"] = "level edit did not land cleanly (see commit / mismatch)"
    except Exception as e:                                               # noqa: BLE001
        rec["blocker"] = f"{type(e).__name__}: {e}"
    return rec
