"""rvt.convert.modify_family -- COMBINATION ROUTE (3): prompt + RFA -> RFA.

Natural-language edits of a family file: "rename the type to 225A MCB;
set BusRating 225; set PanelName DP-7".  The edits ride entirely on
CERTIFIED machinery:

* the family file opens with :meth:`rvt.mutate.Document.from_file` (an
  ``.rfa`` carries the same stream set as a project: partition + ElemTable
  + Global/Latest; verified in this stream's spike);
* every edit is a :func:`rvt.manipulate.modify_element` json-path edit of
  the family document's SELF-``Family`` record (the type table
  ``m_pFamilyTypes.m_pairs[]`` + the current-type defaults
  ``m_familyParams``), committed in ONE :func:`rvt.manipulate.commit_plans`
  (records re-encoded, fresh adler32 stamps, unit re-blocked, ElemTable
  re-emitted, CRCIO re-framed) -- the M3-certified modify path;
* renames also keep the ``PartAtom`` Atom-XML metadata in step (title /
  type title), rebuilt through the container writer;
* gates: :func:`rvt.manipulate.verify_manipulated` (structural),
  :func:`rvt.famgen.famdoc_adoc.validate_family_file` family-mode
  (0 errors required to CLAIM the cell), release preservation
  (:mod:`rvt.versions`), and a semantic RE-READ proving each new value.

THE VALUE CARRIERS (verified on our generated families): a family
parameter's live value sits in ``m_value`` (doubles, in Revit internal
units), ``m_int`` (integers) or ``m_str`` (text) of the type-table row --
so ratings, counts AND names/strings are all editable.  The carrier follows
the parameter definition's STORAGE CLASS first (the pointer class the file's
own schema names: ``ParamDefString`` -> ``m_str``, ``ParamDefInt`` ->
``m_int``; those two carry no ``m_specTypeId`` at all, #333/#336) and the
``m_specTypeId`` of a ``ParamDefValue`` otherwise -- the one rule shared
with rvt_to_ifc, :mod:`rvt.convert.param_carrier`.  Unit conversion is
SPEC-DRIVEN: amperes as-is, volts / W / kW x 1/0.3048^2, kVA x 1000 x
1/0.3048^2, Hz / lm / K as-is (they ARE Revit's internal units), lengths to
feet and masses to kilograms (lb x ``KG_PER_LB``, the factory's one
constant) -- an explicit unit is REQUIRED for lengths and masses, never
guessed; a unit on a measurable spec this lane has no conversion for is
refused by name; only a dimensionless ``number`` ignores a unit suffix.
A LENGTH here is every spec the format's own units table
(``famgen/assets/family_units.json``) displays in a plain length unit --
``aec:length`` and Revit's discipline SIZE specs alike (``cableTraySize``,
``conduitSize``, ``ductSize``, ``pipeSize``, ``wireDiameter`` ...): Revit
stores all of them in feet, so ``Tray Width=12 in`` converts and a bare
``Tray Width=12`` is refused exactly like ``Width=12`` (#668).  The trade's
inch / foot MARKS are units too: ``Width=4"`` is 4 in, ``Depth=2'`` 2 ft,
``1'6"`` / ``1' 6"`` / ``1'-6"`` feet-and-inches (18 in); ONE pair of quotes
cleanly WRAPPING a whole value (``"600 mm"``, ``'4"'``) still comes off first,
and any other quote arrangement (``4''``, ``4'"``, ``''4''``) is refused by
name, never read as feet or inches (#678).

GEOMETRY (#909).  Our generated families carry constraint graphs: a
parameter LABELS a dimension between reference planes that edges, faces and
followers are locked to.  Writing the value alone would leave that dimension
and its geometry at the old size -- a family that disagrees with itself.  So
an edit of a generator INPUT is applied by REBUILDING the family from its
generator at the new value (:mod:`rvt.convert.family_regen`): the generator
and its spec are recovered from the file and PROVEN by reproducing the input
byte for byte first; the result is byte-identical to building at that value
directly.  Everything else (foreign families, catalog equipment, IFC-built
families, a family that does not reproduce) stays on the value path, and an
edit there of a parameter that labels a dimension -- directly or through a
formula parameter -- says so in an explicit caveat (never a silent
mismatch).  Formula parameters an edit feeds (``Nut Across Flats`` ->
``Nut Half Across Flats``) are re-evaluated on both paths; a formula
parameter itself is refused by name (Revit computes it).  No desktop verdict
exists for a rebuilt family (hard rule 4).

VOCABULARY COORDINATION: if a sibling stream lands a shared family-edit
vocabulary module (``rvt.convert.edit_family``), :func:`parse_family_edit`
delegates to its ``parse_family_edit`` and records the delegation; until
then the minimal grammar below IS the vocabulary (merge note in
docs/inbox/convert-b.md).

Territory: ``src/rvt/convert/`` (convert-B stream).
"""
from __future__ import annotations

import argparse
import functools
import html
import json
import os
import re
import time
import unicodedata
import traceback
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Tuple

from .. import _quoted
from .. import versions as V
from ..famgen import standards as ST
from ..famgen.factory import KG_PER_LB
from .add_to_project import (ConvertError, P0_STAMP, QUARANTINE_STAMP, TOOL,
                             TOOL_VERSION, _jdump, _relp, _sha256,
                             quarantined_input)
from ..famgen import formula as _FO
from .param_carrier import carrier_for_param

__all__ = [
    "FamilyEditError", "FamilyInventory", "inventory_family",
    "parse_family_edit", "apply_family_edits", "modify_family", "main",
]

#: volts / VA / W -> Revit internal electrical units (display / 0.3048^2)
_ELEC_FACTOR = 1.0 / (0.3048 ** 2)


class FamilyEditError(ConvertError):
    """The family edit could not be parsed / applied; the message says why."""


# ---------------------------------------------------------------------------
# inventory: what THIS .rfa lets you edit
# ---------------------------------------------------------------------------

@dataclass
class FamilyInventory:
    """The editable surface of one family file."""
    path: str
    family_id: int
    family_name: str                     # PartAtom title (the display name)
    type_names: List[str]
    params: List[dict]                   # {caption, param_id, def_class, spec, carrier, current}
    release: Optional[int] = None
    quarantined: bool = False
    doc: Any = None                      # rvt.mutate.Document
    notes: List[str] = dc_field(default_factory=list)

    def param_by_caption(self, caption: str) -> Optional[dict]:
        key = re.sub(r"[\s_-]+", "", str(caption)).lower()
        hits = [p for p in self.params
                if re.sub(r"[\s_-]+", "", p["caption"]).lower() == key]
        if len(hits) == 1:
            return hits[0]
        if not hits:
            subs = [p for p in self.params
                    if key and key in re.sub(r"[\s_-]+", "", p["caption"]).lower()]
            if len(subs) == 1:
                return subs[0]
        return None

    def as_json(self) -> Dict[str, Any]:
        return {"path": _relp(self.path), "family_id": self.family_id,
                "family_name": self.family_name, "type_names": self.type_names,
                "release": self.release, "quarantined": self.quarantined,
                "params": [dict({k: p[k] for k in ("caption", "param_id", "def_class",
                                                   "spec", "carrier", "current")},
                                kind=_KIND_OF_CARRIER[p["carrier"]])
                           for p in self.params],
                "notes": list(self.notes)}


#: carrier -> the human word for what it stores (``--inventory``'s ``kind``)
_KIND_OF_CARRIER = {"m_str": "text", "m_int": "integer", "m_value": "number"}


def _partatom_title(path: str) -> str:
    from ..container import open_rvt
    try:
        with open_rvt(path) as f:
            xml = f.raw("PartAtom").decode("utf-8", "replace")
        m = re.search(r"<title>(.*?)</title>", xml, re.S)
        return html.unescape(m.group(1)) if m else ""
    except Exception:                                          # noqa: BLE001
        return ""


def inventory_family(path: str) -> FamilyInventory:
    """Open ``path`` and survey the editable surface: the self-Family, its
    type table, and every family parameter (caption / spec / carrier /
    current value)."""
    if not os.path.isfile(path):
        raise FamilyEditError(f"family file not found: {path}")
    from ..mutate import Document
    doc = Document.from_file(path)
    fams = doc.ids_of_class("Family")
    if not fams:
        raise FamilyEditError("the file carries no Family element (not a family "
                              "document?)")
    fam = int(fams[0])
    fv = doc.value(fam) or {}
    ftt = ((fv.get("m_pFamilyTypes") or {}).get("value") or {})
    pairs = ftt.get("m_pairs") or []
    type_names = [str(p.get("name")) for p in pairs]
    # current values live in pair[current]'s rows; captions on the ParamElems
    cur_rows: Dict[int, dict] = {}
    if pairs:
        for row in ((pairs[0].get("params") or {}).get("m_params") or []):
            cur_rows[int(row.get("m_paramId", -1))] = row
    params: List[dict] = []
    for eid in doc.ids_of_class("ParamElemFamily"):
        pv = doc.value(eid) or {}
        pd = pv.get("m_pParamDef") or {}
        d = pd.get("value") or {}
        cap = str(d.get("m_caption") or "").strip()
        if not cap:
            continue
        def_class = str(pd.get("ptr_class") or "")
        spec = str((d.get("m_specTypeId") or {}).get("m_typeId") or "")
        carrier = carrier_for_param(def_class, spec)
        row = cur_rows.get(int(eid), {})
        params.append({"caption": cap, "param_id": int(eid),
                       "def_class": def_class, "spec": spec,
                       "carrier": carrier, "current": row.get(carrier),
                       # a FORMULA parameter (#850 tree on the row): Revit
                       # computes it, an edit sets its inputs (#909)
                       "formula": not _FO.is_no_formula(row.get("m_oExpression"))})
    inv = FamilyInventory(
        path=os.path.abspath(path), family_id=fam,
        family_name=_partatom_title(path) or str(fv.get("m_name") or ""),
        type_names=type_names, params=params,
        release=V.detect_release(path),
        quarantined=quarantined_input(path), doc=doc)
    if not pairs:
        inv.notes.append("the family type table is empty (types may live as "
                         "FamilySymbols -- annotation flavour); type-table edits "
                         "have nothing to target")
    return inv


# ---------------------------------------------------------------------------
# the vocabulary (delegates to a sibling shared module when it exists)
# ---------------------------------------------------------------------------

_RE_RENAME_TYPE = re.compile(
    r"^rename\s+(?:the\s+)?type(?:\s+[\"']?(?P<old>[^\"']+?)[\"']?)?\s+(?:to|as)\s+"
    r"[\"']?(?P<new>[^\"']+?)[\"']?$", re.I)
_RE_RENAME_FAMILY = re.compile(
    r"^rename\s+(?:the\s+)?family\s+(?:to|as)\s+[\"']?(?P<new>[^\"']+?)[\"']?$", re.I)
_RE_SET = re.compile(
    r"^set\s+(?:the\s+)?(?P<cap>[A-Za-z][A-Za-z0-9 _-]*?)"
    r"(?:\s+of\s+type\s+(?:\"(?P<typeq>[^\"]+)\"|'(?P<typeq2>[^']+)'"
    r"|(?P<type>[^\"'\s]+)))?"
    r"\s+(?:to\s+|=\s*)?(?P<val>.+?)$", re.I)

_UNIT_TOKENS = {
    "a": ("current", 1.0), "amp": ("current", 1.0), "amps": ("current", 1.0),
    "v": ("potential", _ELEC_FACTOR), "volt": ("potential", _ELEC_FACTOR),
    "volts": ("potential", _ELEC_FACTOR),
    "ft": ("length", 1.0), "feet": ("length", 1.0), "foot": ("length", 1.0),
    "'": ("length", 1.0),
    "in": ("length", 1.0 / 12.0), "inch": ("length", 1.0 / 12.0),
    "inches": ("length", 1.0 / 12.0), '"': ("length", 1.0 / 12.0),
    "mm": ("length", 1.0 / 304.8), "m": ("length", 1.0 / 0.3048),
    "kva": ("apparent_power", 1000.0 * _ELEC_FACTOR),
    "va": ("apparent_power", _ELEC_FACTOR),
    "w": ("wattage", _ELEC_FACTOR),      # the factory's watts factor (skeleton.watts)
    "kw": ("wattage", 1000.0 * _ELEC_FACTOR),
    "hz": ("frequency", 1.0),            # Hz, lm and K ARE Revit's internal units:
    "lm": ("luminous_flux", 1.0),        # the factory stores them as given, so does
    "k": ("color_temperature", 1.0),     # the edit lane
    "kg": ("mass", 1.0),                 # Revit's internal mass unit IS the kilogram
    "lb": ("mass", KG_PER_LB), "lbs": ("mass", KG_PER_LB), "lbm": ("mass", KG_PER_LB),
    "ka": ("number", 1.0),               # ShortCircuitRatingkA is dimensionless kA
}

