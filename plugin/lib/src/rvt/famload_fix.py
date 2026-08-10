"""rvt.famload_fix -- THE PRODUCT-PATH FIX layer (instbug-fix stream).

THE BUG (charter: docs/inbox/instbug-fix.md).  Files that load MULTIPLE
family documents or PLACE INSTANCES of our loaded families onto the genesis
lineage trip Autodesk's open-time consistency audit (Revit-DocumentCorruption,
extractor exit -1073742517), while the same operations on the sample bases
pass.  The product path is ``rvt.famgen.loader`` (stage L, chained) +
``tools/ifc_intent.stage_equipment`` (stage E, ConstructedSpecimens template
+ ``rvt.mutate.add_family_instance`` + ``rvt.commit``); the certified
``rvt.famload`` path does not carry these defects.

THE DEFECTS THIS LAYER FIXES -- each a corpus-law violation measured this
session (six-sample mine; the numbers are the corpus support):

D1  ``FamilyInstance.m_pConnectorManager`` authored with ptr class
    ``ConnectorManager``.  Corpus law: 13,636/13,636 instances carry
    ``{null, FamilyInstanceConnectorManager}`` -- the SUBCLASS, never the
    base class (``rvt.objlint`` FamilyInstance PTR_CLASS_SET).  Violated by
    EVERY placed instance of our loaded families ever emitted
    (``rvt.famgen.loader.author_family_instance`` and
    ``tools/ifc_intent._connector_manager_for``); present in every
    audit-FAILED instance file (DEMO_250v_room x6, electrical_room_2500a
    x8) and in NO viewer-PASSED file.  The schema derives
    FamilyInstanceConnectorManager from ConnectorManager with no extra
    fields, so the fix is the class identity alone.

D2  ``ContentTable.m_ContentRecSet`` NOT sorted by GUID after the SECOND
    chained load.  Corpus law: the six samples' ContentTable records are
    ascending by ``ContentKey.m_guidKey`` (bytes_le), matching the
    ContentDocuments stream order; ``rvt.famload`` sorts (L1a / L_v2
    certified); ``rvt.famgen.loader.register_in_host_adocument`` appends.
    Measured: every N>=2 chain (stage_L2.., stage_W, the demo) is unsorted;
    every viewer-PASSED file is sorted.

D3  Host ``Family.m_oFamDimConstrMgr`` = null (corpus: present 831/831) and
    ``FamilySymbol.m_pMoveRestrictions`` = null (corpus: present 2710/2710).
    The corpus-lawful empty forms are ``rvt.genesis.residue_c``'s
    ``famdim_constr_empty`` / ``move_restrictions_empty``; the substituted
    forms are viewer-PASSED (WF_fix).  NOTE: WF_nofix ALSO passed, so the
    nulls alone are not sufficient to trip the audit -- they are fixed
    because they are the only remaining objlint-CRITICAL deltas from the
    corpus and the fixed form is certified.

D4  ``ConnectorDataCell.m_oRelevantParams.m_params`` EMPTY on our host
    families.  Corpus law: 228/228 rme cells carry the full connector
    property table (11/12/15/18/21 rows; ELECTRICAL EQUIPMENT cells: ONE
    canonical 15-row id order, measured 22/22).  Ours had 0 rows (the box
    family has no connector and hence no cell -- exactly the one famgen
    configuration that ever viewer-PASSED, WF_nofix).

D5  The demo instances carry ``m_createdPhaseId = -1`` and no phase in the
    header deletion set, because ``ConstructedSpecimens`` looks up
    ``ids_of_class("Phase")`` -- the class is ``ProjectPhase`` -- so the
    template never finds the base's phases.  The corpus ENUM allows null,
    but the certified created-instance shape (V20) carries the phase in
    both places; the fix resolves the base's ProjectPhase (highest id = the
    'New Work' phase, matching the sample convention).

WHAT THIS LAYER DOES NOT CLAIM: R_inst_box (ZA_deep + the bare box family +
one placed instance) failed the audit while carrying NONE of D1..D5 on its
instance (manager null, N=1, box family); its instance is lawful on every
mined axis V20 calibrates.  The un-eliminated suspect there is the famgen
loader's baked symbol geometry ([H] grammar) under the audit's deep walk --
only the staged viewer batch can rule on it.  This layer fixes every
corpus-law violation on the demo path and re-emits; the verdicts decide.

USE::

    from rvt import famload_fix as FX
    with FX.fixed_product_path():
        ...  # any famgen.loader / ifc_intent / frontdoor build code
    rep = FX.assert_fixed("out.rvt")     # post-emit fix assertions + accounting

TERRITORY: this module + tests/test_famload_fix.py + experiments/instbug/fix
+ the rvt.validate loaded-content rule.  ``rvt.famgen.loader`` /
``tools/ifc_intent.py`` / ``rvt.frontdoor.standalone`` are NEVER edited --
they are monkey-patched inside the context manager, and the equivalent
source diffs for their owners are in docs/inbox/instbug-fix.md.
"""
from __future__ import annotations

