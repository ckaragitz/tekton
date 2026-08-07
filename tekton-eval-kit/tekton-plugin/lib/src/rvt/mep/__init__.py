"""rvt.mep — MEP / electrical CRUD modules built on the rvt writer core.

Each submodule owns one element category and works against a
:class:`rvt.mutate.Document` (create) or its :mod:`rvt.manipulate` edit
session (modify / delete):

* ``electrical_data`` — wiring (``RbsWireCurve`` home runs / branch wires),
  the electrical-settings elements (voltage types, distribution systems,
  wire types / materials / insulation, demand factors, load
  classifications, ``ElectricalSetting``) and panelboard circuit data
  (circuit numbering / slot layout).

The core writer modules (``mutate``, ``commit``, ``manipulate``) are never
edited by these; a combined create+edit commit lives here
(``electrical_data.commit_electrical``).
"""
