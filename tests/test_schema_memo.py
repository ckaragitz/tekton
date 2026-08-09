"""In-process schema memo (issue #183, perf-schema-memo stream).

``rvt.schema.parse`` is memoized per process by the content sha256 of the
``Formats/Latest`` bytes, and ``rvt.schema_cache`` (the build-time on-disk
cache the plugin ships) fills / consults the SAME memo.  Proven here, all
fresh-clone (the only schema bytes used are the pinned plugin base's own):

* ``parse(b) is parse(b)``; different bytes -> a distinct Schema; junk still
  raises ``ParseError`` (exceptions are never memoized as values);
* N=5 parses of the same bytes run the REAL parser exactly once, and N=5
  cache-served parses (``schema_cache.install``) hit ``load_cache_file``
  exactly once (monkeypatched counters);
* the memo is bounded (``MEMO_MAX``) and evicts oldest-first;
* sharing is safe: two ``ObjectDecoder`` s built on the one memoized schema
  decode the pinned G_ABPD base's ``Global/Latest`` to identical records and
  leave the shared object's shape (class / field / index counts) unchanged;
* the shipped cache payload never carries a caller's ``source`` and
  ``schema_cache.build_cache`` stays byte-identical to the shipped asset,
  whatever the process memoized before with another ``source``.
"""
from __future__ import annotations

import hashlib
import os

import pytest

from rvt import schema as S
from rvt import schema_cache as SC
from rvt.container import open_rvt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "plugin")
BASE = os.path.join(PLUGIN, "assets", "genesis", "G_ABPD.rvt")


@pytest.fixture(scope="module")
def blob() -> bytes:
    with open_rvt(BASE) as f:
        return f.inflate("Formats/Latest", 0)


@pytest.fixture(autouse=True)
def _clean_memo():
    """Every test starts and ends with an empty memo, so ordering never
    matters and nothing leaks to other files."""
    S.memo_clear()
    yield
    S.memo_clear()


@pytest.fixture
def real_parses(monkeypatch) -> list:
    """A list that grows by one every time the REAL byte-level parser runs."""
    runs: list = []
    orig_run = S._Parser.run

    def counting_run(self):
        runs.append(1)
        return orig_run(self)

    monkeypatch.setattr(S._Parser, "run", counting_run)
    return runs


def _shape(s) -> tuple:
    return (len(s.classes), len(s.top_level), len(s.by_id), len(s.by_name),
            sum(len(c.fields) for c in s.classes),
            sum(len(c.guids) for c in s.classes),
            sum(s.desc_hist.values()), sum(s.type_refs.values()),
            len(s.unresolved), s.consumed, s.total_size, s.sha256)


# ---------------------------------------------------------------------------
# identity, distinctness, errors
# ---------------------------------------------------------------------------

def test_same_bytes_same_object(blob):
    a = S.parse(blob, source="first")
    b = S.parse(blob, source="second")
    assert a is b
    assert a.sha256 == hashlib.sha256(blob).hexdigest()
    assert a.source == "first"                 # names the first materialisation
    assert len(a.classes) > 4000 and a.by_id[0x1C].name == "ADocument"


def test_different_bytes_distinct_schema(blob):
    a = S.parse(blob)
    other = blob + b"\x00"                     # one more pad byte: still parses, new digest
    b = S.parse(other)
    assert b is not a
    assert b.sha256 != a.sha256 and b.total_size == a.total_size + 1
    assert len(b.classes) == len(a.classes)
    assert S.parse(other) is b and S.parse(blob) is a


def test_parse_uncached_is_private(blob):
    a = S.parse(blob)
    p = S.parse_uncached(blob, source="mine")
    assert p is not a and p.source == "mine" and _shape(p) == _shape(a)
    assert S.parse(blob) is a                  # the private copy did not displace the memo


def test_junk_still_raises_and_is_not_memoized():
    for _ in range(2):
        with pytest.raises(S.ParseError):
            S.parse(b"definitely not a schema stream")
    assert not S._MEMO


# ---------------------------------------------------------------------------
# exactly-once: the real parser, and the cache-file load
# ---------------------------------------------------------------------------

def test_five_parses_run_the_real_parser_once(blob, real_parses):
    got = [S.parse(blob, source=f"call{i}") for i in range(5)]
    assert len(real_parses) == 1
    assert all(g is got[0] for g in got)


