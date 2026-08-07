"""latest_probes.py: Global/Latest reader-tolerance probe generator.

Unit tests cover the length-preserving edit machinery, the deterministic
replacement generators, the AString census, the Forge (typeid, json) pair
walker and the ElementId reference scan on synthetic payloads.  The
integration test analyses the real rstbasic sample, generates two probe
variants into a temp dir and proves each is structurally VALID (only
Global/Latest rewritten, prefix + gzip CRC + framing intact); it is skipped
when the sample is absent.
"""
from __future__ import annotations

import importlib.util
import json
import os
import struct
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tools", "latest_probes.py")
RST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
G0 = os.path.join(ROOT, "experiments", "genesis", "G0.rvt")


@pytest.fixture(scope="module")
def lp():
    spec = importlib.util.spec_from_file_location("latest_probes", TOOL)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["latest_probes"] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# helpers to build a synthetic Latest-like payload
# ---------------------------------------------------------------------------

def _astr(s: str) -> bytes:
    enc = s.encode("utf-16-le")
    return struct.pack("<I", len(enc) // 2) + enc


def _synthetic():
    """prologue-ish junk + build list + naming table + forge pairs + ids."""
    p = bytearray()
    p += bytes(0x53)                                   # prologue
    p += struct.pack("<I", 2) + _astr("Revit 2026 build A") + _astr("Revit 2025 build B")
    # naming table: marker 1 + name + negative built-in id + -1
    for name in ("S206", "FOUNDATION-2700", "52", "8"):
        p += struct.pack("<I", 1) + _astr(name) + struct.pack("<q", -2008113) \
             + struct.pack("<q", -1)
    # a project string in a name table (room)
    p += struct.pack("<I", 3) + _astr("Kitchen & Dining") + struct.pack("<q", 9943196)
    # username token
    p += struct.pack("<I", 1) + _astr("macalis") + struct.pack("<q", -1)
    # machinery
    p += _astr("ColorFillSecondaryData") + _astr("Rooms : Name")
    # forge pairs
    for tid in ("autodesk.unit.dimension:currency-1.0.0",
                "autodesk.spec.aec.structural:rebarNumber-1.0.0"):
        js = '{\n   "typeid": "' + tid + '",\n   "constants": []\n}\n'
        js = js + " " * (170 - len(js))
        p += _astr(tid) + _astr(js)
    # element-id references (i64) as an array: u32 count + n * i64
    ids = [99859, 99860, 1046264]
    p += struct.pack("<I", len(ids)) + b"".join(struct.pack("<q", i) for i in ids)
    return bytes(p), set(ids) | {5000}


# ---------------------------------------------------------------------------
# unit tests (no sample files needed)
# ---------------------------------------------------------------------------

def test_neutral_name_length_and_uniqueness(lp):
    seen = set()
    for i, (cls, ln) in enumerate([("project.room", 4), ("project.room", 16),
                                    ("project.naming", 15), ("project.naming", 4),
                                    ("user", 7), ("project.material", 15)], 1):
        s = lp.neutral_name(cls, i, ln)
        assert len(s) == ln
        assert s not in seen
        seen.add(s)
    assert lp.neutral_name("project.room", 9, 4) == "Rm09"
    assert lp.neutral_name("project.naming", 23, 15) == "Nm0000000000023"
    # 1..2 char names: distinct base-36 tokens
    ones = {lp.neutral_name("project.naming", k, 1) for k in range(36)}
    twos = {lp.neutral_name("project.naming", k, 2) for k in range(200)}
    assert len(ones) == 36 and len(twos) == 200
    assert all(len(x) == 2 for x in twos)


def test_json_stub_is_length_identical_valid_json(lp):
    for tid, ln in [("autodesk.unit.dimension:currency-1.0.0", 202),
                    ("autodesk.spec.aec:number-2.0.0", 161),
                    ("x" * 200, 161)]:
        s = lp.json_stub(tid, ln)
        assert len(s) == ln
        obj = json.loads(s)                     # must be valid JSON
        if len(tid) + 15 <= ln:
            assert obj == {"typeid": tid}
        else:
            assert obj == {}


def test_scrub_lbmap_keeps_widths_and_is_unique(lp):
    a = lp.scrub_lbmap("1046264.1.1471776", 1)
    b = lp.scrub_lbmap("1046264.1.1471776", 2)
    c = lp.scrub_lbmap("493612.1.1471771", 1)
    assert len(a) == len("1046264.1.1471776") and len(c) == len("493612.1.1471771")
    assert a != b
    assert [len(f) for f in a.split(".")] == [7, 1, 7]


def test_apply_edits_length_preserving_and_overlap_rejected(lp):
    pay = b"AAAABBBBCCCC"
    e1 = lp.Edit(0, b"AAAA", b"XXXX", "name")
    e2 = lp.Edit(8, b"CCCC", b"YYYY", "name")
    out = lp.apply_edits(pay, [e1, e2])
    assert out == b"XXXXBBBBYYYY" and len(out) == len(pay)
    with pytest.raises(AssertionError):
        lp.apply_edits(pay, [lp.Edit(0, b"AAA", b"XX", "name")])       # length change
    with pytest.raises(AssertionError):
        lp.apply_edits(pay, [lp.Edit(0, b"BBBB", b"XXXX", "name")])    # old mismatch


def test_census_and_classification_on_synthetic(lp):
    pay, valid = _synthetic()
    strings = lp.census_strings(pay)
    pairs = lp.walk_forge_pairs(pay)
    assert len(pairs) == 2
    assert pairs[0].t.text.startswith("autodesk.") and pairs[0].j.text.startswith("{")
    covered = set()
    for s in strings:
        covered.update(range(s.off, s.end))
    for x in lp.census_short_naming_entries(pay, {s.off for s in strings}):
        if not (covered & set(range(x.off, x.end))):
            strings.append(x)
    strings.sort(key=lambda s: s.off)
    lp.classify(strings, pairs, pay, lp._build_string_range(pay))
    by = {s.text: s.cls for s in strings}
    assert by["S206"] == "project.naming"
    assert by["FOUNDATION-2700"] == "project.naming"
    assert by["52"] == "project.naming"
    assert by["8"] == "project.naming"
    assert by["macalis"] == "user"
    assert by["ColorFillSecondaryData"] == "machinery"
    assert by["Rooms : Name"] == "category"
    assert by["Kitchen & Dining"] == "project.room"
    assert by["Revit 2026 build A"] == "build"
    assert all(s.cls == "forge.typeid" for s in strings if s.text.startswith("autodesk."))


def test_id_scan_finds_valid_ids_only(lp):
    pay, valid = _synthetic()
    hits = lp.scan_id_refs(pay, valid)
    vals = {h.value for h in hits}
    assert vals == {99859, 99860, 1046264}      # 5000 (< floor never emitted) absent
    offs = [h.off for h in hits]
    assert len(offs) == len(set(offs))
    # nulling them yields i64 -1 at exactly those positions
    an = lp.Analysis("rst", "-", pay, b"\x05" + b"\x00" * 7, [], [], hits, valid, set())
    out = lp.apply_edits(pay, lp.edits_ids(an))
    for h in hits:
        assert struct.unpack_from("<q", out, h.off)[0] == -1
    assert len(out) == len(pay)


def test_forge_stub_and_blank_edits_preserve_length(lp):
    pay, valid = _synthetic()
    pairs = lp.walk_forge_pairs(pay)
    an = lp.Analysis("rst", "-", pay, b"\x05" + b"\x00" * 7, [], pairs, [], valid, set())
    for mode in ("stub", "blank", "scrub"):
        out = lp.apply_edits(pay, lp.edits_forge(an, mode))
        assert len(out) == len(pay)
        # typeid keys survive stub/blank, are scrubbed in scrub
        keep = pairs[0].t.text.encode("utf-16-le") in out
        assert keep == (mode != "scrub")
    stub = lp.apply_edits(pay, lp.edits_forge(an, "stub"))
    j = pairs[0].j
    body = stub[j.data_off:j.end].decode("utf-16-le")
    assert json.loads(body) == {"typeid": pairs[0].t.text}


# ---------------------------------------------------------------------------
# integration (needs the rstbasic sample)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not os.path.exists(RST), reason="rstbasic sample absent")
def test_analysis_of_rstbasic_latest(lp):
    an = lp.analyse("rst")
    cls = {}
    for s in an.strings:
        cls.setdefault(s.cls, []).append(s.text)
    assert not cls.get("unclassified"), f"unclassified strings: {cls.get('unclassified')}"
    assert len(cls["project.room"]) == 11 and "Hall" in cls["project.room"]
    assert "FOUNDATION-2700" in cls["project.naming"] and "S206" in cls["project.naming"]
    assert len(cls["project.naming"]) >= 30
    assert set(cls["user"]) == {"liqi", "macalis"}
    assert len(an.pairs) >= 1300
    forge_bytes = sum((p.t.end - p.t.off) + (p.j.end - p.j.off) for p in an.pairs)
    assert forge_bytes / len(an.payload) > 0.8            # ~84 % of the stream
    assert len(an.id_hits) >= 9000
    assert len({h.value for h in an.id_hits}) == 6175         # the audit's dangling count
    assert an.summary()["id_dangling_in_this_file"] == 0     # rst: all LIVE
    if os.path.exists(G0):
        g = lp.analyse("G0")
        assert g.payload == an.payload                       # Latest byte-identical
        assert g.summary()["id_dangling_in_this_file"] == 6175 # G0: all dangling


@pytest.mark.skipif(not os.path.exists(RST), reason="rstbasic sample absent")
def test_probe_generation_is_structurally_valid(lp, tmp_path):
    from rvt.container import open_rvt
    from rvt.validate import validate_file

    an = lp.analyse("rst")
    out_dir = str(tmp_path)
    for probe in ("P1_names", "P4_ids_null", "P3a_forge_stub"):
        note = lp.emit_probe(an, probe, out_dir, run_validator=False)
        path = os.path.join(ROOT, note["file"])
        assert os.path.exists(path)
        # only Global/Latest differs from the base
        with open_rvt(RST) as src, open_rvt(path) as d:
            differ = [s.name for s in src.streams() if src.raw(s.name) != d.raw(s.name)]
            assert differ == ["Global/Latest"], differ
            assert d.prefix("Global/Latest") == b"\x05" + b"\x00" * 7
            assert all(m.crc_ok for m in d.members("Global/Latest"))
            pay = d.inflate("Global/Latest", 0)
        assert len(pay) == len(an.payload)                  # length-preserving
        v = note["self_verification"]
        assert v["payload_identical_to_edited"] and v["prefix_ok"] and v["gzip_crc_ok"]
        assert v["full_pages_ecc_bad"] == 0
        rep = validate_file(path, layers=("structure", "consistency"))
        assert rep.ok, [f.message for f in rep.errors]
        note_json = json.load(open(path[:-4] + ".json"))
        assert note_json["edits"]["count"] > 0
        assert note_json["latest"]["bytes_changed"] > 0
    # P1: sample names gone, our neutral names present
    with open_rvt(os.path.join(out_dir, "P1_names.rvt")) as d:
        pay = d.inflate("Global/Latest", 0)
    assert "FOUNDATION-2700".encode("utf-16-le") not in pay
    assert "Kitchen & Dining".encode("utf-16-le") not in pay
    assert "macalis".encode("utf-16-le") not in pay
    assert "Nm".encode("utf-16-le") in pay and "Rm".encode("utf-16-le") in pay
