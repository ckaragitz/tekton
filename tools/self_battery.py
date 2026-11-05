#!/usr/bin/env python
"""self_battery.py -- the exhaustive self-battery (#796, steer #765): build
every product the engine DECLARES, at every release it can author, and put
every in-session instrument on each result.

Owner: "you should be able to test every possible item possible and debug and
make it right."  This is that, minus the one thing no sandbox contains (Revit
itself, hard rule 4): a PASS here is necessary, never sufficient, and "0
errors" is a fact about our bytes -- never evidence that Revit opens them.

THE MATRIX IS ENUMERATED, NEVER HAND-WRITTEN (DONE 1).  Every case comes from
what the engine declares, and each source is reported with its counts in
``report["declarations"]``:

  make_family  every GENERATOR subcommand of tools/make_family.py (a
               subcommand with an optional ``--output`` plus ``--no-validate``
               and ``--json``), read from its own argparse tree; the axes are
               every option with ``choices`` and every ``store_true`` flag
               (output-only flags excepted), plus the free-text options
               :data:`AXIS_SOURCES` binds to the engine function declaring
               their values.  The full product, or one factor at a time past
               :data:`MAX_PRODUCT`.  A non-generator subcommand that still
               takes ``--output`` is a FAIL row unless
               :data:`NON_FAMILY_SUBCOMMANDS` names why it writes no family.
  famspec      every ``rvt.frontdoor.famspec.KINDS`` kind valid with no other
               field and not already a make_family subcommand (built and
               written through the famspec lane's own build/write); a kind
               that needs fields must be covered by another source, or it is
               a FAIL row.
  archetype    every key of the #591 registry: its nominal, each standard
               size of its primary parameter, each boolean keyword of
               ``make_archetype`` flipped once, and the NEC working space where
               the archetype declares one.
  part_shape   ``GENERIC_PART_SHAPES + COMPOSITE_SHAPES`` (checked against the
               famspec schema's shape enum -- a drift is a FAIL row), each as
               one universal part carrying every field the schema declares
               for a part, x the work planes in :data:`LITERALS`.
  prism        the single-prism lane: the schema's two footprints (rectangle,
               ring) x its ``prism_drive`` enum, plus each boolean keyword of
               ``make_generic_model`` flipped once.
  ifc_route    every tracked ``inputs/ifc/*.ifc`` through
               ``router.route(..., "rfa", target_version=y)``; every ``.rfa``
               it writes is its own case.
  evidence     every family of every ``family_set`` recipe in
               ``rvt.frontdoor.matrix.EVIDENCE_FORMS`` (the families of a
               certified room, #984): its declared constructor and kwargs.
  taxonomy     a COVERAGE CHECK, not a builder: every build mechanism the MEP
               taxonomy declares (``famspec:`` / ``archetype:`` / ``house:``)
               must be driven by one of the sources above, or it is a FAIL row
               naming the uncovered builder.

x every release in ``KNOWN_RELEASES`` that is creation-certified; its pinned
base must resolve (``resolve_base(target_release=y)``) -- a creation-certified
release whose tracked base does NOT resolve is a FAIL row, never a silent
skip.  Adding a constructor, an archetype, a shape, a choice or a release adds
its cases with no edit here (#685: breadth is data, not code).

ALIASES.  Byte-identical outputs of one release (e.g. ``troffer`` /
``recessed-troffer``) are built once more, reported with ``alias_of`` and
instrumented once -- but a variant that silently stops having an effect would
look exactly like that, so every alias must be a pair the ALIAS PIN
(:data:`ALIAS_PIN`, release-free groups of case keys, regenerated with
``--pin-aliases`` from a full run) lists; an unpinned alias is a FAIL on
``build`` ("the variant had no effect").  A pinned group whose members are no
longer byte-identical is listed as drift (a note, not a failure).

INSTRUMENTS (DONE 2), each recorded per case as pass / fail / skip / refused:

  build, write  the case's own constructor and writer (inside the release's
                build context); an exception is a FAIL -- or REFUSED only when
                it is a NAMED port-layer refusal: the ``PortabilityError``
                family (``Missing2025`` / ``Missing2024`` / ``Missing2023``,
                DONE 4).  A ``ReleaseContextError`` (nested contexts, a schema
                pin mismatch, an undetectable base), ``BaseNotCertified`` or
                ``UnsupportedTarget`` is a defect or a mis-enumerated release,
                so it FAILS.
  release       ``versions.detect_release`` of the written file == the target
  verify        ``skeleton.verify_family_rfa`` read back in the file's own release
  validate      ``rvt.validate.validate_file(family=True)``: 0 errors
  provenance    ``famdoc_adoc.provenance_scan_v2`` (donor = that release's
                base) + ``factory.provenance_scan`` (the make_family ledger):
                every check true, ``identity_is_ours`` included
  law           ``constraint_law.check_file`` on the family and on every
                nested family document it carries: 0 errors
  conformance   ``conformance.check_file`` against invariants mined from the
                born corpus (each file read in its own release; cached by the
                sha256 of the corpus bytes AND of every module of the ``rvt``
                package, so a decoder fix never reads a stale cache): 0
                ``question`` findings, 0 records only partly decoded, and more
                than 0 rules evaluated (an inert check is a FAIL, not a pass);
                SKIP only when no corpus is present by default -- an explicit
                ``--corpus`` that yields nothing FAILS the run
  determinism   the same case built and written again into another directory
                (same basename, #168) by the DETERMINISM TWIN: a second Python
                process with a different ``PYTHONHASHSEED`` whose clock
                (``time`` and ``datetime.now``) runs :data:`TIME_SHIFT_S` ahead
                -- past a year, hour, minute and second boundary -- so neither
                hash-seed ordering nor the wall clock can hide; sha256 equal.
                A case the twin cannot re-enumerate (a test's closure) is
                rebuilt in-process under the same clock shift, and the detail
                says which.

An instrument that crashes is a FAIL, never a skip.

PINNED PROBES (``_catalog`` / ``_run_one``) are the few regression pins of
lanes no declaration enumerates (the desktop-verified one-box drive pair of
#907/#910, a multi-type family, the #714 pset-drive plan): listed separately,
never counted in the matrix.

RULE 3 / RULE 6.  The born corpus (quarantined, git-ignored) is read as
STATISTICS only: the report carries counts and our own files' divergent field
names, never a corpus file name or value.

USAGE::

    .venv/bin/python tools/self_battery.py                    # full: every source x release
    .venv/bin/python tools/self_battery.py --quick            # CI: native release, archetype nominals
    .venv/bin/python tools/self_battery.py --release 2024 --only 'archetype:conduit'
    .venv/bin/python tools/self_battery.py --list             # the enumerated matrix, nothing built
    .venv/bin/python tools/self_battery.py --pin-aliases      # full run; accept + re-pin its aliases

Exit 0 = no case FAILED (refusals and pinned aliases are not failures).
Exit 1 = a case failed, a pinned probe failed, the corpus given failed to
mine, or NOTHING RAN (0 cases: an ``--only`` typo, a broken release) --
an empty run is never a pass.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib
import inspect
import itertools
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (os.path.join(ROOT, "src"), HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

INSTRUMENTS = ("build", "write", "release", "verify", "validate", "provenance",
               "law", "conformance", "determinism")
STATES = ("pass", "fail", "refused", "skip", "not_run")

#: make_family generator options that only shape the OUTPUT, never the family
OUTPUT_ONLY = frozenset({"help", "json", "no_validate", "type_catalog"})
#: past this many combinations a subcommand is swept one factor at a time
MAX_PRODUCT = 64
#: the ONE place a free-text make_family option is bound to the engine function
#: DECLARING its values (the values themselves come from the engine)
AXIS_SOURCES: Dict[Tuple[str, str], Tuple[str, str]] = {
    ("luminaire", "size"): ("rvt.famgen.factory", "held_troffer_sizes"),
}
#: values the engine accepts but does not export; each is a follow-up to export
LITERALS: Dict[str, Any] = {
    # factory.add_generic_part accepts work_plane in (None, "level", "vertical")
    # and exports no constant for it; "level" == None
    "work_plane": (None, "vertical"),
}
#: universal-part values for the schema's part fields, by field (anything the
#: schema adds later and this does not name gets UNIVERSAL_DEFAULT)
UNIVERSAL_VALUES: Dict[str, Any] = {
    "width_ft": 1.0, "depth_ft": 0.8, "height_ft": 1.2, "radius_ft": 0.4,
    "diameter_ft": 0.8, "length_ft": 2.0, "top_radius_ft": 0.2, "base_z_ft": 0.0,
    "center": [0.0, 0.0],
    # a CONCAVE ring (a notch in the top edge), feet
    "vertices": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.5, 0.4], [0.0, 1.0]],
}
UNIVERSAL_DEFAULT = 0.5
#: every family case is written under ONE basename (its folder carries the
#: case's slug): the basename is part of the bytes (#168), so byte-identical
#: content -- an alias -- is only visible when the name cannot differ
FAMILY_BASENAME = "battery.rfa"
#: make_family subcommands that WRITE (they take ``--output`` or
#: ``--no-validate``) but are not enumerated as generators, and why; any other
#: such non-generator is a FAIL row (a family writer the battery would otherwise
#: never see)
NON_FAMILY_SUBCOMMANDS: Dict[str, str] = {
    "load": "loads the generated panelboard into a project: an .rvt lane, not a family",
    "load-device": "loads a generated device family into a project: an .rvt lane",
    "loader": "the loader readiness report (JSON); writes no family",
    "proofs": ("writes the three proof families, through make_panelboard / "
               "make_transformer / make_troffer -- the constructors the panelboard, "
               "transformer and luminaire generator cases already run"),
}
#: the determinism twin's clock runs this far ahead: past a year, a day, an
#: hour, a minute and a second boundary (400 d + 1 h + 1 min + 1.5 s)
TIME_SHIFT_S = 400 * 86400 + 3661.5
#: how long ``Twin.collect`` waits for one case's answer before it kills the twin
#: and FAILS that case's determinism (the slowest case builds in seconds)
TWIN_TIMEOUT_S = 600.0
#: the alias pin: release-free groups of case keys whose bytes are identical
#: BY DESIGN (regenerate from a full run with --pin-aliases)
ALIAS_PIN = os.path.join(HERE, "self_battery_aliases.json")


# ---------------------------------------------------------------------------
# cases
# ---------------------------------------------------------------------------

@dataclass
class Case:
    """One tuple of the matrix: ``source`` x ``product`` x ``variant`` x
    ``release``.  A family case has ``build`` (-> product) and ``write``
    ((product, path) -> report); a route case has ``route`` ((out_dir, year)
    -> report dict) and one row per ``.rfa`` it writes."""
    source: str
    product: str
    variant: Dict[str, Any]
    release: int = 0
    build: Optional[Callable[[], Any]] = None
    write: Optional[Callable[[Any, str], Dict[str, Any]]] = None
    route: Optional[Callable[[str, int], Dict[str, Any]]] = None
    repro: Any = None
    error: Optional[str] = None          # a declaration problem: the case FAILS as is
    rebuildable: bool = False            # the determinism twin can re-enumerate it by cid

    @property
    def key(self) -> str:
        v = " ".join(f"{k}={_fmt(val)}" for k, val in self.variant.items())
        return f"{self.source}:{self.product}" + (f" {v}" if v else "")

    @property
    def cid(self) -> str:
        return f"{self.key}@{self.release}"

    def tuple(self) -> Dict[str, Any]:
        return {"source": self.source, "product": self.product,
                "variant": {k: _jsonable(v) for k, v in self.variant.items()},
                "release": self.release}


def _fmt(v: Any) -> str:
    if isinstance(v, bool):
        return "yes" if v else "no"
    if v is None:
        return "none"
    if isinstance(v, float) and v == int(v):
        return f"{int(v)}"
    return str(v)


def _jsonable(v: Any) -> Any:
    try:
        json.dumps(v)
        return v
    except TypeError:
        return repr(v)


def _default_write(prod: Any, path: str) -> Dict[str, Any]:
    """The product's own writer, read-back instruments left to the battery
    (it runs them itself, outside the build context, in the file's release)."""
    return prod.write(path, validate=False, provenance=False)


# -- S1: make_family generator subcommands -----------------------------------

class _ParserStash(Exception):
    pass


def make_family_module():
    # a caller (a test importing this module) may have taken tools/ back off
    # sys.path after the import; the generator CLI lives beside this file
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    return importlib.import_module("make_family")


def make_family_parser(MF=None) -> argparse.ArgumentParser:
    """tools/make_family.py's own root parser, captured without editing it:
    ``main`` builds the tree and calls ``parse_args`` -- intercepted once.
    Never cached: choices such as ``sorted(F.DEVICE_KINDS)`` are evaluated
    when the tree is built, so a fresh tree sees the engine as it is now."""
    MF = MF or make_family_module()
    grabbed: Dict[str, Any] = {}
    orig = argparse.ArgumentParser.parse_args

    def grab(self, *a, **k):
        grabbed["parser"] = self
        raise _ParserStash()

    argparse.ArgumentParser.parse_args = grab
    try:
        MF.main([])
    except _ParserStash:
        pass
    finally:
        argparse.ArgumentParser.parse_args = orig
    if "parser" not in grabbed:
        raise RuntimeError("make_family.main() built no parser")
    return grabbed["parser"]


def _subparsers(root: argparse.ArgumentParser) -> Dict[str, argparse.ArgumentParser]:
    sp = next(a for a in root._actions if isinstance(a, argparse._SubParsersAction))
    return dict(sp.choices)


def _is_generator(p: argparse.ArgumentParser) -> bool:
    dests = {a.dest: a for a in p._actions}
    out = dests.get("output")
    return (out is not None and bool(out.option_strings) and not out.required
            and "no_validate" in dests and "json" in dests)


def _axes(sub: str, p: argparse.ArgumentParser) -> List[Tuple[str, str, List[Any], Any]]:
    """``[(option, dest, values, default)]`` of one generator subcommand."""
    axes = []
    for a in p._actions:
        if not a.option_strings or a.dest in OUTPUT_ONLY:
            continue
        opt = max(a.option_strings, key=len)
        if a.choices:
            vals = list(a.choices)
            if a.default in vals:
                vals.remove(a.default)
            axes.append((opt, a.dest, [a.default] + vals, a.default))
        elif isinstance(a, argparse._StoreTrueAction):
            axes.append((opt, a.dest, [False, True], False))
        elif (sub, a.dest) in AXIS_SOURCES:
            mod, fn = AXIS_SOURCES[(sub, a.dest)]
            vals = sorted(getattr(importlib.import_module(mod), fn)())
            if a.default in vals:
                vals.remove(a.default)
            axes.append((opt, a.dest, [a.default] + vals, a.default))
    return axes


def _combinations(axes) -> Tuple[List[Dict[str, Any]], str]:
    """Every combination of ``axes`` (as {dest: value} of NON-default values),
    or one factor at a time past :data:`MAX_PRODUCT`."""
    n = 1
    for ax in axes:
        n *= len(ax[2])
    if n <= MAX_PRODUCT:
        combos = []
        for vals in itertools.product(*(ax[2] for ax in axes)):
            combos.append({ax[1]: v for ax, v in zip(axes, vals) if v != ax[3]})
        return combos, f"full product ({n})"
    combos = [{}]
    for ax in axes:
        for v in ax[2][1:]:
            combos.append({ax[1]: v})
    return combos, f"one factor at a time ({len(combos)} of {n})"


def _argv(sub: str, axes, combo: Dict[str, Any]) -> List[str]:
    argv = [sub]
    for opt, dest, _vals, _default in axes:
        if dest not in combo:
            continue
        v = combo[dest]
        if v is True:
            argv.append(opt)
        elif v is not False:
            argv += [opt, str(v)]
    return argv


def _mf_build(argv: List[str]) -> Callable[[], Any]:
    def build():
        MF = make_family_module()
        ns = make_family_parser(MF).parse_args(argv)
        got: Dict[str, Any] = {}
        orig = MF._emit

        def capture(prod, _ns):
            got["prod"] = prod
            return {"ok": True}

        MF._emit = capture
        try:
            ns.func(ns)
        finally:
            MF._emit = orig
        if "prod" not in got:
            raise RuntimeError(f"make_family {' '.join(argv)} built no product")
        return got["prod"]
    return build


def enum_make_family(decl: Dict[str, Any]) -> List[Case]:
    MF = make_family_module()
    subs = _subparsers(make_family_parser(MF))
    cases: List[Case] = []
    info: Dict[str, Any] = {"generators": {}, "excluded": sorted(
        n for n, p in subs.items() if not _is_generator(p))}
    for sub in info["excluded"]:
        dests = {a.dest for a in subs[sub]._actions}
        if not dests & {"output", "no_validate"}:
            continue                          # an info / report command: writes nothing
        if sub in NON_FAMILY_SUBCOMMANDS:
            continue
        cases.append(Case("make_family", sub, {}, repro={"argv": [sub]},
                          error=(f"declaration gap: make_family {sub!r} writes (--output or "
                                 f"--no-validate) but is not a generator (no optional --output "
                                 f"+ --no-validate + --json) and NON_FAMILY_SUBCOMMANDS does "
                                 f"not say why the battery need not build it")))
    info["non_family_with_output"] = {k: v for k, v in NON_FAMILY_SUBCOMMANDS.items()
                                      if k in subs}
    for sub in sorted(n for n, p in subs.items() if _is_generator(p)):
        axes = _axes(sub, subs[sub])
        combos, how = _combinations(axes)
        info["generators"][sub] = {"axes": {d: [_jsonable(v) for v in vals]
                                            for _o, d, vals, _df in axes},
                                   "cases": len(combos), "sweep": how}
        for combo in combos:
            argv = _argv(sub, axes, combo)
            cases.append(Case("make_family", sub, dict(combo), build=_mf_build(argv),
                              write=_default_write, repro={"argv": argv}))
    info["cases"] = len(cases)
    decl["make_family"] = info
    return cases


# -- S2: famspec kinds -------------------------------------------------------

#: which battery source drives a famspec kind's constructor, by constructor
_DRIVES = {"rvt.famgen.factory:make_archetype": "archetype",
           "rvt.famgen.factory:make_generic_model": "part_shape+prism"}


def enum_famspec(decl: Dict[str, Any], mf_subs: Sequence[str]) -> List[Case]:
    from rvt.frontdoor import famspec as FS
    cases: List[Case] = []
    info: Dict[str, Any] = {"kinds": list(FS.KINDS), "covered_by": {}}
    for kind in FS.KINDS:
        if kind in mf_subs:
            info["covered_by"][kind] = "make_family"
            continue
        cover = _DRIVES.get(FS.constructor_name(kind))
        if cover:                         # its geometry / product is another source's axis
            info["covered_by"][kind] = cover
            continue
        try:
            k, kw, _r = FS.normalise({"kind": kind})
        except FS.FamspecError:
            info["covered_by"][kind] = None
            cases.append(Case("famspec", kind, {}, repro={"famspec": {"kind": kind}},
                              error=(f"declaration gap: famspec kind {kind!r} needs fields "
                                     f"and no battery source drives "
                                     f"{FS.constructor_name(kind)}")))
            continue
        info["covered_by"][kind] = "famspec"

        def build(k=k, kw=kw):
            return FS.build(k, dict(kw))

        def write(prod, path):
            return FS.write(prod, path)
        cases.append(Case("famspec", kind, {}, build=build, write=write,
                          repro={"famspec": {"kind": kind}}))
    info["cases"] = len(cases)
    decl["famspec"] = info
    return cases


# -- S3: the archetype registry ----------------------------------------------

def enum_archetypes(decl: Dict[str, Any], *, nominal_only: bool = False) -> List[Case]:
    from rvt.famgen import archetypes as AR
    from rvt.famgen import factory as F
    flags = [(n, p.default) for n, p in inspect.signature(F.make_archetype).parameters.items()
             if isinstance(p.default, bool)]
    cases: List[Case] = []
    info: Dict[str, Any] = {"archetypes": {}, "boolean_keywords": [n for n, _ in flags],
                            "nominal_only": nominal_only}

    def mk(product, variant, **kw):
        def build():
            return F.make_archetype(product=product, **kw)
        return Case("archetype", product, variant, build=build, write=_default_write,
                    repro={"make_archetype": {"product": product, **kw}})

    for key in AR.keys():
        a = AR.archetype(key)
        n0 = len(cases)
        cases.append(mk(key, {}))
        if not nominal_only:
            prim = next((p for p in a.params if p.primary), None)
            if prim is not None:
                for v in sorted(set(prim.choices) - {prim.default}):
                    cases.append(mk(key, {prim.key: v}, dimensions={prim.key: v}))
            for name, default in flags:
                cases.append(mk(key, {name: not default}, **{name: not default}))
            if a.working_space:
                if AR.wants_clearance("clearance"):
                    cases.append(mk(key, {"prompt": "clearance"}, prompt="clearance"))
                else:
                    cases.append(Case("archetype", key, {"prompt": "clearance"},
                                      error="declaration drift: wants_clearance('clearance') "
                                            "is False for a working-space archetype"))
        info["archetypes"][key] = len(cases) - n0
    info["cases"] = len(cases)
    decl["archetype"] = info
    return cases


# -- S4: part shapes ----------------------------------------------------------

def _schema_part_fields() -> Dict[str, Dict[str, Any]]:
    from rvt.frontdoor import famspec as FS
    sch = FS.schema() or {}
    return (((sch.get("definitions") or {}).get("generic_model") or {}).get("properties") or {}
            ).get("parts", {}).get("items", {}).get("properties", {})


def universal_part(shape: str) -> Dict[str, Any]:
    """One part carrying every field the famspec schema declares for a part."""
    part: Dict[str, Any] = {"name": f"battery {shape}", "shape": shape}
    for fld, node in _schema_part_fields().items():
        if fld in ("name", "shape"):
            continue
        t = node.get("type")
        if fld in UNIVERSAL_VALUES:
            part[fld] = UNIVERSAL_VALUES[fld]
        elif t == "integer":
            part[fld] = int(node.get("minimum", 1))
        elif t == "number":
            part[fld] = UNIVERSAL_DEFAULT
    return part


def enum_part_shapes(decl: Dict[str, Any]) -> List[Case]:
    from rvt.famgen import factory as F
    from rvt.famgen import revolve as RV
    shapes = tuple(F.GENERIC_PART_SHAPES) + tuple(RV.COMPOSITE_SHAPES)
    schema_enum = (_schema_part_fields().get("shape") or {}).get("enum")
    cases: List[Case] = []
    info: Dict[str, Any] = {"shapes": list(shapes), "schema_enum": schema_enum,
                            "work_plane": [_jsonable(w) for w in LITERALS["work_plane"]]}
    if schema_enum is not None and set(schema_enum) != set(shapes):
        cases.append(Case("part_shape", "declaration", {},
                          error=(f"declaration drift: engine shapes {sorted(shapes)} != famspec "
                                 f"schema enum {sorted(schema_enum)}")))
    for shape in shapes:
        for wp in LITERALS["work_plane"]:
            part = universal_part(shape)
            if wp is not None:
                part["work_plane"] = wp

            def build(part=part, shape=shape):
                return F.make_generic_model(parts=[dict(part)], name=f"Battery {shape}",
                                            source="self battery")
            cases.append(Case("part_shape", shape, ({"work_plane": wp} if wp else {}),
                              build=build, write=_default_write,
                              repro={"make_generic_model": {"parts": [part]}}))
    info["cases"] = len(cases)
    decl["part_shape"] = info
    return cases


# -- S5: the single prism -----------------------------------------------------

def enum_prism(decl: Dict[str, Any]) -> List[Case]:
    from rvt.famgen import factory as F
    from rvt.frontdoor import famspec as FS
    gm = (((FS.schema() or {}).get("definitions") or {}).get("generic_model") or {}
          ).get("properties") or {}
    sig = inspect.signature(F.make_generic_model).parameters
    default_drive = sig["prism_drive"].default
    drives = (gm.get("prism_drive") or {}).get("enum") or [default_drive]
    feet = {k: UNIVERSAL_VALUES[k] for k in ("width_ft", "depth_ft", "height_ft")}
    footprints: Dict[str, Dict[str, Any]] = {}
    if "width_ft" in gm and "depth_ft" in gm:
        footprints["rect"] = feet
    if "vertices" in gm:
        footprints["ring"] = {"vertices": UNIVERSAL_VALUES["vertices"],
                              "height_ft": feet["height_ft"]}
    flags = [(n, p.default) for n, p in sig.items() if isinstance(p.default, bool)]
    cases: List[Case] = []

    def mk(fp, variant, **kw):
        args = {**footprints[fp], **kw}

        def build():
            return F.make_generic_model(name=f"Battery prism {fp}", source="self battery",
                                        **args)
        return Case("prism", fp, variant, build=build, write=_default_write,
                    repro={"make_generic_model": args})

    for fp in footprints:
        for d in drives:
            cases.append(mk(fp, ({"prism_drive": d} if d != default_drive else {}),
                            prism_drive=d))
    if "rect" in footprints:
        for name, default in flags:
            cases.append(mk("rect", {name: not default}, **{name: not default}))
    decl["prism"] = {"footprints": list(footprints), "prism_drive": drives,
                     "boolean_keywords": [n for n, _ in flags], "cases": len(cases)}
    return cases


# -- S6: the IFC -> rfa route -------------------------------------------------

def enum_ifc(decl: Dict[str, Any]) -> List[Case]:
    import glob
    paths = sorted(glob.glob(os.path.join(ROOT, "inputs", "ifc", "*.ifc")))
    cases: List[Case] = []
    for p in paths:
        def route(out_dir, year, p=p):
            from rvt.frontdoor import router as R
            res = R.route({"ifc": p}, "rfa", out=out_dir, target_version=year, quiet=True)
            return {"ok": bool(res.ok), "line": res.line or res.status,
                    "errors": list(res.errors or [])[:5]}
        stem = os.path.splitext(os.path.basename(p))[0]
        cases.append(Case("ifc_route", stem, {}, route=route,
                          repro={"route": {"ifc": os.path.relpath(p, ROOT), "output": "rfa"}}))
    decl["ifc_route"] = {"inputs": [os.path.relpath(p, ROOT) for p in paths],
                         "cases": len(cases)}
    return cases


# -- S7: the certified family sets of the evidence table ----------------------

def enum_evidence(decl: Dict[str, Any]) -> List[Case]:
    """Every family of every ``family_set`` recipe in ``matrix.EVIDENCE_FORMS``
    (#984): the constructor and kwargs the matrix declares for a certified
    room's families.  This is where a ``house:`` builder (the switchboard)
    is declared with buildable arguments."""
    from rvt.frontdoor import matrix as M
    cases: List[Case] = []
    info: Dict[str, Any] = {"entries": {}, "constructors": []}
    for ev_path, ent in sorted(M.EVIDENCE_FORMS.items()):
        if ent.get("recipe") != "family_set":
            continue
        stem = os.path.splitext(os.path.basename(ev_path))[0]
        info["entries"][ev_path] = [tag for tag, _c, _k in ent["families"]]
        for tag, ctor, kwargs in ent["families"]:
            if ctor not in info["constructors"]:
                info["constructors"].append(ctor)

            def build(ctor=ctor, kwargs=kwargs):
                return M._resolve(ctor)(**dict(kwargs))
            cases.append(Case("evidence", f"{stem}/{tag}", {}, build=build,
                              write=_default_write,
                              repro={"constructor": ctor, "kwargs": _jsonable(dict(kwargs))}))
    info["cases"] = len(cases)
    decl["evidence"] = info
    return cases


# -- S8: the taxonomy's builders must all be driven ----------------------------

def check_taxonomy(decl: Dict[str, Any]) -> List[Case]:
    """A COVERAGE CHECK over ``rvt.famgen.taxonomy``: every build mechanism a
    kind declares must be driven by a source above -- ``famspec:<kind>`` by
    whichever source covers that famspec kind, ``archetype:<key>`` by the
    archetype source, ``house:<module>:<fn>`` by a declared constructor of the
    evidence source.  An uncovered builder is a FAIL row (#796 review: the
    switchboard was reached only because one tracked IFC happens to hold one)."""
    from rvt.famgen import archetypes as AR
    from rvt.famgen import taxonomy as TX
    fam_cover = (decl.get("famspec") or {}).get("covered_by") or {}
    arche = set(AR.keys())
    house = set((decl.get("evidence") or {}).get("constructors") or [])
    mechs: Dict[str, List[str]] = {}
    for row in TX.kinds():
        for m in row.via:
            mechs.setdefault(m, []).append(row.key)
    cover: Dict[str, Optional[str]] = {}
    cases: List[Case] = []
    for m in sorted(mechs):
        kind, _, arg = m.partition(":")
        if kind == "famspec":
            c = fam_cover.get(arg.partition("/")[0])
        elif kind == "archetype":
            c = "archetype" if arg in arche else None
        elif kind == "house":
            c = "evidence" if arg in house else None
        else:
            c = None
        cover[m] = c
        if c is None:
            cases.append(Case("taxonomy", m, {}, repro={"taxonomy_kinds": mechs[m]},
                              error=(f"declaration gap: the taxonomy builder {m!r} (kinds "
                                     f"{', '.join(mechs[m])}) is driven by no battery source")))
    decl["taxonomy"] = {"mechanisms": cover, "uncovered": sorted(k for k, v in cover.items()
                                                                  if v is None)}
    return cases


SOURCES = ("make_family", "famspec", "archetype", "part_shape", "prism", "ifc_route",
           "evidence", "taxonomy")


def enumerate_matrix(*, quick: bool = False, sources: Optional[Sequence[str]] = None
                     ) -> Tuple[List[Case], Dict[str, Any]]:
    """The release-free case list + ``declarations`` (what each came from).
    ``quick`` = the archetype nominals only (the CI shard)."""
    decl: Dict[str, Any] = {"literals": {k: [_jsonable(x) for x in v]
                                         for k, v in LITERALS.items()},
                            "axis_sources": {f"{s} --{d}": f"{m}.{fn}"
                                             for (s, d), (m, fn) in AXIS_SOURCES.items()}}
    if quick:
        cases = enum_archetypes(decl, nominal_only=True)
    else:
        want = set(sources or SOURCES)
        unknown = want - set(SOURCES)
        if unknown:
            raise SystemExit(f"unknown --source {sorted(unknown)} (sources: {', '.join(SOURCES)})")
        cases = []
        mf = enum_make_family(decl)
        if "make_family" in want:
            cases += mf
        mf_subs = sorted(decl["make_family"]["generators"])
        for name, fn in (("famspec", lambda: enum_famspec(decl, mf_subs)),
                         ("archetype", lambda: enum_archetypes(decl)),
                         ("part_shape", lambda: enum_part_shapes(decl)),
                         ("prism", lambda: enum_prism(decl)),
                         ("ifc_route", lambda: enum_ifc(decl)),
                         ("evidence", lambda: enum_evidence(decl)),
                         ("taxonomy", lambda: check_taxonomy(decl))):   # last: reads the rest
            got = fn()
            if name in want:
                cases += got
    for c in cases:                       # the twin re-enumerates exactly these by cid
        c.rebuildable = c.error is None
    return cases, decl


# ---------------------------------------------------------------------------
# releases
# ---------------------------------------------------------------------------

def releases(only: Optional[Sequence[int]] = None, *, quick: bool = False
             ) -> Tuple[List[int], Dict[int, str], Dict[str, str], Dict[int, str]]:
    """``(run, {year: base path}, {year: why skipped}, {year: why BROKEN})``:
    every ``KNOWN_RELEASES`` entry that is creation-certified runs on its
    pinned, certified base -- the same rule the release context uses.  A
    creation-certified release whose tracked base does not resolve (or is not
    pinned + certified) is BROKEN, which the run reports as a FAIL row: the
    release is declared authorable, so its base failing is a defect, never a
    skip.  ``quick`` = the native release only.  Newest first."""
    from rvt import versions as V
    from rvt.frontdoor.base import resolve_base
    from rvt.frontdoor import release_ctx as RC
    run: List[int] = []
    bases: Dict[int, str] = {}
    skipped: Dict[str, str] = {}
    broken: Dict[int, str] = {}
    native = RC.native_release()
    for y in sorted(V.KNOWN_RELEASES, reverse=True):
        if quick and y != native:
            skipped[str(y)] = "--quick runs the native release only"
            continue
        if only and y not in only:
            skipped[str(y)] = "not selected (--release)"
            continue
        if not V.KNOWN_RELEASES[y].creation_certified:
            skipped[str(y)] = "not creation-certified (KNOWN_RELEASES)"
            continue
        try:
            rb = resolve_base(target_release=y)
        except Exception as e:                                    # noqa: BLE001
            broken[y] = (f"creation-certified, but its pinned base does not resolve: "
                         f"{type(e).__name__}: {str(e)[:200]}")
            continue
        if not (rb.pinned and rb.certified):
            broken[y] = (f"creation-certified, but its base is not pinned + certified "
                         f"(pinned={rb.pinned}, certified={rb.certified})")
            continue
        run.append(y)
        bases[y] = rb.path
    return run, bases, skipped, broken


# ---------------------------------------------------------------------------
# the corpus oracle (conformance), cached by the corpus's sha256
# ---------------------------------------------------------------------------

def default_corpus() -> Optional[str]:
    from rvt.famgen import conformance as CO
    for rel in (os.path.join("samples", "reference-families"), os.path.join("samples", "rft")):
        d = os.path.join(ROOT, rel)
        if os.path.isdir(d) and CO.corpus_paths(d):
            return d
    return None


def instrument_sha() -> str:
    """sha256 over every ``.py`` of the ``rvt`` package (relative path +
    bytes): the miner is ``conformance.py`` but what it observes is decided
    by the decoders under it (``objects``, ``families``, ``global_framing``,
    the schema / framing layers), so a fix anywhere in the package re-mines."""
    import rvt
    pkg = os.path.dirname(os.path.abspath(rvt.__file__))
    h = hashlib.sha256()
    for d, dirs, files in os.walk(pkg):
        dirs[:] = sorted(x for x in dirs if x != "__pycache__")
        for f in sorted(files):
            if f.endswith(".py"):
                p = os.path.join(d, f)
                h.update(os.path.relpath(p, pkg).replace(os.sep, "/").encode())
                h.update(bytes.fromhex(_sha(p)))
    return h.hexdigest()


def corpus_sha(paths: Sequence[str]) -> str:
    """sha256 over every corpus file's bytes, the miner's class list and
    :func:`instrument_sha` -- a changed corpus OR a changed decoder never
    reads a stale cache."""
    from rvt.famgen import conformance as CO
    h = hashlib.sha256()
    h.update(bytes.fromhex(instrument_sha()))
    h.update(repr(CO.DEFAULT_CLASSES).encode())
    for p in paths:
        h.update(bytes.fromhex(_sha(p)))
    return h.hexdigest()


def load_oracle(corpus: Optional[str], cache_dir: Optional[str], *, explicit: bool = False
                ) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """``(invariants or None, report block)``.  The block carries counts and
    the summary only -- never a corpus file name (rule 3 / rule 6).

    No corpus at the DEFAULT location is a skip (a fresh clone has none); a
    corpus the caller named (``explicit``) that is missing, empty or mines
    nothing is a FAIL -- the instrument was asked for and did not run.  A corpus
    that mines only PARTLY (some files fail to decode) is ``partial``: its
    invariants are used and the run fails."""
    from rvt.famgen import conformance as CO
    if not corpus:
        return None, {"state": "skip", "reason": "no born corpus present "
                      "(samples/reference-families or samples/rft; a fresh clone has neither)"}
    if not os.path.isdir(corpus):
        return None, {"state": "fail" if explicit else "skip",
                      "reason": "the corpus directory given does not exist"}
    paths = CO.corpus_paths(corpus)
    if not paths:
        return None, {"state": "fail" if explicit else "skip",
                      "reason": "the corpus directory holds no .rfa / .rft"}
    t0 = time.time()
    key = corpus_sha(paths)
    blk: Dict[str, Any] = {"state": "ok", "corpus_sha256": key, "files": len(paths)}
    cpath = os.path.join(cache_dir, f"conformance-{key[:24]}.json") if cache_dir else None
    oracle = None
    if cpath and os.path.isfile(cpath):
        try:
            with open(cpath) as fh:
                d = json.load(fh)
            if d.get("corpus_sha256") == key:
                oracle = CO.Oracle.from_json(d["oracle"])
                blk["cache"] = "hit"
        except Exception:                                         # noqa: BLE001
            oracle = None
    if oracle is None:
        oracle = CO.mine(corpus)
        blk["cache"] = "miss" if cpath else "off"
        if cpath:
            os.makedirs(cache_dir, exist_ok=True)
            with open(cpath, "w") as fh:
                json.dump({"corpus_sha256": key, "oracle": oracle.to_json()}, fh)
    inv = oracle.invariants()
    blk.update({"summary": oracle.summary(), "decoded": oracle.files,
                "attempted": oracle.attempted, "failed": oracle.failed,
                "failure_types": dict(oracle.failure_types),
                "fallbacks": oracle.fallbacks,
                "undecoded_records": oracle.undecoded_records,
                "partial_records": oracle.partial_records,
                "classes_without_specimens": oracle.classes_without_specimens(),
                "releases": dict(oracle.releases),
                "classes_with_invariants": len(inv),
                "invariants": sum(len(v) for v in inv.values()),
                "seconds": round(time.time() - t0, 1)})
    if not oracle.files or not inv:
        blk["state"] = "fail"
        return None, blk
    if oracle.failed:
        # the invariants rest on the files that DID decode; a corpus file our
        # decoder cannot read is an instrument defect, so the run fails -- the
        # conformance rows still run (#1088 review)
        blk["state"] = "partial"
        blk["reason"] = (f"{oracle.failed} of {oracle.attempted} corpus files did not decode; "
                         f"the invariants rest on the other {oracle.files}")
    return inv, blk


# ---------------------------------------------------------------------------
# running a case
# ---------------------------------------------------------------------------

#: the NAMED port-layer refusals (DONE 4) -- and nothing else: a port layer
#: saying by name that a class has no twin in the target release.  Deliberately
#: NOT here: the BASE ``PortabilityError`` (a bare one is raised for our own
#: encoder gaps -- "unsupported field kind", "not the pinned Revit-2023 schema",
#: "framing ordinals drifted", an id that does not fit 32 bits -- every one a
#: defect, #1088 review); ``ReleaseContextError`` (also raised for a nested
#: context, a base whose schema hash misses its pin, a base whose release
#: cannot be detected -- defects); ``BaseNotCertified`` and
#: ``UnsupportedTarget`` (the battery runs only releases whose certified base
#: resolved, so either is a defect).
REFUSALS = (("rvt.genesis.port2025", "Missing2025"),
            ("rvt.genesis.port2024", "Missing2024"),
            ("rvt.genesis.port2023", "Missing2023"))


def _refusal_types() -> Tuple[type, ...]:
    """``Missing2025`` / ``Missing2024`` / ``Missing2023``.  Every other
    exception -- the bare ``PortabilityError`` they derive from included -- is
    a FAIL."""
    return tuple(getattr(importlib.import_module(mod), name) for mod, name in REFUSALS)


def classify(exc: BaseException) -> str:
    return "refused" if isinstance(exc, _refusal_types()) else "fail"


def _exc_line(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:300]}"


