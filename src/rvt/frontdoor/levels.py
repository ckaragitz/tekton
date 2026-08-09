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
ft)}`` plus the ``""`` entry every level-less item falls back to (the bound
datum nearest z = 0 with NO z offset: an item without a level carries world
z, exactly main's ``_pick_level`` semantics) -- ``rvt.mutate.add_wall``
reads the wall's base z from the datum, ``stage_equipment`` adds the datum z
to the item's level-relative z and sets ``m_assocLevelId``.  A storey that
is not built maps its gear to the top datum at the storey's OWN z, while a
room shell on it stands on the top datum itself (a wall's base IS its datum;
no base offset is authored) -- both said in the ``not_built`` reason.  When
nothing differs -- every job whose prompt / IFC
says nothing about levels (no level, or one DEFAULTED storey, asserts no
name), or an intent that already matches -- no file is written, the caller
keeps its input, and the output stays byte-identical to a build without this
stage.

Territory: ``src/rvt/frontdoor/`` (front-door stream).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..ifc.intent import FT_PER_M

__all__ = ["ELEV_TOL_FT", "story_levels", "bind_levels", "level_map", "resolve",
           "stage_levels"]

#: elevations closer than this (ft) are 'the same datum' -- no re-elevation
ELEV_TOL_FT = 1e-6

#: intent level id -> (base Level element id, datum z in ft); key ``""`` =
#: the datum an item with no / an unknown level lands on: the bound datum
#: nearest z = 0 with z offset 0 (a level-less item carries WORLD z)
LevelMap = Dict[str, Tuple[int, float]]


def story_levels(doc) -> List[dict]:
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
    "reason"}``.  An intent that asserts nothing about levels -- no level at
    all, or one flagged ``"default": True`` (a prompt / IFC silent about
    levels) -- binds the first storey and keeps the datum's own name AND
    elevation (it never renames or moves anything)."""
    stories = story_levels(doc)
    if not stories:
        raise ValueError("the base carries no Level datum to bind the intent's levels to")
    want = sorted((dict(lv) for lv in intent_levels or [{"id": "L1", "elevation": 0.0,
                                                          "default": True}]),
                  key=lambda lv: float(lv.get("elevation") or 0.0))
    bound: List[dict] = []
    not_built: List[dict] = []
    for i, lv in enumerate(want):
        elev_ft = round(float(lv.get("elevation") or 0.0) * FT_PER_M, 6)
        name = str(lv.get("name") or f"Level {i + 1}")
        lid = str(lv.get("id") or f"L{i + 1}")
        if i < len(stories):
            st = stories[i]
            base_elev = float(st.get("elevation_ft") or 0.0)
            if lv.get("default"):                    # asserts nothing: keep the datum as is
                name, elev_ft = st.get("name") or name, base_elev
            bound.append({"id": lid, "name": name, "elevation_ft": elev_ft,
                          "base_id": int(st["id"]), "base_name": st.get("name"),
                          "base_elevation_ft": base_elev,
                          "rename": name != (st.get("name") or ""),
                          "move": abs(elev_ft - base_elev) > ELEV_TOL_FT})
        else:
            top = bound[-1]
            not_built.append({
                "id": lid, "name": name, "elevation_ft": elev_ft, "base_id": top["base_id"],
                "reason": (f"{name} ({elev_ft:g} ft) NOT created: the base carries "
                           f"{len(stories)} building-story datums and the create path binds "
                           "storeys to them (rename + re-elevate, the certified modify shape) "
                           "-- it does not add Level datums / plan views yet; equipment on it "
                           f"is placed at its own elevation, associated to {top['name']} "
                           f"(Level {top['base_id']}); a room shell on it stands on "
                           f"{top['name']}'s datum ({top['elevation_ft']:g} ft) -- a wall's "
                           "base IS its datum and no base offset is authored")})
    return bound, not_built


def level_map(bound: Sequence[dict], not_built: Sequence[dict] = (), *,
              landed: bool = True) -> LevelMap:
    """The :data:`LevelMap` for stages W / E.  ``landed=False`` (the edit did
    not land) speaks the base's own elevations; a not-built storey maps to
    the top bound datum at the storey's OWN z; ``""`` (level-less items,
    which carry WORLD z) = the bound datum whose final elevation is nearest
    0, with NO z offset -- main's ``_pick_level`` semantics."""
    z = "elevation_ft" if landed else "base_elevation_ft"
    out: LevelMap = {b["id"]: (int(b["base_id"]), float(b[z])) for b in bound}
    out.update({nb["id"]: (int(nb["base_id"]), float(nb["elevation_ft"])) for nb in not_built})
    if bound:
        ground = min(bound, key=lambda b: (abs(float(b[z])), float(b[z])))
        out.setdefault("", (int(ground["base_id"]), 0.0))
    return out


def resolve(levels: Optional[LevelMap], level: Optional[str],
            default: Tuple[Optional[int], float] = (None, 0.0)) -> Tuple[Optional[int], float]:
    """``(Level id, datum z ft)`` for an intent ``level`` id: its own entry,
    else the map's ``""`` fallback, else ``default`` (no map at all)."""
    levels = levels or {}
    return levels.get(level or "", levels.get("", default))


def stage_levels(src_rvt: str, out_path: str, intent_levels: Sequence[dict], *,
                 room_level: Optional[str] = None) -> Dict[str, Any]:
    """Stage D: bind ``intent_levels`` to ``src_rvt``'s story datums and
    write the renamed / re-elevated datums -> ``out_path``.

    One :func:`rvt.manipulate.set_level_elevation` and/or one ``m_text``
    :func:`rvt.manipulate.modify_element` per bound datum that differs, ONE
    commit (:func:`rvt.manipulate.commit_plans`); the written file is
    re-opened and its levels decoded again, proving every name and elevation
    landed and nothing else moved (replaced records == the edited datums,
    ElemTable count unchanged).  ``rec["written"]`` is False when no datum
    differed (no file; the caller keeps ``src_rvt``).  ``rec["level_map"]``
    feeds stages W / E and ``rec["room_level_id"]`` is the datum the room's
    walls stand on (``room_level`` = the intent's ``RoomShell.level``).
    ``ok`` False + ``blocker`` on any failure -- the caller degrades to the
    unedited datums (the map then carries the base's own elevations), never
    withholds."""
    from .. import manipulate as M
    from ..mutate import Document

    rec: Dict[str, Any] = {"stage": "D", "in": src_rvt, "out": out_path, "ok": False,
                           "written": False, "levels": [], "not_built": [], "edited_ids": []}
    try:
        doc = Document.from_file(src_rvt)
        bound, not_built = bind_levels(doc, intent_levels)
        rec["levels"], rec["not_built"] = bound, not_built
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
        else:
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
            if not rec["ok"]:
                rec["blocker"] = "level edit did not land cleanly (see commit / mismatch)"
    except Exception as e:                                               # noqa: BLE001
        rec["blocker"] = f"{type(e).__name__}: {e}"
    rec["level_map"] = level_map(rec["levels"], rec["not_built"], landed=rec["ok"])
    rec["room_level_id"] = resolve(rec["level_map"], room_level)[0]
    return rec
