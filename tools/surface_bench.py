#!/usr/bin/env python3
"""surface_bench.py -- the SIMULATED SURFACE HARNESS for the tekton plugin.

Every tekton skill runs on a sandboxed AI surface, and on those surfaces the
unit of cost is not CPU seconds -- it is the SHELL INVOCATION (each one is a
full model round-trip) and the COLD START (a fresh VM/container that has
never seen the plugin).  This harness constructs three bare environments
approximating the real surfaces and runs the canonical skill jobs in each,
counting BOTH costs:

  cowork      a Cowork VM session: the plugin unzipped once at an unusual
              mount-like path (spaces + parens), a bare non-venv python,
              cleared env, dead HTTP proxies (the no-network default), one
              persistent filesystem for the whole session (so caches warm
              WITHIN the session, exactly like the VM).
  codeexec    a Messages-API code_execution container modelled STRICTLY
              stateless per call: before EVERY shell invocation the plugin
              is re-extracted fresh, the workdir/tmpdir are new, bytecode
              caching is off, and any input artifact from an earlier step is
              re-staged (the "re-upload").  Every invocation pays the full
              cold start; the per-invocation extract cost is reported
              separately so the "unpack once per conversation" saving is
              visible.
  local       a local Claude Code session: the repo present, the repo's own
              interpreter, everything warm.

Canonical jobs (the documented one-command skill flows, in session order):
  preflight        skills/tekton-author/scripts/_bootstrap.py --json
  author-prompt    _bootstrap.py run frontdoor.py author --prompt <panel> --json
  go-author-prompt _bootstrap.py go author --prompt <panel> --json (ONE call:
                   inline readiness + the job + one combined JSON)
  go-author-6panels
                   the same ONE call with the flagship ROOM6_PROMPT (six
                   generated families loaded + placed; the #184 ceiling)
  author-ifc       _bootstrap.py run frontdoor.py author --ifc electrical-room-2500a.ifc --json
  go-author-ifc    _bootstrap.py go author --ifc electrical-room-2500a.ifc --target-version 2025 --json
                   (ONE call -- the IFC flow the SKILL documents; on a
                   numpy-less interpreter the envelope states the route's
                   prerequisite up front -> BLOCKED (needs numpy))
  edit-roundtrip   rvt_edit.py info -> set-level -> rvt_validate.py (3 calls,
                   the pre-#111 tekton-edit flow incl. the mandatory gate; kept
                   as the fallback path and the before-number)
  go-edit          _bootstrap.py go edit <bundled 2025 base> set-level ... (ONE
                   call: readiness + edit + self-check + the mandatory gate)
  validate         skills/tekton-inspect: rvt_validate.py <authored .rvt>
  ifc-harden       skills/tekton-ifc (the Claude Design / Cowork sandbox skill:
                   plain CLIs, its own session): validate_ifc.py -> harden_ifc.py
                   -> validate_ifc.py -> report.py on the sample IFC, 4 calls;
                   BLOCKED without ifcopenshell + numpy (issue #113)
  go-ifc-harden    the same flow as ONE call of scripts/ifc_flow.py --json (one
                   process, one import, 2 analyses instead of 4; issue #754) --
                   the before/after pair for the tekton-ifc session

Run from the repo root with the repo interpreter:

    .venv/bin/python tools/surface_bench.py                # all three surfaces
    .venv/bin/python tools/surface_bench.py --surfaces local --jobs preflight,author-prompt
    .venv/bin/python tools/surface_bench.py --json bench.json --md bench.md --keep

The default plugin source is the SHIPPED artifact tekton-plugin.zip (what a
surface actually receives); --from-tree copies plugin/ instead (dev mode).
Nothing here talks to the network; the bare surfaces get dead proxies +
PIP_NO_INDEX so any accidental network/pip attempt fails RED and fast.
tests/test_surface_perf.py reuses this module as a CI regression gate.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_ZIP = os.path.join(ROOT, "tekton-plugin.zip")
PLUGIN_TREE = os.path.join(ROOT, "plugin")

PANEL_PROMPT = "create an eaton panel for me with 6 switches"
#: the flagship demo prompt: SIX generated families loaded + placed (issue #124)
ROOM6_PROMPT = "an electrical room with 6 panels"
ROOM6_FAMILIES = 6
IFC_EXAMPLE_REL = os.path.join("skills", "tekton-author", "examples",
                               "electrical-room-2500a.ifc")
#: `go author --ifc` names the recipient's release, as the SKILL tells a
#: session to (target version is a first-class input); 2025 = a certified base
GO_IFC_TARGET_VERSION = "2025"
#: `go edit` input: the bundled, certified Revit 2025 base (always in the
#: plugin, so the job needs no earlier step) and a Level present in all three
#: bundled bases ("GEN B1 - Basement", tests/test_edit_own_release.py)
GO_EDIT_BASE_REL = os.path.join("assets", "genesis", "G_ABPD_2025.rvt")
GO_EDIT_LEVEL_ID = 1351691

#: the tekton-ifc skill's engine: plain CLIs run as `python scripts/<tool>.py`
#: (no `rvt`, no `_bootstrap.py`; issue #113), what they import (the module
#: names of scripts/requirements.txt, in its order) and the skill's own fix
IFC_SKILL_SCRIPTS_REL = os.path.join("skills", "tekton-ifc", "scripts")
IFC_SKILL_NEEDS = ("ifcopenshell", "numpy")
IFC_SKILL_FIX = "pip install -r scripts/requirements.txt"

JOB_ORDER = ("preflight", "author-prompt", "go-author-prompt", "go-author-6panels",
             "author-ifc", "go-author-ifc", "edit-roundtrip", "go-edit", "validate",
             "ifc-harden", "go-ifc-harden")
SURFACE_ORDER = ("cowork", "codeexec", "local")

# what each surface is, one line, for the table header
SURFACE_BLURB = {
    "cowork":   "Cowork VM: bare python, unusual mount path, no network, session-persistent",
    "codeexec": "code_execution: stateless per call -- fresh extract + fresh tmp EVERY invocation",
    "local":    "local Claude Code: repo present, repo interpreter, warm",
}


# ---------------------------------------------------------------------------
# plugin source -> a fresh environment directory
# ---------------------------------------------------------------------------

def _extract_zip(zip_path: str, dst: str) -> float:
    """Extract the shipped plugin zip into dst/. Returns seconds spent."""
    t0 = time.time()
    os.makedirs(dst, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dst)
    return time.time() - t0


def _copy_tree(src: str, dst: str) -> float:
    """Copy the plugin/ working tree (dev fallback when no zip is built)."""
    t0 = time.time()
    ign = shutil.ignore_patterns("__pycache__", "node_modules", ".pytest_cache",
                                 ".DS_Store")
    shutil.copytree(src, dst, ignore=ign)
    return time.time() - t0


def stage_plugin(source: str, dst: str) -> float:
    """Materialise a bare plugin at dst (zip extract or tree copy)."""
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    if source.lower().endswith(".zip"):
        return _extract_zip(source, dst)
    return _copy_tree(source, dst)


# ---------------------------------------------------------------------------
# per-surface process environment
# ---------------------------------------------------------------------------

_CLEARED = ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "VIRTUAL_ENV",
            "RVT_PLUGIN_ROOT", "RVT_GENESIS_BASE", "RVT_FAMILY_DONOR",
            "RVT_SPECIMEN_ANCESTOR", "TEKTON_ROOT", "PIP_INDEX_URL")


def bare_env(tmpdir: str, no_network: bool = True) -> dict:
    """A cleaned environment for the bare surfaces: no venv, no RVT_* state,
    a surface-private TMPDIR (so warm caches never leak across surfaces),
    and -- by default -- dead proxies so any network attempt fails fast."""
    env = {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "HOME": os.environ.get("HOME", tmpdir),   # sandbox pythons ship numpy;
                                                  # on this host it resolves via
                                                  # the user site, so HOME stays
        "LANG": os.environ.get("LANG", "en_US.UTF-8"),
        "TMPDIR": tmpdir,
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
    }
    if no_network:
        dead = "http://127.0.0.1:9"        # discard port: connection refused fast
        env.update({"http_proxy": dead, "https_proxy": dead,
                    "HTTP_PROXY": dead, "HTTPS_PROXY": dead,
                    "no_proxy": "", "PIP_NO_INDEX": "1",
                    "PIP_RETRIES": "0", "PIP_TIMEOUT": "1"})
    return env


def local_env(tmpdir: str) -> dict:
    """The local surface: the developer's own env minus stale RVT_* state."""
    env = dict(os.environ)
    for k in _CLEARED:
        env.pop(k, None)
    env["TMPDIR"] = tmpdir
    return env


