"""Tests for the Revit-2023 support layer (genesis-2023-reduce stream).

Covers:
* the KNOWN_RELEASES[2023] registration (pins match the file's own schema;
  detection via BasicFileInfo Format)
* rvt.versions.schema_2023 (pinned size/sha256/class count; the load-bearing
  claims PARSER_DELTAS == () and ELEMENT_ID_BITS == 32)
* rvt.versions.records32 -- THE 2023 FORMAT DELTA (32-bit element ids):
  - is_ids32 keys off the schema's own Identifier declaration (v1 m_id i32)
  - the 32-bit record walk covers every segment FULLY, ends on the sentinel,
    and agrees across seq 101/102/103
  - a NEGATIVE control: the same 2023 bytes REFUSE to walk under the 2024+
    (64-bit) grammar -- the layer is load-bearing, not decorative
  - the ElemTable wire codec round-trips byte-exact on the sample
  - activation/restoration: after ids32() exits every patched binding is
    back (including the from-import rebinds); nesting is safe
  - a bounded schema-directed decode probe (>=99 % clean under ids32)
* tools/genesis_2023.py context_2023: composes reading + ids32 + the local
  tag patches; four-registry census coherent on the untouched sample
* quarantine discipline: SOURCES.md complete, no sample binaries in plugin/

Sample-backed tests skip when the quarantined dev samples are absent
(samples are DEV-ONLY and never shipped -- samples/2023/SOURCES.md).
"""
import os
import struct
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from rvt import versions as V  # noqa: E402
from rvt.versions import KNOWN_RELEASES, records32, schema_2023  # noqa: E402

S23 = os.path.join(ROOT, "samples", "2023", "rstbasicsampleproject.rvt")
S26 = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")

HAVE_2023 = os.path.isfile(S23)
HAVE_2026 = os.path.isfile(S26)

need23 = pytest.mark.skipif(not HAVE_2023, reason="2023 dev samples absent")
need26 = pytest.mark.skipif(not HAVE_2026, reason="2026 dev samples absent")


# ---------------------------------------------------------------------------
# registration + pins
# ---------------------------------------------------------------------------

def test_2023_registered():
    assert 2023 in KNOWN_RELEASES
    r = KNOWN_RELEASES[2023]
    assert r.schema_size == 462_765
    assert r.schema_sha256.startswith("bce7907b")
    assert r.class_count == 4418
    assert r.creation_certified is False          # nothing 2023 is certified yet
    assert r.samples_dir == "samples/2023"
    # the six framing ordinals -- the 2023 ordinal era
    assert r.framing == {"BLOCK_TAG": 0x0E4E, "TRAILER_TAG": 0x0E47,
                         "FOOTER_TAG": 0x0E61, "CONTAINER_CLASS": 0x0365,
                         "UNIT_INNER_CLASS": 0x0364, "PT_CLASS": 0x0BC0}


def test_2023_ordinals_strictly_older():
    """Ordinals drift MONOTONICALLY with insertions: every 2023 framing
    ordinal is strictly below its 2024 counterpart."""
    f23, f24 = KNOWN_RELEASES[2023].framing, KNOWN_RELEASES[2024].framing
    for k in f23:
        assert f23[k] < f24[k], k


def test_schema_2023_module_pins():
    assert schema_2023.YEAR == 2023
    assert schema_2023.EXPECTED_SIZE == 462_765
    assert schema_2023.CLASS_COUNT == 4418
    assert schema_2023.PARSER_DELTAS == ()        # the no-fork claim
    assert schema_2023.ELEMENT_ID_BITS == 32      # THE 2023 delta


def test_creation_guard_refuses_2023():
    with pytest.raises(V.UnsupportedTarget):
        V.require_creation_release(2023)
    st = V.creation_status(2023)
    assert st["supported"] is False and st["have_samples"]


def test_check_openable_2023_user():
    # a Revit-2023 user cannot open ANY newer release's file
    for newer in (2024, 2025, 2026):
        with pytest.raises(V.NewerFileError):
            V.check_openable(newer, 2023)
    V.check_openable(2023, 2023)                  # own release: fine
    V.check_openable(2023, 2026)                  # older file, newer Revit: fine


# ---------------------------------------------------------------------------
# detection + schema (sample-backed)
# ---------------------------------------------------------------------------

@need23
def test_detect_release_2023():
    assert V.detect_release(S23) == 2023


@need23
def test_schema_2023_loads_and_verifies():
    s = schema_2023.load()
    st = s.stats()
    assert st["stream_size"] == 462_765
    assert st["class_count"] == 4418
    assert st["unresolved_refs"] == 0             # grammar parses to EOF
    assert schema_2023.verify(s)


@need23
def test_framing_by_name_matches_table():
    s = V.schema_of(S23)
    assert V.ordinals_from_schema(s) == dict(KNOWN_RELEASES[2023].framing)


