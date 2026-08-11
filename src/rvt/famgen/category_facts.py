"""category_facts -- family CATEGORY and PART TYPE, mined from Revit's own
default ``.rft`` family templates (issue #516).

WHY THIS EXISTS.  ``skeleton._resolve_category`` maps a friendly key
("panelboard", "casework") to a built-in category id.  Five of those ids
were desktop-verified in use; the wider set added for issue #498 came from
Revit's *published* BuiltInCategory list and was marked ``[INFERRED]`` --
nobody had confirmed that a family carrying each id lands in the expected
branch of Revit's category list.  Issue #516 was therefore gated
``needs-revit-desktop``.

WHAT REMOVED THE GATE.  Revit's default family-template set (the ``.rft``
files a user picks in *New > Family*) is Autodesk's own statement of the
answer: a template named for a category *is* a family document of that
category, and its self-``Family.m_categoryId`` is the id Revit itself
assigns.  That is the same fact the Family Category and Parameters dialog
would have shown, read out of the format instead of a screenshot -- and it
is stronger, because it is the value Revit wrote rather than a label it
rendered.

WHAT IS AND IS NOT PROVEN.  The id below is the id Revit uses for a family
of that kind: VERIFIED.  It does NOT follow that a family *we* author with
that id lands in the expected Project Browser branch -- that remains a
Revit-side observation (hard rule 4: our reading of a template is not
Autodesk's reader accepting our output).  ``BROWSER_PLACEMENT_UNVERIFIED``
records that distinction so no caller mistakes one for the other.

PROVENANCE / RULE 3.  These are *laws mined from* Autodesk files, never
donor bytes: a category id is an interface constant (Autodesk publishes the
BuiltInCategory enumeration), and the template files themselves stay in the
git-ignored quarantine (``samples/rft/``, ``vendor/``).  Nothing here is
copied content -- it is three integers and a boolean per family kind, plus
the template's file name as the citation.  ``tools/sync_plugin.py``'s
deny-audit sees only this module.

MINED 2026-08-11 from the 82-file default template set (Revit 2026), each
row read as ``load_rft_elements(...)`` self-Family ``m_categoryId`` /
``m_partType`` / ``m_isWorkPlaneBased``.  Re-mine with
``tools/rft_facts.py mine``.
"""
from __future__ import annotations

from typing import Dict, List, NamedTuple, Optional, Tuple

#: The template set is authoritative for the CATEGORY ID a family of a given
#: kind carries.  It says nothing about where OUR family appears in the
#: Project Browser -- that needs Revit (issue #516 DONE 2 / hard rule 4).
BROWSER_PLACEMENT_UNVERIFIED = (
    "a template proves the category id Revit uses for that family kind; it "
    "does not prove a family we author with that id lands in the expected "
    "branch of Revit's category list -- that is a Revit-side observation")


class CatFact(NamedTuple):
    """One mined row.  ``template`` is the citation (a file NAME, never
    content); ``part_type`` and ``work_plane_based`` are that template's
    self-Family values."""
    category: int
    part_type: int
    work_plane_based: bool
    template: str

    @property
    def verified(self) -> bool:
        return True