def test_five_cached_parses_load_the_cache_file_once(blob, monkeypatch):
    loads = []
    orig_lcf = SC.load_cache_file

    def counting_lcf(path, source=""):
        loads.append(path)
        return orig_lcf(path, source=source)

    monkeypatch.setattr(SC, "load_cache_file", counting_lcf)
    # install() rebinds S.parse and flags the module; monkeypatch puts both back
    monkeypatch.setattr(S, "parse", S.parse)
    monkeypatch.setattr(S, "_schema_cache_installed", False, raising=False)
    rep = SC.install()
    assert S._schema_cache_installed and rep["dirs"], rep
    got = [S.parse(blob) for _ in range(5)]
    assert len(loads) == 1, loads
    assert all(g is got[0] for g in got)
    assert getattr(got[0], "_from_cache", False) is True      # served from the .tksc
    # ... and the direct load_cached / plain-parser arms see the same object
    assert SC.load_cached(got[0].sha256) is got[0]
    assert S.parse.__name__ == "parse_cached"
    assert S.parse._schema_cache_orig(blob) is got[0]
    assert len(loads) == 1


def test_load_cached_miss_is_not_memoized(tmp_path):
    bogus = "0" * 64
    assert SC.load_cached(bogus, dirs=[str(tmp_path)]) is None
    assert bogus not in S._MEMO


# ---------------------------------------------------------------------------
# bounded
# ---------------------------------------------------------------------------

def test_memo_is_bounded_and_evicts_oldest(monkeypatch):
    monkeypatch.setattr(S, "MEMO_MAX", 3)
    made = []

    def build(tag):
        def _b():
            s = S.Schema()
            s.sha256 = tag
            made.append(tag)
            return s
        return _b

    objs = {d: S.memoized(d, build(d)) for d in ("a", "b", "c")}
    assert list(S._MEMO) == ["a", "b", "c"]
    assert S.memoized("a", build("a")) is objs["a"] and made == ["a", "b", "c"]
    S.memoized("d", build("d"))
    assert list(S._MEMO) == ["b", "c", "d"]            # oldest ("a") evicted
    assert S.memoized("a", build("a")) is not objs["a"]  # rebuilt after eviction
    assert made == ["a", "b", "c", "d", "a"]
    assert S.memoized("zzz", lambda: None) is None and "zzz" not in S._MEMO


# ---------------------------------------------------------------------------
# sharing is safe: decode the pinned base twice on the one memoized schema
# ---------------------------------------------------------------------------

def test_two_documents_share_one_schema_and_decode_identically(blob, real_parses):
    """The real-world pattern: ``Document.from_file`` (``from .schema import
    parse`` inside the function) twice on the pinned base -> ONE real parse,
    both decoders hold the same Schema, every seq-102 record decodes to the
    same value both times, and the shared object's shape is untouched."""
    from rvt.mutate import Document
    schema = S.parse(blob)
    before = _shape(schema)
    d1 = Document.from_file(BASE)
    d2 = Document.from_file(BASE)
    assert len(real_parses) == 1
    assert d1.dec.schema is schema and d2.dec.schema is schema
    ids = sorted(d1.idx[102])
    assert len(ids) > 50 and ids == sorted(d2.idx[102])
    for eid in ids:
        assert d1.class_of(eid) == d2.class_of(eid)
        assert repr(d1.value(eid)) == repr(d2.value(eid)), eid
    assert S.parse(blob) is schema
    assert _shape(schema) == before


# ---------------------------------------------------------------------------
# build_cache is independent of the memo
# ---------------------------------------------------------------------------

def test_cache_payload_never_carries_a_callers_source(blob):
    s = S.parse(blob, source="/some/callers/path.rvt")
    assert SC.schema_to_payload(s)["source"] == ""


def test_build_cache_ignores_a_memoized_source(blob, tmp_path):
    S.parse(blob, source="/some/callers/path.rvt")     # poison the memo's source
    idx = SC.build_cache(PLUGIN, out_dir=str(tmp_path))
    digest = hashlib.sha256(blob).hexdigest()
    mine = tmp_path / (digest + SC.CACHE_EXT)
    shipped = os.path.join(PLUGIN, "assets", "schema_cache", digest + SC.CACHE_EXT)
    assert mine.is_file() and any(e["schema_sha256"] == digest for e in idx["entries"])
    assert mine.read_bytes() == open(shipped, "rb").read()   # byte-identical to the shipped asset
