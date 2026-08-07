"""rvt.frontdoor.router -- THE ROUTER: any permutation in, one delivery out.

``route(inputs, output, **opts)`` looks the request up in the PERMUTATION
MATRIX (:mod:`rvt.frontdoor.matrix`), picks the stage chain, executes the
existing composable stages (imported, never reimplemented -- this module
adds NO authoring logic of its own), and DELIVERS:

* the final output file (stamped; caveats AFTER delivery, per the
  deliverable rule);
* EVERY intermediate artifact alongside it (the intent JSON, the emitted
  IFC, the generated families / .rfa, the handoff package, the underlying
  build/edit manifests);
* a ROUTE MANIFEST (``route.json`` + ``ROUTE.md``): the cell, the stages
  actually run with their implementations and timings, the evidence the
  matrix cites for each stage, the stamps (PROOF-ONLY etc.), the caveats,
  and the detected Revit release of every delivered .rvt/.rfa.

Unknown or missing cells return the matrix row + the closest supported
route as ONE clear line (``RouteResult.line``) -- never a traceback.

CLI: ``tools/route.py``.  Territory: perm-matrix stream (new module).
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import time
import traceback
from dataclasses import dataclass, field as dc_field
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import matrix as MX
from .base import repo_root

__all__ = ["RouteError", "RouteResult", "route", "route_ids"]


class RouteError(RuntimeError):
    """Bad ARGUMENTS (unknown input/output kind, unreadable file).  Missing
    matrix cells are NOT errors -- they return a RouteResult with the line."""


# ---------------------------------------------------------------------------
# result
# ---------------------------------------------------------------------------

@dataclass
class RouteResult:
    ok: bool
    status: str                                   # short status line
    line: str = ""                                # THE one clear line (unsupported)
    cell: Optional[Dict[str, Any]] = None         # the matrix row consulted
    route: Optional[str] = None                   # route id executed
    out_dir: Optional[str] = None
    files: Dict[str, str] = dc_field(default_factory=dict)      # role -> path
    steps: List[Dict[str, Any]] = dc_field(default_factory=list)
    stamps: List[str] = dc_field(default_factory=list)
    caveats: List[str] = dc_field(default_factory=list)
    releases: Dict[str, Any] = dc_field(default_factory=dict)   # file role -> release
    errors: List[str] = dc_field(default_factory=list)
    manifest_paths: Dict[str, str] = dc_field(default_factory=dict)
    seconds: float = 0.0

    def as_json(self) -> Dict[str, Any]:
        return {"ok": self.ok, "status": self.status, "line": self.line,
                "cell": self.cell, "route": self.route, "out_dir": self.out_dir,
                "files": dict(self.files), "steps": list(self.steps),
                "stamps": list(self.stamps), "caveats": list(self.caveats),
                "releases": dict(self.releases), "errors": list(self.errors),
                "manifest": dict(self.manifest_paths), "seconds": self.seconds}


# ---------------------------------------------------------------------------
# small helpers (routing plumbing only -- no authoring logic)
# ---------------------------------------------------------------------------

def _norm_inputs(inputs: Dict[str, Any]) -> Dict[str, Any]:
    out = {k: v for k, v in (inputs or {}).items() if v is not None}
    for k in out:
        if k not in MX.INPUT_KINDS:
            raise RouteError(f"unknown input kind {k!r} (inputs: "
                             f"{', '.join(MX.INPUT_KINDS)})")
    for k in ("ifc", "rvt", "spec"):
        if k in out:
            p = os.path.abspath(str(out[k]))
            if not os.path.isfile(p):
                raise RouteError(f"--{k} file not found: {out[k]}")
            out[k] = p
    return out


def _out_dir(opts: Dict[str, Any], inputs: Dict[str, Any], output: str) -> str:
    if opts.get("out"):
        return os.path.abspath(str(opts["out"]))
    stamp = time.strftime("%Y%m%d-%H%M%S")
    name = "-".join(sorted(inputs)) + "-to-" + output
    return os.path.abspath(os.path.join(repo_root(), "experiments", "routes",
                                        f"{name}-{stamp}"))


def _slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(s)).strip("_") or "route"


class _Steps:
    """Collect step records; time each stage call."""

    def __init__(self, res: RouteResult) -> None:
        self.res = res

    def run(self, stage_id: str, impl: str, fn: Callable[[], Any],
            detail: Optional[str] = None) -> Any:
        t0 = time.time()
        rec: Dict[str, Any] = {"stage": stage_id, "impl": impl}
        if detail:
            rec["detail"] = detail
        try:
            out = fn()
            rec["ok"] = True
            return out
        except Exception as e:                                   # noqa: BLE001
            rec["ok"] = False
            rec["error"] = f"{type(e).__name__}: {e}"
            self.res.errors.append(f"{stage_id}: {type(e).__name__}: {e}")
            raise _StepFailed(stage_id) from e
        finally:
            rec["seconds"] = round(time.time() - t0, 1)
            self.res.steps.append(rec)


class _StepFailed(Exception):
    pass


def _load_tool(relpath: str, modname: str):
    """Import a repo tool/script as a module (the established pattern:
    build.load_ifc_room_module / edit.load_job_module)."""
    p = os.path.join(repo_root(), *relpath.split("/"))
    if not os.path.isfile(p):
        raise RouteError(f"{relpath} not found at {p}")
    spec = importlib.util.spec_from_file_location(modname, p)
    if spec is None or spec.loader is None:
        raise RouteError(f"cannot load {relpath}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _stamp_releases(res: RouteResult) -> None:
    """Best-effort: detect the Revit release of every delivered .rvt/.rfa."""
    try:
        from .. import versions as V
    except Exception:                                            # pragma: no cover
        return
    for role, p in list(res.files.items()):
        if not (isinstance(p, str) and p.lower().endswith((".rvt", ".rfa"))
                and os.path.isfile(p)):
            continue
        try:
            res.releases[role] = V.detect_release(p)
        except Exception:                                        # noqa: BLE001
            res.releases[role] = None


def _absorb_author_result(res: RouteResult, r: Any) -> None:
    """Fold an AuthorResult (rvt.frontdoor.author) into the RouteResult:
    files, intermediate artifacts, stamps, errors, manifests."""
    for role, p in (r.files or {}).items():
        if isinstance(p, dict):
            p = p.get("path")
        if p:
            res.files[role] = (p if os.path.isabs(str(p))
                               else os.path.join(repo_root(), str(p)))
    if r.intent_json:
        res.files["intent"] = r.intent_json
    for k, p in (r.handoff or {}).items():
        if k != "primary_path_note" and isinstance(p, str):
            res.files[f"handoff:{k}"] = (p if os.path.isabs(p)
                                         else os.path.join(repo_root(), p))
    for k, p in (r.manifest_paths or {}).items():
        res.manifest_paths[f"author:{k}"] = p
    verdict = ((r.manifest or {}).get("build") or {}).get("combination_verdict") or {}
    if verdict.get("stamp"):
        res.stamps.append(str(verdict["stamp"]))
    status = str(r.status or "")
    if "PROOF-ONLY" in status.upper() and status not in res.stamps:
        res.stamps.append(status)
    tv = (r.manifest or {}).get("target_version") or {}
    if tv.get("line"):
        res.caveats.append(str(tv["line"]))
    res.errors.extend([str(e) for e in (r.errors or [])])


_AUTHOR_OPTS = ("base", "strict", "stages", "wall_mode", "specimens",
                "symbol_hollow", "no_validate", "strict_validate", "stem",
                "target_version", "handoff_only", "no_handoff")


def _author_kwargs(opts: Dict[str, Any]) -> Dict[str, Any]:
    return {k: opts[k] for k in _AUTHOR_OPTS if k in opts and opts[k] is not None}


def _read_famspec(rfa: Any) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """The rfa input contract: a famspec dict, a path to a famspec .json,
    or a .rfa path (returned as second element -- refused by the cells that
    cannot reload it)."""
    if isinstance(rfa, dict):
        return dict(rfa), None
    s = str(rfa)
    if s.lower().endswith(".rfa"):
        return None, os.path.abspath(s)
    if os.path.isfile(s) and s.lower().endswith(".json"):
        with open(s) as fh:
            d = json.load(fh)
        if not isinstance(d, dict):
            raise RouteError(f"famspec {s} must be a JSON object with a 'kind'")
        return d, None
    if s.strip().startswith("{"):
        d = json.loads(s)
        return (d if isinstance(d, dict) else None), None
    raise RouteError(f"rfa input {rfa!r} is neither a famspec JSON (dict / "
                     ".json path / inline) nor a .rfa path")


# ===========================================================================
# route implementations -- each composes EXISTING stage functions
# ===========================================================================

def _r_author_single(res: RouteResult, inputs: Dict[str, Any], out_dir: str,
                     opts: Dict[str, Any], *, kind: str) -> None:
    """prompt->rvt / ifc->rvt / (prompt+rvt edit) via the composite
    front-door entrypoint (rvt.frontdoor.author -- the certified pipeline)."""
    import rvt.frontdoor as FD
    steps = _Steps(res)
    kw = _author_kwargs(opts)
    if kind == "prompt":
        r = steps.run("prompt->intent + intent->rvt", "rvt.frontdoor:author",
                      lambda: FD.author(prompt=inputs["prompt"], out=out_dir, **kw))
    elif kind == "ifc":
        r = steps.run("ifc->intent + intent->rvt", "rvt.frontdoor:author",
                      lambda: FD.author(ifc=inputs["ifc"], out=out_dir, **kw))
    else:                                                        # rvt edit
        r = steps.run("rvt-read + rvt-edit", "rvt.frontdoor:author",
                      lambda: FD.author(rvt=inputs["rvt"], edit=inputs["prompt"],
                                        out=out_dir, **kw))
    _absorb_author_result(res, r)
    res.ok = bool(r.ok)
    res.status = str(r.status)


def _r_prompt_to_rvt(res, inputs, out_dir, opts):
    if opts.get("via") == "ifc":
        return _r_prompt_via_ifc_to_rvt(res, inputs, out_dir, opts)
    _r_author_single(res, inputs, out_dir, opts, kind="prompt")


def _r_ifc_to_rvt(res, inputs, out_dir, opts):
    if opts.get("via") == "family":
        return _r_ifc_family_load(res, inputs, out_dir, opts)
    _r_author_single(res, inputs, out_dir, opts, kind="ifc")
    # a PRODUCT IFC (no room, no equipment intent) falls back to the family chain
    if not res.ok and not res.files.get("combined") and opts.get("via") is None:
        nothing = any("nothing buildable" in e or "IFC intent failed" in e
                      for e in res.errors)
        if nothing:
            res.caveats.append("room route found nothing buildable -- fell back "
                               "to the PRODUCT-IFC family chain (ifc->facts->"
                               "rfa->loaded rvt)")
            res.errors.append("(room route errors above pre-date the fallback)")
            _r_ifc_family_load(res, inputs, out_dir, opts)


def _r_rvt_edit(res, inputs, out_dir, opts):
    """prompt+rvt: EDIT when the prompt is edit-shaped; else the authoring
    prompt is built with the user's .rvt as BASE (the partial branch)."""
    from . import edit as E
    from ..mutate import Document
    prompt = str(inputs["prompt"])
    edit_shaped = True
    try:
        doc = Document.from_file(inputs["rvt"])
        E.parse_edit_spec(prompt, doc=doc)
    except E.EditParseError:
        edit_shaped = False
    except Exception:                        # unreadable file -> let author report it
        edit_shaped = True
    if edit_shaped:
        return _r_author_single(res, inputs, out_dir, opts, kind="rvt")
    # authoring-shaped prompt: build ON the user's file as base (partial)
    res.caveats.append(
        "the prompt did not parse as an EDIT; built as an authoring prompt "
        "with your .rvt as the BASE -- certified stage code + gates run, but "
        "no viewer certification exists on arbitrary bases (PARTIAL branch "
        "of the prompt+rvt cell)")
    o2 = dict(opts)
    o2["base"] = inputs["rvt"]
    _r_author_single(res, {"prompt": prompt}, out_dir, o2, kind="prompt")


