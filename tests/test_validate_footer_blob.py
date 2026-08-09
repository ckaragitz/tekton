"""The 0x0f3f unit-footer-blob presence law as a validator rule (issue #7).

Autodesk's open-time audit rejects any file in which a placed instance
walks into a save unit whose 64-byte 0x0f3f footer blob is empty (genesis-
audit VERDICTS #36: E3/E6 FAIL empty, E1b PASS random => presence-only);
an uninstanced empty-blob unit is tolerated (H10 / L_v2 PASSED).  The
writers are long fixed; this rule keeps a regression visible without a
viewer round:

* structure layer: WARNING for every save unit whose blob is not 64 bytes;
* semantic layer: ERROR when a placed instance resolves into such a
  loaded-family unit (instance symbol -> FamilySymbol.m_familyId -> host
  Family famdoc GUID == unit GUID), or when a FamilyInstance's family
  document cannot be resolved at all while a short-blob unit exists.

Fresh-clone runnable: the inputs are the tracked bundled genesis bases and
a one-panel prompt build onto the pinned base (~6 s, built once per module);
the violations are synthesised by rewriting one unit footer in place.

Run: .venv/bin/python -m pytest tests/test_validate_footer_blob.py -q
"""
from __future__ import annotations

import dataclasses
import os
import struct
from contextlib import ExitStack

import pytest

from rvt import ecc
from rvt import partitions as P
from rvt import validate as VA
from rvt.cfb_writer import write_cfb
from rvt.partitions import StreamWalker
from rvt.roundtrip import read_entries
from rvt.validate import UNIT_FOOTER_BLOB_LEN, Validator, main, validate_file

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(ROOT, "plugin", "assets", "genesis")
BASES = {2026: os.path.join(GEN, "G_ABPD.rvt"),
         2025: os.path.join(GEN, "G_ABPD_2025.rvt"),
         2024: os.path.join(GEN, "G_ABPD_2024.rvt")}

pytestmark = pytest.mark.skipif(
    not all(os.path.isfile(p) for p in BASES.values()),
    reason="bundled genesis bases missing")


def _msgs(findings):
    return [f"[{f.severity}/{f.layer}] {f.where}: {f.message}" for f in findings]


def _blob_findings(rep):
    return [f for f in rep.findings if "0x0f3f" in f.message]


def _footer_errors(rep):
    return [f for f in rep.errors if f.where == "unit-footer"]


def _entries(path):
    """Yield (entry, logical, walker) per CFB entry of ``path`` under the
    file's own release; logical/walker are None for non-partition entries."""
    with ExitStack() as stack:
        VA.enter_own_release(stack, path)
        for e in read_entries(path):
            if e.entry_type == "stream" and e.path.startswith("Partitions/"):
                logical = ecc.unframe_stream(e.data)
                w = StreamWalker(logical, inflate=False, keep_data=False)
                assert not w.errors, (path, e.path, w.errors)
                yield e, logical, w
            else:
                yield e, None, None


def census(path):
    """[(stream, unit index, blob len)] for every save unit of ``path``."""
    return [(e.path, u.index, len(u.footer_blob))
            for e, _l, w in _entries(path) if w is not None for u in w.units]


def strip_footer_blob(src, dst, unit_index, new_len=0):
    """Copy ``src`` to ``dst`` with save unit ``unit_index``'s 0x0f3f blob cut
    to ``new_len`` bytes (default: the empty form our writers once emitted).
    Only the one footer changes; the stream is re-framed (CRCIO) and the
    container rewritten, so every other validator check stays green."""
    out, patched_streams = [], 0
    for e, logical, w in _entries(src):
        if w is not None:
            p = w.units[unit_index].footer_offset + len(P.TERMINATOR)
            tag, blen = struct.unpack_from("<HI", logical, p)
            assert tag == P.FOOTER_TAG and blen == UNIT_FOOTER_BLOB_LEN, (tag, blen)
            patched = (logical[:p] + struct.pack("<HI", P.FOOTER_TAG, new_len)
                       + logical[p + 6:p + 6 + new_len] + logical[p + 6 + blen:])
            e = dataclasses.replace(e, data=ecc.frame_stream(patched))
            patched_streams += 1
        out.append(e)
    assert patched_streams == 1, f"expected exactly one Partitions stream in {src}"
    write_cfb(dst, out)
    return dst


# ---------------------------------------------------------------------------
# the law's constant and the certified bases
# ---------------------------------------------------------------------------

def test_blob_length_constant_is_the_writers():
    from rvt.famgen.famdoc_adoc import FOOTER_BLOB_LEN, build_footer
    assert UNIT_FOOTER_BLOB_LEN == FOOTER_BLOB_LEN == len(build_footer(guid="x")) == 64


@pytest.mark.parametrize("year", sorted(BASES))
def test_pinned_bases_carry_the_blob_and_stay_silent(year):
    path = BASES[year]
    assert [n for (_s, _i, n) in census(path)] == [UNIT_FOOTER_BLOB_LEN]
    rep = validate_file(path)
    assert rep.ok, _msgs(rep.errors)
    assert not _blob_findings(rep), _msgs(_blob_findings(rep))


def test_short_blob_on_the_host_unit_is_a_warning(tmp_path):
    """Unit 0 of a base has no loaded family behind it: an empty blob there
    is a writer-hygiene WARNING at the framing layer, never an error."""
    probe = strip_footer_blob(BASES[2024], str(tmp_path / "u0_empty_2024.rvt"), 0)
    assert census(probe) == [("Partitions/21", 0, 0)]
    rep = validate_file(probe)
    assert rep.ok, _msgs(rep.errors)
    hits = _blob_findings(rep)
    assert len(hits) == 1, _msgs(rep.findings)
    f = hits[0]
    assert (f.severity, f.layer, f.where) == ("warning", "structure", "Partitions/21")
    assert "u0:0" in f.message and "not 64 bytes" in f.message


