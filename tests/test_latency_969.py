"""#969: the 6-panel job's stages F and L got cheaper without moving a byte.

Each saving replaces a computation with one that must give the SAME answer;
these tests pin the answer AND the mechanism:

* ``skeleton.shared_record_cache``: inside the scope, documents share their
  encoded records -- every document's segments equal its uncached encode, the
  second near-identical document encodes only the records the first did not
  have, a changed record is re-encoded, a new encoder empties the rows, and the
  rows are gone when the outermost scope closes;
* ``adocument.decode_latest_shared``: outside a ``shared_latest_decodes``
  scope it is ``decode_latest``; inside, one decode per distinct payload (the
  same object back, equal to a fresh decode), a bounded LRU, and a different
  schema or element-id width is a different row;
* ``emit_family_rfa_v2(verify=False)`` leaves the read-back to the caller and
  ``standalone_family_write`` reports the verification ``emit`` itself would
  have made, with the file bytes unchanged;
* ``validate_family`` reads the file ONCE for its two validator runs and
  reports exactly what two independent ``validate_file`` runs report.
"""
from __future__ import annotations

import hashlib
import os

import pytest

from rvt import adocument as A
from rvt import encode as E
from rvt import validate as V
from rvt.container import open_rvt
from rvt.famgen import factory as F
from rvt.famgen import famdoc_adoc as FA
from rvt.famgen import skeleton as SK
from rvt.genesis import skeleton as GSK


def _sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _panel(name):
    d = F.make_panelboard(name=name).doc
    d.finalize()
    return d


class _Counting:
    """Count ObjectEncoder.encode_object / encode_record calls (= records encoded afresh).
    Patched on the CLASS, never as instance attributes: an instance attribute left on the
    shared encoder would shadow the 2023 era's class-level encode_record swap (records32)."""

    def __init__(self, monkeypatch):
        self.n = 0
        for name in ("encode_object", "encode_record"):
            orig = getattr(E.ObjectEncoder, name)

            def wrap(enc, *a, _orig=orig, **k):
                self.n += 1
                return _orig(enc, *a, **k)
            monkeypatch.setattr(E.ObjectEncoder, name, wrap)


# -- the shared record memo ------------------------------------------------------------

def test_shared_segments_are_each_documents_own_uncached_segments():
    a, b = _panel("L969 A"), _panel("L969 B")
    want = [SK.build_unit_segments(a.elements), SK.build_unit_segments(b.elements)]
    with SK.shared_record_cache():
        got = [SK.build_unit_segments(a.elements, cache={}),
               SK.build_unit_segments(b.elements, cache={})]
    assert got == want


def test_the_second_document_encodes_only_what_the_first_did_not_have(monkeypatch):
    a, b = _panel("L969 C"), _panel("L969 D")
    n_records = sum(1 for e in b.elements for _r in e.records(class_ids=GSK._SCHEMA_CACHE["enc"].class_id_of))
    alone = _Counting(monkeypatch)
    SK.build_unit_segments(b.elements, cache={})
    encoded_alone = alone.n
    assert encoded_alone >= n_records * 0.9          # without the scope: (nearly) everything afresh
    shared = _Counting(monkeypatch)
    with SK.shared_record_cache():
        SK.build_unit_segments(a.elements, cache={})
        first = shared.n
        SK.build_unit_segments(b.elements, cache={})
        second = shared.n - first
    # the two panelboards differ in their name (and what derives from it): most records are shared
    assert 0 < second < encoded_alone / 4, (first, second, encoded_alone)


def test_a_changed_record_is_re_encoded_not_served_from_another_document():
    a, b = _panel("L969 E"), _panel("L969 E")       # identical content
    victim = next(e for e in b.elements if isinstance(e.obj, dict) and e.obj)
    key = next(k for k, v in victim.obj.items() if isinstance(v, (int, float)) and not isinstance(v, bool))
    victim.obj[key] = victim.obj[key] + 1
    want = SK.build_unit_segments(b.elements)
    with SK.shared_record_cache():
        SK.build_unit_segments(a.elements, cache={})
        assert SK.build_unit_segments(b.elements, cache={}) == want


def test_a_new_encoder_empties_the_shared_rows_and_the_scope_drops_them():
    a = _panel("L969 F")
    with SK.shared_record_cache():
        with SK.shared_record_cache():               # nested: the outer scope's rows
            SK.build_unit_segments(a.elements, cache={})
        rows = SK._SHARED_RECORDS["rows"]
        assert rows                                  # filled, still open after the inner scope
        assert SK._shared_rows(object(), E.Writer.element_id) is rows and not rows
    assert SK._SHARED_RECORDS["rows"] is None and SK._SHARED_RECORDS["depth"] == 0


def test_without_a_per_document_cache_nothing_is_shared():
    a = _panel("L969 G")
    with SK.shared_record_cache():
        SK.build_unit_segments(a.elements)           # no cache= -> the plain encode, no rows
        assert SK._SHARED_RECORDS["rows"] == {}


# -- one decode of a Global/Latest payload per job --------------------------------------

@pytest.fixture(scope="module")
def written(tmp_path_factory):
    path = str(tmp_path_factory.mktemp("l969") / "p.rfa")
    F.make_panelboard(name="M969").write(path)
    return path


@pytest.fixture(scope="module")
def latest(written):
    with open_rvt(written) as f:
        return f.inflate("Global/Latest")


