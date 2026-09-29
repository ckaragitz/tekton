"""shared_params_from_rfa -- a USER'S shared-parameter library, read from their own families.

Every shared parameter a family carries (``ParamElemExternal``: the GUID a project
schedule or tag binds by, its name, its definition class and spec) is collected
from the ``.rfa`` files given, across releases (each file is read inside its OWN
release, ``rvt.global_framing.enter_own_release``), and written as:

* a Revit shared-parameter TXT (the documented tab-separated grammar Revit itself
  reads: ``*META`` / ``*GROUP`` / ``*PARAM``), GUIDs copied verbatim; and
* a PARAMETER PROFILE JSON: for every source family, which of those parameters it
  carries, instance or type, and in which palette group -- what a generated family
  of the same kind applies at build (``make_family --param-profile``, #866).

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

Exit 0 when every file was read; 1 when any file could not be (each named).
Read-only on the inputs.
"""
from __future__ import annotations

import argparse
import glob
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
    "ParamDefTextBrowseEdit": "TEXT",
    "ParamDefNoOfPoles": "NUMBER_OF_POLES",
}

#: measurable spec (version-less) -> DATATYPE token; a spec with no token here is
#: written as its spec id (Revit's newer files do the same) and flagged in the profile
SPEC_DATATYPE = {
    "autodesk.spec:spec.string": "TEXT",           # a ParamDefValue carrying a text/int/bool
    "autodesk.spec:spec.int64": "INTEGER",         # spec (how OUR writer authors them, #165)
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
    "autodesk.spec.aec.electrical:current": "ELECTRICAL_CURRENT",
    "autodesk.spec.aec.electrical:potential": "ELECTRICAL_POTENTIAL",
    "autodesk.spec.aec.electrical:power": "ELECTRICAL_POWER",
    "autodesk.spec.aec.electrical:apparentPower": "ELECTRICAL_APPARENT_POWER",
    "autodesk.spec.aec.electrical:wattage": "ELECTRICAL_WATTAGE",
    "autodesk.spec.aec.electrical:frequency": "ELECTRICAL_FREQUENCY",
    "autodesk.spec.aec.electrical:luminousFlux": "ELECTRICAL_LUMINOUS_FLUX",
    "autodesk.spec.aec.electrical:efficacy": "ELECTRICAL_EFFICACY",
    "autodesk.spec.aec.electrical:colorTemperature": "COLOR_TEMPERATURE",
    "autodesk.spec.aec.electrical:conduitSize": "CONDUIT_SIZE",
    "autodesk.spec.aec.electrical:cableTraySize": "CABLETRAY_SIZE",
    "autodesk.spec.aec.electrical:wireDiameter": "WIRE_SIZE",
    "autodesk.spec.aec.piping:pipeSize": "PIPE_SIZE",
}


def _versionless(spec: Optional[str]) -> str:
    return str(spec or "").rsplit("-", 1)[0]


def datatype_of(def_class: str, spec: Optional[str]) -> Tuple[str, bool]:
    """(DATATYPE token, known).  ``known`` False = written as the spec id."""
    if def_class in DEF_CLASS_DATATYPE:
        return DEF_CLASS_DATATYPE[def_class], True
    tok = SPEC_DATATYPE.get(_versionless(spec))
    if tok:
        return tok, True
    return (str(spec) if spec else "NUMBER"), False


def _files(args: Iterable[str]) -> List[str]:
    out: List[str] = []
    for a in args:
        if os.path.isdir(a):
            out += sorted(glob.glob(os.path.join(a, "*.rfa")))
        else:
            out.append(a)
    return out


def read_family(path: str) -> Dict[str, Any]:
    """Every shared parameter of one family document, with how the family binds it."""
    from rvt import global_framing as GF
    from rvt.families import FamilyIndex
    params: List[Dict[str, Any]] = []
    with ExitStack() as stack:
        GF.enter_own_release(stack, path)
        fi = FamilyIndex(path)
        recs = fi.unit_records(0).get(102, {})
        instance: Dict[int, bool] = {}
        category = None
        for eid, rec in recs.items():
            if fi.class_name(rec.class_id) != "Family":
                continue
            v = fi.value(0, eid) or {}
            if v.get("m_surrogateId") != -1:          # the document's OWN Family element
                continue
            category = v.get("m_categoryId")
            for q in ((v.get("m_familyParams") or {}).get("value") or {}).get("m_params") or []:
                instance[int(q["m_paramId"])] = bool(q.get("m_instance"))
        for eid, rec in recs.items():
            if fi.class_name(rec.class_id) != "ParamElemExternal":
                continue
            v = fi.value(0, eid) or {}
            pd = v.get("m_pParamDef") or {}
            pv = pd.get("value") or {}
            dt, known = datatype_of(pd.get("ptr_class", ""), (pv.get("m_specTypeId") or {}).get("m_typeId"))
            params.append({
                "guid": str(((v.get("m_externalParamKey") or {}).get("m_guidValue")) or ""),
                "name": str(pv.get("m_caption") or ""),
                "def_class": pd.get("ptr_class"),
                "spec": (pv.get("m_specTypeId") or {}).get("m_typeId"),
                "datatype": dt, "datatype_known": known,
                "palette_group": (pv.get("m_groupTypeId") or {}).get("m_typeId") or "",
                "instance": instance.get(int(eid)),
                "description": str(v.get("m_description") or ""),
                "visible": bool(pv.get("m_userVisible", True)),
                "user_modifiable": bool(v.get("m_userModifiable", True)),
                "hide_when_no_value": bool(v.get("m_hideWhenNoValue", False)),
            })
    return {"category": category, "params": sorted(params, key=lambda p: p["name"])}


