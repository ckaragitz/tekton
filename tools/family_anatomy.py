"""family_anatomy -- profile a family's anatomy, content-free, and report
where one family falls short of another (issue #837, steer #836).

WHY THIS EXISTS.  The owner's highly complex reference families set the bar
for generation (S-2026-09-23-b).  "Our families are less detailed" is not a
backlog item; "4 of 5 references carry >= 20 labelled dimensions and ours
carry 0" is.  ``famdiff.py`` diffs two families field by field, which finds
format LAWS; this profiles a WHOLE family into counts, so the gap between a
reference and ours can be ranked and filed one issue at a time.

CONTENT-FREE BY CONSTRUCTION.  A profile holds counts and kinds only -- no
parameter names, no string values, no coordinates, no element ids, no GUIDs.
Its keys come from this module's own vocabulary plus two schema identifiers
(a ParamDef class name, a parameter-group type id), never from the file's
text.  A profile is a fact ABOUT a family, never a copy of it (hard rule 3),
which is what lets the aggregate numbers of a third-party reference family
appear in a record.  The reference families themselves stay in
``samples/reference-families/`` (git-ignored; the repo is public, rule 6) and
are never read by a generation flow (S-2026-08-10-c).

EACH ASPECT SAYS HOW IT WAS READ:
  ``decoded``          -- read from the element's own fields
  ``class-count``      -- counted by class; what the class means is known,
                          finer detail is not decoded yet
  ``not-yet-readable`` -- we know it exists and cannot read it yet (e.g. a
                          Yes/No parameter bound to a form's visibility, #690)
Nothing is guessed: a record that fails to decode is counted under
``undecoded``, never skipped silently.

USAGE
    python tools/family_anatomy.py profile X.rfa [--json out.json]
    python tools/family_anatomy.py compare REFERENCE.rfa OURS.rfa [--json out.json]

Read-only: it never writes to the inputs.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC = os.path.join(ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

#: form classes: every one of them is a GenSweep (m_cutting = void,
#: m_famElemVisibility = the detail-level / view flags, m_categoryId = the
#: subcategory, m_materialId = the material)
FORM_CLASSES = {
    "ExtrusionElem": "extrusion",
    "BlendElem": "blend",
    "SweptBlendElem": "swept_blend",
    "RevolutionElem": "revolve",
    "GenSweep": "sweep",
}

#: counted by class; meaning known, finer detail not decoded yet
COUNTED = {
    "FamilyInstance": "nested_instances",
    "ConnectorElem": "connectors",
    "MaterialElem": "materials",
    "TextNote": "text_notes",
    "CurveElem": "curves",
    "BaseArray": "arrays",
    "RadialArray": "radial_arrays",
    "Opening": "openings",
    "ParamElemExternal": "shared_parameters",
    "DBViewPlan": "plan_views",
    "DBViewSection": "elevation_views",
    "DBView3d": "views_3d",
}

NOT_YET_READABLE = {
    "visibility_parameter_bindings": "a Yes/No parameter bound to a form's "
                                     "visibility is not decoded yet (#690)",
}


def _group_key(type_id: str) -> str:
    """'autodesk.parameter.group:dimensions-1.0.0' -> 'dimensions' -- a schema
    identifier, never the family's own text."""
    t = str(type_id or "")
    t = t.split(":", 1)[-1] if ":" in t else t
    return t.rsplit("-", 1)[0] if "-" in t else (t or "none")


