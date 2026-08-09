"""hostsym-product (#10) -- the host symbol law lives in the two loaders.

The corpus law (measured on 36 native host Family rows, docs/inbox/species.md
1.2): a loaded family's HOST side carries real-named FamSymSurrogate +
FamilySymbol pairs only, its host Family type table has exactly ONE leading
blank ' ' current-values row with ``m_idx`` on a real pair, and no instance
binds a blank-named symbol.  The UNIT side keeps the born blank-pair-first
table (`[' ', real..]`).  Both loaders used to leak the unit's blank pair to
the host side; birthright v3 patched that opt-in.  These tests pin the law
on the product loaders themselves, on the pinned certified base (no samples/
needed), for the plain product document AND a born-shaped one -- and, since
type catalogs (#163), for a MULTI-TYPE product: N real-named pairs (one per
catalog selection), zero blank-named pairs, in both loaders.
"""
from __future__ import annotations

import os
import sys
from dataclasses import replace

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt import famload as FL                                       # noqa: E402
from rvt.famgen import birthright as BR                            # noqa: E402
from rvt.famgen import factory as F                                # noqa: E402
from rvt.famgen import loader as L                                 # noqa: E402

BASE = os.path.join(ROOT, "plugin", "assets", "genesis", "G_ABPD.rvt")

needs_base = pytest.mark.skipif(not os.path.isfile(BASE),
                                reason="pinned genesis base G_ABPD absent")


@pytest.fixture(scope="module")
def host():
    return L.survey_host(BASE)


@pytest.fixture(scope="module")
def fl_host():
    return FL.survey_host(BASE, categories=[L.CAT_ELECTRICAL_EQUIPMENT])


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _panel(start_id: int):
    return F.make_panelboard(vendor="eaton", line="pow-r-line", mains_a=400,
                            spaces=42, voltage="480Y/277", mcb=True,
                            mounting="surface", solid=True, start_id=start_id)


def _make_born_shaped(doc, *, current_on_blank: bool = False):
    """Give ``doc`` the born blank-pair-first type table (the shape birthright
    v2's TYPES lane authors and every standalone-born .rfa carries) and
    re-finalize so the unit-side FamilyTypeTable is baked `[' ', real]`.
    ``current_on_blank`` mimics an extracted foreign family (current_type 0
    on a blank-first table)."""
    doc.finalized = False
    _name, vals = doc.types[doc.current_type]
    doc.types = [(" ", dict(vals))] + list(doc.types)
    doc.current_type = 0 if current_on_blank else doc.current_type + 1
    doc.finalize()
    return doc


def _table(family_obj):
    """(row names, m_idx) of a Family element's FamilyTypeTable."""
    ftt = family_obj["m_pFamilyTypes"]["value"]
    return [str(p.get("name", "")) for p in ftt["m_pairs"]], ftt["m_idx"]


# ---------------------------------------------------------------------------
# 1. the pure contracts
# ---------------------------------------------------------------------------

class _Doc:
    def __init__(self, types, current_type=0):
        self.types = types
        self.current_type = current_type


class TestPureLaw:
    def test_real_type_names_drops_blanks_keeps_order(self):
        d = _Doc([(" ", {}), ("A", {}), ("", {}), ("B", {})])
        assert L.real_type_names(d) == ["A", "B"]

    def test_real_type_names_empty(self):
        assert L.real_type_names(_Doc([])) == []
        assert L.real_type_names(_Doc([(" ", {})])) == []

    def test_symbol_type_name_prefers_real_current(self):
        d = _Doc([(" ", {}), ("A", {}), ("B", {})], current_type=2)
        assert L.symbol_type_name(d, "fb") == "B"

    def test_symbol_type_name_skips_blank_current(self):
        d = _Doc([(" ", {}), ("A", {}), ("B", {})], current_type=0)
        assert L.symbol_type_name(d, "fb") == "A"

    def test_symbol_type_name_fallback(self):
        assert L.symbol_type_name(_Doc([]), "fb") == "fb"
        assert L.symbol_type_name(_Doc([(" ", {})]), "fb") == "fb"
        assert L.symbol_type_name(_Doc([("A", {})], current_type=7), "fb") == "A"


# ---------------------------------------------------------------------------
# 2. the famgen loader (component families; the front door's load lane)
# ---------------------------------------------------------------------------

