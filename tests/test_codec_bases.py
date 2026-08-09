"""Every codec layer round-trips byte-exact on the three BUNDLED bases (#132).

The byte-exact writer chain (gzip -> CRCIO page ECC -> CFB -> stream codecs
-> schema-directed object codec -> ADocument) is proven end to end in
KNOWLEDGE.md, but every corpus test that proves it keys on ``samples/`` or
``extracted/`` and self-skips in a fresh clone / CI.  This module runs the
same laws on the only Revit files a fresh clone has -- our own composed,
certified genesis bases shipped in the plugin -- so a writer change that
breaks any layer, or the 2025/2024 framing ordinals, goes red before merge:

    plugin/assets/genesis/G_ABPD.rvt        Revit 2026
    plugin/assets/genesis/G_ABPD_2025.rvt   Revit 2025
    plugin/assets/genesis/G_ABPD_2024.rvt   Revit 2024

Every case reads its base under ``rvt.versions.records32.reading32`` (the
file's OWN framing ordinals; the 32-bit record layer would switch in for a
<= 2023 file) and an autouse fixture proves the latest-release constants
are back afterwards.  No record counts are hard-coded (bases get re-pinned,
#19) -- only structural minima.  A failing assertion here is a FINDING to
file, never a bound to loosen.

Run: .venv/bin/python -m pytest tests/test_codec_bases.py -q -rs --durations=10
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys

import pytest

from rvt import adocument as ad
from rvt import ecc
from rvt import partitions as P
from rvt import stream_encoders as se
from rvt import versions as V
from rvt.container import PAGE_PAYLOAD, PAGE_STRIDE, open_rvt
from rvt.encode import (ObjectEncoder, first_divergence, reencode_segment,
                        roundtrip_segment)
from rvt.objects import iter_records
from rvt.roundtrip import roundtrip, verify_pair
from rvt.validate import UNFRAMED_STREAMS      # project streams stored with NO page ECC
from rvt.versions._release_schema import verify_schema
from rvt.versions.records32 import reading32

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
VENDOR = os.path.join(ROOT, "plugin", "skills", "_shared", "_vendor")   # olefile
GEN = os.path.join(ROOT, "plugin", "assets", "genesis")
BASES = {2026: os.path.join(GEN, "G_ABPD.rvt"),
         2025: os.path.join(GEN, "G_ABPD_2025.rvt"),
         2024: os.path.join(GEN, "G_ABPD_2024.rvt")}
SEQS = (101, 102, 103)

pytestmark = pytest.mark.skipif(
    not all(os.path.isfile(p) for p in BASES.values()),
    reason="bundled genesis bases missing")


@pytest.fixture(autouse=True)
def _constants_restored():
    """After every case the built-in (latest-release) framing is back."""
    yield
    latest = V.framing_table(V.LATEST_RELEASE)
    assert {k: getattr(P, k) for k in latest} == latest


@pytest.fixture(params=sorted(BASES, reverse=True))
def base(request):
    """(year, open document) with the base's own release in force."""
    year = request.param
    with reading32(BASES[year]), open_rvt(BASES[year]) as doc:
        yield year, doc


def _mismatch(what: str, want: bytes, got: bytes) -> str:
    i = first_divergence(want, got)
    lo = max(0, i - 8)
    return (f"{what}: len {len(got)} vs {len(want)}; first diff @0x{i:x}: "
            f"got {got[lo:i].hex(' ')} | {got[i:i + 16].hex(' ')} "
            f"want {want[lo:i].hex(' ')} | {want[i:i + 16].hex(' ')}")


def _ecc_streams(doc):
    for s in doc.streams():
        raw = doc.raw(s.name)
        if raw and s.name.split("/")[-1] not in UNFRAMED_STREAMS:
            yield s.name, raw


def _unit0_segments(doc) -> dict:
    """StreamWalker over every partition stream (0 errors required); the
    per-seq concatenated block payloads of unit 0 of the first partition
    (the engine's global unit 0, cf. ``rvt.families.unit_segments``)."""
    segs: dict = {}
    for i, pname in enumerate(doc.partition_streams()):
        w = P.StreamWalker(doc.logical(pname), inflate=True, keep_data=True)
        assert w.errors == [], (pname, w.errors)
        assert all(b.crc_ok for b in w.blocks), pname
        if i == 0:
            u = w.units[0]
            for b in sorted(w.blocks[u.first_block:u.first_block + u.n_blocks],
                            key=lambda b: b.hdr_offset):
                segs.setdefault(b.seq, bytearray()).extend(b.data or b"")
    return {seq: bytes(buf) for seq, buf in segs.items()}


