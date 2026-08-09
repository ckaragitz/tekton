"""rvt.frontdoor.input_release -- classify the ERA of an ``--rvt`` INPUT
before anything opens it (issue #176).

The ``--rvt --edit`` route edits the user's own file, so the first honest
question is not "which release do you want" but "which release IS this, and
has tekton ever read one".  Every job answers it up front from the two cheap
signals the container carries -- the ``BasicFileInfo`` era markers
(:func:`rvt.meta.classify_bfi_era`, layout-independent) and, failing a year
there, :func:`rvt.versions.detect_release` on the open container -- and
lands in exactly one of:

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
stream read, ~0.3 ms); only the ``unverified`` branch parses the schema
(``rvt.schema.parse`` is memoised per process, so the read ladder that
follows does not parse it again).
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

from .. import versions as V
from ..meta import BFI_ERA_2008, BFI_ERA_2019, BFI_ERA_UNKNOWN, classify_bfi_era
from .target_status import supported_targets

__all__ = ["UNVERIFIED_TAG", "UNVERIFIED_STAMP", "REFUSED_PREFIX",
           "input_release_block", "verified_floor"]

#: the stamp an ``unverified`` input puts on the manifest / status (verbatim
#: from the issue's DONE -- relayed as-is by the skills); the tag alone rides
#: in the one-line status
UNVERIFIED_TAG = "UNVERIFIED-RELEASE"
UNVERIFIED_STAMP = (f"{UNVERIFIED_TAG}: no file of this release has been read by "
                    "tekton before; validate before trusting")
#: the status prefix of a refused input (``manifest.status`` starts with it)
REFUSED_PREFIX = "REFUSED (input release)"


def verified_floor() -> Dict[str, List[int]]:
    """The releases tekton has actually read / edited, derived from the
    version model (never a year literal): read = every KNOWN release, edit =
    the creation-certified ones (the host release context, #70).  Both
    sorted ascending, so ``[0]`` is the floor."""
    return {"read": sorted(V.KNOWN_RELEASES), "edit": supported_targets()}


def _refusal_line(blk: Dict[str, Any], reason: str) -> str:
    era, year, floor = blk["era"], blk["year"], blk["floor"]
    if era == BFI_ERA_2008:
        what = f"a Revit {year or '2008-2018'} file in the pre-2019 BasicFileInfo layout"
    elif era == BFI_ERA_2019:
        what = f"a Revit {year or '2019+ (year unreadable)'} file"
    else:
        what = "not a Revit file tekton can classify"
    return (f"{REFUSED_PREFIX}: {os.path.basename(blk['path'])} is {what} ({reason}); "
            f"tekton reads Revit {floor['read'][0]}+ and edits Revit {floor['edit'][0]}+ "
            f"({', '.join(map(str, floor['edit']))}) -- re-save it in Revit "
            f"{floor['read'][0]} or newer, or hand over an IFC export of it instead "
            "(frontdoor author --ifc FILE.ifc)")


def input_release_block(path: str) -> Dict[str, Any]:
    """Classify ``path`` (an existing file) -> the manifest's ``input_release``
    block: ``{path, era, year, floor, status, note | stamp | line (+reason)}``.
    Total: never raises; an unreadable container is a ``refused`` block."""
    blk: Dict[str, Any] = {"path": os.path.abspath(path), "era": BFI_ERA_UNKNOWN,
                           "year": None, "floor": verified_floor()}

    def refuse(reason: str) -> Dict[str, Any]:
        blk.update(status="refused", reason=reason, line=_refusal_line(blk, reason))
        return blk

    # ---- the container + the two cheap signals -----------------------------
    try:
        from ..container import open_rvt
        doc = open_rvt(os.fspath(path))
    except Exception as e:                                           # noqa: BLE001
        return refuse(f"not an OLE2 compound file: {type(e).__name__}")
    with doc:
        has_bfi, has_schema = doc.has("BasicFileInfo"), doc.has("Formats/Latest")
        if has_bfi:
            blk.update(classify_bfi_era(doc.raw("BasicFileInfo")))
        if blk["year"] is None:
            # the detector every other consumer uses (BFI's binary Format
            # field, then the Formats/Latest signature) on the OPEN container
            blk["year"] = V.detect_release(doc)

    # ---- the decision --------------------------------------------------------
    if blk["era"] == BFI_ERA_2008:
        return refuse("Revit 2008-2018 write BasicFileInfo as 'Revit Build: ...'; tekton "
                      "decodes only the 2019+ 'Format: ...' layout and has never read a "
                      "file of this era")
    if not has_schema:
        return refuse("no Formats/Latest class schema stream"
                      + ("" if has_bfi else " and no BasicFileInfo"))
    if blk["year"] is None:
        return refuse("no release year in BasicFileInfo and an unrecognised "
                      "Formats/Latest signature")
    year = int(blk["year"])
    floor = blk["floor"]
    if year in V.KNOWN_RELEASES:
        blk.update(status="known", note=f"Revit {year}: a release tekton reads"
                   + ("" if year in floor["edit"] else
                      f" (edits are verified on {', '.join(map(str, floor['edit']))} only)"))
        return blk
    # a year outside the roster: proceed only if its OWN schema parses by name
    try:
        from ..global_framing import schema_of
        V.ordinals_from_schema(schema_of(path))
    except Exception as e:                                           # noqa: BLE001
        return refuse(f"its own Formats/Latest schema does not parse "
                      f"({type(e).__name__}: {str(e)[:120]})")
    side = "older" if year < floor["read"][0] else "newer"
    blk.update(status="unverified", stamp=UNVERIFIED_STAMP,
               note=(f"Revit {year} is {side} than any release tekton has read "
                     f"({floor['read'][0]}-{floor['read'][-1]}); its own class schema "
                     "parses, so the job proceeds under that schema"))
    return blk
