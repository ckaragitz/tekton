"""rvt.famgen.factory -- THE ASSET FACTORY: compose real, generated Revit families.

The forge that turns a JOB SPEC ("an Eaton Pow-R-Line 480Y/277 V, 400 A,
42-space, main-breaker, surface-mounted panelboard") into a complete Revit
FAMILY file (``.rfa``) whose every byte is either OURS or a documented
per-release FORMAT constant -- and never a manufacturer's or Autodesk's
family content.

Pipeline (``docs/writer/asset-factory.md``)::

    job spec  -->  FACTS (rvt.famgen.catalog: manufacturer dimensions /
                   ratings, each figure tagged fact | assumed + source)
              -->  FAMILY DOCUMENT SKELETON (rvt.famgen.skeleton.FamilyDoc:
                   self-Family, Ref. Level, origin planes, plan view,
                   family parameters + types = the FACTS as parameters, the
                   tagging-contract parameter NAMES so schedules bind)
              -->  GEOMETRY (rvt.famgen.geometry: the enclosure box at TRUE
                   catalog dimensions, authored six-face solid or dummy rep)
              -->  ELECTRICAL CONNECTOR(S) on a real solid face (voltage /
                   poles / apparent load from the ratings, associated to the
                   type's parameters)
              -->  .rfa (our partition stream + our Global streams + our
                   PartAtom + real ECC + our container)
              -->  verify + validate (0 errors, family mode) + provenance scan

The product sentence this serves: "build me an Eaton panel with X and Y and
a room rated for 250 V" -- the platform CREATES the family (the asset), it
does not merely place a library symbol.

CONTENT RULE (docs/product/content-strategy.md, THE rule): no cloned
third-party geometry.  Manufacturer dimensions / ratings are FACTS (Feist);
photometry is REFERENCED (a URL), never redistributed; the geometry, the
parameters and the type table are OUR expression.  Every generated family
carries a provenance ledger (:func:`provenance_scan`) proving no Autodesk
family bytes, our ``PartAtom``, our ``BasicFileInfo`` identity, and naming
the format constants carried from the donor container.

Public API::

    from rvt.famgen import factory as F
    prod = F.make_panelboard(vendor='eaton', line='pow-r-line', mains_a=400,
                             spaces=42, voltage='480Y/277', mcb=True,
                             mounting='surface')
    rep  = prod.write('experiments/families/factory/eaton_prl_400A_42sp_480Y.rfa')
    prod = F.make_transformer(kva=75, primary_v=480, secondary_v='208Y/120')
    prod = F.make_luminaire(kind='recessed-troffer', size='2x4', wattage=38,
                            lumens=4600, cct=4000, voltage='120-277')
    F.provenance_scan(path)                   # standalone provenance report

    # the project-side LOADER (proven mechanisms + spec; no project file yet)
    F.parse_content_documents(payload)        # Global/ContentDocuments codec
    F.insert_content_document(payload, guid, adoc)
    F.author_embedded_adocument(prod.doc)     # our embedded document object
    F.build_family_save_unit(prod.doc)        # our partition save unit
    F.splice_save_unit(host_logical, unit_bytes)
    F.loader_readiness(host_rvt, prod)        # runs P1..P5, stops honestly

CLI: ``tools/make_family.py`` (``python tools/make_family.py panelboard ...``).

TERRITORY: this module only composes the sibling modules' public
constructors (rvt.famgen.skeleton / geometry / catalog) and the format
codecs (rvt.families / rvt.adocument / rvt.validate); it edits none of them.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import uuid
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from . import catalog as C
from . import skeleton as SK
from . import geometry as G
from ..genesis.types import inches, mm

_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "..", "..", ".."))
FACTORY_OUT = os.path.join(_ROOT, "experiments", "families", "factory")

# ---------------------------------------------------------------------------
# parameter vocabulary -- the tekton-ifc TAGGING CONTRACT names
# (skills/tekton-ifc/references/shared-parameters-mapping.md,
#  usecases/eaton-panelboard/panelboard-shared-parameters.txt) so a project
# schedule / tag keyed on these NAMES binds to a generated family.
# ---------------------------------------------------------------------------

#: panelboard contract parameters: (name, spec-type-id key, group key)
PANEL_CONTRACT_PARAMS = (
    ("PanelName", "text", "identity"),
    ("Voltage", "voltage", "electrical"),
    ("Phases", "integer", "electrical"),
    ("Wires", "integer", "electrical"),
    ("BusRating", "current", "electrical"),
    ("MainsType", "text", "electrical"),
    ("MainsRating", "current", "electrical"),
    ("ShortCircuitRatingkA", "number", "electrical"),
    ("Mounting", "text", "identity"),
    ("NumberOfCircuits", "integer", "electrical"),
    ("NeutralRating", "text", "electrical"),
)

#: Forge spec type ids for family parameters.  The ``-1.0.0`` form is what
#: real family parameters carry [VERIFIED on the .rfa / rme family specimens:
#: length-1.0.0, potential-1.0.0]; the electrical + photometric ids are in
#: the Revit-shipped Forge spec corpus (ESSchemaStorage) [VERIFIED present];
#: the integer id is the published generic spec [INFERRED -- no integer
#: family parameter exists in the specimen set; a wrong spec id only affects
#: units display].
SPEC = {
    "length": SK.SPEC_LENGTH,                                    # V
    "text": SK.SPEC_TEXT,                                        # published id
    "number": SK.SPEC_NUMBER,                                    # number-1.0.0 (Revit-2026 registry + donor units table; #333 round 17)
    "integer": SK.SPEC_INTEGER,      # sentinel: selects ParamDefInt (storage-class law, #333 r24)
    "voltage": SK.SPEC_VOLTAGE,                                  # V
    "current": "autodesk.spec.aec.electrical:current-1.0.0",     # corpus
    "apparent_power": SK.SPEC_APPARENT_POWER,                    # corpus
    "wattage": SK.SPEC_WATTAGE,                                  # corpus
    "luminous_flux": SK.SPEC_LUMINOUS_FLUX,                      # corpus
    "cct": SK.SPEC_COLOR_TEMPERATURE,                           # corpus
    "efficacy": "autodesk.spec.aec.electrical:efficacy-1.0.0",   # corpus
}
GROUP = {
    "dimensions": SK.PGROUP_DIMENSIONS,
    "identity": SK.PGROUP_IDENTITY,
    "electrical": SK.PGROUP_ELECTRICAL,
    "electrical_loads": SK.PGROUP_ELECTRICAL_LOADS,
    "photometrics": "autodesk.parameter.group:lightPhotometrics-1.0.0",  # corpus
    "constraints": SK.PGROUP_CONSTRAINTS,
}

#: our product identity written into PartAtom / BasicFileInfo (no Autodesk
#: product label; the family NAME is the file name / PartAtom title)
PRODUCT_NAME = "rvt-writer"


# ---------------------------------------------------------------------------
# provenance-tagged values
# ---------------------------------------------------------------------------

@dataclass
class Fact:
    """One value with its provenance -- the honesty unit of the factory.

    ``kind``: 'fact' (read from a published document, catalog-flagged),
    'assumed' (catalog-flagged assumed / derived from a fact by a rule not
    on the record), 'derived' (computed by us from facts), 'given' (a job
    parameter the user supplied), 'ours' (our expression: names, our own
    parametric envelope).  Assumed / given values SURFACE as unverified
    parameters; a fact carries its source id.
    """
    value: Any
    kind: str = "fact"
    source: str = ""
    note: str = ""

    def as_json(self) -> dict:
        return {"value": self.value, "provenance": self.kind,
                "source": self.source, "note": self.note}


@dataclass
class FactSheet:
    """The resolved facts driving one family (job spec x catalog record)."""
    subject: str                          # "eaton/pow-r-line-panelboards PRL2X 400A 42sp"
    catalog: str = ""                     # "vendor/line" record used ('' = none)
    variant: str = ""                     # catalog model / variant id
    values: Dict[str, Fact] = dc_field(default_factory=dict)
    notes: List[str] = dc_field(default_factory=list)

    def set(self, key: str, value: Any, kind: str = "fact", source: str = "",
            note: str = "") -> Fact:
        f = Fact(value, kind, source, note)
        self.values[key] = f
        return f

    def get(self, key: str, default: Any = None) -> Any:
        f = self.values.get(key)
        return f.value if f is not None else default

    def assumed(self) -> List[str]:
        return sorted(k for k, f in self.values.items() if f.kind == "assumed")

    def unverified(self) -> List[str]:
        return sorted(k for k, f in self.values.items()
                      if f.kind in ("assumed", "given"))

    def as_json(self) -> dict:
        return {"subject": self.subject, "catalog": self.catalog,
                "variant": self.variant,
                "values": {k: f.as_json() for k, f in self.values.items()},
                "assumed_fields": self.assumed(),
                "notes": list(self.notes)}


class FactoryError(ValueError):
    """A job the factory cannot honestly build (missing / unsourced fact,
    an out-of-catalog request); the message says what to source / change."""


# ---------------------------------------------------------------------------
# OUR shared-parameter file -- the GUID identities a firm's schedules / tags
# bind by (parsed and applied by rvt.famgen.skeleton: a parameter whose
# caption AND datatype match a row is authored SHARED at the row's GUID,
# verbatim; every other parameter stays local -- reference §1.3).
# ---------------------------------------------------------------------------

#: the tracked shared-parameter file of the tagging contract (OURS)
DEFAULT_SHARED_PARAMS = os.path.join(_ROOT, "usecases", "eaton-panelboard",
                                     "panelboard-shared-parameters.txt")


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(s).lower()).strip("_")


def _fp(sheet: FactSheet, variant: dict, path: str, key: str, *,
        transform=None, fact_only: bool = False) -> Fact:
    """Copy a catalog field into the sheet with its provenance flag.
    ``transform`` converts the raw value (e.g. inches -> feet)."""
    val = C.require(variant, path, fact_only=fact_only)
    kind = C.field_provenance(variant, path) or "assumed"
    if transform is not None:
        val = transform(val)
    return sheet.set(key, val, kind=kind, source=variant.get("model", ""))


def _voltage_number(voltage: Any) -> Tuple[float, int, int]:
    """Parse a system voltage string into (line-to-line V, phases, wires).

    '480Y/277' -> (480, 3, 4); '208Y/120' -> (208, 3, 4); '240' -> (240, 1, 3
    for a 3-wire single-phase / or 3, 3); '480' -> (480, 3, 3); '600' -> (600,
    3, 3); a bare number = that L-L voltage, 3-phase 3-wire assumed.
    """
    s = str(voltage).strip().upper().replace("V", "").replace(" ", "")
    m = re.match(r"^(\d+(?:\.\d+)?)Y/(\d+(?:\.\d+)?)$", s)
    if m:
        return float(m.group(1)), 3, 4
    m = re.match(r"^(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)$", s)      # 120/240 split phase
    if m:
        return float(m.group(2)), 1, 3
    m = re.match(r"^(\d+(?:\.\d+)?)$", s)
    if m:
        v = float(m.group(1))
        return v, 3, 3
    raise FactoryError(f"unrecognised voltage {voltage!r}: use e.g. 480Y/277, "
                       f"208Y/120, 480, 240, 120/240")


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------------------
# FACTS RESOLUTION -- panelboard
# ---------------------------------------------------------------------------

#: line aliases -> catalog (vendor, line) records
_PANEL_LINES = {
    ("eaton", "pow-r-line"): ("eaton", "pow-r-line-panelboards"),
    ("eaton", "pow-r-line-panelboards"): ("eaton", "pow-r-line-panelboards"),
    ("eaton", "prl"): ("eaton", "pow-r-line-panelboards"),
    ("square-d", "nq"): ("square-d", "nq-nf-iline-panelboards"),
    ("square-d", "nf"): ("square-d", "nq-nf-iline-panelboards"),
    ("square-d", "nq-nf-iline-panelboards"): ("square-d", "nq-nf-iline-panelboards"),
}


def _eaton_prl_model(voltage_ll: float, phases: int, wires: int) -> str:
    """Choose the Pow-R-Line member by voltage class (catalog facts):
    PRL1X = 240 Vac max; PRL2X = 240 & 480Y/277; PRL3X = up to 600 Vac."""
    if voltage_ll <= 240 and not (wires == 4 and voltage_ll > 240):
        return "PRL1X"
    if voltage_ll <= 480:
        return "PRL2X"
    return "PRL3X"


def _panel_box_height(sheet: FactSheet, variant: dict, prl1x: Optional[dict],
                      mains_a: float, spaces: int, mcb: bool) -> Fact:
    """Resolve the panel box HEIGHT.

    Facts: a Pow-R-Line box height is a FUNCTION of mains rating + branch
    circuit count (the box family's H options are facts; the PRL1X
    circuits->height table is a fact).  For a member whose own sizing table
    is not on the record (PRL2X/3X/3E carry only 'same box family, heights
    per the member's sizing table'), the height is taken from the SHARED
    box family's PRL1X table and flagged 'assumed' (surfaced as unverified),
    then snapped up to the member's own tabulated height options (facts).
    Never invents: >42 spaces on a 20-in section is a multi-section panel
    the catalog read does not size -> FactoryError.
    """
    dims = variant.get("dims_in") or {}
    h_options = dims.get("h_options") or []
    opts = variant.get("options") or {}
    rat = variant.get("ratings") or {}
    source_variant = variant
    kind = "fact"
    scope_note = ""
    # circuits->height sizing table, in either catalog shape:
    #   options.box_height_by_circuits (Eaton PRL1X: per mains + config)
    #   options.mlo_box_height_single_phase_3wire (Square D NQ: per mains, MLO)
    table = opts.get("box_height_by_circuits")
    if table is None and opts.get("mlo_box_height_single_phase_3wire") is not None:
        table = opts.get("mlo_box_height_single_phase_3wire")
        if mcb:
            kind = "assumed"
            scope_note = ("; the record's height table is the MLO / single-phase "
                          "table -- an MCB / 3-phase interior may need a taller "
                          "box -- SURFACED AS UNVERIFIED")
    if table is None and prl1x is not None:
        table = (prl1x.get("options") or {}).get("box_height_by_circuits")
        source_variant = prl1x
        kind = "assumed"          # borrowed from the shared box family (PRL1X)
    # the member's single-section circuit limit (catalog fact; else the Eaton
    # 20-in section's 42): larger => multi-section, not sized by the record
    max_single = (opts.get("max_branch_circuits_single_section")
                  or rat.get("max_branch_pole_spaces")
                  or (prl1x or {}).get("options", {}).get("max_branch_circuits_single_section")
                  or 42)
    if spaces > int(max_single):
        raise FactoryError(
            f"{spaces} spaces exceeds the member's single-section maximum "
            f"({int(max_single)}, catalog fact): larger panels are MULTI-SECTION "
            "and their box height is not sized by the catalog record -- refusing "
            "to invent one")
    if not table:
        raise FactoryError(f"{variant.get('model')}: no circuits->height sizing "
                           "table on record and no shared-family table to borrow")
    # pick the row group: mains rating + MCB/MLO configuration
    want = "main breaker" if mcb else "main lugs"
    groups = [g for g in table if float(g.get("mains_a", -1)) == float(mains_a)]
    if not groups:
        avail = sorted({float(g.get("mains_a", -1)) for g in table})
        raise FactoryError(f"no sizing rows for {mains_a} A mains; tabulated: {avail}")
    def _score(g):
        cfg = str(g.get("config", "")).lower()
        # prefer the plain (no through-feed / sub-feed) configuration
        base = 0 if ("through-feed" not in cfg and "sub-feed" not in cfg) else 5
        return base + (0 if want in cfg else 2)
    group = sorted(groups, key=_score)[0]
    height_in = None
    matched_row = None
    for row in group.get("rows") or []:
        try:
            max_ckts, h = int(row[0]), float(row[1])
        except (TypeError, ValueError, IndexError):     # pragma: no cover
            continue
        if spaces <= max_ckts:
            height_in = h
            matched_row = max_ckts
            break
    if height_in is None:
        raise FactoryError(f"{spaces} circuits not covered by the sizing rows "
                           f"for {mains_a} A ({group.get('config')})")
    # snap up to the member's own tabulated box heights (facts)
    numeric_opts = sorted(float(x) for x in h_options if isinstance(x, (int, float)))
    snapped = False
    if numeric_opts and height_in not in numeric_opts:
        bigger = [x for x in numeric_opts if x >= height_in]
        if not bigger:
            raise FactoryError(f"height {height_in} in exceeds the tabulated box "
                               f"heights {numeric_opts}")
        height_in = bigger[0]
        kind = "assumed"
        snapped = True
    cfg = group.get("config")
    note = (f"row '{spaces} circuits <= {matched_row}' -> {height_in:g} in from the "
            f"{source_variant.get('model')} sizing table"
            + (f" (config '{cfg}')" if cfg else ""))
    if snapped:
        note += f"; snapped up to the member's tabulated heights {numeric_opts}"
    if source_variant is not variant:
        note += ("; borrowed from the shared box family (member's own sizing "
                 "table not on record) -- SURFACED AS UNVERIFIED")
    note += scope_note
    return sheet.set("height_in", float(height_in), kind=kind,
                     source=source_variant.get("model", ""), note=note)


def resolve_panelboard_facts(vendor: str = "eaton", line: str = "pow-r-line",
                             *, mains_a: float, spaces: int, voltage,
                             mcb: bool = True, mounting: str = "surface",
                             sccr_ka: Optional[float] = None,
                             panel_name: str = "PANEL",
                             neutral_rating: str = "100%") -> FactSheet:
    """Resolve every dimension / rating for a panelboard from the catalog.

    Width / depth are catalog FACTS (never zero-filled: null -> FactoryError);
    height per :func:`_panel_box_height`; ratings from the variant + the
    job spec ('given').  ``sccr_ka`` defaults to the low end of the
    member's fully-rated interrupting range for the voltage (fact) and is
    'assumed' when the record's rating is a range (the exact kA depends on
    the ordered devices).
    """
    key = (str(vendor).lower(), str(line).lower())
    if key not in _PANEL_LINES:
        raise FactoryError(f"no panelboard facts line for {vendor}/{line}; "
                           f"known: {sorted(_PANEL_LINES)}")
    cv, cl = _PANEL_LINES[key]
    vll, phases, wires = _voltage_number(voltage)
    if cv == "eaton":
        model = _eaton_prl_model(vll, phases, wires)
    else:
        # square-d: NQ = 240 Vac; NF = 480Y/277 & 600Y/347
        model = "NQ" if vll <= 240 else "NF"
    doc = C.load_line(cv, cl)
    try:
        variant = C.get_variant(cv, cl, model=model)
    except C.CatalogError as e:
        raise FactoryError(str(e))
    prl1x = None
    if cv == "eaton" and model != "PRL1X":
        try:
            prl1x = C.get_variant(cv, cl, model="PRL1X")
        except C.CatalogError:
            prl1x = None
    sheet = FactSheet(subject=f"{cv}/{cl} {model} {mains_a:g} A {spaces} sp {voltage}",
                      catalog=f"{cv}/{cl}", variant=model)
    # -- dimensions (facts; never fabricated) -------------------------------
    _fp(sheet, variant, "dims_in.w", "width_in", fact_only=False)
    _fp(sheet, variant, "dims_in.d", "depth_in", fact_only=False)
    if sheet.get("width_in") in (None, "VARIABLE"):
        raise FactoryError(f"{model}: box width not sourced")
    if sheet.get("depth_in") in (None, "VARIABLE"):
        raise FactoryError(f"{model}: box depth not sourced")
    _panel_box_height(sheet, variant, prl1x, mains_a, spaces, mcb)
    lf = doc.get("line_facts") or {}
    gt = ((lf.get("gutter_top_bottom_min_in") or {}).get("value"))
    gs = ((lf.get("gutter_side_min_in") or {}).get("value"))
    if gt is not None:
        sheet.set("gutter_top_bottom_min_in", float(gt), kind="fact", source=cl)
    if gs is not None:
        sheet.set("gutter_side_min_in", float(gs), kind="fact", source=cl)
    # -- ratings -------------------------------------------------------------
    r = variant.get("ratings") or {}
    sheet.set("voltage_ll_v", float(vll), kind="given", note=str(voltage))
    sheet.set("voltage_system", str(voltage), kind="given")
    sheet.set("phases", int(phases), kind="given")
    sheet.set("wires", int(wires), kind="given")
    sheet.set("mains_rating_a", float(mains_a), kind="given")
    sheet.set("bus_rating_a", float(mains_a), kind="derived",
              note="bus ampacity taken equal to the mains rating (a smaller-bus "
                   "option exists; ordering choice, not a catalog fact)")
    sheet.set("spaces", int(spaces), kind="given")
    sheet.set("mains_type", "MCB" if mcb else "MLO", kind="given")
    sheet.set("mounting", str(mounting).lower(), kind="given")
    sheet.set("panel_name", str(panel_name), kind="given")
    sheet.set("neutral_rating", str(neutral_rating), kind="given",
              note="neutral rating is an ordering option (100% / 200%), user-given")
    # mains ratings offered (fact) -> validate the request against the catalog
    offered = (r.get("mains_ratings_available_a")
               or (prl1x or {}).get("ratings", {}).get("mains_ratings_available_a"))
    if offered and float(mains_a) not in [float(x) for x in offered]:
        sheet.notes.append(f"{mains_a:g} A mains not in the tabulated ratings {offered}; "
                           "carried as a user-given value")
    mlo_max = r.get("mlo_max_a") or r.get("main_device_max_a")
    if mlo_max is not None and float(mains_a) > float(mlo_max):
        raise FactoryError(f"{model}: {mains_a:g} A exceeds the member's maximum "
                           f"{mlo_max} A (catalog fact)")
    vmax = r.get("voltage_max_ac_v")
    if vmax is not None:
        sheet.set("voltage_max_ac_v", float(vmax), kind=C.field_provenance(
            variant, "ratings.voltage_max_ac_v") or "fact", source=model)
        if vll > float(vmax):
            raise FactoryError(f"{model}: {vll:g} V exceeds the member's "
                               f"{vmax} Vac maximum (catalog fact)")
    # short-circuit rating: user value, else the low end of the fully-rated
    # interrupting range at this voltage (fact -> assumed as a default choice)
    if sccr_ka is not None:
        sheet.set("sccr_ka", float(sccr_ka), kind="given")
    else:
        ika = r.get("interrupting_ka_fully_rated") or r.get("interrupting_ka_fully_rated_240v")
        val = None
        if isinstance(ika, dict):
            # keyed by voltage class ('240', '480Y/277', ...)
            for k in (str(voltage).strip(), f"{int(vll)}", f"{int(vll)}Y/{int(round(vll/1.732))}"):
                if k in ika:
                    val = ika[k]
                    break
            if val is None and ika:
                val = next(iter(ika.values()))
        elif ika is not None:
            val = ika
        if isinstance(val, list) and val:
            val = val[0]
        if val is not None:
            sheet.set("sccr_ka", float(val), kind="assumed", source=model,
                      note="default = low end of the member's fully-rated interrupting "
                           "range at this voltage (catalog fact); the actual kA "
                           "depends on the ordered branch devices -- UNVERIFIED")
        else:
            sheet.set("sccr_ka", None, kind="assumed",
                      note="not sourced; parameter left for the user")
    # identity (manufacturer / model as PARAMETER VALUES -- content-strategy 5.4)
    sheet.set("manufacturer", "Eaton" if cv == "eaton" else "Schneider Electric",
              kind="fact", source=cl, note="brand of the catalog record")
    sheet.set("model", model, kind="fact", source=cl,
              note="catalog member; carried as the Model parameter VALUE, not the family name")
    sheet.notes.append("Panelboard weights are NOT published in the catalog "
                       "sections read -> no Weight parameter is emitted.")
    sheet.notes.append("Family / type NAMES avoid catalog numbers; manufacturer "
                       "and model ride as identity-parameter VALUES "
                       "(content-strategy 5.4 unsettled).")
    return sheet


# ---------------------------------------------------------------------------
# FACTS RESOLUTION -- transformer
# ---------------------------------------------------------------------------

_XFMR_LINES = {
    "eaton": ("eaton", "dry-type-transformers"),
    "hps": ("hps", "sentinel-g-transformers"),
}


def resolve_transformer_facts(kva: float, *, vendor: str = "eaton",
                              primary_v: Any = 480, secondary_v: Any = "208Y/120",
                              enclosure: str = "NEMA 2 (indoor)") -> FactSheet:
    """Resolve W/H/D + weight + frame for a dry-type transformer by kVA.

    500 kVA reads 'Contact Eaton representative' in the catalog (dims null)
    -> FactoryError (never invented).
    """
    v = str(vendor).lower()
    if v not in _XFMR_LINES:
        raise FactoryError(f"no transformer facts for vendor {vendor!r}; "
                           f"known: {sorted(_XFMR_LINES)}")
    cv, cl = _XFMR_LINES[v]
    try:
        variant = C.get_variant(cv, cl, kva=float(kva))
    except C.CatalogError as e:
        raise FactoryError(str(e))
    model = variant.get("model", "")
    sheet = FactSheet(subject=f"{cv}/{cl} {model} {kva:g} kVA",
                      catalog=f"{cv}/{cl}", variant=model)
    for axis, key in (("w", "width_in"), ("h", "height_in"), ("d", "depth_in")):
        try:
            _fp(sheet, variant, f"dims_in.{axis}", key)
        except C.CatalogError as e:
            raise FactoryError(f"{model}: {e} (the catalog publishes no dimensions "
                               f"for this rating -- refusing to invent them)")
        if sheet.get(key) is None:
            raise FactoryError(f"{model}: dims_in.{axis} not sourced")
    r = variant.get("ratings") or {}
    sheet.set("kva", float(kva), kind="fact", source=model)
    sheet.set("phases", int(r.get("phase") or 3), kind=C.field_provenance(
        variant, "ratings.phase") or "fact", source=model)
    sheet.set("primary_v", primary_v, kind="given",
              note=f"catalog primary {r.get('primary_v')}")
    sheet.set("secondary_v", secondary_v, kind="given",
              note=f"catalog secondary {r.get('secondary_v')}")
    for k in ("temp_rise_c", "frequency_hz", "windings", "weight_lb", "weight_kg",
              "frame", "weathershield_kit", "wall_mount_bracket"):
        if k in r and r[k] is not None:
            sheet.set(k, r[k], kind=C.field_provenance(variant, f"ratings.{k}")
                      or "fact", source=model)
    sheet.set("enclosure", str(enclosure), kind="given")
    sheet.set("manufacturer", "Eaton" if cv == "eaton" else "Hammond Power Solutions",
              kind="fact", source=cl)
    sheet.set("model", model, kind="fact", source=cl,
              note="catalog number as the Model parameter VALUE, not the family name")
    lf = C.load_line(cv, cl).get("line_facts") or {}
    clr = (lf.get("install_clearance_side_rear_in") or {}).get("value")
    if clr is not None:
        sheet.set("clearance_side_rear_in", float(clr), kind="fact", source=cl)
    sheet.notes.append("kVA / voltages / frame / dims / weight are catalog facts; "
                       "enclosure choice + connector layout are ours.")
    return sheet


# ---------------------------------------------------------------------------
# FACTS RESOLUTION -- luminaire
# ---------------------------------------------------------------------------

_LUM_KINDS = {
    "recessed-troffer": ("lithonia", "blt-led-troffer"),
    "troffer": ("lithonia", "blt-led-troffer"),
    "downlight": ("lithonia", "ldn6-led-downlight"),
    "recessed-downlight": ("lithonia", "ldn6-led-downlight"),
}


def resolve_luminaire_facts(kind: str = "recessed-troffer", *,
                            size: str = "2x4", wattage: Optional[float] = None,
                            lumens: Optional[float] = None,
                            cct: Optional[float] = None,
                            voltage: Any = "120-277",
                            aperture_in: Optional[float] = None,
                            housing_height_in: Optional[float] = None) -> FactSheet:
    """Resolve housing dims + electrical/photometric ratings for a luminaire.

    Troffer: 2x4 -> 2BLT4-38W (facts), 2x2 -> 2BLT2 (all 'assumed' -- the
    2x2 member's dims are inferred).  Downlight (the 'Chicago plenum
    recessed light' archetype): the catalog record is honestly all-assumed
    with NULL housing dims -> the factory builds OUR OWN parametric housing
    (aperture / can height as job or default values, flagged 'ours' /
    'given'), never a fabricated manufacturer dimension.
    Photometry (IES) is a URL REFERENCE parameter, never a bundled file.
    """
    k = str(kind).lower()
    if k not in _LUM_KINDS:
        raise FactoryError(f"unknown luminaire kind {kind!r}; known: {sorted(_LUM_KINDS)}")
    cv, cl = _LUM_KINDS[k]
    doc = C.load_line(cv, cl)
    lf = doc.get("line_facts") or {}
    sheet = FactSheet(subject=f"{cv}/{cl} {k} {size}", catalog=f"{cv}/{cl}")
    if "troffer" in k:
        model = "2BLT4-38W" if str(size).replace(" ", "").lower() in ("2x4", "2'x4'") \
            else "2BLT2"
        try:
            variant = C.get_variant(cv, cl, model=model)
        except C.CatalogError as e:
            raise FactoryError(str(e))
        sheet.variant = variant.get("model", model)
        # troffer dims: dims_in.d = LENGTH, .w = WIDTH, .h = housing height
        _fp(sheet, variant, "dims_in.d", "length_in")
        _fp(sheet, variant, "dims_in.w", "width_in")
        _fp(sheet, variant, "dims_in.h", "height_in")
        if None in (sheet.get("length_in"), sheet.get("width_in"), sheet.get("height_in")):
            raise FactoryError(f"{model}: housing dims not fully sourced")
        r = variant.get("ratings") or {}
        w = wattage if wattage is not None else r.get("input_watts")
        lm = lumens if lumens is not None else (r.get("delivered_lumens_nominal")
                                                or r.get("delivered_lumens_listed"))
        ct = cct if cct is not None else r.get("cct_k")
        sheet.set("wattage_w", None if w is None else float(w),
                  kind=("given" if wattage is not None else
                        (C.field_provenance(variant, "ratings.input_watts") or "assumed")),
                  source=sheet.variant)
        sheet.set("lumens_lm", None if lm is None else float(lm),
                  kind=("given" if lumens is not None else
                        (C.field_provenance(variant, "ratings.delivered_lumens_nominal")
                         or "assumed")), source=sheet.variant)
        sheet.set("cct_k", None if ct is None else float(ct),
                  kind=("given" if cct is not None else
                        (C.field_provenance(variant, "ratings.cct_k") or "assumed")),
                  source=sheet.variant)
        cri = r.get("cri")
        if cri is not None:
            sheet.set("cri", int(cri), kind=C.field_provenance(variant, "ratings.cri")
                      or "fact", source=sheet.variant)
        sheet.set("shape", "box", kind="ours", note="rectangular recessed housing")
        sheet.set("manufacturer", "Lithonia Lighting (Acuity Brands)", kind="fact",
                  source=cl)
        sheet.set("model", sheet.variant, kind="fact", source=cl,
                  note="catalog member as the Model parameter VALUE")
    else:
        # downlight archetype -- housing is OURS (record dims are null)
        try:
            variant = C.get_variant(cv, cl, model="LDN6-35/15-CP")
        except C.CatalogError as e:
            raise FactoryError(str(e))
        sheet.variant = variant.get("model", "LDN6")
        r = variant.get("ratings") or {}
        ap = aperture_in if aperture_in is not None else (r.get("aperture_in") or 6)
        hh = housing_height_in if housing_height_in is not None else 7.5
        can_d = float(ap) + 1.5           # OUR housing can outside diameter
        sheet.set("aperture_in", float(ap),
                  kind=("given" if aperture_in is not None else "assumed"),
                  source=sheet.variant,
                  note="nominal aperture (search-summary provenance) -- unverified")
        sheet.set("can_diameter_in", can_d, kind="ours",
                  note="OUR parametric housing can (record housing dims are NULL / "
                       "not sourced -- never a fabricated manufacturer dimension)")
        sheet.set("height_in", float(hh),
                  kind=("given" if housing_height_in is not None else "ours"),
                  note="OUR housing height default; the spec sheet was not read")
        sheet.set("shape", "cylinder", kind="ours",
                  note="polygonal can approximation (true curved B-rep = phase 2)")
        lm = lumens if lumens is not None else r.get("lumens")
        ct = cct if cct is not None else r.get("cct_k")
        sheet.set("wattage_w", None if wattage is None else float(wattage),
                  kind=("given" if wattage is not None else "assumed"),
                  note=("wattage not published on the record" if wattage is None else ""))
        sheet.set("lumens_lm", None if lm is None else float(lm),
                  kind=("given" if lumens is not None else "assumed"),
                  source=sheet.variant)
        sheet.set("cct_k", None if ct is None else float(ct),
                  kind=("given" if cct is not None else "assumed"),
                  source=sheet.variant)
        sheet.set("manufacturer", "Lithonia Lighting (Acuity Brands)", kind="fact",
                  source=cl)
        sheet.set("model", sheet.variant, kind="fact", source=cl,
                  note="catalog member as the Model parameter VALUE")
        sheet.notes.append("Downlight housing dims are NOT sourced (record all-'assumed'); "
                           "the family carries OUR parametric can until a human reads "
                           "the spec sheet.")
    # voltage / photometry (line-level)
    vin = (lf.get("voltage_input_v") or {}).get("value") or []
    if isinstance(voltage, (int, float)):
        sheet.set("voltage_v", float(voltage), kind="given")
    else:
        # '120-277' -> connector rated at the low end (120 V single-phase)
        nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", str(voltage))]
        sheet.set("voltage_v", nums[0] if nums else 120.0, kind="given",
                  note=f"input range {voltage}; connector at the low value")
    if vin:
        sheet.set("voltage_input_range_v", list(vin), kind=(
            (lf.get("voltage_input_v") or {}).get("provenance") or "fact"), source=cl)
    photo = (lf.get("photometry_reference") or {}).get("value")
    src2 = (doc.get("sources") or {}).get("S2") or (doc.get("sources") or {}).get("S1") or {}
    sheet.set("photometry_url", src2.get("url", ""), kind="fact", source=cl,
              note=str(photo or "IES referenced by manufacturer URL, never bundled"))
    if lf.get("plenum_use") is not None:
        pu = lf["plenum_use"]
        sheet.set("plenum_rated", bool(pu.get("value")), kind=pu.get("provenance", "assumed"),
                  source=cl, note=str(pu.get("note", ""))[:160])
    sheet.notes.append("No Weight parameter (not published). No .ies payload "
                       "(URL reference only). No ImposterLight light-source "
                       "element yet (the family-skeleton stream exposes no "
                       "constructor) -- photometrics ride as parameters.")
    return sheet


# ---------------------------------------------------------------------------
# GEOMETRY composition (skeleton doc <- form bundle <- connector)
# ---------------------------------------------------------------------------

def geometry_context(doc: SK.FamilyDoc, *, embedded: bool = False) -> G.FamilyDocContext:
    """The :class:`rvt.famgen.geometry.FamilyDocContext` of a from-scratch
    :class:`FamilyDoc`: forms belong to the doc's self-Family, sketch on the
    doc's Reference Level, and reference the family's own category style
    (-1: our documents carry no object-style copies -- the S0 reduction)."""
    return G.FamilyDocContext(
        family_id=int(doc.self_family.elem_id),
        level_id=int(doc.ref_level.elem_id),
        geometry_style_id=-1,
        curve_style_id=-1,
        solid_control_command=0,
        extra_regen_ids=[],
        embedded=bool(embedded),
    )


def add_box_form(doc: SK.FamilyDoc, width_ft: float, depth_ft: float,
                 height_ft: float, *, base_z_ft: float = 0.0,
                 center: Sequence[float] = (0.0, 0.0),
                 rep: str = G.REP_SOLID) -> G.FormBundle:
    """Author a rectangular BOX form (width x, depth y in plan; height z
    from ``base_z``) into ``doc``: sketch on the Ref. Level datum, four model
    lines, the extrusion + its cached six-face solid (``rep='solid'``) or a
    ``SerializedDummy`` rep (``rep='dummy'``, the regeneration variant).

    The bundle's elements join the document BEFORE ``finalize`` so the
    self-Family owns / indexes them like any skeleton element.
    """
    if doc.finalized:
        raise FactoryError("document is finalized; add forms before finalize")
    ctx = geometry_context(doc)
    fb = G.box(float(width_ft), float(depth_ft), float(height_ft), ctx, doc.ids,
               base_z_ft=float(base_z_ft), center=tuple(center), rep=rep)
    doc.add(*fb.elements)
    return fb


def box_face(face: str) -> Dict[str, Any]:
    """The geometry-history TAG + edge-loop tags of a named face of the box
    template (rvt.famgen.geometry): 'top' = the start cap (z = base+height),
    'bottom' = the end cap (z = base), '+y' / '-x' / '-y' / '+x' = the four
    side faces (profile V0(+x,+y) -> V1(-x,+y) -> V2(-x,-y) -> V3(+x,-y):
    side_0 = the +y face, side_1 = -x, side_2 = -y, side_3 = +x).

    A connector's ``m_geomRef.m_geomTag`` = the face TAG and its
    ``EdgeLoopRef.m_sortedTagArr`` = the sorted edge tags of that face
    [VERIFIED: the panelboard specimen's connector sits on side_0 = tag 2
    with edge tags [3, 4, 8, 17]].
    """
    t = G._box_tags(4)
    n = 4

    def lat_at_vertex(j: int) -> int:
        return t["lateral"][n - 1] if j == 0 else t["lateral"][j - 1]

    if face in ("top", "start"):
        return {"tag": t["start_face"], "edges": sorted(t["rail_start"]),
                "normal": (0.0, 0.0, 1.0)}
    if face in ("bottom", "end"):
        return {"tag": t["end_face"], "edges": sorted(t["rail_end"]),
                "normal": (0.0, 0.0, -1.0)}
    sides = {"+y": 0, "-x": 1, "-y": 2, "+x": 3}
    if face not in sides:
        raise KeyError(f"unknown box face {face!r}: top/bottom/+y/-x/-y/+x")
    i = sides[face]
    edges = sorted([t["rail_start"][i], t["rail_end"][i],
                    lat_at_vertex(i), lat_at_vertex((i + 1) % n)])
    normals = {"+y": (0.0, 1.0, 0.0), "-x": (-1.0, 0.0, 0.0),
               "-y": (0.0, -1.0, 0.0), "+x": (1.0, 0.0, 0.0)}
    return {"tag": t["face"][i], "edges": edges, "normal": normals[face]}


def add_connector(doc: SK.FamilyDoc, *, host: G.FormBundle, face: str,
                  location: Sequence[float], direction: Sequence[float],
                  u_axis: Sequence[float], voltage_v: float, poles: int,
                  apparent_load_va: Union[float, Sequence[float]] = 0.0,
                  power_factor: float = 1.0,
                  bind_voltage_param: Optional[str] = None,
                  bind_load_param: Optional[str] = None,
                  load_class: str = "Power",
                  description: str = "Power Connection",
                  primary: Optional[bool] = None) -> SK.SkelElement:
    """Add a POWER connector hosted on a named FACE of ``host`` (a box form
    bundle): the connector references the extrusion's face by geometry tag
    (:func:`box_face`) and carries the face's edge-loop tags -- the same
    face-referencing every real MEP family connector uses [V], instead of
    the datum-plane host the S0e skeleton probe had to fall back on.

    ``bind_voltage_param`` / ``bind_load_param`` = captions of the doc's
    family parameters to ASSOCIATE with the connector's voltage / apparent
    load (the type value drives the connector) [V mechanism].
    ``apparent_load_va`` (a total split over the poles, or a per-phase list)
    and ``primary`` (``None`` = only the family's first connector is; a
    second primary raises): laws in ``SK.electrical_domain`` /
    ``SK.FamilyDoc.resolve_primary``.
    """
    if doc.finalized:
        raise FactoryError("document is finalized; add connectors before finalize")
    try:
        primary = doc.resolve_primary(primary)
    except ValueError as e:
        raise FactoryError(str(e)) from None
    ext = host.by_class("ExtrusionElem")
    if not ext:
        raise FactoryError("host form has no ExtrusionElem")
    if len(host.params.get("vertices") or ()) != 4:
        # box_face() speaks _box_tags(4): a straight 4-curve prism_form bundle
        # (box / plate / polygon_cylinder).  A two-arc G.cylinder has another
        # cap/edge tag map -- refuse it loudly rather than mis-tag the connector.
        raise FactoryError(f"host form {host.kind!r} is not a 4-curve prism; "
                           "box_face tags would not address its faces")
    fx = box_face(face)
    lc = next((l for l in doc.load_classes
               if l.obj.get("m_name") == load_class or
               (l.obj.get("m_symbolInfo") or {}).get("value", {}).get("m_name") == load_class),
              None)
    if lc is None:
        lc = doc.add_load_classification(load_class)
    bindings: List[Tuple[int, int]] = []
    if bind_voltage_param:
        bindings.append((doc._param_key(bind_voltage_param), SK.ELEM_PROP_VOLTAGE))
    if bind_load_param:
        bindings.append((doc._param_key(bind_load_param), SK.ELEM_PROP_APPARENT_LOAD))
    con = SK.new_electrical_connector(
        SK._alloc(doc.ids), doc.self_family.elem_id,
        host_element_id=ext[0].elem_id, host_geom_tag=int(fx["tag"]),
        location=tuple(float(c) for c in location),
        direction=tuple(float(c) for c in direction),
        u_axis=tuple(float(c) for c in u_axis),
        voltage_v=float(voltage_v), poles=int(poles),
        load_class_id=lc.elem_id, apparent_load_va=apparent_load_va,
        power_factor=float(power_factor), description=str(description),
        primary=primary,
        edge_loop_tags=list(fx["edges"]), param_bindings=bindings,
        index=len(doc.connectors) + 1)
    con.notes.append(f"hosted on the enclosure's {face} face (tag {fx['tag']}, "
                     f"edge tags {fx['edges']})")
    doc.connectors.append(con)
    doc.add(con)
    return con


# ---------------------------------------------------------------------------
# the FamilyProduct (a generated family, ready to write)
# ---------------------------------------------------------------------------

@dataclass
class TypeRow:
    """One family TYPE of a product: its name, the fact sheet it was resolved
    from, and the engineering values written to its type-table row as
    ``(parameter caption, SPEC key, value)`` -- the same facts a Revit type
    catalog row carries (lengths in inches, ratings raw)."""
    name: str
    facts: FactSheet
    catalog: List[Tuple[str, str, Any]] = dc_field(default_factory=list)

    def as_json(self) -> dict:
        return {"name": self.name, "subject": self.facts.subject,
                "variant": self.facts.variant,
                "assumed_fields": self.facts.assumed(),
                "unverified_fields": self.facts.unverified(),
                "values": {cap: val for cap, _s, val in self.catalog}}


@dataclass
class FamilyProduct:
    """A generated family: the finalized document + its fact sheet(s).

    ``facts`` = the PRIMARY type's sheet (the type whose dimensions the one
    authored solid is built at); ``types`` = one :class:`TypeRow` per
    family type in type-table order (a single entry unless ``types=`` named
    several catalog selections)."""
    kind: str                              # 'panelboard' | 'transformer' | 'luminaire'
    doc: SK.FamilyDoc
    facts: FactSheet
    forms: List[G.FormBundle] = dc_field(default_factory=list)
    file_stem: str = "family"
    notes: List[str] = dc_field(default_factory=list)
    types: List[TypeRow] = dc_field(default_factory=list)
    type_catalog: Optional[Dict[str, Any]] = None      # set by write_type_catalog()

    @property
    def name(self) -> str:
        return self.doc.name

    def _sheets(self) -> List[FactSheet]:
        return [t.facts for t in self.types] or [self.facts]

    def assumed(self) -> List[str]:
        """Assumed fields of ANY type (nothing unverified hides in a row)."""
        return sorted({k for s in self._sheets() for k in s.assumed()})

    def unverified(self) -> List[str]:
        return sorted({k for s in self._sheets() for k in s.unverified()})

    def shared_parameters(self) -> Dict[str, str]:
        """{caption: GUID} of the parameters authored SHARED (file GUIDs)."""
        return {n: pe.refs["guid"] for n, pe in sorted(self.doc.params.items())
                if pe.class_name == "ParamElemExternal"}

    def summary(self) -> Dict[str, Any]:
        pes = self.doc.params
        summ = {
            "kind": self.kind, "family_name": self.doc.name,
            "category": SK.category_label(self.doc.category_id),
            "part_type": self.doc.part_type,
            "elements": len(self.doc.elements),
            "types": [n for n, _v in self.doc.types],
            "parameters": sorted(pes),
            "shared_parameters": self.shared_parameters(),
            "forms": [{"kind": f.kind, **{k: v for k, v in f.params.items()
                                          if k in ("width_ft", "depth_ft", "height_ft",
                                                   "base_z_ft", "rep")}}
                      for f in self.forms],
            "connectors": len(self.doc.connectors),
            "assumed_fields": self.assumed(),
            "unverified_fields": self.unverified(),
            "type_facts": [t.as_json() for t in self.types],
            "notes": list(self.notes),
        }
        if self.type_catalog:
            summ["type_catalog"] = dict(self.type_catalog)
        return summ

    def write_type_catalog(self, rfa_path: str) -> Dict[str, Any]:
        """Write OUR Revit type catalog ``<stem>.txt`` beside ``rfa_path``
        (Revit pairs the two by file name) and remember it, so a following
        :meth:`write` records it in the report's ``family.type_catalog``."""
        self.type_catalog = write_type_catalog(self, os.path.splitext(rfa_path)[0] + ".txt")
        return self.type_catalog

    def write(self, path: str, *, validate: bool = True, provenance: bool = True,
              timestamp: Optional[int] = 0, report_path: Optional[str] = None
              ) -> Dict[str, Any]:
        """Emit the standalone ``.rfa`` at ``path`` from BUNDLED assets
        (container source = the certified genesis base; a user-supplied
        ``$RVT_FAMILY_DONOR`` .rfa is the hidden escape hatch), then verify,
        family-mode-validate and provenance-scan it."""
        from rvt.frontdoor.standalone import standalone_family_write
        return standalone_family_write(
            self, path, validate=validate, provenance=provenance,
            timestamp=timestamp, report_path=report_path,
            family_donor=os.environ.get("RVT_FAMILY_DONOR"))


