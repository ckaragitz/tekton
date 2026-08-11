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

from . import famspec as FS
from . import matrix as MX
from .base import repo_root
from .. import _jsonsafe
from .._logsink import stage_stdout

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
    # the front door's own ``target_version`` block (rvt.frontdoor._resolve_
    # base_and_version / the author manifest; with a --rvt host the edit
    # route's _rvt_route_version_block + input_release): requested / status /
    # output_release / line ... -- ONE shape for the rvt and the rfa routes alike
    target_version: Optional[Dict[str, Any]] = None
    # _target_base's per-route memo {target: (base, block)}: a route that
    # resolves the same --target-version twice (emit, then load host) gets
    # the SAME block, its errors and its line stated once (not serialised)
    _bases: Dict[Any, Any] = dc_field(default_factory=dict, repr=False, compare=False)

    def release_view(self) -> Optional[Dict[str, Any]]:
        """The compact relay-as-is ``release`` block (same shape as the front
        door's ``--json`` result, issue #24), or None when no version story."""
        if not self.target_version:
            return None
        from . import target_status as TS
        return TS.release_view({"target_version": self.target_version,
                                "status": self.status}, files=self.files)

    def as_json(self) -> Dict[str, Any]:
        return {"ok": self.ok, "status": self.status, "line": self.line,
                "cell": self.cell, "route": self.route, "out_dir": self.out_dir,
                "files": dict(self.files), "steps": list(self.steps),
                "stamps": list(self.stamps), "caveats": list(self.caveats),
                "releases": dict(self.releases),
                "target_version": self.target_version, "release": self.release_view(),
                "errors": list(self.errors),
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


def _stage_stdout(res: RouteResult, out_dir: str, quiet: bool):
    """``quiet``: the stages' stdout streams into ``<out_dir>/route.log``,
    named in ``res.manifest_paths``; an unwritable ``out_dir`` costs the log
    (ONE caveat -- the router's non-fatal channel, where build degradations
    already land), never the stages (:mod:`rvt._logsink`, #373)."""
    return stage_stdout(out_dir, "route.log", quiet=quiet,
                        on_open=lambda p: res.manifest_paths.__setitem__("route.log", p),
                        on_degrade=res.caveats.append)


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


BUILD_CAVEAT_PREFIX = "build: "
BUILD_CAVEAT_CAP = 10           # degradations listed as caveats before the "+N more" tail


def _absorb_build_degradations(res: RouteResult, r: Any) -> None:
    """Every ``manifest.build.degradations`` entry of an author result (the
    IFC census line, 'W-1 NOT built', 'validation SKIPPED', ...) rides into
    ``res.caveats`` prefixed ``build: `` -- order kept, duplicates dropped,
    a long list capped with a '+N more, see MANIFEST.md' tail.  Labels after
    delivery (rule 1): ``ok`` / ``status`` are untouched (issue #347)."""
    degradations = ((r.manifest or {}).get("build") or {}).get("degradations") or []
    fresh = [cv for cv in dict.fromkeys(BUILD_CAVEAT_PREFIX + str(d) for d in degradations)
             if cv not in res.caveats]
    if len(fresh) > BUILD_CAVEAT_CAP:
        md = (r.manifest_paths or {}).get("md") or "MANIFEST.md"
        more = len(fresh) - BUILD_CAVEAT_CAP
        fresh = fresh[:BUILD_CAVEAT_CAP] + [
            f"{BUILD_CAVEAT_PREFIX}... +{more} more degradation(s), see {md} "
            "(build.degradations in manifest.json)"]
    res.caveats.extend(fresh)


def _absorb_author_result(res: RouteResult, r: Any) -> None:
    """Fold an AuthorResult (rvt.frontdoor.author) into the RouteResult:
    files, intermediate artifacts, stamps, caveats (the target-version line +
    every build degradation), errors, manifests."""
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
    if tv:
        res.target_version = dict(tv)
    if tv.get("line"):
        res.caveats.append(str(tv["line"]))
    _absorb_build_degradations(res, r)
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


def _target_base(res: RouteResult, opts: Dict[str, Any], label: str):
    """Resolve the certified base for ``opts['target_version']`` (None = the
    registry default) through the front door's ONE resolver and record the
    version block on ``res``.  Returns ``(base | None, version_block)``; the
    resolver's errors ride in ``res.errors``.  Shared by every family route
    that needs a base: the load host here, the emit release in
    :func:`_emit_at_target`; memoised per route (``res._bases``) so a route
    doing both resolves -- and states -- the block once."""
    target = opts.get("target_version")
    if target in res._bases:
        return res._bases[target]
    base, vb = _resolve(res, opts, label, target)
    res.target_version = vb
    res._bases[target] = (base, vb)
    return base, vb


def _resolve(res: RouteResult, opts: Dict[str, Any], label: str, target: Any):
    """ONE call to the front door's resolver for ``target`` (None = the
    default base); its errors ride in ``res.errors``.  The only place the
    router talks to ``_resolve_base_and_version``."""
    from . import AuthorRequest, _resolve_base_and_version
    base, vb, errors = _resolve_base_and_version(
        AuthorRequest(prompt=f"({label})", base=opts.get("base"),
                      target_version=None if target is None else int(target)))
    res.errors.extend(errors)
    return base, vb


def _host_version_block(res: RouteResult, host: str, target: Any, *, verb: str) -> None:
    """``--rvt`` given: the loaded output keeps THE HOST's release (a load
    runs under the host's own release, ``rvt.famload``'s
    host_release_context -- it cannot transmute a 2025 project into a 2024
    one), so THE ``target_version`` block of this rvt-output cell is the
    edit route's own (``rvt.frontdoor._rvt_route_version_block``: the host's
    release auto-detected and stated every time -- ``detected`` with no
    flag, ``match`` / ``match-older``, or ``fallback`` + THE one clear line
    when the stated year cannot open the host), worded for a load.  A
    family emitted beside it at ``--target-version`` (the famspec / product
    lanes, :func:`_emit_at_target`) keeps its own block under ``rfa``."""
    from . import _rvt_route_version_block
    from .. import versions as V
    try:
        host_rel: Optional[int] = int(V.detect_release(host))
    except Exception:                                                # noqa: BLE001
        host_rel = None
    hb = _rvt_route_version_block(target, host_rel)
    for k in ("line", "note"):        # the edit route's wording, said of a load
        if hb.get(k):
            hb[k] = (hb[k].replace("edited output", f"{verb}ed output")
                     .replace("Revit-openable edit", f"Revit-openable {verb}")
                     .replace("the edit preserves", f"the {verb} preserves"))
    if res.target_version:            # the family emitted beside it, at the flag's year
        hb["rfa"] = res.target_version
    res.target_version = hb
    res.caveats.append(str(hb.get("line") or f"{verb}ed INTO your --rvt: {hb.get('note')}"))


def _resolve_host(res: RouteResult, host: Optional[str], *, verb: str,
                  opts: Dict[str, Any]) -> Optional[str]:
    """``host`` when given (the user's project: the output keeps ITS release,
    stated by :func:`_host_version_block`), else
    the default host: the pinned certified genesis base, or with
    ``--target-version N`` the certified base OF THAT RELEASE
    (:func:`_target_base`; the load then runs under that host's release via
    ``rvt.famload``'s host_release_context).  An uncertified target degrades
    to the default base + THE line as a caveat (rule 1: delivered, labelled).
    On a missing pin / refused base returns None after setting a FAILED
    status + the clear line (never a traceback)."""
    target = opts.get("target_version")
    if host is not None:
        _host_version_block(res, host, target, verb=verb)
        return host
    n_err, restated = len(res.errors), target in res._bases
    base, vb = _target_base(res, opts, "family load")
    if base is None:
        reason = "; ".join(res.errors[n_err:]) or str(vb.get("note"))
        res.ok = False
        res.status = f"FAILED (no host project: {reason})"
        res.line = (f"rfa -> rvt {verb}s the family INTO a host project: pass --rvt "
                    "<your.rvt>, or restore the pinned genesis base "
                    "(rvt/frontdoor/assets/genesis_base.json / $RVT_GENESIS_BASE).")
        return None
    if target is not None and vb.get("status") != "match" and not restated:
        res.caveats.append(f"target {target} requested: {vb.get('line') or vb.get('note')}")
    rel = vb.get("output_release")
    res.caveats.append(f"no host .rvt supplied: {verb}ed into the certified Revit {rel} "
                       f"genesis base ({base.source}, sha256 {base.sha256[:12]}...) -- "
                       "the certified base every build route authors on")
    return base.path


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
        _jsonsafe.dump(rows, fh, indent=1)
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
            _jsonsafe.dump(cov, fh, indent=1)
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


def _emit_at_target(res: RouteResult, opts: Dict[str, Any], out_dir: str,
                    emit: Callable[[], Any], *, model=None,
                    source_ifc: Optional[str] = None) -> Any:
    """Run a standalone FAMILY emit at the ``--target-version`` release
    (issue #171) and return its result.

    The recipient's Revit year is resolved by the front door's ONE resolver
    (``rvt.frontdoor._resolve_base_and_version`` -- the very block the rvt
    routes carry) and, for a certified non-native target, ``emit`` runs
    inside ``release_ctx.release_build_context`` of that year's base
    (framing ordinals, codec singletons, the carried-schema pin and the port
    layer bound to that release), so the ``.rfa`` ARE Revit N.  If the emit
    cannot run at that release (no port layer, a class the older schema
    lacks), or the year is uncertified / unknown, or a wrong-release
    ``--base`` was refused AS A BASE, the families are still DELIVERED (rule
    1) by the native emit, and the block says so: ``status='fallback'`` /
    ``'refused'`` + THE one clear line as a caveat after delivery, and on a
    ``fallback`` (not on ``refused``) the version-agnostic IFC addition as
    on the rvt path.  No
    ``--target-version`` -> today's native emit untouched, only reported.
    On a degrade ``emit`` runs twice by design: the failed target-release
    attempt keeps its (``ok: False``, ``attempt``-labelled) step records and
    the native re-run adds its own -- the honest trace of what was tried;
    and the memoised base (:func:`_target_base`) is re-pointed at the
    default so a LOAD that follows (rfa -> rvt, the ifc family chain) hosts
    on the very release the block now names, not on the year the family
    could not be built for.  The whole version story (block update, memo
    re-point, IFC addition, caveat) is committed only once the native emit
    has DELIVERED: a lane whose native run raises too produced nothing and
    states nothing, so the next lane of the same route (ifc -> rfa:
    archetype, then assembly -- #564) makes its own attempt at Revit N."""
    from . import release_ctx as RC
    from . import target_status as TS
    native = RC.native_release()
    target = opts.get("target_version")
    if target is None:
        res.target_version = {
            "requested": None, "status": "unspecified", "output_release": native,
            "note": (f"no --target-version given: the families target the certified "
                     f"default release (Revit {native}); Revit cannot open a newer file "
                     "-- ask the recipient's Revit year first")}
        return emit()
    from . import _emit_ifc_addition
    target = int(target)
    base, vb = _target_base(res, opts, "family route")
    story: Dict[str, Any] = {}         # what THIS lane adds to the block, once it delivered
    if vb.get("status") == "match" and target != native:      # match => base resolved
        n_err, n_steps = len(res.errors), len(res.steps)
        try:
            with RC.release_build_context(base.path) as info:
                res.steps.append({"stage": "release-context", "ok": True, "seconds": 0.0,
                                  "impl": "rvt.frontdoor.release_ctx:release_build_context",
                                  "release": info["release"], "native": info["native"],
                                  "port_layer": info["port_layer"]})
                return emit()
        except RouteError:
            raise
        except Exception as e:                                       # noqa: BLE001
            # certified + pinned, but THIS emit cannot run at that release
            # (missing port layer / a class the older schema lacks): degrade
            # to the native emit + the line, never a failure (rule 1)
            reason = "; ".join(res.errors[n_err:]) or f"{type(e).__name__}: {e}"
            del res.errors[n_err:]
            for rec in res.steps[n_steps:]:
                # the failed attempt stays in the trace, labelled -- the native
                # re-run below records its own step, so the two never blur
                rec["attempt"] = f"Revit {target} release context (degraded to native)"
            story = {"status": "fallback", "output_release": native, "pending": reason,
                     "line": (f"target {target} requested: this family emit cannot run "
                              f"at Revit {target} yet ({reason}); this file targets "
                              f"{native} -- your Revit {target} cannot open it; the "
                              "IFC alongside is version-agnostic (links into Revit "
                              "2019+)")}
    elif vb.get("status") == "refused":
        # interim shim: a wrong-release --base is refused AS A BASE by the
        # resolver; a family emit needs no base, so deliver native + say so
        story = {"output_release": native,
                 "line": (f"{vb.get('note')}; the family .rfa are delivered at "
                          f"Revit {native} (open in {TS.opens_in(native)})")}
    out = emit()        # native; raises -> this lane delivered nothing and states nothing
    if story.get("status") == "fallback":
        res._bases[target] = (_resolve(res, opts, "family route", None)[0], vb)
    vb.update(story)    # in place: the memo and res.target_version hold this dict
    _emit_ifc_addition(vb, res, out_dir, _slug(opts.get("stem") or "prompt_intent"),
                       model=model, source_ifc=source_ifc, errors=res.errors)
    _settle_ifc_clause(vb)
    if vb.get("line"):
        res.caveats.append(str(vb["line"]))
    return out


def _settle_ifc_clause(vb: Dict[str, Any]) -> None:
    """The fallback line (the resolver's, or the degrade branch above)
    promises 'the IFC alongside'; keep that promise only when
    ``_emit_ifc_addition`` actually wrote one.  A family request with no room
    intent and no source IFC (a famspec) has nothing to emit as IFC -- say
    so instead (follow-up: the resolver should add the clause only when an
    IFC is written, rvt.frontdoor._resolve_base_and_version)."""
    if vb.get("status") != "fallback" or vb.get("ifc_addition"):
        return
    line = re.sub(r";?\s*the IFC alongside is version-agnostic[^;]*", "",
                  str(vb.get("line") or "")).rstrip(" ;")
    vb["line"] = (line + "; no IFC rides beside a FAMILY request (it resolves no room "
                         "intent) -- state the recipient's Revit year and re-run")


def _families_from_model(res: RouteResult, model, out_dir: str, opts: Dict[str, Any],
                         *, source_ifc: Optional[str] = None) -> Dict[str, Any]:
    """stage_families (tools/ifc_intent.py, reused as-is) -> families/*.rfa,
    at the ``--target-version`` release when one is given (issue #171)."""
    from . import build as B
    steps = _Steps(res)
    R = B.load_ifc_room_module()
    frec = _emit_at_target(
        res, opts, out_dir,
        lambda: steps.run("intent->rfa", "tools/ifc_intent.py:stage_families",
                          lambda: R.stage_families(model, out_dir)),
        model=model, source_ifc=source_ifc)
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
    """A prompt -> family .rfa, in the order the honesty contract sets:

    1. CATALOG facts first (steer #591 DONE 6): "a 225 A Eaton panelboard" is a
       real record and must route to it, never to a generated approximation.
    2. Otherwise the ARCHETYPE lane: a named product this engine generates
       ("create a cable tray family") is built at standard nominal sizes.
    3. Otherwise the honest refusal the intent parser already writes.
    """
    from . import prompt_intent as PP
    from . import intent as FI
    prompt = str(inputs["prompt"])
    steps = _Steps(res)
    mark = len(res.errors)
    model = None
    try:
        model, _parsed = steps.run("prompt->intent",
                                   "rvt.frontdoor.prompt_intent:prompt_to_intent",
                                   lambda: PP.prompt_to_intent(prompt))
    except _StepFailed:
        pass
    frec: Dict[str, Any] = {}
    if model is not None:
        intent_json = os.path.join(out_dir, "intent.json")
        FI.write_intent_json(model, intent_json)
        res.files["intent"] = intent_json
        frec = _families_from_model(res, model, out_dir, opts)
    built = int(frec.get("built") or 0)
    if built:
        res.ok = True
        res.status = f"OK ({built} family .rfa generated; refusals honest)"
        return
    # nothing catalog-backed came out of it: is this a product we GENERATE?
    if _archetype_rfa(res, prompt, out_dir, opts, demote=res.errors[mark:]):
        return
    res.ok = False
    res.status = ("FAILED (no family plan in this prompt could be built -- "
                  "see caveats for every refusal)")


def _archetype_rfa(res: RouteResult, prompt: str, out_dir: str,
                   opts: Dict[str, Any], *,
                   demote: Optional[List[Any]] = None) -> bool:
    """The ARCHETYPE lane (steer #591): a prompt naming a product this engine
    generates -> ONE .rfa at standard nominal sizes.  Returns True when it
    delivered (or tried and failed loudly), False when the prompt names no
    generated product, so the caller can keep its own refusal.
    """
    from ..famgen import archetypes as AR
    try:
        req = AR.resolve_prompt(prompt)
    except AR.ArchetypeError:
        return False
    if req is None:
        return False
    # the catalog lane's refusal is no longer the answer -- keep it as context
    for e in (demote or []):
        res.caveats.append(f"the catalog lane did not apply here ({e}) -- fell "
                           "through to the ARCHETYPE lane below")
    del res.errors[len(res.errors) - len(demote or []):]
    kw: Dict[str, Any] = {"product": req.arch.key, "prompt": prompt}
    sub = dict(opts)
    sub.setdefault("stem", _slug(req.name))
    _famspec_rfa(res, "archetype", kw, out_dir, sub)
    if not res.files.get("rfa"):
        return True
    rep = req.to_json()
    rec_path = os.path.join(out_dir, "archetype.json")
    try:
        with open(rec_path, "w", encoding="utf-8") as fh:
            _jsonsafe.dump(rep, fh, indent=1)
        res.files["archetype"] = rec_path
    except OSError as e:                                     # delivery never blocks
        res.caveats.append(f"the archetype record could not be written ({e})")
    n_nom, n_giv = len(req.nominal()), len(req.given())
    res.status = (f"OK ({req.arch.title}: {len(req.parts())}-part .rfa generated at "
                  f"standard nominal sizes; {n_giv} dimension(s) from the prompt, "
                  f"{n_nom} nominal)")
    # THE NAMED-PRODUCT GUARD (steer #591 "Still refused").  The file is still
    # delivered -- hard rule 1 -- but a prompt that named a specific item must
    # never be answered SILENTLY with a generic one, so the claim leads both the
    # status line and the caveats.
    if req.claim:
        res.status += " -- NOT the product you named"
        res.caveats.insert(0, req.claim["line"])
    res.caveats.append(
        f"ARCHETYPE LANE: this family was GENERATED, not read from a catalog. "
        f"{n_nom} dimension(s) are NOMINAL -- {req.arch.basis}; the practice is "
        f"named to say WHICH convention the sizes follow, not to claim conformance "
        f"with a standards document (tekton holds none) -- and "
        f"{n_giv} came from your prompt"
        + (": " + "; ".join(f"{k} = {req.quoted[k]!r}" for k in req.given()
                            if k in req.quoted) if req.quoted else "")
        + ". No manufacturer, model or part number is claimed; every nominal "
          "dimension is listed in the report's unverified_fields and any of them "
          "can be overridden by naming it in the prompt or in a famspec's "
          "'dimensions'.")
    res.caveats.append(f"LOD: {req.arch.lod_note}. NOT modelled: "
                       + "; ".join(req.arch.limits or ("--",)))
    return True


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
            frec = _families_from_model(res, model, out_dir, opts,
                                        source_ifc=inputs["ifc"])
            built = int(frec.get("built") or 0)
            res.ok = built > 0
            res.status = f"OK ({built} catalog family .rfa from the room IFC)"
            return
    res.caveats.append("no buildable room-equipment family plan in this IFC -- "
                       "took the PRODUCT-IFC path (measured facts -> the "
                       "downlight archetype)")
    mark = len(res.errors)
    try:
        _product_rfa(res, inputs["ifc"], out_dir, opts)
        return
    except _StepFailed as sf:
        failed_at = str(sf.args[0])
    # The archetype lane could not measure this IFC (several products, or a
    # body it does not model).  Rather than end at the refusal, measure every
    # product's mesh into prisms and author ONE multi-part family (#498).
    demoted = res.errors[mark:]
    del res.errors[mark:]
    for e in demoted:
        res.caveats.append(f"the measured-archetype lane did not apply here ({e}) "
                           "-- fell through to the ASSEMBLY lane below")
    _assembly_rfa(res, inputs["ifc"], out_dir, opts)
    if res.files.get("rfa"):       # the demotion rides on the status line, not only a caveat
        res.status += f" by the ASSEMBLY lane, after the archetype lane failed at {failed_at}"


def _assembly_rfa(res: RouteResult, ifc_path: str, out_dir: str,
                  opts: Dict[str, Any]) -> None:
    """An ARBITRARY-GEOMETRY IFC -> ONE multi-part generic_model .rfa.

    The third ``ifc -> rfa`` lane (steer S-2026-08-10-c / #498): no catalog
    identity, no archetype -- every product with a tessellated body is
    measured into a prism (:mod:`rvt.ifc.assembly_parts`) and the whole set
    is authored as one donor-free family through the generic_model
    constructor, so the emit / validate / provenance / target-version block
    is the very one the famspec lane uses."""
    from ..ifc import assembly_parts as AP
    steps = _Steps(res)
    try:
        model = steps.run("ifc->parts", "rvt.ifc.assembly_parts:read_assembly",
                          lambda: AP.read_assembly(ifc_path))
    except _StepFailed as sf:
        res.ok = False
        msg = str(sf.__cause__)[:400]
        res.status = f"FAILED (ifc->parts: {msg})"
        res.line = (f"nothing in this IFC could be measured into a solid: {msg}. "
                    "The assembly lane authors a family from TESSELLATED bodies "
                    "(IfcTriangulatedFaceSet / IfcPolygonalFaceSet); an IFC of "
                    "swept/CSG solids re-exports as a mesh from most authoring "
                    "tools. Nothing is invented from an unmeasurable body.")
        return

    rec_path = os.path.join(out_dir, "assembly-parts.json")
    try:
        with open(rec_path, "w", encoding="utf-8") as fh:
            _jsonsafe.dump(model.to_json(), fh, indent=1)
        res.files["assembly_parts"] = rec_path
    except OSError as e:                                        # delivery never blocks
        res.caveats.append(f"the measurement record could not be written ({e})")

    name = (model.assembly_name or model.project_name
            or os.path.splitext(os.path.basename(ifc_path))[0])
    # identity + a bill of materials the family can SCHEDULE, carried verbatim
    # off the IFC's psets: absent stays absent, nothing is invented.
    bom = model.bill_of_materials()
    text_params: Dict[str, str] = {"Source IFC": os.path.basename(ifc_path)}
    if model.assembly_tag:
        text_params["Assembly Tag"] = model.assembly_tag
    pns = [r["part_number"] for r in bom if r["part_number"]]
    if pns:
        seen: List[str] = []
        for pn in pns:
            if pn not in seen:
                seen.append(pn)
        text_params["Part Numbers"] = ", ".join(seen)
    kw: Dict[str, Any] = {
        "parts": model.to_parts(), "name": name,
        "source": f"IFC mesh ({os.path.basename(ifc_path)})",
        "identity": dict(model.identity), "text_params": text_params,
    }
    sub = dict(opts)
    sub.setdefault("stem", _slug(name))
    _famspec_rfa(res, "generic_model", kw, out_dir, sub, source_ifc=ifc_path)
    if not res.files.get("rfa"):
        return
    d = model.dims_ft()
    res.status = (f"OK ({len(model.parts)}-part generic_model .rfa measured from "
                  f"{os.path.basename(ifc_path)})")
    res.caveats.append(
        f"ASSEMBLY LANE: {len(model.parts)} IFC product(s) measured into prisms "
        f"({', '.join(f'{k} x{v}' for k, v in sorted(model.fit_counts().items()))}), "
        f"overall {d['x'] * 12:.2f} x {d['y'] * 12:.2f} x {d['z'] * 12:.2f} in; every "
        "dimension is GIVEN by your mesh and reported as such -- no catalog fact, no "
        "manufacturer identity, no donor bytes")
    res.caveats.extend(model.notes)
    if model.decomposed:
        res.caveats.append(", ".join(
            f"{'box' if r.get('method') == 'boxes' else 'slab'} decomposition improved "
            f"{r['name']} ({r['parts']} solids, fill {r['fill_before']:.2f} -> "
            f"{r['fill_after']:.2f})" for r in model.decomposed[:6]))
    if model.kept_prism:
        res.caveats.append(
            "kept as a single prism (the decomposition was refused, never "
            "silently accepted): " + "; ".join(
                f"{r['name']} -- {r['reason']}" for r in model.kept_prism[:6]))
    if bom:
        res.caveats.append(
            f"bill of materials read off the IFC psets and authored onto the family "
            f"type ({len(bom)} product rows; part numbers "
            f"{text_params.get('Part Numbers', 'absent')})"
            + ("" if model.identity else
               "; no Manufacturer property in the source, so that identity field is "
               "left EMPTY rather than invented"))
    if model.skipped:
        res.caveats.append(
            f"{len(model.skipped)} product(s) carried no measurable solid and were "
            "SKIPPED BY NAME (never guessed): "
            + "; ".join(f"{s['name']} ({s['reason']})" for s in model.skipped[:6]))
    res.caveats.append(
        "each part is the PRISMATIC MASSING of its mesh (plan footprint extruded "
        "over the mesh's Z extent), not a faceted copy: a cross-section that varies "
        "with height becomes its envelope. assembly-parts.json reports each part's "
        "'fill' (mesh volume / authored prism volume) so the approximation is "
        "measurable per part rather than described.")


def _product_rfa(res: RouteResult, ifc_path: str, out_dir: str,
                 opts: Dict[str, Any]) -> Optional[Any]:
    """PRODUCT IFC -> facts -> our downlight family .rfa (the certified
    archetype), composed and emitted at the ``--target-version`` release
    (:func:`_emit_at_target`; the release-independent fact extraction runs
    once, outside it).  Returns the DownlightProduct or None."""
    from ..ifc import product_facts as PF
    from ..ifc import famfrom_ifc as FFI
    steps = _Steps(res)
    facts = steps.run("ifc->facts", "rvt.ifc.product_facts:extract_product_facts",
                      lambda: PF.extract_product_facts(ifc_path))
    facts_p = os.path.join(out_dir, "product-facts.json")
    steps.run("facts->json", "rvt.ifc.product_facts:write_facts_record",
              lambda: PF.write_facts_record(facts, facts_p))
    res.files["product_facts"] = facts_p

    def emit():
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

    return _emit_at_target(res, opts, out_dir, emit, source_ifc=ifc_path)


def _r_ifc_family_load(res, inputs, out_dir, opts):
    """The ifc->rfa->loaded-rvt chain (the L_downlight_loaded pipeline): the
    product .rfa is emitted at the ``--target-version`` release
    (:func:`_product_rfa`, as ifc -> rfa does) and LOADED into ``--rvt`` or
    that release's certified base (:func:`_resolve_host`, one memoised
    version block for both)."""
    from ..ifc import famfrom_ifc as FFI
    prod = _product_rfa(res, inputs["ifc"], out_dir, opts)
    if prod is None or not res.ok:
        return
    _load_family(res, out_dir, opts,
                 host=inputs.get("rvt"),
                 builder=lambda start_id=100000: FFI.make_downlight(
                     facts=prod.product_facts, start_id=start_id).doc,
                 name=_slug(getattr(prod.doc, "name", "downlight")),
                 category=int(prod.doc.category_id))


def _load_family(res: RouteResult, out_dir: str, opts: Dict[str, Any], *,
                 host: Optional[str], builder, name: str, category: int) -> None:
    """The certified four-registry LOAD (rvt.famload via
    famfrom_ifc.load_into_project); ``category`` = the family document's
    own OST category id, declared up front so the host survey can bind its
    category style row as a core id."""
    from ..ifc import famfrom_ifc as FFI
    steps = _Steps(res)
    host_rvt = _resolve_host(res, host, verb="load", opts=opts)
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
                    lambda: FFI.load_into_project(host_rvt, out_rvt, builder=builder,
                                                  name=name, core_categories=(category,)))
    res.files["loaded_rvt"] = out_rvt
    rep_json = os.path.join(out_dir, f"{name}_load-report.json")
    with open(rep_json, "w") as fh:
        _jsonsafe.dump(rep.as_json(), fh, indent=1)
    res.files["load_report"] = rep_json
    ok = bool(rep.ok and os.path.isfile(out_rvt)
              and (rep.validate_project_mode or {}).get("verdict") == "VALID")
    res.ok = ok
    res.status = ("OK (family loaded four-registry; project validates 0 errors)"
                  if ok else
                  f"FAILED (load: {rep.stop_reason or rep.error or 'see report'})")


