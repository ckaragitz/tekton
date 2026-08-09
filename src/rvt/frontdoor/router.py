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

The ``rvt.convert`` implementations are registered here as-is (issue #5):
rvt->ifc (``rvt_to_ifc``), rvt->rfa (``extract_family``, selector in
``opts['family']``), prompt+rfa->rfa (``modify_family``), the
authoring-shaped branch of prompt+rvt (``add_to_project``), ifc+rvt
(``merge_ifc``) and the extracted-.rfa reload lane of rfa[+rvt]->rvt
(``extract_family.reload_family``).  Their own manifests ride beside the
route manifest; their gates are folded into the status line as labels.

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
    # the rfa slot carries a famspec (dict / .json / inline JSON) OR a .rfa
    # path; a .rfa path that does not exist is a usage error like any other
    rfa = out.get("rfa")
    if isinstance(rfa, str) and rfa.lower().endswith(".rfa"):
        p = os.path.abspath(rfa)
        if not os.path.isfile(p):
            raise RouteError(f"--rfa file not found: {rfa}")
        out["rfa"] = p
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


def _default_host() -> Tuple[str, str]:
    """The default LOAD HOST when no rvt is supplied: the pinned, hash-verified
    certified genesis base (repo copy or the plugin-bundled one) -- never an
    Autodesk sample.  Returns (path, one-line description); raises
    :class:`rvt.frontdoor.base.BaseError` when the pin cannot be resolved."""
    from .base import resolve_base
    rb = resolve_base()
    return rb.path, (f"the pinned certified genesis base ({rb.source}, sha256 "
                     f"{rb.sha256[:12]}...)")


def _resolve_host(res: RouteResult, host: Optional[str], *, verb: str) -> Optional[str]:
    """``host`` when given (the user's project), else the default host; on a
    missing pin returns None after setting a FAILED status + the clear line
    (never a traceback)."""
    if host is not None:
        return host
    try:
        path, desc = _default_host()
    except Exception as e:                                           # noqa: BLE001
        res.ok = False
        res.status = f"FAILED (no host project: {type(e).__name__}: {e})"
        res.line = (f"rfa -> rvt {verb}s the family INTO a host project: pass --rvt "
                    "<your.rvt>, or restore the pinned genesis base "
                    "(rvt/frontdoor/assets/genesis_base.json / $RVT_GENESIS_BASE).")
        return None
    res.caveats.append(f"no host .rvt supplied: {verb}ed into {desc} -- the "
                       "certified base every build route authors on")
    return path


def _abs_repo(p: Any) -> Any:
    if isinstance(p, str) and p and not os.path.isabs(p):
        return os.path.join(repo_root(), p)
    return p


def _absorb_convert_record(res: RouteResult, rec: Dict[str, Any], *,
                           prefix: str) -> Dict[str, Any]:
    """Fold an rvt.convert manifest record (add_to_project / merge_ifc /
    modify_family / extract_family / rvt_to_ifc share the shape) into the
    RouteResult: delivered files, stamps, caveats-after-delivery, manifest
    paths, errors.  Returns {'verdicts': {role: 'VALID'|...}, 'all_valid':
    bool} from the record's own gates (labels, never withholding)."""
    for role, p in (rec.get("files") or {}).items():
        p = _abs_repo(p)
        if isinstance(p, str) and p and (os.path.isfile(p) or os.path.isdir(p)):
            res.files[role] = p
    for c in rec.get("created") or []:
        if c.get("kind") == "family(.rfa)" and c.get("path"):
            p = _abs_repo(str(c["path"]))
            if os.path.isfile(p):
                res.files[f"rfa:{c.get('tag') or c.get('name')}"] = p
    for s in rec.get("stamps") or []:
        if s and s not in res.stamps:
            res.stamps.append(str(s))
    vstamp = (rec.get("verdict") or {}).get("stamp")
    if vstamp and vstamp not in res.stamps:
        res.stamps.append(str(vstamp))
    for d in rec.get("degradations") or []:
        res.caveats.append(str(d))
    for e in rec.get("errors") or []:
        res.errors.append(str(e))
    out_dir = res.out_dir or ""
    for name, role in (("manifest.json", f"{prefix}:json"), ("MANIFEST.md", f"{prefix}:md")):
        p = os.path.join(out_dir, name)
        if os.path.isfile(p):
            res.manifest_paths[role] = p
    verdicts: Dict[str, str] = {}
    val = rec.get("validation") or {}
    if isinstance(val, dict) and isinstance(val.get("family_mode"), dict):
        val = {"rfa": val}                     # extract_family's flat gate record
    for role, g in (val.items() if isinstance(val, dict) else ()):
        if not isinstance(g, dict):
            continue
        v = g.get("validate") or g.get("family_mode") or {}
        verdicts[role] = str(v.get("verdict") or "UNKNOWN")
    return {"verdicts": verdicts,
            "all_valid": bool(verdicts) and all(v == "VALID" for v in verdicts.values())}


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


def _edit_shaped(prompt: str) -> bool:
    """Is the prompt an EDIT (ops.json path, inline JSON ops, or a sentence
    of the edit grammar) rather than an authoring prompt?  Decided on SHAPE
    alone, without the file: a grammar clause whose NAME does not resolve
    ('move DP-1 to 3,4' on a file with no DP-1) is still an edit -- the edit
    pipeline then reports the unresolved name honestly instead of the
    sentence being re-read as 'add a DP-1'."""
    from . import edit as E
    try:
        E.parse_edit_spec(prompt, doc=None)
        return True
    except E.EditParseError as e:
        return "no edit understood" not in str(e) and "empty --edit" not in str(e)
    except Exception:                                                # noqa: BLE001
        return True


def _r_rvt_edit(res, inputs, out_dir, opts):
    """prompt+rvt: EDIT when the prompt is edit-shaped (the certified edit
    pipeline); an AUTHORING-shaped prompt ('add a 100 A lighting panel to
    my project') is ADDED INTO the user's file by rvt.convert.add_to_project."""
    if _edit_shaped(str(inputs["prompt"])):
        return _r_author_single(res, inputs, out_dir, opts, kind="rvt")
    res.caveats.append(
        "the prompt did not parse as an EDIT: taken as an authoring prompt "
        "and ADDED INTO your project (rvt.convert.add_to_project -- new "
        "equipment generated, loaded and placed beside your content)")
    _r_add_into_rvt(res, inputs, out_dir, opts)


def _convert_status(res: RouteResult, gates: Dict[str, Any], *, what: str,
                    delivered: bool) -> None:
    """One status rule for the INTO/convert routes: delivered + all gates
    VALID -> OK; delivered with a red gate -> DELIVERED (label); nothing
    delivered -> FAILED.  ok == a deliverable exists (the deliverable rule:
    gates are labels, never refusals)."""
    verdicts = gates.get("verdicts") or {}
    verd = ", ".join(f"{k} {v}" for k, v in verdicts.items()) or "no gate ran (--no-validate)"
    if delivered and (gates.get("all_valid") or not verdicts):
        res.ok = True
        res.status = f"OK ({what}; validator {verd})"
    elif delivered:
        res.ok = True
        res.status = (f"DELIVERED WITH A RED GATE ({what}; validator {verd}) -- "
                      "the file is delivered, the label rides with it")
    else:
        res.ok = False
        res.status = f"FAILED ({what}: no output file was produced -- see errors)"


def _r_add_into_rvt(res, inputs, out_dir, opts):
    """prompt+rvt (authoring-shaped): rvt.convert.add_to_project."""
    from ..convert import add_to_project as AP
    steps = _Steps(res)
    kw: Dict[str, Any] = {"strict": bool(opts.get("strict")),
                          "validate": not opts.get("no_validate")}
    if opts.get("at") is not None:
        kw["at"] = [float(x) for x in opts["at"]]
    if opts.get("level") is not None:
        kw["level"] = str(opts["level"])
    if opts.get("stem"):
        kw["stem"] = _slug(opts["stem"])
    try:
        rec = steps.run("prompt->intent + add-into-rvt",
                        "rvt.convert.add_to_project:add_to_project",
                        lambda: AP.add_to_project(str(inputs["prompt"]), inputs["rvt"],
                                                  out_dir, **kw))
    except _StepFailed:
        res.ok = False
        err = res.errors[-1] if res.errors else "add_to_project failed"
        res.status = f"FAILED ({err.split(': ', 1)[-1][:300]})"
        if "ConvertError" in err:
            res.line = ("prompt+rvt -> rvt (add into your project) was REFUSED by "
                        f"name: {err.split(': ', 2)[-1][:300]} Closest: an edit "
                        "sentence on the same file ('move DP-1 to 3,4'), or "
                        "prompt -> rvt on the certified genesis base.")
        return
    gates = _absorb_convert_record(res, rec, prefix="add_to_project")
    delivered = any(res.files.get(r) for r in ("combined", "shell", "equipment"))
    tgt = rec.get("target") or {}
    _convert_status(res, gates, delivered=delivered,
                    what=(f"added into your project: {len(rec.get('created') or [])} "
                          f"created (families/instances/walls); target release "
                          f"{tgt.get('release')} preserved"))


def _r_ifc_merge_into_rvt(res, inputs, out_dir, opts):
    """ifc+rvt: rvt.convert.merge_ifc -- the IFC's intent appended INTO the
    target at a deterministic disjoint offset."""
    from ..convert import merge_ifc as MI
    steps = _Steps(res)
    kw: Dict[str, Any] = {"strict": bool(opts.get("strict")),
                          "validate": not opts.get("no_validate")}
    if opts.get("offset") is not None:
        kw["offset"] = [float(x) for x in opts["offset"]]
    if opts.get("level") is not None:
        kw["level"] = str(opts["level"])
    if opts.get("stem"):
        kw["stem"] = _slug(opts["stem"])
    try:
        rec = steps.run("ifc->intent + merge-into-rvt", "rvt.convert.merge_ifc:merge_ifc",
                        lambda: MI.merge_ifc(inputs["ifc"], inputs["rvt"], out_dir, **kw))
    except _StepFailed:
        res.ok = False
        err = res.errors[-1] if res.errors else "merge_ifc failed"
        res.status = f"FAILED ({err.split(': ', 1)[-1][:300]})"
        if "ConvertError" in err:
            res.line = ("ifc+rvt -> rvt (merge into your project) was REFUSED by "
                        f"name: {err.split(': ', 2)[-1][:300]} Closest: ifc -> rvt "
                        "on the certified genesis base (drop the rvt).")
        return
    gates = _absorb_convert_record(res, rec, prefix="merge_ifc")
    delivered = any(res.files.get(r) for r in ("combined", "shell", "equipment"))
    pl = rec.get("placement") or {}
    tgt = rec.get("target") or {}
    res.caveats.append(f"merge placement: {pl.get('rule')}; offset {pl.get('offset')}")
    _convert_status(res, gates, delivered=delivered,
                    what=(f"merged into your project: {len(rec.get('created_ids') or [])} "
                          f"created ids; target release {tgt.get('release')} preserved"))


def _r_rvt_to_ifc(res, inputs, out_dir, opts):
    """rvt -> ifc: rvt.convert.rvt_to_ifc (readback -> intent -> IFC4; the
    round trip through our own resolver is the acceptance)."""
    from ..convert import rvt_to_ifc as RI
    steps = _Steps(res)
    stem = _slug(opts.get("stem")
                 or os.path.splitext(os.path.basename(inputs["rvt"]))[0])
    out_ifc = os.path.join(out_dir, f"{stem}.ifc")
    try:
        rec = steps.run("rvt-read + rvt->intent + intent->ifc",
                        "rvt.convert.rvt_to_ifc:convert_rvt_to_ifc",
                        lambda: RI.convert_rvt_to_ifc(inputs["rvt"], out_ifc, out_dir=out_dir,
                                                      roundtrip=not opts.get("no_roundtrip")))
    except _StepFailed:
        res.ok = False
        err = res.errors[-1] if res.errors else "rvt_to_ifc failed"
        res.status = f"FAILED ({err.split(': ', 1)[-1][:300]})"
        return
    _absorb_convert_record(res, rec, prefix="rvt_to_ifc")
    for name, role in ((f"{stem}.manifest.json", "rvt_to_ifc:json"),
                       (f"{stem}.MANIFEST.md", "rvt_to_ifc:md")):
        p = os.path.join(out_dir, name)
        if os.path.isfile(p):
            res.manifest_paths[role] = p
    rt = rec.get("roundtrip") or {}
    ex = (rec.get("extraction") or {}).get("cells") or {}
    summary = {k: v.get("status") for k, v in ex.items() if isinstance(v, dict)}
    if summary:
        res.caveats.append("extraction cells: " + json.dumps(summary, default=str))
    delivered = bool(res.files.get("ifc") and os.path.isfile(res.files["ifc"]))
    res.ok = delivered
    if not delivered:
        res.status = "FAILED (no IFC was produced -- see errors)"
    elif rt.get("ran"):
        res.status = (f"OK (IFC4 exported; round trip: equipment {rt.get('equipment_survived')}, "
                      f"walls {rt.get('walls_matched')}, feeder edges "
                      f"{len(rt.get('feeder_edges_out_matched') or [])}/"
                      f"{len(rt.get('feeder_edges_in') or [])}, all_survived="
                      f"{rt.get('all_survived')})")
    else:
        res.status = "OK (IFC4 exported; round-trip check did not run -- see caveats)"


def _r_extract_family(res, inputs, out_dir, opts):
    """rvt -> rfa: rvt.convert.extract_family (one embedded family document ->
    a standalone .rfa; family selector from opts['family'])."""
    from ..convert import extract_family as EF
    steps = _Steps(res)
    try:
        rows = steps.run("rvt-read (family survey)", "rvt.convert.extract_family:list_families",
                         lambda: EF.list_families(inputs["rvt"]))
    except _StepFailed:
        res.ok = False
        res.status = "FAILED (the project could not be surveyed for family documents)"
        return
    listing = os.path.join(out_dir, "families.json")
    with open(listing, "w") as fh:
        json.dump(rows, fh, indent=1, default=str)
    res.files["families"] = listing
    selector = opts.get("family")
    if selector is None:
        if len(rows) == 1:
            selector = str(rows[0]["family_id"])
            res.caveats.append(f"no --family given: the project embeds exactly one "
                               f"family ({rows[0]['family_name']!r}) -- extracted it")
        else:
            res.ok = False
            res.status = ("NEEDS-A-SELECTOR (the project embeds "
                          f"{len(rows)} family documents)" if rows else
                          "UNSUPPORTED (the project embeds no family documents)")
            names = "; ".join(f"{r['family_name']!r} (unit {r['unit']})" for r in rows[:12])
            res.line = ((f"rvt -> rfa extracts ONE embedded family: name it with --family "
                         f"(name fragment | family id | unit index). This project embeds "
                         f"{len(rows)}: {names}"
                         + (" ..." if len(rows) > 12 else "") + " (full list: families.json).")
                        if rows else
                        "rvt -> rfa: this project embeds NO family documents, so there is "
                        "nothing to extract. Closest supported route: prompt -> rfa "
                        "(generate the family from its facts).")
            return
    stem = _slug(opts["stem"]) if opts.get("stem") else None
    out_rfa = os.path.join(out_dir, f"{stem}.rfa") if stem else None
    try:
        rec = steps.run("rvt->rfa", "rvt.convert.extract_family:extract_family",
                        lambda: EF.extract_family(inputs["rvt"], str(selector), out_rfa,
                                                  out_dir=out_dir,
                                                  validate=not opts.get("no_validate")))
    except _StepFailed:
        res.ok = False
        err = res.errors[-1] if res.errors else "extract_family failed"
        msg = err.split(": ", 2)[-1][:400]
        res.status = f"FAILED ({msg})"
        if "ExtractError" in err:
            res.line = (f"rvt -> rfa refused by name: {msg} Closest supported route: "
                        "prompt -> rfa (regenerate the family from its facts).")
        return
    gates = _absorb_convert_record(res, rec, prefix="extract_family")
    rfa = res.files.get("rfa")
    if rfa:
        s = os.path.splitext(os.path.basename(rfa))[0]
        for name, role in ((f"{s}.manifest.json", "extract_family:json"),
                           (f"{s}.MANIFEST.md", "extract_family:md")):
            p = os.path.join(out_dir, name)
            if os.path.isfile(p):
                res.manifest_paths[role] = p
    fam = rec.get("family") or {}
    _convert_status(res, gates, delivered=bool(rfa and os.path.isfile(rfa)),
                    what=(f"extracted {fam.get('family_name')!r} (unit {fam.get('unit')}, "
                          f"types {fam.get('types')}) into a standalone .rfa"))


def _r_rfa_modify(res, inputs, out_dir, opts):
    """prompt+rfa -> rfa: rvt.convert.modify_family (text | inline JSON ops |
    ops.json path -- rvt.convert.edit_family's structured ops normalise into
    the same vocabulary)."""
    from ..convert import modify_family as MF
    famspec, rfa_path = _read_famspec(inputs["rfa"])
    if rfa_path is None:
        res.ok = False
        res.status = "UNSUPPORTED-INPUT-FORM (a famspec is not an editable file)"
        res.line = ("prompt+rfa -> rfa EDITS an existing .rfa file; the rfa given is a "
                    "famspec (a request to GENERATE). Closest supported route: prompt -> "
                    "rfa (put the change in the prompt), then prompt+rfa on the result.")
        return
    steps = _Steps(res)
    kw: Dict[str, Any] = {"validate": not opts.get("no_validate")}
    if opts.get("stem"):
        kw["stem"] = _slug(opts["stem"])
    try:
        rec = steps.run("rfa-edit", "rvt.convert.modify_family:modify_family",
                        lambda: MF.modify_family(rfa_path, str(inputs["prompt"]), out_dir, **kw))
    except _StepFailed:
        res.ok = False
        err = res.errors[-1] if res.errors else "modify_family failed"
        msg = err.split(": ", 2)[-1][:400]
        res.status = f"FAILED ({msg})"
        if "FamilyEditError" in err or "FamilyOpsError" in err or "ConvertError" in err:
            res.line = ("prompt+rfa -> rfa could not apply this edit: " + msg + " Grammar: "
                        "'rename the type to X; rename the family to Y; set <Param> <value> "
                        "[unit]; set <Param> of type \"T\" <value>' -- or inline JSON / an "
                        "ops.json path ({'ops': [{'op': 'set-param', 'param': 'BusRating', "
                        "'value': '225'}]}). --inventory on rvt.convert.modify_family lists "
                        "the editable parameters.")
        return
    gates = _absorb_convert_record(res, rec, prefix="modify_family")
    rfa = res.files.get("rfa")
    g = ((rec.get("validation") or {}).get("rfa") or {})
    reread = g.get("reread") or []
    _convert_status(res, gates, delivered=bool(rfa and os.path.isfile(rfa)),
                    what=(f"{len((rec.get('apply') or {}).get('applied') or reread)} edit(s) "
                          f"applied; re-read ok={all(r.get('ok') for r in reread) if reread else 'n/a'}; "
                          f"release preserved={(g.get('release') or {}).get('preserved')}"))


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
    host_rvt = _resolve_host(res, host, verb="load")
    if host_rvt is None:
        return
    if host is not None:
        res.caveats.append("loaded into YOUR host project: the four-registry "
                           "mechanism + census/validator gates ran; viewer "
                           "certification exists for the rst host and the "
                           "genesis/composed bases, not for arbitrary hosts")
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

_STANDALONE_BORN_LINE = (
    "this .rfa is STANDALONE-BORN (its element ids sit at/below the host's id "
    "watermark): the component loader splices family records verbatim and cannot "
    "re-number them, and the schema-typed id-remap + famload lane that DOES load any "
    "Revit-born .rfa is viewer-certified in the research lane only (T2a) -- not "
    "product-wired yet. What loads today: a .rfa tekton EXTRACTED from a loaded "
    "project (rvt -> rfa --family X, then this route), or a famspec JSON ({'kind': "
    "'downlight'}). Closest supported routes: rvt -> rfa -> rfa+rvt -> rvt (the "
    "extract/reload cycle), prompt+rvt -> rvt ('add a ... to my project' generates, "
    "loads AND places), prompt -> rvt.")


def _reload_rfa(res: RouteResult, rfa_path: str, out_dir: str, opts: Dict[str, Any], *,
                host: Optional[str]) -> None:
    """The extracted-.rfa lane: rvt.convert.extract_family.reload_family (a
    standalone .rfa on disk -> RfaFamilyDoc -> the four-registry COMPONENT
    loader into a copy of the host).  A standalone-born family (ids below
    the host watermark) is answered with THE clear line, never a traceback."""
    from ..convert import extract_family as EF
    steps = _Steps(res)
    host_rvt = _resolve_host(res, host, verb="reload")
    if host_rvt is None:
        return
    if host is not None:
        res.caveats.append("reloaded into YOUR host project: the component loader + "
                           "census/validator gates ran; viewer evidence for this lane "
                           "is base-level (TB0g / stage_L8 on our composed base), not "
                           "for arbitrary hosts")
    stem = _slug(opts.get("stem") or os.path.splitext(os.path.basename(rfa_path))[0])
    out_rvt = os.path.join(out_dir, f"{stem}_loaded.rvt")
    try:
        rec = steps.run("rfa-reload", "rvt.convert.extract_family:reload_family "
                                      "(rvt.famgen.loader four-registry component load)",
                        lambda: EF.reload_family(rfa_path, host_rvt, out_rvt,
                                                 validate=not opts.get("no_validate")))
    except _StepFailed:
        res.ok = False
        err = res.errors[-1] if res.errors else "reload failed"
        msg = err.split(": ", 2)[-1][:400]
        if "host watermark" in err or "watermark" in msg:
            res.status = "UNSUPPORTED-INPUT-FORM (standalone-born .rfa: ids below the host watermark)"
            res.line = f"rfa -> rvt: {_STANDALONE_BORN_LINE} (loader said: {msg})"
        else:
            res.status = f"FAILED (rfa-reload: {msg})"
            res.line = ("rfa -> rvt could not reload this .rfa: " + msg + " -- the "
                        "extracted-.rfa lane reads tekton/Revit 2024-2026 family files "
                        "whose ElemTable our codec parses (a foreign file's GraveyardRec "
                        "footer is a named codec gap). " + _STANDALONE_BORN_LINE)
        return
    res.files["loaded_rvt"] = _abs_repo(rec.get("out")) or out_rvt
    rep_p = out_rvt + ".load.json"
    if os.path.isfile(rep_p):
        res.files["load_report"] = rep_p
    verdict, n_err = "UNKNOWN", None
    try:
        with open(rep_p) as fh:
            lrep = json.load(fh)
        v = ((lrep.get("proofs") or {}).get("verify_written") or {}).get("validate") or {}
        verdict, n_err = str(v.get("verdict") or "UNKNOWN"), v.get("n_errors")
    except Exception:                                                # noqa: BLE001
        pass
    ids = rec.get("ids") or {}
    res.caveats.append("the family is LOADED, no instance is placed by this cell "
                       "(place with prompt+rvt 'add ...' or edit ops add-instance)")
    delivered = os.path.isfile(res.files["loaded_rvt"])
    if delivered and rec.get("ok"):
        res.ok = True
        res.status = (f"OK (family reloaded four-registry: host family {ids.get('host_family')}, "
                      f"symbol {ids.get('symbol')}, +{rec.get('elements_added')} host elements; "
                      f"project validator {verdict}"
                      + (f" {n_err} errors" if n_err is not None else "") + ")")
    elif delivered:
        res.ok = True
        res.status = (f"DELIVERED WITH A RED GATE (reload: {rec.get('stop_reason') or 'see report'}; "
                      f"validator {verdict}) -- the file is delivered, the label rides with it")
    else:
        res.ok = False
        res.status = f"FAILED (reload: {rec.get('stop_reason') or 'no output written'})"


def _r_rfa_load(res, inputs, out_dir, opts):
    """rfa[+rvt] -> rvt: famspec -> our .rfa -> loaded project (rvt.famload);
    or a .rfa PATH -> the extracted-.rfa reload lane (rvt.famgen.loader)."""
    from ..ifc import famfrom_ifc as FFI
    famspec, rfa_path = _read_famspec(inputs["rfa"])
    if rfa_path is not None:
        return _reload_rfa(res, rfa_path, out_dir, opts, host=inputs.get("rvt"))
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
    "rfa_load": _r_rfa_load,                        # rfa[+rvt] -> rvt (famspec | extracted .rfa)
    "spec_to_rvt": _r_spec_to_rvt,
    "spec_to_ifc": _r_spec_to_ifc,
    "spec_to_rfa": _r_spec_to_rfa,
    "rvt_edit": _r_rvt_edit,                        # prompt+rvt: edit | add_to_project
    "ifc_merge_into_rvt": _r_ifc_merge_into_rvt,    # ifc+rvt: rvt.convert.merge_ifc
    "ifc_build_then_edit": _r_ifc_build_then_edit,
    "spec_on_rvt_seed": _r_spec_on_rvt_seed,
    "prompt_via_ifc_to_rvt": _r_prompt_via_ifc_to_rvt,
    "ifc_family_load": _r_ifc_family_load,
    # the rvt.convert export / extract / family-edit routes (issue #5)
    "rvt_to_ifc": _r_rvt_to_ifc,                    # rvt -> ifc
    "extract_family": _r_extract_family,            # rvt -> rfa
    "rfa_modify": _r_rfa_modify,                    # prompt+rfa -> rfa
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