# ---------------------------------------------------------------------------
# invocation + job records
# ---------------------------------------------------------------------------

class Invocation:
    """One shell invocation = one model round-trip on a real surface."""

    def __init__(self, label: str, argv: list, seconds: float, exit_code: int,
                 stdout: str, stderr: str, extract_seconds: float = 0.0):
        self.label = label
        self.argv = argv
        self.seconds = seconds
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.extract_seconds = extract_seconds   # codeexec: the per-call re-extract

    def as_dict(self) -> dict:
        return {"label": self.label, "argv": self.argv,
                "seconds": round(self.seconds, 3), "exit": self.exit_code,
                "extract_seconds": round(self.extract_seconds, 3),
                "stderr_tail": self.stderr[-600:] if self.exit_code else ""}


class JobResult:
    def __init__(self, name: str):
        self.name = name
        self.status = "PASS"
        self.reason = ""
        self.invocations: list[Invocation] = []
        # where an author job's time goes INSIDE the process (issue #124):
        # {"job_seconds", "build_seconds", "stages": [{"stage", "seconds", ...}]}
        self.breakdown: dict = {}
        # BLOCKED by a prerequisite the surface stated up front (#127/#553):
        # {"route", "needs", "fix"} -- copied through to the JSON row
        self.prerequisite: dict = {}

    @property
    def seconds(self) -> float:
        return sum(i.seconds for i in self.invocations)

    @property
    def extract_seconds(self) -> float:
        return sum(i.extract_seconds for i in self.invocations)

    @property
    def calls(self) -> int:
        return len(self.invocations)

    def fail(self, reason: str) -> "JobResult":
        self.status, self.reason = "FAIL", reason
        return self

    def blocked(self, reason: str, prerequisite: dict | None = None) -> "JobResult":
        self.status, self.reason = "BLOCKED", reason
        self.prerequisite = prerequisite or {}
        return self

    def skipped(self, reason: str) -> "JobResult":
        self.status, self.reason = "SKIPPED", reason
        return self

    def as_dict(self) -> dict:
        d = {"job": self.name, "status": self.status, "reason": self.reason,
             "shell_calls": self.calls, "seconds": round(self.seconds, 3),
             "extract_seconds": round(self.extract_seconds, 3),
             "invocations": [i.as_dict() for i in self.invocations]}
        if self.breakdown:
            d["breakdown"] = self.breakdown
        if self.prerequisite:
            d["prerequisite"] = self.prerequisite
        return d


# ---------------------------------------------------------------------------
# the surface: how a shell invocation happens there
# ---------------------------------------------------------------------------