_INTERNAL_AS_GIVEN = "(Revit's internal unit -- stored as given)"

#: measurable specs converted by ONE table-driven branch:
#: (spec marker, unit kind, bare-number refusal offer | None, internal unit
#: named in the note, caveat).  An ``offer`` means the unit is REQUIRED --
#: a bare number is refused listing those units (never guessed); ``None``
#: means a bare number is stored as given, exactly as before this table.
#: the length note's geometry caveat -- true on the VALUE path; an edit the
#: family's generator REBUILDS (#909, rvt.convert.family_regen) swaps it for
#: :data:`REBUILT_NOTE`, and a value-only edit of a parameter that LABELS a
#: dimension drops it for the fuller ``VALUE ONLY`` statement (one geometry
#: statement per edit)
LENGTH_CAVEAT = " (CAVEAT: type-table value only; the authored solid is not re-derived)"
REBUILT_NOTE = (" (geometry REBUILT by the family's own generator at this value (#909): "
                "the reference planes, the labelled dimension(s), the locked edges and "
                "faces and the followers agree with it -- no desktop verdict, hard rule 4)")

_SPEC_UNITS = (
    (":length", "length", "in / ft / mm / m", "ft", LENGTH_CAVEAT),
    (":mass-", "mass", "lb / kg", "kg", ""),
    ("electrical:wattage", "wattage", None, "internal (W x 1/0.3048^2)", ""),
    ("electrical:frequency", "frequency", None, f"Hz {_INTERNAL_AS_GIVEN}", ""),
    ("electrical:luminousFlux", "luminous_flux", None, f"lm {_INTERNAL_AS_GIVEN}", ""),
    ("electrical:colorTemperature", "color_temperature", None,
     f"K {_INTERNAL_AS_GIVEN}", ""),
)


def _converted_units() -> str:
    """``kind token / token; ...`` for every unit this lane converts (a
    refusal's offer, drawn from ``_UNIT_TOKENS`` so it cannot fall behind)."""
    kinds: Dict[str, List[str]] = {}
    for tok, (kind, _factor) in _UNIT_TOKENS.items():
        if kind != "number":
            kinds.setdefault(kind.replace("_", " "), []).append(tok)
    return "; ".join(f"{kind} {' / '.join(toks)}" for kind, toks in kinds.items())


#: the ``autodesk.unit.unit:*`` DISPLAY units that format a plain length.  A
#: spec the units table displays in one of these is a length by dimension,
#: and Revit's internal unit for the length dimension is the foot whatever
#: the discipline calls the spec -- so this short list of unit names, not a
#: second hand-kept list of spec ids, decides "stored in feet" (#668).  The
#: four imperial names are every plain-length unit our table uses, the two
#: metric ones the ids the repo already sources; compound units that merely
#: mention feet or inches (feetPerMinute, squareInches, inchesOfWater ...)
#: are other dimensions and deliberately absent.
_LENGTH_DISPLAY_UNITS = ("feet", "feetFractionalInches", "inches", "fractionalInches",
                         "meters", "millimeters")


def _unversioned(type_id: str) -> str:
    """``autodesk.spec.aec:length-1.0.0`` -> ``autodesk.spec.aec:length``."""
    return str(type_id or "").rsplit("-", 1)[0]


@functools.lru_cache(maxsize=1)
def _feet_specs() -> FrozenSet[str]:
    """Spec ids (version-less) the format's OWN units table displays in a
    plain length unit = every spec Revit stores in feet; read once, lazily."""
    with open(ST._UNITS_ASSET, encoding="utf-8") as fh:
        fmap = json.load(fh).get("m_formatOptionsMap") or []
    return frozenset(
        _unversioned(e["first"]["m_typeId"]) for e in fmap
        if _unversioned(e["second"]["m_unitTypeId"]["m_typeId"]).rpartition(":")[2]
        in _LENGTH_DISPLAY_UNITS)


_RE_NUMBER_UNIT = re.compile(r"(-?\d+(?:[.,]\d+)?)\s*([A-Za-z\"']*)")
#: feet-and-inches -- 1'6"  1' 6"  1'-6" -- read as inches through the
#: table's own two marks (#678)
_RE_FEET_INCHES = re.compile(r"(-?)(\d+)\s*'\s*-?\s*(\d+(?:\.\d+)?)\s*\"")
_INCHES_PER_FOOT = _UNIT_TOKENS["'"][1] / _UNIT_TOKENS['"'][1]


def _unwrap_measure(txt: str) -> str:
    """ONE pair of quotes that cleanly WRAPS the value comes off (``"600 mm"``,
    ``'4"'`` -> ``4"``, ``"2'"`` -> ``2'``); nothing else is stripped, so a
    foot / inch MARK reaches ``_UNIT_TOKENS`` like any unit word (``4"``,
    ``2'``, ``1'6"``, ``4 "``) and every other quote arrangement -- ``4''``
    (two apostrophes), ``4'"``, ``''4''``, ``"4""``, a stray ``"600 mm`` -- is
    left for the grammar to REFUSE by name, never read as a value (#678).  A
    pair whose inside starts or ends with the same quote is not a clean wrap."""
    q, inner = txt[:1], txt[1:-1].strip()
    if len(txt) >= 2 and q in "\"'" and txt[-1] == q and q not in (inner[:1], inner[-1:]):
        return inner
    return txt


def _convert_value(param: dict, raw: str) -> Tuple[Any, List[str]]:
    """Turn the prompt's value into the carrier's internal value, spec-driven.
    Returns (value, notes)."""
    notes: List[str] = []
    spec = param["spec"]
    carrier = param["carrier"]
    txt = str(raw).strip()
    if carrier == "m_str":
        # unquote only a value WHOLLY wrapped in one matching pair; any other
        # quote is the user's text ("= 'quoted' value" stays as typed, #1008)
        if (len(txt) >= 2 and txt[0] == txt[-1] and txt[0] in "\"'"
                and txt[0] not in txt[1:-1]):
            # ONE pair around all of it: '"a" and "b"' is two quoted pieces, kept
            txt = txt[1:-1]
        return txt, notes
    txt = _unwrap_measure(txt)
    measurable = carrier != "m_int" and bool(spec) and ":number" not in spec   # a unit MEANS something here
    if measurable and (fi := _RE_FEET_INCHES.fullmatch(txt)):
        # 1'6" == 18": converts on a length, refused by name anywhere else; where a
        # unit is ignored there is no ONE number written, so it stays unreadable
        sign, feet, inch = fi.groups()
        num = int(feet) * _INCHES_PER_FOOT + float(inch)
        num, unit = (-num if sign else num), '"'
    elif (m := _RE_NUMBER_UNIT.fullmatch(txt)):
        num = float(m.group(1).replace(",", ""))
        unit = m.group(2).lower()
    else:
        raise FamilyEditError(
            f"{param['caption']}: cannot read a number from {txt!r}")
    if carrier == "m_int":
        if unit:
            notes.append(f"{param['caption']}: unit {unit!r} ignored (integer parameter)")
        return int(round(num)), notes
    # doubles: spec-driven conversion to Revit internal units
    if "electrical:current" in spec:
        if unit and _UNIT_TOKENS.get(unit, ("", 0))[0] != "current":
            raise FamilyEditError(f"{param['caption']} is a current (amps); got unit {unit!r}")
        return float(num), notes                       # amperes are internal
    if "electrical:potential" in spec:
        if unit and _UNIT_TOKENS.get(unit, ("", 0))[0] != "potential":
            raise FamilyEditError(f"{param['caption']} is a voltage; got unit {unit!r}")
        notes.append(f"{param['caption']}: {num:g} V -> internal x{_ELEC_FACTOR:.6f}")
        return float(num) * _ELEC_FACTOR, notes
    if "electrical:apparent_power" in spec or "apparent" in spec:
        kind, factor = _UNIT_TOKENS.get(unit or "kva", ("apparent_power",
                                                        1000.0 * _ELEC_FACTOR))
        if kind != "apparent_power":
            raise FamilyEditError(f"{param['caption']} is apparent power; got unit {unit!r}")
        notes.append(f"{param['caption']}: {num:g} {unit or 'kVA'} -> internal")
        return float(num) * factor, notes
    key = ":length" if _unversioned(spec) in _feet_specs() else spec   # SIZE specs are feet (#668)
    for marker, kind, offer, internal, caveat in _SPEC_UNITS:
        if marker not in key:
            continue
        if not unit:
            if offer is None:
                return float(num), notes               # bare number stored as given, as before
            raise FamilyEditError(
                f"{param['caption']} is a {kind.upper()}: give an explicit unit "
                f"({offer}) -- units are never guessed")
        got, factor = _UNIT_TOKENS.get(unit, ("", 0.0))
        if got != kind:
            raise FamilyEditError(f"{param['caption']} is a {kind.replace('_', ' ')}; "
                                  f"got unit {unit!r}")
        sep = " " if unit.isalpha() else ""            # 600 mm / 4" / 2' -- a mark hugs its number
        notes.append(f"{param['caption']}: {num:g}{sep}{unit} -> {num * factor:g} "
                     f"{internal}{caveat}")
        return float(num) * factor, notes
    if unit and measurable:                            # measurable, merely unconverted here
        raise FamilyEditError(
            f"{param['caption']}: no conversion for unit {unit!r} on spec {spec} "
            f"(this lane converts: {_converted_units()}) -- give a supported "
            "unit, or a bare number ONLY if it is already in Revit internal "
            "units (internal is not the display unit for most specs); units "
            "are never guessed")
    if unit:                                           # spec-less or Revit's unitless number
        notes.append(f"{param['caption']}: unit {unit!r} ignored (dimensionless spec "
                     f"{spec})")
    return float(num), notes


def _sibling_vocabulary():
    """Poll for a sibling stream's shared vocabulary module."""
    try:
        from . import edit_family as EF                        # type: ignore
        if hasattr(EF, "parse_family_edit"):
            return EF
    except ImportError:
        pass
    return None


_RE_CLAUSE_SEP = re.compile(r";|\n|\bthen\b|,\s*(?=set\b|rename\b)")


def _reads(inv: FamilyInventory, fragment: str) -> bool:
    """Is the fragment after a separator inside a quoted value a further edit
    (#1021)?  A rename; a ``set`` with an explicit ``=`` / ``to`` / ``:`` (``set
    Material = steel`` is a mistyped edit, refused); a ``set`` naming a
    parameter of this family; or one the grammar itself refuses.  ``set screw
    included`` / ``set up later`` is text."""
    c = fragment.strip().rstrip(".")
    if (_RE_RENAME_FAMILY.match(c) or _RE_RENAME_TYPE.match(c)
            or _RE_SET_DELIM_WORD.match(c)):
        return True
    try:
        m = _match_set(inv, c)
    except FamilyEditError:
        return True
    return m is not None and inv.param_by_caption(m.group("cap").strip()) is not None


_RE_SET_DELIM_WORD = re.compile(r"set\s.*?(?:=|:|\sto\s)", re.I | re.S)


def _split_clauses(s: str, inv: FamilyInventory, joined: Optional[set] = None) -> List[str]:
    """Split edit text on ``;``, newlines, ``then`` and ``, set|rename`` -- never
    inside a quoted value (#1017; the rules: :mod:`rvt._quoted`)."""
    return _quoted.split_clauses(s, _RE_CLAUSE_SEP, lambda f: _reads(inv, f), FamilyEditError,
                                 joined)


