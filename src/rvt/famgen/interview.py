"""rvt.famgen.interview -- the QUESTION ENGINE: the ordered RESIDUE a prompt leaves.

THE ASK, AND THE CORRECTION IT ALREADY CARRIES.  Owner steer #684
(``docs/STEERING.md`` S-2026-08-11-b) asked that a bare product prompt walk the
user from the word to a fully specified family -- *"if i ask for a tansformer in
a simple prompt, i need series of questions to get to the specific detail that
the family would be generated. even the vendor etc everything and anything"* --
and that the questions be DERIVED, never hand-written per product: *"this needs
to be a universal database engine"*.  Steers #685 and #687 then moved the
emphasis before a line of this was written: **the prompt is the interface**, and
*"lines of questions are just for use if the prompt is not descriptive
enough"* / *"if its broad ask questions"*.

So this module is NOT a form.  Its whole subject is the **residue**: what a
prompt, read as far as it can be read, still leaves undetermined.  A descriptive
prompt leaves none and is built immediately (:attr:`Plan.enough` is True with an
empty :attr:`Plan.questions`); a broad prompt leaves a lot, most decisive first.
:func:`plan` takes the prompt FIRST and the answers second, and there is no
entry point that asks a question the prompt already answered.

WHERE THE QUESTIONS COME FROM (the universal-database requirement).  Nothing in
this file knows what a transformer is.  Every question is derived from a
registry the engine already holds:

==============  ==========================================  =========================================
source          answers                                     for "a transformer"
==============  ==========================================  =========================================
``catalog``     which real products we hold FACTS for        vendor eaton / hps; the kVA rows each publishes
``archetypes``  what we can GENERATE at nominal sizes        the parameter list, nominals, standard sizes
``standards``   what an engineer will SCHEDULE it by         the category's standard parameters, spec + group
``taxonomy``    which kinds exist at all                     -- (not built yet)
``vendors``     which vendors exist at all                   -- (not built yet)
==============  ==========================================  =========================================

Two of those five are in flight on unmerged PRs (``archetypes`` #674,
``taxonomy`` / ``vendors`` #692), so :data:`SOURCES` is a **pluggable source
list** loaded by name at call time: an absent source contributes nothing, is
never imported unconditionally, and is named as absent in
:func:`source_status` and in every :class:`Plan` and :class:`Resolution`.  A
question set is therefore honest about how much of the engine was actually
readable when it was produced.

Adding a **vendor**, a **product line** or a **rating row** to the facts store
adds its questions and its choices with no edit here: the vendor list is the
catalog's own vendors, a line's identifying question is whichever ratings key
separates its variants, and the published option lists become the choices.  A
whole new *kind* still needs its constructor -- an engine cannot offer to build
what it has no constructor for -- and :func:`unbuildable_categories` reports any
catalog category in that state rather than pretending to interview for it.

ONLY CHOICES THE ENGINE CAN ACTUALLY DELIVER.  Every catalog-derived choice is
PROBED through the kind's own facts resolver before it is offered
(:func:`_deliverable`).  Eaton's 500 kVA row is in the catalog and publishes no
dimensions ("Contact Eaton representative"), so it is not on the kVA list -- an
interview that offered it would be collecting an answer it could only refuse.
A question left with exactly ONE deliverable choice is not a question at all:
the engine fills it and says so.

THE TIERS FALL OUT OF WHO SUPPLIED THE VALUE (not out of the key):

======== =====================================================================
``fact``    read back from a catalog record we hold
``given``   the user answered it (typed, or picked a choice)
``nominal`` nobody answered; standard practice for the class supplied it -- an
            archetype nominal, or the constructor's own documented default
``blank``   nobody answered and nothing standard applies; it stays empty, and
            an empty standard parameter is the honest state (never invented)
======== =====================================================================

HARD RULE 1 IS THE POINT, NOT A FOOTNOTE.  A question loop that withholds the
file is the failure mode this module exists to avoid, so :func:`resolve` is
total: it takes a plan at ANY stage -- zero answers included -- and returns a
famspec the router already accepts, with :attr:`Resolution.assumed` naming
every answer that was assumed rather than given.  There is no state of this
engine in which a caller has to answer something to get a file.

Territory: famgen (new module; reads the registries and the constructors'
signatures, writes no family and edits no writer path).
"""
from __future__ import annotations

import importlib
import inspect
import re
from dataclasses import dataclass, field as dc_field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

__all__ = [
    "InterviewError", "TIERS", "FACT", "GIVEN", "NOMINAL", "BLANK",
    "Source", "SOURCES", "source_status", "load_source",
    "Choice", "Question", "Answered", "Plan", "Resolution",
    "RANKS", "kinds", "describe_kind", "unbuildable_categories",
    "plan", "answer", "resolve", "check_registry",
]


class InterviewError(ValueError):
    """A request the question engine cannot even frame (an unknown kind asked
    for by name).  Never raised for an UNANSWERED question -- that is the
    normal state and :func:`resolve` handles it."""


# ---------------------------------------------------------------------------
# provenance tiers
# ---------------------------------------------------------------------------

FACT = "fact"
GIVEN = "given"
NOMINAL = "nominal"
BLANK = "blank"

#: the four tiers a resolved value can carry, most to least sourced
TIERS: Tuple[str, ...] = (FACT, GIVEN, NOMINAL, BLANK)

#: one line per tier, for a report a human reads
TIER_MEANING: Dict[str, str] = {
    FACT: "read back from a catalog record we hold",
    GIVEN: "you answered it",
    NOMINAL: ("nobody answered; standard practice for the class supplied it "
              "(an archetype nominal, or the constructor's documented default)"),
    BLANK: "nobody answered and nothing standard applies -- it stays empty",
}


# ---------------------------------------------------------------------------
# the pluggable source list
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Source:
    """One registry the questions are derived from.

    ``module`` is imported BY NAME at call time and never at import time, so a
    source that does not exist on this checkout costs nothing and is reported
    absent rather than crashing the engine (#674 and #692 are unmerged).
    """
    name: str
    module: str
    answers: str


SOURCES: Tuple[Source, ...] = (
    Source("catalog", "rvt.famgen.catalog",
           "which real products we hold FACTS for"),
    Source("archetypes", "rvt.famgen.archetypes",
           "what we can GENERATE at standard nominal sizes"),
    Source("standards", "rvt.famgen.standards",
           "what an engineer will SCHEDULE it by"),
    Source("taxonomy", "rvt.famgen.taxonomy",
           "which kinds exist at all"),
    Source("vendors", "rvt.famgen.vendors",
           "which vendors exist at all"),
)

_SOURCE_BY_NAME: Dict[str, Source] = {s.name: s for s in SOURCES}


def load_source(name: str) -> Optional[Any]:
    """Import one source module, or ``None`` when this checkout has no such
    module.  Only :class:`ImportError` is swallowed: a source that exists and
    is broken must not be silently reported as absent."""
    src = _SOURCE_BY_NAME.get(name)
    if src is None:
        raise InterviewError(f"no source {name!r}; known: {sorted(_SOURCE_BY_NAME)}")
    try:
        return importlib.import_module(src.module)
    except ImportError:
        return None


def _sources(names: Optional[Sequence[str]] = None) -> Dict[str, Optional[Any]]:
    """``{source name: module or None}`` for the requested subset (all by
    default) -- the one place a source is looked up."""
    wanted = tuple(names) if names is not None else tuple(s.name for s in SOURCES)
    return {n: load_source(n) for n in wanted}


