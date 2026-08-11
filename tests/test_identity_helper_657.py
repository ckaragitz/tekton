"""``rvt.identity.own_streams`` (#657) -- the ONE helper behind the three minimal-commit writers' identity step
(``commit.commit_new_elements``, ``mep.conduit.commit_created``, ``mep.electrical_data.commit_electrical``):

* its contract -- which streams come back for which arguments, how ``BasicFileInfo`` is rewritten (save path =
  the output's basename, username, OUR author placeholder, the document GUID kept by default / fresh or given when
  asked), the increment-table usernames, and "never raises: an unreadable stream is left out with a warning";
* one byte-identity row per writer: the ``BasicFileInfo`` (and increment table) each writer emits equals an in-test
  re-implementation of the block that writer carried before the fold (main @ d0d70af), and no other stream but the
  partition / ``Global/ElemTable`` moves;
* the "never let identity break a commit" contract at all three sites: an undecodable ``BasicFileInfo`` still
  yields a written file, a warning, and the bad stream carried verbatim.

Pinned genesis bases only (fresh-clone safe); foreign pins under ``release_build_context``.  The sha256 table of the
writers' whole outputs before == after the fold (three pins) is in the #657 record."""
from __future__ import annotations

import os
import uuid
import warnings

import pytest

import conftest as C
from rvt import identity as I
from rvt.container import open_rvt
from rvt.frontdoor.release_ctx import release_build_context
from rvt.roundtrip import read_entries
from rvt.stream_encoders import decode_basic_file_info, decode_increment_table

pytestmark = pytest.mark.usefixtures("no_release_leak")

FIXED = uuid.UUID("00000657-0657-4657-8657-000000000657")
BAD_BFI = b"\x00\x01\x02"


@pytest.fixture(scope="module")
def pin() -> str:
    if not C.CERTIFIED_YEARS:
        pytest.skip("no certified pinned base")
    return C.pinned_base(C.FOREIGN_FIRST[0])


@pytest.fixture
def fixed_uuid4(monkeypatch):
    monkeypatch.setattr(uuid, "uuid4", lambda: FIXED)
    return str(FIXED)


def _streams(path) -> dict:
    return {e.path: e.data for e in read_entries(os.fspath(path)) if e.entry_type == "stream"}


def _bfi(path) -> dict:
    return decode_basic_file_info(_streams(path)[I.BFI_STREAM])


# --- the blocks the three writers carried before #657 (main @ d0d70af), re-implemented verbatim -------------------

def old_commit_bfi(bfi: bytes, out_path: str, identity=None) -> bytes:          # commit.py step 3
    cur = decode_basic_file_info(bfi).get("unique_document_guid")
    ident = dict(identity or {})
    ident.setdefault("document_guid", cur)
    return I.own_basic_file_info(bfi, out_path=out_path, **ident)


def old_commit_increment_table(src: str, identity=None) -> bytes:               # commit.py step 3b
    with open_rvt(src) as d:
        pref = d.prefix(I.INCREMENT_TABLE_STREAM)
        infl = d.inflate(I.INCREMENT_TABLE_STREAM, 0)
        raw = d.raw(I.INCREMENT_TABLE_STREAM)
    return I.own_increment_table_stream(raw, pref, infl, username=(identity or {}).get("username", ""))


def old_conduit_bfi(bfi: bytes, out_path: str) -> bytes:                        # mep/conduit.py::commit_created
    cur = decode_basic_file_info(bfi).get("unique_document_guid")
    return I.own_basic_file_info(bfi, out_path=out_path, document_guid=cur)


def old_electrical_bfi(bfi: bytes, out_path: str, identity=None) -> bytes:      # mep/electrical_data.py (own_identity)
    return I.own_basic_file_info(bfi, out_path=out_path, **(identity or {}))


# --- (1) the helper's contract ------------------------------------------------------------------------------------

def test_default_returns_only_basicfileinfo_with_our_identity_and_the_document_guid_kept(pin, tmp_path):
    out = str(tmp_path / "kept.rvt")
    with release_build_context(pin), open_rvt(pin) as d:
        got = I.own_streams(d, out)
        raw = d.raw(I.BFI_STREAM)
    assert set(got) == {I.BFI_STREAM}
    before, after = decode_basic_file_info(raw), decode_basic_file_info(got[I.BFI_STREAM])
    assert after["unique_document_guid"] == before["unique_document_guid"] == after["central_episode_guid"]
    assert after["last_save_path"] == "kept.rvt"
    assert after["username"] == ""
    assert after["author"] == after["client_app_name"] == I.PRODUCT_AUTHOR_PLACEHOLDER
    assert after["build"] == before["build"]                                   # the version marker stays
    assert after["unique_document_increments"] == before["unique_document_increments"]
    assert got[I.BFI_STREAM] == old_commit_bfi(raw, out) == old_conduit_bfi(raw, out)


