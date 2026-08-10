"""A partition whose stream header does not parse is a FAIL *verdict* of the
structural self-check, never a raise (issue #458).

``rvt.manipulate.verify_manipulated`` used to let ``StreamWalker``'s
``ValueError: unexpected Partitions header`` escape -- for the primary
partition always, and since #430 uniformly for a second one -- so the edit
doors reported a crashed job on a file they had already written instead of
delivering it labelled FAIL, and everything after the structural gate (the
validation gate, provenance, the manifest) was lost.  Now such a partition is
ONE walker error whose reason is recorded (``framing_errors[<partition>]``,
worded exactly as the validator's L1 finding on it), the primary's
block-dependent facts stay ``None``, and the gate says FAIL; a lost
``Global/ElemTable`` on a two-partition file is a verdict too.  The same round
retired the self-check's private inventory list: the walk reads the family
shape off the file (``PartAtom`` present -> unframed), so "every framed
non-partition stream carries >= 1 gzip member" is applied literally by both
gates.  On undamaged files nothing a gate says changes.

Fresh-clone runnable (tracked bundled bases + the tracked eval-kit family;
edits and damaged copies go to ``tmp_path``); in the CI shard via
tests/ci_shard.d/458-partition-header-verdict.txt.

Run: .venv/bin/python -m pytest tests/test_partition_header_verdict.py -q
"""
from __future__ import annotations

import dataclasses
import os

import pytest

from rvt import manipulate as M
from rvt.cfb_writer import CfbEntry, write_cfb
from rvt.container import open_rvt
from rvt.roundtrip import read_entries
from rvt.validate import UNFRAMED_STREAMS, unframed_streams_of, validate_file, walk_file

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(ROOT, "plugin", "assets", "genesis")
BASES = {2026: os.path.join(GEN, "G_ABPD.rvt"),
         2025: os.path.join(GEN, "G_ABPD_2025.rvt"),
         2024: os.path.join(GEN, "G_ABPD_2024.rvt")}
FAMILY = os.path.join(ROOT, "tekton-eval-kit", "TEST-KIT", "08_eaton_panelboard_family.rfa")
LEVEL_ID = 1351691                     # "GEN B1 - Basement", present in all three bases

pytestmark = pytest.mark.skipif(
    not all(os.path.isfile(p) for p in BASES.values()),
    reason="bundled genesis bases missing")

#: the block-dependent facts of the primary partition: not checked -> None
BLOCK_DEPENDENT = ("isize_identity_mismatches", "sentinel_last", "stamps_ok",
                   "unit0_ids_equal_elemtable")


def _gates(job, path, *, walked=None, edited=(LEVEL_ID,)):
    """(verify dict, structural gate, validator report json -timings)."""
    v = M.verify_manipulated(path, edited_ids=list(edited), walked=walked)
    structural = job.structural_gate_from_manipulated(v)
    rep = validate_file(path, walked=walked).to_json()
    rep.pop("timings")
    return v, structural, rep


def _judged(job, path, **kw):
    """The gates through two independent walks and through ONE shared walk --
    which must not change a word either says -- returning the shared triple."""
    independent = _gates(job, path, **kw)
    walked = walk_file(path)
    shared = _gates(job, path, walked=walked, **kw)
    walked.close()
    for name, a, b in zip(("verify_manipulated", "structural gate", "validator report"),
                          independent, shared):
        assert a == b, f"{os.path.basename(path)}: {name} differs when the walk is shared"
    return shared


def _errors_at(rep, where):
    return [f["message"] for f in rep["findings"]
            if f["severity"] == "error" and f["where"] == where]


def _partition(path: str) -> str:
    with open_rvt(path) as doc:
        return doc.partition_streams()[0]


def _rewrite(src: str, dst: str, mutate_by_name: dict, extra=()) -> None:
    """Copy ``src`` to ``dst`` with the RAW bytes of each named stream passed
    through its ``mutate(bytearray)``; ``extra`` entries appended verbatim."""
    out = []
    for e in read_entries(src):
        if e.entry_type == "stream" and e.path in mutate_by_name:
            raw = bytearray(e.data)
            mutate_by_name[e.path](raw)
            e = dataclasses.replace(e, data=bytes(raw))
        out.append(e)
    write_cfb(dst, out + list(extra))


def _zero16(raw: bytearray) -> None:
    """Zero the first 16 bytes: the 18-byte stream header no longer parses."""
    raw[0:16] = b"\x00" * 16


#: inside the ONE gzip body of a Global/* stream: u64 prefix + gzip header + a bit
_IN_GLOBAL_BODY = 8 + 10 + 200


