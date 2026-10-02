"""mep_connectors -- connectors of the non-electrical MEP domains on generated families (#894).

Our writer authored POWER connectors only (``skeleton.new_electrical_connector``).
A generated fan coil's conduit hub, a junction box's knockouts or a wireway's ends
then carried no connector a user could route conduit to.  This module adds the
CONDUIT connector, learned from born specimens before it is authored (steer #913),
never guessed.

WHAT THE CORPUS PINS (the owner's reference library, 421 families read inside their
own releases; counts only, the corpus stays quarantined -- hard rule 3, rule 6):

* 392 ``ConnectorElemDomainCableTrayConduit`` connectors in 166 families.  Every
  one has ``m_eSystemType`` 32; ``m_eProfileType`` 0 (round, 267) or 1 (rectangular,
  125); ``m_ePlacementType`` 0 (387 of 392).  A round one keeps width = height = 1.0.
* ONE PRIMARY PER DOMAIN, the others pointing at it: the 166 primaries carry
  ``m_idPrimaryElem`` = their own id; all 226 non-primaries carry the domain's primary
  conduit connector there and list it in their header's deletion parents (a law of the
  conduit domain: the corpus's non-primary power connectors point at themselves).
  Every corpus connector is in a 2025 file, so release state cannot be split from
  regeneration state; what the corpus shows is that the shell does not depend on
  the domain.
* ``m_dConnectorDiameter`` stores the DIAMETER: where it is bound to a family
  parameter through the diameter property (-1133415) the two are equal (90 / 90);
  through the radius property (-1133401) the stored value is twice the parameter
  (104 / 104).
* The connector SHELL is the one our power connectors already carry: the same
  element class and category (-2007000 for every domain), face reference, edge
  loop and ``FamilyParametrizedElemParamsCell`` associations.  The geometry-step
  fields that differ from our power connector differ identically on the corpus's
  own power connectors, so they are not domain state.

So a conduit connector is the verified power-connector shell with this domain.
Piping (hydronic) and duct connectors are NOT authored here: the corpus holds no
hydronic or duct specimen whose system is known (its 9 piping-domain connectors sit
on conduit fittings), and a system classification is never guessed (#894).

"Conduit routes to it in Revit" is a desktop claim (hard rule 4).
"""
from __future__ import annotations

from typing import Any, Optional, Sequence

#: every born conduit / cable-tray connector's system type (392 / 392)
CONDUIT_SYSTEM_TYPE = 32
PROFILE_ROUND, PROFILE_RECTANGULAR = 0, 1
#: the connector property a family parameter drives: the diameter (the stored
#: diameter equals the parameter) -- and the radius (stored = 2 x parameter)
ELEM_PROP_CONDUIT_DIAMETER = -1133415
ELEM_PROP_CONDUIT_RADIUS = -1133401
DOMAIN_CLASS = "ConnectorElemDomainCableTrayConduit"


def conduit_domain(diameter_ft: float, *, primary: bool = True, description: str = "") -> dict:
    """The ``ConnectorElemDomainCableTrayConduit`` value of a ROUND conduit connector."""
    from ..genesis import types as GT
    if not (float(diameter_ft) > 0):
        raise ValueError(f"conduit diameter must be positive, got {diameter_ft!r}")
    d = GT.blank_object(DOMAIN_CLASS)
    d.update({
        "m_pConnElem": {"weakref": 2},
        "m_dConnectorWidth": 1.0, "m_dConnectorHeight": 1.0,
        "m_dConnectorDiameter": float(diameter_ft),
        "m_dConnectorAngle": 0.0,
        "m_eSystemType": CONDUIT_SYSTEM_TYPE,
        "m_ePlacementType": 0,
        "m_eProfileType": PROFILE_ROUND,
        "m_nConnectorReferenceIndex": -1,
        "m_bIsPrimaryConnector": bool(primary),
        "m_bConnectorUtilityParam": False,
        "m_strConnectorDescription": str(description),
    })
    return d


def add_conduit_connector(doc, *, host: Any, face: str, location: Sequence[float],
                          direction: Sequence[float], u_axis: Sequence[float],
                          diameter_ft: float, bind_diameter_param: Optional[str] = None,
                          primary: Optional[bool] = None, description: str = "Conduit"):
    """Add a ROUND conduit connector on a named face of ``host`` (a box form, as
    :func:`rvt.famgen.factory.add_connector`).  ``bind_diameter_param`` = a length
    family parameter that drives the connector's diameter.  ``primary`` None = the
    family's first conduit connector is the primary one of its domain.  Conduit
    connectors are kept in ``doc.mep_connectors`` (``doc.connectors`` holds the
    power connectors, whose primary flag lives under another field name)."""
    from . import factory as F
    from . import skeleton as SK
    if doc.finalized:
        raise F.FactoryError("document is finalized; add connectors before finalize")
    ext = host.by_class("ExtrusionElem")
    if not ext or len(host.params.get("vertices") or ()) != 4:
        raise F.FactoryError("a conduit connector is hosted on a box form's face")
    mep = getattr(doc, "mep_connectors", None)
    if mep is None:
        mep = doc.mep_connectors = []
    prim = next((c for c in mep if c.obj["m_pDomain"]["value"]["m_bIsPrimaryConnector"]), None)
    if primary is None:
        primary = prim is None
    if primary and prim is not None:
        raise F.FactoryError("the family already has a primary conduit connector (one per domain)")
    if not primary and prim is None:
        raise F.FactoryError("a non-primary conduit connector points at its domain's primary: "
                             "add the primary one first")
    fx = F.box_face(face)
    bindings = []
    if bind_diameter_param:
        bindings.append((doc._param_key(bind_diameter_param), ELEM_PROP_CONDUIT_DIAMETER))
    con = SK.new_electrical_connector(
        SK._alloc(doc.ids), doc.self_family.elem_id,
        host_element_id=ext[0].elem_id, host_geom_tag=int(fx["tag"]),
        location=tuple(float(c) for c in location),
        direction=tuple(float(c) for c in direction),
        u_axis=tuple(float(c) for c in u_axis),
        load_class_id=-1, description=str(description), primary=False,
        edge_loop_tags=list(fx["edges"]), param_bindings=bindings,
        index=len(doc.connectors) + len(mep) + 1)
    con.obj["m_pDomain"] = {"ptr_class": DOMAIN_CLASS, "pid": -1,
                            "value": conduit_domain(diameter_ft, primary=bool(primary),
                                                    description=description)}
    if not primary:
        # the corpus law: a non-primary conduit connector points at its domain's
        # primary and depends on it (226 / 226)
        con.obj["m_idPrimaryElem"] = int(prim.elem_id)
        dele = con.header["m_parents"]["value"]["m_deletion"]
        dele.append(int(prim.elem_id))
        dele.sort()
    con.notes[:] = [f"conduit connector (#894), {diameter_ft * 12:g} in, on the {face} face "
                    f"(tag {fx['tag']}); domain pinned from the corpus, seq103=SerializedDummy"]
    con.refs["domain"] = "conduit"
    mep.append(con)
    doc.add(con)
    return con
