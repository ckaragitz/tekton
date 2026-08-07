"""objlint.py -- THE CONSTRUCTED-OBJECT LINTER.

WHY THIS EXISTS (docs/inbox/genesis-audit.md, ORCHESTRATOR VERDICTS #9): every
file whose element records are CLONED / VERBATIM / byte-exact reproductions
of real Autodesk objects LOADS in Autodesk's own reader (35+ certified files:
K1, the R-controls, L1a, T_conduit_types); EVERY file carrying our
FROM-SCRATCH CONSTRUCTED objects -- the genesis settings singletons, our
built-in style catalog rows, house-standard content, built field-by-field
over schema blanks with OUR values -- FAILS with "Revit-DocumentCorruption:
The file is corrupt" (X5, X9, R1, R2, R3, S1..S5, K5a, K5d, the G1 set),
while our own validator calls all of them VALID.  The reader audits
something our validator does not.  Rather than discovering the constraints
one viewer-hour at a time, this module MINES them from the corpus.

THREE STAGES

1. SPECIMEN INVARIANT MINING (:func:`mine_all` -> ``experiments/genesis/
   lint/invariants/<class>.json``).  For every class our constructors emit
   (``rvt.genesis.{settings,catalog,types,skeleton,house_standard}``), decode
   ALL host-document specimens of that class across the six 2026 samples
   (61,139 records, 119 classes) -- the seq-102 object, its seq-101
   ``ElementHeader``, its ``Global/ElemTable`` row (owner + owned children)
   and its seq-103 representation class -- and mine per-field invariants
   over a schema-parallel FLATTENING of each object:
     * never-null fields (null in 0/N specimens), always-null fields
     * container LENGTHS that are CONSTANT (or the small observed set)
     * fields whose VALUE is IDENTICAL in every specimen (format constants
       we must copy exactly), enum / flag observed value SETS, numeric ranges
     * ElementId-typed fields: nullness AND the TARGET CLASS distribution
       (every positive id is resolved to its class in its own file; built-in
       negative ids stay literal), so "always points at a UnitsElem" is a rule
     * owned-pointer slots: sub-object PRESENT in N/N (and its class set)
     * the ElementHeader shape (m_parents list lengths, regen wildcards,
       ab / view flags, category), the seq-103 rep class, and the
       ElemTable-owned children classes.

2. THE LINTER (:func:`lint_object`) -> findings
   ``[{severity, field_path, rule, ours, specimens_say, support, ...}]``
   flagging every violation of a mined invariant by ONE constructed object.

3. RUN + REPORT (:func:`run` / ``__main__``): lints the constructed objects
   the reader REJECTED -- the substitution ladder's OURS (X5.rvt / X9.rvt id
   band >= 1,500,000; verdicts FAIL) and the census-complete S5.rvt (FAIL) --
   and CALIBRATES against the constructed / created objects the reader
   ACCEPTED (T_conduit_types.rvt = our from-scratch conduit / wire types,
   certified PASS; the V20/V21/V23/V29 created FamilyInstance / SWall /
   circuit elements, certified PASS): a rule those controls violate is
   provably NOT load-bearing and is marked so.  Writes
   ``docs/writer/objlint-report.md`` -- the top of it is the ranked bug list
   for the fix stream.

The linter reads the corpus + the probe files ONLY; it never edits any
constructor.  Reproduce (repo root)::

    .venv/bin/python -m rvt.objlint                 # mine + lint + report
    .venv/bin/python -m rvt.objlint --mine-only     # refresh the invariant corpus
    .venv/bin/python -m rvt.objlint --no-mine       # lint from the cached corpus
    .venv/bin/python -m rvt.objlint --classes GStyleElem,PenWidthTableElem

Public API::

    inv = mine_class("GStyleElem")                  # ClassInvariants
    findings = lint_object("GStyleElem", obj, header)   # dicts, ranked
    corpus = load_invariants()                      # {class|cohort: ClassInvariants}
"""
from __future__ import annotations

import argparse
import collections
import dataclasses
import json
import math
import os
import sys
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.path.join(ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src"))

LINT_DIR = os.path.join(ROOT, "experiments", "genesis", "lint")
INV_DIR = os.path.join(LINT_DIR, "invariants")
REPORT_MD = os.path.join(ROOT, "docs", "writer", "objlint-report.md")
RECORD_MD = os.path.join(ROOT, "docs", "inbox", "genesis-lint.md")

SAMPLES = [
    "rstbasicsampleproject", "rstadvancedsampleproject",
    "racbasicsampleproject", "racadvancedsampleproject",
    "rmebasicsampleproject", "dach-sample-project",
]
#: pristine-sample ElemTable watermarks (IdentifierSource.m_last): an element
#: whose id is ABOVE its base's watermark was CREATED by us (the acceptance
#: V-files).  Read from the corpus lazily by :func:`_pristine_watermark`.

INVALID = -1
NULL_GUID = "00000000-0000-0000-0000-000000000000"

# ---------------------------------------------------------------------------
# tunables
# ---------------------------------------------------------------------------
DISTINCT_CAP = 12          # track at most this many distinct values per path
ENUM_MAX = 8               # a value set of <= this many members can be an enum
ENUM_SATURATION = 3        # need n_seen >= ENUM_SATURATION * distinct
MIN_SUPPORT = 2            # specimens needed before ANY rule is emitted
STR_CAP = 160              # truncate strings in accumulators
OUR_ID_FLOOR = 1_500_000   # the substitution / genesis id band (ours >= this)

# rule-type base weights (multiplied by support / calibration factors)
RULE_WEIGHT = {
    "NEVER_NULL": 1.00, "PTR_PRESENT": 1.00, "SEQ103_CLASS": 0.95,
    "IDENTICAL": 0.90, "CONST_LEN": 0.90, "OWNED_CHILD": 0.85,
    "ENUM": 0.70, "LEN_SET": 0.60, "PTR_CLASS_SET": 0.60,
    "ALWAYS_NULL": 0.50, "PTR_ABSENT": 0.50, "STR_VOCAB": 0.40,
    "RANGE": 0.30,
}
SEVERITY_NAMES = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]


def log(msg: str) -> None:
    print(msg, flush=True)


# ===========================================================================
# 0. the class set our constructors emit
# ===========================================================================
#: The classes emitted by ``rvt.genesis.{settings,catalog,types,skeleton,
#: house_standard}`` -- enumerated by RUNNING the constructors (see
#: :func:`enumerate_constructor_classes`); this frozen list keeps the miner
#: independent of constructor churn.  ``FamilyInstance`` / ``SWall`` /
#: ``RbsElectricalSystem`` are appended as CONTROL classes: elements WE
#: created that the Autodesk viewer CERTIFIED (V20/V21/V23/V29), used to
#: calibrate the false-positive rate of every rule type.
CONSTRUCTOR_CLASSES: List[str] = sorted({
    # rvt.genesis.settings (the document-settings singletons + trackers)
    "PenWidthTableElem", "BrowserOrganization", "RbsDbViewSystemNavigator",
    "StructSettingsElem", "WallJoinDefaultSetting", "AutoJoinTracker",
    "KeynoteTable", "KeynotingSystem", "InitialViewSettings",
    "ReconcileBrowserSettingsElem", "ConstructionSetProject",
    "RbsWireSettingsElem", "RbsWireSizesElem", "RbsPipeSettingsElem",
    "RbsPipeSizesElem", "RbsDuctSettingsElem", "RbsDuctSizesElem",
    "ConduitSettingsElem", "CableTraySettingsElem", "AutoCamSettingsElem",
    "HalftoneUnderlaySettings", "MultipleValuesIndicationSettings",
    "DaylightSourceIdSet", "ExternalParamLock", "AllProjectRevisions",
    "ProjectRevision", "RevisionNumberingSequence",
    "WorksetVisibilitySettingsElem", "WorksharingViewModeSettings",
    "CoordinateSystemDisplayElem", "ActiveGeoLocationTrackingElement",
    "DefaultDivideSettings", "ProjectCopySettingsElem", "CopyWatchProperties",
    "Dwg2dExportUserSettingsData", "STEPExportSettings", "ModelGraphicsStyle",
    "GCSTracker", "AssemblyTracker", "LayoutNodesTracker", "MEPSystemTracker",
    "MEPComponentTracker", "MEPNetworkTracker", "KeynoteTagsOnSheetsTracker",
    "RevisionCloudsOnSheetsTracker", "SheetsInSheetCollectionTracker",
    "AnalyticalToPhysicalRelationManager", "ReactionsUpToDateElem",
    "AreaSettingsElem", "AreaMeasureElem", "EnergyDataSettings", "ZoneScheme",
    "ReinforcementSettings", "RouteAnalysisSettings",
    "MEPHiddenLineSettingsElem", "FabricationSettings",
    "FabricationServiceSettings", "FabricationSettingsElement",
    "CircuitNamingTypeSetting", "SSEPointVisibilitySettings",
    "StructuralConnectionSettings", "RvtLinkInstanceAppearanceParentElem",
    "SketchGridAppearanceParentElem", "CurtaSystemFaceManager", "PrintSettings",
    "ViewSheetSet", "GraphicsCache", "MEPNetworkDataElem", "DBViewType",
    "Viewer", "DBDrawing", "Viewport",
    # rvt.genesis.catalog / types / house_standard (type catalogs)
    "GStyleElem", "CategoryElem", "CustomElement", "RbsVoltageType",
    "MaterialElem", "BasicWallType", "ElectricalDemandFactorDefinition",
    "ElectricalLoadClassification", "RbsCableTrayType", "RbsConduitType",
    "RbsDistributionSysType", "CableTraySizesElem", "CompoundCeilingType",
    "ConduitSizesElem", "ConduitStandardType", "ElectricalSetting",
    "FillPatternElem", "FloorAttributes", "FontElem", "LinePatternElem",
    "RbsWireType", "RoofAttributes", "TextNoteAttributes",
    "RbsWireInsulationType", "RbsWireMaterialType",
    "RbsWireTemperatureRatingType",
    # rvt.genesis.skeleton / house_standard (the document skeleton)
    "PhaseFilterElem", "SunAndShadowSettings", "ExtentElem", "DBViewPlan",
    "Level", "ProjectPhase", "SketchPlane", "AllProjectPhases", "DBView3d",
    "DBViewProject", "LevelAttributes", "LightSchemeElement", "ModelClipBox",
    "ProjectInfo", "UnitsElem", "Viewer3d", "BasePoint", "GeoLocation",
    "GeoSite", "TrueNorth",
})
CONTROL_CLASSES: List[str] = ["FamilyInstance", "SWall", "RbsElectricalSystem"]
ALL_CLASSES: List[str] = sorted(set(CONSTRUCTOR_CLASSES) | set(CONTROL_CLASSES))


def enumerate_constructor_classes() -> Dict[str, List[str]]:
    """RUN every constructor entry point and return {module: [class names]}
    -- the live enumeration behind :data:`CONSTRUCTOR_CLASSES`."""
    out: Dict[str, List[str]] = {}
    from rvt.genesis.types import IdSource
    try:
        from rvt.genesis import settings as ST
        cat = ST.standard_settings(IdSource(9_000_000), tier="all",
                                   doc_ids={"units": 1, "document_sun": 2, "phase_new": 3,
                                            "phase_filter": 4, "geo_location": 5,
                                            "level1": 6, "phase_set": 7})
        out["settings"] = sorted({r.class_name for r in cat.records} | {"RbsPipeSizesElem", "ViewSheetSet"})
    except Exception as e:                                        # pragma: no cover
        out["settings"] = [f"<error {e!r}>"]
    try:
        from rvt.genesis import catalog as CAT
        out["catalog"] = sorted({r.class_name for r in CAT.builtin_style_catalog(IdSource(9_100_000))})
    except Exception as e:                                        # pragma: no cover
        out["catalog"] = [f"<error {e!r}>"]
    try:
        from rvt.genesis import types as TY
        out["types"] = sorted({r.class_name for r in TY.demo_catalog(9_200_000).records})
    except Exception as e:                                        # pragma: no cover
        out["types"] = [f"<error {e!r}>"]
    try:
        from rvt.genesis import skeleton as SK
        out["skeleton"] = sorted({e.class_name for e in SK.build_minimal_skeleton().elements})
    except Exception as e:                                        # pragma: no cover
        out["skeleton"] = [f"<error {e!r}>"]
    try:
        from rvt.genesis import house_standard as HS
        out["house_standard"] = sorted({r.class_name for r in HS.build_catalog(9_300_000).records})
    except Exception as e:                                        # pragma: no cover
        out["house_standard"] = [f"<error {e!r}>"]
    return out