def source_status(names: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """Which sources answered and which were absent, for the report."""
    mods = _sources(names)
    rows = []
    for n, m in mods.items():
        s = _SOURCE_BY_NAME[n]
        rows.append({"source": n, "module": s.module, "answers": s.answers,
                     "available": m is not None})
    present = [r["source"] for r in rows if r["available"]]
    missing = [r["source"] for r in rows if not r["available"]]
    return {
        "sources": rows,
        "available": present,
        "absent": missing,
        "note": ("questions derived from " + ", ".join(present) if present
                 else "no question source is available on this checkout")
        + (f"; absent: {', '.join(missing)} (their questions are not asked and "
           f"nothing here claims to have read them)" if missing else ""),
    }


# ---------------------------------------------------------------------------
# how decisive a question is -- the ORDER of the residue
# ---------------------------------------------------------------------------

#: rank bands, most decisive first.  Everything at or below
#: :data:`DECISIVE_MAX` changes WHICH product is built; the rest refines one.
RANK_KIND = 0        # which product is this at all
RANK_VENDOR = 10     # whose product
RANK_LINE = 20       # which of that vendor's lines / which generated product
RANK_SELECTOR = 30   # the rating that identifies the member of the line
RANK_SIZED = 40      # a dimension / rating with published standard choices
RANK_OPEN = 50       # a constructor argument with no published choice list
RANK_SCHEDULE = 60   # a standard parameter an engineer schedules it by

RANKS: Dict[int, str] = {
    RANK_KIND: "which product",
    RANK_VENDOR: "vendor",
    RANK_LINE: "product line",
    RANK_SELECTOR: "the rating that identifies the member",
    RANK_SIZED: "a dimension with standard sizes",
    RANK_OPEN: "a value the constructor takes",
    RANK_SCHEDULE: "a parameter it will be scheduled by",
}

#: above this rank a question only REFINES a product that is already decided
DECISIVE_MAX = RANK_SELECTOR


# ---------------------------------------------------------------------------
# bindings: the one declarative row per famspec kind
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Binding:
    """How one famspec kind is wired to the registries.

    This is the ONLY hand-authored per-kind data in the module, and it is
    deliberately thin: it names the constructor, the catalog category it reads,
    which constructor argument carries the vendor and which carries the line,
    and the factory's own selector map (read by attribute name, so the factory
    stays the single source of truth -- a rename degrades to "no choices
    offered", never to a wrong list).  Adding a VENDOR, a LINE or a RATING ROW
    needs no row here; a whole new KIND needs its constructor first.
    """
    kind: str                       # the famspec kind
    category: str = ""              # catalog doc['category'] it reads ('' = none)
    std_category: str = ""          # the standards table key
    vendor_arg: str = ""            # constructor kwarg carrying the vendor
    line_arg: str = ""              # constructor kwarg carrying the line/product
    #: factory attribute holding ``{vendor: (vendor, line)}``
    vendor_map: str = ""
    #: factory attribute holding ``{(vendor, line_alias): (vendor, line)}``
    pair_map: str = ""
    #: factory attribute holding ``{selector: (vendor, line)}`` -- a product
    #: selector that stands in for the line (a luminaire's ``kind``)
    line_map: str = ""
    #: factory attribute holding the selector keys when the map is not a
    #: ``(vendor, line)`` mapping (a device's ``DEVICE_KINDS``)
    line_keys: str = ""


BINDINGS: Tuple[Binding, ...] = (
    Binding("transformer", category="transformer",
            std_category="electrical_equipment",
            vendor_arg="vendor", vendor_map="_XFMR_LINES"),
    Binding("panelboard", category="panelboard",
            std_category="electrical_equipment",
            vendor_arg="vendor", line_arg="line", pair_map="_PANEL_LINES"),
    Binding("luminaire", category="luminaire",
            std_category="lighting_fixture",
            line_arg="kind", line_map="_LUM_KINDS"),
    Binding("device", category="device",
            std_category="electrical_fixture",
            line_arg="kind", line_keys="DEVICE_KINDS"),
)

_BINDING_BY_KIND: Dict[str, Binding] = {b.kind: b for b in BINDINGS}

#: constructor keyword arguments that are PLUMBING, not questions for a user
_NOT_A_QUESTION: Tuple[str, ...] = (
    "start_id", "name", "solid", "types", "shared_params", "standards",
    "standard_values", "identity", "text_params", "base_z_ft", "parts",
    "category", "prompt", "dimensions", "product",
)

#: catalog ratings keys that publish an OPTION LIST for a constructor argument.
#: The only key->key aliasing in the module; a per-variant scalar key needs no
#: row (a question key equal to a ratings key finds its own values).
_CHOICE_LISTS: Dict[str, Tuple[str, ...]] = {
    "mains_a": ("mains_ratings_available_a", "mains_ratings_a"),
    "spaces": ("branch_pole_space_options",),
}


# ---------------------------------------------------------------------------
# one offered answer
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Choice:
    """One answer the engine can actually deliver.

    ``note`` says what picking it gets you (the catalog model it selects, the
    record it comes from).  A choice is only ever constructed after
    :func:`_deliverable` has probed it -- an undeliverable value is left OFF the
    list rather than offered and refused later.
    """
    value: Any
    label: str = ""
    note: str = ""
    source: str = ""                       # 'catalog' / 'archetypes' / ...

    def to_json(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"value": self.value, "label": self.label or str(self.value)}
        if self.note:
            d["note"] = self.note
        if self.source:
            d["source"] = self.source
        return d


@dataclass(frozen=True)
class Question:
    """One thing the prompt did not settle.

    ``choices`` are the only values the engine can deliver for this key (empty
    = an open value); ``default`` / ``default_tier`` are what happens if it is
    never answered -- which is always allowed (hard rule 1); ``affects`` says
    what the answer will change, in the words of the registry it came from.
    """
    key: str
    ask: str
    rank: int
    source: str                             # which registry produced it
    #: the CONSTRUCTOR keyword this key binds to, when the famspec spells it
    #: differently.  A luminaire's product selector is ``make_luminaire``'s
    #: ``kind`` argument but the famspec's ``fixture`` field (``kind`` there
    #: selects the constructor) -- ``key`` is always the famspec's spelling, so
    #: an answer never has to be renamed by the caller.
    arg: str = ""
    affects: str = ""
    choices: Tuple[Choice, ...] = ()
    #: values a source names that the engine cannot deliver WITH THE ANSWERS SO
    #: FAR, each with the constructor's own refusal.  They are not offered (a
    #: choice the engine would refuse is the bug this module is built against)
    #: and not hidden either: answering something else can bring them back, and
    #: the report says which they were and why.
    withheld: Tuple[Dict[str, Any], ...] = ()
    open: bool = True                       # a value off the list is accepted
    unit: str = ""
    default: Any = None
    default_tier: str = NOMINAL
    default_basis: str = ""
    #: where an ANSWER is written in the famspec: '' = the constructor kwarg of
    #: the same name, 'standard_values' = the schedule-parameter map
    slot: str = ""
    #: the parameter name an answer fills, when the answer goes to ``slot``
    param: str = ""
    #: words a prompt uses for this key (drives the prompt reader; derived)
    words: Tuple[str, ...] = ()

    @property
    def decisive(self) -> bool:
        """True when the answer changes WHICH product is built."""
        return self.rank <= DECISIVE_MAX

    @property
    def prunes(self) -> int:
        """How many deliverable outcomes answering this eliminates."""
        return max(0, len(self.choices) - 1)

    @property
    def kwarg(self) -> str:
        """The constructor keyword this question's answer is passed as."""
        return self.arg or self.key

    def to_json(self) -> Dict[str, Any]:
        return {
            "key": self.key, "ask": self.ask, "rank": self.rank,
            "rank_meaning": RANKS.get(self.rank, ""),
            "decisive": self.decisive, "source": self.source,
            "affects": self.affects,
            "choices": [c.to_json() for c in self.choices],
            "withheld": [dict(w) for w in self.withheld],
            "open": self.open, "unit": self.unit,
            "default": self.default, "default_tier": self.default_tier,
            "default_basis": self.default_basis,
            "prunes": self.prunes,
        }


@dataclass(frozen=True)
class Answered:
    """One resolved value and the tier it carries into the famspec."""
    key: str
    value: Any
    tier: str
    source: str = ""
    basis: str = ""
    #: the prompt words this was read from, quoted back verbatim
    quoted: str = ""
    slot: str = ""
    param: str = ""

    def to_json(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"key": self.key, "value": self.value,
                             "tier": self.tier, "meaning": TIER_MEANING[self.tier]}
        for k, v in (("source", self.source), ("basis", self.basis),
                     ("from_prompt", self.quoted), ("parameter", self.param)):
            if v:
                d[k] = v
        return d


# ---------------------------------------------------------------------------
# reading the registries
# ---------------------------------------------------------------------------

def _factory():
    from . import factory as F                      # noqa: WPS433  (lazy)
    return F


def _famspec():
    from ..frontdoor import famspec as FS           # noqa: WPS433  (lazy)
    return FS


def _fmap(name: str) -> Dict[Any, Any]:
    """A selector map read off the factory BY NAME.  Absent -> ``{}``: the
    question loses its choices and becomes open, which is honest, rather than
    the module carrying a second copy that can drift."""
    if not name:
        return {}
    m = getattr(_factory(), name, None)
    return dict(m) if isinstance(m, Mapping) else {}


def _catalog_lines(cat, category: str) -> List[Tuple[str, str, Dict[str, Any]]]:
    """Every ``(vendor, line, doc)`` in the facts store for one category."""
    if cat is None or not category:
        return []
    out = []
    for v, l in cat.list_lines():
        doc = cat.load_line(v, l)
        if str(doc.get("category") or "").lower() == category.lower():
            out.append((v, l, doc))
    return out


def _variant_dims_sourced(cat, variant: Dict[str, Any]) -> bool:
    """True when the record publishes the envelope the constructors need.

    The generic rule that keeps an unbuildable row off every choice list:
    ``dims_in.w/h/d`` present and not null.  ``'VARIABLE'`` is a published
    value (a panelboard height chosen from ``h_options``), not a hole.
    """
    dims = variant.get("dims_in") or {}
    return all(dims.get(a) is not None for a in ("w", "h", "d"))


def _signature_defaults(fn: Any) -> Dict[str, Any]:
    """``{parameter: default}`` for every keyword parameter of a constructor,
    ``_MISSING`` for one with no default."""
    out: Dict[str, Any] = {}
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):                  # pragma: no cover
        return out
    for name, p in sig.parameters.items():
        if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        out[name] = _MISSING if p.default is p.empty else p.default
    return out


