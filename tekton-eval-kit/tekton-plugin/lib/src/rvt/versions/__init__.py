"""rvt.versions -- the multi-version model for the Revit .rvt read stack
and the release guards for the creation path.

WHY THIS MODULE EXISTS (2026-08-04, MULTI-VERSION PHASE A)
------------------------------------------------------------
Reading/editing an existing .rvt is version-agnostic BY DESIGN: every file
embeds its own ``Formats/Latest`` class schema and our decoders decode
against IT.  The read stack was nevertheless failing on Revit 2025 and 2024
files -- and the root cause is instructive:

* The schema-STREAM grammar did NOT change.  ``rvt.schema.parse`` reads the
  2024, 2025 and 2026 ``Formats/Latest`` to EOF with zero errors, unmodified.
  There are NO schema-parser deltas across these releases.
* What did change is a handful of numbers ``rvt.partitions`` hard-codes as
  "magic tags".  Every one of them turns out to be a schema CLASS ORDINAL
  (a per-release type id) of a class with a STABLE NAME:

      partitions constant   schema class        2024    2025    2026
      -------------------   ------------------  ------  ------  ------
      BLOCK_TAG             SegmentMarker       0x0e7c  0x0ed9  0x0f28
      TRAILER_TAG           SegmentCheckback    0x0e75  0x0ed2  0x0f21
      FOOTER_TAG            SignatureMarker     0x0e8f  0x0eee  0x0f3f
      CONTAINER_CLASS       ContentMarker       0x037b  0x0391  0x03a3
      UNIT_INNER_CLASS      ContentKey          0x037a  0x0390  0x03a2
      PT_CLASS              PartitionTable      0x0bec  0x0c40  0x0c80

  Class ordinals DRIFT between releases (classes are inserted mid-order:
  2024 has 4,492 classes, 2025 4,600, 2026 4,690), so a byte pattern like
  ``\\x28\\x0f`` (= SegmentMarker 2026) is meaningless in a 2025 file.  Even
  "low" ordinals move: XYZ went 172 -> 88 and UV 1861 -> 239 between 2024
  and 2025.  Fixed-offset arithmetic is therefore WRONG; the only correct
  model resolves every ordinal BY NAME from the file's own schema.

* With those six ordinals resolved by name, the ENTIRE read stack (container
  -> ECC page framing -> gzip -> StreamWalker block framing -> schema ->
  schema-directed object decode -> layered validator) runs at PARITY on
  2024 and 2025: verdict VALID, ~96k records, ~32k elements, 99.98 % clean
  seq-102 decode, and the ONLY failures are the same 7 pre-existing
  Extensible-Storage-blob gaps 2026 has.

THIS MODULE PROVIDES
--------------------
* :class:`Release` and :data:`KNOWN_RELEASES` -- what we know per release
  (schema signature, sample build, framing ordinals, creation status).
* :func:`detect_release` -- a file's release from ``BasicFileInfo``
  ("Format: 2025"), falling back to the schema signature.
* :func:`ordinals_from_schema` / :func:`framing_for` -- the six framing
  ordinals resolved BY NAME from a parsed schema (works for ANY release,
  including future ones we have never seen).
* :func:`reading` -- a context manager that activates a file's framing
  ordinals inside ``rvt.partitions`` (its module constants are looked up at
  call time, so binding them per file makes StreamWalker /
  parse_partition_table / the whole validator work on any release WITHOUT
  editing partitions.py).  This is the one call the read path needs.
* The GUARDS: :func:`require_creation_release`, :func:`require_release`,
  :func:`check_openable`.  Creating a version-N file needs version-N format
  data (its schema + unit-schema corpus + a version-N certified genesis
  base), which only comes from a version-N file; today only 2026 is
  certified.  These guards make sure no creation path silently emits a
  2026 file for a 2025 target -- Revit CANNOT open newer files, so a 2026
  output is unusable to a Revit-2025 user.

The precomputed tables are a cache / cross-check.  The AUTHORITY is always
the file's own schema (by-name resolution); the tables exist so detection and
framing work without a schema parse and so drift is asserted, not assumed.
"""
from __future__ import annotations

import os
import struct
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, Mapping, Optional, Union