def parse_family_edit(spec: str, inv: FamilyInventory) -> Dict[str, Any]:
    """Normalise ``spec`` (NL text | inline JSON | ops.json path) into ops:

        {"op": "rename-type",   "type_index": i, "name": str}
        {"op": "rename-family", "name": str}
        {"op": "set-param",     "param_id": id, "caption": str, "carrier": c,
                                "value": converted, "raw": str}

    Delegates to ``rvt.convert.edit_family.parse_family_edit`` when that
    sibling module exists (recorded in the result)."""
    sib = _sibling_vocabulary()
    if sib is not None:
        out = sib.parse_family_edit(spec, inv)
        out.setdefault("vocabulary", "rvt.convert.edit_family (sibling module)")
        return out
    s = str(spec or "").strip()
    if not s:
        raise FamilyEditError("empty edit (give text, inline JSON, or ops.json)")
    ops: List[dict] = []
    understood: List[dict] = []
    notes: List[str] = []
    op_notes: List[List[str]] = []          # the notes each op produced (#994)

    def norm_json_ops(payload) -> List[dict]:
        raw_ops = payload.get("ops") if isinstance(payload, dict) else payload
        if isinstance(raw_ops, dict):
            raw_ops = [raw_ops]
        if not isinstance(raw_ops, list) or not raw_ops:
            raise FamilyEditError("JSON edit must be a non-empty list of ops")
        out = []
        for o in raw_ops:
            op = str(o.get("op") or "").lower()
            mark = len(notes)
            if op in ("rename-type", "rename_type"):
                out.append(_op_rename_type(inv, o.get("type"), str(o.get("name"))))
            elif op in ("rename-family", "rename_family"):
                out.append({"op": "rename-family", "name": str(o.get("name"))})
            elif op in ("set-param", "set_param", "set"):
                out.append(_op_set(inv, str(o.get("param")), str(o.get("value")),
                                   notes,
                                   type_name=o.get("type") or o.get("type_name")))
            else:
                raise FamilyEditError(f"unknown op {op!r} (rename-type | "
                                      "rename-family | set-param)")
            op_notes.append(notes[mark:])
        notes[:] = _settle_overrides(out, op_notes)
        return out

    if os.path.isfile(s) and s.lower().endswith(".json"):
        with open(s) as fh:
            ops = norm_json_ops(json.load(fh))
        return {"ops": ops, "source": "ops-file", "understood": ops,
                "notes": notes, "vocabulary": "rvt.convert.modify_family (built-in)"}
    if s.startswith("[") or s.startswith("{"):
        ops = norm_json_ops(json.loads(s))
        return {"ops": ops, "source": "inline-json", "understood": ops,
                "notes": notes, "vocabulary": "rvt.convert.modify_family (built-in)"}

    unparsed: List[str] = []
    joined: set = set()
    for cl in _split_clauses(s, inv, joined):
        c = cl.rstrip(".")
        mark = len(notes)
        if (m := _RE_RENAME_FAMILY.match(c)):
            op = {"op": "rename-family", "name": m.group("new").strip()}
        elif (m := _RE_RENAME_TYPE.match(c)):
            op = _op_rename_type(inv, m.group("old"), m.group("new").strip())
        elif (m := _match_set(inv, c)):
            cap = m.group("cap").strip()
            if (m.group("val").strip().lower() in ("", "to", "=")
                    and inv.param_by_caption(cap) is not None and _ends_on_delimiter(c)):
                # 'set Finish to' / 'set Finish =': the delimiter is not a value
                # (#1008) -- 'set Finish to to' / '= =' DO give one; a JSON op's
                # empty value stays a deliberate clear
                raise FamilyEditError(
                    f"no value given for {cap!r}: set {cap} = <value> (quote it to store "
                    "the word 'to' itself)")
            op = _op_set(inv, m.group("cap").strip(), m.group("val").strip(), notes,
                         type_name=(m.group("typeq") or m.group("typeq2")
                                    or m.group("type")), clause=c)
        elif cl in joined:
            # kept whole across a ';' / newline / 'then' inside quotes, then
            # unreadable (a newline in the value, a mixed quote in a name):
            # refused, never dropped -- this lane shows no 'unparsed' to the
            # user, so even a clause the old split could not read (an unknown
            # caption with ':') is a refusal here (PR #1018 second review; #1022)
            raise FamilyEditError(
                f"cannot read {cl!r} as one edit: a quoted value here holds a ';' / "
                "newline / 'then' (to store such text, use a JSON set-param op)")
        else:
            unparsed.append(cl)
            continue
        ops.append(op)
        op_notes.append(notes[mark:])
        understood.append({"clause": cl, "op": op})
    notes[:] = _settle_overrides(ops, op_notes)
    if not ops:
        raise FamilyEditError(
            "no family edit understood. Grammar: 'rename the type to NAME', "
            "'rename type OLD to NAME', 'rename the family to NAME', "
            "'set <Parameter> [of type \"T\"] <value> [unit]' -- quote type "
            "names containing spaces (parameters of this file: "
            + ", ".join(p["caption"] for p in inv.params) + "). Unparsed: "
            + "; ".join(unparsed[:4]))
    return {"ops": ops, "source": "text", "understood": understood,
            "unparsed": unparsed, "notes": notes,
            "vocabulary": "rvt.convert.modify_family (built-in; merges into the "
                          "shared rvt.convert.edit_family vocabulary when that "
                          "sibling module lands)"}


_RE_SET_LEAD = re.compile(r"^set\s+(?:the\s+)?", re.I)


#: a SET clause whose parameter is closed by an EXPLICIT delimiter (``to`` /
#: ``=``, optionally after ``of type T``): the parameter is everything before it
_RE_SET_DELIM = re.compile(
    r"^set\s+(?:the\s+)?(?P<cap>[A-Za-z][A-Za-z0-9 _-]*?)"
    r"(?:\s+of\s+type\s+(?:\"(?P<typeq>[^\"]+)\"|'(?P<typeq2>[^']+)'"
    r"|(?P<type>[^\"'\s]+)))?"
    r"(?:\s+to\s+|\s*=\s*)(?P<val>.+?)$", re.I)
_RE_EXPLICIT = re.compile(r"^(?:to\s|=|of\s+type\s)", re.I)


def _match_set(inv: FamilyInventory, clause: str):
    """``_RE_SET`` with the parameter named by the family's OWN captions first
    (#909), so a multi-word caption (``set Strut Length to 36 in``) is never
    cut at its first word by the lazy pattern.  Order: (1) the longest caption
    the clause starts with that is followed by an EXPLICIT delimiter (``to`` /
    ``=`` / ``of type``); (2) a clause with an explicit delimiter names the
    parameter as everything before it -- ``set Material Finish to galvanized``
    is the parameter ``Material Finish`` (refused by name if the family has
    none), never ``Material`` = "Finish to galvanized"; (3) the longest
    caption followed by a bare value (``set Width 600 mm``); (4) the plain
    pattern, as before.

    NO EXCEPTION TO (2) (#994 review): ``set Finish galvanized to spec`` names
    the parameter ``Finish galvanized`` and is refused by name, with a hint
    that the value goes after ``=`` (``set Finish = galvanized to spec``).
    Words after a known caption cannot be told apart from a mistyped
    parameter (``set finish color to black``, ``set Model number to X``) by
    case or vocabulary, and a refusal is recoverable where a mis-targeted
    write is not.

    An UNQUOTED type name after ``of type`` is first resolved against the
    family's own type names (#1006, :func:`_resolve_type_name`), so a generated
    family's ``Conduit - Straight Run 0.75 in 10 ft`` is one name, never cut at
    its first word or folded into the value."""
    clause = _canon_caption_span(inv, clause)
    _refuse_glued_caption(inv, clause)
    lead_n = _RE_SET_LEAD.match(clause)
    if lead_n:
        named = re.sub(r"(?:\s+to|\s*=)$", "",
                       clause[lead_n.end():].strip().rstrip(".;,!?:").rstrip(), flags=re.I)
        named = " ".join(named.split()).lower()        # 'Distance to  Wall' == 'Distance to Wall'
        whole = next((str(p["caption"]).strip() for p in inv.params
                      if " ".join(str(p["caption"]).split()).lower() == named and " " in named),
                     None)
        if whole is not None:
            # the clause IS a multi-word caption, with no value: 'set Distance
            # to Wall' is never Distance = "Wall" when 'Distance to Wall' is a
            # parameter of this family (#1011, from PR #1012's review)
            raise FamilyEditError(
                f"no value given for {whole!r}: set {whole} = <value>")
    clause, qual = _resolve_type_name(inv, clause)
    _start, long_cap = _caption_of_type(inv, clause)
    # quoted ('') or resolved (name) alike: the qualifier reading is decided
    m = _match_set_inner(inv, clause, prefer=long_cap, typed=qual is not None)
    if qual is not None and m is not None and not (
            m.group("typeq") or m.group("typeq2") or m.group("type")):
        # the clause qualified its parameter with a type the grammar did not
        # read: never let it fall through to the default type (#1007 review)
        raise FamilyEditError(
            f"could not read the type in {clause!r}: set <Parameter> of type "
            "\"<type name>\" = <value>")
    if qual and m is not None and (m.group("typeq") or m.group("typeq2")) != qual:
        raise FamilyEditError(f"could not read the type {qual!r} in {clause!r}")
    if m is not None:
        typed = m.group("typeq") or m.group("typeq2") or m.group("type")
        val = m.group("val") or ""
        if not typed and re.match(r"of\s+type\b", val.strip(), re.I):
            # 'set Size of Type' (captions Size / Size of Type): the words
            # 'of Type' are never the VALUE of the shorter caption (#1011)
            raise FamilyEditError(
                f"no value given in {clause!r}, or a value that starts with 'of type' "
                "(quote such a value): set <Parameter> = <value>, or set <Parameter> of "
                "type \"<type name>\" = <value>")
        if typed:
            hit = _ends_in_type(val, [str(n) for n in (getattr(inv, "type_names", None) or [])])
            if hit is not None:
                raise FamilyEditError(
                    f"the value ends in 'of type {hit}', a type of this family: name one "
                    "type, before the value -- set <Parameter> of type \"<type>\" = <value>; "
                    "to store the words as text, quote the value")
    return m


def _word_ends(text: str, i: int) -> bool:
    """A caption (or type name) matched up to ``text[:i]`` ends a WORD there:
    the next character does not continue it.  A word continues through word
    characters, combining marks (an NFD accent: 'A' + U+0301), format
    characters (zero-width joiners) and symbols such as emoji -- else a caption
    ending inside 'Á' or 'A\u200d' would be named and the rest of the word
    written as its value (#1013 review)."""
    if i >= len(text):
        return True
    ch = text[i]
    if ch.isalnum() or ch == "_":
        return False
    cat = unicodedata.category(ch)
    return not (cat[0] == "M" or cat == "Cf" or cat == "So")


#: a quoted span of a value -- an '=' inside it is the value's own text
_RE_QUOTED = re.compile(r"\"[^\"]*\"|'[^']*'")


def _caption_matches(inv: FamilyInventory, body: str) -> List[Tuple[str, int, bool]]:
    """Every caption ``body`` starts with, as ``(caption, end, whole)``: the
    caption's words match with any whitespace between them, case-insensitively,
    and in either Unicode normalisation form (a caption stored NFD matches a
    clause typed NFC and back -- #1013 review); ``end`` is the index in
    ``body`` where the match stops and ``whole`` whether a word ends there
    (:func:`_word_ends`)."""
    out: List[Tuple[str, int, bool]] = []
    for cap in (str(p["caption"]) for p in inv.params):
        words = cap.split()
        if not words:
            continue
        for form in (None, "NFC", "NFD"):
            b = unicodedata.normalize(form, body) if form else body
            ws = [unicodedata.normalize(form, w) for w in words] if form else words
            cm = re.match(r"\s+".join(map(re.escape, ws)), b, re.I)
            if cm is None:
                continue
            end = cm.end()
            if form:                       # the same prefix, in body's own indices
                end = next((i for i in range(len(body) + 1)
                            if unicodedata.normalize(form, body[:i]) == b[:cm.end()]), None)
                if end is None:
                    continue
            out.append((cap, end, _word_ends(body, end)))
            break
    return out


