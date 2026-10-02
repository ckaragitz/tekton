"""The project family loader: unique family names (#937) and a project that
names itself in BasicFileInfo (#928).

#937 -- Revit keeps family names unique per document, yet loading the same
generated family twice into one project wrote two ``Family`` elements with one
name and the file still validated 0 errors.  ``load_family_into_project`` now
refuses the clash with a :class:`FamilyNameClash` before anything is written
(the default, ``on_name_clash="refuse"``); the front-door routes pass
``on_name_clash="rename"`` and load the family as ``"<name> (2)"`` (the first
free number), so a route always delivers a file (hard rule 1) and its record
says what was renamed.

#928 -- pass 1 commits to ``<out>.pass1.tmp`` and ``commit_new_elements``
wrote that temp name into BasicFileInfo's last-save path.  Pass 2 now re-owns
BasicFileInfo against the real output, so the stream is exactly what a direct
``commit_new_elements`` write of ``<out>`` produces.  Measured on all three
bundled bases (single + batched loads): every other stream of a loaded project
is byte-identical to the pre-#928 output; BasicFileInfo differs only in
``last_save_path`` (and its regenerated mirror text).

Nothing here claims Revit behaviour (hard rule 4).
"""
from __future__ import annotations

import ast
import hashlib
import os

import pytest

from conftest import context_constants, ladder_constants

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(ROOT, "plugin", "assets", "genesis")
BASES = {2026: os.path.join(GEN, "G_ABPD.rvt"),
         2025: os.path.join(GEN, "G_ABPD_2025.rvt"),
         2024: os.path.join(GEN, "G_ABPD_2024.rvt")}

#: the flagship product's family name (``load_family_into_project``'s default)
FLAGSHIP = "Panelboard 480Y/277 400A MCB 42ckt Surface"

pytestmark = [pytest.mark.skipif(not all(os.path.isfile(p) for p in BASES.values()),
                                 reason="bundled certified genesis bases missing"),
              pytest.mark.usefixtures("no_release_leak")]


@pytest.fixture
def release_leak_extra():
    from rvt import partitions as P
    from rvt.famgen import factory as FF, skeleton as FSK
    from rvt.genesis import types as GT
    return lambda: dict(ladder_constants(), **context_constants(),
                        **{"P.TERMINATOR": P.TERMINATOR, "FSK.FOOTER_TAG": FSK.FOOTER_TAG,
                           "GT._STATE": sorted(GT._STATE),
                           "FF.FORMATS_LATEST_SHA256_PREFIX": FF.FORMATS_LATEST_SHA256_PREFIX})


@pytest.fixture(scope="module", autouse=True)
def loaded_once(tmp_path_factory):
    """The flagship family loaded once into the 2026 base (also seeds the lazy
    codec singletons before the leak guard's first snapshot)."""
    from rvt.famgen import loader as L
    out = str(tmp_path_factory.mktemp("t937") / "once.rvt")
    res = L.load_family_into_project(BASES[2026], out, place=False, validate=False)
    assert res.ok, res.stop_reason
    return out, res


def _sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _family_names(path):
    from contextlib import ExitStack
    from rvt.families import family_documents
    from rvt.global_framing import enter_own_release
    with ExitStack() as st:
        enter_own_release(st, path)
        return [r["family_name"] for r in family_documents(path)]


def _bfi(path):
    from rvt import stream_encoders as se
    from rvt.container import open_rvt
    from rvt.identity import BFI_STREAM
    with open_rvt(path) as f:
        raw = f.raw(BFI_STREAM)
    return raw, se.decode_basic_file_info(raw)


# ---------------------------------------------------------------------------
# #937 -- family names are unique per document
# ---------------------------------------------------------------------------

def test_resolve_family_name_policies():
    from rvt.famgen import loader as L
    taken = {L._name_key("Panel"): (7, "Panel"), L._name_key("Panel (2)"): (9, "Panel (2)")}
    assert L.resolve_family_name("Other", taken)[0] == "Other"
    with pytest.raises(L.FamilyNameClash, match=r"already holds a family named 'Panel' "
                                                r"\(element 7\)"):
        L.resolve_family_name("Panel", taken)
    with pytest.raises(L.FamilyNameClash):                 # a case-only variant clashes
        L.resolve_family_name("PANEL", taken)
    name, proof = L.resolve_family_name("Panel", taken, on_name_clash="rename")
    assert name == "Panel (3)"                             # first FREE number, deterministic
    assert proof == {"requested": "Panel", "written": "Panel (3)", "policy": "rename",
                     "clash_with": {"family_id": 7, "family_name": "Panel"}}
    with pytest.raises(L.LoaderError, match="on_name_clash"):
        L.resolve_family_name("Panel", taken, on_name_clash="overwrite")
    assert issubclass(L.FamilyNameClash, L.LoaderError)


def test_host_survey_lists_family_names():
    """The survey sees the host's families: none on the 2026 base, the eight
    curtain-wall system families on the 2025 / 2024 bases."""
    from rvt.famgen import loader as L
    assert L.survey_host(BASES[2026], category=None).family_names == {}
    names = L.survey_host(BASES[2025], category=None).family_names
    assert len(names) == 8 and names[L._name_key("Rectangular Mullion")][1] == "Rectangular Mullion"


