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
SPEC-DRIVEN: amperes as-is, volts x 1/0.3048^2, lengths to feet (an
explicit unit is REQUIRED for lengths -- never guessed), kVA x 1000 x
1/0.3048^2.

HONEST LIMIT: editing a DIMENSION parameter changes the type-table value
only -- generated families carry no dimension-constraint graph, so the
authored solid is NOT re-derived.  The geometry-true path is regeneration
from the facts sidecar (``families/<stem>.json``); every dimension edit
records this caveat.

VOCABULARY COORDINATION: if a sibling stream lands a shared family-edit
vocabulary module (``rvt.convert.edit_family``), :func:`parse_family_edit`
delegates to its ``parse_family_edit`` and records the delegation; until
then the minimal grammar below IS the vocabulary (merge note in
docs/inbox/convert-b.md).

Territory: ``src/rvt/convert/`` (convert-B stream).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
import traceback
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .. import versions as V
from .add_to_project import (ConvertError, P0_STAMP, QUARANTINE_STAMP, TOOL,
                             TOOL_VERSION, _jdump, _relp, _sha256,
                             quarantined_input)
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
        return m.group(1) if m else ""
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
                       "carrier": carrier, "current": row.get(carrier)})
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
    "ka": ("number", 1.0),               # ShortCircuitRatingkA is dimensionless kA
}


def _convert_value(param: dict, raw: str) -> Tuple[Any, List[str]]:
    """Turn the prompt's value into the carrier's internal value, spec-driven.
    Returns (value, notes)."""
    notes: List[str] = []
    spec = param["spec"]
    carrier = param["carrier"]
    txt = str(raw).strip().strip("\"'")
    if carrier == "m_str":
        return txt, notes
    m = re.fullmatch(r"(-?\d+(?:[.,]\d+)?)\s*([A-Za-z\"']*)", txt)
    if not m:
        raise FamilyEditError(
            f"{param['caption']}: cannot read a number from {txt!r}")
    num = float(m.group(1).replace(",", ""))
    unit = (m.group(2) or "").lower()
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
    if ":length" in spec:
        if not unit:
            raise FamilyEditError(
                f"{param['caption']} is a LENGTH: give an explicit unit "
                "(in / ft / mm / m) -- units are never guessed")
        kind, factor = _UNIT_TOKENS.get(unit, ("", 0.0))
        if kind != "length":
            raise FamilyEditError(f"{param['caption']} is a length; got unit {unit!r}")
        notes.append(f"{param['caption']}: {num:g} {unit} -> {num * factor:g} ft "
                     "(CAVEAT: type-table value only; the authored solid is not "
                     "re-derived -- regenerate from the facts sidecar for "
                     "geometry-true resizing)")
        return float(num) * factor, notes
    if unit:
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

    def norm_json_ops(payload) -> List[dict]:
        raw_ops = payload.get("ops") if isinstance(payload, dict) else payload
        if isinstance(raw_ops, dict):
            raw_ops = [raw_ops]
        if not isinstance(raw_ops, list) or not raw_ops:
            raise FamilyEditError("JSON edit must be a non-empty list of ops")
        out = []
        for o in raw_ops:
            op = str(o.get("op") or "").lower()
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
    for cl in [c.strip() for c in re.split(r";|\n|\bthen\b|,\s*(?=set\b|rename\b)", s)
               if c.strip()]:
        c = cl.rstrip(".")
        if (m := _RE_RENAME_FAMILY.match(c)):
            op = {"op": "rename-family", "name": m.group("new").strip()}
        elif (m := _RE_RENAME_TYPE.match(c)):
            op = _op_rename_type(inv, m.group("old"), m.group("new").strip())
        elif (m := _RE_SET.match(c)):
            op = _op_set(inv, m.group("cap").strip(), m.group("val").strip(), notes,
                         type_name=(m.group("typeq") or m.group("typeq2")
                                    or m.group("type")))
        else:
            unparsed.append(cl)
            continue
        ops.append(op)
        understood.append({"clause": cl, "op": op})
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


