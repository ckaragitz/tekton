"""Tests for rvt.frontdoor.standalone -- STANDALONE CREATION FROM BUNDLED
ASSETS ONLY (problem A of the 2026-08-04 field session).

The centrepiece is the CLEAN-ENVIRONMENT reproduction + fix: a temp dir that
contains ONLY the plugin (plus the two engine scripts the sync patch adds to
its mirror -- see docs/inbox/standalone.md, patch P6), no repo extracted/,
no samples/, no vendor/, no experiments/:

* the STOCK entrypoint (patches P1-P6 applied) builds native .rvt in the
  clean env with no env var and no donor -- the field failure
  (FileNotFoundError: .../extracted/racbasicsampleproject/Formats__Latest.gz/
  000.bin) is gone, and the resolver finds the plugin bundle on its own;
* WITH ``author_standalone`` BOTH worked examples (the eaton panel prompt and
  the electrical-room IFC) build native .rvt end to end -- families
  generated (family-mode VALID 0 errors, provenance clean), loaded, placed,
  walls built from the CONSTRUCTED SWall template, project validator VALID
  0 errors -- with the research-input tripwire ARMED the whole time, so a
  single read of extracted/ | samples/ | vendor/ | experiments/genesis/
  or an Autodesk install directory would have failed the build RED.

Slow (two full builds in a subprocess): the E2E tests share one clean env
via a module fixture.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

PLUGIN = os.path.join(ROOT, "plugin")
BUNDLED_BASE = os.path.join(PLUGIN, "assets", "genesis", "G_ABPD.rvt")

#: engine scripts famdoc_adoc loads by path; the sync patch (record P6) adds
#: them to the plugin's lib/tools mirror -- the fixture simulates exactly that
SYNC_PATCH_SCRIPTS = ("genesis_assemble.py", "rvt_reduce.py")

pytestmark = pytest.mark.skipif(
    not os.path.isfile(BUNDLED_BASE),
    reason="plugin bundle (assets/genesis/G_ABPD.rvt) not present")


# ===========================================================================
# the clean environment (module-scoped: two E2E builds share it)
# ===========================================================================

@pytest.fixture(scope="module")
def clean_env(tmp_path_factory):
    root = tmp_path_factory.mktemp("tekton-clean")
    dst = os.path.join(str(root), "plugin")
    shutil.copytree(PLUGIN, dst, ignore=shutil.ignore_patterns("__pycache__"))
    for name in SYNC_PATCH_SCRIPTS:
        src = os.path.join(ROOT, "tools", name)
        if os.path.isfile(src):
            shutil.copyfile(src, os.path.join(dst, "lib", "tools", name))
    # tools/sync_plugin.py mirrors ALL of src/rvt into lib/src/rvt on its next
    # run; simulate that for the one new module (running the sync from a test
    # would rewrite plugin/ wholesale -- the orchestrator's call)
    sa = os.path.join(SRC, "rvt", "frontdoor", "standalone.py")
    shutil.copyfile(sa, os.path.join(dst, "lib", "src", "rvt", "frontdoor",
                                     "standalone.py"))
    return str(root)


def _run_clean(clean_root: str, code: str, timeout: int = 900):
    """Run ``code`` with cwd=clean_root, TEKTON_ROOT=clean_root and ONLY the
    plugin's engine on the path -- the repo checkout is unreachable."""
    env = {k: v for k, v in os.environ.items()
           if k not in ("RVT_GENESIS_BASE", "RVT_PLUGIN_ROOT", "PYTHONPATH")}
    env["TEKTON_ROOT"] = clean_root
    env["PYTHONPATH"] = os.path.join(clean_root, "plugin", "lib", "src")
    return subprocess.run([sys.executable, "-c", code], cwd=clean_root, env=env,
                          capture_output=True, text=True, timeout=timeout)


# ===========================================================================
# 1. the fix, on the STOCK path: patches P1+P2+P4+P6 applied, the field
#    failure of 2026-08-04 is gone (these two tests asserted the pre-patch
#    reproduction until the patches landed -- docs/inbox/standalone.md P1-P6)
# ===========================================================================

