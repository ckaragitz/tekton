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
  ``decoded``          -- read from fields whose meaning is established (a
                          form's void flag, a parameter's spec id, the type
                          table ...)
  ``inferred``         -- read from a field whose MEANING is inferred from
                          its name or from our own writer, and not yet
                          confirmed against a Revit-born family (e.g. the
                          dimension constraint lists)
  ``class-count``      -- counted by EXACT class (not its subclasses); finer
                          detail not decoded yet
  ``not-yet-readable`` -- we know it exists and cannot read it yet (e.g. a
                          Yes/No parameter bound to a form's visibility, #690)
A record the decoder reports errors for, or cannot consume cleanly, is
counted under ``undecoded`` by class and left out of every other count --
and ``compare`` says so when either side has any.

A PROJECT IS REFUSED.  A family document's own Family element has a nil
``m_famDocGUID``; every Family loaded into a project carries a real one.  A
file with no such element is not a family and ``profile`` exits 1 rather
than profiling whichever loaded family happens to come first.

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
import re
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
    "SweepElem": "sweep",
}

#: RefPlane.m_refName is the "Is Reference" setting, an enum (famgen/skeleton
#: PLANE_REF: left=0 ... not_a_reference=12, strong=13, weak=14) -- NOT a name.
#: The plane's name is DatumPlane.m_text.
NOT_A_REFERENCE, STRONG_REFERENCE, WEAK_REFERENCE = 12, 13, 14
#: ... skeleton.REF_NAME marks the VALUES verified and the NAMES inferred for
#: codes no named specimen plane backs, so everything read from this enum is
#: reported ``inferred`` (#842 round 3).  ``other_reference`` = every code
#: but 12/13/14: the named settings Left ... Top (0-8) and the unmapped 9-11.

#: Dimension is an abstract base -- no record carries it (#842 round 3: the
#: reader looked for it and read 0 on every family).  Its concrete classes,
#: found by schema inheritance: real dimensions by kind, alignments (the
#: padlocks) apart; any other Dimension subclass counts as "other".
DIMENSION_KINDS = {
    "LinearDimString": "linear",
    "AngularDim": "angular",
    "RadialDim": "radial",
    "ArcLengthDim": "arc_length",
    "SpotElevation": "spot_elevation",
}
ALIGNMENT_CLASSES = ("Alignment", "ArcAlignment")

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
    "DBViewPlan": "plan_views",
    "DBViewSection": "elevation_views",
    "DBView3d": "views_3d",
}

NOT_YET_READABLE = {
    "visibility_parameter_bindings": "a Yes/No parameter bound to a form's "
                                     "visibility is not decoded yet (#690)",
    "connectors_by_domain": "a connector's domain (electrical, duct, pipe, "
                            "cable tray) is not decoded yet; connectors are "
                            "only counted",
    "shared_nested_families": "whether a nested family is shared is not "
                              "decoded yet; nested families are only counted",
    "material_parameters": "a parameter bound to a form's material is not "
                           "decoded yet; forms with a fixed material are "
                           "counted",
    "symbolic_vs_model_lines": "symbolic lines are not told apart from model "
                               "and sketch curves yet; curves are only counted",
    "view_specific_elements": "m_ownerDBViewId is set on the views' own sketch "
                              "planes and extents too, so detail/annotation "
                              "content cannot be told apart yet (#842 round 2)",
}


class NotAFamily(ValueError):
    """The file has no self Family element (a project, or not a Revit file)."""


def _nil_guid(g) -> bool:
    return not g or not str(g).replace("0", "").replace("-", "")


#: a schema identifier: 'autodesk.parameter.group:dimensions-1.0.0',
#: 'autodesk.spec.aec:length-2.0.0', 'autodesk.spec:spec.string-2.0.0'.  Only
#: such an id yields a key (its last token); anything else is 'other', so no
#: text the family chose can ever become a key (#842 round 2: a bare word
#: like "Voltage" passed the old sanitiser).
_SCHEMA_ID = re.compile(r"^autodesk\.[A-Za-z0-9_.]+:(?:[A-Za-z0-9_]+\.)*([A-Za-z0-9_]+)-\d+(?:\.\d+)*$")


def _group_key(type_id) -> str:
    """'autodesk.parameter.group:dimensions-1.0.0' -> 'dimensions',
    'autodesk.spec:spec.string-2.0.0' -> 'string'; empty -> 'none'; any
    other text -> 'other'."""
    t = str(type_id or "")
    if not t:
        return "none"
    m = _SCHEMA_ID.match(t)
    return m.group(1) if m else "other"


