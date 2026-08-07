"""rvt.convert.add_to_project -- COMBINATION ROUTE (1): prompt + RVT -> RVT.

"Add a 100 A lighting panel to my project."  The prompt is parsed by the
EXISTING front-door vocabulary (:func:`rvt.frontdoor.prompt_intent
.prompt_to_intent` -- rules-first, deterministic, no external model call),
and the resulting intent is built INTO THE USER'S OWN FILE instead of the
genesis base, composing three already-proven paths:

* M2_rac (viewer-certified) proved rvt.manipulate EDITS a foreign file;
* L1a (viewer-certified) proved the four-registry family LOAD into a
  foreign working project; stage_L8_lp4 (viewer-certified) proved load +
  placement on our own base;
* V23..V29 / H1 / H2 (viewer-certified) proved instance placement and the
  wall-add path with clone-template scaffolding.

THE TARGET IS THE AUTHORITY:

* RELEASE  -- detected via :mod:`rvt.versions`; the output is a splice of
  the input, so it STAYS the input's release by construction (verified
  after the write and recorded).  Creation into a release without certified
  format data is REFUSED with :func:`rvt.versions.creation_status`'s honest
  reason -- never a silent newer-release file the user's Revit cannot open.
* SCHEMA   -- the target's own embedded ``Formats/Latest`` is installed at
  the codec chokepoints (:func:`rvt.frontdoor.standalone.install_schema`);
  a schema that differs from the installed one fails RED.
* LEVELS   -- placement lands on the target's OWN level (``--level`` picks
  by 1-based story index or name; default = the building story nearest
  elevation 0), with the level's real elevation folded into the placement.
* WALLS / CONTENT -- the target's walls and instances are surveyed into a
  content bounding box; new equipment lands in FREE FLOOR SPACE just
  outside it (or at an explicit ``--at X,Y``), free-standing, wall panels
  upright -- the certified free-standing placement shape.  Face-hosting on
  the target's walls (the H1 recipe) is the fidelity follow-up, recorded
  per run.

ZERO DONORS: generated families come from the facts store with the
bundled-base container (:func:`rvt.famgen.factory.FamilyProduct.write` is
standalone by default); placement scaffolding is CONSTRUCTED
(:class:`rvt.frontdoor.standalone.ConstructedSpecimens` built against the
TARGET's own schema/levels/phases) -- nothing is cloned from any
Autodesk-authored element.

THE DELIVERABLE RULE: gates are labels.  Every run that can produce a file
DELIVERS it, with the honest stamps after: the P0 PROOF-ONLY stamp, the
walls+families open-bug stamp when this run creates that combination, and a
QUARANTINED-TARGET stamp when the target is an Autodesk sample (dev-only
proof, never shipped).

Territory: ``src/rvt/convert/`` (convert-B stream).  Imports, never edits:
rvt.frontdoor.{prompt_intent,intent,standalone,build,base,manifest},
tools/ifc_intent.py (module), rvt.{mutate,versions,validate,famload}.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import time
import traceback
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .. import versions as V
from ..frontdoor import intent as FI
from ..frontdoor import standalone as SA
from ..frontdoor.base import is_autodesk_sample, repo_root
from ..frontdoor.build import load_ifc_room_module

__all__ = [
    "ConvertError", "TargetInfo", "resolve_target", "resolve_level",
    "translate_model", "model_bbox_m", "auto_offset_m",
    "build_into_target", "add_to_project", "write_convert_manifest", "main",
]

FT_PER_M = 3.280839895013123
M_PER_FT = 0.3048

TOOL = "tekton convert (rvt.convert)"
TOOL_VERSION = "1.0.0"

#: the P0 stamp every output carries until G2/G3 clear (TRACKER P0)
P0_STAMP = ("PROOF-ONLY, NOT-DELIVERABLE (P0: identity/counsel gates G2-G3 "
            "open; every tekton output is an internal proof)")

QUARANTINE_STAMP = ("QUARANTINED TARGET (dev-only proof): the target file is an "
                    "Autodesk sample standing in for a user upload; this output "
                    "exists to PROVE the route and is never shipped or "
                    "redistributed")


class ConvertError(RuntimeError):
    """The combination route cannot run; the message names the ONE reason."""


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def _relp(p: Optional[str]) -> Optional[str]:
    if not p:
        return None
    try:
        r = os.path.relpath(p, repo_root())
        return r if not r.startswith("..") else os.path.abspath(p)
    except ValueError:
        return os.path.abspath(p)


def _sha256(path: str, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _jdump(path: str, obj: Any) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=1, default=str)
    return path


def quarantined_input(path: str) -> bool:
    """True when ``path`` is third-party/sample content standing in for a
    user upload: dev-only proof territory, never shipped.  Wider than
    :func:`rvt.frontdoor.base.is_autodesk_sample` -- the repo's ``vendor/``
    tree counts too."""
    if is_autodesk_sample(path):
        return True
    ap = os.path.abspath(path)
    for sub in ("vendor", "samples"):
        if ap.startswith(os.path.join(os.path.abspath(repo_root()), sub) + os.sep):
            return True
    return False


# ---------------------------------------------------------------------------
# the TARGET: release + schema + levels + walls + content extents
# ---------------------------------------------------------------------------

@dataclass
class TargetInfo:
    """Everything the combination routes need to know about the user's file."""
    path: str
    release: Optional[int]
    release_supported: bool
    schema_sha256: Optional[str]
    quarantined: bool                      # Autodesk sample => dev-only proof
    levels: List[dict] = dc_field(default_factory=list)
    n_walls: int = 0
    n_instances: int = 0
    n_family_docs: int = 0
    wall_types: List[int] = dc_field(default_factory=list)
    bbox_m: Optional[Dict[str, List[float]]] = None    # {"x":[lo,hi],"y":[..],"z":[..]}
    watermark: int = 0
    doc: Any = None                        # rvt.mutate.Document (not serialised)
    notes: List[str] = dc_field(default_factory=list)

    def as_json(self) -> Dict[str, Any]:
        return {
            "path": _relp(self.path), "sha256": _sha256(self.path),
            "bytes": os.path.getsize(self.path),
            "release": self.release, "release_supported": self.release_supported,
            "schema_sha256": self.schema_sha256, "quarantined": self.quarantined,
            "levels": self.levels, "n_walls": self.n_walls,
            "n_instances": self.n_instances, "n_family_docs": self.n_family_docs,
            "wall_types": self.wall_types[:8], "bbox_m": self.bbox_m,
            "watermark": self.watermark, "notes": list(self.notes),
        }


