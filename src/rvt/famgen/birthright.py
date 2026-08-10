"""rvt.famgen.birthright -- AUTHOR the template birth-state (rft-probes
stream, 2026-08-05).  OPT-IN: nothing in famgen changes unless
:func:`apply_birthright` is called explicitly.

WHY THIS MODULE EXISTS.  Desktop Revit creates every family FROM an
``.rft`` template -- a genuine famdoc is BORN with template content and
never assembled from nothing.  The instance-audit campaign's terminal
finding (genesis-audit verdicts #36..#42) is exactly that shape: a
donor-DERIVED famdoc reduced to our content passes the audit (SUB_ALL),
our from-scratch assembly fails (BX_conj), and the 16-record residue of
that matched pair sits in the SELF-FAMILY RECORD + HEADER.  If
template-birth inheritance is the law (the rft-probe T1/T2 rungs measure
it), the product fix is to make famgen AUTHOR the birth-state -- never to
copy template bytes.

THE ZERO-DONOR LINE (samples/SOURCES.md rules).  Templates are MINING
material.  What may be adopted from a measured template is a LAW or a
SHAPE: enum values, small integer counters, flags, category-coupled ids,
roster classes, ordering.  What must be authored fresh is IDENTITY and
CONTENT: GUIDs, names, high-entropy blobs, long strings.  The
:func:`adoptable` predicate encodes the line; :func:`apply_birthright`
refuses to carry a non-adoptable value and authors an equivalent instead
(fresh uuid4 for GUID-shaped values, our own names).

THE INPUT CONTRACT -- ``experiments/rft/template_birth.json`` (the acquire
stream's measurement of one ``.rft``; tolerant parse, minimum viable =
``class_histogram``)::

    {
      "version": 1,
      "source": {"rft": "samples/rft/<file>.rft", "sha256": "...",
                 "release": 2026},
      "famdoc": {
        "n_records": int,
        "self_family_id": int,
        "category_id": int,
        "part_type": int,
        "class_histogram": {"ClassName": count, ...},
        "self_family_fields": {"m_<key>": <json value>, ...},   # optional
        "self_family_header": {"m_<key>": <json value>, ...},   # optional
        "elements": [{"id": int, "class": str, "owner": int,
                      "name": str}, ...],                        # optional
        "layout": {"record_order": [...], ...}                   # optional
      }
    }

  Top-level OR nested under "famdoc" both parse; unknown keys ride along
  in ``BirthSpec.raw``.

THE THREE LANES of :func:`apply_birthright`:

  roster   author the birth ELEMENTS our famdoc lacks (template classes
           absent from our document), via the :data:`CONSTRUCTORS`
           registry -- ``{class_name: fn(doc, spec, count) -> [SkelElement]}``.
           v1 ships an EMPTY registry on purpose: the unauthorable list
           returned by :func:`birth_delta` IS the famgen author spec, and
           each entry is closed by registering a constructor (the catprobe
           precedent: measured law -> our constructor -> chain-coherent
           rebuild).
  fields   set the birth FIELD values on OUR self-Family (obj + header)
           for every adoptable measured field we currently emit
           differently -- the lane aimed at the SUB_ALL/F1 16-record
           residue.  Never introduces keys our writer does not emit;
           never carries a non-adoptable value.
  layout   reserved: physical-arrangement laws (emission order), wired to
           ``rvt.famgen.layout_law`` when a template layout fact demands
           it.  v1 records the request and does nothing.

USAGE (the T3 probe path in ``tools/rft_probe.py``)::

    from rvt.famgen import birthright as BR
    spec  = BR.read_birth_spec("experiments/rft/template_birth.json")
    delta = BR.birth_delta(doc, spec)      # doc: finalized famgen FamilyDoc
    if not delta["unauthorable"]:
        report = BR.apply_birthright(doc, spec)

VERSION 2 (birthright stream, post-verdict-#43).  ``tools/
birthright_mine.py mine`` measures a BORN specimen into a v2 spec
(``experiments/birthright/template_birth.json``) carrying the full birth
element models -- adoptable laws/shapes as plain JSON, references
symbolic, identity/content as ``{"__author__": ...}`` slots -- plus the
blank-pair type-table shape, the self-Family residue, the ownership
topology and the absorbed-index history.  :func:`apply_birthright`
detects a v2 spec and routes to :func:`apply_birthright_v2` (lanes
roster / topology / types / fields), every element CONSTRUCTED by our
writer, then :func:`birth_verify` machine-diffs the authored birth
against the mined spec (field-model equality modulo identity).

THE OPT-IN FAMGEN FLAG::

    from rvt.famgen import birthright as BR
    with BR.enabled("experiments/birthright/template_birth.json"):
        prod = factory.make_panelboard(...)   # famdoc BORN with the
                                              # authored birth set

Nothing in the default pipeline imports this module; ``enabled`` patches
the factory constructors for the duration of the ``with`` only (the
catprobe precedent) and FAILS the build on any authored-vs-mined
mismatch.

TERRITORY: this file, ``tools/rft_probe.py``, ``tests/test_rft_probe.py``
(rft-probes stream); v2 lanes + ``tools/birthright_mine.py`` +
``tests/test_birthright.py`` (birthright stream).  Imports famgen/genesis
modules; edits none of them.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

__all__ = ["BirthSpec", "read_birth_spec", "birth_delta", "apply_birthright",
           "adoptable", "CONSTRUCTORS", "register_constructor",
           "apply_birthright_v2", "author_birth_block", "birth_verify",
           "enabled", "resolve_roles", "materialize",
           "apply_birthright_v3", "apply_host_symbol_law",
           "apply_host_family_table_law",
           "apply_birthright_v4", "apply_born_identity", "identity_census",
           "BORN_HEADER_FLAGS", "BORN_EXTENT_FLAGS_3D", "born_header_flags",
           "BORN_IDENTITY_LAW", "BIRTH_SUFFIX_BASE"]


# ---------------------------------------------------------------------------
# the spec
# ---------------------------------------------------------------------------

@dataclass
class BirthSpec:
    """One measured birth-state (see the module contract).  Version-2 specs
    (tools/birthright_mine.py) additionally carry the full mined birth
    ELEMENT models (``birth_elements``: adoptable laws/shapes as plain
    JSON, references symbolic ``{"__eid__": born_id}`` / ``{"__role__":
    ...}``, identity/content as ``{"__author__": ...}`` slots), the born
    type-table shape, the ownership topology and the field policy."""
    path: str
    version: int
    source: Dict[str, Any]
    n_records: Optional[int]
    self_family_id: Optional[int]
    category_id: Optional[int]
    part_type: Optional[int]
    class_histogram: Dict[str, int]
    self_family_fields: Dict[str, Any] = field(default_factory=dict)
    self_family_header: Dict[str, Any] = field(default_factory=dict)
    elements: List[Dict[str, Any]] = field(default_factory=list)
    layout: Dict[str, Any] = field(default_factory=dict)
    birth_elements: List[Dict[str, Any]] = field(default_factory=list)
    type_table: Dict[str, Any] = field(default_factory=dict)
    topology: Dict[str, Any] = field(default_factory=dict)
    separators: Dict[str, Any] = field(default_factory=dict)
    field_policy: Dict[str, Any] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)

    def summary(self) -> Dict[str, Any]:
        return {"path": self.path, "version": self.version,
                "rft": (self.source or {}).get("rft"),
                "n_records": self.n_records,
                "category_id": self.category_id,
                "part_type": self.part_type,
                "n_classes": len(self.class_histogram),
                "has_self_family_fields": bool(self.self_family_fields),
                "has_layout": bool(self.layout),
                "n_elements_detailed": len(self.elements)}


def read_birth_spec(path: str) -> BirthSpec:
    """Parse ``template_birth.json`` tolerantly.  The famdoc facts may sit
    at top level or under ``famdoc``; the ONLY hard requirement is a
    non-empty ``class_histogram`` (a birth-state with no roster measures
    nothing)."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"birth spec not found: {path}")
    with open(path) as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: birth spec must be a JSON object")
    fam = data.get("famdoc") if isinstance(data.get("famdoc"), dict) else data
    hist = (fam.get("class_histogram") or fam.get("classes_histogram")
            or data.get("class_histogram") or {})
    if not isinstance(hist, dict) or not hist:
        raise ValueError(
            f"{path}: no class_histogram -- the minimum viable birth spec "
            f"is a per-class census of the template famdoc")
    hist = {str(k): int(v) for k, v in hist.items()}

    def _int(*keys) -> Optional[int]:
        for k in keys:
            for scope in (fam, data):
                v = scope.get(k)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    return int(v)
        return None

    return BirthSpec(
        path=path,
        version=int(data.get("version") or 1),
        source=dict(data.get("source") or {}),
        n_records=_int("n_records", "record_count"),
        self_family_id=_int("self_family_id", "self_family"),
        category_id=_int("category_id", "category"),
        part_type=_int("part_type"),
        class_histogram=hist,
        self_family_fields=dict(fam.get("self_family_fields") or {}),
        self_family_header=dict(fam.get("self_family_header") or {}),
        elements=list(fam.get("elements") or []),
        layout=dict(fam.get("layout") or {}),
        birth_elements=list(data.get("birth_elements") or []),
        type_table=dict(data.get("type_table") or {}),
        topology=dict(data.get("topology") or {}),
        separators=dict(data.get("separators_born") or {}),
        field_policy=dict(data.get("field_policy") or {}),
        raw=data,
    )