_MISSING = object()


def _constructor(kind: str) -> Optional[Callable[..., Any]]:
    return getattr(_factory(), f"make_{kind}", None)


def _resolver(kind: str) -> Optional[Callable[..., Any]]:
    return getattr(_factory(), f"resolve_{kind}_facts", None)


# ---------------------------------------------------------------------------
# deliverability: probe before you offer
# ---------------------------------------------------------------------------

def _selector_field(kind: str) -> str:
    """The FAMSPEC field name for a kind whose product selector is the
    constructor's own ``kind`` argument (``fixture`` for a luminaire,
    ``device`` for a device).  Read off ``famspec.OWN_KIND_FIELD`` so the two
    modules cannot drift; ``''`` when the kind has no such rename."""
    return str(getattr(_famspec(), "OWN_KIND_FIELD", {}).get(kind, "") or "")


def _to_kwargs(kind: str, values: Mapping[str, Any]) -> Dict[str, Any]:
    """Answers keyed the FAMSPEC way -> the constructor's own keywords.

    Standard-parameter answers (``std:<name>``) are not constructor arguments
    and are dropped here; they travel in ``standard_values``.
    """
    own = _selector_field(kind)
    b = _BINDING_BY_KIND.get(kind)
    out: Dict[str, Any] = {}
    for k, v in values.items():
        if str(k).startswith("std:"):
            continue
        if own and k == own and b is not None and b.line_arg:
            out[b.line_arg] = v
        else:
            out[k] = v
    return out


def _probe_kwargs(kind: str, answers: Mapping[str, Any]) -> Dict[str, Any]:
    """The keyword arguments a facts probe for ``kind`` is called with: the
    constructor's own defaults, overridden by the answers, filtered to what the
    resolver actually accepts."""
    ctor, res = _constructor(kind), _resolver(kind)
    if res is None:
        return {}
    base = {k: v for k, v in _signature_defaults(ctor).items()
            if v is not _MISSING} if ctor is not None else {}
    base.update({k: v for k, v in _to_kwargs(kind, answers).items() if v is not None})
    accepted = _signature_defaults(res)
    return {k: v for k, v in base.items() if k in accepted}


def _deliverable(kind: str, answers: Mapping[str, Any]) -> Optional[str]:
    """``None`` when the engine can build ``kind`` with these answers, else the
    reason it cannot -- the constructor's own refusal, quoted.

    The probe runs the kind's FACTS RESOLVER, which is where every honest
    refusal lives (an unsourced dimension, a rating outside the line, a vendor
    with no record).  It authors no geometry, so a choice list costs
    milliseconds.  A resolver we cannot call in this shape returns ``None``:
    the engine does not get to claim a value is undeliverable on the strength
    of its own bad call.
    """
    res = _resolver(kind)
    if res is None:
        return None
    F = _factory()
    from . import catalog as C
    try:
        res(**_probe_kwargs(kind, answers))
        return None
    except (F.FactoryError, C.CatalogError) as e:
        return str(e)
    except TypeError:
        return None
    except Exception:                                # pragma: no cover
        return None


# ---------------------------------------------------------------------------
# the kinds this engine can actually interview for
# ---------------------------------------------------------------------------

def _archetype_keys(arch) -> Tuple[str, ...]:
    if arch is None:
        return ()
    fn = getattr(arch, "keys", None)
    try:
        return tuple(fn()) if callable(fn) else ()
    except Exception:                                # pragma: no cover
        return ()


def kinds(sources: Optional[Sequence[str]] = None) -> Tuple[str, ...]:
    """Every kind this engine has a question set for, derived.

    A kind qualifies when (1) a source names it and (2) the engine can build it
    from ZERO answers -- because a question set whose end state is a refusal is
    not a question set (hard rule 1).  ``generic_model`` is the standing example
    of the second half: it is a real famspec kind whose geometry the caller
    supplies, so no series of questions this module can derive produces a file,
    and :func:`describe_kind` says exactly that instead of interviewing.
    """
    mods = _sources(sources)
    out: List[str] = []
    for b in BINDINGS:
        if mods.get("catalog") is None:
            continue
        if _constructor(b.kind) is None:
            continue
        if _deliverable(b.kind, {}) is None:
            out.append(b.kind)
    out.extend(_archetype_keys(mods.get("archetypes")))
    tax = mods.get("taxonomy")
    listed = getattr(tax, "kinds", None) if tax is not None else None
    if callable(listed):
        try:
            for k in listed():
                if str(k) not in out and _constructor(str(k)) is not None:
                    out.append(str(k))
        except Exception:                            # pragma: no cover
            pass
    return tuple(sorted(set(out)))


def unbuildable_categories(sources: Optional[Sequence[str]] = None) -> List[Dict[str, str]]:
    """Catalog categories we hold FACTS for but cannot build a family in.

    The honest counterpart of :func:`kinds`: the facts store can grow a
    category before the engine grows its constructor, and the interview must
    say so rather than offer to interview for it.
    """
    mods = _sources(sources)
    cat = mods.get("catalog")
    if cat is None:
        return []
    known = {b.category for b in BINDINGS if b.category}
    seen: Dict[str, List[str]] = {}
    for v, l in cat.list_lines():
        c = str(cat.load_line(v, l).get("category") or "").lower()
        if c and c not in known:
            seen.setdefault(c, []).append(f"{v}/{l}")
    return [{"category": c,
             "records": ", ".join(sorted(recs)),
             "why": (f"the facts store holds {len(recs)} record(s) in this category "
                     f"but the engine has no make_{c} constructor, so there is "
                     f"nothing a question set could end in")}
            for c, recs in sorted(seen.items())]


# ---------------------------------------------------------------------------
# deriving the questions of one kind
# ---------------------------------------------------------------------------

def _words_for(key: str, label: str) -> Tuple[str, ...]:
    """The words a prompt uses for a key -- derived from the key and its label,
    never a hand-written vocabulary."""
    out = {key.lower()}
    stem = re.sub(r"_(in|ft|mm|a|v|kva)$", "", key.lower())
    out.add(stem)
    out.add(stem.replace("_", " "))
    if label:
        out.add(label.lower())
    return tuple(sorted(w for w in out if w))


#: how a key's own tokens are spelled back to a human.  Derived case fixing for
#: the unit abbreviations the constructors use -- not a per-product vocabulary.
_SPELL: Dict[str, str] = {
    "kva": "kVA", "va": "VA", "a": "A", "v": "V", "in": "in", "ft": "ft",
    "mm": "mm", "ac": "AC", "dc": "DC", "ka": "kA", "sccr": "SCCR",
    "mcb": "MCB (main circuit breaker)", "mlo": "MLO", "cct": "CCT",
    "id": "ID", "od": "OD", "nema": "NEMA",
}


