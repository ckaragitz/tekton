"""Every project-rewriting writer keeps the host's partition tail (#941).

#938/#942 made the two project LOADERS keep the host's exact partition tail
(``rvt.partition_tail``).  The other writers that rewrite a project's
partition still read their source DE-PAGED (``doc.logical``) and kept the
walker's ``end_record`` whole, so each re-framed one generation of the
source's final-block CRCIO parity as content.  On the 6-panel ``go author``
project (2026) that was +580 B at the identity stage
(``manipulate.commit_plans``), +578 B at the walls stage and +526 B at the
placement stage (both ``commit.commit_new_elements``).

The writers now read their source with ``partition_tail.writer_logical`` (the
exact content), so the written tail is the host's byte for byte, and their
verifiers (``commit.verify_written``, ``manipulate.verify_manipulated``,
``mep.electrical_data.verify_electrical``, ``commit_created(verify=True)``)
judge it with ``partition_tail.tail_verdict`` against the host they read.

Nothing here claims Revit behaviour (hard rule 4): the fixed outputs differ
from the earlier ones only by the dropped stale bytes, and no viewer round has
been run on them.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from contextlib import ExitStack

import pytest

from conftest import context_constants, ladder_constants, partition_of, rewrite_stream

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(ROOT, "plugin", "assets", "genesis")
BASES = {2026: os.path.join(GEN, "G_ABPD.rvt"),
         2025: os.path.join(GEN, "G_ABPD_2025.rvt"),
         2024: os.path.join(GEN, "G_ABPD_2024.rvt")}
#: bytes after the 10-byte end record in each certified base's exact partition
BASE_STRAY = {2026: 1272, 2025: 2116, 2024: 1252}

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
def _warm_codecs():
    """Seed the lazy codec / schema singletons once (under each base's own
    release) before the leak guard's first snapshot, so it sees only real
    leaks."""
    from rvt.global_framing import enter_own_release
    from rvt.mutate import Document
    for base in BASES.values():
        with ExitStack() as st:
            enter_own_release(st, base)
            Document.from_file(base)


def _own(stack, path):
    from rvt.global_framing import enter_own_release
    enter_own_release(stack, path)


def _tail(path):
    from rvt.partition_tail import host_tail
    with ExitStack() as st:
        _own(st, path)
        return host_tail(path)


def _stage_p(base, out):
    """Stage P (the job identity -> ProjectInfo): one ``commit_plans``."""
    from rvt.frontdoor import project_info as PI
    with ExitStack() as st:
        _own(st, base)
        return PI.stage_project_info(base, out, PI.ProjectIdentity(project_name="T941"))


def _stale(raw):
    """The old defect: 97 bytes of framed junk after the exact content."""
    from rvt import ecc
    from rvt.partition_tail import exact_tail
    ex, _end, _t = exact_tail(raw)
    return ecc.frame_stream(ex + raw[-97:])


# -- the writers ----------------------------------------------------------------

@pytest.mark.parametrize("release", [2026, 2025, 2024])
def test_commit_plans_keeps_the_host_tail(release, tmp_path):
    """``manipulate.commit_plans`` (stage P identity, levels, edits, famload
    pass 3): the written tail is the host's; its verifier says so."""
    from rvt import manipulate as M
    base = BASES[release]
    out = str(tmp_path / f"p_{release}.rvt")
    rec = _stage_p(base, out)
    assert rec["ok"], rec.get("blocker")
    pt = rec["commit"]["partition_tail"]
    assert pt["exact"] and pt["kept_host_tail"], pt
    assert pt["host_tail_bytes"] == BASE_STRAY[release] + 10
    assert _tail(out) == _tail(base)
    ver = M.verify_manipulated(out, edited_ids=[rec["elem_id"]], host_rvt=base)
    vt = ver["partition_tail"]
    assert vt["ok"] and vt["equals_host_tail"] and vt["host_tail_known"], vt
    assert vt["stray_bytes"] == BASE_STRAY[release]
    assert "partition_tail_defect" not in ver


def _element(base):
    """One deterministic new host-document element on ``base`` (a level work
    plane, as ``test_identity_helper_657``) + its framed records."""
    from rvt.mep.devices import add_level_datum_plane
    from rvt.mutate import Document
    doc = Document.from_file(base)
    el = add_level_datum_plane(doc, doc.levels()[0]["id"], (1.0, 2.0))
    return doc, el, dict(doc.serialize(el))


@pytest.mark.parametrize("release", [2026, 2025, 2024])
def test_commit_new_elements_keeps_the_host_tail(release, tmp_path):
    """``commit.commit_new_elements`` (walls, equipment, mep, loader pass 1):
    one new element committed, the host's tail kept, every other partition
    byte up to the end record the writer's own."""
    from rvt.commit import commit_new_elements, verify_written
    from rvt.frontdoor.release_ctx import release_build_context
    base = BASES[release]
    out = str(tmp_path / f"c_{release}.rvt")
    with release_build_context(base):
        _doc, el, recs = _element(base)
        crep = commit_new_elements(base, out, [recs], [el.elemrec])
        ver = verify_written(out, [el.elem_id], host_rvt=base)   # walks under the caller's release
    assert crep.partition_tail["exact"] and crep.partition_tail["kept_host_tail"]
    assert crep.partition_tail["host_tail_bytes"] == BASE_STRAY[release] + 10
    assert _tail(out) == _tail(base)
    assert ver["partition_tail"]["ok"] and ver["partition_tail"]["equals_host_tail"]
    assert ver["ecc_mismatches"] == 0 and ver["walker_errors"] == 0
    assert all(ver["new_ids_found"][s] for s in (101, 102, 103))


