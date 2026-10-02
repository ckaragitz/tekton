"""The partition TAIL law of a project load (#938).

#939 found nested family hosts carrying the host's old final-block CRCIO parity
as content after the family end record.  The project loaders had the same
defect, twice per load: pass 1 (``commit_new_elements``) re-framed the host's
de-paged tail (exact tail + final-block parity) and pass 2 re-read the pass-1
file de-paged (+ its parity).  Measured on the bundled certified bases: +660 B
(2026), +1,051 B (2025), +645 B (2024) after the end record per load.

The law pinned here (``rvt.partition_tail``): a load never changes the host's
tail -- the written partition's exact content after the end offset equals the
HOST's, byte for byte.  Not "ends exactly on the end record": the certified
composed bases themselves carry 1,272 / 2,116 / 1,252 B after it (accumulated
in their composition and certified that way), and a Revit-born project ends on
it with 0 B (``docs/writer/content-splice.md`` row 11), so keeping the host's
tail is the one rule that holds for both.  ``verify_loaded_projects`` /
``famload.verify_loaded_project`` check it on every load.

Nothing here claims Revit behaviour (hard rule 4): the fixed outputs differ
from the earlier ones only by the dropped stale bytes, and no viewer round has
been run on them.
"""
from __future__ import annotations

import os
from contextlib import ExitStack

import pytest

from conftest import context_constants, ladder_constants, partition_of, rewrite_stream

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(ROOT, "plugin", "assets", "genesis")
BASES = {2026: os.path.join(GEN, "G_ABPD.rvt"),
         2025: os.path.join(GEN, "G_ABPD_2025.rvt"),
         2024: os.path.join(GEN, "G_ABPD_2024.rvt")}
#: bytes after the 10-byte end record in each certified base's EXACT partition
#: (measured; the lineage's own tail, which every load must keep)
BASE_STRAY = {2026: 1272, 2025: 2116, 2024: 1252}

# loads enter the host's release context in-process and reads climb the
# read-side ladder: conftest's guard watches both (#707)
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
def _warm_native_codecs(tmp_path_factory):
    """The first native load in a process seeds the lazy codec singletons
    (the default ADocument decoder, the genesis type state); do it once before
    the guard's first snapshot so the guard sees only real leaks."""
    from rvt.famgen import loader as L
    out = str(tmp_path_factory.mktemp("t938w") / "w.rvt")
    assert L.load_family_into_project(BASES[2026], out, place=False, validate=False).ok


def _tail(path):
    """(exact tail, the release's end record) of ``path``'s partition, read
    under the file's own release."""
    from rvt.famgen import famdoc_adoc as FDA
    from rvt.global_framing import enter_own_release
    from rvt.partition_tail import host_tail
    with ExitStack() as st:
        enter_own_release(st, path)
        return host_tail(path), FDA.FAMILY_END_RECORD


def _check(path, expected=None):
    from rvt.global_framing import enter_own_release
    from rvt.partition_tail import check_tail
    with ExitStack() as st:
        enter_own_release(st, path)
        return check_tail(path, expected)


@pytest.mark.parametrize("release", [2026, 2025, 2024])
def test_certified_base_carries_its_lineage_tail(release):
    """The certified bases start their tail on the end record and carry a
    lineage tail after it (not a born law: Revit-born streams end on it)."""
    tail, end = _tail(BASES[release])
    assert tail.startswith(end)
    assert len(tail) - len(end) == BASE_STRAY[release]
    rep = _check(BASES[release])
    assert rep["ok"] and rep["stray_bytes"] == BASE_STRAY[release]


@pytest.mark.parametrize("release", [2026, 2025, 2024])
def test_project_load_keeps_the_host_tail(release, tmp_path):
    """The component loader into each bundled base: the written tail equals
    the host's byte for byte, the stale parity is dropped, and the verifier
    judged it."""
    from rvt.famgen import loader as L
    out = str(tmp_path / f"load_{release}.rvt")
    res = L.load_family_into_project(BASES[release], out, place=False, validate=False)
    assert res.ok, res.stop_reason
    pt = res.proofs["partition_tail"]
    # since #941 pass 1 (commit_new_elements) reads the host exactly, so pass
    # 2 finds no stale suffix left to drop
    assert pt["kept_host_tail"] and pt["stale_bytes_dropped"] == 0, pt
    vt = res.proofs["verify_written"]["partition_tail"]
    host, _end = _tail(BASES[release])
    got, _ = _tail(out)
    assert got == host
    rep = _check(out, host)
    assert rep["ok"] and rep["equals_host_tail"], rep
    assert vt["ok"] and vt["equals_host_tail"], vt