import contextlib
import copy
import sys
import uuid
from typing import Any, Dict, List, Optional, Sequence

from .genesis.residue_c import famdim_constr_empty, move_restrictions_empty

__all__ = [
    "famdim_constr_empty", "move_restrictions_empty",
    "lawful_instance_connector_manager", "electrical_connector_cell",
    "sort_content_recset", "fixed_product_path", "assert_fixed",
    "EE_CELL_PARAM_ORDER",
]

#: the ONE canonical Electrical-Equipment ConnectorDataCell row order
#: [V rme: 22/22 fifteen-row cells share exactly this id sequence]
EE_CELL_PARAM_ORDER = (
    -1140002,   # voltage                      (float, ours)
    -1150159,   # (always 0.0)                 [V 22/22]
    -1140018,   # int 31 (3-pole) / 30 (1-pole) [V 15x31 / 7x30 tracks poles]
    -1133412,   # int 1                         [V 22/22]
    -1140009,   # int 1                         [V 22/22]
    -1140008,   # power factor                  (float, ours; corpus 1.0/0.8/0.95)
    -1140001,   # poles (int)                   (ours)
    -1140131,   # 0                             [V 22/22]
    -1140014,   # load classification ELEMENT   (m_elemId, ours)
    -1140000,   # 0                             [V 22/22]
    -1140003,   # 0                             [V modal]
    -1140007,   # 0                             [V 22/22]
    -1140006,   # 0                             [V 22/22]
    -1140005,   # apparent load                 (float, ours; corpus 0 or value)
    -1140004,   # 0 / derived VA                [V modal 0]
)


def _row(param_id: int, *, value: float = 0.0, iv: int = 0,
         elem_id: int = -1) -> dict:
    """One ``FamilyParams`` row in the corpus cell shape [V 454674]."""
    return {"m_str": "", "m_oExpression": None, "m_value": float(value),
            "m_elemId": int(elem_id), "m_paramId": int(param_id),
            "m_int": int(iv), "m_instance": False, "m_reporting": False}