def test_truncated_blob_counts_as_short(tmp_path):
    """Presence means all 64 bytes: a 16-byte blob is flagged like an empty one."""
    probe = strip_footer_blob(BASES[2026], str(tmp_path / "u0_short.rvt"), 0, new_len=16)
    assert census(probe) == [("Partitions/21", 0, 16)]
    rep = validate_file(probe)
    assert rep.ok, _msgs(rep.errors)
    assert [("u0:16" in f.message, f.severity) for f in _blob_findings(rep)] == [(True, "warning")]


# ---------------------------------------------------------------------------
# loaded families: uninstanced (WARNING) vs instanced (ERROR)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """One famgen panelboard loaded onto the pinned base and placed once, via
    the front door's no-key prompt path (the product shape).  Yields the
    load-only stage (family unit, no instance) and the combined deliverable
    (family unit + one placed instance)."""
    import rvt.frontdoor as FD
    out = tmp_path_factory.mktemp("blobrule")
    try:
        r = FD.author(prompt="an electrical room with 1 panel", out=str(out / "job"),
                      no_handoff=True)
    except Exception as e:                                   # pragma: no cover
        pytest.skip(f"prompt build unavailable here: {type(e).__name__}: {e}")
    from rvt.mutate import Document
    assert r.ok, (r.status, r.errors)
    combined = r.manifest["build"]["files"]["combined"]["path"]
    load_only = os.path.join(os.path.dirname(combined), "_stages", "stage_L1_pp1.rvt")
    assert os.path.isfile(combined) and os.path.isfile(load_only)
    instances = {k: sorted(Document.from_file(p).ids_of_class("FamilyInstance"))
                 for k, p in (("load_only", load_only), ("combined", combined))}
    return {"dir": out, "combined": combined, "load_only": load_only,
            "instances": instances,
            # the load-only stage with its family unit's blob emptied (no instance)
            "load_only_u1_empty": strip_footer_blob(load_only, str(out / "L1_u1_empty.rvt"), 1)}


def test_writer_output_carries_the_blob_on_every_unit(built):
    for key in ("load_only", "combined"):
        assert [n for (_s, _i, n) in census(built[key])] == [64, 64], key
        rep = validate_file(built[key])
        assert rep.ok, (key, _msgs(rep.errors))
        assert not _blob_findings(rep), (key, _msgs(_blob_findings(rep)))
    assert built["instances"]["load_only"] == []
    assert len(built["instances"]["combined"]) == 1


def test_uninstanced_empty_blob_unit_is_a_warning(built):
    """H10 / L_v2: a loaded family nobody placed loads fine with an empty
    blob -- reader-tolerated, so WARNING (visible) but the file stays VALID."""
    probe = built["load_only_u1_empty"]
    assert [n for (_s, _i, n) in census(probe)] == [64, 0]
    rep = validate_file(probe)
    assert rep.ok, _msgs(rep.errors)
    hits = _blob_findings(rep)
    assert [(f.severity, f.layer) for f in hits] == [("warning", "structure")], _msgs(hits)
    assert "u1:0" in hits[0].message


def test_instanced_empty_blob_unit_is_an_error(built, capsys):
    """E3/E6: the placed panel's family unit loses its blob => the exact file
    shape Autodesk's audit rejects => INVALID, naming unit and instance."""
    probe = strip_footer_blob(built["combined"], str(built["dir"] / "demo_u1_empty.rvt"), 1)
    rep = validate_file(probe)
    assert not rep.ok
    errs = _footer_errors(rep)
    assert len(errs) == 1 and errs == rep.errors, _msgs(rep.errors)
    msg = errs[0].message
    assert errs[0].layer == "semantic"
    assert "1 placed instance(s) walk into 1/1" in msg and " u1 (" in msg
    assert str(built["instances"]["combined"][0]) in msg and "VERDICTS #36" in msg
    # the framing-layer warning is still there for the same unit
    assert any(f.severity == "warning" and "u1:0" in f.message for f in _blob_findings(rep))
    # and the CLI exits non-zero on it
    assert main([probe, "--quiet"]) == 1
    assert capsys.readouterr().out.startswith("FAIL")


def test_unresolvable_instance_convicts_every_short_unit(built):
    """If a FamilyInstance's symbol -> family -> famdoc GUID chain breaks, the
    validator cannot show the short-blob unit is uninstanced: ERROR.  A
    non-instance owner of an unresolvable symbol id is not evidence, and an
    instance resolving to another family document is not either."""
    probe = built["load_only_u1_empty"]
    sym_ref = [(111, "m_symbolId", 222, "Symbol")]      # owner 111 -> symbol 222
    other_doc = {333: {"12345678-1234-1234-1234-123456789abc"}}
    v = Validator(probe, layers=("structure",))
    with ExitStack() as stack:
        VA.enter_own_release(stack, probe)
        v.run()
        assert v.rep.ok
        v._check_instanced_unit_footers(sym_ref, {}, {}, inst_ids=set())        # not an instance
        v._check_instanced_unit_footers(sym_ref, {222: 333}, other_doc, {111})  # resolved elsewhere
        assert not _footer_errors(v.rep), _msgs(v.rep.findings)
        v._check_instanced_unit_footers(sym_ref, {}, {}, inst_ids={111})        # chain broken
    errs = _footer_errors(v.rep)
    assert len(errs) == 1, _msgs(v.rep.findings)
    assert "could not be resolved" in errs[0].message and "[111]" in errs[0].message
    assert "0 placed instance(s) walk into 0/1" in errs[0].message
