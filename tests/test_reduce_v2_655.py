"""``rvt.reduce_v2`` after #655: the partition-stream end record ``u16 ContentMarker, i32 0, i32 -1`` is built from
the ContentMarker ordinal IN FORCE (``rvt.partitions.CONTAINER_CLASS``, bound by name from the file's own schema by
``rvt.versions.reading`` / the front door's ``host_release_context``), never from a by-value ``0x3a3``.  So
``remove_units_v2`` -- one loaded family removed COHERENTLY from a project (unit spliced out, ContentDocuments rebuilt,
ContentTable + FamilyMgr reconciled) -- runs on the 2025 and 2024 pins as it always did on 2026, and the 2026 output is
byte-identical to what ``main`` @ ``3ec84d7`` wrote for the same deterministic input (the before/after table is in
docs/inbox/shard-docs-audit.d/655-reduce-v2-end-record.md).  Pinned genesis bases only: fresh-clone safe."""
from __future__ import annotations

import contextlib
import itertools
import struct
import uuid
import zlib

import pytest

import conftest as C
import rvt.versions as V
from rvt import famload as FL
from rvt import partitions as P
from rvt import reduce_law as RL
from rvt import reduce_v2 as RV
from rvt.famgen import heads as H
from rvt.frontdoor import base as B
from rvt.frontdoor.release_ctx import host_release_context
from rvt.validate import validate_file

pytestmark = pytest.mark.usefixtures("no_release_leak")


@pytest.fixture
def release_leak_extra():
    return C.ladder_constants


# --- the ordinal comes from the name lookup, not a literal ---------------------------------------------------------

def test_part_end_record_follows_the_container_class_in_force():
    native = RV.part_end_record()
    assert native == struct.pack("<Hii", V.framing_table(V.LATEST_RELEASE)["CONTAINER_CLASS"], 0, -1)
    assert len(native) == 10
    for year in C.FOREIGN:
        with V.reading(year=year) as ords:                             # the production by-name binding of a release
            assert RV.part_end_record() == struct.pack("<Hii", ords["CONTAINER_CLASS"], 0, -1) != native
    with pytest.MonkeyPatch.context() as mp:                          # and whatever ANY binding puts there ...
        mp.setattr(P, "CONTAINER_CLASS", 0x1234)
        assert RV.part_end_record() == struct.pack("<Hii", 0x1234, 0, -1)   # ... the end record follows it
    assert RV.part_end_record() == native
    assert not hasattr(RV, "PART_END_RECORD")                           # the by-value constant is gone, not aliased


# --- remove_units_v2 on every certified pin ---------------------------------------------------------------------------

@contextlib.contextmanager
def _pinned_uuid4():
    """``uuid.uuid4`` replaced by a counter for the block: famload's content / document / session GUIDs become
    reproducible, so the loaded host -- and everything built from it -- has stable bytes."""
    counter = itertools.count(1)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(uuid, "uuid4", lambda: uuid.UUID(int=(0x655 << 64) | next(counter), version=4))
        yield


@pytest.fixture(scope="module")
def hosts(tmp_path_factory):
    """Per certified year: the pin + ONE constructor-built section head loaded four-registry by ``rvt.famload``
    (which enters the host's release itself) -> ``(host path, the loaded document's content GUID)``."""
    out = {}
    for year in C.FOREIGN_FIRST:
        host = str(tmp_path_factory.mktemp(f"h{year}") / f"host{year}.rvt")   # fixed basename -> fixed BasicFileInfo
        with _pinned_uuid4():                                                     # same GUIDs on every pin
            res = FL.load_family_document(C.pinned_base(year), H.family_load("section_head_open"), host,
                                          name="section_head_open", validate=False)
        assert res.ok, res.stop_reason
        out[year] = (host, str(res.plans[0].guid).lower())
    return out