def _smash64(raw: bytearray, off: int = _IN_GLOBAL_BODY) -> None:
    """Destroy 64 bytes at ``off`` -- far beyond CRCIO auto-repair."""
    raw[off:off + 64] = b"\xff" * 64


def _twin_entry(src: str, mutate=None) -> CfbEntry:
    """``src``'s partition duplicated under the next stream number (a
    NON-primary partition), its raw bytes passed through ``mutate``."""
    pname = _partition(src)
    part = next(e for e in read_entries(src) if e.entry_type == "stream" and e.path == pname)
    raw = bytearray(part.data)
    if mutate:
        mutate(raw)
    return dataclasses.replace(part, path=f"Partitions/{int(pname.split('/')[1]) + 1}",
                               data=bytes(raw))


@pytest.fixture(scope="module")
def edited(tmp_path_factory):
    """A front-door style set-level edit of the 2025 base (own release)."""
    from rvt.frontdoor.release_ctx import release_build_context
    from rvt.mutate import Document
    base = BASES[2025]
    out = str(tmp_path_factory.mktemp("hdr_verdict") / "level_2025.rvt")
    with release_build_context(base):
        doc = Document.from_file(base)
        plan = M.set_level_elevation(doc, LEVEL_ID, doc._level_elevation(LEVEL_ID) + 1.25)
        M.commit_plans(base, out, [plan])
    return out


# ---------------------------------------------------------------------------
# 1. the primary partition's header zeroed: a verdict, block facts None
# ---------------------------------------------------------------------------
def test_primary_header_zeroed_is_a_fail_verdict(job, tmp_path, edited):
    pname = _partition(edited)
    bad = str(tmp_path / "primary_hdr0.rvt")
    _rewrite(edited, bad, {pname: _zero16})
    v, structural, rep = _judged(job, bad)                    # no exception
    assert structural["status"] == "FAIL"
    assert v["walker_errors"] == 1 and structural["report"]["walker_errors"] == 1
    assert list(v["framing_errors"]) == [pname]
    assert v["framing_errors"][pname].startswith("partition header/framing: unexpected Partitions header")
    for k in BLOCK_DEPENDENT:
        assert v[k] is None, (k, v[k])
    assert v["edited"] == {} and v["crc_failures"] == 0
    assert isinstance(v["elemtable_count"], int) and v["header_count"] == 0
    # the validator words the same condition identically, and FAILs too
    assert not rep["ok"] and v["framing_errors"][pname] in _errors_at(rep, pname)


# ---------------------------------------------------------------------------
# 2. a twin partition's header zeroed: FAIL, the primary's facts intact
# ---------------------------------------------------------------------------
def test_twin_header_zeroed_is_a_fail_verdict(job, tmp_path, edited):
    bad = str(tmp_path / "twin_hdr0.rvt")
    twin = _twin_entry(edited, _zero16)
    _rewrite(edited, bad, {}, extra=[twin])
    v, structural, rep = _judged(job, bad)                    # no exception
    assert structural["status"] == "FAIL"
    assert v["walker_errors"] == 1 and list(v["framing_errors"]) == [twin.path]
    assert (v["crc_failures"], v["ecc_mismatches"], v["isize_identity_mismatches"]) == (0, 0, 0)
    assert v["stamps_ok"] is True and all(v["sentinel_last"].values())
    assert v["elemtable_count"] == v["header_count"] and v["unit0_ids_equal_elemtable"]
    assert v["edited"][str(LEVEL_ID)]["102"] == {"class": "Level", "clean": True}
    assert not rep["ok"] and v["framing_errors"][twin.path] in _errors_at(rep, twin.path)
    assert not _errors_at(rep, _partition(edited))


def test_both_headers_zeroed_count_two_walker_errors(job, tmp_path, edited):
    pname = _partition(edited)
    bad = str(tmp_path / "both_hdr0.rvt")
    _rewrite(edited, bad, {pname: _zero16}, extra=[_twin_entry(edited, _zero16)])
    v, structural, rep = _judged(job, bad)
    assert structural["status"] == "FAIL" and v["walker_errors"] == 2
    assert len(v["framing_errors"]) == 2 and v["stamps_ok"] is None


