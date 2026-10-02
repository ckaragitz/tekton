"""rvt.ifc.pset_drive -- a carried IFC pset parameter DRIVES the part it
describes (issue #714).

WHY.  #769 carries an IFC's own property sets onto the family as real, typed
parameters (:mod:`rvt.ifc.pset_params`), but as VALUES only: a user who
attached ``Pset_TransformerClearances`` with ``BodyWidth`` to the tank shell
gets a ``BodyWidth`` parameter that moves nothing when they change it.  The
pset already says WHICH product it describes (the ``IfcRelDefinesByProperties``
that attaches it), and the assembly lane has measured that product into a
named part, so the remaining question is only which of the part's three
spans the value is.

WHAT THIS DOES.  :func:`plan` matches every carried LENGTH parameter to
``(part, axis)`` and emits the declarative drive specs the multi-part generic
model already wires (``factory._make_generic_multipart``):

* **x / y** -- an in-plane drive (:mod:`rvt.famgen.drive_law`, the
  desktop-verified #787 / #904 law): two reference planes at the part's OWN
  faces, one labelled dimension carrying the parameter, the part's two edges
  locked to them; made symmetric about the origin centre plane only when the
  part is centred on it (the multipart way, #913);
* **z** -- a height drive (:mod:`rvt.famgen.height_law`, #787 Case B): the
  part's cap faces locked to two horizontal planes held by a labelled
  elevation dimension; a part off the origin elevation has its base held
  there by a LOCKED unlabelled height (the panelboard's chain, #914).

NEVER A GUESS.  A parameter is matched only when (1) its pset is attached to
exactly ONE product, (2) exactly one measured part carries that product's
name (a product decomposed into several solids, or two products of one name,
is not one part), and (3) the value EQUALS one of that part's spans to
:data:`SPAN_TOL` -- float noise, never a snap: a value a hair off the span is
reported as off, because a labelled dimension forces its planes to the
parameter's value and would silently move the geometry.  Equal to two spans
(a square part) is resolved only by an axis word in the parameter's own name
(``...Width`` = x, ``...Depth`` = y, ``...Height`` = z) and otherwise left a
value.  Every unmatched parameter is reported with its reason.

ALL OR NOTHING.  The specs carry ``group`` = the parameter, and the lane
builds with ``settle_drives=True``: a group the factory refuses is dropped
and the family rebuilt without it, so a refused drive leaves the file
byte-identical to the build that never asked for it.

NOTHING HERE CLAIMS A FAMILY FLEXES.  "DRIVES" means the chain is AUTHORED;
no multi-part pset drive has a desktop verdict (hard rule 4), so no route
calls the result editable.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

#: span equality, feet: float noise only (0.3 um).  ``drive_law`` /
#: ``height_law`` themselves refuse a parameter whose value is more than 1e-6
#: ft off its planes, so a looser match would only move the refusal there.
SPAN_TOL = 1e-6
#: "close but not equal" -- reported as such, never snapped (1/64 in)
NEAR_TOL = 1.0 / 64.0 / 12.0
#: an axis word in a parameter's own name, the ONLY tie-break for a value
#: equal to two of a part's spans
_AXIS_WORD = (("x", re.compile(r"Width(?![a-z])")),
              ("y", re.compile(r"Depth(?![a-z])")),
              ("z", re.compile(r"Height(?![a-z])")))
_AXES = ("x", "y", "z")
_CENTRED = 1e-9

DRIVES = "DRIVES"
VALUE_ONLY = "value only"


def _spans(part: Dict[str, Any]) -> Tuple[Optional[Dict[str, Tuple[float, float]]], str]:
    """``{axis: (lo, hi)}`` of a part as the factory authors it, or ``(None,
    why)`` when it has no drivable span."""
    shape = str(part.get("shape") or "box").lower()
    base = float(part.get("base_z_ft") or 0.0)
    if shape == "box":
        cx, cy = (tuple(part.get("center") or (0.0, 0.0)) + (0.0, 0.0))[:2]
        w, d = float(part["width_ft"]), float(part["depth_ft"])
        h = float(part["height_ft"])
        return {"x": (cx - w / 2.0, cx + w / 2.0), "y": (cy - d / 2.0, cy + d / 2.0),
                "z": (base, base + h)}, ""
    if shape in ("cylinder_x", "cylinder_y"):
        return None, (f"a lying cylinder ({shape}) is authored vertical with its cached "
                      "B-rep rotated: a lock on its sketch or caps would drive nothing "
                      "Revit draws (#591 round 4)")
    if shape in ("polygon", "cylinder"):
        # a cap face is a cap face whatever the footprint: z only
        return {"z": (base, base + float(part["height_ft"]))}, ""
    return None, f"shape {shape!r} has no drivable span"


def _fmt_in(ft: float) -> str:
    return f"{ft * 12.0:.4g} in"


def _named_axis(name: str) -> Optional[str]:
    """The ONE axis a parameter's name names (Width -> x, ...), else None."""
    hits = [ax for ax, rx in _AXIS_WORD if rx.search(name)]
    return hits[0] if len(hits) == 1 else None


