"""test_famload_2025.py -- THE 2025 FAMLOAD / INSTANCE LANE (issue #14, gap B).

Before this stream every lane that loads a family into, places on, or edits
an EXISTING Revit-2025 file died on its first partition walk with
``unexpected Partitions header: v=9 cls=0x391`` -- the release build context
existed only around ``build_intent`` (keyed on the resolved BASE), and the
four-registry loader (``rvt.famload``), the component loader
(``rvt.famgen.loader``), ``rvt.convert.add_to_project`` (prompt + the user's
project -- the field workflow) and the ``--rvt --edit`` route all ran with the
native (2026) framing/codecs.  Worse, the release-aware validator counted a
2025 file's ContentDocuments with the 2026 tokens and reported a FALSE
four-registry incoherence on every 2025 file carrying loaded content.

These tests pin the lane end-to-end on the BUNDLED certified 2025 base
(``plugin/assets/genesis/G_ABPD_2025.rvt`` -- in git), so they run in a
fresh clone and in CI: no samples/, no experiments/ ladders.

Run: .venv/bin/python -m pytest tests/test_famload_2025.py -q
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import rvt.versions as V                                   # noqa: E402
from conftest import context_constants, ladder_constants   # noqa: E402
from rvt import partitions as P                            # noqa: E402
from rvt.frontdoor import release_ctx as RC                # noqa: E402

GEN = os.path.join(ROOT, "plugin", "assets", "genesis")
BASE25 = os.path.join(GEN, "G_ABPD_2025.rvt")
BASE26 = os.path.join(GEN, "G_ABPD.rvt")
BASE24 = os.path.join(GEN, "G_ABPD_2024.rvt")

pytestmark = [pytest.mark.skipif(not (os.path.isfile(BASE25) and os.path.isfile(BASE26)
                                      and 2025 in V.SUPPORTED_CREATION_RELEASES),
                                 reason="bundled certified 2025/2026 genesis bases missing"),
              pytest.mark.usefixtures("no_release_leak")]  # every test leaves the process at the native release


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _lane_constants() -> dict:
    """The module singletons this lane's contexts swap, past the framing table conftest's guard always
    watches: the ladder's and the write side's lists, plus the Global-stream tokens, the constructor
    codec state and the family-writer constants this file snapshotted before it took the shared guard."""
    from rvt.famgen import factory as FF, skeleton as FSK
    from rvt.genesis import skeleton as GSK, types as GT
    return dict(ladder_constants(), **context_constants(),
                **{"P.TERMINATOR": P.TERMINATOR, "FF.CD_SEPARATOR": FF.CD_SEPARATOR,
                   "FF.CD_END_RECORD": FF.CD_END_RECORD, "GSK.EMPTY_CONTENT_DOCUMENTS": GSK.EMPTY_CONTENT_DOCUMENTS,
                   "FSK.FOOTER_TAG": FSK.FOOTER_TAG, "GT._STATE": sorted(GT._STATE),
                   "FF.FORMATS_LATEST_SHA256_PREFIX": FF.FORMATS_LATEST_SHA256_PREFIX})


@pytest.fixture
def release_leak_extra():
    """``no_release_leak`` watches everything this lane swaps, not the framing table alone."""
    return _lane_constants


def _assert_2025_file(path: str, *, loaded_families: int) -> dict:
    """The five emission facts of a 2025 output: BasicFileInfo release, the
    pinned 2025 schema aboard, framing clean under 2025 ordinals AND refused
    under the native ones, the release-aware validator VALID with 0 errors,
    and the four registries coherent with ``loaded_families`` documents."""
    from rvt.container import open_rvt
    from rvt.famload import four_registry_census
    from rvt.partitions import StreamWalker
    from rvt.validate import validate_file

    assert V.detect_release(path) == 2025
    assert V.schema_of(path).stats()["sha256"] == V.KNOWN_RELEASES[2025].schema_sha256
    with open_rvt(path) as f:
        pns = f.partition_streams()
        with V.reading(path):
            for pn in pns:
                w = StreamWalker(f.logical(pn), inflate=True, keep_data=False)
                assert not w.errors, (pn, w.errors[:3])
        with pytest.raises(Exception):
            for pn in pns:                    # native (2026) framing must refuse
                StreamWalker(f.logical(pn), inflate=True, keep_data=False)
    rep = validate_file(path)                 # release-aware, NO context around it
    errs = [f"[{x.layer}] {x.where}: {x.message}" for x in rep.errors]
    assert rep.ok and not errs, errs
    census = four_registry_census(path)       # bare: reads under the file's release
    assert census["coherent"], census
    assert census["contentdocs_entries"] == loaded_families, census
    assert census["save_units"] == loaded_families + 1, census
    return census


@pytest.fixture(scope="module")
def added_panel(tmp_path_factory):
    """prompt + the 2025 base -> a 2025 project with ONE generated family
    loaded four-registry and ONE placed instance (rvt.convert.add_to_project,
    called BARE -- the lane enters the host release context itself)."""
    from rvt.convert import add_to_project as ATP
    out = tmp_path_factory.mktemp("atp25")
    rec = ATP.add_to_project("add a 100 A lighting panel", BASE25, str(out))
    return rec


# ---------------------------------------------------------------------------
# the mechanism: rvt.global_framing + host_release_context
# ---------------------------------------------------------------------------

def test_global_framing_tokens_follow_the_release():
    from rvt import global_framing as GF
    from rvt.famgen import factory as FF
    native = GF.tokens()
    assert native["CD_SEPARATOR"] == FF.CD_SEPARATOR          # 2026: identity
    assert native["CD_END_RECORD"] == FF.CD_END_RECORD
    t25 = GF.tokens(V.framing_table(2025))
    assert t25["CD_SEPARATOR"][:2] == bytes.fromhex("9103")   # ContentMarker 0x391
    assert t25["CD_SEPARATOR"][6:8] == bytes.fromhex("9003")  # ContentKey 0x390
    with GF.reading(BASE25) as ords:
        assert ords["CONTAINER_CLASS"] == 0x391 == P.CONTAINER_CLASS
        assert FF.CD_SEPARATOR == t25["CD_SEPARATOR"]
    assert FF.CD_SEPARATOR == native["CD_SEPARATOR"]
    assert P.CONTAINER_CLASS == 0x3A3


def test_content_documents_misparse_without_the_tokens(added_panel):
    """The false-E1 mechanism, pinned: a 2025 ContentDocuments payload read
    with the native tokens yields ZERO entries (no exception); read with the
    file's own tokens it yields the one loaded document."""
    from rvt import global_framing as GF
    from rvt.container import open_rvt
    from rvt.famgen.factory import parse_content_documents
    out = added_panel["files"]["combined"]
    with open_rvt(out) as f:
        payload = b"".join(f.inflate_all("Global/ContentDocuments"))
    entries_native, _tail = parse_content_documents(payload)
    assert entries_native == []
    with GF.bound(V.framing_table(2025)):
        entries_2025, tail = parse_content_documents(payload)
    assert len(entries_2025) == 1 and len(tail) == 14