def profile(path: str) -> dict:
    """The anatomy of one family: counts and kinds only (see module doc)."""
    from rvt.families import FamilyIndex

    fi = FamilyIndex(path)
    by_class = collections.defaultdict(list)
    for eid, r in fi.unit_records(0).get(102, {}).items():
        by_class[fi.class_name(r.class_id)].append(int(eid))
    undecoded = collections.Counter()

    def val(eid: int, cls: str) -> dict:
        try:
            v = fi.value(0, eid, 102)
        except Exception:                                  # noqa: BLE001 -- counted, not hidden
            v = None
        if not isinstance(v, dict):
            undecoded[cls] += 1
            return {}
        return v

    # --- forms -----------------------------------------------------------
    forms = collections.Counter()
    solids = voids = with_subcat = with_material = 0
    vis_flags = collections.Counter()
    for cls, kind in FORM_CLASSES.items():
        for eid in by_class.get(cls, []):
            v = val(eid, cls)
            if not v:
                continue
            forms[kind] += 1
            if v.get("m_cutting"):
                voids += 1
            else:
                solids += 1
            if isinstance(v.get("m_categoryId"), int) and v["m_categoryId"] != -1:
                with_subcat += 1
            if isinstance(v.get("m_materialId"), int) and v["m_materialId"] != -1:
                with_material += 1
            flags = (v.get("m_famElemVisibility") or {}).get("m_flags")
            if isinstance(flags, int):
                vis_flags[flags] += 1

    # --- the family record: types, formulas, dimension constraints -------
    fam_cat = None
    types = formulas = reporting = 0
    labelled = fixed_refs = driven_segs = 0
    families = by_class.get("Family", [])
    for eid in families[:1]:
        v = val(eid, "Family")
        fam_cat = v.get("m_categoryId")
        tt = ((v.get("m_pFamilyTypes") or {}).get("value") or {}).get("m_pairs") or []
        types = len(tt)
        params = ((v.get("m_familyParams") or {}).get("value") or {}).get("m_params") or []
        formulas = sum(1 for p in params if isinstance(p, dict) and p.get("m_oExpression"))
        reporting = sum(1 for p in params if isinstance(p, dict) and p.get("m_reporting"))
        dc = ((v.get("m_oFamDimConstrMgr") or {}).get("value") or {})
        labelled = len(dc.get("m_paramExprs") or [])
        fixed_refs = len(dc.get("m_fixedRefs") or [])
        driven_segs = len(dc.get("m_drivenDimSegs") or [])

    # --- parameters -------------------------------------------------------
    p_total = p_inst = 0
    p_storage = collections.Counter()
    p_group = collections.Counter()
    for eid in by_class.get("ParamElemFamily", []):
        v = val(eid, "ParamElemFamily")
        if not v:
            continue
        p_total += 1
        if v.get("m_instanceParam"):
            p_inst += 1
        pdef = v.get("m_pParamDef") or {}
        p_storage[str(pdef.get("ptr_class") or "unknown")] += 1
        p_group[_group_key(((pdef.get("value") or {}).get("m_groupTypeId") or {}).get("m_typeId"))] += 1

    # --- dimensions, reference planes, subcategories ---------------------
    dims = eq_dims = 0
    for eid in by_class.get("Dimension", []):
        v = val(eid, "Dimension")
        if not v:
            continue
        dims += 1
        if v.get("m_useEqualityFormula"):
            eq_dims += 1
    ref_planes = named_planes = origin_planes = 0
    for eid in by_class.get("RefPlane", []):
        v = val(eid, "RefPlane")
        if not v:
            continue
        ref_planes += 1
        if v.get("m_refName"):
            named_planes += 1
        if v.get("m_definesOrigin"):
            origin_planes += 1
    subcats = 0
    for eid in by_class.get("CategoryElem", []):
        v = val(eid, "CategoryElem")
        cat = ((v.get("m_pCategory") or {}).get("value") or {})
        if fam_cat is not None and cat.get("m_parentCategoryId") == fam_cat:
            subcats += 1

    def aspect(value, how="decoded"):
        return {"value": value, "how": how}

    prof = {
        "forms": aspect({"by_kind": dict(sorted(forms.items())), "total": sum(forms.values()),
                         "solids": solids, "voids": voids}),
        "form_visibility": aspect({"distinct_settings": len(vis_flags),
                                   "forms_off_the_common_setting":
                                       sum(vis_flags.values()) - max(vis_flags.values(), default=0)}),
        "form_subcategories": aspect({"forms_assigned": with_subcat, "subcategories": subcats}),
        "form_materials": aspect({"forms_assigned": with_material}),
        "reference_planes": aspect({"total": ref_planes, "named": named_planes,
                                    "define_origin": origin_planes}),
        "dimensions": aspect({"total": dims, "equality": eq_dims, "labelled": labelled,
                              "driven_segments": driven_segs, "locked_refs": fixed_refs}),
        "parameters": aspect({"total": p_total, "instance": p_inst, "type": p_total - p_inst,
                              "by_storage": dict(sorted(p_storage.items())),
                              "by_group": dict(sorted(p_group.items())),
                              "formulas": formulas, "reporting": reporting}),
        "types": aspect({"total": types}),
    }
    for cls, key in COUNTED.items():
        prof[key] = aspect({"total": len(by_class.get(cls, []))}, "class-count")
    prof["nested_families"] = aspect({"total": max(0, len(families) - 1)}, "class-count")
    for key, why in NOT_YET_READABLE.items():
        prof[key] = {"value": None, "how": "not-yet-readable", "why": why}
    prof["undecoded"] = {"value": dict(sorted(undecoded.items())), "how": "decoded"}
    return prof


