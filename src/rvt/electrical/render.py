"""Renderers for computed panel schedules: printable HTML (industry-style
two-column panelboard schedule), CSV, and a machine-readable summary
JSON that the tekton-ifc generators consume (psets + spec circuits).
"""
from __future__ import annotations

import csv
import html
import io
from typing import Iterable, Optional

from . import calcs
from .schedule import PanelSchedule, TransformerCalc

DISCLAIMER = ("DESIGN AID — computed by tekton's calc engine from the job "
              "spec. All values must be reviewed and stamped by the "
              "licensed engineer of record before construction/permit. "
              "Simplified NEC-style rules; conductor derating, voltage drop, "
              "series ratings and coordination are NOT evaluated.")

CSS = """
html,body{background:#fff;}
body{font-family:'Helvetica Neue',Arial,sans-serif;color:#111;margin:24px;}
h1{font-size:20px;margin:0 0 4px 0;} h2{font-size:14px;margin:18px 0 6px;}
.sub{color:#555;font-size:12px;margin-bottom:14px;}
table{border-collapse:collapse;width:100%;font-size:11px;}
th,td{border:1px solid #444;padding:3px 5px;}
th{background:#e6e6e6;font-weight:600;text-align:center;}
td.num{text-align:right;font-variant-numeric:tabular-nums;}
td.ctr{text-align:center;}
td.desc-r{text-align:left;}
td.desc-l{text-align:right;}
td.space{color:#999;font-style:italic;}
.hdr td{border:1px solid #444;padding:4px 8px;}
td.k{font-weight:600;background:#f2f2f2;white-space:nowrap;}
.foot{margin-top:10px;}
.warn{color:#a40000;font-weight:600;}
.disclaimer{margin-top:16px;font-size:10px;color:#444;border-top:1px solid #999;
padding-top:6px;}
.eg{display:inline-block;background:#fff2b3;border:1px solid #d1b400;padding:2px 8px;
font-size:11px;font-weight:600;margin-bottom:8px;}
@media print{ body{margin:8mm;} .pagebreak{page-break-before:always;} }
"""


def _fmt(v: float, nd: int = 0) -> str:
    return f"{v:,.{nd}f}"


def _phase(sched: PanelSchedule, slot: int) -> str:
    return calcs.slot_phase(slot, 3 if sched.panel.system.phases == 3 else 1)


