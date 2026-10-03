"""rvt.convert.family_regen -- a family edit that MOVES THE GEOMETRY (#909).

THE DEFECT.  The family edit lane (:mod:`rvt.convert.modify_family`) writes a
parameter's value into the type table and nothing else.  Our generated
families now carry real constraint graphs (#904 / #913 / #916 / #948 / #787
Case B): ``Strut Length`` LABELS a dimension between two reference planes,
the strut edges are locked to those planes, the rods / washers / nuts follow
them at ``Rod Inset`` ...  Setting ``Strut Length`` to 36 in left the labelled
dimension measuring 30 in, its planes, every locked edge and every follower at
the old positions -- a family that disagrees with itself, the very mismatch
``drive_law`` refuses to author.

THE ROUTE TAKEN: REBUILD, PROVEN BY REPRODUCTION.  The generators already know
the whole chain (which planes, which locks, which followers, which formula
children); re-solving the graph in place would be a second, unverified copy
of that knowledge.  So an edit of a generator INPUT rebuilds the family from
its generator with the new value -- byte-identical to building it at that
value directly under the input's own family and type name (the names are
KEPT, never changed silently; a dimension-derived name that now describes the
old size is said, and which FILE name reloads over the placed family -- Revit
names a loaded family by its file name -- is said with it, #994).  A generated family does not carry its spec, so the spec is
RECOVERED from the file (its parameter values, its name, its start id) and
the recovery is PROVEN before anything is rebuilt: the generator, run on the
recovered spec, must reproduce the input file BYTE FOR BYTE (sha256, written
under the input's own file name -- the only path-dependent byte is
``BasicFileInfo``'s last-save name).  A family that does not reproduce -- a
Revit-born family, one edited by hand since, a spec value no parameter
carries (a trapeze's lip), another release -- is never rebuilt on a guess.

THE GENERATORS this module can recover (``GENERATORS``):

* every product of :data:`rvt.famgen.archetypes.ARCHETYPES` (the archetype
  drive registries: ``drives`` / ``heights`` / ``diameters`` / ``runs``),
  through :func:`rvt.famgen.factory.make_archetype` -- the strut trapeze
  (solid, and its #917 nested-hardware form), cable tray, strut channel,
  wireway, junction box, lighting control panel, conduit;
* the #917 nested-hardware children as standalone families: the hex nut
  (``Nut Across Flats`` drives the hexagon through the FORMULA parameter
  ``Nut Half Across Flats`` = Nut Across Flats / 2, #948) and the square
  washer.

Which family parameter is a generator INPUT is DERIVED, never listed: a
parameter whose value (``Archetype.family_params`` / ``standard_values``)
depends on exactly one archetype dimension with slope = that dimension's unit
is that dimension; one that depends on several (``Rod Length``) or on a
multiple (``Nut Across Flats`` = 1.5 x rod diameter) is DERIVED -- the
generator computes it, so it is set by editing its inputs (said by name).
Where the generator's own settle law ties inputs together (a trapeze: Strut
Length = Rod Spacing + 2 x Rod Inset), the dimension the edit leaves to be
re-derived is the first one that is NOT a drive caption (Rod Spacing is a
value, never a driver -- exactly what the constraint graph does in Revit when
Strut Length flexes and the rods follow at Rod Inset).

WHAT IS NOT SUPPORTED, AND SAYS SO (never a silent mismatch).  Everything
else stays on the value-only path, and when the parameter -- or a formula
parameter computed from it -- LABELS a dimension in the file
(:func:`label_report`), the result carries an explicit caveat naming the
dimension(s) left measuring the old value and the reason no rebuild was
possible.  Catalog equipment (a panelboard's Width / Depth / Height drives),
IFC-built families (#714 pset drives) and every foreign family are on that
path today.

HARD RULE 4.  A rebuilt family is our generator's output at the new value;
whether Revit's solver, flexing the ORIGINAL family, would have produced the
same geometry is unverified, and so is the rebuilt family's behaviour in
Revit -- no desktop verdict exists for either.

Territory: ``src/rvt/convert/`` (new module, #909).
"""
from __future__ import annotations

import contextlib
import functools
import hashlib
import math
import os
import shutil
import tempfile
from dataclasses import dataclass, field as dc_field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

