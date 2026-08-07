"""commit layer: create an element and prove the written file is healthy."""
import os
import pytest


@pytest.fixture(scope="module")
def committed(tmp_path_factory):
    from rvt.mutate import Document
    from rvt.commit import commit_new_elements
    src = os.path.join(os.path.dirname(__file__), "..", "samples", "rstbasicsampleproject.rvt")
    if not os.path.exists(src):
        pytest.skip("sample not present")
    doc = Document.load("rstbasicsampleproject")
    tpl = doc.value(1173925)
    o = tpl["m_instOrigin"]
    new = doc.add_family_instance(1411287, 311, position=(o[0] + 8.0, o[1], o[2]),
                                  rotation=0.0, template_instance_id=1173925)
    recs = dict(doc.serialize(new))
    out = str(tmp_path_factory.mktemp("commit") / "created.rvt")
    rep = commit_new_elements(src, out, [recs], [new.elemrec])
    return out, new, rep


def test_created_element_file_is_healthy(committed):
    from rvt.commit import verify_written
    out, new, rep = committed
    v = verify_written(out, [new.elem_id])
    assert v["crc_failures"] == 0
    assert v["ecc_mismatches"] == 0
    assert v["walker_errors"] == 0
    assert v["elemtable_count"] == v["header_count"] == rep.elemtable_count_after
    assert all(v["sentinel_last"].values())
    assert v["stamps_ok"]
    for seq in (101, 102, 103):
        assert new.elem_id in v["new_ids_found"][seq]
        assert v["new_ids_found"][seq][new.elem_id]["clean"]
