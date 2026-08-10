#!/usr/bin/env python
"""provenance.py — the AUTHORSHIP PROVENANCE LEDGER CLI (P0 cutover-gate instrument), v2.

v2 fixes the instrument the genesis audit caught lying (it reported "0
autodesk-sample" on a file 94 % Autodesk BYTES because it only walked the
ElemTable against ONE baseline).  Now:

  * STREAM-AWARE (--streams, default ON): every stream (Formats/Latest,
    Global/Latest, Global/ContentDocuments, Global/ElemTable, Global/History,
    Global/DocumentIncrementTable, Global/PartitionTable, BasicFileInfo,
    PartAtom, ProjectInformation, TransmissionData, RevitPreview4.0) and every
    Partitions/N save unit is classified by BYTES vs the baseline(s):
    identical / prefix-shared / % byte-identical (rolling block match) /
    ours, and rolled up BYTE-WEIGHTED: "of N total inflated bytes, X% identical
    -to-baseline, Y% modified-lineage, Z% ours".
  * MULTI-BASELINE (--baseline may repeat; 'all' = every samples/*.rvt): an
    element / stream is sample-derived if it matches ANY baseline (union), and
    the report says WHICH baseline (this is what catches DBViewProject = a
    0.91 clone of racbasic's and ElectricalSetting 46/49 fields = rme's).
  * EMBEDDED-STRING provenance (--strings, default ON): records / streams
    carrying Autodesk resource identifiers (Forge autodesk.* typeIds,
    assetlibrary_base.fbx, SunAndSky, ADSK, autodesk.com ...) are counted as
    'autodesk-resource-refs' (the G1c items).
  * IDENTITY (--identity, default ON): BasicFileInfo + DocumentIncrementTable
    must assert OUR identity (rvt.identity policy), never a template's.
  * The G1 verdict, recomputed HONESTLY: PASS requires the element layer AND
    zero identical-to-baseline bytes in the expression-bearing streams
    (Global/Latest, ContentDocuments, family save units) AND zero resource
    refs AND identity ours — with Formats/Latest reported SEPARATELY as the
    counsel-C4 schema stream.  An element-only run says so and does not
    certify G1.

Usage:
  tools/provenance.py FILE.rvt --baseline all --streams --json out.json
  tools/provenance.py FILE.rvt --baseline samples/rst...rvt --baseline samples/rme...rvt
  tools/provenance.py FILE.rvt --baseline auto           # best-overlapping sample
  tools/provenance.py FILE.rvt --baseline self           # baseline == the file
  tools/provenance.py FILE.rvt --no-streams --no-strings --no-identity   # v1 (element layer only)
  tools/provenance.py FILE.rvt --no-baseline
  tools/provenance.py FILE.rvt --composed-base auto      # vs the PINNED COMPOSED base it is / descends from

``--composed-base auto`` (issues #143 / #284) ledgers FILE against the
certified pinned composed genesis base it IS or DESCENDS FROM (found by
bytes: exact sha256, else the census descent test), with that pin's
authorship census: only the pin's residue is Autodesk-derived, its other
slots are ours by composition, FILE's own elements are created / cloned by
lineage into the residue.  It is also what a run falls back to when no
sample baseline resolves -- a fresh clone has no ``samples/`` and the pinned
base is its only available baseline -- so the pre-ship command above gives a
reading there instead of "everything unbaselined".  Element + strings +
identity layers; the byte-weighted STREAM ledger needs a sample corpus (the
census is element-level) and is skipped, so such a run never certifies G1.

Exit code: 0 = G1 certified PASS (all layers), 2 = fails, 3 = passes the
ledgered layers but is NOT a full G1 certification, 1 = error.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.mutate import Document                                    # noqa: E402
from rvt.provenance import format_report, provenance, reading_own_release  # noqa: E402

DEFAULT_CACHE_DIR = os.path.join(ROOT, "experiments", "genesis", "provenance", ".cache")


def _open_own_release(path: str) -> Document:
    """``Document.from_file`` under the file's own release framing."""
    with reading_own_release(path):
        return Document.from_file(path)


