"""Job runner: electrical-job.json -> schedules (HTML/CSV) + summary JSON.

Job JSON shape (``kind: tekton.electrical-job``)::

    {
      "specVersion": "0.1.0",
      "kind": "tekton.electrical-job",
      "project": { "name": ..., "number": ... },
      "example": true,                      # renders an EXAMPLE banner
      "panels": [ {
        "name": "B-HG4", "system": "480Y/277", "mainsType": "MCB",
        "mainsRatingA": 400, "busRatingA": 400, "spaces": 42,
        "aicKA": 35, "mounting": "Surface", "fedFrom": "MDB",
        "feeder": "BS-FD1020", "notes": "...",
        "circuits": [ {                     # one entry per load
          "number": 1,                      # optional fixed slot
          "description": "XFMR-LR1 primary", "kva": 45,   # or "va"/"amps"
          "phases": 3, "poles": 3, "loadClass": "xfmr",
          "continuous": true, "breaker": null, "wire": null,
          "equipment": "XFMR-LR1"           # optional element it feeds
        } ] } ],
      "transformers": [ { "name": "XFMR-LR1", "kva": 45, "primaryV": 480,
        "secondaryV": 208, "phases": 3, "fedFrom": "B-HG4",
        "feeds": "B-LR1" } ]
    }
"""
from __future__ import annotations

import json
import os
from typing import Optional

from . import render
from .models import Load, Panel, Transformer, VoltageSystem
from .schedule import (PanelSchedule, TransformerCalc, build_panel_schedule,
                       calc_transformer)


# ------------------------------------------------------------- parse job
def _load(d: dict) -> Load:
    return Load(
        description=str(d.get("description") or d.get("name") or "LOAD"),
        va=(float(d["va"]) if d.get("va") is not None else None),
        kva=(float(d["kva"]) if d.get("kva") is not None else None),
        amps=(float(d["amps"]) if d.get("amps") is not None else None),
        phases=int(d.get("phases", 1)),
        poles=(int(d["poles"]) if d.get("poles") is not None else None),
        load_class=str(d.get("loadClass", d.get("load_class", "misc"))),
        continuous=bool(d.get("continuous", False)),
        breaker=(float(d["breaker"]) if d.get("breaker") is not None else None),
        wire=(str(d["wire"]) if d.get("wire") else None),
        number=(int(d["number"]) if d.get("number") is not None else None),
        tag=(str(d["equipment"]) if d.get("equipment") else None),
    )


def _panel(d: dict) -> Panel:
    sys = VoltageSystem.parse(d.get("system", "208Y/120"),
                              phases=d.get("phases"), wires=d.get("wires"))
    return Panel(
        name=str(d["name"]),
        system=sys,
        mains_type=str(d.get("mainsType", "MLO")),
        mains_rating=float(d.get("mainsRatingA", d.get("busRatingA", 225))),
        bus_rating=float(d.get("busRatingA", 225)),
        spaces=int(d.get("spaces", 42)),
        fed_from=str(d.get("fedFrom", "")),
        feeder=str(d.get("feeder", "")),
        mounting=str(d.get("mounting", "Surface")),
        aic_ka=(float(d["aicKA"]) if d.get("aicKA") is not None else None),
        min_branch_breaker=float(d.get("minBranchBreakerA", 15)),
        loads=[_load(c) for c in d.get("circuits", [])],
        notes=str(d.get("notes", "")),
    )


def _transformer(d: dict) -> Transformer:
    return Transformer(
        name=str(d["name"]), kva=float(d["kva"]),
        primary_v=float(d.get("primaryV", 480)),
        secondary_v=float(d.get("secondaryV", 208)),
        phases=int(d.get("phases", 3)),
        secondary_system=str(d.get("secondarySystem", "")),
        fed_from=str(d.get("fedFrom", "")),
        feeds=str(d.get("feeds", "")),
        impedance_pct=(float(d["impedancePct"])
                       if d.get("impedancePct") is not None else None),
    )