# ---------------------------------------------------------------------------
# (a) gzip: every member of every stream verifies its CRC32/ISIZE trailer
# ---------------------------------------------------------------------------

def test_every_gzip_member_crc_ok(base):
    year, doc = base
    members = [(s.name, m) for s in doc.streams() for m in doc.members(s.name)]
    bad = [(name, m.index) for name, m in members if not m.crc_ok]
    print(f"\n{year}: gzip members {len(members)}, crc failures {len(bad)}")
    assert bad == []
    for name in ("Formats/Latest", "Global/Latest", "Contents", *doc.partition_streams()):
        assert doc.members(name), f"{year}: {name} carries no gzip member"


# ---------------------------------------------------------------------------
# (b) CRCIO page ECC: stored trailers regenerate; unframe -> frame is identity
# ---------------------------------------------------------------------------

def test_ecc_full_page_trailers_and_reframe(base):
    year, doc = base
    n_pages, framed = 0, set()
    for name, raw in _ecc_streams(doc):
        for off in range(0, len(raw) - PAGE_STRIDE + 1, PAGE_STRIDE):
            page = raw[off:off + PAGE_PAYLOAD]
            assert ecc.page_trailer(page) == raw[off + PAGE_PAYLOAD:off + PAGE_STRIDE], \
                (year, name, off)
            n_pages += 1
        got = ecc.frame_stream(ecc.unframe_stream(raw))
        assert got == raw, _mismatch(f"{year} {name} reframe", raw, got)
        framed.add(name)
    print(f"\n{year}: ECC full pages {n_pages}, framed streams {len(framed)}")
    assert n_pages >= 1, year
    assert {"Formats/Latest", ad.STREAM, "Contents", *doc.partition_streams()} <= framed, framed


def test_ecc_verifies_with_numpy_hidden(tmp_path):
    """The same ECC laws on one base from a BARE interpreter (``-I -S``: no
    site-packages, hence no numpy -- only ``src/`` and the plugin's vendored
    olefile), the way tests/test_coldstart.py runs the shipped surface.
    The 2025 base, so non-default framing ordinals are in force on that path."""
    year = 2025
    code = (
        "import importlib.util, sys\n"
        f"sys.path.insert(0, {SRC!r}); sys.path.insert(0, {VENDOR!r})\n"
        "assert importlib.util.find_spec('numpy') is None, 'numpy is not hidden'\n"
        "from rvt import ecc\n"
        "from rvt.container import open_rvt, PAGE_PAYLOAD, PAGE_STRIDE\n"
        "from rvt.validate import UNFRAMED_STREAMS\n"
        "from rvt.versions.records32 import reading32\n"
        f"path, n = {BASES[year]!r}, 0\n"
        "with reading32(path), open_rvt(path) as doc:\n"
        "    for s in doc.streams():\n"
        "        raw = doc.raw(s.name)\n"
        "        if not raw or s.name.split('/')[-1] in UNFRAMED_STREAMS:\n"
        "            continue\n"
        "        for off in range(0, len(raw) - PAGE_STRIDE + 1, PAGE_STRIDE):\n"
        "            assert ecc.page_trailer(raw[off:off + PAGE_PAYLOAD]) == "
        "raw[off + PAGE_PAYLOAD:off + PAGE_STRIDE], (s.name, off)\n"
        "            n += 1\n"
        "        assert ecc.frame_stream(ecc.unframe_stream(raw)) == raw, s.name\n"
        "assert n >= 1, n\n"
        "assert 'numpy' not in sys.modules, 'ECC pulled numpy'\n"
        "print('NUMPY-FREE-ECC-OK', n)\n")
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("RVT_") and k != "PYTHONPATH"}
    r = subprocess.run([sys.executable, "-I", "-S", "-c", code], cwd=str(tmp_path),
                       env=env, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-2000:]
    assert "NUMPY-FREE-ECC-OK" in r.stdout, r.stdout[-500:]


# ---------------------------------------------------------------------------
# (c) the six small structured streams: enc(dec(x)) == x
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", list(se.CODECS))
def test_stream_codec_roundtrip_byte_exact(base, name):
    year, doc = base
    kind = se.CODECS[name][2]
    if kind == "payload":
        data = doc.inflate(f"Global/{name}", 0)
    elif kind == "contents":
        data = doc.inflate("Contents", 0)
    else:
        data = doc.raw(name)
    assert data, f"{year}: {name} is empty"
    exact, out = se.roundtrip(name, data)
    assert exact, _mismatch(f"{year} {name}", data, out)