def test_host_release_context_semantics():
    from rvt import adocument as ADOC
    from rvt.famgen import factory as FF
    # native host: no context at all
    with RC.host_release_context(BASE26) as info:
        assert info is None and RC.active_release() is None
    # 2025 host: keyed on the host, donor = OUR bundled 2025 base, joined on re-entry
    with RC.host_release_context(BASE25) as info:
        assert info["release"] == 2025 and info["keyed_on"] == "host"
        # the base/donor is OUR pinned 2025 base (bundled copy or the ledger
        # path -- same bytes either way), never "whatever the host is"
        from rvt.frontdoor import base as B
        assert B.sha256_of(info["base"]) == B.PIN.release_slot(2025)["sha256"]
        assert info["path"] == os.path.abspath(BASE25)
        assert RC.active_release() == 2025
        assert P.CONTAINER_CLASS == 0x391 and FF.CD_SEPARATOR[:2] == b"\x91\x03"
        assert ADOC._DECODER is not None
        with RC.host_release_context(BASE25) as inner:          # re-entrant join
            assert inner is info
        with RC.release_build_context(BASE25) as inner2:        # build joins host
            assert inner2 is info
        assert RC.active_release() == 2025                       # inner exit kept it
        if os.path.isfile(BASE24):
            with pytest.raises(RC.ReleaseContextError):
                with RC.host_release_context(BASE24):
                    pass
    assert RC.active_release() is None