# ------------------------------------------------------------------ HTML
def panel_html(sched: PanelSchedule, example_banner: bool = False,
               xfmr: Optional[TransformerCalc] = None) -> str:
    """Render one panel as a full standalone HTML page."""
    p = sched.panel
    s = p.system
    h = html.escape
    rows = []

    def cell_block(slot: int, side: str) -> str:
        c = sched.slot_map.get(slot)
        ph = _phase(sched, slot)
        if c is None:
            desc = '<td class="space" colspan="3">— SPACE —</td>'
            va = '<td class="num"></td>'
            ckt = f'<td class="ctr">{slot}</td>'
            if side == "L":
                return ckt + desc + va
            return va + desc + ckt
        first = (slot == c.slots[0])
        va_val = c.va_by_phase.get(ph, 0.0)
        va_txt = _fmt(va_val) if va_val else ""
        if first:
            cont = " (cont.)" if c.load.continuous else ""
            desc_txt = h(c.load.description) + cont
            brk = f"{c.breaker:g}/{c.poles}P"
            wire = h(c.wire)
        else:
            desc_txt = "&nbsp;&nbsp;&#9474;"   # continuation mark
            brk = "&#9474;"
            wire = ""
        dcls = "desc-l" if side == "L" else "desc-r"
        cells_l = [f'<td class="ctr">{slot}</td>',
                   f'<td class="{dcls}">{desc_txt}</td>',
                   f'<td class="ctr">{wire}</td>',
                   f'<td class="ctr">{brk}</td>',
                   f'<td class="num">{va_txt}</td>']
        return "".join(cells_l if side == "L" else list(reversed(cells_l)))

    nrows = (p.spaces + 1) // 2
    for r in range(nrows):
        ls, rs = 2 * r + 1, 2 * r + 2
        ph = _phase(sched, ls)
        rows.append(f"<tr>{cell_block(ls,'L')}"
                    f'<td class="ctr" style="background:#f7f7f7"><b>{ph}</b></td>'
                    f"{cell_block(rs,'R') if rs <= p.spaces else '<td colspan=5></td>'}</tr>")

    hdr = f"""
<table class="hdr" style="width:auto;margin-bottom:10px">
<tr><td class="k">PANEL</td><td><b>{h(p.name)}</b></td>
    <td class="k">VOLTAGE</td><td>{h(s.label)}</td>
    <td class="k">MOUNTING</td><td>{h(p.mounting)}</td></tr>
<tr><td class="k">MAINS</td><td>{h(p.mains_type)} — {p.mains_rating:g} A</td>
    <td class="k">BUS RATING</td><td>{p.bus_rating:g} A</td>
    <td class="k">A.I.C.</td><td>{(str(p.aic_ka)+' kA') if p.aic_ka else 'per calc'}</td></tr>
<tr><td class="k">FED FROM</td><td>{h(p.fed_from) or '—'}</td>
    <td class="k">FEEDER</td><td>{h(p.feeder) or '—'}</td>
    <td class="k">SPACES</td><td>{p.spaces} ({sched.poles_used} used)</td></tr>
</table>"""

    va_head = '<th>VA (Ø)</th>'
    thead = (f"<tr><th>CKT</th><th>LOAD DESCRIPTION</th><th>WIRE</th>"
             f"<th>BKR/P</th>{va_head}<th>Ø</th>{va_head}<th>BKR/P</th>"
             f"<th>WIRE</th><th>LOAD DESCRIPTION</th><th>CKT</th></tr>")

    pv = sched.phase_va
    v_ln = s.v_ln or s.v_ll
    phase_amps = {k: (pv[k] / v_ln if v_ln else 0.0) for k in ("A", "B", "C")}
    demand_rows = "".join(
        f"<tr><td>{h(k)}</td><td class='num'>{_fmt(sched.class_va[k])}</td>"
        f"<td>{h(calcs.DEMAND_FACTORS_DOC.get(k,''))}</td>"
        f"<td class='num'>{_fmt(sched.class_demand_va.get(k,0.0))}</td></tr>"
        for k in sched.class_va)

    warns = "".join(f'<li class="warn">{h(w)}</li>' for w in sched.warnings) \
        or "<li>None.</li>"

    xfmr_html = ""
    if xfmr is not None:
        t = xfmr.transformer
        xfmr_html = f"""
<h2>Serving transformer — {h(t.name)}</h2>
<table style="width:auto"><tr><th>Rating</th><th>Primary FLA</th>
<th>Primary FLA×125%</th><th>Primary OCPD</th><th>Secondary FLA</th>
<th>Secondary OCPD</th><th>Demand loading</th></tr>
<tr><td class="num">{t.kva:g} kVA {t.primary_v:g}-{t.secondary_v:g} V</td>
<td class="num">{xfmr.primary_fla:.1f} A</td><td class="num">{xfmr.primary_x125:.1f} A</td>
<td class="num">{xfmr.primary_ocpd} A</td><td class="num">{xfmr.secondary_fla:.1f} A</td>
<td class="num">{xfmr.secondary_ocpd} A</td>
<td class="num">{(f'{xfmr.loading_pct:.0f}%') if xfmr.loading_pct is not None else '—'}</td></tr>
</table>"""

    banner = ('<div class="eg">EXAMPLE data — illustrative circuit/load '
              'list, NOT the issued DDOT schedule</div>'
              if example_banner else "")

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Panelboard Schedule — {h(p.name)}</title>
<style>{CSS}</style></head><body>
{banner}
<h1>PANELBOARD SCHEDULE — {h(p.name)}</h1>
<div class="sub">{h(s.label)} • {h(p.mains_type)} {p.mains_rating:g} A •
bus {p.bus_rating:g} A • {p.spaces} spaces • {h(p.notes)}</div>
{hdr}
<table>{thead}{''.join(rows)}
<tr><th colspan="4" style="text-align:right">CONNECTED VA / PHASE</th>
<td class="num"><b>A {_fmt(pv['A'])}</b><br>B {_fmt(pv['B'])}<br>C {_fmt(pv['C'])}</td>
<td></td>
<td class="num"><b>A {phase_amps['A']:.0f} A</b><br>B {phase_amps['B']:.0f} A<br>C {phase_amps['C']:.0f} A</td>
<th colspan="4" style="text-align:left">PHASE AMPS (VA ÷ {v_ln:g} V)</th></tr>
</table>
<div class="foot">
<h2>Load summary</h2>
<table style="width:auto"><tr><th>Load class</th><th>Connected VA</th>
<th>Demand rule</th><th>Demand VA</th></tr>{demand_rows}
<tr><th style="text-align:right">TOTAL</th><td class="num"><b>{_fmt(sched.connected_va)}</b></td>
<td>connected {sched.connected_kva:.1f} kVA → demand {sched.demand_kva:.1f} kVA</td>
<td class="num"><b>{_fmt(sched.demand_va)}</b></td></tr></table>
<table style="width:auto;margin-top:6px">
<tr><td class="k">Connected load</td><td class="num">{sched.connected_kva:.2f} kVA</td>
<td class="num">{sched.connected_amps:.1f} A</td></tr>
<tr><td class="k">Demand load</td><td class="num">{sched.demand_kva:.2f} kVA</td>
<td class="num"><b>{sched.demand_amps:.1f} A</b> vs bus {p.bus_rating:g} A</td></tr>
<tr><td class="k">Continuous portion</td><td class="num">{sched.continuous_va/1000:.2f} kVA</td>
<td class="num">largest motor {sched.largest_motor_va/1000:.2f} kVA</td></tr>
<tr><td class="k">Phase balance</td><td class="num">max−min {_fmt(sched.imbalance_va)} VA</td>
<td class="num">{sched.imbalance_pct:.1f}% of average phase</td></tr>
</table>
<h2>Warnings / review items</h2><ul>{warns}</ul>
{xfmr_html}
</div>
<div class="disclaimer">{h(DISCLAIMER)}</div>
</body></html>
"""


# -------------------------------------------------------------------- CSV
CSV_FIELDS = ["panel", "ckt", "slots", "description", "load_class", "phases",
              "poles", "va", "amps", "breaker_a", "wire", "continuous",
              "va_A", "va_B", "va_C"]


def panel_csv(sched: PanelSchedule) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(CSV_FIELDS)
    for c in sched.circuits:
        w.writerow([sched.panel.name, c.number,
                    "-".join(str(s) for s in c.slots),
                    c.load.description, c.load.load_class, c.load.phases,
                    c.poles, round(c.va, 1), round(c.amps, 2), c.breaker,
                    c.wire, int(bool(c.load.continuous)),
                    round(c.va_by_phase["A"], 1),
                    round(c.va_by_phase["B"], 1),
                    round(c.va_by_phase["C"], 1)])
    return buf.getvalue()


# ------------------------------------------------------------- summary
def panel_summary(sched: PanelSchedule) -> dict:
    """Machine-readable summary for the tekton-ifc generators.

    ``psets.PanelScheduleCalc`` mirrors the room-spec pset style
    (``{value, type}``) so ifc/spec generators can merge it verbatim;
    ``circuits`` matches the spec_to_rvt ``circuits`` schema
    (panel/load/number/description/rating/poles).
    """
    p = sched.panel
    pv = sched.phase_va
    circuits = []
    for c in sched.circuits:
        circuits.append({
            "panel": p.name, "number": str(c.number),
            "load": c.load.tag or c.load.description,
            "equipmentLoad": bool(c.load.tag),
            "description": c.load.description,
            "rating": c.breaker, "poles": c.poles, "wire": c.wire,
            "va": round(c.va, 1), "amps": round(c.amps, 2),
            "loadClass": c.load.load_class,
            "continuous": bool(c.load.continuous),
            "slots": list(c.slots), "phases": list(c.phases_used),
        })
    return {
        "panel": p.name,
        "system": p.system.text,
        "systemLabel": p.system.label,
        "mainsType": p.mains_type, "mainsRatingA": p.mains_rating,
        "busRatingA": p.bus_rating, "spaces": p.spaces,
        "polesUsed": sched.poles_used,
        "fedFrom": p.fed_from, "feeder": p.feeder,
        "connectedVA": round(sched.connected_va, 1),
        "connectedKVA": round(sched.connected_kva, 3),
        "demandVA": round(sched.demand_va, 1),
        "demandKVA": round(sched.demand_kva, 3),
        "connectedAmps": round(sched.connected_amps, 2),
        "demandAmps": round(sched.demand_amps, 2),
        "continuousVA": round(sched.continuous_va, 1),
        "largestMotorVA": round(sched.largest_motor_va, 1),
        "phaseVA": {k: round(pv[k], 1) for k in ("A", "B", "C")},
        "phaseImbalanceVA": round(sched.imbalance_va, 1),
        "phaseImbalancePct": round(sched.imbalance_pct, 2),
        "classConnectedVA": {k: round(v, 1) for k, v in sched.class_va.items()},
        "classDemandVA": {k: round(v, 1)
                          for k, v in sched.class_demand_va.items()},
        "warnings": list(sched.warnings),
        "circuits": circuits,
        "psets": {
            "PanelScheduleCalc": {
                "ConnectedLoadKVA": {"value": round(sched.connected_kva, 2), "type": "real"},
                "DemandLoadKVA": {"value": round(sched.demand_kva, 2), "type": "real"},
                "DemandLoadAmps": {"value": round(sched.demand_amps, 1), "type": "current"},
                "PhaseAVA": {"value": round(pv["A"], 0), "type": "real"},
                "PhaseBVA": {"value": round(pv["B"], 0), "type": "real"},
                "PhaseCVA": {"value": round(pv["C"], 0), "type": "real"},
                "PhaseImbalancePct": {"value": round(sched.imbalance_pct, 1), "type": "real"},
                "PolesUsed": {"value": sched.poles_used, "type": "count"},
                "CalcBasis": "tekton electrical calc engine (design aid, NEC-style simplified)",
                "ReviewRequired": "Licensed engineer to verify before construction",
            }
        },
    }


def transformer_summary(tc: TransformerCalc) -> dict:
    t = tc.transformer
    return {
        "name": t.name, "kva": t.kva,
        "primaryV": t.primary_v, "secondaryV": t.secondary_v,
        "phases": t.phases, "fedFrom": t.fed_from, "feeds": t.feeds,
        "primaryFLA": round(tc.primary_fla, 2),
        "primaryFLAx125": round(tc.primary_x125, 2),
        "primaryOCPD": tc.primary_ocpd,
        "secondaryFLA": round(tc.secondary_fla, 2),
        "secondaryOCPD": tc.secondary_ocpd,
        "fedPanel": tc.fed_panel,
        "fedConnectedKVA": (round(tc.fed_connected_kva, 3)
                            if tc.fed_connected_kva is not None else None),
        "fedDemandKVA": (round(tc.fed_demand_kva, 3)
                         if tc.fed_demand_kva is not None else None),
        "loadingPct": (round(tc.loading_pct, 1)
                       if tc.loading_pct is not None else None),
        "warnings": list(tc.warnings),
        "psets": {
            "TransformerCalc": {
                "PrimaryFLA": {"value": round(tc.primary_fla, 1), "type": "current"},
                "PrimaryOCPD": {"value": tc.primary_ocpd, "type": "current"},
                "SecondaryFLA": {"value": round(tc.secondary_fla, 1), "type": "current"},
                "SecondaryOCPD": {"value": tc.secondary_ocpd, "type": "current"},
                "DemandLoadingPct": {"value": (round(tc.loading_pct, 1)
                                               if tc.loading_pct is not None else None),
                                     "type": "real"},
                "CalcBasis": "tekton electrical calc engine (design aid)",
            }
        },
    }