def _op_rename_type(inv: FamilyInventory, old: Optional[str], new: str) -> dict:
    if not inv.type_names:
        raise FamilyEditError("this family has no type-table types to rename "
                              + ("(" + "; ".join(inv.notes) + ")" if inv.notes else ""))
    if old:
        key = str(old).strip().lower()
        hits = [i for i, n in enumerate(inv.type_names) if n.strip().lower() == key]
        if not hits:
            hits = [i for i, n in enumerate(inv.type_names) if key in n.lower()]
        if len(hits) != 1:
            raise FamilyEditError(f"type {old!r} matches {len(hits)} of "
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
            type_name: Optional[str] = None) -> dict:
    p = inv.param_by_caption(caption)
    if p is None:
        raise FamilyEditError(
            f"no parameter {caption!r} in this family. Parameters: "
            + ", ".join(q["caption"] for q in inv.params))
    val, conv_notes = _convert_value(p, raw)
    notes.extend(conv_notes)
    op = {"op": "set-param", "param_id": p["param_id"], "caption": p["caption"],
          "carrier": p["carrier"], "spec": p["spec"], "value": val, "raw": raw}
    if type_name:
        key = str(type_name).strip().strip("\"'").lower()
        hits = [n for n in inv.type_names if n.strip().lower() == key]
        if not hits:
            hits = [n for n in inv.type_names if key in n.lower()]
        if len(hits) != 1:
            raise FamilyEditError(
                f"'of type {type_name}' matches {len(hits)} of {inv.type_names}: "
                "name the type exactly (quote names containing spaces)")
        op["type_name"] = hits[0]
        notes.append(f"{p['caption']}: scoped to type {hits[0]!r} -- the current-"
                     "defaults row (m_familyParams) is left as-is for a scoped edit")
    return op


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
    partatom_renames: List[Tuple[str, str]] = []
    new_family_name: Optional[str] = None
    applied: List[dict] = []

    for op in ops:
        kind = op["op"]
        if kind == "rename-type":
            i = int(op["type_index"])
            changes[f"m_pFamilyTypes.value.m_pairs[{i}].name"] = op["name"]
            partatom_renames.append((str(op.get("old") or inv.type_names[i]),
                                     op["name"]))
            applied.append(op)
        elif kind == "rename-family":
            new_family_name = op["name"]
            if inv.family_name:
                partatom_renames.append((inv.family_name, op["name"]))
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
    ver = M.verify_manipulated(out_path, edited_ids=[fam])
    rec["structural_verify"] = {k: ver.get(k) for k in
                                ("crc_failures", "ecc_mismatches", "walker_errors",
                                 "stamps_ok", "elemtable_count", "header_count")}
    rec["structural_ok"] = bool(
        ver.get("crc_failures") == 0 and ver.get("ecc_mismatches") == 0
        and not ver.get("walker_errors") and ver.get("stamps_ok")
        and ver.get("elemtable_count") == ver.get("header_count"))

    # ---- PartAtom follow (names in the Atom-XML metadata) -----------------
    if partatom_renames or new_family_name:
        rec["partatom"] = _patch_partatom(out_path, partatom_renames)
    return rec


def _patch_partatom(path: str, renames: Sequence[Tuple[str, str]]) -> Dict[str, Any]:
    """Rewrite name occurrences inside the PartAtom stream (plain XML,
    unframed) and rebuild the container."""
    import dataclasses as _dc
    from ..cfb_writer import write_cfb
    from ..container import open_rvt
    from ..roundtrip import read_entries
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
    entries = read_entries(path)
    new_entries = [
        _dc.replace(e, data=out_xml.encode("utf-8"))
        if e.entry_type == "stream" and e.path == "PartAtom" else e
        for e in entries]
    write_cfb(path, new_entries)
    return {"changed": True, "replaced": replaced,
            "bytes": len(out_xml.encode("utf-8"))}


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

    # output name: a family's display name IS largely its file name
    new_name = next((o["name"] for o in parsed["ops"]
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
        rec["apply"] = apply_family_edits(inv, parsed["ops"], out_path)
    except Exception as e:                                     # noqa: BLE001
        rec["errors"].append(f"apply failed: {type(e).__name__}: {e}")
        rec["errors"].append(traceback.format_exc(limit=6))
        rec["files"] = {}
        _finish(rec, out_dir, t0)
        raise

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
        g["reread"] = _reread_proof(out_path, parsed["ops"])
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
    _finish(rec, out_dir, t0)
    return rec


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
            out.append({"op": "rename-type", "want": op["name"], "got": got,
                        "ok": got == op["name"]})
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
            title = _partatom_title(path)
            out.append({"op": "rename-family", "want": op["name"], "got": title,
                        "ok": op["name"] in (title or "")})
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