__all__ = [
    "Release", "KNOWN_RELEASES", "LATEST_RELEASE", "FRAMING_CLASSES",
    "VersionError", "UnknownRelease", "UnsupportedTarget", "NewerFileError",
    "detect_release", "detect_release_from_bfi", "detect_release_from_schema",
    "release_of", "ordinals_from_schema", "framing_for", "framing_table",
    "reading", "activate", "schema_of", "describe",
    "SUPPORTED_CREATION_RELEASES", "require_creation_release",
    "require_release", "check_openable", "creation_status",
    "creation_fallback_line",
]

# ---------------------------------------------------------------------------
# The mapping that IS the version model: rvt.partitions constant -> the
# schema class whose ordinal it holds.  Every "magic tag" in the partition
# framing is one of these; NONE of them is a true constant.
# ---------------------------------------------------------------------------
FRAMING_CLASSES: Dict[str, str] = {
    "BLOCK_TAG": "SegmentMarker",        # block header tag        (2026 0x0f28)
    "TRAILER_TAG": "SegmentCheckback",   # block trailer tag       (2026 0x0f21)
    "FOOTER_TAG": "SignatureMarker",     # unit footer tag         (2026 0x0f3f)
    "CONTAINER_CLASS": "ContentMarker",  # stream hdr / separator  (2026 0x03a3)
    "UNIT_INNER_CLASS": "ContentKey",    # inside the separator    (2026 0x03a2)
    "PT_CLASS": "PartitionTable",        # Global/PartitionTable   (2026 0x0c80)
}


class VersionError(RuntimeError):
    """Base for every version-model refusal."""


class UnknownRelease(VersionError):
    """The file's release could not be determined / is not one we know."""


class UnsupportedTarget(VersionError):
    """A creation was asked for a release we cannot yet produce."""


class NewerFileError(VersionError):
    """A file is newer than the Revit the recipient runs (unopenable)."""


# ---------------------------------------------------------------------------
# release records
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Release:
    """Everything the toolchain knows about one Revit release."""
    year: int
    schema_size: int                 # inflated Formats/Latest byte length
    schema_sha256: str               # the per-release schema constant
    class_count: int                 # classes in the release schema
    sample_build: str                # BasicFileInfo build string of the samples
    framing: Mapping[str, int]       # partitions-constant name -> ordinal
    anchors: Mapping[str, int]       # a few named class ordinals of note
    samples_dir: str = ""            # where the quarantined dev samples live
    creation_certified: bool = False # do we hold a certified genesis base?
    genesis_base: str = ""           # relpath of that certified base, if any

    @property
    def label(self) -> str:
        return f"Revit {self.year}"

    def as_json(self) -> Dict[str, Any]:
        return {
            "year": self.year, "schema_size": self.schema_size,
            "schema_sha256": self.schema_sha256, "class_count": self.class_count,
            "sample_build": self.sample_build,
            "framing": dict(self.framing), "anchors": dict(self.anchors),
            "samples_dir": self.samples_dir,
            "creation_certified": self.creation_certified,
            "genesis_base": self.genesis_base,
        }


