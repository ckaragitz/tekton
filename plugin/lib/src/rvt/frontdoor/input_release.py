"""rvt.frontdoor.input_release -- classify the ERA of an ``--rvt`` INPUT
before anything opens it (issue #176).

The ``--rvt --edit`` route edits the user's own file, so the first honest
question is not "which release do you want" but "which release IS this, and
has tekton ever read one".  Every job answers it up front from the two cheap
signals the container carries -- the ``BasicFileInfo`` era markers
(:func:`rvt.meta.classify_bfi_era`, layout-independent) and, failing a year
there, the ``Formats/Latest`` signature -- and lands in exactly one of:

* ``known``      -- the year is in ``rvt.versions.KNOWN_RELEASES``: the job
                    proceeds exactly as before (no schema parse added).
* ``unverified`` -- a 2019+ layout whose year tekton has never read (older
                    than the roster, or newer), but whose own
                    ``Formats/Latest`` parses by name: the job proceeds under
                    the own-release ladder and the manifest / status carry
                    :data:`UNVERIFIED_STAMP`.
* ``refused``    -- the 2008-2018 layout, no detectable year, an unparseable
                    schema, or not a Revit compound file at all: nothing can
                    be built from it, so the route stops with ONE line naming
                    the era / year found, the verified floor and the two
                    remedies (exit code 2 at the CLI).  Refusing an
                    unreadable INPUT withholds nothing (rule 1): there is no
                    output to withhold.

The block is cheap for the common case (one container open + one raw
stream read); only the ``unverified`` branch parses the schema, and that
parse is the memoised one the read ladder reuses a moment later.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from .. import versions as V
from ..meta import BFI_ERA_2008, BFI_ERA_2019, BFI_ERA_UNKNOWN, classify_bfi_era

__all__ = ["UNVERIFIED_STAMP", "REFUSED_PREFIX", "input_release_block",
           "verified_floor"]

#: the stamp an ``unverified`` input puts on the manifest / status (verbatim
#: from the issue's DONE -- relayed as-is by the skills)
UNVERIFIED_STAMP = ("UNVERIFIED-RELEASE: no file of this release has been read by "
                    "tekton before; validate before trusting")
#: the status prefix of a refused input (``manifest.status`` starts with it)
REFUSED_PREFIX = "REFUSED (input release)"


def verified_floor() -> Dict[str, Any]:
    """The releases tekton has actually read / edited, derived from the
    version model (never a year literal): read = every KNOWN release, edit =
    the creation-certified ones (the host release context, #70)."""
    known = sorted(V.KNOWN_RELEASES)
    editable = sorted(V.SUPPORTED_CREATION_RELEASES)
    return {"read_min": known[0], "read": known,
            "edit_min": (editable[0] if editable else None), "edit": editable}


def _refusal_line(path: str, era: str, year: Optional[int], reason: str) -> str:
    floor = verified_floor()
    name = os.path.basename(path)
    what = {BFI_ERA_2008: f"a Revit {year or '2008-2018'} file in the pre-2019 BasicFileInfo layout",
            BFI_ERA_2019: f"a Revit {year if year else '2019+ (year unreadable)'} file",
            BFI_ERA_UNKNOWN: "not a Revit file tekton can classify"}[era]
    return (f"{REFUSED_PREFIX}: {name} is {what} ({reason}); tekton reads Revit "
            f"{floor['read_min']}+ and edits Revit {floor['edit_min']}+ "
            f"({', '.join(map(str, floor['edit']))}) -- re-save it in Revit "
            f"{floor['read_min']} or newer, or hand over an IFC export of it instead "
            "(frontdoor author --ifc FILE.ifc)")


def input_release_block(path: str) -> Dict[str, Any]:
    """Classify ``path`` (an existing file) -> the manifest's ``input_release``
    block: ``{status, era, year, known, floor, note | stamp | line, ...}``.
    Total: never raises; an unreadable container is a ``refused`` block."""
    floor = verified_floor()
    blk: Dict[str, Any] = {"path": os.path.abspath(path), "era": BFI_ERA_UNKNOWN,
                           "year": None, "year_source": None, "known": False,
                           "floor": floor}

    def refuse(reason: str) -> Dict[str, Any]:
        blk.update(status="refused", reason=reason,
                   line=_refusal_line(path, blk["era"], blk["year"], reason))
        return blk

    # ---- the container + the two cheap signals -----------------------------
    try:
        from ..container import open_rvt
        doc = open_rvt(os.fspath(path))
    except Exception as e:                                           # noqa: BLE001
        return refuse(f"not an OLE2 compound file: {type(e).__name__}")
    try:
        has_bfi, has_schema = doc.has("BasicFileInfo"), doc.has("Formats/Latest")
        if has_bfi:
            blk.update(classify_bfi_era(doc.raw("BasicFileInfo")))
            if blk["year"] is not None:
                blk["year_source"] = "BasicFileInfo"
        if blk["year"] is None and has_schema:
            try:
                blk["year"] = V.detect_release_from_schema(doc.concat("Formats/Latest"))
            except Exception:                                        # noqa: BLE001
                blk["year"] = None
            if blk["year"] is not None:
                blk["year_source"] = "Formats/Latest signature"
    finally:
        doc.close()

    # ---- the decision --------------------------------------------------------
    if blk["era"] == BFI_ERA_2008:
        return refuse("Revit 2008-2018 write BasicFileInfo as 'Revit Build: ...'; tekton "
                      "decodes only the 2019+ 'Format: ...' layout and has never read a "
                      "file of this era")
    if not has_schema:
        return refuse("no Formats/Latest class schema stream" +
                      ("" if has_bfi else " and no BasicFileInfo"))
    if blk["year"] is None:
        return refuse("no release year in BasicFileInfo and an unrecognised "
                      "Formats/Latest signature")
    year = int(blk["year"])
    if year in V.KNOWN_RELEASES:
        blk.update(status="known", known=True,
                   note=f"Revit {year}: a release tekton reads"
                        + ("" if year in floor["edit"] else
                           f" (edits are verified on {', '.join(map(str, floor['edit']))} only)"))
        return blk
    # a year outside the roster: proceed only if its OWN schema parses by name
    try:
        from ..global_framing import schema_of          # memoised: the ladder reuses it
        V.ordinals_from_schema(schema_of(path))
    except Exception as e:                                           # noqa: BLE001
        return refuse(f"its own Formats/Latest schema does not parse "
                      f"({type(e).__name__}: {str(e)[:120]})")
    side = "older" if year < floor["read_min"] else "newer"
    blk.update(status="unverified", stamp=UNVERIFIED_STAMP,
               note=(f"Revit {year} is {side} than any release tekton has read "
                     f"({floor['read_min']}-{floor['read'][-1]}); its own class schema "
                     "parses, so the job proceeds under that schema -- "
                     + UNVERIFIED_STAMP))
    return blk
