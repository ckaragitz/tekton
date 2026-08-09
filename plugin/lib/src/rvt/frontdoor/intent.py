"""rvt.frontdoor.intent -- the ONE INTENT MODEL every input route resolves to.

The front door has THREE inputs (prompt / IFC / existing .rvt) and ONE
authoring intent model between them: :class:`rvt.ifc.intent.IntentModel`
(spec v2).  This module is the thin normalisation layer around it -- it
IMPORTS the resolver (never edits it) and adds only what the front door
itself needs:

* :func:`intent_from_ifc` -- the ``--ifc`` route: the resolved-placement,
  Pset-join-key intent (the ifc-room stream's resolver).
* :func:`summarize` -- a compact, JSON-able intent summary for the manifest
  (equipment by kind, walls, feeder edges, family plans by status, the
  recorded-only ``other_products``, and the IFC census of issue #153: what
  the file held vs what reached the intent).
* :func:`combination_check` -- detects THE OPEN CELL (docs/inbox/
  genesis-audit.md ORCHESTRATOR VERDICTS #48, issue #16): PLACED INSTANCES
  of OUR generated family documents on OUR composed genesis base fail
  Autodesk's audit, while walls PASS, loaded families PASS, and walls +
  loaded families together PASS (WF_fix / WF_nofix, verdict #27 -- the old
  'walls+families combination' suspicion is EXONERATED).  The build step
  DEGRADES HONESTLY on the true cell: split into two coordinated files
  (``--strict``: shell = walls + loaded families, equipment = the placed
  instances) or emit one file STAMPED with :data:`OPEN_CELL_STAMP`.  A
  stamp is a LABEL (hard rule 1): every route still delivers its file(s).

Territory: ``src/rvt/frontdoor/`` (front-door stream); ``rvt.ifc.intent`` is
imported, not edited.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, Iterable, List, Optional

from ..ifc import intent as I

__all__ = [
    "IntentModel", "IntentError", "intent_from_ifc", "write_intent_json",
    "summarize", "CombinationVerdict", "combination_check",
    "buildable_family_plans", "planned_instances",
    "OPEN_BUG_ID", "OPEN_BUG_TEXT", "OPEN_CELL_STAMP",
]

#: re-export: the ONE intent model class
IntentModel = I.IntentModel
IntentError = I.IntentError

#: the open cell this stream must DETECT, label, and still deliver
OPEN_BUG_ID = "generated-family-instances-on-composed-base"
OPEN_CELL_STAMP = ("PROOF-ONLY: generated-family INSTANCES on a composed genesis base "
                   "(open cell, docs/inbox/genesis-audit.md #48, issue #16)")
OPEN_BUG_TEXT = (
    "PLACED INSTANCES of OUR generated family documents on OUR composed "
    "genesis base are THE OPEN CELL: they fail Autodesk's audit ('Processing "
    "failed' -- ROOM2025_full.rvt, demo-250v-v5/prompt_room.rvt in "
    "docs/coverage/viewer-certified.json) while every other measured axis is "
    "exonerated -- docs/inbox/genesis-audit.md ORCHESTRATOR VERDICTS #48, "
    "issue #16 (next instrument: desktop Revit's own dialog). Certified around "
    "it: walls on the base PASS, loaded families PASS, walls + loaded families "
    "in ONE file PASS (WF_fix / WF_nofix, verdict #27), our famdocs + instances "
    "on a PRISTINE Revit host PASS (T1r / T1u / U16). Until the cell closes the "
    "front door DEGRADES, never withholds: --strict emits two coordinated files "
    "('shell' = walls + loaded families, the certified shape; 'equipment' = the "
    "placed instances, the open cell isolated), the default emits one combined "
    "file STAMPED '" + OPEN_CELL_STAMP + "'.")


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
        "other_products_total": len(model.other_products or []),
        "other_products": [{k: o.get(k) for k in ("name", "tag", "ifcClass", "kind", "disposition")}
                           for o in (model.other_products or [])],
        "census": dict(model.census or {}),
        "audit": dict(model.audit or {}),
    }


def planned_instances(model: IntentModel,
                      loaded_tags: Optional[Iterable[str]] = None) -> int:
    """How many equipment instances the E stage will place: one per equipment
    item whose family is loaded.  ``loaded_tags=None`` = plan time (every
    buildable plan is assumed to load); a set = the tags that actually loaded."""
    tags = (set(loaded_tags) if loaded_tags is not None
            else {p.tag for p in buildable_family_plans(model)})
    return sum(1 for e in (model.equipment or []) if e.tag in tags)


_CELL_WHY = ("placed instances of OUR generated families on the composed genesis base "
             "are THE OPEN CELL (genesis-audit #48, issue #16; walls, loaded families "
             "and walls + loaded families are certified)")


# ---------------------------------------------------------------------------
# the open-cell detector
# ---------------------------------------------------------------------------

@dataclass
class CombinationVerdict:
    """What the build step must do about THE OPEN CELL (placed instances of
    our generated families on our composed genesis base)."""
    has_walls: bool
    n_walls: int
    has_loaded_families: bool
    n_loaded_families: int
    triggers_open_bug: bool
    mode: str                       # 'single' | 'split-strict' | 'stamp-proof-only'
    stamp: Optional[str]            # the manifest stamp when the open cell is exercised
    files: List[str]                # planned output roles: ['combined'] | ['shell', 'equipment']
    reason: str
    notes: List[str] = dc_field(default_factory=list)
    n_instances: int = 0            # instances the E stage will place
    composed_base: bool = True      # the host is our composed genesis base (lineage)

    @property
    def places_instances(self) -> bool:
        return self.n_instances > 0

    def as_json(self) -> Dict[str, Any]:
        return {
            "open_bug": OPEN_BUG_ID if self.triggers_open_bug else None,
            "open_bug_text": OPEN_BUG_TEXT if self.triggers_open_bug else None,
            "has_walls": self.has_walls, "n_walls": self.n_walls,
            "has_loaded_families": self.has_loaded_families,
            "n_loaded_families": self.n_loaded_families,
            "n_instances": self.n_instances,
            "places_instances": self.places_instances,
            "composed_base": self.composed_base,
            "triggers_open_bug": self.triggers_open_bug,
            "mode": self.mode, "stamp": self.stamp, "files": list(self.files),
            "reason": self.reason, "notes": list(self.notes),
        }


def combination_check(model: IntentModel, *, strict: bool = False,
                      stages: str = "FLWECV", composed_base: bool = True,
                      loaded_tags: Optional[Iterable[str]] = None) -> CombinationVerdict:
    """Decide how the build must degrade for THIS intent on THIS host.

    The truth table follows the ledger (docs/coverage/viewer-certified.json,
    docs/inbox/genesis-audit.md #27 / #48), not a suspicion:

    * PLACED INSTANCES of our generated families (``L`` + ``E`` in ``stages``
      and at least one loaded family with equipment) on our COMPOSED genesis
      base = THE OPEN CELL:
        - ``strict``  -> ``mode='split-strict'``: TWO coordinated files --
          ``shell`` = the walls + the LOADED families (the WF_fix-certified
          shape, no placement) and ``equipment`` = the loaded families +
          their PLACED instances (the open cell, isolated).  Both delivered.
        - default     -> ``mode='stamp-proof-only'``: ONE combined file whose
          manifest is STAMPED :data:`OPEN_CELL_STAMP`.  Delivered.
    * anything else -> ``mode='single'``, no open-cell stamp: walls only,
      loaded families only, walls + loaded families WITHOUT placement (all
      certified shapes), or instances on a host that is NOT our composed
      base (our famdocs + instances on a pristine Revit host PASS -- T1r /
      T1u / U16; the artifact itself stays PROOF-ONLY via the status gate).

    ``composed_base`` defaults to True: a caller that cannot vouch for the
    host's lineage gets the conservative label (a stamp never withholds).
    ``loaded_tags``: None at plan time (every buildable plan is assumed to
    load); after the L stage pass the tags that actually loaded and the
    verdict follows the load result (nothing loaded -> nothing placed).
    """
    n_walls = len(model.room.walls) if model.room else 0
    n_fam = (len(buildable_family_plans(model)) if loaded_tags is None
             else len(set(loaded_tags)))
    has_w, has_f = n_walls > 0, n_fam > 0
    n_inst = (planned_instances(model, loaded_tags)
              if ("L" in stages and "E" in stages) else 0)
    builds_w = has_w and "W" in stages          # walls the job will actually create
    common = dict(has_walls=has_w, n_walls=n_walls, has_loaded_families=has_f,
                  n_loaded_families=n_fam, n_instances=n_inst,
                  composed_base=bool(composed_base))
    if n_inst > 0 and composed_base:
        shell_what = (f"the {n_walls} walls + the {n_fam} loaded families, NO placement "
                      "-- the WF_fix-certified shape" if builds_w
                      else f"the {n_fam} loaded families, NO placement -- the "
                           "certified load shape")
        if strict:
            v = CombinationVerdict(
                **common, triggers_open_bug=True, mode="split-strict",
                stamp=None, files=["shell", "equipment"],
                reason=(f"--strict: {_CELL_WHY}, so the job is emitted as TWO coordinated "
                        f"files -- 'shell' ({shell_what}) and 'equipment' (the loaded "
                        f"families + their {n_inst} PLACED instances = the open cell, "
                        "isolated). Both files are delivered; only 'equipment' carries the "
                        "unverified cell."))
            v.notes.append("both files are grown on the SAME base with the SAME intent and "
                           "coordinate frame; link both into one Revit project / open side by "
                           "side. When the open cell closes (issue #16) the front door will "
                           "emit one file again (drop --strict then).")
        else:
            v = CombinationVerdict(
                **common, triggers_open_bug=True, mode="stamp-proof-only",
                stamp=OPEN_CELL_STAMP, files=["combined"],
                reason=("default: ONE combined file ("
                        + (f"the {n_walls} walls + " if builds_w else "")
                        + f"the {n_fam} loaded families + their {n_inst} PLACED instances) is "
                        f"emitted and DELIVERED, and the manifest is STAMPED '{OPEN_CELL_STAMP}' "
                        f"-- {_CELL_WHY}. Pass --strict to get the certified shell and the "
                        "instances as two coordinated files instead."))
            v.notes.append("the stamp is a LABEL, not refusal logic: the file is delivered and "
                           "its own self-checks (validator / registries / identity) still run; "
                           "the stamp only refuses to represent the open cell as accepted.")
        return v
    # not the open cell -> a single file of a certified shape (or a foreign host)
    if n_inst > 0:
        what = (f"{n_inst} instances of our generated families placed on a host that is NOT "
                "the composed genesis base: our famdocs + instances on a pristine Revit host "
                "are a certified cell (T1r / T1u / U16); this artifact itself is unverified "
                "and rides the status gate's PROOF-ONLY label")
    elif builds_w and has_f and "L" in stages:
        what = (f"{n_walls} walls + {n_fam} loaded families WITHOUT placement -- the "
                "WF_fix / WF_nofix certified shape (genesis-audit #27); the old "
                "'walls+families combination' suspicion is exonerated")
    elif builds_w:
        what = "walls only (viewer-certified shape: room shell on the genesis base)"
    elif has_f and "L" in stages:
        what = ("loaded families only, no placement (viewer-certified shape: family load "
                "on the genesis lineage)")
    else:
        what = "no walls and no loadable families (nothing model-side to author)"
    return CombinationVerdict(
        **common, triggers_open_bug=False, mode="single",
        stamp=None, files=["combined"],
        reason=f"open cell not exercised by this job: {what}")


# ---------------------------------------------------------------------------
# convenience: read a persisted intent JSON back (summary use only)
# ---------------------------------------------------------------------------

def load_intent_json(path: str) -> Dict[str, Any]:  # pragma: no cover - trivial
    with open(path) as fh:
        return json.load(fh)
