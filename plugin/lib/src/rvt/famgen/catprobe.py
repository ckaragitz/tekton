"""catprobe -- famgen-CHAIN residue overrides for the catchain probe round
(catchain stream, post-verdict-#41).

WHY.  Batch 47 (layout-law morphs) ended with M2 PASS / everything else
FAIL: pure record ORDER is exonerated in both directions and none of the
byte-morphable single fields (order-cell dedup M3, sparse counters M4,
partType M5, deletion prefix M6) is the law alone.  The surviving suspects
from ``experiments/layout/layout_diff.json`` are the ENTANGLED residues a
byte morph cannot flip coherently -- the family CATEGORY itself (and
everything category-coupled), the 1-row-vs-5-row FamilyTypeTable shape,
the locked/param BIP group, the missing materials order-cell group --
possibly as a CONJUNCTION (the 12 perfect separators co-vary).  Testing
them requires REBUILDING the product through the full famgen chain so that
every coupled surface (famdoc self-Family, host Family object copy, host
FamilySymbol / surrogates / FamilyInstance headers, ADocument registration
rows, symbol geometry GStyle) is authored coherently by the chain's own
constructors.

WHAT THIS MODULE IS.  The minimal OPT-IN override layer that makes those
rebuilds possible WITHOUT editing any shared famgen file:

* :func:`category_override` -- a context manager that flips the family
  category for everything built inside it: ``skeleton.new_family_document``
  (the famdoc self-Family's ``m_categoryId`` + the category-coupled
  ``m_partType``) and ``loader.survey_host`` (the host-side category every
  loader surface follows: FamilySymbol header, both surrogates,
  FamilyInstance, the ADocument CategoryTable row, the category-projection
  GStyle the symbol geometry binds).  ``also=[(module, attr)]`` patches
  additional module-level category constants (the demo placement's
  ``tools/ifc_intent.OST_ELECTRICAL_EQUIPMENT`` instance-scrub constant).
  Everything is restored on exit; nothing outside the ``with`` changes.

* :func:`apply_residues` -- the doc-level residue recipes, applied to a
  finalized :class:`rvt.famgen.skeleton.FamilyDoc` BEFORE the load.  Each
  recipe reproduces a corpus-mined donor shape (mined 2026-08-05 from the
  matched-pair corpus, see the constants below):

  - ``types5``          the donor's FamilyTypeTable shape: a leading BLANK
                        ``' '`` pair duplicating the current values + the
                        real types (>= 4), ``m_idx = 1`` [V SUB_ALL/B7:
                        5 pairs, idx 1, pair0 name ' ' with rows ==
                        m_familyParams rows].
  - ``bip``             the locked/param BIP group: ``-1001205`` (the cost
                        BIP) in ``m_lockedParameterIdsForDirectManipulation``
                        and in the identityData palette of the order cell
                        [V SUB_ALL locked == [-1001205, dims...]; B7 locked
                        == [-1001205, one dim]; -1001205 is NOT a value row].
  - ``materials``       the materials machinery: the ``-1005500`` material
                        BIP as an INSTANCE value row on every type + the
                        current-values set (``m_elemId`` = the material,
                        ours -1 = unassigned), a ``MaterialFSDO`` in
                        ``m_fsdos`` and a ``materials-1.0.0`` group FIRST in
                        the order cell [V SUB_ALL row {-1005500, elemId
                        1177727, instance true}; fsdo {category, material,
                        famParam -1005500}; cell groups open with materials].
  - ``dedup_cell``      the M3 fix (``layout_law.normalize_order_cell``):
                        one group per key, dims/materials < identityData <
                        electrical [V no PASS file carries a dup key].
  - ``sparse_counters`` the M4 one-liners: ``m_nextAbsorbedIndex`` 3165,
                        ``m_predefinedLimitIdx`` 1963 (the donor's sparse
                        edit-history values) [V SUB_ALL].
  - ``deletion_prefix`` the M6 convention completed: the measured
                        NON-ELEMENT parents prepended to the self-Family
                        header ``m_parents.m_deletion`` -- the category id,
                        the material BIP (when authored), the cost BIP
                        (when authored) [V SUB_ALL deletion opens
                        [-2001330, -1005500, -1001205, <material elem>]].
  - ``ref_type_ids``    ``m_refTypeIds = [4]`` [V SUB_ALL and B7 both
                        carry exactly [4]; B0 carries []].

Nothing in the default pipeline imports this module; the catchain probes
(tools/catchain.py) are its only caller.  PROOF-ONLY dev machinery.
"""
from __future__ import annotations