KNOWN_RELEASES: Dict[int, Release] = {
    2026: Release(
        year=2026, schema_size=496_597,
        schema_sha256="6459a9a93ebde32c26e4190de2756bf7a4592e63a0d142feca43c392ecdf8ac2",
        class_count=4690, sample_build="20250227_1515(x64)",
        framing={"BLOCK_TAG": 0x0F28, "TRAILER_TAG": 0x0F21, "FOOTER_TAG": 0x0F3F,
                 "CONTAINER_CLASS": 0x03A3, "UNIT_INNER_CLASS": 0x03A2,
                 "PT_CLASS": 0x0C80},
        anchors={"ADocument": 0x1C, "Element": 0x25, "ElementId": 0x14,
                 "ElemTable": 0x5C9, "ElemRec": 0x5C5, "GraveyardRec": 0x5CA,
                 "DocumentHistory": 0x538, "DocumentIncrementTable": 0x53C,
                 "DocumentStorageIndexImpl": 0x53E, "ElementHeader": 0x5E5,
                 "GElement": 0x89E, "SerializedDummy": 0xF2C, "GStyleElem": 0x8CC,
                 "CategoryElem": 0x2E1, "ESSchemaStorage": 0x56F, "HostObj": 0x1B9,
                 "Level": 0x9E7, "SWall": 0xF02, "FamilyInstance": 0x7C5,
                 "FamilySymbol": 0x7E6, "Symbol": 0x70, "XYZ": 0x58, "UV": 0xF7},
        samples_dir="samples", creation_certified=True,
        genesis_base="experiments/genesis/subst_k4/compose/G_ABPD.rvt"),
    2025: Release(
        year=2025, schema_size=484_585,
        schema_sha256="c964f9aa2a5f674e3ca412edb6c72fa3eb6208f6b462e836489ab9a2ea066c04",
        class_count=4600, sample_build="Development Build",
        framing={"BLOCK_TAG": 0x0ED9, "TRAILER_TAG": 0x0ED2, "FOOTER_TAG": 0x0EEE,
                 "CONTAINER_CLASS": 0x0391, "UNIT_INNER_CLASS": 0x0390,
                 "PT_CLASS": 0x0C40},
        anchors={"ADocument": 0x1C, "Element": 0x25, "ElementId": 0x14,
                 "ElemTable": 0x5AB, "ElemRec": 0x5A7, "GraveyardRec": 0x5AC,
                 "DocumentHistory": 0x51D, "DocumentIncrementTable": 0x521,
                 "DocumentStorageIndexImpl": 0x523, "ElementHeader": 0x5C7,
                 "GElement": 0x876, "SerializedDummy": 0xEDD, "GStyleElem": 0x8A4,
                 "CategoryElem": 0x2D3, "ESSchemaStorage": 0x554, "HostObj": 0x1B2,
                 "Level": 0x9B7, "SWall": 0xEB2, "FamilyInstance": 0x79F,
                 "FamilySymbol": 0x7C0, "Symbol": 0x70, "XYZ": 0x58, "UV": 0xEF},
        samples_dir="samples/2025", creation_certified=False),
    2024: Release(
        year=2024, schema_size=470_502,
        schema_sha256="0bfb947b3c9a0cec2ea9692873e3b0325f1c9387caaffddbce4cc2509e77cf21",
        class_count=4492, sample_build="20230308_1635(x64)",
        framing={"BLOCK_TAG": 0x0E7C, "TRAILER_TAG": 0x0E75, "FOOTER_TAG": 0x0E8F,
                 "CONTAINER_CLASS": 0x037B, "UNIT_INNER_CLASS": 0x037A,
                 "PT_CLASS": 0x0BEC},
        anchors={"ADocument": 0x1C, "Element": 0x25, "ElementId": 0x14,
                 "ElemTable": 0x583, "ElemRec": 0x57F, "GraveyardRec": 0x584,
                 "DocumentHistory": 0x4FF, "DocumentIncrementTable": 0x503,
                 "DocumentStorageIndexImpl": 0x505, "ElementHeader": 0x59F,
                 "GElement": 0x83F, "SerializedDummy": 0xE80, "GStyleElem": 0x86D,
                 "CategoryElem": 0x2BE, "ESSchemaStorage": 0x537, "HostObj": 0x19D,
                 "Level": 0x976, "SWall": 0xE55, "FamilyInstance": 0x766,
                 "FamilySymbol": 0x788, "Symbol": 0x6B, "XYZ": 0xAC, "UV": 0x745},
        samples_dir="samples/2024", creation_certified=False),
}

LATEST_RELEASE = max(KNOWN_RELEASES)

# schema signature -> release, for detection when BasicFileInfo is absent
_SCHEMA_SIGNATURES: Dict[str, int] = {
    r.schema_sha256: r.year for r in KNOWN_RELEASES.values()}
_SCHEMA_SIZES: Dict[int, int] = {r.schema_size: r.year for r in KNOWN_RELEASES.values()}


# ---------------------------------------------------------------------------
# detection
# ---------------------------------------------------------------------------
def _parse_year(text: Optional[str]) -> Optional[int]:
    """'2025' / 'Format: 2025' / 'Autodesk Revit 2025 (Build ...)' -> 2025."""
    if not text:
        return None
    import re
    m = re.search(r"(20\d{2})", str(text))
    return int(m.group(1)) if m else None


def detect_release_from_bfi(raw_bfi: bytes) -> Optional[int]:
    """Release year from a raw ``BasicFileInfo`` stream (the cheap, primary
    signal).  ``BasicFileInfo`` is stored UNFRAMED and its layout is the same
    across releases, so this needs no schema and no page/ECC work."""
    try:
        from .. import stream_encoders as se
        return _parse_year(se.decode_basic_file_info(raw_bfi).get("format"))
    except Exception:
        return None


