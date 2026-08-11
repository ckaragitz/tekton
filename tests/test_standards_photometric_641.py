"""test_standards_photometric_641.py -- the photometric-web reference is ONE
caption on every luminaire route (#641).

Issue #641 (Refs #631 #622 #601, steer S-2026-08-11-a: one parameter per
meaning): after #631 the IFC-born downlight (``rvt.ifc.famfrom_ifc``) and the
prompt-born luminaire (``rvt.famgen.factory.make_luminaire``) spelled every
shared quantity identically EXCEPT the IES / photometric-web reference --
``Photometric Web File`` on one route, ``IES File (URL reference)`` on the
other -- and ``standards.meaning_key`` did not know they were one quantity, so
no instrument noticed.  Now ``standards.SYNONYM_GROUPS`` folds every spelling
onto Revit's own caption, ``Photometric Web File``, and the factory authors that
caption too.  It stays constructor-authored (no Lighting Fixtures table row):
in Revit the parameter belongs to a family's light source, which not every
lighting-fixture family defines, so every OTHER constructor is untouched.

Evidence tiers: (1) the table -- the spellings fold, ``--check`` is clean;
(2) the documents -- the prompt-born luminaire (troffer and downlight) carries
exactly one spelling, Revit's, with the catalog URL under it, and a caller's
legacy spelling never grows a twin; both routes agree; (3) ON THE FILE -- the
written ``.rfa`` is family-mode VALID with 0 errors, provenance clean, and the
captions read back with exactly one spelling and pairwise-distinct meanings.

Validator-green is necessary, NOT certification (hard rule 4).  Fresh-clone
safe: bundled base, bundled steplite reader, tracked IFC input.

Run: .venv/bin/python -m pytest tests/test_standards_photometric_641.py -q
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from conftest import HAVE_SCHEMA, needs_schema                 # noqa: E402
from rvt.famgen import standards as ST                         # noqa: E402
from rvt.famgen import factory as F                            # noqa: E402
from rvt.ifc import famfrom_ifc as FI                          # noqa: E402
from rvt.ifc import product_facts as PF                        # noqa: E402

CANON = "Photometric Web File"                                  # Revit's own caption
LEGACY = "IES File (URL reference)"                             # the factory's, until #641
SPELLINGS = (CANON, "Photometric Web", "Photometric File", LEGACY, "IES File",
             "IES Photometric File", "photometric_web_file", "IESFile")

needs_ifc = pytest.mark.skipif(not (HAVE_SCHEMA and os.path.exists(PF.DEFAULT_IFC)),
                               reason="class schema / tracked IFC input absent")


def _twins(names):
    """{meaning key: [captions]} for every quantity spelled more than once."""
    by_key = {}
    for n in names:
        by_key.setdefault(ST.meaning_key(n), []).append(n)
    return {k: v for k, v in by_key.items() if len(v) > 1}


def _present(names):
    """The photometric-web spellings among ``names``."""
    return sorted(n for n in names if ST.meaning_key(n) == ST.meaning_key(CANON))


# ---------------------------------------------------------------------------
# 1. the table
# ---------------------------------------------------------------------------

def test_every_spelling_of_the_photometric_web_reference_is_one_meaning():
    keys = {ST.meaning_key(s) for s in SPELLINGS}
    assert keys == {ST.meaning_key(CANON)}
    group = next(g for g in ST.SYNONYM_GROUPS if CANON in g)
    assert group[0] == CANON                        # the spelling we standardise on
    assert LEGACY in group


def test_the_table_is_sound_and_no_category_lists_the_reference_twice():
    assert ST.check_specs() == []
    # constructor-authored, not a table row: no category grows it as a blank
    key = ST.meaning_key(CANON)
    listed = {cat for cat, rows in ST.CATEGORY_STANDARDS.items()
              for p in rows if ST.meaning_key(p.name) == key}
    assert listed == set()


# ---------------------------------------------------------------------------
# 2. the documents
# ---------------------------------------------------------------------------

@needs_schema
@pytest.mark.parametrize("kwargs", [{}, {"kind": "downlight"},
                                    {"types": [30, 38, 48]}])
def test_the_prompt_born_luminaire_carries_revits_caption_once(kwargs):
    prod = F.make_luminaire(**kwargs)
    names = set(prod.doc.params)
    assert _present(names) == [CANON]
    assert _twins(names) == {}
    pid = prod.doc.params[CANON].elem_id
    for _tname, vals in prod.doc.types:              # the catalog URL rides under it
        assert isinstance(vals[pid], str)
    _t0, vals0 = prod.doc.types[0]
    if kwargs.get("kind") != "downlight":
        assert vals0[pid].startswith("http")         # the troffer record's S2 URL


@needs_schema
def test_a_callers_legacy_spelling_never_grows_a_twin():
    """``standard_values`` under the old factory spelling is the constructor's
    own quantity: nothing is authored beside ``Photometric Web File`` and the
    value is NAMED as not placed (a constructor-owned parameter is filled by
    the constructor, never redefined by the standards step)."""
    prod = F.make_luminaire(standard_values={LEGACY: "https://example.invalid/x.ies",
                                             "IES File": "y.ies"})
    names = set(prod.doc.params)
    assert _present(names) == [CANON] and _twins(names) == {}
    rep = prod.standards
    assert not any(ST.meaning_key(a["name"]) == ST.meaning_key(CANON) for a in rep["applied"])
    assert set(rep.get("values_not_placed", [])) == {LEGACY, "IES File"}


@needs_ifc
def test_both_luminaire_routes_spell_the_reference_the_same_way():
    ifc_born = FI.make_downlight(facts=PF.extract_product_facts(PF.DEFAULT_IFC), start_id=1000)
    prompt_born = F.make_luminaire(kind="downlight")
    assert _present(ifc_born.doc.params) == [CANON]
    assert _present(prompt_born.doc.params) == [CANON]
    a = {ST.meaning_key(n): n for n in ifc_born.doc.params}
    b = {ST.meaning_key(n): n for n in prompt_born.doc.params}
    assert {k: (a[k], b[k]) for k in set(a) & set(b) if a[k] != b[k]} == {}


# ---------------------------------------------------------------------------
# 3. on the file
# ---------------------------------------------------------------------------

def _write_and_read_captions(prod, path):
    from rvt.frontdoor.standalone import standalone_family_write
    from rvt.families import FamilyIndex
    rep = standalone_family_write(prod, path)
    fam = (rep.get("validate") or {}).get("family_mode") or {}
    assert fam.get("verdict") == "VALID" and fam.get("n_errors") == 0, fam.get("errors")
    assert (rep.get("provenance") or {}).get("ok") is True, rep["provenance"].get("suspects")
    assert rep["ok"] is True
    idx = FamilyIndex(path)
    return {idx.value(0, eid)["m_pParamDef"]["value"]["m_caption"]
            for eid in idx.ids_of_class(0, "ParamElemFamily")}


@needs_schema
def test_the_written_luminaire_reads_back_one_caption_and_no_meaning_twins(tmp_path):
    prod = F.make_luminaire()
    caps = _write_and_read_captions(prod, str(tmp_path / "troffer.rfa"))
    assert caps == set(prod.doc.params)              # the file carries what the doc does
    assert _present(caps) == [CANON]
    assert LEGACY not in caps
    assert _twins(caps) == {}
    assert len({ST.meaning_key(c) for c in caps}) == len(caps)
