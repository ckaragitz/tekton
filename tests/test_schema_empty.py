"""test_schema_empty.py -- ``rvt.schema.parse`` raises its own typed
``ParseError`` for input that holds no class record (issue #569, Refs #533).

A truncated container whose CFB directory survives (``head -c 65536`` of any
pinned base) inflates ``Formats/Latest`` to ``b""``; on ``main`` ``parse``
returned a 0-class ``Schema`` for it and every consumer died somewhere less
legible (``Schema.stats()`` -> ``ValueError: max() arg is an empty
sequence``, ``by_name['ADocument']`` -> ``KeyError``).  Now the parser says
so at the boundary, in one sentence naming the byte count, and:

* a raise is never memoized (the empty digest does not poison the memo);
* real parse failures keep their existing messages (grammar untouched);
* every certified pinned base's schema parses exactly as on ``main`` -- the
  release pin (size / sha256 / class count), and the whole class map equal to
  the shipped ``.tksc`` cache ``main``'s parser wrote (tracked plugin asset);
* the two CLIs that meet a 64 KB truncation report it and keep their exit
  codes: ``tools/rvt_inspect.py`` (exit 1, its shim deleted -- the engine's
  sentence now) and ``python -m rvt.estorage <file> --report`` (exit 1; a
  foreign pin's ``own schema unreadable`` warning names ``ParseError``).

Sample-free (the pinned genesis bases are tracked assets); in the CI shard
via ``tests/ci_shard.d/569-schema-empty.txt``.

Run: .venv/bin/python -m pytest tests/test_schema_empty.py -q
"""
from __future__ import annotations

import hashlib
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from conftest import CERTIFIED_YEARS, load_tool, pinned_base    # noqa: E402
from rvt import schema as S                                    # noqa: E402
from rvt import schema_cache as SC                             # noqa: E402
from rvt import versions as V                                  # noqa: E402
from rvt.container import open_rvt                             # noqa: E402
from rvt.versions._release_schema import verify_schema         # noqa: E402

SENTENCE = "no class records in {n:,} bytes of Formats/Latest (an empty or truncated schema stream)"


def _schema_blob(year: int) -> bytes:
    with open_rvt(pinned_base(year)) as f:
        return f.concat("Formats/Latest")


@pytest.fixture
def trunc64k(tmp_path):
    """path of the 64 KB head of the pinned base of ``year``: opens as CFB,
    every stream broken, ``Formats/Latest`` inflates to nothing."""
    def make(year: int) -> str:
        dst = tmp_path / f"trunc64k_{year}.rvt"
        with open(pinned_base(year), "rb") as fh:
            dst.write_bytes(fh.read(64 * 1024))
        return str(dst)
    return make


# ---------------------------------------------------------------------------
# the parser boundary
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("parse", [S.parse, S.parse_uncached], ids=["memoized", "uncached"])
@pytest.mark.parametrize("blob", [b"", b"\x00", b"\x00" * 8, b"\x00" * 15],
                         ids=["empty", "zero1", "zero8", "zero15"])
def test_no_class_records_is_a_typed_one_sentence_error(parse, blob):
    """Empty input and an all-zero tail shorter than the 16-byte end-of-stream
    sentinel hold no class record: ``ParseError`` at offset 0, naming the
    byte count -- from both the memoized and the private entry point."""
    with pytest.raises(S.ParseError) as ei:
        parse(blob)
    assert (ei.value.offset, ei.value.msg) == (0, SENTENCE.format(n=len(blob)))


def test_a_raise_is_never_memoized():
    S.memo_clear()
    with pytest.raises(S.ParseError):
        S.parse(b"")
    assert hashlib.sha256(b"").hexdigest() not in S._MEMO
    with pytest.raises(S.ParseError):          # asked again: raised again, not served
        S.parse(b"")