#: VERIFIED rows -- one per default template, keyed by the template's family
#: kind.  Where several templates share a kind (hosted / wall-based / etc.)
#: the FREE-STANDING one is the row and the variants are listed in
#: :data:`HOST_VARIANTS`, because hosting changes ``work_plane_based`` but
#: never the category.
CATEGORY_FACTS: Dict[str, CatFact] = {
    # -- architectural ----------------------------------------------------
    "baluster":                CatFact(-2000127,  -1, False, "Baluster.rft"),
    "casework":                CatFact(-2001000,   0, False, "Casework.rft"),
    "column":                  CatFact(-2000100,  -1, False, "Column.rft"),
    "curtain_wall_panel":      CatFact(-2000170,  -1, False, "Curtain_Wall_Panel.rft"),
    "detail_item":             CatFact(-2002000,  -1, False, "Detail_Item.rft"),
    "division_profile":        CatFact(-2008165,  -1, False, "Division_Profile.rft"),
    "door":                    CatFact(-2000023,  -1, False, "Door.rft"),
    "entourage":               CatFact(-2001370,  -1, False, "Entourage.rft"),
    "furniture":               CatFact(-2000080,   0, False, "Furniture.rft"),
    "furniture_system":        CatFact(-2001100,   0, False, "Furniture_System.rft"),
    "generic_model":           CatFact(-2000151,   0, False, "Generic_Model.rft"),
    "parking":                 CatFact(-2001180,  -1, False, "Parking.rft"),
    "planting":                CatFact(-2001360,  -1, False, "Planting.rft"),
    "profile":                 CatFact(-2003000,  -1, False, "Profile.rft"),
    "railing_support":         CatFact(-2000948,  -1, False, "Railing_Support.rft"),
    "railing_termination":     CatFact(-2000949,  -1, False, "Railing_Termination.rft"),
    "site":                    CatFact(-2001260,   0, False, "Site.rft"),
    "specialty_equipment":     CatFact(-2001350,   0, False, "Specialty_Equipment.rft"),
    "window":                  CatFact(-2000014,  -1, False, "Window.rft"),
    # -- electrical -------------------------------------------------------
    "electrical_equipment":    CatFact(-2001040,  14, False, "Electrical_Equipment.rft"),
    "electrical_fixture":      CatFact(-2001060,   0, False, "Electrical_Fixture.rft"),
    "lighting_fixture":        CatFact(-2001120,   0, False, "Lighting_Fixture.rft"),
    "data_panel":              CatFact(-2001040,  17, True,  "Data_Panel.rft"),
    # -- low-voltage / systems devices ------------------------------------
    "data_device":             CatFact(-2008083,   0, False, "Data_Device.rft"),
    "fire_alarm_device":       CatFact(-2008085,   0, False, "Fire_Alarm_Device.rft"),
    "telephone_device":        CatFact(-2008075,   0, False, "Telephone_Device.rft"),
    # -- mechanical / plumbing --------------------------------------------
    "mechanical_equipment":    CatFact(-2001140,   0, False, "Mechanical_Equipment.rft"),
    "plumbing_fixture":        CatFact(-2001160,   0, False, "Plumbing_Fixture.rft"),
    # -- duct fittings: ONE category, the part type is the fitting kind ----
    "duct_elbow":              CatFact(-2008010,   5, False, "Duct_Elbow.rft"),
    "duct_tee":                CatFact(-2008010,   6, False, "Duct_Tee.rft"),
    "duct_transition":         CatFact(-2008010,   7, False, "Duct_Transition.rft"),
    "duct_cross":              CatFact(-2008010,   8, False, "Duct_Cross.rft"),
    # -- structural --------------------------------------------------------
    "structural_column":       CatFact(-2001330,  -1, False, "Structural_Column.rft"),
    "structural_foundation":   CatFact(-2001300,  -1, False, "Structural_Foundation.rft"),
    "structural_framing":      CatFact(-2001320,  -1, False,
                                       "Structural_Framing__Beams_and_Braces.rft"),
    "structural_stiffener":    CatFact(-2001354,  -1, False, "Structural_Stiffener.rft"),
    "structural_truss":        CatFact(-2009600,  -1, False, "Structural_Trusses.rft"),
    # -- rebar -------------------------------------------------------------
    "rebar_coupler":           CatFact(-2009060,  -1, False, "Rebar_Coupler_Template.rft"),
    "rebar_shape":             CatFact(-2009013,  -1, False, "Rebar_Shape_Template.rft"),
}

#: Host variants that share a kind's category.  ``True`` = that template's
#: ``m_isWorkPlaneBased``; note only the *face*-hosted flavours set it --
#: wall/ceiling/floor/roof-based templates carry False and host through a
#: different mechanism.  [VERIFIED per template.]
HOST_VARIANTS: Dict[str, Tuple[Tuple[str, bool], ...]] = {
    "casework":            (("Casework_wall_based.rft", False),),
    "data_device":         (("Data_Device_Hosted.rft", True),),
    "electrical_fixture":  (("Electrical_Fixture_ceiling_based.rft", False),
                            ("Electrical_Fixture_wall_based.rft", False)),
    "fire_alarm_device":   (("Fire_Alarm_Device_Hosted.rft", True),),
    "generic_model":       (("Generic_Model_ceiling_based.rft", False),
                            ("Generic_Model_face_based.rft", True),
                            ("Generic_Model_floor_based.rft", False),
                            ("Generic_Model_line_based.rft", False),
                            ("Generic_Model_roof_based.rft", False),
                            ("Generic_Model_two_level_based.rft", False),
                            ("Generic_Model_wall_based.rft", False)),
    "lighting_fixture":    (("Lighting_Fixture_ceiling_based.rft", False),
                            ("Lighting_Fixture_wall_based.rft", False),
                            ("Linear_Lighting_Fixture.rft", False),
                            ("Spot_Lighting_Fixture.rft", False)),
    "mechanical_equipment": (("Mechanical_Equipment_ceiling_based.rft", False),
                             ("Mechanical_Equipment_wall_based.rft", False)),
    "plumbing_fixture":    (("Plumbing_Fixture_wall_based.rft", False),),
    "specialty_equipment": (("Specialty_Equipment_wall_based.rft", False),),
    "structural_stiffener": (("Structural_Stiffener_Line_Based.rft", False),),
    "telephone_device":    (("Telephone_Device_Hosted.rft", True),),
}