# ---------------------------------------------------------------------------
# the zero-donor adoption line
# ---------------------------------------------------------------------------

_GUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

#: strings longer than this are CONTENT (must be authored), not shape
_MAX_ADOPTABLE_STR = 24


def adoptable(key: str, value: Any) -> bool:
    """May a measured template value be adopted verbatim?  Laws and shapes
    yes; identity and content no (authored equivalents instead)."""
    if isinstance(value, bool) or value is None:
        return True
    if isinstance(value, (int, float)):
        return True                      # counters, enums, ids, flags
    if isinstance(value, str):
        if _GUID_RE.match(value):
            return False                 # identity -- author a fresh one
        return len(value) <= _MAX_ADOPTABLE_STR
    if isinstance(value, (list, dict)):
        items = value.values() if isinstance(value, dict) else value
        return all(adoptable(key, v) for v in items)
    if isinstance(value, (bytes, bytearray)):
        return False                     # blobs are content
    return False


def author_equivalent(key: str, value: Any) -> Any:
    """The authored stand-in for a non-adoptable measured value."""
    if isinstance(value, str) and _GUID_RE.match(value):
        return str(uuid.uuid4())
    if isinstance(value, str):
        return f"birthright-{key.lstrip('m_')[:16]}"
    if isinstance(value, (bytes, bytearray)):
        return b""
    return value


# ---------------------------------------------------------------------------
# the constructor registry (lane A)
# ---------------------------------------------------------------------------

#: {class_name: fn(doc, spec, count) -> list[SkelElement]} -- famgen-side
#: constructors for birth elements.  EMPTY by design in v1: the
#: unauthorable list from :func:`birth_delta` is the author spec, and each
#: entry is closed by registering a constructor here.
CONSTRUCTORS: Dict[str, Callable[..., List[Any]]] = {}


def register_constructor(class_name: str):
    """Decorator: ``@register_constructor("BrowserOrganization")``."""
    def deco(fn):
        CONSTRUCTORS[class_name] = fn
        return fn
    return deco


# ---------------------------------------------------------------------------
# the delta
# ---------------------------------------------------------------------------

def _doc_histogram(doc) -> Dict[str, int]:
    hist: Dict[str, int] = {}
    for e in getattr(doc, "elements", []) or []:
        c = getattr(e, "class_name", "?")
        hist[c] = hist.get(c, 0) + 1
    return hist


def _self_family(doc):
    sf = getattr(doc, "self_family", None)
    if sf is None:
        raise ValueError("doc has no self_family")
    return sf


def birth_delta(doc, spec: BirthSpec) -> Dict[str, Any]:
    """What separates OUR famdoc from the measured birth-state.

    Returns::

        {"missing_classes":  {class: count_missing},   # template has, we lack
         "surplus_classes":  {class: count_surplus},   # we have, template lacks
         "field_deltas":     [{key, ours, template, adoptable}...],
         "header_deltas":    [...same for the self-Family header...],
         "authorable":       [classes covered by CONSTRUCTORS],
         "unauthorable":     [classes missing a constructor  == author spec],
         "layout_requested": bool}
    """
    ours = _doc_histogram(doc)
    missing: Dict[str, int] = {}
    surplus: Dict[str, int] = {}
    for c, n in spec.class_histogram.items():
        d = n - ours.get(c, 0)
        if d > 0:
            missing[c] = d
    for c, n in ours.items():
        d = n - spec.class_histogram.get(c, 0)
        if d > 0:
            surplus[c] = d

    sf = _self_family(doc)
    field_deltas: List[Dict[str, Any]] = []
    for k, v in (spec.self_family_fields or {}).items():
        if k not in (sf.obj or {}):
            continue                     # never introduce unknown keys
        if sf.obj.get(k) != v:
            field_deltas.append({"key": k, "ours": sf.obj.get(k),
                                 "template": v,
                                 "adoptable": adoptable(k, v)})
    header_deltas: List[Dict[str, Any]] = []
    for k, v in (spec.self_family_header or {}).items():
        if k not in (sf.header or {}):
            continue
        if sf.header.get(k) != v:
            header_deltas.append({"key": k, "ours": sf.header.get(k),
                                  "template": v,
                                  "adoptable": adoptable(k, v)})

    authorable = sorted(c for c in missing if c in CONSTRUCTORS)
    unauthorable = sorted(c for c in missing if c not in CONSTRUCTORS)
    return {"missing_classes": missing, "surplus_classes": surplus,
            "field_deltas": field_deltas, "header_deltas": header_deltas,
            "authorable": authorable, "unauthorable": unauthorable,
            "layout_requested": bool(spec.layout)}


# ---------------------------------------------------------------------------
# the application (lanes)
# ---------------------------------------------------------------------------

def apply_birthright(doc, spec: BirthSpec, *,
                     lanes: Sequence[str] = ("roster", "fields")) -> Dict[str, Any]:
    """Augment OUR famdoc with the authored birth-state.  Mutates ``doc``
    (elements appended; self-Family fields set); returns the report.
    Refuses when lane ``roster`` is requested and a missing class has no
    constructor -- T3 is built honestly or not at all.

    A VERSION-2 spec (``birth_elements`` present) routes to the full
    author pipeline (:func:`apply_birthright_v2`): roster block + ownership
    topology + blank-pair type table + self-Family residue fields +
    absorbed-index history -- every element constructed by our writer from
    the mined shapes, zero donor bytes."""
    if spec.birth_elements:
        return apply_birthright_v2(doc, spec, lanes=(
            None if tuple(lanes) == ("roster", "fields") else lanes))
    delta = birth_delta(doc, spec)
    report: Dict[str, Any] = {"lanes": list(lanes), "delta": delta,
                              "roster_added": [], "fields_set": [],
                              "header_set": [], "authored_equivalents": [],
                              "layout": "not applied (v1 reserved)"}

    if "roster" in lanes:
        if delta["unauthorable"]:
            raise ValueError(
                f"birthright: {len(delta['unauthorable'])} missing birth "
                f"class(es) lack constructors: {delta['unauthorable'][:8]} "
                f"-- register them in rvt.famgen.birthright.CONSTRUCTORS "
                f"(the birth_delta output is the author spec)")
        for cls in delta["authorable"]:
            made = CONSTRUCTORS[cls](doc, spec,
                                     delta["missing_classes"][cls])
            for el in made or []:
                doc.elements.append(el)
                report["roster_added"].append(
                    {"id": getattr(el, "elem_id", None), "class": cls})

    if "fields" in lanes:
        sf = _self_family(doc)
        for d in delta["field_deltas"]:
            k, v = d["key"], d["template"]
            if not d["adoptable"]:
                v = author_equivalent(k, v)
                report["authored_equivalents"].append(
                    {"key": k, "authored": v})
            sf.obj[k] = v
            report["fields_set"].append(k)
        for d in delta["header_deltas"]:
            k, v = d["key"], d["template"]
            if not d["adoptable"]:
                v = author_equivalent(k, v)
                report["authored_equivalents"].append(
                    {"key": f"hdr.{k}", "authored": v})
            sf.header[k] = v
            report["header_set"].append(k)

    return report


# ===========================================================================
# VERSION 2 -- the AUTHOR lanes (mined-shape re-authoring, zero donor bytes)
# ===========================================================================
#
# The v2 spec (tools/birthright_mine.py) carries the full mined birth
# element models.  Every leaf is one of:
#   plain JSON            an ADOPTABLE law/shape (enum, counter, flag,
#                         category-coupled id, short/vocabulary string)
#   {"__eid__": born_id}  a symbolic reference into the birth set -- the
#                         author lane allocates OUR ids and remaps
#   {"__role__": name}    a reference to one of OUR frame elements
#                         ("self_family", "role:UnitsElem", ...)
#   {"__author__": slot}  identity/content -- AUTHORED here (fresh GUIDs
#                         from OUR document identity, our own names, empty
#                         blobs); the specimen's value never reaches this
#                         module.
#
# The lanes (apply_birthright_v2):
#   roster    author the whole birth block (styles/categories/fonts/
#             materials/patterns/settings) as OUR SkelElements
#   topology  flip OUR frame elements to the born ownership shape
#             (self-Family owns the UnitsElem / view chain / datums)
#   types     the blank-pair-first type table (the types5 law)
#   fields    the self-Family residue (obj fields + header scalars +
#             deletion prefix + the absorbed-index history law)

