"""famdoc-blobs stream tests -- the blob-carrying famdoc bisection ladder.

Pins the verdict-#36/#37 machinery: batch 37's hybrid recipes rebuilt
through the FIXED writer, every emitted unit carrying the 64-byte 0x0f3f
footer blob (raw-scanned INDEPENDENTLY here, not through the tool's own
gate), the added unit's blob byte-matching our deterministic nonce, the
B0 product-shape anchor (the BXhf_f1i1 recipe), probes.json's decision
table, and -- once staged -- the two-control batch manifest.

Stream-local only (SUITE-COORDINATION: no full-suite runs from this
stream)::

    .venv/bin/python -m pytest tests/test_famdoc_blobs.py -q
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import sys
import uuid

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (os.path.join(ROOT, "src"), os.path.join(ROOT, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

OUT_DIR = os.path.join(ROOT, "experiments", "famdoc_blobs")
ACCT = os.path.join(OUT_DIR, "accounting.json")
PROBES = os.path.join(OUT_DIR, "probes.json")
ACCEPTANCE = os.path.join(ROOT, "experiments", "acceptance")
RST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
G_ABPD = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "compose",
                      "G_ABPD.rvt")

LADDER = ("B7", "B0", "B1", "B2", "B3", "B4", "B5", "B6")

#: the axis element counts each hybrid ADDS to the donor famdoc (famdoc-
#: bisect's measured multisets: H1 = extrusion+sketch+4 curves+plane,
#: H2 = 14 params, H3 = 2 planes+level+type, H4 = 8-element view chain,
#: H5 = connector+load class+its param, H6/H7 = none)
ADDED_ELEMS = {"B7": 0, "B1": 7, "B2": 14, "B3": 4, "B4": 8, "B5": 3, "B6": 0}

pytestmark = pytest.mark.skipif(
    not (os.path.isfile(ACCT) and os.path.isfile(PROBES)),
    reason="famdoc_blobs artifacts not built (run tools/famdoc_blobs.py build)")

#: the manifests are tracked in git but the probe .rvt binaries live in
#: git-ignored dirs -- a fresh clone has the JSONs and not the bytes, so
#: binary-reading tests skip on the samples/ sentinel (KNOWLEDGE: tests
#: self-skip when samples or built ladders are absent)
needs_bins = pytest.mark.skipif(
    not os.path.isfile(RST),
    reason="samples/ not present (fresh clone) -- probe binaries unavailable")


@pytest.fixture(scope="module")
def acct():
    with open(ACCT) as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def probes():
    with open(PROBES) as fh:
        return json.load(fh)


def _units(path, with_data=True):
    """INDEPENDENT raw-scan of every save unit's 0x0f3f footer blob (the
    walker, not the tool's blob_proof)."""
    from rvt.container import open_rvt
    from rvt.partitions import StreamWalker
    out = []
    with open_rvt(path) as f:
        for nm in sorted(s.name for s in f.streams()
                         if s.name.startswith("Partitions/")):
            w = StreamWalker(f.logical(nm), inflate=with_data,
                             keep_data=with_data)
            assert not w.errors, (path, nm, w.errors[:3])
            for u in w.units:
                seg102 = bytearray()
                if with_data:
                    for b in sorted((b for b in
                                     w.blocks[u.first_block:u.first_block + u.n_blocks]
                                     if b.seq == 102), key=lambda b: b.hdr_offset):
                        seg102.extend(b.data or b"")
                out.append({
                    "guid": str(uuid.UUID(bytes_le=u.guid)) if u.guid else None,
                    "blob": bytes(u.footer_blob), "seg102": bytes(seg102)})
    return out


_BASE_GUIDS = {}


def _base_guids(base):
    if base not in _BASE_GUIDS:
        _BASE_GUIDS[base] = {u["guid"] for u in _units(base, with_data=False)}
    return _BASE_GUIDS[base]


