"""#979 -- three gaps in ``pset_params.collect`` left by #978's review.

1. ``IFCLABEL('1574.8')`` then ``IFCLENGTHMEASURE(1574.8)`` on one product is one
   statement and carries the LENGTH (the reverse order already did), so file
   order never decides whether the label drives.  A label that reads as a
   different number, or as no number, never upgrades.
2. An unreadable value that comes FIRST still gets its ``skipped`` row: its
   product is counted as an owner (#975), so the drop must be explained.
3. Removing an unattached repeat's row once an occurrence value is carried uses
   ``_same_statement`` (lengths at the drive's 1e-6 ft), the same test the
   first-unattached comparison uses -- never raw 1e-9 relative.

Pure plan-level checks: nothing is built, no release context is entered.
Nothing here claims Revit behaviour (hard rule 4).
"""
from __future__ import annotations

from test_pset_drive_714 import PRODUCTS, _L, _measured, _rows, ifc_text
from test_pset_edges_975 import _orphans_first, _psets_with, _write


def test_a_label_then_a_length_of_one_value_still_drives(tmp_path):
    from rvt.ifc import pset_drive as PD
    psets = _psets_with([("Pset_Label", ["tank_shell"],
                          [("BodyWidth", "IFCLABEL", "1574.8")])], before_body=True)
    parts, coll = _measured(_write(tmp_path, ifc_text(PRODUCTS, psets), "label_first.ifc"))
    kind, val = coll["params"]["BodyWidth"]
    assert kind == "length" and abs(val - 1574.8 / 304.8) < 1e-9, (kind, val)
    src = coll["sources"]["BodyWidth"]
    assert src["ifc_type"] == "IfcLengthMeasure" and "conflicting_values" not in src
    assert not [r for r in coll["skipped"] if r["name"] == "BodyWidth"]
    row = _rows(PD.plan(parts, coll))["BodyWidth"]
    assert row["status"] == PD.DRIVES and (row["part"], row["axis"]) == ("tank_shell", "x"), row


def test_a_label_then_a_real_of_one_value_carries_the_number(tmp_path):
    from rvt.ifc import pset_params as PP
    psets = _psets_with([("Pset_Label", ["tank_shell"], [("Ratio", "IFCLABEL", "0.5")]),
                         ("Pset_Real", ["tank_shell"], [("Ratio", "IFCREAL", 0.5)])])
    coll = PP.collect(_write(tmp_path, ifc_text(PRODUCTS, psets), "label_real.ifc"))
    assert coll["params"]["Ratio"] == ("number", 0.5)


def test_a_label_of_another_or_no_number_never_upgrades(tmp_path):
    from rvt.ifc import pset_params as PP
    psets = _psets_with([("Pset_Label", ["tank_shell"],
                          [("BodyWidth", "IFCLABEL", "wide"), ("Mark", "IFCLABEL", "12")]),
                         ("Pset_Num", ["tank_shell"], [("Mark", _L, 13)])],
                        before_body=True)
    coll = PP.collect(_write(tmp_path, ifc_text(PRODUCTS, psets), "label_other.ifc"))
    assert coll["params"]["BodyWidth"] == ("text", "wide")
    assert coll["params"]["Mark"] == ("text", "12")
    assert coll["sources"]["Mark"]["conflicting_values"] == [13.0]


def test_an_unreadable_value_first_still_has_its_row(tmp_path):
    from rvt.ifc import pset_drive as PD
    bad = ("Pset_Bad", ["pad_slab"], [("BodyWidth", _L, "abc")])
    psets = _psets_with([bad], before_body=True)
    parts, coll = _measured(_write(tmp_path, ifc_text(PRODUCTS, psets), "bad_first.ifc"))
    rows = [r for r in coll["skipped"] if r["name"] == "BodyWidth"]
    assert len(rows) == 1, rows
    assert rows[0]["on"] == "pad_slab" and "unreadable value 'abc'" in rows[0]["why"], rows
    assert "pad_slab" in coll["sources"]["BodyWidth"]["products"]
    row = _rows(PD.plan(parts, coll))["BodyWidth"]
    assert row["status"] == PD.VALUE_ONLY and "attached to 2 products" in row["reason"], row