__all__ = [
    "LABEL_CLASSES", "label_report", "formula_children", "formula_dependents",
    "formula_followups",
    "Recovered", "recover", "caption_map", "plan_rebuild", "rebuild",
    "value_only_caveat", "derived_caveat", "RebuildPlan", "GENERATORS",
]

#: the dimension classes that LABEL a parameter (``m_ArrSegInfo[i].m_paramId``)
LABEL_CLASSES = ("LinearDimString", "RadialDim", "AngularDim")

#: relative tolerance of a label / value agreement (labels are authored exact)
AGREE_TOL = 1e-9

IN = 1.0 / 12.0
_UNIT_FACTOR = {"in": IN, "ft": 1.0, "count": 1.0}


# ---------------------------------------------------------------------------
# the file's own parameter table, labels and formulas
# ---------------------------------------------------------------------------

def _rows(fv: Dict[str, Any]) -> List[Dict[str, Any]]:
    return (((fv.get("m_familyParams") or {}).get("value") or {}).get("m_params") or [])


def _row_value(row: Dict[str, Any]) -> Any:
    """A row's numeric value (``m_value``, or ``m_int`` for integers / Yes-No)."""
    v = row.get("m_value")
    if isinstance(v, (int, float)) and float(v) != 0.0:
        return float(v)
    i = row.get("m_int")
    if isinstance(i, int) and i != 0:
        return int(i)
    return float(v) if isinstance(v, (int, float)) else 0.0


def _captions(doc) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for eid in doc.ids_of_class("ParamElemFamily"):
        d = (((doc.value(eid) or {}).get("m_pParamDef") or {}).get("value") or {})
        out[int(eid)] = str(d.get("m_caption") or "")
    return out


def _seg_stored(seg: Dict[str, Any]) -> Optional[float]:
    vals = seg.get("m_values") or []
    v = vals[0].get("m_value") if vals and isinstance(vals[0], dict) else None
    if isinstance(v, (int, float)):
        return float(v)
    lv = seg.get("m_lockedValue")
    return float(lv) if isinstance(lv, (int, float)) else None


def label_report(source: Any) -> List[Dict[str, Any]]:
    """Every LABELLED dimension segment of a family (a path or an opened
    :class:`rvt.mutate.Document`): ``{dim, class, param_id, caption, stored,
    value, agree}`` -- ``stored`` is what the dimension measures (its current
    segment value), ``value`` the parameter's current value; ``agree`` is the
    contradiction test an edit must keep true."""
    from ..mutate import Document
    doc = Document.from_file(source) if isinstance(source, str) else source
    fams = doc.ids_of_class("Family")
    if not fams:
        return []
    fv = doc.value(fams[0]) or {}
    cur = {int(r.get("m_paramId", -1)): r for r in _rows(fv)}
    caps = _captions(doc)
    out: List[Dict[str, Any]] = []
    for cls in LABEL_CLASSES:
        for eid in doc.ids_of_class(cls):
            for seg in (doc.value(eid) or {}).get("m_ArrSegInfo") or []:
                pid = int(seg.get("m_paramId", -1)) if isinstance(seg, dict) else -1
                if pid < 0:
                    continue
                stored = _seg_stored(seg)
                row = cur.get(pid)
                val = _row_value(row) if row is not None else None
                agree = (stored is not None and val is not None and
                         abs(float(stored) - float(val))
                         <= AGREE_TOL * max(1.0, abs(float(val))))
                out.append({"dim": int(eid), "class": cls, "param_id": pid,
                            "caption": caps.get(pid, ""), "stored": stored,
                            "value": val, "agree": bool(agree)})
    return out