def ensure_target_schema(target_path: str) -> Dict[str, Any]:
    """Install the TARGET's own embedded schema at the codec chokepoints, or
    verify the already-installed schema is byte-identical to the target's.
    Different bytes = a different release's class map => fail RED.

    The state must be read BEFORE calling ``install_schema``: its
    ``bundled_schema`` step re-parses the new path into the shared state
    (overwriting the recorded sha) while the encoder/decoder SINGLETONS stay
    on the first-installed schema -- comparing afterwards would always pass.
    """
    from ..container import open_rvt
    with open_rvt(target_path) as f:
        blob = f.inflate("Formats/Latest", 0)
    digest = hashlib.sha256(blob).hexdigest()
    prev = dict(getattr(SA, "_SCHEMA_STATE", None) or {})
    if prev.get("installed") and prev.get("sha256") and prev["sha256"] != digest:
        raise ConvertError(
            f"the target's embedded schema ({digest[:16]}...) differs from the "
            f"schema already installed in this process ({prev['sha256'][:16]}...): "
            "class ordinals are per-release and cannot be mixed. Run this "
            "route in a fresh process, or convert the target with its own "
            "release's fleet.")
    rep = SA.install_schema(target_path)
    rep["target_schema_sha256"] = digest
    return rep


def _wall_span_ft(v: dict) -> Optional[Tuple[float, float, float, float]]:
    """(x0, y0, x1, y1) feet of an SWall's location line, from its own
    VWallDriver GLine (origin + direction + end params)."""
    drv = ((v.get("m_pCurveDriver") or {}).get("value") or {})
    crv = ((drv.get("m_pCrv") or {}).get("value") or {})
    org = crv.get("m_origin")
    dirv = crv.get("m_dirVec")
    par = crv.get("m_endParams")
    if not (isinstance(org, list) and isinstance(dirv, list)
            and isinstance(par, list) and len(par) >= 2):
        return None
    x0 = float(org[0]) + float(dirv[0]) * float(par[0])
    y0 = float(org[1]) + float(dirv[1]) * float(par[0])
    x1 = float(org[0]) + float(dirv[0]) * float(par[1])
    y1 = float(org[1]) + float(dirv[1]) * float(par[1])
    return x0, y0, x1, y1