def _sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def slug(cid: str) -> str:
    """A portable directory/file name for a case id (portable paths):
    ``[A-Za-z0-9._-]`` + a 6-hex hash of the full id, under 80 chars."""
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", cid.split("@")[0]).strip("._-")[:64] or "case"
    return f"{s}-{hashlib.sha256(cid.encode()).hexdigest()[:6]}"


# ---------------------------------------------------------------------------
# determinism: the shifted clock and the twin process
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def shifted_clock(shift: float = TIME_SHIFT_S) -> Iterator[None]:
    """Run the ``time`` module's wall clock ``shift`` seconds ahead:
    ``time.time`` / ``time_ns`` and ``gmtime`` / ``localtime`` / ``ctime`` /
    ``asctime`` / ``strftime`` called without an explicit time.  (Elapsed-time
    measurements use ``perf_counter``, which is untouched.)"""
    T = time
    names = ("time", "time_ns", "gmtime", "localtime", "ctime", "asctime", "strftime")
    saved = {n: getattr(T, n) for n in names}

    def _time():
        return saved["time"]() + shift

    def _time_ns():
        return saved["time_ns"]() + int(shift * 1e9)

    def _at(fn):
        def wrapped(*a):
            return fn(*a) if a and a[0] is not None else fn(_time())
        return wrapped

    def _asctime(*a):
        return saved["asctime"](*a) if a else saved["asctime"](saved["localtime"](_time()))

    def _strftime(fmt, *a):
        return (saved["strftime"](fmt, *a) if a
                else saved["strftime"](fmt, saved["localtime"](_time())))

    T.time, T.time_ns = _time, _time_ns
    T.gmtime, T.localtime, T.ctime = _at(saved["gmtime"]), _at(saved["localtime"]), _at(saved["ctime"])
    T.asctime, T.strftime = _asctime, _strftime
    try:
        yield
    finally:
        for n, f in saved.items():
            setattr(T, n, f)