# ---------------------------------------------------------------------------
# family assembly helpers shared by the three product constructors
# ---------------------------------------------------------------------------

def _text(doc: SK.FamilyDoc, name: str, group: str = "identity") -> SK.SkelElement:
    return doc.add_family_parameter(name, SPEC["text"], GROUP[group])


def _num(doc: SK.FamilyDoc, name: str, spec: str, group: str) -> SK.SkelElement:
    return doc.add_family_parameter(name, SPEC[spec], GROUP[group])


def _clean_name(*parts: Any) -> str:
    return " ".join(str(p) for p in parts if str(p))


# ---------------------------------------------------------------------------
# TYPES -- one family, N catalog selections (type-table rows)
# ---------------------------------------------------------------------------

def _number(v: Any) -> float:
    """'225' / '225A' / '45 kVA' / 38 -> the leading number."""
    if isinstance(v, (int, float)):
        return float(v)
    m = re.match(r"^\s*(\d+(?:\.\d+)?)", str(v))
    if not m:
        raise FactoryError(f"type selector {v!r} is not a number (e.g. 225, '400A', '75kVA')")
    return float(m.group(1))


def _type_jobs(types: Optional[Sequence[Any]], primary: Dict[str, Any], *,
               scalar_key: str) -> List[Dict[str, Any]]:
    """Normalise ``types=`` into one job dict per family TYPE.

    ``types`` is a list of CATALOG SELECTORS: a bare number / '225A'-style
    string selects along the product's rating axis (``scalar_key``: mains
    amps, kVA, watts); a dict overrides any of ``primary``'s per-type keys
    (e.g. ``{'mains_a': 225, 'mcb': False}``) and may name the row
    explicitly (``'type_name'``).  ``None`` / empty = the one type
    ``primary`` describes (the historical single-type family, row for row).
    The FIRST job is the primary type: the one authored solid is built at
    its dimensions.
    """
    if not types:
        return [dict(primary)]
    jobs: List[Dict[str, Any]] = []
    for sel in types:
        job = dict(primary)
        if isinstance(sel, dict):
            unknown = sorted(set(sel) - set(primary) - {"type_name"})
            if unknown:
                raise FactoryError(f"type selector keys {unknown} are not per-type "
                                   f"fields of this product (per-type: {sorted(primary)})")
            job.update(sel)
        else:
            job[scalar_key] = _number(sel)
        jobs.append(job)
    return jobs