def resolve_target(path: str, *, survey_limit: int = 4000) -> TargetInfo:
    """Open the user's file and survey what the routes need: release
    (rvt.versions), schema identity, levels, wall/instance census and the
    content bounding box (metres) that placement stays clear of."""
    if not os.path.isfile(path):
        raise ConvertError(f"target file not found: {path}")
    release = V.detect_release(path)
    info = TargetInfo(
        path=os.path.abspath(path), release=release,
        release_supported=bool(release in V.SUPPORTED_CREATION_RELEASES),
        schema_sha256=None, quarantined=quarantined_input(path))
    if release is None:
        info.notes.append("release could not be detected from BasicFileInfo/schema")
    schema_rep = ensure_target_schema(info.path)
    info.schema_sha256 = schema_rep.get("target_schema_sha256")

    from ..mutate import Document
    doc = Document.from_file(info.path)
    info.doc = doc
    info.levels = doc.levels()
    info.watermark = max((int(doc.et.footer.last_id) if doc.et.footer else 0),
                         max(doc.et_by_id) if doc.et_by_id else 0)
    lo = [float("inf")] * 3
    hi = [float("-inf")] * 3

    def eat(x: float, y: float, z: float = 0.0) -> None:
        for i, v in enumerate((x, y, z)):
            lo[i] = min(lo[i], v)
            hi[i] = max(hi[i], v)

    wall_ids = doc.ids_of_class("SWall")
    info.n_walls = len(wall_ids)
    for wid in wall_ids[:survey_limit]:
        span = _wall_span_ft(doc.value(wid) or {})
        if span:
            eat(span[0], span[1])
            eat(span[2], span[3])
    inst_ids = doc.ids_of_class("FamilyInstance")
    info.n_instances = len(inst_ids)
    for iid in inst_ids[:survey_limit]:
        v = doc.value(iid) or {}
        tr = (((v.get("m_pInstanceInfo") or {}).get("value") or {})
              .get("m_Trf") or {})
        orx = tr.get("m_or")
        if isinstance(orx, list) and len(orx) == 3:
            eat(float(orx[0]), float(orx[1]), float(orx[2]))
    info.wall_types = [int(i) for i in doc.ids_of_class("BasicWallType")]
    try:
        from ..families import family_documents
        info.n_family_docs = sum(1 for r in family_documents(info.path)
                                 if r.get("unit") is not None)
    except Exception as e:                                     # noqa: BLE001
        info.notes.append(f"family-document census unavailable: {type(e).__name__}: {e}")
    if lo[0] < hi[0]:
        info.bbox_m = {"x": [round(lo[0] * M_PER_FT, 3), round(hi[0] * M_PER_FT, 3)],
                       "y": [round(lo[1] * M_PER_FT, 3), round(hi[1] * M_PER_FT, 3)],
                       "z": [round(lo[2] * M_PER_FT, 3), round(hi[2] * M_PER_FT, 3)]}
    else:
        info.notes.append("no walls/instances surveyed: content bbox unknown "
                          "(placement anchors at the origin)")
    return info


def resolve_level(info: TargetInfo, want: Optional[str] = None) -> Tuple[int, float]:
    """Pick the TARGET's level to place on: ``want`` = 1-based story index
    ('2'), a level name (substring, case-insensitive), or None (the building
    story nearest elevation 0).  Returns ``(level_id, elevation_ft)``."""
    lv = info.levels
    if not lv:
        raise ConvertError("the target carries no Level element to place on")
    stories = [l for l in lv if l.get("is_building_story")] or lv
    stories = sorted(stories, key=lambda l: float(l.get("elevation_ft", 0.0)))
    if want not in (None, ""):
        w = str(want).strip()
        if w.isdigit():
            k = int(w)
            if not (1 <= k <= len(stories)):
                raise ConvertError(
                    f"--level {k} out of range: the target has {len(stories)} "
                    f"building stories ({', '.join(str(s.get('name')) for s in stories)})")
            pick = stories[k - 1]
        else:
            hits = [l for l in lv if w.lower() in str(l.get("name", "")).lower()]
            if len(hits) != 1:
                raise ConvertError(
                    f"--level {want!r} matches {len(hits)} target levels "
                    f"({[h.get('name') for h in hits][:6]}): give a unique name or index")
            pick = hits[0]
    else:
        pick = min(stories, key=lambda l: abs(float(l.get("elevation_ft", 0.0))))
    return int(pick["id"]), float(pick.get("elevation_ft", 0.0))


# ---------------------------------------------------------------------------
# intent geometry: bbox / translation / disjoint offset
# ---------------------------------------------------------------------------

def model_bbox_m(model: FI.IntentModel) -> Optional[Dict[str, List[float]]]:
    """XY bounding box (metres) of an intent's walls + equipment footprints."""
    lo = [float("inf")] * 2
    hi = [float("-inf")] * 2

    def eat(x: float, y: float) -> None:
        lo[0] = min(lo[0], x); hi[0] = max(hi[0], x)          # noqa: E702
        lo[1] = min(lo[1], y); hi[1] = max(hi[1], y)          # noqa: E702

    for eq in model.equipment:
        w = float((eq.dims_m or {}).get("w", 0.6)) / 2.0
        d = float((eq.dims_m or {}).get("d", 0.6)) / 2.0
        r = max(w, d)
        eat(eq.insertion_m[0] - r, eq.insertion_m[1] - r)
        eat(eq.insertion_m[0] + r, eq.insertion_m[1] + r)
    if model.room:
        for wl in model.room.walls:
            eat(float(wl.p0_m[0]), float(wl.p0_m[1]))
            eat(float(wl.p1_m[0]), float(wl.p1_m[1]))
    if lo[0] > hi[0]:
        return None
    return {"x": [round(lo[0], 3), round(hi[0], 3)], "y": [round(lo[1], 3), round(hi[1], 3)]}


