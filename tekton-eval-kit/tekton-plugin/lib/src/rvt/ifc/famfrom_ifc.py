"""rvt.ifc.famfrom_ifc -- OUR generated Revit FAMILY from an IFC product's facts.

The pipeline  IFC product  ->  facts (rvt.ifc.product_facts)  ->  OUR family
document  ->  a standalone ``.rfa``  ->  the family LOADED into a certified
project base:

    facts   = product_facts.extract_product_facts(ifc)            # measured
    product = make_downlight(facts=facts)                          # composed
    product.write_rfa("experiments/families/ifc/chicago_plenum_downlight.rfa")
    load_into_project(host_rvt, "experiments/families/ifc/L_downlight_loaded.rvt",
                      builder=lambda start_id: make_downlight(...).doc)

THE ARCHETYPE.  ``rvt.famgen.factory.make_luminaire`` is the LUMINAIRE
archetype; its recessed-troffer form is what has been exercised (a
rectangular housing).  This module is the RECESSED-CAN variant the factory
does not carry: the housing is COMPOSED from ``rvt.famgen.geometry`` form
clusters sized by the IFC facts --

    can          cylinder   the housing can (measured diameter / height)
    trim ring    thin cyl.  the visible trim flange at the ceiling (trim OD)
    lens         thin cyl.  the frosted lens disc inside the can
    frame        plate      the plaster / mounting frame plate
    junction box box        the gasketed integral J-box (hosts the connector)
    driver box   box        the LED driver enclosure atop the can
    2 bar hangers boxes     the telescoping bar hangers (set the width)

-- with the CCEA rating / aperture / housing / trim / mounting / lamp as
family PARAMETERS by NAME, the measured dimensions as dimension parameters,
and a photometric-web parameter left as an unset REFERENCE (a URL / path the
user supplies; never an embedded ``.ies``).  One single-phase LIGHTING
connector sits on the junction box's TOP face -- where the branch-circuit
conductors actually enter (knockouts / conduit connector) -- using the
factory's face-referenced connector (the box template; ``factory.add_
connector``), NOT the never-emitted cylinder-hosted connector of the
factory's stub downlight (that path hosts a connector on a curved solid via
the BOX face template -- an untested combination this module avoids).

CONTENT RULE (docs/product/content-strategy.md): the geometry and parameters
are OUR expression; the IFC (OUR OWN authoring) supplies the numbers.  No
cloned third-party geometry, no manufacturer content; photometry referenced,
never bundled.  The emitter is the ASSAY-CLEAN family path
(``rvt.famgen.famdoc_adoc.emit_family_rfa_v2``: OUR family ADocument, OUR
partition footer, OUR identity, PartAtom ours; the only carried stream is the
per-release schema constant) -- the same path that emitted the four
provenance-clean v2 families.

The LOAD (step 3, ``load_into_project``) drives the certified four-registry
loader ``rvt.famload.load_family_document`` (the L1a mechanism -- our family
becomes an embedded save unit + a ContentDocuments entry + a ContentTable
record + a FamilyMgr entry, plus its host Family / FamilySymbol / surrogates
/ ParamElemFamily twins) into the CERTIFIED host (default: the rst basic
sample, the exact host on which the loader is viewer-PROVEN).

Public API::

    from rvt.ifc import famfrom_ifc as FI
    prod = FI.make_downlight(ifc_path="inputs/ifc/chicago-plenum-downlight.ifc")
    rep  = prod.write_rfa("experiments/families/ifc/chicago_plenum_downlight.rfa")
    lr   = FI.load_into_project(FI.HOST_RST, "experiments/families/ifc/L_downlight_loaded.rvt")
    FI.build_deliverables()          # facts + .rfa (+ minimal sibling) + load + probes.json
    python -m rvt.ifc.famfrom_ifc    # the same, from the shell

TERRITORY: this module + ``rvt.ifc.product_facts`` + ``tests/test_ifc_family.py``
+ ``experiments/families/ifc/**`` + ``docs/inbox/ifc-family.md``.  Composes
(never edits) ``rvt.famgen.{skeleton, geometry, factory, famdoc_adoc}`` /
``rvt.famload`` / ``rvt.validate`` public constructors and codecs.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field as dc_field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from ..famgen import factory as F
from ..famgen import skeleton as SK
from ..famgen import geometry as G
from ..genesis.types import inches
from . import product_facts as PF

_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "..", "..", ".."))
OUT_DIR = os.path.join(_ROOT, "experiments", "families", "ifc")

#: the certified project HOST the family is loaded into by default -- the
#: rst basic sample: an Autodesk sample source (a certified BASE per the
#: probe_batch ledger) AND the exact host on which the four-registry loader
#: rvt.famload is VIEWER-PROVEN (L1a PASS, docs/coverage/viewer-certified.json)
HOST_RST = os.path.join(_ROOT, "samples", "rstbasicsampleproject.rvt")
#: the MEP sample host (carries the Lighting-Fixtures category style row the
#: family binds as a core id; the loader mechanism is NOT viewer-proven on
#: it) -- the domain-real variant, emitted as an informational sibling
HOST_RME = os.path.join(_ROOT, "samples", "rmebasicsampleproject.rvt")

#: the luminaire archetype family the recessed-can variant derives from --
#: the factory's luminaire (troffer form) through the assay-clean emitter.
#: NO .rfa has yet been viewer-certified (ledger 2026-08-04), so this file is
#: the FIRST base-to-certify in the batch (probes.json).
ARCHETYPE_RFA = os.path.join(_ROOT, "experiments", "families", "genesis2",
                             "troffer_2x4_v2.rfa")

PRODUCT_NAME = F.PRODUCT_NAME          # 'rvt-writer'

#: the CCEA / Chicago-plenum specification contract: family parameter NAMES
#: (a schedule / tag keyed on these names binds to the generated family) --
#: (parameter caption, IFC pset property, spec key, group key)
CCEA_CONTRACT_PARAMS = (
    ("CCEA Rating", "Rating", "text", "identity"),
    ("Aperture", "Aperture", "text", "identity"),         # the label ('6 in (152 mm) round')
    ("Housing", "Housing", "text", "identity"),
    ("Trim", "Trim", "text", "identity"),
    ("Mounting", "Mounting", "text", "identity"),
    ("Lamp", "Lamp", "text", "identity"),
)

#: dimension parameters (caption, downlight_geometry key, group)
DIM_PARAMS = (
    ("Aperture Diameter", "aperture_stated_ft", "dimensions"),      # nominal, STATED
    ("Housing Diameter", "can_diameter_ft", "dimensions"),          # measured can
    ("Housing Height", "can_height_ft", "dimensions"),
    ("Overall Height", "overall_height_stated_ft", "dimensions"),  # pset OverallHeightMeters
    ("Frame Length", "frame_length_ft", "dimensions"),
    ("Frame Width", "frame_width_ft", "dimensions"),
    ("Trim Diameter", "trim_diameter_ft", "dimensions"),
    ("Lens Diameter", "lens_diameter_ft", "dimensions"),
    ("Bar Hanger Span", "hanger_span_ft", "dimensions"),
)


class FamFromIfcError(ValueError):
    """The facts cannot honestly drive the family (a required measured
    dimension is missing) or a job parameter is unusable."""


# ---------------------------------------------------------------------------
# the resolved fact sheet (facts + job parameters, provenance-tagged)
# ---------------------------------------------------------------------------

def resolve_downlight_facts(facts: Optional[PF.ProductFacts] = None, *,
                            ifc_path: str = PF.DEFAULT_IFC,
                            voltage: Optional[float] = None,
                            wattage: Optional[float] = None,
                            lumens: Optional[float] = None,
                            cct: Optional[float] = None,
                            photometric_web: Optional[str] = None) -> F.FactSheet:
    """Resolve the IFC PRODUCT FACTS + the electrical / photometric JOB
    parameters into the factory's provenance-tagged :class:`FactSheet`.

    Geometry / spec strings come from the IFC (kind ``'fact'``, source =
    the IFC file); the electrical / photometric values the IFC does NOT
    state are JOB parameters (kind ``'given'``, i.e. UNVERIFIED, surfaced
    as such) or left unset (``None``) -- never fabricated.  A required
    housing dimension the tessellation cannot supply raises
    :class:`FamFromIfcError` (the constructor refuses to invent it).
    """
    if facts is None:
        facts = PF.extract_product_facts(ifc_path)
    geo = PF.downlight_geometry(facts)
    prod = facts.product
    src = os.path.basename(facts.source_path)
    sheet = F.FactSheet(
        subject=f"{prod.get('ifc_class')} '{prod.get('name')}' ({prod.get('tag')}) "
                f"from {src}",
        catalog=f"own-ifc/{PF._relpath(facts.source_path)}",
        variant=str(prod.get("tag") or prod.get("global_id") or "product"))
    src_id = f"{src}#{prod.get('global_id')}"
    # -- geometry (measured / stated) -------------------------------------------
    required = ("can_diameter_ft", "can_height_ft", "can_base_z_ft", "trim_diameter_ft",
                "frame_length_ft", "frame_width_ft", "frame_z_ft", "aperture_stated_ft")
    missing = [k for k in required if geo.get(k) is None]
    if missing:
        raise FamFromIfcError(f"the IFC facts lack required housing geometry {missing}: "
                              f"the constructor will not invent a dimension (measure a "
                              f"'housing_can' / 'trim_reflector' / 'plaster_frame' mesh "
                              f"and state the pset 'Aperture')")
    for k, v in geo.items():
        note = ""
        if k.startswith("aperture_stated") or k in ("aperture_label",):
            note = f"STATED in the pset 'Aperture' label {geo.get('aperture_label')!r}"
        elif k.startswith("overall_height_stated"):
            note = ("STATED pset 'OverallHeightMeters' (the tessellation measures "
                    f"{geo.get('measured_height_ft')} ft -- both recorded)")
        elif k.startswith("overall_dims") or k == "measured_height_ft":
            note = "the whole product envelope MEASURED from the tessellation"
        else:
            note = "MEASURED from our IFC's tessellated mesh bounding box"
        sheet.set(k, v, kind="fact", source=src_id, note=note)
    # -- the specification strings (pset) ---------------------------------------
    for caption, prop, _spec, _grp in CCEA_CONTRACT_PARAMS:
        val = facts.pset_value(prop)
        sheet.set(f"spec.{prop}", (str(val) if val is not None else None),
                  kind=("fact" if val is not None else "assumed"), source=src_id,
                  note=(f"pset property {prop!r} -> family parameter {caption!r}"
                        if val is not None else
                        f"pset property {prop!r} ABSENT (parameter {caption!r} left empty)"))
    # -- identity ---------------------------------------------------------------------
    sheet.set("model", str(prod.get("tag") or ""), kind="fact", source=src_id,
              note="IFC Tag -> the Model identity value / the family type name")
    sheet.set("product_name", str(prod.get("name") or ""), kind="fact", source=src_id)
    sheet.set("description", str(prod.get("description") or ""), kind="fact", source=src_id,
              note="IFC Description -> the Description identity value")
    sheet.set("manufacturer", None, kind="assumed",
              note="NOT SOURCED -- the IFC is OUR design (three-d-stage authoring), it names "
                   "no manufacturer; the Manufacturer identity value is deliberately not written")
    sheet.set("global_id", str(prod.get("global_id") or ""), kind="fact", source=src_id)
    sheet.set("surface_colours", {n: s.get("rgb") for n, s in facts.surface_styles.items()},
              kind="fact", source=src_id,
              note="IfcSurfaceStyle colours; carried in the report (no material elements "
                   "are authored -- the S0 discipline: no object-style copies)")
    # -- electrical / photometric JOB parameters (not in the IFC) ----------------------
    sheet.set("voltage_v", (float(voltage) if voltage is not None else 120.0),
              kind="given",
              note=("connector voltage supplied as a job parameter" if voltage is not None else
                    "connector voltage NOT in the IFC (no electrical pset) -- 120 V "
                    "single-phase DEFAULT for a residential/commercial recessed downlight; "
                    "an editable, UNVERIFIED parameter"))
    sheet.set("wattage_w", (float(wattage) if wattage is not None else None),
              kind=("given" if wattage is not None else "assumed"),
              note=("input wattage supplied as a job parameter" if wattage is not None else
                    "NOT SOURCED -- 'Integrated LED module' carries no wattage in the IFC; "
                    "the Wattage parameter is written as 0 (unset), never invented"))
    sheet.set("lumens_lm", (float(lumens) if lumens is not None else None),
              kind=("given" if lumens is not None else "assumed"),
              note="NOT SOURCED (no photometric pset)" if lumens is None else "job parameter")
    sheet.set("cct_k", (float(cct) if cct is not None else None),
              kind=("given" if cct is not None else "assumed"),
              note="NOT SOURCED (no photometric pset)" if cct is None else "job parameter")
    sheet.set("photometric_web", str(photometric_web or ""), kind=("given" if photometric_web
                                                                 else "assumed"),
              note=("photometric web REFERENCE (path / URL) -- a parameter the user fills; "
                    "the family never embeds an .ies payload (facts-store rule)"
                    if not photometric_web else "photometric web reference supplied"))
    sheet.notes.append("Source = OUR OWN IFC document (Claude-Design authoring): every 'fact' "
                       "is a measured mesh bounding box, a stated pset value or a surface "
                       "colour read from that file this session; provenance is ours end to end.")
    sheet.notes.append("Nulls (wattage / lumens / cct) are NOT SOURCED and never invented; "
                       "voltage is a job DEFAULT (given). All ride as editable parameters.")
    return sheet


# ---------------------------------------------------------------------------
# the composed FAMILY (the recessed-can variant of the luminaire archetype)
# ---------------------------------------------------------------------------

@dataclass
class DownlightProduct:
    """A composed downlight family: the finalized document + its facts."""
    doc: SK.FamilyDoc
    facts: F.FactSheet
    product_facts: PF.ProductFacts
    forms: List[G.FormBundle] = dc_field(default_factory=list)
    detail: str = "standard"
    file_stem: str = "chicago_plenum_downlight"
    notes: List[str] = dc_field(default_factory=list)

    @property
    def name(self) -> str:
        return self.doc.name

    def summary(self) -> Dict[str, Any]:
        return {
            "kind": "luminaire/recessed-downlight (IFC-derived)",
            "family_name": self.doc.name,
            "category": SK.category_label(self.doc.category_id),
            "part_type": self.doc.part_type,
            "detail": self.detail,
            "elements": len(self.doc.elements),
            "types": [n for n, _v in self.doc.types],
            "parameters": sorted(self.doc.params),
            "forms": [{"kind": fb.kind, "role": fb.params.get("role"),
                       **{k: v for k, v in fb.params.items()
                          if k in ("width_ft", "depth_ft", "height_ft", "radius_ft",
                                   "base_z_ft", "rep", "center")}}
                      for fb in self.forms],
            "connectors": len(self.doc.connectors),
            "assumed_fields": self.facts.assumed(),
            "unverified_fields": self.facts.unverified(),
            "notes": list(self.notes),
        }

    def write_rfa(self, path: str, *, mode: str = "candidate",
                  footer_mode: str = "nonce", validate: bool = True,
                  provenance: bool = True, report_path: Optional[str] = None
                  ) -> Dict[str, Any]:
        """Emit the standalone ``.rfa`` at ``path`` through the ASSAY-CLEAN
        family path (:func:`rvt.famgen.famdoc_adoc.emit_family_rfa_v2`),
        then run the certified family-mode validator + the byte-level
        provenance ledger + the read-back verification.  Writes
        ``<stem>.json`` beside it and returns the report dict."""
        from ..famgen import famdoc_adoc as FA
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        t0 = time.time()
        emit = FA.emit_family_rfa_v2(self.doc, path, mode=mode, footer_mode=footer_mode,
                                     write_reports=False)
        rep: Dict[str, Any] = {
            "path": path, "family": self.summary(), "facts": self.facts.as_json(),
            "product_facts": {"source": self.product_facts.source_path,
                              "sha256": self.product_facts.source_sha256,
                              "product": self.product_facts.product,
                              "psets": self.product_facts.psets,
                              "overall_dims_ft": self.product_facts.overall_dims_ft,
                              "meshes": self.product_facts.counts.get("meshes"),
                              "faces": self.product_facts.counts.get("faces")},
            "emit": {k: v for k, v in emit.items() if k not in ("adocument", "verify")},
            "verify": emit.get("verify"),
            "adocument_summary": {
                "conclusion": (emit.get("adocument") or {}).get("conclusion"),
                "registries": (emit.get("adocument") or {}).get("registries"),
                "residual": (emit.get("adocument") or {}).get("residual"),
            },
        }
        if validate:
            try:
                val = FA.validate_family_file(path)
                rep["validate"] = {
                    "family_mode": val["family_mode"], "arbiter_raw": {
                        "verdict": val["arbiter_raw"]["verdict"],
                        "n_errors": val["arbiter_raw"]["n_errors"],
                        "errors": val["arbiter_raw"]["errors"]},
                    "donor_parity": val.get("donor_parity"),
                    "ok": bool(val["ok"]), "gate_note": val["gate_note"]}
            except Exception as e:                              # pragma: no cover
                rep["validate"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        if provenance:
            try:
                prov = FA.provenance_scan_v2(path, our_ids={int(e.elem_id)
                                                             for e in self.doc.elements})
                rep["provenance"] = {"ok": bool(prov["ok"]), "verdict": prov["verdict"],
                                     "checks": prov["checks"],
                                     "adocument": {k: prov["adocument"].get(k) for k in (
                                         "inflated_bytes", "decodes_clean",
                                         "references_to_our_elements", "dangling_id_refs_gt99",
                                         "byte_scan_donor_ids", "donor_name_string_hits",
                                         "longest_common_run_with_donor_latest",
                                         "owner_family_id")},
                                     "identity": prov.get("identity"),
                                     "partition_footer": {k: prov["partition_footer"].get(k)
                                                          for k in ("units", "walker_errors",
                                                                    "signature_string_status",
                                                                    "end_record_is_decoded_constant",
                                                                    "donor_footer_blob_present",
                                                                    "donor_end_parity_present")},
                                     "carried_constants": prov.get("carried_constants")}
            except Exception as e:                              # pragma: no cover
                rep["provenance"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        rep["ok"] = bool(rep["verify"] and rep["verify"].get("ok")
                         and (not validate or (rep.get("validate") or {}).get("ok"))
                         and (not provenance or (rep.get("provenance") or {}).get("ok")))
        rep["seconds"] = round(time.time() - t0, 1)
        rp = report_path or (os.path.splitext(path)[0] + ".json")
        with open(rp, "w") as fh:
            json.dump(rep, fh, indent=1, default=str)
        rep["report_path"] = rp
        return rep


def _len(doc: SK.FamilyDoc, name: str) -> SK.SkelElement:
    return doc.add_family_parameter(name, F.SPEC["length"], F.GROUP["dimensions"])


def _txt(doc: SK.FamilyDoc, name: str, group: str = "identity") -> SK.SkelElement:
    return doc.add_family_parameter(name, F.SPEC["text"], F.GROUP[group])


def _num(doc: SK.FamilyDoc, name: str, spec: str, group: str) -> SK.SkelElement:
    return doc.add_family_parameter(name, F.SPEC[spec], F.GROUP[group])


def _add(doc: SK.FamilyDoc, fb: G.FormBundle) -> G.FormBundle:
    doc.add(*fb.elements)
    return fb


def make_downlight(*, facts: Optional[PF.ProductFacts] = None,
                   ifc_path: str = PF.DEFAULT_IFC,
                   voltage: Optional[float] = None, wattage: Optional[float] = None,
                   lumens: Optional[float] = None, cct: Optional[float] = None,
                   photometric_web: Optional[str] = None,
                   detail: str = "standard", solid: bool = True,
                   name: Optional[str] = None, start_id: int = 1000) -> DownlightProduct:
    """Compose OUR recessed-downlight family from the IFC product facts.

    Geometry (the FAMILY frame): the insertion origin is the CAN AXIS (the
    aperture centre a designer places on the ceiling grid) at the Ref. Level
    (the ceiling face, work-plane-based); every part keeps the product's
    REAL relative layout, translated so the can axis is (0, 0); z 0 = the
    trim / ceiling plane, all housing above it (z up into the plenum).

    ``detail``: ``'standard'`` = can + trim + lens + frame + junction box +
    driver box + 2 bar hangers (8 forms); ``'envelope'`` = can + trim ring
    only (2 forms -- the attribution sibling that isolates the multi-form
    composition).  Sub-inch hardware (screws, knockouts, locknuts, nail
    flags, frame lips) is RECORDED in the facts but not modelled as forms
    (below a family's level of detail).

    Parameters by NAME: the CCEA specification strings (``CCEA Rating``,
    ``Aperture``, ``Housing``, ``Trim``, ``Mounting``, ``Lamp``), the
    dimension set (:data:`DIM_PARAMS`), ``Wattage`` / ``Voltage`` /
    ``Lumens`` / ``Color Temperature`` (unset = 0 when not sourced) and the
    ``Photometric Web File`` REFERENCE (a URL/path text, never an .ies
    payload).  One single-phase Lighting connector on the junction box top.
    """
    if detail not in ("standard", "envelope"):
        raise FamFromIfcError(f"detail must be 'standard' or 'envelope', got {detail!r}")
    pf = facts if facts is not None else PF.extract_product_facts(ifc_path)
    fs = resolve_downlight_facts(pf, voltage=voltage, wattage=wattage, lumens=lumens,
                                 cct=cct, photometric_web=photometric_web)
    g = fs.get
    aperture_in = (g("aperture_stated_in") or 6.0)
    fam_name = name or f"Chicago-Plenum Recessed Downlight {aperture_in:g}in"
    can_r = float(g("can_diameter_ft")) / 2.0
    frame_len = float(g("frame_length_ft"))
    doc = SK.new_family_document("lighting_fixture", fam_name,
                                 part_type=SK.PART_TYPE["normal"],
                                 work_plane_based=True, start_id=int(start_id),
                                 plane_length_ft=max(6.0, frame_len * 2.5))
    doc.notes.append("luminaire (recessed downlight from OUR IFC): work-plane-based (ceiling "
                     "face); insertion origin = the can / aperture axis; z 0 = the trim plane")
    doc.notes.append("NO ImposterLight light-source element (skeleton exposes no constructor) "
                     "-- photometrics ride as parameters; the photometric web is an unset "
                     "REFERENCE parameter (never an embedded .ies)")
    doc.notes.append("no material / object-style elements are authored (the S0 discipline); "
                     "the five IFC surface colours are carried in the report only")

    # -- parameters ---------------------------------------------------------------
    p_dim: Dict[str, SK.SkelElement] = {}
    for caption, _key, _grp in DIM_PARAMS:
        p_dim[caption] = _len(doc, caption)
    p_txt: Dict[str, SK.SkelElement] = {}
    for caption, _prop, spec_k, grp_k in CCEA_CONTRACT_PARAMS:
        p_txt[caption] = doc.add_family_parameter(caption, F.SPEC[spec_k], F.GROUP[grp_k])
    p_watt = _num(doc, "Wattage", "wattage", "electrical")
    p_volt = _num(doc, "Voltage", "voltage", "electrical")
    p_lm = _num(doc, "Lumens", "luminous_flux", "photometrics")
    p_cct = _num(doc, "Color Temperature", "cct", "photometrics")
    p_ies = _txt(doc, "Photometric Web File", "photometrics")

    # -- the type row: facts as parameter VALUES ------------------------------------
    model = str(g("model") or "downlight")
    type_name = model or f"{aperture_in:g}in"
    watt = g("wattage_w")
    volt = float(g("voltage_v") or 120.0)
    values: Dict[Any, Any] = {}
    for caption, key, _grp in DIM_PARAMS:
        v = g(key)
        values[p_dim[caption].elem_id] = float(v) if v is not None else 0.0
    for caption, prop, _s, _g in CCEA_CONTRACT_PARAMS:
        v = g(f"spec.{prop}")
        values[p_txt[caption].elem_id] = str(v) if v is not None else ""
    values[p_watt.elem_id] = SK.watts(watt) if watt else 0.0
    values[p_volt.elem_id] = SK.volts(volt)
    values[p_lm.elem_id] = float(g("lumens_lm") or 0.0)
    values[p_cct.elem_id] = float(g("cct_k") or 0.0)
    values[p_ies.elem_id] = str(g("photometric_web") or "")
    values["model"] = model
    values["description"] = str(g("description") or "")
    if g("manufacturer"):                       # unsourced => NOT written (never invented)
        values["manufacturer"] = str(g("manufacturer"))
    doc.add_type(type_name, values)

    # -- GEOMETRY: the housing form clusters (product frame -> can axis at 0,0) --
    ctx = F.geometry_context(doc)
    rep = G.REP_SOLID if solid else G.REP_DUMMY
    can_c = g("can_center_ft") or [0.0, 0.0, 0.0]
    ox, oy = float(can_c[0]), float(can_c[1])          # translation: can axis -> origin

    def rel(cx: float, cy: float) -> Tuple[float, float]:
        return (float(cx) - ox, float(cy) - oy)

    forms: List[G.FormBundle] = []
    # (1) the housing can -- cylinder from the can base up
    can = _add(doc, G.cylinder(can_r, float(g("can_height_ft")), ctx, doc.ids,
                              base_z_ft=float(g("can_base_z_ft")),
                              center=(0.0, 0.0), rep=rep))
    can.params.update({"role": "housing can (sealed steel can)",
                       "source": "housing_can mesh bbox"})
    forms.append(can)
    # (2) the trim ring -- a thin disc at the ceiling plane (z 0 .. frame_z)
    frame_z = float(g("frame_z_ft") or 0.06)
    trim_h = max(frame_z, inches(0.25))
    trim = _add(doc, G.cylinder(float(g("trim_diameter_ft")) / 2.0, trim_h, ctx, doc.ids,
                               base_z_ft=0.0, center=(0.0, 0.0), rep=rep))
    trim.params.update({"role": "trim ring flange (white baffle trim, at the ceiling plane)",
                        "source": "trim_reflector mesh outer diameter"})
    trim.notes.append("the trim is a DISC of the trim OD -- the annular aperture cut (a "
                      "void through the flange) is a phase-2 form; the aperture value rides "
                      "as the 'Aperture Diameter' parameter")
    forms.append(trim)
    if detail == "standard":
        # (3) the frosted lens -- a thin disc inside the can at the lens plane
        lens_d = g("lens_diameter_ft")
        lens_z = g("lens_z_ft")
        if lens_d and lens_z is not None:
            lens_t = inches(0.125)
            lens = _add(doc, G.cylinder(float(lens_d) / 2.0, lens_t, ctx, doc.ids,
                                       base_z_ft=float(lens_z) - lens_t / 2.0,
                                       center=(0.0, 0.0), rep=rep))
            lens.params.update({"role": "frosted lens disc", "source": "lens mesh bbox"})
            forms.append(lens)
        # (4) the plaster / mounting frame plate
        frame = _add(doc, G.plate(frame_len, float(g("frame_width_ft")),
                                  max(float(g("frame_thickness_ft") or 0.0), inches(0.0625)),
                                  ctx, doc.ids, base_z_ft=frame_z,
                                  center=rel(*(g("frame_center_ft") or [0.0, 0.0])[:2]),
                                  rep=rep))
        frame.params.update({"role": "plaster / mounting frame plate",
                             "source": "plaster_frame mesh bbox"})
        forms.append(frame)
        # (5) the gasketed integral junction box (hosts the connector)
        jd = g("jbox_dims_ft")
        jc = g("jbox_center_ft")
        jbox = None
        if jd and jc is not None:
            jbox = _add(doc, G.box(float(jd[0]), float(jd[1]), float(jd[2]), ctx, doc.ids,
                                    base_z_ft=float(g("jbox_base_z_ft")),
                                    center=rel(jc[0], jc[1]), rep=rep))
            jbox.params.update({"role": "gasketed integral junction box (branch-circuit entry)",
                                "source": "junction_box mesh bbox"})
            forms.append(jbox)
        # (6) the LED driver enclosure atop the can
        dd = g("driver_dims_ft")
        dc_ = g("driver_center_ft")
        if dd and dc_ is not None:
            drv = _add(doc, G.box(float(dd[0]), float(dd[1]), float(dd[2]), ctx, doc.ids,
                                   base_z_ft=float(g("driver_base_z_ft")),
                                   center=rel(dc_[0], dc_[1]), rep=rep))
            drv.params.update({"role": "LED driver enclosure", "source": "driver_box mesh bbox"})
            forms.append(drv)
        # (7)(8) the telescoping bar hangers (front / back)
        span = g("hanger_span_ft")
        sec = g("hanger_bar_section_ft")
        offy = g("hanger_offset_y_ft")
        if span and sec and offy is not None:
            for side, sy in (("front", -float(offy)), ("back", +float(offy))):
                hb = _add(doc, G.box(float(span), float(sec[0]), float(sec[1]), ctx, doc.ids,
                                      base_z_ft=float(g("hanger_base_z_ft") or frame_z),
                                      center=rel(ox, sy + oy), rep=rep))
                hb.params.update({"role": f"telescoping bar hanger ({side})",
                                  "source": f"hanger_bar_{side} mesh bbox"})
                forms.append(hb)
    else:
        jbox = None

    # -- the electrical connector ---------------------------------------------------
    # single-phase LIGHTING feed on the junction box TOP face (the box template's
    # face-referenced connector); in the 'envelope' variant (no junction box) the
    # connector sits on the trim disc's start cap via the same box-face template
    # is NOT valid for a cylinder -- so the envelope variant hosts it on the
    # junction-box-less form set by using the datum host instead (see note).
    con_note = ""
    if jbox is not None:
        jd = g("jbox_dims_ft")
        jc = g("jbox_center_ft")
        top_z = float(g("jbox_base_z_ft")) + float(jd[2])
        cx, cy = rel(jc[0], jc[1])
        F.add_connector(doc, host=jbox, face="top",
                        location=(cx, cy, top_z), direction=(0.0, 0.0, 1.0),
                        u_axis=(1.0, 0.0, 0.0), voltage_v=volt, poles=1,
                        apparent_load_va=float(watt or 0.0), power_factor=0.95,
                        bind_voltage_param="Voltage", bind_load_param="Wattage",
                        load_class="Lighting", description="Power Connection")
        con_note = ("single-phase Lighting connector on the junction box TOP face "
                    "(face-referenced, box template) -- where the branch circuit enters")
    else:
        # envelope variant: no box form -> the datum-hosted connector (the S0e
        # skeleton pattern: host = the Ref. Level, tag 0), at the can top centre
        top_z = float(g("can_top_z_ft") or (float(g("can_base_z_ft")) + float(g("can_height_ft"))))
        doc.add_electrical_connector(host_element_id=None, host_geom_tag=0,
                                     location=(0.0, 0.0, top_z),
                                     direction=(0.0, 0.0, 1.0), voltage=volt, poles=1,
                                     load_class="Lighting",
                                     apparent_load_va=float(watt or 0.0),
                                     power_factor=0.95, bind_voltage_param="Voltage",
                                     bind_load_param="Wattage",
                                     description="Power Connection")
        con_note = ("envelope variant: datum-hosted connector (Ref. Level, tag 0 -- the S0e "
                    "pattern) at the can top; the standard variant hosts it on the J-box face")
    doc.finalize()
    prod = DownlightProduct(doc=doc, facts=fs, product_facts=pf, forms=forms,
                            detail=detail,
                            file_stem=("chicago_plenum_downlight" if detail == "standard"
                                       else "chicago_plenum_downlight_min"))
    prod.notes.append(con_note)
    prod.notes.append(f"{len(forms)} form clusters composed from rvt.famgen.geometry "
                      f"({sum(len(fb.elements) for fb in forms)} form elements) sized by the "
                      f"IFC facts; family frame = product frame translated by "
                      f"({-ox:+.4f}, {-oy:+.4f}) ft so the can axis is the insertion origin")
    prod.notes.append("apparent load = the input wattage (0 = NOT SOURCED, the IFC states no "
                      "wattage); power factor 0.95 booked; bound to the Wattage parameter")
    if fs.unverified():
        prod.notes.append("UNVERIFIED / not-sourced values surfaced as parameters: "
                          + ", ".join(fs.unverified()))
    hw = [p.name for p in pf.parts if p.role in ("hardware",) or p.name.startswith("frame_lip")
          or p.name.startswith("nail_flag") or p.name in ("jbox_gasket", "jbox_cover")]
    prod.notes.append(f"{len(hw)} sub-inch hardware meshes RECORDED in the facts but NOT "
                      f"modelled (below family level of detail): {hw}")
    return prod


# ---------------------------------------------------------------------------
# step 3 -- LOAD the family into a certified project base (rvt.famload)
# ---------------------------------------------------------------------------

@dataclass
class LoadReport:
    """The outcome of loading our family into a project host."""
    host: str
    out_path: str
    loader: str
    ok: bool
    stop_reason: str = ""
    plans: List[dict] = dc_field(default_factory=list)
    verify: Dict[str, Any] = dc_field(default_factory=dict)
    validate_project_mode: Dict[str, Any] = dc_field(default_factory=dict)
    acceptance: List[str] = dc_field(default_factory=list)
    error: str = ""
    seconds: float = 0.0

    def as_json(self) -> dict:
        return {"host": self.host, "out_path": self.out_path, "loader": self.loader,
                "ok": self.ok, "stop_reason": self.stop_reason, "plans": self.plans,
                "verify": self.verify, "validate_project_mode": self.validate_project_mode,
                "acceptance": self.acceptance, "error": self.error,
                "seconds": self.seconds}


def load_into_project(host_rvt: str = HOST_RST, out_rvt: Optional[str] = None, *,
                      builder: Optional[Callable[..., SK.FamilyDoc]] = None,
                      name: str = "chicago_plenum_downlight",
                      report_path: Optional[str] = None,
                      core_categories: Sequence[int] = (SK.OST_LIGHTING_FIXTURES,),
                      **make_kw: Any) -> LoadReport:
    """LOAD the downlight family into the project ``host_rvt`` through the
    certified four-registry loader (``rvt.famload.load_family_document`` --
    the L1a mechanism), writing ``out_rvt``; then validate the written
    project (``rvt.validate``, project mode).  ``builder`` = a
    ``callable(start_id) -> FamilyDoc`` (default: :func:`make_downlight`
    with ``make_kw``); the loader calls it with a free id block ABOVE the
    host watermark.

    ``core_categories`` DECLARES the family's category up front (default:
    OST_LightingFixtures) so the loader's host survey can bind the host's
    category style row as a CORE id when the host carries one (the MEP
    sample does -- GStyleElem 127; the structural sample does not, and the
    binding is honestly omitted, exactly as in the certified L1a).  With a
    builder the loader cannot infer the category before building, so an
    undeclared builder load binds no core ids on ANY host.  Returns a
    :class:`LoadReport`.
    """
    from .. import famload as FL
    out_rvt = out_rvt or os.path.join(OUT_DIR, "L_downlight_loaded.rvt")
    os.makedirs(os.path.dirname(os.path.abspath(out_rvt)) or ".", exist_ok=True)
    rep = LoadReport(host=host_rvt, out_path=out_rvt,
                     loader="rvt.famload.load_family_document (four-registry, L1a mechanism)",
                     ok=False)
    t0 = time.time()

    def _default_builder(start_id: int = 100000) -> SK.FamilyDoc:
        return make_downlight(start_id=start_id, **make_kw).doc

    build = builder or _default_builder
    fl = FL.FamilyLoad(key=name, builder=build,
                       core_categories=[int(c) for c in core_categories] or None)
    try:
        res = FL.load_family_document(host_rvt, fl, out_rvt, name=name,
                                      report_path=report_path or
                                      (os.path.splitext(out_rvt)[0] + "_load.json"))
        rep.ok = bool(res.ok)
        rep.stop_reason = str(res.stop_reason or "")
        rep.plans = [p.as_json() for p in res.plans]
        rep.verify = dict(res.proofs.get("verify_written") or {})
        rep.acceptance = list(res.acceptance)
    except Exception as exc:
        rep.ok = False
        rep.error = f"{type(exc).__name__}: {exc}"
    if os.path.exists(out_rvt):
        try:
            from .. import validate as _v
            vr = _v.validate_file(out_rvt)
            errs = [f for f in vr.findings if f.severity == _v.SEV_ERROR]
            warns = [f for f in vr.findings if f.severity == _v.SEV_WARNING]
            rep.validate_project_mode = {
                "verdict": "VALID" if not errs else "INVALID", "n_errors": len(errs),
                "errors": [f"{f.layer} {f.where}: {f.message}" for f in errs][:12],
                "n_warnings": len(warns),
                "warnings": [f"{f.layer} {f.where}: {f.message}" for f in warns][:6]}
        except Exception as e:                                  # pragma: no cover
            rep.validate_project_mode = {"error": f"{type(e).__name__}: {e}"}
    rep.seconds = round(time.time() - t0, 1)
    return rep


# ---------------------------------------------------------------------------
# the batch manifest (tools/probe_batch.py gate: probes.json)
# ---------------------------------------------------------------------------

def _rel(p: Optional[str]) -> Optional[str]:
    if not p:
        return None
    try:
        r = os.path.relpath(p, _ROOT)
    except ValueError:                                          # pragma: no cover
        return p
    return p if r.startswith("..") else r.replace(os.sep, "/")


def _ledger_status(path: str) -> str:
    """The viewer-certified ledger status of a repo path
    ('certified' | 'sample' | 'failed' | 'unknown')."""
    ledger = os.path.join(_ROOT, "docs", "coverage", "viewer-certified.json")
    rp = _rel(path)
    try:
        with open(ledger) as fh:
            d = json.load(fh)
    except (OSError, ValueError):
        return "unknown"
    cert = {str(e.get("file")) for e in (d.get("certified") or []) if e.get("file")}
    fail = {str(e.get("file")) for e in (d.get("failed") or []) if e.get("file")}
    if rp in cert:
        return "certified"
    if rp and rp.startswith("samples/") and os.path.exists(os.path.join(_ROOT, rp)):
        return "sample"
    if rp in fail:
        return "failed"
    return "unknown"


def write_probes_manifest(out_dir: str, *, rfa: Dict[str, Any],
                          rfa_min: Optional[Dict[str, Any]] = None,
                          load: Optional[LoadReport] = None,
                          load_rme: Optional[LoadReport] = None) -> Dict[str, Any]:
    """Write ``probes.json`` for this stream's batch (the ``tools/probe_batch
    .py`` grate).  The reading:

    * NO ``.rfa`` is viewer-certified (ledger 2026-08-04) -> our downlight
      ``.rfa`` cannot be a probe on a certified family base: it and its
      luminaire ARCHETYPE (the factory's troffer through the same assay-clean
      emitter) are staged as CANDIDATE-BASES, archetype FIRST -- 'certify me
      or fail me', the honest reading of an uncertified lineage.
    * the LOADED project IS a probe: its declared base = the certified host
      it was loaded into (samples/rstbasicsampleproject.rvt -- an Autodesk
      sample source AND the exact host on which the four-registry loader
      is viewer-PROVEN via L1a), so a FAIL convicts our family document's
      CONTENT (the one change vs L1a's level-head family).
    """
    arch_status = _ledger_status(ARCHETYPE_RFA)
    host_rst_status = _ledger_status(HOST_RST)
    entries: List[Dict[str, Any]] = []
    entries.append({
        "id": "IFA0-archetype",
        "kind": "candidate-base",
        "file": _rel(ARCHETYPE_RFA),
        "role": "the luminaire ARCHETYPE (factory make_luminaire, recessed-troffer form) through "
                "the assay-clean emitter -- the FAMILY the downlight variant derives from",
        "ledger_status": arch_status,
        "why_first": ("NO .rfa is viewer-certified yet (docs/coverage/viewer-certified.json has "
                      "zero family entries), so the archetype the downlight builds on is itself "
                      "unjudged; upload it FIRST as the base-to-certify. If it PASSES the "
                      "downlight becomes a one-variable probe on it (recessed-can composition + "
                      "IFC-facts parameters); if it FAILS the lighting-fixture family layer is "
                      "the finding and the downlight verdict is moot until it is fixed"),
        "if_PASS": "certified luminaire ARCHETYPE: family files reach the oracle at all, and the "
                   "clean-path lighting-fixture family (skeleton + box housing + connector + "
                   "parameters) loads; re-read IFA1 against it",
        "if_FAIL": "the lighting-fixture family layer itself fails (skeleton / clean ADocument / "
                   "lighting category) -- bisect with the certified panel/xfmr v2 siblings; "
                   "IFA1's verdict measures nothing until this passes",
    })
    entries.append({
        "id": "IFA1-downlight-rfa",
        "kind": "candidate-base",
        "file": _rel(rfa.get("path")),
        "derived_from": _rel(ARCHETYPE_RFA),
        "role": ("OUR recessed-downlight family composed from the IFC facts: 8 form clusters "
                 "(can / trim / lens / frame / junction box / driver / 2 bar hangers), the "
                 "CCEA-spec + dimension parameters, one Lighting connector on the junction "
                 "box top -- assay-clean emitter (our ADocument / footer / identity)"),
        "the_ONE_change_vs_archetype": ("housing = a MULTI-FORM recessed-can composition sized "
                                         "by measured IFC facts (vs the archetype's single box "
                                         "housing) + the CCEA/aperture/lamp/mounting parameter "
                                         "set + the photometric-web reference parameter"),
        "validate_family_mode": (rfa.get("validate") or {}).get("family_mode"),
        "provenance_ok": (rfa.get("provenance") or {}).get("ok"),
        "if_PASS": ("the IFC->family bridge lands a REAL family in the reader: our multi-form "
                    "recessed can is accepted; the fixture family is instantiable content"),
        "if_FAIL": ("(with IFA0 PASSING) the recessed-can COMPOSITION or the new parameter set "
                    "is the delta -- read the card; the IFA1m envelope sibling (2 forms) "
                    "attributes it to the multi-form composition vs the parameters"),
    })
    if rfa_min:
        entries.append({
            "id": "IFA1m-downlight-envelope",
            "kind": "candidate-base",
            "file": _rel(rfa_min.get("path")),
            "derived_from": _rel(ARCHETYPE_RFA),
            "role": ("the same family reduced to the housing ENVELOPE (can + trim ring, "
                     "datum-hosted connector) -- the attribution sibling isolating the "
                     "8-form composition"),
            "if_PASS": "(with IFA1 FAIL) the multi-form composition (jbox / driver / hangers / "
                       "lens / frame or the face-hosted connector) is the delta",
            "if_FAIL": "(with IFA0 PASS) the parameter set / connector binding is the delta, "
                       "not the form count",
        })
    if load is not None:
        entries.append({
            "id": "IFA2-downlight-loaded",
            "kind": "probe",
            "file": _rel(load.out_path),
            "base": _rel(load.host),
            "base_ledger_status": host_rst_status,
            "base_certification": ("Autodesk sample source (certified BASE by the gate) AND the "
                                   "exact host on which the four-registry loader rvt.famload "
                                   "is viewer-PROVEN: L1a_rstbasic_loaded_levelhead.rvt PASS"),
            "passing_sibling": ("experiments/genesis/loader/"
                                "L1a_rstbasic_loaded_levelhead.rvt (same loader + same host + the "
                                "same core-id pattern -- L1a bound its level-head category "
                                "GStyle 23795, we bind the host's built-in Lighting-Fixtures "
                                "projection GStyle 127 -- so the ONE change is the family "
                                "document: our lighting-fixture downlight (model family, part "
                                "type 0, 8 solids + a face-hosted connector) instead of the "
                                "level-head annotation family)"),
            "tests": ("does the reader accept the certified rst base with OUR IFC-derived "
                      "recessed-downlight family LOADED as an embedded document (save unit + "
                      "ContentDocuments + ContentTable + FamilyMgr coherent, host Family / "
                      "symbol / surrogates / param twins ours)?  = the family is INSTANTIABLE"),
            "loader_ok": load.ok,
            "validate_project_mode": load.validate_project_mode,
            "if_PASS": ("our IFC-derived family document is accepted as a project's embedded "
                        "content: the IFC -> facts -> family -> loaded-project bridge is proven "
                        "end to end at the reader; the family is a candidate for placement"),
            "if_FAIL": ("(with the CTRL passing and L1a certified) our family DOCUMENT's "
                        "content is the delta vs L1a's level head: the model-family layer "
                        "(part type 0 lighting fixture, multi-form solids, the electrical "
                        "connector / load classification, the symbol-regeneration hypothesis "
                        "H2) -- bisect against IFA2m (envelope-only load) and the acceptance "
                        "list"),
        })
    if load_rme is not None:
        entries.append({
            "id": "IFA3-downlight-loaded-rme",
            "kind": "probe",
            "file": _rel(load_rme.out_path),
            "base": _rel(load_rme.host),
            "base_ledger_status": _ledger_status(HOST_RME),
            "base_certification": "Autodesk MEP sample source (certified BASE by the gate)",
            "tests": ("the DOMAIN-REAL host: the MEP sample (an electrical / lighting project "
                      "that already carries luminaire families) -- the same loader and family "
                      "on a different host (the four-registry loader is NOT viewer-proven on "
                      "rme; the HOST is the variable vs IFA2). Both hosts bind the built-in "
                      "Lighting-Fixtures projection GStyle (element 127 in each) as the "
                      "family's core id -- the shipped category catalog is laid out "
                      "identically across the samples"),
            "loader_ok": load_rme.ok,
            "validate_project_mode": load_rme.validate_project_mode,
            "if_PASS": "the loader generalises to the MEP host; the electrical-domain project "
                       "accepts our fixture family alongside its own luminaires",
            "if_FAIL": ("(with IFA2 PASSING) the HOST is the delta (rme core-id binding / the "
                        "MEP registries), not our family content"),
        })
    manifest = {
        "stream": "ifc-family (IFC product facts -> OUR family -> loaded project)",
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "gate": ("tools/probe_batch.py: the .rfa entries are CANDIDATE-BASES (no family file "
                 "is viewer-certified); the loaded .rvt is a PROBE whose declared base is the "
                 "certified rst sample source. Stage with: tools/probe_batch.py stage "
                 "<IFA2 .rvt> --candidate-base <IFA0 archetype .rfa> --candidate-base "
                 "<IFA1 .rfa> --control-from samples/rstbasicsampleproject.rvt"),
        "read_order": ["CONTROL (gate-generated CTRL_ copy of a certified file) FIRST",
                       "IFA2 (the LOAD proof on the certified rst base -- the DONE probe)",
                       "IFA0 (the archetype .rfa: does the oracle read a family at all?)",
                       "IFA1 (our downlight .rfa) then IFA1m (envelope sibling)"],
        "bases": {"rst": {"path": _rel(HOST_RST), "ledger_status": host_rst_status},
                  "rme": {"path": _rel(HOST_RME), "ledger_status": _ledger_status(HOST_RME)},
                  "archetype": {"path": _rel(ARCHETYPE_RFA), "ledger_status": arch_status}},
        "known_passing_anchors": {
            "L1a": "experiments/genesis/loader/L1a_rstbasic_loaded_levelhead.rvt",
            "rst": "samples/rstbasicsampleproject.rvt"},
        "probes": entries,
        "hypotheses_carried": [
            "H1 an embedded family ADocument with the all-null 239-slot AppInfoManager "
            "(rvt.famload's L3 open question, unchanged)",
            "H2 the loaded FamilySymbol's seq-103 rep is a SerializedDummy -- Revit "
            "regenerates the symbol geometry from the family document (our 8 solids)",
            "H3 the family's electrical layer: one Lighting connector on a solid FACE "
            "(box template, geometry tag + edge-loop tags), our load classification",
            "H4 NO ImposterLight / photometric light-source object -- photometrics as "
            "parameters, photometric web an unset REFERENCE",
            "H5 the trim is a solid DISC (no annular aperture void) -- the aperture is a "
            "parameter value, not a cut form (phase 2)",
        ],
    }
    path = os.path.join(out_dir, "probes.json")
    with open(path, "w") as fh:
        json.dump(manifest, fh, indent=1, default=str)
    manifest["path"] = path
    return manifest


# ---------------------------------------------------------------------------
# the deliverable builder (steps 1-4 end to end)
# ---------------------------------------------------------------------------

def build_deliverables(out_dir: str = OUT_DIR, *, ifc_path: str = PF.DEFAULT_IFC,
                       with_load: bool = True, with_rme_load: bool = True,
                       with_envelope: bool = True,
                       voltage: Optional[float] = None, wattage: Optional[float] = None,
                       verbose: bool = True) -> Dict[str, Any]:
    """Build the whole ifc-family deliverable set into ``out_dir``:

    1. ``chicago_plenum_downlight.facts.json`` (+ the full facts dump) --
       the product-facts record (catalog schema, self-validated);
    2. ``chicago_plenum_downlight.rfa`` (+ ``_min.rfa`` envelope sibling) --
       our family, family-mode-validated, provenance-scanned;
    3. ``L_downlight_loaded.rvt`` (rst host, the DONE probe) and
       ``L_downlight_loaded_rme.rvt`` (rme host, informational) -- the family
       LOADED through ``rvt.famload``, project-mode-validated;
    4. ``probes.json`` (the gate manifest) + ``ifc_family.json`` (summary).
    """
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    summary: Dict[str, Any] = {"stream": "ifc-family", "out_dir": out_dir,
                               "ifc": _rel(ifc_path)}

    def log(m: str) -> None:
        if verbose:
            print(m, flush=True)

    # -- 1. FACTS ---------------------------------------------------------------------
    log(f"== 1 facts  <- {_rel(ifc_path)}")
    facts = PF.extract_product_facts(ifc_path)
    facts_path = os.path.join(out_dir, "chicago_plenum_downlight.facts.json")
    full_path = os.path.join(out_dir, "chicago_plenum_downlight.facts.full.json")
    wr = PF.write_facts_record(facts, facts_path, full_dump_path=full_path)
    summary["facts"] = {"path": facts_path, "full_dump": full_path,
                        "schema_valid": not wr["problems"],
                        "meshes": facts.counts["meshes"], "faces": facts.counts["faces"],
                        "styles": facts.counts["surface_styles"],
                        "properties": facts.counts["properties"],
                        "overall_dims_ft": facts.overall_dims_ft}
    log(f"   facts record schema-valid; {facts.counts['meshes']} meshes, "
        f"{facts.counts['properties']} pset properties, overall "
        f"{facts.overall_dims_ft['x']:.3f} x {facts.overall_dims_ft['y']:.3f} x "
        f"{facts.overall_dims_ft['z']:.3f} ft")

    # -- 2. the .rfa (+ envelope sibling) -------------------------------------------
    rfa_path = os.path.join(out_dir, "chicago_plenum_downlight.rfa")
    log(f"== 2 family -> {_rel(rfa_path)}")
    prod = make_downlight(facts=facts, voltage=voltage, wattage=wattage)
    rfa = prod.write_rfa(rfa_path)
    summary["rfa"] = {"path": rfa_path, "ok": rfa["ok"], "elements": len(prod.doc.elements),
                      "forms": len(prod.forms), "parameters": sorted(prod.doc.params),
                      "validate_family_mode": (rfa.get("validate") or {}).get("family_mode"),
                      "provenance_ok": (rfa.get("provenance") or {}).get("ok"),
                      "verify_ok": (rfa.get("verify") or {}).get("ok")}
    fm = (rfa.get("validate") or {}).get("family_mode") or {}
    log(f"   {len(prod.doc.elements)} elements / {len(prod.forms)} forms | family_mode="
        f"{fm.get('verdict')} ({fm.get('n_errors')} err) | provenance ok="
        f"{(rfa.get('provenance') or {}).get('ok')} | ok={rfa['ok']}")
    rfa_min = None
    if with_envelope:
        min_path = os.path.join(out_dir, "chicago_plenum_downlight_min.rfa")
        log(f"== 2b envelope sibling -> {_rel(min_path)}")
        prod_min = make_downlight(facts=facts, detail="envelope", voltage=voltage,
                                  wattage=wattage)
        rfa_min = prod_min.write_rfa(min_path)
        summary["rfa_min"] = {"path": min_path, "ok": rfa_min["ok"],
                              "elements": len(prod_min.doc.elements),
                              "forms": len(prod_min.forms),
                              "validate_family_mode": (rfa_min.get("validate") or {}).get(
                                  "family_mode"),
                              "provenance_ok": (rfa_min.get("provenance") or {}).get("ok")}
        fmm = (rfa_min.get("validate") or {}).get("family_mode") or {}
        log(f"   {len(prod_min.doc.elements)} elements / {len(prod_min.forms)} forms | "
            f"family_mode={fmm.get('verdict')} ({fmm.get('n_errors')} err) | ok={rfa_min['ok']}")

    # -- 3. LOAD into the certified project base -------------------------------------
    load = load_rme = None
    if with_load:
        out_rvt = os.path.join(out_dir, "L_downlight_loaded.rvt")
        log(f"== 3 load into rst -> {_rel(out_rvt)}")

        def _builder(start_id: int = 100000) -> SK.FamilyDoc:
            return make_downlight(facts=facts, voltage=voltage, wattage=wattage,
                                  start_id=start_id).doc

        load = load_into_project(HOST_RST, out_rvt, builder=_builder)
        summary["load_rst"] = load.as_json()
        vpm = load.validate_project_mode
        log(f"   loader ok={load.ok} {('| ' + load.stop_reason) if load.stop_reason else ''}"
            f"{('| ERROR ' + load.error) if load.error else ''} | project validate="
            f"{vpm.get('verdict')} ({vpm.get('n_errors')} err)")
        if with_rme_load and os.path.exists(HOST_RME):
            out_rme = os.path.join(out_dir, "L_downlight_loaded_rme.rvt")
            log(f"== 3b load into rme -> {_rel(out_rme)}")
            load_rme = load_into_project(HOST_RME, out_rme, builder=_builder,
                                         name="chicago_plenum_downlight")
            summary["load_rme"] = load_rme.as_json()
            v2 = load_rme.validate_project_mode
            log(f"   loader ok={load_rme.ok} {('| ' + load_rme.stop_reason) if load_rme.stop_reason else ''}"
                f"{('| ERROR ' + load_rme.error) if load_rme.error else ''} | project validate="
                f"{v2.get('verdict')} ({v2.get('n_errors')} err)")

    # -- 4. probes.json + summary --------------------------------------------------------
    probes = write_probes_manifest(out_dir, rfa=rfa, rfa_min=rfa_min, load=load,
                                   load_rme=load_rme)
    summary["probes"] = {"path": probes["path"], "ids": [e["id"] for e in probes["probes"]]}
    summary["seconds"] = round(time.time() - t0, 1)
    with open(os.path.join(out_dir, "ifc_family.json"), "w") as fh:
        json.dump(summary, fh, indent=1, default=str)
    log(f"== done in {summary['seconds']}s -> {out_dir}")
    return summary


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="rvt.ifc.famfrom_ifc",
                                 description="IFC product -> OUR Revit family (.rfa) -> loaded "
                                             "into a certified project base")
    ap.add_argument("--ifc", default=PF.DEFAULT_IFC, help="the IFC product file")
    ap.add_argument("--out", default=OUT_DIR, help="output directory")
    ap.add_argument("--voltage", type=float, default=None, help="connector voltage (job param)")
    ap.add_argument("--wattage", type=float, default=None, help="input wattage (job param)")
    ap.add_argument("--no-load", action="store_true", help="skip the famload proofs")
    ap.add_argument("--no-rme", action="store_true", help="skip the rme-hosted load")
    ap.add_argument("--no-envelope", action="store_true", help="skip the envelope sibling")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(list(argv) if argv is not None else None)
    s = build_deliverables(a.out, ifc_path=a.ifc, with_load=not a.no_load,
                           with_rme_load=not a.no_rme, with_envelope=not a.no_envelope,
                           voltage=a.voltage, wattage=a.wattage, verbose=not a.quiet)
    # exit 0 = the facts record is valid, the .rfa passed every gate, and (when
    # the load ran) the rst-hosted project loaded + validated
    ok = bool((s.get("facts") or {}).get("schema_valid")) and bool((s.get("rfa") or {}).get("ok"))
    if not a.no_load:
        load = s.get("load_rst") or {}
        ok = ok and bool(load.get("ok")) and \
            (load.get("validate_project_mode") or {}).get("verdict") == "VALID"
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