# ---------------------------------------------------------------------------
# cohorts: split a class's specimens where two populations differ by rule
# ---------------------------------------------------------------------------
#: {class: [(cohort_name, predicate(value_dict, header_dict) -> bool)]}
#: The FIRST matching predicate names the cohort; no match -> "" (all).
#: Splitting keeps two structurally different populations from diluting
#: each other's invariants (a project pen table vs a curtain family's; a
#: built-in-category style row vs a sub-category row; a project view type
#: vs a family-scoped one).
def _famid(v):
    return v.get("m_famId", INVALID)


COHORTS: Dict[str, List[Tuple[str, Callable[[dict, dict], bool]]]] = {
    "PenWidthTableElem": [
        ("project", lambda v, h: _famid(v) == INVALID),
        ("family-scoped", lambda v, h: _famid(v) not in (None, INVALID)),
    ],
    "DBViewType": [
        ("project", lambda v, h: _famid(v) == INVALID),
        ("family-scoped", lambda v, h: _famid(v) not in (None, INVALID)),
    ],
    "GStyleElem": [
        ("builtin", lambda v, h: v.get("m_ownerId", INVALID) == INVALID),
        ("subcategory", lambda v, h: v.get("m_ownerId", INVALID) != INVALID),
    ],
    "CategoryElem": [
        ("builtin-parent", lambda v, h: (v.get("m_parentId", INVALID) or 0) < 0),
        ("nested", lambda v, h: (v.get("m_parentId", INVALID) or 0) >= 0),
    ],
    "SketchPlane": [
        ("family-owned", lambda v, h: _famid(v) not in (None, INVALID)),
        ("project", lambda v, h: _famid(v) == INVALID),
    ],
}


def cohort_of(class_name: str, value: dict, header: Optional[dict] = None) -> str:
    for name, pred in COHORTS.get(class_name, ()):
        try:
            if pred(value or {}, header or {}):
                return name
        except Exception:                                          # pragma: no cover
            continue
    return ""


# ===========================================================================
# 1. schema-parallel FLATTENING of a decoded object -> typed leaves
# ===========================================================================

@dataclasses.dataclass
class Leaf:
    """One observation from a decoded object.  ``path`` is index-normalized
    (growable containers collapse to ``f[]`` + a synthetic ``f.#len``;
    fixed arrays keep their index; owned pointers add a synthetic
    ``f.#ptr`` holding the concrete class name)."""
    path: str
    ftype: str          # bool int float str guid eid weak ptr len classref vec other
    value: Any          # the (tokenized) value


class Flattener:
    """Walk a decoded value dict IN PARALLEL WITH THE ARCHIVE CLASS MAP and
    yield :class:`Leaf` observations.  Mirrors ``rvt.objects.ObjectDecoder``
    field for field, so every dict key the decoder produced is visited with
    its true schema type (an int under an ElementId-typed field is an id, an
    int under an ``m_geomSteps`` counter is not)."""

    def __init__(self, decoder=None):
        if decoder is None:
            from .objects import ObjectDecoder
            decoder = ObjectDecoder()
        self.dec = decoder
        self.eid_types = {t for t in (decoder.id_ElementId, decoder.id_Identifier) if t}

    #: body leaves that are tautological (the element's own id) -- never mined
    SKIP_PATHS = {"m_id"}

    # -- public --------------------------------------------------------------
    def flatten(self, class_name: str, value: dict, prefix: str = "",
                resolve: Optional[Callable[[int], str]] = None) -> List[Leaf]:
        """All leaves of ``value`` (a body of ``class_name``).  ``resolve``
        maps a positive ElementId to its target class token (``'@Level'``);
        unresolvable -> ``'@?'``."""
        cd = self.dec.schema.by_name.get(class_name)
        if cd is None or not isinstance(value, dict):
            return []
        out: List[Leaf] = []
        self._walk_class(value, cd.type_id, prefix, out, resolve or (lambda i: "@?"), 0)
        return [lf for lf in out if lf.path not in self.SKIP_PATHS]

    # -- walk ----------------------------------------------------------------
    def _walk_class(self, value: dict, type_id: int, path: str, out: List[Leaf],
                    resolve, depth: int) -> None:
        if not isinstance(value, dict) or depth > 40:
            return
        from .objects import field_key
        seen: dict = {}
        for cd in self.dec.chain(type_id):
            for f in cd.fields:
                key = field_key(cd, f, seen)
                seen[key] = True
                if key not in value:
                    continue
                fp = f"{path}.{key}" if path else key
                self._walk_field(value[key], f, fp, out, resolve, depth)

    def _walk_field(self, v, f, fpath: str, out: List[Leaf], resolve, depth: int) -> None:
        kind, flags = f.kind, f.flags
        shape, indir = flags >> 4, flags & 0x0F
        if kind == 0x08:                                     # AString(s)
            if shape in (0x5, 0x1):
                self._container(v, f, fpath, out, resolve, depth, fixed=(shape == 0x1),
                                scalar=lambda x, p: out.append(Leaf(p, "str", _tok_str(x))))
            else:
                out.append(Leaf(fpath, "str", _tok_str(v)))
            return
        if kind == 0x0D:                                     # inline array wrapper
            elem = f.element
            if elem is None:
                out.append(Leaf(fpath, "other", type(v).__name__))
                return
            if shape == 0x1:                                 # fixed array of elements
                if isinstance(v, list):
                    for i, x in enumerate(v):
                        self._walk_field(x, elem, f"{fpath}[{i}]", out, resolve, depth + 1)
                return
            if isinstance(v, list):                          # counted array
                out.append(Leaf(f"{fpath}.#len", "len", len(v)))
                for x in v:
                    self._walk_field(x, elem, f"{fpath}[]", out, resolve, depth + 1)
            return
        if shape == 0x5:                                     # growable container
            self._container(v, f, fpath, out, resolve, depth, fixed=False, scalar=None)
            return
        if shape == 0x1:                                     # fixed array
            self._container(v, f, fpath, out, resolve, depth, fixed=True, scalar=None)
            return
        self._scalar(v, f, fpath, out, resolve, depth)

    def _container(self, v, f, fpath, out, resolve, depth, *, fixed: bool, scalar) -> None:
        if not isinstance(v, list):
            out.append(Leaf(fpath, "other", "notalist"))
            return
        if not fixed:
            out.append(Leaf(f"{fpath}.#len", "len", len(v)))
        for i, x in enumerate(v):
            p = f"{fpath}[{i}]" if fixed else f"{fpath}[]"
            if scalar is not None:
                scalar(x, p)
            else:
                self._scalar(x, f, p, out, resolve, depth + 1)

    def _scalar(self, x, f, xpath: str, out: List[Leaf], resolve, depth: int) -> None:
        kind, indir = f.kind, f.flags & 0x0F
        if kind == 0x01:
            out.append(Leaf(xpath, "bool", bool(x)))
            return
        if kind in (0x02, 0x03, 0x04, 0x05, 0x0B):
            out.append(Leaf(xpath, "int", _num(x)))
            return
        if kind in (0x06, 0x07):
            out.append(Leaf(xpath, "float", _num(x)))
            return
        if kind == 0x08:
            out.append(Leaf(xpath, "str", _tok_str(x)))
            return
        if kind == 0x09:
            out.append(Leaf(xpath, "guid", _tok_guid(x)))
            return
        if kind == 0x0A:                                     # class-definition ref
            out.append(Leaf(xpath, "classref", _tok_classref(x)))
            return
        if kind != 0x0E:
            out.append(Leaf(xpath, "other", type(x).__name__))
            return
        if indir == 0:                                       # inline value class
            tid = f.type_id
            if tid in self.eid_types:
                out.append(Leaf(xpath, "eid", _tok_eid(x, resolve)))
                return
            if tid in (self.dec.id_XYZ, self.dec.id_UV):
                out.append(Leaf(xpath, "vec", _tok_vec(x)))
                return
            if tid == self.dec.id_GUIDvalue:
                out.append(Leaf(xpath, "guid", _tok_guid(x)))
                return
            if isinstance(x, dict):
                self._walk_class(x, tid, xpath, out, resolve, depth + 1)
            else:
                out.append(Leaf(xpath, "other", type(x).__name__))
            return
        if indir == 3:                                       # weak reference
            n = x.get("weakref") if isinstance(x, dict) else None
            out.append(Leaf(xpath, "weak", "@weakref" if n else None))
            return
        # owned / polymorphic pointer
        if x is None:
            out.append(Leaf(f"{xpath}.#ptr", "ptr", None))
            return
        if isinstance(x, dict):
            if "backref_pid" in x:
                out.append(Leaf(f"{xpath}.#ptr", "ptr", "@backref"))
                return
            pc = x.get("ptr_class")
            out.append(Leaf(f"{xpath}.#ptr", "ptr", str(pc) if pc else None))
            sub = x.get("value")
            cid = self.dec.schema.by_name.get(pc).type_id if pc in self.dec.schema.by_name else None
            if isinstance(sub, dict) and cid is not None:
                self._walk_class(sub, cid, f"{xpath}->{pc}", out, resolve, depth + 1)
            return
        out.append(Leaf(f"{xpath}.#ptr", "ptr", type(x).__name__))


# -- leaf value tokenizers ---------------------------------------------------
def _num(x):
    if isinstance(x, bool):
        return int(x)
    if isinstance(x, (int, float)):
        return x
    return x


def _tok_str(x) -> Optional[str]:
    if x is None or x == "":
        return None
    s = str(x)
    return s[:STR_CAP]


def _tok_guid(x) -> Optional[str]:
    if x is None:
        return None
    s = str(x)
    return None if s == NULL_GUID or set(s) <= {"0", "-"} else s


def _tok_classref(x) -> Optional[str]:
    if isinstance(x, dict):
        return str(x.get("classref"))
    return str(x) if x is not None else None


def _tok_vec(x) -> str:
    if isinstance(x, (list, tuple)):
        return "zero" if all(abs(float(c or 0.0)) < 1e-12 for c in x) else "nonzero"
    return "other"


def _tok_eid(x, resolve) -> Any:
    """ElementId leaf token: -1 -> None (null); other negative -> the literal
    built-in constant (int); positive -> ``resolve(id)`` ('@ClassName')."""
    if isinstance(x, bool) or not isinstance(x, int):
        return "@nonint"
    if x == INVALID:
        return None
    if x < 0:
        return int(x)                                        # built-in id constant
    try:
        return str(resolve(int(x)))
    except Exception:                                        # pragma: no cover
        return "@?"


NULL_TOKENS = (None, "null", 0)


def is_null_leaf(leaf: Leaf) -> bool:
    """A leaf is 'null' when: eid -1, ptr None, weak null, str empty/None,
    guid zero.  Numbers / bools / lens are never null."""
    t, v = leaf.ftype, leaf.value
    if t in ("eid", "ptr", "str", "guid", "weak"):
        return v is None
    return False


# ===========================================================================
# 2. accumulators + invariant derivation
# ===========================================================================