def detect_release_from_schema(schema_or_blob: Any) -> Optional[int]:
    """Release year from a ``Formats/Latest`` blob (bytes) or a parsed
    :class:`rvt.schema.Schema`, via its per-release sha256 / size signature."""
    import hashlib
    if isinstance(schema_or_blob, (bytes, bytearray, memoryview)):
        b = bytes(schema_or_blob)
        y = _SCHEMA_SIGNATURES.get(hashlib.sha256(b).hexdigest())
        return y if y is not None else _SCHEMA_SIZES.get(len(b))
    sha = getattr(schema_or_blob, "sha256", None)
    if sha and sha in _SCHEMA_SIGNATURES:
        return _SCHEMA_SIGNATURES[sha]
    size = getattr(schema_or_blob, "total_size", None)
    return _SCHEMA_SIZES.get(size) if size else None


def _open_doc(source: Any):
    """Accept a path or an already-open RvtDocument; return (doc, must_close)."""
    if isinstance(source, (str, os.PathLike)):
        from ..container import open_rvt
        return open_rvt(os.fspath(source)), True
    return source, False


def detect_release(source: Any, *, strict: bool = False) -> Optional[int]:
    """Determine the Revit release year of a .rvt / .rfa / .rte.

    ``source`` may be a path, an open ``rvt.container.RvtDocument``, or raw
    ``BasicFileInfo`` bytes.  Order of evidence: ``BasicFileInfo.format``
    (authoritative -- it is what Revit itself writes), then the
    ``Formats/Latest`` signature.  ``strict=True`` raises
    :class:`UnknownRelease` instead of returning None.
    """
    if isinstance(source, (bytes, bytearray)):
        yr = detect_release_from_bfi(bytes(source))
        if yr is None and strict:
            raise UnknownRelease("BasicFileInfo bytes carry no recognisable Format year")
        return yr
    doc, must_close = _open_doc(source)
    try:
        yr = None
        try:
            if doc.has("BasicFileInfo"):
                yr = detect_release_from_bfi(doc.raw("BasicFileInfo"))
        except Exception:
            yr = None
        if yr is None:
            try:
                if doc.has("Formats/Latest"):
                    yr = detect_release_from_schema(doc.concat("Formats/Latest"))
            except Exception:
                yr = None
    finally:
        if must_close:
            doc.close()
    if yr is None and strict:
        raise UnknownRelease(
            f"cannot determine the Revit release of {getattr(source, 'path', source)!r} "
            f"(no BasicFileInfo Format year and an unrecognised Formats/Latest); "
            f"known releases: {sorted(KNOWN_RELEASES)}")
    return yr


def release_of(source: Any) -> Optional[Release]:
    """The :class:`Release` record for a file (None if the year is unknown
    to us -- the read path can still proceed by-name via
    :func:`framing_for`)."""
    yr = detect_release(source)
    return KNOWN_RELEASES.get(yr) if yr is not None else None


# ---------------------------------------------------------------------------
# schema access + by-name ordinal resolution (THE authority)
# ---------------------------------------------------------------------------
def schema_of(source: Any):
    """Parse a file's OWN ``Formats/Latest`` (a path or open RvtDocument).

    This is release-independent: the schema stream grammar is unchanged
    across 2024 / 2025 / 2026, so ``rvt.schema.parse`` handles all of them.
    (See ``rvt.versions.schema_2025`` / ``schema_2024`` for the pinned
    per-release handles.)
    """
    from ..schema import parse as parse_schema
    doc, must_close = _open_doc(source)
    try:
        blob = doc.concat("Formats/Latest")
        return parse_schema(blob, source=getattr(doc, "path", ""))
    finally:
        if must_close:
            doc.close()


def ordinals_from_schema(schema) -> Dict[str, int]:
    """Resolve every framing ordinal BY NAME from a parsed schema.

    This is the authority the read stack should trust: it works for ANY
    release (including ones we have never seen), because the class NAMES are
    stable while the ordinals drift.  Raises :class:`VersionError` if a
    required framing class is missing (the schema is not a Revit
    ``Formats/Latest`` at all).
    """
    out: Dict[str, int] = {}
    missing = []
    for const, cls in FRAMING_CLASSES.items():
        c = schema.by_name.get(cls)
        if c is None:
            missing.append(cls)
        else:
            out[const] = int(c.type_id)
    if missing:
        raise VersionError(
            "schema lacks the partition-framing classes "
            f"{missing} -- not a Revit Formats/Latest schema?")
    return out


