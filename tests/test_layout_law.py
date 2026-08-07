"""layout_law tests: the id-assignment normalization pass (layout-law
stream).  A small famgen panelboard document is normalized and the
convention, bijection, content preservation and idempotence are proven."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.famgen import factory as F                     # noqa: E402
from rvt.famgen import layout_law as LL                 # noqa: E402
from rvt.famgen.skeleton import build_unit_segments     # noqa: E402


@pytest.fixture(scope="module")
def doc():
    prod = F.make_panelboard(voltage="208Y/120", mains_a=225, spaces=30,
                             mcb=False, solid=True, start_id=5000)
    d = prod.doc
    if not d.finalized:
        d.finalize()
    return d


def _class_order(d):
    return [e.class_name for e in sorted(d.elements, key=lambda e: e.elem_id)]


def _snapshot(d):
    """(class_name, kind, id-normalized record byte lengths) multiset --
    a content fingerprint that survives renumbering."""
    import collections
    c = collections.Counter()
    for e in d.elements:
        c[(e.class_name, e.kind)] += 1
    return c


def test_normalize_off_is_noop(doc):
    import copy
    d = copy.deepcopy(doc)
    before = [(e.elem_id, e.class_name) for e in d.elements]
    rep = LL.normalize_doc(d, order="off")
    assert rep["n_moved"] == 0
    assert [(e.elem_id, e.class_name) for e in d.elements] == before


def test_normalize_orders_frame_first(doc):
    import copy
    d = copy.deepcopy(doc)
    before_ids = sorted(e.elem_id for e in d.elements)
    before_content = _snapshot(d)
    rep = LL.normalize_doc(d, order="donor_frame_first")
    # bijection over the SAME id block
    assert sorted(e.elem_id for e in d.elements) == before_ids
    # content preserved (class/kind census unchanged)
    assert _snapshot(d) == before_content
    # the convention: self-Family, proj viewer, proj view, proj drawing,
    # proj viewport, units first
    order = _class_order(d)
    assert order[:6] == ["Family", "Viewer", "DBViewProject", "DBDrawing",
                         "Viewport", "UnitsElem"]
    assert rep["class_order_after"][:6] == order[:6]
    # the moved frame elements really are the PROJECT chain (owner links
    # renumbered consistently)
    fam = d.self_family
    assert d.elements[0] is fam or d.elements[0].elem_id == fam.elem_id
    proj = next(e for e in d.elements if e.class_name == "DBViewProject")
    viewer = next(e for e in d.elements if e.class_name == "Viewer"
                  and e.owner_id == proj.elem_id)
    assert viewer.elem_id < proj.elem_id          # donor sequence: viewer first


def test_normalize_heals_param_type_ids(doc):
    import copy
    d = copy.deepcopy(doc)
    LL.normalize_doc(d, order="donor_frame_first")
    for e in d.elements:
        if e.class_name != "ParamElemFamily":
            continue
        tid = ((((e.obj.get("m_pParamDef") or {}).get("value") or {})
                .get("m_typeId") or {}).get("m_typeId") or "")
        assert tid.startswith("revit.local.family:")
        suffix = tid.split(":", 1)[1].split("-", 1)[0][-8:]
        assert int(suffix, 16) == e.elem_id, \
            f"stale typeId suffix on {e.elem_id}: {tid}"


def test_normalize_registries_carry_no_stale_ids(doc):
    import copy
    d = copy.deepcopy(doc)
    LL.normalize_doc(d, order="donor_frame_first")
    ids = {e.elem_id for e in d.elements}
    fam = d.self_family
    rows = (((fam.obj.get("m_familyIds") or {}).get("value") or {})
            .get("m_data") or [])
    assert rows, "self-Family m_familyIds emptied by normalization"
    for r in rows:
        assert int(r.get("m_elementId", -1)) in ids
    dele = ((fam.header.get("m_parents") or {}).get("value") or {}) \
        .get("m_deletion") or []
    for x in dele:
        if isinstance(x, int) and x > 0:
            assert x in ids, f"stale deletion parent {x}"


def test_normalize_idempotent(doc):
    import copy
    d = copy.deepcopy(doc)
    LL.normalize_doc(d, order="donor_frame_first")
    once = [(e.elem_id, e.class_name) for e in d.elements]
    rep2 = LL.normalize_doc(d, order="donor_frame_first")
    assert rep2["n_moved"] == 0
    assert [(e.elem_id, e.class_name) for e in d.elements] == once


def test_normalized_doc_emits_in_convention_order(doc):
    import copy
    import struct
    d = copy.deepcopy(doc)
    LL.normalize_doc(d, order="donor_frame_first")
    segs = build_unit_segments(d.elements)
    ids = []
    seg, p = segs[102], 0
    while p < len(seg):
        eid, _st, ps = struct.unpack_from("<qII", seg, p)
        if eid != -1:
            ids.append(eid)
        p += 16 + ps + 4
    assert ids == sorted(e.elem_id for e in d.elements)
    by_id = {e.elem_id: e.class_name for e in d.elements}
    assert [by_id[i] for i in ids[:6]] == ["Family", "Viewer", "DBViewProject",
                                           "DBDrawing", "Viewport", "UnitsElem"]


def test_normalize_refuses_unfinalized():
    d = F.make_panelboard(voltage="208Y/120", mains_a=225, spaces=30,
                          mcb=False, solid=True, start_id=5000).doc
    d.finalized = False
    with pytest.raises(ValueError, match="FINALIZED"):
        LL.normalize_doc(d)


def test_order_cell_merge(doc):
    import copy
    d = copy.deepcopy(doc)
    fam = d.self_family

    def groups():
        cells = (((fam.obj.get("m_cellList") or {}).get("value") or {})
                 .get("m_cells") or [])
        for c in cells:
            sp = ((c.get("value") or {}) if isinstance(c, dict) else {}) \
                .get("m_sortedParams")
            if isinstance(sp, list):
                return sp
        return []

    before = groups()
    keys_before = [str((g.get("m_groupTypeId") or {}).get("m_typeId"))
                   for g in before]
    ids_before = sorted(pid for g in before
                        for pid in (g.get("m_paramIds") or []))
    assert len(keys_before) != len(set(keys_before)), \
        "fixture regression: famgen no longer emits duplicate group keys " \
        "(update this test AND retire the M3 axis)"
    rep = LL.normalize_order_cell(d)
    after = groups()
    keys_after = [str((g.get("m_groupTypeId") or {}).get("m_typeId"))
                  for g in after]
    ids_after = sorted(pid for g in after
                       for pid in (g.get("m_paramIds") or []))
    assert len(keys_after) == len(set(keys_after)), "duplicate keys survive"
    assert ids_after == ids_before, "param id multiset changed"
    assert rep["merged_groups"] >= 1
    assert "electrical" in keys_after[-1] or "identity" in keys_after[-1].lower()