_V2_LANES = ("roster", "topology", "types", "fields")


class _Author:
    """Deterministic identity authoring for one application: fresh GUIDs
    and names derived from OUR document identity (uuid5 chain), stable
    within a build, never the specimen's."""

    def __init__(self, seed: str):
        self.seed = str(seed) or str(uuid.uuid4())
        self.n_guids = 0
        self.n_strings = 0
        self.n_bytes = 0

    def value(self, slot: Dict[str, Any], *, context: str = "") -> Any:
        kind = (slot or {}).get("kind")
        if kind == "guid":
            self.n_guids += 1
            return str(uuid.uuid5(uuid.NAMESPACE_URL,
                                  f"birthright:{self.seed}:guid:"
                                  f"{context}:{self.n_guids}"))
        if kind == "string":
            self.n_strings += 1
            stem = slot.get("shape_stem")
            if stem:
                return f"{stem}{self.n_strings}"
            return f"rvt-writer birth {self.n_strings}"
        if kind == "bytes":
            self.n_bytes += 1
            return b""
        return None

    def report(self) -> Dict[str, int]:
        return {"guids": self.n_guids, "strings": self.n_strings,
                "bytes": self.n_bytes}


def resolve_roles(doc, spec: BirthSpec) -> Dict[str, int]:
    """``{"self_family": id, "role:<Class>": id}`` over OUR document --
    every frame role the spec references must resolve to exactly ONE of
    our elements."""
    roles: Dict[str, int] = {"self_family": _self_family(doc).elem_id}
    wanted: set = set()

    def scan(node):
        if isinstance(node, dict):
            if set(node.keys()) == {"__role__"}:
                wanted.add(node["__role__"])
                return
            for v in node.values():
                scan(v)
        elif isinstance(node, list):
            for v in node:
                scan(v)

    for e in spec.birth_elements:
        scan(e.get("header"))
        scan(e.get("obj"))
        scan(e.get("rep"))
        if isinstance(e.get("owner"), str):
            wanted.add(e["owner"])
    scan(spec.self_family_fields)
    for role in sorted(wanted):
        if role == "self_family":
            continue
        if not role.startswith("role:"):
            raise ValueError(f"birthright: unknown role {role!r}")
        cls = role[len("role:"):]
        hits = [e for e in doc.elements if e.class_name == cls]
        if len(hits) != 1:
            raise ValueError(
                f"birthright: role {role!r} needs exactly one {cls} in our "
                f"document, found {len(hits)}")
        roles[role] = hits[0].elem_id
    return roles


def materialize(node: Any, idmap: Dict[int, int], roles: Dict[str, int],
                author: _Author, *, context: str = "") -> Any:
    """A mined field model -> OUR concrete value tree (refs remapped,
    author slots filled).  Raises on a reference outside the birth set --
    the miner's closure guarantees there are none."""
    if isinstance(node, dict):
        keys = set(node.keys())
        if keys == {"__eid__"}:
            b = int(node["__eid__"])
            if b not in idmap:
                raise ValueError(f"birthright: reference to born id {b} "
                                 f"outside the authored birth set")
            return idmap[b]
        if keys == {"__role__"}:
            return roles[node["__role__"]]
        if keys == {"__author__"}:
            return author.value(node["__author__"], context=context)
        return {k: materialize(v, idmap, roles, author,
                               context=f"{context}.{k}")
                for k, v in node.items()}
    if isinstance(node, list):
        return [materialize(v, idmap, roles, author, context=context)
                for v in node]
    return node


def author_birth_block(doc, spec: BirthSpec, roles: Dict[str, int],
                       author: _Author) -> Dict[str, Any]:
    """Lane ROSTER (v2): construct EVERY mined birth element as OUR
    SkelElement -- new ids in our document's space, references remapped,
    identity authored -- and append to ``doc.elements``.  Returns the
    report with the id map (born -> ours) the verify pass consumes."""
    from ..genesis.skeleton import SkelElement
    entries = spec.birth_elements
    if not entries:
        return {"n_added": 0, "idmap": {}}
    base = max(e.elem_id for e in doc.elements) + 1
    idmap = {int(e["born_id"]): base + i for i, e in enumerate(entries)}
    added: List[Any] = []
    for e in entries:
        new_id = idmap[int(e["born_id"])]
        ctx = f"{e['class']}:{e['born_id']}"
        hdr = materialize(e.get("header") or {}, idmap, roles, author,
                          context=ctx + ".hdr")
        obj = materialize(e.get("obj") or {}, idmap, roles, author,
                          context=ctx + ".obj")
        rep = e.get("rep")
        rep = (materialize(rep, idmap, roles, author, context=ctx + ".rep")
               if rep is not None else None)
        owner = e.get("owner")
        if isinstance(owner, str):
            owner_id = roles[owner]
        elif isinstance(owner, dict):
            owner_id = idmap[int(owner["__eid__"])]
        else:
            owner_id = -1
        added.append(SkelElement(new_id, str(e["class"]), hdr, obj, rep,
                                 owner_id=owner_id, kind="birthright"))
    doc.elements.extend(added)
    hist: Dict[str, int] = {}
    for a in added:
        hist[a.class_name] = hist.get(a.class_name, 0) + 1
    return {"n_added": len(added), "id_range": [base, base + len(added) - 1],
            "class_histogram": hist, "idmap": idmap}


def apply_topology(doc, spec: BirthSpec) -> Dict[str, Any]:
    """Lane TOPOLOGY (v2): the born famdoc's self-Family OWNS the frame;
    flip OUR top-level elements of the mined flip classes to self-Family
    ownership."""
    flips = list((spec.topology or {}).get("self_family_owned_ours_top")
                 or [])
    sf = _self_family(doc)
    flipped: List[Dict[str, Any]] = []
    for e in doc.elements:
        if (e.class_name in flips and e.elem_id != sf.elem_id
                and (e.owner_id or 0) <= 0):
            e.owner_id = sf.elem_id
            flipped.append({"id": e.elem_id, "class": e.class_name})
    return {"flip_classes": flips, "n_flipped": len(flipped),
            "flipped": flipped}


def apply_birth_types(doc, spec: BirthSpec) -> Dict[str, Any]:
    """Lane TYPES (v2): the blank-pair-first table (the born law: pair 0 is
    the blank ' ' current-values pair; the current index names a REAL
    type).  PRE-finalize mutation; the caller re-finalizes."""
    tt = spec.type_table or {}
    if not tt.get("blank_pair_first"):
        return {"applied": False, "why": "born table not blank-pair-first"}
    if not doc.types:
        raise ValueError("birthright: document has no types")
    if any(n == " " for n, _v in doc.types):
        return {"applied": False, "why": "blank pair already present"}
    base_name, base_vals = doc.types[doc.current_type]
    doc.types = [(" ", dict(base_vals))] + list(doc.types)
    doc.current_type = doc.current_type + 1
    return {"applied": True, "n_pairs": len(doc.types),
            "current_type": doc.current_type,
            "law": tt.get("law")}


def apply_birth_fields(doc, spec: BirthSpec, roles: Dict[str, int],
                       author: _Author) -> Dict[str, Any]:
    """Lane FIELDS (v2), POST-finalize: the self-Family residue -- mined
    obj fields (pre-filtered by the miner's policy; author slots filled
    here), header scalars, and the deletion PREFIX (the born header's
    non-element parents)."""
    sf = _self_family(doc)
    rep: Dict[str, Any] = {"fields_set": [], "header_set": [],
                           "skipped_unknown": []}
    for k, v in (spec.self_family_fields or {}).items():
        if k not in (sf.obj or {}):
            rep["skipped_unknown"].append(k)
            continue
        val = materialize(v, {}, roles, author, context=f"sf.{k}")
        if sf.obj.get(k) != val:
            sf.obj[k] = val
            rep["fields_set"].append(k)
    for k, v in (spec.self_family_header or {}).items():
        if k not in (sf.header or {}):
            rep["skipped_unknown"].append(f"hdr.{k}")
            continue
        if isinstance(v, (bool, int, float)) or v is None:
            if sf.header.get(k) != v:
                sf.header[k] = v
                rep["header_set"].append(k)
    prefix = [int(x) for x in
              (spec.field_policy or {}).get("deletion_prefix") or []]
    if prefix:
        par = ((sf.header.get("m_parents") or {}).get("value") or {})
        dele = par.get("m_deletion")
        if isinstance(dele, list):
            add = [x for x in prefix if x not in dele]
            dele[:0] = add
            rep["deletion_prefix"] = add
    return rep