class Surface:
    """One simulated surface.  ``run()`` executes a single shell invocation
    under the surface's rules (per-call reset for codeexec) and returns the
    Invocation record."""

    def __init__(self, name: str, source: str, bench_root: str, python: str,
                 stateless: bool, no_network: bool, timeout: float):
        self.name = name
        self.source = source
        self.root = os.path.join(bench_root, name)
        self.python = python
        self.stateless = stateless
        self.no_network = no_network
        self.timeout = timeout
        self.call_no = 0
        self.plugin_dir = ""
        self.workdir = ""
        self.tmpdir = ""
        self.artifacts = os.path.join(self.root, "artifacts")
        self.setup_seconds = 0.0
        os.makedirs(self.artifacts, exist_ok=True)
        if not stateless:
            self._stage_session()

    # -- environment staging -------------------------------------------------
    def _stage_session(self) -> None:
        if self.name == "local":
            self.plugin_dir = PLUGIN_TREE           # the repo, warm
            self.setup_seconds = 0.0
        else:
            # the mount-like path a sandbox upload really gets (spaces + parens)
            self.plugin_dir = os.path.join(
                self.root, "mnt volume 1 (user files)", "skill uploads", "tekton plugin")
            self.setup_seconds = stage_plugin(self.source, self.plugin_dir)
        self.workdir = os.path.join(self.root, "work")
        self.tmpdir = os.path.join(self.root, "tmp")
        os.makedirs(self.workdir, exist_ok=True)
        os.makedirs(self.tmpdir, exist_ok=True)

    def _stage_call(self) -> float:
        """codeexec: EVERY invocation gets a fresh container."""
        call_dir = os.path.join(self.root, f"call{self.call_no:02d}")
        self.plugin_dir = os.path.join(call_dir, "plugin")
        secs = stage_plugin(self.source, self.plugin_dir)
        self.workdir = os.path.join(call_dir, "work")
        self.tmpdir = os.path.join(call_dir, "tmp")
        os.makedirs(self.workdir, exist_ok=True)
        os.makedirs(self.tmpdir, exist_ok=True)
        return secs

    # -- path helpers --------------------------------------------------------
    def bootstrap(self, skill: str) -> str:
        return os.path.join(self.plugin_dir, "skills", skill, "scripts", "_bootstrap.py")

    def env(self) -> dict:
        if self.name == "local":
            return local_env(self.tmpdir)
        env = bare_env(self.tmpdir, no_network=self.no_network)
        if self.stateless:
            env["PYTHONDONTWRITEBYTECODE"] = "1"   # no .pyc survives the call anyway
        return env

    def stage_input(self, path: str) -> str:
        """Bring an artifact from an earlier step into THIS call's world (the
        stateless 're-upload'); on persistent surfaces the path already
        exists and is used in place."""
        if not self.stateless:
            return path
        dst = os.path.join(self.workdir, os.path.basename(path))
        shutil.copy2(path, dst)
        return dst

    def keep_artifact(self, path: str, name: str) -> str:
        """Preserve a job output beyond the per-call wipe."""
        dst = os.path.join(self.artifacts, name)
        if os.path.abspath(path) != os.path.abspath(dst):
            shutil.copy2(path, dst)
        return dst

    # -- the one primitive ---------------------------------------------------
    def run(self, label: str, argv_builder) -> Invocation:
        """One shell invocation.  ``argv_builder(surface)`` is called AFTER
        the per-call reset so it sees the fresh plugin/work dirs."""
        self.call_no += 1
        extract = self._stage_call() if self.stateless else 0.0
        argv = [self.python] + argv_builder(self)
        t0 = time.time()
        try:
            p = subprocess.run(argv, cwd=self.workdir, env=self.env(),
                               capture_output=True, text=True, timeout=self.timeout)
            secs, code, out, err = time.time() - t0, p.returncode, p.stdout, p.stderr
        except subprocess.TimeoutExpired as e:
            secs, code = time.time() - t0, -9
            out = (e.stdout or b"").decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
            err = f"TIMEOUT after {self.timeout}s"
        return Invocation(label, argv, secs, code, out, err, extract_seconds=extract)


# ---------------------------------------------------------------------------
# the canonical jobs
# ---------------------------------------------------------------------------

def _json_or_none(text: str):
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None


_JSON_PUNCT = frozenset("{}[],")


def _d(v) -> dict:
    """``v`` when it is a dict, else ``{}`` -- for walking parsed job JSON."""
    return v if isinstance(v, dict) else {}


