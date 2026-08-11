"""test_router_load_release.py -- ``--target-version`` on the family LOAD
routes of the permutation router (issue #242; src/rvt/frontdoor/router.py:
``_resolve_host`` / ``_r_rfa_load`` / ``_r_ifc_family_load``).

The standalone family cells honour the recipient's Revit year since #171;
these are their loaded-project siblings -- rfa[+rvt] -> rvt (famspec lane
and .rfa-path lanes) and the ifc -> rfa -> loaded-rvt chain (``--via
family``).  Proven here on a FRESH CLONE (bundled per-release bases, the
famgen catalog; no samples/, no viewer):

* no ``--rvt``: the host IS the pinned certified base OF THAT RELEASE --
  ``target_version`` 2025 / 2024 deliver a ``.rfa`` AND a loaded ``.rvt``
  that BOTH detect as that year (``rvt.versions.detect_release``), the
  project validates 0 errors under its own release, the four registries are
  coherent, ``route.json.target_version.status == 'match'`` -- for every
  catalog famspec kind and for the standalone-born ``.rfa``-path lane;
* an uncertified (2023) / unknown (2027) year is never refused and never
  silent: loaded onto the default (Revit 2026) base, ``status ==
  'fallback'`` + THE one clear line in the caveats and in ROUTE.md;
* an explicit ``--rvt`` host keeps ITS release (a load cannot transmute the
  host): the block is the edit route's own -- ``detected`` with no flag,
  ``match``, ``match-older``, or ``fallback`` + THE line when the stated
  year cannot open the host -- and the ``.rfa`` emitted beside it at the
  flag's year keeps its own block under ``target_version.rfa``;
* a certified year the family emit cannot run at degrades ONCE: the block,
  the ``.rfa`` and the load host all name the default release (never a
  2026 label on a 2024 file);
* no flag -> today's behaviour (default base, ``unspecified``);
* the ifc -> rfa -> loaded-rvt chain goes through the same resolver (the
  measured downlight archetype needs the family container archetype on
  disk -- owner machine, #94 -- so its end-to-end case self-skips here and
  the fresh-clone case pins that the year is honoured and STATED up to the
  point where the emit stops);
* the CLI (``tools/route.py run --output rvt --rfa FAMSPEC --target-version
  2025 --json``) agrees: exit 0, ONE JSON document.

Run: .venv/bin/python -m pytest tests/test_router_load_release.py -q
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from rvt import versions as V                     # noqa: E402
from rvt.frontdoor import router as R             # noqa: E402
from rvt.frontdoor import release_ctx as RC       # noqa: E402

PY = sys.executable
EXAMPLES = os.path.join(ROOT, "spec", "examples")
FAMSPEC = {k: os.path.join(EXAMPLES, f"famspec-{k}.json")
           for k in ("panelboard", "transformer", "luminaire", "device")}
PRODUCT_IFC = os.path.join(ROOT, "inputs", "ifc", "chicago-plenum-downlight.ifc")
SUPPORTED = sorted(V.SUPPORTED_CREATION_RELEASES)
NATIVE = RC.native_release()
OLDER = [y for y in SUPPORTED if y != NATIVE]           # 2024, 2025


def _base(year: int) -> str:
    from rvt.frontdoor.base import resolve_base
    return resolve_base(target_release=year).path


def _bases_present() -> bool:
    try:
        return all(os.path.isfile(_base(y)) for y in SUPPORTED)
    except Exception:
        return False


def _catalog_ok() -> bool:
    try:
        from rvt.famgen import factory as F
        F.resolve_panelboard_facts("eaton", "pow-r-line", mains_a=225, spaces=42,
                                   voltage="480Y/277", mcb=True, mounting="surface",
                                   panel_name="X")
        return all(os.path.isfile(p) for p in FAMSPEC.values())
    except Exception:
        return False


def _famcontainer_present() -> bool:
    """The measured downlight archetype emits on the family container
    archetype (research corpus) -- absent on a fresh clone (#94)."""
    try:
        from rvt.famgen import famdoc_adoc as FA
        return os.path.isfile(FA.TEMPLATE_DONOR)
    except Exception:
        return False


def _has_numpy() -> bool:
    try:
        import numpy  # noqa: F401
        return True
    except Exception:
        return False


pytestmark = [
    pytest.mark.skipif(not _bases_present(), reason="pinned per-release genesis bases absent"),
    pytest.mark.skipif(not _catalog_ok(), reason="famgen catalog / famspec examples absent"),
    pytest.mark.skipif(len(OLDER) == 0, reason="only one certified release"),
]
needs_product_ifc = pytest.mark.skipif(
    not (os.path.isfile(PRODUCT_IFC) and _has_numpy()), reason="product IFC input or numpy absent")


def _validator_errors(path: str) -> int:
    from rvt.validate import validate_file
    return len(validate_file(path).errors)


def _manifest(res):
    with open(res.manifest_paths["route.json"]) as fh:
        return json.load(fh)


def _assert_loaded_at(res, year: int) -> dict:
    """The famload lane's contract at ``year``: both files ARE that release,
    the project validates 0 errors under it, the four registries cohere."""
    assert res.ok, res.errors + [res.status, res.line]
    assert res.route == "rfa_load"
    rfa, rvt = res.files["rfa"], res.files["loaded_rvt"]
    assert os.path.isfile(rfa) and os.path.isfile(rvt)
    assert V.detect_release(rfa) == year and V.detect_release(rvt) == year, res.releases
    assert res.releases == {"rfa": year, "loaded_rvt": year}, res.releases
    rep = json.load(open(res.files["load_report"]))
    assert rep["ok"] is True
    assert rep["validate_project_mode"]["verdict"] == "VALID"
    assert rep["validate_project_mode"]["n_errors"] == 0
    reg = (rep.get("verify") or {}).get("registries") or {}
    assert reg.get("coherent") is True and reg.get("ours_in_all_four") is True, reg
    assert _validator_errors(rvt) == 0
    assert "project validates 0 errors" in res.status and "Revit" not in res.status
    assert any(s.startswith("PROOF-ONLY") for s in res.stamps)
    return rep


# ---------------------------------------------------------------------------
# no --rvt: the host is THAT release's certified base
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("year", OLDER)
@pytest.mark.parametrize("kind", sorted(FAMSPEC))
def test_famspec_loads_onto_that_releases_base(kind, year, tmp_path):
    res = R.route({"rfa": FAMSPEC[kind]}, "rvt", out=str(tmp_path / "o"), target_version=year)
    _assert_loaded_at(res, year)
    tv = res.target_version or {}
    assert tv.get("requested") == year and tv.get("status") == "match", tv
    assert tv.get("output_release") == year and "rfa" not in tv
    assert [s["stage"] for s in res.steps] == ["release-context", "famspec->rfa",
                                               "rfa-emit", "rfa-load"]
    assert res.steps[0]["release"] == year
    host_cav = [c for c in res.caveats if c.startswith("no host .rvt supplied")]
    assert len(host_cav) == 1 and f"certified Revit {year} genesis base" in host_cav[0]
    assert not any("cannot open" in c for c in res.caveats), res.caveats
    man = _manifest(res)
    assert man["target_version"]["status"] == "match"
    rel = man["release"]
    assert rel["requested"] == year and rel["output"] == year and rel["resolution"] == "match"
    assert "line" not in rel
    with open(res.manifest_paths["ROUTE.md"]) as fh:
        assert f"requested Revit {year} -> output Revit {year} (**match**)" in fh.read()


@pytest.mark.parametrize("year", OLDER)
def test_standalone_born_rfa_path_loads_onto_that_releases_base(year, tmp_path):
    """The .rfa-PATH lane (rvt.convert.rfa_load's id remap + famload): a
    native-born .rfa of ours lands on the Revit-``year`` base under that
    host's release."""
    gen = R.route({"rfa": FAMSPEC["panelboard"]}, "rfa", out=str(tmp_path / "g"))
    assert gen.ok, gen.errors
    assert gen.releases["rfa"] == NATIVE
    res = R.route({"rfa": gen.files["rfa"]}, "rvt", out=str(tmp_path / "o"), target_version=year)
    assert res.ok, res.errors + [res.status, res.line]
    assert [s["stage"] for s in res.steps] == ["rfa-classify", "rfa-born-load"]
    loaded = res.files["loaded_rvt"]
    assert V.detect_release(loaded) == year and res.releases == {"loaded_rvt": year}
    assert "VALID 0 errors" in res.status and _validator_errors(loaded) == 0
    reg = json.load(open(res.files["load_report"]))["proofs"]["verify_written"]["registries"]
    assert reg["coherent"] is True and reg["ours_in_all_four"] is True
    tv = res.target_version or {}
    assert tv.get("requested") == year and tv.get("status") == "match", tv
    assert _manifest(res)["release"]["output"] == year


# ---------------------------------------------------------------------------
# uncertified / unknown year: delivered on the default base + THE line
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("year", [2023, 2027])
def test_uncertified_year_loads_onto_the_default_base_with_the_line(year, tmp_path):
    assert year not in SUPPORTED
    res = R.route({"rfa": FAMSPEC["transformer"]}, "rvt", out=str(tmp_path / "o"),
                  target_version=year)
    _assert_loaded_at(res, NATIVE)                        # rule 1: delivered, not refused
    tv = res.target_version or {}
    assert tv.get("requested") == year and tv.get("status") == "fallback", tv
    assert tv.get("output_release") == NATIVE
    line = str(tv.get("line") or "")
    assert f"target {year} requested" in line and f"your Revit {year} cannot open it" in line
    assert f"this file targets {NATIVE}" in line
    assert "IFC alongside" not in line and "no IFC rides" in line     # a family request
    assert res.caveats.count(line) == 1, "the line rides ONCE as a caveat after delivery"
    assert any(c.startswith("no host .rvt supplied") and f"Revit {NATIVE} genesis base" in c
               for c in res.caveats)
    assert not any(s.get("stage") == "release-context" for s in res.steps)
    man = _manifest(res)
    assert man["release"]["resolution"] == "fallback" and man["release"]["line"] == line
    with open(res.manifest_paths["ROUTE.md"]) as fh:
        md = fh.read()
    assert "(**fallback**)" in md and line in md


# ---------------------------------------------------------------------------
# an explicit --rvt host keeps ITS release; the flag is stated, never silent
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def host_2025(tmp_path_factory):
    """A user's Revit-2025 project: a panelboard famspec loaded onto the 2025
    base (itself a case above) -- the second load goes INTO it."""
    year = max(OLDER)
    res = R.route({"rfa": FAMSPEC["panelboard"]}, "rvt",
                  out=str(tmp_path_factory.mktemp("host")), target_version=year)
    assert res.ok, res.errors + [res.status]
    return {"rvt": res.files["loaded_rvt"], "year": year}


def test_explicit_host_no_flag_is_detected(host_2025, tmp_path):
    hy = host_2025["year"]
    res = R.route({"rfa": FAMSPEC["transformer"], "rvt": host_2025["rvt"]}, "rvt",
                  out=str(tmp_path / "o"))
    assert res.ok, res.errors + [res.status, res.line]
    assert V.detect_release(res.files["loaded_rvt"]) == hy
    assert res.releases == {"rfa": NATIVE, "loaded_rvt": hy}
    assert _validator_errors(res.files["loaded_rvt"]) == 0
    tv = res.target_version or {}
    assert tv.get("status") == "detected" and tv.get("requested") is None, tv
    assert tv.get("input_release") == hy and tv.get("output_release") == hy
    assert f"the loaded output stays Revit {hy}" in tv["note"] and "edited" not in tv["note"]
    assert (tv.get("rfa") or {}).get("status") == "unspecified"      # the .rfa beside: native
    assert any(c.startswith("loaded INTO your --rvt") and f"Revit {hy}" in c for c in res.caveats)
    assert not any("ignored for the LOAD" in c for c in res.caveats)
    rel = _manifest(res)["release"]
    assert rel["resolution"] == "detected" and rel["input_release"] == hy and rel["output"] == hy


def test_explicit_host_older_target_is_stated_with_the_line(host_2025, tmp_path):
    """--target-version 2024 into a 2025 host: the .rfa IS 2024, the loaded
    project stays 2025 and THE line says the recipient's 2024 cannot open it."""
    hy, ty = host_2025["year"], min(OLDER)
    if ty >= hy:
        pytest.skip("needs two certified releases below the native one")
    res = R.route({"rfa": FAMSPEC["transformer"], "rvt": host_2025["rvt"]}, "rvt",
                  out=str(tmp_path / "o"), target_version=ty)
    assert res.ok, res.errors + [res.status, res.line]           # delivered (rule 1)
    assert res.releases == {"rfa": ty, "loaded_rvt": hy}, res.releases
    assert _validator_errors(res.files["loaded_rvt"]) == 0
    tv = res.target_version or {}
    assert tv.get("status") == "fallback" and tv.get("requested") == ty, tv
    assert tv.get("input_release") == hy and tv.get("output_release") == hy
    line = str(tv.get("line") or "")
    assert f"target {ty} requested" in line and f"(Revit {hy})" in line
    assert f"your Revit {ty} cannot open the loaded output" in line and "edit" not in line
    assert line in res.caveats
    rfa_tv = tv.get("rfa") or {}
    assert rfa_tv.get("requested") == ty and rfa_tv.get("status") == "match"
    assert rfa_tv.get("output_release") == ty
    man = _manifest(res)
    assert man["release"]["resolution"] == "fallback" and man["release"]["line"] == line
    with open(res.manifest_paths["ROUTE.md"]) as fh:
        md = fh.read()
    assert f"requested Revit {ty} -> output Revit {hy} (**fallback**)" in md
    assert f"the .rfa beside it: requested Revit {ty} -> output Revit {ty} (**match**)" in md


@pytest.mark.parametrize("ty, status", [(None, "match"), (NATIVE, "match-older")])
def test_explicit_host_matching_or_newer_target(host_2025, tmp_path, ty, status):
    hy = host_2025["year"]
    ty = hy if ty is None else ty
    res = R.route({"rfa": FAMSPEC["device"], "rvt": host_2025["rvt"]}, "rvt",
                  out=str(tmp_path / "o"), target_version=ty)
    assert res.ok, res.errors + [res.status, res.line]
    assert res.releases == {"rfa": ty, "loaded_rvt": hy}, res.releases
    tv = res.target_version or {}
    assert tv.get("status") == status and tv.get("requested") == ty, tv
    assert tv.get("output_release") == hy and "line" not in tv
    assert (tv.get("rfa") or {}).get("output_release") == ty
    assert not any("cannot open" in c for c in res.caveats), res.caveats


def test_explicit_host_on_the_rfa_path_lane(host_2025, tmp_path):
    """The .rfa-PATH lane into --rvt: no family is emitted, so the block is
    the host's alone (no 'rfa' sub-block); a stated older year -> THE line."""
    hy, ty = host_2025["year"], min(OLDER)
    if ty >= hy:
        pytest.skip("needs two certified releases below the native one")
    gen = R.route({"rfa": FAMSPEC["luminaire"]}, "rfa", out=str(tmp_path / "g"))
    assert gen.ok, gen.errors
    res = R.route({"rfa": gen.files["rfa"], "rvt": host_2025["rvt"]}, "rvt",
                  out=str(tmp_path / "o"), target_version=ty)
    assert res.ok, res.errors + [res.status, res.line]
    assert res.releases == {"loaded_rvt": hy} and _validator_errors(res.files["loaded_rvt"]) == 0
    tv = res.target_version or {}
    assert "rfa" not in tv and tv.get("input_release") == hy
    assert tv.get("status") == "fallback" and tv["line"] in res.caveats
    assert "reloaded output" in tv["line"]


# ---------------------------------------------------------------------------
# a certified year THIS emit cannot run at: ONE consistent degrade
# ---------------------------------------------------------------------------

def test_degraded_emit_loads_onto_the_default_base_it_names(tmp_path, monkeypatch):
    """When the family cannot be emitted at a certified year (a class the
    older schema lacks, ...), the block degrades to the default release --
    and so must the LOAD host: never a Revit-2024 project under a block
    that says 2026 (or the reverse)."""
    from rvt.frontdoor import famspec as FS
    year = min(OLDER)
    real_write = FS.write

    def write(prod, path, **kw):
        if RC.active_release() == year:
            raise KeyError(f"SyntheticCell absent from the {year} schema")
        return real_write(prod, path, **kw)

    monkeypatch.setattr(FS, "write", write)
    res = R.route({"rfa": FAMSPEC["transformer"]}, "rvt", out=str(tmp_path / "o"),
                  target_version=year)
    _assert_loaded_at(res, NATIVE)                              # delivered, at ONE release
    tv = res.target_version or {}
    assert tv.get("status") == "fallback" and tv.get("output_release") == NATIVE, tv
    assert "SyntheticCell" in str(tv.get("pending")) and "SyntheticCell" in tv["line"]
    assert tv["line"] in res.caveats
    tried = [s for s in res.steps if s.get("attempt")]
    assert tried and all(f"Revit {year}" in s["attempt"] for s in tried)
    assert any(c.startswith("no host .rvt supplied") and f"Revit {NATIVE} genesis base" in c
               for c in res.caveats)
    assert RC.active_release() is None


# ---------------------------------------------------------------------------
# no flag: today's behaviour, only reported
# ---------------------------------------------------------------------------

def test_no_flag_is_the_default_base_reported(tmp_path):
    res = R.route({"rfa": FAMSPEC["transformer"]}, "rvt", out=str(tmp_path / "o"))
    _assert_loaded_at(res, NATIVE)
    tv = res.target_version or {}
    assert tv.get("requested") is None and tv.get("status") == "unspecified", tv
    assert [s["stage"] for s in res.steps] == ["famspec->rfa", "rfa-emit", "rfa-load"]
    assert not any("cannot open" in c for c in res.caveats)
    assert _manifest(res)["release"].get("ask")
    assert RC.active_release() is None


# ---------------------------------------------------------------------------
# the ifc -> rfa -> loaded-rvt chain (--via family) goes through the same resolver
# ---------------------------------------------------------------------------

@needs_product_ifc
def test_ifc_family_chain_honours_and_states_the_year(tmp_path):
    """End to end where the downlight archetype can be emitted (owner
    machine); on a fresh clone the emit stops on the container gap (#94) --
    by then the facts were measured ONCE (release-independent, outside the
    context), the year resolved, the Revit-2025 context entered and the
    failed attempt kept in the trace -- but NO version story of its own: a
    lane that wrote no file states no 'fallback', promises no IFC alongside
    and copies none (#564), which is what this pins there."""
    year = max(OLDER)
    res = R.route({"ifc": PRODUCT_IFC}, "rvt", via="family", out=str(tmp_path / "o"),
                  target_version=year)
    assert res.route == "ifc_to_rvt"
    stages = [s["stage"] for s in res.steps]
    assert stages[:3] == ["ifc->facts", "facts->json", "release-context"], stages
    assert res.steps[2]["release"] == year and stages.count("ifc->facts") == 1
    tv = res.target_version or {}
    assert tv.get("requested") == year, tv
    assert not any("Traceback" in e for e in res.errors)
    if not _famcontainer_present():
        assert res.ok is False and "family container" in res.status      # #94, pre-existing
        assert tv.get("status") == "match" and "pending" not in tv, tv   # the resolver's block, untouched
        tried = [s for s in res.steps if s.get("attempt")]              # the Revit-N attempt, labelled
        assert tried and tried[-1]["stage"] == "rfa-emit" and tried[-1]["ok"] is False
        assert not any("cannot run at Revit" in c for c in res.caveats) and "ifc" not in res.files
        return
    assert res.ok, res.errors + [res.status, res.line]
    out = int(tv["output_release"])
    assert (tv["status"], out) in (("match", year), ("fallback", NATIVE)), tv
    assert V.detect_release(res.files["rfa"]) == out
    assert V.detect_release(res.files["loaded_rvt"]) == out
    rep = json.load(open(res.files["load_report"]))
    assert rep["ok"] is True and rep["validate_project_mode"]["verdict"] == "VALID"
    if tv["status"] == "fallback":
        assert tv["line"] in res.caveats


# ---------------------------------------------------------------------------
# the CLI agrees: exit 0, ONE JSON document, both files at the year
# ---------------------------------------------------------------------------

def test_cli_route_run_rvt_from_famspec_at_target(tmp_path):
    year = max(OLDER)
    out = tmp_path / "cli"
    cp = subprocess.run([PY, os.path.join(ROOT, "tools", "route.py"), "run",
                         "--output", "rvt", "--rfa", FAMSPEC["panelboard"],
                         "--target-version", str(year), "--out", str(out), "--json"],
                        cwd=ROOT, capture_output=True, text=True, timeout=600)
    assert cp.returncode == 0, cp.stderr[-2000:] + cp.stdout[-2000:]
    doc = json.loads(cp.stdout)                     # exactly one JSON document on stdout
    assert doc["ok"] is True and doc["route"] == "rfa_load"
    assert doc["target_version"]["status"] == "match" and doc["release"]["output"] == year
    assert doc["releases"] == {"rfa": year, "loaded_rvt": year}
    for role in ("rfa", "loaded_rvt"):
        p = doc["files"][role]
        p = p if os.path.isabs(p) else os.path.join(ROOT, p)
        assert V.detect_release(p) == year
