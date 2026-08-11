"""``rvt.roundtrip.read_entries`` / ``catalog`` take ``str | os.PathLike`` themselves (#693): the ONE ``os.fspath``
sits at the olefile touchpoint, so ``read_streams``, ``rewrite_entries``' ``src`` and
``tests/conftest.twin_partition_entry`` hand their path through untouched.  On the pinned genesis bases
(fresh-clone safe):

* a ``pathlib.Path``, a bare ``__fspath__`` object and the ``str`` give the same entries, field by field, and the
  same catalog;
* anything that is not a path is the ``TypeError`` ``os.fspath`` (and ``open``) give -- the type is pinned, not
  the wording;
* every documented ``rewrite_entries`` use is unchanged with a ``PathLike`` ``src``: same bytes out, ``str`` back,
  the same ``KeyError`` text for a stream the container does not hold;
* ``conftest.twin_partition_entry`` takes the ``PathLike`` too."""
from __future__ import annotations

import dataclasses
import os
from pathlib import Path

import pytest

import conftest as C
from rvt import roundtrip as R


class _Spelled:
    """The least a path can be: an object with ``__fspath__`` and nothing else (no ``__str__`` of its own)."""

    def __init__(self, p: str):
        self._p = p

    def __fspath__(self) -> str:
        return self._p


@pytest.mark.parametrize("spell", [Path, _Spelled], ids=["pathlib", "bare-fspath"])
def test_read_entries_pathlike_equals_str_field_by_field(pin, spell):
    ref = R.read_entries(pin)
    got = R.read_entries(spell(pin))
    assert [dataclasses.astuple(e) for e in got] == [dataclasses.astuple(e) for e in ref]
    meta = R.read_entries(spell(pin), with_data=False)
    assert [dataclasses.replace(e, data=b"") for e in ref] == meta                            # the metadata-only pass too


@pytest.mark.parametrize("spell", [Path, _Spelled], ids=["pathlib", "bare-fspath"])
def test_catalog_pathlike_equals_str(pin, spell):
    ref, got = R.catalog(pin), R.catalog(spell(pin))
    assert got["entries"] == ref["entries"]
    assert got["header"] == ref["header"]
    assert got["file"] == ref["file"] == os.path.abspath(pin)                                # still reported as str


@pytest.mark.parametrize("call", [R.read_entries, R.catalog, R.read_streams], ids=["read_entries", "catalog", "read_streams"])
def test_a_non_path_is_the_typeerror_fspath_gives(call):
    with pytest.raises(TypeError):
        call(object())
    with pytest.raises(TypeError):
        call(5.0)


def test_rewrite_entries_with_a_pathlike_src_is_unchanged(pin, tmp_path):
    a = R.rewrite_entries(pin, tmp_path / "a.rvt", {})
    b = R.rewrite_entries(Path(pin), tmp_path / "b.rvt", {})
    assert type(b) is str and b == str(tmp_path / "b.rvt")                                    # PathLike in, str back
    assert Path(a).read_bytes() == Path(b).read_bytes()
    with pytest.raises(KeyError) as by_str:
        R.rewrite_entries(pin, tmp_path / "never.rvt", {"No/Such": b""})
    with pytest.raises(KeyError) as by_path:
        R.rewrite_entries(Path(pin), tmp_path / "never.rvt", {"No/Such": b""})
    assert by_path.value.args == by_str.value.args                                            # same message, src named
    assert pin in by_path.value.args[0]
    assert not (tmp_path / "never.rvt").exists()


def test_conftest_twin_partition_entry_takes_a_pathlike(pin):
    assert dataclasses.astuple(C.twin_partition_entry(Path(pin))) == dataclasses.astuple(C.twin_partition_entry(pin))
