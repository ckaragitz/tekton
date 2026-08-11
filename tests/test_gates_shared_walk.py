"""One page walk, two gates (issue #266): the structural gate
(``rvt.manipulate.verify_manipulated``) and the validation gate
(``rvt.validate.validate_file``) of a front-door edit share ONE read + ECC
pass + inflate/CRC walk of the written file (``rvt.validate.walk_file``)
instead of each re-opening, inflating and CRC-walking the container.

The contract pinned here: sharing changes NOTHING a gate says.  On the three
bundled genesis bases, on a set-level edit of one, on a hard-damaged copy
(payload bytes destroyed beyond CRCIO auto-repair) and on a soft-damaged copy
(one payload bit flipped -- inside Revit's auto-repair envelope, so the
validator's view is REPAIRED while the writer self-check must still judge the
bytes as stored) the shared-walk gate dicts are identical to the ones two
independent walks produce, and the damaged copies FAIL exactly as before.
Since #430 the self-check enumerates blocks by each stream's framing, so a
lost gzip body off the primary partition (``Global/Latest``, ``Contents``,
``Global/ElemTable``, a second ``Partitions/<N>``) FAILs it as well.

Fresh-clone runnable (tracked bundled bases only; edits and damaged copies are
written to ``tmp_path`` through conftest's ``rewrite_stream`` / ``partition_of``,
#579 / #604); in the CI shard via tests/ci_shard.d/.

Run: .venv/bin/python -m pytest tests/test_gates_shared_walk.py -q
"""
from __future__ import annotations

import dataclasses
import os

import pytest

from conftest import partition_of, rewrite_stream
from rvt import ecc
from rvt import manipulate as M
from rvt import partitions as P
from rvt import versions as V
from rvt.cfb_writer import write_cfb
from rvt.roundtrip import read_entries
from rvt.validate import WalkedFile, validate_file, walk_file

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(ROOT, "plugin", "assets", "genesis")
BASES = {2026: os.path.join(GEN, "G_ABPD.rvt"),
         2025: os.path.join(GEN, "G_ABPD_2025.rvt"),
         2024: os.path.join(GEN, "G_ABPD_2024.rvt")}
LEVEL_ID = 1351691                     # "GEN B1 - Basement", present in all three bases

pytestmark = pytest.mark.skipif(
    not all(os.path.isfile(p) for p in BASES.values()),
    reason="bundled genesis bases missing")


@pytest.fixture(autouse=True)
def _constants_restored():
    """After every test the built-in (latest-release) framing is back."""
    yield
    latest = V.framing_table(V.LATEST_RELEASE)
    assert {k: getattr(P, k) for k in latest} == latest


def _report_json(rep) -> dict:
    """A validator Report as the gate sees it, minus wall-clock noise."""
    d = rep.to_json()
    d.pop("timings")
    return d


def _gates(job, path: str, tmp_path, tag: str, *, walked=None, edited=(), deleted=()):
    """(verify dict, structural gate, validator report json, validation gate)
    for ``path`` -- through the shared ``walked`` or, without it, the way
    every gate walked the file for itself before #266."""
    v = M.verify_manipulated(path, edited_ids=list(edited), deleted_ids=list(deleted),
                             walked=walked)
    structural = job.structural_gate_from_manipulated(v)
    rep = validate_file(path, walked=walked)
    vg = job.validation_gate(path, str(tmp_path / f"{tag}.validation.json"), walked=walked)
    for k in ("elapsed_s", "report_json"):
        vg.pop(k)
    return v, structural, _report_json(rep), vg


def _assert_sharing_is_invisible(job, path, tmp_path, tag, **ids):
    independent = _gates(job, path, tmp_path, tag + "-indep", **ids)
    walked = walk_file(path)
    assert isinstance(walked, WalkedFile) and walked.repair
    shared = _gates(job, path, tmp_path, tag + "-shared", walked=walked, **ids)
    walked.close()
    for name, a, b in zip(("verify_manipulated", "structural gate", "validator report",
                          "validation gate"), independent, shared):
        assert a == b, f"{tag}: {name} differs when the walk is shared"
    return shared


def _edit(year: int, out_dir) -> str:
    """Raise LEVEL_ID of BASES[year] by 1.25 ft the way the front door does
    (inside the base's own release context); returns the written path."""
    from rvt.frontdoor.release_ctx import release_build_context
    from rvt.mutate import Document
    base = BASES[year]
    out = str(out_dir / f"level_{year}.rvt")
    with release_build_context(base):
        doc = Document.from_file(base)
        plan = M.set_level_elevation(doc, LEVEL_ID, doc._level_elevation(LEVEL_ID) + 1.25)
        M.commit_plans(base, out, [plan])
    return out


# an offset inside the first block's deflate body of a Partitions/<N> stream:
# 44-byte stream header + 26-byte block header + 10-byte gzip header + a bit
_IN_FIRST_MEMBER = 44 + 26 + 10 + 200