def _shift_datetime(shift: float) -> None:
    """In the twin process only (it never restores): ``datetime.datetime.now``
    / ``utcnow`` / ``today`` run ``shift`` seconds ahead too."""
    import datetime as DT
    real = DT.datetime
    delta = DT.timedelta(seconds=shift)

    class datetime(real):                                         # noqa: N801
        @classmethod
        def now(cls, tz=None):
            return real.now(tz) + delta

        @classmethod
        def utcnow(cls):
            return real.utcnow() + delta

        @classmethod
        def today(cls):
            return real.today() + delta
    DT.datetime = datetime


def parent_hash_seed() -> str:
    v = os.environ.get("PYTHONHASHSEED", "")
    return v if v.isdigit() else "random"


def twin_hash_seed(parent: Optional[str] = None) -> str:
    """A seed that differs from this process's: the next integer when the
    parent's is fixed, else a fixed 796 (the parent's is random)."""
    parent = parent or parent_hash_seed()
    return str((int(parent) + 1) % 4294967296) if parent.isdigit() else "796"


def _shift_text(shift: float) -> str:
    d, r = divmod(shift, 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    return f"+{int(d)} d {int(h)} h {int(m)} min {s:g} s"


class Twin:
    """The determinism twin: ONE long-lived second Python process (this file
    with ``--twin``) under another ``PYTHONHASHSEED`` and a clock
    :data:`TIME_SHIFT_S` ahead, which re-enumerates the matrix and rebuilds a
    case by its cid into the path it is given.  ``submit`` returns at once,
    so the twin builds while this process runs the read-back instruments;
    ``collect`` waits for the answer.  A twin that dies is restarted for the
    next case, and the case it died on FAILS determinism."""

    def __init__(self, out: str, bases: Dict[int, str], *, shift: float = TIME_SHIFT_S):
        self.cfg = {"out": out, "bases": {str(y): p for y, p in bases.items()}, "shift": shift}
        self.shift = shift
        self.seed = twin_hash_seed()
        self.log = os.path.join(out, "determinism-twin.log")
        self.proc: Optional[subprocess.Popen] = None
        self._log_fh = None
        self._lines: Optional["queue.Queue[str]"] = None
        self.started = 0

    def describe(self) -> Dict[str, Any]:
        return {"mode": "twin process", "parent_hash_seed": parent_hash_seed(),
                "twin_hash_seed": self.seed, "time_shift_s": self.shift,
                "time_shift": _shift_text(self.shift), "twin_starts": self.started}

    def _start(self) -> None:
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = self.seed
        env.pop("SOURCE_DATE_EPOCH", None)
        env["PYTHONPATH"] = os.pathsep.join(
            [os.path.join(ROOT, "src"), HERE] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH")
                                                 else []))
        os.makedirs(os.path.dirname(self.log), exist_ok=True)
        self._log_fh = open(self.log, "a")
        self.proc = subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), "--twin", json.dumps(self.cfg)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._log_fh,
            text=True, cwd=ROOT, env=env)
        # a reader thread, so ``collect`` can wait with a DEADLINE: a hung twin
        # fails that case's determinism instead of hanging the whole battery
        self._lines = q = queue.Queue()
        out = self.proc.stdout

        def pump():
            for line in iter(out.readline, ""):
                q.put(line)
            q.put("")                                   # EOF: the twin exited
        threading.Thread(target=pump, name="self-battery-twin", daemon=True).start()
        self.started += 1

    def submit(self, cid: str, target: str) -> None:
        if self.proc is None or self.proc.poll() is not None:
            self._start()
        self.proc.stdin.write(json.dumps({"cid": cid, "target": target}) + "\n")
        self.proc.stdin.flush()

    def probe(self, text: str = "self-battery") -> Dict[str, Any]:
        """The twin's ``time.time()``, ``datetime.now()`` and ``hash(text)`` --
        the evidence that its clock and hash seed really differ from ours."""
        if self.proc is None or self.proc.poll() is not None:
            self._start()
        self.proc.stdin.write(json.dumps({"probe": text}) + "\n")
        self.proc.stdin.flush()
        return self.collect()

    def collect(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        timeout = TWIN_TIMEOUT_S if timeout is None else timeout
        try:
            line = self._lines.get(timeout=timeout) if self.proc and self._lines else ""
        except queue.Empty:
            self.close(kill=True)
            raise RuntimeError(f"the determinism twin gave no answer in {timeout:g} s -- "
                               f"killed, restarted for the next case; see {self.log}")
        if not line:
            rc = self.proc.poll() if self.proc else None
            self.close()
            raise RuntimeError(f"the determinism twin died (rc={rc}); see {self.log}")
        return json.loads(line)

    def close(self, kill: bool = False) -> None:
        if self.proc is not None:
            try:
                if kill:
                    raise TimeoutError
                self.proc.stdin.close()
                self.proc.wait(timeout=30)
            except Exception:                                     # noqa: BLE001
                self.proc.kill()
                try:
                    self.proc.wait(timeout=30)
                except Exception:                                 # noqa: BLE001
                    pass
            self.proc = None
            self._lines = None
        if self._log_fh is not None:
            self._log_fh.close()
            self._log_fh = None


def _twin_index() -> Dict[str, Case]:
    """release-free case key -> Case: the full matrix + the pinned probes."""
    cases, _decl = enumerate_matrix()
    idx = {c.key: c for c in cases if c.rebuildable}
    for k, thunk in _catalog().items():
        idx[f"pinned:{k}"] = Case("pinned", k, {}, build=thunk, write=_default_write)
    return idx


def _twin_main(cfg_json: str) -> int:
    """The twin's loop: one JSON request per line on stdin -> one JSON answer
    per line on the protocol channel.  Anything the engine prints goes to
    stderr (the twin's log), never into the protocol."""
    cfg = json.loads(cfg_json)
    proto = os.fdopen(os.dup(1), "w", buffering=1)
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    stack = contextlib.ExitStack()
    stack.enter_context(shifted_clock(float(cfg["shift"])))      # for the twin's whole life
    _shift_datetime(float(cfg["shift"]))
    make_family_module()._ensure_standalone()
    bat = Battery(cfg["out"], bases={int(y): p for y, p in cfg["bases"].items()})
    index: Optional[Dict[str, Case]] = None
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        req = json.loads(line)
        t0 = time.perf_counter()
        resp: Dict[str, Any]
        if req.get("probe"):          # what the twin's clock and string hashing say
            import datetime as DT
            proto.write(json.dumps({"time": time.time(), "now": DT.datetime.now().timestamp(),
                                    "hash": hash(req["probe"]),
                                    "hash_seed": os.environ.get("PYTHONHASHSEED")}) + "\n")
            continue
        try:
            if index is None:
                index = _twin_index()
            key, _, y = req["cid"].rpartition("@")
            if key not in index:
                raise KeyError(f"the twin's enumeration has no case {key!r}")
            case = Case(**{**index[key].__dict__, "release": int(y)})
            if case.route is not None:
                try:
                    resp = {"route": case.route(req["target"], case.release)}
                except (Exception, SystemExit) as e:              # noqa: BLE001
                    resp = {"route_exc": [classify(e), _exc_line(e)]}
            else:
                stage, got, _t = bat.produce(case, req["target"])
                resp = {"stage": stage, "error": None if stage is None else _exc_line(got)}
        except BaseException as e:                                # noqa: BLE001
            resp = {"stage": "twin", "error": _exc_line(e)}
        resp["seconds"] = round(time.perf_counter() - t0, 2)
        resp["hash_seed"] = os.environ.get("PYTHONHASHSEED")
        proto.write(json.dumps(resp, default=str) + "\n")
    stack.close()
    return 0


class Battery:
    """Shared state of a run: bases per release, the oracle's invariants,
    the alias table, the output root."""

    def __init__(self, out: str, *, bases: Optional[Dict[int, str]] = None,
                 invariants: Optional[Dict[str, Any]] = None,
                 corpus_reason: str = "no born corpus given", keep: bool = False,
                 twin: Optional[Twin] = None,
                 alias_groups: Optional[Dict[str, int]] = None):
        from rvt.frontdoor import release_ctx as RC
        self.out = out
        self.native = RC.native_release()
        self.bases: Dict[int, str] = dict(bases or {})
        self.invariants = invariants
        self.corpus_reason = corpus_reason
        self.keep = keep
        self.twin = twin
        #: release-free case key -> pinned alias group; None = every alias allowed
        #: (a bare Battery; main() always loads the pin)
        self.alias_groups = alias_groups
        self.seen: Dict[Tuple[int, str], str] = {}        # (release, sha256) -> cid

    def alias_pinned(self, key: str, alias_cid: str) -> bool:
        if self.alias_groups is None:
            return True
        g = self.alias_groups.get(key)
        return g is not None and g == self.alias_groups.get(alias_cid.rpartition("@")[0])

    def base(self, year: int) -> str:
        if year not in self.bases:
            from rvt.frontdoor import release_ctx as RC
            b = RC._bundled_base_of(year)
            if not b:
                raise RuntimeError(f"no pinned certified base for Revit {year}")
            self.bases[year] = b
        return self.bases[year]

    @contextlib.contextmanager
    def release_scope(self, year: int) -> Iterator[None]:
        """Build AND write inside the release's build context (as
        ``matrix._in_release`` / ``router._emit_at_target`` do); one context
        per case, exited before the read-back instruments run."""
        if year == self.native:
            yield
            return
        from rvt.frontdoor import release_ctx as RC
        with RC.release_build_context(self.base(year)):
            yield

    # -- producing ------------------------------------------------------
    def produce(self, case: Case, path: str) -> Tuple[Optional[str], Any, Dict[str, Any]]:
        """Build + write one family case inside its release.  Returns
        ``(failed stage or None, exception or write report, timings)``.

        ``path`` is REMOVED first: a file left there by an earlier run (a fixed
        ``--out``, a ``--keep`` run) would otherwise satisfy "the writer wrote a
        file" and hand last run's bytes to every read-back instrument and to
        determinism (#1088 review)."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.lexists(path):
            os.remove(path)
        stage = "build"
        t: Dict[str, Any] = {}
        t0 = time.perf_counter()              # never the (possibly shifted) wall clock
        try:
            with self.release_scope(case.release):
                prod = case.build()
                t["build"] = round(time.perf_counter() - t0, 2)
                stage = "write"
                t1 = time.perf_counter()
                rep = case.write(prod, path)
                t["write"] = round(time.perf_counter() - t1, 2)
        except (Exception, SystemExit) as e:                      # noqa: BLE001
            t.setdefault(stage, round(time.perf_counter() - t0, 2))
            return stage, e, t
        if not os.path.isfile(path):
            return "write", RuntimeError("the writer returned but wrote no file"), t
        return None, rep, t

    # -- one case -> rows --------------------------------------------------
    def run(self, case: Case) -> List[Dict[str, Any]]:
        if case.error:
            row = _new_row(case, case.cid)
            _set(row, "build", "fail", case.error)
            return [_finish(row, 0.0)]
        if case.route is not None:
            return self._run_route(case)
        return [self._run_family(case)]

    def _run_family(self, case: Case) -> Dict[str, Any]:
        t0 = time.time()
        row = _new_row(case, case.cid)
        name = slug(case.cid)
        # a clean case directory: nothing an earlier run left (its a/ or the
        # twin's b/) can be graded as this run's output
        shutil.rmtree(os.path.join(self.out, str(case.release), name), ignore_errors=True)
        da = os.path.join(self.out, str(case.release), name, "a")
        db = os.path.join(self.out, str(case.release), name, "b")
        path = os.path.join(da, FAMILY_BASENAME)
        stage, got, t = self.produce(case, path)
        row["timings"].update(t)
        if stage is not None:
            st = classify(got)
            if stage == "write":
                _set(row, "build", "pass", "")
            _set(row, stage, st, _exc_line(got))
            if st == "fail":
                row["traceback"] = "".join(traceback.format_exception(
                    type(got), got, got.__traceback__))[-1500:]
            return _finish(row, time.time() - t0)
        _set(row, "build", "pass", "")
        v = got.get("verify") if isinstance(got, dict) else None
        _set(row, "write", "pass", f"{os.path.getsize(path)} bytes"
             + (f"; verify in context ok={v.get('ok')}" if isinstance(v, dict) else ""))
        row["path"] = path
        row["sha256"] = sha = _sha(path)
        alias = self.seen.get((case.release, sha))
        if alias:
            row["alias_of"] = alias
            for inst in INSTRUMENTS[2:]:
                _set(row, inst, "skip", f"byte-identical to {alias}")
            if self.alias_pinned(case.key, alias):
                row["state"] = "alias"
            else:
                # a variant that silently stopped having an effect looks exactly like this
                _set(row, "build", "fail",
                     f"the variant had no effect: byte-identical to {alias}, and the alias "
                     f"pin ({os.path.relpath(ALIAS_PIN, ROOT)}) does not group the two -- "
                     f"re-pin with --pin-aliases only if that is by design")
            if not self.keep:
                shutil.rmtree(os.path.dirname(da), ignore_errors=True)
                row["path"] = None
            return _finish(row, time.time() - t0)
        self.seen[(case.release, sha)] = case.cid
        # determinism (#168): the same case again, another directory, same
        # basename -- by the twin (another process, hash seed and clock) while
        # the read-back instruments run here
        pb = os.path.join(db, FAMILY_BASENAME)
        twin = self.twin if case.rebuildable else None
        twin_err: Optional[str] = None
        if twin is not None:
            try:
                twin.submit(case.cid, pb)
            except Exception as e:                                # noqa: BLE001
                twin, twin_err = None, _exc_line(e)
        self.instruments(row, path, case.release)
        t1 = time.perf_counter()
        if twin is not None:
            try:
                resp = twin.collect()
                stage, err = resp.get("stage"), resp.get("error")
            except Exception as e:                                # noqa: BLE001
                stage, err = "twin", _exc_line(e)
            how = (f"twin process, PYTHONHASHSEED {twin.seed} vs {parent_hash_seed()}, "
                   f"clock {_shift_text(twin.shift)}")
        elif case.rebuildable and self.twin is not None:
            stage, err, how = "twin", twin_err, "twin process"
        else:
            with shifted_clock():
                stage, got, _t = self.produce(case, pb)
            err = None if stage is None else _exc_line(got)
            how = f"in-process rebuild, clock {_shift_text(TIME_SHIFT_S)}"
        row["timings"]["determinism"] = round(time.perf_counter() - t1, 2)
        if stage is not None:
            _set(row, "determinism", "fail",
                 f"second build failed at {stage}: {err} ({how})")
        elif not os.path.isfile(pb):
            _set(row, "determinism", "fail", f"the second build wrote no file ({how})")
        else:
            sb = _sha(pb)
            _set(row, "determinism", "pass" if sb == sha else "fail",
                 (f"sha256 equal ({how})" if sb == sha
                  else f"sha256 differs ({sha[:12]} vs {sb[:12]}; {how})"))
        if not self.keep:
            shutil.rmtree(db, ignore_errors=True)
        return _finish(row, time.time() - t0)

    def _run_route(self, case: Case) -> List[Dict[str, Any]]:
        import glob
        t0 = time.time()
        name = slug(case.cid)
        dirs = {k: os.path.join(self.out, str(case.release), name, k) for k in ("a", "b")}
        res: Dict[str, Dict[str, str]] = {}
        errs: Dict[str, Optional[Tuple[str, str]]] = {}

        def judged(rep: Dict[str, Any]) -> Optional[Tuple[str, str]]:
            return None if rep.get("ok") else (
                "fail", f"route not ok: {rep.get('line')} {rep.get('errors') or ''}"[:400])

        for d in dirs.values():
            shutil.rmtree(d, ignore_errors=True)
        twin = self.twin if case.rebuildable else None
        how = (f"twin process, PYTHONHASHSEED {twin.seed} vs {parent_hash_seed()}, "
               f"clock {_shift_text(twin.shift)}" if twin is not None
               else f"in-process rerun, clock {_shift_text(TIME_SHIFT_S)}")
        if twin is not None:                  # the second run goes first, concurrently
            try:
                twin.submit(case.cid, dirs["b"])
            except Exception as e:                                # noqa: BLE001
                twin, errs["b"] = None, ("fail", f"twin: {_exc_line(e)}")
        for k in ("a", "b"):
            d = dirs[k]
            if k == "b" and "b" in errs:
                pass
            elif k == "b" and twin is not None:
                try:
                    resp = twin.collect()
                except Exception as e:                            # noqa: BLE001
                    resp = {"route_exc": ["fail", f"twin: {_exc_line(e)}"]}
                if "route" in resp:
                    errs[k] = judged(resp["route"])
                else:
                    st, msg = resp.get("route_exc") or ["fail", resp.get("error")]
                    errs[k] = (st, msg)
            else:
                try:
                    if k == "b":
                        with shifted_clock():
                            rep = case.route(d, case.release)
                    else:
                        rep = case.route(d, case.release)
                    errs[k] = judged(rep)
                except (Exception, SystemExit) as e:              # noqa: BLE001
                    errs[k] = (classify(e), _exc_line(e))
            res[k] = {os.path.relpath(p, d).replace(os.sep, "/"): p
                      for p in sorted(glob.glob(os.path.join(d, "**", "*.rfa"), recursive=True))}
        rows: List[Dict[str, Any]] = []
        if errs["a"] or not res["a"]:
            row = _new_row(case, case.cid)
            st, msg = errs["a"] or ("fail", "the route wrote no .rfa")
            _set(row, "build", st, msg)
            rows.append(_finish(row, time.time() - t0))
        for rel, path in res["a"].items():
            sub = Case(case.source, f"{case.product}/{rel[:-4]}", dict(case.variant),
                       release=case.release, repro=case.repro)
            row = _new_row(sub, sub.cid)
            t1 = time.time()
            _set(row, "build", "pass", "router.route ok" if not errs["a"] else
                 f"written, but {errs['a'][1]}")
            _set(row, "write", "pass", f"{os.path.getsize(path)} bytes")
            row["path"] = path
            row["sha256"] = sha = _sha(path)
            self.instruments(row, path, case.release)
            other = res["b"].get(rel)
            if other is None:
                _set(row, "determinism", "fail", "the second route run did not write it"
                     + (f" ({errs['b'][1]})" if errs["b"] else "") + f" ({how})")
            else:
                sb = _sha(other)
                _set(row, "determinism", "pass" if sb == sha else "fail",
                     (f"sha256 equal ({how})" if sb == sha
                      else f"sha256 differs ({sha[:12]} vs {sb[:12]}; {how})"))
            rows.append(_finish(row, time.time() - t1))
        extra = sorted(set(res["b"]) - set(res["a"]))
        if extra:
            row = _new_row(case, case.cid + "#extra")
            _set(row, "determinism", "fail", f"the second run wrote {len(extra)} more .rfa")
            rows.append(_finish(row, 0.0))
        if not self.keep:
            shutil.rmtree(dirs["b"], ignore_errors=True)
        return rows

    # -- the read-back instruments ------------------------------------------
    def instruments(self, row: Dict[str, Any], path: str, year: int) -> None:
        from rvt.objects import decode_memo
        with decode_memo():
            for inst, fn in (("release", self._i_release), ("verify", self._i_verify),
                             ("validate", self._i_validate),
                             ("provenance", self._i_provenance), ("law", self._i_law),
                             ("conformance", self._i_conformance)):
                t0 = time.time()
                try:
                    st, detail, extra = fn(path, year)
                except Exception as e:                            # noqa: BLE001
                    st, detail, extra = "fail", f"instrument crashed: {_exc_line(e)}", None
                _set(row, inst, st, detail)
                if extra:
                    row["instruments"][inst].update(extra)
                row["timings"][inst] = round(time.time() - t0, 2)

    def _i_release(self, path, year):
        from rvt import versions as V
        got = V.detect_release(path)
        return ("pass" if got == year else "fail", f"detect_release = {got}", None)

    def _i_verify(self, path, year):
        from rvt.famgen import skeleton as SK
        from rvt.global_framing import enter_own_release
        with contextlib.ExitStack() as st:
            note = enter_own_release(st, path)
            r = SK.verify_family_rfa(path)
        d = r.get("decode_seq102") or {}
        detail = (f"crc_fail={r.get('gzip_crc_failures')} ecc_mismatch={r.get('ecc_mismatch')}"
                  f" decode={d.get('clean')}/{d.get('records')}")
        if note:
            # a file WE wrote must name its release through its own schema; a
            # fallback rung reading it is a defect, not a footnote (#1088 review)
            return "fail", f"our file's own schema did not resolve its release ({note}); " \
                           + detail, None
        return ("pass" if r.get("ok") else "fail", detail, None)

    def _i_validate(self, path, year):
        from rvt.validate import validate_file
        rep = validate_file(path, family=True)
        errs = [f for f in rep.findings if f.severity == "error"]
        detail = f"{len(errs)} error(s)"
        if errs:
            detail += ": " + "; ".join(str(f.message)[:160] for f in errs[:3])
        return ("pass" if not errs else "fail", detail, {"errors": len(errs)})

    def _i_provenance(self, path, year):
        from rvt.famgen import famdoc_adoc as FA
        from rvt.famgen import factory as F
        v2 = FA.provenance_scan_v2(path, donor=self.base(year))
        ledger = F.provenance_scan(path)
        bad = [f"v2.{k}" for k, ok in (v2.get("checks") or {}).items() if not ok]
        bad += [f"ledger.{k}" for k, ok in (ledger.get("checks") or {}).items() if not ok]
        if v2.get("ok") is False and not bad:
            bad.append("v2.ok")
        if not v2.get("checks"):
            bad.append("v2: no checks ran")
        if not ledger.get("checks"):
            bad.append("ledger: no checks ran")
        n = len(v2.get("checks") or {}) + len(ledger.get("checks") or {})
        ident = (v2.get("checks") or {}).get("identity_is_ours")
        detail = (f"{n - len(bad)}/{n} checks true; identity_is_ours={ident}"
                  + (f"; FAILING {', '.join(bad)}" if bad else ""))
        return ("pass" if not bad else "fail", detail, {"failing_checks": bad})

    def _i_law(self, path, year):
        from rvt.famgen import constraint_law as CL
        units = {"family": 0}
        units.update({f"nested {g[:8]}": u for g, u in sorted(CL.nested_units(path).items())})
        errs = []
        for label, u in units.items():
            fs = CL.check_file(path) if u == 0 else CL.check_file(path, unit=u)
            errs += [f"[{label}] {str(f.get('message', ''))[:160]}" for f in fs
                     if f.get("severity") == "error"]
        detail = (f"{len(units)} document(s), {len(errs)} error(s)"
                  + (": " + "; ".join(errs[:2]) if errs else ""))
        return ("pass" if not errs else "fail", detail, {"errors": len(errs)})

    def _i_conformance(self, path, year):
        from rvt.famgen import conformance as CO
        if not self.invariants:
            return "skip", self.corpus_reason, None
        st: Dict[str, Any] = {}
        fs = CO.check_file(path, self.invariants, stats=st)
        qs = [f for f in fs if f["severity"] == "question"]
        notes = [f for f in fs if f["severity"] == "note"]
        fields = sorted({f"{f['class']}.{f['field']}" for f in qs})
        partial = st.get("partial_records", 0) + st.get("undecoded_records", 0)
        extra = {"questions": len(qs), "notes": len(notes),
                 "rules_evaluated": st.get("rules_evaluated", 0),
                 "elements": st.get("elements", 0), "question_fields": fields,
                 "partial_records": st.get("partial_records", 0),
                 "undecoded_records": st.get("undecoded_records", 0)}
        detail = (f"{len(qs)} question(s), {len(notes)} note(s) over "
                  f"{st.get('rules_evaluated', 0)} rule checks")
        if partial:
            # their fields were never checked: a partial decode is not a pass
            return "fail", (f"{partial} record(s) of the checked classes decoded only partly "
                            f"or not at all, so their fields went unchecked; " + detail), extra
        if not st.get("rules_evaluated"):
            return "fail", "inert: 0 rules evaluated on this file", extra
        if st.get("release_note"):
            # read on a fallback rung: every field was checked against a table
            # the file itself did not choose -- not a pass for a file we wrote
            return "fail", (f"our file's own schema did not resolve its release "
                            f"({st['release_note']}); " + detail), extra
        if qs:
            detail += ": " + qs[0]["message"][:160]
        return ("pass" if not qs else "fail", detail, extra)


def _new_row(case: Case, cid: str) -> Dict[str, Any]:
    return {"case": cid, "tuple": case.tuple(), "repro": _jsonable(case.repro),
            "state": None, "instruments": {}, "timings": {}}


def _set(row: Dict[str, Any], inst: str, state: str, detail: str) -> None:
    row["instruments"][inst] = {"state": state, "detail": detail}


def _finish(row: Dict[str, Any], seconds: float) -> Dict[str, Any]:
    for inst in INSTRUMENTS:
        row["instruments"].setdefault(inst, {"state": "not_run", "detail": ""})
    row["instruments"] = {i: row["instruments"][i] for i in INSTRUMENTS}
    states = [v["state"] for v in row["instruments"].values()]
    if row["state"] != "alias":
        row["state"] = ("fail" if "fail" in states else
                        "refused" if "refused" in states else "pass")
    row["ok"] = row["state"] in ("pass", "alias")
    # the flat view (tests/test_constraint_law_910.py reads steps["law"])
    row["steps"] = {k: ("ok" if v["state"] == "pass" else
                        f"{v['state'].upper()} {v['detail']}".strip())
                    for k, v in row["instruments"].items()}
    row["seconds"] = round(seconds, 2)
    return row


# ---------------------------------------------------------------------------
# PINNED probes: regression pins of lanes no declaration enumerates
# ---------------------------------------------------------------------------

def _catalog() -> Dict[str, Callable[[], Any]]:
    """The PINNED probes -- NOT the matrix (that is enumerated, see the module
    docstring).  Each pins a lane the engine's declarations do not reach:

    * ``archetype_strut_trapeze`` -- the desktop-verified driving trapeze
      from its prompt (#904 / #907);
    * ``drive_one_box_law`` / ``drive_one_box_control`` -- the one-box probe
      pair P / C under the born in-plane law, both desktop-verified, carrying
      no m_constrInfo back-edges (#787 / #907 / #910);
    * ``panelboard_types`` -- a multi-type family (#163), a free-text option
      no axis enumerates;
    * ``ifc_pset_drives`` -- an IFC's pset parameters driving the parts they
      name (#714), the assembly lane's plan built all-or-nothing;
    * ``shape_mixed_assembly`` -- parts of DIFFERENT shapes sharing one family
      (box + cylinder + cylinder_y), the multi-part form the prompt and IFC
      assembly lanes emit; the part_shape source builds one part per family;
    * ``panelboard_600A`` -- a free-numeric mains rating no axis enumerates."""
    from rvt.famgen import factory as F

    def _one_box(regen_edge):
        def mk():
            from rvt.famgen import drive_law as DL
            prod = F.make_generic_model(
                parts=[{"name": "b", "shape": "box", "width_ft": 2,
                        "depth_ft": 1, "height_ft": 1}],
                name="B_drive" + ("" if regen_edge else "_C"),
                category="generic_model", source="self battery", drive=True)
            DL.apply_born_inplane_law(prod.doc, regen_edge=regen_edge)
            return prod
        return mk

    def _pset_drives():
        from rvt.ifc import pset_drive as PD
        parts = [{"name": "pad", "shape": "box", "width_ft": 4, "depth_ft": 3,
                  "height_ft": 0.5, "center": (0, 0), "base_z_ft": 0},
                 {"name": "tank", "shape": "box", "width_ft": 3, "depth_ft": 2,
                  "height_ft": 4, "center": (0, -0.25), "base_z_ft": 0.5}]
        vals = {"PadWidth": ("pad", 4.0), "TankDepth": ("tank", 2.0),
                "TankHeight": ("tank", 4.0)}
        coll = {"params": {n: ("length", v) for n, (_p, v) in vals.items()},
                "sources": {n: {"pset": "P", "product": p, "products": [p]}
                            for n, (p, _v) in vals.items()}}
        plan = PD.plan(parts, coll)
        return F.make_generic_model(parts=parts, name="B_pset_drives",
                                    source="self battery",
                                    numeric_params=dict(coll["params"]),
                                    drives=plan["drives"], heights=plan["heights"],
                                    settle_drives=True)

    return {
        "archetype_strut_trapeze": lambda: F.make_archetype(
            product="strut_trapeze", prompt="a 2 tier slotted trapeze with threaded rod"),
        "drive_one_box_law": _one_box(True),
        "drive_one_box_control": _one_box(False),
        "panelboard_types": lambda: F.make_panelboard(name="B_panelT", types=["225A", "400A"]),
        "ifc_pset_drives": _pset_drives,
        "shape_mixed_assembly": lambda: F.make_generic_model(
            parts=[{"name": "base", "shape": "box", "width_ft": 2, "depth_ft": 2,
                    "height_ft": 0.2},
                   {"name": "mast", "shape": "cylinder", "radius_ft": 0.1,
                    "height_ft": 3, "base_z_ft": 0.2},
                   {"name": "arm", "shape": "cylinder_y", "radius_ft": 0.08,
                    "length_ft": 1.5, "center": (0, 0.75), "base_z_ft": 3.0}],
            name="B_mixed", source="self battery"),
        "panelboard_600A": lambda: F.make_panelboard(name="B_600", mains_a=600),
    }


def _run_one(key: str, thunk: Callable[[], Any], out_dir: str,
             oracle_inv: Optional[Dict[str, Any]], *,
             battery: Optional[Battery] = None, rebuildable: bool = False) -> Dict[str, Any]:
    """Every instrument on one thunk at the native release; the row's
    ``steps`` maps instrument -> ``"ok"`` | ``"FAIL ..."`` | ``"SKIP ..."``.
    ``rebuildable`` (main's pins, which ARE ``_catalog()``): the battery's
    twin rebuilds it by key; any other thunk is rebuilt in-process."""
    b = battery or Battery(out_dir, invariants=oracle_inv)
    case = Case("pinned", key, {}, release=b.native, build=thunk, write=_default_write,
                rebuildable=rebuildable)
    seen, b.seen = b.seen, {}             # a pin is never an alias of a matrix case
    try:
        row = b.run(case)[0]
    finally:
        b.seen = seen
    row["artefact"] = key
    return row


# ---------------------------------------------------------------------------
# the report
# ---------------------------------------------------------------------------

def alias_groups(pin: Optional[Dict[str, Any]]) -> Dict[str, int]:
    """release-free case key -> group index, from the pin's ``groups``."""
    out: Dict[str, int] = {}
    for i, g in enumerate((pin or {}).get("groups") or []):
        for k in g:
            out[k] = i
    return out


def load_alias_pin(path: str = ALIAS_PIN) -> Dict[str, Any]:
    """The pin, or an EMPTY pin when the file is missing (every alias then FAILS)."""
    if not os.path.isfile(path):
        return {"groups": [], "missing": True}
    with open(path) as fh:
        return json.load(fh)


def pin_from_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """The release-free alias groups a run observed (union of every release)."""
    parent: Dict[str, str] = {}

    def find(k: str) -> str:
        parent.setdefault(k, k)
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k
    for r in rows:
        if r.get("alias_of"):
            a = find(r["case"].rpartition("@")[0])
            b = find(r["alias_of"].rpartition("@")[0])
            if a != b:
                parent[max(a, b)] = min(a, b)
    groups: Dict[str, List[str]] = {}
    for k in parent:
        groups.setdefault(find(k), []).append(k)
    gs = sorted(sorted(g) for g in groups.values())
    return {"issue": 796, "tool": "tools/self_battery.py --pin-aliases",
            "what": ("release-free groups of self-battery case keys whose written bytes are "
                     "identical BY DESIGN (a variant the constructor accepts that does not "
                     "change that product); an alias outside these groups FAILS the run"),
            "relations": sum(len(g) - 1 for g in gs), "groups": gs}


def alias_drift(rows: List[Dict[str, Any]], groups: Dict[str, int]) -> List[Dict[str, Any]]:
    """Pinned groups whose members, built in one release, are NO LONGER
    byte-identical (a note: a pinned no-op variant started to have an effect)."""
    by: Dict[Tuple[str, int], Dict[str, List[str]]] = {}
    for r in rows:
        if not r.get("sha256"):
            continue
        key, _, y = r["case"].rpartition("@")
        if key in groups:
            by.setdefault((y, groups[key]), {}).setdefault(r["sha256"], []).append(r["case"])
    return [{"release": y, "distinct": len(shas),
             "cases": sorted(c for cs in shas.values() for c in cs)}
            for (y, _g), shas in sorted(by.items()) if len(shas) > 1]


def summarize(rows: List[Dict[str, Any]],
              groups: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    per = {i: {s: 0 for s in STATES} for i in INSTRUMENTS}
    for r in rows:
        if r["state"] == "alias":
            continue
        for i in INSTRUMENTS:
            per[i][r["instruments"][i]["state"]] += 1
    totals = {s: sum(1 for r in rows if r["state"] == s)
              for s in ("pass", "fail", "refused", "alias")}

    def listing(state):
        return [{"case": r["case"], "tuple": r["tuple"], "instrument": i,
                 "detail": r["instruments"][i]["detail"]}
                for r in rows for i in INSTRUMENTS
                if r["instruments"][i]["state"] == state]
    by_release: Dict[str, Dict[str, int]] = {}
    for r in rows:
        y = r["case"].rpartition("@")[2].split("#")[0]
        d = by_release.setdefault(y, {"rows": 0, "pass": 0, "fail": 0, "refused": 0,
                                      "alias": 0})
        d["rows"] += 1
        d[r["state"]] += 1
    return {"per_instrument": per, "totals": totals, "by_release": by_release,
            "failures": listing("fail"), "refusals": listing("refused"),
            "aliases": [{"case": r["case"], "alias_of": r["alias_of"], "state": r["state"]}
                        for r in rows if r.get("alias_of")],
            "alias_drift": alias_drift(rows, groups or {})}


def text_summary(report: Dict[str, Any]) -> str:
    s = report["summary"]
    m = report["matrix"]
    lines = [f"self-battery ({report['mode']}): {m['cases']} cases over "
             f"{len(report['releases']['run'])} release(s) {report['releases']['run']}, "
             f"{m['distinct']} distinct documents, {s['totals']['alias']} aliases; "
             f"{s['totals']['pass']} pass, {s['totals']['fail']} FAIL, "
             f"{s['totals']['refused']} refused  ({report['seconds']:.0f} s)"]
    for y, why in sorted(report["releases"]["skipped"].items()):
        lines.append(f"  release {y} skipped: {why}")
    for y, why in sorted((report["releases"].get("broken") or {}).items()):
        lines.append(f"  release {y} BROKEN (a FAIL row): {why}")
    c = report["corpus"]
    lines.append(f"  corpus: {c.get('summary') or c.get('reason')}"
                 + (f"  -- PARTIAL (a FAIL): {c['reason']}" if c.get("state") == "partial" else ""))
    d = report.get("determinism") or {}
    if d:
        lines.append(f"  determinism: {d.get('mode')}, clock {d.get('time_shift')}"
                     + (f", PYTHONHASHSEED {d.get('twin_hash_seed')} vs "
                        f"{d.get('parent_hash_seed')}" if d.get("twin_hash_seed") else ""))
    lines.append("  instrument      " + " ".join(f"{st:>8}" for st in STATES))
    for inst, counts in s["per_instrument"].items():
        lines.append(f"  {inst:<15} " + " ".join(f"{counts[st]:>8}" for st in STATES))
    if s["failures"]:
        lines.append(f"FAILURES ({len(s['failures'])} instrument x case):")
        for f in s["failures"]:
            lines.append(f"  FAIL {f['case']}  [{f['instrument']}] {f['detail'][:200]}")
    if s["refusals"]:
        lines.append(f"REFUSED ({len(s['refusals'])}, named refusals -- not failures):")
        for f in s["refusals"]:
            lines.append(f"  REFUSED {f['case']}  [{f['instrument']}] {f['detail'][:200]}")
    aliases = s.get("aliases") or []
    if aliases:
        lines.append(f"ALIASES ({len(aliases)}: byte-identical to an earlier case of the same "
                     f"release; pinned ones pass, unpinned ones FAIL):")
        for a in aliases:
            lines.append(f"  {'ALIAS' if a['state'] == 'alias' else 'FAIL '} {a['case']}"
                         f"  = {a['alias_of']}")
    for d in s.get("alias_drift") or []:
        lines.append(f"NOTE pinned alias group no longer byte-identical at {d['release']} "
                     f"({d['distinct']} distinct): {', '.join(d['cases'])[:300]}")
    pinned = report.get("pinned") or []
    if pinned:
        bad = [r for r in pinned if not r["ok"]]
        lines.append(f"pinned probes: {len(pinned) - len(bad)}/{len(pinned)} pass")
        for r in bad:
            why = next((f"[{k}] {v}" for k, v in r["steps"].items()
                        if v.startswith(("FAIL", "REFUSED"))), "")
            lines.append(f"  FAIL {r['case']}: {why[:200]}")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)
    if args[:1] == ["--twin"]:                       # the determinism twin (internal)
        return _twin_main(args[1])
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=os.path.join(ROOT, "out", "self-battery"),
                    help="where the built families go (default out/self-battery)")
    ap.add_argument("--report", default=None,
                    help="the JSON report (default <out>.json, i.e. out/self-battery.json); "
                         "the text summary goes beside it as .txt")
    ap.add_argument("--quick", action="store_true",
                    help="the CI shard: the native release, every archetype at its nominal")
    ap.add_argument("--release", default=None, metavar="Y[,Y]",
                    help="only these releases (default: every creation-certified one)")
    ap.add_argument("--source", default=None, metavar="S[,S]",
                    help=f"only these sources ({', '.join(SOURCES)})")
    ap.add_argument("--only", default=None, metavar="REGEX",
                    help="only cases whose id matches (e.g. 'archetype:conduit')")
    ap.add_argument("--corpus", default=None,
                    help="born family documents to mine (default samples/reference-families, "
                         "else samples/rft); a corpus given here that yields nothing FAILS")
    ap.add_argument("--no-corpus", action="store_true", help="skip conformance")
    ap.add_argument("--cache", default=None,
                    help="conformance invariant cache dir (default <out>/.cache)")
    ap.add_argument("--no-pinned", action="store_true", help="skip the pinned probes")
    ap.add_argument("--no-twin", action="store_true",
                    help="judge determinism in-process (clock shifted, same hash seed) "
                         "instead of in the twin process")
    ap.add_argument("--aliases", default=ALIAS_PIN,
                    help="the alias pin (default tools/self_battery_aliases.json)")
    ap.add_argument("--pin-aliases", action="store_true",
                    help="accept every alias of this FULL run and rewrite the pin from it")
    ap.add_argument("--keep", action="store_true",
                    help="keep the determinism copies (b/) and alias files")
    ap.add_argument("--list", action="store_true", help="print the matrix; build nothing")
    ap.add_argument("--json", action="store_true", help="print the JSON report")
    a = ap.parse_args(args)
    if a.pin_aliases and (a.quick or a.only or a.source or a.release):
        ap.error("--pin-aliases rewrites the pin from a FULL run: drop --quick / --only / "
                 "--source / --release")
    # determinism is judged with no SOURCE_DATE_EPOCH (as matrix._pinned_env
    # does) -- and the caller's value is put back however the run ends
    saved = os.environ.pop("SOURCE_DATE_EPOCH", None)
    try:
        return _main(a, args, saved)
    finally:
        if saved is not None:
            os.environ["SOURCE_DATE_EPOCH"] = saved


def _main(a: argparse.Namespace, args: List[str], sde: Optional[str]) -> int:
    t_start = time.time()
    env = {"SOURCE_DATE_EPOCH": sde, "RVT_GENESIS_BASE": os.environ.get("RVT_GENESIS_BASE")}
    only_rel = [int(y) for y in a.release.split(",")] if a.release else None
    run_rel, bases, skipped, broken = releases(only_rel, quick=a.quick)
    sources = [s.strip() for s in a.source.split(",")] if a.source else None
    base_cases, decl = enumerate_matrix(quick=a.quick, sources=sources)
    rx = re.compile(a.only) if a.only else None
    # a creation-certified release whose base is broken is a FAIL row, never a skip
    cases: List[Case] = [Case("release", "base", {}, release=y, error=f"Revit {y}: {why}")
                         for y, why in sorted(broken.items(), reverse=True)]
    for y in run_rel:
        for c in base_cases:
            cc = Case(**{**c.__dict__, "release": y})
            if rx is None or rx.search(cc.cid):
                cases.append(cc)
    if a.list:
        for c in cases:
            print(c.cid + ("   [DECLARATION FAIL] " + c.error if c.error else ""))
        print(f"{len(cases)} cases; releases {run_rel}; skipped {skipped}; broken "
              f"{sorted(broken)}")
        return 0 if cases else 1
    if not cases:
        print(f"NOTHING TO RUN: 0 cases (releases {run_rel}, skipped {skipped}, "
              f"--only {a.only!r}, --source {a.source!r}) -- an empty run is a FAIL, "
              f"never a pass")
        return 1

    # the oracle FIRST: no build has armed anything against reading the
    # quarantined corpus yet (and it is read as statistics only)
    corpus = None if a.no_corpus else (a.corpus or default_corpus())
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    inv, cblk = load_oracle(corpus, a.cache or os.path.join(out, ".cache"),
                            explicit=a.corpus is not None and not a.no_corpus)
    if a.no_corpus:
        cblk = {"state": "skip", "reason": "--no-corpus"}
    elif corpus and a.corpus is None:
        cblk["dir"] = os.path.relpath(corpus, ROOT)

    pin = load_alias_pin(a.aliases)
    groups = alias_groups(pin)
    make_family_module()._ensure_standalone()
    twin = None if a.no_twin else Twin(out, bases)
    bat = Battery(out, bases=bases, invariants=inv, keep=a.keep, twin=twin,
                  alias_groups=None if a.pin_aliases else groups,
                  corpus_reason=cblk.get("reason") or f"corpus unusable: {cblk.get('summary')}")
    rows: List[Dict[str, Any]] = []
    pinned: List[Dict[str, Any]] = []
    try:
        for c in cases:
            for row in bat.run(c):
                rows.append(row)
                worst = next((f"{k}: {v['detail']}" for k, v in row["instruments"].items()
                              if v["state"] in ("fail", "refused")), "")
                if row["state"] == "alias":
                    worst = f"= {row['alias_of']}"
                mark = {"pass": "PASS", "fail": "FAIL", "refused": "RFSD",
                        "alias": "ALIAS"}[row["state"]]
                print(f"[{mark:5}] {row['case'][:72]:72} {row['seconds']:6.2f}s  "
                      f"{worst[:120]}", flush=True)
        if not (a.no_pinned or a.quick or rx is not None or sources):
            for key, thunk in _catalog().items():
                r = _run_one(key, thunk, os.path.join(out, "pinned"), inv, battery=bat,
                             rebuildable=True)
                r["case"] = f"pinned:{key}@{bat.native}"
                print(f"[{'PASS' if r['ok'] else 'FAIL':5}] {r['case']:72} "
                      f"{r['seconds']:6.2f}s", flush=True)
                pinned.append(r)
    finally:
        if twin is not None:
            twin.close()

    by_source: Dict[str, int] = {}
    for r in rows:
        by_source[r["tuple"]["source"]] = by_source.get(r["tuple"]["source"], 0) + 1
    report: Dict[str, Any] = {
        "tool": "tools/self_battery.py", "issue": 796,
        "mode": "quick" if a.quick else "full",
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "argv": args,
        "env": env,
        "releases": {"run": run_rel, "skipped": skipped, "broken": {str(y): w for y, w in
                                                                    broken.items()},
                     "bases": {str(y): os.path.relpath(p, ROOT) for y, p in bases.items()}},
        "declarations": decl,
        "corpus": cblk,
        "determinism": (twin.describe() if twin is not None else
                        {"mode": "in-process", "time_shift_s": TIME_SHIFT_S,
                         "time_shift": _shift_text(TIME_SHIFT_S),
                         "hash_seed": parent_hash_seed()}),
        "alias_pin": {"path": os.path.relpath(os.path.abspath(a.aliases), ROOT),
                      "groups": len(pin.get("groups") or []),
                      "relations": sum(len(g) - 1 for g in pin.get("groups") or []),
                      "missing": bool(pin.get("missing")),
                      "enforced": not a.pin_aliases},
        "matrix": {"cases": len(rows), "enumerated": len(cases),
                   "per_release": len(base_cases),
                   "distinct": sum(1 for r in rows if r["state"] != "alias"),
                   "by_source": by_source},
        "summary": summarize(rows, groups),
        "rows": rows,
        "pinned": pinned,
    }
    report["seconds"] = round(time.time() - t_start, 1)
    rp = os.path.abspath(a.report or (out.rstrip(os.sep) + ".json"))
    os.makedirs(os.path.dirname(rp), exist_ok=True)
    with open(rp, "w") as fh:
        json.dump(report, fh, indent=1, default=str)
    txt = text_summary(report)
    with open(os.path.splitext(rp)[0] + ".txt", "w") as fh:
        fh.write(txt + "\n")
    if a.pin_aliases:
        newpin = pin_from_rows(rows)
        with open(a.aliases, "w") as fh:
            json.dump(newpin, fh, indent=1)
            fh.write("\n")
        print(f"alias pin -> {a.aliases}: {len(newpin['groups'])} groups, "
              f"{newpin['relations']} relations")
    if a.json:
        print(json.dumps(report, indent=1, default=str))
    print("\n" + txt + f"\nreport -> {rp}")
    return exit_code(report, pinned, cblk, rows)


def exit_code(report: Dict[str, Any], pinned: Sequence[Dict[str, Any]],
              cblk: Dict[str, Any], rows: Sequence[Dict[str, Any]]) -> int:
    """1 when ANYTHING failed: a FAIL row (a BROKEN release is one), a pinned
    probe, a corpus that was asked for and failed or mined only partly, or a
    run that executed no case at all; else 0."""
    failed = report["summary"]["totals"]["fail"] + sum(1 for r in pinned if not r["ok"])
    if cblk.get("state") in ("fail", "partial"):
        failed += 1
    if not rows:
        failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
