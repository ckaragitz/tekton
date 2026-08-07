#!/usr/bin/env python
"""run_ladder2025.py -- THE Y2025 SUBSTITUTION LADDER: the certified v3
in-place ladder (tools/genesis_substitute_v3.py), re-pointed at a Revit-2025
base with every constructor record passed through the port2025 adaptation
layer (rvt.genesis.port2025).  Campaign step G25-4 of
docs/writer/genesis-2025-plan.md, run by the genesis-2025-port stream.

WHAT THIS SCRIPT ADDS (and nothing else -- v3 and the X builders are
IMPORTED, never edited):

1.  A **2025 process context** (:func:`port2025_run_context`): the six
    partition-framing ordinals of the base file bound via
    ``rvt.versions.reading`` PLUS the per-release default codecs swapped to
    the pinned 2025 schema for the duration of the run --
    ``rvt.adocument._DECODER`` (the ADocument codec SubstContext /
    TypedEditor default to), ``rvt.encode._DEFAULT_ENCODER`` (the
    module-level ``encode_record`` regadd's framed_records_from uses), and
    the ``ObjectDecoder`` name inside ``rvt.regadd`` / ``rvt.regdiff``
    (their lazy report decoders).  Everything is restored on exit; nothing
    leaks into the 2026 creation path.
2.  A **build adapter**: ``genesis_substitute_v3.build_for`` is wrapped so
    every record the X builders produce is passed through
    ``port2025.adapt_record`` (2025 class ordinals, 2025-shaped bodies,
    the confirmed field maps).  Records of 2026-only classes (the conductor
    catalog) are dropped LOUDLY into the build notes -- they emit nothing
    on a 2025 build by design (their 2025 representation is the
    string-valued ``RbsWireType.m_strMaxConductorSize``, which the adapter
    writes from the referenced size cell's own label).
3.  The **2025 catalog constants**: ``rvt.genesis.catalog``'s frozen enum /
    per-key structural profile loaders are redirected to the 2025-mined
    tables (``builtin_category_enum_2025.json`` -- 1,068 categories vs
    2026's 1,074 -- and ``builtin_style_profile_2025.json``), so the Y6 /
    Y_cat catalog rows are shaped by the 2025 corpus, not the 2026 one.
4.  ``genesis_substitute_v3._class_id`` ("ElementHeader") resolves against
    the 2025 map.
5.  BASE RESOLUTION + THE HONESTY BANNER: prefers the reduce2025 stream's
    ``B2025_K4`` (the 2025 twin of the certified K4); falls back to the
    deepest 2025 reduction present, else the untouched 2025 rst sample.
    Whatever base is used, it is passed with ``--allow-uncertified`` and the
    probes manifest is stamped: **NO 2025 file is viewer-certified yet**
    (the viewer session is signed out) -- every rung is STAGED, its
    certification PENDING the next viewer session, with the base itself as
    the batch's round-1 control (which simultaneously answers "does the
    viewer accept 2025 uploads at all").

Usage (from the repo root)::

    .venv/bin/python experiments/genesis2025/subst/run_ladder2025.py
    .venv/bin/python experiments/genesis2025/subst/run_ladder2025.py --only Y1
    .venv/bin/python experiments/genesis2025/subst/run_ladder2025.py --base <2025.rvt>
"""
from __future__ import annotations

import argparse
import contextlib
import functools
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

OUT_DIR = HERE
SAMPLE_2025 = os.path.join(ROOT, "samples", "2025", "rstbasicsampleproject.rvt")

#: where the reduce2025 stream's outputs are expected, deepest first.  The
#: certified-lineage name (B2025_K4) is polled first; then the K/R rungs.
BASE_CANDIDATES = [
    "experiments/genesis2025/B2025_K4.rvt",
    "experiments/genesis2025/triage/K4.rvt",
    "experiments/genesis2025/triage/B2025_K4.rvt",
    "experiments/genesis2025/reduce/B2025_K4.rvt",
    "experiments/genesis2025/triage/K3.rvt",
    "experiments/genesis2025/R9.rvt",
    "experiments/genesis2025/reduce/R9.rvt",
    "experiments/genesis2025/R5.rvt",
    "experiments/genesis2025/reduce/R5.rvt",
]