import contextlib
from typing import Any, Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# corpus-mined donor constants (SUB_ALL / B7, mined 2026-08-05; the mining
# script + full shapes are recorded in docs/inbox/catchain.md)
# ---------------------------------------------------------------------------

#: the locked BIP every PASS famdoc carries in m_locked... + the identity
#: palette (skeleton.BIP_TYPE_COST; cost name inferred, id VERIFIED)
BIP_COST_LOCKED = -1001205

#: the material BIP of the donor's materials group / value row / MaterialFSDO
#: (structural-material family param id; VERIFIED on SUB_ALL/B7)
BIP_MATERIAL = -1005500

#: the donor's sparse edit-history counters [V SUB_ALL self-Family]
DONOR_NEXT_ABSORBED = 3165
DONOR_PREDEFINED_LIMIT = 1963

#: the donor's m_refTypeIds [V SUB_ALL == B7 == [4]]
DONOR_REF_TYPE_IDS = (4,)

#: the donor's identityData palette membership for the cost BIP: it sits in
#: the identityData group of the order cell WITHOUT a value row
#: [V SUB_ALL identity group: ..., -1002500, -1001205, -1005554, ...]
_IDENTITY_GROUP_SUFFIX = "identityData-1.0.0"


def _sk():
    from . import skeleton as SK
    return SK


# ===========================================================================
# the category override (the BUILD-call-chain parameter, as a context)
# ===========================================================================

@contextlib.contextmanager
def category_override(category_id: int, *, part_type: int = -1,
                      also: Sequence[Tuple[Any, str]] = ()):
    """Author everything inside the ``with`` under ``category_id``.

    Patches (restored on exit):

    * ``skeleton.new_family_document`` -- whatever category/part_type the
      product constructor passes, the document is BORN with
      ``category_id`` + ``part_type`` (partType is category-coupled: the
      corpus GM/structural famdocs carry -1; 14 is the electrical
      panelboard value only).
    * ``loader.survey_host`` -- the host survey resolves ``category_id``:
      its projection GStyle, a specimen instance of that category, and the
      ``HostContext.category`` every host-side author_* consumes
      (FamilySymbol header, FamilySurrogate, FamSymSurrogate,
      FamilyInstance, ADocument CategoryTable registration).
    * every ``(module, attr)`` in ``also`` -- module-level category
      constants looked up at call time (e.g. the demo placement's
      ``ifc_intent.OST_ELECTRICAL_EQUIPMENT`` instance-scrub constant).

    The host Family mirrors the famdoc self-Family's ``m_categoryId`` /
    ``m_partType`` automatically (``author_host_family`` copies the
    self-Family object), so famdoc + host stay coherent by construction.
    """
    SK = _sk()
    from . import loader as L

    orig_nfd = SK.new_family_document
    orig_sh = L.survey_host

    def nfd(category, name, **kw):                    # noqa: ANN001
        kw["part_type"] = int(part_type)
        return orig_nfd(int(category_id), name, **kw)

    def sh(host_rvt=L.DEFAULT_HOST, *, category=None):  # noqa: ANN001
        return orig_sh(host_rvt, category=int(category_id))

    saved: List[Tuple[Any, str, Any]] = []

    def patch(obj: Any, attr: str, val: Any) -> None:
        saved.append((obj, attr, getattr(obj, attr)))
        setattr(obj, attr, val)

    patch(SK, "new_family_document", nfd)
    patch(L, "survey_host", sh)
    for obj, attr in also:
        patch(obj, attr, int(category_id))
    try:
        yield {"category_id": int(category_id), "part_type": int(part_type),
               "patched": [f"{getattr(o, '__name__', o)}.{a}" for o, a, _v in saved]}
    finally:
        for obj, attr, old in reversed(saved):
            setattr(obj, attr, old)


