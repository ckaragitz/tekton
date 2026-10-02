"""#975 -- four edge cases of ``pset_params.collect`` left by #974's review.

1. An unreadable value on another product still records that product as an
   owner of the label (#967's invariant), in either file order.
2. A plain number and a length of one value carry the LENGTH kind whichever
   comes first, so file order never decides whether the label drives.
3. A ``skipped`` row about two unattached values makes no claim a later
   occurrence value turns false.
(4. is the record correction in ``docs/inbox/param-drive.d/973-pset-override.md``.)

Pure plan-level checks: nothing is built, no release context is entered.
Nothing here claims Revit behaviour (hard rule 4).
"""
from __future__ import annotations

import os

from test_pset_drive_714 import PRODUCTS, PSETS, _L, _measured, _rows, ifc_text


def _write(d, text, name):
    p = os.path.join(str(d), name)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(text)
    return p


def _psets_with(extra, *, before_body=False):
    """PSETS plus ``extra`` psets, placed just before or after ``Pset_Body``."""
    i = [p[0] for p in PSETS].index("Pset_Body") + (0 if before_body else 1)
    return PSETS[:i] + list(extra) + PSETS[i:]


_BAD = ("Pset_Bad", ["pad_slab"], [("BodyWidth", _L, "abc")])


def _assert_two_owners(parts, coll):
    from rvt.ifc import pset_drive as PD
    src = coll["sources"]["BodyWidth"]
    assert sorted(src["products"]) == ["pad_slab", "tank_shell"], src
    assert len(set(src["product_ids"])) == 2, src
    # the readable value is still the carried one, and it is not a conflict
    assert abs(coll["params"]["BodyWidth"][1] - 1574.8 / 304.8) < 1e-9
    assert "conflicting_values" not in src
    row = _rows(PD.plan(parts, coll))["BodyWidth"]
    assert row["status"] == PD.VALUE_ONLY and "attached to 2 products" in row["reason"], row


def test_an_unreadable_value_after_still_counts_its_product(tmp_path):
    psets = _psets_with([_BAD])
    parts, coll = _measured(_write(tmp_path, ifc_text(PRODUCTS, psets), "bad_after.ifc"))
    assert any("unreadable value" in r["why"] for r in coll["skipped"]
               if r["name"] == "BodyWidth")
    _assert_two_owners(parts, coll)


def test_an_unreadable_value_before_still_counts_its_product(tmp_path):
    """...and the pending owners never conjure a parameter out of a label whose
    only value is unreadable (``Mystery``)."""
    bad = ("Pset_Bad", ["pad_slab"], [("BodyWidth", _L, "abc"), ("Mystery", _L, "abc")])
    psets = _psets_with([bad], before_body=True)
    parts, coll = _measured(_write(tmp_path, ifc_text(PRODUCTS, psets), "bad_first.ifc"))
    _assert_two_owners(parts, coll)
    assert "Mystery" not in coll["params"] and "Mystery" not in coll["sources"]


def test_a_real_then_a_length_of_one_value_still_drives(tmp_path):
    from rvt.ifc import pset_drive as PD
    psets = _psets_with([("Pset_Real", ["tank_shell"], [("BodyWidth", "IFCREAL", 1574.8)])],
                        before_body=True)
    parts, coll = _measured(_write(tmp_path, ifc_text(PRODUCTS, psets), "real_first.ifc"))
    kind, val = coll["params"]["BodyWidth"]
    assert kind == "length" and abs(val - 1574.8 / 304.8) < 1e-9
    src = coll["sources"]["BodyWidth"]
    assert src["ifc_type"] == "IfcLengthMeasure" and "conflicting_values" not in src
    assert not [r for r in coll["skipped"] if r["name"] == "BodyWidth"]
    row = _rows(PD.plan(parts, coll))["BodyWidth"]
    assert row["status"] == PD.DRIVES and (row["part"], row["axis"]) == ("tank_shell", "x"), row


def _orphans_first(values):
    """The #714 fixture with one unattached pset per value of BodyWidth placed
    AHEAD of every occurrence pset, in the order given."""
    base = ifc_text(PRODUCTS, PSETS)
    head, rest = base.split("#100=", 1)
    lines = []
    for i, v in enumerate(values):
        lines.append(f"#9{i:03d}0=IFCPROPERTYSINGLEVALUE('BodyWidth',$,"
                     f"IFCLENGTHMEASURE({float(v)!r}),$);")
        lines.append(f"#9{i:03d}1=IFCPROPERTYSET('{90001 + 10 * i:022d}',#5,"
                     f"'Pset_Type{i}',$,(#9{i:03d}0));")
    return head + "\n".join(lines) + "\n#100=" + rest


def test_two_unattached_rows_stay_true_when_an_occurrence_wins(tmp_path):
    """File order: unattached 1500, unattached 1600, occurrence 1574.8.  No row
    may still say an unattached value 'is kept' once the occurrence's is carried."""
    from rvt.ifc import pset_drive as PD
    text = _orphans_first([1500, 1600])
    parts, coll = _measured(_write(tmp_path, text, "two_orphans_then_occ.ifc"))
    assert abs(coll["params"]["BodyWidth"][1] - 1574.8 / 304.8) < 1e-9
    rows = [r for r in coll["skipped"] if r["name"] == "BodyWidth"]
    assert len(rows) == 2, rows
    for r in rows:
        assert "kept" not in r["why"] and "not carried" in r["why"], r
        assert "occurrence value 1574.8" in r["why"], r
    assert {("1500.0" in r["why"]) for r in rows} == {True, False}
    assert _rows(PD.plan(parts, coll))["BodyWidth"]["status"] == PD.DRIVES


def test_an_unattached_repeat_equal_to_the_occurrence_is_no_skip(tmp_path):
    """Unattached 1500, unattached 1574.8, occurrence 1574.8: the value 1574.8 IS
    carried, so no row says it was not."""
    from rvt.ifc import pset_params as PP
    coll = PP.collect(_write(tmp_path, _orphans_first([1500, 1574.8]), "eq_orphan.ifc"))
    rows = [r for r in coll["skipped"] if r["name"] == "BodyWidth"]
    assert len(rows) == 1 and "1500.0" in rows[0]["why"], rows
