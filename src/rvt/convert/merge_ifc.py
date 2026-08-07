"""rvt.convert.merge_ifc -- COMBINATION ROUTE (2): IFC + RVT -> RVT (merge).

An authored IFC (a Design-exported electrical room, a fixture layout) is
MERGED into an existing project: the IFC is resolved to the placement-true
intent by the certified resolver (:func:`rvt.ifc.intent.resolve_intent` --
world-baked positions, Pset tagging-contract join, feeder tree, our family
mapping), the whole intent is TRANSLATED by a disjoint offset so nothing
collides with the target's existing content, and the shared
build-into-target engine appends it: walls appended, families generated
zero-donor + loaded four-registry, instances placed at the intent's frames.

The offset is DETERMINISTIC and recorded: default = the incoming content
lands just east of the target's content bounding box (+ margin, y-centred);
``--offset DX DY`` (metres) overrides.  ``--offset 0 0`` merges in place
(the IFC's own world coordinates).

Everything else -- release preservation, target-schema installation, the
walls+families open-bug degrade, the stamps, the manifest -- is the shared
engine's behaviour (see :mod:`rvt.convert.add_to_project`).

Territory: ``src/rvt/convert/`` (convert-B stream).
"""
from __future__ import annotations

import argparse
import os
import traceback
from typing import Any, Dict, Optional, Sequence

from ..frontdoor import intent as FI
from .add_to_project import (ConvertError, auto_offset_m, build_into_target,
                             model_bbox_m, resolve_level, resolve_target,
                             translate_model, write_convert_manifest, _jdump,
                             M_PER_FT)

__all__ = ["merge_ifc", "main"]


def merge_ifc(ifc_path: str, target_path: str, out_dir: str, *,
              offset: Optional[Sequence[float]] = None, margin_m: float = 3.0,
              level: Optional[str] = None, strict: bool = False,
              stem: Optional[str] = None, validate: bool = True) -> Dict[str, Any]:
    """IFC + RVT -> RVT.  Resolve, offset disjointly, append, deliver."""
    if not os.path.isfile(ifc_path):
        raise ConvertError(f"IFC file not found: {ifc_path}")
    target = resolve_target(target_path)
    model = FI.intent_from_ifc(ifc_path)

    lvl_id, lvl_elev_ft = resolve_level(target, level)
    if offset is not None and len(offset) >= 2:
        dx, dy = float(offset[0]), float(offset[1])
        rule = f"explicit --offset ({dx}, {dy}) m"
    else:
        dx, dy = auto_offset_m(target, model, margin_m=margin_m)
        rule = (f"auto-disjoint: incoming content east of the target's bbox "
                f"(+{margin_m} m margin, y-centred)")
    incoming_bbox = model_bbox_m(model)
    shift = translate_model(model, dx, dy, equip_dz_m=lvl_elev_ft * M_PER_FT)

    stem = stem or (os.path.splitext(os.path.basename(ifc_path))[0] + ".merged")
    rec = build_into_target(model, target, out_dir, stem=stem, strict=strict,
                            level=level, validate=validate)
    rec["route"] = "ifc+rvt->rvt merge (rvt.convert.merge_ifc)"
    rec["ifc"] = {"path": ifc_path,
                  "bytes": os.path.getsize(ifc_path),
                  "resolved_equipment": len(model.equipment),
                  "resolved_walls": len(model.room.walls) if model.room else 0,
                  "incoming_bbox_pre_offset_m": incoming_bbox}
    rec["placement"] = {"rule": rule, "offset": shift,
                        "level": {"id": lvl_id, "elevation_ft": lvl_elev_ft},
                        "hosting": ("free-standing placement at the intent's frames "
                                    "(certified shape); face-hosting follow-up")}
    rec["created_ids"] = sorted({int(c["elem_id"]) for c in rec.get("created") or []
                                 if c.get("elem_id") is not None}
                                | {int(c["symbol_id"]) for c in rec.get("created") or []
                                   if c.get("symbol_id") is not None}
                                | {int(c["family_id"]) for c in rec.get("created") or []
                                   if c.get("family_id") is not None})
    rec["intent_summary"] = FI.summarize(model)
    try:
        FI.write_intent_json(model, os.path.join(out_dir, "intent.json"))
    except Exception as e:                                     # noqa: BLE001
        _jdump(os.path.join(out_dir, "intent.json"),
               {"summary": rec["intent_summary"],
                "note": f"full intent dump unavailable: {type(e).__name__}: {e}"})
    write_convert_manifest(rec, out_dir)
    return rec


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="rvt.convert.merge_ifc",
        description="IFC + RVT -> RVT: merge an authored IFC into an existing "
                    "project at a disjoint offset (the combination route).")
    ap.add_argument("ifc", help="the .ifc to merge in")
    ap.add_argument("target", help="the existing .rvt to merge into")
    ap.add_argument("-o", "--out-dir", required=True)
    ap.add_argument("--offset", type=float, nargs=2, metavar=("DX_M", "DY_M"),
                    help="explicit offset in metres (0 0 = merge in place)")
    ap.add_argument("--margin", type=float, default=3.0,
                    help="auto-offset margin in metres (default 3)")
    ap.add_argument("--level", default=None,
                    help="target level: 1-based story index or name substring")
    ap.add_argument("--stem", default=None)
    ap.add_argument("--strict", action="store_true",
                    help="walls+families open bug -> two coordinated files")
    ap.add_argument("--no-validate", action="store_true")
    a = ap.parse_args(argv)
    try:
        rec = merge_ifc(a.ifc, a.target, a.out_dir, offset=a.offset,
                        margin_m=a.margin, level=a.level, strict=a.strict,
                        stem=a.stem, validate=not a.no_validate)
    except (ConvertError, Exception) as e:                     # noqa: BLE001
        if not isinstance(e, ConvertError):
            traceback.print_exc(limit=6)
        print(f"REFUSED/FAILED: {e}")
        return 2
    files = rec.get("deliverables") or {}
    print(f"delivered {len(files)} file(s):")
    for role, d in files.items():
        print(f"  {role}: {d['path']} ({d['bytes']:,} bytes)")
    print(f"  created ids: {rec.get('created_ids')}")
    for s in rec.get("stamps") or []:
        print(f"  STAMP: {s}")
    for d in (rec.get("degradations") or [])[:8]:
        print(f"  caveat: {d}")
    ok = bool(files) and all(
        (g.get("validate") or {}).get("verdict") == "VALID"
        for g in (rec.get("validation") or {}).values())
    return 0 if ok else 1


if __name__ == "__main__":                                    # pragma: no cover
    raise SystemExit(main())