def test_clean_env_stock_author_is_standalone(clean_env):
    """The STOCK entrypoint (``rvt.frontdoor.author``) builds native .rvt in
    the clean env -- no $RVT_GENESIS_BASE, no donor, no research-corpus read
    (formerly: FileNotFoundError .../extracted/.../Formats__Latest.gz)."""
    code = """
import json, os
from rvt.frontdoor import author
r = author(prompt='create an eaton panel for me with 6 switches', out='out-stock')
fams = ((r.manifest.get('build') or {}).get('family_files')) or []
print(json.dumps({'status': r.status, 'errors': r.errors, 'files': r.files,
                  'combined_abs': os.path.abspath(r.files.get('combined', '')),
                  'reasons': [str(f.get('reason') or '') for f in fams],
                  'ok': [bool(f.get('ok')) for f in fams]}))
"""
    p = _run_clean(clean_env, code)
    assert p.returncode == 0, p.stderr[-2000:]
    out = json.loads(p.stdout.strip().splitlines()[-1])
    joined = " ".join(out["reasons"])
    assert "FileNotFoundError" not in joined, joined
    assert "extracted" not in joined and "Formats__Latest" not in joined, joined
    assert out["errors"] == [], out["errors"]
    assert "combined" in out["files"], out
    assert os.path.isfile(out["combined_abs"]), out["combined_abs"]
    assert out["ok"] and all(out["ok"]), out


def test_clean_env_base_resolves_to_plugin_bundle(clean_env):
    """P2: the pinned resolver probes the plugin's real bundle location
    (assets/genesis) relative to the package itself -- no env var needed."""
    code = """
import json, os
from rvt.frontdoor.base import resolve_base
rb = resolve_base(None)
print(json.dumps({'path': os.path.abspath(rb.path), 'source': rb.source,
                  'certified': rb.certified}))
"""
    p = _run_clean(clean_env, code)
    assert p.returncode == 0, p.stderr[-2000:]
    out = json.loads(p.stdout.strip().splitlines()[-1])
    want = os.path.join(clean_env, "plugin", "assets", "genesis", "G_ABPD.rvt")
    assert os.path.realpath(out["path"]) == os.path.realpath(want), out
    assert out["source"] == "pinned-bundled" and out["certified"] is True, out


# ===========================================================================
# 2. the fix: BOTH worked examples, zero donor files, tripwire armed
# ===========================================================================

def _assert_built(res: dict, *, want_walls: int, want_instances: int):
    assert res["errors"] == [], res["errors"]
    assert "combined" in res["files"], res
    b = res["build"]
    fams = b["family_files"]
    built = [f for f in fams if f.get("ok")]
    assert built and all(f.get("ok") for f in built), fams
    kinds = res["created_kinds"]
    assert kinds.get("equipment-instance", 0) == want_instances, kinds
    assert kinds.get("wall", 0) == want_walls, kinds
    v = b["validation"]["combined"]
    assert v["validate"]["verdict"] == "VALID"
    assert v["validate"]["n_errors"] == 0
    assert v["identity"]["status"] == "PASS"
    assert v["census"].get("coherent") is not False
    # THE DELIVERABLE RULE: PROOF-ONLY is a stamp on a delivered file, never
    # a reason a file is missing
    assert os.path.isfile(res["combined_abs"]), res["combined_abs"]
    for f in res["family_reports"]:
        fm = f["family_mode"]
        assert fm["verdict"] == "VALID" and fm["n_errors"] == 0, f
        assert f["provenance_ok"] is True, f
        assert f["container_mode"] == "bundled-base", f


_E2E_CODE = """
import glob, json, os
from rvt.frontdoor.standalone import author_standalone
r = author_standalone(%(kw)s, out=%(out)r, guard=True)
b = r.manifest.get('build') or {}
kinds = {}
for c in b.get('elements_created') or []:
    kinds[c['kind']] = kinds.get(c['kind'], 0) + 1
reports = []
for rp in sorted(glob.glob(os.path.join(%(out)r, 'families', '*.json'))):
    d = json.load(open(rp))
    reports.append({'family_mode': ((d.get('validate') or {}).get('family_mode')) or {},
                    'provenance_ok': (d.get('provenance') or {}).get('ok'),
                    'container_mode': d.get('container_mode')})
print(json.dumps({'status': r.status, 'errors': r.errors, 'files': r.files,
                  'combined_abs': os.path.abspath(r.files.get('combined', '')),
                  'created_kinds': kinds,
                  'build': {'family_files': b.get('family_files') or [],
                            'validation': b.get('validation') or {},
                            'degradations': b.get('degradations') or []},
                  'family_reports': reports}))
"""