def _r_ifc_onto_rvt(res, inputs, out_dir, opts):
    o2 = dict(opts)
    o2["base"] = inputs["rvt"]
    _r_author_single(res, inputs, out_dir, o2, kind="ifc")
    res.caveats.append(
        "MERGE semantics: the IFC intent was built with your .rvt as the "
        "base; viewer certification exists only for the genesis base -- "
        "this output is gate-checked but viewer-unverified (PARTIAL cell)")


def _r_ifc_build_then_edit(res, inputs, out_dir, opts):
    """prompt+ifc: build the IFC, then apply the prompt as an EDIT."""
    from . import edit as E
    from ..mutate import Document
    import rvt.frontdoor as FD
    steps = _Steps(res)
    build_dir = os.path.join(out_dir, "build")
    kw = _author_kwargs(opts)
    r1 = steps.run("ifc->intent + intent->rvt", "rvt.frontdoor:author",
                   lambda: FD.author(ifc=inputs["ifc"], out=build_dir, **kw))
    _absorb_author_result(res, r1)
    built = None
    for role in ("combined", "equipment", "shell"):
        p = (r1.files or {}).get(role)
        if isinstance(p, dict):
            p = p.get("path")
        if p and not os.path.isabs(str(p)):
            p = os.path.join(repo_root(), str(p))
        if p and os.path.isfile(p):
            built = p
            break
    if not built:
        res.ok = False
        res.status = "FAILED (the ifc leg produced no .rvt to edit)"
        return
    prompt = str(inputs["prompt"])
    try:
        doc = Document.from_file(built)
        E.parse_edit_spec(prompt, doc=doc)
    except E.EditParseError as e:
        res.ok = False
        res.status = ("FAILED (the prompt is not an edit): intent-level "
                      "merge of a prompt into an IFC is not built yet")
        res.line = (f"prompt+ifc -> rvt runs [ifc->rvt] then applies the prompt "
                    f"as an EDIT; this prompt is not edit-shaped ({e}). "
                    "Closest: edit sentences ('move MSB to 3,4; rename panel "
                    "LP-1 to LP-9'), or drop the prompt for a plain ifc -> rvt.")
        return
    r2 = steps.run("rvt-read + rvt-edit", "rvt.frontdoor:author",
                   lambda: FD.author(rvt=built, edit=prompt, out=out_dir, **kw))
    _absorb_author_result(res, r2)
    res.ok = bool(r2.ok)
    res.status = str(r2.status)
    res.caveats.append("composition of two proven stages (ifc->rvt, then the "
                       "certified edit pipeline); no single-artifact "
                       "certification of the composed route (PARTIAL cell)")


