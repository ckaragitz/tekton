#!/usr/bin/env python3
"""tekton_env.py -- the ONE shared bootstrap for every tekton skill script.

Purpose: a skill session must go from cold to working in ONE cheap call --
no filesystem archaeology, no task boards, no ``pip install`` on the hot
path.  Everything here is deterministic and resolved STRICTLY relative to
this file's own location:

  * :func:`plugin_root` -- walk UP from ``os.path.abspath(__file__)`` to the
    first directory containing ``.claude-plugin/``.  Never searches, globs,
    or lists the filesystem; wherever the plugin folder was copied or
    mounted (Cowork, a zip extract, a temp dir with spaces), the root is
    its own ancestor, full stop.
  * :func:`ensure_engine` -- make ``import rvt`` work by inserting the
    bundled ``<root>/lib/src`` into ``sys.path`` (and the vendored
    ``olefile`` under ``skills/_shared/_vendor`` if the real one is
    absent).  NO pip install, NO venv creation.  Also exports the env var
    the engine reads (``RVT_PLUGIN_ROOT``) and a matching ``PYTHONPATH``
    so child processes inherit the same world.  ``RVT_GENESIS_BASE`` is
    the USER's override and is never exported by the plugin (#92).
  * :func:`preflight` -- ONE call, < 2 s, returning the readiness dict
    {python, engine, genesis_base, family_donor, out_dir, ...} plus a
    single human-readable line.  This replaces the old multi-command
    setup ceremony.
  * :func:`run_script` -- run a sibling skill script (frontdoor.py,
    rvt_edit.py, ...) in THIS interpreter with the engine already on the
    path: ``python scripts/_bootstrap.py run frontdoor.py author ...``.
  * :func:`go` -- the ONE-CALL dispatch: inline preflight + the job + ONE
    combined JSON on stdout, so a skill session needs exactly ONE Bash
    call (every call is a full model round-trip on an AI surface):
    ``python scripts/_bootstrap.py go author --prompt "..." --out out/j1 --json``.
    ``go author ...`` routes to the front door; ``go <script>.py ...`` runs
    any sibling script the same way.  ``run`` stays for compatibility.

  ensure_engine also installs the BUILD-TIME SCHEMA CACHE
  (``rvt.schema_cache``, shipped at ``assets/schema_cache/``): the parsed
  per-release ``Formats/Latest`` class map is reconstructed from a
  sha256-keyed cache file instead of re-parsed by every process; a miss
  falls back to the real parser, byte-identity of the key makes a wrong
  hit impossible.
  * :func:`doctor` -- the OPTIONAL one-time environment check/setup
    (``/tekton-doctor``).  Anything heavy (installing the IFC extras)
    lives here, off the hot path, and only with an explicit ``--install``.

HARD RULE (non-negotiable): nothing in this module -- and nothing in any
tekton skill -- reads, probes, lists, or requests access to an Autodesk
installation directory (the Windows program / program-data Autodesk trees,
/Applications/Autodesk, any Autodesk family-template folder).  The
family-donor status below comes ONLY from a file bundled inside this
plugin (``assets/family/``) or a file the user explicitly supplied
(``$RVT_FAMILY_DONOR`` / a CLI argument).  tests/test_bootstrap.py
enforces this with a source scan.
"""
from __future__ import annotations

import hashlib
import json
import os
import runpy
import sys
import tempfile
import time

__all__ = [
    "plugin_root", "ensure_engine", "ensure_rvt", "preflight",
    "family_donor_status", "specimen_status", "run_script", "go", "doctor",
    "cli",
]

_HERE = os.path.dirname(os.path.abspath(__file__))