# ---------------------------------------------------------------------------
# the footer law itself
# ---------------------------------------------------------------------------

def test_build_footer_is_deterministic_64B_and_guid_unique():
    from rvt.famgen.famdoc_adoc import FOOTER_BLOB_LEN, build_footer
    a = build_footer(guid="00000000-0000-0000-0000-000000000001", payload=b"x")
    b = build_footer(guid="00000000-0000-0000-0000-000000000001", payload=b"x")
    c = build_footer(guid="00000000-0000-0000-0000-000000000002", payload=b"x")
    assert len(a) == FOOTER_BLOB_LEN == 64
    assert a == b and a != c


def test_fixed_writer_paths_emit_the_footer():
    """Both loaders ride factory.build_family_save_unit; the factory source
    must call build_footer (the verdict-#36 core fix) -- a regression here
    voids any future round exactly like batch 37."""
    import inspect
    from rvt.famgen import factory
    src = inspect.getsource(factory.build_family_save_unit)
    assert "build_footer" in src and "FOOTER_TAG" in src


# ---------------------------------------------------------------------------
# every emitted probe: blob census + nonce, independently re-derived
# ---------------------------------------------------------------------------

@needs_bins
@pytest.mark.parametrize("name", LADDER)
def test_probe_every_unit_carries_64B_blob_and_added_nonce_matches(name, acct):
    from rvt.famgen.famdoc_adoc import build_footer
    info = acct["built"][name]
    path = os.path.join(ROOT, info["file"])
    assert os.path.isfile(path)
    base = G_ABPD if name == "B0" else RST
    units = _units(path)
    assert all(len(u["blob"]) == 64 for u in units), \
        f"{name}: a unit without a 64-byte blob (the batch-37 voider)"
    added = [u for u in units if u["guid"] not in _base_guids(base)]
    assert len(added) == 1, f"{name}: expected exactly ONE added unit"
    u = added[0]
    assert u["blob"] == build_footer(guid=u["guid"], payload=u["seg102"]), \
        f"{name}: added unit's blob is not OUR deterministic nonce"


@pytest.mark.parametrize("name", LADDER)
def test_gates_green(name, acct):
    g = acct["gates"][name]
    assert g["gates_ok"] is True
    assert g["validator_errors"] == 0 and g["validator_unexpected"] == 0
    assert g["four_registry_coherent"] is True
    assert g["load_hop_units_added"] == 1
    assert g["instance_hop_units_added"] == 0
    assert g["survivor_law_ok"] is True
    assert g["identity"] == "PASS"
    assert g["blob_all_units_64B"] is True
    assert g["blob_added_nonce_verified"] is True
    assert g["blob_units_added"] == 1


@pytest.mark.parametrize("name", sorted(ADDED_ELEMS))
def test_hybrid_axis_element_counts(name, acct):
    """The B-rung rebuilds its H recipe: donor famdoc + exactly the axis
    multiset (element count read from the build record)."""
    info = acct["built"][name]
    b7 = acct["built"]["B7"]
    assert info["n_elements"] == b7["n_elements"] + ADDED_ELEMS[name]
    if name not in ("B7", "B6"):
        assert len((info.get("hybrid") or {}).get("carried") or []) == \
            ADDED_ELEMS[name]


def test_b0_is_the_bxhf_recipe(acct):
    info = acct["built"]["B0"]
    assert info["base"].endswith("G_ABPD.rvt")
    assert len(info["instance_ids"]) == 1
    assert info["instance_connmgr"] == "FamilyInstanceConnectorManager"
    forms = info["symbol_form"]
    assert forms and all(f["ok"] for f in forms.values())
    assert all(i["n_dangling"] == 0 for i in info["equipment"]["instances"])
    assert "corpus_symbol_form" in info["recipe"]


def test_b6_carries_the_donor_inline_adocument(acct):
    swap = acct["built"]["B6"].get("adoc_swap") or {}
    assert swap.get("appinfo_populated") == 131
    assert swap.get("swapped_guid") == acct["built"]["B6"]["document_guid"]


