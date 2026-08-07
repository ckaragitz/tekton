"""rvt.frontdoor.intent -- the ONE INTENT MODEL every input route resolves to.

The front door has THREE inputs (prompt / IFC / existing .rvt) and ONE
authoring intent model between them: :class:`rvt.ifc.intent.IntentModel`
(spec v2).  This module is the thin normalisation layer around it -- it
IMPORTS the resolver (never edits it) and adds only what the front door
itself needs:

* :func:`intent_from_ifc` -- the ``--ifc`` route: the resolved-placement,
  Pset-join-key intent (the ifc-room stream's resolver).
* :func:`summarize` -- a compact, JSON-able intent summary for the manifest
  (equipment by kind, walls, feeder edges, family plans by status).
* :func:`combination_check` -- detects the OPEN BUG combination (created
  WALLS + LOADED FAMILY DOCUMENTS in the same file trip Revit's audit; walls
  alone PASS, families alone PASS -- docs/inbox/genesis-audit.md verdict
  #24) so the build step can DEGRADE HONESTLY: split into two coordinated
  files (``--strict``) or emit one file STAMPED 'PROOF-ONLY: walls+families
  combination unverified'.  The front door never silently ships an
  unverified combination.

Territory: ``src/rvt/frontdoor/`` (front-door stream); ``rvt.ifc.intent`` is
imported, not edited.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, List, Optional

from ..ifc import intent as I

__all__ = [
    "IntentModel", "IntentError", "intent_from_ifc", "write_intent_json",
    "summarize", "CombinationVerdict", "combination_check",
    "buildable_family_plans", "OPEN_BUG_ID", "OPEN_BUG_TEXT",
]

#: re-export: the ONE intent model class
IntentModel = I.IntentModel
IntentError = I.IntentError

#: the open bug this stream must DETECT and never silently ship
OPEN_BUG_ID = "walls+loaded-families-audit"
OPEN_BUG_TEXT = (
    "created WALLS + LOADED FAMILY DOCUMENTS in the SAME file currently trip "
    "Autodesk's audit ('Processing failed'), while walls alone PASS "
    "(electrical_room_2500a_walls_only.rvt, certified) and loaded families "
    "alone PASS (stage_L8_lp4.rvt, certified) -- docs/inbox/genesis-audit.md "
    "ORCHESTRATOR VERDICTS #24 (verdict #22's 'one defective family' RETRACTED). "
    "The mechanism is under bisection in the render/creation stream; until it "
    "is fixed the front door DEGRADES: --strict emits two coordinated files "
    "(shell + equipment), the default emits one combined file STAMPED "
    "'PROOF-ONLY: walls+families combination unverified'.")


# ---------------------------------------------------------------------------
# route (2): the IFC intent
# ---------------------------------------------------------------------------

def intent_from_ifc(ifc_path: str) -> IntentModel:
    """The ``--ifc`` route: resolve an authored IFC into the placement-true,
    tagging-contract-mapped intent (spec v2) -- pure delegation to
    :func:`rvt.ifc.intent.resolve_intent` (the ifc-room stream's resolver)."""
    return I.resolve_intent(ifc_path)


def write_intent_json(model: IntentModel, path: str) -> str:
    """Persist the intent (spec v2 JSON) -- the same shape for every route."""
    return I.write_intent(model, path)


# ---------------------------------------------------------------------------
# summaries
# ---------------------------------------------------------------------------

def buildable_family_plans(model: IntentModel) -> List[I.FamilyPlan]:
    """Family plans the build step will actually generate + LOAD (resolved
    catalog products and the honest house switchboard)."""
    return [p for p in (model.family_plans or []) if p.status in ("resolved", "house")]


def summarize(model: IntentModel) -> Dict[str, Any]:
    """Compact, JSON-able summary of an intent for the deliverable manifest."""
    kinds: Dict[str, int] = {}
    for e in model.equipment:
        kinds[e.kind] = kinds.get(e.kind, 0) + 1
    plans_by_status: Dict[str, int] = {}
    for p in (model.family_plans or []):
        plans_by_status[p.status] = plans_by_status.get(p.status, 0) + 1
    walls = model.room.walls if model.room else []
    return {
        "project": model.project_name,
        "source": model.source_path,
        "schema": model.schema,
        "levels": [{"id": l.get("id"), "name": l.get("name"),
                    "elevation": l.get("elevation")} for l in (model.levels or [])],
        "room": None if not model.room else {
            "name": model.room.name,
            "walls": len(walls),
            "walls_synthesized": sum(1 for w in walls if w.synthesized),
            "doors": len(model.room.doors),
            "ring_ccw": bool((model.room.clear or {}).get("ring_ccw")),
            "centerline_extents_m": (model.room.clear or {}).get("centerline_extents_m"),
        },
        "equipment_total": len(model.equipment),
        "equipment_by_kind": kinds,
        "equipment": [{"tag": e.tag, "kind": e.kind, "disposition": e.disposition,
                       "insertion_m": [round(float(x), 3) for x in e.insertion_m],
                       "mounting": e.mounting, "frame_kind": e.frame_kind}
                      for e in model.equipment],
        "feeder_edges": [{"from": ed.source, "to": ed.target, "kind": ed.kind,
                          "rating_a": ed.rating_a, "voltage": ed.voltage}
                         for ed in model.feeders],
        "family_plans_by_status": plans_by_status,
        "family_plans": [{"tag": p.tag, "kind": p.kind, "status": p.status,
                          "constructor": (p.constructor.split(".")[-1] if p.constructor else None),
                          "variant": p.variant, "catalog": p.catalog,
                          "refusal": p.refusal}
                         for p in (model.family_plans or [])],
        "clearances": len(model.clearances or []),
        "audit": dict(model.audit or {}),
    }


# ---------------------------------------------------------------------------
# the open-bug combination detector
# ---------------------------------------------------------------------------

@dataclass
class CombinationVerdict:
    """What the build step must do about the walls+families open bug."""
    has_walls: bool
    n_walls: int
    has_loaded_families: bool
    n_loaded_families: int
    triggers_open_bug: bool
    mode: str                       # 'single' | 'split-strict' | 'stamp-proof-only'
    stamp: Optional[str]            # the manifest stamp when unverified
    files: List[str]                # planned output roles: ['combined'] | ['shell', 'equipment']
    reason: str
    notes: List[str] = dc_field(default_factory=list)

    def as_json(self) -> Dict[str, Any]:
        return {
            "open_bug": OPEN_BUG_ID if self.triggers_open_bug else None,
            "open_bug_text": OPEN_BUG_TEXT if self.triggers_open_bug else None,
            "has_walls": self.has_walls, "n_walls": self.n_walls,
            "has_loaded_families": self.has_loaded_families,
            "n_loaded_families": self.n_loaded_families,
            "triggers_open_bug": self.triggers_open_bug,
            "mode": self.mode, "stamp": self.stamp, "files": list(self.files),
            "reason": self.reason, "notes": list(self.notes),
        }


def combination_check(model: IntentModel, *, strict: bool = False) -> CombinationVerdict:
    """Decide how the build must degrade for THIS intent.

    * walls only, or families only  -> ``mode='single'`` (a proven-shaped
      file: walls-only and families-only are BOTH viewer-certified shapes).
    * walls AND >=1 loadable family together = the OPEN BUG combination:
        - ``strict``  -> ``mode='split-strict'``: TWO coordinated files
          (``shell`` = walls only; ``equipment`` = loaded families + their
          instances), each individually a proven shape; the manifest ties
          them together (same base, same coordinate frame, same intent).
        - default     -> ``mode='stamp-proof-only'``: ONE combined file whose
          manifest is STAMPED 'PROOF-ONLY: walls+families combination
          unverified'.
      Never a silent single unverified file.
    """
    n_walls = len(model.room.walls) if model.room else 0
    n_fam = len(buildable_family_plans(model))
    has_w, has_f = n_walls > 0, n_fam > 0
    if has_w and has_f:
        if strict:
            v = CombinationVerdict(
                has_walls=True, n_walls=n_walls, has_loaded_families=True,
                n_loaded_families=n_fam, triggers_open_bug=True, mode="split-strict",
                stamp=None, files=["shell", "equipment"],
                reason=("--strict: the walls+loaded-families combination is the OPEN BUG, so "
                        "the room is emitted as TWO coordinated files -- 'shell' (the "
                        f"{n_walls} walls on the base) and 'equipment' (the {n_fam} loaded "
                        "families + their placed instances on the base) -- each a "
                        "viewer-certified SHAPE (walls-only PASS; families+placement PASS)."))
            v.notes.append("both files are grown on the SAME base with the SAME intent and "
                           "coordinate frame; link both into one Revit project / open side by "
                           "side. When the render/creation stream fixes the open bug the "
                           "front door will emit one file again (drop --strict then).")
        else:
            stamp = "PROOF-ONLY: walls+families combination unverified"
            v = CombinationVerdict(
                has_walls=True, n_walls=n_walls, has_loaded_families=True,
                n_loaded_families=n_fam, triggers_open_bug=True, mode="stamp-proof-only",
                stamp=stamp, files=["combined"],
                reason=("default: ONE combined file (the room's walls + the loaded families + "
                        "their instances) is emitted and the manifest is STAMPED "
                        f"'{stamp}' -- this exact combination is the OPEN BUG "
                        "(unverified/failing in the viewer). Pass --strict to get two "
                        "coordinated proven-shaped files instead."))
            v.notes.append("the stamp is not decoration: it is the front door refusing to "
                           "represent an unverified combination as accepted; the file's "
                           "own self-checks (validator / registries / identity) still run.")
        return v
    # no combination -> a single proven-shaped file
    what = ("walls only (viewer-certified shape: room shell on the genesis base)" if has_w
            else "loaded families + instances only (viewer-certified shape: family load + "
                 "placement on the genesis base)" if has_f
            else "no walls and no loadable families (nothing model-side to author)")
    return CombinationVerdict(
        has_walls=has_w, n_walls=n_walls, has_loaded_families=has_f,
        n_loaded_families=n_fam, triggers_open_bug=False, mode="single",
        stamp=None, files=["combined"],
        reason=f"no walls+families combination in this intent: {what}")


# ---------------------------------------------------------------------------
# convenience: read a persisted intent JSON back (summary use only)
# ---------------------------------------------------------------------------

def load_intent_json(path: str) -> Dict[str, Any]:  # pragma: no cover - trivial
    with open(path) as fh:
        return json.load(fh)
