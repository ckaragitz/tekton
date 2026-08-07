"""Stream-local tests for tools/famdoc_bisect.py (famdoc-bisect stream).

Covers the hybrid machinery invariants (donor pinning, rebase closure,
axis-set shapes, self-Family registration) and -- when the probe ladder has
been built -- the emitted probes' machine gates read back from disk.

Run: .venv/bin/python -m pytest tests/test_famdoc_bisect.py -q
(SUITE-COORDINATION: stream-local file only; never the full suite.)
"""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (os.path.join(ROOT, "src"), os.path.join(ROOT, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import famdoc_bisect as FB  # noqa: E402

OUT = os.path.join(ROOT, "experiments", "famdoc_bisect")


@pytest.fixture(scope="module", autouse=True)
def _schema():
    FB._install_schema()


@pytest.fixture(scope="module")
def donor():
    els, adoc_value, idx = FB.load_unit_elements(FB.RST, FB.DONOR_UNIT)
    return {"els": els, "adoc": adoc_value, "idx": idx}


@pytest.fixture(scope="module")
def wm():
    import ifc_intent as T
    return T.host_watermark(FB.RST)


# ---------------------------------------------------------------------------
# donor pinning
# ---------------------------------------------------------------------------

def test_donor_unit_shape(donor):
    els = donor["els"]
    assert len(els) == 417
    ids = {e.elem_id for e in els}
    assert {FB.DONOR_SELF_FAMILY, FB.DONOR_LEVEL, FB.DONOR_PLAN_VIEW,
            FB.DONOR_EXTRUSION} <= ids
    sf = next(e for e in els if e.elem_id == FB.DONOR_SELF_FAMILY)
    assert sf.class_name == "Family"
    # SELF-CONTAINED: no nested Family element carries a content document
    for e in els:
        if e.class_name == "Family" and e.elem_id != FB.DONOR_SELF_FAMILY:
            fd = ((e.obj.get("m_oFamDoc") or {}).get("value") or {})
            assert not fd.get("m_contentDocGUID"), \
                "donor famdoc is no longer self-contained"


def test_donor_inline_adoc(donor):
    aim = ((donor["adoc"].get("m_pAppInfoManager") or {}).get("value") or {})
    arr = aim.get("m_appInfoArr") or []
    assert len(arr) == 239
    assert sum(1 for x in arr if x) == 131          # populated family-editor registries
    assert donor["adoc"].get("m_ownerFamilyId") == FB.DONOR_SELF_FAMILY


# ---------------------------------------------------------------------------
# rebase closure
# ---------------------------------------------------------------------------

def test_rebase_leaves_no_old_member_ids(donor, wm):
    els = donor["els"]
    member = sorted(e.elem_id for e in els)
    idmap = {old: wm + 1 + i for i, old in enumerate(member)}
    new_els, census = FB.rebase_elements(els, idmap)
    old = set(member)
    leaks = []

    def scan(node):
        if isinstance(node, dict):
            for v in node.values():
                if isinstance(v, bool):
                    continue
                if isinstance(v, int) and v in old:
                    leaks.append(v)
                else:
                    scan(v)
        elif isinstance(node, list):
            for v in node:
                if isinstance(v, bool):
                    continue
                if isinstance(v, int) and v in old:
                    leaks.append(v)
                else:
                    scan(v)

    for e in new_els:
        scan(e.header)
        scan(e.obj)
        if e.rep is not None:
            scan(e.rep)
    assert not leaks, f"old member ids survived the rebase: {leaks[:6]}"
    # monotone map preserves the unit's record order
    assert [idmap[m] for m in member] == sorted(idmap.values())
    # the remap census names the id-bearing keys (loader-walk semantics)
    assert census.get("m_id"), "remap census empty -- the walk did nothing"


# ---------------------------------------------------------------------------
# axis sets + hybrid registration
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ours(wm):
    return FB.our_product(wm + 2000).doc


def test_axis_sets_pinned(ours):
    sets = FB.axis_sets(ours)
    assert {len(sets[k]) for k in ("H1", "H2", "H3", "H4", "H5")} == {7, 14, 4, 8, 2}
    assert len(sets["H1"]) == 7 and len(sets["H2"]) == 14
    assert len(sets["H3"]) == 4 and len(sets["H4"]) == 8 and len(sets["H5"]) == 2


def test_connector_param_is_a_family_param(ours):
    pid = FB.connector_param_id(ours)
    kinds = {e.elem_id: e.kind for e in ours.elements}
    assert kinds.get(pid) == "family_param"


@pytest.fixture(scope="module")
def hybrid_h1(wm):
    return FB.make_hybrid("H1", wm)


def test_hybrid_h1_registration(hybrid_h1, wm):
    doc, rep = hybrid_h1
    assert len(doc.elements) == 417 + 7
    carried = {c["id"] for c in rep["carried"]}
    assert len(carried) == 7
    sf = doc.self_family
    dele = ((sf.header.get("m_parents") or {}).get("value") or {}).get("m_deletion") or []
    data = ((sf.obj.get("m_familyIds") or {}).get("value") or {}).get("m_data") or []
    fam_ids = {int(d.get("m_elementId")) for d in data}
    assert carried <= set(dele), "carried elements missing from the deletion list"
    assert carried <= fam_ids, "carried elements missing from m_familyIds"
    assert dele == sorted(dele), "deletion list must stay ascending"
    # unique absorbed indices
    idxs = [int(d.get("m_index")) for d in data]
    assert len(idxs) == len(set(idxs))
    # every carried element sits above the donor block, below famload's ids
    lo, hi = rep["donor_block"]
    assert all(c > hi for c in carried)
    # no carried element still points at OUR self-family / level (repointed)
    assert rep["repointed"], "H1 must repoint our anchors to the donor's"


def test_hybrid_h2_tables(wm):
    doc, rep = FB.make_hybrid("H2", wm)
    sf = doc.self_family
    params = [e for e in doc.elements if e.class_name == "ParamElemFamily"]
    assert len(params) == 2 + 14
    reg = rep["registration"]["params"]
    assert reg["rows_appended"] >= 14
    assert reg["type_pairs_extended"] == 5           # blank + 4 named donor pairs
    fp = ((sf.obj.get("m_familyParams") or {}).get("value") or {}).get("m_params") or []
    row_ids = {r.get("m_paramId") for r in fp}
    carried = {c["id"] for c in rep["carried"] if c["class"] == "ParamElemFamily"}
    assert carried <= row_ids, "our param rows missing from m_familyParams"
    ftt = ((sf.obj.get("m_pFamilyTypes") or {}).get("value") or {})
    for pr in ftt.get("m_pairs") or []:
        ids = {r.get("m_paramId") for r in (pr.get("params") or {}).get("m_params") or []}
        assert carried <= ids, f"pair {pr.get('name')!r} missing our rows"


def test_hybrid_doc_guid_fresh_and_unit_encodes(hybrid_h1):
    doc, _rep = hybrid_h1
    from rvt.families import FamilyIndex
    idx = FamilyIndex(FB.RST)
    native = {str(u.guid) for u in idx.units if u.guid}
    assert doc.document_guid not in native
    unit = doc.to_embedded_unit()
    assert unit["record_count"] == len(doc.elements)
    assert set(unit["segments"]) == {101, 102, 103}
    assert all(len(v) > 0 for v in unit["segments"].values())


# ---------------------------------------------------------------------------
# the emitted ladder (skip when not built)
# ---------------------------------------------------------------------------

ACCT = os.path.join(OUT, "accounting.json")
built = os.path.isfile(ACCT)


@pytest.mark.skipif(not built, reason="ladder not built")
def test_emitted_gates():
    with open(ACCT) as fh:
        acct = json.load(fh)
    assert set(FB.LADDER) <= set(acct.get("built") or {})
    for name in FB.LADDER:
        a = (acct.get("accounting") or {}).get(name) or {}
        va = a.get("validator") or {}
        assert va.get("n_errors") == 0, f"{name}: validator errors {va}"
        assert not va.get("unexpected_errors"), name
        assert (a.get("census") or {}).get("coherent") is True, name
        assert a.get("survivor_law_ok") is True, name
        info = acct["built"][name]
        f = os.path.join(ROOT, info["file"])
        assert os.path.isfile(f), name
        # md5 pinned at build time still matches the file on disk
        assert FB.md5_of(f) == info["md5"], f"{name}: file changed after accounting"


@pytest.mark.skipif(not built, reason="ladder not built")
def test_emitted_axis_content():
    """The one-axis content claims, read back from the emitted bytes."""
    from rvt.families import FamilyIndex
    with open(ACCT) as fh:
        acct = json.load(fh)

    def unit_hist(name):
        info = acct["built"][name]
        idx = FamilyIndex(os.path.join(ROOT, info["file"]))
        guid = info.get("document_guid")
        unit = next((u for u, ui in enumerate(idx.units)
                     if ui.guid and guid and str(ui.guid) == str(guid)),
                    len(idx.units) - 1)
        recs = idx.unit_records(unit)
        hist = {}
        for eid in recs.get(102, {}):
            cn = idx.class_name(recs[102][eid].class_id)
            hist[cn] = hist.get(cn, 0) + 1
        return hist

    h7 = unit_hist("H7")
    assert sum(h7.values()) == 417 and h7.get("ExtrusionElem") == 1
    h1 = unit_hist("H1")
    assert h1.get("ExtrusionElem") == 2 and h1.get("CurveElem") == 15
    h2 = unit_hist("H2")
    assert h2.get("ParamElemFamily") == 16
    h5 = unit_hist("H5")
    assert h5.get("ConnectorElem") == 1 and h5.get("ElectricalLoadClassification") == 1
    h8 = unit_hist("H8")
    assert sum(h8.values()) == 41 and h8.get("ConnectorElem") == 1


@pytest.mark.skipif(not built, reason="ladder not built")
def test_h6_carries_the_donor_inline_adoc():
    from rvt import adocument as A
    from rvt.families import FamilyIndex, content_document_adoc
    with open(ACCT) as fh:
        acct = json.load(fh)

    def populated(name):
        info = acct["built"][name]
        idx = FamilyIndex(os.path.join(ROOT, info["file"]))
        guid = str(info["document_guid"])
        blob = content_document_adoc(idx, guid)
        ad = A.decode_latest(blob)
        assert ad.clean
        aim = ((ad.value.get("m_pAppInfoManager") or {}).get("value") or {})
        arr = aim.get("m_appInfoArr") or []
        return sum(1 for x in arr if x)

    assert populated("H7") == 0          # our authored minimal inline ADocument
    assert populated("H6") == 131        # the donor's own registries, carried


@pytest.mark.skipif(not built, reason="ladder not built")
def test_probes_json_shape():
    with open(os.path.join(OUT, "probes.json")) as fh:
        man = json.load(fh)
    assert man["upload_order_max_information_first"] == list(FB.LADDER)
    assert man["control"]["source"].endswith("rstbasicsampleproject.rvt")
    probes = {p["rung"]: p for p in man["probes"]}
    assert set(probes) == set(FB.LADDER)
    for name, p in probes.items():
        assert p["base"].endswith("rstbasicsampleproject.rvt")
        assert p["n_families"] == 1 and p["n_instances"] == 1
        assert p["gates"]["validator_errors"] == 0
        assert p["gates"]["four_registry_coherent"] is True
        assert p["gates"]["survivor_law_ok"] is True