#: Corrections this round made to ``skeleton._resolve_category``'s
#: ``[INFERRED]`` block -- kept as data so the record, the tests and the
#: skills cite one source.  ``was`` is what shipped before #516; ``now`` is
#: the corrected id; ``evidence`` names the tier (see the module docstring
#: and the resolver's comment):
#:
#:   "rft"  the category's own default family template  (strongest)
#:   "inv"  rvt.inventory.BUILTIN_CATEGORIES_VERIFIED -- a real sample
#:          ELEMENT carries the id
#:   "inv?" rvt.inventory.BUILTIN_CATEGORIES_ASSUMED -- a public constant no
#:          sample exercises, adopted ONLY because ``was`` is demonstrably
#:          another category.  Still [INFERRED]; it is a strict improvement
#:          on a known-wrong value, not a verification.
#:
#: EVERY row here silently produced the WRONG KIND OF FAMILY before.
CORRECTIONS: Tuple[Dict[str, object], ...] = (
    {"key": "casework", "was": -2000079, "now": -2001000, "evidence": "rft",
     "source": "Casework.rft",
     "note": "-2000079 is Room Separation (residue_a.PARENT_LABELS)"},
    {"key": "fire_alarm_device", "was": -2008013, "now": -2008085,
     "evidence": "rft", "source": "Fire_Alarm_Device.rft",
     "note": "-2008013 is OST_DuctTerminal / Air Terminals (inventory, "
             "VERIFIED by 'M_Supply Diffuser'): asking for a fire-alarm "
             "device built an air terminal"},
    {"key": "telephone_device", "was": -2008086, "now": -2008075,
     "evidence": "rft", "source": "Telephone_Device.rft",
     "note": "-2008086 was the guess; the template carries -2008075"},
    {"key": "security_device", "was": -2008085, "now": -2008079,
     "evidence": "inv?", "source": "inventory OST_SecurityDevices",
     "note": "COLLISION: -2008085 is Fire Alarm Devices by its own "
             "template, so this built fire-alarm families. -2008079 is the "
             "public OST_SecurityDevices constant and stays [INFERRED] -- "
             "no default template declares a security-device category."},
    {"key": "lighting_device", "was": -2008080, "now": -2008087,
     "evidence": "inv", "source": "inventory OST_LightingDevices",
     "note": "corroborated by a real 'Single Pole' switch element"},
    {"key": "cable_tray_fitting", "was": -2008131, "now": -2008126,
     "evidence": "inv", "source": "inventory OST_CableTrayFitting",
     "note": "corroborated by a real 'Channel Horizontal Bend' element"},
    {"key": "conduit_fitting", "was": -2008133, "now": -2008128,
     "evidence": "inv", "source": "inventory OST_ConduitFitting",
     "note": "corroborated by a real 'Conduit Body - Type L' element"},
    {"key": "communication_device", "was": -2008012, "now": -2008077,
     "evidence": "inv?", "source": "inventory OST_CommunicationDevices",
     "note": "-2008012 appears in no in-repo table; -2008077 is the public "
             "constant and stays [INFERRED]"},
)

#: Keys this round could NOT settle: no default template declares them and
#: no sample element carries them.  They stay [INFERRED] and say so.
#: Re-guessing them is how #516 happened; an explicit integer OST id always
#: passes straight through ``_resolve_category``.
STILL_INFERRED: Tuple[str, ...] = (
    "pipe_accessory", "duct_accessory", "cable_tray", "conduit",
    "communication_device", "nurse_call_device", "security_device",
)

