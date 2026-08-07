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
  [the version-model stream's proven context].
* The module-local framing-tag copies ``versions.reading`` cannot reach
  [tools/genesis_2025.py::context_2025's proven list]: ``rvt.reduce``,
  ``rvt.manipulate``, ``rvt.commit``, ``rvt.writer`` block/trailer tags and
  ``rvt.famgen.factory``'s ContentDocuments separator/end-record.
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
"""
from __future__ import annotations

import contextlib
import functools
import importlib
import struct
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

from .. import versions as V

__all__ = ["ReleaseContextError", "native_release", "needs_release_context",
           "release_build_context", "active_release"]


class ReleaseContextError(RuntimeError):
    """The base's release cannot be activated; the message names the ONE
    missing piece (unknown release, uncertified, or no port layer)."""


#: the currently ACTIVE non-default release context (None outside one).
_ACTIVE: Dict[str, Any] = {"release": None}


def active_release() -> Optional[int]:
    """The release year of the innermost active build context, or None."""
    return _ACTIVE["release"]


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
    schema = V.schema_of(base_path)
    want = V.KNOWN_RELEASES[year].schema_sha256
    got = schema.stats()["sha256"]
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

@contextlib.contextmanager
def release_build_context(base_path: str) -> Iterator[Optional[Dict[str, Any]]]:
    """Run the build stack against ``base_path``'s own release.

    No-op (yields None) when the base IS the native release.  Otherwise
    yields a small info dict and keeps every swap active until exit."""
    year = V.detect_release(base_path)
    if year is None:
        raise ReleaseContextError(
            f"cannot detect the Revit release of {base_path} -- refusing to "
            "guess the emit framing")
    if year == native_release():
        yield None
        return
    rel = V.KNOWN_RELEASES.get(year)
    if rel is None or not rel.creation_certified:
        raise ReleaseContextError(
            f"Revit {year} is not a certified creation release "
            f"(KNOWN_RELEASES[{year}].creation_certified is not True) -- "
            "resolve_base should never have produced this base")
    port = _port_module(year)
    dec, enc, schema = _codec_triple_from_base(base_path, year)

    saved: List[Tuple[Any, str, Any]] = []

    def swap(obj: Any, name: str, value: Any) -> None:
        saved.append((obj, name, getattr(obj, name)))
        setattr(obj, name, value)

    import os

    from .. import adocument as ADOC
    from .. import commit as COMMIT
    from .. import encode as ENC
    from .. import manipulate as MANIP
    from .. import mutate as MU
    from .. import reduce as RED
    from .. import regadd as REGADD
    from .. import regdiff as REGDIFF
    from .. import schema as SCHEMA
    from .. import writer as WRITER
    from ..container import open_rvt
    from ..famgen import factory as FF
    from ..famgen import famdoc_adoc as FDA
    from ..famgen import skeleton as FSK
    from ..genesis import skeleton as GSK
    from ..genesis import types as GT
    from ..objects import ObjectDecoder
    from ..stream_encoders import decode_basic_file_info
    from . import standalone as SA

    base_abs = os.path.abspath(base_path)

    with V.reading(base_path) as ords:
        # ---- (1) module-local framing-tag copies (context_2025's list) ----
        swap(RED, "BLOCK_TAG", ords["BLOCK_TAG"])
        swap(RED, "BLOCK_TRL_TAG", ords["TRAILER_TAG"])
        swap(MANIP, "BLOCK_TAG", ords["BLOCK_TAG"])
        swap(MANIP, "TRAILER_TAG", ords["TRAILER_TAG"])
        swap(COMMIT, "BLOCK_TRL_TAG", ords["TRAILER_TAG"])
        swap(WRITER, "BLOCK_TRL_TAG", ords["TRAILER_TAG"])
        swap(FF, "CD_SEPARATOR", struct.pack(
            "<HiHi", ords["CONTAINER_CLASS"], -1, ords["UNIT_INNER_CLASS"], -1))
        swap(FF, "CD_END_RECORD", struct.pack(
            "<HiiI", ords["CONTAINER_CLASS"], 0, -1, 0))
        # ---- (1b) famgen's own framing copies (this stream's addition) ----
        swap(FSK, "_PART_TAG", ords["CONTAINER_CLASS"])
        swap(FSK, "BLOCK_TAG", ords["BLOCK_TAG"])
        swap(FSK, "TRAILER_TAG", ords["TRAILER_TAG"])
        swap(FSK, "FOOTER_TAG", ords["FOOTER_TAG"])
        swap(FDA, "FAMILY_END_RECORD", struct.pack(
            "<Hii", ords["CONTAINER_CLASS"], 0, -1))
        swap(GSK, "EMPTY_CONTENT_DOCUMENTS", struct.pack(
            "<HIII", ords["CONTAINER_CLASS"], 0, 0xFFFFFFFF, 0))
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

        # ---- (2) codec singletons -> the base's schema --------------------
        swap(ENC, "_DEFAULT_ENCODER", enc)
        swap(ADOC, "_DECODER", ADOC.ADocumentDecoder(schema))
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
        orig_load = SCHEMA.load_schema
        orig_default_path = SCHEMA.DEFAULT_PATH

        def _load_schema_ctx(path: str = orig_default_path):
            if path in (None, orig_default_path) or not os.path.isfile(path):
                return schema
            return orig_load(path)

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
        # ----     identity strings from the base's own BasicFileInfo -------
        with open_rvt(base_path) as f:
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

        # ---- (6) standalone resolution: the ACTIVE base is the bundle -----
        orig_bbp = SA.bundled_base_path

        def bbp(explicit: Optional[str] = None, **kw) -> str:
            if explicit:
                return orig_bbp(explicit, **kw)     # caller authority intact
            return base_abs

        swap(SA, "bundled_base_path", bbp)
        prev_sa_state = dict(SA._SCHEMA_STATE)
        SA._SCHEMA_STATE.clear()
        SA._SCHEMA_STATE.update({
            "schema": schema, "from": base_abs,
            "sha256": schema.stats()["sha256"],
            "bytes": schema.stats().get("bytes", 0), "blob": b"",
            "is_corpus_constant": False,
            "installed": True, "installed_from": base_abs,
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

        # ---- (8) donor-id byte scan: corroborate hits against the tree ----
        # famdoc_adoc's zero-donor gate byte-scans the authored family
        # ADocument for the donor's element ids.  With a PROJECT-base donor
        # the id universe is every host element id, and our own authored
        # position-index tables read misaligned as k<<8 i64 windows -- on
        # this base a real element id can collide (2025: Family 18432 ==
        # 72<<8, sitting inside the monotone 52..86 index run).  The scan
        # module itself documents the schema-typed census as the authority;
        # apply exactly that rule, process-locally: a byte window counts
        # ONLY when the decoded tree also carries the id as a value.  A real
        # carried reference stays fatal; a cross-field window is recorded as
        # a named false positive instead of refusing the artefact
        # (deliverable rule: gates are labels, never refusal logic).
        ga = FDA._ga()
        orig_scan = ga.byte_scan_ids

        def _tree_ids(value) -> set:
            out: set = set()

            def walk(node):
                if isinstance(node, dict):
                    for v in node.values():
                        walk(v)
                elif isinstance(node, list):
                    for v in node:
                        walk(v)
                elif isinstance(node, int) and not isinstance(node, bool):
                    out.add(node)

            walk(value)
            return out

        def corroborated_scan(payload, id_set):
            r = orig_scan(payload, id_set)
            if not r.get("hits"):
                return r
            try:
                back = ADOC.decode_latest(bytes(payload))
            except Exception:
                return r                    # cannot corroborate -> keep hits
            if not back.clean:
                return r
            present = _tree_ids(back.value)
            real = [i for i in (r.get("examples") or []) if i in present]
            if real:
                return r                    # tree-corroborated: genuine
            return {**r, "hits": 0, "distinct": 0, "examples": [],
                    "false_positive_windows": r.get("examples"),
                    "false_positive_note": (
                        "byte window(s) matched donor ids but the schema-"
                        "decoded tree carries none of them as a value -- "
                        "cross-field alignment artefact (the module's own "
                        "authority rule); recorded, not fatal")}

        swap(ga, "byte_scan_ids", corroborated_scan)

        info = {"release": year, "native": native_release(),
                "ordinals": dict(ords), "schema_sha256": schema.stats()["sha256"],
                "port_layer": port.__name__, "base": base_abs,
                "bfi": {"format": base_format, "build": base_build}}
        _ACTIVE["release"] = year
        try:
            yield info
        finally:
            _ACTIVE["release"] = None
            for obj, name, val in reversed(saved):
                setattr(obj, name, val)
            GSK._SCHEMA_CACHE.clear()
            GSK._SCHEMA_CACHE.update(prev_cache)
            port._STATE.clear()
            port._STATE.update(prev_port_state)
            SA._SCHEMA_STATE.clear()
            SA._SCHEMA_STATE.update(prev_sa_state)