def _joined(values: Sequence[Any], suffix: str = "") -> str:
    """'400A' for one distinct value, '225-400-600A' for several (order kept)."""
    seen: List[str] = []
    for v in values:
        s = f"{v:g}" if isinstance(v, float) else str(v)
        if s not in seen:
            seen.append(s)
    return ("-".join(seen) + suffix) if seen else ""


def _common(values: Sequence[Any]) -> str:
    """The value every type shares, else '' (dropped from the family NAME)."""
    vals = {str(v) for v in values}
    return str(values[0]) if len(vals) == 1 else ""


#: engineering value -> internal units, per SPEC key (else the value as is)
_TO_INTERNAL = {"length": inches, "voltage": SK.volts,
                "apparent_power": SK.voltamps, "wattage": SK.watts}


def _add_type_row(doc: SK.FamilyDoc, rows: List[TypeRow], name: str, facts: FactSheet,
                  entries: Sequence[Tuple[str, str, Any]], description: str) -> None:
    """Add ONE type: ``entries`` = ``(parameter caption, SPEC key, engineering
    value)`` -- the single source of both the type-table row (converted to
    internal units, keyed by the doc's parameters) and the type-catalog row;
    Manufacturer / Model come from ``facts``, ``description`` is row-only."""
    if any(r.name == name for r in rows):
        raise FactoryError(f"two type selections resolve to the same type name {name!r}: "
                           "make the selectors distinct (rating / configuration)")
    values: Dict[Any, Any] = {doc.params[cap].elem_id: _TO_INTERNAL.get(spec, lambda v: v)(val)
                              for cap, spec, val in entries}
    values.update({"manufacturer": str(facts.get("manufacturer")),
                   "model": str(facts.get("model")), "description": description})
    doc.add_type(name, values)
    rows.append(TypeRow(name=name, facts=facts, catalog=list(entries) + [
        ("Manufacturer", "text", str(facts.get("manufacturer"))),
        ("Model", "text", str(facts.get("model")))]))


