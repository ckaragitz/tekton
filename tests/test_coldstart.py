"""Cold-start caches + one-call dispatch (perf-coldstart stream).

What is proven here:

* the BUILD-TIME SCHEMA CACHE (``rvt.schema_cache``) reconstructs the parsed
  ``Formats/Latest`` schema class-for-class identical to a fresh parse of the
  same bytes, is keyed by the content sha256 (a wrong hit is impossible by
  construction), ships in the plugin (``assets/schema_cache/``), and falls
  back to the real parser on any miss;
* ``_bootstrap.py go ...`` is ONE Bash call: inline preflight + the job +
  ONE combined JSON on stdout (ready and not-ready shapes, exit codes);
* the PROMPT ROUTE runs on a bare interpreter with ZERO extras installed
  (``-I -S``: no site-packages, hence no numpy): module import, the handoff
  package, and the full fallback native build all work -- numpy is lazy and
  the prompt path never exercises it (the validator's ECC tier degrades to a
  stated ERROR, never an import-time corpse);
* the four skill ``_bootstrap.py`` shims stay byte-identical.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "plugin")
SRC = os.path.join(ROOT, "src")

PROMPT = ("an electrical room 20x15 ft rated for 800 A service with one "
          "switchboard and two lighting panels")
SMALL_PROMPT = "an electrical room 12x10 ft with one lighting panel"

# -I -S: isolated, no site -> no pip-installed extras AT ALL (no numpy).
BARE_PY = [sys.executable, "-I", "-S"]


def _copy_plugin(dst_root: str) -> str:
    dst = os.path.join(dst_root, "plugin copy (bare)")
    ign = shutil.ignore_patterns("__pycache__", "node_modules", ".pytest_cache",
                                 ".DS_Store")
    for part in (".claude-plugin", "skills", "lib", "assets"):
        src = os.path.join(PLUGIN, part)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(dst, part), ignore=ign)
    return dst


@pytest.fixture(scope="module")
def plugin_copy(tmp_path_factory):
    return _copy_plugin(str(tmp_path_factory.mktemp("coldstart")))


@pytest.fixture(scope="module")
def workdir(tmp_path_factory):
    return str(tmp_path_factory.mktemp("coldwork"))


def _bootstrap(copy_root: str, skill: str = "tekton-author") -> str:
    return os.path.join(copy_root, "skills", skill, "scripts", "_bootstrap.py")


def _run(args, cwd, timeout=600):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("RVT_") and k != "PYTHONPATH"}
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True,
                          text=True, timeout=timeout)


def _embedded_schema_blob():
    sys.path.insert(0, SRC)
    from rvt.frontdoor import standalone as SA
    bp = SA.bundled_base_path(os.path.join(PLUGIN, "assets", "genesis", "G_ABPD.rvt"),
                              verify=False)
    return SA._inflate_formats_latest(bp)


# ---------------------------------------------------------------------------
# schema cache: fidelity, shipping, keying
# ---------------------------------------------------------------------------

def test_schema_cache_roundtrip_is_class_for_class_identical(tmp_path):
    sys.path.insert(0, SRC)
    from rvt import schema as S, schema_cache as SC
    blob = _embedded_schema_blob()
    parsed = S.parse(blob, source="fresh")
    p = SC.dump_cache(parsed, str(tmp_path / (parsed.sha256 + SC.CACHE_EXT)))
    loaded = SC.load_cache_file(p, source="fresh")
    assert loaded is not None
    assert loaded.sha256 == parsed.sha256
    assert loaded.total_size == parsed.total_size
    assert len(loaded.classes) == len(parsed.classes)
    assert len(loaded.top_level) == len(parsed.top_level)
    for a, b in zip(parsed.classes, loaded.classes):
        assert (a.type_id, a.name, a.parent_id, a.parent, a.parent_inline,
                a.version, a.offset, a.end, a.depth, a.guids) == \
               (b.type_id, b.name, b.parent_id, b.parent, b.parent_inline,
                b.version, b.offset, b.end, b.depth, b.guids)
        fa = [(f.name, f.kind, f.flags, f.offset, f.count, f.type_id,
               f.type_name, f.inline_definition, f.extra,
               f.element is not None) for f in a.fields]
        fb = [(f.name, f.kind, f.flags, f.offset, f.count, f.type_id,
               f.type_name, f.inline_definition, f.extra,
               f.element is not None) for f in b.fields]
        assert fa == fb, a.name
    assert parsed.desc_hist == loaded.desc_hist
    assert parsed.type_refs == loaded.type_refs
    # the two derived indices behave identically
    assert loaded.by_name["ADocument"].type_id == parsed.by_name["ADocument"].type_id
    assert loaded.by_id[0x1C].name == "ADocument"


def test_schema_cache_ships_in_plugin_and_matches_bundled_base():
    d = os.path.join(PLUGIN, "assets", "schema_cache")
    assert os.path.isdir(d), "plugin must ship assets/schema_cache (sync_plugin step)"
    idx = json.load(open(os.path.join(d, "index.json")))
    assert idx["entries"], "cache index has no entries"
    blob = _embedded_schema_blob()
    digest = hashlib.sha256(blob).hexdigest()
    files = {e["schema_sha256"]: e for e in idx["entries"]}
    assert digest in files, "no cache entry for the bundled base's embedded schema"
    sys.path.insert(0, SRC)
    from rvt import schema_cache as SC
    got = SC.load_cache_file(os.path.join(d, digest + SC.CACHE_EXT))
    assert got is not None and got.sha256 == digest
    assert len(got.classes) > 4000
    assert got.by_id[0x1C].name == "ADocument"


def test_cached_parse_hit_and_fallback_miss(plugin_copy, workdir):
    """install() serves a sha-matched stream from the cache and falls back to
    the REAL parser (which raises on junk) on a miss -- proven in a bare
    subprocess so the wrapper never leaks into this test process."""
    code = r"""