def _leaves(prefix: str, v):
    if isinstance(v, dict):
        for k, x in v.items():
            yield from _leaves(f"{prefix}.{k}" if prefix else k, x)
    elif isinstance(v, (int, float)) and not isinstance(v, bool):
        yield prefix, v


def compare(ref: dict, ours: dict) -> list:
    """Every numeric leaf where the reference has MORE than ours, ranked:
    a feature ours lacks entirely first (reference > 0, ours == 0), then by
    the size of the gap relative to the reference."""
    rows = []
    for aspect_name, a in ref.items():
        if aspect_name == "undecoded" or a.get("how") == "not-yet-readable":
            continue
        rv = dict(_leaves("", a.get("value")))
        ov = dict(_leaves("", (ours.get(aspect_name) or {}).get("value")))
        for k, r in rv.items():
            o = ov.get(k, 0)
            if r > o:
                rows.append({"aspect": aspect_name, "measure": k, "reference": r, "ours": o,
                             "missing": o == 0, "how": a.get("how")})
    rows.sort(key=lambda x: (not x["missing"], -(x["reference"] - x["ours"]) / max(x["reference"], 1),
                             x["aspect"], x["measure"]))
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Profile a family's anatomy (content-free) "
                                             "and report where one falls short of another.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("profile", help="the anatomy of one family")
    p.add_argument("path")
    p.add_argument("--json", dest="json_out")
    c = sub.add_parser("compare", help="where OURS falls short of REFERENCE")
    c.add_argument("reference")
    c.add_argument("ours")
    c.add_argument("--json", dest="json_out")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "profile":
            out = {"profile": profile(a.path)}
            for name, asp in out["profile"].items():
                print(f"  {name:32s} {asp['how']:17s} {json.dumps(asp['value'])}")
        else:
            ref, ours = profile(a.reference), profile(a.ours)
            gaps = compare(ref, ours)
            out = {"reference": ref, "ours": ours, "gaps": gaps}
            print(f"=== {len(gaps)} measure(s) where ours falls short "
                  f"({sum(g['missing'] for g in gaps)} missing entirely)")
            for g in gaps:
                tag = "MISSING" if g["missing"] else "short  "
                print(f"  {tag} {g['aspect']}.{g['measure']}: reference {g['reference']}, ours {g['ours']}")
    except (OSError, ValueError) as e:
        print(f"family_anatomy: cannot read the family: {e}", file=sys.stderr)
        return 1
    if a.json_out:
        with open(a.json_out, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
