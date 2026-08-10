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
elements as "autodesk-sample" (3,058 blockers on a prompt job before #143).

What this tool writes (``src/rvt/frontdoor/assets/genesis_census.json``,
mirrored into the plugin by ``tools/sync_plugin.py``): for each pinned base,
keyed by its sha256, the element ids that are STILL byte-identical to the
Autodesk ancestor the lineage was reduced from — derived ONLY from tracked
evidence, reproducible on a fresh clone:

* the base's own ElemTable ids + classes (the pinned ``.rvt`` is in-repo);
* its composition chain, walked from the compose manifest
  (``experiments/genesis/**/G_ABPD*.manifest.json``): every in-place rung's
  certified report (``kind: inplace``; ``landed_slots`` = slots our
  constructor emitted an object at; ``byte_delta.records_changed_ids`` /
  ``changed_ids`` = slots whose bytes then differed from the rung's parent),
  recursively through each report's ``parent`` down to the ancestor (the
  reduced sample ``K4``, which no in-place rung produces);
* any byte-ground-truth census a stream recorded for a pinned base
  (``rvt.genesis.residue_c`` wrote one for the 2026 base: seq-102 compare vs
  K4, per id, with dispositions) — used to CROSS-CHECK the chain method and
  to annotate dispositions (machinery / coincident / genuine Autodesk values).

The law actually applied (what "ours by composition" means here): a base
slot is ours iff SOME certified rung's ``byte_delta`` lists its id among the
records whose bytes changed (``records_changed_ids`` / ``changed_ids``) AND
that rung's ``landed_slots`` says our constructor emitted an object there --
"changed => landed by our constructor" is checked per rung, three ways: the
id sets themselves, the rung report's own ``unexpected_changed_ids == []``,
and its ``assertion_holds``; a rung report failing any of them voids the
census (exit 1, nothing written).  ``identical_to_ancestor`` = base ids NO
rung changed: their records are still the ancestor's serialization, which is
``autodesk-sample`` under ``rvt.provenance``'s byte law (byte-identical to
the sample at the same id).  Slots a rung landed but re-emitted
byte-identically (content-free machinery, coincident designation facts) stay
IN that set -- reported, with their recorded disposition, never argued away.
Ids a rung changed that are no longer aboard the pin must be the compose's
recorded phase-2 deletions (the reconciliation ``show`` prints: 2026 2,700
changed = 2,680 aboard + 20 deleted; 2025 2,392 = 2,391 + 1; 2024 2,356 =
2,355 + 1).  Where a byte-ground-truth census of the same base exists (2026:
``residue_c``, seq-102 compare vs K4) the chain result must reproduce it id
for id -- a disagreement is byte truth overruling the chain: exit 1 and the
asset is NOT rewritten, so the shipped census stays the last one byte truth
agreed with (a re-pinned base then reads STALE in the gate = the conservative
ledger, never an over-claim).  2025/2024 have no id-level byte truth; the
per-rung law + the deletion reconciliation are their whole evidence.

Usage::

    tools/genesis_census.py build            # (re)write the census asset
    tools/genesis_census.py check            # exit 1 if the asset is stale
    tools/genesis_census.py show             # one screen per base

Exit codes: 0 ok, 1 stale / a law violated / chain-vs-byte-truth
disagreement (``build`` then writes nothing), 2 inputs missing.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from collections import Counter
from typing import Dict, List, Optional, Set

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.frontdoor import base as B                                   # noqa: E402
from rvt.frontdoor.census import CENSUS_PATH, SCHEMA                 # noqa: E402

EXPERIMENTS = os.path.join(ROOT, "experiments")
#: substrings a JSON must contain to be worth parsing (558 files / 42 MB
#: under experiments/; only the report-shaped ~250 matter here)
_REPORT_MARKERS = (b'"out"', b'"alias_of"', b'"landed_slots"', b'"autodesk_serialization_identical"')


def _abs(p: str) -> str:
    return os.path.abspath(p if os.path.isabs(p) else os.path.join(ROOT, p))


def _rel(p: str) -> str:
    return os.path.relpath(_abs(p), ROOT).replace(os.sep, "/")