def electrical_connector_cell(con: Dict[str, Any], *, bindings: List[dict],
                              load_class_host: int) -> dict:
    """The corpus-lawful ``ConnectorDataCell`` of ONE electrical connector:
    the canonical 15-row relevant-params table (EE_CELL_PARAM_ORDER) with our
    connector facts where the corpus rows carry family values and the corpus
    constants everywhere else.  ``con`` = one entry of
    ``rvt.famgen.loader._connector_facts``.
    """
    poles = int(con.get("poles") or 3)
    volt = float(con.get("voltage") or 0.0)
    load = float(con.get("load") or 0.0)
    pf = float(con.get("power_factor") or 1.0)
    values = {
        -1140002: _row(-1140002, value=volt),
        -1140018: _row(-1140018, iv=(31 if poles == 3 else 30)),
        -1133412: _row(-1133412, iv=1),
        -1140009: _row(-1140009, iv=1),
        -1140008: _row(-1140008, value=pf),
        -1140001: _row(-1140001, iv=poles),
        -1140014: _row(-1140014, elem_id=(int(load_class_host)
                                          if load_class_host not in (None, -1)
                                          else -1)),
        -1140005: _row(-1140005, value=load),
    }
    rows = [values.get(pid) or _row(pid) for pid in EE_CELL_PARAM_ORDER]
    return {"ptr_class": "ConnectorDataCell", "pid": -1, "value": {
        "m_propId2FamParamIdBindings": list(bindings),
        "m_oRelevantParams": {"ptr_class": "FamilyParams", "pid": -1, "value": {
            "m_params": rows,
            "m_geomRefHandles": {"m_offsetGeomMap": []}}},
        "m_connectorType": 1,
        "m_domain": 2,
        "m_index": int(con.get("index") or 1),
        "m_profileType": -1,
    }}


def lawful_instance_connector_manager(slots: Sequence[dict]) -> dict:
    """The instance connector manager in the corpus-lawful CLASS:
    ``FamilyInstanceConnectorManager`` (schema: derives from
    ConnectorManager, no extra fields -- same value dict, lawful identity).
    """
    return {"ptr_class": "FamilyInstanceConnectorManager", "pid": -1,
            "value": {"m_setDeletedConnectors": [],
                      "m_connPtrArray": list(slots),
                      "m_modifiers": []}}


def _guid_key(rec: dict) -> bytes:
    return uuid.UUID(str((rec.get("m_ContentKey") or {}).get("m_guidKey"))).bytes_le


def sort_content_recset(latest_value: dict) -> int:
    """Sort ``ContentTable.m_ContentRecSet`` ascending by ContentKey GUID
    (bytes_le) IN PLACE -- the corpus order (six samples) and rvt.famload's
    certified rule.  Returns the record count."""
    ct = ((latest_value.get("m_oContentTable") or {}).get("value") or {})
    recs = ct.get("m_ContentRecSet")
    if isinstance(recs, list) and len(recs) > 1:
        recs.sort(key=_guid_key)
    return len(recs) if isinstance(recs, list) else 0


def recset_sorted(latest_value: dict) -> bool:
    ct = ((latest_value.get("m_oContentTable") or {}).get("value") or {})
    recs = ct.get("m_ContentRecSet") or []
    keys = [_guid_key(r) for r in recs]
    return keys == sorted(keys)