def _axis_from_name(name: str, candidates: Sequence[str]) -> Optional[str]:
    hits = [ax for ax, rx in _AXIS_WORD if rx.search(name)]
    if len(hits) == 1 and hits[0] in candidates:
        return hits[0]
    return None


def _height_specs(caption: str, part: str, lo: float, hi: float) -> List[Dict[str, Any]]:
    """#787 Case B specs for ONE part's cap faces at ``lo`` .. ``hi``: the
    labelled height between them, the base held to the origin elevation by a
    LOCKED unlabelled height when it is off it (``factory._prism_height_specs``,
    per part).  Exactly one end of each spec is positioned."""
    faces = {part: {"start": "lo", "end": "hi"}}
    if abs(lo) < _CENTRED:
        return [{"caption": caption, "lo": 0.0, "hi": hi, "parts": faces, "group": caption}]
    if abs(hi) < _CENTRED:
        return [{"caption": caption, "lo": lo, "hi": 0.0, "parts": faces, "group": caption}]
    name = f"{caption} base"
    held = ({"caption": None, "locked": True, "lo": 0.0, "hi": lo, "name_hi": name,
             "parts": {}, "group": caption} if lo > 0 else
            {"caption": None, "locked": True, "lo": lo, "hi": 0.0, "name_lo": name,
             "parts": {}, "group": caption})
    return [held, {"caption": caption, "lo": name, "hi": hi, "parts": faces,
                   "group": caption}]


def plan(parts: Sequence[Dict[str, Any]], collected: Dict[str, Any]) -> Dict[str, Any]:
    """Match the carried parameters of ``collected`` (:func:`pset_params.collect`)
    to the measured ``parts`` (``AssemblyModel.to_parts()``).

    Returns ``{"drives": [...], "heights": [...], "rows": [...]}`` --
    ``drives`` / ``heights`` are the factory's spec lists (empty when nothing
    matched, so the build is the one without drives), ``rows`` one record per
    carried parameter, sorted by name: ``{"parameter", "status" (DRIVES |
    value only), "part", "axis", "reason"}``.  A ``DRIVES`` row here is a
    PLAN; :func:`settle_rows` turns it into a value-only row if the factory
    refused it.  Pure: reads nothing, writes nothing, never raises on a
    malformed part (the part is reported, not the lane)."""
    params = collected.get("params") or {}
    sources = collected.get("sources") or {}
    by_name: Dict[str, List[Dict[str, Any]]] = {}
    for p in parts:
        by_name.setdefault(str(p.get("name") or ""), []).append(p)
    drives: List[Dict[str, Any]] = []
    heights: List[Dict[str, Any]] = []
    rows: List[Dict[str, Any]] = []
    claimed: Dict[Tuple[str, str], str] = {}

    def row(name, status, reason, part="", axis=""):
        rows.append({"parameter": name, "status": status, "part": part, "axis": axis,
                     "reason": reason})

    for name in sorted(params):
        kind, value = params[name]
        src = sources.get(name) or {}
        if kind != "length":
            row(name, VALUE_ONLY, f"a {kind} parameter: only a length labels a dimension")
            continue
        allp = [str(p or "") for p in (src.get("products") or [])]
        if not allp and src.get("product"):
            allp = [str(src["product"])]
        n_owners = max(len(set(src.get("product_ids") or [])), len(allp))
        if any(not p for p in allp) and n_owners > 1:
            row(name, VALUE_ONLY, f"its pset ({src.get('pset') or '?'}) is attached to "
                                  f"{n_owners} products, one or more unnamed: which one it "
                                  "measures is not stated")
            continue
        products = [p for p in allp if p]
        if not products:
            row(name, VALUE_ONLY, f"its pset ({src.get('pset') or '?'}) is attached to no "
                                  "named product, so no part is named")
            continue
        if n_owners > 1:
            row(name, VALUE_ONLY, f"it is attached to {n_owners} products "
                                  f"({', '.join(products[:4])}): which one it measures "
                                  "is not stated")
            continue
        prod = products[0]
        found = by_name.get(prod, [])
        if not found:
            pieces = [n for n in by_name if n.startswith(prod + " [")]
            row(name, VALUE_ONLY, (
                f"{prod!r} was measured into {len(pieces)} solid(s), so no ONE part's "
                "span is the product's" if pieces else
                f"{prod!r} is not a measured part of this family (no tessellated body, "
                "or the pset sits on the assembly)"), part=prod)
            continue
        if len(found) > 1:
            row(name, VALUE_ONLY, f"{len(found)} measured parts are named {prod!r}: "
                                  "which one it measures is not determined", part=prod)
            continue
        try:
            spans, why = _spans(found[0])
        except (KeyError, TypeError, ValueError) as e:
            spans, why = None, f"the part's dimensions could not be read ({type(e).__name__})"
        if spans is None:
            row(name, VALUE_ONLY, why, part=prod)
            continue
        v = float(value)
        size = {ax: hi - lo for ax, (lo, hi) in spans.items()}
        cands = [ax for ax in _AXES if ax in size and abs(size[ax] - v) <= SPAN_TOL]
        tie = ""
        if len(cands) > 1:
            ax = _axis_from_name(name, cands)
            if ax is None:
                row(name, VALUE_ONLY, f"equals the part's {' and '.join(cands)} spans "
                                      f"({_fmt_in(v)}) and its name names no one axis: "
                                      "not guessed", part=prod)
                continue
            tie = f"; equal to its {' and '.join(cands)} spans, the name's axis word picked {ax}"
            cands = [ax]
        named = _named_axis(name)
        if len(cands) == 1 and named is not None and named != cands[0]:
            row(name, VALUE_ONLY, f"its name says {named} but its value equals the part's "
                                  f"{cands[0]} span ({_fmt_in(v)}): not guessed",
                part=prod)
            continue
        if not cands:
            near = sorted((abs(size[ax] - v), ax) for ax in size)
            if near and near[0][0] <= NEAR_TOL:
                d, ax = near[0]
                why = (f"is {_fmt_in(v)} but the part's {ax} span is {_fmt_in(size[ax])} "
                       f"({d * 12.0 * 25.4:.3g} mm off): a labelled dimension would move the "
                       "geometry to the parameter, so it is not driven and never snapped")
            else:
                why = (f"is {_fmt_in(v)}, equal to none of the part's spans ("
                       + ", ".join(f"{ax} {_fmt_in(size[ax])}" for ax in _AXES if ax in size)
                       + ")")
            row(name, VALUE_ONLY, why, part=prod)
            continue
        ax = cands[0]
        if (prod, ax) in claimed:
            row(name, VALUE_ONLY, f"the part's {ax} span is already driven by "
                                  f"{claimed[(prod, ax)]}", part=prod, axis=ax)
            continue
        claimed[(prod, ax)] = name
        lo, hi = spans[ax]
        if ax == "z":
            heights.extend(_height_specs(name, prod, lo, hi))
            how = ("its cap faces locked to two horizontal planes held by a labelled "
                   "elevation dimension (#787 Case B)"
                   + ("" if abs(lo) < _CENTRED else
                      f"; its base held at {_fmt_in(lo)} by a locked unlabelled height"))
        else:
            spec = {"caption": name, "axis": ax, "lo": lo, "hi": hi,
                    "parts": {prod: ("lo", "hi")}, "group": name}
            centred = abs(lo + hi) < _CENTRED
            if centred:
                spec["symmetric"] = True
            drives.append(spec)
            how = ("its two edges locked to reference planes at its own faces, one "
                   "labelled dimension (#787 / #904 in-plane law)"
                   + ("; symmetric about the origin centre plane (the part is centred)"
                      if centred else "; the part is off-centre, so the planes are free"))
        row(name, DRIVES, f"equals the part's {ax} span ({_fmt_in(v)}): {how}{tie}",
            part=prod, axis=ax)
    return {"drives": drives, "heights": heights, "rows": rows}