# ---------------------------------------------------------------------------
# the report index: which tracked JSON produced which .rvt
# ---------------------------------------------------------------------------
class ReportIndex:
    """Every report-shaped tracked JSON under ``experiments/``, parsed once:
    ``docs`` (relpath -> dict), ``by_out`` (the ``.rvt`` a report produced ->
    report relpath; an alias report describes ``<its own stem>.rvt``), and
    ``truth`` (subject ``.rvt`` -> a byte-ground-truth census of it)."""

    def __init__(self, root: str = EXPERIMENTS):
        self.docs: Dict[str, dict] = {}
        self.by_out: Dict[str, str] = {}
        self.truth: Dict[str, str] = {}
        weight: Dict[str, int] = {}
        for p in sorted(glob.glob(os.path.join(root, "**", "*.json"), recursive=True)):
            try:
                with open(p, "rb") as fh:
                    blob = fh.read()
            except OSError:
                continue
            if not any(m in blob for m in _REPORT_MARKERS):
                continue
            try:
                d = json.loads(blob)
            except ValueError:
                continue
            if not isinstance(d, dict):
                continue
            rp = _rel(p)
            self.docs[rp] = d
            if "autodesk_serialization_identical" in d and d.get("subject"):
                self.truth[_rel(d["subject"])] = rp
                continue
            out = d.get("out")
            if isinstance(out, dict):
                out = out.get("file")
            if not (isinstance(out, str) and out.endswith(".rvt")):
                # an alias / out-less rung report describes <own stem>.rvt
                out = rp[:-5] + ".rvt" if (d.get("alias_of") or d.get("kind") == "inplace") else None
            if out is None:
                continue
            key, w = _rel(out), self._weight(d)
            # a compose manifest and a summary may both name one out: prefer
            # the document that carries the evidence
            if key not in self.by_out or w > weight[key]:
                self.by_out[key], weight[key] = rp, w

    @staticmethod
    def _weight(d: dict) -> int:
        if d.get("op") == "compose":
            return 3
        if d.get("kind") == "inplace":
            return 2
        return 1 if d.get("alias_of") else 0

    def producer(self, rvt_relpath: Optional[str]) -> Optional[str]:
        return self.by_out.get(_rel(rvt_relpath)) if rvt_relpath else None


# ---------------------------------------------------------------------------
# walking one base's composition chain
# ---------------------------------------------------------------------------
class LawViolation(ValueError):
    """The tracked evidence breaks a law the census depends on (a rung changed
    a record it did not land, a rung report's own assertion fails, a changed
    id vanished without a recorded deletion, or the chain disagrees with byte
    ground truth): no census may be derived -- or shipped -- from it."""


