#!/usr/bin/env python
"""emission_check.py -- THE FIVE-GATE EMISSION CHECK for a release-targeted
front-door output (build-2025 stream).

A file authored for ``--target-version <year>`` passes when ALL FIVE hold:

  G1  identity      BasicFileInfo Format == the target year (rvt.versions
                    .detect_release reads exactly that) and the build string
                    is present;
  G2  schema        the schema aboard (Formats/Latest) is BYTE-IDENTICAL to
                    the pinned per-release schema (KNOWN_RELEASES[year]
                    .schema_sha256);
  G3  framing       every Partitions stream walks CLEAN under the target
                    release's ordinals (every block/trailer/footer tag
                    accounted), AND the same walk under the NATIVE (default-
                    release) ordinals FAILS -- the file carries ONLY the
                    target framing on disk, no native-release tags;
  G4  validator     rvt.validate reports ZERO errors with the target
                    release's reading context active;
  G5  registries    the four-registry census is coherent (save_units - 1 ==
                    ContentDocuments entries == ContentTable records) and
                    the ADocument decodes clean.

This is the ladder's per-rung acceptance posture (genesis_substitute_v3's
problems list) restated for a FRESH-BUILD output, where the substitution-
only gates (byte-delta / Latest parity) have no meaning.

Usage:
    .venv/bin/python experiments/frontdoor2025/emission_check.py <file.rvt> [year]

Exit 0 = all gates PASS.  Also importable: ``check_emission(path, year)``.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from typing import Any, Dict, Optional

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

import rvt.versions as V                                    # noqa: E402
from rvt.frontdoor import release_ctx as RC                 # noqa: E402


def _load_tool(name: str):
    p = os.path.join(ROOT, "tools", f"{name}.py")
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _walk_all_partitions(path: str) -> Dict[str, Any]:
    """Walk every Partitions stream with WHATEVER ordinals are currently
    active; returns per-stream {blocks, units, errors} or the raised error."""
    from rvt.container import open_rvt
    from rvt.partitions import StreamWalker
    out: Dict[str, Any] = {"streams": {}, "ok": True, "raised": None}
    try:
        with open_rvt(path) as f:
            for pn in f.partition_streams():
                w = StreamWalker(f.logical(pn), inflate=True, keep_data=False)
                out["streams"][pn] = {"blocks": len(w.blocks),
                                      "units": len(w.units),
                                      "errors": list(w.errors)[:4]}
                if w.errors:
                    out["ok"] = False
    except Exception as e:                                   # noqa: BLE001
        out["ok"] = False
        out["raised"] = f"{type(e).__name__}: {e}"
    return out


def check_emission(path: str, year: Optional[int] = None) -> Dict[str, Any]:
    path = os.path.abspath(path)
    detected = V.detect_release(path)
    year = int(year or detected or 0)
    rel = V.KNOWN_RELEASES.get(year)
    rep: Dict[str, Any] = {"file": os.path.relpath(path, ROOT), "year": year,
                           "bytes": os.path.getsize(path), "gates": {}}
    if rel is None:
        rep["gates"]["G1_identity"] = {"pass": False,
                                       "why": f"unknown release {year}"}
        rep["pass"] = False
        return rep

    # G1 -- identity (BasicFileInfo)
    from rvt.container import open_rvt
    from rvt import stream_encoders as SE
    with open_rvt(path) as f:
        bfi = SE.decode_basic_file_info(f.raw("BasicFileInfo"))
    g1 = {"detect_release": detected, "format": bfi.get("format"),
          "build": bfi.get("build"),
          "pass": bool(detected == year and str(year) in str(bfi.get("format"))
                       and bfi.get("build"))}
    rep["gates"]["G1_identity"] = g1

    # G2 -- the pinned schema aboard
    s = V.schema_of(path)
    got = s.stats()["sha256"]
    g2 = {"schema_sha256": got, "pinned": rel.schema_sha256,
          "pass": bool(got == rel.schema_sha256)}
    rep["gates"]["G2_schema"] = g2

    # G3 -- framing: clean under the target ordinals, REFUSED under native
    with V.reading(path):
        target_walk = _walk_all_partitions(path)
    native = RC.native_release()
    if year == native:
        native_walk = {"skipped": "target IS the native release"}
        native_fails = True
    else:
        native_walk = _walk_all_partitions(path)         # native ordinals
        native_fails = not native_walk["ok"]
    g3 = {"target_walk": target_walk,
          "native_walk_must_fail": {"native": native,
                                    "failed": native_fails,
                                    "how": native_walk.get("raised")
                                    or [s.get("errors") for s in
                                        (native_walk.get("streams") or {}).values()
                                        if s.get("errors")][:1]},
          "pass": bool(target_walk["ok"] and native_fails)}
    rep["gates"]["G3_framing"] = g3

    # G4 + G5 need the FULL build context (codecs, not just framing) when the
    # file is a non-native release
    def _g45() -> Dict[str, Any]:
        import rvt.validate as VAL
        out: Dict[str, Any] = {}
        vrep = VAL.validate_file(path)                  # rvt.validate.Report
        errs = list(vrep.errors)
        out["G4_validator"] = {"verdict": "VALID" if vrep.ok else "INVALID",
                               "errors": len(errs),
                               "warnings": len(vrep.warnings),
                               "error_messages": [f"{f.where}: {f.message}"
                                                  for f in errs[:4]],
                               "pass": bool(vrep.ok and not errs)}
        GT = _load_tool("genesis_triage")
        cen = GT.census(path)
        su, cd, ct = (cen.get("save_units"), cen.get("contentdocs_entries"),
                      cen.get("contenttable_records"))
        coherent = (su is not None and cd is not None and ct is not None
                    and (su - 1) == cd == ct)
        out["G5_registries"] = {"save_units": su, "contentdocs_entries": cd,
                                "contenttable_records": ct,
                                "familymgr_entries": cen.get("familymgr_entries"),
                                "adocument_clean": cen.get("adocument_clean"),
                                "pass": bool(coherent and cen.get("adocument_clean"))}
        return out

    if year == native:
        with V.reading(path):
            rep["gates"].update(_g45())
    else:
        with RC.release_build_context(path):
            rep["gates"].update(_g45())

    rep["pass"] = all(g.get("pass") for g in rep["gates"].values())
    return rep


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__)
        return 2
    path = argv[0]
    year = int(argv[1]) if len(argv) > 1 else None
    rep = check_emission(path, year)
    print(json.dumps(rep, indent=1, default=str))
    print(f"[emission-check] {rep['file']} year={rep['year']} -> "
          + ("ALL FIVE GATES PASS" if rep["pass"] else "FAIL"))
    return 0 if rep["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