@needs_base
class TestFamgenLoader:
    def test_plain_product_host_table(self, host):
        prod = _panel(host.watermark + 1)
        plan = L.plan_load(prod, host, place=True)
        el = L.author_host_family(prod, plan, host)
        names, idx = _table(el.obj)
        assert names == [" ", "400A MCB 42ckt"] and idx == 1
        assert plan.type_name == "400A MCB 42ckt"

    def test_born_shaped_product_no_double_blank(self, host):
        """The DEMO v8 leak: unit table `[' ', real]` copied verbatim behind
        the loader's own blank -> `[' ', ' ', real]`, m_idx on a blank."""
        prod = _panel(host.watermark + 1)
        _make_born_shaped(prod.doc)
        unit_names, unit_idx = _table(prod.doc.self_family.obj)
        assert unit_names == [" ", "400A MCB 42ckt"] and unit_idx == 1   # unit side keeps the born law
        plan = L.plan_load(prod, host, place=True)
        el = L.author_host_family(prod, plan, host)
        assert _table(el.obj) == ([" ", "400A MCB 42ckt"], 1)   # one leading blank, m_idx on real
        # the unit-side table is untouched by the host authoring
        assert _table(prod.doc.self_family.obj) == (unit_names, unit_idx)

    def test_symbol_and_surrogate_never_blank_named(self, host):
        """Extract->place shape: current_type 0 on a blank-first table."""
        prod = _panel(host.watermark + 1)
        _make_born_shaped(prod.doc, current_on_blank=True)
        plan = L.plan_load(prod, host, place=False)
        assert plan.type_name == "400A MCB 42ckt"
        ssur = L.author_famsym_surrogate(plan, host.category)
        assert ssur.obj["m_name"].strip()
        sym, _geo = L.author_family_symbol(prod, plan, host, L._type_rows(prod), solid=False)
        assert sym.obj["m_symbolInfo"]["value"]["m_name"] == "400A MCB 42ckt"

    def test_dry_run_load_is_lawful_end_to_end(self, host):
        prod = _panel(host.watermark + 1)
        _make_born_shaped(prod.doc)
        res = L.load_family_into_project(BASE, None, product=prod, place=False,
                                         symbol_solid=False, validate=False)
        gate = res.proofs["roundtrip_gate"]
        assert gate["failed"] == 0 and gate["roundtrip_ok"] == gate["records"]
        classes = [e["class"] for e in res.elements]
        assert classes.count("FamilySymbol") == 1 and classes.count("FamSymSurrogate") == 1

    def test_birthright_v3_loader_half_is_now_a_noop(self, host):
        """v3's opt-in loader patch finds nothing left to drop."""
        prod = _panel(host.watermark + 1)
        _make_born_shaped(prod.doc)
        plan = L.plan_load(prod, host, place=True)
        el = L.author_host_family(prod, plan, host)
        before = _table(el.obj)
        rep = BR.apply_host_family_table_law(el)
        assert rep["applied"] is False and rep["dropped_blank_rows"] == 0
        assert _table(el.obj) == before


# ---------------------------------------------------------------------------
# 3. famload (the four-registry loader: one host symbol pair per REAL type)
# ---------------------------------------------------------------------------