_FAMSPEC_KINDS = FS.KINDS          # panelboard / transformer / luminaire / device / downlight
#: "'panelboard' | 'transformer' | ..." -- the kind alternatives as the clear lines spell them
_FAMSPEC_KINDS_ALT = " | ".join(f"'{k}'" for k in FS.KINDS)

#: the honest label every famspec-generated deliverable carries (rule 1: a
#: label after delivery, never a refusal): validator + provenance gates ran,
#: Autodesk's reader has not seen THIS artifact (rule 4)
FAMSPEC_STAMP = ("PROOF-ONLY: generated family from a famspec -- family-mode validator "
                 "+ provenance gated, not viewer-certified as this artifact; "
                 "NOT-DELIVERABLE until TRACKER gates G2/G3 clear")


def _rfa_lanes_line() -> str:
    """THE one clear line's tail when a .rfa cannot be loaded: what the cell
    reads, what it refuses by name (one home: rvt.convert.rfa_load), and the
    closest supported routes."""
    from ..convert.rfa_load import REFUSED_BY_NAME
    return (f"What this cell reads: a famspec JSON ({{'kind': {_FAMSPEC_KINDS_ALT}, ...}} "
            "-- spec/famspec.schema.json), a .rfa "
            "tekton EXTRACTED from a loaded project (reloaded verbatim), or any "
            "STANDALONE-BORN .rfa -- our own .rfa deliverables and Revit-saved family "
            "files whose ElemTable our codec parses (schema-typed id remap + "
            f"four-registry famload, the certified T2a mechanism). {REFUSED_BY_NAME}. "
            "Closest supported routes: rvt -> rfa -> rfa+rvt -> rvt (the extract/reload "
            "cycle), prompt+rvt -> rvt ('add a ... to my project' generates, loads AND "
            "places), prompt -> rvt.")