def _refuse_glued_caption(inv: FamilyInventory, clause: str) -> None:
    """Refuse a clause whose caption runs straight into a combining mark, a
    format character or a symbol ('Height' + U+200D, 'Rating' + U+0308, 'Type'
    + an emoji) when NO longer caption of the family is what the user typed
    there ('Size' / 'Size\u2122 Code' reads the long caption): which word was
    meant cannot be told, and every reading writes a cut or orphaned word
    somewhere (#1013 review).  The message names no caption: a guessed
    prefix would point the recovery at a parameter the user did not name."""
    lead = _RE_SET_LEAD.match(clause)
    if not lead:
        return
    body = clause[lead.end():]
    ms = _caption_matches(inv, body)
    for cap, end, whole in ms:
        if end >= len(body):
            continue
        if whole:
            # punctuation glued to the LONGEST caption ('Mark^ 1', 'Mark Note-1')
            # with no other reading writes the user's punctuation into the
            # value (#1014): refused -- unless a longer caption is what was
            # typed, or a shorter caption reads it with to / '=' ('Distance
            # to Wall-mounted box' is Distance = "Wall-mounted box")
            ch = body[end]
            if (ch.isspace() or ch in ":=\"'"
                    or any(e > end and w for _c, e, w in ms)
                    or any(e < end and body[e:e + 1].isspace()
                           and re.match(r"(?:to\s|=)", body[e:].lstrip(), re.I)
                           for _c, e, _w in ms)):
                continue
            raise FamilyEditError(
                f"a parameter name runs straight into {ch!r}: put a space or '=' "
                "between the parameter and its value -- set <Parameter> = <value>")
        ch = body[end]
        if ch.isalnum() or ch == "_":
            continue                       # a letter: the ordinary grammar reads it
        if any(e > end and w for _c, e, w in ms):
            continue                       # a longer caption IS what was typed
        raise FamilyEditError(
            f"a parameter name runs straight into the character U+{ord(ch):04X}: name "
            "the parameter in full, then a space or '=' before the value -- "
            "set <Parameter> = <value>")


def _canon_caption_span(inv: FamilyInventory, clause: str) -> str:
    """``clause`` with the caption it starts with (the LONGEST that ends a
    word, matched with any whitespace and in either Unicode normalisation form)
    rewritten with single spaces, so every later step -- type resolution
    included -- sees one form (``set Distance  to  Wall of type T 1 = 4``,
    #1013 review).  The user's own words and casing are kept; when they differ
    from the stored caption only in normalisation form, the stored caption's
    text is used.  Only the caption span changes; the value is never touched."""
    lead = _RE_SET_LEAD.match(clause)
    if not lead:
        return clause
    body = clause[lead.end():]
    best = None
    for cap, end, whole in _caption_matches(inv, body):
        if whole and (best is None or len(" ".join(cap.split())) > len(" ".join(best[0].split()))):
            best = (cap, end)
    if best is None:
        return clause
    cap, end = best
    typed = " ".join(body[:end].split())
    if typed.lower() != " ".join(cap.split()).lower():
        typed = " ".join(cap.split())      # another normalisation form: the stored text
    return clause[:lead.end()] + typed + body[end:]


def _match_set_inner(inv: FamilyInventory, clause: str, prefer: Optional[str] = None,
                     typed: bool = False):
    """:func:`_match_set`'s grammar on a clause whose type name is resolved.
    ``prefer`` = a caption containing "of type" that the clause names
    (:func:`_caption_of_type`): a shorter caption whose remainder starts with
    "of type" is then not a reading (#1011: ``set Size of Type 5 mm``).
    ``typed`` = :func:`_resolve_type_name` already quoted a family type in, so
    the qualifier reading is decided and the longest-caption rule stands down."""
    lead = _RE_SET_LEAD.match(clause)
    caps: List[Tuple[str, str]] = []
    whole_word: set = set()
    if lead:
        body = clause[lead.end():]
        low = body.lower()
        for cap in sorted((p["caption"] for p in inv.params), key=len, reverse=True):
            words = str(cap).split()
            if not words:
                continue
            cm = re.match(r"\s+".join(map(re.escape, words)), body, re.I)
            if cm is not None and _word_ends(body, cm.end()):                     # any whitespace between the words
                rest = body[cm.end():].lstrip()
                glued = body[cm.end():cm.end() + 1] == ":"
                if glued and not caps and re.match(r"(?:to\s|=)", rest[1:].strip() + " ", re.I):
                    # 'set Note to A: to x' / ':= x': two delimiters -- the value
                    # cannot be told (#1016 review); a LONGER caption that
                    # matched ('Note:' in 'set Note: = x') reads it instead
                    raise FamilyEditError(
                        "two delimiters after the parameter: set <Parameter> = <value>")
                if glued and not rest[1:].strip():
                    # 'set Note:' -- never a blank or ':' write, whichever caption
                    # ('Note' or 'Note:') was meant (#1016 review)
                    raise FamilyEditError("no value given: set <Parameter> = <value>")
                if glued and not caps:
                    # a colon GLUED to the caption: 'Tray Type: 1' == 'Tray Type = 1'
                    # (#1014); after a space it is the value's own ('set Note :)').
                    # Only when no LONGER caption already matched ('set Note:
                    # A"x"' with captions Note / Note: A is Note: A, #1016 review).
                    # Type names keep main's grammar (no colon delimiter, #1016).
                    after = rest[1:].strip()
                    pre = " ".join(cap.split()).lower() + ":"
                    if "=" in _RE_QUOTED.sub("", after) and any(
                            " ".join(str(p["caption"]).split()).lower().startswith(pre)
                            and len(" ".join(str(p["caption"]).split())) > len(pre)
                            for p in inv.params):
                        # 'set Note: Installs = x' with a caption 'Note: Install':
                        # a mistyped longer caption, never Note = "Installs = x"
                        raise FamilyEditError(
                            f"no parameter {(cap + ': ' + after.split('=')[0].strip())!r} in "
                            "this family: name the parameter exactly -- set <Parameter> = <value>")
                    rest = "= " + rest[1:].lstrip()
                caps.append((cap, rest))
                if re.match(r"\s|$|[:=]", body[cm.end():]):
                    whole_word.add(cap)            # ends at a word boundary the user typed
    if len(caps) > 1 and not typed:
        # the LONGEST caption the clause names, followed by a bare value, is the
        # parameter: 'set Distance to Wall 3 ft' is never Distance = "Wall 3 ft"
        # (#1013 review).  If that value itself holds a to / '=', the shorter
        # caption's delimiter reading is just as possible: refuse, naming both.
        lcap, lrest = max(caps, key=lambda cr: len(" ".join(str(cr[0]).split())))
        lrest_s = lrest.strip().lstrip(":").strip()
        # only a caption that ENDS where the user ended a word: 'Distance to
        # Wall-mounted box' is Distance = "Wall-mounted box" (#1013 review)
        if lcap in whole_word and lrest_s and not _RE_EXPLICIT.match(lrest_s) and not (
                prefer and lcap.strip().lower() != prefer.strip().lower()):
            if _RE_DELIM_AHEAD.search(" " + lrest_s) and any(
                    c != lcap and _RE_EXPLICIT.match(r) for c, r in caps):
                # a SHORTER caption followed by to / '=' reads it too
                # ('Distance to Wall height to 3'); with none ('Mark Note x to
                # red'), the long caption is the only reading
                raise FamilyEditError(
                    f"{clause!r} reads two ways: parameter {lcap!r} with value "
                    f"{lrest_s!r}, or a shorter parameter -- write set {lcap} = <value>")
            lm = _RE_SET.match("set P " + lrest_s)
            if lm is not None:
                return _CaptionMatch(lm, lcap)
    if prefer:
        caps = [(c, r) for c, r in caps if c.strip().lower() == prefer.strip().lower()
                or not re.match(r"of\s+type\b", r, re.I)]
    for cap, rest in caps:
        if _RE_EXPLICIT.match(rest):
            m = _RE_SET.match("set P " + rest)
            if (m is not None and re.match(r"to\s", rest, re.I)
                    and "=" in _RE_QUOTED.sub("", m.group("val") or "")):
                # 'set Distance to Walls = 5' with a caption 'Distance to Wall':
                # the user named a longer parameter, mistyped -- never Distance
                # = "Walls = 5" (#1014)
                pre = " ".join(cap.split()).lower() + " to "
                if any(" ".join(str(p["caption"]).split()).lower().startswith(pre)
                       for p in inv.params):
                    raise FamilyEditError(
                        f"no parameter {' '.join(clause.split('=')[0].split()[1:])!r} in this "
                        "family: name the parameter exactly -- set <Parameter> = <value>")
            if m is not None:
                if re.match(r"of\s+type\s", rest, re.I) and not (
                        m.group("typeq") or m.group("typeq2") or m.group("type")):
                    continue        # 'of Type 5' read as a VALUE of 'Size': not this caption (#1010)
                return _CaptionMatch(m, cap)
    m = _RE_SET_DELIM.match(clause)
    if m is not None:
        return m
    for cap, rest in caps:
        m = _RE_SET.match("set P " + rest)
        if m is not None:
            return _CaptionMatch(m, cap)
    return _RE_SET.match(clause)


#: the first ``of type T`` qualifier inside a refused clause's tail (#1003)
_RE_OF_TYPE = re.compile(r"(?:^|\s+)of\s+type\s+(?P<t>\"[^\"]+\"|'[^']+'|[^\"'\s]+)", re.I)


_RE_OF_TYPE_AT = re.compile(r"\s+of\s+type\s+", re.I)
_RE_DELIM_AHEAD = re.compile(r"\s+to\s+|\s*=", re.I)
#: what may follow a family type name typed unquoted: the end, ``to``, ``=``
#: (spaces optional before it), or one space and a bare value
_RE_AFTER_NAME = re.compile(r"(?P<to>\s+to\s+)|(?P<eq>\s*=\s*)|(?P<sp>\s+)|(?P<end>$)", re.I)


def _refuse_type(named: str, types: Sequence[str]):
    raise FamilyEditError(
        f"'of type {named}' is not a type of this family "
        f"({', '.join(map(repr, types)) or 'no types'}): name a type exactly, "
        "quoted when it has spaces -- e.g. set <Parameter> of type \"<type name>\" = <value>")


def _quote_type_name(inv: FamilyInventory, clause: str) -> str:
    """``clause`` with an unquoted family type name quoted in, or a
    :class:`FamilyEditError` -- the clause half of
    :func:`_resolve_type_name` (#1006), for the refusal hint."""
    return _resolve_type_name(inv, clause)[0]


def _caption_of_type(inv: FamilyInventory, clause: str) -> Tuple[int, Optional[str]]:
    """``(start, caption)``: when the clause names one of the family's captions
    that itself contains "of type" (``Size of Type``), the position after it
    -- where a qualifier may begin -- and that caption; else ``(0, None)``
    (#1009).  When a SHORTER caption reads the same words as caption + type
    qualifier (captions Size / Size of Type, ``set Size of type Big One = 5``),
    that reading wins (#1010) -- unless the long caption ALSO reads (it is
    followed by ``to`` / ``=``, or both readings take a bare value): then the
    clause is refused, naming both readings (#1011)."""
    lead0 = _RE_SET_LEAD.match(clause)
    if not lead0:
        return 0, None
    type_lows = [str(n).strip().lower() for n in (getattr(inv, "type_names", None) or [])
                 if str(n).strip()]
    cap_lows = {str(p["caption"]).strip().lower() for p in inv.params}
    body0 = clause[lead0.end():].lower()
    for cap in sorted((str(p["caption"]).strip() for p in inv.params), key=len, reverse=True):
        c = cap.lower()
        if not (c and body0.startswith(c) and (len(body0) == len(c)
                                                 or _word_ends(body0, len(c)))):
            continue
        inner = list(re.finditer(r"\s+of\s+type\b", c))
        if not inner:
            continue
        before, after = c[:inner[-1].start()].strip(), body0[inner[-1].end():].lstrip()
        if before in cap_lows:
            for t in sorted(type_lows, key=len, reverse=True):
                qt = (after[:1] if after[:1] in "\"'" else "")
                tt = qt + t + qt                      # a QUOTED type reads the same way
                if after.startswith(tt) and (len(after) == len(tt)
                                             or _word_ends(after, len(tt))):
                    if qt:
                        return 0, None    # quoted by the user: unambiguously the qualifier
                    q_rest = after[len(t):]
                    q_bare = not re.match(r"\s*(=|to\s)", q_rest + " ", re.I)
                    long_rest = body0[len(c):]
                    long_delim = bool(re.match(r"\s*(=|to\s)", long_rest + " ", re.I))
                    if long_delim or (q_bare and long_rest.strip()):
                        raise FamilyEditError(
                            f"{clause!r} reads two ways: parameter {cap!r}, or parameter "
                            f"{before!r} of type {t!r} -- quote the type to mean the second "
                            f"(set <Parameter> of type \"<type>\" = <value>) or write "
                            f"set {cap} = <value> for the first")
                    return 0, None
        return lead0.end() + len(c), cap
    return 0, None


