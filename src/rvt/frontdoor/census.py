"""rvt.frontdoor.census -- the AUTHORSHIP CENSUS of the pinned composed
genesis bases (issue #143): which host element ids of ``G_ABPD*.rvt`` still
carry the Autodesk ancestor's bytes, and -- by complement -- which slots are
OURS BY COMPOSITION (re-authored in place by our constructors, rung by
certified rung).

Data: ``assets/genesis_census.json``, written by ``tools/genesis_census.py``
from tracked evidence only (the pinned ``.rvt`` + every certified rung
report's ``landed_slots`` / ``byte_delta``); keyed by the base's sha256 so it
applies ONLY to the exact certified bytes.  Any other base (a user's
``--base``, an Autodesk sample) has no census: the provenance ledger then
treats everything inherited from it as the sample's, as before.

The census applies TRANSITIVELY (issue #284): a file that is not a pin but
DESCENDS from one -- a prior tekton output grown on ``G_ABPD*``, now the
input of an edit -- is recognised by :func:`lineage` (a byte descent test:
>= 95 % of the pin's composed slots present and byte-identical in it) and is
then ledgered against THE PIN ITSELF with the pin's census, so its residue is
exactly the pin's residue it still carries byte-identical, residue slots any
build in the chain edited read ``ours-modified`` (still derived), and every
element the chain created is examined for lineage like a new one.  A file
with no descent (a foreign project, an Autodesk sample) has no lineage:
nothing inherited from it is presumed ours.

Consumers: ``tools/rvt_job.provenance_gate`` (the front door's status gate)
and ``tools/provenance.py --composed-base auto`` hand
:meth:`Lineage.composed_baseline` (+ :attr:`Lineage.pin_doc` for a
descendant) to ``rvt.provenance.provenance(..., composed=...)`` so a build --
or an edit of a build -- on our base is ledgered against the true residue
instead of counting every composed element as Autodesk-derived.
"""
from __future__ import annotations

import functools
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, Mapping, Optional, Tuple

from .base import sha256_of

_HERE = os.path.dirname(os.path.abspath(__file__))
CENSUS_PATH = os.path.join(_HERE, "assets", "genesis_census.json")
SCHEMA = "tekton.frontdoor.genesis-census/1"

#: what the residue IS, for manifests (one wording, every release)
RESIDUE_MEANING = ("base elements still byte-identical to the Autodesk ancestor the genesis "
                   "lineage was reduced from (issue #21 residue: content-free machinery, "
                   "coincident designation facts, and the last genuinely Autodesk-valued "
                   "settings) -- every OTHER base slot is ours by composition")


@dataclass(frozen=True)
class BaseCensus:
    """One pinned base's census."""
    base_id: str
    revit_release: int
    sha256: str
    host_elements: int
    residue_ids: FrozenSet[int]
    never_authored_ids: FrozenSet[int]
    landed_but_identical: int = 0
    by_disposition: Dict[str, int] = field(compare=False, default_factory=dict)

    @property
    def ours_by_composition(self) -> int:
        return self.host_elements - len(self.residue_ids)

    def summary(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "base_id": self.base_id, "revit_release": self.revit_release,
            "host_elements": self.host_elements,
            "ours_by_composition": self.ours_by_composition,
            "identical_to_ancestor": len(self.residue_ids),
            "landed_but_identical": self.landed_but_identical,
            "never_authored": len(self.never_authored_ids),
            "meaning": RESIDUE_MEANING,
            "source": "rvt/frontdoor/assets/genesis_census.json (tools/genesis_census.py)",
        }
        if self.by_disposition:
            out["by_disposition"] = dict(self.by_disposition)
        return out


@functools.lru_cache(maxsize=4)
def load(path: str = CENSUS_PATH) -> Mapping[str, BaseCensus]:
    """{sha256: BaseCensus} from the shipped asset ({} when absent)."""
    out: Dict[str, BaseCensus] = {}
    try:
        with open(path) as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        raw = {}
    for sha, b in (raw.get("bases") or {}).items():
        try:
            it = b.get("identical_to_ancestor") or {}
            out[str(sha)] = BaseCensus(
                base_id=str(b.get("id")), revit_release=int(b.get("revit_release")),
                sha256=str(sha), host_elements=int(b.get("host_elements")),
                residue_ids=frozenset(int(e) for e in it.get("ids") or []),
                never_authored_ids=frozenset(int(e) for e in b.get("never_authored_ids") or []),
                landed_but_identical=int(it.get("landed_but_identical") or 0),
                by_disposition=dict(((b.get("cross_check") or {}).get("by_disposition") or {})))
        except (TypeError, ValueError):
            continue
    return out