def _reload_rfa(res: RouteResult, rfa_path: str, out_dir: str, opts: Dict[str, Any], *,
                host: Optional[str]) -> None:
    """A .rfa PATH -> loaded project.  Two lanes, chosen by the id law:

    * the family's ids sit ABOVE the host watermark (a .rfa tekton extracted
      from a loaded project) -> ``rvt.convert.extract_family.reload_family``:
      records spliced VERBATIM through the four-registry COMPONENT loader
      (unchanged -- the certified extract/reload cycle);
    * the ids sit AT/BELOW it (STANDALONE-BORN: our own ``start_id=1000``
      deliverables, any Revit-saved family) -> ``rvt.convert.rfa_load``: the
      schema-typed decode-time id remap into the free block above the
      watermark + ``rvt.famload`` (the viewer-certified T2a mechanism,
      issue #99).

    A file neither lane can read is answered with THE clear line, never a
    traceback."""
    from ..convert import extract_family as EF
    from ..convert import rfa_load as RL
    steps = _Steps(res)
    host_rvt = _resolve_host(res, host, verb="reload", opts=opts)
    if host_rvt is None:
        return
    if host is not None:
        res.caveats.append("reloaded into YOUR host project: the loader + "
                           "census/validator gates ran; viewer evidence for this lane "
                           "is base-level (T2a / TB0g / stage_L8 on our composed base), "
                           "not for arbitrary hosts")
    stem = _slug(opts.get("stem") or os.path.splitext(os.path.basename(rfa_path))[0])
    out_rvt = os.path.join(out_dir, f"{stem}_loaded.rvt")
    try:
        born, floor, wm = steps.run(
            "rfa-classify", "rvt.convert.rfa_load:is_standalone_born (ElemTable id law)",
            lambda: RL.is_standalone_born(rfa_path, host_rvt))
        res.steps[-1]["detail"] = (f"rfa id floor {floor} vs host watermark {wm}: "
                                   + ("standalone-born -> id-remap lane" if born
                                      else "above the watermark -> verbatim reload lane"))
        if born:
            rec = steps.run("rfa-born-load", "rvt.convert.rfa_load:load_rfa_into_project "
                                             "(schema-typed id remap + rvt.famload four-registry)",
                            lambda: RL.load_rfa_into_project(
                                rfa_path, host_rvt, out_rvt,
                                validate=not opts.get("no_validate")))
        else:
            rec = steps.run("rfa-reload", "rvt.convert.extract_family:reload_family "
                                          "(rvt.famgen.loader four-registry component load)",
                            lambda: EF.reload_family(rfa_path, host_rvt, out_rvt,
                                                     validate=not opts.get("no_validate")))
    except _StepFailed as sf:
        res.ok = False
        msg = str(sf.__cause__)[:400]
        res.status = f"FAILED ({sf.args[0]}: {msg})"
        res.line = f"rfa -> rvt could not load this .rfa: {msg}. {_rfa_lanes_line()}"
        return
    if rec.get("summary"):
        res.caveats.append(str(rec["summary"]))
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
    how = ("loaded four-registry via the id-remap lane, standalone-born" if born
           else "reloaded four-registry")
    if delivered and rec.get("ok"):
        res.ok = True
        res.status = (f"OK (family {how}: host family {ids.get('host_family')}, "
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


def _famspec_request(res: RouteResult, famspec: Dict[str, Any], opts: Dict[str, Any],
                     *, cell: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Validate + normalise a famspec (:mod:`rvt.frontdoor.famspec`, the
    ``spec/famspec.schema.json`` contract).  Returns ``(kind, constructor
    kwargs)`` and folds the famspec's route options into ``opts`` (the CLI
    flag wins); an invalid famspec sets the INVALID-FAMSPEC status + THE
    one clear line and returns None -- never a constructor traceback."""
    try:
        kind, kw, ropts = FS.normalise(famspec)
    except FS.FamspecError as e:
        res.ok = False
        kind = famspec.get("kind") if isinstance(famspec, dict) else None
        res.status = ("INVALID-FAMSPEC" if kind in FS.KINDS
                      else f"UNSUPPORTED-FAMSPEC-KIND ({kind or 'unset'})")
        res.errors.extend(e.problems)
        res.line = (f"{cell}: the famspec is not a valid request -- {e}. The contract "
                    f"is spec/famspec.schema.json (kinds: {', '.join(FS.KINDS)}; fields "
                    "mirror rvt.famgen.factory.make_<kind>'s keyword arguments; worked "
                    "examples: spec/examples/famspec-*.json). Closest supported route: "
                    "prompt -> rfa ('an eaton 225 A panelboard, 42 spaces, 208Y/120 V').")
        return None
    for k, v in ropts.items():
        if opts.get(k) is None:
            opts[k] = v
            res.caveats.append(f"{k}={v} taken from the famspec (no --{k.replace('_', '-')} "
                               "flag given)")
    return kind, kw


def _famspec_rfa(res: RouteResult, kind: str, kw: Dict[str, Any], out_dir: str,
                 opts: Dict[str, Any], *,
                 source_ifc: Optional[str] = None) -> Optional[Tuple[Any, str]]:
    """famspec -> OUR standalone .rfa: run the kind's constructor, emit at
    the ``--target-version`` release (:func:`_emit_at_target`), fold the
    write report (family-mode validator, provenance scan) into ``res``.
    Returns ``(product, stem)`` -- ``product.doc`` is the FamilyDoc -- or
    None when nothing was delivered; sets ``res.ok`` / ``res.status``.
    ``source_ifc`` is the IFC the famspec was measured from, if any (the
    assembly lane): on a genuine version fallback it is copied beside the
    delivered ``.rfa``; a famspec-only request has none and says so."""
    steps = _Steps(res)
    ctor = FS.constructor_name(kind)

    def emit() -> Tuple[Any, str, Dict[str, Any]]:
        prod = steps.run("famspec->rfa", ctor, lambda: FS.build(kind, kw))
        stem = _slug(opts.get("stem") or prod.file_stem)
        rep = steps.run("rfa-emit", "rvt.frontdoor.famspec:write (FamilyProduct.write | "
                                    "DownlightProduct.write_rfa)",
                        lambda: FS.write(prod, os.path.join(out_dir, f"{stem}.rfa"),
                                         report_path=os.path.join(out_dir, f"{stem}.report.json")))
        return prod, stem, rep

    try:
        prod, stem, rep = _emit_at_target(res, opts, out_dir, emit, source_ifc=source_ifc)
    except _StepFailed as sf:
        res.ok = False
        msg = str(sf.__cause__)[:400]
        res.status = f"FAILED ({sf.args[0]}: {msg})"
        res.line = ((f"famspec kind {kind!r} was REFUSED BY NAME by its constructor ({ctor}): "
                     f"{msg}. Nothing is invented: change the famspec to facts the catalog "
                     "carries (spec/famspec.schema.json describes every field).")
                    if FS.is_refusal(sf.__cause__) else
                    (f"famspec kind {kind!r} could not be emitted here: {msg}."
                     + ("" if kind in FS.CATALOG_KINDS else
                        " This kind needs the family container archetype of the research "
                        f"corpus (owner machine); the catalog kinds {' / '.join(FS.CATALOG_KINDS)} "
                        "run anywhere.")))
        return None
    rfa_out = os.path.join(out_dir, f"{stem}.rfa")
    delivered = os.path.isfile(rfa_out)
    if delivered:
        res.files["rfa"] = rfa_out
    if os.path.isfile(str(rep.get("report_path"))):
        res.files["rfa_report"] = str(rep["report_path"])
    fam = rep.get("family") or {}
    tc = (fam.get("type_catalog") or {}).get("path")
    if tc and os.path.isfile(str(tc)):
        res.files["type_catalog"] = str(tc)
    v = rep.get("validate") or {}
    v = v.get("family_mode") or v          # FamilyProduct.write | DownlightProduct.write_rfa shape
    verdict, n_err = str(v.get("verdict") or "UNKNOWN"), v.get("n_errors")
    prov = rep.get("provenance") or {}
    res.caveats.extend(str(c) for c in rep.get("caveats") or [])
    unver = fam.get("unverified_fields") or []
    if unver:
        res.caveats.append("generated / assumed / user-given fact fields (nominal = generated standard practice, given = you stated it, assumed = a rule off a fact) (surfaced in the report, not "
                           f"silently trusted): {', '.join(map(str, unver))}")
    if FAMSPEC_STAMP not in res.stamps:
        res.stamps.append(FAMSPEC_STAMP)
    _convert_status(
        res, {"verdicts": {"family-mode": f"{verdict}" + (f" {n_err} errors" if n_err is not None else "")},
              "all_valid": bool(rep.get("ok", verdict == "VALID"))},
        delivered=delivered,
        what=(f"{kind} family {prod.name!r} generated from the famspec: "
              f"{fam.get('elements', len(prod.doc.elements))} elements, types "
              f"{fam.get('types') or [n for n, _ in prod.doc.types]}; provenance ok={prov.get('ok')}"))
    return (prod, stem) if delivered else None


def _r_rfa_generate(res, inputs, out_dir, opts):
    """rfa -> rfa: a famspec ({'kind': panelboard | transformer | luminaire |
    device | downlight, ...}) -> OUR standalone .rfa (issue #162 / #361).  A
    .rfa PATH alone is a no-op (nothing to generate, nothing to edit): THE
    clear line."""
    famspec, rfa_path = _read_famspec(inputs["rfa"])
    if rfa_path is not None:
        res.ok = False
        res.status = "UNSUPPORTED-INPUT-FORM (an existing .rfa alone is a no-op)"
        res.line = (f"rfa -> rfa GENERATES a family from a famspec JSON ({{'kind': "
                    f"{_FAMSPEC_KINDS_ALT}, ...}} -- spec/famspec.schema.json); an existing "
                    ".rfa with .rfa output has nothing to generate. Closest supported routes: "
                    "prompt+rfa -> rfa (EDIT it: 'set BusRating 225; rename the type to X'), "
                    "rfa -> rvt (LOAD it into a project).")
        return
    req = _famspec_request(res, famspec or {}, opts, cell="rfa -> rfa")
    if req is not None:
        _famspec_rfa(res, req[0], req[1], out_dir, opts)


def _r_rfa_load(res, inputs, out_dir, opts):
    """rfa[+rvt] -> rvt: famspec -> our .rfa -> loaded project (rvt.famload);
    or a .rfa PATH -> the verbatim reload lane (extracted .rfa) / the
    id-remap lane (standalone-born .rfa), see :func:`_reload_rfa`."""
    famspec, rfa_path = _read_famspec(inputs["rfa"])
    if rfa_path is not None:
        return _reload_rfa(res, rfa_path, out_dir, opts, host=inputs.get("rvt"))
    req = _famspec_request(res, famspec or {}, opts, cell="rfa -> rvt")
    if req is None:
        return
    kind, kw = req
    # the .rfa deliverable rides along at the --target-version release; the
    # LOAD below rebuilds the document above the host watermark under the
    # HOST's release (--target-version picks that year's certified base;
    # _target_base's memo states the version block once for both)
    emitted = _famspec_rfa(res, kind, kw, out_dir, opts)
    if emitted is None:
        return
    prod, stem = emitted
    emit_status = res.status
    _load_family(res, out_dir, opts, host=inputs.get("rvt"),
                 builder=lambda start_id=100000: FS.build(kind, kw, start_id=start_id).doc,
                 name=stem, category=int(prod.doc.category_id))
    res.caveats.append("the family is LOADED, no instance is placed by this cell (place "
                       "with prompt+rvt 'add ...' or edit ops add-instance); the .rfa "
                       f"deliverable beside it: {emit_status}")


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
    frec = _families_from_model(res, model, out_dir, opts, source_ifc=ifc_path)
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
        # seed job progress -> job-create.log (whatever the route's own verbosity);
        # an unopenable log = ONE caveat, never the job (#424).  Its stderr
        # verdict line joins the log only when the route is quiet (#448).
        with (stage_stdout(out_dir, "job-create.log", quiet=True,
                           on_open=lambda p: res.files.__setitem__("job_log", p),
                           on_degrade=res.caveats.append),
              E.job_stderr_joins_stdout(bool(opts.get("quiet")))):
            return int(J.main(argv))

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
    "rfa_load": _r_rfa_load,                        # rfa[+rvt] -> rvt (famspec | .rfa path)
    "rfa_generate": _r_rfa_generate,                # rfa -> rfa (famspec -> our .rfa, issue #162)
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

    ``quiet=True`` (``tools/route.py run --json``): whatever the stages print
    goes to ``<out_dir>/route.log`` (``manifest_paths['route.log']``), never
    to the caller's stdout -- the front door build's convention (issue #188).

    An ``out`` that :func:`standalone.out_dir_refusal` refuses is a
    :class:`RouteError` (its ONE line) raised before the dir is created, for
    every supported cell, so nothing -- not even ``route.log`` -- is written
    there (issue #473; the front door's twin one layer down is #452).
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
    from .standalone import out_dir_refusal
    line = out_dir_refusal(out_dir)
    if line:
        raise RouteError(line)              # before makedirs: nothing lands in the quarantine dir
    os.makedirs(out_dir, exist_ok=True)
    res.out_dir = out_dir
    res.route = cell.route
    res.caveats.extend(cell.caveats)

    capture = _stage_stdout(res, out_dir, quiet=bool(opts.get("quiet")))   # opens route.log now
    try:
        with capture:
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
        "target_version": res.target_version,
        "release": res.release_view(),
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
        _jsonsafe.dump(man, fh, indent=1)
    res.manifest_paths["route.json"] = jp

    lines = [f"# route: {'+'.join(sorted(inputs))} -> {output}", ""]
    lines.append(f"* ok: **{res.ok}** -- {res.status}")
    if res.line:
        lines.append(f"* {res.line}")
    c = res.cell or {}
    lines.append(f"* matrix cell: status **{c.get('status')}**, route "
                 f"`{res.route}`, stages: {' -> '.join(c.get('stages') or [])}")
    for label, tv in (("target version", res.target_version),
                      ("the .rfa beside it", (res.target_version or {}).get("rfa"))):
        if not tv:
            continue
        req = tv.get("requested")
        asked = f"Revit {req}" if req is not None else "(not stated)"
        tail = f": {tv['line']}" if tv.get("line") else f" -- {tv.get('note') or ''}"
        lines.append(f"* {label}: requested {asked} -> output Revit "
                     f"{tv.get('output_release')} (**{tv.get('status')}**){tail}")
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
