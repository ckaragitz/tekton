"""rvt.convert -- COMBINATION-INPUT routes: creating INTO existing files.

The permutation mandate says any of {prompt, IFC, RVT, RFA, spec-JSON} may
arrive alone or COMBINED.  This package holds the combination routes that
take an EXISTING file as one input and author INTO it, composing the
already-certified stages (nothing here re-implements a stage):

* :mod:`rvt.convert.add_to_project`  -- prompt + RVT -> RVT ("add a 100 A
  lighting panel to my project"): the prompt route's intent
  (rvt.frontdoor.prompt_intent) retargeted onto the USER'S file (its
  release, its levels, its walls, its free floor space), families generated
  zero-donor (rvt.famgen.factory -> bundled-base container), loaded by the
  four-registry component loader (rvt.famgen.loader via tools/ifc_intent
  stage_load), instances placed by rvt.mutate through the certified
  clone-template path with CONSTRUCTED specimens
  (rvt.frontdoor.standalone.ConstructedSpecimens built against the target).
* :mod:`rvt.convert.merge_ifc`       -- IFC + RVT -> RVT (merge): the IFC
  resolved to the placement-true intent (rvt.ifc.intent), translated by a
  disjoint offset so nothing collides, then the SAME build-into-target
  pipeline (walls appended, families loaded + placed).
* :mod:`rvt.convert.modify_family`   -- prompt + RFA -> RFA: natural-language
  family edits ("rename the type to X; set BusRating 225") applied through
  rvt.manipulate's certified modify path on the family document's records,
  with the PartAtom metadata kept in step.

Territory: ``src/rvt/convert/`` (convert-B stream).  Everything imported,
nothing edited: rvt.frontdoor.{prompt_intent,intent,standalone,build},
tools/ifc_intent.py (as a module), rvt.{mutate,manipulate,commit,famload,
famgen,versions,validate,inventory,families}.

The EXPORT / EXTRACT directions live beside the combination routes
(convert-a stream, same composition rules -- see each module's docstring):

* :mod:`rvt.convert.rvt_to_ifc`      -- RVT -> intent -> IFC4 (readback via
  rvt.mutate/inventory/families, emission via rvt.frontdoor.ifc_out;
  round-trip through rvt.ifc.intent is the acceptance).
* :mod:`rvt.convert.extract_family`  -- RVT -> RFA: one embedded family
  document lifted into a standalone .rfa (records verbatim, scaffolding
  re-authored via rvt.convert.rfa_assemble); the full cycle re-loads the
  extracted .rfa through rvt.famgen.loader.
* :mod:`rvt.convert.edit_family`     -- RFA + structured ops -> RFA (the
  deterministic ops surface over modify_family's certified edit engine).
"""
from __future__ import annotations

__all__ = ["add_to_project", "merge_ifc", "modify_family",
           "rvt_to_ifc", "extract_family", "edit_family", "rfa_assemble"]