# ===========================================================================
# doc-level residue recipes
# ===========================================================================

def _order_cell_groups(fam) -> List[Dict[str, Any]]:
    """The self-Family FamilyParamsOrderCell's m_sortedParams list (live)."""
    cells = (((fam.obj.get("m_cellList") or {}).get("value") or {})
             .get("m_cells") or [])
    for c in cells:
        cv = (c.get("value") or {}) if isinstance(c, dict) else {}
        sp = cv.get("m_sortedParams")
        if isinstance(sp, list):
            return sp
    raise ValueError("catprobe: self-Family carries no FamilyParamsOrderCell")


def _group_key(g: Dict[str, Any]) -> str:
    return str((g.get("m_groupTypeId") or {}).get("m_typeId"))


def default_type_variants(doc) -> List[Tuple[str, Dict[int, Any]]]:
    """Three rating variants of the product's current type (distinct names
    + distinct bus/mains ratings, circuit counts) -- the values that make a
    5-pair table with the leading blank row.  Derived from the document's
    own parameters; every value stays in the product's own vocabulary."""
    p = {name: pe.elem_id for name, pe in doc.params.items()}
    need = ("BusRating", "MainsRating", "NumberOfCircuits")
    missing = [n for n in need if n not in p]
    if missing:
        raise ValueError(f"catprobe: product lacks the rating parameters "
                         f"{missing}; pass type_variants explicitly")
    out: List[Tuple[str, Dict[int, Any]]] = []
    for name, bus, ckt in (("100A MLO 18ckt", 100.0, 18),
                           ("400A MLO 42ckt", 400.0, 42),
                           ("600A MLO 42ckt", 600.0, 42)):
        out.append((name, {p["BusRating"]: float(bus),
                           p["MainsRating"]: float(bus),
                           p["NumberOfCircuits"]: int(ckt)}))
    return out


def apply_types5(doc, type_variants: Optional[Sequence[Tuple[str, Dict[Any, Any]]]] = None
                 ) -> Dict[str, Any]:
    """Restructure ``doc.types`` to the donor table shape (PRE-finalize
    mutation; the caller re-finalizes): a leading BLANK ``' '`` pair whose
    values duplicate the current type's, then the real types (the product's
    own + 3 rating variants), ``current_type = 1``."""
    if not doc.types:
        raise ValueError("catprobe: document has no types to restructure")
    if any(n == " " for n, _v in doc.types):
        raise ValueError("catprobe: types already carry a blank pair")
    base_name, base_vals = doc.types[doc.current_type]
    variants = list(type_variants) if type_variants is not None \
        else default_type_variants(doc)
    new_types: List[Tuple[str, Dict[Any, Any]]] = [(" ", dict(base_vals)),
                                                   (base_name, base_vals)]
    for vname, overrides in variants:
        row = dict(base_vals)
        row.update(overrides)
        new_types.append((str(vname), row))
    names = [n for n, _v in new_types]
    if len(set(names)) != len(names):
        raise ValueError(f"catprobe: type names not distinct: {names}")
    doc.types = new_types
    doc.current_type = 1
    return {"n_pairs": len(new_types), "names": names, "current_type": 1,
            "law": "donor table shape: blank ' ' current-values pair first, "
                   "m_idx 1 [V SUB_ALL/B7]"}


def apply_material_values(doc, *, material_elem_id: int = -1) -> Dict[str, Any]:
    """Add the donor's material value row (PRE-finalize mutation) to every
    type: ``{m_paramId -1005500, m_elemId <material>, m_instance true}``.
    ``material_elem_id`` -1 = unassigned (our documents author no Material
    element; the donor's row points at a material OUTSIDE the unit and the
    corpus accepts it -- the SEPARATOR is the row + group presence)."""
    row = {"m_elemId": int(material_elem_id), "m_instance": True}
    for _n, vals in doc.types:
        vals[BIP_MATERIAL] = dict(row)
    return {"param_id": BIP_MATERIAL, "material_elem_id": int(material_elem_id),
            "types_touched": len(doc.types)}