@pytest.mark.parametrize("blob, start", [
    (b"\x00" * 16, "parse error at 0x0: bad class name len=0 "),          # long enough to be read as a record
    (b"\x01", "parse error at 0x0: truncated: "),
    (b"\x00\x00\x05", "parse error at 0x2: truncated: "),
    (b"definitely not a schema stream", "parse error at 0x0: class marker != 0 (0x6564) "),
], ids=["zero16", "one-byte", "cut-mid-name", "text"])
def test_real_parse_failures_keep_their_messages(blob, start):
    """The grammar's own failures are untouched: same type, same wording."""
    with pytest.raises(S.ParseError) as ei:
        S.parse_uncached(blob)
    assert str(ei.value).startswith(start), str(ei.value)


def test_a_blob_cut_mid_class_still_raises_truncated():
    """A real schema cut inside its first class record: ``truncated``, as
    before -- not the new sentence (it does hold the start of a record)."""
    blob = _schema_blob(CERTIFIED_YEARS[0])[:40]
    with pytest.raises(S.ParseError) as ei:
        S.parse_uncached(blob)
    assert "truncated" in str(ei.value) and "no class records" not in str(ei.value)


# ---------------------------------------------------------------------------
# every valid schema parses exactly as before
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("year", CERTIFIED_YEARS)
def test_pinned_base_schema_parses_identically_to_main(year):
    """A fresh (uncached) parse of the pin's own schema stream carries the
    release pin (``verify_schema``: size / sha256 / class count / no
    unresolved refs) and equals, field for field, the Schema rebuilt from
    the shipped ``plugin/assets/schema_cache/<sha>.tksc`` -- the class map
    ``main``'s parser wrote (this PR leaves that tracked asset untouched)."""
    rel = V.KNOWN_RELEASES[year]
    s = S.parse_uncached(_schema_blob(year), source=f"pin{year}")
    verify_schema(rel, s)                                        # raises SchemaMismatch
    assert s.consumed + s.trailing_pad == s.total_size and "ADocument" in s.by_name
    shipped = SC.disk_loader(rel.schema_sha256)                  # bypasses the memo: read from disk
    assert shipped is not None, f"no shipped schema cache for Revit {year} ({rel.schema_sha256[:16]}...)"
    assert SC.schema_to_payload(s) == SC.schema_to_payload(shipped)


# ---------------------------------------------------------------------------
# the two CLIs that meet a 64 KB truncation
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def inspect_tool():
    return load_tool("rvt_inspect")


@pytest.mark.parametrize("year", CERTIFIED_YEARS)
def test_rvt_inspect_reports_the_engines_sentence_exit_1(inspect_tool, trunc64k, capsys, year):
    """The stream listing still prints, then ONE line names the engine's
    typed error (the tool's own ``ValueError`` shim is gone); exit 1, no
    traceback, nothing on stderr."""
    rc = inspect_tool.main([trunc64k(year)])
    out, err = capsys.readouterr()
    assert rc == 1 and err == "" and "Traceback" not in out
    assert "streams (" in out
    assert ("\nschema (Formats/Latest): unreadable (ParseError: parse error at 0x0: "
            + SENTENCE.format(n=0) + ") -- nothing below the stream listing can be reported\n") in out
    assert "ValueError" not in out


@pytest.mark.parametrize("year", CERTIFIED_YEARS)
def test_estorage_cli_names_the_typed_error_exit_1(trunc64k, capsys, year):
    """``python -m rvt.estorage <trunc> --report``: exit 1 with the load
    failure in one ERROR line (unchanged); a foreign pin first states the
    release rung it fell back to, and that warning now names ``ParseError``
    and the byte count instead of a by-name ``VersionError`` over an empty
    class map.  A native pin enters nothing, so it prints no warning."""
    from rvt import estorage
    path = trunc64k(year)
    rc = estorage.main([path, "--report"])
    out, err = capsys.readouterr()
    assert rc == 1 and out == "" and "Traceback" not in err
    lines = err.splitlines()
    assert lines[-1].startswith(f"ERROR: cannot load {path}: RuntimeError: ") and "walker errors" in lines[-1]
    if year != V.LATEST_RELEASE:                                 # a foreign pin climbs the ladder
        assert lines[0] == ("warning: own schema unreadable (ParseError: parse error at 0x0: "
                            + SENTENCE.format(n=0) + f"); checked against the pinned Revit {year} "
                            "framing table (the release BasicFileInfo declares)")
        assert len(lines) == 2
    else:
        assert len(lines) == 1
