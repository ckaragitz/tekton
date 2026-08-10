"""rvt.frontdoor.release_ctx -- THE RELEASE-AWARE BUILD CONTEXT (build-2025).

``rvt.frontdoor.build.build_intent`` constructs on whatever base
``resolve_base`` returned.  The construction stack, however, was written
against ONE release (the registry default -- Revit 2026 today): its framing
tags, class ordinals, codec singletons and a handful of module-local
constants all assume the default release.  When the resolved base is a
DIFFERENT certified release (``--target-version 2025`` resolving the
certified ``G_ABPD_2025``), the build must run inside a context that
re-points every one of those assumptions at the base's own release -- and
restore all of it on exit.

This module IS that context.  It composes the patch sets three sibling
streams proved out, plus the famgen-path additions this stream owns:

* ``rvt.versions.reading(base)`` -- the six partition-framing ordinals in
  ``rvt.partitions`` (+ TERMINATOR + the resync search), read AND write side
  [the version-model stream's proven context].  Every project-side block
  emitter (``rvt.reduce``, ``rvt.writer``, ``rvt.commit``, ``rvt.manipulate``,
  ``rvt.families``, ``rvt.mep.conduit``) reads those names at CALL time, so
  this alone re-points them (#455/#467 retired the per-module tag copies
  tools/genesis_2025.py::context_2025 once had to swap one by one); the rest
  of that list -- ``rvt.famgen.factory``'s ContentDocuments separator/
  end-record -- is ``global_framing.bound``'s (#93).
* The per-release default codecs [run_ladder2025.py's proven swaps]:
  ``rvt.encode._DEFAULT_ENCODER``, ``rvt.adocument._DECODER``,
  ``rvt.regadd``/``rvt.regdiff``'s decoder factories, and the constructor
  singletons ``rvt.genesis.types._STATE`` / ``rvt.genesis.skeleton
  ._SCHEMA_CACHE`` -- all bound to the base's own schema (pin-verified
  against ``KNOWN_RELEASES[year].schema_sha256``).
* The port layer (``rvt.genesis.port2025.adapt``) wired into the FAMGEN
  build path at the record boundary [this stream]: every
  ``SkelElement.records()`` / ``NewElement.records()`` triple is adapted to
  the target schema before encoding, so 2026-shaped constructor literals
  gain the target release's fields with the port layer's MINED corpus
  defaults (e.g. ``GeomTable.m_maxSafeTag = -1``) instead of failing the
  encoder.  The port codec state is seeded FROM THE BASE's schema, so the
  quarantined ``samples/`` corpus is never read (standalone-safe).
* The famgen module-local framing constants [this stream]:
  ``rvt.famgen.skeleton``'s partition tags, ``famdoc_adoc.FAMILY_END_
  RECORD``, the inline save-unit separator of ``factory.build_family_save_
  unit`` (fixed 12-byte rewrite), and the fresh-document global-stream
  model builders in ``rvt.genesis.skeleton`` whose class tags bake default-
  release ordinals (ElemTable / History / DIT / PartitionTable / Contents /
  the empty ContentDocuments payload / BasicFileInfo's format+build) -- all
  re-resolved BY NAME from the base's schema, plus the format/build strings
  read from the base's own BasicFileInfo.
* ``rvt.mutate``'s class-id constants (ElementHeader / SerializedDummy /
  GElement / SWall / FamilyInstance / RbsElectricalSystem) by-name.
* ``rvt.frontdoor.standalone``'s resolution state: ``bundled_base_path``
  returns the ACTIVE base (so the family container donor is the target-
  release base, not the default one) and ``_SCHEMA_STATE`` is force-seeded
  (``install_schema``'s idempotency cannot pin a stale default-release
  schema in a mixed-release process).  The constructed specimen templates
  are adapted through the port layer too.

Keying: ``release_build_context(base_path)`` detects the base's release
(``rvt.versions.detect_release``) and compares it against the REGISTRY
DEFAULT release (``genesis_base.json`` ``default.revit_release`` -- never a
year literal in logic).  Matching release -> a no-op context.  A different
release must be creation-certified in ``KNOWN_RELEASES`` and must have a
port layer module (``rvt.genesis.port<year>``); anything else raises
``ReleaseContextError`` naming the missing piece.

Everything swapped is restored LIFO on exit; nesting is safe; nothing on
disk changes.  Territory: this file + the two-line entry hook in
``rvt.frontdoor.build`` (documented in docs/inbox/build-2025.md).

THE HOST-KEYED ENTRY (famload-2025-lane, issue #14).  The build context is
keyed on the BASE the front door resolved.  Every lane that instead operates
on an EXISTING file -- the four-registry loader ``rvt.famload``, the
component loader ``rvt.famgen.loader``, ``rvt.convert.add_to_project``
(prompt + the user's project), the ``--rvt --edit`` route -- needs the very
same swap set keyed on THAT file's release, or it dies on the first
``StreamWalker`` with ``unexpected Partitions header: v=9 cls=0x391`` (gap B
of docs/inbox/compose-2025.md).  :func:`host_release_context` is that entry:
same mechanism, any existing file, re-entrant (a same-release context that
is already active is joined, not re-applied -- the loaders are called from
inside ``build_intent`` too), and the family CONTAINER donor stays OUR
bundled certified base of the host's release (never the user's file -- rule
3).  The read-only Global-stream tokens both contexts need come from
``rvt.global_framing`` (the leaf the validator's census shares).
"""
from __future__ import annotations