def pinned_sha256s() -> Dict[str, str]:
    """{sha256: base id} of every CERTIFIED pin in ``genesis_base.json`` --
    the registry is the authority on what is pinned; the census only adds
    the per-slot authorship of those exact bytes."""
    from .base import PIN, release_status
    out: Dict[str, str] = {}
    for year in PIN.release_years():
        st = release_status(year)
        if st["certified"] and st.get("sha256"):
            out[str(st["sha256"]).lower()] = str(st.get("id"))
    return out


def lookup(path: Optional[str]) -> Tuple[Optional[str], Optional[BaseCensus]]:
    """(pinned base id | None, census | None) for the bytes at ``path``.
    Pinned-with-census is the normal case; pinned-WITHOUT-census means the
    asset is stale (a re-pin without ``tools/genesis_census.py build``) and
    the caller must say so rather than mistake our base for a user's."""
    if not path or not os.path.isfile(path):
        return None, None
    digest = sha256_of(path).lower()
    pinned = pinned_sha256s().get(digest)
    return pinned, (load().get(digest) if pinned else None)


def for_file(path: Optional[str]) -> Optional[BaseCensus]:
    """The census of ``path`` iff its bytes ARE a pinned composed base."""
    return lookup(path)[1]


# ---------------------------------------------------------------------------
# the transitive census (issue #284): a file that DESCENDS from a pin
# ---------------------------------------------------------------------------
#: descent bar: this share of the pin's COMPOSED slots (all its slots when the
#: census is stale) must be present AND byte-identical in the file.  Our
#: builds and edits touch a handful of base slots (ProjectInfo, a level or
#: two); an Autodesk sample shares only the residue (~13 %); an older tekton
#: output grown on an earlier rung shares 64-74 % (no census vouches for the
#: rest); a foreign project shares nothing.
DESCENT_MIN_IDENTICAL = 0.95

KIND_PINNED = "pinned-composed-genesis"        #: the bytes ARE a certified pin
KIND_DESCENDS = "descends-from-pinned-genesis" #: passes the descent test against one


@dataclass(frozen=True)
class Lineage:
    """A base file IS a certified pin (``exact``) or DESCENDS from one.
    ``census`` None = the asset is stale for that pin (ledger conservatively,
    say STALE).  ``pin_doc`` = the parsed pin a descendant is ledgered
    against (None when exact: the base is the pin); ``evidence`` = the
    descent test's numbers, for manifests."""
    pinned_id: str
    census: Optional[BaseCensus]
    exact: bool
    pin_path: str
    pin_doc: Any = field(default=None, compare=False, repr=False)
    evidence: Dict[str, Any] = field(default_factory=dict, compare=False)

    @property
    def kind(self) -> str:
        return KIND_PINNED if self.exact else KIND_DESCENDS

    def composed_baseline(self):
        """The pin's census as the ledger's ``ComposedBaseline`` (None when
        stale: nothing can be split, everything inherited reads as sample)."""
        if self.census is None:
            return None
        from ..provenance import ComposedBaseline
        return ComposedBaseline(residue_ids=self.census.residue_ids, pinned_id=self.pinned_id)

    def summary(self) -> Optional[Dict[str, Any]]:
        """The manifest's ``residue`` block: :meth:`BaseCensus.summary` of the
        pin (unchanged since #143), plus -- for a descendant only -- which pin
        it descends from and the descent evidence.  None when stale."""
        if self.census is None:
            return None
        out = self.census.summary()
        if not self.exact:
            out["descends_from"] = self.pinned_id
            out["descent"] = dict(self.evidence)
        return out


