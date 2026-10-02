"""#973 -- a type-level or unattached pset value never blocks an occurrence's
pset drive (IFC's override rule: the occurrence value wins), and "the same
value" means the drive's own tolerance everywhere.

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


def _orphan(text, props):
    """Append an IfcPropertySet no relation links to any product (the shape a
    type-level set reached through HasPropertySets has here)."""
    lines = [f"#9{i:04d}=IFCPROPERTYSINGLEVALUE('{n}',$,{t}({float(v)!r}),$);"
             for i, (n, t, v) in enumerate(props)]
    ids = ",".join(f"#9{i:04d}" for i in range(len(props)))
    lines.append(f"#98000=IFCPROPERTYSET('{98000:022d}',#5,'Pset_Type',$,({ids}));")
    return text.replace("ENDSEC;\nEND-ISO", "\n".join(lines) + "\nENDSEC;\nEND-ISO")


def test_an_unattached_differing_value_does_not_block_the_drive(tmp_path):
    from rvt.ifc import pset_drive as PD
    text = _orphan(ifc_text(PRODUCTS, PSETS), [("BodyWidth", _L, 1500)])
    parts, coll = _measured(_write(tmp_path, text, "orphan_after.ifc"))
    src = coll["sources"]["BodyWidth"]
    assert "conflicting_values" not in src and src["products"] == ["tank_shell"]
    assert any("overridden by the occurrence value" in r["why"] for r in coll["skipped"]
               if r["name"] == "BodyWidth")
    row = _rows(PD.plan(parts, coll))["BodyWidth"]
    assert row["status"] == PD.DRIVES and (row["part"], row["axis"]) == ("tank_shell", "x"), row


def test_an_occurrence_value_overrides_a_type_value_seen_first(tmp_path):
    """Order-free: the unattached set ahead of the occurrence's set in the file."""
    from rvt.ifc import pset_drive as PD
    base = ifc_text(PRODUCTS, PSETS)
    head, rest = base.split("#100=", 1)
    orphan = _orphan("ENDSEC;\nEND-ISO", [("BodyWidth", _L, 1500)]).replace(
        "\nENDSEC;\nEND-ISO", "\n")
    text = head + orphan + "#100=" + rest
    parts, coll = _measured(_write(tmp_path, text, "orphan_first.ifc"))
    assert abs(coll["params"]["BodyWidth"][1] - 1574.8 / 304.8) < 1e-9
    assert coll["sources"]["BodyWidth"]["products"] == ["tank_shell"]
    assert _rows(PD.plan(parts, coll))["BodyWidth"]["status"] == PD.DRIVES


def test_a_repeat_within_the_drive_tolerance_is_the_same_value(tmp_path):
    """1574.8 vs 1574.8001 mm: ~3.3e-7 ft apart, under SPAN_TOL -- not a conflict,
    and not reported as a 'different value' either."""
    from rvt.ifc import pset_drive as PD
    from rvt.ifc import pset_params as PP
    assert PP.SAME_LENGTH_FT == PD.SPAN_TOL
    psets = PSETS + [("Pset_Body2", ["tank_shell"], [("BodyWidth", _L, 1574.8001)])]
    parts, coll = _measured(_write(tmp_path, ifc_text(PRODUCTS, psets), "tol.ifc"))
    assert "conflicting_values" not in coll["sources"]["BodyWidth"]
    assert not [r for r in coll["skipped"] if r["name"] == "BodyWidth"]
    assert _rows(PD.plan(parts, coll))["BodyWidth"]["status"] == PD.DRIVES


def test_a_real_conflict_is_still_a_value(tmp_path):
    from rvt.ifc import pset_drive as PD
    psets = PSETS + [("Pset_Body2", ["tank_shell"], [("BodyWidth", _L, 1500)])]
    parts, coll = _measured(_write(tmp_path, ifc_text(PRODUCTS, psets), "real.ifc"))
    row = _rows(PD.plan(parts, coll))["BodyWidth"]
    assert row["status"] == PD.VALUE_ONLY and "conflicting values" in row["reason"], row