def _r_prompt_to_ifc(res, inputs, out_dir, opts):
    from . import prompt_intent as PP
    from . import intent as FI
    from . import ifc_out as IO
    steps = _Steps(res)
    model, parsed = steps.run("prompt->intent",
                              "rvt.frontdoor.prompt_intent:prompt_to_intent",
                              lambda: PP.prompt_to_intent(str(inputs["prompt"])))
    intent_json = os.path.join(out_dir, "intent.json")
    steps.run("intent->json", "rvt.frontdoor.intent:write_intent_json",
              lambda: FI.write_intent_json(model, intent_json))
    res.files["intent"] = intent_json
    stem = _slug(opts.get("stem") or "prompt_intent")
    ifc_path = os.path.join(out_dir, f"{stem}.ifc")
    steps.run("intent->ifc", "rvt.frontdoor.ifc_out:write_intent_ifc",
              lambda: IO.write_intent_ifc(model, ifc_path))
    res.files["ifc"] = ifc_path
    cov = parsed.coverage.as_json() if getattr(parsed, "coverage", None) else None
    if cov:
        cov_p = os.path.join(out_dir, "prompt-coverage.json")
        with open(cov_p, "w") as fh:
            json.dump(cov, fh, indent=1, default=str)
        res.files["prompt_coverage"] = cov_p
    res.ok = True
    res.status = "OK (deterministic IFC4 of the resolved intent; version-agnostic)"


