"""rvt.frontdoor -- THE MULTI-SURFACE FRONT DOOR: one entrypoint, three inputs.

tekton must be drivable from ANY AI surface (Claude Design / Chat /
Cowork, ChatGPT Work, Gemini, ...) with ANY of THREE inputs::

    author(prompt="an electrical room 30x20 ft rated for 2500 A service ...")
    author(ifc="design.ifc")
    author(rvt="in.rvt", edit="delete DP-1 with cascade; move LP-2 to 3,4")

and every route lands in the SAME place:

  input --> the ONE intent model (rvt.ifc.intent.IntentModel, spec v2) --> the
  build step: intent -> our .rvt ON THE CERTIFIED GENESIS BASE (never an
  Autodesk sample) --> the .rvt file(s) + a deliverable MANIFEST (route,
  intent, elements created, families generated, base + certification, the
  validator summary, PROOF-ONLY stamps, and the CRUD affordances).

Routing:

* ``--ifc``    -> :mod:`rvt.ifc.intent` (the ifc-room stream's placement /
                 Pset-join-key resolver -- imported, not edited) -> intent.
* ``--prompt`` -> :mod:`rvt.frontdoor.prompt_intent`: (a) the PRIMARY path
                 is the documented three-d-stage HANDOFF (a scene brief +
                 ``PROMPT_TO_IFC.md`` any AI surface executes with Three.js,
                 the exported IFC re-entering through ``--ifc``); (b) a
                 built-in rules-first FALLBACK parser resolves the prompt
                 into the same intent with NO external model call and no
                 API key, its coverage stated honestly.
* ``--rvt``    -> :meth:`rvt.mutate.Document.from_file` + the edit CLI's
                 operations (:mod:`rvt.frontdoor.edit` delegating to the job
                 runner's certified edit pipeline: modify / move / retype /
                 delete / cascade), driven by ``--edit`` text or an ops spec.

The OPEN BUG (created walls + loaded family documents in one file trip the
audit) is DETECTED and DEGRADED honestly by :mod:`rvt.frontdoor.build`:
``--strict`` -> two coordinated files (shell + equipment); default -> one
combined file STAMPED 'PROOF-ONLY: walls+families combination unverified'.

CLI: ``tools/frontdoor.py`` (the ``author`` command).  Territory:
``src/rvt/frontdoor/`` (front-door stream).
"""
from __future__ import annotations

import contextlib
import os
import re
import time
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, List, NoReturn, Optional

from .._lazyimp import ExtraNotInstalled
from . import base as _base
from . import intent as _intent
from .base import (BaseError, BaseNotCertified, ResolvedBase, PIN,
                   is_autodesk_sample, resolve_base, release_status)

__all__ = [
    "author", "run", "AuthorRequest", "AuthorResult", "FrontDoorError",
    "InputReleaseRefused", "ROUTES",
    "BaseError", "BaseNotCertified", "ResolvedBase", "PIN", "resolve_base",
    "is_autodesk_sample", "release_status", "VERSION",
]

VERSION = "1.0.0"
ROUTES = ("prompt", "ifc", "rvt")


class FrontDoorError(RuntimeError):
    """A request the front door cannot honour (bad arguments / no input)."""


class InputReleaseRefused(FrontDoorError):
    """The ``--rvt`` INPUT is of an era / release tekton cannot read (issue
    #176): nothing can be built from it, so the route stops with ONE line
    (``str(exc)``; the CLI's usage-error exit 2, no traceback) after writing
    the refusal manifest.  ``.result`` is that :class:`AuthorResult`."""

    def __init__(self, line: str, result: "AuthorResult") -> None:
        super().__init__(line)
        self.result = result


