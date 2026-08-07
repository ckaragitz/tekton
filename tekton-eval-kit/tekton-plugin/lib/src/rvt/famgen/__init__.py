"""rvt.famgen -- generating Revit FAMILY documents (.rfa / embedded content
documents) from OUR OWN expression, field by field from parameters.

Sub-modules:

* :mod:`rvt.famgen.skeleton` -- the FAMILY-DOCUMENT SKELETON: everything a
  family document must contain BEFORE any authored geometry -- the
  self-``Family`` element (category, type table, family parameters), the
  Reference Level, the origin reference planes, the family's own units and
  object-style copies, the parameter machinery (``ParamElemFamily``), the
  MEP connector (``ConnectorElem`` + ``ConnectorElemDomainElectrical``) and
  the two delivery forms (standalone ``.rfa`` / embedded save unit).

Design principle (same as ``rvt.genesis``): NO cloned third-party geometry
or content -- every object is constructed field by field from plain
parameter values (dimensions, ratings, names).  Manufacturer dimensions /
ratings are FACTS; the geometry and the parameters are OURS.

See docs/writer/family-skeleton.md (the family-document field map) and
docs/writer/family-authoring.md (the reconnaissance the map was built on).
"""

__all__ = ["skeleton"]

# NOTE: kept a near-bare stub on purpose -- a sibling workstream may also
# add modules under rvt.famgen; nothing is imported eagerly here.

