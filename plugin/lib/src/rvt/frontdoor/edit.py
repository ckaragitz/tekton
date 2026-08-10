"""rvt.frontdoor.edit -- input route (3): an EXISTING ``.rvt`` + an edit.

``frontdoor author --rvt FILE.rvt --edit "TEXT|spec"`` opens the project
with :meth:`rvt.mutate.Document.from_file` (file-driven, no corpus) and
drives the edit CLI's proven operations -- delete (+ cascade), modify
(rename / set-mark / set-level / set-param), move, retype, and the create
ops of an edit run (add-instance / add-circuit) -- by DELEGATING to the job
runner's certified EDIT pipeline (``tools/rvt_job.py``: rvt.manipulate for
every manipulate op in ONE commit + rvt.mutate for adds + the structural /
validation / identity / provenance gates).  The front door adds only:

* :func:`parse_edit_spec` -- accepts THREE shapes for ``--edit``:
    - a path to an ``ops.json`` (list of ops, or ``{"ops": [...]}``),
    - inline JSON (``'[{"op": "move", ...}]'``),
    - or NATURAL-LANGUAGE edit text ("delete DP-1 with cascade; move LP-2
      to 3, 4; rename panel HG4 to HG4A") parsed by a rules-first grammar,
      names/marks resolved to element ids from the file itself.
  Every op lands in the ONE ops vocabulary the job runner already speaks --
  no fourth edit dialect.
* :func:`editables` -- the CRUD-affordance inventory: what this file lets
  you modify / move / retype / delete (panels, instances, walls, levels
  with ids + names), for the manifest and for name resolution.

Territory: ``src/rvt/frontdoor/`` (front-door stream).  Imports
``tools/rvt_job.py`` as a module (never edits it).
"""
from __future__ import annotations

import contextlib
import importlib.util
import json
import math
import os
import re
import sys
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, List, Optional, Tuple

from .base import repo_root
from .. import _jsonsafe
from .._logsink import stage_stdout

__all__ = ["EditParseError", "EditSpec", "parse_edit_spec", "editables",
           "resolve_ref", "load_job_module", "job_stderr_joins_stdout", "run_edit"]

FT_PER_M = 3.280839895013123


class EditParseError(ValueError):
    """The --edit input could not be turned into ops."""


# ---------------------------------------------------------------------------
# tools/rvt_job.py as a module (the certified edit pipeline; single source)
# ---------------------------------------------------------------------------

_JOB = None


def load_job_module():
    """Import ``tools/rvt_job.py`` (the ONE existing edit front door) as a
    module.  Cached and registered as ``sys.modules["rvt_job"]``, so every
    in-process caller shares one executed copy (#477); raises ImportError if
    the tools tree is absent (a pip-installed engine without the repo
    checkout)."""
    global _JOB
    if _JOB is not None:
        return _JOB
    cands = [os.path.join(repo_root(), "tools", "rvt_job.py")]
    plugin_root = os.environ.get("RVT_PLUGIN_ROOT")
    if plugin_root:
        cands.append(os.path.join(plugin_root, "skills", "tekton-native", "scripts", "rvt_job.py"))
    for p in cands:
        if os.path.isfile(p):
            spec = importlib.util.spec_from_file_location("rvt_job", p)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = mod
                spec.loader.exec_module(mod)
                _JOB = mod
                return mod
    raise ImportError("tools/rvt_job.py not found (the --rvt route delegates to the "
                      "job runner's edit pipeline); tried: " + "; ".join(cands))


@contextlib.contextmanager
def job_stderr_joins_stdout(quiet: bool):
    """``quiet``: for the block, the in-process job runner's stderr (its ONE
    ``[rvt_job] FAILED (…)`` verdict line) goes wherever ``sys.stdout`` points
    at ENTRY -- entered after :func:`stage_stdout`, that is the same stage log
    (or degrade sink), so the caller's own stderr stays 0 B; the reason rides
    in the manifest's ``status`` anyway.  Not ``quiet``: stderr stays live."""
    with (contextlib.redirect_stderr(sys.stdout) if quiet else contextlib.nullcontext()):
        yield


# ---------------------------------------------------------------------------
# the editable inventory (CRUD affordances + name resolution)
# ---------------------------------------------------------------------------

