"""param_profile -- apply a USER'S parameter profile to a family we generate (#866).

A parameter profile (``tekton.param-profile/1``, written by
``tools/shared_params_from_rfa.py`` from the user's OWN families) says which
shared parameters the families of a library carry, per family, bound by instance
or by type.  Applied to a family we build, it adds the same SHARED definitions --
same GUID, name, storage class, spec, palette group, flags -- so the generated
family schedules and tags alongside the user's library.

Values: none.  Every added parameter is written BLANK -- the all-empty value row a
Revit-born family itself stores for a parameter nobody filled (``m_str`` "",
``m_int`` 0, ``m_value`` 0.0, ``m_elemId`` -1) -- because a profile holds
definitions, never a value (S-2026-08-11-a: an empty standard parameter is
correct, an invented one is not).  A parameter the family already authors (same
GUID, or same caption) is left as the family authored it and said so.

What is selected (:func:`select`):

* ``family=<name>`` -- exactly the parameters that one profile family carries as
  its OWN (instance or type; a label's or nested family's definition is not one);
* otherwise the profile families of the generated family's CATEGORY: every
  parameter at least ``share`` of them carry, bound the way most of them bind it.

Not written, and said in the notes: storage classes our writer cannot author
(``ParamDefTextBrowseEdit`` / ``ParamDefImageSymbolBrowseEdit``, and
``ParamDefFamType``, whose value is a nested family's type).

This module holds no library content: the profile is the user's file, read at
build time from wherever they keep it (rule 6 / hard rule 3).
"""
from __future__ import annotations

import json
import re
import math
import os
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

PROFILE_SCHEMA = "tekton.param-profile/1"

_GUID = re.compile(r"^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$")

#: the spec a class WITHOUT its own ``m_specTypeId`` is typed as in a formula check
#: (a text / Yes-No / integer parameter is not a length: formula.py refuses text and
#: integer operands, and types Yes/No logic) -- a ParamDefValue carries its own spec
CLASS_SPEC = {
    "ParamDefString": "autodesk.spec:spec.string-1.0.0",
    "ParamDefURL": "autodesk.spec:spec.string-1.0.0",
    "ParamDefYesNo": "autodesk.spec:spec.bool-1.0.0",
    "ParamDefInt": "autodesk.spec:spec.int64-1.0.0",
    "ParamDefNoOfPoles": "autodesk.spec:spec.int64-1.0.0",
    "ParamDefMaterialBrowse": "autodesk.spec:spec.string-1.0.0",
}

#: storage classes :func:`rvt.genesis.residue_b.shared_parameter` authors, and the
#: blank value a Revit-born family stores for each (all fields empty either way;
#: the type picks which field the value row names)
WRITABLE = {
    "ParamDefValue": 0.0,
    "ParamDefString": "",
    "ParamDefURL": "",
    "ParamDefYesNo": 0,
    "ParamDefInt": 0,
    "ParamDefNoOfPoles": 0,
    "ParamDefMaterialBrowse": 0.0,
}


class ProfileError(ValueError):
    pass


@dataclass
class ProfileParam:
    guid: str
    name: str
    def_class: str
    spec: Optional[str]
    palette_group: str
    instance: bool
    description: str = ""
    visible: bool = True
    user_modifiable: bool = True
    hide_when_no_value: bool = False