def _r_ifc_normalize(res, inputs, out_dir, opts):
    from . import intent as FI
    from . import ifc_out as IO
    steps = _Steps(res)
    model = steps.run("ifc->intent", "rvt.frontdoor.intent:intent_from_ifc",
                      lambda: FI.intent_from_ifc(inputs["ifc"]))
    intent_json = os.path.join(out_dir, "intent.json")
    steps.run("intent->json", "rvt.frontdoor.intent:write_intent_json",
              lambda: FI.write_intent_json(model, intent_json))
    res.files["intent"] = intent_json
    stem = _slug(opts.get("stem")
                 or os.path.splitext(os.path.basename(inputs["ifc"]))[0] + ".normalized")
    ifc_path = os.path.join(out_dir, f"{stem}.ifc")
    steps.run("intent->ifc", "rvt.frontdoor.ifc_out:write_intent_ifc",
              lambda: IO.write_intent_ifc(model, ifc_path))
    res.files["ifc"] = ifc_path
    res.ok = True
    res.status = ("OK (normalised into our tagging-contract dialect; content "
                  "outside the resolved intent does not survive)")


def _families_from_model(res: RouteResult, model, out_dir: str) -> Dict[str, Any]:
    """stage_families (tools/ifc_intent.py, reused as-is) -> families/*.rfa."""
    from . import build as B
    steps = _Steps(res)
    R = B.load_ifc_room_module()
    frec = steps.run("intent->rfa", "tools/ifc_intent.py:stage_families",
                     lambda: R.stage_families(model, out_dir))
    def _ab(p: str) -> str:
        return p if os.path.isabs(p) else os.path.join(repo_root(), p)

    fam_dir = frec.get("dir") or os.path.join(out_dir, "families")
    res.files["families_dir"] = _ab(fam_dir)
    for f in frec.get("families") or []:
        if f.get("built") and f.get("path"):
            res.files[f"rfa:{f.get('tag') or f.get('family_name')}"] = _ab(f["path"])
    for f in frec.get("families") or []:
        if not f.get("built"):
            res.caveats.append(f"{f.get('tag')}: NOT built -- {f.get('status')}"
                               + (f" ({f.get('refusal')})" if f.get("refusal") else ""))
    return frec


def _r_prompt_to_rfa(res, inputs, out_dir, opts):
    from . import prompt_intent as PP
    from . import intent as FI
    steps = _Steps(res)
    model, _parsed = steps.run("prompt->intent",
                               "rvt.frontdoor.prompt_intent:prompt_to_intent",
                               lambda: PP.prompt_to_intent(str(inputs["prompt"])))
    intent_json = os.path.join(out_dir, "intent.json")
    FI.write_intent_json(model, intent_json)
    res.files["intent"] = intent_json
    frec = _families_from_model(res, model, out_dir)
    built = int(frec.get("built") or 0)
    res.ok = built > 0
    res.status = (f"OK ({built} family .rfa generated; refusals honest)"
                  if res.ok else
                  "FAILED (no family plan in this prompt could be built -- "
                  "see caveats for every refusal)")