def settle_rows(rows: List[Dict[str, Any]], settle: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Fold the factory's verdict (``FamilyProduct.drive_settle``) into the
    plan's rows: a planned drive the factory refused becomes value-only with
    the factory's reason -- nothing is reported as driving unless its chain
    was authored."""
    refused = (settle or {}).get("refused") or {}
    wired = set((settle or {}).get("wired") or ())
    out = []
    for r in rows:
        r = dict(r)
        if r["status"] == DRIVES:
            if r["parameter"] in refused:
                r["status"] = VALUE_ONLY
                r["reason"] = (f"planned on {r['part']} {r['axis']} but the factory refused "
                               f"the chain: {refused[r['parameter']]}; the file is the build "
                               "without it")
            elif settle is not None and r["parameter"] not in wired:
                r["status"] = VALUE_ONLY
                r["reason"] = "planned, but the built family carries no chain for it"
        out.append(r)
    return out


def summarise(rows: Sequence[Dict[str, Any]]) -> List[str]:
    """Caveat lines: one per parameter, DRIVES vs value-only with the reason."""
    if not rows:
        return []
    n = sum(1 for r in rows if r["status"] == DRIVES)
    lines = [
        f"YOUR PSET PARAMETERS AS DRIVES (#714): {n} of {len(rows)} carried parameter(s) "
        "drive the part they describe -- the chain is AUTHORED (reference planes, locks, "
        "a labelled dimension), the family has NO desktop-Revit verdict, so nothing here "
        "is called editable (hard rule 4); the rest are values only, each with its reason"]
    for r in rows:
        if r["status"] == DRIVES:
            lines.append(f"{r['parameter']} DRIVES {r['part']} along {r['axis']}: {r['reason']}")
        else:
            lines.append(f"{r['parameter']} is a value only: {r['reason']}")
    return lines