@needs_base
class TestFamload:
    def _plan(self, fl_host, doc):
        fl = FL.FamilyLoad(key="panel", doc=doc)
        plan, _nxt = FL._plan_family(fl, doc, fl_host, fl_host.watermark + 1)
        return plan

    def test_born_shaped_doc_plans_real_types_only(self, fl_host):
        """The SC1 leak: one pair per doc.types entry incl. the blank, and the
        instance-facing symbol_id = the blank pair's."""
        doc = _make_born_shaped(_panel(fl_host.watermark + 1).doc)
        assert [n for n, _v in doc.types] == [" ", "400A MCB 42ckt"]
        plan = self._plan(fl_host, doc)
        assert plan.type_names == ["400A MCB 42ckt"]
        assert len(plan.symbol_ids) == 1 and len(plan.symbol_surrogate_ids) == 1
        assert plan.symbol_id == plan.symbol_ids[0] != FL.INVALID

    def test_host_elements_carry_no_blank_symbol(self, fl_host):
        doc = _make_born_shaped(_panel(fl_host.watermark + 1).doc)
        plan = self._plan(fl_host, doc)
        els = FL.author_host_elements(doc, plan)
        syms = [e for e in els if e.class_name == "FamilySymbol"]
        ssurs = [e for e in els if e.class_name == "FamSymSurrogate"]
        fams = [e for e in els if e.class_name == "Family"]
        assert len(syms) == len(ssurs) == 1 and len(fams) == 1
        assert syms[0].obj["m_symbolInfo"]["value"]["m_name"] == "400A MCB 42ckt"
        assert ssurs[0].obj["m_name"] == "400A MCB 42ckt"
        assert ssurs[0].obj["m_elemId"] == plan.symbol_id
        # the symbol carries the REAL type's parameter row, not an empty one
        assert syms[0].obj["m_pParams"]["value"]["m_params"]
        # host Family (annotation flavour): the single blank current-values row
        assert _table(fams[0].obj) == ([" "], 0)
        # unit side untouched: born blank-pair-first
        assert _table(doc.self_family.obj) == ([" ", "400A MCB 42ckt"], 1)

    def test_plain_doc_unchanged(self, fl_host):
        doc = _panel(fl_host.watermark + 1).doc
        plan = self._plan(fl_host, doc)
        assert plan.type_names == ["400A MCB 42ckt"]

    def test_all_blank_falls_back_to_family_name(self, fl_host):
        doc = _panel(fl_host.watermark + 1).doc
        doc.finalized = False
        _n, vals = doc.types[0]
        doc.types = [(" ", dict(vals))]
        doc.current_type = 0
        doc.finalize()
        plan = self._plan(fl_host, doc)
        assert plan.type_names == [str(doc.name)] and str(doc.name).strip()

    def test_dry_run_load_is_lawful_end_to_end(self, fl_host):
        doc = _make_born_shaped(_panel(fl_host.watermark + 1).doc)
        res = FL.load_family_documents(BASE, [FL.FamilyLoad(key="panel", doc=doc)],
                                       None, validate=False)
        gate = res.proofs["roundtrip_gate"]
        assert gate["failed"] == 0 and gate["roundtrip_ok"] == gate["records"]
        assert [p.type_names for p in res.plans] == [["400A MCB 42ckt"]]
        classes = [e["class"] for e in res.proofs["host_elements"]["by_family"]["panel"]]
        assert classes.count("FamilySymbol") == 1 and classes.count("FamSymSurrogate") == 1

    def test_birthright_v3_product_half_still_composes(self, fl_host):
        """v3's famload-facing strip stays valid ahead of the product law
        (it strips doc.types; famload would have skipped the blank anyway)."""
        doc = _make_born_shaped(_panel(fl_host.watermark + 1).doc)
        rep = BR.apply_host_symbol_law(doc)
        assert rep["applied"] is True and [n for n, _v in doc.types] == ["400A MCB 42ckt"]
        assert self._plan(fl_host, doc).type_names == ["400A MCB 42ckt"]


# ---------------------------------------------------------------------------
# 4. MULTI-TYPE families (type catalogs, #163): N real-named pairs, 0 blank
# ---------------------------------------------------------------------------

TYPES3 = ["225A MCB 42ckt", "400A MCB 42ckt", "600A MCB 42ckt"]


def _panel3(start_id: int):
    """ONE panelboard family with three catalog selections (225/400/600 A)."""
    return F.make_panelboard(vendor="eaton", line="pow-r-line", mains_a=400,
                            spaces=42, voltage="480Y/277", mcb=True,
                            mounting="surface", solid=True, start_id=start_id,
                            types=[225, 400, 600])


def _sym_names(elements):
    syms = [e for e in elements if e.class_name == "FamilySymbol"]
    ssurs = [e for e in elements if e.class_name == "FamSymSurrogate"]
    return ([s.obj["m_symbolInfo"]["value"]["m_name"] for s in syms],
            [s.obj["m_name"] for s in ssurs], syms, ssurs)