def _label(key: str) -> str:
    """A key spelled for a person: ``mains_a`` -> ``Mains A``, ``kva`` ->
    ``kVA``, ``primary_v`` -> ``Primary V``."""
    parts = [p for p in str(key).replace("-", "_").split("_") if p]
    out = []
    for i, p in enumerate(parts):
        low = p.lower()
        if low in _SPELL:
            out.append(_SPELL[low])
        elif i == 0:
            out.append(p[:1].upper() + p[1:])
        else:
            out.append(low)
    return " ".join(out).strip()


def _dedupe_choices(cs: Sequence[Choice], prefer: Any = None) -> Tuple[Choice, ...]:
    """One entry per DELIVERABLE OUTCOME.

    ``_PANEL_LINES`` maps three spellings (``pow-r-line`` / ``prl`` /
    ``pow-r-line-panelboards``) onto one catalog record, and offering all three
    asks the user to choose between three names for the same file.  Choices
    that resolve to the same record collapse to one -- the constructor's own
    default spelling when it is among them, else the shortest.
    """
    by_outcome: Dict[str, List[Choice]] = {}
    for c in cs:
        by_outcome.setdefault(c.note or str(c.value), []).append(c)
    out: List[Choice] = []
    for group in by_outcome.values():
        pick = next((g for g in group if g.value == prefer), None)
        out.append(pick or min(group, key=lambda g: (len(str(g.value)), str(g.value))))
    return tuple(sorted(out, key=lambda c: str(c.value)))


def _selected_records(cat, kind: str, b: Binding,
                      answers: Mapping[str, Any]) -> List[Tuple[str, str, Dict[str, Any]]]:
    """The catalog record(s) currently in play, given what is settled so far.

    This is what keeps a published option list attached to the record that
    published it: Square D's ``branch_pole_space_options`` must not be offered
    as the standard sizes of an Eaton panel just because both are panelboards.
    """
    lines = _catalog_lines(cat, b.category)
    if not lines:
        return []
    pair, lmap, vmap = _fmap(b.pair_map), _fmap(b.line_map), _fmap(b.vendor_map)
    field = _selector_field(kind) or b.line_arg
    sel = answers.get(field, _ctor_default(kind, b.line_arg)) if b.line_arg else None
    vendor = str(answers.get(b.vendor_arg,
                             _ctor_default(kind, b.vendor_arg)) or "").lower() \
        if b.vendor_arg else ""
    want: Optional[set] = None
    if lmap:
        rec = lmap.get(sel)
        want = {rec} if rec else None
    elif pair:
        rec = pair.get((vendor, str(sel).lower() if sel else ""))
        want = {rec} if rec else ({(v, l) for (vn, _a), (v, l) in pair.items()
                                   if vn == vendor} or None)
    elif vmap:
        rec = vmap.get(vendor)
        want = {rec} if rec else None
    if want is None:
        return lines
    return [(v, l, d) for v, l, d in lines if (v, l) in want]


def _catalog_choices(cat, kind: str, b: Binding, key: str,
                     picked: List[Tuple[str, str, Dict[str, Any]]],
                     answers: Mapping[str, Any],
                     held: Optional[List[Dict[str, Any]]] = None) -> List[Choice]:
    """The published values for ``key``, from the records currently in play.

    Two generic rules and no product knowledge: a ratings key with the same
    name as the question carries ONE value per variant (a transformer's kVA);
    a ratings key aliased in :data:`_CHOICE_LISTS` carries a published OPTION
    LIST for the argument (a panelboard's tabulated mains ratings).  Every
    candidate is probed before it is offered.
    """
    # THE PROBE, NOT A GUESS, DECIDES.  Every published value is collected and
    # then run through the kind's facts resolver; only where there is no
    # resolver to ask does the sourced-dimensions rule stand in for it.
    screen = _resolver(kind) is None
    vals: Dict[Any, List[str]] = {}
    for v, l, doc in picked:
        for variant in doc.get("variants") or []:
            if screen and not _variant_dims_sourced(cat, variant):
                continue
            r = variant.get("ratings") or {}
            if key in r and isinstance(r[key], (int, float)) and not isinstance(r[key], bool):
                vals.setdefault(float(r[key]), []).append(
                    f"{v}/{l} {variant.get('model')}")
        for alias in _CHOICE_LISTS.get(key, ()):
            for variant in doc.get("variants") or []:
                if screen and not _variant_dims_sourced(cat, variant):
                    continue
                pub = (variant.get("ratings") or {}).get(alias)
                if isinstance(pub, list) and all(
                        isinstance(x, (int, float)) and not isinstance(x, bool) for x in pub):
                    for x in pub:
                        vals.setdefault(float(x), []).append(
                            f"{v}/{l} {variant.get('model')}")
    out: List[Choice] = []
    for val in sorted(vals):
        trial = dict(answers)
        trial[key] = val
        why = _deliverable(kind, trial)
        if why is not None:
            # Eaton's 500 kVA row lives here: the catalog HAS it and publishes
            # no dimensions for it, so it is never offered as a kVA to pick.
            if held is not None:
                held.append({"value": val, "why": why})
            continue
        models = sorted(set(vals[val]))
        out.append(Choice(value=val, label=f"{val:g}",
                          note="published by " + ", ".join(models[:3]),
                          source="catalog"))
    return out


def _vendor_line_questions(cat, kind: str, b: Binding,
                           answers: Mapping[str, Any]) -> List[Question]:
    """Vendor and line, first class wherever the catalog holds more than one
    (steer #684 DONE 2).  Exactly one deliverable choice is not a question."""
    out: List[Question] = []
    lines = _catalog_lines(cat, b.category)
    if b.vendor_arg:
        if b.pair_map:
            vendors = sorted({v for v, _l in _fmap(b.pair_map)})
        else:
            vendors = sorted(_fmap(b.vendor_map)) or sorted({v for v, _l, _d in lines})
        cs: List[Choice] = []
        held: List[Dict[str, Any]] = []
        pair0 = _fmap(b.pair_map)
        field0 = _selector_field(kind) or b.line_arg
        for v in vendors:
            # A VENDOR IS PROBED WITH ITS OWN LINE.  Leaving the constructor's
            # default line in place probed "square-d + pow-r-line", which is
            # refused for the right reason and would have dropped Square D off
            # the vendor list entirely -- a vendor we do hold facts for.
            trials = []
            if b.line_arg and pair0:
                for ln in sorted({l for vn, l in pair0 if vn == v}):
                    t = dict(answers)
                    t[b.vendor_arg], t[field0] = v, ln
                    trials.append(t)
            if not trials:
                t = dict(answers)
                t[b.vendor_arg] = v
                if b.line_arg:
                    t.pop(field0, None)
                trials.append(t)
            why = [_deliverable(kind, t) for t in trials]
            if all(w is not None for w in why):
                held.append({"value": v, "why": str(why[0])})
                continue
            recs = sorted({f"{cv}/{cl}" for cv, cl, _d in lines if cv == v}) or [v]
            cs.append(Choice(value=v, label=v,
                             note="facts from " + ", ".join(recs), source="catalog"))
        cs = list(_dedupe_choices(cs, prefer=_ctor_default(kind, b.vendor_arg)))
        listed = ", ".join(c.label for c in cs)
        out.append(Question(
            key=b.vendor_arg,
            ask=(f"Whose {_label(kind)}? The catalog holds facts for {listed}."
                 if cs else f"Whose {_label(kind)}?"),
            rank=RANK_VENDOR, source="catalog",
            affects="which catalog record answers every dimension and rating",
            choices=tuple(cs), withheld=tuple(held), open=False,
            default=_ctor_default(kind, b.vendor_arg),
            default_basis="the constructor's documented default vendor",
            words=_words_for(b.vendor_arg, "manufacturer")))
    if b.line_arg:
        cs, held = [], []
        vendor = str(answers.get(b.vendor_arg)
                     or _ctor_default(kind, b.vendor_arg) or "").lower()
        pair, lmap = _fmap(b.pair_map), _fmap(b.line_map)
        if pair:
            names = sorted({ln for vn, ln in pair if vn == vendor})
        elif lmap:
            names = sorted(lmap)
        else:
            names = sorted(_fmap(b.line_keys))
        field = _selector_field(kind) or b.line_arg
        for n in names:
            trial = dict(answers)
            trial[field] = n
            why = _deliverable(kind, trial)
            if why is not None:
                held.append({"value": n, "why": why})
                continue
            rec = lmap.get(n) if lmap else pair.get((vendor, n))
            cs.append(Choice(value=n, label=n,
                             note=("facts from " + "/".join(rec)) if rec else "",
                             source="catalog"))
        cs = list(_dedupe_choices(cs, prefer=_ctor_default(kind, b.line_arg)))
        listed = ", ".join(c.label for c in cs)
        out.append(Question(
            key=field, arg=b.line_arg,
            ask=(f"Which {_label(kind)}? {listed}." if cs
                 else f"Which {_label(kind)}?"),
            rank=RANK_LINE, source="catalog",
            affects="which catalog record answers every dimension and rating",
            choices=tuple(cs), withheld=tuple(held), open=False,
            default=_ctor_default(kind, b.line_arg),
            default_basis="the constructor's documented default line",
            words=_words_for(field, "line")))
    return out