def framing_table(year: int) -> Dict[str, int]:
    """The precomputed framing ordinals for a KNOWN release (fast path)."""
    r = KNOWN_RELEASES.get(int(year))
    if r is None:
        raise UnknownRelease(
            f"no precomputed framing table for Revit {year}; known: "
            f"{sorted(KNOWN_RELEASES)}.  Use ordinals_from_schema(schema_of(f)) "
            "to read it schema-directed anyway.")
    return dict(r.framing)


def framing_for(source: Any, *, schema=None, prefer_schema: bool = True) -> Dict[str, int]:
    """The six framing ordinals for a file.

    By default resolves them from the file's own schema (authoritative); if
    the schema is unavailable falls back to the precomputed table of the
    detected release.  When BOTH are available they are cross-checked and a
    mismatch raises :class:`VersionError` (schema drift we have not modelled).
    """
    by_schema: Optional[Dict[str, int]] = None
    if schema is not None:
        by_schema = ordinals_from_schema(schema)
    elif prefer_schema:
        try:
            by_schema = ordinals_from_schema(schema_of(source))
        except VersionError:
            raise
        except Exception:
            by_schema = None
    yr = detect_release(source)
    tab = dict(KNOWN_RELEASES[yr].framing) if yr in KNOWN_RELEASES else None
    if by_schema is not None:
        if tab is not None and tab != by_schema:
            raise VersionError(
                f"framing ordinals from the file's schema disagree with the Revit "
                f"{yr} table: schema={by_schema} table={tab}")
        return by_schema
    if tab is not None:
        return tab
    raise UnknownRelease(
        "cannot resolve partition framing ordinals: no schema and an "
        f"unknown release ({yr!r}); known: {sorted(KNOWN_RELEASES)}")


# ---------------------------------------------------------------------------
# activating a release's framing inside rvt.partitions (the read enabler)
# ---------------------------------------------------------------------------
_PATCHED_NAMES = ("BLOCK_TAG", "TRAILER_TAG", "FOOTER_TAG",
                  "CONTAINER_CLASS", "UNIT_INNER_CLASS", "PT_CLASS", "TERMINATOR",
                  "_find_block_header")


def _make_find_block_header(P):
    """A version-aware ``_find_block_header``: searches for the CURRENT
    ``BLOCK_TAG`` byte pattern instead of the literal 2026 ``\\x28\\x0f``.
    (Only reached on the tolerance branch -- unexpected bytes between a unit
    separator and the next block header, never seen after de-paging.)"""
    def _find_block_header(raw: bytes, start: int, limit: int = 65536) -> int:
        pat = struct.pack("<H", P.BLOCK_TAG)
        end = min(len(raw), start + limit)
        q = start
        while True:
            q = raw.find(pat, q, end)
            if q < 0:
                return -1
            if q + 26 <= len(raw):
                flags = struct.unpack_from("<I", raw, q + 2)[0]
                if flags in (4, 5, 6, 7) and raw[q + 26:q + 29] == b"\x1f\x8b\x08":
                    return q
            q += 1
    return _find_block_header


def activate(ordinals: Mapping[str, int]) -> Dict[str, Any]:
    """Bind a set of framing ordinals into ``rvt.partitions`` (module
    globals, looked up by name at call time).  Returns the previous values so
    the caller can restore them; prefer the :func:`reading` context manager,
    which does this for you.

    ``TERMINATOR`` (an 18-byte marker computed from ``BLOCK_TAG`` at import
    time) is recomputed, and the ``\\x28\\x0f`` resync search is replaced by
    a version-aware one -- so no 2026 assumption survives while active.
    """
    from .. import partitions as P
    prev = {n: getattr(P, n) for n in _PATCHED_NAMES}
    for const in ("BLOCK_TAG", "TRAILER_TAG", "FOOTER_TAG",
                  "CONTAINER_CLASS", "UNIT_INNER_CLASS", "PT_CLASS"):
        if const in ordinals:
            setattr(P, const, int(ordinals[const]))
    P.TERMINATOR = struct.pack("<HIIII", P.BLOCK_TAG, 0, 0, 0, 0)
    P._find_block_header = _make_find_block_header(P)
    return prev


