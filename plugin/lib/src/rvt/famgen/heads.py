"""rvt.famgen.heads -- OUR annotation-head family set (the view/tag types a
project's DBViewTypes and datum/annotation attribute types default to).

The twelve head/tag families a minimal Autodesk project keeps (the set the
viewer-FAILED R10b reduction retained; the K3 rung's usage-field targets) --
Section Head + Tail (four variants), Level Head, Grid Head, Callout Head,
Elevation Mark Body + two Pointers, View Title, Boundary Condition -- built
FROM SCRATCH as OUR family documents (``rvt.famgen.skeleton.FamilyDoc``):
the right built-in ANNOTATION category, our own name, the annotation part
type (-1), the family's user-parameter set (the SAME parameter semantics as
the Autodesk head family it stands in for -- Radius / Width / Height /
Length / Name / Elevation -- with OUR values), one type, the family
skeleton (self-Family, Reference Level, origin reference planes, units, the
1-plan-view constellation), delivered BOTH as a standalone ``.rfa`` and as
an embeddable ``FamilyDoc`` for ``rvt.famload``.

WHAT THEY ARE NOT (the honest gap, carried as the L-proof acceptance
question): they carry NO detail geometry (the circle / line / filled
regions an Autodesk head draws in its plan view are symbolic ``CurveElem``s /
``FilledRegion``s owned by that view) and NO label (a ``TagNote`` bound to a
parameter).  No family stream has constructors for those yet -- the family
skeleton stops at S0 (no geometry), the geometry stream authors SOLID forms
(model sketch curves + extrusions), and the label element has no specimen
reconstruction.  A loaded head therefore names a real, coherent, our-own
family document whose SHAPE regenerates to nothing visible.  Whether the
Autodesk reader requires the annotation content -- versus merely a coherent
loaded family document behind each usage field -- is exactly what the L
ladder in ``experiments/genesis/loader/`` asks the viewer.

The category / parameter facts below are decoded from rstbasic's own head
families (embedded units 5, 6, 13, 17, 20, 23, 25, 26, 34, 35, 44, 52)
[VERIFIED]; every VALUE is ours.

Usage: ``python -m rvt.famgen.heads`` emits the twelve standalone ``.rfa``
files + ``heads_report.json`` under ``experiments/genesis/loader/``.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, List, Optional, Sequence

from . import skeleton as SK
from .skeleton import (FamilyDoc, new_family_document, mm, SPEC_LENGTH,
                       SPEC_TEXT, PGROUP_DIMENSIONS)

_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "..", "..", ".."))
OUT_DIR = os.path.join(_ROOT, "experiments", "genesis", "loader")

# ---------------------------------------------------------------------------
# built-in annotation categories (m_categoryId of the sample's head families)
# ---------------------------------------------------------------------------
OST_SECTION_HEADS = -2000400        #: section heads AND tails (both variants)
OST_LEVEL_HEADS = -2006020
OST_GRID_HEADS = -2006040
OST_CALLOUT_HEADS = -2000538
OST_ELEVATION_MARKS = -2006045
OST_VIEW_TITLES = -2000515
OST_BOUNDARY_CONDITIONS = -2005301

#: the annotation part type: every head family's host + self Family carries
#: m_partType -1 [VERIFIED rstbasic 1388845 + its embedded self-Family]
PART_TYPE_ANNOTATION = -1

#: parameter groups the head families' parameters use [V: the sample's
#: length params carry group '' (none) or 'graphics'; ours use the
#: dimensions / graphics groups]
PGROUP_GRAPHICS = "autodesk.parameter.group:graphics-1.0.0"

CATEGORY_LABEL = {
    OST_SECTION_HEADS: "Section Marks", OST_LEVEL_HEADS: "Level Heads",
    OST_GRID_HEADS: "Grid Heads", OST_CALLOUT_HEADS: "Callout Heads",
    OST_ELEVATION_MARKS: "Elevation Marks", OST_VIEW_TITLES: "View Titles",
    OST_BOUNDARY_CONDITIONS: "Boundary Conditions",
}


# ---------------------------------------------------------------------------
# the twelve head specifications
# ---------------------------------------------------------------------------

@dataclass
class HeadSpec:
    """One annotation-head family of OUR set."""
    key: str
    name: str                        # OUR family name
    type_name: str                   # OUR symbol/type name
    category: int
    role: str                        # which usage field references it
    stands_in_for: str               # the Autodesk family it replaces (K1/rstbasic)
    params: List[dict] = dc_field(default_factory=list)   # {name, spec, value, group}
    notes: List[str] = dc_field(default_factory=list)


def _len(name: str, mm_value: float, group: str = PGROUP_DIMENSIONS) -> dict:
    return {"name": name, "spec": SPEC_LENGTH, "value": mm(mm_value), "group": group}


def _txt(name: str, value: str, group: str = PGROUP_GRAPHICS) -> dict:
    return {"name": name, "spec": SPEC_TEXT, "value": str(value), "group": group}


HEAD_SPECS: Dict[str, HeadSpec] = {}


def _reg(spec: HeadSpec) -> None:
    HEAD_SPECS[spec.key] = spec


# section heads / tails (four variants) -----------------------------------
_reg(HeadSpec(
    key="section_head_open", name="RW Section Head - Open",
    type_name="Section Head - Open", category=OST_SECTION_HEADS,
    role="SectionAttributes.m_sectionHeadFamilyTagId",
    stands_in_for="M_Section Head - No Arrow (rstbasic unit 17)",
    params=[_len("Radius", 6.0)],
    notes=["Autodesk's carries NO user parameters (its labels bind the built-in "
           "detail-number / sheet-number tokens); OURS carries our head radius"]))
_reg(HeadSpec(
    key="section_head_filled", name="RW Section Head - Filled",
    type_name="Section Head - Filled", category=OST_SECTION_HEADS,
    role="SectionAttributes.m_sectionHeadFamilyTagId",
    stands_in_for="M_Section Head - Filled (rstbasic unit 35)",
    params=[_len("Radius", 6.0)]))
_reg(HeadSpec(
    key="section_tail_filled", name="RW Section Tail - Filled",
    type_name="Section Tail - Filled", category=OST_SECTION_HEADS,
    role="SectionAttributes.m_sectionTailFamilyTagId",
    stands_in_for="M_Section Tail - Filled (rstbasic unit 44)",
    params=[_len("Width", 3.0), _len("Height", 6.0)],
    notes=["parameter set = the sample's (Width, Height), our values"]))
_reg(HeadSpec(
    key="section_tail_horizontal", name="RW Section Tail - Horizontal",
    type_name="Section Tail - Horizontal", category=OST_SECTION_HEADS,
    role="SectionAttributes.m_sectionTailFamilyTagId",
    stands_in_for="M_Section Tail - Filled Horizontal (rstbasic unit 5)",
    params=[_len("Width", 6.0), _len("Height", 3.0)]))
# level / grid heads --------------------------------------------------------
_reg(HeadSpec(
    key="level_head", name="RW Level Head - Circle",
    type_name="Level Head - Circle", category=OST_LEVEL_HEADS,
    role="LevelAttributes.m_familyTagId",
    stands_in_for="M_Level Head - Circle1 (rstbasic unit 34)",
    params=[_txt("Name", "Level"), _txt("Elevation", ""), _len("Radius", 4.0)],
    notes=["parameter set = the sample's (Name, Elevation, Radius): the two "
           "text params are ParamDefValue with the string spec in OUR "
           "skeleton (the sample uses the ParamDefString class)"]))
_reg(HeadSpec(
    key="grid_head", name="RW Grid Head - Circle",
    type_name="Grid Head - Circle", category=OST_GRID_HEADS,
    role="GridAttributes.m_familyTagId",
    stands_in_for="M_Grid Head - Circle1 (rstbasic unit 23)",
    params=[_len("Radius", 6.5), _txt("Name", "Grid")]))
# callout head ------------------------------------------------------------------
_reg(HeadSpec(
    key="callout_head", name="RW Callout Head",
    type_name="Callout Head", category=OST_CALLOUT_HEADS,
    role="CalloutTag.m_familyTagId",
    stands_in_for="M_Callout Head1 (rstbasic unit 6)",
    params=[_len("Radius", 6.0)],
    notes=["Autodesk's carries no user parameters (built-in reference labels)"]))
# elevation marks ------------------------------------------------------------
_reg(HeadSpec(
    key="elevation_body", name="RW Elevation Mark Body",
    type_name="Elevation Mark Body", category=OST_ELEVATION_MARKS,
    role="InteriorElevAttributes.m_elevationSymbolId (the mark body)",
    stands_in_for="M_Elevation Mark Body_Circle-12mm1 (rstbasic unit 20)",
    params=[_len("Radius", 6.0)],
    notes=["the sample's parameters are Yes/No + a FamType (Filled / View Name / "
           "Ref / Arrow Type) driving nested pointer families; OURS is the body "
           "circle only (no nested families)"]))
_reg(HeadSpec(
    key="elevation_pointer_1", name="RW Elevation Mark Pointer",
    type_name="Filled Arrow", category=OST_ELEVATION_MARKS,
    role="the elevation mark body's nested pointer family (unreferenced by the host)",
    stands_in_for="M_Elevation Mark Pointer_Circle-12mm (rstbasic unit 13)",
    params=[_len("Radius", 6.0)]))
_reg(HeadSpec(
    key="elevation_pointer_2", name="RW Elevation Mark Pointer 2",
    type_name="Detail Number", category=OST_ELEVATION_MARKS,
    role="the elevation mark body's nested pointer family (unreferenced by the host)",
    stands_in_for="M_Elevation Mark Pointer_Circle-12mm1 (rstbasic unit 52)",
    params=[_len("Radius", 6.0)]))
# view title -----------------------------------------------------------------
_reg(HeadSpec(
    key="view_title", name="RW View Title",
    type_name="View Title", category=OST_VIEW_TITLES,
    role="ViewportAttributes.m_familyTagId",
    stands_in_for="M_View Title (rstbasic unit 26)",
    params=[_len("Line Length", 25.0)],
    notes=["Autodesk's carries no user parameters (title / scale labels bind "
           "view built-ins); OURS carries our title-line length"]))
# boundary condition ---------------------------------------------------------
_reg(HeadSpec(
    key="boundary_condition", name="RW Boundary Condition - Fixed",
    type_name="Boundary Condition - Fixed", category=OST_BOUNDARY_CONDITIONS,
    role="StructSettingsElem.m_bcFixedFamilyId (a structural annotation family)",
    stands_in_for="M_Boundary Condition-Fixed (rstbasic unit 25)",
    params=[_len("Radius", 3.0), _len("Width", 12.0), _len("Length", 12.0)],
    notes=["parameter set = the sample's (Radius, Width, Length), our values; "
           "the sample nests three symbol families (fixed / pinned / roller), ours "
           "is the single fixed body"]))

assert len(HEAD_SPECS) == 12, len(HEAD_SPECS)

#: the usage repointing a full head set applies to a host (rvt.famload
#: UsageRepoint arguments): referrer class, field, family key
DEFAULT_USAGE_MAP = [
    ("LevelAttributes", "m_familyTagId", "level_head"),
    ("GridAttributes", "m_familyTagId", "grid_head"),
    ("SectionAttributes", "m_sectionHeadFamilyTagId", "section_head_open"),
    ("SectionAttributes", "m_sectionTailFamilyTagId", "section_tail_filled"),
    ("CalloutTag", "m_familyTagId", "callout_head"),
    ("ViewportAttributes", "m_familyTagId", "view_title"),
    ("InteriorElevAttributes", "m_elevationSymbolId", "elevation_body"),
    ("StructSettingsElem", "m_bcFixedFamilyId", "boundary_condition"),
]


# ---------------------------------------------------------------------------
# builders
# ---------------------------------------------------------------------------

def build_head_family(key: str, *, start_id: int = 1000,
                      name_override: Optional[str] = None) -> FamilyDoc:
    """Build OUR head family ``key`` (see :data:`HEAD_SPECS`) as a finalized
    :class:`FamilyDoc` whose element ids start at ``start_id`` (a project load
    passes a block above the host watermark).

    Content: the annotation-family skeleton -- self-Family (category = the
    head's OST category, ``m_partType`` -1), Reference Level + level type,
    the two origin reference planes, the units registry, the 1-plan-view
    constellation, the head's user parameters (dimensions / graphics
    groups) and ONE type carrying our values.  NO detail geometry / label
    (see the module doc -- the honest gap of this rung).
    """
    if key not in HEAD_SPECS:
        raise KeyError(f"unknown head family {key!r}; known: {sorted(HEAD_SPECS)}")
    spec = HEAD_SPECS[key]
    name = name_override or spec.name
    doc = new_family_document(int(spec.category), name, start_id=int(start_id),
                              part_type=PART_TYPE_ANNOTATION, with_views=True,
                              datum_length_ft=2.0, plane_length_ft=1.0)
    doc.notes.append(f"stands in for {spec.stands_in_for}; usage role: {spec.role}")
    doc.notes.append("annotation skeleton only: no detail geometry, no label [H]")
    for n in spec.notes:
        doc.notes.append(n)
    # user parameters (the family's own parameter set) + one type of values
    tvals: Dict[Any, Any] = {}
    for p in spec.params:
        pe = doc.add_family_parameter(p["name"], spec_type_id=p["spec"],
                                      group_type_id=p.get("group") or PGROUP_DIMENSIONS,
                                      default=p["value"])
        tvals[pe.elem_id] = p["value"]
    doc.add_type(spec.type_name, tvals)
    doc.finalize()
    # our-name assertion: never an Autodesk product-family name
    for bad in ("M_", "Autodesk", "Revit"):
        if bad in name:
            raise ValueError(f"head family name {name!r} contains {bad!r}")
    return doc


def family_load(key: str, *, name_override: Optional[str] = None):
    """A ``rvt.famload.FamilyLoad`` for head ``key`` (its builder + the
    core-category binding = the head's own category)."""
    from .. import famload as FL
    spec = HEAD_SPECS[key]
    return FL.FamilyLoad(key=key,
                         builder=(lambda start_id, _k=key, _n=name_override:
                                  build_head_family(_k, start_id=start_id,
                                                    name_override=_n)),
                         core_categories=[spec.category])


def all_family_loads(keys: Optional[Sequence[str]] = None) -> list:
    """FamilyLoad entries for every head (or a subset), in HEAD_SPECS order."""
    ks = list(keys) if keys else list(HEAD_SPECS)
    return [family_load(k) for k in ks]


def default_repoints(keys: Optional[Sequence[str]] = None) -> list:
    """``rvt.famload.UsageRepoint`` list of the DEFAULT usage map, restricted
    to the loaded ``keys`` (a host without a referrer class is a no-op)."""
    from .. import famload as FL
    ks = set(keys) if keys else set(HEAD_SPECS)
    return [FL.UsageRepoint(referrer_class=c, field=f, family_key=k)
            for (c, f, k) in DEFAULT_USAGE_MAP if k in ks]


# ---------------------------------------------------------------------------
# standalone .rfa emission (the family form of each head)
# ---------------------------------------------------------------------------

def emit_head_rfas(out_dir: str = OUT_DIR, *, keys: Optional[Sequence[str]] = None,
                   validate: bool = True) -> Dict[str, Any]:
    """Emit each head family as a standalone ``.rfa`` + a JSON report of
    its skeleton round-trip / read-back / family-mode validation.  Every
    file is 100 % ours (our partition stream + our Globals + our PartAtom +
    real ECC + our container).  Returns the report dict (also written)."""
    os.makedirs(out_dir, exist_ok=True)
    ks = list(keys) if keys else list(HEAD_SPECS)
    rep: Dict[str, Any] = {"out_dir": os.path.relpath(out_dir, _ROOT),
                           "families": {}}
    for key in ks:
        spec = HEAD_SPECS[key]
        doc = build_head_family(key)
        rt = doc.roundtrip()
        path = os.path.join(out_dir, f"head_{key}.rfa")
        entry: Dict[str, Any] = {
            "name": doc.name, "type": spec.type_name, "category": spec.category,
            "category_label": CATEGORY_LABEL.get(spec.category, str(spec.category)),
            "elements": len(doc.elements), "params": [p["name"] for p in spec.params],
            "roundtrip": {"records": rt.get("records"), "ok": rt.get("roundtrip_ok"),
                          "failed": rt.get("failed"), "failures": (rt.get("failures") or [])[:4]},
            "role": spec.role, "stands_in_for": spec.stands_in_for,
            "notes": list(doc.notes),
        }
        try:
            emit = doc.to_rfa(path)
            entry["rfa"] = {"path": os.path.relpath(path, _ROOT),
                            "bytes": (os.path.getsize(path) if os.path.exists(path) else None)}
            if isinstance(emit, dict):
                for k in ("verify", "read_back", "streams"):
                    if k in emit:
                        entry["rfa"][k] = emit[k]
            if validate:
                try:
                    v = SK.validate_family(path)
                    fam = v.get("family_mode") or {}
                    entry["validate_family"] = {
                        "verdict": fam.get("verdict"), "errors": fam.get("n_errors"),
                        "warnings": fam.get("n_warnings"),
                        "elements_decoded": (fam.get("stats") or {}).get("elements_decoded"),
                        "refs_checked": (fam.get("stats") or {}).get("refs_checked")}
                except Exception as ex:                        # pragma: no cover
                    entry["validate_family"] = {"error": repr(ex)}
        except Exception as ex:
            entry["rfa"] = {"error": f"{type(ex).__name__}: {ex}"}
        rep["families"][key] = entry
    with open(os.path.join(out_dir, "heads_report.json"), "w") as fh:
        json.dump(rep, fh, indent=1, default=str)
    return rep


def summary_table(rep: Optional[Dict[str, Any]] = None) -> str:
    """One line per head: elements, params, round-trip, .rfa validation."""
    lines = [f"{'key':26s} {'category':>10s} {'elems':>5s} {'params':>6s} "
             f"{'roundtrip':>10s} {'rfa':>8s} name"]
    for key, spec in HEAD_SPECS.items():
        doc = build_head_family(key)
        rt = doc.roundtrip()
        rr = "-"
        if rep and key in rep.get("families", {}):
            v = rep["families"][key].get("validate_family") or {}
            rr = str(v.get("verdict") or v.get("error") or "-")[:8]
        lines.append(f"{key:26s} {spec.category:>10d} {len(doc.elements):>5d} "
                     f"{len(spec.params):>6d} "
                     f"{rt.get('roundtrip_ok', 0)}/{rt.get('records', 0):<7d} {rr:>8s} {doc.name}")
    return "\n".join(lines)


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m rvt.famgen.heads")
    ap.add_argument("--out", default=OUT_DIR)
    ap.add_argument("--keys", default="", help="comma-separated head keys (default all 12)")
    ap.add_argument("--no-validate", action="store_true")
    a = ap.parse_args(argv)
    keys = [k.strip() for k in a.keys.split(",") if k.strip()] or None
    rep = emit_head_rfas(a.out, keys=keys, validate=not a.no_validate)
    print(summary_table(rep))
    n_ok = sum(1 for e in rep["families"].values()
               if (e.get("validate_family") or {}).get("verdict") == "VALID")
    print(f"\n{len(rep['families'])} head families emitted to {rep['out_dir']} "
          f"({n_ok} validate-clean); report heads_report.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
