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

Fresh-clone runnable (tracked bundled bases only; edits and damaged copies are
written to ``tmp_path``); in the CI shard via tests/ci_shard.d/.

Run: .venv/bin/python -m pytest tests/test_gates_shared_walk.py -q
"""
from __future__ import annotations

import dataclasses
import os

import pytest

from rvt import ecc
from rvt import manipulate as M
from rvt import partitions as P
from rvt import versions as V
from rvt.cfb_writer import write_cfb
from rvt.container import open_rvt
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


@pytest.fixture(scope="module")
def job():
    """``tools/rvt_job.py`` -- the gate verdict functions both doors use."""
    from rvt.frontdoor.edit import load_job_module
    return load_job_module()


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


def _rewrite_stream(src: str, dst: str, name: str, mutate) -> None:
    """Copy ``src`` to ``dst`` with stream ``name``'s RAW bytes passed
    through ``mutate(bytearray) -> None``; every other entry verbatim."""
    entries = read_entries(src)
    out = []
    for e in entries:
        if e.entry_type == "stream" and e.path == name:
            raw = bytearray(e.data)
            mutate(raw)
            e = dataclasses.replace(e, data=bytes(raw))
        out.append(e)
    write_cfb(dst, out)


def _partition(path: str) -> str:
    with open_rvt(path) as doc:
        return doc.partition_streams()[0]


# an offset inside the first block's deflate body of a Partitions/<N> stream:
# 44-byte stream header + 26-byte block header + 10-byte gzip header + a bit
_IN_FIRST_MEMBER = 44 + 26 + 10 + 200


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
    bad = str(tmp_path / "hard.rvt")
    pname = _partition(edited)

    def smash(raw):
        raw[_IN_FIRST_MEMBER:_IN_FIRST_MEMBER + 64] = b"\xff" * 64
    _rewrite_stream(edited, bad, pname, smash)
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
    bad = str(tmp_path / "soft.rvt")
    pname = _partition(edited)

    def flip(raw):
        raw[_IN_FIRST_MEMBER] ^= 0x04
    _rewrite_stream(edited, bad, pname, flip)
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
    bad = str(tmp_path / "soft2.rvt")
    pname = _partition(edited)

    def flip(raw):
        raw[_IN_FIRST_MEMBER] ^= 0x04
    _rewrite_stream(edited, bad, pname, flip)
    repaired = walk_file(bad)
    stored = repaired.view(repair=False)
    assert stored is not repaired and not stored.repair
    assert stored.raw(pname) is repaired.raw(pname)          # shared, not re-read
    assert stored.ecc(pname) is repaired.ecc(pname)          # shared, not re-verified
    assert stored.logical(pname) != repaired.logical(pname)  # as stored vs auto-repaired