def _restore(prev: Mapping[str, Any]) -> None:
    from .. import partitions as P
    for n, v in prev.items():
        setattr(P, n, v)


@contextmanager
def reading(source: Any = None, *, ordinals: Optional[Mapping[str, int]] = None,
            schema=None, year: Optional[int] = None) -> Iterator[Dict[str, int]]:
    """Read a .rvt of ANY release with its own framing ordinals in force.

    Usage::

        with rvt.versions.reading(path):
            rep = rvt.validate.validate_file(path)      # 2024/2025 now VALID

    Ordinal source, in priority: explicit ``ordinals`` > ``schema`` (by-name)
    > the file's own schema (by-name) > the precomputed table of ``year`` /
    the detected release.  On exit the previous ``rvt.partitions`` values are
    restored, so this is safe to nest and cannot leak state into the (2026)
    creation path.  Yields the ordinals in force.
    """
    if ordinals is not None:
        ords = dict(ordinals)
    elif schema is not None:
        ords = ordinals_from_schema(schema)
    elif source is not None:
        ords = framing_for(source)
    elif year is not None:
        ords = framing_table(year)
    else:
        raise VersionError("reading(): give a source path/document, a schema, "
                           "explicit ordinals or a release year")
    prev = activate(ords)
    try:
        yield ords
    finally:
        _restore(prev)


# ---------------------------------------------------------------------------
# guards for the creation path (no silent 2026 for a 2025 target)
# ---------------------------------------------------------------------------
#: releases we can CREATE files for = releases with a certified genesis base.
#: A version-N genesis base + the version-N format data (schema, unit-schema
#: corpus) only come from a version-N file; today that lineage exists for
#: 2026 alone (docs/writer/genesis-2025-plan.md is the 2025 campaign).
SUPPORTED_CREATION_RELEASES = frozenset(
    y for y, r in KNOWN_RELEASES.items() if r.creation_certified)


def creation_status(target: int) -> Dict[str, Any]:
    """What creating a Revit-`target` file would take, honestly."""
    target = int(target)
    r = KNOWN_RELEASES.get(target)
    if r is not None and r.creation_certified:
        return {"target": target, "supported": True, "base": r.genesis_base,
                "reason": f"certified {r.label} genesis base pinned"}
    if r is not None:
        return {"target": target, "supported": False, "base": None,
                "have_samples": bool(r.samples_dir), "have_schema": True,
                "reason": (f"no certified Revit {target} genesis base yet: creating a "
                           f"{target} file needs {target} format data (schema + unit-schema "
                           f"corpus, both harvested from the quarantined {r.samples_dir} "
                           f"samples) AND a {target} genesis lineage (reduction ladder -> "
                           f"family-free base -> substitution ladder -> composer); see "
                           f"docs/writer/genesis-2025-plan.md")}
    return {"target": target, "supported": False, "base": None,
            "have_samples": False, "have_schema": False,
            "reason": (f"Revit {target} is unknown to the version model (known: "
                       f"{sorted(KNOWN_RELEASES)}); acquire that release's own "
                       f"free public sample project first")}


def require_creation_release(target: Union[int, str]) -> Release:
    """Refuse to CREATE a file for a release we cannot produce.

    THE guard that prevents the silent-2026 failure: the certified genesis
    base is Revit 2026, so a build for a 2025 target MUST stop here rather
    than hand a Revit-2025 user a 2026 file that will not open.  Returns the
    :class:`Release` on success.
    """
    yr = _parse_year(str(target)) if not isinstance(target, int) else int(target)
    if yr is None:
        raise UnknownRelease(f"unrecognised target release {target!r}")
    st = creation_status(yr)
    if not st["supported"]:
        raise UnsupportedTarget(
            f"cannot create a Revit {yr} file: {st['reason']}. "
            f"Certified creation targets today: {sorted(SUPPORTED_CREATION_RELEASES)}. "
            "Do NOT substitute a newer release -- Revit cannot open a file newer "
            "than itself.")
    return KNOWN_RELEASES[yr]