def auto_offset_m(target: TargetInfo, model: FI.IntentModel,
                  *, margin_m: float = 3.0) -> Tuple[float, float]:
    """The deterministic DISJOINT offset: the incoming intent lands just EAST
    of the target's content bbox (max x + margin), centred on the target's
    y extent.  (0, 0) when either bbox is unknown."""
    mb = model_bbox_m(model)
    tb = target.bbox_m
    if not mb or not tb:
        return 0.0, 0.0
    dx = float(tb["x"][1]) - float(mb["x"][0]) + float(margin_m)
    ty_c = (float(tb["y"][0]) + float(tb["y"][1])) / 2.0
    my_c = (float(mb["y"][0]) + float(mb["y"][1])) / 2.0
    dy = ty_c - my_c
    return round(dx, 3), round(dy, 3)


def translate_model(model: FI.IntentModel, dx_m: float, dy_m: float,
                    equip_dz_m: float = 0.0) -> Dict[str, Any]:
    """Translate the WHOLE intent horizontally (+ the equipment vertically by
    the target level's elevation).  Walls sit ON their level, so only the
    equipment carries the z shift."""
    n_eq = 0
    for eq in model.equipment:
        eq.insertion_m = [float(eq.insertion_m[0]) + dx_m,
                          float(eq.insertion_m[1]) + dy_m,
                          float(eq.insertion_m[2]) + equip_dz_m]
        if isinstance(getattr(eq, "elevation_m", None), (int, float)):
            eq.elevation_m = float(eq.elevation_m) + equip_dz_m
        n_eq += 1
    n_w = 0
    if model.room:
        for wl in model.room.walls:
            wl.p0_m = [float(wl.p0_m[0]) + dx_m, float(wl.p0_m[1]) + dy_m]
            wl.p1_m = [float(wl.p1_m[0]) + dx_m, float(wl.p1_m[1]) + dy_m]
            n_w += 1
        ext = (model.room.clear or {}).get("centerline_extents_m")
        if isinstance(ext, dict):
            ext["x"] = [float(ext["x"][0]) + dx_m, float(ext["x"][1]) + dx_m]
            ext["y"] = [float(ext["y"][0]) + dy_m, float(ext["y"][1]) + dy_m]
    rec = {"dx_m": round(dx_m, 3), "dy_m": round(dy_m, 3),
           "equip_dz_m": round(equip_dz_m, 3),
           "equipment_translated": n_eq, "walls_translated": n_w,
           "note": ("clearance boxes / conduit runs (informational layers) are "
                    "NOT translated; positions in the manifest are post-offset")}
    model.notes.append(f"convert: intent translated by ({rec['dx_m']}, {rec['dy_m']}) m "
                       f"(+{rec['equip_dz_m']} m equipment z) into the target's frame")
    return rec


# ---------------------------------------------------------------------------
# THE BUILD INTO AN EXISTING FILE (families -> load -> walls -> instances -> gates)
# ---------------------------------------------------------------------------