# resolution + reporting constants ------------------------------------------
MARKER_DIR = ".claude-plugin"                 # what makes a dir the plugin root
GENESIS_REL = os.path.join("assets", "genesis", "G_ABPD.rvt")
PIN_REL = os.path.join("lib", "src", "rvt", "frontdoor", "assets", "genesis_base.json")
FACTS_REL = os.path.join("lib", "src", "rvt", "famgen", "facts")
FAMILY_DONOR_DIR_REL = os.path.join("assets", "family")   # bundled constructed donors (.rfa/.rvt)
SPECIMEN_ENV = "RVT_SPECIMEN_ANCESTOR"        # user-supplied specimen ancestor (reported only)
FAMILY_DONOR_ENV = "RVT_FAMILY_DONOR"         # user-supplied family format donor (reported only)
LINE_PREFIX = "tekton:"                       # every readiness line starts with this
MIN_PY = (3, 9)


class TektonEnvError(RuntimeError):
    """The plugin root cannot be resolved from this file's own location."""


# ---------------------------------------------------------------------------
# root resolution -- strictly from our own path, never a search
# ---------------------------------------------------------------------------

def plugin_root(start: str | None = None) -> str:
    """The plugin root: the nearest ancestor of THIS FILE that contains a
    ``.claude-plugin/`` directory.  Raises :class:`TektonEnvError` (with the
    one path that was walked) instead of ever falling back to a search."""
    d = os.path.abspath(start or _HERE)
    walked = d
    while True:
        if os.path.isdir(os.path.join(d, MARKER_DIR)):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            raise TektonEnvError(
                f"no {MARKER_DIR}/ directory found on the path above {walked} -- "
                "the tekton plugin folder is incomplete (keep skills/ and "
                ".claude-plugin/ together when copying it)")
        d = parent


# ---------------------------------------------------------------------------
# engine on the path -- sys.path insertion only, NO pip
# ---------------------------------------------------------------------------

def _prepend_env_path(var: str, path: str) -> None:
    cur = os.environ.get(var, "")
    parts = cur.split(os.pathsep) if cur else []
    if path not in parts:
        os.environ[var] = os.pathsep.join([path] + parts) if parts else path


def _append_env_path(var: str, path: str) -> None:
    cur = os.environ.get(var, "")
    parts = cur.split(os.pathsep) if cur else []
    if path not in parts:
        os.environ[var] = os.pathsep.join(parts + [path]) if parts else path


def _is_bundled_default_base(path: str, root: str) -> bool:
    """True when ``path`` IS the plugin's pinned default genesis base: the
    bundled file itself, or a byte-identical copy (e.g. a previous install
    dir a stale shell export still points at) -- size first, sha256 only
    on a size match, so a large firm template costs one stat."""
    try:
        if os.path.samefile(path, os.path.join(root, GENESIS_REL)):
            return True
        with open(os.path.join(root, PIN_REL)) as fh:
            pin = json.load(fh)["default"]
        return (os.path.getsize(path) == int(pin["bytes"])
                and _sha256(path).lower() == str(pin["sha256"]).lower())
    except (OSError, KeyError, ValueError):
        return False                     # missing/unreadable: the engine reports it


def _drop_bundled_base_env(root: str) -> None:
    """``$RVT_GENESIS_BASE`` is the USER's override and the engine honours
    it ahead of the per-release bundled bases ``--target-version`` selects,
    so the plugin never exports it; an inherited value that is merely our
    own default base (what older bootstraps / the legacy ``--env`` lines
    exported) carries no user intent and is dropped, or it would pin every
    job to the default release (#92).  Any other value is left alone."""
    envp = os.environ.get("RVT_GENESIS_BASE")
    if envp and _is_bundled_default_base(envp, root):
        del os.environ["RVT_GENESIS_BASE"]