@need23
def test_is_ids32_from_schema_declaration():
    s = V.schema_of(S23)
    assert records32.is_ids32(s) is True
    c = s.by_name["Identifier"]
    assert c.version == 1 and c.fields[0].name == "m_id"


@need26
def test_is_ids32_false_for_2026():
    assert records32.is_ids32(V.schema_of(S26)) is False


# ---------------------------------------------------------------------------
# the 32-bit record layer (sample-backed)
# ---------------------------------------------------------------------------

def _segments(path, seqs=(101, 102, 103)):
    from collections import defaultdict
    from rvt.container import open_rvt
    from rvt.partitions import StreamWalker
    segs = defaultdict(bytearray)
    with open_rvt(path) as d:
        for pn in d.partition_streams():
            w = StreamWalker(d.logical(pn), inflate=True)
            for b in sorted(w.blocks, key=lambda x: x.hdr_offset):
                if b.data and b.seq in seqs:
                    segs[(b.unit, b.seq)] += b.data
    return {k: bytes(v) for k, v in segs.items()}


@need23
def test_record_walk_full_coverage_and_sentinels():
    """The 32-bit walk covers EVERY segment fully, ends on the sentinel, and
    seq 101/102/103 record counts agree per unit."""
    with V.reading(S23):
        segs = _segments(S23)
    counts = {}
    for (u, s), buf in segs.items():
        recs = list(records32.iter_records32(buf, s))
        # full coverage: the last record's span ends exactly at the buffer end
        last = recs[-1]
        span_end = (last.seg_offset + records32.raw_hdr_len32(s)
                    + last.body_size + 4)
        assert span_end == len(buf), (u, s)
        assert last.elem_id == -1 and last.body_size == 0, (u, s)   # sentinel
        counts.setdefault(u, {})[s] = len(recs)
    for u, per in counts.items():
        assert len(set(per.values())) == 1, (u, per)


@need23
def test_negative_control_64bit_grammar_refuses():
    """The SAME 2023 bytes do not walk under the 2024+ (64-bit) grammar --
    the width layer is load-bearing."""
    from rvt.objects import iter_records as iter64
    with V.reading(S23):
        segs = _segments(S23, seqs=(101,))
    buf = segs[(0, 101)]
    n32 = sum(1 for _ in records32.iter_records32(buf, 101))
    n64 = sum(1 for _ in iter64(buf, 101))
    assert n32 > 10_000
    assert n64 < n32 // 100        # the 64-bit walk dies almost immediately


@need23
def test_elemtable32_roundtrip_byte_exact():
    from rvt.container import open_rvt
    with open_rvt(S23) as f:
        et = f.inflate("Global/ElemTable")
    model = records32.decode_elemtable32(et)
    assert records32.encode_elemtable32(model) == et
    # normalized semantics: owner-invalid is the 64-bit sentinel
    from rvt.elemtable import INVALID_ID
    owners = {r[5] for r in model["records"]}
    assert INVALID_ID in owners
    assert 0xFFFFFFFF not in owners               # never the raw 32-bit wire value


@need23
def test_ids32_activation_and_restoration():
    import rvt.objects as O
    import rvt.mutate as MU
    import rvt.elemtable as ET
    import rvt.stream_encoders as SE
    before = (O.iter_records, MU.iter_records, ET.parse_elemtable,
              SE.decode_elemtable, O.Reader.element_id)
    with records32.ids32():
        assert O.iter_records is records32.iter_records32
        assert MU.iter_records is records32.iter_records32      # from-import rebind
        assert SE.decode_elemtable is records32.decode_elemtable32
        with records32.ids32():                                  # nesting is safe
            assert O.iter_records is records32.iter_records32
        assert O.iter_records is records32.iter_records32
    after = (O.iter_records, MU.iter_records, ET.parse_elemtable,
             SE.decode_elemtable, O.Reader.element_id)
    assert after == before


@need23
def test_bounded_decode_probe_under_reading32():
    """>= 99 % clean schema-directed decode over a bounded record probe."""
    from rvt.objects import ObjectDecoder
    with records32.reading32(S23):
        sch = V.schema_of(S23)
        dec = ObjectDecoder(sch)
        segs = _segments(S23, seqs=(102,))
    buf = segs[(0, 102)]
    total = clean = 0
    with records32.ids32():
        for r in records32.iter_records32(buf, 102):
            if r.elem_id < 0:
                continue
            total += 1
            if total > 400:
                break
            obj = dec.decode_record(r.class_id, r.payload)
            clean += int(obj.clean or obj.stub)
    assert total >= 400
    assert clean >= 396                            # >= 99 %


# ---------------------------------------------------------------------------
# the ladder context (tools/genesis_2023.py)
# ---------------------------------------------------------------------------