def load_profile(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        prof = json.load(fh)
    if not isinstance(prof, dict) or prof.get("schema") != PROFILE_SCHEMA:
        raise ProfileError(f"{path}: not a {PROFILE_SCHEMA} parameter profile")
    for key in ("families", "parameters"):
        if not isinstance(prof.get(key), dict):
            raise ProfileError(f"{path}: profile has no {key!r} table")
    return prof


def _param(prof: Dict[str, Any], guid: str, instance: bool, group: str) -> ProfileParam:
    d = prof["parameters"][guid]
    return ProfileParam(guid=guid, name=d["name"], def_class=d["def_class"], spec=d.get("spec"),
                        palette_group=group, instance=bool(instance),
                        description=d.get("description", ""), visible=d.get("visible", True),
                        user_modifiable=d.get("user_modifiable", True),
                        hide_when_no_value=d.get("hide_when_no_value", False))


def select(prof: Dict[str, Any], *, category: Optional[int] = None, family: Optional[str] = None,
           share: float = 0.5) -> Tuple[List[ProfileParam], List[str]]:
    """(parameters, notes) the profile gives a family of ``category`` -- or the
    exact set of profile ``family``.  Ordered by name, then GUID (deterministic)."""
    notes: List[str] = []
    fams = prof["families"]
    if isinstance(share, bool) or not isinstance(share, (int, float)) or not (0 < share <= 1):
        raise ProfileError(f"share {share!r} must be a number in (0, 1]")
    if family is not None:
        if family not in fams:
            raise ProfileError(f"profile has no family {family!r}")
        rows = [q for q in fams[family]["params"] if q.get("instance") is not None]
        out = [_param(prof, q["guid"], q["instance"], q.get("palette_group", "")) for q in rows
               if q["guid"] in prof["parameters"]]
        notes.append(f"profile family {family!r}: {len(out)} of its shared parameters")
    else:
        pool = [f for f in fams.values() if f.get("category") == category]
        if not pool:
            return [], [f"profile holds no family of category {category}: nothing applied"]
        seen: Dict[str, List[dict]] = {}
        for f in pool:
            for q in f["params"]:
                if q.get("instance") is not None and q["guid"] in prof["parameters"]:
                    seen.setdefault(q["guid"], []).append(q)
        need = max(1, math.ceil(len(pool) * share - 1e-9))     # ceil, float-safe (0.7 x 10 = 7)
        out = []
        for guid, qs in seen.items():
            if len(qs) < need:
                continue
            binds = Counter(bool(q["instance"]) for q in qs)
            groups = Counter(q.get("palette_group", "") for q in qs)
            if binds[True] == binds[False]:
                notes.append(f"{prof['parameters'][guid]['name']!r}: bound by instance and by type "
                             f"equally often -- written by type")
            out.append(_param(prof, guid, binds[True] > binds[False],
                              sorted(groups.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]))
        notes.append(f"category {category}: {len(out)} shared parameters carried by at least "
                     f"{int(need)} of the profile's {len(pool)} families of that category")
    return sorted(out, key=lambda p: (p.name, p.guid)), notes


def _value_for(p: ProfileParam, values: Dict[str, Any]) -> Tuple[Any, Optional[str], Optional[str]]:
    """(default value, formula, refusal) the caller's ``values`` give ``p`` -- keyed by
    GUID or by name; a missing entry is blank.  A value must suit the storage class
    (text for text / URL, Yes/No as a bool or 0/1, a number for a measurable value in
    internal units); anything else is refused, never coerced."""
    v = values.get(p.guid.lower(), values.get(p.name))
    blank = WRITABLE[p.def_class]
    if v is None:
        return blank, None, None
    if isinstance(v, dict) and "formula" in v:
        if p.def_class == "ParamDefMaterialBrowse":
            return blank, None, "a formula (a material is not written by formula)"
        return blank, str(v["formula"]), None
    if p.def_class in ("ParamDefString", "ParamDefURL"):
        return (str(v), None, None) if isinstance(v, str) else (blank, None, "not text")
    if p.def_class == "ParamDefYesNo":
        return ((int(bool(v)), None, None) if isinstance(v, bool) or v in (0, 1)
                else (blank, None, "not Yes/No"))
    if p.def_class in ("ParamDefInt", "ParamDefNoOfPoles"):
        return ((int(v), None, None) if isinstance(v, int) and not isinstance(v, bool)
                else (blank, None, "not an integer"))
    if p.def_class == "ParamDefValue":
        return ((float(v), None, None) if isinstance(v, (int, float)) and not isinstance(v, bool)
                and math.isfinite(v) else (blank, None, "not a finite number"))
    return blank, None, f"no value is written for a {p.def_class}"


def apply(doc, params: List[ProfileParam], values: Optional[Dict[str, Any]] = None,
          values_source: str = "the caller") -> List[str]:
    """Add ``params`` to the (unfinalized or re-finalizable) family ``doc`` as SHARED
    parameters -- blank, unless ``values`` (keyed by GUID or name) gives one: a
    constant, or ``{"formula": "Width"}`` written as the parameter's formula
    (:mod:`rvt.famgen.formula`; one it cannot store is left out and said at build).
    Returns the notes (what was added, filled, left, or not writable).  The caller
    finalizes the document afterwards."""
    from .skeleton import PGROUP_DIMENSIONS
    notes: List[str] = []
    values = {(str(k).lower() if _GUID.match(str(k)) else str(k)): v
              for k, v in (values or {}).items()}
    filled = 0
    have_guid = {str(pe.refs.get("guid", "")).lower() for pe in doc.params.values()}
    added = 0
    for p in params:
        if p.def_class not in WRITABLE:
            notes.append(f"{p.name!r}: storage class {p.def_class} is not written by this writer "
                         f"-- left out")
            continue
        if p.guid.lower() in have_guid:
            notes.append(f"{p.name!r}: already carried at the same GUID -- kept as authored")
            continue
        if p.name in doc.params:
            notes.append(f"{p.name!r}: the family already authors a parameter of this name -- "
                         f"kept as authored, the profile's definition left out")
            continue
        default, formula, refused = _value_for(p, values)
        if refused:
            notes.append(f"{p.name!r}: the given value is {refused} for a {p.def_class} -- "
                         f"left blank")
        pe = doc.add_shared_parameter(p.name, p.guid,
                                      p.spec or CLASS_SPEC.get(p.def_class, ""),
                                      p.palette_group or PGROUP_DIMENSIONS,
                                      kind=p.def_class, description=p.description,
                                      default=default)
        pe.refs["instance"] = p.instance
        if formula:
            pe.refs["formula"] = formula
        if formula or default != WRITABLE[p.def_class]:
            filled += 1
        pe.obj["m_hideWhenNoValue"] = bool(p.hide_when_no_value)
        pe.obj["m_userModifiable"] = bool(p.user_modifiable)
        pe.obj["m_pParamDef"]["value"]["m_userVisible"] = bool(p.visible)
        have_guid.add(p.guid.lower())
        added += 1
    notes.insert(0, f"parameter profile: {added} shared parameters added, {filled} of them "
                    f"given a value or formula from {values_source} (a formula the writer "
                    f"cannot store is left out and said at build), the rest blank "
                    f"({sum(1 for p in params if p.instance)} of {len(params)} selected bound per instance)")
    unused = sorted(set(values) - {p.guid.lower() for p in params} - {p.name for p in params})
    if unused:
        notes.append(f"values given for parameters the profile did not select: {', '.join(unused)}")
    return notes


@dataclass
class ProfileRequest:
    """``shared_params=`` for a family constructor: apply ``profile`` (a path or a
    loaded profile) at the document's first finalize -- ``family`` names one profile
    family to mirror, else the document's category is matched at ``share``.  ``rows``
    = an optional shared-parameter file handled exactly as a plain ``shared_params``."""
    profile: Any
    family: Optional[str] = None
    share: float = 0.5
    rows: Any = None
    #: values to fill, keyed by GUID or name (a dict, or a path to a JSON of one):
    #: a constant or {"formula": "..."}; everything else stays blank
    values: Any = None
    is_param_profile_request = True           # duck-typed by rvt.famgen.skeleton (no import cycle)

    def loaded(self) -> Dict[str, Any]:
        if isinstance(self.profile, str):
            self.profile = load_profile(self.profile)
        return self.profile


def apply_request(doc, req: ProfileRequest) -> List[str]:
    """Select and :func:`apply` ``req`` to ``doc`` (its own category); the notes."""
    sel, notes = select(req.loaded(), category=doc.category_id, family=req.family, share=req.share)
    values, source = req.values, "the given values"
    if isinstance(values, str):
        source = f"the values file {os.path.basename(values)!r}"
        with open(values, "r", encoding="utf-8") as fh:
            values = json.load(fh)
    if values is not None and not isinstance(values, dict):
        raise ProfileError(f"values must map parameter names / GUIDs to values, not "
                           f"{type(values).__name__}")
    return apply(doc, sel, values or {}, source) + notes
