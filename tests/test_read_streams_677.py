"""``rvt.roundtrip.read_streams(path)`` (#677) -- the engine's ONE "every stream of a container -> its raw bytes"
census, next to ``read_entries`` / ``catalog``.  Its contract, on the pinned genesis bases (fresh-clone safe):

* ``str`` and ``PathLike`` alike;
* streams only -- the root and every storage dropped -- in ``read_entries`` (stream-id) order, byte for byte what
  ``read_entries`` carries;
* raw = as stored (still paged): equal to ``rvt.container.open_rvt(p).raw(name)`` for every stream of every
  certified pin, an independent reader as oracle;
* ``tests/conftest.streams`` IS this call (not a second copy of it)."""
from __future__ import annotations

from pathlib import Path

import pytest

import conftest as C
from rvt import roundtrip as R
from rvt.container import open_rvt


def test_streams_only_in_read_entries_order_byte_for_byte_pathlike_or_str(pin):
    entries = R.read_entries(pin)                                                           # str
    got = R.read_streams(Path(pin))                                                         # PathLike
    assert {e.entry_type for e in entries if e.path not in got} == {"root", "storage"}      # what is dropped
    assert list(got) == [e.path for e in entries if e.is_stream]                            # order = stream-id order
    assert all(got[e.path] == e.data for e in entries if e.is_stream)


@pytest.mark.parametrize("year", C.CERTIFIED_YEARS)
def test_raw_is_what_the_container_reader_calls_raw(year):
    p = C.pinned_base(year)
    got = R.read_streams(p)
    with open_rvt(p) as doc:
        names = [s.name for s in doc.streams()]
        assert sorted(got) == sorted(names)                                                 # every stream, no storage
        assert all(got[n] == doc.raw(n) for n in names)                                     # raw = still paged


def test_conftest_streams_is_the_engine_call(monkeypatch):
    sentinel = {"Only/Stream": b"\x01"}
    monkeypatch.setattr(R, "read_streams", lambda path: sentinel)
    assert C.streams("any.rvt") is sentinel                                                 # delegates, reads nothing