class _Acc:
    """Per-path statistics over N specimens.  ``n_seen`` counts leaf
    OBSERVATIONS (an element-level path under a container is observed once
    per element); ``present`` counts DISTINCT SPECIMENS in which the path
    occurred at least once (marked by :meth:`mark_present`)."""
    __slots__ = ("ftype", "n_seen", "n_null", "values", "overflow",
                 "num_min", "num_max", "files", "present")

    def __init__(self, ftype: str):
        self.ftype = ftype
        self.n_seen = 0
        self.n_null = 0
        self.values: Dict[Any, int] = {}
        self.overflow = False
        self.num_min = None
        self.num_max = None
        self.files: Set[str] = set()
        self.present = 0

    def mark_present(self) -> None:
        self.present += 1

    def add(self, leaf: Leaf, src: str) -> None:
        self.n_seen += 1
        self.files.add(src)
        if is_null_leaf(leaf):
            self.n_null += 1
            tok = "NULL"
        else:
            tok = _hashable(leaf.value)
        v = leaf.value
        if leaf.ftype in ("int", "float", "len") and isinstance(v, (int, float)) \
                and not isinstance(v, bool) and not (isinstance(v, float) and math.isnan(v)):
            self.num_min = v if self.num_min is None else min(self.num_min, v)
            self.num_max = v if self.num_max is None else max(self.num_max, v)
        # keep counting values we already track (dominant-value statistics
        # stay accurate); only refuse NEW keys once the cap is reached
        if tok in self.values:
            self.values[tok] += 1
        elif len(self.values) < DISTINCT_CAP:
            self.values[tok] = 1
        else:
            self.overflow = True

    def to_json(self) -> dict:
        return {"ftype": self.ftype, "n_seen": self.n_seen, "n_null": self.n_null,
                "values": _values_json(self.values), "overflow": self.overflow,
                "num_min": self.num_min, "num_max": self.num_max,
                "files": sorted(self.files), "present": self.present}

    @classmethod
    def from_json(cls, d: dict) -> "_Acc":
        a = cls(d["ftype"])
        a.n_seen = d["n_seen"]
        a.n_null = d["n_null"]
        a.values = {_from_key(k): v for k, v in (d.get("values") or {}).items()}
        a.overflow = d.get("overflow", False)
        a.num_min = d.get("num_min")
        a.num_max = d.get("num_max")
        a.files = set(d.get("files") or [])
        a.present = d.get("present", a.n_seen)
        return a


def _hashable(v):
    if isinstance(v, list):
        return tuple(_hashable(x) for x in v)
    if isinstance(v, dict):
        return tuple(sorted((k, _hashable(x)) for k, x in v.items()))
    return v


def _values_json(values: dict) -> dict:
    return {_to_key(k): n for k, n in values.items()}


def _to_key(k) -> str:
    return json.dumps(k, default=str)


def _from_key(s: str):
    try:
        v = json.loads(s)
    except Exception:                                        # pragma: no cover
        return s
    if isinstance(v, list):
        return tuple(v)
    return v


@dataclasses.dataclass
class Rule:
    """One mined invariant on one path."""
    path: str
    rule: str                  # NEVER_NULL / IDENTICAL / CONST_LEN / ENUM / ...
    expect: Any                # the expectation (value / set / [min,max])
    support: int               # leaf observations supporting the rule (n_seen)
    files: int                 # distinct source files behind it
    total: int                 # specimens in the (class, cohort)
    ftype: str = ""
    scope: str = "body"        # body / header / elemtable / rep
    present: int = 0           # distinct specimens the path occurred in

    @property
    def presence(self) -> float:
        """Fraction of specimens in which the path exists (its coverage)."""
        return min(1.0, (self.present or self.support) / max(self.total, 1))

    def to_json(self) -> dict:
        d = dataclasses.asdict(self)
        d["expect"] = _json_safe(self.expect)
        return d

    @classmethod
    def from_json(cls, d: dict) -> "Rule":
        r = cls(d["path"], d["rule"], _expect_from_json(d["expect"], d["rule"]),
                d["support"], d["files"], d["total"], d.get("ftype", ""),
                d.get("scope", "body"), d.get("present", 0))
        return r


def _json_safe(v):
    if isinstance(v, set):
        return sorted((_json_safe(x) for x in v), key=lambda x: (str(type(x)), str(x)))
    if isinstance(v, tuple):
        return [_json_safe(x) for x in v]
    if isinstance(v, list):
        return [_json_safe(x) for x in v]
    return v


def _expect_from_json(e, rule: str):
    if rule in ("ENUM", "LEN_SET", "PTR_CLASS_SET", "STR_VOCAB") and isinstance(e, (list, set)):
        return set(_from_key(json.dumps(x)) if isinstance(x, list) else x for x in (e or []))
    if rule == "IDENTICAL" and isinstance(e, list):
        return tuple(e)
    return e


@dataclasses.dataclass
class ClassInvariants:
    """The mined invariant corpus for one (class, cohort)."""
    class_name: str
    cohort: str
    n_specimens: int
    per_file: Dict[str, int]
    rules: List[Rule]
    paths: Dict[str, dict]                 # raw per-path accumulator dumps
    seq103_classes: Dict[str, int] = dataclasses.field(default_factory=dict)
    owned_children: Dict[str, dict] = dataclasses.field(default_factory=dict)
    notes: List[str] = dataclasses.field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.class_name}|{self.cohort}" if self.cohort else self.class_name

    def to_json(self) -> dict:
        return {"class": self.class_name, "cohort": self.cohort,
                "n_specimens": self.n_specimens, "per_file": self.per_file,
                "seq103_classes": self.seq103_classes,
                "owned_children": self.owned_children,
                "rules": [r.to_json() for r in self.rules],
                "paths": self.paths, "notes": self.notes}

    @classmethod
    def from_json(cls, d: dict) -> "ClassInvariants":
        return cls(d["class"], d.get("cohort", ""), d["n_specimens"],
                   d.get("per_file") or {}, [Rule.from_json(r) for r in d.get("rules") or []],
                   d.get("paths") or {}, d.get("seq103_classes") or {},
                   d.get("owned_children") or {}, d.get("notes") or [])


def _is_element_path(path: str) -> bool:
    """True for paths whose observations are container ELEMENTS (they can
    outnumber the specimens) as opposed to one-per-specimen fields."""
    return "[]" in path


def derive_rules(accs: Dict[str, _Acc], n_total: int, *,
                 scope_of: Optional[Callable[[str], str]] = None) -> List[Rule]:
    """Turn per-path accumulators into invariant rules.

    ``present`` (distinct specimens the path occurred in) drives
    universality: a specimen-level path is UNIVERSAL when present == n_total.
    Element-level paths (under a growable container, marked ``[]``) carry
    per-element rules over ``n_seen`` observations, but must still occur in
    enough distinct specimens (``present``) to generalise.
    """
    rules: List[Rule] = []
    if n_total < MIN_SUPPORT:
        return rules
    for path, a in accs.items():
        n = a.n_seen
        pres = a.present or n                       # legacy accumulators
        if n < MIN_SUPPORT or pres < MIN_SUPPORT:
            continue
        scope = scope_of(path) if scope_of else "body"
        universal = pres >= n_total                 # path exists in EVERY specimen
        elem_path = _is_element_path(path)
        vals = {k: c for k, c in a.values.items() if k != "NULL"}
        distinct = len(vals) + (1 if a.n_null else 0)

        def _mk(kind, expect):
            return Rule(path, kind, expect, n, len(a.files), n_total, a.ftype, scope, pres)

        # -- nullability ------------------------------------------------------
        if a.ftype in ("eid", "ptr", "str", "guid", "weak"):
            if a.n_null == 0:
                rules.append(_mk("PTR_PRESENT" if a.ftype == "ptr" else "NEVER_NULL",
                                 "non-null"))
            elif a.n_null == n and universal:
                rules.append(_mk("PTR_ABSENT" if a.ftype == "ptr" else "ALWAYS_NULL", "null"))
        # -- length rules -----------------------------------------------------
        if a.ftype == "len":
            lens = {int(k) for k in vals if isinstance(k, (int, float))}
            if not a.overflow and len(lens) == 1:
                rules.append(_mk("CONST_LEN", next(iter(lens))))
            elif not a.overflow and 1 < len(lens) <= ENUM_MAX \
                    and n >= ENUM_SATURATION * len(lens) and pres >= 3:
                rules.append(_mk("LEN_SET", set(lens)))
            elif a.num_min is not None and pres >= 3:
                rules.append(_mk("RANGE", [a.num_min, a.num_max]))
            continue
        # -- identical (a non-null constant) ----------------------------------
        # specimen-level paths need universality; element-level paths need
        # every observed element identical across >= 3 specimens.
        if not a.overflow and a.n_null == 0 and len(vals) == 1 and n >= 3 \
                and (universal or (elem_path and pres >= 3)):
            (val,) = vals.keys()
            rules.append(_mk("IDENTICAL", val))
            continue
        # -- enum / vocabulary -----------------------------------------------------
        if not a.overflow and 1 < distinct <= ENUM_MAX \
                and n >= ENUM_SATURATION * distinct and pres >= 3:
            allowed = set(vals.keys()) | ({None} if a.n_null else set())
            kind = "PTR_CLASS_SET" if a.ftype == "ptr" else ("STR_VOCAB" if a.ftype == "str" else "ENUM")
            rules.append(_mk(kind, allowed))
            continue
        # -- numeric range -------------------------------------------------------
        if a.ftype in ("int", "float") and a.num_min is not None and n >= 3 and pres >= 3:
            rules.append(_mk("RANGE", [a.num_min, a.num_max]))
    return rules


def _scope_of_path(path: str) -> str:
    if path.startswith("HDR."):
        return "header"
    if path.startswith("ETR."):
        return "elemtable"
    if path.startswith("REP."):
        return "rep"
    return "body"


# ===========================================================================
# 3. corpus specimen collection + mining
# ===========================================================================

class SpecimenSource:
    """One sample project loaded from the pre-extracted corpus (or a .rvt
    file on disk) with the lookups the miner needs: class of any id,
    ElemTable rows, owned children, the seq-101/102/103 records."""

    def __init__(self, doc, name: str):
        self.doc = doc
        self.name = name
        self.et_by_id = doc.et_by_id
        # owner -> [child ids] from the ElemTable
        self.children: Dict[int, List[int]] = collections.defaultdict(list)
        for r in doc.et.records:
            if r.owner_id not in (0xFFFFFFFFFFFFFFFF, INVALID):
                self.children[int(r.owner_id)].append(int(r.id))
        self._cls_cache: Dict[int, str] = {}

    @classmethod
    def load_sample(cls, project: str) -> "SpecimenSource":
        from .mutate import Document
        return cls(Document.load(project), project)

    @classmethod
    def load_file(cls, path: str) -> "SpecimenSource":
        from .mutate import Document
        return cls(Document.from_file(path), os.path.basename(path))

    # -- lookups ---------------------------------------------------------------
    def class_of(self, eid: int) -> str:
        c = self._cls_cache.get(eid)
        if c is None:
            c = self.doc.class_of(int(eid)) or "ABSENT"
            self._cls_cache[eid] = c
        return c

    def resolve(self, eid: int) -> str:
        return "@" + self.class_of(eid)

    def host_ids_of(self, class_name: str) -> List[int]:
        cd = self.doc.dec.schema.by_name.get(class_name)
        if cd is None:
            return []
        return sorted(i for i, r in self.doc.idx[102].items()
                      if r.class_id == cd.type_id and i in self.et_by_id)

    def object(self, eid: int, seq: int = 102) -> Tuple[Optional[dict], bool]:
        """(decoded value, clean) for record ``eid`` in ``seq``."""
        r = self.doc.idx[seq].get(eid)
        if r is None:
            return None, False
        o = self.doc.dec.decode_record(r.class_id, r.payload)
        return o.value, bool(o.clean or o.stub)

    def rep_class(self, eid: int) -> str:
        r = self.doc.idx[103].get(eid)
        if r is None:
            return "MISSING"
        return self.doc.dec.class_name(r.class_id)

    def elemrec_leaves(self, eid: int) -> List[Leaf]:
        """The ElemTable-row features of ``eid`` -- the reader's view of the
        ADD path: is the row owned (and by what class), the classes of the
        rows it owns, and its LIFECYCLE vintage: creation episode (0 == born
        with the document), id magnitude band, renumbering, partition."""
        out: List[Leaf] = []
        er = self.et_by_id.get(eid)
        if er is None:
            return out
        owned = er.owner_id not in (0xFFFFFFFFFFFFFFFF, INVALID)
        out.append(Leaf("ETR.has_owner", "bool", bool(owned)))
        out.append(Leaf("ETR.owner_class", "eid",
                        self.resolve(er.owner_id) if owned else None))
        kids = self.children.get(int(eid), [])
        out.append(Leaf("ETR.owned.#len", "len", len(kids)))
        for k in kids:
            out.append(Leaf("ETR.owned[]", "eid", self.resolve(k)))
        # lifecycle / add-path vintage
        out.append(Leaf("ETR.created_at_birth", "bool", int(er.creation_ep) == 0))
        out.append(Leaf("ETR.id_band", "classref", id_band(int(er.id))))
        out.append(Leaf("ETR.renumbered", "bool", int(er.original_id) != int(er.id)))
        out.append(Leaf("ETR.usermod_never", "bool", int(er.user_modified_ep) == 0xFFFFFFFF))
        out.append(Leaf("ETR.partition_id", "int", int(er.partition_id)))
        return out