# ---------------------------------------------------------------------------
# (d) partition framing + the schema-directed object codec on unit 0
# ---------------------------------------------------------------------------

def test_unit0_records_roundtrip_byte_exact(base):
    year, doc = base
    segs = _unit0_segments(doc)
    assert set(SEQS) <= set(segs), (year, sorted(segs))
    enc = ObjectEncoder(V.schema_of(doc))          # the base's OWN schema
    tested = 0
    for seq in SEQS:
        seg = segs[seq]
        st = roundtrip_segment(seg, seq, enc)
        print(f"\n{year} seq{seq}: {len(seg):,} B records={st['records']} "
              f"tested={st['tested']} pass={st['pass']} fail={st['fail']} "
              f"skipped_unclean={st['skipped_unclean']}")
        assert st["pass"] == st["tested"] > 0, st["failures"][:3]
        assert st["skipped_bad_trailer"] == 0, (year, seq)
        tested += st["tested"]
        rebuilt, st2 = reencode_segment(seg, seq, enc)
        assert st2["tail"] == 0, st2
        assert rebuilt == seg, _mismatch(f"{year} seq{seq} reencode_segment", seg, rebuilt)
    assert tested >= 9000, (year, tested)


@pytest.mark.parametrize("base", [
    pytest.param(2026, marks=pytest.mark.xfail(
        strict=True, reason="#138: an Extensible-Storage DataStorage record in "
        "unit 0 does not decode clean (passed through verbatim by reencode_segment)")),
    2025, 2024], indirect=True)
def test_unit0_every_record_decodes_clean(base):
    """The stricter law behind (d): no record is excluded from the tested set
    because its object decode is lossy (``roundtrip_segment`` skips those by
    contract).  Retires its own xfail when #138 lands."""
    year, doc = base
    dec = ObjectEncoder(V.schema_of(doc)).dec
    unclean = [(seq, rec.elem_id, dec.class_name(rec.class_id))
               for seq, seg in _unit0_segments(doc).items() if seq in SEQS
               for rec in iter_records(seg, seq) if rec.elem_id >= 0
               and not dec.decode_record(rec.class_id, rec.payload).clean]
    assert unclean == [], (year, unclean[:5])


# ---------------------------------------------------------------------------
# (e) Global/Latest: the ADocument graph decodes clean and re-encodes exact
# ---------------------------------------------------------------------------

def test_adocument_decode_clean_and_encode_byte_exact(base):
    year, doc = base
    dec = ad.ADocumentDecoder(V.schema_of(doc))
    payload = doc.inflate(ad.STREAM, 0)
    adoc = ad.decode_latest(payload, dec)
    assert adoc.errors == [], f"{year}: {adoc.errors[:1]}"
    assert adoc.clean, year
    assert adoc.trailer == ad.TRAILER, f"{year}: trailer {adoc.trailer.hex()}"
    assert adoc.consumed + 2 + len(adoc.trailer) == len(payload), year
    out = ad.encode_latest(adoc, dec)
    assert out == payload, _mismatch(f"{year} Global/Latest", payload, out)


# ---------------------------------------------------------------------------
# (f) CFB container: read -> write -> stream-equal
# ---------------------------------------------------------------------------

def test_cfb_roundtrip_is_stream_equal(base, tmp_path):
    year, doc = base
    out = str(tmp_path / f"rt_{year}.rvt")
    layout, _tr, _tw = roundtrip(doc.path, out)
    assert layout.major_version == 4 and layout.sector_size == 4096, year
    problems, notes = verify_pair(doc.path, out)
    assert problems == [], f"{year} round trip mismatch:\n  " + "\n  ".join(problems)
    # the only note is "second reader not installed", and only when it is not
    assert bool(notes) == (importlib.util.find_spec("compoundfiles") is None), notes


# ---------------------------------------------------------------------------
# (g) the embedded schema is the release's pinned constant
# ---------------------------------------------------------------------------

def test_schema_matches_known_release_pin(base):
    year, doc = base
    verify_schema(V.KNOWN_RELEASES[year], V.schema_of(doc))   # size/sha256/classes/refs; raises
    assert V.detect_release(doc) == year
