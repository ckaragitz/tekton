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
  the prompt path never exercises it (the validator's ECC tier verifies on
  its stdlib decoder, never an import-time corpse; every family's own
  report validates ok -- issue #75);
* the IFC ROUTE's one prerequisite (numpy) is stated UP FRONT on that bare
  interpreter -- preflight's ``routes`` / ``ifc-route`` segment, and `go
  author --ifc` answering ONE JSON with ``go.prerequisite``, exit 3, 0 B
  stderr, no job attempted -- while numpy present means no gate (issue #127);
* the four skill ``_bootstrap.py`` shims stay byte-identical.
"""
from __future__ import annotations

import glob
import hashlib
import importlib.util
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
    subprocess so the miss loader never leaks into this test process."""
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
sch = S.parse(blob)                       # miss loader registered: should hit the cache
hit = getattr(sch, "_from_cache", False)
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
# per-route capability: the --ifc route's prerequisite is stated UP FRONT
# (issue #127) -- READY never precedes a guaranteed FAILED
# ---------------------------------------------------------------------------

IFC_EXAMPLE_REL = os.path.join("skills", "tekton-author", "examples",
                               "electrical-room-2500a.ifc")

# the exact probe preflight uses -- and numpy is never imported into this process
HAVE_NUMPY = importlib.util.find_spec("numpy") is not None


def test_preflight_states_ifc_route_needs_numpy_when_absent(plugin_copy, workdir):
    """Bare interpreter (-I -S, no numpy): the environment IS ready (prompt
    and rvt routes build), and the ONE line + the JSON say the ifc route
    needs numpy and how to get it -- before any job is started."""
    r = _run(BARE_PY + [_bootstrap(plugin_copy), "--json"], cwd=workdir)
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stderr == ""
    pf = json.loads(r.stdout)
    assert pf["ok"] is True and pf["line"].startswith("tekton: READY")
    routes = pf["routes"]
    assert routes["prompt"] == {"ok": True, "needs": []}
    assert routes["rvt"] == {"ok": True, "needs": []}
    assert routes["ifc"]["ok"] is False
    assert routes["ifc"]["needs"] == ["numpy"]
    assert "pip install numpy" in routes["ifc"]["fix"]
    assert "| ifc-route needs numpy" in pf["line"]


@pytest.mark.skipif(not HAVE_NUMPY, reason="numpy not installed in this interpreter")
def test_preflight_states_ifc_route_ok_when_numpy_present(plugin_copy, workdir):
    r = _run([sys.executable, "-I", _bootstrap(plugin_copy), "--json"], cwd=workdir)
    assert r.returncode == 0, r.stderr[-2000:]
    pf = json.loads(r.stdout)
    assert pf["routes"]["ifc"] == {"ok": True, "needs": []}
    assert "| ifc-route OK |" in pf["line"]


def test_go_author_ifc_without_numpy_states_prerequisite_once(plugin_copy, workdir):
    """`go author --ifc` on a numpy-less interpreter: ONE JSON, exit 3,
    0 B stderr, the prerequisite named up front (go.prerequisite + a
    relayable NOT READY line), and the job never attempted (no half-built
    out dir, no mid-job error)."""
    out = os.path.join(workdir, "go-ifc-nonumpy")
    r = _run(BARE_PY + [_bootstrap(plugin_copy), "go", "author",
                        "--ifc", os.path.join(plugin_copy, IFC_EXAMPLE_REL),
                        "--target-version", "2025", "--out", out, "--json"], cwd=workdir)
    assert r.returncode == 3, r.stderr[-2000:]
    assert r.stderr == ""
    doc = json.loads(r.stdout)                     # stdout IS one JSON object
    g = doc["go"]
    assert g["ready"] is False and g["exit_code"] == 3
    assert g["prerequisite"]["route"] == "ifc" and g["prerequisite"]["needs"] == ["numpy"]
    assert "pip install numpy" in g["prerequisite"]["fix"]
    assert g["preflight_line"].startswith("tekton: NOT READY for --ifc")
    assert "numpy" in g["preflight_line"]
    assert g["preflight"]["ok"] is True             # the ENVIRONMENT is fine
    assert doc["result"] is None
    assert "job_seconds" not in g and not os.path.exists(out)


def test_ifc_route_prerequisite_table_matches_the_engine(plugin_copy, workdir):
    """Drift guard for tekton_env.ROUTE_EXTRAS: run the front door itself
    (no `go` gate) without numpy -- it must stop on exactly that missing
    extra, named, with the fix, in ONE JSON and 0 B stderr.  If the ifc
    route ever goes numpy-free this turns red and the table must follow."""
    out = os.path.join(workdir, "run-ifc-nonumpy")
    r = _run(BARE_PY + [_bootstrap(plugin_copy), "run", "frontdoor.py", "author",
                        "--ifc", os.path.join(plugin_copy, IFC_EXAMPLE_REL),
                        "--target-version", "2025", "--out", out, "--json"], cwd=workdir)
    assert r.returncode == 3, r.stderr[-2000:]
    assert r.stderr == ""
    res = json.loads(r.stdout)
    assert res["route"] == "ifc" and res["ok"] is False
    assert len(res["errors"]) == 1
    err = res["errors"][0]
    assert err.startswith("IFC intent failed: the --ifc route needs numpy"), err
    assert "pip install numpy" in err
    assert res["status"] == f"FAILED ({err})"        # whole, not cut mid-sentence
    assert os.path.isfile(res["manifest"]["json"])   # the manifest is still delivered


@pytest.mark.skipif(not HAVE_NUMPY, reason="numpy not installed in this interpreter")
def test_go_author_ifc_with_numpy_is_not_gated(plugin_copy, workdir):
    """The gate only ever fires on a MISSING extra: with numpy importable the
    same call runs the job (go.prerequisite absent, a result present)."""
    out = os.path.join(workdir, "go-ifc-numpy")
    r = _run([sys.executable, "-I", _bootstrap(plugin_copy), "go", "author",
              "--ifc", os.path.join(plugin_copy, IFC_EXAMPLE_REL),
              "--target-version", "2025", "--out", out, "--stages", "W", "--json"],
             cwd=workdir, timeout=900)
    doc = json.loads(r.stdout)
    g = doc["go"]
    assert g["ready"] is True and "prerequisite" not in g
    assert doc["result"] is not None and doc["result"]["route"] == "ifc"
    assert os.path.isfile(doc["result"]["intent_json"])


# ---------------------------------------------------------------------------
# the prompt route on a BARE interpreter: zero extras installed
# ---------------------------------------------------------------------------

def test_prompt_fallback_build_runs_without_numpy(plugin_copy, workdir):
    """THE headline: the full prompt fallback native build (families ->
    load -> walls -> equipment) completes and writes the combined .rvt with
    NO numpy anywhere on the interpreter.  The validator's ECC tier runs on
    its stdlib decoder there -- never an import-time crash, never a withheld
    file -- and every generated family's OWN report validates ok with a
    family-mode verdict (issue #75: it used to say ``ok: false`` /
    "not CRCIO-framed" on exactly this surface)."""
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
    fam_reports = sorted(glob.glob(os.path.join(out, "families", "*.json")))
    assert fam_reports, "the build must write one report per generated family"
    for p in fam_reports:
        v = json.load(open(p)).get("validate") or {}
        assert v.get("ok") is True, (os.path.basename(p), v.get("error") or v)
        assert (v.get("family_mode") or {}).get("verdict") == "VALID", os.path.basename(p)


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
