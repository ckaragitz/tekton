"""rvt.schema_cache -- BUILD-TIME cache of parsed ``Formats/Latest`` schemas.

WHY (perf-coldstart stream, 2026-08-04): on the sandboxed AI surfaces the
plugin runs on (Cowork VM, code_execution, Claude Design) every process pays
``rvt.schema.parse`` over the ~500 KB per-release class map on first use
(~67 ms on the reference bare env, system python 3.9).  The schema is a
RELEASE CONSTANT (byte-identical across every file of a release -- sha256
``6459a9a9...`` for Revit 2026), so the parse result is a pure function of
the stream bytes.  This module moves that parse to PLUGIN BUILD time:

  * BUILD (``python -m rvt.schema_cache build`` / the ``tools/sync_plugin.py``
    step): parse each bundled release schema once and emit a compact,
    deterministic cache file ``<schema-sha256>.tksc`` plus ``index.json``
    into ``plugin/assets/schema_cache/``.
  * RUNTIME (:func:`install`, wired by ``skills/_shared/tekton_env.py``'s
    ``ensure_engine``): registers :func:`disk_loader` as a miss loader on
    ``rvt.schema`` (``register_miss_loader``), so on a memo miss
    ``rvt.schema.parse`` first looks the input's sha256 up in the cache
    directory and reconstructs the parsed :class:`rvt.schema.Schema` from
    the cache; ONLY when no cache file answers does the real parser run.
    The key IS the content hash, so the cache can never serve a schema for
    bytes it was not built from.  The hook lives inside ``parse`` under
    ``rvt.schema``'s sha256-keyed memo (issue #183): nothing is rebound, the
    import order of ``from rvt.schema import parse`` binders is irrelevant,
    and a job pays at most ONE cache load per distinct schema, not one per
    decoder construction.

FORMAT: ``TKSC`` magic + one marshal(version 2) payload of plain tuples /
dicts (no code objects, no pickle -- loading a hostile file cannot execute
code; any structural surprise returns a miss, never an exception).  Marshal
v2 of the same payload is byte-deterministic, which is what lets
``sync_plugin.py --check`` treat the cache like any other synced asset.

Fidelity is proven, not assumed: ``tests/test_coldstart.py`` compares the
reconstructed schema class-for-class (id / name / parent / version / field
lists / guids) against a fresh parse of the same bytes.

Territory: perf-coldstart stream (``docs/inbox/perf-coldstart.md``).
"""
from __future__ import annotations

import hashlib
import json
import marshal
import os
import sys
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Tuple

MAGIC = b"TKSC"
FORMAT = 1
CACHE_EXT = ".tksc"
CACHE_DIR_ENV = "RVT_SCHEMA_CACHE_DIR"
ASSETS_REL = os.path.join("assets", "schema_cache")

__all__ = [
    "schema_to_payload", "payload_to_schema", "dump_cache", "load_cache_file",
    "cache_dirs", "load_cached", "disk_loader", "install", "build_cache",
    "sync_assets",
]


# ---------------------------------------------------------------------------
# payload <-> Schema (lossless for every runtime-consumed attribute)
# ---------------------------------------------------------------------------

def _field_to_tuple(f) -> tuple:
    return (f.name, f.kind, f.flags, f.offset, f.count, f.type_id, f.type_name,
            1 if f.inline_definition else 0,
            _field_to_tuple(f.element) if f.element is not None else None,
            f.extra)


def _class_to_tuple(c) -> tuple:
    return (c.type_id, c.name, c.version, c.offset, c.end, c.depth,
            c.parent_id, c.parent, 1 if c.parent_inline else 0,
            tuple(_field_to_tuple(f) for f in c.fields), tuple(c.guids))


def schema_to_payload(s) -> Dict[str, Any]:
    """A marshal-able, deterministic dict carrying the WHOLE parsed schema --
    a function of the stream bytes alone: ``Schema.source`` (which caller
    materialised the object) is per-process provenance, never content, so
    the payload carries a constant in its place."""
    return {
        "format": FORMAT,
        "sha256": s.sha256,
        "total_size": s.total_size,
        "consumed": s.consumed,
        "trailing_pad": s.trailing_pad,
        "source": "",
        "classes": tuple(_class_to_tuple(c) for c in s.classes),
        "top_level_ids": tuple(c.type_id for c in s.top_level),
        "desc_hist": tuple(sorted((k, n) for k, n in s.desc_hist.items())),
        "type_refs": tuple(sorted((k, n) for k, n in s.type_refs.items())),
        "unresolved": tuple(tuple(u) for u in s.unresolved),
    }