def _ctor_default(kind: str, key: str) -> Any:
    ctor = _constructor(kind)
    if ctor is None:
        return None
    d = _signature_defaults(ctor).get(key, _MISSING)
    return None if d is _MISSING else d


def _standards_questions(std, category: str, taken: Sequence[str]) -> List[Question]:
    """One question per standard parameter of the category that no constructor
    argument already fills -- what an engineer will SCHEDULE it by (#601).

    They rank LAST and default to BLANK: an unanswered standard parameter is
    authored empty, which is the honest state of a fact nobody supplied.
    """
    if std is None or not category:
        return []
    try:
        rows = std.authored_params(category)
        keyer = getattr(std, "meaning_key", lambda x: str(x).lower())
    except Exception:                                # pragma: no cover
        return []
    used = {keyer(t) for t in taken}
    out: List[Question] = []
    for p in rows:
        if keyer(p.name) in used:
            continue
        out.append(Question(
            key="std:" + p.name,
            ask=f"{p.name}?",
            rank=RANK_SCHEDULE, source="standards",
            affects=(f"the '{p.name}' family parameter ({p.spec}, "
                     f"{p.group} group) -- blank unless you fill it"),
            choices=(), open=True,
            default=None, default_tier=BLANK,
            default_basis=("an unanswered standard parameter is authored blank; "
                           "an invented value would be a lie"),
            slot="standard_values", param=p.name,
            words=_words_for(p.name.lower().replace(" ", "_"), p.name)))
    return out


def _catalog_kind_questions(mods: Dict[str, Optional[Any]], kind: str,
                            answers: Mapping[str, Any]) -> List[Question]:
    """The question set of a catalog-backed kind: vendor, line, then every
    constructor argument that is a real choice for a user."""
    cat, std = mods.get("catalog"), mods.get("standards")
    b = _BINDING_BY_KIND[kind]
    qs: List[Question] = _vendor_line_questions(cat, kind, b, answers)
    picked = _selected_records(cat, kind, b, answers) if cat is not None else []
    ctor = _constructor(kind)
    defaults = _signature_defaults(ctor) if ctor is not None else {}
    for key, dflt in defaults.items():
        if key in _NOT_A_QUESTION or key in (b.vendor_arg, b.line_arg):
            continue
        default = None if dflt is _MISSING else dflt
        held: List[Dict[str, Any]] = []
        cs = (_catalog_choices(cat, kind, b, key, picked, answers, held)
              if cat is not None else [])
        if not cs and isinstance(default, bool):
            cs = [Choice(True, "yes"), Choice(False, "no")]
        rank = (RANK_SELECTOR if cs and any(c.source == "catalog" for c in cs)
                and key not in _CHOICE_LISTS else RANK_SIZED if cs else RANK_OPEN)
        qs.append(Question(
            key=key,
            ask=(f"{_label(key)}?"
                 + (" Published: " + ", ".join(c.label for c in cs) + "." if cs else "")),
            rank=rank, source="catalog" if cs else "constructor",
            affects=_affects_for(std, b.std_category, key),
            choices=tuple(cs), withheld=tuple(held),
            open=not isinstance(default, bool),
            default=default,
            default_tier=NOMINAL if default is not None else BLANK,
            default_basis=(f"the constructor's documented default ({default!r})"
                           if default is not None else
                           "no standard value applies; it stays blank"),
            words=_words_for(key, _label(key))))
    taken = [q.key for q in qs] + [b.vendor_arg, b.line_arg]
    qs.extend(_standards_questions(std, b.std_category, taken))
    return qs


def _affects_for(std, category: str, key: str) -> str:
    """What answering ``key`` will affect, named in the standards table's own
    words when the two line up by MEANING -- the link back to source 3."""
    if std is not None and category:
        try:
            keyer = getattr(std, "meaning_key", None)
            if callable(keyer):
                rows = list(std.authored_params(category))
                want = keyer(key.replace("_", " "))
                hit = next((p for p in rows if keyer(p.name) == want), None)
                if hit is None:
                    # a constructor argument is often one WORD of the parameter
                    # the table spells out ('kva' -> 'kVA Rating').  Match on a
                    # whole word only: a substring match made 'va' claim every
                    # parameter with those letters in it.
                    hits = [p for p in rows
                            if want in {keyer(w) for w in str(p.name).split()}]
                    hit = min(hits, key=lambda p: len(p.name)) if hits else None
                if hit is not None:
                    return (f"the '{hit.name}' family parameter ({hit.spec}, "
                            f"{hit.group} group) and the geometry that follows it")
        except Exception:                            # pragma: no cover
            pass
    return f"the constructor's {key} argument"


def _archetype_questions(mods: Dict[str, Optional[Any]], product: str,
                         answers: Mapping[str, Any]) -> List[Question]:
    """The question set of a GENERATED product: one question per archetype
    parameter, its nominal as the default, its standard sizes as the choices."""
    arch, std = mods.get("archetypes"), mods.get("standards")
    a = arch.archetype(product)
    qs: List[Question] = []
    for p in a.params:
        cs = tuple(Choice(float(c), f"{float(c):g}", source="archetypes")
                   for c in (getattr(p, "choices", ()) or ()))
        qs.append(Question(
            key=p.key,
            ask=(f"{p.label}?" + (f" Standard sizes: "
                                  + ", ".join(c.label for c in cs)
                                  + f" {p.unit}." if cs else "")),
            rank=(RANK_SELECTOR if getattr(p, "primary", False)
                  else RANK_SIZED if cs else RANK_OPEN),
            source="archetypes",
            affects=(getattr(p, "basis", "") or f"the {p.label} of the generated part"),
            choices=cs, open=True, unit=getattr(p, "unit", ""),
            default=p.default, default_tier=NOMINAL,
            default_basis=getattr(p, "basis", "") or "standard practice for the class",
            slot="dimensions",
            words=tuple(sorted(set(_words_for(p.key, p.label))
                               | {str(w).lower() for w in (getattr(p, "aliases", ()) or ())}))))
    qs.extend(_standards_questions(std, getattr(a, "category", ""),
                                   [q.key for q in qs]))
    return qs


# ---------------------------------------------------------------------------
# reading what the prompt already settled
# ---------------------------------------------------------------------------

#: a number the caller wrote AS a number.  The lookbehind is load-bearing: the
#: digits inside a token are not a measurement, or "an IP65 box" reads as 65.
_NUM = (r"(?<![A-Za-z0-9.,/-])(?<!\d )"
        r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)")

#: unit words per key suffix -- derived from the key's own name, not a table of
#: products.  A key with no recognised unit is never read out of a prompt as a
#: bare number; it stays a question, which is the honest failure direction.
_UNIT_RE: Tuple[Tuple[str, str], ...] = (
    ("kva", r"k\s*v\s*a\b"),
    ("_a", r"a(?:mps?|mperes?)?\b"),
    ("_in", r"(?:in\b|in\.|inch(?:es)?\b|\")"),
    ("_ft", r"(?:ft\b|ft\.|foot\b|feet\b|')"),
    ("_v", r"v(?:olts?)?\b"),
    ("spaces", r"(?:space|circuit|pole|ckt|way)s?\b"),
    ("va", r"v\s*a\b"),
)


