"""``rvt.reduce_v2`` after #671: every path-taking entry enters the file's OWN release itself, the way every other
engine entry does -- ``remove_units_v2`` under ``rvt.frontdoor.release_ctx.host_release_context`` (the write-side
entry; a caller's same-release context is JOINED, not re-applied), ``verify_content_coherence`` / ``family_units`` /
``python -m rvt.reduce_v2 --coherence FILE`` on ``rvt.global_framing.enter_own_release`` (the read-side ladder, its
rung reported as ``release_note``).  So a BARE call on a 2025 / 2024 project writes exactly the bytes #655 pinned
under the caller's context (instead of ``unexpected Partitions header: v=9 cls=0x391``), and the coherence census of a
foreign file counts its registries instead of raising or reading ``units N / ContentDocuments 0``.  The famload'ed
hosts and the digests are #655's own (imported, not copied); pinned genesis bases only: fresh-clone safe."""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

import conftest as C
import rvt.versions as V
from rvt import partitions as P
from rvt import reduce_v2 as RV
from rvt.frontdoor import base as B
from rvt.frontdoor import release_ctx as RC
from test_reduce_v2_655 import HOST_DIGEST, OUT_DIGEST, hosts  # noqa: F401 -- the fixture: pin + ONE loaded head per year

pytestmark = pytest.mark.usefixtures("no_release_leak")


@pytest.fixture
def release_leak_extra():
    return C.ladder_constants


# --- the writer: bare == wrapped, byte for byte (2026 included: its documented use must not move) -----------------------

@pytest.mark.parametrize("reconcile", [True, False], ids=["reconciled", "registries-left"])
@pytest.mark.parametrize("year", C.FOREIGN_FIRST)
def test_a_bare_call_writes_what_the_wrapped_call_writes(hosts, tmp_path, year, reconcile):
    host, guid = hosts[year]
    bare = str(tmp_path / f"bare_{year}_{int(reconcile)}.rvt")
    wrapped = str(tmp_path / f"wrapped_{year}_{int(reconcile)}.rvt")
    rep = RV.remove_units_v2(host, [guid], bare, reconcile_adocument=reconcile)      # no context: it enters its own
    assert RC.active_release() is None                                                # ... and left it again
    with RC.host_release_context(host):                                               # the way #655 (and every lane) held it
        RV.remove_units_v2(host, [guid], wrapped, reconcile_adocument=reconcile)
    with open(bare, "rb") as fb, open(wrapped, "rb") as fw:
        assert fb.read() == fw.read(), f"bare != wrapped on {year} (reconcile={reconcile})"
    assert rep["partition"]["units_before"] == 2 and rep["partition"]["units_after"] == 1   # a removal, not two no-ops
    assert rep["post"]["coherent"] is reconcile                                       # the writer's own census, in its context
    if B.sha256_of(host)[:16] == HOST_DIGEST[year]:                                   # #655's pinned input -> its pinned output
        assert B.sha256_of(bare)[:16] == OUT_DIGEST[(year, reconcile)]


# --- the instruments: a foreign file is read, not mis-read ------------------------------------------------------------

@pytest.mark.parametrize("year", C.FOREIGN)
def test_the_coherence_census_counts_a_foreign_files_registries_bare(hosts, tmp_path, year):
    host, guid = hosts[year]
    coh = RV.verify_content_coherence(host)                        # the pin + one loaded document: 2 units, 1 of each
    assert coh["release_note"] is None                             # its own schema settled the framing
    assert (coh["partition_units"], coh["cd_entries"], coh["content_table_records"], coh["familymgr_guids"]) == (2, 1, 1, 1)
    assert coh["coherent"] is True and coh["partition_end_record_ok"] is True
    out = str(tmp_path / f"S4_{year}.rvt")
    RV.remove_units_v2(host, [guid], out)
    after = RV.verify_content_coherence(out)                       # the OUTPUT re-read bare, outside the writer's context
    assert (after["partition_units"], after["cd_entries"], after["coherent"], after["release_note"]) == (1, 0, True, None)
    assert after["partition_tail_junk_bytes"] == 0                 # the canonical end record, nothing after it
    rows = RV.family_units(host)                                   # the name-lookup helper walks the file too
    assert [(r["unit"], r["guid"]) for r in rows] == [(1, guid)] and rows[0]["family_name"]


def test_the_module_door_measures_a_foreign_file_bare(hosts):
    """The real ``python -m rvt.reduce_v2 --coherence`` door: a fresh interpreter (nothing but ``src`` on the path, no
    context anything could have left behind) on the oldest certified foreign pin's host."""
    if not C.FOREIGN:
        pytest.skip("no certified foreign-release pin")
    host, _guid = hosts[min(C.FOREIGN)]
    run = subprocess.run([sys.executable, "-m", "rvt.reduce_v2", "--coherence", host], capture_output=True, text=True,
                         env=dict(os.environ, PYTHONPATH=C.SRC), cwd=C.ROOT, timeout=300)
    assert run.returncode == 0 and run.stderr == "", (run.stdout + run.stderr)[-2000:]
    rep = json.loads(run.stdout)
    assert (rep["coherent"], rep["partition_units"], rep["cd_entries"], rep["release_note"]) == (True, 2, 1, None)


# --- the context discipline: join, refuse, type -----------------------------------------------------------------------

@pytest.mark.parametrize("year", C.FOREIGN)
def test_an_active_same_release_context_is_joined_not_re_entered(hosts, tmp_path, year):
    host, guid = hosts[year]
    out = str(tmp_path / f"joined_{year}.rvt")
    with RC.host_release_context(host) as outer:
        assert RC.active_release() == year
        rep = RV.remove_units_v2(host, [guid], out)
        coh = RV.verify_content_coherence(out)
        # the caller's context is still the one in force: joined on the way in, left standing on the way out
        assert RC.active_release() == year
        assert P.CONTAINER_CLASS == V.framing_table(year)["CONTAINER_CLASS"]
        with RC.host_release_context(host) as again:               # and it is still THE context a same-release entry joins
            assert again is outer
    assert RC.active_release() is None
    assert rep["post"]["coherent"] is True and coh["coherent"] is True and coh["release_note"] is None
    if B.sha256_of(host)[:16] == HOST_DIGEST[year]:
        assert B.sha256_of(out)[:16] == OUT_DIGEST[(year, True)]     # the joined call wrote the pinned bytes too


def test_a_context_of_another_foreign_release_is_refused_not_stacked(hosts, tmp_path):
    if len(C.FOREIGN) < 2:
        pytest.skip("needs two certified foreign pins")
    (host_a, _), (host_b, guid_b) = hosts[C.FOREIGN[0]], hosts[C.FOREIGN[1]]
    with RC.host_release_context(host_a):
        with pytest.raises(RC.ReleaseContextError, match="release context is active; cannot enter"):
            RV.remove_units_v2(host_b, [guid_b], str(tmp_path / "never.rvt"))
        assert RC.active_release() == C.FOREIGN[0]                 # the refusal left the outer context intact
    assert not os.path.exists(tmp_path / "never.rvt")


def test_an_unreadable_source_is_the_typed_release_error_not_a_walker_dump(tmp_path):
    bogus = tmp_path / "notes.rvt"
    bogus.write_text("not a Revit container\n")
    with pytest.raises(RC.UnreadableHost) as ei:
        RV.remove_units_v2(str(bogus), ["09982dbb-c022-48fc-a116-6d8ba6867fdb"], str(tmp_path / "out.rvt"))
    assert isinstance(ei.value, RC.ReleaseContextError)
    assert ei.value.what == "not a Revit container tekton can open"