def _ends_in_type(value: str, names: Sequence[str]) -> Optional[str]:
    """The family type ``value`` ends in after its LAST ``of type`` (quoted or
    not, trailing punctuation dropped), else ``None`` (#1007 B2, #1011)."""
    ms = list(re.finditer(r"(?:^|\s)of\s+type\s+", value, re.I))
    if not ms:
        return None
    last = value[ms[-1].end():].strip().lower().rstrip(".!?,;:").strip()
    if len(last) >= 2 and last[0] == last[-1] and last[0] in "\"'":
        last = last[1:-1].strip()
    return next((n for n in names if n.strip().lower() == last), None)


def _resolve_type_name(inv: FamilyInventory, clause: str) -> Tuple[str, Optional[str]]:
    """Resolve the ``of type`` qualifier of a set clause (#1006, #1007).

    Returns ``(clause, qualifier)``: ``clause`` with an UNQUOTED ``of type
    NAME`` rewritten to the grammar's quoted form when NAME is one of the
    family's own type names (#1006), or
    refused by name -- never a name cut short with the rest written into the
    value, never a clause folded into the default type's value.

    * Only the ``of type`` that qualifies the PARAMETER counts: the one before
      any ``=`` or quote, and before any ``to`` unless the words before it are
      exactly one of the family's captions (``Distance to Wall``).  An ``of
      type`` inside the value is the user's text and is left alone.
    * A family type name matches case-insensitively and must be followed by
      the end, ``to``, ``=`` (``Big One=black`` too), or one space and a bare
      value.  Longest first.  A name followed by MORE words and then a
      delimiter (``Big One XLL to black`` -- the user typed a longer name) is
      not a match; if nothing else fits, the clause is refused.  In the bare
      form a name followed by a word that begins (or extends) the next word
      of a longer type of this family (``Big One XL`` / ``Big One XLL``)
      cannot be told from that longer name, and a bare value of several words that starts with a word
      (``Default Extra black``) cannot be told from a longer mistyped name,
      so both are refused (``of type T1 3 ft`` and ``= <value>`` still work).
    * With no family name matching: an unquoted name of more than one word
      before ``to`` / ``=``, or (no delimiter) a first word that is not
      exactly a type, is refused.  A single word before the delimiter
      (``of type T1 to 5``) is left to the grammar, which refuses a name that
      matches no type.

    ``qualifier`` is ``None`` when the clause has no ``of type`` qualifying
    its parameter, the resolved type name when one was quoted in, and ``""``
    when a qualifier was left to the grammar (quoted by the user, or one exact
    word).  :func:`_match_set` refuses any clause whose qualifier the grammar
    did not read, so a typed clause never falls into the default type.
    Also refused: a type named with no value; a value that ENDS in ``of type
    <a type of this family>`` (quoted or not); two valid readings (``X`` /
    ``X to Y``); a head before ``of type`` that is not a caption + ``to`` /
    ``=`` when the tail names a type (``Finish's color of type Big One``); and
    any single word before ``to`` / ``=`` that is not exactly a type (no
    substring match -- ``T1`` never reaches ``T10``)."""
    start, _cap = _caption_of_type(inv, clause)
    m = _RE_OF_TYPE_AT.search(clause, start)
    if m is None:
        return clause, None
    types = [str(n) for n in (getattr(inv, "type_names", None) or []) if str(n).strip()]
    names = sorted({n.strip() for n in types}, key=len, reverse=True)
    tail = clause[m.end():]
    low = tail.lower()
    head = clause[:m.start()]
    lead = _RE_SET_LEAD.match(head)
    words_head = head[lead.end():].strip() if lead else head.strip()
    in_value = ("=" in head or '"' in head or "'" in head
                or (re.search(r"\bto\b", words_head, re.I) and not any(
                    str(p["caption"]).strip().lower() == words_head.lower() for p in inv.params)))
    if in_value:
        # Only a head that is a COMPLETE set clause -- one of the family's
        # captions, then to / '=' -- puts this 'of type' inside a value.  A
        # head like "Finish's color" or "Route to Panel name" is not one: if
        # the tail starts with a type of this family, the clause cannot be
        # read safely and is refused, never written to the default type
        # (#1007 review, B3).
        wl = words_head.lower()
        real_value = any(
            wl.startswith(c) and re.match(r"\s+to\s|\s*=", wl[len(c):] + " ")
            for c in (str(p["caption"]).strip().lower() for p in inv.params) if c)
        if not real_value:
            if any(low.startswith(n.lower()) and _RE_AFTER_NAME.match(tail, len(n))
                   for n in names):
                raise FamilyEditError(
                    f"could not read {words_head!r} as one of this family's parameters "
                    "before 'of type': set <Parameter> of type \"<type name>\" = <value>")
            return clause, None
        # 'of type' inside the VALUE is the user's text -- unless the value
        # ENDS in 'of type <a type of this family>', quoted or not: then the
        # user may have meant that type, and writing the phrase into the
        # default type is the mis-target #1006 retires (#1007 review, B2)
        # the LAST 'of type' in the value, trailing punctuation dropped
        # ('black of type Big One!', 'x of type steel of type Big One')
        lm = list(_RE_OF_TYPE_AT.finditer(clause))[-1]
        last = clause[lm.end():].strip().lower().rstrip(".!?,;:").strip()
        if len(last) >= 2 and last[0] == last[-1] and last[0] in "\"'":
            last = last[1:-1].strip()
        if last in {n.lower() for n in names}:
            shown = next(n for n in names if n.lower() == last)
            raise FamilyEditError(
                f"the value ends in 'of type {shown}', a type of this family: to set "
                "that type, put the type before the value -- set <Parameter> of type "
                f"\"{shown}\" = <value>; to store the words as text, quote the value")
        return clause, None
    if clause[m.end():m.end() + 1] in ("\"", "'"):
        return clause, ""                 # quoted: the grammar reads it; the backstop checks it did
    for n in names:
        if not low.startswith(n.lower()):
            continue
        after = _RE_AFTER_NAME.match(tail, len(n))
        if after is None:
            continue                                      # 'Big One-x', 'Big One.': not this name
        rest = tail[after.end():]
        if after.group("sp") is not None:
            if _RE_DELIM_AHEAD.search(rest):
                continue                                  # more words, then to/= : a longer name
            vw = rest.split()
            nxt = vw[0].lower() if vw else ""
            # a longer type of this family whose next word the typed word could
            # be (or start): 'Big One XLL' vs 'Big One XL' -- 'black' vs 'Long' is not
            longer = [o for o in names if len(o) > len(n) and o.lower().startswith(n.lower() + " ")
                      and nxt and (o[len(n):].split()[0].lower().startswith(nxt)
                                   or nxt.startswith(o[len(n):].split()[0].lower()))]
            if longer or (len(vw) > 1 and vw[0][:1].isalpha()):
                # a bare value of several words that starts with a word could
                # be the rest of a longer (mistyped) type name: refuse, '='
                # says it unambiguously ("of type T1 3 ft" still parses)
                _refuse_type(n + (" " + vw[0] if vw else "") + " ...", types)
        if not rest.strip() or rest.strip().lower() in ("to", "="):
            raise FamilyEditError(
                f"no value given for type {n!r}: set <Parameter> of type \"{n}\" = <value>")
        if after.group("sp") is None:
            # a SHORTER type of this family that also reads with a to / '=' is
            # a second valid parse ('X' / 'X to Y' in 'of type X to Y to z'):
            # refuse rather than pick (#1007 review)
            for s2 in names:
                if len(s2) < len(n) and low.startswith(s2.lower()):
                    a2 = _RE_AFTER_NAME.match(tail, len(s2))
                    if (a2 is not None and a2.group("sp") is None
                            and tail[a2.end():].strip()):
                        raise FamilyEditError(
                            f"'of type {tail[:after.start()].strip()} ...' reads as type {n!r} or "
                            f"type {s2!r}: quote the type -- set <Parameter> of type \"{n}\" = "
                            "<value>")
        if '"' in n and "'" in n:
            _refuse_type(n, types)
        q = "'" if '"' in n else '"'
        sep = (" to " if after.group("to") is not None
               else " = " if after.group("eq") is not None
               else " " if after.group("sp") is not None else "")
        return clause[:m.end()] + q + n + q + sep + rest, n
    d = _RE_DELIM_AHEAD.search(tail)
    if d is not None:
        named = tail[:d.start()].strip()
        if (len(named.split()) > 1 or any(c in named for c in ".,;")
                or named.lower() not in {n.lower() for n in names}):
            _refuse_type(named, types)
        return clause, ""
    words = tail.split()
    if len(words) > 1 and words[0].lower() not in {n.lower() for n in names}:
        _refuse_type(words[0] + " ...", types)
    if len(words) < 2:
        raise FamilyEditError(
            f"no value given for 'of type {tail.strip()}': set <Parameter> of type "
            "\"<type name>\" = <value>")
    return clause, ""


def _ends_on_delimiter(clause: str) -> bool:
    """``clause`` ends on a ``to`` / ``=`` delimiter with no value after it:
    the text before that last token does not itself end on a delimiter
    (``set Finish to`` yes; ``set Finish to to`` / ``set Finish = =`` no)."""
    t = clause.strip().rstrip(".;,!").rstrip()
    m = re.search(r"(?:\s+to|\s*=)$", t, re.I)
    if m is None:
        return False
    rest = t[:m.start()].rstrip()
    return re.search(r"(?:\s+to|=)$", rest, re.I) is None


def _value_hint(inv: FamilyInventory, caption: str, clause: Optional[str] = None) -> str:
    """For a refused ``caption`` that starts with one of the family's own
    captions (``Finish galvanized``), name the recovery: the words after a
    known caption may be part of a VALUE (``set Finish galvanized to spec``),
    but nothing in the clause tells that apart from a mistyped parameter
    (``set finish color to black``), so the edit is refused, never guessed
    (#994 review) -- the hint says how to write the value unambiguously.  The
    example is the user's own ``clause`` with ``=`` after the caption, so it
    keeps whichever delimiter they wrote (#1000)."""
    low = caption.lower()
    for cap in sorted((p["caption"] for p in inv.params), key=len, reverse=True):
        c = cap.lower()
        if c and low.startswith(c) and len(low) > len(c) and low[len(c)].isspace():
            if clause:
                try:
                    clause = _quote_type_name(inv, clause)       # a full type name stays one (#1006)
                except FamilyEditError:
                    pass
            at = (clause or "").lower().find(low)
            rest = (clause[at + len(cap):].strip() if at >= 0 else "<value>")
            # an 'of type T' qualifier stays the TYPE, in its parsed position
            # (before the '='), never folded into the value (#1003)
            q = _RE_OF_TYPE.search(rest)
            of = ""
            if q is not None:
                of = " of type " + q.group("t")
                rest = (rest[:q.start()] + rest[q.end():]).strip()
            return (f" -- if the words after {cap!r} are part of its VALUE, write the "
                    f"value after '=': set {cap}{of} = {rest}")
    return ""


class _CaptionMatch:
    """A ``_RE_SET`` match whose ``cap`` group is the family's own caption."""

    def __init__(self, m, cap: str):
        self._m, self._cap = m, cap

    def group(self, name: str):
        return self._cap if name == "cap" else self._m.group(name)