import contextlib
import functools
import importlib
import struct
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

from .. import versions as V

__all__ = ["ReleaseContextError", "native_release", "needs_release_context",
           "release_build_context", "host_release_context", "enter_host_release",
           "active_release"]


class ReleaseContextError(RuntimeError):
    """The base's release cannot be activated; the message names the ONE
    missing piece (unknown release, uncertified, or no port layer)."""


#: the info dict of the ACTIVE non-default release context (None outside one).
_ACTIVE: Dict[str, Any] = {"info": None}


def active_release() -> Optional[int]:
    """The release year of the active non-default release context, or None."""
    info = _ACTIVE["info"]
    return int(info["release"]) if info else None


def native_release() -> int:
    """The construction stack's native release = the registry DEFAULT slot's
    ``revit_release`` (genesis_base.json), never a year literal."""
    from .base import PIN
    return int(PIN.revit_release)


def needs_release_context(base_path: str) -> bool:
    """True when building on ``base_path`` requires the release context."""
    rel = V.detect_release(base_path)
    return rel is not None and rel != native_release()


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def _port_module(year: int):
    """``rvt.genesis.port<year>`` -- the constructor portability layer."""
    name = f"rvt.genesis.port{year}"
    try:
        return importlib.import_module(name)
    except ImportError as e:
        raise ReleaseContextError(
            f"no constructor port layer for Revit {year}: module {name} is "
            f"absent ({e}).  The build context cannot adapt the default-"
            "release constructors without it.") from e


def _codec_triple_from_base(base_path: str, year: int):
    """(decoder, encoder, schema) parsed from the BASE's own Formats/Latest,
    verified against the release pin -- the standalone-safe way to get the
    target schema (never reads samples/)."""
    from ..global_framing import schema_of
    schema = schema_of(base_path)
    want = V.KNOWN_RELEASES[year].schema_sha256
    got = schema.sha256
    if want and got != want:
        raise ReleaseContextError(
            f"base {base_path} carries schema sha256 {got[:16]}... but the "
            f"Revit {year} pin is {want[:16]}... -- refusing to build on an "
            "unpinned schema")
    from ..encode import ObjectEncoder
    from ..objects import ObjectDecoder
    dec = ObjectDecoder(schema)
    enc = ObjectEncoder(decoder=dec)
    return dec, enc, schema


def _by_name(schema, name: str) -> int:
    c = schema.by_name.get(name)
    if c is None:
        raise ReleaseContextError(
            f"class {name!r} is missing from the target schema -- the "
            "fresh-document model builders cannot be re-pointed")
    return int(c.type_id)


