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

Consumers: ``tools/rvt_job.provenance_gate`` (the front door's status gate)
hands :meth:`BaseCensus.residue_ids` to ``rvt.provenance.provenance(...,
composed_residue_ids=...)`` so a build on our base is ledgered against the
true residue instead of counting every composed element as Autodesk-derived.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, Optional

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
    raw: Dict[str, Any] = field(compare=False, repr=False, default_factory=dict)

    @property
    def ours_by_composition(self) -> int:
        return self.host_elements - len(self.residue_ids)

    def summary(self) -> Dict[str, Any]:
        it = self.raw.get("identical_to_ancestor") or {}
        cc = self.raw.get("cross_check") or {}
        out: Dict[str, Any] = {
            "base_id": self.base_id, "revit_release": self.revit_release,
            "host_elements": self.host_elements,
            "ours_by_composition": self.ours_by_composition,
            "identical_to_ancestor": len(self.residue_ids),
            "landed_but_identical": it.get("landed_but_identical"),
            "never_authored": len(self.never_authored_ids),
            "meaning": RESIDUE_MEANING,
            "source": "rvt/frontdoor/assets/genesis_census.json (tools/genesis_census.py)",
        }
        if cc.get("available") and cc.get("by_disposition"):
            out["by_disposition"] = dict(cc["by_disposition"])
        return out


_CACHE: Optional[Dict[str, BaseCensus]] = None


def load(path: str = CENSUS_PATH) -> Dict[str, BaseCensus]:
    """{sha256: BaseCensus} from the shipped asset ({} when absent)."""
    global _CACHE
    if _CACHE is not None and path == CENSUS_PATH:
        return _CACHE
    out: Dict[str, BaseCensus] = {}
    try:
        with open(path) as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        raw = {}
    for sha, b in (raw.get("bases") or {}).items():
        try:
            out[str(sha)] = BaseCensus(
                base_id=str(b.get("id")), revit_release=int(b.get("revit_release")),
                sha256=str(sha), host_elements=int(b.get("host_elements")),
                residue_ids=frozenset(int(e) for e in (b.get("identical_to_ancestor") or {}).get("ids") or []),
                never_authored_ids=frozenset(int(e) for e in b.get("never_authored_ids") or []),
                raw=dict(b))
        except (TypeError, ValueError):
            continue
    if path == CENSUS_PATH:
        _CACHE = out
    return out


def _sha256_of(path: str, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def for_file(path: Optional[str]) -> Optional[BaseCensus]:
    """The census of ``path`` iff its bytes ARE a pinned composed base."""
    if not path or not os.path.isfile(path):
        return None
    table = load()
    if not table:
        return None
    try:
        return table.get(_sha256_of(path))
    except OSError:
        return None


__all__ = ["BaseCensus", "CENSUS_PATH", "SCHEMA", "RESIDUE_MEANING", "load", "for_file"]