def apply_birth_indices(doc, spec: BirthSpec,
                        idmap: Dict[int, int]) -> Dict[str, Any]:
    """Lane FIELDS (v2), POST-finalize: the absorbed-index HISTORY law.
    The born self-Family's element index carries the template's history
    gaps (sparse indices, next = max + 1).  Authored birth elements keep
    their mined indices; OUR content continues above the born maximum
    (exactly how a real fresh-from-template family continues)."""
    sf = _self_family(doc)
    born_index = {int(e["born_id"]): e.get("absorbed_index")
                  for e in spec.birth_elements
                  if e.get("absorbed_index") is not None}
    by_new = {idmap[b]: i for b, i in born_index.items() if b in idmap}
    pairs = ((sf.obj.get("m_familyIds") or {}).get("value") or {}) \
        .get("m_data")
    if not isinstance(pairs, list) or not by_new:
        return {"applied": False}
    nxt = max(by_new.values()) + 1
    n_ours = 0
    for p in pairs:
        eid = p.get("m_elementId")
        if eid in by_new:
            p["m_index"] = int(by_new[eid])
        else:
            p["m_index"] = nxt
            nxt += 1
            n_ours += 1
    sf.obj["m_nextAbsorbedIndex"] = nxt
    return {"applied": True, "born_indices": len(by_new),
            "our_continuation": n_ours, "next_absorbed_index": nxt,
            "law": "born indices carried (counter shapes); our elements "
                   "continue above the born max; next = max + 1"}


