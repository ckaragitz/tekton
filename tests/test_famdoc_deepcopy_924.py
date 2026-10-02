"""A finalized FamilyDoc deep-copies whatever this process encoded before (#924).

Since #932 a document keeps a per-document encode cache that holds the
process-wide ObjectEncoder; once anything had been written, that encoder
carries compiled ``struct.Struct`` plans, and ``copy.deepcopy(doc)`` raised
``TypeError: cannot pickle '_struct.Struct' object`` -- test_catchain's
fixtures failed in the CI shard and passed alone.  The copy now starts with
no cache and encodes to the same bytes.
"""
import copy
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src"))


def _panel():
    from rvt.famgen import factory as F
    prod = F.make_panelboard(voltage="480Y/277", mains_a=225, spaces=42,
                             mcb=False, solid=True, start_id=5000)
    if not prod.doc.finalized:
        prod.doc.finalize()
    return prod


def test_a_written_document_deep_copies_and_encodes_the_same(tmp_path):
    prod = _panel()
    # a write fills the shared encoder's plans and this document's cache
    prod.write(str(tmp_path / "pb.rfa"), validate=False)
    other = _panel()
    other.write(str(tmp_path / "pb2.rfa"), validate=False)
    # a roundtrip DECODES through the shared decoder the encoder holds, which
    # compiles its struct.Struct plans -- the state the CI shard was in
    assert other.doc.roundtrip()["failed"] == 0
    doc = prod.doc
    assert doc.__dict__.get("_record_cache"), "precondition: the doc carries its cache"
    dup = copy.deepcopy(doc)
    assert "_record_cache" not in dup.__dict__
    assert dup is not doc and dup.elements is not doc.elements
    assert dup.partition_payloads() == doc.partition_payloads()
    # the original keeps its own cache untouched
    assert doc.__dict__.get("_record_cache")


def test_a_copy_is_independent_of_its_source():
    doc = _panel().doc
    dup = copy.deepcopy(doc)
    dup.self_family.obj["m_refTypeIds"] = [12345]
    assert doc.self_family.obj.get("m_refTypeIds") != [12345]