class Chain:
    """Accumulates, over every certified rung report reachable from a compose
    manifest: the slots our constructors LANDED, the ids whose bytes a rung
    CHANGED, the ids the compose DELETED in phase 2, the rung / compose names
    read, the ancestor file(s) the walk bottomed out at (no in-place rung
    produces them = the reduced sample), and every LAW VIOLATION met on the
    way ("changed => landed by our constructor", per rung)."""

    def __init__(self, index: ReportIndex):
        self.index = index
        self.landed: Set[int] = set()
        self.changed: Set[int] = set()
        self.deleted: Set[int] = set()
        self.rungs: List[str] = []
        self.composes: List[str] = []
        self.ancestors: List[str] = []
        self.no_byte_evidence: List[str] = []
        self.violations: List[str] = []
        self._seen: Set[str] = set()

    def walk_file(self, rvt_relpath: str) -> None:
        rep = self.index.producer(rvt_relpath)
        if rep is None:
            self._ancestor(rvt_relpath)
        else:
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
        d = self.index.docs.get(rp)
        if d is None:
            raise FileNotFoundError(f"rung report missing from the tracked tree: {rp}")
        if d.get("alias_of"):
            # md5-identical alias (Z_RA_2025 -> RA_2025 ...): the evidence is
            # the real report's, and ITS parent chain
            self.walk_report(os.path.join(os.path.dirname(rp), f"{d['alias_of']}.json"))
        elif d.get("op") == "compose":
            self.composes.append(rp)
            for r in ((d.get("phase_1_inplace") or {}).get("merge") or {}).get("rungs") or []:
                if r.get("report_file"):
                    self.walk_report(r["report_file"])
            for spec in (d.get("phase_2_deletions") or {}).get("specs") or []:
                self._deletion(spec)
            if (d.get("base") or {}).get("file"):
                self.walk_file(d["base"]["file"])
        elif d.get("kind") == "inplace":
            self._rung(rp, d)
        else:
            # a reduction / triage report (K4 <- K3 <- R9 ...): the in-place
            # ladder starts ABOVE this file, so it is the byte ancestor -- the
            # reduced Autodesk sample every rung's byte_delta is measured
            # from.  Nothing of ours lands below it; the walk stops here.
            out = d.get("out")
            self._ancestor(str((out.get("file") if isinstance(out, dict) else out) or rp))

    def _deletion(self, spec: dict) -> None:
        """A compose's phase-2 deletion: the seed ids of its tracked spec file
        (``source_file``; the shapes ``genesis_compose.DeletionSpec.from_json``
        accepts) left the file lawfully (reduce law), so a rung-changed id
        missing from the pin is accounted for iff it is here.  An unreadable
        spec is itself a violation: the reconciliation has no evidence."""
        src = spec.get("source_file")
        try:
            with open(_abs(str(src))) as fh:
                obj = json.load(fh)
            if isinstance(obj, list):
                obj = {"ids": obj}
            ids = obj.get("ids") or obj.get("delete") or obj.get("seed") or obj.get("delete_ids") or []
            self.deleted.update(int(x) for x in ids)          # a dict of ids iterates its keys
        except (OSError, ValueError, TypeError, AttributeError) as e:
            self.violations.append(f"phase-2 deletion spec {spec.get('name')} ({src}) unreadable: "
                                   f"{type(e).__name__}: {e}")

    def _rung(self, rp: str, d: dict) -> None:
        name = str(d.get("rung") or os.path.basename(rp)[:-5])
        self.rungs.append(name)
        landed = {int(row["slot"]) for row in d.get("landed_slots") or [] if "slot" in row}
        self.landed |= landed
        bd = d.get("byte_delta") or {}
        changed = bd.get("records_changed_ids", bd.get("changed_ids"))
        if isinstance(changed, list):
            changed = {int(x) for x in changed}
            self.changed |= changed
            # THE LAW the census rests on, checked on the id sets themselves:
            # a record whose bytes this rung changed is one our constructor
            # landed -- else "changed" would not mean "ours"
            stray = changed - landed
            if stray:
                self.violations.append(f"rung {name} ({rp}): {len(stray)} changed id(s) its constructor "
                                       f"did not land {sorted(stray)[:8]}")
        else:
            # no per-id byte evidence in this report: by the byte law NONE of
            # its slots may be presumed changed (conservative; recorded)
            self.no_byte_evidence.append(name)
        # ... and as the rung's own certification recorded it
        if bd.get("unexpected_changed_ids"):
            self.violations.append(f"rung {name} ({rp}): byte_delta.unexpected_changed_ids = "
                                   f"{bd['unexpected_changed_ids'][:8]}")
        if "assertion_holds" in bd and bd["assertion_holds"] is not True:
            self.violations.append(f"rung {name} ({rp}): byte_delta.assertion_holds is "
                                   f"{bd['assertion_holds']!r} (problems: {bd.get('problems')})")
        if d.get("parent"):
            self.walk_file(d["parent"])

    def reconcile(self, aboard: Set[int]) -> dict:
        """Every id a rung changed or landed is either ABOARD the pin or one
        of the compose's recorded phase-2 deletions, and no deleted id is
        aboard -- the count-level truth for bases with no byte census."""
        gone = (self.changed | self.landed) - aboard
        unaccounted = sorted(gone - self.deleted)
        resurrected = sorted(self.deleted & aboard)
        if unaccounted:
            self.violations.append(f"{len(unaccounted)} id(s) a rung changed/landed are neither aboard "
                                   f"the pin nor a recorded phase-2 deletion {unaccounted[:8]}")
        if resurrected:
            self.violations.append(f"{len(resurrected)} recorded phase-2 deletion(s) still aboard the "
                                   f"pin {resurrected[:8]}")
        return {
            "changed_in_chain": len(self.changed), "changed_aboard": len(self.changed & aboard),
            "changed_then_deleted": sorted(self.changed - aboard),
            "landed_in_chain": len(self.landed), "phase_2_deleted": len(self.deleted),
        }