def _r_ifc_to_rfa(res, inputs, out_dir, opts):
    """Room IFC -> catalog families; PRODUCT IFC -> the measured downlight."""
    from . import intent as FI
    steps = _Steps(res)
    model = None
    try:
        model = steps.run("ifc->intent", "rvt.frontdoor.intent:intent_from_ifc",
                          lambda: FI.intent_from_ifc(inputs["ifc"]))
    except _StepFailed:
        pass
    plans = []
    if model is not None:
        plans = FI.buildable_family_plans(model)
        if plans:
            intent_json = os.path.join(out_dir, "intent.json")
            FI.write_intent_json(model, intent_json)
            res.files["intent"] = intent_json
            frec = _families_from_model(res, model, out_dir)
            built = int(frec.get("built") or 0)
            res.ok = built > 0
            res.status = f"OK ({built} catalog family .rfa from the room IFC)"
            return
    res.caveats.append("no buildable room-equipment family plan in this IFC -- "
                       "took the PRODUCT-IFC path (measured facts -> the "
                       "downlight archetype)")
    _product_rfa(res, inputs["ifc"], out_dir, opts)


def _product_rfa(res: RouteResult, ifc_path: str, out_dir: str,
                 opts: Dict[str, Any]) -> Optional[Any]:
    """PRODUCT IFC -> facts -> our downlight family .rfa (the certified
    archetype).  Returns the DownlightProduct or None."""
    from ..ifc import product_facts as PF
    from ..ifc import famfrom_ifc as FFI
    steps = _Steps(res)
    facts = steps.run("ifc->facts", "rvt.ifc.product_facts:extract_product_facts",
                      lambda: PF.extract_product_facts(ifc_path))
    facts_p = os.path.join(out_dir, "product-facts.json")
    steps.run("facts->json", "rvt.ifc.product_facts:write_facts_record",
              lambda: PF.write_facts_record(facts, facts_p))
    res.files["product_facts"] = facts_p
    prod = steps.run("facts->rfa", "rvt.ifc.famfrom_ifc:make_downlight",
                     lambda: FFI.make_downlight(facts=facts))
    stem = _slug(opts.get("stem") or getattr(prod.doc, "name", "downlight"))
    rfa_path = os.path.join(out_dir, f"{stem}.rfa")
    rep = steps.run("rfa-emit", "rvt.ifc.famfrom_ifc:DownlightProduct.write_rfa",
                    lambda: prod.write_rfa(rfa_path))
    res.files["rfa"] = rfa_path
    if rep.get("report_path"):
        res.files["rfa_report"] = rep["report_path"]
    ok = bool(((rep.get("validate") or {}).get("verdict") == "VALID")
              or os.path.isfile(rfa_path))
    res.ok = ok
    res.status = ("OK (measured product family emitted; validator family-mode)"
                  if ok else "FAILED (family emit did not validate)")
    return prod


def _r_ifc_family_load(res, inputs, out_dir, opts):
    """The ifc->rfa->loaded-rvt chain (the L_downlight_loaded pipeline)."""
    from ..ifc import famfrom_ifc as FFI
    prod = _product_rfa(res, inputs["ifc"], out_dir, opts)
    if prod is None or not res.ok:
        return
    _load_family(res, out_dir, opts,
                 host=inputs.get("rvt"),
                 builder=lambda start_id=100000: FFI.make_downlight(
                     ifc_path=inputs["ifc"], start_id=start_id).doc,
                 name=_slug(getattr(prod.doc, "name", "downlight")))


def _load_family(res: RouteResult, out_dir: str, opts: Dict[str, Any], *,
                 host: Optional[str], builder, name: str) -> None:
    """The certified four-registry LOAD (rvt.famload via
    famfrom_ifc.load_into_project)."""
    from ..ifc import famfrom_ifc as FFI
    steps = _Steps(res)
    host_rvt = host or FFI.HOST_RST
    if host is None:
        res.caveats.append("no host .rvt supplied: loaded into the loader-"
                           "certified rst host (the exact host of the "
                           "viewer-certified L1a / L_downlight_loaded proofs)")
    else:
        res.caveats.append("loaded into YOUR host project: the four-registry "
                           "mechanism + census/validator gates ran; viewer "
                           "certification exists for the rst host and the "
                           "genesis lineage, not for arbitrary hosts")
    out_rvt = os.path.join(out_dir, f"{name}_loaded.rvt")
    rep = steps.run("rfa-load", "rvt.ifc.famfrom_ifc:load_into_project "
                                "(rvt.famload four-registry)",
                    lambda: FFI.load_into_project(host_rvt, out_rvt,
                                                  builder=builder, name=name))
    res.files["loaded_rvt"] = out_rvt
    rep_json = os.path.join(out_dir, f"{name}_load-report.json")
    with open(rep_json, "w") as fh:
        json.dump(rep.as_json(), fh, indent=1, default=str)
    res.files["load_report"] = rep_json
    ok = bool(rep.ok and os.path.isfile(out_rvt)
              and (rep.validate_project_mode or {}).get("verdict") == "VALID")
    res.ok = ok
    res.status = ("OK (family loaded four-registry; project validates 0 errors)"
                  if ok else
                  f"FAILED (load: {rep.stop_reason or rep.error or 'see report'})")