def editables(doc, *, limit: Optional[int] = None) -> Dict[str, List[dict]]:
    """What ``doc`` (a :class:`rvt.mutate.Document`) lets you edit: family
    instances (equipment/devices), walls and levels, each with its id, class,
    category and best human name.  Powers ``--rvt`` name resolution and the
    manifest's CRUD-affordance section."""
    from .. import inventory as INV
    out: Dict[str, List[dict]] = {"instances": [], "walls": [], "levels": [], "circuits": []}
    for eid in doc.ids_of_class("FamilyInstance"):
        try:
            name = INV.element_name(doc, eid)
        except Exception:
            name = None
        out["instances"].append({"id": eid, "name": name,
                                 "category": doc.category_of(eid), "class": "FamilyInstance"})
    for eid in doc.ids_of_class("SWall"):
        try:
            name = INV.element_name(doc, eid)
        except Exception:
            name = None
        v = doc.value(eid) or {}
        out["walls"].append({"id": eid, "name": name or f"Wall {eid}", "class": "SWall",
                             "type_id": v.get("m_WallAttributesId")})
    for lv in doc.levels():
        out["levels"].append({"id": lv["id"], "name": lv.get("name"), "class": "Level",
                              "elevation_ft": lv.get("elevation_ft")})
    for eid in doc.ids_of_class("RbsElectricalSystem"):
        v = doc.value(eid) or {}
        out["circuits"].append({"id": eid, "name": v.get("m_strName") or v.get("m_number"),
                                "class": "RbsElectricalSystem"})
    if limit:
        for k in out:
            out[k] = out[k][:limit]
    return out


def _name_index(doc) -> Dict[str, List[int]]:
    """lower-cased name -> element ids (instances, walls, levels)."""
    idx: Dict[str, List[int]] = {}
    inv = editables(doc)
    for row in inv["instances"] + inv["walls"] + inv["levels"] + inv["circuits"]:
        n = row.get("name")
        if n:
            idx.setdefault(str(n).strip().lower(), []).append(int(row["id"]))
    return idx


def resolve_ref(doc, ref: str, *, index: Optional[Dict[str, List[int]]] = None) -> int:
    """Resolve an element reference: an id (``1466502`` / ``#1466502`` /
    ``element 1466502``) or a NAME / mark / panel name (exact match first,
    then unique substring).  Ambiguity or absence is an :class:`EditParseError`
    that names the candidates -- never a guess."""
    s = str(ref).strip().strip("\"'`")
    m = re.fullmatch(r"(?:element|elem|id|the)?\s*#?\s*(\d{2,10})", s, re.I)
    if m:
        eid = int(m.group(1))
        if not doc.exists(eid):
            raise EditParseError(f"element id {eid} does not exist in this file")
        return eid
    key = re.sub(r"^(?:the|panel|panelboard|transformer|switchboard|wall|instance|"
                 r"equipment|element)\s+", "", s, flags=re.I).strip().lower()
    idx = index if index is not None else _name_index(doc)
    if key in idx:
        ids = sorted(set(idx[key]))
        if len(ids) == 1:
            return ids[0]
        raise EditParseError(f"name {ref!r} matches {len(ids)} elements {ids[:8]}: use an id")
    subs = sorted({i for n, ids in idx.items() if key and key in n for i in ids})
    if len(subs) == 1:
        return subs[0]
    if not subs:
        near = [n for n in idx if key and (key.split("-")[0] in n or n in key)][:8]
        raise EditParseError(f"no element named {ref!r} in this file"
                             + (f" (did you mean: {', '.join(near)})" if near else ""))
    raise EditParseError(f"name {ref!r} is ambiguous ({len(subs)} candidates {subs[:8]}): use an id")


# ---------------------------------------------------------------------------
# the --edit input: JSON path | inline JSON | natural-language text
# ---------------------------------------------------------------------------

