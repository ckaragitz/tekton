"""test_orient_514.py -- the rigid re-orientation allow-list (#514).

WHY THIS EXISTS.  ``rvt.famgen.orient`` places a FINISHED B-rep by walking the
record and transforming fields named in an ALLOW-LIST.  That design is right --
``m_keys`` carries history tags like ``[3, i, -1]`` that merely LOOK like a
3-vector, and rotating them corrupts element history -- but it has one failure
mode, and it is the quiet kind:

    a geometric field the allow-list does NOT name is left unrotated, so the
    body's halves disagree -- and our validator still says VALID, because every
    field is individually well-formed.

Desktop verdicts exist for the shapes authored today (probe A and the tray,
``docs/inbox/swept-solids-arbitrary-axis.md``).  These tests are the guard for
the NEXT shape: they fail by NAME when a form starts carrying a 3-vector the
allow-list has never seen, instead of letting a half-rotated body ship.

Tiers: (1) the matrix; (2) fields that must never move; (3) points vs
directions; (4) identity and recursion; (5) the sweep over a REAL authored
form -- the one that earns this file.
"""
import math

import pytest

from rvt.famgen import geometry as G, orient as O, skeleton as SK


def _doc():
    return SK.new_family_document("generic_model", "Orient Probe",
                                  part_type=SK.PART_TYPE["normal"],
                                  work_plane_based=True, start_id=1000,
                                  plane_length_ft=6.0)


def _det(M):
    return (M[0][0] * (M[1][1] * M[2][2] - M[1][2] * M[2][1])
            - M[0][1] * (M[1][0] * M[2][2] - M[1][2] * M[2][0])
            + M[0][2] * (M[1][0] * M[2][1] - M[1][1] * M[2][0]))


# ---------------------------------------------------------------------------
# (1) the matrix
# ---------------------------------------------------------------------------

def test_plus_z_is_exactly_the_identity():
    """Upright bodies stay BIT-identical -- what makes this module safe to add
    to a lineage with desktop verdicts behind it."""
    assert O.rotation_from_z((0.0, 0.0, 1.0)) == [[1.0, 0.0, 0.0],
                                                  [0.0, 1.0, 0.0],
                                                  [0.0, 0.0, 1.0]]


@pytest.mark.parametrize("d", [(0, 1, 0), (1, 0, 0), (1, 1, 0), (0, 0, -1),
                               (1e-9, 0, -1), (0.3, -0.7, 0.2), (0, 0, 5)])
def test_rotation_is_proper_and_maps_z_onto_the_axis(d):
    """det == +1 (a mirror would invert the solid) and R . +Z == the axis."""
    R = O.rotation_from_z(d)
    assert _det(R) == pytest.approx(1.0, abs=1e-9), "mirroring would flip the body"
    n = math.sqrt(sum(float(c) * float(c) for c in d))
    assert O._apply(R, (0.0, 0.0, 1.0)) == pytest.approx([c / n for c in d], abs=1e-9)


def test_degenerate_direction_never_yields_nan():
    """A zero-length segment is a caller bug: fail loudly, or be the identity --
    never a NaN matrix that silently corrupts every vector it touches."""
    try:
        R = O.rotation_from_z((0.0, 0.0, 0.0))
    except (ValueError, ZeroDivisionError):
        return
    assert all(c == c for row in R for c in row), "NaN in the rotation matrix"
    assert _det(R) == pytest.approx(1.0, abs=1e-9)


# ---------------------------------------------------------------------------
# (2) fields that must never move
# ---------------------------------------------------------------------------

def test_m_keys_is_never_rotated():
    """The module's own warning, pinned: m_keys holds history tags, not
    geometry.  A 'rotate any 3-element list' implementation passes every other
    test here and ships a broken family that still validates."""
    rec = {"m_keys": [3, 7, -1], "m_center": [1.0, 0.0, 0.0]}
    O.rotate_record(rec, O.rotation_from_z((0.0, 1.0, 0.0)))
    assert rec["m_keys"] == [3, 7, -1], "history tags were rotated as a vector"


def test_points_translate_and_directions_do_not():
    """Translating a frame axis makes every face frame drift with the body."""
    ident = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    rec = {"m_center": [0.0, 0.0, 0.0], "m_zVec": [0.0, 0.0, 1.0]}
    O.rotate_record(rec, ident, offset=(10.0, 0.0, 0.0))
    assert rec["m_center"] == [10.0, 0.0, 0.0], "a point must move"
    assert rec["m_zVec"] == [0.0, 0.0, 1.0], "a direction must NOT move"