_FAMSPEC_KINDS = ("downlight",)


def _r_famspec_load(res, inputs, out_dir, opts):
    """rfa[+rvt] -> rvt: famspec -> our .rfa -> loaded project."""
    from ..ifc import famfrom_ifc as FFI
    famspec, rfa_path = _read_famspec(inputs["rfa"])
    if rfa_path is not None:
        res.ok = False
        res.status = "UNSUPPORTED-INPUT-FORM (.rfa reload from disk)"
        res.line = ("a bare .rfa path cannot be reloaded from disk yet (no "
                    ".rfa->FamilyDoc reconstitution exists); supply the "
                    "famspec JSON ({'kind': 'downlight', ...}) that generated "
                    "it -- the family is REBUILT by its constructor and "
                    "loaded through the certified four-registry loader. "
                    "Closest: rfa(famspec)[+rvt] -> rvt, or prompt -> rfa.")
        return
    kind = str((famspec or {}).get("kind") or "").strip().lower()
    if kind not in _FAMSPEC_KINDS:
        res.ok = False
        res.status = f"UNSUPPORTED-FAMSPEC-KIND ({kind or 'unset'})"
        res.line = (f"famspec kind {kind!r} is not wired for a standalone "
                    f"LOAD (wired: {', '.join(_FAMSPEC_KINDS)}). Catalog "
                    "kinds (panelboard / transformer / luminaire) generate "
                    "as .rfa via prompt->rfa / spec->rfa and LOAD through "
                    "the room pipeline (prompt/ifc -> rvt).")
        return
    kw = {k: v for k, v in (famspec or {}).items() if k != "kind"}
    steps = _Steps(res)
    prod = steps.run("facts->rfa", "rvt.ifc.famfrom_ifc:make_downlight",
                     lambda: FFI.make_downlight(**kw))
    name = _slug(opts.get("stem") or getattr(prod.doc, "name", "downlight"))
    rfa_out = os.path.join(out_dir, f"{name}.rfa")
    steps.run("rfa-emit", "rvt.ifc.famfrom_ifc:DownlightProduct.write_rfa",
              lambda: prod.write_rfa(rfa_out))
    res.files["rfa"] = rfa_out
    _load_family(res, out_dir, opts, host=inputs.get("rvt"),
                 builder=lambda start_id=100000: FFI.make_downlight(
                     start_id=start_id, **kw).doc,
                 name=name)


def _spec_to_ifc_file(res: RouteResult, spec: str, out_dir: str,
                      opts: Dict[str, Any]) -> str:
    steps = _Steps(res)
    gen = _load_tool("skills/tekton-ifc/scripts/generate_ifc.py", "_route_generate_ifc")
    stem = _slug(opts.get("stem")
                 or os.path.splitext(os.path.basename(spec))[0])
    ifc_path = os.path.join(out_dir, f"{stem}.ifc")

    def run() -> int:
        rc = int(gen.main(["--spec", spec, "-o", ifc_path]))
        if rc != 0 or not os.path.isfile(ifc_path):
            raise RuntimeError(f"generate_ifc.py exited {rc}")
        return rc

    steps.run("spec->ifc", "skills/tekton-ifc/scripts/generate_ifc.py:main", run)
    res.files["ifc"] = ifc_path
    return ifc_path


def _r_spec_to_ifc(res, inputs, out_dir, opts):
    _spec_to_ifc_file(res, inputs["spec"], out_dir, opts)
    res.ok = True
    res.status = "OK (deterministic IFC4 from the building spec)"


def _r_spec_to_rvt(res, inputs, out_dir, opts):
    ifc_path = _spec_to_ifc_file(res, inputs["spec"], out_dir, opts)
    _r_author_single(res, {"ifc": ifc_path}, out_dir, opts, kind="ifc")


def _r_spec_to_rfa(res, inputs, out_dir, opts):
    from . import intent as FI
    ifc_path = _spec_to_ifc_file(res, inputs["spec"], out_dir, opts)
    steps = _Steps(res)
    model = steps.run("ifc->intent", "rvt.frontdoor.intent:intent_from_ifc",
                      lambda: FI.intent_from_ifc(ifc_path))
    intent_json = os.path.join(out_dir, "intent.json")
    FI.write_intent_json(model, intent_json)
    res.files["intent"] = intent_json
    frec = _families_from_model(res, model, out_dir)
    built = int(frec.get("built") or 0)
    res.ok = built > 0
    res.status = (f"OK ({built} catalog family .rfa from the spec's tagged "
                  "equipment)" if res.ok else
                  "FAILED (no catalog-coverable equipment in this spec -- "
                  "see caveats for every refusal)")