def composed_lineage(candidate: str, doc: Document, verbose: bool = True):
    """The ``rvt.frontdoor.census.Lineage`` when ``candidate`` IS or DESCENDS
    FROM a certified pinned composed base (else None): its ``pin_doc`` (or
    ``doc`` itself when it IS the pin) is THE baseline and
    ``composed_baseline()`` the pin's census (None = stale: ledgered
    conservatively)."""
    from rvt.frontdoor import census as C
    with reading_own_release(candidate):
        lin = C.lineage(candidate, doc)
    if lin is not None and verbose:
        how = "IS" if lin.exact else (f"descends from ({lin.evidence['probed_identical']:,}/"
                                      f"{lin.evidence['pin_slots_probed']:,} composed slots identical)")
        print(f"[composed-base] {os.path.basename(candidate)} {how} the pinned base {lin.pinned_id}; "
              f"census {'STALE (run tools/genesis_census.py build)' if lin.census is None else 'current'}",
              file=sys.stderr)
    return lin


def _elemtable_ids(path: str):
    """Cheap: read only Global/ElemTable ids of a file (for auto-baseline)."""
    from rvt.container import open_rvt
    from rvt.elemtable import inflate_global_stream, parse_elemtable
    with open_rvt(path) as f:
        st = inflate_global_stream(f.raw("Global/ElemTable"))
        return set(parse_elemtable(st.payload, os.path.basename(path)).ids())


def sample_paths() -> list:
    return sorted(glob.glob(os.path.join(ROOT, "samples", "*.rvt")))