#: Revit type-catalog column declarations ``<param>##<SPEC>##<UNITS>`` per
#: factory SPEC key (the documented catalog vocabulary; lengths are written
#: in inches, electrical ratings in their engineering units, text/counts as
#: OTHER).  The catalog is OURS: one row per type from the same facts the
#: type table carries -- never a copied manufacturer catalog file.
TYPE_CATALOG_COLUMNS = {
    "length": ("LENGTH", "INCHES"),
    "voltage": ("ELECTRICAL_POTENTIAL", "VOLTS"),
    "current": ("ELECTRICAL_CURRENT", "AMPERES"),
    "apparent_power": ("ELECTRICAL_APPARENT_POWER", "VOLT_AMPERES"),
    "wattage": ("ELECTRICAL_WATTAGE", "WATTS"),
    "luminous_flux": ("ELECTRICAL_LUMINOUS_FLUX", "LUMENS"),
    "cct": ("COLOR_TEMPERATURE", "KELVIN"),
    "number": ("OTHER", ""),
    "integer": ("OTHER", ""),
    "text": ("OTHER", ""),
}


def _catalog_cell(v: Any) -> str:
    """A catalog cell: floats without trailing zeros, bools as 1/0, None
    empty (quoting of commas / quotes is the csv writer's job)."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, float):
        return f"{v:.6f}".rstrip("0").rstrip(".") or "0"
    return str(v)


def _catalog_columns(product: "FamilyProduct") -> List[Tuple[str, str]]:
    """(caption, SPEC key) columns = the union of the types' entries, first-seen order."""
    if not product.types:
        raise FactoryError("product carries no type rows to catalogue")
    cols: List[Tuple[str, str]] = []
    for r in product.types:
        for cap, spec, _v in r.catalog:
            if (cap, spec) not in cols:
                cols.append((cap, spec))
    return cols


def _catalog_header(cols: Sequence[Tuple[str, str]]) -> List[str]:
    return ["{}##{}##{}".format(cap, *TYPE_CATALOG_COLUMNS.get(spec, ("OTHER", "")))
            for cap, spec in cols]


def type_catalog_text(product: "FamilyProduct") -> str:
    """OUR Revit type catalog for ``product``: the header row
    ``,<param>##<SPEC>##<UNITS>,...`` then one ``<type name>,<values>`` row
    per type.  Pure ASCII/UTF-8 text authored from the fact sheets."""
    cols = _catalog_columns(product)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow([""] + _catalog_header(cols))
    for r in product.types:
        vals = {(cap, spec): v for cap, spec, v in r.catalog}
        w.writerow([_catalog_cell(r.name)] + [_catalog_cell(vals.get(c)) for c in cols])
    return buf.getvalue()


def write_type_catalog(product: "FamilyProduct", path: str) -> Dict[str, Any]:
    """Write :func:`type_catalog_text` to ``path``; returns a small report."""
    text = type_catalog_text(product)
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    return {"path": path, "types": [t.name for t in product.types],
            "columns": _catalog_header(_catalog_columns(product)),
            "bytes": len(text.encode("utf-8"))}


# ---------------------------------------------------------------------------
# PRODUCT 1 -- PANELBOARD
# ---------------------------------------------------------------------------

def make_panelboard(*, vendor: str = "eaton", line: str = "pow-r-line",
                    mains_a: float = 400, spaces: int = 42,
                    voltage: Any = "480Y/277", mcb: bool = True,
                    mounting: str = "surface", panel_name: str = "PANEL",
                    sccr_ka: Optional[float] = None,
                    neutral_rating: str = "100%",
                    solid: bool = True, name: Optional[str] = None,
                    start_id: int = 1000,
                    types: Optional[Sequence[Any]] = None,
                    shared_params: SK.SharedParamsArg = None) -> FamilyProduct:
    """Compose a PANELBOARD family from catalog facts.

    Geometry: the enclosure box at TRUE catalog dimensions (width x height
    in the family's XY plane = the wall face for a work-plane-based /
    face-hosted family, depth extruded +Z out of the face for SURFACE
    mounting, or recessed -Z for FLUSH).  One 3-pole power connector on the
    enclosure's top face (the specimen's convention: feeder entry on top),
    voltage associated to the ``Voltage`` family parameter.

    Parameters: the tekton-ifc tagging-contract NAMES (PanelName,
    Voltage, Phases, Wires, BusRating, MainsType, MainsRating,
    ShortCircuitRatingkA, Mounting, NumberOfCircuits, NeutralRating) plus
    Width / Height / Depth and the identity built-ins (Manufacturer, Model,
    Description) -- the manufacturer FACTS as parameter values.

    ``types`` = catalog selectors for a MULTI-TYPE family (one product line,
    a type per rating): mains ratings (``[225, 400, 600]`` / ``'225A'``) or
    dicts over the per-type fields ``mains_a, spaces, mcb, sccr_ka,
    neutral_rating``.  Each selection resolves its own fact sheet and
    becomes one type-table row carrying ITS dims / ratings / Model; the
    first is the primary type (the solid is built at its box).  ``None`` =
    the single type ``mains_a``/``spaces``/``mcb`` describe.

    ``shared_params`` = OUR shared-parameter file (path or parsed rows):
    every parameter it names is authored SHARED at the file's GUID (the
    eleven contract parameters for :data:`DEFAULT_SHARED_PARAMS`), the rest
    stay local; ``None`` = every parameter local (the historical shape).
    """
    jobs = _type_jobs(types, {"mains_a": mains_a, "spaces": spaces, "mcb": mcb,
                              "sccr_ka": sccr_ka, "neutral_rating": neutral_rating},
                      scalar_key="mains_a")
    sheets = [resolve_panelboard_facts(vendor, line, mains_a=float(j["mains_a"]),
                                       spaces=int(j["spaces"]), voltage=voltage,
                                       mcb=bool(j["mcb"]), mounting=mounting,
                                       sccr_ka=j["sccr_ka"], panel_name=panel_name,
                                       neutral_rating=j["neutral_rating"])
              for j in jobs]
    facts = sheets[0]                                   # the primary type
    mains_a, spaces, mcb = float(jobs[0]["mains_a"]), int(jobs[0]["spaces"]), bool(jobs[0]["mcb"])
    W = inches(facts.get("width_in"))
    H = inches(facts.get("height_in"))
    D = inches(facts.get("depth_in"))
    vll = float(facts.get("voltage_ll_v"))
    mount = str(facts.get("mounting")).lower()
    fam_name = name or _clean_name(
        "Panelboard", facts.get("voltage_system"),
        _common([f"{int(j['mains_a'])}A" for j in jobs]),
        _common([s.get("mains_type") for s in sheets]),
        _common([f"{int(j['spaces'])}ckt" for j in jobs]), mount.title())
    doc = SK.new_family_document("electrical_equipment", fam_name,
                                 part_type=SK.PART_TYPE["panelboard"],
                                 work_plane_based=True, start_id=start_id,
                                 plane_length_ft=max(6.0, H * 1.5),
                                 shared_params=shared_params)
    doc.notes.append("panelboard: work-plane-based (face-hosted like every rme "
                     "panelboard); enclosure box in the family XY = the host face")
    # -- parameters: dimensions ------------------------------------------
    for dim in ("Width", "Height", "Depth"):
        _num(doc, dim, "length", "dimensions")
    # -- parameters: the tagging contract (same NAMES -> schedules bind; the
    #    same GUIDs too under ``shared_params``) ------------------------------
    for pname, spec_k, group_k in PANEL_CONTRACT_PARAMS:
        doc.add_family_parameter(pname, SPEC[spec_k], GROUP[group_k])
    # -- the type(s): facts as parameter VALUES ------------------------------
    rows: List[TypeRow] = []
    for job, fx in zip(jobs, sheets):
        j_mains, j_spaces, j_mcb = float(job["mains_a"]), int(job["spaces"]), bool(job["mcb"])
        mains_type = fx.get("mains_type")
        type_name = job.get("type_name") or _clean_name(
            f"{int(j_mains)}A", mains_type, f"{j_spaces}ckt")
        sccr = fx.get("sccr_ka")
        _add_type_row(doc, rows, type_name, fx, [
            ("Width", "length", fx.get("width_in")), ("Height", "length", fx.get("height_in")),
            ("Depth", "length", fx.get("depth_in")),
            ("PanelName", "text", str(fx.get("panel_name"))),
            ("Voltage", "voltage", vll), ("Phases", "integer", int(fx.get("phases"))),
            ("Wires", "integer", int(fx.get("wires"))),
            ("BusRating", "current", float(fx.get("bus_rating_a"))),
            ("MainsType", "text", str(mains_type)),
            ("MainsRating", "current", float(fx.get("mains_rating_a"))),
            ("ShortCircuitRatingkA", "number", float(sccr) if sccr is not None else 0.0),
            ("Mounting", "text", str(mount)), ("NumberOfCircuits", "integer", j_spaces),
            ("NeutralRating", "text", str(fx.get("neutral_rating"))),
        ], description=(
            f"{fx.get('voltage_system')} V, {int(fx.get('phases'))}-phase "
            f"{int(fx.get('wires'))}-wire, {int(j_mains)} A "
            f"{'main-breaker' if j_mcb else 'main-lugs-only'} panelboard, "
            f"{j_spaces} circuits, {mount} mounted "
            f"(box {fx.get('width_in'):g} W x {fx.get('height_in'):g} H x "
            f"{fx.get('depth_in'):g} D in; generated from catalog facts)"))
    # -- geometry: the enclosure box -------------------------------------
    # profile W (x) x H (y) in the family plane (the wall face); depth along
    # +Z for surface mounting, recessed (-Z) for flush.
    if mount.startswith("flush"):
        base_z, height = -D, D          # box behind the face (z -D..0)
    else:
        base_z, height = 0.0, D         # box proud of the face (z 0..D)
    fb = add_box_form(doc, W, H, height, base_z_ft=base_z, center=(0.0, 0.0),
                      rep=G.REP_SOLID if solid else G.REP_DUMMY)
    fb.params.update({"role": "panelboard enclosure",
                      "dims_in": [facts.get("width_in"), facts.get("height_in"),
                                  facts.get("depth_in")],
                      "mounting": mount})
    # -- connector: 3-pole power feed, top face centre (specimen convention)
    poles = 3 if int(facts.get("phases")) >= 3 else 1
    add_connector(doc, host=fb, face="+y",
                  location=(0.0, H / 2.0, base_z + height / 2.0),
                  direction=(0.0, 0.0, -1.0), u_axis=(0.0, 1.0, 0.0),
                  voltage_v=vll, poles=poles, apparent_load_va=0.0,
                  power_factor=1.0, bind_voltage_param="Voltage",
                  load_class="Power", description="Panel Feed")
    doc.finalize()
    prod = FamilyProduct("panelboard", doc, facts, forms=[fb], types=rows,
                         file_stem=_slug(f"{vendor}_{facts.variant}_"
                                         f"{_joined([int(j['mains_a']) for j in jobs], 'A')}_"
                                         f"{_joined([int(j['spaces']) for j in jobs], 'sp')}_"
                                         f"{facts.get('voltage_system')}"))
    prod.notes.append("connector hosted on the enclosure's top face (face-referenced, "
                      "edge-loop tags of the solid) -- resolves the S0e datum-host gap")
    _multi_type_notes(prod, label="UNVERIFIED (assumed) values surfaced: ")
    return prod