# ---------------------------------------------------------------------------
# the adapt boundary (port layer at .records() time)
# ---------------------------------------------------------------------------

def _make_adapter(port, dec) -> Callable[[Any, Any], Any]:
    """(class_id_or_name, obj) -> target-shaped obj via ``port.adapt``.

    The port walk is idempotent for the famgen classes (hooks are constants
    or read source-release-only fields), so re-adapting an already-adapted
    dict is safe; a class the port cannot express raises its own
    ``PortabilityError`` -- an honest hard stop, never a silent skip."""

    def adapt_obj(cls: Any, obj: Any):
        if not isinstance(obj, dict) or not obj:
            return obj                     # SerializedDummy / empty reps
        name = cls if isinstance(cls, str) else dec.class_name(int(cls))
        if not name:
            return obj
        return port.adapt(name, obj)

    return adapt_obj


def _wrap_records_methods(swap, port, dec) -> None:
    """Swap ``genesis.skeleton.SkelElement.records`` and
    ``mutate.NewElement.records`` so every (seq, class, object) triple
    carries a port-adapted object dict.  Every encode path in the famgen
    build flows through one of the two."""
    from ..genesis import skeleton as GSK
    from .. import mutate as MU

    adapt_obj = _make_adapter(port, dec)

    orig_skel = GSK.SkelElement.records

    def skel_records(self, class_ids=None, by_name: bool = False):
        return [(seq, cls, adapt_obj(cls, obj))
                for seq, cls, obj
                in orig_skel(self, class_ids=class_ids, by_name=by_name)]

    orig_new = MU.NewElement.records

    def new_records(self):
        out = []
        for seq, cls, obj in orig_new(self):
            out.append((seq, cls, adapt_obj(cls, obj)))
        return out

    swap(GSK.SkelElement, "records", skel_records)
    swap(MU.NewElement, "records", new_records)


# ---------------------------------------------------------------------------
# the context
# ---------------------------------------------------------------------------

def _classify_release(path: str, *, host: bool):
    """(year, Release, port module) for an existing file, or the no-op marker
    ``(year, None, None)`` when the file IS the native release.  Raises
    ``ReleaseContextError`` naming the one missing piece otherwise."""
    what = "host lane (load/place/edit)" if host else "build"
    year = V.detect_release(path)
    if year is None:
        raise ReleaseContextError(
            f"cannot detect the Revit release of {path} -- refusing to "
            "guess the emit framing")
    if year == native_release():
        return year, None, None
    rel = V.KNOWN_RELEASES.get(year)
    if rel is None or not rel.creation_certified:
        raise ReleaseContextError(
            f"Revit {year} is not a certified creation release "
            f"(KNOWN_RELEASES[{year}].creation_certified is not True) -- "
            f"the {what} cannot author into a Revit {year} file")
    return year, rel, _port_module(year)


def _bundled_base_of(year: int) -> Optional[str]:
    """OUR pinned + certified genesis base of ``year`` from bundled locations
    (repo pin path or the plugin bundle), or None when it does not resolve.
    The family CONTAINER donor of a host-keyed context: never the user's own
    file (rule 3), always our composed base of the same release."""
    try:
        from .base import resolve_base
        rb = resolve_base(target_release=int(year))
    except Exception:                                   # noqa: BLE001
        return None
    return rb.path if (rb.pinned and rb.certified) else None


@contextlib.contextmanager
def release_build_context(base_path: str) -> Iterator[Optional[Dict[str, Any]]]:
    """Run the build stack against ``base_path``'s own release.

    No-op (yields None) when the base IS the native release.  Otherwise
    yields a small info dict and keeps every swap active until exit.  A
    same-release context that is already active is joined (yields its info)
    instead of re-applied."""
    with _release_context(base_path, host=False) as info:
        yield info