@dataclass
class EditSpec:
    """The normalised edit: ops in the job runner's vocabulary + coverage."""
    ops: List[dict]
    source: str                              # 'ops-file' | 'inline-json' | 'text'
    understood: List[dict] = dc_field(default_factory=list)
    unparsed: List[str] = dc_field(default_factory=list)
    resolutions: Dict[str, int] = dc_field(default_factory=dict)   # ref -> id

    def as_json(self) -> Dict[str, Any]:
        return {"source": self.source, "ops": list(self.ops),
                "understood": list(self.understood), "unparsed": list(self.unparsed),
                "resolutions": dict(self.resolutions),
                "vocabulary": ("delete{id,cascade} | rename{id,name} | set-mark{id,mark} | "
                               "set-level{id,elevation_ft|elevation_m} | set-param{id,param_id,"
                               "value,holder?} (holder = m_pParamValueSet{AString|Double|Int|"
                               "ElementId}; only needed to type an ABSENT row, e.g. an ElementId "
                               "-1 is a bare int) | move{id,to|delta,rotation_deg} | retype{id,symbol} | "
                               "add-instance{symbol,position_ft,rotation_deg,name} | "
                               "add-circuit{panel,load} -- the SAME ops.json the job runner "
                               "(tools/rvt_job.py edit) accepts")}


#: NL grammar -- one rule per op (clause-level; ';' / 'then' / newline separate clauses)
_RE_DELETE = re.compile(r"^(?:delete|remove|drop)\s+(?P<ref>.+?)(?P<casc>\s+(?:with\s+cascade|"
                        r"cascade|and\s+(?:all\s+)?(?:its\s+)?dependen(?:ts|cies)))?$", re.I)
_RE_MOVE_TO = re.compile(r"^move\s+(?P<ref>.+?)\s+to\s+(?P<xyz>[-\d.,\s]+?)"
                         r"(?P<unit>\s*(?:ft|feet|foot|m|meters?|metres?))?"
                         r"(?:\s+(?:and\s+)?rotat(?:e|ion)\s+(?:to\s+|by\s+)?(?P<rot>-?\d+(?:\.\d+)?)"
                         r"\s*(?:deg(?:rees?)?|°)?)?$", re.I)
_RE_MOVE_BY = re.compile(r"^move\s+(?P<ref>.+?)\s+by\s+(?P<xyz>[-\d.,\s]+?)"
                         r"(?P<unit>\s*(?:ft|feet|foot|m|meters?|metres?))?$", re.I)
_RE_ROTATE = re.compile(r"^rotate\s+(?P<ref>.+?)\s+(?:to|by)\s+(?P<rot>-?\d+(?:\.\d+)?)"
                        r"\s*(?:deg(?:rees?)?|°)?$", re.I)
_RE_RENAME = re.compile(r"^rename\s+(?:panel\s+|panelboard\s+)?(?P<ref>.+?)\s+(?:to|as)\s+"
                        r"[\"']?(?P<name>[^\"']+?)[\"']?$", re.I)
_RE_SETMARK = re.compile(r"^(?:set\s+(?:the\s+)?mark\s+(?:of|on|for)\s+(?P<ref>.+?)\s+to|"
                         r"mark\s+(?P<ref2>.+?)\s+(?:as|=))\s*[\"']?(?P<mark>[^\"']+?)[\"']?$", re.I)
_RE_SETLEVEL = re.compile(r"^set\s+(?:the\s+)?(?:level\s+)?(?P<ref>.+?)\s+elevation\s+to\s+"
                          r"(?P<val>-?\d+(?:\.\d+)?)\s*(?P<unit>ft|feet|foot|m|meters?|metres?)?$", re.I)
_RE_RETYPE = re.compile(r"^retype\s+(?P<ref>.+?)\s+to\s+(?:symbol\s+|type\s+)?(?P<sym>#?\d{2,10}|.+)$", re.I)
_RE_SETPARAM = re.compile(r"^set\s+param(?:eter)?\s+(?P<pid>-?\d+)\s+(?:of|on|for)\s+"
                          r"(?P<ref>.+?)\s+to\s+(?P<val>.+)$", re.I)


def _parse_xyz(txt: str, unit: Optional[str]) -> List[float]:
    parts = [p for p in re.split(r"[,\s]+", txt.strip()) if p]
    vals = [float(p) for p in parts]
    if len(vals) == 2:
        vals.append(0.0)
    if len(vals) != 3:
        raise EditParseError(f"expected 2 or 3 coordinates, got {txt!r}")
    u = (unit or "").strip().lower()
    if u.startswith(("m", "meter", "metre")):
        vals = [v * FT_PER_M for v in vals]
    return vals


def _coerce(val: str):
    t = val.strip().strip("\"'")
    for cast in (int, float):
        try:
            return cast(t)
        except ValueError:
            pass
    if t.lower() in ("true", "false"):
        return t.lower() == "true"
    return t