def _tuple_to_field(t, Field):
    (name, kind, flags, offset, count, type_id, type_name, inline, elem, extra) = t
    return Field(name=name, kind=kind, flags=flags, offset=offset, count=count,
                 type_id=type_id, type_name=type_name,
                 inline_definition=bool(inline),
                 element=_tuple_to_field(elem, Field) if elem is not None else None,
                 extra=extra)


def payload_to_schema(payload: Dict[str, Any], source: str = ""):
    """Rebuild a :class:`rvt.schema.Schema` (real ClassDef/Field dataclasses,
    all lookup indices) from a payload."""
    from .schema import Schema, ClassDef, Field
    s = Schema()
    s.sha256 = payload["sha256"]
    s.total_size = payload["total_size"]
    s.consumed = payload["consumed"]
    s.trailing_pad = payload["trailing_pad"]
    s.source = source or payload.get("source", "")
    for t in payload["classes"]:
        (type_id, name, version, offset, end, depth, parent_id, parent,
         parent_inline, fields, guids) = t
        cd = ClassDef(type_id=type_id, name=name, version=version, offset=offset,
                      end=end, depth=depth, parent_id=parent_id, parent=parent,
                      parent_inline=bool(parent_inline),
                      fields=[_tuple_to_field(ft, Field) for ft in fields],
                      guids=list(guids))
        s.classes.append(cd)
        s.by_id[cd.type_id] = cd
        s.by_name.setdefault(cd.name, cd)     # first definition wins (parser rule)
    top = set(payload["top_level_ids"])
    s.top_level = [c for c in s.classes if c.type_id in top]
    s.desc_hist = Counter({tuple(k): n for k, n in payload["desc_hist"]})
    s.type_refs = Counter({k: n for k, n in payload["type_refs"]})
    s.unresolved = [tuple(u) for u in payload["unresolved"]]
    s._from_cache = True                  # verifiable provenance (tests / debugging)
    return s


# ---------------------------------------------------------------------------
# cache files
# ---------------------------------------------------------------------------

def dump_cache(schema, path: str) -> str:
    """Write ``schema`` as one deterministic cache file; returns the path."""
    payload = schema_to_payload(schema)
    blob = MAGIC + marshal.dumps(payload, 2)
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(blob)
    return path


def load_cache_file(path: str, source: str = ""):
    """Schema from one cache file, or ``None`` on ANY problem (bad magic,
    wrong format, truncation, structural surprise) -- a miss, never a crash."""
    try:
        with open(path, "rb") as fh:
            blob = fh.read()
        if not blob.startswith(MAGIC):
            return None
        payload = marshal.loads(blob[len(MAGIC):])
        if not isinstance(payload, dict) or payload.get("format") != FORMAT:
            return None
        return payload_to_schema(payload, source=source)
    except Exception:                                     # noqa: BLE001
        return None


def cache_dirs(extra: Optional[Iterable[str]] = None) -> List[str]:
    """Candidate cache directories, most specific first:
    ``$RVT_SCHEMA_CACHE_DIR`` -> the plugin bundle (``$RVT_PLUGIN_ROOT`` or
    the bundled-engine layout ``<root>/lib/src/rvt`` above this file) ->
    the repo layout (``<repo>/plugin/assets/schema_cache``)."""
    dirs: List[str] = list(extra or ())
    envd = os.environ.get(CACHE_DIR_ENV)
    if envd:
        dirs.append(envd)
    envr = os.environ.get("RVT_PLUGIN_ROOT")
    if envr:
        dirs.append(os.path.join(envr, ASSETS_REL))
    here = os.path.dirname(os.path.abspath(__file__))       # .../src/rvt
    up3 = os.path.abspath(os.path.join(here, "..", "..", ".."))
    if os.path.basename(os.path.dirname(here)) == "src":
        dirs.append(os.path.join(up3, ASSETS_REL))          # plugin: <root>/lib/src/rvt
        up2 = os.path.abspath(os.path.join(here, "..", ".."))
        dirs.append(os.path.join(up2, "plugin", ASSETS_REL))  # repo: <repo>/src/rvt
    out, seen = [], set()
    for d in dirs:
        ad = os.path.abspath(d)
        if ad not in seen and os.path.isdir(ad):
            seen.add(ad)
            out.append(ad)
    return out