def build_into_target(model: FI.IntentModel, target: TargetInfo, out_dir: str,
                      *, stem: str = "combined", strict: bool = False,
                      level: Optional[str] = None, validate: bool = True,
                      wall_mode: str = "min",
                      symbol_solid: bool = True) -> Dict[str, Any]:
    """Author ``model`` INTO ``target`` -- the shared engine of the
    prompt+RVT and IFC+RVT routes.

    Stage order (each = the certified stage code from ``tools/ifc_intent.py``,
    loaded as a module, pointed at the TARGET instead of the genesis base):

      F  generate the .rfa deliverables (zero-donor, bundled-base container);
      L  four-registry LOAD of each family into the target (chained);
      W  append the intent's walls (clone of a CONSTRUCTED SWall template
         built against the target's own wall type / level / phase);
      E  place one instance per loaded family at the intent's frames;
      V  gates per output: rvt.validate (0 errors required to claim the
         cell), four-registry census, release-preservation check.

    The walls+families OPEN BUG degrade applies exactly as in the front
    door: ``--strict`` emits two coordinated files (shell / equipment), the
    default emits ONE stamped combined file.  Returns the full record;
    ``record['files']`` maps role -> path (the deliverables)."""
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    stages_dir = os.path.join(out_dir, "_stages")
    os.makedirs(stages_dir, exist_ok=True)
    R = load_ifc_room_module()

    rec: Dict[str, Any] = {
        "engine": "rvt.convert.build_into_target",
        "target": target.as_json(), "files": {}, "stages": [],
        "created": [], "degradations": [], "errors": [], "validation": {},
        "stamps": [P0_STAMP],
    }
    if target.quarantined:
        rec["stamps"].append(QUARANTINE_STAMP)

    # release guard: creating records for a release without certified format
    # data is refused with the version model's own honest reason
    if target.release is None or not target.release_supported:
        st = V.creation_status(target.release) if target.release else None
        raise ConvertError(
            "cannot author into this target: "
            + (st["reason"] if st else "its release could not be detected")
            + f". Certified creation releases today: {sorted(V.SUPPORTED_CREATION_RELEASES)}; "
              "the per-release fleets are bringing the others up.")

    lvl_id, lvl_elev_ft = resolve_level(target, level)
    rec["level"] = {"id": lvl_id, "elevation_ft": lvl_elev_ft,
                    "requested": level or "(nearest elevation 0)"}

    # ---- degrade decision (the walls+families open bug) -------------------
    verdict = FI.combination_check(model, strict=strict)
    rec["verdict"] = verdict.as_json()
    plans = FI.buildable_family_plans(model)
    want_walls = verdict.n_walls > 0
    want_fams = len(plans) > 0
    for p in (model.family_plans or []):
        if p.status not in ("resolved", "house"):
            rec["degradations"].append(
                f"{p.tag} ({p.kind}): NOT built -- family plan {p.status}"
                + (f": {p.refusal}" if p.refusal else ""))
    if not want_walls and not want_fams:
        raise ConvertError("the intent has nothing buildable: no walls and no "
                           "loadable family plans (see degradations)")
    if want_fams and target.n_walls > 0 and not want_walls:
        rec["degradations"].append(
            "note: the target already carries walls; THIS RUN creates none, so "
            "loading our families into it is the certified load-into-a-walled-host "
            "shape (L1a foreign-host precedent), not the created-walls+loaded-"
            "families open-bug combination")

    # ---- F: the .rfa deliverables ----------------------------------------
    frec = R.stage_families(model, out_dir)
    rec["families"] = {k: v for k, v in frec.items()}
    rec["stages"].append({"stage": "F", "built": frec.get("built"),
                          "all_ok": frec.get("all_ok"), "dir": frec.get("dir")})
    rec["files"]["families_dir"] = os.path.join(out_dir, "families")
    for f in frec.get("families") or []:
        if f.get("built"):
            rec["created"].append({"kind": "family(.rfa)", "tag": f.get("tag"),
                                   "name": f.get("family_name"), "path": f.get("path"),
                                   "catalog": f.get("catalog"), "variant": f.get("variant"),
                                   "ok": f.get("ok")})

    # ---- L: load into the TARGET -----------------------------------------
    loaded: Dict[str, Any] = {}
    loaded_file: Optional[str] = None
    if want_fams:
        lrec = R.stage_load(model, target.path, stages_dir, symbol_solid=symbol_solid)
        loaded = lrec.pop("_loaded", {}) or {}
        lrec.pop("_products", None)
        loaded_file = lrec.pop("_current", None)
        rec["load"] = {k: v for k, v in lrec.items()}
        rec["stages"].append({"stage": "L", "n_loaded": lrec.get("n_loaded"),
                              "n_planned": lrec.get("n_planned"),
                              "final": lrec.get("final"), "blocker": lrec.get("blocker")})
        if lrec.get("blocker"):
            rec["degradations"].append(
                f"family LOAD blocked at {lrec.get('blocker')} -- proceeding with "
                f"{lrec.get('n_loaded')}/{lrec.get('n_planned')} loaded")
        if not loaded:
            loaded_file = None
            if want_walls:
                rec["degradations"].append("no family loaded -> walls only")
            else:
                raise ConvertError("no family could be loaded into the target and "
                                   "there are no walls to build "
                                   f"(first blocker: {lrec.get('blocker')})")
        if loaded_file == target.path:
            loaded_file = None

    # ---- specimens: CONSTRUCTED against the TARGET ------------------------
    specimens = None
    if want_walls or (loaded and loaded_file):
        specimens = SA.ConstructedSpecimens(SA.CONSTRUCTED, base_path=target.path)
        rec["stages"].append({"stage": "specimens", "source": "(constructed vs target)",
                              "wall": specimens.wall_id, "wall_type": specimens.wall_type,
                              "instance": specimens.instance_id})

    combined_path = os.path.join(out_dir, f"{stem}.rvt")
    shell_path = os.path.join(out_dir, f"{stem}-shell.rvt")
    equip_path = os.path.join(out_dir, f"{stem}-equipment.rvt")
    have_fams = bool(loaded) and bool(loaded_file)
    mode = verdict.mode
    if verdict.triggers_open_bug and not have_fams:
        mode = "single"
        rec["degradations"].append("walls+families collapsed to walls-only (nothing "
                                   "loaded) -- single proven-shaped file")
    rec["mode"] = mode

    def _walls(src: str, dst: str, label: str) -> Optional[str]:
        wrec, wok = R.stage_walls(model, src, dst, specimens,
                                  level_id=lvl_id, wall_mode=wall_mode)
        wrec["stage"] = label
        rec["stages"].append(_slim(wrec))
        if wok:
            for w in wrec.get("walls") or []:
                rec["created"].append({"kind": "wall", "tag": w.get("id"),
                                       "elem_id": w.get("elem_id"),
                                       "length_m": w.get("length_m"),
                                       "height_ft": w.get("height_ft"),
                                       "file_role": label})
            return dst
        rec["degradations"].append(f"{label}: walls NOT built: "
                                   + str(wrec.get("blocker") or wrec.get("error")))
        return None

    def _equip(src: str, dst: str, label: str) -> Optional[str]:
        erec, eok = R.stage_equipment(model, src, dst, specimens, loaded,
                                      level_id=lvl_id)
        erec["stage"] = label
        rec["stages"].append(_slim(erec))
        if eok:
            for i in erec.get("instances") or []:
                rec["created"].append({"kind": "equipment-instance", "tag": i.get("tag"),
                                       "elem_id": i.get("elem_id"),
                                       "symbol": i.get("symbol"), "family": i.get("family"),
                                       "position_ft": i.get("position_ft"),
                                       "file_role": label})
            for tag, infd in (loaded or {}).items():
                rec["created"].append({"kind": "loaded-family", "tag": tag,
                                       "symbol_id": infd.get("symbol_id"),
                                       "family_id": infd.get("family_id"),
                                       "content_guid": infd.get("content_guid")})
            return dst
        rec["degradations"].append(f"{label}: instances NOT placed: "
                                   + str(erec.get("blocker") or erec.get("error")))
        return None

    try:
        if mode == "split-strict":
            if want_walls and _walls(target.path, shell_path, "W(shell)"):
                rec["files"]["shell"] = shell_path
            if have_fams:
                if _equip(loaded_file, equip_path, "E(equipment)"):
                    rec["files"]["equipment"] = equip_path
                else:
                    shutil.copyfile(loaded_file, equip_path)
                    rec["files"]["equipment"] = equip_path
                    rec["degradations"].append("equipment file = the loaded chain "
                                               "(placement failed; families still loaded)")
        else:
            current: Optional[str] = None
            if want_walls:
                src = loaded_file if have_fams else target.path
                wtarget = (os.path.join(stages_dir, "stage_W_walls.rvt")
                           if have_fams else combined_path)
                current = _walls(src, wtarget, "W")
            if have_fams:
                src = current or loaded_file
                got = _equip(src, combined_path, "E")
                if got:
                    current = combined_path
                elif current and current != combined_path:
                    shutil.copyfile(current, combined_path)
                    current = combined_path
                elif current is None:
                    shutil.copyfile(loaded_file, combined_path)
                    current = combined_path
                    rec["degradations"].append("combined file = the loaded chain "
                                               "(placement failed; families still loaded)")
                    for tag, infd in (loaded or {}).items():
                        rec["created"].append({"kind": "loaded-family", "tag": tag,
                                               "symbol_id": infd.get("symbol_id"),
                                               "family_id": infd.get("family_id")})
            if current and os.path.abspath(current) != os.path.abspath(combined_path):
                shutil.copyfile(current, combined_path)
                current = combined_path
            if current:
                rec["files"]["combined"] = combined_path
    except Exception as e:                                     # noqa: BLE001
        rec["errors"].append(f"build crashed: {type(e).__name__}: {e}")
        rec["errors"].append(traceback.format_exc(limit=8))

    # ---- V: gates per emitted file (labels, never withholding) ------------
    if validate:
        for role in ("combined", "shell", "equipment"):
            p = rec["files"].get(role)
            if not p or not os.path.isfile(p):
                continue
            g: Dict[str, Any] = {}
            try:
                g["validate"] = R.validate_rvt(p)
            except Exception as e:                             # noqa: BLE001
                g["validate"] = {"verdict": "ERROR", "error": f"{type(e).__name__}: {e}"}
            try:
                g["census"] = R.registry_census(p)
            except Exception as e:                             # noqa: BLE001
                g["census"] = {"error": f"{type(e).__name__}: {e}"}
            out_rel = V.detect_release(p)
            g["release"] = {"input": target.release, "output": out_rel,
                            "preserved": bool(out_rel == target.release)}
            if not g["release"]["preserved"]:
                rec["errors"].append(f"{role}: OUTPUT RELEASE {out_rel} != input "
                                     f"{target.release} -- release preservation broken")
            g["self_checks_ok"] = bool(
                g["validate"].get("verdict") == "VALID"
                and g["census"].get("coherent") is not False
                and g["release"]["preserved"])
            rec["validation"][role] = g
        rec["identity_note"] = (
            "the output keeps the TARGET's own identity block (BasicFileInfo / "
            "history): this route EDITS the user's file, it does not re-author "
            "its identity; the P0 provenance gate does not apply a genesis-base "
            "ledger to a user-supplied target")
    rec["seconds"] = round(time.time() - t0, 1)
    return rec