def _multi_type_notes(prod: FamilyProduct, label: str = "UNVERIFIED (assumed): ") -> None:
    """Surface the assumed fields (of every type) under ``label``; for a
    multi-type family, say out loud that the ONE solid sits at the primary
    type's dimensions while the other rows carry theirs as parameter VALUES;
    and name the parameters authored SHARED (file GUIDs) if any."""
    assumed = prod.assumed()
    if assumed:
        prod.notes.append(label + ", ".join(assumed))
    shared = prod.shared_parameters()
    if shared:
        prod.notes.append(
            f"{len(shared)} SHARED parameters (ParamElemExternal, GUIDs verbatim from OUR "
            f"shared-parameter file): {', '.join(shared)} -- a schedule / tag keyed on "
            f"those GUIDs binds after load; every other parameter is local "
            f"[family-side shared definitions are UNCERTIFIED: no loads claim]")
    if len(prod.types) > 1:
        prod.notes.append(
            f"{len(prod.types)} types {[t.name for t in prod.types]}: ONE family, one "
            f"type-table row per catalog selection (per-type dims / ratings / Model as "
            f"parameter VALUES); the enclosure solid and connector are authored ONCE at "
            f"the primary type's ({prod.types[0].name}) dimensions -- geometry is not "
            f"label-driven yet (asset-factory honest limit #4)")


# ---------------------------------------------------------------------------
# PRODUCT 2 -- DRY-TYPE TRANSFORMER
# ---------------------------------------------------------------------------

def make_transformer(*, kva: float = 75, vendor: str = "eaton",
                     primary_v: Any = 480, secondary_v: Any = "208Y/120",
                     solid: bool = True, name: Optional[str] = None,
                     start_id: int = 1000,
                     types: Optional[Sequence[Any]] = None,
                     shared_params: SK.SharedParamsArg = None) -> FamilyProduct:
    """Compose a DRY-TYPE TRANSFORMER family from catalog facts: the
    enclosure box at the catalog W x D footprint x H tall standing on the
    Reference Level (free-standing, floor-mounted), with TWO 3-pole power
    connectors on the top face: PRIMARY (480 V) and SECONDARY (208 V), the
    secondary being what feeds a downstream panel (KNOWLEDGE: transformer
    secondary -> panel circuit membership).

    ``types`` = kVA points (``[30, 45, 75]`` / ``'45kVA'`` / ``{'kva': 45}``)
    for a MULTI-TYPE family: one row per rating with its own frame / dims /
    weight / Model; the first is the primary type (the solid is its box).
    ``shared_params`` as :func:`make_panelboard` (caption + datatype match a
    file row -> SHARED at the file's GUID; else local)."""
    jobs = _type_jobs(types, {"kva": kva}, scalar_key="kva")
    sheets = [resolve_transformer_facts(float(j["kva"]), vendor=vendor, primary_v=primary_v,
                                        secondary_v=secondary_v) for j in jobs]
    facts = sheets[0]                                   # the primary type
    kva = jobs[0]["kva"]
    W = inches(facts.get("width_in"))
    Hh = inches(facts.get("height_in"))
    D = inches(facts.get("depth_in"))
    vp, _p_ph, _p_w = _voltage_number(primary_v)
    vs, _s_ph, _s_w = _voltage_number(secondary_v)
    fam_name = name or _clean_name("Dry Type Transformer",
                                   _common([f"{float(j['kva']):g}kVA" for j in jobs]),
                                   f"{int(vp)}-{secondary_v}")
    doc = SK.new_family_document("electrical_equipment", fam_name,
                                 part_type=SK.PART_TYPE["electrical_equipment"],
                                 work_plane_based=False, start_id=start_id,
                                 plane_length_ft=max(6.0, W * 2.0),
                                 shared_params=shared_params)
    doc.notes.append("transformer: free-standing (floor); part type 15 = the rme "
                     "dry-type transformer's own part type [V value]")
    for dim in ("Width", "Height", "Depth"):
        _num(doc, dim, "length", "dimensions")
    _num(doc, "kVA Rating", "apparent_power", "electrical")
    _num(doc, "Primary Voltage", "voltage", "electrical")
    _num(doc, "Secondary Voltage", "voltage", "electrical")
    _num(doc, "Phases", "integer", "electrical")
    _num(doc, "Temperature Rise", "number", "electrical")
    has_weight = any(fx.get("weight_lb") for fx in sheets)
    if has_weight:
        _num(doc, "Weight", "number", "identity")
    _text(doc, "Frame")
    _text(doc, "Enclosure")
    rows: List[TypeRow] = []
    for job, fx in zip(jobs, sheets):
        j_kva = float(job["kva"])
        type_name = job.get("type_name") or _clean_name(f"{j_kva:g} kVA",
                                                        f"{int(vp)}-{secondary_v}")
        _add_type_row(doc, rows, type_name, fx, [
            ("Width", "length", fx.get("width_in")), ("Height", "length", fx.get("height_in")),
            ("Depth", "length", fx.get("depth_in")),
            ("kVA Rating", "apparent_power", j_kva * 1000.0),
            ("Primary Voltage", "voltage", vp), ("Secondary Voltage", "voltage", vs),
            ("Phases", "integer", int(fx.get("phases") or 3)),
            ("Temperature Rise", "number", float(fx.get("temp_rise_c") or 0.0)),
        ] + ([("Weight", "number", float(fx.get("weight_lb") or 0.0))] if has_weight else []) + [
            ("Frame", "text", str(fx.get("frame") or "")),
            ("Enclosure", "text", str(fx.get("enclosure") or "")),
        ], description=(
            f"{j_kva:g} kVA, {int(fx.get('phases') or 3)}-phase, "
            f"{primary_v} - {secondary_v} V dry-type transformer, "
            f"{fx.get('temp_rise_c') or '?'} C rise, "
            f"{fx.get('windings') or 'aluminum'} windings, "
            f"frame {fx.get('frame') or '?'} "
            f"({fx.get('width_in'):g} W x {fx.get('height_in'):g} H x "
            f"{fx.get('depth_in'):g} D in, {fx.get('weight_lb') or '?'} lb; "
            f"generated from catalog facts)"))
    # geometry: W (x) x D (y) footprint, H tall from the floor
    fb = add_box_form(doc, W, D, Hh, base_z_ft=0.0, center=(0.0, 0.0),
                      rep=G.REP_SOLID if solid else G.REP_DUMMY)
    fb.params.update({"role": "transformer enclosure",
                      "dims_in": [facts.get("width_in"), facts.get("depth_in"),
                                  facts.get("height_in")]})
    # connectors: primary + secondary windings on the top face, offset in X.
    # The primary winding is the family's ONE primary connector (the side an
    # upstream circuit attaches to); the secondary books the kVA rating as a
    # balanced 3-pole load = an equal per-phase split (SK.electrical_domain)
    add_connector(doc, host=fb, face="top",
                  location=(-W / 4.0, 0.0, Hh), direction=(0.0, 0.0, 1.0),
                  u_axis=(1.0, 0.0, 0.0), voltage_v=vp, poles=3,
                  apparent_load_va=0.0, bind_voltage_param="Primary Voltage",
                  load_class="Power", description="Primary", primary=True)
    add_connector(doc, host=fb, face="top",
                  location=(W / 4.0, 0.0, Hh), direction=(0.0, 0.0, 1.0),
                  u_axis=(1.0, 0.0, 0.0), voltage_v=vs, poles=3,
                  apparent_load_va=float(kva) * 1000.0,
                  bind_voltage_param="Secondary Voltage",
                  bind_load_param="kVA Rating",
                  load_class="Power", description="Secondary", primary=False)
    doc.finalize()
    prod = FamilyProduct("transformer", doc, facts, forms=[fb], types=rows,
                         file_stem=_slug(f"xfmr_{_joined([float(j['kva']) for j in jobs], 'kVA')}"
                                         f"_{int(vp)}-{secondary_v}"))
    prod.notes.append("two connectors on the top face: the primary winding is the "
                      "family's primary connector; the secondary is bound to the kVA "
                      "rating and books it as an equal per-phase (balanced) load")
    _multi_type_notes(prod)
    return prod


# ---------------------------------------------------------------------------
# PRODUCT 3 -- LUMINAIRE
# ---------------------------------------------------------------------------

def make_luminaire(*, kind: str = "recessed-troffer", size: str = "2x4",
                   wattage: Optional[float] = None, lumens: Optional[float] = None,
                   cct: Optional[float] = None, voltage: Any = "120-277",
                   aperture_in: Optional[float] = None,
                   solid: bool = True, name: Optional[str] = None,
                   start_id: int = 1000,
                   types: Optional[Sequence[Any]] = None,
                   shared_params: SK.SharedParamsArg = None) -> FamilyProduct:
    """Compose a LUMINAIRE family: a recessed TROFFER (rectangular housing at
    the catalog dimensions) or a recessed DOWNLIGHT (OUR parametric can --
    the flagship record's housing dims are not sourced).  One single-phase
    power connector on the housing top, load = the wattage (associated to
    the Wattage parameter); photometry = parameters + an IES URL reference
    (no bundled .ies).  No ImposterLight light-source element yet (honest
    limit -- the skeleton exposes no constructor).

    ``types`` = wattage / lumen packages for a MULTI-TYPE family: watts
    (``[30, 38, 48]`` / ``'38W'``) or dicts over ``wattage, lumens, cct,
    size, aperture_in``; one row per package, the first = the primary type
    (the housing solid is built at its dimensions).  ``shared_params`` as
    :func:`make_panelboard`."""
    jobs = _type_jobs(types, {"wattage": wattage, "lumens": lumens, "cct": cct,
                              "size": size, "aperture_in": aperture_in},
                      scalar_key="wattage")
    sheets = [resolve_luminaire_facts(kind, size=j["size"], wattage=j["wattage"],
                                      lumens=j["lumens"], cct=j["cct"], voltage=voltage,
                                      aperture_in=j["aperture_in"]) for j in jobs]
    facts = sheets[0]                                   # the primary type
    size = jobs[0]["size"]
    shape = facts.get("shape")
    volt = float(facts.get("voltage_v") or 120.0)
    watt = facts.get("wattage_w")
    watts_all = [fx.get("wattage_w") for fx in sheets]
    fam_name = name or (_clean_name("Recessed Troffer", _common([j["size"] for j in jobs]),
                                    _common([f"{w:g}W" if w else "" for w in watts_all]))
                        if shape == "box" else
                        _clean_name("Recessed Downlight",
                                    _common([f"{fx.get('aperture_in'):g}in aperture"
                                             for fx in sheets])))
    doc = SK.new_family_document("lighting_fixture", fam_name,
                                 part_type=SK.PART_TYPE["normal"],
                                 work_plane_based=True, start_id=start_id,
                                 plane_length_ft=6.0, shared_params=shared_params)
    doc.notes.append("luminaire: work-plane-based (ceiling face); NO ImposterLight "
                     "light-source element (skeleton exposes no constructor) -- "
                     "photometrics ride as parameters; IES = URL reference only")
    # parameters
    _num(doc, "Wattage", "wattage", "electrical")
    _num(doc, "Lumens", "luminous_flux", "photometrics")
    _num(doc, "Color Temperature", "cct", "photometrics")
    _num(doc, "Voltage", "voltage", "electrical")
    _text(doc, "IES File (URL reference)", "photometrics")
    if shape == "box":
        dims = (("Length", "length_in"), ("Width", "width_in"), ("Height", "height_in"))
        L = inches(facts.get("length_in")); Wd = inches(facts.get("width_in"))
    else:
        dims = (("Aperture Diameter", "aperture_in"), ("Housing Diameter", "can_diameter_in"),
                ("Height", "height_in"))
        L = inches(facts.get("can_diameter_in")); Wd = L
    Hh = inches(facts.get("height_in"))
    for caption, _key in dims:
        _num(doc, caption, "length", "dimensions")
    rows: List[TypeRow] = []
    for job, fx in zip(jobs, sheets):
        j_size, j_watt = job["size"], fx.get("wattage_w")
        if fx.get("shape") != shape:                       # pragma: no cover
            raise FactoryError("every type of one luminaire family shares its housing shape")
        type_name = job.get("type_name") or _clean_name(
            j_size if shape == "box" else f"{fx.get('aperture_in'):g}in",
            f"{j_watt:g}W" if j_watt else "",
            f"{int(fx.get('cct_k'))}K" if fx.get("cct_k") else "")
        _add_type_row(doc, rows, type_name, fx, [
            ("Wattage", "wattage", float(j_watt) if j_watt else 0.0),
            ("Lumens", "luminous_flux", float(fx.get("lumens_lm") or 0.0)),
            ("Color Temperature", "cct", float(fx.get("cct_k") or 0.0)),
            ("Voltage", "voltage", volt),
            ("IES File (URL reference)", "text", str(fx.get("photometry_url") or "")),
        ] + [(caption, "length", fx.get(key)) for caption, key in dims], description=(
            (f"Recessed LED troffer {j_size}, {j_watt:g} W, {fx.get('lumens_lm'):g} lm, "
             f"{int(fx.get('cct_k'))} K, {voltage} V "
             f"({fx.get('length_in'):g} L x {fx.get('width_in'):g} W x "
             f"{fx.get('height_in'):g} H in; generated from catalog facts)")
            if shape == "box" else
            (f"Recessed downlight, {fx.get('aperture_in'):g} in aperture, "
             f"{fx.get('lumens_lm') or '?'} lm, {fx.get('cct_k') or '?'} K, "
             f"{voltage} V; OUR parametric housing (manufacturer housing dims not "
             f"sourced); IES referenced by URL")))
    # geometry: the housing above the ceiling face (z 0..H)
    if shape == "box":
        fb = add_box_form(doc, L, Wd, Hh, base_z_ft=0.0, center=(0.0, 0.0),
                          rep=G.REP_SOLID if solid else G.REP_DUMMY)
        fb.params.update({"role": "troffer housing",
                          "dims_in": [facts.get("length_in"), facts.get("width_in"),
                                      facts.get("height_in")]})
    else:
        # the inscribed 4-gon prism (G.polygon_cylinder), NOT the true two-arc
        # G.cylinder: it shares the box topology template, so box_face('top') /
        # add_connector address its top cap exactly as they do a box's; the
        # curved CylSurf can is phase 2 (its cap/edge tags differ)
        ctx = geometry_context(doc)
        fb = G.polygon_cylinder(L / 2.0, Hh, ctx, doc.ids, base_z_ft=0.0,
                                center=(0.0, 0.0),
                                rep=G.REP_SOLID if solid else G.REP_DUMMY)
        doc.add(*fb.elements)
        fb.params.update({"role": "downlight housing can (polygonal approximation)",
                          "dims_in": [facts.get("can_diameter_in"),
                                      facts.get("can_diameter_in"),
                                      facts.get("height_in")]})
    # connector: single-phase feed on the housing top, load = wattage
    add_connector(doc, host=fb, face="top",
                  location=(0.0, 0.0, Hh), direction=(1.0, 0.0, 0.0),
                  u_axis=(0.0, 0.0, -1.0), voltage_v=volt, poles=1,
                  apparent_load_va=float(watt or 0.0), power_factor=0.95,
                  bind_voltage_param="Voltage", bind_load_param="Wattage",
                  load_class="Lighting", description="Power Connection")
    doc.finalize()
    stem = ("troffer_" + _slug(size) + "_recessed") if shape == "box" \
        else _slug(f"downlight_{facts.get('aperture_in'):g}in")
    if len(rows) > 1:
        stem += "_" + _slug(_joined([w for w in watts_all if w], "W") or f"{len(rows)}types")
    prod = FamilyProduct("luminaire", doc, facts, forms=[fb], file_stem=stem, types=rows)
    prod.notes.append("apparent load = the input wattage (power factor 0.95 booked "
                      "on the connector); bound to the Wattage parameter")
    _multi_type_notes(prod)
    if shape != "box":
        prod.notes.append("housing = OUR polygonal can (manufacturer housing dims not "
                          "sourced); the true curved profile is phase 2")
    return prod