# ---------------------------------------------------------------------------
# the lanes, called BARE on a 2025 host
# ---------------------------------------------------------------------------

def test_add_to_project_on_the_2025_base(added_panel):
    """prompt + RVT(2025) -> RVT(2025): the field workflow (gap B closed)."""
    rec = added_panel
    assert not rec["errors"], rec["errors"]
    assert rec["target"]["release"] == 2025 and rec["target"]["release_supported"]
    out = rec["files"]["combined"]
    kinds = [c["kind"] for c in rec["created"]]
    assert kinds.count("loaded-family") == 1 and kinds.count("equipment-instance") == 1
    v = rec["validation"]["combined"]["validate"]
    assert v["verdict"] == "VALID" and v["n_errors"] == 0          # in-lane self-check
    census = _assert_2025_file(out, loaded_families=1)              # standalone truth
    guid = rec["created"][kinds.index("loaded-family")]["content_guid"].lower()
    assert census["unit_guids"] == census["contentdocs_guids"] == [guid]
    assert guid in census["familymgr_guids"] and guid in census["contenttable_guids"]


def test_famload_four_registry_loader_on_the_2025_base(tmp_path):
    """rvt.famload (the annotation / four-registry loader) on a 2025 host:
    our constructor-built section head loads coherent, host linkage intact."""
    from rvt import famload as FL
    from rvt.famgen import heads as H
    out = str(tmp_path / "FL25_head.rvt")
    res = FL.load_family_document(BASE25, H.family_load("section_head_open"), out,
                                  name="section_head_open")
    assert res.ok, res.stop_reason
    ver = res.proofs["verify_written"]
    assert ver["registries"]["coherent"] and ver["registries"]["ours_in_all_four"]
    assert ver["host_linkage"]["ok"] and ver["elemtable"]["our_host_ids_present"]
    _assert_2025_file(out, loaded_families=1)


def test_famgen_loader_bare_on_the_2025_base(tmp_path):
    """rvt.famgen.loader (the component loader) called BARE on the 2025 base:
    the flagship generated panelboard loads four-registry coherent and its
    host Family / FamilySymbol decode under the 2025 schema.  (Placement on
    a genesis base goes through the constructed-specimen path -- covered by
    the add_to_project test; the loader's own ``place=True`` clones a host
    instance of the category, which a family-free base never has, on any
    release.)"""
    from rvt.famgen import loader as L
    from rvt.mutate import Document
    out = str(tmp_path / "L25_panel.rvt")
    res = L.load_family_into_project(BASE25, out, place=False, validate=True)
    assert res.ok, res.stop_reason
    _assert_2025_file(out, loaded_families=1)
    with RC.host_release_context(out):
        doc = Document.from_file(out)
        fam = doc.value(res.plan.host_family_id) or {}
        sym = doc.value(res.plan.symbol_id) or {}
    assert fam.get("m_name") and sym, "host Family/FamilySymbol decode under 2025"


def test_edit_route_moves_the_placed_instance_on_a_2025_file(added_panel, tmp_path):
    """--rvt <2025 file> --edit: open/plan/edit/verify under the input's release."""
    import rvt.frontdoor as FD
    src = added_panel["files"]["combined"]
    r = FD.author(rvt=src, edit="move LP-1 to 3,1,0", out=str(tmp_path / "e"))
    assert r.ok, r.errors
    out = r.files["edited"]
    _assert_2025_file(out, loaded_families=1)
    tv = FD.author(rvt=src, edit="move LP-1 to 1,1,0", out=str(tmp_path / "e2"),
                   target_version=2025).manifest.get("target_version") or {}
    assert tv.get("status") == "match" and tv.get("output_release") == 2025


def test_uncertified_release_is_refused_not_guessed(tmp_path):
    """A host whose release cannot be authored into is named, never built on
    with the wrong framing: add_to_project keeps its honest ConvertError."""
    from rvt.convert import add_to_project as ATP
    info = ATP.TargetInfo(path=BASE25, release=2023, release_supported=False,
                          schema_sha256=None, quarantined=False)
    with pytest.raises(ATP.ConvertError):
        ATP.build_into_target(None, info, str(tmp_path))