def _unit_pattern(key: str) -> Optional[str]:
    k = key.lower()
    for suffix, pat in _UNIT_RE:
        if k == suffix.strip("_") or k.endswith(suffix):
            return pat
    return None


#: what may sit between a number, its unit and the word it qualifies.  English
#: hyphenates these -- "a 24-inch-wide tray" -- and a bare ``\s*`` dropped every
#: one of them.
_SEP = r"[\s-]*"

#: how far either side of a measurement its own word may sit
_ANCHOR_WINDOW = 30


def _read_prompt(prompt: str, questions: Sequence[Question]) -> Dict[str, Tuple[Any, str]]:
    """``{key: (value, quoted words)}`` for everything the prompt states.

    Both readers are driven by the question metadata rather than by a list of
    products: a CHOICE question is answered when one of its own choice labels
    appears as a word (the vendor names come from the catalog, so a new vendor
    is recognised the day its record lands), and a NUMERIC question is answered
    when a number carries the unit its key implies.

    ONE MEASUREMENT ANSWERS ONE QUESTION.  The first version of this bound
    every ``_in`` question to the same "24 inch", so a ladder tray came out 24
    in wide, 24 in deep, with 24 in rungs 24 in thick -- and the report quoted
    the caller's three words back at eight dimensions they never gave.  So a
    measurement is consumed when it is used, a number is bound to a question
    only when one of THAT question's own words sits beside it, and an
    unanchored measurement goes to the single most decisive question of its
    unit and to nothing else.  Everything left over stays a question, which is
    the honest direction to fail in.
    """
    text = " " + str(prompt or "") + " "
    out: Dict[str, Tuple[Any, str]] = {}
    for q in questions:
        for c in q.choices:
            if not isinstance(c.value, str):
                continue
            pat = (r"(?<![A-Za-z0-9])"
                   + re.escape(str(c.value)).replace(r"\-", r"[\s-]?")
                   + r"(?![A-Za-z0-9])")
            m = re.search(pat, text, re.I)
            if m:
                out[q.key] = (c.value, m.group(0).strip())
                break

    numeric = [q for q in questions
               if q.key not in out and _unit_pattern(q.key) is not None
               and isinstance(q.default, (int, float))
               and not isinstance(q.default, bool)]
    numeric.sort(key=lambda q: (q.rank, q.key))
    spans: List[Tuple[int, int]] = []

    def _free(span: Tuple[int, int]) -> bool:
        return all(span[1] <= a or span[0] >= b for a, b in spans)

    def _take(q: Question, anchored: bool) -> bool:
        for m in re.finditer(_NUM + _SEP + str(_unit_pattern(q.key)), text, re.I):
            if not _free(m.span()):
                continue
            if anchored:
                lo = max(0, m.start() - _ANCHOR_WINDOW)
                hi = min(len(text), m.end() + _ANCHOR_WINDOW)
                window = text[lo:hi].lower()
                if not any(re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", window)
                           for w in q.words if len(w) > 2):
                    continue
            try:
                out[q.key] = (float(m.group(1).replace(",", "")), m.group(0).strip())
            except ValueError:                       # pragma: no cover
                return False
            spans.append(m.span())
            return True
        return False

    for q in numeric:                                # pass 1: its own word beside it
        _take(q, anchored=True)
    claimed_units: set = set()
    for q in numeric:                                # pass 2: one bare measurement
        if q.key in out:
            claimed_units.add(_unit_pattern(q.key))
            continue
        unit = _unit_pattern(q.key)
        if unit in claimed_units:
            continue                                 # that unit is spoken for
        if _take(q, anchored=False):
            claimed_units.add(unit)
    return out


def _archetype_prompt(mods: Dict[str, Optional[Any]], kind: str, prompt: str,
                      questions: Sequence[Question]) -> Dict[str, Tuple[Any, str]]:
    """What the archetype registry's own resolver read out of the prompt.

    Empty for a catalog kind, for a checkout without the registry, or for a
    prompt it declines -- in every one of those the generic reader stands.
    """
    arch = mods.get("archetypes")
    if arch is None or not prompt or kind not in _archetype_keys(arch):
        return {}
    try:
        res = arch.resolve_prompt(str(prompt), product=kind)
    except Exception:                                # pragma: no cover
        return {}
    if res is None:
        return {}
    keys = {q.key for q in questions}
    out: Dict[str, Tuple[Any, str]] = {}
    for k, prov in (getattr(res, "provenance", None) or {}).items():
        if prov != GIVEN or k not in keys:
            continue
        out[k] = (res.values[k], str((getattr(res, "quoted", None) or {}).get(k, "")))
    return out


def _read_kind(prompt: str, available: Sequence[str],
               mods: Dict[str, Optional[Any]]) -> Optional[str]:
    """Which kind the prompt names, from vocabulary the registries supply."""
    text = " " + str(prompt or "").lower() + " "
    arch = mods.get("archetypes")
    if arch is not None:
        try:
            hit = arch.resolve_prompt(str(prompt or ""))
            if hit is not None:
                return hit.arch.key
        except Exception:                            # pragma: no cover
            pass
    best: Optional[Tuple[int, str]] = None
    for k in available:
        for word in {k, k.replace("_", " "), k.replace("_", "-")}:
            if re.search(r"(?<![a-z])" + re.escape(word) + r"s?(?![a-z])", text):
                cand = (len(word), k)
                if best is None or cand > best:
                    best = cand
    if best is not None:
        return best[1]
    # a product selector naming its own kind ("a troffer", "a duplex receptacle")
    for b in BINDINGS:
        if b.kind not in available:
            continue
        for sel in list(_fmap(b.line_map)) + list(_fmap(b.line_keys)):
            word = str(sel).replace("-", "[ -]?").replace("_", "[ _]?")
            if re.search(r"(?<![a-z])" + word + r"s?(?![a-z])", text):
                return b.kind
    return None


# ---------------------------------------------------------------------------
# the plan
# ---------------------------------------------------------------------------

@dataclass
class Plan:
    """A partially-resolved request and its ORDERED residue."""
    kind: Optional[str]
    covered: bool
    questions: Tuple[Question, ...] = ()
    answers: Dict[str, Answered] = dc_field(default_factory=dict)
    prompt: str = ""
    sources: Dict[str, Any] = dc_field(default_factory=dict)
    note: str = ""
    #: kinds this engine does have a question set for (for the honest refusal)
    available: Tuple[str, ...] = ()
    #: answers that CANNOT be honoured together, each naming what was asked,
    #: the engine's own refusal, and what was built instead.  Hard rule 1: a
    #: contradiction is a caveat after delivery, never a withheld file.
    conflicts: Tuple[Dict[str, Any], ...] = ()

    @property
    def enough(self) -> bool:
        """True when nothing DECISIVE is left -- the engine knows which product
        it is building and every further question only refines it."""
        return not any(q.decisive for q in self.questions)

    def next(self, n: int = 3) -> Tuple[Question, ...]:
        """The next few questions to ask, most decisive first (the skill flow
        asks a handful at a time, never a form)."""
        return tuple(self.questions[:max(0, int(n))])

    def question(self, key: str) -> Optional[Question]:
        return next((q for q in self.questions if q.key == key), None)

    def to_json(self) -> Dict[str, Any]:
        return {
            "kind": self.kind, "covered": self.covered, "prompt": self.prompt,
            "enough_to_build": self.enough,
            "questions": [q.to_json() for q in self.questions],
            "answered": {k: a.to_json() for k, a in sorted(self.answers.items())},
            "available_kinds": list(self.available),
            "conflicts": [dict(c) for c in self.conflicts],
            "sources": self.sources,
            "note": self.note,
        }

    def conflict_line(self) -> str:
        """The sentence a caller MUST show when answers could not be honoured
        together -- said after the file, never instead of it."""
        if not self.conflicts:
            return ""
        return " ".join(
            f"You asked for {c['key']}={c['asked']!r}; "
            f"{c['why']} Built with {c['key']}={c['used']!r} instead."
            for c in self.conflicts)

    def say(self) -> str:
        """The plan in one paragraph, for a session to read out."""
        if not self.covered:
            return self.note
        lead = (self.conflict_line() + " ") if self.conflicts else ""
        if not self.questions:
            return lead + (f"Nothing left to ask about this {self.kind}: the "
                           f"prompt settled it. Building.")
        if lead:
            return lead + self._open_line()
        return self._open_line()

    def _open_line(self) -> str:
        if not self.questions:
            return (f"Nothing left to ask about this {self.kind}: the prompt "
                    f"settled it. Building.")
        head = "; ".join(q.ask for q in self.next(3))
        tail = ("" if self.enough else
                " (these change which product gets built)")
        return (f"{len(self.questions)} thing(s) the prompt leaves open for this "
                f"{self.kind}{tail}. Next: {head} "
                f"You can stop any time -- whatever you leave, I build with the "
                f"assumed answers named.")


