"""rvt.frontdoor.standalone -- STANDALONE CREATION FROM BUNDLED ASSETS ONLY.

The field failure this module kills (Cowork session, 2026-08-04): native
``.rvt`` creation died with ``FileNotFoundError:
.../extracted/racbasicsampleproject/Formats__Latest.gz/000.bin`` because four
inputs of the build path lived only on the research machine:

    1. the CORPUS SCHEMA  ``extracted/racbasicsampleproject/Formats__Latest.gz/
       000.bin`` -- every no-arg ``ObjectDecoder()`` / ``ObjectEncoder()`` /
       ``adocument.get_decoder()`` resolved ``rvt.schema.DEFAULT_PATH`` there;
    2. the SPECIMEN ANCESTOR ``experiments/genesis/R5.rvt`` -- the wall /
       instance clone templates (``tools/ifc_intent.py SpecimenSet``);
    3. the pinned BASE at its repo path ``experiments/genesis/subst_k4/compose/
       G_ABPD.rvt`` (the resolver never looked at the plugin's real bundle
       location ``<plugin>/assets/genesis/G_ABPD.rvt``);
    4. the FAMILY CONTAINER DONOR ``vendor/phi-ag-rvt/examples/Autodesk/
       racbasicsamplefamily-2026.rfa`` (``skeleton.emit_family_rfa`` /
       ``famdoc_adoc.TEMPLATE_DONOR``).

This module replaces all four with THE ONE ASSET THE PLUGIN SHIPS -- the
certified genesis base ``G_ABPD.rvt`` -- plus constructed content:

    1. SCHEMA        <- parsed from the base's own embedded ``Formats/Latest``
                        (PROVEN byte-identical to the corpus stream:
                        sha256 6459a9a9... on the corpus 000.bin, the bundled
                        base, R5, all six Autodesk sample projects AND the
                        family archetype .rfa -- the per-release format
                        constant, counsel C4);
    2. SPECIMENS     <- CONSTRUCTED wall / instance templates (schema-directed
                        ``default_object`` + the documented generic shapes) --
                        no R5, no donor file, nothing cloned from any
                        Autodesk-authored element;
    3. BASE          <- resolved from the plugin bundle (or $RVT_GENESIS_BASE /
                        the repo pin path), sha256-pinned exactly as
                        ``rvt.frontdoor.base`` demands;
    4. FAMILY FILES  <- ``famdoc_adoc.emit_family_rfa_v2`` with the BUNDLED
                        BASE as the container source: ``Formats/Latest`` = the
                        base's copy of the format constant, ``Global/Latest`` =
                        OUR AUTHORED family ADocument
                        (``author_family_adocument`` seeded from the base's
                        decoded tree, purged + repopulated over OUR inventory),
                        element records / PartAtom / footer / container OURS.
                        PROVEN on this machine: family-mode validator VALID
                        0 errors 0 warnings, ``provenance_scan_v2`` all checks
                        TRUE, carried stream = the schema constant only.

HARD RULE (user, non-negotiable): tekton NEVER reads ANY Autodesk
installation directory -- not the Windows program / program-data Autodesk
trees, not an Autodesk family-template folder, not /Applications/Autodesk,
no registry -- and never asks the user for access to one.  This module never
constructs such a path; :func:`forbid_research_inputs` additionally turns any
read of extracted/ / samples/ / vendor/ / experiments/ or an Autodesk install
directory into a hard error so regressions cannot ship silently.

``--family-donor PATH`` stays available as a HIDDEN escape hatch
(:func:`activate` honours ``family_donor=``): a user-supplied ``.rfa``
provides container + schema at runtime; nothing is redistributed.  It is
never required and never mentioned proactively.

THE DELIVERABLE RULE (user, non-negotiable): PROOF-ONLY stamps are LABELS,
never refusal logic.  Every function here either produces its artefact or
raises one clear error naming the single missing input -- there is no code
path that withholds a buildable file.

Territory: ``src/rvt/frontdoor/standalone.py`` (standalone-creation stream);
tests in ``tests/test_frontdoor_standalone.py``; the record + the exact
patches for build.py / base.py / ifc_intent.py / famgen in
``docs/inbox/standalone.md``.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .base import PIN, BaseError, repo_root, sha256_of

__all__ = [
    "StandaloneError", "plugin_root", "bundled_base_path", "bundled_schema",
    "install_schema", "schema_identity_report", "default_object",
    "family_instance_template", "swall_template", "ConstructedSpecimens",
    "CONSTRUCTED", "make_specimens", "standalone_family_write", "activate",
    "forbid_research_inputs", "author_standalone", "dependency_table",
]

#: sentinel accepted wherever a specimen SOURCE PATH is expected: "construct
#: the templates, read no ancestor file"
CONSTRUCTED = "__constructed__"

#: sha256 of the inflated per-release ``Formats/Latest`` schema stream
#: (Revit 2026) -- the corpus constant every source above carries.
SCHEMA_2026_SHA256 = "6459a9a93ebde32c26e4190de2756bf7a4592e63a0d142feca43c392ecdf8ac2"

_ELECTRICAL_EQUIPMENT = -2001040
_WALLS_CATEGORY = -2000011


class StandaloneError(RuntimeError):
    """Standalone resolution failed; the message names the ONE missing input."""


# ===========================================================================
# 1. bundled-asset resolution
# ===========================================================================

def plugin_root() -> Optional[str]:
    """The plugin bundle root, when this package IS the plugin's bundled
    engine copy (``<plugin>/lib/src/rvt/frontdoor/standalone.py``): four
    levels up from this file, recognised by ``assets/genesis`` +
    ``lib/src/rvt`` both existing.  ``$RVT_PLUGIN_ROOT`` overrides."""
    envp = os.environ.get("RVT_PLUGIN_ROOT")
    if envp and os.path.isdir(envp):
        return os.path.abspath(envp)
    here = os.path.dirname(os.path.abspath(__file__))     # .../src/rvt/frontdoor
    cand = os.path.abspath(os.path.join(here, "..", "..", "..", ".."))
    if (os.path.isdir(os.path.join(cand, "assets", "genesis"))
            and os.path.isdir(os.path.join(cand, "lib", "src", "rvt"))):
        return cand
    return None


def bundled_base_path(explicit: Optional[str] = None, *, verify: bool = True) -> str:
    """Locate the certified genesis base from BUNDLED locations only.

    Order: ``explicit`` -> ``$RVT_GENESIS_BASE`` -> the repo pin path ->
    ``<plugin>/assets/genesis/<name>`` -> ``<plugin>/lib/genesis/<name>``
    (the pin's historic bundled location).  The sha256 must equal the pin
    unless the caller supplied the file (their authority, recorded upstream
    by ``rvt.frontdoor.base.resolve_base``)."""
    name = os.path.basename(PIN.base_relpath)
    tried: List[str] = []
    cands: List[Tuple[str, bool]] = []            # (path, must_match_pin)
    if explicit:
        cands.append((explicit, False))
    envp = os.environ.get("RVT_GENESIS_BASE")
    if envp:
        cands.append((envp, False))
    cands.append((os.path.join(repo_root(), PIN.base_relpath), True))
    pr = plugin_root()
    if pr:
        cands.append((os.path.join(pr, "assets", "genesis", name), True))
        cands.append((os.path.join(pr, "lib", "genesis", name), True))
    for path, pinned in cands:
        ap = os.path.abspath(path)
        tried.append(ap)
        if not os.path.isfile(ap):
            continue
        if verify and pinned:
            digest = sha256_of(ap)
            if digest.lower() != PIN.base_sha256.lower():
                raise BaseError(
                    f"genesis base pin MISMATCH at {ap}: sha256 {digest[:16]}... != "
                    f"pinned {PIN.base_sha256[:16]}...")
        return ap
    raise StandaloneError(
        "the certified genesis base G_ABPD.rvt was not found in any bundled "
        "location (tried: " + "; ".join(tried) + "). Supply it via "
        "$RVT_GENESIS_BASE or --base; the plugin normally bundles it at "
        "assets/genesis/G_ABPD.rvt.")


# ===========================================================================
# 2. the schema EMBEDDED in the bundled base + chokepoint installation
# ===========================================================================

_SCHEMA_STATE: Dict[str, Any] = {}


def _inflate_formats_latest(rvt_path: str) -> bytes:
    from ..container import open_rvt
    with open_rvt(rvt_path) as f:
        return f.inflate("Formats/Latest", 0)


def bundled_schema(base_path: Optional[str] = None):
    """The parsed schema from the bundled base's own ``Formats/Latest``
    (cached).  This IS the project-side schema: every ``.rvt`` embeds the
    per-release class map and our decoder decodes against it."""
    bp = os.path.abspath(base_path or bundled_base_path())
    hit = _SCHEMA_STATE.get("schema")
    if hit is not None and _SCHEMA_STATE.get("from") == bp:
        return hit
    from ..schema import parse as parse_schema
    blob = _inflate_formats_latest(bp)
    digest = hashlib.sha256(blob).hexdigest()
    schema = parse_schema(blob, source=f"{bp}#Formats/Latest")
    _SCHEMA_STATE.update({"schema": schema, "from": bp, "sha256": digest,
                          "bytes": len(blob), "blob": blob,
                          "is_corpus_constant": digest == SCHEMA_2026_SHA256})
    return schema


def install_schema(base_path: Optional[str] = None) -> Dict[str, Any]:
    """Reroute EVERY default-schema chokepoint to the bundled base's embedded
    schema, so no code path ever resolves the research corpus:

    * ``rvt.schema.load_schema`` (and the from-imported copies in
      ``rvt.objects`` / ``rvt.encode`` / ``rvt.adocument``) -- the no-arg /
      default-path call returns the bundled schema; an explicit existing path
      still loads that path;
    * ``rvt.schema.DEFAULT_PATH`` -- pointed at a materialised cache file of
      the same bytes (for any code comparing/opening the path directly);
    * the singleton caches: ``rvt.genesis.skeleton._SCHEMA_CACHE`` (used by
      ``rvt.famgen.skeleton.build_unit_segments``), ``rvt.encode
      ._DEFAULT_ENCODER``, ``rvt.adocument._DECODER``.

    Idempotent; returns a report of what was installed."""
    from .. import schema as _schema
    schema = bundled_schema(base_path)
    report: Dict[str, Any] = {"schema_sha256": _SCHEMA_STATE["sha256"],
                              "schema_bytes": _SCHEMA_STATE["bytes"],
                              "is_corpus_constant": _SCHEMA_STATE["is_corpus_constant"],
                              "from": _SCHEMA_STATE["from"], "installed": []}
    if _SCHEMA_STATE.get("installed") and _SCHEMA_STATE.get("installed_from") == \
            _SCHEMA_STATE.get("from"):
        report["installed"] = ["(already installed)"]
        return report

    # (a) a real file for DEFAULT_PATH consumers
    cache_dir = os.path.join(tempfile.gettempdir(), "tekton-schema-cache")
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f"Formats_Latest_{_SCHEMA_STATE['sha256'][:16]}.bin")
    if not (os.path.isfile(cache_file)
            and os.path.getsize(cache_file) == _SCHEMA_STATE["bytes"]):
        with open(cache_file, "wb") as fh:
            fh.write(_SCHEMA_STATE["blob"])
    old_default = _schema.DEFAULT_PATH
    _schema.DEFAULT_PATH = cache_file
    report["installed"].append(f"rvt.schema.DEFAULT_PATH -> {cache_file}")

    # (b) load_schema in every module that from-imported it
    orig_load = _schema.load_schema

    def _load_schema_bundled(path: str = old_default):
        if path in (None, old_default, cache_file) or not os.path.isfile(path):
            return schema
        return orig_load(path)

    _schema.load_schema = _load_schema_bundled
    from .. import objects as _objects
    from .. import encode as _encode
    from .. import adocument as _adocument
    for mod in (_objects, _encode, _adocument):
        mod.load_schema = _load_schema_bundled
        report["installed"].append(f"{mod.__name__}.load_schema -> bundled")

    # (c) the singleton caches
    dec = _objects.ObjectDecoder(schema)
    enc = _encode.ObjectEncoder(decoder=dec)
    try:
        from ..genesis import skeleton as _gsk
        _gsk._SCHEMA_CACHE["dec"] = dec
        _gsk._SCHEMA_CACHE["enc"] = enc
        report["installed"].append("rvt.genesis.skeleton._SCHEMA_CACHE seeded")
    except Exception as e:                                # pragma: no cover
        report["installed"].append(f"genesis.skeleton cache NOT seeded: {e}")
    _encode._DEFAULT_ENCODER = enc
    _adocument._DECODER = _adocument.ADocumentDecoder(schema)
    report["installed"].append("rvt.encode._DEFAULT_ENCODER / rvt.adocument._DECODER seeded")
    _SCHEMA_STATE["installed"] = True
    # remember WHICH base seeded the singletons: a later call with a
    # DIFFERENT base (e.g. a per-release targeted build in the same process)
    # re-seeds instead of silently keeping the stale release's codecs
    _SCHEMA_STATE["installed_from"] = _SCHEMA_STATE["from"]
    _SCHEMA_STATE["decoder"] = dec
    _SCHEMA_STATE["encoder"] = enc
    return report


def schema_identity_report(base_path: Optional[str] = None,
                           corpus_path: Optional[str] = None) -> Dict[str, Any]:
    """PROOF that the schema embedded in the bundled base is class-for-class
    identical to the research-corpus stream the code used before.

    Byte tier: sha256 of both inflated streams.  Class tier: id / name /
    parent / version / field-list (name, kind, flags, count, type) compared
    for every class.  Returns ``{identical_bytes, identical_classes,
    n_classes, mismatches[...]}`` -- run on the research machine where the
    corpus exists; in the field the corpus side is reported absent."""
    from ..schema import parse as parse_schema
    bp = base_path or bundled_base_path()
    blob_b = _inflate_formats_latest(bp)
    rep: Dict[str, Any] = {
        "base": bp,
        "base_sha256": hashlib.sha256(blob_b).hexdigest(),
        "base_bytes": len(blob_b),
        "expected_constant_sha256": SCHEMA_2026_SHA256,
        "base_is_corpus_constant": hashlib.sha256(blob_b).hexdigest() == SCHEMA_2026_SHA256,
    }
    cp = corpus_path or os.path.join(
        repo_root(), "extracted", "racbasicsampleproject", "Formats__Latest.gz", "000.bin")
    if not os.path.isfile(cp):
        rep["corpus"] = f"(absent here: {cp})"
        rep["identical_bytes"] = rep["base_is_corpus_constant"]
        return rep
    blob_c = open(cp, "rb").read()
    rep["corpus"] = cp
    rep["corpus_sha256"] = hashlib.sha256(blob_c).hexdigest()
    rep["identical_bytes"] = blob_b == blob_c
    sb = parse_schema(blob_b, source="base")
    sc = parse_schema(blob_c, source="corpus")
    mismatches: List[str] = []
    ids = sorted(set(sb.by_id) | set(sc.by_id))
    for tid in ids:
        a, b = sb.by_id.get(tid), sc.by_id.get(tid)
        if a is None or b is None:
            mismatches.append(f"class {tid:#x} only in {'corpus' if a is None else 'base'}")
            continue
        if (a.name, a.parent_id, a.version) != (b.name, b.parent_id, b.version):
            mismatches.append(f"class {tid:#x}: {a.name}/{a.parent_id}/{a.version} != "
                              f"{b.name}/{b.parent_id}/{b.version}")
            continue
        fa = [(f.name, f.kind, f.flags, f.count, f.type_id) for f in a.fields]
        fb = [(f.name, f.kind, f.flags, f.count, f.type_id) for f in b.fields]
        if fa != fb:
            mismatches.append(f"class {tid:#x} {a.name}: field lists differ")
    rep["n_classes"] = len(ids)
    rep["identical_classes"] = not mismatches
    rep["mismatches"] = mismatches[:50]
    return rep


# ===========================================================================
# 3. schema-directed default objects (the constructor substrate)
# ===========================================================================

_NULL_GUID = "00000000-0000-0000-0000-000000000000"


def _default_scalar(f, schema, depth: int):
    kind = f.kind
    if kind == 0x01:
        return False
    if kind in (0x02, 0x03, 0x04, 0x05, 0x0B):
        return 0
    if kind in (0x06, 0x07):
        return 0.0
    if kind == 0x08:
        return ""
    if kind == 0x09:
        return _NULL_GUID
    if kind == 0x0A:                                   # classref -- no sane default
        return {"classref": "Element"}
    if kind == 0x0E:
        indir = f.flags & 0x0F
        if indir == 3:                                 # weak pointer
            return {"weakref": 0}
        if indir != 0:                                 # owned/shared pointer
            return None
        # inline value class
        dec = _SCHEMA_STATE.get("decoder")
        tid = f.type_id
        if dec is not None:
            if tid in (dec.id_ElementId, dec.id_Identifier):
                return -1
            if tid == dec.id_XYZ:
                return [0.0, 0.0, 0.0]
            if tid == dec.id_UV:
                return [0.0, 0.0]
            if tid == dec.id_GUIDvalue:
                return _NULL_GUID
        return default_object(schema, tid, depth + 1)
    raise StandaloneError(f"no default for field kind {kind:#x} ({f.name})")


def default_object(schema, class_or_id, depth: int = 0) -> Dict[str, Any]:
    """A COMPLETE, schema-conformant value dict for ``class_or_id`` with every
    field at its type default (ints 0, ElementIds -1, bools False, strings
    empty, arrays empty, pointers null).  The substrate the constructed
    specimen templates override -- nothing here is copied from any file."""
    if depth > 24:
        raise StandaloneError("default_object recursion runaway")
    cd = schema.by_id.get(class_or_id) if isinstance(class_or_id, int) \
        else schema.by_name.get(class_or_id)
    if cd is None:
        raise StandaloneError(f"unknown class {class_or_id!r}")
    dec = _SCHEMA_STATE.get("decoder")
    chain = dec.chain(cd.type_id) if dec is not None else [cd]
    from ..objects import field_key
    out: Dict[str, Any] = {}
    for c in chain:
        for f in c.fields:
            key = field_key(c, f, out)
            shape = f.flags >> 4
            if f.kind == 0x0D:                          # array wrapper
                if shape == 0x1 and f.count:
                    out[key] = [_default_scalar(f.element, schema, depth)
                                for _ in range(f.count)]
                else:
                    out[key] = []
                continue
            if shape == 0x5:
                out[key] = []
                continue
            if shape == 0x1:
                n = f.count or 0
                out[key] = [_default_scalar(f, schema, depth) for _ in range(n)]
                continue
            out[key] = _default_scalar(f, schema, depth)
    return out


def _ptr(cls: str, value: Dict[str, Any], pid: int = -1) -> Dict[str, Any]:
    return {"ptr_class": cls, "pid": pid, "value": value}


def _dflt(schema, cls: str, **over) -> Dict[str, Any]:
    d = default_object(schema, cls)
    d.update(over)
    return d


# ===========================================================================
# 4. CONSTRUCTED specimen templates (no R5, no donor, nothing cloned)
# ===========================================================================

def _element_header(schema, *, category: int, class_name: str,
                    flags4: int) -> Dict[str, Any]:
    h = default_object(schema, "ElementHeader")
    h.update({
        "m_regenHistory": {"m_historyMap": []},
        "m_categroryId": category,
        "m_familyId": -1, "m_ownerViewId": -1, "m_designOptionId": -1,
        "m_unplacedOwnerId": -1, "m_miscId": -1,
        # every-view-visible flag word carried by every specimen header in the
        # corpus (format bookkeeping, not content)
        "m_viewRules": {"m_nVisibleViewFlags": -4225},
        "m_abFlags4Bytes": flags4,
        "m_classDef": {"m_ref": {"classref": class_name}},
        "m_pBBox": _ptr("Outline", {"m_minmax": [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]}),
        "m_parents": _ptr("ElementParents", _dflt(
            schema, "ElementParents",
            m_deletion=[], m_regenOnly=[], m_regenWildcards=[],
            m_nonDetermRegenChildren=[], m_dependencyParents=[],
            m_appearanceParents=[], m_deferredParents=[],
            m_deferredPropagationParents=[], m_computedParametersParents=[],
            m_hasNonDetermRegenChildren=False)),
    })
    return h


def family_instance_template(schema, *, elem_id: int, level_id: int,
                             phase_id: int = -1,
                             category: int = _ELECTRICAL_EQUIPMENT
                             ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """A CONSTRUCTED free-standing ``FamilyInstance`` clone template.

    Shape: the documented free-standing pattern (mutation-plan §6 /
    docs/writer): symbol == masterSymbol, no host, identity transform, empty
    parameter sets, an empty ``FamilyParams``, the single-slot ``GeomTable``
    and the two universal cells.  ``rvt.mutate.add_family_instance`` +
    ``ifc_intent._scrub_instance`` overwrite every placement-bearing field;
    what this template contributes is exactly the DEFAULT field state, so it
    is constructed as defaults -- copied from no file."""
    obj = default_object(schema, "FamilyInstance")
    obj.update({
        "m_pParamValueSetDouble": None, "m_pParamValueSetInt": None,
        "m_pParamValueSetAString": None, "m_pParamValueSetElementId": None,
        "m_geomSteps": None,
        "m_pGeomTable": _ptr("GeomTable", _dflt(
            schema, "GeomTable", m_refPntMirrored=False,
            m_table=[{"m_geomGeneratorId": -1}], m_bigTableOwner=None,
            m_materialMarkers=[], m_faceTypeMarkers=[])),
        "m_constrInfo": [],
        "m_cellList": _ptr("CellList", {"m_cells": [
            _ptr("AnalyticalSpaceBoundingCell", {"m_isSpaceBounding": True}),
            _ptr("FamilyInstancePatternHelper",
                 _dflt(schema, "FamilyInstancePatternHelper",
                       m_PatternPositionMap=[], m_substituteFaceMap=[])),
        ]}),
        "m_docAccess": {"m_pDoc": {"weakref": 1}},
        "m_id": elem_id,
        "m_assocLevelId": level_id,
        "m_famId": -1, "m_unplacedOwnerId": -1, "m_ownerDBViewId": -1,
        "m_createdPhaseId": phase_id, "m_demolishedPhaseId": -1,
        "m_designOptionId": -1,
        "m_locked": False, "m_moribund": False, "m_dummy": False,
        "m_pInstanceInfo": _ptr("InstanceInfo", _dflt(
            schema, "InstanceInfo",
            m_Trf={"m_3x3": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                   "m_or": [0.0, 0.0, 0.0]},
            m_symbolId=-1, m_GRepId=0, m_cda={"m_pDoc": {"weakref": 1}})),
        "m_GInstanceId": 0, "m_elevation": 0.0, "m_hostParam": 0.0,
        "m_hostId": -1, "m_extraHostIds": [], "m_explicitHostIds": [],
        "m_refs": [], "m_offsetPosArr": [], "m_subInstTable": [],
        "m_pInstParams": _ptr("FamilyParams", _dflt(
            schema, "FamilyParams", m_params=[],
            m_geomRefHandles={"m_offsetGeomMap": []})),
        "m_oFamInstSpec": None, "m_pDesignPropManager": None,
        "m_pCurveDriver": None, "m_pInplaceInsertionHelper": None,
        "m_pConnectorManager": None, "m_posRelToGrid": None,
        "m_oFamInstUserData": None, "m_leaders": [], "m_oPOFDriver": None,
        "m_instOrigin": [0.0, 0.0, 0.0], "m_RefDir": [1.0, 0.0, 0.0],
        "m_zAxis": [0.0, 0.0, 1.0],
        "m_masterSymbolId": -1, "m_ownerElemId": -1,
        "m_assocSketchPlaneId": -1, "m_analyticalTopPlaneId": -1,
        "m_analyticalBottomPlaneId": -1, "m_superInstanceId": -1,
        "m_scheduleOnlyLevelId": -1,
        "m_famElemVisibility": {"m_flags": -1},
        "m_structType": 0, "m_structUsage": 0, "m_insertOrientation": 0,
        "m_roomBounding": True,
        "m_flippedX": False, "m_flippedY": False, "m_flippedFromToRoom": False,
        "m_useOffsetPos": False, "m_invisible": False,
        "m_workPlaneBased": False, "m_workPlaneFlipped": False,
        "m_bVertical": True, "m_instDormant": False,
    })
    hdr = _element_header(schema, category=category, class_name="FamilyInstance",
                          flags4=2344)
    return hdr, obj


def _box_face_hist() -> List[Dict[str, Any]]:
    """The generic 6-entry face-history table of an extruded box (bottom, top,
    four sides) -- pure topology bookkeeping, same for every simple wall."""
    keys = [[1, -1, -1], [2, -1, -1], [3, 0, -1], [3, 1, -1], [3, 2, -1], [3, 3, -1]]
    return [{"m_id": i + 1, "m_faceHist": {"m_keys": k}} for i, k in enumerate(keys)]


def _box_edge_hist() -> List[Dict[str, Any]]:
    """The generic 12-entry edge-history table of the box (8 vertical/side
    edges + 4 cap edges)."""
    keys = ([[1, i, j, -1] for i in range(4) for j in (0, 1)]
            + [[2, i, (3 - i) % 4, -1] for i in range(4)])
    return [{"m_id": 7 + i, "m_edgeHist": {"m_keys": k}}
            for i, k in enumerate(keys)]


def swall_template(schema, *, elem_id: int, level_id: int, wall_type_id: int,
                   thickness_ft: float, shell_ft: float = 0.0,
                   phase_id: int = -1, length_ft: float = 10.0,
                   height_ft: float = 8.0) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """A CONSTRUCTED straight-wall (``SWall``) clone template.

    The wall is UNJOINED BY CONSTRUCTION (what ``_clean_wall_clone('unjoin')``
    produces from a joined specimen): geometry history = one ``BaseWallGStep``
    with the generic box topology tables, no tweaks, no snapshots, empty join
    sets, no paint/face overrides, location line on the CENTERLINE
    (``m_wallKeyRef`` 0, key offset 0).  The four driven reference faces sit
    at +-thickness/2 and the core faces at +-(thickness/2 - shell);
    ``rvt.mutate.add_wall`` rebuilds every face plane for the real wall line,
    preserving these perpendicular offsets."""
    half = thickness_ft / 2.0
    core = max(half - shell_ft, 0.0)

    def _face(tag: int, off: float, gflags: int) -> Dict[str, Any]:
        return _ptr("Face", _dflt(
            schema, "Face",
            m_GInfo={"m_categoryId": -1, "m_tag": tag, "m_controlCommand": 0,
                     "m_flags": gflags},
            m_pFirstLoop=None, m_faceRegions=[], m_pGFilling=None,
            m_oBackgroundFilling=None, m_renderStyleId=-1, m_cutType=0,
            m_faceFlags_v9=32,
            m_pSurf=_ptr("Plane", _dflt(
                schema, "Plane",
                m_Envelope={"m_corners": [[0.0, 0.0], [length_ft, height_ft]]},
                m_orientFlag=True,
                m_origin=[0.0, off, 0.0],
                m_xVec=[1.0, 0.0, 0.0], m_yVec=[0.0, 0.0, 1.0]))))

    base_step = _ptr("BaseWallGStep", _dflt(
        schema, "BaseWallGStep",
        m_faceHistTable=_box_face_hist(), m_curveHistTableSet=[],
        m_edgeHistTable=_box_edge_hist(), m_edgeHistTableReverse=[],
        m_id=1, m_version=7, m_flags=761725, m_pElem={"weakref": 2},
        m_oExtraDatas=None, m_generatedWallCrossSection=1))
    geom_steps = _ptr("GeomStepList", _dflt(
        schema, "GeomStepList",
        m_nonBRepGList=[], m_bRepFormGList=[base_step], m_bRepAdjustGList=[],
        m_bRepCutOutGList=[], m_bRepPostCutOutGList=[], m_bRepTweakGList=[],
        m_bRepFormSnapshot=None, m_bRepAdjustSnapshot=None,
        m_bRepCutOutSnapshot=None, m_bRepPostCutOutSnapshot=None,
        m_pElem={"weakref": 2}, m_latestGStepTypeInPrevRegenCycle=[2, 3, 3, 3, 6],
        m_idCounter=2, m_flags=11))

    obj = default_object(schema, "SWall")
    obj.update({
        "m_pParamValueSetDouble": _ptr("ParamValueSetDouble", {"m_paramSet": []}),
        "m_pParamValueSetInt": None, "m_pParamValueSetAString": None,
        "m_pParamValueSetElementId": None,
        "m_geomSteps": geom_steps,
        "m_pGeomTable": _ptr("GeomTable", _dflt(
            schema, "GeomTable", m_refPntMirrored=False,
            m_table=[{"m_geomGeneratorId": -1}], m_bigTableOwner=None,
            m_materialMarkers=[], m_faceTypeMarkers=[])),
        "m_constrInfo": [],
        "m_cellList": _ptr("CellList", {"m_cells": [
            _ptr("AnalyticalElementParametersCell",
                 default_object(schema, "AnalyticalElementParametersCell")),
            _ptr("AnalyticalSpaceBoundingCell", {"m_isSpaceBounding": True}),
            _ptr("VWallPatternHelper", _dflt(
                schema, "VWallPatternHelper",
                m_PatternPositionMap=[], m_substituteFaceMap=[])),
        ]}),
        "m_docAccess": {"m_pDoc": {"weakref": 1}},
        "m_id": elem_id,
        "m_assocLevelId": level_id,
        "m_famId": -1, "m_unplacedOwnerId": -1, "m_ownerDBViewId": -1,
        "m_createdPhaseId": phase_id, "m_demolishedPhaseId": -1,
        "m_designOptionId": -1,
        "m_locked": False, "m_moribund": False, "m_dummy": False,
        "m_hostObjMiscData": None, "m_oGeomToElemMap": None,
        "m_roomBounding": True,
        "m_drivenCGLineDataU": None, "m_drivenCGLineDataV": None,
        "m_pCurveDriver": _ptr("VWallDriver", _dflt(
            schema, "VWallDriver",
            m_oControlData=None,
            m_pCrv=_ptr("GLine", _dflt(
                schema, "GLine",
                m_GInfo={"m_categoryId": -1, "m_tag": 0, "m_controlCommand": 0,
                         "m_flags": 17301508},
                m_endParams=[0.0, length_ft],
                m_origin=[0.0, 0.0, 0.0], m_dirVec=[1.0, 0.0, 0.0])),
            m_sideJoins=[], m_controlJoinsSet=[], m_midParams=[],
            m_nextMidParamId=0, m_flip=False, m_sideAlignments=[],
            m_joinStrength=3, m_noJoinAtEnd=[False, False],
            m_noJoinAtMidEnds=[])),
        "m_pRefFaces": [
            _face(1, 0.0, 3670692),
            _face(2, -half, 3670176),
            _face(3, half, 3670176),
            _face(4, -core, 137887908),
        ],
        "m_embeddedTo": [], "m_wallRunTimeData": None,
        "m_keyRefOffset": 0.0, "m_locLineOffset": 0.0,
        "m_WallAttributesId": wall_type_id,
        "m_upToLevelId": -1,
        "m_analyticalProjectionSurfaceId": -9,
        "m_analyticalTopPlane": -12, "m_analyticalBottomPlane": -12,
        "m_contFootingId": -1,
        "m_curtainAuxData": {"m_mullionTdFlags": 0},
        "m_version": 5, "m_subWallGridIdInType": -1,
        "m_wallStructuralUsage": 0, "m_wallKeyRef": 0, "m_wallCrossSection": 1,
        "m_isFlipped": False, "m_isStructuralSignificant": False,
        "m_oUserData": None, "m_oDefiningFaceRefs": None,
    })
    hdr = _element_header(schema, category=_WALLS_CATEGORY, class_name="SWall",
                          flags4=6441)
    return hdr, obj


# ===========================================================================
# 5. the SpecimenSet replacement
# ===========================================================================

class ConstructedSpecimens:
    """Drop-in for ``tools/ifc_intent.py SpecimenSet`` built ENTIRELY from
    constructed content -- no ancestor / donor file is read.

    Constructed against the BUNDLED BASE's own facts (its schema, level,
    wall type + compound-structure thickness, phase set); the encoded
    template records are injected into each build ``Document`` exactly like
    the old specimen records, then cloned + rewritten by the unchanged
    ``rvt.mutate`` / stage code."""

    #: template ids: far above any real id in the base lineage, never emitted
    WALL_TID = 990000001
    INSTANCE_TID = 990000002

    def __init__(self, source_path: str = CONSTRUCTED,
                 base_path: Optional[str] = None):
        if source_path not in (None, "", CONSTRUCTED):
            raise StandaloneError(
                f"ConstructedSpecimens takes no source file (got {source_path!r})")
        self.source_path = "(constructed -- no specimen file)"
        bp = base_path or bundled_base_path()
        from ..mutate import Document
        base_doc = Document.from_file(bp)
        schema = base_doc.dec.schema
        install_schema(bp)                       # decoder/encoder singletons ready
        lv = base_doc.levels()
        stories = [l for l in lv if l.get("is_building_story")] or lv
        if not stories:
            raise StandaloneError("the base carries no Level to build on")
        level_id = int(min(stories, key=lambda l: abs(float(l.get("elevation_ft", 0.0))))["id"])
        # the project-phase class is ProjectPhase; "Phase" matches nothing
        phases = sorted(base_doc.ids_of_class("ProjectPhase"))
        phase_id = int(phases[-1]) if phases else -1   # 'New Work' convention
        wt_ids = base_doc.ids_of_class("BasicWallType")
        self.wall_type = int(wt_ids[0]) if wt_ids else None
        thickness = 0.4
        shell = 0.0
        if self.wall_type is not None:
            thickness, shell = _wall_type_thickness(base_doc, self.wall_type)
        self.level_id = level_id
        self.phase_id = phase_id
        self._records: Dict[int, Dict[int, Any]] = {}
        self.instance_id: Optional[int] = self.INSTANCE_TID
        self.instance_symbol: Optional[int] = None       # constructed: no residue to repoint
        self.instance_category: Optional[int] = _ELECTRICAL_EQUIPMENT
        self.wall_id: Optional[int] = None
        h, o = family_instance_template(schema, elem_id=self.INSTANCE_TID,
                                        level_id=level_id, phase_id=phase_id)
        self._add_template(schema, self.INSTANCE_TID, "ElementHeader", h,
                           "FamilyInstance", o)
        if self.wall_type is not None:
            self.wall_id = self.WALL_TID
            h, o = swall_template(schema, elem_id=self.WALL_TID, level_id=level_id,
                                  wall_type_id=self.wall_type,
                                  thickness_ft=thickness, shell_ft=shell,
                                  phase_id=phase_id)
            self._add_template(schema, self.WALL_TID, "ElementHeader", h, "SWall", o)

    # -- encoding ---------------------------------------------------------
    def _add_template(self, schema, eid: int, hdr_cls: str, hdr: Dict[str, Any],
                      obj_cls: str, obj: Dict[str, Any]) -> None:
        from ..objects import Record
        enc = _SCHEMA_STATE["encoder"]
        dec = _SCHEMA_STATE["decoder"]
        from ..mutate import record_stamp
        recs: Dict[int, Any] = {}
        for seq, cls_name, value in ((101, hdr_cls, hdr), (102, obj_cls, obj)):
            cid = enc.class_id_of(cls_name)
            body = enc.encode_object(cid, value)
            back = dec.decode_record(cid, body)
            if not back.clean:
                raise StandaloneError(
                    f"constructed {cls_name} template does not decode clean: "
                    f"{back.errors[:2]}")
            recs[seq] = Record(elem_id=eid, stamp=record_stamp(cid, body),
                               class_id=cid, body_size=2 + len(body),
                               payload=body, seg_offset=-1, trailer_ok=True)
        self._records[eid] = recs

    # -- the SpecimenSet contract ----------------------------------------
    def inject_into(self, target) -> Dict[str, Any]:
        injected = []
        for eid, recs in self._records.items():
            for seq, r in recs.items():
                target.idx[seq][eid] = r
            for seq in (101, 102, 103):
                target._decoded.pop((eid, seq), None)
            injected.append(eid)
        return {"source": self.source_path, "injected_ids": injected,
                "wall_specimen": self.wall_id, "wall_type": self.wall_type,
                "instance_specimen": self.instance_id,
                "instance_symbol": self.instance_symbol,
                "instance_category": self.instance_category,
                "constructed": True,
                "note": ("templates CONSTRUCTED from the schema + documented "
                         "generic shapes; no ancestor/donor file read, no "
                         "Autodesk-authored element cloned")}


def _wall_type_thickness(doc, wall_type_id: int) -> Tuple[float, float]:
    """(total thickness, exterior-shell width) of the base wall type, from its
    own compound structure."""
    v = doc.value(wall_type_id) or {}

    def _find_layers(x):
        if isinstance(x, dict):
            if "m_layers" in x and isinstance(x["m_layers"], list):
                return x["m_layers"]
            for xv in x.values():
                got = _find_layers(xv)
                if got is not None:
                    return got
        elif isinstance(x, list):
            for xv in x:
                got = _find_layers(xv)
                if got is not None:
                    return got
        return None

    layers = _find_layers(v) or []
    widths = [float((l.get("value") if isinstance(l, dict) and "value" in l else l
                     ).get("m_layerWidth", 0.0)) for l in layers if isinstance(l, dict)]
    total = sum(widths) or 0.4
    shell = widths[0] if len(widths) >= 3 else 0.0
    return total, shell


def make_specimens(source_path: Optional[str] = None,
                   base_path: Optional[str] = None):
    """SpecimenSet factory honouring the resolution order: an explicit real
    file wins (a user-supplied specimen source, loaded by the unchanged
    ``SpecimenSet``); otherwise CONSTRUCTED templates."""
    if source_path and source_path != CONSTRUCTED and os.path.isfile(source_path):
        orig = _ACTIVE.get("SpecimenSet")
        if orig is None:
            from ..frontdoor.build import load_ifc_room_module
            orig = load_ifc_room_module().SpecimenSet
        return orig(source_path)
    return ConstructedSpecimens(CONSTRUCTED, base_path=base_path)


# ===========================================================================
# 6. the family container from bundled assets (stage F, zero-donor)
# ===========================================================================

def standalone_family_write(product, path: str, *, validate: bool = True,
                            provenance: bool = True,
                            timestamp: Optional[int] = 0,
                            report_path: Optional[str] = None,
                            family_donor: Optional[str] = None) -> Dict[str, Any]:
    """``FamilyProduct.write`` with the container drawn from BUNDLED assets.

    Emission = ``famdoc_adoc.emit_family_rfa_v2`` with ``donor`` = the bundled
    genesis base (or a USER-SUPPLIED ``family_donor`` .rfa -- the hidden
    escape hatch): ``Formats/Latest`` = that file's copy of the per-release
    schema constant; ``Global/Latest`` = OUR AUTHORED family ADocument;
    everything else OURS.  Validation = family-mode arbiter; provenance =
    ``provenance_scan_v2``.  Returns the same report shape
    ``tools/ifc_intent.stage_families`` consumes."""
    from ..famgen import famdoc_adoc as FA
    donor = family_donor or bundled_base_path()
    install_schema(None if family_donor else donor)
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    rep: Dict[str, Any] = {"path": path, "family": product.summary(),
                           "facts": product.facts.as_json(),
                           "container_source": donor,
                           "container_mode": ("user-donor" if family_donor
                                              else "bundled-base")}
    emit = FA.emit_family_rfa_v2(product.doc, path, donor=donor,
                                 timestamp=timestamp, write_reports=False)
    rep["emit"] = {k: v for k, v in emit.items() if k not in ("verify", "adocument")}
    rep["adocument"] = (emit.get("adocument") or {}).get("conclusion")
    rep["verify"] = emit.get("verify")
    if validate:
        try:
            val = FA.validate_family_file(path, with_donor_parity=False)
            rep["validate"] = {"ok": val.get("ok"),
                               "family_mode": val.get("family_mode"),
                               "arbiter_raw": val.get("arbiter_raw")}
        except Exception as e:                              # pragma: no cover
            rep["validate"] = {"ok": False, "error": repr(e)}
    if provenance:
        try:
            scan = FA.provenance_scan_v2(path, donor=donor)
            checks = scan.get("checks") or {}
            rep["provenance"] = {"ok": scan.get("ok"),
                                 "suspects": [k for k, v in checks.items() if not v],
                                 "verdict": scan.get("verdict"),
                                 "checks": checks}
        except Exception as e:                              # pragma: no cover
            rep["provenance"] = {"ok": False, "error": repr(e), "suspects": ["scan crashed"]}
    rep["ok"] = bool(rep["verify"] and rep["verify"].get("ok")
                     and (not validate or rep["validate"].get("ok"))
                     and (not provenance or rep["provenance"].get("ok")))
    rp = report_path or (os.path.splitext(path)[0] + ".json")
    with open(rp, "w") as fh:
        json.dump(rep, fh, indent=1, default=str)
    rep["report_path"] = rp
    return rep


# ===========================================================================
# 7. the research-input tripwire
# ===========================================================================

#: path fragments that mean a build is reading research-machine inputs
_RESEARCH_MARKERS = (os.sep + "extracted" + os.sep,
                     os.sep + "samples" + os.sep,
                     os.sep + "vendor" + os.sep)
_R5_MARKER = os.sep + "experiments" + os.sep + "genesis" + os.sep

#: Autodesk INSTALLATION directories -- reading these is banned outright
_AUTODESK_INSTALL_MARKERS = ("programdata" + os.sep + "autodesk",
                             "program files" + os.sep + "autodesk",
                             os.sep + "applications" + os.sep + "autodesk",
                             "family templates")

_GUARD: Dict[str, Any] = {"armed": False, "enabled": False, "hits": [], "allow": []}


def allow_research_inputs() -> None:
    """Disarm the tripwire (audit hooks cannot be removed; this no-ops it).
    Test/tooling affordance -- production activation leaves it armed."""
    _GUARD["enabled"] = False


def forbid_research_inputs(*, allow: Sequence[str] = ()) -> None:
    """Arm a process-wide audit hook: any file OPEN whose path names the
    research corpus (extracted/ | samples/ | vendor/ | experiments/genesis/)
    or an Autodesk installation directory raises ``StandaloneError`` --
    creation must run from bundled assets alone, and a regression fails RED
    instead of silently reading the research machine.  ``allow`` = absolute
    path prefixes exempted (the resolved bundled base is always exempt)."""
    _GUARD["allow"] = [os.path.abspath(a) for a in allow]
    try:
        _GUARD["allow"].append(os.path.abspath(bundled_base_path()))
    except Exception:
        pass
    _GUARD["enabled"] = True
    if _GUARD["armed"]:
        return

    def hook(event: str, args) -> None:
        if event != "open" or not _GUARD["enabled"]:
            return
        p = args[0]
        if not isinstance(p, (str, bytes, os.PathLike)):
            return
        try:
            ap = os.path.abspath(os.fsdecode(p))
        except Exception:
            return
        low = ap.lower()
        if any(ap.startswith(a) for a in _GUARD["allow"]):
            return
        if any(m in low for m in _AUTODESK_INSTALL_MARKERS):
            _GUARD["hits"].append(ap)
            raise StandaloneError(
                f"BANNED: attempted read of an Autodesk installation path: {ap}")
        if any(m in low for m in _RESEARCH_MARKERS) or _R5_MARKER in low:
            _GUARD["hits"].append(ap)
            raise StandaloneError(
                f"standalone build touched a research-machine input: {ap} "
                "(the front door must build from bundled assets alone)")

    sys.addaudithook(hook)
    _GUARD["armed"] = True


# ===========================================================================
# 8. activation -- wire the resolvers into the unchanged build path
# ===========================================================================

_ACTIVE: Dict[str, Any] = {}


def activate(*, base_path: Optional[str] = None,
             family_donor: Optional[str] = None,
             guard: bool = False) -> Dict[str, Any]:
    """Make the EXISTING front door standalone-capable, without editing it:

    * :func:`install_schema` -- the corpus-schema chokepoints;
    * ``rvt.frontdoor.base.resolve_specimen_source`` -> :data:`CONSTRUCTED`
      when no real specimen file resolves (the R5 path stays first on the
      research machine, honouring bit-for-bit compatibility there);
    * the ifc-room module's ``SpecimenSet`` -> :func:`make_specimens`;
    * ``famgen.factory.FamilyProduct.write`` -> :func:`standalone_family_write`
      (container from the bundled base, or ``family_donor``);
    * optionally arms :func:`forbid_research_inputs`.

    These runtime reroutes are exactly the wiring the patch list in
    ``docs/inbox/standalone.md`` proposes to land in
    build.py / base.py / ifc_intent.py / famgen; until those patches are
    applied, calling ``activate()`` (as ``author_standalone`` and the tests
    do) provides the identical behaviour."""
    rep: Dict[str, Any] = {}
    bp = base_path or bundled_base_path()
    rep["base"] = bp
    rep["schema"] = install_schema(bp)

    from . import base as FB
    from . import build as B

    if not _ACTIVE.get("resolve_specimen_source"):
        orig_rss = FB.resolve_specimen_source

        def rss(explicit: Optional[str] = None, **kw) -> str:
            if explicit and explicit != CONSTRUCTED:
                return orig_rss(explicit, **kw)      # user-supplied file: their authority
            return CONSTRUCTED                       # DEFAULT: constructed, never R5

        FB.resolve_specimen_source = rss
        B.resolve_specimen_source = rss
        _ACTIVE["resolve_specimen_source"] = orig_rss
    rep["specimens"] = "CONSTRUCTED by default; a user-supplied --specimens file wins"

    R = B.load_ifc_room_module()
    if not _ACTIVE.get("SpecimenSet"):
        _ACTIVE["SpecimenSet"] = R.SpecimenSet

        def _spec_factory(source_path: str):
            return make_specimens(source_path, base_path=bp)

        R.SpecimenSet = _spec_factory
    rep["ifc_room.SpecimenSet"] = "make_specimens (constructed on the sentinel)"

    from ..famgen import factory as FF
    if not _ACTIVE.get("FamilyProduct.write"):
        _ACTIVE["FamilyProduct.write"] = FF.FamilyProduct.write

        def _write(self, path: str, **kw):
            kw.setdefault("family_donor", family_donor)
            return standalone_family_write(self, path, **kw)

        FF.FamilyProduct.write = _write
    rep["family_container"] = ("user-donor " + family_donor if family_donor
                               else "bundled-base (emit_family_rfa_v2)")

    if guard:
        forbid_research_inputs()
        rep["guard"] = "armed (research inputs + Autodesk install paths raise)"
    return rep


def author_standalone(**kwargs) -> Any:
    """``rvt.frontdoor.author`` with the standalone resolvers active.  The
    one-call entry the plugin skills should use: creation works from bundled
    assets alone, zero donor files."""
    family_donor = kwargs.pop("family_donor", None)
    guard = kwargs.pop("guard", False)
    base = kwargs.get("base")
    tv = kwargs.get("target_version")
    if base is None and tv is not None:
        # A NON-DEFAULT target release resolves through its registry slot
        # FIRST (resolve_base probes the plugin bundle by basename), so the
        # bundled per-release base -- not the default one -- becomes the
        # explicit base.  A PENDING slot keeps base=None: the default base
        # resolves below and the front door degrades honestly (the fallback
        # line + the IFC addition).  Any other resolution failure (pin
        # mismatch, missing file) propagates RED.
        from . import release_ctx as RC
        from .base import BaseNotCertified, resolve_base
        try:
            if int(tv) != RC.native_release():
                base = resolve_base(target_release=int(tv)).path
        except BaseNotCertified:
            base = None
    rep = activate(base_path=base, family_donor=family_donor, guard=guard)
    # resolve_base() alone would miss the plugin bundle location (its pinned
    # candidates are the repo path + <plugin>/lib/genesis); passing the
    # resolved bundled path explicitly keeps the pin check (sha256 equality
    # marks it certified) without editing base.py.
    kwargs.setdefault("base", rep["base"])
    from . import author
    return author(**kwargs)


# ===========================================================================
# 9. the dependency table (problem A's answer, as data)
# ===========================================================================

def dependency_table() -> List[Dict[str, str]]:
    """{creation feature: source-before -> source-now} -- the audit that
    proves the front door needs the research machine for NOTHING."""
    return [
        {"feature": "project-side schema (every ObjectDecoder()/ObjectEncoder()/"
                    "ADocument codec default)",
         "before": "extracted/racbasicsampleproject/Formats__Latest.gz/000.bin "
                   "(research corpus; FileNotFoundError in the field)",
         "now": "parsed from the bundled base's own Formats/Latest "
                "(byte-identical constant, sha256 6459a9a9...)"},
        {"feature": "genesis base (the document authored on)",
         "before": "experiments/genesis/subst_k4/compose/G_ABPD.rvt (repo path "
                   "only; the plugin bundle location was never probed)",
         "now": "<plugin>/assets/genesis/G_ABPD.rvt (sha256-pinned) / "
                "$RVT_GENESIS_BASE / --base"},
        {"feature": "wall clone template (stage W scaffolding)",
         "before": "experiments/genesis/R5.rvt SWall specimen (Autodesk-lineage "
                   "joined wall, cloned + cleaned)",
         "now": "CONSTRUCTED SWall template (schema defaults + generic box "
                "topology; unjoined by construction; base's own wall type "
                "thickness)"},
        {"feature": "equipment instance clone template (stage E scaffolding)",
         "before": "experiments/genesis/R5.rvt FamilyInstance specimen (a door)",
         "now": "CONSTRUCTED free-standing FamilyInstance template (schema "
                "defaults; every placement-bearing field overwritten by the "
                "unchanged build code)"},
        {"feature": "family container: Formats/Latest of a new .rfa",
         "before": "vendor/phi-ag-rvt/.../racbasicsamplefamily-2026.rfa "
                   "(Autodesk sample family, raw stream carried)",
         "now": "the bundled base's Formats/Latest (PROVEN byte-identical "
                "project vs family; counsel C4 stream)"},
        {"feature": "family container: Global/Latest ADocument of a new .rfa",
         "before": "the donor .rfa's ADocument byte-for-byte (v1 emit) / the "
                   "donor's decoded tree as authoring shape (v2)",
         "now": "OUR AUTHORED family ADocument: author_family_adocument seeded "
                "from the bundled base's decoded tree, purged, repopulated over "
                "OUR inventory (provenance_scan_v2 all-clean)"},
        {"feature": "family container: partition footer / end record",
         "before": "opaque bytes copied from the donor (v1)",
         "now": "OUR footer (build_footer) + the decoded 10-byte end-record "
                "constant (already famdoc_adoc; unchanged)"},
        {"feature": "family registry-semantics maps (UET fill)",
         "before": "experiments/genesis/G1_registry_maps.json (research file, "
                   "optional)",
         "now": "same file when present; the built-in fallback otherwise "
                "(PROVEN sufficient: family-mode VALID 0 errors without it)"},
        {"feature": "feeder circuits (stage C)",
         "before": "no circuit specimen anywhere (named blocker)",
         "now": "unchanged: still a NAMED BLOCKER (RbsElectricalSystem "
                "constructor is electrical-stream territory); the resolved "
                "circuit plan rides in the manifest"},
    ]


if __name__ == "__main__":                                # pragma: no cover
    print(json.dumps({"base": bundled_base_path(),
                      "schema": install_schema(),
                      "identity": {k: v for k, v in schema_identity_report().items()
                                   if k != "mismatches"}}, indent=1, default=str))