def _load_cached_from_disk(digest: str, dirs: Optional[Iterable[str]],
                           source: str):
    name = digest + CACHE_EXT
    for d in cache_dirs(dirs):
        p = os.path.join(d, name)
        if os.path.isfile(p):
            got = load_cache_file(p, source=source)
            if got is not None and got.sha256.lower() == digest:
                return got
    return None


def load_cached(sha256_hex: str, dirs: Optional[Iterable[str]] = None,
                source: str = ""):
    """Schema for the stream whose sha256 is ``sha256_hex``, from the first
    cache dir that has it; ``None`` on miss.  Shares ``rvt.schema``'s
    in-process memo (issue #183): a digest already materialised in this
    process -- by the parser or by an earlier cache load -- is returned as
    the same object without touching the disk again."""
    from .schema import memoized
    digest = sha256_hex.lower()
    return memoized(digest, lambda: _load_cached_from_disk(digest, dirs, source))


# ---------------------------------------------------------------------------
# runtime installation -- make rvt.schema.parse cache-aware
# ---------------------------------------------------------------------------

def disk_loader(digest: str, source: str = ""):
    """The miss loader :func:`install` registers on ``rvt.schema``: the
    Schema rebuilt from the first of :func:`cache_dirs` holding
    ``<digest>.tksc``, or ``None`` (never raises) so the real parser runs."""
    return _load_cached_from_disk(digest, None, source)


def install() -> Dict[str, Any]:
    """Register :func:`disk_loader` with ``rvt.schema.register_miss_loader``
    so every ``rvt.schema.parse`` miss tries the sha256-keyed cache (the
    dirs of :func:`cache_dirs`; ``$RVT_SCHEMA_CACHE_DIR`` adds one) before
    the byte-level parser.  Nothing is rebound; idempotent; returns a small
    report.  Per process each distinct stream costs at most ONE cache-file
    load (or one real parse) -- the memo above the hook sees to that."""
    from .schema import register_miss_loader
    fresh = register_miss_loader(disk_loader)
    return {"installed": "rvt.schema miss loader (sha256-keyed .tksc, miss -> parser)"
                         if fresh else "(already)",
            "dirs": cache_dirs()}


# ---------------------------------------------------------------------------
# build time -- parse each bundled release schema once
# ---------------------------------------------------------------------------

def _iter_bundled_sources(plugin_root: str) -> List[str]:
    """Every bundled container that carries a release schema: the certified
    genesis base(s) under ``assets/genesis`` (one per shipped release) plus
    any constructed donor under ``assets/family``."""
    out: List[str] = []
    for rel in (os.path.join("assets", "genesis"), os.path.join("assets", "family")):
        d = os.path.join(plugin_root, rel)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if f.lower().endswith((".rvt", ".rfa")):
                out.append(os.path.join(d, f))
    return out