# ---------------------------------------------------------------------------
# one base
# ---------------------------------------------------------------------------
def _elemtable(path: str) -> Dict[int, str]:
    """{host element id: class name} of a project file of any release."""
    from rvt.mutate import Document
    from rvt.versions import reading
    with reading(path):
        doc = Document.from_file(path)
        return {int(e): (doc.class_of(int(e)) or "?") for e in doc.et_by_id}


def census_one(year: int, index: ReportIndex, audit: Optional[Dict[str, dict]] = None) -> dict:
    """The census entry of the pinned base of ``year``.  Raises
    :class:`LawViolation` when the chain's evidence breaks the per-rung law
    or the deletion reconciliation; ``audit`` (base id -> reconciliation)
    receives the numbers ``show`` prints -- kept OUT of the asset, whose
    shape the front door's ``rvt.frontdoor.census`` reads."""
    rb = B.resolve_base(target_release=int(year))        # sha-verified against the pin
    if not rb.pinned:
        raise B.BaseError(f"Revit {year}: $RVT_GENESIS_BASE / --base override in force; "
                          "the census is of the PINNED base only")
    st = B.release_status(int(year))
    ids = _elemtable(rb.path)
    chain = Chain(index)
    chain.walk_file(str(st["relpath"]))
    reconciliation = chain.reconcile(set(ids))
    if chain.violations:
        raise LawViolation(f"{st['id']} ({year}): " + "; ".join(chain.violations))
    if audit is not None:
        audit[str(st["id"])] = reconciliation
    changed = chain.changed & ids.keys()
    identical = sorted(ids.keys() - changed)
    never_authored = [e for e in identical if e not in chain.landed]
    out = {
        "id": st["id"], "revit_release": int(year), "sha256": rb.sha256,
        "relpath": st["relpath"], "host_elements": len(ids),
        "ancestor": chain.ancestors,
        "ours_by_composition": len(ids) - len(identical),
        "identical_to_ancestor": {
            "count": len(identical),
            "meaning": ("host element ids whose records NO certified rung of the composition "
                        "chain changed: their bytes are the Autodesk ancestor's serialization "
                        "(= 'autodesk-sample' under rvt.provenance's byte law). Includes slots "
                        "our constructors landed but re-emitted byte-identically (content-free "
                        "machinery / coincident designation facts) -- reported, not argued away."),
            "landed_but_identical": len(identical) - len(never_authored),
            "never_authored": len(never_authored),
            "by_class": dict(Counter(ids[e] for e in identical).most_common()),
            "ids": identical,
        },
        "never_authored_ids": never_authored,
        "chain": {
            "rungs": chain.rungs, "composes": chain.composes,
            "rungs_without_byte_evidence": chain.no_byte_evidence,
            "landed_slots": len(chain.landed & ids.keys()), "changed_ids": len(changed),
        },
    }
    truth = index.truth.get(_rel(str(st["relpath"])))
    if truth:
        cc = out["cross_check"] = _cross_check(index.docs[truth], truth, set(identical))
        if cc["agree"] is not True:
            # byte truth overrules the chain: no census is derived (nothing
            # written), so the shipped asset stays the last one truth agreed with
            raise LawViolation(f"{st['id']} ({year}): CHAIN vs BYTE TRUTH DISAGREE -- the chain says "
                               f"{cc['chain_identical']} identical, {truth} says {cc['truth_identical']} "
                               f"(only in truth {cc['only_in_truth']}, only in chain {cc['only_in_chain']})")
    return out


def _cross_check(d: dict, source: str, mine: Set[int]) -> dict:
    """The chain method vs a byte-ground-truth census of the same base
    (e.g. residue_c/census.json: seq-102 payload compare vs K4 per id)."""
    truth = {int(e["id"]): e.get("disposition") for e in d.get("elements") or []}
    agree = mine == truth.keys()
    return {
        "source": source, "truth_identical": len(truth), "chain_identical": len(mine),
        "agree": agree,
        "only_in_truth": sorted(truth.keys() - mine)[:20],
        "only_in_chain": sorted(mine - truth.keys())[:20],
        "by_disposition": (dict(d.get("by_disposition") or {}) if agree else
                           dict(Counter(truth[e] for e in mine & truth.keys()).most_common())),
        "dispositions": d.get("dispositions"),
    }


