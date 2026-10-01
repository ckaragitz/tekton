"""The Family Types "Lock" column follows the segment lock bits (#915).

In every Revit-born family of the reference corpus,
``Family.m_lockedParameterIdsForDirectManipulation`` holds exactly the
parameters whose labelled dimension segments carry the lock bit
(``m_ArrSegInfo[k].m_flags & 1``): 262 of 262 members have it, 1,994 of 1,994
non-members do not, and the list is empty in 279 of 421 families.  Ours used to
list every length parameter, so the owner's Family Types dialog showed Lock
ticked on all of them (#900 screenshot).
"""
from __future__ import annotations

import pytest

from rvt.famgen import factory as F
from rvt.famgen import skeleton as SK

LOCK = "m_lockedParameterIdsForDirectManipulation"


@pytest.mark.parametrize("key, prompt", [
    ("strut_trapeze", "a 2 tier slotted trapeze with threaded rod"),
    ("cable_tray", None), ("wireway", None), ("junction_box", None),
    ("strut_channel", None), ("lighting_control_panel", None), ("conduit", None),
])
def test_no_archetype_locks_a_parameter_whose_dimensions_are_unlocked(key, prompt):
    prod = (F.make_archetype(product=key, prompt=prompt) if prompt
            else F.make_archetype(product=key))
    doc = prod.doc
    state = SK.labelled_lock_state(doc)
    locked = doc.self_family.obj[LOCK]
    assert locked == sorted(p for p, on in state.items() if on)
    assert not any(p in locked for p, on in state.items() if not on)


def test_the_list_is_never_filled_from_the_length_parameters():
    prod = F.make_generic_model(parts=[{"shape": "box", "name": "a", "width_ft": 1.0,
                                        "depth_ft": 1.0, "height_ft": 1.0,
                                        "center": [0.0, 0.0]}],
                                name="f", numeric_params={"A": ("length", 1.0),
                                                          "B": ("length", 2.0)})
    assert prod.doc.self_family.obj[LOCK] == []


def test_a_locked_labelled_segment_puts_its_parameter_in_and_unlocking_takes_it_out():
    prod = F.make_archetype(product="wireway")
    doc = prod.doc
    seg = next(s for e in doc.elements if isinstance(e.obj, dict)
               for s in e.obj.get("m_ArrSegInfo") or () if s.get("m_paramId", -1) >= 0)
    pid = seg["m_paramId"]
    seg["m_flags"] = int(seg.get("m_flags", 0)) | 1
    assert pid in SK.sync_locked_params(doc)
    seg["m_flags"] &= ~1
    assert pid not in SK.sync_locked_params(doc)


def test_an_entry_that_labels_no_dimension_is_left_alone():
    """A built-in a residue lists on purpose (the catchain cost BIP) stays."""
    prod = F.make_archetype(product="wireway")
    doc = prod.doc
    doc.self_family.obj[LOCK] = [-1001]
    assert SK.sync_locked_params(doc) == [-1001]