def ensure_engine(root: str | None = None) -> str:
    """Make ``import rvt`` (and its only third-party dep, olefile) work from
    the plugin's own bundled source.  Idempotent, < 10 ms after the first
    call.  Returns a short description of the engine source used.

    The BUNDLED engine wins over any pip-installed ``rvt`` so the plugin
    always runs the engine it ships (killing the per-session
    ``pip install -e ./lib`` ceremony and the stale-install failure mode).
    Env exports (``RVT_PLUGIN_ROOT``, ``PYTHONPATH``) use ``setdefault`` /
    prepend semantics; ``RVT_GENESIS_BASE`` is the user's and is never
    exported (see :func:`_drop_bundled_base_env`)."""
    r = plugin_root() if root is None else root
    lib_src = os.path.join(r, "lib", "src")
    bundled = os.path.isdir(os.path.join(lib_src, "rvt"))
    if bundled and lib_src not in sys.path:
        sys.path.insert(0, lib_src)
    # vendored olefile fallback (the engine's only third-party import)
    try:
        import olefile  # noqa: F401
    except ImportError:
        vendor = os.path.join(r, "skills", "_shared", "_vendor")
        if os.path.isdir(os.path.join(vendor, "olefile")) and vendor not in sys.path:
            sys.path.insert(0, vendor)
    # the env contract the engine reads (children inherit via PYTHONPATH)
    os.environ.setdefault("RVT_PLUGIN_ROOT", r)
    _drop_bundled_base_env(r)
    if bundled:
        _prepend_env_path("PYTHONPATH", lib_src)
        vendor = os.path.join(r, "skills", "_shared", "_vendor")
        if os.path.isdir(vendor):
            _prepend_env_path("PYTHONPATH", vendor)
    import rvt  # noqa: F401  -- raises ImportError with the real reason if broken
    _install_lazy_schema()
    _install_schema_cache()
    # IFC read fallback: when the real ifcopenshell is ABSENT, append the
    # bundled pure-python steplite shim package (rvt/ifc/_ifcos_shim) so
    # `import ifcopenshell` inside the read paths resolves to it -- try
    # ifcopenshell, else steplite, by ordinary import order (APPEND, so a
    # real install always wins; the shim additionally stands down by itself
    # if a real distribution appears ahead of it on a child's path).
    import importlib.util as _ilu
    if _ilu.find_spec("ifcopenshell") is None:
        shim = os.path.join(os.path.dirname(os.path.abspath(rvt.__file__)),
                            "ifc", "_ifcos_shim")
        if os.path.isdir(os.path.join(shim, "ifcopenshell")):
            if shim not in sys.path:
                sys.path.append(shim)
            _append_env_path("PYTHONPATH", shim)
    src = os.path.dirname(os.path.abspath(getattr(rvt, "__file__", "") or ""))
    if bundled and src.startswith(os.path.abspath(lib_src)):
        return f"bundled source: {lib_src}"
    return f"installed package: {src or '?'} (bundled source absent at {lib_src})"


def _install_lazy_schema() -> None:
    """Arm the lazy bundled-schema fallback (sibling module
    ``tekton_schema.py``): on a bare machine the first no-arg
    ``ObjectDecoder()``/``ObjectEncoder()`` resolves the schema from the
    bundled genesis base instead of dying on the research corpus path.
    ~16 ms to arm; the schema parse itself happens only if a job needs a
    decoder (never during preflight).  A missing sibling degrades to the
    old behaviour -- the wrapper is an enhancement, not a dependency."""
    try:
        if "tekton_schema" in sys.modules:
            mod = sys.modules["tekton_schema"]
        else:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "tekton_schema", os.path.join(_HERE, "tekton_schema.py"))
            if spec is None or spec.loader is None:
                return
            mod = importlib.util.module_from_spec(spec)
            sys.modules["tekton_schema"] = mod
            spec.loader.exec_module(mod)
        mod.install()
    except Exception:                                            # noqa: BLE001
        # never break the engine over the fallback; the original
        # FileNotFoundError (with the real path) still surfaces if needed
        pass


def _install_schema_cache() -> None:
    """Arm the BUILD-TIME schema cache (``rvt.schema_cache``): wraps
    ``rvt.schema.parse`` so a stream whose sha256 matches a bundled cache
    file (``assets/schema_cache/<sha>.tksc``) is reconstructed from the
    cache (~2-3x faster than parsing) instead of re-parsed by every
    process; any miss falls through to the real parser.  Composes with the
    lazy bundled-schema fallback above: that wrapper decides WHERE the
    schema bytes come from, this one makes turning bytes into a parsed
    schema cheap.  Optional by construction -- any failure leaves the
    original parser untouched."""
    try:
        from rvt import schema_cache as _sc
        _sc.install()
    except Exception:                                            # noqa: BLE001
        pass


