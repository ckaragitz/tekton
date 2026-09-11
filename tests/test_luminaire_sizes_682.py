"""test_luminaire_sizes_682.py -- a troffer builds at every catalog-resolved
size, not only 2x4 (#682).

Before: ``make_luminaire``'s troffer type description formatted six figures
with ``{value:g}`` / ``int(value)`` and guarded none of them.  The ``2BLT2``
member carries no photometrics (``wattage_w`` / ``lumens_lm`` / ``cct_k`` all
``None``, kind ``assumed``), so every size except 2x4 raised

    TypeError: unsupported format string passed to NoneType.__format__

before a single byte was written -- a traceback, not the honest refusal-by-name
this factory owes.  Supplying an explicit ``wattage`` did not help: the very
next placeholder reads ``lumens_lm``, which is ``None`` too.  The downlight
branch of the same expression already guarded its unknowns with ``or '?'``;
only the troffer branch was missed.

After: ``_figure()`` renders an unsourced figure as ``?`` -- unknown stays
unknown rather than raising or being fabricated (steer S-2026-08-11-a).

Then #703: not raising was necessary, not sufficient.  ``size='1x4'``
*delivered* a family NAMED "Recessed Troffer 1x4" built from the 2x2
member's housing (23.75 x 23.75 in, measured) because the resolver was
binary -- '2x4' -> 2BLT4, anything else -> 2BLT2.  The facts file holds two
members and no more, so an unheld size is now refused BY NAME with the held
sizes listed; the prompt route still DELIVERS (hard rule 1) -- it never
passes an unheld size through, it delivers the default member and says
"NOT a 1x4" (rvt.frontdoor.taxonomy_build).

Evidence tiers: (1) the helper itself; (2) every HELD size builds, with and
without an explicit wattage; (2b) an unheld size is refused by name; (2c)
name <-> housing dims agree for every deliverable size; (2d) one figure, one
answer (CCT in the type name vs its description; unpublished photometrics
blank, never 0); (3) the description of a member with no photometrics says so
and invents nothing; (4) the WRITTEN .rfa -- family-mode VALID 0 errors,
provenance clean; (5) 2x4 is unchanged (no regression on the sourced member).
"""
import pytest

from rvt.famgen import factory as F

#: built-in parameter id the type-table row stores its Description under
BIP_DESCRIPTION = -1010109


def _description(prod, idx: int = 0) -> str:
    """The Description cell of a product's type row."""
    _name, row = prod.doc.types[idx]
    return str(row[BIP_DESCRIPTION])


# ---------------------------------------------------------------------------
# (1) the helper
# ---------------------------------------------------------------------------

def test_figure_renders_unknown_instead_of_raising():
    assert F._figure(None) == "?"
    assert F._figure(38) == "38"
    assert F._figure(4400.0) == "4400"
    assert F._figure(3500, ".0f") == "3500"
    assert F._figure(None, ".0f", unknown="--") == "--"


# ---------------------------------------------------------------------------
# (2) every size builds -- the regression this issue is about
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("size", ["2x4", "2x2"])
@pytest.mark.parametrize("wattage", [None, 30])
def test_troffer_builds_at_every_held_size(size, wattage):
    prod = F.make_luminaire(kind="recessed-troffer", size=size, wattage=wattage)
    assert prod.doc.name.startswith("Recessed Troffer")
    assert size in prod.doc.name
    assert prod.forms, "a troffer must author its housing solid"


# ---------------------------------------------------------------------------
# (2b) a size the catalog does NOT hold is refused BY NAME, never delivered
# as another member's housing wearing that name (#703)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("size", ["1x4", "1x2", "4x4", "zzz"])
def test_unheld_troffer_size_is_refused_by_name(size):
    with pytest.raises(F.FactoryError) as e:
        F.make_luminaire(kind="recessed-troffer", size=size)
    msg = str(e.value)
    assert size in msg, "the refusal names the size asked for"
    assert "2x2" in msg and "2x4" in msg, "and lists the sizes we hold"


@pytest.mark.parametrize("size,written", [("2 x 4", "2BLT4-38W"), ("2'x4'", "2BLT4-38W"),
                                          ("2X2", "2BLT2"),
                                          # these two are what troffer_size()
                                          # ACTUALLY normalises beyond the three
                                          # spellings above -- the multiplication
                                          # sign and the hyphen both fold to 'x'.
                                          # Untested until the #703 review asked
                                          # what the new normalisations do; a
                                          # test that only pins what already
                                          # worked pins nothing (#674 round 5).
                                          ("2×4", "2BLT4-38W"),
                                          ("2-4", "2BLT4-38W"),
                                          ("2x4 ft", "2BLT4-38W")])