def apply_birthright_v2(doc, spec: BirthSpec, *,
                        lanes: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """The full v2 pipeline over a FINALIZED famgen FamilyDoc:
    roster -> topology -> types -> re-finalize -> fields (+ indices).
    Mutates ``doc``; returns the report (with the born->ours id map)."""
    lanes = tuple(lanes) if lanes is not None else _V2_LANES
    roles = resolve_roles(doc, spec)
    author = _Author(getattr(doc, "family_guid", "")
                     or getattr(doc, "document_guid", ""))
    report: Dict[str, Any] = {"version": 2, "lanes": list(lanes),
                              "roles": roles}
    was_finalized = bool(getattr(doc, "finalized", False))
    if was_finalized:
        doc.finalized = False
    idmap: Dict[int, int] = {}
    if "roster" in lanes:
        report["roster"] = author_birth_block(doc, spec, roles, author)
        idmap = report["roster"].get("idmap") or {}
    if "topology" in lanes:
        report["topology"] = apply_topology(doc, spec)
    if "types" in lanes:
        report["types"] = apply_birth_types(doc, spec)
    if hasattr(doc, "finalize"):
        doc.finalize()
        report["refinalized"] = True
    if "fields" in lanes:
        report["fields"] = apply_birth_fields(doc, spec, roles, author)
        if idmap:
            report["indices"] = apply_birth_indices(doc, spec, idmap)
    report["authored"] = author.report()
    report["idmap_size"] = len(idmap)
    # the verify pass needs the id map; keep it OFF the JSON-sized report
    report["_idmap"] = idmap
    return report


# ---------------------------------------------------------------------------
# the opt-in famgen flag (catprobe precedent: no shared famgen file edited)
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def enabled(spec_or_path, *, verify: bool = True, binds=None,
            version: int = 2):
    """OPT-IN: every family product built inside the ``with`` is authored
    THROUGH birthright -- ``factory.make_panelboard`` / ``make_transformer``
    / ``make_luminaire`` are wrapped so each finalized product document
    gains the authored birth set before it is loaded/emitted.  With
    ``verify`` (the default) each authored birth is MACHINE-DIFFED against
    the mined spec (field-model equality modulo identity) and a mismatch
    FAILS the build -- never a silent drift.  Nothing outside the ``with``
    changes; nothing in the default pipeline imports this.

    ``binds`` (v2 self-contained lane, optional): a render-binds sidecar
    (path or parsed dict -- see :func:`read_bind_spec`); when given, each
    product's form geometry is REBOUND to the authored in-unit style/
    material rows after the birth set lands (:func:`apply_render_binds`),
    and the walked-bind census must come back self-contained.

    ``version=3`` (species stream): route each product through
    :func:`apply_birthright_v3` (v2 + the HOSTSYM lane) AND live-patch
    ``rvt.famgen.loader.author_host_family`` for the duration of the
    ``with`` so the loader path's host Family type table keeps the native
    single-leading-blank shape (:func:`apply_host_family_table_law`);
    those loader reports land in the yielded dict's ``hostsym_loader``
    list.  ``version=2`` (the default) is byte-for-byte the previous
    behavior.

    ``version=4`` (identity stream, post-verdict-#47): v3 PLUS the BORN
    IDENTITY lane (:func:`apply_born_identity`) -- every family parameter's
    ``revit.local.family:`` identity suffix re-minted as a FROZEN BIRTH id
    in a small private birth space (the transplant shape every reduced-base
    PASS carries) and every skeleton header's ``m_abFlags4Bytes`` set to
    the born-standalone per-class value (:data:`BORN_HEADER_FLAGS`).  The
    v3 loader patch carries over unchanged."""
    spec = (spec_or_path if isinstance(spec_or_path, BirthSpec)
            else read_birth_spec(str(spec_or_path)))
    bind_spec = (read_bind_spec(binds) if isinstance(binds, str)
                 else binds)
    if version not in (2, 3, 4):
        raise ValueError(f"birthright.enabled: unknown version {version!r} "
                         f"(2, 3 or 4)")
    from . import factory as F
    saved: List[Any] = []
    reports: List[Dict[str, Any]] = []
    hostsym_loader: List[Dict[str, Any]] = []

    def wrap(fn):
        def wrapped(*a, **kw):
            prod = fn(*a, **kw)
            if version == 4:
                rep = apply_birthright_v4(prod.doc, spec)
            elif version == 3:
                rep = apply_birthright_v3(prod.doc, spec)
            else:
                rep = apply_birthright(prod.doc, spec)
            idmap = rep.pop("_idmap", {}) or {}
            entry = {"family": getattr(prod.doc, "name", "?"),
                     "n_added": (rep.get("roster") or {}).get("n_added"),
                     "report": rep}
            if bind_spec is not None:
                entry["binds"] = apply_render_binds(prod.doc, bind_spec,
                                                    idmap)
                census = walked_bind_census(prod.doc)
                entry["walked_bind_census"] = census
                if not census["self_contained"]:
                    raise ValueError(
                        f"selfcontained: walked binds not self-contained "
                        f"after rebind (foreign={census['foreign']}, "
                        f"unbound_form={census['unbound_form']})")
            if verify and spec.birth_elements:
                ver = birth_verify(prod.doc, spec, idmap,
                                   rep.get("roles") or {})
                entry["verify"] = {"ok": ver["ok"], "counts": ver["counts"],
                                   "n_elements": ver["n_elements"],
                                   "mismatches": ver["mismatches"][:8]}
                if not ver["ok"]:
                    raise ValueError(
                        f"birthright: authored birth diverges from the "
                        f"mined spec ({len(ver['mismatches'])} mismatches; "
                        f"first: {ver['mismatches'][:2]})")
            reports.append(entry)
            prod.notes.append(
                f"birthright: authored birth set applied "
                f"({(rep.get('roster') or {}).get('n_added')} elements, "
                f"zero donor bytes; spec {os.path.basename(spec.path)})")
            return prod
        wrapped.__name__ = fn.__name__
        return wrapped

    for name in ("make_panelboard", "make_transformer", "make_luminaire"):
        fn = getattr(F, name, None)
        if fn is None:
            continue
        saved.append((name, fn))
        setattr(F, name, wrap(fn))
    saved_loader = None
    if version >= 3:
        from . import loader as L
        _orig_ahf = L.author_host_family

        def _ahf_v3(product, plan, host):
            el = _orig_ahf(product, plan, host)
            hostsym_loader.append(apply_host_family_table_law(el))
            return el

        _ahf_v3.__name__ = _orig_ahf.__name__
        L.author_host_family = _ahf_v3
        saved_loader = (L, _orig_ahf)
    try:
        yield {"spec": spec.summary(), "reports": reports,
               "version": version, "hostsym_loader": hostsym_loader}
    finally:
        if saved_loader is not None:
            saved_loader[0].author_host_family = saved_loader[1]
        for name, fn in reversed(saved):
            setattr(F, name, fn)


# ---------------------------------------------------------------------------
# the machine diff: authored birth vs mined spec (field-model equality
# modulo identity)
# ---------------------------------------------------------------------------

def _diff_walk(spec_node: Any, got: Any, idmap: Dict[int, int],
               roles: Dict[str, int], path: str,
               out: Dict[str, Any]) -> None:
    if isinstance(spec_node, dict):
        keys = set(spec_node.keys())
        if keys == {"__eid__"}:
            want = idmap.get(int(spec_node["__eid__"]))
            if got == want:
                out["refs_remapped"] = out.get("refs_remapped", 0) + 1
            else:
                out.setdefault("mismatches", []).append(
                    {"path": path, "kind": "ref", "want": want, "got": got})
            return
        if keys == {"__role__"}:
            want = roles.get(spec_node["__role__"])
            if got == want:
                out["refs_remapped"] = out.get("refs_remapped", 0) + 1
            else:
                out.setdefault("mismatches", []).append(
                    {"path": path, "kind": "role", "want": want, "got": got})
            return
        if keys == {"__author__"}:
            out["authored"] = out.get("authored", 0) + 1
            kind = spec_node["__author__"].get("kind")
            if kind == "guid" and not (isinstance(got, str)
                                       and _GUID_RE.match(got)):
                out.setdefault("mismatches", []).append(
                    {"path": path, "kind": "authored-guid-shape",
                     "got": str(got)[:40]})
            return
        if not isinstance(got, dict) or set(got.keys()) != keys:
            out.setdefault("mismatches", []).append(
                {"path": path, "kind": "shape",
                 "want_keys": sorted(keys)[:8],
                 "got": (sorted(got.keys())[:8]
                         if isinstance(got, dict) else type(got).__name__)})
            return
        for k in spec_node:
            _diff_walk(spec_node[k], got[k], idmap, roles, f"{path}.{k}", out)
        return
    if isinstance(spec_node, list):
        if not isinstance(got, list) or len(got) != len(spec_node):
            out.setdefault("mismatches", []).append(
                {"path": path, "kind": "list-shape",
                 "want_len": len(spec_node),
                 "got": (len(got) if isinstance(got, list)
                         else type(got).__name__)})
            return
        for i, (a, b) in enumerate(zip(spec_node, got)):
            _diff_walk(a, b, idmap, roles, f"{path}[{i}]", out)
        return
    if spec_node == got:
        out["equal"] = out.get("equal", 0) + 1
    else:
        out.setdefault("mismatches", []).append(
            {"path": path, "kind": "value", "want": spec_node,
             "got": got})


def birth_verify(doc, spec: BirthSpec, idmap: Dict[int, int],
                 roles: Dict[str, int]) -> Dict[str, Any]:
    """MACHINE-DIFF the authored birth against the mined spec: every
    authored element's field model must equal the mined model modulo
    identity (references through the id map, author slots authored).
    Returns the verdict; ``ok`` demands ZERO mismatches."""
    by_id = {e.elem_id: e for e in doc.elements}
    out: Dict[str, Any] = {"n_elements": 0}
    for e in spec.birth_elements:
        new_id = idmap.get(int(e["born_id"]))
        el = by_id.get(new_id)
        if el is None:
            out.setdefault("mismatches", []).append(
                {"path": f"{e['class']}:{e['born_id']}",
                 "kind": "missing-element", "want": new_id})
            continue
        out["n_elements"] += 1
        ctx = f"{e['class']}:{e['born_id']}"
        if el.class_name != e["class"]:
            out.setdefault("mismatches", []).append(
                {"path": ctx, "kind": "class", "want": e["class"],
                 "got": el.class_name})
        _diff_walk(e.get("header") or {}, el.header, idmap, roles,
                   ctx + ".hdr", out)
        _diff_walk(e.get("obj") or {}, el.obj, idmap, roles,
                   ctx + ".obj", out)
        if e.get("rep") is not None:
            _diff_walk(e["rep"], el.rep, idmap, roles, ctx + ".rep", out)
        want_owner = e.get("owner")
        if isinstance(want_owner, str):
            want_owner = roles.get(want_owner)
        elif isinstance(want_owner, dict):
            want_owner = idmap.get(int(want_owner["__eid__"]))
        got_owner = el.owner_id if (el.owner_id or 0) > 0 else -1
        if (want_owner or -1) != got_owner:
            out.setdefault("mismatches", []).append(
                {"path": ctx, "kind": "owner", "want": want_owner,
                 "got": got_owner})
    out["mismatches"] = out.get("mismatches", [])
    out["ok"] = not out["mismatches"]
    out["counts"] = {k: out.get(k, 0) for k in
                     ("equal", "refs_remapped", "authored")}
    return out

# ---------------------------------------------------------------------------
# v2 SELF-CONTAINED lanes (selfcontained stream, 2026-08-05) -- the render
# BINDS.  MEASURED LAW (docs/inbox/selfcontained.md HR1; specimens: the
# vendor-born standalone .rfa + its T2a embedding, viewer-PASS on G_ABPD):
#
#   * a BORN famdoc's instanced-form geometry is BOUND to the famdoc's OWN
#     in-unit GStyleElem rows: the solid Geometry subNode's
#     ``GInfo.m_categoryId`` names the solid style (born 4087), every face's
#     ``m_pGFilling.GInfo.m_categoryId`` names the face-fill style (born
#     5564), the form's sketch CurveElems bind the sketch style (born 4123),
#     and every face's ``m_renderStyleId`` names an in-unit MaterialElem
#     (born 5265/5264) whose appearance asset is itself in-unit;
#   * OUR famgen famdoc emits ``-1`` on every one of those slots
#     (measured: B0/T0 -- 0 positive binds), so the audit's instance walk
#     must resolve the style OUTSIDE the unit: on rst that fallback lands on
#     born host rows (tolerated when the walk is carried by a born shell);
#     on the composed G_ABPD every landing row is OUR SUBSTITUTED element
#     (U16g's enumerated refs) or deleted -- and every ours-content famdoc
#     fails there;
#   * the EMBEDDED-donor species (U16g) binds HOST style rows directly --
#     the same landing, one hop earlier.
#
# THE LANE: after the authored birth set is applied (so the authored
# counterparts of the born style/material rows EXIST in-unit), rebind our
# form geometry to those in-unit locals.  The bind TARGETS are mined from
# the specimen into a small sidecar spec (tools/selfcontained.py
# mine-binds) carrying only symbolic born ids -- zero donor identity.
# ---------------------------------------------------------------------------

#: sidecar bind-spec keys -> what they bind [V specimen + T2a, measured]
BIND_ROLES = ("solid_style", "face_fill_style", "sketch_style",
              "render_material")


def read_bind_spec(path: str) -> Dict[str, Any]:
    """Parse the render-binds sidecar written by ``tools/selfcontained.py
    mine-binds``: ``{"binds": {role: {"__eid__": born_id}}, ...}``.
    Refuses a spec that names identity (only born ids may ride)."""
    with open(path) as fh:
        raw = json.load(fh)
    binds = raw.get("binds") or {}
    missing = [r for r in BIND_ROLES if r not in binds]
    if missing:
        raise ValueError(f"bind spec {path} is missing roles {missing}")
    for role, node in binds.items():
        if not (isinstance(node, dict) and set(node) == {"__eid__"}
                and isinstance(node["__eid__"], int)):
            raise ValueError(
                f"bind spec {path} role {role!r} must be a symbolic "
                f"{{'__eid__': born_id}} reference, got {node!r}")
    return raw


def apply_render_binds(doc, binds: Dict[str, Any],
                       idmap: Dict[int, int]) -> Dict[str, Any]:
    """Rebind OUR form geometry to the AUTHORED in-unit counterparts of the
    born style/material rows (see the lane comment above).  Requires the
    birth roster to be applied first (``idmap``: born id -> our id).
    Mutates ``doc``; returns the report.  Build-refusing when a target is
    absent or of the wrong class -- a dangling bind would be exactly the
    defect this lane exists to remove."""
    spec_binds = (binds.get("binds") or binds)
    targets: Dict[str, int] = {}
    by_id = {e.elem_id: e for e in doc.elements}
    want_class = {"solid_style": "GStyleElem", "face_fill_style": "GStyleElem",
                  "sketch_style": "GStyleElem",
                  "render_material": "MaterialElem"}
    for role in BIND_ROLES:
        born = int(spec_binds[role]["__eid__"])
        ours = idmap.get(born)
        if ours is None:
            raise ValueError(
                f"render bind {role}: born id {born} is not in the authored "
                f"birth id map -- the birth set does not carry its row")
        el = by_id.get(ours)
        if el is None or el.class_name != want_class[role]:
            raise ValueError(
                f"render bind {role}: authored counterpart {ours} is "
                f"{'absent' if el is None else el.class_name}, expected "
                f"{want_class[role]}")
        targets[role] = ours
    rep: Dict[str, Any] = {"targets": targets,
                           "bound": {"solid_nodes": 0, "faces_render": 0,
                                     "sketch_curves": 0, "material_field": 0}}
    for e in doc.elements:
        if e.class_name == "ExtrusionElem" and e.rep is not None:
            for sn in e.rep.get("m_subNodes") or []:
                if not (isinstance(sn, dict)
                        and sn.get("ptr_class") == "Geometry"):
                    continue
                gv = sn.get("value") or {}
                gi = gv.get("m_GInfo") or {}
                gi["m_categoryId"] = targets["solid_style"]
                gv["m_GInfo"] = gi
                rep["bound"]["solid_nodes"] += 1
                for f in gv.get("m_pFaces") or []:
                    fv = f.get("value") if isinstance(f, dict) else None
                    if isinstance(fv, dict) and "m_renderStyleId" in fv:
                        fv["m_renderStyleId"] = targets["render_material"]
                        rep["bound"]["faces_render"] += 1
            if isinstance(e.obj, dict) and "m_materialId" in e.obj:
                e.obj["m_materialId"] = targets["render_material"]
                rep["bound"]["material_field"] += 1
        elif e.class_name == "CurveElem" and e.rep is not None:
            gi = e.rep.get("m_GInfo") or {}
            if gi.get("m_categoryId", -1) == -1:
                gi["m_categoryId"] = targets["sketch_style"]
                e.rep["m_GInfo"] = gi
                rep["bound"]["sketch_curves"] += 1
            e.notes.append("selfcontained: sketch curve bound in-unit")
    if not rep["bound"]["solid_nodes"]:
        raise ValueError("render binds: no ExtrusionElem Geometry subNode "
                         "found to bind -- the form shape drifted")
    rep["law"] = ("born famdocs bind form geometry to their OWN in-unit "
                  "style/material rows; -1 leaves the resolution to the "
                  "host, which on a composed base lands on substituted "
                  "rows [V T2a in-unit binds PASS / B0 -1 FAIL / U16g "
                  "host binds FAIL -- docs/inbox/selfcontained.md]")
    return rep


def walked_bind_census(doc) -> Dict[str, Any]:
    """The machine gate's view of a FamilyDoc BEFORE emission: every
    form/curve style-bind slot with where it points (member id / -1 /
    foreign).  Zero ``foreign`` + zero ``unbound_form`` = self-contained
    on the walked-bind surface."""
    member = {e.elem_id for e in doc.elements}
    out = {"solid": [], "faces_render": [], "curves": [],
           "foreign": 0, "unbound_form": 0}
    for e in doc.elements:
        if e.class_name == "ExtrusionElem" and e.rep is not None:
            for sn in e.rep.get("m_subNodes") or []:
                if not (isinstance(sn, dict)
                        and sn.get("ptr_class") == "Geometry"):
                    continue
                gv = sn.get("value") or {}
                b = (gv.get("m_GInfo") or {}).get("m_categoryId", -1)
                out["solid"].append(b)
                if b == -1:
                    out["unbound_form"] += 1
                elif b not in member:
                    out["foreign"] += 1
                for f in gv.get("m_pFaces") or []:
                    fv = f.get("value") if isinstance(f, dict) else None
                    if isinstance(fv, dict):
                        r = fv.get("m_renderStyleId", -1)
                        out["faces_render"].append(r)
                        if r not in member and r != -1:
                            out["foreign"] += 1
                        if r == -1:
                            out["unbound_form"] += 1
        elif e.class_name == "CurveElem" and e.rep is not None:
            b = (e.rep.get("m_GInfo") or {}).get("m_categoryId", -1)
            out["curves"].append(b)
            if b not in member and b != -1:
                out["foreign"] += 1
    out["self_contained"] = out["foreign"] == 0 and out["unbound_form"] == 0
    return out


# ---------------------------------------------------------------------------
# VERSION 3 -- the REGISTERED SPECIES SHAPE (species stream, 2026-08-05)
#
# THE FORENSIC BASIS (experiments/species/cd_forensics.json; T2a = the ONLY
# reduced-base loaded-famdoc PASS, vs SC1 = the closest FAIL, same base,
# same famload lane):
#
#   * every registration STREAM surface is form-identical between the PASS
#     and the FAIL -- ContentDocuments framing (one entry, 0x3a3 separator,
#     end record), the inline ADocument (7 diff paths, ALL identity/count:
#     four history GUIDs = own unit GUID in BOTH, m_ownerFamilyId = own
#     self-Family, elem rows), the ContentTable record, the FamilyMgr
#     entry, the host Global/ElemTable rows, the partition separator.  The
#     hypothesized "standalone inline-ADocument form" (m_elemTable NULL,
#     owners externalized, NO history GUIDs) is the standalone FILE's
#     Global/Latest shape -- it is NOT the registered shape; T2a registers
#     through author_embedded_adocument like everything else.  Cross
#     evidence: U16g shipped the BORN wrapper (independent identity,
#     131/239 registries, donor build strings) and FAILED on G_ABPD; T2a
#     ships the authored-empty form and PASSES.  The ADocument axis is
#     dead on reduced bases; v3 changes NOTHING there.
#   * id policy: both register at watermark+1.. contiguous (current-id
#     policy stands; T2a's 45 small-id rep aliases are unremapped BORN
#     residue, tolerated per HR1, not a shape to author).
#   * THE ONE separating registered surface is the HOST SYMBOL TABLE:
#       - famload path (SC1): the v2 types lane prepends the blank pair to
#         ``doc.types``; famload authors one FamSymSurrogate+FamilySymbol
#         per doc.types entry and plan.symbol_id = the FIRST -- so SC1
#         registered a ' '-named FamSymSurrogate AND bound the placed
#         instance to the blank pair's symbol.  T2a registered exactly ONE
#         pair, first NON-blank name, instance bound to it.  No native
#         host row is ' '-named (rft_probe finding #4).
#       - famgen-loader path (DEMO v8): author_host_family copies the
#         BAKED unit type table ([' ', real]) and prepends its OWN blank
#         current-values row -> the host Family carried a DOUBLE-blank
#         table [' ', ' ', real] with m_idx = 1 POINTING AT A BLANK ROW.
#         Native law (measured, rstbasic host Family rows): at most ONE
#         leading blank; m_idx never names a blank when real pairs exist
#         (Notch: [' ', 'Notch'] m_idx 1).
#
# THE v3 LANE (hostsym): keep the born blank-pair-first law INSIDE the
# unit (v2 types lane, unchanged), and author the HOST registration the
# way the native corpus and the reduced-base PASS do:
#   1. post-finalize, strip blank pairs from the famload-facing
#      ``doc.types`` (the baked unit table is untouched) -> famload
#      authors real-named symbol pairs only and the instance binds a
#      real-named symbol;
#   2. under ``enabled(..., version=3)`` the famgen loader's
#      author_host_family is live-patched (corpus_symbol_form precedent)
#      to drop blank-named rows it copied from the unit table, restoring
#      the native [' ', real..] m_idx-on-real shape.
# Zero donor bytes; v1/v2 surfaces unchanged; opt-in only.
#
# PROMOTED TO PRODUCT (#10, docs/inbox/hostsym-product.md): both loaders now
# enforce this law themselves (``rvt.famgen.loader.real_type_names`` /
# ``symbol_type_name``; ``rvt.famload._plan_family``).  The v3 lane is KEPT
# as a verifier of the baked unit-side shape and for the species/identity
# accounting; on product output it has nothing left to change (the loader
# half reports ``applied: False``).
# ---------------------------------------------------------------------------

_V3_LANES = _V2_LANES + ("hostsym",)

HOST_SYMBOL_LAW = (
    "host symbol table = real-named pairs only (instance binds a real-named "
    "symbol); host Family type table = one leading blank current-values row "
    "+ real pairs, m_idx on a real pair; the unit-side table keeps the born "
    "blank-pair-first form [measured: T2a + native rstbasic hosts]")


def apply_host_symbol_law(doc) -> Dict[str, Any]:
    """Lane HOSTSYM (v3), POST-finalize: strip blank pairs from the
    famload-facing ``doc.types`` while the BAKED unit-side type table keeps
    the blank-pair-first born law.  Build-refusing on any shape drift
    (unfinalized doc, blank current type, a baked table that lost the
    blank-first form or whose current index names a blank)."""
    if not getattr(doc, "finalized", False):
        raise ValueError(
            "birthright v3 hostsym: document is not finalized -- the "
            "unit-side blank-pair table must be baked before the "
            "famload-facing strip")
    types = list(doc.types or [])
    names = [str(n) for n, _v in types]
    blanks = [i for i, n in enumerate(names) if not n.strip()]
    ci = int(getattr(doc, "current_type", 0) or 0)
    # verify the BAKED unit table first (never mutate on a drifted doc)
    sf = _self_family(doc)
    ftt = ((sf.obj.get("m_pFamilyTypes") or {}).get("value") or {})
    pairs = [str(p.get("name", "")) for p in (ftt.get("m_pairs") or [])]
    idx = ftt.get("m_idx")
    if not blanks:
        return {"applied": False, "why": "no blank pair in doc.types",
                "host_type_names": names, "unit_table_pairs": pairs,
                "unit_table_idx": idx}
    if not pairs or pairs[0].strip():
        raise ValueError(
            f"birthright v3 hostsym: baked unit type table is not "
            f"blank-pair-first ({pairs[:3]!r}) -- the born types5 law is "
            f"missing; refuse")
    if not (isinstance(idx, int) and 0 <= idx < len(pairs)
            and pairs[idx].strip()):
        raise ValueError(
            f"birthright v3 hostsym: baked unit table current index "
            f"{idx!r} does not name a REAL pair ({pairs!r}); refuse")
    if not names[ci].strip():
        raise ValueError(
            "birthright v3 hostsym: doc.current_type names the blank pair "
            "-- stripping it would leave no current host symbol; refuse")
    keep = [(n, v) for (n, v) in types if str(n).strip()]
    if not keep:
        raise ValueError("birthright v3 hostsym: no real-named type pair "
                         "to keep; refuse")
    new_ci = sum(1 for n in names[:ci] if n.strip())
    doc.types = keep
    doc.current_type = new_ci
    return {"applied": True, "stripped_blank_pairs": len(blanks),
            "host_type_names": [n for n, _v in keep],
            "current_type": new_ci,
            "unit_table_pairs": pairs, "unit_table_idx": idx,
            "law": HOST_SYMBOL_LAW}


def apply_host_family_table_law(host_family_el) -> Dict[str, Any]:
    """The famgen-loader half of the HOSTSYM lane: on an authored HOST
    ``Family`` element, drop blank-named type rows that were copied from
    the unit table, keeping the loader's own single leading blank
    current-values row; point m_idx at the first real pair.  Restores the
    native shape (rstbasic: [' ', 'Notch'] m_idx 1; single-type [' ']
    m_idx 0).  Since #10 the product loader authors that shape itself, so
    on loader output this is a verifier that reports ``applied: False``;
    ``native`` states the shape verdict positively either way (False only
    on the two off-shape early returns, which also carry ``why``)."""
    o = getattr(host_family_el, "obj", None) or {}
    ftt = ((o.get("m_pFamilyTypes") or {}).get("value") or {})
    pairs = ftt.get("m_pairs") or []
    if not pairs:
        return {"applied": False, "native": False,
                "why": "host Family has no type pairs"}
    head, rest = pairs[0], pairs[1:]
    if str(head.get("name", "")).strip():
        return {"applied": False, "native": False,
                "why": "no leading blank current-values row",
                "pairs": [p.get("name") for p in pairs]}
    keep = [p for p in rest if str(p.get("name", "")).strip()]
    dropped = len(rest) - len(keep)
    ftt["m_pairs"] = [head] + keep
    ftt["m_idx"] = 1 if keep else 0
    return {"applied": dropped > 0, "native": True,
            "dropped_blank_rows": dropped,
            "pairs": [p.get("name") for p in ftt["m_pairs"]],
            "m_idx": ftt["m_idx"]}


def apply_birthright_v3(doc, spec: BirthSpec, *,
                        lanes: Optional[Sequence[str]] = None
                        ) -> Dict[str, Any]:
    """The v3 pipeline: the FULL v2 pipeline (roster -> topology -> types
    -> re-finalize -> fields + indices), then the HOSTSYM lane on the
    finalized document.  The famgen-loader half of hostsym is wired by
    ``enabled(..., version=3)``."""
    lanes = tuple(lanes) if lanes is not None else _V3_LANES
    v2_lanes = tuple(l for l in lanes if l != "hostsym")
    rep = apply_birthright_v2(doc, spec, lanes=v2_lanes)
    rep["version"] = 3
    rep["lanes"] = list(lanes)
    if "hostsym" in lanes:
        rep["hostsym"] = apply_host_symbol_law(doc)
    return rep


# ===========================================================================
# VERSION 4 -- the BORN IDENTITY lane (identity stream, post-verdict-#47)
# ===========================================================================
#
# THE MEASURED LAW (tools/identity_probe.py forensics ->
# experiments/identity/identity_diff.json):
#
# * Every famdoc element's ``revit.local.family:<32-hex session><8-hex
#   id>-1.0.0`` family-parameter identity records the id the parameter had
#   AT BIRTH and is FROZEN thereafter: native containers carry suffix ==
#   current id (rst host 120/120 SELF, rst embedded units 243/243 SELF)
#   because they ARE the birth container; every REBASED transplant carries
#   suffix != current id (OTHER) because the string never re-derives.
# * On the reduced base G_ABPD the four loaded-famdoc cells split exactly
#   on that axis: T2a + TB0g (all params OTHER -- transplant-shaped birth
#   identity) PASS; T1uG + SC1 (our params SELF -- identity minted at the
#   host-watermark current id, i.e. coupled to the host's id/episode
#   state) FAIL.  The same SELF bytes pass on pristine rst (T1u), so the
#   coupling expresses only on reduced substrates -- the verdict-#47 law.
# * The seq-101 header ``m_abFlags4Bytes`` carries a per-class
#   species-coherent value: the born-standalone table below (measured on
#   the vendor .rfa, == T2a's PASS bytes; the embedded species differs
#   only by the 0x10 bit).  Our authored famdocs deviate per class (stray
#   0x800 on view classes, missing 0x2000+0x14 on SunAndShadowSettings,
#   missing 0x10 on datum/view classes) -- the only other element-level
#   identity-adjacent surface separating ours from born on the matched
#   pair.
#
# The lane is OPT-IN (version=4), single-purpose, and refuses loudly on
# any shape it does not understand.  Zero donor bytes: the birth ids are
# OUR mint in a private small id space; the flags are per-class laws
# (adoptable shapes under the zero-donor line).

_V4_LANES = _V3_LANES + ("identity",)

BORN_IDENTITY_LAW = (
    "family-parameter identity ('revit.local.family:<session><id>-1.0.0') "
    "= the FROZEN BIRTH id, minted in a small private birth space disjoint "
    "from the host id allocation (suffix != current element id -- the "
    "transplant shape of every reduced-base PASS); header m_abFlags4Bytes "
    "= the born-standalone per-class value [measured: vendor .rfa == T2a "
    "PASS; rst units 243/243 suffix-frozen at birth]")

#: the born-standalone per-class ``m_abFlags4Bytes`` values, measured on
#: vendor/phi-ag-rvt/examples/Autodesk/racbasicsamplefamily-2026.rfa (the
#: T2a source -- the ONLY reduced-base loaded-famdoc PASS species) and
#: byte-confirmed against T1uG's shell block.  Only classes our skeleton
#: authors are listed; classes absent from the table are left untouched.
#: ExtentElem is role-split in the specimen (plan/section satellites 26,
#: the DBView3d satellite 10 -- ExtentElem {26: 6, 10: 1} against 2 plan +
#: 4 section + 1 3D views): the table carries the plan/section value and
#: :func:`born_header_flags` resolves the role per element, now that every
#: generated family carries the "View 1" DBView3d (#381).
BORN_HEADER_FLAGS: Dict[str, int] = {
    "Level": 2074,
    "LevelAttributes": 30,
    "DBViewType": 26,
    "DBViewPlan": 26,
    "Viewer": 26,
    "Viewport": 26,
    "DBDrawing": 8218,
    "ExtentElem": 26,
    "SketchPlane": 26,
    "RefPlane": 2074,
    "SunAndShadowSettings": 8222,
}

#: the DBView3d satellite's ExtentElem value (the role split above)
BORN_EXTENT_FLAGS_3D = 10


def _view3d_ids(els) -> set:
    return {int(e.elem_id) for e in els if e.class_name == "DBView3d"}


def _extent_view_id(el):
    """The view an ExtentElem is the satellite of (its ``m_dbViewId``)."""
    return (getattr(el, "obj", None) or {}).get("m_dbViewId")


def born_header_flags(el, view3d_ids) -> Optional[int]:
    """The born-standalone ``m_abFlags4Bytes`` value for ``el`` -- the
    :data:`BORN_HEADER_FLAGS` table value, except an ExtentElem whose
    ``m_dbViewId`` names a DBView3d (``view3d_ids``) carries
    :data:`BORN_EXTENT_FLAGS_3D`.  None = class not covered (untouched)."""
    if el.class_name == "ExtentElem" and _extent_view_id(el) in view3d_ids:
        return BORN_EXTENT_FLAGS_3D
    return BORN_HEADER_FLAGS.get(el.class_name)


#: the private birth-id space the identity lane mints family-parameter
#: birth ids in: small (far below any project watermark), disjoint from
#: the born specimens' own param ids (4208..5812) and from every live id.
BIRTH_SUFFIX_BASE = 4096
_BIRTH_SUFFIX_SPAN = 100          # > params per family, < 4208 - 4096

_LOCAL_FAMILY_RE = re.compile(
    r"^revit\.local\.family:([0-9a-f]{32})([0-9a-f]{8})-(.+)$")


def _param_type_id_parts(el) -> Optional[Dict[str, Any]]:
    """(session hex, embedded id, version tail) of a ParamElemFamily's
    ``m_typeId`` identity string, or None when the param does not carry
    the session form."""
    pd = ((el.obj.get("m_pParamDef") or {}).get("value") or {})
    tid = pd.get("m_typeId")
    s = str((tid or {}).get("m_typeId") or "") if isinstance(tid, dict) \
        else ""
    m = _LOCAL_FAMILY_RE.match(s)
    if not m:
        return None
    return {"session": m.group(1), "embedded_id": int(m.group(2), 16),
            "tail": m.group(3), "slot": tid}


def apply_born_identity(doc, *,
                        suffix_base: int = BIRTH_SUFFIX_BASE
                        ) -> Dict[str, Any]:
    """Lane IDENTITY (v4), POST-finalize: re-mint every family parameter's
    identity suffix as a FROZEN BIRTH id in the private birth space, and
    set every covered header's ``m_abFlags4Bytes`` to the born-standalone
    value (ExtentElem by role: plan/section satellite 26, the DBView3d's
    satellite 10).  Mutates ``doc.elements`` in place; build-refusing on
    any unexpected shape (unfinalized doc, a param whose suffix is not the
    famgen SELF mint, an ExtentElem naming a view the document does not
    carry, birth-space overflow)."""
    if not getattr(doc, "finalized", False):
        raise ValueError(
            "birthright v4 identity: document is not finalized -- the "
            "identity re-mint runs on the baked element list")
    els = list(doc.elements)
    ids = {int(e.elem_id) for e in els}
    view3d_ids = _view3d_ids(els)
    extent_roles: Dict[str, int] = {}
    for el in els:
        if el.class_name != "ExtentElem":
            continue
        vid = _extent_view_id(el)
        if vid not in ids:
            raise ValueError(
                f"birthright v4 identity: ExtentElem {el.elem_id} names "
                f"view {vid!r}, which the document does not carry -- its "
                f"flags role (plan/section 26 vs DBView3d 10) is "
                f"undecidable; refuse")
        role = "view3d" if vid in view3d_ids else "plan_section"
        extent_roles[role] = extent_roles.get(role, 0) + 1
    params = sorted((e for e in els if e.class_name == "ParamElemFamily"),
                    key=lambda e: int(e.elem_id))
    if len(params) >= _BIRTH_SUFFIX_SPAN:
        raise ValueError(
            f"birthright v4 identity: {len(params)} family parameters "
            f"overflow the private birth space "
            f"({suffix_base}+{_BIRTH_SUFFIX_SPAN}); widen deliberately")
    suffixes: List[Dict[str, Any]] = []
    for k, el in enumerate(params):
        parts = _param_type_id_parts(el)
        if parts is None:
            raise ValueError(
                f"birthright v4 identity: ParamElemFamily {el.elem_id} "
                f"carries no 'revit.local.family:' session identity -- "
                f"unexpected shape; refuse")
        if parts["embedded_id"] != int(el.elem_id):
            raise ValueError(
                f"birthright v4 identity: ParamElemFamily {el.elem_id} "
                f"identity suffix already embeds {parts['embedded_id']} "
                f"(not the famgen SELF mint) -- refusing to re-mint an "
                f"identity this lane did not shape")
        birth_id = suffix_base + k
        parts["slot"]["m_typeId"] = (
            f"revit.local.family:{parts['session']}"
            f"{birth_id & 0xFFFFFFFF:08x}-{parts['tail']}")
        suffixes.append({"param": int(el.elem_id), "birth_id": birth_id})
    flags_set: Dict[str, int] = {}
    flags_changed = 0
    for el in els:
        want = born_header_flags(el, view3d_ids)
        if want is None:
            continue
        hdr = getattr(el, "header", None)
        if not isinstance(hdr, dict) or "m_abFlags4Bytes" not in hdr:
            raise ValueError(
                f"birthright v4 identity: {el.class_name} {el.elem_id} "
                f"header carries no m_abFlags4Bytes -- unexpected shape")
        if int(hdr["m_abFlags4Bytes"]) != int(want):
            flags_changed += 1
        hdr["m_abFlags4Bytes"] = int(want)
        flags_set[el.class_name] = flags_set.get(el.class_name, 0) + 1
    return {"applied": True, "law": BORN_IDENTITY_LAW,
            "suffix_base": int(suffix_base),
            "n_suffixes_reminted": len(suffixes),
            "suffixes": suffixes,
            "flags_classes": flags_set,
            "flags_headers_covered": sum(flags_set.values()),
            "flags_changed": flags_changed,
            "extent_roles": extent_roles}


def identity_census(doc) -> Dict[str, Any]:
    """The machine gate for v4-authored documents: every family parameter
    carries the session identity form with a FROZEN-BIRTH suffix (small,
    != the element's current id) and every covered header carries the
    born-standalone flags value.  ``identity_ok`` gates BX_v4 / DEMO
    v10."""
    params = []
    off_form = []
    self_minted = []
    big_suffix = []
    flags_off = []
    view3d_ids = _view3d_ids(doc.elements)
    for el in doc.elements:
        if el.class_name == "ParamElemFamily":
            parts = _param_type_id_parts(el)
            if parts is None:
                off_form.append(int(el.elem_id))
                continue
            row = {"param": int(el.elem_id),
                   "embedded_id": parts["embedded_id"]}
            params.append(row)
            if parts["embedded_id"] == int(el.elem_id):
                self_minted.append(row)
            if parts["embedded_id"] >= (1 << 20):
                big_suffix.append(row)
        want = born_header_flags(el, view3d_ids)
        if want is not None:
            got = (getattr(el, "header", None) or {}).get("m_abFlags4Bytes")
            if got != want:
                flags_off.append({"id": int(el.elem_id),
                                  "class": el.class_name,
                                  "got": got, "want": want})
    checks = {
        "params_session_form": not off_form,
        "no_self_minted_suffix": not self_minted,
        "suffixes_in_small_birth_space": not big_suffix,
        "born_header_flags": not flags_off,
    }
    return {"n_params": len(params), "params": params,
            "params_off_form": off_form, "self_minted": self_minted,
            "big_suffix": big_suffix, "flags_off": flags_off,
            "checks": checks, "identity_ok": all(checks.values())}


def apply_birthright_v4(doc, spec: BirthSpec, *,
                        lanes: Optional[Sequence[str]] = None
                        ) -> Dict[str, Any]:
    """The v4 pipeline: the FULL v3 pipeline (v2 lanes + HOSTSYM), then
    the BORN IDENTITY lane on the finalized document.  The identity
    census must come back green -- a v4 build that fails its own gate
    refuses."""
    lanes = tuple(lanes) if lanes is not None else _V4_LANES
    v3_lanes = tuple(l for l in lanes if l != "identity")
    rep = apply_birthright_v3(doc, spec, lanes=v3_lanes)
    rep["version"] = 4
    rep["lanes"] = list(lanes)
    if "identity" in lanes:
        rep["identity"] = apply_born_identity(doc)
        census = identity_census(doc)
        rep["identity_census"] = {k: census[k] for k in
                                  ("n_params", "checks", "identity_ok")}
        if not census["identity_ok"]:
            raise ValueError(
                f"birthright v4 identity: census not green after the lane "
                f"({census['checks']}) -- refusing to emit")
    return rep