@dataclass
class AuthorRequest:
    """One ``author`` call: exactly ONE of prompt / ifc / (rvt + edit)."""
    prompt: Optional[str] = None
    ifc: Optional[str] = None
    rvt: Optional[str] = None
    edit: Optional[str] = None
    out: Optional[str] = None                 # output DIRECTORY
    base: Optional[str] = None                # --base override (never a sample)
    strict: bool = False                      # the walls+families split degrade
    handoff_only: bool = False                # prompt: emit the handoff, skip the fallback build
    no_handoff: bool = False                  # prompt: skip the handoff package
    stages: str = "FLWECV"                    # build stages subset
    wall_mode: str = "min"                    # wall clone clean-up mode
    specimens: Optional[str] = None           # specimen ancestor override
    symbol_hollow: bool = False               # loaded symbols without solids
    no_validate: bool = False                 # skip the validation gate (debug only)
    strict_validate: bool = False             # validator strict mode (rvt route)
    stem: Optional[str] = None                # output file stem
    quiet: bool = True
    target_version: Optional[int] = None      # --target-version: the Revit release the
                                              # RECIPIENT runs (None = unstated -> the
                                              # certified default release)

    def route(self) -> str:
        n = sum(x is not None for x in (self.prompt, self.ifc, self.rvt))
        if n == 0:
            raise FrontDoorError("author needs exactly one input: --prompt TEXT | --ifc FILE | "
                                 "--rvt FILE --edit SPEC")
        if n > 1:
            raise FrontDoorError("author takes exactly ONE input: --prompt, --ifc, or --rvt "
                                 "(they are three routes into the same intent model)")
        if self.rvt is not None:
            if not self.edit:
                raise FrontDoorError("--rvt requires --edit (an edit sentence, an ops.json path, "
                                     "or inline JSON) -- to CREATE from a description use "
                                     "--prompt; to just inspect a .rvt use tools/rvt_edit.py info")
            return "rvt"
        return "ifc" if self.ifc is not None else "prompt"


@dataclass
class AuthorResult:
    """What ``author`` produced."""
    route: str
    ok: bool
    status: str
    out_dir: str
    manifest: Dict[str, Any] = dc_field(default_factory=dict)
    manifest_paths: Dict[str, str] = dc_field(default_factory=dict)
    files: Dict[str, str] = dc_field(default_factory=dict)
    intent_json: Optional[str] = None
    handoff: Dict[str, str] = dc_field(default_factory=dict)
    errors: List[str] = dc_field(default_factory=list)
    seconds: float = 0.0

    def as_json(self) -> Dict[str, Any]:
        out = {"route": self.route, "ok": self.ok, "status": self.status,
               "out_dir": self.out_dir, "files": self.files,
               "intent_json": self.intent_json, "handoff": self.handoff,
               "manifest": {k: v for k, v in self.manifest_paths.items()},
               "errors": self.errors, "seconds": self.seconds}
        # issue #24: the ONE --json result must carry the honest release story
        # and the stamps itself, so an AI surface never re-reads manifest.json
        if self.manifest:
            from . import target_status as _ts
            out["release"] = _ts.release_view(self.manifest, files=self.files)
            out["stamps"] = list(((self.manifest.get("honesty") or {})
                                  .get("proof_only_stamps")) or [])
        return out


# ============================================================================
# THE ENTRYPOINT
# ============================================================================

def author(*, prompt: Optional[str] = None, ifc: Optional[str] = None,
           rvt: Optional[str] = None, edit: Optional[str] = None,
           out: Optional[str] = None, **kwargs: Any) -> AuthorResult:
    """The ONE front-door entrypoint (three routes, one intent model, one
    build step, one manifest).  See the module docstring."""
    req = AuthorRequest(prompt=prompt, ifc=ifc, rvt=rvt, edit=edit, out=out, **kwargs)
    return run(req)


def run(req: AuthorRequest) -> AuthorResult:
    """Route ``req``.  Where the job's out dir may live is a property of the
    REQUEST, so it is judged here, for all three routes, before the dir is
    created (issue #452): an ``--out`` that :func:`standalone.out_dir_refusal`
    refuses (inside THIS checkout's quarantine roots or an Autodesk
    installation directory) raises :class:`FrontDoorError` with its ONE line
    and writes zero bytes -- no edited file under ``<repo>/samples/`` reading
    as an Autodesk sample ever after, no intent/handoff files there.  That
    predicate judges BOTH the dir's lexical spelling and its physical
    location (symlinks resolved, case folded), so every alias of the
    checkout -- and an outward link planted inside ``samples/`` (#474) --
    is caught."""
    t0 = time.time()
    route = req.route()
    out_dir = _out_dir(req, route)
    from .standalone import out_dir_refusal
    line = out_dir_refusal(out_dir)
    if line:
        raise FrontDoorError(line)          # before makedirs: nothing lands in the quarantine dir
    os.makedirs(out_dir, exist_ok=True)
    if route == "rvt":
        res = _route_rvt(req, out_dir)
    elif route == "ifc":
        res = _route_ifc(req, out_dir)
    else:
        res = _route_prompt(req, out_dir)
    res.seconds = round(time.time() - t0, 1)
    return res


