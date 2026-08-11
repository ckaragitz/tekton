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

Evidence tiers: (1) the helper itself; (2) every size builds, with and without
an explicit wattage; (3) the description of a member with no photometrics says
so and invents nothing; (4) the WRITTEN .rfa -- family-mode VALID 0 errors,
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

@pytest.mark.parametrize("size", ["2x4", "2x2", "1x4"])
@pytest.mark.parametrize("wattage", [None, 30])
def test_troffer_builds_at_every_size(size, wattage):
    prod = F.make_luminaire(kind="recessed-troffer", size=size, wattage=wattage)
    assert prod.doc.name.startswith("Recessed Troffer")
    assert size in prod.doc.name
    assert prod.forms, "a troffer must author its housing solid"


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