def ensure_rvt(root: str | None = None) -> str:
    """Back-compat alias (the old per-skill ``_bootstrap.ensure_rvt``)."""
    return ensure_engine(root)


# ---------------------------------------------------------------------------
# donor / specimen status -- bundled path or user-supplied file ONLY
# ---------------------------------------------------------------------------

def _supplied_or_bundled(env_var: str, bundled_dir: str, exts: tuple[str, ...]) -> dict:
    """Status dict for an optional build input.  Sources are EXACTLY:
    (1) a user-supplied file named by ``env_var``; (2) a file bundled inside
    the plugin at ``bundled_dir``.  No other location is ever consulted."""
    envp = os.environ.get(env_var)
    if envp:
        if os.path.isfile(envp):
            return {"status": "user-supplied", "path": os.path.abspath(envp)}
        return {"status": "missing", "path": None,
                "note": f"${env_var} is set but the file does not exist: {envp}"}
    if os.path.isdir(bundled_dir):
        cands = sorted(f for f in os.listdir(bundled_dir)
                       if f.lower().endswith(exts) and
                       os.path.isfile(os.path.join(bundled_dir, f)))
        if cands:
            return {"status": "bundled", "path": os.path.join(bundled_dir, cands[0])}
    return {"status": "missing", "path": None}


def family_donor_status(root: str | None = None) -> dict:
    """The family-format-donor input for the family build stage (F/L).
    ``bundled`` (a constructed donor shipped in ``assets/family/``),
    ``user-supplied`` (``$RVT_FAMILY_DONOR``), or ``missing``.  When missing
    the skill asks the user for ONE thing -- their Revit version and one
    ``.rfa``/``.rvt`` of their own -- and NEVER goes looking for Autodesk
    content on the machine."""
    r = plugin_root() if root is None else root
    return _supplied_or_bundled(FAMILY_DONOR_ENV, os.path.join(r, FAMILY_DONOR_DIR_REL),
                                (".rfa", ".rvt"))


def specimen_status(root: str | None = None) -> dict:
    """The specimen-ancestor input for the walls/equipment build stages
    (``--specimens``).  Same three sources rule as the family donor."""
    r = plugin_root() if root is None else root
    return _supplied_or_bundled(SPECIMEN_ENV, os.path.join(r, "assets", "genesis"),
                                (".specimen.rvt",))


# ---------------------------------------------------------------------------
# preflight -- ONE call, one line, < 2 s
# ---------------------------------------------------------------------------