def test_keep_document_guid_false_takes_a_fresh_guid_the_electrical_policy(pin, tmp_path, fixed_uuid4):
    out = str(tmp_path / "fresh.rvt")
    with release_build_context(pin), open_rvt(pin) as d:
        got = I.own_streams(d, out, identity={"username": "u657"}, keep_document_guid=False)
        raw = d.raw(I.BFI_STREAM)
    m = decode_basic_file_info(got[I.BFI_STREAM])
    assert m["unique_document_guid"] == fixed_uuid4 != decode_basic_file_info(raw)["unique_document_guid"]
    assert m["username"] == "u657"
    assert got[I.BFI_STREAM] == old_electrical_bfi(raw, out, {"username": "u657"})


@pytest.mark.parametrize("keep", [True, False])
def test_an_explicit_document_guid_wins_either_way(pin, tmp_path, keep):
    ident = {"document_guid": str(FIXED), "username": ""}
    with release_build_context(pin), open_rvt(pin) as d:
        got = I.own_streams(d, str(tmp_path / "x.rvt"), identity=ident, keep_document_guid=keep)
        raw = d.raw(I.BFI_STREAM)
    assert decode_basic_file_info(got[I.BFI_STREAM])["unique_document_guid"] == str(FIXED)
    assert got[I.BFI_STREAM] == old_commit_bfi(raw, str(tmp_path / "x.rvt"), ident) \
        == old_electrical_bfi(raw, str(tmp_path / "x.rvt"), ident)
    assert ident == {"document_guid": str(FIXED), "username": ""}              # the caller's dict is not written to


def test_increment_table_rewrites_every_save_episode_username(pin, tmp_path):
    with release_build_context(pin), open_rvt(pin) as d:
        got = I.own_streams(d, str(tmp_path / "dit.rvt"), identity={"username": "u657"}, increment_table=True)
        assert set(got) == {I.BFI_STREAM, I.INCREMENT_TABLE_STREAM}
        assert got[I.INCREMENT_TABLE_STREAM] == old_commit_increment_table(pin, {"username": "u657"})
        out = C.rewrite_streams(pin, tmp_path / "dit.rvt", dict(got))
        with open_rvt(out) as o:
            rows = decode_increment_table(o.inflate(I.INCREMENT_TABLE_STREAM, 0))
    names = [r["username"] for k in ("records", "records2") for r in rows.get(k) or []
             if isinstance(r, dict) and "username" in r]
    assert names and set(names) == {"u657"}


def test_never_raises_an_undecodable_basicfileinfo_is_left_out_with_a_warning_and_the_table_still_comes(pin, tmp_path):
    bad = C.rewrite_stream(pin, tmp_path / "bad.rvt", I.BFI_STREAM, lambda raw: BAD_BFI)
    with release_build_context(pin), open_rvt(bad) as d:
        with pytest.warns(UserWarning, match=r"^identity scrub skipped: "):
            got = I.own_streams(d, "x.rvt", increment_table=True)
    assert set(got) == {I.INCREMENT_TABLE_STREAM}


def test_never_raises_a_document_without_the_streams(pin, tmp_path):
    headless = C.rewrite_streams(pin, tmp_path / "headless.rvt", {I.BFI_STREAM: None, I.INCREMENT_TABLE_STREAM: None})
    with release_build_context(pin), open_rvt(headless) as d:
        with warnings.catch_warnings():
            warnings.simplefilter("error")                                     # no BasicFileInfo: silent, nothing to own
            assert I.own_streams(d, "x.rvt") == {}
        with pytest.warns(UserWarning, match=r"^increment-table identity scrub skipped: "):
            assert I.own_streams(d, "x.rvt", increment_table=True) == {}


# --- (2) the three writers: byte identity of what they emit vs the pre-fold blocks, on every certified pin ---------

def _element(base):
    """One deterministic new host-document element on ``base`` (a level work plane) + its framed records."""
    from rvt.mep.devices import add_level_datum_plane
    from rvt.mutate import Document
    doc = Document.from_file(base)
    el = add_level_datum_plane(doc, doc.levels()[0]["id"], (1.0, 2.0))
    return doc, el, dict(doc.serialize(el))


def _only_these_moved(base, out, moved: set) -> dict:
    b, o = _streams(base), _streams(out)
    assert set(b) == set(o)
    assert {k for k in b if b[k] != o[k]} == moved
    return o