def _out_dir(req: AuthorRequest, route: str) -> str:
    if req.out:
        return os.path.abspath(req.out)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    if route == "ifc":
        stem = os.path.splitext(os.path.basename(str(req.ifc)))[0]
    elif route == "rvt":
        stem = os.path.splitext(os.path.basename(str(req.rvt)))[0] + "-edit"
    else:
        stem = "prompt-job"
    return os.path.abspath(os.path.join("experiments", "frontdoor", f"{stem}-{stamp}"))


def _stem(req: AuthorRequest, route: str) -> str:
    if req.stem:
        return re.sub(r"[^A-Za-z0-9._-]+", "_", req.stem)
    if route == "ifc":
        return re.sub(r"[^A-Za-z0-9._-]+", "_", os.path.splitext(os.path.basename(str(req.ifc)))[0])
    if route == "rvt":
        return re.sub(r"[^A-Za-z0-9._-]+", "_", os.path.splitext(os.path.basename(str(req.rvt)))[0]) + ".edited"
    return "prompt_room"


# ============================================================================
# the version target (--target-version): resolve + never-silent fallback
# ============================================================================

def _release_of_base(base: Optional[ResolvedBase]) -> int:
    """The release the build on ``base`` PRODUCES: the base file's own detected
    release (``build_intent`` runs inside that release's context, so a 2025
    base yields a 2025 file whoever supplied it), else the registry default."""
    default_release = int(PIN.revit_release)
    if base is None:
        return default_release
    try:
        from .. import versions as _V
        return int(_V.detect_release(base.path) or default_release)
    except Exception:                                                # noqa: BLE001
        return default_release


_NAMED_BY = {"explicit": "--base", "env": "$RVT_GENESIS_BASE"}    # ResolvedBase.source -> flag


