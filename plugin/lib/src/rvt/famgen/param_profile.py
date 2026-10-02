"""param_profile -- apply a USER'S parameter profile to a family we generate (#866).

A parameter profile (``tekton.param-profile/1``, written by
``tools/shared_params_from_rfa.py`` from the user's OWN families) says which
shared parameters the families of a library carry, per family, bound by instance
or by type.  Applied to a family we build, it adds the same SHARED definitions --
same GUID, name, storage class, spec, palette group, flags -- so the generated
family schedules and tags alongside the user's library.

Values, in order of authority (S-2026-08-11-a: an empty standard parameter is
correct, an invented one is not):

* the caller's own ``values`` (a constant, or ``{"formula": "..."}``) -- tier ``given``;
* else the library's CONVENTION for the parameter (#875), read from the profile
  rows: a FORMULA when every carrying family uses the same one, a CONSTANT only
  when two or more families hold it and agree -- tier ``library``, cited to the
  profile; product data that differs between families, material ids and family
  types never carry; a text formula is written as the formula it is (#870) -- a
  string constant or an ``if()`` choosing between texts, as the library stores it;
* else BLANK -- the all-empty value row a Revit-born family itself stores for a
  parameter nobody filled (``m_str`` "", ``m_int`` 0, ``m_value`` 0.0,
  ``m_elemId`` -1).

Each filled parameter carries ``refs["provenance"]`` and is named in the notes with
its tier.  A parameter the family already authors (same GUID, or same caption) is
left as the family authored it and said so.

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
#: (a text / Yes-No / integer parameter is not a length: formula.py refuses integer
#: operands, types Yes/No logic and takes text only as a value, #870) -- a
#: ParamDefValue carries its own spec
CLASS_SPEC = {
    "ParamDefString": "autodesk.spec:spec.string-1.0.0",
    "ParamDefURL": "autodesk.spec:spec.string-1.0.0",
    "ParamDefYesNo": "autodesk.spec:spec.bool-1.0.0",
    "ParamDefInt": "autodesk.spec:spec.int64-1.0.0",
    "ParamDefNoOfPoles": "autodesk.spec:spec.int64-1.0.0",
    "ParamDefMaterialBrowse": "autodesk.spec:spec.string-1.0.0",
    # a measurable definition that arrived WITHOUT its spec (an older / hand-edited
    # profile): the writer stores it as a number, so the formula check types it so
    "ParamDefValue": "autodesk.spec.aec:number-1.0.0",
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
    #: how the library fills it, when that is a CONVENTION (#875): {"formula": text}
    #: when every carrying family uses that formula, {"value": v} when at least two
    #: families carry it and all hold that value -- never one product's own data
    convention: Optional[Dict[str, Any]] = None


def _convention(rows: List[dict], def_class: str) -> Optional[Dict[str, Any]]:
    """The library's convention for one parameter from the rows that carry it, or None.

    A FORMULA is structure (how a family is built): taken when every row carries the
    same readable one.  A CONSTANT is data: taken only when two or more families hold
    it and all agree -- a value one family holds is that product's (a 500 kVA unit's
    rating must not label a 45 kVA one).  A material / family-type value is an element
    id of the source document: never carried."""
    if def_class in ("ParamDefMaterialBrowse", "ParamDefFamType") or not rows:
        return None
    if any(not isinstance(q, dict) or q.get("formula_unread") for q in rows):
        return None
    # '""' is how an empty string constant spells: Revit's own "no formula" (formula.is_no_formula)
    forms = [None if q.get("formula") in (None, '""') else q.get("formula") for q in rows]
    if any(f is not None and not isinstance(f, str) for f in forms):
        return None                                   # a malformed row: no convention for THIS parameter
    if all(f is not None for f in forms) and len(set(forms)) == 1:
        return {"formula": forms[0]}
    if any(f is not None for f in forms):
        return None                                   # some rows are formula-driven, some not
    vals = [q.get("value") for q in rows]
    if len(rows) >= 2 and all(v is not None for v in vals) and len({repr(v) for v in vals}) == 1:
        v = vals[0]
        if isinstance(v, (str, int, float)) and not isinstance(v, bool):
            return {"value": v}
    return None


def load_profile(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        prof = json.load(fh)
    if not isinstance(prof, dict) or prof.get("schema") != PROFILE_SCHEMA:
        raise ProfileError(f"{path}: not a {PROFILE_SCHEMA} parameter profile")
    for key in ("families", "parameters"):
        if not isinstance(prof.get(key), dict):
            raise ProfileError(f"{path}: profile has no {key!r} table")
    return prof


def _flag(v: Any, default: bool) -> bool:
    return v if isinstance(v, bool) else default


def _param(prof: Dict[str, Any], guid: Any, instance: Any, group: Any
           ) -> Tuple[Optional[ProfileParam], Optional[str]]:
    """(the parameter, None) or (None, why it is skipped).  Every field is checked
    HERE, before anything is added to a document, so a malformed profile row is
    skipped and said -- never a failed build, never a half-applied profile."""
    g = str(guid).strip() if isinstance(guid, str) else ""
    if g.startswith("{") and g.endswith("}"):
        g = g[1:-1]                                          # a braced GUID, as hand-written
    if not _GUID.match(g):
        return None, f"GUID {str(guid)[:60]!r} is not a GUID"
    d = prof["parameters"].get(guid)
    if not isinstance(d, dict):
        return None, f"GUID {g} has no definition"
    name, cls = d.get("name"), d.get("def_class")
    if not isinstance(name, str) or not name.strip():
        return None, f"GUID {g}: no parameter name"
    if not isinstance(cls, str):
        return None, f"{name[:60]!r}: no storage class"
    spec = d.get("spec")
    return ProfileParam(guid=g.lower(), name=name, def_class=cls,
                        spec=spec if isinstance(spec, str) else None,
                        palette_group=group if isinstance(group, str) else "",
                        instance=bool(instance) if isinstance(instance, (bool, int)) else False,
                        description=d.get("description") if isinstance(d.get("description"), str) else "",
                        visible=_flag(d.get("visible"), True),
                        user_modifiable=_flag(d.get("user_modifiable"), True),
                        hide_when_no_value=_flag(d.get("hide_when_no_value"), False)), None


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
        out = []
        for q in fams[family]["params"]:
            if not isinstance(q, dict) or q.get("instance") is None \
                    or not isinstance(q.get("guid"), str):
                continue
            par, why = _param(prof, q["guid"], q["instance"], q.get("palette_group", ""))
            if why:
                notes.append(f"profile parameter skipped: {why}")
            else:
                par.convention = _convention([q], par.def_class)
                out.append(par)
        notes.append(f"profile family {family!r}: {len(out)} of its shared parameters")
    else:
        pool = [f for f in fams.values() if f.get("category") == category]
        if not pool:
            return [], [f"profile holds no family of category {category}: nothing applied"]
        seen: Dict[str, List[dict]] = {}
        for f in pool:
            for q in f["params"]:
                if isinstance(q, dict) and q.get("instance") is not None \
                        and isinstance(q.get("guid"), str) and q["guid"] in prof["parameters"]:
                    seen.setdefault(q["guid"], []).append(q)
        need = max(1, math.ceil(len(pool) * share - 1e-9))     # ceil, float-safe (0.7 x 10 = 7)
        out = []
        for guid, qs in seen.items():
            if len(qs) < need:
                continue
            binds = Counter(bool(q["instance"]) for q in qs)
            groups = Counter(q.get("palette_group") if isinstance(q.get("palette_group"), str)
                             else "" for q in qs)
            par, why = _param(prof, guid, binds[True] > binds[False],
                              sorted(groups.items(), key=lambda kv: (-kv[1], kv[0]))[0][0])
            if why:
                notes.append(f"profile parameter skipped: {why}")
                continue
            if binds[True] == binds[False]:
                notes.append(f"{par.name!r}: bound by instance and by type equally often -- "
                             f"written by type")
            par.convention = _convention(qs, par.def_class)
            out.append(par)
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
        # the stored integer is 32-bit (m_int): a wider one (a serial number given as a
        # JSON integer) would fail the whole family at encode time -- refused instead
        return ((int(v), None, None) if isinstance(v, int) and not isinstance(v, bool)
                and -2**31 <= v <= 2**31 - 1 else (blank, None, "not a 32-bit integer"))
    if p.def_class == "ParamDefValue":
        try:
            f = float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None
        except OverflowError:                         # a JSON integer with hundreds of digits
            f = None
        return ((f, None, None) if f is not None and math.isfinite(f)
                else (blank, None, "not a finite number"))
    return blank, None, "not writable for this storage class"


def _given(p: ProfileParam, values: Dict[str, Any]) -> Any:
    return values.get(p.guid.lower(), values.get(p.name))


def _from_convention(p: ProfileParam) -> Tuple[Any, Optional[str], Optional[str], bool]:
    """(default, formula, refusal, True) for ``p``'s library convention.  A formula
    -- a text one included (#870): a string constant or an ``if()`` choosing between
    texts is written as the formula the library stores, never flattened to a value."""
    blank = WRITABLE[p.def_class]
    conv = p.convention or {}
    if "formula" in conv:
        return blank, conv["formula"], None, True
    got = _value_for(p, {p.name: conv.get("value")}) if "value" in conv else (blank, None, None)
    return got[0], got[1], got[2], True


def _spec_kind(spec: str) -> str:
    """``spec`` without its schema version ('...:length-2.0.0' -> '...:length')."""
    head, sep, tail = str(spec).rpartition("-")         # the rule of skeleton._canonical_spec
    return head if sep and tail.count(".") == 2 and all(x.isdigit() for x in tail.split(".")) \
        else str(spec)


def _link(doc, p: "ProfileParam", target: Any) -> Tuple[Optional[str], Optional[str]]:
    """(formula, refusal) for a profile-map entry linking ``p`` to the generated
    family's own parameter ``target`` (#876): the formula is the target's name, so the
    library parameter carries the family's value in every type.  Refused, with the
    reason, when the target is not a parameter of this family, cannot be named in a
    formula, holds another kind of value than ``p`` (a length is never linked to a
    number, a text to a length), is an integer (formulas take no integer operand),
    or is bound per INSTANCE while ``p`` is a type parameter (a type formula cannot
    read an instance parameter) -- every refusal the formula step itself would make,
    made here so no link is announced that the family will not carry; never coerced."""
    from . import formula as FX
    from .skeleton import SPEC_LENGTH, _is_instance_param
    if not isinstance(target, str) or not target:
        return None, f"the map entry is {target!r}, not a parameter name"
    if p.def_class == "ParamDefMaterialBrowse":
        return None, "a material is not written by formula"
    pe = doc.params.get(target)
    if pe is None:
        return None, f"the family has no parameter {target!r}"
    if pe.refs.get("kind") == "ParamDefMaterialBrowse":
        return None, f"{target!r} is a material, not written by formula"
    if not FX.is_spellable(target):
        return None, f"{target!r} cannot be named in a formula"
    mine = _spec_kind(p.spec or CLASS_SPEC.get(p.def_class, ""))
    theirs = _spec_kind(pe.refs.get("spec") or SPEC_LENGTH)   # as skeleton._formula_spec reads it
    if "spec.int64" in (mine + theirs):
        return None, "an integer is not linked by formula (formulas take no integer operand)"
    if not p.instance and _is_instance_param(pe):
        return None, (f"{target!r} is bound per instance and the library parameter per type: "
                      f"a type formula cannot read an instance parameter")
    if mine != theirs:
        return None, (f"{target!r} is a {theirs.split(':')[-1]}, the library parameter a "
                      f"{mine.split(':')[-1]}")
    return target, None


def apply(doc, params: List[ProfileParam], values: Optional[Dict[str, Any]] = None,
          values_source: str = "the caller", profile_source: str = "the profile",
          links: Optional[Dict[str, Any]] = None,
          links_source: str = "the profile map") -> List[str]:
    """Add ``params`` to the (unfinalized or re-finalizable) family ``doc`` as SHARED
    parameters -- filled from ``values`` (keyed by GUID or name: a constant, or
    ``{"formula": "Width"}``) when given, else from the parameter's library
    convention (``ProfileParam.convention``), else blank.  A formula is written by
    :mod:`rvt.famgen.formula` at finalize; one it cannot store is left out, said, and
    loses its provenance tag (:func:`settle_formula_provenance`).
    ``links`` (#876, keyed like ``values``) maps a profile parameter to the generated
    family's OWN parameter it stands for (``{"<library Width GUID>": "Width"}``): it
    is written as a formula naming that parameter, tagged ``given`` from
    ``links_source``, so the library parameter tracks the family in every type.  A
    caller's value for the same parameter wins; a link that cannot hold (no such
    parameter, another kind of value) is refused and said.
    Returns the notes (what was added, filled, left, or not writable).  The caller
    finalizes the document afterwards."""
    from .skeleton import PGROUP_DIMENSIONS
    notes: List[str] = []
    values = {(str(k).lower() if _GUID.match(str(k)) else str(k)): v
              for k, v in (values or {}).items()}
    links = {(str(k).lower() if _GUID.match(str(k)) else str(k)): v
             for k, v in (links or {}).items()}
    linked: List[str] = []
    filled = 0
    conv_values: List[str] = []
    conv_formulas: List[str] = []
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
        target = links.get(p.guid.lower(), links.get(p.name))
        link_used = False
        if target is not None and _given(p, values) is not None:
            notes.append(f"{p.name!r}: the map links it to {target!r}, but a value was given "
                         f"-- the given value is written")
        link_refused = None
        if target is not None and _given(p, values) is None:
            formula, link_refused = _link(doc, p, target)
            if not link_refused:
                link_used = True
                linked.append(f"{p.name!r} = {target!r}")
        from_convention = False
        if (default == WRITABLE[p.def_class] and formula is None and not refused
                and p.convention and _given(p, values) is None and not link_used):
            # a refused link never costs the parameter the library's own convention
            default, formula, refused, from_convention = _from_convention(p)
        if link_refused:
            notes.append(f"{p.name!r}: the map's link is refused -- {link_refused} -- "
                         + ("the library's convention is written instead"
                            if from_convention and not refused else "left blank"))
        if refused and from_convention:
            what = refused if refused.startswith("the library's") else \
                f"the library's convention value is {refused} for a {p.def_class}"
            notes.append(f"{p.name!r}: {what} -- left blank")
        elif refused:
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
        if formula or default != WRITABLE[p.def_class] or (from_convention and not refused):
            # a convention is reported even when its value equals the blank row (a Yes/No
            # the library holds at No): the library said so, the file says the same
            if from_convention:
                (conv_formulas if formula else conv_values).append(p.name)
                pe.refs["provenance"] = {"tier": "library", "source": profile_source,
                                         "by": "formula" if formula else "value"}
            elif link_used:
                pe.refs["provenance"] = {"tier": "given", "source": links_source,
                                         "by": "formula", "link": formula}
            else:
                filled += 1
                pe.refs["provenance"] = {"tier": "given", "source": values_source,
                                         "by": "formula" if formula else "value"}
            if formula:
                # what a formula CLAIMS, kept apart from the tag: each finalize settles
                # the tag from it (settle_formula_provenance), so a formula refused on
                # one finalize and written on a later one is tagged again
                pe.refs["formula_provenance"] = {"tag": dict(pe.refs["provenance"]),
                                                 "formula": formula}
        pe.obj["m_hideWhenNoValue"] = bool(p.hide_when_no_value)
        pe.obj["m_userModifiable"] = bool(p.user_modifiable)
        pe.obj["m_pParamDef"]["value"]["m_userVisible"] = bool(p.visible)
        have_guid.add(p.guid.lower())
        added += 1
    conventional = len(conv_values) + len(conv_formulas)
    notes.insert(0, f"parameter profile: {added} shared parameters added, {filled} of them "
                    f"given a value or formula from {values_source}, {conventional} from the "
                    f"library's own conventions in {profile_source} ({len(conv_values)} values, "
                    f"{len(conv_formulas)} formulas -- a formula is checked when the family is "
                    f"finalized, and one the writer cannot store is named in a 'NOT written' "
                    f"note and stays blank), the rest blank "
                    f"({sum(1 for p in params if p.instance)} of {len(params)} selected bound per instance)")
    if conventional:
        notes.insert(1, f"provenance library ({profile_source}): "
                        + "; ".join([f"{n!r} by value" for n in conv_values]
                                    + [f"{n!r} by formula" for n in conv_formulas]))
    if linked:
        notes.insert(1, f"linked by {links_source} to the family's own parameters (a formula "
                        f"each, so the value follows every type): " + "; ".join(linked))
    unused = sorted(set(values) - {p.guid.lower() for p in params} - {p.name for p in params})
    if unused:
        notes.append(f"values given for parameters the profile did not select: {', '.join(unused)}")
    unlinked = sorted(set(links) - {p.guid.lower() for p in params} - {p.name for p in params})
    if unlinked:
        notes.append(f"map entries for parameters the profile did not select: {', '.join(unlinked)}")
    return notes


def settle_formula_provenance(doc, written_ids) -> None:
    """After the formulas are written (``written_ids`` = the parameter ids that got
    one): a parameter filled BY FORMULA -- from the library or given -- carries its
    provenance tag only when its formula was written; one refused carries no value, so
    its tag is dropped, it leaves the provenance line, and a note names it.  Settled
    afresh on every finalize from the claim :func:`apply` recorded, so a formula
    refused once and written on a later finalize is tagged and listed again and the
    notes say only what the latest finalize wrote.  Idempotent."""
    written_ids = set(written_ids)
    dropped: Dict[str, List[str]] = {"library": [], "given": []}
    library: Dict[str, Tuple[List[str], List[str]]] = {}     # source -> (by value, by formula)
    for name, pe in doc.params.items():
        claim = pe.refs.get("formula_provenance")
        if claim and pe.refs.get("formula") != claim["formula"]:
            # the formula was replaced after the profile filled it: no longer its claim
            pe.refs.pop("formula_provenance")
            if pe.refs.get("provenance") == claim["tag"]:
                pe.refs.pop("provenance")
        elif claim:
            if pe.elem_id in written_ids:
                pe.refs["provenance"] = dict(claim["tag"])
            else:
                pe.refs.pop("provenance", None)
                dropped.setdefault(claim["tag"].get("tier"), []).append(name)
        prov = pe.refs.get("provenance") or {}
        if prov.get("tier") == "library":
            by_value, by_formula = library.setdefault(str(prov.get("source")), ([], []))
            (by_formula if prov.get("by") == "formula" else by_value).append(name)
    for i, n in enumerate(doc.notes):
        if n.startswith("provenance library ("):
            # each profile's line from its OWN parameters (a document two profiles were
            # applied to keeps two lines, each true of its source)
            head, _sep, _body = n.partition("): ")
            by_value, by_formula = library.get(head[len("provenance library ("):], ([], []))
            kept = [f"{d!r} by value" for d in by_value] + [f"{d!r} by formula" for d in by_formula]
            doc.notes[i] = f"{head}): {'; '.join(kept)}" if kept else f"{head}): none written"
    # the map's line (#876) lists only the links still carried: one the formula step
    # refused is not announced as following every type
    for i, n in enumerate(doc.notes):
        if n.startswith("linked by "):
            head, _sep, _body = n.partition("): ")
            kept = [f"{name!r} = {pe.refs['provenance']['link']!r}"
                    for name, pe in doc.params.items()
                    if (pe.refs.get("provenance") or {}).get("link")
                    and head.startswith(f"linked by {pe.refs['provenance'].get('source')} ")]
            doc.notes[i] = f"{head}): {'; '.join(kept)}" if kept else f"{head}): none written"
    doc.notes[:] = [n for n in doc.notes if not n.startswith(_NOT_WRITTEN_NOTES)]
    for tier, names in dropped.items():
        if names:
            doc.notes.append(f"{tier} formulas not written, so these parameters carry no {tier} "
                             "value: " + ", ".join(repr(d) for d in sorted(names)))


#: the notes :func:`settle_formula_provenance` owns (rebuilt on every finalize)
_NOT_WRITTEN_NOTES = ("library formulas not written", "given formulas not written")


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
    #: the PROFILE MAP (#876): profile parameter (GUID or name) -> the generated
    #: family's own parameter it stands for (a dict, or a path to a JSON of one)
    links: Any = None
    is_param_profile_request = True           # duck-typed by rvt.famgen.skeleton (no import cycle)

    def loaded(self) -> Dict[str, Any]:
        if isinstance(self.profile, str):
            self.profile = load_profile(self.profile)
        return self.profile


def apply_request(doc, req: ProfileRequest) -> List[str]:
    """Select and :func:`apply` ``req`` to ``doc`` (its own category); the notes."""
    prof_src = (f"the profile {os.path.basename(req.profile)!r}" if isinstance(req.profile, str)
                else "the given profile")              # named before loaded() replaces the path
    sel, notes = select(req.loaded(), category=doc.category_id, family=req.family, share=req.share)
    values, source = req.values, "the given values"
    if isinstance(values, str):
        source = f"the values file {os.path.basename(values)!r}"
        with open(values, "r", encoding="utf-8") as fh:
            values = json.load(fh)
    if values is not None and not isinstance(values, dict):
        raise ProfileError(f"values must map parameter names / GUIDs to values, not "
                           f"{type(values).__name__}")
    links, links_source = req.links, "the given profile map"
    if isinstance(links, str):
        links_source = f"the profile map {os.path.basename(links)!r}"
        with open(links, "r", encoding="utf-8") as fh:
            links = json.load(fh)
    if links is not None and not isinstance(links, dict):
        raise ProfileError(f"a profile map must map parameter names / GUIDs to the family's "
                           f"parameter names, not {type(links).__name__}")
    return apply(doc, sel, values or {}, source, prof_src, links or {}, links_source) + notes