def _smash64(raw: bytes, off: int = _IN_FIRST_MEMBER) -> bytes:
    """A ``rewrite_stream`` damage: 64 bytes at ``off`` destroyed -- far
    beyond CRCIO auto-repair."""
    return raw[:off] + b"\xff" * 64 + raw[off + 64:]


def _flip_bit(raw: bytes) -> bytes:
    """A ``rewrite_stream`` damage: ONE payload bit flipped in the first
    block's body -- inside Revit's auto-repair envelope."""
    return raw[:_IN_FIRST_MEMBER] + bytes([raw[_IN_FIRST_MEMBER] ^ 0x04]) + raw[_IN_FIRST_MEMBER + 1:]


# ---------------------------------------------------------------------------
# 1. the three pinned bases: identical dicts, and healthy
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("year", sorted(BASES))
def test_pinned_base_gates_identical_shared_or_not(job, tmp_path, year):
    v, structural, report, vg = _assert_sharing_is_invisible(
        job, BASES[year], tmp_path, f"base{year}")
    assert structural["status"] == "PASS" and vg["status"] == "PASS", (structural, vg)
    assert (v["crc_failures"], v["ecc_mismatches"], v["walker_errors"]) == (0, 0, 0)
    assert report["ok"] and report["counts"]["error"] == 0


# ---------------------------------------------------------------------------
# 2. a front-door style edit: identical dicts, the edit seen clean by both
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def edited(tmp_path_factory):
    return _edit(2025, tmp_path_factory.mktemp("shared_walk_edit"))


def test_edit_output_gates_identical_shared_or_not(job, tmp_path, edited):
    v, structural, report, vg = _assert_sharing_is_invisible(
        job, edited, tmp_path, "edit", edited=[LEVEL_ID])
    assert structural["status"] == "PASS" and vg["status"] == "PASS"
    assert v["edited"][str(LEVEL_ID)]["102"] == {"class": "Level", "clean": True}
    assert v["fallbacks"] == [] and report["ok"]


# ---------------------------------------------------------------------------
# 3. damaged copies still FAIL both gates, with the same findings either way
# ---------------------------------------------------------------------------
def test_hard_damage_fails_both_gates_identically(job, tmp_path, edited):
    """64 payload bytes destroyed in the partition's first block: far beyond
    the CRCIO auto-repair envelope -> validator ERROR, structural FAIL."""
    bad = rewrite_stream(edited, tmp_path / "hard.rvt", partition_of(edited), _smash64)
    v, structural, report, vg = _assert_sharing_is_invisible(
        job, bad, tmp_path, "hard", edited=[LEVEL_ID])
    assert structural["status"] == "FAIL"
    assert v["crc_failures"] >= 1
    assert vg["status"] == "FAIL" and not report["ok"]
    assert any("ECC" in f["message"] for f in report["findings"] if f["severity"] == "error")


def test_soft_damage_is_judged_as_stored_by_the_self_check(job, tmp_path, edited):
    """ONE payload bit flipped: inside Revit's auto-repair envelope, so the
    validator repairs it (WARNING, file still VALID) and its shared walk
    carries REPAIRED bytes -- yet the writer self-check keeps judging OUR
    bytes as stored (gzip CRC broken -> FAIL), shared walk or not."""
    pname = partition_of(edited)
    bad = rewrite_stream(edited, tmp_path / "soft.rvt", pname, _flip_bit)
    walked = walk_file(bad)
    assert walked.repaired(pname), "the ECC pass should have auto-repaired the flipped bit"
    assert ecc.PAGE_STRIDE < len(walked.raw(pname)), "the flip must sit in a full page"
    v, structural, report, vg = _assert_sharing_is_invisible(
        job, bad, tmp_path, "soft", edited=[LEVEL_ID])
    assert v["crc_failures"] >= 1 and structural["status"] == "FAIL"
    assert report["ok"] and vg["status"] == "PASS"
    assert any("auto-repairable" in f["message"] for f in report["findings"]
               if f["severity"] == "warning"), report["findings"][:5]


# ---------------------------------------------------------------------------
# 3b. off the primary partition the self-check sees a lost body too (#430):
#     blocks are enumerated by each stream's FRAMING, so a body that will not
#     inflate at all is a CRC failure wherever it sits -- not only where the
#     block walker of the primary partition happens to look
# ---------------------------------------------------------------------------
# 64 destroyed bytes inside the ONE gzip body of a non-partition framed stream:
# Global/* = u64 prefix + gzip header + a bit; Contents = 24-byte wrapper + ...
_LOST_BODY = {"Global/Latest": 8 + 10 + 200, "Global/ElemTable": 8 + 10 + 200,
              "Contents": 24 + 10 + 20}