def _op_rename_type(inv: FamilyInventory, old: Optional[str], new: str) -> dict:
    if not inv.type_names:
        raise FamilyEditError("this family has no type-table types to rename "
                              + ("(" + "; ".join(inv.notes) + ")" if inv.notes else ""))
    if old:
        # EXACT (case-insensitive) only, as for a set (#1007): a substring
        # ('T1' in 'T10') would rename a type the user did not name (#1009)
        key = str(old).strip().strip("\"'").strip().lower()
        hits = [i for i, n in enumerate(inv.type_names) if n.strip().lower() == key]
        if len(hits) != 1:
            raise FamilyEditError(f"type {old!r} is not exactly one of this family's types "
                                  f"{inv.type_names}: name it exactly")
        idx = hits[0]
    elif len(inv.type_names) == 1:
        idx = 0
    else:
        raise FamilyEditError(f"the family has {len(inv.type_names)} types "
                              f"{inv.type_names}: say which ('rename type OLD to NEW')")
    return {"op": "rename-type", "type_index": idx,
            "old": inv.type_names[idx], "name": new}


def _op_set(inv: FamilyInventory, caption: str, raw: str, notes: List[str],
            type_name: Optional[str] = None, clause: Optional[str] = None) -> dict:
    p = inv.param_by_caption(caption)
    if p is None:
        raise FamilyEditError(
            f"no parameter {caption!r} in this family. Parameters: "
            + ", ".join(q["caption"] for q in inv.params)
            + _value_hint(inv, caption, clause))
    if p.get("formula"):
        raise FamilyEditError(
            f"{p['caption']} is a FORMULA parameter: Revit computes it from the "
            "parameters its formula reads -- set those instead (#909)")
    val, conv_notes = _convert_value(p, raw)
    notes.extend(conv_notes)
    op = {"op": "set-param", "param_id": p["param_id"], "caption": p["caption"],
          "carrier": p["carrier"], "spec": p["spec"], "value": val, "raw": raw}
    if type_name:
        key = str(type_name).strip().strip("\"'").lower()
        # EXACT (case-insensitive) only: a substring ('T1' in 'T10', 'One' in
        # 'Big One') would write to a type the user did not name (#1007 review)
        hits = [n for n in inv.type_names if n.strip().lower() == key]
        if len(hits) != 1:
            raise FamilyEditError(
                f"'of type {type_name}' is not exactly one of this family's types "
                f"{inv.type_names}: name the type exactly (quote names containing spaces)")
        op["type_name"] = hits[0]
        notes.append(f"{p['caption']}: scoped to type {hits[0]!r} -- the current-"
                     "defaults row (m_familyParams) is left as-is for a scoped edit")
    return op


def _op_target(op: dict) -> tuple:
    kind = op["op"]
    if kind == "set-param":
        return ("set", int(op["param_id"]), op.get("type_name"))
    if kind == "rename-type":
        return ("type", int(op["type_index"]))
    return (kind,)


def _overrides(later: dict, earlier: dict) -> bool:
    """``later`` writes everything ``earlier`` wrote: the same parameter (an
    unscoped set covers every type, a scoped one only its own type), the same
    type's name, or the family name."""
    a, b = _op_target(later), _op_target(earlier)
    if a[0] != b[0]:
        return False
    if a[0] == "set":
        return a[1] == b[1] and (a[2] is None or a[2] == b[2])
    return a == b


def _op_shown(op: dict) -> Tuple[str, str]:
    kind = op["op"]
    if kind == "set-param":
        return op["caption"], str(op.get("raw"))
    if kind == "rename-type":
        return f"type name {op.get('old')!r}", str(op["name"])
    return "family name", str(op["name"])


def _settle_overrides(ops: List[dict], op_notes: Sequence[Sequence[str]]) -> List[str]:
    """The last op on a target wins (#994): every op a LATER op of the same
    edit overrides is marked ``overridden_by`` (the later op's 1-based number)
    and is applied by nobody; its own notes (unit conversion, the geometry
    statement the route adds to them) are replaced by ONE note saying it was
    overridden -- a note about a value the file does not carry would be false.
    Returns the edit's notes, in op order."""
    notes: List[str] = []
    for i, op in enumerate(ops):
        later = next((j for j in range(i + 1, len(ops)) if _overrides(ops[j], op)), None)
        if later is None:
            notes.extend(op_notes[i] if i < len(op_notes) else ())
            continue
        op["overridden_by"] = later + 1
        what, val = _op_shown(op)
        _w, val2 = _op_shown(ops[later])
        notes.append(f"{what}: {val!r} (op {i + 1}) is overridden by a later op in the "
                     f"same edit (op {later + 1}: {val2!r}) -- the last one wins; nothing "
                     "of op " + str(i + 1) + " is written")
    return notes


def _effective_ops(ops: Sequence[dict]) -> List[dict]:
    """``ops`` without the ones a later op of the same edit overrides."""
    return [o for o in ops if not o.get("overridden_by")]


# ---------------------------------------------------------------------------
# apply: ONE manipulate commit + the PartAtom follow
# ---------------------------------------------------------------------------

def apply_family_edits(inv: FamilyInventory, ops: Sequence[dict],
                       out_path: str) -> Dict[str, Any]:
    """Apply ``ops`` to ``inv``'s file -> ``out_path`` through rvt.manipulate
    (one commit), then keep PartAtom in step.  Returns the apply record."""
    from .. import manipulate as M
    doc = inv.doc
    fam = inv.family_id
    fv = doc.value(fam) or {}
    ftt = ((fv.get("m_pFamilyTypes") or {}).get("value") or {})
    pairs = ftt.get("m_pairs") or []
    changes: Dict[str, Any] = {}
    #: PartAtom follows, SCOPED (#994): a type rename touches only its type's
    #: entry, a family rename only the family-level elements -- in generated
    #: families the type name equals the family title, so a plain text replace
    #: renamed both.  Keyed by target, so the last op on a target wins.
    type_renames: Dict[int, Tuple[str, str]] = {}
    new_family_name: Optional[str] = None
    applied: List[dict] = []

    for op in _effective_ops(ops):
        kind = op["op"]
        if kind == "rename-type":
            i = int(op["type_index"])
            changes[f"m_pFamilyTypes.value.m_pairs[{i}].name"] = op["name"]
            type_renames[i] = (str(inv.type_names[i] if i < len(inv.type_names)
                                   else op.get("old")), op["name"])
            applied.append(op)
        elif kind == "rename-family":
            new_family_name = op["name"]
            fam_rec_name = str(fv.get("m_name") or "")
            if fam_rec_name:
                changes["m_name"] = op["name"]
            applied.append(dict(op, note=(
                "family display name = PartAtom title + the file name; the "
                "self-Family m_name is "
                + ("also rewritten" if fam_rec_name else "empty in generated "
                   "families (left empty)"))))
        elif kind == "set-param":
            pid = int(op["param_id"])
            carrier = op["carrier"]
            scope = op.get("type_name")
            hit = False
            for i, pr in enumerate(pairs):
                if scope and str(pr.get("name")) != scope:
                    continue
                rows = ((pr.get("params") or {}).get("m_params") or [])
                for j, row in enumerate(rows):
                    if int(row.get("m_paramId", -1)) == pid:
                        changes[f"m_pFamilyTypes.value.m_pairs[{i}].params"
                                f".m_params[{j}].{carrier}"] = op["value"]
                        hit = True
            if not scope:
                # unscoped: the current-type defaults follow the type table
                fp_rows = (((fv.get("m_familyParams") or {}).get("value") or {})
                           .get("m_params") or [])
                for k, row in enumerate(fp_rows):
                    if int(row.get("m_paramId", -1)) == pid:
                        changes[f"m_familyParams.value.m_params[{k}].{carrier}"] = op["value"]
                        hit = True
            if not hit:
                raise FamilyEditError(
                    f"{op['caption']}: parameter {pid} has no value row in "
                    + (f"type {scope!r}" if scope else
                       "the type table or the current defaults")
                    + " -- nothing to set")
            applied.append(op)
        else:                                                  # pragma: no cover
            raise FamilyEditError(f"unknown op {kind!r}")

    formula_notes = _formula_followups(inv, fv, pairs, _effective_ops(ops), changes)
    if not changes and new_family_name is not None:
        # a generated family's self-Family m_name is empty: a family rename
        # alone changes no record -- the name lives in PartAtom (+ the file
        # name), so the edit is a byte copy with PartAtom kept in step
        import shutil
        shutil.copyfile(inv.path, out_path)
        rec = {"applied": applied, "record_changes": {},
               "commit": {"out": _relp(out_path), "blocks": 0,
                          "note": "no record changes (the family name lives in "
                                  "PartAtom and the file name)"}}
        rec["partatom"] = _patch_partatom_scoped(out_path, new_family_name, type_renames)
        return rec
    if not changes:
        raise FamilyEditError("the ops produced no record changes")
    plan = M.modify_element(doc, fam, changes, kind="family-edit",
                            reason="rvt.convert.modify_family")
    crep = M.commit_plans(inv.path, out_path, [plan])
    rec: Dict[str, Any] = {
        "applied": applied,
        "record_changes": {k: v for k, v in changes.items()},
        "commit": {"out": _relp(out_path),
                   "blocks": getattr(crep, "n_blocks", None)},
    }
    if formula_notes:
        rec["formula_followups"] = formula_notes
    ver = M.verify_manipulated(out_path, edited_ids=[fam])
    rec["structural_verify"] = {k: ver.get(k) for k in
                                ("crc_failures", "ecc_mismatches", "walker_errors",
                                 "stamps_ok", "elemtable_count", "header_count")}
    rec["structural_ok"] = bool(
        ver.get("crc_failures") == 0 and ver.get("ecc_mismatches") == 0
        and not ver.get("walker_errors") and ver.get("stamps_ok")
        and ver.get("elemtable_count") == ver.get("header_count"))

    # ---- PartAtom follow (names in the Atom-XML metadata) -----------------
    if type_renames or new_family_name is not None:
        rec["partatom"] = _patch_partatom_scoped(out_path, new_family_name, type_renames)
    return rec


def _formula_followups(inv: FamilyInventory, fv: Dict[str, Any], pairs: List[dict],
                       ops: Sequence[dict], changes: Dict[str, Any]) -> List[str]:
    """Re-evaluate every FORMULA parameter the set-param ops feed (``Nut Across
    Flats`` -> ``Nut Half Across Flats``, #909) in each row set the ops wrote --
    every type row (or the scoped one) and, unscoped, the current defaults --
    with the file's own expression trees, adding the results to ``changes``.
    Returns notes: one per followed formula, and any it could not compute."""
    from . import family_regen as FR
    sets = [o for o in ops if o.get("op") == "set-param"]
    if not sets:
        return []
    carriers = {int(p["param_id"]): p["carrier"] for p in inv.params}
    caps = {int(p["param_id"]): p["caption"] for p in inv.params}
    notes: List[str] = []
    row_sets: List[Tuple[str, List[dict], Dict[int, Any]]] = []
    for i, pr in enumerate(pairs):
        edits = {int(o["param_id"]): o["value"] for o in sets
                 if not o.get("type_name") or str(pr.get("name")) == o["type_name"]}
        if edits:
            row_sets.append((f"m_pFamilyTypes.value.m_pairs[{i}].params.m_params",
                             ((pr.get("params") or {}).get("m_params") or []), edits))
    unscoped = {int(o["param_id"]): o["value"] for o in sets if not o.get("type_name")}
    if unscoped:
        row_sets.append(("m_familyParams.value.m_params",
                         (((fv.get("m_familyParams") or {}).get("value") or {})
                          .get("m_params") or []), unscoped))
    seen = set()
    for base, rows, edits in row_sets:
        follow, fnotes = FR.formula_followups(rows, edits, carriers)
        for n in fnotes:
            if n not in notes:
                notes.append(n)
        for pid, val in follow.items():
            for j, row in enumerate(rows):
                if int(row.get("m_paramId", -1)) == pid:
                    changes[f"{base}[{j}].{carriers.get(pid, 'm_value')}"] = val
            if pid not in seen:
                seen.add(pid)
                shown = f" -> {val:g}" if isinstance(val, (int, float)) else ""
                notes.append(f"{caps.get(pid, pid)}: re-evaluated by its formula from "
                             f"the edited value{shown}")
    return notes