def test_standalone_eaton_panel_prompt(clean_env):
    code = _E2E_CODE % {"kw": "prompt='create an eaton panel for me with 6 switches'",
                        "out": "out-eaton"}
    p = _run_clean(clean_env, code)
    assert p.returncode == 0, (p.stdout[-1500:], p.stderr[-2500:])
    res = json.loads(p.stdout.strip().splitlines()[-1])
    _assert_built(res, want_walls=0, want_instances=1)


def test_standalone_electrical_room_ifc(clean_env):
    ifc = os.path.join("plugin", "skills", "tekton-author", "examples",
                       "electrical-room-2500a.ifc")
    assert os.path.isfile(os.path.join(clean_env, ifc))
    code = _E2E_CODE % {"kw": f"ifc={ifc!r}", "out": "out-room"}
    p = _run_clean(clean_env, code, timeout=1800)
    assert p.returncode == 0, (p.stdout[-1500:], p.stderr[-2500:])
    res = json.loads(p.stdout.strip().splitlines()[-1])
    _assert_built(res, want_walls=4, want_instances=8)
    assert len([f for f in res["build"]["family_files"] if f.get("ok")]) == 8


# ===========================================================================
# 3. the resolver pieces (fast, in-process; research machine or clean)
# ===========================================================================

def test_schema_identity_class_for_class():
    from rvt.frontdoor import standalone as SA
    rep = SA.schema_identity_report()
    assert rep["base_is_corpus_constant"] is True
    assert rep["identical_bytes"] is True
    if "n_classes" in rep:                       # corpus present (research machine)
        assert rep["identical_classes"] is True, rep["mismatches"][:5]
        assert rep["n_classes"] == 4690


def test_install_schema_seeds_every_chokepoint(tmp_path):
    from rvt.frontdoor import standalone as SA
    SA.install_schema()
    from rvt import adocument, encode, objects, schema
    s = objects.load_schema()                    # no-arg: must NOT touch extracted/
    assert s.sha256 == SA.SCHEMA_2026_SHA256
    assert encode.load_schema() is s
    assert adocument.load_schema() is s
    assert os.path.isfile(schema.DEFAULT_PATH)
    from rvt.genesis import skeleton as gsk
    assert gsk._SCHEMA_CACHE.get("dec") is not None
    # the contract (#315): only the default-path family answers with the
    # installed schema; an explicit path loads verbatim, a missing one raises
    assert schema.load_schema(None) is s
    assert schema.load_schema(schema.DEFAULT_PATH) is s
    missing = str(tmp_path / "typo" / "Formats_Latest_2025.bin")
    with pytest.raises(FileNotFoundError) as ei:
        objects.load_schema(missing)
    assert ei.value.filename == missing
    copy = str(tmp_path / "Formats_Latest_copy.bin")
    shutil.copyfile(schema.DEFAULT_PATH, copy)
    assert schema.load_schema(copy).sha256 == s.sha256