def test_chained_rewrites_do_not_grow_the_tail(tmp_path):
    """P -> commit -> P again (three writers in a chain) all keep the BASE's
    tail: no generation accumulates."""
    from rvt.commit import commit_new_elements
    base = BASES[2026]
    p1 = str(tmp_path / "p1.rvt")
    assert _stage_p(base, p1)["ok"]
    c = str(tmp_path / "c.rvt")
    _doc, el, recs = _element(p1)
    commit_new_elements(p1, c, [recs], [el.elemrec])
    p2 = str(tmp_path / "p2.rvt")
    assert _stage_p(c, p2)["ok"]
    host = _tail(base)
    assert _tail(p1) == _tail(c) == _tail(p2) == host


def test_electrical_and_conduit_commits_keep_the_host_tail(tmp_path):
    """``mep.electrical_data.commit_electrical`` and ``mep.conduit
    .commit_created`` read the host exactly too."""
    from rvt.mep import conduit as C
    from rvt.mep import electrical_data as ED
    base = BASES[2026]
    e_out = str(tmp_path / "e.rvt")
    c_out = str(tmp_path / "cd.rvt")
    doc, el, _recs = _element(base)
    erep = ED.commit_electrical(base, e_out, doc, new_elements=[el])
    doc, el, _recs = _element(base)
    crep = C.commit_created(base, c_out, doc, [C.ConduitPlan("conduit", curves=[el])],
                            verify=True)
    assert erep.partition_tail["kept_host_tail"]
    assert crep["partition_tail"]["kept_host_tail"]
    host = _tail(base)
    assert _tail(e_out) == host and _tail(c_out) == host
    v = ED.verify_electrical(e_out, host_rvt=base)
    assert v["partition_tail"]["equals_host_tail"] and v["structurally_valid"], v
    assert crep["verify_written"]["partition_tail"]["equals_host_tail"]


# -- the verifiers name a stale suffix -------------------------------------------

def test_verifiers_flag_stale_parity(tmp_path):
    """A rewritten file whose partition carries extra bytes after the host's
    tail fails each writer's own verification by name."""
    from rvt import manipulate as M
    from rvt.commit import verify_written
    from rvt.mep import electrical_data as ED
    base = BASES[2026]
    good = str(tmp_path / "good.rvt")
    rec = _stage_p(base, good)
    assert rec["ok"]
    bad = rewrite_stream(good, str(tmp_path / "bad.rvt"), partition_of(good), _stale)
    vm = M.verify_manipulated(bad, edited_ids=[rec["elem_id"]], host_rvt=base)
    assert vm["partition_tail"]["ok"] is False
    assert vm["partition_tail"]["tail_bytes"] == len(_tail(base)) + 97
    assert vm["partition_tail_defect"].startswith("partition tail:"), vm["partition_tail_defect"]
    vw = verify_written(bad, [], host_rvt=base)
    assert vw["partition_tail"]["ok"] is False and "partition_tail_defect" in vw
    assert ED.verify_electrical(bad, host_rvt=base)["structurally_valid"] is False
    # without the host the tail is only judged to start on the end record
    v2 = M.verify_manipulated(bad, edited_ids=[rec["elem_id"]])
    assert v2["partition_tail"]["ok"] and "expected_tail_bytes" not in v2["partition_tail"]


def test_writer_logical_falls_back_to_the_depaged_read():
    """A source whose final block does not decode exactly (an Autodesk-born
    block with heap bytes in its pad region) is read de-paged, as before #941,
    and the report says the host tail is unknown; a framed one is read exactly."""
    from rvt import ecc
    from rvt.container import depage, open_rvt
    from rvt.partition_tail import tail_defect, writer_logical

    class _Doc:
        def __init__(self, raw):
            self._raw = raw

        def raw(self, _name):
            return self._raw

        def logical(self, _name):
            return depage(self._raw)

    junk = b"\x00" * 7
    got, rep = writer_logical(_Doc(junk), "Partitions/0")
    assert got == depage(junk) and rep["exact"] is False and "why" in rep
    with open_rvt(BASES[2026]) as f:
        raw = f.raw(f.partition_streams()[0])
    got, rep = writer_logical(_Doc(raw), "Partitions/0")
    assert got == ecc.unframe_stream(raw) and rep["exact"] is True
    assert tail_defect(None) is None and tail_defect({"ok": None}) is None


# -- end to end: the 6-panel go author ---------------------------------------------

@pytest.mark.slow
def test_go_author_stages_all_keep_the_base_tail(tmp_path):
    """The 6-panel prompt project (2026): stage P (identity), L (batch load),
    W (walls) and the placed output all end on the BASE's exact tail (before
    #941: 1,852 / 1,852 / 2,430 / 2,956 B after the end record)."""
    out = str(tmp_path / "j")
    env = dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src"), TEKTON_ROOT=ROOT)
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "frontdoor.py"), "author",
                        "--prompt", "an electrical room with 6 panels", "--target-version", "2026",
                        "--out", out, "--json"], cwd=ROOT, env=env, capture_output=True,
                       text=True, timeout=600)
    assert r.returncode == 0, r.stderr[-2000:]
    res = json.loads(r.stdout[r.stdout.index("{"):])
    assert res.get("ok"), res.get("errors")
    host = _tail(BASES[2026])
    stages = [os.path.join(out, "_stages", n) for n in
              ("stage_P_identity.rvt", "stage_L_loaded.rvt", "stage_W_walls.rvt")]
    files = [p for p in stages if os.path.isfile(p)] + [os.path.join(out, "prompt_room.rvt")]
    assert len(files) == 4, files
    for p in files:
        assert _tail(p) == host, (p, len(_tail(p)), len(host))
