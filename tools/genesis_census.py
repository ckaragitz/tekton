#!/usr/bin/env python
"""genesis_census.py — the AUTHORSHIP CENSUS of the pinned composed genesis
bases (issue #143, the front-door status gate's baseline).

Problem this data solves: ``tools/rvt_job.provenance_gate`` ledgers a build's
OUTPUT against the base it was grown from.  For a build on an Autodesk
sample project that is right: every element inherited unchanged from the base
is Autodesk's.  For a build on OUR pinned composed genesis base
(``plugin/assets/genesis/G_ABPD*.rvt``) it is wrong: the base's slots were
re-authored IN PLACE by our constructors, rung by certified rung, and only a
measured residue still carries the Autodesk ancestor's bytes.  Baselining the
output against the base then reports every one of OUR ~2,700 composed
elements as "autodesk-sample" (3,058 blockers on a prompt job today).

What this tool writes (``src/rvt/frontdoor/assets/genesis_census.json``,
mirrored into the plugin by ``tools/sync_plugin.py``): for each pinned base,
keyed by its sha256, the element ids that are STILL byte-identical to the
Autodesk ancestor the lineage was reduced from — derived ONLY from tracked
evidence, reproducible on a fresh clone:

* the base's own ElemTable ids + classes (the pinned ``.rvt`` is in-repo);
* its composition chain, walked from the compose manifest
  (``experiments/genesis/**/G_ABPD*.manifest.json``): every in-place rung's
  certified report (``landed_slots`` = slots our constructor emitted an object
  at; ``byte_delta.records_changed_ids`` / ``changed_ids`` = slots whose
  bytes then differed from the rung's parent), recursively through each
  report's ``parent`` down to the ancestor (the reduced sample ``K4``, which
  no rung report produces);
* for the 2026 base, the byte-ground-truth census
  ``experiments/genesis/subst_k4/residue_c/census.json`` (seq-102 compare vs
  K4, per id, with dispositions) — used to CROSS-CHECK the chain method and
  to annotate dispositions (machinery / coincident / genuine Autodesk values).

The byte law is the provenance instrument's own (``rvt.provenance``: an
element byte-identical to the sample IS ``autodesk-sample``), so the census
never declares anything "ours" that ``tools/provenance.py --baseline all``
would not on the owner's machine: ``identical_to_ancestor`` = base ids whose
records NO rung in the chain changed.  Slots a rung landed but re-emitted
byte-identically (content-free machinery, coincident designation facts) stay
IN that set — reported, with their recorded disposition, never argued away.

Usage::

    tools/genesis_census.py build            # (re)write the census asset
    tools/genesis_census.py check            # exit 1 if the asset is stale
    tools/genesis_census.py show             # one screen per base

Exit codes: 0 ok, 1 stale/mismatch, 2 inputs missing.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import Counter
from typing import Dict, List, Optional, Set, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.frontdoor import base as B                                   # noqa: E402
from rvt.frontdoor.census import CENSUS_PATH, SCHEMA                 # noqa: E402

EXPERIMENTS = os.path.join(ROOT, "experiments", "genesis")
#: the 2026 byte-ground-truth census (docs/inbox/genesis-12.md §1.1)
RESIDUE_C_CENSUS = os.path.join(EXPERIMENTS, "subst_k4", "residue_c", "census.json")


def _rel(p: str) -> str:
    ap = os.path.abspath(os.path.join(ROOT, p) if not os.path.isabs(p) else p)
    return os.path.relpath(ap, ROOT).replace(os.sep, "/")


def _load(p: str) -> Optional[dict]:
    try:
        with open(os.path.join(ROOT, p) if not os.path.isabs(p) else p) as fh:
            d = json.load(fh)
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) else None


# ---------------------------------------------------------------------------
# the report index: which tracked JSON produced which .rvt
# ---------------------------------------------------------------------------
class ReportIndex:
    """``out`` relpath -> report relpath over every tracked experiment JSON."""

    def __init__(self, root: str = EXPERIMENTS):
        self.by_out: Dict[str, str] = {}
        for p in sorted(glob.glob(os.path.join(root, "**", "*.json"), recursive=True)):
            d = _load(p)
            if d is None:
                continue
            out = d.get("out")
            if isinstance(out, dict):
                out = out.get("file")
            if isinstance(out, str) and out.endswith(".rvt"):
                # a compose manifest and a summary may both name one out:
                # prefer the document that carries the evidence
                key = _rel(out)
                have = self.by_out.get(key)
                if have is None or self._weight(d) > self._weight(_load(have) or {}):
                    self.by_out[key] = _rel(p)

    @staticmethod
    def _weight(d: dict) -> int:
        if d.get("op") == "compose":
            return 3
        if d.get("landed_slots"):
            return 2
        return 1 if d.get("alias_of") else 0

    def producer(self, rvt_relpath: Optional[str]) -> Optional[str]:
        return self.by_out.get(_rel(rvt_relpath)) if rvt_relpath else None


# ---------------------------------------------------------------------------
# walking one base's composition chain
# ---------------------------------------------------------------------------
class Chain:
    """Accumulates, over every certified rung report reachable from a compose
    manifest: the slots our constructors LANDED, the ids whose bytes a rung
    CHANGED, the reports read, and the ancestor file(s) the walk bottomed
    out at (no report produces them = the reduced Autodesk sample)."""

    def __init__(self, index: ReportIndex):
        self.index = index
        self.landed: Dict[int, str] = {}
        self.changed: Dict[int, str] = {}
        self.reports: List[dict] = []
        self.ancestors: List[str] = []
        self.no_byte_evidence: List[str] = []
        self._seen: Set[str] = set()

    # -- entry ---------------------------------------------------------------
    def walk_file(self, rvt_relpath: str) -> None:
        rep = self.index.producer(rvt_relpath)
        if rep is None:
            # an alias file (RB_2025.rvt) carries no 'out' but has its report
            # beside it under the same name
            beside = _rel(rvt_relpath)[:-4] + ".json"
            d = _load(beside)
            if d is not None and (d.get("alias_of") or isinstance(d.get("landed_slots"), list)):
                rep = beside
        if rep is None:
            self._ancestor(rvt_relpath)
            return
        self.walk_report(rep)

    def _ancestor(self, rvt_relpath: str) -> None:
        r = _rel(rvt_relpath)
        if r not in self.ancestors:
            self.ancestors.append(r)

    def walk_report(self, report_relpath: str) -> None:
        rp = _rel(report_relpath)
        if rp in self._seen:
            return
        self._seen.add(rp)
        d = _load(rp)
        if d is None:
            self.reports.append({"report": rp, "kind": "MISSING"})
            return
        if d.get("alias_of"):
            # md5-identical alias (Z_RA_2025 -> RA_2025 ...): the evidence is
            # the real report's, and ITS parent chain
            self.reports.append({"report": rp, "kind": "alias", "alias_of": d["alias_of"]})
            self.walk_report(os.path.join(os.path.dirname(rp), f"{d['alias_of']}.json"))
            return
        if d.get("op") == "compose":
            self._walk_compose(rp, d)
            return
        if isinstance(d.get("landed_slots"), list):
            self._walk_rung(rp, d)
            return
        # a reduction / triage report (K4 <- K3 <- R9 ...): the in-place
        # ladder starts ABOVE this file, so it is the byte ancestor -- the
        # reduced Autodesk sample every rung's byte_delta is measured from.
        # Nothing of ours lands below it; the walk stops here.
        out = d.get("out")
        out = out.get("file") if isinstance(out, dict) else out
        self.reports.append({"report": rp, "kind": str(d.get("kind") or d.get("op") or "other")[:40],
                             "ancestor": True})
        self._ancestor(str(out or rp))

    # -- node kinds ------------------------------------------------------------
    def _walk_compose(self, rp: str, d: dict) -> None:
        merge = ((d.get("phase_1_inplace") or {}).get("merge") or {})
        rungs = merge.get("rungs") or []
        base_file = (d.get("base") or {}).get("file")
        self.reports.append({"report": rp, "kind": "compose", "base": base_file,
                             "rungs": [r.get("name") for r in rungs],
                             "merged_slots": merge.get("merged_slots"),
                             "deleted": (d.get("phase_2_deletions") or {}).get("total_deleted")})
        for r in rungs:
            rf = r.get("report_file")
            if rf:
                self.walk_report(rf)
        if base_file:
            self.walk_file(base_file)

    def _walk_rung(self, rp: str, d: dict) -> None:
        name = str(d.get("rung") or os.path.basename(rp)[:-5])
        slots = {int(row["slot"]) for row in d["landed_slots"] if "slot" in row}
        bd = d.get("byte_delta") or {}
        changed_raw = bd.get("records_changed_ids", bd.get("changed_ids"))
        changed: Optional[Set[int]] = None
        if isinstance(changed_raw, list):
            changed = {int(x) for x in changed_raw}
        for s in slots:
            self.landed.setdefault(s, name)
        if changed is None:
            # no per-id byte evidence in this report: by the byte law NONE of
            # its slots may be presumed changed (conservative; recorded)
            self.no_byte_evidence.append(name)
        else:
            for s in changed:
                self.changed.setdefault(s, name)
        self.reports.append({"report": rp, "kind": "rung", "rung": name,
                             "parent": d.get("parent"), "landed": len(slots),
                             "changed": None if changed is None else len(changed),
                             "verdict": d.get("verdict")})
        if d.get("parent"):
            self.walk_file(d["parent"])


# ---------------------------------------------------------------------------
# one base
# ---------------------------------------------------------------------------
def _base_file(slot: dict) -> Optional[str]:
    for cand in B.PIN.candidate_paths(relpath=str(slot.get("relpath"))):
        if os.path.isfile(cand) and B.sha256_of(cand) == slot.get("sha256"):
            return cand
    return None


def _elemtable(path: str) -> Dict[int, str]:
    """{host element id: class name} of a project file."""
    from rvt.mutate import Document
    from rvt.versions import reading
    with reading(path):                       # 2025/2024 framing ordinals by name
        doc = Document.from_file(path)
        return {int(e): (doc.class_of(int(e)) or "?") for e in doc.et_by_id}


def census_one(year: int, slot: dict, index: ReportIndex) -> dict:
    path = _base_file(slot)
    if path is None:
        raise FileNotFoundError(f"pinned base for {year} ({slot.get('id')}) not found / sha mismatch")
    ids = _elemtable(path)
    chain = Chain(index)
    chain.walk_file(str(slot["relpath"]))
    changed = {e for e in chain.changed if e in ids}
    landed = {e for e in chain.landed if e in ids}
    identical = sorted(e for e in ids if e not in changed)
    never_authored = sorted(e for e in ids if e not in changed and e not in landed)
    by_class = Counter(ids[e] for e in identical)
    out = {
        "id": slot.get("id"), "revit_release": int(year), "sha256": slot.get("sha256"),
        "relpath": slot.get("relpath"), "host_elements": len(ids),
        "ancestor": chain.ancestors,
        "ours_by_composition": len(ids) - len(identical),
        "identical_to_ancestor": {
            "count": len(identical),
            "meaning": ("host element ids whose records NO certified rung of the composition "
                        "chain changed: their bytes are the Autodesk ancestor's serialization "
                        "(= 'autodesk-sample' under rvt.provenance's byte law). Includes slots "
                        "our constructors landed but re-emitted byte-identically (content-free "
                        "machinery / coincident designation facts) -- reported, not argued away."),
            "landed_but_identical": sum(1 for e in identical if e in landed),
            "never_authored": len(never_authored),
            "by_class": dict(by_class.most_common()),
            "ids": identical,
        },
        "never_authored_ids": never_authored,
        "chain": {
            "reports": len(chain.reports),
            "rungs": [r["rung"] for r in chain.reports if r.get("kind") == "rung"],
            "composes": [r["report"] for r in chain.reports if r.get("kind") == "compose"],
            "rungs_without_byte_evidence": chain.no_byte_evidence,
            "landed_slots": len(landed), "changed_ids": len(changed),
        },
    }
    if int(year) == 2026:
        out["cross_check"] = _cross_check_2026(identical, ids)
    return out


def _cross_check_2026(identical: List[int], ids: Dict[int, str]) -> dict:
    """The chain method vs the byte-ground-truth census of G_ABPD
    (residue_c/census.json: seq-102 payload compare against K4 per id)."""
    d = _load(RESIDUE_C_CENSUS)
    if d is None:
        return {"available": False}
    truth = {int(e["id"]): e for e in d.get("elements") or []}
    mine = set(identical)
    disp = Counter(truth[e].get("disposition") for e in mine if e in truth)
    return {
        "available": True, "source": _rel(RESIDUE_C_CENSUS),
        "truth_identical": len(truth), "chain_identical": len(mine),
        "agree": sorted(mine) == sorted(truth),
        "only_in_truth": sorted(set(truth) - mine)[:20],
        "only_in_chain": sorted(mine - set(truth))[:20],
        "by_disposition": dict(disp.most_common()),
        "dispositions": d.get("dispositions"),
    }


# ---------------------------------------------------------------------------
# the asset
# ---------------------------------------------------------------------------
def build_census() -> dict:
    index = ReportIndex()
    bases: Dict[str, dict] = {}
    for year in B.PIN.release_years():
        slot = B.PIN.release_slot(year)
        if not slot or str(slot.get("status")) != "certified" or not slot.get("sha256"):
            continue
        bases[str(slot["sha256"])] = census_one(year, slot, index)
    return {
        "schema": SCHEMA,
        "purpose": ("Per pinned composed genesis base (keyed by sha256): which host element ids "
                    "still carry the Autodesk ancestor's bytes. The front-door status gate "
                    "(tools/rvt_job.provenance_gate) uses it so a build on OUR base is ledgered "
                    "against the true residue instead of miscounting every composed element as "
                    "Autodesk-derived. Applies ONLY on an exact sha256 match; any other base is "
                    "ledgered as before (everything inherited = the sample's)."),
        "law": ("identical_to_ancestor = ids no certified rung's byte_delta changed; derived only "
                "from tracked rung reports + the pinned .rvt; regenerate with "
                "tools/genesis_census.py build after any re-pin."),
        "generated_by": "tools/genesis_census.py",
        "bases": bases,
    }


def _dumps(c: dict) -> str:
    """indent=1 JSON with the long id lists kept on ONE line each (the asset
    ships in the plugin; a line per id would triple its size for nothing)."""
    stash: Dict[str, list] = {}

    def _fold(o):
        if isinstance(o, dict):
            out = {}
            for k, v in o.items():
                if k in ("ids", "never_authored_ids") and isinstance(v, list):
                    key = f"@@IDS{len(stash)}@@"
                    stash[key] = v
                    out[k] = key
                else:
                    out[k] = _fold(v)
            return out
        if isinstance(o, list):
            return [_fold(v) for v in o]
        return o

    text = json.dumps(_fold(c), indent=1)
    for key, ids in stash.items():
        text = text.replace(f'"{key}"', json.dumps(ids, separators=(",", ":")))
    return text + "\n"


def _summary(c: dict) -> List[str]:
    lines = []
    for sha, b in (c.get("bases") or {}).items():
        it = b["identical_to_ancestor"]
        lines.append(f"{b['id']} ({b['revit_release']}, sha {sha[:12]}): {b['host_elements']:,} host elements; "
                     f"{b['ours_by_composition']:,} ours by composition; "
                     f"{it['count']:,} byte-identical to the ancestor "
                     f"({it['landed_but_identical']} landed-but-identical, {it['never_authored']} never authored)")
        lines.append(f"   ancestor: {', '.join(b['ancestor']) or '?'}; rungs: {len(b['chain']['rungs'])}; "
                     f"no byte evidence: {b['chain']['rungs_without_byte_evidence'] or 'none'}")
        top = list(it["by_class"].items())[:8]
        lines.append("   top identical classes: " + ", ".join(f"{k} {v}" for k, v in top))
        cc = b.get("cross_check")
        if cc and cc.get("available"):
            lines.append(f"   cross-check vs {cc['source']}: agree={cc['agree']} "
                         f"(truth {cc['truth_identical']} / chain {cc['chain_identical']}); "
                         f"dispositions {cc['by_disposition']}")
    return lines


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("verb", choices=("build", "check", "show"))
    ap.add_argument("--out", default=CENSUS_PATH)
    a = ap.parse_args(argv)
    try:
        c = build_census()
    except FileNotFoundError as e:
        print(f"genesis_census: {e}", file=sys.stderr)
        return 2
    text = _dumps(c)
    if a.verb == "show":
        print("\n".join(_summary(c)))
        return 0
    if a.verb == "check":
        have = None
        if os.path.exists(a.out):
            with open(a.out) as fh:
                have = fh.read()
        if have != text:
            print(f"genesis_census: {os.path.relpath(a.out, ROOT)} is STALE — run tools/genesis_census.py build")
            return 1
        print(f"genesis_census: {os.path.relpath(a.out, ROOT)} current")
        print("\n".join(_summary(c)))
        return 0
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", newline="\n") as fh:
        fh.write(text)
    print(f"genesis_census: wrote {os.path.relpath(a.out, ROOT)}")
    print("\n".join(_summary(c)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
