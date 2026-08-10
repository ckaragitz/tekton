"""rvt.frontdoor.build -- THE BUILD STEP: intent -> our .rvt ON THE
CERTIFIED GENESIS BASE (all three input routes end here).

The mechanics are the ifc-room stream's PROVEN build code, reused as-is
(``tools/ifc_intent.py`` loaded as a module -- imported, never edited):

    P  the job's PROJECT INFORMATION (rvt.frontdoor.project_info: the
       intent's identity written into the base's ProjectInfo element by the
       certified modify shape -- first, so every later file inherits it);
    D  the intent's LEVELS bound to the base's two building-story DATUMS
       (rvt.frontdoor.levels: rename + re-elevate, the same modify shape;
       storeys beyond them recorded not-built, never silently dropped);
    F  our generated FAMILIES (.rfa) from the intent's family mapping
       (rvt.famgen.factory catalog products + the honest house switchboard);
    L  LOAD them onto the base (rvt.famgen.loader, four-registry, chained);
    W  the room's WALLS (rvt.mutate.add_wall on the base's own wall type,
       specimen scaffolding cloned from the certified ancestor R5; each wall
       carries an AUTHORED seq-103 GElement solid -- rvt.render.brep, the
       W1_gabpd_wall_solid recipe -- unless ``RVT_WALL_REP=dummy``) on the
       room's level datum;
    E  the EQUIPMENT instances (rvt.mutate.add_family_instance onto OUR
       loaded symbols at the intent's WORLD frames, our connector managers),
       each associated to ITS level's datum (m_assocLevelId), AND -- in the
       same commit -- the feeder CIRCUITS (rvt.mutate.add_circuit over the
       constructed RbsElectricalSystem specimen, one per non-service edge);
    C  the circuit READBACK (count == edges, both-side connector links on
       the written bytes); a shortfall is recorded, never faked;
    V  the gates: rvt.validate (0 errors) / four-registry census / identity
       gate / the P0 provenance-deliverability gate, per output file.

What THIS module adds is the degrade policy the ifc-room pipeline never
had -- THE OPEN CELL (docs/inbox/genesis-audit.md verdict #48, issue #16):
PLACED INSTANCES of OUR generated family documents on OUR composed genesis
base fail Autodesk's audit, while walls PASS, loaded families PASS and
walls + loaded families in one file PASS (WF_fix / WF_nofix, verdict #27).
So :func:`build_intent` first asks
:func:`rvt.frontdoor.intent.combination_check` (intent + stages + the
base's lineage) and then does exactly one of:

  * ``single``            no instance placed on a composed base (walls only,
                          loaded families only, walls + loaded families
                          without placement, or a non-composed host) -> ONE
                          certified-shape file, no open-cell stamp;
  * ``split-strict``      (``--strict``) -> TWO coordinated files, both
                          delivered: ``shell`` (the walls + the LOADED
                          families on the base -- the certified shape) +
                          ``equipment`` (the loaded families + their PLACED
                          instances -- the open cell, isolated);
  * ``stamp-proof-only``  (default) -> ONE combined file whose manifest is
                          STAMPED :data:`rvt.frontdoor.intent.OPEN_CELL_STAMP`.

A stamp is a label (hard rule 1): every mode delivers its file(s).  It never
pretends a refused family (no catalog facts) or a blocked circuit was built.

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
from . import levels as LV
from . import project_info as PI
from . import release_ctx as RC
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

#: env opt-out for the created walls' seq-103 rep (``dummy`` restores the
#: pre-bake SerializedDummy output byte-for-byte; no front-door flag needed)
WALL_REP_ENV = "RVT_WALL_REP"


def default_wall_rep() -> str:
    """``'solid'`` unless ``RVT_WALL_REP=dummy`` (unknown values -> 'solid':
    a typo must not cost the user their walls)."""
    from ..render.brep import WALL_REPS
    v = (os.environ.get(WALL_REP_ENV) or "solid").strip().lower()
    return v if v in WALL_REPS else "solid"


@dataclass
class BuildOptions:
    """How to run the build."""
    out_dir: str
    base: ResolvedBase
    stem: str = "frontdoor"                    # output file stem
    strict: bool = False                       # --strict => split-strict degrade (open cell)
    specimen_src: Optional[str] = None         # None -> the pinned ancestor (R5)
    stages: str = "FLWECV"                     # subset of F,L,W,E,C,V
    wall_mode: str = "min"                     # 'min' | 'unjoin' | 'raw'
    wall_rep: str = dc_field(default_factory=default_wall_rep)   # 'solid' | 'dummy'
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
    project_info: Dict[str, Any] = dc_field(default_factory=dict)    # stage P record
    levels: Dict[str, Any] = dc_field(default_factory=dict)          # stage D record
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
            "status_gate": self.status_gate, "project_info": self.project_info,
            "levels": self.levels,
            "degradations": list(self.degradations),
            "created": list(self.created), "errors": list(self.errors),
            "stages": list(self.stages), "seconds": self.seconds,
        }


# ---------------------------------------------------------------------------
# per-stage wall time (manifest build.stages[*].seconds -- issue #124)
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def _timed_stage(res: "BuildResult"):
    """Stamp ``seconds`` (this block's wall time, perf_counter, 0.01 s) on
    every ``res.stages`` entry appended inside the block -- the ONE clock the
    manifest's per-stage column uses (a stage record's own coarser figure, if
    any, is superseded), so ``tools/surface_bench.py`` can say where a job's
    time goes."""
    n0 = len(res.stages)
    t0 = time.perf_counter()
    try:
        yield
    finally:
        dt = round(time.perf_counter() - t0, 2)
        for st in res.stages[n0:]:
            st["seconds"] = dt


# ---------------------------------------------------------------------------
# stage L in ONE host pass (issue #124)
# ---------------------------------------------------------------------------

def _load_entry(tag: str, lr, in_path: str, out_path: str, R) -> Dict[str, Any]:
    """One ``loads[]`` row of the stage-L record (the shape
    ``tools/ifc_intent.stage_load`` writes per family; stage E and the
    manifest read it)."""
    plan = lr.plan
    entry: Dict[str, Any] = {
        "tag": tag, "in": _relp(in_path), "out": _relp(out_path),
        "ok": bool(lr.ok), "stop_reason": lr.stop_reason,
        "host_watermark": (lr.proofs.get("plan") or {}).get("host_watermark"),
        "symbol_id": plan.symbol_id if plan else None,
        "family_id": plan.host_family_id if plan else None,
        "surrogate_id": plan.surrogate_id if plan else None,
        "content_guid": plan.guid if plan else None,
        "twins": len(plan.twin_of) if plan else None,
        "elements_added": len(lr.elements),
        "proofs": R._slim_proofs(lr.proofs),
        "acceptance": lr.acceptance,
        "report": _relp(out_path + ".load.json"),
    }
    if not lr.ok:
        entry["blocker"] = lr.stop_reason or "load returned ok=False"
    return entry


def stage_load_batched(model: FI.IntentModel, base_path: str, stages_dir: str, R, *,
                       symbol_solid: bool = True) -> Dict[str, Any]:
    """Stage L in ONE host pass: every mapped family (feeder-tree order) is
    generated above the ids the previous one allocated and all N are loaded
    by :func:`rvt.famgen.loader.load_families_into_project` -- one survey,
    one ``Global/Latest`` edit, one commit, one container write, one
    verification -- instead of N chained single loads.

    Degrade policy (the chain's, kept): the deliverable is the DEEPEST GOOD
    PREFIX of the load order.  A family that cannot be authored stops the
    batch there (the loader's own rule); a family the loader blames for a
    failed write step or a failed verification (``BatchLoadResult.culprit``)
    is dropped with everything after it and the prefix is loaded again; a
    failure the loader cannot pin on one family (host write crashed,
    file-level verification) sheds the LAST family and tries again -- so a
    bad family costs host passes (logged, counted in ``host_passes``), never
    the families before it.

    Returns the stage record shape of ``tools/ifc_intent.stage_load``
    (``loads`` / ``loaded`` / ``final`` / ``n_loaded`` / ``blocker`` + the
    private ``_loaded`` / ``_products`` / ``_current`` hand-offs to stage E),
    plus ``mode`` / ``host_passes`` / ``shared_proofs`` / ``verify``.
    (``rvt.convert.add_to_project`` still calls the chained ``stage_load``.)"""
    from ..famgen import loader as L
    order = R._load_order(model)
    out = os.path.join(stages_dir, "stage_L_loaded.rvt")
    rec: Dict[str, Any] = {"stage": "L", "mode": "batched (one host pass)",
                           "base": _relp(base_path), "order": order, "loads": [],
                           "host_passes": 0, "final": None, "blocker": None}
    products: Dict[str, Any] = {}

    def builder(tag):
        def build(start_id):
            products[tag] = R.build_product(model.plan_for(tag), start_id=start_id,
                                            solid=symbol_solid)
            return products[tag]
        return build

    loaded: Dict[str, Any] = {}
    dropped: List[Dict[str, Any]] = []       # rows of families dropped by an earlier pass
    attempt = list(order)
    while attempt:
        rec["host_passes"] += 1
        try:
            res = L.load_families_into_project(base_path, out, [builder(t) for t in attempt],
                                               symbol_solid=symbol_solid,
                                               report_path=out + ".load.json", validate=False)
        except Exception as e:                                       # noqa: BLE001
            # the host itself could not be surveyed / opened: no family to blame
            rec["blocker"] = rec["blocker"] or f"host: {type(e).__name__}: {e}"
            dropped = [{"tag": t, "ok": False, "blocker": f"{type(e).__name__}: {e}"}
                       for t in attempt] + dropped
            dropped[0]["traceback"] = traceback.format_exc(limit=8)
            R._log(f"L  EXCEPTION: {type(e).__name__}: {e}")
            break
        rec["shared_proofs"] = {k: res.shared.get(k) for k in
                                ("adocument_reencode", "content_documents", "pass1_commit",
                                 "write_error")}
        rec["verify"] = res.shared.get("verify_written")
        entries = [_load_entry(tag, lr, base_path, out, R) for tag, lr in zip(attempt, res.loads)]
        n_written = sum(1 for lr in res.loads if lr.out_path)     # families in the written file
        file_ok = bool(n_written) and bool((rec["verify"] or {}).get("file_ok"))
        if file_ok and all(lr.ok for lr in res.loads[:n_written]):
            # the written file is good: all N, or the prefix before a family
            # that could not be AUTHORED (nothing bad is in the file)
            for tag, lr in zip(attempt, res.loads[:n_written]):
                loaded[tag] = {"symbol_id": lr.plan.symbol_id,
                               "family_id": lr.plan.host_family_id,
                               "content_guid": lr.plan.guid, "product": products.get(tag)}
            rec["loads"] = entries[:n_written]
            dropped = entries[n_written:] + dropped
            if res.culprit is not None and rec["blocker"] is None:
                rec["blocker"] = f"{attempt[res.culprit]}: {res.loads[res.culprit].stop_reason}"
            break
        # not deliverable as attempted.  Deepest good prefix: keep everything
        # before the family to blame; when the loader cannot pin the failure
        # on one family (host write crashed, file-level verification), shed
        # the LAST family and try again -- a bad family costs passes, never
        # the families before it.
        keep = res.culprit if res.culprit is not None else len(attempt) - 1
        blame = attempt[keep] if keep < len(attempt) else attempt[-1]
        if rec["blocker"] is None:
            rec["blocker"] = f"{blame}: {res.stop_reason}"
        for e in entries[keep:]:
            e["ok"] = False
            e.setdefault("blocker", res.stop_reason)
        dropped = entries[keep:] + dropped
        if keep <= 0:
            break                                 # nothing left to keep
        R._log(f"L  pass {rec['host_passes']}: {res.stop_reason} -> loading the "
               f"{keep}-family prefix again")
        attempt = attempt[:keep]
    rec["loads"] = rec["loads"] + dropped
    current = out if loaded else base_path
    rec["loaded"] = {t: {k: v for k, v in d.items() if k != "product"} for t, d in loaded.items()}
    rec["final"] = _relp(current) if loaded else None
    rec["n_loaded"] = len(loaded)
    rec["n_planned"] = len(order)
    rec["_products"] = products          # for stage E (not json-serialised)
    rec["_loaded"] = loaded
    rec["_current"] = current
    R._log(f"L  {len(loaded)}/{len(order)} families loaded in {rec['host_passes']} host "
           f"pass(es) -> {os.path.basename(current)}"
           + (f"; blocker: {rec['blocker']}" if rec["blocker"] else ""))
    return rec


# ---------------------------------------------------------------------------
# the build
# ---------------------------------------------------------------------------

def build_intent(model: FI.IntentModel, opts: BuildOptions) -> BuildResult:
    """Build ``model`` into ``.rvt`` file(s) on the certified genesis base
    with the honest open-cell DEGRADE (see module docstring)."""
    t0 = time.time()
    res = BuildResult()
    out_dir = opts.out_dir
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(os.path.join(out_dir, "_stages"), exist_ok=True)

    try:
        R = load_ifc_room_module()
    except BuildError as e:
        res.errors.append(str(e))
        res.seconds = round(time.time() - t0, 1)
        return res

    # RELEASE CONTEXT (docs/inbox/build-2025.md): when the resolved base is a
    # certified NON-DEFAULT release (e.g. --target-version 2025), the whole
    # build runs inside rvt.frontdoor.release_ctx -- framing ordinals, codec
    # singletons and the constructor port layer bound to the base's own
    # release, everything restored on exit.  Native-release bases are a no-op.
    try:
        release_guard = RC.release_build_context(opts.base.path)
    except RC.ReleaseContextError as e:
        res.errors.append(str(e))
        res.seconds = round(time.time() - t0, 1)
        return res

    with release_guard as release_info:
        if release_info:
            res.stages.append({"stage": "release-context",
                               "release": release_info["release"],
                               "native": release_info["native"],
                               "port_layer": release_info["port_layer"]})
        out = _build_intent_inner(model, opts, R, res, t0)
        if release_info and any(c.get("kind") == "equipment-instance"
                                for c in out.created):
            out.degradations.append(
                "KNOWN LIMIT (release-independent): placed equipment instances "
                "carry the OPEN instance-audit residual of the famgen path "
                "(no-instance famgen files pass the viewer; instance-bearing "
                f"ones are the open question on Revit {release_info['native']} "
                f"too) -- this Revit {release_info['release']} output shares "
                "that fate; walls+base are the certified-clean subset")
        return out


def _build_intent_inner(model: FI.IntentModel, opts: BuildOptions, R,
                        res: BuildResult, t0: float) -> BuildResult:
    log_buf = io.StringIO()
    stages_dir = os.path.join(opts.out_dir, "_stages")

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
    # its own business).  The RESOLVED base is always exempt (it went
    # through resolve_base's pin/sample gates -- a sanctioned input even
    # when an explicit --base/$RVT_GENESIS_BASE lives under experiments/).
    SA.forbid_research_inputs(
        allow=[p for p in (opts.base.path, opts.specimen_src) if p])
    try:
        # ---- the degrade decision (placed instances of OUR families on OUR
        #      composed base = THE OPEN CELL).  Every base except a pristine
        #      Autodesk sample (dev-only, quarantined) is treated as our composed
        #      lineage: the pinned bases are, and an explicit/env override is a
        #      genesis campaign base -- the conservative label either way. ----
        verdict = FI.combination_check(model, strict=opts.strict, stages=opts.stages,
                                       composed_base=not opts.base.is_autodesk_sample)
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
    base_path = opts.base.path        # the pinned base: the P0 gate's reference

    # ------------------------------------------------------------------
    # P. the job's identity -> the base's ProjectInfo (one modify, first,
    #    so every downstream file inherits it; issue #148)
    # ------------------------------------------------------------------
    p_out = os.path.join(stages_dir, "stage_P_identity.rvt")
    with _timed_stage(res):
        prec = PI.stage_project_info(base_path, p_out, PI.identity_from_intent(model))
        res.stages.append(_slim_stage(prec))
    res.project_info = {**prec, "in": _relp(base_path), "out": _relp(p_out)}
    src_base = p_out if prec["ok"] else base_path     # what D / L / W grow on
    if not prec["ok"]:
        res.degradations.append("job identity NOT written into ProjectInfo: "
                                + str(prec.get("blocker"))
                                + " -> the output keeps the base's placeholder Project "
                                  "Information (edit it in Revit: Manage > Project Information)")

    # ------------------------------------------------------------------
    # D. the intent's levels -> the base's building-story DATUMS (rename +
    #    re-elevate, one modify; storeys beyond them recorded; issue #147)
    # ------------------------------------------------------------------
    d_out = os.path.join(stages_dir, "stage_D_levels.rvt")
    with _timed_stage(res):
        drec = LV.stage_levels(src_base, d_out, model.levels or [],
                               room_level=model.room.level if model.room else None)
        res.stages.append(_slim_stage(drec))
    res.levels = {**drec, "in": _relp(src_base), "out": _relp(d_out) if drec["written"] else None}
    level_ids = drec["level_map"]                     # intent level id -> (base Level id, z ft)
    room_level = drec["room_level_id"]                # the datum the room's walls stand on
    if drec["ok"] and drec["written"]:
        src_base = d_out
    elif not drec["ok"]:
        res.degradations.append("levels NOT bound to the base's story datums: "
                                + str(drec.get("blocker"))
                                + " -> the output keeps the base's level names / elevations "
                                  "(equipment still associates to its storey's datum)")
    for nb in drec["not_built"]:
        res.degradations.append(nb["reason"])
    for b in drec["levels"]:
        if b.get("rename_skipped"):
            res.degradations.append(f"level {b['id']}: {b['rename_skipped']}")

    # ------------------------------------------------------------------
    # F. our generated FAMILIES (.rfa) -- standalone deliverables too
    # ------------------------------------------------------------------
    if want_fams and "F" in opts.stages:
        with _timed_stage(res):
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
        with _timed_stage(res):
            lrec = stage_load_batched(model, src_base, stages_dir, R,
                                      symbol_solid=opts.symbol_solid)
            loaded = lrec.pop("_loaded", {}) or {}
            lrec.pop("_products", None)
            loaded_file = lrec.pop("_current", None)
            res.load = {k: v for k, v in lrec.items()}
            res.stages.append({"stage": "L", "mode": lrec.get("mode"),
                               "host_passes": lrec.get("host_passes"),
                               "n_loaded": lrec.get("n_loaded"),
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
        if loaded_file == src_base or not loaded:
            loaded_file = None

    # ------------------------------------------------------------------
    # specimens (the certified ancestor's clone templates: wall + instance)
    # ------------------------------------------------------------------
    specimens = None
    if want_walls or (loaded and "E" in opts.stages):
        with _timed_stage(res):
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
    # the verdict FOLLOWS the load result: only families that actually loaded
    # can be placed, so a load that degraded (partly or to nothing) shrinks or
    # drops the open-cell label honestly -- one call, no special case
    if want_fams:
        planned = verdict
        verdict = FI.combination_check(model, strict=opts.strict, stages=opts.stages,
                                       composed_base=planned.composed_base,
                                       loaded_tags=loaded if have_fams else ())
        res.verdict = verdict
        if planned.triggers_open_bug and not verdict.triggers_open_bug:
            res.degradations.append("nothing loaded -> no instance placed: the job collapsed "
                                    "to walls-only, a single certified-shape file (open cell "
                                    "not exercised, stamp dropped)")
    mode = verdict.mode

    # ------------------------------------------------------------------
    # W + E per the degrade mode
    # ------------------------------------------------------------------
    erec: Optional[Dict[str, Any]] = None             # stage E's record: stage C names causes off it
    if mode == "split-strict":
        # (a) shell = the walls + the LOADED families (no placement): the
        #     WF_fix-certified shape, grown on the loaded chain; with no walls
        #     requested/built the loaded chain IS the certified shell
        wok = None
        if want_walls:
            with _timed_stage(res):
                wrec, wok = R.stage_walls(model, loaded_file, shell_path, specimens,
                                          level_id=room_level, wall_mode=opts.wall_mode,
                                          wall_rep=opts.wall_rep)
                wrec["stage"] = "W(shell)"
                res.stages.append(_slim_stage(wrec))
            if wok:
                _harvest_created(res, wrec, "wall")
            else:
                res.degradations.append("shell walls NOT built: "
                                        + str(wrec.get("blocker") or wrec.get("error"))
                                        + " -> the shell is the loaded families alone")
        if not wok:
            shutil.copyfile(loaded_file, shell_path)
        res.files["shell"] = shell_path
        _harvest_loaded_families(res, loaded)
        # (b) equipment = the loaded families + their PLACED instances (the
        #     open cell, isolated from the certified shell)
        with _timed_stage(res):
            erec, eok = R.stage_equipment(model, loaded_file, equip_path, specimens, loaded,
                                          level_ids=level_ids, circuits="C" in opts.stages)
            erec["stage"] = "E(equipment)"
            res.stages.append(_slim_stage(erec))
        if eok:
            res.files["equipment"] = equip_path
            _harvest_created(res, erec, "instance")
        else:
            res.degradations.append("equipment file NOT emitted (instances NOT placed): "
                                    + str(erec.get("blocker") or erec.get("error"))
                                    + " -- the shell file still carries the loaded families")
    else:
        # single / stamp-proof-only: one file, built in W -> E order
        current = None
        if want_walls:
            src = loaded_file if have_fams else src_base
            wtarget = (os.path.join(stages_dir, "stage_W_walls.rvt")
                       if (have_fams and "E" in opts.stages) else combined_path)
            with _timed_stage(res):
                wrec, wok = R.stage_walls(model, src, wtarget, specimens,
                                          level_id=room_level, wall_mode=opts.wall_mode,
                                          wall_rep=opts.wall_rep)
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
            with _timed_stage(res):
                erec, eok = R.stage_equipment(model, src, combined_path, specimens, loaded,
                                              level_ids=level_ids, circuits="C" in opts.stages)
                erec["stage"] = "E"
                res.stages.append(_slim_stage(erec))
            if eok:
                current = combined_path
                _harvest_created(res, erec, "instance")
            else:
                res.degradations.append("equipment instances NOT placed: "
                                        + str(erec.get("blocker") or erec.get("error")))
                if current and current != combined_path:
                    shutil.copyfile(current, combined_path)   # walls-only survives
                    current = combined_path
                elif current is None and loaded_file:
                    shutil.copyfile(loaded_file, combined_path)   # loaded-only survives
                    current = combined_path
        elif have_fams and current is None:
            shutil.copyfile(loaded_file, combined_path)
            current = combined_path
        if current and os.path.abspath(current) != os.path.abspath(combined_path):
            shutil.copyfile(current, combined_path)
            current = combined_path
        if current:
            res.files["combined"] = combined_path
            if have_fams:
                # every file grown in this branch descends from the loaded
                # chain, so the loaded families ride it (placed or not)
                _harvest_loaded_families(res, loaded)

    # ------------------------------------------------------------------
    # C. circuits: wired in stage E's commit; read back + verified here
    # ------------------------------------------------------------------
    deepest = res.deepest
    if "C" in opts.stages and deepest and model.feeders:
        with _timed_stage(res):
            crec = R.stage_circuits(model, deepest, erec)
            res.circuits = crec
            res.stages.append({"stage": "C", "ok": crec.get("ok"),
                               "planned": len(crec.get("circuits_planned") or []),
                               "built": crec.get("circuits_built"),
                               "links_ok": crec.get("links_ok"),
                               "blocker": crec.get("blocker")})
        if crec.get("blocker"):
            res.degradations.append("feeder CIRCUITS incomplete: " + str(crec.get("blocker")))
    elif deepest and R.circuit_edges(model):
        res.degradations.append("feeder CIRCUITS not wired: " + R.STAGE_C_NOT_REQUESTED)

    # ------------------------------------------------------------------
    # V. gates per emitted file
    # ------------------------------------------------------------------
    if opts.validate and "V" in opts.stages:
        gate_seconds: Dict[str, float] = {}          # per-gate split of the V stage

        def _gate(name: str, fn, *args):
            t = time.perf_counter()
            try:
                return fn(*args)
            finally:
                gate_seconds[name] = round(gate_seconds.get(name, 0.0)
                                           + time.perf_counter() - t, 2)

        with _timed_stage(res):
            for role in ("combined", "shell", "equipment"):
                p = res.files.get(role)
                if not p or not os.path.isfile(p):
                    continue
                g: Dict[str, Any] = {}
                try:
                    g["validate"] = _gate("validate", R.validate_rvt, p)
                except Exception as e:                                   # noqa: BLE001
                    g["validate"] = {"verdict": "ERROR", "error": f"{type(e).__name__}: {e}"}
                try:
                    g["census"] = _gate("census", R.registry_census, p)
                except Exception as e:                                   # noqa: BLE001
                    g["census"] = {"error": f"{type(e).__name__}: {e}"}
                try:
                    g["identity"] = _gate("identity", R.identity_gate, p)
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
                    res.status_gate = _gate("status_gate", R.status_gate, deepest, base_path)
                except Exception as e:                                   # noqa: BLE001
                    res.status_gate = {"status": f"PROOF-ONLY, NOT-DELIVERABLE (gate crashed: "
                                                 f"{type(e).__name__}: {e})", "deliverable": False}
                # the Project Status written in stage P mirrors this gate's stamp;
                # the day the gate says deliverable, that constant must follow it
                written = (res.project_info.get("after") or {}).get("project_status")
                if res.status_gate.get("deliverable") and written == PI.PROJECT_STATUS_PROOF_ONLY:
                    res.degradations.append(
                        f"ProjectInfo Project Status reads '{written}' but the P0 gate now says "
                        "DELIVERABLE -- rvt.frontdoor.project_info's default is stale")
            res.stages.append({"stage": "V", "files": sorted(res.validation),
                               "gates": gate_seconds})
    elif not opts.validate:
        res.degradations.append("validation SKIPPED (--no-validate): this is NOT a shippable run")


# ---------------------------------------------------------------------------
# harvesting the created-element census for the manifest / CRUD affordances
# ---------------------------------------------------------------------------

#: the per-circuit facts stage E records that ride into the manifest
_CIRCUIT_KEYS = ("elem_id", "panel", "panel_id", "panel_slot", "load", "load_id", "load_conn",
                 "number", "start_slot", "poles", "rating_a", "voltage", "edge_kind")


def _harvest_created(res: BuildResult, rec: Dict[str, Any], kind: str) -> None:
    if kind == "wall":
        for w in rec.get("walls") or []:
            res.created.append({"kind": "wall", "tag": w.get("id"), "elem_id": w.get("elem_id"),
                                "length_m": w.get("length_m"), "height_ft": w.get("height_ft"),
                                "rep": rec.get("wall_rep", "dummy"),
                                "file_role": rec.get("stage")})
    else:
        for i in rec.get("instances") or []:
            res.created.append({"kind": "equipment-instance", "tag": i.get("tag"),
                                "elem_id": i.get("elem_id"), "symbol": i.get("symbol"),
                                "family": i.get("family"), "equip_kind": i.get("kind"),
                                "position_ft": i.get("position_ft"),
                                "level": i.get("level"), "level_id": i.get("level_id"),
                                "z_above_level_ft": i.get("z_above_level_ft"),
                                "frame_kind": i.get("frame_kind"),
                                "connector_slots_panel": i.get("connector_slots_panel"),
                                "file_role": rec.get("stage")})
        for c in rec.get("circuits") or []:
            res.created.append({"kind": "circuit", "tag": f"{c.get('panel')}>{c.get('load')}",
                                **{k: c.get(k) for k in _CIRCUIT_KEYS},
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
    keep = ("stage", "ok", "in", "out", "wall_mode", "wall_rep", "wall_type", "wall_type_name",
            "level", "written", "edited_ids", "elemtable_before", "elemtable_after", "new_ids",
            "verify", "structurally_valid", "seconds", "blocker", "error", "notes")
    out = {k: rec.get(k) for k in keep if k in rec}
    for k in ("in", "out"):
        if out.get(k):
            out[k] = _relp(out[k]) if os.path.isabs(str(out[k])) else out[k]
    if rec.get("walls"):
        out["walls"] = [{"id": w.get("id"), "elem_id": w.get("elem_id"),
                         "p0_ft": w.get("p0_ft"), "p1_ft": w.get("p1_ft"),
                         "height_ft": w.get("height_ft"), "rep": w.get("rep"),
                         "n_dangling": w.get("n_dangling")} for w in rec["walls"]]
    if rec.get("instances"):
        out["instances"] = [{"tag": i.get("tag"), "elem_id": i.get("elem_id"),
                             "symbol": i.get("symbol"), "family": i.get("family"),
                             "position_ft": i.get("position_ft"), "frame_kind": i.get("frame_kind"),
                             "n_dangling": i.get("n_dangling")} for i in rec["instances"]]
    if "circuits" in rec:
        out["circuits"] = [{k: c.get(k) for k in _CIRCUIT_KEYS[:7] + ("n_dangling",)}
                           for c in rec["circuits"]]
        out["circuits_skipped"] = rec.get("circuits_skipped") or []
        out["circuits_blocker"] = rec.get("circuits_blocker")
    return out