def id_band(eid: int) -> str:
    """Order-of-magnitude bucket of an ElementId (built-in styles and
    document-birth singletons live in the low bands of every real file)."""
    n = abs(int(eid))
    for thr, name in ((5_000, "<5k"), (50_000, "<50k"), (500_000, "<500k"),
                      (5_000_000, "<5M")):
        if n < thr:
            return name
    return ">=5M"


def specimen_leaves(src: SpecimenSource, eid: int, flat: Flattener,
                    class_name: str) -> Optional[Tuple[List[Leaf], str, dict, dict]]:
    """Every leaf of specimen ``eid`` (body + header + elemtable + rep) plus
    its cohort.  Returns None if the body does not decode cleanly."""
    body, clean = src.object(eid, 102)
    if body is None or not clean:
        return None
    hdr, hclean = src.object(eid, 101)
    leaves = flat.flatten(class_name, body, resolve=src.resolve)
    if hdr is not None and hclean:
        leaves += flat.flatten("ElementHeader", hdr, prefix="HDR", resolve=src.resolve)
    leaves += src.elemrec_leaves(eid)
    leaves.append(Leaf("REP.seq103_class", "classref", src.rep_class(eid)))
    return leaves, cohort_of(class_name, body, hdr), body, (hdr or {})


def mine_from_sources(class_name: str, sources: Sequence[SpecimenSource],
                      flat: Flattener, *, max_per_file: int = 0
                      ) -> Dict[str, ClassInvariants]:
    """Mine every host specimen of ``class_name`` from ``sources``.
    Returns {cohort_or_'': ClassInvariants} (cohort keys per :data:`COHORTS`;
    the '' entry aggregates ALL specimens)."""
    accs: Dict[str, Dict[str, _Acc]] = collections.defaultdict(dict)
    n_spec: Dict[str, int] = collections.Counter()
    per_file: Dict[str, Dict[str, int]] = collections.defaultdict(collections.Counter)
    rep_classes: Dict[str, Dict[str, int]] = collections.defaultdict(collections.Counter)
    #: {cohort: Counter(child_class -> N specimens owning >=1 such child)}
    owned_children: Dict[str, Dict[str, int]] = collections.defaultdict(collections.Counter)
    for src in sources:
        ids = src.host_ids_of(class_name)
        if max_per_file and len(ids) > max_per_file:
            step = len(ids) / float(max_per_file)
            ids = [ids[int(i * step)] for i in range(max_per_file)]
        for eid in ids:
            got = specimen_leaves(src, eid, flat, class_name)
            if got is None:
                continue
            leaves, cohort, _body, _hdr = got
            keys = [""] + ([cohort] if cohort else [])
            child_classes = {str(lf.value) for lf in leaves
                             if lf.path == "ETR.owned[]" and lf.value is not None}
            for ck in keys:
                n_spec[ck] += 1
                per_file[ck][src.name] += 1
                bucket = accs[ck]
                seen_paths: Set[str] = set()
                for lf in leaves:
                    a = bucket.get(lf.path)
                    if a is None:
                        a = bucket[lf.path] = _Acc(lf.ftype)
                    a.add(lf, src.name)
                    seen_paths.add(lf.path)
                    if lf.path == "REP.seq103_class":
                        rep_classes[ck][str(lf.value)] += 1
                for p in seen_paths:                            # per-specimen presence
                    bucket[p].mark_present()
                for cc in child_classes:
                    owned_children[ck][cc] += 1
    out: Dict[str, ClassInvariants] = {}
    for ck, bucket in accs.items():
        n_total = n_spec[ck]
        rules = derive_rules(bucket, n_total, scope_of=_scope_of_path)
        rules += _owned_child_rules(owned_children.get(ck, {}), n_total)
        inv = ClassInvariants(
            class_name=class_name, cohort=ck, n_specimens=n_total,
            per_file=dict(per_file[ck]),
            rules=rules,
            paths={p: a.to_json() for p, a in sorted(bucket.items())},
            seq103_classes=dict(rep_classes.get(ck, {})),
            owned_children=dict(owned_children.get(ck, {})),
        )
        out[ck] = inv
    return out


def _owned_child_rules(child_counts: Dict[str, int], n_total: int) -> List[Rule]:
    """A child class owned by EVERY specimen (per-specimen presence count >=
    n_total) is an OWNED_CHILD rule: our element must own one too."""
    rules: List[Rule] = []
    for cls_tok, cnt in child_counts.items():
        if n_total >= 3 and cnt >= n_total:
            rules.append(Rule("ETR.owned[]", "OWNED_CHILD", cls_tok, cnt, 0, n_total,
                              "eid", "elemtable", cnt))
    return rules


# ---------------------------------------------------------------------------
# persistence
# ---------------------------------------------------------------------------

def _inv_path(key: str) -> str:
    safe = key.replace("|", "__")
    return os.path.join(INV_DIR, f"{safe}.json")


def save_invariants(invs: Iterable[ClassInvariants]) -> List[str]:
    os.makedirs(INV_DIR, exist_ok=True)
    written = []
    for inv in invs:
        p = _inv_path(inv.key)
        with open(p, "w") as fh:
            json.dump(inv.to_json(), fh, indent=1, default=str)
        written.append(p)
    return written


def load_invariants(classes: Optional[Iterable[str]] = None) -> Dict[str, ClassInvariants]:
    """{key: ClassInvariants} from ``INV_DIR`` (key = class or class|cohort)."""
    out: Dict[str, ClassInvariants] = {}
    if not os.path.isdir(INV_DIR):
        return out
    want = set(classes) if classes else None
    for fn in sorted(os.listdir(INV_DIR)):
        if not fn.endswith(".json") or fn.startswith("_"):
            continue
        key = fn[:-5].replace("__", "|")
        if want and key.split("|")[0] not in want:
            continue
        try:
            with open(os.path.join(INV_DIR, fn)) as fh:
                inv = ClassInvariants.from_json(json.load(fh))
            out[inv.key] = inv
        except Exception as e:                                   # pragma: no cover
            log(f"   ! could not load {fn}: {e}")
    return out


def load_sample_sources(samples: Sequence[str] = tuple(SAMPLES)) -> List[SpecimenSource]:
    out = []
    for s in samples:
        t0 = time.time()
        out.append(SpecimenSource.load_sample(s))
        log(f"   corpus {s}: {len(out[-1].et_by_id):,} host elements ({time.time() - t0:.1f}s)")
    return out


def mine_all(classes: Sequence[str] = tuple(ALL_CLASSES), *,
             sources: Optional[List[SpecimenSource]] = None,
             save: bool = True, max_per_file: int = 0) -> Dict[str, ClassInvariants]:
    """Mine + persist the invariant corpus for ``classes``."""
    flat = Flattener()
    if sources is None:
        log("== loading the six sample sources")
        sources = load_sample_sources()
    all_invs: Dict[str, ClassInvariants] = {}
    t0 = time.time()
    for i, cn in enumerate(classes, 1):
        tc = time.time()
        got = mine_from_sources(cn, sources, flat, max_per_file=max_per_file)
        for k, inv in got.items():
            all_invs[inv.key] = inv
        base = got.get("")
        n = base.n_specimens if base else 0
        nr = len(base.rules) if base else 0
        log(f"   [{i:3d}/{len(classes)}] {cn:38s} specimens {n:6d} rules {nr:5d} "
            f"cohorts {[k for k in got if k]} ({time.time() - tc:.1f}s)")
    log(f"   mined {len(all_invs)} class/cohort corpora in {time.time() - t0:.1f}s")
    if save:
        save_invariants(all_invs.values())
        index = {k: {"class": v.class_name, "cohort": v.cohort,
                     "n_specimens": v.n_specimens, "rules": len(v.rules),
                     "per_file": v.per_file} for k, v in sorted(all_invs.items())}
        os.makedirs(INV_DIR, exist_ok=True)
        with open(os.path.join(INV_DIR, "_index.json"), "w") as fh:
            json.dump({"generated": time.strftime("%Y-%m-%d %H:%M:%S"),
                       "samples": SAMPLES, "classes": index}, fh, indent=1)
        log(f"   wrote {len(all_invs)} invariant files -> {os.path.relpath(INV_DIR, ROOT)}")
    return all_invs


# ===========================================================================
# 4. THE LINTER
# ===========================================================================

@dataclasses.dataclass
class Finding:
    class_name: str
    cohort: str
    field_path: str
    rule: str
    ours: Any
    specimens_say: Any
    support: int
    files: int
    total: int
    ftype: str = ""
    scope: str = "body"
    severity: str = "MEDIUM"
    score: float = 0.0
    present: int = 0
    #: filled by the calibration pass
    calibration: str = ""              # '' or 'violated-by-passing-control' etc.
    elem_id: Optional[int] = None
    source: str = ""

    def to_json(self) -> dict:
        d = dataclasses.asdict(self)
        d["ours"] = _json_safe(self.ours)
        d["specimens_say"] = _json_safe(self.specimens_say)
        return d


def _rule_score(rule: Rule) -> float:
    """Base severity score of a rule = weight x specimen COVERAGE (presence),
    boosted by the number of independent files and the absolute support."""
    w = RULE_WEIGHT.get(rule.rule, 0.3)
    frac = rule.presence                                   # <= 1.0 by construction
    files = min(rule.files, 6) / 6.0 if rule.files else 0.5
    depth = min(rule.support, 30) / 30.0
    return round(w * (0.55 * frac + 0.25 * files + 0.20 * depth), 4)


def _severity(score: float, rule: Rule) -> str:
    strong = rule.rule in ("NEVER_NULL", "PTR_PRESENT", "IDENTICAL", "CONST_LEN",
                           "SEQ103_CLASS", "OWNED_CHILD")
    if strong and score >= 0.80 and rule.files >= 3:
        return "CRITICAL"
    if score >= 0.60:
        return "HIGH"
    if score >= 0.35:
        return "MEDIUM"
    return "LOW"


def lint_object(class_name: str, obj: dict, header: Optional[dict] = None, *,
                invariants: Optional[Dict[str, ClassInvariants]] = None,
                cohort: Optional[str] = None,
                seq103_class: Optional[str] = None,
                elemrec_leaves: Optional[List[Leaf]] = None,
                resolve: Optional[Callable[[int], str]] = None,
                flat: Optional[Flattener] = None,
                elem_id: Optional[int] = None,
                source: str = "") -> List[Finding]:
    """Lint ONE constructed object of ``class_name`` against the mined
    invariants.  Returns findings, most severe first.

    ``obj`` / ``header`` are decoded value dicts (as ``rvt.objects`` /
    the genesis constructors produce).  ``resolve`` maps a positive ElementId
    to '@TargetClass' (falls back to '@?').  ``seq103_class`` is the class
    name of the element's seq-103 representation ('SerializedDummy' /
    'GElement'), ``elemrec_leaves`` its ElemTable-row features (see
    :meth:`SpecimenSource.elemrec_leaves`)."""
    invs = invariants if invariants is not None else load_invariants([class_name])
    if not invs:
        return []
    flat = flat or Flattener()
    resolve = resolve or (lambda i: "@?")
    header = header or {}
    ch = cohort if cohort is not None else cohort_of(class_name, obj, header)
    key = f"{class_name}|{ch}" if ch and f"{class_name}|{ch}" in invs else class_name
    inv = invs.get(key)
    if inv is None:
        return []
    # -- flatten ours ------------------------------------------------------------
    leaves = flat.flatten(class_name, obj, resolve=resolve)
    leaves += flat.flatten("ElementHeader", header, prefix="HDR", resolve=resolve) if header else []
    if elemrec_leaves:
        leaves += list(elemrec_leaves)
    if seq103_class:
        leaves.append(Leaf("REP.seq103_class", "classref", seq103_class))
    by_path: Dict[str, List[Leaf]] = collections.defaultdict(list)
    for lf in leaves:
        by_path[lf.path].append(lf)
    have_elemrec = elemrec_leaves is not None
    have_header = bool(header)
    have_rep = seq103_class is not None
    findings: List[Finding] = []
    for rule in inv.rules:
        # skip scopes ours cannot supply
        if rule.scope == "header" and not have_header:
            continue
        if rule.scope == "elemtable" and not have_elemrec:
            continue
        if rule.scope == "rep" and not have_rep:
            continue
        ours_leaves = by_path.get(rule.path)
        viol = _check_rule(rule, ours_leaves, by_path)
        if viol is None:
            continue
        ours_disp, spec_disp = viol
        sc = _rule_score(rule)
        findings.append(Finding(
            class_name=class_name, cohort=ch, field_path=rule.path, rule=rule.rule,
            ours=ours_disp, specimens_say=spec_disp, support=rule.support,
            files=rule.files, total=rule.total, ftype=rule.ftype, scope=rule.scope,
            severity=_severity(sc, rule), score=sc, present=(rule.present or rule.support),
            elem_id=elem_id, source=source))
    findings.sort(key=lambda f: (-f.score, SEVERITY_NAMES.index(f.severity), f.field_path))
    return findings