@need23
def test_context_2023_census_coherent():
    import genesis_2023 as G
    with G.context_2023(G.SRC):
        cen = G.four_registry_census(G.SRC)
    assert cen["four_registry_coherent"] is True
    assert cen["save_units"] == 53
    assert cen["contentdocs_entries"] == 52
    assert cen["contenttable_records"] == 52
    assert cen["familymgr_doc_guids"] == 52
    assert cen["adocument_clean"] is True
    assert cen["elements"] == 13_821


@need23
def test_context_2023_restores_everything():
    import genesis_2023 as G
    import rvt.objects as O
    import rvt.partitions as P
    import rvt.adocument as adoc
    import rvt_reduce as RR
    before = (O.iter_records, P.BLOCK_TAG, adoc._DECODER, RR.scan_stream_ids)
    with G.context_2023(G.SRC):
        assert P.BLOCK_TAG == 0x0E4E
        assert O.iter_records is records32.iter_records32
        assert RR.scan_stream_ids is records32.scan_stream_ids32
    after = (O.iter_records, P.BLOCK_TAG, adoc._DECODER, RR.scan_stream_ids)
    assert after == before


# ---------------------------------------------------------------------------
# the run lock (a rule a process can violate must be a gate the tool enforces)
# ---------------------------------------------------------------------------

def test_ladder_lock_refuses_live_holder_and_reclaims_stale(tmp_path, monkeypatch):
    import genesis_2023 as G
    lock = tmp_path / ".ladder.lock"
    monkeypatch.setattr(G, "RUNGS", str(tmp_path))
    monkeypatch.setattr(G, "LOCK_PATH", str(lock))
    # live holder (our own pid counts as alive) -> REFUSE
    lock.write_text(str(os.getpid()))
    with pytest.raises(SystemExit, match="REFUSED"):
        with G.ladder_lock():
            pass
    # stale holder (a dead pid) -> reclaimed, lock taken, then cleared
    lock.write_text("999999999")
    with G.ladder_lock():
        assert lock.read_text() == str(os.getpid())
    assert not lock.exists()


# ---------------------------------------------------------------------------
# quarantine discipline
# ---------------------------------------------------------------------------

def test_sources_md_covers_all_samples():
    d = os.path.join(ROOT, "samples", "2023")
    if not os.path.isdir(d):
        pytest.skip("2023 dev samples absent")
    src = open(os.path.join(d, "SOURCES.md")).read()
    for fn in os.listdir(d):
        if fn.endswith(".rvt"):
            assert fn in src, f"{fn} missing from SOURCES.md"
    assert "DEV-ONLY" in src and "never shipped" in src


def test_no_sample_binaries_in_plugin():
    bad = []
    for base, _dirs, files in os.walk(os.path.join(ROOT, "plugin")):
        for fn in files:
            if fn.endswith((".rvt", ".rfa", ".rte")) and "sample" in fn.lower():
                bad.append(os.path.join(base, fn))
    assert not bad, bad


# ---------------------------------------------------------------------------
# ladder artifacts (present only after tools/genesis_2023.py ran; every rung
# must carry its gates in its own report -- the record is load-bearing)
# ---------------------------------------------------------------------------

RUNGS_DIR = os.path.join(ROOT, "experiments", "genesis2023", "reduce")


def _rung_report(name):
    import json
    p = os.path.join(RUNGS_DIR, f"{name}.json")
    if not os.path.isfile(p):
        pytest.skip(f"{name} not built yet")
    with open(p) as fh:
        return json.load(fh)


@pytest.mark.parametrize("name", ["R5_2023", "R6_2023", "R7_2023",
                                  "R8_2023", "R9_2023"])
def test_r_rung_gates(name):
    rep = _rung_report(name)
    assert rep.get("structural_ok") is True
    assert rep["validator"]["ok"] is True and rep["validator"]["errors"] == 0
    assert rep["reduce_law"]["verdict"] == "EDIT-FREE"
    assert rep["reduce_law"]["added"] == 0
    assert not rep.get("FAILED_SELF_CHECK")


def test_k3_2023_gates():
    rep = _rung_report("K3_2023")
    assert rep.get("structural_ok") is True
    assert rep["validator"]["ok"] is True and rep["validator"]["errors"] == 0
    assert rep["reduce_law"]["edits_are_exactly_the_neutralised_referrers"] is True
    assert rep["reduce_law"]["removed"] == 0 and rep["reduce_law"]["added"] == 0
    assert not rep.get("FAILED_SELF_CHECK")


def test_b2023_k4_gates():
    rep = _rung_report("B2023_K4")
    assert rep.get("structural_ok") is True
    assert rep["validator"]["ok"] is True and rep["validator"]["errors"] == 0
    assert rep["reduce_law"]["verdict"] == "EDIT-FREE"
    assert rep["residual_guid_bytes_in_Latest_and_ContentDocuments"] == 0
    assert rep["census"]["four_registry_coherent"] is True
    assert not rep.get("FAILED_SELF_CHECK")