def test_install_schema_behind_the_plugins_lazy_wrapper(tmp_path, monkeypatch):
    """The order ``go`` uses on a bare surface: ``tekton_env`` arms the lazy
    wrapper (``skills/_shared/tekton_schema.py``) BEFORE ``install_schema``
    runs.  An explicit missing path must still end in ``FileNotFoundError``
    -- the bundled loader loads explicit paths itself instead of delegating
    back into the wrapper it replaced (which would re-enter it forever)."""
    from rvt import adocument, encode, objects, schema
    from rvt.frontdoor import standalone as SA
    for mod in (schema, objects, encode, adocument):      # restored at teardown
        monkeypatch.setattr(mod, "load_schema", mod.load_schema)
    monkeypatch.setattr(schema, "DEFAULT_PATH", schema.DEFAULT_PATH)
    monkeypatch.delattr(schema, "_tekton_lazy_bundled_schema", raising=False)
    monkeypatch.setattr(SA, "_SCHEMA_STATE", {})          # a full (re)install
    monkeypatch.syspath_prepend(os.path.join(PLUGIN, "skills", "_shared"))
    import tekton_schema as lazy
    assert lazy.install() in ("installed", "corpus-present")
    lazy_ref = schema.load_schema                         # a holder of the wrapper
    SA.install_schema()
    s = objects.load_schema()
    assert s is SA.bundled_schema()
    assert schema.load_schema() is s and adocument.load_schema(None) is s
    assert lazy_ref() is s
    missing = str(tmp_path / "no" / "such" / "schema.bin")
    for load in (schema.load_schema, objects.load_schema, lazy_ref):
        with pytest.raises(FileNotFoundError):
            load(missing)


def test_constructed_templates_encode_decode_clean():
    from rvt.frontdoor import standalone as SA
    cs = SA.ConstructedSpecimens()
    assert cs.instance_id and cs.wall_id and cs.wall_type
    assert cs.source_path.startswith("(constructed")
    from rvt.mutate import Document
    d = Document.from_file(SA.bundled_base_path())
    rep = cs.inject_into(d)
    assert rep["constructed"] is True
    assert cs.circuit_id and rep["circuit_specimen"] == cs.circuit_id
    assert set(rep["injected_ids"]) == {cs.wall_id, cs.instance_id, cs.circuit_id}
    for eid in (cs.wall_id, cs.instance_id, cs.circuit_id):
        for seq in (101, 102):
            o = d.decode(eid, seq)
            assert o is not None and o.clean, (eid, seq, o and o.errors[:2])
    w = d.add_wall(311, 600634, (0.0, 0.0), (10.0, 0.0), height=8.0,
                   template_id=cs.wall_id)
    assert d.serialize(w) is not None


def test_dependency_table_names_every_field_failure_input():
    from rvt.frontdoor import standalone as SA
    befores = " ".join(r["before"] for r in SA.dependency_table())
    for marker in ("extracted/racbasicsampleproject", "R5.rvt",
                   "racbasicsamplefamily-2026.rfa", "G_ABPD.rvt"):
        assert marker in befores, marker


def test_forbidden_autodesk_install_paths_raise():
    from rvt.frontdoor import standalone as SA
    SA.forbid_research_inputs()
    try:
        with pytest.raises(SA.StandaloneError, match="Autodesk installation"):
            open(os.path.join(os.sep + "ProgramData", "Autodesk", "RVT 2026",
                              "Family Templates", "x.rft"))
        with pytest.raises(SA.StandaloneError, match="research-machine input"):
            open(os.path.join(ROOT, "extracted", "racbasicsampleproject",
                              "Formats__Latest.gz", "000.bin"), "rb")
    finally:
        SA.allow_research_inputs()               # never poison later tests


@pytest.mark.skipif(not os.path.isdir(os.path.join(ROOT, "vendor")),
                    reason="research machine only")
def test_family_donor_escape_hatch_routes_to_user_file():
    """--family-donor: a USER-SUPPLIED .rfa provides container+schema at
    runtime (hidden escape hatch; never required, never advertised)."""
    donor = os.path.join(ROOT, "vendor", "phi-ag-rvt", "examples", "Autodesk",
                         "racbasicsamplefamily-2026.rfa")
    if not os.path.isfile(donor):
        pytest.skip("no donor .rfa on this machine")
    from rvt.frontdoor import standalone as SA
    from rvt.famgen import factory as F
    prod = F.make_panelboard(mains_a=225, spaces=30, voltage="480Y/277",
                             mcb=False, panel_name="HATCH", start_id=1000)
    import tempfile
    out = os.path.join(tempfile.mkdtemp(prefix="tekton-hatch-"), "hatch.rfa")
    rep = SA.standalone_family_write(prod, out, family_donor=donor)
    assert rep["container_mode"] == "user-donor"
    assert rep["container_source"] == donor
    assert rep["ok"] is True, rep.get("validate")