def apply_bip_lock(doc) -> Dict[str, Any]:
    """POST-finalize: the locked/param BIP group -- ``-1001205`` into
    ``m_lockedParameterIdsForDirectManipulation`` (sorted; the BIP sorts
    first exactly as the donor's ``[-1001205, <dims>]``) and into the
    identityData palette group of the order cell (no value row -- the donor
    carries none)."""
    fam = doc.self_family
    locked = list(fam.obj.get("m_lockedParameterIdsForDirectManipulation") or [])
    if BIP_COST_LOCKED not in locked:
        locked.append(BIP_COST_LOCKED)
    fam.obj["m_lockedParameterIdsForDirectManipulation"] = sorted(locked)
    sp = _order_cell_groups(fam)
    target = None
    for g in sp:
        if _group_key(g).endswith(_IDENTITY_GROUP_SUFFIX):
            target = g                      # last identityData group wins
    if target is None:
        SK = _sk()
        target = {"m_groupTypeId": {"m_typeId": SK.PGROUP_IDENTITY},
                  "m_paramIds": []}
        sp.append(target)
    ids = list(target.get("m_paramIds") or [])
    if BIP_COST_LOCKED not in ids:
        ids.append(BIP_COST_LOCKED)
    target["m_paramIds"] = ids
    return {"locked": fam.obj["m_lockedParameterIdsForDirectManipulation"],
            "identity_palette_gained": BIP_COST_LOCKED}


def apply_materials_group(doc) -> Dict[str, Any]:
    """POST-finalize: the materials machinery's non-value surfaces -- the
    ``materials-1.0.0`` group FIRST in the order cell (holding -1005500,
    moved out of the identity palette finalize put it in) and the
    ``MaterialFSDO`` in ``m_fsdos`` (category = the family's own category,
    famParamId -1005500, materialId -1 unassigned).  The value rows must
    already be in the types (apply_material_values + re-finalize)."""
    SK = _sk()
    fam = doc.self_family
    fp_rows = (((fam.obj.get("m_familyParams") or {}).get("value") or {})
               .get("m_params") or [])
    if not any(r.get("m_paramId") == BIP_MATERIAL for r in fp_rows):
        raise ValueError("catprobe: materials group wants the -1005500 value "
                         "row first (apply_material_values before finalize)")
    sp = _order_cell_groups(fam)
    for g in sp:
        ids = g.get("m_paramIds") or []
        if BIP_MATERIAL in ids:
            g["m_paramIds"] = [i for i in ids if i != BIP_MATERIAL]
    sp[:] = [g for g in sp if g.get("m_paramIds")]
    sp.insert(0, {"m_groupTypeId": {"m_typeId": SK.PGROUP_MATERIALS},
                  "m_paramIds": [BIP_MATERIAL]})
    mat_row = next(r for r in fp_rows if r.get("m_paramId") == BIP_MATERIAL)
    fam.obj["m_fsdos"] = [{
        "ptr_class": "MaterialFSDO", "pid": -1,
        "value": {"m_categoryId": int(fam.obj.get("m_categoryId")),
                  "m_materialId": int(mat_row.get("m_elemId", -1)),
                  "m_famParamId": BIP_MATERIAL},
    }]
    return {"cell_groups": [_group_key(g).rsplit(":", 1)[-1].split("-")[0]
                            for g in sp],
            "fsdos": fam.obj["m_fsdos"]}


def apply_sparse_counters(doc, *, next_absorbed: int = DONOR_NEXT_ABSORBED,
                          limit_idx: int = DONOR_PREDEFINED_LIMIT) -> Dict[str, Any]:
    """POST-finalize: the M4 one-liners (the donor's sparse edit-history
    counters; the element INDEX pairs stay dense exactly as M4 left them)."""
    fam = doc.self_family
    was = {"m_nextAbsorbedIndex": fam.obj.get("m_nextAbsorbedIndex"),
           "m_predefinedLimitIdx": fam.obj.get("m_predefinedLimitIdx")}
    fam.obj["m_nextAbsorbedIndex"] = int(next_absorbed)
    fam.obj["m_predefinedLimitIdx"] = int(limit_idx)
    return {"was": was, "now": {"m_nextAbsorbedIndex": int(next_absorbed),
                                "m_predefinedLimitIdx": int(limit_idx)}}