def _kind_question(available: Sequence[str], mods: Dict[str, Optional[Any]]) -> Question:
    cs = tuple(Choice(k, k.replace("_", " "), source="engine") for k in available)
    return Question(
        key="kind",
        ask="What are we building? " + ", ".join(c.label for c in cs) + ".",
        rank=RANK_KIND, source="engine",
        affects="which constructor and which registries answer everything else",
        choices=cs, open=False, default=None, default_tier=BLANK,
        default_basis="no product can be assumed from no words at all",
        words=("kind", "product"))


def plan(prompt: str = "", kind: Optional[str] = None,
         answers: Optional[Mapping[str, Any]] = None,
         sources: Optional[Sequence[str]] = None) -> Plan:
    """The ordered residue of a request: what the prompt and the answers so far
    still leave undetermined, most decisive first.

    ``prompt`` is read FIRST (steers #685 / #687: the prompt is the interface),
    then ``answers`` override it.  A prompt descriptive enough to settle
    everything comes back with no questions at all.  A kind the engine has no
    question set for comes back ``covered=False`` with a plain sentence -- it
    does not pretend to interview.
    """
    mods = _sources(sources)
    status = source_status(sources)
    available = kinds(sources)
    given: Dict[str, Any] = {str(k): v for k, v in (answers or {}).items()
                             if v is not None}

    chosen = str(kind).strip().lower().replace(" ", "_").replace("-", "_") if kind else None
    if chosen is None:
        chosen = str(given.pop("kind", "") or "").strip().lower() or None
    if chosen is None:
        chosen = _read_kind(prompt, available, mods)
    if chosen is None:
        q = _kind_question(available, mods)
        pre = _read_prompt(prompt, [q])
        if "kind" in pre:
            chosen = str(pre["kind"][0])
        else:
            return Plan(kind=None, covered=bool(available), questions=(q,),
                        prompt=str(prompt or ""), sources=status,
                        available=available,
                        note=("Nothing in the prompt names a product this engine "
                              "builds. It can build: "
                              + (", ".join(available) or "(nothing -- no source "
                                 "is available on this checkout)") + "."))

    if chosen not in available:
        return Plan(kind=chosen, covered=False, questions=(),
                    prompt=str(prompt or ""), sources=status, available=available,
                    note=_no_question_set_note(chosen, available, mods))

    qs = _questions_for(mods, chosen, given)
    # THE PROMPT SPEAKS BEFORE ANY QUESTION IS ASKED (steers #685 / #687).
    # An archetype reads its own prompt: `archetypes.resolve_prompt` already
    # knows that a tray's bare "24 inch" is its WIDTH and that "6-in-deep"
    # is its loading depth, and duplicating that reader here would be a second
    # thing to get wrong.
    pre = _archetype_prompt(mods, chosen, prompt, qs)
    pre.update(_read_prompt(prompt, [q for q in qs if q.key not in pre]))
    resolved: Dict[str, Answered] = {}
    for q in qs:
        if q.key in given:
            resolved[q.key] = Answered(q.key, given[q.key], GIVEN,
                                       source="answer", basis="you answered it",
                                       slot=q.slot, param=q.param)
        elif q.key in pre:
            val, quoted = pre[q.key]
            resolved[q.key] = Answered(q.key, val, GIVEN, source="prompt",
                                       basis="the prompt said so", quoted=quoted,
                                       slot=q.slot, param=q.param)
        elif len(q.choices) == 1 and not q.open:
            # NOT A QUESTION: one deliverable value is a fact of the engine, not
            # a decision for the user.  What was held back is still named.
            only = q.choices[0]
            extra = ("; not deliverable with the answers so far: "
                     + ", ".join(f"{w['value']} ({w['why']})" for w in q.withheld[:3])
                     ) if q.withheld else ""
            resolved[q.key] = Answered(
                q.key, only.value,
                FACT if only.source == "catalog" else NOMINAL,
                source=only.source,
                basis=("the only value this engine can deliver -- "
                       + (only.note or "no other is offered") + extra),
                slot=q.slot, param=q.param)
    # RE-DERIVE with what we now know: the vendor decides which lines exist and
    # which rating rows are published, so a settled vendor must not leave the
    # other lines' choices on the list (offering a choice the engine cannot
    # then deliver is the failure this whole module is built against).
    steering = {q.key for q in qs if q.rank in (RANK_VENDOR, RANK_LINE)}
    if steering & set(resolved):
        merged = {k: a.value for k, a in resolved.items()}
        qs = _questions_for(mods, chosen, merged)
        # An answer survives if the ENGINE can still deliver it, not if it is on
        # the (deduplicated) offer list -- 'prl' is a real spelling of the Eaton
        # line even though only 'pow-r-line' is offered.
        for key in [k for k, a in resolved.items()
                    if a.tier == GIVEN and not str(k).startswith("std:")]:
            if _deliverable(chosen, {key: resolved[key].value}) is not None:
                del resolved[key]

    qs, resolved, conflicts = _settle_conflicts(mods, chosen, qs, resolved)

    residue = tuple(sorted((q for q in qs if q.key not in resolved),
                           key=lambda q: (q.rank, -q.prunes, q.key)))
    p = Plan(kind=chosen, covered=True, questions=residue, answers=resolved,
             prompt=str(prompt or ""), sources=status, available=available,
             conflicts=tuple(conflicts))
    p.note = status["note"]
    return p


def _nearest(q: Optional[Question], asked: Any) -> Any:
    """The closest value this engine can actually deliver to what was asked.

    Numeric choices pick the nearest published value (a caller who asked HPS
    for 225 kVA gets the nearest rating HPS publishes, said out loud); anything
    else falls to the question's own default.
    """
    if q is None:
        return None
    nums = [c.value for c in q.choices
            if isinstance(c.value, (int, float)) and not isinstance(c.value, bool)]
    if nums and isinstance(asked, (int, float)) and not isinstance(asked, bool):
        return min(nums, key=lambda x: (abs(float(x) - float(asked)), float(x)))
    if q.choices:
        return q.choices[0].value
    return q.default


def _settle_conflicts(mods: Dict[str, Optional[Any]], kind: str,
                      qs: List[Question], resolved: Dict[str, Answered]):
    """Make a contradictory answer set BUILDABLE, loudly.

    Answers can be individually deliverable and jointly impossible: HPS
    publishes 30 and 75 kVA, so ``vendor=hps`` and ``kva=225`` are each fine
    and together are a refusal.  Hard rule 1 forbids answering that with an
    exception, so the LEAST decisive answer yields -- the vendor identifies the
    product, the rating refines it -- and what was asked, why it could not be
    honoured and what was built instead are all carried on the plan.
    """
    conflicts: List[Dict[str, Any]] = []
    for _ in range(len(resolved) + 1):
        why = _deliverable(kind, {k: a.value for k, a in resolved.items()})
        if why is None:
            break
        ranks = {q.key: q.rank for q in qs}
        cands = sorted((k for k, a in resolved.items()
                        if a.tier == GIVEN and not str(k).startswith("std:")),
                       key=lambda k: (-ranks.get(k, RANK_OPEN), k))
        if not cands:
            break                                    # nothing given to give up
        drop = cands[0]
        asked = resolved.pop(drop).value
        qs = _questions_for(mods, kind, {k: a.value for k, a in resolved.items()})
        q = next((x for x in qs if x.key == drop), None)
        used = _nearest(q, asked)
        conflicts.append({"key": drop, "asked": asked, "why": why, "used": used})
        if used is not None:
            resolved[drop] = Answered(
                drop, used, NOMINAL, source=(q.source if q else "engine"),
                basis=(f"you asked for {asked!r}, which this engine cannot deliver "
                       f"with the rest of your answers ({why}); {used!r} is the "
                       f"nearest it can"))
    return qs, resolved, conflicts