def _release_of(plugin_root: str, src_path: str) -> Optional[str]:
    """Best-effort release label from the front door's pin (soft: None when
    the pin does not know this file)."""
    pin = os.path.join(plugin_root, "lib", "src", "rvt", "frontdoor", "assets",
                       "genesis_base.json")
    if not os.path.isfile(pin):
        pin = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "frontdoor", "assets", "genesis_base.json")
    try:
        with open(pin) as fh:
            p = json.load(fh)
        want = str(p["default"]["sha256"]).lower()
        h = hashlib.sha256()
        with open(src_path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        if h.hexdigest().lower() == want:
            return str(p["default"].get("revit_release") or "") or None
    except Exception:                                       # noqa: BLE001
        pass
    return None


def build_cache(plugin_root: str, out_dir: Optional[str] = None) -> Dict[str, Any]:
    """Parse the schema embedded in every bundled container and write the
    cache files + ``index.json`` into ``out_dir`` (default: the plugin's
    ``assets/schema_cache``).  One release constant -> one file, however many
    bundled containers carry it."""
    try:                                  # engine dep; plugin vendors a fallback
        import olefile  # noqa: F401
    except ImportError:
        vend = os.path.join(plugin_root, "skills", "_shared", "_vendor")
        if os.path.isdir(os.path.join(vend, "olefile")) and vend not in sys.path:
            sys.path.append(vend)
    from .container import open_rvt
    # a real parse, never a memo hit: the cache is always (re)built from the
    # byte-level parser, not re-serialised from an earlier cache load
    from .schema import parse_uncached as _parse
    out_dir = out_dir or os.path.join(plugin_root, ASSETS_REL)
    entries: Dict[str, Dict[str, Any]] = {}
    for src in _iter_bundled_sources(plugin_root):
        with open_rvt(src) as f:
            blob = f.inflate("Formats/Latest", 0)
        digest = hashlib.sha256(blob).hexdigest()
        # POSIX separators: index.json is a build artifact compared byte-for-byte
        # by tools/sync_plugin.py --check, so it must not vary by host platform.
        rel_src = os.path.relpath(src, plugin_root).replace(os.sep, "/")
        if digest in entries:
            entries[digest]["sources"].append(rel_src)
            continue
        schema = _parse(blob)
        dump_cache(schema, os.path.join(out_dir, digest + CACHE_EXT))
        entries[digest] = {
            "schema_sha256": digest,
            "stream_bytes": len(blob),
            "classes": len(schema.classes),
            "revit_release": _release_of(plugin_root, src),
            "sources": [rel_src],
            "file": digest + CACHE_EXT,
        }
    index = {"format": FORMAT, "note": "sha256(Formats/Latest inflated) -> parsed-"
             "schema cache; built by tools/sync_plugin.py via rvt.schema_cache",
             "entries": sorted(entries.values(), key=lambda e: e["schema_sha256"])}
    os.makedirs(out_dir, exist_ok=True)
    # newline="\n": text mode would translate to CRLF on Windows, and this file
    # is byte-compared by tools/sync_plugin.py --check.
    with open(os.path.join(out_dir, "index.json"), "w",
              encoding="utf-8", newline="\n") as fh:
        json.dump(index, fh, indent=1, sort_keys=True)
        fh.write("\n")
    return index


def sync_assets(plugin_root: str, check_only: bool = False) -> List[str]:
    """The ``tools/sync_plugin.py`` step: (re)build the cache into a scratch
    dir, byte-compare against ``<plugin>/assets/schema_cache``, copy on
    difference.  Returns the list of drifted cache paths (empty = in sync)."""
    import shutil
    import tempfile
    dst = os.path.join(plugin_root, ASSETS_REL)
    with tempfile.TemporaryDirectory(prefix="tekton-schema-cache-") as tmp:
        build_cache(plugin_root, out_dir=tmp)
        drift: List[str] = []
        fresh = sorted(os.listdir(tmp))
        for name in fresh:
            s, d = os.path.join(tmp, name), os.path.join(dst, name)
            same = os.path.isfile(d) and open(d, "rb").read() == open(s, "rb").read()
            if not same:
                drift.append(os.path.join(ASSETS_REL, name))
                if not check_only:
                    os.makedirs(dst, exist_ok=True)
                    shutil.copy2(s, d)
        if os.path.isdir(dst):                              # stale entries out
            for name in sorted(os.listdir(dst)):
                if name not in fresh and (name.endswith(CACHE_EXT) or name == "index.json"):
                    drift.append(os.path.join(ASSETS_REL, name) + " (stale)")
                    if not check_only:
                        os.remove(os.path.join(dst, name))
    return drift


# ---------------------------------------------------------------------------
# CLI:  python -m rvt.schema_cache build [--plugin-root R] [--out DIR]
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in ("build", "verify"):
        sys.stderr.write("usage: python -m rvt.schema_cache {build|verify} "
                         "[--plugin-root R] [--out DIR]\n")
        return 2

    def _opt(name: str) -> Optional[str]:
        return argv[argv.index(name) + 1] if name in argv else None

    root = _opt("--plugin-root")
    if root is None:
        here = os.path.dirname(os.path.abspath(__file__))
        cand = os.path.abspath(os.path.join(here, "..", "..", ".."))     # plugin layout
        root = cand if os.path.isdir(os.path.join(cand, "assets", "genesis")) \
            else os.path.join(os.path.abspath(os.path.join(here, "..", "..")), "plugin")
    if argv[0] == "verify":
        drift = sync_assets(root, check_only=True)
        for d in drift:
            print(f"SCHEMA-CACHE DRIFT: {d}")
        print("schema cache " + ("IN SYNC" if not drift else f"DRIFTED ({len(drift)})"))
        return 0 if not drift else 1
    out = _opt("--out")
    index = build_cache(root, out_dir=out)
    for e in index["entries"]:
        print(f"cached {e['schema_sha256'][:16]}...  {e['classes']} classes  "
              f"{e['stream_bytes']:,} B  release={e['revit_release'] or '?'}  "
              f"sources={e['sources']}")
    print(f"wrote {len(index['entries'])} cache file(s) + index.json -> "
          f"{out or os.path.join(root, ASSETS_REL)}")
    return 0


if __name__ == "__main__":                                  # pragma: no cover
    raise SystemExit(main())
