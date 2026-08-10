"""rvt.convert.param_carrier -- which field of a family type-table row
carries a parameter's live value: ``m_value`` (doubles, Revit internal
units), ``m_int`` (integers) or ``m_str`` (text).

The carrier follows the parameter DEFINITION'S STORAGE CLASS first -- the
pointer class the file's own schema resolves for ``m_pParamDef``
(``ParamDefString`` -> ``m_str``, ``ParamDefInt`` -> ``m_int``; under the
#333/#336 storage-class law those two carry NO ``m_specTypeId``) -- and the
``m_specTypeId`` of a ``ParamDefValue`` otherwise (pre-law files typed
strings / integers as ``spec.string`` / ``spec.int64``).

ONE rule for both readers -- :mod:`rvt.convert.modify_family` (family-edit
inventory, #354) and :mod:`rvt.convert.rvt_to_ifc` (the tagging contract an
rvt -> ifc export writes, #355).  A leaf on purpose: no imports.
"""
from __future__ import annotations

__all__ = ["carrier_for_param"]


def carrier_for_param(def_class: str, spec: str) -> str:
    """Storage class first (the schema-resolved pointer class name of the
    parameter definition), the spec of a ``ParamDefValue`` otherwise."""
    if def_class == "ParamDefString" or "spec.string" in spec:
        return "m_str"
    if def_class == "ParamDefInt" or "spec.int64" in spec:
        return "m_int"
    return "m_value"