def _slim(stage_rec: Dict[str, Any]) -> Dict[str, Any]:
    keep = ("stage", "ok", "in", "out", "wall_mode", "wall_type", "wall_type_name",
            "level", "elemtable_before", "elemtable_after", "new_ids", "verify",
            "structurally_valid", "seconds", "blocker", "error")
    out = {k: stage_rec.get(k) for k in keep if k in stage_rec}
    if stage_rec.get("walls"):
        out["walls"] = [{"id": w.get("id"), "elem_id": w.get("elem_id")}
                        for w in stage_rec["walls"]]
    if stage_rec.get("instances"):
        out["instances"] = [{"tag": i.get("tag"), "elem_id": i.get("elem_id"),
                             "symbol": i.get("symbol")}
                            for i in stage_rec["instances"]]
    return out


# ---------------------------------------------------------------------------
# ROUTE (1): prompt + RVT
# ---------------------------------------------------------------------------

def add_to_project(prompt: str, target_path: str, out_dir: str, *,
                   at: Optional[Sequence[float]] = None,
                   level: Optional[str] = None, margin_m: float = 1.0,
                   strict: bool = False, stem: Optional[str] = None,
                   validate: bool = True) -> Dict[str, Any]:
    """prompt + RVT -> RVT.  Parse ``prompt`` with the front-door vocabulary,
    retarget the intent onto the user's file, build into it, deliver.

    ``at`` = explicit anchor (metres, target world frame) for the new
    equipment; default = free floor space just outside the target's content
    bbox (east side, y-centred).  ``level`` picks the target level.
    """
    from ..frontdoor import prompt_intent as PI
    target = resolve_target(target_path)
    model, parsed = PI.prompt_to_intent(prompt)

    # placement: translate the prompt layout (origin-centred) to the anchor
    lvl_id, lvl_elev_ft = resolve_level(target, level)
    mb = model_bbox_m(model)
    if at is not None and len(at) >= 2:
        dx = float(at[0]) - (mb["x"][0] if mb else 0.0)
        dy = float(at[1]) - (mb["y"][0] if mb else 0.0)
        anchor_rule = f"explicit --at {list(map(float, at))} m (the addition's min corner)"
    else:
        dx, dy = auto_offset_m(target, model, margin_m=margin_m)
        anchor_rule = (f"free floor space east of the target's content bbox "
                       f"(+{margin_m} m margin, y-centred)")
    shift = translate_model(model, dx, dy, equip_dz_m=lvl_elev_ft * M_PER_FT)

    stem = stem or "add_to_project"
    rec = build_into_target(model, target, out_dir, stem=stem, strict=strict,
                            level=level, validate=validate)
    rec["route"] = "prompt+rvt->rvt (rvt.convert.add_to_project)"
    rec["prompt"] = parsed.prompt
    rec["prompt_coverage"] = parsed.coverage.as_json()
    rec["placement"] = {"rule": anchor_rule, "offset": shift,
                        "level": {"id": lvl_id, "elevation_ft": lvl_elev_ft},
                        "hosting": ("free-standing (certified shape); wall panels "
                                    "stand upright at panel height; FACE-HOSTING on "
                                    "the target's walls (H1 recipe) is the fidelity "
                                    "follow-up")}
    if any("level" in (c.get("clause") or "").lower()
           for c in parsed.coverage.understood):
        rec.setdefault("degradations", []).append(
            "a level/storey clause in the prompt is recorded but NOT used for "
            "target-level selection -- pass --level to pick the target's level")
    rec["intent_summary"] = FI.summarize(model)
    try:
        FI.write_intent_json(model, os.path.join(out_dir, "intent.json"))
    except Exception as e:                                     # noqa: BLE001
        _jdump(os.path.join(out_dir, "intent.json"),
               {"summary": rec["intent_summary"],
                "note": f"full intent dump unavailable: {type(e).__name__}: {e}"})
    write_convert_manifest(rec, out_dir)
    return rec


