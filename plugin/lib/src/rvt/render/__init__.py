"""rvt.render -- the RENDER lens: does an element carry BAKED (viewer-drawable)
geometry, or only a definition the desktop application regenerates?

The archaeology behind this package (``docs/writer/baked-geometry.md``)
established that a Revit-saved element's drawable geometry lives in its
``Partitions/<N>`` **seq-103 record** (the "rep" stream): a ``GElement``
(class 0x89e) whose sub-nodes form a B-rep (``Geometry`` = ``GBRep`` with
``Face`` / ``Edge`` / ``EdgeLoop`` + analytic surfaces), symbolic curves
(``GLine``/``GArc``) or an instance reference (``GInstance`` -> the
symbol's rep).  A ``SerializedDummy`` (class 0xf2c) rep carries NOTHING to
draw -- Autodesk's cloud viewer / extractor does not regenerate, so a
dummy-rep 3D element loads but is invisible ("Design is empty").

Sub-modules:

* :mod:`rvt.render.inspect` -- the geometry-carriage inspector: for any
  file, per element ``{class, kind, has_baked_geometry, geometry byte count,
  solids/faces/edges/curves, storage location}``, with a CLI and JSON dump.
  This is the diagnostic the RENDER gate uses beside the LOAD gate.
"""

__all__ = ["inspect"]

# import-free on purpose: nothing is imported eagerly (corpus / schema
# access happens only inside rvt.render.inspect).
