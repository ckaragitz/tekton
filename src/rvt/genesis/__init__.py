"""rvt.genesis — synthesizing a .rvt from OUR OWN expression (no Autodesk content).

Sub-modules:

* :mod:`rvt.genesis.types` — pure CONSTRUCTORS for system-family types and
  document-standard elements (wall/floor/roof/ceiling types, conduit / cable-
  tray / wire types, voltage & distribution-system definitions, load
  classifications + demand factors, materials, line & fill patterns, text
  types, object styles).  Every constructor takes PLAIN PARAMETERS (mm,
  volts, names, RGB) and emits a COMPLETE, schema-valid object built field by
  field from the archive class map — never a cloned Autodesk payload.

See docs/writer/genesis-types.md for the field-by-field definition maps and
docs/writer/genesis.md for the overall genesis plan.
"""
from . import types  # noqa: F401
from .types import (  # noqa: F401
    TypeRecord, GenesisCatalog, IdSource, blank_object, element_header,
    new_wall_type, new_floor_type, new_roof_type, new_ceiling_type,
    new_material, new_line_pattern, new_fill_pattern,
    new_voltage_type, new_distribution_system,
    new_conduit_standard, new_conduit_type, conduit_sizes_element,
    new_cable_tray_type, cable_tray_sizes_element,
    new_wire_material_type, new_wire_insulation_type,
    new_wire_temperature_rating_type, new_wire_type,
    new_conductor_material, new_conductor_temperature_rating,
    new_conductor_insulation, new_conductor_size,
    new_demand_factor, new_load_class, electrical_setting,
    new_text_type, new_category, new_gstyle, default_object_styles,
)