def _check_rule(rule: Rule, ours: Optional[List[Leaf]],
                by_path: Dict[str, List[Leaf]]) -> Optional[Tuple[Any, Any]]:
    """Return (ours_display, specimens_display) if OUR leaves violate the
    rule, else None.  ``ours`` = our leaves at the rule's path (None/[] when
    we do not have the path at all)."""
    kind = rule.rule
    n = rule.support
    tot = rule.total
    pres = rule.present or min(n, tot)
    if kind == "OWNED_CHILD":
        supp = f"{tot}/{tot} specimens"
    elif _is_element_path(rule.path) and n != pres:
        supp = f"{n} elements over {pres}/{tot} specimens"
    else:
        supp = f"{pres}/{tot} specimens"

    if kind == "OWNED_CHILD":
        kids = {lf.value for lf in by_path.get("ETR.owned[]", [])}
        if rule.expect not in kids:
            return (f"owns {sorted(map(str, kids)) or 'nothing'}",
                    f"every specimen owns a {rule.expect} row in the ElemTable ({supp})")
        return None

    if not ours:                                             # path absent in ours
        # A path is legitimately absent when it lives (a) under a container
        # (only present when the container is non-empty; the container's own
        # length rule covers that), (b) under an owned pointer / polymorphic
        # sub-object (present only when THAT concrete sub-object is held; the
        # pointer slot's own PTR_PRESENT / PTR_CLASS_SET rule covers that), or
        # (c) in only some specimens (conditional presence).  Flag absence
        # ONLY for universal, top-level fields.
        if "[]" in rule.path or "->" in rule.path or rule.path.endswith(".#ptr") \
                or rule.path.endswith("#len") or rule.presence < 0.999:
            return None
        if kind in ("NEVER_NULL", "PTR_PRESENT", "IDENTICAL", "CONST_LEN", "ENUM",
                    "PTR_CLASS_SET", "STR_VOCAB"):
            return ("<path absent in our object>",
                    f"{kind} {rule.expect!r} ({supp})")
        return None

    if kind == "NEVER_NULL":
        bad = [lf for lf in ours if is_null_leaf(lf)]
        if bad:
            return (_disp_values(ours), f"never null ({supp})")
        return None
    if kind == "PTR_PRESENT":
        bad = [lf for lf in ours if lf.value is None]
        if bad:
            return ("null (no owned sub-object)",
                    f"owned sub-object always present, class(es) seen: "
                    f"{_disp(rule.expect)} ({supp})" if rule.expect != 'non-null'
                    else f"owned sub-object ALWAYS present ({supp})")
        return None
    if kind == "ALWAYS_NULL":
        bad = [lf for lf in ours if not is_null_leaf(lf)]
        if bad:
            return (_disp_values(bad), f"always null / -1 ({supp})")
        return None
    if kind == "PTR_ABSENT":
        bad = [lf for lf in ours if lf.value is not None]
        if bad:
            return (_disp_values(bad), f"pointer ALWAYS null in specimens ({supp})")
        return None
    if kind == "IDENTICAL":
        # '@?' = a positive id we cannot resolve to a class (unknown target):
        # not a violation of a class-token constant, just unknowable
        bad = [lf for lf in ours if not _tok_equal(lf.value, rule.expect)
               and not is_null_leaf(lf) and _hashable(lf.value) != "@?"]
        nulls = [lf for lf in ours if is_null_leaf(lf)]
        if bad or nulls:
            return (_disp_values(ours), f"identical value {_disp(rule.expect)} in ALL {supp}")
        return None
    if kind == "CONST_LEN":
        bad = [lf for lf in ours if int(lf.value if lf.value is not None else 0) != int(rule.expect)]
        if bad:
            return (_disp_values(ours), f"length always {rule.expect} ({supp})")
        return None
    if kind == "LEN_SET":
        allowed = set(int(x) for x in _as_set(rule.expect))
        bad = [lf for lf in ours if int(lf.value if lf.value is not None else 0) not in allowed]
        if bad:
            return (_disp_values(ours), f"length always in {sorted(allowed)} ({supp})")
        return None
    if kind in ("ENUM", "PTR_CLASS_SET", "STR_VOCAB"):
        allowed = _as_set(rule.expect)
        bad = []
        for lf in ours:
            tok = None if is_null_leaf(lf) else _hashable(lf.value)
            if tok == "@?":                                   # unresolvable target: only
                if None not in allowed and not any(str(x).startswith("@") for x in allowed):
                    bad.append(lf)                            # flag when specimens NEVER reference
                continue
            if tok not in allowed:
                bad.append(lf)
        if bad:
            return (_disp_values(bad), f"value always in {_disp(allowed)} ({supp})")
        return None
    if kind == "RANGE":
        lo, hi = rule.expect
        bad = [lf for lf in ours if isinstance(lf.value, (int, float)) and not isinstance(lf.value, bool)
               and (lf.value < lo - _tol(lo) or lf.value > hi + _tol(hi))]
        if bad:
            return (_disp_values(bad), f"range [{_fmt_num(lo)} .. {_fmt_num(hi)}] over {supp}")
        return None
    return None


def _tol(x) -> float:
    return abs(x) * 1e-9 if isinstance(x, float) else 0


def _fmt_num(x) -> str:
    if isinstance(x, float):
        return f"{x:.6g}"
    return str(x)


def _tok_equal(a, b) -> bool:
    ta, tb = _hashable(a), _hashable(b)
    if isinstance(ta, float) or isinstance(tb, float):
        try:
            return abs(float(ta) - float(tb)) <= 1e-9 * max(1.0, abs(float(tb)))
        except (TypeError, ValueError):
            return False
    return ta == tb


def _as_set(e) -> set:
    if isinstance(e, set):
        return e
    if isinstance(e, (list, tuple)):
        return set(_hashable(x) for x in e)
    return {e}


def _disp(v, cap: int = 160) -> str:
    if isinstance(v, set):
        s = "{" + ", ".join(sorted((_disp_one(x) for x in v))) + "}"
    else:
        s = _disp_one(v)
    return s if len(s) <= cap else s[:cap - 3] + "..."


def _disp_one(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, float):
        return f"{v:.6g}"
    if isinstance(v, tuple):
        return "(" + ",".join(_disp_one(x) for x in v[:6]) + (",..." if len(v) > 6 else "") + ")"
    return str(v)


def _disp_values(leaves: List[Leaf], cap: int = 6) -> str:
    vals = [("null" if is_null_leaf(lf) else _disp_one(_hashable(lf.value))) for lf in leaves]
    uniq = list(dict.fromkeys(vals))
    s = ", ".join(uniq[:cap]) + (f" (+{len(uniq) - cap} more)" if len(uniq) > cap else "")
    if len(leaves) > 1:
        s += f"  [{len(leaves)} leaves]"
    return s


# ===========================================================================
# 5. OUR objects to lint: file sources (the ladder / candidates / controls)
# ===========================================================================
#: {source name: (path, id-selector, verdict, description)}
#:   verdict: 'FAIL' (viewer rejected -> the bug hunt), 'PASS' (viewer
#:   certified -> calibration control), 'UNTESTED'.
#:   id-selector: 'band>=N' (our ids at/above N), 'created' (ids above the
#:   pristine base's watermark), or an explicit id list.
def _pristine_watermark(project: str) -> int:
    from .elemtable import load_elemtable
    return int(load_elemtable(project).footer.last_id)


def our_sources() -> List[dict]:
    return [
        # ---- the ladder's rejected constructed objects (THE BUG HUNT) -----------
        {"name": "X5", "path": "experiments/genesis/subst/X5.rvt", "verdict": "FAIL",
         "select": ("band>=", OUR_ID_FLOOR),
         "what": "substitution ladder X1..X5 (pen table, browser orgs + navigator, "
                 "struct/wall-join/keynote/initial-view, MEP settings+sizes, 51 "
                 "singletons/trackers) on K1 -- viewer FAILED (Revit-DocumentCorruption)"},
        {"name": "X9", "path": "experiments/genesis/subst/X9.rvt", "verdict": "FAIL",
         "select": ("band>=", 2_000_000),
         "what": "substitution ladder rungs X6a..X9 (our 1,407-row GStyle catalog, "
                 "patterns/materials, units/sites/base points/project info, the view/"
                 "level/phase skeleton) -- viewer FAILED (parent X5 already failed)"},
        {"name": "S5", "path": "experiments/genesis/singletons/S5.rvt", "verdict": "FAIL",
         "select": ("band>=", OUR_ID_FLOOR),
         "what": "the census-complete candidate: G1_candidate base (skeleton + house "
                 "content, ids 1.5M) + every settings singleton + the complete catalog "
                 "(ids 1.6M) -- viewer FAILED"},
        # ---- the reader-ACCEPTED constructed / created objects (CALIBRATION) ----
        {"name": "T_conduit", "path": "experiments/genesis/types/T_conduit_types.rvt",
         "verdict": "PASS", "select": ("created", "rmebasicsampleproject"),
         "what": "OUR from-scratch RbsConduitType / ConduitStandardType / ConduitSizes / "
                 "CableTray / RbsWire* / CustomElement types injected into rme -- "
                 "viewer PASSED = the from-scratch constructor path is accepted for these"},
        {"name": "V21", "path": "experiments/acceptance/V21_batch_four_columns.rvt",
         "verdict": "PASS", "select": ("created", "rstbasicsampleproject"),
         "what": "four created FamilyInstance columns (clone-path) -- viewer PASSED"},
        {"name": "V23", "path": "experiments/acceptance/V23_electrical_room.rvt",
         "verdict": "PASS", "select": ("created", "rmebasicsampleproject"),
         "what": "created SWall x3 + FamilyInstance x9 (electrical room) -- viewer PASSED"},
        {"name": "V29", "path": "experiments/acceptance/V29_room_with_circuits.rvt",
         "verdict": "PASS", "select": ("created", "rmebasicsampleproject"),
         "what": "created SWall / FamilyInstance / RbsElectricalSystem circuits -- viewer PASSED"},
        # ---- our injected types with no viewer verdict yet ---------------------
        {"name": "T_settings", "path": "experiments/genesis/types/T_settings.rvt",
         "verdict": "UNTESTED", "select": ("created", "rmebasicsampleproject"),
         "what": "OUR GStyle/Category/Voltage/DistributionSys/LoadClass/Font/Text/"
                 "LinePattern types injected into rme -- no viewer verdict recorded"},
        {"name": "T_walltype", "path": "experiments/genesis/types/T_walltype.rvt",
         "verdict": "UNTESTED", "select": ("created", "rmebasicsampleproject"),
         "what": "OUR wall/floor/roof/ceiling types + materials + patterns injected into "
                 "rme -- no viewer verdict recorded"},
    ]


#: substitution-ladder id bands -> rung name (from experiments/genesis/subst/X*.json)
RUNG_BANDS = [
    (1_500_000, 1_599_999, "X1  pen table"),
    (1_600_000, 1_699_999, "X2  browser/navigator"),
    (1_700_000, 1_799_999, "X3  named singletons"),
    (1_800_000, 1_899_999, "X4  MEP settings/sizes"),
    (1_900_000, 1_999_999, "X5  remaining singletons"),
    (2_000_000, 2_099_999, "X6a GStyle catalog"),
    (2_100_000, 2_199_999, "X7  patterns/materials"),
    (2_200_000, 2_299_999, "X8  units/site/info"),
    (2_300_000, 2_399_999, "X9  view/level skeleton"),
]