# ---------------------------------------------------------------------------
# the asset
# ---------------------------------------------------------------------------
def build_census(audit: Optional[Dict[str, dict]] = None) -> dict:
    """The whole asset (every certified pin).  Raises ONE :class:`LawViolation`
    naming every base whose evidence breaks a law (see :func:`census_one`);
    ``audit`` collects each base's reconciliation."""
    index = ReportIndex()
    bases: Dict[str, dict] = {}
    broken: List[str] = []
    for year in B.PIN.release_years():
        if B.release_status(year)["certified"]:
            try:
                b = census_one(year, index, audit)
            except LawViolation as e:
                broken.append(str(e))
                continue
            bases[b["sha256"]] = b
    if broken:
        raise LawViolation(" | ".join(broken))
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


def dumps(c: dict) -> str:
    """indent=1 JSON with every all-integer array folded onto ONE line (the
    asset ships in the plugin; a line per id would triple its size)."""
    return re.sub(r"\[[\d,\s]+\]", lambda m: re.sub(r"\s+", "", m.group(0)),
                  json.dumps(c, indent=1)) + "\n"


def _summary(c: dict, audit: Optional[Dict[str, dict]] = None) -> str:
    lines = []
    for sha, b in (c.get("bases") or {}).items():
        it = b["identical_to_ancestor"]
        lines.append(f"{b['id']} ({b['revit_release']}, sha {sha[:12]}): {b['host_elements']:,} host elements; "
                     f"{b['ours_by_composition']:,} ours by composition; "
                     f"{it['count']:,} byte-identical to the ancestor "
                     f"({it['landed_but_identical']} landed-but-identical, {it['never_authored']} never authored)")
        lines.append(f"   ancestor: {', '.join(b['ancestor']) or '?'}; rungs: {len(b['chain']['rungs'])}; "
                     f"no byte evidence: {b['chain']['rungs_without_byte_evidence'] or 'none'}")
        rec = (audit or {}).get(str(b["id"]))
        if rec:
            lines.append(f"   law: changed => landed holds on every rung; reconciliation: "
                         f"{rec['changed_in_chain']:,} ids changed by the chain = {rec['changed_aboard']:,} aboard "
                         f"+ {len(rec['changed_then_deleted'])} deleted in phase 2 {rec['changed_then_deleted'][:8]}"
                         f"{' …' if len(rec['changed_then_deleted']) > 8 else ''} "
                         f"(of {rec['phase_2_deleted']} recorded deletions), none unaccounted")
        lines.append("   top identical classes: "
                     + ", ".join(f"{k} {v}" for k, v in list(it["by_class"].items())[:8]))
        cc = b.get("cross_check")
        if cc:
            lines.append(f"   cross-check vs {cc['source']}: agree={cc['agree']} "
                         f"(truth {cc['truth_identical']} / chain {cc['chain_identical']}); "
                         f"dispositions {cc['by_disposition']}")
        elif rec:
            lines.append("   cross-check: no byte-ground-truth census tracked for this base -- the per-rung "
                         "law + the reconciliation above are its evidence")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("verb", choices=("build", "check", "show"))
    ap.add_argument("--out", default=CENSUS_PATH)
    a = ap.parse_args(argv)
    audit: Dict[str, dict] = {}
    try:
        c = build_census(audit)
    except (B.BaseError, FileNotFoundError) as e:
        print(f"genesis_census: {e}", file=sys.stderr)
        return 2
    except LawViolation as e:
        print(f"genesis_census: LAW VIOLATED, no census derived (nothing written): {e}", file=sys.stderr)
        return 1
    rel = os.path.relpath(a.out, ROOT)
    if a.verb == "check":
        have = None
        if os.path.exists(a.out):
            with open(a.out) as fh:
                have = fh.read()
        if have != dumps(c):
            print(f"genesis_census: {rel} is STALE — run tools/genesis_census.py build")
            return 1
        print(f"genesis_census: {rel} current")
    elif a.verb == "build":
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        with open(a.out, "w", newline="\n") as fh:
            fh.write(dumps(c))
        print(f"genesis_census: wrote {rel}")
    print(_summary(c, audit))
    return 0


if __name__ == "__main__":
    sys.exit(main())