def test_outside_a_scope_every_call_decodes_afresh(latest):
    x, y = A.decode_latest_shared(latest), A.decode_latest_shared(latest)
    assert x is not y and x.value == y.value == A.decode_latest(latest).value


def test_inside_a_scope_one_decode_per_payload(latest, monkeypatch):
    calls = []
    orig = A.decode_latest
    monkeypatch.setattr(A, "decode_latest", lambda p, d=None: calls.append(1) or orig(p, d))
    fresh = orig(latest)
    with A.shared_latest_decodes():
        first = A.decode_latest_shared(latest)
        with A.shared_latest_decodes():              # nested scopes share the outer rows
            again = A.decode_latest_shared(bytes(bytearray(latest)))   # equal bytes, another object
    assert first is again and len(calls) == 1
    assert (first.value, first.clean, first.trailer) == (fresh.value, fresh.clean, fresh.trailer)
    assert A._SHARED_LATEST["rows"] is None


def test_the_memo_is_a_bounded_lru(latest):
    other = latest[:-4] + b"\x00\x00\x00\x00" if latest[-4:] != b"\x00\x00\x00\x00" else latest + b"\x00"
    third = latest + b"\x01"
    with A.shared_latest_decodes():
        a = A.decode_latest_shared(latest)
        A.decode_latest_shared(other)
        assert A.decode_latest_shared(latest) is a   # hit; now most recent
        A.decode_latest_shared(third)                # evicts `other`, keeps `latest`
        assert len(A._SHARED_LATEST["rows"]) == A.SHARED_LATEST_SLOTS
        assert A.decode_latest_shared(latest) is a


def test_another_schema_or_id_width_is_another_row(latest, monkeypatch):
    with A.shared_latest_decodes():
        a = A.decode_latest_shared(latest)
        monkeypatch.setattr(A, "_DECODER", A.ADocumentDecoder(A.get_decoder().schema))
        assert A.decode_latest_shared(latest) is a   # same class + schema + width: same decode
        orig_id = A.Reader.element_id
        monkeypatch.setattr(A.Reader, "element_id", lambda self: orig_id(self))   # same reads, another writer
        b = A.decode_latest_shared(latest)
        assert b is not a and b.value == a.value


# -- the read-back verification inside the checks' decode memo --------------------------

def test_emit_without_verify_leaves_it_to_the_caller(tmp_path):
    from rvt.frontdoor.standalone import bundled_base_path
    donor = bundled_base_path()
    d1, d2 = _panel("L969 H"), _panel("L969 H")
    path = str(tmp_path / "h.rfa")                   # one path: the file records its own name
    e1 = FA.emit_family_rfa_v2(d1, path, donor=donor, timestamp=0, write_reports=False)
    sha1 = _sha(path)
    os.remove(path)
    e2 = FA.emit_family_rfa_v2(d2, path, donor=donor, timestamp=0, write_reports=False, verify=False)
    assert e2["verify"] is None and e1["verify"]["ok"]
    assert _sha(path) == sha1
    assert SK.verify_family_rfa(path) == e1["verify"]


def test_standalone_write_reports_the_verification_emit_would_have_made(tmp_path):
    prod = F.make_panelboard(name="L969 I")
    rep = prod.write(str(tmp_path / "s.rfa"))
    path = rep["path"]
    assert rep["ok"] and rep["verify"] == SK.verify_family_rfa(path)
    assert rep["verify"]["decode_seq102"]["clean"] == rep["verify"]["decode_seq102"]["records"]


# -- validate_family: one walk for both runs --------------------------------------------

def _findings(rep):
    return [(f.severity, f.layer, f.where, f.message) for f in rep.findings]


def test_validate_family_reads_the_file_once_and_reports_two_independent_runs(written, monkeypatch):
    walks = []
    orig_walk = V.walk_file
    monkeypatch.setattr(V, "walk_file", lambda p, **k: walks.append(p) or orig_walk(p, **k))
    opens = []
    orig_open = V.olefile.OleFileIO
    monkeypatch.setattr(V.olefile, "OleFileIO", lambda *a, **k: opens.append(a) or orig_open(*a, **k))
    got = SK.validate_family(written)
    n_shared = len(opens)
    opens.clear()
    raw, fam = V.validate_file(written), V.validate_file(written, family=True)   # the two runs, unshared
    # one walk, and one CFB read of the streams for both runs instead of one per run
    assert walks == [written] and n_shared == len(opens) - 1, (n_shared, len(opens))
    monkeypatch.undo()
    assert got["family_mode"]["n_errors"] == sum(1 for f in fam.findings if f.severity == V.SEV_ERROR)
    w = V.walk_file(written)
    try:
        assert _findings(V.validate_file(written, walked=w)) == _findings(raw)
        assert _findings(V.validate_file(written, family=True, walked=w)) == _findings(fam)
    finally:
        w.close()
    assert got["project_mode"]["stats"] == dict(raw.stats) and got["family_mode"]["stats"] == dict(fam.stats)


def test_validate_family_on_a_non_container_still_reports(tmp_path):
    bad = tmp_path / "junk.rfa"
    bad.write_bytes(b"not a compound file")
    got = SK.validate_family(str(bad))
    assert got["ok"] is False and got["family_mode"]["verdict"] == "INVALID"


def test_this_module_runs_the_worktree_engine():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assert os.path.abspath(A.__file__).startswith(os.path.join(here, "src"))