def _resolve_base_and_version(req: AuthorRequest):
    """Resolve the base honouring ``req.target_version``.

    Returns ``(base | None, version_block | None, errors)``.  The GUARD
    (``rvt.versions`` + the release registry) makes the failure mode honest,
    never silent: a target whose base is certified resolves THAT base; a
    target still in certification degrades to the certified default base
    with ``status='fallback'`` and THE one clear line (the caller must
    surface the line and emit the version-agnostic IFC addition); a
    user-supplied base of the wrong release is REFUSED outright -- unless its
    bytes ARE one of our certified genesis slots arriving by path, which is
    no user override at all: the target's own slot is resolved instead.  With
    no target the version block reports the release the resolved base
    actually produces (a supplied 2025 base = a 2025 file), never a default
    the delivered bytes contradict (issue #472).
    """
    errors: List[str] = []
    base: Optional[ResolvedBase] = None
    named: Optional[ResolvedBase] = None      # the --base / $RVT_GENESIS_BASE file, once resolved target-less
    target = req.target_version
    if target is None:
        try:
            base = resolve_base(req.base)
        except BaseError as e:
            errors.append(str(e))
        produced = _release_of_base(base)
        flag = _NAMED_BY.get(base.source) if base is not None else None
        if flag:
            trust = (f"our certified Revit {produced} genesis base" if base.certified
                     else "accepted on its supplier's authority")
            origin = f"the release of the base named by {flag} ({trust})"
        else:
            origin = "the certified default release"
        vb = {"requested": None, "status": "unspecified",
              "output_release": produced,
              "note": (f"no --target-version given: the output targets Revit {produced}, "
                       f"{origin}. Revit cannot open a newer file -- ask the user's Revit "
                       "version before promising a .rvt (the tekton-author skill asks first).")}
        return base, vb, errors
    target = int(target)
    try:
        from .. import versions as _V
    except Exception:                                                # pragma: no cover
        _V = None
    try:
        base = resolve_base(req.base, target_release=target)
        vb = {"requested": target, "status": "match", "output_release": target,
              "note": f"Revit {target} target: certified Revit {target} genesis base resolved"}
        return base, vb, errors
    except BaseNotCertified as e:
        pending_msg = str(e)
    except BaseError as e:
        errors.append(str(e))
        return None, {"requested": target, "status": "refused",
                      "output_release": None, "note": str(e)}, errors
    except Exception as e:                                           # VersionError etc.
        # An explicit --base / $RVT_GENESIS_BASE of the WRONG release.  When
        # that file is byte-for-byte one of OUR certified genesis slots (the
        # standalone plugin path passes the bundled base explicitly; a
        # packager or a legacy env export may name any per-release base), this
        # is not a user override at all -- it is our base arriving via a path,
        # whichever slot it is (issue #472: the default AND the 2025/2024
        # copies alike), so the target's own slot decides and a pending target
        # degrades honestly.  A genuinely user-supplied wrong-release base (a
        # firm's file, a stale or mispinned slot) stays REFUSED -- never
        # author a wrong-release file while promising the target.  Resolved
        # target-less, ``pinned`` IS "these bytes are a certified slot's".
        if req.base or os.environ.get("RVT_GENESIS_BASE"):
            try:
                named = resolve_base(req.base)
            except BaseError:                                        # pragma: no cover
                named = None
        if named is None or not named.pinned:
            errors.append(f"target {target}: {e}")
            return None, {"requested": target, "status": "refused",
                          "output_release": None, "note": str(e)}, errors
        pending_msg = str(e)
        # One of our own bases arrived via a path (plugin bundle / legacy
        # `--env` exports): that is not a user override, so the target's OWN
        # certified slot (bundled beside it, sha-pinned) must win before any
        # degrade -- otherwise a 2025 recipient gets a 2026 file plus a false
        # "pending certification" line while G_ABPD_2025 sits in the bundle
        # (issue #24).  Only the pinned-slot resolution runs here.
        saved_env = os.environ.pop("RVT_GENESIS_BASE", None)
        try:
            base = resolve_base(None, target_release=target)
            vb = {"requested": target, "status": "match", "output_release": target,
                  "note": (f"Revit {target} target: certified Revit {target} genesis base "
                           f"resolved (the file named by {_NAMED_BY[named.source]} is our "
                           f"certified Revit {_release_of_base(named)} genesis base; the "
                           "target's own release slot was used instead)")}
            return base, vb, errors
        except (BaseNotCertified, BaseError) as e2:
            pending_msg = str(e2)
        except Exception as e2:                                      # noqa: BLE001
            pending_msg = f"{pending_msg}; slot resolution: {e2}"
        finally:
            if saved_env is not None:
                os.environ["RVT_GENESIS_BASE"] = saved_env
    # ---- the honest FALLBACK: deliver the certified default + THE LINE -----
    base = named                              # our slot copy named by path (already resolved), else:
    if base is None:
        try:
            base = resolve_base(req.base)
        except BaseError as e:
            errors.append(str(e))
    produced = _release_of_base(base)
    from . import target_status as _ts
    support = _ts.support_status(target)
    supported = _ts.supported_targets()
    nearest: Optional[int] = None
    if support == "certified-base" or _V is None:
        # a certified slot that could not be resolved on THIS machine (bundle
        # incomplete): the version model's uniform "pending" wording stands
        line = (_V.creation_fallback_line(target, produced) if _V is not None else
                f"target {target} requested: the {target} base is pending certification; "
                f"this file targets {produced} -- your Revit {target} cannot open it; "
                f"the IFC alongside is version-agnostic")
    else:
        # a release we do not create for (older / unknown year): say THAT, name
        # what is supported and the nearest target, never call it "pending"
        nearest = _ts.nearest_supported(target)
        parts = [f"target {target} requested: tekton has no certified Revit {target} "
                 f"creation base (supported: {', '.join(map(str, supported))})"]
        if nearest is not None and nearest > target:
            parts.append(f"the nearest supported target is Revit {nearest}, which "
                         f"Revit {target} cannot open either")
        parts.append(f"this file targets {produced} -- your Revit {target} cannot open it")
        parts.append("the IFC alongside is version-agnostic (links into Revit 2019+)")
        line = "; ".join(parts)
    vb = {"requested": target, "status": "fallback", "output_release": produced,
          "line": line,
          "target_support": support,
          "nearest_supported": nearest,
          "supported_targets": supported,
          "base_status": release_status(target),
          "pending": pending_msg,
          "note": ("DELIVERABLE RULE: the buildable file is delivered (it targets Revit "
                   f"{produced}); the line above states plainly that the requested Revit "
                   f"{target} cannot open it, and a version-agnostic IFC of the SAME "
                   "intent is emitted as an ADDITION (never as a replacement)")}
    if _V is not None:
        try:
            vb["creation_status"] = _V.creation_status(target)
        except Exception:                                            # pragma: no cover
            pass
    return base, vb, errors