def test_trade_size_spelling_resolves_to_its_own_member(size, written):
    assert F.resolve_luminaire_facts("recessed-troffer", size=size).variant == written


def test_route_and_constructor_agree_on_which_sizes_are_held():
    """The prompt route's caveat set IS the factory's member set (#703 review).

    Failure this pins: someone adds a sourced 1x4 member to the facts file
    and to ``_TROFFER_MEMBERS``; the constructor builds it, but a
    hand-maintained copy in ``taxonomy_build`` still drops the size, so
    'a 1x4 troffer' silently delivers a 2x4 saying 'NOT a 1x4' -- with every
    test green.  Derived, not duplicated, so it cannot happen.
    """
    from rvt.frontdoor import taxonomy_build as TB
    assert TB._catalog_sizes() == F.held_troffer_sizes()
    assert F.held_troffer_sizes() == {"2x2", "2x4"}, \
        "if this changed, the route's caveat changed with it -- that is the point"


# ---------------------------------------------------------------------------
# (2c) name <-> housing dims agree for EVERY deliverable size (#703 DONE 2)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("size,length_in,width_in", [("2x4", 47.75, 23.75),
                                                     ("2x2", 23.75, 23.75)])
def test_name_and_housing_dims_agree(size, length_in, width_in):
    prod = F.make_luminaire(kind="recessed-troffer", size=size)
    assert size in prod.doc.name
    assert prod.facts.get("length_in") == length_in
    assert prod.facts.get("width_in") == width_in
    # the nominal trade size, in feet, is the housing rounded up to the grid
    nom_l, nom_w = sorted((float(x) for x in size.split("x")), reverse=True)
    assert nom_l * 12 - length_in == pytest.approx(0.25)
    assert nom_w * 12 - width_in == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# (2d) one figure, one answer: the type NAME rounds the CCT exactly as its
# own description does (#703 DONE 3 -- int() truncated: 3500.7 -> '3500K'
# next to a description reading '3501 K')
# ---------------------------------------------------------------------------

def test_type_name_cct_agrees_with_its_description():
    prod = F.make_luminaire(kind="recessed-troffer", size="2x4", cct=3500.7)
    name, _row = prod.doc.types[0]
    assert "3501K" in name
    assert "3501 K" in _description(prod)


def test_unpublished_photometrics_are_blank_in_the_type_catalog():
    """A figure the record does not publish is written as NOTHING in the
    user-facing type catalog, never as 0 (S-2026-08-11-a)."""
    prod = F.make_luminaire(kind="recessed-troffer",
                            types=[{"size": "2x4", "wattage": 38}, {"size": "2x2"}])
    lines = F.type_catalog_text(prod).splitlines()
    ncols = [len(ln.split(",")) for ln in lines]
    assert len(set(ncols)) == 1, f"ragged catalog: {ncols}"
    unknown_row = [ln for ln in lines if ln.startswith("2x2,")][0]
    assert unknown_row.split(",")[1:4] == ["", "", ""], unknown_row
    assert "0" not in unknown_row.split(",")[1:4]


# ---------------------------------------------------------------------------
# (3) an unsourced figure stays unknown, and is never invented
# ---------------------------------------------------------------------------

def test_unsourced_photometrics_are_unknown_not_fabricated():
    facts = F.resolve_luminaire_facts("recessed-troffer", size="2x2",
                                      wattage=None, lumens=None, cct=None,
                                      voltage="120-277", aperture_in=None)
    # precondition: this member is exactly the one with no photometrics
    assert facts.get("wattage_w") is None
    assert facts.get("lumens_lm") is None

    prod = F.make_luminaire(kind="recessed-troffer", size="2x2")
    desc = _description(prod)
    assert "? W" in desc and "? lm" in desc and "? K" in desc
    # the dimensions ARE sourced for this member, so they must still print
    assert "?" not in desc.split("(", 1)[1]


# ---------------------------------------------------------------------------
# (4) the written family
# ---------------------------------------------------------------------------

def test_2x2_troffer_writes_and_validates(tmp_path):
    prod = F.make_luminaire(kind="recessed-troffer", size="2x2")
    rep = prod.write(str(tmp_path / "troffer_2x2.rfa"), validate=True)
    assert rep["validate"]["family_mode"]["n_errors"] == 0, \
        rep["validate"]["family_mode"]["errors"]
    assert rep["provenance"]["ok"], rep["provenance"]["suspects"]


# ---------------------------------------------------------------------------
# (5) the sourced member is unchanged
# ---------------------------------------------------------------------------

def test_2x4_troffer_still_reports_its_catalog_figures():
    prod = F.make_luminaire(kind="recessed-troffer", size="2x4")
    desc = _description(prod)
    assert "38 W" in desc
    assert "?" not in desc