def pin_file(year: Optional[int]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """(pin id, path, sha256) of the CERTIFIED pin of release ``year`` from
    the registry's own candidate locations (repo path, plugin bundle),
    sha-verified -- or Nones.  Registry-direct on purpose: a firm's
    ``$RVT_GENESIS_BASE`` names the base to BUILD on, not what our pin is."""
    from .base import PIN, release_status
    if year is None:
        return None, None, None
    st = release_status(int(year))
    slot = PIN.release_slot(int(year)) or {}
    sha = str(st.get("sha256") or "").lower()
    if not (st["certified"] and sha):
        return None, None, None
    for cand in PIN.candidate_paths(relpath=str(slot.get("relpath") or "") or None):
        if os.path.isfile(cand) and sha256_of(cand).lower() == sha:
            return str(st.get("id")), cand, sha
    return None, None, None


_PINS: Dict[str, Tuple[str, str, Any]] = {}     # sha -> (id, path, parsed Document)


def _pin_of_release(year: Optional[int]) -> Optional[Tuple[str, str, str, Any]]:
    """(id, path, sha, Document) of the certified pin for ``year``, parsed
    once per process (the pin is immutable: everything derived from it is a
    function of its sha).  None when there is no such pin here or it does
    not parse under the release context in force (never cached)."""
    pin_id, path, sha = pin_file(year)
    if not path:
        return None
    if sha not in _PINS:
        from ..mutate import Document
        try:
            _PINS[sha] = (pin_id, path, Document.from_file(path))
        except Exception:                               # noqa: BLE001
            return None
    pin_id, path, doc = _PINS[sha]
    return pin_id, path, sha, doc


def lineage(path: Optional[str], doc: Any = None, *, exact_only: bool = False) -> Optional[Lineage]:
    """The certified pin ``path`` IS or DESCENDS FROM, or None.

    Bytes first, as :func:`lookup`: an exact sha256 of a certified pin is the
    pin whatever the file is named.  Otherwise (unless ``exact_only``) the
    DESCENT TEST against the certified pin of the file's own release: of the
    pin's composed slots (census complement; every slot when the census is
    stale) at least :data:`DESCENT_MIN_IDENTICAL` must be present in the file
    with byte-identical records (``rvt.provenance.same_records``, the
    ledger's own byte law).  ``doc`` = the already-parsed
    ``rvt.mutate.Document`` of ``path`` (spares a second parse); the caller
    owns the release context (the edit route and tools/provenance.py already
    read under the file's own release).  Any failure to read is "no lineage":
    the gate falls back to the name heuristic and never over-claims."""
    if not path or not os.path.isfile(path):
        return None
    pinned, census = lookup(path)
    if pinned:
        return Lineage(pinned_id=pinned, census=census, exact=True, pin_path=os.path.abspath(path))
    if exact_only:
        return None
    try:
        from ..mutate import Document
        from ..provenance import same_records
        from ..stream_encoders import history_head_guid
        from ..versions import detect_release
        pin = _pin_of_release(detect_release(path))
        if pin is None or os.path.abspath(pin[1]) == os.path.abspath(path):
            return None
        pin_id, pin_path, pin_sha, pin_doc = pin
        base = doc if doc is not None else Document.from_file(path)
        pin_ids, base_ids = set(pin_doc.et_by_id), set(base.et_by_id)
        identical = {e for e in pin_ids & base_ids if same_records(base, pin_doc, e)}
    except Exception:                                   # noqa: BLE001
        return None
    census = load().get(pin_sha)
    probe = (pin_ids - census.residue_ids) if census is not None else pin_ids
    share = len(probe & identical) / max(1, len(probe))
    if share < DESCENT_MIN_IDENTICAL:
        return None
    hist0 = history_head_guid(path)
    evidence = {
        "min_share": DESCENT_MIN_IDENTICAL, "share": round(share, 4),
        "probed": "composed slots" if census is not None else "all pin slots (census STALE)",
        "pin_slots_probed": len(probe), "probed_identical": len(probe & identical),
        "pin_slots_edited": len((pin_ids & base_ids) - identical),
        "pin_slots_dropped": len(pin_ids - base_ids),
        # corroborating only: our commits reuse the pin's episode, but the pin
        # inherited it from its own ancestor and non-descendants carry it too
        "history_head_guid_matches_pin": hist0 is not None and hist0 == history_head_guid(pin_path),
    }
    return Lineage(pinned_id=pin_id, census=census, exact=False, pin_path=os.path.abspath(pin_path),
                   pin_doc=pin_doc, evidence=evidence)


def __getattr__(name: str):
    """``census.history_head_guid`` stays importable (it lived here until #434)
    without a bare census import loading the codec/container modules."""
    if name == "history_head_guid":
        from ..stream_encoders import history_head_guid
        return history_head_guid
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    """``dir(census)`` lists every ``__all__`` name, the lazy re-export included."""
    return sorted(set(globals()) | set(__all__))


__all__ = ["BaseCensus", "CENSUS_PATH", "SCHEMA", "RESIDUE_MEANING", "load", "lookup",
           "for_file", "pinned_sha256s", "Lineage", "lineage", "pin_file", "history_head_guid",
           "DESCENT_MIN_IDENTICAL", "KIND_PINNED", "KIND_DESCENDS"]
