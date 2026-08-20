"""rvt.famgen.catalog -- loader / query API for the MANUFACTURER FACTS STORE.

The facts store (``rvt/famgen/facts/<vendor>/<line>.json``) holds the
lawful DATA that drives family generation: published dimensional and rating
FACTS about real products, each figure tagged with its source (URL /
document / date accessed) and a per-field provenance flag
(``'fact'`` = read from a document, ``'assumed'`` = inferred / derived /
summary-only / not-yet-sourced).  See ``facts/LICENSE_NOTES.md`` for the
basis (facts are not copyrightable; we store no manufacturer files) and
``docs/writer/facts-store.md`` for the schema and workflow.

This module is deliberately conservative:

* it never fabricates a value -- a ``null`` fact stays ``None`` and
  :func:`require` raises rather than guessing;
* it distinguishes verified from assumed data so the generator can surface
  every ``assumed`` figure as an editable, unverified parameter;
* selection is by explicit selector (model / alias / rating value), never by
  fuzzy matching.

Public API::

    from rvt.famgen import catalog
    catalog.list_lines()                       -> [(vendor, line), ...]
    doc = catalog.load_line("eaton", "pow-r-line-panelboards")
    v   = catalog.get_variant("eaton", "pow-r-line-panelboards", model="PRL1X")
    v   = catalog.get_variant("eaton", "dry-type-transformers", kva=75)
    catalog.find_variants("square-d", "nq-nf-iline-panelboards",
                          voltage_max_ac_v=240)
    catalog.dims_feet(v)                       -> {'w': ft, 'h': ft, 'd': ft}
    catalog.provenance_report("eaton", "pow-r-line-panelboards")
    catalog.validate_line(doc)                 -> [problems]

CLI::

    python -m rvt.famgen.catalog list
    python -m rvt.famgen.catalog show   <vendor> <line>
    python -m rvt.famgen.catalog get    <vendor> <line> key=value ...
    python -m rvt.famgen.catalog validate

TERRITORY: reads only ``facts/**``; touches no other rvt module.
"""
from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ---------------------------------------------------------------------------
# locations / constants
# ---------------------------------------------------------------------------

FACTS_DIR = Path(__file__).resolve().parent / "facts"
IN_PER_FT = 12.0
MM_PER_IN = 25.4

PROVENANCE_FLAGS = ("fact", "assumed")
VERIFICATION_LEVELS = ("VERIFIED", "UNVERIFIED", "SEARCH-SUMMARY")

# leaf containers whose keys must each carry a field_provenance entry
_TRACKED = ("ratings", "dims_in", "options")


class CatalogError(LookupError):
    """No / ambiguous variant match, or a required fact is not sourced."""


# ---------------------------------------------------------------------------
# discovery / loading
# ---------------------------------------------------------------------------

def facts_dir() -> Path:
    """Return the facts directory (raises if the data was not installed)."""
    if not FACTS_DIR.is_dir():
        raise CatalogError(f"facts directory missing: {FACTS_DIR}")
    return FACTS_DIR


def list_lines() -> List[Tuple[str, str]]:
    """All ``(vendor, line)`` pairs present in the store, sorted."""
    out: List[Tuple[str, str]] = []
    for p in sorted(facts_dir().glob("*/*.json")):
        out.append((p.parent.name, p.stem))
    return out


def line_path(vendor: str, line: str) -> Path:
    p = facts_dir() / vendor / f"{line}.json"
    if not p.is_file():
        avail = ", ".join(f"{v}/{l}" for v, l in list_lines()) or "(none)"
        raise CatalogError(f"no facts record {vendor}/{line}; available: {avail}")
    return p


@lru_cache(maxsize=None)
def _load_cached(vendor: str, line: str) -> str:
    return line_path(vendor, line).read_text(encoding="utf-8")


def load_line(vendor: str, line: str) -> Dict[str, Any]:
    """Load one ``<vendor>/<line>.json`` record (fresh dict each call)."""
    return json.loads(_load_cached(vendor, line))


_GENERATION = 0


def generation() -> int:
    """How many times :func:`reload` has run -- a cache key for anything memoised on top of
    the records (``rvt.famgen.vendors.declared``), so a reload is seen downstream too."""
    return _GENERATION