def build(paths: Iterable[str]) -> Tuple[Dict[str, Any], List[str]]:
    """(profile, errors).  The profile's ``parameters`` is keyed by GUID; a GUID seen
    with two names or two datatypes is kept once and listed in ``conflicts``."""
    families: Dict[str, Any] = {}
    parameters: Dict[str, Dict[str, Any]] = {}
    conflicts: List[Dict[str, Any]] = []
    errors: List[str] = []
    for p in _files(paths):
        stem = os.path.splitext(os.path.basename(p))[0]
        try:
            fam = read_family(p)
        except Exception as exc:                                   # noqa: BLE001 -- named, not hidden
            errors.append(f"{p}: {type(exc).__name__}: {exc}")
            continue
        families[stem] = {"category": fam["category"],
                          "params": [{"guid": q["guid"], "name": q["name"],
                                      "instance": q["instance"],
                                      "palette_group": q["palette_group"]} for q in fam["params"]]}
        for q in fam["params"]:
            if not q["guid"]:
                continue
            key = {k: q[k] for k in ("name", "def_class", "spec", "datatype", "datatype_known",
                                     "description", "visible", "user_modifiable",
                                     "hide_when_no_value")}
            seen = parameters.get(q["guid"])
            if seen is None:
                parameters[q["guid"]] = dict(key, used_by=1)
            else:
                seen["used_by"] += 1
                if (seen["name"], seen["datatype"]) != (key["name"], key["datatype"]):
                    conflicts.append({"guid": q["guid"], "kept": [seen["name"], seen["datatype"]],
                                      "also": [key["name"], key["datatype"]], "family": stem})
    return {"schema": "tekton.param-profile/1", "families": families,
            "parameters": parameters, "conflicts": conflicts}, errors


def shared_parameter_txt(profile: Dict[str, Any]) -> str:
    """The profile's parameters as a Revit shared-parameter file.  File GROUPs are the
    name prefix before the first '_' (a file grouping only; the palette group a
    family binds each parameter in is in the profile)."""
    params = sorted(profile["parameters"].items(), key=lambda kv: kv[1]["name"])
    group_names: List[str] = []
    for _g, p in params:
        g = p["name"].split("_", 1)[0] if "_" in p["name"] else "General"
        if g not in group_names:
            group_names.append(g)
    gid = {g: i + 1 for i, g in enumerate(group_names)}
    lines = ["# This is a Revit shared parameter file.",
             "# Do not edit manually.",
             "*META\tVERSION\tMINVERSION", "META\t2\t1",
             "*GROUP\tID\tNAME"]
    lines += [f"GROUP\t{gid[g]}\t{g}" for g in group_names]
    lines.append("*PARAM\tGUID\tNAME\tDATATYPE\tDATACATEGORY\tGROUP\tVISIBLE\tDESCRIPTION\t"
                 "USERMODIFIABLE\tHIDEWHENNOVALUE")
    for guid, p in params:
        g = p["name"].split("_", 1)[0] if "_" in p["name"] else "General"
        desc = p["description"].replace("\t", " ").replace("\r", " ").replace("\n", " ")
        lines.append("\t".join(["PARAM", guid, p["name"], p["datatype"], "", str(gid[g]),
                                "1" if p["visible"] else "0", desc,
                                "1" if p["user_modifiable"] else "0",
                                "1" if p["hide_when_no_value"] else "0"]))
    return "\n".join(lines) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("inputs", nargs="+", help=".rfa files or directories of them")
    ap.add_argument("--txt", help="write the shared-parameter TXT here")
    ap.add_argument("--profile", help="write the parameter-profile JSON here")
    ap.add_argument("--json", action="store_true", help="print a summary as JSON")
    ns = ap.parse_args(argv)
    profile, errors = build(ns.inputs)
    if ns.txt:
        with open(ns.txt, "w", encoding="utf-8") as fh:
            fh.write(shared_parameter_txt(profile))
    if ns.profile:
        with open(ns.profile, "w", encoding="utf-8") as fh:
            json.dump(profile, fh, indent=1, sort_keys=True)
    summary = {"families": len(profile["families"]), "parameters": len(profile["parameters"]),
               "conflicts": len(profile["conflicts"]),
               "datatypes_unmapped": sum(1 for p in profile["parameters"].values()
                                         if not p["datatype_known"]),
               "errors": errors}
    if ns.json:
        print(json.dumps(summary, indent=1))
    else:
        print(f"{summary['families']} families, {summary['parameters']} shared parameters, "
              f"{summary['conflicts']} conflicts, {summary['datatypes_unmapped']} datatypes "
              f"written as spec ids, {len(errors)} unreadable")
        for e in errors:
            print("  unreadable:", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