def test_second_load_of_the_same_family_is_refused_before_any_write(loaded_once, tmp_path):
    from rvt.famgen import loader as L
    once, res = loaded_once
    assert res.proofs["family_name"] == {"requested": FLAGSHIP, "written": FLAGSHIP,
                                         "policy": "refuse", "clash_with": None}
    before = _sha(once)
    twice = str(tmp_path / "twice.rvt")
    with pytest.raises(L.FamilyNameClash) as ei:
        L.load_family_into_project(once, twice, place=False, validate=False)
    assert ei.value.name == FLAGSHIP and ei.value.existing_id == res.plan.host_family_id
    assert FLAGSHIP in str(ei.value)
    assert not os.path.exists(twice)                       # nothing written ...
    assert not os.path.exists(twice + ".pass1.tmp")
    assert _sha(once) == before                            # ... and the project unchanged
    assert _family_names(once) == [FLAGSHIP]


def test_rename_policy_loads_it_as_name_2(loaded_once, tmp_path):
    from rvt.famgen import loader as L
    once, res = loaded_once
    out = str(tmp_path / "renamed.rvt")
    r2 = L.load_family_into_project(once, out, place=False, validate=False,
                                    on_name_clash="rename")
    assert r2.ok, r2.stop_reason
    assert r2.plan.family_name == FLAGSHIP + " (2)"
    assert r2.proofs["family_name"]["clash_with"] == {"family_id": res.plan.host_family_id,
                                                      "family_name": FLAGSHIP}
    assert any("loaded as" in n and "(2)" in n for n in r2.proofs["plan"]["notes"])
    assert sorted(_family_names(out)) == sorted([FLAGSHIP, FLAGSHIP + " (2)"])


def test_batched_loader_names_are_unique_across_the_batch(tmp_path):
    """Two copies of one family in ONE batch: refused at the second (the first
    is written -- the batch's prefix rule), or renamed with ``rename``."""
    from rvt.famgen import loader as L, factory as F

    def flagship(start):
        return F.make_panelboard(vendor="eaton", line="pow-r-line", mains_a=400, spaces=42,
                                 voltage="480Y/277", mcb=True, mounting="surface",
                                 solid=True, start_id=start)
    out = str(tmp_path / "refuse.rvt")
    b = L.load_families_into_project(BASES[2026], out, [flagship, flagship], validate=False)
    assert not b.ok and b.culprit == 1
    assert "FamilyNameClash" in b.stop_reason and FLAGSHIP in b.stop_reason
    assert b.loads[0].ok and _family_names(out) == [FLAGSHIP]
    out2 = str(tmp_path / "rename.rvt")
    b2 = L.load_families_into_project(BASES[2026], out2, [flagship, flagship],
                                      validate=False, on_name_clash="rename")
    assert b2.ok, b2.stop_reason
    assert [r.plan.family_name for r in b2.loads] == [FLAGSHIP, FLAGSHIP + " (2)"]
    assert sorted(_family_names(out2)) == sorted([FLAGSHIP, FLAGSHIP + " (2)"])


def _calls(path, func):
    """Every call of ``*.func(...)`` in ``path``: its keyword -> literal value."""
    with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    out = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == func):
            out.append({k.arg: (k.value.value if isinstance(k.value, ast.Constant) else None)
                        for k in node.keywords})
    return out


@pytest.mark.parametrize("path,func", [
    ("src/rvt/frontdoor/build.py", "load_families_into_project"),    # prompt / IFC build
    ("tools/ifc_intent.py", "load_family_into_project"),             # add_to_project chain
    ("src/rvt/convert/extract_family.py", "load_family_into_project"),  # rfa -> rvt reload
])
def test_frontdoor_routes_rename_rather_than_refuse(path, func):
    """The front door's decision (#937): a route always delivers (hard rule 1),
    so its loads take the deterministic rename and record it."""
    calls = _calls(path, func)
    assert calls and all(c.get("on_name_clash") == "rename" for c in calls), calls


# ---------------------------------------------------------------------------
# #928 -- the loaded project names itself in BasicFileInfo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("release", [2026, 2025, 2024])
def test_loaded_project_records_its_own_file_name(release, tmp_path):
    from rvt.container import open_rvt
    from rvt.famgen import loader as L
    from rvt.identity import BFI_STREAM, own_streams
    out = str(tmp_path / f"loaded_{release}.rvt")
    res = L.load_family_into_project(BASES[release], out, place=False, validate=False)
    assert res.ok, res.stop_reason
    raw, model = _bfi(out)
    assert model["last_save_path"] == f"loaded_{release}.rvt"
    assert b"pass1" not in raw and "pass1".encode("utf-16-le") not in raw
    # exactly what a direct write of ``out`` from this host would carry
    with open_rvt(BASES[release]) as host:
        direct = own_streams(host, out, identity={"username": ""})[BFI_STREAM]
    assert raw == direct
    _hraw, hmodel = _bfi(BASES[release])
    assert model["unique_document_guid"] == hmodel["unique_document_guid"]