def resolve_base(explicit: str = "") -> tuple:
    """(path, description) of the deepest 2025 base available right now."""
    if explicit:
        return os.path.abspath(explicit), "explicit --base"
    for rel in BASE_CANDIDATES:
        p = os.path.join(ROOT, rel)
        if os.path.exists(p):
            return p, f"reduce2025 stream output {rel}"
    hits = sorted(glob.glob(os.path.join(ROOT, "experiments", "genesis2025", "**", "*.rvt"),
                            recursive=True))
    hits = [h for h in hits if os.path.dirname(h) != OUT_DIR
            and not os.path.basename(h).startswith(("Y", "CTRL"))]
    if hits:
        return hits[-1], "deepest 2025 artifact found under experiments/genesis2025"
    return SAMPLE_2025, ("FALLBACK: the untouched quarantined 2025 rst sample "
                        "(no reduce2025 output exists yet; the sample doubles as "
                        "the round-1 'viewer accepts 2025 uploads' control)")


@contextlib.contextmanager
def port2025_run_context(base_path: str):
    """Bind the 2025 framing ordinals + swap every per-release default codec
    to the pinned 2025 schema; restore all of it on exit."""
    from rvt import adocument as adoc
    from rvt import encode as ENC
    from rvt import regadd, regdiff, versions
    from rvt.genesis import catalog as CAT
    from rvt.genesis import port2025 as P25
    from rvt.objects import ObjectDecoder
    import genesis_substitute_v3 as V3

    dec25, enc25, schema25 = P25._S25()
    rel = versions.detect_release(base_path)
    if rel != 2025:
        raise SystemExit(f"base {base_path} is Revit {rel}, not 2025 -- refusing "
                         "(release mixing inside one ladder is the exact trap "
                         "rvt.versions.require_release exists for)")

    saved = {}

    def swap(mod, name, value):
        saved[(mod, name)] = getattr(mod, name)
        setattr(mod, name, value)

    # lineage banner for the reports (the reduce2025 stream's certified-recipe
    # ladder; docs/inbox/genesis-2025-reduce.md)
    V3.BASE_LINEAGE.setdefault(
        os.path.relpath(base_path, ROOT),
        "B2025_K4 = the reduce2025 stream's family-free 2025 base (sha256 276be333...): "
        "samples/2025/rstbasicsampleproject -> R5..R9_2025 (maxgc, every rung "
        "validator-0-errors + reduce_law EDIT-FREE) -> K3_2025 (usage nulls, the "
        "certified 2026 K3 recipe, edits == neutralised set exactly) -> B2025_K4 "
        "(all 52 embedded family documents removed, four-registry coherent 1/0/0/0, "
        "residual GUID bytes 0).  VIEWER CERTIFICATION PENDING (staged as the "
        "reduce2025 stream's batch with control; nothing 2025 has ever been uploaded).")
    enum25, prof25 = P25.load_2025_catalog_constants()
    with versions.reading(base_path) as ords:
        # the re-blocker's own copies of the framing ordinals (rvt.reduce bakes
        # BLOCK_TAG and imports the trailer tag by name -- versions.reading
        # patches rvt.partitions only; this was genesis-2025-plan.md section-7's
        # named risk, and Y1's first 2025 run hit it exactly:
        # 'walker errors after re-block: unexpected tag 0x0f28 at 18')
        from rvt import reduce as RED
        swap(RED, "BLOCK_TAG", ords["BLOCK_TAG"])
        swap(RED, "BLOCK_TRL_TAG", ords["TRAILER_TAG"])
        swap(adoc, "_DECODER", adoc.ADocumentDecoder(schema25))
        swap(ENC, "_DEFAULT_ENCODER", ENC.ObjectEncoder(decoder=dec25))
        swap(regadd, "ObjectDecoder", functools.partial(ObjectDecoder, schema25))
        swap(regdiff, "ObjectDecoder", functools.partial(ObjectDecoder, schema25))
        swap(V3, "_class_id", P25.class_id_2025)
        swap(CAT, "load_builtin_category_enum",
             lambda *a, **k: enum25)
        swap(CAT, "load_builtin_style_profile",
             lambda *a, **k: prof25)
        orig_build_for = V3.build_for
        swap(V3, "build_for", _make_adapted_build_for(orig_build_for))
        try:
            yield
        finally:
            for (mod, name), v in saved.items():
                setattr(mod, name, v)