def test_m_3x3_is_composed_as_a_matrix():
    """A Trf basis stays a transform: R . M, not three loose rotated rows."""
    R = O.rotation_from_z((0.0, 1.0, 0.0))
    M = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    rec = {"m_3x3": [row[:] for row in M]}
    O.rotate_record(rec, R, offset=(5.0, 5.0, 5.0))
    assert rec["m_3x3"] == O._matmul(R, M)
    assert _det(rec["m_3x3"]) == pytest.approx(1.0, abs=1e-9)


# ---------------------------------------------------------------------------
# (4) identity and recursion
# ---------------------------------------------------------------------------

def test_identity_leaves_a_nested_record_untouched():
    import copy
    rec = {"a": {"m_center": [1.0, 2.0, 3.0],
                 "b": [{"m_xVec": [0.0, 1.0, 0.0]},
                       {"m_keys": [1, 2, 3], "m_origin": [4.0, 5.0, 6.0]}]}}
    before = copy.deepcopy(rec)
    O.rotate_record(rec, O.rotation_from_z((0.0, 0.0, 1.0)))
    assert rec == before


def test_recursion_reaches_vectors_nested_inside_lists():
    rec = {"l1": [{"l2": {"l3": [{"m_center": [0.0, 0.0, 0.0]}]}}]}
    n = O.rotate_record(rec, O.rotation_from_z((0.0, 0.0, 1.0)),
                        offset=(1.0, 2.0, 3.0))
    assert n >= 1, "the walker never reached the nested vector"
    assert rec["l1"][0]["l2"]["l3"][0]["m_center"] == [1.0, 2.0, 3.0]


# ---------------------------------------------------------------------------
# (5) THE SWEEP -- over a real authored form
# ---------------------------------------------------------------------------

#: 3-float lists that are deliberately NOT geometry.  Every entry needs a
#: reason; an unexplained name here is how an allow-list rots.
KNOWN_NON_GEOMETRY = {
    "m_keys",           # history tags [3, i, -1]: integers shaped like a vector
    "m_endParams",      # frame-local uv parameters, not a point in space
}


def _vec3_fields(obj, out, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if O._is_vec3(v):
                out.setdefault(k, set()).add(path + "/" + k)
            else:
                _vec3_fields(v, out, path + "/" + k)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _vec3_fields(item, out, "%s[%d]" % (path, i))


def _authored_forms():
    """Real forms, authored through the factory exactly as a family is.

    The ``add_*`` wrappers are the entry point (they take a ``FamilyDoc`` and
    build the context themselves); ``geometry.prism_form`` takes an internal
    ``FamilyDocContext`` and is not the caller-facing shape.
    """
    from rvt.famgen import factory as F
    return [("cylinder", F.add_cylinder_form(_doc(), 0.666667, 0.8333)),
            ("box", F.add_box_form(_doc(), 0.5, 0.75, 1.25)),
            ("polygon", F.add_polygon_form(
                _doc(), [[0.0, 0.0], [0.6, 0.0], [0.3, 0.5]], 1.0))]


@pytest.mark.parametrize("what", ["cylinder", "box", "polygon"])
def test_no_unclassified_three_vector_in_an_authored_form(what):
    """THE guard: every 3-vector a real authored form carries is either
    rotated by ``orient`` or explicitly declared non-geometry.

    When a new shape emits a geometric field the allow-list has never seen,
    this fails BY NAME -- instead of shipping a body whose halves disagree
    while the validator calls it VALID.
    """
    forms = dict(_authored_forms())
    if what not in forms:
        pytest.skip("%s form not available in this checkout" % what)

    found = {}
    for el in getattr(forms[what], "elements", forms[what]):
        _vec3_fields(getattr(el, "obj", el), found)
    assert found, "no 3-vectors found at all -- the probe is broken, not the code"

    handled = set(O.VECTOR_FIELDS) | KNOWN_NON_GEOMETRY | {"m_3x3"}
    unclassified = {k: sorted(v)[:2] for k, v in found.items() if k not in handled}
    assert not unclassified, (
        "3-vector fields an authored %s carries that orient.py neither rotates "
        "nor declares non-geometry -- classify each one in POINT_FIELDS, "
        "DIRECTION_FIELDS or KNOWN_NON_GEOMETRY: %r" % (what, unclassified))