def apply_deletion_prefix(doc, prefix: Sequence[int]) -> Dict[str, Any]:
    """POST-finalize: the M6 convention completed -- the NON-ELEMENT parents
    prepended (in order) to the self-Family header ``m_parents.m_deletion``
    [V SUB_ALL opens category, material BIP, cost BIP, material elem]."""
    fam = doc.self_family
    par = ((fam.header.get("m_parents") or {}).get("value") or {})
    dele = par.get("m_deletion")
    if not isinstance(dele, list):
        raise ValueError("catprobe: self-Family header has no m_deletion list")
    was = len(dele)
    add = [int(x) for x in prefix if int(x) not in dele]
    dele[:0] = add
    return {"prefix": add, "len": {"was": was, "now": len(dele)}}


def apply_ref_type_ids(doc, ids: Sequence[int] = DONOR_REF_TYPE_IDS) -> Dict[str, Any]:
    """POST-finalize: ``m_refTypeIds`` = the donor's [4]."""
    fam = doc.self_family
    was = list(fam.obj.get("m_refTypeIds") or [])
    fam.obj["m_refTypeIds"] = [int(x) for x in ids]
    return {"was": was, "now": fam.obj["m_refTypeIds"]}


def apply_residues(doc, *, types5: bool = False, bip: bool = False,
                   materials: bool = False, dedup_cell: bool = False,
                   sparse_counters: bool = False,
                   deletion_prefix: bool = False,
                   ref_type_ids: bool = False,
                   type_variants: Optional[Sequence[Tuple[str, Dict[Any, Any]]]] = None,
                   material_elem_id: int = -1) -> Dict[str, Any]:
    """Apply the selected residue recipes to a FINALIZED FamilyDoc, in the
    coherent order: PRE-finalize table/value mutations first, ONE
    re-finalize (the chain's own derivation of table / current values /
    order cell / locked / index), then the POST-finalize field recipes.

    ``deletion_prefix`` derives its prefix from what is actually authored:
    the family's category id + the material BIP (iff ``materials``) + the
    cost BIP (iff ``bip``) -- the header names exactly the non-element
    parents the object carries, the donor's own coherence rule.
    """
    if not getattr(doc, "finalized", False):
        raise ValueError("catprobe.apply_residues wants a FINALIZED doc "
                         "(the product constructor finalizes; re-finalize "
                         "is this function's job)")
    report: Dict[str, Any] = {"applied": []}
    pre = False
    if types5:
        report["types5"] = apply_types5(doc, type_variants)
        report["applied"].append("types5")
        pre = True
    if materials:
        report["material_values"] = apply_material_values(
            doc, material_elem_id=material_elem_id)
        report["applied"].append("materials")
        pre = True
    if pre:
        doc.finalize()                      # ONE coherent re-derivation
        report["refinalized"] = True
    if bip:
        report["bip"] = apply_bip_lock(doc)
        report["applied"].append("bip")
    if materials:
        report["materials_group"] = apply_materials_group(doc)
    if dedup_cell:
        from . import layout_law as LL
        report["dedup_cell"] = LL.normalize_order_cell(doc)
        report["applied"].append("dedup_cell")
    if sparse_counters:
        report["sparse_counters"] = apply_sparse_counters(doc)
        report["applied"].append("sparse_counters")
    if deletion_prefix:
        prefix = [int(doc.self_family.obj.get("m_categoryId"))]
        if materials:
            prefix.append(BIP_MATERIAL)
        if bip:
            prefix.append(BIP_COST_LOCKED)
        report["deletion_prefix"] = apply_deletion_prefix(doc, prefix)
        report["applied"].append("deletion_prefix")
    if ref_type_ids:
        report["ref_type_ids"] = apply_ref_type_ids(doc)
        report["applied"].append("ref_type_ids")
    return report