def _r_spec_on_rvt_seed(res, inputs, out_dir, opts):
    """spec+rvt: the job runner's CREATE mode (seed audit + hard gates)."""
    from . import edit as E
    steps = _Steps(res)
    J = E.load_job_module()
    stem = _slug(opts.get("stem")
                 or os.path.splitext(os.path.basename(inputs["spec"]))[0])
    out_rvt = os.path.join(out_dir, f"{stem}.rvt")
    argv = ["create", "--spec", inputs["spec"], "--base", inputs["rvt"],
            "-o", out_rvt]
    if opts.get("no_validate"):
        argv.append("--no-validate")

    def run() -> int:
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = int(J.main(argv))
        log_p = os.path.join(out_dir, "job-create.log")
        with open(log_p, "w") as fh:
            fh.write(buf.getvalue())
        res.files["job_log"] = log_p
        return rc

    rc = steps.run("spec->rvt-legacy", "tools/rvt_job.py:main create", run)
    if os.path.isfile(out_rvt):
        res.files["rvt"] = out_rvt
    for suffix, role in ((".manifest.json", "job_manifest"),
                         (".validation.json", "job_validation")):
        p = out_rvt + suffix
        if os.path.isfile(p):
            res.manifest_paths[role] = p
    res.caveats.append("your .rvt is the SEED/TEMPLATE: authored content "
                       "clones its loaded types; the output is ledgered "
                       "against that seed (PROOF-ONLY vs what you supplied)")
    res.ok = (rc == 0 and os.path.isfile(out_rvt))
    res.status = ("OK (job runner create: hard gates passed; status in the "
                  "job manifest)" if res.ok
                  else f"FAILED (rvt_job.py create exited {rc})")


def _r_prompt_via_ifc_to_rvt(res, inputs, out_dir, opts):
    """The chain prompt->ifc->rvt: emit the intent's IFC, re-enter via ifc."""
    _r_prompt_to_ifc(res, inputs, out_dir, opts)
    if not res.ok:
        return
    ifc_path = res.files.get("ifc")
    # keep BOTH intents: the prompt leg's, and the ifc leg's re-resolution
    p1 = res.files.get("intent")
    if p1 and os.path.isfile(p1):
        p1b = os.path.join(out_dir, "intent-from-prompt.json")
        os.replace(p1, p1b)
        res.files["intent_from_prompt"] = p1b
    res.caveats.append("chain: the prompt's intent was emitted as IFC and "
                       "re-entered through the ifc route (the handoff round "
                       "trip, run in-process)")
    _r_author_single(res, {"ifc": ifc_path}, out_dir, opts, kind="ifc")


_IMPLS: Dict[str, Callable[..., None]] = {
    "prompt_to_rvt": _r_prompt_to_rvt,
    "prompt_to_ifc": _r_prompt_to_ifc,
    "prompt_to_rfa": _r_prompt_to_rfa,
    "ifc_to_rvt": _r_ifc_to_rvt,
    "ifc_normalize": _r_ifc_normalize,
    "ifc_to_rfa": _r_ifc_to_rfa,
    "famspec_load": _r_famspec_load,
    "spec_to_rvt": _r_spec_to_rvt,
    "spec_to_ifc": _r_spec_to_ifc,
    "spec_to_rfa": _r_spec_to_rfa,
    "rvt_edit": _r_rvt_edit,
    "ifc_onto_rvt": _r_ifc_onto_rvt,
    "ifc_build_then_edit": _r_ifc_build_then_edit,
    "spec_on_rvt_seed": _r_spec_on_rvt_seed,
    "prompt_via_ifc_to_rvt": _r_prompt_via_ifc_to_rvt,
    "ifc_family_load": _r_ifc_family_load,
}


def route_ids() -> List[str]:
    return sorted(_IMPLS)


# ===========================================================================
# THE ENTRYPOINT
# ===========================================================================