# ---------------------------------------------------------------------------
# PROVENANCE SCAN (the identity / no-Autodesk-bytes proof)
# ---------------------------------------------------------------------------

#: Formats/Latest is a per-release FORMAT constant (byte-identical schema in
#: every Revit 2026 file, .rvt or .rfa) -- carrying it is carrying the file
#: format, not content.  Known corpus digest (KNOWLEDGE.md):
FORMATS_LATEST_SHA256_PREFIX = "6459a9a9"

#: strings that would betray cloned Autodesk / manufacturer content.
#: The published Forge schema IDENTIFIERS ('autodesk.spec.*',
#: 'autodesk.parameter.group.*', 'autodesk.unit.*') and the local-parameter
#: identity form ('revit.local.family:*') are the format's parameter
#: VOCABULARY -- every family parameter carries them -- and are whitelisted;
#: the patterns target company / author / product strings and file paths.
_SUSPECT_PATTERNS = (
    r"C:\\", r"Users\\", r"\bAutodesk\b", r"OmniClass", r"Table[- ]End",
    r"racbasic", r"rmebasic", r"Documents and Settings",
)
#: format-vocabulary namespaces excluded from suspicion (interoperability ids)
_FORGE_VOCAB = re.compile(
    r"^(autodesk\.(spec|parameter\.group|unit\.(unit|symbol))[:.]"
    r"|revit\.local\.(family|shared)[:.])", re.I)


def provenance_scan(path: str, *, donor: Optional[str] = None) -> Dict[str, Any]:
    """The provenance ledger of a generated ``.rfa``.

    Proves: (1) every element of the family document is OURS (its id set is
    exactly the generated document's; every seq-102 object decodes and its
    strings are scanned); (2) NO Autodesk / manufacturer identity strings in
    the family document, ``PartAtom`` or ``BasicFileInfo`` (the checked
    patterns are listed); (3) ``PartAtom`` = our product manifest (no
    Autodesk taxonomy terms / OmniClass); (4) ``BasicFileInfo`` = our
    identity (author = the writer, no Windows user path); (5) the format
    constants carried from the donor container are named and characterised:
    ``Formats/Latest`` (the per-release schema constant, sha256 checked
    against the corpus digest) and ``Global/Latest`` (the donor's document
    object scaffolding -- registries with DANGLING references to donor ids
    that do not exist in our file -- carrying no family geometry, type
    table, parameter set or manufacturer content).
    """
    from ..container import open_rvt
    from ..families import FamilyIndex, unit_segments
    from ..objects import iter_records
    from .. import adocument as _A

    rep: Dict[str, Any] = {"path": path, "checks": {}, "findings": []}
    idx = FamilyIndex(path)
    # (1) the family document's elements + strings
    segs = unit_segments(idx, 0)
    ids = sorted({r.elem_id for r in iter_records(segs[102], 102) if r.elem_id >= 0})
    strings: List[str] = []
    classes: Dict[str, int] = {}
    dirty = 0
    for eid in ids:
        d = idx.decode(0, eid, 102)
        cn = idx.class_name(idx.unit_records(0)[102][eid].class_id)
        classes[cn] = classes.get(cn, 0) + 1
        if d is None or not d.clean:
            dirty += 1
            continue
        _collect(d.value, strings)
    rep["family_document"] = {
        "n_elements": len(ids), "id_range": [ids[0], ids[-1]] if ids else None,
        "classes": classes, "undecoded": dirty,
        "n_distinct_strings": len(set(strings)),
    }
    sus_elem = _suspects(strings)
    rep["checks"]["family_document_strings_clean"] = not sus_elem
    if sus_elem:
        rep["findings"].append({"where": "family document", "suspects": sus_elem[:20]})
    rep["family_document"]["forge_vocabulary_ids"] = forge_vocabulary(strings)
    rep["family_document"]["sample_strings"] = sorted(set(strings))[:40]
    # (2)/(3) PartAtom + BasicFileInfo + stream inventory
    with open_rvt(path) as f:
        names = sorted(s.name for s in f.streams())
        rep["streams"] = names
        pa = f.raw("PartAtom").decode("utf-8", "replace") if "PartAtom" in names else ""
        bfi = f.raw("BasicFileInfo") if "BasicFileInfo" in names else b""
        fmt = f.inflate("Formats/Latest", 0) if "Formats/Latest" in names else b""
        latest = f.inflate("Global/Latest", 0) if "Global/Latest" in names else b""
    rep["part_atom"] = {
        "bytes": len(pa),
        "product": bool(re.search(r"<A:product>rvt-writer</A:product>", pa)),
        "no_autodesk_product_label": ("Autodesk" not in pa.replace(
            SK.PARTATOM_NS, "").replace("Revit", "")),
        "no_omniclass": ("OmniClass" not in pa) and ("23." not in re.sub(
            r"\d{4}-\d{2}-\d{2}", "", pa)),
        "namespace_note": ("uses the partatom XML VOCABULARY (urn:schemas-autodesk-com:"
                           "partatom) -- format interoperability, values are ours"),
    }
    rep["checks"]["part_atom_ours"] = (rep["part_atom"]["product"]
                                       and rep["part_atom"]["no_autodesk_product_label"]
                                       and rep["part_atom"]["no_omniclass"])
    bfi_txt = bfi.decode("utf-16-le", "replace") + bfi.decode("utf-8", "replace")
    rep["basic_file_info"] = {
        "bytes": len(bfi),
        "author_rvt_writer": "rvt-writer" in bfi_txt,
        "no_windows_user_path": not re.search(r"C:\\Users\\", bfi_txt),
        "no_autodesk_employee_path": not re.search(r"\\Autodesk\\|autodesk\.com", bfi_txt),
    }
    rep["checks"]["basic_file_info_ours"] = all(rep["basic_file_info"][k] for k in (
        "author_rvt_writer", "no_windows_user_path", "no_autodesk_employee_path"))
    # (5) the carried format constants
    fmt_sha = _sha256(fmt) if fmt else ""
    rep["carried_format_constants"] = {
        "Formats/Latest": {
            "inflated_bytes": len(fmt), "sha256": fmt_sha,
            "is_corpus_schema_constant": fmt_sha.startswith(FORMATS_LATEST_SHA256_PREFIX),
            "note": ("the per-release archive class map, byte-identical in every "
                     "Revit 2026 file (.rvt and .rfa) -- FORMAT, not content"),
        },
        "Global/Latest": _characterize_latest(latest, set(ids), _A),
        "opaque": ["Partitions unit footer blob (64 B) + stream end record (~92 B): "
                   "opaque format bytes from the donor container (V15/V20 proved "
                   "the reader accepts foreign / re-blocked content beside them)"],
    }
    rep["checks"]["formats_latest_is_format_constant"] = bool(
        rep["carried_format_constants"]["Formats/Latest"]["is_corpus_schema_constant"])
    rep["ours"] = ["Partitions save unit (every element of the family document)",
                   "Global/ElemTable", "Global/History", "Global/DocumentIncrementTable",
                   "Global/PartitionTable", "Global/ContentDocuments (empty)",
                   "Contents", "BasicFileInfo", "TransmissionData", "PartAtom",
                   "CFB container, gzip framing, CRCIO page ECC"]
    rep["patterns_checked"] = list(_SUSPECT_PATTERNS)
    rep["ok"] = bool(rep["checks"].get("family_document_strings_clean")
                     and rep["checks"].get("part_atom_ours")
                     and rep["checks"].get("basic_file_info_ours")
                     and rep["checks"].get("formats_latest_is_format_constant")
                     and dirty == 0)
    return rep


def _collect(v: Any, out: List[str]) -> None:
    if isinstance(v, str):
        if v:
            out.append(v)
    elif isinstance(v, dict):
        for x in v.values():
            _collect(x, out)
    elif isinstance(v, list):
        for x in v:
            _collect(x, out)


def _suspects(strings: Sequence[str]) -> List[str]:
    pats = [re.compile(p, re.I) for p in _SUSPECT_PATTERNS]
    out = []
    for s in set(strings):
        if _FORGE_VOCAB.match(s):       # format vocabulary, not content
            continue
        if any(p.search(s) for p in pats):
            out.append(s[:120])
    return sorted(out)


def forge_vocabulary(strings: Sequence[str]) -> List[str]:
    """The Forge / local-parameter identifier strings present (whitelisted
    format VOCABULARY -- reported so the whitelist is transparent)."""
    return sorted({s for s in strings if _FORGE_VOCAB.match(s)})


def _characterize_latest(payload: bytes, our_ids: set, A) -> Dict[str, Any]:
    """Decode the carried Global/Latest (the ADocument object graph) and
    characterise what it is: document-object scaffolding whose element
    references point at DONOR ids absent from our file (dangling), the
    Revit-shipped Forge unit/spec corpus, and NO family geometry / types /
    parameters / manufacturer content."""
    out: Dict[str, Any] = {"inflated_bytes": len(payload)}
    if not payload:
        out["status"] = "absent"
        return out
    try:
        adoc = A.decode_latest(payload)
    except Exception as e:                                  # pragma: no cover
        out["status"] = f"undecoded ({e!r})"
        return out
    ids = set(adoc.element_ids())
    dangling = sorted(ids - set(our_ids))
    out.update({
        "status": "decoded", "clean": bool(adoc.clean),
        "distinct_element_ids_referenced": len(ids),
        "references_to_our_elements": len(ids & set(our_ids)),
        "dangling_references_to_donor_ids": len(dangling),
        "content_records": len(((adoc.value.get("m_oContentTable") or {}).get("value")
                                or {}).get("m_ContentRecSet") or []),
        "n_distinct_strings": len(set(adoc.strings())),
        "characterisation": (
            "the DONOR container's serialized ADocument (family-editor / document "
            "registries): its element-tracking registries reference donor element "
            "ids that do NOT exist in this file (dangling), plus the Revit-shipped "
            "Forge unit/spec corpus (a per-release constant, identical in every "
            "file).  It carries NO family geometry, NO type table, NO parameter "
            "definitions and NO manufacturer content -- those live in the "
            "partition save unit and PartAtom, which are ours.  It is the one "
            "honest carried non-constant, retired by authoring OUR ADocument "
            "(the codec exists: rvt.adocument.encode_latest; acceptance of an "
            "empty-registry family document is the open viewer question)."),
    })
    return out


# ===========================================================================
# THE PROJECT-SIDE LOADER (embedding a generated family into a .rvt)
# ===========================================================================
#
# Loading OUR family into a host project = five host mutations
# (docs/writer/asset-factory.md "loader"):
#
#   L1  Global/ContentDocuments += one entry keyed by our document GUID
#       (framing SOLVED here + proven byte-exact: :func:`parse_content_
#       documents` / :func:`assemble_content_documents`);
#   L2  Partitions/<N> += our save unit (unit k+1) before the stream end
#       record (:func:`build_family_save_unit` / :func:`splice_save_unit`,
#       walker-clean re-read);
#   L3  the embedded document's serialized ADocument (the entry's payload:
#       inline ElemTable + History) -- :func:`author_embedded_adocument`
#       builds OUR minimal document object with the ADocument codec; its
#       acceptance with EMPTY family-editor registries (AppInfoManager) is
#       the open viewer question;
#   L4  host-side elements: a host `Family` (m_oFamDoc{contentDocGUID}),
#       one `FamilySymbol` per type, a placed `FamilyInstance`, their
#       ElemRecs and the save bookkeeping (rvt.commit + rvt.mutate) --
#       NOT YET AUTHORED (no from-scratch host Family / FamilySymbol
#       constructor exists; SPECIFIED in the record);
#   L5  the host Global/Latest ContentTable registry record for the new
#       content GUID -- SPECIFIED (rvt.adocument transform), not yet built.
#
# The loader therefore STOPS at proven mechanisms + a precise spec: no
# project file is emitted with a partial / faked insertion.
# ---------------------------------------------------------------------------

import struct as _struct

#: ContentDocuments entry separator token: u16 0x3a3, i32 -1, u16 0x3a2,
#: i32 -1 (the partition-unit separator with counter -1) [VERIFIED]
CD_SEPARATOR = _struct.pack("<HiHi", 0x3A3, -1, 0x3A2, -1)          # 12 B
#: ContentDocuments end record: u16 0x3a3, i32 0, i32 -1, u32 0 [VERIFIED]
CD_END_RECORD = _struct.pack("<HiiI", 0x3A3, 0, -1, 0)              # 14 B


def parse_content_documents(payload: bytes) -> Tuple[List[Tuple[str, bytes]], bytes]:
    """Parse an inflated ``Global/ContentDocuments`` payload (8-byte stream
    prefix ALREADY stripped) into ``([(guid, adoc_bytes), ...], tail)``.

    GRAMMAR [VERIFIED byte-exact reassembly on rme 305 / rac 163 / rst 52
    entries -- retires the wave-1 scanner's 32/305 under-count]::

        entry = separator(12: u16 0x3a3, i32 -1, u16 0x3a2, i32 -1)
              + GUID(16, bytes_le)              = the embedded document's
                                                  content GUID (== its
                                                  partition unit separator
                                                  GUID)
              + u32 adoc_len
              + ADocument (u16 0x1c + object; INLINE ElemTable + History)
              + u32 adoc_len                     (mirror)
        stream = entry* + end_record(14: u16 0x3a3, i32 0, i32 -1, u32 0)

    Entries appear sorted by GUID (bytes_le order).  ``tail`` = the bytes
    after the last entry (the 14-byte end record on a clean stream).
    """
    entries: List[Tuple[str, bytes]] = []
    p = 0
    n = len(payload)
    while p + 12 <= n and payload[p:p + 12] == CD_SEPARATOR:
        guid = str(uuid.UUID(bytes_le=payload[p + 12:p + 28]))
        alen = _struct.unpack_from("<I", payload, p + 28)[0]
        adoc = payload[p + 32:p + 32 + alen]
        mirror = _struct.unpack_from("<I", payload, p + 32 + alen)[0]
        if mirror != alen:
            raise ValueError(f"ContentDocuments entry @{p}: adoc_len mirror "
                             f"{mirror} != {alen}")
        entries.append((guid, adoc))
        p = p + 32 + alen + 4
    return entries, payload[p:]


