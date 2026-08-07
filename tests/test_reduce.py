"""reduce.py: delete elements from a project and prove the file stays healthy."""
import os
import struct

import pytest

RST = os.path.join(os.path.dirname(__file__), "..", "samples", "rstbasicsampleproject.rvt")


# ---------------------------------------------------------------------------
# pure unit tests of the framing logic (no sample needed)
# ---------------------------------------------------------------------------

def _rec(seq, eid, body, stamp=0):
    """Build one framed record: header + body + u32 size repeat."""
    if seq == 101:
        hdr = struct.pack("<qI", eid, len(body))
    else:
        hdr = struct.pack("<qII", eid, stamp, len(body))
    return hdr + body + struct.pack("<I", len(body))


def _sentinel(seq):
    return _rec(seq, -1, b"")


def test_split_records_lossless_and_sentinel_required():
    from rvt.reduce import split_records
    seg = _rec(102, 7, b"\xaa" * 30) + _rec(102, 9, b"\xbb" * 5) + _sentinel(102)
    recs = split_records(seg, 102)
    assert [r.elem_id for r in recs] == [7, 9, -1]
    assert b"".join(r.data for r in recs) == seg          # lossless tiling
    assert recs[-1].is_sentinel
    with pytest.raises(ValueError):
        split_records(seg + b"\x00\x00", 102)            # trailing garbage refused
    with pytest.raises(ValueError):
        split_records(_rec(102, 7, b"x" * 4), 102)         # no sentinel refused


def test_reblock_whole_records_flags_and_isize():
    from rvt.reduce import reblock, split_records
    seg = b"".join(_rec(101, i, b"\x11" * 100) for i in range(10)) + _sentinel(101)
    recs = split_records(seg, 101)
    blocks = reblock(recs, 101, target=400)                 # forces several blocks
    assert all(b.flags == 4 for b in blocks)
    assert sum(b.A for b in blocks) == len(recs)
    assert b"".join(b.payload for b in blocks) == seg
    for b in blocks:
        assert b.isize_ok
        assert len(b.payload) <= 400


def test_reblock_spanning_record_matches_autodesk_layout():
    """A record too big for one block is body-chunked: flags 6 -> 7... -> 5,
    first block = header + exactly `target` body bytes (rstbasic evidence:
    flags-6 blocks have payload 131,088 = 16 + 131,072)."""
    from rvt.reduce import reblock, split_records
    big = _rec(102, 42, bytes(range(256)) * 12)             # 3072-byte body
    seg = _rec(102, 1, b"a" * 10) + big + _rec(102, 2, b"b" * 10) + _sentinel(102)
    recs = split_records(seg, 102)
    blocks = reblock(recs, 102, target=1024)
    flags = [b.flags for b in blocks]
    assert flags.count(6) == 1 and flags.count(5) == 1 and 7 in flags
    six = next(b for b in blocks if b.flags == 6)
    assert six.A == 1 and six.C == 1024 and len(six.payload) == 16 + 1024
    five = next(b for b in blocks if b.flags == 5)
    assert five.A == 0
    assert b"".join(b.payload for b in blocks) == seg      # bytes conserved
    assert all(b.isize_ok for b in blocks)


# ---------------------------------------------------------------------------
# integration: delete real elements from the smallest sample
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def reduced(tmp_path_factory):
    if not os.path.exists(RST):
        pytest.skip("sample not present")
    from rvt.mutate import Document
    from rvt.reduce import delete_elements
    doc = Document.from_file(RST)
    victims = sorted(doc.ids_of_class("TextNote"))[:25]   # leaf annotation
    assert victims
    out = str(tmp_path_factory.mktemp("reduce") / "reduced.rvt")
    rep = delete_elements(RST, out, victims)
    return out, victims, rep, len(doc.et_by_id)


def test_reduced_file_is_structurally_healthy(reduced):
    from rvt.reduce import verify_reduced
    out, victims, rep, before = reduced
    v = verify_reduced(out, victims)
    assert v["crc_failures"] == 0
    assert v["ecc_mismatches"] == 0
    assert v["walker_errors"] == []
    assert v["counts_match"]
    assert v["elemtable_count"] == before - len(victims) == rep.elemtable_count_after
    assert all(v["sentinel_last"].values())
    assert v["seq_id_sets_equal"]
    assert v["stamps_bad"] == 0
    assert v["deleted_still_present"] == []
    assert v["isize_identity_ok"]
    assert v["ok"]
    for seq in (101, 102, 103):
        assert rep.records_removed[seq] == len(victims)