def _emit_ifc_addition(vb: Optional[Dict[str, Any]], res: "AuthorResult",
                       out_dir: str, stem: str, *, model=None,
                       source_ifc: Optional[str] = None,
                       errors: Optional[List[str]] = None) -> None:
    """On a version fallback, put the version-agnostic IFC beside the build:
    the input IFC verbatim (``--ifc`` route) or the intent re-emitted as IFC
    (``--prompt`` route).  Fills ``vb['ifc_addition']`` + ``res.files['ifc']``."""
    if not vb or vb.get("status") != "fallback":
        return
    try:
        if source_ifc:
            import shutil
            dst = os.path.join(out_dir, os.path.basename(str(source_ifc)))
            if os.path.abspath(dst) != os.path.abspath(str(source_ifc)):
                shutil.copyfile(str(source_ifc), dst)
            vb["ifc_addition"] = _rel(dst) or dst
            vb["ifc_addition_source"] = "the input IFC, copied beside the build (already version-agnostic)"
            res.files.setdefault("ifc", dst)
        elif model is not None:
            from . import ifc_out as _ifc_out
            dst = os.path.join(out_dir, f"{stem}.ifc")
            _ifc_out.write_intent_ifc(model, dst, note=str(vb.get("line") or ""))
            vb["ifc_addition"] = _rel(dst) or dst
            vb["ifc_addition_source"] = ("the resolved intent re-emitted as IFC4 "
                                         "(rvt.frontdoor.ifc_out; re-consumable via "
                                         "`frontdoor author --ifc`)")
            res.files.setdefault("ifc", dst)
        else:
            vb["ifc_addition"] = None
            vb["ifc_addition_source"] = "no intent resolved: nothing to emit"
    except Exception as e:                                           # noqa: BLE001
        (errors if errors is not None else []).append(
            f"IFC addition failed: {type(e).__name__}: {e}")
        vb["ifc_addition"] = None
        vb["ifc_addition_source"] = f"FAILED: {type(e).__name__}: {e}"


# ============================================================================
# route: --prompt
# ============================================================================

def _route_prompt(req: AuthorRequest, out_dir: str) -> AuthorResult:
    from . import prompt_intent as PP
    from . import build as B
    from . import manifest as MF

    res = AuthorResult(route="prompt", ok=False, status="", out_dir=out_dir)
    text = str(req.prompt or "").strip()
    if not text:
        res.errors.append("empty --prompt")
        res.status = "FAILED (empty prompt)"
        return res
    inputs: Dict[str, Any] = {"prompt": text}
    handoff: Dict[str, str] = {}
    model = parsed = None
    intent_json = None
    coverage = None
    errors: List[str] = []

    # ---- (b) the built-in fallback parse (also renders the handoff) --------
    try:
        model, parsed = PP.prompt_to_intent(text)
        coverage = parsed.coverage.as_json()
        intent_json = os.path.join(out_dir, "intent.json")
        _intent.write_intent_json(model, intent_json)
        res.intent_json = intent_json
        inputs["fallback_parser"] = ("rules-first deterministic (no external model call, "
                                     "no API key)")
    except Exception as e:                                           # noqa: BLE001
        errors.append(f"prompt parse failed: {type(e).__name__}: {e}")

    # ---- (a) the PRIMARY path: the AI-surface handoff package ---------------
    if not req.no_handoff and model is not None:
        try:
            hp = PP.write_handoff(text, out_dir, parsed=parsed, model=model)
            handoff = {k: (_rel(v) or v) for k, v in hp.items()}
            handoff["primary_path_note"] = (
                "an AI surface executes HANDOFF.md/scene-brief.json with Three.js, exports "
                "IFC4 (tekton-ifc exporter, our tagging-contract Psets), and the .ifc "
                "re-enters via `frontdoor author --ifc` -- the recommended path")
            res.handoff = handoff
        except Exception as e:                                       # noqa: BLE001
            errors.append(f"handoff package failed: {type(e).__name__}: {e}")

    # ---- the fallback BUILD (works with no model call) ----------------------
    build_json: Optional[Dict[str, Any]] = None
    base, version_block, verrors = _resolve_base_and_version(req)
    if verrors and not req.handoff_only:
        errors += verrors
    if req.handoff_only:
        inputs["handoff_only"] = True
    elif model is not None and base is not None:
        opts = B.BuildOptions(out_dir=out_dir, base=base, stem=_stem(req, "prompt"),
                              strict=req.strict, specimen_src=req.specimens,
                              stages=req.stages, wall_mode=req.wall_mode,
                              symbol_solid=not req.symbol_hollow,
                              validate=not req.no_validate, quiet=req.quiet)
        br = B.build_intent(model, opts)
        build_json = br.as_json()
        res.files = {k: v for k, v in build_json.get("files", {}).items() if v}
        errors += br.errors

    # version fallback: the version-agnostic IFC rides BESIDE the build
    _emit_ifc_addition(version_block, res, out_dir, _stem(req, "prompt"),
                       model=model, errors=errors)

    manifest = MF.build_manifest(
        route="prompt", inputs=inputs, base=(base or _explicit_or_pin(req)), out_dir=out_dir,
        intent_summary=(_intent.summarize(model) if model is not None else None),
        intent_json=intent_json, build=build_json, coverage=coverage,
        handoff=handoff or None, errors=errors, version=version_block)
    if req.handoff_only and not build_json:
        manifest["status"] = ("HANDOFF-ONLY (no .rvt built: hand scene-brief.json / HANDOFF.md "
                              "to an AI surface, then run --ifc on its export)")
    res.manifest = manifest
    res.manifest_paths = MF.write_manifest(manifest, out_dir)
    res.status = str(manifest.get("status"))
    res.errors = list(errors)
    res.ok = _ok_from_status(res.status)
    return res