def test_two_unreadable_values_have_one_row_each(tmp_path):
    from rvt.ifc import pset_params as PP
    bad = ("Pset_Bad", ["pad_slab"], [("BodyWidth", _L, "abc")])
    bad2 = ("Pset_Bad2", ["clearance_top_volume"], [("BodyWidth", _L, "xyz")])
    psets = _psets_with([bad, bad2], before_body=True)
    coll = PP.collect(_write(tmp_path, ifc_text(PRODUCTS, psets), "two_bad.ifc"))
    rows = [r for r in coll["skipped"] if r["name"] == "BodyWidth"]
    assert sorted(r["on"] for r in rows) == ["clearance_top_volume", "pad_slab"], rows


def test_an_unattached_repeat_within_drive_tolerance_is_no_skip(tmp_path):
    """Unattached 1500, unattached 1574.8001 (3.3e-7 ft from the occurrence --
    the same statement at the drive's 1e-6 ft, not at raw 1e-9 relative),
    occurrence 1574.8: only the 1500 row remains."""
    from rvt.ifc import pset_params as PP
    coll = PP.collect(_write(tmp_path, _orphans_first([1500, 1574.8001]), "near_orphan.ifc"))
    rows = [r for r in coll["skipped"] if r["name"] == "BodyWidth"]
    assert len(rows) == 1 and "1500.0" in rows[0]["why"], rows
    # the first-unattached comparison already agreed: the same value first is no row
    coll = PP.collect(_write(tmp_path, _orphans_first([1574.8001]), "near_first.ifc"))
    assert not [r for r in coll["skipped"] if r["name"] == "BodyWidth"]


def test_an_infinite_label_is_no_number_and_never_drives(tmp_path):
    """#983 review: 'inf' compared "equal" to every number by tolerance, so a
    label 'inf' then a length upgraded silently and DROVE -- two contradicting
    statements.  A non-finite value is never the same as anything."""
    from rvt.ifc import pset_drive as PD
    for i, word in enumerate(("inf", "-inf", "Infinity", "nan")):
        psets = _psets_with([("Pset_Label", ["tank_shell"],
                              [("BodyWidth", "IFCLABEL", word)])], before_body=True)
        parts, coll = _measured(_write(tmp_path, ifc_text(PRODUCTS, psets), f"inf{i}.ifc"))
        assert coll["params"]["BodyWidth"][0] == "text", (word, coll["params"]["BodyWidth"])
        assert coll["sources"]["BodyWidth"].get("conflicting_values"), word
        assert _rows(PD.plan(parts, coll))["BodyWidth"]["status"] == PD.VALUE_ONLY, word


def test_a_yes_no_is_never_a_number(tmp_path):
    """#983 review: IFCBOOLEAN(.T.) then IFCLENGTHMEASURE(1.) upgraded the
    Yes/No to a 1-unit length (True == 1.0 in Python) -- in a metre file it
    would drive any 1 m span.  A boolean is a different statement."""
    from rvt.ifc import pset_params as PP
    psets = _psets_with([("Pset_Flag", ["tank_shell"], [("Flag", "IFCLABEL", "__BOOL__")]),
                         ("Pset_Len", ["tank_shell"], [("Flag", _L, 1)])])
    text = ifc_text(PRODUCTS, psets).replace("IFCLABEL('__BOOL__')", "IFCBOOLEAN(.T.)")
    coll = PP.collect(_write(tmp_path, text, "bool.ifc"))
    assert coll["params"]["Flag"] == ("text", "Yes"), coll["params"]["Flag"]
    src = coll["sources"]["Flag"]
    assert src["raw_value"] is True and src.get("conflicting_values") == [1.0], src