def _read_json(path):
    """The JSON at ``path`` as a dict (``{}`` for a non-object), or ``None``
    when there is no readable JSON there (missing/unreadable/invalid, or no
    path at all)."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return _d(json.load(fh))
    except (OSError, ValueError, TypeError):
        return None


def _why(inv: Invocation) -> str:
    """Why a job did not pass, in <= 200 chars, for its `reason` (issue #287).

    Prefers the job's OWN verdict when it printed a well-formed --json result
    (front door: ``errors[0]`` / ``status``; `go` envelope: ``result.error`` /
    ``result.gates.line``, or the preflight line when the job never ran),
    then the last stderr line the tool wrote as its own message (``error: ...``,
    the uniform CLI convention here -- a library finaliser may still print a
    traceback after it), then the last non-empty stderr line, then the last
    stdout line that is not bare JSON punctuation (a clean failure
    pretty-prints its JSON, so the literal last line is ``}``), then ``exit N``."""
    res = _json_or_none(inv.stdout)
    if isinstance(res, dict):
        go, inner = _d(res.get("go")), _d(res.get("result")) or res
        errs = inner.get("errors")
        for cand in (errs[0] if isinstance(errs, list) and errs else None,
                     inner.get("error"), inner.get("status"), _d(inner.get("gates")).get("line"),
                     go.get("exception"), inner.get("line"),
                     None if go.get("ready", True) else go.get("preflight_line")):
            if isinstance(cand, str) and cand.strip():
                return " ".join(cand.split())[:200]
    own = [line.strip() for line in (inv.stderr or "").splitlines() if line.strip().startswith("error:")]
    if own:
        return own[-1][:200]
    for text, is_stdout in ((inv.stderr, False), (inv.stdout, True)):
        for line in reversed((text or "").splitlines()):
            line = line.strip()
            if line and not (is_stdout and set(line) <= _JSON_PUNCT):
                return line[:200]
    return f"exit {inv.exit_code}"


def _prerequisite(res) -> dict | None:
    """The `go` envelope's own ``go.prerequisite`` ({route, needs, fix}) when
    the surface stated -- up front, ``go.ready:false``, ``result:null``,
    exit 3, no job attempted (#127) -- that the requested route needs an
    extra this interpreter lacks; None for every other output.  Such a row
    is BLOCKED (an honest surface truth), never FAIL (#553)."""
    go = _d(_d(res).get("go"))
    prereq = _d(go.get("prerequisite"))
    return prereq if not go.get("ready", True) and prereq.get("needs") else None


def _needs_words(prereq: dict) -> str:
    """``needs numpy (python -m pip install numpy)`` (or ``needs numpy`` when
    no ``fix`` is given) -- the bootstrap's own wording of a route capability
    / prerequisite (tekton_env._route_words); the ONE phrasing here too."""
    words = "needs " + " + ".join(str(n) for n in prereq.get("needs") or ["?"])
    return f"{words} ({prereq['fix']})" if prereq.get("fix") else words


def stage_breakdown(result: dict, envelope: dict | None = None) -> dict:
    """Where an author job's time went INSIDE the process: the manifest's
    ``build.stages[*].seconds`` (F families / L load / specimens / W walls /
    E equipment / C circuits / V gates -- issue #124) + ``build.seconds`` +
    the `go` envelope's ``job_seconds`` when there is one.  ``result`` is the
    front door's JSON result (its ``manifest.json`` path is read from disk)."""
    bd: dict = {}
    if envelope and isinstance(envelope.get("go"), dict):
        bd["job_seconds"] = envelope["go"].get("job_seconds")
        bd["preflight_seconds"] = envelope["go"].get("preflight_seconds")
    man = result.get("manifest")
    manifest = _read_json(man.get("json") if isinstance(man, dict) else man)
    if manifest is None:
        return bd
    build = _d(manifest.get("build"))
    bd["build_seconds"] = build.get("seconds")
    stages = []
    for st in build.get("stages") or []:
        row = {"stage": st.get("stage"), "seconds": st.get("seconds")}
        for k in ("mode", "host_passes", "n_loaded", "n_planned", "gates"):
            if st.get(k) is not None:
                row[k] = st[k]
        stages.append(row)
    bd["stages"] = stages
    return bd


def load_stage(bd: dict) -> dict:
    """The manifest's family-load (L) stage row of a breakdown, or {}."""
    return next((st for st in bd.get("stages") or [] if st.get("stage") == "L"), {})


def _degraded_load(bd: dict) -> str:
    """A non-empty reason when the job loaded fewer families than it planned.
    The front door still delivers such a build (rule 1) and reports ok, but a
    job that got fast by loading 2/6 families is not a bench PASS -- it would
    read as a latency win in the headline table."""
    load = load_stage(bd)
    planned, loaded = load.get("n_planned"), load.get("n_loaded")
    if planned and loaded is not None and loaded < planned:
        return f"degraded load: {loaded}/{planned} families (delivered, but not the job that was asked for)"
    return ""


def _fmt_breakdown(bd: dict) -> str:
    """'F 4.1s · L 1.5s (1 pass, 6/6) · W 0.3s · E 0.2s · V 1.6s' for the table notes."""
    parts = []
    for st in bd.get("stages") or []:
        if st.get("seconds") is None or st.get("stage") in ("release-context",):
            continue
        s = f"{st['stage']} {st['seconds']:.1f}s"
        if st.get("stage") == "L" and st.get("host_passes") is not None:
            s += f" ({st['host_passes']} pass{'es' if st['host_passes'] != 1 else ''}, " \
                 f"{st.get('n_loaded')}/{st.get('n_planned')})"
        parts.append(s)
    inner = " · ".join(parts) if parts else "no stage timings in the manifest"
    if bd.get("job_seconds") is not None:
        inner = f"job {bd['job_seconds']:.1f}s = " + inner
    if bd.get("summary"):                    # what the job did, in its own words (ifc-harden)
        inner += "; " + bd["summary"]
    return inner


def _probe_preflight(s: Surface, state: dict, label: str) -> Invocation:
    """ONE `_bootstrap.py --json` call.  Records the surface's own summary in
    ``state["preflight"]`` -- python, extras, the per-route capability table
    stated up front (#127; ``{}`` on plugin builds that predate it) -- when it
    is READY, ``{}`` when it is not: either way the surface has been asked."""
    inv = s.run(label, lambda s: [s.bootstrap("tekton-author"), "--json"])
    pf = _json_or_none(inv.stdout)
    if inv.exit_code != 0 or not isinstance(pf, dict) or not pf.get("ok"):
        state["preflight"] = {}
        return inv
    state["preflight"] = {"python": pf["python"]["version"],
                          "extras": pf.get("extras", {}),
                          "routes": pf.get("routes", {}),
                          "internal_seconds": pf.get("seconds")}
    return inv


def job_preflight(s: Surface, state: dict) -> JobResult:
    job = JobResult("preflight")
    inv = _probe_preflight(s, state, "preflight --json")
    job.invocations.append(inv)
    return job if state["preflight"] else job.fail(f"preflight not READY: {_why(inv)}")


def job_author_prompt(s: Surface, state: dict) -> JobResult:
    job = JobResult("author-prompt")
    out_tag = f"out-prompt-{s.call_no + 1}"
    inv = s.run("author --prompt (panel)", lambda s: [
        s.bootstrap("tekton-author"), "run", "frontdoor.py", "author",
        "--prompt", PANEL_PROMPT, "--json", "--out", os.path.join(s.workdir, out_tag)])
    job.invocations.append(inv)
    res = _json_or_none(inv.stdout)
    if inv.exit_code != 0 or not res or not res.get("ok"):
        return job.fail(f"author --prompt failed: {_why(inv)}")
    combined = (res.get("files") or {}).get("combined")
    if not combined or not os.path.isfile(combined):
        return job.fail("no combined .rvt in the result")
    job.breakdown = stage_breakdown(res)
    state["authored_rvt"] = s.keep_artifact(combined, "prompt_room.rvt")
    degraded = _degraded_load(job.breakdown)
    return job.fail(degraded) if degraded else job


def job_go_author_prompt(s: Surface, state: dict) -> JobResult:
    """The ONE-CALL flow (`_bootstrap.py go author ...`): inline preflight +
    the job + one combined JSON -- a whole session in a single shell call.
    SKIPPED (not failed) on plugin builds that predate the `go` dispatch."""
    return _job_go_author(s, state, "go-author-prompt", "--prompt (panel)",
                          lambda s: ["--prompt", PANEL_PROMPT])


def job_go_author_6panels(s: Surface, state: dict) -> JobResult:
    """The flagship demo prompt through the one-call flow: six generated
    families loaded (ONE host pass since #124) + walls + six placed
    instances.  The job whose per-stage breakdown the latency epic tracks."""
    return _job_go_author(s, state, "go-author-6panels", "--prompt (6 panels)",
                          lambda s: ["--prompt", ROOM6_PROMPT])


def job_go_author_ifc(s: Surface, state: dict) -> JobResult:
    """The IFC flow the SKILL documents: ONE `go author --ifc FILE
    --target-version N` call.  With numpy the job builds (PASS); on a
    numpy-less interpreter the envelope states the route's prerequisite up
    front (`go.prerequisite`, #550) and no job is attempted -> BLOCKED (needs
    numpy), classified from the envelope itself, whatever ran before it."""
    return _job_go_author(s, state, "go-author-ifc", "--ifc (electrical room)",
                          lambda s: ["--ifc", os.path.join(s.plugin_dir, IFC_EXAMPLE_REL),
                                     "--target-version", GO_IFC_TARGET_VERSION])


def _job_go_author(s: Surface, state: dict, name: str, short: str, route_args) -> JobResult:
    """One `go author` job.  ``route_args(surface)`` -> the input part of the
    argv (``--prompt P`` / ``--ifc FILE --target-version N``), built after the
    per-call reset so it sees this call's plugin dir."""
    job = JobResult(name)
    out_tag = f"out-go-{s.call_no + 1}"
    inv = s.run(f"go author {short}", lambda s: [
        s.bootstrap("tekton-author"), "go", "author", *route_args(s),
        "--json", "--out", os.path.join(s.workdir, out_tag)])
    job.invocations.append(inv)
    res = _json_or_none(inv.stdout)
    if res is None and ((inv.stdout or "").lstrip().startswith("tekton:")
                        or inv.exit_code == 2
                        or "go" in (inv.stderr or "")):
        # pre-`go` builds treat unknown argv as plain preflight (readiness
        # line, exit 0/3) or usage-error -- an absent feature, not a failure
        return job.skipped("`go` dispatch not in this plugin build yet")
    prereq = _prerequisite(res)
    if prereq:                               # stated up front, no job attempted (#553)
        return job.blocked(_why(inv), prerequisite=prereq)   # = go.preflight_line
    if inv.exit_code != 0 or not res:
        return job.fail(f"go author failed: {_why(inv)}")
    # the combined JSON: accept either the front door result directly or a
    # {preflight, result} envelope -- the contract is ONE call, ONE JSON.
    inner = res.get("result", res)
    if not inner.get("ok"):
        return job.fail(f"go author reported not-ok: {_why(inv)}")
    job.breakdown = stage_breakdown(inner, envelope=res)
    combined = (inner.get("files") or {}).get("combined")
    if combined and os.path.isfile(combined) and "authored_rvt" not in state:
        state["authored_rvt"] = s.keep_artifact(combined, os.path.basename(combined))
    degraded = _degraded_load(job.breakdown)
    return job.fail(degraded) if degraded else job


def job_author_ifc(s: Surface, state: dict) -> JobResult:
    job = JobResult("author-ifc")
    out_tag = f"out-ifc-{s.call_no + 1}"
    inv = s.run("author --ifc (electrical room)", lambda s: [
        s.bootstrap("tekton-author"), "run", "frontdoor.py", "author",
        "--ifc", os.path.join(s.plugin_dir, IFC_EXAMPLE_REL),
        "--json", "--out", os.path.join(s.workdir, out_tag)])
    job.invocations.append(inv)
    res = _json_or_none(inv.stdout)
    if inv.exit_code == 0 and res and res.get("ok"):
        return job
    if "preflight" not in state:
        # run without the preflight job (`--jobs author-ifc`): ask the surface
        # for its route table now -- one cheap call, counted on this row -- so
        # the classification below never depends on job order (#562)
        job.invocations.append(_probe_preflight(s, state, "preflight --json (route table)"))
    # preflight already stated this route cannot build here (routes.ifc,
    # #127): an honest surface truth, not a regression (#553).  Absent table
    # (pre-#127 plugin build) -> classified as before.
    cap = state["preflight"].get("routes", {}).get("ifc")
    if isinstance(cap, dict) and not cap.get("ok", True):
        prereq = {"route": "ifc", "needs": cap.get("needs") or [], "fix": cap.get("fix")}
        return job.blocked(f"ifc route prerequisite stated by preflight: {_needs_words(prereq)}",
                           prerequisite=prereq)
    blob = (inv.stdout or "") + (inv.stderr or "")
    if "ifcopenshell" in blob:
        return job.blocked("ifcopenshell not importable on this surface "
                           "(fresh-sandbox install is minutes / impossible without egress)")
    return job.fail(f"author --ifc failed: {_why(inv)}")


def job_edit_roundtrip(s: Surface, state: dict) -> JobResult:
    """The tekton-edit SKILL flow: info -> ONE edit -> the mandatory gate."""
    job = JobResult("edit-roundtrip")
    rvt = state.get("authored_rvt")
    if not rvt:
        return job.skipped("no authored .rvt (author-prompt did not pass)")

    # call 1: info (ids + names every other command needs)
    inv = s.run("rvt_edit info", lambda s: [
        s.bootstrap("tekton-edit"), "run", "rvt_edit.py", s.stage_input(rvt), "info"])
    job.invocations.append(inv)
    info = _json_or_none(inv.stdout)
    if inv.exit_code != 0 or not info or not info.get("levels"):
        return job.fail(f"info failed: {_why(inv)}")
    lvl = max(info["levels"], key=lambda l: l.get("elevation_ft", 0.0))

    # call 2: the edit (nudge the top level; deterministic, always present)
    edited_name = "edited.rvt"
    inv = s.run("rvt_edit set-level", lambda s: [
        s.bootstrap("tekton-edit"), "run", "rvt_edit.py", s.stage_input(rvt),
        "set-level", "--id", str(lvl["id"]),
        "--elevation-ft", str(round(lvl["elevation_ft"] + 0.25, 4)),
        "-o", os.path.join(s.workdir, edited_name)])
    job.invocations.append(inv)
    edited = os.path.join(s.workdir, edited_name)
    if inv.exit_code != 0 or not os.path.isfile(edited):
        return job.fail(f"set-level failed: {_why(inv)}")
    edited = s.keep_artifact(edited, "edited.rvt")

    # call 3: the mandatory gate on every written file
    inv = s.run("validate edited", lambda s: [
        s.bootstrap("tekton-edit"), "run", "rvt_validate.py",
        s.stage_input(edited), "--quiet"])
    job.invocations.append(inv)
    if inv.exit_code != 0:
        return job.fail(f"edited file failed the gate: {_why(inv)}")
    return job


def job_go_edit(s: Surface, state: dict) -> JobResult:
    """The tekton-edit SKILL flow since #111: ONE `go edit` call = readiness +
    the edit + the structural self-check + the mandatory validation gate, one
    combined JSON.  Runs on the bundled Revit 2025 base so it needs no
    earlier step.  SKIPPED (not failed) on plugin builds without `go edit`."""
    job = JobResult("go-edit")
    edited_name = "go-edited.rvt"
    inv = s.run("go edit set-level (2025 base)", lambda s: [
        s.bootstrap("tekton-edit"), "go", "edit",
        os.path.join(s.plugin_dir, GO_EDIT_BASE_REL),
        "set-level", "--id", str(GO_EDIT_LEVEL_ID), "--elevation-ft", "5.0",
        "-o", os.path.join(s.workdir, "out", edited_name)])
    job.invocations.append(inv)
    res = _json_or_none(inv.stdout)
    if res is None or "verb" not in res.get("go", {}):
        # pre-`go` builds print the readiness line; pre-#111 `go` has no verb
        # marker (and no `edit` verb) -- an absent feature, not a failure
        return job.skipped("`go edit` not in this plugin build yet")
    inner = res.get("result")
    if not isinstance(inner, dict) or "gates" not in inner:
        return job.fail(f"go edit failed: {_why(inv)}")
    if inv.exit_code != 0 or not inner.get("ok"):
        return job.fail(f"go edit not ok: {_why(inv)}")
    out = (inner.get("output") or {}).get("path")
    if not out or not os.path.isfile(out):
        return job.fail("go edit reported ok but wrote no file")
    s.keep_artifact(out, edited_name)
    job.breakdown = {"job_seconds": res["go"].get("job_seconds"),
                     "preflight_seconds": res["go"].get("preflight_seconds"),
                     "edit_seconds": inner.get("seconds"),
                     "validation_seconds": inner["gates"]["validation"].get("elapsed_s"),
                     "gates": inner["gates"].get("line")}
    return job


def job_validate(s: Surface, state: dict) -> JobResult:
    job = JobResult("validate")
    rvt = state.get("authored_rvt")
    if not rvt:
        return job.skipped("no authored .rvt (author-prompt did not pass)")
    inv = s.run("rvt_validate authored", lambda s: [
        s.bootstrap("tekton-inspect"), "run", "rvt_validate.py",
        s.stage_input(rvt), "--quiet"])
    job.invocations.append(inv)
    if inv.exit_code != 0:
        return job.fail(f"validator errors: {_why(inv)}")
    return job


_MISSING_MODULE = re.compile(r"No module named '([A-Za-z_]\w*)")   # top-level name of a dotted module


def _missing_prerequisite(inv: Invocation, needs) -> list:
    """Which of a job's declared prerequisites ``needs`` (module names) a
    failed call could not import -- read from its ``ModuleNotFoundError``, in
    ``needs`` order; ``[]`` when the call passed or failed for another reason."""
    if inv.exit_code == 0:
        return []
    named = set(_MISSING_MODULE.findall(inv.stderr or ""))
    return [n for n in needs if n in named]


def _tier_name(tier) -> str:
    """'Tier 1 (partial)' from the report's 'Tier 1 (partial) -- imports usably
    but ...' -- the tier without its one-line gloss."""
    return str(tier).split(" -- ")[0]


def _ifc_score(path: str) -> dict:
    """``{"score", "tier", "schema_errors"}`` from a ``validate_ifc.py --json``
    report on disk, or ``{}`` when no score is readable there."""
    rep = _d(_read_json(path))
    sc = _d(rep.get("score"))
    if "score" not in sc or "tier" not in sc:
        return {}
    return {"score": sc["score"], "tier": sc["tier"],
            "schema_errors": _d(rep.get("schema")).get("n_errors")}


def _ifc_summary(bd: dict) -> str:
    """'score 35.7 -> 77.0 (Tier 0 (v1-like) -> Tier 1 (partial)); 124 boxes ->
    extrusions; products 14 -> 13; GlobalIds 13/13 kept; schema errors after 0'
    -- what hardening did, for the table notes (the stage rows carry the time)."""
    parts = [f"score {bd['score_before']} -> {bd['score_after']} "
             f"({bd['tier_before']} -> {bd['tier_after']})"]
    if bd["boxes_converted"] is not None:
        parts.append(f"{bd['boxes_converted']} boxes -> extrusions")
    if bd["products_before"] is not None:
        parts.append(f"products {bd['products_before']} -> {bd['products_after']}")
    if bd["globalids_preserved"] is not None:
        parts.append(f"GlobalIds {bd['globalids_preserved']}/{bd['products_after']} kept")
    parts.append(f"schema errors after {bd['schema_errors_after']}")
    return "; ".join(parts)


def _ifc_skill_blocked(job: JobResult, inv: Invocation):
    """The BLOCKED verdict both tekton-ifc jobs share: the call failed at
    import on one of the skill's declared wheels -> the job, blocked, with
    that prerequisite stated; None when the call passed or failed otherwise."""
    missing = _missing_prerequisite(inv, IFC_SKILL_NEEDS)
    if not missing:
        return None
    prereq = {"route": "ifc-skill", "needs": missing, "fix": IFC_SKILL_FIX}
    return job.blocked("tekton-ifc tools cannot import on this interpreter: "
                       + _needs_words(prereq), prerequisite=prereq)


def job_ifc_harden(s: Surface, state: dict) -> JobResult:
    """The tekton-ifc skill's documented flow on a foreign IFC (its SKILL.md
    5.2-5.4) on the plugin's sample: validate_ifc.py -> harden_ifc.py ->
    validate_ifc.py on the hardened file (it must reopen clean) -> report.py,
    FOUR shell calls of plain CLIs -- no `rvt`, no `go`, its own session
    (issue #113).  They import ifcopenshell + numpy (scripts/requirements.txt;
    the session's `pip install` is a network call this harness never makes),
    so an interpreter without them fails the FIRST call at import -> BLOCKED
    with that prerequisite stated, never FAIL."""
    job = JobResult("ifc-harden")
    tag = f"ifc-{s.call_no + 1}"
    stages: list = []

    def tool(s: Surface, name: str) -> str:
        return os.path.join(s.plugin_dir, IFC_SKILL_SCRIPTS_REL, name)

    def out(s: Surface, name: str) -> str:          # this call's workdir (stateless: fresh per call)
        return os.path.join(s.workdir, f"{tag}-{name}")

    def call(step: str, label: str, argv_builder) -> Invocation:
        inv = s.run(label, argv_builder)
        job.invocations.append(inv)
        stages.append({"stage": step, "seconds": round(inv.seconds, 3)})
        return inv

    # call 1: validate the input -- score/tier BEFORE
    inv = call("validate", "validate_ifc (sample)", lambda s: [
        tool(s, "validate_ifc.py"), os.path.join(s.plugin_dir, IFC_EXAMPLE_REL),
        "--json", out(s, "validate.json")])
    if _ifc_skill_blocked(job, inv):
        return job
    if inv.exit_code != 0:
        return job.fail(f"validate_ifc failed: {_why(inv)}")
    validate_json = out(s, "validate.json")
    before = _ifc_score(validate_json)
    if not before:
        return job.fail("validate_ifc wrote no score")
    validate_json = s.keep_artifact(validate_json, "ifc-validate.json")

    # call 2: harden -> the rewritten IFC + its action/diff report (exit 1 =
    # the rewritten file has schema errors: the tool's own contract failed)
    inv = call("harden", "harden_ifc", lambda s: [
        tool(s, "harden_ifc.py"), os.path.join(s.plugin_dir, IFC_EXAMPLE_REL),
        "-o", out(s, "hardened.ifc"), "--report", out(s, "harden.json")])
    hardened, harden_json = out(s, "hardened.ifc"), out(s, "harden.json")
    if inv.exit_code != 0 or not os.path.isfile(hardened):
        return job.fail(f"harden_ifc failed: {_why(inv)}")
    hardened = s.keep_artifact(hardened, "ifc-hardened.ifc")
    harden_json = s.keep_artifact(harden_json, "ifc-harden.json")

    # call 3: the hardened file must reopen clean -- score/tier AFTER
    inv = call("re-validate", "validate_ifc (hardened)", lambda s: [
        tool(s, "validate_ifc.py"), s.stage_input(hardened),
        "--json", out(s, "validate-after.json")])
    validate_after_json = out(s, "validate-after.json")
    after = _ifc_score(validate_after_json)
    if inv.exit_code != 0 or not after:
        return job.fail(f"validate_ifc (hardened) failed: {_why(inv)}")
    validate_after_json = s.keep_artifact(validate_after_json, "ifc-validate-after.json")

    # call 4: the delivery report (stdlib-only) OF THE HARDENED FILE with the before/after section --
    # named explicitly: the artifacts are kept under bench names, so report.py's sibling rule cannot apply (#760)
    inv = call("report", "report (before/after)", lambda s: [
        tool(s, "report.py"), s.stage_input(validate_json),
        "--compare", s.stage_input(harden_json),
        "--after", s.stage_input(validate_after_json), "-o", out(s, "report.md")])
    report_md = out(s, "report.md")
    if inv.exit_code != 0 or not os.path.isfile(report_md):
        return job.fail(f"report failed: {_why(inv)}")
    s.keep_artifact(report_md, "ifc-report.md")

    actions = _d(_d(_read_json(harden_json)).get("actions"))
    job.breakdown = _ifc_breakdown(stages, before, after, actions)
    return job


def _ifc_breakdown(stages: list, before: dict, after: dict, actions: dict) -> dict:
    """The breakdown both tekton-ifc jobs report: the stage timings, the
    before/after score + tier, and what hardening did (from harden_ifc's
    ``actions``), summarised for the table notes."""
    bd = {
        "stages": stages,
        "score_before": before["score"], "tier_before": _tier_name(before["tier"]),
        "score_after": after["score"], "tier_after": _tier_name(after["tier"]),
        "schema_errors_after": after["schema_errors"],
        "boxes_converted": actions.get("boxes_converted"),
        "globalids_preserved": actions.get("product_globalids_preserved"),
        "products_before": actions.get("products_before"),
        "products_after": actions.get("products_after"),
    }
    bd["summary"] = _ifc_summary(bd)
    return bd


def job_go_ifc_harden(s: Surface, state: dict) -> JobResult:
    """The same tekton-ifc flow as ONE shell call: ``scripts/ifc_flow.py
    SAMPLE --out DIR --json`` runs validate -> harden -> re-validate -> report
    in one process (one ifcopenshell import, the input analysed once and the
    hardened output once) and prints one JSON summary (issue #754).  Same
    verdicts as `ifc-harden`: BLOCKED when the interpreter cannot import the
    wheels (its own ModuleNotFoundError at the first import), FAIL when the
    flow failed or the hardened file has schema errors (the files are still
    delivered -- the tool exits 1, never withholds), PASS otherwise."""
    job = JobResult("go-ifc-harden")
    tag = f"go-ifc-{s.call_no + 1}"
    inv = s.run("ifc_flow (sample, one call)", lambda s: [
        os.path.join(s.plugin_dir, IFC_SKILL_SCRIPTS_REL, "ifc_flow.py"),
        os.path.join(s.plugin_dir, IFC_EXAMPLE_REL),
        "--out", os.path.join(s.workdir, tag), "--json"])
    job.invocations.append(inv)
    if _ifc_skill_blocked(job, inv):
        return job
    env = _d(_json_or_none(inv.stdout))
    for path in _d(env.get("files")).values():        # delivered whatever the verdict (exit 1 too)
        if isinstance(path, str) and os.path.isfile(path):
            s.keep_artifact(path, "go-ifc-" + os.path.basename(path))
    if inv.exit_code != 0:                             # exit 1 names its verdict in the envelope's `line`
        return job.fail(f"ifc_flow failed: {_why(inv)}")
    before, after = _d(env.get("before")), _d(env.get("after"))
    if "score" not in before or "score" not in after:
        return job.fail("ifc_flow printed no before/after score")
    job.breakdown = _ifc_breakdown(env.get("stages") or [], before, after, _d(env.get("actions")))
    job.breakdown["job_seconds"] = env.get("seconds")       # in-process time; the rest is the interpreter + imports
    return job


JOBS = {
    "preflight": job_preflight,
    "author-prompt": job_author_prompt,
    "go-author-prompt": job_go_author_prompt,
    "go-author-6panels": job_go_author_6panels,
    "author-ifc": job_author_ifc,
    "go-author-ifc": job_go_author_ifc,
    "edit-roundtrip": job_edit_roundtrip,
    "go-edit": job_go_edit,
    "validate": job_validate,
    "ifc-harden": job_ifc_harden,
    "go-ifc-harden": job_go_ifc_harden,
}


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------

def bench_surface(name: str, source: str, bench_root: str, python: str,
                  jobs: list, timeout: float, assume_network: bool) -> dict:
    s = Surface(name, source, bench_root, python,
                stateless=(name == "codeexec"),
                no_network=(name != "local" and not assume_network),
                timeout=timeout)
    state: dict = {}
    results: list[JobResult] = []
    for jn in jobs:
        results.append(JOBS[jn](s, state))
    return {
        "surface": name,
        "model": SURFACE_BLURB[name],
        "python": python,
        "python_version": state.get("preflight", {}).get("python"),
        "extras": state.get("preflight", {}).get("extras"),
        "plugin_source": os.path.relpath(source, ROOT) if source.startswith(ROOT) else source,
        "session_setup_seconds": round(s.setup_seconds, 3),
        "jobs": [j.as_dict() for j in results],
        "session_totals": {
            "shell_calls": sum(j.calls for j in results),
            "seconds": round(sum(j.seconds for j in results), 3),
            "extract_seconds": round(sum(j.extract_seconds for j in results), 3),
        },
    }


def _cell(jd: dict, surface: str) -> str:
    if jd is None:
        return "--"
    mark = {"PASS": "", "FAIL": " FAIL", "BLOCKED": " BLOCKED", "SKIPPED": " skipped"}[jd["status"]]
    if jd["status"] in ("SKIPPED",):
        return "skipped"
    needs = (jd.get("prerequisite") or {}).get("needs")
    if needs:                                # BLOCKED (needs numpy): the stated prerequisite
        mark += f" ({_needs_words({'needs': needs})})"
    secs = f"{jd['seconds']:.1f}s"
    if surface == "codeexec" and jd["extract_seconds"]:
        secs += f" (+{jd['extract_seconds']:.1f}s extract)"
    return secs + mark


def markdown_table(report: dict) -> str:
    surfaces = [r["surface"] for r in report["surfaces"]]
    by = {r["surface"]: r for r in report["surfaces"]}
    lines = []
    lines.append("| job | shell calls | " + " | ".join(surfaces) + " |")
    lines.append("|---|---|" + "|".join("---" for _ in surfaces) + "|")
    jobs = [j["job"] for j in report["surfaces"][0]["jobs"]]
    for jn in jobs:
        row = []
        calls = None
        for sn in surfaces:
            jd = next((j for j in by[sn]["jobs"] if j["job"] == jn), None)
            row.append(_cell(jd, sn))
            if jd and jd["status"] != "SKIPPED":
                calls = jd["shell_calls"]
        lines.append(f"| {jn} | {calls if calls is not None else '--'} | " + " | ".join(row) + " |")
    tot = []
    for sn in surfaces:
        t = by[sn]["session_totals"]
        cell = f"**{t['seconds']:.1f}s / {t['shell_calls']} calls**"
        if sn == "codeexec" and t["extract_seconds"]:
            cell += f" (+{t['extract_seconds']:.1f}s extract)"
        tot.append(cell)
    lines.append("| **session total** |  | " + " | ".join(tot) + " |")
    notes = []
    for sn in surfaces:
        r = by[sn]
        pv = r.get("python_version") or "?"
        ex = r.get("extras") or {}
        exs = ", ".join(f"{k}={'yes' if v else 'NO'}" for k, v in sorted(ex.items())) or "?"
        setup = f"; session setup (one unzip) {r['session_setup_seconds']:.1f}s" \
            if r["session_setup_seconds"] else ""
        notes.append(f"- **{sn}** -- {r['model']}; python {pv}; extras: {exs}{setup}")
    # where the author jobs' time goes inside the process (manifest build.stages)
    for sn in surfaces:
        for jd in by[sn]["jobs"]:
            bd = jd.get("breakdown")
            if bd and bd.get("stages"):
                notes.append(f"- {sn} / {jd['job']} stages: {_fmt_breakdown(bd)}")
            elif bd and bd.get("gates"):                # go-edit: edit + gates inside ONE call
                notes.append(f"- {sn} / {jd['job']}: job {bd.get('job_seconds')}s "
                             f"(edit+gates {bd.get('edit_seconds')}s, of which validator "
                             f"{bd.get('validation_seconds')}s) -- {bd['gates']}")
    reasons = []
    for sn in surfaces:
        for jd in by[sn]["jobs"]:
            if jd["status"] not in ("PASS",) and jd["reason"]:
                reasons.append(f"- {sn} / {jd['job']}: {jd['status']} -- {jd['reason']}")
    out = "\n".join(lines) + "\n\n" + "\n".join(notes)
    if reasons:
        out += "\n\nNon-PASS detail:\n" + "\n".join(reasons)
    return out


def run_bench(surfaces=SURFACE_ORDER, jobs=JOB_ORDER, source: str = "",
              python_bare: str = "/usr/bin/python3", timeout: float = 300.0,
              workroot: str = "", keep: bool = False,
              assume_network: bool = False) -> dict:
    """Programmatic entry (used by tests/test_surface_perf.py)."""
    if not source:
        source = DEFAULT_ZIP if os.path.isfile(DEFAULT_ZIP) else PLUGIN_TREE
    bench_root = workroot or tempfile.mkdtemp(prefix="tekton-surface-bench-")
    os.makedirs(bench_root, exist_ok=True)
    try:
        report = {
            "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
            "plugin_source": os.path.relpath(source, ROOT) if source.startswith(ROOT) else source,
            "host": {"platform": sys.platform, "bench_python": sys.version.split()[0]},
            "surfaces": [],
        }
        for sn in surfaces:
            python = sys.executable if sn == "local" else python_bare
            report["surfaces"].append(
                bench_surface(sn, source, bench_root, python, list(jobs),
                              timeout, assume_network))
        return report
    finally:
        if not keep:
            shutil.rmtree(bench_root, ignore_errors=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="tekton simulated-surface benchmark")
    ap.add_argument("--surfaces", default=",".join(SURFACE_ORDER),
                    help=f"comma list of {'/'.join(SURFACE_ORDER)}")
    ap.add_argument("--jobs", default=",".join(JOB_ORDER),
                    help=f"comma list of {'/'.join(JOB_ORDER)} (session order kept)")
    ap.add_argument("--zip", dest="source", default="",
                    help="plugin source: a tekton-plugin.zip (default) ")
    ap.add_argument("--from-tree", action="store_true",
                    help="use the plugin/ working tree instead of the shipped zip")
    ap.add_argument("--python-bare", default="/usr/bin/python3",
                    help="the bare interpreter approximating the sandbox VMs")
    ap.add_argument("--timeout", type=float, default=300.0)
    ap.add_argument("--workroot", default="", help="build the environments here")
    ap.add_argument("--keep", action="store_true", help="keep the environments")
    ap.add_argument("--assume-network", action="store_true",
                    help="do NOT install the dead-proxy no-network guard")
    ap.add_argument("--json", dest="json_out", default="", help="write the full report")
    ap.add_argument("--md", dest="md_out", default="", help="write the markdown table")
    a = ap.parse_args(argv)

    surfaces = [s.strip() for s in a.surfaces.split(",") if s.strip()]
    bad = [s for s in surfaces if s not in SURFACE_ORDER]
    if bad:
        ap.error(f"unknown surface(s): {bad}")
    jobs = [j.strip() for j in a.jobs.split(",") if j.strip()]
    bad = [j for j in jobs if j not in JOBS]
    if bad:
        ap.error(f"unknown job(s): {bad}")
    source = a.source
    if a.from_tree:
        source = PLUGIN_TREE
    elif not source:
        source = DEFAULT_ZIP if os.path.isfile(DEFAULT_ZIP) else PLUGIN_TREE

    report = run_bench(surfaces=surfaces, jobs=jobs, source=source,
                       python_bare=a.python_bare, timeout=a.timeout,
                       workroot=a.workroot, keep=a.keep,
                       assume_network=a.assume_network)
    table = markdown_table(report)
    print(table)
    if a.json_out:
        with open(a.json_out, "w") as fh:
            json.dump(report, fh, indent=1)
        print(f"\n[json -> {a.json_out}]")
    if a.md_out:
        with open(a.md_out, "w") as fh:
            fh.write(f"# tekton surface benchmark ({report['generated']}; "
                     f"source {report['plugin_source']})\n\n" + table + "\n")
        print(f"[md -> {a.md_out}]")
    # exit 1 only on FAIL (BLOCKED/SKIPPED are honest surface truths)
    fails = [1 for s in report["surfaces"] for j in s["jobs"] if j["status"] == "FAIL"]
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
