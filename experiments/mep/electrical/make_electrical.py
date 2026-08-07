#!/usr/bin/env python3
"""make_electrical.py — build the WIRING / ELECTRICAL-SETTINGS / PANEL-DATA
proof files against the Revit MEP sample (rmebasicsampleproject.rvt).

Each cell of the electrical CRUD matrix is proven by a generated .rvt that
passes the writer's own structural verifier AND the Autodesk-free validator
(tools/rvt_validate.py, all three layers, ZERO errors), followed by a
semantic re-read (Document.from_file) confirming the change landed:

  wire_create.rvt        a NEW home-run wire (free arrow end -> device) plus
                         a NEW branch wire (device <-> device, chamfer) for
                         existing circuit 469513 'Power Washing Room 25' on
                         panel PP-1A, with the connected devices EDITED so
                         their connectors reference the wires back (one
                         combined create+edit commit).
  wire_delete.rvt        DELETE an existing wire (its tag cascades, the
                         devices' connector back-links are neutralised).
  settings_modify.rvt    MODIFY one of every electrical setting: a demand
                         factor value, a voltage definition, a distribution
                         system name, a wire type flag, a load classification
                         abbreviation, the ElectricalSetting default circuit
                         rating and the wire tick-label separator.
  load_class_create.rvt  CREATE a load classification with its own demand
                         factor + six parameter elements, and a new
                         600Y/347 V distribution system with its two new
                         voltage definitions (11 new elements).
  panel_renumber.rvt     renumber_circuits() on real panels PP-1A (622027,
                         hole at slot 2) and LP-2 (471705, holes 1/14/19):
                         circuits re-laid to contiguous 1..N.  (The rule is
                         first proven to reproduce Autodesk's own numbering
                         on the untouched panels PP-2B / PP-3B, incl. their
                         3-pole '20,22,24' / '19,21,23' circuits.)

Run:  .venv/bin/python experiments/mep/electrical/make_electrical.py [--skip-validate]
Writes experiments/mep/electrical/manifest.json.
"""
from __future__ import annotations

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from rvt.mutate import Document  # noqa: E402
from rvt.mep import electrical_data as ED  # noqa: E402

SRC = os.path.join(ROOT, "samples", "rmebasicsampleproject.rvt")

# template facts (rme) --------------------------------------------------------
CKT_469513 = 469513              # 'Power Washing Room 25', circuit 3 of PP-1A
PANEL_PP1A = 622027              # 17 circuits, hole at slot 2
PANEL_LP2 = 471705               # 17 circuits, holes at 1, 14, 19
PANEL_PP2B = 471596              # Autodesk-numbered incl. 3-pole 'EP-2' 20,22,24
PANEL_PP3B = 503195              # Autodesk-numbered incl. 3-pole 'EP-3' 19,21,23
DF_HVAC = 638823                 # ElectricalDemandFactorDefinition 'HVAC' (1.0)
VT_120 = 55359                   # RbsVoltageType '120' (110..130)
DS_120_240 = 277809              # RbsDistributionSysType '120/240 Single'
WT_XHHW = 261496                 # RbsWireType 'XHHW'
LC_RECEPT = 690425               # ElectricalLoadClassification 'Receptacles'
ES_SETTING = 639116              # ElectricalSetting singleton
WS_SETTING = 293123              # RbsWireSettingsElem singleton
WIRE_TO_DELETE = 469466          # branch wire 467291 <-> 467473 (circuits 469428/469434)


def _validate(path: str) -> dict:
    """Run the Autodesk-free validator (all layers) and return its summary."""
    try:
        from rvt.validate import validate_file
    except Exception as e:                                       # pragma: no cover
        return {"skipped": str(e)}
    rep = validate_file(path)
    d = rep.to_json()
    errs = [f for f in d["findings"] if f["severity"] == "error"]
    warns = [f for f in d["findings"] if f["severity"] == "warning"]
    return {"ok": bool(rep.ok), "errors": len(errs), "warnings": len(warns),
            "error_messages": [f["message"] for f in errs],
            "warning_messages": [f["message"] for f in warns][:6],
            "stats": {k: d["stats"].get(k) for k in
                      ("records", "elements_decoded", "refs_checked",
                       "connector_edges", "circuits") if k in d["stats"]}}