def content_document_entry(guid: str, adoc: bytes) -> bytes:
    """One serialized ``Global/ContentDocuments`` entry for ``guid``."""
    return (CD_SEPARATOR + uuid.UUID(guid).bytes_le
            + _struct.pack("<I", len(adoc)) + bytes(adoc)
            + _struct.pack("<I", len(adoc)))


def assemble_content_documents(entries: Sequence[Tuple[str, bytes]],
                               tail: bytes = CD_END_RECORD) -> bytes:
    """Assemble the inflated ``Global/ContentDocuments`` payload from
    ``entries`` (sorted here by GUID bytes_le, the order the reader stores)
    + the end record.  ``assemble(parse(x)) == x`` on the corpus."""
    out = bytearray()
    for guid, adoc in sorted(entries, key=lambda e: uuid.UUID(e[0]).bytes_le):
        out += content_document_entry(guid, adoc)
    out += bytes(tail)
    return bytes(out)


def insert_content_document(payload: bytes, guid: str, adoc: bytes) -> bytes:
    """Return ``payload`` (inflated ``Global/ContentDocuments``) with a new
    entry for ``guid`` inserted at its GUID-sorted position (existing
    entries and the end record byte-preserved)."""
    entries, tail = parse_content_documents(payload)
    if any(g == guid for g, _a in entries):
        raise ValueError(f"content document {guid} already present")
    entries.append((guid, bytes(adoc)))
    return assemble_content_documents(entries, tail=tail or CD_END_RECORD)


# -- L3: OUR embedded document object (ADocument) --------------------------

def author_embedded_adocument(doc: SK.FamilyDoc, *, episode: int = 0,
                              document_guid: Optional[str] = None,
                              appinfo_slots: int = 239) -> Dict[str, Any]:
    """Author the ADocument of ``doc`` in its EMBEDDED form: the object a
    ``Global/ContentDocuments`` entry carries -- INLINE ``ElemTable`` (one
    ElemRec per element of the document) + INLINE ``DocumentHistory`` (a
    document with no separate Global streams) + the empty sub-tables.

    Shape [VERIFIED against the 208 V panelboard's embedded ADocument,
    decoded clean + re-encoded byte-exact by rvt.adocument]:
    m_pHostDocument = weak 1 (the HOST document); the document's own
    sub-objects self-reference weak 2 (this ADocument = archive object 2 in
    the host context); ContentTable empty; ``m_ownerFamilyId`` = the
    document's own self-Family; ``m_storedByRevitBuild`` = [] (embedded).

    THE OPEN QUESTION: the specimen's ``AppInfoManager`` holds 110
    populated family-editor registries (FamilyMgr, CategoryTracking,
    ElementTracking, SymbolIdMgr, SketchEditMgr ...).  OURS carries the
    239-slot registry with EVERY slot null (the minimal-document form) --
    whether Revit's loader tolerates empty registries is UNKNOWN and is the
    viewer question this rung answers.  Returns ``{"value", "payload",
    "self_check"}`` (payload = the entry's ADocument bytes, no trailer).
    """
    from .. import adocument as _A
    from ..genesis.types import blank_object as _blank

    def _clean_blank(cls_name: str) -> dict:
        o = _blank(cls_name)
        return o

    els = sorted(doc.elements, key=lambda e: e.elem_id)
    elem_recs = []
    for e in els:
        elem_recs.append({
            "m_history": {
                "m_originalElementId": {"m_id64": int(e.elem_id)},
                "m_creationDate": {"m_id": int(episode)},
                "m_lastModificationDate": {"m_id": int(episode)},
                "m_lastUserModificationDate": {"m_id": -1},
            },
            "m_id": int(e.elem_id),
            "m_OwningElementId": int(e.owner_id) if getattr(e, "owner_id", -1) >= 0 else -1,
            "m_partitionId": {"m_id": 0},
        })
    et = _clean_blank("ElemTable")
    et["m_elemArr"] = elem_recs
    et["m_graveyardRecs"] = []
    src = _clean_blank("IdentifierSource")
    src["m_last"] = max((e.elem_id for e in els), default=0)
    et["m_pSource"] = {"ptr_class": "IdentifierSource", "pid": -1, "value": src}
    et["m_bExpandAllOnLoad"] = False
    et["m_bLastElementIdOverride"] = False
    hguid = document_guid or doc.document_guid or str(uuid.uuid4())
    dit = _clean_blank("DocumentIncrementTable")
    dit["m_increments"] = []
    dit["m_localIncrements"] = []
    dit["m_permutation"] = []
    hist = _clean_blank("DocumentHistory")
    hist.update({
        "m_pADoc": {"weakref": 2},
        "m_pIncrementTable": {"ptr_class": "DocumentIncrementTable", "pid": -1,
                              "value": dit},
        "m_episodeList": {"m_oEpisodes": []},
        "m_nextLocalSequenceNumber": 0,
        "m_subsequenceNumberDeficit": 0,
        "m_creationGUID": {"m_guid": hguid},
        "m_detachGUID": {"m_guid": hguid},
        "m_upgradeGUID": {"m_guid": hguid},
        "m_previousUpgradeGUID": {"m_guid": "00000000-0000-0000-0000-000000000000"},
        "m_saveAsGUID": {"m_guid": hguid},
        "m_upgradeVersions": [],
    })
    ct = _clean_blank("ContentTable")
    ct["m_pHostDocument"] = {"weakref": 2}
    ct["m_ContentRecSet"] = []
    # StyleSettings: nine table stubs, each just {m_pADoc: weak 2}
    ss = _clean_blank("StyleSettings")
    for fld, cls in (("m_categoryTable", "CategoryTable"),
                     ("m_pMaterialTable", "MaterialTableNew"),
                     ("m_pPenWidthTableGetter", "PenWidthTableGetter"),
                     ("m_pLinePatternTable", "LinePatternTable"),
                     ("m_pFontTable", "FontTableNew"),
                     ("m_pFillPatternTable", "FillPatternTable"),
                     ("m_pTilePatternTable", "TilePatternTable"),
                     ("m_pAppearanceAssetTable", "AppearanceAssetTable"),
                     ("m_pStructuralPropertySetTable", "StructuralPropertySetTable")):
        if fld in ss:
            ss[fld] = {"ptr_class": cls, "pid": -1, "value": {"m_pADoc": {"weakref": 2}}}
    noble = _clean_blank("NOBLE_SecondaryDataStorage")
    noble.update({"m_appInfoData": [], "m_data": [], "m_pDoc": {"weakref": 2},
                  "m_enqueuedData2primaryParents": [],
                  "m_invalidatedInTransaction": [],
                  "m_invalidatingCandidates": [],
                  "m_primary2SecondaryDataIdMap": []})
    steel = _clean_blank("SteelModelInfo")
    aim = _clean_blank("AppInfoManager")
    aim["m_pADoc"] = {"weakref": 2}
    aim["m_appInfoArr"] = [None] * int(appinfo_slots)      # ALL registries null
    value = {
        "m_elemTable": {"ptr_class": "ElemTable", "pid": -1, "value": et},
        "m_appInfoArr": [],
        "m_oContentTable": {"ptr_class": "ContentTable", "pid": -1, "value": ct},
        "m_pHostDocument": {"weakref": 1},
        "m_pAppInfoManager": {"ptr_class": "AppInfoManager", "pid": -1, "value": aim},
        "m_pStyleSettings": {"ptr_class": "StyleSettings", "pid": -1, "value": ss},
        "m_pHistory": {"ptr_class": "DocumentHistory", "pid": -1, "value": hist},
        "m_pSteelModelInfo": {"ptr_class": "SteelModelInfo", "pid": -1, "value": steel},
        "m_pPartitionTable": None,
        "m_oNobleSecondaryData": {"ptr_class": "NOBLE_SecondaryDataStorage",
                                  "pid": -1, "value": noble},
        "m_ownerFamilyId": int(doc.self_family.elem_id),
        "m_ownerFamilyContainingGroupId": -1,
        "m_devBranchInfo": {"m_devBranchId": 1, "m_syncVersion": 2662},
        "m_groupFile": False,
        "m_corruptDocument": False,
        "m_bIsCoreDocument": False,
        "m_executedUpgrades": [],
        "m_storedByRevitBuild": [],
        "m_oExServicesUsed": {"ptr_class": "ExServicesUsed", "pid": -1,
                              "value": {"m_arrServiceInfo": []}},
    }
    payload = _A.encode_latest(value, trailer=b"")     # entry form: no trailer
    # self-check: our own decoder reads it back to the same tree
    back = _A.decode_latest(payload)
    self_ok = bool(back.clean) and _values_close(back.value, value)
    return {"value": value, "payload": payload, "self_check": {
        "decodes_clean": bool(back.clean), "roundtrip_equal": self_ok,
        "bytes": len(payload), "elem_recs": len(elem_recs),
        "appinfo_slots_null": int(appinfo_slots),
        "open_question": ("AppInfoManager carries all-null registries "
                          "(specimen: 110 populated) -- acceptance UNKNOWN"),
    }}


def _values_close(a: Any, b: Any) -> bool:
    """Deep equality tolerant of the decoder's blank-field expansions:
    every key/value WE set must come back equal (extra defaulted keys ok)."""
    if isinstance(b, dict):
        if not isinstance(a, dict):
            return False
        return all(_values_close(a.get(k), v) for k, v in b.items())
    if isinstance(b, list):
        return isinstance(a, list) and len(a) == len(b) and all(
            _values_close(x, y) for x, y in zip(a, b))
    if b is None:
        return a is None or a == {} or a == []
    if isinstance(b, float):
        return isinstance(a, (int, float)) and abs(float(a) - b) < 1e-9
    return a == b


# -- L2: the embedded save unit + partition splice -------------------------

def build_family_save_unit(doc: SK.FamilyDoc, *, block_size: int = 128 * 1024,
                           gzip_level: int = 3) -> Dict[str, Any]:
    """Assemble the bytes of OUR family document as an EMBEDDED SAVE UNIT of
    a host project's ``Partitions/<N>``: the 28-byte unit separator (our
    content GUID + record count) + one block run per seq (whole records,
    our gzip, block counters by the corpus identity) + the 18-byte unit
    terminator + the 0x0f3f footer + the 'Data generated ...' magic.

    Framing = the family-skeleton stream's proven single-unit assembler
    minus the stream header / end record (a save unit is header-less).
    """
    from ..writer import gzip_member
    if not doc.finalized:
        doc.finalize()
    unit = doc.to_embedded_unit()
    segs: Dict[int, bytes] = unit["segments"]
    guid = unit["content_doc_guid"]
    n_records = int(unit["record_count"])
    hdr_len = {101: 16, 102: 20, 103: 20}
    body = bytearray()
    body += _struct.pack("<Hi", 0x3A3, -1)                       # separator
    body += _struct.pack("<HI", 0x3A2, n_records) + uuid.UUID(guid).bytes_le
    for seq in (101, 102, 103):
        seg = segs.get(seq, b"")
        recs = SK._split_records(seg, seq)
        blocks: List[bytes] = []
        cur = bytearray()
        for rb in recs:
            if cur and len(cur) + len(rb) > block_size:
                blocks.append(bytes(cur))
                cur = bytearray()
            cur += rb
        blocks.append(bytes(cur))
        for pay in blocks:
            A = sum(1 for _ in SK._split_records(pay, seq))
            Cc = len(pay) - hdr_len[seq] * A
            gz = gzip_member(pay, level=gzip_level, sync_flush=True)
            B = 8 + len(gz)
            body += _struct.pack("<HIIIIII", SK.BLOCK_TAG, 4, A, B, Cc, seq, 0)
            body += gz
            body += _struct.pack("<HI", SK.TRAILER_TAG, B)
    # unit terminator + footer + magic string.
    # The footer blob MUST be non-empty: Autodesk's consistency audit rejects
    # any INSTANCED unit whose 0x0f3f blob is missing (verdict #36: E1b — a
    # random 64-byte blob passes, the empty form fails; presence-only check).
    # We author the deterministic 64-byte nonce form (famdoc_adoc.build_footer).
    from .famdoc_adoc import build_footer as _build_footer
    _blob = _build_footer(guid=guid, payload=bytes(segs.get(102, b"")))
    body += _struct.pack("<H", SK.BLOCK_TAG) + b"\x00" * 16
    body += _struct.pack("<HI", SK.FOOTER_TAG, len(_blob)) + _blob
    txt = SK.DATA_GENERATED_STRING.encode("utf-16-le")
    body += _struct.pack("<I", len(SK.DATA_GENERATED_STRING)) + txt
    return {"guid": guid, "record_count": n_records,
            "bytes": bytes(body), "segments": {k: len(v) for k, v in segs.items()},
            "type_names": unit["type_names"]}


def splice_save_unit(host_logical: bytes, unit_bytes: bytes) -> Dict[str, Any]:
    """Insert a save unit into a host's inflated ``Partitions/<N>`` logical
    stream immediately BEFORE the stream end record; every existing unit is
    byte-preserved (a family load never re-blocks the host document or the
    other embedded documents).  Returns ``{"logical", "insert_offset",
    "walker": {units_before, units_after, errors, our_unit_records}}``.
    The re-walk proves the framing: unit count + 1, walker error-free, and
    our unit's per-seq record counts decode.
    """
    from ..partitions import StreamWalker
    from ..objects import iter_records
    w0 = StreamWalker(host_logical, inflate=False, keep_data=False)
    if w0.errors:
        raise RuntimeError(f"host partition stream walker errors: {w0.errors[:3]}")
    ins = int(w0.end_offset)          # start of the stream end record
    new_logical = bytes(host_logical[:ins]) + bytes(unit_bytes) + bytes(host_logical[ins:])
    w1 = StreamWalker(new_logical, inflate=True, keep_data=True)
    ours = w1.units[-1] if w1.units else None
    per_seq: Dict[str, int] = {}
    ids_ok = None
    if ours is not None:
        blocks = w1.blocks[ours.first_block:ours.first_block + ours.n_blocks]
        segs: Dict[int, bytearray] = {}
        for b in sorted(blocks, key=lambda b: b.hdr_offset):
            segs.setdefault(b.seq, bytearray()).extend(b.data or b"")
        idsets = {}
        for s, buf in segs.items():
            recs = list(iter_records(bytes(buf), s))
            per_seq[str(s)] = len(recs)
            idsets[s] = [r.elem_id for r in recs if r.elem_id >= 0]
        ids_ok = (idsets.get(101) == idsets.get(102) == idsets.get(103))
    return {"logical": new_logical, "insert_offset": ins,
            "walker": {"units_before": len(w0.units), "units_after": len(w1.units),
                       "errors": list(w1.errors[:5]),
                       "our_unit_index": ours.index if ours else None,
                       "our_unit_guid": (str(uuid.UUID(bytes_le=ours.guid))
                                          if ours and ours.guid else None),
                       "our_unit_counter": ours.counter if ours else None,
                       "our_unit_records": per_seq,
                       "id_sets_identical": ids_ok}}