def rung_of(eid: int, source_name: str) -> str:
    if source_name in ("X5", "X9"):
        for lo, hi, name in RUNG_BANDS:
            if lo <= eid <= hi:
                return name
    if source_name == "S5":
        return "S5 base (G1_candidate)" if eid < 1_600_000 else "S5 singletons+catalog"
    return source_name


def select_our_ids(src: SpecimenSource, select) -> List[int]:
    kind = select[0]
    if kind == "band>=":
        floor = int(select[1])
        return sorted(i for i in src.et_by_id if i >= floor and i in src.doc.idx[102])
    if kind == "created":
        wm = _pristine_watermark(str(select[1]))
        return sorted(i for i in src.et_by_id if i > wm and i in src.doc.idx[102])
    if kind == "ids":
        return sorted(int(i) for i in select[1] if int(i) in src.doc.idx[102])
    raise ValueError(f"unknown selector {kind!r}")


def lint_source(spec: dict, invariants: Dict[str, ClassInvariants],
                flat: Flattener) -> dict:
    """Lint every OUR element of one file source.  Returns
    {'source': spec, 'elements': [...], 'findings': [Finding...], 'by_class': Counter}."""
    path = os.path.join(ROOT, spec["path"]) if not os.path.isabs(spec["path"]) else spec["path"]
    if not os.path.exists(path):
        return {"source": spec, "error": f"missing file {path}", "findings": [], "elements": []}
    src = SpecimenSource.load_file(path)
    ids = select_our_ids(src, spec["select"])
    findings: List[Finding] = []
    elements = []
    skipped = collections.Counter()
    for eid in ids:
        cn = src.class_of(eid)
        if cn not in invariants and not any(k.startswith(cn + "|") for k in invariants):
            skipped[cn] += 1
            continue
        body, clean = src.object(eid, 102)
        if body is None or not clean:
            skipped[f"{cn} (undecodable)"] += 1
            continue
        hdr, _hc = src.object(eid, 101)
        fs = lint_object(cn, body, hdr or {}, invariants=invariants,
                         seq103_class=src.rep_class(eid),
                         elemrec_leaves=src.elemrec_leaves(eid),
                         resolve=src.resolve, flat=flat, elem_id=int(eid),
                         source=spec["name"])
        for f in fs:
            f.source = spec["name"]
        findings.extend(fs)
        elements.append({"elem_id": int(eid), "class": cn,
                         "cohort": cohort_of(cn, body, hdr or {}),
                         "rung": rung_of(int(eid), spec["name"]),
                         "n_findings": len(fs)})
    return {"source": spec, "elements": elements, "findings": findings,
            "skipped": dict(skipped),
            "by_class": collections.Counter(e["class"] for e in elements)}


# ===========================================================================
# 6. aggregation, calibration, ranking, report
# ===========================================================================

def aggregate(results: List[dict]) -> dict:
    """Group findings by (class, cohort, path, rule) across all elements /
    sources, split by verdict, and apply the CALIBRATION: any rule violated
    by a PASS control of the same class is NOT load-bearing."""
    agg: Dict[tuple, dict] = {}
    for res in results:
        spec = res["source"]
        verdict = spec.get("verdict", "?")
        for f in res.get("findings", []):
            key = (f.class_name, f.cohort, f.field_path, f.rule)
            g = agg.get(key)
            if g is None:
                g = agg[key] = {
                    "class": f.class_name, "cohort": f.cohort, "path": f.field_path,
                    "rule": f.rule, "specimens_say": f.specimens_say,
                    "support": f.support, "files": f.files, "total": f.total,
                    "present": f.present or f.support,
                    "severity": f.severity, "score": f.score, "scope": f.scope,
                    "ftype": f.ftype,
                    "violations": collections.Counter(),      # verdict -> count
                    "sources": collections.Counter(),         # source name -> count
                    "rungs": collections.Counter(),           # rung -> count
                    "ours_samples": [],                        # a few distinct ours displays
                    "elem_ids": [],
                    "calibration": "",
                }
            g["violations"][verdict] += 1
            g["sources"][spec["name"]] += 1
            g["rungs"][rung_of(f.elem_id or 0, spec["name"])] += 1
            if str(f.ours) not in g["ours_samples"] and len(g["ours_samples"]) < 3:
                g["ours_samples"].append(str(f.ours))
            if len(g["elem_ids"]) < 4 and f.elem_id is not None:
                g["elem_ids"].append(f.elem_id)
    # calibration --------------------------------------------------------------
    for g in agg.values():
        v = g["violations"]
        if v.get("PASS", 0) > 0 and v.get("FAIL", 0) > 0:
            g["calibration"] = "ALSO violated by a PASSING control -> NOT load-bearing"
        elif v.get("PASS", 0) > 0:
            g["calibration"] = "violated only by PASSING controls -> NOT load-bearing"
    return {"groups": list(agg.values())}


def rule_type_fp_rates(results: List[dict], invariants: Dict[str, ClassInvariants]) -> dict:
    """Per RULE-TYPE: how many rules of that type were CHECKED against
    PASS-control elements vs how many were VIOLATED -> the false-positive
    rate of the rule type (a rule type the accepted controls routinely violate
    is not a reliable audit signal)."""
    checked: Dict[str, int] = collections.Counter()
    violated: Dict[str, int] = collections.Counter()
    for res in results:
        if res["source"].get("verdict") != "PASS":
            continue
        n_elems_by_class = collections.Counter(e["class"] for e in res.get("elements", []))
        for cn, n_el in n_elems_by_class.items():
            for k, inv in invariants.items():
                if k.split("|")[0] != cn:
                    continue
                for r in inv.rules:
                    checked[r.rule] += n_el
        for f in res.get("findings", []):
            violated[f.rule] += 1
    rates = {}
    for rt in sorted(set(checked) | set(violated)):
        c, v = checked.get(rt, 0), violated.get(rt, 0)
        rates[rt] = {"checked": c, "violated": v,
                     "fp_rate": round(v / c, 4) if c else None}
    return rates


def rank_bug_list(agg: dict, fp_rates: dict) -> List[dict]:
    """The ranked BUG LIST: FAIL-source violations, ranked by
    (a) rule support (N/N over many files = hard constraint) and
    (b) how often our objects violate it, demoted by the rule type's
    control false-positive rate and by same-class control calibration."""
    rows = []
    for g in agg["groups"]:
        nfail = g["violations"].get("FAIL", 0)
        if nfail == 0:
            continue
        fp = (fp_rates.get(g["rule"]) or {}).get("fp_rate") or 0.0
        demote = 1.0 - min(0.85, fp)                            # noisy rule types sink
        calib = 0.15 if g["calibration"] else 1.0             # same-class control passes with it
        support_frac = min(1.0, g.get("present", g["support"]) / max(g["total"], 1))
        base = float(g["score"])
        # how much of our failing population violates it (log-scaled)
        pop = 0.55 + 0.45 * min(1.0, math.log1p(nfail) / math.log1p(60))
        rank_score = round(base * demote * calib * pop * (0.6 + 0.4 * support_frac), 4)
        rows.append({**g, "n_fail_violations": nfail, "rank_score": rank_score,
                     "rule_fp_rate": fp})
    rows.sort(key=lambda r: (-r["rank_score"], -r["n_fail_violations"], r["class"], r["path"]))
    return rows


#: thematic family of a finding (for the executive summary)
FAMILIES = [
    ("elemtable-ownership", "ElemTable OWNERSHIP web (owner / owned children)"),
    ("elemtable-vintage", "ElemTable VINTAGE (id band / creation episode)"),
    ("nulled-reference", "NULLED reference specimens ALWAYS populate"),
    ("missing-subobject", "MISSING owned sub-object (pointer we leave null)"),
    ("header-shape", "ElementHeader shape (parents lists / flags)"),
    ("container-shape", "container length / cardinality"),
    ("seq103-rep", "seq-103 representation class"),
    ("product-default-value", "our VALUE differs from a universal specimen constant"),
    ("value-range", "our value outside the observed range"),
    ("string-vocab", "string / name vocabulary"),
    ("other", "other"),
]


def family_of(g: dict) -> str:
    p, r, ft = g["path"], g["rule"], g.get("ftype", "")
    if p.startswith("ETR.owner") or p.startswith("ETR.has_owner") or p.startswith("ETR.owned"):
        return "elemtable-ownership"
    if p.startswith("ETR."):
        return "elemtable-vintage"
    if p.startswith("REP."):
        return "seq103-rep"
    if r == "PTR_PRESENT" or (r == "PTR_ABSENT"):
        return "missing-subobject"
    if p.startswith("HDR."):
        return "header-shape"
    if r in ("NEVER_NULL", "ALWAYS_NULL") or (r == "IDENTICAL" and ft in ("eid", "weak", "guid", "ptr")
                                             and str(g.get("specimens_say", "")).find("@") >= 0):
        return "nulled-reference"
    if r in ("CONST_LEN", "LEN_SET", "OWNED_CHILD") or p.endswith("#len"):
        return "container-shape"
    if r == "RANGE":
        return "value-range"
    if r == "STR_VOCAB":
        return "string-vocab"
    if r in ("IDENTICAL", "ENUM", "PTR_CLASS_SET"):
        return "nulled-reference" if ft == "eid" else "product-default-value"
    return "other"


# ---------------------------------------------------------------------------
# markdown report
# ---------------------------------------------------------------------------

