"""shared_params_from_rfa -- a USER'S shared-parameter library, read from their own families.

Every shared parameter a family carries (``ParamElemExternal``: the GUID a project
schedule or tag binds by, its name, its definition class and spec) is collected
from the ``.rfa`` files given, across releases (each file is read inside its OWN
release, ``rvt.global_framing.enter_own_release``), and written as:

* a Revit shared-parameter TXT (the documented tab-separated grammar Revit itself
  reads: ``*META`` / ``*GROUP`` / ``*PARAM``), GUIDs copied (normalised to lowercase,
  as Revit and our reader compare them); and
* a PARAMETER PROFILE JSON: for every source family, which of those parameters it
  carries, instance or type (``null`` = the document only defines it, for a label or
  a nested family -- not a parameter of the family itself), and in which palette
  group -- what a generated family of the same kind applies at build
  (``make_family --param-profile``, #866).

DATATYPE is never guessed: it comes from the definition class or the measurable
spec; two browse-edit classes are mapped by inference (counted in the summary); a
parameter with no known token stays in the profile and is left OUT of the TXT,
named.  A name carried by two GUIDs is legal in Revit's file but refused by OUR
reader (``read_shared_parameter_file``) -- the summary counts them.

WHY (steer #865): the owner works with a commercial content library whose families
all run on one master shared-parameter set; generated families that carry the same
definitions schedule and tag alongside it.  The library's content is the USER'S:
this tool reads it from their own files at their request and writes where they say
-- never into this repository (rule 6: the repo is public), never into the product
(hard rule 3).  This module holds no library content of any kind.

USAGE
    python tools/shared_params_from_rfa.py FAMILY.rfa [FAMILY.rfa ...] \\
        --txt OUT.txt --profile OUT.json [--json]
    (a directory argument means every .rfa in it)

Exit 0 when every file was read; 1 when any file could not be, or a directory held
no .rfa (each named).
Read-only on the inputs.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import ExitStack
from typing import Any, Dict, Iterable, List, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if os.path.join(_ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(_ROOT, "src"))

#: ``ParamDef*`` storage class -> shared-parameter-file DATATYPE, where the class
#: alone decides it (the measurable ``ParamDefValue`` is decided by its spec below)
DEF_CLASS_DATATYPE = {
    "ParamDefString": "TEXT",
    "ParamDefYesNo": "YESNO",
    "ParamDefInt": "INTEGER",
    "ParamDefMaterialBrowse": "MATERIAL",
    "ParamDefURL": "URL",
    "ParamDefNoOfPoles": "NUMBER_OF_POLES",
    "ParamDefFamType": "FAMILYTYPE",            # DATACATEGORY = its m_categoryId (the one row kind that uses it)
}

#: classes whose token is INFERRED from the class hierarchy, not observed in a
#: shared-parameter file written by Revit: both are ``ParamDefBrowseEdit``
#: subclasses (the "..." dialog editor) with no fields of their own, the text
#: one storing its value in the row's ``m_str`` -- Revit's multi-line text and
#: image parameter types.  Counted as ``datatypes_inferred`` in the summary.
INFERRED_CLASS_DATATYPE = {
    "ParamDefTextBrowseEdit": "MULTILINETEXT",
    "ParamDefImageSymbolBrowseEdit": "IMAGE",
}

#: measurable spec (version-less) -> DATATYPE token, including the text / integer /
#: Yes-No specs OUR writer puts on a ``ParamDefValue`` (#165).  A spec with no token
#: here has NO known token: the parameter stays in the profile and is left OUT of
#: the TXT (named in the summary), never written under a guessed token.
SPEC_DATATYPE = {
    "autodesk.spec:spec.string": "TEXT",
    "autodesk.spec:spec.int64": "INTEGER",
    "autodesk.spec.aec:integer": "INTEGER",
    "autodesk.spec:spec.bool": "YESNO",
    "autodesk.spec.aec:length": "LENGTH",
    "autodesk.spec.aec:number": "NUMBER",
    "autodesk.spec.aec:angle": "ANGLE",
    "autodesk.spec.aec:area": "AREA",
    "autodesk.spec.aec:volume": "VOLUME",
    "autodesk.spec.aec:slope": "SLOPE",
    "autodesk.spec.aec:currency": "CURRENCY",
    "autodesk.spec.aec.structural:mass": "MASS",
    "autodesk.spec.aec.structural:force": "FORCE",
    "autodesk.spec.aec.electrical:current": "ELECTRICAL_CURRENT",
    "autodesk.spec.aec.electrical:potential": "ELECTRICAL_POTENTIAL",
    "autodesk.spec.aec.electrical:power": "ELECTRICAL_POWER",
    "autodesk.spec.aec.electrical:apparentPower": "ELECTRICAL_APPARENT_POWER",
    "autodesk.spec.aec.electrical:wattage": "ELECTRICAL_WATTAGE",
    "autodesk.spec.aec.electrical:frequency": "ELECTRICAL_FREQUENCY",
    "autodesk.spec.aec.electrical:luminousFlux": "ELECTRICAL_LUMINOUS_FLUX",
    "autodesk.spec.aec.electrical:efficacy": "ELECTRICAL_EFFICACY",
    "autodesk.spec.aec.electrical:colorTemperature": "COLOR_TEMPERATURE",
}


def _versionless(spec: Optional[str]) -> str:
    return str(spec or "").rsplit("-", 1)[0]


def datatype_of(def_class: str, spec: Optional[str]) -> Tuple[Optional[str], str]:
    """(DATATYPE token, basis) with basis ``class`` / ``spec`` / ``inferred`` /
    ``unknown``.  ``unknown`` -> token None: no token is ever guessed."""
    if def_class in DEF_CLASS_DATATYPE:
        return DEF_CLASS_DATATYPE[def_class], "class"
    if def_class in INFERRED_CLASS_DATATYPE:
        return INFERRED_CLASS_DATATYPE[def_class], "inferred"
    tok = SPEC_DATATYPE.get(_versionless(spec)) if spec else None
    if tok:
        return tok, "spec"
    return None, "unknown"


def _files(args: Iterable[str]) -> Tuple[List[str], List[str]]:
    """(.rfa paths, errors).  A directory means every .rfa in it (any case); the
    same file named twice is read once; a directory with none is an error."""
    out: List[str] = []
    errors: List[str] = []
    seen = set()
    for a in args:
        if os.path.isdir(a):
            found = sorted(os.path.join(a, n) for n in os.listdir(a)
                           if n.lower().endswith(".rfa") and os.path.isfile(os.path.join(a, n)))
            if not found:
                errors.append(f"{a}: no .rfa file in this directory")
        else:
            found = [a]
        for p in found:
            key = os.path.normcase(os.path.realpath(p))
            if key not in seen:
                seen.add(key)
                out.append(p)
    return out, errors


def read_index(fi) -> Dict[str, Any]:
    """Every shared parameter of one opened family document (``fi`` = a
    ``rvt.families.FamilyIndex`` or anything with its ``unit_records`` /
    ``class_name`` / ``value``), with how the document's OWN Family element
    (``m_surrogateId == -1``; a nested family's surrogate is not it) binds it.

    ``instance`` is True / False for a parameter of the family itself and None
    for one the document only DEFINES -- referenced by a label or a nested
    family, not a parameter of this family.  ``self_families`` = how many own
    Family elements were found (1 in a well-formed family; anything else is
    reported by :func:`build`)."""
    params: List[Dict[str, Any]] = []
    recs = fi.unit_records(0).get(102, {})
    instance: Dict[int, bool] = {}
    rows: Dict[int, dict] = {}                   # param id -> the current type's value row
    category = None
    self_families = 0
    for eid, rec in recs.items():
        if fi.class_name(rec.class_id) != "Family":
            continue
        v = fi.value(0, eid) or {}
        if v.get("m_surrogateId") != -1:
            continue
        self_families += 1
        if self_families > 1:                   # never merged: the first one stands, the count is reported
            continue
        category = v.get("m_categoryId")
        for q in ((v.get("m_familyParams") or {}).get("value") or {}).get("m_params") or []:
            instance[int(q["m_paramId"])] = bool(q.get("m_instance"))
            rows[int(q["m_paramId"])] = q
    # every parameter's caption, so a formula reads back over NAMES (#875), and the
    # family's own name table, so the spelling is checked by parsing it back
    from rvt.famgen import formula as FX
    from rvt.famgen.skeleton import _canonical_spec
    names: Dict[int, str] = {}
    refs: Dict[str, Any] = {}
    for eid, rec in recs.items():
        if fi.class_name(rec.class_id) in ("ParamElemExternal", "ParamElemFamily"):
            pd = (fi.value(0, eid) or {}).get("m_pParamDef") or {}
            pv = pd.get("value") or {}
            if pv.get("m_caption"):
                cap = str(pv["m_caption"])
                names[int(eid)] = cap
                spec = (FX.SPEC_YESNO if pd.get("ptr_class") == "ParamDefYesNo" else
                        _canonical_spec((pv.get("m_specTypeId") or {}).get("m_typeId") or FX.SPEC_NUMBER))
                # a caption defined twice (a nested family's definition): the family's own wins
                if cap not in refs or int(eid) in rows:
                    refs[cap] = FX.ParamRef(int(eid), spec)
    table = FX.NameTable(refs)
    for eid, rec in recs.items():
        if fi.class_name(rec.class_id) != "ParamElemExternal":
            continue
        v = fi.value(0, eid) or {}
        pd = v.get("m_pParamDef") or {}
        pv = pd.get("value") or {}
        spec = (pv.get("m_specTypeId") or {}).get("m_typeId")
        dt, basis = datatype_of(pd.get("ptr_class", ""), spec)
        params.append({
            "guid": str(((v.get("m_externalParamKey") or {}).get("m_guidValue")) or "").lower(),
            "name": str(pv.get("m_caption") or ""),
            "def_class": pd.get("ptr_class"),
            "spec": spec,
            "datatype": dt, "datatype_basis": basis,
            "data_category": pv.get("m_categoryId") if pd.get("ptr_class") == "ParamDefFamType" else None,
            "palette_group": (pv.get("m_groupTypeId") or {}).get("m_typeId") or "",
            "instance": instance.get(int(eid)),
            "description": str(v.get("m_description") or ""),
            "visible": bool(pv.get("m_userVisible", True)),
            "user_modifiable": bool(v.get("m_userModifiable", True)),
            "hide_when_no_value": bool(v.get("m_hideWhenNoValue", False)),
            **_value_of(rows.get(int(eid)), pd.get("ptr_class", ""), names, table),
        })
    return {"category": category, "self_families": self_families,
            "params": sorted(params, key=lambda p: (p["name"], p["guid"]))}


#: storage classes whose stored value is transferable between documents, and where it is
#: stored (a material / family-type value is an element id of THIS document: not)
_VALUE_FIELD = {"ParamDefString": "m_str", "ParamDefURL": "m_str", "ParamDefTextBrowseEdit": "m_str",
                "ParamDefYesNo": "m_int", "ParamDefInt": "m_int", "ParamDefNoOfPoles": "m_int",
                "ParamDefValue": "m_value"}


def _value_of(row: Optional[dict], def_class: str, names: Dict[int, str],
              table: Any = None) -> Dict[str, Any]:
    """How the family fills one parameter in its current type (#875): ``value`` (the
    stored text / integer / Yes-No / measurable value in internal units; None when
    blank or not transferable) and ``formula`` (the expression as Revit text over
    parameter NAMES; None when there is none, ``formula_unread`` True when there is
    one this reader cannot spell -- never a guessed text)."""
    out: Dict[str, Any] = {"value": None, "formula": None, "formula_unread": False}
    if not isinstance(row, dict):
        return out
    field = _VALUE_FIELD.get(def_class)
    if field:
        val = row.get(field)
        if field == "m_str":
            out["value"] = val if isinstance(val, str) and val else None
        elif field == "m_int":
            out["value"] = int(val) if isinstance(val, int) and not isinstance(val, bool) else None
            if def_class != "ParamDefYesNo" and not out["value"]:
                out["value"] = None                   # 0 = unset for a count
        else:
            out["value"] = float(val) if isinstance(val, (int, float)) and val else None
    expr = row.get("m_oExpression")
    from rvt.famgen.formula import is_no_formula, unparse, unparse_checked
    if not is_no_formula(expr):                       # an empty string constant = no formula
        text = unparse(expr, names) if table is None else unparse_checked(expr, names, table)
        out["formula"], out["formula_unread"] = text, text is None
    return out


def read_family(path: str) -> Dict[str, Any]:
    """:func:`read_index` of one ``.rfa``, read inside the file's OWN release;
    ``release_note`` = why that release could not be put in force (None = it was)."""
    from rvt import global_framing as GF
    from rvt.families import FamilyIndex
    with ExitStack() as stack:
        note = GF.enter_own_release(stack, path)
        out = read_index(FamilyIndex(path))
    out["release_note"] = note
    return out


#: the fields that make a GUID's definition what it is: any of these differing
#: between two families is a CONFLICT (the first seen is kept, the other listed)
_IDENTITY = ("name", "def_class", "spec_family", "datatype", "datatype_basis", "data_category")
#: fields a library legitimately drifts on between files (a description edited, a
#: spec written at a newer version, a visibility flag) -- a VARIANT, counted and
#: listed, never a conflict; the first seen is kept
_COSMETIC = ("spec", "description", "visible", "user_modifiable", "hide_when_no_value")


def build(paths: Iterable[str]) -> Tuple[Dict[str, Any], List[str]]:
    """(profile, errors).  ``families`` is keyed by file stem -- by the path as given
    when two inputs share a stem (so a consumer naming one family by stem must
    rename such a file).  The profile's ``parameters`` is keyed by GUID and keeps
    the first-seen definition; another family's differing identity field
    (:data:`_IDENTITY`) is listed in ``conflicts``, a differing cosmetic one
    (:data:`_COSMETIC`) in ``variants``; per-file oddities go to ``warnings``."""
    families: Dict[str, Any] = {}
    parameters: Dict[str, Dict[str, Any]] = {}
    conflicts: List[Dict[str, Any]] = []
    variants: List[Dict[str, Any]] = []
    warnings: List[str] = []
    files, errors = _files(paths)
    stems = [os.path.splitext(os.path.basename(p))[0] for p in files]
    for p, stem in zip(files, stems):
        key = stem if stems.count(stem) == 1 else p      # two files of one name: keyed by path
        try:
            fam = read_family(p)
        except Exception as exc:                                   # noqa: BLE001 -- named, not hidden
            errors.append(f"{p}: {type(exc).__name__}: {exc}")
            continue
        if fam.get("release_note"):
            warnings.append(f"{p}: {fam['release_note']}")
        if fam["self_families"] != 1:
            warnings.append(f"{p}: {fam['self_families']} own Family elements (expected 1); "
                            f"instance flags read from the first")
        blank = sum(1 for q in fam["params"] if not q["guid"])
        if blank:
            warnings.append(f"{p}: {blank} shared parameter(s) with no GUID -- left out of "
                            f"the parameter table and the TXT")
        families[key] = {"category": fam["category"],
                         "params": [{"guid": q["guid"], "name": q["name"],
                                     "instance": q["instance"],
                                     "palette_group": q["palette_group"],
                                     "value": q.get("value"), "formula": q.get("formula"),
                                     "formula_unread": q.get("formula_unread", False)}
                                    for q in fam["params"]]}
        for q in fam["params"]:
            if not q["guid"]:
                continue
            d = {k: q[k] for k in _IDENTITY + _COSMETIC if k != "spec_family"}
            d["spec_family"] = _versionless(q["spec"]) or None
            seen = parameters.get(q["guid"])
            if seen is None:
                parameters[q["guid"]] = dict(d, used_by=1)
                continue
            seen["used_by"] += 1
            for fields, sink in ((_IDENTITY, conflicts), (_COSMETIC, variants)):
                diff = [k for k in fields if seen[k] != d[k]]
                if diff:
                    sink.append({"guid": q["guid"], "family": key, "fields": diff,
                                 "kept": {k: seen[k] for k in diff}, "also": {k: d[k] for k in diff}})
    return {"schema": "tekton.param-profile/1", "families": families,
            "parameters": parameters, "conflicts": conflicts, "variants": variants,
            "warnings": warnings}, errors


def _file_group(name: str) -> str:
    return (name.split("_", 1)[0] if "_" in name else "") or "General"


def shared_parameter_txt(profile: Dict[str, Any]) -> str:
    """The profile's parameters as a Revit shared-parameter file.  File GROUPs are the
    name prefix before the first '_' (a file grouping only; the palette group a
    family binds each parameter in is in the profile).  A parameter with no known
    DATATYPE token is left out (:func:`txt_omitted` names them)."""
    params = sorted(((g, p) for g, p in profile["parameters"].items() if p["datatype"]),
                    key=lambda kv: (kv[1]["name"], kv[0]))
    group_names: List[str] = []
    for _g, p in params:
        if _file_group(p["name"]) not in group_names:
            group_names.append(_file_group(p["name"]))
    gid = {g: i + 1 for i, g in enumerate(group_names)}
    lines = ["# This is a Revit shared parameter file.",
             "# Do not edit manually.",
             "*META\tVERSION\tMINVERSION", "META\t2\t1",
             "*GROUP\tID\tNAME"]
    lines += [f"GROUP\t{gid[g]}\t{g}" for g in group_names]
    lines.append("*PARAM\tGUID\tNAME\tDATATYPE\tDATACATEGORY\tGROUP\tVISIBLE\tDESCRIPTION\t"
                 "USERMODIFIABLE\tHIDEWHENNOVALUE")
    for guid, p in params:
        desc = p["description"].replace("\t", " ").replace("\r", " ").replace("\n", " ")
        cat = "" if p.get("data_category") is None else str(int(p["data_category"]))
        lines.append("\t".join(["PARAM", guid, p["name"], p["datatype"], cat,
                                str(gid[_file_group(p["name"])]),
                                "1" if p["visible"] else "0", desc,
                                "1" if p["user_modifiable"] else "0",
                                "1" if p["hide_when_no_value"] else "0"]))
    return "\n".join(lines) + "\n"


def txt_omitted(profile: Dict[str, Any]) -> List[str]:
    """GUIDs the TXT leaves out (no known DATATYPE token), with their class / spec."""
    return [f"{g} ({p['def_class']}, spec {p['spec']})"
            for g, p in sorted(profile["parameters"].items()) if not p["datatype"]]


def summary_of(profile: Dict[str, Any], errors: List[str]) -> Dict[str, Any]:
    params = profile["parameters"].values()
    names: Dict[str, int] = {}
    for p in params:
        names[p["name"]] = names.get(p["name"], 0) + 1
    rows = [q for f in profile["families"].values() for q in f["params"]]
    return {"families": len(profile["families"]), "parameters": len(profile["parameters"]),
            "conflicts": len(profile["conflicts"]),
            "variants": len(profile["variants"]),
            "datatypes_inferred": sum(1 for p in params if p["datatype_basis"] == "inferred"),
            "txt_omitted": txt_omitted(profile),
            # names shared by two GUIDs: legal in Revit's file, but OUR reader
            # (read_shared_parameter_file) refuses such a file -- key by GUID instead
            "duplicate_names": sum(1 for n in names.values() if n > 1),
            "family_rows": len(rows),
            "rows_not_family_parameters": sum(1 for q in rows if q["instance"] is None),
            "warnings": profile["warnings"], "errors": errors}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("inputs", nargs="+", help=".rfa files or directories of them")
    ap.add_argument("--txt", help="write the shared-parameter TXT here")
    ap.add_argument("--profile", help="write the parameter-profile JSON here")
    ap.add_argument("--json", action="store_true", help="print a summary as JSON")
    ns = ap.parse_args(argv)
    profile, errors = build(ns.inputs)
    if ns.txt:
        with open(ns.txt, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(shared_parameter_txt(profile))
    if ns.profile:
        with open(ns.profile, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(profile, fh, indent=1, sort_keys=True)
    summary = summary_of(profile, errors)
    if ns.json:
        print(json.dumps(summary, indent=1))
    else:
        print(f"{summary['families']} families, {summary['parameters']} shared parameters, "
              f"{summary['conflicts']} conflicts ({summary['variants']} cosmetic variants), "
              f"{summary['duplicate_names']} names on two GUIDs, "
              f"{summary['datatypes_inferred']} datatypes inferred, "
              f"{len(summary['txt_omitted'])} left out of the TXT, "
              f"{summary['rows_not_family_parameters']} of {summary['family_rows']} rows not the "
              f"family's own parameters, {len(errors)} unreadable")
        for line in summary["txt_omitted"]:
            print("  not in TXT (no known DATATYPE):", line)
        for w in summary["warnings"]:
            print("  warning:", w)
        for e in errors:
            print("  unreadable:", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
