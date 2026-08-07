"""rvt.ifc -- IFC (ISO 16739 / IFC4) as a FIRST-CLASS INPUT to family and
project genesis.

The KNOWLEDGE.md workflow decision: Claude Design authors the model and
emits IFC; this project is the BRIDGE that turns Design-authored IFC into
Revit-native, editable content.  ``tools/ifc_to_spec.py`` is the original
PROJECT-side front door (storeys -> levels, IfcWall -> walls, electrical
proxies -> equipment placements); the modules here deepen both the project
and the family side.  Every input IFC is OUR OWN authoring (Claude-Design /
three-d-stage IFC writer) -- provenance = ours; values read from it are
catalog-flag ``fact`` (source = the IFC file itself).

Sub-modules (added by separate workstreams; each names its own territory):

* :mod:`rvt.ifc.product_facts` -- (ifc-family stream) extract a
  PRODUCT-FACTS record from an IFC product: typed Pset values, overall +
  per-mesh bounding boxes in feet, surface colours -- in the
  ``rvt.famgen.catalog`` facts-store schema.
* :mod:`rvt.ifc.famfrom_ifc` -- (ifc-family stream) compose OUR family
  document from those facts (the recessed-downlight variant of the luminaire
  archetype, form clusters + parameters authored field-by-field by the
  ``rvt.famgen`` constructors -- never a DirectShape blob, never copied
  third-party bytes), emit the standalone ``.rfa`` through the assay-clean
  family path (``rvt.famgen.famdoc_adoc``), and LOAD it into a certified
  project base through the four-registry loader (``rvt.famload``).
* :mod:`rvt.ifc.intent` -- (a sibling stream) resolve an authored IFC into
  a placement-true, family-mapped INTENT for the project side (composed
  placement chains, geometry-recovered insertion points, the
  tagging-contract mapping).
"""

__all__ = ["product_facts", "famfrom_ifc", "intent"]

# NOTE: kept import-free on purpose -- sibling workstreams add modules
# under rvt.ifc (nothing is imported eagerly here; ifcopenshell / numpy are
# needed only by the modules that read IFC geometry, and the family
# composer can run from a JSON facts record without them).