def creation_fallback_line(target: Union[int, str], produced: Union[int, str]) -> str:
    """THE one clear line the front door must say when a target release is
    requested but its genesis base is not yet certified and the build falls
    back to a release the recipient's Revit CANNOT open.

    Owned by the version model so the wording is uniform everywhere the
    fallback surfaces (CLI summary, manifest, skills).  The delivery itself
    is the deliverable rule's job; this line is the honesty that rides with
    it, plus the pointer to the version-agnostic IFC addition.
    """
    t = _parse_year(str(target)) if not isinstance(target, int) else int(target)
    p = _parse_year(str(produced)) if not isinstance(produced, int) else int(produced)
    return (f"target {t} requested: the {t} base is pending certification; "
            f"this file targets {p} -- your Revit {t} cannot open it; "
            f"the IFC alongside is version-agnostic")


def require_release(actual: Optional[int], expected: Union[int, str], *,
                    what: str = "file") -> int:
    """Assert a file's release equals what a step expects (e.g. that the
    genesis base / specimen ancestor a build is about to clone from is the
    target release).  Refuses mixing releases inside one creation."""
    exp = _parse_year(str(expected)) if not isinstance(expected, int) else int(expected)
    if exp is None:
        raise UnknownRelease(f"unrecognised expected release {expected!r}")
    if actual is None:
        raise UnknownRelease(f"cannot determine the release of the {what}; expected Revit {exp}")
    if int(actual) != exp:
        raise VersionError(
            f"the {what} is Revit {actual} but Revit {exp} is required -- format "
            f"data is per-release (schema class ordinals differ), so the two "
            f"cannot be mixed in one file")
    return int(actual)


def check_openable(file_release: Optional[int], revit_version: Union[int, str]) -> None:
    """Refuse to hand a user a file newer than the Revit they run.

    Revit opens files SAVED IN its own release or OLDER, never newer -- the
    exact trap of problem (C): a 2026 output is unusable to a Revit-2025 user.
    """
    rv = _parse_year(str(revit_version)) if not isinstance(revit_version, int) else int(revit_version)
    if rv is None:
        raise UnknownRelease(f"unrecognised Revit version {revit_version!r}")
    if file_release is None:
        raise UnknownRelease("cannot determine the file's release to check openability")
    if int(file_release) > rv:
        raise NewerFileError(
            f"the file is Revit {file_release} but the recipient runs Revit {rv}: "
            f"Revit cannot open a NEWER file.  Produce a Revit-{rv} (or older) file "
            f"instead ({'not yet certified' if rv not in SUPPORTED_CREATION_RELEASES else 'certified'} "
            f"as a creation target).")


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------
def describe(source: Any) -> Dict[str, Any]:
    """One-shot version report for a file: detected release, schema
    signature, the framing ordinals it needs, and creation status."""
    out: Dict[str, Any] = {"path": os.fspath(source) if isinstance(source, (str, os.PathLike)) else None}
    yr = detect_release(source)
    out["release"] = yr
    out["known"] = yr in KNOWN_RELEASES if yr is not None else False
    try:
        s = schema_of(source)
        st = s.stats()
        out["schema"] = {"size": st["stream_size"], "sha256": st["sha256"],
                         "classes": st["class_count"], "fields": st["field_count"],
                         "unresolved_refs": st["unresolved_refs"],
                         "matches_release_pin": (yr in KNOWN_RELEASES
                                                 and st["sha256"] == KNOWN_RELEASES[yr].schema_sha256)}
        out["framing"] = ordinals_from_schema(s)
    except Exception as e:  # pragma: no cover - defensive
        out["schema_error"] = f"{type(e).__name__}: {e}"
        out["framing"] = framing_table(yr) if yr in KNOWN_RELEASES else None
    if yr is not None:
        out["creation"] = creation_status(yr)
    return out


def main(argv=None) -> int:  # pragma: no cover - CLI convenience
    import argparse
    import json
    ap = argparse.ArgumentParser(prog="rvt.versions",
                                 description="Report the Revit release + framing of a .rvt/.rfa")
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    for p in a.paths:
        d = describe(p)
        if a.json:
            print(json.dumps(d, indent=1, default=str))
        else:
            fr = d.get("framing") or {}
            sc = d.get("schema") or {}
            print(f"{p}: Revit {d['release']} "
                  f"schema={sc.get('size')}B/{sc.get('classes')} classes "
                  f"framing={{{', '.join(f'{k}={v:#x}' for k, v in fr.items())}}} "
                  f"creation_supported={d.get('creation', {}).get('supported')}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