def _patch_partatom(path: str, renames: Sequence[Tuple[str, str]]) -> Dict[str, Any]:
    """Rewrite name occurrences inside the PartAtom stream (plain XML,
    unframed) and rebuild the container in place (the rebuilt bytes reach
    ``path`` by an atomic replace, so a failed write cannot tear the file)."""
    from ..container import open_rvt
    from ..roundtrip import rewrite_entries
    with open_rvt(path) as f:
        xml = f.raw("PartAtom").decode("utf-8")
    out_xml = xml
    replaced: List[dict] = []
    for old, new in renames:
        if not old:
            continue
        n = out_xml.count(old)
        if n:
            out_xml = out_xml.replace(old, new)
        replaced.append({"old": old, "new": new, "occurrences": n})
    if out_xml == xml:
        return {"changed": False, "replaced": replaced,
                "note": "no PartAtom occurrence of the renamed strings"}
    data = out_xml.encode("utf-8")
    rewrite_entries(path, path, {"PartAtom": data})
    return {"changed": True, "replaced": replaced, "bytes": len(data)}


#: the family-level PartAtom elements: the entry's OWN ``<title>`` / ``<id>``
#: (the first of each -- a Revit-born PartAtom also has ``<title>`` inside each
#: ``<A:part>``, which names a TYPE), the feature's ``<A:title>``, and the
#: design file's ``<A:title>NAME.rfa``.  A type's entry is ours
#: ``<A:type><A:title>NAME</A:title>`` or Revit's ``<A:part ...><title>NAME``
_RE_PA_ENTRY = (re.compile(r"(<title>)(.*?)(</title>)", re.S),
                re.compile(r"(<id>)(.*?)(</id>)", re.S))
_RE_PA_FEATURE = re.compile(r"(<A:feature><A:title>)(.*?)(</A:title>)", re.S)
_RE_PA_DESIGN = re.compile(r"(<A:design-file><A:title>)(.*?)(</A:title>)", re.S)
_RE_PA_TYPE = re.compile(r"(<A:type><A:title>|<A:part\b[^>]*>\s*<title>)(.*?)(</A:title>|</title>)",
                         re.S)


def _patch_partatom_scoped(path: str, family: Optional[str],
                           types: Dict[int, Tuple[str, str]]) -> Dict[str, Any]:
    """Keep PartAtom in step with the edit's renames, each on its OWN elements
    (#994): ``family`` (the new family name, or ``None``) rewrites the
    family-level elements that carry the old family title (and the design
    file's ``OLD.rfa``); ``types`` ({type index: (old, new)}) rewrites only
    that type's ``<A:type>`` entry -- the i-th entry when it carries the old
    name, else the one entry that does.  Order-independent: every match is
    against the input's PartAtom.  Values are XML-escaped; the container is
    rebuilt in place (atomic replace) only when the XML changed."""
    import html
    from ..container import open_rvt
    from ..roundtrip import rewrite_entries
    from ..famgen.skeleton import _xml_escape
    with open_rvt(path) as f:
        xml = f.raw("PartAtom").decode("utf-8")
    replaced: List[dict] = []
    out_xml = xml
    if family is not None:
        m0 = _RE_PA_ENTRY[0].search(xml)
        old = html.unescape(m0.group(2)) if m0 else ""
        n = [0]

        def sub_if(want: str, new: str):
            def f(m):
                if html.unescape(m.group(2)) != want:
                    return m.group(0)
                n[0] += 1
                return m.group(1) + _xml_escape(new) + m.group(3)
            return f
        if m0 is not None:
            for rx in _RE_PA_ENTRY:                    # the entry's own, first one only
                out_xml = rx.sub(sub_if(old, family), out_xml, count=1)
            if "<A:family" not in out_xml:             # our form: the feature is the family's;
                # Revit's form lists types as <A:family><A:part>, and its
                # <A:feature><A:title> is a parameter GROUP ("Constraints").  Our
                # form may carry zero <A:type> entries, so that is not the test (#1000)
                out_xml = _RE_PA_FEATURE.sub(sub_if(old, family), out_xml)
            out_xml = _RE_PA_DESIGN.sub(sub_if(old + ".rfa", family + ".rfa"), out_xml)
        replaced.append({"scope": "family", "old": old, "new": family, "occurrences": n[0]})
    if types:
        spans = list(_RE_PA_TYPE.finditer(out_xml))
        edits: Dict[int, str] = {}
        for i, (old, new) in sorted(types.items()):
            k = i if i < len(spans) and html.unescape(spans[i].group(2)) == old else None
            if k is None:
                hits = [j for j, s in enumerate(spans) if html.unescape(s.group(2)) == old]
                k = hits[0] if len(hits) == 1 else None
            if k is not None:
                edits[k] = new
            replaced.append({"scope": "type", "index": i, "old": old, "new": new,
                             "occurrences": int(k is not None)})
        for k in sorted(edits, reverse=True):
            s = spans[k]
            out_xml = out_xml[:s.start(2)] + _xml_escape(edits[k]) + out_xml[s.end(2):]
    if out_xml == xml:
        return {"changed": False, "replaced": replaced,
                "note": "no PartAtom occurrence of the renamed strings"}
    data = out_xml.encode("utf-8")
    rewrite_entries(path, path, {"PartAtom": data})
    return {"changed": True, "replaced": replaced, "bytes": len(data)}


def _partatom_type_titles(path: str) -> List[str]:
    import html
    from ..container import open_rvt
    try:
        with open_rvt(path) as f:
            xml = f.raw("PartAtom").decode("utf-8", "replace")
    except Exception:                                          # noqa: BLE001
        return []
    return [html.unescape(m.group(2)) for m in _RE_PA_TYPE.finditer(xml)]


# ---------------------------------------------------------------------------
# THE ROUTE
# ---------------------------------------------------------------------------

def modify_family(rfa_path: str, edit: str, out_dir: str, *,
                  stem: Optional[str] = None,
                  validate: bool = True) -> Dict[str, Any]:
    """prompt + RFA -> RFA.  Parse, apply, gate, DELIVER (stamps after)."""
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    inv = inventory_family(rfa_path)
    parsed = parse_family_edit(edit, inv)
    # the ops the file carries: an op a later op overrides is applied by
    # nobody and re-read by nobody (its note says so, #994)
    ops = _effective_ops(parsed["ops"])

    # output name: a family's display name IS largely its file name
    new_name = next((o["name"] for o in reversed(ops)
                     if o["op"] == "rename-family"), None)
    base_stem = stem or (re.sub(r"[^A-Za-z0-9._ -]+", "", new_name).strip()
                         if new_name else
                         os.path.splitext(os.path.basename(rfa_path))[0] + ".edited")
    out_path = os.path.join(out_dir, base_stem + ".rfa")

    rec: Dict[str, Any] = {
        "route": "prompt+rfa->rfa (rvt.convert.modify_family)",
        "tool": TOOL, "tool_version": TOOL_VERSION,
        "input": {"path": _relp(inv.path), "sha256": _sha256(inv.path),
                  "release": inv.release, "family_name": inv.family_name,
                  "types": inv.type_names},
        "edit": edit, "parsed": parsed,
        "files": {"rfa": out_path},
        "stamps": [P0_STAMP], "degradations": [], "errors": [],
    }
    if inv.quarantined:
        rec["stamps"].append(QUARANTINE_STAMP)
    try:
        rec["apply"], regen, geometry = _apply_geometry_true(inv, ops, out_path)
    except Exception as e:                                     # noqa: BLE001
        rec["errors"].append(f"apply failed: {type(e).__name__}: {e}")
        rec["errors"].append(traceback.format_exc(limit=6))
        rec["files"] = {}
        _finish(rec, out_dir, t0)
        raise
    reread_ops = ops
    # one geometry statement per edit: a value-only edit of a LABELLING
    # parameter carries the full VALUE ONLY caveat, so its unit note drops
    # the short one
    full = {g.split(": VALUE ONLY", 1)[0] for g in geometry if ": VALUE ONLY" in g}
    parsed["notes"] = [n[:-len(LENGTH_CAVEAT)]
                       if n.endswith(LENGTH_CAVEAT) and n.split(":", 1)[0] in full else n
                       for n in parsed.get("notes") or []]
    if regen is not None:
        rec["regeneration"] = regen
        if regen.get("route") == "regenerated":
            # the rebuilt family's parameter ids are its own: re-read by caption
            reread_ops = _rebind_ops(inventory_family(out_path), ops)
            rebuilt = set(regen.get("captions") or ())
            parsed["notes"] = [
                n[:-len(LENGTH_CAVEAT)] + REBUILT_NOTE
                if n.endswith(LENGTH_CAVEAT) and n.split(":", 1)[0] in rebuilt else n
                for n in parsed.get("notes") or []]

    # ---- gates (labels) ---------------------------------------------------
    if validate:
        g: Dict[str, Any] = {}
        try:
            from ..famgen import famdoc_adoc as FA
            val = FA.validate_family_file(out_path, with_donor_parity=False)
            fm = val.get("family_mode") or {}
            g["family_mode"] = {"verdict": fm.get("verdict"),
                                "n_errors": fm.get("n_errors"),
                                "n_warnings": fm.get("n_warnings")}
        except Exception as e:                                 # noqa: BLE001
            g["family_mode"] = {"verdict": "ERROR",
                                "error": f"{type(e).__name__}: {e}"}
        out_rel = V.detect_release(out_path)
        g["release"] = {"input": inv.release, "output": out_rel,
                        "preserved": bool(out_rel == inv.release)}
        # semantic re-read: every op's new value echoes back
        g["reread"] = _reread_proof(out_path, reread_ops)
        if regen is not None:
            # the contradiction an edit must not leave behind: every labelled
            # dimension measures its parameter's value (#909)
            from . import family_regen as FR
            labels = FR.label_report(out_path)
            g["labels"] = {"n": len(labels),
                           "disagree": [l for l in labels if not l["agree"]]}
        g["self_checks_ok"] = bool(
            g["family_mode"].get("verdict") == "VALID"
            and g["release"]["preserved"]
            and all(r.get("ok") for r in g["reread"]))
        rec["validation"] = {"rfa": g}
        if not g["self_checks_ok"]:
            rec["degradations"].append("one or more self-checks did not pass -- "
                                       "the file is delivered with this label, "
                                       "see validation")
    for n in parsed.get("notes") or []:
        rec["degradations"].append(n)
    for n in (rec["apply"].get("formula_followups") or []):
        rec["degradations"].append(n)
    for n in geometry:
        rec["degradations"].append(n)
    if regen is not None:
        note = _name_note(inv, ops, regen, rfa_path, out_path)
        regen.pop("name_note", None)
        if note:
            regen["name_note"] = note
            rec["degradations"].append(note)
    _finish(rec, out_dir, t0)
    return rec


def _name_note(inv: FamilyInventory, ops: Sequence[dict], regen: Dict[str, Any],
               rfa_path: str, out_path: str) -> str:
    """The ONE name statement of a rebuilt edit (#994), true for every
    combination of renames: the rebuild keeps the input's family title and
    type names, so a name the generator derived from the OLD dimensions is
    stale exactly where the edit did not rename it -- the family title unless
    a rename-family, each type that carried it unless a rename-type of that
    type.  Revit names a LOADED family by its FILE name, so the note also says
    which file name loads over the placed family: the delivered file when it
    kept the input's file name, else the input's file name to save it as (a
    rename-family is a new family by intent, so no reload advice then)."""
    stale = regen.get("name_stale") if regen.get("route") == "regenerated" else None
    if not stale:
        return ""
    old, fresh = stale["old"], stale["fresh"]
    renamed_family = any(o["op"] == "rename-family" for o in ops)
    renamed_types = {int(o["type_index"]) for o in ops if o["op"] == "rename-type"}
    what: List[str] = []
    fixes: List[str] = []
    if not renamed_family and inv.family_name == old:
        what.append(f"the family title {old!r}")
        fixes.append("'rename the family to ...'")
    n_types = sum(1 for i, t in enumerate(inv.type_names)
                  if t == old and i not in renamed_types)
    if n_types:
        what.append(f"the type name {old!r}" if n_types == 1 else
                    f"{n_types} type names {old!r}")
        fixes.append("'rename the type to ...'")
    if not what:
        return ""
    many = len(what) > 1 or n_types > 1
    note = (f"{' and '.join(what)} {'were' if many else 'was'} generated from the old "
            f"dimensions (the generator would name this size {fresh!r}); "
            f"{'they are' if many else 'it is'} kept, never changed silently -- "
            f"{' / '.join(fixes)} to change {'them' if many else 'it'}")
    if not renamed_family:
        src_file = os.path.basename(rfa_path)
        out_file = os.path.basename(out_path)
        src_stem = os.path.splitext(src_file)[0]
        if out_file.lower() == src_file.lower():
            note += (f". Revit names a loaded family by its file name: this file keeps the "
                     f"input's file name {src_file!r}, so loading it replaces the placed "
                     f"family {src_stem!r}")
        else:
            note += (f". Revit names a loaded family by its file name: this file is "
                     f"{out_file!r}, so loading it adds a SECOND family "
                     f"{os.path.splitext(out_file)[0]!r} beside {src_stem!r} -- save or "
                     f"load it as {src_file!r} to replace the placed family")
    return note