@pytest.mark.parametrize("reconcile", [True, False], ids=["reconciled", "registries-left"])
@pytest.mark.parametrize("year", C.FOREIGN_FIRST)
def test_remove_units_v2_on_each_certified_pin(hosts, tmp_path, year, reconcile):
    host, guid = hosts[year]
    out = str(tmp_path / f"S4_{year}_{int(reconcile)}.rvt")
    with host_release_context(host):                                    # the caller's context, as every lane holds it
        rep = RV.remove_units_v2(host, [guid], out, reconcile_adocument=reconcile)
        expected_end = RV.part_end_record()
        exact = RV.exact_partition_logical(out, rep["partition"]["stream"])
        _ranges, w = RV.unit_ranges(exact)
        law = RL.check_files(host, out)
    # the unit is gone, the stream ends with THIS release's end record and nothing after it
    assert rep["partition"]["units_before"] == 2 and rep["partition"]["units_after"] == 1
    removed = rep["partition"]["removed"]
    assert [r["guid"] for r in removed] == [guid]
    assert exact[w.end_offset:] == expected_end
    assert expected_end[:2] == struct.pack("<H", V.framing_table(year)["CONTAINER_CLASS"])
    assert rep["removed_guid_sets_equal"] is True
    assert rep["content_documents"]["entries_before"] == 1 and rep["content_documents"]["entries_after"] == 0
    post = rep["post"]
    assert post["partition_end_record_ok"] and post["partition_tail_junk_bytes"] == 0
    assert post["cd_end_record_ok"] and post["cd_grammar_roundtrip_ok"]
    if reconcile:
        assert rep["adocument"]["removed_guids_still_referenced"] == [] and rep["adocument"]["decodes_clean"]
        assert post["coherent"] is True
    else:
        assert rep["adocument"]["dangling_content_guids_left_in_registries"] == [guid]
        assert post["coherent"] is False and post["sets"]["content_table_minus_units"] == [guid]
    # 0 errors under the file's OWN release, resolved from its own schema (necessary, never sufficient -- rule 4)
    v = validate_file(out).to_json()
    assert v["ok"] and v["counts"].get("error", 0) == 0, v["findings"][:3]
    assert not [f for f in v["findings"] if f.get("where") == "release"]     # no fallback rung was needed
    assert V.detect_release(out) == year
    # rule 5: the removed document's records go WITH it; every survivor byte-identical
    assert (law.verdict, law.added, len(law.survivors_edited)) == ("EDIT-FREE", [], 0)
    assert law.removed == removed[0]["counter"]                            # exactly the unit's own records


#: sha256 (first 16 hex) of the deterministic case per pin: the famload'ed host (the INPUT), then remove_units_v2's
#: output with / without the ADocument reconciliation.  The 2026 pair equals main @ 3ec84d7 byte for byte (the #655
#: record); 2025 / 2024 raised "unexpected partition end record: 9103... / 7b03..." there and produce these now.
HOST_DIGEST = {2026: "a6d27bfaf4b31a58", 2025: "d6b06ae72df4fc02", 2024: "3ffab85827c48462"}
OUT_DIGEST = {
    (2026, True): "199e0f07b2b33e5c", (2026, False): "87720c3b48997d76",
    (2025, True): "4d841ea2a63fe1c9", (2025, False): "1d48e58432f3c1bd",
    (2024, True): "f456924467c26cfc", (2024, False): "32341bb256b08e72",
}


@pytest.mark.parametrize("year", C.FOREIGN_FIRST)
def test_output_bytes_are_the_pinned_digests(hosts, tmp_path, year):
    """Byte identity, told apart from input drift: when famload / commit / the head constructor / the zlib build
    write a different HOST for the pinned case, this row SKIPS saying so (that is not reduce_v2's to judge -- the
    semantic rows above still ran); when the host is the pinned one, remove_units_v2's bytes must be too."""
    host, guid = hosts[year]
    if B.sha256_of(host)[:16] != HOST_DIGEST[year]:
        pytest.skip(f"INPUT drift on {year}: the famload'ed host is no longer {HOST_DIGEST[year]} "
                    f"(zlib {zlib.ZLIB_RUNTIME_VERSION}) -- re-pin HOST_DIGEST + OUT_DIGEST from these files "
                    f"once the semantic rows are green")
    for reconcile in (True, False):
        out = str(tmp_path / f"D_{year}_{int(reconcile)}.rvt")
        with host_release_context(host):
            RV.remove_units_v2(host, [guid], out, reconcile_adocument=reconcile)
        assert B.sha256_of(out)[:16] == OUT_DIGEST[(year, reconcile)], (
            f"remove_units_v2's output on {year} (reconcile={reconcile}) changed while its input did not")