def _make_adapted_build_for(orig_build_for):
    """Wrap V3.build_for: every X-builder record -> port2025.adapt_record."""
    from rvt.genesis import port2025 as P25
    import genesis_substitute as GS

    def adapted_build_for(rung, ctx):
        sb = orig_build_for(rung, ctx)
        allrecs = list(sb.records) + list(sb.new_only or [])
        names = {}
        for r in allrecs:
            nm = GS._rec_name(r) or GS._catalog_name(r)
            if nm:
                names[int(r.elem_id)] = nm
        resolve = lambda i: names.get(int(i))                     # noqa: E731

        def port(records, dropped):
            out = []
            for r in records:
                try:
                    out.append(P25.adapt_record(r, resolve_name=resolve))
                except P25.Missing2025 as ex:
                    dropped.append({"ours": int(r.elem_id), "class": r.class_name,
                                    "name": names.get(int(r.elem_id), ""),
                                    "reason": str(ex)})
            return out

        dropped: list = []
        kept = port(sb.records, dropped)
        kept_new = port(sb.new_only or [], dropped)
        kept_ids = {int(r.elem_id) for r in kept}
        corr = {int(k): int(v) for k, v in sb.corr.items() if int(v) in kept_ids}
        notes = list(sb.notes) + [
            f"[port2025] {len(kept)} records adapted to the Revit-2025 schema "
            f"(2025 class ordinals, confirmed field maps; rvt.genesis.port2025); "
            f"{len(dropped)} record(s) of 2026-only classes emit nothing on 2025"
            + (": " + ", ".join(sorted({d['class'] for d in dropped}))
               if dropped else "")]
        adapted = GS.SubstBuild(
            old_ids=list(sb.old_ids), records=kept, corr=corr, new_only=kept_new,
            notes=notes, residue=dict(sb.residue or {}),
            info={**dict(sb.info or {}),
                  "port2025": {"adapted": len(kept) + len(kept_new),
                               "dropped_2026_only": dropped}})
        extra = getattr(sb, "extra_records_for_resolution", None)
        if extra is not None:
            adapted.extra_records_for_resolution = extra
        return adapted

    return adapted_build_for


def stamp_probes_manifest(base_path: str, base_how: str) -> None:
    """Post-stamp probes.json with the 2025 campaign truth: release, the
    PENDING certifications, and the round-1 reading."""
    p = os.path.join(OUT_DIR, "probes.json")
    if not os.path.exists(p):
        return
    with open(p) as fh:
        m = json.load(fh)
    m["release"] = 2025
    m["stream"] = ("genesis-2025-port (THE Y2025 SUBSTITUTION LADDER -- the certified "
                   "v3 in-place mechanism on a Revit-2025 base, constructors passed "
                   "through rvt.genesis.port2025)")
    m["viewer_certification"] = (
        "PENDING -- the Autodesk viewer session is signed out.  EVERY entry in this "
        "manifest (including the base and the control) is STAGED, NOT certified: no "
        "Revit-2025 file has ever been uploaded.  Upload when the session returns, "
        "control first.")
    m["base_2025"] = {
        "file": os.path.relpath(base_path, ROOT), "resolved_as": base_how,
        "certification": ("PENDING (built with --allow-uncertified; the batch law "
                          "still holds: the base itself is the staged control, and "
                          "if the control fails the whole batch is VOID)"),
    }
    m["round_1_reading"] = (
        "The control (the untouched 2025 base) answers TWO questions at once: "
        "(a) does the Autodesk viewer accept Revit-2025 uploads at all "
        "(genesis-2025-plan.md section 7 risk #1), and (b) is this base sound.  "
        "Control FAIL with 2026 controls passing = the viewer rejects 2025 uploads "
        "-- the campaign needs a different oracle, and NOTHING about the rungs is "
        "read from the batch.")
    with open(p, "w") as fh:
        json.dump(m, fh, indent=1)
    print(f"[probes] stamped {os.path.relpath(p, ROOT)} with the 2025 campaign truth")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base", default="", help="explicit 2025 base (default: poll "
                                               "for the reduce2025 stream's output)")
    ap.add_argument("--only", default="", help="comma list of rungs (passed to v3)")
    ap.add_argument("--no-ledger", action="store_true")
    args = ap.parse_args(argv)

    base, how = resolve_base(args.base)
    print(f"[base-2025] {os.path.relpath(base, ROOT)}")
    print(f"[base-2025] resolved as: {how}")
    print("[base-2025] viewer certification: PENDING (no 2025 file has ever been "
          "uploaded; --allow-uncertified recorded; the base doubles as the "
          "round-1 control)")

    import genesis_substitute_v3 as V3
    v3_args = ["--base", base, "--out-dir", OUT_DIR, "--allow-uncertified"]
    if args.only:
        v3_args += ["--only", args.only]
    if args.no_ledger:
        v3_args += ["--no-ledger"]
    with port2025_run_context(base):
        rc = V3.main(v3_args)
    stamp_probes_manifest(base, how)
    return rc


if __name__ == "__main__":
    sys.exit(main())