# ---------------------------------------------------------------------------
# probes.json: order, bases, decision table
# ---------------------------------------------------------------------------

@needs_bins
def test_probes_json_order_and_bases(probes):
    rungs = [p["rung"] for p in probes["probes"]]
    assert rungs == list(LADDER), "reading order must be B7, B0, B1..B6"
    for p in probes["probes"]:
        want = "experiments/genesis/subst_k4/compose/G_ABPD.rvt" \
            if p["rung"] == "B0" else "samples/rstbasicsampleproject.rvt"
        assert p["base"] == want
        f = os.path.join(ROOT, p["file"])
        assert os.path.isfile(f)
        h = hashlib.md5(open(f, "rb").read()).hexdigest()
        assert h == p["md5"], f"{p['rung']}: probes.json md5 is stale"
        assert p["gates"]["gates_ok"] is True
        assert p["blob_proof"]["added_nonce_verified"] is True
        assert p["blob_proof"]["units_added_vs_base"] == 1


def test_decision_table_covers_the_branches(probes):
    r = probes["reading_the_matrix"]
    keys = " ".join(r)
    for needed in ("CTRL", "B7 PASS", "B7 FAIL", "B0 PASS", "B0 FAIL"):
        assert needed in keys, f"decision table lacks the {needed} branch"
    assert "DEMO v6" in r["B0 PASS"]
    assert "VOID" in r["B7 FAIL"], "B7 FAIL must void B1..B6 content reads"


def test_no_stale_h_manifest():
    """The repointed famdoc_bisect run must not leave a probes.json under
    _h/ (it would duplicate declarations probe_batch globs over)."""
    assert not os.path.exists(os.path.join(OUT_DIR, "_h", "probes.json"))


# ---------------------------------------------------------------------------
# the staged batch (two controls) -- runs only once stage() has happened
# ---------------------------------------------------------------------------

def _blobs_batch():
    best = None
    for p in glob.glob(os.path.join(ACCEPTANCE, "batch_*.json")):
        try:
            with open(p) as fh:
                man = json.load(fh)
        except (OSError, ValueError):
            continue
        if "famdoc_blobs" in str(man.get("tool", "")):
            n = int(re.match(r"batch_(\d+)", os.path.basename(p)).group(1))
            if best is None or n > best[0]:
                best = (n, man)
    return best


staged = pytest.mark.skipif(_blobs_batch() is None,
                            reason="ladder not yet staged")


@staged
@needs_bins
def test_staged_batch_two_controls_and_md5s():
    n, man = _blobs_batch()
    assert man["control_count"] == 2
    entries = man["entries"]
    controls = [e for e in entries if e["kind"] == "control"]
    assert len(controls) == 2
    srcs = {e["control_source"] for e in controls}
    assert srcs == {"samples/rstbasicsampleproject.rvt",
                    "experiments/genesis/subst_k4/compose/G_ABPD.rvt"}
    for e in entries:
        staged_path = os.path.join(ROOT, e["staged_as"])
        assert os.path.isfile(staged_path), e["staged_as"]
        h = hashlib.md5(open(staged_path, "rb").read()).hexdigest()
        assert h == e["md5"], f"{e['staged_as']}: staged copy md5 drifted"
    order = [os.path.splitext(os.path.basename(e["staged_as"]))[0]
             for e in entries if e["kind"] == "probe"]
    assert order == list(LADDER)
    for c in controls:
        src_h = hashlib.md5(
            open(os.path.join(ROOT, c["control_source"]), "rb").read()).hexdigest()
        assert src_h == c["md5"], "control is not byte-identical to its source"


@staged
def test_staged_controls_named_with_batch_tag():
    n, man = _blobs_batch()
    for e in man["entries"]:
        if e["kind"] == "control":
            assert re.search(rf"_b{n}\.rvt$", e["staged_as"])