def _md_escape(s: str) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def write_report(bug_list: List[dict], agg: dict, fp_rates: dict,
                 results: List[dict], invariants: Dict[str, ClassInvariants],
                 path: str = REPORT_MD) -> str:
    L: List[str] = []
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    L.append("# THE CONSTRUCTED-OBJECT LINT REPORT (`rvt.objlint`)")
    L.append("")
    L.append(f"Generated {now} by `src/rvt/objlint.py`.  Every finding is a "
             f"violation, by one of OUR from-scratch CONSTRUCTED objects, of a "
             f"per-field invariant MINED from the real specimens of that class "
             f"across the six 2026 sample projects (`experiments/genesis/lint/"
             f"invariants/<class>.json`).  **The top of this report is the BUG "
             f"LIST for the fix stream** — ranked by (a) how many specimens "
             f"support the rule (N/N over several files = a HARD constraint) and "
             f"(b) how often our objects violate it, and CALIBRATED against the "
             f"constructed / created objects the Autodesk viewer already ACCEPTED "
             f"(T_conduit_types = our from-scratch conduit / wire types PASS; the "
             f"V-file created FamilyInstance / SWall / circuits PASS): a rule those "
             f"controls also violate is provably NOT load-bearing and is marked so "
             f"and demoted.  The validator (`tools/rvt_validate.py`) reports every "
             f"file here VALID with 0 errors — none of these findings is a "
             f"validator rule; they are the reader's implicit shape contract, mined.")
    L.append("")
    # ---- sources -----------------------------------------------------------
    L.append("## 1. What was linted")
    L.append("")
    L.append("| source | file | our elements | classes | verdict | role |")
    L.append("|---|---|--:|--:|---|---|")
    for res in results:
        spec = res["source"]
        n = len(res.get("elements", []))
        ncls = len(res.get("by_class", {}))
        role = "BUG HUNT" if spec["verdict"] == "FAIL" else (
            "calibration control" if spec["verdict"] == "PASS" else "informational")
        err = res.get("error")
        L.append(f"| **{spec['name']}** | `{spec['path']}` | {n} | {ncls} | "
                 f"{spec['verdict']} | {role}{' — ' + err if err else ''} |")
    L.append("")
    for res in results:
        spec = res["source"]
        L.append(f"* **{spec['name']}** ({spec['verdict']}): {_md_escape(spec['what'])}"
                 + (f" — classes: {', '.join(f'{c}×{n}' for c, n in sorted(res.get('by_class', {}).items(), key=lambda kv: -kv[1])[:14])}"
                    if res.get("by_class") else ""))
    L.append("")
    inv_n = len({k.split('|')[0] for k in invariants})
    nspec = sum(v.n_specimens for k, v in invariants.items() if "|" not in k)
    L.append(f"Invariant corpus: **{inv_n} classes**, {nspec:,} host specimens mined "
             f"from the six samples (seq-102 object + seq-101 header + ElemTable row + "
             f"seq-103 rep class per specimen), {sum(len(v.rules) for v in invariants.values()):,} "
             f"rules over {len(invariants)} class/cohort corpora.  Reproduce: "
             f"`.venv/bin/python -m rvt.objlint`.")
    L.append("")

    # ---- executive summary: finding families -----------------------------
    load_bearing_all = [r for r in bug_list if not r["calibration"]]
    L.append("## 2. Executive summary — the finding FAMILIES")
    L.append("")
    L.append("Every load-bearing finding (violated by our REJECTED objects, not by any "
             "PASSING control of the same class) falls into a family.  The families are the "
             "constructor work items; the flat ranked list in §4 is the evidence per field.  "
             "`rules` = distinct (class, path, rule) rules violated; `elements` = how many of our "
             "objects break at least one rule of the family; `top exemplar` = the highest-ranked "
             "instance.  **X5-scoped** = present among X1..X5's classes (X5 = the FIRST rung the "
             "viewer rejected, so those are the prime suspects for that verdict).")
    L.append("")
    L.append("| family | rules | violating elements | X5-scoped | top exemplar (class · path · ours → specimens) |")
    L.append("|---|--:|--:|:--:|---|")
    fam_rows: Dict[str, List[dict]] = collections.defaultdict(list)
    for r in load_bearing_all:
        fam_rows[family_of(r)].append(r)
    for fam, label in FAMILIES:
        rows = fam_rows.get(fam) or []
        if not rows:
            continue
        elems: Set[int] = set()
        x5 = False
        for r in rows:
            elems.update(r.get("elem_ids") or [])
            if r["sources"].get("X5", 0):
                x5 = True
        top = max(rows, key=lambda x: x["rank_score"])
        ex = (f"{top['class']} · `{_md_escape(top['path'])}` · "
              f"{_md_escape(_disp(top['ours_samples'][0] if top['ours_samples'] else '', 40))} → "
              f"{_md_escape(_disp(top['specimens_say'], 80))}")
        L.append(f"| **{label}** | {len(rows)} | ≥{len(elems)} | {'yes' if x5 else ''} | {ex} |")
    L.append("")
    # ---- ladder-rung attribution ---------------------------------------------
    rung_rules: Dict[str, List[dict]] = collections.defaultdict(list)
    for r in load_bearing_all:
        for rung, n in r["rungs"].items():
            rung_rules[rung].append(r)
    if rung_rules:
        L.append("**Ladder-rung attribution** (which substitution rung / candidate layer each violation "
                 "belongs to; the K1-derived ladder failed FIRST at X5, so X1..X5 rows are the ones a "
                 "single verdict can convict; X6a..X9 were only ever tested on the failing parent):")
        L.append("")
        L.append("| rung / layer | classes touched | distinct rules violated | strongest finding |")
        L.append("|---|---|--:|---|")
        for rung in sorted(rung_rules):
            rows = rung_rules[rung]
            classes = collections.Counter(r["class"] for r in rows)
            top = max(rows, key=lambda x: x["rank_score"])
            L.append(f"| {rung} | {', '.join(f'{c}' for c, _ in classes.most_common(6))}"
                     f"{' …' if len(classes) > 6 else ''} | {len(rows)} | "
                     f"{top['class']} · `{_md_escape(top['path'])}` · {top['rule']} |")
        L.append("")

    # ---- calibration ------------------------------------------------------
    L.append("## 3. Calibration — rule types the ACCEPTED controls violate")
    L.append("")
    L.append("Our from-scratch conduit / wire / cable-tray types (T_conduit_types.rvt) and the "
             "created FamilyInstance / SWall / circuit elements (V21/V23/V29) all LOADED in the "
             "Autodesk viewer.  Every rule of a class those controls violate is by definition "
             "not required by the reader.  Per RULE TYPE, the fraction of rules the controls "
             "violate is the type's false-positive rate; noisy types are demoted in the ranking "
             "and their findings should be read as texture, not defects.")
    L.append("")
    L.append("| rule type | rules checked on PASS controls | violated | false-positive rate | reading |")
    L.append("|---|--:|--:|--:|---|")
    for rt, st in sorted(fp_rates.items(), key=lambda kv: -(kv[1]["fp_rate"] or 0)):
        fp = st["fp_rate"]
        reading = ("trustworthy" if fp is not None and fp < 0.02 else
                   "mostly reliable" if fp is not None and fp < 0.08 else
                   "NOISY — demoted" if fp is not None else "no control coverage")
        L.append(f"| {rt} | {st['checked']} | {st['violated']} | "
                 f"{'-' if fp is None else f'{100*fp:.1f}%'} | {reading} |")
    L.append("")
    ctrl = [g for g in agg["groups"] if g["calibration"]]
    if ctrl:
        L.append("Rules a PASSING control of the SAME class also violates are provably not "
                 "load-bearing (marked and demoted).  Per control class, how many rules the "
                 "accepted objects violate, by rule type:")
        L.append("")
        L.append("| control class | rules violated by the PASSING control(s) | by rule type | control sources |")
        L.append("|---|--:|---|---|")
        cby: Dict[str, list] = collections.defaultdict(list)
        for g in ctrl:
            cby[g["class"]].append(g)
        for cn in sorted(cby, key=lambda c: -len(cby[c])):
            rows = cby[cn]
            bt = collections.Counter(x["rule"] for x in rows)
            srcs = sorted({s for x in rows for s in x["sources"] if s in _pass_names(results)})
            L.append(f"| {cn} | {len(rows)} | "
                     f"{', '.join(f'{k}×{v}' for k, v in bt.most_common())} | {', '.join(srcs)} |")
        L.append("")
        # the calibrated rules that ALSO hit our FAILING objects: the interesting ones
        both = [g for g in ctrl if g["violations"].get("FAIL", 0)]
        if both:
            L.append("Calibrated rules that OUR FAILING objects violate too (same shape in an "
                     "accepted file — these are texture, not the defect):")
            L.append("")
            L.append("| class | path | rule | fail violations | control sources |")
            L.append("|---|---|---|--:|---|")
            for g in sorted(both, key=lambda x: (x["class"], x["path"]))[:40]:
                psrc = ", ".join(s for s in g["sources"] if s in _pass_names(results))
                L.append(f"| {g['class']} | `{_md_escape(g['path'])}` | {g['rule']} | "
                         f"{g['violations'].get('FAIL', 0)} | {psrc} |")
            if len(both) > 40:
                L.append(f"| … | ({len(both) - 40} more) |  |  |  |")
            L.append("")

    # ---- THE BUG LIST ------------------------------------------------------
    load_bearing = [r for r in bug_list if not r["calibration"]]
    L.append("## 4. THE BUG LIST — ranked violations by our REJECTED constructed objects")
    L.append("")
    L.append("Read `support` as: this many of the class's real specimens satisfy the rule "
             "(N/N = every specimen we have, across `files` sample projects).  Read `violations` "
             "as: this many of OUR objects (in the FAILING files X5 / X9 / S5) break it, and which "
             "ladder rung they belong to (X5 = the FIRST failing rung, so its rows and X1..X4's are "
             "the prime suspects; S5 = the failing census-complete candidate).  `ours` is what our "
             "constructor emitted; `specimens say` is the mined invariant.  Header (`HDR.`), "
             "ElemTable (`ETR.`) and seq-103 (`REP.`) paths are the record-envelope shape; the "
             "rest are seq-102 object fields (`->Class` = through an owned pointer, `[]` = a "
             "container's elements, `#len` = its length, `#ptr` = which class an owned pointer "
             "slot holds, `@Class` = the class an ElementId points at).")
    L.append("")
    L.append("| # | sev | class (cohort) | field path | rule | ours | specimens say | support | violations (rung: n) | score |")
    L.append("|--:|---|---|---|---|---|---|---|---|--:|")
    for i, r in enumerate(load_bearing[:60], 1):
        rungs = "; ".join(f"{k}: {v}" for k, v in r["rungs"].most_common(4))
        cls = r["class"] + (f" ({r['cohort']})" if r["cohort"] else "")
        L.append(f"| {i} | {r['severity']} | {cls} | `{_md_escape(r['path'])}` | {r['rule']} | "
                 f"{_md_escape(_disp(r['ours_samples'][0] if r['ours_samples'] else '', 90))} | "
                 f"{_md_escape(r['specimens_say'])} | {_support_str(r)} · {r['files']}f | "
                 f"{r['n_fail_violations']} ({_md_escape(rungs)}) | {r['rank_score']:.3f} |")
    if len(load_bearing) > 60:
        L.append(f"| … | | ({len(load_bearing) - 60} more findings in the JSON) | | | | | | | |")
    L.append("")

    # ---- per-class detail ---------------------------------------------------
    L.append("## 5. Per-class findings (all rejected-object violations, by class)")
    L.append("")
    by_cls: Dict[str, List[dict]] = collections.defaultdict(list)
    for r in bug_list:
        by_cls[r["class"]].append(r)
    for cn in sorted(by_cls, key=lambda c: -max(x["rank_score"] for x in by_cls[c])):
        rows = by_cls[cn]
        inv = invariants.get(cn) or next((v for k, v in invariants.items() if k.startswith(cn + "|")), None)
        nspec_c = inv.n_specimens if inv else 0
        L.append(f"### {cn}  — {len(rows)} finding(s); {nspec_c} specimens mined")
        L.append("")
        L.append("| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |")
        L.append("|---|---|---|---|---|---|---|---|")
        for r in rows[:25]:
            rungs = "; ".join(f"{k}: {v}" for k, v in r["rungs"].most_common(3))
            eids = ", ".join(str(e) for e in (r.get("elem_ids") or [])[:4])
            L.append(f"| {r['severity']} | `{_md_escape(r['path'])}` | {r['rule']} | "
                     f"{_md_escape(_disp(r['ours_samples'][0] if r['ours_samples'] else '', 80))} | "
                     f"{_md_escape(_disp(r['specimens_say'], 120))} | {_support_str(r)} | "
                     f"{r['n_fail_violations']} ({_md_escape(rungs)}) | {eids} |")
        if len(rows) > 25:
            L.append(f"| … | ({len(rows) - 25} more) | | | | | | |")
        L.append("")

    # ---- untested / informational ------------------------------------------
    unt = [g for g in agg["groups"] if g["violations"].get("UNTESTED", 0) and not
           g["violations"].get("FAIL", 0)]
    L.append("## 6. Untested sources (no viewer verdict) — violations unique to them")
    L.append("")
    if unt:
        L.append("| class | path | rule | ours | specimens say | support |")
        L.append("|---|---|---|---|---|---|")
        for g in sorted(unt, key=lambda x: -x["score"])[:40]:
            L.append(f"| {g['class']} | `{_md_escape(g['path'])}` | {g['rule']} | "
                     f"{_md_escape(_disp(g['ours_samples'][0] if g['ours_samples'] else '', 80))} | "
                     f"{_md_escape(_disp(g['specimens_say'], 120))} | {_support_str(g)} |")
        if len(unt) > 40:
            L.append(f"| … | ({len(unt) - 40} more) |  |  |  |  |")
    else:
        L.append("None — every rule the untested T_settings / T_walltype objects violate is ALSO "
                 "violated by the rejected X/S set (their findings are counted in §4 / §5), i.e. "
                 "the untested files add no new suspects; their verdicts would only confirm.")
    L.append("")

    # ---- method ------------------------------------------------------------------
    L.append("## 7. Method + how to read a finding")
    L.append("")
    L.append("* **Mining.** For each class our constructors emit, EVERY host-document specimen "
             "(id in `Global/ElemTable`) of the six samples is decoded (seq-102 body, seq-101 "
             "`ElementHeader`, ElemTable row, seq-103 rep class) and flattened schema-parallel into "
             "typed leaves.  Growable containers collapse to `path[]` + `path.#len`; owned pointers add "
             "`path.#ptr` (the concrete class) and are walked into; ElementId leaves are TOKENIZED — "
             "-1 = null, other negatives = the literal built-in id constant, positive = `@Class` of the "
             "target in ITS OWN file — so `always references a UnitsElem` and `never dangling` are "
             "minable, and cross-file id values are comparable.  Cohorts split populations that differ by "
             "rule (project vs family-scoped pen tables / view types; built-in vs sub-category style rows).")
    L.append("* **Rules.** NEVER_NULL / PTR_PRESENT (a field or owned sub-object present-and-non-null in "
             "N/N), IDENTICAL (one value in all N — a format constant), CONST_LEN / LEN_SET (container "
             "length), ENUM / PTR_CLASS_SET / STR_VOCAB (a small saturated value set), RANGE, ALWAYS_NULL / "
             "PTR_ABSENT, OWNED_CHILD (an ElemTable-owned child class every specimen owns), on the body, the "
             "header (`HDR.`), the ElemTable row (`ETR.`) and the seq-103 rep (`REP.`).")
    L.append("* **Calibration.** The same lint runs over the constructed / created objects the viewer "
             "ACCEPTED.  A (class, path, rule) they violate is not required by the reader (marked, "
             "demoted); a rule TYPE they violate often is a noisy signal (the false-positive table).  Our "
             "conduit / wire types passing tells us the from-scratch construction PATH itself is fine — the "
             "reader's objection is class-specific SHAPE / VALUE, which is what this list localises.")
    L.append("* **Reading the list.** A CRITICAL / HIGH row on a class we ship in the failing files, "
             "supported by N/N specimens across ≥3 sample projects, not calibrated away, is a concrete "
             "shape difference between our object and every accepted one — the fix is to make the "
             "constructor emit what the specimens carry (or, where the value is Autodesk expression, to "
             "record it for counsel).  Element ids and names in `ours` locate the exact record.")
    L.append("")
    L.append("## 8. Reproduction")
    L.append("")
    L.append("```")
    L.append(".venv/bin/python -m rvt.objlint                    # mine (six samples) + lint + this report")
    L.append(".venv/bin/python -m rvt.objlint --no-mine          # reuse experiments/genesis/lint/invariants/")
    L.append(".venv/bin/python -m rvt.objlint --classes GStyleElem,PenWidthTableElem")
    L.append(".venv/bin/python -m pytest tests/test_objlint.py -q")
    L.append("```")
    L.append("")
    text = "\n".join(L) + "\n"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)
    return text