# ============================================================================
# route: --ifc
# ============================================================================

def _route_ifc(req: AuthorRequest, out_dir: str) -> AuthorResult:
    from . import build as B
    from . import manifest as MF

    res = AuthorResult(route="ifc", ok=False, status="", out_dir=out_dir)
    ifc_path = os.path.abspath(str(req.ifc))
    inputs: Dict[str, Any] = {"ifc": ifc_path}
    errors: List[str] = []
    model = None
    intent_json = None
    if not os.path.isfile(ifc_path):
        res.errors.append(f"--ifc file not found: {req.ifc}")
        res.status = "FAILED (ifc file not found)"
        return res
    try:
        model = _intent.intent_from_ifc(ifc_path)
        intent_json = os.path.join(out_dir, "intent.json")
        _intent.write_intent_json(model, intent_json)
        res.intent_json = intent_json
        inputs["intent_resolver"] = ("rvt.ifc.intent (placement chains + world geometry + "
                                     "tagging-contract Pset join key)")
    except ExtraNotInstalled as e:         # a lazy optional extra (numpy) is absent (#127):
        # ONE sentence, and short enough to ride whole in the manifest's
        # `FAILED (<errors[0][:160]>)` status a skill relays verbatim
        errors.append(f"IFC intent failed: the --ifc route needs {e.name}, not installed on "
                      f"this interpreter -- one-time fix: python -m pip install {e.name} "
                      "(--prompt / --rvt run without it)")
    except Exception as e:                                           # noqa: BLE001
        errors.append(f"IFC intent failed: {type(e).__name__}: {e}")

    build_json: Optional[Dict[str, Any]] = None
    base: Optional[ResolvedBase] = None
    version_block: Optional[Dict[str, Any]] = None
    if model is not None:
        base, version_block, verrors = _resolve_base_and_version(req)
        errors += verrors
        if base is not None:
            opts = B.BuildOptions(out_dir=out_dir, base=base, stem=_stem(req, "ifc"),
                                  strict=req.strict, specimen_src=req.specimens,
                                  stages=req.stages, wall_mode=req.wall_mode,
                                  symbol_solid=not req.symbol_hollow,
                                  validate=not req.no_validate, quiet=req.quiet)
            br = B.build_intent(model, opts)
            build_json = br.as_json()
            res.files = {k: v for k, v in build_json.get("files", {}).items() if v}
            errors += br.errors

    # version fallback: the user's IFC is ALREADY the version-agnostic form --
    # deliver a copy beside the build so the delivery is self-contained
    _emit_ifc_addition(version_block, res, out_dir, _stem(req, "ifc"),
                       model=model, source_ifc=ifc_path, errors=errors)

    manifest = MF.build_manifest(
        route="ifc", inputs=inputs, base=(base or _explicit_or_pin(req)), out_dir=out_dir,
        intent_summary=(_intent.summarize(model) if model is not None else None),
        intent_json=intent_json, build=build_json, coverage=None, handoff=None,
        errors=errors, version=version_block)
    res.manifest = manifest
    res.manifest_paths = MF.write_manifest(manifest, out_dir)
    res.status = str(manifest.get("status"))
    res.errors = list(errors)
    res.ok = _ok_from_status(res.status)
    return res


