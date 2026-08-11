"""rvt.frontdoor.famspec -- the famspec INPUT CONTRACT of the router's rfa slot.

A famspec is a small JSON object ``{"kind": ..., <constructor kwargs>}``
asking tekton to GENERATE one family with its own constructors (issue #162):

    kind = panelboard  -> rvt.famgen.factory.make_panelboard(**fields)
    kind = transformer -> rvt.famgen.factory.make_transformer(**fields)
    kind = luminaire   -> rvt.famgen.factory.make_luminaire(kind=fixture, **fields)
    kind = device      -> rvt.famgen.factory.make_device(kind=device, **fields)
    kind = downlight   -> rvt.ifc.famfrom_ifc.make_downlight(**fields)   (measured
                          product archetype; owner machine until it emits on the
                          bundled base)

The written contract is ``spec/famspec.schema.json`` (JSON Schema draft-07,
our own text; ``spec/examples/famspec-*.json``).  This module:

* :func:`schema` / :func:`schema_path` -- load it (repo ``spec/`` or the
  plugin's mirrored copy; ``None`` when neither is on disk);
* :func:`validate` -- check a famspec against it with a stdlib-only
  validator for the draft-07 subset the schema uses (no jsonschema
  dependency), degrading to the built-in kind/type checks when the schema
  file is not shipped;
* :func:`normalise` -- split a famspec into ``(kind, constructor kwargs,
  route options)`` (``target_version`` is a ROUTE option, ``fixture`` /
  ``device`` are make_luminaire's / make_device's own ``kind``,
  ``shared_params: "default"`` is OUR file);
* :func:`build` / :func:`write` / :func:`is_refusal` -- the constructor
  dispatch, the one .rfa writer over both product types, and the "refused
  by name" classification the router's rfa cells call, so the router holds
  no per-kind logic.

Territory: perm-matrix / famspec-contract stream (new module).
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from .base import repo_root

__all__ = ["KINDS", "CATALOG_KINDS", "OWN_KIND_FIELD", "FamspecError", "schema_path", "schema",
           "validate", "check_schema", "normalise", "build", "write",
           "constructor_name", "is_refusal"]

#: the catalog kinds (rvt.famgen.factory) run anywhere; downlight (the
#: measured product archetype, rvt.ifc.famfrom_ifc) needs the research
#: corpus' family container until it emits on the bundled base
CATALOG_KINDS: Tuple[str, ...] = ("panelboard", "transformer", "luminaire", "device")
#: ``generic_model`` is NOT catalog-backed: its geometry is GIVEN by the
#: caller (vertices + height, or width/depth + height) -- the route for an
#: arbitrary 3D object, e.g. a Claude Design body (issue #498).
#: ``archetype`` is not catalog-backed either, and does not need the caller to
#: supply geometry: it GENERATES a named product (a cable tray, a strut
#: channel) at standard NOMINAL sizes for its class, every dimension reported
#: nominal or given, no manufacturer claim (rvt.famgen.archetypes, issue #591).
KINDS: Tuple[str, ...] = CATALOG_KINDS + ("downlight", "generic_model", "archetype")

#: famspec fields that steer the ROUTE, not the constructor
_ROUTE_FIELDS = ("target_version",)
#: famspec kind -> the field carrying that constructor's OWN ``kind`` argument
#: (renamed in the famspec because ``kind`` selects the constructor)
OWN_KIND_FIELD = {"luminaire": "fixture", "device": "device"}

SCHEMA_RELPATH = os.path.join("spec", "famspec.schema.json")
#: tools/sync_plugin.py mirrors spec/famspec.schema.json beside the native skill
_PLUGIN_RELPATH = os.path.join("skills", "tekton-native", "examples", "famspec.schema.json")


class FamspecError(ValueError):
    """The famspec is not a valid request (schema violation / unknown kind).
    ``problems`` = every violation found, one line each."""

    def __init__(self, problems: List[str]) -> None:
        self.problems = list(problems)
        super().__init__("; ".join(self.problems[:6])
                         + (f" (+{len(self.problems) - 6} more)" if len(self.problems) > 6 else ""))


# ---------------------------------------------------------------------------
# the schema file
# ---------------------------------------------------------------------------

def schema_path() -> Optional[str]:
    """``spec/famspec.schema.json`` in the repo, else the plugin's mirrored
    copy (``<plugin>/skills/tekton-native/examples/``, the plugin root found
    by :func:`rvt.frontdoor.standalone.plugin_root`), else None."""
    from .standalone import plugin_root
    cands = [os.path.join(repo_root(), SCHEMA_RELPATH)]
    proot = plugin_root()
    if proot:
        cands.append(os.path.join(proot, _PLUGIN_RELPATH))
    for p in cands:
        if os.path.isfile(p):
            return os.path.abspath(p)
    return None


_SCHEMA: Any = None            # None = not looked yet; False = looked, not shipped


def schema() -> Optional[Dict[str, Any]]:
    global _SCHEMA
    if _SCHEMA is None:
        p = schema_path()
        if p is None:
            _SCHEMA = False
        else:
            with open(p, encoding="utf-8") as fh:
                _SCHEMA = json.load(fh)
    return _SCHEMA or None


# ---------------------------------------------------------------------------
# a stdlib validator for the draft-07 subset spec/famspec.schema.json uses:
# type / enum / const / required / properties / additionalProperties
# (false = no other keys; a schema = every other key's VALUE is checked)
# / oneOf / anyOf / $ref (local) / minimum / maximum / exclusiveMinimum /
# minLength / minItems / items / pattern.  Anything else in a schema node is
# documentation (title / description / $schema / $id / definitions).
# ---------------------------------------------------------------------------

_TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "null": lambda v: v is None,
}


def _resolve_ref(root: Dict[str, Any], ref: str) -> Dict[str, Any]:
    if not ref.startswith("#/"):
        raise ValueError(f"only local $ref supported, got {ref!r}")
    node: Any = root
    for part in ref[2:].split("/"):
        node = node[part.replace("~1", "/").replace("~0", "~")]
    return node


def check_schema(value: Any, node: Dict[str, Any], root: Optional[Dict[str, Any]] = None,
                 where: str = "$") -> List[str]:
    """Validate ``value`` against schema ``node``; returns the problems
    (empty = valid).  ``root`` = the document ``$ref`` resolves in."""
    root = node if root is None else root
    if "$ref" in node:
        return check_schema(value, _resolve_ref(root, node["$ref"]), root, where)
    out: List[str] = []
    t = node.get("type")
    if t is not None:
        kinds = t if isinstance(t, list) else [t]
        if not any(_TYPES[k](value) for k in kinds):
            return [f"{where}: expected {'/'.join(kinds)}, got {type(value).__name__} {value!r}"[:200]]
    if "const" in node and value != node["const"]:
        out.append(f"{where}: must be {node['const']!r}, got {value!r}")
    if "enum" in node and value not in node["enum"]:
        out.append(f"{where}: {value!r} is not one of {node['enum']}")
    num = isinstance(value, (int, float)) and not isinstance(value, bool)
    if num:
        if "minimum" in node and value < node["minimum"]:
            out.append(f"{where}: {value} < minimum {node['minimum']}")
        if "maximum" in node and value > node["maximum"]:
            out.append(f"{where}: {value} > maximum {node['maximum']}")
        if "exclusiveMinimum" in node and value <= node["exclusiveMinimum"]:
            out.append(f"{where}: {value} must be > {node['exclusiveMinimum']}")
    if isinstance(value, str):
        if "minLength" in node and len(value) < node["minLength"]:
            out.append(f"{where}: string shorter than {node['minLength']}")
        if "pattern" in node and not re.search(node["pattern"], value):
            out.append(f"{where}: {value!r} does not match {node['pattern']!r}")
    if isinstance(value, list):
        if "minItems" in node and len(value) < node["minItems"]:
            out.append(f"{where}: fewer than {node['minItems']} items")
        if isinstance(node.get("items"), dict):
            for i, item in enumerate(value):
                out.extend(check_schema(item, node["items"], root, f"{where}[{i}]"))
    if isinstance(value, dict):
        for req in node.get("required", ()):
            if req not in value:
                out.append(f"{where}: '{req}' is required")
        props = node.get("properties") or {}
        for k, v in value.items():
            if k in props:
                out.extend(check_schema(v, props[k], root, f"{where}.{k}"))
            elif node.get("additionalProperties") is False:
                out.append(f"{where}: unknown field '{k}' (allowed: {', '.join(sorted(props))})")
            elif isinstance(node.get("additionalProperties"), dict):
                # a SCHEMA for every other key: the free-key maps the contract
                # uses (an archetype's 'dimensions', a family's
                # 'standard_values') -- their VALUES are checked even though
                # their names are open, so {"width_in": "wide"} is refused here
                # rather than surviving to the constructor
                out.extend(check_schema(v, node["additionalProperties"], root,
                                        f"{where}.{k}"))
    if "anyOf" in node:
        branches = [check_schema(value, b, root, where) for b in node["anyOf"]]
        if all(branches):
            out.append(f"{where}: matches none of the allowed shapes ("
                       + " | ".join(b[0].split(': ', 1)[-1] for b in branches) + ")")
    if "oneOf" in node:
        branches = [check_schema(value, b, root, where) for b in node["oneOf"]]
        n_ok = sum(1 for b in branches if not b)
        if n_ok != 1:
            out.extend(_one_of_problems(value, node["oneOf"], branches, n_ok, root, where))
    return out


def _one_of_problems(value: Any, alts: List[Dict[str, Any]], branches: List[List[str]],
                     n_ok: int, root: Dict[str, Any], where: str) -> List[str]:
    """Report a failed ``oneOf`` legibly: when the alternatives discriminate
    on a ``kind`` const (as the famspec kinds do), show only the problems of
    the branch whose kind matches instead of all four."""
    if isinstance(value, dict) and "kind" in value:
        for alt, probs in zip(alts, branches):
            node = _resolve_ref(root, alt["$ref"]) if "$ref" in alt else alt
            if ((node.get("properties") or {}).get("kind") or {}).get("const") == value["kind"]:
                return probs or [f"{where}: matches more than one alternative"]
    if n_ok > 1:
        return [f"{where}: matches {n_ok} alternatives, exactly one allowed"]
    return [p for b in branches for p in b[:2]]


# ---------------------------------------------------------------------------
# the contract: validate / normalise / build
# ---------------------------------------------------------------------------

def _builtin_problems(spec: Dict[str, Any]) -> List[str]:
    """The checks that hold even where the schema file is not shipped."""
    if not isinstance(spec, dict):
        return [f"$: a famspec is a JSON object with a 'kind', got {type(spec).__name__}"]
    kind = str(spec.get("kind") or "").strip().lower()
    if kind not in KINDS:
        return [f"$.kind: {spec.get('kind')!r} is not one of {list(KINDS)}"]
    tv = spec.get("target_version")
    if tv is not None and (isinstance(tv, bool) or not isinstance(tv, int)):
        return [f"$.target_version: expected an integer Revit year, got {tv!r}"]
    return []


def validate(spec: Any) -> List[str]:
    """Every problem with ``spec`` (empty = a valid famspec).  Uses
    ``spec/famspec.schema.json`` when it is on disk, else the built-in
    kind/type checks (the constructors then refuse bad values by name)."""
    probs = _builtin_problems(spec)
    if probs:
        return probs
    sch = schema()
    return check_schema(spec, sch) if sch is not None else []


def normalise(spec: Dict[str, Any]) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    """``(kind, constructor kwargs, route options)`` of a VALID famspec
    (raises :class:`FamspecError` otherwise).  Route options today:
    ``target_version``.  Constructor renames: luminaire ``fixture`` /
    device ``device`` -> ``kind``; ``shared_params: 'default'`` -> the
    factory's own file."""
    probs = validate(spec)
    if probs:
        raise FamspecError(probs)
    kind = str(spec["kind"]).strip().lower()
    kw = {k: v for k, v in spec.items() if k != "kind" and k not in _ROUTE_FIELDS}
    ropts = {k: spec[k] for k in _ROUTE_FIELDS if spec.get(k) is not None}
    own = OWN_KIND_FIELD.get(kind)
    if own and own in kw:
        kw["kind"] = kw.pop(own)
    if str(kw.get("shared_params") or "").strip().lower() == "default":
        from ..famgen import factory as F
        kw["shared_params"] = F.DEFAULT_SHARED_PARAMS
    return kind, kw, ropts