import json, os, sys, hashlib
boot_dir = os.path.dirname(sys.argv[1])
sys.path.insert(0, boot_dir)
import importlib.util
spec = importlib.util.spec_from_file_location("_bootstrap", sys.argv[1])
bs = importlib.util.module_from_spec(spec); spec.loader.exec_module(bs)
bs.ensure_engine()
import rvt.schema as S
from rvt.frontdoor import standalone as SA
blob = SA._inflate_formats_latest(SA.bundled_base_path())
sch = S.parse(blob)                       # wrapped: should hit the cache
hit = getattr(S, "_schema_cache_installed", False)
try:
    S.parse(b"definitely not a schema stream")
    miss = "no-error"
except Exception as e:
    miss = type(e).__name__
print(json.dumps({"installed": bool(hit), "classes": len(sch.classes),
                  "sha": sch.sha256[:16], "miss_error": miss}))
"""
    r = _run([sys.executable, "-I", "-c", code, _bootstrap(plugin_copy)], cwd=workdir)
    assert r.returncode == 0, r.stderr[-2000:]
    out = json.loads(r.stdout)
    assert out["installed"] is True
    assert out["classes"] > 4000
    assert out["miss_error"] == "ParseError"      # fallback reached the real parser


# ---------------------------------------------------------------------------
# go: ONE call, ONE combined JSON
# ---------------------------------------------------------------------------

def test_go_one_call_prompt_handoff(plugin_copy, workdir):
    out = os.path.join(workdir, "go-handoff")
    r = _run(BARE_PY + [_bootstrap(plugin_copy), "go", "author", "--handoff-only",
                        "--prompt", PROMPT, "--out", out, "--json"], cwd=workdir)
    assert r.returncode == 0, r.stderr[-2000:]
    doc = json.loads(r.stdout)                     # stdout IS one JSON object
    g = doc["go"]
    assert g["one_call"] is True and g["ready"] is True
    assert g["preflight_line"].startswith("tekton: READY")
    assert g["exit_code"] == 0
    res = doc["result"]
    assert res["route"] == "prompt" and res["ok"] is True
    assert os.path.isfile(res["handoff"]["scene_brief"])
    assert os.path.isfile(res["handoff"]["instructions"])


def test_go_appends_json_for_author(plugin_copy, workdir):
    out = os.path.join(workdir, "go-nojson")
    r = _run(BARE_PY + [_bootstrap(plugin_copy), "go", "author", "--handoff-only",
                        "--prompt", PROMPT, "--out", out], cwd=workdir)
    assert r.returncode == 0, r.stderr[-2000:]
    doc = json.loads(r.stdout)
    assert doc["result"]["route"] == "prompt"      # --json was auto-appended


def test_go_not_ready_is_one_json_exit_3(workdir, tmp_path):
    broken = _copy_plugin(str(tmp_path))
    shutil.rmtree(os.path.join(broken, "assets", "genesis"))
    r = _run(BARE_PY + [_bootstrap(broken), "go", "author", "--prompt", PROMPT],
             cwd=workdir)
    assert r.returncode == 3
    doc = json.loads(r.stdout)
    assert doc["go"]["ready"] is False
    assert doc["result"] is None
    assert "NOT READY" in doc["go"]["preflight_line"]


def test_go_usage_error(plugin_copy, workdir):
    r = _run(BARE_PY + [_bootstrap(plugin_copy), "go"], cwd=workdir)
    assert r.returncode == 2
    assert "usage" in r.stderr.lower()


# ---------------------------------------------------------------------------
# the prompt route on a BARE interpreter: zero extras installed
# ---------------------------------------------------------------------------

def test_prompt_fallback_build_runs_without_numpy(plugin_copy, workdir):
    """THE headline: the full prompt fallback native build (families ->
    load -> walls -> equipment) completes and writes the combined .rvt with
    NO numpy anywhere on the interpreter.  The validator's vectorised ECC
    tier states its numpy need as an in-report ERROR (honest degrade, exit
    4) -- never an import-time crash, never a withheld file."""
    out = os.path.join(workdir, "go-nonumpy-build")
    r = _run(BARE_PY + [_bootstrap(plugin_copy), "go", "author",
                        "--prompt", SMALL_PROMPT, "--out", out, "--json"],
             cwd=workdir, timeout=900)
    assert r.returncode in (0, 4), r.stderr[-2000:]
    doc = json.loads(r.stdout)
    assert doc["go"]["ready"] is True
    res = doc["result"]
    assert res["route"] == "prompt"
    files = res.get("files") or {}
    assert files.get("combined") and os.path.isfile(files["combined"]), \
        "the fallback build must deliver the combined .rvt without numpy"
    assert os.path.isfile(res["intent_json"])


def test_frontdoor_import_is_numpy_free(plugin_copy, workdir):
    """Regression guard for the lazy imports: importing the whole front door
    (and the validator) must not pull numpy, and the rules parser itself
    stays numpy-free end to end."""
    code = (
        "import sys\n"
        f"sys.path.insert(0, {os.path.join(plugin_copy, 'lib', 'src')!r})\n"
        f"sys.path.insert(0, {os.path.join(plugin_copy, 'skills', '_shared', '_vendor')!r})\n"
        "import rvt.frontdoor, rvt.validate\n"
        "assert 'numpy' not in sys.modules, 'eager numpy import returned'\n"
        "from rvt.frontdoor import prompt_intent as PI\n"
        f"p = PI.parse_prompt({PROMPT!r})\n"
        "assert p.room is not None and p.items\n"
        "assert 'numpy' not in sys.modules, 'prompt parsing exercised numpy'\n"
        "print('NUMPY-FREE-OK', len(p.items))\n")
    r = _run(BARE_PY + ["-c", code], cwd=workdir)
    assert r.returncode == 0, r.stderr[-2000:]
    assert "NUMPY-FREE-OK" in r.stdout


def test_go_resolves_frontdoor_from_every_skill(plugin_copy, workdir):
    """`go author ...` works from skills that do NOT colocate frontdoor.py
    (tekton-edit / tekton-inspect / tekton-native): the canonical copy
    beside tekton-author is resolved from the plugin root, never a search."""
    for skill in ("tekton-edit", "tekton-inspect", "tekton-native"):
        out = os.path.join(workdir, f"go-{skill}")
        r = _run(BARE_PY + [_bootstrap(plugin_copy, skill), "go", "author",
                            "--handoff-only", "--prompt", PROMPT, "--out", out],
                 cwd=workdir)
        assert r.returncode == 0, (skill, r.stderr[-1500:])
        doc = json.loads(r.stdout)
        assert doc["result"]["route"] == "prompt", skill


# ---------------------------------------------------------------------------
# shim hygiene
# ---------------------------------------------------------------------------

def test_bootstrap_shims_stay_byte_identical():
    skills = ("tekton-author", "tekton-edit", "tekton-inspect", "tekton-native")
    bodies = {s: open(os.path.join(PLUGIN, "skills", s, "scripts", "_bootstrap.py"),
                      "rb").read() for s in skills}
    assert len(set(bodies.values())) == 1, \
        "the _bootstrap.py shim must stay identical in every skill"