def _questions_for(mods: Dict[str, Optional[Any]], kind: str,
                   answers: Mapping[str, Any]) -> List[Question]:
    if kind in _BINDING_BY_KIND:
        return _catalog_kind_questions(mods, kind, answers)
    if kind in _archetype_keys(mods.get("archetypes")):
        return _archetype_questions(mods, kind, answers)
    return []                                        # pragma: no cover


def _no_question_set_note(kind: str, available: Sequence[str],
                          mods: Dict[str, Optional[Any]]) -> str:
    """The plain sentence a kind with no question set gets (steer #684 DONE 6).

    It says WHY, not just no: a famspec kind whose geometry the caller supplies
    has no series of questions that ends in a file, and a catalog category with
    no constructor has nothing to end in either.
    """
    FS = _famspec()
    why = ""
    if kind in getattr(FS, "KINDS", ()):
        why = (f" '{kind}' is a real famspec kind, but its geometry is supplied by "
               f"the caller (vertices / a mesh / a parts list), so no series of "
               f"questions this engine can derive would end in a file.")
    else:
        for row in unbuildable_categories():
            if row["category"] == kind:
                why = f" {row['why']} ({row['records']})."
                break
    absent = [s for s in ("archetypes", "taxonomy", "vendors") if mods.get(s) is None]
    hint = (f" Sources not available on this checkout: {', '.join(absent)} -- a "
            f"question set for it may exist once they land." if absent else "")
    return (f"There is no question set for '{kind}'.{why} This engine has questions "
            f"for: " + (", ".join(available) or "(nothing)") + "." + hint)


def answer(p: Plan, **kv: Any) -> Plan:
    """Answer some questions and get the new residue.  Unknown keys are
    refused BY NAME rather than silently dropped."""
    known = {q.key for q in p.questions} | set(p.answers)
    bad = [k for k in kv if k not in known and k != "kind"]
    if bad:
        raise InterviewError(
            f"not a question of this {p.kind or 'request'}: {', '.join(sorted(bad))}. "
            f"Open questions: " + (", ".join(q.key for q in p.questions) or "(none)"))
    merged: Dict[str, Any] = {k: a.value for k, a in p.answers.items()
                              if a.tier == GIVEN}
    merged.update({k: v for k, v in kv.items() if v is not None})
    return plan(prompt=p.prompt, kind=p.kind, answers=merged,
                sources=[r["source"] for r in p.sources.get("sources", [])] or None)


# ---------------------------------------------------------------------------
# the resolution -- always a file (hard rule 1)
# ---------------------------------------------------------------------------

@dataclass
class Resolution:
    """A famspec the router already accepts, plus what was assumed to get it."""
    kind: str
    famspec: Dict[str, Any]
    values: Dict[str, Answered] = dc_field(default_factory=dict)
    assumed: Tuple[str, ...] = ()
    remaining: Tuple[str, ...] = ()
    sources: Dict[str, Any] = dc_field(default_factory=dict)
    conflicts: Tuple[Dict[str, Any], ...] = ()
    note: str = ""

    def by_tier(self) -> Dict[str, List[str]]:
        out: Dict[str, List[str]] = {t: [] for t in TIERS}
        for k, a in self.values.items():
            out[a.tier].append(k)
        return {t: sorted(v) for t, v in out.items()}

    def to_json(self) -> Dict[str, Any]:
        return {
            "kind": self.kind, "famspec": self.famspec,
            "values": {k: a.to_json() for k, a in sorted(self.values.items())},
            "assumed_answers": list(self.assumed),
            "questions_not_asked": list(self.remaining),
            "by_tier": self.by_tier(),
            "conflicts": [dict(c) for c in self.conflicts],
            "sources": self.sources, "note": self.note,
        }

    def say(self) -> str:
        lead = ""
        if self.conflicts:
            lead = " ".join(
                f"You asked for {c['key']}={c['asked']!r}; {c['why']} "
                f"Built with {c['key']}={c['used']!r} instead." for c in self.conflicts) + " "
        if not self.assumed:
            return lead + (f"Every answer came from you or the catalog; "
                           f"building the {self.kind}.")
        return lead + (f"Building the {self.kind} now. {len(self.assumed)} answer(s) "
                f"were ASSUMED, not given: "
                + ", ".join(f"{k}={self.values[k].value!r}" for k in self.assumed[:6])
                + (f" (+{len(self.assumed) - 6} more)" if len(self.assumed) > 6 else "")
                + ". Say any of them and I rebuild with it.")


def resolve(p: Plan) -> Resolution:
    """Turn a plan at ANY stage into a famspec the router accepts.

    This is hard rule 1 in code: it never asks for anything, never raises for
    an unanswered question, and never returns something the caller cannot
    build.  Every question still open falls to its default and is named in
    :attr:`Resolution.assumed`.
    """
    if not p.covered or not p.kind:
        raise InterviewError(
            p.note or "no product is identified yet, so there is nothing to build; "
                      "name one of: " + ", ".join(p.available))
    values: Dict[str, Answered] = dict(p.answers)
    assumed: List[str] = []
    for q in p.questions:
        if q.default is None:
            continue                                 # blank stays blank
        values[q.key] = Answered(q.key, q.default, q.default_tier,
                                 source=q.source, basis=q.default_basis,
                                 slot=q.slot, param=q.param)
        assumed.append(q.key)

    spec: Dict[str, Any] = {"kind": p.kind}
    std_vals: Dict[str, Any] = {}
    dims: Dict[str, Any] = {}
    archetype_kind = p.kind not in _BINDING_BY_KIND
    if archetype_kind:
        spec = {"kind": "archetype", "product": p.kind}
    for key, a in values.items():
        if a.tier == BLANK or a.value is None:
            continue
        if a.slot == "standard_values":
            std_vals[a.param or key] = a.value
        elif a.slot == "dimensions":
            dims[key] = a.value
        else:
            spec[key] = a.value
    if std_vals:
        spec["standard_values"] = std_vals
    if dims:
        spec["dimensions"] = dims

    note = (f"{len(assumed)} answer(s) assumed rather than given; the file is "
            f"built either way (hard rule 1) and every assumption is named. "
            + p.sources.get("note", ""))
    return Resolution(kind=p.kind, famspec=spec, values=values,
                      assumed=tuple(assumed),
                      remaining=tuple(q.key for q in p.questions),
                      sources=p.sources, conflicts=p.conflicts, note=note)


# ---------------------------------------------------------------------------
# describe / audit
# ---------------------------------------------------------------------------

def describe_kind(kind: str, sources: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """The whole question set of one kind, unanswered -- a doc build, and the
    honest answer to "what will you ask me?"."""
    p = plan(kind=kind, sources=sources)
    d = p.to_json()
    if p.covered:
        d["resolution_with_no_answers"] = resolve(p).to_json()
    return d


def check_registry(sources: Optional[Sequence[str]] = None) -> List[str]:
    """Every problem in the derived question sets, one line each (empty = sound).

    (1) every covered kind resolves from ZERO answers into a famspec the
    contract accepts -- the hard-rule-1 audit; (2) no question offers a choice
    the engine cannot deliver; (3) question keys are unique per kind; (4) every
    non-blank default carries a basis.
    """
    FS = _famspec()
    probs: List[str] = []
    for k in kinds(sources):
        p = plan(kind=k, sources=sources)
        if not p.covered:
            probs.append(f"{k}: listed as covered but plan() says otherwise")
            continue
        seen = set()
        for q in p.questions:
            if q.key in seen:
                probs.append(f"{k}.{q.key}: duplicate question key")
            seen.add(q.key)
            if q.default is not None and not q.default_basis:
                probs.append(f"{k}.{q.key}: a default with no basis")
            for c in q.choices:
                if q.slot or c.source != "catalog":
                    continue
                why = _deliverable(k, {q.key: c.value})
                if why is not None:
                    probs.append(f"{k}.{q.key}: offers {c.value!r} which the "
                                 f"engine refuses: {why}")
        r = resolve(p)
        bad = FS.validate(r.famspec)
        if bad:
            probs.append(f"{k}: zero-answer famspec is not valid: {bad[:3]}")
    return probs