def reload() -> None:
    """Drop the cache (after editing a JSON file in-process)."""
    global _GENERATION
    _load_cached.cache_clear()
    _GENERATION += 1


def all_lines() -> Dict[Tuple[str, str], Dict[str, Any]]:
    return {(v, l): load_line(v, l) for v, l in list_lines()}


# ---------------------------------------------------------------------------
# selection
# ---------------------------------------------------------------------------

def _norm(x: Any) -> Any:
    if isinstance(x, str):
        return x.strip().lower()
    return x


def _matches(actual: Any, wanted: Any) -> bool:
    """Selector match: scalar equality (case-insensitive for strings), or
    membership when the actual value is a list, or range containment when
    the actual value is a two-number ``[lo, hi]`` list and ``wanted`` is a
    number."""
    if isinstance(actual, list):
        if (len(actual) == 2 and isinstance(wanted, (int, float))
                and all(isinstance(a, (int, float)) for a in actual)):
            return actual[0] <= wanted <= actual[1]
        return _norm(wanted) in [_norm(a) for a in actual]
    return _norm(actual) == _norm(wanted)


def _variant_matches(v: Dict[str, Any], selector: Dict[str, Any]) -> bool:
    for key, wanted in selector.items():
        if key == "model":
            names = [v.get("model")] + list(v.get("aliases") or [])
            if _norm(wanted) not in [_norm(n) for n in names if n is not None]:
                return False
            continue
        # dotted path (ratings.kva) or bare key searched in ratings/options
        if "." in key:
            actual = _get_path(v, key)
        else:
            actual = _MISSING
            for cont in ("ratings", "options", "dims_in"):
                sub = v.get(cont) or {}
                if key in sub:
                    actual = sub[key]
                    break
            if actual is _MISSING and key in v:
                actual = v[key]
        if actual is _MISSING or not _matches(actual, wanted):
            return False
    return True


_MISSING = object()


def _get_path(obj: Any, path: str) -> Any:
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return _MISSING
    return cur


def find_variants(vendor: str, line: str, **selector: Any) -> List[Dict[str, Any]]:
    """Every variant of ``vendor/line`` matching ALL selector terms.

    Selector keys: ``model`` (matches the model or any alias), any ratings /
    options / dims_in key by bare name (e.g. ``kva=75``, ``mains_a=225``,
    ``voltage_max_ac_v=240``), or a dotted path (``ratings.temp_rise_c=150``).
    A numeric selector matches inside a two-element ``[lo, hi]`` range.
    No selector = every variant.
    """
    doc = load_line(vendor, line)
    variants = doc.get("variants") or []
    return [dict(v) for v in variants if _variant_matches(v, selector)]


def get_variant(vendor: str, line: str, **selector: Any) -> Dict[str, Any]:
    """Exactly one variant matching the selector; raises :class:`CatalogError`
    listing candidates when zero or several match (never a silent guess)."""
    hits = find_variants(vendor, line, **selector)
    if len(hits) == 1:
        return hits[0]
    models = [h.get("model") for h in (hits or find_variants(vendor, line))]
    what = "no" if not hits else f"{len(hits)} ambiguous"
    raise CatalogError(
        f"{what} variant match in {vendor}/{line} for {selector or 'no selector'}; "
        f"candidates: {models}")


# ---------------------------------------------------------------------------
# provenance / verification helpers
# ---------------------------------------------------------------------------

def leaf_paths(variant: Dict[str, Any]) -> List[str]:
    """The dotted leaf keys a variant is expected to tag with provenance:
    the top-level keys of ``ratings``, ``dims_in`` and ``options``."""
    out: List[str] = []
    for cont in _TRACKED:
        sub = variant.get(cont)
        if isinstance(sub, dict):
            out.extend(f"{cont}.{k}" for k in sub)
    return out


def field_provenance(variant: Dict[str, Any], path: str) -> Optional[str]:
    return (variant.get("field_provenance") or {}).get(path)


def is_fact(variant: Dict[str, Any], path: str) -> bool:
    return field_provenance(variant, path) == "fact"


def assumed_fields(variant: Dict[str, Any]) -> List[str]:
    """Leaf fields flagged ``assumed`` (surface as unverified parameters)."""
    fp = variant.get("field_provenance") or {}
    return sorted(k for k, v in fp.items() if v == "assumed")