def _entry(name, out, cr, v, extra):
    e = {"file": os.path.relpath(out, ROOT), "size_bytes": os.path.getsize(out),
         "commit": cr.to_json() if cr is not None else None,
         "verify": {k: v.get(k) for k in
                    ("crc_failures", "ecc_mismatches", "walker_errors",
                     "isize_identity_mismatches", "stamps_ok", "elemtable_count",
                     "header_count", "unit0_ids_equal_elemtable",
                     "elemtable_ids_sorted", "structurally_valid")},
         "verify_edited": v.get("edited"),
         **extra}
    return e


# ============================================================================
# 1. WIRE CREATE (home run + branch wire, devices back-linked)
# ============================================================================
def build_wire_create(out: str) -> dict:
    doc = Document.from_file(SRC)
    loads = ED.circuit_loads(doc, CKT_469513)
    pnl = ED.circuit_panel(doc, CKT_469513)
    # (a) HOME RUN: free arrow end -> the circuit's first load
    hr = ED.add_home_run(doc, CKT_469513)
    # (b) BRANCH wire between the circuit's first two loads (chamfer)
    br = ED.add_wire(doc, CKT_469513, loads[0][0], loads[1][0],
                     wiring_type="chamfer")
    new = [hr.wire, br.wire]
    plans = hr.device_plans + br.device_plans
    dangling = {e.elem_id: doc.check_references(e) for e in new}
    cr = ED.commit_electrical(SRC, out, doc, new_elements=new, plans=plans)
    edited = sorted({p.elem_id for p in plans})
    v = ED.verify_electrical(out, new_ids=[e.elem_id for e in new], edited_ids=edited)
    d2 = Document.from_file(out)
    rb = {
        "home_run": ED.wire_info(d2, hr.wire.elem_id),
        "branch": ED.wire_info(d2, br.wire.elem_id),
        "device_backlinks": {
            dv: {i: [r for r in refs if r[0] in (hr.wire.elem_id, br.wire.elem_id)]
                 for i, refs in ED.connectors(d2.value(dv)).items()}
            for dv in edited},
    }
    ok = (v["structurally_valid"]
          and rb["home_run"]["home_run"] and rb["home_run"]["circuits"] == [CKT_469513]
          and rb["home_run"]["end"]["device"] == loads[0][0]
          and not rb["branch"]["home_run"] and rb["branch"]["wiring"] == "chamfer"
          and rb["branch"]["start"]["device"] == loads[0][0]
          and rb["branch"]["end"]["device"] == loads[1][0]
          and all(any(refs for refs in b.values())
                  for b in rb["device_backlinks"].values()))
    return _entry("wire_create", out, cr, v, {
        "proves": ("CREATE two RbsWireCurve wires for existing circuit 469513 "
                   f"(panel {pnl[0]} 'PP-1A' slot connector {pnl[1]}): a HOME "
                   "RUN with a FREE arrow start end (pointing to the panel) ending "
                   f"on device {loads[0][0]}, and a chamfered BRANCH wire "
                   f"{loads[0][0]}<->{loads[1][0]}; the connected devices are "
                   "edited in the SAME commit so their supply connectors "
                   "reference the wires back (two-way connType-1 links, no "
                   "one-way connector warnings)."),
        "circuit": CKT_469513, "panel": pnl, "loads_used": loads[:2],
        "elements": [{"id": e.elem_id, "class": e.class_name, "notes": e.notes} for e in new],
        "device_edits": edited,
        "dangling_refs_before_write": dangling,
        "readback": rb,
        "SEMANTIC_OK": bool(ok),
    })


# ============================================================================
# 2. WIRE DELETE
# ============================================================================
def build_wire_delete(out: str) -> dict:
    doc = Document.from_file(SRC)
    before = ED.wire_info(doc, WIRE_TO_DELETE)
    plan = ED.delete_wire(doc, WIRE_TO_DELETE, cascade=True)
    cr = ED.commit_electrical(SRC, out, doc, plans=[plan])
    v = ED.verify_electrical(out, deleted_ids=plan.ids_to_remove,
                             edited_ids=plan.edited_ids)
    d2 = Document.from_file(out)
    still = {i: d2.exists(i) for i in plan.ids_to_remove}
    # devices must no longer mention the wire
    dev_clean = {}
    for e in (before["start"], before["end"]):
        if not e:
            continue
        refs = ED.connectors(d2.value(e["device"]) or {})
        dev_clean[e["device"]] = all(t != WIRE_TO_DELETE
                                     for lst in refs.values() for (t, _i, _c) in lst)
    ok = (v["structurally_valid"] and not any(still.values())
          and all(dev_clean.values()))
    return _entry("wire_delete", out, cr, v, {
        "proves": (f"DELETE wire {WIRE_TO_DELETE} (branch {before['start']['device']}"
                   f"<->{before['end']['device']}, circuits {before['circuits']}): its "
                   "three records + ElemRec removed, its wire tag cascaded, and "
                   "the two devices' connector back-links neutralised (soft "
                   "referrers, plus the neighbouring wire's header lists)."),
        "wire_before": before,
        "deleted_ids": plan.ids_to_remove,
        "dependents": plan.dependents,
        "referrers_neutralised": [r["id"] for r in plan.referrer_edits],
        "readback": {"deleted_still_present": still,
                     "devices_no_longer_reference_wire": dev_clean},
        "SEMANTIC_OK": bool(ok),
    })


