#!/usr/bin/env python3
"""V20 — the FIRST CREATED ELEMENT: a new concrete column in the structure.

Uses the full authoring pipeline end to end:
  rvt.mutate.Document.add_family_instance()  ->  NewElement (3 records + ElemRec)
  rvt.encode (via Document.serialize)        ->  framed record bytes, correct stamps
  rvt.commit.commit_new_elements()           ->  splice into unit 0, ElemTable append,
                                                 header count, ECC re-frame, CFB write
A 450x450 mm concrete square column (symbol 1411287, family
'M_Concrete-Square-Column') placed 8 ft east of an existing column
(template instance 1173925) on Level 1. If the viewer shows an extra column
in the {3D} view, we have created a native Revit element from nothing.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.commit import commit_new_elements, verify_written  # noqa: E402
from rvt.mutate import Document  # noqa: E402

SRC = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
OUT = os.path.join(ROOT, "experiments", "acceptance", "V20_first_created_element.rvt")

SYMBOL = 1411287        # M_Concrete-Square-Column :: 450 x 450mm
LEVEL = 311             # Level 1
TEMPLATE = 1173925      # existing free-standing instance of that symbol


def main() -> None:
    doc = Document.load("rstbasicsampleproject")
    tpl = doc.value(TEMPLATE)
    origin = tpl["m_instOrigin"]
    pos = (origin[0] + 8.0, origin[1], origin[2])
    new = doc.add_family_instance(SYMBOL, LEVEL, position=pos, rotation=0.0,
                                  template_instance_id=TEMPLATE)
    print(f"new element id {new.elem_id} ({new.class_name}), rep class 0x{new.rep_class_id:x}")
    print(f"template at {[round(t, 3) for t in origin]} -> new at {[round(t, 3) for t in pos]}")
    for n in new.notes[:6]:
        print("  note:", n)

    records = doc.serialize(new)
    assert records, "serialize returned nothing"
    by_seq = {seq: rb for seq, rb in records}
    print("record sizes:", {seq: len(rb) for seq, rb in by_seq.items()})

    report = commit_new_elements(SRC, OUT, [by_seq], [new.elemrec])
    print(f"\nV20 written: {OUT} ({os.path.getsize(OUT):,} bytes)")
    print(f"  ElemTable {report.elemtable_count_before} -> {report.elemtable_count_after}, "
          f"watermark -> {report.watermark_after}, bytes added per seq {report.per_seq_bytes_added}")

    v = verify_written(OUT, [new.elem_id])
    print("\n== read-back verification ==")
    print(f"  CRC failures: {v['crc_failures']}   ECC page mismatches: {v['ecc_mismatches']}   "
          f"walker errors: {v['walker_errors']}")
    print(f"  ElemTable count {v['elemtable_count']} == header count {v['header_count']} : "
          f"{v['elemtable_count'] == v['header_count']}")
    print(f"  sentinel still last per seq: {v['sentinel_last']}")
    print(f"  all seq-102/103 stamps valid: {v['stamps_ok']}")
    print(f"  new element found & decodes clean per seq: {v['new_ids_found']}")


if __name__ == "__main__":
    main()
