"""#921: connector counts and ``m_index`` span every domain.

Power connectors live in ``doc.connectors``, conduit connectors in
``doc.mep_connectors``.  The reference corpus numbers ``m_index``
continuously across domains, so a power connector added after a conduit
connector takes the next index, never a reused one, and a family's summary
counts both.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.famgen import factory as F  # noqa: E402
from rvt.famgen import mep_connectors as MC  # noqa: E402
from rvt.famgen import skeleton as SK  # noqa: E402


def _index(con):
    return con.obj["m_index"]


def test_a_power_connector_after_a_conduit_connector_takes_the_next_index():
    doc = SK.new_family_document("electrical_equipment", "Zz Mixed")
    box = F.add_box_form(doc, 0.5, 0.5, 0.5)
    c = MC.add_conduit_connector(doc, host=box, face="top", location=(0, 0, 0.5),
                                 direction=(0, 0, 1), u_axis=(1, 0, 0), diameter_ft=0.0625)
    p = F.add_connector(doc, host=box, face="+y", location=(0, 0.25, 0.25),
                        direction=(0, 1, 0), u_axis=(1, 0, 0), voltage_v=120, poles=1)
    q = doc.add_electrical_connector(host_element_id=box.by_class("ExtrusionElem")[0].elem_id,
                                     host_geom_tag=F.box_face("-y")["tag"],
                                     location=(0, -0.25, 0.25), direction=(0, -1, 0),
                                     voltage=120, poles=1)
    assert [_index(c), _index(p), _index(q)] == [1, 2, 3]   # distinct and continuous


def test_the_summary_counts_every_domain():
    from rvt.famgen import fan_coil as FC
    prod = FC.make_fan_coil_unit()
    total = len(prod.doc.connectors) + len(getattr(prod.doc, "mep_connectors", []))
    assert len(getattr(prod.doc, "mep_connectors", [])) >= 1
    assert prod.summary()["connectors"] == total