def formula_children(rows: Sequence[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    """``{param id: expression tree}`` of every FORMULA parameter in a row set
    (the self-Family's ``m_familyParams`` rows, or one type row's -- #850: the
    tree rides on each row's ``m_oExpression``; null / empty = no formula)."""
    from ..famgen import formula as FO
    return {int(r.get("m_paramId", -1)): r["m_oExpression"] for r in rows
            if isinstance(r, dict) and not FO.is_no_formula(r.get("m_oExpression"))}


def _dependents(trees: Dict[int, Dict[str, Any]], pids: Sequence[int]) -> List[int]:
    """Formula parameters reading any of ``pids``, transitively, in an order
    where every formula follows the formulas it reads."""
    from ..famgen import formula as FO
    reads = {p: set(FO.referenced_params(t)) for p, t in trees.items()}
    hit = set(pids)
    order: List[int] = []
    changed = True
    while changed:
        changed = False
        for p, r in reads.items():
            if p not in order and r & hit:
                order.append(p)
                hit.add(p)
                changed = True
    return order


def formula_dependents(rows: Sequence[Dict[str, Any]], pids: Sequence[int]) -> List[int]:
    """The formula parameters (ids) that read any of ``pids``, transitively."""
    return _dependents(formula_children(rows), pids)


def formula_followups(rows: Sequence[Dict[str, Any]], edits: Dict[int, Any],
                      carriers: Dict[int, str]) -> Tuple[Dict[int, Any], List[str]]:
    """The new values of every formula parameter an edit feeds (``Nut Across
    Flats`` -> ``Nut Half Across Flats``), evaluated with the row set's own
    expression trees over its CURRENT values with ``edits`` applied.  Returns
    ``({param id: value}, notes)``; a formula the evaluator cannot compute is
    reported, never approximated (its stored value is left as it was)."""
    from ..famgen import formula as FO
    trees = formula_children(rows)
    order = _dependents(trees, list(edits))
    if not order:
        return {}, []
    vals: Dict[int, Any] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        pid = int(r.get("m_paramId", -1))
        c = carriers.get(pid, "m_value")
        v = r.get(c)
        vals[pid] = float(v or 0.0) if c == "m_value" else v
    vals.update(edits)
    out: Dict[int, Any] = {}
    notes: List[str] = []
    for pid in order:
        try:
            v = FO.evaluate(trees[pid], vals)
        except Exception as exc:                              # noqa: BLE001
            notes.append(f"formula parameter {pid} reads the edited value but could "
                         f"not be re-evaluated ({exc}); its stored value is unchanged")
            continue
        if isinstance(v, bool):
            v = int(v)
        vals[pid] = v
        out[pid] = v
    return out, notes


# ---------------------------------------------------------------------------
# the generators and how a parameter maps to their inputs
# ---------------------------------------------------------------------------

def _numeric(d: Dict[str, Any]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for c, v in (d or {}).items():
        if isinstance(v, tuple) and len(v) == 2:
            v = v[1]
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            continue
        out[str(c)] = float(v)
    return out


def _arch_values(arch, vals: Dict[str, float]) -> Dict[str, float]:
    out = _numeric(arch.standard_values(dict(vals)) or {})
    out.update(_numeric(arch.family_params(dict(vals)) or {}))
    return out


def _settled_defaults(arch) -> Dict[str, float]:
    v = arch.defaults()
    if arch.settle is not None:
        prov = {p.key: "nominal" for p in arch.params}
        arch.settle(v, prov, {})
    return v


@functools.lru_cache(maxsize=None)
def caption_map(product: str) -> Dict[str, Any]:
    """How an archetype's FAMILY PARAMETERS map to its dimensions, derived by
    perturbing each dimension: ``inputs`` = ``{caption: key}`` (the parameter
    IS that dimension, slope 1 in its unit), ``derived`` = ``{caption: [keys
    it depends on]}`` (computed by the generator), ``drivers`` = the captions
    the archetype's drive registries label."""
    from ..famgen import archetypes as AR
    arch = AR.archetype(product)
    base = _settled_defaults(arch)
    c0 = _arch_values(arch, base)
    deps: Dict[str, List[str]] = {c: [] for c in c0}
    slope: Dict[Tuple[str, str], float] = {}
    for p in arch.params:
        h = 1.0
        v = dict(base)
        v[p.key] = float(v[p.key]) + h
        try:
            c1 = _arch_values(arch, v)
        except Exception:                                    # noqa: BLE001
            continue
        for c in c0:
            if c in c1 and abs(c1[c] - c0[c]) > 1e-12:
                deps[c].append(p.key)
                slope[(c, p.key)] = (c1[c] - c0[c]) / h
    inputs: Dict[str, str] = {}
    derived: Dict[str, List[str]] = {}
    for c, ks in deps.items():
        if len(ks) == 1:
            f = _UNIT_FACTOR.get(arch.param(ks[0]).unit)
            if f is not None and abs(slope[(c, ks[0])] - f) <= 1e-9 * max(1.0, f):
                inputs[c] = ks[0]
                continue
        derived[c] = list(ks)
    drivers: List[str] = []
    for fn in (arch.drives, arch.heights, arch.diameters, arch.runs):
        if fn is None:
            continue
        try:
            specs = fn(dict(base)) or []
        except Exception:                                    # noqa: BLE001
            continue
        for s in specs:
            for c in (s.get("caption"), (s.get("follow") or {}).get("caption")):
                if c and c not in drivers:
                    drivers.append(c)
    return {"inputs": inputs, "derived": derived, "drivers": drivers,
            "required": sorted(inputs.keys() & _numeric(arch.family_params(dict(base)) or {}).keys())}


@dataclass
class Recovered:
    """A generator + spec recovered from a family file (not yet proven)."""
    generator: str                       # "archetype" | "hex_nut" | "washer"
    product: str                         # the archetype key / child kind
    values: Dict[str, float]             # dimension key -> natural-unit value
    inputs: Dict[str, str]               # caption -> dimension key
    derived: Dict[str, List[str]]        # caption -> the keys it is computed from
    drivers: List[str]                   # captions the constraint graph labels
    name: str                            # the family name (PartAtom title)
    start_id: int
    options: Dict[str, Any] = dc_field(default_factory=dict)
    release: Optional[int] = None        # the input's Revit release (rebuilt at it)
    notes: List[str] = dc_field(default_factory=list)

    def build(self, values: Dict[str, float], *, name: Optional[str],
              drop: Sequence[str] = ()):
        return GENERATORS[self.generator]["build"](self, values, name=name, drop=drop)

    def describe(self) -> Dict[str, Any]:
        return {"generator": GENERATORS[self.generator]["callable"],
                "product": self.product, "start_id": self.start_id,
                "name": self.name, "options": dict(self.options),
                "release": self.release,
                "values": dict(self.values)}


def _natural(value: float, unit: str) -> float:
    f = _UNIT_FACTOR.get(unit, 1.0)
    if unit == "count":
        return float(int(round(float(value))))
    return round(float(value) / f, 10)


def _recover_archetypes(inv) -> List[Recovered]:
    from ..famgen import archetypes as AR
    if len(inv.type_names) != 1:
        return []
    cur = {p["caption"]: p for p in inv.params}
    out: List[Recovered] = []
    for key in AR.keys():
        arch = AR.archetype(key)
        cm = caption_map(key)
        need = cm["required"]
        if not need or any(c not in cur for c in need):
            continue
        vals = arch.defaults()
        for c, k in cm["inputs"].items():
            p = cur.get(c)
            if p is None or p.get("current") is None:
                continue
            vals[k] = _natural(p["current"], arch.param(k).unit)
        opts: Dict[str, Any] = {}
        if "Show Clearance" in cur and arch.working_space:
            opts["clearance"] = True
        if key == "strut_trapeze" and inv.doc is not None and inv.doc.ids_of_class("FamilyInstance"):
            opts["nested_hardware"] = True
        out.append(Recovered("archetype", key, vals, dict(cm["inputs"]),
                             {c: list(v) for c, v in cm["derived"].items()},
                             list(cm["drivers"]), inv.family_name, int(inv.family_id),
                             opts))
    out.sort(key=lambda r: -len(r.inputs))
    return out


def _build_archetype(rec: Recovered, values: Dict[str, float], *, name: Optional[str],
                     drop: Sequence[str] = ()):
    from ..famgen import factory as F
    dims = {k: v for k, v in values.items() if k not in drop}
    kw: Dict[str, Any] = dict(product=rec.product, dimensions=dims, name=name,
                              start_id=rec.start_id)
    if rec.options.get("clearance"):
        kw["prompt"] = "with NEC working space clearance"
    if rec.options.get("nested_hardware"):
        kw["nested_hardware"] = True
    return F.make_archetype(**kw)


def _auto_name_archetype(rec: Recovered, values: Dict[str, float],
                         drop: Sequence[str] = ()) -> str:
    from ..famgen import archetypes as AR
    dims = {k: v for k, v in values.items() if k not in drop}
    res = AR.resolve(rec.product, dims,
                     prompt=("with NEC working space clearance"
                             if rec.options.get("clearance") else ""))
    return res.name


#: the #917 children, standalone: ``{family name: (generator, {caption: key})}``
_CHILDREN = {
    "hex_nut": {"inputs": {"Nut Across Flats": "across_flats_ft", "Nut Height": "height_ft"},
                "derived": {"Nut Half Across Flats": ["across_flats_ft"],
                            "Width": ["across_flats_ft"], "Depth": ["across_flats_ft"],
                            "Height": ["height_ft"]},
                "drivers": ["Nut Half Across Flats", "Nut Height"],
                "callable": "rvt.famgen.trapeze_nested:make_hex_nut"},
    "washer": {"inputs": {"Washer Size": "size_ft", "Washer Thickness": "thickness_ft"},
               "derived": {"Width": ["size_ft"], "Depth": ["size_ft"],
                           "Height": ["thickness_ft"]},
               "drivers": ["Washer Size", "Washer Thickness"],
               "callable": "rvt.famgen.trapeze_nested:make_washer"},
}


def _recover_children(inv) -> List[Recovered]:
    if len(inv.type_names) != 1:
        return []
    caps = {p["caption"]: p for p in inv.params}
    out: List[Recovered] = []
    for kind, spec in _CHILDREN.items():
        want = set(spec["inputs"]) | set(spec["derived"])
        if set(caps) != want:
            continue
        vals = {k: round(float(caps[c]["current"]), 12) for c, k in spec["inputs"].items()}
        out.append(Recovered(kind, kind, vals, dict(spec["inputs"]),
                             {c: list(v) for c, v in spec["derived"].items()},
                             list(spec["drivers"]), inv.family_name, int(inv.family_id)))
    return out


def _build_child(rec: Recovered, values: Dict[str, float], *, name: Optional[str],
                 drop: Sequence[str] = ()):
    from ..famgen import trapeze_nested as TN
    nm = name or rec.name
    if rec.generator == "hex_nut":
        return TN.make_hex_nut(rec.start_id, across_flats_ft=values["across_flats_ft"],
                               height_ft=values["height_ft"], name=nm)
    return TN.make_washer(rec.start_id, size_ft=values["size_ft"],
                          thickness_ft=values["thickness_ft"], name=nm)


#: generator -> how to recover it from a file, rebuild it, and name it
GENERATORS: Dict[str, Dict[str, Any]] = {
    "archetype": {"recover": _recover_archetypes, "build": _build_archetype,
                  "auto_name": _auto_name_archetype,
                  "callable": "rvt.famgen.factory:make_archetype"},
    "hex_nut": {"recover": _recover_children, "build": _build_child,
                "auto_name": lambda rec, values, drop=(): rec.name,
                "callable": _CHILDREN["hex_nut"]["callable"]},
    "washer": {"recover": lambda inv: [], "build": _build_child,
               "auto_name": lambda rec, values, drop=(): rec.name,
               "callable": _CHILDREN["washer"]["callable"]},
}


def recover(inv) -> List[Recovered]:
    """Every generator + spec a family's parameters are consistent with
    (candidates, best first; none proven yet -- :func:`plan_rebuild` proves)."""
    out: List[Recovered] = []
    seen = set()
    for g in GENERATORS.values():
        fn = g["recover"]
        if fn in seen:
            continue
        seen.add(fn)
        try:
            out.extend(fn(inv))
        except Exception:                                    # noqa: BLE001 -- a guess, never a failure
            continue
    for r in out:
        r.release = inv.release
    return out


# ---------------------------------------------------------------------------
# prove, plan, rebuild
# ---------------------------------------------------------------------------

def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _write(prod, path: str) -> None:
    prod.write(path, validate=False, provenance=False)


def _drop_orders(rec: Recovered, edited: Sequence[str]) -> List[Tuple[str, ...]]:
    """The dimension sets a build may leave to the generator's settle law:
    none first, then each non-driver dimension, then each other one."""
    keys = list(rec.values)
    non_driver = [k for c, k in rec.inputs.items() if c not in rec.drivers]
    other = [k for k in keys if k not in non_driver]
    order: List[Tuple[str, ...]] = [()]
    for k in non_driver + other:
        if k not in edited and (k,) not in order:
            order.append((k,))
    return order


def _try_build(rec: Recovered, values: Dict[str, float], name: Optional[str],
               edited: Sequence[str] = ()):
    """``(product, dropped keys, refusals)`` -- the first build the generator
    accepts, leaving the fewest dimensions to its settle law."""
    refusals: List[str] = []
    for drop in _drop_orders(rec, edited):
        try:
            return rec.build(values, name=name, drop=drop), drop, refusals
        except Exception as exc:                             # noqa: BLE001
            refusals.append(f"{type(exc).__name__}: {exc}")
            if rec.generator != "archetype":
                break
    return None, (), refusals


@contextlib.contextmanager
def _release_context(year: Optional[int]):
    """Build + write at the input's release: only the native release is
    rebuilt (the edit lane itself reads native-release families only today;
    another release is refused here by name, never written at the wrong one)."""
    from ..frontdoor import release_ctx as RC
    if year is not None and int(year) != RC.native_release():
        raise RuntimeError(f"a Revit {year} family is not rebuilt (the generators "
                           f"rebuild at the native Revit {RC.native_release()} only here)")
    yield None


def _prove(rec: Recovered, input_path: str, work: str) -> Tuple[bool, str]:
    """Rebuild the recovered spec under the input's own file name and compare
    bytes.  ``(reproduced, reason)``."""
    d = os.path.join(work, "reproduce", rec.generator + "-" + rec.product)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, os.path.basename(input_path))
    try:
        with _release_context(rec.release):
            prod, drop, refusals = _try_build(rec, dict(rec.values), rec.name)
            if prod is None:
                return False, ("the generator refused the recovered spec: "
                               + "; ".join(refusals[:2]))
            _write(prod, p)
    except Exception as exc:                                 # noqa: BLE001
        return False, f"the recovered spec could not be built ({type(exc).__name__}: {exc})"
    if _sha256(p) != _sha256(input_path):
        return False, (f"{GENERATORS[rec.generator]['callable']}({rec.product}) on the "
                       "recovered spec does not reproduce the input byte for byte")
    return True, ""


@dataclass
class RebuildPlan:
    ok: bool
    reason: str = ""
    recovered: Optional[Recovered] = None
    #: caption -> (dimension key, new natural value) of the ops it rebuilds
    changes: Dict[str, Tuple[str, float]] = dc_field(default_factory=dict)
    #: ops left for the value path (non-input parameters, renames)
    rest: List[dict] = dc_field(default_factory=list)
    #: set-param ops on DERIVED parameters (computed by the generator)
    derived: List[dict] = dc_field(default_factory=list)
    candidates: List[Dict[str, Any]] = dc_field(default_factory=list)


def plan_rebuild(inv, ops: Sequence[dict], *, work: str) -> RebuildPlan:
    """Decide whether ``ops`` can be applied by REBUILDING the family from its
    generator: at least one unscoped set-param targets a generator input, and
    the generator, on the spec recovered from the file, reproduces the input
    byte for byte."""
    sets = [o for o in ops if o.get("op") == "set-param"]
    if not sets:
        return RebuildPlan(False, "no parameter is set")
    cands = recover(inv)
    if not cands:
        return RebuildPlan(False, "no generator of ours matches this family's parameters "
                                  "(a family we did not generate, or one we cannot "
                                  "recover the spec of)")
    tried: List[Dict[str, Any]] = []
    for rec in cands:
        hits = [o for o in sets if o.get("caption") in rec.inputs]
        if not hits:
            tried.append({"generator": rec.generator, "product": rec.product,
                          "result": "no edited parameter is an input of this generator"})
            continue
        ok, why = _prove(rec, inv.path, work)
        tried.append({"generator": rec.generator, "product": rec.product,
                      "result": "reproduced" if ok else why})
        if not ok:
            continue
        plan = RebuildPlan(True, recovered=rec, candidates=tried)
        from ..famgen import archetypes as AR
        for o in ops:
            cap = o.get("caption")
            if o.get("op") == "set-param" and cap in rec.inputs:
                if o.get("type_name"):
                    return RebuildPlan(False, f"{cap}: a type-scoped edit of a "
                                              "generator input is not rebuilt", candidates=tried)
                k = rec.inputs[cap]
                unit = (AR.archetype(rec.product).param(k).unit
                        if rec.generator == "archetype" else "ft")
                plan.changes[cap] = (k, _natural(o["value"], unit))
            else:
                if o.get("op") == "set-param" and cap in rec.derived:
                    plan.derived.append(o)
                plan.rest.append(o)
        return plan
    # not rebuilt: still say which edited parameters the best-matching
    # generator COMPUTES (structure of the generator, not a proven spec)
    best = cands[0]
    derived = [o for o in sets if o.get("caption") in best.derived]
    return RebuildPlan(False, "; ".join(f"{t['product']}: {t['result']}" for t in tried),
                       recovered=best if derived else None, derived=derived,
                       candidates=tried)


def derived_caveat(rec: Recovered, op: dict) -> str:
    """The caveat for an edit of a parameter the generator COMPUTES."""
    from ..famgen import archetypes as AR
    keys = rec.derived.get(op.get("caption"), [])
    if rec.generator == "archetype":
        arch = AR.archetype(rec.product)
        names = [arch.param(k).label for k in keys]
    else:
        names = [c for c, k in rec.inputs.items() if k in keys]
    return (f"{op.get('caption')}: VALUE ONLY -- the {rec.product} generator computes this "
            f"parameter from {', '.join(names) or 'its other dimensions'}; the value is "
            "stored as given, the geometry does not follow it -- set "
            + ("that" if len(names) == 1 else "those") + " instead to change the family")


def rebuild(plan: RebuildPlan, out_path: str) -> Dict[str, Any]:
    """Write the family rebuilt at the new values to ``out_path``.  Raises the
    generator's refusal (the caller falls back to the value path, said)."""
    rec = plan.recovered
    assert rec is not None
    new = dict(rec.values)
    edited = []
    for cap, (k, v) in plan.changes.items():
        new[k] = v
        edited.append(k)
    # the input's family title + type names are KEPT (never changed silently);
    # when the input carried the generator's own dimension-derived name, the
    # kept name now describes the old size -- reported as ``name_stale``, and
    # the route (modify_family._name_note) words the note for the edit's own
    # renames and output file name (#994: Revit names a LOADED family by its
    # FILE name, so whether it replaces the placed family is the file's call)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    with _release_context(rec.release):
        prod, drop, refusals = _try_build(rec, new, rec.name, edited)
        if prod is None:
            raise RuntimeError("the generator refused the edited spec: "
                               + "; ".join(refusals[:3]))
        _write(prod, out_path)
    auto = GENERATORS[rec.generator]["auto_name"]
    name_stale: Optional[Dict[str, str]] = None
    try:
        if auto(rec, rec.values) == rec.name:
            fresh = auto(rec, new, drop)
            if fresh != rec.name:
                name_stale = {"old": rec.name, "fresh": fresh}
    except Exception:                                        # noqa: BLE001 -- a note only
        name_stale = None
    rederived = list(drop)
    return {
        "route": "regenerated",
        "generator": GENERATORS[rec.generator]["callable"],
        "product": rec.product,
        "start_id": rec.start_id,
        "options": dict(rec.options),
        "release": rec.release,
        "spec_recovered": {k: rec.values[k] for k in rec.values},
        "spec_built": {k: v for k, v in new.items() if k not in drop},
        "re_derived_by_generator": rederived,
        "name": getattr(prod, "name", None) or rec.name,
        "name_rule": "the input's family and type names are kept",
        **({"name_stale": name_stale} if name_stale else {}),
        "proof": "the generator on the recovered spec reproduced the input "
                 "byte for byte (sha256, written under the input's file name); "
                 "the output is byte-identical to a direct build at the new "
                 "value(s) WITH the input's name",
        "candidates": plan.candidates,
    }


# ---------------------------------------------------------------------------
# the value path's honest statement
# ---------------------------------------------------------------------------

def value_only_caveat(caption: str, labels: Sequence[Dict[str, Any]], reason: str,
                      *, via: Sequence[str] = ()) -> str:
    """The caveat a value-only edit of a LABELLING parameter carries."""
    dims = sorted({(l["class"], l["dim"]) for l in labels})
    shown = ", ".join(f"{c} {d}" for c, d in dims[:6]) + (" ..." if len(dims) > 6 else "")
    olds = sorted({round(float(l["stored"]), 9) for l in labels if l.get("stored") is not None})
    through = (f" (through the formula parameter(s) {', '.join(via)})" if via else "")
    return (f"{caption}: VALUE ONLY -- this parameter labels {len(dims)} dimension(s) "
            f"in this family{through} ({shown}), which still measure "
            f"{', '.join(f'{o:g}' for o in olds)} ft, and the geometry they hold "
            f"(reference planes, locked edges and faces, followers) did NOT move: "
            f"the family now disagrees with itself. No rebuild was possible: {reason}. "
            "What Revit does on opening such a file is unverified (hard rule 4)")