def _pass_names(results: List[dict]) -> Set[str]:
    return {r["source"]["name"] for r in results if r["source"].get("verdict") == "PASS"}


def _support_str(g: dict) -> str:
    """'present/total' (with observation count when they differ)."""
    pres = g.get("present", g["support"])
    if _is_element_path(g["path"]) and g["support"] != pres:
        return f"{min(pres, g['total'])}/{g['total']} sp ({g['support']} obs)"
    return f"{min(pres, g['total'])}/{g['total']}"


# ===========================================================================
# 6b. FRESH-constructor lint (the fix stream's iteration loop)
# ===========================================================================

def fresh_constructor_records() -> Tuple[List[Any], Dict[int, str]]:
    """Build our constructor constellations FRESH (no file) and return
    ([records...], id -> class map).  Records are TypeRecord / SkelElement
    (both expose class_name, elem_id, obj, header, rep_class_name)."""
    from rvt.genesis.types import IdSource
    recs: List[Any] = []
    idmap: Dict[int, str] = {}
    # the house standard's whole catalog (walls, materials, patterns, views,
    # levels, sites, electrical types...) -- the G-line's content
    try:
        from rvt.genesis import house_standard as HS
        hc = HS.build_catalog(4_000_000)
        recs += list(hc.records)
    except Exception as e:                                       # pragma: no cover
        log(f"   ! house_standard.build_catalog: {e!r}")
    # named ids the settings constellation wants to be wired to
    doc_ids = {}
    for r in recs:
        cn = getattr(r, "class_name", "")
        if cn == "UnitsElem":
            doc_ids["units"] = r.elem_id
        elif cn == "SunAndShadowSettings" and "document_sun" not in doc_ids:
            doc_ids["document_sun"] = r.elem_id
        elif cn == "ProjectPhase" and "phase_new" not in doc_ids:
            doc_ids["phase_new"] = r.elem_id
        elif cn == "PhaseFilterElem" and "phase_filter" not in doc_ids:
            doc_ids["phase_filter"] = r.elem_id
        elif cn == "GeoLocation" and "geo_location" not in doc_ids:
            doc_ids["geo_location"] = r.elem_id
        elif cn == "Level" and "level1" not in doc_ids:
            doc_ids["level1"] = r.elem_id
        elif cn == "AllProjectPhases":
            doc_ids["phase_set"] = r.elem_id
    try:
        from rvt.genesis import settings as ST
        cat = ST.standard_settings(IdSource(4_500_000), tier="all", doc_ids=doc_ids)
        recs += list(cat.records)
    except Exception as e:                                       # pragma: no cover
        log(f"   ! settings.standard_settings: {e!r}")
    try:
        from rvt.genesis import catalog as CAT
        recs += list(CAT.builtin_style_catalog(IdSource(4_800_000)))
    except Exception as e:                                       # pragma: no cover
        log(f"   ! catalog.builtin_style_catalog: {e!r}")
    for r in recs:
        try:
            idmap[int(r.elem_id)] = str(r.class_name)
        except Exception:                                        # pragma: no cover
            pass
    return recs, idmap


def calibrated_keys(run_json: str = os.path.join(LINT_DIR, "objlint_run.json")) -> Set[tuple]:
    """The (class, cohort, path, rule) keys the last file run proved NOT
    load-bearing (violated by a PASSING control) -- reused by the fresh
    loop so the fix stream is not sent after tolerated differences."""
    out: Set[tuple] = set()
    if not os.path.exists(run_json):
        return out
    try:
        with open(run_json) as fh:
            d = json.load(fh)
        for r in d.get("bug_list") or []:
            if r.get("calibration"):
                out.add((r["class"], r.get("cohort", ""), r["path"], r["rule"]))
    except Exception:                                                # pragma: no cover
        pass
    return out


def lint_fresh(invariants: Optional[Dict[str, ClassInvariants]] = None,
               classes: Optional[Sequence[str]] = None,
               show: int = 60) -> List[Finding]:
    """Lint the CURRENT constructors' output STANDALONE (no file build):
    the fix stream's fast loop -- change a constructor, re-run, watch the
    finding disappear.  ElemTable-scope rules (ownership / vintage) are
    skipped (no ElemTable exists); body / header / seq-103 rules apply.
    Rules the last file run proved NOT load-bearing are tagged and sunk."""
    invs = invariants if invariants is not None else load_invariants(classes)
    if not invs:
        log("== no invariant corpus cached -- run `python -m rvt.objlint --mine-only` first")
        return []
    calib = calibrated_keys()
    log(f"== building fresh constructor constellations "
        f"({len(calib)} rules known-tolerated from the last file run)")
    recs, idmap = fresh_constructor_records()
    resolve = lambda i: "@" + idmap.get(int(i), "?")                # noqa: E731
    flat = Flattener()
    log(f"   {len(recs):,} records, {len(set(idmap.values()))} classes")
    findings: List[Finding] = []
    want = set(classes) if classes else None
    for r in recs:
        cn = str(getattr(r, "class_name", ""))
        if want and cn not in want:
            continue
        if cn not in invs and not any(k.startswith(cn + "|") for k in invs):
            continue
        obj = getattr(r, "obj", None) or {}
        hdr = getattr(r, "header", None) or {}
        rep_cls = getattr(r, "rep_class_name", None)
        fs = lint_object(cn, obj, hdr, invariants=invs, resolve=resolve, flat=flat,
                         seq103_class=rep_cls, elem_id=int(getattr(r, "elem_id", 0) or 0),
                         source="fresh")
        for f in fs:
            if (f.class_name, f.cohort, f.field_path, f.rule) in calib:
                f.calibration = "known-tolerated (a PASSING control also does this)"
        findings.extend(fs)
    # aggregate by (class, path, rule) for a readable table
    agg: Dict[tuple, dict] = {}
    for f in findings:
        k = (f.class_name, f.cohort, f.field_path, f.rule)
        g = agg.setdefault(k, {"f": f, "n": 0})
        g["n"] += 1
    rows = sorted(agg.values(),
                  key=lambda g: (bool(g["f"].calibration), -g["f"].score, g["f"].class_name))
    log(f"== fresh constructor lint: {len(findings)} findings, "
        f"{len(rows)} distinct (class, path, rule)")
    log(f"   {'sev':8s} {'class':30s} {'rule':13s} {'n':>4s}  path -> ours vs specimens")
    for g in rows[:show]:
        f = g["f"]
        tag = "  [known-tolerated]" if f.calibration else ""
        log(f"   {f.severity:8s} {f.class_name[:29]:30s} {f.rule:13s} {g['n']:4d}  "
            f"{f.field_path[:58]} | ours={_disp(f.ours, 30)} | "
            f"{_disp(f.specimens_say, 60)}{tag}")
    if len(rows) > show:
        log(f"   ... {len(rows) - show} more")
    return findings


# ===========================================================================
# 7. driver
# ===========================================================================

def run(*, mine: bool = True, classes: Optional[Sequence[str]] = None,
        sources: Optional[List[dict]] = None, report_path: str = REPORT_MD,
        json_path: Optional[str] = None) -> dict:
    t_all = time.time()
    classes = list(classes) if classes else list(ALL_CLASSES)
    flat = Flattener()
    if mine:
        log(f"== mining specimen invariants for {len(classes)} classes")
        invariants = mine_all(classes)
    else:
        invariants = load_invariants(classes)
        log(f"== loaded {len(invariants)} cached invariant corpora")
        if not invariants:
            log("   (nothing cached -- mining)")
            invariants = mine_all(classes)
    srcs = sources or our_sources()
    log(f"== linting {len(srcs)} sources")
    results = []
    for spec in srcs:
        t0 = time.time()
        res = lint_source(spec, invariants, flat)
        nf = len(res.get("findings", []))
        ne = len(res.get("elements", []))
        log(f"   {spec['name']:12s} [{spec['verdict']:8s}] {ne:5d} our elements -> {nf:6d} findings "
            f"({time.time() - t0:.1f}s){'  ERROR ' + res['error'] if res.get('error') else ''}")
        results.append(res)
    agg = aggregate(results)
    fp = rule_type_fp_rates(results, invariants)
    bug_list = rank_bug_list(agg, fp)
    write_report(bug_list, agg, fp, results, invariants, report_path)
    log(f"== wrote {os.path.relpath(report_path, ROOT)} "
        f"({len(bug_list)} ranked findings; {len(agg['groups'])} distinct rules violated)")
    out = {
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "classes": len(invariants),
        "sources": [{"name": r["source"]["name"], "verdict": r["source"]["verdict"],
                     "path": r["source"]["path"], "elements": len(r.get("elements", [])),
                     "findings": len(r.get("findings", [])),
                     "by_class": dict(r.get("by_class", {})),
                     "skipped": r.get("skipped", {}), "error": r.get("error")}
                    for r in results],
        "rule_type_fp_rates": fp,
        "bug_list": [{k: (_json_safe(v) if not isinstance(v, collections.Counter) else dict(v))
                      for k, v in r.items()} for r in bug_list],
        "seconds": round(time.time() - t_all, 1),
    }
    jp = json_path or os.path.join(LINT_DIR, "objlint_run.json")
    os.makedirs(os.path.dirname(jp), exist_ok=True)
    with open(jp, "w") as fh:
        json.dump(out, fh, indent=1, default=str)
    log(f"== wrote {os.path.relpath(jp, ROOT)} ({out['seconds']}s total)")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Constructed-object linter (specimen invariants).")
    ap.add_argument("--mine-only", action="store_true", help="mine + save invariants, no lint")
    ap.add_argument("--no-mine", action="store_true", help="lint from the cached invariant corpus")
    ap.add_argument("--classes", default="", help="comma-separated class subset")
    ap.add_argument("--enumerate", action="store_true",
                    help="run the constructors and print the classes they emit")
    ap.add_argument("--fresh", action="store_true",
                    help="lint the CURRENT constructors' output standalone "
                         "(no file build; the fix stream's fast loop)")
    args = ap.parse_args(argv)
    if args.fresh:
        classes = [c for c in args.classes.split(",") if c] or None
        lint_fresh(classes=classes)
        return 0
    if args.enumerate:
        got = enumerate_constructor_classes()
        allc = sorted(set().union(*[set(v) for v in got.values()]))
        for mod, cls in got.items():
            log(f"== {mod}: {len(cls)} classes\n   " + ", ".join(cls))
        log(f"== union: {len(allc)} classes; missing from CONSTRUCTOR_CLASSES: "
            f"{sorted(set(allc) - set(CONSTRUCTOR_CLASSES))}")
        return 0
    classes = [c for c in args.classes.split(",") if c] or None
    if args.mine_only:
        mine_all(classes or ALL_CLASSES)
        return 0
    run(mine=not args.no_mine, classes=classes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