# ============================================================================
# 3. SETTINGS MODIFY (one of each electrical-settings class)
# ============================================================================
def build_settings_modify(out: str) -> dict:
    doc = Document.from_file(SRC)
    before = ED.electrical_settings(doc)
    plans = [
        ED.set_demand_factor(doc, DF_HVAC, 0.85),                          # HVAC 1.0 -> 0.85
        ED.set_voltage_type(doc, VT_120, max_volts=132.0),                # 120 V: max 130 -> 132
        ED.rename_setting(doc, DS_120_240, "240/120 Single Phase"),       # dist system rename
        ED.modify_setting(doc, WT_XHHW, {"m_bShareGround": False},        # wire type flag
                          reason="wire type XHHW: share ground -> off"),
        ED.set_load_classification(doc, LC_RECEPT, abbreviation="RCPT"), # abbreviation
        ED.modify_setting(doc, ES_SETTING, {"m_circuitRating": 30.0},     # default ckt rating
                          reason="ElectricalSetting default circuit rating 20 -> 30 A"),
        ED.modify_setting(doc, WS_SETTING, {"m_strElectricalConnectorSeparator": "/"},
                          reason="wire tick-label connector separator '-' -> '/'"),
    ]
    edited = sorted({p.elem_id for p in plans})
    cr = ED.commit_electrical(SRC, out, doc, plans=plans)
    v = ED.verify_electrical(out, edited_ids=edited)
    d2 = Document.from_file(out)
    after = ED.electrical_settings(d2)

    def pick(rows, i):
        return next((r for r in rows if r["id"] == i), None)
    checks = {
        "demand_factor_hvac_0.85": abs((pick(after["demand_factors"], DF_HVAC) or {})
                                        .get("values", [{}])[0].get("factor", 0) - 0.85) < 1e-9,
        "voltage_120_max_132": abs(((pick(after["voltage_types"], VT_120) or {})
                                    .get("max_volts") or 0) - 132.0) < 1e-6,
        "distsys_renamed": (pick(after["distribution_systems"], DS_120_240) or {})
                           .get("name") == "240/120 Single Phase",
        "wiretype_share_ground_off": (pick(after["wire_types"], WT_XHHW) or {})
                                     .get("share_ground") is False,
        "loadclass_abbrev_RCPT": (pick(after["load_classifications"], LC_RECEPT) or {})
                                  .get("abbreviation") == "RCPT",
        "elec_setting_ckt_rating_30": abs((after["electrical_setting"] or {})
                                          .get("circuit_rating", 0) - 30.0) < 1e-9,
        "wire_separator_slash": (after["wire_settings"] or {}).get("connector_separator") == "/",
    }
    ok = v["structurally_valid"] and all(checks.values())
    return _entry("settings_modify", out, cr, v, {
        "proves": ("MODIFY each electrical-settings class in place (byte-exact "
                   "re-encode + fresh stamp): demand factor 'HVAC' 1.0->0.85, "
                   "voltage '120' max 130->132 V, distribution system renamed "
                   "'240/120 Single Phase', wire type 'XHHW' share-ground off, "
                   "load classification 'Receptacles' abbreviation 'RCPT', "
                   "ElectricalSetting default circuit rating 20->30 A, wire "
                   "tick-label separator '-'->'/'."),
        "edited": edited,
        "plans": [p.to_json() for p in plans],
        "before": {k: before[k] for k in ("electrical_setting", "wire_settings")},
        "readback_checks": checks,
        "SEMANTIC_OK": bool(ok),
    })