# ---------------------------------------------------------------------------
# 3. a lost ElemTable on a TWO-partition file: choosing the primary no longer
#    inflates it -> the #430 verdict (counts None -> FAIL), not a raise
# ---------------------------------------------------------------------------
def test_lost_elemtable_on_two_partition_file_is_a_verdict(job, tmp_path, edited):
    bad = str(tmp_path / "twin_et_lost.rvt")
    _rewrite(edited, bad, {"Global/ElemTable": _smash64}, extra=[_twin_entry(edited)])
    v, structural, rep = _judged(job, bad)
    assert structural["status"] == "FAIL" and v["crc_failures"] >= 1
    assert v["elemtable_count"] is None and v["unit0_ids_equal_elemtable"] is None
    assert isinstance(v["header_count"], int) and v["walker_errors"] == 0
    assert "framing_errors" not in v
    assert v["edited"][str(LEVEL_ID)]["102"] == {"class": "Level", "clean": True}
    assert not rep["ok"] and _errors_at(rep, "Global/ElemTable")


# ---------------------------------------------------------------------------
# 4. identity: undamaged files say exactly what they said (no new key, PASS)
# ---------------------------------------------------------------------------
VERIFY_KEYS = ["crc_failures", "ecc_mismatches", "walker_errors", "isize_identity_mismatches",
               "elemtable_count", "header_count", "sentinel_last", "stamps_ok",
               "deleted_still_present", "deleted_in_elemtable", "edited",
               "elemtable_ids_sorted", "unit0_ids_equal_elemtable", "fallbacks"]


@pytest.mark.parametrize("year", sorted(BASES))
def test_undamaged_bases_unchanged(job, year):
    v, structural, rep = _judged(job, BASES[year], edited=())
    assert list(v) == VERIFY_KEYS                             # framing_errors only when earned
    assert structural["status"] == "PASS" and rep["ok"]
    assert (v["crc_failures"], v["ecc_mismatches"], v["walker_errors"]) == (0, 0, 0)


def test_undamaged_edit_and_verbatim_twin_unchanged(job, tmp_path, edited):
    v, structural, rep = _judged(job, edited)
    assert list(v) == VERIFY_KEYS and structural["status"] == "PASS" and rep["ok"]
    twin = str(tmp_path / "twin_ok.rvt")
    _rewrite(edited, twin, {}, extra=[_twin_entry(edited)])
    v, structural, rep = _judged(job, twin)
    assert list(v) == VERIFY_KEYS and structural["status"] == "PASS" and rep["ok"]
    assert v["walker_errors"] == 0


# ---------------------------------------------------------------------------
# 5. the family shape is read off the file: ONE inventory law for both gates
# ---------------------------------------------------------------------------
def test_family_shape_is_inferred_by_the_walk():
    assert unframed_streams_of(["Contents", "Global/Latest"]) == UNFRAMED_STREAMS
    assert unframed_streams_of(["Contents", "PartAtom"]) == UNFRAMED_STREAMS | {"PartAtom"}
    walked = walk_file(BASES[2025])
    assert walked.unframed == UNFRAMED_STREAMS
    # an explicit set (the validator's mode) is honoured as given
    assert walked.view(repair=True, unframed=UNFRAMED_STREAMS | {"PartAtom"}).unframed \
        == UNFRAMED_STREAMS | {"PartAtom"}
    walked.close()


@pytest.mark.skipif(not os.path.isfile(FAMILY), reason="tracked eval-kit family missing")
def test_family_partatom_is_unframed_and_costs_nothing():
    """A Revit-born ``.rfa``: its plain-XML ``PartAtom`` is unframed by the
    file's own shape, so the self-check reads 0 CRC failures on it without a
    private exemption list -- and the family-mode validator agrees."""
    walked = walk_file(FAMILY)
    assert "PartAtom" in walked.names and "PartAtom" in walked.unframed
    assert walked.crc_failures("PartAtom") == 0 and walked.ecc("PartAtom") is None
    v = M.verify_manipulated(FAMILY, walked=walked)
    assert v == M.verify_manipulated(FAMILY)                  # sharing invisible on a family too
    assert (v["crc_failures"], v["ecc_mismatches"], v["walker_errors"]) == (0, 0, 0)
    assert v["elemtable_count"] == v["header_count"] and "framing_errors" not in v
    assert validate_file(FAMILY, family=True, walked=walked).ok
    walked.close()


def test_memberless_framed_stream_fails_both_gates_alike(job, tmp_path, edited):
    """The L1 law literally: a framed non-partition stream with no gzip member
    has lost its body wherever it sits in the inventory -- the self-check
    counts it (structural FAIL) exactly where the validator errors."""
    extra = CfbEntry(path="Global/Orphan", entry_type="stream", data=b"\x00" * 64)
    bad = str(tmp_path / "orphan.rvt")
    _rewrite(edited, bad, {}, extra=[extra])
    v, structural, rep = _judged(job, bad)
    assert v["crc_failures"] == 1 and structural["status"] == "FAIL"
    assert "no gzip member found in framed stream" in _errors_at(rep, "Global/Orphan")