#: A conflict this round exposed and did NOT resolve.  ``inventory``'s
#: ASSUMED block reads the low-voltage device band as Communication -2008077
#: / Security -2008079 / Fire Alarm -2008081 / Data -2008083 / Nurse Call
#: -2008085.  The templates agree on Data (-2008083) but put FIRE ALARM at
#: -2008085 (where inventory assumes Nurse Call) and TELEPHONE at -2008075.
#: So the assumed band is offset somewhere, and ``nurse_call_device``
#: (-2008084) rests on it.  Settling it needs a nurse-call/security template
#: or a sample element -- not another guess.
INVENTORY_ASSUMED_BAND_CONFLICT = (
    "inventory assumes -2008085 = OST_NurseCallDevices, but "
    "Fire_Alarm_Device.rft carries -2008085; the assumed low-voltage band is "
    "offset and nurse_call_device / security_device rest on it")


def fact(kind: str) -> Optional[CatFact]:
    """The mined row for ``kind``, or None when no default template
    declares it (see :data:`STILL_INFERRED`)."""
    return CATEGORY_FACTS.get(str(kind).lower().replace(" ", "_"))


def category_of(kind: str) -> Optional[int]:
    f = fact(kind)
    return None if f is None else f.category


def part_type_of(kind: str) -> Optional[int]:
    f = fact(kind)
    return None if f is None else f.part_type


def verified_keys() -> Tuple[str, ...]:
    return tuple(sorted(CATEGORY_FACTS))


def check_facts() -> List[str]:
    """Self-consistency gate (the provenance discipline ``standards.py``
    uses): every row must cite a template, carry a built-in (negative)
    category id and a part type in the observed enumeration, and no key may
    be both verified and listed as still-inferred.  Returns complaints;
    empty means clean."""
    bad: List[str] = []
    for key, f in sorted(CATEGORY_FACTS.items()):
        if not f.template.endswith(".rft"):
            bad.append(f"{key}: template citation {f.template!r} is not a .rft")
        if not isinstance(f.category, int) or f.category >= 0:
            bad.append(f"{key}: category {f.category!r} is not a built-in "
                       f"(negative) id")
        if f.part_type not in (-1, 0, 5, 6, 7, 8, 14, 17):
            bad.append(f"{key}: part type {f.part_type} is outside the "
                       f"enumeration measured on the template set")
        if not isinstance(f.work_plane_based, bool):
            bad.append(f"{key}: work_plane_based {f.work_plane_based!r} "
                       f"is not a bool")
    for key in STILL_INFERRED:
        if key in CATEGORY_FACTS:
            bad.append(f"{key}: listed STILL_INFERRED but also verified")
    for c in CORRECTIONS:
        key, now, ev = str(c["key"]), c["now"], str(c.get("evidence"))
        if ev not in ("rft", "inv", "inv?"):
            bad.append(f"{key}: evidence tier {ev!r} is not one of "
                       f"rft / inv / inv?")
        if c["was"] == now:
            bad.append(f"{key}: CORRECTIONS row does not correct anything "
                       f"(was == now == {now})")
        if ev == "rft":
            # a template-tier correction must be backed by a row in the
            # mined table, citing the template the row names
            got = category_of(key)
            if got != now:
                bad.append(f"{key}: CORRECTIONS says {now} but the mined "
                           f"table says {got}")
            f = fact(key)
            if f is not None and f.template != c.get("source"):
                bad.append(f"{key}: CORRECTIONS cites {c.get('source')!r} but "
                           f"the mined row cites {f.template!r}")
        elif key in CATEGORY_FACTS:
            bad.append(f"{key}: corrected on the {ev!r} tier but also present "
                       f"in the template-mined table -- use the rft tier")
    for key, variants in sorted(HOST_VARIANTS.items()):
        if key not in CATEGORY_FACTS:
            bad.append(f"{key}: HOST_VARIANTS names a kind with no fact row")
        for name, wpb in variants:
            if not name.endswith(".rft"):
                bad.append(f"{key}: variant citation {name!r} is not a .rft")
            if not isinstance(wpb, bool):
                bad.append(f"{key}/{name}: work_plane_based is not a bool")
    return bad