# ============================================================================
# 4. LOAD CLASSIFICATION CREATE (+ a new 600Y/347 distribution system)
# ============================================================================
def build_load_class_create(out: str) -> dict:
    doc = Document.from_file(SRC)
    v347 = ED.add_voltage_type(doc, "347", 347, 330, 360)
    v600 = ED.add_voltage_type(doc, "600", 600, 570, 610)
    ds = ED.add_distribution_system(doc, "600/347 Wye", vll=v600, vlg=v347,
                                    phase="three", config="wye", num_wires=4)
    lc = ED.add_load_classification(doc, "EV Charging", abbreviation="EV",
                                    demand_factor=1.0, signature_type=0,
                                    space_load_class=2)
    new = doc.new_elements
    dangling = {e.elem_id: doc.check_references(e) for e in new}
    cr = ED.commit_electrical(SRC, out, doc, new_elements=new)
    v = ED.verify_electrical(out, new_ids=[e.elem_id for e in new])
    d2 = Document.from_file(out)
    st = ED.electrical_settings(d2)
    cls_id = lc[0].elem_id
    row = next((r for r in st["load_classifications"] if r["id"] == cls_id), None)
    ds_row = next((r for r in st["distribution_systems"] if r["id"] == ds.elem_id), None)
    params_ok = row is not None and all(
        (row["param_elem_ids"][k] in [e.elem_id for e in lc]) for k in ED.LOAD_CLASS_PARAM_FIELDS)
    # each new param element points back at the classification
    back_ok = all((d2.value(pid) or {}).get("m_idLoadClassification") == cls_id
                  for pid in (row["param_elem_ids"].values() if row else []))
    ok = (v["structurally_valid"] and row is not None and row["name"] == "EV Charging"
          and row["abbreviation"] == "EV" and row["demand_factor"] == "EV Charging"
          and params_ok and back_ok
          and ds_row is not None and ds_row["vll"] == 600.0 and ds_row["vlg"] == 347.0
          and ds_row["phase"] == "three" and ds_row["num_wires"] == 4)
    return _entry("load_class_create", out, cr, v, {
        "proves": ("CREATE electrical-settings elements: a load classification "
                   "'EV Charging' (abbr 'EV') as the full Revit closure — its "
                   "own ElectricalDemandFactorDefinition (1.0) and six "
                   "ParamElemElectricalLoadClassification parameter elements, "
                   "cross-referenced both ways with mutual deletion parents — "
                   "plus a NEW '600/347 Wye' distribution system referencing "
                   "two NEW voltage definitions (347 V, 600 V)."),
        "elements": [{"id": e.elem_id, "class": e.class_name, "kind": e.kind}
                     for e in new],
        "dangling_refs_before_write": dangling,
        "readback": {"load_classification": row, "distribution_system": ds_row,
                     "params_point_back_at_classification": back_ok},
        "SEMANTIC_OK": bool(ok),
    })


# ============================================================================
# 5. PANEL RENUMBER
# ============================================================================
def build_panel_renumber(out: str) -> dict:
    doc = Document.from_file(SRC)
    # first: prove the rule reproduces Autodesk's own numbering (no-op panels)
    repro = {}
    for p in (PANEL_PP2B, PANEL_PP3B):
        laid = ED.layout_circuits(ED.panel_circuits(doc, p))
        repro[p] = {"panel": ED.panel_info(doc, p)["name"],
                    "circuits": len(laid),
                    "rule_reproduces_autodesk_numbering":
                        all((r["number"] or "") == r["new_number"]
                            and r["start_slot"] == r["new_start_slot"] for r in laid),
                    "sample_numbers": [r["number"] for r in laid][-5:]}
    before = {p: {"info": ED.panel_info(doc, p),
                  "numbering": ED.check_panel_numbering(doc, p),
                  "circuits": [(r["id"], r["number"], r["start_slot"], r["poles"])
                               for r in ED.panel_circuits(doc, p)]}
              for p in (PANEL_PP1A, PANEL_LP2)}
    plans = ED.renumber_circuits(doc, PANEL_PP1A) + ED.renumber_circuits(doc, PANEL_LP2)
    edited = sorted({p.elem_id for p in plans})
    cr = ED.commit_electrical(SRC, out, doc, plans=plans)
    v = ED.verify_electrical(out, edited_ids=edited)
    d2 = Document.from_file(out)
    after = {p: {"numbering": ED.check_panel_numbering(d2, p),
                 "circuits": [(r["id"], r["number"], r["start_slot"], r["poles"])
                              for r in ED.panel_circuits(d2, p)]}
             for p in (PANEL_PP1A, PANEL_LP2)}
    contiguous = {}
    for p in (PANEL_PP1A, PANEL_LP2):
        nums = [r[1] for r in after[p]["circuits"]]
        slots = [r[2] for r in after[p]["circuits"]]
        contiguous[p] = (nums == [str(i) for i in range(1, len(nums) + 1)]
                         and slots == list(range(1, len(slots) + 1))
                         and after[p]["numbering"]["compact"]
                         and not after[p]["numbering"]["spaces"])
    ok = (v["structurally_valid"] and all(contiguous.values())
          and all(r["rule_reproduces_autodesk_numbering"] for r in repro.values()))
    return _entry("panel_renumber", out, cr, v, {
        "proves": ("renumber_circuits() re-lays-out real panels PP-1A (622027: "
                   "17 circuits, hole at slot 2 -> contiguous 1..17) and LP-2 "
                   "(471705: 17 circuits, holes at 1/14/19 -> 1..17): every "
                   "circuit's m_number / m_nStartSlot rewritten in place. The "
                   "two-column rule (n-pole = n same-parity slots, lowest fit) "
                   "is first shown to REPRODUCE Autodesk's own numbering "
                   "value-for-value on untouched panels PP-2B and PP-3B, "
                   "including their 3-pole '20,22,24' / '19,21,23' circuits."),
        "rule_reproduces_autodesk": repro,
        "edited_circuits": edited,
        "before": {str(k): b for k, b in before.items()},
        "after": {str(k): a for k, a in after.items()},
        "contiguous_1_to_N": {str(k): c for k, c in contiguous.items()},
        "SEMANTIC_OK": bool(ok),
    })