def parse_edit_spec(spec: str, doc=None) -> EditSpec:
    """Normalise the ``--edit`` argument into the job runner's ops.

    ``spec`` = a path to ops.json | inline JSON | natural-language text.
    ``doc`` (the opened :class:`rvt.mutate.Document`) is required to
    resolve NAMES in text edits; ids need no doc.
    """
    if spec is None or not str(spec).strip():
        raise EditParseError("empty --edit (give ops.json, inline JSON, or an edit sentence)")
    s = str(spec).strip()
    # -- 1. a JSON file ------------------------------------------------------
    if os.path.isfile(s) and s.lower().endswith(".json"):
        with open(s) as fh:
            payload = json.load(fh)
        ops = payload.get("ops") if isinstance(payload, dict) else payload
        if not isinstance(ops, list) or not ops:
            raise EditParseError(f"{s}: ops.json must be a non-empty list (or {{\"ops\": [...]}})")
        return EditSpec(ops=[dict(o) for o in ops], source="ops-file",
                        understood=[{"op": _opkey(o)} for o in ops])
    # -- 2. inline JSON -------------------------------------------------------
    if s.startswith("[") or s.startswith("{"):
        try:
            payload = json.loads(s)
        except json.JSONDecodeError as e:
            raise EditParseError(f"inline JSON edit is not valid JSON: {e}")
        ops = payload.get("ops") if isinstance(payload, dict) else payload
        if isinstance(ops, dict):
            ops = [ops]
        if not isinstance(ops, list) or not ops:
            raise EditParseError("inline JSON edit must be a non-empty list of ops")
        return EditSpec(ops=[dict(o) for o in ops], source="inline-json",
                        understood=[{"op": _opkey(o)} for o in ops])
    # -- 3. natural-language text -------------------------------------------
    return _parse_text(s, doc)


def _opkey(o: dict) -> str:
    return str(o.get("op") or o.get("type") or "").strip().lower()


def _parse_text(text: str, doc) -> EditSpec:
    clauses = [c.strip() for c in re.split(r";|\n|\bthen\b|\band\s+then\b", text) if c.strip()]
    ops: List[dict] = []
    understood: List[dict] = []
    unparsed: List[str] = []
    resolutions: Dict[str, int] = {}
    index = _name_index(doc) if doc is not None else {}

    def rid(ref: str) -> int:
        if doc is None:
            m = re.fullmatch(r"(?:element|elem|id)?\s*#?\s*(\d{2,10})", ref.strip(), re.I)
            if m:
                return int(m.group(1))
            raise EditParseError(f"cannot resolve name {ref!r} without the opened file")
        eid = resolve_ref(doc, ref, index=index)
        resolutions[ref.strip()] = eid
        return eid

    for cl in clauses:
        c = cl.rstrip(".")
        try:
            if (m := _RE_DELETE.match(c)):
                op = {"op": "delete", "id": rid(m.group("ref")), "cascade": bool(m.group("casc"))}
            elif (m := _RE_MOVE_TO.match(c)):
                op = {"op": "move", "id": rid(m.group("ref")), "to": _parse_xyz(m.group("xyz"), m.group("unit"))}
                if m.group("rot"):
                    op["rotation_deg"] = float(m.group("rot"))
            elif (m := _RE_MOVE_BY.match(c)):
                op = {"op": "move", "id": rid(m.group("ref")), "delta": _parse_xyz(m.group("xyz"), m.group("unit"))}
            elif (m := _RE_ROTATE.match(c)):
                op = {"op": "move", "id": rid(m.group("ref")), "delta": [0.0, 0.0, 0.0],
                      "rotation_deg": float(m.group("rot"))}
            elif (m := _RE_RENAME.match(c)):
                op = {"op": "rename", "id": rid(m.group("ref")), "name": m.group("name").strip()}
            elif (m := _RE_SETMARK.match(c)):
                ref = m.group("ref") or m.group("ref2")
                op = {"op": "set-mark", "id": rid(ref), "mark": m.group("mark").strip()}
            elif (m := _RE_SETLEVEL.match(c)):
                val = float(m.group("val"))
                unit = (m.group("unit") or "ft").lower()
                op = ({"op": "set-level", "id": rid(m.group("ref")), "elevation_m": val}
                      if unit.startswith(("m", "meter", "metre"))
                      else {"op": "set-level", "id": rid(m.group("ref")), "elevation_ft": val})
            elif (m := _RE_RETYPE.match(c)):
                sym_txt = m.group("sym").strip().lstrip("#")
                sym = int(sym_txt) if sym_txt.isdigit() else rid(sym_txt)
                op = {"op": "retype", "id": rid(m.group("ref")), "symbol": sym}
            elif (m := _RE_SETPARAM.match(c)):
                op = {"op": "set-param", "id": rid(m.group("ref")),
                      "param_id": int(m.group("pid")), "value": _coerce(m.group("val"))}
            else:
                unparsed.append(cl)
                continue
        except EditParseError:
            raise
        except (ValueError, TypeError) as e:
            unparsed.append(f"{cl}  ({type(e).__name__}: {e})")
            continue
        ops.append(op)
        understood.append({"clause": cl, "op": op})
    if not ops:
        raise EditParseError(
            "no edit understood from the text. Grammar: 'delete <name|id> [with cascade]', "
            "'move <ref> to X,Y[,Z] [ft|m] [rotation N deg]', 'move <ref> by dX,dY[,dZ]', "
            "'rotate <ref> to N deg', 'rename panel <ref> to NAME', "
            "'set mark of <ref> to MARK', 'set level <ref> elevation to N ft|m', "
            "'retype <ref> to <symbol id>', 'set parameter <id> of <ref> to VALUE' "
            "(or pass ops.json / inline JSON). Unparsed: " + "; ".join(unparsed[:4]))
    return EditSpec(ops=ops, source="text", understood=understood,
                    unparsed=unparsed, resolutions=resolutions)