def route(inputs: Dict[str, Any], output: str, **opts: Any) -> RouteResult:
    """Route any permutation: ``inputs`` = {kind: value} over
    {prompt, ifc, rvt, rfa, spec}; ``output`` in {rvt, rfa, ifc}.

    Supported cells execute their stage chain and DELIVER (final output +
    every intermediate + the route manifest).  Missing/unknown cells return
    ``ok=False`` with THE one clear line (``.line``) -- never a traceback.
    """
    t0 = time.time()
    inputs = _norm_inputs(inputs)
    if output not in MX.OUTPUT_KINDS:
        raise RouteError(f"unknown output {output!r} (outputs: "
                         f"{', '.join(MX.OUTPUT_KINDS)})")
    if not inputs:
        raise RouteError("no input given (inputs: "
                         f"{', '.join(MX.INPUT_KINDS)})")
    cell = MX.cell_for(list(inputs), output)
    res = RouteResult(ok=False, status="", cell=(cell.as_json() if cell else None))

    if cell is None or cell.status == MX.STATUS_MISSING or cell.route is None:
        res.status = "UNSUPPORTED"
        res.line = MX.unsupported_line(list(inputs), output)
        res.seconds = round(time.time() - t0, 1)
        return res

    impl = _IMPLS.get(cell.route)
    if impl is None:                                             # pragma: no cover
        res.status = "UNSUPPORTED"
        res.line = (f"matrix names route {cell.route!r} but the router has no "
                    "implementation registered -- this is a matrix/router "
                    "drift bug (tests/test_router.py guards it)")
        res.seconds = round(time.time() - t0, 1)
        return res

    out_dir = _out_dir(opts, inputs, output)
    os.makedirs(out_dir, exist_ok=True)
    res.out_dir = out_dir
    res.route = cell.route
    res.caveats.extend(cell.caveats)

    try:
        impl(res, inputs, out_dir, opts)
    except _StepFailed:
        res.ok = False
        if not res.status:
            res.status = f"FAILED ({res.errors[-1] if res.errors else 'stage failed'})"
    except RouteError:
        raise
    except Exception as e:                                       # noqa: BLE001
        res.ok = False
        res.errors.append(f"route crashed: {type(e).__name__}: {e}")
        res.errors.append(traceback.format_exc(limit=6))
        res.status = f"FAILED ({type(e).__name__}: {e})"

    _stamp_releases(res)
    res.seconds = round(time.time() - t0, 1)
    try:
        _write_route_manifest(res, inputs, output, opts)
    except Exception as e:                                       # noqa: BLE001
        res.errors.append(f"route manifest write failed: {type(e).__name__}: {e}")
    return res


# ---------------------------------------------------------------------------
# the route manifest (route.json + ROUTE.md)
# ---------------------------------------------------------------------------

def _relp(p: Any) -> Any:
    if not isinstance(p, str):
        return p
    try:
        r = os.path.relpath(p, repo_root())
        return r if not r.startswith("..") else p
    except ValueError:
        return p


def _write_route_manifest(res: RouteResult, inputs: Dict[str, Any],
                          output: str, opts: Dict[str, Any]) -> None:
    if not res.out_dir:
        return
    man = {
        "router": "rvt.frontdoor.router (perm-matrix stream)",
        "request": {"inputs": {k: _relp(v) if isinstance(v, str) else v
                               for k, v in inputs.items()},
                    "output": output,
                    "opts": {k: v for k, v in opts.items() if k != "out"}},
        "cell": res.cell,
        "route": res.route,
        "ok": res.ok,
        "status": res.status,
        "steps": res.steps,
        "files": {k: _relp(v) for k, v in res.files.items()},
        "releases": res.releases,
        "stamps": res.stamps,
        "caveats": res.caveats,
        "evidence": (res.cell or {}).get("evidence"),
        "errors": res.errors,
        "seconds": res.seconds,
        "deliverable_rule": ("gates are labels: the output files above ARE "
                             "delivered; every caveat/stamp rides AFTER the "
                             "delivery, never instead of it"),
    }
    jp = os.path.join(res.out_dir, "route.json")
    with open(jp, "w") as fh:
        json.dump(man, fh, indent=1, default=str)
    res.manifest_paths["route.json"] = jp

    lines = [f"# route: {'+'.join(sorted(inputs))} -> {output}", ""]
    lines.append(f"* ok: **{res.ok}** -- {res.status}")
    if res.line:
        lines.append(f"* {res.line}")
    c = res.cell or {}
    lines.append(f"* matrix cell: status **{c.get('status')}**, route "
                 f"`{res.route}`, stages: {' -> '.join(c.get('stages') or [])}")
    if res.files:
        lines.append("* delivered:")
        for k, v in res.files.items():
            rel = _relp(v)
            rl = res.releases.get(k)
            lines.append(f"  * `{k}` -> `{rel}`" + (f" (Revit {rl})" if rl else ""))
    if res.stamps:
        lines.append("* stamps: " + "; ".join(res.stamps))
    if res.caveats:
        lines.append("* caveats (after delivery, per the deliverable rule):")
        lines.extend(f"  * {cv}" for cv in res.caveats)
    if c.get("evidence"):
        lines.append("* evidence cited by the matrix: "
                     + "; ".join(c["evidence"]))
    if res.errors:
        lines.append("* errors:")
        lines.extend(f"  * {str(e).splitlines()[0][:200]}" for e in res.errors[:8])
    lines.append(f"* seconds: {res.seconds}")
    mp = os.path.join(res.out_dir, "ROUTE.md")
    with open(mp, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    res.manifest_paths["ROUTE.md"] = mp
