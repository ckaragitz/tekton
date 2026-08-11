"""Tests for rvt.versions -- the multi-version model (MULTI-VERSION PHASE A).

Covers:
* release detection (BasicFileInfo year + Formats/Latest signature)
* the per-release schema handles (schema_2025 / schema_2024): pinned
  size/sha256/class-count, and the load-bearing claim PARSER_DELTAS == ()
  (the 2026 grammar reads every release's schema unmodified)
* by-name framing-ordinal resolution == the precomputed tables (drift is
  asserted, never assumed)
* the reading() context manager: activates a file's ordinals inside
  rvt.partitions, restores the 2026 constants on exit, and makes the
  StreamWalker + a bounded schema-directed object decode work on 2025/2024
  files
* the creation guards: require_creation_release / require_release /
  check_openable (no silent 2026 output for a 2025 target)

The sample-backed tests skip when the quarantined dev samples are absent
(samples are DEV-ONLY and never shipped -- see samples/*/SOURCES.md).
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt import versions as V  # noqa: E402
from rvt.versions import (  # noqa: E402
    KNOWN_RELEASES, NewerFileError, UnknownRelease, UnsupportedTarget,
    VersionError)

S26 = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
S25 = os.path.join(ROOT, "samples", "2025", "rstbasicsampleproject.rvt")
S24 = os.path.join(ROOT, "samples", "2024", "rstbasicsampleproject.rvt")

HAVE_2026 = os.path.isfile(S26)
HAVE_2025 = os.path.isfile(S25)
HAVE_2024 = os.path.isfile(S24)

need26 = pytest.mark.skipif(not HAVE_2026, reason="2026 dev samples absent")
need25 = pytest.mark.skipif(not HAVE_2025, reason="2025 dev samples absent")
need24 = pytest.mark.skipif(not HAVE_2024, reason="2024 dev samples absent")
pytestmark = pytest.mark.usefixtures("no_release_leak")   # the reading() rows enter it in-process: none may leak


# ---------------------------------------------------------------------------
# the release table itself
# ---------------------------------------------------------------------------

def test_known_releases_invariants():
    assert set(KNOWN_RELEASES) >= {2024, 2025, 2026}
    assert V.LATEST_RELEASE == max(KNOWN_RELEASES)
    for year, r in KNOWN_RELEASES.items():
        assert r.year == year
        assert len(r.schema_sha256) == 64
        assert r.schema_size > 400_000
        assert set(r.framing) == set(V.FRAMING_CLASSES)
        # ordinals are u16 class ids
        assert all(0 < v < 0x10000 for v in r.framing.values())
    # class counts grow monotonically with the release year (classes are
    # inserted, which is WHY ordinals drift)
    years = sorted(KNOWN_RELEASES)
    counts = [KNOWN_RELEASES[y].class_count for y in years]
    assert counts == sorted(counts)


def test_creation_certification_is_2026_2025_and_2024():
    assert V.SUPPORTED_CREATION_RELEASES == frozenset({2024, 2025, 2026})
    assert KNOWN_RELEASES[2026].creation_certified
    assert KNOWN_RELEASES[2026].genesis_base
    # G25-5: the Revit 2025 base is certified and pinned
    assert KNOWN_RELEASES[2025].creation_certified
    assert KNOWN_RELEASES[2025].genesis_base
    # the 2024 campaign's tick: G_ABPD_2024 viewer-certified and pinned
    assert KNOWN_RELEASES[2024].creation_certified
    assert KNOWN_RELEASES[2024].genesis_base
    # older releases stay uncertified-guarded
    assert not KNOWN_RELEASES[2023].creation_certified


def test_framing_ordinals_differ_across_releases():
    """The core fact of the version model: NONE of the six framing 'constants'
    is constant across releases."""
    for const in V.FRAMING_CLASSES:
        vals = {KNOWN_RELEASES[y].framing[const] for y in (2024, 2025, 2026)}
        assert len(vals) == 3, f"{const} does not drift?"


def test_framing_table_unknown_release():
    with pytest.raises(UnknownRelease):
        V.framing_table(2019)
    assert V.framing_table(2025)["BLOCK_TAG"] == 0x0ED9


# ---------------------------------------------------------------------------
# guards (no samples needed)
# ---------------------------------------------------------------------------

def test_require_creation_release_2026_ok():
    r = V.require_creation_release(2026)
    assert r.year == 2026 and r.genesis_base


def test_require_creation_release_accepts_2025_2024_refuses_older():
    # G25-5 + the 2024 flip: 2025 and 2024 are certified creation targets now
    for year in (2025, 2024):
        r = V.require_creation_release(year)
        assert r.year == year and r.genesis_base
    # 2023 remains uncertified-guarded
    with pytest.raises(UnsupportedTarget) as ei:
        V.require_creation_release(2023)
    msg = str(ei.value)
    assert "2023" in msg and "genesis" in msg.lower()
    # the refusal must tell the user we will NOT hand over a newer file
    assert "newer" in msg.lower()


def test_require_creation_release_parses_strings():
    assert V.require_creation_release("Revit 2026").year == 2026
    assert V.require_creation_release("Autodesk Revit 2024").year == 2024
    with pytest.raises(UnsupportedTarget):
        V.require_creation_release("Revit 2023")
    with pytest.raises(UnknownRelease):
        V.require_creation_release("not-a-year")


def test_check_openable_refuses_newer_file():
    with pytest.raises(NewerFileError):
        V.check_openable(2026, 2025)          # the exact problem-(C) trap
    V.check_openable(2025, 2025)              # same release: fine
    V.check_openable(2024, 2026)              # older file: fine
    with pytest.raises(UnknownRelease):
        V.check_openable(None, 2025)


def test_require_release_mismatch():
    assert V.require_release(2025, 2025) == 2025
    assert V.require_release(2026, "Revit 2026") == 2026
    with pytest.raises(VersionError):
        V.require_release(2026, 2025, what="genesis base")
    with pytest.raises(UnknownRelease):
        V.require_release(None, 2025)


def test_creation_status_shapes():
    for year in (2026, 2025, 2024):            # 2024 certified at the flip
        ok = V.creation_status(year)
        assert ok["supported"] and ok["base"]
    no = V.creation_status(2023)               # still uncertified-guarded
    assert not no["supported"] and no["have_schema"]
    unk = V.creation_status(2030)
    assert not unk["supported"] and not unk["have_schema"]


# ---------------------------------------------------------------------------
# per-release schema handles
# ---------------------------------------------------------------------------

def test_parser_deltas_are_empty_by_construction():
    """The documented finding: NO schema-parser deltas for 2025/2024.  If a
    future release needs one, it must be added to that release's module AND
    this assertion updated with the evidence."""
    from rvt.versions import schema_2024, schema_2025
    assert schema_2025.PARSER_DELTAS == ()
    assert schema_2024.PARSER_DELTAS == ()
    assert schema_2025.CLASS_COUNT == 4600
    assert schema_2024.CLASS_COUNT == 4492
    assert KNOWN_RELEASES[2026].class_count == 4690


@need25
def test_schema_2025_loads_and_verifies():
    from rvt.versions import schema_2025
    s = schema_2025.load()
    assert schema_2025.verify(s)
    st = s.stats()
    assert st["stream_size"] == schema_2025.EXPECTED_SIZE
    assert st["sha256"] == schema_2025.EXPECTED_SHA256
    assert st["class_count"] == schema_2025.CLASS_COUNT
    assert st["unresolved_refs"] == 0


@need24
def test_schema_2024_loads_and_verifies():
    from rvt.versions import schema_2024
    s = schema_2024.load()
    assert schema_2024.verify(s)
    assert s.stats()["sha256"] == schema_2024.EXPECTED_SHA256


@need25
def test_schema_verify_rejects_wrong_release():
    from rvt.versions import schema_2024, schema_2025
    from rvt.versions._release_schema import SchemaMismatch
    s25 = schema_2025.load()
    with pytest.raises(SchemaMismatch):
        schema_2024.verify(s25)


# ---------------------------------------------------------------------------
# detection + by-name framing (sample-backed)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path,year", [
    pytest.param(S26, 2026, marks=need26),
    pytest.param(S25, 2025, marks=need25),
    pytest.param(S24, 2024, marks=need24),
])
def test_detect_release(path, year):
    assert V.detect_release(path) == year
    r = V.release_of(path)
    assert r is not None and r.year == year


@pytest.mark.parametrize("path,year", [
    pytest.param(S26, 2026, marks=need26),
    pytest.param(S25, 2025, marks=need25),
    pytest.param(S24, 2024, marks=need24),
])
def test_detect_release_from_raw_bfi_bytes(path, year):
    from rvt.container import open_rvt
    with open_rvt(path) as d:
        raw = d.raw("BasicFileInfo")
    assert V.detect_release(raw) == year
    assert V.detect_release_from_bfi(raw) == year


@pytest.mark.parametrize("path,year", [
    pytest.param(S26, 2026, marks=need26),
    pytest.param(S25, 2025, marks=need25),
    pytest.param(S24, 2024, marks=need24),
])
def test_by_name_ordinals_match_the_precomputed_table(path, year):
    """THE cross-check: the table is a cache, the file's own schema is the
    authority -- and they must agree or the model is wrong."""
    sch = V.schema_of(path)
    assert V.ordinals_from_schema(sch) == dict(KNOWN_RELEASES[year].framing)
    assert V.detect_release_from_schema(V.schema_of(path)) == year
    # framing_for cross-checks schema vs table internally
    assert V.framing_for(path) == dict(KNOWN_RELEASES[year].framing)


@need25
def test_describe_reports_release_and_creation():
    d = V.describe(S25)
    assert d["release"] == 2025 and d["known"]
    assert d["schema"]["matches_release_pin"]
    assert d["framing"]["PT_CLASS"] == 0x0C40
    assert d["creation"]["supported"] is True  # 2025 certified at G25-5


# ---------------------------------------------------------------------------
# the reading() context: activation + restoration + a real 2025/2024 read
# ---------------------------------------------------------------------------

def test_reading_requires_a_source():
    with pytest.raises(VersionError):
        with V.reading():
            pass


def test_reading_activates_and_restores_by_year():
    from rvt import partitions as P
    before = (P.BLOCK_TAG, P.TRAILER_TAG, P.FOOTER_TAG,
              P.CONTAINER_CLASS, P.UNIT_INNER_CLASS, P.PT_CLASS, P.TERMINATOR)
    with V.reading(year=2025) as ords:
        assert ords == dict(KNOWN_RELEASES[2025].framing)
        assert P.BLOCK_TAG == 0x0ED9
        assert P.TERMINATOR.startswith(b"\xd9\x0e")
        with V.reading(year=2024):            # nesting
            assert P.BLOCK_TAG == 0x0E7C
        assert P.BLOCK_TAG == 0x0ED9
    after = (P.BLOCK_TAG, P.TRAILER_TAG, P.FOOTER_TAG,
             P.CONTAINER_CLASS, P.UNIT_INNER_CLASS, P.PT_CLASS, P.TERMINATOR)
    assert after == before                    # no leak into the 2026 path


def test_reading_restores_on_exception():
    from rvt import partitions as P
    before = P.BLOCK_TAG
    with pytest.raises(RuntimeError):
        with V.reading(year=2024):
            raise RuntimeError("boom")
    assert P.BLOCK_TAG == before


def _walk_and_decode(path, year, n_records=400):
    """The bounded read-parity probe: block framing + schema-directed decode
    of the first ``n_records`` seq-102 records, all inside reading()."""
    from rvt.container import open_rvt
    from rvt.objects import ObjectDecoder, iter_records
    from rvt.partitions import StreamWalker

    sch = V.schema_of(path)
    dec = ObjectDecoder(sch)
    with V.reading(path, schema=sch):
        with open_rvt(path) as d:
            pnames = d.partition_streams()
            assert pnames, "no Partitions/<N> streams?"
            walked = decoded = failures = blocks = 0
            for pn in pnames:
                w = StreamWalker(d.logical(pn))
                assert not w.errors, f"{pn}: walker errors {w.errors[:2]}"
                blocks += len(w.blocks)
                seg = b"".join(b.data for b in w.blocks if b.seq == 102 and b.data)
                for rec in iter_records(seg, 102):
                    if rec.elem_id == -1 or rec.body_size == 0:  # save-unit sentinel
                        continue
                    walked += 1
                    try:
                        dec.decode_record(rec.class_id, rec.payload)
                        decoded += 1
                    except Exception:
                        failures += 1
                    if walked >= n_records:
                        break
                if walked >= n_records:
                    break
    assert blocks > 0
    assert walked > 0
    clean = decoded / walked
    assert clean >= 0.95, (f"{path}: only {clean:.1%} of {walked} sampled "
                           f"seq-102 records decode against the {year} schema")


@need25
def test_2025_reads_at_parity_bounded():
    _walk_and_decode(S25, 2025)


@need24
def test_2024_reads_at_parity_bounded():
    _walk_and_decode(S24, 2024)


@need26
def test_2026_baseline_still_reads():
    """Guard against the version model regressing the 2026 path."""
    _walk_and_decode(S26, 2026)


@need25
def test_2025_walker_fails_without_activation():
    """Negative control: the SAME 2025 partition bytes do NOT frame under the
    2026 constants -- proving reading() is load-bearing, not decorative."""
    from rvt.container import open_rvt
    from rvt.partitions import StreamWalker
    with open_rvt(S25) as d:
        pn = d.partition_streams()[0]
        raw = d.logical(pn)
    # under the module-default (2026) ordinals the stream header check
    # raises: cls reads 0x391 (the 2025 ContentMarker) where 0x3a3 is expected
    try:
        w = StreamWalker(raw)                 # module defaults = 2026 ordinals
    except ValueError as e:
        assert "0x391" in str(e) or "unexpected" in str(e)
        return
    assert w.errors or not w.blocks, \
        "2025 partition framed cleanly under 2026 ordinals -- model obsolete?"


# ---------------------------------------------------------------------------
# quarantine discipline
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("year", [2024, 2025])
def test_samples_are_documented_and_quarantined(year):
    d = os.path.join(ROOT, "samples", str(year))
    if not os.path.isdir(d):
        pytest.skip("dev samples absent")
    src = os.path.join(d, "SOURCES.md")
    assert os.path.isfile(src), f"{d} lacks SOURCES.md"
    text = open(src, encoding="utf-8").read()
    assert "DEV-ONLY" in text and "never shipped" in text
    for fn in os.listdir(d):
        if fn.endswith((".rvt", ".rfa")):
            assert fn in text, f"{fn} not recorded in {src}"


def test_no_sample_rvt_inside_plugin_tree():
    """The deny-list law, asserted from this side too: no Autodesk sample
    binary may exist under plugin/ (the only bundled .rvt is our own
    pinned genesis base + our own authored examples)."""
    plug = os.path.join(ROOT, "plugin")
    if not os.path.isdir(plug):
        pytest.skip("plugin tree absent")
    offenders = []
    for dirpath, _dn, fns in os.walk(plug):
        for fn in fns:
            low = fn.lower()
            if low.endswith((".rvt", ".rfa", ".rte")) and "sample" in low:
                offenders.append(os.path.join(dirpath, fn))
    assert not offenders, f"Autodesk sample binaries leaked into plugin/: {offenders}"