def _sha256(path: str, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _check_out_dir() -> dict:
    """A writable place for job outputs: the working directory first, the
    system temp dir as fallback.  Proven by actually creating a file."""
    for cand, label in ((os.getcwd(), "cwd"), (tempfile.gettempdir(), "tmp")):
        try:
            fd, p = tempfile.mkstemp(prefix=".tekton-preflight-", dir=cand)
            os.close(fd)
            os.unlink(p)
            return {"ok": True, "path": cand, "where": label}
        except OSError:
            continue
    return {"ok": False, "path": None, "where": None}


def preflight(root: str | None = None) -> dict:
    """The whole environment story in one call.  Returns the readiness dict;
    ``result['line']`` is the single line to print/report.  READY means the
    four hard inputs are good: python, engine, verified genesis base,
    writable output dir.  A missing family donor does NOT block readiness --
    it degrades the family build stage and the skill asks the user for one
    file instead."""
    t0 = time.time()
    res: dict = {"ok": False}

    # python
    pv = sys.version_info
    res["python"] = {"ok": pv >= MIN_PY, "version": f"{pv[0]}.{pv[1]}.{pv[2]}",
                     "executable": sys.executable}

    # plugin root
    try:
        r = plugin_root() if root is None else root
        res["plugin_root"] = {"ok": True, "path": r}
    except TektonEnvError as e:
        res["plugin_root"] = {"ok": False, "error": str(e)}
        res["seconds"] = round(time.time() - t0, 3)
        res["line"] = f"{LINE_PREFIX} NOT READY | plugin-root: {e}"
        return res

    # engine importable (bundled source; vendored olefile; no pip)
    try:
        src = ensure_engine(r)
        import rvt.container  # noqa: F401  -- the load-bearing module (pulls olefile)
        res["engine"] = {"ok": True, "source": src,
                         "facts_store": os.path.isdir(os.path.join(r, FACTS_REL))}
    except Exception as e:                                    # noqa: BLE001
        res["engine"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}

    # genesis base present + sha256-verified against the shipped pin
    base = os.path.join(r, GENESIS_REL)
    pin_path = os.path.join(r, PIN_REL)
    g: dict = {"ok": False, "path": base, "present": os.path.isfile(base),
               "sha256_verified": False, "revit_release": None}
    if g["present"]:
        try:
            with open(pin_path) as fh:
                pin = json.load(fh)
            want = str(pin["default"]["sha256"]).lower()
            g["revit_release"] = str(pin["default"].get("revit_release") or "") or None
            g["sha256_verified"] = _sha256(base).lower() == want
            g["ok"] = g["sha256_verified"]
            if not g["sha256_verified"]:
                g["error"] = "bundled genesis base sha256 does not match the pin -- the front door would refuse it"
        except (OSError, KeyError, ValueError) as e:
            g["error"] = f"pin unreadable ({e}); base present but unverified"
            g["ok"] = True                      # present; verification unavailable, said so
    else:
        g["error"] = f"bundled genesis base missing: {base}"
    res["genesis_base"] = g

    # optional build inputs (reported, never blocking, never probed elsewhere)
    res["family_donor"] = family_donor_status(r)
    res["specimen"] = specimen_status(r)

    # optional python extras (numpy: the author/front-door intent model;
    # ifcopenshell: the --ifc input route).  Reported so the skill can say
    # "run doctor --install once" instead of pip-installing on the hot path.
    import importlib.util as _ilu
    res["extras"] = {m: _ilu.find_spec(m) is not None
                     for m in ("numpy", "ifcopenshell")}

    # writable output dir
    res["out_dir"] = _check_out_dir()

    res["ok"] = all((res["python"]["ok"], res["engine"]["ok"],
                     res["genesis_base"]["ok"], res["out_dir"]["ok"]))
    res["seconds"] = round(time.time() - t0, 3)

    if res["ok"]:
        rel = g["revit_release"]
        gen = ("verified" if g["sha256_verified"] else "present (unverified)") + \
              (f" (Revit {rel})" if rel else "")
        eng = "bundled" if res["engine"]["source"].startswith("bundled") else "installed"
        outw = "OK" if res["out_dir"]["where"] == "cwd" else f"{res['out_dir']['path']} only"
        res["line"] = (f"{LINE_PREFIX} READY | python {res['python']['version']} | "
                       f"engine {eng} | genesis {gen} | "
                       f"family-donor {res['family_donor']['status']} | "
                       f"out-dir {outw} | {res['seconds']}s")
    else:
        bad = []
        for k in ("python", "engine", "genesis_base", "out_dir"):
            item = res[k]
            if not item.get("ok"):
                bad.append(f"{k.replace('_', '-')}: "
                           f"{item.get('error') or item.get('version') or 'failed'}")
        res["line"] = f"{LINE_PREFIX} NOT READY | " + " | ".join(bad)
    return res


# ---------------------------------------------------------------------------
# run a sibling skill script with the engine already on the path
# ---------------------------------------------------------------------------

def run_script(script: str, argv: list[str], base_dir: str | None = None) -> int:
    """Execute ``script`` (a skill script such as ``frontdoor.py``) in THIS
    interpreter with :func:`ensure_engine` already applied -- so the one
    skill command needs no pip, no eval, no env prefix.  ``script`` may be
    an absolute path, a path relative to the working directory, or a bare
    name resolved in ``base_dir`` (the calling skill's ``scripts/`` dir).
    ``sys.argv`` is set for the script; its ``SystemExit`` propagates."""
    ensure_engine()
    cand = script if script.endswith(".py") else script + ".py"
    path = None
    # the calling skill's own scripts dir WINS over the cwd (deterministic:
    # a stray same-named file in the user's working dir never shadows it)
    for c in ((cand,) if os.path.isabs(cand) else
              (os.path.join(base_dir, cand) if base_dir else None,
               os.path.abspath(cand))):
        if c and os.path.isfile(c):
            path = c
            break
    if path is None:
        sys.stderr.write(f"{LINE_PREFIX} run: script not found: {script}"
                         + (f" (looked beside {base_dir})" if base_dir else "") + "\n")
        return 2
    sys.argv = [path] + list(argv)
    runpy.run_path(path, run_name="__main__")
    return 0


# ---------------------------------------------------------------------------
# go -- ONE-CALL dispatch: preflight + job + ONE combined JSON
# ---------------------------------------------------------------------------

def _resolve_go_target(argv: list[str], base_dir: str | None) -> tuple[str, list[str]]:
    """``go <script>.py ARGS...`` runs that sibling script; anything else
    (``go author --prompt ...``) routes to the front door.  When the calling
    skill's own scripts dir has no ``frontdoor.py`` (e.g. tekton-edit), the
    canonical copy beside tekton-author is used -- resolved from the plugin
    root, never by searching."""
    if argv and argv[0].endswith(".py"):
        return argv[0], argv[1:]
    script = "frontdoor.py"
    if not (base_dir and os.path.isfile(os.path.join(base_dir, script))):
        cand = os.path.join(plugin_root(), "skills", "tekton-author",
                            "scripts", script)
        if os.path.isfile(cand):
            script = cand
    args = list(argv)
    if args and args[0] == "author" and "--json" not in args:
        args.append("--json")            # ONE machine-readable combined result
    return script, args


def go(argv: list[str], base_dir: str | None = None) -> int:
    """THE ONE-CALL SKILL FLOW: inline preflight, then the job, then ONE
    combined JSON object on stdout -- so a skill session spends exactly ONE
    Bash round-trip instead of preflight-call + job-call.

        _bootstrap.py go author --prompt "..." --out out/job1 --json
        _bootstrap.py go author --ifc design.ifc --out out/job2
        _bootstrap.py go rvt_edit.py set-level in.rvt --json

    stdout is exactly one JSON object: ``{"go": {ready, preflight_line,
    preflight_seconds, job_seconds, exit_code, ...}, "result": <the job's
    own --json result (or null; raw stdout tail rides in go.stdout when the
    job printed non-JSON)}``.  Exit code: the job's own exit code; 3 when
    preflight said NOT READY (the job is never attempted); 2 usage."""
    import io
    from contextlib import redirect_stdout

    t0 = time.time()
    if not argv:
        sys.stderr.write("usage: _bootstrap.py go (author ARGS... | SCRIPT.py ARGS...)\n")
        return 2
    pf = preflight()
    out: dict = {"go": {"one_call": True, "ready": bool(pf["ok"]),
                        "preflight_line": pf["line"],
                        "preflight_seconds": pf["seconds"]}}
    if not pf["ok"]:
        out["go"]["preflight"] = pf          # the full detail, only on failure
        out["result"] = None
        print(json.dumps(out, indent=1, default=str))
        return 3
    script, args = _resolve_go_target(argv, base_dir)
    buf = io.StringIO()
    code = 0
    t1 = time.time()
    try:
        with redirect_stdout(buf):
            code = run_script(script, args, base_dir=base_dir)
    except SystemExit as e:                  # the job's own exit code
        if isinstance(e.code, int) or e.code is None:
            code = e.code or 0
        else:                                # exit("message"): keep the message
            sys.stderr.write(str(e.code).rstrip("\n") + "\n")
            code = 1
    except BaseException as e:               # noqa: BLE001 -- still ONE json out
        out["go"]["exception"] = f"{type(e).__name__}: {e}"
        code = 1
    out["go"]["job_seconds"] = round(time.time() - t1, 3)
    out["go"]["seconds"] = round(time.time() - t0, 3)
    out["go"]["exit_code"] = code
    raw = buf.getvalue()
    res, extra = None, raw
    if raw.lstrip().startswith(("{", "[")):
        try:
            res = json.loads(raw)
            extra = ""
        except ValueError:
            res = None
    if res is None and raw:
        i = raw.rfind("\n{")                 # stray log lines, then the JSON
        if i != -1:
            try:
                res = json.loads(raw[i + 1:])
                extra = raw[:i]
            except ValueError:
                res = None
    out["result"] = res
    if extra.strip():
        out["go"]["stdout"] = extra[-8000:]  # non-JSON job output, tail
    print(json.dumps(out, indent=1, default=str))
    return code


# ---------------------------------------------------------------------------
# doctor -- the one-time, off-hot-path environment check/setup
# ---------------------------------------------------------------------------

def doctor(install: bool = False) -> int:
    """Everything preflight checks, verbosely, plus the OPTIONAL extras --
    and the only place any install may happen (explicit ``--install``,
    IFC-route extras only).  Never touches an Autodesk installation
    directory; the family donor question is answered by asking the USER for
    a file, never by looking for one."""
    pf = preflight()
    print(pf["line"])
    print()
    r = pf.get("plugin_root", {}).get("path")
    print(f"  plugin root   : {r or 'UNRESOLVED'}")
    print(f"  python        : {pf['python']['version']}  ({pf['python']['executable']})")
    eng = pf["engine"]
    print(f"  engine        : {'OK -- ' + eng['source'] if eng.get('ok') else 'FAIL -- ' + eng.get('error', '?')}")
    if eng.get("ok"):
        print(f"  facts store   : {'present' if eng.get('facts_store') else 'MISSING (family catalog will not resolve)'}")
    g = pf["genesis_base"]
    print(f"  genesis base  : {'sha256-verified' if g.get('sha256_verified') else ('present, unverified' if g.get('present') else 'MISSING')}"
          + (f"  (Revit {g['revit_release']})" if g.get("revit_release") else ""))
    fd_ = pf["family_donor"]
    if fd_["status"] == "user-supplied":
        print(f"  family container: user-supplied donor  ({fd_['path']})")
    else:
        print("  family container: bundled (genesis base)")
        if fd_.get("note"):
            print(f"                    NOTE: {fd_['note']}")
        print("                    .rfa ADocument is authored CONSTRUCTIVELY (schema-built")
        print("                    famdoc tree; empty registries -- desktop acceptance")
        print("                    tracked in issue #52).")
        print(f"                    (${FAMILY_DONOR_ENV} stays as an expert override, e.g. a")
        print("                     non-2026 target release. We never look for Autodesk")
        print("                     content on this machine.)")
    sp = pf["specimen"]
    print(f"  specimen      : {sp['status']}" + (f"  ({sp['path']})" if sp.get("path") else "")
          + ("" if sp["status"] != "missing"
             else "  (fine: wall/instance templates are constructed from the bundled base;"
                  " --specimens stays as an expert override)"))
    od = pf["out_dir"]
    print(f"  output dir    : {'writable -- ' + od['path'] if od.get('ok') else 'NO writable dir found'}")

    # optional extras -- presence report; install only on explicit request.
    # The IFC READ routes (--ifc intent, product facts) no longer need any
    # install: with ifcopenshell absent, ensure_engine serves them through
    # the bundled pure-python steplite fallback (rvt/ifc/_ifcos_shim).  The
    # real ifcopenshell stays installable for the AUTHORING / validation
    # surfaces (ifcopenshell.api / .geom / .validate) the shim does not carry.
    extras = {"numpy": "lazy: only the validation gate's ECC math and IFC "
                       "geometry resolution exercise it -- the prompt "
                       "route runs without it",
              "ifcopenshell": "IFC authoring/validation only -- reads run on "
                              "the bundled steplite fallback"}
    missing = []
    for mod, why in extras.items():
        try:
            m = __import__(mod)
            if getattr(m, "IS_STEPLITE", False):
                missing.append(mod)      # the real library remains installable
                print(f"  extra {mod:<12}: steplite fallback active (pure-python "
                      f"read path, zero install; real library optional -- {why})")
            else:
                print(f"  extra {mod:<12}: present")
        except ImportError:
            missing.append(mod)
            print(f"  extra {mod:<12}: absent ({why})")
    if missing and install:
        import subprocess
        print(f"\n  installing extras (one-time, requested): {' '.join(missing)}")
        rc = subprocess.call([sys.executable, "-m", "pip", "install", *missing])
        print(f"  pip exit: {rc}")
    elif missing:
        need_read = [m for m in missing if m == "numpy"]
        if need_read:
            print(f"\n  the --ifc intent route needs numpy: python -m pip install numpy")
        if "ifcopenshell" in missing:
            print("  IFC reads already work (steplite); install ifcopenshell only "
                  "for authoring/validation: python -m pip install ifcopenshell")
        print("  (or re-run doctor with --install)")
    print()
    print(pf["line"])
    return 0 if pf["ok"] else 3


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _legacy_env_lines(r: str) -> str:
    """The old ``--env`` export lines, kept so existing docs keep working.
    ``RVT_GENESIS_BASE`` is deliberately NOT among them any more: the
    engine finds every bundled base from ``RVT_PLUGIN_ROOT``, and exporting
    the default one would override ``--target-version`` (#92)."""
    lib_src = os.path.join(r, "lib", "src")
    vendor = os.path.join(r, "skills", "_shared", "_vendor")
    path = lib_src + (os.pathsep + vendor if os.path.isdir(vendor) else "")
    return "\n".join([f'export PYTHONPATH="{path}${{PYTHONPATH:+:$PYTHONPATH}}"',
                      f'export RVT_PLUGIN_ROOT="{r}"'])


def cli(argv: list[str] | None = None, base_dir: str | None = None) -> int:
    """Entry point shared by ``tekton_env.py`` itself and every skill's
    ``scripts/_bootstrap.py`` shim.

        (no args) | preflight   -> print the ONE readiness line (exit 0 / 3)
        --json                  -> print the full preflight dict as JSON
        --env                   -> legacy export lines (compat; not needed by `run`)
        doctor [--install]      -> the one-time environment check/setup
        go ARGS...              -> ONE call: preflight + job + ONE combined JSON
                                   (`go author --prompt ... --out d` routes to the
                                   front door; `go SCRIPT.py ...` runs any sibling)
        run SCRIPT [ARGS...]    -> run a sibling skill script, engine ready
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "go":
        return go(argv[1:], base_dir=base_dir)
    if argv and argv[0] == "run":
        if len(argv) < 2:
            sys.stderr.write("usage: _bootstrap.py run SCRIPT [ARGS...]\n")
            return 2
        return run_script(argv[1], argv[2:], base_dir=base_dir)
    if argv and argv[0] == "doctor":
        return doctor(install="--install" in argv[1:])
    if "--env" in argv:
        try:
            print(_legacy_env_lines(plugin_root()))
            return 0
        except TektonEnvError as e:
            sys.stderr.write(f"{LINE_PREFIX} {e}\n")
            return 3
    pf = preflight()
    if "--json" in argv:
        print(json.dumps(pf, indent=1, default=str))
    else:
        print(pf["line"])
    return 0 if pf["ok"] else 3


if __name__ == "__main__":
    raise SystemExit(cli(base_dir=os.getcwd()))