# ---------------------------------------------------------------------------
# the manifest (json + human)
# ---------------------------------------------------------------------------

def write_convert_manifest(rec: Dict[str, Any], out_dir: str) -> Dict[str, str]:
    """manifest.json + MANIFEST.md beside the outputs: the deliverable, the
    stamps, the caveats -- the file FIRST, the labels after."""
    rec.setdefault("tool", TOOL)
    rec.setdefault("tool_version", TOOL_VERSION)
    rec.setdefault("written_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    files = {k: v for k, v in (rec.get("files") or {}).items()
             if v and os.path.isfile(str(v))}
    rec["deliverables"] = {
        role: {"path": _relp(p), "bytes": os.path.getsize(p), "sha256": _sha256(p)}
        for role, p in files.items() if str(p).endswith(".rvt") or str(p).endswith(".rfa")}
    jp = _jdump(os.path.join(out_dir, "manifest.json"), rec)

    lines: List[str] = []
    lines.append(f"# {rec.get('route', 'rvt.convert')} -- deliverable manifest")
    lines.append("")
    lines.append("## The deliverable(s)")
    if rec["deliverables"]:
        for role, d in rec["deliverables"].items():
            lines.append(f"* **{role}**: `{d['path']}` ({d['bytes']:,} bytes, "
                         f"sha256 {d['sha256'][:16]}...)")
    else:
        lines.append("* NO FILE PRODUCED -- see errors below (the route failed "
                     "before an output existed; nothing was withheld)")
    lines.append("")
    lines.append("## Stamps (labels, not refusals)")
    for s in rec.get("stamps") or []:
        lines.append(f"* {s}")
    v = rec.get("verdict") or {}
    if v.get("stamp"):
        lines.append(f"* {v['stamp']}")
    lines.append("")
    tgt = rec.get("target") or {}
    lines.append("## Target")
    lines.append(f"* file: `{tgt.get('path')}` (Revit {tgt.get('release')}, "
                 f"{tgt.get('n_walls')} walls, {tgt.get('n_instances')} instances, "
                 f"{tgt.get('n_family_docs')} family documents)")
    lines.append(f"* release preserved: every output verified "
                 f"{'YES' if all((g.get('release') or {}).get('preserved') for g in (rec.get('validation') or {}).values()) else 'SEE VALIDATION'}"
                 " -- the output is a splice of the input, no version conversion")
    if rec.get("level"):
        lines.append(f"* placement level: id {rec['level'].get('id')} at "
                     f"{rec['level'].get('elevation_ft')} ft ({rec['level'].get('requested')})")
    lines.append("")
    if rec.get("placement"):
        lines.append("## Placement")
        lines.append(f"* rule: {rec['placement'].get('rule')}")
        lines.append(f"* offset: {json.dumps(rec['placement'].get('offset'))}")
        lines.append(f"* hosting: {rec['placement'].get('hosting')}")
        lines.append("")
    lines.append("## Created")
    for c in rec.get("created") or []:
        bits = ", ".join(f"{k}={v}" for k, v in c.items()
                         if k in ("tag", "elem_id", "symbol_id", "family_id", "name")
                         and v is not None)
        lines.append(f"* {c.get('kind')}: {bits}")
    lines.append("")
    lines.append("## Gates (self-checks; viewer acceptance is a separate tier)")
    for role, g in (rec.get("validation") or {}).items():
        val = g.get("validate") or {}
        cen = g.get("census") or {}
        rel = g.get("release") or {}
        lines.append(f"* {role}: validator {val.get('verdict')} "
                     f"({val.get('n_errors')} errors, {val.get('n_warnings')} warnings); "
                     f"four-registry coherent={cen.get('coherent')}; "
                     f"release {rel.get('output')} (preserved={rel.get('preserved')})")
    if rec.get("identity_note"):
        lines.append(f"* identity: {rec['identity_note']}")
    lines.append("")
    if rec.get("degradations"):
        lines.append("## Caveats / degradations (honest, in delivery order)")
        for d in rec["degradations"]:
            lines.append(f"* {d}")
        lines.append("")
    if rec.get("errors"):
        lines.append("## Errors")
        for e in rec["errors"]:
            lines.append(f"* {e}")
        lines.append("")
    mp = os.path.join(out_dir, "MANIFEST.md")
    with open(mp, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    return {"manifest_json": jp, "manifest_md": mp}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="rvt.convert.add_to_project",
        description="prompt + RVT -> RVT: add prompt-described equipment to an "
                    "existing project (the combination route).")
    ap.add_argument("target", help="the existing .rvt to add into (the user's file)")
    ap.add_argument("--prompt", required=True, help="what to add, in words")
    ap.add_argument("-o", "--out-dir", required=True)
    ap.add_argument("--at", type=float, nargs=2, metavar=("X_M", "Y_M"),
                    help="explicit anchor in metres (target world frame)")
    ap.add_argument("--level", default=None,
                    help="target level: 1-based story index or name substring")
    ap.add_argument("--stem", default=None, help="output file stem")
    ap.add_argument("--strict", action="store_true",
                    help="walls+families open bug -> two coordinated files")
    ap.add_argument("--no-validate", action="store_true")
    a = ap.parse_args(argv)
    try:
        rec = add_to_project(a.prompt, a.target, a.out_dir, at=a.at,
                             level=a.level, strict=a.strict, stem=a.stem,
                             validate=not a.no_validate)
    except (ConvertError, Exception) as e:                     # noqa: BLE001
        if not isinstance(e, ConvertError):
            traceback.print_exc(limit=6)
        print(f"REFUSED/FAILED: {e}")
        return 2
    files = rec.get("deliverables") or {}
    print(f"delivered {len(files)} file(s):")
    for role, d in files.items():
        print(f"  {role}: {d['path']} ({d['bytes']:,} bytes)")
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