def unsourced_fields(variant: Dict[str, Any]) -> List[str]:
    """Leaf fields whose value is ``None`` -- NOT SOURCED, never invent."""
    return [p for p in leaf_paths(variant) if _get_path(variant, p) is None]


def require(variant: Dict[str, Any], path: str, *, fact_only: bool = False) -> Any:
    """Return the value at ``path`` or raise if it is not sourced.

    ``fact_only=True`` additionally rejects ``assumed`` values -- use it for a
    dimension the generator must not fabricate. This is the mechanism that
    enforces "never invent a dimension without flagging 'assumed'": the
    generator asks the catalog to *require* it and gets an exception, not a
    guess.
    """
    val = _get_path(variant, path)
    if val is _MISSING or val is None:
        raise CatalogError(
            f"{variant.get('model')}: '{path}' is NOT SOURCED (null) -- refusing to fabricate; "
            f"see the record's notes / collection_posture")
    if fact_only and field_provenance(variant, path) != "fact":
        raise CatalogError(
            f"{variant.get('model')}: '{path}' is '{field_provenance(variant, path)}' "
            f"(not a verified fact) -- refusing under fact_only")
    return val


def provenance_report(vendor: str, line: str) -> Dict[str, Any]:
    """Counts of fact / assumed / unsourced fields plus source verification
    levels for a whole line -- the honesty audit."""
    doc = load_line(vendor, line)
    fact = assumed = unsourced = missing = 0
    for v in doc.get("variants") or []:
        for p in leaf_paths(v):
            flag = field_provenance(v, p)
            if flag == "fact":
                fact += 1
            elif flag == "assumed":
                assumed += 1
            else:
                missing += 1
            if _get_path(v, p) is None:
                unsourced += 1
    verif: Dict[str, int] = {}
    for s in (doc.get("sources") or {}).values():
        lvl = s.get("verification", "UNKNOWN")
        verif[lvl] = verif.get(lvl, 0) + 1
    return {
        "vendor": vendor, "line": line,
        "variants": len(doc.get("variants") or []),
        "fields_fact": fact, "fields_assumed": assumed,
        "fields_unsourced_null": unsourced, "fields_missing_flag": missing,
        "sources_by_verification": verif,
    }


# ---------------------------------------------------------------------------
# schema validation
# ---------------------------------------------------------------------------

_REQ_TOP = ("schema_version", "vendor", "line", "product_line", "category",
            "collection_posture", "sources", "variants")
_REQ_VARIANT = ("model", "ratings", "dims_in", "source", "field_provenance")


def validate_line(doc: Dict[str, Any]) -> List[str]:
    """Structural + provenance validation of one loaded record.

    Returns a list of human-readable problems (empty list = valid). Rules:
    top-level keys present; every source has url/doc/accessed/verification
    (verification in the known set); every variant has the required keys,
    ``dims_in`` has ``w``/``h``/``d`` keys (values may be null = not
    sourced), ``source`` has url/doc/accessed, and EVERY tracked leaf field
    has a ``field_provenance`` flag in {fact, assumed} -- no field escapes a
    provenance decision.
    """
    probs: List[str] = []
    ident = f"{doc.get('vendor')}/{doc.get('line')}"
    for k in _REQ_TOP:
        if k not in doc:
            probs.append(f"{ident}: missing top-level '{k}'")
    if not isinstance(doc.get("sources"), dict) or not doc.get("sources"):
        probs.append(f"{ident}: 'sources' must be a non-empty object")
    for sid, s in (doc.get("sources") or {}).items():
        for k in ("url", "doc", "accessed", "verification"):
            if k not in s:
                probs.append(f"{ident}: source {sid} missing '{k}'")
        if s.get("verification") not in VERIFICATION_LEVELS:
            probs.append(f"{ident}: source {sid} verification "
                         f"'{s.get('verification')}' not in {VERIFICATION_LEVELS}")
    variants = doc.get("variants")
    if not isinstance(variants, list) or not variants:
        probs.append(f"{ident}: 'variants' must be a non-empty list")
        return probs
    seen = set()
    for i, v in enumerate(variants):
        vid = f"{ident} variant[{i}] {v.get('model')!r}"
        for k in _REQ_VARIANT:
            if k not in v:
                probs.append(f"{vid}: missing '{k}'")
        model = v.get("model")
        if model in seen:
            probs.append(f"{vid}: duplicate model")
        seen.add(model)
        dims = v.get("dims_in") or {}
        for axis in ("w", "h", "d"):
            if axis not in dims:
                probs.append(f"{vid}: dims_in missing '{axis}' (use null if not sourced)")
        src = v.get("source") or {}
        for k in ("url", "doc", "accessed"):
            if k not in src:
                probs.append(f"{vid}: source missing '{k}'")
        fp = v.get("field_provenance")
        if not isinstance(fp, dict) or not fp:
            probs.append(f"{vid}: field_provenance must be a non-empty object")
            fp = {}
        for path in leaf_paths(v):
            flag = fp.get(path)
            if flag not in PROVENANCE_FLAGS:
                probs.append(f"{vid}: no provenance flag for '{path}' "
                             f"(got {flag!r}; want one of {PROVENANCE_FLAGS})")
    return probs