#: every key a profile may contain besides schema-derived ones (a parameter
#: group / spec token from a schema id, a ParamDef class name, an undecoded
#: record's class name) -- the content-free test checks keys against it
VOCABULARY = frozenset({
    "value", "how", "why",
    "forms", "form_visibility", "form_subcategories", "form_materials", "reference_planes",
    "dimensions", "dimension_constraints", "parameters", "types", "nested_families", "undecoded",
    "by_kind", "total", "solids", "voids", "distinct_settings", "forms_off_the_common_setting",
    "forms_assigned", "subcategories", "named", "define_origin", "is_reference", "strong", "weak",
    "reference_strength", "other_reference", "alignments", "labelled", "unlabelled",
    "local", "shared", "other_kind", "instance_or_type_unread",
    "eq_display_option", "param_driven_segments", "driven_segments", "anchored_refs",
    "instance", "type", "by_storage", "by_group", "by_spec", "formulas", "reporting",
    "other", "none",
}) | frozenset(FORM_CLASSES.values()) | frozenset(DIMENSION_KINDS.values()) \
  | frozenset(COUNTED.values()) | frozenset(NOT_YET_READABLE)


def profile(path: str) -> dict:
    """The anatomy of one family: counts and kinds only (see module doc)."""
    from rvt.families import FamilyIndex

    fi = FamilyIndex(path)
    by_class = collections.defaultdict(list)
    for eid, r in fi.unit_records(0).get(102, {}).items():
        by_class[fi.class_name(r.class_id)].append(int(eid))
    undecoded = collections.Counter()
    cache = {}
    chains = {}

    def descends(cls: str, base: str) -> bool:
        """``cls`` is ``base`` or inherits from it, by the file's own schema."""
        if cls not in chains:
            chain, c = [], fi.schema.by_name.get(cls)
            while c is not None and len(chain) < 64:
                chain.append(c.name)
                c = fi.schema.by_name.get(c.parent) if c.parent else None
            chains[cls] = chain or [cls]
        return base in chains[cls]

    def val(eid: int, cls: str) -> dict:
        """The decoded record, or {} -- and then it is COUNTED: the decoder
        reports failure through ``errors`` / ``clean``, it does not raise."""
        if eid in cache:
            return cache[eid]
        try:
            o = fi.decode(0, eid, 102)
        except Exception:                                  # noqa: BLE001 -- counted, not hidden
            o = None
        ok = o is not None and not o.errors and o.clean and isinstance(o.value, dict)
        if not ok:
            undecoded[cls] += 1
        cache[eid] = o.value if ok else {}
        return cache[eid]

    # --- the family's OWN Family element (nil m_famDocGUID) ---------------
    # a Family record that did not decode is NOT evidence of a self family
    # (#842 round 2: an undecodable record read as a nil GUID)
    selves = [e for e in by_class.get("Family", [])
              if "m_famDocGUID" in val(e, "Family") and _nil_guid(val(e, "Family")["m_famDocGUID"])]
    if not selves:
        if undecoded.get("Family"):
            # a Family record the decoder could not read is not proof of a
            # project -- say what happened (#842 round 4)
            raise NotAFamily(f"{undecoded['Family']} Family element(s) could not be decoded; "
                             "no self Family element was read")
        raise NotAFamily("no self Family element (a project file, or not a family)")
    if len(selves) > 1:
        # never guess which one is "the" family (#842 round 3: a tie-break
        # nothing exercised); refused, visibly, until a real file shows it
        raise NotAFamily(f"{len(selves)} self Family elements (nil m_famDocGUID); "
                         "which one is the family is ambiguous")
    fam = val(selves[0], "Family")

    # --- forms -----------------------------------------------------------
    forms = collections.Counter()
    solids = voids = with_subcat = with_material = 0
    vis_flags = collections.Counter()
    # every GenSweep subclass the file carries, by inheritance: a concrete
    # class the table does not name (FormElem, FreeFormElement ...) is
    # "other", never dropped
    for cls in sorted(c for c in by_class if descends(c, "GenSweep")):
        kind = FORM_CLASSES.get(cls, "other")
        for eid in by_class[cls]:
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

    # --- the self family: types, formulas, dimension constraints ---------
    fam_cat = fam.get("m_categoryId")
    types = len(((fam.get("m_pFamilyTypes") or {}).get("value") or {}).get("m_pairs") or [])
    params = ((fam.get("m_familyParams") or {}).get("value") or {}).get("m_params") or []
    formulas = sum(1 for q in params if isinstance(q, dict) and q.get("m_oExpression"))
    reporting = sum(1 for q in params if isinstance(q, dict) and q.get("m_reporting"))
    dc = ((fam.get("m_oFamDimConstrMgr") or {}).get("value") or {})
    param_driven_segments = len(dc.get("m_paramExprs") or [])
    anchored_refs = len(dc.get("m_fixedRefs") or [])
    driven_segments = len(dc.get("m_drivenDimSegs") or [])

    # --- parameters -------------------------------------------------------
    # Every ParamElem subclass the file carries, by inheritance -- a SHARED
    # family parameter is a ParamElemExternal, not a ParamElemFamily (#842
    # round 4: a family with shared parameters read 10 of its 21) -- and only
    # those the family's OWN m_familyParams lists: a nested or loaded family's
    # parameters sit in the same unit (a project read 100 for a family of 19).
    listed = {q.get("m_paramId") for q in params if isinstance(q, dict)}
    p_total = p_inst = p_local = p_shared = p_other_kind = 0
    p_storage, p_group, p_spec = collections.Counter(), collections.Counter(), collections.Counter()
    for cls in sorted(c for c in by_class if descends(c, "ParamElem")):
        for eid in by_class[cls]:
            if eid not in listed:
                continue
            v = val(eid, cls)
            if not v:
                continue
            p_total += 1
            if cls == "ParamElemFamily":
                p_local += 1
                # instance vs type is read from the local parameter's own
                # flag; a shared one carries none, so it is left unread
                # (the family table's m_instance disagrees with this flag on
                # one of our own panelboard's parameters -- not a substitute)
                if v.get("m_instanceParam"):
                    p_inst += 1
            elif cls == "ParamElemExternal":
                p_shared += 1
            else:
                p_other_kind += 1
            pdef = v.get("m_pParamDef") or {}
            cls_name = str(pdef.get("ptr_class") or "")
            p_storage[cls_name if cls_name.startswith("ParamDef") and cls_name in fi.schema.by_name
                      else "other"] += 1
            body = pdef.get("value") or {}
            p_group[_group_key((body.get("m_groupTypeId") or {}).get("m_typeId"))] += 1
            spec = (body.get("m_specTypeId") or {}).get("m_typeId")
            p_spec[_group_key(spec) if spec else "none"] += 1

    # --- dimensions, reference planes, subcategories ---------------------
    dim_kinds = collections.Counter()
    alignments = labelled = eq_option = 0
    for cls in sorted(c for c in by_class if descends(c, "Dimension")):
        for eid in by_class[cls]:
            v = val(eid, cls)
            if not v:
                continue
            if cls in ALIGNMENT_CLASSES:
                alignments += 1
                continue
            dim_kinds[DIMENSION_KINDS.get(cls, "other")] += 1
            # a segment naming a parameter element: how our writer labels a
            # dimension (param_drive.new_labeled_dim) -- inferred for Revit-born
            if any(isinstance(g, dict) and isinstance(g.get("m_paramId"), int)
                   and g["m_paramId"] > 0 for g in v.get("m_ArrSegInfo") or []):
                labelled += 1
            if v.get("m_useEqualityFormula"):
                eq_option += 1
    dims = sum(dim_kinds.values())
    ref_planes = named_planes = origin_planes = is_ref = strong = weak = 0
    for eid in by_class.get("RefPlane", []):
        v = val(eid, "RefPlane")
        if not v:
            continue
        ref_planes += 1
        if isinstance(v.get("m_text"), str) and v["m_text"].strip():
            named_planes += 1
        if v.get("m_definesOrigin"):
            origin_planes += 1
        rn = v.get("m_refName")
        if isinstance(rn, int) and rn != NOT_A_REFERENCE:
            is_ref += 1
            strong += rn == STRONG_REFERENCE
            weak += rn == WEAK_REFERENCE
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
        "reference_strength": aspect({"is_reference": is_ref, "strong": strong, "weak": weak,
                                      "other_reference": is_ref - strong - weak}, "inferred"),
        "dimensions": aspect({"total": dims, "by_kind": dict(sorted(dim_kinds.items())),
                              "alignments": alignments}),
        "dimension_constraints": aspect({"labelled": labelled, "unlabelled": dims - labelled,
                                         "eq_display_option": eq_option,
                                         "param_driven_segments": param_driven_segments,
                                         "driven_segments": driven_segments,
                                         "anchored_refs": anchored_refs}, "inferred"),
        "parameters": aspect({"total": p_total, "local": p_local, "shared": p_shared,
                              "other_kind": p_other_kind,
                              "instance": p_inst, "type": p_local - p_inst,
                              "instance_or_type_unread": p_total - p_local,
                              "by_storage": dict(sorted(p_storage.items())),
                              "by_group": dict(sorted(p_group.items())),
                              "by_spec": dict(sorted(p_spec.items())),
                              "formulas": formulas, "reporting": reporting}),
        "types": aspect({"total": types}),
    }
    for cls, key in COUNTED.items():
        prof[key] = aspect({"total": len(by_class.get(cls, []))}, "class-count")
    prof["nested_families"] = aspect({"total": max(0, len(by_class.get("Family", [])) - 1)},
                                     "class-count")
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
            warn = {side: p["undecoded"]["value"] for side, p in (("reference", ref), ("ours", ours))
                    if p["undecoded"]["value"]}
            out = {"reference": ref, "ours": ours, "gaps": gaps, "undecoded_warning": warn}
            for side, cls in warn.items():
                print(f"  WARNING: {side} has records that did not decode ({cls}); "
                      f"its counts are incomplete")
            print(f"=== {len(gaps)} measure(s) where ours falls short "
                  f"({sum(g['missing'] for g in gaps)} missing entirely)")
            for g in gaps:
                tag = "MISSING" if g["missing"] else "short  "
                print(f"  {tag} {g['aspect']}.{g['measure']}: reference {g['reference']}, ours {g['ours']}")
    except Exception as e:                                 # noqa: BLE001 -- one line, never a traceback
        print(f"family_anatomy: cannot profile the family: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    if a.json_out:
        with open(a.json_out, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