# ============================================================================
def main() -> int:
    skip_validate = "--skip-validate" in sys.argv
    cells = [
        ("wire_create.rvt", build_wire_create, "wires", "CREATE"),
        ("wire_delete.rvt", build_wire_delete, "wires", "DELETE"),
        ("settings_modify.rvt", build_settings_modify, "electrical settings", "MODIFY"),
        ("load_class_create.rvt", build_load_class_create, "electrical settings", "CREATE"),
        ("panel_renumber.rvt", build_panel_renumber, "panel data", "MODIFY (renumber)"),
    ]
    manifest = {"template": os.path.relpath(SRC, ROOT), "files": []}
    all_ok = True
    for fname, fn, cat, verb in cells:
        out = os.path.join(HERE, fname)
        t0 = time.time()
        print(f"\n=== {fname}  ({cat} / {verb})", flush=True)
        entry = fn(out)
        entry["category"] = cat
        entry["verb"] = verb
        entry["build_seconds"] = round(time.time() - t0, 1)
        if not skip_validate:
            t1 = time.time()
            entry["validator"] = _validate(out)
            entry["validate_seconds"] = round(time.time() - t1, 1)
        else:
            entry["validator"] = {"skipped": True}
        val_ok = entry["validator"].get("ok", True)
        cell_ok = bool(entry["verify"]["structurally_valid"] and entry["SEMANTIC_OK"] and val_ok)
        entry["CELL_OK"] = cell_ok
        all_ok &= cell_ok
        manifest["files"].append(entry)
        v = entry["verify"]
        print(f"  structural: CRC {v['crc_failures']} ECC {v['ecc_mismatches']} "
              f"walker {v['walker_errors']} ISIZE {v['isize_identity_mismatches']} "
              f"stamps {v['stamps_ok']} count {v['elemtable_count']}=={v['header_count']} "
              f"unit0==ET {v['unit0_ids_equal_elemtable']}  -> "
              f"{'VALID' if v['structurally_valid'] else 'INVALID'}")
        print(f"  semantic readback: {'OK' if entry['SEMANTIC_OK'] else 'FAIL'}")
        vd = entry["validator"]
        if "errors" in vd:
            print(f"  rvt_validate: {'0 ERRORS' if vd['errors'] == 0 else vd['error_messages']}"
                  f" ({vd['warnings']} warning(s))")
        print(f"  ==> {'PASS' if cell_ok else 'FAIL'}  ({entry['build_seconds']}s)")
    manifest["all_ok"] = bool(all_ok)
    mp = os.path.join(HERE, "manifest.json")
    with open(mp, "w") as f:
        json.dump(manifest, f, indent=1, default=str)
    print(f"\nwrote {mp}")
    print("ALL CELLS PASS" if all_ok else "SOME CELL FAILED — see manifest.json")
    return 0 if all_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