# ---------------------------------------------------------------------------
# the patch set (context manager -- nothing outside it is modified)
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def fixed_product_path(*, fix_connector_manager: bool = True,
                       fix_content_table_sort: bool = True,
                       fix_family_layer_nulls: bool = True,
                       fix_connector_cells: bool = True,
                       fix_specimen_phase: bool = True):
    """Apply the D1..D5 fixes to the LIVE product path for the duration of
    the ``with`` block: ``rvt.famgen.loader`` (author_host_family /
    author_family_symbol / author_family_instance / _connector_data_cells /
    register_in_host_adocument), ``sys.modules["ifc_intent"]`` if this
    process has loaded it (``_connector_manager_for``), and
    ``rvt.frontdoor.standalone.ConstructedSpecimens`` (phase resolution).
    All patches are reverted on exit.
    """
    from .famgen import loader as L
    from .famgen.geometry import assign_pids

    saved: List[tuple] = []

    def patch(obj, name, fn):
        saved.append((obj, name, getattr(obj, name)))
        setattr(obj, name, fn)

    # -- D2: ContentTable GUID sort after registration ----------------------
    if fix_content_table_sort:
        orig_reg = L.register_in_host_adocument

        def reg_sorted(latest_value, plan, **kw):
            rep = orig_reg(latest_value, plan, **kw)
            sort_content_recset(latest_value)
            rep["content_table_sorted"] = True
            return rep
        patch(L, "register_in_host_adocument", reg_sorted)

    # -- D3: the two null owned slots --------------------------------------
    if fix_family_layer_nulls:
        orig_fam = L.author_host_family

        def fam_fixed(product, plan, host):
            el = orig_fam(product, plan, host)
            if el.obj.get("m_oFamDimConstrMgr") is None:
                el.obj["m_oFamDimConstrMgr"] = famdim_constr_empty()
                assign_pids(el.obj)
                el.notes.append("famload_fix D3: m_oFamDimConstrMgr = corpus "
                                "empty form (831/831; WF_fix-certified)")
            return el
        patch(L, "author_host_family", fam_fixed)

        orig_sym = L.author_family_symbol

        def sym_fixed(product, plan, host, type_rows, **kw):
            el, geo = orig_sym(product, plan, host, type_rows, **kw)
            if el.obj.get("m_pMoveRestrictions") is None:
                el.obj["m_pMoveRestrictions"] = move_restrictions_empty()
                assign_pids(el.obj)
                el.notes.append("famload_fix D3: m_pMoveRestrictions = corpus "
                                "empty Matrix (2710/2710; WF_fix-certified)")
            return el, geo
        patch(L, "author_family_symbol", sym_fixed)

    # -- D4: the corpus connector cell --------------------------------------
    if fix_connector_cells:
        def cells_fixed(product, plan):
            facts = L._connector_facts(product)
            cells = []
            for con in facts["connectors"]:
                bindings = [{"first": int(prop),
                             "second": int(plan.twin_of.get(fam, fam))}
                            for prop, fam in con.get("bindings") or []]
                cells.append(electrical_connector_cell(
                    con, bindings=bindings,
                    load_class_host=plan.load_class_host))
            return cells
        patch(L, "_connector_data_cells", cells_fixed)

    # -- D1: the instance connector-manager class ---------------------------
    def _fix_manager_dict(cm: Optional[dict]) -> Optional[dict]:
        if isinstance(cm, dict) and cm.get("ptr_class") == "ConnectorManager":
            cm = copy.deepcopy(cm)
            cm["ptr_class"] = "FamilyInstanceConnectorManager"
        return cm

    if fix_connector_manager:
        orig_inst = L.author_family_instance

        def inst_fixed(product, plan, host, **kw):
            el = orig_inst(product, plan, host, **kw)
            fixed = _fix_manager_dict(el.obj.get("m_pConnectorManager"))
            if fixed is not el.obj.get("m_pConnectorManager"):
                el.obj["m_pConnectorManager"] = fixed
                assign_pids(el.obj)
                el.notes.append("famload_fix D1: connector manager class -> "
                                "FamilyInstanceConnectorManager (13636/13636)")
            return el
        patch(L, "author_family_instance", inst_fixed)

        room = sys.modules.get("ifc_intent")               # patched only if already live, never loaded here
        if room is not None:
            orig_cm = room._connector_manager_for

            def cm_fixed(product, circuit_slots):
                return _fix_manager_dict(orig_cm(product, circuit_slots))
            patch(room, "_connector_manager_for", cm_fixed)

    # -- D5: ConstructedSpecimens phase resolution --------------------------
    if fix_specimen_phase:
        try:
            from .frontdoor import standalone as SA

            class _FixedSpecimens(SA.ConstructedSpecimens):
                def __init__(self, source_path=None, base_path=None):
                    super().__init__(source_path or SA.CONSTRUCTED,
                                     base_path=base_path)
                    if int(getattr(self, "phase_id", -1) or -1) > 0:
                        return
                    from .mutate import Document
                    bp = base_path or SA.bundled_base_path()
                    bd = Document.from_file(bp)
                    phases = sorted(bd.ids_of_class("ProjectPhase"))
                    if not phases:
                        return
                    self.phase_id = int(phases[-1])     # 'New Work' convention
                    schema = bd.dec.schema
                    h, o = SA.family_instance_template(
                        schema, elem_id=self.INSTANCE_TID,
                        level_id=self.level_id, phase_id=self.phase_id)
                    self._add_template(schema, self.INSTANCE_TID,
                                       "ElementHeader", h, "FamilyInstance", o)

            patch(SA, "ConstructedSpecimens", _FixedSpecimens)
        except Exception:                                  # pragma: no cover
            pass

    try:
        yield
    finally:
        for obj, name, val in reversed(saved):
            setattr(obj, name, val)