# ============================================================================
# route: --rvt + --edit
# ============================================================================

def _route_rvt(req: AuthorRequest, out_dir: str) -> AuthorResult:
    res = AuthorResult(route="rvt", ok=False, status="", out_dir=out_dir)
    rvt_path = os.path.abspath(str(req.rvt))
    if not os.path.isfile(rvt_path):
        res.errors.append(f"--rvt file not found: {req.rvt}")
        res.status = "FAILED (rvt file not found)"
        return res
    # the INPUT's era / release is classified on EVERY job before anything
    # opens it (issue #176): a known release proceeds as before, a 2019+
    # release tekton has never read proceeds stamped UNVERIFIED-RELEASE, and
    # a pre-2019 / undetectable / non-Revit input is refused with one line
    from .input_release import input_release_block
    in_rel = input_release_block(rvt_path)
    if in_rel["status"] == "refused":
        _refuse_rvt_input(req, out_dir, res, rvt_path, in_rel)
    # the edit runs under the INPUT file's own release (host release context,
    # issue #14): a Revit 2025/2024 project is opened, planned, edited and
    # verified with its release's framing + codecs; a native file enters no
    # context; a release we cannot author into is reported, never guessed --
    # and is then at least READ under its own schema (the instruments'
    # lenient ladder, #121) so open / plan are schema-directed, not 2026-framed
    from .release_ctx import enter_host_release
    with contextlib.ExitStack() as stack:
        ctx_note = enter_host_release(stack, rvt_path)
        if ctx_note:
            from ..global_framing import enter_own_release
            rung = enter_own_release(stack, rvt_path)
            if rung:
                ctx_note = f"{ctx_note}; read side: {rung}"
        return _route_rvt_inner(req, out_dir, res, rvt_path, ctx_note, in_rel)


def _refuse_rvt_input(req: AuthorRequest, out_dir: str, res: AuthorResult,
                      rvt_path: str, in_rel: Dict[str, Any]) -> NoReturn:
    """Write the refusal manifest for an unreadable-era input, then raise
    :class:`InputReleaseRefused` (the ONE line; exit 2 at the CLI)."""
    from . import manifest as MF
    line = str(in_rel["line"])
    res.manifest = MF.edit_manifest(
        inputs={"rvt": rvt_path, "edit": req.edit},
        base_note="no edit attempted: the input's release cannot be read (see input_release)",
        out_dir=out_dir, edit_spec={}, run={}, errors=[line], input_release=in_rel)
    res.manifest_paths = MF.write_manifest(res.manifest, out_dir)
    res.status = line
    res.errors = [line]
    raise InputReleaseRefused(line, res)


def _route_rvt_inner(req: AuthorRequest, out_dir: str, res: AuthorResult,
                     rvt_path: str, ctx_note: Optional[str],
                     in_rel: Dict[str, Any]) -> AuthorResult:
    from . import edit as E
    from . import manifest as MF

    inputs: Dict[str, Any] = {"rvt": rvt_path, "edit": req.edit}
    errors: List[str] = []
    # open the project (file-driven) and normalise the edit into ops
    editables_before = None
    spec = None
    try:
        from ..mutate import Document
        doc = Document.from_file(rvt_path)
        try:
            editables_before = {k: v[:24] for k, v in E.editables(doc).items()}
        except Exception:                                            # noqa: BLE001
            editables_before = None
        spec = E.parse_edit_spec(str(req.edit), doc=doc)
    except E.EditParseError as e:
        errors.append(f"edit not understood: {e}")
    except Exception as e:                                           # noqa: BLE001
        errors.append(f"cannot open/plan {rvt_path}: {type(e).__name__}: {e}"
                      + (f" ({ctx_note})" if ctx_note else ""))

    run: Dict[str, Any] = {}
    if spec is not None and not errors:
        inputs["ops"] = spec.ops
        try:
            run = E.run_edit(rvt_path, spec, out_dir,
                             out_name=(req.stem or None),
                             validate=not req.no_validate,
                             strict_validate=req.strict_validate,
                             quiet=req.quiet)
            if run.get("out_rvt"):
                res.files = {"edited": run["out_rvt"]}
        except Exception as e:                                       # noqa: BLE001
            errors.append(f"edit run failed: {type(e).__name__}: {e}")

    base_note = ("the --rvt route edits the user's own file in place-copy (never an Autodesk "
                 "sample base test: the input is whatever the user supplies; deliverability of "
                 "the result is ledgered against that input by the job runner's P0 gate)")
    # the input's release is auto-detected and stated EVERY time (issue #24):
    # an edit keeps its input's release, so the recipient question is only
    # "can you open the input" -- answered here without a follow-up call
    version_block = _rvt_route_version_block(
        int(req.target_version) if req.target_version is not None else None, in_rel["year"])
    manifest = MF.edit_manifest(
        inputs=inputs, base_note=base_note, out_dir=out_dir,
        edit_spec=(spec.as_json() if spec is not None else {"error": errors[:1]}),
        run=run, editables_before=editables_before, errors=errors,
        version=version_block, input_release=in_rel)
    res.manifest = manifest
    res.manifest_paths = MF.write_manifest(manifest, out_dir)
    res.status = str(manifest.get("status"))
    res.errors = list(errors)
    res.ok = (run.get("rc") == 0 and bool(run.get("out_rvt")) and not errors)
    return res


