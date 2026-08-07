"""rvt.frontdoor.build -- THE BUILD STEP: intent -> our .rvt ON THE
CERTIFIED GENESIS BASE (all three input routes end here).

The mechanics are the ifc-room stream's PROVEN build code, reused as-is
(``tools/ifc_intent.py`` loaded as a module -- imported, never edited):

    F  our generated FAMILIES (.rfa) from the intent's family mapping
       (rvt.famgen.factory catalog products + the honest house switchboard);
    L  LOAD them onto the base (rvt.famgen.loader, four-registry, chained);
    W  the room's WALLS (rvt.mutate.add_wall on the base's own wall type,
       specimen scaffolding cloned from the certified ancestor R5);
    E  the EQUIPMENT instances (rvt.mutate.add_family_instance onto OUR
       loaded symbols at the intent's frames, our connector managers);
    C  the feeder CIRCUITS (rvt.mep territory) -- today a NAMED BLOCKER on
       the family-free base (no circuit specimen); recorded, never faked;
    V  the gates: rvt.validate (0 errors) / four-registry census / identity
       gate / the P0 provenance-deliverability gate, per output file.

What THIS module adds is the degrade policy the ifc-room pipeline never
had -- the OPEN BUG (docs/inbox/genesis-audit.md verdict #24): created WALLS
+ LOADED FAMILY DOCUMENTS in the SAME file trip Autodesk's audit, while walls
alone PASS and loaded families(+placement) alone PASS.  So
:func:`build_intent` first asks :func:`rvt.frontdoor.intent.combination_check`
and then does exactly one of:

  * ``single``            walls-only OR families-only -> ONE proven-shaped file;
  * ``split-strict``      (``--strict``) -> TWO coordinated files:
                          ``shell`` (the walls on the base) + ``equipment``
                          (the loaded families + their instances on the base);
  * ``stamp-proof-only``  (default) -> ONE combined file whose manifest is
                          STAMPED 'PROOF-ONLY: walls+families combination
                          unverified'.

It never silently ships the unverified combination, and it never pretends a
refused family (no catalog facts) or a blocked circuit was built.

Territory: ``src/rvt/frontdoor/`` (front-door stream).
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import shutil
import sys
import time
import traceback
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, List, Optional

from . import intent as FI
from .base import ResolvedBase, repo_root, resolve_specimen_source
from . import standalone as SA

__all__ = ["BuildError", "BuildOptions", "BuildResult", "load_ifc_room_module",
           "build_intent"]


class BuildError(RuntimeError):
    """The build cannot start (missing engine / base / specimens)."""


# ---------------------------------------------------------------------------
# the ifc-room build code as a module (tools/ifc_intent.py -- REUSED, not edited)
# ---------------------------------------------------------------------------

_ROOM = None


def load_ifc_room_module():
    """Import ``tools/ifc_intent.py`` (the ifc-room stream's staged builder:
    stage_families / stage_load / SpecimenSet / stage_walls /
    stage_equipment / stage_circuits + the gates)."""
    global _ROOM
    if _ROOM is not None:
        return _ROOM
    p = os.path.join(repo_root(), "tools", "ifc_intent.py")
    if not os.path.isfile(p):
        raise BuildError(f"tools/ifc_intent.py not found at {p} (the front door reuses "
                         "the ifc-room stream's build code)")
    spec = importlib.util.spec_from_file_location("_frontdoor_ifc_room", p)
    if spec is None or spec.loader is None:
        raise BuildError("cannot load tools/ifc_intent.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    _ROOM = mod
    return mod


def _relp(p: Optional[str]) -> Optional[str]:
    if not p:
        return None
    try:
        r = os.path.relpath(p, repo_root())
        return r if not r.startswith("..") else os.path.abspath(p)
    except ValueError:
        return os.path.abspath(p)


# ---------------------------------------------------------------------------
# options / result
# ---------------------------------------------------------------------------

@dataclass
class BuildOptions:
    """How to run the build."""
    out_dir: str
    base: ResolvedBase
    stem: str = "frontdoor"                    # output file stem
    strict: bool = False                       # --strict => split-strict degrade
    specimen_src: Optional[str] = None         # None -> the pinned ancestor (R5)
    stages: str = "FLWECV"                     # subset of F,L,W,E,C,V
    wall_mode: str = "min"                     # 'min' | 'unjoin' | 'raw'
    symbol_solid: bool = True
    validate: bool = True
    quiet: bool = True


@dataclass
class BuildResult:
    """Everything the build produced (feeds the manifest)."""
    files: Dict[str, Optional[str]] = dc_field(default_factory=dict)   # role -> path
    verdict: Optional[Any] = None
    families: Dict[str, Any] = dc_field(default_factory=dict)
    load: Dict[str, Any] = dc_field(default_factory=dict)
    stages: List[Dict[str, Any]] = dc_field(default_factory=list)
    validation: Dict[str, Any] = dc_field(default_factory=dict)      # role -> gates
    circuits: Dict[str, Any] = dc_field(default_factory=dict)
    status_gate: Dict[str, Any] = dc_field(default_factory=dict)
    degradations: List[str] = dc_field(default_factory=list)
    created: List[Dict[str, Any]] = dc_field(default_factory=list)   # created elements
    errors: List[str] = dc_field(default_factory=list)
    seconds: float = 0.0
    log: str = ""

    @property
    def deepest(self) -> Optional[str]:
        for role in ("combined", "equipment", "shell"):
            if self.files.get(role):
                return self.files[role]
        return None

    def as_json(self) -> Dict[str, Any]:
        return {
            "files": {k: _relp(v) for k, v in self.files.items() if v},
            "verdict": self.verdict.as_json() if self.verdict is not None else None,
            "families": self.families, "load": self.load,
            "validation": self.validation, "circuits": self.circuits,
            "status_gate": self.status_gate, "degradations": list(self.degradations),
            "created": list(self.created), "errors": list(self.errors),
            "seconds": self.seconds,
        }


# ---------------------------------------------------------------------------
# the build
# ---------------------------------------------------------------------------

def build_intent(model: FI.IntentModel, opts: BuildOptions) -> BuildResult:
    """Build ``model`` into ``.rvt`` file(s) on the certified genesis base
    with the honest walls+families DEGRADE (see module docstring)."""
    t0 = time.time()
    res = BuildResult()
    log_buf = io.StringIO()
    out_dir = opts.out_dir
    os.makedirs(out_dir, exist_ok=True)
    stages_dir = os.path.join(out_dir, "_stages")
    os.makedirs(stages_dir, exist_ok=True)

    try:
        R = load_ifc_room_module()
    except BuildError as e:
        res.errors.append(str(e))
        res.seconds = round(time.time() - t0, 1)
        return res

    # STANDALONE RESOLUTION (docs/inbox/standalone.md): the schema comes from
    # the base's own Formats/Latest, and the build may never read the
    # research corpus -- a stray read fails RED, not silently.
    try:
        SA.install_schema(opts.base.path)
    except Exception as e:                                   # noqa: BLE001
        res.errors.append(f"schema install from base failed: {type(e).__name__}: {e}")
        res.seconds = round(time.time() - t0, 1)
        return res
    # armed for the DURATION of the build (disarmed in the finally: the
    # audit hook is process-wide, and the guarantee is about reads DURING
    # the build -- research tooling running later in the same process is
    # its own business)
    SA.forbid_research_inputs(allow=[p for p in (opts.specimen_src,) if p])
    try:
        # ---- the degrade decision (walls + loaded families = the OPEN BUG) ----
        verdict = FI.combination_check(model, strict=opts.strict)
        res.verdict = verdict
        plans = FI.buildable_family_plans(model)
        n_walls = verdict.n_walls
        want_walls = ("W" in opts.stages) and n_walls > 0
        want_fams = ("L" in opts.stages) and len(plans) > 0

        for p in (model.family_plans or []):
            if p.status not in ("resolved", "house"):
                res.degradations.append(
                    f"{p.tag} ({p.kind}): NOT built -- family plan {p.status}"
                    + (f": {p.refusal}" if p.refusal else "")
                    + " (the facts store never invents dimensions/ratings; supply the missing "
                      "facts or choose a covered rating)")

        if not want_walls and not want_fams:
            res.errors.append("intent has nothing buildable: no walls and no loadable family plans "
                              "(see 'degradations' for every refusal)")
            res.seconds = round(time.time() - t0, 1)
            return res

        ctx = contextlib.redirect_stdout(log_buf) if opts.quiet else contextlib.nullcontext()
        with ctx:
            try:
                _run(model, opts, R, res, verdict, plans, want_walls, want_fams, stages_dir)
            except Exception as e:                                       # noqa: BLE001
                res.errors.append(f"build crashed: {type(e).__name__}: {e}")
                res.errors.append(traceback.format_exc(limit=8))
        res.log = log_buf.getvalue() if opts.quiet else ""
        res.seconds = round(time.time() - t0, 1)
        return res
    finally:
        SA.allow_research_inputs()


def _run(model, opts: BuildOptions, R, res: BuildResult, verdict, plans,
         want_walls: bool, want_fams: bool, stages_dir: str) -> None:
    out_dir = opts.out_dir
    base_path = opts.base.path

    # ------------------------------------------------------------------
    # F. our generated FAMILIES (.rfa) -- standalone deliverables too
    # ------------------------------------------------------------------
    if want_fams and "F" in opts.stages:
        frec = R.stage_families(model, out_dir)
        res.families = {k: v for k, v in frec.items()}
        res.stages.append({"stage": "F", "built": frec.get("built"),
                           "all_ok": frec.get("all_ok"), "dir": frec.get("dir")})
        res.files["families_dir"] = os.path.join(out_dir, "families")
        for f in frec.get("families") or []:
            if f.get("built"):
                res.created.append({"kind": "family(.rfa)", "tag": f.get("tag"),
                                    "name": f.get("family_name"), "path": f.get("path"),
                                    "catalog": f.get("catalog"), "variant": f.get("variant"),
                                    "ok": f.get("ok")})

    # ------------------------------------------------------------------
    # L. LOAD the families onto the base (chained, four-registry)
    # ------------------------------------------------------------------
    loaded: Dict[str, Any] = {}
    loaded_file: Optional[str] = None
    if want_fams:
        lrec = R.stage_load(model, base_path, stages_dir, symbol_solid=opts.symbol_solid)
        loaded = lrec.pop("_loaded", {}) or {}
        lrec.pop("_products", None)
        loaded_file = lrec.pop("_current", None)
        res.load = {k: v for k, v in lrec.items()}
        res.stages.append({"stage": "L", "n_loaded": lrec.get("n_loaded"),
                           "n_planned": lrec.get("n_planned"),
                           "final": lrec.get("final"), "blocker": lrec.get("blocker")})
        if lrec.get("blocker"):
            res.degradations.append(f"family LOAD blocked at {lrec.get('blocker')} -- proceeding "
                                    f"with {lrec.get('n_loaded')}/{lrec.get('n_planned')} loaded "
                                    "(the deepest good load file)")
        if not loaded:
            loaded_file = None
            if want_walls:
                res.degradations.append("no family loaded -> the room degrades to WALLS ONLY "
                                        "(equipment omitted; each load result recorded)")
            else:
                res.errors.append("no family could be loaded and there are no walls to build")
                return
        if loaded_file == base_path or not loaded:
            loaded_file = None

    # ------------------------------------------------------------------
    # specimens (the certified ancestor's clone templates: wall + instance)
    # ------------------------------------------------------------------
    specimens = None
    if want_walls or (loaded and "E" in opts.stages):
        spec_src = opts.specimen_src or SA.CONSTRUCTED
        specimens = (R.SpecimenSet(spec_src) if spec_src != SA.CONSTRUCTED
                     else SA.ConstructedSpecimens(base_path=opts.base.path))
        res.stages.append({"stage": "specimens", "source": _relp(spec_src),
                           "wall": specimens.wall_id, "wall_type": specimens.wall_type,
                           "instance": specimens.instance_id,
                           "instance_symbol": specimens.instance_symbol,
                           "instance_category": specimens.instance_category})

    stem = opts.stem
    combined_path = os.path.join(out_dir, f"{stem}.rvt")
    shell_path = os.path.join(out_dir, f"{stem}-shell.rvt")
    equip_path = os.path.join(out_dir, f"{stem}-equipment.rvt")

    have_fams = bool(loaded) and loaded_file
    have_walls_now = want_walls
    mode = verdict.mode
    # re-derive the effective mode if a load degradation removed the families
    if verdict.triggers_open_bug and not have_fams:
        mode = "single"
        res.degradations.append("the walls+families combination collapsed to walls-only "
                                "(nothing loaded) -- single proven-shaped file")

    # ------------------------------------------------------------------
    # W + E per the degrade mode
    # ------------------------------------------------------------------
    if mode == "split-strict":
        # (a) shell = the walls on the BASE alone
        wrec, wok = R.stage_walls(model, base_path, shell_path, specimens,
                                  wall_mode=opts.wall_mode)
        wrec["stage"] = "W(shell)"
        res.stages.append(_slim_stage(wrec))
        if wok:
            res.files["shell"] = shell_path
            _harvest_created(res, wrec, "wall")
        else:
            res.degradations.append("shell (walls) file NOT emitted: "
                                    + str(wrec.get("blocker") or wrec.get("error")))
        # (b) equipment = the loaded families + their instances (no walls)
        if have_fams and "E" in opts.stages:
            erec, eok = R.stage_equipment(model, loaded_file, equip_path, specimens, loaded)
            erec["stage"] = "E(equipment)"
            res.stages.append(_slim_stage(erec))
            if eok:
                res.files["equipment"] = equip_path
                _harvest_created(res, erec, "instance")
                _harvest_loaded_families(res, loaded)
            else:
                res.degradations.append("equipment file NOT emitted: "
                                        + str(erec.get("blocker") or erec.get("error")))
        elif have_fams:
            # families loaded but no placement requested: the loaded chain IS the equipment file
            shutil.copyfile(loaded_file, equip_path)
            res.files["equipment"] = equip_path
            _harvest_loaded_families(res, loaded)
    else:
        # single / stamp-proof-only: one file, built in W -> E order
        current = None
        if have_walls_now:
            src = loaded_file if have_fams else base_path
            wtarget = (os.path.join(stages_dir, "stage_W_walls.rvt")
                       if (have_fams and "E" in opts.stages) else combined_path)
            wrec, wok = R.stage_walls(model, src, wtarget, specimens, wall_mode=opts.wall_mode)
            wrec["stage"] = "W"
            res.stages.append(_slim_stage(wrec))
            if wok:
                current = wtarget
                _harvest_created(res, wrec, "wall")
            else:
                res.degradations.append("walls NOT built: "
                                        + str(wrec.get("blocker") or wrec.get("error"))
                                        + " -> continuing with the equipment layer")
        if have_fams and "E" in opts.stages:
            src = current or loaded_file
            erec, eok = R.stage_equipment(model, src, combined_path, specimens, loaded)
            erec["stage"] = "E"
            res.stages.append(_slim_stage(erec))
            if eok:
                current = combined_path
                _harvest_created(res, erec, "instance")
                _harvest_loaded_families(res, loaded)
            else:
                res.degradations.append("equipment instances NOT placed: "
                                        + str(erec.get("blocker") or erec.get("error")))
                if current and current != combined_path:
                    shutil.copyfile(current, combined_path)   # walls-only survives
                    current = combined_path
                elif current is None and loaded_file:
                    shutil.copyfile(loaded_file, combined_path)   # loaded-only survives
                    current = combined_path
                    _harvest_loaded_families(res, loaded)
        elif have_fams and current is None:
            shutil.copyfile(loaded_file, combined_path)
            current = combined_path
            _harvest_loaded_families(res, loaded)
        if current and os.path.abspath(current) != os.path.abspath(combined_path):
            shutil.copyfile(current, combined_path)
            current = combined_path
        if current:
            res.files["combined"] = combined_path

    # ------------------------------------------------------------------
    # C. circuits (rvt.mep territory; a NAMED BLOCKER on this base today)
    # ------------------------------------------------------------------
    deepest = res.deepest
    if "C" in opts.stages and deepest and model.feeders:
        crec = R.stage_circuits(model, deepest)
        res.circuits = {k: v for k, v in crec.items() if k != "template_circuit"}
        res.stages.append({"stage": "C", "planned": len(crec.get("circuits_planned") or []),
                           "blocker": crec.get("blocker")})
        if crec.get("blocker"):
            res.degradations.append("feeder CIRCUITS not authored: " + str(crec.get("blocker"))
                                    + " -- the resolved circuit PLAN rides in the manifest "
                                      "(rvt.mep add_circuit / a Revit-side add-in build them "
                                      "from it)")

    # ------------------------------------------------------------------
    # V. gates per emitted file
    # ------------------------------------------------------------------
    if opts.validate and "V" in opts.stages:
        for role in ("combined", "shell", "equipment"):
            p = res.files.get(role)
            if not p or not os.path.isfile(p):
                continue
            g: Dict[str, Any] = {}
            try:
                g["validate"] = R.validate_rvt(p)
            except Exception as e:                                   # noqa: BLE001
                g["validate"] = {"verdict": "ERROR", "error": f"{type(e).__name__}: {e}"}
            try:
                g["census"] = R.registry_census(p)
            except Exception as e:                                   # noqa: BLE001
                g["census"] = {"error": f"{type(e).__name__}: {e}"}
            try:
                g["identity"] = R.identity_gate(p)
            except Exception as e:                                   # noqa: BLE001
                g["identity"] = {"status": "ERROR", "issues": [str(e)]}
            g["self_checks_ok"] = bool(
                (g["validate"].get("verdict") == "VALID")
                and (g["identity"].get("status") == "PASS")
                and (g["census"].get("coherent") is not False))
            res.validation[role] = g
        # deliverability status of the deepest output vs its base (P0 gate)
        if deepest:
            try:
                res.status_gate = R.status_gate(deepest, base_path)
            except Exception as e:                                   # noqa: BLE001
                res.status_gate = {"status": f"PROOF-ONLY, NOT-DELIVERABLE (gate crashed: "
                                             f"{type(e).__name__}: {e})", "deliverable": False}
    elif not opts.validate:
        res.degradations.append("validation SKIPPED (--no-validate): this is NOT a shippable run")


# ---------------------------------------------------------------------------
# harvesting the created-element census for the manifest / CRUD affordances
# ---------------------------------------------------------------------------

def _harvest_created(res: BuildResult, rec: Dict[str, Any], kind: str) -> None:
    if kind == "wall":
        for w in rec.get("walls") or []:
            res.created.append({"kind": "wall", "tag": w.get("id"), "elem_id": w.get("elem_id"),
                                "length_m": w.get("length_m"), "height_ft": w.get("height_ft"),
                                "file_role": rec.get("stage")})
    else:
        for i in rec.get("instances") or []:
            res.created.append({"kind": "equipment-instance", "tag": i.get("tag"),
                                "elem_id": i.get("elem_id"), "symbol": i.get("symbol"),
                                "family": i.get("family"), "equip_kind": i.get("kind"),
                                "position_ft": i.get("position_ft"),
                                "frame_kind": i.get("frame_kind"),
                                "connector_slots_panel": i.get("connector_slots_panel"),
                                "file_role": rec.get("stage")})


def _harvest_loaded_families(res: BuildResult, loaded: Dict[str, Any]) -> None:
    seen = {c.get("tag") for c in res.created if c.get("kind") == "loaded-family"}
    for tag, info in (loaded or {}).items():
        if tag in seen:
            continue
        res.created.append({"kind": "loaded-family", "tag": tag,
                            "symbol_id": info.get("symbol_id"),
                            "family_id": info.get("family_id"),
                            "content_guid": info.get("content_guid")})


def _slim_stage(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Keep the stage record small enough for the manifest."""
    keep = ("stage", "ok", "in", "out", "wall_mode", "wall_type", "wall_type_name", "level",
            "elemtable_before", "elemtable_after", "new_ids", "verify", "structurally_valid",
            "seconds", "blocker", "error", "notes")
    out = {k: rec.get(k) for k in keep if k in rec}
    for k in ("in", "out"):
        if out.get(k):
            out[k] = _relp(out[k]) if os.path.isabs(str(out[k])) else out[k]
    if rec.get("walls"):
        out["walls"] = [{"id": w.get("id"), "elem_id": w.get("elem_id"),
                         "p0_ft": w.get("p0_ft"), "p1_ft": w.get("p1_ft"),
                         "n_dangling": w.get("n_dangling")} for w in rec["walls"]]
    if rec.get("instances"):
        out["instances"] = [{"tag": i.get("tag"), "elem_id": i.get("elem_id"),
                             "symbol": i.get("symbol"), "family": i.get("family"),
                             "position_ft": i.get("position_ft"), "frame_kind": i.get("frame_kind"),
                             "n_dangling": i.get("n_dangling")} for i in rec["instances"]]
    return out
