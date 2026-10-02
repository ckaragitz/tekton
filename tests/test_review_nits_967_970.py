"""Review nits from merged #967 (IFC pset drives) and #970 (perf gate).

* a label the IFC states with CONFLICTING values on one product stays a value
  (the drive plan sees the conflict, not only ``skipped``);
* a pset linked to its products by SEVERAL ``IfcRelDefinesByProperties`` (the
  schema forbids it; an exporter may not) keeps every owner, so it names no
  single part -- before, the last relation won and drove that product alone.

Pure plan-level checks: nothing is built, so no release context is entered.
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


def test_conflicting_values_on_one_owner_are_a_value(tmp_path):
    from rvt.ifc import pset_drive as PD
    psets = PSETS + [("Pset_Body2", ["tank_shell"], [("BodyWidth", _L, 1500)])]
    parts, coll = _measured(_write(tmp_path, ifc_text(PRODUCTS, psets), "conflict.ifc"))
    assert coll["sources"]["BodyWidth"]["conflicting_values"] == [1500.0]
    row = _rows(PD.plan(parts, coll))["BodyWidth"]
    assert row["status"] == PD.VALUE_ONLY and "conflicting values" in row["reason"], row


def test_an_equal_repeat_on_one_owner_still_drives(tmp_path):
    """Two psets on ONE product carrying the same value are one owner, no conflict."""
    from rvt.ifc import pset_drive as PD
    psets = PSETS + [("Pset_Body2", ["tank_shell"], [("BodyWidth", _L, 1574.8)])]
    parts, coll = _measured(_write(tmp_path, ifc_text(PRODUCTS, psets), "same.ifc"))
    row = _rows(PD.plan(parts, coll))["BodyWidth"]
    assert row["status"] == PD.DRIVES and (row["part"], row["axis"]) == ("tank_shell", "x"), row


def test_a_pset_linked_by_two_relations_keeps_both_owners(tmp_path):
    from rvt.ifc import pset_drive as PD
    text = ifc_text(PRODUCTS, PSETS + [("Pset_Leg", ["pad_slab"], [("LegHeight", _L, 150)])])
    rel = [ln for ln in text.splitlines() if "IFCRELDEFINESBYPROPERTIES" in ln][-1]
    tank = [ln for ln in text.splitlines() if "'tank_shell'" in ln][0].split("=")[0]
    pad = [ln for ln in text.splitlines() if "'pad_slab'" in ln][0].split("=")[0]
    extra = rel.replace(rel.split("=")[0], "#99999", 1).replace(f"({pad})", f"({tank})")
    text = text.replace("ENDSEC;\nEND-ISO", extra + "\nENDSEC;\nEND-ISO")
    parts, coll = _measured(_write(tmp_path, text, "tworel.ifc"))
    assert sorted(coll["sources"]["LegHeight"]["products"]) == ["pad_slab", "tank_shell"]
    row = _rows(PD.plan(parts, coll))["LegHeight"]
    assert row["status"] == PD.VALUE_ONLY and "2 products" in row["reason"], row