# ---------------------------------------------------------------------------
# run the certified edit pipeline (tools/rvt_job.py edit)
# ---------------------------------------------------------------------------

def run_edit(rvt_path: str, spec: EditSpec, out_dir: str, *,
             out_name: Optional[str] = None,
             validate: bool = True, strict_validate: bool = False,
             quiet: bool = False) -> Dict[str, Any]:
    """Apply ``spec.ops`` to ``rvt_path`` through the job runner's EDIT
    mode (rvt.manipulate ops in ONE commit + rvt.mutate adds + the hard
    gates) and return {rc, out_rvt, job_manifest, validation, log_path,
    degradations}.

    The job runner writes ``<out>.manifest.json`` / ``<out>.validation.json``;
    the front door's own manifest wraps them.  ``quiet``: the runner's
    progress AND its stderr verdict line stream into ``<out_dir>/edit.log``
    (:mod:`rvt._logsink`, the build's ``build.log`` shape) and
    ``log_path`` names it; an unwritable ``out_dir`` costs the log (one
    ``degradations`` note), never the edit.
    """
    J = load_job_module()
    os.makedirs(out_dir, exist_ok=True)
    stem = out_name or (os.path.splitext(os.path.basename(rvt_path))[0] + ".edited")
    out_rvt = os.path.join(out_dir, stem + ".rvt")
    ops_path = _jsonsafe.write(os.path.join(out_dir, "ops.json"),
                               {"ops": spec.ops, "source": spec.source,
                                "understood": spec.understood}, indent=1)
    argv = ["edit", os.path.abspath(rvt_path), "--ops", ops_path, "-o", out_rvt]
    if not validate:
        argv.append("--no-validate")
    if strict_validate:
        argv.append("--strict-validate")
    log: Dict[str, Any] = {"path": None, "degradations": []}
    with (stage_stdout(out_dir, "edit.log", quiet=quiet,
                       on_open=lambda p: log.__setitem__("path", p),
                       on_degrade=log["degradations"].append),
          job_stderr_joins_stdout(quiet)):
        rc = int(J.main(argv))
    job_manifest, validation = {}, {}
    mp = out_rvt + ".manifest.json"
    if os.path.isfile(mp):
        with open(mp) as fh:
            job_manifest = json.load(fh)
    vp = out_rvt + ".validation.json"
    if os.path.isfile(vp):
        try:
            with open(vp) as fh:
                validation = json.load(fh)
        except Exception:
            validation = {}
    return {"rc": rc, "out_rvt": out_rvt if os.path.isfile(out_rvt) else None,
            "ops_json": ops_path, "job_manifest": job_manifest,
            "validation_json": vp if os.path.isfile(vp) else None,
            "job_manifest_json": mp if os.path.isfile(mp) else None,
            "log_path": log["path"], "degradations": log["degradations"]}