@pytest.mark.parametrize("name", sorted(_LOST_BODY))
def test_lost_body_off_the_primary_partition_fails_the_self_check(job, tmp_path, edited, name):
    """A magic scan alone skips an uninflatable member and reads 0; by the
    stream's framing the body is missing -> ``crc_failures`` >= 1 ->
    structural FAIL, exactly like the validator's L1 error on it.  A lost
    ``Global/ElemTable`` is a verdict (counts None -> FAIL), not a raise."""
    bad = rewrite_stream(edited, tmp_path / "lost.rvt", name, lambda raw: _smash64(raw, _LOST_BODY[name]))
    v, structural, report, vg = _assert_sharing_is_invisible(
        job, bad, tmp_path, "lost-" + name.replace("/", "-"), edited=[LEVEL_ID])
    assert v["crc_failures"] >= 1 and structural["status"] == "FAIL", v
    assert vg["status"] == "FAIL" and not report["ok"]
    assert any(f["where"] == name for f in report["findings"] if f["severity"] == "error")
    if name == "Global/ElemTable":
        assert v["elemtable_count"] is None and v["unit0_ids_equal_elemtable"] is None
        assert isinstance(v["header_count"], int)


def _with_second_partition(src: str, dst: str, *, damaged: bool) -> str:
    """Copy ``src`` to ``dst`` with its partition duplicated under the next
    stream number (a NON-primary partition; the primary stays untouched),
    the copy's first block body destroyed when ``damaged``."""
    entries = read_entries(src)
    pname = partition_of(src)
    part = next(e for e in entries if e.entry_type == "stream" and e.path == pname)
    data = _smash64(part.data) if damaged else part.data
    second = f"Partitions/{int(pname.split('/')[1]) + 1}"
    write_cfb(dst, entries + [dataclasses.replace(part, path=second, data=data)])
    return second


def test_non_primary_partition_is_walked_by_framing(job, tmp_path, edited):
    """A second partition is judged by its block headers like the primary:
    verbatim copy -> both gates PASS, dicts unchanged by sharing; its first
    block destroyed -> ``crc_failures`` >= 1, structural FAIL (the primary,
    the ElemTable and every edit check still clean)."""
    twin = str(tmp_path / "twin.rvt")
    _with_second_partition(edited, twin, damaged=False)
    v, structural, report, vg = _assert_sharing_is_invisible(
        job, twin, tmp_path, "twin", edited=[LEVEL_ID])
    assert structural["status"] == "PASS" and vg["status"] == "PASS", (structural, vg)
    assert (v["crc_failures"], v["walker_errors"]) == (0, 0)

    bad = str(tmp_path / "twin_bad.rvt")
    second = _with_second_partition(edited, bad, damaged=True)
    v, structural, report, vg = _assert_sharing_is_invisible(
        job, bad, tmp_path, "twin-bad", edited=[LEVEL_ID])
    assert v["crc_failures"] >= 1 and structural["status"] == "FAIL", v
    assert v["ecc_mismatches"] == 0 and v["elemtable_count"] == v["header_count"]
    assert v["edited"][str(LEVEL_ID)]["102"] == {"class": "Level", "clean": True}
    assert vg["status"] == "FAIL"
    assert any(f["where"] == second and "CRC32" in f["message"]
               for f in report["findings"] if f["severity"] == "error")


# ---------------------------------------------------------------------------
# 4. the walk is taken once: a shared walk is not re-read by either gate
# ---------------------------------------------------------------------------
def test_shared_walk_is_taken_once(edited, monkeypatch):
    """Handed the walk, neither gate reads or ECC-verifies the file again
    (one WalkedFile serves both views of a file we just wrote); without it,
    each still walks for itself -- the public API is unchanged."""
    walked = walk_file(edited)
    made = []
    real_init = WalkedFile.__init__

    def counting_init(self, *a, **kw):
        made.append(kw.get("repair", True))
        real_init(self, *a, **kw)
    monkeypatch.setattr(WalkedFile, "__init__", counting_init)
    M.verify_manipulated(edited, edited_ids=[LEVEL_ID], walked=walked)
    validate_file(edited, walked=walked)
    assert made == [], "a gate handed the shared walk walked the file again"
    M.verify_manipulated(edited, edited_ids=[LEVEL_ID])
    validate_file(edited)
    assert made == [False, True]        # verify: the as-stored view; validator: the repaired view


def test_soft_damage_view_shares_what_was_read(tmp_path, edited):
    """On a repaired stream the self-check's as-stored view is a SIBLING of
    the shared walk (same raw bytes, same ECC results -- nothing re-read),
    not the repaired object itself; on a clean file it IS the same object."""
    clean = walk_file(edited)
    assert clean.view(repair=False) is clean
    pname = partition_of(edited)
    bad = rewrite_stream(edited, tmp_path / "soft2.rvt", pname, _flip_bit)
    repaired = walk_file(bad)
    stored = repaired.view(repair=False)
    assert stored is not repaired and not stored.repair
    assert stored.raw(pname) is repaired.raw(pname)          # shared, not re-read
    assert stored.ecc(pname) is repaired.ecc(pname)          # shared, not re-verified
    assert stored.logical(pname) != repaired.logical(pname)  # as stored vs auto-repaired
