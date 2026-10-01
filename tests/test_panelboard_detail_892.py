"""#892 (#885 parity): a generated panelboard is built from its real parts, not a labelled box.

``rvt.famgen.equipment_detail.panelboard_parts`` lays out the FRONT of the cabinet
on the catalog box (which stays the parameter-driven enclosure form): a front trim,
a hinged door with two hinges on the left as you face it, a latch handle on the
right, and a nameplate -- nominal proportions, never a manufacturer drawing.  ``make_panelboard`` authors them after the box, and the NEC
working space starts in front of the door hardware.

"Looks right in Revit" is a desktop claim (hard rule 4); these tests pin what the
file carries.
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.famgen import equipment_detail as ED  # noqa: E402
from rvt.famgen import factory as F  # noqa: E402

IN = 1 / 12.0


@pytest.mark.parametrize("W,D,H", [(20 * IN, 5.75 * IN, 48 * IN),   # PRL1X 225 A / 42 ckt
                                   (36 * IN, 11.31 * IN, 90 * IN),  # a PRL4X box
                                   (14 * IN, 4 * IN, 20 * IN)])     # a small one
def test_the_front_parts_stand_on_the_box_face(W, D, H):
    parts = ED.panelboard_parts(W, D, H)
    roles = [p.role for p in parts]
    for role, n in (("front trim", 1), ("door", 1), ("door hinge", 2), ("door latch handle", 1),
                    ("nameplate", 1)):
        assert roles.count(role) == n, role
    for p in parts:
        assert p.w > 0 and p.d > 0 and p.h > 0
        assert p.cy - p.d / 2 >= D - 1e-9                       # nothing inside the box
        assert -W / 2 - 1e-9 <= p.cx - p.w / 2 and p.cx + p.w / 2 <= W / 2 + 1e-9
        assert -1e-9 <= p.z0 and p.z0 + p.h <= H + 1e-9
    assert 0 < ED.front_proud_ft(parts, D) < 1 * IN
    door = next(p for p in parts if p.role == "door")
    # facing the door from +y, your left is +x: hinges there, the latch on the right
    assert all(p.cx > door.cx + door.w / 2 - 0.5 * IN for p in parts if p.role == "door hinge")
    assert next(p for p in parts if p.role == "door latch handle").cx < 0


def test_a_flush_trim_laps_the_wall_opening():
    W, D, H = 20 * IN, 5.75 * IN, 48 * IN
    parts = ED.panelboard_parts(W, D, H, flush=True)
    trim = parts[0]
    assert trim.role == "front trim" and trim.cy - trim.d / 2 == pytest.approx(0.0)
    assert (trim.w, trim.h, trim.z0) == pytest.approx((W + 1.5 * IN, H + 1.5 * IN, -0.75 * IN))


def test_a_non_positive_or_tiny_box_is_refused():
    with pytest.raises(ValueError):
        ED.panelboard_parts(1.0, 0.0, 1.0)
    with pytest.raises(ValueError, match="too small"):
        ED.panelboard_parts(5 * IN, 4 * IN, 20 * IN)
    with pytest.raises(ValueError, match="too small"):
        ED.panelboard_parts(20 * IN, 4 * IN, 8 * IN)
    for W, H in ((6 * IN, 12 * IN), (20 * IN, 12 * IN)):         # the smallest allowed: sane parts
        parts = ED.panelboard_parts(W, 4 * IN, H)
        door = next(p for p in parts if p.role == "door")
        plate = next(p for p in parts if p.role == "nameplate")
        assert door.w > 0 and door.h > 0 and plate.z0 >= door.z0


@pytest.fixture(scope="module")
def panel():
    return F.make_panelboard(mains_a=225, spaces=42, voltage="208Y/120", mcb=True)


def test_the_branch_panel_is_authored_from_its_parts_and_validates(panel, tmp_path):
    f = panel.facts
    W, D, H = f.get("width_in") / 12, f.get("depth_in") / 12, f.get("height_in") / 12
    assert (f.get("width_in"), f.get("height_in"), f.get("depth_in")) == (20.0, 48.0, 5.75)
    parts = ED.panelboard_parts(W, D, H)
    roles = [x.params["role"] for x in panel.forms]
    assert roles[0] == "panelboard enclosure"
    assert roles[1:1 + len(parts)] == [p.role for p in parts]
    assert sum(r.startswith("clearance") for r in roles) == 2
    assert ED.PANEL_DETAIL_NOTE in panel.doc.notes
    front = next(x for x in panel.forms if x.params["role"] == "clearance: front working space").params
    assert front["center"][1] - front["depth_ft"] / 2 == pytest.approx(D + ED.front_proud_ft(parts, D))
    assert front["depth_ft"] == pytest.approx(3.0)              # 120 V to ground: 3 ft
    rep = panel.write(str(tmp_path / "pb.rfa"))
    fm = rep["validate"]["family_mode"]
    assert (fm["verdict"], fm["n_errors"]) == ("VALID", 0) and rep["provenance"]["ok"] is True


def test_the_dummy_variant_carries_no_front_parts():
    prod = F.make_panelboard(solid=False)
    assert len(prod.forms) == 1


def test_a_flush_panel_starts_its_working_space_at_the_wall_face_plus_hardware():
    prod = F.make_panelboard(mains_a=225, spaces=42, voltage="208Y/120", mounting="flush")
    f = prod.facts
    W, D, H = f.get("width_in") / 12, f.get("depth_in") / 12, f.get("height_in") / 12
    parts = ED.panelboard_parts(W, D, H, flush=True)
    front = next(x for x in prod.forms if x.params["role"] == "clearance: front working space").params
    assert front["center"][1] - front["depth_ft"] / 2 == pytest.approx(ED.front_proud_ft(parts, 0.0))
    box = prod.forms[0].params
    assert box["center"][1] == pytest.approx(-D / 2)                  # recessed behind the wall
    assert all(p.cy - p.d / 2 >= -1e-9 for p in parts)                  # the front stands on the wall


def test_the_factory_still_delivers_a_box_with_no_room_for_a_front(monkeypatch, tmp_path):
    def refuse(*a, **k):
        raise ValueError("a 4 x 8 in box is too small for a panelboard front")
    monkeypatch.setattr(ED, "panelboard_parts", refuse)
    prod = F.make_panelboard(mains_a=225, spaces=42, voltage="208Y/120")
    assert [x.params["role"] for x in prod.forms][0] == "panelboard enclosure"
    assert not any(x.params["role"] == "door" for x in prod.forms)
    assert any(n.startswith("panelboard front NOT drawn") for n in prod.doc.notes)
    rep = prod.write(str(tmp_path / "pb.rfa"))
    assert rep["validate"]["family_mode"]["n_errors"] == 0