# ---------------------------------------------------------------------------
# post-emit assertions + registry accounting (the machine proof of the fix)
# ---------------------------------------------------------------------------

def assert_fixed(path: str, *, expect_families: Optional[int] = None,
                 expect_instances: Optional[int] = None) -> Dict[str, Any]:
    """Read an emitted file back and PROVE the D1..D5 states, plus the
    four-registry census.  Raises nothing; the report's ``ok`` summarises."""
    from .mutate import Document
    from .container import open_rvt
    from . import adocument as A
    from .famload import four_registry_census

    rep: Dict[str, Any] = {"path": path}
    doc = Document.from_file(path)
    with open_rvt(path) as f:
        lat = A.decode_latest(f.inflate("Global/Latest"))
    lv = lat.value

    # D2
    rep["content_table_sorted"] = recset_sorted(lv)

    # host family layer (host = elements in the ElemTable)
    fams = [e for e in doc.ids_of_class("Family")]
    syms = [e for e in doc.ids_of_class("FamilySymbol")]
    insts = [e for e in doc.ids_of_class("FamilyInstance")]
    rep["n_host_families"] = len(fams)
    rep["n_host_symbols"] = len(syms)
    rep["n_instances"] = len(insts)

    # D3
    rep["families_null_famdim"] = [e for e in fams
                                   if (doc.value(e) or {}).get("m_oFamDimConstrMgr") is None]
    rep["symbols_null_moverestr"] = [e for e in syms
                                     if (doc.value(e) or {}).get("m_pMoveRestrictions") is None]

    # D4
    empty_cells = []
    for e in fams:
        v = doc.value(e) or {}
        cl = ((v.get("m_cellList") or {}).get("value") or {})
        for c in cl.get("m_cells") or []:
            if isinstance(c, dict) and c.get("ptr_class") == "ConnectorDataCell":
                rows = (((c.get("value") or {}).get("m_oRelevantParams") or {})
                        .get("value") or {}).get("m_params") or []
                if len(rows) < 11:
                    empty_cells.append((e, len(rows)))
    rep["connector_cells_below_corpus_floor"] = empty_cells

    # D1 + D5
    bad_mgr = []
    no_phase = []
    for e in insts:
        v = doc.value(e) or {}
        cm = v.get("m_pConnectorManager")
        if isinstance(cm, dict) and cm.get("ptr_class") != "FamilyInstanceConnectorManager":
            bad_mgr.append((e, cm.get("ptr_class")))
        ph = v.get("m_createdPhaseId", -1)
        hdr = doc.value(e, seq=101) or {}
        dele = (((hdr.get("m_parents") or {}).get("value") or {}).get("m_deletion")) or []
        if not (isinstance(ph, int) and ph > 0 and ph in dele):
            no_phase.append((e, ph))
    rep["instances_unlawful_manager"] = bad_mgr
    rep["instances_without_phase"] = no_phase

    rep["census"] = {k: v for k, v in four_registry_census(path).items()
                     if k in ("save_units", "contentdocs_entries",
                              "contenttable_records", "familymgr_entries",
                              "coherent", "coherent_counts", "coherent_guids")}
    ok = (rep["content_table_sorted"]
          and not rep["families_null_famdim"]
          and not rep["symbols_null_moverestr"]
          and not rep["connector_cells_below_corpus_floor"]
          and not rep["instances_unlawful_manager"]
          and not rep["instances_without_phase"]
          and rep["census"].get("coherent") is True)
    if expect_families is not None:
        ok = ok and (rep["n_host_families"] == expect_families)
    if expect_instances is not None:
        ok = ok and (rep["n_instances"] == expect_instances)
    rep["ok"] = bool(ok)
    return rep