@needs_base
class TestMultiTypeFamgenLoader:
    def test_plan_has_one_pair_per_real_type_primary_first(self, host):
        prod = _panel3(host.watermark + 1)
        assert [n for n, _v in prod.doc.types] == TYPES3
        plan = L.plan_load(prod, host, place=True)
        assert plan.type_names == TYPES3 and plan.type_name == TYPES3[0]
        assert len(plan.symbol_ids) == len(plan.symbol_surrogate_ids) == 3
        assert plan.symbol_id == plan.symbol_ids[0]
        assert plan.symbol_surrogate_id == plan.symbol_surrogate_ids[0]
        ids = plan.symbol_ids + plan.symbol_surrogate_ids + [plan.instance_id]
        assert len(set(ids)) == 7 and min(ids) > host.watermark          # distinct, above the doc
        assert set(ids) <= set(L._plan_host_ids(plan))

    def test_host_table_rows_are_all_backed_by_symbol_pairs(self, host):
        prod = _panel3(host.watermark + 1)
        plan = L.plan_load(prod, host, place=False)
        fam = L.author_host_family(prod, plan, host)
        assert _table(fam.obj) == ([" "] + TYPES3, 1)                     # one blank, m_idx on primary
        res = L.load_family_into_project(BASE, None, product=prod, place=False,
                                         symbol_solid=True, validate=False)
        gate = res.proofs["roundtrip_gate"]
        assert gate["failed"] == 0 and gate["roundtrip_ok"] == gate["records"]
        classes = [e["class"] for e in res.elements]
        assert classes.count("FamilySymbol") == 3 and classes.count("FamSymSurrogate") == 3
        assert classes.count("Family") == 1 and classes.count("FamilySurrogate") == 1
        assert res.proofs["plan"]["type_names"] == TYPES3
        assert res.proofs["plan"]["host_ids"]["symbols"] == plan_symbols(res)

    def test_symbols_are_real_named_and_carry_their_own_row(self, host):
        prod = _panel3(host.watermark + 1)
        plan = L.plan_load(prod, host, place=False)
        pid = plan.twin_of[prod.doc.params["MainsRating"].elem_id]
        got = []
        for tname, sym, ssur in L._symbol_pairs(plan):
            sub = replace(plan, type_name=tname, symbol_id=sym, symbol_surrogate_id=ssur)
            el, _g = L.author_family_symbol(prod, sub, host, L._type_rows(prod, tname), solid=True)
            ss = L.author_famsym_surrogate(sub, host.category)
            rows = el.obj["m_pParams"]["value"]["m_params"]
            mains = [r["m_value"] for r in rows if r.get("m_paramId") == pid][0]
            got.append((el.obj["m_symbolInfo"]["value"]["m_name"], ss.obj["m_name"],
                        ss.obj["m_elemId"] == sym, el.obj["m_partitionSurrogateId"] == ssur, mains))
        assert got == [(n, n, True, True, a) for n, a in zip(TYPES3, [225.0, 400.0, 600.0])]

    def test_born_shaped_multi_type_still_no_blank_pair(self, host):
        prod = _panel3(host.watermark + 1)
        _make_born_shaped(prod.doc)
        assert [n for n, _v in prod.doc.types] == [" "] + TYPES3
        plan = L.plan_load(prod, host, place=False)
        assert plan.type_names == TYPES3 and plan.type_name == TYPES3[0]
        assert _table(L.author_host_family(prod, plan, host).obj) == ([" "] + TYPES3, 1)

    def test_single_type_plan_allocates_exactly_what_it_always_did(self, host):
        """A one-type load's ids are unchanged by the N-pair extension."""
        plan = L.plan_load(_panel(host.watermark + 1), host, place=True)
        assert plan.type_names == ["400A MCB 42ckt"]
        assert plan.symbol_ids == [plan.symbol_id] == [plan.surrogate_id + 1]
        assert plan.symbol_surrogate_ids == [plan.symbol_surrogate_id] == [plan.surrogate_id + 2]
        assert plan.instance_id == plan.surrogate_id + 3


def plan_symbols(res):
    return [e["elem_id"] for e in res.elements if e["class"] == "FamilySymbol"]


@needs_base
class TestMultiTypeFamload:
    def _plan(self, fl_host, doc):
        plan, _nxt = FL._plan_family(FL.FamilyLoad(key="panel3", doc=doc), doc,
                                     fl_host, fl_host.watermark + 1)
        return plan

    def test_plans_n_real_pairs_zero_blank(self, fl_host):
        for born in (False, True):
            doc = _panel3(fl_host.watermark + 1).doc
            if born:
                _make_born_shaped(doc)
            plan = self._plan(fl_host, doc)
            assert plan.type_names == TYPES3
            assert len(plan.symbol_ids) == len(plan.symbol_surrogate_ids) == 3
            names, snames, syms, ssurs = _sym_names(FL.author_host_elements(doc, plan))
            assert names == snames == TYPES3 and all(n.strip() for n in names + snames)
            assert [s.obj["m_elemId"] for s in ssurs] == plan.symbol_ids

    def test_dry_run_load_is_lawful_end_to_end(self, fl_host):
        doc = _panel3(fl_host.watermark + 1).doc
        res = FL.load_family_documents(BASE, [FL.FamilyLoad(key="panel3", doc=doc)],
                                       None, validate=False)
        gate = res.proofs["roundtrip_gate"]
        assert gate["failed"] == 0 and gate["roundtrip_ok"] == gate["records"]
        assert [p.type_names for p in res.plans] == [TYPES3]
        classes = [e["class"] for e in res.proofs["host_elements"]["by_family"]["panel3"]]
        assert classes.count("FamilySymbol") == 3 and classes.count("FamSymSurrogate") == 3