def validate_all() -> Dict[Tuple[str, str], List[str]]:
    """Validate every record in the store; ``{(vendor,line): [problems]}``."""
    out: Dict[Tuple[str, str], List[str]] = {}
    for (v, l) in list_lines():
        out[(v, l)] = validate_line(load_line(v, l))
    return out


# ---------------------------------------------------------------------------
# unit helpers (catalog stores inches; the family writer wants feet)
# ---------------------------------------------------------------------------

def in_to_ft(inches: Any) -> Any:
    """Inches -> feet. ``None`` (not sourced) is preserved; a non-numeric
    sentinel such as ``"VARIABLE"`` (height chosen from ``h_options`` by
    circuit count) passes through unchanged. Never zero-fills."""
    if inches is None or not isinstance(inches, (int, float)):
        return inches
    return inches / IN_PER_FT


def in_to_mm(inches: Any) -> Any:
    if inches is None or not isinstance(inches, (int, float)):
        return inches
    return inches * MM_PER_IN


def dims_feet(variant: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """The variant's ``dims_in`` w/h/d converted to feet (Revit internal).
    ``None`` (not sourced) and ``"VARIABLE"`` (chosen from ``h_options``)
    are preserved as-is -- never zero-filled or invented."""
    d = variant.get("dims_in") or {}
    return {axis: in_to_ft(d.get(axis)) for axis in ("w", "h", "d")}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _fmt(x: Any) -> str:
    return json.dumps(x, indent=2, ensure_ascii=False)


def _parse_selector(args: Iterable[str]) -> Dict[str, Any]:
    sel: Dict[str, Any] = {}
    for a in args:
        if "=" not in a:
            raise SystemExit(f"selector must be key=value, got {a!r}")
        k, v = a.split("=", 1)
        try:
            sel[k] = json.loads(v)          # numbers / lists / booleans
        except json.JSONDecodeError:
            sel[k] = v                      # plain string
    return sel


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "list"
    if cmd == "list":
        for v, l in list_lines():
            doc = load_line(v, l)
            print(f"{v}/{l:34s} {len(doc.get('variants') or [])} variants  "
                  f"[{doc.get('category')}]  {doc.get('product_line')[:70]}")
        return 0
    if cmd == "show" and len(argv) >= 3:
        doc = load_line(argv[1], argv[2])
        print(_fmt({k: doc[k] for k in ("vendor", "line", "product_line", "category")}))
        for v in doc["variants"]:
            print(f"  - {v['model']:22s} dims_in={v.get('dims_in')} "
                  f"assumed={len(assumed_fields(v))} unsourced={unsourced_fields(v)}")
        return 0
    if cmd == "get" and len(argv) >= 3:
        sel = _parse_selector(argv[3:])
        v = get_variant(argv[1], argv[2], **sel)
        print(_fmt(v))
        print("dims_feet:", _fmt(dims_feet(v)))
        print("assumed_fields:", assumed_fields(v))
        return 0
    if cmd == "validate":
        bad = 0
        for (v, l), probs in validate_all().items():
            status = "OK " if not probs else "BAD"
            print(f"[{status}] {v}/{l}")
            for p in probs:
                print("      -", p)
            bad += len(probs)
        for v, l in list_lines():
            print(f"       provenance {v}/{l}: {provenance_report(v, l)}")
        return 1 if bad else 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