def auto_baseline(candidate: str, verbose: bool = True) -> str | None:
    """Pick the samples/*.rvt whose ElemTable id set overlaps the candidate most."""
    cands = sample_paths()
    if not cands:
        return None
    try:
        cand_ids = _elemtable_ids(candidate)
    except Exception as e:
        print(f"[auto-baseline] cannot read candidate ElemTable: {e}", file=sys.stderr)
        return None
    best, best_score = None, 0.0
    for p in cands:
        if os.path.abspath(p) == os.path.abspath(candidate):
            continue
        try:
            ids = _elemtable_ids(p)
        except Exception:
            continue
        inter = len(cand_ids & ids)
        score = inter / max(1, len(cand_ids | ids))
        if verbose:
            print(f"[auto-baseline] {os.path.basename(p):40s} jaccard={score:.3f}", file=sys.stderr)
        if score > best_score:
            best, best_score = p, score
    if best is None or best_score < 0.05:
        if verbose:
            print("[auto-baseline] no plausible baseline found", file=sys.stderr)
        return None
    return best


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", help="candidate .rvt to ledger")
    ap.add_argument("--baseline", action="append", default=None,
                    help="reference Autodesk sample .rvt(s) the candidate descends from; may be "
                         "given multiple times (multi-baseline union); 'all' = every "
                         "samples/*.rvt; 'auto' (default) = the best-overlapping sample; "
                         "'self' = the file itself")
    ap.add_argument("--no-baseline", action="store_true",
                    help="ledger structurally with no baseline (everything unbaselined)")
    ap.add_argument("--composed-base", choices=("auto", "off"), default=None,
                    help="'auto' = ledger against the PINNED COMPOSED GENESIS BASE the file is / "
                         "descends from, with its authorship census (only the pin's residue is "
                         "Autodesk-derived; issues #143/#284); also the fallback when no sample "
                         "baseline resolves (fresh clone). 'off' = never. Stream ledger skipped.")
    ap.add_argument("--streams", dest="streams", action="store_true", default=True,
                    help="ledger the STREAMS byte-weighted (default ON)")
    ap.add_argument("--no-streams", dest="streams", action="store_false",
                    help="skip the stream ledger (v1 element-layer-only behaviour)")
    ap.add_argument("--strings", dest="strings", action="store_true", default=True,
                    help="scan for Autodesk resource identifiers (default ON)")
    ap.add_argument("--no-strings", dest="strings", action="store_false")
    ap.add_argument("--identity", dest="identity", action="store_true", default=True,
                    help="check the identity block against rvt.identity policy (default ON)")
    ap.add_argument("--no-identity", dest="identity", action="store_false")
    ap.add_argument("--json", default=None, help="write the full JSON report here")
    ap.add_argument("--examples", type=int, default=3,
                    help="example element ids+names per class per provenance (default 3)")
    ap.add_argument("--max-classes", type=int, default=8,
                    help="classes shown per category in the text table (default 8)")
    ap.add_argument("--no-examples", action="store_true", help="omit examples from the text table")
    ap.add_argument("--no-units", action="store_true", help="skip embedded save-unit enumeration")
    ap.add_argument("--strict", action="store_true",
                    help="also gate the report-only categories (datums, internal bookkeeping)")
    ap.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR,
                    help=f"baseline block-index cache (default {os.path.relpath(DEFAULT_CACHE_DIR, ROOT)}); "
                         "'' disables caching")
    ap.add_argument("-q", "--quiet", action="store_true", help="print only the gate verdict")
    args = ap.parse_args(argv)

    t0 = time.time()
    if not os.path.exists(args.file):
        print(f"error: {args.file}: no such file", file=sys.stderr)
        return 1

    if args.composed_base == "auto" and (args.baseline or args.no_baseline):
        print("error: --composed-base auto takes no --baseline / --no-baseline (the pin the "
              "file descends from IS the baseline)", file=sys.stderr)
        return 1
    base_paths: list = []
    if not args.no_baseline and args.composed_base != "auto":
        wanted = args.baseline or ["auto"]
        for w in wanted:
            if w == "all":
                base_paths += [p for p in sample_paths()
                               if os.path.abspath(p) != os.path.abspath(args.file)]
            elif w == "self":
                base_paths.append(args.file)
            elif w == "auto":
                p = auto_baseline(args.file, verbose=not args.quiet)
                if p:
                    if not args.quiet:
                        print(f"[auto-baseline] using {p}", file=sys.stderr)
                    base_paths.append(p)
            else:
                if not os.path.exists(w):
                    print(f"error: baseline {w}: no such file", file=sys.stderr)
                    return 1
                base_paths.append(w)
        # de-duplicate, keep order
        seen = set()
        base_paths = [p for p in base_paths
                      if not (os.path.abspath(p) in seen or seen.add(os.path.abspath(p)))]

    # every file is opened under its OWN release (a Revit 2025/2024 candidate
    # is ledgered, not refused with a framing error -- issue #14); the ledger
    # itself then runs under the candidate's release
    doc = _open_own_release(args.file)
    baselines = []
    for bp in base_paths:
        if os.path.abspath(bp) == os.path.abspath(args.file):
            baselines.append(doc)
        else:
            baselines.append(_open_own_release(bp))

    # the pinned composed base as THE baseline: asked for, or the fallback when
    # no sample resolves (a fresh clone's only available baseline is the pin)
    composed = lineage = None
    streams = args.streams and not args.no_baseline
    if args.composed_base == "auto" or (not baselines and not args.no_baseline
                                        and args.composed_base != "off"):
        lineage = composed_lineage(args.file, doc, verbose=not args.quiet)
        if lineage is not None:
            composed = lineage.composed_baseline()
            baselines = [doc if lineage.exact else lineage.pin_doc]
            if streams and not args.quiet:
                print("[composed-base] stream ledger skipped: it needs a SAMPLE corpus (the census "
                      "is element-level) -- this run cannot certify G1", file=sys.stderr)
            streams = False
        elif args.composed_base == "auto":
            print(f"error: {args.file} neither is nor descends from a certified pinned composed "
                  "genesis base; give a sample --baseline instead", file=sys.stderr)
            return 1
        elif not args.quiet:
            print("[composed-base] no sample baseline resolved and the file neither is nor "
                  "descends from a pinned composed base: ledgering with no baseline", file=sys.stderr)

    with reading_own_release(args.file):
        report = provenance(doc, baselines[0] if baselines else None,
                            baselines=baselines or None,
                            examples=args.examples, with_units=not args.no_units,
                            strict=args.strict, streams=streams,
                            strings=args.strings, identity=args.identity,
                            cache_dir=(args.cache_dir or None), verbose=not args.quiet,
                            composed=composed)
    if lineage is not None:
        report["composed_base"] = {"kind": lineage.kind, "pinned_id": lineage.pinned_id,
                                   "pin": os.path.relpath(lineage.pin_path, ROOT),
                                   "census": "STALE" if lineage.census is None else "current",
                                   "descent": dict(lineage.evidence) or None}
    report["elapsed_s"] = round(time.time() - t0, 1)

    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)) or ".", exist_ok=True)
        with open(args.json, "w") as fh:
            json.dump(report, fh, indent=2, default=str)

    if args.quiet:
        print(report["gate_G1"]["verdict"])
    else:
        print(format_report(report, show_examples=not args.no_examples,
                            max_classes=args.max_classes))
        if args.json:
            print(f"\njson report: {args.json}")
        print(f"[{report['elapsed_s']}s]")
    g = report["gate_G1"]
    if g["passes"]:
        return 0 if g.get("certifies_G1") else 3
    return 2


if __name__ == "__main__":
    sys.exit(main())