@contextlib.contextmanager
def host_release_context(host_path: str) -> Iterator[Optional[Dict[str, Any]]]:
    """Run a load / place / edit lane against an EXISTING file's own release
    (the famload-2025 lane's entry -- gap B).

    ``host_path`` is any readable project: our own output, a bundled base or
    the user's file.  No-op (yields None) for a native-release host; joins an
    already-active same-release context; otherwise applies exactly the build
    context's swap set keyed on the HOST's release, with the family container
    donor pinned to our bundled certified base of that release."""
    with _release_context(host_path, host=True) as info:
        yield info


def enter_host_release(stack: contextlib.ExitStack, host_path: str) -> Optional[str]:
    """Enter :func:`host_release_context` on ``stack`` for a lane that must
    still SURVEY / REPORT when the host's release cannot be authored into
    (an uncertified or undetectable release).  Returns None when the context
    is in force (or the host is native), else the refusal sentence -- the
    caller records it and its own guard refuses honestly downstream."""
    try:
        stack.enter_context(host_release_context(host_path))
        return None
    except ReleaseContextError as e:
        return f"no release context for {host_path}: {e}"


@contextlib.contextmanager
def _release_context(path: str, *, host: bool) -> Iterator[Optional[Dict[str, Any]]]:
    year, rel, port = _classify_release(path, host=host)
    if rel is None:
        yield None
        return
    active = _ACTIVE["info"]
    if active is not None:
        if int(active["release"]) == year:
            yield active                          # re-entrant: join, don't stack
            return
        raise ReleaseContextError(
            f"a Revit {active['release']} release context is active; cannot "
            f"enter a Revit {year} context for {path} inside it (one release "
            "per process scope -- exit the outer context first)")
    dec, enc, schema = _codec_triple_from_base(path, year)

    saved: List[Tuple[Any, str, Any]] = []

    def swap(obj: Any, name: str, value: Any) -> None:
        saved.append((obj, name, getattr(obj, name)))
        setattr(obj, name, value)

    import os

    from .. import encode as ENC
    from .. import global_framing as GF
    from .. import mutate as MU
    from .. import regadd as REGADD
    from .. import regdiff as REGDIFF
    from .. import schema as SCHEMA
    from ..container import open_rvt
    from ..famgen import factory as FF
    from ..famgen import famdoc_adoc as FDA
    from ..famgen import skeleton as FSK
    from ..genesis import skeleton as GSK
    from ..genesis import types as GT
    from ..objects import ObjectDecoder
    from ..stream_encoders import decode_basic_file_info
    from . import standalone as SA

    path_abs = os.path.abspath(path)
    # the family CONTAINER donor + standalone "active base": the build's own
    # base, or -- for a host lane -- our bundled certified base of the host's
    # release (falls back to the host only when no bundle resolves, recorded)
    donor_abs = path_abs
    donor_note = "build base"
    if host:
        bundled = _bundled_base_of(year)
        if bundled:
            donor_abs = os.path.abspath(bundled)
            donor_note = "bundled certified base of the host's release"
        else:
            donor_note = ("the host itself (no bundled certified base of "
                          f"Revit {year} resolved) -- family containers would "
                          "borrow the host's Formats/Latest")

    with V.reading(schema=schema) as ords, GF.bound(ords, schema=schema):
        # ---- (1) block framing is V.reading's alone (every project-side --
        # ----     emitter reads rvt.partitions at call time, #467); the ----
        # ----     famgen framing copies still need swapping (#547) ---------
        swap(FSK, "_PART_TAG", ords["CONTAINER_CLASS"])
        swap(FSK, "BLOCK_TAG", ords["BLOCK_TAG"])
        swap(FSK, "TRAILER_TAG", ords["TRAILER_TAG"])
        swap(FSK, "FOOTER_TAG", ords["FOOTER_TAG"])
        # build_family_save_unit bakes its 12-byte unit separator inline;
        # rewrite exactly those 12 bytes on the way out (framing only,
        # payload untouched)
        orig_bfsu = FF.build_family_save_unit

        def bfsu(doc, **kw):
            unit = orig_bfsu(doc, **kw)
            sep = (struct.pack("<Hi", ords["CONTAINER_CLASS"], -1)
                   + struct.pack("<HI", ords["UNIT_INNER_CLASS"],
                                 int(unit["record_count"])))
            body = unit["bytes"]
            unit["bytes"] = sep + body[len(sep):]
            return unit

        swap(FF, "build_family_save_unit", bfsu)

        # ---- (2) codec singletons -> the base's schema (the ADocument -----
        # ----     decoder is GF.bound's) -----------------------------------
        swap(ENC, "_DEFAULT_ENCODER", enc)
        swap(REGADD, "ObjectDecoder", functools.partial(ObjectDecoder, schema))
        swap(REGDIFF, "ObjectDecoder", functools.partial(ObjectDecoder, schema))
        # constructor singletons (genesis.types._STATE is read via _S())
        swap(GT, "_STATE", {"dec": dec, "enc": enc, "schema": schema})
        # genesis.skeleton's shared cache is a dict consumers read by key
        prev_cache = dict(GSK._SCHEMA_CACHE)
        GSK._SCHEMA_CACHE.clear()
        GSK._SCHEMA_CACHE.update({"dec": dec, "enc": enc})
        # the port layer's own target-codec state: seed from the base so the
        # quarantined samples/ corpus is NEVER read (standalone rule)
        yy = f"s{year % 100}"
        if not hasattr(port, f"_S{year % 100}"):
            raise ReleaseContextError(
                f"port layer {port.__name__} lacks _S{year % 100}() -- "
                "cannot seed its codec state")
        prev_port_state = dict(port._STATE)
        port._STATE[yy] = (dec, enc, schema)
        # rvt.schema default chokepoints (install_schema's reroute, but
        # scoped + restored; a mixed-release process may hold stale seeds)
        _load_schema_ctx = SA.default_schema_loader(schema, SCHEMA.DEFAULT_PATH)

        from .. import adocument as ADOC
        from .. import objects as OBJECTS
        swap(SCHEMA, "load_schema", _load_schema_ctx)
        for _m in (OBJECTS, ENC, ADOC):
            swap(_m, "load_schema", _load_schema_ctx)

        # ---- (3) mutate's class-id constants, by name ---------------------
        swap(MU, "CLASS_ELEMENT_HEADER", _by_name(schema, "ElementHeader"))
        swap(MU, "CLASS_SERIALIZED_DUMMY", _by_name(schema, "SerializedDummy"))
        swap(MU, "CLASS_GELEMENT", _by_name(schema, "GElement"))
        swap(MU, "CLASS_SWALL", _by_name(schema, "SWall"))
        swap(MU, "CLASS_FAMILY_INSTANCE", _by_name(schema, "FamilyInstance"))
        swap(MU, "CLASS_ELECTRICAL_SYSTEM", _by_name(schema, "RbsElectricalSystem"))

        # ---- (4) fresh-document global models: class tags by name, --------
        # ----     identity strings from OUR base's own BasicFileInfo -------
        # ----     (the donor: never a user's host file -- rule 6) ----------
        with open_rvt(donor_abs) as f:
            bfi = decode_basic_file_info(f.raw("BasicFileInfo"))
        base_format = str(bfi.get("format") or year)
        base_build = str(bfi.get("build") or "")

        orig_hist = GSK.minimal_history

        def hist(*a, **kw):
            m = orig_hist(*a, **kw)
            m["class_tag"] = _by_name(schema, "DocumentHistory")
            return m

        orig_et = GSK.minimal_elemtable

        def et(*a, **kw):
            m = orig_et(*a, **kw)
            m["class_tag"] = _by_name(schema, "ElemTable")
            m["footer"]["tail_class"] = _by_name(schema, "IdentifierSource")
            return m

        orig_dit = GSK.minimal_increment_table

        def dit(*a, **kw):
            m = orig_dit(*a, **kw)
            m["type_tag"] = _by_name(schema, "DocumentIncrementTable")
            return m

        orig_pt = GSK.minimal_partition_table

        def pt(*a, **kw):
            m = orig_pt(*a, **kw)
            m["class_ordinal"] = _by_name(schema, "PartitionTable")
            return m

        orig_contents = GSK.minimal_contents

        def contents(*a, **kw):
            kw.setdefault("build", base_build)
            pro, pay = orig_contents(*a, **kw)
            pay["type_tag"] = _by_name(schema, "DocumentStorageIndexImpl")
            pay["trailing_pairs"] = [(-1, _by_name(schema, "EditingPermissionsImpl")),
                                     (-1, _by_name(schema, "EditingRequestsImpl"))]
            return pro, pay

        orig_bfi_model = GSK.minimal_basic_file_info

        def bfi_model(*a, **kw):
            kw.setdefault("format_year", base_format)
            if base_build:
                kw.setdefault("build", base_build)
            return orig_bfi_model(*a, **kw)

        swap(GSK, "minimal_history", hist)
        swap(GSK, "minimal_elemtable", et)
        swap(GSK, "minimal_increment_table", dit)
        swap(GSK, "minimal_partition_table", pt)
        swap(GSK, "minimal_contents", contents)
        swap(GSK, "minimal_basic_file_info", bfi_model)

        # ---- (5) the carried-schema pin the family emitters verify --------
        pin_prefix = (rel.schema_sha256 or "")[:8]
        swap(FF, "FORMATS_LATEST_SHA256_PREFIX", pin_prefix)
        swap(FDA, "FORMATS_LATEST_SHA256_PREFIX", pin_prefix)

        # ---- (6) standalone resolution: the ACTIVE base is OUR base of ----
        # ----     this release (the family container donor) ---------------
        orig_bbp = SA.bundled_base_path

        def bbp(explicit: Optional[str] = None, **kw) -> str:
            if explicit:
                return orig_bbp(explicit, **kw)     # caller authority intact
            return donor_abs

        swap(SA, "bundled_base_path", bbp)
        prev_sa_state = dict(SA._SCHEMA_STATE)
        SA._SCHEMA_STATE.clear()
        SA._SCHEMA_STATE.update({
            "schema": schema, "from": path_abs,
            "sha256": schema.sha256,
            "bytes": schema.total_size, "blob": b"",
            "is_corpus_constant": False,
            "installed": True, "installed_from": path_abs,
            "decoder": dec, "encoder": enc,
        })
        # the constructed specimen templates through the port layer (mined
        # corpus defaults for target-only fields, e.g. GeomTable -1/-1)
        def _adapted_template(orig_fn, cls_name: str):
            @functools.wraps(orig_fn)
            def run(schema_arg, **kw):
                hdr, obj = orig_fn(schema_arg, **kw)
                return port.adapt("ElementHeader", hdr), port.adapt(cls_name, obj)
            return run

        swap(SA, "family_instance_template",
             _adapted_template(SA.family_instance_template, "FamilyInstance"))
        swap(SA, "swall_template", _adapted_template(SA.swall_template, "SWall"))

        # ---- (7) the record-boundary port adaptation ----------------------
        _wrap_records_methods(swap, port, dec)

        # (8) -- retired: the donor-id byte-scan corroboration this context
        # used to monkeypatch onto genesis_assemble.byte_scan_ids now lives at
        # famdoc_adoc's own raise sites (corroborated_donor_scan, issue #12),
        # so every release path -- 2026 included -- gets it.

        # "base" = OUR base of this release (the family container donor);
        # "path" = the file the context is keyed on (== base for a build)
        info = {"release": year, "native": native_release(),
                "ordinals": dict(ords), "schema_sha256": schema.sha256,
                "port_layer": port.__name__, "base": donor_abs,
                "base_note": donor_note, "keyed_on": ("host" if host else "base"),
                "path": path_abs,
                "bfi": {"format": base_format, "build": base_build}}
        _ACTIVE["info"] = info
        try:
            yield info
        finally:
            _ACTIVE["info"] = None
            for obj, name, val in reversed(saved):
                setattr(obj, name, val)
            GSK._SCHEMA_CACHE.clear()
            GSK._SCHEMA_CACHE.update(prev_cache)
            port._STATE.clear()
            port._STATE.update(prev_port_state)
            SA._SCHEMA_STATE.clear()
            SA._SCHEMA_STATE.update(prev_sa_state)