def _rebind_ops(inv: FamilyInventory, ops: Sequence[dict]) -> List[dict]:
    """``ops`` with every set-param's parameter id re-read from ``inv`` by
    caption (a rebuilt family numbers its own elements)."""
    out: List[dict] = []
    for o in ops:
        if o.get("op") == "set-param":
            p = inv.param_by_caption(o["caption"])
            if p is not None:
                o = dict(o, param_id=p["param_id"], carrier=p["carrier"])
        out.append(o)
    return out


def _apply_geometry_true(inv: FamilyInventory, ops: Sequence[dict], out_path: str
                         ) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]], List[str]]:
    """Apply ``ops`` so the geometry agrees with the values (#909): REBUILD the
    family from its generator when the edit sets a generator input and the
    generator reproduces the input byte for byte (then the other ops on top,
    by value); otherwise the VALUE path, with an explicit caveat for every
    edited parameter that labels a dimension.  Returns ``(apply record,
    regeneration record | None, geometry caveats)``."""
    import shutil
    import tempfile
    from . import family_regen as FR
    if not any(o.get("op") == "set-param" for o in ops):
        return apply_family_edits(inv, ops, out_path), None, []
    work = tempfile.mkdtemp(prefix="tekton_regen_")
    try:
        try:
            plan = FR.plan_rebuild(inv, ops, work=work)
        except Exception as exc:                               # noqa: BLE001 -- hard rule 1
            plan = FR.RebuildPlan(False, f"the rebuild check failed ({type(exc).__name__}: "
                                         f"{exc})")
        if plan.ok:
            try:
                regen = FR.rebuild(plan, out_path)
            except Exception as exc:                           # noqa: BLE001 -- hard rule 1
                plan = FR.RebuildPlan(False, str(exc), recovered=plan.recovered,
                                      derived=plan.derived, candidates=plan.candidates)
            else:
                regen["captions"] = sorted(plan.changes)
                try:
                    apply_rec = _apply_rest(plan, ops, out_path, work)
                except Exception as exc:                       # noqa: BLE001 -- hard rule 1
                    # the rebuild stood, the other ops could not ride on it:
                    # deliver the whole edit by VALUE instead, and say why
                    plan = FR.RebuildPlan(
                        False, "the family was rebuilt, but the edit's other ops could "
                               f"not be applied to the rebuilt file ({type(exc).__name__}: "
                               f"{exc}) -- the whole edit is delivered by value instead",
                        recovered=plan.recovered, derived=plan.derived,
                        candidates=plan.candidates)
                    try:
                        os.remove(out_path)
                    except OSError:
                        pass
                else:
                    caveats = [FR.derived_caveat(plan.recovered, o) for o in plan.derived]
                    return apply_rec, regen, caveats
        apply_rec = apply_family_edits(inv, ops, out_path)
        regen = {"route": "value-only", "reason": plan.reason,
                 "candidates": plan.candidates}
        return apply_rec, regen, _value_path_caveats(inv, ops, plan)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _apply_rest(plan, ops: Sequence[dict], out_path: str, work: str) -> Dict[str, Any]:
    """The ops the rebuild did not carry (renames, non-input parameters),
    applied by value on top of the rebuilt file at ``out_path``."""
    import shutil
    if plan.rest:
        inv2 = inventory_family(out_path)
        tmp = os.path.join(work, "rest", os.path.basename(out_path))
        os.makedirs(os.path.dirname(tmp), exist_ok=True)
        rest = []
        for o in plan.rest:
            if o.get("op") == "set-param":
                p = inv2.param_by_caption(o["caption"])
                if p is None:
                    raise FamilyEditError(f"{o['caption']}: not in the rebuilt family")
                o = dict(o, param_id=p["param_id"], carrier=p["carrier"])
            elif o.get("op") == "rename-type":
                o = dict(o, old=inv2.type_names[int(o["type_index"])])
            rest.append(o)
        apply_rec = apply_family_edits(inv2, rest, tmp)
        shutil.move(tmp, out_path)
        apply_rec["commit"]["out"] = _relp(out_path)
    else:
        apply_rec = {"applied": list(ops), "record_changes": {},
                     "commit": {"out": _relp(out_path), "blocks": None}}
    apply_rec["rebuilt"] = True
    apply_rec["applied"] = list(ops)
    return apply_rec


def _value_path_caveats(inv: FamilyInventory, ops: Sequence[dict], plan) -> List[str]:
    """The explicit statement for every value-only edit whose parameter -- or
    a formula parameter computed from it -- LABELS a dimension in the file,
    plus every edit of a parameter a recognised generator computes."""
    from . import family_regen as FR
    fv = inv.doc.value(inv.family_id) or {}
    rows = (((fv.get("m_familyParams") or {}).get("value") or {}).get("m_params") or [])
    labels = FR.label_report(inv.doc)
    caps = {int(p["param_id"]): p["caption"] for p in inv.params}
    out: List[str] = []
    for o in ops:
        if o.get("op") != "set-param":
            continue
        pid = int(o["param_id"])
        deps = FR.formula_dependents(rows, [pid])
        direct = [l for l in labels if l["param_id"] == pid]
        via = [l for l in labels if l["param_id"] in deps]
        if direct or via:
            out.append(FR.value_only_caveat(
                o["caption"], direct + via, plan.reason,
                via=sorted({caps.get(l["param_id"], str(l["param_id"])) for l in via})))
    for o in plan.derived:
        if plan.recovered is not None:
            out.append(FR.derived_caveat(plan.recovered, o))
    return out


def _reread_proof(path: str, ops: Sequence[dict]) -> List[dict]:
    from ..mutate import Document
    doc = Document.from_file(path)
    fam = doc.ids_of_class("Family")[0]
    fv = doc.value(fam) or {}
    ftt = ((fv.get("m_pFamilyTypes") or {}).get("value") or {})
    pairs = ftt.get("m_pairs") or []
    out: List[dict] = []
    for op in ops:
        if op["op"] == "rename-type":
            got = (pairs[int(op["type_index"])].get("name")
                   if int(op["type_index"]) < len(pairs) else None)
            # PartAtom's own type entry follows the type -- and ONLY the type
            # (#994: the family title is the rename-family check's business)
            pa_types = _partatom_type_titles(path)
            pa_ok = not pa_types or op["name"] in pa_types
            out.append({"op": "rename-type", "want": op["name"], "got": got,
                        "partatom_types": pa_types,
                        "ok": got == op["name"] and pa_ok})
        elif op["op"] == "set-param":
            pid, carrier = int(op["param_id"]), op["carrier"]
            scope = op.get("type_name")
            got = None
            for pr in pairs:
                if scope and str(pr.get("name")) != scope:
                    continue
                for row in ((pr.get("params") or {}).get("m_params") or []):
                    if int(row.get("m_paramId", -1)) == pid:
                        got = row.get(carrier)
            want = op["value"]
            ok = (abs(float(got) - float(want)) < 1e-9
                  if isinstance(want, float) and got is not None else got == want)
            out.append({"op": "set-param", "caption": op.get("caption"),
                        "want": want, "got": got, "ok": bool(ok)})
        elif op["op"] == "rename-family":
            import html
            title = html.unescape(_partatom_title(path) or "")
            out.append({"op": "rename-family", "want": op["name"], "got": title,
                        "ok": title == op["name"]})
    return out


def _finish(rec: Dict[str, Any], out_dir: str, t0: float) -> None:
    rec["seconds"] = round(time.time() - t0, 1)
    files = {k: v for k, v in (rec.get("files") or {}).items()
             if v and os.path.isfile(str(v))}
    rec["deliverables"] = {
        role: {"path": _relp(p), "bytes": os.path.getsize(p), "sha256": _sha256(p)}
        for role, p in files.items()}
    _jdump(os.path.join(out_dir, "manifest.json"), rec)
    lines = [f"# {rec['route']} -- deliverable manifest", ""]
    lines.append("## The deliverable(s)")
    for role, d in (rec["deliverables"] or {}).items():
        lines.append(f"* **{role}**: `{d['path']}` ({d['bytes']:,} bytes, "
                     f"sha256 {d['sha256'][:16]}...)")
    if not rec["deliverables"]:
        lines.append("* NO FILE PRODUCED -- see errors (nothing withheld)")
    lines.append("")
    lines.append("## Stamps (labels, not refusals)")
    for s in rec.get("stamps") or []:
        lines.append(f"* {s}")
    lines.append("")
    lines.append("## Edits applied")
    for a in ((rec.get("apply") or {}).get("applied") or []):
        lines.append(f"* {json.dumps({k: v for k, v in a.items() if k != 'spec'}, default=str)}")
    lines.append("")
    g = ((rec.get("validation") or {}).get("rfa") or {})
    if g:
        lines.append("## Gates (self-checks)")
        fm = g.get("family_mode") or {}
        lines.append(f"* family-mode validator: {fm.get('verdict')} "
                     f"({fm.get('n_errors')} errors, {fm.get('n_warnings')} warnings)")
        rel = g.get("release") or {}
        lines.append(f"* release: {rel.get('output')} (preserved={rel.get('preserved')})")
        for r in g.get("reread") or []:
            lines.append(f"* re-read {r.get('op')}: want={r.get('want')!r} "
                         f"got={r.get('got')!r} ok={r.get('ok')}")
        lines.append("")
    if rec.get("degradations"):
        lines.append("## Caveats")
        for d in rec["degradations"]:
            lines.append(f"* {d}")
        lines.append("")
    if rec.get("errors"):
        lines.append("## Errors")
        for e in rec["errors"]:
            lines.append(f"* {e}")
    with open(os.path.join(out_dir, "MANIFEST.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="rvt.convert.modify_family",
        description="prompt + RFA -> RFA: natural-language family edits "
                    "(rename type/family, set parameters).")
    ap.add_argument("rfa", help="the family file to edit")
    ap.add_argument("--edit", default=None,
                    help="the edit: text | inline JSON | ops.json path "
                         "(required unless --inventory)")
    ap.add_argument("-o", "--out-dir", default=None,
                    help="output directory (required unless --inventory)")
    ap.add_argument("--stem", default=None, help="output file stem")
    ap.add_argument("--inventory", action="store_true",
                    help="print the editable surface and exit")
    ap.add_argument("--no-validate", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.inventory:
            inv = inventory_family(a.rfa)
            print(json.dumps(inv.as_json(), indent=1, default=str))
            return 0
        if not a.edit or not a.out_dir:
            ap.error("--edit and -o are required (or pass --inventory)")
        rec = modify_family(a.rfa, a.edit, a.out_dir, stem=a.stem,
                            validate=not a.no_validate)
    except (FamilyEditError, ConvertError) as e:
        print(f"REFUSED/FAILED: {e}")
        return 2
    except Exception as e:                                     # noqa: BLE001
        traceback.print_exc(limit=6)
        print(f"FAILED: {e}")
        return 2
    for role, d in (rec.get("deliverables") or {}).items():
        print(f"delivered {role}: {d['path']} ({d['bytes']:,} bytes)")
    for s in rec.get("stamps") or []:
        print(f"  STAMP: {s}")
    for d in (rec.get("degradations") or [])[:8]:
        print(f"  caveat: {d}")
    ok = bool(rec.get("deliverables")) and (
        ((rec.get("validation") or {}).get("rfa") or {}).get("self_checks_ok", True))
    return 0 if ok else 1


if __name__ == "__main__":                                    # pragma: no cover
    raise SystemExit(main())