def test_chained_and_batch_loads_do_not_grow_the_tail(tmp_path):
    """A load into a loaded project, and a batch of two, keep the BASE's tail:
    no generation accumulates."""
    from rvt.famgen import loader as L
    from rvt.famgen import factory as F
    base = BASES[2026]
    host, _ = _tail(base)
    one = str(tmp_path / "one.rvt")
    assert L.load_family_into_project(base, one, place=False, validate=False).ok
    two = str(tmp_path / "two.rvt")
    r2 = L.load_family_into_project(
        one, two, F.make_archetype(product="wireway",
                                   start_id=L.survey_host(one).watermark + 1),
        place=False, validate=False)
    assert r2.ok, r2.stop_reason
    assert _tail(two)[0] == host
    bout = str(tmp_path / "batch.rvt")

    def mk(product):
        return lambda start: F.make_archetype(product=product, start_id=start)
    b = L.load_families_into_project(base, bout, [mk("wireway"), mk("strut_trapeze")],
                                     validate=False)
    assert b.ok, b.stop_reason
    assert _tail(bout)[0] == host
    assert b.shared["verify_written"]["partition_tail"]["equals_host_tail"]


def test_four_registry_loader_keeps_the_host_tail(tmp_path):
    """``rvt.famload`` (the add_to_project / .rfa-load lane) obeys the same law."""
    from rvt import famload as FL
    from rvt.famgen import heads as H
    out = str(tmp_path / "head.rvt")
    res = FL.load_family_document(BASES[2026], H.family_load("section_head_open"), out,
                                  name="section_head_open", validate=False)
    assert res.ok, res.stop_reason
    assert res.proofs["partition_tail"]["kept_host_tail"]
    vt = res.proofs["verify_written"]["partition_tail"]
    assert vt["ok"] and vt["equals_host_tail"], vt
    assert _tail(out)[0] == _tail(BASES[2026])[0]


def test_verifier_flags_stale_parity(tmp_path):
    """A loaded file whose partition carries extra bytes after the host tail
    fails the file-level verification by name."""
    from rvt import ecc
    from rvt.famgen import loader as L
    from rvt.partition_tail import exact_tail
    base = BASES[2026]
    good = str(tmp_path / "good.rvt")
    res = L.load_family_into_project(base, good, place=False, validate=False)
    assert res.ok

    def stale(raw):                                     # the old defect: framed tail bytes as content
        ex, _end, _t = exact_tail(raw)
        return ecc.frame_stream(ex + raw[-97:])
    bad = rewrite_stream(good, str(tmp_path / "bad.rvt"), partition_of(good), stale)
    ver = L.verify_loaded_projects(bad, [res.plan], validate=False, host_rvt=base)
    assert not ver["file_ok"]
    assert any(e.startswith("partition tail") for e in ver["file_errors"]), ver["file_errors"]
    assert ver["partition_tail"]["tail_bytes"] == len(_tail(base)[0]) + 97
    # without the host the tail is only judged to start on the end record
    ver2 = L.verify_loaded_projects(bad, [res.plan], validate=False)
    assert ver2["partition_tail"]["ok"] and "expected_tail_bytes" not in ver2["partition_tail"]


def test_unjudgeable_tails_are_reported_not_trimmed():
    """An inexact host tail (None) keeps the pass's exact content whole; a
    stream that is not CRCIO-framed has no exact tail."""
    from rvt import ecc
    from rvt.partition_tail import exact_tail, keep_host_tail
    from rvt.container import open_rvt
    with open_rvt(BASES[2026]) as f:
        raw = f.raw(f.partition_streams()[0])
    ex = ecc.unframe_stream(raw)
    got, rep = keep_host_tail(raw, None)
    assert got == ex and not rep["kept_host_tail"] and rep["stale_bytes_dropped"] == 0
    got, rep = keep_host_tail(raw, b"\x01" * 12)     # a tail the pass does not start with
    assert got == ex and not rep["kept_host_tail"]
    assert exact_tail(b"\x00" * 7) is None
    # a pass stream that is not exactly decodable at all comes back de-paged,
    # whole, never raising (#942 review)
    from rvt.container import depage
    junk = b"\x00" * 7
    got, rep = keep_host_tail(junk, b"")
    assert got == depage(junk) and rep["stale_bytes_dropped"] == 0
    assert "de-paged whole" in rep["why"]