def test_reduced_file_reloads_and_victims_gone(reduced):
    from rvt.mutate import Document
    out, victims, rep, before = reduced
    doc = Document.from_file(out)
    assert len(doc.et_by_id) == before - len(victims)
    for v_id in victims:
        assert not doc.exists(v_id)
    # embedded documents untouched: same non-host record population survives
    assert len(doc.ids_of_class("TextNote")) > 0


# ---------------------------------------------------------------------------
# ladder v2 (R5..R10): validator-clean maximal-GC reduction machinery
# ---------------------------------------------------------------------------

def _load_tool():
    """Import tools/rvt_reduce.py as a module (it is a script, not a package)."""
    import importlib.util
    import sys
    root = os.path.join(os.path.dirname(__file__), "..")
    key = "rvt_reduce_tool"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(
        key, os.path.join(root, "tools", "rvt_reduce.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


def _synthetic_state(edges, classes, owner_view=None):
    """Build a ladder-v2 state dict from an explicit edge list."""
    from collections import defaultdict
    graph = defaultdict(set)
    referrers = defaultdict(set)
    for a, b in edges:
        graph[a].add(b)
        referrers[b].add(a)
    universe = set(classes)
    return {"graph": dict(graph), "referrers": dict(referrers),
            "cls_of": dict(classes), "host": set(universe),
            "universe": universe, "owner_view": dict(owner_view or {}),
            "ext": {"Global/Latest": set(), "Global/ContentDocuments": set()}}


def test_maxgc_deletes_only_what_no_survivor_references():
    """maxgc = maximal dangling-free deletion inside the seed:
    * a seed element referenced from OUTSIDE the seed survives (pinned),
    * a kept seed element pins everything IT references (forward),
    * a reference CYCLE wholly inside the seed with no outside referrer dies,
    * so no survivor ever references a deleted element."""
    R = _load_tool()
    classes = {1: "TextNote", 2: "TextNote", 3: "Wall", 4: "Dim", 5: "Dim",
               6: "Sketch", 7: "Curve", 8: "Curve"}
    edges = [(3, 4),          # Wall -> Dim 4        : outside referrer pins 4
             (4, 5),          # Dim 4 -> Dim 5       : kept 4 pins 5 forward
             (6, 7), (7, 6),  # Sketch <-> Curve 7   : cycle, 6 is OUTSIDE the seed
             (8, 8)]
    st = _synthetic_state(edges, classes)
    seed = {1, 2, 4, 5, 7, 8}                       # 3 (Wall) and 6 (Sketch) survive
    delete, kept, ev = R.maxgc(st, seed)
    assert delete == {1, 2, 8}                      # free text notes + the lone curve
    assert kept == {4, 5, 7}                        # 4 pinned by wall, 5 by 4, 7 by sketch
    # invariant: nothing kept/surviving references a deleted id
    survivors = (set(classes) - delete)
    for s in survivors:
        assert not (st["graph"].get(s, set()) & delete)
    # a cycle entirely inside the seed with no outside referrer is deleted
    st2 = _synthetic_state([(10, 11), (11, 10)], {10: "A", 11: "B"})
    d2, k2, _ = R.maxgc(st2, {10, 11})
    assert d2 == {10, 11} and not k2


def test_maxgc_extra_pins_survive():
    """The R<n>s (Latest-safe) variants pin scanned ids: an extra pin
    survives and pins forward what it references."""
    R = _load_tool()
    st = _synthetic_state([(1, 2)], {1: "A", 2: "B", 3: "C"})
    d, k, _ = R.maxgc(st, {1, 2, 3}, extra_pins={1})
    assert 1 in k and 2 in k               # 1 pinned externally -> keeps 2 too
    assert d == {3}


def test_owner_view_and_child_rules_grow_the_seed():
    """View-owned content (m_ownerDBViewId in the seed) and ownership
    children (a CategoryElem referencing a seeded element) join the seed."""
    R = _load_tool()
    classes = {1: "DBViewSection", 2: "TextNote", 3: "CategoryElem",
               4: "TextNoteAttributes", 5: "GStyleElem", 6: "Level"}
    # 2 is owned by view 1; category 3 is a child of type 4 (references it);
    # gstyle 5 references category 3 (child of child); level 6 unrelated.
    edges = [(2, 1), (3, 4), (5, 3), (2, 4)]
    st = _synthetic_state(edges, classes, owner_view={2: 1})
    st["doc"] = None
    kids = R._own_children(st, {4})                 # type 4 seeded -> 3, then 5
    assert kids == {3, 5}
    # owner-view rule (as used in stage_seed_v2): 2 dies with its view 1
    seeded = {1}
    seeded |= {e for e, ov in st["owner_view"].items() if ov in seeded}
    assert 2 in seeded and 6 not in seeded


def test_unit_ranges_tile_the_partition_stream():
    """The save-unit byte ranges tile the logical stream exactly (so any
    subset of embedded documents can be spliced out losslessly)."""
    if not os.path.exists(RST):
        pytest.skip("sample not present")
    R = _load_tool()
    from rvt.container import open_rvt
    with open_rvt(RST) as f:
        logical = f.logical(f.partition_streams()[0])
    ranges, w = R._unit_ranges(logical)
    assert len(ranges) == len(w.units) >= 2
    assert ranges[0][0] == 0 and ranges[0][2] == 18          # unit 0 after the header
    for (i, _g, s, e), (_i2, _g2, s2, _e2) in zip(ranges, ranges[1:]):
        assert e == s2                                        # contiguous tiling
        assert e > s
    assert ranges[-1][3] == w.end_offset                      # last unit meets end record
    assert all(g for (_i, g, _s, _e) in ranges[1:])            # embedded units carry GUIDs


def test_remove_units_identity_splice_is_lossless_and_valid(tmp_path):
    """Removing NO units re-emits an equivalent, validator-clean file
    (proves the unit walk + ContentDocuments re-encode round-trip)."""
    if not os.path.exists(RST):
        pytest.skip("sample not present")
    R = _load_tool()
    out = str(tmp_path / "identity_units.rvt")
    rep = R.remove_units(RST, out, set())
    assert rep["units_before"] == rep["units_after"]
    assert rep["cd_entries_before"] == rep["cd_entries_after"]
    assert rep["removed_units"] == []
    from rvt.reduce import verify_reduced
    assert verify_reduced(out)["ok"]
    from rvt.validate import validate_file
    assert validate_file(out).ok


def test_ladder_v2_R5_emits_a_validator_clean_reduction(tmp_path):
    """Stage R5 (annotation + schedule views, maximal GC) deletes thousands of
    elements yet passes BOTH the structural gate and tools/rvt_validate.py
    with ZERO errors — dangling-free by construction."""
    if not os.path.exists(RST):
        pytest.skip("sample not present")
    R = _load_tool()
    st = R.build_state_v2(RST)
    st["src"] = RST
    res = R.run_stage_v2("R5", st, safe=False, out_dir=str(tmp_path))
    assert res["structural_ok"] is True
    assert res["validator"]["ok"] is True and res["validator"]["errors"] == 0
    assert res["deleted"] > 4000                    # a real, deep annotation strip
    assert res["surviving_elements"] == res["elemtable_before"] - res["deleted"]
    # the survivors still contain the placed model (R5 is surgical: annotation only)
    surv = dict(res["top_survivor_classes"])
    assert surv.get("FamilyInstance", 0) > 400            # instances untouched
    assert "TextNote" not in surv                            # annotation gone


def test_identity_delete_reproduces_original_blocking():
    """Deleting nothing must re-block to byte-identical unit-0 payloads
    (proves the re-blocker matches Autodesk's own writer)."""
    if not os.path.exists(RST):
        pytest.skip("sample not present")
    from rvt.container import open_rvt
    from rvt.partitions import StreamWalker
    from rvt.reduce import reblock, split_records
    with open_rvt(RST) as d:
        w = StreamWalker(d.logical(d.partition_streams()[0]), inflate=True, keep_data=True)
    u0 = [b for b in sorted(w.blocks, key=lambda b: b.hdr_offset) if b.unit == 0]
    for seq in (101, 102, 103):
        bs = [b for b in u0 if b.seq == seq]
        seg = b"".join(b.data for b in bs)
        new = reblock(split_records(seg, seq), seq)
        assert [b.data for b in bs] == [n.payload for n in new]
        assert [b.flags for b in bs] == [n.flags for n in new]
        assert [b.n_records for b in bs] == [n.A for n in new]
        assert [b.body_bytes for b in bs] == [n.C for n in new]