# --------------------------------------------------------------- engine
def compute_job(job: dict) -> dict:
    """Run all calcs. Returns ``{'panels': {name: PanelSchedule},
    'transformers': {name: TransformerCalc}}``."""
    panels = {p.name: build_panel_schedule(p)
              for p in (_panel(d) for d in job.get("panels", []))}
    xfmrs = {}
    for d in job.get("transformers", []):
        t = _transformer(d)
        fed = panels.get(t.feeds) if t.feeds else None
        xfmrs[t.name] = calc_transformer(t, fed)
    return {"panels": panels, "transformers": xfmrs}


def summary_dict(job: dict, results: dict) -> dict:
    """Summary JSON consumed by the tekton-ifc generators."""
    circuits = []
    for sched in results["panels"].values():
        circuits.extend(render.panel_summary(sched)["circuits"])
    return {
        "kind": "tekton.electrical-summary",
        "specVersion": job.get("specVersion", "0.1.0"),
        "project": job.get("project", {}),
        "example": bool(job.get("example", False)),
        "disclaimer": render.DISCLAIMER,
        "codeBasis": ("NEC-style simplified: line current I=VA/V (1-ph) or "
                      "VA/(V*sqrt3) (3-ph); continuous/motor/xfmr loads x125%; "
                      "next standard OCPD (240.6(A)); Cu 75C ampacity "
                      "(310.16 + 240.4(D)); demand: lighting 100%, "
                      "receptacles first 10 kVA 100% then 50% (220.44), "
                      "motors +25% of largest (430.24)."),
        "panels": {n: render.panel_summary(s)
                   for n, s in results["panels"].items()},
        "transformers": {n: render.transformer_summary(t)
                         for n, t in results["transformers"].items()},
        # spec_to_rvt-compatible circuit list (both ends must be authored
        # elements; 'equipmentLoad' false entries are branch circuits with
        # no modeled load element and are skipped by the generator).
        "circuits": circuits,
    }


def render_job(job: dict, out_dir: str) -> dict:
    """Compute everything and write per-panel HTML/CSV + summary.json.

    Returns the summary dict. Written files: ``<panel>.html``,
    ``<panel>.csv`` per panel, ``schedules.html`` (all panels, print-
    ready), ``summary.json``.
    """
    os.makedirs(out_dir, exist_ok=True)
    results = compute_job(job)
    example = bool(job.get("example", False))

    # transformer serving each panel (for the per-panel HTML block)
    serving = {}
    for tc in results["transformers"].values():
        if tc.transformer.feeds:
            serving[tc.transformer.feeds] = tc

    pages = []
    for name, sched in results["panels"].items():
        page = render.panel_html(sched, example_banner=example,
                                 xfmr=serving.get(name))
        with open(os.path.join(out_dir, f"{name}.html"), "w",
                  encoding="utf-8") as f:
            f.write(page)
        with open(os.path.join(out_dir, f"{name}.csv"), "w",
                  encoding="utf-8", newline="") as f:
            f.write(render.panel_csv(sched))
        # body-only extract for the combined document
        body = page.split("<body>", 1)[1].rsplit("</body>", 1)[0]
        pages.append(f'<section class="pagebreak">{body}</section>')

    combined = ("<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
                f"<title>Panelboard schedules — "
                f"{job.get('project', {}).get('name', 'job')}</title>"
                f"<style>{render.CSS} section.pagebreak:first-of-type"
                "{page-break-before:auto;}</style></head><body>"
                + "".join(pages) + "</body></html>")
    with open(os.path.join(out_dir, "schedules.html"), "w",
              encoding="utf-8") as f:
        f.write(combined)

    summ = summary_dict(job, results)
    with open(os.path.join(out_dir, "summary.json"), "w",
              encoding="utf-8") as f:
        json.dump(summ, f, indent=2)
    return summ


def run(spec_path: str, out_dir: str) -> dict:
    with open(spec_path, "r", encoding="utf-8") as f:
        job = json.load(f)
    return render_job(job, out_dir)