# ============================================================================
# helpers
# ============================================================================

def _rvt_route_version_block(target: Optional[int], in_rel: Optional[int]) -> Dict[str, Any]:
    """The honest version story for an EDIT: the output preserves the input
    file's release ``in_rel`` (the year the input-release precheck detected;
    an edit cannot transmute a 2026 file into a 2025 one).  ``target=None`` =
    the recipient's year was not stated: the detected input release is still
    reported (status ``detected``)."""
    vb: Dict[str, Any] = {"requested": (int(target) if target is not None else None),
                          "input_release": in_rel, "output_release": in_rel}
    if in_rel is not None and target is None:
        vb["status"] = "detected"
        vb["note"] = (f"the input file is Revit {in_rel}; the edited output stays Revit "
                      f"{in_rel} (opens in Revit {in_rel} and newer, never older)")
    elif in_rel is None:
        vb["status"] = "unknown-input-release"
        vb["note"] = ("could not determine the input file's Revit release; the edit "
                      "preserves whatever it is -- the output opens wherever the input did")
    elif int(in_rel) == int(target):
        vb["status"] = "match"
        vb["note"] = f"the input file is Revit {in_rel}; the edited output stays Revit {in_rel}"
    elif int(in_rel) > int(target):
        vb["status"] = "fallback"
        vb["line"] = (f"target {int(target)} requested: the --rvt route preserves the input "
                      f"file's release (Revit {in_rel}) -- your Revit {int(target)} cannot "
                      f"open the edited output either; supply a Revit {int(target)} input "
                      "file to get a Revit-openable edit")
    else:
        vb["status"] = "match-older"
        vb["note"] = (f"the input file is Revit {in_rel} (older than the target {int(target)}); "
                      f"Revit {int(target)} opens older files, so the edited output is usable")
    return vb


def _rel(p: Optional[str]) -> Optional[str]:
    if not p:
        return None
    try:
        r = os.path.relpath(p, _base.repo_root())
        return r if not r.startswith("..") else os.path.abspath(p)
    except ValueError:
        return os.path.abspath(p)


def _ok_from_status(status: str) -> bool:
    s = str(status).upper()
    return not (s.startswith("FAILED") or s.startswith("NO-OUTPUT")
                or s.startswith("SELF-CHECKS FAILED"))


def _explicit_or_pin(req: AuthorRequest) -> ResolvedBase:
    """A ResolvedBase for the manifest when the real resolution failed (so
    the manifest still names what was attempted -- the target release's own
    slot when the registry has one, #264)."""
    slot = PIN.release_slot(int(req.target_version or PIN.revit_release)) or {}
    p = (os.path.abspath(req.base) if req.base
         else PIN.candidate_paths(relpath=slot.get("relpath"))[0])
    return ResolvedBase(path=p, source=("explicit" if req.base else "pinned-repo"),
                        sha256="(unresolved)", pinned=False,
                        is_autodesk_sample=is_autodesk_sample(p), certified=False,
                        warnings=["base NOT resolved -- no build was attempted"])