def build(kind: str, kw: Dict[str, Any], *, start_id: int = 1000):
    """Run the constructor for ``kind`` -> a product with ``.doc`` (FamilyDoc,
    whose ``category_id`` the loader binds), ``.name`` and ``.file_stem``."""
    if kind == "downlight":
        from ..ifc import famfrom_ifc as FFI
        return FFI.make_downlight(start_id=start_id, **kw)
    from ..famgen import factory as F
    return getattr(F, f"make_{kind}")(start_id=start_id, **kw)


def constructor_name(kind: str) -> str:
    return ("rvt.ifc.famfrom_ifc:make_downlight" if kind == "downlight"
            else f"rvt.famgen.factory:make_{kind}")


def write(prod: Any, path: str, *, report_path: Optional[str] = None) -> Dict[str, Any]:
    """Emit ``prod`` as a standalone .rfa at ``path``: ``FamilyProduct.write``
    (catalog kinds; rvt.frontdoor.standalone.standalone_family_write) or
    ``DownlightProduct.write_rfa``.  Returns the write report (validate /
    provenance / report_path)."""
    if hasattr(prod, "write_rfa"):
        return prod.write_rfa(path)
    return prod.write(path, report_path=report_path)


def is_refusal(exc: BaseException) -> bool:
    """True when the constructor REFUSED BY NAME (a fact the catalog lacks, a
    field it does not take) rather than failing to emit."""
    from ..famgen.factory import FactoryError
    from ..famgen.catalog import CatalogError
    from ..famgen.archetypes import ArchetypeError
    return isinstance(exc, (FactoryError, CatalogError, ArchetypeError, TypeError))
