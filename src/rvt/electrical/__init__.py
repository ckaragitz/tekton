"""rvt.electrical — pure-Python electrical calc engine (design AID).

Computes NEC-style panel schedules and load calcs from a job spec so an
electrical/MEP contractor gets design-time value with NO Autodesk seat in
the loop. Outputs feed back into what we author: circuit ratings/poles for
``Document.add_circuit`` in the .rvt, psets for the IFC bridge, and the
printable panelboard schedule the contractor submits. A licensed engineer
reviews every number — that IS the product model (AI computes, seats review).
"""
from .models import Circuit, Load, Panel, Transformer, VoltageSystem, LOAD_CLASSES
from . import calcs
from .calcs import (
    STANDARD_OCPD, CU_AMPACITY_75C, line_current, load_va, transformer_current,
    next_standard_ocpd, select_breaker, select_wire, transformer_primary_ocpd,
    demand_kva, panel_amps, slot_phase, circuit_slots,
)
from .schedule import (PanelSchedule, TransformerCalc, build_panel_schedule,
                       calc_transformer)
from .render import panel_html, panel_csv, panel_summary, transformer_summary
from .job import compute_job, render_job, summary_dict, run

__all__ = [
    "Circuit", "Load", "Panel", "Transformer", "VoltageSystem", "LOAD_CLASSES",
    "calcs", "STANDARD_OCPD", "CU_AMPACITY_75C", "line_current", "load_va",
    "transformer_current", "next_standard_ocpd", "select_breaker",
    "select_wire", "transformer_primary_ocpd", "demand_kva", "panel_amps",
    "slot_phase", "circuit_slots", "PanelSchedule", "TransformerCalc",
    "build_panel_schedule", "calc_transformer", "panel_html", "panel_csv",
    "panel_summary", "transformer_summary", "compute_job", "render_job",
    "summary_dict", "run",
]
