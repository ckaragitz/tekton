"""test_history_head_guid.py -- ONE engine reader for "the History[0]
episode GUID of a file" (issue #434).

``rvt.stream_encoders.history_head_guid`` replaced three copies (the front
door's identity gate + coherent-GUID commit in ``tools/rvt_job.py``, the
census descent evidence in ``rvt.frontdoor.census``, the MEP minimal commit
in ``rvt.mep.views_spaces``).  Pinned here, on the certified pinned bases
(tracked assets -- fresh-clone safe):

* one reader, one casing: the engine value equals an independent decode of
  ``Global/History`` entry[0], is the canonical lowercase ``str(uuid.UUID)``
  form, equals the pin's own ``BasicFileInfo`` GUID (the L2 save invariant),
  is what the census re-exports, and takes a path or an open document;
* the identity scrub still receives EXACTLY those bytes: a real front-door
  edit of the pin hands ``own_basic_file_info(document_guid=...)`` that very
  string (same type, same case) and the identity gate reads it back coherent.
"""
from __future__ import annotations

import json
import os
import sys
import uuid

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt import stream_encoders as SE                 # noqa: E402
from rvt.frontdoor import census as C                  # noqa: E402
from rvt.frontdoor.release_ctx import release_build_context   # noqa: E402
from conftest import CERTIFIED_YEARS, pinned_base       # noqa: E402  (and the `job` fixture)


def _independent_history0(path: str) -> str:
    """entry[0] of ``Global/History`` by the OTHER route: the container's own
    member scan + ``rvt.content.parse_history`` (not the encoder module)."""
    from rvt.container import open_rvt
    from rvt.content import parse_history
    with open_rvt(path) as f:
        return str(parse_history(f.inflate("Global/History")).document_guid)


def _bfi_guid(path: str) -> str:
    from rvt.container import open_rvt
    with open_rvt(path) as f:
        return str(SE.decode_basic_file_info(f.raw("BasicFileInfo")).get("unique_document_guid") or "")


@pytest.mark.parametrize("year", CERTIFIED_YEARS)
def test_one_reader_one_casing(year):
    pin = pinned_base(year)
    with release_build_context(pin):
        h0 = SE.history_head_guid(pin)
        assert isinstance(h0, str) and h0
        assert h0 == _independent_history0(pin)                  # the same episode, read two ways
        assert h0 == str(uuid.UUID(h0)) == h0.lower()            # THE casing rule: canonical lowercase
        assert h0 == _bfi_guid(pin).lower()                      # L2: BFI document GUID == History[0]
        assert C.history_head_guid is SE.history_head_guid       # the census re-exports, no copy
        from rvt.container import open_rvt
        with open_rvt(pin) as f:                                 # an open document spares the re-open
            assert SE.history_head_guid(f) == h0
    assert SE.history_head_guid(os.path.join(ROOT, "nope", "absent.rvt")) is None   # never raises
    assert SE.history_head_guid(__file__) is None                                    # not a container


def test_argument_contract_and_census_dir():
    """Pin-independent (#451): a path or an ``RvtDocument``, nothing else -- a
    plain binary file object is a caller bug (``TypeError``), not "no History"
    (its ``.raw`` attribute used to satisfy the duck-typed document arm); and
    ``dir(census)`` lists the lazily re-exported name, same object as the engine's."""
    with open(__file__, "rb") as fh, pytest.raises(TypeError):
        SE.history_head_guid(fh)
    with pytest.raises(TypeError):
        SE.history_head_guid(None)
    assert "history_head_guid" in dir(C)
    assert C.history_head_guid is SE.history_head_guid


def test_no_local_copies_remain():
    """The three former call sites import the engine reader; none defines its own."""
    for rel in ("src/rvt/frontdoor/census.py", "tools/rvt_job.py", "src/rvt/mep/views_spaces.py"):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            src = fh.read()
        assert "def history_head_guid" not in src, rel
        assert "stream_encoders import history_head_guid" in src, rel


@pytest.mark.parametrize("year", CERTIFIED_YEARS)
def test_edit_hands_the_identity_scrub_history0_verbatim(job, year, tmp_path, monkeypatch):
    """A real ``rvt_job edit`` of the pin: every ``own_basic_file_info`` call
    receives ``document_guid`` == History[0] exactly (bytes, type, case) --
    what the scrub received before #434 -- and the identity gate reads the
    output back coherent (PASS, our author, GUID == History[0])."""
    import rvt.identity as ID
    pin = pinned_base(year)
    with release_build_context(pin):
        expected = _independent_history0(pin)
    seen = []
    real = ID.own_basic_file_info

    def spy(raw, **kw):
        seen.append(kw.get("document_guid"))
        return real(raw, **kw)

    monkeypatch.setattr(ID, "own_basic_file_info", spy)
    ops = tmp_path / "ops.json"
    ops.write_text(json.dumps({"ops": [{"op": "set-level", "id": 694, "elevation_ft": 12.0}]}))
    out = tmp_path / f"edit{year}.rvt"
    rc = job.main(["edit", pin, "--ops", str(ops), "-o", str(out), "--no-provenance"])
    assert rc == 0
    assert seen and all(g == expected and type(g) is str for g in seen), seen
    man = json.loads((tmp_path / f"edit{year}.rvt.manifest.json").read_text())
    assert man["base"]["history_head_guid"] == expected
    ident = man["gates"]["identity"]
    assert ident["status"] == "PASS", ident["issues"]
    assert ident["history_head_guid"] == expected
    assert ident["identity"]["unique_document_guid"].lower() == expected
    assert ident["identity"]["author"] == ID.DEFAULT_AUTHOR
