"""Tests for rvt.reduce_v2 -- coherent embedded-document (save-unit) removal
on top of the SOLVED ContentDocuments grammar (BUG B / genesis-triage-b)."""
import json
import os
import uuid

import pytest

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
RST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
R9 = os.path.join(ROOT, "experiments", "genesis", "R9.rvt")
R9B = os.path.join(ROOT, "experiments", "genesis", "R9b.rvt")
R9B_JSON = os.path.join(ROOT, "experiments", "genesis", "R9b.json")

from rvt import reduce_v2 as RV                              # noqa: E402

needs_rst = pytest.mark.skipif(not os.path.exists(RST), reason="sample missing")
needs_r9 = pytest.mark.skipif(not (os.path.exists(R9) and os.path.exists(R9B_JSON)),
                              reason="R9 ladder files missing")


# ---------------------------------------------------------------------------
# framing / tiling
# ---------------------------------------------------------------------------

@needs_rst
def test_partition_end_record_is_canonical_10_bytes():
    """Autodesk's own logical partition stream ends EXACTLY with the 10-byte
    end record (u16 ContentMarker = 0x3a3 on this 2026 sample, i32 0, i32 -1)
    -- ECC-exact, no trailing junk."""
    ex = RV.exact_partition_logical(RST, "Partitions/21")
    _rngs, w = RV.unit_ranges(ex)
    assert ex[w.end_offset:] == RV.part_end_record()
    assert len(RV.part_end_record()) == 10


@needs_rst
def test_unit_ranges_tile_and_counters_match():
    ex = RV.exact_partition_logical(RST, "Partitions/21")
    rngs, w = RV.unit_ranges(ex)
    assert rngs[0].start == RV.PART_HDR_LEN and rngs[0].index == 0
    for a, b in zip(rngs, rngs[1:]):
        assert a.end == b.start                                  # tiles exactly
    assert rngs[-1].end == w.end_offset
    # 52 embedded documents in rstbasic, every unit-k has a GUID
    embedded = [r for r in rngs if r.index]
    assert len(embedded) == 52
    assert all(r.guid for r in embedded)
    assert len({r.guid for r in embedded}) == 52


@needs_rst
def test_splice_identity_and_exact_tail():
    ex = RV.exact_partition_logical(RST, "Partitions/21")
    sp = RV.splice_units(ex, [], exact_tail=False)             # remove nothing
    assert sp["logical"] == ex and sp["removed"] == []
    sp2 = RV.splice_units(ex, [], exact_tail=True)
    assert sp2["logical"] == ex                                  # source has 0 junk
    assert sp2["junk_after_end_record_dropped"] == 0
    # unknown GUID -> reported, nothing removed
    sp3 = RV.splice_units(ex, [str(uuid.uuid4())], exact_tail=True)
    assert sp3["removed"] == [] and len(sp3["guids_not_found"]) == 1


# ---------------------------------------------------------------------------
# ContentDocuments (solved grammar)
# ---------------------------------------------------------------------------

@needs_rst
def test_rebuild_content_documents_identity_and_removal():
    from rvt.container import open_rvt
    from rvt.famgen.factory import CD_END_RECORD, parse_content_documents
    with open_rvt(RST) as f:
        cd = b"".join(f.inflate_all("Global/ContentDocuments"))
    r0 = RV.rebuild_content_documents(cd, [])
    assert r0["payload"] == cd and r0["entries_after"] == 52   # grammar identity
    ents, _t = parse_content_documents(cd)
    victims = [g for g, _a in ents[:3]]
    r = RV.rebuild_content_documents(cd, victims)
    assert r["entries_after"] == 49 and len(r["removed"]) == 3
    e2, t2 = parse_content_documents(r["payload"])
    assert t2 == CD_END_RECORD                                  # end record kept
    assert not ({g for g, _a in e2} & set(victims))
    keys = [uuid.UUID(g).bytes_le for g, _a in e2]
    assert keys == sorted(keys)                                  # GUID bytes_le sorted


@needs_r9
def test_old_cd_splice_equals_solved_rebuild():
    """The old path's ContentDocuments output (R9b) is byte-identical to the
    solved-grammar rebuild for the same GUID set -- the CD splice per se is
    NOT the R9b malformation (Bug B lives in coherence + the junk tail)."""
    from rvt.container import open_rvt
    with open_rvt(R9) as f:
        cd9 = b"".join(f.inflate_all("Global/ContentDocuments"))
    with open_rvt(R9B) as f:
        cd9b = b"".join(f.inflate_all("Global/ContentDocuments"))
    removed = RV._r9b_removed_guids()
    assert RV.rebuild_content_documents(cd9, removed)["payload"] == cd9b


# ---------------------------------------------------------------------------
# ADocument content-registry reconciliation
# ---------------------------------------------------------------------------

def _fake_adoc(guids_ct, fm_entries):
    return {
        "m_oContentTable": {"ptr_class": "ContentTable", "pid": -1, "value": {
            "m_pHostDocument": {"weakref": 1},
            "m_ContentRecSet": [{"m_ContentKey": {"m_guidKey": g},
                                  "m_author": "x"} for g in guids_ct]}},
        "m_pAppInfoManager": {"ptr_class": "AppInfoManager", "pid": -1, "value": {
            "m_appInfoArr": [
                {"ptr_class": "OtherAppInfo", "pid": -1, "value": {"a": 1}},
                {"ptr_class": "FamilyMgr", "pid": -1, "value": {
                    "m_arrLoadedFamilyInfo": [
                        {"m_surrogateId": sid, "m_familyDocGUIDs": list(gs)}
                        for sid, gs in fm_entries]}}]}},
    }