@pytest.mark.parametrize("year", C.CERTIFIED_YEARS)
def test_commit_new_elements_owns_basicfileinfo_and_the_increment_table_exactly_as_before(year, tmp_path):
    from rvt.commit import commit_new_elements
    base = C.pinned_base(year)
    out = str(tmp_path / "S1.rvt")
    ident = {"username": ""}
    with release_build_context(base):
        doc, el, recs = _element(base)
        rep = commit_new_elements(base, out, [recs], [el.elemrec], identity=ident)
        o = _only_these_moved(base, out, {rep.partition, "Global/ElemTable", I.BFI_STREAM, I.INCREMENT_TABLE_STREAM})
        assert o[I.INCREMENT_TABLE_STREAM] == old_commit_increment_table(base, ident)
    assert o[I.BFI_STREAM] == old_commit_bfi(_streams(base)[I.BFI_STREAM], out, ident)
    assert _bfi(out)["unique_document_guid"] == _bfi(base)["unique_document_guid"]


@pytest.mark.parametrize("year", C.CERTIFIED_YEARS)
def test_conduit_commit_created_owns_basicfileinfo_exactly_as_before(year, tmp_path):
    from rvt.mep.conduit import ConduitPlan, commit_created
    base = C.pinned_base(year)
    out = str(tmp_path / "S7.rvt")
    with release_build_context(base):
        doc, el, _ = _element(base)
        rep = commit_created(base, out, doc, [ConduitPlan("conduit", curves=[el])])
    o = _only_these_moved(base, out, {rep["partition"], "Global/ElemTable", I.BFI_STREAM})
    assert o[I.BFI_STREAM] == old_conduit_bfi(_streams(base)[I.BFI_STREAM], out)


@pytest.mark.parametrize("year", C.CERTIFIED_YEARS)
def test_commit_electrical_touches_no_identity_stream_unless_asked_and_then_exactly_as_before(year, tmp_path, fixed_uuid4):
    from rvt.mep.electrical_data import commit_electrical
    base = C.pinned_base(year)
    off, on, given = (str(tmp_path / n) for n in ("S8.rvt", "S8b.rvt", "S8c.rvt"))
    ident = {"username": "u657", "document_guid": str(uuid.UUID(int=657))}
    with release_build_context(base):
        doc, el, _ = _element(base)
        rep = commit_electrical(base, off, doc, new_elements=[el])
        commit_electrical(base, on, doc, new_elements=[el], own_identity=True)
        commit_electrical(base, given, doc, new_elements=[el], own_identity=True, identity=ident)
    raw = _streams(base)[I.BFI_STREAM]
    _only_these_moved(base, off, {rep.partition, "Global/ElemTable"})
    o = _only_these_moved(base, on, {rep.partition, "Global/ElemTable", I.BFI_STREAM})
    assert o[I.BFI_STREAM] == old_electrical_bfi(raw, on)
    assert _bfi(on)["unique_document_guid"] == fixed_uuid4                     # this site's policy: a FRESH guid
    o = _only_these_moved(base, given, {rep.partition, "Global/ElemTable", I.BFI_STREAM})
    assert o[I.BFI_STREAM] == old_electrical_bfi(raw, given, ident)
    assert _bfi(given)["unique_document_guid"] == ident["document_guid"] and _bfi(given)["username"] == "u657"


# --- (3) never let identity break a commit: all three sites -------------------------------------------------------

def test_an_undecodable_basicfileinfo_still_yields_a_written_file_and_a_warning_at_all_three_sites(pin, tmp_path):
    from rvt.commit import commit_new_elements
    from rvt.mep.conduit import ConduitPlan, commit_created
    from rvt.mep.electrical_data import commit_electrical
    bad = C.rewrite_stream(pin, tmp_path / "bad.rvt", I.BFI_STREAM, lambda raw: BAD_BFI)
    with release_build_context(pin):
        doc, el, recs = _element(bad)
        sites = {
            "commit": lambda o: commit_new_elements(bad, o, [recs], [el.elemrec], identity={"username": ""}).partition,
            "conduit": lambda o: commit_created(bad, o, doc, [ConduitPlan("conduit", curves=[el])])["partition"],
            "electrical": lambda o: commit_electrical(bad, o, doc, new_elements=[el], own_identity=True).partition,
        }
        for name, write in sites.items():
            out = str(tmp_path / f"{name}.rvt")
            with pytest.warns(UserWarning, match=r"^identity scrub skipped: "):
                pname = write(out)
            moved = {pname, "Global/ElemTable"} | ({I.INCREMENT_TABLE_STREAM} if name == "commit" else set())
            o = _only_these_moved(bad, out, moved)                             # written; the bad stream carried verbatim
            assert o[I.BFI_STREAM] == BAD_BFI