# -- L4/L5: the host-side steps NOT built (the honest spec) -----------------

LOADER_SPEC = {
    "L1_content_documents_entry": {
        "status": "BUILT (parse/assemble/insert; byte-exact corpus round-trip)",
        "grammar": ("separator(u16 0x3a3, i32 -1, u16 0x3a2, i32 -1) + GUID(16) "
                    "+ u32 adoc_len + ADocument + u32 adoc_len (mirror); "
                    "entries GUID-sorted; end record u16 0x3a3, i32 0, i32 -1, u32 0"),
    },
    "L2_partition_save_unit": {
        "status": "BUILT (unit assembly + splice before the end record; walker-clean)",
        "note": ("our unit = separator{content GUID, record count} + our blocks "
                 "+ terminator + footer + magic; host units byte-preserved"),
    },
    "L3_embedded_adocument": {
        "status": ("BUILT (our minimal document object: inline ElemTable of our "
                   "elements + inline empty History + stub tables; codec "
                   "round-trip clean)"),
        "open": ("AppInfoManager registries all-null vs the specimen's 110 "
                 "populated family-editor registries -- ACCEPTANCE UNKNOWN "
                 "(the viewer question of this rung)"),
    },
    "L4_host_elements": {
        "status": "BUILT (rvt.famgen.loader)",
        "what": ("14 host `ParamElemFamily` twins (owner = host Family), a "
                 "`FamilySurrogate`, the host `Family` (our self-Family "
                 "transformed to the host flavour: m_oFamDoc{contentDocGUID, "
                 "big2SmallMap2, coreIds}, m_famDocGUID, host m_familyIds / "
                 "type table / ConnectorDataCell / preview views / reference "
                 "index manager), a host `FamilySymbol` (type row + the SYMBOL "
                 "GEOMETRY: geomSteps history + GeomTable + the seq-103 solid) + "
                 "its `FamSymSurrogate`, and a placed `FamilyInstance` -- all "
                 "landed by rvt.commit.commit_new_elements (save unit 0 + "
                 "ElemTable)"),
        "how": ("field-by-field from the specimen grammar (host Family 454674 / "
                "symbol 455409 diffed against their embedded document); every "
                "record encode->decode byte-exact; docs/writer/asset-factory.md §5"),
    },
    "L5_host_content_table": {
        "status": "BUILT (rvt.famgen.loader.register_in_host_adocument)",
        "what": ("host Global/Latest ADocument: ContentTable.m_ContentRecSet += "
                 "our record; AppInfoManager[FamilyMgr].m_arrLoadedFamilyInfo += "
                 "{surrogateId, [our GUID]}; AppInfoManager[ElementTrackingData] "
                 "symbol / instance id sets += ours"),
        "how": ("rvt.adocument.decode_latest -> edit -> encode_latest (re-decodes "
                "clean) -> the loader's two-pass write"),
    },
}


def loader_readiness(host_rvt: Optional[str] = None,
                     product: Optional[FamilyProduct] = None,
                     out_json: Optional[str] = None,
                     emit: Optional[str] = None) -> Dict[str, Any]:
    """Exercise the loader mechanisms against a real host project and report.

    Proves on the host: (P1) ContentDocuments parse->assemble is byte-exact;
    (P2) an entry for OUR document inserts at its sorted position and the
    result re-parses with count+1; (P3) our embedded ADocument authors and
    round-trips through the codec; (P4) our save unit assembles and splices
    into the host partition stream walker-clean with identical id sets;
    (P5) our element ids are allocated above the host watermark (no
    re-idding needed).

    L4 (host Family / FamilySymbol / instance) and L5 (host ADocument
    registrations) are now BUILT by ``rvt.famgen.loader`` (see
    ``LOADER_SPEC``); pass ``emit=<out.rvt>`` to run the full load through
    it (``rvt.famgen.loader.load_family_into_project``) after the P1-P5
    readiness proofs.  Without ``emit`` this stays the fast, file-less
    mechanism proof.
    """
    from ..container import open_rvt
    from ..elemtable import parse_elemtable
    host = host_rvt or os.path.join(_ROOT, "samples", "rmebasicsampleproject.rvt")
    rep: Dict[str, Any] = {"host": host, "proofs": {}, "spec": LOADER_SPEC}
    with open_rvt(host) as f:
        cd_raw_pref = f.prefix("Global/ContentDocuments")
        cd = b"".join(f.inflate_all("Global/ContentDocuments"))
        et_payload = f.inflate("Global/ElemTable", 0)
        part_name = f.partition_streams()[0]
        part_logical = f.logical(part_name)
    # P1: framing round-trip on the real host
    entries, tail = parse_content_documents(cd)
    rebuilt = assemble_content_documents(entries, tail=tail)
    rep["proofs"]["P1_content_documents_roundtrip"] = {
        "entries": len(entries), "end_record": tail.hex(),
        "byte_exact": rebuilt == cd, "payload_bytes": len(cd),
        "prefix": cd_raw_pref.hex()}
    # P5: allocate our ids above the host watermark
    et = parse_elemtable(et_payload)
    wm_footer = et.footer.last_id if getattr(et, "footer", None) else 0
    wm = max(int(wm_footer or 0), max((r.id for r in et.records), default=0))
    prod = product or make_panelboard(vendor="eaton", line="pow-r-line",
                                      mains_a=400, spaces=42, voltage="480Y/277",
                                      mcb=True, mounting="surface",
                                      start_id=wm + 1)
    ids = [e.elem_id for e in prod.doc.elements]
    rep["proofs"]["P5_id_allocation"] = {
        "host_watermark": wm, "our_id_range": [min(ids), max(ids)],
        "above_watermark": min(ids) > wm, "collisions": 0 if min(ids) > wm else -1}
    # P3: the embedded ADocument
    ad = author_embedded_adocument(prod.doc)
    rep["proofs"]["P3_embedded_adocument"] = {
        **ad["self_check"], "guid": prod.doc.document_guid}
    # P2: insert our entry
    cd_new = insert_content_document(cd, prod.doc.document_guid, ad["payload"])
    entries2, tail2 = parse_content_documents(cd_new)
    ours = [g for g, _a in entries2 if g == prod.doc.document_guid]
    rep["proofs"]["P2_entry_insert"] = {
        "entries_before": len(entries), "entries_after": len(entries2),
        "ours_present": bool(ours), "end_record_intact": tail2 == tail,
        "delta_bytes": len(cd_new) - len(cd),
        "entry_bytes": len(ad["payload"]) + 36}
    # P4: the save unit + splice
    unit = build_family_save_unit(prod.doc)
    sp = splice_save_unit(part_logical, unit["bytes"])
    w = sp["walker"]
    rep["proofs"]["P4_partition_splice"] = {
        "partition_stream": part_name,
        "unit_guid": unit["guid"], "unit_records": unit["record_count"],
        "unit_bytes": len(unit["bytes"]),
        "units_before": w["units_before"], "units_after": w["units_after"],
        "walker_errors": w["errors"],
        "our_unit_guid_read_back": w["our_unit_guid"],
        "our_unit_counter_read_back": w["our_unit_counter"],
        "our_unit_records_per_seq": w["our_unit_records"],
        "id_sets_identical": w["id_sets_identical"],
        "logical_bytes_before": len(part_logical),
        "logical_bytes_after": len(sp["logical"])}
    ok_built = (rep["proofs"]["P1_content_documents_roundtrip"]["byte_exact"]
                and rep["proofs"]["P2_entry_insert"]["ours_present"]
                and rep["proofs"]["P3_embedded_adocument"]["decodes_clean"]
                and rep["proofs"]["P3_embedded_adocument"]["roundtrip_equal"]
                and not w["errors"] and w["units_after"] == w["units_before"] + 1
                and w["id_sets_identical"])
    rep["built_mechanisms_ok"] = bool(ok_built)
    rep["project_file_emitted"] = False
    rep["stop_reason"] = ""
    rep["next_steps"] = [
        "viewer-gate the loaded projects (rvt.famgen.loader ladder): our symbol "
        "geometry (F4a) vs Revit's regeneration (F4b), the empty embedded "
        "AppInfoManager, and the surrogate / FamilyMgr constants",
    ]
    if emit:
        # the full load through the L4/L5 loader (a project file IS emitted)
        try:
            from . import loader as _L
            res = _L.load_family_into_project(
                host, emit, prod, place=True, symbol_solid=True,
                report_path=os.path.splitext(emit)[0] + ".json")
            rep["load"] = {"ok": res.ok, "out_path": res.out_path,
                           "report": res.report_path,
                           "stop_reason": res.stop_reason}
            rep["project_file_emitted"] = bool(res.ok and res.out_path)
        except Exception as exc:                       # pragma: no cover
            rep["load"] = {"ok": False,
                           "error": f"{type(exc).__name__}: {exc}"}
            rep["stop_reason"] = f"loader raised: {exc}"
    if out_json:
        os.makedirs(os.path.dirname(os.path.abspath(out_json)) or ".", exist_ok=True)
        with open(out_json, "w") as fh:
            json.dump({k: v for k, v in rep.items()}, fh, indent=1, default=str)
        rep["report_path"] = out_json
    return rep


# ---------------------------------------------------------------------------
# demo / proof driver: the three families
# ---------------------------------------------------------------------------

PROOF_FILES = {
    "panelboard": "eaton_prl_400A_42sp_480Y.rfa",
    "transformer": "xfmr_75kVA_480-208Y120.rfa",
    "luminaire": "troffer_2x4_recessed.rfa",
}


def build_proof_families(out_dir: str = FACTORY_OUT, *, solid: bool = True,
                         validate: bool = True) -> Dict[str, Any]:
    """Generate the three proof families of the asset-forge stream:

    * ``eaton_prl_400A_42sp_480Y.rfa`` -- Eaton Pow-R-Line 480Y/277 V, 400 A
      main-breaker, 42-space, surface panelboard (PRL2X box: 20 W x 60 H x
      5.75 D in);
    * ``xfmr_75kVA_480-208Y120.rfa`` -- Eaton DT-3 75 kVA 480 delta - 208Y/120
      dry-type transformer (frame FR942: 30.5 W x 43 H x 24 D in);
    * ``troffer_2x4_recessed.rfa`` -- Lithonia BLT 2x4 recessed LED troffer
      (47.75 L x 23.75 W x 2.375 H in, 38 W, 4600 lm, 4000 K, 120-277 V).

    Each: our whole partition stream + our Globals + our PartAtom + real
    ECC + our container; verify (CRC/ECC/decode) + validate 0 errors
    (family mode) + provenance scan; JSON report beside each file.
    """
    os.makedirs(out_dir, exist_ok=True)
    results: Dict[str, Any] = {"out_dir": out_dir, "files": {}}
    builds = [
        ("panelboard", make_panelboard, dict(vendor="eaton", line="pow-r-line",
                                                mains_a=400, spaces=42, voltage="480Y/277",
                                                mcb=True, mounting="surface", solid=solid)),
        ("transformer", make_transformer, dict(kva=75, primary_v=480,
                                                  secondary_v="208Y/120", solid=solid)),
        ("luminaire", make_luminaire, dict(kind="recessed-troffer", size="2x4",
                                              wattage=38, lumens=4600, cct=4000,
                                              voltage="120-277", solid=solid)),
    ]
    for key, fn, kw in builds:
        prod = fn(**kw)
        path = os.path.join(out_dir, PROOF_FILES[key])
        rep = prod.write(path, validate=validate)
        results["files"][key] = {
            "path": path, "ok": rep["ok"],
            "size": (rep.get("emit") or {}).get("size"),
            "elements": rep["family"]["elements"],
            "verify_ok": (rep.get("verify") or {}).get("ok"),
            "validate": (rep.get("validate") or {}).get("family_mode", {}).get("verdict"),
            "validate_errors": (rep.get("validate") or {}).get("family_mode", {}).get("n_errors"),
            "provenance_ok": (rep.get("provenance") or {}).get("ok"),
            "assumed_fields": rep["facts"].get("assumed_fields"),
            "report": rep.get("report_path"),
        }
    return results


def main(argv=None) -> int:
    argv = list(argv or [])
    res = build_proof_families(validate=("--no-validate" not in argv))
    print(f"asset factory -> {res['out_dir']}")
    ok = True
    for key, f in res["files"].items():
        print(f"  {key:11s} {os.path.basename(f['path']):32s} {f['size'] or 0:>9,} B  "
              f"elements={f['elements']:>3}  verify={'OK' if f['verify_ok'] else 'FAIL'}  "
              f"validate={f['validate']}({f['validate_errors']} errors)  "
              f"provenance={'OK' if f['provenance_ok'] else 'FAIL'}")
        if f["assumed_fields"]:
            print(f"              assumed/unverified: {f['assumed_fields']}")
        ok = ok and f["ok"]
    if "--no-loader" not in argv:
        lr = loader_readiness(out_json=os.path.join(FACTORY_OUT, "loader_readiness.json"))
        p = lr["proofs"]
        print("loader readiness (host = rmebasicsampleproject; NO project file emitted):")
        print(f"  P1 ContentDocuments round-trip byte-exact: "
              f"{p['P1_content_documents_roundtrip']['byte_exact']} "
              f"({p['P1_content_documents_roundtrip']['entries']} entries)")
        print(f"  P2 entry insert: entries {p['P2_entry_insert']['entries_before']} -> "
              f"{p['P2_entry_insert']['entries_after']}, ours present "
              f"{p['P2_entry_insert']['ours_present']}, +{p['P2_entry_insert']['delta_bytes']} B")
        print(f"  P3 embedded ADocument: decodes clean "
              f"{p['P3_embedded_adocument']['decodes_clean']}, round-trip "
              f"{p['P3_embedded_adocument']['roundtrip_equal']}, "
              f"{p['P3_embedded_adocument']['bytes']:,} B, "
              f"{p['P3_embedded_adocument']['elem_recs']} elem recs")
        print(f"  P4 save-unit splice: units {p['P4_partition_splice']['units_before']} -> "
              f"{p['P4_partition_splice']['units_after']}, walker errors "
              f"{p['P4_partition_splice']['walker_errors'] or 'none'}, our unit records "
              f"{p['P4_partition_splice']['our_unit_records_per_seq']}")
        print(f"  P5 ids above host watermark: {p['P5_id_allocation']['above_watermark']} "
              f"(watermark {p['P5_id_allocation']['host_watermark']:,}, ours "
              f"{p['P5_id_allocation']['our_id_range']})")
        print(f"  built mechanisms ok: {lr['built_mechanisms_ok']}; "
              f"project_file_emitted: {lr['project_file_emitted']}")
        if lr.get("stop_reason"):
            print(f"  STOP: {lr['stop_reason'][:120]}...")
        else:
            print("  L4/L5: BUILT by rvt.famgen.loader -- run "
                  "`python -m rvt.famgen.loader` for the project ladder")
        ok = ok and lr["built_mechanisms_ok"]
    return 0 if ok else 1


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main(sys.argv[1:]))