def test_reconcile_content_registry_drops_and_edits():
    A, B, C = (str(uuid.uuid4()) for _ in range(3))
    v = _fake_adoc([A, B, C], [(10, [A]), (11, [B, C]), (12, [])])
    nv, rep = RV.reconcile_content_registry(v, [A, B])
    reg = RV.content_registry(nv)
    assert reg["content_table_guids"] == [C]                      # A, B records dropped
    # entry 10 (only A) dropped; entry 11 keeps C (B edited out); 12 (empty) kept
    fm = reg["familymgr"]
    assert [e["surrogate_id"] for e in fm] == [11, 12]
    assert fm[0]["guids"] == [C]
    assert rep["content_table_dropped"] == sorted([A, B])
    assert [d["surrogate_id"] for d in rep["familymgr_entries_dropped"]] == [10]
    assert rep["familymgr_entries_edited"] == [{"surrogate_id": 11, "removed": [B]}]
    assert rep["guids_not_referenced"] == []
    # the input tree is untouched (deep copy)
    assert len(RV.content_registry(v)["content_table_guids"]) == 3
    # a GUID the registries do not know is reported, not silently ignored
    _nv2, rep2 = RV.reconcile_content_registry(v, [str(uuid.uuid4())])
    assert len(rep2["guids_not_referenced"]) == 1


@needs_rst
def test_content_registry_on_real_sample_covers_all_units():
    from rvt.adocument import decode_latest
    from rvt.container import open_rvt
    with open_rvt(RST) as f:
        lat = f.inflate("Global/Latest")
    reg = RV.content_registry(decode_latest(lat).value)
    ct = set(reg["content_table_guids"])
    fm = {g for e in reg["familymgr"] for g in e["guids"]}
    ex = RV.exact_partition_logical(RST, "Partitions/21")
    rngs, _w = RV.unit_ranges(ex)
    units = {r.guid for r in rngs if r.index}
    assert ct == units == fm and len(units) == 52


# ---------------------------------------------------------------------------
# end-to-end: the corrected recipe
# ---------------------------------------------------------------------------

@needs_r9
def test_remove_units_v2_single_document_is_coherent(tmp_path):
    from rvt.reduce import verify_reduced
    out = tmp_path / "one.rvt"
    rep = RV.remove_units_v2(R9, [RV.B1_GUID], str(out),
                             reconcile_adocument=True, exact_tail=True)
    assert rep["removed_guid_sets_equal"] is True
    assert rep["partition"]["units_after"] == rep["partition"]["units_before"] - 1
    assert rep["content_documents"]["entries_after"] == \
        rep["content_documents"]["entries_before"] - 1
    ad = rep["adocument"]
    assert ad["content_table_after"] == ad["content_table_before"] - 1
    assert ad["removed_guids_still_referenced"] == [] and ad["decodes_clean"]
    # the file is CONTENT-COHERENT and structurally healthy
    coh = RV.verify_content_coherence(str(out))
    assert coh["coherent"] is True
    assert coh["partition_tail_junk_bytes"] == 0                # canonical end record
    assert coh["cd_end_record_ok"] and coh["cd_grammar_roundtrip_ok"]
    v = verify_reduced(str(out))
    assert v["ok"], v


@needs_r9
def test_remove_units_v2_without_reconciliation_leaves_dangling_guids(tmp_path):
    out = tmp_path / "incoherent.rvt"
    rep = RV.remove_units_v2(R9, [RV.B1_GUID], str(out),
                             reconcile_adocument=False, exact_tail=True)
    assert rep["adocument"]["reconciled"] is False
    assert rep["adocument"]["dangling_content_guids_left_in_registries"] == [RV.B1_GUID]
    coh = RV.verify_content_coherence(str(out))
    assert coh["coherent"] is False
    assert coh["sets"]["content_table_minus_units"] == [RV.B1_GUID]


@needs_r9
def test_r9b_is_measurably_incoherent_with_junk_tail():
    """The known-FAILING R9b: registries name 38 removed documents and the
    partition stream carries 294 bytes of ECC junk after the end record."""
    coh = RV.verify_content_coherence(R9B)
    assert coh["coherent"] is False
    assert len(coh["sets"]["content_table_minus_units"]) == 38
    assert coh["partition_tail_junk_bytes"] == 294


@needs_r9
def test_validate_probe_file(tmp_path):
    """A v2 removal validates with 0 errors (validator-clean is necessary,
    the viewer is the arbiter)."""
    from rvt.validate import validate_file
    out = tmp_path / "v.rvt"
    RV.remove_units_v2(R9, [RV.B1_GUID], str(out))
    assert validate_file(str(out)).ok


def test_family_units_names_documents():
    if not os.path.exists(RST):
        pytest.skip("sample missing")
    rows = RV.family_units(RST)
    assert len(rows) == 52
    named = [r for r in rows if r["family_name"]]
    assert any(r["family_name"] == "M_Concrete-Square-Column" for r in named)
    b1 = [r for r in rows if r["guid"] == RV.B1_GUID]
    assert b1 and b1[0]["unit"] == 36


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
